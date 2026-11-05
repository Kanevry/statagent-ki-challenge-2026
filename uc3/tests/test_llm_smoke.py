"""Adapter-Smoke (Issue #13, AC4): UC3 nutzt ``plattform.llm`` nur über Vertrag M, ``uc3 lauf`` bleibt offline."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest


def test_complete_mit_mock_fuer_agent_koordinator(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from plattform.llm import complete, mock

    (tmp_path / "agent.koordinator.json").write_text(
        json.dumps({"modell": "mock", "antworten": [{"text": "bereit"}]}), encoding="utf-8"
    )
    protokoll = tmp_path / "modellaufrufe.jsonl"
    monkeypatch.setenv("PLATTFORM_FIXTURES", str(tmp_path))
    monkeypatch.setenv("PLATTFORM_PROTOKOLL", str(protokoll))
    mock.zuruecksetzen()

    antwort = complete([{"role": "user", "content": "Smoke"}], provider="mock", zweck="agent.koordinator")

    assert antwort.text == "bereit"
    assert antwort.provider == "mock"
    zeilen = protokoll.read_text(encoding="utf-8").splitlines()
    assert len(zeilen) == 1
    assert json.loads(zeilen[0])["zweck"] == "agent.koordinator"


def test_lauf_laedt_kein_modell() -> None:
    """Regel R2: ``statagent.lauf`` und die CLI (Befehl ``lauf``) laden ``plattform.llm`` nicht."""
    code = (
        "import sys, statagent.cli, statagent.lauf; "
        "print(sorted(m for m in sys.modules if m == 'plattform.llm' or m.startswith('plattform.llm.')))"
    )
    ergebnis = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=True)
    assert ergebnis.stdout.strip() == "[]"
