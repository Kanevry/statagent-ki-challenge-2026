"""Tagesbudget LLM_TAGESBUDGET_AUFRUFE (#100): zählt über die Protokolldatei, also prozessübergreifend."""

import json
import os
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


# --- Review !36 (57): fail-closed online, Protokoll vor dem Aufruf beschreibbar -----------------------------


def _kein_provider(name):
    raise AssertionError(f"Provider {name} darf nicht gerufen werden")


def test_online_ohne_budget_mit_echtem_provider_ist_konfigfehler(protokoll, monkeypatch):
    """Fängt: online (KIC_ONLINE=1) ohne LLM_TAGESBUDGET_AUFRUFE geht ein echter Aufruf ohne Grenze durch."""
    monkeypatch.setenv("KIC_ONLINE", "1")
    monkeypatch.delenv("LLM_TAGESBUDGET_AUFRUFE", raising=False)
    monkeypatch.setenv("LLM_PROVIDER", "azure")
    monkeypatch.setattr(kern, "provider_instanz", _kein_provider)

    with pytest.raises(KonfigFehler, match="KIC_ONLINE=1 braucht LLM_TAGESBUDGET_AUFRUFE"):
        complete(NACHRICHT, zweck="smoke")
    with pytest.raises(KonfigFehler, match="KIC_ONLINE=1"):
        complete(NACHRICHT, stream=True, zweck="smoke")
    assert _zeilen(protokoll) == []


def test_online_ohne_budget_mit_mock_laeuft(protokoll, monkeypatch):
    """Fängt: die Sperre trifft auch mock, dann bricht die lesende Online-Demo ohne Schlüssel."""
    monkeypatch.setenv("KIC_ONLINE", "1")
    monkeypatch.delenv("LLM_TAGESBUDGET_AUFRUFE", raising=False)

    assert complete(NACHRICHT, zweck="smoke").provider == "mock"


def test_budget_mit_unbeschreibbarem_protokoll_ruft_keinen_provider(tmp_path, protokoll, monkeypatch):
    """Fängt: Protokoll nicht beschreibbar (read_only ohne Volume) zählt 0, der Provider liefe trotzdem."""
    sperre = tmp_path / "keine-ordner"
    sperre.write_text("eine Datei, kein Ordner", encoding="utf-8")
    monkeypatch.setenv("PLATTFORM_PROTOKOLL", str(sperre / "modellaufrufe.jsonl"))
    monkeypatch.setenv("LLM_TAGESBUDGET_AUFRUFE", "5")
    monkeypatch.setattr(kern, "provider_instanz", _kein_provider)

    with pytest.raises(KonfigFehler, match="beschreibbares Protokoll"):
        complete(NACHRICHT, zweck="smoke")


@pytest.mark.skipif(os.name != "posix" or os.geteuid() == 0, reason="root ignoriert Dateirechte")
def test_budget_mit_schreibgeschuetztem_ordner_ist_konfigfehler(tmp_path, monkeypatch):
    """Fängt: schreibgeschützter Protokollordner (wie read_only im Container) lässt den Aufruf durch."""
    ordner = tmp_path / "nur-lesen"
    ordner.mkdir()
    ordner.chmod(0o500)
    try:
        monkeypatch.setenv("PLATTFORM_PROTOKOLL", str(ordner / "modellaufrufe.jsonl"))
        monkeypatch.setenv("LLM_TAGESBUDGET_AUFRUFE", "5")
        monkeypatch.setenv("LLM_PROVIDER", "mock")
        monkeypatch.setattr(kern, "provider_instanz", _kein_provider)
        with pytest.raises(KonfigFehler, match="beschreibbares Protokoll"):
            complete(NACHRICHT, zweck="smoke")
    finally:
        ordner.chmod(0o700)


# --- Folge Review !36 (#118) ----------------------------------------------------------------------


def test_status_json_nennt_budget(protokoll, monkeypatch, capsys):
    """Fängt: status --json ohne Feld budget, die Web-App und der Lead sehen den Stand nicht."""
    from plattform.llm.__main__ import main

    monkeypatch.setenv("LLM_TAGESBUDGET_AUFRUFE", "3")
    complete(NACHRICHT, zweck="smoke")
    assert main(["status", "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["budget"] == {"grenze": 3, "verbraucht": 1, "frei": 2}


def test_zeit_mit_offset_ueber_mitternacht_zaehlt_nach_utc(protokoll, monkeypatch):
    """Fängt: Zeilen mit +01:00 kurz nach Mitternacht landen am falschen UTC-Tag (zu viel oder zu wenig)."""

    class FesteZeit(datetime):
        @classmethod
        def now(cls, tz=None):
            return datetime(2026, 11, 5, 23, 45, tzinfo=UTC)

    monkeypatch.setattr(kern, "datetime", FesteZeit)
    zeilen = [
        {"provider": "mock", "zeit": "2026-11-05T00:30:00+01:00"},  # 04.11. 23:30 UTC, gestern
        {"provider": "mock", "zeit": "2026-11-05T01:30:00+01:00"},  # 05.11. 00:30 UTC, heute
        {"provider": "mock", "zeit": "2026-11-06T00:30:00+01:00"},  # 05.11. 23:30 UTC, heute
    ]
    monkeypatch.setenv("LLM_TAGESBUDGET_AUFRUFE", "10")

    def verbraucht(auswahl: list[dict]) -> int | None:
        protokoll.write_text("".join(json.dumps(z) + "\n" for z in auswahl), encoding="utf-8")
        return budget_status()["verbraucht"]

    assert verbraucht(zeilen) == 2
    # Review !66: ohne astimezone zählte Z1 (Ortsdatum 05.11.) als heute, und Z3 (Ortsdatum 06.11.) als morgen
    assert verbraucht(zeilen[:2]) == 1
    assert verbraucht(zeilen[1:]) == 2


def test_zeile_von_gestern_nach_einer_von_heute_beendet_die_zaehlung_nicht(protokoll, monkeypatch):
    """Fängt (Review !66): Wettlauf um Mitternacht, eine späte Zeile von gestern brach die Zählung ab."""
    heute = datetime.now(UTC)
    gestern = heute - timedelta(days=1)
    zeilen = [heute, gestern, heute]
    protokoll.write_text(
        "".join(json.dumps({"provider": "mock", "zeit": z.isoformat()}) + "\n" for z in zeilen),
        encoding="utf-8",
    )
    monkeypatch.setenv("LLM_TAGESBUDGET_AUFRUFE", "10")
    assert budget_status()["verbraucht"] == 2
