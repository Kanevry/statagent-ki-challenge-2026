"""Lesender Zugriff auf Ergebnisse: Berichtszeitraum, letzter gültiger Lauf, Zellen eines Monats."""

from __future__ import annotations

import calendar
from dataclasses import dataclass
from datetime import date

from statagent.db import Verbindung


def monatserster(lieferung: str) -> date:
    jahr, monat = (int(t) for t in lieferung.split("-"))
    return date(jahr, monat, 1)


def monatsletzter(lieferung: str) -> date:
    jahr, monat = (int(t) for t in lieferung.split("-"))
    return date(jahr, monat, calendar.monthrange(jahr, monat)[1])


def monat_verschieben(lieferung: str, monate: int) -> str:
    jahr, monat = (int(t) for t in lieferung.split("-"))
    index = jahr * 12 + (monat - 1) + monate
    return f"{index // 12:04d}-{index % 12 + 1:02d}"


@dataclass(frozen=True)
class LaufStand:
    lauf_id: int
    lieferung: str
    regelsatz: str
    regelstand: str
    ergebnis_status: str
    ergebnis_hash: str


def letzter_lauf(conn: Verbindung, lieferung: str, regelsatz: str = "v1") -> LaufStand | None:
    """Der maßgebliche Lauf einer Lieferung und eines Regelsatzes: der jüngste veröffentlichte (endgültige),
    sonst der jüngste erfolgreiche (fertig oder unveraendert)."""
    zeile = conn.execute(
        """
        SELECT id, lieferung, regelsatz, regelstand, ergebnis_status, ergebnis_hash
        FROM meta.lauf
        WHERE lieferung = %s AND regelsatz = %s AND status IN ('fertig', 'unveraendert')
        ORDER BY (ergebnis_status = 'endgueltig') DESC, id DESC LIMIT 1
        """,
        (lieferung, regelsatz),
    ).fetchone()
    if zeile is None:
        return None
    return LaufStand(
        lauf_id=int(str(zeile["id"])),
        lieferung=str(zeile["lieferung"]),
        regelsatz=str(zeile["regelsatz"]),
        regelstand=str(zeile["regelstand"]),
        ergebnis_status=str(zeile["ergebnis_status"]),
        ergebnis_hash=str(zeile["ergebnis_hash"]),
    )


def monatswerte(conn: Verbindung, lieferung: str, regelsatz: str = "v1") -> list[dict[str, object]]:
    """Alle Zellen des Berichtsmonats aus stat.stat_beschaeftigte (Regelstand des letzten Laufs).

    Spalten: zeitraum_art, zeitraum_von, zeitraum_bis, region, oenace, oenace_version, geschlecht,
    qualifikation, alter (-1 = unbekannt), variable, wert, status, stand. Leer, wenn kein Lauf vorliegt.
    """
    stand = letzter_lauf(conn, lieferung, regelsatz)
    if stand is None:
        return []
    return conn.execute(
        """
        SELECT zeitraum_art, zeitraum_von, zeitraum_bis, region, oenace, oenace_version, geschlecht,
               qualifikation, alter, variable, wert, status, stand
        FROM stat.stat_beschaeftigte
        WHERE regelsatz = %s AND regelstand = %s AND zeitraum_bis BETWEEN %s AND %s
        ORDER BY region, oenace, geschlecht, qualifikation, alter, variable
        """,
        (regelsatz, stand.regelstand, monatserster(lieferung), monatsletzter(lieferung)),
    ).fetchall()
