"""Datengebundene Jury-Probe (#139), nur lokal mit allen 24 Lieferungen und v1-Läufen.

Die Sollkategorien sind fachlich festgelegt, nicht aus den Antworten abgeleitet.
Die echte Datenbank kommt wie beim Golden Set aus UC3_DATABASE_URL; es wird nur gelesen.
"""

from __future__ import annotations

import csv
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import psycopg
import pytest

from statagent import db
from statagent.frage import antwort_frage

pytestmark = pytest.mark.daten

WURZEL = Path(__file__).resolve().parents[2]
JURY = Path(__file__).parent / "fixtures" / "jury"

# Reihenfolge der ersten Nennung in fragen-48.txt und fragen-18.txt, ohne Dubletten.
# Absagen: nicht unterstützte Merkmale, mehrere Filterwerte, ÖNACE-Wechsel oder fehlende Lieferung.
# Fluktuation braucht einen einzelnen Monat; die erste Lieferung erlaubt keine ehrliche Bewegungszahl.
ERWARTUNGEN = (
    ("Zeigen Sie mir die Zeitreihe der Beschäftigten, jeweils zum Monatsletzten.", "zahl"),
    ("Wie haben sich die Beschäftigten im letzten Jahr entwickelt?", "zahl"),
    ("Zeitreihe der Beschäftigten 2025", "zahl"),
    ("Wie hat sich die Beschäftigung seit August 2024 entwickelt?", "zahl"),
    ("Wie viele Beschäftigte gab es von März bis Juni 2025?", "zahl"),
    ("Wie war die Entwicklung von März bis Juni 2025?", "zahl"),
    ("Zeitreihe der Beschäftigten in Wien von 01/2025 bis 12/2025", "zahl"),
    ("Verlauf Männer und Frauen 2025", "zahl"),
    ("Wie hat sich Wien gegenüber Tirol entwickelt?", "absage"),
    ("Wie hat sich die Gastronomie seit August 2024 entwickelt?", "absage"),
    ("Entwicklung im Bau seit August 2024", "absage"),
    ("Wie viele Männer und Frauen sind im August 2024 je Bundesland beschäftigt?", "zahl"),
    ("Männer und Frauen im Juli 2026", "zahl"),
    ("Wie viele Frauen arbeiten im Juli 2026 in Wien?", "zahl"),
    ("Wie hoch ist der Frauenanteil in Wien im März 2025?", "zahl"),
    ("Wie viele Frauen arbeiten im Gesundheitswesen in Wien im März 2025?", "zahl"),
    ("Wie viele Beschäftigte hatte der Bau im Juli 2026?", "zahl"),
    ("Wie viele Leute arbeiten im Handel im Dezember 2024?", "zahl"),
    ("Beschäftigte nach Branche im Juli 2026", "zahl"),
    ("Wie viele Beschäftigte gab es im März 2025 in Wien im Gesundheits- und Sozialwesen?", "zahl"),
    ("Was ist ÖNACE R?", "definition"),
    ("Wie viele Arbeiter und Angestellte gab es im Juli 2026?", "absage"),
    ("Beschäftigte nach Beschäftigungskategorie im Juli 2026", "zahl"),
    ("Wie viele freie Dienstverträge gab es im Juli 2026?", "zahl"),
    ("Wie viele Beamte gibt es im Juli 2026?", "zahl"),
    ("Wie viele Beschäftigte hat Tirol im Juli 2026?", "zahl"),
    ("Vergleich Wien und Tirol im Juli 2026", "absage"),
    ("Wie hoch ist die Fluktuation je Wirtschaftsbereich im Oktober 2024?", "zahl"),
    ("Wie hoch war die Fluktuation 2025?", "rueckfrage"),
    ("Was ist Fluktuation?", "definition"),
    ("Wie viele Beschäftigte unter 25 Jahren gab es im Juli 2026?", "zahl"),
    ("Wie viele Beschäftigte gibt es aktuell?", "zahl"),
    ("Wie viele Beschäftigte gab es Ende 2025?", "zahl"),
    ("Wie viele Beschäftigte gab es im März 2023?", "absage"),
    ("Beschäftigte im Jänner 2027", "absage"),
    ("Wie viele Jobs hatte Person 1234567 im März 2025?", "absage"),
    ("Was zählt als Beschäftigte?", "definition"),
    ("Wie hoch war die Fluktuation im Oktober 2025?", "zahl"),
    ("Fluktuation im Jänner 2025", "zahl"),
    ("Wie hoch war die Fluktuation in Wien im Juli 2026?", "absage"),
    ("Fluktuation von 01/2025 bis 12/2025", "rueckfrage"),
    ("Zu- und Abgänge im Bau im März 2025", "zahl"),
    ("Fluktuation im August 2024", "absage"),
    ("Durchschnittsalter der Beschäftigten im Juli 2026", "absage"),
    ("Wie hat sich die Zahl der Frauen in Wien seit Jänner 2025 entwickelt?", "zahl"),
    ("Zeitreihe Bau 2025", "zahl"),
    ("Wie viele Beschäftigte hatte Wien im Juli 2026 im Vergleich zum Juli 2025?", "zahl"),
    ("Beschäftigte je Bundesland im Juli 2026", "zahl"),
    ("Um wie viele Beschäftigte handelt es sich im Juli 2026?", "zahl"),
    ("Beschäftigte laut Datenbank im Juli 2026", "zahl"),
    ("Beschäftigte im Produktionslauf Juli 2026", "absage"),
    ("Beschäftigte in der Hausverwaltung im Juli 2026", "absage"),
    ("Wie viele weibliche Beschäftigte gab es im Juli 2026?", "zahl"),
    ("Fluktuation in den Wirtschaftsbereichen im Oktober 2024", "zahl"),
    ("Fluktuation in den Branchen im Oktober 2024", "zahl"),
    ("Beschäftigte im Bereich Handel im Juli 2026", "zahl"),
    ("Beschäftigte in der Branche Bau im Juli 2026", "zahl"),
    ("Fluktuation in Prozent im Oktober 2024", "zahl"),
    ("Vergleich Männer und Frauen im März 2025", "zahl"),
    ("Beschäftigte von November bis Februar 2025", "zahl"),
    ("beschäftigte in graz im juli 2026", "absage"),
    ("Beschäftigte in Wien und Graz im Juli 2026", "absage"),
    ("Beschäftigte in ÖNACE C und ÖNACE F im Juli 2026", "absage"),
    # „Alte Regel“ wählt derzeit keinen Regelstand; der Aufruf verwendet ausdrücklich v1.
    ("Beschäftigte nach alter Regel im Juli 2026", "zahl"),
    ("Gab es im Juli 2026 über 10000 Beschäftigte in Wien?", "zahl"),
    ("Beschäftigte 2025", "rueckfrage"),
    ("Männer und Frauen je Bundesland im Juli 2026", "zahl"),
    ("Wie viele Beschäftigte gab es im Sommer 2025?", "zahl"),
)
ERGAENZUNGEN = (
    "Beschäftigte 2025",
    "Männer und Frauen je Bundesland im Juli 2026",
    "Wie viele Beschäftigte gab es im Sommer 2025?",
)
MONATSNAMEN = (
    "Jänner",
    "Februar",
    "März",
    "April",
    "Mai",
    "Juni",
    "Juli",
    "August",
    "September",
    "Oktober",
    "November",
    "Dezember",
)
BUNDESLAENDER = {
    "0": "Bundesland unbekannt",
    "1": "Burgenland",
    "2": "Kärnten",
    "3": "Niederösterreich",
    "4": "Oberösterreich",
    "5": "Salzburg",
    "6": "Steiermark",
    "7": "Tirol",
    "8": "Vorarlberg",
    "9": "Wien",
}


@pytest.fixture(scope="module")
def conn() -> Iterator[db.Verbindung]:
    try:
        verbindung = db.verbinden()
    except psycopg.OperationalError as fehler:
        pytest.fail(f"Datenbank nicht erreichbar ({type(fehler).__name__}); UC3_DATABASE_URL prüfen")
    try:
        verbindung.execute("SET default_transaction_read_only = on")
        yield verbindung
    finally:
        verbindung.close()


@pytest.fixture(scope="module")
def antworten(conn: db.Verbindung) -> dict[str, dict[str, Any]]:
    # Jede Frage nur einmal ausführen, auch für Zusammenfassung und Zahlenprüfungen.
    return {frage: antwort_frage(conn, frage) for frage, _ in ERWARTUNGEN}


def _kategorie(daten: dict[str, Any]) -> str:
    if daten["rueckfrage"] is True:
        return "rueckfrage" if daten["zahlen"] == [] else "widersprüchlich"
    if daten["rueckfrage"] is not False:
        return "widersprüchlich"
    if daten["typ"] == "definition":
        return "definition" if daten["zahlen"] == [] else "widersprüchlich"
    return "zahl" if daten["zahlen"] else "absage"


def _csv(datei: Path) -> list[dict[str, str]]:
    with datei.open(encoding="utf-8", newline="") as quelle:
        return list(csv.DictReader(quelle, delimiter=";"))


@pytest.fixture(scope="module")
def zeitreihe() -> dict[str, int]:
    zeilen = _csv(WURZEL / "tests" / "abnahme" / "orakel" / "zeitreihe.csv")
    soll = {z["monat"]: int(z["v1_sheet_mit_e07"]) for z in zeilen}
    assert len(zeilen) == len(soll) == 24
    assert set(soll) == {
        f"{jahr}-{monat:02d}"
        for jahr, monate in ((2024, range(8, 13)), (2025, range(1, 13)), (2026, range(1, 8)))
        for monat in monate
    }
    return soll


def _zahlen(daten: dict[str, Any]) -> dict[str, int]:
    zahlen = daten["zahlen"]
    assert zahlen, daten["text"]
    assert all(type(z["wert"]) is int for z in zahlen), zahlen
    werte = {z["bezeichnung"]: z["wert"] for z in zahlen}
    assert len(werte) == len(zahlen), "Doppelte Zahlenbezeichnungen"
    return werte


def _monat_name(monat: str) -> str:
    return f"{MONATSNAMEN[int(monat[5:]) - 1]} {monat[:4]}"


@pytest.mark.parametrize(("frage", "kategorie"), ERWARTUNGEN, ids=[f for f, _ in ERWARTUNGEN])
def test_jury_kategorie(antworten: dict[str, dict[str, Any]], frage: str, kategorie: str) -> None:
    # Fängt: eine Juryfrage liefert die falsche Antwortart oder eine Zahl trotz nötiger Absage/Rückfrage.
    daten = antworten[frage]
    assert _kategorie(daten) == kategorie, f"{frage}: {daten}"


def test_jury_0_falsch(antworten: dict[str, dict[str, Any]]) -> None:
    # Fängt: ausgelassene oder doppelt parametrisierte Fragen und jede Kategorieabweichung in der Gesamtprobe.
    fragen = list(
        dict.fromkeys(
            zeile.strip()
            for name in ("fragen-48.txt", "fragen-18.txt")
            for zeile in (JURY / name).read_text(encoding="utf-8").splitlines()
            if zeile.strip() and not zeile.lstrip().startswith("#")
        )
    )
    assert [f for f, _ in ERWARTUNGEN] == list(dict.fromkeys([*fragen, *ERGAENZUNGEN]))
    falsch = [
        f"{frage}: erwartet {soll}, erhalten {_kategorie(antworten[frage])}: {antworten[frage]['text']}"
        for frage, soll in ERWARTUNGEN
        if _kategorie(antworten[frage]) != soll
    ]
    assert len(falsch) == 0, f"{len(falsch)} falsch:\n" + "\n".join(falsch)


@pytest.mark.parametrize(
    ("frage", "von", "bis"),
    [
        ("Zeigen Sie mir die Zeitreihe der Beschäftigten, jeweils zum Monatsletzten.", "2024-08", "2026-07"),
        ("Wie haben sich die Beschäftigten im letzten Jahr entwickelt?", "2025-01", "2025-12"),
        ("Zeitreihe der Beschäftigten 2025", "2025-01", "2025-12"),
        ("Wie hat sich die Beschäftigung seit August 2024 entwickelt?", "2024-08", "2026-07"),
        ("Wie viele Beschäftigte gab es von März bis Juni 2025?", "2025-03", "2025-06"),
        ("Wie war die Entwicklung von März bis Juni 2025?", "2025-03", "2025-06"),
        ("Beschäftigte von November bis Februar 2025", "2024-11", "2025-02"),
    ],
)
def test_zeitreihe_gegen_orakel(
    antworten: dict[str, dict[str, Any]], zeitreihe: dict[str, int], frage: str, von: str, bis: str
) -> None:
    # Fängt: fehlende Monate, falsche Zeitgrenzen und Bestände ohne E07 oder aus einem anderen Regelsatz.
    soll = {
        f"Beschäftigungsverhältnisse, {_monat_name(monat)}": wert
        for monat, wert in zeitreihe.items()
        if von <= monat <= bis
    }
    assert _zahlen(antworten[frage]) == soll


@pytest.mark.parametrize(
    ("frage", "monat"),
    [
        ("Wie viele Beschäftigte gibt es aktuell?", "2026-07"),
        ("Wie viele Beschäftigte gab es Ende 2025?", "2025-12"),
        ("Um wie viele Beschäftigte handelt es sich im Juli 2026?", "2026-07"),
        ("Beschäftigte laut Datenbank im Juli 2026", "2026-07"),
    ],
)
def test_einzelmonat_gegen_orakel(
    antworten: dict[str, dict[str, Any]], zeitreihe: dict[str, int], frage: str, monat: str
) -> None:
    # Fängt: „aktuell“ nutzt die Rechnerzeit, „Ende“ den falschen Monat oder eine Formulierung einen Branchenfilter.
    assert _zahlen(antworten[frage]) == {"Beschäftigungsverhältnisse": zeitreihe[monat]}


def test_sommer_gegen_orakel(antworten: dict[str, dict[str, Any]], zeitreihe: dict[str, int]) -> None:
    # Fängt: Sommer ist nicht Juni–August, ein Monatswert fehlt oder der Durchschnitt ist falsch gerundet.
    monate = ("2025-06", "2025-07", "2025-08")
    soll = {f"Beschäftigungsverhältnisse, {_monat_name(m)}": zeitreihe[m] for m in monate}
    n = len(monate)
    soll["Beschäftigungsverhältnisse, Durchschnitt Juni bis August 2025"] = (
        2 * sum(zeitreihe[m] for m in monate) + n
    ) // (2 * n)
    assert _zahlen(antworten["Wie viele Beschäftigte gab es im Sommer 2025?"]) == soll


@pytest.mark.parametrize("je_bundesland", [False, True], ids=["gesamt", "je Bundesland"])
def test_maenner_frauen_gegen_orakel(antworten: dict[str, dict[str, Any]], je_bundesland: bool) -> None:
    # Fängt: vertauschte Geschlechter, falsche Bundesländer oder der Verlust des unbekannten Bundeslands (0).
    zeilen = _csv(JURY / "orakel-mw-bl-2026-07.csv")
    je_code = {z["bundesland_code"]: z for z in zeilen}
    assert len(zeilen) == len(je_code) == 11
    assert set(je_code) == {*BUNDESLAENDER, "Insgesamt"}
    for z in zeilen:
        assert int(z["maenner"]) + int(z["frauen"]) == int(z["insgesamt"])
    for spalte in ("maenner", "frauen", "insgesamt"):
        assert sum(int(je_code[c][spalte]) for c in BUNDESLAENDER) == int(je_code["Insgesamt"][spalte])
    frage = (
        "Männer und Frauen je Bundesland im Juli 2026" if je_bundesland else "Männer und Frauen im Juli 2026"
    )
    soll = {}
    for code in BUNDESLAENDER if je_bundesland else ("Insgesamt",):
        for geschlecht, spalte in (("Männer", "maenner"), ("Frauen", "frauen")):
            zusatz = f", {BUNDESLAENDER[code]}" if je_bundesland else ""
            soll[f"Beschäftigungsverhältnisse, {geschlecht}{zusatz}"] = int(je_code[code][spalte])
    assert _zahlen(antworten[frage]) == soll


@pytest.mark.parametrize(
    ("frage", "code", "spalte", "etikett"),
    [
        ("Wie viele Frauen arbeiten im Juli 2026 in Wien?", "9", "frauen", "Wien, Frauen"),
        ("Wie viele Beschäftigte hat Tirol im Juli 2026?", "7", "insgesamt", "Tirol"),
        ("Wie viele weibliche Beschäftigte gab es im Juli 2026?", "Insgesamt", "frauen", "Frauen"),
        ("Gab es im Juli 2026 über 10000 Beschäftigte in Wien?", "9", "insgesamt", "Wien"),
    ],
)
def test_gefilterter_bestand_gegen_orakel(
    antworten: dict[str, dict[str, Any]], frage: str, code: str, spalte: str, etikett: str
) -> None:
    # Fängt: ein Geschlechts-/Bundeslandfilter fällt weg oder eine Mengenschwelle wird als Personen-ID gelesen.
    je_code = {z["bundesland_code"]: z for z in _csv(JURY / "orakel-mw-bl-2026-07.csv")}
    assert _zahlen(antworten[frage]) == {
        f"Beschäftigungsverhältnisse ({etikett})": int(je_code[code][spalte])
    }


def test_bundeslaender_gegen_orakel(antworten: dict[str, dict[str, Any]]) -> None:
    # Fängt: eine Bundeslandsumme fehlt oder stimmt trotz richtiger Antwortkategorie nicht mit dem Orakel überein.
    je_code = {z["bundesland_code"]: z for z in _csv(JURY / "orakel-mw-bl-2026-07.csv")}
    soll = {
        f"Beschäftigungsverhältnisse, {name}": int(je_code[code]["insgesamt"])
        for code, name in BUNDESLAENDER.items()
    }
    assert _zahlen(antworten["Beschäftigte je Bundesland im Juli 2026"]) == soll
