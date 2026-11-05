"""Tiefe Klassifikationscodes in ``uc3 frage`` (#189): Erkennung, Erklärung, Absage.

Alle Namen sind erfunden. Der Aufbau löscht zuerst die tiefen Ebenen, denn mit einem lokalen Startpaket lädt die
Wegwerf-Datenbank die echten mit.
"""

from __future__ import annotations

from datetime import date
from typing import Any

import psycopg
import pytest

from statagent import frage_klass
from statagent.db import Verbindung
from statagent.frage import NICHT_LESBAR, antwort_frage
from statagent.frage_klass import codes_erkennen, tiefer_code_antwort
from statagent.klass import UNTERKLASSE

V2008 = (date(2008, 1, 1), date(2024, 12, 31))
V2025 = (date(2025, 1, 1), None)
OENACE_ZEILEN = [
    (v, code, f"{name} {v}", ebene, oben, *gilt)
    for v, gilt in (("2008", V2008), ("2025", V2025))
    for code, name, ebene, oben in (
        ("C 10", "Erfundene Abteilung", 2, "C"),
        ("C 10.1", "Erfundene Gruppe", 3, "C 10"),
        ("C 10.11", "Erfundene Klasse", 4, "C 10.1"),
        ("C 10.11-0", "Erfundene Unterklasse", 5, "C 10.11"),
    )
] + [
    # Derselbe Code liegt je Fassung in einem anderen Abschnitt.
    ("2008", "J 58.21-0", "Wandernder Code alt", 5, "J", *V2008),
    ("2025", "K 58.21-0", "Wandernder Code neu", 5, "K", *V2025),
]
REGION_ZEILEN = [
    ("2011-01-01", "101", "Erfundener Bezirk", "bezirk", "9", date(2011, 1, 1), date(2011, 12, 31)),
    ("2012-01-01", "101", "Erfundener Bezirk", "bezirk", "9", date(2012, 1, 1), None),
    ("2011-01-01", "90001", "Altdorf", "gemeinde", "101", date(2011, 1, 1), date(2011, 12, 31)),
    ("2012-01-01", "90001", "Neudorf", "gemeinde", "101", date(2012, 1, 1), None),
]
#: Fünf Übergänge der Unterklasse, damit die Antwort kappen muss.
UEBERGAENGE = [
    (UNTERKLASSE, "2008", "C 10.11-0", "2025", f"C 10.1{i}-0", "1:n", date(2025, 1, 1), "erfunden")
    for i in range(1, 6)
] + [
    ("gemeinde", "2011-01-01", "90001", "2012-01-01", "90001", "1:1", date(2012, 1, 1), "erfunden"),
    ("bezirk", "2011-01-01", "101", "2012-01-01", "101", "n:1", date(2012, 1, 1), "erfunden"),
    # Der Stand, auf den dieser Übergang zeigt, ist nicht geladen: kein Name auf der neuen Seite.
    ("bezirk", "2012-01-01", "101", "2013-01-01", "101", "n:1", date(2013, 1, 1), "erfunden"),
]


def _tiefe_ebenen_leeren(conn: Verbindung) -> None:
    conn.execute("DELETE FROM stat.klass_oenace WHERE version IN ('2008', '2025') AND ebene >= 2")
    conn.execute("DELETE FROM stat.klass_region WHERE ebene IN ('bezirk', 'gemeinde')")
    conn.execute(
        f"DELETE FROM stat.uebergang WHERE klassifikation IN ('{UNTERKLASSE}', 'gemeinde', 'bezirk')"
    )


@pytest.fixture
def tief(conn: Verbindung) -> Verbindung:
    _tiefe_ebenen_leeren(conn)
    with conn.cursor() as cur:
        cur.executemany(
            "INSERT INTO stat.klass_oenace (version, code, bezeichnung, ebene, uebergeordnet, gueltig_von, "
            "gueltig_bis) VALUES (%s, %s, %s, %s, %s, %s, %s)",
            OENACE_ZEILEN,
        )
        cur.executemany(
            "INSERT INTO stat.klass_region (version, code, bezeichnung, ebene, uebergeordnet, gueltig_von, "
            "gueltig_bis) VALUES (%s, %s, %s, %s, %s, %s, %s)",
            REGION_ZEILEN,
        )
        cur.executemany(
            "INSERT INTO stat.uebergang (klassifikation, version_alt, code_alt, version_neu, code_neu, beziehung, "
            "gueltig_ab, quelle) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
            UEBERGAENGE,
        )
    return conn


def _bundesland_9(conn: Verbindung) -> str:
    zeile = conn.execute("SELECT bezeichnung FROM stat.klass_region WHERE code = '9'").fetchone()
    assert zeile is not None
    return str(zeile["bezeichnung"])


# Fängt: Datum, Monat oder Menge als Code (dann bekäme „am 10.11.“ eine Absage), und Regelnamen wie E07 als ÖNACE.
@pytest.mark.parametrize(
    ("frage", "codes"),
    [
        ("Was ist ÖNACE C 10.11-0?", ["C 10.11-0"]),
        ("C10.11-0", ["C 10.11-0"]),
        ("10.11-0", ["10.11-0"]),
        ("oenace 10.11-0", ["10.11-0"]),
        ("NACE c 10.1", ["C 10.1"]),
        ("ÖNACE C 10.11", ["C 10.11"]),
        ("c 10", ["C 10"]),
        ("oenace 10.11", ["10.11"]),
        ("ÖNACE-Abteilung 10", ["10"]),
        ("ÖNACE 2025 C 10.11-0", ["C 10.11-0"]),
        ("ÖNACE C 10.11-0", ["C 10.11-0"]),  # so schickt macOS das Ö manchmal
        ("Was ist C 10.11-0 und C 11?", ["C 10.11-0", "C 11"]),
        ("Gemeinde 90001", ["90001"]),
        ("Gemeindecode 90001.", ["90001"]),
        ("Bezirk 101", ["101"]),
        ("Bezirkscode 101", ["101"]),
        # Kein Code:
        ("10.11", []),
        ("10", []),
        ("10.11.2025", []),
        ("ÖNACE C am 10.11.2025", []),
        ("C 10.11.2025", []),
        ("ÖNACE 10.2025", []),
        ("ÖNACE C 10/2025", []),
        ("Beschäftigte am 10.11.", []),
        ("10 Personen", []),
        ("ÖNACE 10 Personen", []),
        ("ÖNACE C", []),
        ("Was ist ÖNACE C?", []),
        ("ÖNACE 2008", []),
        ("Was ist Regel E07?", []),
        ("Bezirk Innsbruck", []),
        ("Gemeinde Hallein", []),
        ("Gemeinde 123", []),
        ("Bezirk 12345", []),
    ],
)
def test_erkennung(frage: str, codes: list[str]) -> None:
    assert [c.code for c in codes_erkennen(frage)] == codes


def test_oenace_unterklasse_statt_abschnitt(tief: Verbindung) -> None:
    """Fängt den gemessenen Fehler: „ÖNACE C 10.11-0“ erklärte still den Abschnitt C."""
    daten = antwort_frage(tief, "Was ist ÖNACE C 10.11-0?")
    text = daten["text"]
    assert daten["typ"] == "definition"
    assert "Der Code C 10.11-0 ist eine Unterklasse der ÖNACE und heißt „Erfundene Unterklasse 2025“." in text
    assert "In ÖNACE 2008 hieß er „Erfundene Unterklasse 2008“." in text
    assert "Er gehört zur Abteilung Erfundene Abteilung 2025 (C 10), Abschnitt" in text
    assert "(C 10.11)" not in text and "(C 10.1)" not in text  # Klasse und Gruppe wiederholen nur den Namen
    assert "Ab ÖNACE 2025 ist er aufgeteilt auf" in text
    assert " und 2 weitere." in text  # fünf Übergänge, drei gezeigt
    assert "Die Statistik zählt nach Abschnitt, nicht nach Unterklasse." in text
    assert "–" not in text and "—" not in text
    assert daten["zahlen"] == []
    assert {s["version"] for s in daten["stand"]} == {"2008", "2025"}


def test_pfad_nur_einmal_ausser_der_code_wandert(tief: Verbindung) -> None:
    """Fängt zwei Fehler: den doppelt gesprochenen Pfad und den verschwiegenen Abschnittswechsel."""
    gleich = antwort_frage(tief, "Was ist ÖNACE C 10.11-0?")["text"]
    assert gleich.count("gehört") == 1
    wandert = antwort_frage(tief, "Was ist ÖNACE 58.21-0?")["text"]
    assert "Der Code J 58.21-0 / K 58.21-0 ist eine Unterklasse der ÖNACE" in wandert
    assert "In ÖNACE 2008 gehört er zum Abschnitt" in wandert
    assert "In ÖNACE 2025 gehört er zum Abschnitt" in wandert


def test_belege_sind_ausfuehrbar_und_zeigen_die_zeilen_der_antwort(tief: Verbindung) -> None:
    """Fängt einen Beleg, der etwas anderes abfragt als die Antwort nennt."""
    belege = antwort_frage(tief, "Was ist ÖNACE C 10.11-0?")["belege"]
    assert [b["quelle"] for b in belege] == ["stat.klass_oenace", "stat.uebergang"]
    zeilen = tief.execute(belege[0]["sql"].encode()).fetchall()
    assert {(z["version"], z["code"]) for z in zeilen} == {("2008", "C 10.11-0"), ("2025", "C 10.11-0")}
    assert len(tief.execute(belege[1]["sql"].encode()).fetchall()) == 5


def test_nackte_nummer_nach_oenace_gibt_keine_rueckfrage(tief: Verbindung) -> None:
    """Fängt den gemessenen Fehler: „oenace 10.11-0“ führte zu einer Rückfrage."""
    daten = antwort_frage(tief, "oenace 10.11-0")
    assert not daten["rueckfrage"]
    assert "Der Code C 10.11-0 ist eine Unterklasse der ÖNACE" in daten["text"]


def test_gemeinde_ist_keine_kennung(tief: Verbindung) -> None:
    """Fängt den gemessenen Fehler: Die Gemeinde 90001 bekam „Einzeldaten gibt StatAgent nicht heraus“."""
    daten = antwort_frage(tief, "Was ist die Gemeinde 90001?")
    text = daten["text"]
    assert "Einzeldaten" not in text
    assert "Der Code 90001 ist eine Gemeinde und heißt „Neudorf“." in text
    assert "Den Code gibt es seit Jänner 2011." in text
    assert "Von Jänner 2011 bis Dezember 2011: „Altdorf“." in text
    assert f"gehört zu: Bezirk Erfundener Bezirk (101), Bundesland {_bundesland_9(tief)} (9)." in text
    assert text.count("gehört zu") == 1  # beide Stände haben denselben Pfad
    assert "Die Statistik zählt nach Bundesland, nicht nach Gemeinde." in text


def test_bezirk_ohne_sinnlosen_uebergang_auf_sich_selbst(tief: Verbindung) -> None:
    """Fängt „Erfundener Bezirk (101) wird zu Erfundener Bezirk (101)“: Das sagt niemandem etwas."""
    text = antwort_frage(tief, "Bezirk 101")["text"]
    assert "Der Code 101 ist ein Bezirk und heißt „Erfundener Bezirk“." in text
    assert "wird zu" not in text and "(101) wird" not in text


@pytest.mark.parametrize(
    ("frage", "satz"),
    [
        ("Was ist ÖNACE Z 99.99-9?", "Den Code Z 99.99-9 gibt es in der ÖNACE nicht."),
        ("Was ist die Gemeinde 99999?", "Eine Gemeinde mit dem Code 99999 gibt es nicht."),
        ("Bezirk 999", "Einen Bezirk mit dem Code 999 gibt es nicht."),
    ],
)
def test_unbekannter_code_weicht_nicht_aus(tief: Verbindung, frage: str, satz: str) -> None:
    """Fängt das stille Ausweichen: Ein falscher Code darf nie einen Abschnitt erklären."""
    daten = antwort_frage(tief, frage)
    assert daten["text"] == satz
    assert daten["definition"] is None


@pytest.mark.parametrize(
    ("frage", "satz", "hinweis"),
    [
        (
            "Was ist ÖNACE C 10.11-0?",
            "Die Ebenen unter dem ÖNACE-Abschnitt sind in dieser Fassung nicht dabei. Den Code C 10.11-0 kann StatAgent darum nicht prüfen.",
            "„Was ist ÖNACE C?“",
        ),
        (
            "Was ist die Gemeinde 90001?",
            "Die Gemeinden sind in dieser Fassung nicht dabei. Den Code 90001 kann StatAgent darum nicht prüfen.",
            None,
        ),
        (
            "Bezirk 101",
            "Die Bezirke sind in dieser Fassung nicht dabei. Den Code 101 kann StatAgent darum nicht prüfen.",
            None,
        ),
    ],
)
def test_ebene_nicht_geladen_ist_kein_unbekannter_code(
    conn: Verbindung, frage: str, satz: str, hinweis: str | None
) -> None:
    """Fängt die falsche Auskunft „den Code gibt es nicht“ in einer Datenbank ohne die tiefen Ebenen."""
    _tiefe_ebenen_leeren(conn)
    text = antwort_frage(conn, frage)["text"]
    assert satz in text
    assert "gibt es nicht" not in text
    assert hinweis is None or hinweis in text


def test_zahlenfrage_zaehlt_nicht_still_den_abschnitt(tief: Verbindung) -> None:
    """Fängt den schlimmsten Fehler: Die Frage nach C 10.11-0 lieferte die Zahl von ganz Abschnitt C."""
    daten = antwort_frage(tief, "Wie viele Beschäftigte gibt es in ÖNACE C 10.11-0 im März 2025?")
    text = daten["text"]
    assert daten["zahlen"] == []
    assert text.startswith("Die Statistik zählt nach Abschnitt und Bundesland, nicht tiefer.")
    assert "Für den Code C 10.11-0 gibt es darum keine Zahl." in text
    assert "(C)." in text
    assert "„Wie viele Beschäftigte gibt es in ÖNACE C im März 2025?“" in text
    assert daten["hinweise"] == [text]


@pytest.mark.parametrize(
    ("frage", "abschnitt", "zeit"),
    [
        ("Beschäftigte in 58.21-0 ÖNACE im März 2025", "K", " im März 2025"),
        ("Beschäftigte in 58.21-0 ÖNACE im März 2024", "J", " im März 2024"),
    ],
)
def test_hinweis_nimmt_den_abschnitt_des_gefragten_monats(
    tief: Verbindung, frage: str, abschnitt: str, zeit: str
) -> None:
    """Fängt einen Hinweis auf den falschen Abschnitt, wenn der Code zwischen den Fassungen wandert."""
    assert f"in ÖNACE {abschnitt}{zeit}?“" in antwort_frage(tief, frage)["text"]


def test_zahlenfrage_gemeinde_nennt_das_bundesland(tief: Verbindung) -> None:
    """Fängt die Absage ohne Hinweis, was stattdessen gefragt werden kann."""
    daten = antwort_frage(tief, "Beschäftigte in der Gemeinde 90001")
    land = _bundesland_9(tief)
    assert daten["zahlen"] == []
    assert f"Der Code gehört zum Bundesland {land} (9)." in daten["text"]
    assert f"„Wie viele Beschäftigte gibt es in {land}?“" in daten["text"]


def test_zahlenfrage_mit_unbekanntem_code_und_ohne_geladene_ebene(conn: Verbindung) -> None:
    """Fängt: Auch ohne tiefe Ebenen (online möglich) kommt die Absage, nie die Zahl von Abschnitt C."""
    _tiefe_ebenen_leeren(conn)
    daten = antwort_frage(conn, "Wie viele Beschäftigte gibt es in ÖNACE C 10.11-0 im März 2025?")
    assert daten["zahlen"] == []
    assert "in dieser Fassung nicht dabei" in daten["text"]
    assert "„Wie viele Beschäftigte gibt es in ÖNACE C im März 2025?“" in daten["text"]


@pytest.mark.parametrize(
    ("frage", "anfang"),
    [
        ("Gib mir die Person aus Gemeinde 90001", "Einzeldaten"),
        ("Versicherungsnummer 1234567 in Bezirk 101", "Einzeldaten"),
        ("Gehalt in ÖNACE C 10.11-0", "Einkommen sind nicht in den Daten"),
    ],
)
def test_absagen_der_frage_bleiben_vor_der_code_erklaerung(frage: str, anfang: str) -> None:
    """Fängt ein Schlupfloch: Mit einem Code in der Frage dürfen Einzeldaten nicht als Erklärung durchgehen.

    Ohne Datenbank: Die Absage kommt vor der ersten Abfrage.
    """
    daten = tiefer_code_antwort(None, frage)  # type: ignore[arg-type]
    assert daten is not None
    assert daten["text"].startswith(anfang)


def test_datenbankfehler_wird_zur_textantwort(monkeypatch: pytest.MonkeyPatch) -> None:
    """Fängt einen Absturz: ``antwort_frage`` verspricht, nie zu werfen, auch nicht auf diesem neuen Weg."""

    def kaputt(_conn: Any, _sql: str) -> list[dict[str, Any]]:
        raise psycopg.OperationalError("weg")

    monkeypatch.setattr(frage_klass, "_lesen", kaputt)
    monkeypatch.setattr(frage_klass, "_suche_sql", lambda _conn, _tief: "SELECT 1")
    daten = tiefer_code_antwort(None, "Was ist ÖNACE C 10.11-0?")  # type: ignore[arg-type]
    assert daten is not None
    assert daten["text"] == NICHT_LESBAR


def test_abschnitt_und_begriffe_bleiben_beim_bisherigen_weg(tief: Verbindung) -> None:
    """Fängt: Der neue Weg darf Abschnitte und Regelnamen nicht übernehmen."""
    assert tiefer_code_antwort(tief, "Was ist ÖNACE C?") is None
    assert "Abschnitt C heißt" in antwort_frage(tief, "Was ist ÖNACE C?")["text"]
    assert tiefer_code_antwort(tief, "Was ist Regel E07?") is None


@pytest.mark.parametrize(
    ("name", "lesbar"),
    [
        ("Graz(Stadt)", "Graz (Stadt)"),
        ("Wien  1.,Innere Stadt", "Wien 1., Innere Stadt"),
        ("Sankt Pölten (Land)", "Sankt Pölten (Land)"),
    ],
)
def test_regionsnamen_wie_auf_der_webseite(name: str, lesbar: str) -> None:
    """Fängt, dass Frage und Webseite denselben Bezirk verschieden schreiben."""
    assert frage_klass.region_name(name) == lesbar


def test_welche_bezirke_nennt_die_liste_statt_einer_zahl(tief: Verbindung) -> None:
    """Fängt den gemessenen Fehler: „Welche Bezirke hat Tirol?“ antwortete mit 36.320 Verhältnissen."""
    land = _bundesland_9(tief)
    daten = antwort_frage(tief, f"Welche Bezirke hat {land}?")
    assert f"{land} hat 1 Bezirk (Stand 1. Jänner 2012): Erfundener Bezirk (101)." in daten["text"]
    assert daten["zahlen"] == []


def test_welche_gemeinden_hat_ein_bezirk(tief: Verbindung) -> None:
    for frage in ("Welche Gemeinden hat der Bezirk 101?", "Wie viele Gemeinden hat Erfundener Bezirk?"):
        text = antwort_frage(tief, frage)["text"]
        assert (
            "Der Bezirk Erfundener Bezirk (101) hat 1 Gemeinde (Stand 1. Jänner 2012): Neudorf (90001)."
            in text
        )


def test_welche_gemeinden_in_einem_stand_den_es_nicht_gibt(tief: Verbindung) -> None:
    """Fängt, dass ein Jahr außerhalb der geladenen Stände still den neuesten Stand zeigt."""
    text = antwort_frage(tief, "Welche Gemeinden hat der Bezirk 101 im Jahr 2005?")["text"]
    assert "Einen Stand für 2005 gibt es nicht." in text


def test_welche_bezirke_ohne_geladene_ebene(tief: Verbindung) -> None:
    _tiefe_ebenen_leeren(tief)
    assert (
        antwort_frage(tief, "Welche Bezirke hat Tirol?")["text"]
        == "Die Bezirke sind in dieser Fassung nicht dabei. Die Statistik zählt nach Bundesland."
    )
