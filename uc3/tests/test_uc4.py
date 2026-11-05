"""UC3-Adapter für UC4 (#106): Frage lesen ohne Modell, Zahl aus stat.stat_beschaeftigte, Beleg je Zahl."""

from __future__ import annotations

import subprocess
import sys
from typing import Any

import pytest

from statagent.db import Verbindung
from statagent.ergebnis import letzter_lauf, monatserster, monatsletzter
from statagent.uc4 import antwort_daten, monat_lesen

MONAT = "2024-08"  # erste Fixture-Lieferung
EINZELDATEN = ("person_id", "vvh_id", "geburtsdatum", "roh.", "bereinigt.")


def _lauf(conn: Verbindung) -> None:
    from statagent import lauf

    lauf.lauf_ausfuehren(conn, MONAT, regelsatz="v1", gestartet_von=None)


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


def _belege_gueltig(daten: dict[str, Any]) -> None:
    for zahl in daten["zahlen"]:
        assert 0 <= zahl["beleg"] < len(daten["belege"])


# Fängt: Monatsname, Abkürzung oder Zahlform wird falsch oder gar nicht als JJJJ-MM erkannt.
@pytest.mark.parametrize(
    ("frage", "monat"),
    [
        ("Wie viele Beschäftigte im März 2025?", "2025-03"),
        ("Beschäftigte 2025-03", "2025-03"),
        ("Stand 3/2025 bitte", "2025-03"),
        ("Jänner 2025 in Wien", "2025-01"),
        ("im Dez. 2024", "2024-12"),
        ("Wie viele Beschäftigte gibt es?", None),
        ("im 2025-13", None),
    ],
)
def test_monat_lesen(frage: str, monat: str | None) -> None:
    assert monat_lesen(frage) == monat


# Fängt: Monatsname und JJJJ-MM liefern verschiedene Zahlen oder weichen von der Summe der Aggregattabelle ab.
def test_monatsformen_gleich_der_direkten_summe(conn: Verbindung) -> None:
    _lauf(conn)
    als_name = antwort_daten(conn, "Wie viele Beschäftigungsverhältnisse gab es im August 2024?")
    als_iso = antwort_daten(conn, "Beschäftigte 2024-08")
    assert als_name["zahlen"][0]["wert"] == als_iso["zahlen"][0]["wert"] == _direkt(conn) > 0
    assert als_name["modell"] is None and als_name["uc"] == "uc3"
    assert "vorläufig" in als_name["text"] or "endgültig" in als_name["text"]


# Fängt: Ausprägung oder Gliederung wird nicht aus der Klassifikation gelesen, Beleg-Index zeigt ins Leere,
# oder der SQL-Text enthält Einzeldaten-Spalten.
def test_auspraegung_gliederung_beleg_und_sql(conn: Verbindung) -> None:
    _lauf(conn)
    wien = antwort_daten(conn, "Beschäftigte in Wien im August 2024")
    assert wien["zahlen"][0]["wert"] == _direkt(conn, " AND region = %s", ("9",))
    gesamt = _direkt(conn)
    je_land = antwort_daten(conn, "Beschäftigte nach Bundesland, August 2024")
    assert len(je_land["zahlen"]) > 1
    assert sum(z["wert"] for z in je_land["zahlen"]) == gesamt
    for daten in (wien, je_land):
        _belege_gueltig(daten)
        beleg = daten["belege"][0]
        assert beleg["quelle"] == "stat.stat_beschaeftigte" and beleg["monat"] == MONAT
        assert beleg["ref"].startswith("meta.lauf/")
        assert not any(spalte in beleg["sql"] for spalte in EINZELDATEN)


# Fängt: Frage ohne Monat oder Monat ohne Lauf wirft, statt leer zu antworten (der Router liefe nicht weiter).
def test_ohne_monat_oder_lauf_leer(conn: Verbindung) -> None:
    for frage in ("Wie viele Beschäftigte gibt es?", "Beschäftigte im Dezember 2030"):
        daten = antwort_daten(conn, frage)
        assert daten["zahlen"] == [] and daten["belege"] == [] and daten["text"]


# Fängt: der Adapter zieht plattform.llm mit (Regel R2, UC3 rechnet ohne Modell).
def test_uc4_importiert_kein_llm() -> None:
    lauf = subprocess.run(
        [sys.executable, "-c", "import sys, statagent.uc4; print('plattform.llm' in sys.modules)"],
        capture_output=True,
        text=True,
        timeout=60,
        check=True,
    )
    assert lauf.stdout.strip() == "False"


# Fängt: das dict passt nicht zum Vertrag UcAntwort (#96, läuft erst nach dem Merge von !30).
def test_vertrag_ucantwort(conn: Verbindung) -> None:
    antwortform = pytest.importorskip("plattform.antwortform")
    _lauf(conn)
    for frage in ("Frauen im August 2024", "nach Geschlecht 2024-08", "ohne Monat"):
        antwortform.UcAntwort.model_validate(antwort_daten(conn, frage))


# Fängt (#125): „Männer und Frauen“ liefert nur Männer, weil nur die erste Ausprägung zählt; die Summe fehlt
# oder weicht von den Teilen ab; eine Teilzahl teilt sich Beleg und SQL mit einer anderen.
def test_mehrere_auspraegungen_je_zahl_mit_eigenem_beleg_und_summe(conn: Verbindung) -> None:
    _lauf(conn)
    daten = antwort_daten(conn, "Männer und Frauen in Wien im August 2024")
    maenner = _direkt(conn, " AND region = %s AND geschlecht = %s", ("9", "M"))
    frauen = _direkt(conn, " AND region = %s AND geschlecht = %s", ("9", "W"))
    assert [z["wert"] for z in daten["zahlen"]] == [maenner, frauen, maenner + frauen]
    assert maenner > 0 and frauen > 0
    assert [z["beleg"] for z in daten["zahlen"]] == [0, 1, 2]
    assert len({b["sql"] for b in daten["belege"]}) == 3
    assert "IN ('M', 'W')" in daten["belege"][2]["sql"]
    assert "zusammen" in daten["zahlen"][2]["bezeichnung"]
    _belege_gueltig(daten)
    laender = antwort_daten(conn, "Wien, Tirol und Salzburg im August 2024")
    assert len(laender["zahlen"]) == 4 and len(laender["belege"]) == 4


# Fängt (#95, 95-2/95-3): Rückfrage ohne Monat in Fachsprache, „(Lauf N)“ im Text statt im Beleg, und kein
# Hinweis, dass bei „Beschäftigte“ Beschäftigungsverhältnisse gezählt werden.
def test_text_alltagssprache_lauf_im_beleg(conn: Verbindung) -> None:
    assert antwort_daten(conn, "Beschäftigte in Tirol")["text"] == (
        "Es ist noch kein Monat gerechnet, darum gibt es noch keine Zahl."
    )
    _lauf(conn)
    stand = letzter_lauf(conn, MONAT)
    assert stand is not None
    daten = antwort_daten(conn, "Beschäftigte im August 2024")
    assert "Lauf" not in daten["text"] and "—" not in daten["text"]
    assert daten["belege"][0]["ref"].startswith(f"meta.lauf/{stand.lauf_id} ")
    assert daten["text"].count("eine Person kann mehrere haben") == 1
    ohne = antwort_daten(conn, "Beschäftigungsverhältnisse im August 2024")
    assert "eine Person kann mehrere haben" not in ohne["text"]


# Fängt: Regelsatz v2 liefert 0, weil die Abfrage fest „Stichtag“ sucht, obwohl die Bestandsregel über das
# Monat zählt; ein Kategoriefilter liefert 0, weil v2 die Kategorie schon in s.qualifikation trägt.
def test_v2_zeitraumart_und_kategorie_aus_den_regeln(conn: Verbindung) -> None:
    from statagent.agenten.regelaenderung import regelsatz_sicherstellen

    _lauf(conn)
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
        conn.execute(
            """INSERT INTO stat.stat_beschaeftigte
               SELECT 'Monat', s.zeitraum_von, s.zeitraum_bis, s.region, s.oenace, s.oenace_version, s.geschlecht,
                      q.beschaeftigungskategorie, s.alter, s.variable, sum(s.wert), s.status, s.stand,
                      'v2', 'test-v2', l2.id
               FROM stat.stat_beschaeftigte s
               JOIN stat.klass_qualifikation q ON q.code = s.qualifikation
               JOIN meta.lauf l2 ON l2.regelsatz = 'v2' AND l2.lieferung = %s
               WHERE s.regelsatz = 'v1' AND s.zeitraum_bis BETWEEN %s AND %s
               GROUP BY 2, 3, 4, 5, 6, 7, 8, 9, 10, 12, 13, 16""",
            (MONAT, monatserster(MONAT), monatsletzter(MONAT)),
        )
    gesamt = antwort_daten(conn, "Beschäftigte im August 2024", regelsatz="v2")
    assert gesamt["zahlen"][0]["wert"] == _direkt(conn) > 0
    assert "s.zeitraum_art = 'Monat'" in gesamt["belege"][0]["sql"]
    assert "irgendwann im Monat" in gesamt["text"] and "(DV)" in gesamt["text"]
    arbeiter = antwort_daten(conn, "Arbeiter im August 2024", regelsatz="v2")
    soll = _direkt(conn, " AND qualifikation IN ('ArbeiterDV', 'ArbeiterFD')")
    assert arbeiter["zahlen"][0]["wert"] == soll > 0
    assert "klass_qualifikation" not in arbeiter["belege"][0]["sql"]
    assert "irgendwann im Monat" not in antwort_daten(conn, "Beschäftigte im August 2024")["text"]


def _monat_direkt(
    conn: Verbindung, monat: str, bedingung: str = "", parameter: tuple[object, ...] = ()
) -> int:
    stand = letzter_lauf(conn, monat)
    assert stand is not None
    zeile = conn.execute(
        (
            "SELECT COALESCE(sum(wert), 0) AS wert FROM stat.stat_beschaeftigte WHERE regelsatz = 'v1'"
            " AND regelstand = %s AND zeitraum_art = 'Stichtag' AND variable = 'Beschaeftigungsverhaeltnisse'"
            " AND zeitraum_bis BETWEEN %s AND %s" + bedingung
        ).encode(),
        (stand.regelstand, monatserster(monat), monatsletzter(monat), *parameter),
    ).fetchone()
    assert zeile is not None
    return int(str(zeile["wert"]))


@pytest.fixture
def vier_monate(conn: Verbindung) -> Verbindung:
    from statagent import lauf

    for monat in ("2024-08", "2024-09", "2024-10", "2024-11"):
        lauf.lauf_ausfuehren(conn, monat, regelsatz="v1", gestartet_von=None)
    return conn


# Fängt (Owner 05.11., „Sommer“): eine Jahreszeit liefert keine Zahl, die Monate weichen von der Aggregattabelle
# ab, der Durchschnitt ist falsch gerundet, oder der Text verschweigt, welche Monate gemeint sind.
def test_jahreszeit_monate_einzeln_und_durchschnitt(vier_monate: Verbindung) -> None:
    conn = vier_monate
    daten = antwort_daten(conn, "Wie viele Beschäftigte gab es im Herbst 2024 in Wien?")
    monate_ = ("2024-09", "2024-10", "2024-11")
    soll = [_monat_direkt(conn, m, " AND region = %s", ("9",)) for m in monate_]
    mittel = (2 * sum(soll) + 3) // 6
    assert [z["wert"] for z in daten["zahlen"]] == [*soll, mittel] and min(soll) > 0
    assert daten["text"].startswith("Herbst 2024 heißt hier September bis November 2024.")
    assert f"Im Durchschnitt waren es {mittel:,}.".replace(",", ".") in daten["text"]
    assert [b["monat"] for b in daten["belege"][:3]] == list(monate_)
    assert "round(avg(" in daten["belege"][3]["sql"] and "region = '9'" in daten["belege"][3]["sql"]
    _belege_gueltig(daten)


# Fängt: ein Zeitraum ganz oder teils außerhalb der Daten liefert nichts, statt den vorhandenen Teil zu nennen;
# ohne Zeitangabe gibt es keine Zahl statt des jüngsten Monats.
def test_ausserhalb_der_daten_und_ohne_zeitangabe(vier_monate: Verbindung) -> None:
    conn = vier_monate
    vorher = antwort_daten(conn, "Beschäftigte im Juli 2024")
    assert vorher["zahlen"] == [] and "keine Daten, nur für August bis November 2024." in vorher["text"]
    assert "Meinen Sie „Beschäftigte im November 2024“?" in vorher["text"] and "UC3" not in vorher["text"]
    sommer = antwort_daten(conn, "Beschäftigte im Sommer 2024")
    assert [z["wert"] for z in sommer["zahlen"]] == [_monat_direkt(conn, "2024-08")]
    assert "Daten gibt es nur für August bis November 2024, darum zählt hier August 2024." in sommer["text"]
    ohne = antwort_daten(conn, "Wie viele Beschäftigte gibt es in Tirol?")
    assert [z["wert"] for z in ohne["zahlen"]] == [_monat_direkt(conn, "2024-11", " AND region = %s", ("7",))]
    assert ohne["text"].startswith("Ohne Zeitangabe zeigen wir den jüngsten Monat: November 2024.")
    letzter = antwort_daten(conn, "Beschäftigte letzten Monat")
    assert letzter["zahlen"][0]["wert"] == _monat_direkt(conn, "2024-11")
