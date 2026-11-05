"""Einstieg `uv run uc2 …`.

Jedes Teilmodul hängt seine Befehle selbst ein: es stellt `register(subparsers)` bereit und setzt je
Befehl `set_defaults(func=…)`. Ein Modul, das es noch nicht gibt, wird übersprungen; so können
Belege, Akteure und Experte parallel entstehen, ohne diese Datei zu ändern.
"""

from __future__ import annotations

import argparse
import importlib
import sys
from collections.abc import Sequence

MODULE: tuple[str, ...] = (
    "uc2.belege.cli",
    "uc2.akteure.cli",
    "uc2.experte.cli",
    "uc2.verhandlung.cli",
    "uc2.verhandlung.freigabe",
)


def baue_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="uc2", description="UC2 HealthPolicy Simulator")
    sub = parser.add_subparsers(dest="befehl", metavar="BEFEHL")
    for name in MODULE:
        try:
            modul = importlib.import_module(name)
        except ModuleNotFoundError as fehler:
            # Nur das fehlende Modul selbst überspringen, nie einen Importfehler darin.
            if fehler.name is not None and name.startswith(fehler.name):
                continue
            raise
        modul.register(sub)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = baue_parser()
    args = parser.parse_args(argv)
    func = getattr(args, "func", None)
    if func is None:
        parser.print_help()
        return 2
    ergebnis = func(args)
    return int(ergebnis or 0)


if __name__ == "__main__":
    sys.exit(main())
