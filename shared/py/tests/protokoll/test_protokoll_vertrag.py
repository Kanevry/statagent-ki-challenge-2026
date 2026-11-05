"""JSON-Vertrag Eintrag (#55): Schema-Datei aktuell, Fixture gültig, lies() liefert Eintrag-Objekte."""

import json
import os
import uuid
from pathlib import Path

import jsonschema
import psycopg
import pytest
from plattform.protokoll import SCHEMA_DATEI, Eintrag, ddl_einspielen, lies, schema_text, schreibe

FIXTURE = SCHEMA_DATEI.parent / "fixtures" / "protokoll-eintraege.json"


def test_schema_datei_aktuell_und_fixture_gueltig():
    assert SCHEMA_DATEI.read_text(encoding="utf-8") == schema_text(), (
        "Schema veraltet: uv run python -m plattform.protokoll schema"
    )
    schema = json.loads(SCHEMA_DATEI.read_text(encoding="utf-8"))
    validator = jsonschema.Draft202012Validator(schema, format_checker=jsonschema.FormatChecker())
    eintraege = json.loads(Path(FIXTURE).read_text(encoding="utf-8"))
    assert eintraege
    for eintrag in eintraege:
        validator.validate(eintrag)
        Eintrag.model_validate(eintrag)


def test_lies_liefert_eintraege():
    url = os.environ.get("PLATTFORM_TEST_DATABASE_URL")
    if not url:
        pytest.skip("PLATTFORM_TEST_DATABASE_URL nicht gesetzt: DB-Test braucht eine leere Wegwerf-DB")
    uc = f"t{uuid.uuid4().hex[:8]}"
    with psycopg.connect(url, autocommit=True) as conn:
        ddl_einspielen(conn)
        ddl_einspielen(conn)  # idempotent
        erster = schreibe(conn, {"uc": uc, "akteur": "agent", "name": "regel-agent", "anweisung": "A"})
        zweiter = schreibe(
            conn,
            {
                "uc": uc,
                "akteur": "mensch",
                "name": "Erika Musterfrau",
                "anweisung": "B",
                "status": "abgelehnt",
            },
        )
        alle = lies(conn, uc=uc)
        offen = lies(conn, uc=uc, status="offen")
    assert [e.id for e in alle] == [zweiter, erster]
    assert all(isinstance(e, Eintrag) for e in alle)
    assert [e.anweisung for e in offen] == ["A"]
    schema = json.loads(SCHEMA_DATEI.read_text(encoding="utf-8"))
    for e in alle:
        jsonschema.validate(json.loads(e.model_dump_json()), schema)
