"""Abnahme #66: Ergebnis-Hashes der Prüf-DB gegen das Laufmanifest der UC3-Lane vergleichen.

Aufruf: ``python tests/abnahme/66_manifest_vergleich.py <laeufe.tsv>``

``laeufe.tsv`` ist die Ausgabe von
``psql -At -F $'\\t' -c "select distinct on (lieferung) lieferung, ergebnis_hash, gezaehlt, fortgeschrieben
from meta.lauf where status in ('fertig','unveraendert') order by lieferung, id desc"``
auf der Prüf-Datenbank. Verglichen wird mit ``docs/plan/uc3/laufmanifest-v1.csv``. Nur lesen.
"""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

MANIFEST = Path(__file__).resolve().parents[2] / "docs" / "plan" / "uc3" / "laufmanifest-v1.csv"


def main(pfad: str) -> int:
    soll = {z["monat"]: z for z in csv.DictReader(MANIFEST.open(encoding="utf-8"))}
    ist: dict[str, list[str]] = {}
    for zeile in Path(pfad).read_text(encoding="utf-8").splitlines():
        teile = zeile.split("\t")
        if len(teile) >= 4:
            ist[teile[0]] = teile
    gleich, abweichend, fehlt = [], [], []
    for monat, z in sorted(soll.items()):
        if monat not in ist:
            fehlt.append(monat)
            continue
        _, hash_ist, gezaehlt_ist, fort_ist = ist[monat][:4]
        if hash_ist == z["ergebnis_hash"] and gezaehlt_ist == z["gezaehlt"]:
            gleich.append(monat)
        else:
            abweichend.append(
                {
                    "monat": monat,
                    "hash_soll": z["ergebnis_hash"][:12],
                    "hash_ist": hash_ist[:12],
                    "gezaehlt_soll": z["gezaehlt"],
                    "gezaehlt_ist": gezaehlt_ist,
                    "fortgeschrieben_soll": z["fortgeschrieben"],
                    "fortgeschrieben_ist": fort_ist,
                }
            )
    print(json.dumps({"gleich": len(gleich), "abweichend": abweichend, "fehlt": fehlt}, ensure_ascii=False))
    return 0 if not abweichend and not fehlt else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1]))
