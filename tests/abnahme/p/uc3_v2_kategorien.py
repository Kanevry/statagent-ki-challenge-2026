"""Blatt Beschäftigungskategorie: Sheet v2 gegen Sheet v1 und Orakel (#69 AC2), ohne Datenbank.

    uv run --package statagent python tests/abnahme/p/uc3_v2_kategorien.py

v2 trägt Auftrag 1 und 2 zusammen (docs/plan/uc3/aenderungsauftraege-matrix.md), ein Sheet nur mit Auftrag 1
gibt es nicht. Daher gilt `Arbeiter = ArbeiterDV + ArbeiterFD` nicht gegen die v1-Zahlen, sondern nur auf
derselben Zählbasis. `identitaet_gegen_v1_monate` zeigt das offen. `auftrag1_insgesamt_gleich_v1_monate`
misst: Auftrag 1 allein (Spalte auftrag1_stichtag_mit_e07 des unabhängigen Orakels) ändert die Summe je Monat
nicht.
Nur Zahlen je Kategorie.
"""

from __future__ import annotations

import csv
import sys

import openpyxl

BLATT = "Beschaeftigungskategorie"


def blatt(pfad: str) -> tuple[list[str], dict[str, list[int]]]:
    ws = openpyxl.load_workbook(pfad, read_only=True, data_only=True)[BLATT]
    zeilen = list(ws.iter_rows(values_only=True))
    monate = [str(m) for m in zeilen[0][2:]]
    return monate, {str(z[0]): [int(w) for w in z[2:]] for z in zeilen[1:] if z[0]}


def main() -> int:
    monate, v1 = blatt("abgabe/aggregationen_v1.xlsx")
    monate2, v2 = blatt("abgabe/aggregationen_v2.xlsx")
    print(f"monate_v1 {len(monate)}")
    print(f"monate_gleich {monate == monate2}")
    print(f"codes_v1 {','.join(sorted(v1))}")
    print(f"codes_v2 {','.join(sorted(v2))}")
    with open("tests/abnahme/orakel/zeitreihe.csv", encoding="utf-8", newline="") as f:
        orakel = {z["monat"]: int(z["auftrag1_stichtag_mit_e07"]) for z in csv.DictReader(f, delimiter=";")}
    summe_v1 = {m: sum(werte[i] for werte in v1.values()) for i, m in enumerate(monate)}
    print(f"auftrag1_insgesamt_gleich_v1_monate {sum(orakel.get(m) == summe_v1[m] for m in monate)}")
    gleich = sum(
        v2["Arbeiter"][i] == v1["ArbeiterDV"][i] + v1["ArbeiterFD"][i]
        and v2["Angestellte"][i] == v1["AngestellteDV"][i] + v1["AngestellteFD"][i]
        and v2["Beamte"][i] == v1["Beamte"][i]
        for i in range(len(monate))
    )
    print(f"identitaet_gegen_v1_monate {gleich}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
