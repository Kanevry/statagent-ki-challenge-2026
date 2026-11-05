"""Spike 1 (#28): OpenAI-kompatibler Echo-Endpunkt für die Tunnel-Messung (ohne Vapi).

POST /chat/completions mit "Authorization: Bearer <token>" antwortet als Server-Sent Events
(text/event-stream) im Chunk-Format von OpenAI und gibt die letzte User-Nachricht als Echo zurück.
Fehlendes oder falsches Token: 401. Jeder andere Pfad oder jede andere Methode: 404.

Das Token kommt zur Laufzeit aus der Umgebungsvariable TUNNEL_ECHO_TOKEN (z. B. aus
secrets.token_urlsafe), es steht nie im Repo.

Aufruf aus uc1/:  TUNNEL_ECHO_TOKEN=… uv run python spikes/tunnel_echo.py [--port 8199]
"""

from __future__ import annotations

import argparse
import hmac
import json
import os
import sys
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

PFAD = "/chat/completions"
MAX_KOERPER = 1 << 20


def _letzte_user_nachricht(anfrage: dict[str, Any]) -> str:
    for nachricht in reversed(anfrage.get("messages") or []):
        if isinstance(nachricht, dict) and nachricht.get("role") == "user":
            inhalt = nachricht.get("content")
            return inhalt if isinstance(inhalt, str) else json.dumps(inhalt, ensure_ascii=False)
    return ""


class EchoHandler(BaseHTTPRequestHandler):
    token: str = ""
    protocol_version = "HTTP/1.1"

    def log_message(self, format: str, *args: Any) -> None:
        # Nur Methode, Pfad, Status; keine Header (Token), keine Inhalte.
        sys.stderr.write(f"{self.log_date_time_string()} {format % args}\n")

    def _antwort(self, status: int, koerper: dict[str, Any]) -> None:
        # Ungelesener Request-Body bliebe sonst in der Keep-alive-Verbindung (cloudflared nutzt sie
        # weiter) und verdürbe die nächste Anfrage. Darum: Verbindung nach Fehlerantworten schließen.
        daten = json.dumps(koerper).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(daten)))
        self.send_header("Connection", "close")
        self.close_connection = True
        self.end_headers()
        self.wfile.write(daten)

    def _nicht_gefunden(self) -> None:
        self._antwort(404, {"error": {"message": "nicht gefunden"}})

    do_GET = do_PUT = do_DELETE = do_PATCH = _nicht_gefunden

    def do_POST(self) -> None:
        if self.path.split("?", 1)[0].rstrip("/") != PFAD:
            self._nicht_gefunden()
            return
        kopf = self.headers.get("Authorization", "")
        erwartet = f"Bearer {self.token}"
        if not self.token or not hmac.compare_digest(kopf.encode(), erwartet.encode()):
            self._antwort(401, {"error": {"message": "nicht autorisiert"}})
            return
        laenge = int(self.headers.get("Content-Length") or 0)
        if laenge > MAX_KOERPER:
            self._antwort(413, {"error": {"message": "zu gross"}})
            return
        try:
            anfrage = json.loads(self.rfile.read(laenge) or b"{}")
        except json.JSONDecodeError:
            self._antwort(400, {"error": {"message": "kein JSON"}})
            return

        echo = _letzte_user_nachricht(anfrage)
        kennung = f"chatcmpl-echo-{time.time_ns()}"
        basis = {"id": kennung, "object": "chat.completion.chunk", "created": int(time.time())}
        basis["model"] = anfrage.get("model", "echo")

        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "close")
        self.end_headers()
        self.close_connection = True

        def senden(delta: dict[str, Any], ende: str | None = None) -> None:
            chunk = {**basis, "choices": [{"index": 0, "delta": delta, "finish_reason": ende}]}
            self.wfile.write(f"data: {json.dumps(chunk, ensure_ascii=False)}\n\n".encode())
            self.wfile.flush()

        senden({"role": "assistant", "content": ""})
        for wort in echo.split(" "):
            senden({"content": wort + " "})
        senden({}, "stop")
        self.wfile.write(b"data: [DONE]\n\n")
        self.wfile.flush()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8199)
    args = parser.parse_args()
    token = os.environ.get("TUNNEL_ECHO_TOKEN", "")
    if not token:
        print("TUNNEL_ECHO_TOKEN ist nicht gesetzt", file=sys.stderr)
        return 2
    EchoHandler.token = token
    server = ThreadingHTTPServer((args.host, args.port), EchoHandler)
    print(f"tunnel_echo lauscht auf http://{args.host}:{args.port}{PFAD}", file=sys.stderr, flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
