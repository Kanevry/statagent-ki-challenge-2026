"""Golden-Set-Eichung: Monatswerte 08/2024 gegen den Beispielbericht des Veranstalters (2.880 Zellen).

Der Beispielbericht (`konfig.beispielbericht()`) liefert den Soll-Wert je Zahlenzelle. Der Ist-Wert wird
aus den Ergebniszellen des Monats (`ergebnis.monatswerte`) aufsummiert. Zuordnungen (Beschäftigungs-
kategorie, Bundesland, Altersgruppe) kommen aus den Klassifikationen der Datenbank, nicht aus dem Code.
Fest im Code steht nur das Layout des Berichts (welche Spalte welche Kombination aus Kategorie und
Geschlecht zeigt); das ist Berichtslayout und keine Zählregel.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, NamedTuple

from openpyxl import load_workbook
from openpyxl.utils import get_column_letter

from statagent import konfig
from statagent.db import Verbindung
from statagent.ergebnis import monatswerte

#: Spaltengruppen des Beispielberichts (Layout des Veranstalters, keine Zählregel): ALLE = Arbeiter, Angestellte,
#: Beamte; AB = „Angestellte und Beamte“ in Tab3–Tab13. Welche Qualifikation zu welcher Kategorie gehört, kommt aus
#: stat.klass_qualifikation; `klassen_laden` prüft, dass es diese Kategorien dort gibt.
ALLE = ("Arbeiter", "Angestellte", "Beamte")
AB = ("Angestellte", "Beamte")

#: Geschlechter der drei Spalten je Kombination: M + F (None), Männer, Frauen.
_GESCHLECHTER: tuple[str | None, ...] = (None, "M", "W")

#: Layout Tab1 (Spalten C..N) und Tab2 (Zeilen 8..19): je Kategorie drei Geschlechter.
_KATEGORIEN_TAB1_TAB2: tuple[tuple[str, ...], ...] = (ALLE, ("Arbeiter",), ("Angestellte",), ("Beamte",))

#: Layout Tab3..Tab12 und Tab13: neun Kombinationen (Kategorien x Geschlecht).
_KATEGORIEN_TAB3_TAB13: tuple[tuple[str, ...], ...] = (ALLE, ("Arbeiter",), AB)

_WIRTSCHAFTSTABELLEN = tuple(f"Tab{n}" for n in range(3, 13))
_VARIABLE = "Beschaeftigungsverhaeltnisse"


@dataclass(frozen=True)
class Spec:
    """Welche Summe eine Berichtszelle verlangt. `None` bedeutet jeweils „alle“."""

    bereich: str  # "region" (Tab1..Tab12) oder "alter" (Tab13)
    region: str | None  # Bezeichnung laut klass_region ("Österreich" = alle), nur bereich "region"
    zeile: (
        str | None
    )  # Wirtschaftszweig: "alle", "eingereiht", "unbekannt" oder Abschnittscode; bzw. Altersgruppe
    kategorien: tuple[str, ...]
    geschlecht: str | None


class SollZelle(NamedTuple):
    blatt: str
    zelle: str
    spec: Spec
    soll: int


@dataclass(frozen=True)
class Zelle:
    blatt: str
    zelle: str
    soll: int
    ist: int


@dataclass(frozen=True)
class Eichergebnis:
    lieferung: str
    zellen: list[Zelle] = field(default_factory=list)

    @property
    def anzahl(self) -> int:
        return len(self.zellen)

    @property
    def abweichungen(self) -> list[Zelle]:
        return [z for z in self.zellen if z.soll != z.ist]

    @property
    def stimmt(self) -> bool:
        return not self.abweichungen


@dataclass(frozen=True)
class Klassen:
    """Zuordnungen aus den Klassifikationen der Datenbank."""

    kategorie_je_qualifikation: Mapping[str, str]
    region_je_bezeichnung: Mapping[str, str]
    altersgruppe_je_alter: Mapping[int, str]
    #: Code(s) für „Wirtschaftszweig unbekannt“ laut stat.quellzuordnung (geliefert '<leer>'), keine Konstante.
    oenace_unbekannt: frozenset[str]


def klassen_laden(conn: Verbindung, regelsatz: str = "v1") -> Klassen:
    qualifikation = {
        str(z["code"]): str(z["beschaeftigungskategorie"])
        for z in conn.execute(
            "SELECT code, beschaeftigungskategorie FROM stat.klass_qualifikation"
        ).fetchall()
    }
    region = {
        str(z["bezeichnung"]): str(z["code"])
        for z in conn.execute(
            "SELECT code, bezeichnung FROM stat.klass_region WHERE version = 'BL' AND ebene = 'bundesland'"
        ).fetchall()
    }
    alter = {
        int(str(z["code"])): str(z["berichtsgruppe"])
        for z in conn.execute("SELECT code, berichtsgruppe FROM stat.klass_alter").fetchall()
    }
    fehlend = set(ALLE) - set(qualifikation.values())
    if fehlend:
        raise ValueError(
            f"Kategorien des Berichtslayouts fehlen in stat.klass_qualifikation: {sorted(fehlend)}"
        )
    unbekannt = frozenset(
        str(z["code"])
        for z in conn.execute(
            """SELECT DISTINCT code FROM stat.quellzuordnung
               WHERE regelsatz = %s AND merkmal = 'oenace' AND geliefert = '<leer>'""",
            (regelsatz,),
        ).fetchall()
    )
    return Klassen(qualifikation, region, alter, unbekannt)


# --------------------------------------------------------------------------------------------- Soll (xlsx)


def _zahl(wert: object) -> int | None:
    if isinstance(wert, bool) or not isinstance(wert, int | float):
        return None
    return int(wert)


def _text(wert: object) -> str:
    if isinstance(wert, float) and wert.is_integer():
        wert = int(wert)
    return "" if wert is None else str(wert).strip()


def _kombinationen(
    kategorien: tuple[tuple[str, ...], ...],
) -> list[tuple[tuple[str, ...], str | None]]:
    return [(k, g) for k in kategorien for g in _GESCHLECHTER]


def _wirtschaftszeile(label: str) -> str:
    if label.startswith("I n s"):
        return "alle"
    if label.startswith("davon"):
        return "eingereiht"
    if label == "Wirtschaftszweig unbekannt":
        return "unbekannt"
    return label


def soll_zellen(xlsx_pfad: Path | None = None) -> list[SollZelle]:
    """Liest alle Zahlenzellen des Beispielberichts (Tab1..Tab13) samt Bedeutung."""
    pfad = xlsx_pfad or konfig.beispielbericht()
    mappe = load_workbook(pfad, data_only=True, read_only=False)
    ergebnis: list[SollZelle] = []

    def hinzu(blatt: str, zeile: int, spalte: int, spec: Spec, wert: object) -> None:
        zahl = _zahl(wert)
        if zahl is None:
            raise ValueError(f"{blatt}!{get_column_letter(spalte)}{zeile}: keine Zahl ({wert!r})")
        ergebnis.append(SollZelle(blatt, f"{get_column_letter(spalte)}{zeile}", spec, zahl))

    # Tab1: Zeile 9, Spalten C..N
    ws: Any = mappe["Tab1"]
    for i, (kat, ges) in enumerate(_kombinationen(_KATEGORIEN_TAB1_TAB2)):
        hinzu("Tab1", 9, 3 + i, Spec("region", "Österreich", "alle", kat, ges), ws.cell(9, 3 + i).value)

    # Tab2: Kopfzeile 7 (Spalten C..M = Regionen), Zeilen 8..19 = Kombinationen
    ws = mappe["Tab2"]
    regionen = [_text(ws.cell(7, s).value) for s in range(3, 14)]
    for z, (kat, ges) in enumerate(_kombinationen(_KATEGORIEN_TAB1_TAB2)):
        for s, region in enumerate(regionen):
            spec = Spec("region", region, "alle", kat, ges)
            hinzu("Tab2", 8 + z, 3 + s, spec, ws.cell(8 + z, 3 + s).value)

    # Tab3..Tab12: Titel in A3 ("Gesamtes Bundesgebiet" bzw. "Bundesland <Name>"), Zeilen ab 10
    for blatt in _WIRTSCHAFTSTABELLEN:
        ws = mappe[blatt]
        titel = _text(ws["A3"].value)
        region = "Österreich" if titel == "Gesamtes Bundesgebiet" else titel.removeprefix("Bundesland ")
        for z in range(10, ws.max_row + 1):
            if _zahl(ws.cell(z, 4).value) is None:
                continue
            zeile = _wirtschaftszeile(_text(ws.cell(z, 2).value))
            for i, (kat, ges) in enumerate(_kombinationen(_KATEGORIEN_TAB3_TAB13)):
                spec = Spec("region", region, zeile, kat, ges)
                hinzu(blatt, z, 4 + i, spec, ws.cell(z, 4 + i).value)

    # Tab13: Alter, Zeilen ab 10, Spalten C..K
    ws = mappe["Tab13"]
    for z in range(10, ws.max_row + 1):
        if _zahl(ws.cell(z, 3).value) is None:
            continue
        gruppe = _text(ws.cell(z, 2).value)
        zeile = "alle" if gruppe == "Insgesamt" else gruppe
        for i, (kat, ges) in enumerate(_kombinationen(_KATEGORIEN_TAB3_TAB13)):
            hinzu("Tab13", z, 3 + i, Spec("alter", None, zeile, kat, ges), ws.cell(z, 3 + i).value)

    mappe.close()
    return ergebnis


# ---------------------------------------------------------------------------------------------- Ist (DB)


class Aggregator:
    """Summen der Monatszellen, vorverdichtet nach Region/Wirtschaftszweig und nach Altersgruppe."""

    def __init__(self, klassen: Klassen) -> None:
        self._klassen = klassen
        # (region-code, oenace, geschlecht, kategorie) -> Summe
        self._region: dict[tuple[str, str, str, str], int] = defaultdict(int)
        # (altersgruppe, geschlecht, kategorie) -> Summe
        self._alter: dict[tuple[str, str, str], int] = defaultdict(int)

    def aufnehmen(self, zeile: Mapping[str, object]) -> None:
        kategorie = self._klassen.kategorie_je_qualifikation[str(zeile["qualifikation"])]
        wert = int(str(zeile["wert"]))
        geschlecht = str(zeile["geschlecht"])
        alter = int(str(zeile["alter"]))
        if alter not in self._klassen.altersgruppe_je_alter:
            raise ValueError(f"Alter {alter} fehlt in stat.klass_alter")
        gruppe = self._klassen.altersgruppe_je_alter[alter]
        self._region[(str(zeile["region"]), str(zeile["oenace"]), geschlecht, kategorie)] += wert
        self._alter[(gruppe, geschlecht, kategorie)] += wert

    def summe(self, spec: Spec) -> int:
        geschlechter = ("M", "W") if spec.geschlecht is None else (spec.geschlecht,)
        if spec.bereich == "alter":
            return sum(
                wert
                for (gruppe, ges, kat), wert in self._alter.items()
                if (spec.zeile == "alle" or gruppe == spec.zeile)
                and ges in geschlechter
                and kat in spec.kategorien
            )
        if spec.region is None:
            raise ValueError("Spec ohne Region")
        regionen = self._klassen.region_je_bezeichnung
        if spec.region != "Österreich" and spec.region not in regionen:
            raise ValueError(f"Region {spec.region!r} fehlt in stat.klass_region")
        code = None if spec.region == "Österreich" else regionen[spec.region]
        return sum(
            wert
            for (reg, oenace, ges, kat), wert in self._region.items()
            if (code is None or reg == code)
            and self._zeile_passt(spec.zeile, oenace, self._klassen.oenace_unbekannt)
            and ges in geschlechter
            and kat in spec.kategorien
        )

    @staticmethod
    def _zeile_passt(zeile: str | None, oenace: str, unbekannt: frozenset[str]) -> bool:
        if zeile == "alle":
            return True
        if zeile == "eingereiht":
            return oenace not in unbekannt
        if zeile == "unbekannt":
            return oenace in unbekannt
        return oenace == zeile


def ist_aus_zeilen(
    zeilen: Iterable[Mapping[str, object]], klassen: Klassen, variable: str = _VARIABLE
) -> Aggregator:
    """Verdichtet die Zellen aus `monatswerte` (nur die genannte Variable) zum Aggregator."""
    agg = Aggregator(klassen)
    for zeile in zeilen:
        if str(zeile["variable"]) == variable:
            agg.aufnehmen(zeile)
    return agg


# -------------------------------------------------------------------------------------------- Eichung


def eichen(
    conn: Verbindung,
    lieferung: str = "2024-08",
    xlsx_pfad: Path | None = None,
    regelsatz: str = "v1",
) -> Eichergebnis:
    """Vergleicht die Monatswerte der Lieferung zellenweise mit dem Beispielbericht."""
    klassen = klassen_laden(conn, regelsatz)
    agg = ist_aus_zeilen(monatswerte(conn, lieferung, regelsatz), klassen)
    zellen = [Zelle(s.blatt, s.zelle, s.soll, agg.summe(s.spec)) for s in soll_zellen(xlsx_pfad)]
    return Eichergebnis(lieferung, zellen)


def bericht_text(ergebnis: Eichergebnis, max_zeilen: int = 40) -> str:
    """Kurzbericht: „Zellen N, abweichend M“, darunter je Abweichung Blatt, Zelle, Soll, Ist, Differenz."""
    abweichend = ergebnis.abweichungen
    zeilen = [f"Zellen {ergebnis.anzahl}, abweichend {len(abweichend)}"]
    for z in abweichend[:max_zeilen]:
        zeilen.append(f"{z.blatt} {z.zelle}: Soll {z.soll}, Ist {z.ist}, Differenz {z.ist - z.soll:+d}")
    if len(abweichend) > max_zeilen:
        zeilen.append(f"... und {len(abweichend) - max_zeilen} weitere")
    return "\n".join(zeilen)
