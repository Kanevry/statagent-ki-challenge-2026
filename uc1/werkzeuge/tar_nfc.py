"""Korpus byte-genau zwischen Rechner A und Rechner B kopieren (#29).

bsdtar auf macOS legte Dateinamen mit Umlaut („ÖGK …“) auf Rechner B als NFD an, auf Rechner A stehen
sie als NFC. Weil `dokid` für PDFs der Dateipfad ist, wich dadurch der Inhalts-Hash ab, obwohl alle
Text-Hashes gleich waren. Dieses Skript packt und entpackt mit Pythons tarfile, das Namen als Bytes
übernimmt, und lässt AppleDouble-Dateien (`._*`) weg.

    python -I werkzeuge/tar_nfc.py packen <verzeichnis> <archiv.tgz>
    python -I werkzeuge/tar_nfc.py entpacken <archiv.tgz> <zielverzeichnis>
"""

from __future__ import annotations

import sys
import tarfile
import unicodedata
from pathlib import Path


def packen(quelle: Path, archiv: Path) -> int:
    anzahl = 0
    with tarfile.open(archiv, "w:gz", format=tarfile.PAX_FORMAT) as tar:
        for pfad in sorted(quelle.rglob("*")):
            if pfad.name.startswith("._") or pfad.name == ".DS_Store" or not pfad.is_file():
                continue
            name = pfad.relative_to(quelle).as_posix()
            if unicodedata.normalize("NFC", name) != name:
                print(f"warnung: Name nicht NFC: {name!r}", file=sys.stderr)
            tar.add(pfad, arcname=name, recursive=False)
            anzahl += 1
    return anzahl


def entpacken(archiv: Path, ziel: Path) -> int:
    ziel.mkdir(parents=True, exist_ok=True)
    with tarfile.open(archiv, "r:gz") as tar:
        mitglieder = tar.getmembers()
        tar.extractall(ziel, filter="data")
    return len(mitglieder)


def main(argv: list[str]) -> int:
    if len(argv) != 3 or argv[0] not in {"packen", "entpacken"}:
        print(__doc__, file=sys.stderr)
        return 2
    befehl, a, b = argv
    anzahl = packen(Path(a), Path(b)) if befehl == "packen" else entpacken(Path(a), Path(b))
    print(f"{befehl} {anzahl} Dateien")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
