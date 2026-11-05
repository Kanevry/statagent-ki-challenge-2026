"""Korpus-Ingest `lotse ingest` (#29): SozDok-XML, PDFs (Formulare, Kataloge) und EKO in die DB lotse.

Ablauf: alle Quellen lesen, in einer Transaktion die betroffenen Zeilen von lotse.ingest_fehler,
lotse.abschnitt und lotse.dokument leeren und per COPY neu laden. lotse.vektor bleibt unberührt, weil
die Vektoren am Text-Hash hängen. Am Ende stehen Zählungen je Quelle und ein globaler Inhalts-Hash, der
nur von den Daten abhängt (keine Zeitstempel, feste Sortierung).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import shutil
import subprocess
import sys
import time
import unicodedata
import xml.etree.ElementTree as ET
from collections.abc import Iterable, Iterator
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Literal

import psycopg

from uc1.config import KonfigFehler, daten_dir
from uc1.db import verbinde

# Dateien bis zu dieser Größe ergeben einen Abschnitt; größere werden nach <absatz> geteilt.
TEILUNGSGRENZE_BYTES = 8192

RECHTSTEXTE = "Rechtstexte"
PDF_ORDNER: tuple[tuple[str, Literal["formular", "katalog"]], ...] = (
    ("Anträge und Formulare", "formular"),
    ("Leistungskataloge", "katalog"),
)
# Befunde/ ist bewusst nicht dabei: das sind Upload-Demos für #33.
EKO_ORDNER = "Medikamenten Erstattungskodex"
# v1 statt *_v2.txt: v2 enthält HTML-Entities.
EKO_DATEIEN = ("regeltext.txt", "indtext.txt")

Teil = Literal["sozdok", "pdf", "eko"]
TEIL_QUELLEN: dict[Teil, tuple[str, ...]] = {
    "sozdok": ("sozdok",),
    "pdf": ("formular", "katalog"),
    "eko": ("eko",),
}

# Elemente, die nicht indiziert werden (Inhaltsverzeichnis, Änderungsprotokoll, Layout, Bilder).
NICHT_INDIZIEREN = frozenset({"inhaltsvz", "aendprot", "layoutdaten", "binary", "src"})
# Leere Symbol-Elemente in SozDok und ihr Text. gdash ist der geschützte Bindestrich (e-card),
# bdash der bedingte Trennstrich (Kranken|anstalten), der im Fließtext entfällt.
SYMBOLE: dict[str, str] = {
    "nbsp": " ",
    "gdash": "-",
    "bdash": "",
    "amp": "&",
    "lt": "<",
    "gt": ">",
    "br": " ",
    "tab": " ",
    "abstand": " ",
    "en": " ",
    "aw": " ",
}
# Zeichenauszeichnung ohne Wortgrenze; alle anderen Elemente trennen ihren Text durch Leerraum.
INLINE = frozenset(
    {
        "b",
        "i",
        "u",
        "rvolink",
        "nolink",
        "wwwlink",
        "entlink",
        "aenlink",
        "matlink",
        "super",
        "sub",
        "gldsym",
        "fnzeichen",
        "n",
        "feld",
        "gs",
    }
)
# In lotse.dokument eigene Spalten; alle übrigen Attribute von <metadaten> gehen nach meta.
EIGENE_SPALTEN = frozenset({"gldart", "gldnr", "abkrvo", "titrvo", "ikra", "berkz"})

_LEERRAUM = re.compile(r"\s+")
_UNSICHTBAR = str.maketrans({"­": None, "​": None, "﻿": None})
_EKO_ZEILE = re.compile(r"^\|([^|]*)\|;\|(.*)\|$")


def normalisiere(text: str) -> str:
    """NFC, unsichtbare Zeichen raus, jeder Leerraum (auch NBSP, schmale Leerzeichen) zu einem Blank.

    Zitate werden als Teilstring gegen abschnitt.text geprüft; dieselbe Funktion muss deshalb auch auf
    das Zitat angewandt werden.
    """
    text = unicodedata.normalize("NFC", text).translate(_UNSICHTBAR)
    return _LEERRAUM.sub(" ", text).strip()


def sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class Abschnitt:
    nr: int
    kontext: str
    text: str
    seite: int | None = None
    zeile: int | None = None

    @property
    def text_hash(self) -> str:
        return sha256(self.kontext + "\n" + self.text)


@dataclass
class Dokument:
    quelle: str
    dokid: str
    datei: str
    titel: str | None
    gesetz: str | None = None
    art: str | None = None
    nummer: str | None = None
    inkrafttreten: date | None = None
    berkz: str | None = None
    meta: dict[str, object] = field(default_factory=dict)
    abschnitte: list[Abschnitt] = field(default_factory=list)
    # Verweise (rvolink abkrvo) auf andere Gesetze; nur für die Autorität, nicht gespeichert.
    verweise: dict[str, int] = field(default_factory=dict)

    @property
    def inhalt_hash(self) -> str:
        return sha256("\x1e".join(sorted(a.text for a in self.abschnitte)))


@dataclass(frozen=True)
class Fehler:
    datei: str
    grund: str


# --------------------------------------------------------------------------- SozDok-XML


def _sammle_text(element: ET.Element, teile: list[str]) -> None:
    symbol = SYMBOLE.get(element.tag)
    if symbol is not None:
        teile.append(symbol)
    block = symbol is None and element.tag not in INLINE
    if block:
        teile.append(" ")
    if element.text:
        teile.append(element.text)
    for kind in element:
        if kind.tag not in NICHT_INDIZIEREN:
            _sammle_text(kind, teile)
        if kind.tail:
            teile.append(kind.tail)
    if block:
        teile.append(" ")


def element_text(element: ET.Element) -> str:
    teile: list[str] = []
    _sammle_text(element, teile)
    return normalisiere("".join(teile))


def _hat_gliederung(element: ET.Element) -> bool:
    return any(e.tag in {"absatz", "ueberschrift"} for e in element.iter() if e is not element)


def bloecke(container: ET.Element) -> Iterator[tuple[str, str]]:
    """(typ, text) in XML-Reihenfolge; typ ist absatz, ueberschrift oder anhang (Liste, Tabelle, …)."""
    if container.text and container.text.strip():
        yield "anhang", normalisiere(container.text)
    for kind in container:
        if kind.tag not in NICHT_INDIZIEREN:
            if kind.tag in {"absatz", "ueberschrift"}:
                yield kind.tag, element_text(kind)
            elif kind.tag not in SYMBOLE and _hat_gliederung(kind):
                yield from bloecke(kind)  # Container wie <abschnitt>
            else:
                yield "anhang", element_text(kind)
        if kind.tail and kind.tail.strip():
            yield "anhang", normalisiere(kind.tail)


def _zeichen(art: str | None) -> str | None:
    if art is None:
        return None
    return {"PARA": "§", "ART": "Art."}.get(art.upper(), art)


def kontext_basis(gesetz: str | None, art: str | None, nummer: str | None) -> str:
    teile = [gesetz or ""]
    if nummer:
        teile += [_zeichen(art) or "", nummer]
    return normalisiere(" ".join(teile))


def teile_abschnitte(bloeke: list[tuple[str, str]], basis: str, ganz: bool) -> list[Abschnitt]:
    """ganz=True: ein Abschnitt mit allem. Sonst ein Abschnitt je <absatz>; Listen und Tabellen hängen am
    vorangehenden Absatz, Überschriften leiten den nächsten Abschnitt ein und gehen in dessen Kontext."""
    bloeke = [(typ, text) for typ, text in bloeke if text]
    erste_ueb = next((text for typ, text in bloeke if typ == "ueberschrift"), "")
    if ganz:
        text = normalisiere(" ".join(text for _, text in bloeke))
        return [Abschnitt(0, normalisiere(f"{basis} {erste_ueb}"), text)] if text else []

    gruppen: list[tuple[str, list[str]]] = []
    aktuell: list[str] | None = None
    offen: list[str] = []  # Überschriften, die auf ihren Absatz warten
    ueb = erste_ueb
    for typ, text in bloeke:
        if typ == "ueberschrift":
            aktuell = None
            offen.append(text)
            ueb = text
        elif typ == "absatz" or aktuell is None:
            aktuell = [*offen, text]
            offen = []
            gruppen.append((ueb, aktuell))
        else:
            aktuell.append(text)
    if offen:  # Überschriften am Ende ohne Absatz
        if gruppen:
            gruppen[-1][1].extend(offen)
        else:
            gruppen.append((ueb, offen))
    return [
        Abschnitt(nr, normalisiere(f"{basis} {u}"), normalisiere(" ".join(t)))
        for nr, (u, t) in enumerate(gruppen)
    ]


# Aufgehobene Paragraphen (Review D1b). SozDok kennzeichnet sie in der ersten Überschrift
# („aufgehoben - Pflegegeld“, „12. Aufgehoben.“) oder, ohne Kennzeichen in der Überschrift, mit einem
# Stummel als ganzem Text („§ 206. Aufgehoben.“, „Artikel 11 Aufgehoben. (2.ZV, BGBl. …)“,
# „(Anm.: aufgehoben durch BGBl. I Nr. 120/2012)“). Beide Muster sind am Anfang verankert, damit gültige
# §§ mit „aufgehoben“ im Fließtext („… tritt außer Kraft und wird aufgehoben“) nicht markiert werden.
_AUFGEHOBEN_KOPF = re.compile(r"^(?:[\w.]+\.\s*)?aufgehoben\b", re.IGNORECASE)
_AUFGEHOBEN_STUMMEL = re.compile(
    r"^(?:(?:§|Art\.|Artikel)\s*\w+\.?\s*)*\(?(?:Anm\.:\s*)?aufgehoben\b", re.IGNORECASE
)
# Länger als ein Stummel ist ein Text, der neben „aufgehoben“ noch Inhalt trägt (etwa Abs. 1 aufgehoben,
# Abs. 2 gilt); der zählt nicht als aufgehoben.
STUMMEL_ZEICHEN = 300


def ist_aufgehoben(bloeke: list[tuple[str, str]]) -> bool:
    """Ist das Dokument ein aufgehobener Paragraph? Erste Überschrift beginnt mit „aufgehoben“, oder der
    Text ohne Überschriften ist ein kurzer Stummel, der mit „(§ n.) aufgehoben“ beginnt."""
    ueberschriften = [text for typ, text in bloeke if typ == "ueberschrift" and text]
    if ueberschriften and _AUFGEHOBEN_KOPF.match(ueberschriften[0]):
        return True
    rumpf = normalisiere(" ".join(text for typ, text in bloeke if typ != "ueberschrift" and text))
    return bool(rumpf) and len(rumpf) <= STUMMEL_ZEICHEN and _AUFGEHOBEN_STUMMEL.match(rumpf) is not None


def _datum(wert: str | None) -> date | None:
    if not wert:
        return None
    try:
        return date.fromisoformat(wert.strip())
    except ValueError:
        return None


def _leer_zu_none(wert: str | None) -> str | None:
    if wert is None:
        return None
    wert = wert.strip()
    return wert or None


def lies_sozdok(pfad: Path, wurzel: Path) -> Dokument | Fehler:
    datei = pfad.relative_to(wurzel).as_posix()
    try:
        groesse = pfad.stat().st_size
        root = ET.parse(pfad).getroot()
    except (ET.ParseError, OSError) as fehler:
        return Fehler(datei, f"XML nicht lesbar: {fehler}")
    dokid = _leer_zu_none(root.get("dokid"))
    if dokid is None:
        return Fehler(datei, "Attribut dokid fehlt am Wurzelelement")
    meta_el = root.find(".//metadaten")
    if meta_el is None:
        return Fehler(datei, "Element metadaten fehlt")
    attr = {k: v for k, v in meta_el.attrib.items()}
    gesetz = _leer_zu_none(attr.get("abkrvo"))
    art = _leer_zu_none(attr.get("gldart"))
    nummer = _leer_zu_none(attr.get("gldnr"))
    meta: dict[str, object] = {k: attr[k] for k in sorted(attr) if k not in EIGENE_SPALTEN}
    if attr.get("ikra") and _datum(attr.get("ikra")) is None:
        meta["ikra_roh"] = attr["ikra"]
    blk: list[tuple[str, str]] = []
    for nutz in root.iter("nutzdaten"):
        blk.extend(bloecke(nutz))
    abschnitte = teile_abschnitte(blk, kontext_basis(gesetz, art, nummer), groesse <= TEILUNGSGRENZE_BYTES)
    verweise: dict[str, int] = {}
    for link in root.iter("rvolink"):
        ziel = normalisiere(link.get("abkrvo") or "")
        if ziel and ziel != gesetz:
            verweise[ziel] = verweise.get(ziel, 0) + 1
    # Größe des ganzen Dokuments: die Suche wertet sehr große Sammeldokumente darüber ab.
    meta["zeichen"] = sum(len(a.text) for a in abschnitte)
    meta["bytes"] = groesse
    # Nur gesetzt, wenn wahr; die Suche liest coalesce(meta->>'aufgehoben', false). Der Inhalts-Hash
    # (dokid, nr, text_hash) enthält meta nicht und bleibt deshalb gleich.
    if ist_aufgehoben(blk):
        meta["aufgehoben"] = True
    return Dokument(
        quelle="sozdok",
        dokid=dokid,
        datei=datei,
        titel=_leer_zu_none(attr.get("titrvo")),
        gesetz=gesetz,
        art=art,
        nummer=nummer,
        inkrafttreten=_datum(attr.get("ikra")),
        berkz=_leer_zu_none(attr.get("berkz")),
        meta=meta,
        abschnitte=abschnitte,
        verweise=verweise,
    )


def setze_autoritaet(daten: list[Dokument | Fehler]) -> None:
    """meta.zitiert = Verweise anderer Gesetze auf das Gesetz des Dokuments; meta.autoritaet =
    ln(1 + zitiert) / ln(1 + max), also 0..1. Die Suche nutzt das als milden Vorrang für Normen,
    auf die sich der Korpus stützt (ASVG, BPGG), vor Weisungen, Abkommen und Statistikvorschriften."""
    doks = [d for d in daten if isinstance(d, Dokument) and d.quelle == "sozdok"]
    zitiert: dict[str, int] = {}
    for d in doks:
        for ziel, n in d.verweise.items():
            zitiert[ziel] = zitiert.get(ziel, 0) + n
    hoechst = math.log1p(max(zitiert.values(), default=0))
    for d in doks:
        z = zitiert.get(d.gesetz or "", 0)
        d.meta["zitiert"] = z
        d.meta["autoritaet"] = round(math.log1p(z) / hoechst, 6) if hoechst else 0.0


def _lies_sozdok_arg(arg: tuple[str, str]) -> Dokument | Fehler:
    return lies_sozdok(Path(arg[0]), Path(arg[1]))


def lies_alle_sozdok(wurzel: Path, limit: int | None) -> list[Dokument | Fehler]:
    dateien = sorted((wurzel / RECHTSTEXTE).glob("*.xml"))[:limit]
    args = [(str(p), str(wurzel)) for p in dateien]
    with ProcessPoolExecutor(max_workers=min(8, os.cpu_count() or 1)) as pool:
        daten = list(pool.map(_lies_sozdok_arg, args, chunksize=64))
    setze_autoritaet(daten)
    return daten


# --------------------------------------------------------------------------- PDF


def _pdftotext() -> str:
    return shutil.which("pdftotext") or "/opt/homebrew/bin/pdftotext"


def _seitenzahl(pfad: Path) -> int:
    from pypdf import PdfReader

    return len(PdfReader(pfad).pages)


def pdf_seiten(pfad: Path) -> list[str]:
    """Text je Seite wie `pdftotext -layout -f N -l N`. Ein Aufruf für das ganze Dokument, geteilt am
    Seitenvorschub; stimmt die Seitenzahl nicht, wird Seite für Seite gelesen."""
    n = _seitenzahl(pfad)
    roh = subprocess.run(
        [_pdftotext(), "-layout", "-enc", "UTF-8", str(pfad), "-"],
        check=True,
        capture_output=True,
        timeout=300,
    ).stdout.decode("utf-8", errors="replace")
    seiten = roh.split("\f")
    if seiten and not seiten[-1].strip():
        seiten = seiten[:-1]
    if len(seiten) == n:
        return seiten
    return [
        subprocess.run(
            [_pdftotext(), "-layout", "-enc", "UTF-8", "-f", str(s), "-l", str(s), str(pfad), "-"],
            check=True,
            capture_output=True,
            timeout=120,
        ).stdout.decode("utf-8", errors="replace")
        for s in range(1, n + 1)
    ]


def lies_pdf(pfad: Path, wurzel: Path, quelle: str) -> Dokument | Fehler:
    datei = pfad.relative_to(wurzel).as_posix()
    try:
        seiten = pdf_seiten(pfad)
    except Exception as fehler:  # pypdf und pdftotext werfen viele Typen
        return Fehler(datei, f"PDF nicht lesbar: {type(fehler).__name__}: {fehler}")
    name = unicodedata.normalize("NFC", pfad.stem)
    abschnitte: list[Abschnitt] = []
    for seite, roh in enumerate(seiten, start=1):
        text = normalisiere(roh)
        if text:  # leere Seiten (Scans ohne Textebene, Leerseiten) ergeben keinen Abschnitt
            abschnitte.append(Abschnitt(len(abschnitte), f"{name} S. {seite}", text, seite=seite))
    return Dokument(
        quelle=quelle,
        dokid=datei,
        datei=datei,
        titel=name,
        meta={"seiten": len(seiten), "leere_seiten": len(seiten) - len(abschnitte)},
        abschnitte=abschnitte,
    )


def lies_alle_pdf(wurzel: Path, limit: int | None) -> list[Dokument | Fehler]:
    ergebnis: list[Dokument | Fehler] = []
    for ordner, quelle in PDF_ORDNER:
        for pfad in sorted((wurzel / ordner).glob("*.pdf"))[:limit]:
            ergebnis.append(lies_pdf(pfad, wurzel, quelle))
    return ergebnis


# --------------------------------------------------------------------------- EKO


def lies_eko(pfad: Path, wurzel: Path, limit: int | None = None) -> Dokument | Fehler:
    """Ein Abschnitt je Zeile (zeile ab 1). Latin-1. Leerzeilen ergäben leere Abschnitte und werden
    übersprungen; die Zeilennummer bleibt die der Datei. In regeltext.txt und indtext.txt gibt es keine."""
    datei = pfad.relative_to(wurzel).as_posix()
    try:
        zeilen = pfad.read_bytes().decode("latin-1").splitlines()
    except OSError as fehler:
        return Fehler(datei, f"Datei nicht lesbar: {fehler}")
    abschnitte: list[Abschnitt] = []
    leer = 0
    for nr_zeile, zeile in enumerate(zeilen[:limit], start=1):
        treffer = _EKO_ZEILE.match(zeile.strip())
        code, text = (treffer.group(1).strip(), treffer.group(2)) if treffer else ("", zeile)
        text = normalisiere(text)
        if not text:
            leer += 1
            continue
        kontext = f"EKO {pfad.stem} Zeile {nr_zeile}" + (f" Pharmanummer {code}" if code else "")
        abschnitte.append(Abschnitt(len(abschnitte), kontext, text, zeile=nr_zeile))
    return Dokument(
        quelle="eko",
        dokid=datei,
        datei=datei,
        titel=pfad.name,
        meta={"zeilen": len(zeilen), "leerzeilen": leer, "kodierung": "latin-1"},
        abschnitte=abschnitte,
    )


def lies_alle_eko(wurzel: Path, limit: int | None) -> list[Dokument | Fehler]:
    return [lies_eko(wurzel / EKO_ORDNER / name, wurzel, limit) for name in EKO_DATEIEN]


# --------------------------------------------------------------------------- Laden


def _dokument_zeilen(doks: Iterable[Dokument]) -> Iterator[tuple[object, ...]]:
    for d in doks:
        yield (
            d.quelle,
            d.dokid,
            d.datei,
            d.titel,
            d.gesetz,
            d.art,
            d.nummer,
            d.inkrafttreten,
            d.berkz,
            json.dumps(d.meta, ensure_ascii=False, sort_keys=True),
            d.inhalt_hash,
        )


def lade(conn: psycopg.Connection, teile: tuple[Teil, ...], daten: list[Dokument | Fehler]) -> None:
    """Leert die Zeilen der gewählten Teile und lädt neu, alles in einer Transaktion."""
    doks = [d for d in daten if isinstance(d, Dokument)]
    fehler = [f for f in daten if isinstance(f, Fehler)]
    quellen = [q for t in teile for q in TEIL_QUELLEN[t]]
    with conn.transaction(), conn.cursor() as cur:
        if set(teile) == set(TEIL_QUELLEN):
            cur.execute("TRUNCATE lotse.ingest_fehler, lotse.abschnitt, lotse.dokument RESTART IDENTITY")
        else:
            # Fehlerzeilen tragen keine Quelle; zuordnen über den Ordner der Datei.
            ordner = [RECHTSTEXTE] if "sozdok" in teile else []
            ordner += [o for o, _ in PDF_ORDNER] if "pdf" in teile else []
            ordner += [EKO_ORDNER] if "eko" in teile else []
            cur.execute(
                "DELETE FROM lotse.ingest_fehler WHERE split_part(datei, '/', 1) = ANY(%s)", (ordner,)
            )
            cur.execute("DELETE FROM lotse.dokument WHERE quelle = ANY(%s)", (quellen,))  # CASCADE
        with cur.copy(
            "COPY lotse.dokument (quelle, dokid, datei, titel, gesetz, art, nummer, inkrafttreten,"
            " berkz, meta, inhalt_hash) FROM STDIN"
        ) as copy:
            for zeile in _dokument_zeilen(doks):
                copy.write_row(zeile)
        cur.execute("SELECT dokid, id FROM lotse.dokument WHERE quelle = ANY(%s)", (quellen,))
        ids: dict[str, int] = dict(cur.fetchall())
        with cur.copy(
            "COPY lotse.abschnitt (dokument_id, nr, seite, zeile, kontext, text, text_hash) FROM STDIN"
        ) as copy:
            for d in doks:
                for a in d.abschnitte:
                    copy.write_row((ids[d.dokid], a.nr, a.seite, a.zeile, a.kontext, a.text, a.text_hash))
        with cur.copy("COPY lotse.ingest_fehler (datei, grund) FROM STDIN") as copy:
            for f in fehler:
                copy.write_row((f.datei, f.grund))


def inhalts_hash(zeilen: Iterable[tuple[str, int, str]]) -> str:
    """sha256 über die sortierten Zeilen `dokid \t nr \t text_hash`. Sortiert wird in Python nach
    Codepunkten, damit weder Ladereihenfolge noch DB-Kollation den Hash beeinflussen."""
    h = hashlib.sha256()
    for dokid, nr, text_hash in sorted(zeilen):
        h.update(f"{dokid}\t{nr}\t{text_hash}\n".encode())
    return h.hexdigest()


def zaehle(conn: psycopg.Connection) -> dict[str, object]:
    """Zählungen je Quelle und globaler Inhalts-Hash aus der DB (nicht aus dem Speicher)."""
    je_quelle: dict[str, dict[str, int]] = {}
    for quelle, doks, abschnitte, ohne in conn.execute(
        "SELECT d.quelle, count(DISTINCT d.id), count(a.id),"
        " count(DISTINCT d.id) FILTER (WHERE NOT EXISTS"
        "  (SELECT 1 FROM lotse.abschnitt x WHERE x.dokument_id = d.id))"
        " FROM lotse.dokument d LEFT JOIN lotse.abschnitt a ON a.dokument_id = d.id"
        " GROUP BY d.quelle ORDER BY d.quelle"
    ).fetchall():
        je_quelle[quelle] = {"dokumente": doks, "abschnitte": abschnitte, "ohne_abschnitt": ohne}
    fehler = conn.execute("SELECT count(*) FROM lotse.ingest_fehler").fetchone()
    aufgehoben = conn.execute(
        "SELECT count(*) FROM lotse.dokument WHERE coalesce((meta->>'aufgehoben')::boolean, false)"
    ).fetchone()
    zeilen = conn.execute(
        "SELECT d.dokid, a.nr, a.text_hash"
        " FROM lotse.abschnitt a JOIN lotse.dokument d ON d.id = a.dokument_id"
    ).fetchall()
    return {
        "quellen": je_quelle,
        "ingest_fehler": int(fehler[0]) if fehler else 0,
        "aufgehoben": int(aufgehoben[0]) if aufgehoben else 0,
        "abschnitte_gesamt": len(zeilen),
        "inhalt_hash": inhalts_hash(zeilen),
    }


def lies(wurzel: Path, teile: tuple[Teil, ...], limit: int | None) -> list[Dokument | Fehler]:
    daten: list[Dokument | Fehler] = []
    if "sozdok" in teile:
        daten += lies_alle_sozdok(wurzel, limit)
    if "pdf" in teile:
        daten += lies_alle_pdf(wurzel, limit)
    if "eko" in teile:
        daten += lies_alle_eko(wurzel, limit)
    return daten


def cli(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="lotse ingest", description="Korpus svbox/uc1 einlesen (#29)")
    parser.add_argument("--nur", choices=list(TEIL_QUELLEN), help="nur diesen Teil neu laden")
    parser.add_argument("--limit", type=int, help="höchstens N Dateien (EKO: Zeilen) je Ordner (Entwicklung)")
    parser.add_argument("--json", action="store_true", help="Zählungen und Hash als JSON")
    parser.add_argument("--url", help="Verbindungs-URL (Standard: LOTSE_DATABASE_URL)")
    args = parser.parse_args(argv)
    try:
        wurzel = daten_dir()
    except KonfigFehler as fehler:
        print(f"lotse ingest: {fehler}", file=sys.stderr)
        return 2
    teile: tuple[Teil, ...] = (args.nur,) if args.nur else tuple(TEIL_QUELLEN)
    start = time.monotonic()
    daten = lies(wurzel, teile, args.limit)
    if not any(isinstance(d, Dokument) for d in daten):
        print(f"lotse ingest: keine Dokumente unter {wurzel} gefunden", file=sys.stderr)
        return 1
    with verbinde(args.url) as conn:
        lade(conn, teile, daten)
        ergebnis = zaehle(conn)
    ergebnis["dauer_s"] = round(time.monotonic() - start, 1)
    if args.json:
        print(json.dumps(ergebnis, ensure_ascii=False, indent=2, sort_keys=True))
        return 0
    quellen = ergebnis["quellen"]
    assert isinstance(quellen, dict)
    for quelle, z in quellen.items():
        print(
            f"{quelle:9} {z['dokumente']:6} Dokumente {z['abschnitte']:7} Abschnitte"
            f" ({z['ohne_abschnitt']} ohne Text)"
        )
    print(f"ingest_fehler {ergebnis['ingest_fehler']}")
    print(f"aufgehoben {ergebnis['aufgehoben']} Dokumente (meta.aufgehoben)")
    print(f"inhalt_hash {ergebnis['inhalt_hash']}")
    print(f"dauer {ergebnis['dauer_s']} s")
    return 0
