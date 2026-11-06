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
import tempfile
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
# Leere, echte Datei: plattform.umgebung verlangt seit #93 is_file(), /dev/null besteht das nicht (28-1).
LEERE_ENV = Path(tempfile.gettempdir()) / "kic-abnahme-leer.env"
LEERE_ENV.write_text("")
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
    "KIC_ENV_DATEI": str(LEERE_ENV),
    "UV_FROZEN": "1",
    "NO_COLOR": "1",
    "FORCE_COLOR": "0",
    "CI": "1",
}
ANSI = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")
LAUF_FEHLER = {124: "Zeitlimit", 126: "nicht ausführbar", 127: "Befehl nicht gefunden"}
# Fehlende Datenbank oder fehlendes Modell ist kein Fachbefund, sondern ein Lauf-Fehler
# (der Abzug sperrt beides). Er wird nie still: Stand „nicht geprüft“ mit Grund, sofort nachsehen.
UMGEBUNG_FEHLT = re.compile(
    r"connection refused|could not connect|OperationalError|Connection to server|gesperrt|"
    r"No module named|ModuleNotFoundError|ERR_PNPM|Cannot find module",
    re.I,
)


# „<Pfad zu svbox/uc3>“, „<24 Monate>“: Vorschläge mit Platzhaltern sind keine Prüfsätze
# (gemessen 05.11. 18:12: sie ergaben über einen Syntaxfehler fälschlich „nicht bestanden“).
PLATZHALTER = re.compile(
    r"<(?!!--)[^<>|;&$'\"]*[A-Za-zÄÖÜäöüß]{3,}[^<>|;&$'\"]*>"
)  # HTML-Kommentare sind echt


def pruefsatz_fehler(p: dict) -> str:
    """Leer, wenn der Prüfsatz formal gültig ist; sonst warum nicht."""
    if p.get("art") == "hand":
        return (
            ""
            if p.get("beschreibung") and p.get("id") and p.get("hash")
            else "Hand-Prüfsatz ohne beschreibung"
        )
    for feld in ("id", "hash", "befehl"):
        if not p.get(feld):
            return f"Feld {feld} fehlt"
    if re.search(r"\b5433\b|\b5434\b|docker\s+(compose|run|rm|volume)|compose\s+(up|down)", p["befehl"]):
        return "Befehl berührt Docker oder einen Bau-Port (5433/5434); Docker steuert nur 66_jury_weg.sh"
    if PLATZHALTER.search(p["befehl"]):
        return f"Befehl enthält einen Platzhalter: {PLATZHALTER.search(p['befehl']).group(0)}"
    syntax = subprocess.run(["bash", "-n", "-c", p["befehl"]], capture_output=True, text=True)
    if syntax.returncode != 0:
        return f"Befehl ist kein gültiges bash: {syntax.stderr.strip()[:120]}"
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


def alte_abzuege_entfernen(behalten: int = 2, ordner: Path | None = None) -> list[str]:
    """Lässt nur die neuesten Abzüge stehen; je main entsteht sonst einer, und die Platte läuft voll (06.11.).

    Fasst nur Ordner mit SHA-Namen an, nie die Links auf die Nachbarordner mit den Daten.
    """
    wurzel = ordner or ABZUEGE
    if not wurzel.is_dir():
        return []
    stand = [
        p
        for p in wurzel.iterdir()
        if re.fullmatch(r"[0-9a-f]{12}(-git)?", p.name) and p.is_dir() and not p.is_symlink()
    ]
    stand.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    weg = stand[behalten:]
    for p in weg:
        shutil.rmtree(p, ignore_errors=True)
    return sorted(p.name for p in weg)


def abzug(sha: str, werkzeug: str) -> Path:
    """Sauberer Abzug als geteilter Klon (mit Git-Historie für git- und gitleaks-Prüfsätze).

    Prüfling = main an `sha` (einmal je Stand gebaut, mit Python- und Node-Umgebung); Prüfwerkzeug =
    `tests/abnahme` aus dem Abnahme-Commit `werkzeug`, bei jedem Lauf neu eingesetzt.
    """
    ziel = ABZUEGE / f"{sha[:12]}-git"
    if not (ziel / ".fertig").exists():
        shutil.rmtree(ziel, ignore_errors=True)
        subprocess.run(
            ["git", "clone", "-q", "--shared", "--no-checkout", str(WURZEL), str(ziel)], check=True
        )
        (ziel / MARKE_KLON).write_text("Prüf-Klon der Abnahme; wird vor jedem Lauf hart zurückgesetzt.\n")
        subprocess.run(["git", "-C", str(ziel), "checkout", "-q", "--detach", sha], check=True)
        subprocess.run(["uv", "sync", "--frozen", "--all-packages", "-q"], cwd=ziel, check=True, env=UMGEBUNG)
        node_ok = any(
            subprocess.run(
                ["pnpm", "install", "--frozen-lockfile", "--ignore-scripts", "--silent", *weise],
                cwd=ziel,
                env=UMGEBUNG,
                capture_output=True,
            ).returncode
            == 0
            for weise in (["--offline"], ["--prefer-offline"])
        )
        if not node_ok:
            print("Hinweis: pnpm install gescheitert; vitest-Prüfsätze werden Lauf-Fehler", file=sys.stderr)
        (ziel / ".fertig").write_text(sha)
    if not (ziel / MARKE_KLON).exists():  # Abzüge von vor der Marke (unter ABZUEGE, also eigene Prüf-Klone)
        (ziel / MARKE_KLON).write_text("Prüf-Klon der Abnahme; wird vor jedem Lauf hart zurückgesetzt.\n")
    nachbarn_verlinken()
    zuruecksetzen(ziel, sha, werkzeug)
    alte_abzuege_entfernen()
    return ziel


NACHBARN = ("svbox", "lieferungen")  # Startpaket und externe Lieferungen (Einzeldaten), nie im Repo


def nachbarn_verlinken() -> None:
    """Legt neben die Abzüge dieselben Nachbarordner wie neben den Haupt-Checkout (Jury-Weg: ../svbox/uc3).

    statagent sucht Startpaket und Lieferungen neben dem Haupt-Checkout (konfig.startpaket,
    konfig.lieferungen_extern); ohne die Links meldet pruefe-abgabe „Vorlage nicht gefunden“ (Lauf 19:53).
    """
    gemeinsam = matrix.git("rev-parse", "--path-format=absolute", "--git-common-dir").stdout.strip()
    basis = Path(gemeinsam).parent.parent
    for name in NACHBARN:
        quelle, link = basis / name, ABZUEGE / name
        if not quelle.is_dir():
            print(f"Hinweis: {name}/ fehlt neben dem Haupt-Checkout", file=sys.stderr)
        elif not link.exists():
            link.symlink_to(quelle)


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


PRUEF_DB_PORT = 5444  # Prüf-DB kic-abnahme; 5433 (Bau-DB) und 5434 (fremd) sind tabu


def db_umgebung(datei: Path) -> str:
    """Übernimmt *_DATABASE_URL aus `datei`; Fehlertext, wenn eine davon nicht zur Prüf-DB führt."""
    from urllib.parse import urlsplit

    for zeile in datei.read_text().splitlines():
        if "=" not in zeile or zeile.lstrip().startswith("#"):
            continue
        name, wert = (t.strip().strip("'\"") for t in zeile.split("=", 1))
        if name in ("STATAGENT_STARTPAKET", "STATAGENT_ABGABE"):
            UMGEBUNG[name] = wert
            continue
        if not name.endswith("DATABASE_URL"):
            continue
        teile = urlsplit(wert)
        if teile.port != PRUEF_DB_PORT or teile.hostname not in ("localhost", "127.0.0.1"):
            return f"{name} zeigt nicht auf die lokale Prüf-DB (Port {PRUEF_DB_PORT})"
        UMGEBUNG[name] = wert
        if name == "UC3_DATABASE_URL":
            # Die Test-Fixtures von uc3 legen sich eine eigene DB an und fallen sonst auf den Bau-Port zurück:
            # auf einem Rechner ohne Bau-DB werden die Tests still übersprungen, sonst treffen sie die Bau-DB.
            UMGEBUNG["UC3_TEST_ADMIN_URL"] = teile._replace(path="/postgres").geturl()
    UMGEBUNG.pop("PGHOST", None)
    UMGEBUNG["PGPORT"] = str(PRUEF_DB_PORT)
    UMGEBUNG["DB_PORT"] = str(PRUEF_DB_PORT)
    return ""


def hand_teil(p: dict, k: dict, belege: dict[str, list[dict]], sha: str) -> dict:
    """Hand-Prüfsatz: zählt als voller Teil, wenn der Prüfer einen gültigen Hand-Beleg abgelegt hat."""
    b = matrix.beleg_fuer(k, belege)
    leer = {"exit": None, "text": ""}
    if not b or b.get("art") != "hand" or b.get("hash") != k["hash"] or matrix.ist_vorschlag(b):
        return leer | {"stand": "nicht geprüft", "grund": f"Hand-Prüfung offen: {p['beschreibung'][:200]}"}
    if alt := matrix.veraltet(b, sha, k["bereich"]):
        return leer | {
            "stand": "nicht geprüft",
            "grund": f"Hand-Beleg veraltet ({alt}): {p['beschreibung'][:120]}",
        }
    text = f"Hand-Beleg {b['pruefer']} {b['zeit']}: {b.get('ausgabe', '')}"
    return leer | {"stand": b["stand"], "grund": b.get("grund", ""), "text": text}


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
        code, out, err = r.returncode, ANSI.sub("", r.stdout), ANSI.sub("", r.stderr)
    except subprocess.TimeoutExpired as t:
        out = t.stdout.decode(errors="replace") if isinstance(t.stdout, bytes) else (t.stdout or "")
        code, err = 124, ""
    return code, out, err, time.monotonic() - start


MARKE_KLON = (
    ".kic-abnahme-pruefklon"  # nur Verzeichnisse mit dieser Datei werden hart zurückgesetzt (Review 4d)
)
ORT: Path | None = None  # Prüf-Klon des laufenden Laufs, wird in Ausgaben durch <pruefklon> ersetzt


def auszug(text: str, grenze: int = 600) -> str:
    """Kürzt die Ausgabe und entfernt Pfade und Rechnernamen (nichts Rechnerspezifisches im Beleg)."""
    for ort in (ORT, ABZUEGE):
        if ort:
            text = text.replace(str(ort), "<pruefklon>")
    text = matrix.schwaerzen(text.strip())
    return text if len(text) <= grenze else text[: grenze // 2] + " … " + text[-grenze // 2 :]


def zuruecksetzen(ort: Path, sha: str, werkzeug: str) -> None:
    """Prüf-Klon hart auf main an `sha` plus Werkzeug-Commit; Reste früherer Prüfsätze werden entfernt.

    Grund (Review 4d, 19:00): ein Prüfsatz schrieb abgabe/protokoll.md in den Klon; der nächste checkout
    scheiterte still. Umgebungen (.venv, node_modules) sind ignoriert und bleiben.
    """
    # Nur ein markierter Prüf-Klon wird hart zurückgesetzt. Auf dem Prüfrechner liegt pruefen.py im Klon
    # selbst, deshalb entscheidet die Marke, nicht der Pfad (20:01: Ablehnung des Pfads verhinderte den Lauf).
    if not (ort / MARKE_KLON).exists():
        wer = (
            "der eigene Arbeitsbaum ohne Marke"
            if WURZEL.resolve().is_relative_to(ort.resolve())
            else "ohne Marke"
        )
        raise SystemExit(f"Abbruch: {ort} ist {wer} {MARKE_KLON}, wird nicht zurückgesetzt")
    subprocess.run(["git", "-C", str(ort), "checkout", "-q", "-f", "--detach", sha], check=True)
    subprocess.run(["git", "-C", str(ort), "clean", "-fdq", "-e", ".fertig", "-e", MARKE_KLON], check=True)
    shutil.rmtree(ort / "tests" / "abnahme", ignore_errors=True)
    subprocess.run(["git", "-C", str(ort), "checkout", "-q", werkzeug, "--", "tests/abnahme"], check=True)


def ort_vorbereiten(ort: Path, sha: str, werkzeug: str) -> None:
    """Bereitet den Checkout für `--ort` vor.

    Auf dem Prüfrechner läuft pruefen.py im Prüf-Klon selbst; schwer_pruefrechner.sh hat ihn vorher hart
    zurückgesetzt. Dann wird nur geprüft (Marke da, Kopf = main-SHA), nicht erneut zurückgesetzt: ein
    Zurücksetzen würde tests/abnahme unter dem laufenden Skript ersetzen. Ohne Marke bleibt der eigene
    Arbeitsbaum tabu (Abbruch 20:01 auf main 71ba5c82, Folge des Schutzes aus Review 4d).
    """
    if ort.resolve() != WURZEL.resolve():
        zuruecksetzen(ort, sha, werkzeug)
        return
    if not (ort / MARKE_KLON).exists():
        raise SystemExit(f"Abbruch: {ort} ist der eigene Arbeitsbaum, kein Prüf-Klon")
    kopf = subprocess.run(
        ["git", "-C", str(ort), "rev-parse", "HEAD"], capture_output=True, text=True, check=True
    ).stdout.strip()
    if not kopf.startswith(sha):
        raise SystemExit(f"Abbruch: Prüf-Klon steht auf {kopf[:8]}, nicht auf main {sha[:8]}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--bereich")
    ap.add_argument("--id")
    ap.add_argument("--schwer", action="store_true")
    ap.add_argument("--gegenprobe", action="store_true")
    ap.add_argument("--ohne-datei", action="store_true", help="nur anzeigen, keinen Lauf ablegen")
    ap.add_argument("--ort", type=Path, help="vorbereiteter Checkout (Prüfrechner) statt eigenem Abzug")
    ap.add_argument("--sha", help="main-SHA des vorbereiteten Checkouts (mit --ort)")
    ap.add_argument("--werkzeug", help="Abnahme-Commit für tests/abnahme (mit --ort)")
    ap.add_argument("--cache", type=Path, help="Issue-Abzug als JSON (Prüfrechner ohne glab)")
    ap.add_argument(
        "--db-env", type=Path, help="KEY=VALUE-Datei mit *_DATABASE_URL der Prüf-DB (nur --schwer)"
    )
    a = ap.parse_args()

    if a.db_env:
        fehler = db_umgebung(a.db_env)
        if fehler:
            print(f"Abbruch vor jedem Lauf: {fehler}", file=sys.stderr)
            return 3
    issues = matrix.issues_holen(a.cache)
    kriterien = {k["id"]: k for k in matrix.alle_kriterien(issues)}
    if a.ort:
        if not (a.sha and a.werkzeug):
            print("--ort braucht --sha und --werkzeug", file=sys.stderr)
            return 2
        sha, werkzeug, ort = a.sha, a.werkzeug, a.ort.resolve()
        ort_vorbereiten(ort, sha, werkzeug)
    else:
        subprocess.run(["git", "-C", str(WURZEL), "fetch", "-q", "origin", "main"], check=True)
        sha = matrix.git("rev-parse", "origin/main").stdout.strip()
        werkzeug = matrix.git("rev-parse", "HEAD").stdout.strip()
        if matrix.git("status", "--porcelain", "--", "tests/abnahme").stdout.strip():
            print("Hinweis: tests/abnahme hat nicht committete Änderungen; der Lauf nutzt", werkzeug[:8])
        ort = abzug(sha, werkzeug)
    global ORT
    ORT = ort
    zeit = matrix.jetzt()
    lauf_id = zeit.replace(" ", "T").replace(":", "") + "-" + sha[:8]

    alle = pruefsaetze(ort)
    # Kriterien mit schwerem Teil: ein leichter Lauf darf sie nur abwerten (nicht bestanden),
    # sonst schweigt er, damit er ein Urteil des schweren Laufs nicht mit „nicht geprüft“ überdeckt.
    hat_schwer = {p["id"] for p in alle if p.get("schwer")}
    wahl = [
        p
        for p in alle
        if (not a.id or p["id"] == a.id)
        and (not a.bereich or p["datei"].split(".")[0].split("-")[0] == a.bereich)
        and (a.schwer or not p.get("schwer"))
        # `einzeln = true`: nur mit --id (22-1 rechnet 24 Läufe v2 nach und sprengt sonst den Schlusslauf).
        and (a.id or not p.get("einzeln"))
        # Der schwere Lauf urteilt nur Kriterien mit schwerem Teil (alle ihre Teile). Rein leichte Kriterien
        # misst der leichte Lauf: auf dem Prüfrechner fehlen glab und Nachbarordner, ein Urteil von dort
        # würde ein jüngeres leichtes Urteil überdecken (Lauf 20:11: 134-4 nur dort nicht bestanden).
        and (not a.schwer or p["id"] in hat_schwer)
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
    hand_belege = matrix.belege_lesen()
    gegen_fehl = 0
    teile: dict[str, list[dict]] = {}
    for p in wahl:
        k = kriterien.get(p["id"])
        if a.gegenprobe:
            if not p.get("gegenprobe"):
                continue
            if fehler := pruefsatz_fehler(p | {"befehl": p["gegenprobe"]}):
                print(f"FEHL Gegenprobe {p['id']}: ungültig ({fehler})")
                gegen_fehl += 1
                continue
            code, out, err, _ = ausfuehren(p["gegenprobe"], ort, p.get("zeitlimit", 180))
            s, _ = urteil(p | {"deckung": "voll"}, code, out, err)
            ok = s == "nicht bestanden"
            gegen_fehl += not ok
            print(f"{'ok  ' if ok else 'FEHL'} Gegenprobe {p['id']}: {s}")
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
        elif p.get("art") == "hand":
            r = hand_teil(p, k, hand_belege, sha)
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
        if not a.schwer and kid in hat_schwer and s != "nicht bestanden":
            print(f"{'(schwer offen)':16} {kid:12} leichte Teile ohne Befund, Urteil aus dem schweren Lauf")
            continue
        grund = " | ".join(
            r["grund"] for r in rs if r["grund"] and (s != "nicht bestanden" or r["stand"] == s)
        )
        zaehler[s] += 1
        b = {
            "id": kid,
            "hash": rs[0]["hash"],
            "stand": s,
            "befehl": "\n".join(r["p"].get("befehl", "(Hand-Prüfung)") for r in rs),
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
        return 1 if gegen_fehl else 0
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
