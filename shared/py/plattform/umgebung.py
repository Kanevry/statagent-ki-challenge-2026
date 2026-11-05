"""`.env.local` laden, ohne dass eine geerbte Variable der Shell still gewinnt.

Gesucht wird vom Startordner aufwärts bis zur Repo-Wurzel. Liegt dort keine Datei (typisch in einem
Worktree unter ``_wt/``), wird die Wurzel des Haupt-Checkouts geprüft, den ``git --git-common-dir`` nennt.
Werte werden nie ausgegeben.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

from dotenv import load_dotenv

DATEINAME = ".env.local"


def _repo_wurzel(start: Path) -> Path | None:
    for ordner in (start, *start.parents):
        if (ordner / ".git").exists():
            return ordner
    return None


def _haupt_checkout(start: Path) -> Path | None:
    try:
        ausgabe = subprocess.run(
            ["git", "-C", str(start), "rev-parse", "--path-format=absolute", "--git-common-dir"],
            capture_output=True,
            text=True,
            timeout=5,
            check=True,
        ).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return None
    return Path(ausgabe).parent if ausgabe else None


def finde_env_local(start: Path | None = None) -> Path | None:
    """Pfad der zuständigen `.env.local` oder ``None``."""
    start = (start or Path.cwd()).resolve()
    wurzel = _repo_wurzel(start)
    for ordner in (start, *start.parents):
        kandidat = ordner / DATEINAME
        if kandidat.is_file():
            return kandidat
        if wurzel is not None and ordner == wurzel:
            break
    haupt = _haupt_checkout(start)
    if haupt is not None and (haupt / DATEINAME).is_file():
        return haupt / DATEINAME
    return None


def lade_env_local(start: Path | None = None) -> Path | None:
    """Lädt `.env.local` mit Vorrang vor geerbten Variablen; gibt den Pfad zurück (nie Werte).

    ``KIC_ENV_DATEI`` zeigt auf eine andere Datei (Tests, Jury-Rechner). Fehlt diese Datei, ist das ein
    Fehler: sonst rechnet ein Lauf nach einem Tippfehler im Pfad still mit geerbten Shell-Werten.
    """
    explizit = os.environ.get("KIC_ENV_DATEI")
    pfad: Path | None
    if explizit:
        pfad = Path(explizit)
        if not pfad.is_file():
            raise FileNotFoundError(f"KIC_ENV_DATEI zeigt auf keine Datei: {pfad}")
    else:
        pfad = finde_env_local(start)
    if pfad is None:
        return None
    # interpolate=False: ein Wert mit `$` bleibt wörtlich (sonst ersetzt python-dotenv still Teile davon).
    load_dotenv(pfad, override=True, interpolate=False)
    return pfad
