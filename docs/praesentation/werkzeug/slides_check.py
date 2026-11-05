"""Prüft die 10 Foliendateien web/content/slides/01 bis 10 (Szenen v4, GitLab #89).

Gibt je Befund eine Zeile aus und endet mit Exit 0 nur, wenn alle Folien gültig sind.
Nur Standardbibliothek; das Frontmatter wird selbst geparst (flache key: value-Zeilen).
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ANZAHL = 10  # Szenen v4: 01 bis 10 (Soll 305 s, Demo danach)
MAX_DAUER_S = 600  # Summe aller dauer_s
PFLICHTFELDER = ("titel", "layout", "szene", "zeit", "dauer_s", "belege")
LAYOUTS = {"titel", "text", "schritte", "zahl", "live"}
LAYOUT_ALIASE = {"cover": "titel"}  # alte Namen, die die Runtime weiter versteht
SZENE_MUSTER = re.compile(r"^[a-z0-9-]+$")
DATEINAME = re.compile(r"^(\d{2})-.+\.md$")
GEDANKENSTRICH = re.compile(r" [—–] ")
BELEG_KENNUNG = re.compile(r"^F\d+$")
NOTIZ_KOMMENTAR = "<!-- notizen -->"
# Verboten: Monat als Ziffernfolge. Ganze Datumsmuster JJJJ-MM-TT (Datenmuster) sind keine Monatsangabe.
MONAT_JJJJ_MM = re.compile(r"(?<!\d)\d{4}-\d{2}(?!\d)(?!-\d)")
MONAT_MM_JJJJ = re.compile(r"(?<!\d)\d{2}/\d{4}(?!\d)")
VERBOTENE_WOERTER = re.compile(r"beispiel|platzhalter|generiert", re.IGNORECASE)
# Die Tabelle der Monatswerte darf Monate als Ziffernfolge führen (Datenquelle des Diagramms).
MONATSTABELLE_DATEIEN = {"03-falsche-zahl.md"}


def standard_wurzel() -> Path:
    """Repo-Wurzel: drei Ebenen über docs/praesentation/werkzeug/."""
    return Path(__file__).resolve().parents[3]


def wert_parsen(roh: str) -> str | list[str]:
    """Wandelt einen Frontmatter-Wert in Text oder Liste ([a, b]-Form) um."""
    wert = roh.strip()
    if wert.startswith("[") and wert.endswith("]"):
        innen = wert[1:-1].strip()
        if not innen:
            return []
        return [teil.strip().strip("\"'") for teil in innen.split(",") if teil.strip()]
    if len(wert) >= 2 and wert[0] == wert[-1] and wert[0] in "\"'":
        return wert[1:-1]
    return wert


def frontmatter_trennen(text: str) -> tuple[dict[str, str | list[str]] | None, str, list[str]]:
    """Liefert (Frontmatter, Körper, Befunde). Frontmatter ist None, wenn es fehlt."""
    zeilen = text.splitlines()
    grenzen = [i for i, zeile in enumerate(zeilen) if zeile.strip() == "---"]
    if len(grenzen) < 2 or grenzen[0] != 0:
        return None, text, ["Frontmatter fehlt (erste Zeile und eine weitere Zeile müssen --- sein)"]
    befunde: list[str] = []
    felder: dict[str, str | list[str]] = {}
    for nr, zeile in enumerate(zeilen[1 : grenzen[1]], start=2):
        if not zeile.strip() or zeile.lstrip().startswith("#"):
            continue
        schluessel, trenner, rest = zeile.partition(":")
        if not trenner or not schluessel.strip() or schluessel != schluessel.strip():
            befunde.append(f"Frontmatter-Zeile {nr} ist keine flache key: value-Zeile")
            continue
        felder[schluessel] = wert_parsen(rest)
    koerper = "\n".join(zeilen[grenzen[1] + 1 :])
    return felder, koerper, befunde


def leer(wert: str | list[str] | None) -> bool:
    if wert is None:
        return True
    if isinstance(wert, list):
        return False  # [] ist ein gesetzter Wert (z. B. belege: [])
    return wert.strip() in {"", "null", "~"}


def notiz_index(zeilen: list[str]) -> int | None:
    """Zeile, ab der die Sprechernotizen beginnen (## Sprechernotizen oder <!-- notizen -->)."""
    return next(
        (i for i, zeile in enumerate(zeilen) if zeile.strip() in {"## Sprechernotizen", NOTIZ_KOMMENTAR}),
        None,
    )


def koerper_pruefen(koerper: str, dateiname: str = "", titel_gesetzt: bool = True) -> list[str]:
    befunde: list[str] = []
    zeilen = koerper.splitlines()
    if not titel_gesetzt and not any(zeile.startswith("# ") for zeile in zeilen):
        befunde.append("Körper hat keine #-Überschrift und kein titel")
    ende = notiz_index(zeilen)
    if ende is None:
        befunde.append("Überschrift ## Sprechernotizen fehlt")
    else:
        danach: list[str] = []
        for zeile in zeilen[ende + 1 :]:
            if zeile.startswith("#"):
                break
            danach.append(zeile)
        if not "".join(danach).strip():
            befunde.append("Sprechernotizen sind leer")
    sichtbar = zeilen if ende is None else zeilen[:ende]
    for nr, zeile in enumerate(sichtbar, start=1):
        if GEDANKENSTRICH.search(zeile):
            befunde.append(f"Gedankenstrich als Stilmittel in Körperzeile {nr}")
        if dateiname in MONATSTABELLE_DATEIEN and zeile.lstrip().startswith("|"):
            continue
        if MONAT_JJJJ_MM.search(zeile) or MONAT_MM_JJJJ.search(zeile):
            befunde.append(f"Monat als Ziffernfolge in Körperzeile {nr} (Monat ausschreiben)")
        verboten = VERBOTENE_WOERTER.search(zeile)
        if verboten:
            befunde.append(f"Verbotenes Wort „{verboten.group(0)}“ in sichtbarer Körperzeile {nr}")
    return befunde


def register_kennungen(belegregister: Path) -> set[str]:
    if not belegregister.is_file():
        return set()
    kennungen: set[str] = set()
    for zeile in belegregister.read_text(encoding="utf-8").splitlines():
        treffer = re.match(r"^\|\s*(F\d+)\s*\|", zeile)
        if treffer:
            kennungen.add(treffer.group(1))
    return kennungen


def datei_pruefen(pfad: Path, storyboard: str, kennungen: set[str]) -> tuple[list[str], int]:
    """Prüft eine Folie; liefert (Befunde, dauer_s)."""
    befunde: list[str] = []
    dauer = 0
    felder, koerper, fm_befunde = frontmatter_trennen(pfad.read_text(encoding="utf-8"))
    befunde.extend(fm_befunde)
    if felder is not None:
        for feld in PFLICHTFELDER:
            if leer(felder.get(feld)):
                befunde.append(f"Pflichtfeld {feld} fehlt oder ist leer")
        treffer = DATEINAME.match(pfad.name)
        nummer = felder.get("nummer")
        if treffer and isinstance(nummer, str) and nummer.strip():
            if not nummer.strip().isdigit() or int(nummer) != int(treffer.group(1)):
                befunde.append(f"nummer {nummer} passt nicht zum Dateinamen")
        layout = felder.get("layout")
        if isinstance(layout, str) and layout and layout not in LAYOUTS and layout not in LAYOUT_ALIASE:
            befunde.append(f"layout {layout} ist nicht erlaubt")
        szene = felder.get("szene")
        if isinstance(szene, str) and szene.strip() and not SZENE_MUSTER.match(szene.strip()):
            befunde.append(f"szene {szene} passt nicht zum Muster [a-z0-9-]+")
        if layout == "live":
            route = felder.get("route")
            if not isinstance(route, str) or not route.startswith("/"):
                befunde.append("layout live ohne route, die mit / beginnt")
        dauer_roh = felder.get("dauer_s")
        if isinstance(dauer_roh, str) and dauer_roh.strip():
            if dauer_roh.strip().isdigit():
                dauer = int(dauer_roh)
            else:
                befunde.append(f"dauer_s {dauer_roh} ist keine ganze Zahl")
        belege = felder.get("belege")
        if isinstance(belege, list):
            for kennung in belege:
                if not BELEG_KENNUNG.match(kennung):
                    befunde.append(f"Beleg {kennung} ist keine Kennung Fn (F1, F2 usw.)")
                elif kennung not in kennungen:
                    befunde.append(f"Beleg {kennung} fehlt im Belegregister")
        elif isinstance(belege, str) and belege.strip():
            befunde.append("belege ist keine Liste in [a, b]-Form")
    titel_gesetzt = felder is not None and not leer(felder.get("titel"))
    befunde.extend(koerper_pruefen(koerper, pfad.name, titel_gesetzt))
    if pfad.name not in storyboard and pfad.stem not in storyboard:
        befunde.append("Datei wird in storyboard.md nicht genannt")
    return befunde, dauer


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--wurzel", type=Path, default=standard_wurzel(), help="Repo-Wurzel")
    args = parser.parse_args(argv)
    wurzel: Path = args.wurzel.resolve()

    folien_dir = wurzel / "web" / "content" / "slides"
    storyboard_pfad = wurzel / "docs" / "praesentation" / "storyboard.md"
    storyboard = storyboard_pfad.read_text(encoding="utf-8") if storyboard_pfad.is_file() else ""
    kennungen = register_kennungen(wurzel / "docs" / "praesentation" / "belegregister.md")

    befunde: list[str] = []
    if not storyboard:
        befunde.append(f"{storyboard_pfad.relative_to(wurzel)}: fehlt")
    if not kennungen:
        befunde.append("docs/praesentation/belegregister.md: keine Zeilen | Fn | gefunden")

    # README.md im Ordner ist keine Folie.
    dateien = (
        sorted(p for p in folien_dir.glob("*.md") if p.name != "README.md") if folien_dir.is_dir() else []
    )
    nummern: list[int] = []
    for pfad in dateien:
        treffer = DATEINAME.match(pfad.name)
        if not treffer:
            befunde.append(f"{pfad.name}: Dateiname entspricht nicht NN-*.md")
        else:
            nummern.append(int(treffer.group(1)))
    if len(dateien) != ANZAHL:
        befunde.append(f"slides: {len(dateien)} Dateien statt {ANZAHL}")
    erwartet = set(range(1, ANZAHL + 1))
    fehlend = sorted(erwartet - set(nummern))
    if fehlend or len(nummern) != len(set(nummern)):
        befunde.append(f"slides: Nummern nicht lückenlos 01 bis {ANZAHL:02d} (fehlend {fehlend})")

    gueltig = 0
    summe = 0
    for pfad in dateien:
        datei_befunde, dauer = datei_pruefen(pfad, storyboard, kennungen)
        summe += dauer
        if datei_befunde:
            befunde.extend(f"{pfad.name}: {befund}" for befund in datei_befunde)
        elif DATEINAME.match(pfad.name):
            gueltig += 1
    if summe > MAX_DAUER_S:
        befunde.append(f"slides: Summe dauer_s {summe} > {MAX_DAUER_S}")

    for befund in befunde:
        print(befund)
    if befunde:
        print(f"slides_check: {gueltig}/{ANZAHL} gültig, {len(befunde)} Befunde")
        return 1
    print(f"slides_check: {gueltig}/{ANZAHL} gültig")
    return 0


if __name__ == "__main__":
    sys.exit(main())
