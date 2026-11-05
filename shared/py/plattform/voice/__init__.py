"""Voice (Vertrag V, #61): Vapi-Custom-LLM-Router, Tunnel-Middleware, Assistant als Code.

Konzept nach einem vorab entstandenen Projekt des Teams, Code hier neu. Einbinden in eine UC-FastAPI::

    app.include_router(erstelle_router(antwort, uc="uc3"))
    app.add_middleware(TunnelFilter)

Text-Fallback ohne Vapi: ``text_antwort(antwort, frage, uc)``. Nicht aus ``plattform/__init__.py`` importiert
(R2: der UC3-Lauf lädt nichts Modellnahes). Datenfluss: ``docs/voice.md``.
"""

from .kern import (
    Antwortfunktion,
    Fehlversuche,
    Sitzung,
    VoiceAntwort,
    erstelle_router,
    gesprochener_text,
    sitzungs_belege,
    text_antwort,
    voice_protokoll_datei,
)
from .tunnel import TunnelFilter

__all__ = [
    "Antwortfunktion",
    "Fehlversuche",
    "Sitzung",
    "TunnelFilter",
    "VoiceAntwort",
    "erstelle_router",
    "gesprochener_text",
    "sitzungs_belege",
    "text_antwort",
    "voice_protokoll_datei",
]
