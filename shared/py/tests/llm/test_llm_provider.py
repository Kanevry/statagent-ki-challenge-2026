"""Provider-Vertrag, Fallback und claude-Schutz (Vertrag M, Akzeptanz 2, 3 und 5). Kein Netz."""

import json
import os
import subprocess

import httpx
import pytest
from plattform.llm import Antwort, KonfigFehler, ZweckFehler, complete, kern, mock
from plattform.llm.azure import AzureProvider
from plattform.llm.claude import ClaudeProvider
from plattform.llm.mistral import MistralProvider
from plattform.llm.mock import MockProvider
from plattform.llm.ollama import OllamaProvider


def _http(status: int = 200, modell: str = "modell-2026-11-01") -> httpx.Client:
    def antworte(anfrage: httpx.Request) -> httpx.Response:
        if status != 200:
            return httpx.Response(status, json={"error": {"message": "nicht verfügbar"}})
        return httpx.Response(
            200,
            json={
                "id": "x",
                "object": "chat.completion",
                "created": 0,
                "model": modell,
                "choices": [
                    {
                        "index": 0,
                        "message": {"role": "assistant", "content": "bereit"},
                        "finish_reason": "stop",
                    }
                ],
                "usage": {"prompt_tokens": 7, "completion_tokens": 1, "total_tokens": 8},
            },
        )

    return httpx.Client(transport=httpx.MockTransport(antworte))


class FakeRunner:
    """Ersetzt den claude-Subprozess; merkt sich argv, stdin, cwd und den Inhalt von cwd beim Aufruf."""

    def __init__(self) -> None:
        self.aufrufe: list[tuple[list[str], str, str, list[str]]] = []

    def __call__(self, argv, eingabe, cwd, zeitlimit_s):
        self.aufrufe.append((argv, eingabe, cwd, os.listdir(cwd)))
        ausgabe = {
            "type": "result",
            "is_error": False,
            "result": "bereit",
            "structured_output": {} if "--json-schema" in argv else None,
            "usage": {"input_tokens": 5, "cache_read_input_tokens": 0, "output_tokens": 1},
            "modelUsage": {"claude-opus-5-5-20261001": {}},
        }
        return subprocess.CompletedProcess(argv, 0, stdout=json.dumps(ausgabe), stderr="")


@pytest.fixture
def umgebung(tmp_path, monkeypatch):
    protokoll = tmp_path / "modellaufrufe.jsonl"
    monkeypatch.setenv("PLATTFORM_PROTOKOLL", str(protokoll))
    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setenv("AZURE_API_KEY", "test")
    monkeypatch.setenv("AZURE_OPENAI_BASE_URL", "https://azure.test")
    monkeypatch.setenv("MISTRAL_API_KEY", "test")
    monkeypatch.setenv("MISTRAL_BASE_URL", "https://mistral.test/v1")
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://ollama.test/v1")
    monkeypatch.setattr(kern, "INSTANZEN", {})
    mock.zuruecksetzen()
    return protokoll


@pytest.mark.parametrize(
    "fabrik",
    [
        lambda: AzureProvider(http_client=_http()),
        lambda: MistralProvider(http_client=_http()),
        lambda: OllamaProvider(http_client=_http()),
        lambda: ClaudeProvider(runner=FakeRunner()),
        lambda: MockProvider(),
    ],
    ids=["azure", "mistral", "ollama", "claude", "mock"],
)
def test_provider_vertrag_antwort_felder(umgebung, fabrik):
    """Fängt: ein Provider, der ein Feld der Antwort leer lässt oder falsch typisiert."""
    instanz = fabrik()
    kern.INSTANZEN[instanz.name] = instanz

    antwort = complete([{"role": "user", "content": "bereit?"}], provider=instanz.name, zweck="smoke")

    assert isinstance(antwort, Antwort)
    assert antwort.text == "bereit"
    assert antwort.json is None
    assert antwort.provider == instanz.name
    assert isinstance(antwort.modell, str) and antwort.modell
    assert isinstance(antwort.version, str) and antwort.version
    assert isinstance(antwort.dauer_ms, int) and antwort.dauer_ms >= 0
    assert isinstance(antwort.tokens_in, int) and isinstance(antwort.tokens_out, int)
    assert antwort.fallback_stufe == 1
    assert len(umgebung.read_text(encoding="utf-8").splitlines()) == 1


def test_azure_503_faellt_auf_stufe_2(umgebung):
    """Fängt: 5xx bricht ab statt auf die nächste Stufe der Kette zu wechseln."""
    kern.INSTANZEN["azure"] = AzureProvider(http_client=_http(status=503))
    kern.INSTANZEN["mistral"] = MistralProvider(http_client=_http(modell="mistral-small-2506"))

    antwort = complete([{"role": "user", "content": "einstufen"}], zweck="qs.einstufung")

    assert (antwort.provider, antwort.fallback_stufe) == ("mistral", 2)
    zeile = json.loads(umgebung.read_text(encoding="utf-8"))
    assert (zeile["provider"], zeile["fallback_stufe"]) == ("mistral", 2)


def test_claude_mit_api_key_bricht_vor_subprozess_ab(umgebung, monkeypatch):
    """Fängt: claude läuft trotz ANTHROPIC_API_KEY (API-Abrechnung statt Abo)."""
    runner = FakeRunner()
    kern.INSTANZEN["claude"] = ClaudeProvider(runner=runner)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test")

    with pytest.raises(KonfigFehler):
        complete([{"role": "user", "content": "x"}], provider="claude", zweck="uc1.lotse")
    assert runner.aufrufe == []


def test_claude_argv_und_leeres_cwd(umgebung):
    """Fängt: fehlende Abschottung (Tools, MCP, Projekt-CLAUDE.md über cwd) oder --bare (API-Key-Pflicht)."""
    runner = FakeRunner()
    kern.INSTANZEN["claude"] = ClaudeProvider(runner=runner)

    complete(
        [{"role": "user", "content": "x"}], provider="claude", zweck="uc1.lotse", schema={"type": "object"}
    )

    argv, eingabe, cwd, inhalt = runner.aufrufe[0]
    assert argv[argv.index("--tools") + 1] == ""
    assert "--strict-mcp-config" in argv and "--json-schema" in argv
    assert "--bare" not in argv
    assert inhalt == [] and not os.path.exists(cwd)
    assert "[user]\nx" in eingabe


def test_claude_fuer_uc3_zweck_verboten(umgebung):
    """Fängt: ein UC3-Zweck lässt claude zu."""
    with pytest.raises(ZweckFehler):
        complete([{"role": "user", "content": "x"}], provider="claude", zweck="agent.koordinator")
