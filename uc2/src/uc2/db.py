"""PG-Verbindung für UC2: eigene DB `healthpolicy` auf PG 5433 (Tests: `healthpolicy_test`).

Reihenfolge: `UC2_DATABASE_URL` (Vertrag E0, `.env.example`) gewinnt; sonst die `PG*`-Variablen (lokal 5433,
CI 5432) mit `UC2_DB`; fehlt etwas, gelten die Standardwerte der Challenge (`statistik`/`statistik` auf
localhost:5433, DB `healthpolicy`). Ein ausdrücklich übergebener DB-Name (Tests, Verwaltung) ersetzt nur den
DB-Namen, Host und Zugang bleiben.
"""

from __future__ import annotations

import os

import psycopg
from psycopg.conninfo import make_conninfo

STANDARD_DB = "healthpolicy"


def verbindungs_parameter(dbname: str | None = None) -> dict[str, str]:
    return {
        "host": os.environ.get("PGHOST", "localhost"),
        "port": os.environ.get("PGPORT", "5433"),
        "user": os.environ.get("PGUSER", "statistik"),
        "password": os.environ.get("PGPASSWORD", "statistik"),
        "dbname": dbname or os.environ.get("UC2_DB", STANDARD_DB),
    }


def conninfo(dbname: str | None = None) -> str:
    url = os.environ.get("UC2_DATABASE_URL")
    if url:
        return make_conninfo(url, dbname=dbname) if dbname else make_conninfo(url)
    return make_conninfo("", **verbindungs_parameter(dbname))


def verbinde(dbname: str | None = None, autocommit: bool = False) -> psycopg.Connection[tuple[object, ...]]:
    return psycopg.connect(conninfo(dbname), autocommit=autocommit)
