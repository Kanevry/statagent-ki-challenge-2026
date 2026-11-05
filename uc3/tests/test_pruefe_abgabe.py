"""Prüfung der Abgabedateien auf erfundenen Minimalordnern (ohne Datenbank)."""

from __future__ import annotations

from pathlib import Path

import openpyxl

from statagent.berichte.pruefe_abgabe import VORLAGE_BLAETTER, berichtsmonate, pruefe_abgabe
from statagent.berichte.qualitaetsbericht import ABSCHNITTE


def _bericht(einstufung: str = "erklärt – plausibel") -> str:
    return "\n".join([
        "# Qualitätsbericht – Berichtsmonat 2024-08",
        "",
        ABSCHNITTE[0],
        "",
        ABSCHNITTE[1],
        "",
        "| Nr. | Ebene | Beschreibung | Umfang | Beleg (Abfrage) | Einstufung | Maßnahme | Rückfrage |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
        f"| 1 | Satz | Test | 3 Sätze | `SELECT 1 \\| 2` | {einstufung} | – | – |",
        "",
        *ABSCHNITTE[2:],
        "",
    ])


def _sheet(pfad: Path, blaetter: list[str]) -> None:
    mappe = openpyxl.Workbook()
    mappe.active.title = blaetter[0]
    for name in blaetter[1:]:
        mappe.create_sheet(name)
    mappe.save(pfad)


def _vollstaendig(wurzel: Path) -> Path:
    abgabe = wurzel / "abgabe"
    (abgabe / "qualitaetsberichte").mkdir(parents=True)
    _sheet(abgabe / "aggregationen_v1.xlsx", VORLAGE_BLAETTER)
    _sheet(abgabe / "aggregationen_v2.xlsx", VORLAGE_BLAETTER)
    for monat in berichtsmonate():
        (abgabe / "qualitaetsberichte" / f"{monat}.md").write_text(_bericht(), encoding="utf-8")
    (abgabe / "ministerium_2026-07.csv").write_text(
        "PERSON_ID;GESCHLECHT;GEBURTSJAHR;TAGE\n2;W;1980;200\n10;M;1975;365\n", encoding="utf-8"
    )
    (abgabe / "protokoll.md").write_text("# Protokoll\n", encoding="utf-8")
    (wurzel / "docs").mkdir()
    (wurzel / "docs" / "models.md").write_text("# Modelle\n", encoding="utf-8")
    (wurzel / "uc3" / "statagent").mkdir(parents=True)
    (wurzel / "uc3" / "statagent" / "lauf.py").write_text("x = 1\n", encoding="utf-8")
    return abgabe


def test_leerer_ordner_alle_punkte_fehlen(tmp_path: Path) -> None:
    # Fängt: Absturz bei fehlenden Dateien oder ein Punkt, der ohne Datei als erfüllt gilt.
    erg = pruefe_abgabe(tmp_path, tmp_path, blaetter=VORLAGE_BLAETTER)
    assert len(erg.punkte) == 7
    assert not any(p.ok for p in erg.punkte)
    assert not erg.ok
    assert erg.als_text().count("[fehlt]") == 7
    assert erg.als_dict()["ok"] is False


def test_vollstaendiger_minimalordner_ist_ok(tmp_path: Path) -> None:
    # Fängt: zu strenge Prüfung (numerische Sortierung, maskierte Pipe im Beleg, Trennzeile als Daten).
    abgabe = _vollstaendig(tmp_path)
    erg = pruefe_abgabe(abgabe, tmp_path, blaetter=VORLAGE_BLAETTER)
    assert erg.ok, erg.als_text()


def test_falsche_einstufung_und_regelkonstante_sind_nicht_ok(tmp_path: Path) -> None:
    # Fängt: Einstufung außerhalb der Drei-Werte-Liste oder Regelkonstante im Code wird übersehen.
    abgabe = _vollstaendig(tmp_path)
    (abgabe / "qualitaetsberichte" / "2025-03.md").write_text(_bericht("erklärt"), encoding="utf-8")
    (tmp_path / "uc3" / "statagent" / "zaehlung.py").write_text("CODE = 'U" "NB'\n", encoding="utf-8")
    erg = pruefe_abgabe(abgabe, tmp_path, blaetter=VORLAGE_BLAETTER)
    assert not erg.ok
    fehlend = {p.name: p.hinweis for p in erg.punkte if not p.ok}
    assert "2025-03" in fehlend["Qualitätsberichte 2024-08 bis 2026-07"]
    assert "„erklärt“" in fehlend["Qualitätsberichte 2024-08 bis 2026-07"]
    assert "zaehlung.py:1" in fehlend["keine Regelkonstanten im Code (Technische Regel 3)"]
    assert len(fehlend) == 2
