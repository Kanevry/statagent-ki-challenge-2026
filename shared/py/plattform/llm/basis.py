"""Gemeinsame Bausteine aller Provider: Antwort, Rohantwort, Fehlerklassen und die Basisklasse."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import Any

Nachricht = dict[str, str]
ROLLEN = frozenset({"system", "user", "assistant"})


class LlmFehler(Exception):
    """Oberklasse aller Fehler des Modell-Schalters."""


class ProviderFehler(LlmFehler):
    """Kein Provider der Kette hat geantwortet (letzte Stufe gescheitert)."""


class SchemaFehler(LlmFehler):
    """Die Antwort hat das Schema auch nach genau einer Wiederholung verfehlt.

    ``kennung`` nennt nur Prüfregel und Ort (z. B. ``type $.stufe``), nie den Antwortwert: nur sie geht ins
    Protokoll. Die volle Meldung bleibt beim Aufrufer.
    """

    def __init__(self, meldung: str, kennung: str = "") -> None:
        super().__init__(meldung)
        self.kennung = kennung


class ZweckFehler(LlmFehler):
    """Der angeforderte Provider ist für diesen Zweck nicht erlaubt (z. B. claude für UC3)."""


class KonfigFehler(LlmFehler):
    """Harte Fehlkonfiguration, die kein Fallback heilen darf (z. B. ANTHROPIC_API_KEY bei claude)."""


class FixtureFehlt(LlmFehler):
    """Der mock-Provider findet keine Fixture für den Zweck."""


class VoruebergehenderFehler(LlmFehler):
    """Netz, 5xx, 429 oder Timeout: die nächste Stufe der Kette darf übernehmen."""


class SchluesselFehlt(VoruebergehenderFehler):
    """Schlüssel fehlt: auf Stufe 1 ein ``KonfigFehler`` (kein stiller Wechsel), später übersprungen."""


@dataclass(frozen=True, slots=True)
class Antwort:
    """Ergebnis von ``complete``. ``json`` ist nur bei Schema-Aufrufen belegt (validiertes dict)."""

    text: str
    json: dict[str, Any] | None
    provider: str
    modell: str
    version: str | None
    dauer_ms: int
    tokens_in: int | None
    tokens_out: int | None
    fallback_stufe: int


@dataclass(slots=True)
class Rohantwort:
    """Was ein Provider liefert; ``json`` nur, wenn der Provider selbst strukturiert antwortet."""

    text: str
    modell: str
    version: str | None
    tokens_in: int | None
    tokens_out: int | None
    json: Any = None


@dataclass(slots=True)
class Strom:
    """Gestreamte Antwort: ``teile`` liefert Text; Version und Tokens stehen nach dem Ende fest."""

    teile: Iterator[str]
    modell: str
    version: str | None = None
    tokens_in: int | None = None
    tokens_out: int | None = None
    extra: dict[str, Any] = field(default_factory=dict)


class Provider:
    """Basisklasse. Unterklassen setzen ``name`` und implementieren ``rufe`` (und optional ``strom``)."""

    name: str = ""
    #: Ergebnis ohne Laufzeitschwankung (mock): ``dauer_ms`` wird dann 0, damit Antworten byteidentisch sind.
    deterministisch: bool = False

    def standard_modell(self, groesse: str) -> str:
        raise NotImplementedError

    def rufe(
        self,
        nachrichten: list[Nachricht],
        *,
        schema: dict[str, Any] | None,
        modell: str,
        aufwand: str | None,
        zweck: str,
    ) -> Rohantwort:
        raise NotImplementedError

    def strom(
        self,
        nachrichten: list[Nachricht],
        *,
        modell: str,
        aufwand: str | None,
        zweck: str,
    ) -> Strom:
        """Standard: ganze Antwort als ein Teil (Provider ohne echtes Streaming)."""
        roh = self.rufe(nachrichten, schema=None, modell=modell, aufwand=aufwand, zweck=zweck)
        return Strom(
            teile=iter([roh.text]),
            modell=roh.modell,
            version=roh.version,
            tokens_in=roh.tokens_in,
            tokens_out=roh.tokens_out,
        )
