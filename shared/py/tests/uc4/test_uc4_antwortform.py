"""Antwortform UcAntwort (#96): Schema-Datei aktuell, Fixture gültig, Beleg-Index geprüft."""

import json

import jsonschema
import pytest
from plattform.antwortform import SCHEMA_DATEI, UcAntwort, schema_text
from pydantic import ValidationError

FIXTURE = SCHEMA_DATEI.parent / "fixtures" / "uc-antwort.json"


def test_schema_datei_aktuell_und_fixture_gueltig():
    assert SCHEMA_DATEI.read_text(encoding="utf-8") == schema_text(), (
        "Schema veraltet: uv run python -m plattform.antwortform schema"
    )
    antwort = json.loads(FIXTURE.read_text(encoding="utf-8"))
    jsonschema.Draft202012Validator(json.loads(SCHEMA_DATEI.read_text(encoding="utf-8"))).validate(antwort)
    UcAntwort.model_validate(antwort)


def test_zahl_mit_ungueltigem_beleg_index_wird_abgelehnt():
    antwort = json.loads(FIXTURE.read_text(encoding="utf-8"))
    antwort["zahlen"][0]["beleg"] = 1  # nur belege[0] existiert
    with pytest.raises(ValidationError, match="zeigt auf keinen Beleg"):
        UcAntwort.model_validate(antwort)
