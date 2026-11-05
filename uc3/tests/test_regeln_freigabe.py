"""`uc3 regeln freigeben --name` über Vertrag P (Review !13 Runde 3, Punkt 1).

Der CLI-Pfad übergibt `repo_pfad`; `plattform.freigabe.freigeben` liest Tupelzeilen und committet. Git nur in
einem Wegwerf-Repo unter tmp_path (konfig.REPO_WURZEL wird umgebogen), nie im echten Repo.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from test_agenten_freigabe import NAME, git
from typer.testing import CliRunner

from statagent import cli, konfig
from statagent.db import Verbindung, verbinden

runner = CliRunner()


@pytest.fixture
def cli_db(conn: Verbindung, arbeits_db: str, monkeypatch: pytest.MonkeyPatch) -> Verbindung:
    monkeypatch.setattr(cli, "verbinden", lambda: verbinden(arbeits_db))
    return conn


def _repo(pfad: Path) -> Path:
    pfad.mkdir()
    git(pfad, "init", "-q", "-b", "main")
    for schluessel, wert in (
        ("user.name", "Test Lauf"),
        ("user.email", "test@example.org"),
        ("commit.gpgsign", "false"),
        ("core.hooksPath", str(pfad / ".git" / "keine-hooks")),
    ):
        git(pfad, "config", schluessel, wert)
    git(pfad, "commit", "-q", "--allow-empty", "-m", "Start")
    return pfad


def _offen(conn: Verbindung) -> int:
    z = conn.execute(
        "SELECT count(*) AS n FROM meta.regel WHERE regelsatz = 'v1' AND aktiv AND freigegeben_von IS NULL"
    ).fetchone()
    assert z is not None
    return int(str(z["n"]))


def _protokoll_status(conn: Verbindung) -> list[str]:
    return [
        str(z["status"])
        for z in conn.execute(
            "SELECT status FROM meta.protokoll WHERE uc = 'uc3' AND vorschlag_typ = 'regel' ORDER BY id"
        ).fetchall()
    ]


# Fängt: freigeben() mit dict-Zeilen (KeyError: 6 in _offener_vorschlag), d. h. die Freigabe über die CLI
# bricht immer ab; dazu fehlender Commit-Trailer oder Regeln, die trotz Freigabe offen bleiben.
def test_regeln_freigeben_ueber_cli_committet_mit_trailer(
    cli_db: Verbindung, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = _repo(tmp_path / "repo")
    monkeypatch.setattr(konfig, "REPO_WURZEL", repo)
    assert _offen(cli_db) > 0

    ergebnis = runner.invoke(cli.app, ["regeln", "freigeben", "--name", NAME])

    assert ergebnis.exit_code == 0, ergebnis.output
    assert _offen(cli_db) == 0
    assert _protokoll_status(cli_db) == ["freigegeben"]
    trailer = git(repo, "log", "-1", "--format=%(trailers:key=Freigegeben-von,valueonly)").strip()
    assert trailer == NAME


# Fängt: scheitert die Freigabe (hier: kein Git-Repo), bleibt ein verwaister Protokolleintrag „offen“ liegen
# oder Regeln werden trotzdem freigegeben.
def test_gescheiterte_freigabe_schliesst_protokoll_und_gibt_nichts_frei(
    cli_db: Verbindung, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    kein_repo = tmp_path / "kein-repo"
    kein_repo.mkdir()
    monkeypatch.setattr(konfig, "REPO_WURZEL", kein_repo)
    vorher = _offen(cli_db)

    ergebnis = runner.invoke(cli.app, ["regeln", "freigeben", "--name", NAME])

    assert ergebnis.exit_code != 0
    assert _offen(cli_db) == vorher
    assert _protokoll_status(cli_db) == ["abgelehnt"]
