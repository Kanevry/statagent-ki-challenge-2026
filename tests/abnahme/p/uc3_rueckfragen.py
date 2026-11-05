"""Prüft die Rückfragen R1 bis R5 (#72 AC1) gegen die Rohlieferungen, ohne Datenbank und ohne Produktcode.

    python3 tests/abnahme/p/uc3_rueckfragen.py

Je Datei: Pflichtteile da, 3 bis 5 Beispiel-IDs, und jede ID zeigt in der Rohlieferung den behaupteten Befund.
Ausgegeben werden nur Zahlen, keine IDs. Startpaket: `STATAGENT_STARTPAKET`, sonst ../svbox/uc3.
"""

from __future__ import annotations

import csv
import gzip
import os
import re
import sys
from pathlib import Path

START = Path(os.environ.get("STATAGENT_STARTPAKET", "../svbox/uc3"))
PFLICHT = (
    r"^\*\*Thema:\*\*",
    r"^\*\*Betroffene Lieferung\(en\):\*\* .*lieferung_\d{4}-\d{2}",
    r"^\| Anzahl betroffener Sätze \| \S",
    r"^\| Zeitraum / ab welcher Lieferung \| \S",
    r"^```sql",
    r"^\*\*Unser Vorschlag zur Behandlung:\*\* \S",
    r"^\*\*Frage an die Fachabteilung:\*\* \S",
)
THEMEN = {"R1": "Geburtsmonat 13", "R2": "ÖNACE", "R3": "2025-10", "R4": "2025-03", "R5": "2025-06"}


def lieferung(monat: str) -> dict[str, dict[str, str]]:
    with gzip.open(
        START / "lieferungen" / f"lieferung_{monat}.csv.gz", "rt", encoding="utf-8", newline=""
    ) as f:
        return {z["VVH_ID"]: z for z in csv.DictReader(f, delimiter=";")}


def belegt(nr: str, ids: list[str]) -> int:
    """Wie viele Beispiel-IDs zeigen in der Rohlieferung den Befund der Rückfrage."""
    if nr == "R1":
        d = lieferung("2024-08")
        return sum(i in d and re.search(r"-13-|^\d{4}13", d[i]["GEBURTSDATUM"]) is not None for i in ids)
    if nr == "R2":
        a, b = lieferung("2025-05"), lieferung("2026-02")
        return sum(i in a or i in b for i in ids)
    if nr in ("R3", "R4"):
        monat, vorher = ("2025-10", "2025-09") if nr == "R3" else ("2025-03", "2025-02")
        d, v = lieferung(monat), lieferung(vorher)
        return sum(i not in d and i in v for i in ids)
    d = lieferung("2025-06")
    return sum(
        i in d and (not d[i]["BEGINN"] or (d[i]["ENDE"] and d[i]["ENDE"] < d[i]["BEGINN"])) for i in ids
    )


def main() -> int:
    maengel = 0
    for nr, thema in THEMEN.items():
        t = Path(f"abgabe/rueckfragen/{nr}.md").read_text(encoding="utf-8")
        fehlt = sum(re.search(m, t, re.M) is None for m in PFLICHT) + (thema not in t)
        z = re.search(r"^\| Beispiel-IDs[^|]*\| ([^|]*) \|", t, re.M)
        ids = re.findall(r"\d+", z.group(1)) if z else []
        ok = belegt(nr, ids)
        print(f"{nr} fehlt {fehlt} ids {len(ids)} belegt {ok}")
        maengel += fehlt + (not 3 <= len(ids) <= 5) + (ok != len(ids))
    print(f"maengel {maengel}")
    return 0 if not maengel else 1


if __name__ == "__main__":
    sys.exit(main())
