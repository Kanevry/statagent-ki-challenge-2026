"""Start über den Unterprozess (`uc2.api.start`) und die CLI-Schalter `--frage-stdin`, `--melde-fall-id`."""

from __future__ import annotations

import io
import json
import sys
import time
from pathlib import Path
from typing import Any

import psycopg
import pytest

from uc2.api.start import Startauftrag, StartFehler, UnterprozessStarter, argv_fuer
from uc2.cli import main
from uc2.verhandlung.cli import FrageFehler, pruefe_frage
from uc2.verhandlung.speicher import lies_fall

TEST_DB = "healthpolicy_test"
# Ersatz für `uv run uc2`: hält argv und stdin fest, meldet eine Fall-ID und schreibt danach mehr als einen
# Pipe-Puffer, damit ein fehlendes Wegschreiben den Kindprozess blockieren würde.
KIND = """
import json, os, sys, time
frage = sys.stdin.read() if "--frage-stdin" in sys.argv else None
with open(os.environ["UC2_TEST_AUS"], "w", encoding="utf-8") as f:
    json.dump({"argv": sys.argv[1:], "frage": frage}, f)
print("fall_id=42", flush=True)
sys.stdout.write("x" * 300000 + "\\n")
time.sleep(0.2)
"""


def test_unterprozess_meldet_fall_id_und_bekommt_frage_per_stdin(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    aus = tmp_path / "aus.json"
    monkeypatch.setenv("UC2_TEST_AUS", str(aus))
    starter = UnterprozessStarter(basis=(sys.executable, "-c", KIND), cwd=tmp_path, timeout_s=20)
    auftrag = Startauftrag("wartezeiten", "mock", "fixture", "Frage mit Umlaut ä")
    lauf = starter(auftrag)
    assert lauf.fall_id == 42
    frist = time.monotonic() + 20
    while lauf.laeuft() and time.monotonic() < frist:
        time.sleep(0.05)
    assert not lauf.laeuft() and lauf.prozess.returncode == 0
    festgehalten = json.loads(aus.read_text(encoding="utf-8"))
    assert festgehalten == {"argv": argv_fuer(auftrag, ()), "frage": "Frage mit Umlaut ä"}


def test_unterprozess_ohne_fall_id_ist_startfehler(tmp_path: Path) -> None:
    starter = UnterprozessStarter(basis=(sys.executable, "-c", "import sys; sys.exit(3)"), cwd=tmp_path)
    with pytest.raises(StartFehler, match="Exit 3"):
        starter(Startauftrag("wartezeiten", "mock", "fixture"))


def test_pruefe_frage() -> None:
    assert pruefe_frage("  Wie\n\tsinken  Wartezeiten? ") == "Wie sinken Wartezeiten?"
    assert len(pruefe_frage("x" * 500)) == 500
    for kaputt in ("", "   ", "x" * 501, "a\x07b", "a‮b"):
        with pytest.raises(FrageFehler):
            pruefe_frage(kaputt)


def test_cli_frage_stdin_und_fall_id_als_erste_zeile(
    pg_test: psycopg.Connection[Any],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    monkeypatch.delenv("UC2_DATABASE_URL", raising=False)
    monkeypatch.delenv("UC2_MOCK_KAPUTT", raising=False)
    monkeypatch.setenv("UC2_DB", TEST_DB)
    monkeypatch.setenv("PLATTFORM_PROTOKOLL", str(tmp_path / "modellaufrufe.jsonl"))
    monkeypatch.setattr(sys, "stdin", io.StringIO("Eigene  Frage\nzu Wartezeiten?"))
    code = main(
        [
            "verhandlung",
            "--fall",
            "wartezeiten",
            "--provider",
            "mock",
            "--frage-stdin",
            "--melde-fall-id",
            "--json",
        ]
    )
    assert code == 0
    erste, _, rest = capsys.readouterr().out.partition("\n")
    assert erste.startswith("fall_id=")
    fall_id = int(erste.removeprefix("fall_id="))
    assert json.loads(rest)["fall"]["fall_id"] == fall_id
    fall = lies_fall(pg_test, fall_id)
    assert fall is not None and fall["frage"] == "Eigene Frage zu Wartezeiten?" and fall["status"] == "fertig"


def test_cli_lehnt_kaputte_frage_ab(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(sys, "stdin", io.StringIO("a\x00b"))
    assert main(["verhandlung", "--fall", "wartezeiten", "--provider", "mock", "--frage-stdin"]) == 2
    assert "Steuerzeichen" in capsys.readouterr().err
