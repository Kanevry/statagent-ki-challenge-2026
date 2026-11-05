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
    _ZAHL_MONAT,
    MERKMALE,
    MONATSNAMEN,
    Merkmal,
    _auspraegung,
    _codes,
    _deutsch,
    _gliederung,
    _monat_anzeige,
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
NICHT_LESBAR = (
    "Diese Frage lässt sich gerade nicht aus der Datenbank beantworten. Was tun: die Frage enger fassen, "
    "zum Beispiel einen Monat statt eines ganzen Zeitraums, oder etwas später noch einmal fragen."
)
_STATUS_TEXT = {"vorlaeufig": "vorläufig", "endgueltig": "endgültig", "gesperrt": "gesperrt"}

_JAHR = re.compile(r"(?<!\d)((?:19|20)\d{2})(?!\d)")
_DEFINITION = re.compile(r"\b(was\s+(ist|sind|bedeutet|heißt|heisst)|definition|bedeutung|definiert)\b")
_FLUKTUATION = re.compile(r"fluktu|zugäng|abgäng|zugaeng|abgaeng|zu- und abg")
_ZEITREIHE = re.compile(r"zeitreihe|entwicklung|verlauf|monatsweise|je monat|pro monat|\bseit\b")
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
    text = frage.lower()
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
    if _ZEITREIHE.search(text) or len(set(monate_lesen(frage))) > 1:
        return "zeitreihe"
    if _GESCHLECHT.search(text):
        return "geschlecht"
    return "bestand"


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
        return f"Für {_monat_anzeige(monat)} gibt es keine Lieferung, also auch keine Zahl."
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


def _fortgeschrieben_hinweis(monat: str, anzahl: int, fluktuation: bool = False) -> str:
    text = (
        f"{_monat_anzeige(monat)} enthält {_deutsch(anzahl)} fortgeschriebene Beschäftigungsverhältnisse: "
        "Sie fehlten in der Lieferung und wurden aus der Lieferung des Vormonats übernommen."
    )
    if fluktuation:
        text += " Zu- und Abgänge dieses Teils fehlen, die Fluktuation ist dadurch zu niedrig."
    return text


def _filter(
    conn: Verbindung, frage: str, monat: str, ohne: tuple[Merkmal, ...]
) -> tuple[list[tuple[Merkmal, str]], list[str]]:
    """Ausprägungen der Frage (z. B. „Wien“, „ÖNACE F“) als Filter, außer für gegliederte Merkmale."""
    filter_: list[tuple[Merkmal, str]] = []
    etiketten: list[str] = []
    for merkmal in MERKMALE:
        if merkmal in ohne:
            continue
        codes = _codes(conn, merkmal, monat)
        code = _auspraegung(frage, merkmal, codes)
        if code is not None:
            filter_.append((merkmal, code))
            etiketten.append(codes[code])
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
) -> dict[str, Any]:
    definition, einheit = _definition_bestand(conn)
    filter_, etiketten = _filter(conn, frage, bis, gruppen)
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
            " ".join([text, *hinweise]),
            definition=definition,
            einheit=einheit,
            stand=staende,
            belege=belege or [_beleg(sql_text, [])],
            hinweise=hinweise,
        )
    gezaehlte_staende = [s for s in staende if str(s["monat"]) not in ohne_stichtag]
    text = _text_bestand(typ, gezaehlt, gruppen, labels, zusatz)
    return _antwort(
        typ,
        " ".join([text, *hinweise, _laien_bestand(), f"Die Zahlen sind {_status_text(gezaehlte_staende)}."]),
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
        return "Für diesen Monat liegen keine bereinigten Einzeldaten vor." + was_tun
    return NICHT_LESBAR


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
        f"Fluktuation im {_monat_anzeige(monat)}: Wie viele Beschäftigungsverhältnisse kamen dazu oder endeten, "
        f"gemessen am Bestand? Zwischen {vorher} und {stichtag} gab es {_deutsch(zu)} Zugänge und "
        f"{_deutsch(ab)} Abgänge bei {_deutsch(best)} Beschäftigungsverhältnissen am {stichtag}."
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
    mit_rate = [z for z in zeilen if z["fluktuation_prozent"] is not None]
    if mit_rate:
        hoechste = max(mit_rate, key=lambda z: float(z["fluktuation_prozent"]))
        code = str(hoechste["oenace"])
        teile.append(
            f"Am höchsten ist sie in Abschnitt {code} ({namen.get(code, code)}) mit "
            f"{_komma(float(hoechste['fluktuation_prozent']))} Prozent."
        )
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
    if jahr is not None:
        return _rueckfrage(
            f"Die Statistik zählt am letzten Tag jedes Monats, für {jahr} gibt es also zwölf Werte. "
            f"Meinen Sie {was} für einen Monat, zum Beispiel „{beispiel} Dezember {jahr}“, "
            f"oder alle Monate als Zeitreihe, „Zeitreihe 01/{jahr} bis 12/{jahr}“?"
        )
    return _rueckfrage(f"Für welchen Monat möchten Sie {was} wissen? Zum Beispiel „{beispiel} März 2025“.")


def antwort_frage(conn: Verbindung, frage: str, regelsatz: str = "v1") -> dict[str, Any]:
    """Beantwortet eine Datenanfrage ohne Sprachmodell; mehrdeutige Fragen bekommen eine Rückfrage.

    Wirft nie: Was sich nicht beantworten lässt (Zeitlimit, verweigerte Abfrage, zu viele Zahlen), kommt als
    Textantwort ohne Zahl und ohne interne Details zurück.
    """
    typ = fragetyp(frage)
    try:
        return _antwort_frage(conn, frage, regelsatz, typ)
    except _KeineZahl as grund:
        return _antwort(typ, str(grund), hinweise=[str(grund)])
    except (psycopg.Error, AbfrageVerweigert):
        return _antwort(typ, NICHT_LESBAR, hinweise=[NICHT_LESBAR])


def _antwort_frage(conn: Verbindung, frage: str, regelsatz: str, typ: str) -> dict[str, Any]:
    if typ == "definition":
        return _definition_antwort(conn, frage)
    monate = monate_lesen(frage)
    jahr = jahr_ohne_monat(frage)
    text = frage.lower()
    if typ == "zeitreihe":
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
            (GESCHLECHT,) if _GESCHLECHT.search(text) else tuple(g for g in (_gliederung(frage),) if g)
        )
        return _bestand_antwort(conn, frage, regelsatz, von, bis, gruppen, "zeitreihe")
    if len(monate) != 1:
        if len(monate) > 1:
            return _rueckfrage(
                "Die Frage nennt mehrere Monate. Meinen Sie eine Zeitreihe („Zeitreihe von … bis …“) "
                "oder einen einzelnen Monat?"
            )
        return _rueckfrage_monat(typ, jahr)
    monat = monate[0]
    if typ == "fluktuation":
        return _fluktuation_antwort(conn, monat, regelsatz)
    if typ == "geschlecht":
        gruppen = (GESCHLECHT, BUNDESLAND) if _BUNDESLAND.search(text) else (GESCHLECHT,)
        return _bestand_antwort(conn, frage, regelsatz, monat, monat, gruppen, "geschlecht")
    gliederung = _gliederung(frage)
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
