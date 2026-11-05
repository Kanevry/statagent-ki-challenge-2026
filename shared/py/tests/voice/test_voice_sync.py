"""``python -m plattform.voice sync``: Konfiguration als Code, Vapi-API nur über httpx.MockTransport."""

from __future__ import annotations

import json

import httpx
import pytest
from plattform.voice.__main__ import main
from plattform.voice.assistant import assistant_konfiguration

API_KEY = "test-vapi-api-key"
SECRET = "test-webhook-secret"
LLM_KEY = "test-llm-schluessel"


@pytest.fixture
def umgebung(monkeypatch):
    monkeypatch.setenv("PUBLIC_URL", "https://tunnel.example.org/")
    monkeypatch.setenv("VAPI_API_KEY", API_KEY)
    monkeypatch.setenv("VAPI_WEBHOOK_SECRET", SECRET)
    monkeypatch.setenv("VAPI_CUSTOM_LLM_KEY", LLM_KEY)
    monkeypatch.delenv("VAPI_ASSISTANT_ID", raising=False)


class Mitschnitt:
    def __init__(self, status: int = 200) -> None:
        self.anfragen: list[httpx.Request] = []
        self.status = status

    def transport(self) -> httpx.MockTransport:
        def handler(anfrage: httpx.Request) -> httpx.Response:
            self.anfragen.append(anfrage)
            return httpx.Response(self.status, json={"id": "asst-erfunden", "server": {"secret": SECRET}})

        return httpx.MockTransport(handler)


def test_trocken_druckt_json_ohne_schluessel(umgebung, capsys):
    assert main(["sync", "--trocken"]) == 0
    ausgabe = capsys.readouterr().out
    konfiguration = json.loads(ausgabe)
    assert konfiguration["model"]["url"] == "https://tunnel.example.org"  # Vapi hängt /chat/completions an
    for wert in (API_KEY, SECRET, LLM_KEY):
        assert wert not in ausgabe


def test_konfiguration_deutsch_ohne_aufnahme():
    konfiguration = assistant_konfiguration("https://tunnel.example.org")
    assert konfiguration["transcriber"]["language"] == "de"
    assert konfiguration["recordingEnabled"] is False
    assert konfiguration["artifactPlan"]["recordingEnabled"] is False
    # Geld (Review !66): kein Anruf ohne Obergrenze, auch wenn niemand auflegt
    assert konfiguration["maxDurationSeconds"] == 120
    assert konfiguration["model"]["provider"] == "custom-llm"
    assert konfiguration["server"]["url"] == "https://tunnel.example.org/vapi/webhook"


@pytest.mark.parametrize("trocken", [True, False])
def test_ohne_public_url_klarer_abbruch(umgebung, monkeypatch, capsys, trocken):
    monkeypatch.delenv("PUBLIC_URL")
    mitschnitt = Mitschnitt()
    argv = ["sync", "--trocken"] if trocken else ["sync"]
    assert main(argv, transport=mitschnitt.transport()) == 2
    assert "PUBLIC_URL ist nicht gesetzt" in capsys.readouterr().err
    assert mitschnitt.anfragen == []


def test_sync_ohne_id_post_mit_bearer_und_url_aus_public_url(umgebung, capsys):
    mitschnitt = Mitschnitt()
    assert main(["sync"], transport=mitschnitt.transport()) == 0
    (anfrage,) = mitschnitt.anfragen
    assert (anfrage.method, str(anfrage.url)) == ("POST", "https://api.vapi.ai/assistant")
    assert anfrage.headers["Authorization"] == f"Bearer {API_KEY}"
    body = json.loads(anfrage.content)
    assert body["model"]["url"] == "https://tunnel.example.org"
    assert body["server"]["secret"] == SECRET
    ausgabe = capsys.readouterr()
    assert "asst-erfunden" in ausgabe.out
    assert API_KEY not in ausgabe.out + ausgabe.err and SECRET not in ausgabe.out + ausgabe.err


def test_sync_mit_id_patch(umgebung, monkeypatch):
    monkeypatch.setenv("VAPI_ASSISTANT_ID", "aus-umgebung")
    mitschnitt = Mitschnitt()
    assert main(["sync", "--assistant-id", "asst-1"], transport=mitschnitt.transport()) == 0
    (anfrage,) = mitschnitt.anfragen
    assert (anfrage.method, anfrage.url.path) == ("PATCH", "/assistant/asst-1")


def test_sync_ohne_api_key_abbruch_ohne_anfrage(umgebung, monkeypatch, capsys):
    monkeypatch.delenv("VAPI_API_KEY")
    mitschnitt = Mitschnitt()
    assert main(["sync"], transport=mitschnitt.transport()) == 2
    assert "VAPI_API_KEY" in capsys.readouterr().err
    assert mitschnitt.anfragen == []


def test_sync_api_fehler_ohne_body_in_der_meldung(umgebung, capsys):
    mitschnitt = Mitschnitt(status=400)
    assert main(["sync"], transport=mitschnitt.transport()) == 2
    fehler = capsys.readouterr().err
    assert "400" in fehler and SECRET not in fehler


def test_zahlen_spricht_die_deutsche_stimme_nicht_vapis_englische_formatierung():
    """Fängt: Vapis formatPlan schrieb „2025“ als „twentyfive“ aus (Web-Anruf 05.11.)."""
    from plattform.voice.assistant import assistant_konfiguration

    stimme = assistant_konfiguration("https://beispiel.example.org")["voice"]
    assert stimme["provider"] == "azure" and stimme["voiceId"].startswith("de-")
    assert stimme["chunkPlan"]["formatPlan"]["enabled"] is False
