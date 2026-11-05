"""Erzeugt docs/praesentation/screens-manifest.md aus quellen.json und den PNGs SC01–SC12 (GitLab #88).

Ohne Option: Manifest schreiben und Stand melden. Mit --check: Exit 0 nur, wenn alle nicht
entfallenen Bilder vorhanden, gültig (PNG, Breite >= 1920) und vollständig belegt sind (#134).
Entfallen ist ein Eintrag mit art "offen" und einem Hinweis, der mit „entfällt“ beginnt.
Alle Ausgaben gehen nach stdout, der Exit-Code ist das Urteil. Nur Standardbibliothek.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import struct
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ANZAHL = 12
MIN_BREITE = 1920
PNG_SIGNATUR = b"\x89PNG\r\n\x1a\n"
QUELLEN = {"oberflaeche", "terminal", "datei", "pen"}
ARTEN_GUELTIG = {"live", "testdaten", "aufzeichnung"}
ARTEN = ARTEN_GUELTIG | {"offen"}
# Wörter im Hinweis, die einem als live ausgegebenen Bild widersprechen (ohne Groß-/Kleinschreibung).
NICHT_LIVE = ("mock", "testdaten", "aufzeichnung")
# Pflichtschlüssel in quellen.json. pen_frame ist seit 05.11. optional (UI-Regie ersetzt Pen-Frames).
FELDER = (
    "bild",
    "motiv",
    "folie",
    "quelle",
    "route",
    "commit",
    "lauf",
    "art",
    "aufgenommen_am",
    "hinweis",
)


@dataclass
class Bildinfo:
    vorhanden: bool
    breite: int | None = None
    hoehe: int | None = None
    sha256: str | None = None
    fehler: str | None = None


def standard_wurzel() -> Path:
    """Repo-Wurzel: drei Ebenen über docs/praesentation/werkzeug/."""
    return Path(__file__).resolve().parents[3]


def bild_pfad(screens: Path, bild: Any) -> Path | None:
    """Pfad zu <bild>.png innerhalb von screens/, oder None bei unzulässigem Bildnamen.

    Abgelehnt werden Nicht-Strings, leere Namen, Trenner, `..` und alles, was aufgelöst
    außerhalb von screens/ landet. Geprüft wird vor jedem Dateizugriff.
    """
    if not isinstance(bild, str) or not bild or bild in {".", ".."}:
        return None
    if "/" in bild or "\\" in bild or ".." in bild or Path(bild).is_absolute():
        return None
    basis = screens.resolve()
    pfad = (basis / f"{bild}.png").resolve()
    if not pfad.is_relative_to(basis) or pfad.parent != basis:
        return None
    return pfad


def ist_entfallen(eintrag: dict[str, Any]) -> bool:
    """Entfallen: art offen und Hinweis beginnt mit „entfällt“."""
    hinweis = str(eintrag.get("hinweis") or "").strip().casefold()
    return eintrag.get("art") == "offen" and hinweis.startswith("entfällt")


def png_lesen(pfad: Path | None) -> Bildinfo:
    """Prüft die PNG-Signatur und liest Breite und Höhe aus dem IHDR-Chunk."""
    if pfad is None:
        return Bildinfo(vorhanden=False, fehler="Bildname unzulässig, nicht gelesen")
    if not pfad.is_file():
        return Bildinfo(vorhanden=False)
    try:
        daten = pfad.read_bytes()
    except OSError as fehler:
        return Bildinfo(vorhanden=True, fehler=f"nicht lesbar ({fehler.strerror})")
    sha = hashlib.sha256(daten).hexdigest()
    if len(daten) < 24 or daten[:8] != PNG_SIGNATUR:
        return Bildinfo(vorhanden=True, sha256=sha, fehler="keine PNG-Signatur")
    if daten[12:16] != b"IHDR":
        return Bildinfo(vorhanden=True, sha256=sha, fehler="erster Chunk ist nicht IHDR")
    breite, hoehe = struct.unpack(">II", daten[16:24])
    return Bildinfo(vorhanden=True, breite=breite, hoehe=hoehe, sha256=sha)


def eintrag_befunde(eintrag: dict[str, Any], info: Bildinfo) -> list[str]:
    """Befunde für --check zu einem Bild."""
    befunde: list[str] = []
    bild = eintrag.get("bild", "?")
    if info.fehler:
        befunde.append(f"{bild}: {info.fehler}")
    elif not info.vorhanden:
        befunde.append(f"{bild}: Datei fehlt")
    elif info.breite is not None and info.breite < MIN_BREITE:
        befunde.append(f"{bild}: Breite {info.breite} < {MIN_BREITE}")
    if not eintrag.get("route") and not eintrag.get("quelle"):
        befunde.append(f"{bild}: weder route noch quelle gesetzt")
    if eintrag.get("quelle") and eintrag["quelle"] not in QUELLEN:
        befunde.append(f"{bild}: quelle {eintrag['quelle']} unbekannt")
    if not eintrag.get("commit"):
        befunde.append(f"{bild}: commit fehlt")
    art = eintrag.get("art")
    if art not in ARTEN_GUELTIG:
        befunde.append(f"{bild}: art {art} ist nicht live, testdaten oder aufzeichnung")
    if art in ARTEN_GUELTIG and not eintrag.get("lauf"):
        befunde.append(f"{bild}: lauf fehlt")
    hinweis = str(eintrag.get("hinweis") or "").casefold()
    if art == "live" and any(wort in hinweis for wort in NICHT_LIVE):
        befunde.append(f"{bild}: art live, aber hinweis nennt Mock, Testdaten oder Aufzeichnung")
    return befunde


def quellen_laden(pfad: Path) -> tuple[list[dict[str, Any]], list[str]]:
    befunde: list[str] = []
    if not pfad.is_file():
        return [], [f"{pfad.name}: fehlt"]
    try:
        daten = json.loads(pfad.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as fehler:
        return [], [f"{pfad.name}: nicht lesbar ({fehler})"]
    if not isinstance(daten, list):
        return [], [f"{pfad.name}: ist keine Liste"]
    erwartet = [f"SC{n:02d}" for n in range(1, ANZAHL + 1)]
    bilder = [e.get("bild") for e in daten if isinstance(e, dict)]
    if len(daten) != ANZAHL or bilder != erwartet:
        befunde.append(f"{pfad.name}: erwartet genau {ANZAHL} Einträge SC01–SC12 in Reihenfolge")
    for eintrag in daten:
        if not isinstance(eintrag, dict):
            continue
        fehlend = [feld for feld in FELDER if feld not in eintrag]
        if fehlend:
            befunde.append(f"{eintrag.get('bild', '?')}: Felder fehlen: {', '.join(fehlend)}")
        if eintrag.get("art") not in ARTEN:
            befunde.append(f"{eintrag.get('bild', '?')}: art {eintrag.get('art')} unbekannt")
    return [e for e in daten if isinstance(e, dict)], befunde


def zelle(wert: Any) -> str:
    if wert is None or wert == "":
        return "–"
    return str(wert).replace("|", "\\|")


def manifest_schreiben(
    ziel: Path, eintraege: list[dict[str, Any]], infos: dict[str, Bildinfo], stand: str
) -> None:
    zeilen = [
        "# Screens-Manifest SC01 bis SC12",
        "",
        "Erzeugt von `docs/praesentation/werkzeug/screens_manifest.py` aus `screens/quellen.json` "
        "und den Bilddateien; nicht von Hand bearbeiten.",
        "Je Bild stehen Herkunft (Route, Commit, Lauf) und Art (live, Testdaten, Aufzeichnung), "
        "damit kein Bild aus Testdaten als Live-Lauf ausgegeben wird.",
        "",
        "| Bild | Motiv | Folie | Datei vorhanden | Breite | Höhe | SHA-256 | Route | Commit "
        "| Lauf | Art | aufgenommen am |",
        "|---|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    fussnoten: list[str] = []
    for eintrag in eintraege:
        bild = str(eintrag.get("bild"))
        info = infos[bild]
        if info.sha256:
            sha = f"`{info.sha256[:16]}`[^{bild}]"
            fussnoten.append(f"[^{bild}]: `{info.sha256}`")
        else:
            sha = "–"
        vorhanden = "ja" if info.vorhanden else "nein"
        if ist_entfallen(eintrag):
            vorhanden = f"{vorhanden} (entfällt)"
        if info.fehler:
            vorhanden = f"{vorhanden} ({info.fehler})"
        commit = eintrag.get("commit")
        zeilen.append(
            "| "
            + " | ".join(
                [
                    bild,
                    zelle(eintrag.get("motiv")),
                    zelle(eintrag.get("folie")),
                    vorhanden,
                    zelle(info.breite),
                    zelle(info.hoehe),
                    sha,
                    zelle(eintrag.get("route")),
                    zelle(str(commit)[:12] if commit else None),
                    zelle(eintrag.get("lauf")),
                    zelle(eintrag.get("art")),
                    zelle(eintrag.get("aufgenommen_am")),
                ]
            )
            + " |"
        )
    zeilen += ["", stand, ""]
    if fussnoten:
        zeilen += fussnoten + [""]
    ziel.write_text("\n".join(zeilen), encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--wurzel", type=Path, default=standard_wurzel(), help="Repo-Wurzel")
    parser.add_argument("--check", action="store_true", help="Abnahme prüfen statt Manifest schreiben")
    args = parser.parse_args(argv)
    praes = args.wurzel.resolve() / "docs" / "praesentation"
    screens = praes / "screens"

    eintraege, befunde = quellen_laden(screens / "quellen.json")
    infos = {str(e.get("bild")): png_lesen(bild_pfad(screens, e.get("bild"))) for e in eintraege}
    aktiv = [e for e in eintraege if not ist_entfallen(e)]
    entfallen = len(eintraege) - len(aktiv)
    # Auch entfallene Einträge dürfen keinen unzulässigen Bildnamen tragen.
    befunde += [
        f"{e.get('bild', '?')}: {infos[str(e.get('bild'))].fehler}"
        for e in eintraege
        if ist_entfallen(e) and infos[str(e.get("bild"))].fehler
    ]
    pruef: dict[str, list[str]] = {
        str(e.get("bild")): eintrag_befunde(e, infos[str(e.get("bild"))]) for e in aktiv
    }
    soll = ANZAHL - entfallen
    vorhanden = sum(1 for e in aktiv if infos[str(e.get("bild"))].vorhanden)
    gueltig = sum(1 for b in pruef.values() if not b)
    stand = f"Stand: {vorhanden}/{soll} vorhanden, {gueltig}/{soll} gültig"
    if entfallen:
        stand += f", {entfallen} entfallen"

    if not args.check:
        manifest_schreiben(praes / "screens-manifest.md", eintraege, infos, stand)
        for befund in befunde:
            print(befund)
        print(f"screens_manifest: {stand}")
        return 0

    alle = befunde + [b for liste in pruef.values() for b in liste]
    for befund in alle:
        print(befund)
    print(f"screens_manifest --check: {stand}, {len(alle)} Befunde")
    return 0 if not alle and gueltig == soll else 1


if __name__ == "__main__":
    sys.exit(main())
