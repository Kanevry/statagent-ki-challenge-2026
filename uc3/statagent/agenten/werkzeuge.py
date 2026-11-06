"""Lese-Werkzeuge der Agenten: Schema, Regeln, Klassifikationen und Aggregate, nie Einzeldaten.

Alles hier liest nur. Was ein Werkzeug liefert, darf an ein Sprachmodell gehen.

- ``sql_lesen`` (freie Abfrage) liest nur stat.*, meta.* und klassifikation.*. Jede Abfrage, die roh.* oder
  bereinigt.* berührt, wird verweigert, egal ob ein Aggregatwort darin steht: ``count(*) OVER()`` oder
  ``geburtsdatum AS count`` würden sonst Einzelsätze durchlassen. Drei Sperren hintereinander: Text
  (Schemaname, Datei-/Fremd-/Abfrage-als-Text-Funktionen, ``search_path``), ``SET LOCAL search_path`` auf die
  freien Schemas, und der Ausführungsplan (jede gelesene Tabelle muss in einem freien Schema liegen).
- roh.* nur über feste Aggregatfunktionen (``roh_kennzahlen``), parametrisiert nur mit der Lieferung,
  Zellen unter ``MINDESTZELLE`` als „<5“.
"""

from __future__ import annotations

import re
from datetime import date, datetime
from decimal import Decimal
from typing import Any

import psycopg
from psycopg import pq, sql

from statagent.db import Verbindung

HOECHSTENS_ZEILEN = 200
ZEITLIMIT = "10s"
#: Spalten, die eine Person oder ein Beschäftigungsverhältnis kennzeichnen (Einzeldaten).
#: Prüftreffer, Rückfragen und Revisionsursachen tragen Beispiel-Kennungen in ``beispiele``; auch die gehen nicht an
#: das Modell. Eine Tabelle mit einer dieser Spalten ist für freie Abfragen ganz gesperrt (auch über to_jsonb(t)).
GESPERRTE_SPALTEN = frozenset({"person_id", "vvh_id", "beispiele"})
GESPERRTE_WOERTER = tuple(sorted(GESPERRTE_SPALTEN))
#: Struktur (ohne Daten) für ``schema_lesen``.
SCHEMAS = ("stat", "meta", "bereinigt", "klassifikation")
#: Was eine freie Abfrage lesen darf: Aggregate, Regeln, Läufe, Klassifikationen. Keine Tabelle dort trägt
#: PERSON_ID oder VVH_ID (nur bereinigt.abschnitt und roh.lieferung); die Spaltensperre bleibt zusätzlich.
FREIE_SCHEMAS = ("stat", "meta", "klassifikation")
#: Schemas mit Sätzen je Verhältnis: für freie Abfragen gesperrt, nur über feste Aggregatfunktionen.
EINZELSATZ_SCHEMAS = ("roh", "bereinigt")
_EINZELSATZ_WORT = re.compile(rf"\b({'|'.join(EINZELSATZ_SCHEMAS)})\b")
#: Wege an der Schemaprüfung vorbei: Dateien, Large Objects, andere Datenbanken, Einstellungen,
#: Abfragen als Text (``query_to_xml('…')``, ``ts_stat``) und Systemkataloge (``pg_stats`` zeigt Werte).
_GESPERRTE_WEGE = re.compile(
    r"\b(pg_read_\w*|pg_ls_\w*|pg_file_\w*|pg_stat\w*|lo_\w*|dblink\w*|copy|set_config|search_path"
    r"|query_to_\w*|cursor_to_\w*|table_to_\w*|schema_to_\w*|database_to_\w*|ts_stat|xpath\w*"
    r"|pg_catalog|information_schema|pg_temp\w*|pg_toast\w*)\b|\bu&"
)
#: Kleinste Zelle, die ``roh_kennzahlen`` als Zahl ausgibt (Geheimhaltung); kleinere als „<5“.
MINDESTZELLE = 5
#: Felder von roh.lieferung ohne Kennungen, für die ``roh_kennzahlen`` leere Felder zählt.
ROH_FELDER = ("geburtsdatum", "geschlecht", "beginn", "ende", "qual", "oenace", "bundesland")
#: Merkmale, für die ``roh_kennzahlen`` die Anzahl je gelieferten Code zählt.
ROH_MERKMALE = ("qual", "oenace", "bundesland", "geschlecht")


class AbfrageVerweigert(PermissionError):
    """Die Abfrage würde schreiben, Einzeldaten zeigen oder ist kein einzelnes SELECT."""


def _json_wert(wert: object) -> object:
    if wert is None or isinstance(wert, bool | int | float | str):
        return wert
    if isinstance(wert, Decimal):
        return int(wert) if wert == wert.to_integral_value() else float(wert)
    if isinstance(wert, date | datetime):
        return wert.isoformat()
    if isinstance(wert, list | tuple):
        return [_json_wert(w) for w in wert]
    if isinstance(wert, dict):
        return {str(k): _json_wert(v) for k, v in wert.items()}
    return str(wert)


def abfrage_pruefen(query: str) -> str:
    """Prüft eine Abfrage vor dem Ausführen. Liefert sie ohne abschließendes Semikolon."""
    text = query.strip().rstrip(";").strip()
    ohne_kommentare = re.sub(r"--[^\n]*|/\*.*?\*/", " ", text, flags=re.DOTALL).strip()
    if not re.match(r"(?i)(select|with)\b", ohne_kommentare):
        raise AbfrageVerweigert("Nur Abfragen, die mit SELECT oder WITH beginnen, sind erlaubt.")
    if ";" in ohne_kommentare:
        raise AbfrageVerweigert("Nur eine einzelne Abfrage ist erlaubt.")
    # Anführungszeichen weg: "ROH" . "lieferung" ist dieselbe Tabelle wie roh.lieferung.
    klein = ohne_kommentare.lower().replace('"', "")
    for wort in GESPERRTE_WOERTER:
        if re.search(rf"\b{wort}\b", klein):
            raise AbfrageVerweigert(f"„{wort}“ kennzeichnet Einzeldaten und geht nicht an das Modell.")
    if _EINZELSATZ_WORT.search(klein):
        raise AbfrageVerweigert(
            "roh.* und bereinigt.* enthalten Einzelsätze und sind für freie Abfragen gesperrt; "
            "Kennzahlen dazu liefert roh_kennzahlen."
        )
    weg = _GESPERRTE_WEGE.search(klein)
    if weg:
        raise AbfrageVerweigert(f"„{weg.group(0)}“ ist in freien Abfragen gesperrt.")
    return text


def _plan_tabellen(knoten: object) -> set[str]:
    """Alle Tabellen ``schema.name``, die ein EXPLAIN-Plan (JSON, VERBOSE) liest, auch in Unterplänen."""
    gefunden: set[str] = set()
    if isinstance(knoten, dict):
        if "Relation Name" in knoten:
            gefunden.add(f"{knoten.get('Schema', '?')}.{knoten['Relation Name']}")
        for wert in knoten.values():
            gefunden |= _plan_tabellen(wert)
    elif isinstance(knoten, list):
        for wert in knoten:
            gefunden |= _plan_tabellen(wert)
    return gefunden


def sql_lesen(conn: Verbindung, query: str, zeitlimit: str = ZEITLIMIT) -> dict[str, Any]:
    """Führt eine geprüfte Leseabfrage aus: ``{spalten, zeilen, abgeschnitten}``.

    Braucht eine Verbindung ohne offene Transaktion (die Nur-Lese-Einstellung muss am Anfang stehen).
    """
    text = abfrage_pruefen(query)
    if conn.info.transaction_status != pq.TransactionStatus.IDLE:
        raise AbfrageVerweigert("sql_lesen braucht eine Verbindung ohne offene Transaktion.")
    with conn.transaction():
        conn.execute("SET TRANSACTION READ ONLY")
        conn.execute(sql.SQL("SET LOCAL statement_timeout = {}").format(sql.Literal(zeitlimit)))
        # Unqualifizierte Namen landen nur in den freien Schemas, nie in roh (auch wenn die Verbindung
        # vorher einen anderen search_path gesetzt hat).
        conn.execute(
            sql.SQL("SET LOCAL search_path = {}").format(
                sql.SQL(", ").join(sql.Identifier(s) for s in FREIE_SCHEMAS)
            )
        )
        with conn.cursor() as cur:
            try:
                cur.execute(b"EXPLAIN (VERBOSE, FORMAT JSON) " + text.encode())
            except psycopg.errors.UndefinedTable as fehler:
                raise AbfrageVerweigert(
                    f"Tabelle unbekannt in {', '.join(FREIE_SCHEMAS)}: {fehler.diag.message_primary}"
                ) from None
            plan = cur.fetchone()
            tabellen = _plan_tabellen(None if plan is None else list(plan.values()))
            fremd = sorted(t for t in tabellen if t.split(".", 1)[0] not in FREIE_SCHEMAS)
            if fremd:
                raise AbfrageVerweigert(
                    f"Die Abfrage liest außerhalb von stat/meta/klassifikation: {', '.join(fremd)}"
                )
            if tabellen:
                cur.execute(
                    b"""SELECT DISTINCT table_schema || '.' || table_name AS tabelle FROM information_schema.columns
                        WHERE table_schema || '.' || table_name = ANY(%s) AND lower(column_name) = ANY(%s)""",
                    (sorted(tabellen), sorted(GESPERRTE_SPALTEN)),
                )
                mit_kennung = sorted(str(z["tabelle"]) for z in cur.fetchall())
                if mit_kennung:
                    raise AbfrageVerweigert(
                        f"{', '.join(mit_kennung)} trägt Kennungen ({', '.join(sorted(GESPERRTE_SPALTEN))}) "
                        "und ist für freie Abfragen gesperrt."
                    )
            cur.execute(text.encode())
            spalten = [s.name for s in (cur.description or [])]
            gesperrt = sorted({s for s in spalten if s.lower() in GESPERRTE_SPALTEN})
            if gesperrt:
                raise AbfrageVerweigert(f"Ergebnis enthält Einzeldaten-Spalten: {', '.join(gesperrt)}")
            roh = cur.fetchmany(HOECHSTENS_ZEILEN + 1)
    zeilen = [{k: _json_wert(v) for k, v in z.items()} for z in roh[:HOECHSTENS_ZEILEN]]
    return {"spalten": spalten, "zeilen": zeilen, "abgeschnitten": len(roh) > HOECHSTENS_ZEILEN}


def regeln_lesen(conn: Verbindung, regelsatz: str) -> list[dict[str, Any]]:
    """Aktive Regeln eines Regelsatzes mit Art, Parametern, Beschreibung und Freigabestand."""
    zeilen = conn.execute(
        """SELECT name, typ, art, reihenfolge, parameter, beschreibung, gueltig_ab_lieferung,
                  gueltig_bis_lieferung, freigegeben_von IS NOT NULL AS freigegeben
           FROM meta.regel WHERE regelsatz = %s AND aktiv ORDER BY typ, reihenfolge, name""",
        (regelsatz,),
    ).fetchall()
    return [{k: _json_wert(v) for k, v in z.items()} for z in zeilen]


def schema_lesen(conn: Verbindung) -> dict[str, list[str]]:
    """Tabellen und Spalten (mit Typ) von stat, meta, bereinigt, klassifikation. Ohne Daten, ohne Kennungen."""
    zeilen = conn.execute(
        """SELECT table_schema || '.' || table_name AS tabelle, column_name, data_type
           FROM information_schema.columns
           WHERE table_schema = ANY(%s)
           ORDER BY table_schema, table_name, ordinal_position""",
        (list(SCHEMAS),),
    ).fetchall()
    schema: dict[str, list[str]] = {}
    for z in zeilen:
        spalte = str(z["column_name"])
        if spalte.lower() in GESPERRTE_SPALTEN:
            continue
        schema.setdefault(str(z["tabelle"]), []).append(f"{spalte} {z['data_type']}")
    return schema


def klassifikation_lesen(conn: Verbindung, begriff: str) -> dict[str, list[dict[str, Any]]]:
    """Inhalt der Klassifikationstabellen, deren Name den Begriff enthält (je höchstens 200 Zeilen)."""
    tabellen = conn.execute(
        """SELECT table_name FROM information_schema.tables
           WHERE table_schema = 'klassifikation' AND table_name ILIKE %s ORDER BY table_name""",
        (f"%{begriff.strip()}%",),
    ).fetchall()
    ergebnis: dict[str, list[dict[str, Any]]] = {}
    for t in tabellen:
        name = str(t["table_name"])
        zeilen = conn.execute(
            sql.SQL("SELECT * FROM klassifikation.{} ORDER BY 1 LIMIT {}").format(
                sql.Identifier(name), sql.Literal(HOECHSTENS_ZEILEN)
            )
        ).fetchall()
        ergebnis[f"klassifikation.{name}"] = [
            {k: _json_wert(v) for k, v in z.items() if k.lower() not in GESPERRTE_SPALTEN} for z in zeilen
        ]
    return ergebnis


#: Kennzeichen einer Zelle, die nur unterdrückt ist, damit sich eine „<5“-Zelle nicht aus der Summe zurückrechnen lässt.
SEKUNDAER = "geheim"


def _verteilung(werte: dict[str, int]) -> dict[str, int | str]:
    """Anzahl je Code mit Geheimhaltung: Zellen 1–4 als „<5“. Ist genau eine Zelle so unterdrückt, wird zusätzlich
    die kleinste übrige Zelle über 0 als „geheim“ ausgewiesen (sekundäre Sperrung), weil die Zeilenzahl der Lieferung
    exakt bekannt ist und die einzelne Zelle sonst als Differenz ablesbar wäre."""
    aus: dict[str, int | str] = {k: _zelle(n) for k, n in werte.items()}
    primaer = [k for k, v in aus.items() if isinstance(v, str)]
    if len(primaer) == 1:
        offen = sorted((n, k) for k, n in werte.items() if k not in primaer and n > 0)
        if offen:
            aus[offen[0][1]] = SEKUNDAER
    return aus


def _zelle(n: int) -> int | str:
    """Geheimhaltung: Zellen von 1 bis MINDESTZELLE - 1 gehen nur als „<5“ hinaus (0 bleibt 0)."""
    return n if n == 0 or n >= MINDESTZELLE else f"<{MINDESTZELLE}"


def roh_kennzahlen(conn: Verbindung, lieferung: str) -> dict[str, Any]:
    """Feste Aggregate einer Rohlieferung: Zeilen, leere Felder je Spalte, Anzahl je Code, Zeitraum als Monat.

    Einziger Weg, auf dem eine Rolle etwas über roh.lieferung erfährt. Parametrisiert nur mit der Lieferung,
    ohne Kennungen, Zellen unter MINDESTZELLE als „<5“.
    """
    if not re.fullmatch(r"\d{4}-\d{2}", lieferung):
        raise AbfrageVerweigert(f"Lieferung {lieferung!r} hat nicht die Form JJJJ-MM")
    leer = sql.SQL(", ").join(
        sql.SQL("count(*) FILTER (WHERE nullif(btrim({f}::text), '') IS NULL) AS {f}").format(
            f=sql.Identifier(f)
        )
        for f in ROH_FELDER
    )
    monate = sql.SQL(", ").join(
        sql.SQL("{fn}(left(nullif(btrim({f}::text), ''), 7)) AS {a}").format(
            fn=sql.SQL(fn), f=sql.Identifier(f), a=sql.Identifier(f"{f}_{fn}")
        )
        for f in ("beginn", "ende")
        for fn in ("min", "max")
    )
    z = conn.execute(
        sql.SQL("SELECT count(*) AS zeilen, {}, {} FROM roh.lieferung WHERE lieferung = %s").format(
            leer, monate
        ),
        (lieferung,),
    ).fetchone()
    assert z is not None
    zeilen = int(str(z["zeilen"]))
    je_code: dict[str, dict[str, int | str]] = {}
    for m in ROH_MERKMALE:
        codes = conn.execute(
            sql.SQL(
                """SELECT coalesce(nullif(btrim({m}::text), ''), '(leer)') AS code, count(*) AS n
                   FROM roh.lieferung WHERE lieferung = %s GROUP BY 1 ORDER BY 1"""
            ).format(m=sql.Identifier(m)),
            (lieferung,),
        ).fetchall()
        je_code[m] = _verteilung({str(c["code"]): int(str(c["n"])) for c in codes})
    leere_felder: dict[str, dict[str, int | float | str]] = {}
    for f in ROH_FELDER:
        n = int(str(z[f]))
        anteil: float | str = round(n / zeilen, 4) if zeilen and _zelle(n) == n else _zelle(n)
        leere_felder[f] = {"anzahl": _zelle(n), "anteil": anteil}
    return {
        "lieferung": lieferung,
        "zeilen": _zelle(zeilen),
        "leere_felder": leere_felder,
        "je_code": je_code,
        "zeitraum": {f: {"min": z[f"{f}_min"], "max": z[f"{f}_max"]} for f in ("beginn", "ende")},
    }
