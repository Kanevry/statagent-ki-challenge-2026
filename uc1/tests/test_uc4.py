"""Tests für uc1.uc4 (Issue #107) ohne Netz und ohne DB: Modell injiziert oder mock-Provider
(PLATTFORM_FIXTURES=tests/fixtures/llm/uc4), Demo-Kontext „Wartezeiten“ (erfunden)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from uc1 import kern, uc4
from uc1.eval import mittlere_satzlaenge

FIXTURES = Path(__file__).resolve().parent / "fixtures"
FRAGE = "Wie lange warte ich auf eine Reha?"


def kontext() -> dict[str, Any]:
    daten: dict[str, Any] = json.loads((FIXTURES / "uc4-wartezeiten.json").read_text(encoding="utf-8"))
    return daten


def modell_mit(*saetze: str) -> Any:
    aufrufe: list[int] = []

    def fn(
        nachrichten: list[dict[str, str]], schema: dict[str, Any], provider: str | None
    ) -> kern.ModellErgebnis:
        aufrufe.append(1)
        return kern.ModellErgebnis(
            json={"saetze": list(saetze)}, provider="test", modell="skript", dauer_ms=0
        )

    fn.aufrufe = aufrufe  # type: ignore[attr-defined]
    return fn


def test_zahlen_und_belege_bleiben_unveraendert_ueber_mock(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Fängt einen Adapter, der Zahlen rundet, Beleg-Indizes verschiebt oder Belege umschreibt (#107 AC 1)."""
    from plattform.llm import mock

    monkeypatch.setenv("PLATTFORM_FIXTURES", str(FIXTURES / "llm" / "uc4"))
    monkeypatch.setenv("PLATTFORM_PROTOKOLL", str(tmp_path / "protokoll.jsonl"))
    mock.zuruecksetzen()
    ktx = kontext()
    a = uc4.antwort(FRAGE, ktx, provider="mock")
    assert set(a) == set(uc4.UcAntwort.model_fields)
    assert a["uc"] == "uc1" and a["modell"] == "mock" and a["protokoll_id"] is None
    assert a["belege"] == [uc4.Beleg.model_validate(b).model_dump() for b in ktx["belege"]]
    assert [(z["wert"], z["beleg"]) for z in a["zahlen"]] == [(19.6, 0), (23.1, 1)]
    assert "19,6" in a["text"] and "23,1" in a["text"]
    assert mittlere_satzlaenge(a["text"]) < 15
    uc4.UcAntwort.model_validate(a)


def test_veraenderte_zahl_wird_abgefangen() -> None:
    """Fängt „rund 20“ statt „19,6“: der Satz mit der gerundeten Zahl fällt weg, die echte steht da."""
    modell = modell_mit(
        "Sie warten jetzt kürzer.", "Im August waren es rund 20 Tage.", "Im Juli waren es 23,1 Tage."
    )
    a = uc4.antwort(FRAGE, kontext(), modell=modell)
    assert "rund 20" not in a["text"] and "20 Tage" not in a["text"]
    assert "19,6 Tage" in a["text"] and "23,1 Tage" in a["text"]
    assert [z["wert"] for z in a["zahlen"]] == [19.6, 23.1]


def test_grenzfrage_ergibt_grenzantwort_ohne_modell() -> None:
    """Fängt einen Adapter, der eine Diagnosefrage ans Modell gibt oder Statistik dazu erklärt (#107 AC 2)."""
    modell = modell_mit("Das sollte nie erscheinen.")
    a = uc4.antwort("Ich habe Fieber und Ausschlag, was habe ich?", kontext(), modell=modell)
    assert modell.aufrufe == [] and a["uc"] == "uc1" and a["zahlen"] == [] and a["belege"] == []
    assert "Diagnose" in a["text"]


def test_beleg_index_ohne_beleg_wird_abgelehnt() -> None:
    """Fängt einen Kontext, dessen Zahl auf einen fehlenden Beleg zeigt (Vertrag #96)."""
    ktx = kontext()
    ktx["zahlen"][1]["beleg"] = 5
    with pytest.raises(ValueError, match="Beleg-Index"):
        uc4.antwort(FRAGE, ktx, modell=modell_mit("egal"))


@pytest.mark.parametrize(
    ("wert", "text"), [(19.6, "19,6"), (1234, "1.234"), (12345.5, "12.345,5"), ("19,6", "19,6")]
)
def test_anzeige_rundet_nicht(wert: Any, text: str) -> None:
    """Fängt eine Schreibweise, die rundet oder das Dezimalkomma verliert."""
    assert uc4.anzeige(uc4.Zahl(bezeichnung="x", wert=wert, beleg=0)) == text


def test_modelltext_wird_geglaettet() -> None:
    """Fängt einen UC4-Text mit Em-Dash oder Floskel des Modells, der ungeglättet rausgeht (uc1.sprache)."""
    modell = modell_mit(
        "Gerne helfe ich Ihnen.", "Sie warten jetzt kürzer — im Median 19,6 Tage.", "Vorher 23,1 Tage."
    )
    a = uc4.antwort(FRAGE, kontext(), modell=modell)
    assert "—" not in a["text"] and "Gerne" not in a["text"]
    assert a["text"].startswith("Sie warten jetzt kürzer, im Median 19,6 Tage.")
    assert all(b["uc"] == "uc3" for b in a["belege"])
