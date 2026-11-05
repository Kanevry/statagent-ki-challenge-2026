"""/uc4 nimmt denselben Weg wie /uc3/fragen (#176): keine Zahl zu einer Frage, die es nicht versteht."""

from __future__ import annotations

from typing import Any

import pytest

from statagent.db import Verbindung
from statagent.ergebnis import letzter_lauf, monatserster, monatsletzter
from statagent.frage import als_ucantwort, antwort_frage
from statagent.lauf import lauf_ausfuehren
from statagent.uc4 import uc4_antwort

MONAT = "2024-09"


@pytest.fixture
def gerechnet(conn: Verbindung) -> Verbindung:
    lauf_ausfuehren(conn, "2024-08", "v1")
    lauf_ausfuehren(conn, MONAT, "v1")
    return conn


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


def _werte(daten: dict[str, Any]) -> list[object]:
    return [z["wert"] for z in daten["zahlen"]]


# Fängt (#176): Die Branche fehlte in der Abfrage, die Zahl galt für alle Branchen in Wien.
def test_branche_im_alltagswort_wird_gelesen(gerechnet: Verbindung) -> None:
    frage = "Wie viele Beschäftigte arbeiten im Gesundheitswesen im September 2024?"
    daten = uc4_antwort(gerechnet, frage)
    soll = _direkt(gerechnet, " AND oenace = 'Q'")
    assert _werte(daten) == [soll] == _werte(antwort_frage(gerechnet, frage))
    assert soll != _direkt(gerechnet)
    assert "Gesundheits" in daten["zahlen"][0]["bezeichnung"]


# Fängt (#176): Fluktuation ergab den Bestand; die Antwort darf keine Bestandszahl als Antwort nennen.
def test_fluktuation_ist_kein_bestand(gerechnet: Verbindung) -> None:
    daten = uc4_antwort(gerechnet, "Wie hoch ist die Fluktuation im September 2024?")
    bestand = _direkt(gerechnet)
    assert bestand not in _werte(daten)
    assert any(z["bezeichnung"].startswith("Fluktuation") for z in daten["zahlen"])


# Fängt (#176): Eine Frage nach einer Person ergab den Gesamtbestand.
def test_einzelperson_keine_zahl(gerechnet: Verbindung) -> None:
    daten = uc4_antwort(gerechnet, "Wie viele Jobs hatte Person 1234567 im September 2024?")
    assert daten["zahlen"] == [] and daten["belege"] == []
    assert "Einzeldaten" in daten["text"]


# Fängt: Ein Merkmal, das es nicht gibt, oder ein unbekanntes Wort ergab die Zahl ohne diese Einschränkung.
@pytest.mark.parametrize(
    "frage",
    [
        "Wie viele Beschäftigte mit Teilzeit gab es im September 2024?",
        "Wie viele Beschäftigte unter 25 Jahren gab es im September 2024?",
        "Wie viele Beschäftigte gab es im Bergbaubetrieb im September 2024?",
    ],
)
def test_nicht_verstanden_keine_zahl(gerechnet: Verbindung, frage: str) -> None:
    daten = uc4_antwort(gerechnet, frage)
    assert daten["zahlen"] == [] and daten["text"]


# Gegenfall: Was verstanden wird, gibt weiter die richtige Zahl, mit Beleg, gegen eigenes SQL gerechnet.
def test_verstandene_frage_gibt_die_richtige_zahl(gerechnet: Verbindung) -> None:
    daten = uc4_antwort(gerechnet, "Wie viele Beschäftigte gab es im September 2024 in Wien?")
    assert _werte(daten) == [_direkt(gerechnet, " AND region = '9'")]
    assert daten["belege"][daten["zahlen"][0]["beleg"]]["monat"] == MONAT
    assert daten["zahlen"][0]["wert"] != _direkt(gerechnet)


# Fängt: #125 geht verloren: zwei Werte eines Merkmals geben weiter je Wert eine Zahl und die Summe.
def test_mehrere_werte_bleiben_je_wert(gerechnet: Verbindung) -> None:
    daten = uc4_antwort(gerechnet, "Beschäftigte in Wien und Tirol im September 2024")
    wien, tirol = _direkt(gerechnet, " AND region = '9'"), _direkt(gerechnet, " AND region = '7'")
    assert _werte(daten) == [wien, tirol, wien + tirol]


# Fängt: Bei zwei Werten fiel eine weitere Einschränkung still weg, die nur /uc3/fragen liest.
@pytest.mark.parametrize(
    "frage",
    [
        "Beschäftigte in Wien und Tirol im Gesundheitswesen im September 2024",
        "Beschäftigte in Wien und Tirol im Bergbaubetrieb im September 2024",
    ],
)
def test_mehrere_werte_mit_ungelesener_einschraenkung(gerechnet: Verbindung, frage: str) -> None:
    daten = uc4_antwort(gerechnet, frage)
    assert daten["zahlen"] == [] and daten["text"]


# Fängt: Die Antwort verletzt den Vertrag der Kette.
@pytest.mark.parametrize(
    "frage",
    [
        "Wie hoch ist die Fluktuation im September 2024?",
        "Wie hoch ist der Frauenanteil in Wien im September 2024?",
        "Was ist Fluktuation?",
        "Beschäftigte in Wien und Tirol im September 2024",
    ],
)
def test_vertrag_ucantwort(gerechnet: Verbindung, frage: str) -> None:
    antwortform = pytest.importorskip("plattform.antwortform")
    antwortform.UcAntwort.model_validate(uc4_antwort(gerechnet, frage))
    assert set(als_ucantwort(antwort_frage(gerechnet, frage))) >= {"text", "belege", "zahlen"}
