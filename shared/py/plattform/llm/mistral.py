"""mistral (EU, Zweitanbieter): Small für Klassifizieren/Extrahieren (``fast``), Large nur für Texte."""

from __future__ import annotations

import os

from .openai_basis import OpenAiKompatibel


class MistralProvider(OpenAiKompatibel):
    name = "mistral"
    schluessel_var = "MISTRAL_API_KEY"
    strom_mit_usage = False

    def basis_url(self) -> str:
        return (os.environ.get("MISTRAL_BASE_URL") or "https://api.mistral.ai/v1").rstrip("/")

    def standard_modell(self, groesse: str) -> str:
        if groesse == "chat":
            return os.environ.get("MISTRAL_MODEL_CHAT") or "mistral-large-latest"
        return os.environ.get("MISTRAL_MODEL_FAST") or "mistral-small-latest"
