"""Klassifikationserklärung (#75): Versionen, Codes, Übergänge und Quellzuordnungen aus ``stat.klass_*``.

Alles kommt aus der Datenbank: Bezeichnungen aus ``stat.klass_*``, Übergänge aus ``stat.uebergang``,
Quellzuordnungen aus ``stat.quellzuordnung``, Zahlen aus ``stat.stat_beschaeftigte`` (Aggregate). Der Code
hier kennt nur die Struktur der Tabellen, keine Zuordnung.

Dazu der Lader für den amtlichen Umsteiger ÖNACE 2008 → 2025 (``OENACE2008_OENACE2025_DE_12B.txt`` aus dem
Startpaket): je Unterklasse ein Übergang (Klassifikation ``oenace_unterklasse``) und je Abschnitt die
Abschnitte, auf die seine Unterklassen führen (Klassifikation ``oenace``), mit Anteil in ``quelle``.
Importiert ``plattform.llm`` nicht (R2).
"""

from __future__ import annotations

import csv
import io
import re
from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

from psycopg import sql

from statagent import konfig
from statagent.db import Verbindung

#: Umsteiger im Startpaket (Statistik Austria, Format 12B: Semikolon, Anführungszeichen, Windows-1252).
UMSTEIGER_DATEI = Path("klassifikationen") / "oenace" / "OENACE2008_OENACE2025_DE_12B.txt"
_UMSTEIGER_NAME = re.compile(r"OENACE(\d{4})_OENACE(\d{4})_DE_12B\.txt$")
UNTERKLASSE = "oenace_unterklasse"


@dataclass(frozen=True)
class Begriff:
    """Ein Merkmal der Beschäftigtenstatistik und wo es in der Datenbank steht."""

    name: str
    titel: str
    tabelle: str  # stat.klass_*
    versioniert: bool  # Spalte version vorhanden
    gueltigkeit: bool  # Spalten gueltig_von/gueltig_bis vorhanden
    spalte: str  # Ausdruck in stat.stat_beschaeftigte (s), q = klass_qualifikation
    quellmerkmal: str | None  # stat.quellzuordnung.merkmal
    join_qualifikation: bool = False
    ganzzahl: bool = False
    nur_abschnitte: bool = False  # bei der Codeliste nur Ebene 1


BEGRIFFE: dict[str, Begriff] = {
    b.name: b
    for b in (
        Begriff("oenace", "ÖNACE (Wirtschaftszweig)", "klass_oenace", True, True, "s.oenace", "oenace",
                nur_abschnitte=True),
        Begriff("region", "Region (Bundesland)", "klass_region", True, True, "s.region", "bundesland"),
        Begriff("qualifikation", "Qualifikation", "klass_qualifikation", False, True, "s.qualifikation",
                "qualifikation"),
        Begriff("beschaeftigungskategorie", "Beschäftigungskategorie", "klass_beschaeftigungskategorie", False,
                True, "q.beschaeftigungskategorie", None, join_qualifikation=True),
        Begriff("geschlecht", "Geschlecht", "klass_geschlecht", False, True, "s.geschlecht", "geschlecht"),
        Begriff("alter", "Alter in vollendeten Jahren", "klass_alter", False, False, "s.alter", None,
                ganzzahl=True),
    )
}  # fmt: skip
#: Andere Schreibweisen, die die Jury eintippen könnte.
ALIASE = {
    "önace": "oenace", "nace": "oenace", "bundesland": "region", "bundeslaender": "region",
    "bundesländer": "region", "kategorie": "beschaeftigungskategorie", "beschäftigungskategorie":
    "beschaeftigungskategorie", "qual": "qualifikation",
}  # fmt: skip


class KlassFehler(ValueError):
    """Unbekannter Begriff oder Code; die Meldung ist für Menschen geschrieben."""


def begriff_finden(name: str) -> Begriff:
    schluessel = name.strip().lower()
    schluessel = ALIASE.get(schluessel, schluessel)
    if schluessel not in BEGRIFFE:
        raise KlassFehler(f"Den Begriff „{name}“ kenne ich nicht. Möglich sind: {', '.join(BEGRIFFE)}.")
    return BEGRIFFE[schluessel]


def _datum(wert: object) -> str:
    return wert.strftime("%d.%m.%Y") if isinstance(wert, date) else ""


def gueltig_text(von: object, bis: object) -> str:
    if not isinstance(von, date) or von.year <= 1900:
        return "ohne Ablaufdatum" if bis is None else f"gültig bis {_datum(bis)}"
    return f"gültig ab {_datum(von)}" if bis is None else f"gültig {_datum(von)} bis {_datum(bis)}"


def _version_spalte(b: Begriff) -> sql.Composable:
    return sql.SQL("version") if b.versioniert else sql.Literal("-")


def _gueltig_spalten(b: Begriff) -> sql.Composable:
    if b.gueltigkeit:
        return sql.SQL("gueltig_von, gueltig_bis")
    return sql.SQL("NULL::date AS gueltig_von, NULL::date AS gueltig_bis")


def versionen(conn: Verbindung, b: Begriff, version: str | None = None) -> list[dict[str, Any]]:
    """Versionen mit Gültigkeit und Anzahl Codes; je Version die Codes mit Bezeichnung (ÖNACE: Abschnitte)."""
    abfrage = sql.SQL(
        "SELECT {v} AS version, code::text AS code, bezeichnung, {g}{e} FROM stat.{t} ORDER BY 1, {o}"
    ).format(
        v=_version_spalte(b),
        g=_gueltig_spalten(b),
        e=sql.SQL(", ebene::text AS ebene") if b.versioniert else sql.SQL(""),
        t=sql.Identifier(b.tabelle),
        o=sql.SQL("code") if b.ganzzahl else sql.SQL('code COLLATE "C"'),
    )
    gruppen: dict[str, dict[str, Any]] = {}
    for z in conn.execute(abfrage).fetchall():
        v = str(z["version"])
        if version is not None and v != version:
            continue
        g = gruppen.setdefault(
            v, {"version": v, "gueltig_von": z["gueltig_von"], "gueltig_bis": z["gueltig_bis"], "anzahl": 0,
                "codes": []},
        )  # fmt: skip
        g["anzahl"] += 1
        von, bis = z["gueltig_von"], z["gueltig_bis"]
        if isinstance(von, date) and (not isinstance(g["gueltig_von"], date) or von < g["gueltig_von"]):
            g["gueltig_von"] = von
        if bis is None:
            g["gueltig_bis"] = None
        elif isinstance(bis, date) and isinstance(g["gueltig_bis"], date) and bis > g["gueltig_bis"]:
            g["gueltig_bis"] = bis
        if not b.nur_abschnitte or str(z.get("ebene")) == "1":
            g["codes"].append({"code": z["code"], "bezeichnung": z["bezeichnung"]})
    return list(gruppen.values())


def _bezeichnungen(conn: Verbindung, b: Begriff, code: str) -> list[dict[str, Any]]:
    bedingung = (
        sql.SQL("code = {}").format(sql.Literal(int(code)))
        if b.ganzzahl
        else sql.SQL("upper(code) = upper({})").format(sql.Literal(code))
    )
    abfrage = sql.SQL(
        "SELECT {v} AS version, code::text AS code, bezeichnung, {g} FROM stat.{t} WHERE {b} ORDER BY 1"
    ).format(v=_version_spalte(b), g=_gueltig_spalten(b), t=sql.Identifier(b.tabelle), b=bedingung)
    return [dict(z) for z in conn.execute(abfrage).fetchall()]


def _uebergaenge(
    conn: Verbindung,
    klassifikation: str,
    b: Begriff,
    code: str,
    version: str | None,
    grenze: int | None = None,
) -> list[dict[str, Any]]:
    """Übergänge, in denen der Code alt oder neu vorkommt (Unterklassen: Code als Anfangsbuchstabe)."""
    unterklasse = klassifikation == UNTERKLASSE
    vergleich = "u.{s} LIKE %(muster)s" if unterklasse else "u.{s} = %(code)s"
    seite_alt = (
        vergleich.format(s="code_alt") + " AND (%(version)s::text IS NULL OR u.version_alt = %(version)s)"
    )
    seite_neu = (
        vergleich.format(s="code_neu") + " AND (%(version)s::text IS NULL OR u.version_neu = %(version)s)"
    )
    abfrage = f"""
        SELECT u.version_alt, u.code_alt, ka.bezeichnung AS bezeichnung_alt,
               u.version_neu, u.code_neu, kn.bezeichnung AS bezeichnung_neu,
               u.beziehung, u.gueltig_ab, u.quelle
        FROM stat.uebergang u
        LEFT JOIN stat.{b.tabelle} ka ON ka.version = u.version_alt AND ka.code = u.code_alt
        LEFT JOIN stat.{b.tabelle} kn ON kn.version = u.version_neu AND kn.code = u.code_neu
        WHERE u.klassifikation = %(klass)s AND (({seite_alt}) OR ({seite_neu}))
        ORDER BY u.version_alt, (left(u.code_alt, 1) = left(u.code_neu, 1)), u.code_alt COLLATE "C",
                 u.code_neu COLLATE "C"
    """
    parameter: dict[str, Any] = {
        "klass": klassifikation,
        "code": code,
        "muster": code[:1] + "%",
        "version": version,
    }
    if grenze is not None:
        abfrage += " LIMIT %(grenze)s"
        parameter["grenze"] = grenze
    return [dict(z) for z in conn.execute(abfrage.encode(), parameter).fetchall()]


def _unterklassen_anzahl(conn: Verbindung, code: str, version: str | None) -> int:
    zeile = conn.execute(
        """SELECT count(*) AS n FROM stat.uebergang u WHERE u.klassifikation = %(k)s
           AND ((u.code_alt LIKE %(m)s AND (%(v)s::text IS NULL OR u.version_alt = %(v)s))
             OR (u.code_neu LIKE %(m)s AND (%(v)s::text IS NULL OR u.version_neu = %(v)s)))""",
        {"k": UNTERKLASSE, "m": code[:1] + "%", "v": version},
    ).fetchone()
    return int(str(zeile["n"])) if zeile else 0


def _quellzuordnungen(conn: Verbindung, b: Begriff, code: str, regelsatz: str) -> list[dict[str, Any]]:
    """Gelieferte Werte, die auf den Code führen, ohne die Identität (geliefert = Code)."""
    if b.quellmerkmal is None:
        return []
    zeilen = conn.execute(
        """SELECT q.geliefert, string_agg(DISTINCT q.version, ', ' ORDER BY q.version) AS versionen,
                  r.name AS regel, r.beschreibung AS regel_text
           FROM stat.quellzuordnung q LEFT JOIN meta.regel r ON r.id = q.regel_id
           WHERE q.regelsatz = %s AND q.merkmal = %s AND q.code = %s AND q.geliefert <> q.code
           GROUP BY q.geliefert, r.name, r.beschreibung ORDER BY r.name NULLS FIRST, q.geliefert COLLATE "C" """,
        (regelsatz, b.quellmerkmal, code),
    ).fetchall()
    return [dict(z) for z in zeilen]


def letzter_veroeffentlichter_monat(conn: Verbindung, regelsatz: str) -> str | None:
    zeile = conn.execute(
        """SELECT max(lieferung) AS monat FROM meta.lauf
           WHERE regelsatz = %s AND ergebnis_status = 'endgueltig' AND status IN ('fertig', 'unveraendert')""",
        (regelsatz,),
    ).fetchone()
    return str(zeile["monat"]) if zeile and zeile["monat"] else None


def _verhaeltnisse(conn: Verbindung, b: Begriff, code: str, regelsatz: str) -> dict[str, Any] | None:
    """Verhältnisse am Stichtag des letzten veröffentlichten Monats mit diesem Code, je ÖNACE-Version."""
    from statagent.berichte.sheet import STICHTAG, STICHTAG_VARIABLE
    from statagent.ergebnis import letzter_lauf, monatserster, monatsletzter

    monat = letzter_veroeffentlichter_monat(conn, regelsatz)
    if monat is None:
        return None
    stand = letzter_lauf(conn, monat, regelsatz)
    if stand is None:
        return None
    wert = sql.Literal(int(code)) if b.ganzzahl else sql.Literal(code)
    abfrage = sql.SQL(
        "SELECT s.oenace_version AS version, COALESCE(sum(s.wert), 0)::bigint AS wert"
        " FROM stat.stat_beschaeftigte s{join} WHERE s.regelsatz = {rs} AND s.regelstand = {st}"
        " AND s.zeitraum_art = {za} AND s.variable = {va} AND s.zeitraum_bis BETWEEN {von} AND {bis}"
        " AND {spalte} = {wert} GROUP BY 1 ORDER BY 1"
    ).format(
        join=sql.SQL(" LEFT JOIN stat.klass_qualifikation q ON q.code = s.qualifikation")
        if b.join_qualifikation
        else sql.SQL(""),
        rs=sql.Literal(stand.regelsatz),
        st=sql.Literal(stand.regelstand),
        za=sql.Literal(STICHTAG),
        va=sql.Literal(STICHTAG_VARIABLE),
        von=sql.Literal(monatserster(monat)),
        bis=sql.Literal(monatsletzter(monat)),
        spalte=sql.SQL(b.spalte),
        wert=wert,
    )
    zeilen = conn.execute(abfrage).fetchall()
    return {
        "monat": monat,
        "stichtag": monatsletzter(monat),
        "lauf_id": stand.lauf_id,
        "regelstand": stand.regelstand,
        "status": stand.ergebnis_status,
        "je_version": [{"oenace_version": str(z["version"]), "wert": int(str(z["wert"]))} for z in zeilen],
        "sql": abfrage.as_string(conn),
    }


def erklaeren(
    conn: Verbindung,
    begriff: str,
    code: str | None = None,
    version: str | None = None,
    regelsatz: str = "v1",
    unterklassen: int = 0,
) -> dict[str, Any]:
    """Erklärung eines Begriffs (ohne Code: Versionen und Codes) oder eines Codes (Bezeichnung, Übergänge,
    Quellzuordnungen, Verhältnisse im letzten veröffentlichten Monat)."""
    b = begriff_finden(begriff)
    if code is None:
        liste = versionen(conn, b, version)
        if version is not None and not liste:
            raise KlassFehler(f"{b.titel} hat keine Version „{version}“.")
        return {"begriff": b.name, "titel": b.titel, "versionen": liste}

    if b.ganzzahl and not re.fullmatch(r"-?\d+", code.strip()):
        raise KlassFehler(f"Bei {b.titel} ist der Code eine ganze Zahl, nicht „{code}“.")
    namen = _bezeichnungen(conn, b, code.strip())
    if version is not None:
        namen = [n for n in namen if n["version"] == version]
    if not namen:
        raise KlassFehler(
            f"Den Code ({code}) gibt es in {b.titel}{f' Version {version}' if version else ''} nicht."
        )
    echt = str(namen[0]["code"])
    daten: dict[str, Any] = {
        "begriff": b.name,
        "titel": b.titel,
        "code": echt,
        "bezeichnungen": namen,
        "uebergaenge": _uebergaenge(conn, b.name, b, echt, version) if b.versioniert else [],
        "quellzuordnungen": _quellzuordnungen(conn, b, echt, regelsatz),
        "verhaeltnisse": _verhaeltnisse(conn, b, echt, regelsatz),
        "regelsatz": regelsatz,
    }
    if b.name == "oenace" and unterklassen > 0:
        daten["unterklassen"] = _uebergaenge(conn, UNTERKLASSE, b, echt, version, grenze=unterklassen)
        daten["unterklassen_gesamt"] = _unterklassen_anzahl(conn, echt, version)
    return daten


# --- Text ---------------------------------------------------------------------------------------------------


def _deutsch(wert: int) -> str:
    return f"{wert:,}".replace(",", ".")


def _versionsname(b: Begriff, version: str) -> str:
    if b.name == "oenace":
        return f"ÖNACE {version}"
    return "" if version in ("-", "BL") else f"Version {version}"


def _seite(b: Begriff, version: str, code: str, bezeichnung: object) -> str:
    name = f"{bezeichnung} " if bezeichnung else ""
    return f"{_versionsname(b, version)} {name}({code})".strip()


def _uebergang_zeilen(b: Begriff, liste: list[dict[str, Any]]) -> list[str]:
    """Je Übergang eine Zeile; mehrere alte Codes mit gleichem Ziel und gleicher Quelle in einer Zeile."""
    gruppen: dict[tuple[Any, ...], list[dict[str, Any]]] = {}
    for u in liste:
        schluessel = (
            u["version_alt"],
            u["version_neu"],
            u["code_neu"],
            u["beziehung"],
            u["gueltig_ab"],
            u["quelle"],
        )
        gruppen.setdefault(schluessel, []).append(u)
    zeilen = []
    for gruppe in gruppen.values():
        u = gruppe[0]
        if len(gruppe) == 1:
            von, verb = _seite(b, u["version_alt"], u["code_alt"], u["bezeichnung_alt"]), "wird"
        else:
            codes = ", ".join(f"({g['code_alt']})" for g in gruppe)
            von, verb = f"{_versionsname(b, u['version_alt'])} {codes}".strip(), "werden"
        nach = _seite(b, u["version_neu"], u["code_neu"], u["bezeichnung_neu"])
        zeilen.append(
            f"- {von} {verb} ab {_datum(u['gueltig_ab'])} zu {nach}, Beziehung {u['beziehung']}."
            f" Quelle: {u['quelle'] or 'nicht angegeben'}."
        )
    return zeilen


_STATUS_TEXT = {"vorlaeufig": "vorläufig", "endgueltig": "endgültig", "gesperrt": "gesperrt"}


def text(daten: dict[str, Any]) -> str:
    """Ausgabe in einfacher Sprache; Codes in Klammern."""
    b = BEGRIFFE[daten["begriff"]]
    zeilen: list[str] = []
    if "versionen" in daten:
        zeilen.append(f"{b.titel}: {len(daten['versionen'])} Version(en).")
        for v in daten["versionen"]:
            kopf = _versionsname(b, v["version"]) or b.titel
            art = "Abschnitte" if b.nur_abschnitte else "Codes"
            zeilen.append(
                f"{kopf}, {gueltig_text(v['gueltig_von'], v['gueltig_bis'])}, {v['anzahl']} Codes"
                + (f", davon {len(v['codes'])} {art}:" if b.nur_abschnitte else ":")
            )
            zeilen.extend(f"  {c['bezeichnung']} ({c['code']})" for c in v["codes"])
        return "\n".join(zeilen)

    zeilen.append(f"{b.titel}, Code ({daten['code']})")
    zeilen.append("Bezeichnung je Version:")
    for n in daten["bezeichnungen"]:
        kopf = _versionsname(b, n["version"])
        gilt = gueltig_text(n["gueltig_von"], n["gueltig_bis"])
        zeilen.append(f"- {kopf + ', ' if kopf else ''}{gilt}: {n['bezeichnung']} ({n['code']})")

    if b.versioniert:
        if daten["uebergaenge"]:
            zeilen.append("Übergänge zwischen den Versionen (stat.uebergang):")
            zeilen.extend(_uebergang_zeilen(b, daten["uebergaenge"]))
        else:
            zeilen.append("Übergänge: keine in stat.uebergang.")
    if "unterklassen" in daten:
        zeilen.append(
            f"Unterklassen (zuerst die, die den Abschnitt wechseln), {len(daten['unterklassen'])} von "
            f"{daten['unterklassen_gesamt']}:"
        )
        for u in daten["unterklassen"]:
            zeilen.append(
                f"- ÖNACE {u['version_alt']} ({u['code_alt']}) zu ÖNACE {u['version_neu']} ({u['code_neu']}), "
                f"{u['beziehung']}: {u['quelle']}"
            )

    if daten["quellzuordnungen"]:
        zeilen.append(f"Gelieferte Werte, die auf ({daten['code']}) führen (Regelsatz {daten['regelsatz']}):")
        nach_regel: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for q in daten["quellzuordnungen"]:
            nach_regel[q["regel"] or "Identität"].append(q)
        for regel, liste in nach_regel.items():
            werte = ", ".join(f"({q['geliefert']})" for q in liste)
            fassungen = sorted({v for q in liste for v in str(q["versionen"]).split(", ")} - {"-"})
            in_fassung = f" in Lieferungen mit ÖNACE {' und '.join(fassungen)}" if fassungen else ""
            zeilen.append(f"- {werte}{in_fassung}, Regel {regel}.")
            if liste[0]["regel_text"]:
                zeilen.append(f"  {liste[0]['regel_text']}")
    elif b.quellmerkmal:
        zeilen.append(f"Gelieferte Werte: nur ({daten['code']}) selbst führt auf diesen Code.")

    vh = daten["verhaeltnisse"]
    if vh is None:
        zeilen.append(
            f"Verhältnisse: Es gibt noch keinen veröffentlichten Monat (Regelsatz {daten['regelsatz']})."
        )
    else:
        kopf = (
            f"Verhältnisse am {_datum(vh['stichtag'])} (letzter veröffentlichter Monat {vh['monat']}, "
            f"Lauf {vh['lauf_id']}, Regelstand {vh['regelstand']}, {_STATUS_TEXT.get(vh['status'], vh['status'])}):"
        )
        zeilen.append(kopf)
        if not vh["je_version"]:
            zeilen.append("- keine")
        for z in vh["je_version"]:
            fassung = f" nach ÖNACE {z['oenace_version']}" if b.name == "oenace" else ""
            zeilen.append(f"- ({daten['code']}){fassung}: {_deutsch(z['wert'])}")
        zeilen.append(f"SQL: {vh['sql']}")
    return "\n".join(zeilen)


# --- Umsteiger ÖNACE 2008 → 2025 ----------------------------------------------------------------------------


@dataclass(frozen=True)
class Zeile:
    code_alt: str  # z. B. "C 10.11-0"
    code_neu: str
    beschreibung: str


def umsteiger_lesen(datei: Path) -> tuple[str, str, list[Zeile]]:
    """Liest den Umsteiger (Format 12B). Versionen aus dem Dateinamen, Codes aus Spalte „Code“."""
    treffer = _UMSTEIGER_NAME.search(datei.name)
    if not treffer:
        raise KlassFehler(f"{datei.name}: Dateiname nicht im Format OENACE<alt>_OENACE<neu>_DE_12B.txt.")
    inhalt = datei.read_bytes().decode("cp1252", errors="replace")
    leser = csv.reader(io.StringIO(inhalt), delimiter=";", quotechar='"')
    kopf = next(leser)
    try:
        i_alt, i_neu = kopf.index("Code"), kopf.index("korrespondierender Code")
        i_text = kopf.index("Korrespondenz-Beschreibung")
    except ValueError as fehler:
        raise KlassFehler(f"{datei.name}: Spalte fehlt ({fehler}).") from fehler
    zeilen = [
        Zeile(z[i_alt].strip(), z[i_neu].strip(), z[i_text].strip())
        for z in leser
        if len(z) > max(i_alt, i_neu, i_text) and z[i_alt].strip() and z[i_neu].strip()
    ]
    if not zeilen:
        raise KlassFehler(f"{datei.name}: keine Übergänge gefunden.")
    return treffer.group(1), treffer.group(2), zeilen


def _beziehung(ziele: int, quellen: int) -> str:
    if ziele == 1 and quellen == 1:
        return "1:1"
    if ziele > 1 and quellen == 1:
        return "1:n"
    if ziele == 1:
        return "n:1"
    return "m:n"


def umsteiger_uebergaenge(datei: Path) -> tuple[list[dict[str, str]], str, str]:
    """Zeilen für stat.uebergang: Unterklassen und Abschnitte (Anteil der Unterklassen in ``quelle``)."""
    alt, neu, zeilen = umsteiger_lesen(datei)
    paare: dict[tuple[str, str], list[str]] = defaultdict(list)
    for z in zeilen:
        if z.beschreibung and z.beschreibung not in paare[(z.code_alt, z.code_neu)]:
            paare[(z.code_alt, z.code_neu)].append(z.beschreibung)
        else:
            paare.setdefault((z.code_alt, z.code_neu), [])
    ziele: dict[str, set[str]] = defaultdict(set)
    quellen: dict[str, set[str]] = defaultdict(set)
    for a, n in paare:
        ziele[a].add(n)
        quellen[n].add(a)
    ergebnis: list[dict[str, str]] = []
    for (a, n), texte in sorted(paare.items()):
        ergebnis.append({
            "klassifikation": UNTERKLASSE, "version_alt": alt, "code_alt": a, "version_neu": neu, "code_neu": n,
            "beziehung": _beziehung(len(ziele[a]), len(quellen[n])),
            "quelle": f"{datei.name}: {'; '.join(texte) or 'ohne Beschreibung'}",
        })  # fmt: skip

    # Abschnitte: Buchstabe am Anfang des Codes. Anteil = Unterklassen des alten Abschnitts mit Ziel im neuen.
    unterklassen: dict[str, set[str]] = defaultdict(set)
    abschnitt_paare: dict[tuple[str, str], set[str]] = defaultdict(set)
    for a, n in paare:
        unterklassen[a[0]].add(a)
        abschnitt_paare[(a[0], n[0])].add(a)
    a_ziele: dict[str, set[str]] = defaultdict(set)
    a_quellen: dict[str, set[str]] = defaultdict(set)
    for a, n in abschnitt_paare:
        a_ziele[a].add(n)
        a_quellen[n].add(a)
    for (a, n), codes in sorted(abschnitt_paare.items()):
        ergebnis.append({
            "klassifikation": "oenace", "version_alt": alt, "code_alt": a, "version_neu": neu, "code_neu": n,
            "beziehung": _beziehung(len(a_ziele[a]), len(a_quellen[n])),
            "quelle": f"{datei.name}, {len(codes)} von {len(unterklassen[a])} Unterklassen führen ganz oder "
            "teilweise hierher",
        })  # fmt: skip
    return ergebnis, alt, neu


def umsteiger_laden(conn: Verbindung, datei: Path) -> int:
    """Schreibt den Umsteiger idempotent nach stat.uebergang (ON CONFLICT aktualisiert Beziehung und Quelle).

    ``gueltig_ab`` ist der Beginn der neuen Version laut stat.klass_oenace. Liefert die Zahl der Zeilen.
    """
    zeilen, _alt, neu = umsteiger_uebergaenge(datei)
    beginn = conn.execute(
        "SELECT min(gueltig_von) AS beginn FROM stat.klass_oenace WHERE version = %s", (neu,)
    ).fetchone()
    if beginn is None or beginn["beginn"] is None:
        raise KlassFehler(f"ÖNACE {neu} fehlt in stat.klass_oenace; der Übergang braucht ihr Gültig-ab.")
    with conn.cursor() as cur:
        cur.executemany(
            """INSERT INTO stat.uebergang
                 (klassifikation, version_alt, code_alt, version_neu, code_neu, beziehung, gueltig_ab, quelle)
               VALUES (%(klassifikation)s, %(version_alt)s, %(code_alt)s, %(version_neu)s, %(code_neu)s,
                       %(beziehung)s, %(gueltig_ab)s, %(quelle)s)
               ON CONFLICT (klassifikation, version_alt, code_alt, version_neu, code_neu) DO UPDATE
                 SET beziehung = EXCLUDED.beziehung, gueltig_ab = EXCLUDED.gueltig_ab, quelle = EXCLUDED.quelle""",
            [{**z, "gueltig_ab": beginn["beginn"]} for z in zeilen],
        )
    return len(zeilen)


def umsteiger_einrichten(conn: Verbindung, startpaket: Path | None = None) -> str:
    """Lädt den Umsteiger aus dem Startpaket, falls vorhanden. Fehlt die Datei, nur ein Hinweis."""
    datei = (startpaket or konfig.startpaket()) / UMSTEIGER_DATEI
    if not datei.is_file():
        return (
            f"Hinweis: {UMSTEIGER_DATEI.name} nicht im Startpaket, Übergang ÖNACE 2008 zu 2025 nicht geladen"
        )
    return f"{datei.name} ({umsteiger_laden(conn, datei)} Übergänge)"
