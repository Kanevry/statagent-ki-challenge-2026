"""Fragen zur Anwendung selbst: Begriffe der Seiten und warum ein Monat angehalten ist.

Das ist keine Statistik: Die Texte erklären Wörter, die auf den Seiten stehen. „Warum angehalten“ liest Regelnamen und
Summen der Prüfungen aus ``meta.pruefung_treffer`` und ``meta.regel``, nie Einzeldaten. Nur lesend und ohne Sprachmodell.
Was hier nicht genau erkannt wird, bleibt beim Weg in ``statagent.frage``.
"""

from __future__ import annotations

import re
from typing import Any

import psycopg

from statagent.agenten.werkzeuge import AbfrageVerweigert
from statagent.db import Verbindung
from statagent.ergebnis import letzter_lauf
from statagent.frage import (
    _PERSON,
    NICHT_LESBAR,
    _antwort,
    _beleg,
    _regelsatz_der_frage,
    _rueckfrage,
    monate_lesen,
)
from statagent.uc4 import _ISO, _NAME_MONAT, _ZAHL_MONAT, _monat_anzeige

#: Begriffe der Anwendung: Muster nach „Was ist/heißt/bedeutet“ und die Erklärung.
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
)
_WAS_IST = re.compile(
    r"^\s*was\s+(?:ist|sind|heißt|heisst|bedeutet|meint)\s+(?:(?:ein|eine|einen|der|die|das|den)\s+)*"
    r"(regelsatz|regelsätze|regelsaetze|angehalten|anhalten)\s*\??\s*$",
    re.IGNORECASE,
)
#: Nur dieser Satz, nach dem Entfernen des Monats: Eine weitere Einschränkung („in Wien“) gibt es hier nicht.
_WARUM = re.compile(
    r"(?:warum|wieso|weshalb)\s+(?:ist|war|wurde|bleibt)\s+(?:(?:der\s+)?monat\s+|im\s+|der\s+lauf\s+(?:im\s+)?)?"
    r"angehalten(?:\s+worden)?",
    re.IGNORECASE,
)


def app_antwort(conn: Verbindung, frage: str, regelsatz: str = "v1") -> dict[str, Any] | None:
    """Antwort auf eine Frage zur Anwendung, sonst None. Wirft nicht."""
    try:
        return _beantworten(conn, frage, regelsatz)
    except (psycopg.Error, AbfrageVerweigert):
        return _antwort("definition", NICHT_LESBAR, hinweise=[NICHT_LESBAR])


def _ohne_monat(frage: str) -> str:
    text = frage.lower()
    for muster in (_NAME_MONAT, _ZAHL_MONAT, _ISO):
        text = muster.sub(" ", text)
    return " ".join(text.split()).strip(" ?.!")


def _beantworten(conn: Verbindung, frage: str, regelsatz: str) -> dict[str, Any] | None:
    # Einzeldaten und ein genannter Regelsatz gehen den Weg der Zahlen: Dort stehen Absage und Zählweise.
    if _PERSON.search(frage.lower()) or _regelsatz_der_frage(frage):
        return None
    if _WARUM.fullmatch(_ohne_monat(frage)):
        return _warum_angehalten(conn, frage, regelsatz)
    was = _WAS_IST.match(frage)
    if was:
        wort = was.group(1).lower()
        for muster, text in BEGRIFFE:
            if muster.search(wort):
                return _antwort("definition", text, definition=text)
    return None


def _warum_angehalten(conn: Verbindung, frage: str, regelsatz: str) -> dict[str, Any]:
    genannt = monate_lesen(frage)
    if not genannt:
        return _rueckfrage(
            f"Für welchen Monat? Zum Beispiel „Warum ist {_monat_anzeige('2025-10')} angehalten?“"
        )
    monat = genannt[-1]
    name = _monat_anzeige(monat)
    stand = letzter_lauf(conn, monat, regelsatz)
    if stand is None:
        text = f"Für {name} gibt es keinen gerechneten Lauf."
        return _antwort("definition", text, hinweise=[text])
    # sql_lesen sperrt die Tabelle für freie Abfragen, weil die Spalte ``beispiele`` Kennungen trägt. Dieser feste Text
    # liest sie nicht, nur Summen und Regelnamen, wie die Monatsseite. lauf_id ist eine Zahl aus der Datenbank.
    sql_text = (
        "SELECT r.name, r.beschreibung, t.anzahl FROM meta.pruefung_treffer t JOIN meta.regel r ON r.id = t.regel_id"
        f" WHERE t.lauf_id = {int(stand.lauf_id)} AND t.anhalten ORDER BY t.anzahl DESC"
    )
    zeilen: list[dict[str, Any]] = [dict(z) for z in conn.execute(sql_text.encode()).fetchall()]
    conn.rollback()
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
    if not zeilen:
        text = f"{name} ist nicht angehalten: Keine Prüfung hat den Lauf gestoppt."
        return _antwort("definition", text, belege=[beleg], hinweise=[text])
    wie_viele = "eine Prüfung" if len(zeilen) == 1 else f"{len(zeilen)} Prüfungen"
    kopf = (
        f"{name} ist angehalten, weil {wie_viele} etwas so Großes gefunden "
        f"{'hat' if len(zeilen) == 1 else 'haben'}, dass ein Mensch entscheiden muss."
    )
    text = f"{kopf} Die Zahlen des Monats bleiben vorläufig, bis ein Mensch entschieden hat."
    zahlen = [
        {
            "bezeichnung": f"Gefundene Fälle, {_satz_kurz(str(z['beschreibung']))}",
            "wert": int(z["anzahl"]),
            "einheit": "Anzahl",
            "beleg": 0,
        }
        for z in zeilen
    ]
    return _antwort("definition", text, belege=[beleg], zahlen=zahlen)


def _satz_kurz(text: str) -> str:
    """Der erste Satz der Regelbeschreibung, ohne Schlusspunkt. Kommas teilten sonst den Tabellentitel."""
    satz = re.split(r"(?<=[^\d\s])\.\s", text.strip(), maxsplit=1)[0].rstrip(" .")
    return satz.replace(", ", "; ")
