"""Qualitätsbericht aus der Fixture-Datenbank (Läufe 2024-08 und 2024-09)."""

from __future__ import annotations

from pathlib import Path

import pytest

from statagent.berichte.pruefe_abgabe import bericht_maengel, einstufungen_aus_bericht
from statagent.berichte.qualitaetsbericht import (
    ABSCHNITTE,
    GUELTIGE_EINSTUFUNGEN,
    BerichtFehler,
    bericht_erzeugen,
    bericht_schreiben,
    zahl,
)
from statagent.db import Verbindung
from statagent.lauf import lauf_ausfuehren


def _laeufe(conn: Verbindung) -> int:
    lauf_ausfuehren(conn, "2024-08", regelsatz="v1", gestartet_von=None)
    return lauf_ausfuehren(conn, "2024-09", regelsatz="v1", gestartet_von=None).lauf_id


def _lauf(conn: Verbindung, lauf_id: int) -> dict[str, object]:
    zeile = conn.execute("SELECT * FROM meta.lauf WHERE id = %s", (lauf_id,)).fetchone()
    assert zeile is not None
    return zeile


def test_bericht_folgt_vorlage_und_meta_lauf(conn: Verbindung) -> None:
    # Fängt: Abschnitte fehlen/vertauscht, Kennzahlen nicht aus meta.lauf, Abrechnung fehlt oder falsch.
    lauf = _lauf(conn, _laeufe(conn))
    text = bericht_erzeugen(conn, "2024-09")
    ueberschriften = [z for z in text.splitlines() if z.startswith("## ")]
    assert ueberschriften == list(ABSCHNITTE)
    assert text.startswith("# Qualitätsbericht – Berichtsmonat 2024-09\n")
    assert "freigegeben von: noch nicht freigegeben" in text
    assert "**Status: VORLÄUFIG.**" in text

    g, z, n, a = (int(str(lauf[k])) for k in ("gelesen", "gezaehlt", "nicht_gezaehlt", "ausgeschlossen"))
    assert f"| gelesene Sätze | {zahl(g)} |" in text
    assert f"| davon gezählt am Stichtag | {zahl(z)} |" in text
    assert f"| Beschäftigungsverhältnisse am Stichtag | {zahl(z)} |" in text
    assert (
        f"Abrechnung in Zahlen: {zahl(g)} gelesen = {zahl(z)} gezählt + {zahl(n)} nicht gezählt"
        f" + {zahl(a)} ausgeschlossen (geht auf)."
    ) in text
    assert "(Annahme A8)" in text
    assert "gegenüber 2024-08" in text
    assert f"Ergebnis-Hash `{lauf['ergebnis_hash']}`" in text
    assert bericht_maengel(text) == []


def test_bericht_ist_bytegleich_und_wird_geschrieben(conn: Verbindung, tmp_path: Path) -> None:
    # Fängt: Zeitstempel „jetzt“, unsortierte Abfragen oder Mengen-Iteration im Bericht.
    _laeufe(conn)
    pfad = bericht_schreiben(conn, "2024-09", ziel=tmp_path / "a" / "2024-09.md")
    assert pfad.read_bytes() == bericht_erzeugen(conn, "2024-09").encode("utf-8")
    assert bericht_erzeugen(conn, "2024-09") == bericht_erzeugen(conn, "2024-09")


def test_auffaelligkeit_mit_einstufung_beleg_und_anhalten(conn: Verbindung) -> None:
    # Fängt: Einstufungs-Code statt Vorlagentext, Beleg-SQL fehlt, angehaltene Prüfung nicht als Grund genannt.
    lauf_id = _laeufe(conn)
    regel = conn.execute(
        """INSERT INTO meta.regel (regelsatz, name, typ, art, reihenfolge, beschreibung, begruendung, grundlage)
           VALUES ('v1', 'P90_testpruefung', 'pruefung', 'test', 90, 'Testprüfung', 'Test', 'Test')
           RETURNING id"""
    ).fetchone()
    assert regel is not None
    for ebene, einstufung, anhalten in (("satz", "erklaert-datenproblem", False), ("aggregat", None, True)):
        conn.execute(
            """INSERT INTO meta.pruefung_treffer (lauf_id, regel_id, ebene, anzahl, einstufung, anhalten, beleg_sql)
               VALUES (%s, %s, %s, 3, %s, %s, 'SELECT vvh_id FROM roh.lieferung WHERE lieferung = ''2024-09''')""",
            (lauf_id, regel["id"], ebene, einstufung, anhalten),
        )
    text = bericht_erzeugen(conn, "2024-09")
    zeilen_p90 = [z for z in text.splitlines() if z.startswith("|") and "Testprüfung" in z]
    assert len(zeilen_p90) == 2
    assert "erklärt – Datenproblem" in zeilen_p90[0] and "nicht erklärbar" in zeilen_p90[1]
    assert set(einstufungen_aus_bericht(text)) <= GUELTIGE_EINSTUFUNGEN
    assert "</summary>" in text and "P90_testpruefung</summary>" in text
    assert "Prüfung P90_testpruefung hat angehalten" in text
    assert bericht_maengel(text) == []


def test_ohne_lauf_gibt_es_keinen_bericht(conn: Verbindung) -> None:
    # Fängt: ein Bericht aus leeren Kennzahlen, wenn der Monat nie gerechnet wurde.
    with pytest.raises(BerichtFehler):
        bericht_erzeugen(conn, "2024-09")
