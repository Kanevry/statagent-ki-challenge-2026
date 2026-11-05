"""Tunnel-Middleware (Vertrag V): über die Tunnel-Domain nur ``/chat/completions*`` und ``/vapi/webhook``.

Eine Anfrage gilt als Tunnel-Anfrage, wenn ihr Host gleich dem Host aus ``PUBLIC_URL`` ist oder der Header
``CF-Connecting-IP`` vorhanden ist (cloudflared setzt ihn). Alles andere bekommt dort 404, lokal bleibt die
ganze API offen. Websockets über den Tunnel werden geschlossen.
"""

from __future__ import annotations

import os
from urllib.parse import urlsplit

from starlette.responses import PlainTextResponse
from starlette.types import ASGIApp, Receive, Scope, Send


def tunnel_host(public_url: str | None) -> str | None:
    """Host (klein, ohne Port) aus ``PUBLIC_URL``; ``None`` ohne gültige Adresse."""
    if not public_url:
        return None
    host = urlsplit(public_url.strip()).hostname
    return host.lower() if host else None


def tunnel_pfad_erlaubt(pfad: str) -> bool:
    return pfad == "/vapi/webhook" or pfad == "/chat/completions" or pfad.startswith("/chat/completions/")


class TunnelFilter:
    """ASGI-Middleware: ``app.add_middleware(TunnelFilter)``; ``public_url`` ersetzt ``PUBLIC_URL``."""

    def __init__(self, app: ASGIApp, public_url: str | None = None) -> None:
        self.app = app
        self._public_url = public_url

    def _ueber_tunnel(self, scope: Scope) -> bool:
        kopfzeilen = {name.lower(): wert for name, wert in scope.get("headers", [])}
        if b"cf-connecting-ip" in kopfzeilen:
            return True
        erwartet = tunnel_host(self._public_url or os.environ.get("PUBLIC_URL"))
        if erwartet is None:
            return False
        host = kopfzeilen.get(b"host", b"").decode("latin-1")
        return (urlsplit(f"//{host}").hostname or "").lower() == erwartet

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] in ("http", "websocket") and self._ueber_tunnel(scope):
            if scope["type"] == "websocket":
                await send({"type": "websocket.close", "code": 1008})
                return
            if not tunnel_pfad_erlaubt(scope.get("path", "")):
                await PlainTextResponse("Not Found", status_code=404)(scope, receive, send)
                return
        await self.app(scope, receive, send)
