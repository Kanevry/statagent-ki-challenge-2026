"""Unbekannte Wörter ergeben keine Zahl (#186)."""

from __future__ import annotations

import pytest

from statagent.db import Verbindung
from statagent.frage import antwort_frage
from statagent.lauf import lauf_ausfuehren
from statagent.woerter import unbekanntes_wort


@pytest.mark.parametrize(
    ("frage", "erkannt", "erwartet"),
    [
        ("Wie viele Beschäftigte gab es im März 2025 in Wien?", ["wien"], None),
        ("Bitte zeigen Sie mir die Zeitreihe der Beschäftigten", [], None),
        ("Wie viele Beschäftigte mit Kindern gab es im März 2025?", [], "Kindern"),
        ("Wie viele Betriebe gab es im März 2025?", [], "Betriebe"),
        ("How many employees were there in März 2025?", [], "How"),
        ("Beschäftigte außer Wien im März 2025", ["wien"], "außer"),
        ("Beschäftigte ab 50 im März 2025", [], "50"),
        ("Wie viele Beschäftigte gab es am 31. März 2025?", [], None),
        ("Gab es im März 2025 über 20.000 Beschäftigte?", [], None),
        ("Gab es im März 2025 über 10000 Beschäftigte?", [], None),
        ("Wie viele Arbeitslose gab es im März 2025?", [], "Arbeitslose"),
    ],
)
def test_unbekanntes_wort(frage: str, erkannt: list[str], erwartet: str | None) -> None:
    assert unbekanntes_wort(frage, erkannt) == erwartet


# Fängt (#186): Eine Einschränkung, die das Programm nicht kennt, fiel still weg, die Zahl galt für alle.
@pytest.mark.parametrize(
    "frage",
    [
        "Wie viele Beschäftigte mit Kindern gab es im September 2024?",
        "Wie viele Betriebe gab es im September 2024 in Wien?",
        "Beschäftigte mit Ausbildung im September 2024",
        "Beschäftigte außer Wien im September 2024",
        "How many employees in September 2024?",
        "Was kostet eine Pizza?",
        "Wie viele Personen hatten im September 2024 mehr als ein Beschäftigungsverhältnis?",
        "Wie viele Bundesländer hatten im September 2024 über 1000 Beschäftigte?",
        "Wie viele Beschäftigte gab es im Monat nach dem August 2024?",
        "Wie viele Beschäftigte gab es vor September 2024?",
        "Gab es über 50 Betriebe in Wien im September 2024?",
        "Wie hoch war der Bestand zum Jahresende?",
        "Wie viele Beschäftigte gibt es pro Jahr?",
        "Beschäftigte im September 2024 nach v2",
        "Beschäftigte in ÖNACE Z im September 2024",
        "Welches Bundesland hat die höchste Zahl im September 2024?",
        "Welchen Anteil hat Wien an allen Beschäftigten im September 2024?",
        "42",
    ],
)
def test_keine_zahl_bei_unbekanntem_wort(conn: Verbindung, frage: str) -> None:
    lauf_ausfuehren(conn, "2024-08", "v1")
    lauf_ausfuehren(conn, "2024-09", "v1")
    daten = antwort_frage(conn, frage)
    assert daten["zahlen"] == [] and daten["belege"] == []


def test_einwohner_meinen_das_bundesland(conn: Verbindung) -> None:
    lauf_ausfuehren(conn, "2024-08", "v1")
    lauf_ausfuehren(conn, "2024-09", "v1")
    wiener = antwort_frage(conn, "Wie viele Wiener arbeiteten im September 2024?")
    wien = antwort_frage(conn, "Wie viele Beschäftigte arbeiteten im September 2024 in Wien?")
    assert wiener["zahlen"][0]["wert"] == wien["zahlen"][0]["wert"]


# Fängt: „gegenüber dem Vormonat“ zeigte nur den genannten Monat und ließ den Vergleich still weg.
def test_vergleich_zum_vormonat_zeigt_beide_monate(conn: Verbindung) -> None:
    lauf_ausfuehren(conn, "2024-08", "v1")
    lauf_ausfuehren(conn, "2024-09", "v1")
    daten = antwort_frage(conn, "Beschäftigte im September 2024 im Vergleich zum Vormonat")
    monate = [z["bezeichnung"] for z in daten["zahlen"]]
    assert any("August 2024" in m for m in monate) and any("September 2024" in m for m in monate)


# Fängt: „März und Juli“ zeigte auch die Monate dazwischen.
def test_aufzaehlung_nur_die_genannten_monate(conn: Verbindung) -> None:
    for monat in ("2024-08", "2024-09", "2024-10"):
        lauf_ausfuehren(conn, monat, "v1")
    daten = antwort_frage(conn, "Beschäftigte im August 2024 und im Oktober 2024")
    namen = " ".join(z["bezeichnung"] for z in daten["zahlen"])
    assert "August 2024" in namen and "Oktober 2024" in namen and "September 2024" not in namen


# Fängt (Blind-Runde 3): „Beamtinnen und Beamte“ zählte nur die Frauen.
def test_doppelnennung_meint_alle(conn: Verbindung) -> None:
    lauf_ausfuehren(conn, "2024-08", "v1")
    alle = antwort_frage(conn, "Wie viele Beamte gab es im August 2024?")
    doppelt = antwort_frage(conn, "Wie viele Beamtinnen und Beamte gab es im August 2024?")
    assert doppelt["zahlen"][0]["wert"] == alle["zahlen"][0]["wert"]


# Fängt (Blind-Runde 3): „Frauen und Beamte“ wurde still als Schnittmenge gerechnet.
def test_zwei_merkmale_mit_und_fragt_zurueck(conn: Verbindung) -> None:
    lauf_ausfuehren(conn, "2024-08", "v1")
    daten = antwort_frage(conn, "Wie viele Frauen und Beamte gab es im August 2024?")
    assert daten["zahlen"] == [] and "?" in daten["text"]


# Fängt (Blind-Runde 3): „zuletzt verändert“ nannte nur den Stand des jüngsten Monats.
def test_veraenderung_zeigt_zwei_monate(conn: Verbindung) -> None:
    lauf_ausfuehren(conn, "2024-08", "v1")
    lauf_ausfuehren(conn, "2024-09", "v1")
    daten = antwort_frage(conn, "Wie hat sich die Beschäftigung zuletzt verändert?")
    namen = " ".join(z["bezeichnung"] for z in daten["zahlen"])
    assert "August 2024" in namen and "September 2024" in namen


# Fängt (Katalog): „in Wien, aktuell“ und „in Wien, nach Geschlecht“ galten hinter dem Komma als unbekannter Ort.
@pytest.mark.parametrize(
    "frage",
    [
        "Die Beamten in Wien, aktuell",
        "Beschäftigte in Wien, nach Geschlecht aufgeschlüsselt, im September 2024",
    ],
)
def test_bekanntes_wort_hinter_dem_komma(conn: Verbindung, frage: str) -> None:
    lauf_ausfuehren(conn, "2024-08", "v1")
    lauf_ausfuehren(conn, "2024-09", "v1")
    assert antwort_frage(conn, frage)["zahlen"]


# Fängt (ui-regie, Bank): Im v2-Weg fiel „ohne Kinder“ still weg, die Antwort war die Zahl aller Frauen.
@pytest.mark.parametrize(
    "frage",
    [
        "Frauen ohne Kinder im September 2024",
        "Frauen ohne Kinder im September 2024 nach v2",
        "Beschäftigte mit Kindern im September 2024 nach v2",
        "Betriebe im September 2024 nach v2",
    ],
)
def test_unbekanntes_wort_auch_im_v2_weg(conn: Verbindung, frage: str) -> None:
    for monat in ("2024-08", "2024-09"):
        lauf_ausfuehren(conn, monat, "v1")
        lauf_ausfuehren(conn, monat, "v2")
    assert antwort_frage(conn, frage)["zahlen"] == []


def test_regelsatz_angabe_ist_kein_unbekanntes_wort() -> None:
    assert unbekanntes_wort("Beschäftigte im März 2025 im Regelsatz v1", []) is None
    assert unbekanntes_wort("Beschäftigte über das ganze Monat März 2025", []) is None


# Fängt: Das „1“ in „v1“ galt als lose Zahl, „im Regelsatz v1“ bekam die Absage.
def test_ziffer_am_wort_ist_keine_lose_zahl() -> None:
    assert unbekanntes_wort("Beschäftigte im Regelsatz v1 im März 2025", []) is None
    assert unbekanntes_wort("Beschäftigte ab 50 im März 2025", []) == "50"
