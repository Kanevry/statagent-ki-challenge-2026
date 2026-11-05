"""Fährt den Fragen-Katalog über ``uc3 frage`` und /uc4-Station 1 und schreibt die Matrix.

Aufruf auf dem m5, nur gegen die Kopie ``statistik_probe``::

    UC3_DATABASE_URL=… uv run python uc3/tests/fragen_laeufer.py [--aus matrix.md] [--id Z060,Z061]
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent))

from fragen_orakel import Soll, Urteil, Zeile, katalog_lesen, matrix, soll_rechnen, urteilen
from plattform.router import kern_satz

from statagent.db import Verbindung, verbinden
from statagent.frage import als_webantwort, antwort_frage
from statagent.uc4 import uc4_antwort

#: Nur Kopien: Der Läufer liest zwar nur, aber die Abgabe-Datenbank bleibt unberührt. „kic_vorlage“ ist die Ersatz-DB
#: auf dem CI-Server (Dump vom 05.11. 22:05, Zugang nur lesend), solange der m5 weg ist.
ERLAUBTE_DB = frozenset({"statistik_probe", "kic_vorlage"})


def datenbank_pruefen(conn: Verbindung) -> None:
    zeile = conn.execute("SELECT current_database() AS name").fetchone()
    name = str(zeile["name"]) if zeile else ""
    if name not in ERLAUBTE_DB:
        raise SystemExit(f"Der Läufer läuft nur gegen {sorted(ERLAUBTE_DB)}, nicht gegen {name}.")
    print(f"Datenbank: {name}", file=sys.stderr, flush=True)


def _fragen(conn: Verbindung, zeile: Zeile, soll: Soll) -> list[tuple[str, Urteil]]:
    aufruf = zeile.optionen.get("aufruf", "v1")
    ergebnisse: list[tuple[str, Urteil]] = []
    for weg in ("uc3", "uc4"):
        try:
            if weg == "uc3":
                antwort: dict[str, Any] = als_webantwort(antwort_frage(conn, zeile.frage, aufruf))
                ergebnisse.append((weg, urteilen(zeile, soll, antwort)))
            else:
                antwort = uc4_antwort(conn, zeile.frage, aufruf)
                ergebnisse.append((weg, urteilen(zeile, soll, antwort, kern_satz(antwort["text"]))))
        except Exception as fehler:  # Ein Absturz ist für die Jury so schlimm wie eine falsche Zahl.
            conn.rollback()
            ergebnisse.append(
                (weg, Urteil("falsch", f"Absturz: {type(fehler).__name__}: {fehler}", ziel=False))
            )
    return ergebnisse


def laufen(conn: Verbindung, zeilen: list[Zeile]) -> list[tuple[Zeile, str, Urteil]]:
    datenbank_pruefen(conn)
    ergebnisse: list[tuple[Zeile, str, Urteil]] = []
    for nummer, zeile in enumerate(zeilen, start=1):
        beginn = time.monotonic()
        soll = soll_rechnen(conn, zeile)
        conn.rollback()
        orakel = time.monotonic()
        ergebnisse += [(zeile, weg, urteil) for weg, urteil in _fragen(conn, zeile, soll)]
        conn.rollback()
        ende = time.monotonic()
        print(
            f"{nummer}/{len(zeilen)} {zeile.id} Orakel {orakel - beginn:.1f} s, Antworten {ende - orakel:.1f} s",
            file=sys.stderr,
            flush=True,
        )
    return ergebnisse


def main() -> int:
    argumente = argparse.ArgumentParser()
    argumente.add_argument("--aus", type=Path, help="Matrix zusätzlich in diese Datei schreiben")
    argumente.add_argument("--id", default="", help="Nur diese Zeilen, mit Komma getrennt")
    argumente.add_argument("--katalog", type=Path, help="Andere Tabelle statt fragen_katalog.md")
    optionen = argumente.parse_args()
    zeilen = katalog_lesen(optionen.katalog) if optionen.katalog else katalog_lesen()
    if optionen.id:
        gewaehlt = set(optionen.id.split(","))
        zeilen = [z for z in zeilen if z.id in gewaehlt]
    with verbinden() as conn:
        ergebnisse = laufen(conn, zeilen)
    text = matrix(ergebnisse)
    print(text)
    if optionen.aus:
        optionen.aus.write_text(text, encoding="utf-8")
    return 1 if any(u.urteil == "falsch" for _, _, u in ergebnisse) else 0


if __name__ == "__main__":
    raise SystemExit(main())
