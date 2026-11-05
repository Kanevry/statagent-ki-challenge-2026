"""Der ÖNACE-Wechsel als Datei für die Web-Monatsseite (#179).

Die Zahlen rechnet `_oenace_wechsel` aus `bereinigt.abschnitt`. Dieses Schema gibt es online nicht, und ein
veröffentlichter Monat ändert sich nicht mehr. Deshalb liegt das Ergebnis als erzeugte Datei im Web-Code:
`web/components/uc3/oenace-wechsel.json`, je Monat und Regelsatz. Ein Monat ohne Eintrag zeigt nichts.
`test_oenace_wechsel_datei.py` vergleicht die Datei mit der Datenbank (Marker `daten`).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from statagent import konfig
from statagent.berichte.qualitaetsbericht import _oenace_wechsel
from statagent.db import Verbindung

DATEI = konfig.REPO_WURZEL / "web" / "components" / "uc3" / "oenace-wechsel.json"
REGELSAETZE = ("v1", "v2")


def wechsel_je_monat(conn: Verbindung) -> dict[str, dict[str, dict[str, Any]]]:
    """Je Monat und Regelsatz der Wechsel, nur für gerechnete Monate, in denen eine neue ÖNACE-Version beginnt."""
    zeilen = conn.execute(
        """SELECT DISTINCT lieferung, regelsatz FROM meta.lauf
           WHERE regelsatz = ANY(%s) AND status IN ('fertig', 'unveraendert') ORDER BY lieferung, regelsatz""",
        (list(REGELSAETZE),),
    ).fetchall()
    ergebnis: dict[str, dict[str, dict[str, Any]]] = {}
    for z in zeilen:
        wechsel = _oenace_wechsel(conn, str(z["lieferung"]), str(z["regelsatz"]))
        if wechsel is not None:
            ergebnis.setdefault(str(z["lieferung"]), {})[str(z["regelsatz"])] = wechsel
    return ergebnis


def als_text(daten: dict[str, dict[str, dict[str, Any]]]) -> str:
    return json.dumps(daten, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def datei_schreiben(conn: Verbindung, ziel: Path = DATEI) -> tuple[Path, int]:
    """Schreibt die Datei und gibt Pfad und Zahl der Monate zurück. In die Datenbank schreibt das nichts."""
    daten = wechsel_je_monat(conn)
    ziel.write_text(als_text(daten), encoding="utf-8")
    return ziel, len(daten)
