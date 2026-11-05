#!/usr/bin/env python3
"""Abnahme-Lauf: führt die Prüfsätze gegen einen sauberen Abzug von main aus und urteilt mechanisch.

    uv run python tests/abnahme/pruefen.py                  # alle leichten Prüfsätze
    uv run python tests/abnahme/pruefen.py --bereich uc3    # nur ein Bereich
    uv run python tests/abnahme/pruefen.py --id 70-AC2      # ein Kriterium
    uv run python tests/abnahme/pruefen.py --gegenprobe     # jede Gegenprobe muss scheitern
    uv run python tests/abnahme/pruefen.py --schwer         # auch schwere (nur auf dem Prüfrechner)

Prüfsätze stehen in `tests/abnahme/pruefungen/<bereich>.toml`. Jeder Lauf schreibt genau eine Datei
`docs/abnahme/laeufe/<lauf-id>.jsonl`: erste Zeile das Laufmanifest, dann ein Beleg je Prüfsatz, letzte Zeile
`{"abgeschlossen": true}`. Ein Lauf ohne diese letzte Zeile zählt nicht. Die Matrix (`matrix.py`) nimmt je
Kriterium den jüngsten gültigen Beleg aus `belege.jsonl` und allen abgeschlossenen Läufen.

Der Abzug hat keine `.env.local`, keine Modellschlüssel und keine erreichbare Datenbank: Datenbank-Variablen
zeigen auf einen gesperrten Port. Was eine Datenbank oder ein Modell braucht, ist `schwer = true`.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
import tomllib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import matrix  # noqa: E402

WURZEL = matrix.WURZEL
PRUEFUNGEN = WURZEL / "tests" / "abnahme" / "pruefungen"
LAEUFE = WURZEL / "docs" / "abnahme" / "laeufe"
ABZUEGE = Path(os.environ.get("ABNAHME_ABZUG_DIR", "/tmp/kic-abnahme-abzug"))

GESPERRT = "postgresql://gesperrt:gesperrt@127.0.0.1:9/gesperrt"
UMGEBUNG = {
    "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
    "HOME": os.environ.get("HOME", "/tmp"),
    "LANG": "de_AT.UTF-8",
    "TZ": "Europe/Vienna",
    "UC1_DATABASE_URL": GESPERRT,
    "UC2_DATABASE_URL": GESPERRT,
    "UC3_DATABASE_URL": GESPERRT,
    "DATABASE_URL": GESPERRT,
    "PGHOST": "127.0.0.1",
    "PGPORT": "9",
    "DB_PORT": "9",
    "LLM_PROVIDER": "gesperrt",
    "KIC_ENV_DATEI": "/dev/null",
    "UV_FROZEN": "1",
}
LAUF_FEHLER = {124: "Zeitlimit", 126: "nicht ausführbar", 127: "Befehl nicht gefunden"}
# Fehlende Datenbank oder fehlendes Modell ist kein Fachbefund, sondern ein Lauf-Fehler
# (der Abzug sperrt beides). Er wird nie still: Stand „nicht geprüft“ mit Grund, sofort nachsehen.
UMGEBUNG_FEHLT = re.compile(
    r"connection refused|could not connect|OperationalError|Connection to server|gesperrt|"
    r"No module named|ModuleNotFoundError|ERR_PNPM|Cannot find module",
    re.I,
)


def pruefsatz_fehler(p: dict) -> str:
    """Leer, wenn der Prüfsatz formal gültig ist; sonst warum nicht."""
    for feld in ("id", "hash", "befehl"):
        if not p.get(feld):
            return f"Feld {feld} fehlt"
    if not isinstance(p.get("erwartet", []), list):
        return "erwartet muss eine Liste sein"
    for r in p.get("erwartet", []):
        if "(?!" in r or "(?<!" in r:
            return f"verneinende Suche nicht erlaubt: {r}"
        try:
            re.compile(r, re.M)
        except re.error as fehler:
            return f"ungültiger Regex {r!r}: {fehler}"
    if p.get("deckung", "voll") not in ("voll", "teil"):
        return "deckung muss voll oder teil sein"
    return ""


def pruefsaetze(ort: Path) -> list[dict]:
    """Prüfsätze aus dem Werkzeugstand im Abzug (committeter Stand der Abnahme-Lane, nicht Arbeitsbaum)."""
    saetze = []
    for datei in sorted((ort / "tests" / "abnahme" / "pruefungen").glob("*.toml")):
        for p in tomllib.loads(datei.read_text()).get("pruefung", []):
            p["datei"] = datei.name
            saetze.append(p)
    return saetze


def abzug(sha: str, werkzeug: str) -> Path:
    """Sauberer Abzug: Prüfling = main an `sha` (einmal je Stand gebaut, mit Python- und Node-Umgebung),
    Prüfwerkzeug = `tests/abnahme` aus dem Abnahme-Commit `werkzeug` (bei jedem Lauf neu eingesetzt)."""
    ziel = ABZUEGE / sha[:12]
    if not (ziel / ".fertig").exists():
        ziel.mkdir(parents=True, exist_ok=True)
        archiv = subprocess.run(["git", "-C", str(WURZEL), "archive", sha], capture_output=True, check=True)
        subprocess.run(["tar", "-x", "-C", str(ziel)], input=archiv.stdout, check=True)
        subprocess.run(["uv", "sync", "--frozen", "--all-packages", "-q"], cwd=ziel, check=True, env=UMGEBUNG)
        subprocess.run(
            ["pnpm", "install", "--frozen-lockfile", "--offline", "--ignore-scripts", "--silent"],
            cwd=ziel,
            check=True,
            env=UMGEBUNG,
        )
        (ziel / ".fertig").write_text(sha)
    shutil.rmtree(ziel / "tests" / "abnahme", ignore_errors=True)
    archiv = subprocess.run(
        ["git", "-C", str(WURZEL), "archive", werkzeug, "tests/abnahme"], capture_output=True, check=True
    )
    subprocess.run(["tar", "-x", "-C", str(ziel)], input=archiv.stdout, check=True)
    return ziel


def urteil(p: dict, code: int, stdout: str, stderr: str = "") -> tuple[str, str]:
    """Mechanisches Urteil: Exit wie erwartet (Standard 0) und jeder Regex (MULTILINE) in stdout."""
    if code in LAUF_FEHLER and not p.get("zeitlimit_ist_befund"):
        return "nicht geprüft", f"Lauf-Fehler: {LAUF_FEHLER[code]} (Exit {code}), sofort nachsehen"
    if code != p.get("exit", 0) and UMGEBUNG_FEHLT.search(stdout + stderr):
        return "nicht geprüft", f"Lauf-Fehler: Umgebung fehlt (DB, Modell oder Paket), Exit {code}"
    fehlt = [r for r in p.get("erwartet", []) if not re.search(r, stdout, re.M)]
    exit_ok = code == p.get("exit", 0)
    if exit_ok and not fehlt:
        if p.get("deckung", "voll") == "teil":
            return "nicht geprüft", "Teil-Prüfsatz erfüllt, der volle Prüfsatz fehlt noch"
        return "bestanden", p.get("grund", "")
    teile = []
    if not exit_ok:
        teile.append(f"Exit {code} statt {p.get('exit', 0)}")
    if fehlt:
        teile.append("nicht gefunden: " + "; ".join(fehlt))
    return "nicht bestanden", p.get("befund", "") + (" " if p.get("befund") else "") + ", ".join(teile)


def ausfuehren(befehl: str, ort: Path, sekunden: int) -> tuple[int, str, str, float]:
    start = time.monotonic()
    try:
        r = subprocess.run(
            ["bash", "-c", befehl],
            cwd=ort,
            env=UMGEBUNG,
            capture_output=True,
            text=True,
            timeout=sekunden,
        )
        code, out, err = r.returncode, r.stdout, r.stderr
    except subprocess.TimeoutExpired as t:
        out = t.stdout.decode(errors="replace") if isinstance(t.stdout, bytes) else (t.stdout or "")
        code, err = 124, ""
    return code, out, err, time.monotonic() - start


def auszug(text: str, grenze: int = 600) -> str:
    """Kürzt die Ausgabe und entfernt lokale Pfade, damit nichts Rechnerspezifisches in den Beleg kommt."""
    text = text.replace(str(ABZUEGE), "<abzug>").replace(os.environ.get("HOME", "~"), "~").strip()
    text = matrix.VERBOTEN.sub("<entfernt>", text)
    return text if len(text) <= grenze else text[: grenze // 2] + " … " + text[-grenze // 2 :]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--bereich")
    ap.add_argument("--id")
    ap.add_argument("--schwer", action="store_true")
    ap.add_argument("--gegenprobe", action="store_true")
    ap.add_argument("--ohne-datei", action="store_true", help="nur anzeigen, keinen Lauf ablegen")
    a = ap.parse_args()

    subprocess.run(["git", "-C", str(WURZEL), "fetch", "-q", "origin", "main"], check=True)
    sha = matrix.git("rev-parse", "origin/main").stdout.strip()
    issues = matrix.issues_holen(None)
    kriterien = {k["id"]: k for k in matrix.alle_kriterien(issues)}
    werkzeug = matrix.git("rev-parse", "HEAD").stdout.strip()
    if matrix.git("status", "--porcelain", "--", "tests/abnahme").stdout.strip():
        print(
            "Hinweis: tests/abnahme hat nicht committete Änderungen; der Lauf nutzt den Commit", werkzeug[:8]
        )
    ort = abzug(sha, werkzeug)
    zeit = matrix.jetzt()
    lauf_id = zeit.replace(" ", "T").replace(":", "") + "-" + sha[:8]

    wahl = [
        p
        for p in pruefsaetze(ort)
        if (not a.id or p["id"] == a.id)
        and (not a.bereich or p["datei"] == f"{a.bereich}.toml")
        and (a.schwer or not p.get("schwer"))
    ]
    zeilen = [
        {
            "lauf": lauf_id,
            "sha": sha,
            "werkzeug": werkzeug,
            "zeit": zeit,
            "umfang": len(wahl),
            "schwer": a.schwer,
        }
    ]
    teile: dict[str, list[dict]] = {}
    for p in wahl:
        k = kriterien.get(p["id"])
        if a.gegenprobe:
            if not p.get("gegenprobe"):
                continue
            code, out, err, _ = ausfuehren(p["gegenprobe"], ort, p.get("zeitlimit", 180))
            s, _ = urteil(p | {"deckung": "voll"}, code, out, err)
            print(f"{'ok  ' if s == 'nicht bestanden' else 'FEHL'} Gegenprobe {p['id']}: {s}")
            continue
        if fehler := pruefsatz_fehler(p):
            r = {"stand": "nicht geprüft", "grund": f"Prüfsatz ungültig: {fehler}", "exit": None, "text": ""}
        elif not k:
            r = {"stand": "nicht geprüft", "grund": "Kriterium nicht mehr im Issue", "exit": None, "text": ""}
        elif k["hash"] != p["hash"]:
            r = {
                "stand": "nicht geprüft",
                "grund": "Kriterium geändert, Prüfsatz anpassen",
                "exit": None,
                "text": "",
            }
        else:
            code, out, err, dauer = ausfuehren(p["befehl"], ort, p.get("zeitlimit", 180))
            s, grund = urteil(p, code, out, err)
            text = out + (f"\n[stderr] {err}" if err.strip() else "")
            r = {"stand": s, "grund": grund, "exit": code, "text": text, "dauer": dauer}
        teile.setdefault(p["id"], []).append(r | {"p": p, "hash": k["hash"] if k else p["hash"]})

    zaehler = {"bestanden": 0, "nicht bestanden": 0, "nicht geprüft": 0}
    for kid, rs in teile.items():
        staende = [r["stand"] for r in rs]
        voll_ok = any(r["stand"] == "bestanden" and r["p"].get("deckung", "voll") == "voll" for r in rs)
        if "nicht bestanden" in staende:
            s = "nicht bestanden"
        elif voll_ok and all(r["stand"] == "bestanden" or "Teil-Prüfsatz" in r["grund"] for r in rs):
            s = "bestanden"
        else:
            s = "nicht geprüft"
        grund = " | ".join(
            r["grund"] for r in rs if r["grund"] and (s != "nicht bestanden" or r["stand"] == s)
        )
        zaehler[s] += 1
        b = {
            "id": kid,
            "hash": rs[0]["hash"],
            "stand": s,
            "befehl": "\n".join(r["p"]["befehl"] for r in rs),
            "ausgabe": auszug("\n---\n".join(r["text"] for r in rs)),
            "exit": [r["exit"] for r in rs],
            "dauer_s": round(sum(r.get("dauer", 0.0) for r in rs), 1),
            "grund": grund,
            "sha": sha[:12],
            "zeit": zeit,
            "pruefer": f"lauf {lauf_id}",
            "pruefsatz": rs[0]["p"]["datei"],
        }
        if s == "nicht bestanden":
            arten = {r["p"].get("befund_art", "abweichend") for r in rs if r["stand"] == s}
            b["befund_art"] = "fehlt" if arten == {"fehlt"} else "abweichend"
        pfade = sorted({x for r in rs for x in r["p"].get("pfade", [])})
        if pfade and all(r["p"].get("pfade") for r in rs):
            b["pfade"] = pfade
        zeilen.append(b)
        print(f"{s:16} {kid:12} {grund[:90]}")
    if a.gegenprobe:
        return 0
    zeilen.append({"abgeschlossen": True, "ende": matrix.jetzt()})
    print(f"Lauf {lauf_id}: " + ", ".join(f"{v} {k}" for k, v in zaehler.items()))
    if not a.ohne_datei:
        LAEUFE.mkdir(parents=True, exist_ok=True)
        ziel = LAEUFE / f"{lauf_id}.jsonl"
        ziel.write_text("".join(json.dumps(z, ensure_ascii=False) + "\n" for z in zeilen))
        print(f"abgelegt: {ziel.relative_to(WURZEL)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
