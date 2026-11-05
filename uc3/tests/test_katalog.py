"""Nachweise Betrieb v1 (#16): Laufmanifest (AC1) und Prüfkatalog P01–P24 (AC2) auf den Fixture-Lieferungen."""

from __future__ import annotations

import csv
from pathlib import Path

import pytest

from statagent import pruefungen
from statagent.berichte.katalog import (
    KATALOG_SPALTEN,
    laufmanifest_luecken,
    laufmanifest_schreiben,
    pruefkatalog_schreiben,
    pruefkatalog_zeilen,
)
from statagent.db import Verbindung


def test_pruefkatalog_hat_24_vollstaendige_plaetze(conn: Verbindung, tmp_path: Path) -> None:
    # Fängt: fehlender/doppelter Platz, leeres Pflichtfeld in der CSV, „umgesetzt“ ohne Code-Pfad in pruefungen.py.
    datei = pruefkatalog_schreiben(conn, tmp_path / "pruefkatalog.csv")
    with datei.open(encoding="utf-8", newline="") as f:
        zeilen = list(csv.DictReader(f))
    assert [z["platz"] for z in zeilen] == [f"P{n:02d}" for n in range(1, 25)]
    for z in zeilen:
        assert all(z[s].strip() for s in KATALOG_SPALTEN), z["platz"]
        if z["status"] == "umgesetzt":
            datei_teil, funktion = z["sql"].split(":")
            assert datei_teil == "statagent/pruefungen.py"
            assert pruefungen.ARTEN[z["art"]].__name__ == funktion, z["platz"]
    assert {z["herkunft"] for z in zeilen} <= {"forensik", "anhang_a", "zusatz"}


def test_pruefkatalog_wirft_bei_fehlender_einstufung(conn: Verbindung) -> None:
    # Fängt: ein Platz ohne Einstufung landet still als leere Zelle im Katalog.
    conn.execute(
        "UPDATE meta.regel SET parameter = parameter - 'einstufung' WHERE regelsatz = 'v1' AND name LIKE 'P05\\_%'"
    )
    with pytest.raises(ValueError, match=r"P05 .*'einstufung'"):
        pruefkatalog_zeilen(conn)


def test_laufmanifest_letzter_lauf_ohne_abgebrochene_und_ohne_spaetere_lieferung(
    conn: Verbindung, tmp_path: Path
) -> None:
    # Fängt: abgebrochener Lauf im Manifest, älterer statt jüngster Lauf bei Neulauf, Lieferung nach dem Laufmonat.
    from statagent.lauf import lauf_ausfuehren

    ids = {m: lauf_ausfuehren(conn, m, regelsatz="v1").lauf_id for m in ("2024-08", "2024-09", "2024-10")}
    neulauf = lauf_ausfuehren(conn, "2024-10", regelsatz="v1").lauf_id
    conn.execute("INSERT INTO meta.lauf (lieferung, regelsatz) VALUES ('2024-11', 'v1')")  # Status laeuft
    conn.commit()

    datei = laufmanifest_schreiben(conn, tmp_path / "laufmanifest-v1.csv")
    with datei.open(encoding="utf-8", newline="") as f:
        zeilen = list(csv.DictReader(f))
    assert [z["monat"] for z in zeilen] == ["2024-08", "2024-09", "2024-10"]
    assert [int(z["lauf_id"]) for z in zeilen] == [ids["2024-08"], ids["2024-09"], neulauf]
    assert all(z["nach_laufmonat"] == "0" for z in zeilen)
    assert all(z["spaeteste_verwendete_lieferung"] == z["monat"] for z in zeilen)
    assert "2024-08" in zeilen[1]["verwendete_lieferungen"].split(";")  # Revision und Vormonatsvergleich
    assert laufmanifest_luecken(conn) == ["2024-11"]
