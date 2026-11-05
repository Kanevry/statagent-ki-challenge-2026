"""Liest die UC3-Prüf-DB (nur lesen) und gibt eindeutige Zeilen für schwere Prüfsätze aus.

    P="uv run --package statagent python tests/abnahme/p/uc3_db.py"
    $P abrechnung 2024-08 [--regelsatz v1]
    $P zeitreihe --orakel tests/abnahme/orakel/zeitreihe.csv --spalte v1_sheet_mit_e07
    $P laeufe --manifest docs/plan/uc3/laufmanifest-v1.csv
    $P regelsaetze v1 v2 ministerium

Die Adresse kommt aus UC3_DATABASE_URL; der Prüflauf setzt sie nur auf die Prüf-DB (Port 5444).
Je Monat zählt der jüngste Lauf mit Status fertig oder unveraendert. Monatssumme = gezaehlt; die
E07-Fortschreibung ist darin enthalten (Laufmanifest 2025-03: gezaehlt 388650 = 387180 + 1470).
"""

from __future__ import annotations

import argparse
import csv
import os
import sys

import psycopg

LETZTER_LAUF = """
select distinct on (lieferung) lieferung, gelesen, gezaehlt, nicht_gezaehlt, ausgeschlossen,
       coalesce(fortgeschrieben, 0), ergebnis_hash, ergebnis_status
from meta.lauf
where status in ('fertig', 'unveraendert') and regelsatz = %s
order by lieferung, id desc
"""


def laeufe_lesen(regelsatz: str) -> dict[str, tuple]:
    with psycopg.connect(os.environ["UC3_DATABASE_URL"], connect_timeout=5) as verbindung:
        verbindung.read_only = True
        zeilen = verbindung.execute(LETZTER_LAUF, (regelsatz,)).fetchall()
    return {z[0]: z for z in zeilen}


def abrechnung(lieferung: str, regelsatz: str) -> int:
    z = laeufe_lesen(regelsatz).get(lieferung)
    if not z:
        print(f"kein fertiger Lauf {regelsatz} für {lieferung}")
        return 1
    _, gelesen, gezaehlt, nicht, aus, fort, _, status = z
    print(f"gelesen {gelesen}")
    print(f"gezaehlt {gezaehlt}")
    print(f"nicht_gezaehlt {nicht}")
    print(f"ausgeschlossen {aus}")
    print(f"fortgeschrieben {fort}")
    print(f"ergebnis_status {status}")
    # gezaehlt enthält die E07-Fortschreibung; sie stammt nicht aus der eigenen Lieferung
    print(f"aufgehend {'ja' if gelesen == gezaehlt - fort + nicht + aus else 'nein'}")
    return 0


def zeitreihe(orakel: str, spalte: str, regelsatz: str) -> int:
    ist = laeufe_lesen(regelsatz)
    with open(orakel, newline="") as f:
        soll = {r["monat"]: int(r[spalte]) for r in csv.DictReader(f, delimiter=";")}
    abweichend = []
    for monat, wert in sorted(soll.items()):
        z = ist.get(monat)
        summe = z[2] if z else None
        if summe != wert:
            abweichend.append((monat, wert, summe))
    print(f"monate {len(soll)}")
    print(f"mit_lauf {sum(1 for m in soll if m in ist)}")
    print(f"abweichend {len(abweichend)}")
    for monat, wert, summe in abweichend[:10]:
        print(f"  {monat}: soll {wert}, ist {summe}")
    return 0 if not abweichend else 1


def laeufe(manifest: str, regelsatz: str) -> int:
    ist = laeufe_lesen(regelsatz)
    with open(manifest, newline="", encoding="utf-8") as f:
        soll = {r["monat"]: r for r in csv.DictReader(f)}
    gleich = sum(1 for m, r in soll.items() if m in ist and ist[m][6] == r["ergebnis_hash"])
    nach = sum(int(r.get("nach_laufmonat") or 0) for r in soll.values())
    print(f"manifest_monate {len(soll)}")
    print(f"db_monate {len(ist)}")
    print(f"hash_gleich {gleich}")
    print(f"nach_laufmonat {nach}")
    return 0 if gleich == len(soll) == len(ist) and nach == 0 else 1


REGELN_AKTIV = """
select count(*) filter (where aktiv), count(*) filter (where aktiv and freigegeben_von is not null)
from meta.regel where regelsatz = %s
"""


def regelsaetze(namen: list[str]) -> int:
    """Aktive und freigegebene Regeln je Regelsatz; auf frischer Prüf-DB zeigt das, ob `db init` sie lädt."""
    leer = 0
    with psycopg.connect(os.environ["UC3_DATABASE_URL"], connect_timeout=5) as verbindung:
        verbindung.read_only = True
        for name in namen:
            aktiv, frei = verbindung.execute(REGELN_AKTIV, (name,)).fetchone()
            print(f"regelsatz {name} aktiv {aktiv} freigegeben {frei}")
            leer += aktiv == 0
    print(f"regelsaetze_ohne_aktive_regel {leer}")
    return 0 if leer == 0 else 1


def main() -> int:
    ap = argparse.ArgumentParser()
    unter = ap.add_subparsers(dest="befehl", required=True)
    a1 = unter.add_parser("abrechnung")
    a1.add_argument("lieferung")
    a2 = unter.add_parser("zeitreihe")
    a2.add_argument("--orakel", required=True)
    a2.add_argument("--spalte", required=True)
    a3 = unter.add_parser("laeufe")
    a3.add_argument("--manifest", required=True)
    for p in (a1, a2, a3):
        p.add_argument("--regelsatz", default="v1")
    a4 = unter.add_parser("regelsaetze")
    a4.add_argument("namen", nargs="+")
    a = ap.parse_args()
    if a.befehl == "regelsaetze":
        return regelsaetze(a.namen)
    if a.befehl == "abrechnung":
        return abrechnung(a.lieferung, a.regelsatz)
    if a.befehl == "zeitreihe":
        return zeitreihe(a.orakel, a.spalte, a.regelsatz)
    return laeufe(a.manifest, a.regelsatz)


if __name__ == "__main__":
    sys.exit(main())
