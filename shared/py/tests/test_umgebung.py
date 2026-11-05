"""`.env.local` muss gegen geerbte Shell-Variablen gewinnen (sonst rechnet ein Lauf still mit altem Wert)."""

import os

from plattform.umgebung import lade_env_local


def test_env_local_ueberschreibt_geerbte_variable(tmp_path, monkeypatch):
    (tmp_path / ".git").mkdir()
    (tmp_path / ".env.local").write_text("KIC_TESTWERT=aus-datei\n", encoding="utf-8")
    unterordner = tmp_path / "uc3" / "statagent"
    unterordner.mkdir(parents=True)
    monkeypatch.delenv("KIC_ENV_DATEI", raising=False)
    monkeypatch.setenv("KIC_TESTWERT", "geerbt")

    pfad = lade_env_local(unterordner)

    assert pfad == tmp_path / ".env.local"
    assert os.environ["KIC_TESTWERT"] == "aus-datei"
