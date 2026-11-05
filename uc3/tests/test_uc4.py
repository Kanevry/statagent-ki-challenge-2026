"""UC3-Adapter für UC4 (#106): Frage lesen ohne Modell, Zahl aus stat.stat_beschaeftigte, Beleg je Zahl."""

from __future__ import annotations

import subprocess
import sys
from typing import Any

import pytest

from statagent.db import Verbindung
from statagent.ergebnis import letzter_lauf, monatserster, monatsletzter
from statagent.uc4 import antwort_daten, monat_lesen

MONAT = "2024-08"  # erste Fixture-Lieferung
EINZELDATEN = ("person_id", "vvh_id", "geburtsdatum", "roh.", "bereinigt.")


def _lauf(conn: Verbindung) -> None:
    from statagent import lauf

    lauf.lauf_ausfuehren(conn, MONAT, regelsatz="v1", gestartet_von=None)


def _direkt(conn: Verbindung, bedingung: str = "", parameter: tuple[object, ...] = ()) -> int:
    stand = letzter_lauf(conn, MONAT)
    assert stand is not None
    zeile = conn.execute(
        (
            "SELECT COALESCE(sum(wert), 0) AS wert FROM stat.stat_beschaeftigte WHERE regelsatz = 'v1'"
            " AND regelstand = %s AND zeitraum_art = 'Stichtag' AND variable = 'Beschaeftigungsverhaeltnisse'"
            " AND zeitraum_bis BETWEEN %s AND %s" + bedingung
        ).encode(),
        (stand.regelstand, monatserster(MONAT), monatsletzter(MONAT), *parameter),
    ).fetchone()
    assert zeile is not None
    return int(str(zeile["wert"]))


def _belege_gueltig(daten: dict[str, Any]) -> None:
    for zahl in daten["zahlen"]:
        assert 0 <= zahl["beleg"] < len(daten["belege"])


# Fängt: Monatsname, Abkürzung oder Zahlform wird falsch oder gar nicht als JJJJ-MM erkannt.
@pytest.mark.parametrize(
    ("frage", "monat"),
    [
        ("Wie viele Beschäftigte im März 2025?", "2025-03"),
        ("Beschäftigte 2025-03", "2025-03"),
        ("Stand 3/2025 bitte", "2025-03"),
        ("Jänner 2025 in Wien", "2025-01"),
        ("im Dez. 2024", "2024-12"),
        ("Wie viele Beschäftigte gibt es?", None),
        ("im 2025-13", None),
    ],
)
def test_monat_lesen(frage: str, monat: str | None) -> None:
    assert monat_lesen(frage) == monat


# Fängt: Monatsname und JJJJ-MM liefern verschiedene Zahlen oder weichen von der Summe der Aggregattabelle ab.
def test_monatsformen_gleich_der_direkten_summe(conn: Verbindung) -> None:
    _lauf(conn)
    als_name = antwort_daten(conn, "Wie viele Beschäftigungsverhältnisse gab es im August 2024?")
    als_iso = antwort_daten(conn, "Beschäftigte 2024-08")
    assert als_name["zahlen"][0]["wert"] == als_iso["zahlen"][0]["wert"] == _direkt(conn) > 0
    assert als_name["modell"] is None and als_name["uc"] == "uc3"
    assert "vorläufig" in als_name["text"] or "endgültig" in als_name["text"]


# Fängt: Ausprägung oder Gliederung wird nicht aus der Klassifikation gelesen, Beleg-Index zeigt ins Leere,
# oder der SQL-Text enthält Einzeldaten-Spalten.
def test_auspraegung_gliederung_beleg_und_sql(conn: Verbindung) -> None:
    _lauf(conn)
    wien = antwort_daten(conn, "Beschäftigte in Wien im August 2024")
    assert wien["zahlen"][0]["wert"] == _direkt(conn, " AND region = %s", ("9",))
    gesamt = _direkt(conn)
    je_land = antwort_daten(conn, "Beschäftigte nach Bundesland, August 2024")
    assert len(je_land["zahlen"]) > 1
    assert sum(z["wert"] for z in je_land["zahlen"]) == gesamt
    for daten in (wien, je_land):
        _belege_gueltig(daten)
        beleg = daten["belege"][0]
        assert beleg["quelle"] == "stat.stat_beschaeftigte" and beleg["monat"] == MONAT
        assert beleg["ref"].startswith("meta.lauf/")
        assert not any(spalte in beleg["sql"] for spalte in EINZELDATEN)


# Fängt: Frage ohne Monat oder Monat ohne Lauf wirft, statt leer zu antworten (der Router liefe nicht weiter).
def test_ohne_monat_oder_lauf_leer(conn: Verbindung) -> None:
    for frage in ("Wie viele Beschäftigte gibt es?", "Beschäftigte im Dezember 2030"):
        daten = antwort_daten(conn, frage)
        assert daten["zahlen"] == [] and daten["belege"] == [] and daten["text"]


# Fängt: der Adapter zieht plattform.llm mit (Regel R2, UC3 rechnet ohne Modell).
def test_uc4_importiert_kein_llm() -> None:
    lauf = subprocess.run(
        [sys.executable, "-c", "import sys, statagent.uc4; print('plattform.llm' in sys.modules)"],
        capture_output=True,
        text=True,
        timeout=60,
        check=True,
    )
    assert lauf.stdout.strip() == "False"


# Fängt: das dict passt nicht zum Vertrag UcAntwort (#96, läuft erst nach dem Merge von !30).
def test_vertrag_ucantwort(conn: Verbindung) -> None:
    antwortform = pytest.importorskip("plattform.antwortform")
    _lauf(conn)
    for frage in ("Frauen im August 2024", "nach Geschlecht 2024-08", "ohne Monat"):
        antwortform.UcAntwort.model_validate(antwort_daten(conn, frage))
