"""CLI ``uv run python -m plattform.voice``: ``serve``, ``sync``, ``smoke``.

- ``serve [--uc uc4] [--mock] [--port 8104] [--host 127.0.0.1]`` startet die Voice-App mit uvicorn.
- ``sync [--assistant-id ID] [--trocken]``: ``--trocken`` druckt die Assistant-Konfiguration als JSON, ohne
  Schlüssel und ohne Netz; sonst schreibt ``sync`` den Assistant per Vapi-API.
- ``smoke [--assistant-id ID] [--frage TEXT]`` stellt eine Textfrage über ``POST /chat`` der Vapi-API.

``sync`` und ``smoke`` haben Außenwirkung: nur nach Freigabe ausführen. Ausgegeben werden nie Schlüssel.
"""

from __future__ import annotations

import argparse
import json
import os
import sys

import httpx

from plattform.umgebung import lade_env_local

from .assistant import SMOKE_FRAGE, SyncFehler, assistant_konfiguration, smoke, synchronisiere


def _serve(args: argparse.Namespace) -> int:
    import uvicorn  # erst hier: sync und smoke brauchen keinen Server

    from .app import erstelle_app

    uvicorn.run(erstelle_app(args.uc, mock=args.mock), host=args.host, port=args.port)
    return 0


def _sync(args: argparse.Namespace, transport: httpx.BaseTransport | None) -> int:
    try:
        konfiguration = assistant_konfiguration(os.environ.get("PUBLIC_URL"))
        if args.trocken:
            print(json.dumps(konfiguration, ensure_ascii=False, indent=2))
            return 0
        kennung = synchronisiere(
            konfiguration,
            api_key=os.environ.get("VAPI_API_KEY"),
            webhook_secret=os.environ.get("VAPI_WEBHOOK_SECRET"),
            assistant_id=args.assistant_id or os.environ.get("VAPI_ASSISTANT_ID") or None,
            transport=transport,
        )
    except SyncFehler as fehler:
        print(f"sync abgebrochen: {fehler}", file=sys.stderr)
        return 2
    except httpx.HTTPError as fehler:
        print(f"sync abgebrochen: {type(fehler).__name__}", file=sys.stderr)
        return 1
    print(f"Assistant {kennung}: Custom LLM {konfiguration['model']['url']}")
    return 0


def _smoke(args: argparse.Namespace, transport: httpx.BaseTransport | None) -> int:
    assistant_id = args.assistant_id or os.environ.get("VAPI_ASSISTANT_ID")
    try:
        if not assistant_id:
            raise SyncFehler("--assistant-id fehlt (oder VAPI_ASSISTANT_ID)")
        ergebnis = smoke(
            api_key=os.environ.get("VAPI_API_KEY"),
            assistant_id=assistant_id,
            frage=args.frage,
            transport=transport,
        )
    except SyncFehler as fehler:
        print(f"smoke fehlgeschlagen: {fehler}", file=sys.stderr)
        return 1
    except httpx.HTTPError as fehler:
        print(f"smoke fehlgeschlagen: {type(fehler).__name__}", file=sys.stderr)
        return 1
    print(f"Chat {ergebnis.chat_id}: {ergebnis.antwort}")
    return 0


def main(argv: list[str] | None = None, *, transport: httpx.BaseTransport | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m plattform.voice")
    befehle = parser.add_subparsers(dest="befehl", required=True)

    serve = befehle.add_parser("serve", help="Voice-App (Router + Tunnel-Filter) mit uvicorn starten")
    serve.add_argument("--uc", default="uc4", choices=["uc4"])
    serve.add_argument("--mock", action="store_true", help="Mock-Adapter des Routers, ohne Netz und DB")
    serve.add_argument("--port", type=int, default=8104)
    serve.add_argument("--host", default="127.0.0.1")

    sync = befehle.add_parser("sync", help="Vapi-Assistant auf PUBLIC_URL setzen (PATCH mit ID, sonst POST)")
    sync.add_argument("--assistant-id", default=None, help="Standard: VAPI_ASSISTANT_ID")
    sync.add_argument("--trocken", action="store_true", help="nur die Konfiguration drucken, kein Netz")

    probe = befehle.add_parser("smoke", help="eine Textfrage über die Vapi-Chat-API an den Assistant")
    probe.add_argument("--assistant-id", default=None, help="Standard: VAPI_ASSISTANT_ID")
    probe.add_argument("--frage", default=SMOKE_FRAGE)

    args = parser.parse_args(argv)
    if args.befehl == "serve":
        return _serve(args)
    if args.befehl == "smoke":
        return _smoke(args, transport)
    return _sync(args, transport)


if __name__ == "__main__":
    lade_env_local()
    raise SystemExit(main())
