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


def test_datenbank_url_gewinnt_und_db_name_ersetzt_nur_den_namen(monkeypatch: pytest.MonkeyPatch) -> None:
    from psycopg.conninfo import conninfo_to_dict

    from uc2 import db

    monkeypatch.setenv("UC2_DATABASE_URL", "postgresql://nutzer:geheim@dbhost:6543/healthpolicy")
    monkeypatch.setenv("PGHOST", "anderer")
    standard = conninfo_to_dict(db.conninfo())
    assert (standard["host"], standard["port"], standard["dbname"]) == ("dbhost", "6543", "healthpolicy")
    test = conninfo_to_dict(db.conninfo("healthpolicy_test"))
    assert (test["host"], test["dbname"]) == ("dbhost", "healthpolicy_test")
