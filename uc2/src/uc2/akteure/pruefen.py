"""Prüfung des Akteurs-Pools und der Modellrollen für `uv run uc2 akteure pruefen`.

Sammelt alle Fehler statt beim ersten abzubrechen. Geprüft wird:

- genau die 14 Akteursdateien zu den IDs aus `institutionen.yaml`, keine weiteren,
- jede Frontmatter gegen `akteur.schema.json`, `id` = Dateiname, `institution` existiert,
- Body mit `## Auftrag` und `## Ausgabeschema`,
- jede Sprachmodell-Rolle hat `zweck` und ein Modell für azure, claude und mock; Code-Rollen haben keines,
- Namens- und Parteienscan über Akteursdateien und `modellrollen.yaml` ergibt 0 Treffer.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import jsonschema

from uc2 import pfade
from uc2.akteure import namensscan
from uc2.akteure.laden import (
    SPRACHMODELL_PROVIDER,
    AkteurFehler,
    lade_institutionen,
    lade_schema,
    lies_akteursdatei,
    lies_modellrollen,
)

SPRACHMODELL_ROLLEN: tuple[str, ...] = ("moderator", "akteur")
CODE_ROLLEN: tuple[str, ...] = (
    "experte",
    "suche",
    "matrix",
    "klassifikation",
    "pruefungen",
    "personenschutz",
)
ANZAHL_AKTEURE = 14


@dataclass
class Ergebnis:
    """Ergebnis der Prüfung; `ok` nur ohne Fehler."""

    akteure: list[str] = field(default_factory=list)
    rollen: list[str] = field(default_factory=list)
    fehler: list[str] = field(default_factory=list)
    hinweise: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.fehler

    def als_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "akteure": self.akteure,
            "rollen": self.rollen,
            "fehler": self.fehler,
            "hinweise": self.hinweise,
        }


def _schemafehler(validator: jsonschema.Draft202012Validator, daten: object, praefix: str) -> list[str]:
    meldungen = []
    for f in sorted(validator.iter_errors(daten), key=lambda f: list(f.absolute_path)):
        stelle = "/".join(str(t) for t in f.absolute_path) or "(Wurzel)"
        meldungen.append(f"{praefix}: {stelle}: {f.message}")
    return meldungen


def pruefe_akteure(akteure: Path, config: Path, ergebnis: Ergebnis) -> None:
    """Dateien, Schema, IDs und Institutionen prüfen."""
    ids = lade_institutionen(config)
    if len(ids) != ANZAHL_AKTEURE or len(set(ids)) != len(ids):
        ergebnis.fehler.append(
            f"institutionen.yaml: {ANZAHL_AKTEURE} eindeutige IDs erwartet, {len(ids)} gefunden"
        )
    vorhanden = {p.stem for p in akteure.glob("*.md")}
    for iid in ids:
        if iid not in vorhanden:
            ergebnis.fehler.append(f"Akteursdatei fehlt: {iid}.md")
    for fremd in sorted(vorhanden - set(ids)):
        ergebnis.fehler.append(f"{fremd}.md: keine Institution mit dieser ID in institutionen.yaml")

    validator = jsonschema.Draft202012Validator(lade_schema("akteur"))
    for iid in sorted(vorhanden):
        pfad = akteure / f"{iid}.md"
        try:
            daten, body = lies_akteursdatei(pfad)
        except AkteurFehler as fehler:
            ergebnis.fehler.append(str(fehler))
            continue
        meldungen = _schemafehler(validator, daten, pfad.name)
        ergebnis.fehler.extend(meldungen)
        if daten.get("id") != iid:
            ergebnis.fehler.append(f"{pfad.name}: id {daten.get('id')!r} passt nicht zum Dateinamen")
        institution = daten.get("institution")
        if institution not in ids:
            ergebnis.fehler.append(f"{pfad.name}: unbekannte institution {institution!r}")
        elif institution != iid:
            ergebnis.fehler.append(
                f"{pfad.name}: institution {institution!r} muss der Dateiname {iid!r} sein"
            )
        for abschnitt in ("## Auftrag", "## Ausgabeschema"):
            if abschnitt not in body:
                ergebnis.fehler.append(f"{pfad.name}: Abschnitt '{abschnitt}' fehlt")
        if not meldungen and iid in ids:
            ergebnis.akteure.append(iid)


def pruefe_modellrollen(config: Path, ergebnis: Ergebnis) -> None:
    """Rollen, Zweck und Modell je Provider prüfen."""
    try:
        daten = lies_modellrollen(config)
    except AkteurFehler as fehler:
        ergebnis.fehler.append(str(fehler))
        return
    if not isinstance(daten.get("luecke"), str) or not daten["luecke"].strip():
        ergebnis.fehler.append("modellrollen.yaml: Feld 'luecke' fehlt")
    rollen: dict[str, Any] = daten["rollen"]
    for name in (*SPRACHMODELL_ROLLEN, *CODE_ROLLEN):
        if name not in rollen:
            ergebnis.fehler.append(f"modellrollen.yaml: Rolle '{name}' fehlt")
    for name, eintrag in rollen.items():
        praefix = f"modellrollen.yaml: Rolle '{name}'"
        if not isinstance(eintrag, dict) or not isinstance(eintrag.get("sprachmodell"), bool):
            ergebnis.fehler.append(f"{praefix}: Feld 'sprachmodell' (true/false) fehlt")
            continue
        provider = eintrag.get("provider") or {}
        if not isinstance(provider, dict):
            ergebnis.fehler.append(f"{praefix}: 'provider' ist keine Zuordnung")
            continue
        if eintrag["sprachmodell"]:
            if eintrag.get("zweck") != f"uc2.{name}":
                ergebnis.fehler.append(f"{praefix}: zweck muss 'uc2.{name}' sein")
            for p in SPRACHMODELL_PROVIDER:
                angabe = provider.get(p)
                modell = angabe.get("modell") if isinstance(angabe, dict) else None
                if not isinstance(modell, str) or not modell.strip():
                    ergebnis.fehler.append(f"{praefix}: kein Modell für Provider '{p}'")
        elif provider:
            ergebnis.fehler.append(f"{praefix}: Rolle ohne Sprachmodell darf keine Provider nennen")
        ergebnis.rollen.append(str(name))


def pruefe_namen(akteure: Path, config: Path, ergebnis: Ergebnis) -> None:
    """Namens- und Parteienscan; externe Namensliste über `UC2_NAMENSLISTE` (optional)."""
    namen, hinweis = namensscan.lade_namensliste()
    if hinweis:
        ergebnis.hinweise.append(hinweis)
    dateien = [*sorted(akteure.glob("*.md")), config / "modellrollen.yaml"]
    vorhandene = [p for p in dateien if p.is_file()]
    ergebnis.fehler.extend(f"Namensscan: {t}" for t in namensscan.scanne_dateien(vorhandene, namen))


def pruefe(akteure: Path | None = None, config: Path | None = None) -> Ergebnis:
    """Gesamtprüfung; Standardorte aus `uc2.pfade`."""
    ordner = akteure or pfade.AKTEURE
    konfig = config or pfade.CONFIG
    ergebnis = Ergebnis()
    try:
        pruefe_akteure(ordner, konfig, ergebnis)
    except AkteurFehler as fehler:
        ergebnis.fehler.append(str(fehler))
    pruefe_modellrollen(konfig, ergebnis)
    pruefe_namen(ordner, konfig, ergebnis)
    return ergebnis


def pruefe_zug(zug: object) -> list[str]:
    """Fehler eines Akteurszugs gegen `zug.schema.json`; leer = gültig (für die Verhandlung, #44)."""
    return _schemafehler(jsonschema.Draft202012Validator(lade_schema("zug")), zug, "zug")
