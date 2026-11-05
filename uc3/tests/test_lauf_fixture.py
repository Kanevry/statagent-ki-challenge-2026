"""Tests auf der Fixture-Lieferung (Wegwerf-PostgreSQL, läuft auch in der CI ohne Startpaket-Daten).

Erwartete Werte stehen handgerechnet in fixtures/erwartet.json. Fallen der Lieferung 2024-08:
Volldublette (1005), zwei Abschnitte (1006), Ende vor/am Stichtag (1004/1003), leeres OENACE und
BUNDESLAND (1007), ÖNACE-2003-Code DK (1008) und D (1009), Geburtsmonat 13 (1010), Geburtsjahr 1871
(1011), Person mit zwei VVH (5001: 1001 und 1013), freier Dienstvertrag (1007, 1012).
2024-10 hat BEGINN und ENDE vertauscht (Spaltentausch).
"""

from __future__ import annotations

import json
from pathlib import Path

import psycopg
import pytest

from statagent.db import Verbindung, schema_einrichten
from statagent.ergebnis import monatswerte

ERWARTET = json.loads((Path(__file__).parent / "fixtures" / "erwartet.json").read_text(encoding="utf-8"))
VARIABLE = "Beschaeftigungsverhaeltnisse"


def _zellen(conn: Verbindung, lieferung: str) -> set[tuple[str, str, str, str, int, int]]:
    conn.commit()
    return {
        (z["region"], z["oenace"], z["geschlecht"], z["qualifikation"], z["alter"], z["wert"])  # type: ignore[misc]
        for z in monatswerte(conn, lieferung)
        if z["zeitraum_art"] == "Stichtag" and z["variable"] == VARIABLE and z["wert"] != 0
    }


def _soll_zellen(lieferung: str) -> set[tuple[str, str, str, str, int, int]]:
    return {
        (z["region"], z["oenace"], z["geschlecht"], z["qualifikation"], z["alter"], z["wert"])
        for z in ERWARTET[lieferung]["zellen"]
    }


def _zaehle(conn: Verbindung, abfrage: str) -> int:
    conn.commit()
    zeile = conn.execute(abfrage.encode()).fetchone()
    assert zeile is not None
    return int(str(zeile["n"]))


# --- ohne lauf.py -----------------------------------------------------------------------------------


def test_fixture_lieferungen_sind_geladen(conn: Verbindung) -> None:
    # Fängt: COPY lädt leere Felder als '' statt NULL oder verliert Zeilen (Dubletten, Kopfzeile).
    zeilen = {
        z["lieferung"]: z["n"]
        for z in conn.execute("SELECT lieferung, count(*) AS n FROM roh.lieferung GROUP BY 1").fetchall()
    }
    assert zeilen == {"2024-08": 16, "2024-09": 5, "2024-10": 9, "2024-11": 8}
    leer = _zaehle(conn, "SELECT count(*) AS n FROM roh.lieferung WHERE oenace = '' OR ende = ''")
    assert leer == 0


def test_schema_zweimal_einrichten_verliert_nichts(conn: Verbindung) -> None:
    # Fängt: nicht idempotente DDL/Seeds (Doppel-Seeds, DROP, fehlendes ON CONFLICT) bei erneutem Einrichten.
    vorher = {
        t: _zaehle(conn, f"SELECT count(*) AS n FROM {t}")
        for t in ("meta.regel", "stat.quellzuordnung", "stat.klass_oenace", "roh.lieferung")
    }
    schema_einrichten(conn)
    schema_einrichten(conn)
    nachher = {t: _zaehle(conn, f"SELECT count(*) AS n FROM {t}") for t in vorher}
    assert nachher == vorher
    assert vorher["meta.regel"] >= 13  # Regelsatz v1: mindestens die 13 Einlese-, Zuordnungs- und Zählregeln
    assert vorher["roh.lieferung"] == 38


def _lauf_zeile(conn: Verbindung) -> int:
    zeile = conn.execute(
        "INSERT INTO meta.lauf (lieferung, regelsatz, status) VALUES ('2024-08', 'v1', 'fertig') RETURNING id"
    ).fetchone()
    assert zeile is not None
    return int(str(zeile["id"]))


def _stat_zeile(conn: Verbindung, lauf_id: int, status: str) -> None:
    conn.execute(
        """
        INSERT INTO stat.stat_beschaeftigte
          (zeitraum_art, zeitraum_von, zeitraum_bis, region, oenace, oenace_version, geschlecht,
           qualifikation, alter, variable, wert, status, stand, regelsatz, regelstand, lauf_id)
        VALUES ('Stichtag', '2024-08-31', '2024-08-31', '9', 'C', '2008', 'M', 'ArbeiterDV', 44,
                'Beschaeftigungsverhaeltnisse', 1, %s, 'Lieferung 2024-08', 'v1', 'testhash', %s)
        """,
        (status, lauf_id),
    )


@pytest.mark.parametrize(
    "anweisung", ["UPDATE stat.stat_beschaeftigte SET wert = 2", "DELETE FROM stat.stat_beschaeftigte"]
)
def test_trigger_schuetzt_endgueltige_zeile(conn: Verbindung, anweisung: str) -> None:
    # Fängt: ein Trigger, der Veröffentlichtes (status endgueltig) überschreiben oder löschen lässt.
    _stat_zeile(conn, _lauf_zeile(conn), "endgueltig")
    conn.commit()
    with pytest.raises(psycopg.errors.RaiseException, match="unveränderlich"):
        conn.execute(anweisung.encode())
    conn.rollback()
    assert _zaehle(conn, "SELECT sum(wert) AS n FROM stat.stat_beschaeftigte") == 1


def test_trigger_laesst_vorlaeufige_zeile_aendern(conn: Verbindung) -> None:
    # Fängt: ein Trigger, der zu viel sperrt und vorläufige Ergebnisse unveränderlich macht.
    _stat_zeile(conn, _lauf_zeile(conn), "vorlaeufig")
    conn.execute("UPDATE stat.stat_beschaeftigte SET wert = 2")
    assert _zaehle(conn, "SELECT sum(wert) AS n FROM stat.stat_beschaeftigte") == 2


# --- braucht statagent.regeln ----------------------------------------------------------------------

UNGUELTIGE_NAMEN = ["Team", "Team UC3", "Admin Admin", "KI Agent", "Bernhard", "A\nCo-authored-by: x"]


@pytest.mark.parametrize("name", UNGUELTIGE_NAMEN)
def test_freigabe_lehnt_ungueltigen_namen_ab(conn: Verbindung, name: str) -> None:
    # Fängt: Freigabe durch Sammelnamen, Einwort-Namen oder Trailer-Injektion per Zeilenumbruch.
    regeln = pytest.importorskip("statagent.regeln")
    with pytest.raises(regeln.NameUngueltig):
        regeln.regeln_freigeben(conn, regelsatz="v1", name=name)
    conn.rollback()
    assert _zaehle(conn, "SELECT count(*) AS n FROM meta.regel WHERE freigegeben_von IS NOT NULL") == 0


# --- braucht statagent.lauf ------------------------------------------------------------------------


@pytest.mark.parametrize("lieferung", ["2024-08", "2024-09", "2024-10", "2024-11"])
def test_lauf_zaehlt_und_rechnet_ab(conn: Verbindung, lieferung: str) -> None:
    # Fängt: falsche Stichtagslogik, Dublette doppelt gezählt, Abschnittswahl, UNB/'0', DK->C, Monat 13,
    # Alter > 100, nicht vertauschte Spalten (2024-10), zwei aktive Abschnitte, Alter 80 plausibel, ungültiges ENDE
    # inkl. 'today' (2024-11, sonst nicht deterministisch), Abrechnung gelesen != gezählt+nicht+ausgeschlossen.
    lauf = pytest.importorskip("statagent.lauf")
    # Lieferungen laufen in zeitlicher Reihenfolge (Fachbeschreibung § 2a): Vormonate zuerst rechnen.
    for vorher in ("2024-08", "2024-09", "2024-10"):
        if vorher < lieferung:
            lauf.lauf_ausfuehren(conn, vorher, regelsatz="v1", gestartet_von=None)
    erg = lauf.lauf_ausfuehren(conn, lieferung, regelsatz="v1", gestartet_von=None)
    soll = ERWARTET[lieferung]
    assert erg.status == "fertig"
    assert erg.ergebnis_status == "vorlaeufig"
    assert (erg.gelesen, erg.gezaehlt, erg.nicht_gezaehlt, erg.ausgeschlossen) == (
        soll["gelesen"],
        soll["gezaehlt"],
        soll["nicht_gezaehlt"],
        soll["ausgeschlossen"],
    )
    assert erg.gelesen == erg.gezaehlt + erg.nicht_gezaehlt + erg.ausgeschlossen
    assert _zellen(conn, lieferung) == _soll_zellen(lieferung)


def test_lauf_ausser_reihenfolge_wird_abgelehnt(conn: Verbindung) -> None:
    # Fängt: Lauf eines Monats, dessen Vormonat noch nicht gerechnet ist (Reihenfolge-Pflicht § 2a).
    lauf = pytest.importorskip("statagent.lauf")
    with pytest.raises(lauf.LaufFehler, match="zeitlicher Reihenfolge"):
        lauf.lauf_ausfuehren(conn, "2024-09", regelsatz="v1", gestartet_von=None)


def test_zweiter_lauf_ist_unveraendert_mit_gleichem_hash(conn: Verbindung) -> None:
    # Fängt: nicht deterministischer Lauf (Hash ändert sich) oder erneutes Schreiben bei gleichem Regelstand.
    lauf = pytest.importorskip("statagent.lauf")
    erster = lauf.lauf_ausfuehren(conn, "2024-08", regelsatz="v1", gestartet_von=None)
    zweiter = lauf.lauf_ausfuehren(conn, "2024-08", regelsatz="v1", gestartet_von=None)
    assert zweiter.status == "unveraendert"
    assert zweiter.ergebnis_hash == erster.ergebnis_hash
    assert _zellen(conn, "2024-08") == _soll_zellen("2024-08")


def test_nach_freigabe_ist_lauf_endgueltig_und_zeilen_sind_geschuetzt(conn: Verbindung) -> None:
    # Fängt: Veröffentlichung ohne Regelfreigabe, Ergebnis bleibt nach Veröffentlichung vorläufig,
    # oder endgültige Zeilen sind nicht durch den Trigger geschützt.
    lauf = pytest.importorskip("statagent.lauf")
    regeln = pytest.importorskip("statagent.regeln")
    vorlaeufig = lauf.lauf_ausfuehren(conn, "2024-08", regelsatz="v1", gestartet_von=None)
    assert vorlaeufig.ergebnis_status == "vorlaeufig"
    with pytest.raises(lauf.LaufFehler, match="ohne Freigabe"):
        lauf.veroeffentlichen(conn, "2024-08", "v1", "Erika Musterfrau")
    conn.rollback()
    offen = conn.execute(
        b"SELECT count(*) AS n FROM meta.regel WHERE regelsatz = 'v1' AND aktiv AND freigegeben_von IS NULL"
    ).fetchone()
    assert offen is not None
    assert regeln.regeln_freigeben(conn, regelsatz="v1", name="Erika Musterfrau") == offen["n"]
    conn.commit()
    assert lauf.veroeffentlichen(conn, "2024-08", "v1", "Erika Musterfrau") > 0
    conn.commit()
    endgueltig = lauf.lauf_ausfuehren(conn, "2024-08", regelsatz="v1", gestartet_von=None)
    assert endgueltig.ergebnis_status == "endgueltig"
    assert endgueltig.status == "unveraendert"
    assert endgueltig.gezaehlt == 12
    conn.commit()
    with pytest.raises(psycopg.errors.RaiseException, match="unveränderlich"):
        conn.execute(b"UPDATE stat.stat_beschaeftigte SET wert = wert + 1 WHERE status = 'endgueltig'")
    conn.rollback()


ANTI_JOINS = {
    "region": "LEFT JOIN stat.klass_region k ON k.code = s.region WHERE k.code IS NULL",
    "oenace": "LEFT JOIN stat.klass_oenace k ON k.code = s.oenace AND k.version = s.oenace_version "
    "WHERE k.code IS NULL",
    "geschlecht": "LEFT JOIN stat.klass_geschlecht k ON k.code = s.geschlecht WHERE k.code IS NULL",
    "qualifikation": "LEFT JOIN stat.klass_qualifikation k ON k.code = s.qualifikation WHERE k.code IS NULL",
    "alter": 'LEFT JOIN stat.klass_alter k ON k.code = s."alter" WHERE k.code IS NULL',
}


@pytest.mark.parametrize("merkmal", list(ANTI_JOINS))
def test_alle_zellcodes_stehen_in_der_klassifikation(conn: Verbindung, merkmal: str) -> None:
    # Fängt: Zelle mit Code ohne Klassifikationszeile (z. B. DK/UNB/'0'/-1 nicht zugeordnet) -> Join-Verlust.
    lauf = pytest.importorskip("statagent.lauf")
    for lieferung in ("2024-08", "2024-09", "2024-10"):
        lauf.lauf_ausfuehren(conn, lieferung, regelsatz="v1", gestartet_von=None)
    assert _zaehle(conn, "SELECT count(*) AS n FROM stat.stat_beschaeftigte") > 0
    assert _zaehle(conn, f"SELECT count(*) AS n FROM stat.stat_beschaeftigte s {ANTI_JOINS[merkmal]}") == 0
