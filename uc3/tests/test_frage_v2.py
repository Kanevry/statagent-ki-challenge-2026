"""Datenanfragen im Regelsatz v2: Zählung je Monat, gleiche Zahl wie die Aggregattabelle (Auftrag Lead, b-uc3-b6)."""

from __future__ import annotations

import pytest

from statagent.agenten.regelaenderung import regelsatz_sicherstellen
from statagent.db import Verbindung
from statagent.ergebnis import letzter_lauf, monatserster, monatsletzter
from statagent.frage import antwort_frage
from statagent.lauf import lauf_ausfuehren

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
        ("Frauenanteil im August 2024 nach Regelsatz v2", "nicht lesen"),
        ("Beschäftigte unter 25 Jahren im August 2024 nach Regelsatz v2", "nicht lesen"),
        ("Beschäftigte nach Altersgruppe im August 2024 nach Regelsatz v2", "nicht lesen"),
        ("Person 1234567 im August 2024 nach Regelsatz v2", "Einzeldaten"),
    ],
)
def test_v2_absagen(mit_v2: Verbindung, frage: str, wort: str) -> None:
    daten = antwort_frage(mit_v2, frage)
    assert daten["zahlen"] == [] and wort in daten["text"]
