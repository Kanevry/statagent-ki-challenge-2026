"""Modell-Schalter (Vertrag M): ein ``complete`` für azure, mistral, ollama, claude und mock.

Nicht aus ``plattform/__init__.py`` importiert (R2): der UC3-Lauf bleibt ohne Modell und offline.
"""

from .basis import (
    Antwort,
    FixtureFehlt,
    KonfigFehler,
    LlmFehler,
    ProviderFehler,
    SchemaFehler,
    ZweckFehler,
)
from .kern import aktives_modell, complete, prompt_hash

__all__ = [
    "Antwort",
    "FixtureFehlt",
    "KonfigFehler",
    "LlmFehler",
    "ProviderFehler",
    "SchemaFehler",
    "ZweckFehler",
    "aktives_modell",
    "complete",
    "prompt_hash",
]
