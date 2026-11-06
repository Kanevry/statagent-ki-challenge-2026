"""Tiefe Klassifikationscodes in einer Datenanfrage (#189): ÖNACE unter dem Abschnitt, Bezirk, Gemeinde.

Die Statistik zählt nach Abschnitt und Bundesland. Ein tieferer Code lässt sich deshalb erklären, aber nicht
zählen: Eine Erklär-Frage bekommt Name, Ebene, Pfad, Gültigkeit und Übergänge aus ``statagent.klass``, eine
Zahlen-Frage eine klare Absage mit dem passenden Abschnitt oder Bundesland als Hinweis. Abschnitte und alles
andere liefern None und bleiben beim bisherigen Weg in ``statagent.frage``.

Nur lesend, alle Namen und Codes aus der Datenbank. Importiert ``plattform.llm`` nicht (R2). ``statagent.frage``
importiert dieses Modul erst beim Aufruf, darum darf es umgekehrt von dort importieren.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from typing import Any

import psycopg
from psycopg import sql

from statagent import klass
from statagent.agenten.werkzeuge import AbfrageVerweigert
from statagent.db import Verbindung
from statagent.frage import (
    _BUNDESLAND,
    _DEFINITION,
    _FLUKTUATION,
    _GESCHLECHT,
    _ZEITREIHE,
    NICHT_LESBAR,
    UC,
    _Abgeschnitten,
    _antwort,
    _lesen,
    _treffer,
    fragetyp,
    jahr_ohne_monat,
    monate_lesen,
    nicht_auswertbar,
)
from statagent.zeitraum import MONATSNAMEN, monat_anzeige

OENACE, BEZIRK, GEMEINDE = "oenace", "bezirk", "gemeinde"
#: So viele Stände und Übergänge nennt eine Antwort, der Rest steht als „und N weitere“ da.
HOECHSTENS = 3
ZAEHLT_TIEFER_NICHT = "Die Statistik zählt nach Abschnitt und Bundesland, nicht tiefer."

#: Hinter einem Code steht keine weitere Ziffer: „10.11.2025“ und „10/2025“ sind Daten, „C 10.11.“ ein Satzende.
_ENDE = r"(?![\w%]|[.,/-]\d)"
#: „10 Personen“ ist eine Menge, auch mit Buchstabe oder ÖNACE davor.
_KEINE_MENGE = r"(?!\s*%)(?!\s*(?:prozent|personen|leute|menschen|mal|euro|jahre|jahren|monate|monaten|tage|tagen|uhr)\b)"
_MIT_PUNKT = r"\d{2}(?:\.\d(?!\d)|\.\d{2}(?:-\d)?)"
_NUMMER = rf"(?:{_MIT_PUNKT}|\d{{2}})"
#: Nach dem Wort ÖNACE ist auch das Dezimalkomma gemeint: „ÖNACE C 10,11“.
_NUMMER_WORT = r"(?:\d{2}(?:[.,]\d(?!\d)|[.,]\d{2}(?:-\d)?)|\d{2})"
#: Kein Code hinter „ÖNACE C“: Jahr, Datum, Monat und Jahr, Tag und Monatsname.
_KEIN_DATUM = (
    r"(?!(?:19|20)\d{2}(?!\d))(?!\d{1,2}[./]\d{1,2}[./]\d{2,4})(?!\d{1,2}[./](?:19|20)\d{2})"
    r"(?!\d{1,2}\.?\s*(?:jän|jaen|jan|feb|mär|maer|mrz|apr|mai|jun|jul|aug|sep|okt|nov|dez))"
)
_OENACE_CODE = re.compile(
    # Nach dem Wort darf die Zahl allein stehen („oenace 10.11“), auch mit Fassung („ÖNACE 2025 C 10“).
    r"(?<!\w)(?:önace|oenace|nace)(?:[\s-]+(?:19|20)\d{2})?[\s:-]*"
    r"(?:(?:abschnitt|abteilung|gruppe|klasse|unterklasse|code|kode)[\s:-]*)?"
    rf"(?P<buchstabe_1>[a-z]?)[\s-]*(?P<nummer_1>{_NUMMER_WORT}){_ENDE}{_KEINE_MENGE}"
    # Nach „ÖNACE C“ ist jede andere Ziffernfolge ein Code, den es nicht gibt („C 1“, „C 101“), nie still Abschnitt C.
    r"|(?<!\w)(?:önace|oenace|nace)(?:[\s-]+(?:19|20)\d{2})?[\s:-]*"
    rf"(?P<buchstabe_5>[a-z])[\s-]*{_KEIN_DATUM}(?P<nummer_5>\d+(?:[.,-]\d+)*){_ENDE}{_KEINE_MENGE}"
    # Ohne das Wort braucht die Zahl einen Buchstaben davor; ohne Leerzeichen nur mit Punkt, denn E07, A13 und R10
    # sind hier Regeln, Annahmen und Rückfragen ...
    rf"|(?<![\w.,/-])(?P<buchstabe_2>[a-z])(?:\s(?P<nummer_2>{_NUMMER})|(?P<nummer_4>{_MIT_PUNKT})){_ENDE}{_KEINE_MENGE}"
    # ... oder die Endung einer Unterklasse.
    rf"|(?<![\w.,/-])(?P<nummer_3>\d{{2}}\.\d{{2}}-\d){_ENDE}",
    re.IGNORECASE,
)
_CODE_WORT = r"(?:[\s-]*(?:code|kennziffer|kennzahl|nummer|nr\.?))?[\s:-]*"
_REGION_CODE = re.compile(
    rf"(?<!\w)gemeinde{_CODE_WORT}(?P<gemeinde>\d{{5}}){_ENDE}"
    rf"|(?<!\w)bezirks?{_CODE_WORT}(?P<bezirk>\d{{3}}){_ENDE}",
    re.IGNORECASE,
)
#: Wörter, die nach einer Zahl fragen. Eine Erklärung nennt nie eine Zahl, ein Fehlgriff hier kostet also wenig.
_ZAHLEN_FRAGE = re.compile(
    r"beschäftig|beschaeftig|verhältnis|verhaeltnis|wie\s*viele?\b|\banzahl\b|\bzahl(?:en)?\b|\bbestand\b"
    r"|durchschnitt|\bpersonen\b|\bleute\b|\bmenschen\b|\bjobs?\b|\bstellen\b"
    r"|\barbeit(?:er|erinnen|nehmer|nehmerinnen|ende|enden|skräfte|splätze)\b"
)


@dataclass(frozen=True)
class TieferCode:
    """Ein Code aus der Frage. ``code`` wie in der Datenbank, bei ÖNACE ohne Buchstabe nur die Nummer."""

    art: str
    code: str
    von: int = field(default=0, compare=False)
    bis: int = field(default=0, compare=False)


@dataclass
class _Befund:
    """Was die Datenbank zu einem Code weiß. Ohne ``daten``: Code unbekannt oder Ebene nicht geladen."""

    tief: TieferCode
    belege: list[dict[str, Any]]
    daten: dict[str, Any] | None = None
    geladen: bool = True
    mehrdeutig: str | None = None
    abschnitt: dict[str, Any] | None = None


def codes_erkennen(frage: str) -> list[TieferCode]:
    """Alle tiefen Codes der Frage in Lesereihenfolge, ohne Doppelte. Reine Funktion ohne Datenbank."""
    text = unicodedata.normalize("NFC", frage)
    gefunden: list[TieferCode] = []
    for treffer in _OENACE_CODE.finditer(text):
        werte = treffer.groupdict()
        nummer = (
            werte["nummer_1"]
            or werte["nummer_2"]
            or werte["nummer_3"]
            or werte["nummer_4"]
            or werte["nummer_5"]
        ).replace(",", ".")
        buchstabe = (werte["buchstabe_1"] or werte["buchstabe_2"] or werte["buchstabe_5"] or "").upper()
        code = f"{buchstabe} {nummer}" if buchstabe else nummer
        gefunden.append(TieferCode(OENACE, code, treffer.start(), treffer.end()))
    for treffer in _REGION_CODE.finditer(text):
        art = GEMEINDE if treffer.group(GEMEINDE) else BEZIRK
        gefunden.append(TieferCode(art, treffer.group(art), treffer.start(), treffer.end()))
    gefunden.sort(key=lambda c: c.von)
    return list(dict.fromkeys(gefunden))


def _ohne_codes(frage: str, codes: list[TieferCode]) -> str:
    """Die Frage ohne die Codes; ein Code selbst ist weder Kennung noch Merkmal."""
    text = unicodedata.normalize("NFC", frage)
    teile = []
    start = 0
    for code in codes:
        teile.append(text[start : code.von])
        start = code.bis
    return " ".join([*teile, text[start:]])


_EINORDNUNG = re.compile(r"zu welche[mr]|gehört|gehoert|was bedeutet|was heißt|was heisst|was ist|was war")
#: Ohne das Wort ÖNACE und ohne Punkt können „E 07“, „A 13“, „R 10“ und „U 25“ auch Regeln, Annahmen oder Alter sein.
_ÖNACE_WORT = re.compile(r"(?i)(?<!\w)(?:önace|oenace|nace)(?!\w)")


def _fragt_nach_zahl(frage: str, rest: str) -> bool:
    text = frage.lower()
    if _ZAHLEN_FRAGE.search(text):
        return True
    # „Zu welchem Bundesland gehört der Bezirk 701?“ fragt nach der Einordnung, nicht nach einer Zahl.
    if _EINORDNUNG.search(text):
        return False
    if any(m.search(text) for m in (_FLUKTUATION, _GESCHLECHT, _BUNDESLAND, _ZEITREIHE)):
        return True
    if _DEFINITION.search(text):
        return False
    return bool(monate_lesen(rest)) or jahr_ohne_monat(rest) is not None


def tiefer_code_antwort(conn: Verbindung, frage: str) -> dict[str, Any] | None:
    """Fertige Antwort, wenn die Frage einen tiefen Code nennt; sonst None (bisheriger Weg). Wirft nie."""
    if _LISTEN_FRAGE.search(frage):
        try:
            liste = _liste_antwort(conn, frage)
        except (psycopg.Error, AbfrageVerweigert, _Abgeschnitten):
            return _antwort("definition", NICHT_LESBAR, hinweise=[NICHT_LESBAR])
        if liste is not None:
            return liste
    codes = codes_erkennen(frage)
    if not codes:
        return None
    rest = _ohne_codes(frage, codes)
    typ = fragetyp(frage)
    # Einzeldaten und Merkmale, die es nicht gibt, sagt die Frage selbst ab; der Code ändert daran nichts.
    # Durchschnitte sind hier ausgenommen, die fallen unten unter die Absage „zählt nicht tiefer“.
    absage = nicht_auswertbar(rest, mittel=True)
    if absage is not None:
        return _antwort(typ, absage, hinweise=[absage])
    try:
        befunde = [_nachsehen(conn, c) for c in codes]
    except (psycopg.Error, AbfrageVerweigert, _Abgeschnitten):
        return _antwort(typ, NICHT_LESBAR, hinweise=[NICHT_LESBAR])
    if not _ÖNACE_WORT.search(frage):
        befunde = [
            b
            for b in befunde
            if b.tief.art != OENACE or "." in b.tief.code or b.daten is not None or b.mehrdeutig
        ]
        if not befunde:
            return None
    if _fragt_nach_zahl(frage, rest):
        text = _absage_text(befunde, monate_lesen(rest))
        belege = [b for befund in befunde for b in befund.belege]
        return _antwort(typ, text, hinweise=[text], belege=belege)
    return _erklaerung(befunde)


# --- Welche Bezirke hat Tirol? ---------------------------------------------------------------------------------

#: „Welche Bezirke hat Tirol?“, „Wie viele Gemeinden hat der Bezirk Weiz?“: eine Frage nach der Liste, nicht nach Personen.
_LISTEN_FRAGE = re.compile(r"(?i)(?<!\w)(welche|wie\s*viele)\s+(bezirke|gemeinden)(?!\w)")
_JAHR = re.compile(r"(?<!\d)((?:19|20)\d{2})(?!\d)")
#: Eine Frage nach Beschäftigten oder einem Vergleich ist keine Frage nach der Liste; sie nimmt den normalen Weg.
_KEINE_LISTE = re.compile(
    r"(?i)beschäftig|beschaeftig|personen|menschen|leute|verhältnis|verhaeltnis|meisten|wenigsten|mehr als|weniger als"
)
#: Füllwörter einer Listenfrage; was danach übrig bleibt, ist ein Ort, den die Antwort kennen muss.
_FUELLWOERTER = frozenset(
    [
        "welche",
        "wie",
        "viele",
        "bezirke",
        "gemeinden",
        "hat",
        "haben",
        "hatte",
        "hatten",
        "gibt",
        "gab",
        "es",
        "in",
        "im",
        "am",
        "der",
        "die",
        "das",
        "den",
        "dem",
        "des",
        "von",
        "vom",
        "bezirk",
        "bundesland",
        "österreich",
        "oesterreich",
        "insgesamt",
        "stand",
        "jahr",
        "heute",
        "derzeit",
        "aktuell",
        "jetzt",
        "ganz",
        "zum",
        "zur",
        "denn",
        "alle",
        "sind",
        "waren",
    ]
)
#: So viele Gemeinden nennt eine Antwort einzeln, der Rest steht als „und N weitere“ da.
LISTE_MAX = 40


def _liste_antwort(conn: Verbindung, frage: str) -> dict[str, Any] | None:
    treffer = _LISTEN_FRAGE.search(frage)
    if not treffer:
        return None
    if _KEINE_LISTE.search(frage):
        return None
    was = treffer.group(2).lower()
    text = frage.lower()
    quelle = "stat.klass_region"
    staende = [str(z["version"]) for z in _lesen(
        conn,
        "SELECT DISTINCT version FROM stat.klass_region WHERE ebene = 'gemeinde' ORDER BY version",
    )]  # fmt: skip
    if not staende:
        satz = (
            f"Die {was.capitalize()} sind in dieser Fassung nicht dabei. Die Statistik zählt nach Bundesland."
        )
        return _antwort("definition", satz, hinweise=[satz])
    jahr = _JAHR.search(frage)
    stand = staende[-1]
    if jahr:
        gesucht = f"{jahr.group(1)}-01-01"
        if gesucht not in staende:
            satz = (
                f"Einen Stand für {jahr.group(1)} gibt es nicht. "
                f"Es gibt die Stände von {_monat(staende[0])} bis {_monat(staende[-1])}."
            )
            return _antwort("definition", satz, hinweise=[satz])
        stand = gesucht
    ort = f"im Stand vom 1. {_monat(stand)}"
    klammer = f"(Stand 1. {_monat(stand)})"
    v = sql.Literal(stand)
    # Nur was die Antwort braucht: Alle Gemeinden auf einmal lägen über der Zeilengrenze von sql_lesen.
    bezirke_sql = (
        sql.SQL(
            # Nur Bezirke mit Gemeinden: Der Sammelcode 900 „Wien(Stadt)“ steht neben den 23 Wiener Bezirken, ohne eigene.
            "SELECT b.code, b.bezeichnung, b.uebergeordnet, count(g.code) AS gemeinden"
            " FROM stat.klass_region b JOIN stat.klass_region g"
            " ON g.version = b.version AND g.ebene = 'gemeinde' AND g.uebergeordnet = b.code"
            " WHERE b.version = {v} AND b.ebene = 'bezirk'"
            " GROUP BY b.code, b.bezeichnung, b.uebergeordnet ORDER BY b.code"
        )
        .format(v=v)
        .as_string(conn)
    )
    bezirke = _lesen(conn, bezirke_sql)
    bundeslaender = _lesen(
        conn, "SELECT code, bezeichnung FROM stat.klass_region WHERE ebene = 'bundesland' AND code <> '0'"
    )
    stand_angabe = [{"klassifikation": quelle, "version": stand}]

    def antwort(satz: str, definition: str, abfrage: str = bezirke_sql) -> dict[str, Any]:
        zaehlt = "Die Statistik zählt nach Bundesland, nicht tiefer."
        return _antwort(
            "definition",
            f"{satz} {zaehlt}",
            definition=definition,
            stand=stand_angabe,
            belege=[_beleg(quelle, abfrage, f"{quelle}/{stand}")],
        )

    bezirk: dict[str, Any] | None = None
    code = re.search(r"(?i)bezirk\w*\s+(\d{3})(?!\d)", frage)
    if code:
        bezirk = next((b for b in bezirke if b["code"] == code.group(1)), None)
        if bezirk is None:
            satz = f"Einen Bezirk mit dem Code {code.group(1)} gibt es {ort} nicht."
            return _antwort("definition", satz, hinweise=[satz])
    land = None
    if bezirk is None:
        land = next((b for b in bundeslaender if _treffer(text, str(b["bezeichnung"]))), None)
    if bezirk is None and (land is None or re.search(r"(?i)bezirk\s", frage)):
        # „Graz“ und „Graz (Stadt)“: der Name ohne Klammer genügt; längster Name zuerst, damit „Innsbruck-Land“ gewinnt.
        for b in sorted(bezirke, key=lambda z: len(str(z["bezeichnung"])), reverse=True):
            name = region_name(b["bezeichnung"])
            if _treffer(text, name) or _treffer(text, name.split(" (")[0]):
                bezirk = b
                break
    if bezirk is not None:
        name = region_name(bezirk["bezeichnung"])
        if was == "bezirke":
            land_name = next(
                (b["bezeichnung"] for b in bundeslaender if b["code"] == bezirk["uebergeordnet"]), ""
            )
            satz = f"{name} ({bezirk['code']}) ist selbst ein Bezirk und gehört zum Bundesland {land_name}."
            return antwort(satz, f"Bezirk {bezirk['code']}: {name}")
        gemeinden_sql = (
            sql.SQL(
                "SELECT code, bezeichnung FROM stat.klass_region"
                " WHERE version = {v} AND ebene = 'gemeinde' AND uebergeordnet = {b} ORDER BY code"
            )
            .format(v=v, b=sql.Literal(str(bezirk["code"])))
            .as_string(conn)
        )
        unter = _lesen(conn, gemeinden_sql)
        namen = [_genannt(region_name(g["bezeichnung"]), g["code"]) for g in unter[:LISTE_MAX]]
        rest = f" und {len(unter) - LISTE_MAX} weitere" if len(unter) > LISTE_MAX else ""
        anzahl = f"{len(unter)} Gemeinde" if len(unter) == 1 else f"{len(unter)} Gemeinden"
        satz = f"Der Bezirk {name} ({bezirk['code']}) hat {anzahl} {klammer}: {', '.join(namen)}{rest}."
        return antwort(satz, f"Gemeinden im Bezirk {bezirk['code']}: {len(unter)}", gemeinden_sql)
    if land is not None:
        unter_bezirke = [b for b in bezirke if b["uebergeordnet"] == land["code"]]
        name = f"Das Bundesland {land['bezeichnung']}"
        anzahl_g = sum(int(b["gemeinden"]) for b in unter_bezirke)
        # Wien: Jeder Gemeindebezirk ist in der Quelle zugleich Bezirk und Gemeinde.
        gleich = " Dort zählt jeder Bezirk als eine Gemeinde." if anzahl_g == len(unter_bezirke) else ""
        if was == "bezirke":
            namen = [_genannt(region_name(b["bezeichnung"]), b["code"]) for b in unter_bezirke]
            anzahl = (
                f"{len(unter_bezirke)} Bezirk" if len(unter_bezirke) == 1 else f"{len(unter_bezirke)} Bezirke"
            )
            satz = f"{name} hat {anzahl} {klammer}: {', '.join(namen)}.{gleich}"
            return antwort(satz, f"Bezirke in {land['bezeichnung']}: {len(unter_bezirke)}")
        satz = f"{name} hat {klass._deutsch(anzahl_g)} Gemeinden {klammer}.{gleich} Alle stehen auf der Seite Klassifikationen."
        return antwort(satz, f"Gemeinden in {land['bezeichnung']}: {klass._deutsch(anzahl_g)}")
    # Bleibt ein Wort übrig, ist ein Ort gemeint, den es nicht gibt: nicht still die Summe von Österreich nennen.
    woerter = re.findall(r"[^\W\d_][\w.-]*", frage)
    unbekannt = [w for w in woerter if w.lower() not in _FUELLWOERTER and w.lower() not in MONATSNAMEN]
    if unbekannt:
        ort_wort = " ".join(unbekannt)
        satz = (
            f"„{ort_wort}“ kenne ich nicht als Bundesland oder Bezirk. "
            "Fragen Sie zum Beispiel: „Welche Bezirke hat Tirol?“"
        )
        return _antwort("definition", satz, hinweise=[satz])
    anzahl_alle = sum(int(b["gemeinden"]) for b in bezirke)
    satz = (
        f"Österreich hat {len(bezirke)} Bezirke und {klass._deutsch(anzahl_alle)} Gemeinden {klammer}. "
        "Wien zählt dabei mit seinen Gemeindebezirken. Alle stehen auf der Seite Klassifikationen."
    )
    return antwort(satz, f"Österreich: {len(bezirke)} Bezirke, {klass._deutsch(anzahl_alle)} Gemeinden")


# --- Datenbank ------------------------------------------------------------------------------------------------


def _tabelle(tief: TieferCode) -> str:
    return "klass_oenace" if tief.art == OENACE else "klass_region"


def _beleg(quelle: str, sql_text: str, ref: str) -> dict[str, Any]:
    return {"uc": UC, "quelle": quelle, "sql": sql_text, "ref": ref}


def _suche_sql(conn: Verbindung, tief: TieferCode) -> str:
    """Dieselbe Zuordnung wie ``klass._bezeichnungen``: ÖNACE ohne Buchstabe sucht nur die Nummer."""
    bedingung = (
        "split_part(code, ' ', 2) = {c}" if tief.art == OENACE and tief.code[0].isdigit() else "code = {c}"
    )
    return (
        sql.SQL(
            "SELECT version, code, bezeichnung, ebene, uebergeordnet, gueltig_von, gueltig_bis FROM stat."
            + _tabelle(tief)
            + " WHERE "
            + bedingung
            + " ORDER BY gueltig_von, version"
        )
        .format(c=sql.Literal(tief.code))
        .as_string(conn)
    )


def _ebene_sql(tief: TieferCode) -> str:
    if tief.art == OENACE:
        return "SELECT count(*) AS n FROM stat.klass_oenace WHERE version IN ('2008', '2025') AND ebene >= 2"
    return f"SELECT count(*) AS n FROM stat.klass_region WHERE ebene = '{tief.art}'"


def _nachsehen(conn: Verbindung, tief: TieferCode) -> _Befund:
    quelle = f"stat.{_tabelle(tief)}"
    suche = _suche_sql(conn, tief)
    beleg = _beleg(quelle, suche, f"{quelle}/{tief.code}")
    if _lesen(conn, suche):
        try:
            daten = klass.erklaeren(conn, tief.art if tief.art == OENACE else "region", tief.code)
        except klass.KlassFehler as fehler:  # den Code gibt es, also bleibt nur: nicht eindeutig
            return _Befund(tief, [beleg], mehrdeutig=str(fehler))
        belege = [beleg]
        # Über der Unterklasse nennt die Antwort keine Übergänge, also auch kein Beleg dafür.
        if daten.get("uebergaenge_gesamt") and (tief.art != OENACE or daten["ebene"] == "5"):
            belege.append(_uebergang_beleg(conn, tief, daten))
        return _Befund(tief, belege, daten=daten)
    ebene = _ebene_sql(tief)
    belege = [beleg, _beleg(quelle, ebene, quelle)]
    if int(_lesen(conn, ebene)[0]["n"]) > 0:
        return _Befund(tief, belege)
    return _Befund(tief, belege, geladen=False, abschnitt=_abschnitt_lesen(conn, tief, belege))


def _abschnitt_lesen(
    conn: Verbindung, tief: TieferCode, belege: list[dict[str, Any]]
) -> dict[str, Any] | None:
    """Der Abschnitt zum Buchstaben des Codes, wenn die Ebenen darunter nicht geladen sind."""
    if tief.art != OENACE or tief.code[0].isdigit():
        return None
    buchstabe = tief.code[0]
    abfrage = (
        sql.SQL(
            "SELECT version, code, bezeichnung FROM stat.klass_oenace WHERE ebene = 1 AND code = {}"
            " ORDER BY gueltig_von DESC"
        )
        .format(sql.Literal(buchstabe))
        .as_string(conn)
    )
    zeilen = _lesen(conn, abfrage)
    if not zeilen:
        return None
    belege.append(_beleg("stat.klass_oenace", abfrage, f"stat.klass_oenace/{buchstabe}"))
    return zeilen[0]


def _uebergang_beleg(conn: Verbindung, tief: TieferCode, daten: dict[str, Any]) -> dict[str, Any]:
    """Abfrage mit denselben Zeilen wie ``klass._uebergaenge_tief``, die Antwort zeigt nur die ersten davon."""
    praefix = tief.art == OENACE and daten["ebene"] != "5"
    seiten = []
    for zeile in daten["bezeichnungen"]:
        version = sql.Literal(str(zeile["version"]))
        muster = sql.Literal(str(zeile["code"]) + ("%" if praefix else ""))
        seiten.append(
            sql.SQL(
                "(version_alt = {v} AND code_alt LIKE {m}) OR (version_neu = {v} AND code_neu LIKE {m})"
            ).format(v=version, m=muster)
        )
    sql_text = (
        sql.SQL(
            "SELECT version_alt, code_alt, version_neu, code_neu, beziehung, gueltig_ab, quelle"
            " FROM stat.uebergang WHERE klassifikation = {k} AND ({s})"
            " ORDER BY gueltig_ab, version_alt, code_alt, code_neu"
        )
        .format(k=sql.Literal(daten["uebergang_klassifikation"]), s=sql.SQL(" OR ").join(seiten))
        .as_string(conn)
    )
    return _beleg(
        "stat.uebergang", sql_text, f"stat.uebergang/{daten['uebergang_klassifikation']}/{tief.code}"
    )


# --- Texte ----------------------------------------------------------------------------------------------------


def _nicht_geladen_text(tief: TieferCode) -> str:
    was = (
        "Die Ebenen unter dem ÖNACE-Abschnitt sind"
        if tief.art == OENACE
        else f"Die {klass.ebene_name(tief.art, mehrzahl=True)} sind"
    )
    return f"{was} in dieser Fassung nicht dabei. Den Code {tief.code} kann StatAgent darum nicht prüfen."


def _unbekannt_text(tief: TieferCode) -> str:
    if tief.art == OENACE:
        return f"Den Code {tief.code} gibt es in der ÖNACE nicht."
    if tief.art == GEMEINDE:
        return f"Eine Gemeinde mit dem Code {tief.code} gibt es nicht."
    return f"Einen Bezirk mit dem Code {tief.code} gibt es nicht."


def region_name(name: object) -> str:
    """„Graz(Stadt)“ und „Wien  1.,Innere Stadt“ aus der Quelle lesbar; wie die Webseite (regionName)."""
    text = re.sub(r"\s*\(", " (", str(name))
    text = re.sub(r",\s*", ", ", text)
    return re.sub(r"\s+", " ", text).strip()


def _monat(wert: object) -> str:
    return monat_anzeige(str(wert)[:7])


def _liste(teile: list[str], rest: str = "weitere") -> str:
    """Höchstens drei Namen; ``rest`` nach dem Fall im Satz: „auf … und 2 weitere“, „aus … und 2 weiteren“."""
    gezeigt = ", ".join(teile[:HOECHSTENS])
    return f"{gezeigt} und {len(teile) - HOECHSTENS} {rest}" if len(teile) > HOECHSTENS else gezeigt


def _genannt(name: object, code: object) -> str:
    return f"{name} ({code})" if name else f"({code})"


def _oenace_uebergaenge(tief: TieferCode, daten: dict[str, Any]) -> list[str]:
    """Nur was sich ändert: Bleibt der Code gleich und allein, ist nichts zu sagen. Darüber nur bei der Unterklasse."""
    if daten["ebene"] != "5":
        return []
    code = daten["code"]
    ziele = [u for u in daten["uebergaenge"] if u["code_alt"] == code]
    quellen = [u for u in daten["uebergaenge"] if u["code_neu"] == code]
    saetze = []
    if len(ziele) > 1:
        namen = _liste([_genannt(u["bezeichnung_neu"], u["code_neu"]) for u in ziele])
        saetze.append(f"Ab ÖNACE {ziele[0]['version_neu']} ist er aufgeteilt auf {namen}.")
    elif ziele and ziele[0]["code_neu"] != code:
        neu = _genannt(ziele[0]["bezeichnung_neu"], ziele[0]["code_neu"])
        saetze.append(f"Ab ÖNACE {ziele[0]['version_neu']} heißt der Code {neu}.")
    if len(quellen) > 1:
        namen = _liste([_genannt(u["bezeichnung_alt"], u["code_alt"]) for u in quellen])
        saetze.append(f"In ÖNACE {quellen[0]['version_alt']} waren das {namen}.")
    elif quellen and quellen[0]["code_alt"] != code:
        alt = _genannt(quellen[0]["bezeichnung_alt"], quellen[0]["code_alt"])
        saetze.append(f"In ÖNACE {quellen[0]['version_alt']} war das {alt}.")
    return saetze


def _umbenennungen(zeilen: list[dict[str, Any]], code: object) -> list[dict[str, Any]]:
    """Übergänge, bei denen der Code bleibt und nur der Name wechselt."""
    return [
        u
        for u in zeilen
        if u["code_alt"] == u["code_neu"] == code
        and u["bezeichnung_alt"]
        and u["bezeichnung_neu"] not in (None, u["bezeichnung_alt"])
    ]


def _region_uebergaenge(daten: dict[str, Any], wer: str, jetzt: bool) -> list[str]:
    """Zusammenlegung, Teilung und neuer Code; ein neuer Name steht schon bei den Zeiträumen."""
    code = daten["code"]
    je_datum: dict[object, list[dict[str, Any]]] = {}
    for u in daten["uebergaenge"]:
        je_datum.setdefault(u["gueltig_ab"], []).append(u)
    umbenannt = _umbenennungen(daten["uebergaenge"], code)
    # „Seit … heißt … so“ stimmt nur für die letzte Umbenennung eines Codes, den es noch gibt.
    letzte = max(umbenannt, key=lambda u: str(u["gueltig_ab"])) if umbenannt and jetzt else None
    saetze = []
    for ab in sorted(je_datum, key=str):
        gruppe = je_datum[ab]
        datum = _monat(ab)
        herein = [u for u in gruppe if u["code_neu"] == code and u["code_alt"] != code]
        hinaus = [u for u in gruppe if u["code_alt"] == code and u["code_neu"] != code]
        for u in _umbenennungen(gruppe, code):
            alt, neu = region_name(u["bezeichnung_alt"]), region_name(u["bezeichnung_neu"])
            saetze.append(
                f"Seit {datum} heißt {wer} so, davor „{alt}“."
                if u is letzte
                else f"Ab {datum} hieß {wer} „{neu}“, davor „{alt}“."
            )
        if len(herein) > 1:
            namen = _liste(
                [_genannt(region_name(u["bezeichnung_alt"]), u["code_alt"]) for u in herein], "weiteren"
            )
            saetze.append(f"Seit {datum} zusammengelegt aus {namen}.")
        elif herein:
            u = herein[0]
            davor = (
                f"({u['code_alt']})"
                if u["bezeichnung_alt"] == u["bezeichnung_neu"]
                else _genannt(region_name(u["bezeichnung_alt"]), u["code_alt"])
            )
            saetze.append(f"Seit {datum} mit diesem Code, davor {davor}.")
        if len(hinaus) > 1:
            namen = _liste([_genannt(region_name(u["bezeichnung_neu"]), u["code_neu"]) for u in hinaus])
            saetze.append(f"Ab {datum} aufgeteilt auf {namen}.")
        elif hinaus:
            u = hinaus[0]
            saetze.append(
                f"Ab {datum} mit neuem Code ({u['code_neu']})."
                if u["bezeichnung_alt"] == u["bezeichnung_neu"]
                else f"Ab {datum} gehört das Gebiet zu {_genannt(region_name(u['bezeichnung_neu']), u['code_neu'])}."
            )
    return saetze


def _pfad_codes(pfad: list[dict[str, Any]]) -> tuple[str, ...]:
    return tuple(str(p["code"]) for p in pfad)


def _oben(pfad: list[dict[str, Any]]) -> str:
    """Nur die zwei obersten Ebenen: Klasse und Gruppe wiederholen fast immer denselben Namen."""
    je_ebene = {str(p["ebene"]): f"{p['bezeichnung']} ({p['code']})" for p in pfad}
    abschnitt, abteilung = je_ebene.get("1"), je_ebene.get("2")
    if abteilung and abschnitt:
        return f"zur Abteilung {abteilung}, Abschnitt {abschnitt}"
    return f"zum Abschnitt {abschnitt}" if abschnitt else f"zu: {klass._pfad_text(pfad)}"


def _oenace_text(tief: TieferCode, daten: dict[str, Any]) -> str:
    codes = " / ".join(str(c) for c in daten["codes"])
    namen = daten["bezeichnungen"]
    neueste = namen[-1]
    ebene = daten["ebene_name"]
    if len(namen) > 1:
        saetze = [f"Der Code {codes} ist eine {ebene} der ÖNACE und heißt „{neueste['bezeichnung']}“."]
        saetze += [
            f"In ÖNACE {n['version']} hieß er „{n['bezeichnung']}“."
            for n in namen[:-1]
            if n["bezeichnung"] != neueste["bezeichnung"]
        ]
    elif neueste["gueltig_bis"] is None:
        saetze = [
            f"Der Code {codes} ist eine {ebene} der ÖNACE {neueste['version']} und heißt "
            f"„{neueste['bezeichnung']}“. Es gibt ihn seit {_monat(neueste['gueltig_von'])}."
        ]
    else:
        saetze = [
            f"Der Code {codes} ist eine {ebene} der ÖNACE {neueste['version']} und hieß "
            f"„{neueste['bezeichnung']}“. Es gab ihn bis {_monat(neueste['gueltig_bis'])}."
        ]
    # Der Pfad nur einmal (jüngste Fassung), außer der Code wandert zwischen den Fassungen.
    je_pfad = {_pfad_codes(n["pfad"]): n for n in namen if n["pfad"]}
    for n in je_pfad.values():
        fassung = f"In ÖNACE {n['version']} gehört er" if len(je_pfad) > 1 else "Er gehört"
        saetze.append(f"{fassung} {_oben(n['pfad'])}.")
    saetze += _oenace_uebergaenge(tief, daten)
    saetze.append(f"Die Statistik zählt nach Abschnitt, nicht nach {ebene}.")
    return " ".join(saetze)


def _listen_zeit(von: Any, bis: Any) -> str:
    """Stände statt Kalender: Der Stand 1. Jänner 2024 gilt bis Jahresende, die Änderung kann mitten im Jahr liegen."""
    letzter = monat_anzeige(f"{bis.year:04d}-01")
    return f"von {_monat(von)} bis {letzter}" if von.year != bis.year else f"von {letzter}"


def _gezeigter_pfad(raum: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {**p, "bezeichnung": region_name(p["bezeichnung"])} for p in raum["pfad"] if p["ebene"] != "staat"
    ]


def _region_text(tief: TieferCode, daten: dict[str, Any]) -> str:
    gemeinde = tief.art == GEMEINDE
    ebene = klass.ebene_name(tief.art)
    pron = "sie" if gemeinde else "er"
    raeume = daten["zeitraeume"]
    letzter = raeume[-1]
    jetzt = letzter["gueltig_bis"] is None
    saetze = [
        f"Der Code {daten['code']} ist {'eine' if gemeinde else 'ein'} {ebene} und "
        f"{'heißt' if jetzt else 'hieß'} „{region_name(letzter['bezeichnung'])}“."
    ]
    pfad = _gezeigter_pfad(letzter)
    if pfad:
        saetze.append(f"{pron.capitalize()} {'gehört' if jetzt else 'gehörte'} zu: {klass._pfad_text(pfad)}.")
    aenderungen = _region_uebergaenge(daten, "die Gemeinde" if gemeinde else "der Bezirk", jetzt)
    seit = f"Seit {_monat(raeume[0]['gueltig_von'])} "
    if not jetzt:
        saetze.append(
            f"In den Listen stand der Code {_listen_zeit(raeume[0]['gueltig_von'], letzter['gueltig_bis'])}."
        )
    elif not any(a.startswith(seit) for a in aenderungen):  # sonst stünde dasselbe Datum zweimal da
        saetze.append(f"In den Listen steht der Code seit {_monat(raeume[0]['gueltig_von'])}.")
    # Frühere Zeiträume nur, wenn sie mehr sagen als die Umbenennung: Dann fehlt das Datum der Änderung nicht.
    alte_namen = {u["bezeichnung_alt"] for u in _umbenennungen(daten["uebergaenge"], daten["code"])}
    nachher_pfad = _pfad_codes(pfad)
    frueher: list[str] = []
    for r in reversed(raeume[:-1]):
        oben = _gezeigter_pfad(r)
        zu = f", {klass._pfad_text(oben)}" if oben and _pfad_codes(oben) != nachher_pfad else ""
        nachher_pfad = _pfad_codes(oben)
        if zu or r["bezeichnung"] not in alte_namen:
            frueher.insert(
                0,
                f"In den Listen {_listen_zeit(r['gueltig_von'], r['gueltig_bis'])}: "
                f"„{region_name(r['bezeichnung'])}“{zu}.",
            )
    teile = frueher[-(HOECHSTENS - 1) :]
    if len(frueher) > len(teile):
        teile.insert(0, f"Davor {len(frueher) - len(teile)} weitere Zeiträume.")
    saetze += teile
    saetze += aenderungen
    saetze.append(f"Die Statistik zählt nach Bundesland, nicht nach {ebene}.")
    return " ".join(saetze)


def _erklaerung(befunde: list[_Befund]) -> dict[str, Any]:
    texte: list[str] = []
    definitionen: list[str] = []
    stand: list[dict[str, Any]] = []
    for befund in befunde:
        tief, daten = befund.tief, befund.daten
        if daten is None:
            if befund.mehrdeutig:
                texte.append(befund.mehrdeutig)
            elif befund.geladen:
                texte.append(_unbekannt_text(tief))
            else:
                texte.append(_nicht_geladen_text(tief))
                if befund.abschnitt:
                    texte.append(
                        f"Den Abschnitt erklärt die Frage „Was ist ÖNACE {befund.abschnitt['code']}?“."
                    )
            continue
        namen = daten["bezeichnungen"]
        if tief.art == OENACE:
            texte.append(_oenace_text(tief, daten))
            definitionen += [f"ÖNACE {n['version']} {n['code']}: {n['bezeichnung']}" for n in namen]
        else:
            texte.append(_region_text(tief, daten))
            definitionen.append(
                f"{klass.ebene_name(tief.art)} {daten['code']}: {region_name(namen[-1]['bezeichnung'])}"
            )
        # Bei Regionen wären das bis zu 16 Stände: Der erste und der letzte sagen dasselbe.
        gezeigt = namen if tief.art == OENACE or len(namen) < 3 else [namen[0], namen[-1]]
        stand += [{"klassifikation": f"stat.{_tabelle(tief)}", "version": n["version"]} for n in gezeigt]
    return _antwort(
        "definition",
        " ".join(texte),
        definition="; ".join(definitionen) or None,
        stand=stand,
        belege=[b for befund in befunde for b in befund.belege],
    )


def _gilt_im_monat(zeile: dict[str, Any], monat: str) -> bool:
    von, bis = f"{zeile['gueltig_von']:%Y-%m}", zeile["gueltig_bis"]
    return von <= monat and (bis is None or monat <= f"{bis:%Y-%m}")


def _vorschlag(befund: _Befund, monat: str | None) -> tuple[str, str] | None:
    """Das, wonach die Statistik zählt: (Satz, wie es in einer Frage heißt)."""
    if befund.abschnitt:
        a = befund.abschnitt
        return (
            f"Der Buchstabe steht für den Abschnitt {a['bezeichnung']} ({a['code']}).",
            f"ÖNACE {a['code']}",
        )
    if befund.daten is None:
        return None
    namen = befund.daten["bezeichnungen"]
    im_monat = [n for n in namen if monat and _gilt_im_monat(n, monat)]
    zeile = (im_monat or namen)[-1]
    oenace = befund.tief.art == OENACE
    gesucht = "1" if oenace else "bundesland"
    oben = next((p for p in zeile["pfad"] if str(p["ebene"]) == gesucht), None)
    if oben is None:
        return None
    if oenace:
        return (
            f"Der Code gehört zum Abschnitt {oben['bezeichnung']} ({oben['code']}).",
            f"ÖNACE {oben['code']}",
        )
    return f"Der Code gehört zum Bundesland {oben['bezeichnung']} ({oben['code']}).", str(oben["bezeichnung"])


def _absage_text(befunde: list[_Befund], monate: list[str]) -> str:
    monat = monate[-1] if monate else None
    saetze = [ZAEHLT_TIEFER_NICHT]
    beispiel = None
    for befund in befunde:
        tief = befund.tief
        if befund.daten is None and not befund.mehrdeutig:
            saetze.append(_unbekannt_text(tief) if befund.geladen else _nicht_geladen_text(tief))
        else:
            saetze.append(f"Für den Code {tief.code} gibt es darum keine Zahl.")
        vorschlag = _vorschlag(befund, monat)
        if vorschlag is not None:
            saetze.append(vorschlag[0])
            beispiel = beispiel or vorschlag[1]
    if beispiel is not None:
        zeit = f" im {monat_anzeige(monat)}" if monat else ""
        saetze.append(f"Fragen Sie zum Beispiel: „Wie viele Beschäftigte gibt es in {beispiel}{zeit}?“")
    return " ".join(saetze)
