"""Oracle `pruefe_lauf.py` (#44): grün auf einem mock-Lauf, rot auf einem verfälschten Ereignis."""

from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path
from typing import Any

import psycopg
import pytest
from psycopg.types.json import Jsonb

from uc2.belege.extraktion import extrahiere
from uc2.belege.index import indexiere
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


@pytest.fixture
def extrakt_ddl(pg_test: psycopg.Connection[Any], tmp_path: Path, ausgabe_text: str) -> None:
    """Echtes DDL der Belege-Tabellen (`uc2.quelle`, `uc2.artikel`, `uc2.abschnitt`) über einen Probe-Index;
    danach sind die Tabellen leer, die Tests legen ihre erfundenen Zeilen selbst an."""
    quelle = tmp_path / "presse"
    quelle.mkdir()
    (quelle / "Pressespiegel vom 01.09.2026.pdf").write_text(ausgabe_text, encoding="utf-8")
    extrahiere(
        quelle, tmp_path / "extrakt", ab=date(2026, 1, 1), prozesse=1, leser=lambda p: p.read_text("utf-8")
    )
    indexiere(tmp_path / "extrakt", pg_test)
    pg_test.execute("truncate uc2.abschnitt, uc2.artikel, uc2.quelle cascade")
    pg_test.commit()


def _mock_lauf(verbindung: psycopg.Connection[Any]) -> int:
    optionen = Laufoptionen(provider="mock", quelle=FixtureQuelle())
    return Verhandlung(verbindung, lade_fall("wartezeiten"), optionen).fuehre_aus()


def _pruefe(fall_id: int, capsys: pytest.CaptureFixture[str]) -> tuple[int, dict[str, Any]]:
    capsys.readouterr()
    code = pruefe_lauf.main(["--fall", str(fall_id), "--db", TEST_DB, "--json"])
    return code, json.loads(capsys.readouterr().out)


def test_eigenes_zahlenmuster() -> None:
    funde = pruefe_lauf.zahlen_mit_einheit(
        "−22,24 % Wartezeit, 1.234,5 Mio EUR, ab 2030, 300 Stellen, 3 Ärzte, 12.000 Stellen, 3,5 %, 2030 Tage"
    )
    assert funde == [
        ("22,24 %", 22.24),
        ("1.234,5 Mio", 1234.5),
        ("300 Stellen", 300.0),
        ("12.000 Stellen", 12000.0),
        ("3,5 %", 3.5),
    ]


def test_ergebniswerte_ohne_ziel_und_eingaben() -> None:
    experte = {
        "ergebnis": {
            "zieljahr": 5,
            "ziel": {"wartezeit_aenderung_prozent_hoechstens": -20.0},
            "kennzahlen": {"wartezeit_aenderung_prozent": {"modus": -14.0, "min": -16.5, "max": -11.2}},
            "massnahmen": [{"umfang": 300, "wirkung_prozent": -9.5, "mehrkosten_mio_eur": 41.0}],
            "jahrespfad": [{"jahr": 1, "wartezeit_aenderung_prozent": -3.3}],
            "annahmen": [{"min": 2.0, "modus": 3.0, "max": 4.0}],
        }
    }
    assert sorted(pruefe_lauf.ergebniswerte(experte)) == [-16.5, -14.0, -11.2, -9.5, -3.3, 41.0]


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


def _erster_zug(
    pg_test: psycopg.Connection[Any], fall_id: int, runde: int
) -> tuple[int, str, dict[str, Any]]:
    zeile = pg_test.execute(
        "select seq, akteur, daten from uc2.ereignis "
        "where fall_id = %s and art = 'zug' and runde = %s order by seq limit 1",
        (fall_id, runde),
    ).fetchone()
    assert zeile is not None
    return zeile[0], zeile[1], zeile[2]


def test_ziel_als_experten_zahl_und_beleg_zahl_ohne_text_werden_rot(
    pg_test: psycopg.Connection[Any], capsys: pytest.CaptureFixture[str]
) -> None:
    """Review !47: Ziel (−20) mit Quelle experte; 999 Mio EUR mit einer Beleg-Quelle ohne diese Zahl."""
    fall_id = _mock_lauf(pg_test)
    zeile = pg_test.execute(
        "select daten from uc2.ereignis where fall_id = %s and art = 'experte'", (fall_id,)
    ).fetchone()
    assert zeile is not None
    ziel = zeile[0]["ergebnis"]["ziel"]["wartezeit_aenderung_prozent_hoechstens"]
    # Das Ziel steht im Ereignis (früher genügte das), ist aber kein Ergebniswert des Rechenmodells.
    assert not any(pruefe_lauf.gleich(ziel, w) for w in pruefe_lauf.ergebniswerte(zeile[0]))
    seq, akteur, daten = _erster_zug(pg_test, fall_id, 1)
    belege = pg_test.execute(
        "select daten from uc2.ereignis where fall_id = %s and art = 'belege' and runde = 1 and akteur = %s",
        (fall_id, akteur),
    ).fetchone()
    assert belege is not None and belege[0]["belege"]
    bid = belege[0]["belege"][0]["beleg_id"]
    daten["zug"]["zahlen"] += [
        {"wert": ziel, "einheit": "%", "quelle": "experte"},
        {"wert": 999, "einheit": "Mio EUR", "quelle": bid},
    ]
    pg_test.execute(
        "update uc2.ereignis set daten = %s where fall_id = %s and seq = %s", (Jsonb(daten), fall_id, seq)
    )
    pg_test.commit()

    code, bericht = _pruefe(fall_id, capsys)
    assert code == 1
    rot = {p["pruefung"]: p["verstoesse"] for p in bericht["pruefungen"] if not p["ok"]}
    assert set(rot) == {"experte", "belege"}
    assert any(f"Experten-Zahl {float(ziel)}" in v for v in rot["experte"])
    assert any("999.0 steht nicht im Zitat" in v for v in rot["belege"])


def test_lauf_markiert_ziel_als_widerspruch_und_orakel_bleibt_gruen(
    pg_test: psycopg.Connection[Any], capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Laufzeit und Orakel lesen dieselbe Regel: der Lauf markiert, das Orakel akzeptiert die Markierung."""
    from uc2.modelle import szenario

    original = szenario._akteurszug

    def mit_ziel(k: dict[str, Any]) -> dict[str, Any]:
        zug = original(k)
        if k["akteur"]["id"] == sorted(k["teilnehmer"])[0] and int(k["runde"]) == 1:
            zug["zahlen"] = [*zug["zahlen"], {"wert": -20, "einheit": "%", "quelle": "experte"}]
        return zug

    monkeypatch.setattr(szenario, "_akteurszug", mit_ziel)
    fall_id = _mock_lauf(pg_test)
    widerspruch = pg_test.execute(
        "select runde, daten from uc2.ereignis where fall_id = %s and art = 'zahl_widerspruch'", (fall_id,)
    ).fetchall()
    assert [(r, d["wert"]) for r, d in widerspruch] == [(1, -20.0)]
    code, bericht = _pruefe(fall_id, capsys)
    assert code == 0, bericht


def _lege_abschnitt_an(pg_test: psycopg.Connection[Any], abschnitt_id: str, text: str) -> None:
    """Legt `uc2.abschnitt` an (echtes DDL über einen Probe-Index) und dazu einen Abschnitt mit dieser ID."""
    artikel_id, nr = abschnitt_id.rsplit("-", 1)
    pg_test.execute(
        "insert into uc2.quelle (md5, datei, ausgabedatum, seiten, uebersprungen, grund) "
        "values ('0' || %s, 'erfunden.pdf', '2026-09-01', 1, false, null) on conflict (md5) do nothing",
        (artikel_id[:12],),
    )
    pg_test.execute(
        "insert into uc2.artikel (artikel_id, quelle_md5, pdf_seite, artikeldatum, medium, titel) "
        "values (%s, '0' || %s, 1, '2026-09-01', 'Erfundene Zeitung', 'Erfundener Titel') "
        "on conflict (artikel_id) do nothing",
        (artikel_id, artikel_id[:12]),
    )
    pg_test.execute(
        "insert into uc2.abschnitt (abschnitt_id, artikel_id, nr, text, text_hash) "
        "values (%s, %s, %s, %s, %s)",
        (abschnitt_id, artikel_id, int(nr), text, f"hash-{abschnitt_id}"),
    )
    pg_test.commit()


def test_beleg_zahl_im_abschnitt_aber_ausserhalb_des_zitats_gruen_sonst_rot(
    pg_test: psycopg.Connection[Any],
    capsys: pytest.CaptureFixture[str],
    extrakt_ddl: None,
) -> None:
    """#149: Das Orakel prüft gegen den vollen Abschnitt aus PG (wie die Laufzeit gegen `text_modell`), nicht
    gegen das `zitat` (höchstens 300 Zeichen). Eine Zahl, die nirgends im Abschnitt steht, bleibt rot."""
    fall_id = _mock_lauf(pg_test)
    seq, akteur, daten = _erster_zug(pg_test, fall_id, 1)
    belege = pg_test.execute(
        "select daten from uc2.ereignis where fall_id = %s and art = 'belege' and runde = 1 and akteur = %s",
        (fall_id, akteur),
    ).fetchone()
    assert belege is not None
    chip = belege[0]["belege"][0]
    bid = chip["beleg_id"]
    assert "4.321" not in chip["zitat"] and "777" not in chip["zitat"]
    _lege_abschnitt_an(pg_test, bid, chip["zitat"] + " Weiter hinten stehen 4.321 Fälle in der Statistik.")
    daten["zug"]["zahlen"] += [{"wert": 4321, "einheit": "Mio EUR", "quelle": bid}]
    pg_test.execute(
        "update uc2.ereignis set daten = %s where fall_id = %s and seq = %s", (Jsonb(daten), fall_id, seq)
    )
    pg_test.commit()

    code, bericht = _pruefe(fall_id, capsys)
    assert code == 0, bericht

    # Eine Zahl, die weder im Zitat noch im Abschnitt steht, wird gemeldet (mit Bezug „Abschnitt“).
    daten["zug"]["zahlen"] += [{"wert": 777, "einheit": "Mio EUR", "quelle": bid}]
    pg_test.execute(
        "update uc2.ereignis set daten = %s where fall_id = %s and seq = %s", (Jsonb(daten), fall_id, seq)
    )
    pg_test.commit()
    code, bericht = _pruefe(fall_id, capsys)
    assert code == 1
    rot = {p["pruefung"]: p["verstoesse"] for p in bericht["pruefungen"] if not p["ok"]}
    assert set(rot) == {"belege"}
    assert len(rot["belege"]) == 1
    assert f"777.0 steht nicht im Abschnitt von {bid}" in rot["belege"][0]
    assert "nicht in PG" not in rot["belege"][0]


def test_lade_abschnitte_artikel_id_umfasst_alle_abschnitte_und_fehlende_fehlen(
    pg_test: psycopg.Connection[Any], extrakt_ddl: None
) -> None:
    _lege_abschnitt_an(pg_test, "aaaaaaaaaaaa-001-01", "Erster Teil mit 12 Fällen.")
    _lege_abschnitt_an(pg_test, "aaaaaaaaaaaa-001-02", "Zweiter Teil mit 34 Fällen.")
    _lege_abschnitt_an(pg_test, "bbbbbbbbbbbb-002-01", "Anderer Artikel.")
    texte = pruefe_lauf.lade_abschnitte(
        pg_test, {"aaaaaaaaaaaa-001-02", "aaaaaaaaaaaa-001", "cccccccccccc-003-01"}
    )
    assert texte == {
        "aaaaaaaaaaaa-001-02": "Zweiter Teil mit 34 Fällen.",
        "aaaaaaaaaaaa-001": "Erster Teil mit 12 Fällen.\nZweiter Teil mit 34 Fällen.",
    }
    assert pruefe_lauf.lade_abschnitte(pg_test, set()) == {}


def test_abschnitt_nicht_in_pg_faellt_auf_zitat_zurueck_und_sagt_es(
    pg_test: psycopg.Connection[Any], capsys: pytest.CaptureFixture[str]
) -> None:
    """Fixture-Belege (mock-Lauf) stehen nicht in `uc2.abschnitt`: Zitat als Bezug, Meldung nennt es."""
    fall_id = _mock_lauf(pg_test)
    seq, akteur, daten = _erster_zug(pg_test, fall_id, 1)
    belege = pg_test.execute(
        "select daten from uc2.ereignis where fall_id = %s and art = 'belege' and runde = 1 and akteur = %s",
        (fall_id, akteur),
    ).fetchone()
    assert belege is not None
    bid = belege[0]["belege"][0]["beleg_id"]
    daten["zug"]["zahlen"] += [{"wert": 999, "einheit": "Mio EUR", "quelle": bid}]
    pg_test.execute(
        "update uc2.ereignis set daten = %s where fall_id = %s and seq = %s", (Jsonb(daten), fall_id, seq)
    )
    pg_test.commit()
    code, bericht = _pruefe(fall_id, capsys)
    assert code == 1
    rot = {p["pruefung"]: p["verstoesse"] for p in bericht["pruefungen"] if not p["ok"]}
    assert any("steht nicht im Zitat" in v and "Abschnitt nicht in PG, nur Zitat" in v for v in rot["belege"])
