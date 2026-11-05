"""Zweck-Routing aus ``plattform/zwecke.toml``: Provider-Vorzug, Modellgröße, Fallback-Kette, Erlaubnis."""

from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass
from functools import cache
from pathlib import Path

from .basis import ZweckFehler

TABELLE = Path(__file__).resolve().parent.parent / "zwecke.toml"
PROVIDER = ("azure", "mistral", "ollama", "claude", "mock")


@dataclass(frozen=True, slots=True)
class Zweck:
    name: str
    vorzug: str
    groesse: str
    kette: tuple[str, ...]
    erlaubt: frozenset[str]


@cache
def _tabelle(pfad: Path = TABELLE) -> dict[str, dict]:
    with pfad.open("rb") as datei:
        return tomllib.load(datei)


def zweck(name: str) -> Zweck:
    tabelle = _tabelle()
    eintrag = tabelle.get(name) or tabelle["standard"]
    return Zweck(
        name=name,
        vorzug=eintrag["vorzug"],
        groesse=eintrag.get("groesse", "fast"),
        kette=tuple(eintrag["kette"]),
        erlaubt=frozenset(eintrag["erlaubt"]) | {"mock"},
    )


def waehle(name: str, provider: str | None) -> tuple[str, str]:
    """Erster Provider und Quelle (``argument``, ``env`` oder ``zweck``)."""
    if provider:
        return provider, "argument"
    umgebung = os.environ.get("LLM_PROVIDER", "").strip()
    if umgebung:
        return umgebung, "env"
    return zweck(name).vorzug, "zweck"


def kette(name: str, provider: str | None) -> tuple[list[str], str]:
    """Fallback-Kette für einen Aufruf; prüft Bekanntheit und Erlaubnis des ersten Providers."""
    eintrag = zweck(name)
    erster, quelle = waehle(name, provider)
    if erster not in PROVIDER:
        raise ZweckFehler(f"unbekannter Provider {erster!r} (erlaubt: {', '.join(PROVIDER)})")
    if erster not in eintrag.erlaubt:
        raise ZweckFehler(
            f"Provider {erster!r} ist für Zweck {name or 'standard'!r} nicht erlaubt "
            f"(erlaubt: {', '.join(sorted(eintrag.erlaubt))})"
        )
    if erster == "mock":
        return ["mock"], quelle
    rest = [p for p in eintrag.kette if p != erster and p in eintrag.erlaubt]
    return [erster, *rest], quelle
