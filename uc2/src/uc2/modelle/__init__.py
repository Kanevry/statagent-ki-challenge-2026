"""Modellaufrufe der UC2-Rollen (Moderator, Akteur) über `plattform.llm.complete`.

Modell und Aufwand je Rolle und Provider kommen aus `uc2/config/modellrollen.yaml`; jeder Aufruf läuft mit
`zweck="uc2.panel"` (Vertrag aus #41) und schreibt so die E0-Protokollzeile. Fehler des Schalters werden auf
zwei Arten abgebildet: `UngueltigeAntwort` (der Zug zählt als `ungueltige_ausgabe`, der Lauf geht weiter)
und `ModellKonfigFehler` (Fehlkonfiguration, der Lauf bricht ab).
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

# plattform hat keinen py.typed-Marker (Wurzel-Workspace, E0); die Typen fängt dieser Adapter ab.
from plattform.llm import (  # type: ignore[import-untyped]
    KonfigFehler,
    LlmFehler,
    SchemaFehler,
    ZweckFehler,
    complete,
)

from uc2.akteure.laden import lade_modellrollen, lies_modellrollen

ROLLEN = ("moderator", "akteur")
PROVIDER = ("mock", "claude", "azure", "mistral", "ollama")


class ModellKonfigFehler(RuntimeError):
    """Fehlkonfiguration, die kein Wiederholen heilt (Schlüssel, Zweck, ANTHROPIC_API_KEY bei claude)."""


class UngueltigeAntwort(RuntimeError):
    """Die Antwort ist nach der Wiederholung im Schalter ungültig oder kein Provider hat geantwortet.

    `kennung` nennt nur Prüfregel und Ort (aus `SchemaFehler.kennung`) oder den Fehlertyp, nie Modelltext.
    """

    def __init__(self, meldung: str, kennung: str) -> None:
        super().__init__(meldung)
        self.kennung = kennung


@dataclass(frozen=True)
class Rollenmodell:
    """Modellwahl einer Rolle für einen Provider (Stufe 1 der Fallback-Kette)."""

    rolle: str
    provider: str
    modell: str
    aufwand: str | None
    zweck: str


@dataclass(frozen=True)
class Modellantwort:
    """Validierte JSON-Antwort und wer tatsächlich geantwortet hat."""

    json: dict[str, Any]
    text: str
    provider: str
    modell: str
    fallback_stufe: int


def waehle_provider(argument: str | None, config: Path | None = None) -> str:
    """Provider: Argument > `LLM_PROVIDER` > `standard_provider` aus `modellrollen.yaml`."""
    wahl = argument or os.environ.get("LLM_PROVIDER", "").strip()
    if not wahl:
        wahl = str(lies_modellrollen(config).get("standard_provider") or "azure")
    if wahl not in PROVIDER:
        raise ModellKonfigFehler(f"unbekannter Provider {wahl!r} (erlaubt: {', '.join(PROVIDER)})")
    return wahl


def rollenmodell(rolle: str, provider: str, config: Path | None = None) -> Rollenmodell:
    """Modell und Aufwand der Rolle für den Provider aus `modellrollen.yaml`."""
    rollen = lade_modellrollen(config)
    eintrag = rollen.get(rolle)
    if eintrag is None or not eintrag.sprachmodell or eintrag.zweck is None:
        raise ModellKonfigFehler(f"modellrollen.yaml: Rolle {rolle!r} ist keine Sprachmodell-Rolle")
    angabe = eintrag.provider.get(provider)
    if angabe is None:
        raise ModellKonfigFehler(f"modellrollen.yaml: Rolle {rolle!r} nennt kein Modell für {provider!r}")
    return Rollenmodell(
        rolle=rolle,
        provider=provider,
        modell=angabe.aufgeloest(),
        aufwand=angabe.aufwand,
        zweck=eintrag.zweck,
    )


def rufe(rm: Rollenmodell, nachrichten: list[dict[str, str]], schema: dict[str, Any]) -> Modellantwort:
    """Ein Modellaufruf mit JSON-Schema; Wiederholung bei Schemaverstoß macht `complete` selbst."""
    try:
        antwort = complete(
            nachrichten,
            schema=schema,
            provider=rm.provider,
            zweck=rm.zweck,
            modell=rm.modell,
            aufwand=rm.aufwand,
        )
    except (KonfigFehler, ZweckFehler) as fehler:
        raise ModellKonfigFehler(f"{type(fehler).__name__}: {fehler}") from fehler
    except SchemaFehler as fehler:
        raise UngueltigeAntwort(str(fehler), f"SchemaFehler: {fehler.kennung}") from fehler
    except LlmFehler as fehler:
        raise UngueltigeAntwort(str(fehler), type(fehler).__name__) from fehler
    daten = antwort.json
    if not isinstance(daten, dict):
        raise UngueltigeAntwort("Antwort ohne JSON-Objekt", "json $")
    return Modellantwort(
        json=daten,
        text=str(antwort.text),
        provider=str(antwort.provider),
        modell=str(antwort.modell),
        fallback_stufe=int(antwort.fallback_stufe),
    )
