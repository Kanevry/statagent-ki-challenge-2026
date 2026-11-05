"""FastAPI-App für ``python -m plattform.voice serve``: Voice-Router plus Tunnel-Filter, sonst nichts."""

from __future__ import annotations

from fastapi import FastAPI

from .kern import erstelle_router
from .tunnel import TunnelFilter


def erstelle_app(uc: str = "uc4", *, mock: bool = False) -> FastAPI:
    """App mit ``/chat/completions`` und ``/vapi/webhook``; bisher nur ``uc4`` (Kette über den Router)."""
    if uc != "uc4":
        raise ValueError(f"serve kennt nur uc4, nicht {uc!r}; UC1 bis UC3 binden erstelle_router selbst ein")
    from .uc4 import uc4_antwort  # erst hier: lädt plattform.router

    app = FastAPI(title="plattform.voice", docs_url=None, redoc_url=None, openapi_url=None)
    app.include_router(erstelle_router(uc4_antwort(mock=mock), uc="uc4"))
    app.add_middleware(TunnelFilter)
    return app
