"""Vapi-Custom-LLM-Router (Vertrag V, #61): ``/chat/completions`` und ``/vapi/webhook`` für eine UC-FastAPI.

Vapi schickt das Transkript OpenAI-kompatibel an ``POST /chat/completions`` und spricht die Antwort. Die UC
liefert nur die Funktion ``antwort(nachrichten, sitzung) -> VoiceAntwort``; der Router prüft den Schlüssel,
hängt die Belege gesprochen an („Beleg: roh.lieferung 2025-03.“) und legt sie je ``call_id`` für die UI ab.

Geheimnisse werden in konstanter Zeit verglichen (sha256 beider Seiten, ``hmac.compare_digest``). Fehlt die
Variable, antwortet der Router 503 (fail-closed). Ins Protokoll ``voice.jsonl`` geht nur das Ende eines
Anrufs: Hash der call_id, Dauer, Endgrund, nie Transkript oder Antworttext.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import threading
import time
import uuid
from collections import OrderedDict, deque
from collections.abc import Callable, Iterator, Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, ConfigDict
from starlette.concurrency import run_in_threadpool

from plattform.antwortform import Beleg, Uc
from plattform.llm.basis import ROLLEN, Nachricht
from plattform.protokoll import protokoll_datei

#: Grenze des prozesslokalen Sitzungsspeichers (älteste Sitzung fällt heraus).
MAX_SITZUNGEN = 200
#: Höchstens so viele Belege je Sitzung (die ältesten fallen heraus).
MAX_BELEGE_JE_SITZUNG = 50
#: Fehlversuche je Client-IP im Fenster, ab dann 429 bis das Fenster abläuft.
FEHLVERSUCHE_GRENZE = 10
FEHLVERSUCHE_FENSTER_S = 60.0

_MODELLNAME = "plattform-voice"
_ENDGRUND_ZEICHEN = re.compile(r"[^a-z0-9._-]")


class VoiceAntwort(BaseModel):
    """Antwort der UC-Funktion: Text ohne Beleg und die Belege (Herkunft aus ``plattform.antwortform``)."""

    model_config = ConfigDict(extra="forbid")

    text: str
    belege: list[Beleg] = []


@dataclass(frozen=True, slots=True)
class Sitzung:
    """Ein Vapi-Anruf: ``call_id`` = ``call.id`` aus dem Body, ``gestartet`` = erste Anfrage des Anrufs."""

    call_id: str
    uc: Uc
    gestartet: datetime


#: Signatur der UC-Funktion; ein Mapping derselben Form wird streng als ``VoiceAntwort`` geprüft.
Antwortfunktion = Callable[[list[Nachricht], Sitzung], VoiceAntwort | Mapping[str, Any]]


# --- Sitzungsspeicher -------------------------------------------------------------------------------


@dataclass
class _Eintrag:
    sitzung: Sitzung
    belege: list[Beleg] = field(default_factory=list)


_SITZUNGEN: OrderedDict[str, _Eintrag] = OrderedDict()
_SITZUNGSSPERRE = threading.Lock()


def _sitzung_holen(call_id: str, uc: Uc) -> Sitzung:
    with _SITZUNGSSPERRE:
        eintrag = _SITZUNGEN.get(call_id)
        if eintrag is None:
            eintrag = _Eintrag(Sitzung(call_id=call_id, uc=uc, gestartet=datetime.now(UTC)))
            _SITZUNGEN[call_id] = eintrag
        _SITZUNGEN.move_to_end(call_id)
        while len(_SITZUNGEN) > MAX_SITZUNGEN:
            _SITZUNGEN.popitem(last=False)
        return eintrag.sitzung


def _belege_ablegen(call_id: str, belege: list[Beleg]) -> None:
    with _SITZUNGSSPERRE:
        eintrag = _SITZUNGEN.get(call_id)
        if eintrag is None:  # inzwischen verdrängt
            return
        for beleg in belege:
            if beleg not in eintrag.belege:
                eintrag.belege.append(beleg.model_copy(deep=True))
        del eintrag.belege[:-MAX_BELEGE_JE_SITZUNG]


def sitzungs_belege(call_id: str) -> list[Beleg]:
    """Belege eines Anrufs in der Reihenfolge des ersten Auftretens (ohne Doppelte); unbekannt → leer."""
    with _SITZUNGSSPERRE:
        eintrag = _SITZUNGEN.get(call_id)
        return [beleg.model_copy(deep=True) for beleg in eintrag.belege] if eintrag else []


# --- Antwort ----------------------------------------------------------------------------------------


def _als_voice_antwort(roh: object) -> VoiceAntwort:
    """Nimmt eine ``VoiceAntwort`` oder ein Mapping derselben Form an; Belege werden streng geprüft."""
    return VoiceAntwort.model_validate(roh)


def gesprochener_text(antwort: VoiceAntwort) -> str:
    """Text samt gesprochenen Belegen, z. B. „… 387.180. Beleg: stat.beschaeftigte 2025-03.“ (ohne SQL)."""
    saetze: list[str] = []
    for beleg in antwort.belege:
        zeitraum = beleg.lieferung or beleg.monat
        satz = f"Beleg: {beleg.quelle} {zeitraum}." if zeitraum else f"Beleg: {beleg.quelle}."
        if satz not in saetze:
            saetze.append(satz)
    return " ".join([antwort.text.rstrip(), *saetze]) if saetze else antwort.text


def text_antwort(antwort: Antwortfunktion, frage: str, uc: Uc) -> VoiceAntwort:
    """Text-Fallback für UC-Chatfelder: dieselbe ``antwort``-Funktion ohne Vapi, ohne gesprochenen Beleg."""
    sitzung = Sitzung(call_id=f"text-{uuid.uuid4().hex}", uc=uc, gestartet=datetime.now(UTC))
    return _als_voice_antwort(antwort([{"role": "user", "content": frage}], sitzung))


def _nachrichten(roh: object) -> list[Nachricht]:
    """OpenAI-Nachrichten → ``Nachricht``; Teile-Listen werden Text, Tool- und Leer-Nachrichten fallen weg."""
    nachrichten: list[Nachricht] = []
    if not isinstance(roh, list):
        return nachrichten
    for eintrag in roh:
        if not isinstance(eintrag, dict) or eintrag.get("role") not in ROLLEN:
            continue
        inhalt = eintrag.get("content")
        if isinstance(inhalt, list):
            inhalt = "".join(
                str(teil.get("text", ""))
                for teil in inhalt
                if isinstance(teil, dict) and teil.get("type") == "text"
            )
        if isinstance(inhalt, str) and inhalt:
            nachrichten.append({"role": str(eintrag["role"]), "content": inhalt})
    return nachrichten


def _stuecke(text: str) -> list[str]:
    """Teilt nach jedem Leerraum; zusammengesetzt ergibt sich genau ``text``."""
    return [stueck for stueck in re.split(r"(?<=\s)", text) if stueck]


def _sse(daten: Mapping[str, Any] | str) -> str:
    inhalt = daten if isinstance(daten, str) else json.dumps(daten, ensure_ascii=False)
    return f"data: {inhalt}\n\n"


def _sse_strom(text: str, kennung: str, erstellt: int, modell: str) -> Iterator[str]:
    def chunk(delta: dict[str, str], ende: str | None) -> dict[str, Any]:
        return {
            "id": kennung,
            "object": "chat.completion.chunk",
            "created": erstellt,
            "model": modell,
            "choices": [{"index": 0, "delta": delta, "finish_reason": ende}],
        }

    for nummer, stueck in enumerate(_stuecke(text)):
        delta = {"role": "assistant", "content": stueck} if nummer == 0 else {"content": stueck}
        yield _sse(chunk(delta, None))
    yield _sse(chunk({}, "stop"))
    yield _sse("[DONE]")


def _vollstaendig(text: str, kennung: str, erstellt: int, modell: str) -> dict[str, Any]:
    return {
        "id": kennung,
        "object": "chat.completion",
        "created": erstellt,
        "model": modell,
        "choices": [{"index": 0, "message": {"role": "assistant", "content": text}, "finish_reason": "stop"}],
    }


# --- Schutz -----------------------------------------------------------------------------------------


def _gleich(erhalten: str | None, erwartet: str) -> bool:
    """Vergleich in konstanter Zeit über die sha256 beider Seiten (Länge verrät nichts)."""
    links = hashlib.sha256((erhalten or "").encode("utf-8")).digest()
    rechts = hashlib.sha256(erwartet.encode("utf-8")).digest()
    return hmac.compare_digest(links, rechts) and erhalten is not None


def _bearer(request: Request) -> str | None:
    kopf = request.headers.get("authorization", "")
    schema, _, wert = kopf.partition(" ")
    return wert.strip() if schema.lower() == "bearer" and wert.strip() else None


def client_ip(request: Request) -> str:
    """``CF-Connecting-IP`` (über den Tunnel), sonst die Gegenstelle der Verbindung."""
    return request.headers.get("cf-connecting-ip") or (request.client.host if request.client else "unbekannt")


class Fehlversuche:
    """Ratenlimit nur auf Fehlversuche, je Client-IP im Speicher (gleitendes Fenster)."""

    def __init__(
        self,
        grenze: int = FEHLVERSUCHE_GRENZE,
        fenster_s: float = FEHLVERSUCHE_FENSTER_S,
        uhr: Callable[[], float] = time.monotonic,
        max_ips: int = 1024,
    ) -> None:
        self._grenze = grenze
        self._fenster_s = fenster_s
        self._uhr = uhr
        self._max_ips = max_ips
        self._zeiten: OrderedDict[str, deque[float]] = OrderedDict()
        self._sperre = threading.Lock()

    def _aktuell(self, ip: str, jetzt: float) -> deque[float]:
        zeiten = self._zeiten.get(ip, deque())
        while zeiten and jetzt - zeiten[0] > self._fenster_s:
            zeiten.popleft()
        return zeiten

    def gesperrt(self, ip: str) -> bool:
        with self._sperre:
            return len(self._aktuell(ip, self._uhr())) >= self._grenze

    def merken(self, ip: str) -> None:
        with self._sperre:
            jetzt = self._uhr()
            zeiten = self._aktuell(ip, jetzt)
            zeiten.append(jetzt)
            self._zeiten[ip] = zeiten
            self._zeiten.move_to_end(ip)
            while len(self._zeiten) > self._max_ips:
                self._zeiten.popitem(last=False)


def _pruefe_geheimnis(
    request: Request, variable: str, erhalten: str | None, fehlversuche: Fehlversuche
) -> None:
    """503 ohne Variable, 429 nach zu vielen Fehlversuchen, 401 bei falschem oder fehlendem Geheimnis."""
    erwartet = os.environ.get(variable)
    if not erwartet:
        raise HTTPException(status_code=503, detail=f"{variable} ist nicht gesetzt")
    ip = client_ip(request)
    if fehlversuche.gesperrt(ip):
        raise HTTPException(status_code=429, detail="zu viele Fehlversuche")
    if not _gleich(erhalten, erwartet):
        fehlversuche.merken(ip)
        raise HTTPException(status_code=401, detail="nicht berechtigt")


# --- Protokoll --------------------------------------------------------------------------------------


_PROTOKOLLSPERRE = threading.Lock()


def voice_protokoll_datei() -> Path:
    """``PLATTFORM_VOICE_PROTOKOLL`` oder ``voice.jsonl`` neben dem Modellprotokoll (nur Modellaufrufe)."""
    explizit = os.environ.get("PLATTFORM_VOICE_PROTOKOLL")
    return Path(explizit) if explizit else protokoll_datei().with_name("voice.jsonl")


def _dauer_s(nachricht: Mapping[str, Any]) -> float | None:
    dauer = nachricht.get("durationSeconds")
    if isinstance(dauer, int | float) and not isinstance(dauer, bool):
        return round(float(dauer), 1)
    try:
        start = datetime.fromisoformat(str(nachricht["startedAt"]))
        ende = datetime.fromisoformat(str(nachricht["endedAt"]))
    except (KeyError, ValueError):
        return None
    return round((ende - start).total_seconds(), 1)


def _anrufende_schreiben(uc: Uc, nachricht: Mapping[str, Any]) -> None:
    anruf = nachricht.get("call")
    call_id = str(anruf.get("id", "")) if isinstance(anruf, Mapping) else ""
    endgrund = _ENDGRUND_ZEICHEN.sub("", str(nachricht.get("endedReason", "")).lower())[:80] or None
    zeile = {
        "zeit": datetime.now(UTC).isoformat(timespec="milliseconds"),
        "uc": uc,
        "typ": "end-of-call-report",
        "call_id_hash": hashlib.sha256(call_id.encode("utf-8")).hexdigest() if call_id else None,
        "dauer_s": _dauer_s(nachricht),
        "endgrund": endgrund,
    }
    ziel = voice_protokoll_datei()
    ziel.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(zeile, ensure_ascii=False, sort_keys=True) + "\n"
    with _PROTOKOLLSPERRE, ziel.open("a", encoding="utf-8") as datei:
        datei.write(text)


# --- Router -----------------------------------------------------------------------------------------


def erstelle_router(
    antwort: Antwortfunktion, *, uc: Uc, fehlversuche: Fehlversuche | None = None
) -> APIRouter:
    """FastAPI-Router mit ``POST /chat/completions`` (+ ``/{token}``) und ``POST /vapi/webhook``.

    ``antwort`` ist eine normale (synchrone) Funktion und läuft im Threadpool; wirft sie, antwortet der Router
    500, bevor ein Stream beginnt. ``fehlversuche`` gilt für beide Endpunkte (Standard: eigener Zähler).
    """
    zaehler = fehlversuche or Fehlversuche()
    router = APIRouter()

    async def _beantworten(request: Request) -> StreamingResponse | JSONResponse:
        try:
            koerper = await request.json()
        except ValueError as fehler:
            raise HTTPException(status_code=400, detail="Body ist kein JSON") from fehler
        if not isinstance(koerper, dict):
            raise HTTPException(status_code=400, detail="Body ist kein Objekt")
        anruf = koerper.get("call")
        call_id = anruf.get("id") if isinstance(anruf, dict) else None
        sitzung = _sitzung_holen(str(call_id) if call_id else f"ohne-call-{uuid.uuid4().hex}", uc)

        roh = await run_in_threadpool(antwort, _nachrichten(koerper.get("messages")), sitzung)
        ergebnis = _als_voice_antwort(roh)
        _belege_ablegen(sitzung.call_id, ergebnis.belege)

        text = gesprochener_text(ergebnis)
        kennung = f"chatcmpl-{uuid.uuid4().hex}"
        erstellt = int(time.time())
        modell = str(koerper.get("model") or _MODELLNAME)
        if koerper.get("stream") is True:
            return StreamingResponse(
                _sse_strom(text, kennung, erstellt, modell),
                media_type="text/event-stream",
                headers={"Cache-Control": "no-cache"},
            )
        return JSONResponse(_vollstaendig(text, kennung, erstellt, modell))

    @router.post("/chat/completions", response_model=None)
    async def chat_completions(request: Request) -> StreamingResponse | JSONResponse:
        _pruefe_geheimnis(request, "VAPI_CUSTOM_LLM_KEY", _bearer(request), zaehler)
        return await _beantworten(request)

    @router.post("/chat/completions/{token}", response_model=None)
    async def chat_completions_token(token: str, request: Request) -> StreamingResponse | JSONResponse:
        _pruefe_geheimnis(request, "VAPI_CUSTOM_LLM_KEY", token, zaehler)
        return await _beantworten(request)

    @router.post("/vapi/webhook")
    async def vapi_webhook(request: Request) -> dict[str, str]:
        # Geheimnis zuerst: ohne gültiges x-vapi-secret wird der Body nie gelesen.
        _pruefe_geheimnis(request, "VAPI_WEBHOOK_SECRET", request.headers.get("x-vapi-secret"), zaehler)
        try:
            koerper = await request.json()
        except ValueError as fehler:
            raise HTTPException(status_code=400, detail="Body ist kein JSON") from fehler
        nachricht = koerper.get("message") if isinstance(koerper, dict) else None
        if not isinstance(nachricht, dict) or nachricht.get("type") != "end-of-call-report":
            return {"status": "ignored"}
        _anrufende_schreiben(uc, nachricht)
        return {"status": "ok"}

    return router
