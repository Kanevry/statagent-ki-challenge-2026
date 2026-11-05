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
from typing import Any

import psycopg
from psycopg import sql

from statagent.agenten.werkzeuge import sql_lesen
from statagent.berichte.sheet import STICHTAG, STICHTAG_VARIABLE
from statagent.db import Verbindung
from statagent.ergebnis import letzter_lauf, monat_verschieben, monatserster, monatsletzter
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
    "des maßgeblichen Laufs. Zugang: ein Verhältnis besteht am Stichtag, aber nicht am Stichtag des Vormonats; "
    "Abgang: umgekehrt. Beide Stichtage aus der Lieferung des Berichtsmonats (stat.bewegung_oenace). Zugänge "
    "zählen beim Abschnitt am Stichtag, Abgänge beim Abschnitt am Vormonats-Stichtag. Bestand 0 ergibt keine Rate."
)
OENACE_ERKLAERUNG = (
    "ÖNACE ist die österreichische Einteilung der Wirtschaftsbereiche in Abschnitte (Buchstaben)."
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
    werte = sorted({_STATUS_TEXT.get(str(s["status"]), str(s["status"])) for s in staende})
    return " und ".join(werte)


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
    filter_, etiketten = _filter(conn, frage, bis, gruppen)
    sql_text = bestand_sql(conn, regelsatz, von, bis, filter_, gruppen)
    ergebnis = sql_lesen(conn, sql_text)
    zeilen: list[dict[str, Any]] = ergebnis["zeilen"]
    definition, einheit = _definition_bestand(conn)
    if not zeilen:
        zeitraum = _monat_anzeige(von) if von == bis else f"{_monat_anzeige(von)} bis {_monat_anzeige(bis)}"
        return _antwort(
            typ,
            f"Für {zeitraum} gibt es noch keinen gerechneten Monat (Regelsatz {regelsatz}). "
            "Erst ein Lauf für den Monat liefert Zahlen.",
            definition=definition,
            einheit=einheit,
            belege=[_beleg(sql_text, [])],
        )
    staende = _staende(zeilen)
    hash_ = None
    if len(staende) == 1:
        stand = letzter_lauf(conn, str(staende[0]["monat"]), regelsatz)
        hash_ = stand.ergebnis_hash if stand and stand.lauf_id == staende[0]["lauf"] else None
    beleg = _beleg(sql_text, staende, hash_)
    labels = [_codes(conn, g, bis) for g in gruppen]
    zusatz = f" ({', '.join(etiketten)})" if etiketten else ""
    zahlen: list[dict[str, Any]] = []
    for z in zeilen:
        teile = [str(z["monat"])] if von != bis else []
        if gruppen and z["g0"] is None:
            continue  # Monat mit Lauf, aber ohne Zeile für die Gliederung
        for i, g in enumerate(gruppen):
            code = str(z[f"g{i}"])
            teile.append(
                labels[i].get(code, code) if g is not OENACE else f"{code} {labels[i].get(code, '')}".strip()
            )
        zahlen.append(
            {
                "bezeichnung": "Beschäftigungsverhältnisse"
                + zusatz
                + (f", {', '.join(teile)}" if teile else ""),
                "wert": int(z["wert"]),
                "einheit": einheit,
                "beleg": 0,
            }
        )
    hinweise: list[str] = []
    fehlend = _fehlende_monate(von, bis, {str(s["monat"]) for s in staende})
    if fehlend:
        hinweise.append(
            f"Für {len(fehlend)} Monate im Zeitraum gibt es noch keinen gerechneten Lauf: "
            + ", ".join(_monat_anzeige(m) for m in fehlend[:6])
            + (" und weitere" if len(fehlend) > 6 else "")
            + "."
        )
    text = _text_bestand(typ, zeilen, staende, gruppen, labels, zusatz)
    return _antwort(
        typ,
        " ".join([text, *hinweise, _laien_bestand(), f"Die Zahlen sind {_status_text(staende)}."]),
        definition=definition,
        einheit=einheit,
        stand=staende,
        belege=[beleg],
        zahlen=zahlen,
        hinweise=hinweise,
    )


def _fehlende_monate(von: str, bis: str, vorhanden: set[str]) -> list[str]:
    fehlend: list[str] = []
    monat = von
    while monat <= bis and len(fehlend) < 600:
        if monat not in vorhanden:
            fehlend.append(monat)
        monat = monat_verschieben(monat, 1)
    return fehlend


def _text_bestand(
    typ: str,
    zeilen: list[dict[str, Any]],
    staende: list[dict[str, Any]],
    gruppen: tuple[Merkmal, ...],
    labels: list[dict[str, str]],
    zusatz: str,
) -> str:
    je_monat: dict[str, int] = {}
    for z in zeilen:
        je_monat[str(z["monat"])] = je_monat.get(str(z["monat"]), 0) + int(z["wert"])
    monate = sorted(je_monat)
    if typ == "zeitreihe":
        erster, letzter = monate[0], monate[-1]
        text = (
            f"Beschäftigungsverhältnisse{zusatz} am Monatsende, {_monat_anzeige(erster)} bis "
            f"{_monat_anzeige(letzter)} ({len(monate)} Monate): von {_deutsch(je_monat[erster])} "
            f"auf {_deutsch(je_monat[letzter])}."
        )
        if gruppen:
            text += f" Aufgeteilt nach {', '.join(g.name for g in gruppen)}, eine Zahl je Monat und Gruppe."
        return text
    monat = monate[0]
    stichtag = monatsletzter(monat).strftime("%d.%m.%Y")
    text = f"Am {stichtag} ({_monat_anzeige(monat)}) gab es {_deutsch(je_monat[monat])} Beschäftigungsverhältnisse{zusatz}."
    if gruppen and gruppen[0] is GESCHLECHT:
        je_geschlecht: dict[str, int] = {}
        for z in zeilen:
            if z["g0"] is not None:
                je_geschlecht[str(z["g0"])] = je_geschlecht.get(str(z["g0"]), 0) + int(z["wert"])
        teile = [f"{labels[0].get(c, c)}: {_deutsch(n)}" for c, n in sorted(je_geschlecht.items())]
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


def _fluktuation_antwort(conn: Verbindung, monat: str, regelsatz: str) -> dict[str, Any]:
    stand = letzter_lauf(conn, monat, regelsatz)
    if stand is None:
        return _antwort(
            "fluktuation",
            f"Für {_monat_anzeige(monat)} gibt es noch keinen gerechneten Monat (Regelsatz {regelsatz}).",
            definition=FLUKTUATION_DEFINITION,
            einheit="Prozent",
        )
    staende = [
        {
            "monat": monat,
            "lauf": stand.lauf_id,
            "regelstand": stand.regelstand,
            "status": stand.ergebnis_status,
        }
    ]
    sql_text = _fluktuation_sql(conn, regelsatz, stand.regelstand, monat)
    beleg = _beleg(sql_text, staende, stand.ergebnis_hash)
    try:
        zeilen: list[dict[str, Any]] = sql_lesen(conn, sql_text)["zeilen"]
    except psycopg.errors.RaiseException as fehler:
        grund = fehler.diag.message_primary or str(fehler)
        return _antwort(
            "fluktuation",
            f"Für {_monat_anzeige(monat)} lässt sich die Fluktuation nicht berechnen: {grund}. "
            "Ein neuer Lauf für den Monat behebt das.",
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
    stichtag = monatsletzter(monat).strftime("%d.%m.%Y")
    vorher = monatsletzter(monat_verschieben(monat, -1)).strftime("%d.%m.%Y")
    teile = [
        f"Fluktuation im {_monat_anzeige(monat)}: Wie viele Beschäftigungsverhältnisse kamen dazu oder endeten, "
        f"gemessen am Bestand? Zwischen {vorher} und {stichtag} gab es {_deutsch(zu)} Zugänge und "
        f"{_deutsch(ab)} Abgänge bei {_deutsch(best)} Verhältnissen am {stichtag}."
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
        hinweis = (
            f"Für {', '.join(ohne_bestand)} gibt es am {stichtag} keine Beschäftigten; "
            "dort ist keine Rate berechenbar, es stehen nur Zu- und Abgänge da."
        )
        hinweise.append(hinweis)
        teile.append(hinweis)
    teile.append(
        "Formel: (Zugänge + Abgänge) geteilt durch 2, geteilt durch den Bestand am Monatsende. "
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
        zeilen: list[dict[str, Any]] = sql_lesen(conn, sql_text)["zeilen"]
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
    """Beantwortet eine Datenanfrage ohne Sprachmodell; mehrdeutige Fragen bekommen eine Rückfrage."""
    typ = fragetyp(frage)
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
            return _antwort("zeitreihe", f"Es gibt noch keinen gerechneten Monat (Regelsatz {regelsatz}).")
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
