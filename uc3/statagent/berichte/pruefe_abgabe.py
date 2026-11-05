"""Prüfung der Abgabedateien vor dem Hochladen (Vollständigkeit, Form und Inhalt).

Jeder Punkt ist entweder erfüllt oder „fehlt“ mit Hinweis; ein fehlender oder kaputter Teil bricht die
Prüfung nicht ab. `ok` gilt nur, wenn alle Punkte erfüllt sind.

- Qualitätsberichte werden gegen ``qualitaetsbericht_vorlage.md`` des Veranstalters geprüft (Titel,
  Abschnittsüberschriften, Einstufungen), nicht gegen den eigenen Generator. Fehlt die Vorlage, prüft die
  Struktur gegen den Generator und der Punkt „Vorlage Qualitätsbericht“ fehlt (kein stilles ok).
- Sheets werden inhaltlich geprüft: Monatsspalten je Ergebnisblatt vorhanden und gefüllt, Insgesamt als
  ``=SUM`` über genau die Datenzeilen, gleiche Summe je Monat auf allen Blättern. Mit Datenbank (`conn`)
  zusätzlich Summe je Monat = Gesamtzahl aus stat.stat_beschaeftigte des maßgeblichen Laufs.
"""

from __future__ import annotations

import csv
import hashlib
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from statagent import ergebnis, konfig
from statagent.berichte.qualitaetsbericht import ABSCHNITTE, GUELTIGE_EINSTUFUNGEN
from statagent.berichte.sheet import (
    BLATT_BUNDESLAND,
    BLATT_GESCHLECHT,
    BLATT_KATEGORIE,
    OENACE_PRAEFIX,
    STICHTAG,
    STICHTAG_VARIABLE,
    VORLAGE_DATEI,
    _blatt_lesen,
)
from statagent.db import Verbindung
from statagent.ergebnis import monat_verschieben

ERSTER_MONAT, MONATE = "2024-08", 24
MINISTERIUM_KOPF = ["PERSON_ID", "GESCHLECHT", "GEBURTSJAHR", "TAGE"]
MINDEST_TAGE = 200
#: Blätter der Veranstaltervorlage, falls die Vorlage nicht greifbar ist (CI ohne Startpaket).
VORLAGE_BLAETTER = [
    "Hinweise",
    "Bundesland",
    "Geschlecht",
    "OENACE_2008",
    "OENACE_2025",
    "Beschaeftigungskategorie",
]
# Muster für Regelkonstanten im Code (Technische Regel 3). Zusammengesetzt, damit diese Datei selbst
# nicht als Treffer zählt.
KONSTANTEN_MUSTER = re.compile(r"""(['"])U""" + r"""NB\1|D\[""" + "A-")
_ZELLGRENZE = re.compile(r"(?<!\\)\|")

BERICHT_VORLAGE = "qualitaetsbericht_vorlage.md"
MONAT_PLATZHALTER = "JJJJ-MM"
#: Ein Bericht mit weniger Zeilen gilt als leer (der kürzeste echte Bericht hat über 150).
MINDEST_ZEILEN = 20
#: Ergebnisblätter des Sheets; ÖNACE 2008 bis 2024-12, ÖNACE 2025 ab 2025-01 (Hinweise-Blatt der Vorlage).
ERGEBNIS_BLAETTER = (
    BLATT_BUNDESLAND,
    BLATT_GESCHLECHT,
    OENACE_PRAEFIX + "2008",
    OENACE_PRAEFIX + "2025",
    BLATT_KATEGORIE,
)
OENACE_WECHSEL = "2025-01"
_ABRECHNUNG = re.compile(
    r"Abrechnung in Zahlen: ([\d.]+) gelesen(?: \+ ([\d.]+) fortgeschrieben)? = ([\d.]+) gezählt"
    r" \+ ([\d.]+) nicht gezählt \+ ([\d.]+) ausgeschlossen \((geht auf|geht NICHT auf)\)"
)
_HOECHSTENS = 8


@dataclass(frozen=True)
class BerichtStruktur:
    """Was ein Qualitätsbericht tragen muss: Titel (mit JJJJ-MM), Abschnitte, erlaubte Einstufungen."""

    titel: str
    abschnitte: tuple[str, ...]
    einstufungen: frozenset[str]


GENERATOR_STRUKTUR = BerichtStruktur(
    f"# Qualitätsbericht – Berichtsmonat {MONAT_PLATZHALTER}", tuple(ABSCHNITTE), GUELTIGE_EINSTUFUNGEN
)


@dataclass(frozen=True)
class Punkt:
    name: str
    ok: bool
    hinweis: str


@dataclass
class Pruefergebnis:
    punkte: list[Punkt] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return bool(self.punkte) and all(p.ok for p in self.punkte)

    def als_dict(self) -> dict[str, Any]:
        return {"ok": self.ok, "punkte": [asdict(p) for p in self.punkte]}

    def als_text(self) -> str:
        zeilen = [f"[{'ok' if p.ok else 'fehlt'}] {p.name}: {p.hinweis}" for p in self.punkte]
        zeilen.append("Abgabe vollständig." if self.ok else "Abgabe NICHT vollständig.")
        return "\n".join(zeilen)


def berichtsmonate() -> list[str]:
    return [monat_verschieben(ERSTER_MONAT, i) for i in range(MONATE)]


def vorlage_blaetter(vorlagen_dir: Path | None = None) -> list[str]:
    """Blattnamen der Veranstaltervorlage; ohne Startpaket die bekannte Liste."""
    vorlage = (vorlagen_dir or konfig.vorlagen()) / VORLAGE_DATEI
    if vorlage.is_file():
        try:
            return _blaetter(vorlage)
        except Exception:
            pass
    return list(VORLAGE_BLAETTER)


def _blaetter(pfad: Path) -> list[str]:
    import openpyxl

    mappe = openpyxl.load_workbook(pfad, read_only=True)
    try:
        return [str(n) for n in mappe.sheetnames]
    finally:
        mappe.close()


def _zellen(zeile: str) -> list[str]:
    return [z.strip() for z in _ZELLGRENZE.split(zeile.strip().strip("|"))]


def struktur_aus_vorlage(text: str) -> BerichtStruktur:
    """Titel, Abschnittsüberschriften und Einstufungen (fett in der Zeile „Einstufung:“) der Vorlage."""
    zeilen = [z.rstrip() for z in text.splitlines()]
    titel = next((z for z in zeilen if z.startswith("# ")), "")
    abschnitte = tuple(z for z in zeilen if z.startswith("## "))
    legende = next((z for z in zeilen if z.startswith("Einstufung:")), "")
    return BerichtStruktur(titel, abschnitte, frozenset(re.findall(r"\*\*(.+?)\*\*", legende)))


def bericht_struktur(vorlagen_dir: Path | None = None) -> tuple[BerichtStruktur, Punkt]:
    """Struktur aus der Vorlage des Veranstalters; fehlt sie, die des Generators und ein fehlender Punkt."""
    name = "Vorlage Qualitätsbericht"
    pfad = (vorlagen_dir or konfig.vorlagen()) / BERICHT_VORLAGE
    if not pfad.is_file():
        return GENERATOR_STRUKTUR, Punkt(
            name, False, "Vorlage nicht gefunden: Struktur nur gegen den Generator geprüft"
        )
    struktur = struktur_aus_vorlage(pfad.read_text(encoding="utf-8"))
    luecken = [
        teil
        for teil, wert in (
            ("Titel mit JJJJ-MM", MONAT_PLATZHALTER in struktur.titel),
            ("Abschnitte", bool(struktur.abschnitte)),
            ("Einstufungen", bool(struktur.einstufungen)),
        )
        if not wert
    ]
    if luecken:
        return GENERATOR_STRUKTUR, Punkt(
            name, False, f"{pfad.name} ohne {', '.join(luecken)}: Struktur nur gegen den Generator geprüft"
        )
    return struktur, Punkt(
        name,
        True,
        f"{pfad.name}: {len(struktur.abschnitte)} Abschnitte, {len(struktur.einstufungen)} Einstufungen",
    )


def _abschnitt(zeilen: list[str], ueberschrift: str) -> list[str] | None:
    """Zeilen eines Abschnitts bis zur nächsten Überschrift ``## ``; None, wenn er fehlt."""
    try:
        start = zeilen.index(ueberschrift)
    except ValueError:
        return None
    aus: list[str] = []
    for zeile in zeilen[start + 1 :]:
        if zeile.startswith("## "):
            break
        aus.append(zeile)
    return aus


def einstufungen_aus_bericht(text: str, abschnitt: str = ABSCHNITTE[1]) -> list[str]:
    """Inhalte der Spalte „Einstufung“ in der Tabelle von Abschnitt 2 (eine je Datenzeile)."""
    zeilen = _abschnitt([z.rstrip() for z in text.splitlines()], abschnitt)
    if zeilen is None:
        return []
    spalte: int | None = None
    werte: list[str] = []
    for zeile in zeilen:
        if not zeile.startswith("|"):
            continue
        zellen = _zellen(zeile)
        if spalte is None:
            if "Einstufung" in zellen:
                spalte = zellen.index("Einstufung")
            continue
        if all(set(z) <= set("-: ") for z in zellen):
            continue  # Trennzeile
        werte.append(zellen[spalte] if spalte < len(zellen) else "")
    return werte


def _zahl(text: str | None) -> int:
    return int(text.replace(".", "")) if text else 0


def _abrechnung_mangel(ueberblick: list[str]) -> str | None:
    """§ 1 muss die Zeile „Abrechnung in Zahlen“ tragen, und sie muss aufgehen (Text und Rechnung)."""
    treffer = next((t for t in map(_ABRECHNUNG.search, ueberblick) if t), None)
    if treffer is None:
        return "§ 1 ohne Zeile „Abrechnung in Zahlen“"
    gelesen, fort, gezaehlt, nicht, aus = (_zahl(treffer.group(i)) for i in range(1, 6))
    if treffer.group(6) != "geht auf" or gelesen + fort != gezaehlt + nicht + aus:
        return "Abrechnung in § 1 geht nicht auf"
    return None


def bericht_maengel(
    text: str, struktur: BerichtStruktur = GENERATOR_STRUKTUR, monat: str | None = None
) -> list[str]:
    """Mängel eines Qualitätsberichts gegen die Struktur der Vorlage.

    Geprüft: Länge, Titel (mit `monat`, wenn angegeben), alle Abschnitte in der Reihenfolge der Vorlage,
    Abrechnungszeile in § 1, mindestens eine Tabellenzeile in § 2, nur erlaubte Einstufungen.
    """
    maengel: list[str] = []
    zeilen = [z.rstrip() for z in text.splitlines()]
    if len([z for z in zeilen if z.strip()]) < MINDEST_ZEILEN:
        maengel.append(f"weniger als {MINDEST_ZEILEN} Zeilen (leer)")
    titel = next((z for z in zeilen if z.startswith("# ")), "")
    if monat is not None and titel != struktur.titel.replace(MONAT_PLATZHALTER, monat):
        maengel.append(f"Titel „{titel[2:]}“ passt nicht zu {monat}")
    vorhanden = [u for u in zeilen if u.startswith("## ") and u in struktur.abschnitte]
    fehlend = [u for u in struktur.abschnitte if u not in vorhanden]
    if fehlend:
        maengel.append("fehlt " + ", ".join(f"„{u[3:]}“" for u in fehlend))
    elif vorhanden != list(struktur.abschnitte):
        maengel.append("Abschnitte nicht in der Reihenfolge der Vorlage")
    ueberblick = _abschnitt(zeilen, struktur.abschnitte[0]) if struktur.abschnitte else None
    if ueberblick is not None:
        mangel = _abrechnung_mangel(ueberblick)
        if mangel:
            maengel.append(mangel)
    if len(struktur.abschnitte) > 1:
        einstufungen = einstufungen_aus_bericht(text, struktur.abschnitte[1])
        if struktur.abschnitte[1] in zeilen and not einstufungen:
            maengel.append(f"„{struktur.abschnitte[1][3:]}“ ohne Tabellenzeile")
        falsch = sorted({e for e in einstufungen if e not in struktur.einstufungen})
        if falsch:
            maengel.append("ungültige Einstufung " + ", ".join(f"„{e}“" for e in falsch))
    return maengel


def blatt_monate(blatt: str) -> list[str]:
    """Berichtsmonate, die ein Ergebnisblatt tragen muss (ÖNACE-Wechsel zum 2025-01)."""
    alle = berichtsmonate()
    if blatt == OENACE_PRAEFIX + "2008":
        return [m for m in alle if m < OENACE_WECHSEL]
    if blatt == OENACE_PRAEFIX + "2025":
        return [m for m in alle if m >= OENACE_WECHSEL]
    return alle


def _ist_zahl(wert: object) -> bool:
    if isinstance(wert, bool):
        return False
    return isinstance(wert, int) or (isinstance(wert, float) and wert.is_integer())


def _db_gesamt(conn: Verbindung, monat: str, regelsatz: str) -> int | None:
    """Beschäftigungsverhältnisse am Stichtag des maßgeblichen Laufs (Muster `sheet.sheet_schreiben`)."""
    if ergebnis.letzter_lauf(conn, monat, regelsatz) is None:
        return None
    return sum(
        int(str(z["wert"]))
        for z in ergebnis.monatswerte(conn, monat, regelsatz)
        if z["zeitraum_art"] == STICHTAG and z["variable"] == STICHTAG_VARIABLE
    )


def sheet_maengel(pfad: Path, conn: Verbindung | None = None, regelsatz: str | None = None) -> list[str]:
    """Inhaltliche Mängel eines Aggregations-Sheets (Monatsspalten, Insgesamt-Formel, Blattsummen, DB)."""
    from openpyxl import load_workbook
    from openpyxl.utils import get_column_letter

    mappe = load_workbook(pfad)  # Formeln, nicht zwischengespeicherte Werte
    maengel: list[str] = []
    summen: dict[str, dict[str, int]] = {}
    try:
        for name in ERGEBNIS_BLAETTER:
            if name not in mappe.sheetnames:
                maengel.append(f"Blatt {name} fehlt")
                continue
            try:
                blatt = _blatt_lesen(mappe[name])
            except ValueError as fehler:
                maengel.append(str(fehler))
                continue
            datenzeilen = sorted(blatt.zeilen.values())
            if not datenzeilen:
                maengel.append(f"{name}: keine Datenzeilen")
                continue
            summen[name] = {}
            for monat in blatt_monate(name):
                spalte = blatt.spalten.get(monat)
                if spalte is None:
                    maengel.append(f"{name}: Spalte {monat} fehlt")
                    continue
                werte = [blatt.ws.cell(r, spalte).value for r in datenzeilen]
                belegt = [w for w in werte if w is not None and str(w).strip()]
                if not belegt:
                    maengel.append(f"{name} {monat}: Spalte leer")
                    continue
                if not all(_ist_zahl(w) for w in belegt):
                    maengel.append(f"{name} {monat}: Werte nicht ganzzahlig")
                    continue
                summen[name][monat] = sum(int(w) for w in belegt)
                b = get_column_letter(spalte)
                soll = f"=SUM({b}{datenzeilen[0]}:{b}{datenzeilen[-1]})"
                ist = blatt.ws.cell(blatt.insgesamt, spalte).value
                if not (isinstance(ist, str) and ist.replace(" ", "").upper() == soll):
                    maengel.append(f"{name} {monat}: Insgesamt {ist!r} statt {soll}")
    finally:
        mappe.close()

    for monat in berichtsmonate():
        je_blatt = {n: s[monat] for n, s in summen.items() if monat in s}
        if not je_blatt:
            continue
        if len(set(je_blatt.values())) > 1:
            maengel.append(
                f"{monat}: Blattsummen ungleich ({', '.join(f'{n} {w}' for n, w in je_blatt.items())})"
            )
            continue
        summe = next(iter(je_blatt.values()))
        if summe <= 0:
            maengel.append(f"{monat}: Summe {summe}")
        elif conn is not None and regelsatz is not None:
            soll_db = _db_gesamt(conn, monat, regelsatz)
            if soll_db is None:
                maengel.append(f"{monat}: kein Lauf für Regelsatz {regelsatz}")
            elif soll_db != summe:
                maengel.append(f"{monat}: Blattsumme {summe} ≠ stat.stat_beschaeftigte {soll_db}")
    return maengel


def _gekuerzt(maengel: list[str]) -> str:
    rest = len(maengel) - _HOECHSTENS
    return "; ".join(maengel[:_HOECHSTENS]) + (f"; … und {rest} weitere" if rest > 0 else "")


# --- Punkte ------------------------------------------------------------------------------------------


def _punkt_sheet(pfad: Path, name: str, blaetter: list[str] | None, conn: Verbindung | None) -> Punkt:
    if not pfad.is_file():
        return Punkt(name, False, f"{pfad.name} nicht gefunden")
    try:
        gelesen = _blaetter(pfad)
        # aggregationen_<regelsatz>.xlsx (sheet.sheet_schreiben)
        maengel = sheet_maengel(pfad, conn, pfad.stem.removeprefix("aggregationen_"))
    except Exception as fehler:
        return Punkt(name, False, f"{pfad.name} nicht lesbar ({type(fehler).__name__})")
    if blaetter is not None and gelesen != blaetter:
        maengel.insert(0, f"Blätter {gelesen} statt {blaetter} wie in der Vorlage")
    if maengel:
        return Punkt(name, False, f"{pfad.name}: {_gekuerzt(maengel)}")
    db = ", Summen = stat.stat_beschaeftigte" if conn is not None else ", ohne Datenbankabgleich"
    return Punkt(
        name,
        True,
        f"{pfad.name}: {len(gelesen)} Blätter, Monatsspalten gefüllt, Insgesamt-Formeln und Blattsummen"
        f" stimmen{db}",
    )


def _punkt_berichte(abgabe_dir: Path, struktur: BerichtStruktur) -> Punkt:
    name = "Qualitätsberichte 2024-08 bis 2026-07"
    ordner = abgabe_dir / "qualitaetsberichte"
    fehlend: list[str] = []
    mangelhaft: list[str] = []
    for monat in berichtsmonate():
        datei = ordner / f"{monat}.md"
        if not datei.is_file():
            fehlend.append(monat)
            continue
        maengel = bericht_maengel(datei.read_text(encoding="utf-8"), struktur, monat)
        if maengel:
            mangelhaft.append(f"{monat} ({'; '.join(maengel)})")
    if not fehlend and not mangelhaft:
        return Punkt(
            name,
            True,
            f"{MONATE} Berichte mit {len(struktur.abschnitte)} Abschnitten, Monat im Titel, aufgehender"
            " Abrechnung und gültigen Einstufungen",
        )
    hinweise = []
    if fehlend:
        hinweise.append(f"{len(fehlend)} von {MONATE} fehlen: {', '.join(fehlend)}")
    if mangelhaft:
        hinweise.append("mangelhaft: " + _gekuerzt(mangelhaft))
    return Punkt(name, False, "; ".join(hinweise))


def _beleg_sha256(beleg: Path) -> str | None:
    """sha256 aus dem Beleg ``ministerium_<monat>.beleg.md`` (Zeile „| sha256 | `…` |“), sonst None."""
    treffer = re.search(
        r"^\| sha256 \| `([0-9a-f]{64})` \|$", beleg.read_text(encoding="utf-8"), re.MULTILINE
    )
    return treffer.group(1) if treffer else None


def _punkt_ministerium(abgabe_dir: Path) -> Punkt:
    """Die CSV enthält Einzeldaten und liegt nicht im Repo (abgabe/.gitignore); im Repo steht der Beleg mit sha256.

    Mit CSV (lokal, SV-Box) wird sie geprüft und gegen die sha256 des Belegs abgeglichen; ohne CSV reicht der
    freigegebene Beleg (Entscheid Lead 58, #16).
    """
    name = "Ministeriums-Lieferung 2026-07"
    pfad = abgabe_dir / "ministerium_2026-07.csv"
    beleg = abgabe_dir / "ministerium_2026-07.beleg.md"
    sha = _beleg_sha256(beleg) if beleg.is_file() else None
    if beleg.is_file() and sha is None:
        return Punkt(name, False, f"{beleg.name} ohne sha256-Zeile")
    if not pfad.is_file():
        if sha is not None:
            return Punkt(
                name,
                True,
                f"{pfad.name} nicht im Repo (Einzeldaten, Abgabe über SV-Box); Beleg sha256 {sha[:12]}",
            )
        return Punkt(name, False, f"weder {pfad.name} noch {beleg.name} gefunden")
    if sha is not None and hashlib.sha256(pfad.read_bytes()).hexdigest() != sha:
        return Punkt(name, False, f"{pfad.name} passt nicht zur sha256 im Beleg")
    with pfad.open(encoding="utf-8", newline="") as f:
        zeilen = list(csv.reader(f, delimiter=";"))
    if not zeilen or zeilen[0] != MINISTERIUM_KOPF:
        return Punkt(name, False, f"Kopf muss {';'.join(MINISTERIUM_KOPF)} sein")
    daten = zeilen[1:]
    if not daten:
        return Punkt(name, False, "keine Datenzeilen")
    if any(len(z) != len(MINISTERIUM_KOPF) for z in daten):
        return Punkt(name, False, "Zeilen mit falscher Spaltenzahl")
    ids = [z[0] for z in daten]
    schluessel = [int(i) for i in ids] if all(i.isdigit() for i in ids) else ids
    if schluessel != sorted(schluessel):
        return Punkt(name, False, "nicht nach PERSON_ID sortiert")
    zu_wenig = [z[0] for z in daten if not z[3].isdigit() or int(z[3]) < MINDEST_TAGE]
    if zu_wenig:
        return Punkt(name, False, f"{len(zu_wenig)} Zeilen mit TAGE < {MINDEST_TAGE} oder nicht numerisch")
    return Punkt(name, True, f"{len(daten)} Personen, sortiert, TAGE ≥ {MINDEST_TAGE}")


def _punkt_protokoll(abgabe_dir: Path) -> Punkt:
    pfad = abgabe_dir / "protokoll.md"
    if not pfad.is_file():
        return Punkt("Protokoll", False, "protokoll.md nicht gefunden")
    if not pfad.read_text(encoding="utf-8").strip():
        return Punkt("Protokoll", False, "protokoll.md ist leer")
    return Punkt("Protokoll", True, "protokoll.md vorhanden")


def _punkt_modelle(abgabe_dir: Path, repo_wurzel: Path) -> Punkt:
    for pfad in (repo_wurzel / "docs" / "models.md", abgabe_dir / "modelle.md"):
        if pfad.is_file() and pfad.read_text(encoding="utf-8").strip():
            return Punkt("Modellangabe", True, f"{pfad.name} vorhanden")
    return Punkt("Modellangabe", False, "weder docs/models.md noch abgabe/modelle.md vorhanden")


def _punkt_konstanten(repo_wurzel: Path) -> Punkt:
    name = "keine Regelkonstanten im Code (Technische Regel 3)"
    paket = repo_wurzel / "uc3" / "statagent"
    if not paket.is_dir():
        return Punkt(name, False, f"{paket.relative_to(repo_wurzel)} nicht gefunden")
    treffer: list[str] = []
    for datei in sorted(paket.rglob("*.py")):
        if datei.name == "regeln.py":
            continue
        for nr, zeile in enumerate(datei.read_text(encoding="utf-8").splitlines(), start=1):
            if KONSTANTEN_MUSTER.search(zeile):
                treffer.append(f"{datei.relative_to(repo_wurzel)}:{nr}")
    if treffer:
        return Punkt(name, False, "Treffer: " + ", ".join(treffer))
    return Punkt(name, True, "kein Treffer außerhalb von regeln.py")


def pruefe_abgabe(
    abgabe_dir: Path,
    repo_wurzel: Path,
    blaetter: list[str] | None = None,
    *,
    conn: Verbindung | None = None,
    vorlagen_dir: Path | None = None,
) -> Pruefergebnis:
    """Prüft den Abgabeordner.

    `blaetter` überschreibt die Blattnamen der Vorlage, `vorlagen_dir` den Vorlagenordner (sonst
    `konfig.vorlagen()`). Mit `conn` werden die Sheet-Summen zusätzlich gegen die Datenbank geprüft.
    """
    soll = blaetter if blaetter is not None else vorlage_blaetter(vorlagen_dir)
    struktur, vorlage_punkt = bericht_struktur(vorlagen_dir)
    return Pruefergebnis(
        [
            _punkt_sheet(abgabe_dir / "aggregationen_v1.xlsx", "Aggregations-Sheet v1", soll, conn),
            _punkt_berichte(abgabe_dir, struktur),
            vorlage_punkt,
            _punkt_ministerium(abgabe_dir),
            _punkt_protokoll(abgabe_dir),
            _punkt_modelle(abgabe_dir, repo_wurzel),
            _punkt_sheet(
                abgabe_dir / "aggregationen_v2.xlsx",
                "Aggregations-Sheet v2 (nach Änderungsaufträgen)",
                None,
                conn,
            ),
            _punkt_konstanten(repo_wurzel),
        ]
    )
