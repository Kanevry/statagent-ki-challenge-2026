"""CLI: ``uv run python -m plattform.voice sync [--assistant-id ID] [--trocken]``.

``--trocken`` druckt die Assistant-Konfiguration als JSON, ohne Schlüssel und ohne Netz. Ohne ``--trocken``
schreibt ``sync`` den Assistant per Vapi-API (Außenwirkung: nur nach Freigabe ausführen).
"""

from __future__ import annotations

import argparse
import json
import os
import sys

import httpx

from plattform.umgebung import lade_env_local

from .assistant import SyncFehler, assistant_konfiguration, synchronisiere


def main(argv: list[str] | None = None, *, transport: httpx.BaseTransport | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m plattform.voice")
    befehle = parser.add_subparsers(dest="befehl", required=True)
    sync = befehle.add_parser("sync", help="Vapi-Assistant auf PUBLIC_URL setzen (PATCH mit ID, sonst POST)")
    sync.add_argument("--assistant-id", default=None, help="Standard: VAPI_ASSISTANT_ID")
    sync.add_argument("--trocken", action="store_true", help="nur die Konfiguration drucken, kein Netz")
    args = parser.parse_args(argv)

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


if __name__ == "__main__":
    lade_env_local()
    raise SystemExit(main())
