"""Live-Änderung (Jury-Teil 2, #80): unbekannte Aufträge werden richtige Vorschläge in einem neuen Regelsatz.

Fängt die Fehler der Live-Probe vom 05.11.: das Modell riet Werte („monat_15“), nahm die falsche Regel, für
„Beamte ausschließen“ und „Bundesländer zusammenlegen“ gab es keine Regel-Art, und eine Freigabe hätte v2 (die
Abgabe) in place geändert. Das Modell ist ein Fake; geprüft wird, was der Code garantiert.
"""

from __future__ import annotations

import json
import subprocess
from collections.abc import Iterator
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from plattform.freigabe import freigeben as plattform_freigeben

from statagent.agenten.anwenden import ablehnen_ausfuehren, freigabe_ausfuehren
from statagent.agenten.koordinator import (
    agent_ausfuehren,
    bekannte_werte,
    produktions_regelsatz,
    rolle_nach_worten,
    ruecknahme_gemeint,
    ziel_bestimmen,
)
from statagent.agenten.regelaenderung import regelsatz_sicherstellen
from statagent.agenten.vorschlag import VorschlagFehler, vorschlag_lesen, vorschlag_schema_einrichten
from statagent.db import Verbindung
from statagent.lauf import lauf_ausfuehren
from statagent.regeln import regeln_laden, regelstand

NAME = "Lena Gruber"
MONAT = "2024-08"


class SequenzModell:
    """Fake für ``plattform.llm.complete``: je Zweck eine Liste von Antworten, die letzte wiederholt sich."""

    def __init__(self, antworten: dict[str, list[dict[str, Any]]]) -> None:
        self.antworten = antworten
        self.aufrufe: list[tuple[str, list[dict[str, str]]]] = []

    def __call__(
        self, nachrichten: list[dict[str, str]], schema: Any = None, zweck: str = "", **_: Any
    ) -> Any:
        liste = self.antworten[zweck]
        n = sum(1 for z, _ in self.aufrufe if z == zweck)
        self.aufrufe.append((zweck, nachrichten))
        daten = liste[min(n, len(liste) - 1)]
        return SimpleNamespace(text=json.dumps(daten), json=daten, provider="mock", modell="fake-1")


def _neu(art: str, name: str, parameter: dict[str, Any]) -> dict[str, Any]:
    return {
        "typ": "regel_neu",
        "regelsatz_ziel": "v2",
        "neue_regeln": [
            {
                "name": name,
                "typ": "zaehl",
                "art": art,
                "parameter": [{"schluessel": k, "wert": w} for k, w in parameter.items()],
                "beschreibung": "Live-Änderung",
                "begruendung": "Anweisung",
            }
        ],
        "begruendung": "Live-Änderung.",
    }


def _aendern(regel: str, parameter: dict[str, Any]) -> dict[str, Any]:
    return {
        "typ": "regel_aendern",
        "regelsatz_ziel": "v2",
        "aenderungen": [
            {
                "regel_name": regel,
                "parameter_neu": [{"schluessel": k, "wert": w} for k, w in parameter.items()],
            }
        ],
        "begruendung": "Live-Änderung.",
    }


def _modell(rolle: str, *antworten: dict[str, Any]) -> SequenzModell:
    return SequenzModell(
        {"agent.koordinator": [{"rolle": rolle, "auftrag": "x"}], f"agent.{rolle}": list(antworten)}
    )


def git(repo: Path, *argumente: str) -> str:
    return subprocess.run(
        ["git", "-C", str(repo), *argumente], check=True, capture_output=True, text=True
    ).stdout.strip()


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    pfad = tmp_path / "repo"
    pfad.mkdir()
    git(pfad, "init", "-q", "-b", "main")
    for schluessel, wert in (
        ("user.name", "Test Lauf"),
        ("user.email", "test@example.org"),
        ("commit.gpgsign", "false"),
        ("core.hooksPath", str(pfad / ".git" / "keine-hooks")),
    ):
        git(pfad, "config", schluessel, wert)
    git(pfad, "commit", "-q", "--allow-empty", "-m", "Start")
    return pfad


@pytest.fixture
def live_conn(conn: Verbindung) -> Iterator[Verbindung]:
    """Fixture-DB mit gerechnetem Monat in v1 (Basis für bekannte Werte und Probe)."""
    vorschlag_schema_einrichten(conn)
    lauf_ausfuehren(conn, MONAT, "v1", reihenfolge_pruefen=False)
    yield conn


def _stand(conn: Verbindung, regelsatz: str) -> str:
    return regelstand(conn, regeln_laden(conn, regelsatz, MONAT))


def test_ziel_ist_nie_ein_regelsatz_mit_laeufen(live_conn: Verbindung) -> None:
    # Fängt: Basis v2 mit Läufen, Modell nennt v2 als Ziel → die Freigabe hätte die Abgabe v2 geändert.
    with live_conn.transaction():
        regelsatz_sicherstellen(live_conn, "v2", "v1")
    assert ziel_bestimmen(live_conn, "v1", "v2") == "v2"  # Entwurf ohne Läufe darf Änderungen sammeln
    lauf_ausfuehren(live_conn, MONAT, "v2", reihenfolge_pruefen=False)
    assert ziel_bestimmen(live_conn, "v2", "v2") == "v3"
    assert ziel_bestimmen(live_conn, "v1", "v2") == "v3"
    assert ziel_bestimmen(live_conn, "v2", "v7") == "v3"  # das Modell wählt keine Nummer


def test_beamte_ausschliessen_zaehlt_ohne_beamte_und_verliert_kein_verhaeltnis(live_conn: Verbindung) -> None:
    modell = _modell(
        "klassifikation",
        _neu("ausschluss", "R8_ohne_beamte", {"merkmal": "qualifikation", "werte": ["Beamte"]}),
    )
    erg = agent_ausfuehren(live_conn, "Beamte nicht mehr zählen", complete=modell, probe_lieferung=MONAT)
    assert erg.vorschlag_id is not None, erg.abgelehnt
    v = vorschlag_lesen(live_conn, erg.vorschlag_id)
    assert (v.regelsatz_basis, v.regelsatz_ziel) == ("v1", "v2")
    p = v.probe[MONAT]
    beamte = p["vorher"]["je_merkmal"]["qualifikation"]["Beamte"]
    assert beamte > 0 and "Beamte" not in p["nachher"]["je_merkmal"]["qualifikation"]
    assert p["nachher"]["gesamt"] == p["vorher"]["gesamt"] - beamte  # Lauf rechnet die Abrechnung auf
    andere = {k: w for k, w in p["vorher"]["je_merkmal"]["qualifikation"].items() if k != "Beamte"}
    assert p["nachher"]["je_merkmal"]["qualifikation"] == andere


def test_bundeslaender_zusammenlegen_summiert_und_aendert_den_gesamtbestand_nicht(
    live_conn: Verbindung,
) -> None:
    zuordnung = ["1=Ost", "3=Ost", "9=Ost"]
    modell = _modell(
        "klassifikation", _neu("gruppierung", "R9_ostregion", {"merkmal": "region", "zuordnung": zuordnung})
    )
    erg = agent_ausfuehren(live_conn, "Ostregion bilden", complete=modell, probe_lieferung=MONAT)
    assert erg.vorschlag_id is not None, erg.abgelehnt
    p = vorschlag_lesen(live_conn, erg.vorschlag_id).probe[MONAT]
    vorher, nachher = p["vorher"]["je_merkmal"]["region"], p["nachher"]["je_merkmal"]["region"]
    assert nachher["Ost"] == sum(vorher.get(c, 0) for c in ("1", "3", "9"))
    assert not {"1", "3", "9"} & set(nachher)
    assert p["nachher"]["gesamt"] == p["vorher"]["gesamt"]


def test_unbekannte_auspraegung_geht_zur_korrektur_zurueck(live_conn: Verbindung) -> None:
    # Fängt: „Wien“ statt Code „9“ hätte nichts zusammengelegt; das Programm meldet die bekannten Werte zurück.
    falsch = _neu("gruppierung", "R9_ost", {"merkmal": "region", "zuordnung": ["Wien=Ost", "Burgenland=Ost"]})
    richtig = _neu("gruppierung", "R9_ost", {"merkmal": "region", "zuordnung": ["9=Ost", "1=Ost"]})
    modell = _modell("klassifikation", falsch, richtig)
    erg = agent_ausfuehren(live_conn, "Wien und Burgenland zusammen", complete=modell)
    assert erg.vorschlag_id is not None, erg.abgelehnt
    assert len(erg.korrekturen) == 1 and "gibt es beim Merkmal region nicht" in erg.korrekturen[0]
    zweite_runde = [n for z, n in modell.aufrufe if z == "agent.klassifikation"][1]
    assert "nicht angenommen" in zweite_runde[-1]["content"]


def test_stichtag_am_15_wird_nach_korrektur_von_gleich_bis(live_conn: Verbindung) -> None:
    # Fängt: „am 15.“ wurde zu Stichtag mit von = monatsletzter, bis unverändert (Live-Probe 05.11.).
    falsch = _aendern("R2_R4_stichtag_eigene_lieferung", {"von": "tag:15"})
    richtig = _aendern("R2_R4_stichtag_eigene_lieferung", {"von": "tag:15", "bis": "tag:15"})
    erg = agent_ausfuehren(live_conn, "Stichtag 15.", complete=_modell("datenmanagement", falsch, richtig))
    assert erg.vorschlag_id is not None, erg.abgelehnt
    assert erg.korrekturen and "derselbe Tag" in erg.korrekturen[0]
    neu = vorschlag_lesen(live_conn, erg.vorschlag_id).aenderungen[0]["parameter_neu"]
    assert (neu["zeitraum_art"], neu["von"], neu["bis"]) == ("Stichtag", "tag:15", "tag:15")


def test_nach_zwei_korrekturen_ist_schluss(live_conn: Verbindung) -> None:
    falsch = _aendern("R2_R4_stichtag_eigene_lieferung", {"von": "monat_15"})
    modell = _modell("datenmanagement", falsch)
    erg = agent_ausfuehren(live_conn, "Stichtag 15.", complete=modell)
    assert erg.vorschlag_id is None and erg.abgelehnt is not None and "monat_15" in erg.abgelehnt
    assert sum(1 for z, _ in modell.aufrufe if z == "agent.datenmanagement") == 3


@pytest.mark.parametrize(
    "antwort",
    [
        _aendern("R5_alter", {"geburtsmonat_13": "ersatz:01-01"}),
        _neu("ausschluss", "R8_ohne_beamte", {"merkmal": "qualifikation", "werte": ["Beamte"]}),
    ],
    ids=["regel_aendern", "regel_neu"],
)
def test_ablehnen_und_ruecknahme_stellen_den_stand_wieder_her(
    live_conn: Verbindung, repo: Path, antwort: dict[str, Any]
) -> None:
    conn = live_conn
    rolle = "datenmanagement" if antwort["typ"] == "regel_aendern" else "klassifikation"
    vorher = _stand(conn, "v1")
    kopf = git(repo, "rev-parse", "HEAD")

    abgelehnt = agent_ausfuehren(conn, "Live-Änderung", complete=_modell(rolle, antwort))
    assert abgelehnt.vorschlag_id is not None, abgelehnt.abgelehnt
    ablehnen_ausfuehren(conn, abgelehnt.vorschlag_id, NAME, repo, begruendung="nicht gewollt")
    assert _stand(conn, "v1") == vorher and git(repo, "rev-parse", "HEAD") == kopf
    assert produktions_regelsatz(conn) == "v1"

    erg = agent_ausfuehren(conn, "Live-Änderung", complete=_modell(rolle, antwort))
    assert erg.vorschlag_id is not None
    f = freigabe_ausfuehren(conn, erg.vorschlag_id, NAME, repo, freigeben=plattform_freigeben)
    assert f.angewendet, f.meldung
    assert produktions_regelsatz(conn) == "v2" and _stand(conn, "v1") == vorher  # v1 unverändert
    if antwort["typ"] == "regel_aendern":
        assert _stand(conn, "v2") != vorher

    zurueck = SequenzModell(
        {"agent.koordinator": [{"rolle": rolle, "auftrag": "zurück", "ruecknahme_von": erg.vorschlag_id}]}
    )
    r = agent_ausfuehren(
        conn, f"Nimm Vorschlag {erg.vorschlag_id} zurück", complete=zurueck, regelsatz_basis=None
    )
    assert r.vorschlag_id is not None, r.abgelehnt
    rv = vorschlag_lesen(conn, r.vorschlag_id)
    assert (rv.typ, rv.regelsatz_basis, rv.regelsatz_ziel) == ("regel_aendern", "v2", "v3")
    assert freigabe_ausfuehren(conn, r.vorschlag_id, NAME, repo, freigeben=plattform_freigeben).angewendet
    assert produktions_regelsatz(conn) == "v3" and _stand(conn, "v3") == vorher
    # Historie bleibt: der zurückgenommene Vorschlag ist weiter freigegeben, v2 besteht weiter
    assert vorschlag_lesen(conn, erg.vorschlag_id).status == "freigegeben"
    assert int(git(repo, "rev-list", "--count", "HEAD")) == 3


def test_ruecknahme_nur_vom_stand_der_den_vorschlag_enthaelt(live_conn: Verbindung) -> None:
    zurueck = SequenzModell({"agent.koordinator": [{"rolle": "datenmanagement", "ruecknahme_von": 999}]})
    erg = agent_ausfuehren(live_conn, "Nimm Vorschlag 999 zurück", complete=zurueck)
    assert erg.vorschlag_id is None and erg.abgelehnt is not None and "nicht freigegeben" in erg.abgelehnt


def test_widerspruch_zu_frueherer_regel_ist_keine_ruecknahme(live_conn: Verbindung) -> None:
    # Fängt: „nicht mehr das ganze Monat, sondern am 15.“ las der Koordinator als Rücknahme von Auftrag 2 und
    # stellte den Monatsletzten wieder her (Live-Probe 05.11.). Ohne Rücknahme-Wort gilt ruecknahme_von nicht.
    stichtag = _aendern("R2_R4_stichtag_eigene_lieferung", {"von": "tag:15", "bis": "tag:15"})
    modell = SequenzModell(
        {
            "agent.koordinator": [{"rolle": "datenmanagement", "auftrag": "x", "ruecknahme_von": 1}],
            "agent.datenmanagement": [stichtag],
        }
    )
    erg = agent_ausfuehren(live_conn, "Nicht mehr der Monatsletzte, sondern der 15. zählt.", complete=modell)
    assert erg.vorschlag_id is not None, erg.abgelehnt
    assert vorschlag_lesen(live_conn, erg.vorschlag_id).aenderungen[0]["parameter_neu"]["von"] == "tag:15"


@pytest.mark.parametrize(
    ("anweisung", "gemeint"),
    [
        ("Nimm Vorschlag 41 zurück", True),
        ("Mach die letzte Änderung rückgängig", True),
        ("Bitte wieder wie vorher zählen", True),
        ("Ab jetzt am 15. statt über das ganze Monat", False),
        ("Beamte nicht mehr zählen", False),
    ],
)
def test_ruecknahme_nur_bei_ausdruecklichem_wort(anweisung: str, gemeint: bool) -> None:
    assert ruecknahme_gemeint(anweisung) is gemeint


def test_ausschluss_wenn_nach_beschaeftigungskategorie_gezaehlt_wird(conn: Verbindung) -> None:
    # Fängt: in v2 (R6 = beschaeftigungskategorie) brach der Ausschluss mit „missing FROM-clause entry for table
    # kq“ ab (Live-Probe 05.11., Auftrag „ohne Beamte“).
    vorschlag_schema_einrichten(conn)
    with conn.transaction():
        conn.execute(
            """UPDATE meta.regel SET parameter = '{"qualifikation": "beschaeftigungskategorie"}'::jsonb
               WHERE regelsatz = 'v1' AND name = 'R6_beschaeftigungskategorie'"""
        )
    lauf_ausfuehren(conn, MONAT, "v1", reihenfolge_pruefen=False)
    antwort = _neu("ausschluss", "R8_ohne_beamte", {"merkmal": "qualifikation", "werte": ["Beamte"]})
    erg = agent_ausfuehren(
        conn, "Beamte nicht zählen", complete=_modell("klassifikation", antwort), probe_lieferung=MONAT
    )
    assert erg.vorschlag_id is not None, erg.abgelehnt
    p = vorschlag_lesen(conn, erg.vorschlag_id).probe[MONAT]
    assert set(p["nachher"]["je_merkmal"]["qualifikation"]) == {"Angestellte", "Arbeiter"}
    beamte = p["vorher"]["je_merkmal"]["qualifikation"]["Beamte"]
    assert p["nachher"]["gesamt"] == p["vorher"]["gesamt"] - beamte


def test_nur_meldungstext_einer_pruefregel_ist_kein_vorschlag(live_conn: Verbindung) -> None:
    # Fängt: „Monat 13 → 1. Jänner“ änderte nur den Maßnahmetext von P04; das ändert keine Zahl.
    text = _aendern("P04_geburtsdatum_monat_13", {"massnahme": "Ersatztag 1. Jänner"})
    erg = agent_ausfuehren(
        live_conn, "Prüfregel P04 soll Monat 13 anders melden", complete=_modell("qs", text)
    )
    assert erg.vorschlag_id is None and erg.abgelehnt is not None and "keine Zahl" in erg.abgelehnt


@pytest.mark.parametrize(
    ("anweisung", "rolle"),
    [
        ("Haltet einen Monat schon an, wenn der Bestand mehr als 3 Prozent unter dem Vormonat liegt.", "qs"),
        (
            "Beschäftigungsverhältnisse von Kindern unter 15 Jahren zählen wir nicht mehr mit.",
            "klassifikation",
        ),
        ("kinder unter fünfzehn jahren zählen wir ab jetzt nicht mehr", "klassifikation"),
        ("beamte zählen wir nicht mehr", "klassifikation"),
        ("beamtinnen und beamte bitte nicht mehr mitzählen", "klassifikation"),
        ("wien niederösterreich und burgenland zusammen als ostregion ausweisen", "klassifikation"),
        ("bei geburtsmonat dreizehn nehmt bitte den ersten jänner als ersatztag", "datenmanagement"),
        ("ab jetzt zählt nur mehr wer am fünfzehnten des monats beschäftigt ist", "datenmanagement"),
        (
            "Ab sofort zählen wir nicht mehr das ganze Monat, sondern nur, wer am 15. beschäftigt ist.",
            "datenmanagement",
        ),
    ],
)
def test_wort_weiche_auch_fuer_lockere_schreibweise(anweisung: str, rolle: str) -> None:
    assert rolle_nach_worten(anweisung) == rolle


def test_qs_ohne_schwellenwort_geht_an_die_zaehlrolle(live_conn: Verbindung) -> None:
    # Fängt: „Kinder unter 15 nicht mehr zählen“ ging an qs, die P13 umschrieb (Probe 19:23).
    antwort = _neu("ausschluss", "R8_unter_15", {"merkmal": "alter", "werte": ["0-14"]})
    modell = SequenzModell(
        {"agent.koordinator": [{"rolle": "qs", "auftrag": "x"}], "agent.klassifikation": [antwort]}
    )
    erg = agent_ausfuehren(live_conn, "Kinder unter 15 Jahren zählen wir nicht mehr mit.", complete=modell)
    assert erg.rolle == "klassifikation" and erg.vorschlag_id is not None, erg.abgelehnt
    assert not [z for z, _ in modell.aufrufe if z == "agent.qs"]


def test_rueckfrage_der_rolle_holt_eine_zweite_meinung(live_conn: Verbindung) -> None:
    antwort = _aendern("R5_alter", {"geburtsmonat_13": "ersatz:01-01"})
    modell = SequenzModell(
        {
            "agent.koordinator": [{"rolle": "klassifikation", "auftrag": "x"}],
            "agent.klassifikation": [{"rueckfrage": "Welche Regel?"}],
            "agent.datenmanagement": [antwort],
        }
    )
    erg = agent_ausfuehren(live_conn, "Bei Geburtsmonat 13 gilt der erste Jänner.", complete=modell)
    assert erg.rolle == "datenmanagement" and erg.vorschlag_id is not None, erg.rueckfrage


def test_bekannte_werte_ohne_lauf_der_basis_und_nach_kategorie(live_conn: Verbindung) -> None:
    # Fängt: neuer Regelsatz ohne Läufe → leere Liste → Rückfrage (Probe 19:25, Ostregion und Vorarlberg).
    with live_conn.transaction():
        regelsatz_sicherstellen(live_conn, "v2", "v1")
        live_conn.execute(
            """UPDATE meta.regel SET parameter = '{"qualifikation": "beschaeftigungskategorie"}'::jsonb
               WHERE regelsatz = 'v2' AND name = 'R6_beschaeftigungskategorie'"""
        )
    werte = bekannte_werte(live_conn, "v2")
    assert {"1", "3", "8", "9"} <= set(werte["region"])
    assert set(werte["qualifikation"]) >= {"Arbeiter", "Angestellte", "Beamte"}
    assert "ArbeiterDV" not in werte["qualifikation"]
    assert "ArbeiterDV" in bekannte_werte(live_conn, "v1")["qualifikation"]


@pytest.mark.parametrize(
    ("art", "parameter"),
    [
        ("ausschluss", {"merkmal": "qualifikation", "werte": ["Beamte"]}),
        ("gruppierung", {"merkmal": "region", "zuordnung": ["1=Ost", "3=Ost", "9=Ost"]}),
    ],
)
def test_lauf_mit_neuer_zaehlregel_haelt_blattsummen_nicht_an(
    live_conn: Verbindung, art: str, parameter: dict[str, Any]
) -> None:
    # Fängt (Review b-uc3-b6): P21 hielt jeden Monat an, weil der Bestand die Ausgeschlossenen mitzählte bzw.
    # die Gruppe „Ost“ in keiner Klassifikation steht; danach verweigert veroeffentlichen.
    conn = live_conn
    with conn.transaction():
        regelsatz_sicherstellen(conn, "v2", "v1")
        conn.execute(
            """INSERT INTO meta.regel (regelsatz, name, typ, art, reihenfolge, parameter, beschreibung, begruendung,
                                       grundlage, gueltig_ab_lieferung)
               VALUES ('v2', 'R8_live', 'zaehl', %s, 80, %s::jsonb, 'Live', 'Live', 'Test', '2024-08')""",
            (art, json.dumps(parameter)),
        )
    lauf = lauf_ausfuehren(conn, MONAT, "v2", reihenfolge_pruefen=False)
    treffer = conn.execute(
        """SELECT r.name, t.anzahl, t.anhalten, t.details FROM meta.pruefung_treffer t
           JOIN meta.regel r ON r.id = t.regel_id WHERE t.lauf_id = %s AND r.name LIKE 'P21%%'""",
        (lauf.lauf_id,),
    ).fetchall()
    assert treffer and all(t["anzahl"] == 0 and not t["anhalten"] for t in treffer), treffer
    nicht_gezaehlt = conn.execute(
        "SELECT gelesen, gezaehlt, nicht_gezaehlt, ausgeschlossen FROM meta.lauf WHERE id = %s",
        (lauf.lauf_id,),
    ).fetchone()
    assert nicht_gezaehlt is not None


def test_rueckfrage_ohne_andere_rolle_wird_einmal_nachgefasst(live_conn: Verbindung) -> None:
    # Fängt: „Monat 13 → 1. Jänner“ fragte, ob P04 gemeint sei (Probe 19:44); einmal nachfassen, dann Vorschlag.
    antwort = _aendern("R5_alter", {"geburtsmonat_13": "ersatz:01-01"})
    modell = _modell("datenmanagement", {"rueckfrage": "Ist P04 gemeint?"}, antwort)
    erg = agent_ausfuehren(live_conn, "Bei Geburtsmonat 13 gilt der erste Jänner.", complete=modell)
    assert erg.vorschlag_id is not None, erg.rueckfrage
    assert erg.korrekturen == ["Rückfrage der Rolle: Ist P04 gemeint?"]


def test_echte_rueckfrage_bleibt_nach_dem_nachfassen(live_conn: Verbindung) -> None:
    modell = _modell("datenmanagement", {"rueckfrage": "Erster oder letzter Tag?"})
    erg = agent_ausfuehren(live_conn, "Bei Geburtsmonat 13 anders rechnen.", complete=modell)
    assert erg.vorschlag_id is None and erg.rueckfrage == "Erster oder letzter Tag?"
    assert sum(1 for z, _ in modell.aufrufe if z == "agent.datenmanagement") == 2


def test_gruppierung_nach_kategorie_heisst_qualifikation(live_conn: Verbindung) -> None:
    # Fängt: „Arbeiter und Angestellte zusammen“ nannte merkmal beschaeftigungskategorie (Probe 19:44).
    with live_conn.transaction():
        live_conn.execute(
            """UPDATE meta.regel SET parameter = '{"qualifikation": "beschaeftigungskategorie"}'::jsonb
               WHERE regelsatz = 'v1' AND name = 'R6_beschaeftigungskategorie'"""
        )
    antwort = _neu(
        "gruppierung",
        "R9_unselbstaendige",
        {
            "merkmal": "beschaeftigungskategorie",
            "zuordnung": ["Arbeiter=Unselbständige", "Angestellte=Unselbständige"],
        },
    )
    erg = agent_ausfuehren(
        live_conn, "Arbeiter und Angestellte zusammen", complete=_modell("klassifikation", antwort)
    )
    assert erg.vorschlag_id is not None, erg.abgelehnt
    regel = vorschlag_lesen(live_conn, erg.vorschlag_id).aenderungen[0]["regel"]
    assert regel["parameter"]["merkmal"] == "qualifikation"


def test_alter_vorschlag_mit_ziel_eines_gerechneten_regelsatzes_wird_nicht_freigegeben(
    live_conn: Verbindung, repo: Path
) -> None:
    # Fängt (Zweitmeinung astra): ein offener Vorschlag mit Ziel v2 aus der Zeit vor den v2-Läufen hätte bei
    # Freigabe v2, also die Abgabe, in place geändert.
    conn = live_conn
    erg = agent_ausfuehren(
        conn,
        "Live-Änderung",
        complete=_modell("datenmanagement", _aendern("R5_alter", {"max_plausibel": 100})),
    )
    assert erg.vorschlag_id is not None and erg.regelsatz_ziel == "v2"
    with conn.transaction():
        regelsatz_sicherstellen(conn, "v2", "v1")
    lauf_ausfuehren(conn, MONAT, "v2", reihenfolge_pruefen=False)
    stand, kopf = _stand(conn, "v2"), git(repo, "rev-parse", "HEAD")
    with pytest.raises(VorschlagFehler, match="gerechnete Monate"):
        freigabe_ausfuehren(conn, erg.vorschlag_id, NAME, repo, freigeben=plattform_freigeben)
    assert _stand(conn, "v2") == stand and git(repo, "rev-parse", "HEAD") == kopf
    assert vorschlag_lesen(conn, erg.vorschlag_id).status == "offen"
