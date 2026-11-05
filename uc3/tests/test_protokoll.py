"""Protokoll-Export: Git-Commits mit Freigabe-Trailer und Freigaben aus der Datenbank."""

from __future__ import annotations

import subprocess
from pathlib import Path

from statagent.berichte.protokoll import freigabe_commits, protokoll_erzeugen
from statagent.db import Verbindung
from statagent.lauf import lauf_ausfuehren, veroeffentlichen
from statagent.regeln import regeln_freigeben


def _git(repo: Path, *argumente: str) -> None:
    subprocess.run(["git", "-C", str(repo), *argumente], check=True, capture_output=True)


def test_commit_mit_trailer_steht_im_protokoll(tmp_path: Path) -> None:
    # Fängt: Trailer werden nicht gelesen, Commits ohne Freigabe landen im Protokoll, Reihenfolge falsch.
    _git(tmp_path, "init", "-q")
    _git(
        tmp_path,
        "-c",
        "user.name=Test",
        "-c",
        "user.email=test@example.org",
        "commit",
        "-q",
        "--allow-empty",
        "-m",
        "Entwicklung ohne Freigabe",
    )
    _git(
        tmp_path,
        "-c",
        "user.name=Test",
        "-c",
        "user.email=test@example.org",
        "commit",
        "-q",
        "--allow-empty",
        "-m",
        "Zählt freie Dienstverträge mit den Dienstverträgen zusammen",
        "--trailer",
        "Freigegeben-von: Lena Gruber",
        "--trailer",
        "Vorschlag: uc3/1",
        "--trailer",
        "Modell: gpt-5-4-mini@azure",
    )
    commits = freigabe_commits(tmp_path)
    assert [(c.anweisung, c.freigegeben_von, c.vorschlag, c.modell) for c in commits] == [
        (
            "Zählt freie Dienstverträge mit den Dienstverträgen zusammen",
            "Lena Gruber",
            "uc3/1",
            "gpt-5-4-mini@azure",
        )
    ]


def test_protokoll_nennt_regelfreigabe_und_veroeffentlichung(conn: Verbindung, tmp_path: Path) -> None:
    # Fängt: Freigaben mit Namen (Regeln, Monat) fehlen im Abgabe-Protokoll.
    _git(tmp_path, "init", "-q")
    lauf_ausfuehren(conn, "2024-08", "v1")
    regeln_freigeben(conn, "v1", "Lena Gruber")
    veroeffentlichen(conn, "2024-08", "v1", "Lena Gruber")
    text = protokoll_erzeugen(conn, tmp_path)
    assert "## 3 Regelfreigaben" in text and "| v1 | Lena Gruber |" in text
    assert "| 2024-08 | v1 | Lena Gruber |" in text
    assert "Noch keine freigegebene Änderung über die Agenten." in text
