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
    (repo / "erzeugt").mkdir()
    (repo / ref).write_text("print('lauf')\n", encoding="utf-8")
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
        f"Vorschlag: test/{vorschlag_id}",
        "Modell: gpt-5-mini@azure",
    ]
    assert _git(repo, "show", "--name-only", "--format=", "HEAD").splitlines() == [ref]
    assert pruefe_freigegeben(conn, ref, repo) == vorschlag_id
    with pytest.raises(NichtFreigegeben):
        pruefe_freigegeben(conn, offen_ref, repo)


def test_geaenderte_datei_gilt_als_nicht_freigegeben(conn, repo):
    """Fängt: Freigabe gilt weiter, obwohl ein Agent die Datei danach umgeschrieben hat (R6d)."""
    ref = f"erzeugt/{uuid.uuid4()}.py"
    (repo / "erzeugt").mkdir()
    (repo / ref).write_text("print('freigegeben')\n", encoding="utf-8")
    vorschlag_id = _vorschlag(conn, ref=ref)
    freigeben(conn, vorschlag_id, "Bernhard Götzendorfer", repo, objekt_typ="datei")

    (repo / ref).write_text("print('nachher geändert')\n", encoding="utf-8")

    with pytest.raises(NichtFreigegeben, match="geändert"):
        pruefe_freigegeben(conn, ref, repo)


def test_fremd_gestagtes_bleibt_draussen(conn, repo):
    """Fängt: eine gestagte, nicht freigegebene Datei rutscht in den Freigabe-Commit (Regel 7/8)."""
    (repo / "fremd.txt").write_text("nicht freigegeben\n", encoding="utf-8")
    _git(repo, "add", "fremd.txt")
    vorschlag_id = _vorschlag(conn)

    freigeben(conn, vorschlag_id, "Bernhard Götzendorfer", repo)

    assert _git(repo, "show", "--name-only", "--format=", "HEAD") == ""
    assert _git(repo, "diff", "--cached", "--name-only") == "fremd.txt"


def test_wiederholung_legt_keinen_zweiten_commit_an(conn, repo):
    """Fängt: zweiter Commit für denselben Vorschlag nach abgebrochener DB-Transaktion."""
    vorschlag_id = _vorschlag(conn)
    _git(
        repo, "commit", "--allow-empty", "-q", "-m", "früher", "--trailer", f"Vorschlag: test/{vorschlag_id}"
    )
    vorher = _git(repo, "rev-parse", "HEAD")

    freigabe = freigeben(conn, vorschlag_id, "Bernhard Götzendorfer", repo)

    assert _commits(repo) == 1
    assert freigabe.commit_hash == vorher


def test_gleiche_id_anderer_uc_wird_nicht_wiederverwendet(conn, repo):
    """Fängt: der Commit eines anderen UC mit derselben ID wird wiederverwendet, die Datei nie committet."""
    ref = f"uc3/erzeugt/{uuid.uuid4()}.py"
    (repo / ref).parent.mkdir(parents=True)
    (repo / ref).write_text("print('uc3')\n", encoding="utf-8")
    vorschlag_id = _vorschlag(conn, ref=ref)
    _git(repo, "commit", "--allow-empty", "-q", "-m", "uc1", "--trailer", f"Vorschlag: uc1/{vorschlag_id}")

    freigeben(conn, vorschlag_id, "Bernhard Götzendorfer", repo, objekt_typ="datei")

    assert _commits(repo) == 2
    assert _git(repo, "show", "--name-only", "--format=", "HEAD").splitlines() == [ref]
    assert pruefe_freigegeben(conn, ref, repo) == vorschlag_id


@pytest.mark.parametrize("ref", [".", "*.py", "../ausserhalb.py", "erzeugt"])
def test_datei_ref_ist_genau_eine_datei_im_repo(conn, repo, ref):
    """Fängt: ref „.“ oder ein Muster committet mehrere Dateien unter „Freigegeben-von“."""
    (repo / "erzeugt").mkdir()
    (repo / "erzeugt" / "a.py").write_text("a\n", encoding="utf-8")
    (repo / "b.py").write_text("b\n", encoding="utf-8")
    vorschlag_id = _vorschlag(conn, ref=ref)

    with pytest.raises(ValueError):
        freigeben(conn, vorschlag_id, "Bernhard Götzendorfer", repo, objekt_typ="datei")
    assert _commits(repo) == 0
    assert _status(conn, vorschlag_id) == "offen"


def test_pruefe_freigegeben_verlangt_datei_freigabe(conn, repo):
    """Fängt: ein Skript gilt als freigegeben, weil eine Regel-Freigabe denselben ref trägt."""
    ref = f"erzeugt/{uuid.uuid4()}.py"
    vorschlag_id = _vorschlag(conn, ref=ref)
    freigeben(conn, vorschlag_id, "Bernhard Götzendorfer", repo)  # objekt_typ regel

    with pytest.raises(NichtFreigegeben, match="keine Datei"):
        pruefe_freigegeben(conn, ref, repo)


def test_offene_transaktion_wird_abgelehnt(conn, repo):
    """Fängt: autocommit=True, aber der Aufrufer hat schon eine Transaktion offen (nur Savepoint)."""
    vorschlag_id = _vorschlag(conn)
    with conn.transaction(), pytest.raises(ValueError, match="offene Transaktion"):
        freigeben(conn, vorschlag_id, "Bernhard Götzendorfer", repo)


def test_verbindung_ohne_autocommit_wird_abgelehnt(repo):
    """Fängt: Freigabe läuft als Savepoint einer fremden Transaktion und wird nie festgeschrieben."""
    url = os.environ.get("PLATTFORM_TEST_DATABASE_URL")
    if not url:
        pytest.skip("PLATTFORM_TEST_DATABASE_URL nicht gesetzt: DB-Test braucht eine leere Wegwerf-DB")
    with psycopg.connect(url) as ohne, pytest.raises(ValueError, match="autocommit"):
        freigeben(ohne, 1, "Bernhard Götzendorfer", repo)


def test_parallele_freigaben_ohne_index_lock(conn, repo):
    url = os.environ["PLATTFORM_TEST_DATABASE_URL"]
    ids = [_vorschlag(conn, anweisung=f"Parallel {i}") for i in range(2)]
    start = threading.Barrier(2)
    fehler: list[BaseException] = []

    def lauf(vorschlag_id: int) -> None:
        try:
            with psycopg.connect(url, autocommit=True) as eigene:
                start.wait()
                freigeben(eigene, vorschlag_id, "Anna Huber", repo)
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
        freigeben(conn, vorschlag_id, "Anna Huber", ziel)

    assert _status(conn, vorschlag_id) == "offen"
    anzahl = conn.execute("SELECT count(*) FROM meta.freigabe WHERE protokoll_id = %s", (vorschlag_id,))
    assert anzahl.fetchone()[0] == 0
    assert _commits(repo) == 0
