"""Datenbankzugang (psycopg 3) und Schema-Einrichtung aus `uc3/db/*.sql`."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

import psycopg
from psycopg.rows import dict_row

from statagent import konfig

Verbindung = psycopg.Connection[dict[str, object]]


def verbinden(url: str | None = None, *, autocommit: bool = True) -> Verbindung:
    """Öffnet eine Verbindung mit Zeilen als dict.

    Standard ist autocommit: Schreibende Schritte laufen ausdrücklich in ``conn.transaction()``-Blöcken.
    """
    return psycopg.connect(url or konfig.datenbank_url(), autocommit=autocommit, row_factory=dict_row)


@contextmanager
def verbindung(url: str | None = None) -> Iterator[Verbindung]:
    conn = verbinden(url)
    try:
        yield conn
    finally:
        conn.close()


def sql_dateien(verzeichnis: Path | None = None) -> list[Path]:
    """Alle DDL- und Seed-Dateien in Ausführungsreihenfolge (Dateiname aufsteigend)."""
    return sorted((verzeichnis or konfig.DB_VERZEICHNIS).glob("[0-9][0-9][0-9]_*.sql"))


def schema_einrichten(conn: Verbindung, verzeichnis: Path | None = None) -> list[str]:
    """Wendet alle SQL-Dateien idempotent an (eine Transaktion). Liefert die Dateinamen."""
    angewendet: list[str] = []
    with conn.transaction():
        for datei in sql_dateien(verzeichnis):
            conn.execute(datei.read_text(encoding="utf-8").encode())
            angewendet.append(datei.name)
    return angewendet


def lieferungen(conn: Verbindung) -> list[str]:
    """Geladene Lieferungen laut roh.ladeprotokoll, aufsteigend."""
    zeilen = conn.execute("SELECT lieferung FROM roh.ladeprotokoll ORDER BY lieferung").fetchall()
    return [str(z["lieferung"]) for z in zeilen]
