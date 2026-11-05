"""UC3-Adapter für UC4 „Gemeinsamer Einstieg“ (#106, Epic #95, Vertrag ``plattform.antwortform``, #96).

Die KI schreibt Code, das Programm rechnet: Der Adapter liest die Frage ohne Sprachmodell. Er erkennt einen
Monat (``2025-03``, ``03/2025`` oder „März 2025“), optional Ausprägungen (z. B. „Wien“, „Frauen“,
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
from typing import Any

from psycopg import sql

from statagent.berichte.sheet import STICHTAG, STICHTAG_VARIABLE
from statagent.db import Verbindung, verbinden
from statagent.ergebnis import LaufStand, letzter_lauf, monatserster, monatsletzter

QUELLE = "stat.stat_beschaeftigte"
UC = "uc3"

#: Monatsnamen der Alltagssprache (österreichisch und bundesdeutsch) → Monatsnummer.
MONATSNAMEN: dict[str, int] = {
    "jänner": 1, "jaenner": 1, "januar": 1, "jän": 1, "jan": 1,
    "feber": 2, "februar": 2, "feb": 2,
    "märz": 3, "maerz": 3, "mär": 3, "mrz": 3,
    "april": 4, "apr": 4,
    "mai": 5,
    "juni": 6, "jun": 6,
    "juli": 7, "jul": 7,
    "august": 8, "aug": 8,
    "september": 9, "sept": 9, "sep": 9,
    "oktober": 10, "okt": 10,
    "november": 11, "nov": 11,
    "dezember": 12, "dez": 12,
}  # fmt: skip
_ANZEIGE_MONAT = (
    "Jänner", "Februar", "März", "April", "Mai", "Juni",
    "Juli", "August", "September", "Oktober", "November", "Dezember",
)  # fmt: skip
_STATUS_TEXT = {"vorlaeufig": "vorläufig", "endgueltig": "endgültig", "gesperrt": "gesperrt"}

_ISO = re.compile(r"(?<!\d)(\d{4})-(\d{1,2})(?!\d)")
_ZAHL_MONAT = re.compile(r"(?<!\d)(\d{1,2})[./](\d{4})(?!\d)")
_NAME_MONAT = re.compile(
    r"(?<!\w)("
    + "|".join(sorted(map(re.escape, MONATSNAMEN), key=len, reverse=True))
    + r")\.?\s+(\d{4})(?!\d)"
)
_OENACE_CODE = re.compile(r"(?:önace|oenace)[\s-]*(?:abschnitt\s+)?([a-z])(?!\w)")


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
    jahr, nummer = monat.split("-")
    return f"{_ANZEIGE_MONAT[int(nummer) - 1]} {jahr}"


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


def _abfrage(
    stand: LaufStand, monat: str, filter_: list[tuple[Merkmal, str]], gruppe: Merkmal | None
) -> sql.Composed:
    """SELECT über stat.stat_beschaeftigte; Parameter sind nur Regelsatz, Regelstand, Monat, Gliederung."""
    bedingungen = [
        sql.SQL("s.regelsatz = {}").format(sql.Literal(stand.regelsatz)),
        sql.SQL("s.regelstand = {}").format(sql.Literal(stand.regelstand)),
        sql.SQL("s.zeitraum_art = {}").format(sql.Literal(STICHTAG)),
        sql.SQL("s.variable = {}").format(sql.Literal(STICHTAG_VARIABLE)),
        sql.SQL("s.zeitraum_bis BETWEEN {} AND {}").format(
            sql.Literal(monatserster(monat)), sql.Literal(monatsletzter(monat))
        ),
    ]
    for merkmal, code in filter_:
        bedingungen.append(sql.SQL("{} = {}").format(sql.SQL(merkmal.spalte), sql.Literal(code)))
    join = any(m.join_qualifikation for m, _ in filter_) or (gruppe is not None and gruppe.join_qualifikation)
    teile: list[sql.Composable] = [
        sql.SQL("SELECT {}COALESCE(sum(s.wert), 0)::bigint AS wert FROM stat.stat_beschaeftigte s").format(
            sql.SQL(f"{gruppe.spalte} AS code, " if gruppe else "")
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


def antwort_daten(conn: Verbindung, frage: str, regelsatz: str = "v1") -> dict[str, Any]:
    """Felder einer ``UcAntwort`` als dict, ohne ``plattform.antwortform`` (testbar vor dem Merge von !30)."""
    monat = monat_lesen(frage)
    if monat is None:
        return _leer(
            "UC3 hat in der Frage keinen Monat erkannt. Bitte einen Monat nennen, z. B. „März 2025“ oder 2025-03."
        )
    stand = letzter_lauf(conn, monat, regelsatz)
    if stand is None:
        return _leer(
            f"Für {_monat_anzeige(monat)} gibt es noch keinen gerechneten Lauf (Regelsatz {regelsatz})."
        )

    filter_: list[tuple[Merkmal, str]] = []
    etiketten: list[str] = []
    gruppe = _gliederung(frage)
    gruppen_codes: dict[str, str] = {}
    for merkmal in MERKMALE:
        codes = _codes(conn, merkmal, monat)
        if merkmal is gruppe:
            gruppen_codes = codes
            continue
        code = _auspraegung(frage, merkmal, codes)
        if code is not None:
            filter_.append((merkmal, code))
            etiketten.append(codes[code])

    abfrage = _abfrage(stand, monat, filter_, gruppe)
    sql_text = abfrage.as_string(conn)
    zeilen = conn.execute(abfrage).fetchall()
    bezeichnung, einheit = _variable(conn)
    status = _STATUS_TEXT.get(stand.ergebnis_status, stand.ergebnis_status)
    beleg = {
        "quelle": QUELLE,
        "lieferung": stand.lieferung,
        "monat": monat,
        "sql": sql_text,
        "ref": f"meta.lauf/{stand.lauf_id} regelstand {stand.regelstand} {stand.ergebnis_status}",
    }
    zusatz = f" ({', '.join(etiketten)})" if etiketten else ""
    stichtag = monatsletzter(monat).strftime("%d.%m.%Y")
    if gruppe is None:
        wert = int(str(zeilen[0]["wert"]))
        zahlen = [{"bezeichnung": bezeichnung + zusatz, "wert": wert, "einheit": einheit, "beleg": 0}]
        text = (
            f"Am Stichtag {stichtag} ({_monat_anzeige(monat)}) gab es {_deutsch(wert)} {bezeichnung}{zusatz}; "
            f"die Zahl ist {status} (Lauf {stand.lauf_id})."
        )
    else:
        zahlen = [
            {
                "bezeichnung": f"{bezeichnung}{zusatz}, {gruppen_codes.get(str(z['code']), str(z['code']))}",
                "wert": int(str(z["wert"])),
                "einheit": einheit,
                "beleg": 0,
            }
            for z in zeilen
        ]
        summe = sum(int(str(z["wert"])) for z in zeilen)
        text = (
            f"Am Stichtag {stichtag} ({_monat_anzeige(monat)}) gab es {_deutsch(summe)} {bezeichnung}{zusatz}, "
            f"aufgeteilt nach {gruppe.name} in {len(zahlen)} Zahlen; die Zahlen sind {status} "
            f"(Lauf {stand.lauf_id})."
        )
    return {"text": text, "belege": [beleg], "zahlen": zahlen, "uc": UC, "modell": None, "protokoll_id": None}


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
            "ohne ihn liefert nur statagent.uc4.antwort_daten ein dict."
        ) from fehler
    with verbinden() as conn:
        daten = antwort_daten(conn, frage)
    return UcAntwort(**daten)
