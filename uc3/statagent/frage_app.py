"""Fragen zur Anwendung selbst: Begriffe, warum ein Monat angehalten ist, was die Prüfungen fanden, was geändert wurde.

Das ist keine Statistik: Die Texte erklären Wörter, die auf den Seiten stehen; alles Monatsbezogene kommt aus
``meta.pruefung_treffer``, ``meta.regel``, ``meta.freigabe`` und ``meta.protokoll`` und zeigt nie Einzeldaten. Nur
lesend und ohne Sprachmodell. Was hier nicht erkannt wird, bleibt beim Weg in ``statagent.frage``.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import psycopg

from statagent.agenten.werkzeuge import AbfrageVerweigert
from statagent.db import Verbindung
from statagent.ergebnis import letzter_lauf
from statagent.frage import (
    NICHT_LESBAR,
    UC,
    _antwort,
    _beleg,
    _lesen,
    _rueckfrage,
    monate_lesen,
)
from statagent.pensionen import NICHT_GELADEN
from statagent.uc4 import _aufzaehlung, _deutsch, _monat_anzeige

#: Begriffe der Anwendung. Schlüssel: Muster nach „Was ist/heißt/bedeutet“.
BEGRIFFE: tuple[tuple[re.Pattern[str], str], ...] = (
    (
        re.compile(r"\bregelsatz\b|\bregelsätze\b|\bregelsaetze\b"),
        "Ein Regelsatz ist die Sammlung aller Regeln, nach denen gezählt wird. StatAgent hat zwei: Nach den alten "
        "Regeln zählt ein Beschäftigungsverhältnis, wenn es am letzten Tag des Monats besteht. Nach den "
        "Änderungsaufträgen zählt es, wenn es irgendwann im Monat bestand.",
    ),
    (
        re.compile(r"\bangehalten\b|\banhalten\b"),
        "Angehalten heißt: Eine Prüfung hat beim Rechnen etwas so Großes gefunden, dass ein Mensch entscheiden muss. "
        "Der Monat ist gerechnet, seine Zahlen bleiben aber vorläufig.",
    ),
    (
        re.compile(r"\bvorläufig\b|\bvorlaeufig\b"),
        "Vorläufig heißt: Die Zahl ist gerechnet, aber noch nicht mit Namen freigegeben, oder eine Prüfung wartet "
        "noch auf eine Entscheidung. Endgültige Zahlen ändern sich nicht mehr.",
    ),
    (
        re.compile(r"\bendgültig\b|\bendgueltig\b|\bveröffentlicht\b"),
        "Endgültig heißt: Ein Mensch hat den Monat mit Vor- und Nachnamen freigegeben. Die Zahl bleibt dann unverändert; "
        "fällt später eine Abweichung auf, steht sie als Revisionsbedarf im Qualitätsbericht.",
    ),
    (
        re.compile(r"\brevisionsbedarf\b|\brevision\b"),
        "Revisionsbedarf heißt: Eine spätere Lieferung zeigt für einen schon veröffentlichten Monat eine andere Zahl. "
        "Die Zahl bleibt, die Abweichung steht im Qualitätsbericht.",
    ),
    (
        re.compile(r"\blauf\b"),
        "Ein Lauf ist eine Rechnung für eine Lieferung: einlesen, prüfen, zählen. Zwei Läufe mit denselben Daten und "
        "Regeln ergeben dieselben Zahlen.",
    ),
    (
        re.compile(r"\bstichtag\b"),
        "Der Stichtag ist der letzte Tag des Monats. Nach den alten Regeln zählt, wer an diesem Tag ein "
        "Beschäftigungsverhältnis hat.",
    ),
    (
        re.compile(r"\bänderungsauftr\w*|\baenderungsauftr\w*"),
        "Ein Änderungsauftrag ist eine Anweisung, wie anders gezählt werden soll. Ein Agent setzt sie als Regel um, ein "
        "Mensch gibt sie mit Namen frei. Erst dann gilt sie.",
    ),
    (
        re.compile(r"\bfreigabe\b"),
        "Eine Freigabe ist die Entscheidung eines Menschen mit Vor- und Nachnamen und Zeitpunkt. Ohne sie gilt keine "
        "Änderung, und kein Monat wird endgültig.",
    ),
    (
        re.compile(r"\bfortschreibung\b|\bfortgeschrieben\b|\bübernommen\b"),
        "Fortgeschrieben heißt: Ein Verhältnis fehlt in der Lieferung, also wird es aus der Lieferung des Vormonats "
        "übernommen. Der Monat bleibt dann vorläufig, und der Qualitätsbericht nennt die Menge.",
    ),
    (
        re.compile(r"\bsvs\b"),
        "SVS ist die Sozialversicherungsanstalt der Selbständigen. Sie entstand zum 1. Jänner 2020 aus SVA, SVB und der "
        "Versicherungsanstalt des österreichischen Notariates. Sie kommt in der Pensionsstatistik vor, nicht in der "
        "Beschäftigtenstatistik.",
    ),
    (
        re.compile(r"\bträger\b|\btraeger\b|\bversicherungsträger\b"),
        "Träger sind die Versicherungsanstalten, die Pensionen auszahlen und ihre Zahlen melden. Sie kommen in der "
        "Pensionsstatistik vor, nicht in der Beschäftigtenstatistik.",
    ),
)
_WAS_IST = re.compile(
    r"^\s*(?:was\s+(?:ist|sind|heißt|heisst|bedeutet|meint)|erkläre?(?:n sie)?(?:\s+mir)?|was\s+versteht\s+man\s+unter)\s+"
    r"(?:(?:ein|eine|einen|der|die|das|den|dem|mit|unter)\s+)*(.{2,60}?)\s*\??\s*$",
    re.IGNORECASE,
)
_WARUM = re.compile(r"\bwarum\b|\bwieso\b|\bweshalb\b", re.IGNORECASE)
_ANGEHALTEN = re.compile(r"\bangehalten\b|\bvorläufig\b|\bvorlaeufig\b", re.IGNORECASE)
_FEHLER = re.compile(
    r"\b(?:welche|was\s+für|gab\s+es|gibt\s+es|zeig\w*)\b.*\b(?:fehler|auffälligkeit\w*|auffaelligkeit\w*|probleme?|befunde?)\b"
    r"|\b(?:fehler|auffälligkeit\w*|auffaelligkeit\w*|probleme?|befunde?)\b.*\b(?:gab|gibt)\s+es\b"
    r"|\bwas\s+(?:ist|war)\b.*\b(?:passiert|los)\b",
    re.IGNORECASE,
)
_JAHR = re.compile(r"(?<!\d)20\d{2}(?!\d)")
_TRAEGER_LISTE = re.compile(r"\bwelche\s+(?:versicherungs)?(?:träger|traeger)\b", re.IGNORECASE)
_AENDERUNG = re.compile(
    r"\bwas\s+(?:wurde|ist|hat\s+sich)\b.*\bgeändert\b|\bwelche\s+änderung\w*\b|\bwelche\s+änderungsauftr\w*\b"
    r"|\bwer\s+hat\b.*\bfreigegeben\b|\bwas\s+wurde\b.*\bfreigegeben\b",
    re.IGNORECASE,
)
#: Die Lieferung ans Ministerium. „Beschäftigte im Ministerium“ meint etwas anderes und bleibt beim Weg der Zahlen.
_MINISTERIUM = re.compile(
    r"\b(?:an|ans|für|fürs)\s+(?:das\s+)?ministerium\b|\bministeriums-?\s*(?:lieferung|liste|datei|auswertung|meldung)"
    r"|\bministerium\s+(?:bekommt|erhält|kriegt)\b|\blieferung\s+(?:an|ans)\b.*\bministerium\b",
    re.IGNORECASE,
)
_BELEG_MINISTERIUM = Path(__file__).resolve().parents[2] / "abgabe" / "ministerium_2026-07.beleg.md"
#: So viele Änderungen nennt die Antwort; die Seite „Freigaben“ zeigt alle.
ANGEZEIGTE_AENDERUNGEN = 5


def app_antwort(conn: Verbindung, frage: str, regelsatz: str = "v1") -> dict[str, Any] | None:
    """Antwort auf eine Frage zur Anwendung, sonst None. Wirft nicht."""
    try:
        return _beantworten(conn, frage, regelsatz)
    except (psycopg.Error, AbfrageVerweigert):
        return _antwort("definition", NICHT_LESBAR, hinweise=[NICHT_LESBAR])


def _beantworten(conn: Verbindung, frage: str, regelsatz: str) -> dict[str, Any] | None:
    if _MINISTERIUM.search(frage):
        return _ministerium()
    if _TRAEGER_LISTE.search(frage):
        return _traeger(conn)
    # Mit einem Monat ist die Änderung der Zahl gemeint: „Was hat sich im Juli 2026 geändert?“
    if _AENDERUNG.search(frage) and not monate_lesen(frage) and not _JAHR.search(frage):
        return _aenderungen(conn)
    if _WARUM.search(frage) and _ANGEHALTEN.search(frage):
        return _pruefungen(conn, frage, regelsatz, nur_anhaltende=True)
    if _FEHLER.search(frage):
        return _pruefungen(conn, frage, regelsatz, nur_anhaltende=False)
    was = _WAS_IST.match(frage)
    if was:
        wort = was.group(1).lower()
        for muster, text in BEGRIFFE:
            if muster.search(wort):
                return _antwort("definition", text, definition=text)
    return None


def _monat_der_frage(frage: str) -> str | None:
    genannt = monate_lesen(frage)
    return genannt[-1] if genannt else None


def _pruefungen(conn: Verbindung, frage: str, regelsatz: str, nur_anhaltende: bool) -> dict[str, Any]:
    monat = _monat_der_frage(frage)
    if monat is None:
        beispiel = (
            f"Warum ist {_monat_anzeige('2025-10')} angehalten?"
            if nur_anhaltende
            else (f"Welche Fehler gab es im {_monat_anzeige('2025-10')}?")
        )
        return _rueckfrage(f"Für welchen Monat? Zum Beispiel „{beispiel}“")
    stand = letzter_lauf(conn, monat, regelsatz)
    name = _monat_anzeige(monat)
    if stand is None:
        text = f"Für {name} gibt es keinen gerechneten Lauf."
        return _antwort("definition", text, hinweise=[text])
    # sql_lesen sperrt die Tabelle für freie Abfragen, weil die Spalte ``beispiele`` Kennungen trägt. Dieser feste Text
    # liest sie nicht, nur Summen und Regelnamen, wie die Monatsseite. lauf_id ist eine Zahl aus der Datenbank.
    sql_text = (
        "SELECT r.name, r.beschreibung, t.anzahl, t.umfang, t.anhalten FROM meta.pruefung_treffer t"
        f" JOIN meta.regel r ON r.id = t.regel_id WHERE t.lauf_id = {int(stand.lauf_id)} AND t.anzahl > 0"
        " ORDER BY t.anhalten DESC, t.anzahl DESC"
    )
    zeilen: list[dict[str, Any]] = [dict(z) for z in conn.execute(sql_text.encode()).fetchall()]
    conn.rollback()  # Nur gelesen; _lesen braucht danach eine Verbindung ohne offene Transaktion.
    anhaltend = [z for z in zeilen if z["anhalten"]]
    beleg = _beleg(
        sql_text,
        [
            {
                "monat": monat,
                "lauf": stand.lauf_id,
                "regelstand": stand.regelstand,
                "status": stand.ergebnis_status,
            }
        ],
    )
    gezeigt = anhaltend if nur_anhaltende else zeilen
    if nur_anhaltende and not anhaltend:
        text = f"{name} ist nicht angehalten: Keine Prüfung hat den Lauf gestoppt."
        return _antwort("definition", text, belege=[beleg], hinweise=[text])
    if not gezeigt:
        text = f"Im {name} hat keine Prüfung etwas gefunden."
        return _antwort("definition", text, belege=[beleg], hinweise=[text])
    if nur_anhaltende:
        kopf = (
            f"{name} ist angehalten, weil {_anzahl_pruefungen(len(anhaltend))} etwas so Großes gefunden "
            f"{'hat' if len(anhaltend) == 1 else 'haben'}, dass ein Mensch entscheiden muss."
        )
    else:
        kopf = f"Im {name} {'hat' if len(zeilen) == 1 else 'haben'} {_anzahl_pruefungen(len(zeilen))} etwas gefunden"
        kopf += (
            f", {len(anhaltend)} davon {'hat' if len(anhaltend) == 1 else 'haben'} den Lauf angehalten."
            if anhaltend
            else "."
        )
    text = " ".join(
        [
            kopf,
            *(f"{_satz_kurz(str(z['beschreibung']))} ({z['umfang']})." for z in gezeigt[:3]),
            "Die Zahlen des Monats bleiben vorläufig, bis ein Mensch entschieden hat.",
        ]
        if anhaltend
        else [kopf]
    )
    zahlen = [
        {
            "bezeichnung": f"Gefundene Fälle, {_satz_kurz(str(z['beschreibung']))}",
            "wert": int(z["anzahl"]),
            "einheit": "Anzahl",
            "beleg": 0,
        }
        for z in gezeigt
    ]
    daten = _antwort("definition", text, belege=[beleg], zahlen=zahlen)
    daten["antwortsatz"], daten["ersetzt"] = kopf, kopf
    return daten


def _anzahl_pruefungen(anzahl: int) -> str:
    return "eine Prüfung" if anzahl == 1 else f"{anzahl} Prüfungen"


def _satz_kurz(text: str) -> str:
    """Der erste Satz der Regelbeschreibung, ohne Schlusspunkt. Kommas blieben im Tabellentitel: sie werden Strichpunkte."""
    satz = re.split(r"(?<=[^\d\s])\.\s", text.strip(), maxsplit=1)[0].rstrip(" .")
    return satz.replace(", ", "; ")


def _traeger(conn: Verbindung) -> dict[str, Any]:
    sql_text = (
        "SELECT code, bezeichnung FROM stat.klass_versicherungstraeger"
        " WHERE ebene = 3 AND gueltig_bis IS NULL ORDER BY code"
    )
    try:
        zeilen = _lesen(conn, sql_text)
    except (psycopg.errors.UndefinedTable, AbfrageVerweigert):
        conn.rollback()
        return _antwort("definition", NICHT_GELADEN, hinweise=[NICHT_GELADEN])
    namen = _aufzaehlung([f"{z['code']} ({z['bezeichnung']})" for z in zeilen])
    text = f"In der Pensionsstatistik melden heute {len(zeilen)} Träger: {namen}. In der Beschäftigtenstatistik gibt es dieses Merkmal nicht."
    return _antwort("definition", text, definition=text, belege=[_beleg(sql_text, [])])


def _aenderungen(conn: Verbindung) -> dict[str, Any]:
    sql_text = (
        "SELECT to_char(f.zeitpunkt AT TIME ZONE 'Europe/Vienna', 'DD.MM.YYYY HH24:MI') AS zeit, f.name, p.anweisung"
        " FROM meta.freigabe f JOIN meta.protokoll p ON p.id = f.protokoll_id"
        " WHERE f.entscheidung = 'ja' AND f.objekt_typ = 'regel' ORDER BY f.zeitpunkt DESC"
    )
    zeilen = _lesen(conn, sql_text)
    if not zeilen:
        text = "Bisher ist keine Regel mit einem Namen freigegeben worden."
        return _antwort("definition", text, hinweise=[text])
    teile = [
        f"{z['zeit']}, {z['name']}: {_auftrag_kurz(str(z['anweisung']))}"
        for z in zeilen[:ANGEZEIGTE_AENDERUNGEN]
    ]
    anzahl = "Eine Regel wurde" if len(zeilen) == 1 else f"{len(zeilen)} Regeln wurden"
    weitere = "" if len(zeilen) <= ANGEZEIGTE_AENDERUNGEN else " Alle stehen auf der Seite Freigaben."
    text = f"{anzahl} mit Namen und Zeitpunkt freigegeben. Zuletzt: {' '.join(teile)}{weitere}"
    return _antwort("definition", text, definition=text, belege=[_beleg(sql_text, [])])


def _auftrag_kurz(anweisung: str) -> str:
    """Nur der Kopf des Auftrags: Die Anweisung an den Agenten füllt sonst den Bildschirm, ohne Anführungszeichen."""
    kopf = re.split(r"(?<=[^\d\s])[.:]\s", anweisung.strip(), maxsplit=1)[0].replace("„", "").replace("“", "")
    return f"{kopf[:120].rstrip()}."


def _ministerium() -> dict[str, Any]:
    erklaerung = (
        "Das Ministerium bekommt eine Liste aller Personen, die in den letzten zwölf Monaten bis zum Berichtsmonat "
        "mindestens 200 Tage als Arbeiter beschäftigt waren. Sie enthält Einzeldaten und liegt darum nicht in der "
        "Anwendung, sondern im Abgabeordner."
    )
    try:
        treffer = re.search(
            r"\|\s*Zeilen\s*\|\s*(\d+) Personen", _BELEG_MINISTERIUM.read_text(encoding="utf-8")
        )
    except OSError:
        treffer = None
    if treffer is None:
        return _antwort("definition", erklaerung, definition=erklaerung)
    personen = int(treffer.group(1))
    beleg = {
        "uc": UC,
        "quelle": "abgabe/ministerium_2026-07.beleg.md",
        "ref": "abgabe/ministerium_2026-07.beleg.md",
    }
    return _antwort(
        "definition",
        f"In der Lieferung an das Ministerium stehen {_deutsch(personen)} Personen. {erklaerung}",
        definition=erklaerung,
        belege=[beleg],
        zahlen=[
            {
                "bezeichnung": "Personen in der Ministeriums-Lieferung",
                "wert": personen,
                "einheit": "Personen",
                "beleg": 0,
            }
        ],
    )
