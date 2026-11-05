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
        ("Wie viele Beschäftigte mit Kindern gab es im März 2025?", [], "kindern"),
        ("Wie viele Betriebe gab es im März 2025?", [], "betriebe"),
        ("How many employees were there in März 2025?", [], "how"),
        ("Beschäftigte außer Wien im März 2025", ["wien"], "außer"),
        ("Wie viele Arbeitslose gab es im März 2025?", [], "arbeitslose"),
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
        "Beschäftigte außer Wien im September 2024",
        "How many employees in September 2024?",
        "Was kostet eine Pizza?",
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
