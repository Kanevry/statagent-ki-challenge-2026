"""Prüfkatalog P01–P24 (meta.regel, Typ pruefung) und seine Ausführung je Lauf.

(a) Fixture-Lieferungen (CI): Treffer der Fallen aus test_lauf_fixture (Volldublette 1005, DK → C 1008,
    leer → UNB/0 1007, Alter 153 Jahre 1011, Spaltentausch 2024-10, Erstlieferung 2024-08).
(b) `-m daten`: gegen die Datenbank mit allen 24 Lieferungen (UC3_DATABASE_URL wie `uc3 lauf`; UC3_DATEN_URL überschreibt), in einer
    Transaktion, die am Ende zurückgerollt wird. Soll-Zahlen aus der unabhängigen Gegenrechnung.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from dataclasses import replace
from pathlib import Path

import psycopg
import pytest

from statagent import konfig
from statagent.db import Verbindung, verbinden
from statagent.regeln import Regel, RegelFehler, regeln_laden

DATEI_120 = Path(__file__).resolve().parents[1] / "db" / "120_pruefregeln_v1.sql"
# Dieselbe Datenbank wie die CLI (UC3_DATABASE_URL, sonst der Standard aus konfig); kein fester Tunnel-Port, sonst
# überspringt `-m daten` auf einem frischen Klon still vier Tests (Jury-Probe 4d, H4).
DATEN_URL = os.environ.get("UC3_DATEN_URL") or konfig.datenbank_url()


def _treffer(conn: Verbindung, lauf_id: int) -> dict[str, dict[str, object]]:
    zeilen = conn.execute(
        """SELECT r.name, t.ebene, t.anzahl, t.umfang, t.beispiele, t.einstufung, t.massnahme, t.anhalten,
                  t.beleg_sql, t.details
           FROM meta.pruefung_treffer t JOIN meta.regel r ON r.id = t.regel_id
           WHERE t.lauf_id = %s""",
        (lauf_id,),
    ).fetchall()
    return {str(z["name"]): z for z in zeilen}


# --- (a) Fixture-Lieferungen ------------------------------------------------------------------------


def test_katalog_hat_24_pruefregeln_ohne_konstanten_im_code(conn: Verbindung) -> None:
    # Fängt: fehlende/doppelte Regelzeile, Art ohne Implementierung, Einstufung außerhalb der CHECK-Werte.
    from statagent.pruefungen import ARTEN

    regeln = [r for r in regeln_laden(conn, "v1", "2024-08") if r.typ == "pruefung"]
    assert [r.reihenfolge for r in regeln] == list(range(1, 25))
    assert all(r.name.startswith(f"P{r.reihenfolge:02d}_") for r in regeln)
    erlaubt = {"erklaert-plausibel", "erklaert-datenproblem", "nicht-erklaerbar"}
    for r in regeln:
        assert r.art in ARTEN, r.name
        assert r.parameter["ebene"] in ("satz", "aggregat", "lieferung"), r.name
        einstufungen = {v for s, v in r.parameter.items() if s.startswith("einstufung")}
        assert einstufungen and einstufungen <= erlaubt, r.name
        assert isinstance(r.parameter.get("anhalten"), bool), r.name


def test_lauf_schreibt_je_pruefregel_einen_treffer(conn: Verbindung) -> None:
    # Fängt: Fallen der Fixture nicht erkannt, Treffer ohne Zeile bei anzahl 0, PERSON_ID als Beispiel,
    # Vormonatsprüfung in der Erstlieferung, falsche Abrechnung, Spaltentausch nicht gemeldet.
    from statagent.lauf import lauf_ausfuehren

    laeufe = {m: lauf_ausfuehren(conn, m, regelsatz="v1") for m in ("2024-08", "2024-09", "2024-10")}
    conn.commit()

    t08 = _treffer(conn, laeufe["2024-08"].lauf_id)
    assert len(t08) == 24
    assert (t08["P01_volldubletten"]["anzahl"], t08["P01_volldubletten"]["beispiele"]) == (1, [1005])
    assert t08["P01_volldubletten"]["einstufung"] == "erklaert-datenproblem"
    assert (t08["P11_oenace_altcode_2003"]["anzahl"], t08["P11_oenace_altcode_2003"]["beispiele"]) == (
        1,
        [1008],
    )
    assert (t08["P10_merkmal_leer"]["anzahl"], t08["P10_merkmal_leer"]["beispiele"]) == (1, [1007])
    assert (t08["P06_alter_unplausibel"]["anzahl"], t08["P06_alter_unplausibel"]["beispiele"]) == (1, [1011])
    assert (t08["P04_geburtsdatum_monat_13"]["anzahl"], t08["P04_geburtsdatum_monat_13"]["beispiele"]) == (
        1,
        [1010],
    )
    assert t08["P03_spaltentausch"]["anzahl"] == 0
    assert t08["P02_mehrere_abschnitte_im_zeitraum"]["anzahl"] == 0  # 1006: Abschnitte schließen an
    assert t08["P12_code_unbekannt"]["anzahl"] == 0
    assert t08["P21_blattsummen"]["anzahl"] == 0
    assert t08["P22_abrechnung"]["umfang"] == "16 = 12 + 3 + 1"
    assert t08["P22_abrechnung"]["anhalten"] is False
    # Fixture: 1006 endet am 30.06.2024 im Fenster (1 von 15 Abschnitten), also kein P24-Treffer.
    assert t08["P24_lieferumfang_fenster"]["anzahl"] == 0
    for name in ("P13_auspraegung_verschwunden", "P15_bestand_vs_vormonat", "P16_verhaeltnisse_verschwunden"):
        assert t08[name]["anzahl"] == 0 and t08[name]["umfang"] == "nicht anwendbar", name
    personen = {5001, 5002, 5005, 5007, 5008, 5010, 5011}
    for name, t in t08.items():
        bsp = t["beispiele"]
        assert isinstance(bsp, list) and len(bsp) <= 5 and not personen & set(bsp), name
        if t["umfang"] != "nicht anwendbar":
            assert str(t["beleg_sql"]).lstrip().startswith(("SELECT", "WITH", "--")), name

    t10 = _treffer(conn, laeufe["2024-10"].lauf_id)
    assert t10["P03_spaltentausch"]["anzahl"] == 9
    assert t10["P03_spaltentausch"]["einstufung"] == "erklaert-datenproblem"
    assert t10["P09_beginn_nach_ende"]["anzahl"] == 0  # nach dem Tausch keine
    # 2024-10 hat keines der Verhältnisse von 2024-09 (Fixture): Lieferumfang hält an.
    assert t10["P16_verhaeltnisse_verschwunden"]["anhalten"] is True
    assert laeufe["2024-10"].ergebnis_status == "vorlaeufig"
    assert "P16_verhaeltnisse_verschwunden" in laeufe["2024-10"].meldung


def test_p08_meldet_ersetztes_ende_e06(conn: Verbindung) -> None:
    # Fängt: ein ungültiges ENDE (Fixture 2024-11: VVH 3003 „2024-02-30“, 3004 „today“), das E06 ersetzt, meldet keine
    # P-Regel; der Qualitätsbericht zeigt die Korrektur dann nicht (Review !13 Runde 3, Punkt 11).
    from statagent.lauf import lauf_ausfuehren

    laeufe = {
        m: lauf_ausfuehren(conn, m, regelsatz="v1") for m in ("2024-08", "2024-09", "2024-10", "2024-11")
    }
    conn.commit()
    p08 = _treffer(conn, laeufe["2024-11"].lauf_id)["P08_beginn_ersetzt"]
    assert p08["anzahl"] == 2 and p08["beispiele"] == [3003, 3004]


def test_belege_sind_ausfuehrbar(conn: Verbindung) -> None:
    # Fängt: Beleg-SQL, das im Qualitätsbericht nicht nachvollziehbar ist (Syntaxfehler, falsche Literale).
    from statagent.lauf import lauf_ausfuehren

    lauf_id = lauf_ausfuehren(conn, "2024-08", regelsatz="v1").lauf_id
    conn.commit()
    for name, t in _treffer(conn, lauf_id).items():
        beleg = t["beleg_sql"]
        if beleg is None or "_bestand" in str(beleg) or "_zellen" in str(beleg):
            continue  # nicht anwendbar bzw. Temp-Tabellen des Laufs (im Beleg gekennzeichnet)
        for teil in str(beleg).split(";\n\n"):
            assert conn.execute(teil.encode()).fetchall() is not None, name
            conn.rollback()


def test_unbekannte_art_bricht_ab(conn: Verbindung) -> None:
    # Fängt: eine Prüfregel ohne Implementierung, die still übergangen wird.
    from statagent.pruefungen import pruefungen_ausfuehren

    regeln = regeln_laden(conn, "v1", "2024-08")
    p01 = next(r for r in regeln if r.name == "P01_volldubletten")
    falsch: list[Regel] = [replace(p01, art="gibt_es_nicht")]
    with pytest.raises(RegelFehler, match="unbekannte Prüfart"):
        pruefungen_ausfuehren(conn, lauf_id=0, lieferung="2024-08", regelsatz="v1", regeln=falsch)


# --- (b) alle 24 Lieferungen ------------------------------------------------------------------------


@pytest.fixture(scope="module")
def daten() -> Iterator[Verbindung]:
    try:
        conn = verbinden(DATEN_URL, autocommit=False)
    except psycopg.OperationalError as fehler:
        # Wer `-m daten` wählt, will diese Tests: fehlende Daten sind ein Fehler, kein Überspringen (wie test_goldenset).
        pytest.fail(f"Datenbank nicht erreichbar ({type(fehler).__name__}); UC3_DATABASE_URL prüfen")
    try:
        conn.execute(DATEI_120.read_text(encoding="utf-8").encode())  # wird mit zurückgerollt
        yield conn
    finally:
        conn.rollback()
        conn.close()


def _pruefen(conn: Verbindung, lieferung: str) -> tuple[list[str], dict[str, dict[str, object]]]:
    from statagent.pruefungen import pruefungen_ausfuehren
    from statagent.zaehlung import zaehlen

    z = conn.execute(
        """SELECT max(id) AS id FROM meta.lauf
           WHERE lieferung = %s AND regelsatz = 'v1' AND status IN ('fertig', 'unveraendert')""",
        (lieferung,),
    ).fetchone()
    if z is None or z["id"] is None:
        pytest.fail(f"kein Lauf {lieferung} in der Datenbank; zuerst uv run uc3 lauf --alle")
    lauf_id = int(str(z["id"]))
    regeln = regeln_laden(conn, "v1", lieferung)
    zaehlen(conn, lieferung=lieferung, berichtsmonat=lieferung, regelsatz="v1", regeln=regeln)
    anhalten = pruefungen_ausfuehren(
        conn, lauf_id=lauf_id, lieferung=lieferung, regelsatz="v1", regeln=regeln
    )
    return anhalten, _treffer(conn, lauf_id)


@pytest.mark.daten
def test_2024_08_erstlieferung(daten: Verbindung) -> None:
    # Fängt: falsche Stichtagsmengen gegen den Beispielbericht; Erstlieferung nicht als Teilabzug erkannt.
    anhalten, t = _pruefen(daten, "2024-08")
    assert anhalten == []
    soll = {
        "P04_geburtsdatum_monat_13": 370,
        "P06_alter_unplausibel": 7,
        "P07_alter_hoch_plausibel": 0,
        "P10_merkmal_leer": 1996,
        "P11_oenace_altcode_2003": 50,
        "P24_lieferumfang_fenster": 1,
    }
    assert {n: t[n]["anzahl"] for n in soll} == soll
    assert t["P22_abrechnung"]["umfang"] == "392.284 = 392.236 + 48 + 0"
    assert t["P15_bestand_vs_vormonat"]["umfang"] == "nicht anwendbar"


@pytest.mark.daten
def test_2025_03_dubletten_und_freier_dienstvertrag(daten: Verbindung) -> None:
    # Fängt: Volldubletten falsch gezählt; verschwundene FD-Ausprägungen nicht erkannt oder nicht angehalten.
    anhalten, t = _pruefen(daten, "2025-03")
    assert t["P01_volldubletten"]["anzahl"] == 1663
    assert t["P02_mehrere_abschnitte_im_zeitraum"]["anzahl"] == 0
    p13 = t["P13_auspraegung_verschwunden"]
    details = p13["details"]
    assert isinstance(details, dict)
    weg = {(a["gliederung"], a["code"]) for a in details["auspraegungen"]}
    assert weg == {("qualifikation", "ArbeiterFD"), ("qualifikation", "AngestellteFD")}
    assert sum(a["vormonat"] for a in details["auspraegungen"]) == 1492
    assert p13["anhalten"] is True and p13["einstufung"] == "erklaert-datenproblem"
    assert "P13_auspraegung_verschwunden" in anhalten


@pytest.mark.daten
def test_2025_05_merkmalswelle(daten: Verbindung) -> None:
    # Fängt: Welle gleicher Codewechsel am selben Tag nicht erkannt (Steiermark O → C).
    _, t = _pruefen(daten, "2025-05")
    p18 = t["P18_merkmalswelle"]
    assert p18["anzahl"] == 491
    assert p18["einstufung"] == "nicht-erklaerbar"
    details = p18["details"]
    assert isinstance(details, dict)
    assert [(w["von"], w["nach"], w["bundesland"]) for w in details["wellen"]] == [("O", "C", "6")]


@pytest.mark.daten
def test_2025_10_unvollstaendige_lieferung_haelt_an(daten: Verbindung) -> None:
    # Fängt: fehlende 79.000 Verhältnisse nicht erkannt (NOT IN mit NULL, falscher Vormonats-Stichtag).
    anhalten, t = _pruefen(daten, "2025-10")
    assert {"P15_bestand_vs_vormonat", "P16_verhaeltnisse_verschwunden", "P17_zeilenzahl_vs_vormonat"} <= set(
        anhalten
    )
    assert t["P16_verhaeltnisse_verschwunden"]["anzahl"] == 78949
    assert t["P16_verhaeltnisse_verschwunden"]["beispiele"] == [34, 79, 95, 122, 133]  # numerisch sortiert
    # Beispiele der Gegenrechnung (dort nach Text sortiert) gehören zu den fehlenden Verhältnissen.
    z = daten.execute(
        """SELECT count(*) AS n FROM bereinigt.abschnitt v
           WHERE v.lieferung = '2025-09' AND v.regelsatz = 'v1' AND v.vvh_id IN (100003, 100005, 100025)
             AND v.beginn <= '2025-09-30' AND (v.ende IS NULL OR v.ende >= '2025-09-30')
             AND NOT EXISTS (SELECT 1 FROM bereinigt.abschnitt a
                             WHERE a.lieferung = '2025-10' AND a.regelsatz = 'v1' AND a.vvh_id = v.vvh_id
                               AND a.herkunft = 'geliefert')"""
    ).fetchone()
    assert z is not None and z["n"] == 3
    assert t["P15_bestand_vs_vormonat"]["umfang"].startswith("313.154 gegen 394.200")  # type: ignore[union-attr]
    assert t["P17_zeilenzahl_vs_vormonat"]["umfang"].startswith("345.078 / 434.104")  # type: ignore[union-attr]
    assert t["P22_abrechnung"]["anhalten"] is False
    assert t["P21_blattsummen"]["anhalten"] is False


def test_blattsummen_folgen_der_beschaeftigungskategorie(conn: Verbindung) -> None:
    # Fängt: Nach Auftrag 1 (R6 zählt nach Beschäftigungskategorie) prüfte P21 die Zellen gegen die fünf
    # Qualifikationscodes; nur „Beamte“ traf, jeder v2-Monat hielt an (Lauf 05.11., Summe 13.187 statt Bestand).
    import json

    from statagent.agenten.regelaenderung import regelsatz_sicherstellen
    from statagent.lauf import lauf_ausfuehren

    regelsatz_sicherstellen(conn, "v2", "v1")
    conn.execute(
        """UPDATE meta.regel SET parameter = parameter || %s::jsonb
           WHERE regelsatz = 'v2' AND typ = 'zaehl' AND art = 'dimension'""",
        (json.dumps({"qualifikation": "beschaeftigungskategorie"}),),
    )
    conn.commit()
    lauf = lauf_ausfuehren(conn, "2024-08", regelsatz="v2")
    conn.commit()
    p21 = _treffer(conn, lauf.lauf_id)["P21_blattsummen"]
    assert p21["anzahl"] == 0, p21
