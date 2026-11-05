"""Prüfung der Abgabedateien vor dem Hochladen (Vollständigkeit und Form, ohne Datenbank).

Jeder Punkt ist entweder erfüllt oder „fehlt“ mit Hinweis; ein fehlender oder kaputter Teil bricht die
Prüfung nicht ab. `ok` gilt nur, wenn alle Punkte erfüllt sind.
"""

from __future__ import annotations

import csv
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from statagent import konfig
from statagent.berichte.qualitaetsbericht import ABSCHNITTE, GUELTIGE_EINSTUFUNGEN
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


def vorlage_blaetter() -> list[str]:
    """Blattnamen der Veranstaltervorlage; ohne Startpaket die bekannte Liste."""
    vorlage = konfig.vorlagen() / "aggregationen_vorlage.xlsx"
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


def einstufungen_aus_bericht(text: str) -> list[str]:
    """Inhalte der Spalte „Einstufung“ in der Tabelle von Abschnitt 2."""
    zeilen = text.splitlines()
    try:
        start = zeilen.index(ABSCHNITTE[1])
    except ValueError:
        return []
    spalte: int | None = None
    werte: list[str] = []
    for zeile in zeilen[start + 1 :]:
        if zeile.startswith("## "):
            break
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


def bericht_maengel(text: str) -> list[str]:
    """Mängel eines Qualitätsberichts: fehlende Abschnitte, falsche Reihenfolge, ungültige Einstufung."""
    maengel: list[str] = []
    ueberschriften = [z.rstrip() for z in text.splitlines() if z.startswith("## ")]
    vorhanden = [u for u in ueberschriften if u in ABSCHNITTE]
    fehlend = [u for u in ABSCHNITTE if u not in vorhanden]
    if fehlend:
        maengel.append("fehlt " + ", ".join(f"„{u[3:]}“" for u in fehlend))
    elif vorhanden != list(ABSCHNITTE):
        maengel.append("Abschnitte nicht in der Reihenfolge der Vorlage")
    falsch = sorted({e for e in einstufungen_aus_bericht(text) if e not in GUELTIGE_EINSTUFUNGEN})
    if falsch:
        maengel.append("ungültige Einstufung " + ", ".join(f"„{e}“" for e in falsch))
    return maengel


# --- Punkte ------------------------------------------------------------------------------------------


def _punkt_sheet(pfad: Path, name: str, blaetter: list[str] | None) -> Punkt:
    if not pfad.is_file():
        return Punkt(name, False, f"{pfad.name} nicht gefunden")
    try:
        gelesen = _blaetter(pfad)
    except Exception as fehler:
        return Punkt(name, False, f"{pfad.name} nicht lesbar ({type(fehler).__name__})")
    if blaetter is not None and gelesen != blaetter:
        return Punkt(name, False, f"Blätter {gelesen} statt {blaetter} wie in der Vorlage")
    return Punkt(name, True, f"{pfad.name} lesbar, {len(gelesen)} Blätter")


def _punkt_berichte(abgabe_dir: Path) -> Punkt:
    name = "Qualitätsberichte 2024-08 bis 2026-07"
    ordner = abgabe_dir / "qualitaetsberichte"
    fehlend: list[str] = []
    mangelhaft: list[str] = []
    for monat in berichtsmonate():
        datei = ordner / f"{monat}.md"
        if not datei.is_file():
            fehlend.append(monat)
            continue
        maengel = bericht_maengel(datei.read_text(encoding="utf-8"))
        if maengel:
            mangelhaft.append(f"{monat} ({'; '.join(maengel)})")
    if not fehlend and not mangelhaft:
        return Punkt(name, True, f"{MONATE} Berichte mit fünf Abschnitten und gültigen Einstufungen")
    hinweise = []
    if fehlend:
        hinweise.append(f"{len(fehlend)} von {MONATE} fehlen: {', '.join(fehlend)}")
    if mangelhaft:
        hinweise.append("mangelhaft: " + ", ".join(mangelhaft))
    return Punkt(name, False, "; ".join(hinweise))


def _punkt_ministerium(abgabe_dir: Path) -> Punkt:
    name = "Ministeriums-Lieferung 2026-07"
    pfad = abgabe_dir / "ministerium_2026-07.csv"
    if not pfad.is_file():
        return Punkt(name, False, f"{pfad.name} nicht gefunden")
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


def pruefe_abgabe(abgabe_dir: Path, repo_wurzel: Path, blaetter: list[str] | None = None) -> Pruefergebnis:
    """Prüft den Abgabeordner. `blaetter` überschreibt die Blattnamen der Vorlage (sonst aus dem Startpaket)."""
    soll = blaetter if blaetter is not None else vorlage_blaetter()
    return Pruefergebnis(
        [
            _punkt_sheet(abgabe_dir / "aggregationen_v1.xlsx", "Aggregations-Sheet v1", soll),
            _punkt_berichte(abgabe_dir),
            _punkt_ministerium(abgabe_dir),
            _punkt_protokoll(abgabe_dir),
            _punkt_modelle(abgabe_dir, repo_wurzel),
            _punkt_sheet(
                abgabe_dir / "aggregationen_v2.xlsx", "Aggregations-Sheet v2 (nach Änderungsaufträgen)", None
            ),
            _punkt_konstanten(repo_wurzel),
        ]
    )
