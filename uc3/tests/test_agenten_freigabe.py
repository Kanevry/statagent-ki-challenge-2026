"""Freigabe mit Namen, Git-Commit mit Trailer, Anwenden und der Start erzeugter Code-Dateien.

Git läuft nur in einem Wegwerf-Repo unter tmp_path. ``fake_freigeben`` bildet Vertrag P mit dem Nachtrag
zu !6 nach: Verbindung mit autocommit ohne offene Transaktion, meta.freigabe und Commit in einer
Transaktion, Trailer ``Vorschlag: uc3/<id>``, bei Dateien ``commit --only`` genau dieser Datei.
"""

from __future__ import annotations

import subprocess
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from plattform.freigabe import ablehnen as plattform_ablehnen
from plattform.freigabe import freigeben as plattform_freigeben
from psycopg import pq

from statagent.agenten.anwenden import (
    NichtFreigegeben,
    ablehnen_ausfuehren,
    anwenden,
    datei_ablegen,
    erzeugt_ausfuehren,
    freigabe_ausfuehren,
)
from statagent.agenten.vorschlag import (
    CodeDateiEntwurf,
    vorschlag_anlegen,
    vorschlag_lesen,
    vorschlag_schema_einrichten,
)
from statagent.db import Verbindung
from statagent.ergebnis import monatswerte
from statagent.lauf import lauf_ausfuehren
from statagent.regeln import NameUngueltig

ANWEISUNG = "Zählt freie Dienstverträge mit den Dienstverträgen zusammen"
NAME = "Lena Gruber"
R6_ALT = {"qualifikation": "code"}
R6_NEU = {"qualifikation": "beschaeftigungskategorie"}


def git(repo: Path, *argumente: str) -> str:
    return subprocess.run(
        ["git", "-C", str(repo), *argumente], check=True, capture_output=True, text=True
    ).stdout.strip()


class FakeFreigabe:
    """Ruft das echte ``plattform.freigabe.freigeben`` (Vertrag P) auf, zählt Aufrufe und kann einen Git-Fehler
    vortäuschen (dann ändert sich nichts)."""

    def __init__(self, scheitern: bool = False) -> None:
        self.scheitern = scheitern
        self.aufrufe = 0

    def __call__(self, conn: Verbindung, vorschlag_id: int, name: str, repo_pfad: Path, **kwargs: Any) -> Any:
        self.aufrufe += 1
        assert conn.autocommit and conn.info.transaction_status == pq.TransactionStatus.IDLE
        if self.scheitern:
            raise subprocess.CalledProcessError(128, ["git", "commit"])
        return plattform_freigeben(conn, vorschlag_id, name, repo_pfad, **kwargs)


def fake_ablehnen(conn: Verbindung, vorschlag_id: int, name: str, begruendung: str) -> Any:
    return plattform_ablehnen(conn, vorschlag_id, name, begruendung)


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    pfad = tmp_path / "repo"
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


@pytest.fixture
def agent_conn(conn: Verbindung) -> Iterator[Verbindung]:
    # meta.protokoll/meta.freigabe kommen aus plattform/sql/meta.sql (Vertrag P), eingespielt von db init.
    vorschlag_schema_einrichten(conn)
    yield conn


def r6_vorschlag(conn: Verbindung) -> int:
    return vorschlag_anlegen(
        conn,
        anweisung=ANWEISUNG,
        rolle="klassifikation",
        typ="regel_aendern",
        regelsatz_ziel="v2",
        regelsatz_basis="v1",
        begruendung="Änderungsauftrag 1",
        aenderungen=[
            {"regel_name": "R6_beschaeftigungskategorie", "parameter_alt": R6_ALT, "parameter_neu": R6_NEU}
        ],
        modell="fake-1",
        provider="mock",
    )


def regel(conn: Verbindung, regelsatz: str, name: str) -> dict[str, Any] | None:
    return conn.execute(
        "SELECT parameter, freigegeben_von FROM meta.regel WHERE regelsatz = %s AND name = %s",
        (regelsatz, name),
    ).fetchone()


def commits(repo: Path) -> int:
    return int(git(repo, "rev-list", "--count", "HEAD"))


def test_team_ist_kein_name(agent_conn: Verbindung, repo: Path) -> None:
    vid = r6_vorschlag(agent_conn)
    freigabe = FakeFreigabe()
    with pytest.raises(NameUngueltig):
        freigabe_ausfuehren(agent_conn, vid, "Team", repo, freigeben=freigabe)
    assert freigabe.aufrufe == 0 and commits(repo) == 1
    assert vorschlag_lesen(agent_conn, vid).status == "offen"
    assert regel(agent_conn, "v2", "R6_beschaeftigungskategorie") is None


def test_freigabe_mit_namen_aendert_regel_und_committet_mit_trailer(
    agent_conn: Verbindung, repo: Path
) -> None:
    conn = agent_conn
    vid = r6_vorschlag(conn)
    ergebnis = freigabe_ausfuehren(conn, vid, "  Lena   Gruber ", repo, freigeben=FakeFreigabe())

    assert ergebnis.angewendet and ergebnis.fehler is None and ergebnis.name == NAME
    v = vorschlag_lesen(conn, vid)
    assert (v.status, v.zustand, v.freigegeben_von) == ("freigegeben", "freigegeben, angewendet", NAME)
    assert v.commit_hash == git(repo, "rev-parse", "HEAD") == ergebnis.commit_hash
    assert regel(conn, "v2", "R6_beschaeftigungskategorie") == {"parameter": R6_NEU, "freigegeben_von": NAME}
    assert regel(conn, "v1", "R6_beschaeftigungskategorie")["parameter"] == R6_ALT  # type: ignore[index]
    # Die Kopie der übrigen Regeln kommt ohne Freigabe in v2 an.
    assert regel(conn, "v2", "R5_alter") == {
        "parameter": regel(conn, "v1", "R5_alter")["parameter"],  # type: ignore[index]
        "freigegeben_von": None,
    }
    f = conn.execute(
        "SELECT name, entscheidung, objekt_typ FROM meta.freigabe WHERE protokoll_id = %s", (vid,)
    )
    assert f.fetchall() == [{"name": NAME, "entscheidung": "ja", "objekt_typ": "regel"}]

    log = git(repo, "log", "-1", "--format=%s%n%(trailers)")
    assert log.splitlines()[0] == ANWEISUNG
    assert (
        f"Freigegeben-von: {NAME}" in log and f"Vorschlag: uc3/{vid}" in log and "Modell: fake-1@mock" in log
    )

    lauf_ausfuehren(conn, "2024-08", "v2", reihenfolge_pruefen=False)
    assert {str(z["qualifikation"]) for z in monatswerte(conn, "2024-08", "v2")} <= {
        "Angestellte",
        "Arbeiter",
        "Beamte",
    }


def test_scheitert_der_commit_bleibt_alles_wie_vorher(agent_conn: Verbindung, repo: Path) -> None:
    vid = r6_vorschlag(agent_conn)
    with pytest.raises(subprocess.CalledProcessError):
        freigabe_ausfuehren(agent_conn, vid, NAME, repo, freigeben=FakeFreigabe(scheitern=True))
    assert vorschlag_lesen(agent_conn, vid).status == "offen" and commits(repo) == 1
    assert regel(agent_conn, "v2", "R6_beschaeftigungskategorie") is None
    assert agent_conn.execute("SELECT count(*) AS n FROM meta.freigabe").fetchone() == {"n": 0}


def test_scheitert_das_anwenden_bleibt_die_freigabe_und_anwenden_ist_wiederholbar(
    agent_conn: Verbindung, repo: Path
) -> None:
    conn = agent_conn
    vid = r6_vorschlag(conn)
    # Jemand hat v2 inzwischen angelegt und R6 dort anders gesetzt: Konflikt beim Anwenden.
    with conn.transaction():
        conn.execute(
            """INSERT INTO meta.regel (regelsatz, name, typ, art, reihenfolge, parameter, beschreibung, begruendung,
                                       grundlage)
               SELECT 'v2', name, typ, art, reihenfolge, parameter, beschreibung, begruendung, grundlage
               FROM meta.regel WHERE regelsatz = 'v1' AND aktiv"""
        )
        conn.execute(
            """UPDATE meta.regel SET parameter = '{"qualifikation": "anders"}'
               WHERE regelsatz = 'v2' AND name = 'R6_beschaeftigungskategorie'"""
        )

    ergebnis = freigabe_ausfuehren(conn, vid, NAME, repo, freigeben=FakeFreigabe())
    assert not ergebnis.angewendet and ergebnis.fehler == "RegelKonflikt"
    v = vorschlag_lesen(conn, vid)
    assert v.zustand == "freigegeben, nicht angewendet (RegelKonflikt)" and v.commit_hash is not None
    assert commits(repo) == 2

    with conn.transaction():
        conn.execute(
            """UPDATE meta.regel SET parameter = '{"qualifikation": "code"}'
               WHERE regelsatz = 'v2' AND name = 'R6_beschaeftigungskategorie'"""
        )
    assert anwenden(conn, vid).zustand == "freigegeben, angewendet"
    assert anwenden(conn, vid).anwenden_fehler is None  # zweites Mal: nichts zu tun
    assert regel(conn, "v2", "R6_beschaeftigungskategorie") == {"parameter": R6_NEU, "freigegeben_von": NAME}
    assert commits(repo) == 2


def test_ablehnen_aendert_nichts(agent_conn: Verbindung, repo: Path) -> None:
    vid = r6_vorschlag(agent_conn)
    v = ablehnen_ausfuehren(agent_conn, vid, NAME, repo, begruendung="nicht gewollt", ablehnen=fake_ablehnen)
    assert (v.status, v.abgelehnt_von, v.ablehnungsgrund) == ("abgelehnt", NAME, "nicht gewollt")
    assert regel(agent_conn, "v2", "R6_beschaeftigungskategorie") is None and commits(repo) == 1


RUMPF = """def run(conn, lieferung):
    z = conn.execute(
        "SELECT count(*) AS n FROM roh.lieferung WHERE lieferung = %s", (lieferung,)
    ).fetchone()
    return {"lieferung": lieferung, "saetze": z["n"]}
"""


def test_code_datei_laeuft_nur_mit_freigabe_genau_dieses_inhalts(agent_conn: Verbindung, repo: Path) -> None:
    conn = agent_conn
    vid = vorschlag_anlegen(
        conn,
        anweisung="Ministeriums-Lieferung als Sonderauswertung",
        rolle="reporting",
        typ="code_datei",
        regelsatz_ziel="v2",
        regelsatz_basis="v1",
        begruendung="Änderungsauftrag 3",
        datei=CodeDateiEntwurf(name="ministerium_probe", endung=".py", rumpf=RUMPF),
        modell="fake-1",
        provider="mock",
    )
    v = vorschlag_lesen(conn, vid)
    assert v.datei_pfad == f"uc3/erzeugt/{vid}_ministerium_probe.py"
    datei = repo / v.datei_pfad
    assert datei_ablegen(v, repo)
    assert datei.read_text(encoding="utf-8").startswith("# Erzeugt von StatAgent (Rolle reporting)")

    with pytest.raises(NichtFreigegeben):
        erzeugt_ausfuehren(conn, datei, "2024-08", repo_pfad=repo)

    ergebnis = freigabe_ausfuehren(conn, vid, NAME, repo, freigeben=FakeFreigabe())
    assert ergebnis.angewendet
    assert git(repo, "show", "--name-only", "--format=", "HEAD") == v.datei_pfad
    assert f"Vorschlag: uc3/{vid}" in git(repo, "log", "-1", "--format=%(trailers)")
    gezaehlt = conn.execute("SELECT count(*) AS n FROM roh.lieferung WHERE lieferung = '2024-08'").fetchone()
    assert erzeugt_ausfuehren(conn, datei, "2024-08", repo_pfad=repo) == {
        "lieferung": "2024-08",
        "saetze": gezaehlt["n"] if gezaehlt else None,
    }

    datei.write_text(datei.read_text(encoding="utf-8") + "# nachträglich geändert\n", encoding="utf-8")
    with pytest.raises(NichtFreigegeben):
        erzeugt_ausfuehren(conn, datei, "2024-08", repo_pfad=repo)
