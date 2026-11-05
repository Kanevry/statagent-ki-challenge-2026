"""`uc3 klass` (#75): Umsteiger ÖNACE 2008 → 2025 lesen und laden, Code erklären.

Der Umsteiger hier ist ein erfundener Ausschnitt im Format 12B des Startpakets (Windows-1252, Semikolon,
Anführungszeichen), nicht die Datei des Veranstalters.
"""

from __future__ import annotations

from pathlib import Path

from statagent.db import Verbindung
from statagent.klass import (
    UNTERKLASSE,
    erklaeren,
    text,
    umsteiger_einrichten,
    umsteiger_laden,
    umsteiger_uebergaenge,
)

KOPF = (
    '"Ebene";"EDV-Code";"Code";"Titel";"korrespondierende Ebene";"korrespondierender EDV-Code";'
    '"korrespondierender Code";"korrespondierender Titel";"Korrespondenz-Beschreibung"'
)
ZEILEN = [
    # Gesundheit: 2008 Q, 2025 R. Erziehung: 2008 P, 2025 Q.
    '5;"Q86100";"Q 86.10-0";"Krankenhäuser";5;"R86100";"R 86.10-0";"Krankenhäuser";"Alle Tätigkeiten"',
    '5;"Q86210";"Q 86.21-0";"Arztpraxen";5;"R86210";"R 86.21-0";"Arztpraxen";"Alle Tätigkeiten"',
    '5;"P85100";"P 85.10-0";"Kindergärten";5;"Q85100";"Q 85.10-0";"Kindergärten";"Alle Tätigkeiten"',
    # Eine Unterklasse teilt sich auf zwei Abschnitte; Semikolon im Text steht in Anführungszeichen.
    '5;"P85520";"P 85.52-0";"Kulturunterricht";5;"Q85520";"Q 85.52-0";"Kulturunterricht";"Musik; Tanz"',
    '5;"P85520";"P 85.52-0";"Kulturunterricht";5;"S93290";"S 93.29-0";"Freizeit";"Freizeitkurse"',
]


def _umsteiger(ordner: Path) -> Path:
    datei = ordner / "OENACE2008_OENACE2025_DE_12B.txt"
    datei.write_bytes(("\r\n".join([KOPF, *ZEILEN]) + "\r\n").encode("cp1252"))
    return datei


def _abschnitte(zeilen: list[dict[str, str]]) -> dict[tuple[str, str], dict[str, str]]:
    return {(z["code_alt"], z["code_neu"]): z for z in zeilen if z["klassifikation"] == "oenace"}


def test_umsteiger_abschnitte_mit_anteil_und_beziehung(tmp_path: Path) -> None:
    """Fängt: Semikolon in Anführungszeichen zerreißt die Zeile, oder der Abschnitt-Anteil/die Beziehung
    wird falsch gezählt (P geht teils nach S, also 1:n mit 1 von 2 Unterklassen)."""
    zeilen, alt, neu = umsteiger_uebergaenge(_umsteiger(tmp_path))
    assert (alt, neu) == ("2008", "2025")
    abschnitte = _abschnitte(zeilen)
    assert set(abschnitte) == {("Q", "R"), ("P", "Q"), ("P", "S")}
    assert abschnitte[("Q", "R")]["beziehung"] == "1:1"
    assert "2 von 2 Unterklassen" in abschnitte[("Q", "R")]["quelle"]
    assert abschnitte[("P", "S")]["beziehung"] == "1:n"
    assert "1 von 2 Unterklassen" in abschnitte[("P", "S")]["quelle"]
    unterklasse = {(z["code_alt"], z["code_neu"]): z for z in zeilen if z["klassifikation"] == UNTERKLASSE}
    assert unterklasse[("P 85.52-0", "Q 85.52-0")]["quelle"].endswith("Musik; Tanz")


def test_umsteiger_laden_idempotent_und_erklaerung(conn: Verbindung, tmp_path: Path) -> None:
    """Fängt: doppeltes Laden bei jedem `db init` (kein ON CONFLICT), Abbruch ohne Datei, und eine Anzeige,
    die Gesundheit 2025 wieder unter Q statt unter R führt."""
    assert umsteiger_einrichten(conn, tmp_path / "leer").startswith("Hinweis:")
    datei = _umsteiger(tmp_path)
    with conn.transaction():
        umsteiger_laden(conn, datei)
    vorher = conn.execute("SELECT count(*) AS n FROM stat.uebergang").fetchone()
    with conn.transaction():
        umsteiger_laden(conn, datei)
    assert conn.execute("SELECT count(*) AS n FROM stat.uebergang").fetchone() == vorher

    daten = erklaeren(conn, "oenace", "q", version="2008", unterklassen=5)
    ziele = {(u["code_alt"], u["code_neu"]): u for u in daten["uebergaenge"] if u["version_neu"] == "2025"}
    assert ziele[("Q", "R")]["bezeichnung_neu"] == "Gesundheits- und Sozialwesen"
    assert ziele[("Q", "R")]["gueltig_ab"].isoformat() == "2025-01-01"
    assert any(u["code_alt"] == "Q 86.10-0" for u in daten["unterklassen"])
    ausgabe = text(daten)
    assert "zu ÖNACE 2025 Gesundheits- und Sozialwesen (R)" in ausgabe
    assert "—" not in ausgabe


def test_code_c_zeigt_altcodes_aus_quellzuordnung(conn: Verbindung) -> None:
    """Fängt: Quellzuordnungen (DA bis DN über Regel Q01) fehlen in der Erklärung von C, oder ohne
    veröffentlichten Monat bricht die Erklärung ab statt es zu sagen."""
    daten = erklaeren(conn, "oenace", "C")
    q01 = [q for q in daten["quellzuordnungen"] if q["regel"] == "Q01_oenace_2003_unterabschnitte"]
    assert {q["geliefert"] for q in q01} >= {"DA", "DN"}
    versionen = {u["version_alt"] for u in daten["uebergaenge"]}
    assert "2003" in versionen
    # 2008 → 2025 kommt aus dem Umsteiger im Startpaket; der fehlt in der CI (dort nur der Hinweis).
    umsteiger = conn.execute(
        "SELECT count(*) AS n FROM stat.uebergang WHERE klassifikation = 'oenace' AND version_alt = '2008'"
    ).fetchone()
    if umsteiger is not None and int(str(umsteiger["n"])) > 0:
        assert "2008" in versionen
    if daten["verhaeltnisse"] is None:
        assert "noch keinen veröffentlichten Monat" in text(daten)


# --- Tiefe Ebenen (Bewertungsbereich 2): ÖNACE bis zur Unterklasse, Bezirke und Gemeinden je Stand ---------
# Zeilen nach dem Vertrag des Laders. Codes und Namen der Gemeinden 622xx sind erfunden.

QUELLE_GEMEINDEN = "Gemeindeänderungen ab 1945 (erfundener Ausschnitt)"


def tiefe_zeilen_entfernen(conn: Verbindung) -> None:
    """Entfernt im Test-Klon, was der Lader aus einem lokalen Startpaket schon geladen hat (in der CI nichts)."""
    with conn.transaction():
        conn.execute("DELETE FROM stat.klass_oenace WHERE ebene > 1 AND code LIKE '% %'")
        conn.execute("DELETE FROM stat.klass_region WHERE ebene IN ('bezirk', 'gemeinde')")
        conn.execute(
            "DELETE FROM stat.uebergang WHERE klassifikation IN (%s, 'bezirk', 'gemeinde')", (UNTERKLASSE,)
        )


def tiefe_zeilen_einfuegen(conn: Verbindung) -> None:
    """ÖNACE-Ebenen 2 bis 5 für 2008 und 2025, drei Stände mit Bezirken und Gemeinden, ihre Übergänge.

    Vorher wird entfernt, was ein lokales Startpaket schon geladen hat; die Tests sehen nur diese Zeilen."""
    tiefe_zeilen_entfernen(conn)
    oenace = [
        ("C", "C 10", "Herstellung von Nahrungs- und Futtermitteln", 2),
        ("C 10", "C 10.1", "Schlachten und Fleischverarbeitung", 3),
        ("C 10.1", "C 10.11", "Schlachten (ohne Geflügel)", 4),
        ("C 10.11", "C 10.11-0", "Schlachten (ohne Geflügel)", 5),
        ("C 10.1", "C 10.12", "Schlachten von Geflügel", 4),
        ("C 10.12", "C 10.12-0", "Schlachten von Geflügel", 5),
    ]
    gesundheit = {
        "2008": [("Q", "Q 86", "Gesundheitswesen", 2), ("Q 86", "Q 86.1", "Krankenhäuser", 3),
                 ("Q 86.1", "Q 86.10", "Krankenhäuser", 4), ("Q 86.10", "Q 86.10-0", "Krankenhäuser", 5)],
        "2025": [("R", "R 86", "Gesundheitswesen", 2), ("R 86", "R 86.1", "Krankenhäuser", 3),
                 ("R 86.1", "R 86.10", "Krankenhäuser", 4), ("R 86.10", "R 86.10-0", "Krankenhäuser", 5)],
    }  # fmt: skip
    gueltig = {"2008": ("2008-01-01", "2024-12-31"), "2025": ("2025-01-01", None)}
    with conn.transaction(), conn.cursor() as cur:
        for version, (von, bis) in gueltig.items():
            cur.executemany(
                """INSERT INTO stat.klass_oenace (version, code, bezeichnung, ebene, uebergeordnet, gueltig_von,
                     gueltig_bis) VALUES (%s, %s, %s, %s, %s, %s, %s)""",
                [(version, c, t, e, o, von, bis) for o, c, t, e in [*oenace, *gesundheit[version]]],
            )
        staende = [("2014-01-01", "2014-12-31"), ("2015-01-01", "2015-12-31"), ("2016-01-01", None)]
        for stand, bis in staende:
            gemeinden = [("10101", "Eisenstadt", "101")]
            gemeinden += (
                [("62201", "Altdorf", "622"), ("62202", "Neudorf", "622")]
                if stand == "2014-01-01"
                else [("62240", "Zusammendorf", "622")]
            )
            zeilen = [
                ("101", "Eisenstadt (Stadt)", "bezirk", "1"),
                ("622", "Weiz" if stand < "2016" else "Weiz-Land", "bezirk", "6"),
                *[(c, n, "gemeinde", o) for c, n, o in gemeinden],
            ]
            cur.executemany(
                """INSERT INTO stat.klass_region (version, code, bezeichnung, ebene, uebergeordnet, gueltig_von,
                     gueltig_bis) VALUES (%s, %s, %s, %s, %s, %s, %s)""",
                [(stand, c, n, e, o, stand, bis) for c, n, e, o in zeilen],
            )
        cur.executemany(
            """INSERT INTO stat.uebergang (klassifikation, version_alt, code_alt, version_neu, code_neu, beziehung,
                 gueltig_ab, quelle) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""",
            [
                (
                    UNTERKLASSE,
                    "2008",
                    "C 10.11-0",
                    "2025",
                    "C 10.11-0",
                    "1:1",
                    "2025-01-01",
                    "Umsteiger: alle",
                ),
                (
                    UNTERKLASSE,
                    "2008",
                    "C 10.12-0",
                    "2025",
                    "C 10.12-0",
                    "1:1",
                    "2025-01-01",
                    "Umsteiger: alle",
                ),
                (
                    UNTERKLASSE,
                    "2008",
                    "Q 86.10-0",
                    "2025",
                    "R 86.10-0",
                    "1:1",
                    "2025-01-01",
                    "Umsteiger: alle",
                ),
                (
                    "gemeinde",
                    "2014-01-01",
                    "62201",
                    "2015-01-01",
                    "62240",
                    "n:1",
                    "2015-01-01",
                    QUELLE_GEMEINDEN,
                ),
                (
                    "gemeinde",
                    "2014-01-01",
                    "62202",
                    "2015-01-01",
                    "62240",
                    "n:1",
                    "2015-01-01",
                    QUELLE_GEMEINDEN,
                ),
            ],
        )


def test_unterklasse_mit_ebene_pfad_und_uebergang(conn: Verbindung) -> None:
    """Fängt: ein Code unter dem Abschnitt wird nicht gefunden (Schreibweise ohne Leerzeichen oder ohne
    Buchstaben), Ebene oder Pfad fehlen, oder der Übergang 2008 zu 2025 kommt nicht aus oenace_unterklasse."""
    tiefe_zeilen_einfuegen(conn)
    daten = erklaeren(conn, "oenace", "C 10.11-0")
    assert erklaeren(conn, "oenace", "c10.11-0")["bezeichnungen"] == daten["bezeichnungen"]
    assert erklaeren(conn, "oenace", "10.11-0")["bezeichnungen"] == daten["bezeichnungen"]
    assert daten["ebene_name"] == "Unterklasse"
    assert [n["version"] for n in daten["bezeichnungen"]] == ["2008", "2025"]
    pfad = daten["bezeichnungen"][1]["pfad"]
    assert [(p["ebene_name"], p["code"]) for p in pfad] == [
        ("Abschnitt", "C"), ("Abteilung", "C 10"), ("Gruppe", "C 10.1"), ("Klasse", "C 10.11")
    ]  # fmt: skip
    assert [(u["code_alt"], u["code_neu"]) for u in daten["uebergaenge"]] == [("C 10.11-0", "C 10.11-0")]
    assert daten["verhaeltnisse"] is None and daten["gezaehlt_nach"] == "Abschnitt"
    ausgabe = text(daten)
    assert "Code (C 10.11-0), Unterklasse" in ausgabe
    assert "gehört zu: Klasse Schlachten (ohne Geflügel) (C 10.11), Gruppe" in ausgabe
    assert "Abschnitt Herstellung von Waren (C)" in ausgabe
    assert "Die Statistik zählt nach Abschnitt, nicht nach Unterklasse" in ausgabe
    assert "—" not in ausgabe

    # Gesundheit wechselt den Abschnitt: (Q 86.10-0) wird (R 86.10-0); 86.10-0 findet beide.
    beide = erklaeren(conn, "oenace", "86.10-0")
    assert beide["codes"] == ["Q 86.10-0", "R 86.10-0"]
    assert "zu ÖNACE 2025 Krankenhäuser (R 86.10-0), Beziehung 1:1" in text(beide)

    gruppe = erklaeren(conn, "oenace", "C 10.1", version="2008")
    assert gruppe["ebene_name"] == "Gruppe"
    assert {u["code_alt"] for u in gruppe["uebergaenge"]} == {"C 10.11-0", "C 10.12-0"}


def test_oenace_liste_zaehlt_je_ebene(conn: Verbindung) -> None:
    """Fängt: die Liste ohne Code zeigt plötzlich alle Ebenen statt der Abschnitte, oder --ebene wirkt nicht."""
    tiefe_zeilen_entfernen(conn)
    vorher = erklaeren(conn, "oenace", version="2025")["versionen"][0]["codes"]
    tiefe_zeilen_einfuegen(conn)
    liste = erklaeren(conn, "oenace", version="2025")
    v = liste["versionen"][0]
    assert v["codes"] == vorher
    je = {e["name"]: e["anzahl"] for e in v["je_ebene"]}
    assert je["Unterklassen"] == 3 and je["Abschnitte"] == len(vorher)
    assert "Codes je Ebene: Abschnitte" in text(liste)
    fuenf = erklaeren(conn, "oenace", version="2025", ebene=5)
    assert [c["code"] for c in fuenf["versionen"][0]["codes"]] == ["C 10.11-0", "C 10.12-0", "R 86.10-0"]
    assert "davon 3 Unterklassen:" in text(fuenf)
    alt = erklaeren(conn, "oenace", version="2003")["versionen"][0]["je_ebene"]
    assert {e["name"] for e in alt} == {"Abschnitte", "Unterabschnitte"}


def test_gemeinde_ueber_alle_staende_mit_uebergang(conn: Verbindung) -> None:
    """Fängt: eine Gemeinde erscheint je Stand einzeln statt als Zeitraum, Bezirk oder Bundesland fehlen, oder
    die Zusammenlegung aus stat.uebergang (gemeinde) fehlt."""
    tiefe_zeilen_einfuegen(conn)
    eisenstadt = erklaeren(conn, "region", "10101")
    assert eisenstadt["ebene_name"] == "Gemeinde"
    assert len(eisenstadt["bezeichnungen"]) == 3
    assert len(eisenstadt["zeitraeume"]) == 1
    ausgabe = text(eisenstadt)
    assert (
        "gültig ab 01.01.2014: Eisenstadt (10101), Bezirk Eisenstadt (Stadt) (101), Bundesland Burgenland (1)"
        in (ausgabe)
    )
    assert "Die Statistik zählt nach Bundesland, nicht nach Gemeinde" in ausgabe

    neu = erklaeren(conn, "region", "62240")
    assert [(u["code_alt"], u["beziehung"]) for u in neu["uebergaenge"]] == [
        ("62201", "n:1"),
        ("62202", "n:1"),
    ]
    ausgabe = text(neu)
    assert (
        "Stand 01.01.2014 (62201), (62202) werden ab 01.01.2015 zu Stand 01.01.2015 Zusammendorf (62240)"
        in ausgabe
    )
    assert QUELLE_GEMEINDEN in ausgabe
    # Der Bezirk heißt ab 2016 anders: zwei Zeiträume, Name je Zeitraum.
    weiz = erklaeren(conn, "region", "622")
    assert [r["bezeichnung"] for r in weiz["zeitraeume"]] == ["Weiz", "Weiz-Land"]


def test_region_liste_bleibt_bei_bundeslaendern_und_zaehlt_staende(conn: Verbindung) -> None:
    """Fängt: Bezirke und Gemeinden fließen in die Liste der Bundesländer, oder die Stände fehlen."""
    tiefe_zeilen_entfernen(conn)
    vorher = erklaeren(conn, "region")["versionen"]
    tiefe_zeilen_einfuegen(conn)
    liste = erklaeren(conn, "region")
    assert [{k: v[k] for k in ("version", "anzahl", "codes")} for v in liste["versionen"]] == [
        {k: v[k] for k in ("version", "anzahl", "codes")} for v in vorher
    ]
    assert [(s["version"], s["bezirke"], s["gemeinden"]) for s in liste["staende"]] == [
        ("2014-01-01", 2, 3), ("2015-01-01", 2, 2), ("2016-01-01", 2, 2)
    ]  # fmt: skip
    assert "- Stand 01.01.2014, gültig 01.01.2014 bis 31.12.2014: 2 Bezirke, 3 Gemeinden" in text(liste)
    wien = erklaeren(conn, "region", "9")
    assert "gezaehlt_nach" not in wien and wien["ebene_name"] == "Bundesland"
