"""Fragen-Katalog gegen die echten Daten (nur auf dem m5, CI wählt ``daten`` ab).

Die Datenbank kommt aus ``UC3_DATABASE_URL`` und muss eine Kopie sein (``ERLAUBTE_DB``). Es wird nur gelesen.
"""

from __future__ import annotations

import psycopg
import pytest
from fragen_laeufer import ERLAUBTE_DB, laufen
from fragen_orakel import Urteil, Zeile, katalog_lesen, matrix

from statagent import db

pytestmark = pytest.mark.daten


@pytest.fixture(scope="module")
def ergebnisse() -> list[tuple[Zeile, str, Urteil]]:
    try:
        with db.verbinden() as conn:
            name = conn.execute("SELECT current_database() AS name").fetchone()
            if not name or name["name"] not in ERLAUBTE_DB:
                pytest.skip(f"läuft nur gegen {sorted(ERLAUBTE_DB)}")
            werte = laufen(conn, katalog_lesen())
    except psycopg.OperationalError as fehler:
        pytest.skip(f"keine Datenbank: {fehler}")
    print(matrix(werte))
    return werte


def test_keine_falsche_zahl(ergebnisse: list[tuple[Zeile, str, Urteil]]) -> None:
    falsch = [f"{z.id} [{w}] {z.frage}: {u.grund}" for z, w, u in ergebnisse if u.urteil == "falsch"]
    assert not falsch, "\n".join(falsch)


def test_verstandene_frage_bekommt_die_zahl(ergebnisse: list[tuple[Zeile, str, Urteil]]) -> None:
    offen = [
        f"{z.id} [{w}] {z.frage}: {u.urteil}" for z, w, u in ergebnisse if z.muss and u.urteil != "richtig"
    ]
    assert not offen, "\n".join(offen)


def test_station_zeigt_die_antwort(ergebnisse: list[tuple[Zeile, str, Urteil]]) -> None:
    maengel = [f"{z.id} {z.frage}: {u.mangel}" for z, _, u in ergebnisse if u.mangel]
    assert not maengel, "\n".join(maengel)
