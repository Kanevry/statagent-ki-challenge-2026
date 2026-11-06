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

from statagent import pensionen
from statagent.agenten.werkzeuge import AbfrageVerweigert, sql_lesen
from statagent.berichte.sheet import STICHTAG, STICHTAG_VARIABLE
from statagent.db import Verbindung
from statagent.ergebnis import letzter_lauf, monat_verschieben, monatserster, monatsletzter
from statagent.pensionen import PensionFehler, ist_pensionsfrage, pensionsantwort
from statagent.regeln import Regel, RegelFehler, regeln_laden, regelstand
from statagent.uc4 import (
    _ISO,
    _NAME_MONAT,
    _OENACE_CODE,
    _OENACE_LISTE,
    _ZAHL_MONAT,
    MERKMALE,
    Merkmal,
    _adapter_liest_gleich,
    _aufzaehlung,
    _codes,
    _deutsch,
    _fortgeschrieben_hinweis,
    _gliederung,
    _monat_anzeige,
    antwort_daten,
    jahr_rueckfrage,
)
from statagent.woerter import BEKANNT, unbekanntes_wort
from statagent.zeitraum import (
    KEIN_JAHR,
    MONATSNAMEN,
    ZEITREIHE_WORT,
    schraegstrich_lesen,
    tag_hinweis,
    umschreiben,
    unklar,
    zeitraum_anzeige,
    zeitraum_lesen,
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
#: Bis zu so vielen Monaten nennt der Text jeden Monat einzeln (Jahreszeit, Quartal, Halbjahr).
MONATE_IM_TEXT = 6
#: „Am höchsten“ nennt nur Abschnitte mit mindestens so vielen Beschäftigungsverhältnissen am Stichtag.
MINDESTBESTAND_HOECHSTE = 1000
NICHT_LESBAR = (
    "Diese Frage lässt sich gerade nicht aus der Datenbank beantworten. Was tun: die Frage enger fassen, "
    "zum Beispiel einen Monat statt eines ganzen Zeitraums, oder etwas später noch einmal fragen."
)
_STATUS_TEXT = {"vorlaeufig": "vorläufig", "endgueltig": "endgültig", "gesperrt": "gesperrt"}

_JAHR = re.compile(r"(?<!\d)((?:19|20)\d{2})(?!\d)")
_VERGLEICH_VORMONAT = re.compile(r"\bvormonats?\b", re.IGNORECASE)
_SEIT = re.compile(r"\bseit\b", re.IGNORECASE)
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
DURCHGEHEND_GRUND = f"Wie lange jemand im Monat beschäftigt war, wertet StatAgent nicht aus. {KANN}"
DURCHSCHNITT_GRUND = (
    "Durchschnitte gibt es nur über mehrere Monate, zum Beispiel „Durchschnitt März bis Juni 2025“."
)
DAUER_GRUND = f"Wie lange ein Beschäftigungsverhältnis schon besteht, wertet StatAgent nicht aus. {KANN}"
#: Mehrere, unmögliche oder nicht eindeutige Altersangaben: hier geht es nicht um das Durchschnittsalter.
ALTER_UNKLAR = (
    "Diese Altersangabe kann StatAgent nicht auswerten. Fragen Sie nach einem Alter oder einer Spanne in Jahren, "
    "zum Beispiel „Beschäftigte ab 50 Jahren im Juli 2026“."
)
#: Eine Altersgrenze ohne „Jahre“. Nicht gemeint sind Mengen und Prozent („über 50 Prozent“, „über 20.000“) und Daten
#: („bis 31. März“, „bis 12/2025“, „bis 12 2025“).
_ALTER_GRENZE_MUSTER = (
    r"\b(?:unter|über|ueber|ab|bis|zwischen)[\s-]+\d{2}(?![./,-]?\d)(?!\s+\d{4})"
    r"(?!\.?\s*(?:jän|jan|feb|mär|mae|apr|mai|jun|jul|aug|sep|okt|nov|dez))"
    r"(?!\s*(?:prozent|%|beschäftig|personen|leute|menschen|verhältnis|mitarbeit|arbeitnehm|dienstnehm|betrieb"
    r"|frauen|männer|maenner|arbeiter|angestellte|beamte"
    r"|jobs?\b|stellen\b|tausend|tsd))"
)
_ALTER_GRENZE = re.compile(_ALTER_GRENZE_MUSTER)
_ALTER_FACHLICH_NICHT = re.compile(r"durchschnittsalter|\bwie alt\b|jahrgang|jahrgänge|geburtsjahr")
NICHT_AUSGEWERTET: tuple[tuple[re.Pattern[str], str], ...] = (
    # „den ganzen Monat“, österreichisch „das ganze Monat“: gemeint ist durchgehend. Beide Zählweisen zählen etwas anderes.
    (
        re.compile(
            r"(?<!über\s)(?<!ueber\s)\b(?:den|die|das|ein|des)\s+(?:ganze[ns]?|gesamte[ns]?)\s+monats?\b|\bganze\s+monate\b"
            r"|\bganzes\s+monat\s+(?:beschäftigt|gearbeitet|angestellt|tätig|dabei)|\bdurchgehend\s+beschäftigt"
        ),
        DURCHGEHEND_GRUND,
    ),
    # Dauer vor Alter prüfen: „seit über 2 Jahren beschäftigt“ ist keine Altersfrage, aber genauso nicht in den Daten.
    (
        re.compile(
            r"beschäftigungsdauer|\bdauer\b|(?:betriebs|firmen|unternehmens)zugehörigkeit|\bseit\s+(?:(?:über|ueber|mehr als|unter|weniger als)\s+)?\d{1,3}\s*(?:jahre|jahren|monate|monaten)\b"
            r"|\b(?:über|ueber|unter|ab|bis|länger als|mehr als|weniger als)\s+\d{1,3}\s*(?:jahre|jahren|monate|monaten)\s+"
            r"(?:beschäftigt|angestellt|tätig|im job|im betrieb|dabei|zugehörigkeit)"
        ),
        DAUER_GRUND,
    ),
    (
        re.compile(
            r"\b(alter|altersgruppen?|lebensalter)\b(?!\s+(regel|regeln|version|fassung|stand|zählung|lieferung))"
            r"|durchschnittsalter|jahre alt|\bwie alt\b|\b\d{1,3}-?jährig|jugendlich|jahrgang|jahrgänge|geburtsjahr"
            r"|\b(unter|über|ueber|ab|bis)\s+\d{1,3}\s*(jahre|jahren)\b"
            # Auffangregel: eine Altersangabe ohne eindeutigen Treffer bekommt keinen Gesamtbestand.
            rf"|{_ALTER_GRENZE_MUSTER}"
            r"|\b\d{2}\s*\+|\b(?:älter|aelter|jünger|juenger)(?:e[nrs]?)?\b|\balters(?:stufe|klasse|kohorte|struktur)\w*"
        ),
        ALTER_GRUND,
    ),
    (
        re.compile(r"durchschnitt|mittelwert|median"),
        DURCHSCHNITT_GRUND,
    ),
    # „angehalten“ und „hereinkommen“ enthalten die Wörter, meinen aber nichts davon. „Monatslohn“ schon.
    (
        re.compile(
            r"\blohn|lohn(?:e?s)?\b|löhne|gehalt(?!en|ene)|gehälter|(?<!her)(?<!hin)einkommen|verdienst"
        ),
        "Einkommen sind nicht in den Daten.",
    ),
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
_FREIER_DV = re.compile(r"\bfreie[nmrs]?\s+(?:dienstv\w*|dienstnehmer\w*|dv)\b|\bfd\b")
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
        re.compile(
            r"\b(gastro|gastronomie|gastgewerbe|beherbergung|hotellerie|hotels?|restaurants?|tourismus)\b"
        ),
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
    (re.compile(r"\b(verkehr|transport|logistik|lagerei)\b"), ("Verkehr",)),
    (re.compile(r"\b(bildung|bildungswesen|schulen?|unterricht|erziehung)\b"), ("Erziehung",)),
    (re.compile(r"\b(öffentliche[nr]? verwaltung|verwaltung|behörden?)\b"), ("Öffentliche Verwaltung",)),
    (
        re.compile(r"\b(finanzen|finanzwesen|finanzdienstleistungen|banken?|versicherungen)\b"),
        ("Erbringung von Finanz",),
    ),
    (re.compile(r"\b(landwirtschaft|forstwirtschaft|agrar)\b"), ("Land- und Forstwirtschaft",)),
    (re.compile(r"\b(energie|energieversorgung|strom)\b"), ("Energieversorgung",)),
    (re.compile(r"\bbergbaus?\b"), ("Bergbau",)),
    (re.compile(r"\bkunst\b"), ("Kunst",)),
    (re.compile(r"\b(immobilien|wohnungswesen)\b"), ("Grundstücks",)),
)
#: Wer in einem Bundesland lebt, wird in der Frage oft mit dem Bundesland gemeint („die Wiener“).
EINWOHNER: dict[str, tuple[str, ...]] = {
    "Wien": ("wiener",),
    "Niederösterreich": ("niederösterreicher",),
    "Oberösterreich": ("oberösterreicher",),
    "Steiermark": ("steirer",),
    "Tirol": ("tiroler",),
    "Vorarlberg": ("vorarlberger",),
    "Burgenland": ("burgenländer",),
    "Kärnten": ("kärntner",),
    "Salzburg": ("salzburger",),
}
_ZEITWORT_OHNE_MONAT = re.compile(
    r"\b(?:jahr|jahre|jahren|jahres|monat|monate|monaten|monats|zeitraum|vormonats?|vorjahr(?:es)?)\b",
    re.IGNORECASE,
)
#: Fragt nach einer Änderung: Der Stand eines Monats allein wäre eine andere Antwort.
_VERAENDERUNG = re.compile(
    r"\b(?:veränder\w*|veraender\w*|gestiegen|gesunken|gewachsen|stieg|sank)\b", re.IGNORECASE
)
_MONATSWORT = "|".join(sorted(map(re.escape, MONATSNAMEN), key=len, reverse=True))
#: „im Monat nach Dezember 2025“, „vor Juni“, „nach dem Ende des Winters“: Der Monat in der Frage ist nicht der gemeinte.
_ZEITBEZUG = re.compile(
    rf"\bvormonats?\s+(?:von|zu|des)\b|\b(?:vor|nach)\s+(?:dem\s+|der\s+|den\s+)?(?:ende\b|beginn\b|anfang\b|start\b|sommer|winter|herbst|frühling|frühjahr"
    rf"|(?:{_MONATSWORT})\b)",
    re.IGNORECASE,
)
#: „Wie viel Prozent der Männer arbeiten im Bau“ ist der Anteil an den Männern, nicht der Männeranteil im Bau.
#: Gilt mit einem weiteren Merkmal; „Prozent der Beschäftigten in Wien sind Frauen“ ist der Männer- und Frauenanteil.
_PROZENT_VON_GRUPPE = re.compile(
    r"\bprozent\s+(?:der|aller|von\s+den)\s+(?:frauen|männer|männern|maenner|maennern)\b"
    r"|\banteil\s+(?:der|aller)\s+(?:frauen|männer|maenner)\s*,?\s+die\b"
    r"|\banteil\s+(?:der|aller)\s+(?:frauen|männer|maenner)\s+(?:arbeite\w*|(?:ist|war|sind|waren)\s+(?:in|im|bei)\b)"
    r"|\bvon\s+(?:allen|den)\s+(?:\w+\s+)?(?:frauen|männern|maennern)\b[^?]*\b(?:prozent|anteil)\b"
    r"|\bprozent\s+von\s+allen\s+(?:\w+\s+)?(?:frauen|männern|maennern)\b"
    r"|\bprozent\s+(?:der|aller)\s+(?:weiblichen|männlichen|maennlichen)\s+beschäftigten\b"
    r"|\banteil\b[^?]*\ban\s+(?:allen|den)\s+(?:\w+\s+)?(?:frauen|männern|maennern)\b"
    r"|\bvon\s+hundert\s+(?:frauen|männern|maennern)\b",
    re.IGNORECASE,
)
#: „nur einen Job“, „genau eine Stelle“: Das fragt nach Personen, gezählt werden Verhältnisse.
_EIN_VERHAELTNIS = re.compile(
    r"\b(?:nur|genau|mit)\s+ein\w*\s+(?:job|stelle|verhältnis|beschäftigungsverhältnis|arbeitsverhältnis)\b",
    re.IGNORECASE,
)
#: „Wie viele Bundesländer …“ fragt nach etwas anderem als nach Beschäftigungsverhältnissen.
_ZAEHLT_ANDERES = re.compile(
    r"\bwie\s*viele\s+(?:der\s+|von\s+den\s+)?(?:bundesl\w*|branchen|wirtschaftsbereich\w*|abschnitte|kategorien|monate|regeln|regelsätze)\b",
    re.IGNORECASE,
)
_KEIN_DATUM = f"Daten gibt es nur für {zeitraum_anzeige(ERSTE_LIEFERUNG, LETZTE_LIEFERUNG)}. Bitte einen Zeitraum darin nennen."
_VOR_ZEIT = re.compile(r"\b(?:vormonats?|vorjahr(?:es)?)\b", re.IGNORECASE)
#: Das Alltagswort für die Aufteilung in einem Satz an Nutzer.
_JE_ALLTAG = {"ÖNACE-Abschnitt": "je Branche", "Beschäftigungskategorie": "je Beschäftigungskategorie"}
_VERNEINUNG = frozenset(
    {"außer", "ausser", "ohne", "nicht", "kein", "keine", "keinen", "keiner", "ausgenommen"}
)
_FRAU = re.compile(r"\b(frau|frauen|weiblich\w*)\b")
_MANN = re.compile(r"\b(mann|männer|maenner|männern|maennern|männlich\w*|maennlich\w*)\b")
#: Wortstämme nach „im/in/Branche“, die kein Merkmal meinen („in den Wirtschaftsbereichen“, „in Prozent“).
_KEIN_MERKMAL_STAMM = (
    "österreich", "oesterreich", "vergleich", "jahr", "monat", "zeitraum", "schnitt", "gesamt", "summe",
    "detail", "bundesl", "wirtschaftsbereich", "wirtschaftszweig", "abschnitt", "önace", "oenace",
    "berichtsmonat", "stichtag", "verlauf", "lauf", "bereich", "branche", "sektor", "prozent", "vormonat",
    "vorjahr", "zahl", "tabelle", "beschäftigungskategorie", "kategorie", "geschlecht", "regelsatz", "beschäftigung",
    "durchschnitt",
)  # fmt: skip
#: Nur als ganzes Wort: „Altersheim“ und „Altersteilzeit“ sind keine Merkmale.
_KEIN_MERKMAL_WORT = frozenset({"alter", "alters", "altersgruppe", "altersgruppen", "altersverteilung"})
_FUNKTIONSWORT = frozenset(
    {"im", "in", "der", "den", "dem", "die", "das", "welchem", "welcher", "welchen", "welche", "diesem",
     "dieser", "diesen", "ganz", "ganzen", "gesamten", "allen", "alle", "einem", "einer", "einen", "letzten",
     "letztem", "vergangenen", "laufenden", "form", "höhe", "hoehe", "relation", "bezug", "folge", "etwa",
     "zeit", "punkto", "und", "oder", "sowie", "hat", "hatte", "hatten", "haben", "ist", "war", "waren", "nur"}
)  # fmt: skip
_ORT_KETTE = re.compile(
    r"\b(?:im|in der|in den|in|branche|bereich)\s+([\w-]+(?:\s*(?:,|\bund\b|\boder\b|\bsowie\b)\s*[\w-]+)*)",
    re.IGNORECASE,
)
_LETZTES_JAHR = re.compile(r"\b(?:im\s+)?letzte[nms]?\s+jahr(?:es)?\b", re.IGNORECASE)
_AKTUELL = re.compile(r"\b(aktuell|derzeit|zurzeit|momentan|jetzt)\b", re.IGNORECASE)
KATEGORIE = _merkmal("Beschäftigungskategorie")


#: Alltagsform → die Form, die der Rest des Lesens kennt. Nur, was dieselbe Bedeutung hat.
_ALLTAG: tuple[tuple[re.Pattern[str], str], ...] = (
    # Binnen-I und Gendersternchen meinen alle. Genau in dieser Schreibweise: „Arbeiterinnen“ bleibt die Frauen.
    (re.compile(r"\bArbeiter(?:Innen|[*:_]innen)\b"), "Arbeiter"),
    (re.compile(r"\bBeamt(?:Innen|[*:_]innen)\b"), "Beamte"),
    (re.compile(r"\bAngestellt(?:eR|e[*:_]r)\b"), "Angestellte"),
    # Die Doppelnennung meint alle, darum vor der Regel, die nur die Frauen zählt.
    (
        re.compile(r"\b(?:arbeiterinnen\s+und\s+arbeiter|arbeiter\s+und\s+arbeiterinnen)\b", re.IGNORECASE),
        "Arbeiter",
    ),
    (re.compile(r"\b(?:beamtinnen\s+und\s+beamte|beamte\s+und\s+beamtinnen)\b", re.IGNORECASE), "Beamte"),
    (re.compile(r"\b(?:angestellte\s+und\s+angestellter)\b", re.IGNORECASE), "Angestellte"),
    (re.compile(r"\barbeiterinnen\b", re.IGNORECASE), "Arbeiter Frauen"),
    (re.compile(r"\bbeamtinnen\b", re.IGNORECASE), "Beamte Frauen"),
    (re.compile(r"\bim\s+schnitt\b", re.IGNORECASE), "im Durchschnitt"),
    (re.compile(r"(?<!\w)schnitt\b", re.IGNORECASE), "Durchschnitt"),
    (re.compile(r"\bgabs\b", re.IGNORECASE), "gab es"),
    (re.compile(r"\bgrad\b", re.IGNORECASE), "derzeit"),
    (re.compile(r"\b(?:in\s+jedem|jedes|jedem)\s+bundesland\b", re.IGNORECASE), "je Bundesland"),
    (re.compile(r"\b(?:in\s+jeder|jede|jeder)\s+branche\b", re.IGNORECASE), "je Branche"),
    (re.compile(r"\boö\b", re.IGNORECASE), "Oberösterreich"),
    (re.compile(r"\bnö\b", re.IGNORECASE), "Niederösterreich"),
    (re.compile(r"\bstmk\b\.?", re.IGNORECASE), "Steiermark"),
)
#: „Wie viel Prozent … sind Frauen“ fragt nach dem Anteil, nicht nach der Menge.
_PROZENTZEICHEN = re.compile(r"\s*%")
_PROZENT_ANTEIL = re.compile(r"\b(?:wie\s*viel(?:e)?\s+)?prozent\b", re.IGNORECASE)


def alltag_lesen(frage: str) -> str:
    """Schreibweisen vereinheitlichen, bevor Zeitraum und Merkmale gelesen werden."""
    frage = schraegstrich_lesen(_PROZENTZEICHEN.sub(" Prozent", frage))
    for muster, ersatz in _ALLTAG:
        frage = muster.sub(ersatz, frage)
    if _PROZENT_ANTEIL.search(frage) and not _FLUKTUATION.search(frage.lower()):
        frage = _PROZENT_ANTEIL.sub("Anteil", frage)
    return frage


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
    # „seit März 2025 verändert“ ist schon ein Zeitraum bis zum jüngsten Monat.
    vormonat = _VERGLEICH_VORMONAT.search(frage) or (_VERAENDERUNG.search(frage) and not _SEIT.search(frage))
    genannt = monate_lesen(frage)
    if vormonat and len(set(genannt)) == 1:
        # „März 2025 gegenüber dem Vormonat“ meint zwei Monate, nicht nur den März.
        frage = f"{_monat_anzeige(monat_verschieben(genannt[0], -1))} {frage}"
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
    "SELECT berichtsgruppe AS code, CASE WHEN berichtsgruppe = 'unbekannt' THEN 'Alter unbekannt'"
    " ELSE replace(berichtsgruppe, ' u. mehr', ' Jahre und älter') || CASE WHEN berichtsgruppe LIKE '%% u. mehr'"
    " THEN '' ELSE ' Jahre' END END AS bezeichnung FROM stat.klass_alter"
    " GROUP BY berichtsgruppe ORDER BY min(code) < 0, min(code)",
    ("alter",),
)
_ALTER_GRUPPEN = re.compile(
    r"\b(?:nach|je|pro)\s+(?:\w+\s+)?(?:alter|altersgruppen?)\b(?!\s+(?:regel|regeln|version|fassung|stand|zählung|lieferung))"
    r"|\baltersgruppen\b|\baltersverteilung\b"
)
_ALTER_NICHT = re.compile(r"durchschnittsalter|jugendlich|jahrgang|jahrgänge|geburtsjahr")
_JAHRE = r"\s*-?\s*(?:jahren?|jährig\w*)"
#: (Muster, Grenzen aus den Gruppen, Wortlaut). Höchstalter wie die Klassifikation.
_ALTER_HOECHST = 130
_ALTER_GRENZE_MINDEST = 14
_ALTER_MUSTER: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(rf"\b(\d{{1,3}})(?:{_JAHRE})?(?:\s+alt)?\s+(?:oder|und)\s+(?:älter|aelter|mehr)\b"), "ab"),
    (re.compile(r"\bim\s+alter\s+von\s+(\d{1,3})\s*(?:bis|und)\s*(\d{1,3})\b"), "spanne"),
    (re.compile(rf"\b(?:zwischen\s+)?(\d{{1,3}})\s*-?\s*(?:bis|und|–|—|-)\s*(\d{{1,3}}){_JAHRE}"), "spanne"),
    (re.compile(rf"\b(?:jünger als|juenger als)\s+(\d{{1,3}})(?:{_JAHRE})?"), "unter"),
    (re.compile(rf"\bunter[\s-]+(\d{{1,3}}){_JAHRE}"), "unter"),
    (re.compile(rf"\b(?:älter als|aelter als)\s+(\d{{1,3}})(?:{_JAHRE})?"), "ueber"),
    (re.compile(rf"\b(?:über|ueber)[\s-]+(\d{{1,3}}){_JAHRE}"), "ueber"),
    (re.compile(rf"\bab\s+(\d{{1,3}}){_JAHRE}"), "ab"),
    (re.compile(rf"\bbis\s+(\d{{1,3}}){_JAHRE}"), "bis"),
    # Ohne „Jahre“ nur direkt vor der Zeitangabe oder am Satzende: „über 2000 Beschäftigte“ ist eine Menge.
    (re.compile(r"\bunter\s+(\d{2})(?=\s*(?:$|[?.,](?!\d)|im\b|in\b|am\b|von\b))"), "unter"),
    (re.compile(r"\b(?:über|ueber)\s+(\d{2})(?=\s*(?:$|[?.,](?!\d)|im\b|in\b|am\b|von\b))"), "ueber"),
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
    # Bleibt neben dem Treffer eine Grenze stehen („unter 25 und über 50“), ist die Angabe nicht eindeutig.
    if len(gefunden) != 1 or _ALTER_GRENZE.search(text):
        return None
    art, a, b = gefunden[0]
    if art != "genau" and a < _ALTER_GRENZE_MINDEST:
        return None  # „über 2 Jahre dabei“, „unter 10 in Wien“: das ist keine Altersgrenze
    von, bis, etikett = {
        "spanne": (a, b, f"{a} bis {b} Jahre"),
        "unter": (0, a - 1, f"unter {a} Jahre"),
        # Vollendete Jahre: „über 50“ beginnt bei 51, das Etikett nennt die Grenze (annahmen.md, A14).
        "ueber": (a + 1, _ALTER_HOECHST, f"{a + 1} Jahre und älter"),
        "ab": (a, _ALTER_HOECHST, f"ab {a} Jahre"),
        "bis": (0, a, f"bis {a} Jahre"),
        "genau": (a, a, f"{a} Jahre"),
    }[art]
    if not 0 <= von <= bis <= _ALTER_HOECHST:
        return None
    # von und bis sind ganze Zahlen aus der Frage.
    return Merkmal("Alter", f"(s.alter BETWEEN {von} AND {bis})", "", ()), "true", etikett


def _ohne_altersangabe(frage: str) -> str:
    """Die Frage ohne die Stelle, die ``_alter_lesen`` als Alter gelesen hat („über 50 Jahre“, „30-Jährige“)."""
    text = frage.lower()
    for muster, _ in _ALTER_MUSTER:
        text = muster.sub(" ", text)
    return re.sub(r"\b(?:jahre\s+)?alt\b", " ", text)


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
            if grund is DURCHGEHEND_GRUND:
                return grund  # sagt schon selbst, was geht
            if grund is ALTER_GRUND:
                # Das Beispiel der Alters-Absage sagt schon, was geht.
                return ALTER_GRUND if _ALTER_FACHLICH_NICHT.search(text) else ALTER_UNKLAR
            if grund is DAUER_GRUND or grund is DURCHSCHNITT_GRUND:
                return grund  # sagt schon selbst, was geht
            return f"{grund} Darum gibt es hier keine Zahl. {KANN}"
    return None


def _treffer(text: str, bezeichnung: str) -> re.Match[str] | None:
    return re.search(rf"(?<!\w){re.escape(bezeichnung.lower())}(?:e|n|en)?(?!\w)", text)


def _werte(frage: str, merkmal: Merkmal, codes: dict[str, str]) -> tuple[list[str], list[str]]:
    """Alle in der Frage genannten Codes eines Merkmals und die Textstellen, die sie getroffen haben."""
    text = frage.lower()
    gefunden: dict[str, str] = {}
    weitere: list[str] = []  # Weitere Wörter derselben Branche („Pflege und Spitäler“)
    for code, bezeichnung in codes.items():
        t = _treffer(text, bezeichnung)
        if t:
            gefunden[code] = t.group(0)
    if merkmal is BUNDESLAND:
        for code, bezeichnung in codes.items():
            for einwohner in EINWOHNER.get(bezeichnung, ()):
                if re.search(rf"\b{einwohner}\b", text):
                    gefunden.setdefault(code, einwohner)
    if merkmal is GESCHLECHT:
        for code, muster in (("W", _FRAU), ("M", _MANN)):
            t = muster.search(text)
            if t and code in codes:
                gefunden.setdefault(code, t.group(0))
    if merkmal is OENACE:
        for t in _OENACE_CODE.finditer(text):
            if t.group(1).upper() not in codes:
                raise _KeineZahl(
                    f"Einen ÖNACE-Abschnitt {t.group(1).upper()} gibt es in diesem Monat nicht. {KANN}"
                )
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
            weitere += [w.group(0) for w in muster.finditer(text)]
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
    # Nur ganze Wörter: „Bau“ steckt in „Bergbau und Gewinnung“, meint aber etwas anderes.
    doppelt = {
        c
        for c in gefunden
        for d in gefunden
        if c != d and re.search(rf"(?<!\w){re.escape(codes[c].lower())}(?!\w)", codes[d].lower())
    }
    werte = [c for c in gefunden if c not in doppelt]
    return werte, [*gefunden.values(), *weitere]


def _wort_bekannt(wort: str, erkannt: list[str]) -> bool:
    """Ein Wort nach „im/in/Branche“ ist bekannt, wenn es ein Monat, ein Füllwort oder ein erkanntes Merkmal ist.

    Erkannt heißt: das Wort ist der Anfang einer erkannten Wendung („Gesundheits-“ in „Gesundheits- und
    Sozialwesen“) oder eine erkannte Wendung mit höchstens zwei Buchstaben Endung („Wiens“). Eine Zusammensetzung
    („Produktionslauf“, „Hausverwaltung“) ist damit unbekannt.
    """
    klein = wort.lower().strip("-")
    if (
        not klein
        or klein.isdigit()
        or klein in MONATSNAMEN
        or klein in _FUNKTIONSWORT
        or klein in _KEIN_MERKMAL_WORT
        or klein in BEKANNT
    ):
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


#: Die Frage meint den Regelsatz v2 (Änderungsaufträge, Zählung je Monat). Standard bleibt v1.
_V2_WORT = re.compile(
    r"(?<!\w)v2(?!\w)|regelsatz\s*(?:2|zwei)(?!\w)|änderungsauftr|aenderungsauftr|im\s+(?:ganzen|gesamten)\s+monats?\b"
    r"|(?<!\w)ganzes\s+monats?\b|(?:über|ueber)\s+(?:das|den)\s+(?:ganze[ns]?|gesamte[ns]?)\s+monats?\b",
    re.IGNORECASE,
)
#: Ein genannter Regelsatz, auch einer, den es noch nicht gibt: „Regelsatz v3“, „v3“, „Regelsatz drei“.
_REGELSATZ_NAME = re.compile(
    r"(?<!\w)regelsatz\s*(?:v?(\d+)|(eins|zwei|drei))(?!\w)|(?<!\w)v(\d+)(?!\w)", re.IGNORECASE
)
_ZAHLWORT = {"eins": "1", "zwei": "2", "drei": "3"}
_V1_WORT = re.compile(r"(?<!\w)v1(?!\w)|regelsatz\s*(?:1|eins)(?!\w)", re.IGNORECASE)
_V2_ZIEL = r"(?:(?:dem|den|der|die|des)\s+)?(?:regelsatz\s*(?:v?2|zwei)(?!\w)|v2(?!\w)|(?:änderungs|aenderungs)auftr)"
#: Optional zwischen dem Wort und den Änderungsaufträgen: „vor der Umsetzung der …“, „ohne Berücksichtigung der …“.
_V2_UMSETZUNG = r"(?:(?:der|die)\s+)?(?:(?:umsetzung|berücksichtigung|beruecksichtigung|anwendung)\s+)?"
#: „ohne die Änderungsaufträge“, „bevor die Änderungsaufträge …“, „nicht nach v2“: gerade nicht der Regelsatz v2.
_V2_VERNEINT = re.compile(
    rf"(?<!\w)(?:ohne|vor|bevor|nicht|statt|außer|ausser)\s+{_V2_UMSETZUNG}(?:(?:nach|im|in|laut)\s+)?{_V2_ZIEL}",
    re.IGNORECASE,
)
#: „vor und nach den Änderungsaufträgen“, „vor oder nach Umsetzung der …“, „mit und ohne v2“: beide Regelsätze zugleich.
_V2_BEIDE = re.compile(
    rf"(?<!\w)(?:vor\s+(?:und|oder)\s+nach|mit\s+(?:und|oder)\s+ohne)\s+{_V2_UMSETZUNG}{_V2_ZIEL}",
    re.IGNORECASE,
)
#: Die Angabe des Regelsatzes in der Frage. Sie ist weder Bezug noch Merkmal und darf die Gliederung nicht verdecken.
_REGELSATZ_ANGABE = re.compile(
    r"(?:(?<!\w)(?:nach|laut|gemäß|im|in|und)\s+)?(?:(?<!\w)(?:dem|den|der)\s+)?"
    r"(?:regelsatz\s*(?:v?\d+|eins|zwei|drei)(?!\w)|(?<!\w)v\d+(?!\w)|(?:änderungs|aenderungs)auftr\w*)",
    re.IGNORECASE,
)
_REGELSATZ_UND_GLIEDERUNG = re.compile(
    r"(?<!\w)nach\s+(?:regelsatz\s*)?v\d+\s+und\s+(?:nach\s+)?", re.IGNORECASE
)


def _regelsatz_der_frage(frage: str) -> str | None:
    """Der Regelsatz, den die Frage außer v1 meint; ein unbekannter Name geht vor v2, damit er nicht still wegfällt."""
    namen = {
        f"v{treffer.group(1) or treffer.group(3) or _ZAHLWORT[treffer.group(2).lower()]}"
        for treffer in _REGELSATZ_NAME.finditer(frage)
    }
    andere = sorted(namen - {"v1", "v2"})
    if andere:
        return andere[0]
    return "v2" if _V2_WORT.search(frage) else None


def _kein_regelsatz(conn: Verbindung, frage: str, regelsatz: str) -> dict[str, Any]:
    """Der genannte Regelsatz hat keinen fertigen Lauf: Hinweis mit seinem Namen statt still der v1-Zahl."""
    zeilen = conn.execute(
        "SELECT DISTINCT regelsatz FROM meta.lauf WHERE status IN ('fertig', 'unveraendert') ORDER BY 1"
    ).fetchall()
    gerechnet = [str(z["regelsatz"]) for z in zeilen]
    vorhanden = ""
    if len(gerechnet) == 1:
        vorhanden = f" Es gibt Zahlen im Regelsatz {gerechnet[0]}."
    elif gerechnet:
        vorhanden = f" Zahlen gibt es in den Regelsätzen {_aufzaehlung(gerechnet)}."
    text = f"Im Regelsatz {regelsatz} ist noch kein Monat gerechnet.{vorhanden}"
    return _antwort(fragetyp(frage), text, hinweise=[text])


def _gliederung_ohne_nach(conn: Verbindung, frage: str, letzter: str) -> str:
    """„Juli 2026 v2 Bundesland“: Das bloße Wort meint die Aufteilung, sonst fiele sie still weg."""
    gelesen = _normalisieren(frage, letzter)[
        0
    ]  # „Sommer 2025“ kennt die Wörter-Prüfung in _filter nur als Monate.
    genannt = monate_lesen(gelesen)
    monat = genannt[-1] if genannt else letzter
    if _gliederung(frage) is not None or _filter(conn, gelesen, monat, (), woerter=False)[0]:
        return frage
    for merkmal in MERKMALE:
        for wort in merkmal.gliederung:
            if re.search(rf"(?<!\w){wort}", frage, re.IGNORECASE):
                return re.sub(rf"(?<!\w)({wort})", r"nach \1", frage, count=1, flags=re.IGNORECASE)
    return frage


def _nach_regeln(regelsatz: str) -> str:
    """Sichtbarer Name des Stands im Antwortsatz, gleiche Wörter wie ``mitRegeln`` in web/components/uc3/regelsatz-name.ts."""
    if regelsatz == "v1":
        return "nach den alten Regeln"
    if regelsatz == "v2":
        return "nach den Änderungsaufträgen"
    nummer = re.fullmatch(r"v(\d+)", regelsatz)
    return f"nach der neuen Fassung {nummer.group(1)}" if nummer else f"nach {regelsatz}"


def _beispiel_stand(regelsatz: str) -> str:
    """Für Beispielfragen: Sie sind anklickbar und müssen wieder gelesen werden; „neue Fassung 3“ versteht der Parser nicht."""
    return "nach den Änderungsaufträgen" if regelsatz == "v2" else f"nach Regelsatz {regelsatz}"


def _regelsatz_antwort(conn: Verbindung, frage: str, regelsatz: str) -> dict[str, Any]:
    """Antwort in einem Regelsatz, der nicht am Stichtag zählt: über ``statagent.uc4.antwort_daten``, das die Zählweise
    und die Kategorien aus den Regeln liest. Was der Adapter nicht lesen kann, bekommt eine Absage statt einer Zahl.
    """
    typ = fragetyp(frage)
    if _V2_VERNEINT.search(frage) and not _V2_BEIDE.search(frage):
        text = (
            "Ohne Änderungsaufträge gelten die alten Regeln. Fragen Sie ohne diese Angabe, "
            "zum Beispiel „Beschäftigungsverhältnisse in Wien im Juli 2026“."
        )
        return _antwort(typ, text, hinweise=[text])
    if typ == "fluktuation":
        text = (
            f"Die Fluktuation vergleicht zwei Stichtage. Es gibt sie nur nach den alten Regeln, nicht {_nach_regeln(regelsatz)}. "
            "Zum Beispiel „Fluktuation im Oktober 2025“."
        )
        return _antwort(typ, text, hinweise=[text])
    letzter = _letzter_monat(conn, regelsatz) or LETZTE_LIEFERUNG
    # Zeitangaben wie „März bis Juni 2025“ sind erst nach dem Übersetzen mehrere Monate.
    genannt = set(monate_lesen(_normalisieren(frage, letzter)[0]))
    jahr = jahr_ohne_monat(frage)
    # Ein Durchschnitt braucht mehrere Monate oder ein Jahr; zu einem einzelnen Monat sagt auch v1 ab.
    absage = nicht_auswertbar(frage, mittel=len(genannt) > 1 or (not genannt and jahr is not None))
    if absage is not None:
        return _antwort(typ, absage, hinweise=[absage])
    stand = _nach_regeln(regelsatz)
    beispiel_stand = _beispiel_stand(regelsatz)
    beispiel = f"Zum Beispiel „Beschäftigungsverhältnisse in Wien im Juli 2026 {beispiel_stand}“."
    nicht_lesbar = (
        f"{stand[0].upper()}{stand[1:]} gibt es nur Zahlen nach Monat, Bundesland, Geschlecht, Branche und "
        f"Beschäftigungskategorie. {beispiel}"
    )
    if "anteil" in frage.lower():
        return _antwort(typ, nicht_lesbar, hinweise=[nicht_lesbar])
    beide = _V1_WORT.search(frage) is not None or _V2_BEIDE.search(frage) is not None
    frage = _V1_WORT.sub(" ", _REGELSATZ_ANGABE.sub(" ", _REGELSATZ_UND_GLIEDERUNG.sub("nach ", frage)))
    erster = _erster_monat(conn, regelsatz) or letzter
    # Der Grund aus der Prüfung passt zur Frage („mehrere Bundesländer“), die allgemeine Liste widerspräche ihr.
    frage = _gliederung_ohne_nach(conn, frage, letzter)
    # Übersetzt lesen: „Sommer 2025“ ist hier noch kein Monat, die Wörter-Prüfung in _filter kennt nur Monate.
    gelesen = _normalisieren(frage, letzter)[0]
    ohne_bezug = _ohne_bezug(conn, gelesen, letzter, woerter=False)
    if ohne_bezug and not genannt and jahr is None:
        if regelsatz != "v2":
            return _antwort(typ, nicht_lesbar, hinweise=[nicht_lesbar])
        text = (
            "Nach den Änderungsaufträgen zählt ein Beschäftigungsverhältnis, wenn es irgendwann im Monat bestand. "
            f"Nach den alten Regeln zählt der letzte Tag des Monats. {beispiel}"
        )
        return _antwort(typ, text, hinweise=[text])
    if beide:
        text = (
            "Die Datenanfrage zeigt immer nur einen Stand: nach den alten Regeln oder nach den Änderungsaufträgen. "
            f"Fragen Sie je einmal. {beispiel}"
        )
        return _antwort(typ, text, hinweise=[text])
    if _VERGLEICH_VORMONAT.search(frage) or (_VERAENDERUNG.search(frage) and not _SEIT.search(frage)):
        # Der v2-Weg zeigt einen Monat oder Zeitraum: Der Stand eines Monats wäre hier eine andere Antwort.
        text = (
            f"Einen Vergleich mit dem Vormonat zeigt StatAgent {stand} nicht. Bitte einen Monat oder "
            f"Zeitraum nennen, zum Beispiel „Beschäftigungsverhältnisse März bis Juni 2025 {beispiel_stand}“."
        )
        return _antwort(typ, text, hinweise=[text])
    if _ZEITREIHE.search(frage.lower()):
        text = (
            "Bitte nennen Sie einen Monat oder Zeitraum, "
            f"zum Beispiel „Beschäftigungsverhältnisse März bis Juni 2025 {beispiel_stand}“."
        )
        return _antwort(typ, text, hinweise=[text])
    if (
        jahr is not None
        and not genannt
        and "durchschnitt" not in frage.lower()
        and erster[:4] <= jahr <= letzter[:4]
    ):
        monat = min(max(f"{jahr}-03", erster), letzter)
        return _rueckfrage(
            f"Für welchen Monat {jahr} möchten Sie die Zahl {stand} wissen? "
            f"Zum Beispiel „Beschäftigungsverhältnisse im {_monat_anzeige(monat)} {beispiel_stand}“."
        )
    if ohne_bezug:
        return _antwort(typ, nicht_lesbar, hinweise=[nicht_lesbar])
    # Erst hier die Wörter-Prüfung, sonst verdrängt sie Erklärung und Regelsatz-Sätze. Alle Merkmale ausgenommen:
    # Zwei Werte eines Merkmals („Wien und Tirol“) darf dieser Weg zeigen. „ohne Kinder“ fiele sonst still weg.
    monate_v2 = monate_lesen(gelesen)
    _filter(conn, gelesen, monate_v2[-1] if monate_v2 else letzter, MERKMALE)
    if not _adapter_liest_gleich(conn, frage, regelsatz):
        return _antwort(typ, nicht_lesbar, hinweise=[nicht_lesbar])
    daten = antwort_daten(conn, frage, regelsatz)
    nach = _nach_regeln(regelsatz)
    text = f"{nach[0].upper()}{nach[1:]}: {daten['text']}" if daten["zahlen"] else daten["text"]
    antwort = _antwort(typ, text, belege=daten["belege"], zahlen=daten["zahlen"])
    # In der Kette zählt der erste Satz: Beim Zeitraum der Durchschnitt, nicht die Erklärung des Zeitraums.
    mittel = [z for z in daten["zahlen"] if ", Durchschnitt " in str(z["bezeichnung"])]
    if mittel:
        name, _, zeit = str(mittel[0]["bezeichnung"]).partition(", Durchschnitt ")
        antwort["antwortsatz"] = (
            f"Im Durchschnitt waren es {_deutsch(int(mittel[0]['wert']))} {name}, {zeit}, {nach}."
        )
    return antwort


def _ohne_bezug(conn: Verbindung, frage: str, letzter: str, woerter: bool = True) -> bool:
    """Weder ein Wort zum Bestand noch ein Merkmal, und außer der Zeitangabe stehen andere Wörter da.

    „März 2025“ allein bleibt eine Frage nach dem Bestand, „asdf im März 2025“ nicht. ``_filter`` sagt ab, wenn nach
    „in“ ein unbekanntes Wort steht („in Wein“, „in Vienna“), auch bei einer bloßen Jahreszahl.
    """
    text = frage.lower()
    genannt = monate_lesen(frage)
    if _filter(conn, frage, genannt[-1] if genannt else letzter, (), woerter=woerter)[0]:
        return False
    if _BEZUG.search(text) or _gliederung(frage) is not None or _ALTER_GRUPPEN.search(text):
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


def _ausserhalb_text(von: str, bis: str) -> str:
    """Rückfrage zu einem Zeitraum ganz außerhalb der Daten; ein Winter, der noch im Vorjahr beginnt, hat einen Nachbarn.

    „Winter 2024“ heißt Dezember 2023 bis Februar 2024. Gemeint ist oft Dezember 2024 bis Februar 2025, das sagen wir.
    """
    zeit = zeitraum_anzeige(von, bis)
    daten = zeitraum_anzeige(ERSTE_LIEFERUNG, LETZTE_LIEFERUNG)
    neu_von, neu_bis = monat_verschieben(von, 12), monat_verschieben(bis, 12)
    if von[5:7] == "12" and bis[5:7] == "02" and neu_von >= ERSTE_LIEFERUNG and neu_bis <= LETZTE_LIEFERUNG:
        return (
            f"Für {zeit} gibt es keine Zahl, Daten gibt es nur für {daten}. "
            f"Meinen Sie den Winter {neu_von[:4]}/{neu_bis[2:4]}, also {zeitraum_anzeige(neu_von, neu_bis)}?"
        )
    return (
        f"Für {zeit} gibt es keine Zahl, Daten gibt es nur für {daten}. "
        f"Meinen Sie „Beschäftigte im {_monat_anzeige(LETZTE_LIEFERUNG)}“?"
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


def _weiteres_merkmal(conn: Verbindung, frage: str, letzter: str) -> bool:
    """Nennt die Frage neben dem Geschlecht noch ein Merkmal („im Bau“, „Angestellte“)?"""
    gelesen = _normalisieren(frage, letzter)[0]
    genannt = monate_lesen(gelesen)
    monat = genannt[-1] if genannt else letzter
    if _alter_lesen(gelesen) is not None or _FREIER_DV.search(gelesen.lower()):
        return True
    alle = tuple(m for m in MERKMALE if m is not GESCHLECHT)
    return any(_werte(gelesen, m, _codes(conn, m, monat))[0] for m in alle)


def _zwei_merkmale_mit_und(frage: str, je_merkmal: list[tuple[str, str]]) -> None:
    """„Frauen und Beamte“ nennt zwei Merkmale: Beide zugleich oder zwei Zahlen? Das rechnen wir nicht still."""
    text = frage.lower()
    for name_a, a in je_merkmal:
        for name_b, b in je_merkmal:
            if name_a != name_b and re.search(
                rf"(?<!\w){re.escape(a.lower())}\s+(?:und|oder)\s+(?:(?:in|im|der|den|die|bei)\s+)*"
                rf"{re.escape(b.lower())}(?!\w)",
                text,
            ):
                raise _KeineZahl(
                    f"Soll für „{a}“ und „{b}“ beides zugleich gelten, oder möchten Sie zwei Zahlen? "
                    "Bitte getrennt fragen."
                )


def _filter(
    conn: Verbindung, frage: str, monat: str, ohne: tuple[Merkmal, ...], woerter: bool = True
) -> tuple[list[tuple[Merkmal, str]], list[str]]:
    """Ausprägungen der Frage (z. B. „Wien“, „ÖNACE F“, „Gastronomie“) als Filter, außer für gegliederte Merkmale.

    Nie still falsch: Zwei Werte eines Merkmals („Wien und Tirol“) oder ein Wort nach „im/in“, das kein Merkmal
    ergibt („im Bergbaubetrieb“), führen zu einer Absage statt zu einer Zahl für etwas anderes.
    """
    filter_: list[tuple[Merkmal, str]] = []
    etiketten: list[str] = []
    erkannt: list[str] = []
    je_merkmal: list[tuple[str, str]] = []
    for merkmal in MERKMALE:
        codes = _codes(conn, merkmal, monat)
        werte, stellen = _werte(frage, merkmal, codes)
        erkannt += stellen
        je_merkmal += [(merkmal.name, s) for s in stellen]
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
    _zwei_merkmale_mit_und(frage, je_merkmal)
    freier_dv = _FREIER_DV.search(frage.lower())
    if freier_dv:
        filter_.append((FREIER_DV, "true"))
        etiketten.append("freie Dienstverträge")
        erkannt += ["freie dienstverträge", freier_dv.group(0)]
    alter = _alter_lesen(frage)
    if alter is not None:
        filter_.append((alter[0], alter[1]))
        etiketten.append(alter[2])
        erkannt.append(alter[2])
    for kette in _ORT_KETTE.findall(frage):
        for wort in re.split(r"\s*(?:,|\bund\b|\boder\b|\bsowie\b)\s*", kette, flags=re.IGNORECASE):
            if not _wort_bekannt(wort, erkannt):
                raise _KeineZahl(f"Das Wort „{wort}“ kenne ich nicht als Bundesland oder Branche. {KANN}")
    if not woerter:
        return filter_, etiketten
    if _FLUKTUATION.search(frage.lower()):
        erkannt += ["höchste", "höchsten", "höchster", "höchstem", "höchstes", "hoechste", "am höchsten"]
    fremd = unbekanntes_wort(_ohne_altersangabe(frage) if alter is not None else frage, erkannt)
    if fremd is not None and fremd.lower() in _VERNEINUNG:
        raise _KeineZahl(
            f"Eine Zahl für alle außer einer Gruppe rechnet StatAgent nicht. Bitte nach allen und nach der Gruppe "
            f"einzeln fragen. {KANN}"
        )
    if fremd is not None:
        wort = "die Angabe" if fremd.isdigit() else "das Wort"
        raise _KeineZahl(
            f"Das kann ich nicht beantworten, weil ich {wort} „{fremd[:40]}“ hier nicht kenne. {KANN}"
        )
    return filter_, etiketten


def _branche_ueber_wechsel(
    conn: Verbindung, frage: str, filter_: list[tuple[Merkmal, str]], letzter_alt: str, neu_ab: str
) -> tuple[list[tuple[Merkmal, str]], str] | None:
    """Filter für die Monate vor dem ÖNACE-Wechsel und ein Hinweissatz, wenn die Branche beide Male gleich heißt.

    „Gesundheits- und Sozialwesen“ ist bis Dezember 2024 Abschnitt Q, ab Jänner 2025 Abschnitt R. Heißt die Branche
    verschieden („Handel“) oder meint derselbe Buchstabe zwei Bereiche („ÖNACE Q“), gibt es keine gemeinsame Zahl.
    """
    code_neu = next(code for m, code in filter_ if m is OENACE)
    namen_alt, namen_neu = _codes(conn, OENACE, letzter_alt), _codes(conn, OENACE, neu_ab)
    werte_alt = _werte(frage, OENACE, namen_alt)[0]
    if len(werte_alt) != 1 or namen_alt[werte_alt[0]] != namen_neu.get(code_neu):
        return None
    code_alt, name = werte_alt[0], namen_neu[code_neu]
    filter_alt = [(m, code_alt if m is OENACE else code) for m, code in filter_]
    wie = (
        f"bleibt dabei Abschnitt {code_neu}"
        if code_alt == code_neu
        else f"ist bis {_monat_anzeige(letzter_alt)} Abschnitt {code_alt}, ab {_monat_anzeige(neu_ab)} Abschnitt {code_neu}"
    )
    return filter_alt, (
        f"Die Wirtschaftsbereiche wurden im {_monat_anzeige(neu_ab)} neu eingeteilt: {name} {wie}. "
        "Über den Wechsel hinweg ist der Vergleich darum nur ungefähr."
    )


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
    nur: tuple[str, ...] = (),
) -> dict[str, Any]:
    """``nur``: aufgezählte Monate („März und Juli 2025“); die Monate dazwischen gehören nicht zur Frage."""
    definition, einheit = _definition_bestand(conn)
    filter_, etiketten = _filter(conn, frage, bis, gruppen)
    verstanden = _verstanden(von, bis, filter_, etiketten, gruppen)
    if nur:
        # Nur die genannten Monate: „bis“ stimmte hier nicht.
        verstanden = verstanden.replace(
            f"{_monat_anzeige(von)} bis {_monat_anzeige(bis)}",
            _aufzaehlung([_monat_anzeige(m) for m in nur]),
            1,
        )
    if any(m is FREIER_DV for m, _ in filter_) and regelsatz != "v1":
        raise _KeineZahl(
            f"Freie Dienstverträge kann die Datenanfrage nur nach den alten Regeln trennen, nicht {_nach_regeln(regelsatz)}. {KANN}"
        )
    abschnitte = [(von, bis, filter_)]
    hinweise: list[str] = []
    if OENACE in gruppen or any(m is OENACE for m, _ in filter_):
        v_von, v_bis = _oenace_version(conn, von), _oenace_version(conn, bis)
        if v_von and v_bis and v_von[0] != v_bis[0]:
            letzter_alt = monat_verschieben(v_bis[1], -1)
            ueber = (
                None
                if OENACE in gruppen
                else _branche_ueber_wechsel(conn, frage, filter_, letzter_alt, v_bis[1])
            )
            if ueber is None:
                raise _KeineZahl(
                    f"Für diesen Zeitraum gibt es keine gemeinsame Zahl, weil die Wirtschaftsbereiche im "
                    f"{_monat_anzeige(v_bis[1])} neu eingeteilt wurden. Bitte getrennt fragen: "
                    f"{zeitraum_anzeige(von, letzter_alt)} und {zeitraum_anzeige(v_bis[1], bis)}."
                )
            filter_alt, hinweis = ueber
            abschnitte = [(von, letzter_alt, filter_alt), (v_bis[1], bis, filter_)]
            hinweise.append(hinweis)
            # Der Buchstabe gilt nur für einen Teil des Zeitraums; der Hinweis nennt beide.
            code_neu = next(code for m, code in filter_ if m is OENACE)
            verstanden = verstanden.replace(f"Branche {code_neu} ", "Branche ", 1)
    if len(_monate(von, bis)) > 120:
        raise _KeineZahl(
            f"Daten gibt es nur für {zeitraum_anzeige(ERSTE_LIEFERUNG, LETZTE_LIEFERUNG)}. "
            "Bitte einen Zeitraum darin nennen."
        )
    # Ein Ergebnis über HOECHSTENS_ZEILEN liest sql_lesen nur abgeschnitten: dann je Monat eine Abfrage.
    abfragen: list[tuple[str, list[dict[str, Any]]]] = []
    sql_text = ""
    for teil_von, teil_bis, teil_filter in abschnitte:
        sql_text = bestand_sql(conn, regelsatz, teil_von, teil_bis, teil_filter, gruppen)
        try:
            abfragen.append((sql_text, _lesen(conn, sql_text)))
        except _Abgeschnitten:
            for monat in _monate(teil_von, teil_bis):
                text_m = bestand_sql(conn, regelsatz, monat, monat, teil_filter, gruppen)
                try:
                    zeilen_m = _lesen(conn, text_m)
                except _Abgeschnitten:
                    raise _KeineZahl(
                        f"Für {_monat_anzeige(monat)} wären es zu viele Zahlen für eine Antwort. Bitte enger fragen, "
                        "zum Beispiel mit weniger Aufteilungen oder für ein Bundesland."
                    ) from None
                if zeilen_m:
                    abfragen.append((text_m, zeilen_m))
    if nur:
        abfragen = [(text_q, [z for z in zeilen if str(z["monat"]) in nur]) for text_q, zeilen in abfragen]
    alle = [z for _, zeilen in abfragen for z in zeilen]
    staende = _staende(alle)
    info = _laufinfo(conn, regelsatz, staende)
    for s in staende:
        s["fortgeschrieben"] = info.get(int(s["lauf"]), (0, True))[0]
    ohne_stichtag = {str(s["monat"]) for s in staende if not info.get(int(s["lauf"]), (0, True))[1]}
    if ohne_stichtag:
        hinweise.append(
            f"Für {', '.join(_monat_anzeige(m) for m in sorted(ohne_stichtag))} zählt der Lauf nicht am Stichtag "
            "(letzter Tag des Monats); dafür gibt es hier keine Zahl."
        )
    fehlend = [m for m in (nur or _monate(von, bis)) if m not in {str(s["monat"]) for s in staende}]
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
        if gruppen == (ALTERSGRUPPE,):
            # „bis 14“ zuerst, „Alter unbekannt“ zuletzt: Reihenfolge der Klassifikation, nicht des Texts.
            rang = {code: i for i, code in enumerate(_codes(conn, ALTERSGRUPPE, von))}
            zeilen = sorted(zeilen, key=lambda z: (str(z["monat"]), rang.get(str(z["g0"]), len(rang))))
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
        if von != bis and (bis < ERSTE_LIEFERUNG or von > LETZTE_LIEFERUNG):
            # Ganz außerhalb der Daten: zuerst das, die Kette zeigt nur den ersten Satz.
            return _rueckfrage(_ausserhalb_text(von, bis))
        if von == bis and not staende:
            text = _kein_lauf_text(von)
        else:
            text = f"Für {zeitraum_anzeige(von, bis)} gibt es keine Zahl."
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
    antwortsatz, ersetzt = _antwortsatz(gezaehlt, zusatz, text)
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
            durchschnitts_satz = (
                f"Im Durchschnitt waren es {_deutsch(durchschnitt)} "
                f"(Mittelwert der {_anzahl_monate(len(je_monat))}, auf ganze Zahlen gerundet)."
            )
            text += f" {durchschnitts_satz}"
            antwortsatz = f"Im Durchschnitt waren es {_deutsch(durchschnitt)} Beschäftigungsverhältnisse{zusatz}, {zeitraum}."
            ersetzt = durchschnitts_satz
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
            antwortsatz, ersetzt = (
                f"Anteil an allen{zusatz} im {_monat_anzeige(von)}: {', '.join(anteile)}.",
                "",
            )
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
    daten = _antwort(
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
    daten["antwortsatz"], daten["ersetzt"] = antwortsatz, ersetzt
    return daten


def _monate(von: str, bis: str) -> list[str]:
    monate: list[str] = []
    monat = von
    while monat <= bis and len(monate) < 600:
        monate.append(monat)
        monat = monat_verschieben(monat, 1)
    return monate


def _antwortsatz(zeilen: list[dict[str, Any]], zusatz: str, text: str) -> tuple[str, str]:
    """Der Satz, mit dem die Kette auf /uc4 die Antwort beginnt, und der Teil des Textes, den er ersetzt.

    Die Station zeigt nur den ersten Satz: Darin muss die Zahl stehen, nicht die Erklärung der Frage (Winter 2025).
    """
    je_monat: dict[str, int] = {}
    for z in zeilen:
        je_monat[str(z["monat"])] = je_monat.get(str(z["monat"]), 0) + int(z["wert"])
    monate = sorted(je_monat)
    if len(monate) == 1:
        monat = monate[0]
        tag = monatsletzter(monat).strftime("%d.%m.%Y")
        satz = (
            f"Am {tag}, dem letzten Tag im {_monat_anzeige(monat)}, gab es {_deutsch(je_monat[monat])} "
            f"Beschäftigungsverhältnisse{zusatz}."
        )
        erster = re.match(r"Am .*?Beschäftigungsverhältnisse[^.]*\.", text)
        return satz, erster.group(0) if erster else ""
    satz = (
        f"Von {_deutsch(je_monat[monate[0]])} im {_monat_anzeige(monate[0])} auf {_deutsch(je_monat[monate[-1]])} "
        f"Beschäftigungsverhältnisse{zusatz} im {_monat_anzeige(monate[-1])}."
    )
    return satz, ""


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
        elif monate != _monate(erster, letzter):
            text = f"Beschäftigungsverhältnisse{zusatz} am Stichtag:"
            text += " " + ", ".join(f"{_monat_anzeige(m)} {_deutsch(je_monat[m])}" for m in monate) + "."
            return text
        else:
            text = (
                f"Beschäftigungsverhältnisse{zusatz} am Stichtag, {_monat_anzeige(erster)} bis "
                f"{_monat_anzeige(letzter)} ({_anzahl_monate(len(monate))}): von {_deutsch(je_monat[erster])} "
                f"auf {_deutsch(je_monat[letzter])}."
            )
            if len(monate) <= MONATE_IM_TEXT and not gruppen:
                text += (
                    " Je Monat: "
                    + ", ".join(f"{_monat_anzeige(m)} {_deutsch(je_monat[m])}" for m in monate)
                    + "."
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


def _pensionsfrage(conn: Verbindung, frage: str) -> dict[str, Any]:
    """Pensionen sind eine eigene Statistik mit eigenen Merkmalen (#77), kein Fall der Beschäftigtenstatistik."""
    try:
        return pensionsantwort(conn, frage)
    except (PensionFehler, psycopg.errors.UndefinedTable, AbfrageVerweigert):
        return _antwort("pensionen", pensionen.NICHT_GELADEN, hinweise=[pensionen.NICHT_GELADEN])
    except psycopg.Error:
        return _antwort("pensionen", pensionen.NICHT_LESBAR, hinweise=[pensionen.NICHT_LESBAR])


def antwort_frage(conn: Verbindung, frage: str, regelsatz: str = "v1") -> dict[str, Any]:
    """Beantwortet eine Datenanfrage ohne Sprachmodell; mehrdeutige Fragen bekommen eine Rückfrage.

    Wirft nie: Was sich nicht beantworten lässt (Zeitlimit, verweigerte Abfrage, zu viele Zahlen, ein Merkmal,
    das es nicht gibt), kommt als Textantwort ohne Zahl und ohne interne Details zurück. Eine Antwort ohne Zahl
    bekommt, wenn es geht, einen Vorschlag zur Frage, der vorher gelaufen ist.
    """
    # Import hier, weil frage_app dieses Modul braucht.
    from statagent.frage_app import app_antwort

    zur_anwendung = app_antwort(conn, frage, regelsatz)
    if zur_anwendung is not None:
        return zur_anwendung
    daten = _antwort_kern(conn, frage, regelsatz)
    daten["text"] = _UEBERNOMMEN.sub(_UEBERNOMMEN_KLAR, daten["text"])
    daten["hinweise"] = [_UEBERNOMMEN.sub(_UEBERNOMMEN_KLAR, h) for h in daten["hinweise"]]
    return _mit_vorschlag(conn, frage, regelsatz, daten)


#: Die Zahl der übernommenen Verhältnisse gilt für den ganzen Lauf, nicht für die gefragte Gruppe.
_UEBERNOMMEN = re.compile(
    r"\b(Im \S+ \d{4}) sind ([\d.]+) Beschäftigungsverhältnisse aus der Lieferung des Vormonats"
)
_UEBERNOMMEN_KLAR = (
    r"\1 sind in ganz Österreich \2 Beschäftigungsverhältnisse aus der Lieferung des Vormonats"
)


# --- Vorschlag: passt zur Frage und ist vor dem Zeigen gelaufen -----------------------------------------------------
_KEIN_VORSCHLAG = re.compile(r"Einzeldaten gibt StatAgent")
#: Die Antwort nennt schon eine Folgefrage („Frauen im Juli 2026“, „Was ist ÖNACE C?“).
_BEISPIEL_DA = re.compile(r"„[^“]*(?:\b20\d{2}\b|\?)[^“]*“")


def _teile_der_frage(conn: Verbindung, frage: str, monat: str) -> tuple[str, list[str], str]:
    """Was die Frage sicher gelesen nennt: Wer, die Einschränkungen und die Aufteilung. Nie ein fremdes Wort."""
    text = frage.lower()
    frau = bool(re.search(r"\bfrauen\b|frauenanteil|weiblich", text))
    mann = bool(re.search(r"\bmänner\w*|maenner|männlich|männeranteil", text))
    was = "Männer und Frauen" if frau and mann else "Frauen" if frau else "Männer" if mann else ""
    orte: list[str] = []
    je = ""
    for merkmal in (BUNDESLAND, OENACE, KATEGORIE):
        try:
            codes = _codes(conn, merkmal, monat)
            werte, stellen = _werte(frage, merkmal, codes)
        except _KeineZahl:
            continue
        if len(werte) > 1:
            je = _JE_ALLTAG.get(merkmal.name, f"je {merkmal.name}")
        elif werte and merkmal is BUNDESLAND:
            orte.append(f"in {codes[werte[0]]}")
        elif werte and merkmal is OENACE:
            wortlaut = next(
                (
                    t.group(0)
                    for s in stellen
                    if (t := re.search(rf"\b(?:im|in der|in|beim)\s+{re.escape(s)}\b", frage, re.IGNORECASE))
                ),
                None,
            )
            orte.append(wortlaut or f"ÖNACE {werte[0]}")
        elif werte:
            was = f"{codes[werte[0]]} {was}".strip()
    gliederung = _gliederung(frage)
    if not je and gliederung is not None and gliederung is not GESCHLECHT:
        je = _JE_ALLTAG.get(gliederung.name, f"je {gliederung.name}")
    if not je and frau and mann and _BUNDESLAND.search(text):
        je = "je Bundesland"
    return was, orte, je


def _vorschlaege(conn: Verbindung, frage: str, letzter: str) -> list[str]:
    gelesen = _normalisieren(alltag_lesen(frage), letzter)[0]
    genannt = [m for m in monate_lesen(gelesen) if ERSTE_LIEFERUNG <= m <= letzter]
    monat = genannt[-1] if genannt else letzter
    zeit = f"im {_monat_anzeige(monat)}"
    if _FLUKTUATION.search(gelesen.lower()):
        return [f"Fluktuation je Wirtschaftsbereich {zeit}"]
    was, orte, je = _teile_der_frage(conn, gelesen, monat)
    wer = was or "Beschäftigungsverhältnisse"
    ende = f" {je}" if je else ""
    kandidaten = [f"{' '.join([wer, *orte, zeit])}{ende}", f"{wer} {zeit}{ende}", f"{wer} {zeit}"]
    return list(dict.fromkeys(kandidaten))


def _mit_vorschlag(conn: Verbindung, frage: str, regelsatz: str, daten: dict[str, Any]) -> dict[str, Any]:
    """Hängt an eine Antwort ohne Zahl einen Vorschlag an, der eine Zahl liefert. Ohne Fragezeichen: keine Rückfrage."""
    if (
        daten["zahlen"]
        or daten["typ"] in ("definition", "pensionen")
        or regelsatz != "v1"
        or _regelsatz_der_frage(alltag_lesen(frage))
        or _KEIN_VORSCHLAG.search(daten["text"])
        or _BEISPIEL_DA.search(daten["text"])
    ):
        return daten
    try:
        for kandidat in _vorschlaege(conn, frage, _letzter_monat(conn, regelsatz) or LETZTE_LIEFERUNG):
            if (
                kandidat.lower() != frage.strip(" ?.!").lower()
                and _antwort_kern(conn, kandidat, regelsatz)["zahlen"]
            ):
                daten["text"] = f"{daten['text']} Zum Beispiel: „{kandidat}“."
                break
    except (psycopg.Error, ValueError, _KeineZahl, _Abgeschnitten, AbfrageVerweigert, RegelFehler):
        return daten  # Ohne Vorschlag bleibt die Absage richtig.
    return daten


def _antwort_kern(conn: Verbindung, frage: str, regelsatz: str = "v1") -> dict[str, Any]:
    if ist_pensionsfrage(frage) and not _PERSON.search(frage.lower()):
        return _pensionsfrage(conn, frage)
    frage = _PROZENTZEICHEN.sub(" Prozent", frage)
    prozent_von_gruppe = _PROZENT_VON_GRUPPE.search(frage) is not None
    frage = alltag_lesen(frage)
    try:
        letzter = _letzter_monat(conn, regelsatz)
    except psycopg.Error:
        return _antwort(fragetyp(frage), NICHT_LESBAR, hinweise=[NICHT_LESBAR])
    # Tiefe Codes (#189) vor Absage und Zählung. Import hier, weil frage_klass dieses Modul braucht.
    from statagent.frage_klass import tiefer_code_antwort

    tief = tiefer_code_antwort(conn, frage)
    if tief is not None:
        return tief
    grund = unklar(frage, letzter or LETZTE_LIEFERUNG)
    if grund is not None:
        return _rueckfrage(grund)
    if _EIN_VERHAELTNIS.search(frage):
        text = f"Wie viele Jobs eine Person hat, wertet StatAgent nicht aus. {KANN}"
        return _antwort(fragetyp(frage), text, hinweise=[text])
    if _ZEITBEZUG.search(frage):
        return _rueckfrage(
            "Zeitangaben mit Bezug auf einen anderen Zeitpunkt rechnet StatAgent nicht um. "
            f"Welchen Monat meinen Sie, zum Beispiel „Beschäftigte im {_monat_anzeige(LETZTE_LIEFERUNG)}“?"
        )
    if _ZAEHLT_ANDERES.search(frage):
        return _antwort(
            fragetyp(frage),
            f"StatAgent zählt Beschäftigungsverhältnisse, nicht Bundesländer, Branchen, Monate oder Regeln. {KANN}",
        )
    try:
        if prozent_von_gruppe and _weiteres_merkmal(conn, frage, letzter or LETZTE_LIEFERUNG):
            text = (
                "Einen Anteil an den Frauen oder an den Männern rechnet StatAgent nicht, nur den Frauen- und "
                "Männeranteil an allen. Zum Beispiel „Wie viel Prozent der Beschäftigten in Wien sind Frauen?“."
            )
            return _antwort(fragetyp(frage), text, hinweise=[text])
        if regelsatz == "v1":
            regelsatz = _regelsatz_der_frage(frage) or regelsatz
        if regelsatz != "v1":
            if _letzter_monat(conn, regelsatz) is None:
                return _kein_regelsatz(conn, frage, regelsatz)
            return _regelsatz_antwort(conn, frage, regelsatz)
    except _KeineZahl as fehler:
        return _antwort(fragetyp(frage), str(fehler), hinweise=[str(fehler)])
    except (psycopg.Error, AbfrageVerweigert, RegelFehler):
        return _antwort(fragetyp(frage), NICHT_LESBAR, hinweise=[NICHT_LESBAR])
    except ValueError:  # „März 0000“: Dieses Datum gibt es nicht.
        return _antwort(fragetyp(frage), _KEIN_DATUM, hinweise=[_KEIN_DATUM])
    hinweis_tag = tag_hinweis(frage)
    try:
        frage, notizen, mittel = _normalisieren(frage, letzter or LETZTE_LIEFERUNG)
    except ValueError:  # „Jänner 0000 gegenüber dem Vormonat“: Den Monat davor gibt es nicht.
        return _antwort(fragetyp(frage), _KEIN_DATUM, hinweise=[_KEIN_DATUM])
    if _VOR_ZEIT.search(frage) and not monate_lesen(frage) and jahr_ohne_monat(frage) is None:
        # „gegenüber dem Vormonat“ ohne Monat: Eine ganze Reihe wäre eine andere Antwort.
        return _rueckfrage_monat("fluktuation" if _FLUKTUATION.search(frage.lower()) else "bestand", None)
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
            if _ZEITWORT_OHNE_MONAT.search(frage):
                # „pro Jahr“, „je Quartal“: Das meint nicht den jüngsten Monat.
                return _rueckfrage_monat(typ, None)
            # Mit „im“: „unter 25“ am Satzende bleibt sonst nicht als Alter lesbar und fiele still weg.
            frage = f"{frage.rstrip(' ?.!')} im {_monat_anzeige(letzter)}"
            if _VERAENDERUNG.search(frage):
                frage = f"{_monat_anzeige(monat_verschieben(letzter, -1))} {frage}"
                typ = fragetyp(frage)
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
    except ValueError:  # „März 0000“: Dieses Datum gibt es nicht.
        return _antwort(typ, _KEIN_DATUM, hinweise=[_KEIN_DATUM])
    if notizen:
        text = daten["text"]
        # Ohne „Verstanden“ (Rückfrage, Absage) zuerst der Text: Die Kette zeigt nur den ersten Satz.
        ende = text.find(". ") + 1 if text.startswith("Verstanden:") else len(text)
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
    if typ != "fluktuation" and _geschlecht_gegliedert(text):
        je = _gliederung(frage)
        erlaubt = (GESCHLECHT,) if typ == "zeitreihe" or "anteil" in text else (GESCHLECHT, BUNDESLAND)
        if je is not None and je not in erlaubt:
            # Sonst fiele „je Branche“ still weg, die Antwort gälte für ganz Österreich.
            wie = _JE_ALLTAG.get(je.name, f"je {je.name}")
            if je is BUNDESLAND:
                raise _KeineZahl(
                    f"Männer und Frauen {wie} zeigt StatAgent nur für einen Monat, nicht über einen Zeitraum."
                )
            raise _KeineZahl(
                f"Männer und Frauen {wie} zeigt StatAgent nicht auf einmal. Bitte einzeln fragen."
            )
    if "anteil" in text and typ != "fluktuation":
        if not _GESCHLECHT.search(text):
            raise _KeineZahl(
                "Einen Anteil rechnet StatAgent nur für Frauen und Männer. Für alles andere: beide Zahlen einzeln "
                f"fragen, zum Beispiel „Beschäftigte nach Bundesland im März 2025“. {KANN}"
            )
        # Auch „seit Jänner 2025“: Das ist ein Zeitraum, die Antwort wäre sonst die Menge statt des Anteils.
        if len(set(monate)) > 1 or typ == "zeitreihe":
            return _rueckfrage(
                "Den Anteil gibt es je Monat. Für welchen Monat möchten Sie ihn, zum Beispiel "
                f"„Frauenanteil im {_monat_anzeige(monate[-1] if monate else LETZTE_LIEFERUNG)}“?"
            )
    if typ == "zeitreihe":
        _aufteilung(frage)  # Männer und Frauen je Altersgruppe: Absage
        aufzaehlung = zeitraum_lesen(frage, _letzter_monat(conn, regelsatz))
        nur = aufzaehlung.nur if aufzaehlung is not None and aufzaehlung.art == "liste" else ()
        if nur:
            von, bis = nur[0], nur[-1]
        elif len(monate) >= 2:
            von, bis = min(monate), max(monate)
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
        return _bestand_antwort(conn, frage, regelsatz, von, bis, gruppen, "zeitreihe", mittel, nur)
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
        if (
            any(m is not OENACE for m, _ in filter_)
            or _BUNDESLAND.search(text)
            or _GESCHLECHT.search(text)
            or _ALTER_GRUPPEN.search(text)
        ):
            raise _KeineZahl(
                "Die Fluktuation gibt es nur für ganz Österreich je Wirtschaftsbereich, nicht je Bundesland, "
                "Geschlecht, Beschäftigungskategorie oder Alter. Vorschlag: „Fluktuation je Wirtschaftsbereich im "
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
