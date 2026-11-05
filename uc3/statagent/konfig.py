"""Konfiguration: Datenbank, Startpaket, Ablageorte. Werte kommen aus der Umgebung bzw. `.env.local`."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

from dotenv import load_dotenv

#: Paketwurzel `uc3/` und Repo-Wurzel (eine Ebene darüber).
UC3_WURZEL = Path(__file__).resolve().parents[1]
REPO_WURZEL = UC3_WURZEL.parent
DB_VERZEICHNIS = UC3_WURZEL / "db"

#: Öffentliche Standardwerte des Startpakets (README des Veranstalters), kein Geheimnis.
STANDARD_DATENBANK_URL = "postgresql://statistik:statistik@localhost:5433/statistik"

_geladen = False


def umgebung_laden() -> None:
    """Lädt `.env.local` aus der Repo-Wurzel (falls vorhanden), ohne gesetzte Variablen zu überschreiben."""
    global _geladen
    if _geladen:
        return
    datei = REPO_WURZEL / ".env.local"
    if datei.is_file():
        load_dotenv(datei, override=False)
    _geladen = True


def datenbank_url() -> str:
    umgebung_laden()
    return os.environ.get("UC3_DATABASE_URL") or STANDARD_DATENBANK_URL


def _haupt_checkout(repo: Path) -> Path:
    """Bei einem Git-Worktree (`.git` ist eine Datei) der Ordner des Haupt-Checkouts, sonst `repo`."""
    git = repo / ".git"
    if git.is_file():
        inhalt = git.read_text(encoding="utf-8").strip()
        if inhalt.startswith("gitdir:"):
            gitdir = Path(inhalt.split(":", 1)[1].strip())
            # <haupt>/.git/worktrees/<name> -> <haupt>
            if gitdir.parent.name == "worktrees":
                return gitdir.parent.parent.parent
    return repo


def startpaket() -> Path:
    """Ordner des UC3-Startpakets (Beispielbericht, Vorlagen, Klassifikationen).

    Reihenfolge: `STATAGENT_STARTPAKET`, sonst `../svbox/uc3` neben der Repo-Wurzel bzw. neben dem
    Haupt-Checkout eines Worktrees. Das Startpaket gehört dem Veranstalter und liegt nicht im Repo.
    """
    umgebung_laden()
    gesetzt = os.environ.get("STATAGENT_STARTPAKET")
    if gesetzt:
        return Path(gesetzt).expanduser()
    for basis in (REPO_WURZEL, _haupt_checkout(REPO_WURZEL)):
        kandidat = basis.parent / "svbox" / "uc3"
        if kandidat.is_dir():
            return kandidat
    return REPO_WURZEL.parent / "svbox" / "uc3"


def beispielbericht() -> Path:
    return startpaket() / "beispielbericht_2024-08.xlsx"


def vorlagen() -> Path:
    return startpaket() / "vorlagen"


def lieferungen_extern() -> Path:
    """Ablage für Lieferungen mit Einzeldaten (Ministerium): außerhalb des Repos, nie versioniert.

    Reihenfolge: `STATAGENT_LIEFERUNGEN`, sonst `lieferungen/` neben dem Haupt-Checkout (wie das Startpaket
    `svbox/`). Abgegeben wird von dort über den SV-Box-Teamordner; im Repo steht nur der Beleg mit sha256.
    """
    umgebung_laden()
    gesetzt = os.environ.get("STATAGENT_LIEFERUNGEN")
    if gesetzt:
        return Path(gesetzt).expanduser()
    return _haupt_checkout(REPO_WURZEL).parent / "lieferungen"


def _in_git_repo(ziel: Path) -> bool:
    """True, wenn `ziel` (oder sein nächster existierender Elternordner) in irgendeinem Git-Repo liegt.

    Fängt auch Geschwister-Worktrees und fremde Repos, die `im_repo` über die Pfade allein nicht sieht. Ohne
    lauffähiges git gilt das Ziel vorsichtshalber als Repo.
    """
    ordner = ziel
    while not ordner.is_dir():
        if ordner.parent == ordner:
            return False
        ordner = ordner.parent
    # GIT_DIR und Co. aus der Umgebung würden git auf ein anderes Repo lenken.
    umgebung = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    try:
        lauf = subprocess.run(
            ["git", "-C", str(ordner), "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            timeout=30,
            env=umgebung,
        )
    except (OSError, subprocess.TimeoutExpired):
        return True
    return lauf.returncode == 0 and bool(lauf.stdout.strip())


def im_repo(pfad: Path, repo: Path | None = None) -> bool:
    """True, wenn `pfad` im Repo, in einem Worktree davon oder in irgendeinem anderen Git-Repo liegt."""
    ziel = pfad.resolve()
    wurzeln = {(repo or REPO_WURZEL).resolve(), _haupt_checkout(repo or REPO_WURZEL).resolve()}
    if any(ziel == w or w in ziel.parents for w in wurzeln):
        return True
    return _in_git_repo(ziel)


def abgabe() -> Path:
    """Ablage der erzeugten Ergebnisse (Sheet, Qualitätsberichte, Ministeriums-Lieferung, Protokoll)."""
    umgebung_laden()
    gesetzt = os.environ.get("STATAGENT_ABGABE")
    return Path(gesetzt).expanduser() if gesetzt else REPO_WURZEL / "abgabe"
