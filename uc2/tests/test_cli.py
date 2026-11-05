from __future__ import annotations

import pytest

from uc2.cli import main


def test_hilfe_laeuft(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as ende:
        main(["--help"])
    assert ende.value.code == 0
    assert "uc2" in capsys.readouterr().out


def test_ohne_befehl_zeigt_hilfe() -> None:
    assert main([]) == 2
