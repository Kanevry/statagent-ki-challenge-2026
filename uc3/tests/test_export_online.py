"""`uc3 export-online`: stat und meta für den Online-Server, nie roh oder bereinigt."""

from __future__ import annotations

import shutil
import subprocess
import sys
import uuid
from pathlib import Path

import psycopg
import pytest
from psycopg import sql

from statagent.export_online import ExportFehler, exportieren


def test_verbotenes_schema_loescht_datei(tmp_path: Path) -> None:
    """Fängt: Ein Dump mit einer Tabelle aus roh bleibt liegen und könnte auf den Server wandern."""
    ziel = tmp_path / "online.sql"
    falsch = [sys.executable, "-c", "print('CREATE TABLE roh.lieferung (vvh_id text);')"]
    with pytest.raises(ExportFehler, match="roh"):
        exportieren(ziel, "postgresql://u@localhost/x", falsch)
    assert not ziel.exists()


def test_dump_stat_meta_mit_grants_spielt_ein(admin_url: str, test_db: str, tmp_path: Path) -> None:
    """Fängt: roh/bereinigt im Dump, fehlende Leserechte, und einen Dump von pg_dump 18, den PostgreSQL 16
    wegen `SET transaction_timeout` oder `\\restrict` nicht einspielt."""
    if shutil.which("pg_dump") is None or shutil.which("psql") is None:
        pytest.skip("pg_dump oder psql fehlt")
    rolle = f"kic_test_{uuid.uuid4().hex[:8]}"
    ziel = tmp_path / "online.sql"
    erg = exportieren(ziel, test_db, rolle=rolle)
    inhalt = ziel.read_text(encoding="utf-8")
    assert "CREATE TABLE stat.stat_beschaeftigte" in inhalt
    assert "CREATE TABLE meta.regel" in inhalt
    for verboten in ("CREATE TABLE roh.", "COPY roh.", "CREATE TABLE bereinigt.", "COPY bereinigt."):
        assert verboten not in inhalt
    assert f"GRANT SELECT ON ALL TABLES IN SCHEMA stat, meta TO {rolle};" in inhalt
    assert "\nSET transaction_timeout" not in inhalt
    assert erg.tabellen["stat"] > 0 and erg.tabellen["meta"] > 0
    assert len(erg.sha256) == 64

    name = f"statagent_online_{uuid.uuid4().hex[:8]}"
    with psycopg.connect(admin_url, autocommit=True) as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
    url = admin_url.rsplit("/", 1)[0] + f"/{name}"
    try:
        lauf = subprocess.run(
            ["psql", "-X", "-q", "-v", "ON_ERROR_STOP=1", "-f", str(ziel), url],
            capture_output=True,
            text=True,
            timeout=120,
        )
        assert lauf.returncode == 0, lauf.stderr[-2000:]
        with psycopg.connect(url) as conn:
            zeile = conn.execute(
                "SELECT has_table_privilege(%s, 'stat.stat_beschaeftigte', 'SELECT'),"
                " to_regclass('roh.lieferung') IS NULL",
                (rolle,),
            ).fetchone()
        assert zeile == (True, True)
    finally:
        with psycopg.connect(admin_url, autocommit=True) as admin:
            admin.execute(sql.SQL("DROP DATABASE IF EXISTS {} WITH (FORCE)").format(sql.Identifier(name)))
            admin.execute(sql.SQL("DROP ROLE IF EXISTS {}").format(sql.Identifier(rolle)))


def test_ohne_beispiele_leert_nur_die_beispiel_spalten(test_db: str, tmp_path: Path) -> None:
    # Fängt: Beispiel-Kennungen (synthetische VVH_IDs aus meta.rueckfrage.beispiele) landen trotz Schalter auf dem
    # öffentlichen Online-Server, oder der Schalter verschiebt Spalten im COPY-Block (Lead-Entscheid 05.11.).
    if shutil.which("pg_dump") is None:
        pytest.skip("pg_dump nicht installiert")
    with psycopg.connect(test_db) as conn:
        r1 = conn.execute("SELECT beispiele::text, titel FROM meta.rueckfrage WHERE nr = 'R1'").fetchone()
    assert r1 is not None and r1[0] != "[]"
    erg = exportieren(tmp_path / "ohne.sql", test_db, ohne_beispiele=True)
    inhalt = (tmp_path / "ohne.sql").read_text(encoding="utf-8")
    block = inhalt.split("COPY meta.rueckfrage ", 1)[1].split("\n\\.\n", 1)[0]
    zeile_r1 = next(z for z in block.splitlines()[1:] if z.startswith("R1\t"))
    assert r1[0] not in zeile_r1 and "\t[]\t" in zeile_r1 and r1[1] in zeile_r1
    assert erg.geleert.get("meta.rueckfrage", 0) >= 1
