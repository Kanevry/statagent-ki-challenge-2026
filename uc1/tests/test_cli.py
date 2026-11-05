from __future__ import annotations

from pathlib import Path

import pytest

from uc1 import cli, config


def test_unbekannter_befehl_endet_mit_2(capsys: pytest.CaptureFixture[str]) -> None:
    assert cli.main(["gibtsnicht"]) == 2
    assert "unbekannter Befehl" in capsys.readouterr().err


def test_ungebauter_befehl_meldet_sich_statt_abzustuerzen(capsys: pytest.CaptureFixture[str]) -> None:
    assert cli.main(["antrag"]) == 2
    assert "noch nicht gebaut" in capsys.readouterr().err


def test_daten_dir_fehlt_ist_fehler(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("UC1_DATA_DIR", raising=False)
    with pytest.raises(config.KonfigFehler, match="nicht gesetzt"):
        config.daten_dir()


def test_daten_dir_leer_ist_fehler(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("UC1_DATA_DIR", str(tmp_path))
    with pytest.raises(config.KonfigFehler, match="leer"):
        config.daten_dir()
