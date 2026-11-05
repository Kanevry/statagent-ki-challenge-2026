"""Stelle und Termin (Issue #81): belegte Beratungsstelle mit Adresse aus dem Korpus, Terminentwurf als ICS.

Nichts wird gebucht, kein Kalender- oder Buchungsdienst wird angesprochen. Regeln:

- Eine Adresse wird nur ausgegeben, wenn sie normierter Teilstring der zitierten Quelle ist
  (``adresse_belegt``); sonst steht dort „nicht belegt“. Adressen kommen regelbasiert aus dem Seitentext
  (Muster in ``stellen/adressmuster.yaml``), nie aus einem Sprachmodell.
- Der Entwurf ist deterministisch: Wunschdatum und Zeitstempel stehen im Fixture, nicht ``now()``.
- ``naechste_rueckfrage`` ist eine reine Funktion für den Kern: höchstens eine Frage je Aufruf, nie eine
  schon gestellte oder beantwortete.

Aufruf: ``python -m uc1.termin --fall termin-wien [--json]``, ``--pruefen termin-wien``,
``--aufzeichnen termin-wien`` (schreibt ``eval/termin-dialoge.json``).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import tempfile
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass
from datetime import date, datetime
from functools import cache
from pathlib import Path
from typing import Any

import psycopg
import yaml

from uc1 import kern, sprache
from uc1.db import verbinde
from uc1.eval import normiere
from uc1.suche import suche
from uc1.typen import SucheFn, SuchFilter, Treffer

PAKET_DIR = Path(__file__).resolve().parent.parent
STELLEN_DIR = PAKET_DIR / "stellen"
EVAL_DIR = PAKET_DIR / "eval"
ERZEUGT_DIR = PAKET_DIR / "erzeugt"
DIALOGE_DATEI = EVAL_DIR / "termin-dialoge.json"

QUELLEN: tuple[Any, ...] = ("katalog", "formular")
K_SUCHE = 5
ICS_MAX_OKTETTE = 75
_FALLNAME = re.compile(r"^[a-z0-9][a-z0-9-]*$")

# --------------------------------------------------------------------------------------------------------
# Daten


@cache
def _yaml(name: str) -> dict[str, Any]:
    daten: dict[str, Any] = yaml.safe_load((STELLEN_DIR / name).read_text(encoding="utf-8"))
    return daten


def adressmuster() -> dict[str, Any]:
    return _yaml("adressmuster.yaml")


def wiener_stellen() -> dict[str, Any]:
    return _yaml("wien.yaml")


def termin_regeln() -> dict[str, Any]:
    return _yaml("termin.yaml")


def nicht_belegt() -> str:
    return str(termin_regeln()["texte"]["ohne_adresse"])


@cache
def _adress_regexe() -> tuple[re.Pattern[str], ...]:
    """Formen aus adressmuster.yaml mit eingesetzten Bausteinen, in Dateireihenfolge."""
    daten = adressmuster()
    teile: dict[str, str] = {k: f"(?:{v})" for k, v in daten["teile"].items()}
    formen = []
    for form in daten["formen"].values():
        muster = str(form)
        for name, wert in teile.items():
            muster = muster.replace("{" + name + "}", wert)
        formen.append(re.compile(muster))
    return tuple(formen)


def lade_fall(name: str) -> dict[str, Any]:
    """Fixture ``eval/<name>.json``; nur Kleinbuchstaben, Ziffern und Bindestriche im Namen."""
    if not _FALLNAME.match(name):
        raise ValueError(f"ungültiger Fallname: {name!r}")
    fall: dict[str, Any] = json.loads((EVAL_DIR / f"{name}.json").read_text(encoding="utf-8"))
    return fall


# --------------------------------------------------------------------------------------------------------
# Stellen


@dataclass(frozen=True)
class Stelle:
    """Eine Einrichtung bzw. Beratungsstelle. ``adresse`` ist None, wenn sie nicht belegt ist."""

    id: str
    name: str
    adresse: str | None
    quelle: str | None  # Datei relativ zu UC1_DATA_DIR
    seite: int | None
    abschnitt_id: int | None
    beleg: str  # normierter Ausschnitt vom Namensanker bis zum Ende der Adresse
    rolle: str
    zustaendig: str | None  # Fundstelle, wenn der Kern diesen Träger als zuständig liefert
    plz: str | None = None
    ort: str | None = None
    anliegen: tuple[str, ...] = ()

    @property
    def belegt(self) -> bool:
        return self.adresse is not None

    @property
    def adresse_text(self) -> str:
        return self.adresse if self.adresse is not None else nicht_belegt()

    def als_dict(self) -> dict[str, Any]:
        daten = asdict(self)
        daten["adresse"] = self.adresse_text
        daten["belegt"] = self.belegt
        daten["anliegen"] = list(self.anliegen)
        return daten


@dataclass(frozen=True)
class Adressfund:
    adresse: str
    plz: str
    ort: str
    beleg: str


def adresse_belegt(adresse: str | None, quelltext: str) -> bool:
    """Ist die Adresse normierter Teilstring der Quelle? Leerraum, Bindestriche, Anführungszeichen egal."""
    if adresse is None:
        return False
    kern_ = normiere(adresse)
    return bool(kern_) and kern_ in normiere(quelltext)


def finde_adresse(text: str, anker: str, ort: str | None = None) -> Adressfund | None:
    """Erste Adresse hinter dem Namensanker (höchstens ``max_abstand`` Zeichen), Ort muss passen."""
    seite = normiere(text)
    anker_n = normiere(anker)
    max_abstand = int(adressmuster()["max_abstand"])
    start = seite.find(anker_n)
    while start >= 0:
        ende = start + len(anker_n)
        # Alle Treffer im Fenster, nicht nur den ersten je Form: die Nachbarspalte kann zuerst stehen.
        fenster_ende = min(len(seite), ende + max_abstand + 200)
        kandidaten = [m for rx in _adress_regexe() for m in rx.finditer(seite, ende, fenster_ende)]
        kandidaten = [m for m in kandidaten if m.start() - ende <= max_abstand]
        if ort is not None:
            kandidaten = [m for m in kandidaten if m.group("ort") == ort]
        if kandidaten:
            m = min(kandidaten, key=lambda x: x.start())
            return Adressfund(m.group(0), m.group("plz"), m.group("ort"), seite[start : m.end()])
        start = seite.find(anker_n, ende)
    return None


def _stelle(eintrag: Mapping[str, Any], treffer: Sequence[Treffer], zustaendig: str | None) -> Stelle:
    basis: dict[str, Any] = {
        "id": str(eintrag["id"]),
        "name": str(eintrag["name"]),
        "rolle": str(eintrag["rolle"]),
        "zustaendig": zustaendig,
        "anliegen": tuple(eintrag.get("anliegen", ())),
    }
    datei_teil = str(eintrag.get("datei", ""))
    for t in treffer:
        if datei_teil not in t.datei:
            continue
        fund = finde_adresse(t.text, str(eintrag["anker"]), eintrag.get("ort"))
        if fund is not None and adresse_belegt(fund.adresse, t.text):
            return Stelle(
                adresse=fund.adresse,
                quelle=t.datei,
                seite=t.seite,
                abschnitt_id=t.abschnitt_id,
                beleg=fund.beleg,
                plz=fund.plz,
                ort=fund.ort,
                **basis,
            )
    return Stelle(adresse=None, quelle=None, seite=None, abschnitt_id=None, beleg="", **basis)


def stellen_finden(
    lage: Mapping[str, Any],
    *,
    conn: psycopg.Connection | None = None,
    suche_fn: SucheFn = suche,
) -> list[Stelle]:
    """Stellen zur Lage: Wiener Stellen aus stellen/wien.yaml, belegt über die Volltextsuche in Katalogen
    und Formularen, dazu die zuständige Stelle aus daten/traeger.yaml (Kern). Fehlt für den zuständigen
    Träger eine belegte Adresse, kommt er mit „nicht belegt“ dazu."""
    if conn is None:
        with verbinde() as eigene:
            return stellen_finden(lage, conn=eigene, suche_fn=suche_fn)
    angaben: Mapping[str, Any] = lage.get("angaben", {})
    zust = kern.zustaendige_stelle(str(lage["leistung"]), angaben.get("status"))
    filter_ = SuchFilter(quellen=QUELLEN)
    stellen: list[Stelle] = []
    tabelle = wiener_stellen()
    if str(angaben.get("bundesland", "")).casefold() == tabelle["bundesland"]:
        for eintrag in tabelle["stellen"]:
            treffer = suche_fn(
                str(eintrag["suchanfrage"]), k=K_SUCHE, filter=filter_, weg="volltext", conn=conn
            )
            traeger = eintrag.get("traeger")
            zustaendig = zust["fundstelle"] if zust is not None and traeger == zust["stelle"] else None
            stellen.append(_stelle(eintrag, treffer, zustaendig))
    if zust is not None and not any(s.zustaendig and s.belegt for s in stellen):
        stellen.append(
            Stelle(
                id=f"traeger_{zust['stelle'].casefold()}",
                name=zust["name"],
                adresse=None,
                quelle=None,
                seite=None,
                abschnitt_id=None,
                beleg="",
                rolle="zuständige Stelle laut Entscheidungstabelle",
                zustaendig=zust["fundstelle"],
            )
        )
    return stellen


def stelle_fuer_termin(stellen: Sequence[Stelle], anliegen: str) -> Stelle | None:
    """Erste belegte Stelle zum Anliegen (Reihenfolge aus wien.yaml)."""
    return next((s for s in stellen if s.belegt and anliegen in s.anliegen), None)


# --------------------------------------------------------------------------------------------------------
# Rückfrage


def erkenne_angaben(text: str) -> dict[str, str]:
    """Postleitzahl (Wien) und Zeitpräferenz aus Bürgersprache, regelbasiert (stellen/termin.yaml)."""
    regeln = termin_regeln()["erkennen"]
    sauber = normiere(text).casefold()
    angaben: dict[str, str] = {}
    if (m := re.search(regeln["plz"], sauber)) is not None:
        angaben["plz"] = m.group(1) or m.group(2)
    for wert, muster in regeln["zeitpraeferenz"].items():
        if any(re.search(x, sauber) for x in muster):
            angaben["zeitpraeferenz"] = str(wert)
            break
    return angaben


def _offene_rueckfrage(zustand: Mapping[str, Any]) -> dict[str, str] | None:
    angaben: Mapping[str, Any] = zustand.get("angaben") or {}
    gefragt = set(zustand.get("gefragt") or ())
    for r in termin_regeln()["rueckfragen"]:
        if not angaben.get(r["feld"]) and r["feld"] not in gefragt:
            return {"feld": str(r["feld"]), "frage": str(r["frage"])}
    return None


def naechste_rueckfrage(zustand: Mapping[str, Any]) -> str | None:
    """Nächste Terminfrage oder None. Fehlt nur die Zeitpräferenz, genau diese eine Frage; ist sie bekannt
    oder schon gestellt, keine. Rein: liest ``zustand["angaben"]`` und ``zustand["gefragt"]``."""
    offen = _offene_rueckfrage(zustand)
    return offen["frage"] if offen is not None else None


def behauptet_termin(text: str) -> bool:
    """Steht ein Satz im Text, der eine Buchung oder einen freien Termin behauptet?"""
    sauber = normiere(text).casefold()
    return any(re.search(m, sauber) for m in termin_regeln()["verboten"])


# --------------------------------------------------------------------------------------------------------
# Terminentwurf (RFC 5545, nur Standardbibliothek)

_VTIMEZONE_WIEN = [
    "BEGIN:VTIMEZONE",
    "TZID:Europe/Vienna",
    "BEGIN:DAYLIGHT",
    "TZOFFSETFROM:+0100",
    "TZOFFSETTO:+0200",
    "TZNAME:CEST",
    "DTSTART:19700329T020000",
    "RRULE:FREQ=YEARLY;BYMONTH=3;BYDAY=-1SU",
    "END:DAYLIGHT",
    "BEGIN:STANDARD",
    "TZOFFSETFROM:+0200",
    "TZOFFSETTO:+0100",
    "TZNAME:CET",
    "DTSTART:19701025T030000",
    "RRULE:FREQ=YEARLY;BYMONTH=10;BYDAY=-1SU",
    "END:STANDARD",
    "END:VTIMEZONE",
]


def ics_text(wert: str) -> str:
    """TEXT-Wert nach RFC 5545 § 3.3.11 maskieren."""
    return wert.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")


def falte(zeile: str) -> str:
    """Zeile nach RFC 5545 § 3.1 auf höchstens 75 Oktette falten, ohne UTF-8-Zeichen zu zerteilen."""
    teile: list[str] = []
    aktuell, laenge, grenze = "", 0, ICS_MAX_OKTETTE
    for zeichen in zeile:
        n = len(zeichen.encode("utf-8"))
        if laenge + n > grenze:
            teile.append(aktuell)
            aktuell, laenge, grenze = "", 0, ICS_MAX_OKTETTE - 1  # Folgezeilen beginnen mit einem Blank
        aktuell += zeichen
        laenge += n
    teile.append(aktuell)
    return "\r\n ".join(teile)


def checkliste(lage: Mapping[str, Any], stelle: Stelle, wunsch: Mapping[str, Any]) -> dict[str, list[str]]:
    """Unterlagen (aus daten/leistungen.yaml mit Quelle), Nähe und Zeitpräferenz."""
    leistung = kern.leistungen().get(str(lage["leistung"]), {})
    unterlagen = [
        f"{u['text']} ({sprache.kurze_quelle(u['quelle'])})" for u in leistung.get("unterlagen", [])
    ]
    formular = leistung.get("formular")
    if formular:
        # Nur die Bezeichnung: Sie nennt das Formular schon („Antrag auf Pflegegeld (PAL080) der PVA“); der
        # Kurzname dahinter wiederholte es („… (Antrag PAL080)“, Review !68).
        unterlagen.append(str(formular["bezeichnung"]))
    angaben: Mapping[str, Any] = lage.get("angaben", {})
    wohnort = f"{angaben['plz']} Wien" if angaben.get("plz") else "nicht genannt"
    naehe = [f"Ihr Wohnort: {wohnort}. Die Stelle: {stelle.adresse_text}."]
    fenster = termin_regeln()["zeitfenster"].get(str(wunsch.get("zeitpraeferenz", "")))
    zeit = [f"Ihr Wunsch: {fenster['text']}" if fenster else "nicht genannt"]
    return {"unterlagen": unterlagen, "naehe": naehe, "zeitpraeferenz": zeit}


def _beschreibung(lage: Mapping[str, Any], stelle: Stelle, wunsch: Mapping[str, Any]) -> str:
    texte = termin_regeln()["texte"]
    liste = checkliste(lage, stelle, wunsch)
    zeilen = [str(texte["nicht_gebucht"]), str(texte["wunschhinweis"]), "", f"Stelle: {stelle.name}"]
    zeilen.append(f"Aufgabe: {stelle.rolle}")
    if stelle.zustaendig:
        zeilen.append(f"Zuständig laut {stelle.zustaendig}.")
    zeilen += ["", "Checkliste:", "Unterlagen:"] + [f"- {u}" for u in liste["unterlagen"]]
    zeilen += ["Nähe:"] + [f"- {n}" for n in liste["naehe"]]
    zeilen += ["Zeitpräferenz:"] + [f"- {z}" for z in liste["zeitpraeferenz"]]
    beleg = sprache.kurze_quelle(f"{stelle.quelle}, S. {stelle.seite}")
    # Die interne Abschnitt-ID steht nur im JSON (``Stelle.als_dict``), nicht im Text für Menschen.
    zeilen += ["", f"Quelle: {beleg}"]
    return sprache.glaette("\n".join(zeilen))


def ics_inhalt(lage: Mapping[str, Any], stelle: Stelle, *, wunsch: Mapping[str, Any]) -> str:
    """ICS-Text mit genau einem VEVENT (STATUS:TENTATIVE). Wirft ValueError ohne belegte Adresse."""
    if stelle.adresse is None or stelle.quelle is None:
        raise ValueError(f"Stelle {stelle.id} hat keine belegte Adresse; kein Terminentwurf")
    fenster = termin_regeln()["zeitfenster"].get(str(wunsch.get("zeitpraeferenz", "")))
    if fenster is None:
        raise ValueError("Zeitpräferenz fehlt; zuerst naechste_rueckfrage stellen")
    tag = date.fromisoformat(str(wunsch["datum"])).strftime("%Y%m%d")
    stempel = datetime.fromisoformat(str(lage["erstellt"]).replace("Z", "+00:00")).strftime("%Y%m%dT%H%M%SZ")
    von, bis = (str(fenster[x]).replace(":", "") + "00" for x in ("von", "bis"))
    uid_quelle = f"{lage.get('fall', '')}|{stelle.id}|{tag}|{wunsch['zeitpraeferenz']}"
    uid = hashlib.sha256(uid_quelle.encode("utf-8")).hexdigest()[:16]
    zeilen = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//OneShotAndy//SV KI-Lotse UC1 Terminentwurf//DE",
        "CALSCALE:GREGORIAN",
        *_VTIMEZONE_WIEN,
        "BEGIN:VEVENT",
        f"UID:{lage.get('fall', 'termin')}-{uid}@lotse.invalid",
        f"DTSTAMP:{stempel}",
        f"DTSTART;TZID=Europe/Vienna:{tag}T{von}",
        f"DTEND;TZID=Europe/Vienna:{tag}T{bis}",
        f"SUMMARY:{ics_text(str(termin_regeln()['texte']['summary']))}",
        "STATUS:TENTATIVE",
        "TRANSP:TRANSPARENT",
        "CLASS:PRIVATE",
        f"LOCATION:{ics_text(stelle.adresse)}",
        f"DESCRIPTION:{ics_text(_beschreibung(lage, stelle, wunsch))}",
        "END:VEVENT",
        "END:VCALENDAR",
    ]
    return "".join(falte(z) + "\r\n" for z in zeilen)


def termin_entwurf(
    lage: Mapping[str, Any], stelle: Stelle, *, wunsch: Mapping[str, Any], ziel: Path | None = None
) -> Path:
    """Schreibt den Terminentwurf (Standard: erzeugt/<fall>.ics) und gibt den Pfad zurück. Bucht nichts."""
    pfad = ziel if ziel is not None else ERZEUGT_DIR / f"{lage.get('fall', 'termin-wien')}.ics"
    pfad.parent.mkdir(parents=True, exist_ok=True)
    pfad.write_bytes(ics_inhalt(lage, stelle, wunsch=wunsch).encode("utf-8"))
    return pfad


def _ics_wert(wert: str) -> str:
    return re.sub(r"\\([\\;,nN])", lambda m: "\n" if m.group(1) in "nN" else m.group(1), wert)


def parse_ics(text: str) -> dict[str, Any]:
    """Kleiner Parser: entfaltet Zeilen, zählt VEVENTs und liest ihre Eigenschaften (ohne Parameter)."""
    roh = text.split("\r\n")
    zeilen: list[str] = []
    for z in roh:
        if z[:1] in (" ", "\t") and zeilen:
            zeilen[-1] += z[1:]
        elif z:
            zeilen.append(z)
    events: list[dict[str, str]] = []
    offen: dict[str, str] | None = None
    tiefe_ok = True
    for z in zeilen:
        if z == "BEGIN:VEVENT":
            tiefe_ok = tiefe_ok and offen is None
            offen = {}
        elif z == "END:VEVENT":
            tiefe_ok = tiefe_ok and offen is not None
            if offen is not None:
                events.append(offen)
            offen = None
        elif offen is not None and ":" in z:
            name, wert = z.split(":", 1)
            offen[name.split(";", 1)[0]] = _ics_wert(wert)
    return {
        "vevents": len(events),
        "ausgeglichen": tiefe_ok and offen is None,
        "zeilen_zu_lang": sum(len(z.encode("utf-8")) > ICS_MAX_OKTETTE for z in roh),
        "nur_crlf": "\n" not in text.replace("\r\n", ""),
        "events": events,
    }


# --------------------------------------------------------------------------------------------------------
# Dialoge


def fuehre_dialog(
    fall: Mapping[str, Any], eingaben: Sequence[str], stellen: Sequence[Stelle]
) -> dict[str, Any]:
    """Deterministischer Dialog ohne Modell: Angaben aus jeder Eingabe, je Runde höchstens eine Rückfrage,
    am Ende ein Terminentwurf (nicht gebucht) zur ersten belegten Stelle."""
    zustand: dict[str, Any] = {"angaben": {}, "gefragt": []}
    verlauf: list[dict[str, str]] = []
    ergebnis: dict[str, Any] = {}
    for text in eingaben:
        verlauf.append({"rolle": "person", "text": text})
        zustand["angaben"].update(erkenne_angaben(text))
        status = kern.erkenne_status(text)
        if status:
            zustand["angaben"]["status"] = status
        offen = _offene_rueckfrage(zustand)
        if offen is not None:
            zustand["gefragt"].append(offen["feld"])
            verlauf.append(
                {"rolle": "lotse", "art": "rueckfrage", "feld": offen["feld"], "text": offen["frage"]}
            )
            continue
        stelle = stelle_fuer_termin(stellen, str(fall["anliegen"]))
        if stelle is None:
            verlauf.append({"rolle": "lotse", "art": "abstinenz", "text": nicht_belegt()})
            break
        zeit = termin_regeln()["zeitfenster"][zustand["angaben"]["zeitpraeferenz"]]["text"]
        datum = ".".join(reversed(str(fall["wunsch"]["datum"]).split("-")))
        quelle = sprache.kurze_quelle(f"{stelle.quelle}, S. {stelle.seite}")
        antwort = sprache.glaette(
            f"Ich schlage vor: {stelle.name}, {stelle.adresse_text} ({quelle}). Ihr Wunsch: {datum}, {zeit}. "
            f"{termin_regeln()['texte']['nicht_gebucht']}"
        )
        verlauf.append({"rolle": "lotse", "art": "entwurf", "text": antwort})
        ergebnis = {
            "stelle": stelle.id,
            "adresse": stelle.adresse_text,
            "quelle": stelle.quelle,
            "seite": stelle.seite,
            "status": "TENTATIVE",
            "gebucht": False,
        }
        break
    lotse_texte = [v["text"] for v in verlauf if v["rolle"] == "lotse"]
    return {
        "verlauf": verlauf,
        "rueckfragen_gesamt": sum(v.get("art") == "rueckfrage" for v in verlauf),
        "rueckfragen_zeitpraeferenz": sum(v.get("feld") == "zeitpraeferenz" for v in verlauf),
        "freier_termin_behauptet": any(behauptet_termin(t) for t in lotse_texte),
        "angaben": dict(zustand["angaben"]),
        "ergebnis": ergebnis,
        "beleg_ids": [s.abschnitt_id for s in stellen if s.abschnitt_id is not None],
    }


def dialogfaelle(fall: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Die zwei Fälle aus #81: Zeitpräferenz fehlt (genau 1 Rückfrage), Zeitpräferenz bekannt (keine)."""
    ohne_zeit = re.sub(r",\s*am liebsten vormittags", "", str(fall["lage"]))
    return [
        {
            "id": "zeit-fehlt",
            "erwartet_rueckfragen_zeitpraeferenz": 1,
            "eingaben": [ohne_zeit, "Vormittags."],
        },
        {"id": "zeit-bekannt", "erwartet_rueckfragen_zeitpraeferenz": 0, "eingaben": [str(fall["lage"])]},
    ]


def dialoge_aufzeichnen(fall: Mapping[str, Any], stellen: Sequence[Stelle]) -> list[dict[str, Any]]:
    return [
        {"id": d["id"], "erwartet_rueckfragen_zeitpraeferenz": d["erwartet_rueckfragen_zeitpraeferenz"]}
        | fuehre_dialog(fall, d["eingaben"], stellen)
        for d in dialogfaelle(fall)
    ]


# --------------------------------------------------------------------------------------------------------
# Prüfung der AC aus #81


def _quelltext(conn: psycopg.Connection, abschnitt_id: int) -> str:
    zeile = conn.execute("SELECT text FROM lotse.abschnitt WHERE id = %s", (abschnitt_id,)).fetchone()
    return str(zeile[0]) if zeile else ""


def pruefen(name: str, *, conn: psycopg.Connection | None = None) -> dict[str, Any]:
    """Prüft die AC: Stellen belegt, Adressen Teilstring der Quelle (gegen die DB neu gelesen), 1 VEVENT
    TENTATIVE mit „nicht gebucht“, Dialoge, Determinismus. Schreibt erzeugt/<fall>.ics."""
    if conn is None:
        with verbinde() as eigene:
            return pruefen(name, conn=eigene)
    fall = lade_fall(name)
    stellen = stellen_finden(fall, conn=conn)
    vollstaendig = [s for s in stellen if s.name and s.belegt and s.quelle and s.seite is not None]
    adressen = [s for s in stellen if s.adresse is not None]
    unbelegt = [
        s.id
        for s in adressen
        if s.abschnitt_id is None or not adresse_belegt(s.adresse, _quelltext(conn, s.abschnitt_id))
    ]
    pruefungen: list[dict[str, Any]] = [
        {
            "name": "mindestens 1 Stelle mit Name, Adresse, Quelle, Seite",
            "ok": len(vollstaendig) >= 1,
            "wert": len(vollstaendig),
        },
        {
            "name": "jede ausgegebene Adresse ist Teilstring der Quelle",
            "ok": not unbelegt and bool(adressen),
            "wert": f"{len(adressen) - len(unbelegt)}/{len(adressen)}",
        },
        {"name": "0 unbelegte Adressen", "ok": not unbelegt, "wert": len(unbelegt)},
    ]
    stelle = stelle_fuer_termin(stellen, str(fall["anliegen"]))
    bericht: dict[str, Any] = {}
    if stelle is not None:
        pfad = termin_entwurf(fall, stelle, wunsch=fall["wunsch"])
        bericht = parse_ics(pfad.read_bytes().decode("utf-8"))  # read_text wandelt CRLF um
        ev = bericht["events"][0] if bericht["events"] else {}
        with tempfile.TemporaryDirectory() as tmp:
            zweiter = termin_entwurf(fall, stelle, wunsch=fall["wunsch"], ziel=Path(tmp) / "zweiter.ics")
            gleich = zweiter.read_bytes() == pfad.read_bytes()
        pruefungen += [
            {
                "name": "genau 1 VEVENT",
                "ok": bericht["vevents"] == 1 and bericht["ausgeglichen"],
                "wert": bericht["vevents"],
            },
            {"name": "STATUS:TENTATIVE", "ok": ev.get("STATUS") == "TENTATIVE", "wert": ev.get("STATUS")},
            {
                "name": "SUMMARY Terminentwurf",
                "ok": ev.get("SUMMARY") == "Terminentwurf",
                "wert": ev.get("SUMMARY"),
            },
            {
                "name": "DESCRIPTION enthält „nicht gebucht“",
                "ok": "nicht gebucht" in ev.get("DESCRIPTION", ""),
            },
            {
                "name": "LOCATION ist belegte Adresse",
                "ok": ev.get("LOCATION") == stelle.adresse
                and stelle.abschnitt_id is not None
                and adresse_belegt(ev.get("LOCATION"), _quelltext(conn, stelle.abschnitt_id)),
                "wert": ev.get("LOCATION"),
            },
            {
                "name": "Wunschdatum aus dem Fixture",
                "ok": ev.get("DTSTART", "").startswith(str(fall["wunsch"]["datum"]).replace("-", "")),
                "wert": ev.get("DTSTART"),
            },
            {
                "name": "Checkliste: Unterlagen, Nähe, Zeitpräferenz",
                "ok": all(
                    f"{k}:" in ev.get("DESCRIPTION", "") for k in ("Unterlagen", "Nähe", "Zeitpräferenz")
                ),
            },
            {
                "name": "kein freier Termin behauptet (ICS)",
                "ok": not behauptet_termin(ev.get("DESCRIPTION", "")),
            },
            {
                "name": "Zeilen RFC 5545 (≤ 75 Oktette, CRLF)",
                "ok": bericht["zeilen_zu_lang"] == 0 and bericht["nur_crlf"],
            },
            {"name": "deterministisch (zwei Läufe byte-gleich)", "ok": gleich},
        ]
    else:
        pruefungen.append({"name": "Terminentwurf zu belegter Stelle", "ok": False, "wert": None})
    dialoge = dialoge_aufzeichnen(fall, stellen)
    for d in dialoge:
        pruefungen.append(
            {
                "name": f"Dialog {d['id']}: {d['erwartet_rueckfragen_zeitpraeferenz']} Rückfrage(n) zur Zeit",
                "ok": d["rueckfragen_zeitpraeferenz"] == d["erwartet_rueckfragen_zeitpraeferenz"]
                and not d["freier_termin_behauptet"]
                and d["ergebnis"].get("gebucht") is False,
                "wert": d["rueckfragen_zeitpraeferenz"],
            }
        )
    return {
        "fall": name,
        "ok": all(p["ok"] for p in pruefungen),
        "pruefungen": pruefungen,
        "stellen": [s.als_dict() for s in stellen],
        "ics": {k: v for k, v in bericht.items() if k != "events"},
    }


# --------------------------------------------------------------------------------------------------------
# CLI


def _fall_ausgabe(name: str) -> dict[str, Any]:
    fall = lade_fall(name)
    with verbinde() as conn:
        stellen = stellen_finden(fall, conn=conn)
    stelle = stelle_fuer_termin(stellen, str(fall["anliegen"]))
    pfad = termin_entwurf(fall, stelle, wunsch=fall["wunsch"]) if stelle is not None else None
    return {
        "fall": name,
        "stellen": [s.als_dict() for s in stellen],
        "termin": {
            "datei": str(pfad.relative_to(PAKET_DIR)) if pfad else None,
            "stelle": stelle.id if stelle else None,
            "gebucht": False,
            "checkliste": checkliste(fall, stelle, fall["wunsch"]) if stelle else {},
        },
        "rueckfrage": naechste_rueckfrage({"angaben": fall.get("angaben", {})}),
    }


def _drucke_fall(daten: Mapping[str, Any]) -> None:
    print(f"Fall {daten['fall']}: {len(daten['stellen'])} Stellen")
    for s in daten["stellen"]:
        zust = f" [zuständig: {s['zustaendig']}]" if s["zustaendig"] else ""
        print(f"- {s['name']}{zust}\n  Adresse: {s['adresse']}\n  Quelle: {s['quelle']}, S. {s['seite']}")
    t = daten["termin"]
    print(f"Terminentwurf (nicht gebucht): {t['datei'] or nicht_belegt()}")


def cli(argv: Sequence[str]) -> int:
    p = argparse.ArgumentParser(
        prog="lotse termin", description="Stelle und Terminentwurf (nichts wird gebucht)"
    )
    gruppe = p.add_mutually_exclusive_group(required=True)
    gruppe.add_argument("--fall", help="Fixture eval/<fall>.json: Stellen finden und ICS schreiben")
    gruppe.add_argument("--pruefen", metavar="FALL", help="AC aus #81 prüfen; Exit 1, wenn eine fehlschlägt")
    gruppe.add_argument("--aufzeichnen", metavar="FALL", help="Dialogfälle nach eval/termin-dialoge.json")
    p.add_argument("--json", action="store_true", help="Ausgabe als JSON")
    a = p.parse_args(list(argv))
    if a.fall:
        daten = _fall_ausgabe(a.fall)
        if a.json:
            print(json.dumps(daten, ensure_ascii=False, indent=2))
        else:
            _drucke_fall(daten)
        return 0
    if a.aufzeichnen:
        fall = lade_fall(a.aufzeichnen)
        with verbinde() as conn:
            stellen = stellen_finden(fall, conn=conn)
        inhalt = {"fall": a.aufzeichnen, "issue": 81, "dialoge": dialoge_aufzeichnen(fall, stellen)}
        DIALOGE_DATEI.write_text(json.dumps(inhalt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"geschrieben: {DIALOGE_DATEI.relative_to(PAKET_DIR)}")
        return 0
    ergebnis = pruefen(a.pruefen)
    if a.json:
        print(json.dumps(ergebnis, ensure_ascii=False, indent=2))
    else:
        for pr in ergebnis["pruefungen"]:
            wert = f" ({pr['wert']})" if pr.get("wert") is not None else ""
            print(f"{'OK  ' if pr['ok'] else 'FEHL'} {pr['name']}{wert}")
        print("ERGEBNIS:", "bestanden" if ergebnis["ok"] else "nicht bestanden")
    return 0 if ergebnis["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(cli(sys.argv[1:]))
