"""Abnahme der Monatszählung (Änderungsauftrag 2, GitLab #70 AC1).

Regel: Ein Verhältnis zählt im Berichtsmonat, wenn mindestens ein Zeitabschnitt mindestens einen Tag im Monat
besteht (BEGINN ≤ Monatsletzter und ENDE leer oder ≥ Monatserster). Je VVH zählt es einmal, die Merkmale
kommen aus dem letzten Abschnitt im Monat, das Alter in vollendeten Jahren am Monatsletzten.

Berichtsmonat ist 2024-09 (30 Tage). Die Testsätze tragen synthetische IDs ab 990000 und je Fall ein eigenes
Bundesland, das die Fixture-Lieferung 2024-09 nicht verwendet (2, 4, 5, 7, 8); so lassen sich die Zellen des
Falls ohne Rest der Lieferung prüfen. Jeder Test arbeitet auf einem frischen Datenbank-Klon (Fixture `conn`).
"""

from __future__ import annotations

import json

import pytest
from conftest import ROH_SPALTEN

from statagent.agenten.regelaenderung import regelsatz_sicherstellen
from statagent.db import Verbindung
from statagent.ergebnis import monatswerte
from statagent.lauf import lauf_ausfuehren

MONAT = "2024-09"
MONATSREGEL = {"zeitraum_art": "Monat", "von": "monatserster", "bis": "monatsletzter"}


def _satz(
    vvh: int,
    *,
    person: int,
    geboren: str = "1990-06-15",
    geschlecht: str = "M",
    beginn: str | None,
    ende: str | None,
    qual: str = "ArbeiterDV",
    oenace: str = "C",
    bundesland: str,
) -> tuple[str | None, ...]:
    return (MONAT, str(vvh), str(person), geboren, geschlecht, beginn, ende, qual, oenace, bundesland)


def _einfuegen(conn: Verbindung, saetze: list[tuple[str | None, ...]]) -> None:
    with conn.transaction():
        for s in saetze:
            conn.execute(
                f"INSERT INTO roh.lieferung ({ROH_SPALTEN}) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                s,
            )


def _monatsregelsatz(conn: Verbindung) -> None:
    """Legt v2 als Kopie von v1 an und stellt R2_R4 auf Monatszählung um."""
    regelsatz_sicherstellen(conn, "v2", "v1")
    conn.execute(
        """UPDATE meta.regel SET parameter = parameter || %s::jsonb
           WHERE regelsatz = 'v2' AND typ = 'zaehl' AND art = 'bestand'""",
        (json.dumps(MONATSREGEL),),
    )
    conn.commit()


def _rechnen(conn: Verbindung, regelsatz: str) -> None:
    erg = lauf_ausfuehren(conn, MONAT, regelsatz=regelsatz, gestartet_von=None, reihenfolge_pruefen=False)
    assert erg.status == "fertig"
    conn.commit()


def _zellen(conn: Verbindung, regelsatz: str, bundesland: str) -> list[tuple[str, str, str, int, int]]:
    """Zellen (oenace, geschlecht, qualifikation, alter, wert) eines Bundeslands, sortiert."""
    conn.commit()
    return sorted(
        (
            str(z["oenace"]),
            str(z["geschlecht"]),
            str(z["qualifikation"]),
            int(str(z["alter"])),
            int(str(z["wert"])),
        )
        for z in monatswerte(conn, MONAT, regelsatz)
        if z["region"] == bundesland and z["wert"] != 0
    )


def _monat(
    conn: Verbindung, saetze: list[tuple[str | None, ...]], bundesland: str
) -> list[tuple[str, str, str, int, int]]:
    _einfuegen(conn, saetze)
    _monatsregelsatz(conn)
    _rechnen(conn, "v2")
    return _zellen(conn, "v2", bundesland)


def test_ein_tages_fall_zaehlt_im_monat_aber_nicht_am_stichtag(conn: Verbindung) -> None:
    # Fängt: Monatszählung prüft weiter nur den Stichtag (BEGINN = ENDE = 15. fällt heraus) oder v1 zählt
    # plötzlich Abschnitte, die den Stichtag nicht erreichen.
    saetze = [_satz(990001, person=990101, beginn="2024-09-15", ende="2024-09-15", bundesland="2")]
    _einfuegen(conn, saetze)
    _rechnen(conn, "v1")
    assert _zellen(conn, "v1", "2") == []
    _monatsregelsatz(conn)
    _rechnen(conn, "v2")
    assert _zellen(conn, "v2", "2") == [("C", "M", "ArbeiterDV", 34, 1)]


def test_offenes_ende_zaehlt_und_alter_gilt_am_monatsletzten(conn: Verbindung) -> None:
    # Fängt: offenes ENDE (NULL) fällt aus der Zählung; Alter wird am Monatsersten/Beginn statt am
    # Monatsletzten gerechnet (Geburtstag 30.09. = 44, Geburtstag 01.10. = noch 43).
    saetze = [
        _satz(990002, person=990102, geboren="1980-09-30", beginn="2020-01-01", ende=None, bundesland="4"),
        _satz(
            990003,
            person=990103,
            geboren="1980-10-01",
            geschlecht="W",
            beginn="2020-01-01",
            ende=None,
            bundesland="4",
        ),
    ]
    assert _monat(conn, saetze, "4") == [
        ("C", "M", "ArbeiterDV", 44, 1),
        ("C", "W", "ArbeiterDV", 43, 1),
    ]


@pytest.mark.parametrize("ende_erster", ["2024-09-09", "2024-09-10"])
def test_zwei_abschnitte_zaehlen_einmal_mit_merkmalen_des_spaeteren(
    conn: Verbindung, ende_erster: str
) -> None:
    # Fängt: VVH mit Wechsel am 10. zählt doppelt (je Abschnitt) oder behält die Merkmale des früheren
    # Abschnitts; der Fall ENDE = 10. (Überlappung am Wechseltag) darf die Wahl nicht kippen.
    saetze = [
        _satz(
            990004,
            person=990104,
            beginn="2024-01-01",
            ende=ende_erster,
            qual="ArbeiterDV",
            oenace="C",
            bundesland="5",
        ),
        _satz(
            990004,
            person=990104,
            beginn="2024-09-10",
            ende=None,
            qual="AngestellteDV",
            oenace="G",
            bundesland="5",
        ),
    ]
    assert _monat(conn, saetze, "5") == [("G", "M", "AngestellteDV", 34, 1)]


def test_zwei_vvh_derselben_person_zaehlen_beide(conn: Verbindung) -> None:
    # Fängt: Verhältnisse werden nach PERSON_ID statt nach VVH_ID verdichtet (Wert 1 statt 2).
    saetze = [
        _satz(990005, person=990105, beginn="2020-01-01", ende=None, bundesland="7"),
        _satz(990006, person=990105, beginn="2024-09-20", ende=None, bundesland="7"),
    ]
    assert _monat(conn, saetze, "7") == [("C", "M", "ArbeiterDV", 34, 2)]


@pytest.mark.parametrize(
    ("beginn", "ende", "zaehlt"),
    [
        ("2023-01-01", "2024-08-31", False),  # Ende am Vormonatsletzten
        ("2024-10-01", None, False),  # Beginn am Folgemonatsersten
        ("2023-01-01", "2024-09-01", True),  # Ende am Monatsersten
        ("2024-09-30", None, True),  # Beginn am Monatsletzten
    ],
)
def test_monatsgrenzen(conn: Verbindung, beginn: str, ende: str | None, zaehlt: bool) -> None:
    # Fängt: Off-by-one an den Monatsgrenzen (< statt ≤ beim Monatsersten bzw. Monatsletzten, Vor- oder
    # Folgemonat zählt mit).
    saetze = [_satz(990007, person=990107, beginn=beginn, ende=ende, bundesland="8")]
    soll = [("C", "M", "ArbeiterDV", 34, 1)] if zaehlt else []
    assert _monat(conn, saetze, "8") == soll
