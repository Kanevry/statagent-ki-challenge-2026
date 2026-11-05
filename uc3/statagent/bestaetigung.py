"""Nachträgliche Bestätigung delegierter Freigaben durch die Person selbst (Technische Regel 7).

Hat jemand eine Freigabe im Auftrag einer Person eingegeben, bestätigt diese Person sie mit einem eigenen Commit:
Trailer ``Freigegeben-von: <Vor- und Nachname>`` und je bestätigtem Freigabe-Commit ``Bestaetigt: <sha>``. Der Commit
ist leer (``git commit --only --allow-empty``), ändert also weder Regeln noch Dateien; ``uc3 protokoll`` führt ihn
wie jede Freigabe in § 1.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path

from statagent.regeln import name_pruefen


class BestaetigungFehler(RuntimeError):
    """Bestätigung nicht möglich: unbekannter Vorschlag, kein Freigabe-Commit oder Git-Fehler."""


@dataclass(frozen=True)
class Bestaetigung:
    name: str
    commits: dict[str, str]  # Vorschlag (z. B. uc3/24) → Hash des Freigabe-Commits
    commit_hash: str


def _git(repo: Path, *argumente: str) -> str:
    erg = subprocess.run(["git", "-C", str(repo), *argumente], capture_output=True, text=True, check=False)
    if erg.returncode != 0:
        raise BestaetigungFehler(erg.stderr.strip() or f"git {argumente[0]} ist fehlgeschlagen")
    return erg.stdout.strip()


def freigabe_commit(repo: Path, vorschlag: str) -> str:
    """Hash des jüngsten Commits mit Trailer ``Vorschlag: <vorschlag>`` und ``Freigegeben-von``."""
    format_ = (
        "%H%x1f%(trailers:key=Vorschlag,valueonly,separator=%x2C)%x1f"
        "%(trailers:key=Freigegeben-von,valueonly,separator=%x2C)%x1e"
    )
    for eintrag in _git(repo, "log", f"--format={format_}").split("\x1e"):
        teile = eintrag.strip().split("\x1f")
        if len(teile) != 3:
            continue
        sha, vorschlaege, von = teile
        if vorschlag in [v.strip() for v in vorschlaege.split(",")] and von.strip():
            return sha
    raise BestaetigungFehler(f"Kein Freigabe-Commit mit Vorschlag {vorschlag} gefunden")


def bestaetigen(repo: Path, name: str, vorschlaege: list[str]) -> Bestaetigung:
    """Legt den Bestätigungs-Commit an; prüft vorher Namen und jeden Vorschlag (sonst kein Commit)."""
    person = name_pruefen(name)
    if not vorschlaege:
        raise BestaetigungFehler("Bitte mindestens einen Vorschlag nennen, z. B. uc3/24")
    commits = {v: freigabe_commit(repo, v) for v in dict.fromkeys(vorschlaege)}
    betreff = f"Bestätigung der Freigaben {', '.join(commits)} durch {person}"
    rumpf = "Diese Freigaben wurden in meinem Auftrag eingegeben; ich bestätige sie selbst.\n" + "\n".join(
        f"- {v}: Commit {sha[:10]}" for v, sha in commits.items()
    )
    trailer = "\n".join([f"Freigegeben-von: {person}", *(f"Bestaetigt: {sha}" for sha in commits.values())])
    _git(repo, "commit", "--only", "--allow-empty", "-m", betreff, "-m", rumpf, "-m", trailer)
    return Bestaetigung(person, commits, _git(repo, "rev-parse", "HEAD"))
