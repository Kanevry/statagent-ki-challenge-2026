"""Datenbankzugang (psycopg 3) und Schema-Einrichtung aus `uc3/db/*.sql`."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

import psycopg
from psycopg.rows import dict_row, tuple_row

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


def plattform_ddl() -> Path | None:
    """Gemeinsame DDL von Vertrag P (``plattform/sql/meta.sql``: meta.protokoll, meta.freigabe), falls vorhanden."""
    try:
        import plattform
    except ModuleNotFoundError:
        return None
    datei = Path(str(plattform.__file__)).parent / "sql" / "meta.sql"
    return datei if datei.is_file() else None


@contextmanager
def tupelzeilen(conn: Verbindung) -> Iterator[Verbindung]:
    """Vertrag-P-Funktionen (plattform.freigabe) lesen Zeilen als Tupel; unsere Verbindungen liefern dicts."""
    alt = conn.row_factory
    conn.row_factory = tuple_row  # type: ignore[assignment]
    try:
        yield conn
    finally:
        conn.row_factory = alt


def sql_dateien(verzeichnis: Path | None = None) -> list[Path]:
    """Alle DDL- und Seed-Dateien in Ausführungsreihenfolge: zuerst Vertrag P (shared), dann uc3/db/NNN_*.sql."""
    eigene = sorted((verzeichnis or konfig.DB_VERZEICHNIS).glob("[0-9][0-9][0-9]_*.sql"))
    gemeinsam = plattform_ddl()
    return ([gemeinsam] if gemeinsam else []) + eigene


def schema_einrichten(conn: Verbindung, verzeichnis: Path | None = None) -> list[str]:
    """Wendet alle SQL-Dateien idempotent an (eine Transaktion). Liefert die Dateinamen.

    Danach lädt es den Umsteiger ÖNACE 2008 → 2025 aus dem Startpaket nach stat.uebergang, falls die Datei
    da ist; sonst steht ein Hinweis in der Liste (kein Abbruch).
    """
    from statagent.klass import umsteiger_einrichten

    angewendet: list[str] = []
    with conn.transaction():
        for datei in sql_dateien(verzeichnis):
            conn.execute(datei.read_text(encoding="utf-8").encode())
            angewendet.append(datei.name)
        angewendet.append(umsteiger_einrichten(conn))
    return angewendet


def lieferungen(conn: Verbindung) -> list[str]:
    """Geladene Lieferungen laut roh.ladeprotokoll, aufsteigend."""
    zeilen = conn.execute("SELECT lieferung FROM roh.ladeprotokoll ORDER BY lieferung").fetchall()
    return [str(z["lieferung"]) for z in zeilen]
