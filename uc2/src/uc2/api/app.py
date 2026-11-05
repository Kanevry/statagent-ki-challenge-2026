"""FastAPI `uc2.api:app` auf Port 8102 (#44, PRD S8): Start, Liste, Ereignisstrom (SSE) und Bericht.

Start: `uv run uvicorn uc2.api:app --port 8102` (aus `uc2/`). Die API schreibt nie in einen Fall:
`POST /faelle` startet `uv run uc2 verhandlung` als Unterprozess (`uc2.api.start`), alles andere liest PG.
Höchstens ein laufender Fall je API-Prozess; ein zweiter Start ergibt 409. Dazu ein Ratenlimit: höchstens
ein Start je Client-IP und Minute (im Speicher, 429). Hinter einem Proxy sieht die API nur dessen Adresse; das
Limit gilt dann für alle zusammen, was strenger ist. `X-Forwarded-For` wird bewusst nicht gelesen (fälschbar).

Echte Modelle nur mit `UC2_API_ECHTE_MODELLE=1`, sonst 403; Standard ist `mock`. Online (`KIC_ONLINE=1`)
startet ein echtes Modell zusätzlich nur mit gültigem Tagesbudget (`LLM_TAGESBUDGET_AUFRUFE`, Logik in
`plattform.llm`, !36), sonst 503. Der Lauf selbst bricht in `plattform.llm.complete` ebenso fail-closed ab.

Eine Ausnahme vom Lesen ist `POST /faelle/{id}/freigabe` (Freigabe des Berichts mit Namen,
`uc2.verhandlung.freigabe`): nur für fertige Fälle, mit denselben Sperren wie der Start. `KIC_ONLINE_LESEND=1`
ergibt 403 vor dem Body, dazu ein Ratenlimit je IP, eine Body-Grenze und feste Sätze.

Jede Ausgabe läuft durch `uc2.api.belegfilter` (online nur Zitatfelder je Beleg). Eine PG-Verbindung je
Anfrage, beim SSE-Strom für dessen Dauer. Fehler gehen als JSON mit festen, einfachen Sätzen hinaus: keine
Env-Namen, Pfade, SQL oder Exception-Texte (SEC-009); Einzelheiten nur ins Server-Log.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import threading
import time
from collections.abc import AsyncIterator, Callable
from contextlib import closing
from datetime import date, datetime
from typing import Any, Literal

import psycopg
from fastapi import FastAPI, Header, HTTPException, Query, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, StreamingResponse
from plattform.llm import KonfigFehler, budget_status  # type: ignore[import-untyped]  # kein py.typed
from pydantic import BaseModel, ConfigDict, Field, ValidationError
from starlette.concurrency import run_in_threadpool

from uc2 import db
from uc2.api.belegfilter import daten_fuer_ausgabe, ereignis_fuer_ausgabe
from uc2.api.start import Lauf, Startauftrag, Starter, StartFehler, UnterprozessStarter
from uc2.verhandlung.belege import lade_namensliste
from uc2.verhandlung.bericht import bericht
from uc2.verhandlung.cli import MAX_FRAGE, FrageFehler, pruefe_frage
from uc2.verhandlung.fall import FALL_ID, bekannte_faelle
from uc2.verhandlung.freigabe import MAX_BEGRUENDUNG, FreigabeFehler, entscheide
from uc2.verhandlung.speicher import lies_ereignisse, lies_fall, wirksamer_status

PORT = 8102
ECHTE_MODELLE = "UC2_API_ECHTE_MODELLE"
ONLINE = "KIC_ONLINE"
ONLINE_LESEND = "KIC_ONLINE_LESEND"
RATE_S = 60.0
"""Höchstens ein Start je Client-IP in diesem Abstand (Sekunden)."""
NACHLADEN_S = 0.5
WARTEZEICHEN_S = 15.0
"""Kommentarzeile im Strom, wenn so lange nichts kam (hält Proxys offen)."""
ENDSTATUS = ("fertig", "abgebrochen")
LISTE_MAX = 200
FREIGABE_PRO_MINUTE = 10
"""Höchstens so viele Freigabe-Anfragen je Client-IP und Minute (gleitendes Fenster, im Speicher)."""
MAX_BODY = 4 * 1024
"""Größe des Freigabe-Bodys in Bytes; gezählt beim Lesen, auch ohne Content-Length."""

Verbinder = Callable[[], psycopg.Connection[Any]]

# Feste Sätze nach außen (SEC-009); die Web-Oberfläche zeigt sie unverändert an.
NICHT_BEREIT = "Der Dienst ist gerade nicht bereit."
KONTINGENT_AUS = "Das Tageskontingent für Modellaufrufe ist aufgebraucht."
GESPERRT = "Echte Modelle sind hier gesperrt."
OHNE_NAMENSLISTE = "Belege aus dem Index sind ohne Namensliste gesperrt."
ZU_OFT = "Bitte warte eine Minute, bevor du den nächsten Fall startest."
START_GESCHEITERT = "Der Lauf konnte nicht starten."
FREIGABE_GESPERRT = "Freigeben ist in der Online-Demo gesperrt."
FREIGABE_ZU_OFT = "Bitte warte eine Minute, bevor du noch einmal freigibst."
BODY_ZU_GROSS = "Die Anfrage ist zu groß."
FREIGABE_ANFRAGE = "Die Anfrage passt nicht: Name, Entscheidung oder Begründung sind ungültig."
FREIGABE_STATUS = {
    "name": 422,
    "begruendung": 422,
    "entscheidung": 422,
    "kein_fall": 404,
    "nicht_fertig": 409,
    "entschieden": 409,
}

_log = logging.getLogger(__name__)


class FallStart(BaseModel):
    model_config = ConfigDict(extra="forbid")

    fall: str = Field(pattern=FALL_ID.pattern, description="Fall-ID aus uc2/faelle/")
    frage: str | None = Field(default=None, max_length=MAX_FRAGE * 4)
    provider: Literal["mock", "claude", "azure"] = "mock"
    belege: Literal["fixture", "index"] = "fixture"


class FreigabeEingabe(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(max_length=200)
    entscheidung: Literal["freigegeben", "abgelehnt"]
    begruendung: str | None = Field(default=None, max_length=MAX_BEGRUENDUNG * 4)


class _ZuGross(Exception):
    pass


async def _lese_body(request: Request, grenze: int) -> bytes:
    """Body mit harter Grenze; gezählt wird beim Lesen, auch ohne Content-Length (gestreamte Anfragen)."""
    laenge = request.headers.get("content-length", "")
    if laenge.isdigit() and int(laenge) > grenze:
        raise _ZuGross
    stuecke: list[bytes] = []
    gelesen = 0
    async for stueck in request.stream():
        gelesen += len(stueck)
        if gelesen > grenze:
            raise _ZuGross
        stuecke.append(stueck)
    return b"".join(stuecke)


def _standard_verbinde() -> psycopg.Connection[Any]:
    return db.verbinde(autocommit=True)


def budget_sperre() -> str | None:
    """Grund, warum online kein echtes Modell starten darf, sonst `None`.

    Nur mit `KIC_ONLINE=1`: ohne oder mit ungültigem `LLM_TAGESBUDGET_AUFRUFE` (fail-closed wie `complete`),
    oder wenn das Tageskontingent verbraucht ist. Lokal entscheidet `complete` allein.
    """
    if os.environ.get(ONLINE, "").strip() != "1":
        return None
    try:
        status = budget_status()
    except KonfigFehler as fehler:
        _log.warning("Start verweigert, Budget ungültig: %s", fehler)
        return NICHT_BEREIT
    if status["grenze"] is None:
        _log.warning("Start verweigert: %s=1 ohne Tagesbudget", ONLINE)
        return NICHT_BEREIT
    if not status["frei"]:
        return KONTINGENT_AUS
    return None


def _iso(wert: object) -> object:
    return wert.isoformat() if isinstance(wert, date | datetime) else wert


def sse(ereignis: dict[str, Any]) -> str:
    """Ein SSE-Block: `id`, `event`, einzeiliges JSON in `data`."""
    daten = json.dumps(jsonable_encoder(ereignis), ensure_ascii=False, separators=(",", ":"))
    return f"id: {ereignis['seq']}\nevent: {ereignis['art']}\ndata: {daten}\n\n"


def erstelle_app(
    starter: Starter | None = None,
    verbinde: Verbinder | None = None,
    uhr: Callable[[], float] = time.monotonic,
) -> FastAPI:
    """App mit austauschbarem Starter (Tests: Lauf im Prozess), Verbindungsfabrik und Uhr (Ratenlimit)."""
    starte: Starter = starter or UnterprozessStarter()
    verbinde_pg: Verbinder = verbinde or _standard_verbinde
    sperre = threading.Lock()
    aktiv: list[Lauf] = []
    letzte_starts: dict[str, float] = {}
    freigabe_zeiten: dict[str, list[float]] = {}
    freigabe_sperre = threading.Lock()

    app = FastAPI(title="uc2 HealthPolicy Simulator", version="0.1.0")

    @app.exception_handler(psycopg.OperationalError)
    async def _db_weg(_: Request, fehler: Exception) -> JSONResponse:
        _log.error("Datenbank nicht erreichbar: %s", fehler)
        return JSONResponse({"detail": "Die Datenbank ist gerade nicht erreichbar."}, status_code=503)

    @app.exception_handler(RequestValidationError)
    async def _anfrage_ungueltig(request: Request, fehler: RequestValidationError) -> JSONResponse:
        # Die Standardantwort gibt die Eingabe zurück; nach außen gehen nur feste Sätze (SEC-009).
        _log.info("Anfrage ungültig: %s", request.url.path)
        return JSONResponse({"detail": "Die Anfrage passt nicht."}, status_code=422)

    @app.exception_handler(Exception)
    async def _intern(_: Request, fehler: Exception) -> JSONResponse:
        _log.error("Interner Fehler: %s: %s", type(fehler).__name__, fehler)
        return JSONResponse({"detail": "Es ist ein interner Fehler aufgetreten."}, status_code=500)

    def _zu_oft(ip: str) -> bool:
        """Ratenlimit je IP; nur unter `sperre` aufrufen. Räumt abgelaufene Einträge weg."""
        jetzt = uhr()
        for alt in [k for k, t in letzte_starts.items() if jetzt - t >= RATE_S]:
            del letzte_starts[alt]
        return ip in letzte_starts

    @app.post("/faelle", status_code=202)
    def starte_fall(eingabe: FallStart, request: Request) -> dict[str, Any]:
        if eingabe.fall not in bekannte_faelle():
            raise HTTPException(404, f"unbekannter Fall {eingabe.fall!r}")
        if eingabe.provider != "mock":
            if os.environ.get(ECHTE_MODELLE) != "1":
                raise HTTPException(403, GESPERRT)
            grund = budget_sperre()
            if grund is not None:
                raise HTTPException(503, grund)
        if eingabe.belege == "index" and eingabe.provider != "mock" and lade_namensliste() is None:
            raise HTTPException(422, OHNE_NAMENSLISTE)
        try:
            frage = None if eingabe.frage is None else pruefe_frage(eingabe.frage)
        except FrageFehler as fehler:
            raise HTTPException(422, str(fehler)) from fehler
        ip = request.client.host if request.client else "unbekannt"
        if not sperre.acquire(blocking=False):
            raise HTTPException(409, "Es startet gerade ein Fall")
        try:
            if aktiv and aktiv[-1].laeuft():
                raise HTTPException(409, f"Fall {aktiv[-1].fall_id} läuft noch")
            if _zu_oft(ip):
                raise HTTPException(429, ZU_OFT)
            letzte_starts[ip] = uhr()
            try:
                lauf = starte(Startauftrag(eingabe.fall, eingabe.provider, eingabe.belege, frage))
            except StartFehler as fehler:
                _log.error("Start gescheitert: %s", fehler)
                raise HTTPException(500, START_GESCHEITERT) from fehler
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

    def _freigabe_zu_oft(ip: str) -> bool:
        """Zählt die Anfrage; `True`, wenn das Fenster schon voll ist. Räumt abgelaufene Einträge weg."""
        with freigabe_sperre:
            jetzt = uhr()
            veraltet = [
                k for k, zeiten in freigabe_zeiten.items() if not zeiten or jetzt - zeiten[-1] >= RATE_S
            ]
            for alt in veraltet:
                del freigabe_zeiten[alt]
            zeiten = [t for t in freigabe_zeiten.get(ip, []) if jetzt - t < RATE_S]
            if len(zeiten) >= FREIGABE_PRO_MINUTE:
                freigabe_zeiten[ip] = zeiten
                return True
            freigabe_zeiten[ip] = [*zeiten, jetzt]
            return False

    def _entscheide(fall_id: int, eingabe: FreigabeEingabe) -> datetime:
        with closing(verbinde_pg()) as v:
            return entscheide(v, fall_id, eingabe.name, eingabe.entscheidung, eingabe.begruendung)

    @app.post("/faelle/{fall_id}/freigabe")
    async def freigabe(fall_id: int, request: Request) -> dict[str, Any]:
        if os.environ.get(ONLINE_LESEND, "").strip() == "1":
            raise HTTPException(403, FREIGABE_GESPERRT)
        ip = request.client.host if request.client else "unbekannt"
        if _freigabe_zu_oft(ip):
            raise HTTPException(429, FREIGABE_ZU_OFT)
        try:
            roh = await _lese_body(request, MAX_BODY)
        except _ZuGross as fehler:
            raise HTTPException(413, BODY_ZU_GROSS) from fehler
        try:
            eingabe = FreigabeEingabe.model_validate_json(roh)
        except ValidationError as fehler:
            raise HTTPException(422, FREIGABE_ANFRAGE) from fehler
        try:
            zeitpunkt = await run_in_threadpool(_entscheide, fall_id, eingabe)
        except FreigabeFehler as fehler:
            raise HTTPException(FREIGABE_STATUS.get(fehler.art, 422), str(fehler)) from fehler
        return {"zeitpunkt": zeitpunkt.isoformat()}

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
