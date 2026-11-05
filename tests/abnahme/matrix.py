#!/usr/bin/env python3
"""Abnahme-Matrix je Bereich aus den GitLab-Issues und der Belegdatei.

Liest alle Issues des Projekts, zieht jedes Kriterium heraus (Checkbox oder Text
unter einer Abnahme-Überschrift) und führt es mit dem jüngsten Beleg aus
`docs/abnahme/belege.jsonl` zusammen. Ergebnis: `docs/abnahme/matrix-<bereich>.md`
und ein Zähler je Bereich. Das Skript rechnet die Zahlen, nicht der Prüfer.

Befehle (alle ohne Sprachmodell, nur Standardbibliothek und `glab`):

    uv run python tests/abnahme/matrix.py schreiben            # Matrix und Zähler
    uv run python tests/abnahme/matrix.py zaehler              # nur Zähler
    uv run python tests/abnahme/matrix.py liste --bereich uc3  # Kriterien als JSON
    uv run python tests/abnahme/matrix.py einlesen <datei>     # Belege anhängen (JSONL)
    uv run python tests/abnahme/matrix.py abhaken <id> [--ja]  # Checkbox abhaken, nur mit Beleg

Ein Beleg ist eine JSON-Zeile mit `id`, `hash`, `stand`, `befehl`, `ausgabe` oder
`datei`, `sha`, `zeit`, `pruefer`. Der jüngste Beleg je `id` gilt. Passt der `hash`
nicht mehr zum Kriterium (Issue geändert), gilt das Kriterium als nicht geprüft.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path

PROJEKT = "259"
WURZEL = Path(__file__).resolve().parents[2]
BELEGE = WURZEL / "docs" / "abnahme" / "belege.jsonl"
AUSGABE = WURZEL / "docs" / "abnahme"

STAENDE = ("bestanden", "nicht bestanden", "nicht geprüft", "nach Abgabe")
BEREICHE = ("uc3", "uc1", "uc2", "plattform")
TITEL = {
    "uc3": "UC3 StatAgent (bewertet)",
    "uc1": "UC1 SV KI-Lotse",
    "uc2": "UC2 HealthPolicy Simulator",
    "plattform": "Plattform: E0, E5 Präsentation, E6 Abgabe, UC4, E4",
}

# Überschriften, unter denen Kriterien auch ohne Checkbox stehen.
ABNAHME_KOPF = re.compile(
    r"^(#{1,6})\s*(Akzeptanzkriterien|Akzeptanz|Messbare Abnahmen|Fertig,? wenn|AC)\b", re.I
)
KOPF = re.compile(r"^(#{1,6})\s")
CHECKBOX = re.compile(r"^\s*[-*+]\s+\[( |x|X)\]\s+(.*\S)\s*$")
PUNKT = re.compile(r"^\s{0,3}(?:[-*+]|\d+[.)])\s+(.*\S)\s*$")

# Was nie in eine Datei, ein Issue oder eine Nachricht darf.
VERBOTEN = re.compile(
    r"(/Users/|/home/|\.local\b|m5-remote|win-wsl|\b\d{1,3}(?:\.\d{1,3}){3}\b|://[^@\s/]+:[^@\s/]+@)"
)


def glab_json(pfad: str) -> object:
    aus = subprocess.run(["glab", "api", pfad], capture_output=True, text=True, check=True)
    return json.loads(aus.stdout)


def issues_holen(cache: Path | None) -> list[dict]:
    if cache and cache.exists():
        return json.loads(cache.read_text())
    alle: list[dict] = []
    seite = 1
    while True:
        teil = glab_json(f"projects/{PROJEKT}/issues?per_page=100&page={seite}&state=all")
        if not teil:
            break
        alle.extend(teil)
        seite += 1
    if cache:
        cache.write_text(json.dumps(alle))
    return alle


def bereich(labels: list[str]) -> str:
    s = set(labels)
    if s & {"uc3", "epic::e1-uc3"}:
        return "uc3"
    if s & {"uc1", "epic::e2-uc1"}:
        return "uc1"
    if s & {"uc2", "epic::e3-uc2"}:
        return "uc2"
    return "plattform"


def teilbereich(issue: dict) -> str:
    titel = issue["title"]
    labels = set(issue["labels"])
    if re.search(r"\bE7\b|\bE7-|\bUC4\b", titel):
        return "UC4"
    for label, name in (
        ("epic::e6-abgabe", "E6"),
        ("epic::e5-praesentation", "E5"),
        ("epic::e4-daten", "E4"),
        ("epic::e0-plattform", "E0"),
    ):
        if label in labels:
            return name
    return {"uc3": "UC3", "uc1": "UC1", "uc2": "UC2"}.get(bereich(issue["labels"]), "E0")


def norm(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def kriterium_hash(text: str) -> str:
    return hashlib.sha1(norm(text).encode()).hexdigest()[:10]


def kriterien(issue: dict) -> list[dict]:
    """Kriterien in der Reihenfolge der Beschreibung: Checkboxen überall, Text nur unter Abnahme-Köpfen."""
    zeilen = (issue.get("description") or "").splitlines()
    aus: list[dict] = []
    im_abschnitt = 0  # Ebene der Abnahme-Überschrift, 0 = außerhalb
    im_code = False
    for nr, zeile in enumerate(zeilen):
        if zeile.lstrip().startswith("```"):
            im_code = not im_code
            continue
        if im_code:
            continue
        k = KOPF.match(zeile)
        if k:
            ebene = len(k.group(1))
            if ABNAHME_KOPF.match(zeile):
                im_abschnitt = ebene
            elif im_abschnitt and ebene <= im_abschnitt:
                im_abschnitt = 0
            continue
        c = CHECKBOX.match(zeile)
        if c:
            aus.append(
                {
                    "art": "checkbox",
                    "abgehakt": c.group(1).lower() == "x",
                    "wortlaut": norm(c.group(2)),
                    "zeile": nr,
                }
            )
            continue
        if im_abschnitt:
            p = PUNKT.match(zeile)
            if p:
                aus.append({"art": "text", "abgehakt": False, "wortlaut": norm(p.group(1)), "zeile": nr})
    for i, k in enumerate(aus, 1):
        k["id"] = f"{issue['iid']}-{i}"
        k["hash"] = kriterium_hash(k["wortlaut"])
    return aus


def alle_kriterien(issues: list[dict]) -> list[dict]:
    zeilen = []
    for issue in sorted(issues, key=lambda i: i["iid"]):
        for k in kriterien(issue):
            k.update(
                {
                    "iid": issue["iid"],
                    "titel": issue["title"],
                    "state": issue["state"],
                    "bereich": bereich(issue["labels"]),
                    "teil": teilbereich(issue),
                    "nach_abgabe": "prio::nach-abgabe" in issue["labels"],
                }
            )
            zeilen.append(k)
    return zeilen


def belege_lesen() -> dict[str, dict]:
    jueng: dict[str, dict] = {}
    if BELEGE.exists():
        for zeile in BELEGE.read_text().splitlines():
            if zeile.strip():
                b = json.loads(zeile)
                jueng[b["id"]] = b  # der jüngste gilt
    return jueng


def stand(k: dict, belege: dict[str, dict]) -> tuple[str, dict | None, str]:
    b = belege.get(k["id"])
    if b and b.get("hash") != k["hash"]:
        return "nicht geprüft", b, "Kriterium seit dem Beleg geändert, neu prüfen"
    if k["nach_abgabe"] and not (b and b["stand"] == "bestanden"):
        return "nach Abgabe", b, "Label prio::nach-abgabe"
    if not b:
        return "nicht geprüft", None, ""
    return b["stand"], b, b.get("grund", "")


def zaehlen(zeilen: list[dict], belege: dict[str, dict]) -> dict[str, Counter]:
    z: dict[str, Counter] = {b: Counter() for b in BEREICHE}
    for k in zeilen:
        z[k["bereich"]][stand(k, belege)[0]] += 1
    return z


def zaehler_text(z: dict[str, Counter], sha: str, zeit: str) -> str:
    teile = [
        f"Zähler {zeit}, main {sha}, Reihenfolge bestanden / nicht bestanden / nicht geprüft / nach Abgabe:"
    ]
    for b in BEREICHE:
        c = z[b]
        teile.append(
            f"{b} {c['bestanden']} / {c['nicht bestanden']} / {c['nicht geprüft']} / {c['nach Abgabe']}"
            f" (von {sum(c.values())})"
        )
    return "\n".join(teile)


def zelle(text: str) -> str:
    return (text or "").replace("|", "\\|").replace("\n", " ").strip()


def beleg_zelle(b: dict | None, grund: str) -> str:
    if not b:
        return zelle(grund)
    teile = []
    if b.get("befehl"):
        teile.append(f"`{zelle(b['befehl'])}`")
    if b.get("ausgabe"):
        teile.append(f"→ {zelle(b['ausgabe'])}")
    if b.get("datei"):
        teile.append(zelle(b["datei"]))
    if grund:
        teile.append(f"({zelle(grund)})")
    return " ".join(teile)


def matrix_schreiben(zeilen: list[dict], belege: dict[str, dict], sha: str, zeit: str) -> None:
    z = zaehlen(zeilen, belege)
    for ber in BEREICHE:
        c = z[ber]
        out = [
            f"# Abnahme-Matrix {TITEL[ber]}",
            "",
            f"Erzeugt von `tests/abnahme/matrix.py` am {zeit} (Europe/Vienna) auf main `{sha}`.",
            "Nicht von Hand ändern. Belege stehen in `docs/abnahme/belege.jsonl`,",
            "der jüngste Eintrag je Kriterium gilt. Ein Kriterium ist nur `bestanden`,",
            "wenn der Prüfer den Befehl in seiner Session ausgeführt und die Ausgabe gelesen hat.",
            "",
            "| Stand | Anzahl |",
            "|---|---:|",
        ]
        out += [f"| {s} | {c[s]} |" for s in STAENDE]
        out += [
            f"| gesamt | {sum(c.values())} |",
            "",
            "| Kriterium | Teil | Art | Kriterium im Wortlaut | Stand | Beleg | main-SHA | Uhrzeit |",
            "|---|---|---|---|---|---|---|---|",
        ]
        for k in (k for k in zeilen if k["bereich"] == ber):
            s, b, grund = stand(k, belege)
            art = ("☑" if k["abgehakt"] else "☐") if k["art"] == "checkbox" else "Text"
            zu = " (geschlossen)" if k["state"] == "closed" else ""
            sha_z = zelle(b["sha"][:8]) if b else ""
            zeit_z = zelle(b["zeit"]) if b else ""
            out.append(
                f"| #{k['id']}{zu} | {k['teil']} | {art} | {zelle(k['wortlaut'])} | {s} "
                f"| {beleg_zelle(b, grund)} | {sha_z} | {zeit_z} |"
            )
        (AUSGABE / f"matrix-{ber}.md").write_text("\n".join(out) + "\n")


def jetzt() -> str:
    return subprocess.run(
        ["date", "+%Y-%m-%d %H:%M"],
        capture_output=True,
        text=True,
        env={"TZ": "Europe/Vienna", "PATH": "/usr/bin:/bin"},
        check=True,
    ).stdout.strip()


def main_sha() -> str:
    return subprocess.run(
        ["git", "-C", str(WURZEL), "rev-parse", "--short=8", "origin/main"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()


def beleg_pruefen(b: dict, bekannt: dict[str, dict]) -> list[str]:
    fehler = []
    for feld in ("id", "hash", "stand", "sha", "zeit", "pruefer"):
        if not b.get(feld):
            fehler.append(f"{b.get('id', '?')}: Feld {feld} fehlt")
    if b.get("stand") not in STAENDE:
        fehler.append(f"{b.get('id')}: Stand {b.get('stand')!r} unbekannt")
    if b.get("stand") in ("bestanden", "nicht bestanden") and not (b.get("befehl") or b.get("datei")):
        fehler.append(f"{b.get('id')}: ohne Befehl oder Datei kein Urteil")
    if b.get("id") in bekannt and bekannt[b["id"]]["hash"] != b.get("hash"):
        fehler.append(f"{b.get('id')}: hash passt nicht zum aktuellen Kriterium")
    if b.get("id") not in bekannt:
        fehler.append(f"{b.get('id')}: kein solches Kriterium")
    if VERBOTEN.search(json.dumps(b, ensure_ascii=False)):
        fehler.append(f"{b.get('id')}: enthält Pfad, Hostnamen, IP oder Zugangsdaten")
    return fehler


def abhaken(issues: list[dict], kid: str, belege: dict[str, dict], ja: bool) -> int:
    iid = int(kid.split("-")[0])
    issue = next(i for i in issues if i["iid"] == iid)
    k = next((k for k in kriterien(issue) if k["id"] == kid), None)
    if not k:
        print(f"{kid}: kein solches Kriterium", file=sys.stderr)
        return 2
    b = belege.get(kid)
    if k["art"] != "checkbox":
        print(f"{kid}: Textkriterium, nichts abzuhaken (Kommentar genügt)", file=sys.stderr)
        return 2
    if not b or b["stand"] != "bestanden" or b["hash"] != k["hash"]:
        print(f"{kid}: kein gültiger Beleg mit Stand bestanden, nicht abgehakt", file=sys.stderr)
        return 3
    if k["abgehakt"]:
        print(f"{kid}: schon abgehakt")
        return 0
    zeilen = issue["description"].splitlines()
    zeilen[k["zeile"]] = re.sub(r"\[ \]", "[x]", zeilen[k["zeile"]], count=1)
    neu = "\n".join(zeilen) + ("\n" if issue["description"].endswith("\n") else "")
    kommentar = (
        f"Abnahme {kid}: **bestanden** (Prüfer {b['pruefer']}, {b['zeit']}, main `{b['sha']}`)\n\n"
        f"Kriterium: {k['wortlaut']}\n\n"
        + (f"Befehl:\n```\n{b['befehl']}\n```\n" if b.get("befehl") else "")
        + (f"Ausgabe:\n```\n{b['ausgabe']}\n```\n" if b.get("ausgabe") else "")
        + (f"Beleg: {b['datei']}\n" if b.get("datei") else "")
        + "\nMatrix: `docs/abnahme/matrix-*.md`, erzeugt von `tests/abnahme/matrix.py`."
    )
    if not ja:
        print(f"Trockenlauf {kid}: würde Zeile {k['zeile'] + 1} abhaken und kommentieren:\n{kommentar}")
        return 0
    subprocess.run(
        ["glab", "api", "-X", "PUT", f"projects/{PROJEKT}/issues/{iid}", "-f", f"description={neu}"],
        capture_output=True,
        text=True,
        check=True,
    )
    subprocess.run(
        ["glab", "api", "-X", "POST", f"projects/{PROJEKT}/issues/{iid}/notes", "-f", f"body={kommentar}"],
        capture_output=True,
        text=True,
        check=True,
    )
    nach = glab_json(f"projects/{PROJEKT}/issues/{iid}")
    neu_k = next(x for x in kriterien(nach) if x["id"] == kid)
    print(f"{kid}: abgehakt={neu_k['abgehakt']}")
    return 0 if neu_k["abgehakt"] else 1


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("befehl", choices=("schreiben", "zaehler", "liste", "einlesen", "abhaken"))
    ap.add_argument("arg", nargs="?")
    ap.add_argument("--bereich", choices=BEREICHE)
    ap.add_argument("--cache", type=Path, help="Issue-Abzug als JSON (zum Wiederholen ohne API)")
    ap.add_argument("--ja", action="store_true", help="abhaken wirklich ausführen")
    a = ap.parse_args()

    issues = issues_holen(a.cache)
    zeilen = alle_kriterien(issues)
    bekannt = {k["id"]: k for k in zeilen}
    belege = belege_lesen()

    if a.befehl == "liste":
        wahl = [k for k in zeilen if not a.bereich or k["bereich"] == a.bereich]
        for k in wahl:
            s, _, grund = stand(k, belege)
            print(
                json.dumps(
                    {x: k[x] for x in ("id", "hash", "teil", "art", "abgehakt", "state", "wortlaut")}
                    | {"stand": s, "grund": grund},
                    ensure_ascii=False,
                )
            )
        return 0
    if a.befehl == "einlesen":
        neu = [json.loads(z) for z in Path(a.arg).read_text().splitlines() if z.strip()]
        fehler = [f for b in neu for f in beleg_pruefen(b, bekannt)]
        if fehler:
            print("\n".join(fehler), file=sys.stderr)
            return 2
        with BELEGE.open("a") as f:
            for b in neu:
                f.write(json.dumps(b, ensure_ascii=False) + "\n")
        print(f"{len(neu)} Belege angehängt")
        return 0
    if a.befehl == "abhaken":
        return abhaken(issues, a.arg, belege, a.ja)

    sha, zeit = main_sha(), jetzt()
    if a.befehl == "schreiben":
        matrix_schreiben(zeilen, belege, sha, zeit)
    print(zaehler_text(zaehlen(zeilen, belege), sha, zeit))
    return 0


if __name__ == "__main__":
    sys.exit(main())
