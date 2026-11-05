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
        """Antworttext der Art (notfall, medikament, injection), sonst die allgemeine Grenzantwort."""
        texte = _lade()["texte"]
        sprachen: dict[str, str] = texte.get(self.art) or texte["grenze"]
        return " ".join(sprachen.get(sprache, sprachen["de"]).split())

    def uebergabe_an(self) -> str:
        """Übergabeziel der Art aus ``verweise`` (Medikament mit Apotheke), sonst das allgemeine Ziel."""
        verweise: dict[str, str] = _lade()["verweise"]
        return verweise.get(self.art) or verweise["grenze"]


@dataclass(frozen=True)
class _Regel:
    art: str
    muster: tuple[re.Pattern[str], ...]
    und: tuple[re.Pattern[str], ...]
    ausser_sv: bool = False


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
        _Regel(
            art=r["art"],
            muster=_kompiliere(r["muster"]),
            und=_kompiliere(r.get("und")),
            ausser_sv=bool(r.get("ausser_sv")),
        )
        for r in _lade()[schluessel]
    )


@cache
def _sv_bezug() -> tuple[re.Pattern[str], ...]:
    return _kompiliere(_lade().get("sv_bezug"))


def sv_bezug(text: str) -> bool:
    """Hat die Frage einen Sozialversicherungsbezug (Kosten, Kasse, Antrag, Anspruch, Geldleistung)?"""
    sauber = normalisiere(text)
    return any(m.search(sauber) for m in _sv_bezug())


def _pruefe(text: str, phase: Phase) -> Grenzbefund | None:
    sauber = normalisiere(text)
    for regel in _regeln(phase):
        treffer = next((m for m in regel.muster if m.search(sauber)), None)
        if treffer is None:
            continue
        if regel.und and not any(m.search(sauber) for m in regel.und):
            continue
        if regel.ausser_sv and any(m.search(sauber) for m in _sv_bezug()):
            continue
        return Grenzbefund(art=regel.art, phase=phase, muster=treffer.pattern, notfall=regel.art == "notfall")
    return None


def vorpruefung(text: str) -> Grenzbefund | None:
    """Prüft die Frage: Notfall, Prompt-Injection, Medikament/Dosis, Befund deuten, Symptom deuten."""
    return _pruefe(text, "vor")


def nachpruefung(text: str) -> Grenzbefund | None:
    """Prüft den fertigen Antworttext: Diagnose („Sie haben eine …“), Dosierangaben, Befundbewertung."""
    return _pruefe(text, "nach")


def medizinisch(text: str) -> Grenzbefund | None:
    """Medizinische Frage ohne Sozialversicherungsbezug: ein ``muster`` der Arten unter ``medizinisch`` passt
    (ohne ``und``), aber kein ``sv_bezug``. Der Kern nutzt das nur, wenn er keine Leistung erkannt hat; dann
    übergibt er an Ärztin, Arzt oder 1450, statt aus Gesetzestexten zu antworten (Held-out #39, #155)."""
    sauber = normalisiere(text)
    if any(m.search(sauber) for m in _sv_bezug()):
        return None
    arten = set(_lade().get("medizinisch", {}).get("arten") or [])
    for regel in _regeln("vor"):
        if regel.art not in arten:
            continue
        treffer = next((m for m in regel.muster if m.search(sauber)), None)
        if treffer is not None:
            return Grenzbefund(art="medizinisch", phase="vor", muster=treffer.pattern, notfall=False)
    return None
