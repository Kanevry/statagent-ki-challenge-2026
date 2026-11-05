"""Freigabe (Vertrag P, #55): Namensregel, Commit mit Trailern, Lock, Rollback, Regel R6d."""

import json
import os
import subprocess
import threading
import uuid
from pathlib import Path

import psycopg
import pytest
from plattform.freigabe import GitFehler, NameUngueltig, NichtFreigegeben, freigeben, pruefe_freigegeben
from plattform.protokoll import ddl_einspielen, schreibe

SPERRNAMEN = json.loads((Path(__file__).with_name("sperrnamen.json")).read_text(encoding="utf-8"))


@pytest.fixture
def conn():
    url = os.environ.get("PLATTFORM_TEST_DATABASE_URL")
    if not url:
        pytest.skip("PLATTFORM_TEST_DATABASE_URL nicht gesetzt: DB-Test braucht eine leere Wegwerf-DB")
    with psycopg.connect(url, autocommit=True) as verbindung:
        ddl_einspielen(verbindung)
        yield verbindung


def _git(repo: Path, *argumente: str) -> str:
    return subprocess.run(
        ["git", "-C", str(repo), *argumente], capture_output=True, text=True, check=True
    ).stdout.strip()


@pytest.fixture
def repo(tmp_path):
    pfad = tmp_path / "repo"
    pfad.mkdir()
    (tmp_path / "hooks").mkdir()
    _git(pfad, "init", "-q", "-b", "main")
    _git(pfad, "config", "user.name", "Test")
    _git(pfad, "config", "user.email", "test@example.org")
    _git(pfad, "config", "commit.gpgsign", "false")
    _git(pfad, "config", "core.hooksPath", str(tmp_path / "hooks"))
    return pfad


def _commits(repo: Path) -> int:
    return int(_git(repo, "rev-list", "--all", "--count"))


def _vorschlag(conn, anweisung="Regel R1 anpassen", ref=None) -> int:
    return schreibe(
        conn,
        {
            "uc": "test",
            "akteur": "agent",
            "name": "regel-agent",
            "anweisung": anweisung,
            "vorschlag_typ": "regel",
            "modell": "gpt-5-mini",
            "provider": "azure",
            "ref": ref or f"regel:{uuid.uuid4()}",
        },
    )


def _status(conn, vorschlag_id: int) -> str:
    return conn.execute("SELECT status FROM meta.protokoll WHERE id = %s", (vorschlag_id,)).fetchone()[0]


@pytest.mark.parametrize("name", SPERRNAMEN)
def test_sperrname_abgelehnt_ohne_commit(conn, repo, name):
    vorschlag_id = _vorschlag(conn)
    with pytest.raises(NameUngueltig):
        freigeben(conn, vorschlag_id, name, repo)
    assert _commits(repo) == 0
    assert _status(conn, vorschlag_id) == "offen"


def test_freigeben_schreibt_db_und_commit(conn, repo):
    ref = f"erzeugt/{uuid.uuid4()}.py"
    vorschlag_id = _vorschlag(conn, anweisung="X", ref=ref)
    offen_id = _vorschlag(conn)
    offen_ref = conn.execute("SELECT ref FROM meta.protokoll WHERE id = %s", (offen_id,)).fetchone()[0]

    freigabe = freigeben(conn, vorschlag_id, "Bernhard Götzendorfer", repo, objekt_typ="datei")

    zeile = conn.execute(
        "SELECT name, zeitpunkt, objekt_typ, objekt_ref, entscheidung FROM meta.freigabe"
        " WHERE protokoll_id = %s",
        (vorschlag_id,),
    ).fetchall()
    assert len(zeile) == 1
    name, zeitpunkt, objekt_typ, objekt_ref, entscheidung = zeile[0]
    assert (name, objekt_typ, objekt_ref, entscheidung) == ("Bernhard Götzendorfer", "datei", ref, "ja")
    assert zeitpunkt is not None
    status, commit_hash = conn.execute(
        "SELECT status, commit_hash FROM meta.protokoll WHERE id = %s", (vorschlag_id,)
    ).fetchone()
    assert status == "freigegeben"
    assert commit_hash == freigabe.commit_hash == _git(repo, "rev-parse", "HEAD")
    assert _git(repo, "log", "-1", "--format=%s") == "X"
    assert _git(repo, "log", "-1", "--format=%(trailers)").splitlines() == [
        "Freigegeben-von: Bernhard Götzendorfer",
        f"Vorschlag: {vorschlag_id}",
        "Modell: gpt-5-mini@azure",
    ]
    assert pruefe_freigegeben(conn, ref) == vorschlag_id
    with pytest.raises(NichtFreigegeben):
        pruefe_freigegeben(conn, offen_ref)


def test_parallele_freigaben_ohne_index_lock(conn, repo):
    url = os.environ["PLATTFORM_TEST_DATABASE_URL"]
    ids = [_vorschlag(conn, anweisung=f"Parallel {i}") for i in range(2)]
    start = threading.Barrier(2)
    fehler: list[BaseException] = []

    def lauf(vorschlag_id: int) -> None:
        try:
            with psycopg.connect(url, autocommit=True) as eigene:
                start.wait()
                freigeben(eigene, vorschlag_id, "Erika Musterfrau", repo)
        except BaseException as f:  # noqa: B036 - Fehler im Thread an den Test weiterreichen
            fehler.append(f)

    threads = [threading.Thread(target=lauf, args=(i,)) for i in ids]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=60)
    assert fehler == []
    assert _commits(repo) == 2
    assert {_status(conn, i) for i in ids} == {"freigegeben"}


@pytest.mark.parametrize("fall", ["kein_repo", "hook_scheitert"])
def test_git_fehler_rollt_db_zurueck(conn, repo, tmp_path, fall):
    vorschlag_id = _vorschlag(conn)
    ziel = repo
    if fall == "kein_repo":
        ziel = tmp_path / "kein-repo"
        ziel.mkdir()
    else:  # Git scheitert erst nach den DB-Schreibvorgängen in der Transaktion
        hook = tmp_path / "hooks" / "pre-commit"
        hook.write_text("#!/bin/sh\nexit 1\n", encoding="utf-8")
        hook.chmod(0o755)

    with pytest.raises(GitFehler):
        freigeben(conn, vorschlag_id, "Erika Musterfrau", ziel)

    assert _status(conn, vorschlag_id) == "offen"
    anzahl = conn.execute("SELECT count(*) FROM meta.freigabe WHERE protokoll_id = %s", (vorschlag_id,))
    assert anzahl.fetchone()[0] == 0
    assert _commits(repo) == 0
