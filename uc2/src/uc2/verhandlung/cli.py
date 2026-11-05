"""Befehl `uv run uc2 verhandlung --fall <id> [--provider …] [--belege fixture|index] [--json]`."""

from __future__ import annotations

import argparse
import functools
import json
import sys

from uc2 import db
from uc2.modelle import PROVIDER, ModellKonfigFehler, waehle_provider
from uc2.verhandlung.ausgabe import als_text
from uc2.verhandlung.belege import BelegFehler, Belegquelle, FixtureQuelle, IndexQuelle
from uc2.verhandlung.bericht import bericht
from uc2.verhandlung.fall import FallFehler, bekannte_faelle, lade_fall
from uc2.verhandlung.lauf import PARALLEL_ECHT, Laufoptionen, Verhandlung, VerhandlungsFehler


def register(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    parser = subparsers.add_parser(
        "verhandlung", help="Verhandlung eines Falls aus uc2/faelle/ laufen lassen (schreibt uc2.ereignis)"
    )
    parser.add_argument(
        "--fall", required=True, help=f"Fall-ID aus uc2/faelle/ ({', '.join(bekannte_faelle())})"
    )
    parser.add_argument(
        "--provider",
        choices=PROVIDER,
        help="Modell-Provider (Standard: LLM_PROVIDER, sonst modellrollen.yaml)",
    )
    parser.add_argument(
        "--belege",
        choices=("fixture", "index"),
        default="fixture",
        help="Belegquelle: fixture (erfunden) oder index (echter Index, vor #43 nur mit mock)",
    )
    parser.add_argument(
        "--max-akteure", type=int, help="Obergrenze der Akteure (Smoke), höchstens wie im Fall"
    )
    parser.add_argument("--max-runden", type=int, help="Obergrenze der Runden (Smoke), höchstens wie im Fall")
    parser.add_argument("--json", action="store_true", help="Bericht als JSON statt Terminal-Text")
    parser.set_defaults(func=ausfuehren)


def ausfuehren(args: argparse.Namespace) -> int:
    try:
        fall = lade_fall(args.fall)
        provider = waehle_provider(args.provider)
    except (FallFehler, ModellKonfigFehler) as fehler:
        print(f"Fehler: {fehler}", file=sys.stderr)
        return 2
    for name, wert in (("--max-akteure", args.max_akteure), ("--max-runden", args.max_runden)):
        if wert is not None and wert < 1:
            print(f"Fehler: {name} muss mindestens 1 sein", file=sys.stderr)
            return 2
    with db.verbinde() as verbindung:
        quelle: Belegquelle = FixtureQuelle() if args.belege == "fixture" else IndexQuelle(verbindung)
        optionen = Laufoptionen(
            provider=provider,
            quelle=quelle,
            max_akteure=args.max_akteure,
            max_runden=args.max_runden,
            parallel=1 if provider == "mock" else PARALLEL_ECHT,
            verbinde=None if provider == "mock" else functools.partial(db.verbinde),
        )
        try:
            fall_id = Verhandlung(verbindung, fall, optionen).fuehre_aus()
        except (BelegFehler, ModellKonfigFehler, VerhandlungsFehler) as fehler:
            print(f"Fehler: {fehler}", file=sys.stderr)
            return 1
        daten = bericht(verbindung, fall_id)
    if args.json:
        sys.stdout.write(json.dumps(daten, ensure_ascii=False, indent=2, default=str) + "\n")
    else:
        sys.stdout.write(als_text(daten))
    return 0
