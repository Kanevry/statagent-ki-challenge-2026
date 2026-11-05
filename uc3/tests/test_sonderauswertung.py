"""Sonderauswertung Personentage (Auftrag 3): Datenstand je Tag, Tage je Person, Freigabe der Lieferung."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from statagent.db import Verbindung
from statagent.lauf import lauf_ausfuehren
from statagent.regeln import NameUngueltig, regeln_freigeben
from statagent.sonderauswertung import NichtFreigegeben, ministerium_schreiben

PARAMETER = {
    "monate": 1,
    "qualifikationen": ["ArbeiterDV", "ArbeiterFD"],
    "oenace": "C",
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
        ministerium_schreiben(conn, "2024-11", "Erika Musterfrau", ziel_dir=tmp_path)
    regeln_freigeben(conn, "ministerium", "Erika Musterfrau")
    with pytest.raises(NameUngueltig):
        ministerium_schreiben(conn, "2024-11", "Team", ziel_dir=tmp_path)


def test_personentage_november(conn: Verbindung, tmp_path: Path) -> None:
    # Fängt: falscher Datenstand (jüngste Lieferung), Angestellte/andere Abschnitte mitgezählt, ein ungültiges
    # ENDE als beendet gewertet, Ende vor dem Zeitraum gezählt, Sortierung oder CSV-Kopf falsch.
    _auswertungsregel(conn)
    regeln_freigeben(conn, "ministerium", "Erika Musterfrau")
    datei, auswertung = ministerium_schreiben(conn, "2024-11", "Erika Musterfrau", ziel_dir=tmp_path)
    assert auswertung.datenstand == {"2024-11": "2024-11"}
    assert datei.read_text(encoding="utf-8").splitlines() == [
        "PERSON_ID;GESCHLECHT;GEBURTSJAHR;TAGE",
        "7001;M;1970;30",
        "7002;W;1944;30",
        "7003;M;1985;30",
        "7004;M;1985;30",
    ]
    ausgabe = conn.execute(
        b"SELECT zeilen, freigegeben_von FROM meta.ausgabe WHERE art = 'ministerium' AND berichtsmonat = '2024-11'"
    ).fetchone()
    assert ausgabe is not None and (ausgabe["zeilen"], ausgabe["freigegeben_von"]) == (4, "Erika Musterfrau")
