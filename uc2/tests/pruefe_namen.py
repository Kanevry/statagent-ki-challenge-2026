#!/usr/bin/env python3
"""Eigenständiger Namens- und Parteienscan (Prüfskript, importiert keinen uc2-Laufzeitcode).

Aufruf: `python uc2/tests/pruefe_namen.py <dateien…> [--namensliste <datei>]`
Lauf-Modus (#43): `python uc2/tests/pruefe_namen.py --lauf <json|txt> --namensliste <datei> --autoren <datei>`

Im Lauf-Modus zählt der Scan nur Treffer gegen die beiden Listen (Index-Namensliste und Autor:in-Liste,
eine Zeile je Name, nur das Feld vor einem TAB, `#` kommentiert): ganze Wörter (kein Wortzeichen davor oder
danach), Schreibung wie in der Liste oder ganz in Großbuchstaben, ein Genitiv (s, S, ’s) zählt mit. Bei
JSON werden alle Zeichenketten gescannt, bei Text die ganze Datei. Ausgegeben werden nur Zahlen je Liste;
`--zeige` nennt die getroffenen Namen (nie in Berichte).
Exit 1 bei mindestens einem Treffer, 2 bei fehlender Liste, sonst 0.

Meldet je Datei:Zeile Treffer gegen (a) eine externe Namensliste (Datei außerhalb des Repos, Pfad über
`--namensliste` oder Env `UC2_NAMENSLISTE`; fehlt sie, nur ein Hinweis) und (b) Muster: akademischer Titel
+ Großwort, Zuschreibungen `sagt/so/betont/meint/kritisiert <Großwort>`, häufiger Vorname + Großwort,
Parteinamen. Exit 1 bei mindestens einem Treffer, sonst 0. Die Laufzeit (`uc2.akteure.namensscan`) setzt
dieselbe Logik getrennt um, damit dieses Skript ein unabhängiges Orakel bleibt.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

NAMENSLISTE_ENV = "UC2_NAMENSLISTE"

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

_GROSSBUCHSTABEN = "".join(c for c in map(chr, range(0x41, 0x250)) if c.isupper())
_NAME = r"(?P<name>[" + re.escape(_GROSSBUCHSTABEN) + r"][^\W\d_]+(?:['’-][^\W\d_]+)?)"
"""Großwort: beginnt mit einem lateinischen Großbuchstaben (auch É, Ö, Ł …), auch ganz in Großbuchstaben."""

_STOPP_TEXT = """
    der die das den dem des ein eine einer einen einem eines und oder aber sowie im in am an auf aus bei
    für mit nach von vom zu zum zur über unter vor durch gegen ohne um als wie wenn weil dass ist sind war
    hat haben wird werden kann soll muss nicht kein keine auch noch nur schon sich sie er es wir ihr ihre
    sein seine dies diese dieser dieses jede jeder jedes alle beide hier dort heute damals bisher
    herr frau minister ministerin präsident präsidentin direktor direktorin sprecher sprecherin primar
    primaria primarius obmann obfrau dr mag prof
    """

STOPPWOERTER: frozenset[str] = frozenset(_STOPP_TEXT.split())
"""Großwörter nach Titel oder Funktion, die kein Name sind (Satzanfang, Artikel, Funktionswörter).

Bewusst eine feste Liste statt der Substantive aus den gescannten Dateien: sonst würde ein Name in einer
Datei sich selbst freistellen. Funktionsbezeichnungen ohne Großwort danach („die Gesundheitsministerin
fordert …“) sind ohnehin kein Treffer, weil das Muster ein großgeschriebenes Folgewort verlangt."""

_TITEL = (
    r"(?<![\w.])(?:Univ\.-Prof|Priv\.-Doz|Dipl\.-Ing|DDr|MMag|Prim|Dr|Mag|Prof|Ing|DI)"
    r"(?:\.(?:in|a|ª)|in|ª)?\.?"
)
_FUNKTION = (
    r"(?<![\w])(?:Herr|Frau|Obmann|Obfrau|Primari(?:a|us)|Primar"
    r"|[^\W\d_]*(?:[Mm]inister|[Pp]räsident|[Dd]irektor|[Ss]precher)(?:in)?)"
)

PARTEIEN_OHNE_FALL = (
    r"ÖVP|SPÖ|FPÖ|NEOS|KPÖ|BZÖ|MFG|Bierpartei|Team Stronach|Liste Pilz|Volkspartei"
    r"|Sozialdemokrat[^\W\d_]*|Freiheitlich[^\W\d_]*"
)
"""Parteien, die ohne Rücksicht auf Groß-/Kleinschreibung gesucht werden (`Neos`, `övp`), mit Genitiv-s."""
PARTEIEN_GROSS = r"Grünen?|JETZT"
"""Nur in dieser Schreibung: `grüne`/`jetzt` sind Allgemeinwörter."""

MUSTER: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("titel", re.compile(_TITEL + r"(?:\s*(?:Dr|Mag|med|rer|nat|phil|iur|univ)\.(?:in|a)?)*\s*" + _NAME)),
    ("titel", re.compile(_NAME + r",?\s+(?:MBA|MSc|BSc|PhD|MPH|LL\.M\.?)(?![\w])")),
    ("funktion", re.compile(_FUNKTION + r"\s+" + _NAME)),
    ("zuschreibung", re.compile(r"(?<![\w])(?:sagt|so|betont|meint|kritisiert)\s+" + _NAME)),
    ("vorname", re.compile(r"(?<![\w])(?:" + "|".join(sorted(VORNAMEN)) + r")\s+" + _NAME)),
    ("partei", re.compile(r"(?<![\w])(?:" + PARTEIEN_OHNE_FALL + r")s?(?![\w])", re.IGNORECASE)),
    ("partei", re.compile(r"(?<![\w])(?:" + PARTEIEN_GROSS + r")s?(?![\w])")),
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


def absaetze(text: str) -> list[tuple[str, list[int]]]:
    """Absätze (durch Leerzeilen getrennt) mit normalisiertem Leerraum und Zeilennummer je Zeichen.

    So werden auch Namen gefunden, die über einen Zeilenumbruch laufen (`Dr.` / `Musterfrau`).
    """
    ergebnis: list[tuple[str, list[int]]] = []
    teile: list[str] = []
    zeilen: list[int] = []
    for nr, zeile in enumerate(text.splitlines(), start=1):
        if not zeile.strip():
            if teile:
                ergebnis.append(("".join(teile), zeilen))
                teile, zeilen = [], []
            continue
        for wort in zeile.split():
            if teile:
                teile.append(" ")
                zeilen.append(nr)
            teile.append(wort)
            zeilen.extend([nr] * len(wort))
    if teile:
        ergebnis.append(("".join(teile), zeilen))
    return ergebnis


def scanne_text(text: str, datei: str, namen: Sequence[str] = ()) -> list[Treffer]:
    """Alle Treffer je Absatz, gemeldet mit der Zeile des Fundbeginns.

    `namen` (externe Liste) sind ganze Wörter, Groß-/Kleinschreibung egal.
    """
    muster = list(MUSTER)
    if namen:
        liste = "|".join(re.escape(n) for n in namen)
        muster.append(("namensliste", re.compile(r"(?<![\w])(?:" + liste + r")(?![\w])", re.IGNORECASE)))
    treffer: list[Treffer] = []
    for absatz, zeilen in absaetze(text):
        for art, regel in muster:
            for m in regel.finditer(absatz):
                name = m.groupdict().get("name")
                if name is not None and name.casefold() in STOPPWOERTER:
                    continue
                treffer.append(Treffer(datei, zeilen[m.start()], art, m.group(0)))
    return sorted(treffer, key=lambda t: t.zeile)


def lies_liste(pfad: Path) -> list[str]:
    """Namen einer Liste: erstes Feld vor einem TAB, ohne Leer- und `#`-Zeilen."""
    namen = []
    for zeile in pfad.read_text(encoding="utf-8").splitlines():
        if not zeile.strip() or zeile.lstrip().startswith("#"):
            continue
        name = zeile.split("\t")[0].strip()
        if name:
            namen.append(name)
    return namen


def texte_aus(pfad: Path) -> list[str]:
    """Alle Zeichenketten einer JSON-Datei (rekursiv), sonst der ganze Text."""
    roh = pfad.read_text(encoding="utf-8")
    if pfad.suffix != ".json":
        return [roh]
    gefunden: list[str] = []

    def sammle(wert: object) -> None:
        if isinstance(wert, str):
            gefunden.append(wert)
        elif isinstance(wert, dict):
            for v in wert.values():
                sammle(v)
        elif isinstance(wert, list):
            for v in wert:
                sammle(v)

    sammle(json.loads(roh))
    return gefunden


_WORTANFANG = re.compile(r"(?<!\w)\w+")


_WORTZEICHEN = re.compile(r"\w")
_GENITIV = ("’s", "'s", "’S", "'S", "s", "S")
"""Genitiv nach dem Namen zählt mit, auch in Großschrift („MUSTERFRAUS“)."""


def zaehle_namen(texte: Sequence[str], namen: Sequence[str]) -> dict[str, int]:
    """Treffer je Name (Index über das erste Wort, schnell): ganzes Wort, Schreibung wie in der Liste oder
    ganz in Großbuchstaben, mit oder ohne Genitivendung (`_GENITIV`). „Musterfrau“ trifft also auch
    „MUSTERFRAU“, „Musterfraus“ und „MUSTERFRAUS“; sonst gilt Groß-/Kleinschreibung."""
    index: dict[str, list[tuple[str, str]]] = {}
    for name in set(namen):
        for variante in {name, name.upper()}:
            kopf = _WORTANFANG.match(variante)
            if kopf is not None:
                index.setdefault(kopf.group(0), []).append((variante, name))
    zahlen: dict[str, int] = {}
    for text in texte:
        for wort in _WORTANFANG.finditer(text):
            kopf = wort.group(0)
            kandidaten = [*index.get(kopf, ())]
            if kopf.endswith(("s", "S")):
                kandidaten.extend(index.get(kopf[:-1], ()))
            for variante, name in kandidaten:
                ende = wort.start() + len(variante)
                if not text.startswith(variante, wort.start()):
                    continue
                for endung in (*_GENITIV, ""):
                    nach = ende + len(endung)
                    if text.startswith(endung, ende) and not (
                        nach < len(text) and _WORTZEICHEN.match(text[nach])
                    ):
                        zahlen[name] = zahlen.get(name, 0) + 1
                        break
    return zahlen


def lauf(lauf_datei: Path, listen: dict[str, Path | None], zeige: bool) -> int:
    texte = texte_aus(lauf_datei)
    summe = 0
    for art, pfad in listen.items():
        if pfad is None:
            print(f"{art}: nicht angegeben", file=sys.stderr)
            continue
        if not pfad.is_file():
            print(f"{art}: Datei {pfad} fehlt", file=sys.stderr)
            return 2
        namen = lies_liste(pfad)
        zahlen = zaehle_namen(texte, namen)
        treffer = sum(zahlen.values())
        summe += treffer
        print(f"{art}: {treffer} Treffer, {len(zahlen)} verschiedene Namen, Liste {len(namen)} Namen")
        if zeige:
            for name, n in sorted(zahlen.items()):
                print(f"  {art}: {name} ×{n}")
    print(f"{summe} Treffer in {len(texte)} Texten aus {lauf_datei}", file=sys.stderr)
    return 1 if summe else 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Namens- und Parteienscan (UC2)")
    parser.add_argument("dateien", nargs="*", type=Path)
    parser.add_argument("--namensliste", type=Path, default=None, help=f"sonst Env {NAMENSLISTE_ENV}")
    parser.add_argument("--lauf", type=Path, default=None, help="Lauf-Ausgabe (json|txt) gegen beide Listen")
    parser.add_argument("--autoren", type=Path, default=None, help="Autor:in-Liste (nur mit --lauf)")
    parser.add_argument("--zeige", action="store_true", help="getroffene Namen ausgeben (nur lokal)")
    args = parser.parse_args(argv)
    if args.lauf is not None:
        if args.namensliste is None and args.autoren is None:
            parser.error("--lauf braucht --namensliste und/oder --autoren")
        return lauf(args.lauf, {"namensliste": args.namensliste, "autoren": args.autoren}, args.zeige)
    if not args.dateien:
        parser.error("Dateien oder --lauf angeben")
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
