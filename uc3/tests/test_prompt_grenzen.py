"""Prompt-Grenzen (#15 AC3): Was das Modell tatsächlich sieht, enthält keine Einzeldaten.

Ein Spy steht für ``plattform.llm.complete`` und sammelt jeden Text jeder Nachricht (System-Prompt,
Anweisung, Kontext). Geprüft wird gegen die Werte der Fixture-Lieferungen, nicht gegen den Spaltennamen:
Schema und Definitionen dürfen ``PERSON_ID`` nennen, nur konkrete Kennungen und Geburtsdaten nicht.
"""

from __future__ import annotations

import csv
import json
import re
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from statagent.agenten.koordinator import agent_ausfuehren, anweisung_pruefen
from statagent.agenten.vorschlag import vorschlag_schema_einrichten
from statagent.db import Verbindung
from statagent.lauf import lauf_ausfuehren

FIXTURES = Path(__file__).parent / "fixtures"
FELDER = ("VVH_ID", "PERSON_ID", "GEBURTSDATUM")


def _saetze() -> list[list[str]]:
    zeilen: list[list[str]] = []
    for datei in sorted(FIXTURES.glob("lieferung_*.csv")):
        with datei.open(encoding="utf-8", newline="") as f:
            zeilen += list(csv.reader(f, delimiter=";"))[1:]
    return zeilen


def _werte() -> set[str]:
    # Alle Kennungen der Fixtures haben vier Stellen (1001 … 7007); kleinere Werte gibt es nicht, also prüft
    # der Test jede VVH_ID und PERSON_ID und jedes GEBURTSDATUM.
    with (FIXTURES / "lieferung_2024-08.csv").open(encoding="utf-8") as f:
        kopf = f.readline().strip().split(";")
    spalten = [kopf.index(n) for n in FELDER]
    werte = {z[i] for z in _saetze() for i in spalten if z[i]}
    assert all(len(w) >= 4 for w in werte)
    return werte


WERTE = _werte()
#: Fixture-Werte, die zufällig auch in Regeldefinitionen stehen (siehe test_modellnachrichten_ohne_einzeldaten).
BEKANNT_AUS_DEFINITIONEN = frozenset({"2003", "2008", "1963-13-09"})


def _treffer(text: str) -> set[str]:
    """Fixture-Werte, die als eigenes Token im Text stehen.

    Grenze wie ``\\b``, zusätzlich ohne Bindestrich davor oder danach: „2001“ in einem Datum „2001-01-01“ ist
    kein Treffer für die VVH_ID 2001, ein Geburtsdatum wird als Ganzes gesucht.
    """
    return {w for w in WERTE if re.search(rf"(?<![\w-]){re.escape(w)}(?![\w-])", text)}


def _satz_im_text(text: str) -> list[str]:
    """Sätze, deren neun Felder in Reihenfolge (getrennt durch Satzzeichen, leer als null/None) im Text stehen."""
    gefunden = []
    for satz in _saetze():
        teile = [re.escape(f) if f else r"(?:null|None)?" for f in satz]
        if re.search(r"\W{0,12}".join(teile), text):
            gefunden.append(";".join(satz))
    return gefunden


class SpyModell:
    """``complete``-Fake: Antwort je Zweck, jeder Nachrichtentext wird gesammelt."""

    def __init__(self, antworten: dict[str, dict[str, Any]]) -> None:
        self.antworten = antworten
        self.aufrufe: list[str] = []
        self.texte: list[str] = []

    def __call__(
        self,
        nachrichten: list[dict[str, str]],
        schema: Any = None,
        stream: bool = False,
        provider: str | None = None,
        zweck: str = "",
    ) -> SimpleNamespace:
        self.aufrufe.append(zweck)
        self.texte += [str(n.get("content", "")) for n in nachrichten]
        daten = self.antworten[zweck]
        return SimpleNamespace(text=json.dumps(daten), json=daten, provider="mock", modell="spy-1")

    @property
    def gesehen(self) -> str:
        return "\n".join(self.texte)


def _spy_alter(geburtsmonat_13: str = "ersatz:01-01") -> SpyModell:
    return SpyModell(
        {
            "agent.koordinator": {"rolle": "datenmanagement", "auftrag": "Ersatztag bei Geburtsmonat 13"},
            "agent.datenmanagement": {
                "typ": "regel_aendern",
                "regelsatz_ziel": "v2",
                "aenderungen": [
                    {
                        "regel_name": "R5_alter",
                        "parameter_neu": [{"schluessel": "geburtsmonat_13", "wert": geburtsmonat_13}],
                    }
                ],
                "begruendung": "Bei Geburtsmonat 13 gilt ein anderer Ersatztag.",
            },
        }
    )


@pytest.fixture
def agent_conn(conn: Verbindung) -> Verbindung:
    vorschlag_schema_einrichten(conn)
    # Ein Lauf füllt stat.*, meta.lauf und meta.pruefung_treffer (dort stehen Beispiel-Kennungen): der
    # Kontext hat damit echte Aggregate, und ein Leck aus den Prüftreffern würde sichtbar.
    lauf_ausfuehren(conn, "2024-08", "v1", reihenfolge_pruefen=False)
    return conn


def _regel_text(conn: Verbindung) -> str:
    zeilen = conn.execute("SELECT row_to_json(r)::text AS t FROM meta.regel r").fetchall()
    return "\n".join(str(z["t"]) for z in zeilen)


def _protokoll_text(conn: Verbindung) -> tuple[int, str]:
    zeilen = conn.execute("SELECT row_to_json(p)::text AS t FROM meta.protokoll p").fetchall()
    return len(zeilen), "\n".join(str(z["t"]) for z in zeilen)


def test_pruefung_erkennt_kennungen_und_laesst_schema_zu() -> None:
    """Fängt eine Prüfung, die nichts findet (dann wären die Tests unten wertlos) oder den Spaltennamen verbietet."""
    assert (
        _treffer("Spalten: PERSON_ID (integer), VVH_ID, GEBURTSDATUM; Grenze 110, Lieferung 2024-08") == set()
    )
    assert _treffer("Beispiel: Person 5001 geboren 1980-05-12") == {"5001", "1980-05-12"}
    assert _satz_im_text("1001;5001;1980-05-12;M;2020-01-01;;ArbeiterDV;C;9")
    assert _satz_im_text('["1001", "5001", "1980-05-12", "M", "2020-01-01", null, "ArbeiterDV", "C", "9"]')


def test_modellnachrichten_ohne_einzeldaten(agent_conn: Verbindung, tmp_path: Path, monkeypatch: Any) -> None:
    """Fängt Kontext (Regeln, Schema, Aggregate, roh_kennzahlen, Läufe), der Kennungen, Geburtsdaten oder ganze
    Sätze einer Lieferung an das Modell gibt, und ein Protokoll, das sie speichert."""
    datei = tmp_path / "modellaufrufe.jsonl"
    monkeypatch.setenv("PLATTFORM_PROTOKOLL", str(datei))
    spy = _spy_alter()

    ergebnis = agent_ausfuehren(
        agent_conn, "Bei Geburtsmonat 13 den 1. Jänner einsetzen", complete=spy, probe_lieferung="2024-08"
    )

    assert ergebnis.vorschlag_id is not None, ergebnis.abgelehnt
    assert spy.aufrufe == ["agent.koordinator", "agent.datenmanagement"]
    # Der Spy hat den vollen Kontext gesehen, die Prüfung läuft nicht ins Leere.
    for teil in ('"schema"', '"regeln"', '"laeufe"', '"roh_kennzahlen"', "R5_alter"):
        assert teil in spy.gesehen
    # Zufällige Gleichheit mit Definitionen: ÖNACE-Versionen 2003/2008 (= VVH_ID 2003, 2008) und das
    # Beispiel-Datum 1963-13-09 in der Begründung von E03 stehen in meta.regel, nicht aus einer Lieferung.
    # Sie bleiben erlaubt; jeder andere Fixture-Wert im Text ist ein Leck.
    definitionen = _treffer(_regel_text(agent_conn))
    assert definitionen <= BEKANNT_AUS_DEFINITIONEN
    assert _treffer(spy.gesehen) - definitionen == set()
    assert _satz_im_text(spy.gesehen) == []

    anzahl, protokoll = _protokoll_text(agent_conn)
    assert anzahl >= 1
    assert _treffer(protokoll) - definitionen == set() and _satz_im_text(protokoll) == []
    # plattform.protokoll schreibt die Datei nur in plattform.llm, und dort ohne Inhalt; falls es sie gibt:
    if datei.exists():
        assert _treffer(datei.read_text(encoding="utf-8")) - definitionen == set()


def test_anweisung_mit_kennung_erreicht_weder_modell_noch_protokoll(agent_conn: Verbindung) -> None:
    """Fängt eine Anweisung mit konkreter Kennung, die ungeprüft an Modell und meta.protokoll geht."""
    spy = _spy_alter()
    vorher, _ = _protokoll_text(agent_conn)

    ergebnis = agent_ausfuehren(agent_conn, "Prüfe VVH_ID 859975 auf Geburtsmonat 13", complete=spy)

    assert spy.aufrufe == []
    assert ergebnis.abgelehnt is not None and "Kennung" in ergebnis.abgelehnt
    assert "859975" not in ergebnis.abgelehnt
    assert ergebnis.vorschlag_id is None
    nachher, protokoll = _protokoll_text(agent_conn)
    assert nachher == vorher and "859975" not in protokoll


def test_zahlen_ohne_kennungswort_erreichen_das_modell(agent_conn: Verbindung) -> None:
    """Fängt eine Kennungsprüfung, die jede Zahl verbietet (Grenzen, Jahre, Monate)."""
    spy = SpyModell({"agent.koordinator": {"rolle": None, "rueckfrage": "Welche Regel ist gemeint?"}})
    ergebnis = agent_ausfuehren(agent_conn, "Altersgrenze auf 110 Jahre ab 2025-03", complete=spy)
    assert spy.aufrufe == ["agent.koordinator"]
    assert ergebnis.abgelehnt is None and ergebnis.rueckfrage == "Welche Regel ist gemeint?"


@pytest.mark.parametrize(
    ("wert", "angenommen"),
    [("ersatz:01-01", True), ("ersatz:13-01", False), ("ersatz:02-29", False), ("jahresdifferenz", True)],
)
def test_geburtsmonat_13_ersatz_mm_tt(agent_conn: Verbindung, wert: str, angenommen: bool) -> None:
    """Fängt die Ablehnung des freigabefähigen ``ersatz:MM-TT`` (v1 hat ersatz:07-01) und Ersatzdaten, an denen
    ``make_date`` in zaehlung.py scheitert (Monat 13, 29.02. in einem Gemeinjahr)."""
    ergebnis = agent_ausfuehren(agent_conn, "Ersatztag bei Geburtsmonat 13 ändern", complete=_spy_alter(wert))
    if angenommen:
        assert ergebnis.vorschlag_id is not None, ergebnis.abgelehnt
    else:
        assert ergebnis.vorschlag_id is None
        assert ergebnis.abgelehnt is not None and "geburtsmonat_13" in ergebnis.abgelehnt


@pytest.mark.parametrize(
    "anweisung",
    [
        # Fängt: „person“ + Zahl ab zwei Stellen galt als Kennung, die Altersregel vor der Jury wäre abgewiesen worden.
        "Zähle jede Person 75 und älter als echt",
        # Fängt: Mehrzahl „Personen“ mit Alter in Jahren als Kennung.
        "Personen ab 75 Jahren",
        # Fängt: eine Grenze in Jahren als Kennung.
        "Setze die Altersgrenze auf 100 Jahre",
        # Fängt: einen Prozentwert als Kennung.
        "Halte an, wenn mehr als 3 Prozent fehlen",
        # Fängt: einen Lieferungsmonat (Datum) als Kennung.
        "Lieferung 2025-10",
        # Fängt: eine Dauer in Tagen als Kennung.
        "mindestens 200 Tage",
        # Fängt: den Feldnamen ohne Nummer, den Auftrag 3 verlangt, als Kennung.
        "Felder PERSON_ID, GESCHLECHT",
    ],
)
def test_anweisung_ohne_kennung_geht_durch(anweisung: str) -> None:
    assert anweisung_pruefen(anweisung) is None


@pytest.mark.parametrize(
    "anweisung",
    [
        # Fängt: Spaltenname mit Kennung.
        "VVH_ID 859975",
        # Fängt: Spaltenname, Doppelpunkt, Kennung.
        "PERSON_ID: 1001049",
        # Fängt: Kennungswort ohne _ID vor einer siebenstelligen Kennung.
        "Person 1001049",
        # Fängt: „Kennung“ fehlte im Wortmuster und ging durch.
        "Kennung 1001049",
        # Fängt: mehrere Kennungswörter mit Schrägstrich vor der Kennung gingen durch.
        "Personen/IDs/Kennung 1001049",
        # Fängt: „Nr.“ zwischen Kennungswort und Kennung.
        "Verhältnis Nr. 859975",
        # Fängt: Listen von Kennungen galten als Datum/Dezimalzahl und gingen durch (Review, 05.11.).
        "PERSON_ID 1001049,1001050",
        "IDs 1001049,1001050 und 1001051",
        "VVH_ID 859975/859976",
    ],
)
def test_anweisung_mit_kennung_wird_abgewiesen(anweisung: str) -> None:
    grund = anweisung_pruefen(anweisung)
    assert grund is not None and "Kennung" in grund
    assert not re.search(r"\d{5,}", grund)


def test_kennung_nach_zeilenumbruch_in_begruendung(agent_conn: Verbindung) -> None:
    """Fängt: die Prüfung lief über json.dumps, ein Zeilenumbruch stand dort als ``\\n`` (zwei Zeichen), und
    „PERSON_ID\\n1001049“ in der Begründung ging durch."""
    spy = SpyModell(
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
                "begruendung": "geprüft an PERSON_ID\n1001049",
            },
        }
    )
    ergebnis = agent_ausfuehren(
        agent_conn, "Zählt freie Dienstverträge mit den Dienstverträgen zusammen", complete=spy
    )
    assert ergebnis.vorschlag_id is None
    assert ergebnis.abgelehnt is not None and "Kennung" in ergebnis.abgelehnt
