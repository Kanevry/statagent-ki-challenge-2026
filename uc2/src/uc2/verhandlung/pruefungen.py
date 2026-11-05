"""Prüfungen als Code (Entscheide 4 und 5 in #44).

`validiere_zug` ergänzt das Zugschema um das, was JSON-Schema nicht abdeckt (endliche Zahlen, eindeutige
Themen, Themen aus dem Auftrag, Bezug ab Runde 2). Ein Verstoß führt zu einer Wiederholung mit Hinweis, dann
zu `ungueltige_ausgabe`. `pruefe` läuft nach jedem gültigen Zug und liefert Befunde, die als Ereignisse
geschrieben werden: `zahl_ohne_beleg`, `beleg_ungueltig`, `zitat`, `zahl_widerspruch`.
"""

from __future__ import annotations

import math
import re
from collections.abc import Collection, Iterable, Sequence
from dataclasses import dataclass, field
from typing import Any

from uc2.akteure.pruefen import pruefe_zug
from uc2.verhandlung.belege import Beleg

ZAHL_MUSTER = re.compile(r"\d+([.,]\d+)?\s?(%|Prozent|Mio|Mrd|EUR|€|Tage|Stellen)")
"""Zahlenmuster aus PRD S5; Jahreszahlen 2000–2040 ohne Nachkommastellen sind ausgenommen."""
JAHRE = range(2000, 2041)
TOLERANZ = 0.05
"""Abweichung, bis zu der eine Zahl als gleich gilt (Experte und Abgleich mit `zahlen[]`)."""
ZITAT_WOERTER = 8
_WORT = re.compile(r"\w+")
_ZAHL_TEIL = re.compile(r"\d+([.,]\d+)?")


@dataclass(frozen=True)
class Befund:
    art: str
    daten: dict[str, Any] = field(default_factory=dict)


def validiere_zug(
    zug: object, themen: Collection[str], runde: int, selbst: str, teilnehmer: Collection[str]
) -> list[str]:
    """Fehlerliste; leer = gültig. Schema plus die Prüfungen, die das Schema nicht kann."""
    fehler = pruefe_zug(zug)
    if fehler or not isinstance(zug, dict):
        return fehler or ["zug: kein Objekt"]
    for i, z in enumerate(zug["zahlen"]):
        wert = z["wert"]
        if not isinstance(wert, int | float) or not math.isfinite(wert):
            fehler.append(f"zug: zahlen/{i}/wert ist keine endliche Zahl")
    gesehen: set[str] = set()
    for i, t in enumerate(zug["themen"]):
        if t["thema"] in gesehen:
            fehler.append(f"zug: themen/{i}: Thema {t['thema']!r} steht mehrfach im Zug")
        gesehen.add(t["thema"])
        if t["thema"] not in themen:
            fehler.append(
                f"zug: themen/{i}: Thema {t['thema']!r} steht nicht im Auftrag ({', '.join(themen)})"
            )
    andere = set(teilnehmer) - {selbst}
    for b in zug["bezug_auf"]:
        if b not in andere:
            fehler.append(f"zug: bezug_auf: {b!r} ist kein anderer Teilnehmer ({', '.join(sorted(andere))})")
    if runde >= 2 and not set(zug["bezug_auf"]) & andere:
        fehler.append("zug: bezug_auf muss ab Runde 2 mindestens einen anderen Teilnehmer nennen")
    return fehler


def _zahl(text: str) -> float:
    return float(text.replace(",", "."))


def zahlen_im_text(text: str) -> list[tuple[str, float]]:
    """Fundstellen des Zahlenmusters als (Fund, Wert); Jahreszahlen 2000–2040 entfallen."""
    funde = []
    for m in ZAHL_MUSTER.finditer(text):
        zahl_text = _ZAHL_TEIL.match(m.group(0))
        assert zahl_text is not None  # das Muster beginnt immer mit einer Zahl
        if m.group(1) is None and int(zahl_text.group(0)) in JAHRE:
            continue
        funde.append((m.group(0), _zahl(zahl_text.group(0))))
    return funde


def zahlen_ohne_beleg(zug: dict[str, Any]) -> list[Befund]:
    """Zahl in einer Begründung, die nicht (betragsgleich auf 0,05) in `zahlen[]` steht."""
    werte = [abs(float(z["wert"])) for z in zug["zahlen"]]
    befunde = []
    for t in zug["themen"]:
        for fund, wert in zahlen_im_text(t["begruendung"]):
            if not any(abs(wert - w) <= TOLERANZ for w in werte):
                befunde.append(Befund("zahl_ohne_beleg", {"thema": t["thema"], "fund": fund}))
    return befunde


def ungueltige_belege(zug: dict[str, Any], erlaubt: Collection[str]) -> list[Befund]:
    """Beleg-IDs (Themen und `zahlen[].quelle`) außerhalb der für Akteur und Runde geholten Belege."""
    befunde = []
    for t in zug["themen"]:
        for bid in t["beleg_ids"]:
            if bid not in erlaubt:
                befunde.append(Befund("beleg_ungueltig", {"thema": t["thema"], "beleg_id": bid}))
    for z in zug["zahlen"]:
        if z["quelle"] != "experte" and z["quelle"] not in erlaubt:
            befunde.append(
                Befund("beleg_ungueltig", {"thema": None, "beleg_id": z["quelle"], "in": "zahlen"})
            )
    return befunde


def _woerter(text: str) -> list[str]:
    return [w.casefold() for w in _WORT.findall(text)]


def _ketten(woerter: Sequence[str], n: int) -> Iterable[tuple[str, ...]]:
    return (tuple(woerter[i : i + n]) for i in range(len(woerter) - n + 1))


def zitate(zug: dict[str, Any], belege: Sequence[Beleg], n: int = ZITAT_WOERTER) -> list[Befund]:
    """Mindestens `n` aufeinanderfolgende Wörter wörtlich aus einem Beleg.

    Geprüft werden Begründung, Bedingungen und Zugeständnis je Thema.
    """
    quellen = [(b.beleg_id, set(_ketten(_woerter(b.text), n))) for b in belege]
    befunde = []
    for t in zug["themen"]:
        felder = [t["begruendung"], *t["bedingungen"], t["zugestaendnis"] or ""]
        for feld in felder:
            for kette in _ketten(_woerter(feld), n):
                treffer = next((bid for bid, menge in quellen if kette in menge), None)
                if treffer is not None:
                    befunde.append(
                        Befund(
                            "zitat", {"thema": t["thema"], "beleg_id": treffer, "woerter": " ".join(kette)}
                        )
                    )
                    break
    return befunde


def experten_werte(ergebnis: object) -> list[float]:
    """Alle Zahlen der Experten-Ausgabe (ohne Wahrheitswerte), sortiert und eindeutig."""
    werte: set[float] = set()

    def sammle(knoten: object) -> None:
        if isinstance(knoten, bool):
            return
        if isinstance(knoten, int | float):
            werte.add(float(knoten))
        elif isinstance(knoten, dict):
            for v in knoten.values():
                sammle(v)
        elif isinstance(knoten, list):
            for v in knoten:
                sammle(v)

    sammle(ergebnis)
    return sorted(werte)


def zahl_widersprueche(zug: dict[str, Any], werte: Sequence[float]) -> list[Befund]:
    """Quelle `experte`, aber kein Wert der Experten-Ausgabe auf 0,05 gleich.

    Verglichen wird der Betrag: „Wartezeit sinkt um 22,24 %“ mit 22.24 trifft den Experten-Wert −22.24.
    """
    befunde = []
    for z in zug["zahlen"]:
        if z["quelle"] != "experte":
            continue
        wert = float(z["wert"])
        if not any(abs(abs(wert) - abs(w)) <= TOLERANZ for w in werte):
            befunde.append(Befund("zahl_widerspruch", {"wert": wert, "einheit": z["einheit"]}))
    return befunde


def pruefe(zug: dict[str, Any], belege: Sequence[Beleg], werte: Sequence[float]) -> list[Befund]:
    """Alle Prüfungen nach einem gültigen Zug, in fester Reihenfolge."""
    erlaubt = {b.beleg_id for b in belege}
    return [
        *zahlen_ohne_beleg(zug),
        *ungueltige_belege(zug, erlaubt),
        *zitate(zug, belege),
        *zahl_widersprueche(zug, werte),
    ]


def haltungen_ohne_beleg(zug: dict[str, Any]) -> list[str]:
    """Themen, deren Haltung ≠ 0 ohne Beleg-ID begründet ist (Widerspruch für den Moderator)."""
    return [t["thema"] for t in zug["themen"] if t["haltung"] != 0 and not t["beleg_ids"]]
