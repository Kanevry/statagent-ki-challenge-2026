"""Unabhängiger CSV-Filter über eine Rohlieferung (#70 AC2), ohne Datenbank und ohne Produktcode.

    python3 tests/abnahme/p/uc3_csv_filter.py [--lieferung 2026-07] [--stichtag]

Zählt distinct VVH_ID mit BEGINN <= Monatsletzter und ENDE leer oder >= Monatserster. `--stichtag` (#14 AC2):
am Monatsletzten aktive Sätze, die übrigen und ihre Volldubletten. Ausgegeben werden nur Zahlen, keine Zeilen
(die Lieferung enthält Einzeldaten). Startpaket: `STATAGENT_STARTPAKET`, sonst ../svbox/uc3 neben dem Checkout.
"""

from __future__ import annotations

import argparse
import calendar
import csv
import gzip
import os
import sys
from pathlib import Path


def stichtag(pfad: Path, letzter: str) -> int:
    zeilen = 0
    aktiv: set[str] = set()
    personen: dict[str, int] = {}
    nicht_aktiv: list[tuple[str, ...]] = []
    with gzip.open(pfad, "rt", encoding="utf-8", newline="") as f:
        for z in csv.DictReader(f, delimiter=";"):
            zeilen += 1
            ende = (z["ENDE"] or "").strip()
            if z["BEGINN"] <= letzter and (not ende or ende >= letzter):
                if z["VVH_ID"] not in aktiv:
                    personen[z["PERSON_ID"]] = personen.get(z["PERSON_ID"], 0) + 1
                aktiv.add(z["VVH_ID"])
            else:
                nicht_aktiv.append(tuple(z.values()))
    print(f"zeilen {zeilen}")
    print(f"distinct_stichtag {len(aktiv)}")
    print(f"nicht_aktiv {len(nicht_aktiv)}")
    print(f"volldubletten_nicht_aktiv {len(nicht_aktiv) - len(set(nicht_aktiv))}")
    print(f"personen_mit_mehreren_vvh {sum(1 for n in personen.values() if n > 1)}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--lieferung", default="2026-07")
    ap.add_argument("--startpaket", default=os.environ.get("STATAGENT_STARTPAKET", "../svbox/uc3"))
    ap.add_argument("--stichtag", action="store_true")
    a = ap.parse_args()
    pfad = Path(a.startpaket) / "lieferungen" / f"lieferung_{a.lieferung}.csv.gz"
    if not pfad.is_file():
        print(f"lieferung {a.lieferung} fehlt")
        return 1
    jahr, monat = map(int, a.lieferung.split("-"))
    erster = f"{a.lieferung}-01"
    letzter = f"{a.lieferung}-{calendar.monthrange(jahr, monat)[1]:02d}"
    if a.stichtag:
        return stichtag(pfad, letzter)
    ids: set[str] = set()
    with gzip.open(pfad, "rt", encoding="utf-8", newline="") as f:
        for z in csv.DictReader(f, delimiter=";"):
            ende = (z["ENDE"] or "").strip()
            if z["BEGINN"] <= letzter and (not ende or ende >= erster):
                ids.add(z["VVH_ID"])
    print(f"distinct_vvh {len(ids)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
