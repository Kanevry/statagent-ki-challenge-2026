"""Lader für ÖNACE-Ebenen 2 bis 5, Regionen je Stand und Gemeindeänderungen (klass_quellen).

Parser-Tests mit kleinen erfundenen Dateien in tmp_path, dazu ein Test gegen die Wegwerf-Datenbank.
"""

from __future__ import annotations

import zipfile
from datetime import date
from pathlib import Path

import pytest

from statagent import konfig
from statagent.db import Verbindung
from statagent.klass_quellen import (
    BEZIRK,
    GEMEINDE,
    aenderungen_lesen,
    klassifikationen_einrichten,
    ods_lesen,
    oenace_lesen,
    regionen_lesen,
    staende,
    uebergaenge_bilden,
)

CTI = """"Ebene";"EDV-Code";"Code";"Titel";"Kurztitel"
1;"A";"A";"LAND- UND FORSTWIRTSCHAFT";"Land"
2;"A01";"A 01";"Landwirtschaft";"Landw."
3;"A011";"A 01.1";"Anbau einjähriger Pflanzen";"Anbau"
4;"A0111";"A 01.11";"Anbau von Getreide";"Getreide"
5;"A01110";"A 01.11-0";"Anbau von Getreide";"Getreide"
4;"A0112";"A 01.12";"Anbau von Reis";"Reis"
5;"A01120";"A 01.12-0";"Anbau von Reis";"Reis"
1;"B";"B";"BERGBAU";"Bergbau"
2;"B05";"B 05";"Kohlenbergbau";"Kohle"
"""

# Erfundene Gliederung: Bezirk 101 nimmt 2012 die Gemeinde 10201 auf (Bezirk 102 wird aufgelöst),
# Gemeinden 10101 und 10102 werden 2012 zu 10103, 10104 wird 2012 auf 10105 und 10106 geteilt.
BEZIRKE = {
    "2011-01-01": ["101;Nordbezirk;1;Burgenland", "102;Südbezirk;1;Burgenland"],
    "2012-01-01": ["101;Nordbezirk;1;Burgenland"],
}
GEMEINDEN = {
    "2011-01-01": ["10101;Ahof;101", "10102;Bdorf;101", "10104;Cberg;101", "10201;Dtal;102", "10107;Eau;101"],
    "2012-01-01": ["10103;Ahof-Bdorf;101", "10105;Cberg-Ost;101", "10106;Cberg-West;101", "10108;Dtal;101",
                   "10107;Eau am See;101"],
}  # fmt: skip


def _ods_zelle(wert: str, wiederholt: int = 1) -> str:
    attr = f' table:number-columns-repeated="{wiederholt}"' if wiederholt > 1 else ""
    return (
        f"<table:table-cell{attr}><text:p>{wert}</text:p></table:table-cell>"
        if wert
        else (f"<table:table-cell{attr}/>")
    )


def _ods_blatt(name: str, zeilen: list[list[str]]) -> str:
    teile = [
        f'<table:table table:name="{name}">',
        "<table:table-row>" + _ods_zelle("Titel") + "</table:table-row>",
    ]
    for z in zeilen:
        teile.append(
            "<table:table-row>"
            + "".join(_ods_zelle(w) for w in z)
            + _ods_zelle("", 1000)
            + "</table:table-row>"
        )
    teile.append(
        '<table:table-row table:number-rows-repeated="1000">' + _ods_zelle("", 50) + "</table:table-row>"
    )
    teile.append("</table:table>")
    return "".join(teile)


def _ods_schreiben(datei: Path) -> None:
    kraft = "01.01.2012"
    blaetter = [
        _ods_blatt("alle_GKZaenderungen", [
            ["Gemeindekennziffer alt", "Gemeinde alt", "Gemeindekennziffer neu", "Gemeinde neu", "in Kraft seit",
             "Änderungsgrund"],
            ["10101", "Ahof", "10103", "Ahof-Bdorf", kraft, "Zusammenlegung"],
            ["10102", "Bdorf", "10103", "Ahof-Bdorf", kraft, "Zusammenlegung"],
            ["10104", "Cberg", "10105", "Cberg-Ost", kraft, "Teilung"],
            ["10104", "Cberg", "10106", "Cberg-West", kraft, "Teilung"],
            ["10201", "Dtal", "10108", "Dtal", kraft, "Bezirkszusammenlegung"],
            ["90001", "Alt", "90002", "Alt", "01.01.2005", "Zusammenlegung"],
            ["Q: erfunden"],
        ]),
        _ods_blatt("Zusammenlegungen", [
            ["Gemeindekennziffer neu", "Gemeindename neu", "Gemeindekennziffer alt", "Gemeindename alt",
             "Politischer Bezirk", "in Kraft seit", "Gesetzliche bzw. amtliche Grundlagen"],
            ["10103", "Ahof-Bdorf", "10101", "Ahof", "Nordbezirk", kraft, "LGBl. Nr. 1/2011"],
            ["10103", "Ahof-Bdorf", "10102", "Bdorf", "Nordbezirk", kraft, "LGBl. Nr. 1/2011"],
        ]),
        _ods_blatt("Teilungen", [
            ["Gemeindekennziffer neu", "Gemeindename neu", "Gemeindekennziffer alt", "Gemeindename alt",
             "Politischer Bezirk", "in Kraft seit", "Gesetzliche bzw. amtliche Grundlagen"],
            ["10105", "Cberg-Ost", "10104", "Cberg", "Nordbezirk", kraft, "LGBl. Nr. 2/2011"],
            ["10106", "Cberg-West", "10104", "Cberg", "Nordbezirk", kraft, "LGBl. Nr. 2/2011"],
        ]),
        _ods_blatt("Bezirkszusammenlegungen", [
            ["Gemeindekennziffer neu", "Gemeindename", "Politischer Bezirk neu", "Gemeindekennziffer alt",
             "Politischer Bezirk alt", "in Kraft seit"],
            ["10108", "Dtal", "Nordbezirk", "10201", "Südbezirk", kraft],
        ]),
        _ods_blatt("Namensaenderungen", [
            ["Gemeindekennziffer", "Gemeindename alt", "Gemeindename neu", "Politischen Bezirk", "in Kraft seit",
             "Gesetzliche bzw. amtliche Grundlagen"],
            ["10107", "Eau", "Eau am See", "Nordbezirk", "01.06.2011", "LGBl. Nr. 3/2011"],
            ["10107", "Eau alt", "Eau", "Nordbezirk", "01.06.2003", "LGBl. Nr. 3/2003"],
        ]),
        _ods_blatt("Statusaenderungen", [
            ["Gemeindekennziffer", "Gemeindename", "Politischen Bezirk", "Status neu", "in Kraft seit",
             "Gesetzliche bzw. amtliche Grundlagen"],
            ["10107", "Eau am See", "Nordbezirk", "Markt", "01.07.2011", "LGBl. Nr. 4/2011"],
        ]),
    ]  # fmt: skip
    inhalt = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<office:document-content xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0" '
        'xmlns:table="urn:oasis:names:tc:opendocument:xmlns:table:1.0" '
        'xmlns:text="urn:oasis:names:tc:opendocument:xmlns:text:1.0"><office:body><office:spreadsheet>'
        + "".join(blaetter)
        + "</office:spreadsheet></office:body></office:document-content>"
    )
    with zipfile.ZipFile(datei, "w") as z:
        z.writestr("mimetype", "application/vnd.oasis.opendocument.spreadsheet")
        z.writestr("content.xml", inhalt)


@pytest.fixture
def startpaket(tmp_path: Path) -> Path:
    klass = tmp_path / "klassifikationen"
    (klass / "oenace").mkdir(parents=True)
    (klass / "oenace" / "OENACE2008_DE_CTI.txt").write_bytes(CTI.encode("cp1252"))
    regionen = klass / "regionen"
    (regionen / "Änderungen").mkdir(parents=True)  # Ordnername NFD wie im Startpaket
    for stand, zeilen in BEZIRKE.items():
        text = "BEZIRK_CODE;BEZIRK;BUNDESLAND_CODE;BUNDESLAND\r\n" + "\r\n".join(zeilen) + "\r\n"
        (regionen / f"bezirke_{stand}.csv").write_text(text, encoding="utf-8")
    for stand, zeilen in GEMEINDEN.items():
        kopf = "GEMEINDE_CODE;GEMEINDE;BEZIRK_CODE;BEZIRK;BUNDESLAND_CODE;BUNDESLAND\r\n"
        text = kopf + "".join(f"{z};Nordbezirk;1;Burgenland\r\n" for z in zeilen)
        (regionen / f"gemeinden_{stand}.csv").write_text(text, encoding="utf-8")
    _ods_schreiben(regionen / "Änderungen" / "aenderungenGemeinden_ab2002.ods")
    return tmp_path


def _bestand(regionen_ordner: Path) -> dict[tuple[str, str], set[str]]:
    bestand: dict[tuple[str, str], set[str]] = {}
    for r in regionen_lesen(regionen_ordner):
        bestand.setdefault((r.version, r.ebene), set()).add(r.code)
    return bestand


def test_oenace_ebenen_und_uebergeordnet(startpaket: Path) -> None:
    zeilen = oenace_lesen(startpaket / "klassifikationen" / "oenace" / "OENACE2008_DE_CTI.txt")
    nach_code = {z.code: z for z in zeilen}
    assert {z.ebene for z in zeilen} == {1, 2, 3, 4, 5}
    assert all(z.version == "2008" for z in zeilen)
    assert nach_code["A"].uebergeordnet is None
    assert nach_code["A 01"].uebergeordnet == "A"
    assert nach_code["A 01.1"].uebergeordnet == "A 01"
    assert nach_code["A 01.12"].uebergeordnet == "A 01.1"
    assert nach_code["A 01.12-0"].uebergeordnet == "A 01.12"
    assert nach_code["B 05"].uebergeordnet == "B"  # nach Abschnitt B nicht mehr unter A
    assert nach_code["A 01.1"].bezeichnung == "Anbau einjähriger Pflanzen"  # cp1252 richtig gelesen


def test_regionen_je_stand_mit_gueltigkeit(startpaket: Path) -> None:
    ordner = startpaket / "klassifikationen" / "regionen"
    assert staende(ordner) == [date(2011, 1, 1), date(2012, 1, 1)]
    zeilen = {(z.version, z.code): z for z in regionen_lesen(ordner)}
    bezirk = zeilen[("2011-01-01", "102")]
    assert (bezirk.ebene, bezirk.uebergeordnet) == (BEZIRK, "1")
    assert (bezirk.gueltig_von, bezirk.gueltig_bis) == (date(2011, 1, 1), date(2011, 12, 31))
    gemeinde = zeilen[("2012-01-01", "10108")]
    assert (gemeinde.ebene, gemeinde.uebergeordnet, gemeinde.bezeichnung) == (GEMEINDE, "101", "Dtal")
    assert (gemeinde.gueltig_von, gemeinde.gueltig_bis) == (date(2012, 1, 1), None)
    assert ("2012-01-01", "102") not in zeilen


def test_ods_leser_wiederholte_zellen(startpaket: Path) -> None:
    datei = next((startpaket / "klassifikationen" / "regionen").glob("*/aenderungenGemeinden_ab2002.ods"))
    blaetter = ods_lesen(datei)
    assert set(blaetter) >= {"alle_GKZaenderungen", "Teilungen", "Statusaenderungen"}
    # Leere wiederholte Zeilen und Zellen am Ende fallen weg.
    assert len(blaetter["Teilungen"]) == 4
    assert blaetter["Teilungen"][2] == ["10105", "Cberg-Ost", "10104", "Cberg", "Nordbezirk", "01.01.2012",
                                        "LGBl. Nr. 2/2011"]  # fmt: skip


def test_uebergaenge_beziehungen_und_versionen(startpaket: Path) -> None:
    ordner = startpaket / "klassifikationen" / "regionen"
    liste = aenderungen_lesen(next(ordner.glob("*/aenderungenGemeinden_ab2002.ods")))
    assert liste.nicht_verwendet["Statusaenderungen"] == 1
    ue = uebergaenge_bilden(liste.aenderungen, staende(ordner), _bestand(ordner))
    paare = {(z["klassifikation"], z["code_alt"], z["code_neu"]): z for z in ue.zeilen}

    zusammen = paare[(GEMEINDE, "10101", "10103")]
    assert zusammen["beziehung"] == "n:1"
    assert (zusammen["version_alt"], zusammen["version_neu"]) == ("2011-01-01", "2012-01-01")
    assert zusammen["gueltig_ab"] == date(2012, 1, 1)
    assert "alle_GKZaenderungen (Zusammenlegung)" in str(zusammen["quelle"])
    assert "Zusammenlegungen (LGBl. Nr. 1/2011)" in str(zusammen["quelle"])
    assert paare[(GEMEINDE, "10104", "10105")]["beziehung"] == "1:n"
    assert paare[(GEMEINDE, "10104", "10106")]["beziehung"] == "1:n"
    assert paare[(GEMEINDE, "10201", "10108")]["beziehung"] == "1:1"
    # Namensänderung am 1.6.2011: Stand 2011 davor, Stand 2012 danach, gleicher Code.
    name = paare[(GEMEINDE, "10107", "10107")]
    assert (name["beziehung"], name["version_alt"], name["version_neu"]) == (
        "1:1",
        "2011-01-01",
        "2012-01-01",
    )
    # Bezirk 102 geht in 101 auf; 101 besteht weiter und nimmt Gebiet auf.
    assert paare[(BEZIRK, "102", "101")]["beziehung"] == "n:1"
    assert paare[(BEZIRK, "101", "101")]["beziehung"] == "n:1"
    # Vor dem ersten Stand: nicht geladen, aber gezählt.
    assert ("gemeinde", "90001", "90002") not in paare
    assert ue.ausserhalb == {"alle_GKZaenderungen": 1, "Namensaenderungen": 1}
    assert ue.nicht_im_stand == 0


def _oenace_gueltigkeiten(conn: Verbindung, nur_alt: bool) -> list[tuple[str, str, str]]:
    bedingung = "WHERE NOT (version IN ('2008', '2025') AND ebene >= 2)" if nur_alt else ""
    zeilen = conn.execute(
        f"SELECT DISTINCT version, gueltig_von::text AS von, coalesce(gueltig_bis::text, '') AS bis "
        f"FROM stat.klass_oenace {bedingung} ORDER BY 1, 2, 3"
    ).fetchall()
    return [(str(z["version"]), str(z["von"]), str(z["bis"])) for z in zeilen]


def test_laden_in_datenbank_idempotent(conn: Verbindung, startpaket: Path) -> None:
    vorher = _oenace_gueltigkeiten(conn, nur_alt=True)
    text = klassifikationen_einrichten(conn, startpaket)
    assert "ÖNACE 2008 Ebene 2: 2, Ebene 3: 1, Ebene 4: 2, Ebene 5: 2" in text
    assert "Hinweis" not in text
    klassifikationen_einrichten(conn, startpaket)  # zweiter Lauf ändert nichts

    assert _oenace_gueltigkeiten(conn, nur_alt=False) == vorher  # keine neue Version, Regelstand gleich
    ebene1 = conn.execute(
        "SELECT bezeichnung FROM stat.klass_oenace WHERE version = '2008' AND code = 'A'"
    ).fetchone()
    assert ebene1 is not None and ebene1["bezeichnung"] != "LAND- UND FORSTWIRTSCHAFT"  # Ebene 1 unverändert
    z = conn.execute(
        "SELECT ebene, uebergeordnet, gueltig_von, gueltig_bis FROM stat.klass_oenace "
        "WHERE version = '2008' AND code = 'A 01.11-0'"
    ).fetchone()
    assert z is not None
    assert (z["ebene"], z["uebergeordnet"], z["gueltig_von"], z["gueltig_bis"]) == (
        5,
        "A 01.11",
        date(2008, 1, 1),
        date(2024, 12, 31),
    )
    regionen = conn.execute(
        "SELECT version, ebene, count(*) AS n FROM stat.klass_region GROUP BY 1, 2 ORDER BY 1, 2"
    ).fetchall()
    assert {(r["version"], r["ebene"]): r["n"] for r in regionen} == {
        ("2011-01-01", "bezirk"): 2, ("2011-01-01", "gemeinde"): 5,
        ("2012-01-01", "bezirk"): 1, ("2012-01-01", "gemeinde"): 5,
        ("BL", "bundesland"): 10, ("BL", "staat"): 1,
    }  # fmt: skip
    ue = conn.execute(
        "SELECT klassifikation, count(*) AS n FROM stat.uebergang WHERE klassifikation IN ('gemeinde', 'bezirk') "
        "GROUP BY 1 ORDER BY 1"
    ).fetchall()
    assert {r["klassifikation"]: r["n"] for r in ue} == {"bezirk": 2, "gemeinde": 6}


def test_schema_einrichten_mit_startpaket(conn: Verbindung) -> None:
    """Mit dem echten Startpaket (falls vorhanden) stehen nach schema_einrichten alle ÖNACE-Ebenen bereit."""
    if not (konfig.startpaket() / "klassifikationen" / "oenace" / "OENACE2008_DE_CTI.txt").is_file():
        pytest.skip("Startpaket mit Klassifikationen nicht vorhanden")
    zeilen = conn.execute(
        "SELECT version, ebene, count(*) AS n FROM stat.klass_oenace WHERE version IN ('2008', '2025') "
        "GROUP BY 1, 2"
    ).fetchall()
    ebenen = {(z["version"], z["ebene"]) for z in zeilen}
    assert {(v, e) for v in ("2008", "2025") for e in range(1, 6)} <= ebenen
    assert _oenace_gueltigkeiten(conn, nur_alt=False) == _oenace_gueltigkeiten(conn, nur_alt=True)
