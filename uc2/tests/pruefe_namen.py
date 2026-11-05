#!/usr/bin/env python3
"""Eigenständiger Namens- und Parteienscan (Prüfskript, importiert keinen uc2-Laufzeitcode).

Aufruf: `python uc2/tests/pruefe_namen.py <dateien…> [--namensliste <datei>]`

Meldet je Datei:Zeile Treffer gegen (a) eine externe Namensliste (Datei außerhalb des Repos, Pfad über
`--namensliste` oder Env `UC2_NAMENSLISTE`; fehlt sie, nur ein Hinweis) und (b) Muster: akademischer Titel
+ Großwort, Zuschreibungen `sagt/so/betont/meint/kritisiert <Großwort>`, häufiger Vorname + Großwort,
Parteinamen. Exit 1 bei mindestens einem Treffer, sonst 0. Die Laufzeit (`uc2.akteure.namensscan`) setzt
dieselbe Logik getrennt um, damit dieses Skript ein unabhängiges Orakel bleibt.
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

NAMENSLISTE_ENV = "UC2_NAMENSLISTE"

_GROSS = r"[A-ZÄÖÜ][a-zäöüß]+(?:-[A-ZÄÖÜ][a-zäöüß]+)?"

_VORNAMEN_TEXT = """
    Alexander Alois Andreas Anton Benjamin Bernhard Christian Christoph Daniel David Dominik Elias Erich
    Erwin Ewald Fabian Ferdinand Florian Franz Friedrich Georg Gerald Gerhard Gernot Gottfried Günter
    Günther Hannes Harald Heinz Helmut Herbert Hermann Hubert Jakob Johann Johannes Josef Julian Karl
    Kevin Klaus Konrad Kurt Leopold Ludwig Lukas Manfred Mario Markus Martin Matthias Maximilian Michael
    Moritz Noah Norbert Oliver Otto Patrick Paul Peter Philipp Raphael Reinhard René Richard Robert
    Roland Rudolf Rupert Sebastian Siegfried Simon Stefan Thomas Tobias Ulrich Valentin Walter Werner
    Wilhelm Wolfgang Felix Jonas Gabriel Leon Lorenz Emil Anna Andrea Angelika Astrid Barbara Beate
    Bettina Bianca Birgit Brigitte Carina Christa Christine Claudia Cornelia Daniela Doris Edith Elena
    Elisabeth Elke Emma Erika Eva Gabriele Gertraud Gisela Hannah Heidi Helga Herta Hildegard Ingrid
    Irene Johanna Julia Karin Katharina Kerstin Laura Lea Lena Leonie Lisa Magdalena Manuela Margit Maria
    Marie Marlene Martina Melanie Michaela Monika Natascha Nicole Nina Petra Renate Romana Rosemarie
    Sabine Sandra Sarah Silvia Simone Sonja Sophia Sophie Stefanie Susanne Tanja Teresa Theresa Ulrike
    Ursula Valentina Verena Veronika Waltraud Alexandra Corinna Pamela Ines Judith Miriam Selina
    """

VORNAMEN: frozenset[str] = frozenset(_VORNAMEN_TEXT.split())
"""Häufige Vornamen in Österreich (rund 170); Wörter, die auch deutsche Substantive sind, fehlen."""

PARTEIEN = (
    r"ÖVP|SPÖ|FPÖ|NEOS|KPÖ|BZÖ|Grünen?|Bierpartei|MFG|Team Stronach|Liste Pilz|JETZT|Volkspartei"
    r"|Sozialdemokrat\w*|Freiheitlich\w*"
)

MUSTER: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "titel",
        re.compile(
            r"(?<![\w.])(?:Univ\.-Prof|Priv\.-Doz|Dipl\.-Ing|DDr|MMag|Prim|Dr|Mag|Prof|Ing|DI)\.?"
            r"(?:\s+(?:Dr|Mag|med|rer|nat|phil|iur)\.)*\s+" + _GROSS
        ),
    ),
    ("titel", re.compile(_GROSS + r",?\s+(?:MBA|MSc|BSc|PhD|MPH|LL\.M\.?)(?![\w])")),
    ("zuschreibung", re.compile(r"\b(?:sagt|so|betont|meint|kritisiert)\s+" + _GROSS)),
    ("vorname", re.compile(r"\b(?:" + "|".join(sorted(VORNAMEN)) + r")\s+" + _GROSS)),
    ("partei", re.compile(r"(?<![\w])(?:" + PARTEIEN + r")(?![\w])")),
)


@dataclass(frozen=True)
class Treffer:
    """Ein Fund des Scans."""

    datei: str
    zeile: int
    art: str
    text: str

    def __str__(self) -> str:
        return f"{self.datei}:{self.zeile}: {self.art}: {self.text}"


def lade_namensliste(pfad: Path | None = None) -> tuple[list[str], str | None]:
    """Externe Namensliste (Pfad oder Env `UC2_NAMENSLISTE`); fehlt sie, kommt ein Hinweis zurück."""
    if pfad is None:
        env = os.environ.get(NAMENSLISTE_ENV)
        if not env:
            return [], f"Hinweis: keine Namensliste ({NAMENSLISTE_ENV} nicht gesetzt), nur Musterscan"
        pfad = Path(env)
    if not pfad.is_file():
        return [], f"Hinweis: Namensliste {pfad} nicht gefunden, nur Musterscan"
    namen = [
        z.strip()
        for z in pfad.read_text(encoding="utf-8").splitlines()
        if z.strip() and not z.startswith("#")
    ]
    return namen, None


def scanne_text(text: str, datei: str, namen: Sequence[str] = ()) -> list[Treffer]:
    """Alle Treffer je Zeile; `namen` sind ganze Wörter, Groß-/Kleinschreibung egal."""
    listen_muster = (
        re.compile(r"(?<![\w])(?:" + "|".join(re.escape(n) for n in namen) + r")(?![\w])", re.IGNORECASE)
        if namen
        else None
    )
    treffer: list[Treffer] = []
    for nr, zeile in enumerate(text.splitlines(), start=1):
        for art, muster in MUSTER:
            treffer.extend(Treffer(datei, nr, art, m.group(0)) for m in muster.finditer(zeile))
        if listen_muster is not None:
            treffer.extend(
                Treffer(datei, nr, "namensliste", m.group(0)) for m in listen_muster.finditer(zeile)
            )
    return treffer


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Namens- und Parteienscan (UC2)")
    parser.add_argument("dateien", nargs="+", type=Path)
    parser.add_argument("--namensliste", type=Path, default=None, help=f"sonst Env {NAMENSLISTE_ENV}")
    args = parser.parse_args(argv)
    namen, hinweis = lade_namensliste(args.namensliste)
    if hinweis:
        print(hinweis, file=sys.stderr)
    treffer: list[Treffer] = []
    for pfad in args.dateien:
        treffer.extend(scanne_text(pfad.read_text(encoding="utf-8"), str(pfad), namen))
    for t in treffer:
        print(t)
    print(f"{len(treffer)} Treffer in {len(args.dateien)} Dateien", file=sys.stderr)
    return 1 if treffer else 0


if __name__ == "__main__":
    sys.exit(main())
