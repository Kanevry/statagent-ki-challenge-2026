"""Gemeinsame Fixtures: Wegwerf-PostgreSQL mit Fixture-Startpaket und Mini-Lieferungen.

Lokal: `UC3_TEST_ADMIN_URL` oder `postgresql://statistik:statistik@localhost:5433/postgres`.
CI: leerer PostgreSQL-16-Dienst über `PGHOST`/`PGPORT`/`PGUSER`/`PGPASSWORD`.
Es wird nie in eine bestehende Datenbank geschrieben, nur in `statagent_test_<uuid8>` (und Klone davon).
"""

from __future__ import annotations

import csv
import os
import uuid
from collections.abc import Iterator
from pathlib import Path
from urllib.parse import quote, urlsplit, urlunsplit

import psycopg
import pytest
from psycopg import sql

from statagent.db import Verbindung, schema_einrichten, verbinden

FIXTURES = Path(__file__).parent / "fixtures"
LIEFERUNGEN = ("2024-08", "2024-09", "2024-10")
ROH_SPALTEN = "lieferung, vvh_id, person_id, geburtsdatum, geschlecht, beginn, ende, qual, oenace, bundesland"


def _admin_url() -> str:
    explizit = os.environ.get("UC3_TEST_ADMIN_URL")
    if explizit:
        return explizit
    if "PGHOST" in os.environ:
        user = quote(os.environ.get("PGUSER", "statistik"), safe="")
        passwort = quote(os.environ.get("PGPASSWORD", "statistik"), safe="")
        host, port = os.environ["PGHOST"], os.environ.get("PGPORT", "5432")
        return f"postgresql://{user}:{passwort}@{host}:{port}/postgres"
    return "postgresql://statistik:statistik@localhost:5433/postgres"


def _url_fuer(admin_url: str, dbname: str) -> str:
    teile = urlsplit(admin_url)
    return urlunsplit(teile._replace(path=f"/{dbname}"))


def _laden(conn: Verbindung) -> None:
    conn.execute((FIXTURES / "startpaket_schema.sql").read_text(encoding="utf-8").encode())
    conn.execute((FIXTURES / "startpaket_klassifikation.sql").read_text(encoding="utf-8").encode())
    for lieferung in LIEFERUNGEN:
        datei = FIXTURES / f"lieferung_{lieferung}.csv"
        with datei.open(encoding="utf-8", newline="") as f:
            zeilen = list(csv.reader(f, delimiter=";"))[1:]
        with conn.cursor() as cur, cur.copy(f"COPY roh.lieferung ({ROH_SPALTEN}) FROM STDIN") as copy:
            for z in zeilen:
                # Leere Felder kommen wie im Startpaket als NULL an.
                copy.write_row([lieferung, *(feld or None for feld in z)])
        conn.execute(
            "INSERT INTO roh.ladeprotokoll (lieferung, datei, zeilen) VALUES (%s, %s, %s)",
            (lieferung, datei.name, len(zeilen)),
        )


@pytest.fixture(scope="session")
def admin_url() -> str:
    url = _admin_url()
    try:
        psycopg.connect(url, connect_timeout=5).close()
    except psycopg.OperationalError as fehler:
        pytest.skip(f"kein PostgreSQL-Server erreichbar: {type(fehler).__name__}")
    return url


@pytest.fixture(scope="session")
def test_db(admin_url: str) -> Iterator[str]:
    """URL einer Wegwerf-Datenbank mit Fixture-Startpaket, Lieferungen und eingerichtetem Schema."""
    name = f"statagent_test_{uuid.uuid4().hex[:8]}"
    with psycopg.connect(admin_url, autocommit=True) as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
    url = _url_fuer(admin_url, name)
    try:
        with verbinden(url) as conn:
            _laden(conn)
            schema_einrichten(conn)
            conn.commit()
        yield url
    finally:
        with psycopg.connect(admin_url, autocommit=True) as admin:
            admin.execute(sql.SQL("DROP DATABASE IF EXISTS {} WITH (FORCE)").format(sql.Identifier(name)))


@pytest.fixture
def arbeits_db(admin_url: str, test_db: str) -> Iterator[str]:
    """Frischer Klon von `test_db` je Test, damit Läufe und Freigaben sich nicht beeinflussen."""
    vorlage = urlsplit(test_db).path.lstrip("/")
    klon = f"{vorlage}_{uuid.uuid4().hex[:6]}"
    with psycopg.connect(admin_url, autocommit=True) as admin:
        admin.execute(
            sql.SQL("CREATE DATABASE {} TEMPLATE {}").format(sql.Identifier(klon), sql.Identifier(vorlage))
        )
    try:
        yield _url_fuer(admin_url, klon)
    finally:
        with psycopg.connect(admin_url, autocommit=True) as admin:
            admin.execute(sql.SQL("DROP DATABASE IF EXISTS {} WITH (FORCE)").format(sql.Identifier(klon)))


@pytest.fixture
def conn(arbeits_db: str) -> Iterator[Verbindung]:
    verbindung = verbinden(arbeits_db)
    try:
        yield verbindung
    finally:
        verbindung.close()
