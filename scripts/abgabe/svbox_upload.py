#!/usr/bin/env python3
"""Abgabe in den SV-Box-Teamordner (Nextcloud-Share des Veranstalters, WebDAV).

Ohne Schalter ist das ein Trockenlauf. Das Skript
- liest `abgabe/manifest.json` und prüft jede Datei lokal (Größe, sha256), auch die Ministeriums-CSV,
  die nicht im Repo liegt (`--csv`),
- liest den Teamordner per PROPFIND (nur lesen) und zeigt, was schon dort liegt,
- listet die geplanten Uploads.
Nach außen schreibt es nichts.

Mit `--ausfuehren` (nur der Lead, Freigabe des Owners) lädt es jede Datei per PUT hoch, legt Unterordner
per MKCOL an, liest danach Größe (PROPFIND) und sha256 (GET) jeder Datei zurück und schreibt einen
Transfernachweis ohne Zugangsdaten.

Zugang nie als Argument: `SVBOX_TEAM_URL` (Share-Link, daraus nur der Host), `SVBOX_TEAM_TOKEN`,
`SVBOX_TEAM_PW` kommen aus `--env-datei <.env.local>` (gewinnt) oder der Prozess-Umgebung.
Die Ausgabe nennt weder Link noch Token noch Passwort.

Nur Standardbibliothek.
"""

from __future__ import annotations

import argparse
import base64
import datetime as dt
import hashlib
import http.client
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from zoneinfo import ZoneInfo

WIEN = ZoneInfo("Europe/Vienna")
DAV = "{DAV:}"
# Nur Hilfsdateien des Repos, keine Ergebnisse.
NICHT_HOCHLADEN = {".gitignore"}
EXTERN_PREFIX = "extern"
# Der Host weist nach rund 10 schnellen Anfragen Verbindungen ab (gemessen 05.11., docs/abgabe/README.md).
PAUSE_S = 2.0
# Gemessen bei 143 Anfragen im 2-s-Takt: 2,85 s je Anfrage, also 0,85 s Antwortzeit (nur lesend).
ANTWORT_S = 0.85
# So lange wartet eine einzelne Anfrage höchstens auf das Ende einer Abweisung.
GEDULD_S = 900
ERSTE_WARTEZEIT_S = 15
LAENGSTE_WARTEZEIT_S = 120
# Nur diese HTTP-Antworten sind eine Abweisung. 401, 403, 404 und alle anderen brechen sofort ab.
ABWEISUNG_HTTP = frozenset({429, 502, 503, 504})
# Probe des Schreibwegs: genau dieser Ordner und diese Datei, sonst nichts (Freigabe des Owners nötig).
PROBE_ORDNER = "_probe-lead"
PROBE_DATEI = f"{PROBE_ORDNER}/probe.txt"
PROBE_INHALT = b"Probe des Upload-Wegs, Team OneShotAndy. Keine Daten, wird gleich wieder geloescht.\n"


@dataclass(frozen=True)
class Datei:
    name: str  # relativ zum Teamordner, mit / getrennt
    lokal: Path
    groesse: int
    sha256: str


class Abgewiesen(RuntimeError):
    """Der Host hat länger als die Geduld abgewiesen."""


class _KeineWeiterleitung(urllib.request.HTTPRedirectHandler):
    """Weiterleitungen ablehnen: urllib gäbe sonst den Authorization-Kopf an das neue Ziel weiter."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: ANN001, ANN201
        raise urllib.error.HTTPError(req.full_url, code, f"Weiterleitung abgelehnt ({code})", headers, fp)


_OHNE_WEITERLEITUNG = urllib.request.build_opener(_KeineWeiterleitung)


class Zugang:
    """WebDAV-Zugang zum Public Share. Gibt sich nie selbst aus."""

    def __init__(
        self,
        share_url: str,
        token: str,
        passwort: str,
        pause: float = PAUSE_S,
        geduld: float = GEDULD_S,
        schlaf=time.sleep,
    ) -> None:
        teile = urllib.parse.urlsplit(share_url)
        if teile.scheme != "https" or not teile.netloc:
            raise SystemExit("SVBOX_TEAM_URL ist kein https-Link.")
        self.basis = f"https://{teile.netloc}/public.php/webdav/"
        self._auth = "Basic " + base64.b64encode(f"{token}:{passwort}".encode()).decode()
        self.pause = pause
        self.geduld = geduld
        self._schlaf = schlaf
        self._erste = True
        self.anfragen = 0
        self.abweisungen = 0

    def __repr__(self) -> str:  # nie Zugangsdaten in Tracebacks
        return "Zugang(<verborgen>)"

    def url(self, name: str = "") -> str:
        return self.basis + urllib.parse.quote(name)

    def abruf(
        self, methode: str, name: str = "", daten: bytes | None = None, kopf: dict | None = None
    ) -> tuple[int, bytes]:
        """Eine WebDAV-Anfrage im Takt; gibt (Status, Antwort) zurück.

        Abweisung und Netzfehler werden wiederholt, jede andere HTTP-Antwort geht sofort als HTTPError
        nach oben. Wiederholt werden darf alles: PUT überschreibt, GET und PROPFIND lesen nur, und MKCOL
        meldet beim zweiten Mal 405 (siehe ``hochladen``).
        """
        beginn = time.monotonic()
        wartezeit = ERSTE_WARTEZEIT_S
        while True:
            if not self._erste:
                self._schlaf(self.pause)
            self._erste = False
            self.anfragen += 1
            req = urllib.request.Request(self.url(name), data=daten, method=methode)
            req.add_header("Authorization", self._auth)
            for k, v in (kopf or {}).items():
                req.add_header(k, v)
            try:
                with _OHNE_WEITERLEITUNG.open(req, timeout=120) as antwort:
                    return antwort.status, antwort.read()
            except urllib.error.HTTPError as fehler:
                if fehler.code not in ABWEISUNG_HTTP:
                    raise
                grund = f"HTTP {fehler.code}"
            except (urllib.error.URLError, http.client.HTTPException, OSError) as fehler:
                grund = type(getattr(fehler, "reason", fehler)).__name__
            self.abweisungen += 1
            if time.monotonic() - beginn >= self.geduld:
                raise Abgewiesen(
                    f"{methode} {name or '/'}: nach {self.geduld:.0f} s noch abgewiesen ({grund})"
                )
            print(f"  abgewiesen ({grund}), neuer Versuch in {wartezeit} s", flush=True)
            self._schlaf(wartezeit)
            wartezeit = min(wartezeit * 2, LAENGSTE_WARTEZEIT_S)

    def rechte(self) -> str | None:
        """Nextcloud-Rechte des Share-Ordners (z. B. „RGDNVCK“; C/K = anlegen), None wenn nicht gemeldet."""
        koerper = (
            b'<?xml version="1.0"?><d:propfind xmlns:d="DAV:" xmlns:oc="http://owncloud.org/ns">'
            b"<d:prop><oc:permissions/></d:prop></d:propfind>"
        )
        _, xml = self.abruf("PROPFIND", "", koerper, {"Depth": "0", "Content-Type": "application/xml"})
        return ET.fromstring(xml).findtext(".//{http://owncloud.org/ns}permissions") or None

    def liste(self, ordner: str = "") -> dict[str, int | None]:
        """Alle Dateien im Teamordner, Name → Größe; Ordner haben Größe None.

        Rekursiv mit Depth 1 je Ordner, weil Nextcloud Depth infinity meist abweist.
        """
        koerper = (
            b'<?xml version="1.0"?><d:propfind xmlns:d="DAV:"><d:prop>'
            b"<d:getcontentlength/><d:resourcetype/></d:prop></d:propfind>"
        )
        ziel = ordner + "/" if ordner else ""
        _, xml = self.abruf("PROPFIND", ziel, koerper, {"Depth": "1", "Content-Type": "application/xml"})
        ergebnis = eintraege(xml, urllib.parse.urlsplit(self.basis).path)
        for name, groesse in list(ergebnis.items()):
            if groesse is None and name != ordner:
                ergebnis.update(self.liste(name))
        ergebnis.pop(ordner, None)
        return ergebnis


def eintraege(xml: bytes, pfad_basis: str) -> dict[str, int | None]:
    """PROPFIND-Antwort → Name relativ zum Share → Größe (Ordner: None). Der Share selbst fehlt."""
    ergebnis: dict[str, int | None] = {}
    for antwort in ET.fromstring(xml).iter(f"{DAV}response"):
        href = urllib.parse.unquote(urllib.parse.urlsplit(antwort.findtext(f"{DAV}href") or "").path)
        name = href[len(pfad_basis) :] if href.startswith(pfad_basis) else href
        name = name.strip("/")
        if not name:
            continue
        ordner = antwort.find(f".//{DAV}resourcetype/{DAV}collection") is not None
        laenge = antwort.findtext(f".//{DAV}getcontentlength")
        ergebnis[name] = None if ordner else int(laenge or 0)
    return ergebnis


ZUGANG_SCHLUESSEL = ("SVBOX_TEAM_URL", "SVBOX_TEAM_TOKEN", "SVBOX_TEAM_PW")


def lade_env_datei(pfad: Path, schluessel: tuple[str, ...] = ZUGANG_SCHLUESSEL) -> dict[str, str]:
    """Liest nur die genannten Schlüssel aus einer .env-Datei (KEY=wert, optional in Anführungszeichen).

    Die Datei gewinnt gegen geerbte Variablen. Werte gehen in den Prozess, nie in die Ausgabe.
    """
    werte: dict[str, str] = {}
    for zeile in pfad.read_text(encoding="utf-8").splitlines():
        zeile = zeile.strip()
        if zeile.startswith("export "):
            zeile = zeile[len("export ") :].lstrip()
        name, gleich, wert = zeile.partition("=")
        if not gleich or name.strip() not in schluessel:
            continue
        wert = wert.strip()
        if len(wert) >= 2 and wert[0] == wert[-1] and wert[0] in "'\"":
            wert = wert[1:-1]
        werte[name.strip()] = wert
    return werte


def sha256_datei(pfad: Path) -> str:
    h = hashlib.sha256()
    with pfad.open("rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def plane(manifest: dict, abgabe_ordner: Path, csv: Path | None) -> tuple[list[Datei], list[str]]:
    """Dateien aus dem Manifest mit lokalem Pfad; zweite Liste: Abweichungen (leer = alles stimmt)."""
    dateien: list[Datei] = []
    fehler: list[str] = []
    for eintrag in manifest["dateien"]:
        name = eintrag["datei"]
        if name in NICHT_HOCHLADEN:
            continue
        if eintrag["ort"].startswith(EXTERN_PREFIX):
            if csv is None:
                fehler.append(f"{name}: liegt nicht im Repo, Pfad mit --csv angeben")
                continue
            if csv.name != Path(name).name:
                fehler.append(f"{name}: --csv heißt {csv.name}")
                continue
            lokal = csv
        else:
            lokal = abgabe_ordner / name
        if not lokal.is_file():
            fehler.append(f"{name}: fehlt lokal")
            continue
        groesse, sha = lokal.stat().st_size, sha256_datei(lokal)
        if groesse != eintrag["groesse"] or sha != eintrag["sha256"]:
            fehler.append(
                f"{name}: lokal {groesse} B / {sha[:12]}, "
                f"Manifest {eintrag['groesse']} B / {eintrag['sha256'][:12]}"
            )
            continue
        dateien.append(Datei(name, lokal, groesse, sha))
    return dateien, fehler


def ordner_von(dateien: list[Datei]) -> list[str]:
    """Alle nötigen Unterordner, Eltern vor Kindern."""
    ordner = set()
    for d in dateien:
        teile = d.name.split("/")[:-1]
        for i in range(1, len(teile) + 1):
            ordner.add("/".join(teile[:i]))
    return sorted(ordner, key=lambda o: (o.count("/"), o))


def hochladen(zugang: Zugang, dateien: list[Datei], vorhanden: dict[str, int | None]) -> None:
    """Legt fehlende Ordner an und überschreibt jede Datei. Löscht nichts, darum beliebig wiederholbar."""
    for o in ordner_von(dateien):
        if o in vorhanden:
            continue
        try:
            zugang.abruf("MKCOL", o + "/")
            print(f"  Ordner angelegt: {o}/", flush=True)
        except urllib.error.HTTPError as fehler:
            if fehler.code != 405:  # 405: gibt es schon, etwa nach einer Wiederholung
                raise
    for i, d in enumerate(dateien, 1):
        status, _ = zugang.abruf(
            "PUT", d.name, d.lokal.read_bytes(), {"Content-Type": "application/octet-stream"}
        )
        print(f"  PUT {i}/{len(dateien)} {d.name} ({d.groesse} B): HTTP {status}", flush=True)


def zuruecklesen(zugang: Zugang, dateien: list[Datei]) -> list[dict]:
    liste = zugang.liste()
    zeilen = []
    for d in dateien:
        try:
            sha = hashlib.sha256(zugang.abruf("GET", d.name)[1]).hexdigest()
        except urllib.error.HTTPError as e:
            sha = f"HTTP {e.code}"
        except Abgewiesen:
            sha = "abgewiesen"
        zeilen.append(
            {
                "datei": d.name,
                "groesse": d.groesse,
                "sha256": d.sha256,
                "groesse_svbox": liste.get(d.name),
                "sha256_svbox": sha,
                "gleich": liste.get(d.name) == d.groesse and sha == d.sha256,
            }
        )
    return zeilen


def pruefe_kopf(abgabe: Path, erwartet: str) -> list[str]:
    """Abweichungen des Checkouts: HEAD ist nicht der erwartete Commit oder abgabe/ ist nicht sauber."""
    fehler = []
    kopf = subprocess.run(
        ["git", "-C", str(abgabe), "rev-parse", "HEAD"], capture_output=True, text=True, check=False
    ).stdout.strip()
    if kopf != erwartet:
        fehler.append(f"HEAD {kopf[:12] or 'unbekannt'} ist nicht der erwartete Kopf {erwartet[:12]}")
    status = subprocess.run(
        ["git", "-C", str(abgabe), "status", "--porcelain", "--", "."],
        capture_output=True,
        text=True,
        check=False,
    )
    if status.returncode != 0 or status.stdout.strip():
        fehler.append("abgabe/ ist nicht sauber (geänderte oder neue Dateien)")
    return fehler


def _im_probeordner(name: str) -> bool:
    return name == PROBE_ORDNER or name.startswith(PROBE_ORDNER + "/")


def probe(zugang: Zugang) -> int:
    """Schreibt genau eine Testdatei in einen eigenen Ordner, liest sie zurück und löscht beide wieder.

    Der Ordner muss neu sein: Gibt es ihn schon, ändert die Probe nichts. WebDAV-DELETE auf einen Ordner
    löscht rekursiv, darum entfällt es, sobald etwas anderes als die Testdatei darin aufgetaucht ist.
    """
    davor = zugang.liste()
    if any(_im_probeordner(n) for n in davor):
        print(f"[FEHLT] {PROBE_ORDNER} gibt es schon, Probe abgebrochen, nichts geändert.")
        return 1
    beginn = time.monotonic()
    try:
        zugang.abruf("MKCOL", PROBE_ORDNER + "/")
    except urllib.error.HTTPError as fehler:
        print(f"[FEHLT] Ordner anlegen: HTTP {fehler.code}. Nichts gelöscht, Teamordner von Hand prüfen.")
        return 1
    gleich = False
    try:
        zugang.abruf("PUT", PROBE_DATEI, PROBE_INHALT, {"Content-Type": "text/plain"})
        gleich = zugang.abruf("GET", PROBE_DATEI)[1] == PROBE_INHALT
        print(f"[{'ok' if gleich else 'FEHLT'}] geschrieben und zurückgelesen: {PROBE_DATEI}", flush=True)
    finally:
        _probe_aufraeumen(zugang)
    danach = zugang.liste()
    weg = not any(_im_probeordner(n) for n in danach)
    unveraendert = danach == davor
    print(f"[{'ok' if weg else 'FEHLT'}] Testdatei und Ordner wieder weg", flush=True)
    print(f"[{'ok' if unveraendert else 'FEHLT'}] Teamordner wie vorher: {len(danach)} Einträge", flush=True)
    print(
        f"    {zugang.anfragen} Anfragen, {zugang.abweisungen} Abweisungen, "
        f"{time.monotonic() - beginn:.0f} s für die Schreibschritte",
        flush=True,
    )
    return 0 if gleich and weg and unveraendert else 1


def _probe_aufraeumen(zugang: Zugang) -> None:
    """Löscht die Testdatei, dann den Ordner, aber nur, wenn er danach wirklich leer ist."""
    try:
        try:
            zugang.abruf("DELETE", PROBE_DATEI)
        except urllib.error.HTTPError as fehler:
            if fehler.code != 404:
                print(f"[FEHLT] löschen {PROBE_DATEI}: HTTP {fehler.code}, von Hand prüfen", flush=True)
        rest = [n for n in zugang.liste(PROBE_ORDNER) if n != PROBE_ORDNER]
        if rest:
            print(f"[FEHLT] {PROBE_ORDNER}/ ist nicht leer, Ordner bleibt: {rest}", flush=True)
            return
        zugang.abruf("DELETE", PROBE_ORDNER + "/")
    except urllib.error.HTTPError as fehler:
        print(f"[FEHLT] aufräumen: HTTP {fehler.code}, {PROBE_ORDNER}/ von Hand prüfen", flush=True)
    except Abgewiesen:
        print(f"[FEHLT] aufräumen: abgewiesen, {PROBE_ORDNER}/ von Hand prüfen", flush=True)


def anzahl_anfragen(dateien: list[Datei], vorhanden: dict[str, int | None]) -> int:
    """Anfragen eines ganzen Uploads: Liste und Rechte, MKCOL, PUT, GET und zwei Listen zum Schluss."""
    ordner = ordner_von(dateien)
    alte_liste = 1 + sum(1 for g in vorhanden.values() if g is None)
    neu = sum(1 for o in ordner if o not in vorhanden)
    return alte_liste + 1 + neu + 2 * len(dateien) + 2 * (1 + len(ordner))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--abgabe", type=Path, default=Path("abgabe"), help="Ordner mit manifest.json")
    ap.add_argument("--csv", type=Path, help="Pfad zur ministerium_2026-07.csv (außerhalb des Repos)")
    ap.add_argument(
        "--nachweis", type=Path, help="Transfernachweis (Standard: docs/abgabe/transfernachweis.json)"
    )
    ap.add_argument("--env-datei", type=Path, help=".env.local mit SVBOX_TEAM_* (gewinnt gegen die Umgebung)")
    ap.add_argument("--ohne-netz", action="store_true", help="nur lokal prüfen, den Teamordner nicht lesen")
    ap.add_argument("--erwarteter-kopf", help="40-stelliger Commit des Checkouts; Pflicht für --ausfuehren")
    ap.add_argument(
        "--probe",
        action="store_true",
        help=f"nur eine Testdatei in {PROBE_ORDNER}/ schreiben und wieder löschen (Freigabe Owner)",
    )
    ap.add_argument("--pause", type=float, default=PAUSE_S, help="Sekunden zwischen zwei Anfragen")
    ap.add_argument("--ausfuehren", action="store_true", help="wirklich hochladen (nur Lead, Freigabe Owner)")
    a = ap.parse_args(argv)

    if a.probe:
        if a.ausfuehren:
            raise SystemExit("--probe und --ausfuehren schließen sich aus.")
        zugang = _zugang(a)
        try:
            return probe(zugang)
        except urllib.error.HTTPError as e:
            print(f"[FEHLT] Probe abgebrochen: HTTP {e.code}")
        except Abgewiesen as e:
            print(f"[FEHLT] Probe abgebrochen: {e}")
        return 1
    if a.ausfuehren and not (a.erwarteter_kopf and len(a.erwarteter_kopf) == 40):
        raise SystemExit("--ausfuehren braucht --erwarteter-kopf mit 40 Zeichen.")
    manifest = json.loads((a.abgabe / "manifest.json").read_text(encoding="utf-8"))
    dateien, fehler = plane(manifest, a.abgabe, a.csv)
    if a.erwarteter_kopf:
        kopf_fehler = pruefe_kopf(a.abgabe, a.erwarteter_kopf)
        text = "; ".join(kopf_fehler) or "erwarteter Kopf, abgabe/ sauber"
        print(f"[{'FEHLT' if kopf_fehler else 'ok'}] checkout: {text}")
        fehler.extend(kopf_fehler)
    jetzt = dt.datetime.now(WIEN)
    print(f"Modus: {'AUSFÜHREN' if a.ausfuehren else 'Trockenlauf'} · Manifest-Stand {manifest.get('stand')}")
    print(f"[{'ok' if not fehler else 'FEHLT'}] lokal: {len(dateien)} Dateien stimmen mit dem Manifest")
    for f in fehler:
        print(f"    {f}")
    if not dateien and not fehler:
        fehler.append("Manifest nennt keine Dateien")
    gesamt = sum(d.groesse for d in dateien)
    print(f"    {gesamt / 1e6:.1f} MB, Ordner: {ordner_von(dateien)}")

    if a.ohne_netz:
        return 0 if not fehler else 1
    zugang = _zugang(a)
    try:
        return _mit_netz(a, zugang, manifest, dateien, fehler, jetzt)
    except urllib.error.HTTPError as e:
        print(f"[FEHLT] Abbruch: HTTP {e.code}. Upload nicht vollständig, Zugang und Teamordner prüfen.")
    except Abgewiesen as e:
        print(f"[FEHLT] Abbruch: {e}. Upload nicht vollständig.")
    print("Ein zweiter Aufruf mit --ausfuehren ist gefahrlos: Er überschreibt und löscht nichts sonst.")
    return 1


def pruefe_link(share_url: str, token: str) -> None:
    """Vom Link zählt nur der Host, das Ziel bestimmt der Token: Beide müssen zum selben Share gehören."""
    pfad = urllib.parse.urlsplit(share_url).path.rstrip("/")
    if not pfad.endswith(f"/s/{token}"):
        raise SystemExit("SVBOX_TEAM_URL und SVBOX_TEAM_TOKEN gehören nicht zum selben Share, kein Zugriff.")


def _zugang(a: argparse.Namespace) -> Zugang:
    umgebung = {k: os.environ[k] for k in ZUGANG_SCHLUESSEL if k in os.environ}
    if a.env_datei:
        umgebung.update(lade_env_datei(a.env_datei))
    fehlend = [k for k in ZUGANG_SCHLUESSEL if not umgebung.get(k)]
    if fehlend:
        raise SystemExit(
            f"Zugang fehlt: {', '.join(fehlend)} (--env-datei <.env.local> oder Prozess-Umgebung)"
        )
    pruefe_link(umgebung["SVBOX_TEAM_URL"], umgebung["SVBOX_TEAM_TOKEN"])
    return Zugang(*(umgebung[k] for k in ZUGANG_SCHLUESSEL), pause=a.pause)


def _mit_netz(
    a: argparse.Namespace,
    zugang: Zugang,
    manifest: dict,
    dateien: list[Datei],
    fehler: list[str],
    jetzt: dt.datetime,
) -> int:
    gesamt = sum(d.groesse for d in dateien)
    vorhanden = zugang.liste()
    rechte = zugang.rechte()
    darf = rechte is not None and "C" in rechte and "K" in rechte
    print(
        f"[{'ok' if darf else 'FEHLT'}] teamordner rechte: {rechte or 'nicht gemeldet'}",
        "(C = Dateien anlegen, K = Ordner anlegen)",
    )
    if not darf:
        fehler.append("Teamordner meldet kein Recht zum Anlegen")
    dateien_dort = {n: g for n, g in vorhanden.items() if g is not None}
    print(
        f"[ok] teamordner lesen: {len(dateien_dort)} Dateien,",
        f"{len(vorhanden) - len(dateien_dort)} Ordner dort",
    )
    gleich = [d.name for d in dateien if dateien_dort.get(d.name) == d.groesse]
    fremd = sorted(set(dateien_dort) - {d.name for d in dateien})
    print(f"    schon dort mit gleicher Größe: {len(gleich)}")
    print(f"[{'FEHLT' if fremd else 'ok'}] nicht im Manifest: {fremd or 0}")
    print(
        f"    geplant: {len(dateien)} × PUT,",
        f"{len([o for o in ordner_von(dateien) if o not in vorhanden])} × MKCOL, je Datei ein GET",
    )
    anfragen = anzahl_anfragen(dateien, vorhanden)
    dauer = anfragen * (a.pause + ANTWORT_S) / 60
    print(f"    Dauer im Takt ({a.pause:g} s): rund {dauer:.0f} min für {anfragen} Anfragen")

    if not a.ausfuehren:
        if fremd:
            print("Trockenlauf: nichts hochgeladen. Der Upload gäbe Exit 1, siehe abgabe/CHECKLISTE.md.")
        elif fehler:
            print("Trockenlauf: nichts hochgeladen. Erst die Abweichungen beheben.")
        else:
            print("Trockenlauf: nichts hochgeladen. Alles bereit.")
        return 0 if not fehler and not fremd else 1
    if fehler:
        print("Abweichungen zum Manifest, kein Upload.")
        return 1

    hochladen(zugang, dateien, vorhanden)
    zeilen = zuruecklesen(zugang, dateien)
    differenzen = [z["datei"] for z in zeilen if not z["gleich"]]
    print(f"    {zugang.anfragen} Anfragen, {zugang.abweisungen} Abweisungen", flush=True)
    namen = {d.name for d in dateien}
    fremd_danach = sorted(n for n, g in zugang.liste().items() if g is not None and n not in namen)
    if fremd_danach:
        # Das Kriterium verlangt volle Übereinstimmung mit dem Manifest. Das Skript löscht trotzdem nie etwas.
        print(f"[FEHLT] nicht im Manifest, nichts gelöscht: {fremd_danach}", flush=True)
    differenzen = differenzen + fremd_danach
    nachweis = {
        "zeit": dt.datetime.now(WIEN).isoformat(timespec="seconds"),
        "beginn": jetzt.isoformat(timespec="seconds"),
        "ziel": "SV-Box-Teamordner OneShotAndy",
        "commit": a.erwarteter_kopf,
        "manifest_stand": manifest.get("stand"),
        "anzahl": len(zeilen),
        "bytes": gesamt,
        "anfragen": zugang.anfragen,
        "abweisungen": zugang.abweisungen,
        "differenzen": len(differenzen),
        "abweichend": differenzen,
        "fremd_im_teamordner": fremd_danach,
        "dateien": zeilen,
    }
    ziel = a.nachweis or Path("docs/abgabe/transfernachweis.json")
    ziel.parent.mkdir(parents=True, exist_ok=True)
    ziel.write_text(json.dumps(nachweis, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        f"[{'ok' if not differenzen else 'FEHLT'}] zurückgelesen: {len(zeilen)} Dateien,",
        f"{len(differenzen)} Differenzen",
    )
    print(f"Nachweis: {ziel}")
    return 0 if not differenzen else 1


if __name__ == "__main__":
    sys.exit(main())
