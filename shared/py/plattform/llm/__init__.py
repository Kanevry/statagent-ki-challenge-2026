"""Modell-Schalter (Vertrag M): ein ``complete`` für azure, mistral, ollama, claude und mock.

Nicht aus ``plattform/__init__.py`` importiert (R2): der UC3-Lauf bleibt ohne Modell und offline.
"""

from .basis import (
    Antwort,
    BudgetErschoepft,
    FixtureFehlt,
    KonfigFehler,
    LlmFehler,
    ProviderFehler,
    SchemaFehler,
    SchluesselFehlt,
    VoruebergehenderFehler,
    ZweckFehler,
)
from .kern import aktives_modell, budget_status, complete, prompt_hash

__all__ = [
    "Antwort",
    "BudgetErschoepft",
    "FixtureFehlt",
    "KonfigFehler",
    "LlmFehler",
    "ProviderFehler",
    "SchemaFehler",
    "SchluesselFehlt",
    "VoruebergehenderFehler",
    "ZweckFehler",
    "aktives_modell",
    "budget_status",
    "complete",
    "prompt_hash",
]
