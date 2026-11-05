"""Tiefe Klassifikationsebenen (Bewertungsbereich 2) ändern keine bestehende Abfrage.

ÖNACE-Ebenen 2 bis 5 und Bezirke und Gemeinden je Stand stehen in denselben Tabellen wie Abschnitte und
Bundesländer. Sheet, Qualitätsbericht, Fragen, UC4, Regelstand und Bereinigung lesen weiter nur die Ebene,
nach der die Statistik zählt.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from test_klass import tiefe_zeilen_einfuegen, tiefe_zeilen_entfernen

from statagent import uc4
from statagent.bereinigung import oenace_version
from statagent.berichte import qualitaetsbericht, sheet
from statagent.db import Verbindung
from statagent.ergebnis import monatserster, monatsletzter
from statagent.frage import _oenace_version
from statagent.klass import erklaeren
from statagent.regeln import regeln_laden, regelstand

MONATE = ("2024-11", "2025-01")
BLAETTER = (
    sheet.BLATT_BUNDESLAND,
    sheet.BLATT_GESCHLECHT,
    sheet.BLATT_KATEGORIE,
    sheet.OENACE_PRAEFIX + "2008",
    sheet.OENACE_PRAEFIX + "2025",
)


def _stand(conn: Verbindung) -> dict[str, Any]:
    regeln = regeln_laden(conn, "v1", "2024-08")
    return {
        "sheet_blaetter": {b: sheet.merkmal_von(conn, b) for b in BLAETTER},
        "sheet_versionen": {m: sheet._oenace_versionen(conn, m) for m in MONATE},
        "bericht_namen": {m: qualitaetsbericht._klarnamen(conn, m) for m in MONATE},
        "frage_version": {m: _oenace_version(conn, m) for m in MONATE},
        "uc4": {
            (mk.name, m): conn.execute(
                mk.klass.encode(), {"von": monatserster(m), "bis": monatsletzter(m)}
            ).fetchall()
            for mk in uc4.MERKMALE
            for m in MONATE
        },
        "regelstand": regelstand(conn, regeln),
        "bereinigung": [
            oenace_version(conn, regeln, date(2024, 11, 30)),
            oenace_version(conn, regeln, date(2025, 1, 31)),
        ],
        "klass_listen": [erklaeren(conn, b)["versionen"][0]["codes"] for b in ("oenace", "region")],
    }


def test_tiefe_ebenen_aendern_keine_bestehende_abfrage(conn: Verbindung) -> None:
    """Fängt: Bezirke, Gemeinden oder ÖNACE-Unterklassen landen in den Bezeichnungen des Sheets, verschieben
    die geltende ÖNACE-Version, den Regelstand (alle Läufe wären „geändert“) oder die Klarnamen im Bericht."""
    tiefe_zeilen_entfernen(conn)
    vorher = _stand(conn)
    tiefe_zeilen_einfuegen(conn)
    # Ohne Ebenen-Filter hätte die alte Sheet-Abfrage die neuen Zeilen gesehen.
    alt = {
        str(z["code"])
        for z in conn.execute("SELECT code, bezeichnung FROM stat.klass_region ORDER BY version").fetchall()
    }
    assert {"101", "10101"} <= alt
    nachher = _stand(conn)
    for schluessel in vorher:
        assert nachher[schluessel] == vorher[schluessel], schluessel
    assert "10101" not in nachher["sheet_blaetter"][sheet.BLATT_BUNDESLAND][2]
    assert "C 10" not in nachher["sheet_blaetter"][sheet.OENACE_PRAEFIX + "2025"][2]
