"""Vergleicht ein Aggregations-Sheet Zelle für Zelle mit dem unabhängigen Orakel.

    uv run --package statagent python tests/abnahme/p/uc3_sheet_orakel.py \
        --sheet abgabe/aggregationen_v1.xlsx --orakel tests/abnahme/orakel/sheet-v1.csv \
        --spalte wert_v1_mit_e07

Ausgabe (deterministisch): `zellen <n>`, `abweichend <m>`, `fehlend <k>`, danach höchstens zehn Abweichungen.
Das Orakel stammt aus einer eigenen Rechnung direkt auf den Lieferungen (lead-session-orchestrator-bb,
05.11.2026), nicht aus dem Code, der geprüft wird. Die Zeile „Insgesamt“ ist im Sheet eine Formel; sie wird
als Summe der übrigen Zeilen des Blatts nachgerechnet und mit dem Orakel verglichen.
"""

from __future__ import annotations

import argparse
import csv
import sys

import openpyxl


def sheet_werte(pfad: str) -> dict[tuple[str, str, str], int]:
    wb = openpyxl.load_workbook(pfad, read_only=True, data_only=True)
    werte: dict[tuple[str, str, str], int] = {}
    for ws in wb.worksheets:
        zeilen = list(ws.iter_rows(values_only=True))
        if not zeilen or zeilen[0][0] != "CODE":
            continue
        monate = [str(m) for m in zeilen[0][2:]]
        for z in zeilen[1:]:
            if z[0] is None:
                continue
            for monat, wert in zip(monate, z[2:], strict=False):
                if wert is not None:
                    werte[(ws.title, str(z[0]), monat)] = int(wert)
    # „Insgesamt“ ist im Sheet eine Formel ohne gespeicherten Wert: als Summe der Zeilen nachrechnen.
    summen: dict[tuple[str, str, str], int] = {}
    for (blatt, _code, monat), wert in werte.items():
        schluessel = (blatt, "Insgesamt", monat)
        summen[schluessel] = summen.get(schluessel, 0) + wert
    werte.update(summen)
    return werte


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sheet", required=True)
    ap.add_argument("--orakel", required=True)
    ap.add_argument("--spalte", required=True)
    a = ap.parse_args()

    ist = sheet_werte(a.sheet)
    with open(a.orakel, newline="") as f:
        zeilen = csv.DictReader(f, delimiter=";")
        soll = {(r["blatt"], r["code"], r["monat"]): int(r[a.spalte]) for r in zeilen}

    abweichend = [(k, soll[k], ist[k]) for k in sorted(soll) if k in ist and ist[k] != soll[k]]
    fehlend = [k for k in sorted(soll) if k not in ist]
    zusaetzlich = [k for k in sorted(ist) if k not in soll]
    print(f"zellen {len(soll)}")
    print(f"abweichend {len(abweichend)}")
    print(f"fehlend {len(fehlend)}")
    print(f"zusaetzlich {len(zusaetzlich)}")
    for (blatt, code, monat), s, i in abweichend[:10]:
        print(f"  {blatt} {code} {monat}: soll {s}, ist {i}")
    for blatt, code, monat in (fehlend + zusaetzlich)[:10]:
        print(f"  ohne Gegenstück: {blatt} {code} {monat}")
    return 0 if not (abweichend or fehlend or zusaetzlich) else 1


if __name__ == "__main__":
    sys.exit(main())
