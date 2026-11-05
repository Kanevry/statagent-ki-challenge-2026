"""Sonderauswertung Personentage (Auftrag 3): Datenstand je Tag, Tage je Person, Freigabe der Lieferung."""

from __future__ import annotations

import dataclasses
import json
from pathlib import Path

import pytest
from conftest import ROH_SPALTEN
from plattform.freigabe import GitFehler
from test_agenten_freigabe import NAME, git
from test_regeln_freigabe import _repo

from statagent.db import Verbindung
from statagent.lauf import lauf_ausfuehren
from statagent.regeln import NameUngueltig, regeln_freigeben
from statagent.sonderauswertung import (
    LieferungBereitsFreigegeben,
    NichtFreigegeben,
    auswertung_regel,
    ministerium_schreiben,
    personentage,
)

PARAMETER = {
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


def _auswertungsregel(conn: Verbindung) -> None:
    for monat in ("2024-08", "2024-09", "2024-10", "2024-11"):
        lauf_ausfuehren(conn, monat, "v1")
    conn.execute(
        b"""INSERT INTO meta.regel (regelsatz, name, typ, art, reihenfolge, parameter, beschreibung, begruendung,
              grundlage) VALUES ('ministerium', 'A3_ministerium_personentage', 'zaehl', 'personentage', 10, %s,
              'Test', 'Test', 'Auftrag 3')""",
        (json.dumps(PARAMETER),),
    )


def test_lieferung_braucht_freigegebene_definition_und_namen(conn: Verbindung, tmp_path: Path) -> None:
    # Fängt: Auswertung startet ohne freigegebene Definition (Regel 6d) oder mit Platzhalter-Namen (Regel 7).
    _auswertungsregel(conn)
    with pytest.raises(NichtFreigegeben):
        ministerium_schreiben(conn, "2024-11", "Lena Gruber", ziel_dir=tmp_path)
    regeln_freigeben(conn, "ministerium", "Lena Gruber")
    with pytest.raises(NameUngueltig):
        ministerium_schreiben(conn, "2024-11", "Team", ziel_dir=tmp_path)


def test_personentage_november(conn: Verbindung, tmp_path: Path) -> None:
    # Fängt: falscher Datenstand (jüngste Lieferung), Angestellte/andere Abschnitte mitgezählt, ein ungültiges
    # ENDE als beendet gewertet, Ende vor dem Zeitraum gezählt, Sortierung oder CSV-Kopf falsch.
    _auswertungsregel(conn)
    regeln_freigeben(conn, "ministerium", "Lena Gruber")
    datei, auswertung = ministerium_schreiben(conn, "2024-11", "Lena Gruber", ziel_dir=tmp_path)
    assert auswertung.datenstand == {"2024-11": "2024-11"}
    assert datei.read_text(encoding="utf-8").splitlines() == [
        "PERSON_ID;GESCHLECHT;GEBURTSJAHR;TAGE",
        "7001;M;1970;30",
        "7002;W;1944;30",
        "7004;M;1985;30",
    ]
    ausgabe = conn.execute(
        b"SELECT zeilen, freigegeben_von FROM meta.ausgabe WHERE art = 'ministerium' AND berichtsmonat = '2024-11'"
    ).fetchone()
    assert ausgabe is not None and (ausgabe["zeilen"], ausgabe["freigegeben_von"]) == (3, "Lena Gruber")


def _ausgaben(conn: Verbindung) -> list[tuple[str, int | None]]:
    return [
        (str(z["datei"]), z["protokoll_id"])
        for z in conn.execute(
            b"SELECT datei, protokoll_id FROM meta.ausgabe WHERE art = 'ministerium'"
        ).fetchall()
    ]


def _lieferungs_protokoll(conn: Verbindung) -> list[tuple[int, str, str | None]]:
    return [
        (int(str(z["id"])), str(z["status"]), z["commit_hash"])
        for z in conn.execute(
            b"SELECT id, status, commit_hash FROM meta.protokoll WHERE vorschlag_typ = 'lieferung' ORDER BY id"
        ).fetchall()
    ]


def test_freigabe_committet_genau_die_csv_mit_trailer_und_protokoll(conn: Verbindung, tmp_path: Path) -> None:
    # Fängt: Lieferung nur in meta.ausgabe festgehalten, ohne meta.protokoll/meta.freigabe und ohne Commit mit
    # Trailer (Review !13 Punkt 3, #71 AC2, Regel 7), oder ein Commit mit fremden Dateien.
    repo = _repo(tmp_path / "repo")
    (repo / "fremd.txt").write_text("nicht Teil der Lieferung\n", encoding="utf-8")
    git(repo, "add", "fremd.txt")
    _auswertungsregel(conn)
    regeln_freigeben(conn, "ministerium", NAME)
    datei, _ = ministerium_schreiben(conn, "2024-11", NAME, ziel_dir=repo / "abgabe", repo_pfad=repo)
    assert git(repo, "log", "-1", "--format=%(trailers:key=Freigegeben-von,valueonly)") == NAME
    assert git(repo, "show", "--name-only", "--format=", "HEAD").splitlines() == [
        "abgabe/ministerium_2024-11.csv"
    ]
    assert (
        git(repo, "show", "HEAD:abgabe/ministerium_2024-11.csv") == datei.read_text(encoding="utf-8").strip()
    )
    [(protokoll_id, status, commit)] = _lieferungs_protokoll(conn)
    assert (status, commit) == ("freigegeben", git(repo, "rev-parse", "HEAD"))
    f = conn.execute(
        b"SELECT name, objekt_typ, objekt_ref FROM meta.freigabe WHERE protokoll_id = %s", (protokoll_id,)
    ).fetchone()
    assert f is not None and (f["name"], f["objekt_typ"], f["objekt_ref"]) == (
        NAME,
        "datei",
        "abgabe/ministerium_2024-11.csv",
    )
    assert _ausgaben(conn) == [("abgabe/ministerium_2024-11.csv", protokoll_id)]


def test_zweite_freigabe_desselben_monats_wird_abgewiesen(conn: Verbindung, tmp_path: Path) -> None:
    # Fängt: ein Berichtsmonat wird zweimal freigegeben bzw. eine abweichende Fassung überschreibt die
    # freigegebene Datei ohne neuen Auftrag.
    repo = _repo(tmp_path / "repo")
    _auswertungsregel(conn)
    regeln_freigeben(conn, "ministerium", NAME)
    datei, _ = ministerium_schreiben(conn, "2024-11", NAME, ziel_dir=repo / "abgabe", repo_pfad=repo)
    kopf = git(repo, "rev-parse", "HEAD")
    with pytest.raises(LieferungBereitsFreigegeben, match=f"bereits freigegeben von {NAME} am"):
        ministerium_schreiben(conn, "2024-11", NAME, ziel_dir=repo / "abgabe", repo_pfad=repo)
    conn.execute(b"UPDATE meta.ausgabe SET sha256 = 'anders' WHERE berichtsmonat = '2024-11'")
    with pytest.raises(LieferungBereitsFreigegeben, match="neuen Auftrag"):
        ministerium_schreiben(conn, "2024-11", NAME, ziel_dir=repo / "abgabe", repo_pfad=repo)
    assert git(repo, "rev-parse", "HEAD") == kopf
    assert git(repo, "status", "--porcelain") == ""  # Datei unverändert
    assert len(_ausgaben(conn)) == 1 and len(_lieferungs_protokoll(conn)) == 1
    assert datei.is_file()


def test_gescheitertes_git_lehnt_ab_und_schreibt_keine_ausgabe(conn: Verbindung, tmp_path: Path) -> None:
    # Fängt: Git scheitert, aber meta.ausgabe hält die Lieferung als freigegeben fest oder der Protokolleintrag
    # bleibt offen.
    repo = _repo(tmp_path / "repo")
    hook = repo / ".git" / "keine-hooks" / "pre-commit"
    hook.parent.mkdir(parents=True, exist_ok=True)
    hook.write_text("#!/bin/sh\necho abgelehnt vom Hook >&2\nexit 1\n", encoding="utf-8")
    hook.chmod(0o755)
    kopf = git(repo, "rev-parse", "HEAD")
    _auswertungsregel(conn)
    regeln_freigeben(conn, "ministerium", NAME)
    with pytest.raises(GitFehler):
        ministerium_schreiben(conn, "2024-11", NAME, ziel_dir=repo / "abgabe", repo_pfad=repo)
    [(protokoll_id, status, commit)] = _lieferungs_protokoll(conn)
    assert (status, commit) == ("abgelehnt", None)
    f = conn.execute(
        b"SELECT entscheidung FROM meta.freigabe WHERE protokoll_id = %s", (protokoll_id,)
    ).fetchall()
    assert [z["entscheidung"] for z in f] == ["nein"]
    assert _ausgaben(conn) == []
    assert git(repo, "rev-parse", "HEAD") == kopf
    assert not (repo / "abgabe" / "ministerium_2024-11.csv").exists()


# Grenzfälle (Review !13 Punkt 9): Schwelle − 1 / Schwelle (im Echtbetrieb 199/200, hier mindesttage = 30 auf
# einen Monat), überlappende Verhältnisse derselben Person und ein ÖNACE-2003-Altcode, den die Quellzuordnung
# in Abschnitt C übernimmt. Personen-IDs sind erfunden.
GRENZFAELLE = [
    ("1201", "5201", "2024-11-02", None, "C"),  # 29 Tage: unter der Schwelle
    ("1202", "5202", "2024-11-01", None, "C"),  # 30 Tage: genau die Schwelle
    ("1203", "5203", "2024-11-01", "2024-11-20", "C"),  # zwei Verhältnisse, überlappend 11.–20.11.:
    ("1204", "5203", "2024-11-11", "2024-11-30", "C"),  # zusammen 30 Tage, nicht 40
    ("1205", "5204", "2024-11-01", None, "DA"),  # Altcode, über Q01 in C
]


def test_grenzfaelle_schwelle_ueberlappung_und_altcodes(conn: Verbindung) -> None:
    # Fängt: Schwelle mit > statt >= (Schwelle − 1 zählt oder Schwelle fehlt), überlappende Verhältnisse doppelt
    # gezählt, Altcodes ohne Regelparameter in Abschnitt C (32.667 statt 32.639).
    with conn.transaction():
        for vvh, person, beginn, ende, oenace in GRENZFAELLE:
            conn.execute(
                f"""INSERT INTO roh.lieferung ({ROH_SPALTEN})
                    VALUES ('2024-11', %s, %s, '1980-05-12', 'W', %s, %s, 'ArbeiterDV', %s, '9')""".encode(),
                (vvh, person, beginn, ende, oenace),
            )
    _auswertungsregel(conn)
    regeln_freigeben(conn, "ministerium", NAME)
    regel = auswertung_regel(conn, "ministerium")

    def tage(altcodes: list[str]) -> dict[int, int]:
        neu = dataclasses.replace(regel, parameter={**regel.parameter, "altcodes_als_abschnitt": altcodes})
        return {z[0]: z[3] for z in personentage(conn, neu, "2024-11").zeilen if 5200 <= z[0] < 5300}

    assert tage([]) == {5202: 30, 5203: 30}
    assert tage(["DA", "DB"]) == {5202: 30, 5203: 30, 5204: 30}


def test_geburtsmonat_13_ist_unplausibles_geburtsjahr(conn: Verbindung) -> None:
    # Fängt: Datum mit Monat 13 liefert in GEBURTSJAHR ein Jahr; Auftrag 3 verlangt für unplausible Geburtsdaten
    # „Unbekannt“ (der Ersatztag 1. Juli gilt nur für das Alter in der Statistik, Review 4f / Lead 58).
    with conn.transaction():
        conn.execute(
            f"""INSERT INTO roh.lieferung ({ROH_SPALTEN})
                VALUES ('2024-11', '5301', '5301', '1975-13-04', 'M', '2020-01-01', NULL, 'ArbeiterDV', 'C', '9')"""
        )
    _auswertungsregel(conn)
    regeln_freigeben(conn, "ministerium", NAME)
    zeilen = {z[0]: z for z in personentage(conn, auswertung_regel(conn, "ministerium"), "2024-11").zeilen}
    assert zeilen[5301][2] == "Unbekannt"
    assert zeilen[7001][2] == "1970"
