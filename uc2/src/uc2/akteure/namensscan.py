"""Namens- und Parteienscan für Akteursdateien und Modellrollen (Laufzeit-Seite).

Bewusst eigenständig neben dem Prüfskript `uc2/tests/pruefe_namen.py`: das Prüfskript importiert keinen
Laufzeitcode und bleibt so ein unabhängiges Orakel. Muster:

- akademischer Titel vor oder nach einem großgeschriebenen Wort (`Mag. Musterfrau`, `Musterfrau, MBA`),
- Zuschreibung `sagt/so/betont/meint/kritisiert <Großwort>`,
- häufiger Vorname + großgeschriebenes Wort (Vornamen allein sind keine Personendaten),
- Parteinamen,
- optional eine externe Namensliste (eine Zeile je Name; Datei liegt nie im Repo).
"""

from __future__ import annotations

import os
import re
from collections.abc import Iterable, Sequence
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


def scanne_dateien(dateien: Iterable[Path], namen: Sequence[str] = ()) -> list[Treffer]:
    """Scan über mehrere Dateien."""
    treffer: list[Treffer] = []
    for pfad in dateien:
        treffer.extend(scanne_text(pfad.read_text(encoding="utf-8"), str(pfad), namen))
    return treffer
