"""Positionsmatrix und Einordnung je Thema (PRD S6, Entscheid 7 in #44), reiner Code ohne Modell.

Zustimmung ≥ +1, Ablehnung ≤ −1, 0 = enthalten; ein Teilnehmer ohne Position zählt als enthalten. Je Thema:
Konsens (alle ≥ +1), Mehrheit (mehr als die Hälfte ≥ +1), abgelehnt (mehr als die Hälfte ≤ −1), sonst
offener Konflikt. Minderheit: bei Mehrheit die Ablehnenden, bei Ablehnung die Zustimmenden. Genau die
Hälfte reicht nie.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass, field
from typing import Any

KATEGORIEN = ("konsens", "mehrheit", "abgelehnt", "offener_konflikt")


@dataclass(frozen=True)
class Position:
    akteur: str
    thema: str
    wert: int
    begruendung: str
    beleg_ids: tuple[str, ...] = ()
    quelle: str = "zug"
    """`zug` oder `unveraendert` (aus der Vorrunde übernommen)."""


Runde = dict[str, dict[str, Position]]
"""Positionen einer Runde: Akteur → Thema → Position."""


@dataclass(frozen=True)
class Aenderung:
    runde: int
    akteur: str
    thema: str
    alt: int | None
    neu: int
    begruendung: str

    def als_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class Einordnung:
    kategorie: str
    zustimmend: tuple[str, ...]
    ablehnend: tuple[str, ...]
    enthalten: tuple[str, ...]
    minderheit: tuple[str, ...] = field(default=())

    def als_dict(self) -> dict[str, Any]:
        return {k: list(v) if isinstance(v, tuple) else v for k, v in asdict(self).items()}


def aenderungen(runde: int, vorher: Runde | None, jetzt: Runde) -> list[Aenderung]:
    """Positionsänderungen gegenüber der Vorrunde, sortiert nach Akteur und Thema.

    Eine Position, die es in der Vorrunde nicht gab, zählt als Änderung (alt = None); in Runde 1 gibt es
    keine Änderungen.
    """
    if vorher is None:
        return []
    liste = []
    for akteur in sorted(jetzt):
        for thema in sorted(jetzt[akteur]):
            neu = jetzt[akteur][thema]
            alt = vorher.get(akteur, {}).get(thema)
            if alt is None or alt.wert != neu.wert:
                liste.append(
                    Aenderung(
                        runde, akteur, thema, None if alt is None else alt.wert, neu.wert, neu.begruendung
                    )
                )
    return liste


def ordne_ein(werte: Mapping[str, int | None], teilnehmer: Sequence[str]) -> Einordnung:
    """Einordnung eines Themas über alle Teilnehmer; fehlende Werte zählen als enthalten."""
    dafuer = tuple(a for a in sorted(teilnehmer) if (werte.get(a) or 0) >= 1)
    dagegen = tuple(a for a in sorted(teilnehmer) if (werte.get(a) or 0) <= -1)
    enthalten = tuple(a for a in sorted(teilnehmer) if a not in dafuer and a not in dagegen)
    n = len(teilnehmer)
    if n and len(dafuer) == n:
        return Einordnung("konsens", dafuer, dagegen, enthalten)
    if 2 * len(dafuer) > n:
        return Einordnung("mehrheit", dafuer, dagegen, enthalten, minderheit=dagegen)
    if 2 * len(dagegen) > n:
        return Einordnung("abgelehnt", dafuer, dagegen, enthalten, minderheit=dafuer)
    return Einordnung("offener_konflikt", dafuer, dagegen, enthalten)


def werte(runde: Runde) -> dict[str, dict[str, int]]:
    """Nur die Werte: Akteur → Thema → Haltung."""
    return {a: {t: p.wert for t, p in themen.items()} for a, themen in runde.items()}


def klassifikation(runde: Runde, teilnehmer: Sequence[str], themen: Sequence[str]) -> dict[str, Einordnung]:
    """Einordnung je Thema auf den Positionen einer Runde (Endmatrix: letzte Runde)."""
    return {
        thema: ordne_ein({a: p[thema].wert for a, p in runde.items() if thema in p}, teilnehmer)
        for thema in themen
    }
