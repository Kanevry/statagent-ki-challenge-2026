"""Form des Fragen-Katalogs und Logik des Urteils, ohne Datenbank (läuft auch in CI)."""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Any

import pytest
from fragen_orakel import SOLLE, Soll, Zeile, katalog_lesen, matrix, urteilen

ORAKEL = Path(__file__).with_name("fragen_orakel.py")


def _zeile(soll: str = "zahl", **optionen: str) -> Zeile:
    return Zeile("T1", ("zeit:monat",), soll, ("2025-03",), {}, optionen, "Frage?")


def _antwort(text: str, *werte: float) -> dict[str, Any]:
    return {"text": text, "zahlen": [{"bezeichnung": "x", "wert": w} for w in werte]}


def test_katalog_ist_vollstaendig_lesbar() -> None:
    zeilen = katalog_lesen()
    assert len(zeilen) >= 150
    assert len({z.id for z in zeilen}) == len(zeilen)
    assert {z.soll for z in zeilen} <= SOLLE
    achsen = {a for z in zeilen for a in z.achsen}
    for pflicht in ("zeit:winter", "zeit:teilweise", "merkmal:branche", "form:injection", "kreuz:wechsel"):
        assert pflicht in achsen
    # Eine Zahl als Soll braucht Monate, sonst gibt es nichts zu vergleichen.
    assert all(z.monate for z in zeilen if z.soll == "zahl")


# Fängt: Das Orakel läse Werte über den geprüften Code und bestätigte ihn nur.
def test_orakel_importiert_nichts_aus_statagent() -> None:
    baum = ast.parse(ORAKEL.read_text(encoding="utf-8"))
    namen = [
        alias.name for knoten in ast.walk(baum) if isinstance(knoten, ast.Import) for alias in knoten.names
    ] + [knoten.module or "" for knoten in ast.walk(baum) if isinstance(knoten, ast.ImportFrom)]
    assert not [n for n in namen if n.startswith(("statagent", "plattform"))]


@pytest.mark.parametrize(
    ("zeile", "soll", "antwort", "erwartet"),
    [
        (_zeile(), Soll(pflicht={"m": 100.0}), _antwort("Am 31.03.2025 gab es 100.", 100.0), "richtig"),
        # Stille andere Zahl: die Kernfrage dieses Katalogs.
        (_zeile(), Soll(pflicht={"m": 100.0}), _antwort("Es gab 200.", 200.0), "falsch"),
        (_zeile(), Soll(pflicht={"m": 100.0}), _antwort("Zwei Zahlen.", 100.0, 7.0), "falsch"),
        (_zeile(), Soll(pflicht={"m": 100.0}), _antwort("Bitte einen Monat nennen. Welchen?"), "rueckfrage"),
        (_zeile(), Soll(pflicht={"m": 100.0}), _antwort("Das geht nicht."), "absage"),
        (_zeile("absage"), Soll(), _antwort("Das geht nicht."), "richtig"),
        (_zeile("absage"), Soll(), _antwort("Es gab 5.", 5.0), "falsch"),
        (_zeile("rueckfrage"), Soll(), _antwort("Welcher Monat?"), "richtig"),
        (_zeile("absage"), Soll(), _antwort("Es waren 388.650 Personen."), "falsch"),
        (_zeile("definition"), Soll(), _antwort("Fluktuation heißt Zu- und Abgänge."), "richtig"),
    ],
)
def test_urteil(zeile: Zeile, soll: Soll, antwort: dict[str, Any], erwartet: str) -> None:
    assert urteilen(zeile, soll, antwort).urteil == erwartet


# Fängt: Die Zahlen stimmen, aber der Text nennt eine andere große Zahl.
def test_zahl_im_text_muss_zur_frage_gehoeren() -> None:
    urteil = urteilen(_zeile(), Soll(pflicht={"m": 100.0}), _antwort("Es gab 388.650.", 100.0))
    assert urteil.urteil == "falsch" and "388.650" in urteil.grund


def test_fortschreibung_im_text_ist_keine_antwort() -> None:
    text = "Es gab 100. Im März sind 1.234 Beschäftigungsverhältnisse übernommen."
    assert urteilen(_zeile(), Soll(pflicht={"m": 100.0}), _antwort(text, 100.0)).urteil == "richtig"


# Fängt (Owner 05.11., Winter 2025): Die Station zeigt nur die Erklärung der Frage, keine Zahl.
def test_kern_ohne_zahl_ist_ein_mangel() -> None:
    kern = "Winter 2025 heißt hier Dezember 2024 bis Februar 2025."
    mit_zahl = urteilen(_zeile(), Soll(pflicht={"m": 100.0}), _antwort(f"{kern} Es gab 100.", 100.0), kern)
    assert mit_zahl.urteil == "richtig" and mit_zahl.mangel.startswith("Kern ohne Zahl")
    ohne_zahl = urteilen(_zeile("absage"), Soll(), _antwort(f"{kern} Das geht nicht."), kern)
    assert ohne_zahl.mangel.startswith("Kern nennt nur die Definition")


def test_matrix_nennt_falsch_zuerst() -> None:
    zeile = _zeile()
    text = matrix(
        [
            (zeile, "uc3", urteilen(zeile, Soll(pflicht={"m": 100.0}), _antwort("x", 200.0))),
            (zeile, "uc4", urteilen(zeile, Soll(pflicht={"m": 100.0}), _antwort("x", 100.0))),
        ]
    )
    assert text.startswith("## Falsch: 1 von 2 Antworten")
    assert text.index("Falsch") < text.index("Matrix je Achse")
    assert "| alle | uc3 | 1 | 0 | 0 | 0 | 1 | 0 |" in text
