"""Vapi-Custom-LLM-Router (Vertrag V, #61): ``/chat/completions`` und ``/vapi/webhook`` für eine UC-FastAPI.

Vapi schickt das Transkript OpenAI-kompatibel an ``POST /chat/completions`` und spricht die Antwort. Die UC
liefert nur die Funktion ``antwort(nachrichten, sitzung) -> VoiceAntwort``; der Router prüft den Schlüssel,
hängt die Belege gesprochen an („Beleg: roh.lieferung 2025-03.“) und legt sie je ``call_id`` für die UI ab.

Geheimnisse werden in konstanter Zeit verglichen (sha256 beider Seiten, ``hmac.compare_digest``). Fehlt die
Variable, antwortet der Router 503 (fail-closed). Bodies sind auf 256 KiB begrenzt (413), ``antwort`` auf
``VOICE_ANTWORT_TIMEOUT_S`` (504), gültige Aufrufe je IP auf ``VOICE_RATENLIMIT_PRO_MINUTE`` (429). Ins
Protokoll ``voice.jsonl`` geht je Anruf genau eine Zeile: Hash der call_id, Dauer, Endgrund aus einer
Allowlist, nie Transkript oder Antworttext.

Lädt ``plattform.llm`` nicht (R2); ``Nachricht`` kommt nur für die Typprüfung von dort.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
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
from typing import TYPE_CHECKING, Any, Literal, get_args

import anyio
import anyio.to_thread
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, ConfigDict

from plattform.antwortform import Beleg, Uc
from plattform.protokoll import protokoll_datei

if TYPE_CHECKING:
    from plattform.llm.basis import Nachricht

_LOG = logging.getLogger(__name__)

#: Grenze des prozesslokalen Sitzungsspeichers (älteste Sitzung fällt heraus).
MAX_SITZUNGEN = 200
#: Höchstens so viele Belege je Sitzung (die ältesten fallen heraus).
MAX_BELEGE_JE_SITZUNG = 50
#: Fehlversuche je Client-IP im Fenster, ab dann 429 bis das Fenster abläuft.
FEHLVERSUCHE_GRENZE = 10
FEHLVERSUCHE_FENSTER_S = 60.0
#: Standard für ``VOICE_RATENLIMIT_PRO_MINUTE`` (gültige ``/chat/completions`` je Client-IP).
RATENLIMIT_PRO_MINUTE = 30
#: Standard für ``VOICE_ANTWORT_TIMEOUT_S`` (Deadline der ``antwort``-Funktion).
ANTWORT_TIMEOUT_S = 20.0
#: Größte Body-Länge für alle Endpunkte.
MAX_BODY_BYTES = 256 * 1024
#: So viele Anrufenden merkt sich der Webhook für die Idempotenz.
MAX_GEMELDETE_ANRUFE = 1000

_ROLLEN = frozenset({"system", "user", "assistant"})
_MODELLNAME = "plattform-voice"
_NICHT_EINGERICHTET = "Voice ist nicht eingerichtet."
_BUDGET_MELDUNG = "Das Tagesbudget für Modellaufrufe ist erschöpft. Bitte morgen wieder oder per Text fragen."

#: Bekannte Vapi-Endgründe; ein Eintrag mit ``-`` am Ende gilt als Präfix. Alles andere wird ``sonstiges``.
ENDGRUENDE: tuple[str, ...] = (
    "customer-ended-call",
    "customer-busy",
    "customer-did-not-answer",
    "customer-did-not-give-microphone-permission",
    "assistant-ended-call",
    "assistant-said-end-call-phrase",
    "assistant-forwarded-call",
    "assistant-join-timed-out",
    "assistant-not-found",
    "assistant-error",
    "assistant-request-",
    "silence-timed-out",
    "max-duration-exceeded",
    "exceeded-max-duration",
    "manually-canceled",
    "voicemail",
    "worker-shutdown",
    "unknown-error",
    "pipeline-error-",
    "call-start-error-",
    "phone-call-provider-",
    "call.",
)
_ENDGRUND_ZEICHEN = re.compile(r"[a-z0-9.-]{1,80}")
_LANGE_ZIFFERN = re.compile(r"\d{4,}")

#: ``uc4`` = Kette uc3 → uc2 → uc1 (``plattform.router``); ``unbekannt``: weder Router noch Anfrage.
VoiceUc = Uc | Literal["uc4", "unbekannt"]


class VoiceAntwort(BaseModel):
    """Antwort der UC-Funktion: Text ohne Beleg und die Belege (Herkunft aus ``plattform.antwortform``)."""

    model_config = ConfigDict(extra="forbid")

    text: str
    belege: list[Beleg] = []


@dataclass(frozen=True, slots=True)
class Sitzung:
    """Ein Vapi-Anruf: ``call_id`` = ``call.id`` aus dem Body, ``gestartet`` = erste Anfrage des Anrufs.

    ``uc`` kommt aus ``erstelle_router(uc=…)``, sonst aus ``metadata.uc`` der Anfrage, sonst ``unbekannt``.
    """

    call_id: str
    uc: VoiceUc
    gestartet: datetime


#: Signatur der UC-Funktion; ein Mapping derselben Form wird streng als ``VoiceAntwort`` geprüft.
type Antwortfunktion = Callable[[list[Nachricht], Sitzung], VoiceAntwort | Mapping[str, Any]]


# --- Sitzungsspeicher -------------------------------------------------------------------------------


@dataclass
class _Eintrag:
    sitzung: Sitzung
    belege: list[Beleg] = field(default_factory=list)


_SITZUNGEN: OrderedDict[str, _Eintrag] = OrderedDict()
_SITZUNGSSPERRE = threading.Lock()


def _sitzung_holen(call_id: str, uc: VoiceUc) -> Sitzung:
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
        if not isinstance(eintrag, dict) or eintrag.get("role") not in _ROLLEN:
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


def _ist_budget_erschoepft(fehler: BaseException) -> bool:
    # Per Klassenname, damit plattform.llm hier nicht geladen wird (R2).
    return any(klasse.__name__ == "BudgetErschoepft" for klasse in type(fehler).__mro__)


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


def _zahl_aus_umgebung(name: str, standard: float) -> float:
    try:
        wert = float(os.environ.get(name) or standard)
    except ValueError:
        return standard
    return wert if wert > 0 else standard


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


class Ratenlimit:
    """Gleitendes Fenster je Client-IP im Speicher: ``gesperrt`` ab ``grenze`` Einträgen im Fenster."""

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


#: Ratenlimit nur auf Fehlversuche (falscher oder fehlender Schlüssel).
Fehlversuche = Ratenlimit


def _pruefe_geheimnis(
    request: Request, variable: str, erhalten: str | None, fehlversuche: Ratenlimit
) -> None:
    """503 ohne Variable, 429 nach zu vielen Fehlversuchen, 401 bei falschem oder fehlendem Geheimnis."""
    erwartet = os.environ.get(variable)
    if not erwartet:
        _LOG.warning("Voice: %s ist nicht gesetzt", variable)  # Name nur ins Log, nicht in die Antwort
        raise HTTPException(status_code=503, detail=_NICHT_EINGERICHTET)
    ip = client_ip(request)
    if fehlversuche.gesperrt(ip):
        raise HTTPException(status_code=429, detail="zu viele Fehlversuche")
    if not _gleich(erhalten, erwartet):
        fehlversuche.merken(ip)
        raise HTTPException(status_code=401, detail="nicht berechtigt")


async def _lies_json(request: Request) -> object:
    """Liest den Body mit Grenze ``MAX_BODY_BYTES`` (413 per Content-Length und beim Lesen), 400 ohne JSON."""
    laenge = request.headers.get("content-length")
    if laenge is not None and laenge.isdigit() and int(laenge) > MAX_BODY_BYTES:
        raise HTTPException(status_code=413, detail="Body zu groß")
    puffer = bytearray()
    async for stueck in request.stream():
        puffer.extend(stueck)
        if len(puffer) > MAX_BODY_BYTES:
            raise HTTPException(status_code=413, detail="Body zu groß")
    try:
        return json.loads(puffer)
    except ValueError as fehler:
        raise HTTPException(status_code=400, detail="Body ist kein JSON") from fehler


# --- Protokoll --------------------------------------------------------------------------------------


_PROTOKOLLSPERRE = threading.Lock()
_GEMELDET: OrderedDict[str, None] = OrderedDict()


def voice_protokoll_datei() -> Path:
    """``PLATTFORM_VOICE_PROTOKOLL`` oder ``voice.jsonl`` neben dem Modellprotokoll (nur Modellaufrufe)."""
    explizit = os.environ.get("PLATTFORM_VOICE_PROTOKOLL")
    return Path(explizit) if explizit else protokoll_datei().with_name("voice.jsonl")


def endgrund(roh: object) -> str | None:
    """Endgrund aus der Allowlist ``ENDGRUENDE``; Unbekanntes oder lange Ziffernfolgen → ``sonstiges``."""
    if roh is None or roh == "":
        return None
    wert = str(roh).strip().lower()
    if not _ENDGRUND_ZEICHEN.fullmatch(wert) or _LANGE_ZIFFERN.search(wert):
        return "sonstiges"
    for eintrag in ENDGRUENDE:
        if wert == eintrag or (eintrag.endswith(("-", ".")) and wert.startswith(eintrag)):
            return wert
    return "sonstiges"


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


def _schon_im_protokoll(ziel: Path, call_id_hash: str) -> bool:
    """Prüft die letzten 64 KiB der Datei (Neustart des Prozesses verliert die Menge im Speicher)."""
    try:
        with ziel.open("rb") as datei:
            datei.seek(max(0, ziel.stat().st_size - 64 * 1024))
            return call_id_hash.encode("ascii") in datei.read()
    except FileNotFoundError:
        return False


def _anrufende_schreiben(uc: VoiceUc, nachricht: Mapping[str, Any]) -> bool:
    """Schreibt die Zeile; ``False``, wenn dieser Anruf schon gemeldet war (idempotent über die call_id)."""
    anruf = nachricht.get("call")
    call_id = str(anruf.get("id", "")) if isinstance(anruf, Mapping) else ""
    call_id_hash = hashlib.sha256(call_id.encode("utf-8")).hexdigest() if call_id else None
    zeile = {
        "zeit": datetime.now(UTC).isoformat(timespec="milliseconds"),
        "uc": uc,
        "typ": "end-of-call-report",
        "call_id_hash": call_id_hash,
        "dauer_s": _dauer_s(nachricht),
        "endgrund": endgrund(nachricht.get("endedReason")),
    }
    ziel = voice_protokoll_datei()
    text = json.dumps(zeile, ensure_ascii=False, sort_keys=True) + "\n"
    with _PROTOKOLLSPERRE:
        if call_id_hash is not None:
            if call_id_hash in _GEMELDET or _schon_im_protokoll(ziel, call_id_hash):
                return False
            _GEMELDET[call_id_hash] = None
            while len(_GEMELDET) > MAX_GEMELDETE_ANRUFE:
                _GEMELDET.popitem(last=False)
        ziel.parent.mkdir(parents=True, exist_ok=True)
        with ziel.open("a", encoding="utf-8") as datei:
            datei.write(text)
    return True


# --- Router -----------------------------------------------------------------------------------------


def _uc_aus_anfrage(koerper: Mapping[str, Any]) -> VoiceUc:
    metadaten = koerper.get("metadata")
    wert = metadaten.get("uc") if isinstance(metadaten, Mapping) else None
    for bekannt in get_args(Uc):
        if wert == bekannt:
            uc: Uc = bekannt
            return uc
    return "unbekannt"


def erstelle_router(
    antwort: Antwortfunktion,
    *,
    uc: VoiceUc | None = None,
    fehlversuche: Ratenlimit | None = None,
    aufrufe: Ratenlimit | None = None,
) -> APIRouter:
    """FastAPI-Router mit ``POST /chat/completions`` und ``POST /vapi/webhook``.

    ``uc`` fehlt: aus ``metadata.uc`` der Anfrage, sonst ``unbekannt``. ``antwort`` ist eine normale
    (synchrone) Funktion und läuft im Threadpool mit Deadline ``VOICE_ANTWORT_TIMEOUT_S`` (504; der Thread
    selbst läuft zu Ende). ``BudgetErschoepft`` aus ``plattform.llm`` wird 429, andere Fehler 500, beides
    bevor ein Stream beginnt. ``fehlversuche`` zählt falsche Schlüssel beider Endpunkte, ``aufrufe`` gültige
    ``/chat/completions`` (Standard ``VOICE_RATENLIMIT_PRO_MINUTE`` je Minute und IP).
    """
    zaehler = fehlversuche or Ratenlimit()
    gueltige = aufrufe or Ratenlimit(
        grenze=int(_zahl_aus_umgebung("VOICE_RATENLIMIT_PRO_MINUTE", RATENLIMIT_PRO_MINUTE)), fenster_s=60.0
    )
    router = APIRouter()

    async def _beantworten(request: Request) -> StreamingResponse | JSONResponse:
        koerper = await _lies_json(request)
        if not isinstance(koerper, dict):
            raise HTTPException(status_code=400, detail="Body ist kein Objekt")
        anruf = koerper.get("call")
        call_id = anruf.get("id") if isinstance(anruf, dict) else None
        sitzung = _sitzung_holen(
            str(call_id) if call_id else f"ohne-call-{uuid.uuid4().hex}", uc or _uc_aus_anfrage(koerper)
        )

        frist = _zahl_aus_umgebung("VOICE_ANTWORT_TIMEOUT_S", ANTWORT_TIMEOUT_S)
        try:
            with anyio.fail_after(frist):
                # abandon_on_cancel: nach der Frist wartet der Router nicht auf den Thread (der läuft aus).
                roh = await anyio.to_thread.run_sync(
                    antwort, _nachrichten(koerper.get("messages")), sitzung, abandon_on_cancel=True
                )
        except TimeoutError as fehler:
            raise HTTPException(status_code=504, detail="Antwort dauerte zu lange") from fehler
        except Exception as fehler:
            if _ist_budget_erschoepft(fehler):
                raise HTTPException(status_code=429, detail=_BUDGET_MELDUNG) from fehler
            raise
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
        ip = client_ip(request)
        if gueltige.gesperrt(ip):
            raise HTTPException(status_code=429, detail="zu viele Anfragen")
        gueltige.merken(ip)
        return await _beantworten(request)

    @router.post("/vapi/webhook")
    async def vapi_webhook(request: Request) -> dict[str, str]:
        # Geheimnis zuerst: ohne gültiges x-vapi-secret wird der Body nie gelesen.
        _pruefe_geheimnis(request, "VAPI_WEBHOOK_SECRET", request.headers.get("x-vapi-secret"), zaehler)
        koerper = await _lies_json(request)
        nachricht = koerper.get("message") if isinstance(koerper, dict) else None
        if not isinstance(nachricht, dict) or nachricht.get("type") != "end-of-call-report":
            return {"status": "ignored"}
        geschrieben = _anrufende_schreiben(uc or _uc_aus_anfrage(nachricht), nachricht)
        return {"status": "ok" if geschrieben else "doppelt"}

    return router
