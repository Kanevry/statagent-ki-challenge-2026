"""Spike 2 (#28): AcroForm-Felder der UC1-Antragsformulare auslesen.

Liest je Formular alle Endfelder (voller Name, Typ, Flags, Wert, Seite, Tooltip, Export-Werte) und
schreibt nur Feldmetadaten als JSON nach uc1/formulare/<kurz>.felder.roh.json.

Aufruf aus uc1/:  UC1_DATA_DIR=… uv run python spikes/formularfelder.py
"""

from __future__ import annotations

import json
import os
import sys
from collections import Counter
from pathlib import Path
from typing import Any

from pypdf import PdfReader
from pypdf.generic import DictionaryObject, IndirectObject

# Kurzname -> Dateiname im Ordner "Anträge und Formulare" von UC1_DATA_DIR.
FORMULARE = {
    "pal080": "PAL080_0125_Mpfl_052026.pdf",
    "kur-reha": "Antrag Kur und Reha.pdf",
}
FORMULAR_ORDNER = "Anträge und Formulare"
ZIEL = Path(__file__).resolve().parent.parent / "formulare"

# Bits des Feld-Flags /Ff (PDF 32000-1, Tab. 221, 226, 228).
FF_READONLY = 1 << 0
FF_REQUIRED = 1 << 1
FF_NOEXPORT = 1 << 2
FF_RADIO = 1 << 15
FF_PUSHBUTTON = 1 << 16


def _geerbt(feld: DictionaryObject, schluessel: str) -> Any:
    """Vererbbares Attribut (/FT, /Ff, /V) über die /Parent-Kette suchen."""
    knoten: DictionaryObject | None = feld
    while knoten is not None:
        if schluessel in knoten:
            return knoten[schluessel]
        eltern = knoten.get("/Parent")
        knoten = eltern.get_object() if eltern is not None else None
    return None


def _voller_name(feld: DictionaryObject) -> str:
    teile: list[str] = []
    knoten: DictionaryObject | None = feld
    while knoten is not None:
        if "/T" in knoten:
            teile.append(str(knoten["/T"]))
        eltern = knoten.get("/Parent")
        knoten = eltern.get_object() if eltern is not None else None
    return ".".join(reversed(teile))


def _seiten_je_widget(leser: PdfReader) -> dict[int, int]:
    """Objektnummer eines Widgets -> Seitennummer (1-basiert)."""
    zuordnung: dict[int, int] = {}
    for nummer, seite in enumerate(leser.pages, start=1):
        for annot in seite.get("/Annots", []) or []:
            if isinstance(annot, IndirectObject):
                zuordnung[annot.idnum] = nummer
    return zuordnung


def _endfelder(knoten_ref: Any, ausgabe: list[tuple[DictionaryObject, list[Any]]]) -> None:
    """Feldbaum ablaufen. Endfeld = Knoten ohne Kinder mit eigenem /T; Kinder ohne /T sind Widgets."""
    knoten = knoten_ref.get_object()
    kinder = knoten.get("/Kids", [])
    feld_kinder = [k for k in kinder if "/T" in k.get_object()]
    if feld_kinder:
        for kind in feld_kinder:
            _endfelder(kind, ausgabe)
        return
    widgets = list(kinder) if kinder else [knoten_ref]
    ausgabe.append((knoten, widgets))


def _typ_detail(ft: str, ff: int) -> str:
    if ft == "/Btn":
        if ff & FF_PUSHBUTTON:
            return "pushbutton"
        return "radio" if ff & FF_RADIO else "checkbox"
    if ft == "/Ch":
        return "combo" if ff & (1 << 17) else "liste"
    return "text" if ft == "/Tx" else "signatur" if ft == "/Sig" else "unbekannt"


def felder_lesen(pfad: Path) -> dict[str, Any]:
    leser = PdfReader(pfad)
    acro = leser.trailer["/Root"].get("/AcroForm")
    if acro is None:
        return {"datei": pfad.name, "seiten": len(leser.pages), "felder": [], "zusammenfassung": {}}
    acro = acro.get_object()
    seiten = _seiten_je_widget(leser)
    endfelder: list[tuple[DictionaryObject, list[Any]]] = []
    for ref in acro.get("/Fields", []):
        _endfelder(ref, endfelder)

    felder: list[dict[str, Any]] = []
    for feld, widgets in endfelder:
        ft = str(_geerbt(feld, "/FT") or "")
        ff = int(_geerbt(feld, "/Ff") or 0)
        wert = _geerbt(feld, "/V")
        export: set[str] = set()
        feld_seiten: set[int] = set()
        for w_ref in widgets:
            if isinstance(w_ref, IndirectObject) and w_ref.idnum in seiten:
                feld_seiten.add(seiten[w_ref.idnum])
            w = w_ref.get_object()
            if ft == "/Btn":
                normal = w.get("/AP", {}).get("/N")
                if normal is not None:
                    export.update(str(k) for k in normal.get_object() if str(k) != "/Off")
        eintrag: dict[str, Any] = {
            "name": _voller_name(feld),
            "typ": ft,
            "art": _typ_detail(ft, ff),
            "pflicht": bool(ff & FF_REQUIRED),
            "nur_lesen": bool(ff & FF_READONLY),
            "kein_export": bool(ff & FF_NOEXPORT),
            "ff": ff,
            "wert": None if wert is None else str(wert),
            "seiten": sorted(feld_seiten),
            "widgets": len(widgets),
            "tooltip": str(feld["/TU"]) if "/TU" in feld else None,
        }
        if ft == "/Btn":
            eintrag["export_werte"] = sorted(export)
        if ft == "/Ch" and "/Opt" in feld:
            eintrag["optionen"] = [str(o) for o in feld["/Opt"]]
        if ft == "/Tx" and "/MaxLen" in feld:
            eintrag["max_laenge"] = int(feld["/MaxLen"])
        felder.append(eintrag)

    typen = Counter(f["typ"] for f in felder)
    arten = Counter(f["art"] for f in felder)
    zusammenfassung = {
        "felder_gesamt": len(felder),
        "widgets_gesamt": sum(f["widgets"] for f in felder),
        "je_typ": dict(sorted(typen.items())),
        "je_art": dict(sorted(arten.items())),
        "pflicht": sum(f["pflicht"] for f in felder),
        "nur_lesen": sum(f["nur_lesen"] for f in felder),
        "mit_wert": sum(1 for f in felder if f["wert"] not in (None, "", "/Off")),
        "mit_tooltip": sum(1 for f in felder if f["tooltip"]),
        "ohne_seite": sum(1 for f in felder if not f["seiten"]),
        "need_appearances": bool(acro.get("/NeedAppearances", False)),
        "xfa": "/XFA" in acro,
    }
    return {
        "datei": pfad.name,
        "seiten": len(leser.pages),
        "zusammenfassung": zusammenfassung,
        "felder": felder,
    }


def main() -> int:
    roh = os.environ.get("UC1_DATA_DIR", "").strip()
    if not roh:
        print("UC1_DATA_DIR ist nicht gesetzt", file=sys.stderr)
        return 2
    ordner = Path(roh).expanduser() / FORMULAR_ORDNER
    ZIEL.mkdir(parents=True, exist_ok=True)
    for kurz, datei in FORMULARE.items():
        ergebnis = felder_lesen(ordner / datei)
        ziel = ZIEL / f"{kurz}.felder.roh.json"
        ziel.write_text(json.dumps(ergebnis, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"{kurz}: {json.dumps(ergebnis['zusammenfassung'], ensure_ascii=False)} -> {ziel.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
