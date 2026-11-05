"""Prüft abgabe/manifest.json (#20 AC1): je Datei Name, Größe, SHA256, Regelsatz und Stand, Werte stimmen.

    python3 tests/abnahme/p/uc3_manifest.py [abgabe/manifest.json]

Akzeptiert eine Liste oder ein Objekt mit Liste unter ``dateien``. Dateien mit Einzeldaten (Ministerium)
liegen nicht im Repo: für sie muss die SHA256 dem Beleg ``<name>.beleg.md`` entsprechen.
Exit 0 nur ohne Abweichung.
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path

FELDER = {
    "dateiname": ("dateiname", "datei", "name", "pfad"),
    "groesse": ("groesse", "größe", "bytes", "size"),
    "sha256": ("sha256",),
    "regelsatz": ("regelsatz",),
    "stand": ("stand", "datenstand"),
}


def feld(eintrag: dict, schluessel: tuple[str, ...]) -> object:
    return next((eintrag[k] for k in schluessel if k in eintrag), None)


def main(pfad: str = "abgabe/manifest.json") -> int:
    datei = Path(pfad)
    if not datei.is_file():
        print("manifest fehlt")
        return 1
    daten = json.loads(datei.read_text(encoding="utf-8"))
    eintraege = daten.get("dateien", []) if isinstance(daten, dict) else daten
    abweichend: list[str] = []
    for e in eintraege:
        fehlend = [n for n, k in FELDER.items() if feld(e, k) in (None, "")]
        name = str(feld(e, FELDER["dateiname"]))
        if fehlend:
            abweichend.append(f"{name}: ohne {', '.join(fehlend)}")
            continue
        ziel = datei.parent / name if not Path(name).is_absolute() else Path(name)
        if not ziel.exists() and Path(name).exists():
            ziel = Path(name)
        if ziel.is_file():
            roh = ziel.read_bytes()
            if hashlib.sha256(roh).hexdigest() != feld(e, FELDER["sha256"]) or len(roh) != int(
                str(feld(e, FELDER["groesse"]))
            ):
                abweichend.append(f"{name}: Größe oder SHA256 anders")
            continue
        beleg = datei.parent / f"{Path(name).stem}.beleg.md"
        treffer = beleg.is_file() and re.search(
            r"^\| sha256 \| `([0-9a-f]{64})` \|$", beleg.read_text(encoding="utf-8"), re.M
        )
        if not treffer or treffer.group(1) != feld(e, FELDER["sha256"]):
            abweichend.append(f"{name}: weder im Repo noch per Beleg belegt")
    print(f"manifest_dateien {len(eintraege)}")
    for zeile in abweichend[:10]:
        print(f"  {zeile}")
    print(f"manifest_abweichend {len(abweichend)}")
    return 0 if eintraege and not abweichend else 1


if __name__ == "__main__":
    sys.exit(main(*sys.argv[1:]))
