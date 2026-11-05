"""Antwortform UcAntwort (#96): Schema-Datei aktuell, Fixture gültig, Beleg-Index und Zahlen streng."""

import json
import math

import jsonschema
import pytest
from plattform.antwortform import SCHEMA_DATEI, UcAntwort, schema_text
from pydantic import ValidationError

FIXTURE = SCHEMA_DATEI.parent / "fixtures" / "uc-antwort.json"


def _fixture() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def test_schema_datei_aktuell_und_fixture_gueltig():
    assert SCHEMA_DATEI.read_text(encoding="utf-8") == schema_text(), (
        "Schema veraltet: uv run python -m plattform.antwortform schema"
    )
    antwort = _fixture()
    jsonschema.Draft202012Validator(json.loads(SCHEMA_DATEI.read_text(encoding="utf-8"))).validate(antwort)
    UcAntwort.model_validate(antwort)


def test_zahl_mit_ungueltigem_beleg_index_wird_abgelehnt():
    antwort = _fixture()
    antwort["zahlen"][0]["beleg"] = 1  # nur belege[0] existiert
    with pytest.raises(ValidationError, match="zeigt auf keinen Beleg"):
        UcAntwort.model_validate(antwort)


@pytest.mark.parametrize(
    ("feld", "wert"),
    [
        ("wert", "412.345"),  # würde ohne strict zu 412.345 (Tausenderpunkt als Dezimalpunkt)
        ("wert", True),
        ("wert", math.nan),  # würde sonst als null serialisiert
        ("wert", math.inf),
        ("beleg", "0"),
        ("beleg", True),
    ],
)
def test_zahlen_sind_streng(feld, wert):
    antwort = _fixture()
    antwort["zahlen"][0][feld] = wert
    with pytest.raises(ValidationError):
        UcAntwort.model_validate(antwort)


def test_herkunftsfelder_duerfen_fehlen_uc_nicht():
    antwort = _fixture()
    antwort["belege"] = [{"uc": "uc1", "quelle": "lotse.leistung"}]
    del antwort["zahlen"][0]["einheit"], antwort["modell"], antwort["protokoll_id"]
    gelesen = UcAntwort.model_validate(antwort)
    assert gelesen.belege[0].stand is None and gelesen.zahlen[0].einheit is None

    antwort["belege"] = [{"quelle": "lotse.leistung"}]
    with pytest.raises(ValidationError, match="uc"):
        UcAntwort.model_validate(antwort)
