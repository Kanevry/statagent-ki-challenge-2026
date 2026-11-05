from __future__ import annotations

import contextlib
import os
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import psycopg
import pytest

from uc2 import db

FIXTURES = Path(__file__).parent / "fixtures"
TEST_DB = "healthpolicy_test"


@pytest.fixture(autouse=True)
def nur_mock_einbettung(monkeypatch: pytest.MonkeyPatch) -> None:
    """Kein Test lädt je das echte Embedding-Modell."""
    monkeypatch.setenv("UC2_EINBETTUNG", "mock")


@pytest.fixture
def ausgabe_text() -> str:
    """Erfundene Ausgabe im Format von `pdftotext -layout` (9 Seiten, 3 Artikel, 2 Layout-Kopien)."""
    return (FIXTURES / "belege" / "ausgabe_2026-09-01.txt").read_text(encoding="utf-8")


def _in_ci() -> bool:
    return bool(os.environ.get("CI") or os.environ.get("GITLAB_CI"))


def _lege_testdb_an() -> None:
    """Legt `healthpolicy_test` an, verbunden über die DB aus `PGDATABASE` (Standard `statistik`)."""
    verwaltungs_db = os.environ.get("PGDATABASE", "statistik")
    with db.verbinde(verwaltungs_db, autocommit=True) as verwaltung:
        sql = "select 1 from pg_database where datname = %s"
        if verwaltung.execute(sql, (TEST_DB,)).fetchone() is None:
            with contextlib.suppress(psycopg.errors.DuplicateDatabase):  # parallel angelegt
                verwaltung.execute(f'create database "{TEST_DB}"')


@pytest.fixture
def pg_test() -> Iterator[psycopg.Connection[Any]]:
    """Leeres Schema `uc2` in `healthpolicy_test`.

    Ohne erreichbares PG: lokal übersprungen, in CI (`CI`/`GITLAB_CI`) ein Fehler, damit die PG-Tests
    dort nie still ausfallen.
    """
    try:
        _lege_testdb_an()
        verbindung = db.verbinde(TEST_DB)
    except psycopg.OperationalError as fehler:
        if _in_ci():
            pytest.fail(f"PostgreSQL in CI nicht erreichbar: {fehler}")
        pytest.skip(f"PostgreSQL nicht erreichbar: {fehler}")
    with verbindung:
        verbindung.execute("drop schema if exists uc2 cascade")
        verbindung.commit()
        yield verbindung
