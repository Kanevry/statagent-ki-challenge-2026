"""Review !7: kein Inhalt im Protokoll, harter Schlüsselfehler, Modell je Stufe, Streaming."""

import json

import httpx
import pytest
from plattform.llm import KonfigFehler, SchemaFehler, VoruebergehenderFehler, complete, kern, mock
from plattform.llm.azure import AzureProvider
from plattform.llm.mistral import MistralProvider


@pytest.fixture
def protokoll(tmp_path, monkeypatch):
    datei = tmp_path / "modellaufrufe.jsonl"
    monkeypatch.setenv("PLATTFORM_PROTOKOLL", str(datei))
    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    monkeypatch.setenv("AZURE_OPENAI_BASE_URL", "https://azure.invalid/openai/v1")
    monkeypatch.setenv("AZURE_API_KEY", "test-schluessel")
    monkeypatch.setenv("MISTRAL_API_KEY", "test-schluessel")
    monkeypatch.setattr(kern, "INSTANZEN", {})
    mock.zuruecksetzen()
    yield datei
    mock.zuruecksetzen()


def _zeilen(datei):
    return [json.loads(z) for z in datei.read_text(encoding="utf-8").splitlines()]


def _chat(text="bereit", modell_version="v-2026"):
    def antworte(anfrage: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "id": "x",
                "object": "chat.completion",
                "created": 0,
                "model": modell_version,
                "choices": [
                    {"index": 0, "message": {"role": "assistant", "content": text}, "finish_reason": "stop"}
                ],
                "usage": {"prompt_tokens": 3, "completion_tokens": 1, "total_tokens": 4},
            },
        )

    return antworte


def _sse(teile, fehler_nach=None):
    """SSE-Antwort; mit ``fehler_nach=n`` reißt der Strom nach n Ereignissen mit ReadError ab."""

    class Strom(httpx.SyncByteStream):
        def __iter__(self):
            for nummer, teil in enumerate(teile):
                if fehler_nach is not None and nummer == fehler_nach:
                    raise httpx.ReadError("abgerissen")
                ereignis = {
                    "id": "x",
                    "object": "chat.completion.chunk",
                    "created": 0,
                    "model": "v-2026",
                    "choices": [{"index": 0, "delta": {"content": teil}, "finish_reason": None}],
                }
                yield f"data: {json.dumps(ereignis)}\n\n".encode()
            yield b"data: [DONE]\n\n"

    def antworte(anfrage: httpx.Request) -> httpx.Response:
        return httpx.Response(200, headers={"content-type": "text/event-stream"}, stream=Strom())

    return antworte


def _client(antworte):
    return httpx.Client(transport=httpx.MockTransport(antworte))


def test_schemafehler_schreibt_keinen_antwortwert_ins_protokoll(protokoll, tmp_path, monkeypatch):
    """Fängt: volle jsonschema-Meldung (enthält den Antwortwert) landet in der Protokollzeile."""
    (tmp_path / "test.wert.json").write_text(
        json.dumps({"antworten": [{"json": {"stufe": "ping-7f3a"}}]}), encoding="utf-8"
    )
    monkeypatch.setenv("PLATTFORM_FIXTURES", str(tmp_path))
    schema = {"type": "object", "properties": {"stufe": {"type": "integer"}}, "required": ["stufe"]}

    with pytest.raises(SchemaFehler) as fehler:
        complete([{"role": "user", "content": "x"}], schema=schema, provider="mock", zweck="test.wert")

    assert "ping-7f3a" in str(fehler.value)  # der Aufrufer sieht die volle Meldung
    assert protokoll.read_text(encoding="utf-8").count("ping-7f3a") == 0
    assert _zeilen(protokoll)[0]["fehler"] == "SchemaFehler: type $.stufe"


def test_fehlender_schluessel_auf_stufe_1_ist_konfigfehler(protokoll, monkeypatch):
    """Fängt: stiller Wechsel auf mistral, obwohl der gewählte Provider azure nie konfiguriert war."""
    monkeypatch.delenv("AZURE_API_KEY")
    kern.INSTANZEN["mistral"] = MistralProvider(http_client=_client(_chat()))

    with pytest.raises(KonfigFehler):
        complete([{"role": "user", "content": "x"}], provider="azure")
    assert _zeilen(protokoll)[0]["fehler"] == "KonfigFehler"


def test_explizites_modell_gilt_nur_fuer_stufe_1(protokoll):
    """Fängt: explizites Modell wird an den Fallback-Provider weitergereicht (falscher Modellname)."""

    def scheitert(anfrage):
        return httpx.Response(503, json={"error": {"message": "weg"}})

    gesehen = []

    def mistral_antwort(anfrage):
        gesehen.append(json.loads(anfrage.content)["model"])
        return _chat()(anfrage)

    kern.INSTANZEN["azure"] = AzureProvider(http_client=_client(scheitert))
    kern.INSTANZEN["mistral"] = MistralProvider(http_client=_client(mistral_antwort))

    antwort = complete([{"role": "user", "content": "x"}], provider="azure", modell="gpt-sonder")

    assert antwort.provider == "mistral" and antwort.fallback_stufe == 2
    assert gesehen == ["mistral-small-latest"]


def test_strom_mock_teile_eine_zeile_kein_inhalt(protokoll):
    """Fängt: fehlende oder doppelte Protokollzeile im Stream-Pfad, Inhalt im Protokoll."""
    nachrichten = [{"role": "user", "content": "ping-7f3a"}]
    teile = list(complete(nachrichten, stream=True, provider="mock", zweck="smoke"))

    assert "".join(teile)
    zeilen = _zeilen(protokoll)
    assert len(zeilen) == 1 and zeilen[0]["fehler"] is None
    assert protokoll.read_text(encoding="utf-8").count("ping-7f3a") == 0


def test_strom_abbruch_durch_verbraucher_schreibt_genau_eine_zeile(protokoll):
    """Fängt: Verbraucher bricht nach dem ersten Teil ab, Protokollzeile fehlt."""
    kern.INSTANZEN["azure"] = AzureProvider(http_client=_client(_sse(["a", "b", "c"])))

    strom = complete([{"role": "user", "content": "x"}], stream=True, provider="azure")
    assert next(strom) == "a"
    strom.close()

    assert len(_zeilen(protokoll)) == 1


def test_strom_lesefehler_vor_erstem_teil_geht_zur_naechsten_stufe(protokoll):
    """Fängt: Abriss beim Lesen wird als harter Fehler gemeldet statt auf Stufe 2 zu wechseln."""
    kern.INSTANZEN["azure"] = AzureProvider(http_client=_client(_sse(["a"], fehler_nach=0)))
    kern.INSTANZEN["mistral"] = MistralProvider(http_client=_client(_sse(["m"])))

    teile = list(complete([{"role": "user", "content": "x"}], stream=True, provider="azure"))

    assert teile == ["m"]
    assert _zeilen(protokoll)[-1]["fallback_stufe"] == 2


def test_strom_lesefehler_nach_erstem_teil_ist_voruebergehend(protokoll):
    """Fängt: roher httpx-Fehler statt VoruebergehenderFehler beim Abriss mitten im Strom."""
    kern.INSTANZEN["azure"] = AzureProvider(http_client=_client(_sse(["a", "b"], fehler_nach=1)))

    strom = complete([{"role": "user", "content": "x"}], stream=True, provider="azure")
    assert next(strom) == "a"
    with pytest.raises(VoruebergehenderFehler):
        next(strom)
    assert _zeilen(protokoll)[-1]["fehler"] == "VoruebergehenderFehler"
