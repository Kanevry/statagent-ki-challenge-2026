"""Konfiguration: Datenbank, Startpaket, Ablageorte. Werte kommen aus der Umgebung bzw. `.env.local`."""

from __future__ import annotations

import os
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


def im_repo(pfad: Path, repo: Path | None = None) -> bool:
    """True, wenn `pfad` im Repo (oder in einem Worktree davon) liegt."""
    ziel = pfad.resolve()
    wurzeln = {(repo or REPO_WURZEL).resolve(), _haupt_checkout(repo or REPO_WURZEL).resolve()}
    return any(ziel == w or w in ziel.parents for w in wurzeln)


def abgabe() -> Path:
    """Ablage der erzeugten Ergebnisse (Sheet, Qualitätsberichte, Ministeriums-Lieferung, Protokoll)."""
    umgebung_laden()
    gesetzt = os.environ.get("STATAGENT_ABGABE")
    return Path(gesetzt).expanduser() if gesetzt else REPO_WURZEL / "abgabe"
