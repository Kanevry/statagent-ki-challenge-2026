"""Abnahme #63 (EA-1): Warum antwortet mistral mit HTTP 429?

Aufruf: ``uv run --package plattform python tests/abnahme/63_mistral_diagnose.py``

Misst nur lesend: ``GET /models`` (zeigt, ob der Schlüssel gilt) und die Ratenlimit-Kopfzeilen einer
einzigen sehr kurzen Anfrage. Gibt Statuscodes, Kopfzeilen ``x-ratelimit-*`` und den Fehlertyp aus,
nie den Schlüssel und nie einen Antworttext.
"""

from __future__ import annotations

import json
import os

import httpx
from plattform.umgebung import lade_env_local


def _limits(antwort: httpx.Response) -> dict[str, str]:
    return {
        k: v
        for k, v in antwort.headers.items()
        if k.lower().startswith(("x-ratelimit", "ratelimit", "retry-after"))
    }


def _fehlertyp(antwort: httpx.Response) -> str | None:
    try:
        daten = antwort.json()
    except ValueError:
        return None
    if isinstance(daten, dict):
        for feld in ("type", "code", "object"):
            if isinstance(daten.get(feld), str):
                return str(daten[feld])
    return None


def main() -> int:
    lade_env_local()
    basis = os.environ.get("MISTRAL_BASE_URL", "https://api.mistral.ai/v1").rstrip("/")
    schluessel = os.environ.get("MISTRAL_API_KEY", "")
    kopf = {"Authorization": f"Bearer {schluessel}"}
    ergebnis: dict[str, object] = {"schluessel_vorhanden": bool(schluessel)}
    with httpx.Client(timeout=20) as client:
        modelle = client.get(f"{basis}/models", headers=kopf)
        ergebnis["models_status"] = modelle.status_code
        if modelle.status_code == 200:
            ids = [m.get("id") for m in modelle.json().get("data", []) if isinstance(m, dict)]
            ergebnis["models_anzahl"] = len(ids)
            ergebnis["small_latest_da"] = "mistral-small-latest" in ids
        chat = client.post(
            f"{basis}/chat/completions",
            headers=kopf,
            json={
                "model": "mistral-small-latest",
                "messages": [{"role": "user", "content": "1"}],
                "max_tokens": 1,
            },
        )
        ergebnis["chat_status"] = chat.status_code
        ergebnis["chat_limits"] = _limits(chat)
        ergebnis["chat_fehlertyp"] = _fehlertyp(chat) if chat.status_code >= 400 else None
    print(json.dumps(ergebnis, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
