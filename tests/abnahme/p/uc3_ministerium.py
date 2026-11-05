"""Prüft die Ministeriums-Lieferung am externen Ort gegen Beleg und Orakel (Entscheid #16: CSV nie im Repo).

    python3 tests/abnahme/p/uc3_ministerium.py [--csv ../lieferungen/ministerium_2026-07.csv]

Die CSV enthält Einzeldaten (PERSON_ID) und liegt neben dem Checkout in ``lieferungen/`` (wie das Startpaket
``svbox/``). Ausgegeben werden nur Kennzahlen, nie Zeilen. Soll: Kopf der Vorlage, Semikolon, eindeutige
aufsteigend sortierte PERSON_ID, TAGE 200 bis 365, Zeilenzahl und Unbekannt-Zahl wie Orakel-Variante S,
sha256 = Beleg ``abgabe/ministerium_2026-07.beleg.md`` = Orakel. Exit 0 nur, wenn alles stimmt.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import re
import sys
from pathlib import Path

KOPF = ["PERSON_ID", "GESCHLECHT", "GEBURTSJAHR", "TAGE"]


def orakel_zeile(pfad: str, variante: str) -> dict[str, str]:
    """Abgabevariante: Altcodes DA bis DN als Abschnitt C (Entscheid #72, 32.741 Personen)."""
    with open(pfad, newline="", encoding="utf-8") as f:
        return next(
            r
            for r in csv.DictReader(f, delimiter=";")
            if r["variante"] == variante and r["altcodes_DA_DN_als_C"] == "ja"
        )


def nur_beleg(a: argparse.Namespace) -> int:
    soll = orakel_zeile(a.orakel, a.variante)
    text = Path(a.beleg).read_text(encoding="utf-8")
    sha = re.search(r"^\| sha256 \| `([0-9a-f]{64})` \|$", text, re.M)
    zeilen = re.search(r"^\| Zeilen \| (\d+) Personen", text, re.M)
    pruefungen = {
        "beleg_sha256_wie_orakel": bool(sha) and sha.group(1) == soll["sha256_monat13_unbekannt"],
        "beleg_zeilen_wie_orakel": bool(zeilen) and zeilen.group(1) == soll["zeilen"],
    }
    for name, ok in pruefungen.items():
        print(f"{name} {'ja' if ok else 'nein'}")
    abweichend = sum(not ok for ok in pruefungen.values())
    print(f"abweichend {abweichend}")
    return 0 if not abweichend else 1


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", default="../lieferungen/ministerium_2026-07.csv")
    ap.add_argument("--beleg", default="abgabe/ministerium_2026-07.beleg.md")
    ap.add_argument("--orakel", default="tests/abnahme/orakel/ministerium-varianten.csv")
    ap.add_argument("--variante", default="S")
    ap.add_argument("--nur-beleg", action="store_true", help="ohne CSV: Beleg gegen Orakel (Prüfrechner)")
    a = ap.parse_args()

    if a.nur_beleg:
        return nur_beleg(a)
    pfad = Path(a.csv)
    if not pfad.is_file():
        print("csv fehlt am externen Ort")
        return 1
    soll = orakel_zeile(a.orakel, a.variante)
    roh = pfad.read_bytes()
    sha = hashlib.sha256(roh).hexdigest()
    beleg = Path(a.beleg).read_text(encoding="utf-8")
    treffer = re.search(r"^\| sha256 \| `([0-9a-f]{64})` \|$", beleg, re.M)
    beleg_sha = treffer.group(1) if treffer else None

    zeilen = roh.decode("utf-8").splitlines()
    kopf = zeilen[0].split(";") if zeilen else []
    daten = [z.split(";") for z in zeilen[1:]]
    ids = [z[0] for z in daten]
    tage = [int(z[3]) for z in daten if len(z) == 4 and z[3].isdigit()]
    unbekannt = sum(1 for z in daten if len(z) == 4 and z[2] == "Unbekannt")
    pruefungen = {
        "kopf_wie_vorlage": kopf == KOPF,
        "vier_felder_je_zeile": all(len(z) == 4 for z in daten),
        "person_id_eindeutig_aufsteigend": len(set(ids)) == len(ids) and ids == sorted(ids),
        "tage_200_bis_365": len(tage) == len(daten) and all(200 <= t <= 365 for t in tage),
        "zeilen_wie_orakel": len(daten) == int(soll["zeilen"]),
        "unbekannt_wie_orakel": unbekannt == int(soll["geburtsjahr_unbekannt_bei_monat13_unbekannt"]),
        "sha256_wie_beleg": sha == beleg_sha,
        "sha256_wie_orakel": sha == soll["sha256_monat13_unbekannt"],
    }
    print(f"zeilen {len(daten)}")
    print(f"tage_min {min(tage) if tage else '-'} tage_max {max(tage) if tage else '-'}")
    print(f"unbekannt {unbekannt}")
    print(f"sha256 {sha[:12]}")
    for name, ok in pruefungen.items():
        print(f"{name} {'ja' if ok else 'nein'}")
    abweichend = [n for n, ok in pruefungen.items() if not ok]
    print(f"abweichend {len(abweichend)}")
    return 0 if not abweichend else 1


if __name__ == "__main__":
    sys.exit(main())
