"""Qualitätsbericht je Berichtsmonat nach der Vorlage des Veranstalters (`qualitaetsbericht_vorlage.md`).

Alle Inhalte kommen aus der Datenbank (meta.lauf, meta.pruefung_treffer, meta.rueckfrage, meta.annahme,
meta.regel_wirkung, meta.revision). Der Bericht ist deterministisch: gleiche Datenbank, gleicher Bericht, Byte
für Byte. Es gibt keinen Zeitstempel „jetzt“; „erstellt am“ ist das Ende des Laufs (meta.lauf.beendet_am).

`bericht_daten` liefert den Bericht als Struktur (für `uc3 berichte --json` und die Weboberfläche),
`bericht_erzeugen` setzt daraus das Markdown. Nach außen einfache Sätze, die internen Meldungen
(meta.lauf.meldung) bleiben in der Datenbank.
"""

from __future__ import annotations

import re
from datetime import date, datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from statagent import ergebnis, konfig
from statagent.berichte.annahmen import annahmen
from statagent.db import Verbindung

ZEITZONE = ZoneInfo("Europe/Vienna")
#: Variable der Stichtagszählung in stat.stat_beschaeftigte (Name der Kennzahl, keine Zuordnungsregel).
STICHTAG_VARIABLE = "Beschaeftigungsverhaeltnisse"

#: Die fünf Abschnittsüberschriften der Vorlage, in dieser Reihenfolge.
ABSCHNITTE = (
    "## 1 Überblick",
    "## 2 Auffälligkeiten",
    "## 3 Rückfragen an die Fachabteilung",
    "## 4 Angewendete Regeln",
    "## 5 Revisionsbedarf früherer Monate",
)

#: Einstufungen der Vorlage (wörtlich) zu den Codes in meta.pruefung_treffer.einstufung.
EINSTUFUNGEN = {
    "erklaert-plausibel": "erklärt – plausibel",
    "erklaert-datenproblem": "erklärt – Datenproblem",
    "nicht-erklaerbar": "nicht erklärbar",
}
GUELTIGE_EINSTUFUNGEN = frozenset(EINSTUFUNGEN.values())

EBENEN = {"satz": "Satz", "aggregat": "Aggregat", "lieferung": "Lieferung"}
URSACHEN = {
    "nachmeldung": "Nachmeldung",
    "rueckwirkende_abmeldung": "rückwirkende Abmeldung",
    "nicht_mehr_enthalten": "nicht mehr enthalten",
    "merkmal_geaendert": "Merkmal geändert",
}
TYP_REIHENFOLGE = {"einlese": 1, "zuordnung": 2, "zaehl": 3}
BELEG_KURZ = 60
#: Gliederungen in meta.revision (ohne „insgesamt“), mit Namen für den Bericht.
GLIEDERUNGEN = {
    "region": "Bundesland",
    "geschlecht": "Geschlecht",
    "qualifikation": "Qualifikation",
    "oenace": "ÖNACE-Abschnitt",
}
#: Höchstens so viele Abweichungen je Gliederung zeigt § 5 (die größten nach Betrag).
REVISION_ZEILEN = 5
#: Monatsnamen für Sätze („März 2025“).
MONATSNAMEN = (
    "Jänner",
    "Februar",
    "März",
    "April",
    "Mai",
    "Juni",
    "Juli",
    "August",
    "September",
    "Oktober",
    "November",
    "Dezember",
)
#: Satz ohne Treffer einer Prüfung.
KEINE_AUFFAELLIGKEIT = "Keine Auffälligkeit."


class BerichtFehler(RuntimeError):
    """Für die Lieferung gibt es keinen erfolgreichen Lauf."""


# --- Formatierung ------------------------------------------------------------------------------------


def zahl(wert: int) -> str:
    """Ganzzahl im österreichischen Format (Tausenderpunkt)."""
    return f"{wert:,}".replace(",", ".")


def zahl_vorzeichen(wert: int) -> str:
    return ("+" if wert > 0 else "") + zahl(wert)


def prozent(wert: float) -> str:
    """Prozent mit zwei Nachkommastellen, Dezimalkomma und Vorzeichen."""
    text = f"{abs(wert):,.2f}".replace(",", "_").replace(".", ",").replace("_", ".")
    vorzeichen = "+" if wert > 0 else ("-" if wert < 0 else "")
    return f"{vorzeichen}{text} %"


def mehrzahl(anzahl: int, einzahl: str, viele: str) -> str:
    """„1 Satz“, „2 Sätze“: Anzahl im österreichischen Format mit passendem Wort."""
    return f"{zahl(anzahl)} {einzahl if anzahl == 1 else viele}"


#: Vorzeichenbehaftete Ganzzahl ohne Tausenderpunkt in gespeicherten Texten (etwa „-4410“ aus `:+d`).
_ROHE_ZAHL = re.compile(r"(?<![\w.,])([+-])(\d{4,})(?![\d.,]*\d)")
#: Einzahl nach „1“ in gespeicherten Befundtexten (meta.pruefung_treffer.umfang, Satzvorlagen der Prüfregeln).
#: Satzanfänge im Nominativ ändern auch das Verb, nach einer Präposition genügt das Nomen.
_EINZAHL = tuple(
    (re.compile(r"(?<![\d.,])1 " + muster), ersatz)
    for muster, ersatz in (
        (r"Gruppen (mit mindestens [\d.]+ Verhältnissen) haben\b", r"1 Gruppe \1 hat"),
        (r"Zeilen kamen\b", "1 Zeile kam"),
        (r"neue Verhältnisse gehören\b", "1 neues Verhältnis gehört"),
        (r"Verhältnisse haben\b", "1 Verhältnis hat"),
        (r"Verhältnisse gehören\b", "1 Verhältnis gehört"),
        (r"Verhältnisse tragen\b", "1 Verhältnis trägt"),
        (r"Gruppen\b", "1 Gruppe"),
        (r"Zellen\b", "1 Zelle"),
        (r"Zeilen\b", "1 Zeile"),
        (r"Sätzen?\b", "1 Satz"),
        (r"Verhältnissen?\b", "1 Verhältnis"),
        (r"Personen\b", "1 Person"),
    )
)


def text_glaetten(text: str) -> str:
    """Gespeicherte Befundtexte im Format des Berichts: Tausenderpunkt auch mit Vorzeichen, Einzahl nach „1“.

    Die Texte entstehen beim Lauf (meta.pruefung_treffer.umfang, Satzvorlage der Prüfregel); der Bericht
    vereinheitlicht sie, ohne einen Lauf zu wiederholen. Das Minuszeichen bleibt „-“ wie im ganzen Bericht."""
    text = _ROHE_ZAHL.sub(lambda m: m.group(1) + zahl(int(m.group(2))), text)
    for muster, ersatz in _EINZAHL:
        text = muster.sub(ersatz, text)
    text = _ZEILEN_GEGEN.sub(r"\1 Zeilen statt \2 in \3", text)
    return _MEHR_ODER_WENIGER.sub(
        lambda m: (
            ("mehr" if int(m.group(1).replace(".", "")) > int(m.group(2).replace(".", "")) else "weniger")
            + f" Zeilen als die vorige ({m.group(1)} Zeilen statt {m.group(2)}"
        ),
        text,
    )


#: Umfang der Zeilenzahl-Prüfung „345.078 / 434.104 Zeilen gegen 2025-09“: welche Zahl wozu gehört.
_ZEILEN_GEGEN = re.compile(r"([\d.]+) / ([\d.]+) Zeilen gegen (\d{4}-\d{2})")
#: „mehr oder weniger Zeilen“ der Satzvorlage: die Richtung steht in den beiden Zahlen.
_MEHR_ODER_WENIGER = re.compile(r"mehr oder weniger Zeilen als die vorige \(([\d.]+) Zeilen statt ([\d.]+)")
#: Gliederung und Code in gespeicherten Befundtexten („oenace A“, „region 5“), Klarname aus stat.klass_*.
_GLIEDERUNG_CODE = re.compile(r"\b(oenace|region|qualifikation|geschlecht) ([A-Za-z0-9]+)\b")
#: Klammer, die nur interne Codes enthält („(-1)“, „(UNB bzw. 0)“), in Maßnahmen der Prüfregeln.
_NUR_CODES = re.compile(r"\s*\((?:-?\d+|[A-Z]{2,}(?: bzw\. -?\d+)?)\)")


def _klarnamen(conn: Verbindung, lieferung: str) -> dict[tuple[str, str], str]:
    """Bezeichnung je (Gliederung, Code) aus stat.klass_*, ÖNACE in der am Stichtag gültigen Version.

    ÖNACE-Abschnitte behalten den Buchstaben in Klammern, weil Tabellen und § 5 ihn zeigen."""
    stichtag = ergebnis.monatsletzter(lieferung)
    namen: dict[tuple[str, str], str] = {}
    abfragen = (
        (
            "oenace",
            """SELECT code, bezeichnung || ' (' || code || ')' AS name FROM stat.klass_oenace
               WHERE ebene = 1 AND gueltig_von <= %(t)s AND (gueltig_bis IS NULL OR gueltig_bis >= %(t)s)""",
        ),
        ("region", "SELECT code, bezeichnung AS name FROM stat.klass_region WHERE ebene = 'bundesland'"),
        ("qualifikation", "SELECT code, bezeichnung AS name FROM stat.klass_qualifikation"),
        ("geschlecht", "SELECT code, bezeichnung AS name FROM stat.klass_geschlecht"),
    )
    for gliederung, abfrage in abfragen:
        if _hat_tabelle(conn, "stat.klass_" + gliederung):
            for z in conn.execute(abfrage, {"t": stichtag}).fetchall():
                namen[(gliederung, str(z["code"]))] = str(z["name"])
    return namen


def _lesbar(treffer: list[dict[str, object]], namen: dict[tuple[str, str], str]) -> list[dict[str, object]]:
    """Prüftreffer mit Klarnamen statt Gliederungscodes im Umfang und ohne Code-Klammern in der Maßnahme."""

    def klar(m: re.Match[str]) -> str:
        return namen.get((m.group(1), m.group(2)), m.group(0))

    aus = []
    for t in treffer:
        neu = dict(t)
        if t["umfang"]:
            neu["umfang"] = _GLIEDERUNG_CODE.sub(klar, str(t["umfang"]))
        if t["massnahme"]:
            neu["massnahme"] = _NUR_CODES.sub("", str(t["massnahme"]))
        aus.append(neu)
    return aus


def datum(wert: object) -> str:
    """TT.MM.JJJJ; Zeitpunkte in Wiener Ortszeit."""
    if isinstance(wert, datetime):
        wert = wert.astimezone(ZEITZONE).date()
    if isinstance(wert, date):
        return wert.strftime("%d.%m.%Y")
    return "–"


def monat_text(lieferung: str) -> str:
    """„2025-03“ wird „März 2025“."""
    jahr, monat = lieferung.split("-")
    return f"{MONATSNAMEN[int(monat) - 1]} {jahr}"


def stichtag_text(lieferung: str) -> str:
    """Letzter Tag des Monats in Worten, z. B. „31. März 2025“."""
    tag = ergebnis.monatsletzter(lieferung)
    return f"{tag.day}. {MONATSNAMEN[tag.month - 1]} {tag.year}"


def als_satz(text: object) -> str:
    """Kurzangabe als Satz: großer Anfang, Punkt am Ende („→ C …“ wird „Zugeordnet zu C …“)."""
    s = " ".join(str(text or "").split())
    if not s:
        return ""
    if s.startswith("→"):
        s = "Zugeordnet zu" + s[1:]
    s = s[0].upper() + s[1:]
    return s if s[-1] in ".!?)" else s + "."


class _Vorlage(dict[str, str]):
    """Füllt bekannte Platzhalter einer Satzvorlage und lässt unbekannte stehen."""

    def __missing__(self, schluessel: str) -> str:
        return "{" + schluessel + "}"


def _zelle(text: object) -> str:
    """Tabellenzelle: einzeilig, Pipe maskiert."""
    if text is None or text == "":
        return "–"
    return " ".join(str(text).split()).replace("|", "\\|")


def _kurz(text: str, laenge: int) -> str:
    text = " ".join(text.split())
    return text if len(text) <= laenge else text[: laenge - 1].rstrip() + "…"


def _int(wert: object) -> int:
    return 0 if wert is None else int(str(wert))


def _tabelle(kopf: list[str], zeilen: list[list[str]]) -> list[str]:
    aus = ["| " + " | ".join(kopf) + " |", "| " + " | ".join("---" for _ in kopf) + " |"]
    aus += ["| " + " | ".join(z) + " |" for z in zeilen]
    return aus


# --- Datenbank ---------------------------------------------------------------------------------------


def _hat_tabelle(conn: Verbindung, name: str) -> bool:
    zeile = conn.execute("SELECT to_regclass(%s) IS NOT NULL AS da", (name,)).fetchone()
    return bool(zeile and zeile["da"])


def _bestand(conn: Verbindung, regelsatz: str, regelstand: str, lieferung: str) -> int:
    zeile = conn.execute(
        """SELECT coalesce(sum(wert), 0) AS n FROM stat.stat_beschaeftigte
           WHERE regelsatz = %s AND regelstand = %s AND zeitraum_art = 'Stichtag' AND variable = %s
             AND zeitraum_bis BETWEEN %s AND %s""",
        (
            regelsatz,
            regelstand,
            STICHTAG_VARIABLE,
            ergebnis.monatserster(lieferung),
            ergebnis.monatsletzter(lieferung),
        ),
    ).fetchone()
    return _int(zeile["n"]) if zeile else 0


def _veroeffentlichender_lauf(conn: Verbindung, stand: ergebnis.LaufStand) -> int:
    """Lauf, den eine Person mit Namen freigegeben hat: der erste mit meta.lauf.freigegeben_von für Lieferung,
    Regelsatz und Regelstand (`veroeffentlichen` setzt das Feld; spätere Läufe übernehmen es nur).

    Nicht der Lauf, an dem die endgültigen Zellen hängen: Prüfregeln gehören nicht zum Regelstand, ein früherer
    Lauf mit gleichen Zellen kann also andere Prüftreffer haben als der freigegebene. Rechnet ein späterer Lauf
    unter neuem Regelstand nach, gehören seine Prüftreffer und Regelwirkung zum neuen Stand und stehen nur in
    § 5. Ohne freigegebenen Lauf ist es der maßgebliche Lauf selbst (vorläufig)."""
    zeile = conn.execute(
        """SELECT min(id) AS id FROM meta.lauf
           WHERE lieferung = %s AND regelsatz = %s AND regelstand = %s AND freigegeben_von IS NOT NULL
             AND status IN ('fertig', 'unveraendert')""",
        (stand.lieferung, stand.regelsatz, stand.regelstand),
    ).fetchone()
    return stand.lauf_id if zeile is None or zeile["id"] is None else _int(zeile["id"])


def _freigabe(conn: Verbindung, lieferung: str, regelsatz: str) -> tuple[str, object] | None:
    """Name und Zeitpunkt der Freigabe des Monats: vom jüngsten freigegebenen Lauf.

    Nicht vom Lauf, der die Zellen trägt: rechnet ein zweiter Lauf dasselbe Ergebnis, bleiben die Zellen am
    ersten Lauf, die Freigabe steht aber am zweiten."""
    zeile = conn.execute(
        """SELECT freigegeben_von, freigegeben_am FROM meta.lauf
           WHERE lieferung = %s AND regelsatz = %s AND freigegeben_von IS NOT NULL
           ORDER BY id DESC LIMIT 1""",
        (lieferung, regelsatz),
    ).fetchone()
    return None if zeile is None else (str(zeile["freigegeben_von"]), zeile["freigegeben_am"])


def _offene_regeln(conn: Verbindung, lieferung: str, regelsatz: str) -> int:
    """Aktive, für den Monat gültige Regeln ohne Freigabe mit Namen."""
    zeile = conn.execute(
        """SELECT count(*) AS n FROM meta.regel
           WHERE regelsatz = %(rs)s AND aktiv AND freigegeben_von IS NULL AND gueltig_ab_lieferung <= %(l)s
             AND (gueltig_bis_lieferung IS NULL OR gueltig_bis_lieferung >= %(l)s)""",
        {"rs": regelsatz, "l": lieferung},
    ).fetchone()
    return _int(zeile["n"]) if zeile else 0


def _dateiname(conn: Verbindung, lieferung: str) -> str:
    zeile = conn.execute(
        "SELECT datei FROM roh.ladeprotokoll WHERE lieferung = %s AND datei IS NOT NULL "
        "ORDER BY geladen_am DESC, datei LIMIT 1",
        (lieferung,),
    ).fetchone()
    return str(zeile["datei"]) if zeile else f"lieferung_{lieferung}.csv"


def _pruefungen_gelaufen(conn: Verbindung, lauf_id: int) -> int:
    """Zahl der Prüfregeln, die im Lauf gelaufen sind; 0 heißt: keine Prüfung gelaufen.

    Gemessen an meta.pruefung_treffer: Jede gelaufene Prüfregel schreibt dort ein Ergebnis, auch ohne Treffer
    (anzahl 0). Gezählt werden verschiedene Regeln, nicht Zeilen."""
    if not _hat_tabelle(conn, "meta.pruefung_treffer"):
        return 0
    zeile = conn.execute(
        "SELECT count(DISTINCT regel_id) AS n FROM meta.pruefung_treffer WHERE lauf_id = %s", (lauf_id,)
    ).fetchone()
    return _int(zeile["n"]) if zeile else 0


def _fortgeschrieben(conn: Verbindung, lauf_id: int) -> int:
    """Verhältnisse, die Regel E07 im Lauf aus der Vorlieferung fortgeschrieben hat (meta.lauf.fortgeschrieben)."""
    zeile = conn.execute("SELECT fortgeschrieben FROM meta.lauf WHERE id = %s", (lauf_id,)).fetchone()
    return _int(zeile["fortgeschrieben"]) if zeile else 0


def _treffer(conn: Verbindung, lauf_id: int) -> list[dict[str, object]]:
    if not _hat_tabelle(conn, "meta.pruefung_treffer"):
        return []
    return conn.execute(
        """SELECT t.ebene, t.anzahl, t.umfang, t.einstufung, t.massnahme, t.anhalten, t.beleg_sql,
                  t.details ->> 'rueckfrage' AS rueckfrage, r.name, r.parameter ->> 'regel' AS pruef_regel,
                  r.beschreibung,
                  r.parameter ->> 'satz' AS satz_vorlage
           FROM meta.pruefung_treffer t JOIN meta.regel r ON r.id = t.regel_id
           WHERE t.lauf_id = %s AND t.anzahl > 0
           ORDER BY r.reihenfolge, r.name, array_position(ARRAY['satz', 'aggregat', 'lieferung'], t.ebene)""",
        (lauf_id,),
    ).fetchall()


def _rueckfragen(conn: Verbindung) -> list[dict[str, object]]:
    if not _hat_tabelle(conn, "meta.rueckfrage"):
        return []
    return conn.execute(
        """SELECT nr, titel, lieferungen, frage, vorschlag, regel_name, gestellt_am, antwort, antwort_am,
                  ab_lieferung
           FROM meta.rueckfrage ORDER BY length(nr), nr"""
    ).fetchall()


#: Marke in den Prüfregeln für „Befund ohne gestellte Rückfrage“ (Parameter ``rueckfrage``).
OHNE_RUECKFRAGE = "neu"


def _verweise(treffer: dict[str, object], rueckfragen: list[dict[str, object]]) -> list[str]:
    """Nummern der Rückfragen zu einem Prüftreffer, nur aus meta.rueckfrage und der Prüfregel.

    Eine Rückfrage gehört dazu, wenn ihre Regel (``regel_name``) die Prüfregel ist oder die Prüfregel sie
    nennt. Nennt die Prüfregel keine, zählt auch die Einlese- oder Zählregel, die sie prüft (Parameter
    ``regel``, etwa P01 → E02 → R7), außer der Befund ist „erklärt – plausibel“: eine echte Entwicklung
    (etwa P07, Menschen ab 75) hängt nicht an der offenen Frage ihrer Regel. Die Marke „neu“ ist keine Nummer.
    """
    eigene = str(treffer["rueckfrage"] or "")
    namen = {treffer["name"]}
    if not eigene and treffer.get("pruef_regel") and treffer["einstufung"] != "erklaert-plausibel":
        namen.add(treffer["pruef_regel"])
    nrn = [str(r["nr"]) for r in rueckfragen if r["regel_name"] is not None and r["regel_name"] in namen]
    if eigene and eigene != OHNE_RUECKFRAGE and eigene not in nrn:
        nrn.append(eigene)
    return nrn


def _rueckfrage_spalte(treffer: dict[str, object], rueckfragen: list[dict[str, object]]) -> list[str]:
    """Rückfrage-Spalte in § 2: Nummern, sonst ein Klartext. Neben „nicht erklärbar“ steht nie „–“
    (ohne Einstufung gilt der Treffer als nicht erklärbar, wie in § 2)."""
    nrn = _verweise(treffer, rueckfragen)
    if nrn:
        return nrn
    if treffer["einstufung"] in (None, "nicht-erklaerbar"):
        return ["noch keine Rückfrage gestellt"]
    if treffer["rueckfrage"] == OHNE_RUECKFRAGE or treffer["einstufung"] == "erklaert-plausibel":
        return ["keine Rückfrage nötig"]
    return []


def _gilt_fuer_monat(rueckfrage: dict[str, object], lieferung: str) -> bool:
    """Steht die Lieferung in der Spalte ``lieferungen`` der Rückfrage?

    Formen in 130_rueckfragen.sql: „lieferung_2025-10“, „lieferung_2025-05, lieferung_2026-02“ (Einzelmonate)
    sowie „lieferung_2024-08 und alle weiteren“ und „alle ab lieferung_2024-08“ (ab diesem Monat).
    """
    text = str(rueckfrage.get("lieferungen") or "")
    monate = re.findall(r"\d{4}-\d{2}", text)
    if re.search(r"\balle\b", text, re.IGNORECASE):
        ab = str(rueckfrage.get("ab_lieferung") or min(monate, default=""))
        return bool(ab) and ab <= lieferung
    return lieferung in monate


def _umfang(t: dict[str, object]) -> str:
    if t["umfang"]:
        return text_glaetten(" ".join(str(t["umfang"]).split()))
    return mehrzahl(_int(t["anzahl"]), "Satz", "Sätze")


#: Marke im gespeicherten Beleg einer Prüfung, die nur gelieferte Abschnitte zählt (ohne Fortschreibung E07).
NUR_GELIEFERT = "herkunft = 'geliefert'"
#: Satz zu solchen Prüfungen, wenn der Monat oder sein Vormonat fortgeschriebene Verhältnisse hat.
HINWEIS_NUR_GELIEFERT = "Diese Prüfung zählt nur gelieferte Verhältnisse; der Überblick zählt die fortgeschriebenen (Regel E07) mit."


def befund_satz(t: dict[str, object], lieferung: str) -> str:
    """Ein Satz in Alltagssprache zu einem Prüftreffer, aus der Vorlage `parameter.satz` der Prüfregel.

    Platzhalter: {anzahl}, {umfang}, {monat}. Ohne Vorlage: Beschreibung der Regel mit Umfang; ohne Treffer:
    „Keine Auffälligkeit.“"""
    if _int(t.get("anzahl")) == 0:
        return KEINE_AUFFAELLIGKEIT
    werte = _Vorlage(anzahl=zahl(_int(t["anzahl"])), umfang=_umfang(t), monat=monat_text(lieferung))
    vorlage = t.get("satz_vorlage")
    if vorlage:
        return text_glaetten(" ".join(str(vorlage).format_map(werte).split()))
    return als_satz(
        f"{' '.join(str(t['beschreibung'] or t['name']).split()).rstrip('.')} ({werte['umfang']})"
    )


# --- Abschnitte als Daten ----------------------------------------------------------------------------


def _kennzahlen(conn: Verbindung, lauf: dict[str, object], lieferung: str, regelsatz: str) -> dict[str, Any]:
    gelesen, gezaehlt = _int(lauf["gelesen"]), _int(lauf["gezaehlt"])
    nicht, ausgeschlossen, korrigiert = (
        _int(lauf["nicht_gezaehlt"]),
        _int(lauf["ausgeschlossen"]),
        _int(lauf["korrigiert"]),
    )
    fortgeschrieben = _int(lauf.get("fortgeschrieben") or 0)
    bestand = _bestand(conn, regelsatz, str(lauf["regelstand"]), lieferung)

    vormonat = ergebnis.monat_verschieben(lieferung, -1)
    vorher = ergebnis.letzter_lauf(conn, vormonat, regelsatz)
    if vorher is None:
        veraenderung = f"kein Vergleich, {vormonat} ist nicht gerechnet"
    else:
        alt = _bestand(conn, regelsatz, vorher.regelstand, vormonat)
        diff = bestand - alt
        anteil = prozent(diff / alt * 100) if alt else "kein Anteil"
        fort_vm = _fortgeschrieben(conn, vorher.lauf_id)
        mit = f", davon {zahl(fort_vm)} fortgeschrieben" if fort_vm else ""
        veraenderung = f"{zahl_vorzeichen(diff)} ({anteil}) gegenüber {vormonat} ({zahl(alt)}{mit})"

    # Mit Fortschreibung (E07) gibt es zwei Bestände: mit und ohne fortgeschriebene Verhältnisse. Die
    # Bezeichnungen sagen dann, welche Zahl welche ist; Prüfungen in § 2 zählen nur gelieferte.
    mit_e07 = " (mit fortgeschriebenen, Regel E07)" if fortgeschrieben else ""
    zeilen = [
        ["gelesene Sätze", zahl(gelesen)],
        ["davon gezählt am Stichtag" + mit_e07, zahl(gezaehlt)],
        [
            "ausgeschlossene oder korrigierte Sätze",
            f"{zahl(ausgeschlossen)} ausgeschlossen, {zahl(korrigiert)} korrigiert",
        ],
        ["Beschäftigungsverhältnisse am Stichtag" + mit_e07, zahl(bestand)],
        ["Veränderung zum Vormonat", veraenderung],
    ]
    abrechnung = "Abrechnung: gelesene Sätze = gezählte + nicht gezählte + ausgeschlossene Sätze."
    if fortgeschrieben:
        # E07 schreibt nur Verhältnisse fort, die am Stichtag laufen; sie stecken in „gezählt“.
        zeilen[2:2] = [
            ["davon geliefert gezählt (ohne fortgeschriebene)", zahl(gezaehlt - fortgeschrieben)],
            ["davon fortgeschrieben aus der Vorlieferung (Regel E07, vorläufig)", zahl(fortgeschrieben)],
        ]
        abrechnung = (
            "Abrechnung: gelesene Sätze + fortgeschriebene Verhältnisse = gezählte + nicht gezählte"
            " + ausgeschlossene Sätze."
        )
    aufgeht = gelesen + fortgeschrieben == gezaehlt + nicht + ausgeschlossen
    in_zahlen = (
        f"Abrechnung in Zahlen: {zahl(gelesen)} gelesen"
        + (f" + {zahl(fortgeschrieben)} fortgeschrieben" if fortgeschrieben else "")
        + f" = {zahl(gezaehlt)} gezählt + {zahl(nicht)} nicht gezählt"
        f" + {zahl(ausgeschlossen)} ausgeschlossen ({'geht auf' if aufgeht else 'geht NICHT auf'})."
        f" Korrigierte Sätze ({zahl(korrigiert)}) bleiben in der Abrechnung, eine Einleseregel hat sie nur"
        " verändert."
    )
    return {
        "zeilen": zeilen,
        "werte": {
            "gelesen": gelesen,
            "gezaehlt": gezaehlt,
            "fortgeschrieben": fortgeschrieben,
            "nicht_gezaehlt": nicht,
            "ausgeschlossen": ausgeschlossen,
            "korrigiert": korrigiert,
            "bestand_stichtag": bestand,
        },
        "abrechnung": abrechnung,
        "abrechnung_in_zahlen": in_zahlen,
        "abrechnung_geht_auf": aufgeht,
        "hinweis": "Die Vorlage hat keine Zeile „nicht gezählt“; wir nennen sie in der Abrechnung, damit sie"
        " aufgeht, und zählen dort die Abschnitte, die am Stichtag nicht bestehen.",
    }


def _auffaelligkeiten_daten(
    treffer: list[dict[str, object]],
    rueckfragen: list[dict[str, object]],
    lieferung: str,
    mit_fortschreibung: bool = False,
) -> list[dict[str, Any]]:
    """§ 2 als Daten. `mit_fortschreibung`: der Monat oder sein Vormonat hat fortgeschriebene Verhältnisse (E07);
    dann sagt der Befund einer Prüfung, die nur Gelieferte zählt, warum ihre Zahl vom Überblick abweicht."""
    aus = []
    for nr, t in enumerate(treffer, start=1):
        satz = befund_satz(t, lieferung)
        if mit_fortschreibung and NUR_GELIEFERT in str(t["beleg_sql"] or ""):
            satz += " " + HINWEIS_NUR_GELIEFERT
        # Ohne Einstufung gilt der Treffer als nicht erklärt und geht an die Fachabteilung.
        aus.append(
            {
                "nr": nr,
                "ebene": EBENEN.get(str(t["ebene"]), str(t["ebene"])),
                "regel": str(t["name"]),
                "satz": satz,
                "anzahl": _int(t["anzahl"]),
                "umfang": _umfang(t),
                "einstufung": EINSTUFUNGEN.get(str(t["einstufung"]), EINSTUFUNGEN["nicht-erklaerbar"]),
                "massnahme": als_satz(t["massnahme"]),
                "anhalten": bool(t["anhalten"]),
                "rueckfragen": _rueckfrage_spalte(t, rueckfragen),
                "beleg_sql": str(t["beleg_sql"] or "").strip() or None,
            }
        )
    return aus


def _rueckfragen_daten(
    lieferung: str, treffer: list[dict[str, object]], rueckfragen: list[dict[str, object]]
) -> list[dict[str, Any]]:
    verwiesen = {nr for t in treffer for nr in _verweise(t, rueckfragen)}
    aus = []
    for r in rueckfragen:
        # Nur Rückfragen dieses Monats (#126): laut Spalte lieferungen oder weil ein Prüftreffer auf sie verweist.
        if not (str(r["nr"]) in verwiesen or _gilt_fuer_monat(r, lieferung)):
            continue
        if r["antwort"]:
            antwort = f"{r['antwort']} ({datum(r['antwort_am'])})" if r["antwort_am"] else str(r["antwort"])
        else:
            antwort = f"Noch offen. Bis zur Antwort gilt: {als_satz(r['vorschlag'])}"
        aus.append(
            {
                "nr": str(r["nr"]),
                "gestellt_am": datum(r["gestellt_am"]) if r["gestellt_am"] else "noch nicht gestellt",
                "frage": " ".join(f"{r['titel']}: {r['frage']}".split()),
                "antwort": antwort,
                "offen": not r["antwort"],
                "regel_name": r["regel_name"],
            }
        )
    return aus


def _regeln_daten(conn: Verbindung, lauf_id: int, lieferung: str, regelsatz: str) -> list[dict[str, Any]]:
    zeilen = conn.execute(
        """SELECT r.name, r.typ, r.reihenfolge, r.gueltig_ab_lieferung, r.grundlage, w.saetze
           FROM meta.regel r
           LEFT JOIN meta.regel_wirkung w ON w.regel_id = r.id AND w.lauf_id = %(lauf)s
           WHERE r.typ IN ('einlese', 'zuordnung', 'zaehl')
             AND (w.lauf_id IS NOT NULL
                  OR (r.regelsatz = %(rs)s AND r.aktiv AND r.gueltig_ab_lieferung <= %(l)s
                      AND (r.gueltig_bis_lieferung IS NULL OR r.gueltig_bis_lieferung >= %(l)s)))""",
        {"lauf": lauf_id, "rs": regelsatz, "l": lieferung},
    ).fetchall()
    zeilen.sort(key=lambda z: (TYP_REIHENFOLGE[str(z["typ"])], _int(z["reihenfolge"]), str(z["name"])))
    return [
        {
            "name": str(z["name"]),
            "seit": str(z["gueltig_ab_lieferung"]),
            "grundlage": z["grundlage"],
            "saetze": _int(z["saetze"]),
        }
        for z in zeilen
    ]


def _nachrechnung(
    conn: Verbindung, lauf: dict[str, object], quelle_id: int, treffer_quelle: list[dict[str, object]]
) -> list[str]:
    """Hinweis in § 5, wenn ein späterer Lauf einen veröffentlichten Monat unter neuem Regelstand nachrechnet.

    meta.lauf.regelstand zeigt bei solchen Läufen den veröffentlichten Stand. Ob der neue Stand wirklich
    anders ist, steht in meta.revision: nur dann schreibt der Lauf Zeilen für den eigenen Monat."""
    lauf_id = _int(lauf["id"])
    if lauf_id == quelle_id or not _hat_tabelle(conn, "meta.revision"):
        return []
    anders = conn.execute(
        "SELECT EXISTS (SELECT 1 FROM meta.revision WHERE lauf_id = %s AND berichtsmonat = %s) AS ja",
        (lauf_id, lauf["lieferung"]),
    ).fetchone()
    if anders is None or not anders["ja"]:
        return []
    aus = [
        f"Lauf {lauf_id} hat den veröffentlichten Monat mit geänderten Regeln nachgerechnet. Die Abschnitte 1"
        f" bis 4 zeigen den veröffentlichenden Lauf {quelle_id}; was die neuen Regeln anders sehen, steht nur"
        " hier.",
    ]
    alt = {(t["name"], t["ebene"], _int(t["anzahl"]), bool(t["anhalten"])) for t in treffer_quelle}
    neu = [
        t
        for t in _treffer(conn, lauf_id)
        if (t["name"], t["ebene"], _int(t["anzahl"]), bool(t["anhalten"])) not in alt
    ]
    if neu:
        teile = [
            f"{t['name']} ({EBENEN.get(str(t['ebene']), str(t['ebene']))}, {mehrzahl(_int(t['anzahl']), 'Satz', 'Sätze')}"
            + (", hätte angehalten)" if t["anhalten"] else ")")
            for t in neu
        ]
        aus += ["", "Prüfungen, die mit den neuen Regeln anders treffen: " + "; ".join(teile) + "."]
    return aus


def _ohne_abgleich(conn: Verbindung, lieferung: str | None, regelsatz: str) -> str:
    """Satz, wenn meta.revision für den Lauf nichts enthält; im ersten Monat mit dem Grund."""
    if lieferung is not None:
        vormonat = ergebnis.monat_verschieben(lieferung, -1)
        if ergebnis.letzter_lauf(conn, vormonat, regelsatz) is None:
            return (
                f"Kein Revisionsabgleich, weil {monat_text(lieferung)} der erste gerechnete Monat ist und es"
                " keinen früheren Monat zum Vergleichen gibt."
            )
    return "Für diesen Lauf liegt kein Revisionsabgleich vor."


def _revision_daten(
    conn: Verbindung, lauf_id: int, lieferung: str | None = None, regelsatz: str = "v1"
) -> dict[str, Any]:
    leer: dict[str, Any] = {"abgeglichen": False, "zeilen": [], "details": [], "satz": None}
    if not _hat_tabelle(conn, "meta.revision"):
        return leer | {"satz": _ohne_abgleich(conn, lieferung, regelsatz)}
    zeilen = conn.execute(
        """SELECT berichtsmonat, veroeffentlicht, aktuell, differenz, status_vorher
           FROM meta.revision WHERE lauf_id = %s AND gliederung = 'insgesamt' ORDER BY berichtsmonat""",
        (lauf_id,),
    ).fetchall()
    # Abweichungen je Gliederung: eine Umschichtung (z. B. C +10, D -10) lässt „insgesamt“ unverändert.
    gliederung: dict[str, list[dict[str, object]]] = {}
    for g in conn.execute(
        """SELECT berichtsmonat, gliederung, schluessel, veroeffentlicht, aktuell, differenz
           FROM meta.revision WHERE lauf_id = %s AND gliederung <> 'insgesamt' AND differenz <> 0
           ORDER BY berichtsmonat, gliederung, abs(differenz) DESC, schluessel""",
        (lauf_id,),
    ).fetchall():
        gliederung.setdefault(str(g["berichtsmonat"]), []).append(g)
    ursachen: dict[str, tuple[str, int]] = {}
    if _hat_tabelle(conn, "meta.revision_ursache"):
        for u in conn.execute(
            """SELECT DISTINCT ON (berichtsmonat) berichtsmonat, ursache, anzahl FROM meta.revision_ursache
               WHERE lauf_id = %s ORDER BY berichtsmonat, abs(anzahl) DESC, ursache""",
            (lauf_id,),
        ).fetchall():
            ursachen[str(u["berichtsmonat"])] = (str(u["ursache"]), _int(u["anzahl"]))
    tabelle: list[dict[str, Any]] = []
    details: list[dict[str, Any]] = []
    for z in zeilen:
        monat = str(z["berichtsmonat"])
        if _int(z["differenz"]) == 0 and monat not in gliederung:
            continue
        haupt = None
        if _int(z["differenz"]) == 0:
            haupt = "Umschichtung zwischen Ausprägungen, insgesamt unverändert"
        elif monat in ursachen:
            ursache, anzahl = ursachen[monat]
            haupt = f"{URSACHEN.get(ursache, ursache)} ({mehrzahl(anzahl, 'Verhältnis', 'Verhältnisse')})"
        # status_vorher ist der Stand beim Lauf. Ist der Monat inzwischen endgültig, heißt es „damals vorläufig“.
        damals = z["status_vorher"] == "vorlaeufig"
        jetzt = ergebnis.letzter_lauf(conn, monat, regelsatz)
        tabelle.append(
            {
                "berichtsmonat": monat,
                "veroeffentlicht": _int(z["veroeffentlicht"]),
                "vorlaeufig": damals and (jetzt is None or jetzt.ergebnis_status != "endgueltig"),
                "damals_vorlaeufig": damals,
                "aktuell": _int(z["aktuell"]),
                "differenz": _int(z["differenz"]),
                "hauptursache": haupt,
            }
        )
        gezeigt: dict[str, int] = {}
        for g in gliederung.get(monat, []):
            name = str(g["gliederung"])
            gezeigt[name] = gezeigt.get(name, 0) + 1
            if gezeigt[name] <= REVISION_ZEILEN:
                details.append(
                    {
                        "berichtsmonat": monat,
                        "gliederung": GLIEDERUNGEN.get(name, name),
                        "auspraegung": str(g["schluessel"]),
                        "veroeffentlicht": _int(g["veroeffentlicht"]),
                        "aktuell": _int(g["aktuell"]),
                        "differenz": _int(g["differenz"]),
                    }
                )
    satz = None
    if not zeilen:
        satz = _ohne_abgleich(conn, lieferung, regelsatz)
    elif not tabelle:
        stimmen = "geprüfter Vormonat stimmt" if len(zeilen) == 1 else "geprüfte Vormonate stimmen"
        satz = (
            f"Kein Revisionsbedarf: {zahl(len(zeilen))} {stimmen} in allen Gliederungen mit der"
            " aktuellen Lieferung überein."
        )
    return {"abgeglichen": bool(zeilen), "zeilen": tabelle, "details": details, "satz": satz}


def _status_saetze(
    conn: Verbindung,
    stand: ergebnis.LaufStand,
    lauf: dict[str, object],
    quelle: dict[str, object],
    auffaelligkeiten: list[dict[str, Any]],
    freigabe: tuple[str, object] | None,
) -> list[str]:
    """Je Grund ein einfacher Satz, gebaut aus den Daten (nicht aus meta.lauf.meldung)."""
    monat = monat_text(stand.lieferung)
    if stand.ergebnis_status == "endgueltig":
        # Veröffentlicht ist veröffentlicht: ein Anhalten unter neuem Regelstand steht nur in § 5.
        wer = f"{freigabe[0]} hat sie am {datum(freigabe[1])} freigegeben." if freigabe else ""
        return [f"Die Zahlen für {monat} sind endgültig.", *([wer] if wer else [])]
    saetze = [
        f"Die Zahlen für {monat} sind gesperrt und dürfen so nicht veröffentlicht werden."
        if stand.ergebnis_status == "gesperrt"
        else f"Die Zahlen für {monat} sind vorläufig."
    ]
    angehalten = [a for a in auffaelligkeiten if a["anhalten"]]
    if angehalten:
        # Je Befund sein Satz, der Grund „angehalten“ nur einmal mit allen Prüfregeln.
        # Der E07-Hinweis steht im Status-Block nur einmal.
        hinweis = " " + HINWEIS_NUR_GELIEFERT
        saetze += [str(a["satz"]).replace(hinweis, "") for a in angehalten]
        mit_hinweis = sum(hinweis in str(a["satz"]) for a in angehalten)
        if mit_hinweis == 1:
            saetze.append(HINWEIS_NUR_GELIEFERT)
        elif mit_hinweis > 1:
            saetze.append(HINWEIS_NUR_GELIEFERT.replace("Diese Prüfung zählt", "Diese Prüfungen zählen"))
        regeln = ", ".join(dict.fromkeys(str(a["regel"]) for a in angehalten))
        saetze.append(f"Deshalb ist der Monat angehalten ({regeln}).")
    fort = _int(quelle.get("fortgeschrieben") or 0)
    if fort:
        vormonat = monat_text(ergebnis.monat_verschieben(stand.lieferung, -1))
        saetze.append(
            f"Wir haben {zahl(fort)} Verhältnisse aus der Lieferung für {vormonat} fortgeschrieben, weil sie"
            f" laut dieser Lieferung am {stichtag_text(stand.lieferung)} noch liefen."
        )
    if _offene_regeln(conn, stand.lieferung, stand.regelsatz):
        saetze.append(
            "Die Regeln sind noch nicht mit Namen freigegeben. Erst danach können die Zahlen endgültig werden."
        )
    elif not angehalten:
        saetze.append(
            "Die Regeln sind freigegeben, der Monat selbst ist noch nicht mit Namen veröffentlicht."
        )
    if lauf.get("status") == "unveraendert":
        saetze.append("Ein weiterer Lauf mit denselben Daten und Regeln hat genau dieselben Zahlen ergeben.")
    return saetze


def _begriffe(fortgeschrieben: bool) -> str:
    text = (
        "Begriffe: Ein Verhältnis ist ein Beschäftigungsverhältnis, nicht eine Person. Der Stichtag ist der"
        " letzte Tag des Monats."
    )
    if fortgeschrieben:
        text += " Fortgeschrieben heißt: aus der vorigen Lieferung übernommen."
    return text


# --- Bericht -----------------------------------------------------------------------------------------


def bericht_daten(conn: Verbindung, lieferung: str, regelsatz: str = "v1") -> dict[str, Any]:
    """Der Bericht als Struktur: Kopf, Status-Sätze, die fünf Abschnitte und die Annahmen des Monats."""
    stand = ergebnis.letzter_lauf(conn, lieferung, regelsatz)
    if stand is None:
        raise BerichtFehler(f"kein erfolgreicher Lauf für {lieferung} (Regelsatz {regelsatz})")
    lauf = conn.execute("SELECT * FROM meta.lauf WHERE id = %s", (stand.lauf_id,)).fetchone()
    assert lauf is not None
    # Veröffentlichter Monat: § 1 bis § 4 aus dem Lauf, der veröffentlicht hat; Neues nur in § 5.
    quelle_id = _veroeffentlichender_lauf(conn, stand)
    quelle = (
        lauf
        if quelle_id == stand.lauf_id
        else conn.execute("SELECT * FROM meta.lauf WHERE id = %s", (quelle_id,)).fetchone()
    )
    assert quelle is not None
    treffer = _lesbar(_treffer(conn, quelle_id), _klarnamen(conn, lieferung))
    rueckfragen = _rueckfragen(conn)
    freigabe = _freigabe(conn, lieferung, regelsatz)
    fortgeschrieben = _int(quelle.get("fortgeschrieben") or 0)
    vorher = ergebnis.letzter_lauf(conn, ergebnis.monat_verschieben(lieferung, -1), regelsatz)
    fort_vormonat = _fortgeschrieben(conn, vorher.lauf_id) if vorher else 0
    auffaelligkeiten = _auffaelligkeiten_daten(
        treffer, rueckfragen, lieferung, mit_fortschreibung=bool(fortgeschrieben or fort_vormonat)
    )
    return {
        "lieferung": lieferung,
        "regelsatz": regelsatz,
        # Für die Weboberfläche (#126), oberste Ebene:
        # lauf_id: maßgeblicher Lauf des Monats (jüngster erfolgreicher Lauf, wie technik.lauf_id).
        "lauf_id": stand.lauf_id,
        # regelstand: Hash des Regelstands dieses Laufs (meta.lauf.regelstand).
        "regelstand": stand.regelstand,
        # umgeschichtet: Verhältnisse, die Regel E07 aus der Vorlieferung fortgeschrieben hat
        # (meta.lauf.fortgeschrieben des Laufs, dessen Zahlen § 1 zeigt). meta.lauf hat kein eigenes Feld für
        # Umschichtungen zwischen Ausprägungen; die stehen nur in § 5 (meta.revision).
        "umgeschichtet": fortgeschrieben,
        # pruefungen_gelaufen: Zahl der verschiedenen Prüfregeln mit Ergebnis in meta.pruefung_treffer für den
        # Lauf, dessen Prüfungen § 2 zeigt (auch Prüfungen ohne Treffer); 0 heißt: keine Prüfung gelaufen.
        "pruefungen_gelaufen": _pruefungen_gelaufen(conn, quelle_id),
        "titel": f"Qualitätsbericht – Berichtsmonat {lieferung}",
        "datei": _dateiname(conn, lieferung),
        "erstellt_am": datum(lauf["beendet_am"]),
        "freigegeben_von": freigabe[0] if freigabe else None,
        "freigegeben_am": datum(freigabe[1]) if freigabe else None,
        "status": stand.ergebnis_status,
        "status_saetze": _status_saetze(conn, stand, lauf, quelle, auffaelligkeiten, freigabe),
        "begriffe": _begriffe(bool(fortgeschrieben)),
        "kennzahlen": _kennzahlen(conn, quelle, lieferung, regelsatz),
        "auffaelligkeiten": auffaelligkeiten,
        "rueckfragen": _rueckfragen_daten(lieferung, treffer, rueckfragen),
        "annahmen": annahmen(conn, lieferung, regelsatz),
        "regeln": _regeln_daten(conn, quelle_id, lieferung, regelsatz),
        "revision": _revision_daten(conn, stand.lauf_id, lieferung, regelsatz)
        | {"nachrechnung": _nachrechnung(conn, lauf, quelle_id, treffer)},
        "technik": {
            "lauf_id": stand.lauf_id,
            "veroeffentlichender_lauf": quelle_id,
            "regelstand": stand.regelstand,
            "ergebnis_hash": stand.ergebnis_hash,
        },
    }


# --- Markdown ----------------------------------------------------------------------------------------


def _md_kopf(d: dict[str, Any]) -> list[str]:
    freigabe = (
        f"{d['freigegeben_von']} am {d['freigegeben_am']}"
        if d["freigegeben_von"]
        else "noch nicht freigegeben"
    )
    status = {"endgueltig": "endgültig", "gesperrt": "gesperrt"}.get(str(d["status"]), "vorläufig")
    return [
        f"# {d['titel']}",
        "",
        f"Lieferung: `{d['datei']}`, erstellt am {d['erstellt_am']}, freigegeben von: {freigabe}",
        "",
        f"> **Status: {status}.** " + " ".join(d["status_saetze"]),
        "",
        d["begriffe"],
    ]


def _md_ueberblick(k: dict[str, Any]) -> list[str]:
    return [
        ABSCHNITTE[0],
        "",
        *_tabelle(["Kennzahl", "Wert"], k["zeilen"]),
        "",
        k["abrechnung"],
        "",
        k["abrechnung_in_zahlen"],
        "",
        k["hinweis"],
    ]


def _ueberblick(conn: Verbindung, lauf: dict[str, object], lieferung: str, regelsatz: str) -> list[str]:
    """§ 1 als Markdown-Zeilen."""
    return _md_ueberblick(_kennzahlen(conn, lauf, lieferung, regelsatz))


def _md_auffaelligkeiten(auffaelligkeiten: list[dict[str, Any]], gelaufen: int) -> list[str]:
    kopf = [
        "Nr.",
        "Ebene (Satz / Aggregat / Lieferung)",
        "Beschreibung",
        "Umfang (Sätze, Zellen)",
        "Beleg (Abfrage)",
        "Einstufung",
        "Maßnahme",
        "Rückfrage",
    ]
    zeilen: list[list[str]] = []
    belege: list[str] = []
    for a in auffaelligkeiten:
        beleg = "–"
        if a["beleg_sql"]:
            sql = str(a["beleg_sql"])
            beleg = "`" + _kurz(sql.replace("`", "'"), BELEG_KURZ).replace("|", "\\|") + "`"
            belege += [
                f"<details><summary>Beleg {a['nr']}: {a['regel']}</summary>",
                "",
                "```sql",
                sql,
                "```",
                "",
                "</details>",
                "",
            ]
        zeilen.append(
            [
                str(a["nr"]),
                str(a["ebene"]),
                _zelle(f"{a['satz']} ({a['regel']})"),
                _zelle(a["umfang"]),
                beleg,
                str(a["einstufung"]),
                _zelle(a["massnahme"]),
                _zelle(", ".join(a["rueckfragen"])),
            ]
        )
    aus = [ABSCHNITTE[1], "", *_tabelle(kopf, zeilen), ""]
    if not gelaufen:
        aus += ["Für diesen Lauf liegen keine Prüfergebnisse vor.", ""]
    elif not zeilen:
        aus += [
            f"{KEINE_AUFFAELLIGKEIT} Keine der {gelaufen} Prüfungen hat in diesem Monat angeschlagen.",
            "",
        ]
    aus += belege
    aus.append(
        "Einstufung: „erklärt – plausibel“ heißt, die Entwicklung ist echt und mit Daten belegt. „erklärt –"
        " Datenproblem“ heißt, der Fehler liegt in den Daten und ist behoben. „nicht erklärbar“ heißt, die"
        " Fachabteilung muss es klären."
    )
    return aus


def _md_rueckfragen(rueckfragen: list[dict[str, Any]]) -> list[str]:
    zeilen = [
        [_zelle(r["nr"]), r["gestellt_am"], _zelle(r["frage"]), _zelle(r["antwort"]), _zelle(r["regel_name"])]
        for r in rueckfragen
    ]
    aus = [
        ABSCHNITTE[2],
        "",
        *_tabelle(
            ["Nr.", "Gestellt am", "Frage (kurz)", "Antwort der Fachabteilung", "Umgesetzt als Regel"], zeilen
        ),
    ]
    if not zeilen:
        aus += ["", "Für diesen Berichtsmonat gibt es keine Rückfrage an die Fachabteilung."]
    return aus


def _md_regeln(regeln: list[dict[str, Any]], annahmen_monat: list[dict[str, object]]) -> list[str]:
    tabelle = [[f"`{r['name']}`", r["seit"], _zelle(r["grundlage"]), zahl(r["saetze"])] for r in regeln]
    aus = [
        ABSCHNITTE[3],
        "",
        *_tabelle(
            [
                "Regel",
                "Seit Berichtsmonat",
                "Grundlage (Rückfrage, Änderungsauftrag)",
                "betroffene Sätze in diesem Monat",
            ],
            tabelle,
        ),
    ]
    if annahmen_monat:
        aus += ["", "Annahmen für diesen Monat (sie gelten, bis die Fachabteilung antwortet):", ""]
        for a in annahmen_monat:
            bezug = ", ".join(
                t
                for t in (
                    f"Rückfrage {a['rueckfrage']}" if a["rueckfrage"] else "",
                    str(a["regel_name"] or ""),
                )
                if t
            )
            aus.append(f"- Annahme {a['nr']}: {a['satz']}" + (f" ({bezug})" if bezug else ""))
    return aus


def _md_revision(r: dict[str, Any]) -> list[str]:
    aus = [
        ABSCHNITTE[4],
        "",
        "Hier steht, wo die aktuelle Lieferung für schon veröffentlichte Monate andere Zahlen zeigt."
        " Veröffentlichte Zahlen bleiben unverändert.",
        "",
    ]
    if r["nachrechnung"]:
        aus += [*r["nachrechnung"], ""]
    kopf = ["Berichtsmonat", "veröffentlicht", "laut aktueller Lieferung", "Differenz", "Hauptursache"]
    if r["zeilen"]:  # ohne Abweichung kein leerer Tabellenkopf, nur der Satz unten
        aus += _tabelle(
            kopf,
            [
                [
                    z["berichtsmonat"],
                    zahl(z["veroeffentlicht"])
                    + (
                        " (vorläufig)"
                        if z["vorlaeufig"]
                        else (" (damals vorläufig)" if z.get("damals_vorlaeufig") else "")
                    ),
                    zahl(z["aktuell"]),
                    zahl_vorzeichen(z["differenz"]),
                    _zelle(z["hauptursache"]),
                ]
                for z in r["zeilen"]
            ],
        )
    while aus[-1] == "":
        aus.pop()
    if r["details"]:
        aus += [
            "",
            f"Abweichungen nach Gliederung (die {REVISION_ZEILEN} größten je Gliederung, nach Betrag):",
            "",
            *_tabelle(
                [
                    "Berichtsmonat",
                    "Gliederung",
                    "Ausprägung",
                    "veröffentlicht",
                    "laut aktueller Lieferung",
                    "Differenz",
                ],
                [
                    [
                        g["berichtsmonat"],
                        g["gliederung"],
                        _zelle(g["auspraegung"]),
                        zahl(g["veroeffentlicht"]),
                        zahl(g["aktuell"]),
                        zahl_vorzeichen(g["differenz"]),
                    ]
                    for g in r["details"]
                ],
            ),
        ]
    if r["satz"]:
        aus += ["", r["satz"]]
    return aus


def bericht_markdown(d: dict[str, Any]) -> str:
    """Markdown des Berichts aus `bericht_daten`."""
    t = d["technik"]
    teile = [
        _md_kopf(d),
        _md_ueberblick(d["kennzahlen"]),
        _md_auffaelligkeiten(d["auffaelligkeiten"], d["pruefungen_gelaufen"]),
        _md_rueckfragen(d["rueckfragen"]),
        _md_regeln(d["regeln"], d["annahmen"]),
        _md_revision(d["revision"]),
        [
            "---",
            "",
            f"Technische Angaben: Regelsatz {d['regelsatz']}, Lauf {t['lauf_id']}, Regelstand"
            f" `{t['regelstand']}`, Ergebnis-Hash `{t['ergebnis_hash']}`.",
        ],
    ]
    zeilen: list[str] = []
    for teil in teile:
        if zeilen:
            zeilen.append("")
        zeilen += teil
    while zeilen and zeilen[-1] == "":
        zeilen.pop()
    return "\n".join(zeilen) + "\n"


def bericht_erzeugen(conn: Verbindung, lieferung: str, regelsatz: str = "v1") -> str:
    """Qualitätsbericht (Markdown) des Berichtsmonats aus dem maßgeblichen Lauf."""
    return bericht_markdown(bericht_daten(conn, lieferung, regelsatz))


def bericht_pfad(lieferung: str, regelsatz: str = "v1") -> Path:
    ordner = "qualitaetsberichte" if regelsatz == "v1" else f"qualitaetsberichte_{regelsatz}"
    return konfig.abgabe() / ordner / f"{lieferung}.md"


def bericht_schreiben(
    conn: Verbindung, lieferung: str, regelsatz: str = "v1", ziel: Path | None = None
) -> Path:
    """Schreibt den Bericht nach `ziel` bzw. `abgabe/qualitaetsberichte[_<regelsatz>]/<lieferung>.md`."""
    pfad = ziel or bericht_pfad(lieferung, regelsatz)
    pfad.parent.mkdir(parents=True, exist_ok=True)
    pfad.write_text(bericht_erzeugen(conn, lieferung, regelsatz), encoding="utf-8")
    return pfad
