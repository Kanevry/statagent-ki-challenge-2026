"""Live-Proben aus docs/plan/uc3/live-proben.csv (#80 AC1, AC2), nur Zahlen.

    python3 tests/abnahme/p/uc3_live.py

Zählt je Variante A, B, C die Läufe, die Dauer unter 4 Minuten und ausgefüllte Belegfelder. Die Varianten mit
dem Zusatz `_locker` sind Läufe derselben Variante mit anderem Wortlaut.
"""

from __future__ import annotations

import csv
import sys

FELDER = ("regelsatz", "protokoll_ids", "name", "zeit", "diff", "zahlen")
VARIANTEN = {"A": "A_stichtag_15", "B": "B_ohne_beamte", "C": "C_ostregion"}


def main() -> int:
    with open("docs/plan/uc3/live-proben.csv", encoding="utf-8", newline="") as f:
        zeilen = list(csv.DictReader(f, delimiter=";"))
    print(f"zeilen {len(zeilen)}")
    for kurz, name in VARIANTEN.items():
        wahl = [z for z in zeilen if z["auftrag"].startswith(name)]
        unter = sum(float(z["dauer_s"]) < 240 for z in wahl)
        voll = sum(all(z[k].strip() for k in FELDER) for z in wahl)
        print(f"variante_{kurz} laeufe {len(wahl)} unter_4min {unter} felder_voll {voll}")
    for spalte in ("ablehnen_hash_gleich", "ruecknahme_hash_gleich", "ruecknahme_zahlen_gleich", "bestanden"):
        werte = sorted({z[spalte].strip() for z in zeilen})
        print(f"{spalte} {','.join(werte)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
