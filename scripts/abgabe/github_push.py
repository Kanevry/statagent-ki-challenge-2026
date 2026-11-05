#!/usr/bin/env python3
"""Abgabe nach GitHub: main dieses Repos als Nachfolger von KIChallenge/OneShotAndy.

Ohne Schalter ist das ein Trockenlauf: Das Skript baut die Abgabe in einem leeren Arbeitsordner,
prüft sie und fragt GitHub mit `git push --dry-run`, ob der Push durchginge. Nach außen geht nichts.
Erst `--ausfuehren` pusht. Das tut nur der Lead am Abgabetag kurz vor 09:00.

Ablauf:
1. Abgabe-Basis (Standard `refs/remotes/origin/main`) und GitHub-main in einen leeren Ordner holen.
2. Merge mit `--allow-unrelated-histories -s ours`: Der Inhalt bleibt genau unser main,
   die drei GitHub-Commits bleiben als Vorfahren erhalten. Darum ist der Push ein Fast-Forward.
3. Prüfungen: Pflichtdateien von GitHub vorhanden, Dateiliste ohne Zugangs- und Einzeldaten,
   Sperrmuster (Rechnernamen) in Dateien und Commit-Nachrichten, gitleaks über die ganze Historie,
   Dateigröße unter der GitHub-Grenze.
4. `git push --dry-run` (Trockenlauf) oder Push mit Rückleseprüfung über `git ls-remote` (`--ausfuehren`).

Die Sperrmuster stehen absichtlich nicht im Repo (öffentlich). Sie kommen aus einer Datei außerhalb
(`--sperrmuster`, eine Regex je Zeile, `#` für Kommentare).
Ausgaben nennen nur Datei und Zeile, nie den Treffer.

Nur Standardbibliothek. Aufruf: `python3 -I scripts/abgabe/github_push.py --help`.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from zoneinfo import ZoneInfo

ZIEL_URL = "https://github.com/KIChallenge/OneShotAndy.git"
ZIEL_BRANCH = "main"
WIEN = ZoneInfo("Europe/Vienna")
# Owner: GitHub-Push erst kurz vor 09:00 am Abgabetag.
NICHT_VOR = "2026-11-06T08:30"
# Entscheid Lead a7 (#92, 05.11.): Historie bleibt unverändert; bekannte Treffer in Commit-Nachrichten.
ERLAUBTE_COMMIT_TREFFER = 12
# GitHub lehnt Dateien über 100 MB ab, warnt ab 50 MB.
GROESSE_GRENZE = 50 * 1024 * 1024
# Dateien, die GitHub schon hat und die erhalten bleiben müssen (Vorgabe der Veranstalter).
PFLICHT_GLEICH = ("KI-Challenge_UseCase.yaml",)

# Was nie in die öffentliche Abgabe darf (Dateipfade).
VERBOTENE_PFADE = re.compile(
    r"(^|/)\.env(\.(?!example$)[^/]*)?$"  # .env, .env.local, … aber nicht .env.example
    r"|\.(pem|p12|pfx|key|keystore|jks)$"
    r"|(^|/)id_(rsa|ed25519|ecdsa)(\.pub)?$"
    r"|(^|/)ministerium_[^/]*\.csv$"  # Lieferung mit Einzeldaten (PERSON_ID), nur SV-Box
    r"|^(svbox|lieferungen)/"  # Startpaket und Lieferungen der Veranstalter
)


@dataclass
class Befund:
    name: str
    ok: bool
    text: str


@dataclass
class Bericht:
    befunde: list[Befund] = field(default_factory=list)

    def add(self, name: str, ok: bool, text: str) -> None:
        self.befunde.append(Befund(name, ok, text))
        print(f"[{'ok' if ok else 'FEHLT'}] {name}: {text}", flush=True)

    @property
    def ok(self) -> bool:
        return all(b.ok for b in self.befunde)


def git(arbeit: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(arbeit), *args], check=check, capture_output=True, text=True, encoding="utf-8"
    )


def verbotene_pfade(pfade: list[str]) -> list[str]:
    """Pfade aus der Dateiliste, die nicht öffentlich werden dürfen."""
    return [p for p in pfade if VERBOTENE_PFADE.search(p)]


def lade_sperrmuster(datei: Path) -> list[re.Pattern[str]]:
    muster = []
    for zeile in datei.read_text(encoding="utf-8").splitlines():
        zeile = zeile.strip()
        if zeile and not zeile.startswith("#"):
            muster.append(re.compile(zeile))
    if not muster:
        raise SystemExit(f"Sperrmuster-Datei ohne Muster: {datei}")
    return muster


def treffer_in_text(text: str, muster: list[re.Pattern[str]]) -> list[int]:
    """Zeilennummern (ab 1) mit mindestens einem Treffer. Den Treffer selbst gibt niemand aus."""
    return [n for n, zeile in enumerate(text.splitlines(), 1) if any(m.search(zeile) for m in muster)]


def nicht_vor_erreicht(jetzt: dt.datetime, nicht_vor: str) -> bool:
    grenze = dt.datetime.fromisoformat(nicht_vor).replace(tzinfo=WIEN)
    return jetzt >= grenze


def sperrmuster_in_dateien(arbeit: Path, ref: str, muster: list[re.Pattern[str]]) -> dict[str, list[int]]:
    ergebnis: dict[str, list[int]] = {}
    pfade = git(arbeit, "ls-tree", "-r", "--name-only", "-z", ref).stdout.split("\0")
    for pfad in filter(None, pfade):
        roh = subprocess.run(
            ["git", "-C", str(arbeit), "show", f"{ref}:{pfad}"], check=True, capture_output=True
        ).stdout
        if b"\0" in roh[:8000]:  # binär
            continue
        zeilen = treffer_in_text(roh.decode("utf-8", errors="replace"), muster)
        if zeilen:
            ergebnis[pfad] = zeilen
    return ergebnis


def sperrmuster_in_commits(arbeit: Path, ref: str, muster: list[re.Pattern[str]]) -> tuple[int, int]:
    """(Commits mit Treffer, Commits gesamt) über Nachricht, Autor und Committer aller Commits."""
    roh = git(arbeit, "log", "--format=%H%x00%an %ae %cn %ce%n%B%x01", ref).stdout
    gesamt = treffer = 0
    for eintrag in filter(str.strip, roh.split("\x01")):
        _, _, text = eintrag.strip().partition("\0")
        gesamt += 1
        if treffer_in_text(text, muster):
            treffer += 1
    return treffer, gesamt


def gitleaks(arbeit: Path, ref: str, bericht_pfad: Path) -> tuple[bool, str]:
    lauf = subprocess.run(
        [
            "gitleaks",
            "git",
            "--no-banner",
            "--redact",
            f"--log-opts={ref}",
            "--report-format",
            "json",
            "--report-path",
            str(bericht_pfad),
            str(arbeit),
        ],
        capture_output=True,
        text=True,
    )
    try:
        anzahl = len(json.loads(bericht_pfad.read_text(encoding="utf-8") or "[]"))
    except (OSError, json.JSONDecodeError):
        anzahl = -1
    commits = re.search(r"(\d+) commits scanned", lauf.stderr + lauf.stdout)
    text = f"{commits.group(1) if commits else '?'} Commits, {anzahl} Befunde, rc {lauf.returncode}"
    return lauf.returncode == 0 and anzahl == 0, text


def pfade_der_historie(arbeit: Path, ref: str) -> list[str]:
    """Alle Dateipfade, die je in einem Commit vorkamen: Gepusht wird die ganze Historie."""
    roh = git(arbeit, "log", "--format=", "--name-only", "-z", "--no-renames", "-m", ref).stdout
    return sorted(set(filter(None, (p.strip() for p in roh.split("\0")))))


def sperrmuster_in_historie(arbeit: Path, ref: str, muster: list[re.Pattern[str]]) -> tuple[int, list[str]]:
    """(Dateistände mit Treffer, betroffene Pfade) über alle Blobs der Historie. Nur ein Zählwert."""
    objekte = git(arbeit, "rev-list", "--objects", "--no-object-names", ref).stdout.split()
    namen = git(arbeit, "rev-list", "--objects", ref).stdout.splitlines()
    pfad_von = dict(z.split(" ", 1) for z in namen if " " in z)
    lauf = subprocess.run(
        ["git", "-C", str(arbeit), "cat-file", "--batch"],
        input="\n".join(objekte).encode() + b"\n",
        capture_output=True,
        check=True,
    )
    roh, stelle, treffer = lauf.stdout, 0, 0
    pfade: set[str] = set()
    while stelle < len(roh):
        ende = roh.index(b"\n", stelle)
        oid, art, groesse = roh[stelle:ende].decode().split()
        anfang = ende + 1
        inhalt = roh[anfang : anfang + int(groesse)]
        stelle = anfang + int(groesse) + 1
        if art != "blob" or b"\0" in inhalt[:8000]:
            continue
        if treffer_in_text(inhalt.decode("utf-8", errors="replace"), muster):
            treffer += 1
            pfade.add(pfad_von.get(oid, "?"))
    return treffer, sorted(pfade)


def baue_abgabe(
    arbeit: Path, quelle: Path, quelle_ref: str, ziel_url: str, nachricht: str
) -> tuple[str, str]:
    """Holt Basis und GitHub-Stand, mergt. Gibt (Basis-Commit, Merge-Commit) zurück."""
    git(arbeit, "init", "-q", "-b", "abgabe")
    # Ein Merge-Commit soll die Identität des Repos tragen, nie eine aus dem Rechnernamen abgeleitete.
    for schluessel in ("user.name", "user.email"):
        wert = git(quelle, "config", schluessel, check=False).stdout.strip()
        if not wert:
            raise SystemExit(f"git config {schluessel} fehlt im Quell-Repo.")
        git(arbeit, "config", schluessel, wert)
    git(arbeit, "fetch", "-q", "--no-tags", str(quelle), f"+{quelle_ref}:refs/heads/basis")
    git(
        arbeit,
        "fetch",
        "-q",
        "--no-tags",
        ziel_url,
        f"+refs/heads/{ZIEL_BRANCH}:refs/remotes/github/{ZIEL_BRANCH}",
    )
    basis = git(arbeit, "rev-parse", "refs/heads/basis").stdout.strip()
    git(arbeit, "checkout", "-q", "-B", "abgabe", "refs/heads/basis")
    git(
        arbeit,
        "merge",
        "-q",
        "--no-ff",
        "--allow-unrelated-histories",
        "-s",
        "ours",
        "-m",
        nachricht,
        f"refs/remotes/github/{ZIEL_BRANCH}",
    )
    kopf = git(arbeit, "rev-parse", "HEAD").stdout.strip()
    return basis, kopf


def pruefe(arbeit: Path, muster: list[re.Pattern[str]], bericht_pfad: Path, erlaubte: int) -> Bericht:
    bericht = Bericht()
    gh = f"refs/remotes/github/{ZIEL_BRANCH}"

    # 1. Fast-Forward und Inhalt
    ff = git(arbeit, "merge-base", "--is-ancestor", gh, "HEAD", check=False).returncode == 0
    bericht.add(
        "fast-forward",
        ff,
        "GitHub-main ist Vorfahr der Abgabe" if ff else "GitHub-main fehlt in der Historie",
    )
    gleich = git(arbeit, "diff", "--quiet", "refs/heads/basis", "HEAD", check=False).returncode == 0
    bericht.add("inhalt", gleich, "Dateien gleich der Abgabe-Basis" if gleich else "Merge verändert Dateien")

    # 2. Pflichtdateien der Veranstalter
    for pfad in PFLICHT_GLEICH:
        a = git(arbeit, "rev-parse", f"{gh}:{pfad}", check=False).stdout.strip()
        b = git(arbeit, "rev-parse", f"HEAD:{pfad}", check=False).stdout.strip()
        bericht.add(
            f"pflicht {pfad}",
            bool(a) and a == b,
            "gleich wie auf GitHub" if a and a == b else "fehlt oder anders",
        )
    gh_pfade = set(filter(None, git(arbeit, "ls-tree", "-r", "--name-only", "-z", gh).stdout.split("\0")))
    pfade = list(filter(None, git(arbeit, "ls-tree", "-r", "--name-only", "-z", "HEAD").stdout.split("\0")))
    fehlend = sorted(gh_pfade - set(pfade))
    bericht.add(
        "github-dateien", not fehlend, "alle GitHub-Dateien bleiben" if not fehlend else f"fehlen: {fehlend}"
    )

    # 3. Dateiliste
    verboten = verbotene_pfade(pfade)
    bericht.add("dateiliste", not verboten, f"{len(pfade)} Dateien, verboten: {verboten or 0}")
    alle_pfade = pfade_der_historie(arbeit, "HEAD")
    verboten_alt = verbotene_pfade(alle_pfade)
    bericht.add(
        "dateiliste historie",
        not verboten_alt,
        f"{len(alle_pfade)} Pfade in der ganzen Historie, verboten: {verboten_alt or 0}",
    )
    gross = []
    for zeile in git(arbeit, "ls-tree", "-r", "-l", "HEAD").stdout.splitlines():
        meta, _, pfad = zeile.partition("\t")
        groesse = meta.split()[3]
        if groesse.isdigit() and int(groesse) > GROESSE_GRENZE:
            gross.append(pfad)
    bericht.add("dateigroesse", not gross, f"über 50 MB: {gross or 0}")

    # 4. Sperrmuster (Rechnernamen, Pfade): nur Datei und Zeile ausgeben
    datei_treffer = sperrmuster_in_dateien(arbeit, "HEAD", muster)
    orte = [f"{p}:{','.join(map(str, z))}" for p, z in sorted(datei_treffer.items())]
    bericht.add("sperrmuster dateien", not datei_treffer, f"Treffer in {len(datei_treffer)} Dateien {orte}")
    c_treffer, c_gesamt = sperrmuster_in_commits(arbeit, "HEAD", muster)
    bericht.add(
        "sperrmuster commits",
        c_treffer <= erlaubte,
        f"{c_treffer} von {c_gesamt} Commits in Nachricht oder Identität (erlaubt {erlaubte}, Lead #92)",
    )
    b_treffer, b_pfade = sperrmuster_in_historie(arbeit, "HEAD", muster)
    bericht.add(
        "sperrmuster historie (Zählwert)",
        True,
        f"{b_treffer} alte Dateistände in {len(b_pfade)} Pfaden {b_pfade}. Blockt nicht, Entscheid Lead.",
    )

    # 5. gitleaks über die ganze zu veröffentlichende Historie
    ok, text = gitleaks(arbeit, "HEAD", bericht_pfad)
    bericht.add("gitleaks", ok, f"{text}, Bericht {bericht_pfad}")
    return bericht


def _jetzt() -> dt.datetime:
    return dt.datetime.now(WIEN)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument(
        "--quelle", type=Path, default=Path.cwd(), help="Repo mit der Abgabe-Basis (Standard: hier)"
    )
    ap.add_argument("--quelle-ref", default="refs/remotes/origin/main", help="Ref der Abgabe-Basis")
    ap.add_argument("--erwarteter-kopf", help="40-stelliger Commit der Basis; Pflicht für --ausfuehren")
    ap.add_argument("--ziel-url", default=ZIEL_URL)
    ap.add_argument(
        "--sperrmuster", type=Path, required=True, help="Datei außerhalb des Repos, eine Regex je Zeile"
    )
    ap.add_argument("--erlaubte-commit-treffer", type=int, default=ERLAUBTE_COMMIT_TREFFER)
    ap.add_argument("--arbeitsordner", type=Path, help="leerer Ordner (Standard: neuer Ordner unter /tmp)")
    ap.add_argument("--nachweis", type=Path, help="JSON-Nachweis (Standard: im Arbeitsordner)")
    ap.add_argument("--nicht-vor", default=NICHT_VOR, help="frühester Push, Wiener Zeit (ISO)")
    ap.add_argument("--ausfuehren", action="store_true", help="wirklich pushen (nur Lead, Abgabetag)")
    a = ap.parse_args(argv)

    if re.search(r"://[^/@\s]+@", a.ziel_url):
        raise SystemExit(
            "--ziel-url ohne Zugangsdaten angeben; die Anmeldung läuft über den Git-Credential-Helper."
        )
    quelle = a.quelle.resolve()
    if quelle in (a.sperrmuster.resolve(), *a.sperrmuster.resolve().parents):
        raise SystemExit("Die Sperrmuster-Datei darf nicht im Repo liegen (öffentlich).")
    muster = lade_sperrmuster(a.sperrmuster)
    jetzt = _jetzt()
    if dt.datetime.fromisoformat(a.nicht_vor) < dt.datetime.fromisoformat(NICHT_VOR):
        raise SystemExit(f"--nicht-vor darf nicht vor {NICHT_VOR} liegen.")
    if a.ausfuehren:
        if not a.erwarteter_kopf or not re.fullmatch(r"[0-9a-f]{40}", a.erwarteter_kopf):
            raise SystemExit("--ausfuehren braucht --erwarteter-kopf mit 40 Zeichen.")
        if not nicht_vor_erreicht(jetzt, a.nicht_vor):
            raise SystemExit(f"Zu früh: GitHub-Push erst ab {a.nicht_vor} Wiener Zeit.")

    arbeit = a.arbeitsordner or Path(tempfile.mkdtemp(prefix="abgabe-github-"))
    arbeit.mkdir(parents=True, exist_ok=True)
    if any(arbeit.iterdir()):
        raise SystemExit(f"Arbeitsordner ist nicht leer: {arbeit}")
    print(f"Modus: {'AUSFÜHREN' if a.ausfuehren else 'Trockenlauf'} · Arbeitsordner {arbeit}", flush=True)

    nachricht = "Abgabe KI Challenge 2026: UC3 StatAgent, Team OneShotAndy"
    basis, kopf = baue_abgabe(arbeit, quelle, a.quelle_ref, a.ziel_url, nachricht)
    print(f"Basis {basis} · Abgabe-Commit {kopf}", flush=True)
    bericht = pruefe(
        arbeit, muster, arbeit.parent / f"{arbeit.name}-gitleaks.json", a.erlaubte_commit_treffer
    )
    if a.erwarteter_kopf:
        bericht.add(
            "basis-kopf", basis == a.erwarteter_kopf, f"Basis {basis[:12]}, erwartet {a.erwarteter_kopf[:12]}"
        )

    ergebnis = "nicht gepusht"
    remote_kopf = None
    push_zeit = None
    # Der Trockenlauf fragt GitHub auch bei offenen Befunden (ohne Wirkung), damit Zugang und
    # Fast-Forward früh feststehen. Der echte Push läuft nur, wenn alle Prüfungen bestanden sind.
    if bericht.ok or not a.ausfuehren:
        modus = [] if a.ausfuehren else ["--dry-run"]
        lauf = git(
            arbeit, "push", *modus, "--porcelain", a.ziel_url, f"HEAD:refs/heads/{ZIEL_BRANCH}", check=False
        )
        zusammen = (lauf.stdout + lauf.stderr).strip()
        bericht.add(
            "push" if a.ausfuehren else "push --dry-run",
            lauf.returncode == 0,
            zusammen.splitlines()[-1] if zusammen else f"rc {lauf.returncode}",
        )
        if a.ausfuehren and lauf.returncode == 0:
            ls = git(arbeit, "ls-remote", a.ziel_url, f"refs/heads/{ZIEL_BRANCH}", check=False).stdout.split()
            remote_kopf = ls[0] if ls else None
            push_zeit = _jetzt().isoformat(timespec="seconds")
            bericht.add("ls-remote", remote_kopf == kopf, f"GitHub {remote_kopf}, lokal {kopf}")
            ergebnis = "gepusht und zurückgelesen" if remote_kopf == kopf else "gepusht, Rücklesen abweichend"
        elif not a.ausfuehren:
            ergebnis = (
                "Trockenlauf: Push würde angenommen"
                if lauf.returncode == 0
                else "Trockenlauf: Push abgelehnt"
            )
    else:
        print("Prüfungen nicht bestanden, kein Push-Versuch.", flush=True)

    nachweis = {
        "modus": "ausfuehren" if a.ausfuehren else "trockenlauf",
        "zeit": jetzt.isoformat(timespec="seconds"),
        "ziel": "KIChallenge/OneShotAndy",
        "branch": ZIEL_BRANCH,
        "basis_commit": basis,
        "abgabe_commit": kopf,
        "github_kopf_danach": remote_kopf,
        "push_zeit": push_zeit,
        "ergebnis": ergebnis,
        "pruefungen": [{"name": b.name, "ok": b.ok, "text": b.text} for b in bericht.befunde],
    }
    ziel = a.nachweis or arbeit.parent / f"{arbeit.name}-nachweis.json"
    ziel.write_text(json.dumps(nachweis, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Nachweis: {ziel}", flush=True)
    print("Ergebnis:", "alles ok" if bericht.ok else "NICHT ok", f"({ergebnis})", flush=True)
    return 0 if bericht.ok else 1


def ohne_zugang(text: str) -> str:
    """Entfernt Nutzer und Passwort aus URLs (https://nutzer:pw@host → https://<verborgen>@host)."""
    return re.sub(r"://[^/@\s]+@", "://<verborgen>@", text)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except subprocess.CalledProcessError as fehler:
        # Kein Traceback: der würde die vollständige Befehlszeile samt URL zeigen.
        befehl = " ".join(ohne_zugang(str(x)) for x in fehler.cmd[:4])
        print(f"Abbruch: {befehl} … rc {fehler.returncode}", file=sys.stderr)
        print(ohne_zugang((fehler.stderr or "").strip())[-2000:], file=sys.stderr)
        sys.exit(2)
