from __future__ import annotations

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


@pytest.fixture
def pg_test() -> Iterator[psycopg.Connection[Any]]:
    """Leere Schema-Lage in `healthpolicy_test`; überspringt ohne erreichbares PG."""
    try:
        with db.verbinde("postgres", autocommit=True) as verwaltung:
            sql = "select 1 from pg_database where datname = %s"
            vorhanden = verwaltung.execute(sql, (TEST_DB,)).fetchone()
            if vorhanden is None:
                verwaltung.execute(f'create database "{TEST_DB}"')
        verbindung = db.verbinde(TEST_DB)
    except psycopg.OperationalError as fehler:
        pytest.skip(f"PostgreSQL nicht erreichbar: {fehler}")
    with verbindung:
        verbindung.execute("drop schema if exists uc2 cascade")
        verbindung.commit()
        yield verbindung
