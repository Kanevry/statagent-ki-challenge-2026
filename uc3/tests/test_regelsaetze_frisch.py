"""Frische Datenbank (`db init`): Regelsätze v2 und ministerium sind da, wie die Abgabe sie gerechnet hat (Jury-Probe 4d, B1).

Dazu B2: `sheet` schreibt ohne fertigen Lauf nichts.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from statagent.db import Verbindung, schema_einrichten

# Änderungsaufträge 1 und 2: nur diese Regeln unterscheiden sich zwischen v1 und v2.
GEAENDERT = {"R2_R4_stichtag_eigene_lieferung", "R6_beschaeftigungskategorie"}
VERGLEICH = "typ, art, reihenfolge, parameter, gueltig_ab_lieferung, gueltig_bis_lieferung, aktiv"


def _regeln(conn: Verbindung, regelsatz: str) -> dict[str, tuple[object, ...]]:
    zeilen = conn.execute(
        f"SELECT name, {VERGLEICH} FROM meta.regel WHERE regelsatz = %s", (regelsatz,)
    ).fetchall()
    return {str(z["name"]): tuple(v for k, v in z.items() if k != "name") for z in zeilen}


def test_v2_ist_v1_mit_den_auftraegen_1_und_2(conn: Verbindung) -> None:
    # Fängt: 111_regelsatz_v2.sql weicht von 110/120 ab (z. B. v1 geändert, v2 nicht nachgezogen).
    v1, v2 = _regeln(conn, "v1"), _regeln(conn, "v2")
    assert set(v2) == set(v1)
    assert {n for n in v1 if v1[n] != v2[n]} == GEAENDERT
    r6 = conn.execute(
        "SELECT parameter, freigegeben_von FROM meta.regel WHERE regelsatz = 'v2' AND name = 'R6_beschaeftigungskategorie'"
    ).fetchone()
    assert r6 is not None
    assert r6["parameter"] == {"qualifikation": "beschaeftigungskategorie"}
    assert r6["freigegeben_von"] == "Bernhard Götzendorfer"


def test_v2_hat_eigene_quellzuordnung(conn: Verbindung) -> None:
    n = conn.execute("SELECT count(*) AS n FROM stat.quellzuordnung WHERE regelsatz = 'v2'").fetchone()
    assert n is not None and n["n"] == 100


def test_ministerium_ist_freigegeben_und_eindeutig(conn: Verbindung) -> None:
    # Fängt: `uc3 ministerium` endet auf frischer DB mit „0 aktive Personentage-Regeln (erwartet 1)“.
    from statagent.sonderauswertung import auswertung_regel

    regel = auswertung_regel(conn, "ministerium")
    assert regel.name == "M01_personentage_ministerium"
    assert regel.freigegeben


def test_db_init_zweimal_aendert_die_regelsaetze_nicht(conn: Verbindung) -> None:
    vorher = {rs: _regeln(conn, rs) for rs in ("v1", "v2", "ministerium")}
    schema_einrichten(conn)
    conn.commit()
    assert {rs: _regeln(conn, rs) for rs in ("v1", "v2", "ministerium")} == vorher


def test_lauf_v2_rechnet_auf_frischer_db(conn: Verbindung) -> None:
    # Fängt: „abgebrochen: Regelsatz v2 hat keine aktiven Regeln für 2024-08“.
    lauf = pytest.importorskip("statagent.lauf")
    erg = lauf.lauf_ausfuehren(conn, "2024-08", regelsatz="v2", gestartet_von=None)
    assert erg.status == "fertig"
    assert erg.gelesen == erg.gezaehlt + erg.nicht_gezaehlt + erg.ausgeschlossen


def test_sheet_ohne_lauf_schreibt_nichts(conn: Verbindung, tmp_path: Path) -> None:
    # Fängt: `uc3 sheet --regelsatz v2` ohne Läufe überschreibt die Abgabe mit leeren Spalten bei Exit 0 (B2).
    from statagent.berichte.sheet import sheet_schreiben

    ziel = tmp_path / "aggregationen_v2.xlsx"
    with pytest.raises(ValueError, match="keinen fertigen Lauf"):
        sheet_schreiben(conn, "v2", ziel=ziel)
    assert not ziel.exists()
