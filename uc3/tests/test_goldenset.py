"""Golden Set 08/2024: 2.880 Zahlenzellen des Beispielberichts gegen die Ergebnisse des Monatslaufs.

Läuft nur mit dem Marker ``daten`` (echte Lieferungen in PostgreSQL). Dann ist eine fehlende Datenbank oder ein
fehlender Beispielbericht ein Fehler, kein Überspringen. Der Test rechnet den Lauf 2024-08 selbst, in einer
Transaktion, die am Ende zurückgerollt wird: Er hinterlässt keine Spuren in der Datenbank.
"""

from __future__ import annotations

from collections.abc import Iterator

import psycopg
import pytest

from statagent import db, konfig
from statagent.eichung import Spec, bericht_text, eichen, soll_zellen
from statagent.lauf import lauf_ausfuehren

pytestmark = pytest.mark.daten

LIEFERUNG = "2024-08"


@pytest.fixture(scope="module")
def conn() -> Iterator[db.Verbindung]:
    try:
        verbindung = db.verbinden()
    except psycopg.OperationalError as fehler:
        pytest.fail(f"Datenbank nicht erreichbar ({type(fehler).__name__}); UC3_DATABASE_URL prüfen")
    yield verbindung
    verbindung.close()


def _bericht_vorhanden() -> None:
    if not konfig.beispielbericht().is_file():
        pytest.fail(f"Beispielbericht fehlt: {konfig.beispielbericht()} (STATAGENT_STARTPAKET setzen)")


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


class _Zurueckrollen(Exception):
    """Beendet die Test-Transaktion ohne Wirkung."""


def test_goldenset_2880_zellen_ohne_abweichung(conn: db.Verbindung) -> None:
    # Fängt: jede Abweichung der Zählung (Stichtag, Dubletten, Quellzuordnung, Alter, Kategorie) gegenüber dem
    # Beispielbericht des Veranstalters und eine Abrechnung, die Sätze verliert.
    _bericht_vorhanden()
    try:
        with conn.transaction():
            lauf = lauf_ausfuehren(conn, LIEFERUNG, "v1")
            assert (lauf.gelesen, lauf.gezaehlt, lauf.nicht_gezaehlt, lauf.ausgeschlossen) == (
                392284,
                392236,
                48,
                0,
            )
            ergebnis = eichen(conn, LIEFERUNG)
            assert ergebnis.anzahl == 2880, bericht_text(ergebnis)
            assert ergebnis.abweichungen == [], bericht_text(ergebnis)
            raise _Zurueckrollen
    except _Zurueckrollen:
        pass
