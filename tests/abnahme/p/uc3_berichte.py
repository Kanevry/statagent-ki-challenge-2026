"""Liest die Qualitätsberichte eigenständig (#16 AC4), unabhängig vom Validator des Produkts.

    python3 tests/abnahme/p/uc3_berichte.py [--ordner abgabe/qualitaetsberichte]

Je Bericht fünf Abschnitte; jede Auffälligkeit (Abschnitt 2) nennt Umfang, Abfrage, Maßnahme und eine der drei
Einstufungen. Annahmen und Revisionsbedarf müssen vorkommen. Exit 0 nur ohne Mangel.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

EINSTUFUNGEN = ("erklärt – plausibel", "erklärt – Datenproblem", "nicht erklärbar")
ABSCHNITTE = re.compile(r"^## (\d) ", re.M)
# Spalten in Abschnitt 2: Nr., Ebene, Beschreibung, Umfang, Beleg, Einstufung, Maßnahme, Rückfrage
SPALTEN = 8


def zellen(zeile: str) -> list[str]:
    return [z.strip() for z in re.split(r"(?<!\\)\|", zeile.strip().strip("|"))]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ordner", default="abgabe/qualitaetsberichte")
    a = ap.parse_args()
    dateien = sorted(Path(a.ordner).glob("20[0-9][0-9]-[0-9][0-9].md"))
    ohne_fuenf = zeilen_gesamt = ohne_pflicht = einstufung_falsch = ohne_annahme = ohne_revision = 0
    for d in dateien:
        t = d.read_text(encoding="utf-8")
        if ABSCHNITTE.findall(t) != list("12345"):
            ohne_fuenf += 1
        teil = t.split("## 2 ", 1)[-1].split("## 3 ", 1)[0]
        for z in teil.splitlines():
            if not re.match(r"^\| *\d+ *\|", z):
                continue
            c = zellen(z)
            zeilen_gesamt += 1
            if len(c) < SPALTEN or not (c[3] and c[4] and c[6]):
                ohne_pflicht += 1
            elif c[5] not in EINSTUFUNGEN:
                einstufung_falsch += 1
        ohne_annahme += "Annahme" not in t
        ohne_revision += "## 5 Revisionsbedarf" not in t
    print(f"berichte {len(dateien)}")
    print(f"ohne_fuenf_abschnitte {ohne_fuenf}")
    print(f"auffaelligkeiten {zeilen_gesamt}")
    print(f"ohne_umfang_abfrage_massnahme {ohne_pflicht}")
    print(f"einstufung_falsch {einstufung_falsch}")
    print(f"ohne_annahme {ohne_annahme}")
    print(f"ohne_revisionsbedarf {ohne_revision}")
    fehler = ohne_fuenf + ohne_pflicht + einstufung_falsch + ohne_annahme + ohne_revision
    return 0 if len(dateien) == 24 and zeilen_gesamt and not fehler else 1


if __name__ == "__main__":
    sys.exit(main())
