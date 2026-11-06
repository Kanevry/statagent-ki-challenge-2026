"""Unbekannte Wörter ergeben keine Zahl (#186)."""

from __future__ import annotations

import pytest

from statagent.db import Verbindung
from statagent.frage import antwort_frage
from statagent.lauf import lauf_ausfuehren
from statagent.uc4 import uc4_antwort
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


# Fängt (ui-regie, Bank): „ohne Kinder“ fiel still weg, die Antwort war die Zahl aller Frauen.
def test_unbekanntes_wort_im_v1_weg(conn: Verbindung) -> None:
    lauf_ausfuehren(conn, "2024-08", "v1")
    assert antwort_frage(conn, "Frauen ohne Kinder im August 2024")["zahlen"] == []


def test_regelsatz_angabe_ist_kein_unbekanntes_wort() -> None:
    assert unbekanntes_wort("Beschäftigte im März 2025 im Regelsatz v1", []) is None
    assert unbekanntes_wort("Beschäftigte über das ganze Monat März 2025", []) is None


# Fängt: Das „1“ in „v1“ galt als lose Zahl, „im Regelsatz v1“ bekam die Absage.
def test_ziffer_am_wort_ist_keine_lose_zahl() -> None:
    assert unbekanntes_wort("Beschäftigte im Regelsatz v1 im März 2025", []) is None
    assert unbekanntes_wort("Beschäftigte ab 50 im März 2025", []) == "50"


# Fängt (Prüfung !242): Mit dem erkannten „IT“ wurde aus „arbeiten“ das unbekannte Wort „arbe“.
def test_ersetzen_nur_mit_wortgrenze() -> None:
    assert unbekanntes_wort("Wie viele Leute arbeiten in der IT im März 2025?", ["it"]) is None
    assert unbekanntes_wort("Bitte die Zeitreihe seit März 2025", ["it"]) is None


@pytest.mark.parametrize(
    "frage",
    [
        "Was haette es gegeben, wuerde man Beschäftigte zählen, im März 2025",
        "Gib mir die Mitarbeiter im Berichtsmonat März 2025",
        "Beschaeftigte österreichweit, März 2025",
    ],
)
def test_schreibweisen_und_fuellwoerter(frage: str) -> None:
    assert unbekanntes_wort(frage, []) is None


def _werte(daten: dict[str, object]) -> list[object]:
    return [z["wert"] for z in daten["zahlen"]]  # type: ignore[attr-defined]


@pytest.fixture
def zwei_monate(conn: Verbindung) -> Verbindung:
    lauf_ausfuehren(conn, "2024-08", "v1")
    lauf_ausfuehren(conn, "2024-09", "v1")
    return conn


# Fängt (Prüfung !242): „seit“ mit „verändert“ gab nur den Vormonat und den genannten Monat.
def test_seit_mit_veraendert_bleibt_zeitraum(zwei_monate: Verbindung) -> None:
    daten = antwort_frage(zwei_monate, "Wie hat sich die Beschäftigung seit August 2024 verändert?")
    namen = " ".join(z["bezeichnung"] for z in daten["zahlen"])
    assert "August 2024" in namen and "September 2024" in namen and "Juli 2024" not in namen


# Fängt (Prüfung !242): „Prozent der Männer … im Bau“ nannte den Männeranteil im Bau, die andere Richtung.
@pytest.mark.parametrize(
    "frage",
    [
        "Wie viel Prozent der Männer arbeiten im August 2024 im Bau?",
        "Wie viel Prozent aller Frauen arbeiten im August 2024 in Wien?",
    ],
)
def test_prozent_von_gruppe_sagt_ab(zwei_monate: Verbindung, frage: str) -> None:
    assert antwort_frage(zwei_monate, frage)["zahlen"] == []


def test_prozent_mit_frauen_als_ziel_bleibt_zahl(zwei_monate: Verbindung) -> None:
    daten = antwort_frage(
        zwei_monate, "Wie viel Prozent der Beschäftigten in Wien sind Frauen? Stand August 2024"
    )
    assert any(z["einheit"] == "Prozent" for z in daten["zahlen"])


# Fängt (Prüfung !242): Binnen-I zählte wegen der Regel für „Arbeiterinnen“ nur die Frauen.
def test_binnen_i_meint_alle(zwei_monate: Verbindung) -> None:
    alle = _werte(antwort_frage(zwei_monate, "Wie viele Arbeiter gab es im August 2024?"))
    assert _werte(antwort_frage(zwei_monate, "Wie viele ArbeiterInnen gab es im August 2024?")) == alle
    frauen = _werte(antwort_frage(zwei_monate, "Wie viele Arbeiterinnen gab es im August 2024?"))
    assert frauen != alle


# Fängt (Prüfung !242): „Bau“ steckte in „Bergbau und Gewinnung“, die Antwort galt still nur dem Bergbau.
def test_bau_steckt_nicht_im_bergbau(zwei_monate: Verbindung) -> None:
    assert antwort_frage(zwei_monate, "Beschäftigte im Bergbau und im Bau im August 2024")["zahlen"] == []


# Fängt (Prüfung !242): date(0, …) warf; antwort_frage verspricht, nie zu werfen.
@pytest.mark.parametrize("frage", ["Beschäftigte im März 0000", "Beschäftigte 01/0000"])
def test_jahr_null_wirft_nicht(zwei_monate: Verbindung, frage: str) -> None:
    assert antwort_frage(zwei_monate, frage)["zahlen"] == []


# Fängt (Prüfung !242): Ein zweistelliges Jahr ergab still einen anderen Zeitraum.
@pytest.mark.parametrize(
    "frage",
    ["Beschäftigte im Winter 24/25", "Beschäftigte Q1/25", "Beschäftigte März/25", "Beschäftigte im 03/25"],
)
def test_kurzes_jahr_fragt_zurueck(zwei_monate: Verbindung, frage: str) -> None:
    daten = antwort_frage(zwei_monate, frage)
    assert daten["zahlen"] == [] and "vierstellig" in daten["text"]


# Fängt (Prüfung !242): Das Wort aus der Bewertung lieferte nur die Gesamtzahl.
@pytest.mark.parametrize(
    "frage",
    [
        "Beschäftigte je Wirtschaftsbereich im August 2024",
        "Beschäftigte aufgeteilt auf die Bundesländer im August 2024",
    ],
)
def test_gliederung_wird_gelesen(zwei_monate: Verbindung, frage: str) -> None:
    assert len(antwort_frage(zwei_monate, frage)["zahlen"]) > 1


# Fängt (Prüfung !242): „im Vormonat“ ohne Monat gab den jüngsten Monat, „vs. Vormonat“ nur den genannten.
def test_vormonat(zwei_monate: Verbindung) -> None:
    assert antwort_frage(zwei_monate, "Beschäftigte im Vormonat")["zahlen"] == []
    daten = antwort_frage(zwei_monate, "Beschäftigte September 2024 vs. Vormonat")
    assert len(daten["zahlen"]) >= 2


def test_nur_ein_job_sagt_ab(zwei_monate: Verbindung) -> None:
    assert (
        antwort_frage(zwei_monate, "Wie viele Personen hatten im August 2024 nur einen Job?")["zahlen"] == []
    )


# Fängt (Prüfung !242): „Das Wort „25““ nannte eine Zahl ein Wort.
def test_lose_zahl_heisst_angabe(zwei_monate: Verbindung) -> None:
    daten = antwort_frage(zwei_monate, "Beschäftigte mit 25 Jahren im August 2024")
    assert daten["zahlen"] == [] and daten["text"].startswith("Die Angabe „25“")


# Fängt (Prüfung !242, Runde 2): Diese Fragen ergaben die Gesamtzahl.
@pytest.mark.parametrize(
    "frage",
    [
        "Wie viele Regeln gibt es?",
        "Wie viele der alten Beschäftigten gab es im August 2024?",
        "Wie viele Beschäftigte sind alt?",
        "Wie viel Prozent der Frauen sind Angestellte im August 2024?",
        "Wie viel Prozent der Männer waren im August 2024 im Bau beschäftigt?",
        "Wie viel Prozent der Frauen in Wien arbeiten im Bau im August 2024?",
        "Wie viel Prozent von den Männern arbeiten im Bau im August 2024?",
        "Anteil der Männer, die im Bau arbeiten, im August 2024",
        "Wie hat sich die Beschäftigung gegenüber dem Vormonat verändert?",
        "Beschäftigte im Vergleich zum Vormonat",
        "Beschäftigte gegenüber dem Vorjahr",
        "Beschäftigte im Jänner 0000 gegenüber dem Vormonat",
        "Beschäftigte März-25",
        "Beschäftigte Q1-25",
        "Beschäftigte Mrz-25",
        "Beschäftigte 03.25",
        "Beschäftigte am 31.03.25",
        "Wie viele Männer waren im Vormonat von September 2024 beschäftigt?",
    ],
)
def test_runde_zwei_ohne_zahl(zwei_monate: Verbindung, frage: str) -> None:
    assert antwort_frage(zwei_monate, frage)["zahlen"] == []
    assert uc4_antwort(zwei_monate, frage)["zahlen"] == []


# Gegenfälle: Diese Fragen behalten ihre Zahl.
@pytest.mark.parametrize(
    "frage",
    [
        "Wie viel Prozent der Beschäftigten in Wien sind Frauen? Stand August 2024",
        "Frauenanteil in Wien im August 2024",
        "Anteil der Frauen im Bau im August 2024",
        "Anteil der Frauen unter Arbeitern im August 2024",
        "Wie viel Prozent der Frauen im August 2024",
        "Beschäftigte zwischen 18-25 Jahren im August 2024",
        "Gab es im August 2024 über 20.000 Beschäftigte in Wien?",
        "Wie viele Beschäftigte waren im August 2024 über 50 Jahre alt?",
        "Beschäftigte nach alten Regeln im August 2024",
    ],
)
def test_runde_zwei_mit_zahl(zwei_monate: Verbindung, frage: str) -> None:
    assert uc4_antwort(zwei_monate, frage)["zahlen"]


# Fängt (Prüfung !242, Runde 2): „auf“ machte aus dem Filter eine Aufteilung.
@pytest.mark.parametrize(
    "frage",
    [
        "Beschäftigte bezogen auf das Bundesland Wien im August 2024",
        "Beschäftigte bezogen auf die Branche Bau im August 2024",
    ],
)
def test_bezogen_auf_bleibt_filter(zwei_monate: Verbindung, frage: str) -> None:
    assert len(uc4_antwort(zwei_monate, frage)["zahlen"]) == 1


def test_anteil_nennt_den_monat_im_ersten_satz(zwei_monate: Verbindung) -> None:
    daten = uc4_antwort(zwei_monate, "Frauenanteil in Wien im August 2024")
    assert daten["text"].startswith("Anteil an allen (Wien) im August 2024: ")


def test_in_den_wirtschaftszweigen_ist_eine_gliederung(zwei_monate: Verbindung) -> None:
    assert (
        len(uc4_antwort(zwei_monate, "Beschäftigte in den Wirtschaftszweigen im August 2024")["zahlen"]) > 1
    )


# Fängt (Prüfung !242, Runde 3): falsche Richtung beim Anteil, Prozentzeichen, kurze Jahre mit Satzpunkt.
@pytest.mark.parametrize(
    "frage",
    [
        "Welcher Anteil der Frauen arbeitet im August 2024 im Bau?",
        "Wie viel Prozent der Frauen sind über 50 Jahre alt? Stand August 2024",
        "Wie viel Prozent der Frauen haben einen freien Dienstvertrag? Stand August 2024",
        "Wie viel % der Frauen arbeiten im August 2024 im Bau?",
        "Beschäftigte im März-25.",
        "Beschäftigte Q1-25.",
        "Beschäftigte 03.25.",
        "Beschäftigte am 31.03.25.",
        "Frauenanteil je Branche im August 2024",
        "Männer und Frauen je Branche im August 2024",
    ],
)
def test_runde_drei_ohne_zahl(zwei_monate: Verbindung, frage: str) -> None:
    assert uc4_antwort(zwei_monate, frage)["zahlen"] == []


def test_prozentzeichen_liest_den_anteil(zwei_monate: Verbindung) -> None:
    daten = uc4_antwort(zwei_monate, "Wie viel % der Beschäftigten in Wien sind Frauen? Stand August 2024")
    assert daten["text"].startswith("Anteil an allen (Wien) im August 2024: ")


def test_fluktuation_gegenueber_vormonat_fragt_nach_fluktuation(zwei_monate: Verbindung) -> None:
    daten = antwort_frage(zwei_monate, "Fluktuation gegenüber dem Vormonat")
    assert daten["zahlen"] == [] and "Fluktuation" in daten["text"]


# Fängt (Prüfung !242, Runde 3): Zwei genannte Bundesländer galten als „in den Bundesländern“ und gaben die Tabelle.
def test_in_den_bundeslaendern_mit_namen_ist_kein_aufteilen(zwei_monate: Verbindung) -> None:
    daten = uc4_antwort(zwei_monate, "Beschäftigte in den Bundesländern Wien und Tirol im August 2024")
    assert len(daten["zahlen"]) == 3


@pytest.mark.parametrize(
    "frage",
    [
        "Beschäftigte aufgeteilt auf ÖNACE-Abschnitte im August 2024",
        "Beschäftigte aufgeteilt auf Bundesland im August 2024",
    ],
)
def test_aufgeteilt_auf_ist_eine_gliederung(zwei_monate: Verbindung, frage: str) -> None:
    assert len(uc4_antwort(zwei_monate, frage)["zahlen"]) > 1


@pytest.mark.parametrize(
    "frage",
    [
        "Männer und Frauen je Bundesland im August 2024",
        "Beschäftigte am 31.08.2024",
        "Gab es im August 2024 über 20.000 Beschäftigte in Wien?",
    ],
)
def test_runde_drei_gegenfaelle_behalten_die_zahl(zwei_monate: Verbindung, frage: str) -> None:
    assert uc4_antwort(zwei_monate, frage)["zahlen"]


def test_lagerei_gehoert_zum_verkehr(zwei_monate: Verbindung) -> None:
    mit = uc4_antwort(zwei_monate, "Beschäftigte im Verkehr und in der Lagerei im August 2024")
    ohne = uc4_antwort(zwei_monate, "Beschäftigte im Verkehr im August 2024")
    assert [z["wert"] for z in mit["zahlen"]] == [z["wert"] for z in ohne["zahlen"]]


def test_je_branche_im_satz(zwei_monate: Verbindung) -> None:
    daten = uc4_antwort(zwei_monate, "Männer und Frauen je Branche im August 2024")
    assert daten["zahlen"] and "Unten stehen die Zahlen je Branche" in daten["text"]


# Fängt (Blind-Runden, #186): die andere Richtung beim Anteil, in weiteren Formen.
@pytest.mark.parametrize(
    "frage",
    [
        "Von allen beschäftigten Männern: Wie viel Prozent arbeiten im August 2024 in der Herstellung von Waren?",
        "Wie viel Prozent von allen Frauen arbeiten im August 2024 in Wien?",
        "Wie viel Prozent der weiblichen Beschäftigten arbeiten im August 2024 im Bau?",
        "Wie groß ist der Anteil Kärntens an allen beschäftigten Männern im August 2024?",
        "Wie viele von hundert Frauen arbeiten im August 2024 im Bau?",
        "Frauenanteil seit August 2024",
    ],
)
def test_anteil_andere_richtung_und_zeitraum_ohne_zahl(zwei_monate: Verbindung, frage: str) -> None:
    assert uc4_antwort(zwei_monate, frage)["zahlen"] == []
