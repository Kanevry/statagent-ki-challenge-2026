"""Agenten-Werkzeuge nach Review !13: keine Einzeldaten an das Modell (Punkt 2), Auswertungs-Regelsätze (Punkt 4).

Kein echtes Modell: ein Fake liefert die Antworten, die Datenbank ist die Wegwerf-DB der Fixtures.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from types import SimpleNamespace
from typing import Any

import pytest

from statagent.agenten.koordinator import agent_ausfuehren
from statagent.agenten.regelaenderung import einspielen
from statagent.agenten.vorschlag import vorschlag_lesen, vorschlag_schema_einrichten
from statagent.agenten.werkzeuge import MINDESTZELLE, AbfrageVerweigert, roh_kennzahlen, sql_lesen
from statagent.db import Verbindung
from statagent.sonderauswertung import NichtFreigegeben, auswertung_regel

#: Wie in test_sonderauswertung.py: die Definition von Auftrag 3.
MINISTERIUM = {
    "monate": 1,
    "qualifikationen": ["ArbeiterDV", "ArbeiterFD"],
    "oenace": "C",
    "altcodes_als_abschnitt": [],
    "mindesttage": 30,
    "datenstand": "juengste_lieferung_je_tag",
    "angehaltene_lieferungen": "ueberspringen",
    "bereinigung_regelsatz": "v1",
    "geburtsjahr_unplausibel": "Unbekannt",
    "felder": ["PERSON_ID", "GESCHLECHT", "GEBURTSJAHR", "TAGE"],
    "datei": "ministerium_{berichtsmonat}.csv",
    "trennzeichen": ";",
}
AUFTRAG_3 = "Personentage für das Ministerium als eigene Auswertung"


def _modell(rolle: str, antwort: dict[str, Any]) -> Any:
    """Steht für plattform.llm.complete: Koordinator wählt die Rolle, die Rolle antwortet fest."""
    antworten = {"agent.koordinator": {"rolle": rolle, "auftrag": "fest"}, f"agent.{rolle}": antwort}

    def complete(nachrichten: list[dict[str, str]], schema: Any = None, zweck: str = "", **_: Any) -> Any:
        daten = antworten[zweck]
        return SimpleNamespace(text=json.dumps(daten), json=daten, provider="mock", modell="fake-1")

    return complete


def _auswertungsregel(name: str) -> dict[str, Any]:
    return {
        "typ": "regel_neu",
        "regelsatz_ziel": "ministerium",
        "neue_regeln": [
            {
                "name": name,
                "typ": "zaehl",
                "art": "personentage",
                "reihenfolge": 10,
                "parameter": [{"schluessel": k, "wert": w} for k, w in MINISTERIUM.items()],
                "beschreibung": "Tage je Person in der Herstellung, Arbeiter DV und FD",
                "begruendung": "Auftrag 3",
                "grundlage": "Auftrag 3",
            }
        ],
        "begruendung": "Änderungsauftrag 3: Ministeriums-Lieferung.",
    }


@pytest.fixture
def agent_conn(conn: Verbindung) -> Iterator[Verbindung]:
    vorschlag_schema_einrichten(conn)
    yield conn


def _anzahl(conn: Verbindung, abfrage: str) -> int:
    z = conn.execute(abfrage.encode()).fetchone()
    assert z is not None
    return int(str(z["n"]))


# --- Punkt 2: freie Abfragen erreichen roh.* und bereinigt.* nicht -------------------------------------


@pytest.mark.parametrize(
    "abfrage",
    [
        # Fängt: count(*) OVER() gilt als Aggregatwort und lässt bis zu 200 Geburtsdaten durch.
        "SELECT geburtsdatum, count(*) OVER() FROM roh.lieferung",
        # Fängt: der Alias „count“ gilt als Aggregatwort, die Abfrage liefert Einzelsätze.
        "SELECT geburtsdatum AS count FROM roh.lieferung",
        # Fängt: Schemaname in Anführungszeichen, groß und mit Leerraum geschrieben.
        'SELECT geburtsdatum FROM "ROH" . "lieferung"',
        # Fängt: bereinigt.* (Abschnitte je Verhältnis) mit Aggregat.
        "SELECT geschlecht, count(*) FROM bereinigt.abschnitt GROUP BY 1",
        # Fängt: search_path innerhalb der Abfrage umstellen.
        "SELECT set_config('search_path', 'roh', true) AS p",
        # Fängt: Dateien lesen und Abfragen als Text (Name zusammengesetzt, damit die Wortsperre nicht greift).
        "SELECT pg_read_file('postmaster.pid')",
        "SELECT query_to_xml('select * from r' || 'oh.lieferung', true, true, '')",
        # Fängt: pg_stats zeigt häufigste Werte jeder Spalte, auch von roh.lieferung.
        "SELECT most_common_vals::text AS w FROM pg_stats",
    ],
)
def test_freie_abfrage_auf_einzelsaetze_wird_verweigert(agent_conn: Verbindung, abfrage: str) -> None:
    with pytest.raises(AbfrageVerweigert):
        sql_lesen(agent_conn, abfrage)


def test_unqualifizierte_tabelle_landet_nicht_in_roh(agent_conn: Verbindung) -> None:
    # Fängt: die Verbindung hat search_path = roh gesetzt; ohne SET LOCAL search_path liefe
    # „FROM lieferung“ auf roh.lieferung und gäbe Geburtsdaten aus.
    agent_conn.execute("SET search_path = roh, public")
    try:
        with pytest.raises(AbfrageVerweigert):
            sql_lesen(agent_conn, "SELECT geburtsdatum FROM lieferung")
    finally:
        agent_conn.execute("RESET search_path")


def test_erlaubte_abfrage_auf_stat_liefert_zeilen(agent_conn: Verbindung) -> None:
    # Fängt: eine zu breite Sperre, die auch die freien Schemas (stat, meta, klassifikation) blockiert.
    ergebnis = sql_lesen(agent_conn, "SELECT * FROM stat.klass_qualifikation ORDER BY 1")
    assert ergebnis["zeilen"] and not ergebnis["abgeschnitten"]
    unqualifiziert = sql_lesen(agent_conn, "SELECT count(*) AS n FROM regel")  # search_path: meta
    assert int(unqualifiziert["zeilen"][0]["n"]) > 0


@pytest.mark.parametrize(
    "abfrage",
    [
        "SELECT * FROM meta.pruefung_treffer",
        "SELECT to_jsonb(t) AS j FROM meta.revision_ursache t",
        "SELECT r FROM meta.rueckfrage r",
    ],
)
def test_tabellen_mit_beispiel_kennungen_sind_gesperrt(agent_conn: Verbindung, abfrage: str) -> None:
    # Fängt: VVH_IDs in der Spalte „beispiele“ (Prüftreffer, Revisionsursachen, Rückfragen) gelangen über eine
    # freie Abfrage auf meta ans Modell, auch als ganze Zeile oder JSON (Session-Review, Befund 3).
    with pytest.raises(AbfrageVerweigert, match="Kennungen"):
        sql_lesen(agent_conn, abfrage)


def test_roh_kennzahlen_ohne_kennungen_und_ohne_kleine_zellen(agent_conn: Verbindung) -> None:
    # Fängt: Kennungen (PERSON_ID, VVH_ID) oder Zellen 1 bis 4 in den Rohdaten-Kennzahlen für das Modell.
    k = roh_kennzahlen(agent_conn, "2024-08")
    text = json.dumps(k, ensure_ascii=False)
    assert "person_id" not in text.lower() and "vvh_id" not in text.lower()
    kennungen = agent_conn.execute(
        "SELECT vvh_id AS k FROM roh.lieferung WHERE lieferung = '2024-08' AND vvh_id IS NOT NULL "
        "UNION SELECT person_id FROM roh.lieferung WHERE lieferung = '2024-08' AND person_id IS NOT NULL"
    ).fetchall()
    assert kennungen and not any(f'"{z["k"]}"' in text for z in kennungen)

    def zahlen(x: object) -> Iterator[int]:
        if isinstance(x, dict):
            for w in x.values():
                yield from zahlen(w)
        elif isinstance(x, int) and not isinstance(x, bool):
            yield x

    assert not [n for n in zahlen(k) if 0 < n < MINDESTZELLE]
    gesamt = _anzahl(agent_conn, "SELECT count(*) AS n FROM roh.lieferung WHERE lieferung = '2024-08'")
    assert k["zeilen"] == gesamt and set(k["je_code"]) == {"qual", "oenace", "bundesland", "geschlecht"}
    with pytest.raises(AbfrageVerweigert):
        roh_kennzahlen(agent_conn, "2024-08' OR true --")


# --- Punkt 4: Auswertungs-Regelsätze ------------------------------------------------------------------


def test_auswertungsregel_im_regelsatz_ministerium_wird_angenommen_und_eingespielt(
    agent_conn: Verbindung,
) -> None:
    # Fängt: CHECK ^v[0-9]+$ und „Zählregeln je Art genau einmal“ (global) verweigerten Auftrag 3.
    conn = agent_conn
    ergebnis = agent_ausfuehren(
        conn, AUFTRAG_3, complete=_modell("datenmanagement", _auswertungsregel("A3_ministerium_personentage"))
    )
    assert ergebnis.abgelehnt is None and ergebnis.vorschlag_id is not None
    v = vorschlag_lesen(conn, ergebnis.vorschlag_id)
    assert (v.typ, v.regelsatz_ziel, v.regelsatz_basis) == ("regel_neu", "ministerium", "ministerium")
    with conn.transaction():
        einspielen(
            conn,
            vorschlag_id=v.id,
            typ=v.typ,
            regelsatz_ziel=v.regelsatz_ziel,
            regelsatz_basis=v.regelsatz_basis,
            aenderungen=v.aenderungen,
            anweisung=AUFTRAG_3,
            begruendung="Änderungsauftrag 3",
        )
    # Nur die eine Regel, keine Kopie von v1. Der Auswertungscode findet genau sie und verlangt die Freigabe.
    assert _anzahl(conn, "SELECT count(*) AS n FROM meta.regel WHERE regelsatz = 'ministerium'") == 1
    z = conn.execute("SELECT name, parameter FROM meta.regel WHERE regelsatz = 'ministerium'").fetchone()
    assert z == {"name": "A3_ministerium_personentage", "parameter": MINISTERIUM}
    with pytest.raises(NichtFreigegeben, match="A3_ministerium_personentage"):
        auswertung_regel(conn, "ministerium")

    # Fängt: eine zweite Zählregel derselben Art im selben Regelsatz.
    vorher = _anzahl(conn, "SELECT count(*) AS n FROM meta.vorschlag")
    zweite = agent_ausfuehren(
        conn, AUFTRAG_3, complete=_modell("datenmanagement", _auswertungsregel("A3_ministerium_zweite"))
    )
    assert zweite.abgelehnt is not None and "genau einmal" in zweite.abgelehnt
    assert _anzahl(conn, "SELECT count(*) AS n FROM meta.vorschlag") == vorher


def test_auswertungsregel_ohne_vollstaendige_parameter_wird_verweigert(agent_conn: Verbindung) -> None:
    # Fängt: eine Auswertungsregel, der ein Parameter fehlt, den sonderauswertung.py liest.
    antwort = _auswertungsregel("A3_ministerium_personentage")
    antwort["neue_regeln"][0]["parameter"] = [
        p for p in antwort["neue_regeln"][0]["parameter"] if p["schluessel"] != "mindesttage"
    ]
    ergebnis = agent_ausfuehren(agent_conn, AUFTRAG_3, complete=_modell("datenmanagement", antwort))
    assert ergebnis.abgelehnt is not None and "mindesttage" in ergebnis.abgelehnt


def test_ziel_v1_mit_veroeffentlichtem_monat_bleibt_verweigert(agent_conn: Verbindung) -> None:
    # Fängt: die Öffnung für Auswertungs-Regelsätze lockert den Schutz veröffentlichter Monate in v<Zahl>.
    agent_conn.execute(
        "INSERT INTO meta.lauf (lieferung, regelsatz, status, ergebnis_status) "
        "VALUES ('2024-08', 'v1', 'fertig', 'endgueltig')"
    )
    antwort = {
        "typ": "regel_aendern",
        "regelsatz_ziel": "v1",
        "aenderungen": [
            {
                "regel_name": "R6_beschaeftigungskategorie",
                "parameter_neu": [{"schluessel": "qualifikation", "wert": "beschaeftigungskategorie"}],
            }
        ],
        "begruendung": "Änderungsauftrag 1",
    }
    ergebnis = agent_ausfuehren(agent_conn, "DV und FD zusammen", complete=_modell("klassifikation", antwort))
    assert ergebnis.abgelehnt is not None and "veröffentlichte Monate" in ergebnis.abgelehnt
    assert _anzahl(agent_conn, "SELECT count(*) AS n FROM meta.vorschlag") == 0
