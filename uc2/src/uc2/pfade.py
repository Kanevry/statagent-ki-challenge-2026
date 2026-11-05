"""Pfade zu Konfiguration (im Repo) und Daten (nie im Repo).

Daten, Korpus, Zwischenstände und Vektoren liegen außerhalb des Repos. Umgebungsvariablen gewinnen,
sonst gelten die Standardorte der Challenge-Ablage `~/Projects/ki-challenge-2026/`.
"""

from __future__ import annotations

import os
from pathlib import Path

UC2_WURZEL = Path(__file__).resolve().parents[2]
"""Ordner `uc2/` im Repo (enthält `config/`, `akteure/`, `sql/`, `tests/`)."""

CONFIG = UC2_WURZEL / "config"
AKTEURE = UC2_WURZEL / "akteure"
SQL = UC2_WURZEL / "sql"

ABLAGE = Path(os.environ.get("KIC_ABLAGE", str(Path.home() / "Projects" / "ki-challenge-2026")))
"""Challenge-Ablage außerhalb des Repos (svbox, data, Arbeitsordner)."""


def presse() -> Path:
    """Pressespiegel-PDFs (`svbox/uc2/Presse`)."""
    return Path(os.environ.get("UC2_PRESSE", str(ABLAGE / "svbox" / "uc2" / "Presse")))


def daten() -> Path:
    """Kalibrierdaten (`data/uc2`), etwa das Statistik-Austria-PDF zu den Gesundheitsausgaben."""
    return Path(os.environ.get("UC2_DATEN", str(ABLAGE / "data" / "uc2")))


def arbeit() -> Path:
    """Arbeitsordner für Zwischenstände (JSONL, Vektoren, Messberichte), nie im Repo."""
    return Path(os.environ.get("UC2_ARBEIT", str(ABLAGE / "arbeit" / "uc2")))
