"""/uc4 nimmt denselben Weg wie /uc3/fragen (#176): keine Zahl zu einer Frage, die es nicht versteht."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

import pytest
from typer.testing import CliRunner

from statagent import cli
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


def _direkt_monat(conn: Verbindung, monat: str, bedingung: str) -> int:
    stand = letzter_lauf(conn, monat)
    assert stand is not None
    zeile = conn.execute(
        (
            "SELECT COALESCE(sum(wert), 0) AS wert FROM stat.stat_beschaeftigte WHERE regelsatz = 'v1'"
            " AND regelstand = %s AND zeitraum_art = 'Stichtag' AND variable = 'Beschaeftigungsverhaeltnisse'"
            " AND zeitraum_bis BETWEEN %s AND %s" + bedingung
        ).encode(),
        (stand.regelstand, monatserster(monat), monatsletzter(monat)),
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


# Fängt (#176): Fluktuation ergab den Bestand. In der Kette steht genau eine Zahl, die Tabelle bleibt auf /uc3/fragen.
def test_fluktuation_eine_zahl_kein_bestand(gerechnet: Verbindung) -> None:
    frage = "Wie hoch ist die Fluktuation im September 2024?"
    daten = uc4_antwort(gerechnet, frage)
    voll = antwort_frage(gerechnet, frage)
    gesamt = [z for z in voll["zahlen"] if z["bezeichnung"].startswith("Fluktuation, alle")]
    assert [z["wert"] for z in daten["zahlen"]] == [gesamt[0]["wert"]]
    assert daten["zahlen"][0]["einheit"] == "Prozent"
    assert daten["zahlen"][0]["beleg"] == 0 and len(daten["belege"]) == 1
    assert "stat." in daten["belege"][0]["sql"]
    assert daten["text"].startswith(
        "Über alle Wirtschaftsbereiche zusammen lag die Fluktuation im September 2024 bei "
    )
    assert "Die Zahlen je Branche stehen unter Fragen an die Daten." in daten["text"]
    assert "Die Zahl ist " in daten["text"]


# Fängt: Der Hinweis zu Abschnitten ohne Bestand steht in der Kette, oder der Hinweis zur Fortschreibung fehlt.
def test_fluktuation_nur_der_passende_hinweis(gerechnet: Verbindung) -> None:
    gerechnet.execute("UPDATE meta.lauf SET fortgeschrieben = 1234 WHERE lieferung = '2024-09'")
    text = uc4_antwort(gerechnet, "Fluktuation im September 2024")["text"]
    assert "zu niedrig" in text and "keine Beschäftigten" not in text


# Fängt (Prüfung !192): Die Weiche zum Adapter gab bei zwei Werten wieder den Bestand: der Fehler aus #176.
@pytest.mark.parametrize(
    "frage",
    [
        "Fluktuation in Wien und Tirol im September 2024",
        "Fluktuation bei Männern und Frauen im September 2024",
        "Beschäftigte in Wien und Tirol von 08/2024 bis 09/2024",
        "Frauenanteil in Wien und Tirol im September 2024",
    ],
)
def test_zwei_werte_kein_bestand_als_antwort(gerechnet: Verbindung, frage: str) -> None:
    daten = uc4_antwort(gerechnet, frage)
    assert daten["zahlen"] == [] and daten["text"]


# Fängt (Prüfung !192): „ÖNACE C und F“ ergab nur C, ohne Hinweis; auf /uc3/fragen heißt das eine Absage.
def test_oenace_liste(gerechnet: Verbindung) -> None:
    frage = "Beschäftigte in ÖNACE C und F im September 2024"
    c, f = _direkt(gerechnet, " AND oenace = 'C'"), _direkt(gerechnet, " AND oenace = 'F'")
    assert _werte(uc4_antwort(gerechnet, frage)) == [c, f, c + f]
    absage = antwort_frage(gerechnet, frage)
    assert absage["zahlen"] == [] and "mehrere Werte" in absage["text"]


# Fängt (Prüfung !192): Eine Absage beim Nachlesen brach die Station ab, statt die Absage zu zeigen.
def test_adapter_pruefung_wirft_nicht(gerechnet: Verbindung, monkeypatch: pytest.MonkeyPatch) -> None:
    from statagent import frage as weg
    from statagent import uc4

    def wirft(*_: object) -> None:
        raise weg._KeineZahl("Die Branche gibt es nicht.")

    monkeypatch.setattr(weg, "_werte", wirft)
    assert (
        uc4._adapter_liest_gleich(gerechnet, "Beschäftigte in Wien und Tirol im September 2024", "v1")
        is False
    )


# Fängt (Prüfung !192): Die Konsole sagte weiter die Zahl des alten Wegs.
def test_konsole_nimmt_denselben_weg(gerechnet: Verbindung, monkeypatch: pytest.MonkeyPatch) -> None:
    @contextmanager
    def verbindung() -> Iterator[Verbindung]:
        yield gerechnet

    monkeypatch.setattr(cli, "verbinden", verbindung)
    ergebnis = CliRunner().invoke(
        cli.app, ["antwort", "Wie viele Jobs hatte Person 1234567 im September 2024?"]
    )
    assert ergebnis.exit_code == 0 and "Einzeldaten" in ergebnis.output
    wien = CliRunner().invoke(cli.app, ["antwort", "Beschäftigte in Wien im September 2024"])
    assert f"{_direkt(gerechnet, " AND region = '9'")}" in wien.output


# Fängt (Prüfung !192): Bei „Zugänge“ stand die Fluktuation in Prozent statt der Zahl der Zugänge.
@pytest.mark.parametrize(
    "frage", ["Wie viele Zugänge gab es im September 2024?", "Abgänge im Bau im September 2024"]
)
def test_zugaenge_und_abgaenge_keine_kurzfassung(gerechnet: Verbindung, frage: str) -> None:
    daten = uc4_antwort(gerechnet, frage)
    voll = antwort_frage(gerechnet, frage)
    assert daten["zahlen"] == voll["zahlen"] and "Die Zahlen je Branche stehen" not in daten["text"]
    assert any(z["bezeichnung"].startswith(("Zugänge", "Abgänge")) for z in daten["zahlen"])
    assert "Zwischen" in daten["text"]


# Fängt: Gefragt war eine Branche, die Zahl für alle Branchen wäre eine andere Antwort.
def test_fluktuation_gefragte_branche(gerechnet: Verbindung) -> None:
    frage = "Fluktuation im Bau im September 2024"
    daten = uc4_antwort(gerechnet, frage)
    soll = [
        z
        for z in antwort_frage(gerechnet, frage)["zahlen"]
        if z["bezeichnung"].startswith("Fluktuation, ÖNACE F ")
    ]
    assert [z["wert"] for z in daten["zahlen"]] == [soll[0]["wert"]]
    assert daten["text"].startswith("In der Branche Bau lag die Fluktuation im September 2024 bei ")
    assert "alle Wirtschaftsbereiche" not in daten["text"]


# Fängt: Bei genau einer Zahl steht „Verstanden …“ als Antwort der Station (ui-regie-36); „…: alle“ grenzt nichts ein.
def test_eine_zahl_erster_satz_ist_die_antwort(gerechnet: Verbindung) -> None:
    soll = _direkt(gerechnet)
    daten = uc4_antwort(gerechnet, "Wie viele Beschäftigte gab es im September 2024?")
    anfang = f"Am 30.09.2024, dem letzten Tag im September 2024, gab es {str(f'{soll:,}').replace(',', '.')} Beschäftigungsverhältnisse."
    assert daten["text"].startswith(anfang)
    assert ": alle" not in daten["text"]
    assert "Verstanden: September 2024." in daten["text"]
    wien = uc4_antwort(gerechnet, "Wie viele Beschäftigte gab es im September 2024 in Wien?")
    assert (
        wien["text"].startswith("Am 30.09.2024,")
        and "Verstanden: September 2024, Bundesland Wien." in wien["text"]
    )
    kern = pytest.importorskip("plattform.router").kern_satz
    assert kern(daten["text"]).startswith("Am 30.09.2024, dem letzten Tag im September 2024, gab es")


# Fängt: „…: alle“ steht auch bei mehreren Zahlen im Text.
def test_mehrere_zahlen_ohne_alle(gerechnet: Verbindung) -> None:
    daten = uc4_antwort(gerechnet, "Zeitreihe 08/2024 bis 09/2024")
    assert len(daten["zahlen"]) == 2 and ": alle" not in daten["text"]
    werte = [f"{z['wert']:,}".replace(",", ".") for z in daten["zahlen"]]
    assert daten["text"].startswith(f"Von {werte[0]} auf {werte[1]} Beschäftigungsverhältnisse")


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
        "Wie hat sich Wien gegenüber Tirol im September 2024 entwickelt?",
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


# Fängt (Owner 05.11., „Winter 2025 in Wien im Gesundheits- und Sozialwesen“): Über den ÖNACE-Wechsel gab es nur den Satz
# „Winter 2025 heißt hier …“. Gleicher Name in beiden Versionen heißt: die Zahl, mit dem Abschnitt je Monat.
def test_branche_ueber_oenace_wechsel_zeigt_die_zahl(gerechnet: Verbindung) -> None:
    daten = uc4_antwort(gerechnet, "Beschäftigte in Wien im Gesundheits- und Sozialwesen von 08/2024 bis 03/2025")
    soll = [
        _direkt_monat(gerechnet, monat, " AND region = '9' AND oenace = 'Q'") for monat in ("2024-08", "2024-09")
    ]
    assert _werte(daten)[:2] == soll
    sql_text = " ".join(b["sql"] for b in daten["belege"])
    assert "s.oenace = 'Q'" in sql_text and "s.oenace = 'R'" in sql_text
    assert "ist bis Dezember 2024 Abschnitt Q, ab Jänner 2025 Abschnitt R" in daten["text"]
    kern = pytest.importorskip("plattform.router").kern_satz
    assert any(f"{w:,}".replace(",", ".") in kern(daten["text"]) for w in soll)


# Fängt: „ÖNACE Q“ ist 2008 Gesundheit und 2025 Erziehung, „Handel“ hieß 2008 anders. Keine gemeinsame Zahl.
@pytest.mark.parametrize(
    "frage",
    ["Beschäftigte in ÖNACE Q von 08/2024 bis 03/2025", "Beschäftigte im Handel von 08/2024 bis 03/2025"],
)
def test_keine_gemeinsame_zahl_ueber_den_wechsel(gerechnet: Verbindung, frage: str) -> None:
    daten = uc4_antwort(gerechnet, frage)
    assert daten["zahlen"] == []
    assert daten["text"].startswith("Für diesen Zeitraum gibt es keine gemeinsame Zahl")
    assert "August bis Dezember 2024 und Jänner bis März 2025" in daten["text"]


# Fängt: „Winter 2024“ (Dezember 2023 bis Februar 2024) sagte als ersten Satz nur, was verstanden wurde.
def test_winter_ganz_ausserhalb_fragt_nach_dem_nachbarn(gerechnet: Verbindung) -> None:
    daten = uc4_antwort(gerechnet, "Wie viele Beschäftigte gab es im Winter 2024?")
    assert daten["zahlen"] == []
    assert daten["text"].startswith("Für Dezember 2023 bis Februar 2024 gibt es keine Zahl")
    assert "Winter 2024/25, also Dezember 2024 bis Februar 2025?" in daten["text"]


# Fängt: Ein Monat ohne Lieferung zeigte in der Station nur „Verstanden: Juli 2024.“
def test_ohne_zahl_ist_verstanden_nicht_der_erste_satz(gerechnet: Verbindung) -> None:
    daten = uc4_antwort(gerechnet, "Beschäftigte im Juli 2024")
    assert daten["zahlen"] == [] and not daten["text"].startswith("Verstanden")
    assert daten["text"].startswith("Für Juli 2024 gibt es keine Lieferung")


# Fängt: „im Durchschnitt“ galt nach „im“ als unbekanntes Merkmal und ergab die Absage.
def test_im_durchschnitt_ist_kein_merkmal(gerechnet: Verbindung) -> None:
    lauf_ausfuehren(gerechnet, "2024-10", "v1")
    daten = uc4_antwort(gerechnet, "Wie viele Personen waren im Herbst 2024 in Wien im Schnitt beschäftigt?")
    assert daten["zahlen"] and daten["text"].startswith("Im Durchschnitt waren es")
