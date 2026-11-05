"""Agenten ohne Sprachmodell: ein Fake liefert die Modellantworten, die Datenbank ist die Fixture-DB.

Geprüft wird, was der Code garantiert: Rolle wählen, Vorschlag gegen die Regeln prüfen, Probe mit echten
Zahlen rechnen und zurückrollen, keine Einzeldaten in Werkzeugen und Vorschlägen, Rückfrage bei
Mehrdeutigkeit.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from types import SimpleNamespace
from typing import Any

import psycopg
import pytest

from statagent.agenten.koordinator import agent_ausfuehren
from statagent.agenten.vorschlag import diff_text, probe_rechnen, vorschlag_lesen, vorschlag_schema_einrichten
from statagent.agenten.werkzeuge import AbfrageVerweigert, schema_lesen, sql_lesen
from statagent.db import Verbindung

DV_FD = "Zählt freie Dienstverträge mit den Dienstverträgen zusammen"
STICHTAG_MONAT = "Zählt jedes Verhältnis, das irgendwann im Monat bestand, nicht nur am Stichtag"
BEAMTE = "Beamte ausschließen"
MEHRDEUTIG = "Mach die Statistik besser"


class FakeModell:
    """Steht für ``plattform.llm.complete``: Antwort je Zweck, jeder Aufruf wird mitgeschrieben."""

    def __init__(self, antworten: dict[str, dict[str, Any]]) -> None:
        self.antworten = antworten
        self.aufrufe: list[tuple[str, list[dict[str, str]]]] = []

    def __call__(
        self,
        nachrichten: list[dict[str, str]],
        schema: Any = None,
        stream: bool = False,
        provider: str | None = None,
        zweck: str = "",
    ) -> SimpleNamespace:
        self.aufrufe.append((zweck, nachrichten))
        daten = self.antworten[zweck]
        return SimpleNamespace(
            text=json.dumps(daten),
            json=daten,
            provider="mock",
            modell="fake-1",
            dauer_ms=0,
            tokens_in=0,
            tokens_out=0,
        )


def fake_dv_fd() -> FakeModell:
    return FakeModell(
        {
            "agent.koordinator": {"rolle": "klassifikation", "auftrag": "DV und FD gemeinsam ausweisen"},
            "agent.klassifikation": {
                "typ": "regel_aendern",
                "regelsatz_ziel": "v2",
                "aenderungen": [
                    {
                        "regel_name": "R6_beschaeftigungskategorie",
                        "parameter_neu": [
                            {"schluessel": "qualifikation", "wert": "beschaeftigungskategorie"}
                        ],
                    }
                ],
                "begruendung": "Änderungsauftrag 1: Arbeiter, Angestellte und Beamte ohne Trennung DV/FD.",
            },
        }
    )


@pytest.fixture
def agent_conn(conn: Verbindung) -> Iterator[Verbindung]:
    # meta.protokoll/meta.freigabe kommen aus plattform/sql/meta.sql (Vertrag P), eingespielt von db init.
    vorschlag_schema_einrichten(conn)
    yield conn


def _anzahl(conn: Verbindung, abfrage: str) -> int:
    z = conn.execute(abfrage.encode()).fetchone()
    assert z is not None
    return int(str(z["n"]))


def test_dv_und_fd_zusammen_wird_vorschlag_mit_probe(agent_conn: Verbindung) -> None:
    conn = agent_conn
    modell = fake_dv_fd()
    laeufe_vorher = _anzahl(conn, "SELECT count(*) AS n FROM meta.lauf")

    ergebnis = agent_ausfuehren(conn, DV_FD, complete=modell)

    assert [z for z, _ in modell.aufrufe] == ["agent.koordinator", "agent.klassifikation"]
    assert ergebnis.rolle == "klassifikation" and ergebnis.rueckfrage is None and ergebnis.abgelehnt is None
    assert (ergebnis.modell, ergebnis.provider) == ("fake-1", "mock")
    assert ergebnis.vorschlag_id is not None
    assert _anzahl(conn, "SELECT count(*) AS n FROM meta.vorschlag WHERE status = 'offen'") == 1
    v = vorschlag_lesen(conn, ergebnis.vorschlag_id)
    assert (v.typ, v.regelsatz_basis, v.regelsatz_ziel, v.anweisung) == ("regel_aendern", "v1", "v2", DV_FD)
    assert v.aenderungen[0]["parameter_alt"]["qualifikation"] == "code"
    assert v.aenderungen[0]["parameter_neu"]["qualifikation"] == "beschaeftigungskategorie"
    p = conn.execute(
        "SELECT status, vorschlag_typ, ref FROM meta.protokoll WHERE id = %s", (v.id,)
    ).fetchone()
    assert p == {"status": "offen", "vorschlag_typ": "regel", "ref": "v2/R6_beschaeftigungskategorie"}

    diff = diff_text(v)
    assert "R6_beschaeftigungskategorie" in diff
    assert '- parameter.qualifikation = "code"' in diff
    assert '+ parameter.qualifikation = "beschaeftigungskategorie"' in diff
    assert sum(z.startswith("  - ") for z in diff.splitlines()) == 1  # nur geänderte Parameter

    probe = probe_rechnen(conn, v.id, "2024-08")
    assert probe["vorher"]["gesamt"] == probe["nachher"]["gesamt"] > 0  # Umgruppierung, kein Verlust
    assert len(probe["vorher"]["je_merkmal"]["qualifikation"]) == 5
    assert set(probe["nachher"]["je_merkmal"]["qualifikation"]) == {"Angestellte", "Arbeiter", "Beamte"}
    assert probe["vorher"]["je_merkmal"]["geschlecht"] == probe["nachher"]["je_merkmal"]["geschlecht"]
    # Probe rollt zurück: kein v2, kein zusätzlicher Lauf; gespeichert sind nur die Zahlen.
    assert _anzahl(conn, "SELECT count(*) AS n FROM meta.regel WHERE regelsatz = 'v2'") == 0
    assert _anzahl(conn, "SELECT count(*) AS n FROM meta.lauf") == laeufe_vorher
    assert vorschlag_lesen(conn, v.id).probe["2024-08"]["nachher"]["gesamt"] == probe["nachher"]["gesamt"]

    gespeichert = conn.execute(
        "SELECT row_to_json(v)::text AS t FROM meta.vorschlag v WHERE id = %s", (v.id,)
    ).fetchone()
    assert gespeichert is not None
    assert "person_id" not in str(gespeichert["t"]).lower() and "vvh_id" not in str(gespeichert["t"]).lower()


def test_ganzes_monat_statt_stichtag_zaehlt_mindestens_so_viele(agent_conn: Verbindung) -> None:
    modell = FakeModell(
        {
            "agent.koordinator": {"rolle": "datenmanagement", "auftrag": "Berichtszeitraum ganzer Monat"},
            "agent.datenmanagement": {
                "typ": "regel_aendern",
                "regelsatz_ziel": "v2",
                "aenderungen": [
                    {
                        "regel_name": "R2_R4_stichtag_eigene_lieferung",
                        "parameter_neu": [
                            {"schluessel": "zeitraum_art", "wert": "Monat"},
                            {"schluessel": "von", "wert": "monatserster"},
                            {"schluessel": "bis", "wert": "monatsletzter"},
                        ],
                    }
                ],
                "begruendung": "Änderungsauftrag 2: Bestand im ganzen Monat.",
            },
        }
    )
    ergebnis = agent_ausfuehren(agent_conn, STICHTAG_MONAT, complete=modell, probe_lieferung="2024-08")
    assert ergebnis.vorschlag_id is not None
    probe = vorschlag_lesen(agent_conn, ergebnis.vorschlag_id).probe["2024-08"]
    assert probe["nachher"]["zeitraum_art"] == "Monat"
    assert probe["nachher"]["gesamt"] >= probe["vorher"]["gesamt"]


@pytest.mark.parametrize(
    "abfrage",
    [
        "SELECT vvh_id FROM roh.lieferung",
        "SELECT * FROM roh.lieferung",
        "select count(*) AS n, Person_ID from roh.lieferung group by 2",
        "SELECT geburtsdatum FROM roh.lieferung",
        "UPDATE meta.regel SET aktiv = false",
        "SELECT 1; DELETE FROM meta.regel",
        "SELECT beispiele FROM meta.pruefung_treffer",
    ],
)
def test_sql_lesen_verweigert_einzeldaten_und_schreiben(agent_conn: Verbindung, abfrage: str) -> None:
    with pytest.raises(AbfrageVerweigert):
        sql_lesen(agent_conn, abfrage)


def test_sql_lesen_ist_nur_lesend_und_begrenzt(agent_conn: Verbindung) -> None:
    regeln = _anzahl(agent_conn, "SELECT count(*) AS n FROM meta.regel")
    with pytest.raises(psycopg.errors.ReadOnlySqlTransaction):
        sql_lesen(agent_conn, "WITH x AS (DELETE FROM meta.regel RETURNING 1) SELECT count(*) FROM x")
    assert _anzahl(agent_conn, "SELECT count(*) AS n FROM meta.regel") == regeln

    erlaubt = sql_lesen(agent_conn, "SELECT qual, count(*) AS n FROM roh.lieferung GROUP BY qual ORDER BY 1")
    assert erlaubt["spalten"] == ["qual", "n"] and not erlaubt["abgeschnitten"]
    viel = sql_lesen(agent_conn, "SELECT g FROM generate_series(1, 500) g")
    assert len(viel["zeilen"]) == 200 and viel["abgeschnitten"]
    assert not any(
        "person_id" in s or "vvh_id" in s for spalten in schema_lesen(agent_conn).values() for s in spalten
    )


def test_mehrdeutige_anweisung_gibt_rueckfrage(agent_conn: Verbindung) -> None:
    modell = FakeModell({"agent.koordinator": {"rolle": None, "rueckfrage": "Was genau soll sich ändern?"}})
    ergebnis = agent_ausfuehren(agent_conn, MEHRDEUTIG, complete=modell)
    assert ergebnis.rueckfrage == "Was genau soll sich ändern?"
    assert ergebnis.vorschlag_id is None and len(modell.aufrufe) == 1
    assert _anzahl(agent_conn, "SELECT count(*) AS n FROM meta.vorschlag") == 0


def test_beamte_ausschliessen_ohne_passende_regelart_wird_begruendet_abgelehnt(
    agent_conn: Verbindung,
) -> None:
    """Gewählte Lösung: „Beamte ausschließen“ braucht eine Ausschlussregel. Eine solche Regel-Art kennt der
    Zählcode nicht; eine neue Art wäre neuer Programmcode und damit ein Entwicklungsauftrag. Der Code lehnt
    den Vorschlag deshalb mit Begründung ab, statt eine wirkungslose Regel anzulegen."""
    modell = FakeModell(
        {
            "agent.koordinator": {"rolle": "klassifikation", "auftrag": "Beamte nicht zählen"},
            "agent.klassifikation": {
                "typ": "regel_neu",
                "regelsatz_ziel": "v2",
                "neue_regeln": [
                    {
                        "name": "R8_ohne_beamte",
                        "typ": "zaehl",
                        "art": "ausschluss",
                        "parameter": [{"schluessel": "qualifikation", "wert": ["Beamte"]}],
                        "beschreibung": "Beamte werden nicht gezählt.",
                        "begruendung": "Anweisung",
                    }
                ],
                "begruendung": "Beamte ausschließen.",
            },
        }
    )
    ergebnis = agent_ausfuehren(agent_conn, BEAMTE, complete=modell)
    assert ergebnis.vorschlag_id is None
    assert ergebnis.abgelehnt is not None and "ausschluss" in ergebnis.abgelehnt
    assert "Entwicklungsauftrag" in ergebnis.abgelehnt
    assert _anzahl(agent_conn, "SELECT count(*) AS n FROM meta.vorschlag") == 0


@pytest.mark.parametrize(
    ("rolle", "antwort", "grund"),
    [
        (
            "klassifikation",
            {
                "typ": "regel_aendern",
                "aenderungen": [
                    {
                        "regel_name": "R6_beschaeftigungskategorie",
                        "parameter_neu": [{"schluessel": "qualifikation", "wert": "irgendwas"}],
                    }
                ],
                "begruendung": "x",
            },
            "nicht zulässig",
        ),
        (
            "klassifikation",
            {
                "typ": "regel_aendern",
                "aenderungen": [{"regel_name": "R99_gibt_es_nicht", "parameter_neu": []}],
                "begruendung": "x",
            },
            "gibt es im Regelsatz",
        ),
        (
            "reporting",
            {
                "typ": "regel_aendern",
                "aenderungen": [{"regel_name": "R6_beschaeftigungskategorie", "parameter_neu": []}],
                "begruendung": "x",
            },
            "darf keine Vorschläge",
        ),
        (
            "reporting",
            {
                "typ": "code_datei",
                "datei": {
                    "name": "liste",
                    "sprache": "sql",
                    "inhalt": "SELECT vvh_id FROM bereinigt.abschnitt",
                },
                "begruendung": "x",
            },
            "Einzeldaten",
        ),
    ],
)
def test_ungueltiger_vorschlag_wird_nicht_angelegt(
    agent_conn: Verbindung, rolle: str, antwort: dict[str, Any], grund: str
) -> None:
    modell = FakeModell({"agent.koordinator": {"rolle": rolle, "auftrag": "x"}, f"agent.{rolle}": antwort})
    ergebnis = agent_ausfuehren(agent_conn, "Eine Anweisung", complete=modell)
    assert ergebnis.vorschlag_id is None
    assert ergebnis.abgelehnt is not None and grund in ergebnis.abgelehnt
