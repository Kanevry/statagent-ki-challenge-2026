"""UC3-Datenbank für den Playwright-Job füllen (Antrag #135, Punkt 135-7).

Lädt das Fixture-Startpaket und die vier Mini-Lieferungen aus uc3/tests/fixtures (erfundene Daten, keine
echten Personen), richtet das UC3-Schema ein und rechnet alle Lieferungen mit Regelsatz v1. Danach zeigen die
Seiten unter /uc3 Läufe, Berichte und Prüftreffer statt eines leeren Zustands.

Aufruf (Wurzel des Repos): ``UC3_DATABASE_URL=postgresql://… uv run python scripts/ci/uc3_seed.py``
Die Datenbank muss leer sein; das Skript bricht ab, wenn schon Lieferungen geladen sind.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

WURZEL = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(WURZEL / "uc3" / "tests"))

from conftest import LIEFERUNGEN, _laden  # noqa: E402  (Fixture-Lader der UC3-Tests, eine Quelle)
from statagent.db import schema_einrichten, verbinden  # noqa: E402


def main() -> int:
    url = os.environ.get("UC3_DATABASE_URL", "").strip()
    if not url:
        print("UC3_DATABASE_URL fehlt", file=sys.stderr)
        return 2
    with verbinden(url) as conn:
        vorhanden = conn.execute(
            "SELECT count(*) AS n FROM information_schema.tables"
            " WHERE table_schema = 'roh' AND table_name = 'lieferung'"
        ).fetchone()
        if vorhanden is not None and int(str(vorhanden["n"])) > 0:
            print("roh.lieferung existiert schon, kein Seed", file=sys.stderr)
            return 2
        _laden(conn)
        schema_einrichten(conn)
        conn.commit()
    print(f"geladen: {', '.join(LIEFERUNGEN)}")
    # Läufe über die CLI, wie im Betrieb; ein Lauf = eine Lieferung, in Reihenfolge.
    subprocess.run(
        ["uc3", "lauf", "--alle", "--regelsatz", "v1", "--gestartet-von", "CI Seed"],
        check=True,
        cwd=WURZEL,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
