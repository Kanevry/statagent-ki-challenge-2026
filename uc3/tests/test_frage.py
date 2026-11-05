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
    als_ucantwort,
    als_webantwort,
    antwort_frage,
    fragetyp,
    jahr_ohne_monat,
    monate_lesen,
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
    assert len(daten["zahlen"]) == len(erwartet)
    assert (
        sum(z["wert"] for z in daten["zahlen"])
        == sum(erwartet.values())
        == _bestand(gerechnet, "2024-08")[()]
    )
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


# Fängt: Zu- oder Abgänge falsch zugeordnet, Bezugsbestand nicht der veröffentlichte, oder eine Rate trotz
# Bestand 0.
@pytest.mark.parametrize("monat", ["2024-08", "2024-09"])
def test_fluktuation_gleich_gegenrechnung(gerechnet: Verbindung, monat: str) -> None:
    frage = FLUKTUATION.replace("September 2024", "August 2024") if monat == "2024-08" else FLUKTUATION
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
@pytest.mark.parametrize("frage", ["Beschäftigte 2025", "Fluktuation 2025", "Wie viele Frauen?"])
def test_rueckfrage_statt_zahl(gerechnet: Verbindung, frage: str) -> None:
    daten = antwort_frage(gerechnet, frage)
    assert daten["rueckfrage"] is True and daten["typ"] == "rueckfrage"
    assert daten["zahlen"] == [] and daten["belege"] == [] and daten["text"].rstrip().endswith(("?", "“."))
    if "2025" in frage:
        assert "Dezember 2025" in daten["text"] and "Zeitreihe" in daten["text"]


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
        "1.234 fortgeschriebene" in h and "Zu- und Abgänge dieses Teils fehlen" in h
        for h in fluktuation["hinweise"]
    )
    reihe = antwort_frage(gerechnet, ZEITREIHE)
    assert any(h.startswith("September 2024 enthält 1.234 fortgeschriebene") for h in reihe["hinweise"])
    assert not any("August 2024 enthält" in h for h in reihe["hinweise"])


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
