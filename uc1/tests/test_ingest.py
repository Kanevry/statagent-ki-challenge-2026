"""Tests für uc1.ingest. Fixtures sind aus dem Korpus gekürzte SozDok-Dateien (je < 3 KB)."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from uc1 import ingest
from uc1.ingest import Dokument, Fehler, lies_eko, lies_sozdok

FIXTURES = Path(__file__).parent / "fixtures"
BPGG = FIXTURES / "Rechtstexte" / "BPGG=PARA=4=12=2015-01-13=2015-01-01.xml"
KAPUTTER_NAME = (
    FIXTURES
    / "Rechtstexte"
    / (
        "Verlaengerung_der_Bestimmungen_ueber_die_Abgabe_von_SARS-CoV-2-Antigentests_223_2022"
        "=PARA=1=511=2022-1.xml"
    )
)


def _dok(pfad: Path) -> Dokument:
    ergebnis = lies_sozdok(pfad, FIXTURES)
    assert isinstance(ergebnis, Dokument), ergebnis
    return ergebnis


def test_nur_nutzdaten_ohne_inhaltsvz_und_metadaten() -> None:
    """Fängt einen Parser, der inhaltsvz, aendprot, layoutdaten oder Metadaten-Verweise mit indiziert."""
    dok = _dok(BPGG)
    assert len(dok.abschnitte) == 1  # Datei < 8 KB: ein Abschnitt
    text = dok.abschnitte[0].text
    assert text.startswith("Anspruchsvoraussetzungen § 4. (1) Das Pflegegeld gebührt")
    for fremd in ("Inhaltsverzeichnis-Eintrag", "glueck", "BPGGEinstV", "Layout nicht indizieren"):
        assert fremd not in text
    assert dok.abschnitte[0].kontext == "BPGG § 4 Anspruchsvoraussetzungen"


def test_symbole_und_leerraum_sind_zitierfaehig() -> None:
    """Fängt NBSP, geschützten Bindestrich und bedingten Trennstrich, die ein Zitat als Teilstring
    scheitern ließen (§\\xa04, e card, Kranken anstalten), und Listensymbole, die am Wort kleben."""
    text = _dok(BPGG).abschnitte[0].text
    assert "\xa0" not in text and "  " not in text
    assert "§ 4." in text and "§ 8 des Bundesbehindertengesetzes" in text
    assert "e-card" in text and "Krankenanstalten" in text
    assert "1. eine Definition der Begriffe" in text
    assert "Stufe 1: für Personen" in text


def test_teilung_nach_absatz_mit_liste_am_vorangehenden(monkeypatch: pytest.MonkeyPatch) -> None:
    """Fängt eine Teilung großer Dateien, die Listen als eigene Abschnitte führt, die Reihenfolge
    verliert oder die Überschrift vergisst."""
    monkeypatch.setattr(ingest, "TEILUNGSGRENZE_BYTES", 100)
    abschnitte = _dok(BPGG).abschnitte
    assert [a.nr for a in abschnitte] == [0, 1, 2]
    assert abschnitte[0].text.startswith("Anspruchsvoraussetzungen § 4. (1)")
    assert abschnitte[1].text.startswith("(2) Anspruch auf Pflegegeld")
    assert "Stufe 1: für Personen" in abschnitte[1].text  # Liste hängt an Abs. 2
    assert abschnitte[2].text.startswith("(7)") and abschnitte[2].text.endswith("und ,,Hilfe“,")
    assert {a.kontext for a in abschnitte} == {"BPGG § 4 Anspruchsvoraussetzungen"}


def test_kaputter_dateiname_liest_metadaten_aus_xml() -> None:
    """Fängt einen Ingest, der Metadaten aus dem Dateinamen nimmt (der Name ist bei '/' im dokid
    abgeschnitten) oder solche Dateien verwirft."""
    dok = _dok(KAPUTTER_NAME)
    assert dok.dokid.endswith("223/2022=PARA=1=511=2022-12-30=2023-01-01")
    assert (dok.art, dok.nummer, dok.inkrafttreten.isoformat() if dok.inkrafttreten else None) == (
        "PARA",
        "1",
        "2023-01-01",
    )
    assert dok.datei == "Rechtstexte/" + KAPUTTER_NAME.name
    assert dok.meta["dokart"] == "V"


def test_nicht_parsebares_xml_wird_fehler_mit_grund() -> None:
    """Fängt einen Ingest, der bei kaputtem XML abbricht oder es still verschluckt (Oracle-Summe)."""
    ergebnis = lies_sozdok(FIXTURES / "Rechtstexte" / "KAPUTT=PARA=1=1=2020-01-01=2020-01-01.xml", FIXTURES)
    assert isinstance(ergebnis, Fehler)
    assert ergebnis.grund.startswith("XML nicht lesbar")


def test_eko_latin1_und_zeilennummern() -> None:
    """Fängt falsche Dekodierung (UTF-8 statt Latin-1) und verschobene Zeilennummern bei Leerzeilen."""
    dok = lies_eko(FIXTURES / "eko" / "regeltext.txt", FIXTURES)
    assert isinstance(dok, Dokument)
    assert [a.zeile for a in dok.abschnitte] == [1, 3]
    assert dok.abschnitte[0].text == "Eine Kostenübernahme ist nur möglich zur Selbstkatheterisierung."
    assert dok.abschnitte[0].kontext == "EKO regeltext Zeile 1 Pharmanummer 0087076"
    assert dok.meta["leerzeilen"] == 1


def test_inhalts_hash_unabhaengig_von_reihenfolge() -> None:
    """Fängt einen globalen Hash, der von Lade- oder DB-Reihenfolge abhängt (zwei Läufe ungleich)."""
    zeilen = [("B", 0, "h2"), ("A", 1, "h1"), ("A", 0, "h0")]
    assert ingest.inhalts_hash(zeilen) == ingest.inhalts_hash(list(reversed(zeilen)))
    assert ingest.inhalts_hash(zeilen) != ingest.inhalts_hash(zeilen[:2])


@pytest.mark.parametrize("wert", ["", "leer"])
def test_ohne_daten_dir_fehlercode(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, wert: str) -> None:
    """Fängt einen Ingest, der bei fehlendem oder leerem UC1_DATA_DIR 0 Zeilen meldet und Exit 0 gibt."""
    monkeypatch.setenv("UC1_DATA_DIR", str(tmp_path) if wert else "")
    assert ingest.cli([]) != 0


@pytest.mark.daten
def test_korpus_oracle_summe() -> None:
    """Fängt Dateien, die weder als Dokument noch als Fehler ankommen (Oracle aus #29)."""
    from uc1.db import verbinde

    wurzel = Path(os.environ.get("UC1_DATA_DIR", ""))
    if not (wurzel / "Rechtstexte").is_dir():
        pytest.skip("UC1_DATA_DIR fehlt")
    dateien = len(list((wurzel / "Rechtstexte").glob("*.xml")))
    with verbinde() as conn:
        zeile = conn.execute(
            "SELECT (SELECT count(*) FROM lotse.dokument WHERE quelle = 'sozdok')"
            " + (SELECT count(*) FROM lotse.ingest_fehler WHERE datei LIKE 'Rechtstexte/%')"
        ).fetchone()
    assert zeile is not None and zeile[0] == dateien


@pytest.mark.parametrize(
    ("bloeke", "soll"),
    [
        # Muster aus dem Korpus (gekürzt): Kennzeichen in der ersten Überschrift
        ([("ueberschrift", "aufgehoben - Pflegegeld"), ("absatz", "§ 206. Aufgehoben.")], True),
        ([("ueberschrift", "12. Aufgehoben."), ("absatz", "12. Aufgehoben.")], True),
        # ohne Kennzeichen in der Überschrift, Stummel als ganzer Text
        (
            [("ueberschrift", "Artikel 11"), ("absatz", "Artikel 11 Aufgehoben. (2.ZV, BGBl.Nr.270/1989)")],
            True,
        ),
        ([("absatz", "§ 26. (Anm.: aufgehoben durch BGBl. I Nr. 120/2012)")], True),
        # gültige §§ mit dem Wort im Fließtext oder in einer späteren Überschrift
        ([("ueberschrift", "Pflegegeld"), ("absatz", "§ 4. (1) Die Verordnung wird aufgehoben.")], False),
        ([("ueberschrift", "Krankengeld aufgehoben"), ("absatz", "§ 138. (1) Anspruch …")], False),
        ([("ueberschrift", "Schlussbestimmungen"), ("ueberschrift", "aufgehoben - Übergang")], False),
        ([("absatz", "(1) aufgehoben. " + "(2) Der Anspruch auf Pflegegeld besteht weiter. " * 8)], False),
    ],
)
def test_aufgehoben_nur_bei_kennzeichen_am_anfang(bloeke: list[tuple[str, str]], soll: bool) -> None:
    """Fängt eine Erkennung, die gültige §§ mit „aufgehoben“ im Fließtext markiert (sie fielen dann aus
    der Suche) oder Stummel ohne Kennzeichen in der Überschrift übersieht."""
    assert ingest.ist_aufgehoben(bloeke) is soll


@pytest.mark.daten
def test_aufgehoben_im_eingelesenen_korpus() -> None:
    """Fängt einen Ingest, der meta.aufgehoben nicht schreibt oder gültige Kern-§§ (BPGG § 4) markiert."""
    psycopg = pytest.importorskip("psycopg")
    from uc1.config import datenbank_url

    try:
        conn = psycopg.connect(datenbank_url(), connect_timeout=3)
    except psycopg.OperationalError:
        pytest.skip("DB lotse nicht erreichbar")
    with conn:
        zeilen = dict(
            conn.execute(
                "SELECT gesetz || ' ' || nummer, coalesce((meta->>'aufgehoben')::boolean, false)"
                " FROM lotse.dokument WHERE quelle = 'sozdok' AND art = 'PARA'"
                " AND (gesetz, nummer) IN (('ASVG', '206'), ('ASVG', '253c'), ('BPGG', '4'), ('ASVG', '139'))"
            ).fetchall()
        )
        gesamt = conn.execute(
            "SELECT count(*) FROM lotse.dokument WHERE coalesce((meta->>'aufgehoben')::boolean, false)"
        ).fetchone()
    assert zeilen == {"ASVG 206": True, "ASVG 253c": True, "BPGG 4": False, "ASVG 139": False}
    assert gesamt is not None and 1000 <= gesamt[0] <= 1200
