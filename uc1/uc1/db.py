"""Verbindung zur Datenbank lotse und Einspielen der DDL aus uc1/db/*.sql."""

from __future__ import annotations

import argparse
from pathlib import Path

import psycopg

from uc1.config import datenbank_url

DDL_DIR = Path(__file__).resolve().parent.parent / "db"


def verbinde(url: str | None = None) -> psycopg.Connection:
    return psycopg.connect(url or datenbank_url())


def ddl_dateien() -> list[Path]:
    return sorted(DDL_DIR.glob("*.sql"))


def init_schema(conn: psycopg.Connection) -> list[str]:
    """Spielt zuerst meta.sql von E0 (meta.protokoll, meta.freigabe), dann uc1/db/*.sql ein. Idempotent."""
    from plattform.protokoll import ddl_einspielen

    ddl_einspielen(conn)
    eingespielt: list[str] = ["plattform/sql/meta.sql"]
    for datei in ddl_dateien():
        conn.execute(datei.read_text(encoding="utf-8"))
        eingespielt.append(datei.name)
    conn.commit()
    return eingespielt


def cli(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="lotse db-init", description="DDL der Datenbank lotse einspielen")
    parser.add_argument("--url", help="Verbindungs-URL (Standard: LOTSE_DATABASE_URL)")
    args = parser.parse_args(argv)
    with verbinde(args.url) as conn:
        for name in init_schema(conn):
            print(f"eingespielt: {name}")
    return 0
