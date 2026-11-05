"""Prüfung der Abgabedateien auf erfundenen Minimalordnern (ohne Datenbank).

Die echte Vorlage des Veranstalters liegt nicht im Repo; die Tests legen eine Mini-Vorlage unter tmp_path an
und übergeben `vorlagen_dir`, damit das Ergebnis nicht vom lokalen Startpaket abhängt.
"""

from __future__ import annotations

import hashlib
from collections.abc import Callable
from pathlib import Path
from typing import Any

import openpyxl
import pytest
from openpyxl.utils import get_column_letter

from statagent.berichte.pruefe_abgabe import (
    ERGEBNIS_BLAETTER,
    VORLAGE_BLAETTER,
    berichtsmonate,
    blatt_monate,
    pruefe_abgabe,
)

BERICHTE = "Qualitätsberichte 2024-08 bis 2026-07"
SHEET_V1 = "Aggregations-Sheet v1"
VORLAGE = "Vorlage Qualitätsbericht"

#: Überschriften wörtlich wie in der Vorlage des Veranstalters (nicht aus dem Generator übernommen).
UEBERSCHRIFTEN = [
    "## 1 Überblick",
    "## 2 Auffälligkeiten",
    "## 3 Rückfragen an die Fachabteilung",
    "## 4 Angewendete Regeln",
    "## 5 Revisionsbedarf früherer Monate",
]
ABRECHNUNG = (
    "Abrechnung in Zahlen: 1.000 gelesen = 990 gezählt + 8 nicht gezählt + 2 ausgeschlossen (geht auf)."
)


def _vorlage(ordner: Path, ueberschriften: list[str] = UEBERSCHRIFTEN) -> Path:
    ordner.mkdir(parents=True, exist_ok=True)
    (ordner / "qualitaetsbericht_vorlage.md").write_text(
        "\n".join(
            [
                "# Qualitätsbericht – Berichtsmonat JJJJ-MM",
                "",
                ueberschriften[0],
                "",
                "Abrechnung: gelesene Sätze = gezählte + nicht gezählte + ausgeschlossene Sätze.",
                "",
                ueberschriften[1],
                "",
                "Einstufung: **erklärt – plausibel** (a) · **erklärt – Datenproblem** (b) · **nicht erklärbar** (c).",
                "",
                *ueberschriften[2:],
                "",
            ]
        ),
        encoding="utf-8",
    )
    return ordner


def _bericht(
    monat: str = "2024-08", einstufung: str = "erklärt – plausibel", abrechnung: str = ABRECHNUNG
) -> str:
    return "\n".join(
        [
            f"# Qualitätsbericht – Berichtsmonat {monat}",
            "",
            "Lieferung: `lieferung_JJJJ-MM.csv` · erstellt am 01.01.2026 · freigegeben von: Erika Muster",
            "",
            UEBERSCHRIFTEN[0],
            "",
            "| Kennzahl | Wert |",
            "| --- | --- |",
            "| gelesene Sätze | 1.000 |",
            "| davon gezählt am Stichtag | 990 |",
            "",
            abrechnung,
            "",
            UEBERSCHRIFTEN[1],
            "",
            "| Nr. | Ebene | Beschreibung | Umfang | Beleg (Abfrage) | Einstufung | Maßnahme | Rückfrage |",
            "| --- | --- | --- | --- | --- | --- | --- | --- |",
            f"| 1 | Satz | Test | 3 Sätze | `SELECT 1 \\| 2` | {einstufung} | – | – |",
            "",
            UEBERSCHRIFTEN[2],
            "",
            "Keine Rückfragen.",
            UEBERSCHRIFTEN[3],
            "",
            "| Regel | Seit Berichtsmonat |",
            "| --- | --- |",
            "| R1 | 2024-08 |",
            UEBERSCHRIFTEN[4],
            "",
            "Kein Revisionsbedarf.",
            "",
        ]
    )


def _sheet(pfad: Path, blaetter: list[str]) -> None:
    """Sheet mit zwei Datenzeilen (10 und 20) je Monat und Insgesamt als =SUM über beide."""
    mappe = openpyxl.Workbook()
    mappe.active.title = blaetter[0]
    for name in blaetter[1:]:
        mappe.create_sheet(name)
    for name in ERGEBNIS_BLAETTER:
        ws = mappe[name]
        ws.append(["CODE", name, *blatt_monate(name)])
        ws.append(["1", "eins", *[10] * len(blatt_monate(name))])
        ws.append(["2", "zwei", *[20] * len(blatt_monate(name))])
        ws.append(
            [
                None,
                "Insgesamt",
                *[
                    f"=SUM({get_column_letter(s)}2:{get_column_letter(s)}3)"
                    for s in range(3, ws.max_column + 1)
                ],
            ]
        )
    mappe.save(pfad)


def _sheet_aendern(pfad: Path, aenderung: Callable[[Any], None]) -> None:
    mappe = openpyxl.load_workbook(pfad)
    aenderung(mappe)
    mappe.save(pfad)


def _vollstaendig(wurzel: Path) -> Path:
    abgabe = wurzel / "abgabe"
    (abgabe / "qualitaetsberichte").mkdir(parents=True)
    _sheet(abgabe / "aggregationen_v1.xlsx", VORLAGE_BLAETTER)
    _sheet(abgabe / "aggregationen_v2.xlsx", VORLAGE_BLAETTER)
    for monat in berichtsmonate():
        (abgabe / "qualitaetsberichte" / f"{monat}.md").write_text(_bericht(monat), encoding="utf-8")
    (abgabe / "ministerium_2026-07.csv").write_text(
        "PERSON_ID;GESCHLECHT;GEBURTSJAHR;TAGE\n2;W;1980;200\n10;M;1975;365\n", encoding="utf-8"
    )
    (abgabe / "protokoll.md").write_text("# Protokoll\n", encoding="utf-8")
    (wurzel / "docs").mkdir()
    (wurzel / "docs" / "models.md").write_text("# Modelle\n", encoding="utf-8")
    (wurzel / "uc3" / "statagent").mkdir(parents=True)
    (wurzel / "uc3" / "statagent" / "lauf.py").write_text("x = 1\n", encoding="utf-8")
    return abgabe


def _pruefen(abgabe: Path, wurzel: Path, vorlagen: Path | None = None) -> dict[str, str]:
    """Hinweise der fehlenden Punkte; prüft nebenbei, dass `ok` nur ohne fehlende Punkte gilt."""
    erg = pruefe_abgabe(
        abgabe, wurzel, blaetter=VORLAGE_BLAETTER, vorlagen_dir=vorlagen or _vorlage(wurzel / "vorlagen")
    )
    fehlend = {p.name: p.hinweis for p in erg.punkte if not p.ok}
    assert erg.ok is (not fehlend)
    return fehlend


def test_leerer_ordner_ohne_vorlage_alle_punkte_fehlen(tmp_path: Path) -> None:
    # Fängt: Absturz bei fehlenden Dateien oder ein Punkt, der ohne Datei (oder ohne Vorlage) als erfüllt gilt.
    erg = pruefe_abgabe(tmp_path, tmp_path, blaetter=VORLAGE_BLAETTER, vorlagen_dir=tmp_path / "keine")
    assert len(erg.punkte) == 8
    assert not any(p.ok for p in erg.punkte)
    assert erg.als_text().count("[fehlt]") == 8
    assert erg.als_dict()["ok"] is False


def test_leere_abgabe_mit_vorlage_besteht_nicht(tmp_path: Path) -> None:
    # Fängt: leerer Abgabeordner besteht, weil nur die Vorlage gefunden wird.
    (tmp_path / "abgabe").mkdir()
    fehlend = _pruefen(tmp_path / "abgabe", tmp_path)
    assert VORLAGE not in fehlend
    assert len(fehlend) == 7


def test_vollstaendiger_minimalordner_ist_ok(tmp_path: Path) -> None:
    # Fängt: zu strenge Prüfung (numerische Sortierung, maskierte Pipe im Beleg, Trennzeile als Daten,
    # ÖNACE-Blätter mit nur ihren Monaten).
    abgabe = _vollstaendig(tmp_path)
    assert _pruefen(abgabe, tmp_path) == {}


def test_ohne_vorlage_nicht_stillschweigend_ok(tmp_path: Path) -> None:
    # Fängt: fehlende Vorlage (CI ohne Startpaket) wird still durch die Generator-Struktur ersetzt.
    abgabe = _vollstaendig(tmp_path)
    fehlend = _pruefen(abgabe, tmp_path, vorlagen=tmp_path / "keine")
    assert fehlend == {VORLAGE: "Vorlage nicht gefunden: Struktur nur gegen den Generator geprüft"}


def test_vorlage_mit_abweichender_ueberschrift(tmp_path: Path) -> None:
    # Fängt: Überschriften kommen aus dem Generator statt aus der Vorlage des Veranstalters.
    abgabe = _vollstaendig(tmp_path)
    anders = [*UEBERSCHRIFTEN[:2], "## 3 Rückfragen an die Fachabteilung und Antworten", *UEBERSCHRIFTEN[3:]]
    fehlend = _pruefen(abgabe, tmp_path, vorlagen=_vorlage(tmp_path / "andere", anders))
    assert set(fehlend) == {BERICHTE}
    assert "„3 Rückfragen an die Fachabteilung und Antworten“" in fehlend[BERICHTE]


@pytest.mark.parametrize(
    ("inhalt", "erwartet"),
    [
        # Fängt: Bericht ohne Abrechnungszeile in § 1 besteht.
        (_bericht("2025-03", abrechnung="Abrechnung: siehe Lauf."), "ohne Zeile „Abrechnung in Zahlen“"),
        # Fängt: Abrechnung, die nicht aufgeht (Rechnung falsch, obwohl der Text „geht auf“ sagt).
        (_bericht("2025-03", abrechnung=ABRECHNUNG.replace("990", "900")), "geht nicht auf"),
        # Fängt: Bericht eines anderen Monats unter dem Dateinamen 2025-03.
        (_bericht("2025-04"), "passt nicht zu 2025-03"),
        # Fängt: fast leere Datei, die nur die fünf Überschriften trägt.
        ("# Qualitätsbericht – Berichtsmonat 2025-03\n" + "\n".join(UEBERSCHRIFTEN), "(leer)"),
        # Fängt: falsche Einstufung außerhalb der drei Werte der Vorlage.
        (_bericht("2025-03", "erklärt"), "„erklärt“"),
    ],
)
def test_mangelhafter_bericht(tmp_path: Path, inhalt: str, erwartet: str) -> None:
    abgabe = _vollstaendig(tmp_path)
    (abgabe / "qualitaetsberichte" / "2025-03.md").write_text(inhalt, encoding="utf-8")
    fehlend = _pruefen(abgabe, tmp_path)
    assert set(fehlend) == {BERICHTE}
    assert "2025-03" in fehlend[BERICHTE]
    assert erwartet in fehlend[BERICHTE]


def test_bericht_ohne_tabellenzeile_in_auffaelligkeiten(tmp_path: Path) -> None:
    # Fängt: § 2 mit Kopf, aber ohne eine einzige Tabellenzeile besteht.
    abgabe = _vollstaendig(tmp_path)
    ohne = "\n".join(z for z in _bericht("2025-03").splitlines() if not z.startswith("| 1 | Satz"))
    (abgabe / "qualitaetsberichte" / "2025-03.md").write_text(ohne, encoding="utf-8")
    assert "„2 Auffälligkeiten“ ohne Tabellenzeile" in _pruefen(abgabe, tmp_path)[BERICHTE]


def test_sheet_mit_richtigen_blattnamen_aber_leeren_monatsspalten(tmp_path: Path) -> None:
    # Fängt: Sheet-Prüfung, die nur Blattnamen prüft (leeres Sheet besteht).
    abgabe = _vollstaendig(tmp_path)

    def leeren(mappe: Any) -> None:
        for name in ERGEBNIS_BLAETTER:
            for zeile in mappe[name].iter_rows(min_row=2, max_row=3, min_col=3):
                for zelle in zeile:
                    zelle.value = None

    _sheet_aendern(abgabe / "aggregationen_v1.xlsx", leeren)
    fehlend = _pruefen(abgabe, tmp_path)
    assert set(fehlend) == {SHEET_V1}
    assert "Bundesland 2024-08: Spalte leer" in fehlend[SHEET_V1]


def test_sheet_ohne_monatsspalte(tmp_path: Path) -> None:
    # Fängt: fehlender Berichtsmonat (hier 2026-07 im Blatt Geschlecht) fällt nicht auf.
    abgabe = _vollstaendig(tmp_path)
    _sheet_aendern(
        abgabe / "aggregationen_v1.xlsx", lambda m: m["Geschlecht"].delete_cols(m["Geschlecht"].max_column)
    )
    assert "Geschlecht: Spalte 2026-07 fehlt" in _pruefen(abgabe, tmp_path)[SHEET_V1]


def test_insgesamt_als_zahl_statt_formel(tmp_path: Path) -> None:
    # Fängt: Insgesamt-Zeile mit festem Wert statt =SUM über die Datenzeilen.
    abgabe = _vollstaendig(tmp_path)

    def zahl(mappe: Any) -> None:
        mappe["Bundesland"]["C4"] = 30

    _sheet_aendern(abgabe / "aggregationen_v1.xlsx", zahl)
    fehlend = _pruefen(abgabe, tmp_path)
    assert set(fehlend) == {SHEET_V1}
    assert "Bundesland 2024-08: Insgesamt 30 statt =SUM(C2:C3)" in fehlend[SHEET_V1]


def test_blattsummen_ungleich(tmp_path: Path) -> None:
    # Fängt: ein Blatt summiert in einem Monat anders als die übrigen Blätter.
    abgabe = _vollstaendig(tmp_path)

    def abweichen(mappe: Any) -> None:
        mappe["Geschlecht"]["C2"] = 11

    _sheet_aendern(abgabe / "aggregationen_v1.xlsx", abweichen)
    fehlend = _pruefen(abgabe, tmp_path)
    assert set(fehlend) == {SHEET_V1}
    assert "2024-08: Blattsummen ungleich" in fehlend[SHEET_V1]
    assert "Geschlecht 31" in fehlend[SHEET_V1]


def test_regelkonstante_im_code_ist_nicht_ok(tmp_path: Path) -> None:
    # Fängt: Regelkonstante im Code wird übersehen.
    abgabe = _vollstaendig(tmp_path)
    (tmp_path / "uc3" / "statagent" / "zaehlung.py").write_text("CODE = 'UNB'\n", encoding="utf-8")
    fehlend = _pruefen(abgabe, tmp_path)
    assert set(fehlend) == {"keine Regelkonstanten im Code (Technische Regel 3)"}
    assert "zaehlung.py:1" in fehlend["keine Regelkonstanten im Code (Technische Regel 3)"]


def _beleg(abgabe: Path, sha: str) -> None:
    (abgabe / "ministerium_2026-07.beleg.md").write_text(
        f"# Ministeriums-Lieferung 2026-07\n\n| Angabe | Wert |\n| --- | --- |\n| sha256 | `{sha}` |\n",
        encoding="utf-8",
    )


def test_ministerium_ohne_csv_reicht_der_beleg_mit_sha256(tmp_path: Path) -> None:
    # Fängt: die Jury-Kopie des Repos (CSV mit Einzeldaten bewusst nicht enthalten) gilt als unvollständig, oder
    # ein Beleg ohne sha256 gilt als Lieferung.
    abgabe = _vollstaendig(tmp_path)
    csv_datei = abgabe / "ministerium_2026-07.csv"
    sha = hashlib.sha256(csv_datei.read_bytes()).hexdigest()
    csv_datei.unlink()
    (abgabe / "ministerium_2026-07.beleg.md").write_text("# ohne Prüfsumme\n", encoding="utf-8")
    assert "ohne sha256" in _pruefen(abgabe, tmp_path)["Ministeriums-Lieferung 2026-07"]
    _beleg(abgabe, sha)
    assert "Ministeriums-Lieferung 2026-07" not in _pruefen(abgabe, tmp_path)


def test_ministerium_csv_muss_zur_sha256_im_beleg_passen(tmp_path: Path) -> None:
    # Fängt: eine geänderte oder falsche CSV wird abgegeben, obwohl der freigegebene Beleg eine andere sha256 nennt.
    abgabe = _vollstaendig(tmp_path)
    _beleg(abgabe, "0" * 64)
    assert "passt nicht" in _pruefen(abgabe, tmp_path)["Ministeriums-Lieferung 2026-07"]
