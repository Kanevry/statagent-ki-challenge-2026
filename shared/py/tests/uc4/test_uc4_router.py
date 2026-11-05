"""Router UC4 (#97): Reihenfolge, Kontext, Protokoll ohne Fragetext, fehlende Adapter, R2."""

import subprocess
import sys

import pytest
from plattform.router import durchreichen, mock_adapter


@pytest.fixture
def protokoll(tmp_path, monkeypatch):
    datei = tmp_path / "modellaufrufe.jsonl"
    monkeypatch.setenv("PLATTFORM_PROTOKOLL", str(datei))
    return datei


def test_reihenfolge_und_uc2_sieht_uc3_zahl(protokoll):
    gesehen = {}
    adapter = mock_adapter()
    mock_uc2 = adapter["uc2"]

    def uc2(frage, kontext):
        gesehen["kontext"] = kontext
        return mock_uc2(frage, kontext)

    ergebnis = durchreichen("Wie viele Beschäftigte?", adapter={**adapter, "uc2": uc2})
    assert [a.uc for a in ergebnis.antworten] == ["uc3", "uc2", "uc1"]
    assert ergebnis.fehlend == []
    assert [a.uc for a in gesehen["kontext"]] == ["uc3"]
    assert ergebnis.antworten[1].zahlen[0].wert == ergebnis.antworten[0].zahlen[0].wert


def test_drei_protokollzeilen_ohne_fragetext(protokoll):
    durchreichen("ping-7f3a", adapter=mock_adapter())
    text = protokoll.read_text(encoding="utf-8")
    assert len(text.splitlines()) == 3
    assert text.count("ping-7f3a") == 0


def test_fehlender_adapter_steht_in_fehlend_und_kette_laeuft_weiter(protokoll):
    adapter = mock_adapter()
    del adapter["uc2"]
    ergebnis = durchreichen("Wie viele Beschäftigte?", adapter=adapter)
    assert ergebnis.fehlend == ["uc2"]
    assert [a.uc for a in ergebnis.antworten] == ["uc3", "uc1"]


def test_import_plattform_laedt_router_nicht():
    lauf = subprocess.run(
        [sys.executable, "-c", "import sys, plattform; print('plattform.router' in sys.modules)"],
        capture_output=True,
        text=True,
        timeout=60,
        check=True,
    )
    assert lauf.stdout.strip() == "False"
