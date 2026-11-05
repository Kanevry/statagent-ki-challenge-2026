"""Vapi-Assistant als Code (Vertrag V) und ``sync`` gegen die Vapi-API.

Die Konfiguration trägt keine Schlüssel. Erst ``synchronisiere`` setzt ``server.secret`` aus
``VAPI_WEBHOOK_SECRET`` (Vapi schickt ihn als ``x-vapi-secret`` an den Webhook) und authentifiziert sich mit
``VAPI_API_KEY``. Ohne ``assistant_id`` legt ``sync`` einen neuen Assistant an (POST), sonst PATCH.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass
from typing import Any

import httpx

VAPI_API = "https://api.vapi.ai"
ASSISTANT_NAME = "OneShotAndy StatAgent"
#: Kurz, ohne Versprechen: die Antwort kommt erst aus der Datenbank.
BEGRUESSUNG = "Hallo, hier ist der StatAgent. Was möchten Sie zur Beschäftigtenstatistik wissen?"
SYSTEM_PROMPT = (
    "Du bist der Sprachzugang zum StatAgent. Antworte auf Deutsch, kurz und sachlich. "
    "Nenne nur Zahlen, die dir das System liefert, immer mit ihrem Beleg."
)


class SyncFehler(RuntimeError):
    """Konfiguration unvollständig oder Vapi-API lehnte ab; die Meldung nennt nie einen Wert."""


def basis_url(public_url: str | None) -> str:
    """``PUBLIC_URL`` ohne abschließenden Schrägstrich; ohne gültige http(s)-Adresse ``SyncFehler``."""
    adresse = (public_url or "").strip().rstrip("/")
    if not adresse:
        raise SyncFehler("PUBLIC_URL ist nicht gesetzt: zuerst den Tunnel starten und PUBLIC_URL eintragen")
    if not adresse.startswith(("https://", "http://")):
        raise SyncFehler("PUBLIC_URL muss mit https:// (lokal http://) beginnen")
    return adresse


def assistant_konfiguration(public_url: str | None) -> dict[str, Any]:
    """Assistant-Body ohne Schlüssel: Deutsch, Aufnahme aus, Custom LLM auf ``PUBLIC_URL``."""
    basis = basis_url(public_url)
    return {
        "name": ASSISTANT_NAME,
        "firstMessage": BEGRUESSUNG,
        "firstMessageMode": "assistant-speaks-first",
        "model": {
            "provider": "custom-llm",
            # Basis-URL: Vapi hängt /chat/completions selbst an (docs.vapi.ai, Custom LLM, Schritt 2)
            "url": basis,
            "model": "plattform-voice",
            "messages": [{"role": "system", "content": SYSTEM_PROMPT}],
        },
        "transcriber": {"provider": "deepgram", "model": "nova-2", "language": "de"},
        # formatPlan aus: Vapi schreibt Zahlen sonst nach englischen Regeln aus („2025“ → „twentyfive“,
        # gemessen im Web-Anruf 05.11.); die deutsche Azure-Stimme spricht Zahlen selbst richtig.
        "voice": {
            "provider": "azure",
            "voiceId": "de-AT-IngridNeural",
            "chunkPlan": {"enabled": True, "formatPlan": {"enabled": False}},
        },
        "recordingEnabled": False,
        "artifactPlan": {"recordingEnabled": False},
        "server": {"url": f"{basis}/vapi/webhook"},
        "serverMessages": ["end-of-call-report"],
    }


def synchronisiere(
    konfiguration: dict[str, Any],
    *,
    api_key: str | None,
    webhook_secret: str | None,
    assistant_id: str | None = None,
    transport: httpx.BaseTransport | None = None,
) -> str:
    """Schreibt Assistant (PATCH mit ID, sonst POST), gibt seine ID zurück. Außenwirkung: nur mit Freigabe."""
    if not api_key:
        raise SyncFehler("VAPI_API_KEY ist nicht gesetzt")
    if not webhook_secret:
        raise SyncFehler(
            "VAPI_WEBHOOK_SECRET ist nicht gesetzt: der Webhook würde jede Meldung mit 401 ablehnen"
        )
    body = copy.deepcopy(konfiguration)
    body["server"]["secret"] = webhook_secret
    with httpx.Client(
        base_url=VAPI_API,
        transport=transport,
        timeout=20.0,
        headers={"Authorization": f"Bearer {api_key}"},
    ) as client:
        if assistant_id:
            antwort = client.patch(f"/assistant/{assistant_id}", json=body)
        else:
            antwort = client.post("/assistant", json=body)
    if antwort.is_error:
        # Den Body nicht ausgeben: er kann die Konfiguration samt Secret spiegeln.
        raise SyncFehler(f"Vapi-API antwortete {antwort.status_code}")
    kennung = antwort.json().get("id") if antwort.content else None
    return str(kennung or assistant_id or "")


SMOKE_FRAGE = "Wie viele Beschäftigte gab es im März 2025?"


@dataclass(frozen=True, slots=True)
class SmokeErgebnis:
    """Ergebnis von ``smoke``: Chat-ID und der Anfang der Antwort (höchstens 200 Zeichen)."""

    chat_id: str
    antwort: str


def smoke(
    *,
    api_key: str | None,
    assistant_id: str,
    frage: str = SMOKE_FRAGE,
    transport: httpx.BaseTransport | None = None,
) -> SmokeErgebnis:
    """Eine Textfrage über ``POST /chat`` der Vapi-API an den Assistant (Außenwirkung: nur mit Freigabe)."""
    if not api_key:
        raise SyncFehler("VAPI_API_KEY ist nicht gesetzt")
    with httpx.Client(
        base_url=VAPI_API,
        transport=transport,
        timeout=30.0,
        headers={"Authorization": f"Bearer {api_key}"},
    ) as client:
        antwort = client.post("/chat", json={"assistantId": assistant_id, "input": frage})
    if antwort.is_error:
        raise SyncFehler(f"Vapi-API antwortete {antwort.status_code}")
    try:
        koerper = antwort.json()
    except ValueError as fehler:
        raise SyncFehler("Vapi-API lieferte kein JSON") from fehler
    ausgabe = koerper.get("output") if isinstance(koerper, dict) else None
    texte = [
        str(n["content"]).strip()
        for n in (ausgabe if isinstance(ausgabe, list) else [])
        if isinstance(n, dict) and n.get("role") == "assistant" and str(n.get("content") or "").strip()
    ]
    if not texte:
        raise SyncFehler("Vapi-Antwort enthält keine Assistenten-Nachricht")
    return SmokeErgebnis(chat_id=str(koerper.get("id", "")), antwort=" ".join(texte)[:200])
