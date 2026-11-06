"""FastAPI `uc2.api` (#44): Start, 404/409/403/422, SSE mit `Last-Event-ID`, Bericht und Belegfilter.

Der Unterprozess ist durch einen Starter ersetzt, der `Verhandlung` im Prozess mit mock und Fixture-Belegen
gegen `healthpolicy_test` ausführt.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

import psycopg
import pytest
from fastapi.testclient import TestClient
from plattform.llm import KonfigFehler  # type: ignore[import-untyped]

import uc2.modelle
from uc2 import db
from uc2.api import erstelle_app
from uc2.api.app import GESPERRT, NICHT_BEREIT, START_GESCHEITERT, ZU_OFT
from uc2.api.belegfilter import BELEG_FELDER, MAX_ZEICHEN, daten_fuer_ausgabe, kuerze
from uc2.api.start import Startauftrag, StartFehler
from uc2.modelle import ModellKonfigFehler
from uc2.verhandlung.belege import FIXTURE, FixtureQuelle
from uc2.verhandlung.fall import lade_fall
from uc2.verhandlung.lauf import Laufoptionen, Verhandlung
from uc2.verhandlung.speicher import Fallschreiber, lies_fall

TEST_DB = "healthpolicy_test"
LANGER_TEXT = " ".join(
    f"Erfundener Testsatz Nummer {i} über Wartezeiten, Kassenstellen und digitale Ersteinschätzung."
    for i in range(1, 9)
)
"""Erfundener Belegtext, deutlich länger als 300 Zeichen."""
LANGER_BELEG = {
    "beleg_id": "abcdefabcdef-001-01",
    "medium": "Testblatt",
    "datum": "2026-09-01",
    "titel": "Erfundener Titel " * 30,
    "text": LANGER_TEXT,
    "text_modell": LANGER_TEXT,
    "akteure": ["sv"],
}


@pytest.fixture(autouse=True)
def protokoll_im_tmp(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("PLATTFORM_PROTOKOLL", str(tmp_path / "modellaufrufe.jsonl"))
    monkeypatch.delenv("UC2_MOCK_KAPUTT", raising=False)
    monkeypatch.delenv("UC2_API_ECHTE_MODELLE", raising=False)
    monkeypatch.delenv("KIC_VOLLTEXT_ONLINE", raising=False)
    monkeypatch.delenv("KIC_ONLINE", raising=False)
    monkeypatch.delenv("LLM_TAGESBUDGET_AUFRUFE", raising=False)


@dataclass
class Fertig:
    fall_id: int

    def laeuft(self) -> bool:
        return False


@dataclass
class Laeuft:
    fall_id: int = 99

    def laeuft(self) -> bool:
        return True


class ImProzess:
    """Starter für Tests: `Verhandlung` direkt, mock, Fixture-Belege, DB `healthpolicy_test`."""

    def __init__(self) -> None:
        self.auftraege: list[Startauftrag] = []

    def __call__(self, auftrag: Startauftrag) -> Fertig:
        self.auftraege.append(auftrag)
        fall = lade_fall(auftrag.fall)
        if auftrag.frage is not None:
            fall = replace(fall, frage=auftrag.frage)
        with db.verbinde(TEST_DB) as v:
            optionen = Laufoptionen(provider=auftrag.provider, quelle=FixtureQuelle())
            return Fertig(Verhandlung(v, fall, optionen).fuehre_aus())


def _verbinde() -> psycopg.Connection[Any]:
    return db.verbinde(TEST_DB, autocommit=True)


@pytest.fixture
def starter() -> ImProzess:
    return ImProzess()


@pytest.fixture
def client(starter: ImProzess) -> Iterator[TestClient]:
    with TestClient(erstelle_app(starter=starter, verbinde=_verbinde)) as c:
        yield c


def _sse(text: str) -> list[dict[str, Any]]:
    bloecke = []
    for roh in text.split("\n\n"):
        felder: dict[str, Any] = {}
        for zeile in roh.splitlines():
            if zeile.startswith(":") or ": " not in zeile:
                continue
            k, v = zeile.split(": ", 1)
            felder[k] = json.loads(v) if k == "data" else v
        if felder:
            bloecke.append(felder)
    return bloecke


def _lies_strom(client: TestClient, fall_id: int, **kw: Any) -> tuple[str, list[dict[str, Any]]]:
    with client.stream("GET", f"/faelle/{fall_id}/ereignisse", **kw) as antwort:
        assert antwort.status_code == 200
        assert antwort.headers["content-type"].startswith("text/event-stream")
        text = "".join(antwort.iter_text())
    return text, _sse(text)


def test_post_startet_mock_fall_und_sse_liest_ihn_mit_last_event_id(
    pg_test: psycopg.Connection[Any], client: TestClient, starter: ImProzess
) -> None:
    antwort = client.post("/faelle", json={"fall": "wartezeiten", "frage": "  Wie sinken\nWartezeiten?  "})
    assert antwort.status_code == 202, antwort.text
    fall_id = antwort.json()["fall_id"]
    assert antwort.json()["status"] == "fertig"
    assert starter.auftraege == [Startauftrag("wartezeiten", "mock", "fixture", "Wie sinken Wartezeiten?")]
    fall = lies_fall(pg_test, fall_id)
    assert fall is not None and fall["frage"] == "Wie sinken Wartezeiten?"

    liste = client.get("/faelle").json()
    assert [(f["fall_id"], f["status"]) for f in liste] == [(fall_id, "fertig")]

    _, bloecke = _lies_strom(client, fall_id, params={"seq": 0})
    ereignisse, ende = bloecke[:-1], bloecke[-1]
    n = len(ereignisse)
    assert [int(b["id"]) for b in ereignisse] == list(range(1, n + 1))
    assert ereignisse[0]["event"] == "start" and ereignisse[-1]["event"] == "ergebnis"
    assert all(b["data"]["art"] == b["event"] for b in ereignisse)
    assert ende["event"] == "ende" and ende["data"] == {"status": "fertig", "letzte_seq": n}

    # Wiederverbinden: Last-Event-ID gewinnt über ?seq
    _, rest = _lies_strom(client, fall_id, params={"seq": 0}, headers={"Last-Event-ID": str(n - 3)})
    assert [int(b["id"]) for b in rest[:-1]] == [n - 2, n - 1, n] and rest[-1]["event"] == "ende"

    b = client.get(f"/faelle/{fall_id}").json()
    assert {"matrix", "klassifikation", "teilnahme"} <= set(b) and len(b["teilnahme"]) == 14


def test_fehlerfaelle_404_422_403_ohne_lauf(pg_test: psycopg.Connection[Any], client: TestClient) -> None:
    assert client.post("/faelle", json={"fall": "gibtsnicht"}).status_code == 404
    for fall in ("../faelle/wartezeiten", "/etc/passwd", "wartezeiten.yaml"):
        assert client.post("/faelle", json={"fall": fall}).status_code == 422
    assert client.post("/faelle", json={"fall": "wartezeiten", "provider": "claude"}).status_code == 403
    assert client.post("/faelle", json={"fall": "wartezeiten", "frage": "a\x00b"}).status_code == 422
    assert client.post("/faelle", json={"fall": "wartezeiten", "frage": "x" * 501}).status_code == 422
    assert client.post("/faelle", json={"fall": "wartezeiten", "fremd": 1}).status_code == 422
    for pfad in ("/faelle/424242", "/faelle/424242/ereignisse"):
        antwort = client.get(pfad)
        assert antwort.status_code == 404 and antwort.json() == {"detail": "Fall 424242 nicht gefunden"}


def test_zweiter_start_waehrend_laufendem_fall_ergibt_409() -> None:
    gestartet: list[Startauftrag] = []

    def starte(auftrag: Startauftrag) -> Laeuft:
        gestartet.append(auftrag)
        return Laeuft()

    with TestClient(erstelle_app(starter=starte, verbinde=_verbinde)) as c:
        erst = c.post("/faelle", json={"fall": "wartezeiten"})
        assert erst.status_code == 202 and erst.json() == {"fall_id": 99, "status": "laufend"}
        zweit = c.post("/faelle", json={"fall": "wartezeiten"})
        assert zweit.status_code == 409 and "läuft noch" in zweit.json()["detail"]
    assert len(gestartet) == 1


def test_echte_modelle_nur_mit_schalter(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("UC2_API_ECHTE_MODELLE", "1")
    gestartet: list[Startauftrag] = []

    def starte(auftrag: Startauftrag) -> Laeuft:
        gestartet.append(auftrag)
        return Laeuft()

    with TestClient(erstelle_app(starter=starte, verbinde=_verbinde)) as c:
        assert c.post("/faelle", json={"fall": "wartezeiten", "provider": "claude"}).status_code == 202
    assert gestartet[0].provider == "claude"


# --- Review !47: Budget, Ratenlimit, feste Fehlertexte ----------------------------------------------------


def test_online_ohne_budget_verweigert_echte_modelle_mit_503(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("UC2_API_ECHTE_MODELLE", "1")
    monkeypatch.setenv("KIC_ONLINE", "1")
    gestartet: list[Startauftrag] = []

    def starte(auftrag: Startauftrag) -> Laeuft:
        gestartet.append(auftrag)
        return Laeuft()

    with TestClient(erstelle_app(starter=starte, verbinde=_verbinde)) as c:
        for budget in (None, "0", "viel"):
            if budget is None:
                monkeypatch.delenv("LLM_TAGESBUDGET_AUFRUFE", raising=False)
            else:
                monkeypatch.setenv("LLM_TAGESBUDGET_AUFRUFE", budget)
            antwort = c.post("/faelle", json={"fall": "wartezeiten", "provider": "azure"})
            assert antwort.status_code == 503 and antwort.json() == {"detail": NICHT_BEREIT}
            assert "KIC_ONLINE" not in antwort.text and "LLM_TAGESBUDGET" not in antwort.text
        assert gestartet == []
        monkeypatch.setenv("LLM_TAGESBUDGET_AUFRUFE", "5")
        assert c.post("/faelle", json={"fall": "wartezeiten", "provider": "azure"}).status_code == 202
    assert [a.provider for a in gestartet] == ["azure"]


class ErstLaeuft:
    """Läuft beim ersten Blick (Antwort `laufend`), danach ist der Lauf vorbei."""

    def __init__(self, fall_id: int) -> None:
        self.fall_id = fall_id
        self.blicke = 0

    def laeuft(self) -> bool:
        self.blicke += 1
        return self.blicke == 1


def test_ratenlimit_ein_start_je_ip_und_minute() -> None:
    jetzt = [1000.0]
    gestartet: list[Startauftrag] = []

    def starte(auftrag: Startauftrag) -> ErstLaeuft:
        gestartet.append(auftrag)
        return ErstLaeuft(len(gestartet))

    app = erstelle_app(starter=starte, verbinde=_verbinde, uhr=lambda: jetzt[0])
    with TestClient(app) as c:
        assert c.post("/faelle", json={"fall": "wartezeiten"}).status_code == 202
        jetzt[0] += 59.0
        zweit = c.post("/faelle", json={"fall": "wartezeiten"})
        assert zweit.status_code == 429 and zweit.json() == {"detail": ZU_OFT}
        jetzt[0] += 1.0
        assert c.post("/faelle", json={"fall": "wartezeiten"}).status_code == 202
    assert len(gestartet) == 2


def test_http_fehler_nennen_keine_env_namen(monkeypatch: pytest.MonkeyPatch) -> None:
    def scheitert(_: Startauftrag) -> Laeuft:
        raise StartFehler("Lauf hat keinen Fall angelegt (Exit 2): UC2_NAMENSLISTE fehlt")

    with TestClient(erstelle_app(starter=scheitert, verbinde=_verbinde)) as c:
        gesperrt = c.post("/faelle", json={"fall": "wartezeiten", "provider": "claude"})
        assert gesperrt.status_code == 403 and gesperrt.json() == {"detail": GESPERRT}
        assert "UC2_API_ECHTE_MODELLE" not in gesperrt.text
        kaputt = c.post("/faelle", json={"fall": "wartezeiten"})
        assert kaputt.status_code == 500 and kaputt.json() == {"detail": START_GESCHEITERT}
        assert "UC2_NAMENSLISTE" not in kaputt.text and "Exit" not in kaputt.text


def test_konfigfehler_mit_env_namen_geht_nur_ins_log(
    pg_test: psycopg.Connection[Any], monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    geheim = "GEHEIMER_ENV_NAME fehlt, siehe /srv/kic/.env.local"

    def kein_modell(*_: Any, **__: Any) -> Any:
        raise KonfigFehler(geheim)

    monkeypatch.setattr(uc2.modelle, "complete", kein_modell)

    def starte(auftrag: Startauftrag) -> Fertig:
        angelegt: list[int] = []
        with db.verbinde(TEST_DB) as v:
            optionen = Laufoptionen(provider="mock", quelle=FixtureQuelle(), bei_anlage=angelegt.append)
            with pytest.raises(ModellKonfigFehler):
                Verhandlung(v, lade_fall(auftrag.fall), optionen).fuehre_aus()
        return Fertig(angelegt[0])

    with TestClient(erstelle_app(starter=starte, verbinde=_verbinde)) as c:
        antwort = c.post("/faelle", json={"fall": "wartezeiten"})
        assert antwort.status_code == 202 and antwort.json()["status"] == "abgebrochen"
        fall_id = antwort.json()["fall_id"]
        text, bloecke = _lies_strom(c, fall_id)
        bericht = c.get(f"/faelle/{fall_id}").text
    abbruch = next(b["data"]["daten"] for b in bloecke if b.get("event") == "abbruch")
    assert abbruch == {"grund": "ModellKonfigFehler", "meldung": NICHT_BEREIT}
    for roh in (antwort.text, text, bericht):
        assert "GEHEIMER_ENV_NAME" not in roh and "/srv/kic" not in roh
    assert any("GEHEIMER_ENV_NAME" in r.getMessage() for r in caplog.records)


# --- Belegfilter (Entscheid Lead, Owner-Klick #8705) ------------------------------------------------


def _belege_in(knoten: Any) -> Iterator[dict[str, Any]]:
    if isinstance(knoten, dict):
        if "beleg_id" in knoten and ("medium" in knoten or "titel" in knoten):
            yield knoten
        for v in knoten.values():
            yield from _belege_in(v)
    elif isinstance(knoten, list):
        for v in knoten:
            yield from _belege_in(v)


def _lauf_mit_langem_beleg(pg_test: psycopg.Connection[Any], tmp_path: Path) -> int:
    """mock-Lauf mit einem erfundenen Langbeleg; danach ein Ereignis mit verschachtelten Volltext-Belegen."""
    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
    fixture["belege"].append(LANGER_BELEG)
    pfad = tmp_path / "belege.json"
    pfad.write_text(json.dumps(fixture, ensure_ascii=False), encoding="utf-8")
    optionen = Laufoptionen(provider="mock", quelle=FixtureQuelle(pfad))
    fall_id = Verhandlung(pg_test, lade_fall("wartezeiten"), optionen).fuehre_aus()
    # Ein späteres Ereignis (etwa Kontext oder Notiz), das Belege mit Volltext verschachtelt trägt.
    s = Fallschreiber(pg_test, fall_id)
    zeile = pg_test.execute("select max(seq) from uc2.ereignis where fall_id = %s", (fall_id,)).fetchone()
    assert zeile is not None
    s.seq = int(zeile[0])
    s.ereignis(
        "kontext",
        {
            "belege": [LANGER_BELEG],
            "notiz": {"zuege": [{"themen": [{"belege": [LANGER_BELEG], "ausschnitt": LANGER_TEXT}]}]},
            "text_anzeige": LANGER_TEXT,
        },
    )
    return fall_id


def test_ohne_schalter_nur_zitatfelder_in_sse_und_bericht(
    pg_test: psycopg.Connection[Any], client: TestClient, tmp_path: Path
) -> None:
    fall_id = _lauf_mit_langem_beleg(pg_test, tmp_path)
    text, bloecke = _lies_strom(client, fall_id)
    bericht = client.get(f"/faelle/{fall_id}")
    assert bericht.status_code == 200
    for roh, daten in ((text, [b["data"] for b in bloecke]), (bericht.text, bericht.json())):
        assert LANGER_TEXT not in roh and LANGER_TEXT[: MAX_ZEICHEN + 1] not in roh
        belege = list(_belege_in(daten))
        assert belege
        for b in belege:
            assert set(b) <= set(BELEG_FELDER), b
            assert all(len(v) <= MAX_ZEICHEN for v in b.values() if isinstance(v, str)), b
    kontext = next(b["data"]["daten"] for b in bloecke if b.get("event") == "kontext")
    assert kontext["belege"][0]["zitat"] == kuerze(LANGER_TEXT) and kontext["belege"][0]["zitat"].endswith(
        "…"
    )
    assert "text_anzeige" not in kontext
    assert len(kontext["notiz"]["zuege"][0]["themen"][0]["ausschnitt"]) <= MAX_ZEICHEN


def test_mit_schalter_kommt_der_volltext(
    pg_test: psycopg.Connection[Any], client: TestClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("KIC_VOLLTEXT_ONLINE", "1")
    fall_id = _lauf_mit_langem_beleg(pg_test, tmp_path)
    _, bloecke = _lies_strom(client, fall_id)
    kontext = next(b["data"]["daten"] for b in bloecke if b.get("event") == "kontext")
    assert kontext["belege"][0]["text"] == LANGER_TEXT
    assert "text_modell" not in kontext["belege"][0]


def test_filter_greift_auch_fuer_die_fixture_belege() -> None:
    roh = json.loads(FIXTURE.read_text(encoding="utf-8"))["belege"]
    aus = daten_fuer_ausgabe({"belege": roh}, volltext=False)["belege"]
    assert len(aus) == len(roh)
    for vorher, nachher in zip(roh, aus, strict=True):
        assert set(nachher) <= set(BELEG_FELDER) and "text" not in nachher and "akteure" not in nachher
        assert nachher["zitat"] == kuerze(vorher["text"])
    # Prüfereignisse mit nur einer Beleg-ID bleiben unverändert
    befund = {"thema": "triage", "beleg_id": "abcdefabcdef-001-01", "wortzahl": 8}
    assert daten_fuer_ausgabe(befund, volltext=False) == befund
