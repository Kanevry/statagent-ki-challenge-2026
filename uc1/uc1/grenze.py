"""Grenzprüfung des Lotsen vor und nach der Antwort, regelbasiert über daten/grenzen.yaml (Issue #31).

Deterministisch und ohne Modell: Bei einem Treffer antwortet der Kern mit dem Grenztext statt mit dem Modell.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from functools import cache
from pathlib import Path
from typing import Any, Literal

import yaml

from uc1.ingest import normalisiere

DATEN_DIR = Path(__file__).resolve().parent.parent / "daten"
GRENZEN_DATEI = DATEN_DIR / "grenzen.yaml"

Phase = Literal["vor", "nach"]


@dataclass(frozen=True)
class Grenzbefund:
    """Ergebnis einer greifenden Regel: Art (notfall, injection, medikament, ...), Phase und Grenztext."""

    art: str
    phase: Phase
    muster: str  # das Muster, das gegriffen hat (für Protokoll und Tests)
    notfall: bool

    def text(self, sprache: str = "de") -> str:
        """Antworttext: Notfall mit 144, Injection mit eigenem Text, sonst die Grenzantwort."""
        texte = _lade()["texte"]
        schluessel = self.art if self.art in ("notfall", "injection") else "grenze"
        sprachen: dict[str, str] = texte[schluessel]
        return " ".join(sprachen.get(sprache, sprachen["de"]).split())


@dataclass(frozen=True)
class _Regel:
    art: str
    muster: tuple[re.Pattern[str], ...]
    und: tuple[re.Pattern[str], ...]


def _kompiliere(liste: list[str] | None) -> tuple[re.Pattern[str], ...]:
    return tuple(re.compile(m, re.IGNORECASE) for m in (liste or []))


@cache
def _lade(pfad: Path = GRENZEN_DATEI) -> dict[str, Any]:
    daten: dict[str, Any] = yaml.safe_load(pfad.read_text(encoding="utf-8"))
    return daten


@cache
def _regeln(phase: Phase) -> tuple[_Regel, ...]:
    schluessel = "vorpruefung" if phase == "vor" else "nachpruefung"
    return tuple(
        _Regel(art=r["art"], muster=_kompiliere(r["muster"]), und=_kompiliere(r.get("und")))
        for r in _lade()[schluessel]
    )


def _pruefe(text: str, phase: Phase) -> Grenzbefund | None:
    sauber = normalisiere(text)
    for regel in _regeln(phase):
        treffer = next((m for m in regel.muster if m.search(sauber)), None)
        if treffer is None:
            continue
        if regel.und and not any(m.search(sauber) for m in regel.und):
            continue
        return Grenzbefund(art=regel.art, phase=phase, muster=treffer.pattern, notfall=regel.art == "notfall")
    return None


def vorpruefung(text: str) -> Grenzbefund | None:
    """Prüft die Frage: Notfall, Prompt-Injection, Medikament/Dosis, Befund deuten, Symptom deuten."""
    return _pruefe(text, "vor")


def nachpruefung(text: str) -> Grenzbefund | None:
    """Prüft den fertigen Antworttext: Diagnose („Sie haben eine …“), Dosierangaben, Befundbewertung."""
    return _pruefe(text, "nach")
