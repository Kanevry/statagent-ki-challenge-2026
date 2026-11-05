"""ollama (Offline-Notnagel auf einem lokalen Rechner): OpenAI-kompatibler Endpunkt ohne Schlüssel."""

from __future__ import annotations

import os

from .openai_basis import OpenAiKompatibel


class OllamaProvider(OpenAiKompatibel):
    name = "ollama"
    schluessel_var = None

    def basis_url(self) -> str:
        return (os.environ.get("OLLAMA_BASE_URL") or "http://localhost:11434/v1").rstrip("/")

    def standard_modell(self, groesse: str) -> str:
        return os.environ.get("OLLAMA_MODEL") or "qwen3:8b"
