"""OpenAI-kompatible Chat Completions (azure, mistral, ollama) über das openai-SDK.

``http_client`` ist injizierbar (Tests mit ``httpx.MockTransport``, kein Netz). Das SDK wiederholt nicht
selbst (``max_retries=0``): Wiederholen ist Sache der Fallback-Kette.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from typing import Any, cast

import httpx
import openai
from openai.types.chat import ChatCompletionChunk

from .basis import Nachricht, Provider, Rohantwort, Strom, VoruebergehenderFehler

ZEITLIMIT_S = 60.0


def _voruebergehend(fehler: Exception) -> bool:
    if isinstance(fehler, openai.APIConnectionError | openai.APITimeoutError):
        return True
    # 429 zählt mit: ein gedrosselter Endpunkt soll vor der Jury auf die nächste Stufe wechseln.
    return isinstance(fehler, openai.APIStatusError) and (
        fehler.status_code >= 500 or fehler.status_code == 429
    )


class OpenAiKompatibel(Provider):
    """Gemeinsame Logik; Unterklassen liefern Basis-URL, Schlüssel und Standardmodell."""

    #: Umgebungsvariable des Schlüssels; ``None`` = kein Schlüssel nötig (ollama).
    schluessel_var: str | None = None
    #: ``stream_options.include_usage`` mitschicken (Tokens beim Streaming).
    strom_mit_usage: bool = True

    def __init__(self, http_client: httpx.Client | None = None) -> None:
        # Das SDK typisiert seinen eigenen httpx-Client; zur Laufzeit nimmt es den injizierten Client an.
        self._http_client: Any = http_client

    def basis_url(self) -> str:
        raise NotImplementedError

    def schluessel(self) -> str:
        if self.schluessel_var is None:
            return "nicht-noetig"
        wert = os.environ.get(self.schluessel_var, "")
        if not wert:
            raise VoruebergehenderFehler(f"{self.name}: {self.schluessel_var} nicht belegt")
        return wert

    def zusatz(self, aufwand: str | None) -> dict[str, Any]:
        """Provider-spezifische Parameter (azure: ``reasoning_effort``)."""
        return {}

    def _client(self) -> openai.OpenAI:
        return openai.OpenAI(
            base_url=self.basis_url(),
            api_key=self.schluessel(),
            http_client=self._http_client,
            max_retries=0,
            timeout=ZEITLIMIT_S,
        )

    def rufe(
        self,
        nachrichten: list[Nachricht],
        *,
        schema: dict[str, Any] | None,
        modell: str,
        aufwand: str | None,
        zweck: str,
    ) -> Rohantwort:
        parameter: dict[str, Any] = dict(self.zusatz(aufwand))
        if schema is not None:
            parameter["response_format"] = {
                "type": "json_schema",
                "json_schema": {"name": "antwort", "schema": schema},
            }
        try:
            antwort = self._client().chat.completions.create(
                model=modell,
                messages=nachrichten,  # type: ignore[arg-type]
                **parameter,
            )
        except Exception as fehler:
            if _voruebergehend(fehler):
                raise VoruebergehenderFehler(f"{self.name}: {type(fehler).__name__}") from fehler
            raise
        usage = antwort.usage
        return Rohantwort(
            text=(antwort.choices[0].message.content or "") if antwort.choices else "",
            modell=modell,
            version=antwort.model or None,
            tokens_in=usage.prompt_tokens if usage else None,
            tokens_out=usage.completion_tokens if usage else None,
        )

    def strom(
        self,
        nachrichten: list[Nachricht],
        *,
        modell: str,
        aufwand: str | None,
        zweck: str,
    ) -> Strom:
        parameter: dict[str, Any] = dict(self.zusatz(aufwand))
        if self.strom_mit_usage:
            parameter["stream_options"] = {"include_usage": True}
        try:
            roh = self._client().chat.completions.create(
                model=modell,
                messages=nachrichten,  # type: ignore[arg-type]
                stream=True,
                **parameter,
            )
        except Exception as fehler:
            if _voruebergehend(fehler):
                raise VoruebergehenderFehler(f"{self.name}: {type(fehler).__name__}") from fehler
            raise
        ergebnis = Strom(teile=iter(()), modell=modell)

        def teile() -> Iterator[str]:
            for stueck in cast("Iterator[ChatCompletionChunk]", roh):
                if stueck.model:
                    ergebnis.version = stueck.model
                if stueck.usage:
                    ergebnis.tokens_in = stueck.usage.prompt_tokens
                    ergebnis.tokens_out = stueck.usage.completion_tokens
                for wahl in stueck.choices:
                    if wahl.delta and wahl.delta.content:
                        yield wahl.delta.content

        ergebnis.teile = teile()
        return ergebnis
