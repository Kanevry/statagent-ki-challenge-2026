"""Anhang B: die Prüfabfragen aus docs/plan/uc3/anhang-b-schema.sql liefern auf der Fixture-Datenbank überall 0.

Läuft nach `schema_einrichten` und drei Läufen v1 (Fixture-Lieferungen 2024-08 bis 2024-10). Pensionen sind nicht
importiert; die Integrität nach einem Pensionsimport ist offen (Optimum Bereich 1).
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from statagent.db import Verbindung

SQL_DATEI = Path(__file__).resolve().parents[2] / "docs" / "plan" / "uc3" / "anhang-b-schema.sql"


def _abfragen() -> list[str]:
    text = SQL_DATEI.read_text(encoding="utf-8")
    ohne_kommentare = "\n".join(z for z in text.splitlines() if not z.lstrip().startswith("--"))
    return [a.strip() for a in re.split(r";\s*\n", ohne_kommentare) if a.strip()]


def test_sql_datei_hat_elf_pruefungen() -> None:
    # Fängt: eine Prüfung geht beim Bearbeiten verloren oder zwei verschmelzen (fehlendes Semikolon).
    namen = [re.search(r"'(B\d+) ", a) for a in _abfragen()]
    assert [m.group(1) for m in namen if m] == [f"B{i}" for i in range(1, 12)]


@pytest.fixture
def gerechnet(conn: Verbindung) -> Verbindung:
    lauf = pytest.importorskip("statagent.lauf")
    for lieferung in ("2024-08", "2024-09", "2024-10"):
        lauf.lauf_ausfuehren(conn, lieferung, regelsatz="v1", gestartet_von=None)
    conn.commit()
    return conn


def test_alle_pruefabfragen_ergeben_null(gerechnet: Verbindung) -> None:
    # Fängt: Pflichtfeld in beschreibung/variable leer, Dimension zeigt ins Leere, Variable ohne Metadaten,
    # gelieferte Ausprägung ohne Quellzuordnung, Zellcode ohne Klassifikationszeile.
    assert gerechnet.execute("SELECT count(*) AS n FROM stat.stat_beschaeftigte").fetchone()["n"] > 0  # type: ignore[index]
    ergebnisse = {}
    for abfrage in _abfragen():
        zeile = gerechnet.execute(abfrage.encode()).fetchone()
        assert zeile is not None
        ergebnisse[zeile["pruefung"]] = zeile["fehlend"]
    assert len(ergebnisse) == 11
    assert {p: n for p, n in ergebnisse.items() if n} == {}


class _Zurueck(Exception):
    """Bricht die Transaktion ab, damit die gelöschten Zuordnungen zurückkommen."""


def test_b10_erkennt_fehlende_quellzuordnung(gerechnet: Verbindung) -> None:
    # Fängt: B10 meldet nie etwas (z. B. falscher Abgleich auf '<leer>' oder '<sonst>').
    b10 = next(a for a in _abfragen() if "'B10 " in a)
    with pytest.raises(_Zurueck), gerechnet.transaction():
        gerechnet.execute(
            "DELETE FROM stat.quellzuordnung WHERE regelsatz = 'v1' AND merkmal = 'geschlecht'"
            " AND geliefert IN ('<sonst>', 'M')"
        )
        zeile = gerechnet.execute(b10.encode()).fetchone()
        assert zeile is not None and zeile["fehlend"] > 0
        raise _Zurueck
    zeile = gerechnet.execute(b10.encode()).fetchone()
    assert zeile is not None and zeile["fehlend"] == 0
