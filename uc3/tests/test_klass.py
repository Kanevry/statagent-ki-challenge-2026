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
