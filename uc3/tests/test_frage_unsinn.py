"""Keine Zahl zu Unsinn und zu Fragen, die nichts mit den Daten zu tun haben (ui-regie-e6, b-uc4-99, #176)."""

from __future__ import annotations

import pytest

from statagent.db import Verbindung
from statagent.frage import antwort_frage
from statagent.lauf import lauf_ausfuehren


@pytest.fixture
def gerechnet(conn: Verbindung) -> Verbindung:
    lauf_ausfuehren(conn, "2024-08", "v1")
    return conn


# Fängt: Unsinn ergab „Ohne Zeitangabe zeigen wir den jüngsten Monat“ und den Bestand; die UC4-Kette lief weiter.
@pytest.mark.parametrize(
    "frage",
    [
        "asdf qwer zzz blub",
        "Hallo",
        "Wie wird das Wetter morgen?",
        "Wer ist der Bundeskanzler?",
        "?",
        "asdf im August 2024",
    ],
)
def test_unsinn_absage_ohne_zahl(gerechnet: Verbindung, frage: str) -> None:
    daten = antwort_frage(gerechnet, frage)
    assert daten["zahlen"] == [] and daten["belege"] == []
    assert "StatAgent beantwortet" in daten["text"] and "Ohne Zeitangabe" not in daten["text"]


# Fängt: Englisch und Tippfehler bekamen die Rückfrage „für 2025 gibt es also zwölf Werte“, obwohl ein Monat gemeint ist.
@pytest.mark.parametrize(
    "frage",
    ["How many employees were there in Vienna in March 2025?", "Beschäftigte in Wein im Märtz 2025"],
)
def test_englisch_und_tippfehler_keine_jahr_rueckfrage(gerechnet: Verbindung, frage: str) -> None:
    daten = antwort_frage(gerechnet, frage)
    assert daten["zahlen"] == [] and "zwölf Werte" not in daten["text"]


# Gegenfall: Was StatAgent zählt, zeigt weiter eine Zahl, auch ohne Monat.
@pytest.mark.parametrize(
    "frage",
    [
        "Wie viele Beschäftigte gibt es?",
        "Wie viele Frauen arbeiten in Wien?",
        "Wien",
        "Frauen",
        "Beschäftigte nach Bundesland",
        "August 2024",
        "im August 2024",
        "Wien im August 2024",
        "Jobs im August 2024",
    ],
)
def test_frage_mit_bezug_gibt_zahl(gerechnet: Verbindung, frage: str) -> None:
    daten = antwort_frage(gerechnet, frage)
    assert daten["zahlen"], daten["text"]


# Gegenfall: Eine bloße Jahreszahl bleibt die Rückfrage (#74 AC2).
@pytest.mark.parametrize("frage", ["Beschäftigte 2025", "2025"])
def test_jahr_bleibt_rueckfrage(gerechnet: Verbindung, frage: str) -> None:
    assert "zwölf Werte" in antwort_frage(gerechnet, frage)["text"]
