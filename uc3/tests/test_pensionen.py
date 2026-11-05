"""Pensionsstatistik (#77): Formate erkennen, laden, prüfen, fragen. Die Dateien entstehen im Test aus den Formatregeln."""

from __future__ import annotations

import re
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from openpyxl import Workbook, load_workbook

from statagent import frage as frage_modul
from statagent import konfig, pensionen
from statagent.db import Verbindung
from statagent.pensionen import FormatUnbekannt, PensionFehler
from statagent.regeln import NameUngueltig, regeln_laden, regelstand

MAENNLICH = {"Männer", "Witwer", "M", "m", "männlich"}
T12 = ["geminderte Arbeitsfähigkeit/Erwerbsunfähigkeit", "Alter", "Witwen/Witwer", "Waisen"]
T13 = ["lange Versicherungsdauer", "Korridorpension", "Langzeitversicherte",
       "Schwerarbeit § 607/14 ASVG", "Schwerarbeit § 4 Abs. 3 APG"]  # fmt: skip


def _wert(zeile: int, spalte: int, geschlecht: str) -> int:
    """Männer haben immer mehr als Frauen: Ein Spaltentausch würde jede Summe halten, aber diese Eigenschaft brechen."""
    return 100 * (zeile + 1) + spalte + (5000 if geschlecht in MAENNLICH else 0)


def _kopf_schreiben(wb: Workbook, f: pensionen.Format, jahr: int) -> None:
    wb.remove(wb.active)  # type: ignore[arg-type]
    for name in f.blaetter:
        wb.create_sheet(name.replace("JJJJ", str(jahr)))
    for k in f.kopf:
        ws = wb[str(k["blatt"]).replace("JJJJ", str(jahr))]
        for spalte, wert in enumerate(k["zellen"], 1):
            if wert is not None:
                ws.cell(int(k["zeile"]), spalte, str(wert).replace("JJJJ", str(jahr)))


def _kreuz(ws: Any, zeilen: list[str], kopf: list[Any], geschlecht: list[Any], start: int) -> None:
    for i, name in enumerate(zeilen):
        ws.cell(start + i + 1, 1, name)
    for spalte in range(2, len(kopf)):
        werte = [_wert(i, spalte, str(geschlecht[spalte])) for i in range(len(zeilen))]
        for i, w in enumerate(werte):
            ws.cell(start + i + 1, spalte + 1, w)
        ws.cell(start, spalte + 1, sum(werte))
    for zeile in range(start, start + len(zeilen) + 1):
        ws.cell(zeile, 2, sum(ws.cell(zeile, s + 1).value for s in range(2, len(kopf))))


def datei_bauen(f: pensionen.Format, jahr: int, pfad: Path) -> None:
    wb = Workbook()
    _kopf_schreiben(wb, f, jahr)
    if f.parser == "kreuztabelle":
        for t in f.tabellen.values():
            ws = wb[t["blatt"]]
            kopf = [c.value for c in ws[4]]
            geschlecht = [c.value for c in ws[5]]
            ws.cell(6, 1, "Pensionsversicherungsanstalt gesamt")
            _kreuz(ws, ["  davon Arbeiter", "  davon Angestellte"], kopf, geschlecht, 6)
    elif f.parser == "flach":
        for t in f.tabellen.values():
            ws = wb[t["blatt"]]
            kopf = [c.value for c in ws[1]]
            geschlecht = [None, None, *(str(k).rpartition(" – ")[2] for k in kopf[2:])]
            ws.cell(2, 1, "Pensionsversicherungsanstalt gesamt")
            _kreuz(ws, ["davon Arbeiter", "davon Angestellte"], kopf, geschlecht, 2)
    elif f.parser == "kuerzel":
        for t in f.tabellen.values():
            ws = wb[t["blatt"]]
            kopf = [c.value for c in ws[1]]
            ws.cell(2, 1, jahr)
            ws.cell(2, 2, f.quelle)
            werte = [_wert(0, s, str(kopf[s]).rpartition("_")[2]) for s in range(3, len(kopf))]
            ws.cell(2, 3, sum(werte))
            for s, w in enumerate(werte, 4):
                ws.cell(2, s, w)
    elif f.parser == "bloecke":
        for kopfzeile in (4, 10):
            ws = wb["Pensionen"]
            kopf = [c.value for c in ws[kopfzeile] if c.value is not None]
            zeilen: list[list[int]] = [[], []]
            for s in range(2, len(kopf)):
                for i in (0, 1):
                    zeilen[i].append(_wert(i, s, str(kopf[s]).rpartition(" ")[2]))
            namen = ["Eisenbahn", "Bergbau"]
            for i in (0, 1):
                ws.cell(kopfzeile + 1 + i, 1, namen[i])
                ws.cell(kopfzeile + 1 + i, 2, f"{sum(zeilen[i]):,}".replace(",", "."))
                for s, w in enumerate(zeilen[i], 3):
                    ws.cell(kopfzeile + 1 + i, s, f"{w:,}".replace(",", "."))
            ws.cell(kopfzeile + 3, 1, "Gesamt")
            ws.cell(kopfzeile + 3, 2, f"{sum(zeilen[0]) + sum(zeilen[1]):,}".replace(",", "."))
            for s in range(len(zeilen[0])):
                ws.cell(kopfzeile + 3, s + 3, f"{zeilen[0][s] + zeilen[1][s]:,}".replace(",", "."))
    elif f.parser == "lang_anzahl":
        ws = wb[f"Pensionen {jahr}"]
        summe = 0
        z = 6
        for art in T12:
            for g in ("männlich", "weiblich"):
                w = _wert(0, z, g)
                summe += w
                ws.cell(z, 1, art)
                ws.cell(z, 2, g)
                ws.cell(z, 3, w)
                z += 1
        ws.cell(5, 1, "Pensionen insgesamt")
        ws.cell(5, 3, summe)
    else:
        ws = wb["Daten"]
        sparten = ("GW", "LW") if f.quelle == "SVS-BIS-2022" else ("Gewerbliche Wirtschaft", "Landwirtschaft")
        geschlechter = ("M", "W") if f.quelle == "SVS-BIS-2022" else ("m", "w")
        z = 2
        for sparte in sparten:
            for tabelle, arten in (("Pensionsstand", T12), ("Vorzeitige Alterspensionen", T13)):
                for art in arten:
                    for g in geschlechter:
                        zeile = [jahr, sparte, tabelle, art, g, _wert(0, z, g)]
                        if f.zeitraum_spalte:
                            zeile.append(f"JD {jahr}")
                        for s, wert in enumerate(zeile, 1):
                            ws.cell(z, s, wert)
                        z += 1
    pfad.parent.mkdir(parents=True, exist_ok=True)
    wb.save(pfad)


def _dateiname(f: pensionen.Format, jahr: int) -> str:
    return f"{f.quelle} Meldung {jahr}.xlsx"


def _formate(conn: Verbindung) -> list[pensionen.Format]:
    return pensionen.regelwerk_laden(conn).formate


@pytest.fixture
def ordner(conn: Verbindung, tmp_path: Path) -> Path:
    for f in _formate(conn):
        for jahr in range(f.jahr_von, f.jahr_bis + 1):
            datei_bauen(f, jahr, tmp_path / str(jahr) / _dateiname(f, jahr))
    return tmp_path


def _format(conn: Verbindung, quelle: str) -> pensionen.Format:
    return next(f for f in _formate(conn) if f.quelle == quelle)


def _aendern(pfad: Path, tun: Callable[[Any], None]) -> None:
    wb = load_workbook(pfad)
    tun(wb)
    wb.save(pfad)


def _anzahl(conn: Verbindung) -> int:
    zeile = conn.execute("SELECT count(*) AS n FROM stat.stat_pensionen").fetchone()
    assert zeile is not None
    return int(str(zeile["n"]))


def _wert_in_db(conn: Verbindung, jahr: int, traeger: str, art: str, geschlecht: str) -> int:
    zeile = conn.execute(
        """SELECT wert FROM stat.stat_pensionen WHERE zeitraum_von = make_date(%s, 1, 1)
           AND versicherungstraeger = %s AND pensionsart = %s AND geschlecht = %s""",
        (jahr, traeger, art, geschlecht),
    ).fetchone()
    assert zeile is not None
    return int(str(zeile["wert"]))


def test_alle_formate_laden_und_summen_stimmen(conn: Verbindung, ordner: Path) -> None:
    # Fängt: ein Format liest Zeilen falsch, eine Summenzeile landet in der Statistik, eine Kombination fehlt.
    daten = pensionen.laden(conn, ordner)
    assert daten["dateien"] == 28
    assert len(daten["formate"]) == 9
    # 2018/19: PVA 36, VAEB 36, SVA 18, SVB 18, VAN 8; 2020–25: PVA 36, BVAEB 36, SVS 36.
    assert daten["werte"] == 2 * 116 + 6 * 108 == _anzahl(conn)
    bericht = pensionen.pruefbericht(conn)
    assert bericht["summen"]["geprueft"] > 0 and bericht["summen"]["abweichend"] == 0
    assert bericht["qualifikation_getrennt"] == 0
    # Die Testwerte sind nicht fachlich: Tabelle 13 ist hier größer als die Alterspensionen, die Prüfung muss das melden.
    assert {"jahr", "code", "geschlecht", "vorzeitig", "alter_gesamt"} == set(bericht["vorzeitig"][0])
    # Summen gehören nie in die Statistik, nur Blätter der beiden Klassifikationen stehen dort.
    zeile = conn.execute(
        """SELECT count(*) AS n FROM stat.stat_pensionen s
           WHERE EXISTS (SELECT 1 FROM stat.klass_versicherungstraeger k WHERE k.uebergeordnet = s.versicherungstraeger)
              OR EXISTS (SELECT 1 FROM stat.klass_pensionsart a WHERE a.uebergeordnet = s.pensionsart)"""
    ).fetchone()
    assert zeile is not None and zeile["n"] == 0
    assert "Geändert oder geglättet wird nichts" in pensionen.bericht_text(bericht)


@pytest.mark.parametrize("jahr", [2021, 2022])
def test_pva_vertauscht_die_geschlechter_nicht(conn: Verbindung, ordner: Path, jahr: int) -> None:
    # Fängt: ab 2022 stehen Frauen vor Männern. Wer Spalten von 2021 weiterverwendet, tauscht still, die Summen halten.
    pensionen.laden(conn, ordner)
    for art in ("ALTER", "WITWE", "SCHWER_APG"):
        assert _wert_in_db(conn, jahr, "PVA-ARB", art, "M") > _wert_in_db(conn, jahr, "PVA-ARB", art, "W")


def test_text_mit_tausenderpunkt_wird_zur_zahl(conn: Verbindung, ordner: Path) -> None:
    # Fängt: int('18.228') wirft, float('18.228') ergibt 18,228. Im Blatt steht der Wert als Text.
    pfad = ordner / "2025" / _dateiname(_format(conn, "BVAEB"), 2025)
    _aendern(pfad, lambda wb: wb["Pensionen"].__setitem__("C5", "18.228"))
    pensionen.laden(conn, ordner)
    assert _wert_in_db(conn, 2025, "BVAEB-EB", "GEM", "M") == 18228


@pytest.mark.parametrize("wert", ["18,228", "18.22", "n/a", None, -1, 3.5])
def test_keine_anzahl_bricht_ab(conn: Verbindung, ordner: Path, wert: object) -> None:
    # Fängt: ein Tippfehler in einer Zelle wird still zu 0 oder zu einer falschen Zahl.
    pfad = ordner / "2025" / _dateiname(_format(conn, "BVAEB"), 2025)
    _aendern(pfad, lambda wb: wb["Pensionen"].__setitem__("C5", wert))
    with pytest.raises(PensionFehler, match="keine Anzahl|negativ"):
        pensionen.laden(conn, ordner)
    assert _anzahl(conn) == 0


def test_fremdes_format_bricht_ab_und_laedt_nichts(conn: Verbindung, ordner: Path) -> None:
    # Fängt: ein neuer Formatbruch wird mit dem alten Parser gelesen und ergibt falsche Zahlen.
    pfad = ordner / "2023" / _dateiname(_format(conn, "SVS-AB-2023"), 2023)
    _aendern(pfad, lambda wb: wb["Daten"].__setitem__("H1", "Neue Spalte"))
    with pytest.raises(FormatUnbekannt, match="unbekanntes Format"):
        pensionen.laden(conn, ordner)
    assert _anzahl(conn) == 0


def test_altes_format_in_neuem_jahr_ist_ein_formatbruch(conn: Verbindung, ordner: Path) -> None:
    # Fängt: die PVA fällt 2023 auf das alte Layout zurück; der Fingerabdruck passt, die Gültigkeit nicht.
    alt = _format(conn, "PVA-BIS-2021")
    (ordner / "2023" / _dateiname(_format(conn, "PVA-AB-2022"), 2023)).unlink()
    datei_bauen(alt, 2023, ordner / "2023" / "PVA alt.xlsx")
    with pytest.raises(FormatUnbekannt, match="gilt für 2018 bis 2021"):
        pensionen.laden(conn, ordner)


def test_unbekannter_wert_und_falsches_jahr_brechen_ab(conn: Verbindung, ordner: Path) -> None:
    # Fängt: eine neue Sparte fällt still weg; eine Datei liegt im falschen Jahresordner.
    pfad = ordner / "2020" / _dateiname(_format(conn, "SVS-BIS-2022"), 2020)
    _aendern(pfad, lambda wb: wb["Daten"].__setitem__("B2", "XX"))
    with pytest.raises(PensionFehler, match="„XX“ hat keine Zuordnung"):
        pensionen.laden(conn, ordner)
    _aendern(pfad, lambda wb: wb["Daten"].__setitem__("B2", "GW"))
    _aendern(pfad, lambda wb: wb["Daten"].__setitem__("A2", 2021))
    with pytest.raises(PensionFehler, match="Das Jahr im Ordner ist 2020"):
        pensionen.laden(conn, ordner)


def test_fehlender_bereich_und_fehlende_datei_brechen_ab(conn: Verbindung, ordner: Path) -> None:
    # Fängt: eine Zeile oder eine ganze Datei fehlt, und die Summen über die Träger fallen unbemerkt zu klein aus.
    van = ordner / "2019" / _dateiname(_format(conn, "VAN"), 2019)
    van.unlink()
    with pytest.raises(PensionFehler, match="es fehlt VAN"):
        pensionen.laden(conn, ordner)
    datei_bauen(_format(conn, "VAN"), 2019, van)
    pva = ordner / "2022" / _dateiname(_format(conn, "PVA-AB-2022"), 2022)

    def zeile_weg(wb: Any) -> None:
        wb["Pensionsstand"].delete_rows(4)

    _aendern(pva, zeile_weg)
    with pytest.raises(PensionFehler, match="Werte fehlen"):
        pensionen.laden(conn, ordner)


def test_abweichende_summe_steht_im_bericht_und_sperrt_die_freigabe(conn: Verbindung, ordner: Path) -> None:
    # Fängt: eine gemeldete Summe wird nur gelesen und nie nachgerechnet.
    pfad = ordner / "2019" / _dateiname(_format(conn, "SVA"), 2019)
    _aendern(pfad, lambda wb: wb["Pensionsstand"].__setitem__("C2", 1))
    pensionen.laden(conn, ordner)
    bericht = pensionen.pruefbericht(conn)
    assert bericht["summen"]["abweichend"] == 1
    assert bericht["summen"]["abweichungen"][0]["zelle"] == "C2"
    assert "Abweichende Summen" in pensionen.bericht_text(bericht)
    with pytest.raises(PensionFehler, match="weichen ab"):
        pensionen.freigeben(conn, "Hanna Berger")


def test_doppellauf_gleicher_hash_und_freigabe_schuetzt(conn: Verbindung, ordner: Path) -> None:
    # Fängt: ein zweiter Lauf ändert Zahlen; eine neue Datei überschreibt still, was freigegeben ist (Technische Regel 1, 7).
    erst = pensionen.laden(conn, ordner)
    zweit = pensionen.laden(conn, ordner)
    assert zweit["unveraendert"] is True and zweit["ergebnis_hash"] == erst["ergebnis_hash"]

    with pytest.raises(NameUngueltig):
        pensionen.freigeben(conn, "Team")
    frei = pensionen.freigeben(conn, "Hanna Berger")
    assert frei["zellen"] == _anzahl(conn) and frei["regeln"] > 0
    zeile = conn.execute("SELECT DISTINCT status FROM stat.stat_pensionen").fetchone()
    assert zeile is not None and zeile["status"] == "endgueltig"
    assert pensionen.laden(conn, ordner)["unveraendert"] is True

    pfad = ordner / "2025" / _dateiname(_format(conn, "SVS-AB-2023"), 2025)
    _aendern(pfad, lambda wb: wb["Daten"].__setitem__("F2", 7))
    with pytest.raises(PensionFehler, match="Revisionsbedarf"):
        pensionen.laden(conn, ordner)


def test_regelstand_der_beschaeftigten_bleibt_gleich(conn: Verbindung) -> None:
    # Fängt: eine Pensionszeile rutscht in den Hash von v1. Dann gälten alle Läufe als veraltet und die Abgabe bräche.
    mit = regelstand(conn, regeln_laden(conn, "v1"))
    conn.execute("DELETE FROM stat.quellzuordnung WHERE regelsatz = %s", (pensionen.REGELSATZ,))
    conn.execute("DELETE FROM meta.regel WHERE regelsatz = %s", (pensionen.REGELSATZ,))
    assert regelstand(conn, regeln_laden(conn, "v1")) == mit


def test_traegergliederung_ist_getrennt_und_uebergang_steht_in_daten(conn: Verbindung, ordner: Path) -> None:
    # Fängt: PVA-ARB rutscht in die Qualifikation; die Fusionen stecken im Code statt in stat.uebergang (AC2).
    zeilen = conn.execute(
        """SELECT code_alt, code_neu FROM stat.uebergang
           WHERE klassifikation = 'versicherungstraeger' AND gueltig_ab = '2020-01-01'"""
    ).fetchall()
    paare = {(str(z["code_alt"]), str(z["code_neu"])) for z in zeilen}
    assert {("SVA", "SVS"), ("SVB", "SVS"), ("VAN", "SVS"), ("VAEB", "BVAEB"), ("BVA", "BVAEB")} <= paare
    pensionen.laden(conn, ordner)
    ue = pensionen.pruefbericht(conn)["uebergang"]
    gw = next(u for u in ue["zeilen"] if u["ziel"] == "SVS-GW" and u["tabelle"] == "T13")
    assert gw["ohne_meldung"] == "VAN" and "VAN" in gw["vorgaenger"]
    assert "nicht geglättet" in ue["annahme"]


def test_frage_nennt_die_zahl_aus_der_datenbank(conn: Verbindung, ordner: Path) -> None:
    # Fängt: die Antwort rechnet anders als die Tabelle; Tabelle 13 fließt in Tabelle 12 ein.
    pensionen.laden(conn, ordner)
    antwort = frage_modul.antwort_frage(conn, "Wie viele Alterspensionen von Frauen gab es 2025 bei der PVA?")
    summe = conn.execute(
        """SELECT sum(wert)::bigint AS n FROM stat.stat_pensionen WHERE zeitraum_von = '2025-01-01'
           AND pensionsart = 'ALTER' AND geschlecht = 'W' AND versicherungstraeger LIKE 'PVA-%'"""
    ).fetchone()
    assert summe is not None
    assert [z["wert"] for z in antwort["zahlen"]] == [summe["n"]]
    assert "stat.stat_pensionen" in antwort["belege"][0]["sql"]
    assert "vorläufig" in antwort["text"]
    assert set(frage_modul.als_webantwort(antwort)) == {*frage_modul.UC_FELDER, "definition", "rueckfrage"}

    gesamt = frage_modul.antwort_frage(conn, "Wie viele Pensionen gab es 2025?")["zahlen"][0]["wert"]
    t12 = conn.execute(
        """SELECT sum(s.wert)::bigint AS n FROM stat.stat_pensionen s
           JOIN stat.klass_pensionsart a ON a.code = s.pensionsart
           WHERE s.zeitraum_von = '2025-01-01' AND a.uebergeordnet = 'T12'"""
    ).fetchone()
    assert t12 is not None and gesamt == t12["n"]

    nach = frage_modul.antwort_frage(conn, "Pensionen 2019 nach Träger")["zahlen"]
    assert {z["bezeichnung"].split(", ", 1)[1] for z in nach} >= {"Pensionsversicherungsanstalt"}
    assert (
        sum(z["wert"] for z in nach) == frage_modul.antwort_frage(conn, "Pensionen 2019")["zahlen"][0]["wert"]
    )

    reihe = frage_modul.antwort_frage(conn, "Entwicklung der Pensionen seit 2018")["zahlen"]
    assert len(reihe) == 8

    # „vorzeitige Alterspensionen“ ist Tabelle 13, nicht zwei Arten; nach Art sind es deren fünf.
    arten = frage_modul.antwort_frage(conn, "Vorzeitige Alterspensionen 2024 nach Art")["zahlen"]
    assert len(arten) == 5


@pytest.mark.parametrize(
    "frage",
    [
        "Wie viele Pensionen gab es?",  # kein Jahr
        "Wie viele Pensionen hatte Wien 2025?",  # Merkmal, das es nicht gibt
        "Pensionen nach Alter und Bundesland 2025",
        "Wie viele Pensionen gab es 2017?",  # außerhalb
        "Pensionen im März 2025",  # kein Monatswert
        "Alterspensionen und Waisenpensionen 2025",  # zwei Arten
        "Vorzeitige Pensionen der VAN 2019",  # nicht gemeldet
        "Pensionen der SVS 2019",  # Träger gibt es noch nicht
        "Schwerarbeit Pensionen 2023",  # ASVG oder APG
        "Wie lange beziehen Pensionisten 2023",  # keine Anzahl
    ],
)
def test_frage_ohne_sicheren_sinn_nennt_keine_zahl(conn: Verbindung, ordner: Path, frage: str) -> None:
    # Fängt: eine Frage, die nicht verstanden ist, bekommt trotzdem die Gesamtzahl (!192, #176).
    pensionen.laden(conn, ordner)
    assert frage_modul.antwort_frage(conn, frage)["zahlen"] == []


def test_frage_vor_dem_laden_sagt_das(conn: Verbindung) -> None:
    # Fängt: die Abnahme-Datenbank ist bis zur Freigabe leer; die Antwort darf nicht „0 Pensionen“ lauten.
    antwort = frage_modul.antwort_frage(conn, "Wie viele Pensionen gab es 2025?")
    assert antwort["zahlen"] == [] and "noch nicht geladen" in antwort["text"]


def test_anhang_b_haelt_auch_mit_pensionsdaten(conn: Verbindung, ordner: Path) -> None:
    # Fängt: eine Summe oder ein Code ohne Klassifikation rutscht in stat_pensionen (B12 bis B15 sonst nur auf leer).
    pensionen.laden(conn, ordner)
    text = (Path(__file__).resolve().parents[2] / "docs" / "plan" / "uc3" / "anhang-b-schema.sql").read_text()
    ohne = "\n".join(z for z in text.splitlines() if not z.lstrip().startswith("--"))
    for abfrage in re.split(r";\s*\n", ohne):
        if re.search(r"'B1[2-5] ", abfrage):
            zeile = conn.execute(abfrage.encode()).fetchone()
            assert zeile is not None and zeile["fehlend"] == 0, zeile


def test_bericht_vor_dem_laden(conn: Verbindung) -> None:
    # Fängt: `uc3 pensionen pruefen` stürzt auf einer frischen Datenbank ab oder meldet einen leeren Erfolg.
    bericht = pensionen.pruefbericht(conn)
    assert bericht["ladung"]["dateien"] == 0 and bericht["ladung"]["dateien_soll"] == 28
    assert "noch keine Pensionszahlen" in pensionen.bericht_text(bericht)
    with pytest.raises(PensionFehler, match="keine Pensionszahlen"):
        pensionen.freigeben(conn, "Hanna Berger")


@pytest.mark.daten
def test_echte_dateien_aus_dem_startpaket(conn: Verbindung) -> None:
    # Fängt: die Regeln passen zu den Testdateien, aber nicht zu den 28 echten Meldungen.
    ordner = konfig.startpaket() / pensionen.PENSIONEN_ORDNER
    if not ordner.is_dir():
        pytest.fail(f"Startpaket-Ordner fehlt: {ordner}")
    daten = pensionen.laden(conn, ordner)
    assert daten["dateien"] == 28 and daten["werte"] == 880
    # Beispielzeile aus der Aufgabenstellung, Anhang B.
    assert _wert_in_db(conn, 2025, "PVA-ARB", "ALTER", "M") == 395763
    bericht = pensionen.pruefbericht(conn)
    assert bericht["summen"]["abweichend"] == 0 and bericht["vorzeitig"] == []
