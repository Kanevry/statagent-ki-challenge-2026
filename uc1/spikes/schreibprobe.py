"""Spike 2 (#28): Schreibprobe für das Vorausfüllen der Antragsformulare mit pypdf.

Füllt in einer Kopie unter /tmp/b-uc1-spikes/ je Formular 2 Textfelder und 1 Checkbox mit erfundenen
Demo-Werten, setzt NeedAppearances und prüft mit zwei Lesern: pypdf get_fields() und pdftotext -layout.
Prüft außerdem, ob ein unbekannter Feldname still ignoriert wird.

Aufruf aus uc1/:  UC1_DATA_DIR=… uv run python spikes/schreibprobe.py
"""

from __future__ import annotations

import io
import json
import logging
import os
import subprocess
import sys
import warnings
from pathlib import Path
from typing import Any

from pypdf import PdfReader, PdfWriter

sys.path.insert(0, str(Path(__file__).resolve().parent))
from formularfelder import FORMULAR_ORDNER, FORMULARE, ZIEL

TMP = Path("/tmp/b-uc1-spikes")
DEMO_TEXTE = ["Erika Musterfrau", "01.01.1950"]
UNBEKANNT = "Gibt_es_nicht_4711"


def _waehle_felder(meta: dict[str, Any]) -> tuple[list[str], tuple[str, str], tuple[str, str] | None]:
    """2 Textfelder und 1 Checkbox mit je einem Widget, dazu (falls da) eine Knopfgruppe mit >1 Widget."""
    felder = meta["felder"]
    texte = [f["name"] for f in felder if f["typ"] == "/Tx" and f["widgets"] == 1][:2]
    box = next(f for f in felder if f["typ"] == "/Btn" and f["widgets"] == 1 and f["export_werte"])
    gruppe = next(
        (f for f in felder if f["typ"] == "/Btn" and f["widgets"] > 1 and len(f["export_werte"]) > 1),
        None,
    )
    return (
        texte,
        (box["name"], box["export_werte"][0]),
        (gruppe["name"], gruppe["export_werte"][1]) if gruppe else None,
    )


def _fuellen(quelle: Path, ziel: Path, werte: dict[str, str]) -> list[str]:
    """Füllen und alles mitschneiden, was pypdf dabei meldet (Warnungen, Log)."""
    log = io.StringIO()
    handler = logging.StreamHandler(log)
    logging.getLogger("pypdf").addHandler(handler)
    meldungen: list[str] = []
    try:
        with warnings.catch_warnings(record=True) as gefangen:
            warnings.simplefilter("always")
            schreiber = PdfWriter(clone_from=quelle)
            schreiber.update_page_form_field_values(None, werte, auto_regenerate=True)
            schreiber.set_need_appearances_writer(True)
            with ziel.open("wb") as aus:
                schreiber.write(aus)
        meldungen += [str(w.message) for w in gefangen]
    finally:
        logging.getLogger("pypdf").removeHandler(handler)
    meldungen += [z for z in log.getvalue().splitlines() if z]
    return meldungen


def _pdftotext(pfad: Path) -> str:
    return subprocess.run(
        ["pdftotext", "-layout", str(pfad), "-"], check=True, capture_output=True, text=True
    ).stdout


def probe(kurz: str, quelle: Path) -> dict[str, Any]:
    meta = json.loads((ZIEL / f"{kurz}.felder.roh.json").read_text(encoding="utf-8"))
    texte, (box, box_wert), gruppe = _waehle_felder(meta)
    werte = dict(zip(texte, DEMO_TEXTE, strict=True))
    werte[box] = box_wert
    if gruppe:
        werte[gruppe[0]] = gruppe[1]

    ziel = TMP / f"{kurz}.gefuellt.pdf"
    meldungen = _fuellen(quelle, ziel, werte)
    gelesen = PdfReader(ziel)
    felder = gelesen.get_fields() or {}
    text_neu = _pdftotext(ziel)
    text_alt = _pdftotext(quelle)

    pruefung = {}
    for name, soll in werte.items():
        ist = felder.get(name, {}).get("/V")
        eintrag: dict[str, Any] = {"soll": soll, "ist_pypdf": None if ist is None else str(ist)}
        if not soll.startswith("/"):
            eintrag["sichtbar_pdftotext"] = soll in text_neu and soll not in text_alt
        if name == box or (gruppe and name == gruppe[0]):
            # Zustand der Widgets (/AS) zeigt, ob der Haken wirklich gesetzt ist.
            eintrag["as_widgets"] = _as_zustaende(gelesen, name)
        pruefung[name] = eintrag

    # Unbekannter Feldname: neue Kopie, nur dieses Feld.
    unbekannt_ziel = TMP / f"{kurz}.unbekannt.pdf"
    try:
        unbekannt_meldungen = _fuellen(quelle, unbekannt_ziel, {UNBEKANNT: "x"})
        unbekannt = {"ausnahme": None, "meldungen": unbekannt_meldungen}
    except Exception as fehler:
        unbekannt = {"ausnahme": f"{type(fehler).__name__}: {fehler}", "meldungen": []}
    unbekannt["feld_entstanden"] = UNBEKANNT in (PdfReader(unbekannt_ziel).get_fields() or {})

    acro = gelesen.trailer["/Root"]["/AcroForm"]
    return {
        "formular": kurz,
        "kopie": str(ziel),
        "need_appearances": bool(acro.get("/NeedAppearances", False)),
        "meldungen_beim_fuellen": meldungen,
        "pruefung": pruefung,
        "unbekannter_name": unbekannt,
    }


def _as_zustaende(leser: PdfReader, name: str) -> list[str]:
    zustaende: list[str] = []
    for seite in leser.pages:
        for ref in seite.get("/Annots", []) or []:
            w = ref.get_object()
            eltern = w.get("/Parent")
            t = w.get("/T") or (eltern.get_object().get("/T") if eltern is not None else None)
            if str(t) == name.split(".")[-1] or str(t) == name:
                zustaende.append(str(w.get("/AS")))
    return zustaende


def main() -> int:
    roh = os.environ.get("UC1_DATA_DIR", "").strip()
    if not roh:
        print("UC1_DATA_DIR ist nicht gesetzt", file=sys.stderr)
        return 2
    TMP.mkdir(parents=True, exist_ok=True)
    ordner = Path(roh).expanduser() / FORMULAR_ORDNER
    for kurz, datei in FORMULARE.items():
        print(json.dumps(probe(kurz, ordner / datei), ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
