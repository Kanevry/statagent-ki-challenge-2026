"""Stufe 1: Pressespiegel-PDFs → `quellen.jsonl`, `artikel.jsonl`, `abschnitte.jsonl`, `abweichungen.jsonl`.

Die JSONL-Dateien sind deterministisch (sortiert, ohne Zeitstempel): zwei Läufe über dieselben Dateien
ergeben byte-gleiche Ausgaben. Die Dauer steht nur in `zusammenfassung.json`.
"""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
import time
from collections.abc import Callable, Iterable
from concurrent.futures import ProcessPoolExecutor
from dataclasses import asdict
from datetime import date
from functools import partial
from pathlib import Path
from typing import Any

from uc2.belege.abschnitte import Tagger, lade_tagger, text_hash, zerlege_abschnitte
from uc2.belege.regeln import Regeln, lade_regeln
from uc2.belege.zerlegung import Ausgabe, zerlege_ausgabe

DATEINAME_RE = re.compile(r"^Pressespiegel vom (\d{2})\.(\d{2})\.(\d{4})\.pdf$")

Leser = Callable[[Path], str]


def pdftotext(pfad: Path) -> str:
    """Text einer PDF mit Seitentrennern (`\\f`), Layout erhalten."""
    ergebnis = subprocess.run(
        ["pdftotext", "-q", "-layout", str(pfad), "-"], capture_output=True, check=True, timeout=300
    )
    return ergebnis.stdout.decode("utf-8", errors="replace")


def md5_datei(pfad: Path) -> str:
    h = hashlib.md5()
    with pfad.open("rb") as datei:
        for block in iter(lambda: datei.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def ausgabedatum(pfad: Path) -> date | None:
    treffer = DATEINAME_RE.match(pfad.name)
    if not treffer:
        return None
    tag, monat, jahr = treffer.groups()
    return date(int(jahr), int(monat), int(tag))


def finde_pdfs(quelle: Path, ab: date | None, bis: date | None) -> list[tuple[Path, date]]:
    """PDFs mit Datum im Dateinamen im Zeitraum, sortiert nach Datum und relativem Pfad."""
    gefunden: list[tuple[Path, date]] = []
    for pfad in quelle.rglob("*.pdf"):
        datum = ausgabedatum(pfad)
        if datum is None or (ab and datum < ab) or (bis and datum > bis):
            continue
        gefunden.append((pfad, datum))
    return sorted(gefunden, key=lambda pd: (pd[1], pd[0].relative_to(quelle).as_posix()))


def _verarbeite(leser: Leser, pfad: Path) -> Ausgabe | str:
    try:
        return zerlege_ausgabe(leser(pfad))
    except (subprocess.SubprocessError, OSError, UnicodeError) as fehler:
        return f"lesefehler: {type(fehler).__name__}"


def _schreibe_jsonl(pfad: Path, zeilen: Iterable[dict[str, Any]]) -> int:
    n = 0
    with pfad.open("w", encoding="utf-8", newline="\n") as datei:
        for zeile in zeilen:
            datei.write(json.dumps(zeile, ensure_ascii=False) + "\n")
            n += 1
    return n


def extrahiere(
    quelle: Path,
    aus: Path,
    ab: date | None = None,
    bis: date | None = None,
    prozesse: int | None = None,
    leser: Leser = pdftotext,
    regeln: Regeln | None = None,
    tagger: Tagger | None = None,
) -> dict[str, Any]:
    """Extrahiert alle Ausgaben im Zeitraum nach `aus`; gibt die Zusammenfassung zurück."""
    beginn = time.monotonic()
    regeln = regeln or lade_regeln()
    tagger = tagger or lade_tagger()
    aus.mkdir(parents=True, exist_ok=True)

    dateien = finde_pdfs(quelle, ab, bis)
    quellen: list[dict[str, Any]] = []
    zu_lesen: list[tuple[dict[str, Any], Path]] = []
    erste_datei: dict[str, str] = {}
    for pfad, datum in dateien:
        rel = pfad.relative_to(quelle).as_posix()
        md5 = md5_datei(pfad)
        eintrag: dict[str, Any] = {
            "datei": rel,
            "md5": md5,
            "ausgabedatum": datum.isoformat(),
            "seiten": None,
            "uebersprungen": False,
            "grund": None,
        }
        if md5 in erste_datei:
            eintrag["uebersprungen"] = True
            eintrag["grund"] = f"dublette von {erste_datei[md5]}"
        else:
            erste_datei[md5] = rel
            zu_lesen.append((eintrag, pfad))
        quellen.append(eintrag)

    pfade_liste = [pfad for _, pfad in zu_lesen]
    arbeit = partial(_verarbeite, leser)
    if prozesse == 1 or len(pfade_liste) <= 1:
        ergebnisse = [arbeit(p) for p in pfade_liste]
    else:
        with ProcessPoolExecutor(max_workers=prozesse) as pool:
            ergebnisse = list(pool.map(arbeit, pfade_liste))

    artikel_zeilen: list[dict[str, Any]] = []
    abschnitt_zeilen: list[dict[str, Any]] = []
    abweichungen: list[dict[str, Any]] = []
    je_ausgabe: list[dict[str, Any]] = []
    artikel_hashes: dict[str, str] = {}
    abschnitt_hashes: dict[str, str] = {}

    for eintrag in quellen:
        if eintrag["uebersprungen"]:
            abweichungen.append(
                {
                    "quelle_md5": eintrag["md5"],
                    "datei": eintrag["datei"],
                    "art": "datei_dublette",
                    "detail": eintrag["grund"],
                }
            )

    for (eintrag, _), ergebnis in zip(zu_lesen, ergebnisse, strict=True):
        md5 = eintrag["md5"]
        kopf = {"quelle_md5": md5, "datei": eintrag["datei"]}
        if isinstance(ergebnis, str):
            eintrag["uebersprungen"] = True
            eintrag["grund"] = ergebnis
            abweichungen.append({**kopf, "art": "lesefehler", "detail": ergebnis})
            continue
        eintrag["seiten"] = ergebnis.seiten
        abweichungen.extend({**kopf, **a} for a in ergebnis.abweichungen)
        zahl_artikel = 0
        zahl_abschnitte = 0
        for artikel in ergebnis.artikel:
            artikel_id = f"{md5[:12]}-{artikel.nr:03d}"
            # Beiträge nur mit Titel sind erst bei gleichem Titel, Medium und Datum dieselbe Sendung.
            schluessel = artikel.text
            if artikel.nur_titel:
                schluessel = f"nur_titel|{artikel.titel}|{artikel.medium}|{artikel.artikeldatum}"
            gesamt_hash = text_hash(schluessel)
            if gesamt_hash in artikel_hashes:
                abweichungen.append(
                    {
                        **kopf,
                        "art": "artikel_dublette",
                        "artikel_nr": artikel.nr,
                        "detail": f"wie {artikel_hashes[gesamt_hash]}",
                    }
                )
                continue
            artikel_hashes[gesamt_hash] = artikel_id
            zeile = {"artikel_id": artikel_id, "quelle_md5": md5, **asdict(artikel)}
            del zeile["nr"], zeile["nur_titel"]
            artikel_zeilen.append(zeile)
            zahl_artikel += 1
            texte = zerlege_abschnitte(artikel.text, regeln.max_zeichen, regeln.ueberlappung)
            for n, abschnitt in enumerate(texte, start=1):
                abschnitt_id = f"{artikel_id}-{n:02d}"
                h = text_hash(abschnitt)
                if h in abschnitt_hashes:
                    abweichungen.append(
                        {
                            **kopf,
                            "art": "abschnitt_dublette",
                            "artikel_nr": artikel.nr,
                            "detail": f"{abschnitt_id} wie {abschnitt_hashes[h]}",
                        }
                    )
                    continue
                abschnitt_hashes[h] = abschnitt_id
                abschnitt_zeilen.append(
                    {
                        "abschnitt_id": abschnitt_id,
                        "artikel_id": artikel_id,
                        "nr": n,
                        "text": abschnitt,
                        "text_hash": h,
                        "institutionen": tagger.tags(abschnitt),
                    }
                )
                zahl_abschnitte += 1
        je_ausgabe.append(
            {
                "datei": eintrag["datei"],
                "ausgabedatum": eintrag["ausgabedatum"],
                "seiten": ergebnis.seiten,
                "inhaltsverzeichnis": len(ergebnis.eintraege),
                "artikel": zahl_artikel,
                "abschnitte": zahl_abschnitte,
                "abweichungen": len(ergebnis.abweichungen),
            }
        )

    _schreibe_jsonl(aus / "quellen.jsonl", quellen)
    _schreibe_jsonl(aus / "artikel.jsonl", artikel_zeilen)
    _schreibe_jsonl(aus / "abschnitte.jsonl", abschnitt_zeilen)
    _schreibe_jsonl(aus / "abweichungen.jsonl", abweichungen)
    zusammenfassung: dict[str, Any] = {
        "je_ausgabe": je_ausgabe,
        "summe": {
            "dateien": len(quellen),
            "uebersprungen": sum(1 for q in quellen if q["uebersprungen"]),
            "inhaltsverzeichnis": sum(a["inhaltsverzeichnis"] for a in je_ausgabe),
            "artikel": len(artikel_zeilen),
            "abschnitte": len(abschnitt_zeilen),
            "abweichungen": len(abweichungen),
        },
        "dauer_s": round(time.monotonic() - beginn, 3),
    }
    (aus / "zusammenfassung.json").write_text(
        json.dumps(zusammenfassung, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return zusammenfassung


def lies_jsonl(pfad: Path) -> list[dict[str, Any]]:
    with pfad.open(encoding="utf-8") as datei:
        return [json.loads(zeile) for zeile in datei if zeile.strip()]
