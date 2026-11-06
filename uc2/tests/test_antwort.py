"""UC4-Adapter `uc2.antwort.antwort` (#103) mit Szenario-Mock und erfundenen Fixture-Belegen, ohne PG.

Zwei Fragen: `DEMO` passt zum Fall `wartezeiten` (Rechenmodell rechnet), `PRAES` ist die Beispiel-Frage der
Präsentation (allgemeine Frage, kein Fall, Zahl nur aus dem UC3-Kontext). `DEMO` läuft mit zwei Runden und
vier Akteuren (Debatte, „300 Stellen“ des Szenario-Mocks), `PRAES` mit dem UC4-Standard (eine Runde, drei).
"""

from __future__ import annotations

import json
import threading
from datetime import date
from importlib.metadata import entry_points
from pathlib import Path
from typing import Any

import jsonschema
import pytest
from plattform.antwortform import SCHEMA_DATEI, UcAntwort, Zahl
from plattform.llm import BudgetErschoepft
from plattform.router import durchreichen, mock_adapter

import uc2.modelle
from uc2.akteure.laden import Akteur, lade_akteure
from uc2.antwort import AntwortFehler, FreieZahl, antwort, belegquelle, bereinige, freie_zahlen, kurzlauf
from uc2.antwort import adapter as adapter_modul
from uc2.antwort.adapter import ERSATZ, MODELLANNAHME, QUELLE_BEISPIEL, waehle_fall
from uc2.antwort.allgemein import (
    _GELD,
    FESTER_KERN,
    KERN_SCHEMA,
    MOCK_THEMEN,
    TEILNEHMER,
    VORLAGE_OBEN,
    bezug_aus,
    feste_saetze,
    fester_auftrag,
    kern_text,
    mock_notiz,
)
from uc2.modelle import Modellantwort, UngueltigeAntwort
from uc2.modelle.kontext import lies_kontext
from uc2.verhandlung.belege import BELEG_ID, Beleg, BelegFehler, FixtureQuelle, IndexQuelle
from uc2.verhandlung.lauf import Zugergebnis

FIXTURES = Path(__file__).parent / "fixtures" / "antwort"
DEMO = "Wie entwickeln sich die Wartezeiten, und was heißt das für mich?"
PRAES = (
    "Wie viele Menschen arbeiten im März 2025 in Wien im Gesundheits- und Sozialwesen, "
    "und was heißt das für mich?"
)
DEMO_LANG = {"runden": 2, "max_akteure": 4}
"""Volle Kurzverhandlung für `DEMO`: Debatte und vier Akteure (Standard für UC4: eine Runde, drei)."""


@pytest.fixture(autouse=True)
def mock_und_protokoll_im_tmp(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("LLM_PROVIDER", "mock")
    monkeypatch.setenv("PLATTFORM_PROTOKOLL", str(tmp_path / "modellaufrufe.jsonl"))
    monkeypatch.setenv("PLATTFORM_ROUTER_PROTOKOLL", str(tmp_path / "router.jsonl"))
    monkeypatch.delenv("UC2_MOCK_KAPUTT", raising=False)
    monkeypatch.delenv("UC2_NAMENSLISTE", raising=False)


WIEN_BEZUG = "Für Wien, Gesundheits- und Sozialwesen im März 2025 nennt StatAgent 135.790 Personen."
WIEN_ZEILE = (
    f"{WIEN_BEZUG} In Wien heißt mehr Personal meist kürzere Wartezeiten und mehr Betreuung. "
    "Weniger Personal heißt dort meist längere Wartezeiten und mehr Druck auf die Beschäftigten."
)


def _uc3(datei: str = "uc3-kontext.json") -> UcAntwort:
    return UcAntwort.model_validate(json.loads((FIXTURES / datei).read_text(encoding="utf-8")))


def _uc3_wien(frage: str, kontext: list[UcAntwort]) -> UcAntwort:
    """Mock-UC3 für den Router: erfundene Zahl Wien, März 2025, Gesundheits- und Sozialwesen."""
    return _uc3("uc3-wien-gesundheit.json")


@pytest.fixture(scope="module")
def demo(tmp_path_factory: pytest.TempPathFactory) -> UcAntwort:
    with pytest.MonkeyPatch.context() as mp:
        mp.setenv("LLM_PROVIDER", "mock")
        mp.setenv("PLATTFORM_PROTOKOLL", str(tmp_path_factory.mktemp("demo") / "modellaufrufe.jsonl"))
        return antwort(DEMO, [_uc3()], **DEMO_LANG)


@pytest.fixture(scope="module")
def praes(tmp_path_factory: pytest.TempPathFactory) -> UcAntwort:
    with pytest.MonkeyPatch.context() as mp:
        mp.setenv("LLM_PROVIDER", "mock")
        mp.delenv("UC2_NAMENSLISTE", raising=False)
        mp.setenv("PLATTFORM_PROTOKOLL", str(tmp_path_factory.mktemp("praes") / "modellaufrufe.jsonl"))
        return antwort(PRAES, [_uc3("uc3-wien-gesundheit.json")])


def _akteurszeilen(text: str) -> list[str]:
    return [z for z in text.splitlines() if z.startswith("- ")]


def test_vertrag_pydantic_und_json_schema(demo: UcAntwort) -> None:
    roh = demo.model_dump(mode="json")
    UcAntwort.model_validate(roh)
    schema = json.loads(SCHEMA_DATEI.read_text(encoding="utf-8"))
    jsonschema.Draft202012Validator(schema).validate(roh)
    assert demo.uc == "uc2" and demo.protokoll_id is None and demo.modell == "mock"
    assert demo.zahlen and all(0 <= z.beleg < len(demo.belege) for z in demo.zahlen)
    experte = [b for b in demo.belege if b.quelle == "uc2.experte"]
    assert len(experte) == 1 and experte[0].ref == "beispiel-wartezeiten" and experte[0].sql is None
    bezeichnungen = {z.bezeichnung for z in demo.zahlen if demo.belege[z.beleg].quelle == "uc2.experte"}
    assert {
        "Wartezeitänderung (wahrscheinlichster Wert)",
        "Mehrkosten in % der Gesundheitsausgaben (wahrscheinlichster Wert)",
    } <= bezeichnungen


def test_mock_zweimal_gleiches_ergebnis(demo: UcAntwort) -> None:
    assert antwort(DEMO, [_uc3()], **DEMO_LANG).model_dump() == demo.model_dump()


def test_uc3_kontextzahl_mit_ihrem_beleg_in_der_antwort(demo: UcAntwort) -> None:
    zahl = next(z for z in demo.zahlen if z.wert == 398765)
    beleg = demo.belege[zahl.beleg]
    assert (beleg.uc, beleg.lieferung, beleg.monat, beleg.stand) == (
        "uc3",
        "2025-10",
        "2025-10",
        "vorlaeufig",
    )
    assert (
        "398.765 Personen (laut Beschäftigtenstatistik, Oktober 2025, vorläufig, "
        "die Zahl kann sich noch ändern)"
    ) in demo.text


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
    assert "300 Stellen" not in demo.text and ERSATZ not in demo.text
    assert bereinige("fehlen rund 300 Stellen, Wartezeit −22,24 %", demo.zahlen) == (
        f"fehlen rund {ERSATZ}, Wartezeit −22,24 %"
    )


def test_ohne_bereinigung_bricht_der_textcheck_ab(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(adapter_modul, "bereinige", lambda text, zahlen, profil=frozenset(): text)
    with pytest.raises(FreieZahl, match="300 Stellen"):
        antwort(DEMO, [], **DEMO_LANG)


def test_je_akteur_beleg_mit_medium_und_herkunft(demo: UcAntwort) -> None:
    zeilen = _akteurszeilen(demo.text)
    assert 2 <= len(zeilen) <= kurzlauf.KURZ_GRENZE_AKTEURE
    assert all("Beispielbeleg, erfunden: " in z or MODELLANNAHME in z for z in zeilen)
    presse = [b for b in demo.belege if b.quelle.startswith(QUELLE_BEISPIEL)]
    assert presse and all(b.uc == "uc2" and b.ref and BELEG_ID.fullmatch(b.ref) for b in presse)
    assert all(b.monat and len(b.monat) == 7 and b.monat[4] == "-" for b in presse)
    # Herkunft je Beleg: Medium in der Quelle, Monat, Beleg-ID.
    assert all(len(b.quelle) > len(QUELLE_BEISPIEL) + 2 for b in presse)


def test_ohne_belege_steht_modellannahme(tmp_path: Path) -> None:
    leer = tmp_path / "belege.json"
    leer.write_text('{"belege": []}', encoding="utf-8")
    ergebnis = antwort(DEMO, [], quelle=FixtureQuelle(leer))
    zeilen = _akteurszeilen(ergebnis.text)
    assert zeilen and all(MODELLANNAHME in z for z in zeilen)
    assert not [b for b in ergebnis.belege if b.uc == "uc2" and b.ref and BELEG_ID.fullmatch(b.ref)]


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


# --- Beispiel-Frage der Präsentation: allgemeine Frage, kein Rechenmodell -------------------------------


def test_stichwortregel_fall_nur_bei_passender_frage() -> None:
    fall = waehle_fall(DEMO)
    assert fall is not None and fall.id == "wartezeiten"
    assert waehle_fall("Wie lange ist die Wartezeit auf einen Termin?") is not None
    assert waehle_fall(PRAES) is None


def test_praesentation_vertrag_pydantic_und_json_schema(praes: UcAntwort) -> None:
    roh = praes.model_dump(mode="json")
    UcAntwort.model_validate(roh)
    jsonschema.Draft202012Validator(json.loads(SCHEMA_DATEI.read_text(encoding="utf-8"))).validate(roh)
    assert praes.uc == "uc2" and praes.modell == "mock" and praes.protokoll_id is None


def test_praesentation_kontextzahl_mit_beleg_und_ohne_rechenmodell(praes: UcAntwort) -> None:
    uc3 = _uc3("uc3-wien-gesundheit.json")
    (zahl,) = [z for z in praes.zahlen]
    assert (zahl.bezeichnung, zahl.wert, zahl.einheit) == (
        "Beschäftigte (Wien, Gesundheits- und Sozialwesen)",
        135790,
        "Personen",
    )
    beleg = praes.belege[zahl.beleg]
    assert beleg == uc3.belege[0] and beleg.quelle == "stat.stat_beschaeftigte"
    assert (beleg.lieferung, beleg.monat) == ("2025-03", "2025-03")
    assert not [b for b in praes.belege if b.quelle == "uc2.experte"]
    assert "Rechenmodell" not in praes.text
    assert praes.text.splitlines()[1].startswith(
        "Die Zahl aus der Statistik: Beschäftigte (Wien, Gesundheits- und Sozialwesen): "
    )
    assert "135.790 Personen (laut Beschäftigtenstatistik, März 2025, endgültig)." in praes.text
    # Erlaubt sind nur Zifferngruppen aus Akteursprofilen (z. B. die Hotline „1450“), sonst keine freie Zahl.
    from uc2.akteure.laden import lade_akteure
    from uc2.antwort.textzahlen import profilzahlen

    profil = profilzahlen(t for a in lade_akteure() for t in (*a.ziele, *a.interessen, *a.prioritaeten))
    assert freie_zahlen(praes.text, praes.zahlen, profil) == []


def test_praesentation_je_akteur_beleg_oder_modellannahme(praes: UcAntwort) -> None:
    zeilen = _akteurszeilen(praes.text)
    assert 2 <= len(zeilen) <= kurzlauf.KURZ_MAX_AKTEURE
    for zeile in zeilen:
        assert "Beispielbeleg, erfunden: " in zeile or MODELLANNAHME in zeile, zeile
    presse = [b for b in praes.belege if b.quelle.startswith(QUELLE_BEISPIEL)]
    assert presse and all(b.ref and BELEG_ID.fullmatch(b.ref) and b.monat for b in presse)


def test_praesentation_allgemeiner_auftrag_und_alltagssprache(praes: UcAntwort) -> None:
    for thema in MOCK_THEMEN:
        assert thema["titel"] in praes.text
    assert "Wer ist dafür, wer dagegen:" in praes.text and "Kurz gesagt: " in praes.text
    assert "–" not in praes.text and "—" not in praes.text


def test_praesentation_kontext_geht_ohne_experte_ans_panel(monkeypatch: pytest.MonkeyPatch) -> None:
    gesehen: dict[str, Any] = {}
    echt = kurzlauf.kurzverhandlung

    def spion(**kw: Any) -> kurzlauf.Kurzergebnis:
        gesehen.update(kw)
        return echt(**kw)

    monkeypatch.setattr(adapter_modul, "kurzverhandlung", spion)
    antwort(PRAES, [_uc3("uc3-wien-gesundheit.json")], runden=1)
    assert "vom_rechenmodell_berechnet" not in gesehen["experte"]
    assert gesehen["experte"]["kontext_zahlen"][0]["quelle"] == "stat.stat_beschaeftigte"
    assert gesehen["experte_werte"] == [135790.0]


def test_router_praesentation_kette_uc3_uc2() -> None:
    kette = durchreichen(PRAES, kette=("uc3", "uc2"), adapter={"uc3": _uc3_wien, "uc2": antwort})
    assert kette.fehlend == [] and [a.uc for a in kette.antworten] == ["uc3", "uc2"]
    uc3, uc2 = kette.antworten
    uebernommen = next(z for z in uc2.zahlen if z.wert == uc3.zahlen[0].wert)
    assert uc2.belege[uebernommen.beleg] == uc3.belege[0]
    assert not [b for b in uc2.belege if b.quelle == "uc2.experte"]


def test_zahlerkennung_mit_tausenderpunkt(praes: UcAntwort) -> None:
    assert freie_zahlen("Es sind 135.790 Personen.", praes.zahlen) == []
    assert freie_zahlen("Es sind 135.791 Personen.", praes.zahlen) == ["135.791 Personen"]
    assert freie_zahlen("Es fehlen 1.200 Stellen.", praes.zahlen) == ["1.200 Stellen"]


# --- Belegquelle --------------------------------------------------------------------------------------


class _Verbindung:
    def __enter__(self) -> _Verbindung:
        return self

    def __exit__(self, *args: object) -> None:
        return None


def test_belegquelle_ohne_namensliste_fixture() -> None:
    with belegquelle() as quelle:
        assert isinstance(quelle, FixtureQuelle)


def test_belegquelle_ohne_datenbank_fixture(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(adapter_modul, "lade_namensliste", lambda: object())

    def keine_db(*args: Any, **kwargs: Any) -> Any:
        raise adapter_modul.psycopg.OperationalError("nicht erreichbar")

    monkeypatch.setattr(adapter_modul.psycopg, "connect", keine_db)
    with belegquelle() as quelle:
        assert isinstance(quelle, FixtureQuelle)


@pytest.mark.parametrize(("index", "erwartet"), [(True, IndexQuelle), (False, FixtureQuelle)])
def test_belegquelle_index_nur_mit_namensliste_und_abschnitten(
    monkeypatch: pytest.MonkeyPatch, index: bool, erwartet: type
) -> None:
    namen = object()
    monkeypatch.setattr(adapter_modul, "lade_namensliste", lambda: namen)
    monkeypatch.setattr(adapter_modul.psycopg, "connect", lambda *a, **k: _Verbindung())
    monkeypatch.setattr(adapter_modul, "hat_index", lambda verbindung: index)
    with belegquelle() as quelle:
        assert isinstance(quelle, erwartet)
        if isinstance(quelle, IndexQuelle):
            assert quelle.maskiert and quelle.namen is namen


# --- Review zu !73: Laufzeit, Sprache, Budget ----------------------------------------------------------


def _zaehle_aufrufe(monkeypatch: pytest.MonkeyPatch) -> list[tuple[str, list[dict[str, str]]]]:
    """Jeder Modellaufruf über `uc2.modelle.complete` mit Rolle (aus dem Kontextblock) und Nachrichten."""
    aufrufe: list[tuple[str, list[dict[str, str]]]] = []
    echt = uc2.modelle.complete

    def zaehler(nachrichten: list[dict[str, str]], **kw: Any) -> Any:
        erste = next(n["content"] for n in nachrichten if n["role"] == "user")
        aufrufe.append((str((lies_kontext(erste) or {}).get("rolle")), nachrichten))
        return echt(nachrichten, **kw)

    monkeypatch.setattr(uc2.modelle, "complete", zaehler)
    return aufrufe


def test_uc4_standard_hoechstens_fuenf_aufrufe(monkeypatch: pytest.MonkeyPatch) -> None:
    aufrufe = _zaehle_aufrufe(monkeypatch)
    ergebnis = antwort(DEMO, [_uc3()])
    rollen = [r for r, _ in aufrufe]
    assert rollen.count("moderator_auftrag") == 1 and rollen.count("moderator_notiz") <= 1
    assert 2 <= rollen.count("akteur") <= 3 and "moderator_auswahl" not in rollen
    assert len(rollen) <= 5
    assert len(_akteurszeilen(ergebnis.text)) == rollen.count("akteur")
    assert "in einer Runde" in ergebnis.text and "Einschätzung der Moderation:" in ergebnis.text


def test_praesentation_ohne_auftrag_und_notizaufruf(monkeypatch: pytest.MonkeyPatch) -> None:
    """Allgemeine Frage: fester Auftrag statt Modellaufruf, keine Notiz, nur die drei Akteurszüge."""
    aufrufe = _zaehle_aufrufe(monkeypatch)
    antwort(PRAES, [_uc3("uc3-wien-gesundheit.json")])
    rollen = [r for r, _ in aufrufe]
    assert rollen == ["akteur", "akteur", "akteur", "moderator_kern"]


def test_frist_um_keine_weitere_runde_und_keine_notiz(monkeypatch: pytest.MonkeyPatch) -> None:
    aufrufe = _zaehle_aufrufe(monkeypatch)
    ergebnis = antwort(DEMO, [_uc3()], frist_s=0, **DEMO_LANG)
    rollen = [r for r, _ in aufrufe]
    assert rollen.count("moderator_notiz") == 0 and rollen.count("akteur") == 4
    assert "in einer Runde" in ergebnis.text and "Einschätzung der Moderation" not in ergebnis.text


def test_akteurszuege_laufen_bei_echtem_provider_parallel(monkeypatch: pytest.MonkeyPatch) -> None:
    # Die Barriere öffnet nur, wenn alle drei Züge gleichzeitig warten; nacheinander liefe sie in den Timeout.
    barriere = threading.Barrier(3, timeout=10)

    def zug(rm: Any, nachrichten: Any, *, akteur: str, themen: list[str], runde: int, **kw: Any) -> Any:
        barriere.wait()
        themenzuege = [
            {
                "thema": t,
                "haltung": 1,
                "begruendung": "Gut für die Versorgung.",
                "beleg_ids": [],
                "bedingungen": [],
                "zugestaendnis": None,
            }
            for t in themen
        ]
        return Zugergebnis(
            akteur, {"themen": themenzuege, "bezug_auf": [], "zahlen": []}, [], 1, "azure", "m"
        )

    def moderator(rm: Any, nachrichten: Any, schema: Any) -> Modellantwort:
        assert schema is KERN_SCHEMA
        daten = {
            "mehr": "Mehr Personal heißt meist kürzer warten.",
            "weniger": "Weniger Personal heißt länger warten.",
        }
        return Modellantwort(daten, json.dumps(daten), "azure", "m", 1)

    monkeypatch.setattr(kurzlauf, "fuehre_zug_aus", zug)
    monkeypatch.setattr(kurzlauf, "rufe", moderator)
    ergebnis = antwort(PRAES, [_uc3("uc3-wien-gesundheit.json")], provider="azure", quelle=FixtureQuelle())
    assert len(_akteurszeilen(ergebnis.text)) == 3
    assert "Die Rollen spielt eine KI" in ergebnis.text and "Testbetrieb" not in ergebnis.text


def test_alltagsregel_in_jedem_aufruf(monkeypatch: pytest.MonkeyPatch) -> None:
    aufrufe = _zaehle_aufrufe(monkeypatch)
    antwort(DEMO, [_uc3()])
    assert aufrufe
    for _, nachrichten in aufrufe:
        assert nachrichten[0]["role"] == "system"
        assert nachrichten[0]["content"].endswith(kurzlauf.ALLTAGSREGEL)
    assert "Fachbegriff" in kurzlauf.ALLTAGSREGEL and "Alltagssprache" in kurzlauf.ALLTAGSREGEL


def test_keine_prognose_und_notiz_in_klartext(demo: UcAntwort, praes: UcAntwort) -> None:
    for text in (demo.text, praes.text):
        assert "Änderung" not in text and "zu erwarten" not in text and "wohl nichts" not in text
        assert "Der Code meldet" not in text
    assert "Das Programm hat eine Auffälligkeit gefunden: Bei " in demo.text
    zwei = mock_notiz(
        {
            "themen": [{"id": "triage", "titel": "Digitale Triage"}],
            "aenderungen": [],
            "klassifikation": {"triage": "offener_konflikt"},
            "code_widersprueche": [{"art": "zahl_widerspruch", "akteur": "sv"}, {"art": "x", "akteur": "ak"}],
        }
    )
    assert zwei == (
        "In dieser Runde hat niemand seine Haltung geändert. Noch strittig: Digitale Triage. "
        "Das Programm hat zwei Auffälligkeiten gefunden, zum Beispiel: "
        "Bei sv weicht eine Zahl vom Rechenmodell ab."
    )


def test_mock_satz_ohne_ki(praes: UcAntwort) -> None:
    assert "Testbetrieb ohne KI: Die Rollen kommen aus einer festen Vorlage." in praes.text
    assert "spielt eine KI" not in praes.text


def test_herkunft_ohne_tabelle_und_lieferung_im_text(praes: UcAntwort) -> None:
    assert "stat." not in praes.text and "Tabelle" not in praes.text and "Lieferung" not in praes.text
    assert "2025-03" not in praes.text and "UC3" not in praes.text
    (zahl,) = praes.zahlen
    beleg = praes.belege[zahl.beleg]
    assert (beleg.quelle, beleg.lieferung) == ("stat.stat_beschaeftigte", "2025-03")


def test_budget_erschoepft_geht_unveraendert_an_den_router(monkeypatch: pytest.MonkeyPatch) -> None:
    fehler = BudgetErschoepft("Das Tageskontingent für Modellaufrufe ist aufgebraucht.")

    def leer(*args: Any, **kwargs: Any) -> Any:
        raise fehler

    monkeypatch.setattr(uc2.modelle, "complete", leer)
    with pytest.raises(BudgetErschoepft) as info:
        antwort(DEMO, [])
    assert info.value is fehler
    ergebnis = durchreichen(DEMO, kette=("uc2",), adapter={"uc2": antwort})
    assert [(f.uc, f.grund) for f in ergebnis.fehlend] == [("uc2", "BudgetErschoepft")]


def test_budget_erschoepft_in_der_akteursrunde(monkeypatch: pytest.MonkeyPatch) -> None:
    echt = uc2.modelle.complete
    gezaehlt: list[int] = []

    def nur_ein_aufruf(nachrichten: list[dict[str, str]], **kw: Any) -> Any:
        gezaehlt.append(1)
        if len(gezaehlt) > 1:
            raise BudgetErschoepft("Das Tageskontingent für Modellaufrufe ist aufgebraucht.")
        return echt(nachrichten, **kw)

    monkeypatch.setattr(uc2.modelle, "complete", nur_ein_aufruf)
    ergebnis = durchreichen(DEMO, kette=("uc2",), adapter={"uc2": antwort})
    assert [(f.uc, f.grund) for f in ergebnis.fehlend] == [("uc2", "BudgetErschoepft")]


def _budget_bei(monkeypatch: pytest.MonkeyPatch, trifft: Any) -> None:
    """`BudgetErschoepft` für jeden Aufruf, bei dem `trifft(rolle, nummer)` gilt; sonst der Mock."""
    echt = uc2.modelle.complete
    gezaehlt: dict[str, int] = {}

    def complete(nachrichten: list[dict[str, str]], **kw: Any) -> Any:
        erste = next(n["content"] for n in nachrichten if n["role"] == "user")
        rolle = str((lies_kontext(erste) or {}).get("rolle"))
        gezaehlt[rolle] = gezaehlt.get(rolle, 0) + 1
        if trifft(rolle, gezaehlt[rolle]):
            raise BudgetErschoepft("Das Tageskontingent für Modellaufrufe ist aufgebraucht.")
        return echt(nachrichten, **kw)

    monkeypatch.setattr(uc2.modelle, "complete", complete)


def test_budget_erschoepft_bei_einem_akteur_trotz_zwei_gueltigen(monkeypatch: pytest.MonkeyPatch) -> None:
    """Review-Bank 69: Zwei gültige Züge reichen für ein Ergebnis, der Budgetfehler geht trotzdem weiter."""
    _budget_bei(monkeypatch, lambda rolle, n: rolle == "akteur" and n % 3 == 0)
    with pytest.raises(BudgetErschoepft):
        antwort(PRAES, [_uc3("uc3-wien-gesundheit.json")])
    ergebnis = durchreichen(PRAES, kette=("uc2",), adapter={"uc2": antwort})
    assert [(f.uc, f.grund) for f in ergebnis.fehlend] == [("uc2", "BudgetErschoepft")]


def test_budget_erschoepft_in_der_notiz(monkeypatch: pytest.MonkeyPatch) -> None:
    """Review-Bank 69: Scheitert die Notiz am Budget, gibt es kein Ergebnis ohne Notiz, sondern den Fehler."""
    _budget_bei(monkeypatch, lambda rolle, n: rolle == "moderator_notiz")
    with pytest.raises(BudgetErschoepft):
        antwort(DEMO, [_uc3()])


def _kern_aus_modell(monkeypatch: pytest.MonkeyPatch, antwort_oder_fehler: Any) -> None:
    """Züge wie gehabt aus dem Mock, nur der Moderator-Aufruf für die Kernsätze liefert
    `antwort_oder_fehler`."""
    echt = kurzlauf.rufe

    def rufe(rm: Any, nachrichten: Any, schema: Any) -> Any:
        if schema is not KERN_SCHEMA:
            return echt(rm, nachrichten, schema)
        if isinstance(antwort_oder_fehler, Exception):
            raise antwort_oder_fehler
        return Modellantwort(antwort_oder_fehler, json.dumps(antwort_oder_fehler), "mock", "m", 1)

    monkeypatch.setattr(kurzlauf, "rufe", rufe)


def test_erste_zeile_greift_frage_und_zahl_auf(praes: UcAntwort) -> None:
    """Fängt den Befund des Owners (06.11.): Oben stand ein Lehrbuchsatz, der zu jeder Frage gleich passt,
    obwohl die Karte „mit der Antwort von StatAgent“ verspricht."""
    assert praes.text.splitlines()[0] == WIEN_ZEILE


def test_modellkern_steht_oben(monkeypatch: pytest.MonkeyPatch) -> None:
    """Fängt einen Kernsatz des Modells, der gar nicht in die Antwort kommt (immer nur die festen Sätze)."""
    _kern_aus_modell(
        monkeypatch,
        {
            "mehr": "In Wien heißt mehr Personal kürzer warten",
            "weniger": "Weniger Personal heißt länger warten.",
        },
    )
    text = antwort(PRAES, [_uc3("uc3-wien-gesundheit.json")]).text
    assert text.splitlines()[0] == (
        f"{WIEN_BEZUG} In Wien heißt mehr Personal kürzer warten. Weniger Personal heißt länger warten."
    )


def test_prompt_des_kerns_nennt_frage_und_antwort_von_statagent(monkeypatch: pytest.MonkeyPatch) -> None:
    """Fängt ein Modell, das Frage oder Zahl nicht sieht und darum nur Allgemeines schreiben kann."""
    gesehen: list[str] = []
    echt = kurzlauf.rufe

    def spion(rm: Any, nachrichten: Any, schema: Any) -> Any:
        if schema is KERN_SCHEMA:
            gesehen.append(nachrichten[-1]["content"])
        return echt(rm, nachrichten, schema)

    monkeypatch.setattr(kurzlauf, "rufe", spion)
    antwort(PRAES, [_uc3("uc3-wien-gesundheit.json")])
    assert len(gesehen) == 1 and PRAES in gesehen[0] and WIEN_BEZUG in gesehen[0]


@pytest.mark.parametrize(
    "kern",
    [
        {"mehr": "Mehr Personal heißt 135.790 Stellen.", "weniger": "Weniger Personal heißt länger warten."},
        {"mehr": "", "weniger": "Weniger Personal heißt länger warten."},
        {"mehr": "Mehr Personal " * 20, "weniger": "Weniger Personal heißt länger warten."},
        UngueltigeAntwort("kaputt", "json $"),
        {
            "mehr": "Mehr Personal heißt mehr Beiträge zur Krankenversicherung.",
            "weniger": "Weniger Personal heißt länger warten.",
        },
        {
            "mehr": "Mehr Personal heißt kürzer warten, aber wer es zahlt, ist umstritten.",
            "weniger": "Weniger Personal heißt länger warten.",
        },
        {"mehr": "Mehr Personal heißt höhere Kosten.", "weniger": "Weniger Personal heißt länger warten."},
        {
            "mehr": "Mehr Beschäftigte heißt kürzer warten.",
            "weniger": "Weniger Personal heißt länger warten.",
        },
        {
            "mehr": "Mehr Personal heißt zwanzig Tage weniger Wartezeit.",
            "weniger": "Weniger Personal heißt länger warten.",
        },
        {
            "mehr": "Mehr Personal heißt dreihundert Termine mehr.",
            "weniger": "Weniger Personal heißt länger warten.",
        },
        {
            "mehr": "Mehr Personal heißt die Hälfte der Wartezeit.",
            "weniger": "Weniger Personal heißt länger warten.",
        },
        {"mehr": "Mehr Personal heißt kürzer warten.", "weniger": "Weniger Personal heißt länger warten."},
    ],
    ids=[
        "ziffer",
        "leer",
        "zu-lang",
        "modellfehler",
        "beitraege",
        "wer-zahlt",
        "kosten",
        "falscher-anfang",
        "zahlwort",
        "zahlwort-hundert",
        "haelfte",
        "ohne-bezug-zur-frage",
    ],
)
def test_unbrauchbarer_kern_ergibt_feste_saetze(monkeypatch: pytest.MonkeyPatch, kern: Any) -> None:
    """Fängt: Bei einer Ziffer, einem leeren oder überlangen Satz oder einem Modellfehler bleibt die Zeile
    leer oder die
    Kette verliert den Simulator."""
    _kern_aus_modell(monkeypatch, kern)
    text = antwort(PRAES, [_uc3("uc3-wien-gesundheit.json")]).text
    assert text.splitlines()[0] == WIEN_ZEILE
    # Daran erkennt die Karte die Vorlage (UI-Regie 06.11.); gleicher Satz in web/components/uc4/kette.tsx.
    assert VORLAGE_OBEN in text


def test_modelltext_oben_traegt_keinen_vorlagensatz(monkeypatch: pytest.MonkeyPatch) -> None:
    """Fängt „Oben Vorlage“ an der Karte, obwohl das Modell die Sätze geschrieben hat."""
    _kern_aus_modell(
        monkeypatch,
        {
            "mehr": "In Wien heißt mehr Personal kürzer warten.",
            "weniger": "Weniger Personal heißt länger warten.",
        },
    )
    assert VORLAGE_OBEN not in antwort(PRAES, [_uc3("uc3-wien-gesundheit.json")]).text


def test_rechenmodell_oben_ist_keine_vorlage(demo: UcAntwort) -> None:
    """Fängt „Oben Vorlage“ beim Fallweg: Dort steht das Ergebnis des Rechenmodells, `kern` fehlt immer."""
    assert VORLAGE_OBEN not in demo.text


def _kontextzahl(bezeichnung: str, wert: float = 390900, einheit: str = "Anzahl") -> dict[str, Any]:
    return {"bezeichnung": bezeichnung, "wert": wert, "einheit": einheit, "uc": "uc3", "monat": "2025-10"}


def test_frage_ueber_alle_branchen_sagt_das_und_nennt_die_zahl() -> None:
    """Fängt den Lehrbuchsatz zu „Wie viele Beschäftigte gab es im Oktober 2025?“: Die Zahl zählt alle
    Branchen."""
    bezug = bezug_aus([_kontextzahl("Beschäftigungsverhältnisse")])
    assert bezug is not None
    assert (
        bezug.satz == "Für alle Branchen im Oktober 2025 nennt StatAgent 390.900 Beschäftigungsverhältnisse."
    )
    assert feste_saetze(bezug)["mehr"].startswith("Für Praxis und Spital sagt diese Zahl allein wenig;")
    assert bezug.anker == ("branch",)


def test_monat_angehaengt_ist_kein_bezug_zur_frage() -> None:
    """Fängt den echten Modellsatz vom 06.11.: „Mehr Personal heißt meist kürzere Wartezeit im Oktober.“"""
    bezug = bezug_aus([_kontextzahl("Beschäftigungsverhältnisse")])
    weniger = "Weniger Personal heißt meist längere Wartezeit."
    angehaengt = {"mehr": "Mehr Personal heißt kürzere Wartezeit im Oktober.", "weniger": weniger}
    assert kern_text(angehaengt, bezug) is None
    mehr = "Die Zahl zählt alle Branchen; mehr Personal in Praxen heißt kürzere Wartezeit."
    assert kern_text({"mehr": mehr, "weniger": weniger}, bezug) == f"{mehr} {weniger}"


def test_abgeschriebene_angaben_sind_kein_bezug_zur_frage() -> None:
    """Fängt den echten Modellsatz vom 06.11.: Die Angaben standen als Liste vor jedem Satz und damit dreimal
    auf der Karte."""
    bezug = bezug_aus([_kontextzahl("Beschäftigte (Wien, Gesundheits- und Sozialwesen)")])
    abgeschrieben = {
        "mehr": "Wien, Gesundheits- und Sozialwesen: mehr Personal heißt meist kürzere Wartezeiten.",
        "weniger": "Wien, Gesundheits- und Sozialwesen: weniger Personal heißt meist längere Wartezeiten.",
    }
    assert kern_text(abgeschrieben, bezug) is None
    natuerlich = {
        "mehr": "In Wien heißt mehr Personal meist kürzer warten.",
        "weniger": "Weniger Personal dort nicht.",
    }
    assert kern_text(natuerlich, bezug) is not None


def test_bezugssatz_besteht_die_zahlenpruefung_bei_einheit_anzahl() -> None:
    """Fängt die echte UC3-Zahl (Einheit „Anzahl“): „7.498“ fiele sonst als Zahl ohne Beleg aus dem Satz."""
    zahl = Zahl(
        bezeichnung="Beschäftigungsverhältnisse (Wien, Gesundheits- und Sozialwesen)",
        wert=7498,
        einheit="Anzahl",
        beleg=0,
    )
    bezug = bezug_aus([{**_kontextzahl(zahl.bezeichnung, 7498), "monat": "2025-03"}])
    assert bezug is not None
    assert bezug.satz == (
        "Für Wien, Gesundheits- und Sozialwesen im März 2025 nennt StatAgent 7.498 "
        "Beschäftigungsverhältnisse."
    )
    assert freie_zahlen(bezug.satz, [zahl]) == []
    assert freie_zahlen("Es gab 7.498 Gesundheitszentren.", [zahl]) == ["7.498"]


def test_mehrere_zahlen_stehen_nicht_im_bezugssatz() -> None:
    bezug = bezug_aus([_kontextzahl("Beschäftigte (Bau)", 1), _kontextzahl("Beschäftigte (Handel)", 2)])
    assert bezug is not None and bezug.satz == (
        "Für alle Branchen im Oktober 2025 nennt StatAgent mehrere Zahlen."
    )


def test_ohne_zahl_von_statagent_kein_bezug() -> None:
    assert bezug_aus([]) is None and feste_saetze(None) == dict(
        zip(("mehr", "weniger"), FESTER_KERN, strict=True)
    )


def test_kern_haelt_das_budget_nicht_zurueck(monkeypatch: pytest.MonkeyPatch) -> None:
    """Fängt: Das Tagesbudget endet beim Kernsatz, die Seite zeigt feste Sätze statt des Budget-Hinweises
    (#100)."""
    fehler = UngueltigeAntwort("Budget", "BudgetErschoepft")
    fehler.__cause__ = BudgetErschoepft("aus")
    _kern_aus_modell(monkeypatch, fehler)
    with pytest.raises(BudgetErschoepft):
        antwort(PRAES, [_uc3("uc3-wien-gesundheit.json")])


def test_fallfrage_nennt_oben_wirkung_und_kosten_ohne_entfernte_zahl(demo: UcAntwort) -> None:
    """Fängt eine Kernzeile, aus der die Zahlenprüfung die Kosten streicht („(Zahl ohne Beleg entfernt)“)."""
    erste = demo.text.splitlines()[0]
    assert erste.startswith("Für ") and "nennt StatAgent" in erste
    assert " Das durchgerechnete Maßnahmenpaket bringt laut Rechenmodell: Wartezeit " in erste
    assert erste.endswith("Wartezeit −22,2 %, Mehrkosten 128,2 Mio. Euro pro Jahr.") and ERSATZ not in erste


def test_fester_auftrag_nennt_das_ziel_der_abwaegung() -> None:
    """Fängt ein Ziel, das nur die Frage wiederholt: Bei „Wie viele …?“ gibt es dann nichts abzuwägen."""
    assert fester_auftrag(PRAES)["ziel"].startswith("Abwägen, was mehr oder weniger Personal bedeutet.")


def test_satz_mit_entfernter_zahl_faellt_ganz_weg() -> None:
    """Fängt den Probelauf 05.11.: „… lag im März 2025 bei (Zahl ohne Beleg entfernt).“ in der ganzen
    Antwort."""
    zeile = f"- Bundesländer: Dafür. Die Zahl lag bei {ERSATZ}. Das hilft den Regionen."
    assert adapter_modul._ohne_entfernte_zahl(zeile) == "- Bundesländer: Dafür. Das hilft den Regionen."


def _rollen_mit_aufwand(rolle: str, provider: str) -> Any:
    from dataclasses import replace

    return replace(
        uc2.modelle.rollenmodell(rolle, provider), aufwand="hoch" if rolle == "moderator" else "niedrig"
    )


def test_moderator_im_kurzlauf_rechnet_nicht_mit_hohem_aufwand(monkeypatch: pytest.MonkeyPatch) -> None:
    """Fängt den Probelauf 05.11.: Auftrag mit Aufwand „hoch“ dauert 42,8 s, die ganze Kette 49,8 s."""
    aufwand: list[Any] = []
    echt = kurzlauf.rufe

    def rufe(rm: Any, nachrichten: Any, schema: Any) -> Any:
        aufwand.append(rm.aufwand)
        return echt(rm, nachrichten, schema)

    monkeypatch.setattr(kurzlauf, "rufe", rufe)
    monkeypatch.setattr(kurzlauf, "rollenmodell", _rollen_mit_aufwand)
    antwort(DEMO, [_uc3()])
    assert aufwand and set(aufwand) == {"niedrig"}


def test_allgemeine_frage_waegen_aerzte_versicherte_und_kassen_ab(praes: UcAntwort) -> None:
    """Fängt Runden ohne Kasse oder Ärzte: Folie 9 verspricht die Sicht von Kassen, Ärzten, Versicherten."""
    namen = {a.id: a.name for a in lade_akteure()}
    zeilen = _akteurszeilen(praes.text)
    assert {z[2:].split(":", 1)[0] for z in zeilen} >= {namen["aerztekammer"], namen["sv"]}
    assert len(zeilen) == len(TEILNEHMER)


def test_feste_kernsaetze_und_prompt_sagen_nichts_ueber_geld() -> None:
    """Fängt den Widerspruch zur Lotsen-Karte: Über Beiträge oder Kosten gibt es ohne Rechenmodell keinen
    Beleg."""
    assert kern_text(dict(zip(("mehr", "weniger"), FESTER_KERN, strict=True))) == " ".join(FESTER_KERN)
    bezug = bezug_aus([{"bezeichnung": "Beschäftigte (Bau)", "wert": 5, "einheit": "Anzahl", "uc": "uc3"}])
    assert not _GELD.search(" ".join(feste_saetze(bezug).values()))


def test_kern_mit_ein_und_eine_bleibt() -> None:
    """Fängt einen zu breiten Zahlwort-Filter: „eine“ steht in fast jedem Satz, dann käme nur noch Fixtext."""
    kern = {
        "mehr": "Mehr Personal heißt meist eine kürzere Wartezeit.",
        "weniger": "Weniger Personal heißt länger warten.",
    }
    assert kern_text(kern) is not None


def test_zeile_einer_vertretung_ist_deutsch(praes: UcAntwort) -> None:
    """Fängt „Dafür bei Bessere Arbeitsbedingungen, Mehr öffentliches Geld dafür.“ (Review !210)."""
    assert "Dafür bei „" not in praes.text and "dafür." not in praes.text
    zeilen = [z for z in _akteurszeilen(praes.text) if "Dafür bei: " in z]
    assert zeilen and all("„" in z for z in zeilen)
    assert adapter_modul._titelliste(["A"]) == "„A“"
    assert adapter_modul._titelliste(["A", "B", "C"]) == "„A“, „B“ und „C“"


def test_antwort_nennt_kennzahl_mit_einer_schreibweise(demo: UcAntwort) -> None:
    """Fängt −22,2 % oben und −22,24 % darunter in derselben Antwort, auch aus Modelltext (Review !210)."""
    assert "22,24" not in demo.text and "62,75" not in demo.text
    assert "−22,2 %" in demo.text and ERSATZ not in demo.text
    assert "128,2 Mio. Euro" in demo.text and "Mio EUR" not in demo.text
