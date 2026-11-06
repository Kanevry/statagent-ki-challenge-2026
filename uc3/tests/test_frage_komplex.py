"""Komplexere Fragen ohne Datenbank: Lesen der Rangfrage, Wortgrenzen und Fragen zur Anwendung."""

from __future__ import annotations

import pytest

from statagent.frage import _rang_lesen, nicht_auswertbar
from statagent.frage_app import _AENDERUNG, _MINISTERIUM, _WAS_IST, BEGRIFFE


# Fängt: „gehalt“ traf „an-gehalt-en“, die Antwort war „Einkommen sind nicht in den Daten“.
@pytest.mark.parametrize(
    "frage",
    [
        "Warum ist Oktober 2025 angehalten?",
        "Wurde die Regel eingehalten im März 2025?",
        "Wer ist hereinkommen im Mai 2025",
    ],
)
def test_wortteil_ist_kein_einkommen(frage: str) -> None:
    assert nicht_auswertbar(frage) is None


@pytest.mark.parametrize(
    "frage",
    [
        "Gehalt in Wien im Mai 2025",
        "Monatslohn im Mai 2025",
        "Löhne im Bau",
        "Monatsgehalt der Frauen",
        "Einkommen 2025",
    ],
)
def test_einkommen_bleibt_abgesagt(frage: str) -> None:
    assert "Einkommen" in str(nicht_auswertbar(frage))


# Fängt: Ohne „welche“ fiele „die meisten“ weg, und „die meisten Frauen in Wien“ wäre die Zahl für alle Frauen in Wien.
@pytest.mark.parametrize(
    "frage",
    [
        "Die meisten Frauen in Wien im Juli 2026",
        "Welche Branche im Juli 2026",
        "Welche Branche hat die höchste Fluktuation im Juli 2026?",
    ],
)
def test_rangfrage_nur_mit_welche_und_rangwort(frage: str) -> None:
    assert _rang_lesen(frage) is None


@pytest.mark.parametrize(
    ("frage", "umgeschrieben", "groesste"),
    [
        (
            "Welches Bundesland hat die meisten Beschäftigten im Juli 2026?",
            "hat Beschäftigten im Juli 2026 je Bundesland",
            True,
        ),
        (
            "In welchem Bundesland arbeiten die wenigsten Männer im Mai 2025?",
            "arbeiten Männer im Mai 2025 je Bundesland",
            False,
        ),
        ("Welche Branche hat am meisten Frauen im Juli 2026?", "hat Frauen im Juli 2026 je Branche", True),
    ],
)
def test_rangfrage_wird_zur_aufteilung(frage: str, umgeschrieben: str, groesste: bool) -> None:
    rang = _rang_lesen(frage)
    assert rang is not None and rang.frage == umgeschrieben and rang.groesste is groesste


# Fängt: „Was hat sich im Juli 2026 geändert?“ meint die Zahl, „Beschäftigte im Ministerium“ eine Branche.
def test_datenfragen_bleiben_beim_zahlenweg() -> None:
    assert _MINISTERIUM.search("Beschäftigte im Ministerium im Juli 2026") is None
    assert _MINISTERIUM.search("Wie viele Personen gehen an das Ministerium?")
    assert _AENDERUNG.search("Wie hat sich die Zahl der Frauen verändert?") is None


@pytest.mark.parametrize(
    "frage", ["Was ist ein Regelsatz?", "Was heißt angehalten?", "Was ist die SVS?", "Was bedeutet vorläufig"]
)
def test_begriffe_der_anwendung(frage: str) -> None:
    was = _WAS_IST.match(frage)
    assert was and any(m.search(was.group(1).lower()) for m, _ in BEGRIFFE)
