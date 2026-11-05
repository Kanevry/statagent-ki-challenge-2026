"""export --md (#55): eine Tabellenzeile je Freigabe-Commit und je meta.protokoll-Eintrag."""

import os
import subprocess
import sys
import uuid

import psycopg
import pytest
from plattform.freigabe import ablehnen, freigeben
from plattform.protokoll import ddl_einspielen, schreibe


def _git(repo, *argumente):
    return subprocess.run(
        ["git", "-C", str(repo), *argumente], capture_output=True, text=True, check=True
    ).stdout


def test_export_md_zaehlt_commits_und_eintraege(tmp_path):
    url = os.environ.get("PLATTFORM_TEST_DATABASE_URL")
    if not url:
        pytest.skip("PLATTFORM_TEST_DATABASE_URL nicht gesetzt: DB-Test braucht eine leere Wegwerf-DB")
    repo = tmp_path / "repo"
    repo.mkdir()
    (tmp_path / "hooks").mkdir()
    _git(repo, "init", "-q", "-b", "main")
    for schluessel, wert in [
        ("user.name", "Test"),
        ("user.email", "test@example.org"),
        ("commit.gpgsign", "false"),
        ("core.hooksPath", str(tmp_path / "hooks")),
    ]:
        _git(repo, "config", schluessel, wert)
    _git(repo, "commit", "--allow-empty", "-q", "-m", "Gerüst ohne Freigabe")
    uc = f"t{uuid.uuid4().hex[:8]}"
    with psycopg.connect(url, autocommit=True) as conn:
        ddl_einspielen(conn)
        ids = [
            schreibe(
                conn,
                {
                    "uc": uc,
                    "akteur": "agent",
                    "name": "regel-agent",
                    "anweisung": f"Regel | {i}",
                    "vorschlag_typ": "regel",
                    "ref": f"regel:{uc}:{i}",
                },
            )
            for i in range(3)
        ]
        freigeben(conn, ids[0], "Anna Huber", repo)
        freigeben(conn, ids[1], "Jakob Gruber", repo)
        ablehnen(conn, ids[2], "Anna Huber", "widerspricht Regel R2")

    ziel = tmp_path / "protokoll.md"
    subprocess.run(
        [
            sys.executable,
            "-m",
            "plattform.protokoll",
            "export",
            "--md",
            "--repo",
            str(repo),
            "--db",
            url,
            "--uc",
            uc,
            "--out",
            str(ziel),
        ],
        check=True,
        capture_output=True,
    )

    trailer = _git(repo, "log", "--format=%(trailers:key=Freigegeben-von,valueonly)")
    ablehnungen = 1
    erwartet = len([z for z in trailer.splitlines() if z.strip()]) + ablehnungen + len(ids)
    zeilen = [z for z in ziel.read_text(encoding="utf-8").splitlines() if z.startswith("| ")]
    kopfzeilen = 3  # je Tabelle eine Kopfzeile; Trennzeilen beginnen mit "|---"
    assert len(zeilen) - kopfzeilen == erwartet == 6
