"""ÖNACE-Fassungen vergleichen in ``uc3 frage`` (78-AC2): Erkennung, Antwort und die zwei Goldfälle.

Die Goldfälle unter ``fixtures/klassifikation/`` sind unmittelbar aus den Quelldateien des Startpakets entstanden,
ohne Produktcode. Der 1:n-Fall trägt seine Quellzeilen selbst und läuft darum auch in der CI durch Parser, Lader und
Antwort. Der Abschnitt C braucht den ganzen Umsteiger und läuft nur mit Startpaket.
"""

from __future__ import annotations

import hashlib
import json
from datetime import date
from pathlib import Path
from typing import Any

import psycopg
import pytest

from statagent import frage_fassung, konfig
from statagent.db import Verbindung
from statagent.frage import NICHT_LESBAR, antwort_frage
from statagent.frage_fassung import Vergleich, _aufzaehlung, vergleich_erkennen
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
        ("ÖNACE C 2008 und ÖNACE C 2025", "C"),
        ("Vergleiche ÖNACE 2008 und 2025 für Q", "Q"),
        ("Unterschied bei C zwischen ÖNACE 2008 und 2025", "C"),
        ("ÖNACE 2008 und 2025 C", "C"),
        ("Wie viele Unterklassen aus ÖNACE C wechseln von 2008 auf 2025?", "C"),
        # Die Endung gehört zum Wort: „Abschnitte“ ist nicht Abschnitt E.
        ("Welche ÖNACE-Abschnitte unterscheiden sich 2008 vs 2025?", None),
        ("ÖNACE-Abschnitts 2008 vs 2025", None),
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
        "Angestellte in ÖNACE C 2008 vs 2025",
        "Anteil von ÖNACE C 2008 vs 2025",
        "Wachstum in ÖNACE C von 2008 auf 2025",
        "ÖNACE C 2008 vs 2025 in Prozent",
        "Unter 25-Jährige in ÖNACE C 2008 vs 2025",
        "ÖNACE C 2008 vs 2025 im Bezirk Innsbruck",
        "Person 1234567 in ÖNACE C 2008 vs 2025",
        "Einkommen in ÖNACE C 2008 vs 2025",
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
    ziele = [ziel["code"] for ziel in gold["ziele"]]
    assert (
        f"keine eindeutige Umcodierung: {gold['code_alt']} kann {ziele[0]} oder {ziele[1]} sein, "
        "das Programm wählt keinen aus."
    ) in daten["text"]
    assert "Quelle: Umsteigeschlüssel von Statistik Austria." in daten["text"]
    # Der Text bleibt kurz: Dateiname und 1:n gehören in den Beleg.
    assert UMSTEIGER not in daten["text"] and "1:n" not in daten["text"]
    fall = daten["belege"][-1]
    assert UMSTEIGER in fall["quelle"] and gold["code_alt"] in fall["ref"]
    assert "'1:n'" in fall["sql"]
    for ziel in ziele:
        assert any(z["code_neu"] == ziel for z in conn.execute(fall["sql"].encode()).fetchall())


def test_beide_fassungen_und_belege(conn: Verbindung, tmp_path: Path) -> None:
    """Fängt: Eine Fassung fehlt, die Gültigkeit stammt aus dem Code, oder eine Zahl der Antwort hat keine SQL."""
    gold = _gold("oenace-c-2008-2025.json")
    _umsteiger_leeren(conn)
    _umsteiger_einspielen(conn, tmp_path, _gold("oenace-1n-c-16.10-0.json")["quellzeilen"])

    daten = antwort_frage(conn, "Was unterscheidet ÖNACE C 2008 von 2025?")

    name = gold["bezeichnung"]["2008"]
    assert name == gold["bezeichnung"]["2025"]
    assert f"ÖNACE C heißt in beiden Fassungen „{name}“." in daten["text"]
    assert "Die Fassung 2008 gilt bis Dezember 2024, die Fassung 2025 ab Jänner 2025." in daten["text"]
    assert daten["definition"] == f"ÖNACE 2008 C: {name}; ÖNACE 2025 C: {name}"
    assert [s["version"] for s in daten["stand"]] == ["2008", "2025"]
    assert [b["quelle"] for b in daten["belege"]] == [
        "stat.klass_oenace",
        *[f"stat.uebergang, {UMSTEIGER}"] * 3,
    ]
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
    assert (
        "Der Buchstabe allein reicht hier nicht: Das meiste aus Q steht in der Fassung 2025 unter R." in text
    )
    assert "Das meiste in Q (Fassung 2025) kommt aus P." in text
    assert "Von den 2 Unterklassen aus Q führt jede auf genau einen Code der Fassung 2025." in text
    assert "Unterklassen wechseln den Abschnitt" not in text
    assert "keine eindeutige Umcodierung" not in text


def test_beispiel_bevorzugt_den_echten_1n_fall(conn: Verbindung, tmp_path: Path) -> None:
    """Fängt: Das Beispiel ist ein m:n-Code, obwohl das Kriterium einen 1:n-Fall verlangt und es einen gibt."""
    _umsteiger_leeren(conn)
    _umsteiger_einspielen(
        conn,
        tmp_path,
        [
            KOPF,
            _zeile("C 10.10-0", "C 10.11-0", "a"),
            _zeile("C 10.10-0", "C 10.12-0", "b"),
            _zeile("C 10.20-0", "C 10.12-0", "c"),
            _zeile("C 11.10-0", "C 11.11-0", "d"),
            _zeile("C 11.10-0", "C 11.12-0", "e"),
        ],
    )
    text = antwort_frage(conn, "ÖNACE C 2008 vs 2025")["text"]
    assert "C 11.10-0 kann C 11.11-0 oder C 11.12-0 sein" in text
    assert "Von den 3 Unterklassen aus C führen 1 auf" not in text
    assert "führt 1 auf genau einen Code der Fassung 2025 und 2 auf mehrere." in text


def test_teile_wechseln_den_abschnitt(conn: Verbindung, tmp_path: Path) -> None:
    """Fängt: Der Satz nennt Abschnitte, die nichts abgeben, oder fehlt, wenn einzelne Unterklassen wandern."""
    _umsteiger_leeren(conn)
    _umsteiger_einspielen(
        conn,
        tmp_path,
        [
            KOPF,
            *[_zeile(f"C 1{i}.10-0", f"C 1{i}.10-0", "bleibt") for i in range(5)],
            _zeile("C 15.10-0", "C 15.10-0", "bleibt"),
            _zeile("C 15.10-0", "A 01.10-0", "geht"),
            _zeile("E 38.10-0", "C 16.10-0", "kommt"),
        ],
    )
    text = antwort_frage(conn, "ÖNACE C 2008 vs 2025")["text"]
    assert "Manche Unterklassen wechseln den Abschnitt: Teile gehen nach A, Teile kommen aus E." in text
    assert "Der Buchstabe allein" not in text


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
    assert "C (Fassung 2008) führt nach A und C." in daten["text"]
    assert "Quelle: Umsteigeschlüssel von Statistik Austria." in daten["text"]
    assert " kann " not in daten["text"]
    assert UMSTEIGER in daten["belege"][-1]["quelle"]


@pytest.mark.parametrize(
    ("frage", "erwartet"),
    [
        ("ÖNACE X 2008 vs 2025", "Einen Abschnitt X gibt es in den Fassungen 2008 und 2025 nicht."),
        ("ÖNACE V 2008 vs 2025", "ÖNACE V gibt es nur in der Fassung 2025"),
        (
            "ÖNACE D 2003 vs 2025",
            "Ein direkter Umsteigeschlüssel zwischen den Fassungen 2003 und 2025 liegt hier nicht vor.",
        ),
    ],
)
def test_ehrlich_ohne_abschnitt_oder_umsteiger(conn: Verbindung, frage: str, erwartet: str) -> None:
    """Fängt: Ein Buchstabe, den es nicht gibt, oder ein fehlender Umsteiger führt zu einer erfundenen Zuordnung."""
    _umsteiger_leeren(conn)
    assert erwartet in antwort_frage(conn, frage)["text"]


def test_groesster_zufluss_zaehlt_neue_codes(conn: Verbindung, tmp_path: Path) -> None:
    """Fängt: Sechs alte Codes auf einen neuen gelten als „das meiste“, obwohl fünf andere Codes den Abschnitt tragen
    (so stand es bei ÖNACE M 2025 da: „kommt aus F“, gemessen führt L auf fünf von sechs neuen Codes)."""
    _umsteiger_leeren(conn)
    _umsteiger_einspielen(
        conn,
        tmp_path,
        [
            KOPF,
            *[_zeile(f"F 41.{i}0-0", "M 68.10-0", "viele alte auf einen neuen") for i in range(6)],
            *[_zeile(f"L 68.{i}0-0", f"M 68.{i + 2}0-0", "je einer") for i in range(5)],
        ],
    )
    assert (
        "Das meiste in M (Fassung 2025) kommt aus L." in antwort_frage(conn, "ÖNACE M 2008 vs 2025")["text"]
    )


def test_eine_unterklasse_wechselt(conn: Verbindung, tmp_path: Path) -> None:
    """Fängt: „Einzelne Unterklassen wechseln“, obwohl es genau eine ist."""
    _umsteiger_leeren(conn)
    _umsteiger_einspielen(
        conn,
        tmp_path,
        [KOPF, _zeile("E 38.10-0", "E 38.10-0", "bleibt"), _zeile("E 38.10-0", "C 20.10-0", "geht")],
    )
    text = antwort_frage(conn, "ÖNACE E 2008 vs 2025")["text"]
    assert "Eine Unterklasse wechselt den Abschnitt: Teile gehen nach C." in text
    assert "Die 1 Unterklasse aus E" not in text


def test_fremdes_wort_wird_nicht_zum_code(conn: Verbindung) -> None:
    """Fängt: „ÖNACE ROH …“ landet als Literal in der Abfrage und meldet „nicht lesbar“ wegen der Sperre für roh."""
    _umsteiger_leeren(conn)
    text = antwort_frage(conn, "ÖNACE ROH 2008 vs 2025")["text"]
    assert text != NICHT_LESBAR
    assert "Die Fassung 2008 gilt" in text


def test_offene_aeltere_fassung_wirft_nicht(conn: Verbindung) -> None:
    """Fängt: Hat die ältere Fassung kein Enddatum, wirft die Anzeige, und die Frage endet im Fehler statt in der Antwort."""
    _umsteiger_leeren(conn)
    conn.execute("UPDATE stat.klass_oenace SET gueltig_bis = NULL WHERE version = '2008'")
    text = antwort_frage(conn, "ÖNACE C 2008 vs 2025")["text"]
    assert "Die Fassung 2008 gilt ab Jänner 2008" in text


def test_ort_mit_code_bleibt_beim_bisherigen_weg(conn: Verbindung) -> None:
    """Fängt: Eine Frage nach einem Bezirk mit Code bekommt die Erklärung der Fassungen."""
    assert "Fassung 2008 gilt" not in antwort_frage(conn, "ÖNACE C 2008 vs 2025 Gemeinde 90001")["text"]


@pytest.mark.parametrize(
    ("frage", "absage"),
    [
        ("Person 1234567 in ÖNACE C 2008 vs 2025", "Einzeldaten gibt StatAgent nicht heraus"),
        ("Einkommen in ÖNACE C 2008 vs 2025", "Einkommen sind nicht in den Daten"),
    ],
)
def test_einzeldaten_und_fehlende_merkmale_bekommen_die_absage(
    conn: Verbindung, frage: str, absage: str
) -> None:
    """Fängt: Die Weiche antwortet mit den Listen, oder die Frage endet in der Rückfrage nach einer Zeitreihe."""
    daten = antwort_frage(conn, frage)
    assert absage in daten["text"]
    assert daten["rueckfrage"] is False and "Fassung 2008 gilt" not in daten["text"]


def test_fassung_2003_steht_ueber_die_unterabschnitte_im_schluessel(conn: Verbindung) -> None:
    """Fängt: „Der Schlüssel nennt D nicht“, obwohl DA bis DN darin stehen. Und die Zeilen 2003 → 2008 nennen nur das
    Ziel der Mehrheit: Sie dürfen nicht wie der vollständige Schlüssel klingen (100_klass_daten.sql)."""
    text = antwort_frage(conn, "ÖNACE D 2003 vs 2008")["text"]
    assert (
        "D steht im Schlüssel über seine Unterabschnitte DA bis DN, sie führen vor allem nach C, DE auch nach J."
        in text
    )
    assert "nennt D nicht" not in text
    assert "Quelle: abgeleitet aus dem Umsteigeschlüssel von Statistik Austria." in text

    text = antwort_frage(conn, "ÖNACE DE 2003 vs 2008")["text"]
    assert "DE (Fassung 2003) führt vor allem nach C und J." in text
    assert "In den Listen der Fassung 2008 steht dieser Code nicht." in text
    assert "Quelle: abgeleitet aus dem Umsteigeschlüssel von Statistik Austria." in text

    assert "Nach J (Fassung 2008) führt vor allem DE." in antwort_frage(conn, "ÖNACE J 2003 vs 2008")["text"]
    assert (
        "Nach C (Fassung 2008) führen vor allem DA, DB, DC und 11 weitere."
        in antwort_frage(conn, "ÖNACE C 2003 vs 2008")["text"]
    )


def test_zufluss_ohne_mehrheit_und_einzelner_code(conn: Verbindung, tmp_path: Path) -> None:
    """Fängt: „In Q kommen Teile“ und „Von der 1 Unterklasse führen 0 …“."""
    _umsteiger_leeren(conn)
    _umsteiger_einspielen(
        conn,
        tmp_path,
        [
            KOPF,
            _zeile("Q 86.10-0", "R 86.10-0", "a"),
            _zeile("Q 86.10-0", "R 86.20-0", "b"),
            _zeile("L 68.10-0", "Q 85.10-0", "c"),
            _zeile("M 69.10-0", "Q 85.20-0", "d"),
        ],
    )
    text = antwort_frage(conn, "ÖNACE Q 2008 vs 2025")["text"]
    assert "Nach Q (Fassung 2025) kommen Teile aus L und M." in text
    assert "Die einzige Unterklasse aus Q führt auf mehrere Codes der Fassung 2025." in text
    assert (
        "Für diese eine gibt es keine eindeutige Umcodierung: Q 86.10-0 kann R 86.10-0 oder R 86.20-0 sein"
        in text
    )
    assert "führen 0" not in text


def test_umsteiger_nennt_den_code_nicht(conn: Verbindung, tmp_path: Path) -> None:
    """Fängt: „Keinen Umsteiger“ für einen einzelnen Code, obwohl es den Umsteiger für die Fassungen gibt."""
    _umsteiger_leeren(conn)
    _umsteiger_einspielen(conn, tmp_path, [KOPF, _zeile("C 10.10-0", "C 10.11-0", "a")])
    text = antwort_frage(conn, "ÖNACE B 2008 vs 2025")["text"]
    assert "Der Umsteigeschlüssel zwischen den Fassungen 2008 und 2025 nennt B nicht." in text


def test_ueberblick_ohne_abschnitt(conn: Verbindung, tmp_path: Path) -> None:
    """Fängt: Ohne Buchstabe kommt wieder die Rückfrage nach einer Zeitreihe, oder ÖNACE-Fassungen werden still
    gleichgesetzt, obwohl derselbe Buchstabe zwei Bereiche meint."""
    gold = _gold("oenace-1n-c-16.10-0.json")
    _umsteiger_leeren(conn)
    _umsteiger_einspielen(conn, tmp_path, gold["quellzeilen"])

    daten = antwort_frage(conn, "Was unterscheidet ÖNACE 2008 von 2025?")

    assert daten["rueckfrage"] is False and daten["zahlen"] == []
    assert "Derselbe Buchstabe meint also nicht immer dasselbe." in daten["text"]
    assert "C 16.10-0 kann C 16.11-0 oder C 16.12-0 sein" in daten["text"]
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

    assert hashlib.sha256(datei.read_bytes()).hexdigest() == fall["quelle"]["sha256_umsteiger"]
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
    assert (
        f"Von den {abschnitt['unterklassen_2008']} Unterklassen aus C führen {abschnitt['eindeutig']} auf genau einen "
        f"Code der Fassung 2025 und {abschnitt['mehrdeutig']} auf mehrere."
    ) in text
    assert f"Teile gehen nach {_aufzaehlung(sorted(set(abschnitt['nach']) - {'C'}))}" in text
    assert f"Teile kommen aus {_aufzaehlung(sorted(abschnitt['aus']))}" in text
    assert f"{fall['code_alt']} kann" in text
