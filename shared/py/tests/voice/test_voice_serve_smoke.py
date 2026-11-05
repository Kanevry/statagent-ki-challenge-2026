"""``serve`` (UC4-App über den Router, ohne uvicorn-Start) und ``smoke`` (Vapi-Chat, nur MockTransport)."""

from __future__ import annotations

import json
from collections import OrderedDict

import httpx
import pytest
from fastapi.testclient import TestClient
from plattform.antwortform import Beleg, UcAntwort
from plattform.voice import kern
from plattform.voice.__main__ import main
from plattform.voice.app import erstelle_app
from plattform.voice.uc4 import OHNE_ANTWORT, als_voice_antwort, letzte_frage

SCHLUESSEL = "test-llm-schluessel"
API_KEY = "test-vapi-api-key"


@pytest.fixture
def umgebung(tmp_path, monkeypatch):
    monkeypatch.setenv("VAPI_CUSTOM_LLM_KEY", SCHLUESSEL)
    monkeypatch.setenv("VAPI_API_KEY", API_KEY)
    monkeypatch.setenv("PLATTFORM_PROTOKOLL", str(tmp_path / "modellaufrufe.jsonl"))
    monkeypatch.setenv("PLATTFORM_VOICE_PROTOKOLL", str(tmp_path / "voice.jsonl"))
    monkeypatch.delenv("PLATTFORM_ROUTER_PROTOKOLL", raising=False)
    monkeypatch.delenv("PUBLIC_URL", raising=False)
    monkeypatch.delenv("VAPI_ASSISTANT_ID", raising=False)
    monkeypatch.setattr(kern, "_SITZUNGEN", OrderedDict())
    return tmp_path


def _anfrage(frage: str) -> dict:
    return {
        "stream": False,
        "call": {"id": "anruf-uc4"},
        "messages": [
            {"role": "user", "content": "alte Frage"},
            {"role": "assistant", "content": "alte Antwort"},
            {"role": "user", "content": frage},
        ],
    }


# --- serve ------------------------------------------------------------------------------------------


def test_serve_app_uc4_mock_spricht_je_uc_einen_satz_mit_beleg(umgebung):
    client = TestClient(erstelle_app("uc4", mock=True))
    antwort = client.post(
        "/chat/completions",
        json=_anfrage("Wie viele Beschäftigte im März 2025?"),
        headers={"Authorization": f"Bearer {SCHLUESSEL}"},
    )
    assert antwort.status_code == 200
    text = antwort.json()["choices"][0]["message"]["content"]
    # Kettenreihenfolge uc3 → uc2 → uc1, je UC ein Satz mit Namen
    assert text.index("StatAgent:") < text.index("HealthPolicy Simulator:") < text.index("SV KI-Lotse:")
    assert text.endswith("Beleg: stat.beschaeftigte_monat 2025-03.")
    assert text.count("Beleg:") == 1  # gleicher Beleg aller drei UCs wird einmal gesprochen
    assert [b.quelle for b in kern.sitzungs_belege("anruf-uc4")] == ["stat.beschaeftigte_monat"]
    # die Frage ist die letzte Nutzer-Nachricht: der Router protokolliert ihren Hash
    zeilen = (umgebung / "router.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(zeilen) == 3 and "Beschäftigte" not in "".join(zeilen)


def test_serve_app_hat_tunnel_filter(umgebung, monkeypatch):
    monkeypatch.setenv("PUBLIC_URL", "https://tunnel.example.org")
    client = TestClient(erstelle_app("uc4", mock=True))
    assert client.get("/docs", headers={"Host": "tunnel.example.org"}).status_code == 404
    antwort = client.post(
        "/chat/completions",
        json=_anfrage("Frage"),
        headers={"Host": "tunnel.example.org", "Authorization": f"Bearer {SCHLUESSEL}"},
    )
    assert antwort.status_code == 200


def test_serve_app_kennt_nur_uc4():
    with pytest.raises(ValueError, match="uc4"):
        erstelle_app("uc3")


def test_serve_cli_startet_uvicorn_mit_host_und_port(umgebung, monkeypatch):
    aufrufe: list[dict] = []
    import uvicorn

    monkeypatch.setattr(uvicorn, "run", lambda app, **optionen: aufrufe.append(optionen))
    assert main(["serve", "--mock", "--port", "8199"]) == 0
    assert aufrufe == [{"host": "127.0.0.1", "port": 8199}]


def test_letzte_frage_ist_die_letzte_nutzer_nachricht():
    assert letzte_frage(_anfrage("neu")["messages"]) == "neu"
    assert letzte_frage([{"role": "system", "content": "x"}]) == ""


def test_ohne_antworten_ein_ehrlicher_satz_ohne_beleg():
    assert als_voice_antwort([]).model_dump() == {"text": OHNE_ANTWORT, "belege": []}


def test_nur_erster_satz_je_uc():
    antwort = UcAntwort(
        text="Erster Satz. Zweiter Satz.",
        belege=[Beleg(uc="uc3", quelle="q")],
        zahlen=[],
        uc="uc3",
    )
    assert als_voice_antwort([antwort]).text == "StatAgent: Erster Satz."


# --- smoke ------------------------------------------------------------------------------------------


class Mitschnitt:
    def __init__(self, status: int = 200, koerper: object | None = None) -> None:
        self.anfragen: list[httpx.Request] = []
        self.status = status
        self.koerper = koerper

    def transport(self) -> httpx.MockTransport:
        def handler(anfrage: httpx.Request) -> httpx.Response:
            self.anfragen.append(anfrage)
            return httpx.Response(self.status, json=self.koerper)

        return httpx.MockTransport(handler)


def test_smoke_post_chat_mit_bearer_und_kurzer_ausgabe(umgebung, capsys):
    lang = "StatAgent: 387.180 Beschäftigte. " + "x" * 400
    mitschnitt = Mitschnitt(
        koerper={"id": "chat-erfunden", "output": [{"role": "assistant", "content": lang}]}
    )
    assert (
        main(["smoke", "--assistant-id", "asst-1", "--frage", "Test?"], transport=mitschnitt.transport()) == 0
    )
    (anfrage,) = mitschnitt.anfragen
    assert (anfrage.method, str(anfrage.url)) == ("POST", "https://api.vapi.ai/chat")
    assert anfrage.headers["Authorization"] == f"Bearer {API_KEY}"
    assert json.loads(anfrage.content) == {"assistantId": "asst-1", "input": "Test?"}
    ausgabe = capsys.readouterr()
    assert "chat-erfunden" in ausgabe.out
    assert lang[:200] in ausgabe.out and lang[:201] not in ausgabe.out
    assert API_KEY not in ausgabe.out + ausgabe.err


def test_smoke_ohne_assistenten_nachricht_exit_1(umgebung, capsys):
    mitschnitt = Mitschnitt(koerper={"id": "c", "output": [{"role": "assistant", "content": "  "}]})
    assert main(["smoke", "--assistant-id", "a"], transport=mitschnitt.transport()) == 1
    assert "keine Assistenten-Nachricht" in capsys.readouterr().err


def test_smoke_http_fehler_exit_1_mit_status_ohne_body(umgebung, capsys):
    mitschnitt = Mitschnitt(status=401, koerper={"message": "geheimer-hinweis"})
    assert main(["smoke", "--assistant-id", "a"], transport=mitschnitt.transport()) == 1
    fehler = capsys.readouterr().err
    assert "401" in fehler and "geheimer-hinweis" not in fehler


def test_smoke_ohne_assistant_id_oder_schluessel_ohne_anfrage(umgebung, monkeypatch, capsys):
    mitschnitt = Mitschnitt(koerper={})
    assert main(["smoke"], transport=mitschnitt.transport()) == 1
    monkeypatch.delenv("VAPI_API_KEY")
    assert main(["smoke", "--assistant-id", "a"], transport=mitschnitt.transport()) == 1
    assert mitschnitt.anfragen == []
    assert "VAPI_API_KEY" in capsys.readouterr().err


@pytest.mark.parametrize("mit_antwort", [False, True], ids=["nur-budget", "teil-und-budget"])
def test_uc4_budget_mitten_in_der_kette_wird_gesagt(monkeypatch, mit_antwort):
    """Fängt (Review !38, #119): fehlend mit BudgetErschoepft verworfen, der Anrufer hört OHNE_ANTWORT."""
    from plattform import router
    from plattform.voice import uc4

    antworten = (
        [UcAntwort(text="Es waren 387.180.", belege=[], zahlen=[], uc="uc3", modell="mock")]
        if mit_antwort
        else []
    )
    ergebnis = router.Ergebnis(
        antworten=antworten, fehlend=[router.Fehlend(uc="uc2", grund="BudgetErschoepft")]
    )
    monkeypatch.setattr(uc4, "durchreichen", lambda frage, adapter=None: ergebnis)

    gesagt = uc4.uc4_antwort()([{"role": "user", "content": "Wie viele?"}], None).text
    assert gesagt.endswith(kern.BUDGET_MELDUNG)
    assert OHNE_ANTWORT not in gesagt
    assert ("387.180" in gesagt) is mit_antwort
