"""Freigabe des Berichts einer fertigen Verhandlung durch einen Menschen (PRD S8, U2-2).

Ein Kern für API (`POST /faelle/{id}/freigabe`) und CLI (`uv run uc2 freigabe <fall_id> --name "…"`).
Der Name wird wie in der Plattform geprüft (`plattform.freigabe.pruefe_name`, „Team“ gilt nicht). Die
Entscheidung steht in `uc2.freigabe` und zusätzlich im gemeinsamen Protokoll (`meta.protokoll`,
`meta.freigabe`, Vertrag P, ohne Git-Commit); warum nicht `plattform.freigabe.freigeben`, steht in
`uc2/sql/003_freigabe.sql`. Die Fehler tragen feste, einfache Sätze (SEC-009): sie nennen weder Pfade
noch SQL noch den eingegebenen Text.
"""

from __future__ import annotations

import argparse
import sys
import unicodedata
from datetime import datetime
from typing import Any

import psycopg
from plattform.freigabe import NameUngueltig, pruefe_name  # type: ignore[import-untyped]  # kein py.typed

from uc2 import db
from uc2.verhandlung.speicher import lies_fall, schreibe_freigabe

ENTSCHEIDUNGEN = ("freigegeben", "abgelehnt")
MAX_BEGRUENDUNG = 500
"""Höchstlänge der Begründung in Zeichen (nach dem Zusammenfassen von Leerraum)."""
_BIDI = frozenset("‪‫‬‭‮⁦⁧⁨⁩‎‏")

NAME_UNGUELTIG = "Bitte Vor- und Nachnamen eines Menschen eintragen. „Team“ gilt nicht."
BEGRUENDUNG_FEHLT = "Eine Ablehnung braucht eine Begründung."
BEGRUENDUNG_UNGUELTIG = f"Die Begründung darf höchstens {MAX_BEGRUENDUNG} Zeichen haben, ohne Steuerzeichen."
NICHT_FERTIG = "Der Bericht kann erst nach dem Ende der Verhandlung freigegeben werden."
SCHON_ENTSCHIEDEN = "Dieser Bericht ist schon entschieden."
KEIN_FALL = "Diesen Fall gibt es nicht."


class FreigabeFehler(Exception):
    """Freigabe nicht möglich; `str(fehler)` ist ein fester Satz, `art` sagt, warum."""

    def __init__(self, art: str, satz: str) -> None:
        super().__init__(satz)
        self.art = art


def pruefe_begruendung(roh: str | None) -> str | None:
    """Begründung mit zusammengefasstem Leerraum, oder `None`, wenn leer. Steuerzeichen sind verboten."""
    if roh is None:
        return None
    for zeichen in roh:
        if zeichen in _BIDI or (unicodedata.category(zeichen) == "Cc" and zeichen not in "\t\n\r"):
            raise FreigabeFehler("begruendung", BEGRUENDUNG_UNGUELTIG)
    text = " ".join(roh.split())
    if len(text) > MAX_BEGRUENDUNG:
        raise FreigabeFehler("begruendung", BEGRUENDUNG_UNGUELTIG)
    return text or None


def entscheide(
    verbindung: psycopg.Connection[Any],
    fall_id: int,
    name: str,
    entscheidung: str,
    begruendung: str | None = None,
) -> datetime:
    """Gibt den Bericht frei oder lehnt ihn ab und liefert den Zeitpunkt aus PG.

    Wirft `FreigabeFehler`: `name`, `begruendung`, `entscheidung`, `kein_fall`, `nicht_fertig`, `entschieden`.
    Die Verbindung braucht `autocommit=True`.
    """
    if entscheidung not in ENTSCHEIDUNGEN:
        raise FreigabeFehler("entscheidung", "Die Entscheidung muss „freigegeben“ oder „abgelehnt“ sein.")
    try:
        sauber = pruefe_name(name)
    except NameUngueltig as fehler:
        raise FreigabeFehler("name", NAME_UNGUELTIG) from fehler
    grund = pruefe_begruendung(begruendung)
    if entscheidung == "abgelehnt" and grund is None:
        raise FreigabeFehler("begruendung", BEGRUENDUNG_FEHLT)
    try:
        fall = lies_fall(verbindung, fall_id)
    except psycopg.errors.UndefinedTable:
        fall = None
    if fall is None:
        raise FreigabeFehler("kein_fall", KEIN_FALL)
    if fall["status"] != "fertig":
        raise FreigabeFehler("nicht_fertig", NICHT_FERTIG)
    ablehnung = grund if entscheidung == "abgelehnt" else None
    zeitpunkt = schreibe_freigabe(verbindung, fall_id, sauber, entscheidung, ablehnung, fall["fall_name"])
    if zeitpunkt is None:
        raise FreigabeFehler("entschieden", SCHON_ENTSCHIEDEN)
    return zeitpunkt


# --- CLI -----------------------------------------------------------------------------------------------


def ausfuehren(args: argparse.Namespace) -> int:
    entscheidung = "abgelehnt" if args.ablehnen else "freigegeben"
    try:
        with db.verbinde(autocommit=True) as verbindung:
            zeit = entscheide(verbindung, args.fall_id, args.name, entscheidung, args.begruendung)
    except FreigabeFehler as fehler:
        print(f"Fehler: {fehler}", file=sys.stderr)
        return 2 if fehler.art in ("name", "begruendung", "entscheidung") else 1
    wort = "Abgelehnt" if args.ablehnen else "Freigegeben"
    print(f"{wort} von {' '.join(args.name.split())}, {zeit.astimezone().strftime('%d.%m.%Y %H:%M')}.")
    return 0


def register(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    parser = subparsers.add_parser(
        "freigabe", help="Bericht einer fertigen Verhandlung mit Vor- und Nachnamen freigeben oder ablehnen"
    )
    parser.add_argument("fall_id", type=int, help="Nummer des Falls (siehe uc2.fall)")
    parser.add_argument("--name", required=True, help="Vor- und Nachname, „Team“ wird abgelehnt")
    parser.add_argument("--ablehnen", action="store_true", help="ablehnen (mit --begruendung)")
    parser.add_argument("--begruendung", help="Begründung der Ablehnung")
    parser.set_defaults(func=ausfuehren)
