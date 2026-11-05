"""Online-Schutz vor POST und echten Modellen (#137): Modelltexte maskiert, Zitate gesperrt, Frage geprüft.

Alle Namen, Kennungen und Adressen sind erfunden.
"""

from __future__ import annotations

import json
from dataclasses import replace
from datetime import date
from pathlib import Path
from typing import Any

import psycopg
import pytest
from fastapi.testclient import TestClient

from uc2 import db
from uc2.akteure.laden import lade_akteure
from uc2.api import erstelle_app
from uc2.api.start import Lauf, Startauftrag
from uc2.belege.namen import Namenseintrag, Namensliste, maskiere_modelltext
from uc2.verhandlung import lauf as lauf_modul
from uc2.verhandlung.belege import Beleg, FixtureQuelle
from uc2.verhandlung.bericht import bericht
from uc2.verhandlung.cli import FRAGE_PERSONENDATEN, FrageFehler, pruefe_frage
from uc2.verhandlung.fall import lade_fall
from uc2.verhandlung.lauf import Laufoptionen, Verhandlung, Zugergebnis
from uc2.verhandlung.pruefungen import sperre_zitate, zitate
from uc2.verhandlung.schutz import SchutzFehler, lade_schutz
from uc2.verhandlung.speicher import lies_ereignisse, lies_fall

TEST_DB = "healthpolicy_test"
LISTE = Namensliste(
    (
        Namenseintrag("Felix Probst"),
        Namenseintrag("Maria Beispiel"),
        Namenseintrag("Haberl"),
        Namenseintrag("Betroffene"),  # Allgemeinwort, wie es die Sammlung als Nachname aufnimmt
        Namenseintrag("Wartezeit"),
    )
)
NAMEN = ("Felix", "Probst", "Maria Beispiel", "Haberl")
ZUSATZ = " Das sagt Dr. Felix Probst, und Maria Beispiel fordert mehr Stellen."
DEMO_FRAGEN = (
    "Wie können die Wartezeiten auf Facharzttermine innerhalb von fünf Jahren um 20 % reduziert werden, ohne "
    "die Gesundheitsausgaben um mehr als 5 % zu erhöhen?",
    "Wie viele Menschen arbeiten im März 2025 in Wien im Gesundheitswesen?",
)


# --- 1. Namen in Modelltexten ----------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("text", "erwartet"),
    [
        (
            "Das sagt Dr. Felix Probst, und Maria Beispiel fordert mehr Stellen.",
            "Das sagt eine Person, und eine Person fordert mehr Stellen.",
        ),
        ("Felix Probst warnt. Probst bleibt dabei.", "Eine Person warnt. Eine Person bleibt dabei."),
        ("Wie Haberl sagte, fehlt das Geld.", "Wie eine Person sagte, fehlt das Geld."),
        (
            "Gesundheitsministerin Probst will mehr Stellen.",
            "Eine Vertreterin des Gesundheitsministeriums will mehr Stellen.",
        ),
    ],
)
def test_namen_im_modelltext_werden_zur_rolle(text: str, erwartet: str) -> None:
    assert maskiere_modelltext(text, LISTE) == erwartet


@pytest.mark.parametrize(
    "text",
    [
        "Für Betroffene ändert sich wenig, weil Betroffene länger warten.",
        "Die Betroffenen warten auf Termine.",
        "Der Experte rechnet mit −22,24 % Wartezeit bei 0,21 % Mehrkosten.",
        "Haberl sagte nichts.",  # Einzelwort am Satzanfang: Grenze, siehe maskiere_modelltext
        "Das Thema stützt unser Ziel: Kassenstellen durch bessere Honorare attraktiv machen.",
        "Wahrung von: keine Kürzung der Kassenstellen. Wir gehen auf die Position von sv ein.",
        "Die Ärztekammer fordert 300 zusätzliche Stellen, die Sozialversicherung prüft die Kosten.",
    ],
)
def test_normale_saetze_bleiben_unveraendert(text: str) -> None:
    assert maskiere_modelltext(text, LISTE) == text


def test_lauf_ohne_namensliste_mit_echtem_provider_bricht_ab(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("UC2_NAMEN_OHNE_LISTE", raising=False)
    monkeypatch.delenv("UC2_NAMENSLISTE", raising=False)
    with pytest.raises(SchutzFehler, match="Namensliste"):
        lade_schutz("azure")
    assert len(lade_schutz("mock").namen) == 0  # mock: Muster reichen


# --- 2. Zitat-Sperre -------------------------------------------------------------------------------------

BELEG = Beleg(
    beleg_id="abcdefabcdef-001-01",
    medium="Testblatt",
    datum=date(2026, 9, 1),
    titel="Erfundener Titel",
    text_modell="Die Kasse will im kommenden Jahr genau vierzig neue Stellen für Fachärzte im Land schaffen.",
)


def _zug(begruendung: str) -> dict[str, Any]:
    return {
        "themen": [
            {
                "thema": "stellen",
                "haltung": 1,
                "begruendung": begruendung,
                "beleg_ids": [BELEG.beleg_id],
                "bedingungen": [],
                "zugestaendnis": None,
            }
        ],
        "bezug_auf": [],
        "zahlen": [],
    }


def test_zitat_ab_acht_woertern_wird_vor_dem_speichern_gesperrt() -> None:
    zug = _zug("Wir stützen das: will im kommenden Jahr genau vierzig neue Stellen für Fachärzte. Gut so.")
    assert [b.art for b in zitate(zug, [BELEG])] == ["zitat"]  # Hinweis bleibt
    gesperrt = sperre_zitate(zug, [BELEG])
    assert gesperrt["themen"][0]["begruendung"] == "Wir stützen das: [Zitat]. Gut so."
    assert zug["themen"][0]["begruendung"].startswith("Wir stützen das: will")  # Original unverändert


def test_unter_acht_woertern_bleibt_die_begruendung() -> None:
    zug = _zug("Wir stützen das: genau vierzig neue Stellen für Fachärzte.")
    assert zitate(zug, [BELEG]) == []
    assert sperre_zitate(zug, [BELEG]) == zug


# --- 3. Freitext-Frage -----------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "frage",
    [
        "Wie lange wartet PERSON_ID 4711 auf einen Termin?",
        "Wie lange wartet die Person 123456789 auf einen Termin?",
        "Wartet die Versicherte 1234 010180 länger?",
        "Wartet eine Frau, geboren am 01.02.1980, länger?",
        "Welche Wartezeit hat Geburtsdatum 3.4.1975?",
        "Bitte Antwort an maria.beispiel@example.org senden.",
    ],
)
def test_frage_mit_kennung_geburtsdatum_oder_email_wird_abgelehnt(frage: str) -> None:
    with pytest.raises(FrageFehler) as fehler:
        pruefe_frage(frage)
    assert str(fehler.value) == FRAGE_PERSONENDATEN


def test_namen_in_der_frage_werden_maskiert() -> None:
    assert pruefe_frage("Was sagt Dr. Felix Probst zu den Wartezeiten?") == (
        "Was sagt eine Person zu den Wartezeiten?"
    )
    assert pruefe_frage("Was meint Maria Beispiel dazu?", LISTE) == "Was meint eine Person dazu?"


@pytest.mark.parametrize("frage", DEMO_FRAGEN)
def test_demo_fragen_bleiben_unveraendert(frage: str) -> None:
    assert pruefe_frage(frage, LISTE) == frage


# --- Lauf, Bericht, SSE ----------------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def protokoll_im_tmp(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("PLATTFORM_PROTOKOLL", str(tmp_path / "modellaufrufe.jsonl"))
    monkeypatch.delenv("UC2_MOCK_KAPUTT", raising=False)
    monkeypatch.delenv("KIC_ONLINE", raising=False)
    monkeypatch.delenv("KIC_ONLINE_LESEND", raising=False)


def _verbinde() -> psycopg.Connection[Any]:
    return db.verbinde(TEST_DB, autocommit=True)


def _kein_start(auftrag: Startauftrag) -> Lauf:
    raise AssertionError(f"kein Start erwartet: {auftrag.fall}")


def _lauf_mit_namen_und_zitat(
    verbindung: psycopg.Connection[Any], monkeypatch: pytest.MonkeyPatch
) -> tuple[int, str]:
    """mock-Lauf; der erste Zug in Runde 1 nennt zwei Namen und übernimmt neun Wörter aus einem Beleg."""
    fall = replace(lade_fall("wartezeiten"), frage="Was sagt Dr. Felix Probst zu den Wartezeiten?")
    quelle = FixtureQuelle()
    akteure = {a.id: a for a in lade_akteure()}
    echt = lauf_modul.fuehre_zug_aus
    uebernahme: list[str] = []

    def mit_namen(*args: Any, **kw: Any) -> Zugergebnis:
        erg = echt(*args, **kw)
        if erg.zug is None or kw["runde"] != 1 or uebernahme:
            return erg
        beleg = quelle.belege_fuer(akteure[kw["akteur"]], fall.frage, 1, fall.stichtag)[0]
        uebernahme.append(" ".join(beleg.text.split()[:9]))
        thema = erg.zug["themen"][0]
        thema["begruendung"] += f"{ZUSATZ} Laut Beleg: {uebernahme[0]}"
        return erg

    monkeypatch.setattr(lauf_modul, "fuehre_zug_aus", mit_namen)
    optionen = Laufoptionen(provider="mock", quelle=quelle, namen=LISTE)
    return Verhandlung(verbindung, fall, optionen).fuehre_aus(), uebernahme[0]


def test_namen_und_zitat_erscheinen_weder_in_ereignis_noch_bericht_noch_sse(
    pg_test: psycopg.Connection[Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    fall_id, uebernahme = _lauf_mit_namen_und_zitat(pg_test, monkeypatch)
    ereignisse = lies_ereignisse(pg_test, fall_id)
    zug = next(e for e in ereignisse if e["art"] == "zug")["daten"]["zug"]
    begruendung = zug["themen"][0]["begruendung"]
    assert begruendung.endswith(
        "Das sagt eine Person, und eine Person fordert mehr Stellen. Laut Beleg: [Zitat]"
    )
    assert any(e["art"] == "zitat" for e in ereignisse)  # Hinweis bleibt
    fall = lies_fall(pg_test, fall_id)
    assert fall is not None and fall["frage"] == "Was sagt eine Person zu den Wartezeiten?"
    positionen = pg_test.execute(
        "select string_agg(begruendung, ' ') from uc2.position where fall_id = %s", (fall_id,)
    ).fetchone()
    assert positionen is not None

    with TestClient(erstelle_app(starter=_kein_start, verbinde=_verbinde)) as c:
        with c.stream("GET", f"/faelle/{fall_id}/ereignisse") as antwort:
            sse = "".join(antwort.iter_text())
        bericht_api = c.get(f"/faelle/{fall_id}").text
    texte = {
        "ereignisse": json.dumps([e["daten"] for e in ereignisse], ensure_ascii=False),
        "bericht": json.dumps(bericht(pg_test, fall_id), ensure_ascii=False, default=str),
        "positionen": str(positionen[0]),
        "sse": sse,
        "bericht_api": bericht_api,
    }
    for ort, text in texte.items():
        assert "eine Person" in text and "[Zitat]" in text, ort
        for name in NAMEN:
            assert name not in text, (ort, name)
        # „Laut Beleg:“ steht nur im Zug; der Beleg selbst darf als Zitatfeld (≤ 300 Zeichen) erscheinen.
        assert f"Laut Beleg: {uebernahme}" not in text, ort


def test_api_lehnt_frage_mit_personendaten_ab_ohne_die_eingabe_zu_wiederholen(
    pg_test: psycopg.Connection[Any],
) -> None:
    with TestClient(erstelle_app(starter=_kein_start, verbinde=_verbinde)) as c:
        antwort = c.post(
            "/faelle", json={"fall": "wartezeiten", "frage": "Wie lange wartet Versicherte 1234 010180?"}
        )
    assert antwort.status_code == 422
    assert antwort.json() == {"detail": FRAGE_PERSONENDATEN}
    assert "010180" not in antwort.text
