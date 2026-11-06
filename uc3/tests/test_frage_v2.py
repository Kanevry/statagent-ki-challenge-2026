"""Datenanfragen im Regelsatz v2: Zählung je Monat, gleiche Zahl wie die Aggregattabelle (Auftrag Lead, b-uc3-b6)."""

from __future__ import annotations

import psycopg
import pytest

from statagent import frage as frage_modul
from statagent.agenten.regelaenderung import regelsatz_sicherstellen
from statagent.db import Verbindung
from statagent.ergebnis import letzter_lauf, monatserster, monatsletzter
from statagent.frage import antwort_frage, nicht_auswertbar
from statagent.lauf import lauf_ausfuehren
from statagent.uc4 import uc4_antwort

MONAT = "2024-08"


@pytest.fixture
def mit_v2(conn: Verbindung) -> Verbindung:
    lauf_ausfuehren(conn, MONAT, "v1")
    with conn.transaction():
        regelsatz_sicherstellen(conn, "v2", "v1")
        conn.execute(
            """UPDATE meta.regel SET parameter = parameter || '{"zeitraum_art": "Monat"}'::jsonb
               WHERE regelsatz = 'v2' AND typ = 'zaehl' AND art = 'bestand'"""
        )
        conn.execute(
            """UPDATE meta.regel SET parameter = '{"qualifikation": "beschaeftigungskategorie"}'::jsonb
               WHERE regelsatz = 'v2' AND typ = 'zaehl' AND art = 'dimension'"""
        )
        conn.execute(
            """INSERT INTO meta.lauf (lieferung, regelsatz, regelstand, status, ergebnis_status, beendet_am, meldung)
               SELECT lieferung, 'v2', 'test-v2', 'fertig', ergebnis_status, beendet_am, 'Test v2'
               FROM meta.lauf WHERE regelsatz = 'v1' AND lieferung = %s AND status IN ('fertig', 'unveraendert')
               ORDER BY id DESC LIMIT 1""",
            (MONAT,),
        )
        # Absichtlich anderer Wert als v1: Die Zahl muss aus den v2-Zeilen kommen.
        conn.execute(
            """INSERT INTO stat.stat_beschaeftigte
               SELECT 'Monat', s.zeitraum_von, s.zeitraum_bis, s.region, s.oenace, s.oenace_version, s.geschlecht,
                      q.beschaeftigungskategorie, s.alter, s.variable, sum(s.wert) + 1, s.status, s.stand,
                      'v2', 'test-v2', l2.id
               FROM stat.stat_beschaeftigte s
               JOIN stat.klass_qualifikation q ON q.code = s.qualifikation
               JOIN meta.lauf l2 ON l2.regelsatz = 'v2' AND l2.lieferung = %s
               WHERE s.regelsatz = 'v1' AND s.zeitraum_bis BETWEEN %s AND %s
               GROUP BY 2, 3, 4, 5, 6, 7, 8, 9, 10, 12, 13, 16""",
            (MONAT, monatserster(MONAT), monatsletzter(MONAT)),
        )
    return conn


def _summe(conn: Verbindung, regelsatz: str, art: str) -> int:
    stand = letzter_lauf(conn, MONAT, regelsatz)
    assert stand is not None
    zeile = conn.execute(
        "SELECT sum(wert) AS n FROM stat.stat_beschaeftigte WHERE regelsatz = %s AND regelstand = %s"
        " AND zeitraum_art = %s AND zeitraum_bis BETWEEN %s AND %s",
        (regelsatz, stand.regelstand, art, monatserster(MONAT), monatsletzter(MONAT)),
    ).fetchone()
    assert zeile is not None
    return int(str(zeile["n"]))


# Fängt: Eine Frage nach v2 gab die v1-Zahl oder keine Zahl (gemessen b-uc3-b6: alle v2-Zeilen sind „Monat“).
@pytest.mark.parametrize(
    "frage",
    [
        "Beschäftigte im August 2024 nach Regelsatz v2",
        "Beschäftigte im August 2024 im Regelsatz 2",
        "Beschäftigte im August 2024 nach den Änderungsaufträgen",
        "Beschäftigte im ganzen Monat August 2024",
    ],
)
def test_frage_nach_v2_gibt_die_monatszahl(mit_v2: Verbindung, frage: str) -> None:
    daten = antwort_frage(mit_v2, frage)
    soll = _summe(mit_v2, "v2", "Monat")
    assert [z["wert"] for z in daten["zahlen"]] == [soll] != [_summe(mit_v2, "v1", "Stichtag")]
    assert daten["text"].startswith("Nach Regelsatz v2: ")
    assert "s.zeitraum_art = 'Monat'" in daten["belege"][0]["sql"] and "irgendwann im Monat" in daten["text"]


# Fängt: Der Schalter --regelsatz v2 sagt ab oder rechnet am Stichtag (Folge aus !192).
def test_schalter_regelsatz(mit_v2: Verbindung) -> None:
    soll = _summe(mit_v2, "v2", "Monat")
    assert [z["wert"] for z in antwort_frage(mit_v2, "Beschäftigte im August 2024", "v2")["zahlen"]] == [soll]


# Gegenfall: Ohne diese Wörter bleibt v1.
def test_ohne_v2_wort_bleibt_v1(mit_v2: Verbindung) -> None:
    daten = antwort_frage(mit_v2, "Beschäftigte im August 2024")
    assert [z["wert"] for z in daten["zahlen"]] == [_summe(mit_v2, "v1", "Stichtag")]
    assert "Nach Regelsatz v2" not in daten["text"]


# Fängt: Stichtag und Monat werden still gemischt; was der Weg nicht liest, bekommt keine Zahl.
@pytest.mark.parametrize(
    ("frage", "wort"),
    [
        ("Fluktuation im August 2024 nach Regelsatz v2", "nur im Regelsatz v1"),
        ("Frauenanteil im August 2024 nach Regelsatz v2", "gibt es nur Zahlen nach"),
        ("Beschäftigte unter 25 Jahren im August 2024 nach Regelsatz v2", "gibt es nur Zahlen nach"),
        ("Beschäftigte nach Altersgruppe im August 2024 nach Regelsatz v2", "gibt es nur Zahlen nach"),
        ("Person 1234567 im August 2024 nach Regelsatz v2", "Einzeldaten"),
    ],
)
def test_v2_absagen(mit_v2: Verbindung, frage: str, wort: str) -> None:
    daten = antwort_frage(mit_v2, frage)
    assert daten["zahlen"] == [] and wort in daten["text"]


# Fängt: „Was ist Regelsatz v2?“ bekam die Monatszahl, obwohl niemand nach einer Zahl gefragt hat.
@pytest.mark.parametrize(
    "frage",
    [
        "Was ist Regelsatz v2?",
        "Regelsatz v2",
        "Welche Änderungsaufträge gibt es?",
        "Wurde der Änderungsauftrag umgesetzt?",
        "Was steht im Änderungsauftrag?",
        "Was ist der Unterschied zwischen v1 und v2?",
        "Wie unterscheiden sich die Zahlen in v1 und v2?",
    ],
)
def test_frage_ohne_zahlwunsch_bekommt_die_erklaerung(mit_v2: Verbindung, frage: str) -> None:
    daten = antwort_frage(mit_v2, frage)
    assert daten["zahlen"] == []
    assert "irgendwann im Monat" in daten["text"] and "letzte Tag des Monats" in daten["text"]


# Gegenfall: Monat und Merkmal ohne Wort zum Bestand bleiben eine Frage nach der Zahl.
@pytest.mark.parametrize(
    "frage",
    ["August 2024 nach Regelsatz v2", "Frauen im August 2024 nach Regelsatz v2", "Regelsatz v2 August 2024"],
)
def test_monat_und_v2_bleibt_eine_zahl(mit_v2: Verbindung, frage: str) -> None:
    assert antwort_frage(mit_v2, frage)["zahlen"]


# Fängt: Ein unbekanntes Wort neben Monat und v2 bekam trotzdem den ganzen Bestand.
def test_unsinn_mit_v2_bekommt_keine_zahl(mit_v2: Verbindung) -> None:
    daten = antwort_frage(mit_v2, "asdf im August 2024 nach Regelsatz v2")
    assert daten["zahlen"] == [] and "gibt es nur Zahlen nach" in daten["text"]


# Fängt: Wer zu einem Monat beide Regelsätze nennt, bekam still nur einen oder eine Absage ohne Weg.
def test_beide_regelsaetze_einzeln_fragen(mit_v2: Verbindung) -> None:
    daten = antwort_frage(mit_v2, "Vergleiche August 2024 in v1 und v2")
    assert daten["zahlen"] == [] and "nur einen Regelsatz" in daten["text"]


# Fängt: „den ganzen Monat beschäftigt“ meint durchgehend; v2 zählt aber „irgendwann im Monat“, also etwas anderes.
@pytest.mark.parametrize(
    "frage",
    [
        "Wie viele waren den ganzen Monat August 2024 beschäftigt?",
        "Wie viele Beschäftigte haben ganze Monate gearbeitet im August 2024?",
        "Wie viele waren im August 2024 durchgehend beschäftigt?",
        "Wie viele waren den ganzen Monat August 2024 nach Regelsatz v2 beschäftigt?",
    ],
)
def test_durchgehend_beschaeftigt_gibt_keine_zahl(mit_v2: Verbindung, frage: str) -> None:
    daten = antwort_frage(mit_v2, frage)
    assert daten["zahlen"] == [] and daten["text"].startswith(
        "Wie lange jemand im Monat beschäftigt war, wertet"
    )
    assert "Darum gibt es" not in daten["text"] and "StatAgent beantwortet" in daten["text"]


# Fängt: Die v2-Angabe verdeckte die Gliederung, die Aufteilung fiel still weg.
def test_gliederung_neben_v2_bleibt(mit_v2: Verbindung) -> None:
    daten = antwort_frage(mit_v2, "Beschäftigte im August 2024 nach v2 und Bundesland")
    assert len(daten["zahlen"]) > 1


# Vorab-Lesung Bank !230, Punkt 1: Eine Verneinung schaltete trotzdem auf v2.
@pytest.mark.parametrize(
    "frage",
    [
        "Beschäftigte ohne Änderungsaufträge im August 2024",
        "Beschäftigte vor den Änderungsaufträgen im August 2024",
        "Beschäftigte im August 2024 nicht nach v2",
        "Beschäftigte im August 2024 statt nach Regelsatz v2",
        "Beschäftigte im August 2024 ohne die Änderungsaufträge",
        "Beschäftigte im August 2024 vor Umsetzung der Änderungsaufträge",
    ],
)
def test_verneinung_von_v2_gibt_keine_v2_zahl(mit_v2: Verbindung, frage: str) -> None:
    daten = antwort_frage(mit_v2, frage)
    assert daten["zahlen"] == [] and daten["text"].startswith("Ohne Änderungsaufträge gilt Regelsatz v1.")


# Vorab-Lesung Bank !230, Punkt 2: Österreichisch heißt es „das ganze Monat“.
@pytest.mark.parametrize(
    "frage",
    [
        "Wie viele waren das ganze Monat August 2024 beschäftigt?",
        "Wie viele waren ein ganzes Monat beschäftigt im August 2024?",
        "Wie viele haben im August 2024 ganzes Monat gearbeitet?",
    ],
)
def test_das_ganze_monat_heisst_durchgehend(mit_v2: Verbindung, frage: str) -> None:
    daten = antwort_frage(mit_v2, frage)
    assert daten["zahlen"] == [] and daten["text"].startswith("Wie lange jemand im Monat")


def test_ganzes_monat_ohne_verb_meint_v2(mit_v2: Verbindung) -> None:
    daten = antwort_frage(mit_v2, "Beschäftigte ganzes Monat August 2024")
    assert [z["wert"] for z in daten["zahlen"]] == [_summe(mit_v2, "v2", "Monat")]


# Vorab-Lesung Bank !230, Punkt 3: Das bloße Wort „Bundesland“ gab still die Summe.
def test_blosses_gliederungswort_teilt_auf(mit_v2: Verbindung) -> None:
    daten = antwort_frage(mit_v2, "August 2024 v2 Bundesland")
    assert len(daten["zahlen"]) > 1 and "aufgeteilt nach Bundesland" in daten["text"]


# Gegenfall: „Bundesland Wien“ ist ein Filter und keine Aufteilung.
def test_bundesland_mit_wert_bleibt_filter(mit_v2: Verbindung) -> None:
    daten = antwort_frage(mit_v2, "August 2024 v2 Bundesland Wien")
    assert len(daten["zahlen"]) == 1


# Fix-Liste !230, B1: „vor und nach“ und „mit und ohne“ meinen beide Regelsätze.
@pytest.mark.parametrize(
    "frage",
    [
        "Beschäftigte im August 2024 vor und nach den Änderungsaufträgen",
        "Beschäftigte im August 2024 mit und ohne v2",
    ],
)
def test_vor_und_nach_fragt_beide(mit_v2: Verbindung, frage: str) -> None:
    daten = antwort_frage(mit_v2, frage)
    assert daten["zahlen"] == [] and "nur einen Regelsatz" in daten["text"]


# Fix-Liste !230, B2: Ein Regelsatz ohne Lauf fiel still auf die v1-Zahl zurück.
@pytest.mark.parametrize(
    "frage",
    ["Beschäftigte im August 2024 im Regelsatz v3", "Beschäftigte im August 2024 nach v3", "Regelsatz drei"],
)
def test_regelsatz_ohne_lauf_sagt_mit_namen_ab(mit_v2: Verbindung, frage: str) -> None:
    daten = antwort_frage(mit_v2, frage)
    assert (
        daten["zahlen"] == []
        and "Im Regelsatz v3 ist noch kein Monat gerechnet." in daten["text"]
        and "v1 und v2" in daten["text"]
    )


# Fix-Liste !230, B2: Hat der Regelsatz einen Lauf, nimmt ihn derselbe Weg wie v2 (nach einer Änderung im Betrieb).
def test_regelsatz_mit_lauf_nimmt_den_weg(mit_v2: Verbindung, monkeypatch: pytest.MonkeyPatch) -> None:
    gefragt: list[str] = []

    def antwort(_conn: Verbindung, _frage: str, regelsatz: str) -> dict[str, str]:
        gefragt.append(regelsatz)
        return {"text": "gefragt"}

    monkeypatch.setattr(frage_modul, "_letzter_monat", lambda _conn, _regelsatz: "2024-08")
    monkeypatch.setattr(frage_modul, "_regelsatz_antwort", antwort)
    assert antwort_frage(mit_v2, "Beschäftigte im August 2024 im Regelsatz v3") == {"text": "gefragt"}
    assert gefragt == ["v3"]


# Fix-Liste !230, B3: „Wirft nie“ galt für den v2-Weg nicht.
def test_datenbankfehler_im_v2_weg_wirft_nicht(mit_v2: Verbindung, monkeypatch: pytest.MonkeyPatch) -> None:
    def fehler(*_args: object) -> None:
        raise psycopg.OperationalError("weg")

    monkeypatch.setattr(frage_modul, "antwort_daten", fehler)
    daten = antwort_frage(mit_v2, "Beschäftigte im August 2024 nach Regelsatz v2")
    assert daten["zahlen"] == [] and daten["text"] == frage_modul.NICHT_LESBAR


# Fix-Liste !230, B4: Ein Durchschnitt zu einem einzelnen Monat bekam die Monatszahl.
def test_durchschnitt_zu_einem_monat_sagt_ab(mit_v2: Verbindung) -> None:
    daten = antwort_frage(mit_v2, "Durchschnittliche Beschäftigte im August 2024 nach v2")
    assert daten["zahlen"] == [] and daten["text"] == frage_modul.DURCHSCHNITT_GRUND


# Fix-Liste !230, B5: Die Rückfrage zum Jahr sprach vom letzten Tag und zeigte Beispiele ohne v2.
def test_jahr_nach_v2_fragt_nach_dem_monat(mit_v2: Verbindung) -> None:
    daten = antwort_frage(mit_v2, "Beschäftigte 2024 nach v2")
    assert (
        daten["zahlen"] == []
        and "Regelsatz v2 wissen" in daten["text"]
        and "nach Regelsatz v2“" in daten["text"]
    )
    assert "letzten Tag" not in daten["text"]


# Fix-Liste !230, B6: „während des ganzen Monats“ meint durchgehend, „über das ganze Monat“ unsere v2-Zählung.
def test_waehrend_des_ganzen_monats_sagt_ab(mit_v2: Verbindung) -> None:
    daten = antwort_frage(mit_v2, "Wie viele waren während des ganzen Monats August 2024 beschäftigt?")
    assert daten["zahlen"] == [] and daten["text"].startswith("Wie lange jemand im Monat")


def test_ueber_das_ganze_monat_meint_v2(mit_v2: Verbindung) -> None:
    daten = antwort_frage(mit_v2, "Beschäftigte im August 2024, gezählt über das ganze Monat")
    assert [z["wert"] for z in daten["zahlen"]] == [_summe(mit_v2, "v2", "Monat")]


# Fix-Liste !230, B7: Der Satz „nur Zahlen nach Bundesland“ widersprach einer Frage nach zwei Bundesländern.
def test_zwei_bundeslaender_bekommen_den_passenden_satz(mit_v2: Verbindung) -> None:
    daten = antwort_frage(mit_v2, "Beschäftigte in Wien und Tirol im August 2024 nach v2")
    assert daten["zahlen"] == [] and "mehrere" in daten["text"] and "nur Zahlen nach" not in daten["text"]


def test_zeitreihe_sagt_nur_ein_monat(mit_v2: Verbindung) -> None:
    daten = antwort_frage(mit_v2, "Zeitreihe der Beschäftigten 2024 nach v2")
    assert daten["zahlen"] == [] and daten["text"].startswith(
        "Fragen Sie im Regelsatz v2 nach einem Monat oder Zeitraum, "
    )


# Fix-Liste !230, B8: zwei Sätze, und die Absage ist keine Rückfrage.
def test_fluktuation_absage_in_zwei_saetzen(mit_v2: Verbindung) -> None:
    daten = antwort_frage(mit_v2, "Fluktuation im August 2024 nach Regelsatz v2")
    assert daten["text"].startswith(
        "Die Fluktuation vergleicht zwei Stichtage. Es gibt sie nur im Regelsatz v1"
    )
    assert not daten["rueckfrage"]


# Gegenfall zu B4: Über mehrere Monate bleibt der Durchschnitt erlaubt, auch wenn der Zeitraum erst übersetzt wird.
def test_durchschnitt_ueber_einen_zeitraum_sagt_nicht_durchschnitte_ab(mit_v2: Verbindung) -> None:
    text = antwort_frage(mit_v2, "Durchschnitt August bis September 2024 nach v2")["text"]
    assert text != frage_modul.DURCHSCHNITT_GRUND


# Fix-Liste !230, B7: Auch ein Verlauf zweier Bundesländer bekommt den Grund statt der Erklärung zum Regelsatz.
def test_verlauf_zweier_bundeslaender_bekommt_den_grund(mit_v2: Verbindung) -> None:
    daten = antwort_frage(mit_v2, "Wie hat sich Wien gegenüber Tirol nach v2 entwickelt?")
    assert daten["zahlen"] == [] and "irgendwann im Monat" not in daten["text"]


# Bank 49: Ein Wort zwischen „vor“ und den Änderungsaufträgen schaltete trotzdem auf v2.
@pytest.mark.parametrize(
    "frage",
    [
        "Beschäftigte vor der Umsetzung der Änderungsaufträge im August 2024",
        "Beschäftigte ohne Berücksichtigung der Änderungsaufträge im August 2024",
    ],
)
def test_verneinung_mit_wort_dazwischen(mit_v2: Verbindung, frage: str) -> None:
    daten = antwort_frage(mit_v2, frage)
    assert daten["zahlen"] == [] and daten["text"].startswith("Ohne Änderungsaufträge gilt Regelsatz v1.")


# Gegenfall: Ein anderes „ohne“ neben v2 ist keine Verneinung.
def test_anderes_ohne_neben_v2_ist_keine_verneinung() -> None:
    assert frage_modul._V2_VERNEINT.search("Frauen ohne Kinder im August 2024 nach v2") is None


# Bank 49: Das Muster hatte kein Wortende, „Monatszahl“ und „Monatsbestand“ bekamen die Absage für durchgehend.
@pytest.mark.parametrize(
    "frage",
    [
        "Wie hoch ist die gesamte Monatszahl im August 2024?",
        "Wie hoch ist den gesamten Monatsbestand im August 2024?",
    ],
)
def test_monatszahl_ist_nicht_durchgehend(frage: str) -> None:
    assert nicht_auswertbar(frage) != frage_modul.DURCHGEHEND_GRUND


# Bank 49: /uc4 zeigte zu „Wien und Tirol … nach v2“ die v1-Zahlen ohne Hinweis (gemessen: 93.249 und 36.320).
def test_uc4_mehrere_werte_nach_v2_keine_v1_zahlen(mit_v2: Verbindung) -> None:
    daten = uc4_antwort(mit_v2, "Beschäftigte in Wien und Tirol im August 2024 nach v2")
    assert daten["zahlen"] == [] and "mehrere" in daten["text"]


# Gegenfall: Ohne Regelsatz in der Frage und als Schalter bleiben die Zahlen je Wert.
def test_uc4_mehrere_werte_ohne_wort_und_als_schalter(mit_v2: Verbindung) -> None:
    frage = "Beschäftigte in Wien und Tirol im August 2024"
    v1 = uc4_antwort(mit_v2, frage)["zahlen"]
    v2 = uc4_antwort(mit_v2, frage, "v2")["zahlen"]
    assert len(v1) == 3 and len(v2) == 3 and [z["wert"] for z in v1] != [z["wert"] for z in v2]


# Bank 49: „bevor“ fehlte bei der Verneinung, „vor oder nach“ und „Umsetzung“ bei beiden Regelsätzen.
def test_bevor_ist_eine_verneinung(mit_v2: Verbindung) -> None:
    daten = antwort_frage(mit_v2, "Beschäftigte im August 2024, bevor die Änderungsaufträge umgesetzt wurden")
    assert daten["zahlen"] == [] and daten["text"].startswith("Ohne Änderungsaufträge gilt Regelsatz v1.")


@pytest.mark.parametrize(
    "frage",
    [
        "Beschäftigte im August 2024 vor oder nach den Änderungsaufträgen",
        "Beschäftigte im August 2024 vor und nach Umsetzung der Änderungsaufträge",
    ],
)
def test_vor_oder_nach_mit_umsetzung_fragt_beide(mit_v2: Verbindung, frage: str) -> None:
    daten = antwort_frage(mit_v2, frage)
    assert daten["zahlen"] == [] and "nur einen Regelsatz" in daten["text"]


# Bank 49: Ein einzelner gerechneter Regelsatz steht in der Einzahl.
def test_regelsatz_ohne_lauf_einzahl(conn: Verbindung) -> None:
    conn.execute("DELETE FROM meta.lauf WHERE regelsatz <> 'v1'")
    conn.execute(
        "INSERT INTO meta.lauf (lieferung, regelsatz, regelstand, status) VALUES ('2024-08', 'v1', 'x', 'fertig')"
    )
    text = antwort_frage(conn, "Beschäftigte im August 2024 im Regelsatz v3")["text"]
    assert text == "Im Regelsatz v3 ist noch kein Monat gerechnet. Es gibt Zahlen im Regelsatz v1."


# Bank 49: Der Satz zur Zeitreihe verweist auf einen Zeitraum, den es im Regelsatz v2 auch gibt.
def test_beispiel_der_zeitreihen_absage_rechnet(mit_v2: Verbindung) -> None:
    daten = antwort_frage(mit_v2, "Beschäftigte August bis September 2024 nach Regelsatz v2")
    assert daten["zahlen"]


# Dasselbe im v2-Weg: Er liest die Frage in _regelsatz_antwort und ruft _filter sonst nur ohne die Prüfung.
@pytest.mark.parametrize(
    "frage",
    [
        "Frauen ohne Kinder im August 2024 nach v2",
        "Beschäftigte mit Kindern im August 2024 nach v2",
        "Betriebe im August 2024 nach v2",
    ],
)
def test_unbekanntes_wort_im_v2_weg(mit_v2: Verbindung, frage: str) -> None:
    assert antwort_frage(mit_v2, frage)["zahlen"] == []


def test_v2_gegenprobe_mit_zahl(mit_v2: Verbindung) -> None:
    assert antwort_frage(mit_v2, "Frauen im August 2024 nach v2")["zahlen"]


# Fängt (Blind-Runde, #186): Der v2-Weg nannte nur den Stand eines Monats, gefragt war die Veränderung.
@pytest.mark.parametrize(
    "frage",
    [
        "Wie hat sich die Zahl der Beschäftigten im August 2024 gegenüber dem Vormonat verändert, nach v2?",
        "Beschäftigte im Vormonat nach Regelsatz v2",
    ],
)
def test_v2_vergleich_mit_vormonat_ohne_zahl(mit_v2: Verbindung, frage: str) -> None:
    daten = antwort_frage(mit_v2, frage)
    assert daten["zahlen"] == [] and "einzeln fragen" in daten["text"]
