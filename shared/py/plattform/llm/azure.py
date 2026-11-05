"""azure (Standard, Pflicht für UC3-Agenten): OpenAI-kompatibler Endpunkt ``/openai/v1`` (we-16)."""

from __future__ import annotations

import os
from typing import Any

from .basis import VoruebergehenderFehler
from .openai_basis import OpenAiKompatibel

#: ``aufwand`` des Vertrags → ``reasoning_effort`` der Chat-Completions-API.
AUFWAND = {"hoch": "high", "niedrig": "low"}


class AzureProvider(OpenAiKompatibel):
    name = "azure"
    schluessel_var = "AZURE_API_KEY"

    def basis_url(self) -> str:
        url = os.environ.get("AZURE_OPENAI_BASE_URL", "").rstrip("/")
        if not url:
            raise VoruebergehenderFehler("azure: AZURE_OPENAI_BASE_URL nicht belegt")
        return url if url.endswith("/openai/v1") else url + "/openai/v1"

    def standard_modell(self, groesse: str) -> str:
        return os.environ.get("AZURE_OPENAI_MODEL") or "gpt-5-4-mini"

    def zusatz(self, aufwand: str | None) -> dict[str, Any]:
        return {"reasoning_effort": AUFWAND[aufwand]} if aufwand else {}
