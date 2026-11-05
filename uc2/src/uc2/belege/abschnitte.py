"""Abschnitte, Text-Hashes und Institutions-Tags.

Ein Artikel bis `max_zeichen` bleibt ein Abschnitt. Längere Artikel werden an Absatz- und Satzgrenzen
in Abschnitte von höchstens `max_zeichen` geteilt; der nächste Abschnitt beginnt mit den letzten Sätzen
des vorigen, solange sie zusammen höchstens `ueberlappung` Zeichen lang sind.
"""

from __future__ import annotations

import hashlib
import re
import unicodedata
from pathlib import Path
from typing import Any

import yaml

from uc2 import pfade

SATZGRENZE_RE = re.compile(r"(?<=[.!?…“\"])\s+(?=[A-ZÄÖÜ„\"0-9])")


def normalisiere(text: str) -> str:
    """NFC, Leerraum innerhalb der Zeilen zusammengezogen, leere Zeilen entfernt."""
    text = unicodedata.normalize("NFC", text)
    zeilen = (" ".join(z.split()) for z in text.split("\n"))
    return "\n".join(z for z in zeilen if z)


def text_hash(text: str) -> str:
    """sha256 über den normalisierten Text mit einheitlichem Leerraum (Zeilenumbrüche zählen nicht)."""
    return hashlib.sha256(" ".join(normalisiere(text).split()).encode("utf-8")).hexdigest()


def _einheiten(text: str, max_zeichen: int) -> list[tuple[str, str]]:
    """Sätze als (Trenner davor, Satz); Sätze über `max_zeichen` werden an Wortgrenzen geteilt."""
    einheiten: list[tuple[str, str]] = []
    for absatz in normalisiere(text).split("\n"):
        for n, satz in enumerate(SATZGRENZE_RE.split(absatz)):
            trenner = "\n" if n == 0 else " "
            while len(satz) > max_zeichen:
                schnitt = satz.rfind(" ", 0, max_zeichen + 1)
                if schnitt <= 0:
                    schnitt = max_zeichen
                einheiten.append((trenner, satz[:schnitt].strip()))
                satz = satz[schnitt:].strip()
                trenner = " "
            if satz:
                einheiten.append((trenner, satz))
    return einheiten


def _verbinde(einheiten: list[tuple[str, str]]) -> str:
    teile = [einheiten[0][1]]
    teile.extend(trenner + satz for trenner, satz in einheiten[1:])
    return "".join(teile)


def zerlege_abschnitte(text: str, max_zeichen: int, ueberlappung: int) -> list[str]:
    text = normalisiere(text)
    if len(text) <= max_zeichen:
        return [text] if text else []
    einheiten = _einheiten(text, max_zeichen)
    n = len(einheiten)
    abschnitte: list[str] = []
    a = 0
    while True:
        b = a
        laenge = 0
        while b < n and (b == a or laenge + 1 + len(einheiten[b][1]) <= max_zeichen):
            laenge += len(einheiten[b][1]) + (1 if b > a else 0)
            b += 1
        abschnitte.append(_verbinde(einheiten[a:b]))
        if b >= n:
            return abschnitte
        c = b
        ueber = 0
        while c - 1 > a and ueber + len(einheiten[c - 1][1]) + 1 <= ueberlappung:
            c -= 1
            ueber += len(einheiten[c][1]) + 1
        a = c


class Tagger:
    """Institutions-Tags: Alias als ganzes Wort, ohne Groß-/Kleinschreibung; Ergebnis sortierte IDs."""

    def __init__(self, institutionen: list[dict[str, Any]]) -> None:
        self._muster: list[tuple[str, re.Pattern[str]]] = []
        for inst in institutionen:
            aliase = sorted({str(a) for a in inst.get("aliase", [])}, key=len, reverse=True)
            alternativen = "|".join(re.escape(a) for a in aliase)
            self._muster.append(
                (str(inst["id"]), re.compile(rf"(?<!\w)(?:{alternativen})(?!\w)", re.IGNORECASE))
            )

    def tags(self, text: str) -> list[str]:
        return sorted(iid for iid, muster in self._muster if muster.search(text))


def lade_tagger(pfad: Path | None = None) -> Tagger:
    with (pfad or pfade.CONFIG / "institutionen.yaml").open(encoding="utf-8") as datei:
        roh: dict[str, Any] = yaml.safe_load(datei)
    return Tagger(list(roh["institutionen"]))
