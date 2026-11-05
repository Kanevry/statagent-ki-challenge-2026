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
import os
import re
import subprocess
import sys
import time
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
CHECKBOX = re.compile(r"^\s*(?:[-*+]|\d+[.)])\s+\[( |x|X)\]\s+(.*\S)\s*$")
PUNKT = re.compile(r"^\s{0,3}(?:[-*+]|\d+[.)])\s+(.*\S)\s*$")
FORTSETZUNG = re.compile(r"^\s{2,}\S")  # eingerückte Folgezeile gehört zum Kriterium davor
AC_MARKE = re.compile(r"^\**\s*(AC\d+[a-z]?)\s*:")  # „**AC1:**“ ergibt die feste ID <iid>-AC1

# Was nie in Datei, Issue oder Nachricht darf (öffentliches Repo): Pfade auf Rechnern, Rechnernamen,
# Hostnamen, IP-Adressen außer Loopback, Zugangsdaten in URLs. Konkrete Rechner- und Nutzernamen stehen
# nicht im Repo, sondern je Zeile ein Regex in der Datei aus ABNAHME_SPERRNAMEN
# (Standard: .config/kic-abnahme/sperrnamen im Home-Verzeichnis).
_SPERRDATEI = Path(
    os.environ.get("ABNAHME_SPERRNAMEN", Path.home() / ".config" / "kic-abnahme" / "sperrnamen")
)


def _sperrnamen() -> str:
    if not _SPERRDATEI.is_file():
        return r"(?!)"  # ohne Datei: kein Name (die allgemeinen Muster greifen trotzdem)
    zeilen = [z.strip() for z in _SPERRDATEI.read_text().splitlines() if z.strip() and not z.startswith("#")]
    return "|".join(f"(?:{z})" for z in zeilen) or r"(?!)"


_RECHNER = re.compile(_sperrnamen())
VERBOTEN = re.compile(
    r"(/Users/|/home/|~/|(?<!\.env)\.local\b|\b(?!127\.0\.0\.1\b|0\.0\.0\.0\b)\d{1,3}(?:\.\d{1,3}){3}\b"
    r"|://[^@\s/]+:[^@\s/]+@|" + _RECHNER.pattern + ")"
)
_PFAD = re.compile(r"(?:/Users/|/home/|~/)[^\s'\"`|)\]]*")


def schwaerzen(text: str) -> str:
    """Entfernt Pfade auf Rechnern, Rechnernamen, Hostnamen und fremde IPs (für Repo, Issue, Nachricht)."""
    text = _PFAD.sub("<pfad>", text or "")
    text = _RECHNER.sub("<rechner>", text)
    return VERBOTEN.sub("<entfernt>", text)


def glab_json(pfad: str, versuche: int = 3) -> object:
    """GET über glab; vorübergehende Fehler der API werden bis zu dreimal wiederholt."""
    for nr in range(1, versuche + 1):
        aus = subprocess.run(["glab", "api", pfad], capture_output=True, text=True, cwd=WURZEL)
        if aus.returncode == 0:
            return json.loads(aus.stdout)
        if nr == versuche:
            raise RuntimeError(f"glab api {pfad} scheitert: {aus.stderr.strip()[:200]}")
        time.sleep(2 * nr)
    raise AssertionError("unerreichbar")


def glab_schreiben(methode: str, pfad: str, feld: str, wert: str, versuche: int = 3) -> None:
    """Schreibender Aufruf über glab; vorübergehende Fehler werden wiederholt, sonst klare Meldung."""
    for nr in range(1, versuche + 1):
        aus = subprocess.run(
            ["glab", "api", "-X", methode, f"projects/{PROJEKT}/{pfad}", "-f", f"{feld}={wert}"],
            capture_output=True,
            text=True,
            cwd=WURZEL,
        )
        if aus.returncode == 0:
            return
        if nr == versuche:
            raise RuntimeError(f"glab {methode} {pfad} scheitert: {(aus.stderr or aus.stdout).strip()[:300]}")
        time.sleep(2 * nr)


def issues_holen(cache: Path | None) -> list[dict]:
    if cache and cache.exists():
        return json.loads(cache.read_text())
    alle: list[dict] = []
    seite = 1
    while True:
        teil = glab_json(
            f"projects/{PROJEKT}/issues?per_page=100&page={seite}&state=all&order_by=created_at&sort=asc"
        )
        if not isinstance(teil, list):
            raise RuntimeError(f"Issue-Abruf Seite {seite}: keine Liste, sondern {str(teil)[:120]}")
        if not teil:
            break
        alle.extend(teil)
        seite += 1
    if len({i["iid"] for i in alle}) != len(alle):
        raise RuntimeError("Issue-Abruf: doppelte iid, Seiten haben sich während des Abrufs verschoben")
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
    """Kriterien in der Reihenfolge der Beschreibung: Checkboxen überall, Text nur unter Abnahme-Köpfen.

    Der Wortlaut umfasst die erste Zeile und alle eingerückten Folgezeilen (Datenbasis, Abhängigkeiten);
    der Hash deckt den ganzen Block. Kriterien mit Marke „ACn:“ bekommen die feste ID `<iid>-ACn`, alle
    anderen eine laufende Nummer `<iid>-<n>`; verschiebt sich die Nummer, passt der Hash nicht mehr.
    """
    zeilen = (issue.get("description") or "").split("\n")
    aus: list[dict] = []
    im_abschnitt = 0  # Ebene der Abnahme-Überschrift, 0 = außerhalb
    im_code = False
    offen: dict | None = None  # Kriterium, an das Folgezeilen angehängt werden
    for nr, zeile in enumerate(zeilen):
        if zeile.lstrip().startswith(("```", "~~~")):
            im_code = not im_code
            offen = None
            continue
        if im_code:
            continue
        if offen and FORTSETZUNG.match(zeile) and not CHECKBOX.match(zeile) and not PUNKT.match(zeile):
            offen["folge"].append(zeile.strip())
            continue
        offen = None
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
            offen = {
                "art": "checkbox",
                "abgehakt": c.group(1).lower() == "x",
                "erste": c.group(2),
                "zeile": nr,
            }
        elif im_abschnitt and (p := PUNKT.match(zeile)):
            offen = {"art": "text", "abgehakt": False, "erste": p.group(1), "zeile": nr}
        if offen:
            offen["folge"] = []
            aus.append(offen)
    if im_code:
        print(
            f"Warnung #{issue['iid']}: Codeblock nicht geschlossen, Kriterien danach fehlen", file=sys.stderr
        )
    lauf_nr = 0
    vergeben: set[str] = set()
    for k in aus:
        k["wortlaut"] = norm(" ".join([k.pop("erste"), *k.pop("folge")]))
        k["hash"] = kriterium_hash(k["wortlaut"])
        marke = AC_MARKE.match(k["wortlaut"])
        kid = f"{issue['iid']}-{marke.group(1)}" if marke else None
        if not kid or kid in vergeben:
            lauf_nr += 1
            kid = f"{issue['iid']}-{lauf_nr}"
        vergeben.add(kid)
        k["id"] = kid
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


ZEIT = re.compile(r"^\d{4}-\d\d-\d\d \d\d:\d\d$")
# Ohne eigene Pfadliste gilt ein Beleg nur, solange sich auf main in den Pfaden seines Bereichs nichts ändert.
# Gemeinsame Teile (shared/, Lockfiles, Wurzel-Konfiguration) zählen überall mit;
# ist eine Abhängigkeit unklar, wird neu gemessen.
GEMEINSAM = ["shared", "pyproject.toml", "uv.lock", "package.json", "pnpm-lock.yaml", "web/package.json"]
STANDARD_PFADE = {
    "uc3": [
        "uc3",
        "abgabe",
        "docs/plan/uc3",
        "web/app/uc3",
        "web/app/api/uc3",
        "web/components/uc3",
        *GEMEINSAM,
    ],
    "uc1": ["uc1", "docs/plan/uc1", "web/app/uc1", "web/app/api/uc1", "web/components/uc1", *GEMEINSAM],
    "uc2": ["uc2", "docs/plan/uc2", "web/app/uc2", "web/app/api/uc2", "web/components/uc2", *GEMEINSAM],
    "plattform": [".", ":(exclude)docs/abnahme", ":(exclude)tests/abnahme"],
}
ABNAHME_SESSION = "b-abnahme"  # Prüfer-Präfix der Abnahme-Lane; Agent-Belege mit „/“ im Namen sind Vorschläge
ENTSCHEIDE = WURZEL / "docs" / "abnahme" / "entscheide.jsonl"


LAEUFE = WURZEL / "docs" / "abnahme" / "laeufe"


def belege_lesen() -> dict[str, list[dict]]:
    """Alle Belege je Kriterium, nach Messzeit aufsteigend (bei gleicher Zeit in Lesereihenfolge).

    Quellen: `belege.jsonl` (von Hand) und alle abgeschlossenen Läufe (`laeufe/*.jsonl` mit Schlusszeile).
    Welcher gilt, entscheidet `beleg_fuer`: der jüngste zum aktuellen Wortlaut, nie einer zu einem alten.
    """
    quellen: list[list[dict]] = []
    if BELEGE.exists():
        quellen.append([json.loads(z) for z in BELEGE.read_text().splitlines() if z.strip()])
    for datei in sorted(LAEUFE.glob("*.jsonl")) if LAEUFE.exists() else []:
        zeilen = [json.loads(z) for z in datei.read_text().splitlines() if z.strip()]
        if zeilen and zeilen[-1].get("abgeschlossen"):
            quellen.append([z for z in zeilen if "id" in z])
    alle: dict[str, list[dict]] = {}
    for quelle in quellen:
        for b in quelle:
            alle.setdefault(b["id"], []).append(b)
    for liste in alle.values():
        liste.sort(key=lambda b: str(b.get("zeit", "")))
    return alle


def git(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", str(WURZEL), *args], capture_output=True, text=True)


_GUELTIG: dict[tuple, str] = {}


def veraltet(b: dict, ziel: str, bereich_name: str) -> str:
    """Leer, wenn der Beleg für den Zielstand gilt; sonst der Grund, warum nicht."""
    pfade = tuple(b.get("pfade") or STANDARD_PFADE[bereich_name])
    schluessel = (b["sha"], ziel, pfade)
    if schluessel not in _GUELTIG:
        voll = git("rev-parse", "--verify", "--quiet", f"{b['sha']}^{{commit}}")
        if voll.returncode != 0:
            _GUELTIG[schluessel] = f"Messstand {b['sha']} unbekannt"
        elif git("merge-base", "--is-ancestor", voll.stdout.strip(), ziel).returncode != 0:
            _GUELTIG[schluessel] = f"Messstand {b['sha']} liegt nicht auf main"
        else:
            diff = git("diff", "--quiet", voll.stdout.strip(), ziel, "--", *pfade)
            _GUELTIG[schluessel] = "" if diff.returncode == 0 else f"main hat sich seit {b['sha']} geändert"
    return _GUELTIG[schluessel]


def entscheide_lesen() -> dict[str, dict]:
    """Entscheide von Lead oder Owner je Kriterium (verschoben oder als Restmangel angenommen), mit Quelle."""
    if not ENTSCHEIDE.exists():
        return {}
    return {e["id"]: e for e in (json.loads(z) for z in ENTSCHEIDE.read_text().splitlines() if z.strip())}


def beleg_fuer(k: dict, belege: dict[str, list[dict]]) -> dict | None:
    """Der jüngste Beleg zum aktuellen Wortlaut (Hash).

    Verschiebt sich die laufende Nummer, wird er über Issue und Hash wiedergefunden. Gibt es keinen zum
    aktuellen Wortlaut, gilt der jüngste überhaupt (die Matrix zeigt dann „Kriterium geändert“).
    """
    eigene = belege.get(k["id"], [])
    passend = [b for b in eigene if b.get("hash") == k["hash"]]
    if not passend:
        passend = [
            b
            for kid, liste in belege.items()
            if kid.split("-")[0] == str(k["iid"])
            for b in liste
            if b.get("hash") == k["hash"]
        ]
    if passend:
        return max(passend, key=lambda b: str(b.get("zeit", "")))
    return eigene[-1] if eigene else None


def ist_vorschlag(b: dict) -> bool:
    """Bestanden zählt nur aus einem Lauf oder von der Abnahme-Session selbst, nicht von einem Mess-Agent."""
    pruefer = str(b.get("pruefer", ""))
    return not (pruefer.startswith("lauf ") or (pruefer.startswith(ABNAHME_SESSION) and "/" not in pruefer))


def stand(k: dict, belege: dict[str, list[dict]], ziel: str | None = None) -> tuple[str, dict | None, str]:
    """Stand eines Kriteriums. `ziel` ist der main-Stand, für den geurteilt wird (Standard origin/main)."""
    b = beleg_fuer(k, belege)
    gemessen, grund = "nicht geprüft", ""
    if b and b.get("hash") != k["hash"]:
        grund = "Kriterium seit dem Beleg geändert, neu prüfen"
    elif b and (alt := veraltet(b, ziel or _ZIEL, k["bereich"])):
        grund = f"Beleg veraltet: {alt}; zuletzt {b['stand']} auf {b['sha']}"
    elif b and b["stand"] == "bestanden" and ist_vorschlag(b):
        grund = f"Vorschlag von {b['pruefer']}, noch nicht reproduziert"
    elif b:
        gemessen, grund = b["stand"], b.get("grund", "")
    if k["nach_abgabe"] and gemessen != "bestanden":
        return "nach Abgabe", b, f"Label prio::nach-abgabe; gemessen: {gemessen}"
    e = _entscheide().get(k["id"])
    if e and e.get("hash") == k["hash"] and e["entscheid"] == "nach Abgabe" and gemessen != "bestanden":
        return "nach Abgabe", b, f"Entscheid: {e['wer']} ({e['quelle']}); gemessen: {gemessen}"
    return gemessen, b, grund


_ENTSCHEIDE: dict[str, dict] | None = None
_ZIEL = "origin/main"  # Zielstand für die Gültigkeit; `zaehler --ziel <sha>` setzt ihn


def _entscheide() -> dict[str, dict]:
    global _ENTSCHEIDE
    if _ENTSCHEIDE is None:
        _ENTSCHEIDE = entscheide_lesen()
    return _ENTSCHEIDE


TEILE = ("UC3", "E6", "UC4", "UC1", "UC2", "E5", "E0", "E4")
TOR_TEILE = ("UC3", "E6")


def zaehlen(zeilen: list[dict], belege: dict[str, list[dict]]) -> dict[str, Counter]:
    """Zähler je Bereich (Matrix-Datei) und je Teil (E6 und UC4 getrennt von E0).

    Zusatzschlüssel: `fehlt` (nicht bestanden, weil etwas auf main fehlt) und `geschlossen` (aus geschlossenen
    Issues), damit der Lead Fachfehler von noch nicht gemergter Arbeit unterscheiden kann.
    """
    z: dict[str, Counter] = {b: Counter() for b in (*BEREICHE, *TEILE)}
    for k in zeilen:
        s, b, grund = stand(k, belege)
        for schluessel in (k["bereich"], k["teil"]):
            z[schluessel][s] += 1
            if s == "nicht bestanden" and b and b.get("befund_art") == "fehlt":
                z[schluessel]["fehlt"] += 1
            if s == "nicht geprüft" and b and b.get("stand") == "bestanden" and "veraltet" in grund:
                z[schluessel]["veraltet_ok"] += 1
            if k["state"] == "closed":
                z[schluessel]["geschlossen"] += 1
    return z


def zaehler_text(z: dict[str, Counter], sha: str, zeit: str) -> str:
    teile = [
        f"Zähler {zeit}, geurteilt für main {sha}:",
        "bestanden / nicht bestanden (davon fehlt auf main) /"
        " nicht geprüft (davon veraltet, zuletzt bestanden) / nach Abgabe",
    ]
    for b in (*BEREICHE, *TEILE):
        c = z[b]
        gesamt = sum(c[s] for s in STAENDE)
        if b in TEILE and not gesamt:
            continue
        name = f"  Teil {b}" if b in TEILE else b
        teile.append(
            f"{name} {c['bestanden']} / {c['nicht bestanden']} ({c['fehlt']}) / "
            f"{c['nicht geprüft']} ({c['veraltet_ok']}) / "
            f"{c['nach Abgabe']} (von {gesamt}, {c['geschlossen']} aus geschlossenen Issues)"
        )
    return "\n".join(teile)


def tor(zeilen: list[dict], belege: dict[str, list[dict]]) -> int:
    """Tor vor dem Merge-Stopp für UC3 und E6.

    Jedes Kriterium ist bestanden, verschoben oder per Entscheid (Lead oder Owner, mit Quelle in
    `entscheide.jsonl`) als Restmangel angenommen. Entschiedenes bleibt sichtbar.
    """
    entscheide = entscheide_lesen()
    offen, entschieden = [], []
    for k in zeilen:
        if k["teil"] not in TOR_TEILE:
            continue
        s, _b, grund = stand(k, belege)
        if s not in ("nicht geprüft", "nicht bestanden"):
            continue
        e = entscheide.get(k["id"])
        (entschieden if e and e.get("hash") == k["hash"] else offen).append((k, s, grund, e))
    for k, s, _grund, e in entschieden:
        print(f"entschieden {k['teil']} {k['id']}: {s}; {e['entscheid']} ({e['wer']}, {e['quelle']})")
    for k, s, grund, _ in offen:
        print(f"OFFEN {k['teil']} {k['id']}: {s}: {grund[:160]}")
    print(
        f"Tor UC3+E6: {'offen' if offen else 'grün'} ({len(offen)} offen, {len(entschieden)} per Entscheid)"
    )
    return 1 if offen else 0


def zelle(text: str) -> str:
    return schwaerzen(text or "").replace("|", "\\|").replace("\n", " ").strip()


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


RASTER = WURZEL / "docs" / "abnahme" / "raster-uc3.csv"


def raster_tabelle(zeilen: list[dict], belege: dict[str, list[dict]]) -> list[str]:
    """Kurztabelle je Bewertungsbereich (UC3-Raster, 6 x 20 Punkte); Zuordnung je Issue aus raster-uc3.csv."""
    if not RASTER.exists():
        return []
    import csv

    out = [
        "",
        "## Je Bewertungsbereich (Jury-Raster)",
        "",
        "Zuordnung je Issue in `docs/abnahme/raster-uc3.csv`; keine Punkteschätzung, nur Kriterienstand.",
        "",
        "| Bereich | bestanden | nicht bestanden | nicht geprüft | nach Abgabe | bestandene Kriterien |",
        "|---|---:|---:|---:|---:|---|",
    ]
    with RASTER.open() as f:
        for r in csv.DictReader(f, delimiter=";"):
            iids = {int(x) for x in r["issues"].split()}
            ks = [k for k in zeilen if k["iid"] in iids]
            st = Counter(stand(k, belege)[0] for k in ks)
            ok = ", ".join(k["id"] for k in ks if stand(k, belege)[0] == "bestanden") or "keins"
            out.append(
                f"| {r['bereich']} | {st['bestanden']} | {st['nicht bestanden']} | {st['nicht geprüft']} "
                f"| {st['nach Abgabe']} | {ok} |"
            )
    return [*out, ""]


def matrix_schreiben(zeilen: list[dict], belege: dict[str, list[dict]], sha: str, zeit: str) -> None:
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
            f"| gesamt | {sum(c[s] for s in STAENDE)} |",
            "",
            "| Kriterium | Teil | Art | Kriterium im Wortlaut | Stand | Beleg | main-SHA | Uhrzeit |",
            "|---|---|---|---|---|---|---|---|",
        ]
        if ber == "uc3":
            out += raster_tabelle([k for k in zeilen if k["bereich"] == ber], belege)
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
    if b.get("stand") == "bestanden" and not (b.get("befehl") and b.get("ausgabe")):
        fehler.append(f"{b.get('id')}: bestanden nur mit ausgeführtem Befehl und gelesener Ausgabe")
    if b.get("deckung") == "teil" and b.get("stand") == "bestanden":
        fehler.append(f"{b.get('id')}: ein Teil-Prüfsatz kann nicht bestanden ergeben")
    if b.get("zeit") and not ZEIT.match(str(b["zeit"])):
        fehler.append(f"{b.get('id')}: zeit nicht in der Form JJJJ-MM-TT HH:MM")
    if b.get("sha") and git("rev-parse", "--verify", "--quiet", f"{b['sha']}^{{commit}}").returncode != 0:
        fehler.append(f"{b.get('id')}: Messstand {b['sha']} ist kein bekannter Commit")
    if b.get("id") in bekannt and bekannt[b["id"]]["hash"] != b.get("hash"):
        fehler.append(f"{b.get('id')}: hash passt nicht zum aktuellen Kriterium")
    if b.get("id") not in bekannt:
        fehler.append(f"{b.get('id')}: kein solches Kriterium")
    if VERBOTEN.search(json.dumps(b, ensure_ascii=False)):
        fehler.append(f"{b.get('id')}: enthält Pfad, Hostnamen, IP oder Zugangsdaten")
    return fehler


def abhaken(kid: str, belege: dict[str, list[dict]], ja: bool) -> int:
    """Hakt eine Checkbox ab, nur mit gültigem Beleg; liest das Issue dafür immer frisch (nie aus dem Cache).

    Wiederholbar: ist der Haken schon gesetzt, wird nur ein fehlender Kommentar nachgeholt (Marke je Beleg).
    """
    iid = int(kid.split("-")[0])
    issue = glab_json(f"projects/{PROJEKT}/issues/{iid}")
    k = next((k for k in alle_kriterien([issue]) if k["id"] == kid), None)
    if not k:
        print(f"{kid}: kein solches Kriterium", file=sys.stderr)
        return 2
    if k["state"] == "closed":
        print(f"{kid}: Issue geschlossen, Matrix-Eintrag genügt, kein Haken", file=sys.stderr)
        return 0
    s, b, grund = stand(k | {"nach_abgabe": False}, belege)
    if s != "bestanden" or not b:
        print(f"{kid}: Stand {s} ({grund}), nicht abgehakt", file=sys.stderr)
        return 3
    # Marke ohne SHA und Zeit: ein Kommentar je Kriterium und Wortlaut, egal wie oft neu gemessen wird.
    marke = f"<!-- abnahme-haken:{kid}:{k['hash']}:bestanden -->"
    kommentar = (
        f"Abnahme {kid}: **bestanden** (Prüfer {b['pruefer']}, {b['zeit']}, main `{b['sha']}`)\n\n"
        f"Kriterium: {k['wortlaut']}\n\n"
        + (f"Befehl:\n```\n{b['befehl']}\n```\n" if b.get("befehl") else "")
        + (f"Ausgabe:\n```\n{b['ausgabe']}\n```\n" if b.get("ausgabe") else "")
        + (f"Beleg: {b['datei']}\n" if b.get("datei") else "")
        + "\nMatrix: `docs/abnahme/matrix-*.md`, erzeugt von `tests/abnahme/matrix.py`.\n"
        + marke
    )
    kommentar = schwaerzen(kommentar.replace(marke, "")) + marke
    if not ja:
        print(f"Trockenlauf {kid}: abgehakt={k['abgehakt']}, Zeile {k['zeile'] + 1}\n{kommentar}")
        return 0
    if k["art"] == "checkbox" and not k["abgehakt"]:
        zeilen = issue["description"].split("\n")
        zeilen[k["zeile"]] = re.sub(r"\[ \]", "[x]", zeilen[k["zeile"]], count=1)
        glab_schreiben("PUT", f"issues/{iid}", "description", "\n".join(zeilen))
    notizen = glab_json(f"projects/{PROJEKT}/issues/{iid}/notes?per_page=100")
    if not any(marke in (n.get("body") or "") for n in notizen):
        glab_schreiben("POST", f"issues/{iid}/notes", "body", kommentar)
    nach = glab_json(f"projects/{PROJEKT}/issues/{iid}")
    neu_k = next(x for x in kriterien(nach) if x["id"] == kid)
    if k["art"] != "checkbox":
        print(f"{kid}: Textkriterium, Beleg-Kommentar gesetzt (kein Haken)")
        return 0
    andere = [x["wortlaut"] for x in kriterien(nach) if x["id"] != kid]
    vorher = [x["wortlaut"] for x in kriterien(issue) if x["id"] != kid]
    print(f"{kid}: abgehakt={neu_k['abgehakt']}, übrige Kriterien unverändert={andere == vorher}")
    return 0 if neu_k["abgehakt"] and andere == vorher else 1


def haken_pruefen(zeilen: list[dict], belege: dict[str, list[dict]], ja: bool) -> int:
    """Haken in offenen Issues, die nicht (mehr) belegt sind, werden entfernt, mit Kommentar.

    Entfernt wird ein Haken, wenn es nie einen Abnahme-Beleg gab (Bau-Lane hakt nie selbst ab) oder wenn der
    jüngste gültige Beleg „nicht bestanden“ sagt (Rückfall). Ein nur veralteter Beleg lässt den Haken stehen,
    bis der nächste Lauf neu urteilt.
    """
    entfernt = 0
    for k in zeilen:
        if k["state"] != "opened" or k["art"] != "checkbox" or not k["abgehakt"]:
            continue
        s, b, grund = stand(k, belege)
        hat_beleg = bool(b) and not ist_vorschlag(b) and b.get("hash") == k["hash"]
        if s == "bestanden" or (hat_beleg and s in ("nicht geprüft", "nach Abgabe")):
            continue
        warum = (
            "Rückfall: " + grund
            if hat_beleg
            else "Haken ohne Beleg der Abnahme (die Bau-Lane hakt nicht selbst ab)"
        )
        marke = f"<!-- abnahme-haken-weg:{k['id']}:{k['hash']}:{s} -->"
        text = (
            f"Abnahme {k['id']}: **Haken entfernt**. {warum}.\n\n"
            f"Stand: {s}. Der Haken kommt zurück, sobald ein Lauf es auf main bestanden misst.\n{marke}"
        )
        print(f"{k['id']}: {warum[:120]}")
        if not ja:
            continue
        issue = glab_json(f"projects/{PROJEKT}/issues/{k['iid']}")
        frisch = next((x for x in kriterien(issue) if x["id"] == k["id"]), None)
        if not frisch or frisch["hash"] != k["hash"] or not frisch["abgehakt"]:
            continue
        zeilen_text = issue["description"].split("\n")
        zeilen_text[frisch["zeile"]] = re.sub(r"\[[xX]\]", "[ ]", zeilen_text[frisch["zeile"]], count=1)
        glab_schreiben("PUT", f"issues/{k['iid']}", "description", "\n".join(zeilen_text))
        notizen = glab_json(f"projects/{PROJEKT}/issues/{k['iid']}/notes?per_page=100")
        if not any(marke in (n.get("body") or "") for n in notizen):
            glab_schreiben("POST", f"issues/{k['iid']}/notes", "body", text)
        entfernt += 1
    print(f"{entfernt} Haken entfernt")
    return 0


def befunde(zeilen: list[dict], belege: dict[str, list[dict]], wahl: str | None, ja: bool) -> int:
    """Ein Kommentar je Issue mit allen nicht bestandenen Kriterien; nur wenn sich der Befund geändert hat."""
    je_issue: dict[int, list[tuple[dict, dict]]] = {}
    for k in zeilen:
        if wahl and k["bereich"] != wahl:
            continue
        s, b, _ = stand(k, belege)
        if s == "nicht bestanden" and b:
            je_issue.setdefault(k["iid"], []).append((k, b))
    gepostet = 0
    for iid, liste in sorted(je_issue.items()):
        # Nur Kriterium und Wortlaut: ein Kommentar je Statuswechsel, nie je Lauf (Lead a7, 19:0x).
        kern = json.dumps(sorted((k["id"], k["hash"]) for k, _ in liste))
        marke = f"<!-- abnahme-befund:{hashlib.sha1(kern.encode()).hexdigest()[:12]} -->"
        wort = "Kriterium" if len(liste) == 1 else "Kriterien"
        teile = [f"Abnahme: **{len(liste)} {wort} nicht bestanden** (Prüfer b-abnahme)", ""]
        for k, b in liste:
            teile.append(f"- **{k['id']}** auf main `{b['sha']}`, {b['zeit']}: {b.get('grund', '')}")
            if b.get("befehl"):
                teile.append(f"  Befehl: `{b['befehl'][:300]}`")
            if b.get("ausgabe"):
                teile.append(f"  Gemessen: {b['ausgabe'][:300]}")
        teile += ["", "Fix macht die Lane, der der Code gehört; abgehakt wird nur nach neuer Messung.", marke]
        text = schwaerzen("\n".join(teile))
        if not ja:
            print(f"--- #{iid} (Trockenlauf)\n{text}\n")
            continue
        notizen = glab_json(f"projects/{PROJEKT}/issues/{iid}/notes?per_page=100")
        if any(marke in (n.get("body") or "") for n in notizen):
            print(f"#{iid}: Befund unverändert, kein neuer Kommentar")
            continue
        glab_schreiben("POST", f"issues/{iid}/notes", "body", text)
        gepostet += 1
        print(f"#{iid}: Befund kommentiert ({len(liste)})")
    print(f"{gepostet} Kommentare")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument(
        "befehl", choices=("schreiben", "zaehler", "liste", "einlesen", "abhaken", "befunde", "tor", "haken")
    )
    ap.add_argument("arg", nargs="?")
    ap.add_argument("--bereich", choices=BEREICHE)
    ap.add_argument("--cache", type=Path, help="Issue-Abzug als JSON (zum Wiederholen ohne API)")
    ap.add_argument("--ja", action="store_true", help="abhaken wirklich ausführen")
    ap.add_argument("--ziel", help="main-SHA, für den geurteilt wird (Standard origin/main)")
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
    if a.befehl == "abhaken" and a.arg == "alle":
        # Alle gültig bestandenen Kriterien in offenen Issues; wiederholbar (Marke je Beleg im Kommentar).
        fehler = 0
        for k in zeilen:
            if k["state"] == "opened" and stand(k, belege)[0] == "bestanden":
                try:
                    fehler += abhaken(k["id"], belege, a.ja) != 0
                except RuntimeError as e:
                    print(f"{k['id']}: {e}", file=sys.stderr)
                    fehler += 1
        return 1 if fehler else 0
    if a.befehl == "abhaken":
        return abhaken(a.arg, belege, a.ja)
    if a.befehl == "befunde":
        return befunde(zeilen, belege, a.bereich, a.ja)
    if a.befehl == "haken":  # matrix.py haken pruefen [--ja]
        return haken_pruefen(zeilen, belege, a.ja)
    if a.befehl == "tor":
        return tor(zeilen, belege)

    sha, zeit = main_sha(), jetzt()
    if a.befehl == "schreiben":
        matrix_schreiben(zeilen, belege, sha, zeit)
    if a.ziel:
        global _ZIEL
        _ZIEL = a.ziel
        sha = a.ziel[:8]
    print(zaehler_text(zaehlen(zeilen, belege), sha, zeit))
    return 0


if __name__ == "__main__":
    sys.exit(main())
