"""uc3 bestaetigen: die Person bestätigt delegiert eingegebene Freigaben selbst (Technische Regel 7)."""

from __future__ import annotations

from pathlib import Path

import pytest
from test_agenten_freigabe import git
from test_regeln_freigabe import _repo

from statagent.berichte.protokoll import freigabe_commits
from statagent.bestaetigung import BestaetigungFehler, bestaetigen
from statagent.regeln import NameUngueltig


def test_bestaetigung_nennt_jeden_freigabe_commit_und_landet_im_protokoll(tmp_path: Path) -> None:
    # Fängt: Bestätigung ohne Bezug auf die Freigabe-Commits, ein unbekannter Vorschlag wird stillschweigend
    # übergangen, ein Platzhalter-Name geht durch, oder das Protokoll führt die Bestätigung nicht.
    repo = _repo(tmp_path / "repo")
    for nr in (24, 25):
        git(
            repo,
            "commit",
            "-q",
            "--allow-empty",
            "-m",
            f"Auftrag {nr}",
            "-m",
            f"Freigegeben-von: Lena Gruber\nVorschlag: uc3/{nr}\nModell: x@y",
        )
    shas = {nr: git(repo, "log", "--format=%H", f"--grep=Vorschlag: uc3/{nr}").strip() for nr in (24, 25)}

    vorher = git(repo, "rev-parse", "HEAD").strip()
    with pytest.raises(BestaetigungFehler, match="uc3/99"):
        bestaetigen(repo, "Lena Gruber", ["uc3/24", "uc3/99"])
    with pytest.raises(NameUngueltig):
        bestaetigen(repo, "Team", ["uc3/24"])
    assert git(repo, "rev-parse", "HEAD").strip() == vorher  # nach den Fehlern kein Commit

    erg = bestaetigen(repo, "Lena Gruber", ["uc3/24", "uc3/25"])
    assert erg.commits == {"uc3/24": shas[24], "uc3/25": shas[25]}
    nachricht = git(repo, "log", "-1", "--format=%B")
    assert "Freigegeben-von: Lena Gruber" in nachricht
    assert f"Bestaetigt: {shas[24]}" in nachricht and f"Bestaetigt: {shas[25]}" in nachricht
    assert git(repo, "show", "--stat", "--format=", "HEAD").strip() == ""  # leerer Commit
    assert freigabe_commits(repo)[-1].anweisung.startswith("Bestätigung der Freigaben uc3/24, uc3/25")
