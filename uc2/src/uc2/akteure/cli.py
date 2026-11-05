"""CLI-Befehle `uv run uc2 akteure …`."""

from __future__ import annotations

import argparse
import json
from typing import Any

from uc2.akteure.pruefen import pruefe


def register(subparsers: Any) -> None:
    """Hängt `akteure pruefen [--json]` an den Hauptparser."""
    akteure = subparsers.add_parser("akteure", help="Akteurs-Pool und Modellrollen")
    unter = akteure.add_subparsers(dest="akteure_befehl", metavar="BEFEHL")
    akteure.set_defaults(func=lambda _args: (akteure.print_help(), 2)[1])
    pruefen = unter.add_parser("pruefen", help="14 Akteursdateien, Schema, Modellrollen, Namensscan prüfen")
    pruefen.add_argument("--json", action="store_true", help="Ergebnis als JSON ausgeben")
    pruefen.set_defaults(func=_pruefen)


def _pruefen(args: argparse.Namespace) -> int:
    ergebnis = pruefe()
    if args.json:
        print(json.dumps(ergebnis.als_dict(), ensure_ascii=False, indent=2))
    else:
        for hinweis in ergebnis.hinweise:
            print(hinweis)
        if ergebnis.ok:
            print(
                f"ok: {len(ergebnis.akteure)} Akteure gültig, Rollen {', '.join(ergebnis.rollen)}, "
                "Namensscan 0 Treffer"
            )
        else:
            print(f"{len(ergebnis.fehler)} Fehler:")
            for fehler in ergebnis.fehler:
                print(f"- {fehler}")
    return 0 if ergebnis.ok else 1
