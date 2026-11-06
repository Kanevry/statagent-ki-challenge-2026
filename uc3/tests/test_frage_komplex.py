"""Erklär-Antworten und Wortgrenzen ohne Datenbank."""

from __future__ import annotations

import pytest

from statagent.frage import _BEISPIEL_DA, nicht_auswertbar
from statagent.frage_app import _WARUM, _WAS_IST, BEGRIFFE, _ohne_monat


# Fängt: „gehalt“ traf „an-gehalt-en“, die Antwort war „Einkommen sind nicht in den Daten“.
@pytest.mark.parametrize(
    "frage", ["Warum ist Oktober 2025 angehalten?", "Wurde die Regel eingehalten im März 2025?"]
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


# Fängt: Eine weitere Einschränkung fiele still weg, die Antwort gälte für den ganzen Monat.
@pytest.mark.parametrize(
    ("frage", "passt"),
    [
        ("Warum ist Oktober 2025 angehalten?", True),
        ("Warum ist der Monat Oktober 2025 angehalten?", True),
        ("Warum ist der Himmel im Oktober 2025 blau?", False),
        ("Warum ist Wien im Oktober 2025 angehalten?", False),
    ],
)
def test_warumfrage_nur_ohne_weitere_einschraenkung(frage: str, passt: bool) -> None:
    assert (_WARUM.fullmatch(_ohne_monat(frage)) is not None) is passt


@pytest.mark.parametrize(
    ("frage", "passt"),
    [
        ("Was ist ein Regelsatz?", True),
        ("Was heißt angehalten?", True),
        ("Was ist ein Regelsatz in Wien im März 2025?", False),
        ("Was ist Regelsatz v2?", False),
    ],
)
def test_begriffe_nur_als_ganze_frage(frage: str, passt: bool) -> None:
    was = _WAS_IST.match(frage)
    assert (was is not None and any(m.search(was.group(1).lower()) for m, _ in BEGRIFFE)) is passt


def test_vorhandenes_beispiel_verhindert_zweiten_vorschlag() -> None:
    assert _BEISPIEL_DA.search("Zum Beispiel „Frauen im Juli 2026“.")
    assert _BEISPIEL_DA.search("Zum Beispiel „Was ist ÖNACE C?“.")
    assert _BEISPIEL_DA.search("alle auf einmal mit „je Bundesland“.") is None
