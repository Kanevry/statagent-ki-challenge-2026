"""Konfiguration aus Umgebungsvariablen. Werte stehen in .env.local, nie im Repo."""

from __future__ import annotations

import os
from pathlib import Path

# Lokale Entwicklungs-DB laut CLAUDE.md (PG16 auf Port 5433, Rolle statistik), eigene Datenbank lotse.
STANDARD_DATENBANK_URL = "postgresql://statistik:statistik@localhost:5433/lotse"


class KonfigFehler(RuntimeError):
    """Eine Pflichtangabe fehlt oder ist unbrauchbar."""


def daten_dir() -> Path:
    """Wurzel des UC1-Korpus (svbox/uc1). Fehlt sie oder ist sie leer: Fehler statt leerem Lauf."""
    roh = os.environ.get("UC1_DATA_DIR", "").strip()
    if not roh:
        raise KonfigFehler("UC1_DATA_DIR ist nicht gesetzt (Pfad zu svbox/uc1)")
    pfad = Path(roh).expanduser()
    if not pfad.is_dir():
        raise KonfigFehler(f"UC1_DATA_DIR zeigt auf kein Verzeichnis: {pfad}")
    if not any(pfad.iterdir()):
        raise KonfigFehler(f"UC1_DATA_DIR ist leer: {pfad}")
    return pfad


def datenbank_url() -> str:
    return os.environ.get("LOTSE_DATABASE_URL", "").strip() or STANDARD_DATENBANK_URL
