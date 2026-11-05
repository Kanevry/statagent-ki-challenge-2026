"""UC3-Adapter für UC4 „Gemeinsamer Einstieg“ (#106, Epic #95, Vertrag ``plattform.antwortform``, #96).

Die KI schreibt Code, das Programm rechnet: Der Adapter liest die Frage ohne Sprachmodell. Er erkennt einen
Monat (``2025-03``, ``03/2025`` oder „März 2025“), optional Ausprägungen (z. B. „Wien“, „Männer und Frauen“,
„ÖNACE F“) und optional eine Gliederung („nach Bundesland“). Die Ausprägungen kommen aus den
Klassifikationen ``stat.klass_*``, nicht aus dem Code.

Zahlen kommen nur aus ``stat.stat_beschaeftigte`` (Aggregate, keine Einzeldaten), Regelstand des
maßgeblichen Laufs (``ergebnis.letzter_lauf``). Je Abfrage ein Beleg mit dem ausgeführten SQL.
Erkennt der Adapter keinen Monat oder fehlt der Lauf, kommt eine gültige Antwort ohne Zahlen zurück.
Importiert ``plattform.llm`` nicht (R2).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from itertools import product
from typing import Any

from psycopg import sql

from statagent.berichte.sheet import STICHTAG, STICHTAG_VARIABLE, zaehl_zeitraum
from statagent.db import Verbindung, verbinden
from statagent.ergebnis import LaufStand, letzter_lauf, monatserster, monatsletzter
from statagent.regeln import eine, regeln_laden
from statagent.zeitraum import (
    DURCHSCHNITT_WORT,
    ISO,
    MONATSNAMEN,
    NAME_MONAT,
    ZAHL_MONAT,
    ZEITREIHE_WORT,
    Zeitraum,
    monat_anzeige,
    monate,
    tag_hinweis,
    unklar,
    zeitraum_anzeige,
    zeitraum_lesen,
)

QUELLE = "stat.stat_beschaeftigte"
UC = "uc3"

_STATUS_TEXT = {"vorlaeufig": "vorläufig", "endgueltig": "endgültig", "gesperrt": "gesperrt"}

# Monatsnamen und Monatsmuster liegen in statagent.zeitraum; die alten Namen bleiben für statagent.frage.
_ISO, _ZAHL_MONAT, _NAME_MONAT = ISO, ZAHL_MONAT, NAME_MONAT
_OENACE_CODE = re.compile(r"(?:önace|oenace)[\s-]*(?:abschnitt\s+)?([a-z])(?!\w)")
#: „ÖNACE F und G“, „ÖNACE-Abschnitte C, F oder G“: mehrere Abschnittsbuchstaben hintereinander (#125).
_OENACE_LISTE = re.compile(
    r"(?:önace|oenace)[\s-]*(?:abschnitte?\s+)?([a-z](?:\s*(?:,|und|oder|sowie)\s*[a-z])*)(?!\w)"
)
#: Fragt nach Personen statt Verhältnissen; der Text sagt dann, was gezählt wird (#95, Befund 95-3).
_FRAGT_NACH_PERSONEN = re.compile(
    r"(?<!\w)(?:beschäftigten?|beschaeftigten?|beschäftigter|personen|leute)(?!\w)"
)
#: Obergrenze für Zahlen aus mehreren genannten Ausprägungen (je Kombination eine Abfrage).
MAX_KOMBINATIONEN = 30


@dataclass(frozen=True)
class Merkmal:
    """Eine Gliederung von stat.stat_beschaeftigte: Spalte, Klassifikation und Wörter für „nach …“."""

    name: str
    spalte: str  # SQL-Ausdruck der Gliederung (s = stat.stat_beschaeftigte, q = klass_qualifikation)
    klass: str  # liefert code, bezeichnung; %(von)s/%(bis)s = Berichtsmonat
    gliederung: tuple[str, ...]
    join_qualifikation: bool = False


MERKMALE: tuple[Merkmal, ...] = (
    Merkmal(
        "Bundesland",
        "s.region",
        "SELECT code, bezeichnung FROM stat.klass_region WHERE ebene = 'bundesland'",
        ("bundesl",),
    ),
    Merkmal(
        "Geschlecht", "s.geschlecht", "SELECT code, bezeichnung FROM stat.klass_geschlecht", ("geschlecht",)
    ),
    Merkmal(
        "ÖNACE-Abschnitt",
        "s.oenace",
        "SELECT code, bezeichnung FROM stat.klass_oenace WHERE ebene = 1 AND gueltig_von <= %(bis)s"
        " AND (gueltig_bis IS NULL OR gueltig_bis >= %(von)s)",
        ("önace", "oenace", "branche", "wirtschaftsabschnitt", "abschnitt"),
    ),
    Merkmal(
        "Beschäftigungskategorie",
        "q.beschaeftigungskategorie",
        "SELECT code, bezeichnung FROM stat.klass_beschaeftigungskategorie",
        ("beschäftigungskategorie", "kategorie"),
        join_qualifikation=True,
    ),
)


def monat_lesen(frage: str) -> str | None:
    """Erster Monat der Frage als JJJJ-MM, sonst None."""
    text = frage.lower()
    for muster, jahr_gruppe, monat_gruppe in ((_ISO, 1, 2), (_ZAHL_MONAT, 2, 1)):
        treffer = muster.search(text)
        if treffer and 1 <= int(treffer.group(monat_gruppe)) <= 12:
            return f"{int(treffer.group(jahr_gruppe)):04d}-{int(treffer.group(monat_gruppe)):02d}"
    treffer = _NAME_MONAT.search(text)
    if treffer:
        return f"{int(treffer.group(2)):04d}-{MONATSNAMEN[treffer.group(1)]:02d}"
    return None


def _monat_anzeige(monat: str) -> str:
    return monat_anzeige(monat)


def _deutsch(wert: int) -> str:
    return f"{wert:,}".replace(",", ".")


def _codes(conn: Verbindung, merkmal: Merkmal, monat: str) -> dict[str, str]:
    zeilen = conn.execute(
        merkmal.klass.encode(), {"von": monatserster(monat), "bis": monatsletzter(monat)}
    ).fetchall()
    return {str(z["code"]): str(z["bezeichnung"]) for z in zeilen}


def _auspraegung(frage: str, merkmal: Merkmal, codes: dict[str, str]) -> str | None:
    """Code der in der Frage genannten Ausprägung; längste Bezeichnung gewinnt, Endungen -e/-n/-en erlaubt."""
    text = frage.lower()
    if merkmal.spalte == "s.oenace":
        treffer = _OENACE_CODE.search(text)
        if treffer and treffer.group(1).upper() in codes:
            return treffer.group(1).upper()
    for code, bezeichnung in sorted(codes.items(), key=lambda paar: len(paar[1]), reverse=True):
        if re.search(rf"(?<!\w){re.escape(bezeichnung.lower())}(?:e|n|en)?(?!\w)", text):
            return code
    return None


def _gliederung(frage: str) -> Merkmal | None:
    text = frage.lower()
    for merkmal in MERKMALE:
        if any(re.search(rf"(?<!\w)(?:nach|je|pro)\s+(?:\w+\s+)?{w}", text) for w in merkmal.gliederung):
            return merkmal
    return None


def _variable(conn: Verbindung) -> tuple[str, str | None]:
    zeile = conn.execute(
        "SELECT bezeichnung, einheit FROM stat.variable WHERE statistik = 'beschaeftigte' AND code = %s",
        (STICHTAG_VARIABLE,),
    ).fetchone()
    if zeile is None:
        return STICHTAG_VARIABLE, None
    return str(zeile["bezeichnung"]), str(zeile["einheit"])


def _auspraegungen(frage: str, merkmal: Merkmal, codes: dict[str, str]) -> list[str]:
    """Alle in der Frage genannten Ausprägungen eines Merkmals, in der Reihenfolge der Frage (#125).

    Wie ``_auspraegung``: längste Bezeichnung gewinnt, Endungen -e/-n/-en erlaubt; eine Textstelle zählt
    nur für eine Ausprägung. „ÖNACE F und G“ liefert beide Abschnitte.
    """
    text = frage.lower()
    treffer: list[tuple[int, int, str]] = []
    if merkmal.spalte == "s.oenace":
        for liste in _OENACE_LISTE.finditer(text):
            for buchstabe in re.finditer(r"(?<!\w)[a-z](?!\w)", liste.group(1)):
                if buchstabe.group(0).upper() in codes:
                    stelle = liste.start(1) + buchstabe.start()
                    treffer.append((stelle, stelle + 1, buchstabe.group(0).upper()))
    for code, bezeichnung in sorted(codes.items(), key=lambda paar: len(paar[1]), reverse=True):
        for fund in re.finditer(rf"(?<!\w){re.escape(bezeichnung.lower())}(?:e|n|en)?(?!\w)", text):
            if not any(fund.start() < bis and von < fund.end() for von, bis, _ in treffer):
                treffer.append((fund.start(), fund.end(), code))
    ergebnis: list[str] = []
    for _, _, code in sorted(treffer):
        if code not in ergebnis:
            ergebnis.append(code)
    return ergebnis


@dataclass(frozen=True)
class _Zaehlweise:
    """Wie der Regelsatz zählt, gelesen aus meta.regel (Regeln als Daten, nicht als Konstante)."""

    zeitraum_art: str  # Bestandsregel: v1 „Stichtag“, v2 „Monat“
    kategorie_direkt: bool  # Dimensionsregel: s.qualifikation enthält schon die Beschäftigungskategorie


def _zaehlweise(conn: Verbindung, regelsatz: str, monat: str) -> _Zaehlweise:
    dimension = eine(regeln_laden(conn, regelsatz, monat), "zaehl", "dimension")
    return _Zaehlweise(
        zeitraum_art=zaehl_zeitraum(conn, regelsatz, monat),
        kategorie_direkt=dimension.parameter.get("qualifikation") == "beschaeftigungskategorie",
    )


def _spalte(merkmal: Merkmal, weise: _Zaehlweise) -> str:
    # In v2 trägt s.qualifikation die Kategorie selbst; der Join über klass_qualifikation fände nichts.
    return "s.qualifikation" if merkmal.join_qualifikation and weise.kategorie_direkt else merkmal.spalte


def _abfrage(
    stand: LaufStand,
    monat: str,
    weise: _Zaehlweise,
    filter_: list[tuple[Merkmal, list[str]]],
    gruppe: Merkmal | None,
) -> sql.Composed:
    """SELECT über stat.stat_beschaeftigte; Parameter sind nur Regelsatz, Regelstand, Monat, Gliederung.

    Ein Code je Merkmal filtert mit ``=``, mehrere mit ``IN`` (Summe der genannten Ausprägungen).
    """
    bedingungen = [
        sql.SQL("s.regelsatz = {}").format(sql.Literal(stand.regelsatz)),
        sql.SQL("s.regelstand = {}").format(sql.Literal(stand.regelstand)),
        sql.SQL("s.zeitraum_art = {}").format(sql.Literal(weise.zeitraum_art)),
        sql.SQL("s.variable = {}").format(sql.Literal(STICHTAG_VARIABLE)),
        sql.SQL("s.zeitraum_bis BETWEEN {} AND {}").format(
            sql.Literal(monatserster(monat)), sql.Literal(monatsletzter(monat))
        ),
    ]
    for merkmal, codes in filter_:
        spalte = sql.SQL(_spalte(merkmal, weise))
        if len(codes) == 1:
            bedingungen.append(sql.SQL("{} = {}").format(spalte, sql.Literal(codes[0])))
        else:
            liste = sql.SQL(", ").join(sql.Literal(code) for code in codes)
            bedingungen.append(sql.SQL("{} IN ({})").format(spalte, liste))
    merkmale = [m for m, _ in filter_] + ([gruppe] if gruppe else [])
    join = any(_spalte(m, weise).startswith("q.") for m in merkmale)
    teile: list[sql.Composable] = [
        sql.SQL("SELECT {}COALESCE(sum(s.wert), 0)::bigint AS wert FROM stat.stat_beschaeftigte s").format(
            sql.SQL(f"{_spalte(gruppe, weise)} AS code, " if gruppe else "")
        )
    ]
    if join:
        teile.append(sql.SQL(" LEFT JOIN stat.klass_qualifikation q ON q.code = s.qualifikation"))
    teile.append(sql.SQL(" WHERE ") + sql.SQL(" AND ").join(bedingungen))
    if gruppe:
        teile.append(sql.SQL(" GROUP BY 1 ORDER BY 1"))
    return sql.Composed(teile)


def _leer(text: str) -> dict[str, Any]:
    return {"text": text, "belege": [], "zahlen": [], "uc": UC, "modell": None, "protokoll_id": None}


def _aufzaehlung(teile: list[str]) -> str:
    return teile[0] if len(teile) == 1 else f"{', '.join(teile[:-1])} und {teile[-1]}"


def _klammer(etiketten: list[str]) -> str:
    return f" ({', '.join(etiketten)})" if etiketten else ""


def _datenbereich(conn: Verbindung, regelsatz: str) -> tuple[str | None, str | None]:
    """Erster und jüngster Monat mit einem gerechneten Lauf (JJJJ-MM), sonst (None, None)."""
    zeile = conn.execute(
        "SELECT min(lieferung) AS von, max(lieferung) AS bis FROM meta.lauf"
        " WHERE regelsatz = %s AND status IN ('fertig', 'unveraendert')",
        (regelsatz,),
    ).fetchone()
    if zeile is None or zeile["von"] is None:
        return None, None
    return str(zeile["von"]), str(zeile["bis"])


def _vorschlag(letzter: str) -> str:
    return f"Meinen Sie „Beschäftigte im {_monat_anzeige(letzter)}“?"


def jahr_rueckfrage(beispiel: str, jahr: str, erster: str, letzter: str) -> str:
    """Rückfrage zu einer bloßen Jahreszahl (#74 AC2), gleich in ``uc3 frage`` und in UC4.

    Anzahl und Beispiele kommen aus den vorhandenen Monaten ``erster`` bis ``letzter``: 2026 hat keinen Dezember.
    """
    von, bis = max(f"{jahr}-01", erster), min(f"{jahr}-12", letzter)
    if von > bis:
        return (
            f"Für {jahr} gibt es keine Daten, nur für {zeitraum_anzeige(erster, letzter)}. "
            f"Meinen Sie „{beispiel} {_monat_anzeige(letzter)}“?"
        )
    anzahl = len(monate(von, bis))
    werte = "zwölf Werte" if anzahl == 12 else f"{anzahl} Werte, {zeitraum_anzeige(von, bis)}"
    return (
        f"Die Statistik zählt am letzten Tag jedes Monats, für {jahr} gibt es also {werte}. "
        f"Meinen Sie einen Monat („{beispiel} {_monat_anzeige(bis)}“), den Durchschnitt "
        f"(„{beispiel} Jahresdurchschnitt {jahr}“) oder alle Monate "
        f"(„Zeitreihe {von[5:7]}/{jahr} bis {bis[5:7]}/{jahr}“)?"
    )


def _fortgeschrieben_hinweis(monat: str, anzahl: int, fluktuation: bool = False) -> str:
    text = (
        f"Im {_monat_anzeige(monat)} sind {_deutsch(anzahl)} Beschäftigungsverhältnisse aus der Lieferung des "
        "Vormonats übernommen, weil sie in der Lieferung fehlten."
    )
    if fluktuation:
        text += " Zu- und Abgänge dieses Teils fehlen, die Fluktuation ist dadurch zu niedrig."
    return text


def _fortgeschrieben(conn: Verbindung, lauf_id: int) -> int:
    """Fortgeschriebene Beschäftigungsverhältnisse des Laufs (Regel E07)."""
    zeile = conn.execute("SELECT fortgeschrieben FROM meta.lauf WHERE id = %s", (lauf_id,)).fetchone()
    return int(str(zeile["fortgeschrieben"])) if zeile is not None else 0


def _mit_notizen(daten: dict[str, Any], notizen: list[str]) -> dict[str, Any]:
    if notizen:
        daten["text"] = " ".join([*notizen, daten["text"]])
    return daten


def antwort_daten(conn: Verbindung, frage: str, regelsatz: str = "v1") -> dict[str, Any]:
    """Felder einer ``UcAntwort`` als dict, ohne ``plattform.antwortform`` (testbar vor dem Merge von !30).

    Der Zeitraum kommt aus ``statagent.zeitraum`` (Monat, Bereich, Jahreszeit, Quartal, Halbjahr, Jahr,
    „letzten Monat“); ohne Zeitangabe gilt der jüngste Monat mit Daten. Ein Monat: jede genannte Ausprägung
    (auch mehrere eines Merkmals, #125) bekommt eine eigene Zahl mit eigenem Beleg und SQL; bei mehreren kommt
    die Summe als eigene Abfrage dazu. Mehrere Monate: je Monat eine Zahl und der Durchschnitt als eigene
    Abfrage. Der Text sagt in einem Satz, welche Monate gemeint sind, und was außerhalb der Daten liegt.
    """
    erster, letzter = _datenbereich(conn, regelsatz)
    grund = unklar(frage, letzter)
    if grund is not None:
        return _leer(grund)
    zeitraum = zeitraum_lesen(frage, letzter)
    notizen: list[str] = [h for h in (tag_hinweis(frage),) if h]
    if zeitraum is None:
        if letzter is None:
            return _leer("Es ist noch kein Monat gerechnet, darum gibt es noch keine Zahl.")
        zeitraum = Zeitraum(letzter, letzter, "aktuell", "")
        notizen.append(f"Ohne Zeitangabe zeigen wir den jüngsten Monat: {_monat_anzeige(letzter)}.")
    else:
        satz = zeitraum.erklaerung()
        # Wer eine Zeitreihe zu einem Jahr fragt, meint die Monate; der Satz zum Durchschnitt passt dann nicht.
        if satz and not (zeitraum.art == "jahr" and ZEITREIHE_WORT.search(frage.lower())):
            notizen.append(satz)
    gefragte = zeitraum.monatsliste
    liste = gefragte
    if erster is not None and letzter is not None:
        vorhanden = zeitraum_anzeige(erster, letzter)
        liste = [m for m in gefragte if erster <= m <= letzter]
        aufgezaehlt = zeitraum.art == "liste"
        if not liste:
            gefragt = (
                _aufzaehlung([_monat_anzeige(m) for m in gefragte])
                if aufgezaehlt
                else zeitraum_anzeige(zeitraum.von, zeitraum.bis)
            )
            return _leer(f"Für {gefragt} gibt es keine Daten, nur für {vorhanden}. {_vorschlag(letzter)}")
        # Eine bloße Jahreszahl meint zwölf Werte: nachfragen wie in uc3 frage (#74 AC2).
        if (
            zeitraum.art == "jahr"
            and not DURCHSCHNITT_WORT.search(frage)
            and not ZEITREIHE_WORT.search(frage.lower())
        ):
            return _leer(jahr_rueckfrage("Beschäftigte", zeitraum.von[:4], erster, letzter))
        if len(liste) < len(gefragte):
            zaehlt = (
                _aufzaehlung([_monat_anzeige(m) for m in liste])
                if aufgezaehlt
                else zeitraum_anzeige(liste[0], liste[-1])
            )
            notizen.append(f"Daten gibt es nur für {vorhanden}, darum zählt hier {zaehlt}.")
    if len(liste) == 1:
        return _mit_notizen(_monat_antwort(conn, frage, liste[0], regelsatz), notizen)
    # Aufgezählte Monate („Jänner und Juli 2025“) bekommen nur mit Durchschnittswort einen Durchschnitt.
    mittel = zeitraum.art != "liste" or bool(DURCHSCHNITT_WORT.search(frage))
    return _mit_notizen(_zeitraum_antwort(conn, frage, liste, regelsatz, mittel), notizen)


def _monat_antwort(conn: Verbindung, frage: str, monat: str, regelsatz: str) -> dict[str, Any]:
    """Zahlen für genau einen Monat (Ausprägungen, Kombinationen, Gliederung wie bisher)."""
    stand = letzter_lauf(conn, monat, regelsatz)
    if stand is None:
        return _leer(
            f"Für {_monat_anzeige(monat)} gibt es noch keinen gerechneten Lauf (Regelsatz {regelsatz})."
        )
    weise = _zaehlweise(conn, regelsatz, monat)

    filter_: list[tuple[Merkmal, list[str]]] = []
    namen: dict[
        tuple[str, str], str
    ] = {}  # (Merkmal, Code) → Bezeichnung; „U“ gibt es bei Geschlecht und ÖNACE
    gruppe = _gliederung(frage)
    gruppen_codes: dict[str, str] = {}
    for merkmal in MERKMALE:
        codes = _codes(conn, merkmal, monat)
        if merkmal is gruppe:
            gruppen_codes = codes
            continue
        genannt = _auspraegungen(frage, merkmal, codes)
        if genannt:
            filter_.append((merkmal, genannt))
            namen.update({(merkmal.name, code): codes[code] for code in genannt})

    feste = [namen[(m.name, codes[0])] for m, codes in filter_ if len(codes) == 1]
    mehrfach = [(m, codes) for m, codes in filter_ if len(codes) > 1]
    kombinationen = list(product(*(codes for _, codes in mehrfach)))
    if len(kombinationen) > MAX_KOMBINATIONEN:
        return _leer(
            f"Das sind {len(kombinationen)} Zahlen auf einmal. "
            "Bitte fragen Sie nach weniger Ausprägungen oder nach einer Aufteilung, zum Beispiel nach Bundesland."
        )

    bezeichnung, einheit = _variable(conn)
    status = _STATUS_TEXT.get(stand.ergebnis_status, stand.ergebnis_status)
    belege: list[dict[str, Any]] = []
    zahlen: list[dict[str, Any]] = []

    def abfragen(filter_jetzt: list[tuple[Merkmal, list[str]]], mit_gruppe: bool) -> list[dict[str, Any]]:
        abfrage = _abfrage(stand, monat, weise, filter_jetzt, gruppe if mit_gruppe else None)
        belege.append(
            {
                "uc": "uc3",
                "quelle": QUELLE,
                "lieferung": stand.lieferung,
                "monat": monat,
                "sql": abfrage.as_string(conn),
                "ref": f"meta.lauf/{stand.lauf_id} regelstand {stand.regelstand} {stand.ergebnis_status}",
                "regelstand": stand.regelstand,
                "lauf": stand.ergebnis_hash,
                "stand": stand.ergebnis_status,
            }
        )
        return [dict(z) for z in conn.execute(abfrage).fetchall()]

    teilwerte: list[tuple[str, int]] = []  # (Etikett der Kombination, Wert)
    for kombination in kombinationen:
        wahl = dict(zip((m.name for m, _ in mehrfach), kombination, strict=True))
        filter_jetzt = [(m, [wahl[m.name]] if m.name in wahl else codes) for m, codes in filter_]
        etikett = ", ".join(namen[(name, code)] for name, code in wahl.items())
        zeilen = abfragen(filter_jetzt, mit_gruppe=True)
        name = bezeichnung + _klammer(feste + ([etikett] if etikett else []))
        if gruppe is None:
            wert = int(str(zeilen[0]["wert"]))
            zahlen.append({"bezeichnung": name, "wert": wert, "einheit": einheit, "beleg": len(belege) - 1})
        else:
            wert = sum(int(str(z["wert"])) for z in zeilen)
            zahlen.extend(
                {
                    "bezeichnung": f"{name}, {gruppen_codes.get(str(z['code']), str(z['code']))}",
                    "wert": int(str(z["wert"])),
                    "einheit": einheit,
                    "beleg": len(belege) - 1,
                }
                for z in zeilen
            )
        teilwerte.append((etikett, wert))

    if weise.zeitraum_art == STICHTAG:
        stichtag = monatsletzter(monat).strftime("%d.%m.%Y")
        anfang = f"Am {stichtag}, dem letzten Tag im {_monat_anzeige(monat)}, gab es"
    else:
        anfang = f"Im {_monat_anzeige(monat)} gab es"
    saetze: list[str] = []
    if len(kombinationen) == 1:
        wert = teilwerte[0][1]
        satz = f"{anfang} {_deutsch(wert)} {bezeichnung}{_klammer(feste)}"
        if gruppe is not None:
            satz += f", aufgeteilt nach {gruppe.name} in {len(zahlen)} Zahlen"
        saetze.append(satz + ".")
    else:
        einzeln = [f"{etikett} {_deutsch(wert)}" for etikett, wert in teilwerte]
        satz = f"{anfang} diese {bezeichnung}{_klammer(feste)}: {', '.join(einzeln)}"
        if gruppe is not None:
            satz += f", jeweils aufgeteilt nach {gruppe.name}"
        saetze.append(satz + ".")
        # Summe als eigene Abfrage mit IN (eigener Beleg); sie stimmt mit der Summe der Teile überein.
        summe = int(str(abfragen(filter_, mit_gruppe=False)[0]["wert"]))
        zusammen = _aufzaehlung([namen[(m.name, c)] for m, codes in mehrfach for c in codes])
        zahlen.append(
            {
                "bezeichnung": f"{bezeichnung}{_klammer([*feste, f'{zusammen} zusammen'])}",
                "wert": summe,
                "einheit": einheit,
                "beleg": len(belege) - 1,
            }
        )
        saetze.append(f"Zusammen sind das {_deutsch(summe)}.")
    saetze.append(f"Die Zahl ist {status}." if len(zahlen) == 1 else f"Die Zahlen sind {status}.")
    anzahl_fort = _fortgeschrieben(conn, stand.lauf_id)
    if anzahl_fort:
        saetze.append(_fortgeschrieben_hinweis(monat, anzahl_fort))
    if _FRAGT_NACH_PERSONEN.search(frage.lower()):
        saetze.append("Gezählt werden Beschäftigungsverhältnisse, eine Person kann mehrere haben.")
    if weise.zeitraum_art != STICHTAG:
        saetze.append("Ein Verhältnis zählt, wenn es irgendwann im Monat bestand.")
    if weise.kategorie_direkt:
        saetze.append(
            "Arbeiter, Angestellte und Beamte gelten dabei ohne Trennung nach Dienstvertrag (DV) "
            "und freiem Dienstvertrag (FD)."
        )
    return {
        "text": " ".join(saetze),
        "belege": belege,
        "zahlen": zahlen,
        "uc": UC,
        "modell": None,
        "protokoll_id": None,
    }


def _halb_auf(summe: int, anzahl: int) -> int:
    """Ganzzahliger Durchschnitt, kaufmännisch gerundet (x,5 nach oben); nur für nicht negative Summen."""
    return (2 * summe + anzahl) // (2 * anzahl)


def _zeitraum_antwort(
    conn: Verbindung, frage: str, monatsliste: list[str], regelsatz: str, mittel_zeigen: bool = True
) -> dict[str, Any]:
    """Je Monat eine Zahl (alle genannten Ausprägungen zusammen) und der Durchschnitt der Monate.

    Die Ausprägungen werden je Monat aus der Klassifikation des Monats gelesen. Wechselt die ÖNACE-Einteilung im
    Zeitraum und nennt die Frage eine Branche, kommt eine Absage statt einer Reihe über den Wechsel. Eine
    Aufteilung („nach Bundesland“) gibt es nur für einen Monat; das sagt der Text.
    """
    bezeichnung, einheit = _variable(conn)
    gruppe = _gliederung(frage)
    belege: list[dict[str, Any]] = []
    zahlen: list[dict[str, Any]] = []
    werte: list[tuple[str, int]] = []
    ohne_lauf: list[str] = []
    staende: dict[str, str] = {}  # Monat → Stand des Laufs
    fortgeschrieben: list[str] = []
    etiketten: list[str] | None = None
    oenace_codes: dict[str, str] | None = None
    weise: _Zaehlweise | None = None
    teilabfragen: list[sql.Composable] = []
    von, bis = monatsliste[0], monatsliste[-1]
    for monat in monatsliste:
        stand = letzter_lauf(conn, monat, regelsatz)
        if stand is None:
            ohne_lauf.append(monat)
            continue
        weise = _zaehlweise(conn, regelsatz, monat)
        filter_: list[tuple[Merkmal, list[str]]] = []
        namen: list[str] = []
        for merkmal in MERKMALE:
            if merkmal is gruppe:
                continue
            codes = _codes(conn, merkmal, monat)
            genannt = _auspraegungen(frage, merkmal, codes)
            if not genannt:
                continue
            if merkmal.spalte == "s.oenace":
                if oenace_codes is not None and oenace_codes != codes:
                    return _leer(
                        "Die Wirtschaftsbereiche (ÖNACE) wurden im Zeitraum neu eingeteilt. Eine Reihe über den "
                        "Wechsel wäre irreführend. Bitte die Zeit vor und ab Jänner 2025 getrennt fragen."
                    )
                oenace_codes = codes
            filter_.append((merkmal, genannt))
            woerter = [codes[c] for c in genannt]
            namen.append(woerter[0] if len(woerter) == 1 else f"{_aufzaehlung(woerter)} zusammen")
        if etiketten is None:
            etiketten = namen
        elif etiketten != namen:
            return _leer(
                "Die genannten Ausprägungen gibt es nicht in allen Monaten des Zeitraums. "
                "Bitte einen kürzeren Zeitraum fragen."
            )
        abfrage = _abfrage(stand, monat, weise, filter_, None)
        teilabfragen.append(abfrage)
        staende[monat] = stand.ergebnis_status
        anzahl_fort = _fortgeschrieben(conn, stand.lauf_id)
        if anzahl_fort:
            fortgeschrieben.append(_fortgeschrieben_hinweis(monat, anzahl_fort))
        belege.append(
            {
                "uc": "uc3",
                "quelle": QUELLE,
                "lieferung": stand.lieferung,
                "monat": monat,
                "sql": abfrage.as_string(conn),
                "ref": f"meta.lauf/{stand.lauf_id} regelstand {stand.regelstand} {stand.ergebnis_status}",
                "regelstand": stand.regelstand,
                "lauf": stand.ergebnis_hash,
                "stand": stand.ergebnis_status,
            }
        )
        zeile = conn.execute(abfrage).fetchone()
        wert = int(str(zeile["wert"])) if zeile is not None else 0
        werte.append((monat, wert))
    if not werte:
        return _leer(f"Für {zeitraum_anzeige(von, bis)} gibt es noch keinen gerechneten Lauf.")
    klammer = _klammer(etiketten or [])
    for i, (monat, wert) in enumerate(werte):
        zahlen.append(
            {
                "bezeichnung": f"{bezeichnung}{klammer}, {_monat_anzeige(monat)}",
                "wert": wert,
                "einheit": einheit,
                "beleg": i,
            }
        )
    stichtag = weise is not None and weise.zeitraum_art == STICHTAG
    wann = "jeweils am letzten Tag des Monats" if stichtag else "je Monat"
    einzeln = ", ".join(f"{_monat_anzeige(m)} {_deutsch(w)}" for m, w in werte)
    saetze = [f"{bezeichnung}{klammer} {wann}: {einzeln}."]
    if mittel_zeigen:
        # Durchschnitt als eigene Abfrage über dieselben Monatsabfragen (eigener Beleg), auf ganze Zahlen gerundet.
        mittel_sql = sql.SQL("SELECT round(avg(t.wert))::bigint AS wert FROM ({}) t").format(
            sql.SQL(" UNION ALL ").join(sql.SQL("({})").format(q) for q in teilabfragen)
        )
        zeile = conn.execute(mittel_sql).fetchone()
        mittel = (
            int(str(zeile["wert"])) if zeile is not None else _halb_auf(sum(w for _, w in werte), len(werte))
        )
        belege.append(
            {
                "uc": "uc3",
                "quelle": QUELLE,
                "lieferung": None,
                "monat": None,
                "sql": mittel_sql.as_string(conn),
                "ref": "Durchschnitt der Monatsabfragen oben",
                "regelstand": None,
                "lauf": None,
                "stand": "endgueltig" if set(staende.values()) == {"endgueltig"} else "vorlaeufig",
            }
        )
        gezaehlte = [m for m, _ in werte]
        durchgehend = gezaehlte == monate(gezaehlte[0], gezaehlte[-1])
        gezaehlt = (
            zeitraum_anzeige(gezaehlte[0], gezaehlte[-1])
            if durchgehend
            else _aufzaehlung([_monat_anzeige(m) for m in gezaehlte])
        )
        zahlen.append(
            {
                "bezeichnung": f"{bezeichnung}{klammer}, Durchschnitt {gezaehlt}",
                "wert": mittel,
                "einheit": einheit,
                "beleg": len(belege) - 1,
            }
        )
        saetze.append(f"Im Durchschnitt waren es {_deutsch(mittel)}.")
    if ohne_lauf:
        saetze.append(
            f"Für {', '.join(_monat_anzeige(m) for m in ohne_lauf)} gibt es noch keinen gerechneten Lauf"
            + ("; der Durchschnitt nimmt nur die Monate mit Zahlen." if mittel_zeigen else ".")
        )
    if gruppe is not None:
        saetze.append(
            f"Eine Aufteilung nach {gruppe.name} gibt es je Monat, zum Beispiel "
            f"„Beschäftigte nach {gruppe.name} im {_monat_anzeige(werte[-1][0])}“."
        )
    status = sorted({_STATUS_TEXT.get(s, s) for s in staende.values()})
    offen = [_monat_anzeige(m) for m, s in staende.items() if s != "endgueltig"]
    saetze.append(
        f"Die Zahlen sind {status[0]}."
        if len(status) == 1
        else f"Die Zahlen sind teils {', teils '.join(status)} (vorläufig: {', '.join(offen)})."
    )
    saetze.extend(fortgeschrieben)
    if _FRAGT_NACH_PERSONEN.search(frage.lower()):
        saetze.append("Gezählt werden Beschäftigungsverhältnisse, eine Person kann mehrere haben.")
    if not stichtag:
        saetze.append("Ein Verhältnis zählt, wenn es irgendwann im Monat bestand.")
    return {
        "text": " ".join(saetze),
        "belege": belege,
        "zahlen": zahlen,
        "uc": UC,
        "modell": None,
        "protokoll_id": None,
    }


def antwort(frage: str, kontext: list[Any]) -> Any:
    """Adapter für ``plattform.router`` (Entry-Point ``kic.uc_antwort``/``uc3``): Frage → ``UcAntwort``.

    ``kontext`` bleibt ungenutzt, UC3 ist der erste Schritt der Kette. Die Datenbank kommt aus
    ``UC3_DATABASE_URL`` (``statagent.db.verbinden``).
    """
    try:
        from plattform.antwortform import UcAntwort
    except ImportError as fehler:
        raise RuntimeError(
            "plattform.antwortform fehlt (Vertrag UcAntwort, #96, MR !30); "
            "ohne ihn liefert nur statagent.uc4.uc4_antwort ein dict."
        ) from fehler
    with verbinden() as conn:
        daten = uc4_antwort(conn, frage)
    return UcAntwort.model_validate(daten)


def uc4_antwort(conn: Verbindung, frage: str, regelsatz: str = "v1") -> dict[str, Any]:
    """Felder der ``UcAntwort`` für /uc4: derselbe Weg wie /uc3/fragen, damit beide dasselbe sagen (#176).

    Was dieser Weg nicht versteht, bekommt eine Absage oder Rückfrage, keine Zahl zu einer anderen Frage. Nur mehrere
    Werte eines Merkmals („Wien und Tirol“) zeigt UC4 je Wert (#125); das rechnet ``antwort_daten``, und nur, wenn der
    Adapter alle übrigen Einschränkungen der Frage genauso liest.
    """
    from statagent import frage as weg  # hier, weil statagent.frage aus diesem Modul importiert

    daten = weg.antwort_frage(conn, frage, regelsatz)
    if (
        daten["typ"] in ("bestand", "geschlecht")
        and daten["text"].startswith(weg.MEHRERE_WERTE)
        and "anteil" not in frage.lower()
        and _adapter_liest_gleich(conn, frage, regelsatz)
    ):
        return antwort_daten(conn, frage, regelsatz)
    if daten["typ"] == "fluktuation" and daten["zahlen"]:
        return _fluktuation_kurz(daten)
    return {
        **weg.als_ucantwort(daten),
        "text": _text_fuer_kette(weg.als_webantwort(daten)["text"], daten["zahlen"]),
    }


#: Teile des „Verstanden“-Satzes, die nichts eingrenzen.
_ALLE = re.compile(r",\s+(?:Bundesland|Geschlecht|Branche|Beschäftigungskategorie): alle")
_MONATSSATZ = re.compile(r"Am \d{1,2}\. (\S+) (\d{4}) gab es ([\d.]+ [^.]*\.)\s*")


def _text_fuer_kette(text: str, zahlen: list[dict[str, Any]]) -> str:
    """Der Text für die Stationen der Kette: Bei genau einer Zahl ist der erste Satz die Antwort, danach kommt
    „Verstanden …“. Der erste Satz wird auch als Kern der Station verwendet, darum ohne Punkt nach dem Tag.
    """
    text = _ALLE.sub("", text)
    satz = _MONATSSATZ.search(text)
    if len(zahlen) != 1 or not text.startswith("Verstanden:") or satz is None:
        return text
    monat = f"{satz.group(2)}-{MONATSNAMEN[satz.group(1).lower()]:02d}"
    tag = monatsletzter(monat).strftime("%d.%m.%Y")
    antwort = f"Am {tag}, dem letzten Tag im {_monat_anzeige(monat)}, gab es {satz.group(3)}"
    return f"{antwort} {text[: satz.start()].strip()} {text[satz.end() :].strip()}".strip()


def _fluktuation_kurz(daten: dict[str, Any]) -> dict[str, Any]:
    """Fluktuation in der Kette: eine Zahl (alle Wirtschaftsbereiche oder die gefragte Branche), die Tabelle je Branche
    bleibt auf /uc3/fragen. Gibt es diese eine Zahl nicht, kommt nur der Verweis.
    """
    text = str(daten["text"])
    monat = re.search(r"Fluktuation im (\S+ \d{4})", text)
    wann = monat.group(1) if monat else ""
    branche = re.search(r"gefragt war die Branche (\S)", text)
    anfang = f"Fluktuation, ÖNACE {branche.group(1)} " if branche else "Fluktuation, alle Wirtschaftsbereiche"
    treffer = [z for z in daten["zahlen"] if str(z["bezeichnung"]).startswith(anfang)]
    verweis = "Die Zahlen je Branche stehen unter Fragen an die Daten."
    if not treffer:
        return _leer(f"Für {wann} gibt es keine Gesamtzahl zur Fluktuation. {verweis}")
    zahl = treffer[0]
    wert = f"{zahl['wert']:.2f}".replace(".", ",")
    if branche:
        name = str(zahl["bezeichnung"]).removeprefix(anfang)
        satz = f"In der Branche {name} lag die Fluktuation im {wann} bei {wert} Prozent."
    else:
        satz = f"Über alle Wirtschaftsbereiche zusammen lag die Fluktuation im {wann} bei {wert} Prozent."
    saetze = [satz, verweis]
    saetze += [h for h in daten["hinweise"] if "zu niedrig" in h]
    stand = re.search(r"Die Zahlen sind ([^.]*)\.", text)
    if stand:
        saetze.append(f"Die Zahl ist {stand.group(1)}.")
    return {
        **_leer(" ".join(saetze)),
        "belege": [daten["belege"][zahl["beleg"]]],
        "zahlen": [{**zahl, "beleg": 0}],
    }


def _adapter_liest_gleich(conn: Verbindung, frage: str, regelsatz: str) -> bool:
    """Liest der Adapter jede Ausprägung, die /uc3/fragen in der Frage findet, und bleibt kein Wort unbekannt?"""
    from statagent import frage as weg

    if weg._ZEITREIHE.search(frage.lower()):
        return False  # „Wien gegenüber Tirol entwickelt“: der Adapter zeigt einen Stand, keine Entwicklung
    gelesen = weg.normalisieren(frage)[0]
    genannt = weg.monate_lesen(gelesen)
    monat = genannt[-1] if genannt else weg._letzter_monat(conn, regelsatz)
    if monat is None or weg._FREIER_DV.search(gelesen.lower()):
        return False
    mehrfach: list[Merkmal] = []
    try:
        for merkmal in MERKMALE:
            codes = _codes(conn, merkmal, monat)
            werte = weg._werte(gelesen, merkmal, codes)[0]
            if not set(werte) <= set(_auspraegungen(gelesen, merkmal, codes)):
                return False
            if len(werte) > 1:
                mehrfach.append(merkmal)
        weg._filter(conn, gelesen, monat, tuple(mehrfach))
    except weg._KeineZahl:
        return False
    return True
