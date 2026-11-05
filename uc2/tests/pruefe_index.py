"""Unabhängiges Prüfskript (Oracle) für den Belege-Index (Issue #40).

Importiert keinen uc2-Laufzeitcode, nur Standardbibliothek und psycopg. Es bildet md5, Inhaltsverzeichnis,
Seitentexte ab der Startzeile und Autor:in-Werte selbst aus den PDFs (`pdftotext`, je Artikel die eigene
Seite) und vergleicht sie mit dem Schema `uc2` in PostgreSQL.

Aufruf:
    uv run python uc2/tests/pruefe_index.py --presse <ordner> --ab 2026-01-01 [--db healthpolicy] [--json]
            [--nur-diese-quellen] [--jobs 4] [--max-je-ausgabe 1] [--erwartete-dubletten 10]

Verbindung wie `uc2.db` (hier nachgebaut): `UC2_DATABASE_URL` gewinnt, sonst `PG*`-Variablen (Standard
localhost:5433, statistik/statistik) mit DB `UC2_DB` bzw. `healthpolicy`; `--db` ersetzt nur den DB-Namen.
Exit 0: alle Prüfungen bestanden. Exit 1: mindestens ein Verstoß. Exit 2: Betriebsfehler (DB, pdftotext).

Datenschutz: Das Skript gibt weder Pressetext noch Personennamen aus, nur Zahlen, Dateinamen, IDs, Seiten
und Kurz-Hashes normalisierter Titel.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import unicodedata
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

import psycopg
from psycopg.conninfo import make_conninfo

MODELL = "google/embeddinggemma-2"
DIM = 768
# Grenzen der Inhaltsverzeichnis-Prüfung. Issue #40, Akzeptanz: „Abweichungen ≤ 1 je Ausgabe werden gelistet“;
# PRD docs/plan/uc2/2026-11-05-healthpolicy-simulator.md § 3 Belege: „höchstens 2 Abweichungen je Ausgabe und
# 15 in Summe“. Je Ausgabe gilt die strengere Zahl aus #40, die Summe nennt nur die PRD.
MAX_JE_AUSGABE = 1
MAX_GESAMT = 15
# Lauf v3 (05.11., 187 PDF) meldete 10 Text-Dubletten-Ausnahmen; mehr als erwartet ist ein Verstoß.
ERWARTETE_DUBLETTEN = 10
MAX_LISTE = 40
VERGLEICH_ZEICHEN = 80
DACHZEILE_ZEICHEN = 300
"""Normalisierte Zeichen, die auf der Seite vor dem Titel stehen dürfen (Dachzeile, höchstens 2 Zeilen)."""

DATEI_RE = re.compile(r"^Pressespiegel vom (\d{2})\.(\d{2})\.(\d{4})\.pdf$", re.IGNORECASE)
EINTRAG_RE = re.compile(r"^\s*S\.\s*(\d+)\s{2,}(\S.*?)\s*$")
META_RE = re.compile(r"^\s*(\d{2}\.\d{2}\.\d{4}),\s+(\S.*?)\s*$")
SEITE_ENDE_RE = re.compile(r",\s+Seite\s+\S.*$")
FUSS_RE = re.compile(r"Seite\s+\d+\s+von\s+\d+.*©\s*APA-Comm")
STARTZEILE_RE = re.compile(r"^(\S.*?) vom \d{2}\.\d{2}\.\d{4}$")
FELDBLOCK_RE = re.compile(r"^(Sender|Quelle)\s{2,}\S")
SENDER_RE = re.compile(r"^Sender\s{2,}\S")
TRANSKRIPT_RE = re.compile(r"^\(\d\d:\d\d:\d\d\)")
SPRECHER_RE = re.compile(r"\(\d+ Sekunden\)$")
# Feld `Autor:in` an beliebiger Stelle der Zeile (zweispaltiger Feldblock); „Autor:innen“ trifft nicht.
AUTOR_RE = re.compile(r"Autor:in(\s|$)")
AUTOR_WERT_RE = re.compile(r"Autor:in\s{2,}(\S.*?)(?:\s{2,}|$)")
AUTOR_SQL = r"Autor:in([[:space:]]|$)"
WORT_RE = re.compile(r"\w+")


@dataclass(frozen=True)
class Eintrag:
    seite: int
    titel: str
    medium: str


# --------------------------------------------------------------------------------------------- Hilfen


def kurz_hash(schluessel: str) -> str:
    return hashlib.sha1(schluessel.encode("utf-8")).hexdigest()[:8]


def titel_schluessel(titel: str) -> str:
    """Normalisierung: NFKC, klein, Silbentrennung und Leerraum entfallen (Bindestrich-Schreibweisen egal)."""
    t = unicodedata.normalize("NFKC", titel).casefold().replace("­", "")
    return re.sub(r"[\s\-‐‑‒–]+", "", t)


def vergleichsform(text: str) -> str:
    """Für den Textvergleich: NFKC, klein, ohne Leerraum, Satzzeichen und Bindestriche.

    Strenger als „Leerraum zusammenfassen“, weil der Indexer Silbentrennung am Zeilenende auflöst
    („Arznei-“ + „mitteln“) und Zeilen zu Absätzen verbindet; beides darf den Vergleich nicht stören.
    """
    t = unicodedata.normalize("NFKC", text).casefold()
    return re.sub(r"[\W_]+", "", t)


def medium_schluessel(medium: str) -> str:
    return re.sub(r"\s+", " ", unicodedata.normalize("NFKC", medium)).strip().casefold()


def md5_datei(pfad: Path) -> str:
    h = hashlib.md5(usedforsecurity=False)
    with pfad.open("rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def pdftotext(pdf: Path, erste: int | None = None, letzte: int | None = None) -> str:
    cmd = ["pdftotext", "-q", "-layout"]
    if erste is not None and letzte is not None:
        cmd += ["-f", str(erste), "-l", str(letzte)]
    cmd += [str(pdf), "-"]
    res = subprocess.run(cmd, capture_output=True, check=False, timeout=300)
    if res.returncode != 0:
        raise RuntimeError(f"pdftotext Exit {res.returncode} für {pdf.name}")
    return res.stdout.decode("utf-8", errors="replace")


def seiten_von(text: str) -> list[list[str]]:
    teile = text.split("\f")
    if teile and not teile[-1].strip():
        teile.pop()
    return [t.split("\n") for t in teile]


# ------------------------------------------------------------------------------ Inhaltsverzeichnis


def _ist_rahmen(zeile: str) -> bool:
    s = zeile.strip()
    return s == "Pressespiegel" or bool(FUSS_RE.search(s))


def parse_verzeichnis(seiten: list[list[str]]) -> tuple[list[Eintrag], int]:
    """Parst das Verzeichnis ab der Seite mit „Inhaltsverzeichnis“.

    Gibt (Einträge, Zahl der belegten Seiten ab Beginn des Verzeichnisses) zurück. Eine Folgeseite gehört
    dazu, wenn sie einen Eintrag beginnt oder einen offenen Eintrag abschließt.
    """
    start = next((i for i, s in enumerate(seiten) if any(z.strip() == "Inhaltsverzeichnis" for z in s)), None)
    if start is None:
        return [], 0
    eintraege: list[Eintrag] = []
    offen: tuple[int, list[str]] | None = None
    belegt = 0
    for idx in range(start, len(seiten)):
        zeilen = seiten[idx]
        if idx == start:
            marke = next(i for i, z in enumerate(zeilen) if z.strip() == "Inhaltsverzeichnis")
            zeilen = zeilen[marke + 1 :]
        nutzt_seite = idx == start
        for zeile in zeilen:
            if not zeile.strip() or _ist_rahmen(zeile):
                continue
            beginn = EINTRAG_RE.match(zeile)
            if beginn:
                offen = (int(beginn.group(1)), [beginn.group(2)])
                nutzt_seite = True
                continue
            if offen is None:
                continue
            meta = META_RE.match(zeile)
            if meta:
                medium = SEITE_ENDE_RE.sub("", meta.group(2)).strip()
                eintraege.append(Eintrag(offen[0], " ".join(offen[1]), medium))
                offen = None
                nutzt_seite = True
            else:
                offen[1].append(zeile.strip())
        if not nutzt_seite:
            break
        belegt += 1
    return eintraege, belegt


def lies_verzeichnis(pdf: Path) -> list[Eintrag]:
    """Holt die Verzeichnisseiten per `pdftotext -f 1 -l N`; N wächst, bis das Verzeichnis endet."""
    bis = 4
    while True:
        seiten = seiten_von(pdftotext(pdf, 1, bis))
        eintraege, belegt = parse_verzeichnis(seiten)
        start = next(
            (i for i, s in enumerate(seiten) if any(z.strip() == "Inhaltsverzeichnis" for z in s)),
            None,
        )
        ende_erreicht = len(seiten) < bis
        if start is not None and start + belegt < len(seiten):
            return eintraege
        if ende_erreicht:
            return eintraege
        bis *= 2


def autor_werte(pdf: Path) -> set[str]:
    """Autor:in-Werte aus den Feldblöcken; nur Werte mit mindestens zwei Wörtern, Leerraum vereinheitlicht."""
    werte: set[str] = set()
    for zeile in pdftotext(pdf).split("\n"):
        m = AUTOR_WERT_RE.search(zeile)
        if m:
            wert = " ".join(m.group(1).split())
            if len(wert.split()) >= 2:
                werte.add(wert)
    return werte


# ---------------------------------------------------------------------------------- Seite eines Artikels


@dataclass(frozen=True)
class Seitenrest:
    """Text einer Artikelseite ab der Zeile nach der Startzeile bis vor den Feldblock, in Vergleichsform."""

    text: str
    rundfunk: bool
    transkript: str = ""
    """Radio/TV: ab der ersten Zeile `(hh:mm:ss)`, ohne Sprecherzeilen `… (N Sekunden)`."""


def _inhalt(zeilen: list[str]) -> list[str]:
    return [z.strip() for z in zeilen if z.strip() and not _ist_rahmen(z) and not AUTOR_RE.search(z)]


def lies_seitenrest(pdf: Path, seite: int) -> Seitenrest | None:
    """Eigenes `pdftotext -f N -l N+1` für die Seite eines Artikels, ausgewertet mit `seitenrest`."""
    try:
        return seitenrest(seiten_von(pdftotext(pdf, seite, seite + 1)))
    except RuntimeError:
        return None  # Seite jenseits des Endes (pdftotext Exit 99): zählt als fehlende Startzeile


def seitenrest(seiten: list[list[str]]) -> Seitenrest | None:
    """Seiten N und N+1; None, wenn die erste Inhaltszeile von Seite N keine Startzeile ist.

    Seite N+1 zählt nur, wenn der Feldblock noch nicht kam und sie eine Pressespiegel-Seite ohne eigene
    Startzeile ist (keine Layout-Kopie, kein neuer Artikel).
    """
    if not seiten:
        return None
    erste = _inhalt(seiten[0])
    if not erste or not STARTZEILE_RE.match(erste[0]):
        return None
    zeilen = erste[1:]
    if len(seiten) > 1 and not any(FELDBLOCK_RE.match(z) for z in zeilen):
        folge = [z.strip() for z in seiten[1] if z.strip()]
        inhalt = _inhalt(seiten[1])
        if folge and folge[0] == "Pressespiegel" and not (inhalt and STARTZEILE_RE.match(inhalt[0])):
            zeilen += inhalt
    ende = next((i for i, z in enumerate(zeilen) if FELDBLOCK_RE.match(z)), len(zeilen))
    rundfunk = any(SENDER_RE.match(z) for z in zeilen[ende : ende + 8])
    beginn = next((i for i, z in enumerate(zeilen[:ende]) if TRANSKRIPT_RE.match(z)), ende)
    transkript = [z for z in zeilen[beginn:ende] if not SPRECHER_RE.search(z)]
    return Seitenrest(
        vergleichsform("\n".join(zeilen[:ende])), rundfunk, vergleichsform("\n".join(transkript))
    )


def passt(rest: Seitenrest, abschnitt: str, titel: str) -> bool:
    """Beginnt der (normalisierte) Abschnitt so, wie die Seite nach dem Titel weitergeht?

    Druck: Titel innerhalb der ersten Zeichen (davor höchstens eine Dachzeile) entfernen, dann müssen die
    ersten `VERGLEICH_ZEICHEN` Zeichen übereinstimmen. Radio/TV: Der Indexer behält nur Transkriptzeilen,
    deshalb muss der Abschnitt wie das Transkript beginnen. Beitrag nur mit Titel: Text = Titel.
    """
    anfang = abschnitt[:VERGLEICH_ZEICHEN]
    if not anfang:
        return False
    if abschnitt == titel and titel in rest.text[: len(titel) + DACHZEILE_ZEICHEN]:
        return True
    if rest.rundfunk:
        return bool(rest.transkript) and rest.transkript.startswith(anfang)
    if rest.text.startswith(anfang):
        return True  # Titel nicht abgetrennt (Indexer meldet „titel_abweichend“), Start stimmt trotzdem
    pos = rest.text.find(titel, 0, len(titel) + DACHZEILE_ZEICHEN) if titel else -1
    if pos < 0:
        return False
    return (rest.text[:pos] + rest.text[pos + len(titel) :]).startswith(anfang)


def lies_seitenreste(
    auftraege: list[tuple[Path, int]], jobs: int
) -> dict[tuple[Path, int], Seitenrest | None]:
    eindeutig = sorted(set(auftraege))
    with ThreadPoolExecutor(max_workers=jobs) as pool:
        return dict(zip(eindeutig, pool.map(lambda a: lies_seitenrest(*a), eindeutig), strict=True))


def lade_erste_abschnitte(conn: psycopg.Connection) -> list[str]:
    """Abschnitt 1 aller Artikel in PG, normalisiert (Beleg für Text-Dubletten)."""
    rows = conn.execute("select text from uc2.abschnitt where nr = 1").fetchall()
    return sorted({vergleichsform(r[0]) for r in rows})


# ------------------------------------------------------------------------------------------ Prüfungen


def ergebnis(name: str, verstoesse: list[str], **details: Any) -> dict[str, Any]:
    return {"pruefung": name, "ok": not verstoesse, "verstoesse": verstoesse, **details}


def finde_pdfs(ordner: Path, ab: date) -> list[tuple[Path, date]]:
    gefunden: list[tuple[Path, date]] = []
    for p in sorted(ordner.rglob("*.pdf")):
        m = DATEI_RE.match(p.name)
        if not m:
            continue
        tag = date(int(m.group(3)), int(m.group(2)), int(m.group(1)))
        if tag >= ab:
            gefunden.append((p, tag))
    return gefunden


def pruefe_md5(
    conn: psycopg.Connection, pdfs: list[tuple[Path, date]], ab: date, nur: bool
) -> tuple[dict[str, Any], dict[str, Path]]:
    je_md5: dict[str, list[Path]] = defaultdict(list)
    for pfad, _ in pdfs:
        je_md5[md5_datei(pfad)].append(pfad)
    dubletten = {m: ps for m, ps in je_md5.items() if len(ps) > 1}
    eindeutig = {m: ps[0] for m, ps in je_md5.items()}
    rows = conn.execute("select md5, datei from uc2.quelle where ausgabedatum >= %s", (ab,)).fetchall()
    in_pg = {r[0] for r in rows}
    anzahl_pg = len(in_pg)
    verstoesse: list[str] = []
    fehlen_in_pg = sorted(set(eindeutig) - in_pg)
    verstoesse += [f"md5 {m} ({eindeutig[m].name}) fehlt in uc2.quelle" for m in fehlen_in_pg]
    ueberzaehlig = sorted(in_pg - set(eindeutig))
    if not nur:
        verstoesse += [f"md5 {m} in uc2.quelle, aber nicht auf der Platte" for m in ueberzaehlig]
        if anzahl_pg != len(eindeutig):
            verstoesse.append(f"count(distinct md5): PG {anzahl_pg} != Platte {len(eindeutig)}")
    doppelt = [
        {"md5": m, "dateien": [p.name for p in ps], "in_pg": m in in_pg} for m, ps in dubletten.items()
    ]
    return (
        ergebnis(
            "md5",
            verstoesse,
            dateien_platte=len(pdfs),
            md5_eindeutig_platte=len(eindeutig),
            md5_pg=anzahl_pg,
            byte_gleiche_dubletten=doppelt,
        ),
        eindeutig,
    )


def pruefe_verzeichnisse(
    conn: psycopg.Connection,
    eindeutig: dict[str, Path],
    jobs: int,
    erste_abschnitte: list[str],
    max_je_ausgabe: int = MAX_JE_AUSGABE,
    erwartete_dubletten: int = ERWARTETE_DUBLETTEN,
) -> dict[str, Any]:
    """Inhaltsverzeichnis im PDF gegen uc2.artikel (Seite, Titel).

    Ein in PG fehlender Eintrag ist nur dann eine Text-Dublette (Ausnahme), wenn das Skript es selbst belegt:
    Der Seitentext ab der Startzeile im PDF beginnt wie ein Abschnitt 1, der schon in PG steht. Gemessen
    05.11. (Volllauf m5): solche Dubletten liegen auch in derselben Ausgabe oder unter anderem Medium.
    """
    with ThreadPoolExecutor(max_workers=jobs) as pool:
        verzeichnisse = dict(zip(eindeutig, pool.map(lies_verzeichnis, eindeutig.values()), strict=True))
    pg_artikel: dict[str, list[Eintrag]] = defaultdict(list)
    for md5, seite, titel, medium in conn.execute(
        "select quelle_md5, pdf_seite, titel, medium from uc2.artikel order by pdf_seite, artikel_id"
    ):
        pg_artikel[md5].append(Eintrag(seite, titel, medium))

    def als_dublette_belegt(pfad: Path, seite: int, titel: str) -> bool:
        rest = lies_seitenrest(pfad, seite)
        t = vergleichsform(titel)
        return rest is not None and any(passt(rest, a, t) for a in erste_abschnitte)

    je_ausgabe: list[dict[str, Any]] = []
    abweichungen: list[str] = []
    ausnahmen: list[str] = []
    verstoesse: list[str] = []
    gesamt = 0
    for md5, pfad in eindeutig.items():
        toc = verzeichnisse[md5]
        pg = pg_artikel.get(md5, [])
        offen_toc = Counter((e.seite, titel_schluessel(e.titel)) for e in toc)
        titel_je_schluessel = {(e.seite, titel_schluessel(e.titel)): e.titel for e in toc}
        offen_pg = Counter((e.seite, titel_schluessel(e.titel)) for e in pg)
        gleich = offen_toc & offen_pg
        offen_toc -= gleich
        offen_pg -= gleich
        meldungen: list[str] = []
        # gleicher Titel, andere Seite
        for (seite, schl), _ in list(offen_toc.items()):
            partner = next((k for k in offen_pg if k[1] == schl and offen_pg[k] > 0), None)
            if partner is not None and offen_toc[(seite, schl)] > 0:
                offen_toc[(seite, schl)] -= 1
                offen_pg[partner] -= 1
                meldungen.append(f"seite: Titel {kurz_hash(schl)} TOC S. {seite}, PG S. {partner[0]}")
        # gleiche Seite, anderer Titel
        for (seite, schl), _ in list(offen_toc.items()):
            partner = next((k for k in offen_pg if k[0] == seite and offen_pg[k] > 0), None)
            if partner is not None and offen_toc[(seite, schl)] > 0:
                offen_toc[(seite, schl)] -= 1
                offen_pg[partner] -= 1
                meldungen.append(f"titel: S. {seite} TOC {kurz_hash(schl)}, PG {kurz_hash(partner[1])}")
        ausnahmen_hier: list[str] = []
        for (seite, schl), n in offen_toc.items():
            if n <= 0:
                continue
            belegt = als_dublette_belegt(pfad, seite, titel_je_schluessel[(seite, schl)])
            for _ in range(n):
                if belegt:
                    ausnahmen_hier.append(f"text-dublette (Seitentext belegt): S. {seite} {kurz_hash(schl)}")
                else:
                    meldungen.append(f"fehlt in PG (kein Textbeleg): S. {seite} Titel {kurz_hash(schl)}")
        for (seite, schl), n in offen_pg.items():
            meldungen += [f"zusätzlich in PG: S. {seite} Titel {kurz_hash(schl)}"] * n
        gesamt += len(meldungen)
        name = pfad.name
        abweichungen += [f"{name}: {m}" for m in meldungen]
        ausnahmen += [f"{name}: {m}" for m in ausnahmen_hier]
        if len(meldungen) > max_je_ausgabe:
            verstoesse.append(f"{name}: {len(meldungen)} Abweichungen (> {max_je_ausgabe})")
        if not toc:
            verstoesse.append(f"{name}: Inhaltsverzeichnis nicht gelesen (0 Einträge)")
        je_ausgabe.append(
            {
                "datei": name,
                "md5": md5,
                "eintraege_pdf": len(toc),
                "artikel_pg": len(pg),
                "abweichungen": len(meldungen),
                "ausnahmen": len(ausnahmen_hier),
            }
        )
    if gesamt > MAX_GESAMT:
        verstoesse.append(f"gesamt {gesamt} Abweichungen (> {MAX_GESAMT})")
    if len(ausnahmen) > erwartete_dubletten:
        verstoesse.append(f"{len(ausnahmen)} Text-Dubletten-Ausnahmen (> erwartet {erwartete_dubletten})")
    verstoesse += abweichungen[:MAX_LISTE] if verstoesse else []
    return ergebnis(
        "inhaltsverzeichnis",
        verstoesse,
        ausgaben=len(eindeutig),
        abweichungen_gesamt=gesamt,
        ausnahmen_gesamt=len(ausnahmen),
        ausnahmen_erwartet=erwartete_dubletten,
        abweichungen=abweichungen,
        ausnahmen_text_dubletten=ausnahmen,
        je_ausgabe=je_ausgabe,
    )


def pruefe_autor(
    conn: psycopg.Connection, eindeutig: dict[str, Path], jobs: int, namen_streng: bool = False
) -> dict[str, Any]:
    """`Autor:in` (an beliebiger Stelle, „Autor:innen“ ausgenommen) ist ein Verstoß (#40).

    Autor:in-Namen im Fließtext (Bylines, Erwähnungen) sind für #40 nur ein Hinweis: sie maskiert der
    Personenschutz in #43; mit `--autor-namen-streng` zählen sie."""
    verstoesse: list[str] = []
    hinweise: list[str] = []
    n_text = conn.execute("select count(*) from uc2.abschnitt where text ~ %s", (AUTOR_SQL,)).fetchone()
    n_titel = conn.execute("select count(*) from uc2.artikel where titel ~ %s", (AUTOR_SQL,)).fetchone()
    assert n_text is not None and n_titel is not None
    if n_text[0]:
        verstoesse.append(f"{n_text[0]} Abschnitte mit „Autor:in“")
    if n_titel[0]:
        verstoesse.append(f"{n_titel[0]} Artikeltitel mit „Autor:in“")

    with ThreadPoolExecutor(max_workers=jobs) as pool:
        mengen = list(pool.map(autor_werte, eindeutig.values()))
    werte = set().union(*mengen) if mengen else set()
    je_erstwort: dict[str, list[str]] = defaultdict(list)
    for w in werte:
        je_erstwort[WORT_RE.findall(w)[0]].append(w)
    getroffen_werte: set[str] = set()
    getroffen_abschnitte: list[str] = []
    with conn.cursor(name="autor_scan") as cur:
        cur.execute("select abschnitt_id, text from uc2.abschnitt")
        for abschnitt_id, text in cur:
            t = " ".join(text.split())
            treffer = False
            for m in WORT_RE.finditer(t):
                for wert in je_erstwort.get(m.group(0), ()):
                    ende = m.start() + len(wert)
                    if t.startswith(wert, m.start()) and (ende == len(t) or not t[ende].isalnum()):
                        getroffen_werte.add(wert)
                        treffer = True
            if treffer:
                getroffen_abschnitte.append(abschnitt_id)
    if getroffen_abschnitte:
        meldung = (
            f"{len(getroffen_werte)} Autor:in-Werte in {len(getroffen_abschnitte)} Abschnitten "
            f"(Beispiel-IDs: {', '.join(getroffen_abschnitte[:10])})"
        )
        (verstoesse if namen_streng else hinweise).append(meldung)
    return ergebnis(
        "autorin",
        verstoesse,
        hinweise_fuer_43=hinweise,
        abschnitte_mit_autorzeile=n_text[0],
        titel_mit_autorzeile=n_titel[0],
        autor_werte_geprueft=len(werte),
        autor_werte_getroffen=len(getroffen_werte),
        abschnitte_mit_autorwert=len(getroffen_abschnitte),
    )


def pruefe_seitentext(
    conn: psycopg.Connection, eindeutig: dict[str, Path], jobs: int, erste_abschnitte: list[str]
) -> dict[str, Any]:
    """Je Artikel in PG: Auf PDF-Seite `pdf_seite` steht oben die Startzeile `<Medium> vom TT.MM.JJJJ`, und
    Abschnitt 1 beginnt wie der Seitentext nach dem Titel (`passt`). Unabhängig vom Inhaltsverzeichnis, aus
    dem titel und pdf_seite in PG stammen. Fehlt Abschnitt 1 (Abschnitts-Dublette), muss der Seitentext wie
    ein anderer Abschnitt 1 in PG beginnen. Jede Abweichung ist ein Verstoß, gelistet je Ausgabe."""
    rows = conn.execute(
        """select a.quelle_md5, a.pdf_seite, a.titel, s.nr, s.text
           from uc2.artikel a
           left join lateral (select nr, text from uc2.abschnitt where artikel_id = a.artikel_id
                              order by nr limit 1) s on true
           where a.quelle_md5 = any(%s) and s.nr is not null
           order by a.quelle_md5, a.pdf_seite, a.artikel_id""",
        (list(eindeutig),),
    ).fetchall()
    reste = lies_seitenreste([(eindeutig[r[0]], r[1]) for r in rows], jobs)
    je_ausgabe: dict[str, list[str]] = defaultdict(list)
    ohne_start = 0
    ueber_dublette = 0
    for md5, seite, titel, nr, text in rows:
        rest = reste[(eindeutig[md5], seite)]
        if rest is None:
            ohne_start += 1
            je_ausgabe[eindeutig[md5].name].append(f"S. {seite} keine Startzeile")
            continue
        t = vergleichsform(titel)
        if nr == 1:
            ok = passt(rest, vergleichsform(text), t)
        else:
            ok = any(passt(rest, a, t) for a in erste_abschnitte)
            ueber_dublette += int(ok)
        if not ok:
            je_ausgabe[eindeutig[md5].name].append(f"S. {seite} Abschnitt {nr} ≠ Seitentext")
    verstoesse = [f"{name}: {', '.join(m)}" for name, m in sorted(je_ausgabe.items())]
    return ergebnis(
        "seitentext",
        verstoesse[:MAX_LISTE],
        artikel_geprueft=len(rows),
        abweichungen_gesamt=sum(len(m) for m in je_ausgabe.values()),
        ausgaben_mit_abweichung=len(je_ausgabe),
        ohne_startzeile=ohne_start,
        abschnitt1_als_dublette_belegt=ueber_dublette,
    )


def pruefe_ohne_abschnitt(conn: psycopg.Connection, eindeutig: dict[str, Path]) -> dict[str, Any]:
    """Ein Artikel ohne Abschnitt (etwa nur eine Titelzeile, deren Text anderswo steht) ist ein Verstoß."""
    rows = conn.execute(
        """select a.artikel_id from uc2.artikel a
           where a.quelle_md5 = any(%s)
             and not exists (select 1 from uc2.abschnitt s where s.artikel_id = a.artikel_id)
           order by a.artikel_id""",
        (list(eindeutig),),
    ).fetchall()
    return ergebnis(
        "artikel_ohne_abschnitt",
        [f"Artikel {r[0]} ohne Abschnitt" for r in rows[:MAX_LISTE]],
        artikel_ohne_abschnitt=len(rows),
    )


def pruefe_dubletten(conn: psycopg.Connection) -> dict[str, Any]:
    rows = conn.execute(
        "select text_hash, count(*) from uc2.abschnitt group by text_hash having count(*) > 1"
    ).fetchall()
    return ergebnis(
        "dubletten",
        [f"text_hash {h[:12]} kommt {n}x vor" for h, n in rows[:MAX_LISTE]],
        doppelte_hashes=len(rows),
    )


def pruefe_vektoren(conn: psycopg.Connection) -> dict[str, Any]:
    row = conn.execute(
        """select count(*),
                  count(*) filter (where vektor is null),
                  count(*) filter (where dim is distinct from %s),
                  count(*) filter (where length(vektor) is distinct from %s),
                  count(*) filter (where modell is distinct from %s)
           from uc2.abschnitt""",
        (DIM, DIM * 4, MODELL),
    ).fetchone()
    assert row is not None
    gesamt, ohne, falsch_dim, falsch_len, falsch_modell = row
    verstoesse = []
    if gesamt == 0:
        verstoesse.append("uc2.abschnitt ist leer")
    for anzahl, text in (
        (ohne, "ohne vektor"),
        (falsch_dim, f"mit dim != {DIM}"),
        (falsch_len, f"mit length(vektor) != {DIM * 4}"),
        (falsch_modell, f"mit modell != {MODELL}"),
    ):
        if anzahl:
            verstoesse.append(f"{anzahl} Abschnitte {text}")
    return ergebnis("vektoren", verstoesse, abschnitte=gesamt)


# ------------------------------------------------------------------------------------------------ Main


def verbinden(db: str | None) -> psycopg.Connection:
    """Nachbau von `uc2.db.conninfo` (Import von uc2 ist hier verboten): `UC2_DATABASE_URL` gewinnt, sonst
    `PG*` mit `UC2_DB` bzw. `healthpolicy`; ein übergebenes `db` ersetzt nur den DB-Namen. `PGDATABASE` zählt
    bewusst nicht: es zeigt lokal auf die Verwaltungs-DB."""
    url = os.environ.get("UC2_DATABASE_URL")
    if url:
        return psycopg.connect(make_conninfo(url, dbname=db) if db else make_conninfo(url))
    return psycopg.connect(
        host=os.environ.get("PGHOST", "localhost"),
        port=int(os.environ.get("PGPORT", "5433")),
        user=os.environ.get("PGUSER", "statistik"),
        password=os.environ.get("PGPASSWORD", "statistik"),
        dbname=db or os.environ.get("UC2_DB", "healthpolicy"),
    )


def _positiv(wert: str) -> int:
    zahl = int(wert)
    if zahl < 0:
        raise argparse.ArgumentTypeError(f"muss ≥ 0 sein, nicht {zahl}")
    return zahl


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Unabhängige Prüfung des Belege-Index (#40)")
    ap.add_argument("--presse", required=True, type=Path, help="Ordner mit den Pressespiegel-PDFs")
    ap.add_argument("--ab", required=True, type=date.fromisoformat, help="frühestes Ausgabedatum JJJJ-MM-TT")
    ap.add_argument(
        "--db", default=None, help="DB-Name (Standard: aus UC2_DATABASE_URL, sonst UC2_DB oder healthpolicy)"
    )
    ap.add_argument("--json", action="store_true", help="maschinenlesbare Zusammenfassung")
    ap.add_argument(
        "--nur-diese-quellen",
        action="store_true",
        help="Prüfungen 1 und 2 nur für die gefundenen Dateien (Probelauf mit wenigen PDFs)",
    )
    ap.add_argument("--jobs", type=int, default=4, help="parallele pdftotext-Aufrufe")
    ap.add_argument(
        "--autor-namen-streng",
        action="store_true",
        help="Autor:in-Namen im Fließtext als Verstoß zählen (Personenschutz #43), sonst nur Hinweis",
    )
    ap.add_argument(
        "--max-je-ausgabe",
        type=_positiv,
        default=MAX_JE_AUSGABE,
        help=f"erlaubte Verzeichnis-Abweichungen je Ausgabe (Standard {MAX_JE_AUSGABE}, #40)",
    )
    ap.add_argument(
        "--erwartete-dubletten",
        type=_positiv,
        default=ERWARTETE_DUBLETTEN,
        help=f"erwartete belegte Text-Dubletten (Standard {ERWARTETE_DUBLETTEN}, Lauf v3); mehr = Verstoß",
    )
    args = ap.parse_args(argv)

    pdfs = finde_pdfs(args.presse, args.ab)
    if not pdfs:
        print("keine passenden PDFs gefunden", file=sys.stderr)
        return 2
    try:
        with verbinden(args.db) as conn:
            md5_erg, eindeutig = pruefe_md5(conn, pdfs, args.ab, args.nur_diese_quellen)
            erste = lade_erste_abschnitte(conn)
            ergebnisse = [
                md5_erg,
                pruefe_verzeichnisse(
                    conn, eindeutig, args.jobs, erste, args.max_je_ausgabe, args.erwartete_dubletten
                ),
                pruefe_seitentext(conn, eindeutig, args.jobs, erste),
                pruefe_ohne_abschnitt(conn, eindeutig),
                pruefe_autor(conn, eindeutig, args.jobs, args.autor_namen_streng),
                pruefe_dubletten(conn),
                pruefe_vektoren(conn),
            ]
    except (psycopg.Error, RuntimeError, OSError, subprocess.SubprocessError) as fehler:
        print(f"Betriebsfehler: {type(fehler).__name__}: {fehler}", file=sys.stderr)
        return 2

    ok = all(e["ok"] for e in ergebnisse)
    if args.json:
        print(json.dumps({"ok": ok, "pruefungen": ergebnisse}, ensure_ascii=False, indent=2))
    else:
        for e in ergebnisse:
            kopf = {k: v for k, v in e.items() if isinstance(v, int)}
            print(f"[{'OK' if e['ok'] else 'FEHLER'}] {e['pruefung']}  {kopf}")
            for v in e["verstoesse"]:
                print(f"    - {v}")
        for e in ergebnisse:
            if e["pruefung"] == "md5":
                for d in e["byte_gleiche_dubletten"]:
                    print(f"    Dublette (byte-gleich): {d['dateien']} in_pg={d['in_pg']}")
            if e["pruefung"] == "inhaltsverzeichnis":
                for a in e["abweichungen"][:MAX_LISTE]:
                    print(f"    Abweichung {a}")
                for a in e["ausnahmen_text_dubletten"][:MAX_LISTE]:
                    print(f"    Ausnahme {a}")
        print("ERGEBNIS:", "alle Prüfungen bestanden" if ok else "Verstöße")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
