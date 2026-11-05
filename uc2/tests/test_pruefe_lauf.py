"""Oracle `pruefe_lauf.py` (#44): grün auf einem mock-Lauf, rot auf einem verfälschten Ereignis."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import psycopg
import pytest
from psycopg.types.json import Jsonb

from uc2.verhandlung.belege import FixtureQuelle
from uc2.verhandlung.fall import lade_fall
from uc2.verhandlung.lauf import Laufoptionen, Verhandlung

sys.path.insert(0, str(Path(__file__).parent))
import pruefe_lauf  # noqa: E402  (Prüfskript ist kein Paket und importiert uc2 nicht)

TEST_DB = "healthpolicy_test"


@pytest.fixture(autouse=True)
def protokoll_im_tmp(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("PLATTFORM_PROTOKOLL", str(tmp_path / "modellaufrufe.jsonl"))
    monkeypatch.delenv("UC2_MOCK_KAPUTT", raising=False)


def _mock_lauf(verbindung: psycopg.Connection[Any]) -> int:
    optionen = Laufoptionen(provider="mock", quelle=FixtureQuelle())
    return Verhandlung(verbindung, lade_fall("wartezeiten"), optionen).fuehre_aus()


def _pruefe(fall_id: int, capsys: pytest.CaptureFixture[str]) -> tuple[int, dict[str, Any]]:
    capsys.readouterr()
    code = pruefe_lauf.main(["--fall", str(fall_id), "--db", TEST_DB, "--json"])
    return code, json.loads(capsys.readouterr().out)


def test_eigenes_zahlenmuster() -> None:
    funde = pruefe_lauf.zahlen_mit_einheit(
        "−22,24 % Wartezeit, 1.234,5 Mio EUR, ab 2030, 300 Stellen, 3 Ärzte"
    )
    assert funde == [("22,24 %", 22.24), ("1.234,5 Mio", 1234.5), ("300 Stellen", 300.0)]


def test_mock_lauf_gruen_und_verfaelscht_rot(
    pg_test: psycopg.Connection[Any], capsys: pytest.CaptureFixture[str]
) -> None:
    fall_id = _mock_lauf(pg_test)
    code, bericht = _pruefe(fall_id, capsys)
    assert code == 0, bericht
    assert {p["pruefung"] for p in bericht["pruefungen"]} == {
        "teilnahme", "runden", "schema", "zahlen", "experte", "belege", "protokoll",
    }  # fmt: skip

    # Verfälschen: ein Zug aus Runde 2 ohne bezug_auf und mit einer unmarkierten Zahl in der Begründung.
    seq, daten = pg_test.execute(
        "select seq, daten from uc2.ereignis "
        "where fall_id = %s and art = 'zug' and runde = 2 order by seq limit 1",
        (fall_id,),
    ).fetchone() or (None, None)
    assert seq is not None and daten is not None
    daten["zug"]["bezug_auf"] = []
    daten["zug"]["themen"][0]["begruendung"] += " Dazu kommen 777 Tage."
    pg_test.execute(
        "update uc2.ereignis set daten = %s where fall_id = %s and seq = %s", (Jsonb(daten), fall_id, seq)
    )
    pg_test.commit()

    code, bericht = _pruefe(fall_id, capsys)
    assert code == 1
    rot = {p["pruefung"]: p["verstoesse"] for p in bericht["pruefungen"] if not p["ok"]}
    assert set(rot) == {"runden", "zahlen"}
    assert any("bezug_auf" in v for v in rot["runden"])
    assert any("777 Tage" in v for v in rot["zahlen"])
