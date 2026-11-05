"""Befehl `uv run uc2 verhandlung --fall <id> [--provider …] [--belege fixture|index] [--json]`.

Für die API (`uc2.api`, #44) gibt es zwei Schalter:

- `--frage-stdin`: Die Frage kommt als Freitext über stdin statt aus der Fall-YAML. `pruefe_frage` fasst
  Leerraum zusammen, lehnt Steuer- und Bidi-Zeichen ab und begrenzt auf `MAX_FRAGE` Zeichen. Die Frage landet
  so in `uc2.fall` und im Ereignis `start`.
- `--melde-fall-id`: Die CLI schreibt `fall_id=<n>` als erste Zeile auf stdout, sobald der Fall in
  `uc2.fall` committet ist, und leert den Puffer sofort. Gewählt statt einer vorab vergebenen UUID
  (`--fall-ref`): `uc2.fall.fall_id` ist eine Identity-Spalte, eine UUID bräuchte eine neue Spalte samt
  Migration bestehender Tabellen, und die API müsste PG abfragen, bis die Zeile erscheint. Mit der ersten
  Zeile kennt die API die echte Fall-ID genau dann, wenn der Fall lesbar ist; SSE findet ihn sofort.
  Scheitert der Lauf vor der Anlage (Konfiguration, Belegfreigabe), kommt keine Zeile, und die API meldet
  den Start als gescheitert.

Standard von `--belege` (`waehle_belege`): `index`, wenn `uc2.abschnitt` Zeilen hat und die Namensliste
geladen ist (`UC2_NAMENSLISTE`, Datei außerhalb des Repos); sonst `fixture` mit Hinweis auf stderr. Ein
ausdrückliches `--belege` gewinnt immer; mit echtem Provider prüft danach `pruefe_freigabe`.
"""

from __future__ import annotations

import argparse
import dataclasses
import functools
import json
import sys
import unicodedata
from typing import Any

import psycopg

from uc2 import db
from uc2.modelle import PROVIDER, ModellKonfigFehler, waehle_provider
from uc2.verhandlung.ausgabe import als_text
from uc2.verhandlung.belege import (
    NAMENSLISTE_ANLEITUNG,
    BelegFehler,
    Belegquelle,
    FixtureQuelle,
    IndexQuelle,
    hat_index,
    lade_namensliste,
)
from uc2.verhandlung.bericht import bericht
from uc2.verhandlung.fall import FallFehler, bekannte_faelle, lade_fall
from uc2.verhandlung.lauf import PARALLEL_ECHT, Laufoptionen, Verhandlung, VerhandlungsFehler

MAX_FRAGE = 500
"""Höchstlänge der Frage in Zeichen (nach dem Zusammenfassen von Leerraum)."""
_BIDI = frozenset("\u202a\u202b\u202c\u202d\u202e\u2066\u2067\u2068\u2069\u200e\u200f")


class FrageFehler(ValueError):
    """Frage leer, zu lang oder mit Steuerzeichen."""


def pruefe_frage(roh: str) -> str:
    """Freitext-Frage prüfen und normalisieren; `FrageFehler` bei Verstoß.

    Zeilenumbrüche und Tabulatoren sind erlaubt und werden wie jeder Leerraum zu einem Leerzeichen; jedes
    andere Steuerzeichen (Unicode Cc) und Richtungszeichen (Bidi) wird abgelehnt.
    """
    for zeichen in roh:
        if zeichen in _BIDI or (unicodedata.category(zeichen) == "Cc" and zeichen not in "\t\n\r"):
            raise FrageFehler(f"Frage enthält ein Steuerzeichen (U+{ord(zeichen):04X})")
    frage = " ".join(roh.split())
    if not frage:
        raise FrageFehler("Frage ist leer")
    if len(frage) > MAX_FRAGE:
        raise FrageFehler(f"Frage ist länger als {MAX_FRAGE} Zeichen ({len(frage)})")
    return frage


def _melde_fall_id(fall_id: int) -> None:
    sys.stdout.write(f"fall_id={fall_id}\n")
    sys.stdout.flush()


def waehle_belege(verbindung: psycopg.Connection[Any], ausdruecklich: str | None) -> Belegquelle:
    """Belegquelle nach `--belege` oder, ohne Angabe, nach Index und Namensliste (siehe Moduldoku)."""
    namen = lade_namensliste() if ausdruecklich != "fixture" else None
    if ausdruecklich == "index":
        if namen is None:
            # Fail-closed (Review !43): ohne Namensliste schützen die Muster allein nur 93,8 % der Namen.
            raise BelegFehler(f"Belege aus dem Index nur mit Namensliste. {NAMENSLISTE_ANLEITUNG}")
        return IndexQuelle(verbindung, namen=namen)
    if ausdruecklich == "fixture":
        return FixtureQuelle()
    index = hat_index(verbindung)
    if index and namen is not None:
        return IndexQuelle(verbindung, namen=namen)
    grund = (
        "kein Index in uc2.abschnitt" if not index else f"keine Namensliste geladen ({NAMENSLISTE_ANLEITUNG})"
    )
    print(f"Hinweis: Belege aus der Fixture (erfunden), weil {grund}.", file=sys.stderr)
    return FixtureQuelle()


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
        default=None,
        help="Belegquelle: fixture (erfunden) oder index (maskierter Index; echte Provider nur mit "
        "Namensliste). Standard: index, wenn Index und Namensliste da sind, sonst fixture",
    )
    parser.add_argument(
        "--max-akteure", type=int, help="Obergrenze der Akteure (Smoke), höchstens wie im Fall"
    )
    parser.add_argument("--max-runden", type=int, help="Obergrenze der Runden (Smoke), höchstens wie im Fall")
    parser.add_argument("--json", action="store_true", help="Bericht als JSON statt Terminal-Text")
    parser.add_argument(
        "--frage-stdin",
        action="store_true",
        help=f"Frage als Freitext von stdin statt aus der Fall-YAML (höchstens {MAX_FRAGE} Zeichen)",
    )
    parser.add_argument(
        "--melde-fall-id",
        action="store_true",
        help="erste Zeile auf stdout: fall_id=<n>, sobald der Fall angelegt ist (für uc2.api)",
    )
    parser.set_defaults(func=ausfuehren)


def ausfuehren(args: argparse.Namespace) -> int:
    try:
        fall = lade_fall(args.fall)
        provider = waehle_provider(args.provider)
        if args.frage_stdin:
            # Begrenzt lesen: mehr als das Vierfache der Höchstlänge ist sicher zu lang.
            fall = dataclasses.replace(fall, frage=pruefe_frage(sys.stdin.read(MAX_FRAGE * 4 + 1)))
    except (FallFehler, ModellKonfigFehler, FrageFehler) as fehler:
        print(f"Fehler: {fehler}", file=sys.stderr)
        return 2
    for name, wert in (("--max-akteure", args.max_akteure), ("--max-runden", args.max_runden)):
        if wert is not None and wert < 1:
            print(f"Fehler: {name} muss mindestens 1 sein", file=sys.stderr)
            return 2
    with db.verbinde() as verbindung:
        try:
            quelle = waehle_belege(verbindung, args.belege)
        except BelegFehler as fehler:
            print(f"Fehler: {fehler}", file=sys.stderr)
            return 2
        optionen = Laufoptionen(
            provider=provider,
            quelle=quelle,
            max_akteure=args.max_akteure,
            max_runden=args.max_runden,
            parallel=1 if provider == "mock" else PARALLEL_ECHT,
            verbinde=None if provider == "mock" else functools.partial(db.verbinde),
            bei_anlage=_melde_fall_id if args.melde_fall_id else None,
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
