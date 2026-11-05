"""Die Datei für die Web-Monatsseite passt zu den Daten (#179): erst dadurch ist sie keine Konstante."""

from __future__ import annotations

import json
from collections.abc import Iterator

import psycopg
import pytest

from statagent import db
from statagent.berichte.oenace_wechsel import DATEI, als_text, wechsel_je_monat


@pytest.fixture(scope="module")
def conn() -> Iterator[db.Verbindung]:
    try:
        verbindung = db.verbinden()
    except psycopg.OperationalError as fehler:
        pytest.fail(f"Datenbank nicht erreichbar ({type(fehler).__name__}); UC3_DATABASE_URL prüfen")
    yield verbindung
    verbindung.close()


@pytest.mark.daten
def test_datei_gleicht_den_daten_aufs_byte(conn: db.Verbindung) -> None:
    assert DATEI.read_text(encoding="utf-8") == als_text(wechsel_je_monat(conn)), (
        "web/components/uc3/oenace-wechsel.json weicht ab: uv run uc3 oenace-wechsel, dann committen."
    )


def test_datei_hat_die_form_die_die_seite_liest() -> None:
    daten = json.loads(DATEI.read_text(encoding="utf-8"))
    assert set(daten) == {"2025-01"}
    assert set(daten["2025-01"]) == {"v1", "v2"}
    for eintrag in daten["2025-01"].values():
        assert set(eintrag) == {
            "version_alt", "version_neu", "vormonat", "stichtag", "gesamt", "anders", "nur_buchstabe", "beispiel",
            "beleg_sql",
        }  # fmt: skip
        assert eintrag["version_neu"] != eintrag["version_alt"]
        assert 0 < eintrag["nur_buchstabe"] <= eintrag["anders"] <= eintrag["gesamt"]
        assert set(eintrag["beispiel"]) == {"name", "alt", "neu", "anzahl"}
