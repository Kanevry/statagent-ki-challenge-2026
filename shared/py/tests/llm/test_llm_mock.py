"""mock-Provider und Schema-Wiederholung (Vertrag M, Akzeptanz 1 und 4)."""

import json

import pytest
from plattform.llm import SchemaFehler, complete, kern, mock
from pydantic import BaseModel


@pytest.fixture
def umgebung(tmp_path, monkeypatch):
    protokoll = tmp_path / "modellaufrufe.jsonl"
    monkeypatch.setenv("PLATTFORM_PROTOKOLL", str(protokoll))
    monkeypatch.setenv("LLM_PROVIDER", "mock")
    monkeypatch.setattr(kern, "INSTANZEN", {})
    mock.zuruecksetzen()
    yield protokoll
    mock.zuruecksetzen()


def test_mock_deterministisch_und_protokoll_ohne_inhalt(umgebung):
    """Fängt: nicht-deterministische Antwort (gemessene Dauer), fehlende/doppelte Zeile, Inhalt im Log."""
    erste = complete([{"role": "user", "content": "ping-7f3a"}], zweck="smoke")
    zweite = complete([{"role": "user", "content": "ping-7f3a"}], zweck="smoke")

    assert repr(erste).encode() == repr(zweite).encode()
    inhalt = umgebung.read_text(encoding="utf-8")
    assert len(inhalt.splitlines()) == 2
    assert inhalt.count("ping-7f3a") == 0
    assert json.loads(inhalt.splitlines()[0])["provider"] == "mock"


class Einstufung(BaseModel):
    stufe: int


def _fixture(tmp_path, monkeypatch, antworten):
    (tmp_path / "test.schema.json").write_text(json.dumps({"antworten": antworten}), encoding="utf-8")
    monkeypatch.setenv("PLATTFORM_FIXTURES", str(tmp_path))


def test_schema_heilt_nach_genau_einer_wiederholung(umgebung, tmp_path, monkeypatch):
    """Fängt: keine Wiederholung bei ungültigem JSON bzw. mehr als eine Wiederholung."""
    _fixture(tmp_path, monkeypatch, [{"text": "kein json"}, {"json": {"stufe": 2}}, {"json": {"stufe": 9}}])

    antwort = complete([{"role": "user", "content": "stufe?"}], schema=Einstufung, zweck="test.schema")

    assert antwort.json == {"stufe": 2}
    assert mock._ZAEHLER[mock.fixture_pfad("test.schema")] == 2
    assert len(umgebung.read_text(encoding="utf-8").splitlines()) == 1


def test_schema_zweimal_ungueltig_wirft_schemafehler(umgebung, tmp_path, monkeypatch):
    """Fängt: stilles Durchreichen einer schemawidrigen Antwort nach der Wiederholung."""
    _fixture(tmp_path, monkeypatch, [{"json": {"stufe": "hoch"}}, {"json": {"falsch": 1}}])
    schema = {"type": "object", "properties": {"stufe": {"type": "integer"}}, "required": ["stufe"]}

    with pytest.raises(SchemaFehler):
        complete([{"role": "user", "content": "stufe?"}], schema=schema, zweck="test.schema")
    assert json.loads(umgebung.read_text(encoding="utf-8"))["fehler"].startswith("SchemaFehler")
