"""Erklär-Antworten, Wortgrenzen und das Lesen der Rangfrage ohne Datenbank."""

from __future__ import annotations

import pytest

from statagent.frage import _BEISPIEL_DA, _Rang, _rang_anwenden, _rang_lesen, nicht_auswertbar
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


# Fängt: Ohne „welche“ fiele „die meisten“ weg, und „die meisten Frauen in Wien“ wäre die Zahl für alle Frauen in Wien.
# Die Vorführfragen dürfen nie zur Rangfrage umgeschrieben werden.
@pytest.mark.parametrize(
    "frage",
    [
        "Die meisten Frauen in Wien im Juli 2026",
        "Welche Branche im Juli 2026",
        "Welche Branche hat die höchste Fluktuation im Juli 2026?",
        "Welches Bundesland hat die meisten Beschäftigten nach Branche im Juli 2026?",
        "Zeigen Sie mir die Zeitreihe der Beschäftigten, jeweils zum Monatsletzten.",
        "Wie viele Männer und Frauen sind im August 2024 je Bundesland beschäftigt?",
        "Männer und Frauen im Juli 2026",
        "Wie hoch ist die Fluktuation je Wirtschaftsbereich im Oktober 2024?",
        "Wie viele Beschäftigte gab es im März 2025 in Wien im Gesundheits- und Sozialwesen?",
        "Beschäftigte nach Branche im Juli 2026",
        "Was ist ÖNACE R?",
        "Zeitreihe Bau 2025",
        "Welches Bundesland hat die höchste Zahl?",
        # Fängt: „zweitmeisten“ und „allermeisten“ wurden zu „zweit“ und „aller“ und abgesagt.
        "Welches Bundesland hat die zweitmeisten Beschäftigten im Juli 2026?",
        "Welches Bundesland hat die allermeisten Beschäftigten im Juli 2026?",
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


# Fängt: Bei Männern und Frauen hieße die Summenzeile „Männer, Alle Bundesländer“ und gewänne die Rangfolge.
@pytest.mark.parametrize(
    "frage",
    [
        "Welches Bundesland hat die meisten Männer und Frauen im Juli 2026?",
        "Welches Bundesland hat den höchsten Frauenanteil im Juli 2026?",
    ],
)
def test_rangfrage_nicht_fuer_kreuzung_und_anteil(frage: str) -> None:
    assert _rang_lesen(frage) is None


# Fängt: Eine Summen- oder „unbekannt“-Zeile der Tabelle wird Sieger der Rangfolge.
def test_summenzeile_wird_nie_sieger() -> None:
    zeilen = [
        ("Beschäftigungsverhältnisse, Alle Bundesländer", 900),
        ("Beschäftigungsverhältnisse, Bundesland unbekannt", 500),
        ("Beschäftigungsverhältnisse, Tirol", 20),
        ("Beschäftigungsverhältnisse, Wien", 300),
    ]
    daten = {
        "typ": "bestand",
        "text": "Tabelle.",
        "stand": [{"monat": "2026-07"}],
        "zahlen": [{"bezeichnung": b, "wert": w} for b, w in zeilen],
    }
    rang = _Rang("Beschäftigte im Juli 2026 je Bundesland", True, "Welches Bundesland", "meisten")
    antwort = _rang_anwenden(None, daten, rang)  # type: ignore[arg-type]  # ein Monat: keine Abfrage
    assert antwort["text"].startswith("Am meisten im Juli 2026: Wien mit 300 Beschäftigungsverhältnissen.")
    assert [z["wert"] for z in antwort["zahlen"]][:2] == [300, 20]


# Fängt: Gleichstand an der Spitze nennt nur eine Gruppe; der Zusatz zu „unbekannt“ ist verständlich.
def test_gleichstand_nennt_beide_gruppen() -> None:
    zeilen = [
        ("Beschäftigungsverhältnisse, Tirol", 300),
        ("Beschäftigungsverhältnisse, Bundesland unbekannt", 500),
        ("Beschäftigungsverhältnisse, Wien", 300),
        ("Beschäftigungsverhältnisse, Salzburg", 20),
    ]
    daten = {
        "typ": "bestand",
        "text": "Tabelle.",
        "stand": [{"monat": "2026-07"}],
        "zahlen": [{"bezeichnung": b, "wert": w} for b, w in zeilen],
    }
    rang = _Rang("Beschäftigte im Juli 2026 je Bundesland", True, "Welches Bundesland", "meisten")
    satz = _rang_anwenden(None, daten, rang)["antwortsatz"]  # type: ignore[arg-type]  # ein Monat: keine Abfrage
    assert "Tirol" in satz and "Wien" in satz and "Salzburg" not in satz
    assert satz.endswith("Beschäftigungsverhältnisse ohne bekanntes Bundesland zählen hier nicht mit.")


# Fängt: Die Rückfrage über ein Jahr bot ein Beispiel ohne „unter 25“ an, also eine Zahl für eine andere Gruppe.
def test_rueckfrage_ueber_jahr_ohne_beispiel_bei_alter() -> None:
    rang = _rang_lesen("Welches Bundesland hat die meisten Beschäftigten unter 25 im Jahr 2025?")
    assert rang is not None
    daten = {"typ": "rueckfrage", "text": "Für welchen Monat?", "stand": [], "zahlen": []}
    antwort = _rang_anwenden(None, daten, rang)  # type: ignore[arg-type]  # Alter: ohne Beispiel, keine Abfrage
    assert antwort["typ"] == "rueckfrage"
    assert antwort["text"] == "Die Rangfolge gibt es je Monat. Für welchen Monat möchten Sie sie?"
