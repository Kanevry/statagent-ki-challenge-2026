"""UC4-Adapter `uc2.antwort.antwort` (#103) mit Szenario-Mock und erfundenen Fixture-Belegen, ohne PG."""

from __future__ import annotations

import json
from datetime import date
from importlib.metadata import entry_points
from pathlib import Path
from typing import Any

import jsonschema
import pytest
from plattform.antwortform import SCHEMA_DATEI, UcAntwort
from plattform.router import durchreichen, mock_adapter

from uc2.akteure.laden import Akteur
from uc2.antwort import AntwortFehler, FreieZahl, antwort, bereinige, freie_zahlen, kurzlauf
from uc2.antwort import adapter as adapter_modul
from uc2.antwort.adapter import ERSATZ, MODELLANNAHME
from uc2.modelle import UngueltigeAntwort
from uc2.verhandlung.belege import BELEG_ID, Beleg, BelegFehler, FixtureQuelle

FIXTURES = Path(__file__).parent / "fixtures" / "antwort"
DEMO = "Wie entwickeln sich die Wartezeiten, und was heißt das für mich?"


@pytest.fixture(autouse=True)
def mock_und_protokoll_im_tmp(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("LLM_PROVIDER", "mock")
    monkeypatch.setenv("PLATTFORM_PROTOKOLL", str(tmp_path / "modellaufrufe.jsonl"))
    monkeypatch.setenv("PLATTFORM_ROUTER_PROTOKOLL", str(tmp_path / "router.jsonl"))
    monkeypatch.delenv("UC2_MOCK_KAPUTT", raising=False)


def _uc3() -> UcAntwort:
    return UcAntwort.model_validate(json.loads((FIXTURES / "uc3-kontext.json").read_text(encoding="utf-8")))


@pytest.fixture(scope="module")
def demo(tmp_path_factory: pytest.TempPathFactory) -> UcAntwort:
    with pytest.MonkeyPatch.context() as mp:
        mp.setenv("LLM_PROVIDER", "mock")
        mp.setenv("PLATTFORM_PROTOKOLL", str(tmp_path_factory.mktemp("demo") / "modellaufrufe.jsonl"))
        return antwort(DEMO, [_uc3()])


def _akteurszeilen(text: str) -> list[str]:
    return [z for z in text.splitlines() if z.startswith("- ")]


def test_vertrag_pydantic_und_json_schema(demo: UcAntwort) -> None:
    roh = demo.model_dump(mode="json")
    UcAntwort.model_validate(roh)
    schema = json.loads(SCHEMA_DATEI.read_text(encoding="utf-8"))
    jsonschema.Draft202012Validator(schema).validate(roh)
    assert demo.uc == "uc2" and demo.protokoll_id is None and demo.modell == "mock-fixture"
    assert demo.zahlen and all(0 <= z.beleg < len(demo.belege) for z in demo.zahlen)
    experte = [b for b in demo.belege if b.quelle == "uc2.experte"]
    assert len(experte) == 1 and experte[0].ref == "beispiel-wartezeiten" and experte[0].sql is None
    bezeichnungen = {z.bezeichnung for z in demo.zahlen if demo.belege[z.beleg].quelle == "uc2.experte"}
    assert {
        "Wartezeitänderung (wahrscheinlichster Wert)",
        "Mehrkosten in % der Gesundheitsausgaben (wahrscheinlichster Wert)",
    } <= bezeichnungen


def test_mock_zweimal_gleiches_ergebnis(demo: UcAntwort) -> None:
    assert antwort(DEMO, [_uc3()]).model_dump() == demo.model_dump()


def test_uc3_kontextzahl_mit_ihrem_beleg_in_der_antwort(demo: UcAntwort) -> None:
    zahl = next(z for z in demo.zahlen if z.wert == 398765)
    beleg = demo.belege[zahl.beleg]
    assert (beleg.uc, beleg.lieferung, beleg.monat, beleg.stand) == (
        "uc3",
        "2025-10",
        "2025-10",
        "vorlaeufig",
    )
    assert "398.765 Personen (UC3, Monat 2025-10, Lieferung 2025-10, vorlaeufig)" in demo.text


def test_kontextzahl_geht_als_eingabe_ans_panel(monkeypatch: pytest.MonkeyPatch) -> None:
    gesehen: dict[str, Any] = {}
    echt = kurzlauf.kurzverhandlung

    def spion(**kw: Any) -> kurzlauf.Kurzergebnis:
        gesehen.update(kw)
        return echt(**kw)

    monkeypatch.setattr(adapter_modul, "kurzverhandlung", spion)
    antwort(DEMO, [_uc3()])
    assert gesehen["experte"]["kontext_zahlen"][0]["lieferung"] == "2025-10"
    assert 398765.0 in gesehen["experte_werte"]


def test_keine_freie_zahl_im_text(demo: UcAntwort) -> None:
    # Der Szenario-Mock nennt in Runde 2 bewusst „rund 300 Stellen“ ohne Quelle.
    assert freie_zahlen(demo.text, demo.zahlen) == []
    assert "300 Stellen" not in demo.text and ERSATZ in demo.text
    assert bereinige("fehlen rund 300 Stellen, Wartezeit −22,24 %", demo.zahlen) == (
        f"fehlen rund {ERSATZ}, Wartezeit −22,24 %"
    )


def test_ohne_bereinigung_bricht_der_textcheck_ab(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(adapter_modul, "bereinige", lambda text, zahlen: text)
    with pytest.raises(FreieZahl, match="300 Stellen"):
        antwort(DEMO, [])


def test_je_akteur_beleg_mit_medium_und_herkunft(demo: UcAntwort) -> None:
    zeilen = _akteurszeilen(demo.text)
    assert 2 <= len(zeilen) <= kurzlauf.KURZ_MAX_AKTEURE
    assert all("Belege: " in z or MODELLANNAHME in z for z in zeilen)
    presse = [b for b in demo.belege if b.quelle == "presse"]
    assert presse and all(b.uc == "uc2" and b.ref and BELEG_ID.fullmatch(b.ref) for b in presse)
    assert all(b.monat and len(b.monat) == 7 and b.monat[4] == "-" for b in presse)


def test_ohne_belege_steht_modellannahme(tmp_path: Path) -> None:
    leer = tmp_path / "belege.json"
    leer.write_text('{"belege": []}', encoding="utf-8")
    ergebnis = antwort(DEMO, [], quelle=FixtureQuelle(leer))
    zeilen = _akteurszeilen(ergebnis.text)
    assert zeilen and all(MODELLANNAHME in z for z in zeilen)
    assert not [b for b in ergebnis.belege if b.quelle == "presse"]


class _Unmaskiert:
    name = "index"
    maskiert = False

    def belege_fuer(self, akteur: Akteur, frage: str, runde: int, stichtag: date) -> list[Beleg]:
        raise AssertionError("darf nie gelesen werden")

    def belegzahl(self, akteur: Akteur, frage: str, stichtag: date) -> int:
        raise AssertionError("darf nie gelesen werden")


def test_unmaskierte_quelle_mit_echtem_provider_wird_vor_jedem_aufruf_verweigert() -> None:
    with pytest.raises(BelegFehler, match="nicht maskiert"):
        antwort(DEMO, [], provider="azure", quelle=_Unmaskiert())


def test_modellfehler_wirft_und_router_meldet_uc2_fehlend(monkeypatch: pytest.MonkeyPatch) -> None:
    def kaputt(*args: Any, **kwargs: Any) -> Any:
        raise UngueltigeAntwort("kein Provider", "LlmFehler")

    monkeypatch.setattr(kurzlauf, "rufe", kaputt)
    with pytest.raises(AntwortFehler, match="Moderator"):
        antwort(DEMO, [])
    ergebnis = durchreichen(DEMO, kette=("uc2",), adapter={"uc2": antwort})
    assert ergebnis.antworten == [] and [(f.uc, f.grund) for f in ergebnis.fehlend] == [
        ("uc2", "AntwortFehler")
    ]


def test_router_mit_adapter_und_kette_uc3_uc2() -> None:
    allein = durchreichen(DEMO, kette=("uc2",), adapter={"uc2": antwort})
    assert allein.fehlend == [] and [a.uc for a in allein.antworten] == ["uc2"]
    kette = durchreichen(DEMO, kette=("uc3", "uc2"), adapter={"uc3": mock_adapter()["uc3"], "uc2": antwort})
    uc3, uc2 = kette.antworten
    zahl = uc3.zahlen[0]
    uebernommen = next(z for z in uc2.zahlen if z.wert == zahl.wert)
    assert uc2.belege[uebernommen.beleg] == uc3.belege[zahl.beleg]


def test_entry_point_nach_uv_sync_auffindbar() -> None:
    punkte = list(entry_points(group="kic.uc_antwort", name="uc2"))
    assert len(punkte) == 1 and punkte[0].value == "uc2.antwort:antwort"
    assert punkte[0].load() is antwort
