"""Fall-Definitionen aus `uc2/faelle/<id>.yaml`; die CLI nimmt nur IDs, nie Pfade."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

import yaml

from uc2 import pfade

FAELLE = pfade.UC2_WURZEL / "faelle"
FALL_ID = re.compile(r"^[a-z][a-z0-9_-]{0,63}$")
SCHLUESSEL = frozenset({"id", "version", "frage", "stichtag", "paket", "max_akteure", "max_runden"})


class FallFehler(ValueError):
    """Unbekannte Fall-ID oder ungültige Fall-Datei."""


@dataclass(frozen=True)
class Falldefinition:
    id: str
    frage: str
    stichtag: date
    paket: Path
    max_akteure: int
    max_runden: int


def bekannte_faelle(ordner: Path | None = None) -> list[str]:
    return sorted(p.stem for p in (ordner or FAELLE).glob("*.yaml") if FALL_ID.fullmatch(p.stem))


def lade_fall(fall_id: str, ordner: Path | None = None) -> Falldefinition:
    """Fall laden; die ID muss dem Muster folgen und als Datei im Fall-Ordner liegen."""
    ordner = ordner or FAELLE
    bekannt = bekannte_faelle(ordner)
    if not FALL_ID.fullmatch(fall_id) or fall_id not in bekannt:
        raise FallFehler(f"unbekannter Fall {fall_id!r} (bekannt: {', '.join(bekannt) or 'keine'})")
    pfad = ordner / f"{fall_id}.yaml"
    roh: Any = yaml.safe_load(pfad.read_text(encoding="utf-8"))
    if not isinstance(roh, dict):
        raise FallFehler(f"{pfad.name}: keine Zuordnung")
    fremd = set(roh) - SCHLUESSEL
    if fremd:
        raise FallFehler(f"{pfad.name}: unbekannte Schlüssel {sorted(fremd)}")
    if roh.get("id") != fall_id:
        raise FallFehler(f"{pfad.name}: id muss {fall_id!r} sein")
    frage = " ".join(str(roh.get("frage") or "").split())
    if not frage:
        raise FallFehler(f"{pfad.name}: frage fehlt")
    stichtag = roh.get("stichtag")
    if not isinstance(stichtag, date):
        stichtag = date.fromisoformat(str(stichtag))
    pakete = (pfade.UC2_WURZEL / "pakete").resolve()
    paket = (pfade.UC2_WURZEL / str(roh.get("paket") or "")).resolve()
    if paket.parent != pakete or paket.suffix != ".yaml" or not paket.is_file():
        raise FallFehler(f"{pfad.name}: paket muss eine Datei in uc2/pakete/ sein")
    max_akteure = int(roh.get("max_akteure", 6))
    max_runden = int(roh.get("max_runden", 5))
    if not 1 <= max_akteure <= 6:
        raise FallFehler(f"{pfad.name}: max_akteure muss zwischen 1 und 6 liegen")
    if not 1 <= max_runden <= 5:
        raise FallFehler(f"{pfad.name}: max_runden muss zwischen 1 und 5 liegen")
    return Falldefinition(
        id=fall_id,
        frage=frage,
        stichtag=stichtag,
        paket=paket,
        max_akteure=max_akteure,
        max_runden=max_runden,
    )
