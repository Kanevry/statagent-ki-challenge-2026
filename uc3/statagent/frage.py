"""Datenanfragen der Fachjury (#74): Zeitreihe, Männer und Frauen, Fluktuation je ÖNACE, Definitionen.

Die Frage wird ohne Sprachmodell gelesen (Wörter und Monatsangaben wie in ``statagent.uc4``). Jede Abfrage läuft
über ``sql_lesen`` (nur lesend, nur stat/meta/klassifikation); ihr Text steht als Beleg in der Antwort. Zahlen
kommen aus ``stat.stat_beschaeftigte`` im Regelstand des maßgeblichen Laufs je Monat, Zu- und Abgänge aus der
Aggregatfunktion ``stat.bewegung_oenace`` (``uc3/db/160_bewegung.sql``), die nur Summen liefert.

Ist die Frage mehrdeutig (etwa „Beschäftigte 2025“: Stand welchen Monats?), kommt eine Rückfrage statt einer
Zahl. Die Antwort enthält die Felder einer ``UcAntwort`` und dazu Art, Definition, Einheit und Stand.
"""

from __future__ import annotations

import re
from datetime import date
from typing import Any

import psycopg
from psycopg import sql

from statagent.agenten.werkzeuge import AbfrageVerweigert, sql_lesen
from statagent.berichte.sheet import STICHTAG, STICHTAG_VARIABLE
from statagent.db import Verbindung
from statagent.ergebnis import letzter_lauf, monat_verschieben, monatserster, monatsletzter
from statagent.regeln import Regel, regeln_laden, regelstand
from statagent.uc4 import (
    _ISO,
    _NAME_MONAT,
    _OENACE_CODE,
    _OENACE_LISTE,
    _ZAHL_MONAT,
    MERKMALE,
    Merkmal,
    _aufzaehlung,
    _codes,
    _deutsch,
    _fortgeschrieben_hinweis,
    _gliederung,
    _monat_anzeige,
    jahr_rueckfrage,
)
from statagent.zeitraum import (
    KEIN_JAHR,
    MONATSNAMEN,
    ZEITREIHE_WORT,
    tag_hinweis,
    umschreiben,
    unklar,
    zeitraum_anzeige,
)

UC = "uc3"
QUELLE = "stat.stat_beschaeftigte"
UC_FELDER = ("text", "belege", "zahlen", "uc", "modell", "protokoll_id")

FLUKTUATION_DEFINITION = (
    "Fluktuation = (Zugänge + Abgänge) / 2 / Bestand, in Prozent, je ÖNACE-Abschnitt und Berichtsmonat. "
    "Bestand: Beschäftigungsverhältnisse am Stichtag (Monatsletzter) laut stat.stat_beschaeftigte im Regelstand "
    "des maßgeblichen Laufs. Zugang: ein Beschäftigungsverhältnis besteht am Stichtag, aber nicht am Stichtag des Vormonats; "
    "Abgang: umgekehrt. Beide Stichtage aus der Lieferung des Berichtsmonats (stat.bewegung_oenace). Zugänge "
    "zählen beim Abschnitt am Stichtag, Abgänge beim Abschnitt am Vormonats-Stichtag. Bestand 0 ergibt keine Rate."
)
OENACE_ERKLAERUNG = (
    "ÖNACE ist die österreichische Einteilung der Wirtschaftsbereiche in Abschnitte (Buchstaben)."
)
#: Erste und letzte Lieferung der Aufgabe; davor und danach gibt es keine Daten (nicht: „noch kein Lauf“).
ERSTE_LIEFERUNG, LETZTE_LIEFERUNG = "2024-08", "2026-07"
#: Zählregeln, die stat.bewegung_oenace (uc3/db/160_bewegung.sql) fest eingebaut hat.
EINGEBAUT = {
    ("bestand", "zeitraum_art"): "Stichtag",
    ("bestand", "von"): "monatsletzter",
    ("bestand", "bis"): "monatsletzter",
    ("abschnittswahl", "ordnung"): "spaetester_beginn",
}
#: „Am höchsten“ nennt nur Abschnitte mit mindestens so vielen Beschäftigungsverhältnissen am Stichtag.
MINDESTBESTAND_HOECHSTE = 1000
NICHT_LESBAR = (
    "Diese Frage lässt sich gerade nicht aus der Datenbank beantworten. Was tun: die Frage enger fassen, "
    "zum Beispiel einen Monat statt eines ganzen Zeitraums, oder etwas später noch einmal fragen."
)
_STATUS_TEXT = {"vorlaeufig": "vorläufig", "endgueltig": "endgültig", "gesperrt": "gesperrt"}

_JAHR = re.compile(r"(?<!\d)((?:19|20)\d{2})(?!\d)")
_DEFINITION = re.compile(
    r"\b(was\s+(ist|sind|bedeutet|heißt|heisst|zählt|zaehlt)|definition|bedeutung|definiert)\b"
)
_FLUKTUATION = re.compile(r"fluktu|zugäng|abgäng|zugaeng|abgaeng|zu- und abg")
_ZEITREIHE = ZEITREIHE_WORT
#: „Vergleich“ ist nur ohne genau einen Monat eine Zeitreihe („Vergleich Männer und Frauen im März 2025“ nicht).
_VERGLEICH = re.compile(r"vergleich|gegenüber")
_GESCHLECHT = re.compile(r"männer|maenner|frauen|geschlecht|männlich|weiblich")
_BUNDESLAND = re.compile(r"bundesl|länder|laender")


def _merkmal(name: str) -> Merkmal:
    return next(m for m in MERKMALE if m.name == name)


GESCHLECHT, BUNDESLAND, OENACE = _merkmal("Geschlecht"), _merkmal("Bundesland"), _merkmal("ÖNACE-Abschnitt")


# --- Frage lesen ---------------------------------------------------------------------------------------------


def monate_lesen(frage: str) -> list[str]:
    """Alle Monate der Frage als JJJJ-MM in Lesereihenfolge (``08/2024–07/2026`` ergibt zwei Monate)."""
    text = frage.lower()
    belegt: list[tuple[int, int]] = []
    gefunden: list[tuple[int, str]] = []
    for muster, jahr_gruppe, monat_gruppe in ((_NAME_MONAT, 2, 1), (_ZAHL_MONAT, 2, 1), (_ISO, 1, 2)):
        for treffer in muster.finditer(text):
            if any(treffer.start() < bis and treffer.end() > von for von, bis in belegt):
                continue
            roh = treffer.group(monat_gruppe)
            nummer = MONATSNAMEN[roh] if muster is _NAME_MONAT else int(roh)
            if 1 <= nummer <= 12:
                belegt.append((treffer.start(), treffer.end()))
                gefunden.append((treffer.start(), f"{int(treffer.group(jahr_gruppe)):04d}-{nummer:02d}"))
    return [monat for _, monat in sorted(gefunden)]


def jahr_ohne_monat(frage: str) -> str | None:
    """Eine Jahreszahl, die nicht Teil einer Monatsangabe ist (``Beschäftigte 2025``)."""
    text = KEIN_JAHR.sub(" ", frage.lower())  # „ÖNACE 2008“ ist kein Zeitraum
    for muster in (_NAME_MONAT, _ZAHL_MONAT, _ISO):
        text = muster.sub(" ", text)
    treffer = _JAHR.search(text)
    return treffer.group(1) if treffer else None


def fragetyp(frage: str) -> str:
    """definition | fluktuation | zeitreihe | geschlecht | bestand (ohne Prüfung, ob ein Monat fehlt)."""
    text = frage.lower()
    zeitlos = not monate_lesen(frage) and jahr_ohne_monat(frage) is None
    if _DEFINITION.search(text) and zeitlos:
        return "definition"
    if _FLUKTUATION.search(text):
        return "fluktuation"
    monate = set(monate_lesen(frage))
    if _ZEITREIHE.search(text) or len(monate) > 1 or (_VERGLEICH.search(text) and len(monate) != 1):
        return "zeitreihe"
    if _GESCHLECHT.search(text):
        return "geschlecht"
    return "bestand"


# --- Verstehen: was die Frage meint, und was StatAgent nicht auswerten kann (nie still falsch) -----------------

KANN = (
    "StatAgent beantwortet: Beschäftigungsverhältnisse je Monat oder Zeitraum, nach Bundesland, Geschlecht, "
    "Branche (ÖNACE-Abschnitt), Beschäftigungskategorie und Alter, dazu die Fluktuation je Branche und "
    "Begriffserklärungen."
)
#: Signalwörter für Merkmale, die es in den Daten der Anfrage nicht gibt: lieber ehrlich absagen als eine Zahl
#: ohne diese Einschränkung zu liefern. Sprachverständnis, kein Rechenregelwerk (docs/plan/uc3/annahmen.md).
ALTER_GRUND = (
    "Das Durchschnittsalter und Geburtsjahrgänge wertet StatAgent nicht aus. Es gibt Zahlen zu "
    "einem Alter oder einer Spanne, zum Beispiel „Beschäftigte unter 25 Jahren im Juli 2026“."
)
NICHT_AUSGEWERTET: tuple[tuple[re.Pattern[str], str], ...] = (
    # Dauer vor Alter prüfen: „seit über 2 Jahren beschäftigt“ ist keine Altersfrage, aber genauso nicht in den Daten.
    (
        re.compile(
            r"beschäftigungsdauer|\bseit\s+(?:(?:über|ueber|mehr als|unter|weniger als)\s+)?\d{1,3}\s*(?:jahre|jahren|monate|monaten)\b"
            r"|\b(?:über|ueber|unter|länger als|mehr als|weniger als)\s+\d{1,3}\s*(?:jahre|jahren|monate|monaten)\s+"
            r"(?:beschäftigt|angestellt|tätig|im job|im betrieb)"
        ),
        "Wie lange ein Beschäftigungsverhältnis schon besteht, wertet StatAgent bei Datenanfragen nicht aus.",
    ),
    (
        re.compile(
            r"\b(alter|altersgruppen?|lebensalter)\b(?!\s+(regel|regeln|version|fassung|stand|zählung|lieferung))"
            r"|durchschnittsalter|jahre alt|\bwie alt\b|\b\d{1,3}-?jährig|jugendlich|jahrgang|jahrgänge|geburtsjahr"
            r"|\b(unter|über|ueber|ab|bis)\s+\d{1,3}\s*(jahre|jahren)\b"
        ),
        ALTER_GRUND,
    ),
    (
        re.compile(r"durchschnitt|mittelwert|median"),
        "Durchschnitte rechnet StatAgent bei Datenanfragen nicht.",
    ),
    (re.compile(r"\blohn|löhne|gehalt|gehälter|einkommen|verdienst"), "Einkommen sind nicht in den Daten."),
    (re.compile(r"teilzeit|vollzeit|arbeitszeit|stunden"), "Die Arbeitszeit ist nicht in den Daten."),
    (re.compile(r"lehrling|lehre\b"), "Lehrlinge sind in dieser Statistik kein eigenes Merkmal."),
    (
        re.compile(r"staatsbürger|nationalität|ausländ|herkunftsland"),
        "Die Staatsbürgerschaft ist nicht in den Daten.",
    ),
)
_PERSON = re.compile(r"\bperson\b|personen-?id|\bid\b|\badresse|versicherungsnummer|\bsvnr\b")
#: Eine lange Zahl ist eine Kennung, außer sie ist eine Mengenangabe („über 10000“).
_LANGE_ZAHL = re.compile(r"(?:(\w+)\s+)?(?<![\d./])\d{5,}(?![\d./])")
_MENGENWORT = frozenset(
    {"über", "ueber", "unter", "mehr", "weniger", "als", "ab", "bis", "rund", "etwa", "von"}
)
#: Freie Dienstverträge: im Regelsatz v1 Qualifikationen mit Kennzeichen freier_dienstvertrag (ArbeiterFD,
#: AngestellteFD), im Sheet je Qualifikation ausgewiesen.
_FREIER_DV = re.compile(r"\bfreie[nmrs]?\s+(?:dienstv\w*|dv)\b|\bfd\b")
FREIER_DV = Merkmal(
    "freier Dienstvertrag",
    "q.freier_dienstvertrag",
    "SELECT 'true' AS code, 'freie Dienstverträge' AS bezeichnung",
    (),
    join_qualifikation=True,
)
#: Umgangssprachliche Branchennamen (nur ganze Wörter) → Anfang der ÖNACE-Bezeichnung; aufgelöst über die
#: Version des Monats (Gesundheit ist 2008 Abschnitt Q, 2025 Abschnitt R). Sprachverständnis, kein Rechenregelwerk.
BRANCHEN: tuple[tuple[re.Pattern[str], tuple[str, ...]], ...] = (
    (re.compile(r"\bbau(?:s|e|en|gewerbe|branche|wirtschaft)?\b"), ("Bau",)),
    (
        re.compile(r"\b(gastronomie|gastgewerbe|beherbergung|hotellerie|hotels?|tourismus)\b"),
        ("Beherbergung",),
    ),
    (re.compile(r"\bhandels?\b"), ("Handel",)),
    (
        re.compile(
            r"\b(gesundheit|gesundheitswesen|gesundheitsbereich|pflege|spitäler|spital|krankenhaus|krankenhäuser)\b"
        ),
        ("Gesundheits",),
    ),
    (re.compile(r"\b(industrie|herstellung|produktion|sachgüterproduktion)\b"), ("Herstellung von Waren",)),
    (
        re.compile(r"\b(it|it-branche|informatik|software|informationstechnologie)\b"),
        ("Telekommunikation, Softwareentwicklung", "Information und Kommunikation"),
    ),
    (re.compile(r"\b(verkehr|transport|logistik)\b"), ("Verkehr",)),
    (re.compile(r"\b(bildung|bildungswesen|schulen?|unterricht|erziehung)\b"), ("Erziehung",)),
    (re.compile(r"\b(öffentliche[nr]? verwaltung|verwaltung|behörden?)\b"), ("Öffentliche Verwaltung",)),
    (
        re.compile(r"\b(finanzen|finanzwesen|finanzdienstleistungen|banken?|versicherungen)\b"),
        ("Erbringung von Finanz",),
    ),
    (re.compile(r"\b(landwirtschaft|forstwirtschaft|agrar)\b"), ("Land- und Forstwirtschaft",)),
    (re.compile(r"\b(energie|energieversorgung|strom)\b"), ("Energieversorgung",)),
)
_FRAU = re.compile(r"\b(frau|frauen|weiblich\w*)\b")
_MANN = re.compile(r"\b(mann|männer|maenner|männlich\w*|maennlich\w*)\b")
#: Wortstämme nach „im/in/Branche“, die kein Merkmal meinen („in den Wirtschaftsbereichen“, „in Prozent“).
_KEIN_MERKMAL_STAMM = (
    "österreich", "oesterreich", "vergleich", "jahr", "monat", "zeitraum", "schnitt", "gesamt", "summe",
    "detail", "bundesl", "wirtschaftsbereich", "wirtschaftszweig", "abschnitt", "önace", "oenace",
    "berichtsmonat", "stichtag", "verlauf", "lauf", "bereich", "branche", "sektor", "prozent", "vormonat",
    "vorjahr", "zahl", "tabelle", "beschäftigungskategorie", "kategorie", "geschlecht", "alter",
)  # fmt: skip
_FUNKTIONSWORT = frozenset(
    {"im", "in", "der", "den", "dem", "die", "das", "welchem", "welcher", "welchen", "welche", "diesem",
     "dieser", "diesen", "ganz", "ganzen", "gesamten", "allen", "alle", "einem", "einer", "einen", "letzten",
     "letztem", "vergangenen", "laufenden", "form", "höhe", "hoehe", "relation", "bezug", "folge", "etwa",
     "zeit", "punkto", "und", "oder", "sowie"}
)  # fmt: skip
_ORT_KETTE = re.compile(
    r"\b(?:im|in der|in den|in|branche|bereich)\s+([\w-]+(?:\s*(?:,|\bund\b|\boder\b|\bsowie\b)\s*[\w-]+)*)",
    re.IGNORECASE,
)
_MONATSWORT = "|".join(sorted(map(re.escape, MONATSNAMEN), key=len, reverse=True))
_LETZTES_JAHR = re.compile(r"\b(?:im\s+)?letzte[nms]?\s+jahr(?:es)?\b", re.IGNORECASE)
_AKTUELL = re.compile(r"\b(aktuell|derzeit|zurzeit|momentan|jetzt)\b", re.IGNORECASE)
KATEGORIE = _merkmal("Beschäftigungskategorie")


def normalisieren(frage: str, letzter: str = LETZTE_LIEFERUNG) -> tuple[str, list[str]]:
    """Zeitangaben der Alltagssprache in Monate übersetzen; dazu Sätze, die das Verstandene offenlegen."""
    frage, notizen, _ = _normalisieren(frage, letzter)
    return frage, notizen


def _normalisieren(frage: str, letzter: str) -> tuple[str, list[str], bool]:
    """Wie ``normalisieren``, dazu ob ein Durchschnitt über mehrere Monate gemeint ist.

    Jahreszeiten, Quartale, Halbjahre, Bereiche („März bis Juni 2025“, „November bis Februar 2025“ beginnt im
    Vorjahr), „Anfang/Mitte/Ende 2025“, Monate ohne Jahr und „letzten Monat“ übersetzt ``statagent.zeitraum``
    (``letzter`` ist der jüngste Monat mit Daten). „letztes Jahr“ ist das Jahr vor der letzten Lieferung.
    „Jahresdurchschnitt 2025“ wird zu Jänner bis Dezember 2025; eine bloße Jahreszahl bleibt (Rückfrage, #74 AC2).
    """
    frage, notizen, mittel = umschreiben(frage, letzter)
    if _LETZTES_JAHR.search(frage):
        vorjahr = str(int(LETZTE_LIEFERUNG[:4]) - 1)  # das Jahr vor der letzten Lieferung der Aufgabe
        frage = _LETZTES_JAHR.sub(f" {vorjahr} ", frage)
        notizen.append(f"„Letztes Jahr“ heißt hier {vorjahr}.")
    jahr = jahr_ohne_monat(frage)
    if mittel and jahr is not None and not monate_lesen(frage):
        frage = re.sub(rf"(?<!\d){jahr}(?!\d)", f"Jänner {jahr} bis Dezember {jahr}", frage, count=1)
        notizen.append(f"Gemeint ist der Durchschnitt der Monate Jänner bis Dezember {jahr}.")
    return frage, notizen, mittel


# --- Alter: Spalte stat.stat_beschaeftigte.alter (Regel R5), Altersgruppen aus stat.klass_alter wie im Sheet ------
ALTERSGRUPPE = Merkmal(
    "Alter",
    "(SELECT a.berichtsgruppe FROM stat.klass_alter a WHERE a.code = s.alter)",
    "SELECT DISTINCT berichtsgruppe AS code, CASE WHEN berichtsgruppe ~ '^[0-9]+$' THEN berichtsgruppe || ' Jahre'"
    " ELSE berichtsgruppe END AS bezeichnung FROM stat.klass_alter",
    ("alter",),
)
_ALTER_GRUPPEN = re.compile(
    r"\b(?:nach|je|pro)\s+(?:\w+\s+)?(?:alter|altersgruppen?)\b|\baltersgruppen\b|\baltersverteilung\b"
)
_ALTER_NICHT = re.compile(r"durchschnittsalter|jugendlich|jahrgang|jahrgänge|geburtsjahr")
_JAHRE = r"\s*-?\s*(?:jahren?|jährig\w*)"
#: (Muster, Grenzen aus den Gruppen, Wortlaut). Höchstalter wie die Klassifikation.
_ALTER_HOECHST = 130
_ALTER_MUSTER: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"\bim\s+alter\s+von\s+(\d{1,3})\s*(?:bis|und)\s*(\d{1,3})\b"), "spanne"),
    (re.compile(rf"\b(?:zwischen\s+)?(\d{{1,3}})\s*-?\s*(?:bis|und|–|—|-)\s*(\d{{1,3}}){_JAHRE}"), "spanne"),
    (re.compile(rf"\b(?:jünger als|juenger als)\s+(\d{{1,3}})(?:{_JAHRE})?"), "unter"),
    (re.compile(rf"\bunter\s+(\d{{1,3}}){_JAHRE}"), "unter"),
    (re.compile(rf"\b(?:älter als|aelter als)\s+(\d{{1,3}})(?:{_JAHRE})?"), "ueber"),
    (re.compile(rf"\b(?:über|ueber)\s+(\d{{1,3}}){_JAHRE}"), "ueber"),
    (re.compile(rf"\bab\s+(\d{{1,3}}){_JAHRE}"), "ab"),
    (re.compile(rf"\bbis\s+(\d{{1,3}}){_JAHRE}"), "bis"),
    # Ohne „Jahre“ nur direkt vor der Zeitangabe oder am Satzende: „über 2000 Beschäftigte“ ist eine Menge.
    (re.compile(r"\bunter\s+(\d{2})(?=\s*(?:$|[?.,]|im\b|in\b|am\b|von\b))"), "unter"),
    (re.compile(r"\b(?:über|ueber)\s+(\d{2})(?=\s*(?:$|[?.,]|im\b|in\b|am\b|von\b))"), "ueber"),
    (re.compile(r"\bim\s+alter\s+von\s+(\d{1,3})\b"), "genau"),
    (re.compile(r"\b(\d{1,3})\s*-?\s*jährig\w*"), "genau"),
    (re.compile(r"\b(\d{1,3})\s+jahre\s+alt\b"), "genau"),
)


def _alter_lesen(frage: str) -> tuple[Merkmal, str, str] | None:
    """Genau eine Altersangabe als Filter (Merkmal, Code, Etikett); bei keiner oder mehreren None (dann Absage)."""
    text = frage.lower()
    if _ALTER_NICHT.search(text):
        return None
    gefunden: list[tuple[str, int, int]] = []
    for muster, art in _ALTER_MUSTER:
        for t in muster.finditer(text):
            zahlen = [int(g) for g in t.groups()]
            gefunden.append((art, zahlen[0], zahlen[-1]))
        text = muster.sub(lambda m: " " * len(m.group(0)), text)
    if len(gefunden) != 1:
        return None
    art, a, b = gefunden[0]
    von, bis, etikett = {
        "spanne": (a, b, f"{a} bis {b} Jahre"),
        "unter": (0, a - 1, f"unter {a} Jahre"),
        "ueber": (a + 1, _ALTER_HOECHST, f"über {a} Jahre"),
        "ab": (a, _ALTER_HOECHST, f"ab {a} Jahre"),
        "bis": (0, a, f"bis {a} Jahre"),
        "genau": (a, a, f"{a} Jahre"),
    }[art]
    if not 0 <= von <= bis <= _ALTER_HOECHST:
        return None
    # von und bis sind ganze Zahlen aus der Frage.
    return Merkmal("Alter", f"(s.alter BETWEEN {von} AND {bis})", "", ()), "true", etikett


def nicht_auswertbar(frage: str, mittel: bool = False) -> str | None:
    """Absagetext, wenn die Frage Einzeldaten oder ein Merkmal verlangt, das es nicht gibt; sonst None.

    ``mittel``: die Frage nennt einen Zeitraum aus mehreren Monaten, ein Durchschnitt über die Monate ist dann
    gemeint und auswertbar (das Durchschnittsalter bleibt abgesagt).
    """
    text = frage.lower()
    kennung = any((t.group(1) or "") not in _MENGENWORT for t in _LANGE_ZAHL.finditer(text))
    if _PERSON.search(text) or kennung:
        return "Einzeldaten gibt StatAgent nicht heraus, auch nicht zu einer einzelnen Person. " + KANN
    alter_lesbar = not _ALTER_NICHT.search(text) and (
        _alter_lesen(text) is not None or _ALTER_GRUPPEN.search(text) is not None
    )
    for muster, grund in NICHT_AUSGEWERTET:
        if grund is ALTER_GRUND and alter_lesbar:
            continue
        if mittel and grund.startswith("Durchschnitte") and "median" not in text:
            continue
        if muster.search(text):
            # Das Beispiel der Alters-Absage sagt schon, was geht.
            return grund if grund is ALTER_GRUND else f"{grund} Darum gibt es hier keine Zahl. {KANN}"
    return None


def _treffer(text: str, bezeichnung: str) -> re.Match[str] | None:
    return re.search(rf"(?<!\w){re.escape(bezeichnung.lower())}(?:e|n|en)?(?!\w)", text)


def _werte(frage: str, merkmal: Merkmal, codes: dict[str, str]) -> tuple[list[str], list[str]]:
    """Alle in der Frage genannten Codes eines Merkmals und die Textstellen, die sie getroffen haben."""
    text = frage.lower()
    gefunden: dict[str, str] = {}
    for code, bezeichnung in codes.items():
        t = _treffer(text, bezeichnung)
        if t:
            gefunden[code] = t.group(0)
    if merkmal is GESCHLECHT:
        for code, muster in (("W", _FRAU), ("M", _MANN)):
            t = muster.search(text)
            if t and code in codes:
                gefunden.setdefault(code, t.group(0))
    if merkmal is OENACE:
        for t in _OENACE_CODE.finditer(text):
            if t.group(1).upper() in codes:
                gefunden[t.group(1).upper()] = t.group(0)
        # „ÖNACE C und F“: alle Buchstaben, sonst zählte nur der erste, ohne Hinweis.
        for liste in _OENACE_LISTE.finditer(text):
            for t in re.finditer(r"(?<!\w)[a-z](?!\w)", liste.group(1)):
                if t.group(0).upper() in codes:
                    gefunden.setdefault(t.group(0).upper(), liste.group(0))
        for muster, anfaenge in BRANCHEN:
            t = muster.search(text)
            if not t:
                continue
            branche = next(
                (c for a in anfaenge for c, b in codes.items() if b.startswith(a)),
                None,
            )
            if branche is None:
                raise _KeineZahl(
                    f"Die Branche „{t.group(0)}“ gibt es in der ÖNACE-Version dieses Monats nicht. {KANN}"
                )
            gefunden.setdefault(branche, t.group(0))
    # Ein Name, der in einem längeren genannten Namen steckt, zählt nicht extra.
    doppelt = {c for c in gefunden for d in gefunden if c != d and codes[c].lower() in codes[d].lower()}
    werte = [c for c in gefunden if c not in doppelt]
    return werte, list(gefunden.values())


def _wort_bekannt(wort: str, erkannt: list[str]) -> bool:
    """Ein Wort nach „im/in/Branche“ ist bekannt, wenn es ein Monat, ein Füllwort oder ein erkanntes Merkmal ist.

    Erkannt heißt: das Wort ist der Anfang einer erkannten Wendung („Gesundheits-“ in „Gesundheits- und
    Sozialwesen“) oder eine erkannte Wendung mit höchstens zwei Buchstaben Endung („Wiens“). Eine Zusammensetzung
    („Produktionslauf“, „Hausverwaltung“) ist damit unbekannt.
    """
    klein = wort.lower().strip("-")
    if not klein or klein.isdigit() or klein in MONATSNAMEN or klein in _FUNKTIONSWORT:
        return True
    if any(klein.startswith(stamm) for stamm in _KEIN_MERKMAL_STAMM):
        return True
    for e in (x.lower() for x in erkannt):
        if (len(klein) >= 3 and e.startswith(klein)) or (klein.startswith(e) and len(klein) - len(e) <= 2):
            return True
        # Teil einer mehrwortigen erkannten Wendung („Sozialwesen“ in „Gesundheits- und Sozialwesen“).
        if len(klein) >= 3 and re.search(rf"(?<!\w){re.escape(klein)}(?!\w)", e):
            return True
    return False


def _verstanden(
    von: str, bis: str, filter_: list[tuple[Merkmal, str]], etiketten: list[str], gruppen: tuple[Merkmal, ...]
) -> str:
    zeit = _monat_anzeige(von) if von == bis else f"{_monat_anzeige(von)} bis {_monat_anzeige(bis)}"
    gefiltert = {m.name: (code, e) for (m, code), e in zip(filter_, etiketten, strict=True)}
    teile = [zeit]
    for merkmal, wort in (
        (BUNDESLAND, "Bundesland"),
        (GESCHLECHT, "Geschlecht"),
        (OENACE, "Branche"),
        (KATEGORIE, "Beschäftigungskategorie"),
    ):
        if merkmal in gruppen:
            teile.append(f"je {wort}")
        elif merkmal.name in gefiltert:
            code, etikett = gefiltert[merkmal.name]
            teile.append(f"{wort} {code} {etikett}" if merkmal is OENACE else f"{wort} {etikett}")
        else:
            teile.append(f"{wort}: alle")
    if FREIER_DV.name in gefiltert:
        teile.append("nur freie Dienstverträge")
    if "Alter" in gefiltert:
        teile.append(f"Alter {gefiltert['Alter'][1]}")
    if ALTERSGRUPPE in gruppen:
        teile.append("je Alter")
    return "Verstanden: " + ", ".join(teile) + "."


def _geschlecht_gegliedert(text: str) -> bool:
    """Männer und Frauen getrennt (beide genannt, „Geschlecht“ oder ein Anteil); sonst ist es ein Filter."""
    beide = bool(_MANN.search(text)) and bool(_FRAU.search(text))
    return beide or "geschlecht" in text or "anteil" in text


# --- Bausteine ------------------------------------------------------------------------------------------------


def _anzahl_monate(anzahl: int) -> str:
    return "1 Monat" if anzahl == 1 else f"{anzahl} Monate"


def _komma(wert: float) -> str:
    return f"{wert:.2f}".replace(".", ",")


def _antwort(
    typ: str,
    text: str,
    *,
    definition: str | None = None,
    einheit: str | None = None,
    stand: list[dict[str, Any]] | None = None,
    belege: list[dict[str, Any]] | None = None,
    zahlen: list[dict[str, Any]] | None = None,
    hinweise: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "typ": typ,
        "text": text,
        "rueckfrage": typ == "rueckfrage",
        "definition": definition,
        "einheit": einheit,
        "stand": stand or [],
        "hinweise": hinweise or [],
        "belege": belege or [],
        "zahlen": zahlen or [],
        "uc": UC,
        "modell": None,
        "protokoll_id": None,
    }


def als_ucantwort(daten: dict[str, Any]) -> dict[str, Any]:
    """Nur die Felder der ``UcAntwort`` (plattform.antwortform)."""
    return {k: daten[k] for k in UC_FELDER}


def als_webantwort(daten: dict[str, Any]) -> dict[str, Any]:
    """JSON für die Webseite /uc3/fragen (``uc3 frage --json``): UcAntwort plus ``definition`` und ``rueckfrage``.

    Die Seite prüft den Rest streng gegen ``ucAntwortSchema`` (shared/ui/src/antwortform.ts, ``.strict()``), darum
    keine weiteren Felder. Einheit und Stand stehen je Zahl und je Beleg; Hinweise, die noch nicht im Text stehen,
    kommen an den Text. ``rueckfrage`` ist der Text der Rückfrage oder None.
    """
    text = " ".join([daten["text"], *(h for h in daten["hinweise"] if h not in daten["text"])])
    return {
        **als_ucantwort(daten),
        "text": text,
        "definition": daten["definition"],
        "rueckfrage": text if daten["rueckfrage"] else None,
    }


#: Wörter, die eine Frage nach dem Bestand erkennen lassen.
_BEZUG = re.compile(
    r"beschäftig|beschaeftig|verhältnis|verhaeltnis|arbeit|leute|personen|menschen|\bjobs?\b|\bstellen\b"
    r"|wie\s*viele?\b|anzahl|bestand|\bstand\b|aktuell|derzeit|zurzeit|momentan|jetzt"
)


def _ohne_bezug(conn: Verbindung, frage: str, letzter: str) -> bool:
    """Weder ein Wort zum Bestand noch ein Merkmal, und außer der Zeitangabe stehen andere Wörter da.

    „März 2025“ allein bleibt eine Frage nach dem Bestand, „asdf im März 2025“ nicht. ``_filter`` sagt ab, wenn nach
    „in“ ein unbekanntes Wort steht („in Wein“, „in Vienna“), auch bei einer bloßen Jahreszahl.
    """
    text = frage.lower()
    genannt = monate_lesen(frage)
    if _filter(conn, frage, genannt[-1] if genannt else letzter, ())[0]:
        return False
    if _BEZUG.search(text) or _gliederung(frage) is not None:
        return False
    jahr = jahr_ohne_monat(frage)
    if not genannt and jahr is None:
        return True
    for muster in (_NAME_MONAT, _ZAHL_MONAT, _ISO):
        text = muster.sub(" ", text)
    if jahr is not None:
        text = text.replace(jahr, " ")
    return any(w not in _FUNKTIONSWORT and w != "bitte" for w in re.findall(r"[\wäöüß-]+", text))


def _rueckfrage(text: str) -> dict[str, Any]:
    return _antwort("rueckfrage", text)


def _beleg(sql_text: str, staende: list[dict[str, Any]], hash_: str | None = None) -> dict[str, Any]:
    monate = sorted({str(s["monat"]) for s in staende})
    regelstaende = sorted({str(s["regelstand"]) for s in staende})
    status = [str(s["status"]) for s in staende]
    return {
        "uc": UC,
        "quelle": QUELLE,
        "lieferung": monate[0] if len(monate) == 1 else None,
        "monat": monate[0] if len(monate) == 1 else None,
        "sql": sql_text,
        "ref": ", ".join(f"meta.lauf/{s['lauf']} regelstand {s['regelstand']}" for s in staende) or None,
        "regelstand": regelstaende[0] if len(regelstaende) == 1 else None,
        "lauf": hash_,
        "stand": ("endgueltig" if all(s == "endgueltig" for s in status) else "vorlaeufig")
        if status
        else None,
    }


def _status_text(staende: list[dict[str, Any]]) -> str:
    """„endgültig“, „vorläufig“ oder „teils endgültig, teils vorläufig (vorläufig: August 2024, …)“."""
    offen = [s for s in staende if s["status"] != "endgueltig"]
    if not offen:
        return "endgültig"
    if len(offen) == len(staende):
        werte = {_STATUS_TEXT.get(str(s["status"]), str(s["status"])) for s in offen}
        return " und ".join(sorted(werte))
    monate = ", ".join(_monat_anzeige(str(s["monat"])) for s in offen)
    return f"teils endgültig, teils vorläufig (vorläufig: {monate})"


#: Anfang der Absage bei zwei Werten eines Merkmals; UC4 zeigt in diesem Fall je Wert eine Zahl (#125).
_MEHRZAHL = {
    "Bundesland": "Bundesländer",
    "Geschlecht": "Geschlechter",
    "ÖNACE-Abschnitt": "Branchen",
    "Beschäftigungskategorie": "Beschäftigungskategorien",
}
MEHRERE_WERTE = tuple(f"Die Frage nennt mehrere {w}:" for w in _MEHRZAHL.values())


class _KeineZahl(Exception):
    """Die Frage ist verstanden, aber ohne Zahl zu beantworten; die Nachricht ist der Text für Laien."""


class _Abgeschnitten(Exception):
    """sql_lesen hat nach HOECHSTENS_ZEILEN abgeschnitten: nie eine Teilsumme ausgeben."""


def _lesen(conn: Verbindung, sql_text: str) -> list[dict[str, Any]]:
    ergebnis = sql_lesen(conn, sql_text)
    if ergebnis["abgeschnitten"]:
        raise _Abgeschnitten
    zeilen: list[dict[str, Any]] = ergebnis["zeilen"]
    return zeilen


def _tag_anzeige(tag: date) -> str:
    return f"{tag.day}. {_monat_anzeige(f'{tag.year:04d}-{tag.month:02d}')}"


def _ohne_lieferung(monat: str) -> bool:
    return monat < ERSTE_LIEFERUNG or monat > LETZTE_LIEFERUNG


def _kein_lauf_text(monat: str) -> str:
    if _ohne_lieferung(monat):
        return (
            f"Für {_monat_anzeige(monat)} gibt es keine Lieferung, also auch keine Zahl. Daten gibt es nur für "
            f"{zeitraum_anzeige(ERSTE_LIEFERUNG, LETZTE_LIEFERUNG)}. Meinen Sie "
            f"„Beschäftigte im {_monat_anzeige(min(max(monat, ERSTE_LIEFERUNG), LETZTE_LIEFERUNG))}“?"
        )
    return (
        f"{_monat_anzeige(monat)} ist noch nicht gerechnet. Was tun: den Lauf für den Monat starten "
        f"(uc3 lauf --lieferung {monat}) und dann noch einmal fragen."
    )


def _oenace_version(conn: Verbindung, monat: str) -> tuple[str, str] | None:
    """ÖNACE-Version (Abschnitte), die im Monat gilt, mit ihrem ersten Monat."""
    zeile = conn.execute(
        """SELECT version, to_char(min(gueltig_von), 'YYYY-MM') AS ab FROM stat.klass_oenace
           WHERE ebene = 1 AND gueltig_von <= %s AND (gueltig_bis IS NULL OR gueltig_bis >= %s)
           GROUP BY version ORDER BY version DESC LIMIT 1""",
        (monatsletzter(monat), monatserster(monat)),
    ).fetchone()
    return None if zeile is None else (str(zeile["version"]), str(zeile["ab"]))


def _laufinfo(conn: Verbindung, regelsatz: str, staende: list[dict[str, Any]]) -> dict[int, tuple[int, bool]]:
    """Je Lauf: fortgeschriebene Beschäftigungsverhältnisse (E07) und ob es Zahlen am Stichtag gibt."""
    if not staende:
        return {}
    zeilen = conn.execute(
        """SELECT l.id, l.fortgeschrieben, EXISTS (
             SELECT 1 FROM stat.stat_beschaeftigte s WHERE s.regelsatz = l.regelsatz AND s.regelstand = l.regelstand
               AND s.zeitraum_art = %s AND s.variable = %s AND to_char(s.zeitraum_bis, 'YYYY-MM') = l.lieferung
           ) AS stichtag
           FROM meta.lauf l WHERE l.regelsatz = %s AND l.id = ANY(%s)""",
        (STICHTAG, STICHTAG_VARIABLE, regelsatz, [int(s["lauf"]) for s in staende]),
    ).fetchall()
    return {int(str(z["id"])): (int(str(z["fortgeschrieben"])), bool(z["stichtag"])) for z in zeilen}


def _filter(
    conn: Verbindung, frage: str, monat: str, ohne: tuple[Merkmal, ...]
) -> tuple[list[tuple[Merkmal, str]], list[str]]:
    """Ausprägungen der Frage (z. B. „Wien“, „ÖNACE F“, „Gastronomie“) als Filter, außer für gegliederte Merkmale.

    Nie still falsch: Zwei Werte eines Merkmals („Wien und Tirol“) oder ein Wort nach „im/in“, das kein Merkmal
    ergibt („im Bergbaubetrieb“), führen zu einer Absage statt zu einer Zahl für etwas anderes.
    """
    filter_: list[tuple[Merkmal, str]] = []
    etiketten: list[str] = []
    erkannt: list[str] = []
    for merkmal in MERKMALE:
        codes = _codes(conn, merkmal, monat)
        werte, stellen = _werte(frage, merkmal, codes)
        erkannt += stellen
        if merkmal in ohne or not werte:
            continue
        if len(werte) > 1:
            namen = " und ".join(codes[c] for c in werte)
            raise _KeineZahl(
                f"Die Frage nennt mehrere {_MEHRZAHL[merkmal.name]}: {namen}. Eine Zahl für alle zusammen wäre "
                f"missverständlich. Bitte getrennt fragen oder alle auf einmal mit „je {merkmal.name}“."
            )
        filter_.append((merkmal, werte[0]))
        etiketten.append(codes[werte[0]])
    if _FREIER_DV.search(frage.lower()):
        filter_.append((FREIER_DV, "true"))
        etiketten.append("freie Dienstverträge")
        erkannt.append("freie dienstverträge")
    alter = _alter_lesen(frage)
    if alter is not None:
        filter_.append((alter[0], alter[1]))
        etiketten.append(alter[2])
        erkannt.append(alter[2])
    for kette in _ORT_KETTE.findall(frage):
        for wort in re.split(r"\s*(?:,|\bund\b|\boder\b|\bsowie\b)\s*", kette, flags=re.IGNORECASE):
            if not _wort_bekannt(wort, erkannt):
                raise _KeineZahl(f"Das Wort „{wort}“ kenne ich nicht als Bundesland oder Branche. {KANN}")
    return filter_, etiketten


def bestand_sql(
    conn: Verbindung,
    regelsatz: str,
    von: str,
    bis: str,
    filter_: list[tuple[Merkmal, str]],
    gruppen: tuple[Merkmal, ...],
) -> str:
    """SELECT je Monat (von bis bis) und Gliederung: Bestand am Stichtag aus dem maßgeblichen Lauf des Monats.

    Maßgeblich wie ``ergebnis.letzter_lauf``: jüngster veröffentlichter Lauf, sonst jüngster erfolgreicher.
    Monate ohne Lauf fehlen im Ergebnis; Filter stehen in der Join-Bedingung, damit ein Monat ohne Treffer 0 zeigt.
    """
    bedingungen = [
        sql.SQL("s.regelsatz = {}").format(sql.Literal(regelsatz)),
        sql.SQL("s.regelstand = l.regelstand"),
        sql.SQL("s.zeitraum_art = {}").format(sql.Literal(STICHTAG)),
        sql.SQL("s.variable = {}").format(sql.Literal(STICHTAG_VARIABLE)),
        sql.SQL("to_char(s.zeitraum_bis, 'YYYY-MM') = l.lieferung"),
    ]
    for merkmal, code in filter_:
        bedingungen.append(sql.SQL("{} = {}").format(sql.SQL(merkmal.spalte), sql.Literal(code)))
    join_q = any(m.join_qualifikation for m, _ in filter_) or any(g.join_qualifikation for g in gruppen)
    tabelle = sql.SQL(
        "(stat.stat_beschaeftigte s LEFT JOIN stat.klass_qualifikation q ON q.code = s.qualifikation)"
        if join_q
        else "stat.stat_beschaeftigte s"
    )
    spalten = sql.SQL("").join(
        sql.SQL(", {} AS {}").format(sql.SQL(g.spalte), sql.Identifier(f"g{i}"))
        for i, g in enumerate(gruppen)
    )
    gruppe_nr = sql.SQL("").join(sql.SQL(", {}").format(sql.Literal(5 + i)) for i in range(len(gruppen)))
    abfrage = sql.SQL(
        "WITH lauf AS ("
        "SELECT DISTINCT ON (l.lieferung) l.id, l.lieferung, l.regelstand, l.ergebnis_status FROM meta.lauf l"
        " WHERE l.regelsatz = {rs} AND l.status IN ('fertig', 'unveraendert') AND l.lieferung BETWEEN {von} AND {bis}"
        " ORDER BY l.lieferung, (l.ergebnis_status = 'endgueltig') DESC, l.id DESC)"
        " SELECT l.lieferung AS monat, l.id AS lauf, l.regelstand, l.ergebnis_status AS status{spalten},"
        " COALESCE(sum(s.wert), 0)::bigint AS wert"
        " FROM lauf l LEFT JOIN {tabelle} ON {bedingungen}"
        " GROUP BY 1, 2, 3, 4{gruppe_nr} ORDER BY 1{gruppe_nr}"
    ).format(
        rs=sql.Literal(regelsatz),
        von=sql.Literal(von),
        bis=sql.Literal(bis),
        spalten=spalten,
        tabelle=tabelle,
        bedingungen=sql.SQL(" AND ").join(bedingungen),
        gruppe_nr=gruppe_nr,
    )
    return abfrage.as_string(conn)


def _staende(zeilen: list[dict[str, Any]]) -> list[dict[str, Any]]:
    gesehen: dict[str, dict[str, Any]] = {}
    for z in zeilen:
        gesehen.setdefault(
            str(z["monat"]),
            {"monat": z["monat"], "lauf": z["lauf"], "regelstand": z["regelstand"], "status": z["status"]},
        )
    return [gesehen[m] for m in sorted(gesehen)]


def _definition_bestand(conn: Verbindung) -> tuple[str, str]:
    zeile = conn.execute(
        "SELECT beschreibung, einheit FROM stat.variable WHERE statistik = 'beschaeftigte' AND code = %s",
        (STICHTAG_VARIABLE,),
    ).fetchone()
    if zeile is None:
        return "Beschäftigungsverhältnisse am Stichtag (Monatsletzter).", "Anzahl"
    return str(zeile["beschreibung"]), str(zeile["einheit"])


def _laien_bestand() -> str:
    return (
        "Gezählt werden Beschäftigungsverhältnisse am letzten Tag des Monats; "
        "wer zwei Jobs hat, zählt zweimal."
    )


# --- Antworten je Fragetyp ------------------------------------------------------------------------------------


def _bestand_antwort(
    conn: Verbindung,
    frage: str,
    regelsatz: str,
    von: str,
    bis: str,
    gruppen: tuple[Merkmal, ...],
    typ: str,
    mittel: bool = False,
) -> dict[str, Any]:
    definition, einheit = _definition_bestand(conn)
    filter_, etiketten = _filter(conn, frage, bis, gruppen)
    verstanden = _verstanden(von, bis, filter_, etiketten, gruppen)
    if any(m is FREIER_DV for m, _ in filter_) and regelsatz != "v1":
        raise _KeineZahl(
            f"Freie Dienstverträge kann die Datenanfrage nur im Regelsatz v1 trennen, nicht in {regelsatz}. {KANN}"
        )
    if OENACE in gruppen or any(m is OENACE for m, _ in filter_):
        v_von, v_bis = _oenace_version(conn, von), _oenace_version(conn, bis)
        if v_von and v_bis and v_von[0] != v_bis[0]:
            letzter_alt = monat_verschieben(v_bis[1], -1)
            raise _KeineZahl(
                f"Die Wirtschaftsbereiche (ÖNACE) wurden neu eingeteilt: bis {_monat_anzeige(letzter_alt)} gilt "
                f"ÖNACE {v_von[0]}, ab {_monat_anzeige(v_bis[1])} ÖNACE {v_bis[0]}. Gleiche Buchstaben meinen "
                "dort teils andere Bereiche, eine Reihe über den Wechsel hinweg wäre irreführend. Bitte getrennt "
                f"fragen: von {_monat_anzeige(von)} bis {_monat_anzeige(letzter_alt)} und von "
                f"{_monat_anzeige(v_bis[1])} bis {_monat_anzeige(bis)}."
            )
    # Ein Ergebnis über HOECHSTENS_ZEILEN liest sql_lesen nur abgeschnitten: dann je Monat eine Abfrage.
    abfragen: list[tuple[str, list[dict[str, Any]]]] = []
    sql_text = bestand_sql(conn, regelsatz, von, bis, filter_, gruppen)
    try:
        abfragen.append((sql_text, _lesen(conn, sql_text)))
    except _Abgeschnitten:
        monate = _monate(von, bis)
        if len(monate) > 120:
            raise _KeineZahl(
                "Der Zeitraum ist für eine Antwort zu lang. Bitte höchstens zehn Jahre auf einmal fragen."
            ) from None
        for monat in monate:
            text_m = bestand_sql(conn, regelsatz, monat, monat, filter_, gruppen)
            try:
                zeilen_m = _lesen(conn, text_m)
            except _Abgeschnitten:
                raise _KeineZahl(
                    f"Für {_monat_anzeige(monat)} wären es zu viele Zahlen für eine Antwort. Bitte enger fragen, "
                    "zum Beispiel mit weniger Aufteilungen oder für ein Bundesland."
                ) from None
            if zeilen_m:
                abfragen.append((text_m, zeilen_m))
    alle = [z for _, zeilen in abfragen for z in zeilen]
    staende = _staende(alle)
    info = _laufinfo(conn, regelsatz, staende)
    for s in staende:
        s["fortgeschrieben"] = info.get(int(s["lauf"]), (0, True))[0]
    hinweise: list[str] = []
    ohne_stichtag = {str(s["monat"]) for s in staende if not info.get(int(s["lauf"]), (0, True))[1]}
    if ohne_stichtag:
        hinweise.append(
            f"Für {', '.join(_monat_anzeige(m) for m in sorted(ohne_stichtag))} zählt der Lauf nicht am Stichtag "
            "(letzter Tag des Monats); dafür gibt es hier keine Zahl."
        )
    fehlend = [m for m in _monate(von, bis) if m not in {str(s["monat"]) for s in staende}]
    keine_lieferung = [m for m in fehlend if _ohne_lieferung(m)]
    ungerechnet = [m for m in fehlend if not _ohne_lieferung(m)]
    for monate, wie in (
        (keine_lieferung, "gibt es keine Lieferung"),
        (ungerechnet, "gibt es noch keinen Lauf"),
    ):
        if monate:
            hinweise.append(
                f"Für {_anzahl_monate(len(monate))} im Zeitraum {wie}: "
                + ", ".join(_monat_anzeige(m) for m in monate[:6])
                + (" und weitere" if len(monate) > 6 else "")
                + "."
            )
    hinweise += [
        _fortgeschrieben_hinweis(str(s["monat"]), int(s["fortgeschrieben"]))
        for s in staende
        if s["fortgeschrieben"] and str(s["monat"]) not in ohne_stichtag
    ]
    belege: list[dict[str, Any]] = []
    zahlen: list[dict[str, Any]] = []
    gezaehlt: list[dict[str, Any]] = []
    labels: dict[tuple[str, str], dict[str, str]] = {}
    zusatz = f" ({', '.join(etiketten)})" if etiketten else ""
    for text_q, zeilen in abfragen:
        staende_q = _staende(zeilen)
        hash_ = None
        if len(staende_q) == 1:
            stand = letzter_lauf(conn, str(staende_q[0]["monat"]), regelsatz)
            hash_ = stand.ergebnis_hash if stand and stand.lauf_id == staende_q[0]["lauf"] else None
        belege.append(_beleg(text_q, staende_q, hash_))
        for z in zeilen:
            monat = str(z["monat"])
            if monat in ohne_stichtag or (gruppen and z["g0"] is None):
                continue  # keine Stichtagszahl, oder Monat ohne Zeile für die Gliederung
            gezaehlt.append(z)
            teile = [_monat_anzeige(monat)] if von != bis else []
            for i, g in enumerate(gruppen):
                code = str(z[f"g{i}"])
                # Bezeichnung aus der Klassifikationsversion des Monats der Zeile (ÖNACE 2008 oder 2025).
                namen = labels.setdefault((g.name, monat), _codes(conn, g, monat))
                teile.append(
                    namen.get(code, code) if g is not OENACE else f"{code} {namen.get(code, '')}".strip()
                )
            zahlen.append(
                {
                    "bezeichnung": "Beschäftigungsverhältnisse"
                    + zusatz
                    + (f", {', '.join(teile)}" if teile else ""),
                    "wert": int(z["wert"]),
                    "einheit": einheit,
                    "beleg": len(belege) - 1,
                }
            )
    if not zahlen:
        if von == bis and not staende:
            text = _kein_lauf_text(von)
        else:
            zeitraum = (
                _monat_anzeige(von) if von == bis else f"{_monat_anzeige(von)} bis {_monat_anzeige(bis)}"
            )
            text = f"Für {zeitraum} gibt es keine Zahl."
        return _antwort(
            typ,
            " ".join([verstanden, text, *hinweise]),
            definition=definition,
            einheit=einheit,
            stand=staende,
            belege=belege or [_beleg(sql_text, [])],
            hinweise=hinweise,
        )
    gezaehlte_staende = [s for s in staende if str(s["monat"]) not in ohne_stichtag]
    text = _text_bestand(typ, gezaehlt, gruppen, labels, zusatz)
    je_monat = sorted({str(z["monat"]) for z in gezaehlt})
    if mittel and len(je_monat) > 1:
        if gruppen:
            text += " Einen Durchschnitt gibt es hier nur ohne Aufteilung."
        else:
            # Durchschnitt als eigene Abfrage über die Monatszahlen (eigener Beleg), wie in statagent.uc4.
            quelle = " UNION ALL ".join(f"({text_q})" for text_q, _ in abfragen)
            gezaehlte_monate = sql.SQL(", ").join(sql.Literal(m) for m in je_monat).as_string(conn)
            mittel_sql = f"SELECT round(avg(t.wert))::bigint AS wert FROM ({quelle}) t WHERE t.monat IN ({gezaehlte_monate})"
            durchschnitt = int(_lesen(conn, mittel_sql)[0]["wert"])
            belege.append(_beleg(mittel_sql, [s for s in staende if str(s["monat"]) in je_monat]))
            zeitraum = (
                zeitraum_anzeige(je_monat[0], je_monat[-1])
                if je_monat == _monate(je_monat[0], je_monat[-1])
                else _aufzaehlung([_monat_anzeige(m) for m in je_monat])
            )
            zahlen.append(
                {
                    "bezeichnung": f"Beschäftigungsverhältnisse{zusatz}, Durchschnitt {zeitraum}",
                    "wert": durchschnitt,
                    "einheit": einheit,
                    "beleg": len(belege) - 1,
                }
            )
            text += (
                f" Im Durchschnitt waren es {_deutsch(durchschnitt)} "
                f"(Mittelwert der {_anzahl_monate(len(je_monat))}, auf ganze Zahlen gerundet)."
            )
    if "anteil" in frage.lower() and gruppen == (GESCHLECHT,) and von == bis:
        summe = sum(int(z["wert"]) for z in zahlen)
        anteile = []
        for z in list(zahlen):
            if summe > 0:
                wert = round(100.0 * int(z["wert"]) / summe, 2)
                name = z["bezeichnung"].rsplit(", ", 1)[-1]
                zahlen.append(
                    {**z, "bezeichnung": f"Anteil an allen, {name}", "wert": wert, "einheit": "Prozent"}
                )
                anteile.append(f"{name} {_komma(wert)} Prozent")
        if anteile:
            text += " Anteil an allen: " + ", ".join(anteile) + "."
    if gruppen == (ALTERSGRUPPE,) and von == bis:
        # Summe aller Alter für die letzte Tabellenzeile, als eigene Abfrage mit eigenem Beleg.
        alle_sql = bestand_sql(conn, regelsatz, von, bis, filter_, ())
        alle = _lesen(conn, alle_sql)
        belege.append(_beleg(alle_sql, _staende(alle)))
        zahlen.extend(
            {
                "bezeichnung": f"Beschäftigungsverhältnisse{zusatz}, Alle Altersstufen",
                "wert": int(z["wert"]),
                "einheit": einheit,
                "beleg": len(belege) - 1,
            }
            for z in alle
        )
    if gruppen == (GESCHLECHT, BUNDESLAND) and von == bis:
        # Summe je Geschlecht für die letzte Tabellenzeile, als eigene Abfrage mit eigenem Beleg. Nur für einen Monat:
        # Bestände mehrerer Monate darf man nicht addieren.
        summen_sql = bestand_sql(conn, regelsatz, von, bis, filter_, (GESCHLECHT,))
        summen = _lesen(conn, summen_sql)
        belege.append(_beleg(summen_sql, _staende(summen)))
        namen_geschlecht = _codes(conn, GESCHLECHT, von)
        zahlen.extend(
            {
                "bezeichnung": f"Beschäftigungsverhältnisse{zusatz}, "
                f"{namen_geschlecht.get(str(z['g0']), str(z['g0']))}, Alle Bundesländer",
                "wert": int(z["wert"]),
                "einheit": einheit,
                "beleg": len(belege) - 1,
            }
            for z in summen
            if z["g0"] is not None
        )
    return _antwort(
        typ,
        " ".join(
            [
                verstanden,
                text,
                *hinweise,
                _laien_bestand(),
                f"Die Zahlen sind {_status_text(gezaehlte_staende)}.",
            ]
        ),
        definition=definition,
        einheit=einheit,
        stand=staende,
        belege=belege,
        zahlen=zahlen,
        hinweise=hinweise,
    )


def _monate(von: str, bis: str) -> list[str]:
    monate: list[str] = []
    monat = von
    while monat <= bis and len(monate) < 600:
        monate.append(monat)
        monat = monat_verschieben(monat, 1)
    return monate


def _text_bestand(
    typ: str,
    zeilen: list[dict[str, Any]],
    gruppen: tuple[Merkmal, ...],
    labels: dict[tuple[str, str], dict[str, str]],
    zusatz: str,
) -> str:
    je_monat: dict[str, int] = {}
    for z in zeilen:
        je_monat[str(z["monat"])] = je_monat.get(str(z["monat"]), 0) + int(z["wert"])
    monate = sorted(je_monat)
    if typ == "zeitreihe":
        erster, letzter = monate[0], monate[-1]
        if erster == letzter:
            text = (
                f"Beschäftigungsverhältnisse{zusatz} am Stichtag, {_monat_anzeige(erster)}: "
                f"{_deutsch(je_monat[erster])}."
            )
        else:
            text = (
                f"Beschäftigungsverhältnisse{zusatz} am Stichtag, {_monat_anzeige(erster)} bis "
                f"{_monat_anzeige(letzter)} ({_anzahl_monate(len(monate))}): von {_deutsch(je_monat[erster])} "
                f"auf {_deutsch(je_monat[letzter])}."
            )
        if gruppen:
            text += f" Aufgeteilt nach {', '.join(g.name for g in gruppen)}, eine Zahl je Monat und Gruppe."
        return text
    monat = monate[0]
    text = (
        f"Am {_tag_anzeige(monatsletzter(monat))} gab es {_deutsch(je_monat[monat])} "
        f"Beschäftigungsverhältnisse{zusatz}."
    )
    if gruppen and gruppen[0] is GESCHLECHT:
        je_geschlecht: dict[str, int] = {}
        for z in zeilen:
            je_geschlecht[str(z["g0"])] = je_geschlecht.get(str(z["g0"]), 0) + int(z["wert"])
        namen = labels.get((GESCHLECHT.name, monat), {})
        teile = [f"{namen.get(c, c)}: {_deutsch(n)}" for c, n in sorted(je_geschlecht.items())]
        text += " Davon " + ", ".join(teile) + "."
        if len(gruppen) > 1:
            text += " Unten stehen die Zahlen je Bundesland, getrennt nach Geschlecht."
    elif gruppen:
        text += f" Aufgeteilt nach {gruppen[0].name} in {len(zeilen)} Zahlen."
    return text


def _fluktuation_sql(conn: Verbindung, regelsatz: str, regelstand: str, monat: str) -> str:
    vormonat = monat_verschieben(monat, -1)
    abfrage = sql.SQL(
        "WITH bestand AS ("
        "SELECT s.oenace, sum(s.wert)::bigint AS bestand FROM stat.stat_beschaeftigte s"
        " WHERE s.regelsatz = {rs} AND s.regelstand = {rst} AND s.zeitraum_art = {art} AND s.variable = {var}"
        " AND s.zeitraum_bis BETWEEN {erster} AND {letzter} GROUP BY s.oenace),"
        " bewegung AS (SELECT b.oenace, b.zugaenge, b.abgaenge"
        " FROM stat.bewegung_oenace({lief}, {rs}, {rst}, {stichtag_vorher}, {stichtag}) b)"
        " SELECT COALESCE(n.oenace, w.oenace) AS oenace, COALESCE(n.bestand, 0) AS bestand,"
        " COALESCE(w.zugaenge, 0) AS zugaenge, COALESCE(w.abgaenge, 0) AS abgaenge,"
        " CASE WHEN COALESCE(n.bestand, 0) > 0 THEN round(100.0 * (COALESCE(w.zugaenge, 0)"
        " + COALESCE(w.abgaenge, 0)) / 2 / n.bestand, 2) END AS fluktuation_prozent"
        " FROM bestand n FULL JOIN bewegung w ON w.oenace = n.oenace ORDER BY 1"
    ).format(
        rs=sql.Literal(regelsatz),
        rst=sql.Literal(regelstand),
        art=sql.Literal(STICHTAG),
        var=sql.Literal(STICHTAG_VARIABLE),
        erster=sql.Literal(monatserster(monat)),
        letzter=sql.Literal(monatsletzter(monat)),
        lief=sql.Literal(monat),
        stichtag_vorher=sql.Literal(monatsletzter(vormonat)),
        stichtag=sql.Literal(monatsletzter(monat)),
    )
    return abfrage.as_string(conn)


def rate(zugaenge: int, abgaenge: int, bestand: int) -> float | None:
    """Fluktuation in Prozent; ohne Bestand keine Rate (None statt einer erfundenen Zahl)."""
    if bestand <= 0:
        return None
    return round(100.0 * (zugaenge + abgaenge) / 2 / bestand, 2)


def _regel_abweichung(conn: Verbindung, regelsatz: str, monat: str, stand_regelstand: str) -> str | None:
    """Text, wenn die Zählregeln des Monats nicht die in stat.bewegung_oenace eingebauten sind, sonst None."""
    regeln: list[Regel] = regeln_laden(conn, regelsatz, monat)
    was_tun = (
        f" Was tun: den Monat neu rechnen lassen (uc3 lauf --lieferung {monat}) und dann noch einmal fragen."
    )
    if regelstand(conn, regeln) != stand_regelstand:
        return (
            f"Die Regeln wurden geändert, seit {_monat_anzeige(monat)} gerechnet wurde. Zu- und Abgänge passten "
            "dann nicht sicher zu den Zahlen." + was_tun
        )
    for r in regeln:
        if r.typ != "zaehl":
            continue
        for (art, schluessel), soll in EINGEBAUT.items():
            if r.art == art and str(r.parameter.get(schluessel)) != soll:
                return (
                    f"Für {_monat_anzeige(monat)} zählt die Regel {r.name} anders, als die Fluktuation rechnen "
                    "kann. Sie kennt nur den Stichtag am letzten Tag des Monats und, bei mehreren Abschnitten "
                    "eines Beschäftigungsverhältnisses, den zuletzt begonnenen. Darum gibt es hier keine Zahl."
                )
    return None


def _bewegung_fehlertext(fehler: psycopg.Error, monat: str) -> str:
    """Laientext ohne interne Kennungen (Regelstand-Hashes) und mit dem nächsten Schritt."""
    was_tun = (
        f" Was tun: den Monat neu rechnen lassen (uc3 lauf --lieferung {monat}) und dann noch einmal fragen."
    )
    if isinstance(fehler, psycopg.errors.UndefinedFunction):
        # Die Funktion kommt erst mit `uc3 db init` in eine bestehende Datenbank (uc3/db/160_bewegung.sql).
        return (
            "Die Datenbank kennt die Zählung der Zu- und Abgänge noch nicht. Was tun: einmal `uc3 db init` "
            "ausführen. Freigegebene Regeln und gerechnete Zahlen bleiben dabei unverändert."
        )
    meldung = fehler.diag.message_primary or ""
    if "lokalen Auswertung" in meldung:
        return meldung + "."
    if "Regelstand" in meldung:
        return "Die Einzeldaten dieses Monats wurden inzwischen mit anderen Regeln neu gerechnet." + was_tun
    if "keine bereinigten Daten" in meldung:
        return "Für diesen Monat liegen die Einzeldaten nicht vor." + was_tun
    return NICHT_LESBAR


def hoechste_satz(zeilen: list[dict[str, Any]], namen: dict[str, str]) -> str | None:
    """„Am höchsten“ nur unter Abschnitten mit mindestens MINDESTBESTAND_HOECHSTE, und das steht im Satz:
    die Tabelle darunter kann einen kleineren Abschnitt mit höherer Rate zeigen."""
    mit_rate = [
        z
        for z in zeilen
        if z["fluktuation_prozent"] is not None and int(z["bestand"]) >= MINDESTBESTAND_HOECHSTE
    ]
    if not mit_rate:
        return None
    hoechste = max(mit_rate, key=lambda z: float(z["fluktuation_prozent"]))
    code = str(hoechste["oenace"])
    return (
        f"Unter den Abschnitten mit mindestens {_deutsch(MINDESTBESTAND_HOECHSTE)} Beschäftigungsverhältnissen "
        f"ist sie am höchsten in Abschnitt {code} ({namen.get(code, code)}) mit "
        f"{_komma(float(hoechste['fluktuation_prozent']))} Prozent."
    )


def _fluktuation_antwort(conn: Verbindung, monat: str, regelsatz: str) -> dict[str, Any]:
    stand = letzter_lauf(conn, monat, regelsatz)
    if stand is None:
        return _antwort(
            "fluktuation", _kein_lauf_text(monat), definition=FLUKTUATION_DEFINITION, einheit="Prozent"
        )
    fortgeschrieben = _laufinfo(conn, regelsatz, [{"lauf": stand.lauf_id}]).get(stand.lauf_id, (0, True))[0]
    staende = [
        {
            "monat": monat,
            "lauf": stand.lauf_id,
            "regelstand": stand.regelstand,
            "status": stand.ergebnis_status,
            "fortgeschrieben": fortgeschrieben,
        }
    ]
    sql_text = _fluktuation_sql(conn, regelsatz, stand.regelstand, monat)
    beleg = _beleg(sql_text, staende, stand.ergebnis_hash)
    abweichung = _regel_abweichung(conn, regelsatz, monat, stand.regelstand)
    grund: str | None = abweichung
    zeilen: list[dict[str, Any]] = []
    if grund is None:
        try:
            zeilen = _lesen(conn, sql_text)
        except (psycopg.errors.RaiseException, psycopg.errors.UndefinedFunction) as fehler:
            grund = _bewegung_fehlertext(fehler, monat)
    if grund is not None:
        return _antwort(
            "fluktuation",
            f"Für {_monat_anzeige(monat)} lässt sich die Fluktuation nicht berechnen. {grund}",
            definition=FLUKTUATION_DEFINITION,
            einheit="Prozent",
            stand=staende,
            belege=[beleg],
            hinweise=[grund],
        )
    namen = _codes(conn, OENACE, monat)
    zahlen: list[dict[str, Any]] = []
    ohne_bestand: list[str] = []
    for z in zeilen:
        code = str(z["oenace"])
        name = f"ÖNACE {code} {namen.get(code, '')}".strip()
        if z["fluktuation_prozent"] is None:
            ohne_bestand.append(f"Abschnitt {code} ({namen.get(code, code)})")
        else:
            zahlen.append(
                {
                    "bezeichnung": f"Fluktuation, {name}",
                    "wert": float(z["fluktuation_prozent"]),
                    "einheit": "Prozent",
                    "beleg": 0,
                }
            )
        for feld, wort in (
            ("zugaenge", "Zugänge"),
            ("abgaenge", "Abgänge"),
            ("bestand", "Bestand am Stichtag"),
        ):
            zahlen.append(
                {"bezeichnung": f"{wort}, {name}", "wert": int(z[feld]), "einheit": "Anzahl", "beleg": 0}
            )
    zu = sum(int(z["zugaenge"]) for z in zeilen)
    ab = sum(int(z["abgaenge"]) for z in zeilen)
    best = sum(int(z["bestand"]) for z in zeilen)
    gesamt = rate(zu, ab, best)
    stichtag = _tag_anzeige(monatsletzter(monat))
    vorher = _tag_anzeige(monatsletzter(monat_verschieben(monat, -1)))
    teile = [
        f"Verstanden: Fluktuation im {_monat_anzeige(monat)}, ganz Österreich, je Wirtschaftsbereich.",
        f"Fluktuation im {_monat_anzeige(monat)}: Wie viele Beschäftigungsverhältnisse kamen dazu oder endeten, "
        f"gemessen am Bestand? Zwischen {vorher} und {stichtag} gab es {_deutsch(zu)} Zugänge und "
        f"{_deutsch(ab)} Abgänge bei {_deutsch(best)} Beschäftigungsverhältnissen am {stichtag}.",
    ]
    if gesamt is not None:
        teile.append(f"Über alle Wirtschaftsbereiche sind das {_komma(gesamt)} Prozent.")
        zahlen.append(
            {
                "bezeichnung": "Fluktuation, alle Wirtschaftsbereiche (Summe der Zeilen)",
                "wert": gesamt,
                "einheit": "Prozent",
                "beleg": 0,
            }
        )
    # Kleinstbereiche (z. B. Private Haushalte, rund 250) schwanken stark; „am höchsten“ nur ab 1.000.
    satz = hoechste_satz(zeilen, namen)
    if satz:
        teile.append(satz)
    hinweise: list[str] = []
    if ohne_bestand:
        hinweise.append(
            f"Für {', '.join(ohne_bestand)} gibt es am {stichtag} keine Beschäftigten; "
            "dort ist keine Rate berechenbar, es stehen nur Zu- und Abgänge da."
        )
    if fortgeschrieben:
        hinweise.append(_fortgeschrieben_hinweis(monat, fortgeschrieben, fluktuation=True))
    teile += hinweise
    teile.append(
        "Formel: (Zugänge + Abgänge) geteilt durch 2, geteilt durch den Bestand am Stichtag. "
        f"ÖNACE-Abschnitte sind Wirtschaftsbereiche. Die Zahlen sind {_status_text(staende)}."
    )
    return _antwort(
        "fluktuation",
        " ".join(teile),
        definition=FLUKTUATION_DEFINITION,
        einheit="Prozent",
        stand=staende,
        belege=[beleg],
        zahlen=zahlen,
        hinweise=hinweise,
    )


def _definition_antwort(conn: Verbindung, frage: str) -> dict[str, Any]:
    text = frage.lower()
    treffer = _OENACE_CODE.search(text)
    if treffer:
        code = treffer.group(1).upper()
        sql_text = (
            sql.SQL(
                "SELECT version, code, bezeichnung, ebene, gueltig_von, gueltig_bis FROM stat.klass_oenace"
                " WHERE code = {} ORDER BY gueltig_von DESC"
            )
            .format(sql.Literal(code))
            .as_string(conn)
        )
        zeilen = _lesen(conn, sql_text)
        beleg = {"uc": UC, "quelle": "stat.klass_oenace", "sql": sql_text, "ref": f"stat.klass_oenace/{code}"}
        if not zeilen:
            return _antwort(
                "definition",
                f"Einen ÖNACE-Abschnitt {code} gibt es in keiner gespeicherten Version. {OENACE_ERKLAERUNG}",
                definition=OENACE_ERKLAERUNG,
                belege=[beleg],
            )
        saetze = []
        for z in zeilen:
            ab = _monat_anzeige(str(z["gueltig_von"])[:7])
            bis = (
                f" bis {_monat_anzeige(str(z['gueltig_bis'])[:7])}"
                if z["gueltig_bis"]
                else ", gilt bis heute"
            )
            saetze.append(f"Version {z['version']} (gültig ab {ab}{bis}): „{z['bezeichnung']}“")
        return _antwort(
            "definition",
            f"{OENACE_ERKLAERUNG} Abschnitt {code} heißt in " + "; in ".join(saetze) + ". "
            "Bis Dezember 2024 zählt die Statistik nach Version 2008, ab Jänner 2025 nach Version 2025.",
            definition="; ".join(f"ÖNACE {z['version']} {code}: {z['bezeichnung']}" for z in zeilen),
            stand=[{"klassifikation": "stat.klass_oenace", "version": z["version"]} for z in zeilen],
            belege=[beleg],
        )
    if _FLUKTUATION.search(text):
        return _antwort(
            "definition",
            "Fluktuation zeigt, wie stark sich die Beschäftigten in einem Monat umschichten: Zugänge und Abgänge "
            "zusammen, halbiert und geteilt durch den Bestand am Monatsende, in Prozent.",
            definition=FLUKTUATION_DEFINITION,
            einheit="Prozent",
        )
    if "beschäftig" in text or "beschaeftig" in text:
        definition, einheit = _definition_bestand(conn)
        return _antwort("definition", _laien_bestand(), definition=definition, einheit=einheit)
    return _rueckfrage(
        "Welchen Begriff soll ich erklären? Zum Beispiel „Was ist ÖNACE C?“, „Was ist Fluktuation?“ "
        "oder „Was zählt als Beschäftigte?“."
    )


# --- Einstieg -------------------------------------------------------------------------------------------------


def _rueckfrage_monat(typ: str, jahr: str | None) -> dict[str, Any]:
    was, beispiel = {
        "fluktuation": ("die Fluktuation", "Fluktuation"),
        "geschlecht": ("die Zahlen für Männer und Frauen", "Männer und Frauen"),
        "bestand": ("die Zahl der Beschäftigten", "Beschäftigte"),
    }[typ]
    if typ == "fluktuation":
        im_jahr = min(f"{jahr}-12", LETZTE_LIEFERUNG) if jahr else ""
        monat = _monat_anzeige(im_jahr) if jahr and im_jahr >= f"{jahr}-01" else "März 2025"
        return _rueckfrage(
            "Die Fluktuation gibt es je Monat, ganz Österreich, je Wirtschaftsbereich. Für welchen Monat? "
            f"Zum Beispiel „Fluktuation je Wirtschaftsbereich im {monat}“."
        )
    if jahr is not None:
        return _rueckfrage(jahr_rueckfrage(beispiel, jahr, ERSTE_LIEFERUNG, LETZTE_LIEFERUNG))
    return _rueckfrage(f"Für welchen Monat möchten Sie {was} wissen? Zum Beispiel „{beispiel} März 2025“.")


def antwort_frage(conn: Verbindung, frage: str, regelsatz: str = "v1") -> dict[str, Any]:
    """Beantwortet eine Datenanfrage ohne Sprachmodell; mehrdeutige Fragen bekommen eine Rückfrage.

    Wirft nie: Was sich nicht beantworten lässt (Zeitlimit, verweigerte Abfrage, zu viele Zahlen, ein Merkmal,
    das es nicht gibt), kommt als Textantwort ohne Zahl und ohne interne Details zurück.
    """
    try:
        letzter = _letzter_monat(conn, regelsatz)
    except psycopg.Error:
        return _antwort(fragetyp(frage), NICHT_LESBAR, hinweise=[NICHT_LESBAR])
    grund = unklar(frage, letzter or LETZTE_LIEFERUNG)
    if grund is not None:
        return _rueckfrage(grund)
    hinweis_tag = tag_hinweis(frage)
    frage, notizen, mittel = _normalisieren(frage, letzter or LETZTE_LIEFERUNG)
    if hinweis_tag:
        notizen.insert(0, hinweis_tag)
    typ = fragetyp(frage)
    absage = nicht_auswertbar(frage, mittel=mittel and len(set(monate_lesen(frage))) > 1)
    if absage is not None:
        return _antwort(typ, absage, hinweise=[absage])
    try:
        # Unsinn bekommt keinen Bestand und keine Rückfrage zu einem Monat, sondern die Absage (Kette stoppt, #176).
        if typ == "bestand" and _ohne_bezug(conn, frage, letzter or LETZTE_LIEFERUNG):
            genannt = monate_lesen(frage)
            vorschlag = f" Meinen Sie „Beschäftigte im {_monat_anzeige(genannt[-1])}“?" if genannt else ""
            text = f"Das kann StatAgent nicht beantworten. {KANN}{vorschlag}"
            return _antwort(typ, text, hinweise=[text])
        if (
            typ in ("bestand", "geschlecht", "fluktuation")
            and not monate_lesen(frage)
            and jahr_ohne_monat(frage) is None
            and letzter is not None
        ):
            frage = f"{frage} {_monat_anzeige(letzter)}"
            if _AKTUELL.search(frage):
                notizen.append(
                    f"„Aktuell“ heißt hier der zuletzt gerechnete Monat, {_monat_anzeige(letzter)}."
                )
            else:
                notizen.append(f"Ohne Zeitangabe zeigen wir den jüngsten Monat: {_monat_anzeige(letzter)}.")
        daten = _antwort_frage(conn, frage, regelsatz, typ, mittel)
    except _KeineZahl as grund:
        return _antwort(typ, str(grund), hinweise=[str(grund)])
    except (psycopg.Error, AbfrageVerweigert):
        return _antwort(typ, NICHT_LESBAR, hinweise=[NICHT_LESBAR])
    if notizen:
        text = daten["text"]
        ende = text.find(". ") + 1 if text.startswith("Verstanden:") else 0
        daten["text"] = " ".join(t for t in (text[:ende].strip(), *notizen, text[ende:].strip()) if t)
    return daten


def _aufteilung(frage: str) -> Merkmal | None:
    """Die Aufteilung der Frage; Altersgruppen nur allein, eine zweite Aufteilung fiele sonst still weg."""
    text = frage.lower()
    if not _ALTER_GRUPPEN.search(text):
        return _gliederung(frage)
    if _gliederung(frage) is not None or _geschlecht_gegliedert(text):
        raise _KeineZahl(
            "Die Zahlen je Alter gibt es nur ohne eine zweite Aufteilung. Bitte getrennt fragen, zum Beispiel "
            "„Frauen nach Altersgruppe im Juli 2026“."
        )
    return ALTERSGRUPPE


def _antwort_frage(
    conn: Verbindung, frage: str, regelsatz: str, typ: str, mittel: bool = False
) -> dict[str, Any]:
    if typ == "definition":
        daten = _definition_antwort(conn, frage)
        if not daten["rueckfrage"]:
            daten["text"] = "Verstanden: eine Frage nach der Bedeutung eines Begriffs. " + daten["text"]
        return daten
    monate = monate_lesen(frage)
    jahr = jahr_ohne_monat(frage)
    text = frage.lower()
    if typ == "zeitreihe":
        _aufteilung(frage)  # Männer und Frauen je Altersgruppe: Absage
        if len(monate) >= 2:
            von, bis = min(monate[0], monate[-1]), max(monate[0], monate[-1])
        elif len(monate) == 1:
            von, bis = monate[0], "9999-12"
        elif jahr is not None:
            von, bis = f"{jahr}-01", f"{jahr}-12"
        else:
            von, bis = "0001-01", "9999-12"
        letzter_bekannt = _letzter_monat(conn, regelsatz)
        if letzter_bekannt is None:
            return _antwort("zeitreihe", "Es ist noch kein Monat gerechnet.")
        if bis == "9999-12":
            bis = letzter_bekannt
        if von == "0001-01":
            von = _erster_monat(conn, regelsatz) or bis
        gruppen: tuple[Merkmal, ...] = (
            (GESCHLECHT,) if _geschlecht_gegliedert(text) else tuple(g for g in (_aufteilung(frage),) if g)
        )
        return _bestand_antwort(conn, frage, regelsatz, von, bis, gruppen, "zeitreihe", mittel)
    if typ == "fluktuation" and len(monate) > 1:
        return _rueckfrage_monat(typ, monate[-1][:4])
    if len(monate) != 1:
        if len(monate) > 1:
            return _rueckfrage(
                "Die Frage nennt mehrere Monate. Meinen Sie eine Zeitreihe („Zeitreihe von … bis …“) "
                "oder einen einzelnen Monat?"
            )
        return _rueckfrage_monat(typ, jahr)
    monat = monate[0]
    if typ == "fluktuation":
        if monat == ERSTE_LIEFERUNG:
            raise _KeineZahl(
                f"Für {_monat_anzeige(monat)} gibt es keine Fluktuation: Die erste Lieferung enthält nicht alle "
                "Beschäftigungsverhältnisse des Vormonats, Zu- und Abgänge wären falsch. Ab "
                f"{_monat_anzeige(monat_verschieben(monat, 1))} gibt es sie."
            )
        filter_, etiketten = _filter(conn, frage, monat, ())
        if any(m is not OENACE for m, _ in filter_) or _BUNDESLAND.search(text) or _GESCHLECHT.search(text):
            raise _KeineZahl(
                "Die Fluktuation gibt es nur für ganz Österreich je Wirtschaftsbereich, nicht je Bundesland, "
                "Geschlecht oder Beschäftigungskategorie. Vorschlag: „Fluktuation je Wirtschaftsbereich im "
                f"{_monat_anzeige(monat)}“."
            )
        daten = _fluktuation_antwort(conn, monat, regelsatz)
        if filter_:
            # Gefragt war eine Branche: die Tabelle zeigt alle, das sagt der Verstanden-Satz.
            code, etikett = filter_[0][1], etiketten[0]
            daten["text"] = daten["text"].replace(
                "je Wirtschaftsbereich.",
                f"je Wirtschaftsbereich; gefragt war die Branche {code} {etikett}, sie steht in der Zeile ÖNACE {code}.",
                1,
            )
        return daten
    if typ == "geschlecht" and _geschlecht_gegliedert(text):
        _aufteilung(frage)  # Männer und Frauen je Altersgruppe: Absage
        gruppen = (GESCHLECHT, BUNDESLAND) if _BUNDESLAND.search(text) else (GESCHLECHT,)
        return _bestand_antwort(conn, frage, regelsatz, monat, monat, gruppen, "geschlecht")
    gliederung = _aufteilung(frage)
    return _bestand_antwort(
        conn, frage, regelsatz, monat, monat, (gliederung,) if gliederung else (), "bestand"
    )


def _letzter_monat(conn: Verbindung, regelsatz: str) -> str | None:
    zeile = conn.execute(
        "SELECT max(lieferung) AS m FROM meta.lauf WHERE regelsatz = %s AND status IN ('fertig', 'unveraendert')",
        (regelsatz,),
    ).fetchone()
    return None if zeile is None or zeile["m"] is None else str(zeile["m"])


def _erster_monat(conn: Verbindung, regelsatz: str) -> str | None:
    zeile = conn.execute(
        "SELECT min(lieferung) AS m FROM meta.lauf WHERE regelsatz = %s AND status IN ('fertig', 'unveraendert')",
        (regelsatz,),
    ).fetchone()
    return None if zeile is None or zeile["m"] is None else str(zeile["m"])
