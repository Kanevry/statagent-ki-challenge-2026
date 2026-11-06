"""ÖNACE-Fassungen vergleichen in ``uc3 frage`` (78-AC2): Erkennung, Antwort und die zwei Goldfälle.

Die Goldfälle unter ``fixtures/klassifikation/`` sind unmittelbar aus den Quelldateien des Startpakets entstanden,
ohne Produktcode. Der 1:n-Fall trägt seine Quellzeilen selbst und läuft darum auch in der CI durch Parser, Lader und
Antwort. Der Abschnitt C braucht den ganzen Umsteiger und läuft nur mit Startpaket.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any

import psycopg
import pytest

from statagent import frage_fassung, konfig
from statagent.db import Verbindung
from statagent.frage import NICHT_LESBAR, antwort_frage
from statagent.frage_fassung import Vergleich, vergleich_erkennen
from statagent.klass import UNTERKLASSE, umsteiger_laden, umsteiger_uebergaenge
from statagent.klass_quellen import oenace_lesen

GOLD = Path(__file__).parent / "fixtures" / "klassifikation"
UMSTEIGER = "OENACE2008_OENACE2025_DE_12B.txt"
KOPF = (
    '"Ebene";"EDV-Code";"Code";"Titel";"korrespondierende Ebene";"korrespondierender EDV-Code";'
    '"korrespondierender Code";"korrespondierender Titel";"Korrespondenz-Beschreibung"'
)


def _gold(name: str) -> dict[str, Any]:
    daten: dict[str, Any] = json.loads((GOLD / name).read_text(encoding="utf-8"))
    return daten


def _umsteiger_leeren(conn: Verbindung) -> None:
    """Mit lokalem Startpaket lädt die Wegwerf-Datenbank den echten Umsteiger mit."""
    conn.execute("DELETE FROM stat.uebergang WHERE version_alt = '2008' AND version_neu = '2025'")
    conn.execute("DELETE FROM stat.klass_oenace WHERE version IN ('2008', '2025') AND ebene >= 2")


def _umsteiger_einspielen(conn: Verbindung, ordner: Path, zeilen: list[str]) -> None:
    """Geht wie im Betrieb durch Parser und Lader; Datei in der Kodierung der Quelle."""
    datei = ordner / UMSTEIGER
    datei.write_bytes("\r\n".join(zeilen).encode("cp1252"))
    with conn.transaction():
        umsteiger_laden(conn, datei)


def _zeile(alt: str, neu: str, text: str) -> str:
    return f'5;"{alt}";"{alt}";"alt";5;"{neu}";"{neu}";"neu";"{text}"'


# Fängt: Die Jahre gelten wieder als Zeitraum, „vs2025“ ohne Leerzeichen fällt durch, oder das Wort „vs“ wird zum Code.
@pytest.mark.parametrize(
    ("frage", "code"),
    [
        ("ÖNACE C 2008 vs 2025", "C"),
        ("ÖNACE C 2008 vs2025", "C"),
        ("ÖNACE C 2008 vs. 2025", "C"),
        ("önace c 2008 vs 2025", "C"),
        ("OENACE Q 2008 versus 2025", "Q"),
        ("Was unterscheidet ÖNACE C 2008 von 2025?", "C"),
        ("Worin liegt der Unterschied bei ÖNACE C zwischen 2008 und 2025?", "C"),
        ("Unterschied ÖNACE 2025 C und ÖNACE 2008 C", "C"),
        ("Abschnitt C in den Fassungen ÖNACE 2008 und 2025", "C"),
        ("ÖNACE-Abschnitt C 2008/2025", "C"),
        ("Was hat sich bei ÖNACE C von 2008 auf 2025 geändert?", "C"),
        ("ÖNACE UNB 2008 vs 2025", "UNB"),
        ("ÖNACE 2008 vs 2025", None),
        ("ÖNACE 2008 VS 2025", None),
        ("Was unterscheidet ÖNACE 2008 von ÖNACE 2025?", None),
        ("ÖNACE C 2025 vs 2008", "C"),  # die ältere Fassung steht immer zuerst
    ],
)
def test_vergleich_erkannt(frage: str, code: str | None) -> None:
    jahre = sorted(("2008", "2025"))
    assert vergleich_erkennen(frage) == Vergleich(jahre[0], jahre[1], code)


# Fängt: Eine Frage nach Beschäftigten oder einem Zeitraum bekommt eine Erklärung statt ihrer Zahl oder Rückfrage.
@pytest.mark.parametrize(
    "frage",
    [
        "ÖNACE C von 2008 bis 2025",
        "ÖNACE C 2008 2025",
        "ÖNACE C März 2025 vs März 2026",
        "ÖNACE C 03/2025 vs 03/2026",
        "Wie viele Beschäftigte in ÖNACE C 2008 vs 2025?",
        "Beschäftigte ÖNACE C 2008 vs 2025",
        "Fluktuation ÖNACE C 2008 vs 2025",
        "Frauen in ÖNACE C 2008 vs 2025",
        "ÖNACE C 2008 vs 2025 je Bundesland",
        "Zeitreihe ÖNACE C 2008 vs 2025",
        "ÖNACE C 1. Quartal 2008 vs 2025",
        "ÖNACE C Winter 2008 vs 2025",
        "ÖNACE C 2025",
        "ÖNACE C 2003, 2008 und 2025",
        "Beschäftigte 2008 vs 2025",
    ],
)
def test_kein_vergleich(frage: str) -> None:
    assert vergleich_erkennen(frage) is None


def test_goldfall_1n_von_der_quellzeile_bis_zur_antwort(conn: Verbindung, tmp_path: Path) -> None:
    """Fängt: Ein 1:n-Fall wird zu einer eindeutigen Umcodierung, die Antwort nennt nur eines der Ziele, oder der
    Lader liest die Beziehung falsch. Die Quellzeilen im Goldfall sind die Zeilen aus dem Startpaket."""
    gold = _gold("oenace-1n-c-16.10-0.json")
    _umsteiger_leeren(conn)
    _umsteiger_einspielen(conn, tmp_path, gold["quellzeilen"])
    zeilen = conn.execute(
        "SELECT code_alt, code_neu, beziehung FROM stat.uebergang WHERE klassifikation = %s ORDER BY code_neu",
        (UNTERKLASSE,),
    ).fetchall()
    assert [(z["code_alt"], z["code_neu"], z["beziehung"]) for z in zeilen] == [
        (gold["code_alt"], ziel["code"], gold["beziehung"]) for ziel in gold["ziele"]
    ]

    daten = antwort_frage(conn, gold["frage"])

    assert daten["typ"] == "definition" and daten["rueckfrage"] is False and daten["zahlen"] == []
    text = daten["text"]
    assert f"Mehrdeutig ist zum Beispiel {gold['code_alt']} (1:n)" in text
    for ziel in gold["ziele"]:
        assert f"{ziel['code']} ({ziel['beschreibung']})" in text
    assert "keine eindeutige Umcodierung" in text
    assert "das Programm wählt keinen aus" in text
    assert f"Quelle: Umsteiger {gold['quelle']['datei_umsteiger']}." in text


def test_goldfall_1n_nennt_die_bezeichnung_mit_tiefen_ebenen(conn: Verbindung, tmp_path: Path) -> None:
    """Fängt: Sind die tiefen Ebenen geladen, fehlt der Name des alten Codes aus der Quelle."""
    gold = _gold("oenace-1n-c-16.10-0.json")
    _umsteiger_leeren(conn)
    _umsteiger_einspielen(conn, tmp_path, gold["quellzeilen"])
    conn.execute(
        "INSERT INTO stat.klass_oenace (version, code, bezeichnung, ebene, uebergeordnet, gueltig_von, gueltig_bis) "
        "VALUES ('2008', %s, %s, 5, 'C', %s, %s)",
        (gold["code_alt"], gold["bezeichnung_alt"], date(2008, 1, 1), date(2024, 12, 31)),
    )

    text = antwort_frage(conn, gold["frage"])["text"]

    assert f"{gold['code_alt']} „{gold['bezeichnung_alt']}“ (1:n)" in text


def test_beide_fassungen_und_belege(conn: Verbindung, tmp_path: Path) -> None:
    """Fängt: Eine Fassung fehlt, die Gültigkeit stammt aus dem Code, oder eine Zahl der Antwort hat keine SQL."""
    gold = _gold("oenace-c-2008-2025.json")
    _umsteiger_leeren(conn)
    _umsteiger_einspielen(conn, tmp_path, _gold("oenace-1n-c-16.10-0.json")["quellzeilen"])

    daten = antwort_frage(conn, "Was unterscheidet ÖNACE C 2008 von 2025?")

    name = gold["bezeichnung"]["2008"]
    assert name == gold["bezeichnung"]["2025"]
    assert f"ÖNACE C heißt in beiden Fassungen gleich: „{name}“." in daten["text"]
    assert (
        "Die Fassung 2008 gilt von Jänner 2008 bis Dezember 2024, die Fassung 2025 ab Jänner 2025."
        in daten["text"]
    )
    assert daten["definition"] == f"ÖNACE 2008 C: {name}; ÖNACE 2025 C: {name}"
    assert [s["version"] for s in daten["stand"]] == ["2008", "2025"]
    assert [b["quelle"] for b in daten["belege"]] == ["stat.klass_oenace", *["stat.uebergang"] * 3]
    for beleg in daten["belege"]:  # Jede Beleg-SQL muss so laufen, wie sie dasteht.
        conn.execute(beleg["sql"].encode()).fetchall()


def test_buchstabe_wechselt_den_bereich(conn: Verbindung, tmp_path: Path) -> None:
    """Fängt: Derselbe Buchstabe gilt still als dasselbe, obwohl Gesundheit 2025 unter R steht."""
    _umsteiger_leeren(conn)
    _umsteiger_einspielen(
        conn,
        tmp_path,
        [
            KOPF,
            _zeile("Q 86.10-0", "R 86.10-0", "Krankenhäuser"),
            _zeile("Q 86.21-0", "R 86.21-0", "Arztpraxen"),
            _zeile("P 85.10-0", "Q 85.10-0", "Kindergärten"),
        ],
    )

    text = antwort_frage(conn, "ÖNACE Q 2008 vs 2025")["text"]

    assert "ÖNACE Q heißt je Fassung anders." in text
    assert "Fassung 2008: „Gesundheits- und Sozialwesen“. Fassung 2025: „Erziehung und Unterricht“." in text
    assert "führt die 2 Unterklassen aus Q ganz oder teilweise weiter: 2 nach R (Gesundheits-" in text
    assert "Das meiste aus Q steht in der Fassung 2025 unter R." in text
    assert "In Q (Fassung 2025) kommen" not in text
    assert "Dazu kommen in Q: 1 aus P (Erziehung und Unterricht)." in text
    assert "Alle 2 Unterklassen aus Q führen auf genau einen Code." in text
    assert "Mehrdeutig" not in text


def test_nur_mn_faelle_werden_nicht_zu_1n(conn: Verbindung, tmp_path: Path) -> None:
    """Fängt: Ein Code mit mehreren Zielen und geteilten Zielen (m:n) trägt die Marke 1:n."""
    _umsteiger_leeren(conn)
    _umsteiger_einspielen(
        conn,
        tmp_path,
        [
            KOPF,
            _zeile("C 10.10-0", "C 10.11-0", "a"),
            _zeile("C 10.10-0", "C 10.12-0", "b"),
            _zeile("C 10.20-0", "C 10.12-0", "c"),
        ],
    )

    text = antwort_frage(conn, "ÖNACE C 2008 vs 2025")["text"]

    assert "Mehrdeutig ist zum Beispiel C 10.10-0:" in text
    assert "(1:n)" not in text


def test_ohne_liste_der_unterklassen_kein_erfundener_fall(conn: Verbindung) -> None:
    """Fängt: Fehlen die Unterklassen, nennt die Antwort trotzdem Anzahlen oder einen Einzelfall."""
    _umsteiger_leeren(conn)
    conn.execute(
        "INSERT INTO stat.uebergang (klassifikation, version_alt, code_alt, version_neu, code_neu, beziehung, gueltig_ab, "
        "quelle) VALUES ('oenace', '2008', 'C', '2025', 'C', 'm:n', %s, %s), ('oenace', '2008', 'C', '2025', 'A', 'm:n', %s, %s)",
        (
            date(2025, 1, 1),
            f"{UMSTEIGER}, 2 von 2 Unterklassen",
            date(2025, 1, 1),
            f"{UMSTEIGER}, 1 von 2 Unterklassen",
        ),
    )

    daten = antwort_frage(conn, "ÖNACE C 2008 vs 2025")

    assert "Für C gibt es also keine eindeutige Umcodierung." in daten["text"]
    assert "darum folgt hier kein Einzelfall" in daten["text"]
    assert "Mehrdeutig ist zum Beispiel" not in daten["text"]
    assert f"Quelle: Umsteiger {UMSTEIGER}." in daten["text"]


@pytest.mark.parametrize(
    ("frage", "erwartet"),
    [
        ("ÖNACE X 2008 vs 2025", "Einen Abschnitt X gibt es in den Fassungen 2008 und 2025 nicht."),
        ("ÖNACE V 2008 vs 2025", "ÖNACE V gibt es nur in der Fassung 2025"),
        (
            "ÖNACE D 2003 vs 2025",
            "Einen direkten Umsteiger zwischen den Fassungen 2003 und 2025 gibt es nicht.",
        ),
    ],
)
def test_ehrlich_ohne_abschnitt_oder_umsteiger(conn: Verbindung, frage: str, erwartet: str) -> None:
    """Fängt: Ein Buchstabe, den es nicht gibt, oder ein fehlender Umsteiger führt zu einer erfundenen Zuordnung."""
    _umsteiger_leeren(conn)
    assert erwartet in antwort_frage(conn, frage)["text"]


def test_umsteiger_nennt_den_code_nicht(conn: Verbindung, tmp_path: Path) -> None:
    """Fängt: „Keinen Umsteiger“ für einen einzelnen Code, obwohl es den Umsteiger für die Fassungen gibt."""
    _umsteiger_leeren(conn)
    _umsteiger_einspielen(conn, tmp_path, [KOPF, _zeile("C 10.10-0", "C 10.11-0", "a")])
    text = antwort_frage(conn, "ÖNACE B 2008 vs 2025")["text"]
    assert "Der Umsteiger zwischen den Fassungen 2008 und 2025 nennt B nicht." in text


def test_ueberblick_ohne_abschnitt(conn: Verbindung, tmp_path: Path) -> None:
    """Fängt: Ohne Buchstabe kommt wieder die Rückfrage nach einer Zeitreihe, oder ÖNACE-Fassungen werden still
    gleichgesetzt, obwohl derselbe Buchstabe zwei Bereiche meint."""
    gold = _gold("oenace-1n-c-16.10-0.json")
    _umsteiger_leeren(conn)
    _umsteiger_einspielen(conn, tmp_path, gold["quellzeilen"])

    daten = antwort_frage(conn, "Was unterscheidet ÖNACE 2008 von 2025?")

    assert daten["rueckfrage"] is False and daten["zahlen"] == []
    assert "Derselbe Buchstabe meint also nicht immer dasselbe." in daten["text"]
    assert "Mehrdeutig ist zum Beispiel C 16.10-0 (1:n)" in daten["text"]
    assert "„ÖNACE C 2008 vs 2025“" in daten["text"]


def test_tiefer_code_im_vergleich_wird_erklaert(conn: Verbindung, tmp_path: Path) -> None:
    """Fängt: „ÖNACE C 16.10-0 2008 vs 2025“ bekommt die Absage „zählt nicht tiefer“, weil die Jahre als Zeit gelten."""
    gold = _gold("oenace-1n-c-16.10-0.json")
    _umsteiger_leeren(conn)
    _umsteiger_einspielen(conn, tmp_path, gold["quellzeilen"])
    conn.execute(
        "INSERT INTO stat.klass_oenace (version, code, bezeichnung, ebene, uebergeordnet, gueltig_von, gueltig_bis) "
        "VALUES ('2008', %s, %s, 5, 'C', %s, %s)",
        (gold["code_alt"], gold["bezeichnung_alt"], date(2008, 1, 1), date(2024, 12, 31)),
    )

    text = antwort_frage(conn, "ÖNACE C 16.10-0 2008 vs 2025")["text"]

    assert gold["bezeichnung_alt"] in text
    assert "aufgeteilt auf" in text
    assert "keine Zahl" not in text


# Fängt: Die Weiche greift zu weit und nimmt einer Frage nach Daten ihre Rückfrage.
@pytest.mark.parametrize("frage", ["ÖNACE C 2024 vs 2025", "ÖNACE C 2008 vs 2025 in Wien"])
def test_keine_fassung_oder_ort_bleibt_beim_bisherigen_weg(conn: Verbindung, frage: str) -> None:
    daten = antwort_frage(conn, frage)
    assert daten["rueckfrage"] is True
    assert "Zeitreihe" in daten["text"]


def test_datenbankfehler_wird_zur_absage(conn: Verbindung, monkeypatch: pytest.MonkeyPatch) -> None:
    """Fängt: Ein Lesefehler wirft bis in die Kette durch, statt offen zu sagen, dass nichts lesbar ist."""

    def kaputt(*_: object) -> list[dict[str, Any]]:
        raise psycopg.OperationalError("weg")

    monkeypatch.setattr(frage_fassung, "_lesen", kaputt)
    assert antwort_frage(conn, "ÖNACE C 2008 vs 2025")["text"] == NICHT_LESBAR


@pytest.mark.daten
def test_goldfaelle_gegen_startpaket(conn: Verbindung) -> None:
    """Fängt: Goldfälle und Quelldateien laufen auseinander, oder die Antwort zählt anders als die Quelle."""
    ordner = konfig.startpaket() / "klassifikationen" / "oenace"
    datei = ordner / UMSTEIGER
    if not datei.is_file():
        pytest.skip("Startpaket mit Klassifikationen nicht vorhanden")
    abschnitt, fall = _gold("oenace-c-2008-2025.json"), _gold("oenace-1n-c-16.10-0.json")

    inhalt = datei.read_bytes().decode("cp1252").splitlines()
    assert all(z in inhalt for z in fall["quellzeilen"])
    for version in ("2008", "2025"):
        # Beim Abschnitt steht „Titel“ in Großbuchstaben, die letzte Spalte trägt die Schreibweise der Datenbank.
        zeilen = (ordner / f"OENACE{version}_DE_CTI.txt").read_bytes().decode("cp1252").splitlines()
        assert any(
            z.startswith('1;"C";"C";') and z.endswith(f'"{abschnitt["bezeichnung"][version]}"')
            for z in zeilen
        )
    alt = {z.code: z.bezeichnung for z in oenace_lesen(ordner / "OENACE2008_DE_CTI.txt")}
    neu = {z.code: z.bezeichnung for z in oenace_lesen(ordner / "OENACE2025_DE_CTI.txt")}
    assert alt[fall["code_alt"]] == fall["bezeichnung_alt"]
    assert all(neu[z["code"]] == z["bezeichnung"] for z in fall["ziele"])

    uebergaenge, _, _ = umsteiger_uebergaenge(datei)
    unter = [u for u in uebergaenge if u["klassifikation"] == UNTERKLASSE]
    ziele_c: dict[str, set[str]] = {}
    for u in unter:
        if u["code_alt"].startswith("C "):
            ziele_c.setdefault(u["code_alt"], set()).add(u["code_neu"])
    assert len(ziele_c) == abschnitt["unterklassen_2008"]
    assert sum(len(z) > 1 for z in ziele_c.values()) == abschnitt["mehrdeutig"]
    assert sum(len(z) == 1 for z in ziele_c.values()) == abschnitt["eindeutig"]

    _umsteiger_leeren(conn)
    with conn.transaction():
        umsteiger_laden(conn, datei)
    text = antwort_frage(conn, abschnitt["frage"])["text"]
    assert f"die {abschnitt['unterklassen_2008']} Unterklassen aus C" in text
    assert f"{abschnitt['eindeutig']} Unterklassen aus C führen auf genau einen Code" in text
    assert f"{abschnitt['mehrdeutig']} auf mehrere" in text
    for buchstabe, anzahl in abschnitt["nach"].items():
        assert f"{anzahl} nach {buchstabe}" in text
    for buchstabe, anzahl in abschnitt["aus"].items():
        assert f"{anzahl} aus {buchstabe}" in text
    assert f"Mehrdeutig ist zum Beispiel {fall['code_alt']}" in text
