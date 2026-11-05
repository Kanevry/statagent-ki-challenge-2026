#!/usr/bin/env python3
"""Schreibt docs/praesentation/skript-management.md aus den Sprechernotizen der Management-Folien.

Die Notizen in web/content/slides-management/ sind die einzige Quelle,
damit Folie und Skript nicht auseinanderlaufen.
Aufruf aus der Repo-Wurzel: python3 docs/praesentation/werkzeug/skript_management.py [--check]
--check schreibt nichts und endet mit Exit 1, wenn die Datei nicht zum Stand der Folien passt.
"""

import re
import sys
from pathlib import Path

ORDNER = Path("web/content/slides-management")
ZIEL = Path("docs/praesentation/skript-management.md")
TEMPO = 130  # Wörter je Minute


def wert(kopf: str, schluessel: str) -> str:
    treffer = re.search(rf"^{schluessel}: *(.*)$", kopf, re.M)
    return treffer.group(1).strip().strip('"') if treffer else ""


def folien() -> list[dict[str, str]]:
    ergebnis = []
    for datei in sorted(ORDNER.glob("[0-9][0-9]-*.md")):
        text = datei.read_text(encoding="utf-8")
        _, kopf, rest = text.split("---\n", 2)
        inhalt, _, notizen = rest.partition("## Sprechernotizen")
        h1 = re.search(r"^# (.+)$", inhalt, re.M)
        ergebnis.append(
            {
                "titel": h1.group(1) if h1 else wert(kopf, "titel"),
                "zeit": wert(kopf, "zeit"),
                "dauer": wert(kopf, "dauer_s"),
                "belege": wert(kopf, "belege").strip("[]"),
                "notizen": notizen.strip(),
            }
        )
    return ergebnis


def woerter(notizen: str) -> int:
    return len(notizen.replace("[→]", " ").split())


def baue() -> str:
    alle = folien()
    zeilen = [
        "# Sprech-Skript Management: 10 Minuten",
        "",
        "Erzeugt aus den Sprechernotizen in `web/content/slides-management/` mit "
        "`docs/praesentation/werkzeug/skript_management.py`. "
        "Änderungen gehören in die Folien, nicht hierher. "
        "Folien: `/praesentation/management`, Antworten für die 5 Minuten danach: `management-faq.md`.",
        "",
        "Das Zeichen „→“ steht vor dem Satz, der mit dem Klick kommt. "
        "Kennungen wie F11 stehen im Belegregister und werden nicht mitgesprochen.",
        "",
    ]
    for nr, f in enumerate(alle, 1):
        zeilen += [f"## Folie {nr} · {f['titel']} · {f['zeit']}", ""]
        for absatz in f["notizen"].splitlines():
            if absatz.strip():
                zeilen.append("> " + absatz.strip().replace("[→]", "→"))
                zeilen.append(">")
        if zeilen[-1] == ">":
            zeilen.pop()
        zeilen += ["", f"Belege: {f['belege'] or 'keine Zahl'}.", ""]
    zeilen += [
        "## Zeittabelle",
        "",
        f"Geschätzt mit {TEMPO} Wörtern je Minute. Gemessen wird in der Probe (`probe.md`).",
        "",
        "| Folie | Soll (s) | Wörter | Schätzung (s) |",
        "|---|---|---|---|",
    ]
    soll = wort = schaetzung = 0
    for nr, f in enumerate(alle, 1):
        w = woerter(f["notizen"])
        s = round(w * 60 / TEMPO)
        soll += int(f["dauer"])
        wort += w
        schaetzung += s
        zeilen.append(f"| {nr} | {f['dauer']} | {w} | {s} |")
    zeilen += [f"| **Summe** | **{soll}** | **{wort}** | **{schaetzung}** |", ""]
    return "\n".join(zeilen)


def main() -> int:
    neu = baue()
    if "--check" in sys.argv:
        ok = ZIEL.exists() and ZIEL.read_text(encoding="utf-8") == neu
        print("Skript passt zu den Folien" if ok else "Skript passt NICHT zu den Folien, neu erzeugen")
        return 0 if ok else 1
    ZIEL.write_text(neu, encoding="utf-8")
    print(f"{ZIEL} geschrieben")
    return 0


if __name__ == "__main__":
    sys.exit(main())
