"""Bericht eines Falls aus PG (Ereignisse, Teilnahme, Positionen); Matrix und Einordnung rechnet der Code neu.

Der Bericht liest nur, was der Lauf geschrieben hat; so zeigt das Terminal denselben Stand wie ein späteres
Replay. Das 8-teilige Protokoll ist #45.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

import psycopg

from uc2.verhandlung import matrix
from uc2.verhandlung.speicher import (
    lies_ereignisse,
    lies_fall,
    lies_freigabe,
    lies_positionen,
    lies_teilnahme,
)

PRUEF_ARTEN = ("zahl_ohne_beleg", "beleg_ungueltig", "zitat", "ungueltige_ausgabe", "zahl_widerspruch")


def _iso(wert: object) -> object:
    return wert.isoformat() if isinstance(wert, date | datetime) else wert


def bericht(verbindung: psycopg.Connection[Any], fall_id: int) -> dict[str, Any]:
    fall = lies_fall(verbindung, fall_id)
    if fall is None:
        raise LookupError(f"Fall {fall_id} nicht gefunden")
    ereignisse = lies_ereignisse(verbindung, fall_id)
    teilnahme = lies_teilnahme(verbindung, fall_id)
    positionen = lies_positionen(verbindung, fall_id)
    auftrag = fall["auftrag"] or {"themen": [], "kriterien": [], "regeln": [], "ziel": ""}
    themen = [t["id"] for t in auftrag["themen"]]
    teilnehmer = sorted(t["akteur"] for t in teilnahme if t["eingeladen"])

    chips: dict[tuple[int, str], dict[str, dict[str, str]]] = {}
    runden: dict[int, dict[str, Any]] = {}
    experte: dict[str, Any] | None = None
    ergebnis: dict[str, Any] | None = None
    for e in ereignisse:
        art, runde, akteur, daten = e["art"], e["runde"], e["akteur"], e["daten"]
        if art == "experte":
            experte = daten
        elif art == "ergebnis":
            ergebnis = daten
        if runde is None:
            continue
        r = runden.setdefault(
            runde, {"runde": runde, "phase": None, "zuege": [], "notiz": None, "pruefungen": []}
        )
        if art == "runde":
            r["phase"] = daten.get("phase")
        elif art == "belege" and akteur:
            chips[(runde, akteur)] = {c["beleg_id"]: c for c in daten["belege"]}
        elif art == "zug" and akteur:
            bekannt = chips.get((runde, akteur), {})
            zug = daten["zug"]
            r["zuege"].append(
                {
                    "akteur": akteur,
                    "gueltig": True,
                    "bezug_auf": zug["bezug_auf"],
                    "zahlen": zug["zahlen"],
                    "themen": [
                        {
                            "thema": t["thema"],
                            "haltung": t["haltung"],
                            "begruendung": t["begruendung"],
                            "bedingungen": t["bedingungen"],
                            "zugestaendnis": t["zugestaendnis"],
                            "belege": [
                                bekannt.get(
                                    b, {"beleg_id": b, "medium": "?", "monat": "?", "titel": "unbekannt"}
                                )
                                for b in t["beleg_ids"]
                            ],
                        }
                        for t in zug["themen"]
                    ],
                }
            )
        elif art == "ungueltige_ausgabe" and akteur and akteur != "moderator":
            r["zuege"].append({"akteur": akteur, "gueltig": False, "fehler": daten.get("fehler", [])})
        elif art == "moderator_notiz":
            r["notiz"] = daten
        if art in PRUEF_ARTEN:
            r["pruefungen"].append({"art": art, "akteur": akteur, "daten": daten})

    reihen = sorted(positionen)

    def wert(r: int, a: str, t: str) -> int | None:
        p = positionen[r].get(a, {}).get(t)
        return None if p is None else p.wert

    matrix_tab = {a: {t: [wert(r, a, t) for r in reihen] for t in themen} for a in teilnehmer}
    aenderungen: list[dict[str, Any]] = []
    for nr in reihen:
        aenderungen += [a.als_dict() for a in matrix.aenderungen(nr, positionen.get(nr - 1), positionen[nr])]
    ende = positionen[reihen[-1]] if reihen else {}
    klass = matrix.klassifikation(ende, teilnehmer, themen)
    pruefereignisse = [
        {"seq": e["seq"], "runde": e["runde"], "art": e["art"], "akteur": e["akteur"], "daten": e["daten"]}
        for e in ereignisse
        if e["art"] in PRUEF_ARTEN
    ]
    freigabe = lies_freigabe(verbindung, fall_id)
    return {
        "fall": {k: _iso(v) for k, v in fall.items()},
        "auftrag": auftrag,
        "teilnahme": teilnahme,
        "teilnehmer": teilnehmer,
        "runden": [runden[r] for r in sorted(runden)],
        "matrix": {"runden": reihen, "themen": themen, "werte": matrix_tab},
        "aenderungen": aenderungen,
        "klassifikation": {t: e.als_dict() for t, e in klass.items()},
        "pruefereignisse": pruefereignisse,
        "experte": experte,
        "ergebnis": ergebnis,
        "ereignisse": len(ereignisse),
        "freigabe": None if freigabe is None else {k: _iso(v) for k, v in freigabe.items()},
    }
