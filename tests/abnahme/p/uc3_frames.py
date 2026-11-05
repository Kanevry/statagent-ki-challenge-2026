"""Frame-Matrix und Screenshots der UC3-Seiten (#18 AC1), ohne Browser und ohne Datenbank.

    python3 tests/abnahme/p/uc3_frames.py [--ausgenommen SCREEN ...]

Liest web/tests/uc3-frame-matrix.json und misst an den Bildern in docs/plan/uc3/ui-abnahme/, ob je
zugeordnetem Frame eine Route mit Screenshot in 1440x900 und 390x844 vorliegt. Ob eine Frame-ID in der
Pen-Datei existiert, misst dieses Skript nicht: Die Pen-Datei liegt nicht im Repo (Hand-Beleg).
"""

from __future__ import annotations

import argparse
import json
import struct
import sys
from pathlib import Path

MATRIX = Path("web/tests/uc3-frame-matrix.json")
BILDER = Path("docs/plan/uc3/ui-abnahme")
PFLICHT = ("bgAUw", "fFDc8", "L6f3Mp", "P6gBQD")
GROESSEN = {"1440": (1440, 900), "390": (390, 844)}
# Route zum Dateinamen, Benennung aus docs/plan/uc3/ui-abnahme/README.md.
# Nicht-Routen und Platzhalter fehlen hier absichtlich.
BILD_JE_ROUTE = {
    "/uc3": "monatslaeufe",
    "/uc3/laeufe/2025-03": "lauf-2025-03",
    "/uc3/laeufe/2025-10": "lauf-2025-10",
    "/uc3/berichte": "berichte",
    "/uc3/berichte/2025-10": "bericht-2025-10",
    "/uc3/berichte/regeln": "regeln",
    "/uc3/freigaben": "freigaben",
    "/uc3/freigaben?reiter=erledigt": "freigaben-erledigt",
    "/uc3/fragen": "fragen",
    "/uc3/freigaben/[id]": "freigabe-detail",
    "/uc3/klassifikationen": "klassifikationen",
    "Protokoll-Schublade der Shell (GET /api/uc3/protokoll)": "protokoll",
}


def jpeg_groesse(pfad: Path) -> tuple[int, int] | None:
    daten = pfad.read_bytes()
    i = 2
    while i + 9 < len(daten):
        if daten[i] != 0xFF:
            i += 1
            continue
        marke = daten[i + 1]
        if marke in (0xC0, 0xC1, 0xC2):
            hoehe, breite = struct.unpack(">HH", daten[i + 5 : i + 9])
            return breite, hoehe
        i += 2 + struct.unpack(">H", daten[i + 2 : i + 4])[0]
    return None


def bild_fehler(route: str) -> list[str]:
    stamm = BILD_JE_ROUTE.get(route)
    if stamm is None:
        return [f"{route}: kein Bild zugeordnet"]
    fehler = []
    for name, soll in GROESSEN.items():
        pfad = BILDER / f"{stamm}-{name}.jpg"
        if not pfad.is_file():
            fehler.append(f"{pfad.name} fehlt")
        elif jpeg_groesse(pfad) != soll:
            fehler.append(f"{pfad.name} hat {jpeg_groesse(pfad)}")
    return fehler


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ausgenommen", nargs="*", default=[], help="Screens mit Entscheid (entscheide.jsonl)")
    ausgenommen = ap.parse_args().ausgenommen
    if not MATRIX.is_file():
        print("matrix fehlt")
        return 1
    screens = json.loads(MATRIX.read_text(encoding="utf-8"))["screens"]
    alle_frames = {f for s in screens for f in s["frames"]}
    print(f"screens {len(screens)}")
    print(f"pflichtframes_in_matrix {sum(f in alle_frames for f in PFLICHT)} von {len(PFLICHT)}")
    for name in ausgenommen:
        print(f"ausgenommen {name}")
    screens = [s for s in screens if s["screen"] not in ausgenommen]
    ohne_beleg = []
    routen_fehler = []
    for s in screens:
        fehler = [e for r in s["routen"] for e in bild_fehler(r)]
        routen_fehler += fehler
        # Ein Screen ist belegt, wenn mindestens eine Route alle Bilder hat und er überhaupt eine Route nennt.
        if not any(not bild_fehler(r) for r in s["routen"]):
            ohne_beleg.append(s["screen"])
    pflicht_ohne = sorted(
        f for s in screens for f in s["frames"] if f in PFLICHT and s["screen"] in ohne_beleg
    )
    print(f"screens_ohne_bild {len(ohne_beleg)}")
    print(f"pflichtframes_ohne_bild {len(pflicht_ohne)}")
    print(f"routen_ohne_bild {len(routen_fehler)}")
    nicht_entsprechend = [
        s["screen"]
        for s in screens
        if not str(s.get("abnahme", "")).startswith("entspricht") or "teilweise" in str(s.get("abnahme", ""))
    ]
    print(f"screens_ohne_vergleich {len(nicht_entsprechend)}")
    for name in (*ohne_beleg, *nicht_entsprechend):
        print(f"offen {name}")
    for pflicht in pflicht_ohne:
        print(f"offen {pflicht}")
    for e in routen_fehler:
        print(f"route {e}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
