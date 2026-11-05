"""Prüfungen als Code (Entscheide 4 und 5 in #44).

`validiere_zug` ergänzt das Zugschema um das, was JSON-Schema nicht abdeckt (endliche Zahlen, eindeutige
Themen, Themen aus dem Auftrag, Bezug ab Runde 2). Ein Verstoß führt zu einer Wiederholung mit Hinweis, dann
zu `ungueltige_ausgabe`. `pruefe` läuft nach jedem gültigen Zug und liefert Befunde, die als Ereignisse
geschrieben werden: `zahl_ohne_beleg`, `beleg_ungueltig`, `zitat`, `zahl_widerspruch`.

Die Zahlerkennung (`ZIFFERN`, `zahlwert`) liest dasselbe wie das Orakel `tests/pruefe_lauf.py`; das Orakel
trägt eine eigene Kopie und importiert uc2 nicht.
"""

from __future__ import annotations

import math
import re
from collections.abc import Collection, Iterable, Sequence
from dataclasses import dataclass, field
from typing import Any

from uc2.akteure.pruefen import pruefe_zug
from uc2.verhandlung.belege import Beleg

ZIFFERN = re.compile(r"(?<![\d.,])\d+(?:[.,]\d+)*")
"""Eine vollständige Zifferngruppe, nie mitten in einer anderen Zahl begonnen (wie `tests/pruefe_lauf.py`)."""
EINHEIT = re.compile(r"\s?(?:%|Prozent|Mio|Mrd|EUR|€|Tage|Stellen)")
"""Einheiten aus PRD S5; eine Zahl zählt in einer Begründung nur mit einer dieser Einheiten direkt danach."""
JAHRE = range(2000, 2041)
"""Ganze Zahlen in diesem Bereich gelten als Jahreszahlen und entfallen."""
TOLERANZ = 0.05
"""Abweichung, bis zu der eine Zahl als gleich gilt (Experte, Beleg und Abgleich mit `zahlen[]`)."""
ZITAT_WOERTER = 8
GRUND_BELEG = "Zahl steht nicht im Beleg"
ERGEBNIS_KENNZAHLEN = ("wartezeit_aenderung_prozent", "kosten_aenderung_prozent", "mehrkosten_mio_eur")
"""Kennzahlen des Rechenmodells, gegen die `zahl_widerspruch` prüft (je Modus, Min, Max)."""
_WORT = re.compile(r"\w+")


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


def zahlwert(gruppe: str) -> float | None:
    """Zifferngruppe nach deutscher Schreibweise als Zahl; `None`, wenn sie nicht eindeutig lesbar ist.

    - Ein Komma ist das Dezimalzeichen („3,5“).
    - Ein einzelner Punkt vor genau drei Ziffern ist ein Tausenderpunkt („12.000“), außer die Zahl beginnt mit
      0 („0.125“); sonst ist er das Dezimalzeichen („22.24“, wie Modelle es oft schreiben).
    - Mehrere Trenner: Tausenderpunkte, höchstens ein Dezimalkomma am Ende („1.234.567“, „1.234,5“).
    """
    teile = re.split(r"[.,]", gruppe)
    trenner = [c for c in gruppe if c in ".,"]
    if not trenner:
        return float(gruppe)
    if len(trenner) == 1:
        if trenner[0] == "." and len(teile[1]) == 3 and teile[0] != "0":
            return float(teile[0] + teile[1])
        return float(f"{teile[0]}.{teile[1]}")
    tausender, letzter = trenner[:-1], trenner[-1]
    gruppen = teile[1:] if letzter == "." else teile[1:-1]
    if set(tausender) != {"."} or any(len(g) != 3 for g in gruppen):
        return None
    if letzter == ",":
        return float("".join(teile[:-1]) + "." + teile[-1])
    return float("".join(teile))


def zahlen_im_text(text: str) -> list[tuple[str, float | None]]:
    """(Fund, Wert) je Zahl mit Einheit (PRD S5); Jahreszahlen 2000–2040 entfallen, unlesbar = `None`."""
    funde: list[tuple[str, float | None]] = []
    for m in ZIFFERN.finditer(text):
        einheit = EINHEIT.match(text, m.end())
        if einheit is None:
            continue
        gruppe = m.group(0)
        if gruppe.isdigit() and int(gruppe) in JAHRE:
            continue
        funde.append((gruppe + einheit.group(0), zahlwert(gruppe)))
    return funde


def zahlwerte(text: str) -> list[float]:
    """Alle lesbaren Zahlen eines Texts, mit oder ohne Einheit (Abgleich einer Zahl mit ihrem Beleg)."""
    werte = (zahlwert(m.group(0)) for m in ZIFFERN.finditer(text))
    return [w for w in werte if w is not None]


def gleich(a: float, b: float) -> bool:
    """Betragsgleich auf `TOLERANZ`: „sinkt um 22,24 %“ (22.24) trifft −22.24."""
    return abs(abs(a) - abs(b)) <= TOLERANZ


def zahlen_ohne_beleg(zug: dict[str, Any]) -> list[Befund]:
    """Zahl in einer Begründung, die nicht (betragsgleich auf 0,05) in `zahlen[]` steht."""
    werte = [float(z["wert"]) for z in zug["zahlen"]]
    befunde = []
    for t in zug["themen"]:
        for fund, wert in zahlen_im_text(t["begruendung"]):
            if wert is None or not any(gleich(wert, w) for w in werte):
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


def zahlen_nicht_im_beleg(zug: dict[str, Any], belege: Sequence[Beleg]) -> list[Befund]:
    """Zahl in `zahlen[]` mit einer geholten Beleg-ID als Quelle, die im Text dieses Belegs nicht vorkommt.

    Verglichen wird mit `text_modell` (was das Modell gesehen hat), betragsgleich auf 0,05, Einheit egal: Ein
    Beleg schreibt oft „999 Millionen“, wo der Zug „999 Mio EUR“ einträgt. Grenze: Eine Umrechnung („1,2 Mrd“
    gegen 1200 Mio) gilt als nicht belegt. Ungültige Beleg-IDs meldet schon `ungueltige_belege`.
    """
    texte = {b.beleg_id: zahlwerte(b.text_modell) for b in belege}
    befunde = []
    for z in zug["zahlen"]:
        werte = texte.get(z["quelle"])
        if werte is None:
            continue
        wert = float(z["wert"])
        if not any(gleich(wert, w) for w in werte):
            befunde.append(
                Befund(
                    "zahl_ohne_beleg",
                    {
                        "thema": None,
                        "in": "zahlen",
                        "wert": wert,
                        "einheit": z["einheit"],
                        "quelle": z["quelle"],
                        "grund": GRUND_BELEG,
                    },
                )
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


ZITAT_ERSATZ = "[Zitat]"


def sperre_zitat_text(text: str, ketten: Collection[tuple[str, ...]], n: int = ZITAT_WOERTER) -> str:
    """Jede Stelle aus mindestens `n` Wörtern, die wörtlich in `ketten` steht, wird zu „[Zitat]“.

    Überlappende und aneinanderstoßende Treffer werden zu einer Stelle zusammengefasst; der Text zwischen
    erstem und letztem Wort der Stelle fällt weg, Satzzeichen davor und danach bleiben.
    """
    if not ketten:
        return text
    woerter = list(_WORT.finditer(text))
    gefaltet = [w.group(0).casefold() for w in woerter]
    stellen: list[list[int]] = []
    for i in range(len(woerter) - n + 1):
        if tuple(gefaltet[i : i + n]) not in ketten:
            continue
        if stellen and i <= stellen[-1][1] + 1:
            stellen[-1][1] = i + n - 1
        else:
            stellen.append([i, i + n - 1])
    for erstes, letztes in reversed(stellen):
        text = text[: woerter[erstes].start()] + ZITAT_ERSATZ + text[woerter[letztes].end() :]
    return text


def sperre_zitate(zug: dict[str, Any], belege: Sequence[Beleg], n: int = ZITAT_WOERTER) -> dict[str, Any]:
    """Der Zug mit gesperrten Übernahmen (#137): Begründung, Bedingungen und Zugeständnis je Thema.

    Gleiche Felder und gleicher Bezug (`text_modell`) wie `zitate`; das Ereignis `zitat` bleibt als Hinweis,
    die Übernahme selbst wird nicht mehr gespeichert oder veröffentlicht.
    """
    ketten: set[tuple[str, ...]] = set()
    for b in belege:
        ketten.update(_ketten(_woerter(b.text), n))
    if not ketten:
        return zug
    themen = []
    for t in zug["themen"]:
        zugestaendnis = t["zugestaendnis"]
        themen.append(
            {
                **t,
                "begruendung": sperre_zitat_text(t["begruendung"], ketten, n),
                "bedingungen": [sperre_zitat_text(b, ketten, n) for b in t["bedingungen"]],
                "zugestaendnis": (
                    sperre_zitat_text(zugestaendnis, ketten, n) if zugestaendnis else zugestaendnis
                ),
            }
        )
    return {**zug, "themen": themen}


def _zahl_oder_none(wert: object) -> float | None:
    if isinstance(wert, bool) or not isinstance(wert, int | float):
        return None
    return float(wert)


def experten_ergebniswerte(ergebnis: dict[str, Any]) -> list[float]:
    """Nur die vom Rechenmodell berechneten Werte aus `uc2.experte.modell.ergebnis()`, sortiert und eindeutig.

    - `kennzahlen`: Wartezeit- und Kostenänderung in Prozent sowie Mehrkosten in Mio EUR, je Modus, Min, Max;
    - je Maßnahme `wirkung_prozent` und `mehrkosten_mio_eur`;
    - je Jahr des Jahrespfads alle Werte außer der Jahreszahl `jahr`.

    Eingaben zählen nicht: Ziel und Zieljahr (Vorgabe), Annahmen, Maßnahmenumfang, Zahl der Ecken. Sonst ginge
    `{wert: -20, quelle: "experte"}` (das Ziel) als Rechenergebnis durch, obwohl das Modell −14 % rechnet.
    """
    werte: set[float] = set()

    def nimm(wert: object) -> None:
        zahl = _zahl_oder_none(wert)
        if zahl is not None:
            werte.add(zahl)

    kennzahlen = ergebnis.get("kennzahlen") or {}
    for name in ERGEBNIS_KENNZAHLEN:
        spanne = kennzahlen.get(name) or {}
        for teil in ("modus", "min", "max"):
            nimm(spanne.get(teil))
    for m in ergebnis.get("massnahmen") or []:
        nimm(m.get("wirkung_prozent"))
        nimm(m.get("mehrkosten_mio_eur"))
    for jahr in ergebnis.get("jahrespfad") or []:
        for name, wert in jahr.items():
            if name != "jahr":
                nimm(wert)
    return sorted(werte)


def zahl_widersprueche(zug: dict[str, Any], werte: Sequence[float]) -> list[Befund]:
    """Quelle `experte`, aber kein Ergebniswert des Rechenmodells (`experten_ergebniswerte`) auf 0,05 gleich.

    Verglichen wird der Betrag: „Wartezeit sinkt um 22,24 %“ mit 22.24 trifft den Experten-Wert −22.24.
    """
    befunde = []
    for z in zug["zahlen"]:
        if z["quelle"] != "experte":
            continue
        wert = float(z["wert"])
        if not any(gleich(wert, w) for w in werte):
            befunde.append(Befund("zahl_widerspruch", {"wert": wert, "einheit": z["einheit"]}))
    return befunde


def pruefe(zug: dict[str, Any], belege: Sequence[Beleg], werte: Sequence[float]) -> list[Befund]:
    """Alle Prüfungen nach einem gültigen Zug, in fester Reihenfolge."""
    erlaubt = {b.beleg_id for b in belege}
    return [
        *zahlen_ohne_beleg(zug),
        *ungueltige_belege(zug, erlaubt),
        *zahlen_nicht_im_beleg(zug, belege),
        *zitate(zug, belege),
        *zahl_widersprueche(zug, werte),
    ]


def haltungen_ohne_beleg(zug: dict[str, Any]) -> list[str]:
    """Themen, deren Haltung ≠ 0 ohne Beleg-ID begründet ist (Widerspruch für den Moderator)."""
    return [t["thema"] for t in zug["themen"] if t["haltung"] != 0 and not t["beleg_ids"]]
