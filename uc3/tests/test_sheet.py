"""Aggregations-Sheet (berichte/sheet.py) auf der Fixture-Lieferung.

Die Vorlage des Veranstalters liegt nicht im Repo. Der Kern läuft deshalb gegen eine nachgebaute Mini-Vorlage
gleicher Bauart (CODE-Spalte, Monatsköpfe JJJJ-MM, Zeile Insgesamt mit =SUM); der Test gegen die echte
Vorlage überspringt sauber, wenn das Startpaket fehlt.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from openpyxl import Workbook, load_workbook

from statagent import konfig
from statagent.berichte.sheet import sheet_schreiben
from statagent.db import Verbindung
from statagent.ergebnis import monatserster, monatsletzter

FIXTURE_MONATE = ("2024-08", "2024-09", "2024-10")
MONATE_2008 = ("2024-08", "2024-09", "2024-10", "2024-11", "2024-12")
MONATE_2025 = ("2025-01", "2025-02", "2025-03")
ECHTE_VORLAGE = konfig.vorlagen() / "aggregationen_vorlage.xlsx"


def _laeufe(conn: Verbindung) -> None:
    from statagent import lauf

    for monat in FIXTURE_MONATE:  # Monatsreihenfolge (Fachbeschreibung § 2a)
        lauf.lauf_ausfuehren(conn, monat, regelsatz="v1", gestartet_von=None)


def _blatt(
    wb: Workbook, name: str, titel: str, zeilen: list[tuple[str, str]], monate: tuple[str, ...]
) -> None:
    ws = wb.create_sheet(name)
    ws.append(["CODE", titel, *monate])
    for code, text in zeilen:
        ws.append([code, text])
    ende = len(zeilen) + 1
    summe = ["", "Insgesamt"]
    summe += [
        f"=SUM({ws.cell(1, 3 + i).column_letter}2:{ws.cell(1, 3 + i).column_letter}{ende})"
        for i in range(len(monate))
    ]
    ws.append(summe)
    ws.freeze_panes = "C2"


def _mini_vorlage(conn: Verbindung, pfad: Path) -> Path:
    """Vorlage wie die des Veranstalters; Bundesland bewusst ohne Zeile '0' (prüft das Ergänzen)."""

    def codes(abfrage: str) -> list[tuple[str, str]]:
        return [(str(z["code"]), str(z["bezeichnung"])) for z in conn.execute(abfrage.encode()).fetchall()]

    alle = MONATE_2008 + MONATE_2025
    wb = Workbook()
    wb.active.title = "Hinweise"
    wb["Hinweise"]["A1"] = "Leere Zelle = 0. Bitte keine Zeilen oder Spalten umbenennen."
    land = codes(
        "SELECT code, bezeichnung FROM stat.klass_region WHERE ebene = 'bundesland' AND code <> '0' ORDER BY code"
    )
    _blatt(wb, "Bundesland", "Bundesland", land, alle)
    _blatt(wb, "Geschlecht", "Geschlecht", [("M", "Männer"), ("W", "Frauen")], alle)
    for version, monate in (("2008", MONATE_2008), ("2025", MONATE_2025)):
        oenace = codes(
            f"SELECT code, bezeichnung FROM stat.klass_oenace WHERE version = '{version}' ORDER BY code = 'UNB', code"
        )
        _blatt(wb, f"OENACE_{version}", f"Wirtschaftszweig (ÖNACE {version})", oenace, monate)
    qual = [
        ("ArbeiterDV", "Arbeiter (Dienstvertrag)"),
        ("AngestellteDV", "Angestellte (Dienstvertrag)"),
        ("Beamte", "Beamte"),
        ("ArbeiterFD", "Arbeiter (freier Dienstvertrag)"),
        ("AngestellteFD", "Angestellte (freier Dienstvertrag)"),
    ]
    _blatt(wb, "Beschaeftigungskategorie", "Beschäftigungskategorie", qual, alle)
    wb.save(pfad)
    return pfad


def _soll(conn: Verbindung, regelsatz: str, spalte: str, monat: str) -> dict[str, int]:
    """Unabhängig von sheet.py: Summe je Code direkt aus stat.stat_beschaeftigte (Stichtag)."""
    zeilen = conn.execute(
        f"""
        SELECT {spalte} AS code, sum(wert) AS n FROM stat.stat_beschaeftigte
        WHERE regelsatz = %s AND zeitraum_art = 'Stichtag' AND zeitraum_bis BETWEEN %s AND %s
        GROUP BY 1
        """.encode(),
        (regelsatz, monatserster(monat), monatsletzter(monat)),
    ).fetchall()
    return {str(z["code"]): int(str(z["n"])) for z in zeilen}


def _lesen(ws: Any, monat: str) -> tuple[dict[str, int], str]:
    """Werte je Code einer Monatsspalte und die Insgesamt-Formel."""
    spalte = next(c.column for c in ws[1] if c.value == monat)
    werte: dict[str, int] = {}
    formel = ""
    for r in range(2, ws.max_row + 1):
        if ws.cell(r, 2).value == "Insgesamt":
            formel = str(ws.cell(r, spalte).value)
            break
        werte[str(ws.cell(r, 1).value)] = int(ws.cell(r, spalte).value)
    return werte, formel


def test_sheet_mini_vorlage_v1(conn: Verbindung, tmp_path: Path) -> None:
    # Fängt: Werte in falscher Zeile/Spalte, Formeln überschrieben, fehlende Zeile 'unbekannt' (Summen
    # stimmen nicht), Kopfzeilen verändert, kein Kommentar für vorläufige Monate, nicht reproduzierbare Datei.
    _laeufe(conn)
    vorlage = _mini_vorlage(conn, tmp_path / "vorlage.xlsx")
    erg = sheet_schreiben(conn, "v1", ziel=tmp_path / "a.xlsx", vorlage=vorlage)

    assert erg.monate == list(FIXTURE_MONATE)
    assert erg.abweichungen == []
    assert erg.ergaenzt.get("Bundesland") == ["0"]  # Code 'unbekannt' laut quellzuordnung
    alt, neu = load_workbook(vorlage), load_workbook(erg.pfad)
    assert neu.sheetnames == alt.sheetnames
    for name in alt.sheetnames[1:]:
        assert [c.value for c in neu[name][1]] == [c.value for c in alt[name][1]]

    for monat in FIXTURE_MONATE:
        for blatt, spalte in (
            ("Bundesland", "region"),
            ("Geschlecht", "geschlecht"),
            ("OENACE_2008", "oenace"),
            ("Beschaeftigungskategorie", "qualifikation"),
        ):
            werte, formel = _lesen(neu[blatt], monat)
            soll = _soll(conn, "v1", spalte, monat)
            assert {c: w for c, w in werte.items() if w} == {c: w for c, w in soll.items() if w}, (
                blatt,
                monat,
            )
            assert formel.startswith("=SUM(")
        assert len({s[monat] for s in erg.summen.values() if monat in s}) == 1
    # Unveränderte Blätter behalten die Formel wörtlich, das ergänzte zieht den Bereich nach.
    assert neu["Geschlecht"]["C4"].value == "=SUM(C2:C3)"
    assert neu["Bundesland"]["B11"].value == "Bundesland unbekannt"
    assert neu["Bundesland"]["C12"].value == "=SUM(C2:C11)"
    assert neu["Bundesland"]["F1"].comment is None  # 2024-11 nicht gerechnet
    assert neu["Bundesland"]["F2"].value is None
    if erg.vorlaeufig:
        assert neu["Bundesland"]["C1"].comment.text.startswith("vorläufig: ")
    assert "Regelsatz v1" in str(neu["Hinweise"].cell(neu["Hinweise"].max_row, 1).value)

    zweite = sheet_schreiben(conn, "v1", ziel=tmp_path / "b.xlsx", vorlage=vorlage)
    assert zweite.pfad.read_bytes() == erg.pfad.read_bytes()
    # save() setzt modified auf „jetzt“; reproduzierbar nur, wenn der feste Wert danach wieder steht.
    assert neu.properties.modified == neu.properties.created


def test_sheet_v2_baut_kategorien_um(conn: Verbindung, tmp_path: Path) -> None:
    # Fängt: Blatt Beschäftigungskategorie bleibt bei fünf Qualifikationen, SUM-Bereich nicht nachgezogen,
    # Kategorie 'Unbekannt' fehlt, Blattsummen weichen ab.
    _laeufe(conn)
    with conn.transaction():
        conn.execute(
            """
            INSERT INTO meta.lauf (lieferung, regelsatz, regelstand, status, ergebnis_status, beendet_am, meldung)
            SELECT lieferung, 'v2', 'test-v2', 'fertig', ergebnis_status, beendet_am, 'Test v2'
            FROM meta.lauf WHERE regelsatz = 'v1' AND status IN ('fertig', 'unveraendert')
            """
        )
        # Ein neuer Regelsatz übernimmt die Quellzuordnung seiner Basis (regelaenderung.regelsatz_sicherstellen).
        conn.execute(
            """
            INSERT INTO stat.quellzuordnung (regelsatz, quelle, merkmal, version, geliefert, klassifikation, code,
                                             regel_id)
            SELECT 'v2', quelle, merkmal, version, geliefert, klassifikation, code, regel_id
            FROM stat.quellzuordnung WHERE regelsatz = 'v1'
            """
        )
        conn.execute(
            """
            INSERT INTO stat.stat_beschaeftigte
            SELECT s.zeitraum_art, s.zeitraum_von, s.zeitraum_bis, s.region, s.oenace, s.oenace_version,
                   s.geschlecht, q.beschaeftigungskategorie, s.alter, s.variable, sum(s.wert), s.status, s.stand,
                   'v2', 'test-v2', l2.id
            FROM stat.stat_beschaeftigte s
            JOIN stat.klass_qualifikation q ON q.code = s.qualifikation
            JOIN meta.lauf l2 ON l2.regelsatz = 'v2' AND l2.lieferung = to_char(s.zeitraum_bis, 'YYYY-MM')
            WHERE s.regelsatz = 'v1'
            GROUP BY 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 12, 13, 16
            """
        )
        # Künstliche Zelle mit Kategorie 'Unbekannt' (prüft die Zeile Unbekannt im Umbau).
        conn.execute(
            """
            INSERT INTO stat.stat_beschaeftigte
            SELECT zeitraum_art, zeitraum_von, zeitraum_bis, region, oenace, oenace_version, geschlecht,
                   'Unbekannt', -1, variable, 1, status, stand, regelsatz, regelstand, lauf_id
            FROM stat.stat_beschaeftigte WHERE regelsatz = 'v2' AND zeitraum_bis = '2024-08-31' LIMIT 1
            """
        )
    vorlage = _mini_vorlage(conn, tmp_path / "vorlage.xlsx")
    erg = sheet_schreiben(conn, "v2", ziel=tmp_path / "v2.xlsx", vorlage=vorlage)

    assert erg.kategorien
    assert erg.abweichungen == []
    ws = load_workbook(erg.pfad)["Beschaeftigungskategorie"]
    assert [ws.cell(r, 1).value for r in range(2, 6)] == ["Arbeiter", "Angestellte", "Beamte", "Unbekannt"]
    assert ws["B6"].value == "Insgesamt"
    assert ws["C6"].value == "=SUM(C2:C5)"
    assert ws["C1"].value == "2024-08"
    for monat in FIXTURE_MONATE:
        werte, _ = _lesen(ws, monat)
        soll = _soll(conn, "v2", "qualifikation", monat)
        assert {c: w for c, w in werte.items() if w} == {c: w for c, w in soll.items() if w}
    assert erg.summen["Beschaeftigungskategorie"]["2024-08"] == erg.summen["Bundesland"]["2024-08"]


@pytest.mark.skipif(not ECHTE_VORLAGE.is_file(), reason="Vorlage des Veranstalters (Startpaket) fehlt")
def test_sheet_echte_vorlage(conn: Verbindung, tmp_path: Path) -> None:
    # Fängt: Vorlage des Veranstalters anders gebaut als angenommen (Kopf, CODE-Spalte, Formeln).
    _laeufe(conn)
    erg = sheet_schreiben(conn, "v1", ziel=tmp_path / "echt.xlsx")
    assert erg.abweichungen == []
    alt, neu = load_workbook(ECHTE_VORLAGE), load_workbook(erg.pfad)
    assert neu.sheetnames == alt.sheetnames
    for name in alt.sheetnames[1:]:
        assert [c.value for c in neu[name][1]] == [c.value for c in alt[name][1]]
    for name in ("Bundesland", "OENACE_2008", "OENACE_2025"):
        if name not in erg.ergaenzt:
            assert [c.value for c in neu[name][alt[name].max_row]] == [
                c.value for c in alt[name][alt[name].max_row]
            ]
    werte, _ = _lesen(neu["Bundesland"], "2024-08")
    assert {c: w for c, w in werte.items() if w} == {
        c: w for c, w in _soll(conn, "v1", "region", "2024-08").items() if w
    }
