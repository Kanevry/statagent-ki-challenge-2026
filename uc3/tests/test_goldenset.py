"""Golden Set 08/2024: 2.880 Zahlenzellen des Beispielberichts gegen die Ergebnisse des Monatslaufs."""

from __future__ import annotations

from collections.abc import Iterator

import psycopg
import pytest

from statagent import db, konfig
from statagent.eichung import Spec, bericht_text, eichen, soll_zellen
from statagent.ergebnis import monatswerte

pytestmark = pytest.mark.daten

LIEFERUNG = "2024-08"


@pytest.fixture(scope="module")
def conn() -> Iterator[db.Verbindung]:
    try:
        verbindung = db.verbinden()
    except psycopg.OperationalError as fehler:
        pytest.skip(f"Datenbank nicht erreichbar: {type(fehler).__name__}")
    yield verbindung
    verbindung.close()


def _bericht_vorhanden() -> None:
    if not konfig.beispielbericht().is_file():
        pytest.skip("Beispielbericht (Startpaket) fehlt")


def test_soll_liest_tab1_gesamtwerte() -> None:
    _bericht_vorhanden()
    soll = {(z.blatt, z.zelle): z for z in soll_zellen()}
    assert soll[("Tab1", "C9")].soll == 392236
    assert soll[("Tab1", "D9")].soll == 211603
    assert soll[("Tab1", "E9")].soll == 180633
    assert soll[("Tab1", "C9")].spec == Spec(
        "region", "Österreich", "alle", ("Arbeiter", "Angestellte", "Beamte"), None
    )


def test_soll_hat_2880_zellen() -> None:
    _bericht_vorhanden()
    assert len(soll_zellen()) == 2880


def test_goldenset_2880_zellen_ohne_abweichung(conn: db.Verbindung) -> None:
    _bericht_vorhanden()
    if not monatswerte(conn, LIEFERUNG):
        pytest.skip("Lauf 2024-08 fehlt (keine Ergebniszellen)")
    ergebnis = eichen(conn, LIEFERUNG)
    assert ergebnis.anzahl == 2880, bericht_text(ergebnis)
    assert ergebnis.abweichungen == [], bericht_text(ergebnis)
