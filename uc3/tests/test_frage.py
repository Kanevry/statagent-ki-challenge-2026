"""Datenanfragen der Jury (#74): Zeitreihe, Männer und Frauen je Bundesland, Fluktuation je ÖNACE, Rückfrage,
Definition. Jede Zahl wird hier unabhängig nachgerechnet (eigene SQL, nicht der Code von statagent.frage).
Die Antworten laufen zusätzlich unter einer Nur-Lese-Rolle, die bereinigt.* nicht lesen darf.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
import uuid
from collections.abc import Iterator
from typing import Any
from urllib.parse import urlsplit, urlunsplit

import psycopg
import pytest
from psycopg import sql

from statagent import frage as frage_modul
from statagent import konfig
from statagent.agenten import werkzeuge
from statagent.agenten.werkzeuge import AbfrageVerweigert, sql_lesen
from statagent.db import Verbindung, verbinden
from statagent.ergebnis import letzter_lauf, monat_verschieben, monatserster, monatsletzter
from statagent.frage import (
    ALTER_UNKLAR,
    _alter_lesen,
    als_ucantwort,
    als_webantwort,
    antwort_frage,
    fragetyp,
    jahr_ohne_monat,
    monate_lesen,
    nicht_auswertbar,
    rate,
)
from statagent.lauf import lauf_ausfuehren

ZEITREIHE = "Zeitreihe der Beschäftigten 08/2024–07/2026"
GESCHLECHT = "Wie viele Männer und Frauen je Bundesland im August 2024?"
FLUKTUATION = "Fluktuation je Wirtschaftsbereich im September 2024"
DEFINITION = "Was ist ÖNACE C?"
KENNUNGEN = ("vvh_id", "person_id", "geburtsdatum", "roh.", "bereinigt.")


@pytest.fixture
def gerechnet(conn: Verbindung) -> Verbindung:
    lauf_ausfuehren(conn, "2024-08", "v1")
    lauf_ausfuehren(conn, "2024-09", "v1")
    return conn


def _bestand(conn: Verbindung, monat: str, gruppe: str = "") -> dict[tuple[str, ...], int]:
    """Gegenrechnung: maßgeblicher Lauf über ergebnis.letzter_lauf, Summe direkt aus stat.stat_beschaeftigte."""
    stand = letzter_lauf(conn, monat)
    assert stand is not None
    spalten = f"{gruppe}, " if gruppe else ""
    zeilen = conn.execute(
        (
            f"SELECT {spalten}sum(wert)::bigint AS n FROM stat.stat_beschaeftigte WHERE regelsatz = 'v1'"
            " AND regelstand = %s AND zeitraum_art = 'Stichtag' AND variable = 'Beschaeftigungsverhaeltnisse'"
            f" AND zeitraum_bis BETWEEN %s AND %s {'GROUP BY ' + gruppe if gruppe else ''}"
        ).encode(),
        (stand.regelstand, monatserster(monat), monatsletzter(monat)),
    ).fetchall()
    return {tuple(str(v) for k, v in z.items() if k != "n"): int(str(z["n"])) for z in zeilen}


def _bewegung(conn: Verbindung, monat: str) -> dict[str, tuple[int, int]]:
    """Gegenrechnung der Zu- und Abgänge in Python: Mengen der Verhältnisse an beiden Stichtagen."""

    def am(stichtag: object) -> dict[str, str]:
        zeilen = conn.execute(
            """SELECT DISTINCT ON (vvh_id) vvh_id, oenace FROM bereinigt.abschnitt
               WHERE lieferung = %s AND regelsatz = 'v1' AND beginn <= %s AND (ende IS NULL OR ende >= %s)
               ORDER BY vvh_id, beginn DESC, ende DESC NULLS FIRST""",
            (monat, stichtag, stichtag),
        ).fetchall()
        return {str(z["vvh_id"]): str(z["oenace"]) for z in zeilen}

    jetzt, vorher = am(monatsletzter(monat)), am(monatsletzter(monat_verschieben(monat, -1)))
    ergebnis: dict[str, list[int]] = {}
    for vvh, oenace in jetzt.items():
        if vvh not in vorher:
            ergebnis.setdefault(oenace, [0, 0])[0] += 1
    for vvh, oenace in vorher.items():
        if vvh not in jetzt:
            ergebnis.setdefault(oenace, [0, 0])[1] += 1
    return {k: (v[0], v[1]) for k, v in ergebnis.items()}


def _werte(daten: dict[str, Any], wort: str) -> dict[str, float | int]:
    return {z["bezeichnung"]: z["wert"] for z in daten["zahlen"] if z["bezeichnung"].startswith(wort)}


def _pflichtfelder(daten: dict[str, Any]) -> None:
    """AC1: Zahl, sichtbare SQL, Definition, Einheit, Stand; Laientext ohne Gedankenstrich."""
    assert daten["zahlen"] and daten["definition"] and daten["einheit"] and daten["stand"]
    assert all(0 <= z["beleg"] < len(daten["belege"]) for z in daten["zahlen"])
    assert daten["belege"][0]["sql"].lstrip().upper().startswith(("SELECT", "WITH"))
    assert "—" not in daten["text"] and daten["modell"] is None
    # Sprache nach außen (docs/sprache.md): nie „Verhältnis“ allein, Monate ausgeschrieben.
    assert not re.search(r"\bVerhältnis", daten["text"]) and not re.search(r"\d{4}-\d{2}", daten["text"])


# Fängt: Monatsbereich mit Halbgeviertstrich oder Bindestrich wird zu falschen Monaten gelesen, Jahr ohne Monat
# wird übersehen, oder eine Frage landet beim falschen Antworttyp.
@pytest.mark.parametrize(
    ("frage", "monate", "jahr", "typ"),
    [
        (ZEITREIHE, ["2024-08", "2026-07"], None, "zeitreihe"),
        ("Beschäftigte 08/2024-07/2026", ["2024-08", "2026-07"], None, "zeitreihe"),
        (GESCHLECHT, ["2024-08"], None, "geschlecht"),
        (FLUKTUATION, ["2024-09"], None, "fluktuation"),
        ("Beschäftigte 2025", [], "2025", "bestand"),
        (DEFINITION, [], None, "definition"),
        ("Was ist die Fluktuation im März 2025?", ["2025-03"], None, "fluktuation"),
    ],
)
def test_frage_lesen(frage: str, monate: list[str], jahr: str | None, typ: str) -> None:
    assert monate_lesen(frage) == monate
    assert jahr_ohne_monat(frage) == jahr
    assert fragetyp(frage) == typ


# Fängt: Zeitreihe nimmt einen anderen als den maßgeblichen Lauf je Monat oder verschweigt fehlende Monate.
def test_zeitreihe_gleich_gegenrechnung(gerechnet: Verbindung) -> None:
    daten = antwort_frage(gerechnet, ZEITREIHE)
    _pflichtfelder(daten)
    erwartet = {
        f"Beschäftigungsverhältnisse, {name}": _bestand(gerechnet, m)[()]
        for m, name in (("2024-08", "August 2024"), ("2024-09", "September 2024"))
    }
    assert _werte(daten, "Beschäftigungsverhältnisse") == erwartet
    assert [s["monat"] for s in daten["stand"]] == ["2024-08", "2024-09"]
    assert any("22 Monate" in h for h in daten["hinweise"])


# Fängt: Aufteilung nach Geschlecht und Bundesland weicht von stat.stat_beschaeftigte ab oder verliert Zellen.
def test_maenner_frauen_je_bundesland_gleich_gegenrechnung(gerechnet: Verbindung) -> None:
    daten = antwort_frage(gerechnet, GESCHLECHT)
    _pflichtfelder(daten)
    erwartet = _bestand(gerechnet, "2024-08", "geschlecht, region")
    zeilen = [z for z in daten["zahlen"] if not z["bezeichnung"].endswith(", Alle Bundesländer")]
    assert len(zeilen) == len(erwartet)
    assert sum(z["wert"] for z in zeilen) == sum(erwartet.values()) == _bestand(gerechnet, "2024-08")[()]
    namen = {
        str(z["code"]): str(z["bezeichnung"])
        for z in gerechnet.execute("SELECT code, bezeichnung FROM stat.klass_geschlecht").fetchall()
    }
    regionen = {
        str(z["code"]): str(z["bezeichnung"])
        for z in gerechnet.execute("SELECT code, bezeichnung FROM stat.klass_region").fetchall()
    }
    gefunden = _werte(daten, "Beschäftigungsverhältnisse")
    for (geschlecht, region), n in erwartet.items():
        assert gefunden[f"Beschäftigungsverhältnisse, {namen[geschlecht]}, {regionen[region]}"] == n


# Fängt: Die Summenzeile weicht vom Satz im Text oder von der Gegenrechnung ab, ihr Beleg liefert sie nicht, oder sie
# erscheint auch dort, wo man nicht addieren darf (mehrere Monate).
def test_maenner_frauen_summe_alle_bundeslaender(gerechnet: Verbindung) -> None:
    daten = antwort_frage(gerechnet, GESCHLECHT)
    namen = {
        str(z["code"]): str(z["bezeichnung"])
        for z in gerechnet.execute("SELECT code, bezeichnung FROM stat.klass_geschlecht").fetchall()
    }
    gefunden = _werte(daten, "Beschäftigungsverhältnisse")
    erwartet = _bestand(gerechnet, "2024-08", "geschlecht")
    assert erwartet
    for (code,), n in erwartet.items():
        assert gefunden[f"Beschäftigungsverhältnisse, {namen[code]}, Alle Bundesländer"] == n
        assert f"{namen[code]}: {n:,}".replace(",", ".") in daten["text"]
    summen = [z for z in daten["zahlen"] if z["bezeichnung"].endswith(", Alle Bundesländer")]
    assert daten["zahlen"][-len(summen) :] == summen and len(summen) == len(erwartet)
    beleg = daten["belege"][summen[0]["beleg"]]
    assert beleg is not daten["belege"][daten["zahlen"][0]["beleg"]]
    zeilen = gerechnet.execute(beleg["sql"].encode()).fetchall()
    assert sorted(int(str(z["wert"])) for z in zeilen) == sorted(erwartet.values())
    reihe = antwort_frage(gerechnet, "Zeitreihe Männer und Frauen je Bundesland 08/2024 bis 09/2024")
    assert not any("Alle Bundesländer" in z["bezeichnung"] for z in reihe["zahlen"])


# Fängt: Zu- oder Abgänge falsch zugeordnet, Bezugsbestand nicht der veröffentlichte, oder eine Rate trotz
# Bestand 0.
@pytest.mark.parametrize("monat", ["2024-09"])
def test_fluktuation_gleich_gegenrechnung(gerechnet: Verbindung, monat: str) -> None:
    frage = FLUKTUATION
    daten = antwort_frage(gerechnet, frage)
    _pflichtfelder(daten)
    bestand = {k[0]: n for k, n in _bestand(gerechnet, monat, "oenace").items()}
    bewegung = _bewegung(gerechnet, monat)
    assert bewegung, "Fixture ohne Zu- und Abgänge prüft nichts"
    differenzen = []
    zahlen = daten["zahlen"]
    for code in sorted(set(bestand) | set(bewegung)):
        zu, ab = bewegung.get(code, (0, 0))
        b = bestand.get(code, 0)
        eigene = {
            z["bezeichnung"].split(",")[0]: z["wert"] for z in zahlen if f"ÖNACE {code} " in z["bezeichnung"]
        }
        erwartet: dict[str, float | int] = {"Zugänge": zu, "Abgänge": ab, "Bestand am Stichtag": b}
        r = rate(zu, ab, b)
        if r is not None:
            erwartet["Fluktuation"] = r
        if eigene != erwartet:
            differenzen.append((code, eigene, erwartet))
    assert differenzen == []
    if any(bestand.get(code, 0) == 0 for code in bewegung):
        assert daten["hinweise"] and "keine Rate" in daten["text"]


# Fängt: Bestand 0 ergibt eine erfundene Rate (Division durch null oder 0 Prozent).
def test_nullbestand_ohne_rate() -> None:
    assert rate(0, 3, 0) is None
    assert rate(1, 1, 4) == 25.0


# Fängt: eine mehrdeutige Frage („Beschäftigte 2025“) liefert eine Zahl statt einer Rückfrage.
@pytest.mark.parametrize("frage", ["Beschäftigte 2025", "Fluktuation 2025"])
def test_rueckfrage_statt_zahl(gerechnet: Verbindung, frage: str) -> None:
    daten = antwort_frage(gerechnet, frage)
    assert daten["rueckfrage"] is True and daten["typ"] == "rueckfrage"
    assert daten["zahlen"] == [] and daten["belege"] == [] and daten["text"].rstrip().endswith(("?", "“."))
    if frage == "Beschäftigte 2025":
        assert "Dezember 2025" in daten["text"] and "Zeitreihe" in daten["text"]
        assert "„Beschäftigte Jahresdurchschnitt 2025“" in daten["text"]


# Fängt: „Was ist ÖNACE C?“ erfindet die Bezeichnung oder nennt die Version nicht.
def test_definition_oenace_aus_klassifikation(gerechnet: Verbindung) -> None:
    daten = antwort_frage(gerechnet, DEFINITION)
    assert daten["typ"] == "definition" and daten["zahlen"] == []
    zeilen = gerechnet.execute(
        "SELECT version, bezeichnung FROM stat.klass_oenace WHERE code = 'C' ORDER BY version"
    ).fetchall()
    assert {str(z["version"]) for z in zeilen} >= {"2008", "2025"}
    for z in zeilen:
        assert f"ÖNACE {z['version']} C: {z['bezeichnung']}" in daten["definition"]
        assert f"Version {z['version']}" in daten["text"]
    assert "stat.klass_oenace" in daten["belege"][0]["sql"]


# Fängt: das dict passt nicht zum Vertrag UcAntwort (#96).
def test_vertrag_ucantwort(gerechnet: Verbindung) -> None:
    antwortform = pytest.importorskip("plattform.antwortform")
    for frage in (ZEITREIHE, GESCHLECHT, FLUKTUATION, DEFINITION, "Beschäftigte 2025"):
        antwortform.UcAntwort.model_validate(als_ucantwort(antwort_frage(gerechnet, frage)))


# Fängt: frage zieht plattform.llm mit (die Antworten kommen ohne Sprachmodell).
def test_frage_importiert_kein_llm() -> None:
    lauf = subprocess.run(
        [sys.executable, "-c", "import sys, statagent.frage; print('plattform.llm' in sys.modules)"],
        capture_output=True,
        text=True,
        timeout=60,
        check=True,
    )
    assert lauf.stdout.strip() == "False"


@pytest.fixture
def lese_url(gerechnet: Verbindung, admin_url: str, arbeits_db: str) -> Iterator[str]:
    """Rolle, die nur stat/meta/klassifikation lesen darf (kein bereinigt, kein roh) und nur lesend verbindet."""
    rolle, passwort = f"frage_lesen_{uuid.uuid4().hex[:8]}", uuid.uuid4().hex
    db = urlsplit(arbeits_db).path.lstrip("/")
    ident = sql.Identifier(rolle)
    with psycopg.connect(admin_url, autocommit=True) as admin:
        admin.execute(sql.SQL("CREATE ROLE {} LOGIN PASSWORD {}").format(ident, sql.Literal(passwort)))
        admin.execute(sql.SQL("ALTER ROLE {} SET default_transaction_read_only = on").format(ident))
    with psycopg.connect(arbeits_db, autocommit=True) as d:
        d.execute(sql.SQL("GRANT CONNECT ON DATABASE {} TO {}").format(sql.Identifier(db), ident))
        d.execute(sql.SQL("GRANT USAGE ON SCHEMA stat, meta, klassifikation TO {}").format(ident))
        d.execute(
            sql.SQL("GRANT SELECT ON ALL TABLES IN SCHEMA stat, meta, klassifikation TO {}").format(ident)
        )
    teile = urlsplit(arbeits_db)
    host = teile.netloc.rsplit("@", 1)[-1]
    try:
        yield urlunsplit(teile._replace(netloc=f"{rolle}:{passwort}@{host}"))
    finally:
        with psycopg.connect(arbeits_db, autocommit=True) as d:
            d.execute(sql.SQL("DROP OWNED BY {}").format(ident))
        with psycopg.connect(admin_url, autocommit=True) as admin:
            admin.execute(sql.SQL("DROP ROLE IF EXISTS {}").format(ident))


def _datenhash(conn: Verbindung) -> str:
    zeile = conn.execute(
        """SELECT md5(concat_ws('|',
             (SELECT string_agg(t::text, ';' ORDER BY t::text) FROM stat.stat_beschaeftigte t),
             (SELECT string_agg(t::text, ';' ORDER BY t::text) FROM meta.lauf t),
             (SELECT string_agg(t::text, ';' ORDER BY t::text) FROM bereinigt.abschnitt t))) AS h"""
    ).fetchone()
    assert zeile is not None
    return str(zeile["h"])


# Fängt: die Antworten brauchen Schreib- oder Einzeldatenrechte, eine Schreibanweisung geht durch, die Fragen
# verändern Daten, oder Kennungsfelder stehen in SQL oder Ausgabe.
@pytest.mark.parametrize(
    "schreiben",
    [
        "INSERT INTO meta.lauf (lieferung, regelsatz, regelstand) VALUES ('2099-01', 'v1', 'x')",
        "UPDATE stat.stat_beschaeftigte SET wert = wert + 1",
        "DELETE FROM stat.stat_beschaeftigte",
    ],
)
def test_nur_lese_rolle(gerechnet: Verbindung, lese_url: str, schreiben: str) -> None:
    vorher = _datenhash(gerechnet)
    erwartet = {f: antwort_frage(gerechnet, f) for f in (ZEITREIHE, GESCHLECHT, FLUKTUATION, DEFINITION)}
    with verbinden(lese_url) as lesen:
        for frage, daten in erwartet.items():
            assert antwort_frage(lesen, frage) == daten
            for beleg in daten["belege"]:
                assert not any(k in beleg["sql"].lower() for k in KENNUNGEN)
            assert not any(f'"{k}"' in json.dumps(daten, ensure_ascii=False).lower() for k in KENNUNGEN[:3])
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            lesen.execute("SELECT count(*) FROM bereinigt.abschnitt")
        with pytest.raises((psycopg.errors.InsufficientPrivilege, psycopg.errors.ReadOnlySqlTransaction)):
            lesen.execute(schreiben.encode())
    assert _datenhash(gerechnet) == vorher


# Fängt: der Befehl `frage` ist nicht verdrahtet (Stub) oder `--json` liefert etwas anderes als die Antwort.
def test_cli_frage_json(gerechnet: Verbindung, arbeits_db: str, monkeypatch: pytest.MonkeyPatch) -> None:
    from typer.testing import CliRunner

    from statagent import cli

    monkeypatch.setattr(cli, "verbinden", lambda: verbinden(arbeits_db))
    ergebnis = CliRunner().invoke(cli.app, ["frage", FLUKTUATION, "--json"])
    assert ergebnis.exit_code == 0, ergebnis.output
    erwartet = json.loads(
        json.dumps(als_webantwort(antwort_frage(gerechnet, FLUKTUATION)), ensure_ascii=False, default=str)
    )
    assert json.loads(ergebnis.output) == erwartet
    text = CliRunner().invoke(cli.app, ["frage", FLUKTUATION])
    assert text.exit_code == 0 and "SQL [0]: WITH bestand AS" in text.output and "Definition: " in text.output


# Fängt: die SECURITY-DEFINER-Funktion nimmt beliebige Stichtage, ein Agent könnte über sql_lesen die Bewegungen
# eines einzelnen Tages je Abschnitt abfragen (sehr kleine Zellen außerhalb der Definition).
@pytest.mark.parametrize(
    ("vorher", "stichtag"),
    [
        ("2024-09-29", "2024-09-30"),  # ein Tag Abstand
        ("2024-08-31", "2024-09-15"),  # kein Monatsletzter
        ("2024-07-31", "2024-09-30"),  # zwei Monate Abstand
        ("2024-09-30", "2024-10-31"),  # Stichtag nicht im Monat der Lieferung
    ],
)
def test_bewegung_nur_zwischen_monatsletzten(gerechnet: Verbindung, vorher: str, stichtag: str) -> None:
    stand = letzter_lauf(gerechnet, "2024-09")
    assert stand is not None
    abfrage = (
        "SELECT * FROM stat.bewegung_oenace('2024-09', 'v1', "
        f"'{stand.regelstand}', DATE '{vorher}', DATE '{stichtag}')"
    )
    with pytest.raises(psycopg.errors.RaiseException, match="letzten Tag"):
        sql_lesen(gerechnet, abfrage)


# Fängt: online (nur stat/meta, ohne Schema bereinigt) stürzt `frage` mit UndefinedTable ab, statt zu antworten;
# und 160_bewegung.sql lässt sich dort nicht anlegen.
def test_fluktuation_ohne_schema_bereinigt(gerechnet: Verbindung) -> None:
    gerechnet.execute("DROP SCHEMA bereinigt CASCADE")
    gerechnet.execute((konfig.DB_VERZEICHNIS / "160_bewegung.sql").read_text(encoding="utf-8").encode())
    daten = antwort_frage(gerechnet, "Fluktuation je ÖNACE im September 2024")
    assert daten["typ"] == "fluktuation" and daten["zahlen"] == []
    assert "keine bereinigten Einzeldaten" in daten["text"] and daten["hinweise"]


# Fängt: eine bestehende Datenbank ohne `uc3 db init` nach dem Merge kennt stat.bewegung_oenace nicht; `frage`
# stürzt dann vor der Jury mit UndefinedFunction ab, statt den nächsten Schritt zu nennen.
def test_fluktuation_ohne_bewegungsfunktion(gerechnet: Verbindung) -> None:
    gerechnet.execute("DROP FUNCTION stat.bewegung_oenace(text, text, text, date, date)")
    daten = antwort_frage(gerechnet, "Fluktuation je ÖNACE im September 2024")
    assert daten["typ"] == "fluktuation" and daten["zahlen"] == []
    assert "uc3 db init" in daten["text"] and daten["hinweise"]


# Fängt: sql_lesen schneidet nach HOECHSTENS_ZEILEN ab und die Antwort nennt eine Teilsumme, endet zu früh und
# meldet die fehlenden Monate als „noch keinen Lauf“ (Zeitreihe je Bundesland über 24 Monate = 240 Zeilen).
def test_abgeschnittenes_ergebnis_je_monat_gelesen(
    gerechnet: Verbindung, monkeypatch: pytest.MonkeyPatch
) -> None:
    frage = "Zeitreihe nach Bundesland 08/2024 bis 09/2024"
    voll = antwort_frage(gerechnet, frage)
    je_monat: dict[str, int] = {}
    for z in voll["zahlen"]:
        monat = z["bezeichnung"].split(", ")[1]
        je_monat[monat] = je_monat.get(monat, 0) + 1
    assert len(je_monat) == 2
    monkeypatch.setattr(werkzeuge, "HOECHSTENS_ZEILEN", max(je_monat.values()))
    geteilt = antwort_frage(gerechnet, frage)
    assert [(z["bezeichnung"], z["wert"]) for z in geteilt["zahlen"]] == [
        (z["bezeichnung"], z["wert"]) for z in voll["zahlen"]
    ]
    assert len(geteilt["belege"]) == 2 and geteilt["text"] == voll["text"]
    monkeypatch.setattr(werkzeuge, "HOECHSTENS_ZEILEN", 1)
    zu_viel = antwort_frage(gerechnet, frage)
    assert zu_viel["zahlen"] == [] and "zu viele Zahlen" in zu_viel["text"]


# Fängt: eine Reihe nach ÖNACE über den Wechsel 2008/2025 setzt gleiche Buchstaben gleich (2008-K Finanzen
# erschiene als 2025-K) und springt ohne Hinweis.
def test_oenace_reihe_ueber_versionswechsel_abgelehnt(gerechnet: Verbindung) -> None:
    daten = antwort_frage(gerechnet, "Zeitreihe nach ÖNACE 08/2024 bis 03/2025")
    assert daten["zahlen"] == []
    for teil in ("ÖNACE 2008", "ÖNACE 2025", "bis Dezember 2024", "von Jänner 2025 bis März 2025"):
        assert teil in daten["text"]


# Fängt: fortgeschriebene Beschäftigungsverhältnisse (Regel E07) zählen nie als Zu- oder Abgang, die Fluktuation
# fällt zu niedrig aus, ohne dass die Antwort es sagt.
def test_fortgeschriebene_ausgewiesen(gerechnet: Verbindung) -> None:
    gerechnet.execute("UPDATE meta.lauf SET fortgeschrieben = 1234 WHERE lieferung = '2024-09'")
    fluktuation = antwort_frage(gerechnet, FLUKTUATION)
    assert any(
        "1.234 Beschäftigungsverhältnisse aus der Lieferung" in h
        and "Zu- und Abgänge dieses Teils fehlen" in h
        for h in fluktuation["hinweise"]
    )
    reihe = antwort_frage(gerechnet, ZEITREIHE)
    assert any(
        h.startswith("Im September 2024 sind 1.234 Beschäftigungsverhältnisse") for h in reihe["hinweise"]
    )
    assert not any("Im August 2024 sind" in h for h in reihe["hinweise"])


# Fängt: nach einer Regeländerung (Stichtag am 15.) rechnet stat.bewegung_oenace mit ihren eingebauten Regeln
# weiter und liefert eine Fluktuation, die nicht zum Lauf passt; die Absage nennt einen internen Regelstand.
def test_fluktuation_nur_mit_eingebauten_zaehlregeln(gerechnet: Verbindung) -> None:
    stand_alt = letzter_lauf(gerechnet, "2024-09")
    assert stand_alt is not None
    gerechnet.execute(
        """UPDATE meta.regel SET parameter = parameter || '{"von": "tag:15", "bis": "tag:15"}'::jsonb,
             freigegeben_am = CASE WHEN freigegeben_von IS NULL THEN NULL ELSE now() END
           WHERE regelsatz = 'v1' AND typ = 'zaehl' AND art = 'bestand'"""
    )
    geaendert = antwort_frage(gerechnet, FLUKTUATION)
    assert geaendert["zahlen"] == [] and "Regeln wurden geändert" in geaendert["text"]
    lauf_ausfuehren(gerechnet, "2024-09", "v1")
    neu = antwort_frage(gerechnet, FLUKTUATION)
    assert neu["zahlen"] == [] and "R2_R4_stichtag_eigene_lieferung" in neu["text"]
    for daten in (geaendert, neu):
        assert stand_alt.regelstand not in daten["text"] and "behebt" not in daten["text"]


# Fängt: ein Lauf mit Monatszählung (zeitraum_art Monat) ergibt in der Stichtagsfrage 0 statt „keine Zahl“.
def test_monatszaehlung_ergibt_keine_zahl(gerechnet: Verbindung) -> None:
    gerechnet.execute(
        "UPDATE stat.stat_beschaeftigte SET zeitraum_art = 'Monat', zeitraum_von = DATE '2024-09-01'"
        " WHERE zeitraum_bis = DATE '2024-09-30'"
    )
    daten = antwort_frage(gerechnet, "Beschäftigte September 2024")
    assert daten["zahlen"] == [] and "nicht am Stichtag" in daten["text"]
    reihe = antwort_frage(gerechnet, "Zeitreihe 08/2024 bis 09/2024")
    assert [z["bezeichnung"] for z in reihe["zahlen"]] == ["Beschäftigungsverhältnisse, August 2024"]


# Fängt: Zeitlimit (QueryCanceled) oder eine verweigerte Abfrage enden im Traceback statt in einer Textantwort.
@pytest.mark.parametrize(
    "fehler", [AbfrageVerweigert("intern"), psycopg.errors.QueryCanceled("canceling statement")]
)
@pytest.mark.parametrize("frage", [GESCHLECHT, FLUKTUATION, DEFINITION, ZEITREIHE])
def test_kein_traceback(
    gerechnet: Verbindung, monkeypatch: pytest.MonkeyPatch, fehler: Exception, frage: str
) -> None:
    def wirft(conn: Verbindung, query: str) -> dict[str, Any]:
        raise fehler

    monkeypatch.setattr(frage_modul, "sql_lesen", wirft)
    daten = antwort_frage(gerechnet, frage)
    assert daten["zahlen"] == [] and daten["text"] == frage_modul.NICHT_LESBAR
    assert "intern" not in daten["text"] and "canceling" not in daten["text"]


# Fängt: „Die Zahlen sind endgültig und vorläufig.“ und „noch kein Lauf“ für Monate, zu denen es keine Lieferung
# gibt (vor August 2024).
def test_sprache_status_und_monate_ohne_lieferung(gerechnet: Verbindung) -> None:
    staende = [{"monat": "2024-08", "status": "endgueltig"}, {"monat": "2024-09", "status": "vorlaeufig"}]
    assert frage_modul._status_text(staende) == "teils endgültig, teils vorläufig (vorläufig: September 2024)"
    for frage in ("Beschäftigte Juli 2024", "Fluktuation im Juli 2024"):
        daten = antwort_frage(gerechnet, frage)
        assert daten["zahlen"] == [] and "Für Juli 2024 gibt es keine Lieferung" in daten["text"]
    reihe = antwort_frage(gerechnet, "Zeitreihe 06/2024 bis 09/2024")
    assert any("2 Monate im Zeitraum gibt es keine Lieferung" in h for h in reihe["hinweise"])


# Fängt: `frage --json` liefert Felder außerhalb der Antwortform; die Webseite /uc3/fragen (!51) entfernt nur
# definition und rueckfrage, prüft den Rest streng (.strict()) und lehnte sonst jede Antwort ab.
@pytest.mark.parametrize(
    ("frage", "art"),
    [
        ("Beschäftigte August 2024", "zahl"),
        ("Zeitreihe 08/2024 bis 09/2024", "zahl"),
        ("Beschäftigte 2025", "rueckfrage"),
        ("Zeitreihe nach ÖNACE 08/2024 bis 03/2025", "absage"),
        ("Beschäftigte Juli 2024", "absage"),
    ],
)
def test_cli_json_ist_antwortform_der_webseite(
    gerechnet: Verbindung, arbeits_db: str, monkeypatch: pytest.MonkeyPatch, frage: str, art: str
) -> None:
    from typer.testing import CliRunner

    from statagent import cli

    antwortform = pytest.importorskip("plattform.antwortform")
    monkeypatch.setattr(cli, "verbinden", lambda: verbinden(arbeits_db))
    ergebnis = CliRunner().invoke(cli.app, ["frage", "--json", "--", frage])
    assert ergebnis.exit_code == 0, ergebnis.output
    daten = json.loads(ergebnis.output)
    definition, rueckfrage = daten.pop("definition"), daten.pop("rueckfrage")
    antwortform.UcAntwort.model_validate(daten)
    assert definition is None or isinstance(definition, str)
    if art == "rueckfrage":
        assert isinstance(rueckfrage, str) and rueckfrage == daten["text"] and daten["zahlen"] == []
    else:
        assert rueckfrage is None
    assert (art == "zahl") == bool(daten["zahlen"])


# --- Jury-Probe (#74, note_271969): nie still falsch -----------------------------------------------------------


# Fängt: die Antwort sagt nicht, was verstanden wurde; ein übergangenes Merkmal bleibt unsichtbar.
def test_verstanden_satz(gerechnet: Verbindung) -> None:
    daten = antwort_frage(gerechnet, "Beschäftigte in Wien im August 2024")
    assert daten["text"].startswith(
        "Verstanden: August 2024, Bundesland Wien, Geschlecht: alle, Branche: alle, Beschäftigungskategorie: alle."
    )
    assert daten["zahlen"][0]["wert"] == _bestand(gerechnet, "2024-08", "region")[("9",)]


# Fängt: Alter, Durchschnitt, freie Dienstverträge, Personen oder ein unbekannter Ort fallen still weg und die
# Antwort ist der Gesamtbestand (Jury-Probe: 13 falsche Antworten).
@pytest.mark.parametrize(
    ("frage", "grund"),
    [
        ("Wie viele Jobs hatte Person 1234567 im August 2024?", "Einzeldaten"),
        ("Beschäftigte in Atlantis im August 2024", "„Atlantis“"),
        ("Beschäftigte im Bergbaubetrieb im August 2024", "„Bergbaubetrieb“"),
    ],
)
def test_nicht_auswertbar_ehrlich_abgesagt(gerechnet: Verbindung, frage: str, grund: str) -> None:
    daten = antwort_frage(gerechnet, frage)
    assert daten["zahlen"] == [] and grund in daten["text"]
    assert "StatAgent beantwortet" in daten["text"]


# Fängt: zwei Werte eines Merkmals liefern die Zahl für nur einen davon.
@pytest.mark.parametrize(
    "frage",
    [
        "Beschäftigte in Wien und Tirol im August 2024",
        "Wie viele Arbeiter und Angestellte gab es im August 2024?",
        "Vergleich Wien und Tirol im August 2024",
    ],
)
def test_zwei_werte_eines_merkmals_abgesagt(gerechnet: Verbindung, frage: str) -> None:
    daten = antwort_frage(gerechnet, frage)
    assert daten["zahlen"] == [] and "Die Frage nennt mehrere" in daten["text"]


# Fängt: „von März bis Juni 2025“ liest nur Juni; „entwickelt“ ist keine Zeitreihe; „letztes Jahr“ bleibt offen.
def test_zeitraum_und_entwicklung(gerechnet: Verbindung) -> None:
    frage, _ = frage_modul.normalisieren("Wie viele Beschäftigte gab es von März bis Juni 2025?")
    assert monate_lesen(frage) == ["2025-03", "2025-06"] and fragetyp(frage) == "zeitreihe"
    assert fragetyp("Wie hat sich Wien gegenüber dem Vormonat entwickelt?") == "zeitreihe"
    frage, notizen = frage_modul.normalisieren("Wie haben sich die Beschäftigten im letzten Jahr entwickelt?")
    assert jahr_ohne_monat(frage) == "2025" and notizen == ["„Letztes Jahr“ heißt hier 2025."]
    daten = antwort_frage(gerechnet, "Wie viele Beschäftigte gab es von August bis September 2024?")
    assert [z["wert"] for z in daten["zahlen"]] == [
        _bestand(gerechnet, m)[()] for m in ("2024-08", "2024-09")
    ]


# Fängt: umgangssprachliche Branchen („Bau“, „Gesundheitswesen“) fallen still weg, oder der Buchstabe der falschen
# ÖNACE-Version wird genommen (Gesundheit 2008 = Q, 2025 = R).
def test_branchennamen_je_version(gerechnet: Verbindung) -> None:
    je_abschnitt = {k[0]: n for k, n in _bestand(gerechnet, "2024-08", "oenace").items()}
    bau = antwort_frage(gerechnet, "Wie viele Beschäftigte hatte der Bau im August 2024?")
    assert [z["wert"] for z in bau["zahlen"]] == [je_abschnitt["F"]] and "Branche F Bau" in bau["text"]
    pflege = antwort_frage(gerechnet, "Wie viele arbeiten im Gesundheitswesen im August 2024?")
    assert [z["wert"] for z in pflege["zahlen"]] == [je_abschnitt["Q"]]
    v2025 = {"Q": "Erziehung und Unterricht", "R": "Gesundheits- und Sozialwesen"}
    assert frage_modul._werte("im gesundheitswesen", frage_modul.OENACE, v2025)[0] == ["R"]


# Fängt: Fluktuation für August 2024 (erste Lieferung, kein Vollabzug), mit übergangenem Bundesland-Filter,
# „am höchsten“ in einem Kleinstbereich, und die Rückfrage ohne Weg zu einer Antwort.
def test_fluktuation_ehrlich(gerechnet: Verbindung) -> None:
    august = antwort_frage(gerechnet, "Fluktuation im August 2024")
    assert august["zahlen"] == [] and "erste Lieferung" in august["text"]
    wien = antwort_frage(gerechnet, "Wie hoch war die Fluktuation in Wien im September 2024?")
    assert wien["zahlen"] == [] and "nur für ganz Österreich" in wien["text"]
    september = antwort_frage(gerechnet, FLUKTUATION)
    assert september["zahlen"] and "Am höchsten" not in september["text"]  # Fixture: kein Abschnitt ≥ 1.000
    bau = antwort_frage(gerechnet, "Zu- und Abgänge im Bau im September 2024")
    assert bau["zahlen"] and "gefragt war die Branche F Bau" in bau["text"]
    for frage in ("Wie hoch war die Fluktuation 2025?", "Fluktuation von 01/2025 bis 12/2025"):
        rueck = antwort_frage(gerechnet, frage)
        vorschlag = re.search(r"„(Fluktuation je Wirtschaftsbereich im [^“]+)“", rueck["text"])
        assert rueck["rueckfrage"] and vorschlag
        assert antwort_frage(gerechnet, vorschlag.group(1))["typ"] == "fluktuation"


# Fängt: „Was zählt als Beschäftigte?“ wird als Datenfrage ohne Monat behandelt.
def test_definition_was_zaehlt(gerechnet: Verbindung) -> None:
    assert antwort_frage(gerechnet, "Was zählt als Beschäftigte?")["typ"] == "definition"


# Fängt: „Frauen in Wien“ liefert Männer und Frauen; der Frauenanteil kommt ohne Prozent.
def test_ein_geschlecht_und_anteil(gerechnet: Verbindung) -> None:
    je = _bestand(gerechnet, "2024-08", "geschlecht, region")
    frauen = antwort_frage(gerechnet, "Wie viele Frauen arbeiten im August 2024 in Wien?")
    assert [z["wert"] for z in frauen["zahlen"]] == [je[("W", "9")]]
    anteil = antwort_frage(gerechnet, "Wie hoch ist der Frauenanteil im August 2024?")
    gesamt = sum(je.values())
    frauen_gesamt = sum(n for (g, _), n in je.items() if g == "W")
    prozent = {z["bezeichnung"]: z["wert"] for z in anteil["zahlen"] if z["einheit"] == "Prozent"}
    assert prozent["Anteil an allen, Frauen"] == round(100 * frauen_gesamt / gesamt, 2)


# --- Review-Bank 69 zu !85 --------------------------------------------------------------------------------------


# Fängt: „am höchsten“ verschweigt die Schwelle, die Tabelle zeigt einen kleineren Abschnitt mit höherer Rate.
def test_hoechste_nennt_schwelle() -> None:
    zeilen = [
        {"oenace": "A", "bestand": 5000, "fluktuation_prozent": 3.0},
        {"oenace": "T", "bestand": 250, "fluktuation_prozent": 20.0},
    ]
    satz = frage_modul.hoechste_satz(zeilen, {"A": "Land", "T": "Haushalte"})
    assert satz is not None and satz.startswith("Unter den Abschnitten mit mindestens 1.000")
    assert "Abschnitt A" in satz and "Abschnitt T" not in satz
    assert frage_modul.hoechste_satz(zeilen[1:], {}) is None


# Fängt: Branchenwörter ohne Wortgrenze („handelt“ → Handel, „Datenbank“ → Finanz) und Zusammensetzungen nach
# „im“ („Produktionslauf“, „Hausverwaltung“), die still als Branche gelten.
@pytest.mark.parametrize(
    "frage",
    [
        "Um wie viele Beschäftigte handelt es sich im August 2024?",
        "Beschäftigte laut Datenbank im August 2024",
        "Beschäftigte mit Ausbildung im August 2024",
    ],
)
def test_branchen_nur_ganze_woerter(gerechnet: Verbindung, frage: str) -> None:
    daten = antwort_frage(gerechnet, frage)
    assert (
        "Branche: alle" in daten["text"] and daten["zahlen"][0]["wert"] == _bestand(gerechnet, "2024-08")[()]
    )


@pytest.mark.parametrize(
    "frage",
    ["Beschäftigte im Produktionslauf August 2024", "Beschäftigte in der Hausverwaltung im August 2024"],
)
def test_unbekannte_zusammensetzung_abgesagt(gerechnet: Verbindung, frage: str) -> None:
    daten = antwort_frage(gerechnet, frage)
    assert daten["zahlen"] == [] and "kenne ich nicht" in daten["text"]


# Fängt: „weibliche Beschäftigte“ ergibt den Gesamtbestand mit „Geschlecht: alle“.
@pytest.mark.parametrize(("wort", "code"), [("weibliche", "W"), ("männliche", "M"), ("Maenner", "M")])
def test_geschlecht_synonyme(gerechnet: Verbindung, wort: str, code: str) -> None:
    daten = antwort_frage(gerechnet, f"Wie viele {wort} Beschäftigte gab es im August 2024?")
    assert [z["wert"] for z in daten["zahlen"]] == [_bestand(gerechnet, "2024-08", "geschlecht")[(code,)]]


# Fängt: Beugungen und Füllwörter nach „in“ führen zu einer Fehlabsage der Jury-Kernfrage.
@pytest.mark.parametrize(
    "frage",
    [
        "Fluktuation in den Wirtschaftsbereichen im September 2024",
        "Fluktuation in den Branchen im September 2024",
        "Fluktuation in den Abschnitten im September 2024",
        "Beschäftigte im Bereich Handel im August 2024",
        "Beschäftigte in der Branche Bau im August 2024",
        "Beschäftigte in Wien im Gesundheits- und Sozialwesen im August 2024",  # Vorführfrage 5
        "Fluktuation in Prozent im September 2024",
        "Beschäftigte im August 2024 im Vergleich zum Vormonat",
        "Beschäftigte im Vormonat August 2024",
    ],
)
def test_keine_fehlabsage_bei_beugung(gerechnet: Verbindung, frage: str) -> None:
    daten = antwort_frage(gerechnet, frage)
    assert "kenne ich nicht" not in daten["text"] and daten["zahlen"]


# Fängt: „Vergleich“ mit genau einem Monat löst eine Zeitreihe bis heute aus.
def test_vergleich_mit_einem_monat(gerechnet: Verbindung) -> None:
    daten = antwort_frage(gerechnet, "Vergleich Männer und Frauen im August 2024")
    assert daten["typ"] == "geschlecht" and len(daten["zahlen"]) == 2


# Fängt: „von November bis Februar 2025“ wird zu Februar bis November 2025.
def test_von_bis_ueber_jahreswechsel() -> None:
    frage, notizen = frage_modul.normalisieren("Beschäftigte von November bis Februar 2025")
    assert monate_lesen(frage) == ["2024-11", "2025-02"] and notizen


# Fängt: kleingeschriebene oder nachgereihte Orte („in graz“, „in Wien und Graz“) fallen still weg.
@pytest.mark.parametrize(
    "frage", ["beschäftigte in graz im august 2024", "Beschäftigte in Wien und Graz im August 2024"]
)
def test_unbekannter_ort_abgesagt(gerechnet: Verbindung, frage: str) -> None:
    daten = antwort_frage(gerechnet, frage)
    assert daten["zahlen"] == [] and "„graz“" in daten["text"].lower()


# Fängt: „ÖNACE C und ÖNACE F“ liefert nur C.
def test_zwei_oenace_codes_abgesagt(gerechnet: Verbindung) -> None:
    daten = antwort_frage(gerechnet, "Beschäftigte in ÖNACE C und ÖNACE F im August 2024")
    assert daten["zahlen"] == [] and "Die Frage nennt mehrere" in daten["text"]


# Fängt: freie Dienstverträge werden fälschlich als nicht vorhanden abgesagt; sie sind die FD-Qualifikationen.
# „freie DV“ fiel durch (dv ≠ dienstv) und lieferte still den ungefilterten Bestand (Review 69).
@pytest.mark.parametrize(
    "frage",
    [
        "Wie viele freie Dienstverträge gab es im August 2024?",
        "Wie viele freie DV gab es im August 2024?",
        "Anzahl der freien DV im August 2024",
    ],
)
def test_freie_dienstvertraege_gezaehlt(gerechnet: Verbindung, frage: str) -> None:
    stand = letzter_lauf(gerechnet, "2024-08")
    assert stand is not None
    z = gerechnet.execute(
        """SELECT sum(s.wert) AS n FROM stat.stat_beschaeftigte s JOIN stat.klass_qualifikation q
             ON q.code = s.qualifikation AND q.freier_dienstvertrag
           WHERE s.regelsatz = 'v1' AND s.regelstand = %s AND s.zeitraum_art = 'Stichtag'
             AND s.variable = 'Beschaeftigungsverhaeltnisse' AND s.zeitraum_bis = DATE '2024-08-31'""",
        (stand.regelstand,),
    ).fetchone()
    assert z is not None
    daten = antwort_frage(gerechnet, frage)
    assert [x["wert"] for x in daten["zahlen"]] == [int(str(z["n"]))] and "nur freie Dienstverträge" in daten[
        "text"
    ]


# Fängt: Fehlabsagen durch zu breite Signalwörter (alte Regel, vorjährig, Dauer, Name eines Abschnitts, Mengen).
@pytest.mark.parametrize(
    "frage",
    [
        "Beschäftigte nach alter Regel im August 2024",
        "Beschäftigte gegenüber dem vorjährigen Monat August 2024",
        "Wie ist der Name von ÖNACE K?",
        "Gab es im August 2024 über 10000 Beschäftigte?",
    ],
)
def test_keine_fehlabsage_signalwort(frage: str) -> None:
    assert frage_modul.nicht_auswertbar(frage) is None


# Fängt: Altersfragen ohne eindeutige Angabe und Dauerfragen fallen durch und liefern still den Gesamtbestand (Review 69).
@pytest.mark.parametrize(
    ("frage", "grund"),
    [
        ("Wie viele Jugendliche gab es im August 2024?", "alter"),
        ("Wie alt sind die Beschäftigten im August 2024?", "alter"),
        ("Beschäftigte im Alter im August 2024", "alter"),
        ("30-Jährige und 40-Jährige im August 2024", "alter"),
        ("Beschäftigte, die über 2 Jahre beschäftigt sind, im August 2024", "wie lange"),
        ("Wie viele sind seit über 2 Jahren beschäftigt im August 2024?", "wie lange"),
    ],
)
def test_absage_alter_und_dauer(frage: str, grund: str) -> None:
    text = frage_modul.nicht_auswertbar(frage)
    assert text is not None and grund in text.lower()


# Fängt: Notizen („Letztes Jahr heißt …“) stehen vor dem Verstanden-Satz statt danach.
def test_notizen_nach_verstanden(gerechnet: Verbindung) -> None:
    daten = antwort_frage(gerechnet, "Wie haben sich die Beschäftigten im letzten Jahr entwickelt?")
    assert daten["text"].startswith("Verstanden: Jänner 2025 bis Dezember 2025")
    assert daten["text"].index("„Letztes Jahr“ heißt hier 2025.") > daten["text"].index("alle.")


# --- Zeiträume der Alltagssprache (Owner 05.11., „Sommer“) ------------------------------------------------------


# Fängt: eine Jahreszeit ergibt keine Zahl, der Durchschnitt fehlt oder ist falsch gerundet, „Durchschnitt“ wird
# trotz Zeitraum abgesagt, oder der Text sagt nicht, welche Monate gemeint sind.
def test_jahreszeit_monate_und_durchschnitt(gerechnet: Verbindung) -> None:
    for monat in ("2024-10", "2024-11"):
        lauf_ausfuehren(gerechnet, monat, "v1")
    soll = [_bestand(gerechnet, m)[()] for m in ("2024-09", "2024-10", "2024-11")]
    mittel = (2 * sum(soll) + 3) // 6
    for frage in (
        "Wie viele Beschäftigte gab es im Herbst 2024?",
        "Durchschnitt der Beschäftigten im Herbst 2024",
    ):
        daten = antwort_frage(gerechnet, frage)
        assert [z["wert"] for z in daten["zahlen"]] == [*soll, mittel], frage
        assert "Herbst 2024 heißt hier September bis November 2024." in daten["text"]
        assert f"Im Durchschnitt waren es {mittel:,} (".replace(",", ".") in daten["text"]
    quartal = antwort_frage(gerechnet, "Beschäftigte im 4. Quartal 2024")
    assert [z["wert"] for z in quartal["zahlen"]][:2] == soll[1:]
    assert "Für 1 Monat im Zeitraum gibt es noch keinen Lauf: Dezember 2024." in quartal["text"]


# Fängt: ohne Zeitangabe kommt eine Rückfrage statt der Zahl des jüngsten Monats; ein Monat ohne Lieferung nennt
# nicht, welche Monate es gibt.
def test_ohne_zeitangabe_juengster_monat_und_vorhandene_monate(gerechnet: Verbindung) -> None:
    frauen = antwort_frage(gerechnet, "Wie viele Frauen?")
    je = _bestand(gerechnet, "2024-09", "geschlecht")
    assert [z["wert"] for z in frauen["zahlen"]] == [je[("W",)]]
    assert "Ohne Zeitangabe zeigen wir den jüngsten Monat: September 2024." in (frauen["text"])
    vorher = antwort_frage(gerechnet, "Beschäftigte Juli 2024")
    assert "Daten gibt es nur für August 2024 bis Juli 2026." in vorher["text"]
    assert "Meinen Sie „Beschäftigte im August 2024“?" in vorher["text"]


# Fängt: Der Durchschnitt wird in Python gerechnet, sein Beleg zeigt auf eine Monatsabfrage, das SQL liefert also
# nicht die gezeigte Zahl; bei einer Lücke steht „X bis Y“ auf einem Durchschnitt, der einen Monat auslässt.
def test_durchschnitt_eigene_abfrage_und_luecke(gerechnet: Verbindung) -> None:
    for monat in ("2024-10", "2024-11"):
        lauf_ausfuehren(gerechnet, monat, "v1")
    daten = antwort_frage(gerechnet, "Beschäftigte im Herbst 2024")
    mittel = daten["zahlen"][-1]
    beleg = daten["belege"][mittel["beleg"]]
    assert beleg is not daten["belege"][daten["zahlen"][0]["beleg"]]
    zeile = gerechnet.execute(beleg["sql"].encode()).fetchone()
    assert zeile is not None and int(str(zeile["wert"])) == mittel["wert"]
    assert mittel["bezeichnung"].endswith("Durchschnitt September bis November 2024")
    assert beleg["stand"] == "vorlaeufig"

    gerechnet.execute("UPDATE meta.lauf SET status = 'abgebrochen' WHERE lieferung = '2024-10'")
    soll = [_bestand(gerechnet, m)[()] for m in ("2024-09", "2024-11")]
    luecke = antwort_frage(gerechnet, "Beschäftigte im Herbst 2024")["zahlen"]
    assert [z["wert"] for z in luecke] == [*soll, (2 * sum(soll) + 2) // 4]
    assert luecke[-1]["bezeichnung"].endswith("Durchschnitt September 2024 und November 2024")


# Fängt: Ein Jahr vor dem Monat oder „letzten Jahres“ wird zum jüngsten Monat (Prüfung !169); ohne eindeutiges Jahr
# kommt eine Zahl statt einer Rückfrage.
def test_jahr_vor_dem_monat_und_unklares_jahr(gerechnet: Verbindung) -> None:
    soll = _bestand(gerechnet, "2024-09")[()]
    for frage in ("Wie viele Beschäftigte gab es 2024 im September?", "September in 2024"):
        daten = antwort_frage(gerechnet, frage)
        assert [z["wert"] for z in daten["zahlen"]] == [soll], frage
    unklar_jahr = antwort_frage(gerechnet, "Beschäftigte 2023 und 2024 im September")
    assert unklar_jahr["zahlen"] == [] and "nicht eindeutig" in unklar_jahr["text"]
    assert unklar_jahr["rueckfrage"] is True


# Fängt: Ein Vorschlag der Rückfrage (auf /uc3/fragen ein Knopf) führt zu einer weiteren Rückfrage oder zu keiner Zahl.
def test_vorschlaege_der_jahr_rueckfrage_funktionieren_als_frage(gerechnet: Verbindung) -> None:
    for monat in ("2024-10", "2024-11"):  # die Fixture hat vier Lieferungen, Dezember fehlt
        lauf_ausfuehren(gerechnet, monat, "v1")
    text = antwort_frage(gerechnet, "Beschäftigte 2024")["text"]
    vorschlaege = re.findall(r"„([^“]+)“", text)
    assert vorschlaege == [
        "Beschäftigte Dezember 2024",
        "Beschäftigte Jahresdurchschnitt 2024",
        "Zeitreihe 08/2024 bis 12/2024",
    ]
    soll = [_bestand(gerechnet, m)[()] for m in ("2024-08", "2024-09", "2024-10", "2024-11")]
    monat, mittel, reihe = (antwort_frage(gerechnet, v) for v in vorschlaege)
    assert not monat["rueckfrage"] and "Dezember 2024" in monat["text"]
    assert [z["wert"] for z in mittel["zahlen"]] == [*soll, (2 * sum(soll) + 4) // 8] and not mittel[
        "rueckfrage"
    ]
    assert [z["wert"] for z in reihe["zahlen"]] == soll and not reihe["rueckfrage"]


def _im_alter(conn: Verbindung, monat: str, von: int, bis: int) -> int:
    stand = letzter_lauf(conn, monat)
    assert stand is not None
    zeile = conn.execute(
        "SELECT COALESCE(sum(wert), 0) AS n FROM stat.stat_beschaeftigte WHERE regelsatz = 'v1' AND regelstand = %s"
        " AND zeitraum_art = 'Stichtag' AND variable = 'Beschaeftigungsverhaeltnisse' AND zeitraum_bis = %s"
        " AND alter BETWEEN %s AND %s",
        (stand.regelstand, monatsletzter(monat), von, bis),
    ).fetchone()
    assert zeile is not None
    return int(str(zeile["n"]))


# Fängt: Eine Altersfrage wird abgesagt, ergibt den Gesamtbestand, oder die Grenzen sind um eins verschoben.
@pytest.mark.parametrize(
    ("frage", "von", "bis", "wort"),
    [
        ("Wie viele 30-Jährige gab es im August 2024?", 30, 30, "Alter 30 Jahre"),
        ("Beschäftigte im Alter von 30 im August 2024", 30, 30, "Alter 30 Jahre"),
        ("Wie viele Beschäftigte unter 25 Jahren gab es im August 2024?", 0, 24, "Alter unter 25 Jahre"),
        ("Beschäftigte über 50 Jahren im August 2024", 51, 130, "Alter 51 Jahre und älter"),
        ("Beschäftigte ab 65 Jahren im August 2024", 65, 130, "Alter ab 65 Jahre"),
        ("Beschäftigte unter 25 im August 2024", 0, 24, "Alter unter 25 Jahre"),
        ("Beschäftigte über 50 im August 2024", 51, 130, "Alter 51 Jahre und älter"),
        ("Beschäftigte älter als 50 im August 2024", 51, 130, "Alter 51 Jahre und älter"),
        ("Beschäftigte jünger als 30 im August 2024", 0, 29, "Alter unter 30 Jahre"),
        ("Beschäftigte zwischen 25 und 34 Jahren im August 2024", 25, 34, "Alter 25 bis 34 Jahre"),
        ("25- bis 34-Jährige im August 2024", 25, 34, "Alter 25 bis 34 Jahre"),
    ],
)
def test_alter_und_spanne(gerechnet: Verbindung, frage: str, von: int, bis: int, wort: str) -> None:
    daten = antwort_frage(gerechnet, frage)
    assert [z["wert"] for z in daten["zahlen"]] == [_im_alter(gerechnet, "2024-08", von, bis)]
    assert wort in daten["text"]


# Fängt: Die Altersgruppen weichen vom Bestand ab oder eine zweite Aufteilung fällt still weg.
def test_altersgruppen(gerechnet: Verbindung) -> None:
    daten = antwort_frage(gerechnet, "Beschäftigte nach Altersgruppe im August 2024")
    gesamt = _bestand(gerechnet, "2024-08")[()]
    summe = daten["zahlen"][-1]
    assert summe["bezeichnung"].endswith(", Alle Altersstufen") and summe["wert"] == gesamt
    assert sum(z["wert"] for z in daten["zahlen"][:-1]) == gesamt
    assert "je Alter" in daten["text"]
    assert daten["belege"][summe["beleg"]] is not daten["belege"][daten["zahlen"][0]["beleg"]]
    wort = next(z["bezeichnung"].rsplit(", ", 1)[-1] for z in daten["zahlen"][:-1] if z["wert"])
    zeile = next(z for z in daten["zahlen"] if z["bezeichnung"].endswith(f", {wort}"))
    if wort.removesuffix(" Jahre").isdigit():
        alter = int(wort.removesuffix(" Jahre"))
        assert zeile["wert"] == _im_alter(gerechnet, "2024-08", alter, alter)
    namen = [z["bezeichnung"].rsplit(", ", 1)[-1] for z in daten["zahlen"][:-1]]
    alter_zeilen = [int(n.removesuffix(" Jahre")) for n in namen if n.removesuffix(" Jahre").isdigit()]
    assert alter_zeilen == sorted(alter_zeilen)
    assert "75 u. mehr" not in namen and "unbekannt" not in namen
    for frage in (
        "Männer und Frauen je Altersgruppe im August 2024",
        "Beschäftigte nach Altersgruppe je Bundesland im August 2024",
    ):
        absage = antwort_frage(gerechnet, frage)
        assert absage["zahlen"] == [] and "Die Zahlen je Alter gibt es nur ohne" in absage["text"]


# Fängt: Mehrere Altersangaben ergeben still die erste, das Durchschnittsalter steht in jeder Altersabsage.
@pytest.mark.parametrize(
    "frage",
    [
        "30-Jährige und 40-Jährige im August 2024",
        "unter 25 Jahren und über 50 Jahren im August 2024",
        "Beschäftigte unter 200 Jahren und 300-Jährige im August 2024",
        "Beschäftigte über 130 Jahre im August 2024",
    ],
)
def test_alter_nicht_eindeutig_keine_zahl(gerechnet: Verbindung, frage: str) -> None:
    daten = antwort_frage(gerechnet, frage)
    assert daten["zahlen"] == [] and daten["text"] == ALTER_UNKLAR
    assert "Durchschnittsalter" not in daten["text"]


# Gegenfall: Das Durchschnittsalter bleibt mit eigenem Satz abgesagt.
def test_durchschnittsalter_keine_zahl(gerechnet: Verbindung) -> None:
    daten = antwort_frage(gerechnet, "Durchschnittsalter der Beschäftigten im August 2024")
    assert daten["zahlen"] == [] and "Durchschnittsalter" in daten["text"]


# Fix-Liste !227, Punkt 1: Der Tausenderpunkt galt als Satzende, aus Mengen wurde ein Alter (Regression).
@pytest.mark.parametrize(
    "frage",
    [
        "Gab es im August 2024 über 20.000 Beschäftigte in Wien?",
        "Gab es im August 2024 unter 40.000 Beschäftigte in Wien?",
        "Gab es im August 2024 über 10.000 Beschäftigte in Wien?",
    ],
)
def test_menge_mit_tausenderpunkt_ist_kein_alter(gerechnet: Verbindung, frage: str) -> None:
    daten = antwort_frage(gerechnet, frage)
    assert "Alter" not in daten["text"].split("Am ")[0]
    assert [z["wert"] for z in daten["zahlen"]] == [
        antwort_frage(gerechnet, "Beschäftigte in Wien im August 2024")["zahlen"][0]["wert"]
    ]


def test_prozent_mit_komma_ist_kein_alter() -> None:
    assert _alter_lesen("Anteil über 20,5 Prozent im August 2024") is None


# Fix-Liste !227, Punkt 2: Ohne Monat fiel „unter 25“ still weg, es kam der Gesamtbestand.
@pytest.mark.parametrize("frage", ["Beschäftigte unter 25", "Beschäftigte unter 25?"])
def test_alter_ohne_monat_bleibt(gerechnet: Verbindung, frage: str) -> None:
    daten = antwort_frage(gerechnet, frage)
    letzter = max(s["monat"] for s in daten["stand"])
    assert "Alter unter 25 Jahre" in daten["text"]
    assert [z["wert"] for z in daten["zahlen"]] == [_im_alter(gerechnet, str(letzter), 0, 24)]


# Fix-Liste !227, Punkt 3: Bindestrich und „oder älter“ ergaben genau ein Alter.
@pytest.mark.parametrize(
    ("frage", "von", "bis", "wort"),
    [
        ("Über-50-Jährige im August 2024", 51, 130, "Alter 51 Jahre und älter"),
        ("Unter-25-Jährige im August 2024", 0, 24, "Alter unter 25 Jahre"),
        ("Beschäftigte, 30 Jahre alt oder älter, im August 2024", 30, 130, "Alter ab 30 Jahre"),
        ("Beschäftigte 50 Jahre und älter im August 2024", 50, 130, "Alter ab 50 Jahre"),
    ],
)
def test_alter_mit_bindestrich_und_oder_aelter(
    gerechnet: Verbindung, frage: str, von: int, bis: int, wort: str
) -> None:
    daten = antwort_frage(gerechnet, frage)
    assert wort in daten["text"]
    assert [z["wert"] for z in daten["zahlen"]] == [_im_alter(gerechnet, "2024-08", von, bis)]


# Fix-Liste !227, Punkt 3: Dauer ist kein Alter, Grenzen unter 14 sind keine Altersgrenzen.
@pytest.mark.parametrize(
    ("frage", "wort"),
    [
        ("Beschäftigte ab 2 Jahren Dauer im August 2024", "Wie lange"),
        ("Beschäftigte bis 25 Jahre Betriebszugehörigkeit im August 2024", "Wie lange"),
        ("Wie viele sind über 2 Jahre dabei im August 2024?", "Wie lange"),
        ("Beschäftigte unter 10 in Wien im August 2024", "Altersangabe"),
    ],
)
def test_dauer_und_kleine_grenzen_sind_kein_alter(gerechnet: Verbindung, frage: str, wort: str) -> None:
    daten = antwort_frage(gerechnet, frage)
    assert daten["zahlen"] == [] and wort in daten["text"]


# Fix-Liste !227, Punkt 4: Der Stamm „alter“ machte „Altersheim“ zu einem bekannten Wort.
def test_altersheim_ist_kein_alter(gerechnet: Verbindung) -> None:
    daten = antwort_frage(gerechnet, "Beschäftigte in Altersheimen im August 2024")
    assert daten["zahlen"] == []


# Fix-Liste !227, Punkt 5: Eine Altersangabe ohne eindeutigen Treffer gibt die Absage, nie den Gesamtbestand.
@pytest.mark.parametrize(
    "frage",
    [
        "Beschäftigte ab 50 im August 2024",
        "Beschäftigte bis 25 im August 2024",
        "Beschäftigte zwischen 25 und 34 im August 2024",
        "Beschäftigte 50+ im August 2024",
        "Vergleich unter 25 und über 50 im August 2024",
        "Frauen über 50 nach Bundesland im August 2024",
        "Beschäftigte nach Altersstufen im August 2024",
        "Beschäftigte nach Altersklassen im August 2024",
        "Wie viele ältere Beschäftigte gab es im August 2024?",
    ],
)
def test_auffangregel_alter(gerechnet: Verbindung, frage: str) -> None:
    daten = antwort_frage(gerechnet, frage)
    assert daten["zahlen"] == [] and daten["text"] == ALTER_UNKLAR


# Gegenfall zur Auffangregel: Daten, Mengen und Prozent bleiben.
@pytest.mark.parametrize(
    "frage",
    [
        "Beschäftigte von August 2024 bis 12/2024",
        "Beschäftigte bis 31. Dezember 2024",
        "Wie viele Beschäftigte ab 01.09.2024?",
        "Gab es im August 2024 über 50 Beschäftigte in Wien?",
    ],
)
def test_auffangregel_laesst_daten_und_mengen(frage: str) -> None:
    assert nicht_auswertbar(frage) is None


# Fix-Liste !227, Punkt 6: Fluktuation nach Altersgruppe gab still die Tabelle je Branche.
def test_fluktuation_nach_altersgruppe_sagt_ab(gerechnet: Verbindung) -> None:
    daten = antwort_frage(gerechnet, "Fluktuation nach Altersgruppe im Oktober 2024")
    assert daten["zahlen"] == [] and "oder Alter" in daten["text"]


# Fix-Liste !227, Punkt 7: „Altersgruppen im Monat“ bekam „Das kann StatAgent nicht beantworten“ vor dem Angebot „Alter“.
@pytest.mark.parametrize(
    "frage",
    ["Altersgruppen im August 2024", "Altersverteilung im August 2024", "Nach Altersgruppe im August 2024"],
)
def test_altersgruppen_ohne_bestandswort(gerechnet: Verbindung, frage: str) -> None:
    daten = antwort_frage(gerechnet, frage)
    assert daten["zahlen"] and "je Alter" in daten["text"]


# Fängt: Der Jahrgang ist kein Merkmal der Daten; die Frage gab den Gesamtbestand ohne Hinweis (Prüfung !169).
@pytest.mark.parametrize(
    "frage", ["Beschäftigte Jahrgang 1990 im September 2024", "Geburtsjahr 1990 im September 2024"]
)
def test_jahrgang_nicht_ausgewertet(gerechnet: Verbindung, frage: str) -> None:
    daten = antwort_frage(gerechnet, frage)
    assert daten["zahlen"] == [] and "Geburtsjahrgänge" in daten["text"]


# Fängt: Eine Menge wird als Jahr gelesen, die Frage bekommt eine Rückfrage statt der Zahl (Prüfung !169).
def test_menge_ist_kein_jahr(gerechnet: Verbindung) -> None:
    soll = _bestand(gerechnet, "2024-08", "region")[("9",)]
    daten = antwort_frage(gerechnet, "Gab es im August 2024 über 2000 Beschäftigte in Wien?")
    assert [z["wert"] for z in daten["zahlen"]] == [soll]
