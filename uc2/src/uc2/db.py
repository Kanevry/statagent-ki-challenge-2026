"""PG-Verbindung für UC2: eigene DB `healthpolicy` auf PG 5433 (Tests: `healthpolicy_test`).

Die Verbindung kommt aus den `PG*`-Variablen (lokal 5433, CI 5432); fehlt eine, gelten die
Standardwerte der Challenge (`statistik`/`statistik` auf localhost:5433).
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


def verbinde(dbname: str | None = None, autocommit: bool = False) -> psycopg.Connection[tuple[object, ...]]:
    conninfo = make_conninfo("", **verbindungs_parameter(dbname))
    return psycopg.connect(conninfo, autocommit=autocommit)
