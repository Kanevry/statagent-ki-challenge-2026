"""Pfadschutz für Lieferungen mit Einzeldaten (konfig.im_repo)."""

from __future__ import annotations

import subprocess
from pathlib import Path

from statagent import konfig


def test_ziel_in_fremdem_git_repo_wird_abgelehnt(tmp_path: Path) -> None:
    # Fängt: STATAGENT_LIEFERUNGEN zeigt in einen Geschwister-Worktree oder ein anderes Repo; im_repo kannte nur
    # das eigene Repo und den Haupt-Checkout, die CSV mit PERSON_ID landete dort (Review, Punkt 7).
    fremd = tmp_path / "fremd"
    fremd.mkdir()
    subprocess.run(["git", "init", "-q", str(fremd)], check=True)
    eigenes = tmp_path / "eigenes"
    eigenes.mkdir()
    # auch ein noch nicht angelegter Unterordner zählt (nächster existierender Elternordner)
    assert konfig.im_repo(fremd / "lieferungen" / "ministerium_2026-07.csv", eigenes)
    assert not konfig.im_repo(tmp_path / "draussen" / "ministerium_2026-07.csv", eigenes)
