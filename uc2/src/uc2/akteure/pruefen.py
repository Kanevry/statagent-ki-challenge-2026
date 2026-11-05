"""Prüfung des Akteurs-Pools und der Modellrollen für `uv run uc2 akteure pruefen`.

Sammelt alle Fehler statt beim ersten abzubrechen. Geprüft wird:

- genau die 14 Akteursdateien zu den IDs aus `institutionen.yaml`, keine weiteren,
- jede Frontmatter gegen `akteur.schema.json`, `id` = Dateiname, `institution` existiert,
- Body mit `## Auftrag` und `## Ausgabeschema`,
- jede Sprachmodell-Rolle hat ein Modell für azure, claude und mock; Code-Rollen haben keines,
- jeder Rollen-Zweck steht in `plattform/zwecke.toml`, jeder genannte Provider außer mock ist dort erlaubt,
- kein Institutions-Alias ist ein Themenwort (Eintrag in `themen_interesse` oder Stoppliste),
- Namens- und Parteienscan über Akteursdateien und `modellrollen.yaml` ergibt 0 Treffer.
"""

from __future__ import annotations

import importlib
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import jsonschema

from uc2 import pfade
from uc2.akteure import namensscan
from uc2.akteure.laden import (
    SPRACHMODELL_PROVIDER,
    AkteurFehler,
    lade_aliase,
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

_THEMEN_TEXT = (
    "Kassenstellen Kassenstelle Kassenvertrag Pflege Budget Finanzausgleich Prävention Medikamente "
    "Arzneimittel Generika Medizinprodukte Begutachtung Gesetzesnovelle"
)
THEMENWOERTER: frozenset[str] = frozenset(w.casefold() for w in _THEMEN_TEXT.split())
"""Themenwörter, die nie Alias einer Institution sein dürfen (Review !11); Ergänzung zu `themen_interesse`."""


def lade_zwecktabelle() -> dict[str, Any]:
    """Zweck-Tabelle des Modell-Schalters (`plattform/zwecke.toml`); `AkteurFehler`, wenn nicht importierbar.

    Dynamischer Import: `plattform` kommt aus dem Wurzel-Workspace (`uv sync --all-packages`) und hat
    keine Typinformation; die Tabelle wird hier als Daten gelesen.
    """
    try:
        modul = importlib.import_module("plattform.llm.zwecke")
    except ImportError as fehler:
        raise AkteurFehler(
            f"plattform.llm.zwecke nicht importierbar ({fehler}); an der Repo-Wurzel `uv sync --all-packages`"
        ) from None
    tabelle = modul._tabelle()
    if not isinstance(tabelle, dict):
        raise AkteurFehler("plattform.llm.zwecke._tabelle() liefert keine Zuordnung")
    return tabelle


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


def pruefe_modellrollen(config: Path, ergebnis: Ergebnis, zwecke: Mapping[str, Any] | None = None) -> None:
    """Rollen, Zweck und Modell je Provider prüfen; `zwecke` überschreibt die Plattform-Tabelle (Tests)."""
    try:
        daten = lies_modellrollen(config)
        tabelle = lade_zwecktabelle() if zwecke is None else zwecke
    except AkteurFehler as fehler:
        ergebnis.fehler.append(str(fehler))
        return
    if "luecke" in daten and not isinstance(daten["luecke"], str):
        ergebnis.fehler.append("modellrollen.yaml: Feld 'luecke' muss Text sein")
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
            zweck = eintrag.get("zweck")
            zeile = tabelle.get(zweck) if isinstance(zweck, str) else None
            if not isinstance(zeile, Mapping):
                ergebnis.fehler.append(f"{praefix}: zweck {zweck!r} fehlt in plattform/zwecke.toml")
            else:
                erlaubt = zeile.get("erlaubt") or []
                for p in provider:
                    if p != "mock" and p not in erlaubt:
                        ergebnis.fehler.append(
                            f"{praefix}: Provider '{p}' ist für zweck {zweck!r} nicht erlaubt"
                        )
            for p in SPRACHMODELL_PROVIDER:
                angabe = provider.get(p)
                modell = angabe.get("modell") if isinstance(angabe, dict) else None
                if not isinstance(modell, str) or not modell.strip():
                    ergebnis.fehler.append(f"{praefix}: kein Modell für Provider '{p}'")
        elif provider:
            ergebnis.fehler.append(f"{praefix}: Rolle ohne Sprachmodell darf keine Provider nennen")
        ergebnis.rollen.append(str(name))


def pruefe_aliase(akteure: Path, config: Path, ergebnis: Ergebnis) -> None:
    """Kein Alias darf ein Themenwort sein: weder ein `themen_interesse`-Eintrag noch auf der Stoppliste."""
    themen: dict[str, str] = {}
    for pfad in sorted(akteure.glob("*.md")):
        try:
            daten, _ = lies_akteursdatei(pfad)
        except AkteurFehler:
            continue  # meldet schon pruefe_akteure
        liste = daten.get("themen_interesse")
        for thema in liste if isinstance(liste, list) else []:
            themen.setdefault(str(thema).casefold(), pfad.stem)
    for iid, aliase in lade_aliase(config).items():
        for alias in aliase:
            schluessel = alias.casefold()
            if schluessel in themen:
                ergebnis.fehler.append(
                    f"institutionen.yaml: {iid}: Alias {alias!r} ist Themenwort in {themen[schluessel]}.md"
                )
            elif schluessel in THEMENWOERTER:
                ergebnis.fehler.append(f"institutionen.yaml: {iid}: Alias {alias!r} ist ein Themenwort")


def pruefe_namen(akteure: Path, config: Path, ergebnis: Ergebnis) -> None:
    """Namens- und Parteienscan; externe Namensliste über `UC2_NAMENSLISTE` (optional)."""
    namen, hinweis = namensscan.lade_namensliste()
    if hinweis:
        ergebnis.hinweise.append(hinweis)
    dateien = [*sorted(akteure.glob("*.md")), config / "modellrollen.yaml"]
    for pfad in (p for p in dateien if p.is_file()):
        try:
            text = pfad.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as fehler:
            ergebnis.fehler.append(f"Namensscan: {pfad.name} nicht lesbar ({fehler})")
            continue
        ergebnis.fehler.extend(f"Namensscan: {t}" for t in namensscan.scanne_text(text, str(pfad), namen))


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
    try:
        pruefe_aliase(ordner, konfig, ergebnis)
    except AkteurFehler as fehler:
        ergebnis.fehler.append(str(fehler))
    pruefe_namen(ordner, konfig, ergebnis)
    return ergebnis


def pruefe_zug(zug: object) -> list[str]:
    """Fehler eines Akteurszugs gegen `zug.schema.json`; leer = gültig (für die Verhandlung, #44)."""
    return _schemafehler(jsonschema.Draft202012Validator(lade_schema("zug")), zug, "zug")
