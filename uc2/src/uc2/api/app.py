"""FastAPI `uc2.api:app` auf Port 8102 (#44, PRD S8): Start, Liste, Ereignisstrom (SSE) und Bericht.

Start: `uv run uvicorn uc2.api:app --port 8102` (aus `uc2/`). Die API schreibt nie in einen Fall:
`POST /faelle` startet `uv run uc2 verhandlung` als Unterprozess (`uc2.api.start`), alles andere liest PG.
Höchstens ein laufender Fall je API-Prozess; ein zweiter Start ergibt 409. Das ersetzt ein Rate-Limit,
weil die Seite öffentlich ist. Echte Modelle nur mit `UC2_API_ECHTE_MODELLE=1`, sonst 403;
Standard ist `mock`.

Jede Ausgabe läuft durch `uc2.api.belegfilter` (online nur Zitatfelder je Beleg). Eine PG-Verbindung je
Anfrage, beim SSE-Strom für dessen Dauer; Fehler gehen als JSON ohne Stacktrace hinaus.
"""

from __future__ import annotations

import asyncio
import json
import os
import threading
from collections.abc import AsyncIterator, Callable
from contextlib import closing
from datetime import date, datetime
from typing import Any, Literal

import psycopg
from fastapi import FastAPI, Header, HTTPException, Query, Request
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, ConfigDict, Field
from starlette.concurrency import run_in_threadpool

from uc2 import db
from uc2.api.belegfilter import daten_fuer_ausgabe, ereignis_fuer_ausgabe
from uc2.api.start import Lauf, Startauftrag, Starter, StartFehler, UnterprozessStarter
from uc2.verhandlung.bericht import bericht
from uc2.verhandlung.cli import MAX_FRAGE, FrageFehler, pruefe_frage
from uc2.verhandlung.fall import FALL_ID, bekannte_faelle
from uc2.verhandlung.speicher import lies_ereignisse, lies_fall, wirksamer_status

PORT = 8102
ECHTE_MODELLE = "UC2_API_ECHTE_MODELLE"
NACHLADEN_S = 0.5
WARTEZEICHEN_S = 15.0
"""Kommentarzeile im Strom, wenn so lange nichts kam (hält Proxys offen)."""
ENDSTATUS = ("fertig", "abgebrochen")
LISTE_MAX = 200

Verbinder = Callable[[], psycopg.Connection[Any]]


class FallStart(BaseModel):
    model_config = ConfigDict(extra="forbid")

    fall: str = Field(pattern=FALL_ID.pattern, description="Fall-ID aus uc2/faelle/")
    frage: str | None = Field(default=None, max_length=MAX_FRAGE * 4)
    provider: Literal["mock", "claude", "azure"] = "mock"
    belege: Literal["fixture", "index"] = "fixture"


def _standard_verbinde() -> psycopg.Connection[Any]:
    return db.verbinde(autocommit=True)


def _iso(wert: object) -> object:
    return wert.isoformat() if isinstance(wert, date | datetime) else wert


def sse(ereignis: dict[str, Any]) -> str:
    """Ein SSE-Block: `id`, `event`, einzeiliges JSON in `data`."""
    daten = json.dumps(jsonable_encoder(ereignis), ensure_ascii=False, separators=(",", ":"))
    return f"id: {ereignis['seq']}\nevent: {ereignis['art']}\ndata: {daten}\n\n"


def erstelle_app(starter: Starter | None = None, verbinde: Verbinder | None = None) -> FastAPI:
    """App mit austauschbarem Starter (Tests: Lauf im Prozess) und Verbindungsfabrik."""
    starte: Starter = starter or UnterprozessStarter()
    verbinde_pg: Verbinder = verbinde or _standard_verbinde
    sperre = threading.Lock()
    aktiv: list[Lauf] = []

    app = FastAPI(title="uc2 HealthPolicy Simulator", version="0.1.0")

    @app.exception_handler(psycopg.OperationalError)
    async def _db_weg(_: Request, __: Exception) -> JSONResponse:
        return JSONResponse({"detail": "Datenbank nicht erreichbar"}, status_code=503)

    @app.exception_handler(Exception)
    async def _intern(_: Request, __: Exception) -> JSONResponse:
        return JSONResponse({"detail": "interner Fehler"}, status_code=500)

    @app.post("/faelle", status_code=202)
    def starte_fall(eingabe: FallStart) -> dict[str, Any]:
        if eingabe.fall not in bekannte_faelle():
            raise HTTPException(404, f"unbekannter Fall {eingabe.fall!r}")
        if eingabe.provider != "mock" and os.environ.get(ECHTE_MODELLE) != "1":
            raise HTTPException(403, f"Provider {eingabe.provider!r} ist gesperrt ({ECHTE_MODELLE}=1 fehlt)")
        if eingabe.belege == "index" and eingabe.provider != "mock":
            raise HTTPException(422, "Belegquelle index ist vor der Maskierung (#43) nur mit mock erlaubt")
        try:
            frage = None if eingabe.frage is None else pruefe_frage(eingabe.frage)
        except FrageFehler as fehler:
            raise HTTPException(422, str(fehler)) from fehler
        if not sperre.acquire(blocking=False):
            raise HTTPException(409, "Es startet gerade ein Fall")
        try:
            if aktiv and aktiv[-1].laeuft():
                raise HTTPException(409, f"Fall {aktiv[-1].fall_id} läuft noch")
            try:
                lauf = starte(Startauftrag(eingabe.fall, eingabe.provider, eingabe.belege, frage))
            except StartFehler as fehler:
                raise HTTPException(500, str(fehler)) from fehler
            aktiv[:] = [lauf]
        finally:
            sperre.release()
        status = "laufend"
        if not lauf.laeuft():
            with closing(verbinde_pg()) as v:
                fall = lies_fall(v, lauf.fall_id)
            status = fall["status"] if fall else "abgebrochen"
        return {"fall_id": lauf.fall_id, "status": status}

    @app.get("/faelle")
    def liste() -> list[dict[str, Any]]:
        with closing(verbinde_pg()) as v:
            try:
                zeilen = v.execute(
                    "select fall_id, fall_name, provider, belegquelle, status, lebenszeichen, start, ende "
                    "from uc2.fall order by fall_id desc limit %s",
                    (LISTE_MAX,),
                ).fetchall()
            except psycopg.errors.UndefinedTable:
                return []
        return [
            {
                "fall_id": z[0],
                "fall": z[1],
                "provider": z[2],
                "belegquelle": z[3],
                "status": wirksamer_status(z[4], z[5]),
                "lebenszeichen": _iso(z[5]),
                "start": _iso(z[6]),
                "ende": _iso(z[7]),
            }
            for z in zeilen
        ]

    def _fall_oder_404(v: psycopg.Connection[Any], fall_id: int) -> dict[str, Any]:
        try:
            fall = lies_fall(v, fall_id)
        except psycopg.errors.UndefinedTable:
            fall = None
        if fall is None:
            raise HTTPException(404, f"Fall {fall_id} nicht gefunden")
        return fall

    @app.get("/faelle/{fall_id}")
    def fall_bericht(fall_id: int) -> Any:
        with closing(verbinde_pg()) as v:
            _fall_oder_404(v, fall_id)
            daten = bericht(v, fall_id)
        return daten_fuer_ausgabe(jsonable_encoder(daten))

    @app.get("/faelle/{fall_id}/ereignisse")
    def ereignisse(
        fall_id: int,
        seq: int = Query(0, ge=0),
        last_event_id: str | None = Header(default=None),
    ) -> StreamingResponse:
        ab = seq
        if last_event_id is not None and last_event_id.strip().isdigit():
            ab = int(last_event_id.strip())  # Wiederverbinden: der Header gewinnt über ?seq
        with closing(verbinde_pg()) as v:
            _fall_oder_404(v, fall_id)
        return StreamingResponse(
            _strom(fall_id, ab),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    async def _strom(fall_id: int, ab: int) -> AsyncIterator[str]:
        letzte = ab
        ruhig = 0.0
        v = await run_in_threadpool(verbinde_pg)
        try:
            while True:
                # Erst den Status, dann die Ereignisse: War der Fall schon beendet, sind alle Ereignisse
                # davor committet und kommen in derselben Runde mit.
                fall = await run_in_threadpool(lies_fall, v, fall_id)
                neu = await run_in_threadpool(lies_ereignisse, v, fall_id, letzte)
                for e in neu:
                    letzte = e["seq"]
                    yield sse(ereignis_fuer_ausgabe(e))
                status = fall["status"] if fall else "abgebrochen"
                if status in ENDSTATUS:
                    ende = {"status": status, "letzte_seq": letzte}
                    yield f"event: ende\ndata: {json.dumps(ende, ensure_ascii=False)}\n\n"
                    return
                ruhig = 0.0 if neu else ruhig + NACHLADEN_S
                if ruhig >= WARTEZEICHEN_S:
                    ruhig = 0.0
                    yield ": warte\n\n"
                await asyncio.sleep(NACHLADEN_S)
        finally:
            await run_in_threadpool(v.close)

    return app
