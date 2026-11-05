"""Qualitätsbericht aus der Fixture-Datenbank (Läufe 2024-08 und 2024-09)."""

from __future__ import annotations

from pathlib import Path

import pytest

from statagent.berichte.pruefe_abgabe import bericht_maengel, einstufungen_aus_bericht
from statagent.berichte.qualitaetsbericht import (
    ABSCHNITTE,
    GUELTIGE_EINSTUFUNGEN,
    BerichtFehler,
    _ueberblick,
    bericht_daten,
    bericht_erzeugen,
    bericht_schreiben,
    zahl,
)
from statagent.db import Verbindung
from statagent.lauf import lauf_ausfuehren, veroeffentlichen
from statagent.regeln import regeln_freigeben

NAME = "Lena Gruber"


def _abschnitt(text: str, nr: int) -> str:
    """Text des Abschnitts `nr` (1–5) ohne die folgenden Abschnitte."""
    anfang = text.index(ABSCHNITTE[nr - 1])
    ende = text.index(ABSCHNITTE[nr]) if nr < len(ABSCHNITTE) else len(text)
    return text[anfang:ende]


def _laeufe(conn: Verbindung) -> int:
    lauf_ausfuehren(conn, "2024-08", regelsatz="v1", gestartet_von=None)
    return lauf_ausfuehren(conn, "2024-09", regelsatz="v1", gestartet_von=None).lauf_id


def _lauf(conn: Verbindung, lauf_id: int) -> dict[str, object]:
    zeile = conn.execute("SELECT * FROM meta.lauf WHERE id = %s", (lauf_id,)).fetchone()
    assert zeile is not None
    return zeile


def test_bericht_folgt_vorlage_und_meta_lauf(conn: Verbindung) -> None:
    # Fängt: Abschnitte fehlen/vertauscht, Kennzahlen nicht aus meta.lauf, Abrechnung fehlt oder falsch.
    lauf = _lauf(conn, _laeufe(conn))
    text = bericht_erzeugen(conn, "2024-09")
    ueberschriften = [z for z in text.splitlines() if z.startswith("## ")]
    assert ueberschriften == list(ABSCHNITTE)
    assert text.startswith("# Qualitätsbericht – Berichtsmonat 2024-09\n")
    assert "freigegeben von: noch nicht freigegeben" in text
    assert "> **Status: vorläufig.** Die Zahlen für September 2024 sind vorläufig." in text
    assert "Die Regeln sind noch nicht mit Namen freigegeben." in text

    g, z, n, a = (int(str(lauf[k])) for k in ("gelesen", "gezaehlt", "nicht_gezaehlt", "ausgeschlossen"))
    assert f"| gelesene Sätze | {zahl(g)} |" in text
    assert f"| davon gezählt am Stichtag | {zahl(z)} |" in text
    assert f"| Beschäftigungsverhältnisse am Stichtag | {zahl(z)} |" in text
    assert (
        f"Abrechnung in Zahlen: {zahl(g)} gelesen = {zahl(z)} gezählt + {zahl(n)} nicht gezählt"
        f" + {zahl(a)} ausgeschlossen (geht auf)."
    ) in text
    assert "(Annahme A8)" in text
    assert "gegenüber 2024-08" in text
    assert f"Ergebnis-Hash `{lauf['ergebnis_hash']}`" in text
    assert bericht_maengel(text) == []


def test_bericht_ist_bytegleich_und_wird_geschrieben(conn: Verbindung, tmp_path: Path) -> None:
    # Fängt: Zeitstempel „jetzt“, unsortierte Abfragen oder Mengen-Iteration im Bericht.
    _laeufe(conn)
    pfad = bericht_schreiben(conn, "2024-09", ziel=tmp_path / "a" / "2024-09.md")
    assert pfad.read_bytes() == bericht_erzeugen(conn, "2024-09").encode("utf-8")
    assert bericht_erzeugen(conn, "2024-09") == bericht_erzeugen(conn, "2024-09")


def test_auffaelligkeit_mit_einstufung_beleg_und_anhalten(conn: Verbindung) -> None:
    # Fängt: Einstufungs-Code statt Vorlagentext, Beleg-SQL fehlt, angehaltene Prüfung nicht als Grund genannt.
    lauf_id = _laeufe(conn)
    regel = conn.execute(
        """INSERT INTO meta.regel (regelsatz, name, typ, art, reihenfolge, beschreibung, begruendung, grundlage)
           VALUES ('v1', 'P90_testpruefung', 'pruefung', 'test', 90, 'Testprüfung', 'Test', 'Test')
           RETURNING id"""
    ).fetchone()
    assert regel is not None
    for ebene, einstufung, anhalten in (("satz", "erklaert-datenproblem", False), ("aggregat", None, True)):
        conn.execute(
            """INSERT INTO meta.pruefung_treffer (lauf_id, regel_id, ebene, anzahl, einstufung, anhalten, beleg_sql)
               VALUES (%s, %s, %s, 3, %s, %s, 'SELECT vvh_id FROM roh.lieferung WHERE lieferung = ''2024-09''')""",
            (lauf_id, regel["id"], ebene, einstufung, anhalten),
        )
    text = bericht_erzeugen(conn, "2024-09")
    zeilen_p90 = [z for z in text.splitlines() if z.startswith("|") and "Testprüfung" in z]
    assert len(zeilen_p90) == 2
    assert "erklärt – Datenproblem" in zeilen_p90[0] and "nicht erklärbar" in zeilen_p90[1]
    assert set(einstufungen_aus_bericht(text)) <= GUELTIGE_EINSTUFUNGEN
    assert "</summary>" in text and "P90_testpruefung</summary>" in text
    assert "Deshalb ist der Monat angehalten (P90_testpruefung)." in text
    assert bericht_maengel(text) == []


def test_ohne_lauf_gibt_es_keinen_bericht(conn: Verbindung) -> None:
    # Fängt: ein Bericht aus leeren Kennzahlen, wenn der Monat nie gerechnet wurde.
    with pytest.raises(BerichtFehler):
        bericht_erzeugen(conn, "2024-09")


def test_veroeffentlichter_monat_zeigt_den_veroeffentlichenden_lauf(conn: Verbindung) -> None:
    # Fängt: nach einem Regelwechsel zeigt der Bericht eines veröffentlichten Monats in § 2 und § 4 Treffer und
    # Wirkung des neuen Regelstands und im Kopf „VORLÄUFIG“, obwohl § 1 die veröffentlichten Zahlen zeigt.
    erster = lauf_ausfuehren(conn, "2024-08", "v1")
    regeln_freigeben(conn, "v1", NAME)
    veroeffentlichen(conn, "2024-08", "v1", NAME)
    conn.execute(  # neuer Regelstand: ÖNACE 'D' wird wie 'C' zugeordnet (nicht freigegeben)
        b"""UPDATE stat.quellzuordnung SET code = 'C'
            WHERE regelsatz = 'v1' AND merkmal = 'oenace' AND version = '2008' AND geliefert = 'D'"""
    )
    zweiter = lauf_ausfuehren(conn, "2024-08", "v1")
    assert zweiter.ergebnis_status == "endgueltig" and zweiter.lauf_id != erster.lauf_id
    # Der neue Lauf sieht etwas anderes: eine Prüfung, die anhält, und eine andere Regelwirkung.
    regel = conn.execute(
        """INSERT INTO meta.regel (regelsatz, name, typ, art, reihenfolge, beschreibung, begruendung, grundlage)
           VALUES ('v1', 'P90_testpruefung', 'pruefung', 'test', 90, 'Testprüfung', 'Test', 'Test')
           RETURNING id"""
    ).fetchone()
    assert regel is not None
    conn.execute(
        """INSERT INTO meta.pruefung_treffer (lauf_id, regel_id, ebene, anzahl, einstufung, anhalten, beleg_sql)
           VALUES (%s, %s, 'aggregat', 7, NULL, TRUE, 'SELECT 1')""",
        (zweiter.lauf_id, regel["id"]),
    )
    wirkung = conn.execute(
        """UPDATE meta.regel_wirkung SET saetze = 987654
           WHERE lauf_id = %s AND regel_id = (SELECT min(regel_id) FROM meta.regel_wirkung WHERE lauf_id = %s)
           RETURNING regel_id""",
        (zweiter.lauf_id, zweiter.lauf_id),
    ).fetchall()
    assert len(wirkung) == 1

    text = bericht_erzeugen(conn, "2024-08")
    assert "VORLÄUFIG" not in text
    assert (
        "> **Status: endgültig.** Die Zahlen für August 2024 sind endgültig. Lena Gruber hat sie am " in text
    )
    assert f"| davon gezählt am Stichtag | {zahl(erster.gezaehlt)} |" in _abschnitt(text, 1)
    alte_treffer = conn.execute(
        "SELECT r.name FROM meta.pruefung_treffer t JOIN meta.regel r ON r.id = t.regel_id "
        "WHERE t.lauf_id = %s AND t.anzahl > 0",
        (erster.lauf_id,),
    ).fetchall()
    for t in alte_treffer:
        assert str(t["name"]) in _abschnitt(text, 2)
    assert "Testprüfung" not in _abschnitt(text, 2)
    assert zahl(987654) not in _abschnitt(text, 4)
    revision = _abschnitt(text, 5)
    assert f"veröffentlichenden Lauf {erster.lauf_id}" in revision
    assert "P90_testpruefung (Aggregat, 7 Sätze, hätte angehalten)" in revision
    assert "Umschichtung" in revision and "| 2024-08 | ÖNACE-Abschnitt | C |" in revision
    assert bericht_maengel(text) == []


def test_umschichtung_ist_revisionsbedarf(conn: Verbindung) -> None:
    # Fängt: § 5 liest nur „insgesamt“; C +10 / D −10 erscheint dann als „kein Revisionsbedarf“.
    lauf_id = _laeufe(conn)
    conn.execute(
        "UPDATE meta.revision SET aktuell = veroeffentlicht WHERE lauf_id = %s AND berichtsmonat = '2024-08'",
        (lauf_id,),
    )
    geaendert = conn.execute(
        """UPDATE meta.revision SET aktuell = veroeffentlicht + CASE schluessel WHEN 'C' THEN 10 ELSE -10 END
           WHERE lauf_id = %s AND berichtsmonat = '2024-08' AND gliederung = 'oenace' AND schluessel IN ('C', 'D')
           RETURNING schluessel""",
        (lauf_id,),
    ).fetchall()
    assert len(geaendert) == 2
    revision = _abschnitt(bericht_erzeugen(conn, "2024-09"), 5)
    assert "Kein Revisionsbedarf" not in revision
    assert "Umschichtung zwischen Ausprägungen, insgesamt unverändert" in revision
    zeilen = [z for z in revision.splitlines() if z.startswith("| 2024-08 | ÖNACE-Abschnitt |")]
    assert [z.split(" | ")[2] for z in zeilen] == ["C", "D"]
    assert zeilen[0].endswith("| +10 |") and zeilen[1].endswith("| -10 |")


def test_abrechnung_nennt_fortgeschriebene_verhaeltnisse(conn: Verbindung) -> None:
    # Fängt: mit Fortschreibung (E07) sagt die Prosa „gelesen = gezählt + …“ und die Tabelle trennt geliefert
    # gezählte und fortgeschriebene Verhältnisse nicht.
    lauf = dict(_lauf(conn, _laeufe(conn)))
    lauf["fortgeschrieben"], lauf["gezaehlt"] = 5, int(str(lauf["gezaehlt"])) + 5
    text = "\n".join(_ueberblick(conn, lauf, "2024-09", "v1"))
    z = int(str(lauf["gezaehlt"]))
    assert f"| davon geliefert gezählt | {zahl(z - 5)} |" in text
    assert "| davon fortgeschrieben aus der Vorlieferung (Regel E07, vorläufig) | 5 |" in text
    assert (
        "Abrechnung: gelesene Sätze + fortgeschriebene Verhältnisse = gezählte + nicht gezählte"
        " + ausgeschlossene Sätze."
    ) in text
    assert " + 5 fortgeschrieben = " in text and "(geht auf)" in text


def test_freigabe_kommt_vom_freigegebenen_lauf(conn: Verbindung) -> None:
    # Fängt: zweimal gerechnet mit gleichem Ergebnis, dann veröffentlicht. Die Zellen hängen am ersten Lauf, die
    # Freigabe am zweiten; der Bericht las Name und Zeitpunkt vom ersten und sagte „noch nicht freigegeben“.
    erster = lauf_ausfuehren(conn, "2024-08", "v1")
    zweiter = lauf_ausfuehren(conn, "2024-08", "v1")
    regeln_freigeben(conn, "v1", NAME)
    veroeffentlichen(conn, "2024-08", "v1", NAME)
    zellen = conn.execute(
        "SELECT min(lauf_id) AS id FROM stat.stat_beschaeftigte WHERE status = 'endgueltig'"
    ).fetchone()
    freigegeben = conn.execute(
        "SELECT id FROM meta.lauf WHERE lieferung = '2024-08' AND freigegeben_von IS NOT NULL"
    ).fetchall()
    assert zellen is not None and zellen["id"] == erster.lauf_id
    assert [z["id"] for z in freigegeben] == [zweiter.lauf_id]
    text = bericht_erzeugen(conn, "2024-08")
    assert "noch nicht freigegeben" not in text
    assert f"freigegeben von: {NAME} am " in text and f"{NAME} hat sie am " in text


def test_saetze_sind_einfach_und_struktur_passt_zum_markdown(conn: Verbindung) -> None:
    # Fängt: Regelcode statt Satz als Hauptaussage in § 2, Platzhalter ungefüllt, Gedankenstriche oder „·“ in
    # Sätzen, Annahmen fehlen im Bericht, JSON-Struktur und Markdown rechnen auseinander.
    _laeufe(conn)
    daten = bericht_daten(conn, "2024-09")
    text = bericht_erzeugen(conn, "2024-09")
    assert daten["auffaelligkeiten"], "Fixture ohne Prüftreffer"
    for a in daten["auffaelligkeiten"]:
        assert "{" not in a["satz"] and not a["satz"].startswith(a["regel"])
        assert f"| {a['satz']} ({a['regel']}) |" in text.replace("\\|", "|")
    for satz in [*daten["status_saetze"], *(a["satz"] for a in daten["auffaelligkeiten"])]:
        assert "—" not in satz and " – " not in satz and "·" not in satz
    assert "—" not in text and "·" not in text
    assert daten["kennzahlen"]["abrechnung_in_zahlen"] in text
    nrn = [a["nr"] for a in daten["annahmen"]]
    assert "F4" in nrn and "F9" not in nrn
    assert "- Annahme F4: " in _abschnitt(text, 4)
    assert "Begriffe: Ein Verhältnis ist ein Beschäftigungsverhältnis, nicht eine Person." in text
