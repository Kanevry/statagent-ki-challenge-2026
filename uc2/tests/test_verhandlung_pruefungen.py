"""Prüfungen nach jedem Zug (#44): je benennbarem Fehler ein Test. Alle Texte und Belege sind erfunden."""

from __future__ import annotations

from datetime import date
from typing import Any

from uc2.verhandlung.belege import Beleg
from uc2.verhandlung.pruefungen import (
    pruefe,
    ungueltige_belege,
    validiere_zug,
    zahlen_im_text,
    zahlen_ohne_beleg,
    zitate,
)

BID = "0123456789ab-001-01"
BELEG = Beleg(
    beleg_id=BID,
    medium="Musterblatt",
    datum=date(2026, 9, 1),
    titel="Erfundener Titel",
    text=(
        "Die Kasse will im kommenden Jahr zusätzliche fachärztliche Stellen in ländlichen Bezirken "
        "ausschreiben."
    ),
)


def _zug(begruendung: str, zahlen: list[dict[str, Any]] | None = None, **thema: Any) -> dict[str, Any]:
    return {
        "themen": [
            {
                "thema": "kassenstellen",
                "haltung": 1,
                "begruendung": begruendung,
                "beleg_ids": [BID],
                "bedingungen": [],
                "zugestaendnis": None,
                **thema,
            }
        ],
        "bezug_auf": [],
        "zahlen": zahlen or [],
    }


def test_zahlenmuster_findet_einheiten_und_laesst_jahre_aus() -> None:
    funde = zahlen_im_text(
        "Bis 2030 Tage sinkt es um 22,24 % und es fehlen 300 Stellen, 2050 Tage später 1,5 Mrd"
    )
    assert funde == [("22,24 %", 22.24), ("300 Stellen", 300.0), ("2050 Tage", 2050.0), ("1,5 Mrd", 1.5)]


def test_zahl_ohne_beleg_nur_wenn_nicht_in_zahlen() -> None:
    zug = _zug(
        "Wartezeit −22,24 % laut Experte, dazu fehlen 300 Stellen.",
        [{"wert": -22.24, "einheit": "%", "quelle": "experte"}],
    )
    befunde = zahlen_ohne_beleg(zug)
    assert [(b.art, b.daten["fund"]) for b in befunde] == [("zahl_ohne_beleg", "300 Stellen")]


def test_zitat_ab_acht_woertern_nicht_bei_sieben() -> None:
    # sieben Wörter am Stück aus dem Beleg: „zusätzliche … ausschreiben“
    sieben = _zug(
        "Wie berichtet: zusätzliche fachärztliche Stellen in ländlichen Bezirken ausschreiben, sagt sie."
    )
    assert zitate(sieben, [BELEG]) == []
    # genau acht: „kommenden Jahr … Bezirken“
    acht = _zug("Geplant: kommenden Jahr zusätzliche fachärztliche Stellen in ländlichen Bezirken, heißt es.")
    befunde = zitate(acht, [BELEG])
    assert [b.art for b in befunde] == ["zitat"] and befunde[0].daten["beleg_id"] == BID


def test_beleg_ungueltig_in_thema_und_in_zahlen_quelle() -> None:
    fremd = "fedcba987654-002"
    zug = _zug(
        "Ohne Zahl.", [{"wert": 3, "einheit": "%", "quelle": fremd}], beleg_ids=[BID, "aaaaaaaaaaaa-003-01"]
    )
    befunde = ungueltige_belege(zug, {BID})
    assert [b.daten["beleg_id"] for b in befunde] == ["aaaaaaaaaaaa-003-01", fremd]


def test_nan_und_doppeltes_thema_sind_ungueltig() -> None:
    zug = _zug("Text.", [{"wert": float("nan"), "einheit": "%", "quelle": "experte"}])
    zug["themen"].append({**zug["themen"][0], "haltung": -2})
    fehler = validiere_zug(zug, ["kassenstellen"], 1, "sv", ["sv", "aerztekammer"])
    assert any("endliche Zahl" in f for f in fehler)
    assert any("mehrfach" in f for f in fehler)


def test_ab_runde_zwei_braucht_es_bezug_und_thema_aus_dem_auftrag() -> None:
    zug = _zug("Text.", thema="unbekannt")
    fehler = validiere_zug(zug, ["kassenstellen"], 2, "sv", ["sv", "aerztekammer"])
    assert any("nicht im Auftrag" in f for f in fehler)
    assert any("bezug_auf" in f for f in fehler)


def test_zahl_widerspruch_gegen_experte_auf_005() -> None:
    zug = _zug(
        "Ohne Zahl im Text.",
        [
            {"wert": -22.2, "einheit": "%", "quelle": "experte"},
            {"wert": -21.0, "einheit": "%", "quelle": "experte"},
        ],
    )
    befunde = pruefe(zug, [BELEG], [-22.24, 0.21])
    assert [(b.art, b.daten["wert"]) for b in befunde] == [("zahl_widerspruch", -21.0)]
