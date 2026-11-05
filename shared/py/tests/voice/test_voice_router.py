"""Vertrag V (#61): /chat/completions, Webhook, Tunnel-Middleware, R2. Alles per TestClient, ohne Netz."""

from __future__ import annotations

import json
import subprocess
import sys
import time
from collections import OrderedDict
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from plattform.antwortform import Beleg
from plattform.voice import (
    Fehlversuche,
    Sitzung,
    TunnelFilter,
    VoiceAntwort,
    erstelle_router,
    kern,
    sitzungs_belege,
    text_antwort,
)
from starlette.requests import Request

ANFRAGE = json.loads((Path(__file__).with_name("vapi_anfrage.json")).read_text(encoding="utf-8"))
SCHLUESSEL = "test-llm-schluessel"
SECRET = "test-webhook-secret"
BELEG = Beleg(uc="uc3", quelle="stat.beschaeftigte_monat", lieferung="2025-03", sql="SELECT 1")
GESPROCHEN = "Im März 2025 waren es 387.180 Beschäftigte. Beleg: stat.beschaeftigte_monat 2025-03."


class Aufzeichnung:
    def __init__(self) -> None:
        self.aufrufe: list[tuple[list[dict[str, str]], Sitzung]] = []

    def __call__(self, nachrichten: list[dict[str, str]], sitzung: Sitzung) -> VoiceAntwort:
        self.aufrufe.append((nachrichten, sitzung))
        return VoiceAntwort(text="Im März 2025 waren es 387.180 Beschäftigte.", belege=[BELEG])


@pytest.fixture
def umgebung(tmp_path, monkeypatch):
    monkeypatch.setenv("VAPI_CUSTOM_LLM_KEY", SCHLUESSEL)
    monkeypatch.setenv("VAPI_WEBHOOK_SECRET", SECRET)
    monkeypatch.setenv("PLATTFORM_VOICE_PROTOKOLL", str(tmp_path / "voice.jsonl"))
    monkeypatch.setenv("PLATTFORM_PROTOKOLL", str(tmp_path / "modellaufrufe.jsonl"))
    monkeypatch.delenv("PUBLIC_URL", raising=False)
    monkeypatch.setattr(kern, "_SITZUNGEN", OrderedDict())
    monkeypatch.setattr(kern, "_GEMELDET", OrderedDict())
    for name in ("VOICE_ANTWORT_TIMEOUT_S", "VOICE_RATENLIMIT_PRO_MINUTE"):
        monkeypatch.delenv(name, raising=False)
    return tmp_path


@pytest.fixture
def antwort():
    return Aufzeichnung()


@pytest.fixture
def client(umgebung, antwort):
    app = FastAPI()
    app.include_router(erstelle_router(antwort, uc="uc3"))

    @app.get("/laeufe")
    def laeufe() -> list[str]:
        return []

    app.add_middleware(TunnelFilter, public_url="https://tunnel.example.org")
    return TestClient(app)


def _bearer(wert: str = SCHLUESSEL) -> dict[str, str]:
    return {"Authorization": f"Bearer {wert}"}


def _inhalt_aus_sse(text: str) -> tuple[str, list[str]]:
    daten = [zeile[len("data: ") :] for zeile in text.splitlines() if zeile.startswith("data: ")]
    chunks = [json.loads(d) for d in daten if d != "[DONE]"]
    assert all(c["object"] == "chat.completion.chunk" for c in chunks)
    return "".join(c["choices"][0]["delta"].get("content", "") for c in chunks), daten


# --- /chat/completions ------------------------------------------------------------------------------


def test_stream_liefert_sse_mit_text_und_gesprochenem_beleg_und_done(client, antwort):
    antwort_http = client.post("/chat/completions", json=ANFRAGE, headers=_bearer())
    assert antwort_http.status_code == 200
    assert antwort_http.headers["content-type"].startswith("text/event-stream")
    inhalt, daten = _inhalt_aus_sse(antwort_http.text)
    assert inhalt == GESPROCHEN
    assert daten[-1] == "[DONE]"
    assert len(daten) > 3  # wirklich in Stücken, nicht ein Block


def test_sitzung_traegt_call_id_aus_dem_body_und_uc(client, antwort):
    client.post("/chat/completions", json=ANFRAGE, headers=_bearer())
    nachrichten, sitzung = antwort.aufrufe[0]
    assert sitzung.call_id == ANFRAGE["call"]["id"]
    assert sitzung.uc == "uc3"
    # Teile-Liste der Vapi-Nachricht wird zu Text, Rollen bleiben
    assert nachrichten[-1] == {"role": "user", "content": "Wie viele Beschäftigte im März 2025?"}


def test_zweite_anfrage_desselben_anrufs_behaelt_gestartet(client, antwort):
    client.post("/chat/completions", json=ANFRAGE, headers=_bearer())
    client.post("/chat/completions", json=ANFRAGE, headers=_bearer())
    assert antwort.aufrufe[0][1].gestartet == antwort.aufrufe[1][1].gestartet


def test_ohne_stream_dieselbe_antwort_als_chat_completion(client):
    antwort_http = client.post("/chat/completions", json={**ANFRAGE, "stream": False}, headers=_bearer())
    assert antwort_http.status_code == 200
    koerper = antwort_http.json()
    assert koerper["object"] == "chat.completion"
    assert koerper["choices"][0]["message"] == {"role": "assistant", "content": GESPROCHEN}


@pytest.mark.parametrize("kopf", [{}, _bearer("falsch"), {"Authorization": SCHLUESSEL}])
def test_ohne_oder_mit_falschem_bearer_401_und_antwort_nicht_gerufen(client, antwort, kopf):
    assert client.post("/chat/completions", json=ANFRAGE, headers=kopf).status_code == 401
    assert antwort.aufrufe == []


def test_ohne_variable_503_auch_mit_bearer(client, antwort, monkeypatch):
    monkeypatch.delenv("VAPI_CUSTOM_LLM_KEY")
    assert client.post("/chat/completions", json=ANFRAGE, headers=_bearer()).status_code == 503
    assert antwort.aufrufe == []


def test_leere_variable_gilt_als_fehlend_503(client, monkeypatch):
    # Sonst wäre ein leerer Bearer gegen eine leere Variable „gleich“.
    monkeypatch.setenv("VAPI_CUSTOM_LLM_KEY", "")
    assert (
        client.post("/chat/completions", json=ANFRAGE, headers={"Authorization": "Bearer "}).status_code
        == 503
    )


def test_token_im_pfad_gibt_es_nicht(client):
    # Vapi hängt /chat/completions an die Basis-URL; ein Token im Pfad landete in Proxy-Logs.
    assert client.post(f"/chat/completions/{SCHLUESSEL}", json=ANFRAGE).status_code == 404


def test_503_nennt_keinen_variablennamen(client, monkeypatch):
    monkeypatch.delenv("VAPI_CUSTOM_LLM_KEY")
    antwort_http = client.post("/chat/completions", json=ANFRAGE, headers=_bearer())
    assert antwort_http.json() == {"detail": "Voice ist nicht eingerichtet."}


def test_belege_liegen_je_call_id_fuer_die_ui_ohne_doppelte(client):
    client.post("/chat/completions", json=ANFRAGE, headers=_bearer())
    client.post("/chat/completions", json=ANFRAGE, headers=_bearer())
    assert sitzungs_belege(ANFRAGE["call"]["id"]) == [BELEG]
    assert sitzungs_belege("unbekannt") == []


def test_gesprochener_beleg_nennt_kein_sql(client):
    inhalt, _ = _inhalt_aus_sse(client.post("/chat/completions", json=ANFRAGE, headers=_bearer()).text)
    assert "SELECT" not in inhalt


def test_sitzungsspeicher_hat_eine_grenze(client, monkeypatch):
    monkeypatch.setattr(kern, "MAX_SITZUNGEN", 2)
    for nummer in range(3):
        body = {**ANFRAGE, "call": {"id": f"anruf-{nummer}"}}
        client.post("/chat/completions", json=body, headers=_bearer())
    assert list(kern._SITZUNGEN) == ["anruf-1", "anruf-2"]
    assert sitzungs_belege("anruf-0") == []


def test_antwort_als_mapping_wird_streng_geprueft(umgebung):
    def als_dict(nachrichten, sitzung):
        return {"text": "x", "belege": [{"uc": "uc3", "quelle": "q", "lieferung": 202503}]}

    app = FastAPI()
    app.include_router(erstelle_router(als_dict, uc="uc3"))
    with pytest.raises(ValueError):  # lieferung als Zahl ist kein gültiger Beleg
        TestClient(app).post("/chat/completions", json=ANFRAGE, headers=_bearer())


def test_fehlversuche_werden_begrenzt(umgebung, antwort):
    app = FastAPI()
    app.include_router(erstelle_router(antwort, uc="uc3", fehlversuche=Fehlversuche(grenze=2)))
    client = TestClient(app)
    codes = [
        client.post("/chat/completions", json=ANFRAGE, headers=_bearer("x")).status_code for _ in range(3)
    ]
    assert codes == [401, 401, 429]
    # Andere IP ist nicht gesperrt
    andere = client.post(
        "/chat/completions", json=ANFRAGE, headers={**_bearer(), "CF-Connecting-IP": "203.0.113.9"}
    )
    assert andere.status_code == 200


def test_fehlversuche_fenster_laeuft_ab():
    jetzt = [0.0]
    zaehler = Fehlversuche(grenze=1, fenster_s=10.0, uhr=lambda: jetzt[0])
    zaehler.merken("ip")
    assert zaehler.gesperrt("ip")
    jetzt[0] = 11.0
    assert not zaehler.gesperrt("ip")


def test_text_fallback_nutzt_dieselbe_funktion_ohne_gesprochenen_beleg(antwort):
    ergebnis = text_antwort(antwort, "Wie viele Beschäftigte im März 2025?", "uc3")
    assert ergebnis.text == "Im März 2025 waren es 387.180 Beschäftigte."
    assert ergebnis.belege == [BELEG]
    nachrichten, sitzung = antwort.aufrufe[0]
    assert nachrichten == [{"role": "user", "content": "Wie viele Beschäftigte im März 2025?"}]
    assert sitzung.uc == "uc3"


# --- /vapi/webhook ----------------------------------------------------------------------------------


def _bericht() -> dict:
    return {
        "message": {
            "type": "end-of-call-report",
            "endedReason": "customer-ended-call",
            "durationSeconds": 42.37,
            "call": {"id": ANFRAGE["call"]["id"]},
            "transcript": "AI: Hallo. User: Wie viele Beschäftigte im März 2025?",
            "summary": "Frage nach Beschäftigten",
        }
    }


@pytest.fixture
def body_zaehler(monkeypatch):
    """Zählt jedes Lesen des Request-Bodys (``body`` und ``json`` lesen über ``stream``)."""
    zaehler = {"gelesen": 0}
    original = Request.stream

    async def zaehlend(self):
        zaehler["gelesen"] += 1
        async for stueck in original(self):
            yield stueck

    monkeypatch.setattr(Request, "stream", zaehlend)
    return zaehler


@pytest.mark.parametrize("kopf", [{}, {"x-vapi-secret": "falsch"}])
def test_webhook_ohne_oder_falsches_secret_401_ohne_body_zu_lesen(client, body_zaehler, kopf):
    antwort_http = client.post("/vapi/webhook", json=_bericht(), headers=kopf)
    assert antwort_http.status_code == 401
    assert body_zaehler["gelesen"] == 0


def test_webhook_ohne_variable_503(client, monkeypatch):
    monkeypatch.delenv("VAPI_WEBHOOK_SECRET")
    assert client.post("/vapi/webhook", json=_bericht(), headers={"x-vapi-secret": SECRET}).status_code == 503


def test_webhook_anderer_typ_ignored_ohne_protokoll(client, umgebung):
    body = {"message": {"type": "status-update", "status": "in-progress"}}
    antwort_http = client.post("/vapi/webhook", json=body, headers={"x-vapi-secret": SECRET})
    assert (antwort_http.status_code, antwort_http.json()) == (200, {"status": "ignored"})
    assert not (umgebung / "voice.jsonl").exists()


def test_webhook_end_of_call_report_genau_eine_zeile_ohne_inhalt(client, umgebung, body_zaehler):
    antwort_http = client.post("/vapi/webhook", json=_bericht(), headers={"x-vapi-secret": SECRET})
    assert antwort_http.status_code == 200
    assert body_zaehler["gelesen"] >= 1
    zeilen = (umgebung / "voice.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(zeilen) == 1
    zeile = json.loads(zeilen[0])
    assert set(zeile) == {"zeit", "uc", "typ", "call_id_hash", "dauer_s", "endgrund"}
    assert zeile["dauer_s"] == 42.4
    assert zeile["endgrund"] == "customer-ended-call"
    assert ANFRAGE["call"]["id"] not in zeilen[0]
    assert "Beschäftigte" not in zeilen[0] and "Hallo" not in zeilen[0]
    assert not (umgebung / "modellaufrufe.jsonl").exists()


def test_webhook_dauer_aus_start_und_ende(client, umgebung):
    bericht = _bericht()
    del bericht["message"]["durationSeconds"]
    bericht["message"] |= {"startedAt": "2026-11-05T20:00:00Z", "endedAt": "2026-11-05T20:01:30Z"}
    client.post("/vapi/webhook", json=bericht, headers={"x-vapi-secret": SECRET})
    zeile = json.loads((umgebung / "voice.jsonl").read_text(encoding="utf-8"))
    assert zeile["dauer_s"] == 90.0


def test_webhook_kein_json_400(client):
    antwort_http = client.post("/vapi/webhook", content=b"{kaputt", headers={"x-vapi-secret": SECRET})
    assert antwort_http.status_code == 400


def test_voice_protokoll_standard_neben_modellprotokoll(umgebung, monkeypatch):
    monkeypatch.delenv("PLATTFORM_VOICE_PROTOKOLL")
    assert kern.voice_protokoll_datei() == umgebung / "voice.jsonl"


# --- Tunnel-Middleware ------------------------------------------------------------------------------


def test_tunnel_host_sperrt_andere_pfade(client):
    assert client.get("/laeufe", headers={"Host": "tunnel.example.org"}).status_code == 404
    assert client.get("/laeufe", headers={"Host": "TUNNEL.example.org:443"}).status_code == 404


def test_tunnel_host_laesst_chat_und_webhook_durch(client):
    host = {"Host": "tunnel.example.org"}
    assert client.post("/chat/completions", json=ANFRAGE, headers={**host, **_bearer()}).status_code == 200
    webhook = client.post(
        "/vapi/webhook", json={"message": {"type": "x"}}, headers={**host, "x-vapi-secret": SECRET}
    )
    assert webhook.status_code == 200


def test_cf_connecting_ip_gilt_als_tunnel(client):
    assert client.get("/laeufe", headers={"CF-Connecting-IP": "203.0.113.9"}).status_code == 404


def test_lokal_bleibt_die_api_offen(client):
    assert client.get("/laeufe").status_code == 200


def test_tunnel_host_aus_public_url_der_umgebung(umgebung, monkeypatch):
    monkeypatch.setenv("PUBLIC_URL", "https://andere.example.org/")
    app = FastAPI()

    @app.get("/laeufe")
    def laeufe() -> list[str]:
        return []

    app.add_middleware(TunnelFilter)
    client = TestClient(app)
    assert client.get("/laeufe", headers={"Host": "andere.example.org"}).status_code == 404
    assert client.get("/laeufe").status_code == 200


def test_aehnlicher_pfad_ist_ueber_tunnel_gesperrt(client):
    for pfad in ("/chat/completionsX", "/chat/completions/x", "/vapi/webhook/x"):
        assert client.post(pfad, headers={"Host": "tunnel.example.org"}).status_code == 404


# --- R2 ---------------------------------------------------------------------------------------------


def test_r2_plattform_laedt_voice_nicht():
    code = "import sys, plattform; print(sorted(m for m in sys.modules if m.startswith('plattform.voice')))"
    lauf = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, timeout=60, check=True
    )
    assert lauf.stdout.strip() == "[]"


def test_r2_plattform_voice_laedt_plattform_llm_nicht():
    code = (
        "import sys, plattform.voice; "
        "print('plattform.llm' in sys.modules, 'plattform.router' in sys.modules)"
    )
    lauf = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, timeout=60, check=True
    )
    assert lauf.stdout.strip() == "False False"


# --- Review !38: Signatur, Grenzen, Endgrund, Ratenlimit, Budget, Idempotenz ------------------------


def _app(antwortfunktion, **optionen) -> TestClient:
    app = FastAPI()
    app.include_router(erstelle_router(antwortfunktion, **optionen))
    return TestClient(app)


def test_uc_ist_optional_und_kommt_sonst_aus_metadata(umgebung, antwort):
    client = _app(antwort)
    client.post("/chat/completions", json={**ANFRAGE, "metadata": {"uc": "uc1"}}, headers=_bearer())
    client.post("/chat/completions", json={**ANFRAGE, "call": {"id": "b"}, "metadata": {}}, headers=_bearer())
    assert [s.uc for _, s in antwort.aufrufe] == ["uc1", "unbekannt"]


def test_body_ueber_256_kib_per_content_length_413(client, antwort):
    gross = json.dumps({**ANFRAGE, "fuell": "x" * (kern.MAX_BODY_BYTES + 1)})
    antwort_http = client.post(
        "/chat/completions", content=gross, headers={**_bearer(), "Content-Type": "application/json"}
    )
    assert antwort_http.status_code == 413
    assert antwort.aufrufe == []


def test_body_ueber_256_kib_ohne_content_length_beim_lesen_413(client, antwort):
    def stuecke():
        yield b'{"fuell": "'
        for _ in range(9):
            yield b"x" * 32 * 1024
        yield b'"}'

    antwort_http = client.post("/chat/completions", content=stuecke(), headers=_bearer())
    assert "content-length" not in {k.lower() for k in antwort_http.request.headers}
    assert antwort_http.status_code == 413
    assert antwort.aufrufe == []


def test_webhook_body_ueber_grenze_413(client):
    gross = json.dumps({"message": {"type": "x", "fuell": "x" * (kern.MAX_BODY_BYTES + 1)}})
    antwort_http = client.post(
        "/vapi/webhook", content=gross, headers={"x-vapi-secret": SECRET, "Content-Type": "application/json"}
    )
    assert antwort_http.status_code == 413


def test_antwort_ohne_ergebnis_in_der_frist_504(umgebung, monkeypatch):
    monkeypatch.setenv("VOICE_ANTWORT_TIMEOUT_S", "0.05")

    def langsam(nachrichten, sitzung):
        time.sleep(0.5)
        return VoiceAntwort(text="zu spät")

    assert _app(langsam).post("/chat/completions", json=ANFRAGE, headers=_bearer()).status_code == 504


def test_budget_erschoepft_wird_429_mit_meldung(umgebung):
    class LlmFehler(Exception):
        pass

    class BudgetErschoepft(LlmFehler):
        pass

    def ohne_budget(nachrichten, sitzung):
        raise BudgetErschoepft("Tagesbudget 100 erreicht")

    antwort_http = _app(ohne_budget).post("/chat/completions", json=ANFRAGE, headers=_bearer())
    assert antwort_http.status_code == 429
    assert "Tagesbudget" in antwort_http.json()["detail"]


def test_andere_fehler_aus_antwort_bleiben_500(umgebung):
    def kaputt(nachrichten, sitzung):
        raise RuntimeError("x")

    app = FastAPI()
    app.include_router(erstelle_router(kaputt))
    antwort_http = TestClient(app, raise_server_exceptions=False).post(
        "/chat/completions", json=ANFRAGE, headers=_bearer()
    )
    assert antwort_http.status_code == 500


def test_gueltige_aufrufe_je_ip_begrenzt(umgebung, antwort, monkeypatch):
    monkeypatch.setenv("VOICE_RATENLIMIT_PRO_MINUTE", "2")
    client = _app(antwort)
    codes = [client.post("/chat/completions", json=ANFRAGE, headers=_bearer()).status_code for _ in range(3)]
    assert codes == [200, 200, 429]
    assert len(antwort.aufrufe) == 2


@pytest.mark.parametrize(
    ("roh", "erwartet"),
    [
        ("customer-ended-call", "customer-ended-call"),
        ("pipeline-error-openai-llm-failed", "pipeline-error-openai-llm-failed"),
        ("call.in-progress.error-vapifault-transport-never-connected", None),
        ("pipeline-error-+43 664 1234567", "sonstiges"),
        ("pipeline-error-436641234567", "sonstiges"),
        ("Herr Mustermann legte auf", "sonstiges"),
        ("frei-erfunden", "sonstiges"),
        (None, None),
    ],
)
def test_endgrund_nur_aus_allowlist(roh, erwartet):
    assert kern.endgrund(roh) == (roh if erwartet is None and roh else erwartet)


def test_webhook_zweiter_bericht_desselben_anrufs_schreibt_keine_zeile(client, umgebung, monkeypatch):
    kopf = {"x-vapi-secret": SECRET}
    assert client.post("/vapi/webhook", json=_bericht(), headers=kopf).json() == {"status": "ok"}
    assert client.post("/vapi/webhook", json=_bericht(), headers=kopf).json() == {"status": "doppelt"}
    # Nach einem Neustart (leere Menge im Speicher) hilft der Abgleich mit der Datei
    monkeypatch.setattr(kern, "_GEMELDET", OrderedDict())
    assert client.post("/vapi/webhook", json=_bericht(), headers=kopf).json() == {"status": "doppelt"}
    assert len((umgebung / "voice.jsonl").read_text(encoding="utf-8").splitlines()) == 1


def test_webhook_endgrund_mit_telefonnummer_landet_nicht_im_log(client, umgebung):
    bericht = _bericht()
    bericht["message"]["endedReason"] = "pipeline-error-+436641234567"
    client.post("/vapi/webhook", json=bericht, headers={"x-vapi-secret": SECRET})
    zeile = (umgebung / "voice.jsonl").read_text(encoding="utf-8")
    assert "6641234567" not in zeile and json.loads(zeile)["endgrund"] == "sonstiges"
