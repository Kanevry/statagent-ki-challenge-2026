"""Lese-Werkzeuge der Agenten: Schema, Regeln, Klassifikationen und Aggregate, nie Einzeldaten.

Alles hier liest nur. ``sql_lesen`` läuft in einer Nur-Lese-Transaktion mit Zeitlimit, liefert höchstens
200 Zeilen und verweigert jede Abfrage, die Personen- oder Verhältniskennungen (PERSON_ID, VVH_ID) zeigen
würde. Was ein Werkzeug liefert, darf an ein Sprachmodell gehen.
"""

from __future__ import annotations

import re
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from psycopg import pq, sql

from statagent.db import Verbindung

HOECHSTENS_ZEILEN = 200
ZEITLIMIT = "10s"
#: Spalten, die eine Person oder ein Beschäftigungsverhältnis kennzeichnen (Einzeldaten).
GESPERRTE_SPALTEN = frozenset({"person_id", "vvh_id"})
#: Prüftreffer tragen Beispiel-Kennungen in ``beispiele``; auch die gehen nicht an das Modell.
GESPERRTE_WOERTER = (*sorted(GESPERRTE_SPALTEN), "beispiele")
SCHEMAS = ("stat", "meta", "bereinigt", "klassifikation")
#: Schemas mit Sätzen je Verhältnis: nur mit Aggregat (GROUP BY oder Aggregatfunktion) lesbar.
EINZELSATZ_SCHEMAS = ("roh", "bereinigt")
_AGGREGAT = re.compile(r"\b(group\s+by|count|sum|avg|min|max)\b", re.IGNORECASE)


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
    klein = ohne_kommentare.lower()
    for wort in GESPERRTE_WOERTER:
        if re.search(rf"\b{wort}\b", klein):
            raise AbfrageVerweigert(f"„{wort}“ kennzeichnet Einzeldaten und geht nicht an das Modell.")
    if any(re.search(rf"\b{s}\s*\.", klein) for s in EINZELSATZ_SCHEMAS) and not _AGGREGAT.search(klein):
        raise AbfrageVerweigert("roh.* und bereinigt.* nur als Aggregat (GROUP BY, count, sum …).")
    return text


def sql_lesen(conn: Verbindung, query: str) -> dict[str, Any]:
    """Führt eine geprüfte Leseabfrage aus: ``{spalten, zeilen, abgeschnitten}``.

    Braucht eine Verbindung ohne offene Transaktion (die Nur-Lese-Einstellung muss am Anfang stehen).
    """
    text = abfrage_pruefen(query)
    if conn.info.transaction_status != pq.TransactionStatus.IDLE:
        raise AbfrageVerweigert("sql_lesen braucht eine Verbindung ohne offene Transaktion.")
    with conn.transaction():
        conn.execute("SET TRANSACTION READ ONLY")
        conn.execute(sql.SQL("SET LOCAL statement_timeout = {}").format(sql.Literal(ZEITLIMIT)))
        with conn.cursor() as cur:
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
