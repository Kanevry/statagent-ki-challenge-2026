"""Pensionsstatistik 2018–2025 (#77): Meldungen der Träger einlesen, prüfen, ausgeben.

Jeder Träger liefert seine Zahlen in einem eigenen Excel-Format. Der Code kennt nur die Lese-Arten (``parser``). Welche
Formate es gibt, wie sie aussehen und welcher Wert auf welchen Code führt, steht in ``meta.regel`` (Art
``pension_format``) und ``stat.quellzuordnung`` (Regelsatz ``pensionen-v1``). Unbekanntes bricht das Laden ab.

Importiert ``plattform.llm`` nicht: Die Zahlen entstehen ohne Sprachmodell, zwei Läufe liefern denselben Hash.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections import defaultdict
from collections.abc import Iterable, Iterator
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

from openpyxl import load_workbook
from openpyxl.utils import coordinate_to_tuple, get_column_letter
from openpyxl.worksheet.worksheet import Worksheet

from statagent import konfig
from statagent.db import Verbindung
from statagent.regeln import Regel, name_pruefen, regeln_freigeben, regeln_laden, regelstand

REGELSATZ = "pensionen-v1"
VARIABLE = "Pensionen"
PENSIONEN_ORDNER = "pensionen"
ERSTES_JAHR, LETZTES_JAHR = 2018, 2025
TABELLEN = ("T12", "T13")
#: Vierstellige Jahreszahl in Kopfzeilen und Blattnamen; im Fingerabdruck steht dafür JJJJ.
_JAHR = re.compile(r"(?<!\d)((?:19|20)\d{2})(?!\d)")
_TEXTZAHL = re.compile(r"^\d{1,3}(\.\d{3})*$|^\d+$")


class PensionFehler(ValueError):
    """Eine Meldung passt nicht zu den Regeln; die Meldung sagt in einem Satz, wo und warum."""


class FormatUnbekannt(PensionFehler):
    """Der Fingerabdruck einer Datei passt zu keinem bekannten Format, oder zu mehr als einem."""


@dataclass(frozen=True)
class Format:
    """Eine Formatregel aus ``meta.regel``: Fingerabdruck und wie die Datei zu lesen ist."""

    regel: str
    quelle: str
    parser: str
    jahr_von: int
    jahr_bis: int
    blaetter: tuple[str, ...]
    kopf: tuple[dict[str, Any], ...]
    tabellen: dict[str, dict[str, Any]]
    jahr_zelle: dict[str, str] | None = None
    traeger_zelle: str | None = None
    zeitraum_spalte: str | None = None

    @classmethod
    def aus_regel(cls, regel: Regel) -> Format:
        p = regel.parameter
        return cls(
            regel=regel.name,
            quelle=str(p["quelle"]),
            parser=str(p["parser"]),
            jahr_von=int(p["jahre"][0]),
            jahr_bis=int(p["jahre"][1]),
            blaetter=tuple(p["blaetter"]),
            kopf=tuple(p["kopf"]),
            tabellen=dict(p["tabellen"]),
            jahr_zelle=p.get("jahr_zelle"),
            traeger_zelle=p.get("traeger_zelle"),
            zeitraum_spalte=p.get("zeitraum_spalte"),
        )


@dataclass(frozen=True)
class Knoten:
    """Ein Code einer Klassifikation mit Elterncode und Gültigkeit."""

    code: str
    eltern: str | None
    von: date
    bis: date | None


@dataclass
class Regelwerk:
    """Alles, was das Lesen braucht, aus der Datenbank (Tests bauen es von Hand)."""

    formate: list[Format]
    zuordnung: dict[tuple[str, str, str], str]  # (Quelle, Merkmal, geliefert) -> Code
    traeger: dict[str, Knoten]
    arten: dict[str, Knoten]

    def code(self, quelle: str, merkmal: str, geliefert: object, wo: str) -> str:
        text = str(geliefert).strip() if geliefert is not None else ""
        treffer = self.zuordnung.get((quelle, merkmal, text))
        if treffer is None:
            raise PensionFehler(f"{wo}: „{text}“ hat keine Zuordnung für {merkmal} ({quelle}).")
        return treffer

    def hat_kinder(self, baum: dict[str, Knoten], code: str) -> bool:
        return any(k.eltern == code for k in baum.values())

    def bereiche(self, quelle: str) -> set[str]:
        """Die Bereiche, die eine Quelle melden muss: alle ihre Zuordnungen ohne untergeordnete Codes."""
        return {
            code
            for (q, merkmal, _), code in self.zuordnung.items()
            if q == quelle and merkmal == "versicherungstraeger" and not self.hat_kinder(self.traeger, code)
        }

    def blaetter_unter(self, baum: dict[str, Knoten], code: str) -> set[str]:
        kinder = [k.code for k in baum.values() if k.eltern == code]
        if not kinder:
            return {code}
        return {b for k in kinder for b in self.blaetter_unter(baum, k)}


@dataclass(frozen=True)
class Rohzelle:
    """Eine Zahl aus der Datei, noch mit den Texten des Trägers. ``art`` None: Summenspalte der Tabelle."""

    tabelle: str
    traeger: object
    art: object
    geschlecht: object
    wert: object
    blatt: str
    zelle: str


@dataclass(frozen=True)
class Wert:
    jahr: int
    traeger: str
    art: str
    geschlecht: str
    wert: int
    blatt: str
    zelle: str


@dataclass(frozen=True)
class Summe:
    """Prüfwert aus der Datei; ``geschlecht`` None heißt über beide Geschlechter."""

    jahr: int
    traeger: str
    art: str
    geschlecht: str | None
    gemeldet: int
    gerechnet: int
    blatt: str
    zelle: str


@dataclass
class DateiErgebnis:
    datei: str
    jahr: int
    format: Format
    sha256: str
    werte: list[Wert] = field(default_factory=list)
    summen: list[Summe] = field(default_factory=list)


# --------------------------------------------------------------------------------------------- Regeln aus der DB


def regelwerk_laden(conn: Verbindung) -> Regelwerk:
    regeln = [r for r in regeln_laden(conn, REGELSATZ) if r.art == "pension_format"]
    if not regeln:
        raise PensionFehler(f"Regelsatz {REGELSATZ} fehlt: zuerst `uc3 db init`.")
    zuordnung = {
        (str(z["quelle"]), str(z["merkmal"]), str(z["geliefert"])): str(z["code"])
        for z in conn.execute(
            "SELECT quelle, merkmal, geliefert, code FROM stat.quellzuordnung WHERE regelsatz = %s",
            (REGELSATZ,),
        ).fetchall()
    }

    def baum(tabelle: str) -> dict[str, Knoten]:
        zeilen = conn.execute(
            f"SELECT code, uebergeordnet, gueltig_von, gueltig_bis FROM stat.{tabelle}"
        ).fetchall()
        return {
            str(z["code"]): Knoten(
                str(z["code"]),
                None if z["uebergeordnet"] is None else str(z["uebergeordnet"]),
                z["gueltig_von"],  # type: ignore[arg-type]
                z["gueltig_bis"],  # type: ignore[arg-type]
            )
            for z in zeilen
        }

    return Regelwerk(
        [Format.aus_regel(r) for r in regeln],
        zuordnung,
        baum("klass_versicherungstraeger"),
        baum("klass_pensionsart"),
    )


# ---------------------------------------------------------------------------------------------------- Formate


def _maske(wert: object) -> object:
    return _JAHR.sub("JJJJ", wert) if isinstance(wert, str) else wert


def _kopfzeile(ws: Worksheet, nummer: int) -> list[object]:
    zellen = [_maske(z.value) for z in ws[nummer]]
    while zellen and zellen[-1] is None:
        zellen.pop()
    return zellen


def _blatt(wb: Any, name: str) -> Worksheet:
    """Blatt nach seinem maskierten Namen (``Pensionen JJJJ``)."""
    for ws in wb.worksheets:
        if _maske(ws.title) == name:
            return ws  # type: ignore[no-any-return]
    raise PensionFehler(f"Blatt „{name}“ fehlt.")


def format_erkennen(wb: Any, formate: Iterable[Format], datei: str) -> Format:
    """Vergleicht Blätter und Kopfzeilen der Datei mit den Formatregeln. Genau ein Treffer, sonst Abbruch."""
    blaetter = tuple(str(_maske(ws.title)) for ws in wb.worksheets)
    treffer = []
    for f in formate:
        if f.blaetter != blaetter:
            continue
        if all(_kopfzeile(_blatt(wb, k["blatt"]), int(k["zeile"])) == list(k["zellen"]) for k in f.kopf):
            treffer.append(f)
    if len(treffer) == 1:
        return treffer[0]
    if treffer:
        raise FormatUnbekannt(f"{datei}: passt zu mehreren Formaten: {', '.join(f.regel for f in treffer)}.")
    erste = _kopfzeile(wb.worksheets[0], 1)[:6]
    raise FormatUnbekannt(
        f"{datei}: unbekanntes Format. Blätter {list(blaetter)}, erste Zeile {erste}. "
        "Nichts wurde geladen. Das Format braucht eine eigene, freigegebene Formatregel."
    )


def _jahr_pruefen(gefunden: object, jahr: int, wo: str) -> None:
    text = str(gefunden)
    treffer = _JAHR.findall(text)
    if treffer != [str(jahr)]:
        raise PensionFehler(f"{wo}: Das Jahr im Ordner ist {jahr}, in der Datei steht „{text}“.")


def _zellname(zeile: int, spalte: int) -> str:
    return f"{get_column_letter(spalte)}{zeile}"


# ------------------------------------------------------------------------------------------------- Lese-Arten


def _lies_kreuztabelle(wb: Any, f: Format, datei: str) -> Iterator[Rohzelle]:
    """Zweizeiliger Kopf, Pensionsart über verbundene Zellen, Bereiche in Spalte A."""
    for tabelle, t in f.tabellen.items():
        ws = _blatt(wb, t["blatt"])
        kopf = [z.value for z in ws[int(t["kopfzeile"])]]
        geschlecht = [z.value for z in ws[int(t["geschlechtzeile"])]]
        art: object = None
        arten: list[object] = []
        for wert in kopf:  # verbundene Zellen: openpyxl liefert nur die erste
            art = wert if wert is not None else art
            arten.append(art)
        for zeile in ws.iter_rows(min_row=int(t["geschlechtzeile"]) + 1):
            traeger = zeile[0].value
            if traeger is None:
                continue
            for z in zeile[1:]:
                spalte = z.column - 1
                ist_summe = kopf[spalte] == t["summenspalte"]
                yield Rohzelle(
                    tabelle,
                    traeger,
                    None if ist_summe else arten[spalte],
                    None if ist_summe else geschlecht[spalte],
                    z.value,
                    ws.title,
                    z.coordinate,
                )


def _lies_flach(wb: Any, f: Format, datei: str) -> Iterator[Rohzelle]:
    """Kopf „<Art> – <Geschlecht>“ in einer Zeile. Die Reihenfolge der Geschlechter steht im Kopf, nicht im Code."""
    for tabelle, t in f.tabellen.items():
        ws = _blatt(wb, t["blatt"])
        kopf = [z.value for z in ws[int(t["kopfzeile"])]]
        for zeile in ws.iter_rows(min_row=int(t["kopfzeile"]) + 1):
            traeger = zeile[0].value
            if traeger is None:
                continue
            for z in zeile[1:]:
                titel = str(kopf[z.column - 1])
                if titel == t["summenspalte"]:
                    yield Rohzelle(tabelle, traeger, None, None, z.value, ws.title, z.coordinate)
                    continue
                art, trenner, geschlecht = titel.rpartition(t["trenner"])
                if not trenner:
                    raise PensionFehler(f"{datei}, {ws.title}!{z.coordinate}: Kopf „{titel}“ ohne Trenner.")
                yield Rohzelle(tabelle, traeger, art, geschlecht, z.value, ws.title, z.coordinate)


def _lies_kuerzel(wb: Any, f: Format, datei: str, jahr: int) -> Iterator[Rohzelle]:
    """Eine Datenzeile, Spalten wie ``ALT_M``; JAHR und TRAEGER stehen in der Zeile."""
    for tabelle, t in f.tabellen.items():
        ws = _blatt(wb, t["blatt"])
        kopf = [str(z.value) for z in ws[int(t["kopfzeile"])]]
        zeilen = [z for z in ws.iter_rows(min_row=int(t["kopfzeile"]) + 1) if z[0].value is not None]
        if len(zeilen) != 1:
            raise PensionFehler(f"{datei}, {ws.title}: {len(zeilen)} Datenzeilen statt genau einer.")
        zeile = {kopf[z.column - 1]: z for z in zeilen[0]}
        _jahr_pruefen(zeile["JAHR"].value, jahr, f"{datei}, {ws.title}")
        traeger = zeile["TRAEGER"].value
        for titel, z in zeile.items():
            if titel in ("JAHR", "TRAEGER"):
                continue
            if titel == t["summenspalte"]:
                yield Rohzelle(tabelle, traeger, None, None, z.value, ws.title, z.coordinate)
                continue
            art, trenner, geschlecht = titel.rpartition("_")
            if not trenner:
                raise PensionFehler(f"{datei}, {ws.title}!{z.coordinate}: Spalte „{titel}“ ohne Kürzel.")
            yield Rohzelle(tabelle, traeger, art, geschlecht, z.value, ws.title, z.coordinate)


def _lies_bloecke(wb: Any, f: Format, datei: str) -> Iterator[Rohzelle]:
    """Zwei Blöcke in einem Blatt, je mit Überschrift und Kopf; die Zeile endet mit dem Geschlecht."""
    for tabelle, t in f.tabellen.items():
        ws = _blatt(wb, t["blatt"])
        start = next((z[0].row for z in ws.iter_rows() if z[0].value == t["titel"]), None)
        if start is None:
            raise PensionFehler(f"{datei}: Block „{t['titel']}“ fehlt.")
        kopf = [z.value for z in ws[start + 1]]
        for zeile in ws.iter_rows(min_row=start + 2):
            traeger = zeile[0].value
            if traeger is None:
                break
            for z in zeile[1:]:
                titel = kopf[z.column - 1]
                if titel is None:
                    if z.value is not None:
                        raise PensionFehler(f"{datei}, {ws.title}!{z.coordinate}: Wert ohne Spaltenkopf.")
                    continue
                if titel == t["summenspalte"]:
                    yield Rohzelle(tabelle, traeger, None, None, z.value, ws.title, z.coordinate)
                    continue
                art, _, geschlecht = str(titel).rpartition(" ")
                yield Rohzelle(tabelle, traeger, art, geschlecht, z.value, ws.title, z.coordinate)


def _lies_lang_anzahl(wb: Any, f: Format, datei: str) -> Iterator[Rohzelle]:
    """Liste Pensionsart, Geschlecht, Anzahl; der Träger steht in einer Titelzelle."""
    for tabelle, t in f.tabellen.items():
        ws = _blatt(wb, t["blatt"])
        traeger = ws[str(f.traeger_zelle)].value
        for zeile in ws.iter_rows(min_row=int(t["kopfzeile"]) + 1):
            art = zeile[0].value
            if art is None:
                break
            z = zeile[2]
            yield Rohzelle(tabelle, traeger, art, zeile[1].value, z.value, ws.title, z.coordinate)


def _lies_lang(wb: Any, f: Format, datei: str, jahr: int) -> Iterator[Rohzelle]:
    """Liste mit Spalten nach Namen; ``Tabelle`` entscheidet über die Tabelle jeder Zeile."""
    blatt = next(iter(f.tabellen.values()))
    ws = _blatt(wb, blatt["blatt"])
    kopf = {str(z.value): z.column - 1 for z in ws[int(blatt["kopfzeile"])]}
    for zeile in ws.iter_rows(min_row=int(blatt["kopfzeile"]) + 1):
        if zeile[0].value is None:
            continue
        wo = f"{datei}, {ws.title}!A{zeile[0].row}"
        _jahr_pruefen(zeile[kopf["Jahr"]].value, jahr, wo)
        if f.zeitraum_spalte:
            _jahr_pruefen(zeile[kopf[f.zeitraum_spalte]].value, jahr, wo)
        z = zeile[kopf["Anzahl"]]
        yield Rohzelle(
            str(zeile[kopf["Tabelle"]].value),
            zeile[kopf["Sparte"]].value,
            zeile[kopf["Pensionsart"]].value,
            zeile[kopf["Geschlecht"]].value,
            z.value,
            ws.title,
            z.coordinate,
        )


def _zahl(wert: object, wo: str) -> int:
    """Ganze Zahl ≥ 0; als Text nur mit Tausenderpunkten („18.228“). Alles andere bricht ab."""
    if isinstance(wert, bool):
        raise PensionFehler(f"{wo}: „{wert}“ ist keine Anzahl.")
    if isinstance(wert, int):
        if wert < 0:
            raise PensionFehler(f"{wo}: {wert} ist negativ.")
        return wert
    if isinstance(wert, str) and _TEXTZAHL.fullmatch(wert.strip()):
        return int(wert.strip().replace(".", ""))
    raise PensionFehler(f"{wo}: „{wert}“ ist keine Anzahl.")


def _rohzellen(wb: Any, f: Format, datei: str, jahr: int) -> Iterator[Rohzelle]:
    if f.jahr_zelle:
        _jahr_pruefen(_blatt(wb, f.jahr_zelle["blatt"])[f.jahr_zelle["zelle"]].value, jahr, datei)
    if f.parser == "kreuztabelle":
        return _lies_kreuztabelle(wb, f, datei)
    if f.parser == "flach":
        return _lies_flach(wb, f, datei)
    if f.parser == "kuerzel":
        return _lies_kuerzel(wb, f, datei, jahr)
    if f.parser == "bloecke":
        return _lies_bloecke(wb, f, datei)
    if f.parser == "lang_anzahl":
        return _lies_lang_anzahl(wb, f, datei)
    if f.parser == "lang":
        return _lies_lang(wb, f, datei, jahr)
    raise PensionFehler(f"{f.regel}: unbekannte Lese-Art „{f.parser}“.")


def _gueltig(k: Knoten, jahr: int) -> bool:
    return k.von <= date(jahr, 12, 31) and (k.bis is None or k.bis >= date(jahr, 1, 1))


def _jahre_pruefen(wb: Any, f: Format, jahr: int, datei: str) -> None:
    """Jedes Jahr in Blattnamen und Kopfzeilen ist das Jahr des Ordners, außer eine Zeile nennt fest ein anderes."""
    for ws in wb.worksheets:
        for gefunden in _JAHR.findall(ws.title):
            if gefunden != str(jahr):
                raise PensionFehler(f"{datei}: Das Jahr im Ordner ist {jahr}, das Blatt heißt „{ws.title}“.")
    for k in f.kopf:
        if k.get("jahr_frei"):
            continue
        ws = _blatt(wb, k["blatt"])
        for zelle in ws[int(k["zeile"])]:
            if isinstance(zelle.value, str) and any(j != str(jahr) for j in _JAHR.findall(zelle.value)):
                raise PensionFehler(
                    f"{datei}, {ws.title}!{zelle.coordinate}: Das Jahr im Ordner ist {jahr}, "
                    f"in der Datei steht „{zelle.value}“."
                )


def _keine_fremden_zellen(wb: Any, f: Format, rohzellen: list[Rohzelle], datei: str) -> None:
    """Jede gefüllte Zelle gehört zum Fingerabdruck oder zu einer gelesenen Zeile. Alles andere bricht ab.

    Sonst bliebe eine Zusatzzeile unter den Daten oder eine Zusatzspalte still ungelesen, und die Zahlen stimmten trotzdem.
    """
    kopfzeilen: dict[str, set[int]] = defaultdict(set)
    kopfspalten: dict[str, set[int]] = defaultdict(set)
    for k in f.kopf:
        titel = _blatt(wb, k["blatt"]).title
        kopfzeilen[titel].add(int(k["zeile"]))
        kopfspalten[titel] |= {i for i, wert in enumerate(k["zellen"], 1) if wert is not None}
    letzte: dict[tuple[str, int], int] = {}
    for r in rohzellen:
        zeile, spalte = coordinate_to_tuple(r.zelle)
        letzte[(r.blatt, zeile)] = max(spalte, letzte.get((r.blatt, zeile), 0))
    for ws in wb.worksheets:
        for reihe in ws.iter_rows():
            for z in reihe:
                if z.value is None or z.row in kopfzeilen[ws.title]:
                    continue
                bis = letzte.get((ws.title, z.row))
                if bis is None or (z.column > bis and z.column not in kopfspalten[ws.title]):
                    raise PensionFehler(
                        f"{datei}, {ws.title}!{z.coordinate}: „{z.value}“ gehört zu keiner gelesenen Zeile oder "
                        "Spalte. Nichts wurde geladen."
                    )


def datei_lesen(pfad: Path, jahr: int, werk: Regelwerk) -> DateiErgebnis:
    """Liest eine Meldung vollständig. Wirft bei allem, was nicht zu den Regeln passt; schreibt nichts."""
    datei = f"{jahr}/{pfad.name}"
    inhalt = pfad.read_bytes()
    wb = load_workbook(pfad, data_only=True)
    f = format_erkennen(wb, werk.formate, datei)
    if not f.jahr_von <= jahr <= f.jahr_bis:
        raise FormatUnbekannt(
            f"{datei}: Format {f.regel} gilt für {f.jahr_von} bis {f.jahr_bis}, nicht für {jahr}. "
            "Das ist ein Formatbruch und braucht eine eigene Regel."
        )
    ergebnis = DateiErgebnis(datei, jahr, f, hashlib.sha256(inhalt).hexdigest())
    _jahre_pruefen(wb, f, jahr, datei)
    rohzellen = list(_rohzellen(wb, f, datei, jahr))
    _keine_fremden_zellen(wb, f, rohzellen, datei)
    gesehen: dict[tuple[str, str, str], Wert] = {}
    roh_summen: list[tuple[str, str, str | None, int, str, str]] = []
    for r in rohzellen:
        wo = f"{datei}, {r.blatt}!{r.zelle}"
        traeger = werk.code(f.quelle, "versicherungstraeger", r.traeger, wo)
        if not _gueltig(werk.traeger[traeger], jahr):
            raise PensionFehler(f"{wo}: Träger {traeger} gibt es {jahr} nicht mehr oder noch nicht.")
        tabelle = r.tabelle
        if tabelle not in TABELLEN:  # lange Liste: Spalte Tabelle im Klartext
            tabelle = werk.code(f.quelle, "pensionsart", tabelle, wo)
        art = tabelle if r.art is None else werk.code(f.quelle, "pensionsart", r.art, wo)
        if art != tabelle and werk.arten[art].eltern != tabelle:
            raise PensionFehler(f"{wo}: Pensionsart {art} gehört nicht zu {tabelle}.")
        geschlecht = None if r.geschlecht is None else werk.code(f.quelle, "geschlecht", r.geschlecht, wo)
        wert = _zahl(r.wert, wo)
        ist_summe = (
            werk.hat_kinder(werk.traeger, traeger) or werk.hat_kinder(werk.arten, art) or geschlecht is None
        )
        if ist_summe:
            roh_summen.append((traeger, art, geschlecht, wert, r.blatt, r.zelle))
            continue
        assert geschlecht is not None
        schluessel = (traeger, art, geschlecht)
        if schluessel in gesehen:
            alt = gesehen[schluessel]
            raise PensionFehler(f"{wo}: {schluessel} steht schon in {alt.blatt}!{alt.zelle}.")
        gesehen[schluessel] = Wert(jahr, traeger, art, geschlecht, wert, r.blatt, r.zelle)
    _vollstaendig(gesehen, f, werk, datei)
    ergebnis.werte = sorted(gesehen.values(), key=lambda w: (w.traeger, w.art, w.geschlecht))
    for traeger, art, geschlecht, gemeldet, blatt, zelle in roh_summen:
        gerechnet = _nachrechnen(ergebnis.werte, werk, traeger, art, geschlecht)
        ergebnis.summen.append(Summe(jahr, traeger, art, geschlecht, gemeldet, gerechnet, blatt, zelle))
    return ergebnis


def _vollstaendig(gesehen: dict[tuple[str, str, str], Wert], f: Format, werk: Regelwerk, datei: str) -> None:
    """Jede Kombination aus Bereich, Art der gemeldeten Tabellen und Geschlecht kommt genau einmal vor."""
    arten = {k.code for k in werk.arten.values() if k.eltern in f.tabellen}
    soll = {(t, a, g) for t in werk.bereiche(f.quelle) for a in arten for g in ("M", "W")}
    fehlt = sorted(soll - set(gesehen))
    if fehlt:
        raise PensionFehler(f"{datei}: {len(fehlt)} Werte fehlen, zum Beispiel {fehlt[0]}.")
    zu_viel = sorted(set(gesehen) - soll)
    if zu_viel:
        raise PensionFehler(f"{datei}: Werte außerhalb der gemeldeten Tabellen, zum Beispiel {zu_viel[0]}.")


def _nachrechnen(werte: list[Wert], werk: Regelwerk, traeger: str, art: str, geschlecht: str | None) -> int:
    bereiche = werk.blaetter_unter(werk.traeger, traeger)
    arten = werk.blaetter_unter(werk.arten, art)
    return sum(
        w.wert
        for w in werte
        if w.traeger in bereiche and w.art in arten and (geschlecht is None or w.geschlecht == geschlecht)
    )


def erwartete_dateien(formate: Iterable[Format]) -> dict[int, set[str]]:
    """Je Jahr die Quellen, die laut Formatregeln genau eine Datei liefern (2018/19: fünf, 2020 bis 2025: drei)."""
    soll: dict[int, set[str]] = defaultdict(set)
    for f in formate:
        for jahr in range(f.jahr_von, f.jahr_bis + 1):
            soll[jahr].add(f.quelle)
    return soll


def ordner_lesen(ordner: Path, werk: Regelwerk) -> list[DateiErgebnis]:
    """Liest alle Meldungen unter ``ordner/JJJJ/``. Das Jahr kommt aus dem Ordner, nie aus dem Dateinamen."""
    if not ordner.is_dir():
        raise PensionFehler(f"Ordner {ordner.name}/ fehlt im Startpaket.")
    ergebnisse = []
    for jahr_ordner in sorted(p for p in ordner.iterdir() if p.is_dir()):
        if not re.fullmatch(r"\d{4}", jahr_ordner.name):
            raise PensionFehler(f"Unbekannter Ordner „{jahr_ordner.name}“: erwartet wird ein Jahr.")
        jahr = int(jahr_ordner.name)
        for pfad in sorted(jahr_ordner.iterdir()):
            if pfad.name.startswith((".", "~$")):
                continue
            if pfad.suffix.lower() != ".xlsx":
                raise PensionFehler(f"{jahr}/{pfad.name}: unbekannte Datei, erwartet wird .xlsx.")
            ergebnisse.append(datei_lesen(pfad, jahr, werk))
    soll = erwartete_dateien(werk.formate)
    ist: dict[int, list[str]] = defaultdict(list)
    for e in ergebnisse:
        ist[e.jahr].append(e.format.quelle)
    for jahr in sorted(set(soll) | set(ist)):
        if sorted(ist[jahr]) != sorted(soll[jahr]):
            fehlend = sorted(soll[jahr] - set(ist[jahr]))
            raise PensionFehler(
                f"{jahr}: erwartet {sorted(soll[jahr])}, gefunden {sorted(ist[jahr])}"
                + (f"; es fehlt {', '.join(fehlend)}." if fehlend else ".")
            )
    return ergebnisse


def ergebnis_hash(ergebnisse: Iterable[DateiErgebnis]) -> str:
    """Hash über alle Werte und Summen, sortiert; gleiche Dateien und Regeln, gleicher Hash."""
    zeilen = sorted(
        [
            json.dumps(["w", w.jahr, w.traeger, w.art, w.geschlecht, w.wert, e.datei, w.blatt, w.zelle])
            for e in ergebnisse
            for w in e.werte
        ]
        + [
            json.dumps(
                [
                    "s",
                    s.jahr,
                    s.traeger,
                    s.art,
                    s.geschlecht,
                    s.gemeldet,
                    s.gerechnet,
                    e.datei,
                    s.blatt,
                    s.zelle,
                ]
            )
            for e in ergebnisse
            for s in e.summen
        ]
    )
    return hashlib.sha256("\n".join(zeilen).encode("utf-8")).hexdigest()


# ------------------------------------------------------------------------------------------------------ Laden


def _stand_text(e: DateiErgebnis) -> str:
    traeger = e.format.quelle.split("-", 1)[0]
    return f"Meldung {traeger} {e.jahr}"


def laden(conn: Verbindung, ordner: Path | None = None) -> dict[str, Any]:
    """Liest alle Meldungen und schreibt sie in einer Transaktion: alles oder nichts.

    Steht derselbe Hash schon in der Datenbank, ändert sich nichts. Sind die Zahlen freigegeben und die Dateien anders,
    bricht es ab: Freigegebenes bleibt unverändert.
    """
    werk = regelwerk_laden(conn)
    ergebnisse = ordner_lesen(ordner or konfig.startpaket() / PENSIONEN_ORDNER, werk)
    stand = regelstand(conn, regeln_laden(conn, REGELSATZ))
    neu = ergebnis_hash(ergebnisse)
    alt = conn.execute(
        """SELECT min(ergebnis_hash) AS hash, min(regelstand) AS stand, count(freigegeben_von) AS frei
           FROM meta.pension_ladung"""
    ).fetchone()
    zusammenfassung = {
        "dateien": len(ergebnisse),
        "werte": sum(len(e.werte) for e in ergebnisse),
        "summen": sum(len(e.summen) for e in ergebnisse),
        "formate": sorted({e.format.regel for e in ergebnisse}),
        "ergebnis_hash": neu,
        "regelstand": stand,
    }
    if alt and alt["hash"] == neu and (alt["stand"] == stand or alt["frei"]):
        return {**zusammenfassung, "unveraendert": True}
    if alt and alt["frei"]:
        raise PensionFehler(
            "Die Pensionszahlen sind freigegeben und ändern sich nicht mehr. "
            f"Die Dateien ergeben einen anderen Stand ({neu[:12]} statt {str(alt['hash'])[:12]}): Das ist Revisionsbedarf."
        )
    with conn.transaction():
        conn.execute("DELETE FROM stat.stat_pensionen")
        conn.execute("DELETE FROM meta.pension_ladung")
        for e in ergebnisse:
            conn.execute(
                """INSERT INTO meta.pension_ladung
                     (datei, jahr, quelle, regel_name, sha256, werte, summen, ergebnis_hash, regelstand)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                (
                    e.datei,
                    e.jahr,
                    e.format.quelle,
                    e.format.regel,
                    e.sha256,
                    len(e.werte),
                    len(e.summen),
                    neu,
                    stand,
                ),
            )
            with conn.cursor() as cur:
                cur.executemany(
                    """INSERT INTO stat.stat_pensionen
                         (zeitraum_art, zeitraum_von, zeitraum_bis, versicherungstraeger, pensionsart, geschlecht,
                          variable, wert, status, stand, regelstand, quelle_datei, quelle_blatt, quelle_zelle)
                       VALUES ('Jahresdurchschnitt', %s, %s, %s, %s, %s, %s, %s, 'vorlaeufig', %s, %s, %s, %s, %s)""",
                    [
                        (
                            date(w.jahr, 1, 1), date(w.jahr, 12, 31), w.traeger, w.art, w.geschlecht, VARIABLE, w.wert,
                            _stand_text(e), stand, e.datei, w.blatt, w.zelle,
                        )
                        for w in e.werte
                    ],
                )  # fmt: skip
                cur.executemany(
                    """INSERT INTO meta.pension_summe
                         (datei, blatt, zelle, jahr, versicherungstraeger, pensionsart, geschlecht, gemeldet, gerechnet)
                       VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                    [
                        (
                            e.datei,
                            s.blatt,
                            s.zelle,
                            s.jahr,
                            s.traeger,
                            s.art,
                            s.geschlecht,
                            s.gemeldet,
                            s.gerechnet,
                        )
                        for s in e.summen
                    ],
                )
    return {**zusammenfassung, "unveraendert": False}


def freigeben(conn: Verbindung, name: str, repo_pfad: Path | None = None) -> dict[str, Any]:
    """Gibt Regeln und Zahlen mit Vor- und Nachnamen frei: vorläufig → endgültig. Mit Abweichung geht das nicht."""
    person = name_pruefen(name)
    bericht = pruefbericht(conn)
    if not bericht["ladung"]["dateien"]:
        raise PensionFehler("Es sind keine Pensionszahlen geladen: zuerst `uc3 pensionen laden`.")
    if bericht["ladung"]["freigegeben_von"]:
        raise PensionFehler(f"Die Zahlen sind schon freigegeben von {bericht['ladung']['freigegeben_von']}.")
    if bericht["summen"]["abweichend"] or bericht["vorzeitig"]:
        raise PensionFehler(
            f"{bericht['summen']['abweichend']} Summen weichen ab, in {len(bericht['vorzeitig'])} Fällen ist Tabelle 13 "
            "größer als die Alterspensionen: Das muss zuerst geklärt werden."
        )
    offen = conn.execute(
        "SELECT count(*) AS n FROM meta.regel WHERE regelsatz = %s AND aktiv AND freigegeben_von IS NULL",
        (REGELSATZ,),
    ).fetchone()
    regeln = int(str(offen["n"])) if offen else 0
    if regeln:
        regeln_freigeben(conn, REGELSATZ, person, repo_pfad=repo_pfad)
    with conn.transaction():
        zellen = conn.execute(
            "UPDATE stat.stat_pensionen SET status = 'endgueltig' WHERE status = 'vorlaeufig'"
        ).rowcount
        conn.execute(
            """UPDATE meta.pension_ladung SET freigegeben_von = %s, freigegeben_am = now()
               WHERE freigegeben_von IS NULL""",
            (person,),
        )
    return {"regeln": regeln, "zellen": zellen, "freigegeben_von": person}


# ------------------------------------------------------------------------------------------------------- Bericht

_UNTER = """WITH RECURSIVE baum AS (
  SELECT code, code AS wurzel FROM stat.klass_versicherungstraeger
  UNION ALL
  SELECT k.code, b.wurzel FROM stat.klass_versicherungstraeger k JOIN baum b ON k.uebergeordnet = b.code
)"""
#: Summen über Träger je Jahr und Tabelle: Knoten INSG, PV-UNS, PV-SEL, je Träger. Tabelle 13 ist ein Teil von Tabelle 12.
SQL_SUMMEN = (
    _UNTER
    + """
SELECT extract(year FROM p.zeitraum_von)::int AS jahr, a.uebergeordnet AS tabelle, b.wurzel AS knoten,
       k.bezeichnung, k.ebene, sum(p.wert)::bigint AS wert, min(p.status) AS status
FROM stat.stat_pensionen p
JOIN stat.klass_pensionsart a ON a.code = p.pensionsart
JOIN baum b ON b.code = p.versicherungstraeger
JOIN stat.klass_versicherungstraeger k ON k.code = b.wurzel
GROUP BY 1, 2, 3, 4, 5
ORDER BY 1, 2, k.ebene, b.wurzel
"""
)


def _tabelle_da(conn: Verbindung) -> bool:
    zeile = conn.execute("SELECT to_regclass('stat.stat_pensionen') IS NOT NULL AS da").fetchone()
    return bool(zeile and zeile["da"])


def _prozent(alt: int, neu: int) -> float | None:
    return None if alt == 0 else round(100.0 * (neu - alt) / alt, 1)


def _regelparameter(conn: Verbindung, art: str) -> dict[str, Any]:
    treffer = [r for r in regeln_laden(conn, REGELSATZ) if r.art == art]
    if len(treffer) != 1:
        raise PensionFehler(
            f"Regelsatz {REGELSATZ}: genau eine Regel der Art {art} nötig, gefunden {len(treffer)}."
        )
    return treffer[0].parameter


def pruefbericht(conn: Verbindung) -> dict[str, Any]:
    """Alles, was der Prüfbericht sagt, aus der Datenbank. Rechnet nur nach, ändert keine Zahl."""
    dateien = conn.execute(
        """SELECT datei, jahr, quelle, regel_name, sha256, werte, summen, ergebnis_hash, regelstand,
                  freigegeben_von, freigegeben_am
           FROM meta.pension_ladung ORDER BY jahr, datei"""
    ).fetchall()
    soll = erwartete_dateien(
        [Format.aus_regel(r) for r in regeln_laden(conn, REGELSATZ) if r.art == "pension_format"]
    )
    summen = conn.execute(
        """SELECT datei, blatt, zelle, jahr, versicherungstraeger, pensionsart, geschlecht, gemeldet, gerechnet
           FROM meta.pension_summe ORDER BY jahr, datei, blatt, zelle"""
    ).fetchall()
    abweichend = [dict(s) for s in summen if s["gemeldet"] != s["gerechnet"]]
    ges = conn.execute(SQL_SUMMEN).fetchall()
    geschlecht = _geschlecht(conn)
    return {
        "ladung": {
            "dateien": len(dateien),
            "dateien_soll": sum(len(v) for v in soll.values()),
            "werte": sum(int(str(d["werte"])) for d in dateien),
            "ergebnis_hash": dateien[0]["ergebnis_hash"] if dateien else None,
            "regelstand": dateien[0]["regelstand"] if dateien else None,
            "freigegeben_von": dateien[0]["freigegeben_von"] if dateien else None,
            "formate": sorted({str(d["regel_name"]) for d in dateien}),
            "liste": [dict(d) for d in dateien],
        },
        "summen": {"geprueft": len(summen), "abweichend": len(abweichend), "abweichungen": abweichend},
        "gesamtsummen": [dict(z) for z in ges],
        "luecken": _regelparameter(conn, "pension_luecke")["luecken"],
        "uebergang": _uebergang(conn),
        "spruenge": _spruenge(conn),
        "geschlecht": geschlecht,
        "formate": _formate(conn, dateien, geschlecht["zeilen"]),
        "vorzeitig": _vorzeitig(conn),
        "qualifikation_getrennt": _qualifikation_getrennt(conn),
    }


def _formate(conn: Verbindung, dateien: list[Any], auffaellig: list[dict[str, Any]]) -> dict[str, Any]:
    """Die erkannten Formate mit ihren Jahren und die Brüche: derselbe Träger wechselt sein Format."""
    regeln = sorted(
        (r for r in regeln_laden(conn, REGELSATZ) if r.art == "pension_format"), key=lambda r: r.reihenfolge
    )
    liste = [
        {
            "regel": r.name,
            "beschreibung": r.beschreibung,
            "jahre": list(r.parameter["jahre"]),
            "dateien": sum(1 for d in dateien if d["regel_name"] == r.name),
        }
        for r in regeln
    ]
    nach_traeger: dict[str, list[Regel]] = defaultdict(list)
    for r in regeln:
        nach_traeger[str(r.parameter["quelle"]).split("-", 1)[0]].append(r)
    brueche = []
    for traeger, formate in nach_traeger.items():
        for neu in sorted(formate, key=lambda r: int(r.parameter["jahre"][0]))[1:]:
            jahr = int(neu.parameter["jahre"][0])
            brueche.append(
                {
                    "traeger": traeger,
                    "jahr": jahr,
                    "maenneranteil_auffaellig": sum(
                        1 for g in auffaellig if g["jahr"] == jahr and str(g["code"]).startswith(traeger)
                    ),
                }
            )
    return {"liste": liste, "brueche": brueche}


def _uebergang(conn: Verbindung) -> dict[str, Any]:
    p = _regelparameter(conn, "pension_uebergang")
    alt, neu = int(p["jahr_alt"]), int(p["jahr_neu"])
    zeilen = conn.execute(
        """
        WITH reihe AS (
          SELECT extract(year FROM s.zeitraum_von)::int AS jahr, a.uebergeordnet AS tabelle,
                 s.versicherungstraeger AS code, sum(s.wert)::bigint AS wert
          FROM stat.stat_pensionen s JOIN stat.klass_pensionsart a ON a.code = s.pensionsart
          GROUP BY 1, 2, 3
        )
        SELECT z.ziel, t.tabelle,
               (SELECT string_agg(u.code_alt, ' + ' ORDER BY u.code_alt) FROM stat.uebergang u
                WHERE u.klassifikation = 'versicherungstraeger' AND u.code_neu = z.ziel) AS vorgaenger,
               (SELECT string_agg(u.code_alt, ', ' ORDER BY u.code_alt) FROM stat.uebergang u
                WHERE u.klassifikation = 'versicherungstraeger' AND u.code_neu = z.ziel
                  AND NOT EXISTS (SELECT 1 FROM reihe r WHERE r.code = u.code_alt AND r.jahr = %(alt)s
                                  AND r.tabelle = t.tabelle)) AS ohne_meldung,
               (SELECT sum(r.wert)::bigint FROM reihe r JOIN stat.uebergang u
                  ON u.klassifikation = 'versicherungstraeger' AND u.code_neu = z.ziel AND u.code_alt = r.code
                WHERE r.jahr = %(alt)s AND r.tabelle = t.tabelle) AS wert_alt,
               (SELECT r.wert FROM reihe r WHERE r.code = z.ziel AND r.jahr = %(neu)s AND r.tabelle = t.tabelle) AS wert_neu
        FROM unnest(%(ziele)s::text[]) WITH ORDINALITY AS z(ziel, nr)
        CROSS JOIN (VALUES ('T12'), ('T13')) AS t(tabelle)
        ORDER BY t.tabelle, z.nr
        """,
        {"alt": alt, "neu": neu, "ziele": list(p["ziele"])},
    ).fetchall()
    liste = [
        {
            **dict(z),
            "aenderung_prozent": _prozent(int(str(z["wert_alt"])), int(str(z["wert_neu"])))
            if z["wert_alt"] is not None and z["wert_neu"] is not None
            else None,
        }
        for z in zeilen
    ]
    return {"jahr_alt": alt, "jahr_neu": neu, "annahme": p["annahme"], "zeilen": liste}


def _spruenge(conn: Verbindung) -> dict[str, Any]:
    p = _regelparameter(conn, "pension_sprung")
    zeilen = conn.execute(
        """
        WITH w AS (
          SELECT extract(year FROM zeitraum_von)::int AS jahr, versicherungstraeger AS code, pensionsart, geschlecht, wert,
                 lag(wert) OVER (PARTITION BY versicherungstraeger, pensionsart, geschlecht ORDER BY zeitraum_von) AS vorjahr
          FROM stat.stat_pensionen
        )
        SELECT jahr, code, pensionsart, geschlecht, vorjahr, wert FROM w
        WHERE vorjahr IS NOT NULL AND greatest(vorjahr, wert) >= %(min)s
          AND abs(wert - vorjahr) * 100.0 / nullif(vorjahr, 0) >= %(schwelle)s
        ORDER BY jahr, code, pensionsart, geschlecht
        """,
        {"min": int(p["mindestwert"]), "schwelle": float(p["schwelle_prozent"])},
    ).fetchall()
    return {**p, "zeilen": [dict(z) for z in zeilen]}


def _geschlecht(conn: Verbindung) -> dict[str, Any]:
    p = _regelparameter(conn, "pension_geschlecht")
    zeilen = conn.execute(
        """
        WITH a AS (
          SELECT extract(year FROM zeitraum_von)::int AS jahr, versicherungstraeger AS code, pensionsart,
                 sum(wert) FILTER (WHERE geschlecht = 'M') AS m, sum(wert) AS g
          FROM stat.stat_pensionen GROUP BY 1, 2, 3
        ), b AS (
          SELECT *, 100.0 * m / nullif(g, 0) AS anteil,
                 lag(100.0 * m / nullif(g, 0)) OVER (PARTITION BY code, pensionsart ORDER BY jahr) AS vorjahr,
                 lag(g) OVER (PARTITION BY code, pensionsart ORDER BY jahr) AS g_vorjahr
          FROM a
        )
        SELECT jahr, code, pensionsart, round(vorjahr, 1)::float AS anteil_vorjahr, round(anteil, 1)::float AS anteil
        FROM b
        WHERE vorjahr IS NOT NULL AND least(g, g_vorjahr) >= %(min)s AND abs(anteil - vorjahr) >= %(schwelle)s
        ORDER BY jahr, code, pensionsart
        """,
        {"min": int(p["mindestwert"]), "schwelle": float(p["schwelle_punkte"])},
    ).fetchall()
    return {**p, "zeilen": [dict(z) for z in zeilen]}


def _vorzeitig(conn: Verbindung) -> list[dict[str, Any]]:
    zeilen = conn.execute(
        """
        SELECT extract(year FROM s.zeitraum_von)::int AS jahr, s.versicherungstraeger AS code, s.geschlecht,
               sum(s.wert) FILTER (WHERE a.uebergeordnet = 'T13')::bigint AS vorzeitig,
               sum(s.wert) FILTER (WHERE s.pensionsart = 'ALTER')::bigint AS alter_gesamt
        FROM stat.stat_pensionen s JOIN stat.klass_pensionsart a ON a.code = s.pensionsart
        GROUP BY 1, 2, 3
        HAVING sum(s.wert) FILTER (WHERE a.uebergeordnet = 'T13') > sum(s.wert) FILTER (WHERE s.pensionsart = 'ALTER')
        ORDER BY 1, 2, 3
        """
    ).fetchall()
    return [dict(z) for z in zeilen]


def _qualifikation_getrennt(conn: Verbindung) -> int:
    """Soll 0: Die Bereiche der PVA stehen in der Gliederung der Träger, nicht in der Qualifikation."""
    zeile = conn.execute(
        """SELECT count(*) AS n FROM stat.klass_qualifikation q
           JOIN stat.klass_versicherungstraeger t ON t.code = q.code"""
    ).fetchone()
    return int(str(zeile["n"])) if zeile else 0


def _z(wert: object) -> str:
    return "–" if wert is None else f"{int(str(wert)):,}".replace(",", ".")


def bericht_text(b: dict[str, Any]) -> str:
    """Der Prüfbericht als Markdown, in einfacher Sprache. Gleiche Datenbank, gleicher Text (ohne Uhrzeit)."""
    la, su = b["ladung"], b["summen"]
    if not la["dateien"]:
        return "# Prüfbericht Pensionen\n\nEs sind noch keine Pensionszahlen geladen: `uv run uc3 pensionen laden`.\n"
    status = (
        f"freigegeben von {la['freigegeben_von']}"
        if la["freigegeben_von"]
        else "vorläufig, noch nicht mit Namen freigegeben"
    )
    z = [
        "# Prüfbericht Pensionen 2018 bis 2025",
        "",
        "Die Zahlen sind die Meldungen der Träger. Geprüft wird, was man aus den Dateien nachrechnen kann. "
        "Geändert oder geglättet wird nichts.",
        "",
        f"- **Dateien:** {la['dateien']} von {la['dateien_soll']} geladen, {len(la['formate'])} Formate erkannt.",
        f"- **Werte:** {_z(la['werte'])} je Bereich, Pensionsart und Geschlecht.",
        f"- **Summen der Dateien:** {_z(su['geprueft'])} nachgerechnet, {_z(su['abweichend'])} weichen ab.",
        f"- **Stand:** {status}. Hash {str(la['ergebnis_hash'])[:16]}, Regelstand {la['regelstand']}.",
        "",
    ]
    if su["abweichend"]:
        z += [
            "## Abweichende Summen",
            "",
            "| Datei | Zelle | gemeldet | nachgerechnet |",
            "|---|---|--:|--:|",
        ]
        z += [
            f"| {a['datei']} | {a['blatt']}!{a['zelle']} | {_z(a['gemeldet'])} | {_z(a['gerechnet'])} |"
            for a in su["abweichungen"]
        ]
        z.append("")
    z += _summen_abschnitt(b["gesamtsummen"])
    z += ["## Formate", "", "| Format | Jahre | Dateien | Aufbau |", "|---|---|--:|---|"]
    z += [
        f"| {f['regel']} | {f['jahre'][0]} bis {f['jahre'][1]} | {f['dateien']} | {f['beschreibung']} |"
        for f in b["formate"]["liste"]
    ]
    z.append("")
    for b_ in b["formate"]["brueche"]:
        z.append(
            f"- **Formatbruch {b_['traeger']} {b_['jahr']}:** Der Träger wechselt sein Format. Der Männeranteil zeigt in "
            f"diesem Jahr {b_['maenneranteil_auffaellig']} auffällige Fälle; ein vertauschtes Geschlecht fiele hier auf."
        )
    z.append("")
    z += ["## Lücken in den Meldungen", ""]
    for lu in b["luecken"]:
        z.append(f"- **{lu['titel']}.** {lu['annahme']} (Beleg: {lu['beleg']})")
    z.append("")
    ue = b["uebergang"]
    z += [
        f"## Übergang {ue['jahr_alt']} auf {ue['jahr_neu']}",
        "",
        f"Zum 1.1.2020 wurden Träger zusammengelegt. {ue['annahme']}",
        "",
        f"| Tabelle | Nachfolger | Vorgänger | {ue['jahr_alt']} | {ue['jahr_neu']} | Änderung |",
        "|---|---|---|--:|--:|--:|",
    ]
    for u in ue["zeilen"]:
        aenderung = (
            "–" if u["aenderung_prozent"] is None else f"{u['aenderung_prozent']:+.1f} %".replace(".", ",")
        )
        vorgaenger = str(u["vorgaenger"])
        if u["ohne_meldung"]:
            vorgaenger += f" ({u['ohne_meldung']} ohne Meldung)"
        z.append(
            f"| {u['tabelle']} | {u['ziel']} | {vorgaenger} | {_z(u['wert_alt'])} | {_z(u['wert_neu'])} | {aenderung} |"
        )
    z += ["", "## Auffälligkeiten", "", "Sie sind gemeldet, nicht korrigiert.", ""]
    sp = b["spruenge"]
    z.append(
        f"- **Sprünge:** {len(sp['zeilen'])} Werte ändern sich von einem Jahr aufs nächste um mindestens "
        f"{sp['schwelle_prozent']} Prozent (ab {_z(sp['mindestwert'])} Pensionen)."
    )
    ge = b["geschlecht"]
    z.append(
        f"- **Männeranteil:** {len(ge['zeilen'])} Fälle, in denen er sich um mindestens {ge['schwelle_punkte']} "
        "Prozentpunkte ändert. Ein Spaltentausch ließe alle Summen stimmen und fiele nur hier auf."
    )
    z.append(f"- **Tabelle 13 größer als Alterspensionen:** {len(b['vorzeitig'])} Fälle, Soll ist 0.")
    z.append(
        f"- **Bereiche der PVA in der Qualifikation:** {b['qualifikation_getrennt']} Codes, Soll ist 0. "
        "Arbeiter und Angestellte der PVA sind frühere Träger, keine Qualifikation."
    )
    z.append("")
    if sp["zeilen"]:
        z += [
            "### Sprünge",
            "",
            "| Jahr | Bereich | Art | Geschlecht | Vorjahr | Wert |",
            "|---|---|---|---|--:|--:|",
        ]
        z += [
            f"| {s['jahr']} | {s['code']} | {s['pensionsart']} | {s['geschlecht']} | {_z(s['vorjahr'])} | {_z(s['wert'])} |"
            for s in sp["zeilen"]
        ]
        z.append("")
    if ge["zeilen"]:
        z += ["### Männeranteil", "", "| Jahr | Bereich | Art | Vorjahr | Wert |", "|---|---|---|--:|--:|"]
        z += [
            f"| {g['jahr']} | {g['code']} | {g['pensionsart']} | {_prozent_text(g['anteil_vorjahr'])} | {_prozent_text(g['anteil'])} |"
            for g in ge["zeilen"]
        ]
        z.append("")
    z += ["## Dateien", "", "| Datei | Format | Werte | Summen | Hash |", "|---|---|--:|--:|---|"]
    z += [
        f"| {d['datei']} | {d['regel_name']} | {d['werte']} | {d['summen']} | {str(d['sha256'])[:12]} |"
        for d in la["liste"]
    ]
    z.append("")
    return "\n".join(z)


def _prozent_text(wert: object) -> str:
    return f"{float(str(wert)):.1f} %".replace(".", ",")


def _summen_abschnitt(zeilen: list[dict[str, Any]]) -> list[str]:
    jahre = sorted({int(z["jahr"]) for z in zeilen})
    z = ["## Summen über alle Träger", ""]
    for tabelle, titel in (
        ("T12", "Stand der Pensionen"),
        ("T13", "Vorzeitige Alterspensionen, Teil der Alterspensionen"),
    ):
        z += [f"**{titel}**", "", "| Gliederung | " + " | ".join(str(j) for j in jahre) + " |"]
        z.append("|---|" + "--:|" * len(jahre))
        for knoten, name in (
            ("INSG", "Insgesamt"),
            ("PV-UNS", "PV der Unselbständigen"),
            ("PV-SEL", "PV der Selbständigen"),
        ):
            werte = {
                int(x["jahr"]): x["wert"] for x in zeilen if x["tabelle"] == tabelle and x["knoten"] == knoten
            }
            z.append(f"| {name} | " + " | ".join(_z(werte.get(j)) for j in jahre) + " |")
        z.append("")
    return z


def tabelle(conn: Verbindung, jahr: int, nummer: str = "T12") -> dict[str, Any]:
    """Tabelle 12 oder 13 eines Jahres: je Gliederung und Pensionsart Männer, Frauen, zusammen (eigene Summen)."""
    if nummer not in TABELLEN:
        raise PensionFehler(f"Tabelle {nummer} gibt es nicht, nur {', '.join(TABELLEN)}.")
    zeilen = conn.execute(
        _UNTER
        + """
        SELECT b.wurzel AS knoten, k.bezeichnung, k.ebene, s.pensionsart, s.geschlecht, sum(s.wert)::bigint AS wert
        FROM stat.stat_pensionen s
        JOIN stat.klass_pensionsart a ON a.code = s.pensionsart
        JOIN baum b ON b.code = s.versicherungstraeger
        JOIN stat.klass_versicherungstraeger k ON k.code = b.wurzel
        WHERE a.uebergeordnet = %(t)s AND s.zeitraum_von = make_date(%(j)s, 1, 1)
        GROUP BY 1, 2, 3, 4, 5
        ORDER BY k.ebene, b.wurzel, s.pensionsart, s.geschlecht
        """,
        {"t": nummer, "j": jahr},
    ).fetchall()
    return {"jahr": jahr, "tabelle": nummer, "zeilen": [dict(z) for z in zeilen]}


# ----------------------------------------------------------------------------------------------- Datenfrage

_PENSIONSWORT = re.compile(r"pension")
_FRAGEWORT = re.compile(r"[a-zäöüß0-9/§-]+")
_MONATSWORT = re.compile(
    r"\b(jänner|januar|februar|feber|märz|maerz|april|mai|juni|juli|august|september|oktober|november|dezember)\b"
    r"|\b\d{4}-\d{2}\b"
)
_ZEITREIHE = re.compile(r"entwicklung|zeitreihe|verlauf|\bje jahr\b|\bpro jahr\b|\bseit\b")
_NACH_TEXT = {"traeger": "Träger", "art": "Pensionsart", "geschlecht": "Geschlecht"}
_NACH = {
    "träger": "traeger",
    "traeger": "traeger",
    "trägern": "traeger",
    "versicherungsträger": "traeger",
    "versicherungsträgern": "traeger",
    "art": "art",
    "arten": "art",
    "pensionsart": "art",
    "pensionsarten": "art",
    "geschlecht": "geschlecht",
}
_GLIEDERWORT = ("nach", "je", "pro")
_ARTIKEL = ("dem", "den", "der", "die", "das")
_JAHRWORT = ("jahr", "jahre", "jahren", "jahres")


def ist_pensionsfrage(frage: str) -> bool:
    return bool(_PENSIONSWORT.search(frage.lower()))


def _rueckfrage_text(frage_text: str) -> dict[str, Any]:
    from statagent.frage import _antwort

    return _antwort("rueckfrage", frage_text)


def _ohne_zahl(frage_text: str) -> dict[str, Any]:
    from statagent.frage import _antwort

    return _antwort("pensionen", frage_text, hinweise=[frage_text])


def _gliederungen(woerter: list[str], g_codes: set[str]) -> tuple[set[str], str | None]:
    """Wonach die Frage gliedern will, und ein Wort nach „nach“, „je“ oder „pro“, das keine Gliederung ist."""
    menge: set[str] = {"geschlecht"} if len(g_codes) == 2 else set()
    falsch = None
    erste = None
    for i, wort in enumerate(woerter):
        if wort not in _GLIEDERWORT:
            continue
        folge = [w for w in woerter[i + 1 :] if w not in _ARTIKEL]
        if not folge or folge[0] in _JAHRWORT or re.fullmatch(r"\d{4}", folge[0]):
            continue
        if folge[0] in _NACH:
            erste = i if erste is None else erste
        else:
            falsch = folge[0]
    if erste is not None:
        menge |= {_NACH[w] for w in woerter[erste:] if w in _NACH}
    return menge, falsch


def pensionsantwort(conn: Verbindung, frage: str) -> dict[str, Any]:
    """Beantwortet eine Frage nach Pensionen ohne Sprachmodell. Unbekanntes führt zur Rückfrage, nie zu einer Zahl.

    Die Wörter und was sie meinen stehen in der Regel ``pension_frage``; die Zahl kommt aus einer Abfrage, deren Text als
    Beleg in der Antwort steht.
    """
    from statagent.frage import _antwort, _lesen

    begriffe = _regelparameter(conn, "pension_frage")
    text = frage.lower()
    if _MONATSWORT.search(text):
        return _ohne_zahl(
            "Die Träger melden Pensionen nur als Jahresdurchschnitt, nicht je Monat. Fragen Sie nach einem Jahr von "
            f"{ERSTES_JAHR} bis {LETZTES_JAHR}."
        )
    woerter = _FRAGEWORT.findall(text)
    arten: dict[str, list[str]] = begriffe["arten"]
    traeger: dict[str, list[str]] = begriffe["traeger"]
    geschlechter: dict[str, list[str]] = begriffe["geschlecht"]
    mehrdeutig: dict[str, dict[str, Any]] = begriffe["mehrdeutig"]
    abgelehnt: dict[str, str] = begriffe["abgelehnt"]
    satz_abgelehnt = next((abgelehnt[w] for w in woerter if w in abgelehnt), None)
    if satz_abgelehnt:
        return _rueckfrage_text(satz_abgelehnt)
    bekannt = set(begriffe["fuellwoerter"]) | set(_NACH) | set(mehrdeutig)
    art_codes = {c for c, ws in arten.items() if any(w in ws for w in woerter)}
    # „vorzeitige Alterspensionen“ meint Tabelle 13, „Pensionsstand Waisen“ nur die Waisen: das Engere gilt.
    if "T13" in art_codes:
        art_codes.discard("ALTER")
    knoten_arten = _unterarten(conn)
    for ober, unter in knoten_arten.items():
        if ober in art_codes and art_codes & unter:
            art_codes.discard(ober)
    traeger_codes = {c for c, ws in traeger.items() if any(w in ws for w in woerter)}
    g_codes = {c for c, ws in geschlechter.items() if any(w in ws for w in woerter)}
    for ws in (*arten.values(), *traeger.values(), *geschlechter.values()):
        bekannt |= set(ws)
    jahre = sorted({int(w) for w in woerter if re.fullmatch(r"\d{4}", w)})
    unbekannt = [w for w in woerter if w not in bekannt and not re.fullmatch(r"\d{4}", w)]
    if unbekannt:
        return _rueckfrage_text(
            f"Das Wort „{unbekannt[0]}“ kenne ich bei Pensionen nicht, darum nenne ich keine Zahl. Pensionen gibt es "
            f"je Jahr von {ERSTES_JAHR} bis {LETZTES_JAHR}, nach Träger, Pensionsart und Geschlecht."
        )
    for wort, eintrag in mehrdeutig.items():
        if wort in woerter and not art_codes & set(eintrag["codes"]):
            return _rueckfrage_text(str(eintrag["satz"]))
    gliederungen, nach_falsch = _gliederungen(woerter, g_codes)
    if nach_falsch:
        return _rueckfrage_text(
            f"Nach „{nach_falsch}“ lässt sich nicht gliedern. Pensionen gibt es nach Träger, Pensionsart und Geschlecht. "
            f"Wenn Sie nur „{nach_falsch}“ meinen, fragen Sie bitte ohne „nach“."
        )
    if len(gliederungen) > 1:
        return _rueckfrage_text(
            "Bitte nur eine Gliederung auf einmal: nach Träger, Pensionsart oder Geschlecht."
        )
    gliederung = next(iter(gliederungen), None)
    if len(art_codes) > 1 or len(traeger_codes) > 1:
        return _rueckfrage_text(
            "Die Frage nennt mehr als eine Pensionsart oder mehr als einen Träger. Fragen Sie bitte nach einem davon, "
            "oder nach einer Gliederung wie „nach Träger“."
        )
    if len(g_codes) == 2:
        g_codes = set()
    falsch = [j for j in jahre if not ERSTES_JAHR <= j <= LETZTES_JAHR]
    if falsch:
        return _ohne_zahl(
            f"Für {falsch[0]} gibt es keine Meldung. Pensionen gibt es von {ERSTES_JAHR} bis {LETZTES_JAHR}."
        )
    if len(jahre) == 1:
        davor = woerter[woerter.index(str(jahre[0])) - 1] if woerter.index(str(jahre[0])) > 0 else ""
        if davor in ("nach", "bis"):
            return _rueckfrage_text(
                f"Meinen Sie genau {jahre[0]} oder einen Zeitraum? Für einen Zeitraum nennen Sie bitte beide Jahre, "
                f"zum Beispiel {ERSTES_JAHR} bis {jahre[0]}."
            )
    if _ZEITREIHE.search(text) and len(jahre) <= 1:
        von, bis = (jahre[0] if jahre else ERSTES_JAHR), LETZTES_JAHR
    elif len(jahre) == 2 and " bis " in text:
        von, bis = jahre[0], jahre[1]
    elif len(jahre) == 1:
        von, bis = jahre[0], jahre[0]
    else:
        return _rueckfrage_text(f"Für welches Jahr? Pensionen gibt es von {ERSTES_JAHR} bis {LETZTES_JAHR}.")
    art = art_codes.pop() if art_codes else "T12"
    knoten = traeger_codes.pop() if traeger_codes else "INSG"
    geschlecht = g_codes.pop() if g_codes else None
    if gliederung == "traeger" and knoten not in ("INSG", "PV-UNS", "PV-SEL"):
        return _rueckfrage_text("Die Frage nennt einen Träger und will nach Trägern gliedern. Welches davon?")
    if gliederung == "art" and art not in TABELLEN:
        return _rueckfrage_text(
            "Die Frage nennt eine Pensionsart und will nach Arten gliedern. Welches davon?"
        )
    if gliederung == "geschlecht" and geschlecht:
        geschlecht = None
    da = conn.execute("SELECT count(*) AS n FROM stat.stat_pensionen").fetchone()
    if not da or not da["n"]:
        return _ohne_zahl(
            "Die Pensionsmeldungen sind noch nicht geladen. Sie kommen mit `uv run uc3 pensionen laden`."
        )
    abfrage = _frage_sql(von, bis, art, knoten, geschlecht, gliederung)
    zeilen = _lesen(conn, abfrage)
    namen = _bezeichnungen(conn)
    art_name, knoten_name = namen["art"][art], namen["traeger"][knoten]
    auswahl = ", ".join(
        [
            art_name,
            *([] if knoten == "INSG" else [knoten_name]),
            *([namen["g"][geschlecht]] if geschlecht else []),
        ]
    )
    zeitraum = str(von) if von == bis else f"{von} bis {bis}"
    verstanden = f"Verstanden: {auswahl}, {zeitraum}."
    if not zeilen:
        return _ohne_zahl(
            f"{verstanden} Dazu gibt es keine Meldung. Zum 1.1.2020 wurden Träger zusammengelegt, und die VAN meldet "
            "keine vorzeitigen Alterspensionen."
        )
    stand = conn.execute(
        "SELECT min(ergebnis_hash) AS hash, min(regelstand) AS stand FROM meta.pension_ladung"
    ).fetchone()
    vorlaeufig = any(str(z["status"]) != "endgueltig" for z in zeilen)
    beleg = {
        "uc": "uc3",
        "quelle": "stat.stat_pensionen",
        "lieferung": None,
        "monat": None,
        "sql": abfrage,
        "ref": "meta.pension_ladung",
        "regelstand": str(stand["stand"]) if stand else None,
        "lauf": str(stand["hash"]) if stand else None,
        "stand": "vorlaeufig" if vorlaeufig else "endgueltig",
    }
    zahlen: list[dict[str, Any]] = []
    for z in zeilen:
        teile = [auswahl]
        if z["teil"] is not None:
            teile.append(_teilname(namen, gliederung, str(z["teil"])))
        if von != bis:
            teile.append(str(z["jahr"]))
        zahlen.append(
            {"bezeichnung": ", ".join(teile), "wert": int(z["wert"]), "einheit": "Anzahl", "beleg": 0}
        )
    if von == bis and gliederung is None:
        satz = f"Im Jahresdurchschnitt {von} waren es {_z(zeilen[0]['wert'])} Pensionen."
    elif von == bis:
        satz = f"Im Jahresdurchschnitt {von} nach {_NACH_TEXT[str(gliederung)]}, siehe Tabelle."
    else:
        satz = f"Jahresdurchschnitte {von} bis {bis}, siehe Tabelle."
    hinweise = []
    if vorlaeufig:
        hinweise.append("Stand vorläufig: Die Zahlen sind noch nicht mit Namen freigegeben.")
    if von < 2020 <= bis and knoten != "INSG":
        hinweise.append("Zum 1.1.2020 wurden Träger zusammengelegt; die Reihe ist dort nicht geglättet.")
    if knoten in begriffe.get("hinweis_traeger", {}):
        hinweise.append(begriffe["hinweis_traeger"][knoten])
    return _antwort(
        "pensionen",
        " ".join([verstanden, satz, *hinweise]),
        definition=_definition_pensionen(conn),
        einheit="Anzahl",
        stand=[{"Hash": str(stand["hash"])[:16], "Regelstand": str(stand["stand"])}] if stand else [],
        belege=[beleg],
        zahlen=zahlen,
        hinweise=hinweise,
    )


def _unterarten(conn: Verbindung) -> dict[str, set[str]]:
    unter: dict[str, set[str]] = defaultdict(set)
    for z in conn.execute(
        "SELECT code, uebergeordnet FROM stat.klass_pensionsart WHERE uebergeordnet IS NOT NULL"
    ).fetchall():
        unter[str(z["uebergeordnet"])].add(str(z["code"]))
    return unter


def _definition_pensionen(conn: Verbindung) -> str | None:
    zeile = conn.execute(
        "SELECT beschreibung FROM stat.variable WHERE statistik = 'pensionen' AND code = %s", (VARIABLE,)
    ).fetchone()
    return None if zeile is None else str(zeile["beschreibung"])


def _bezeichnungen(conn: Verbindung) -> dict[str, dict[str, str]]:
    def lese(tabelle: str) -> dict[str, str]:
        return {
            str(z["code"]): str(z["bezeichnung"])
            for z in conn.execute(f"SELECT code, bezeichnung FROM stat.{tabelle}").fetchall()
        }

    return {
        "traeger": lese("klass_versicherungstraeger"),
        "art": lese("klass_pensionsart"),
        "g": lese("klass_geschlecht"),
    }


def _teilname(namen: dict[str, dict[str, str]], gliederung: str | None, teil: str) -> str:
    if gliederung == "traeger":
        return namen["traeger"][teil]
    if gliederung == "art":
        return namen["art"][teil]
    return namen["g"][teil]


def _frage_sql(
    von: int, bis: int, art: str, knoten: str, geschlecht: str | None, gliederung: str | None
) -> str:
    """Eine Leseabfrage für den Beleg. Die Codes stammen aus der Regel, nie aus dem Fragetext."""
    teil = {
        "traeger": "k.code",
        "art": "s.pensionsart",
        "geschlecht": "s.geschlecht",
        None: "NULL::text",
    }[gliederung]
    bedingung = [
        f"t.wurzel = '{knoten}'",
        f"s.zeitraum_von BETWEEN make_date({von}, 1, 1) AND make_date({bis}, 1, 1)",
        f"(s.pensionsart = '{art}' OR a.uebergeordnet = '{art}')",
    ]
    if geschlecht:
        bedingung.append(f"s.geschlecht = '{geschlecht}'")
    if gliederung == "traeger":
        # Träger, nicht Bereiche: je Bereich der Träger darüber, wenn es ihn gibt.
        verbund = (
            "JOIN stat.klass_versicherungstraeger b ON b.code = s.versicherungstraeger\n"
            "JOIN stat.klass_versicherungstraeger k ON k.code = CASE WHEN b.ebene = 4 THEN b.uebergeordnet ELSE b.code END"
        )
    else:
        verbund = ""
    return f"""WITH RECURSIVE baum AS (
  SELECT code, code AS wurzel FROM stat.klass_versicherungstraeger
  UNION ALL
  SELECT k.code, b.wurzel FROM stat.klass_versicherungstraeger k JOIN baum b ON k.uebergeordnet = b.code
)
SELECT extract(year FROM s.zeitraum_von)::int AS jahr, {teil} AS teil, sum(s.wert)::bigint AS wert,
       min(s.status) AS status
FROM stat.stat_pensionen s
JOIN stat.klass_pensionsart a ON a.code = s.pensionsart
JOIN baum t ON t.code = s.versicherungstraeger
{verbund}
WHERE {" AND ".join(bedingung)}
GROUP BY 1, 2
ORDER BY 1, 2"""
