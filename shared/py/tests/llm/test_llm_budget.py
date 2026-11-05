"""Tagesbudget LLM_TAGESBUDGET_AUFRUFE (#100): zählt über die Protokolldatei, also prozessübergreifend."""

import json
from datetime import UTC, datetime, timedelta

import pytest
from plattform import router
from plattform.llm import BudgetErschoepft, KonfigFehler, budget_status, complete, kern, mock

NACHRICHT = [{"role": "user", "content": "ping"}]


@pytest.fixture
def protokoll(tmp_path, monkeypatch):
    datei = tmp_path / "modellaufrufe.jsonl"
    monkeypatch.setenv("PLATTFORM_PROTOKOLL", str(datei))
    monkeypatch.delenv("PLATTFORM_ROUTER_PROTOKOLL", raising=False)
    monkeypatch.setenv("LLM_PROVIDER", "mock")
    monkeypatch.setattr(kern, "INSTANZEN", {})
    mock.zuruecksetzen()
    yield datei
    mock.zuruecksetzen()


def _zeilen(datei):
    return datei.read_text(encoding="utf-8").splitlines() if datei.is_file() else []


def test_dritter_aufruf_ueber_budget_2_wirft_ohne_protokollzeile(protokoll, monkeypatch):
    """Fängt: Budget ohne Wirkung oder ein abgelehnter Aufruf, der trotzdem eine Zeile schreibt."""
    monkeypatch.setenv("LLM_TAGESBUDGET_AUFRUFE", "2")
    complete(NACHRICHT, zweck="smoke")
    complete(NACHRICHT, zweck="smoke")

    with pytest.raises(BudgetErschoepft, match="Tageskontingent"):
        complete(NACHRICHT, zweck="smoke")
    assert len(_zeilen(protokoll)) == 2
    assert budget_status() == {"grenze": 2, "verbraucht": 2, "frei": 0}


def test_stream_wirft_schon_beim_aufruf(protokoll, monkeypatch):
    """Fängt: Prüfung erst im Generator, also nach der Rückgabe von complete (Route sähe keinen Fehler)."""
    monkeypatch.setenv("LLM_TAGESBUDGET_AUFRUFE", "1")
    complete(NACHRICHT, zweck="smoke")
    with pytest.raises(BudgetErschoepft):
        complete(NACHRICHT, stream=True, zweck="smoke")
    assert len(_zeilen(protokoll)) == 1


@pytest.mark.parametrize(
    ("provider", "tage_zurueck"),
    [("mock", 1), ("router", 0), ("lokal", 0)],
    ids=["vortag", "router", "embeddings"],
)
def test_fremde_zeilen_zaehlen_nicht(protokoll, monkeypatch, provider, tage_zurueck):
    """Fängt: Zeilen vom Vortag oder von Router/Embeddings, die das Budget von heute aufbrauchen."""
    zeit = (datetime.now(UTC) - timedelta(days=tage_zurueck)).isoformat(timespec="milliseconds")
    protokoll.write_text(json.dumps({"provider": provider, "zeit": zeit}) + "\n", encoding="utf-8")
    monkeypatch.setenv("LLM_TAGESBUDGET_AUFRUFE", "1")

    complete(NACHRICHT, zweck="smoke")
    assert len(_zeilen(protokoll)) == 2


def test_ungueltiges_budget_ist_konfigfehler(protokoll, monkeypatch):
    """Fängt: ein Tippfehler im Wert, der still „kein Budget“ heißt."""
    monkeypatch.setenv("LLM_TAGESBUDGET_AUFRUFE", "zehn")
    with pytest.raises(KonfigFehler, match="LLM_TAGESBUDGET_AUFRUFE"):
        complete(NACHRICHT, zweck="smoke")
    assert _zeilen(protokoll) == []


def test_router_cli_mit_erschoepftem_budget_endet_mit_exit_3(protokoll, monkeypatch, capsys):
    """Fängt: Router ruft die Adapter trotz verbrauchtem Budget und meldet ein normales Ergebnis."""
    monkeypatch.setenv("LLM_TAGESBUDGET_AUFRUFE", "1")
    complete(NACHRICHT, zweck="smoke")
    gerufen = []
    monkeypatch.setattr(router, "_REGISTRY", {"uc3": lambda f, k: gerufen.append(f)})

    assert router.main(["frage", "--json", "Wie viele?"]) == 3
    assert json.loads(capsys.readouterr().out)["fehler"] == "budget_erschoepft"
    assert gerufen == []
    assert not (protokoll.parent / "router.jsonl").exists()
