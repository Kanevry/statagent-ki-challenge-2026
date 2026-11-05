"""Antrag als Entwurf vorausfüllen: Pflegegeld (PAL080) und Kur/Reha (Issue #32).

Ablauf von ``erzeuge_antrag`` (Details in docs/plan/uc1/antrag.md):
 1. Sitzung laden (``lotse.sitzung.zustand``): Antragsangaben aus dem Gespräch, Status für die Stelle.
 2. Feldzuordnung laden (``formulare/<art>.felder.json``) und das Formular prüfen, BEVOR geschrieben wird:
    sha256 und Seitenzahl der Version, jeder Feldname gegen ``reader.get_fields()``, jeder Export-Wert
    gegen die Zustände des Knopfs. pypdf ignoriert unbekannte Namen sonst still (Spike #28).
 3. Nur Felder befüllen, deren Angabe im Gespräch vorkommt. Zu lange Werte (MaxLen) werden nicht
    gekürzt, sondern stehen unter „noch offen“.
 4. Entwurf schreiben: NeedAppearances, sichtbarer Vermerk „Entwurf, nicht eingereicht“ als
    FreeText-Annotation auf jeder Seite; danach mit pypdf zurücklesen.
 5. Ergebnis: PDF, befüllte Felder, „noch offen“, Unterlagen mit Quelle, zuständige Stelle, Formularwahl.

Nichts wird eingereicht. Der Lotse füllt keine Gesundheitsangaben und keine ärztlichen Teile aus.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from collections.abc import Sequence
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Literal

import psycopg
from pypdf import PdfReader, PdfWriter
from pypdf.annotations import FreeText

from uc1 import kern, sprache

Art = Literal["pflegegeld", "reha"]

FORMULARE_DIR = Path(__file__).resolve().parent.parent / "formulare"
LAUFZEIT_DIR = Path(__file__).resolve().parent.parent / "laufzeit" / "antraege"
ZUORDNUNG: dict[str, str] = {"pflegegeld": "pal080.felder.json", "reha": "kur-reha.felder.json"}
ENTWURF = "Entwurf, nicht eingereicht"
FUELLT_NICHT = "füllt der Lotse nicht aus"
FEHLT = "Angabe fehlt im Gespräch"
KOPF = ("datei", "bezeichnung", "version", "seiten", "sha256")
VERMERK = f"{ENTWURF} (SV KI-Lotse)"  # ASCII, damit jeder Leser die Annotation ohne Schriftwahl zeigt
_PLATZHALTER = re.compile(r"\{([a-z_]+\.[a-z_]+)\}")


class AntragFehler(RuntimeError):
    """Formular, Zuordnung oder Sitzung passen nicht zusammen; es wird nichts geschrieben."""


@dataclass
class AntragErgebnis:
    """Ergebnis von ``erzeuge_antrag``, JSON-fähig über ``als_dict``."""

    art: str
    sitzung_id: str
    pdf: str
    formular: dict[str, Any]
    formularwahl: dict[str, Any]
    befuellt: list[dict[str, Any]] = field(default_factory=list)
    noch_offen: list[dict[str, Any]] = field(default_factory=list)
    unterlagen: list[dict[str, Any]] = field(default_factory=list)
    stelle: dict[str, str] | None = None
    eingereicht: bool = False

    def als_dict(self) -> dict[str, Any]:
        return asdict(self)


# --------------------------------------------------------------------------------------------------------
# Zuordnung und Formularprüfung


def lade_zuordnung(art: str) -> dict[str, Any]:
    if art not in ZUORDNUNG:
        raise AntragFehler(f"unbekannte Antragsart: {art} (erlaubt: {', '.join(ZUORDNUNG)})")
    daten: dict[str, Any] = json.loads((FORMULARE_DIR / ZUORDNUNG[art]).read_text(encoding="utf-8"))
    return daten


def sha256_datei(pfad: Path) -> str:
    return hashlib.sha256(pfad.read_bytes()).hexdigest()


def _quelle(datei: str, seite: int, wortlaut: str | None = None) -> str:
    return f"{datei}, S. {seite}" + (f": „{wortlaut}“" if wortlaut else "")


def _genannte_felder(zuordnung: dict[str, Any]) -> list[str]:
    namen = [e["feld"] for e in zuordnung["felder"]]
    namen += [f for p in zuordnung.get("pflicht", []) for f in p.get("felder", [])]
    return list(dict.fromkeys(namen))


def knopf_zustaende(feld: Any) -> set[str]:
    """Export-Werte eines Knopfs: ``/_States_`` oder, bei mehreren Widgets, die Zustände der Kinder."""
    zustaende = {str(z) for z in feld.get("/_States_", [])}
    for kind in feld.get("/Kids", []):
        normal = kind.get_object().get("/AP", {}).get("/N", {})
        zustaende |= {str(z) for z in getattr(normal, "keys", list)()}
    return zustaende - {"/Off"}


def max_laengen(reader: PdfReader) -> dict[str, int]:
    """MaxLen je voll qualifiziertem Feldnamen. ``get_fields()`` liefert MaxLen nicht mit; ein Kind erbt
    sie vom Elternknoten (PDF 1.7, 12.7.3.1)."""
    ergebnis: dict[str, int] = {}

    def gehe(knoten: Any, praefix: str, geerbt: Any) -> None:
        obj = knoten.get_object()
        teil = obj.get("/T")
        name = (f"{praefix}.{teil}" if praefix else str(teil)) if teil is not None else praefix
        laenge = obj.get("/MaxLen", geerbt)
        for kind in obj.get("/Kids", []):
            gehe(kind, name, laenge)
        if teil is not None and laenge is not None:
            ergebnis[name] = int(laenge)

    wurzel: Any = reader.trailer["/Root"]
    formular: Any = wurzel.get("/AcroForm")
    for feld in formular.get_object().get("/Fields", []) if formular is not None else []:
        gehe(feld, "", None)
    return ergebnis


def pruefe_formular(pfad: Path, zuordnung: dict[str, Any]) -> tuple[dict[str, Any], dict[str, int]]:
    """Version und Feldnamen prüfen, bevor geschrieben wird. Liefert ``get_fields()`` und MaxLen je Feld."""
    formular = zuordnung["formular"]
    if not pfad.is_file():
        raise AntragFehler(f"Formular nicht gefunden: {pfad}")
    ist = sha256_datei(pfad)
    if ist != formular["sha256"]:
        raise AntragFehler(
            f"andere Formularversion: sha256 {ist[:12]}… statt {formular['sha256'][:12]}… "
            f"({formular['datei']}); die Feldzuordnung gilt nur für die geprüfte Version"
        )
    reader = PdfReader(pfad)
    if len(reader.pages) != int(formular["seiten"]):
        raise AntragFehler(f"andere Formularversion: {len(reader.pages)} statt {formular['seiten']} Seiten")
    felder_pdf: dict[str, Any] = dict(reader.get_fields() or {})
    unbekannt = [n for n in _genannte_felder(zuordnung) if n not in felder_pdf]
    if unbekannt:
        raise AntragFehler(f"Feldnamen nicht im Formular: {', '.join(repr(n) for n in unbekannt)}")
    for eintrag in zuordnung["felder"]:
        if eintrag["art"] != "knopf":
            continue
        zustaende = knopf_zustaende(felder_pdf[eintrag["feld"]])
        falsch = sorted(set(eintrag["werte"].values()) - zustaende)
        if falsch:
            raise AntragFehler(f"Export-Werte {falsch} gibt es im Knopf {eintrag['feld']!r} nicht")
    return felder_pdf, max_laengen(reader)


# --------------------------------------------------------------------------------------------------------
# Angaben und Belegung


def antragsangaben(zustand: dict[str, Any]) -> dict[str, str]:
    """Antragsangaben aus dem Sitzungszustand; der Pensionsträger folgt aus ``angaben.status``."""
    werte = {str(k): str(v).strip() for k, v in (zustand.get("antrag") or {}).items() if v and str(v).strip()}
    status = (zustand.get("angaben") or {}).get("status")
    kurz = kern.antrag_daten()["pensionstraeger"].get(status) if status else None
    if kurz:
        werte["person.pensionstraeger"] = str(kurz)
    return werte


def _schluessel(eintrag: dict[str, Any]) -> list[str]:
    if "format" in eintrag:
        return _PLATZHALTER.findall(eintrag["format"])
    return [eintrag["angabe"]]


def feldwert(eintrag: dict[str, Any], angaben: dict[str, str]) -> str | None:
    """Wert für ein Formularfeld oder ``None``, wenn eine Angabe fehlt. Kein Feld ohne Angabe."""
    if any(not angaben.get(s) for s in _schluessel(eintrag)):
        return None
    if "format" in eintrag:
        return _PLATZHALTER.sub(lambda m: angaben[m.group(1)], eintrag["format"])
    wert = angaben[eintrag["angabe"]]
    if eintrag["art"] == "knopf":
        export = eintrag["werte"].get(wert)
        return str(export) if export else None
    if eintrag.get("umformung") == "jahr":
        jahr = re.search(r"(\d{4})\s*$", wert)
        return jahr.group(1) if jahr else None
    return wert


def belege_felder(
    zuordnung: dict[str, Any], angaben: dict[str, str], laengen: dict[str, int]
) -> tuple[dict[str, str], list[dict[str, Any]], list[dict[str, Any]]]:
    """(Werte für pypdf, befüllte Felder, zu lange Werte). MaxLen prüft der Lotse, pypdf tut es nicht."""
    datei = zuordnung["formular"]["datei"]
    werte: dict[str, str] = {}
    befuellt: list[dict[str, Any]] = []
    zu_lang: list[dict[str, Any]] = []
    for eintrag in zuordnung["felder"]:
        wert = feldwert(eintrag, angaben)
        if wert is None:
            continue
        name = eintrag["feld"]
        hoechstens = laengen.get(name)
        if eintrag["art"] == "text" and hoechstens is not None and len(wert) > hoechstens:
            zu_lang.append(
                {
                    "id": f"zu_lang:{name}",
                    "text": f"{eintrag['beschriftung']}: bitte von Hand eintragen, der Wert ist zu lang",
                    "grund": f"zu lang: {len(wert)} Zeichen, das Feld fasst {hoechstens}; nicht gekürzt",
                    "feld": name,
                    "wert": wert,
                    "quelle": _quelle(datei, int(eintrag["seite"])),
                }
            )
            continue
        werte[name] = wert
        befuellt.append(
            {"feld": name, "wert": wert, "angaben": _schluessel(eintrag), "seite": eintrag["seite"]}
        )
    return werte, befuellt, zu_lang


def noch_offen(
    zuordnung: dict[str, Any],
    angaben: dict[str, str],
    befuellt: Sequence[dict[str, Any]],
    zu_lang: Sequence[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Kuratierte Pflichtfelder, die der Entwurf nicht füllt, in Alltagssprache, mit Quelle."""
    datei = zuordnung["formular"]["datei"]
    gefuellt = {b["feld"] for b in befuellt}
    gemeldet = {z["feld"] for z in zu_lang}
    offen: list[dict[str, Any]] = list(zu_lang)
    for p in zuordnung.get("pflicht", []):
        if p.get("wenn") and not angaben.get(p["wenn"]):
            continue
        fehlen = [f for f in p["felder"] if f not in gefuellt]
        if not fehlen or set(fehlen) <= gemeldet:
            continue
        eintrag = {
            "id": p["id"],
            "text": p["text"],
            "grund": FUELLT_NICHT if p.get("lotse_fuellt_nicht") else FEHLT,
            "quelle": _quelle(datei, int(p["seite"]), p["wortlaut"]),
            "annahme": bool(p.get("annahme")),
        }
        if p.get("annahme_grund"):
            eintrag["annahme_grund"] = p["annahme_grund"]
        offen.append(eintrag)
    return offen


def unterlagen(zuordnung: dict[str, Any], angaben: dict[str, str]) -> list[dict[str, Any]]:
    datei = zuordnung["formular"]["datei"]
    liste = []
    for u in zuordnung.get("unterlagen", []):
        if u.get("wenn") and not angaben.get(u["wenn"]):
            continue
        eintrag = {"text": u["text"], "quelle": _quelle(datei, int(u["seite"]), u["wortlaut"])}
        if u.get("bedingung"):
            eintrag["bedingung"] = u["bedingung"]
        liste.append(eintrag)
    return liste


def formularwahl(zuordnung: dict[str, Any]) -> dict[str, Any]:
    formular, wahl = zuordnung["formular"], zuordnung["formularwahl"]
    ergebnis: dict[str, Any] = {
        "datei": formular["datei"],
        "bezeichnung": formular["bezeichnung"],
        "version": formular["version"],
        "begruendung": wahl["begruendung"],
        "quelle": _quelle(formular["datei"], int(wahl["quelle"]["seite"]), wahl["quelle"]["wortlaut"]),
    }
    if wahl.get("abgelehnt"):
        nein = wahl["abgelehnt"]
        ergebnis["nicht_gewaehlt"] = {
            "datei": nein["datei"],
            "quelle": _quelle(nein["datei"], int(nein["seite"]), nein["wortlaut"]),
        }
    return ergebnis


# --------------------------------------------------------------------------------------------------------
# PDF schreiben


def schreibe_entwurf(quelle: Path, werte: dict[str, str], ziel: Path) -> None:
    """Felder setzen, NeedAppearances, Vermerk „Entwurf, nicht eingereicht“ oben auf jeder Seite."""
    schreiber = PdfWriter(clone_from=quelle)
    if werte:
        schreiber.update_page_form_field_values(None, werte, auto_regenerate=False)
    schreiber.set_need_appearances_writer(True)
    for nummer, seite in enumerate(schreiber.pages):
        box = seite.mediabox
        links, oben = float(box.left), float(box.top)
        vermerk = FreeText(
            text=VERMERK,
            rect=(links + 150, oben - 24, links + 440, oben - 6),
            font="Helvetica",
            bold=True,
            font_size="11pt",
            font_color="b00000",
            border_color="b00000",
            background_color="ffffff",
        )
        schreiber.add_annotation(page_number=nummer, annotation=vermerk)
    schreiber.add_metadata({"/Subject": ENTWURF, "/Keywords": "Entwurf; nicht eingereicht; SV KI-Lotse"})
    ziel.parent.mkdir(parents=True, exist_ok=True)
    with ziel.open("wb") as aus:
        schreiber.write(aus)


def pruefe_entwurf(ziel: Path, werte: dict[str, str]) -> None:
    """Zurücklesen: jeder gesetzte Wert steht im Feld (pypdf meldet Fehlschläge nicht)."""
    gelesen = PdfReader(ziel).get_fields() or {}
    falsch = [n for n, w in werte.items() if str(gelesen.get(n, {}).get("/V")) != w]
    if falsch:
        raise AntragFehler(f"Werte nach dem Schreiben nicht im Feld: {', '.join(falsch)}")


# --------------------------------------------------------------------------------------------------------
# Ablauf


def _lade_zustand(sitzung_id: str, conn: psycopg.Connection | None) -> dict[str, Any]:
    if conn is None:
        from uc1.db import verbinde

        with verbinde() as eigene:
            zustand = kern.DbSpeicher(eigene).lade(sitzung_id)
    else:
        zustand = kern.DbSpeicher(conn).lade(sitzung_id)
    if zustand is None:
        raise AntragFehler(f"Sitzung nicht gefunden: {sitzung_id}")
    return zustand


def erzeuge_antrag(
    art: Art,
    sitzung_id: str,
    *,
    ausgabe_dir: Path | None = None,
    conn: psycopg.Connection | None = None,
    zustand: dict[str, Any] | None = None,
    formular: Path | None = None,
    zuordnung: dict[str, Any] | None = None,
) -> AntragErgebnis:
    """Antrag als Entwurf aus einer Sitzung. ``zustand``, ``formular`` und ``zuordnung`` sind für Tests
    injizierbar; ohne sie gelten lotse.sitzung über ``conn``, UC1_DATA_DIR und formulare/<art>.felder.json."""
    zuordnung = zuordnung or lade_zuordnung(art)
    if zustand is None:
        zustand = _lade_zustand(sitzung_id, conn)
    angaben = antragsangaben(zustand)
    stelle = kern.zustaendige_stelle(zuordnung["leistung"], (zustand.get("angaben") or {}).get("status"))
    if stelle:
        angaben["stelle.name"] = stelle["name"]
    if formular is None:
        from uc1.config import daten_dir

        formular = daten_dir() / zuordnung["formular"]["datei"]

    _, laengen = pruefe_formular(formular, zuordnung)
    werte, befuellt, zu_lang = belege_felder(zuordnung, angaben, laengen)
    offen = noch_offen(zuordnung, angaben, befuellt, zu_lang)
    datei = zuordnung["formular"]["datei"]
    if stelle is None:
        offen.insert(
            0,
            {
                "id": "stelle",
                "text": "zuständige Stelle: dazu fehlt, von wem die Person ihre Pension bekommt",
                "grund": FEHLT,
                "quelle": "BPGG § 22 Abs. 1 (daten/traeger.yaml)",
                "annahme": False,
            },
        )
    elif zuordnung["formular"].get("fuer_stelle") not in (None, stelle["stelle"]):
        offen.insert(
            0,
            {
                "id": "formular_stelle",
                "text": f"Zuständig ist: {stelle['name']}. Dieses Formular gehört zu: "
                f"{zuordnung['formular']['fuer_stelle']}. Nehmen Sie das Formular der zuständigen Stelle",
                "grund": "Formular passt nicht zur zuständigen Stelle",
                "quelle": f"{stelle['fundstelle']}; {datei}",
                "annahme": False,
            },
        )

    ziel_dir = ausgabe_dir or LAUFZEIT_DIR
    ziel = ziel_dir / f"{art}-{re.sub(r'[^A-Za-z0-9-]', '_', sitzung_id)}-entwurf.pdf"
    schreibe_entwurf(formular, werte, ziel)
    pruefe_entwurf(ziel, werte)
    return AntragErgebnis(
        art=art,
        sitzung_id=sitzung_id,
        pdf=str(ziel),
        formular={k: zuordnung["formular"][k] for k in KOPF},
        formularwahl=formularwahl(zuordnung),
        befuellt=befuellt,
        noch_offen=offen,
        unterlagen=unterlagen(zuordnung, angaben),
        stelle=stelle,
    )


# --------------------------------------------------------------------------------------------------------
# CLI


def _kurz(quelle: str) -> str:
    """„Ordner/PAL080….pdf, S. 2: „Wortlaut““ → „Antrag PAL080, S. 2“; der Wortlaut steht im JSON."""
    return sprache.kurze_quelle(quelle.split(": „", 1)[0])


def _als_text(e: AntragErgebnis) -> str:
    """Kurz und in Bürgersprache: was fertig ist, was Sie noch tun. Wortlaut der Belege nur im JSON."""
    zeilen = [f"Ihr Antrag ist als Entwurf fertig ({ENTWURF}). Abgeschickt wird nichts.", f"Datei: {e.pdf}"]
    zeilen.append(f"Formular: {e.formularwahl['bezeichnung']}")
    zeilen.append(f"Warum dieses Formular: {e.formularwahl['begruendung']}")
    if e.stelle:
        zeilen.append(f"Zuständig: {e.stelle['name']} ({e.stelle['fundstelle']})")
    zeilen.append(f"Schon ausgefüllt ({len(e.befuellt)}):")
    zeilen += [f"- {b['feld']}: {b['wert']}" for b in e.befuellt]
    zeilen.append(f"Bitte noch selbst ausfüllen ({len(e.noch_offen)}):")
    zeilen += [f"- {o['text']} ({_kurz(o['quelle'])})" for o in e.noch_offen]
    zeilen.append("Legen Sie bei:")
    zeilen += [
        f"- {u['text']}" + (f", {u['bedingung']}" if u.get("bedingung") else "") + f" ({_kurz(u['quelle'])})"
        for u in e.unterlagen
    ]
    zeilen.append("Prüfen Sie alles, ergänzen Sie, was fehlt, und unterschreiben Sie selbst.")
    return sprache.glaette("\n".join(zeilen))


def cli(argv: Sequence[str]) -> int:
    parser = argparse.ArgumentParser(prog="lotse antrag", description="Antrag als Entwurf vorausfüllen (#32)")
    parser.add_argument("art", choices=list(ZUORDNUNG))
    parser.add_argument("--sitzung", required=True, help="ID der Sitzung (lotse frage --json: sitzung_id)")
    parser.add_argument("--ausgabe", type=Path, help=f"Zielordner (Standard: {LAUFZEIT_DIR})")
    parser.add_argument("--json", action="store_true", help="Ergebnis als JSON")
    args = parser.parse_args(list(argv))
    from uc1.config import KonfigFehler

    try:
        ergebnis = erzeuge_antrag(args.art, args.sitzung, ausgabe_dir=args.ausgabe)
    except (AntragFehler, KonfigFehler) as fehler:
        print(f"lotse antrag: {fehler}", file=sys.stderr)
        return 1
    if args.json:
        print(json.dumps(ergebnis.als_dict(), ensure_ascii=False, indent=2))
    else:
        print(_als_text(ergebnis))
    return 0


if __name__ == "__main__":
    raise SystemExit(cli(sys.argv[1:]))
