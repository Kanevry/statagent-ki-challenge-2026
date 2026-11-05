"""Verhandlung gegen PG (`pg_test`) mit dem Szenario-Mock und erfundenen Fixture-Belegen (#44, PRD S5)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import psycopg
import pytest

import uc2.modelle
from uc2.belege.namen import Namenseintrag, Namensliste
from uc2.modelle import ModellKonfigFehler
from uc2.verhandlung.belege import BelegFehler, FixtureQuelle, IndexQuelle
from uc2.verhandlung.bericht import bericht
from uc2.verhandlung.fall import FallFehler, lade_fall
from uc2.verhandlung.lauf import Laufoptionen, Verhandlung
from uc2.verhandlung.speicher import lies_ereignisse, lies_fall, wirksamer_status

SCHUTZLISTE = Namensliste((Namenseintrag("Felix Probst"),))
"""Erfundene Liste: Echte Provider laufen nur mit Namensliste (#137, fail-closed vor dem Prüfpunkt)."""


@pytest.fixture(autouse=True)
def protokoll_im_tmp(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Modell-Protokollzeilen nicht ins Repo schreiben."""
    monkeypatch.setenv("PLATTFORM_PROTOKOLL", str(tmp_path / "modellaufrufe.jsonl"))
    monkeypatch.delenv("UC2_MOCK_KAPUTT", raising=False)


def _lauf(verbindung: psycopg.Connection[Any]) -> int:
    optionen = Laufoptionen(provider="mock", quelle=FixtureQuelle())
    return Verhandlung(verbindung, lade_fall("wartezeiten"), optionen).fuehre_aus()


def _ohne_zeit(verbindung: psycopg.Connection[Any], fall_id: int) -> list[tuple[Any, ...]]:
    return [
        (e["seq"], e["runde"], e["art"], e["akteur"], e["daten"])
        for e in lies_ereignisse(verbindung, fall_id)
    ]


def test_mock_zweimal_gleiche_ereignisse_matrix_und_einordnung(pg_test: psycopg.Connection[Any]) -> None:
    erst, zweit = _lauf(pg_test), _lauf(pg_test)
    assert erst != zweit  # jeder Lauf ist ein neuer Fall
    assert _ohne_zeit(pg_test, erst) == _ohne_zeit(pg_test, zweit)
    b1, b2 = bericht(pg_test, erst), bericht(pg_test, zweit)
    assert b1["matrix"] == b2["matrix"] and b1["klassifikation"] == b2["klassifikation"]
    assert b1["fall"]["status"] == "fertig"
    # Akzeptanz #44: ≤ 6 Akteure, Begründung für jeden, ≥ 3 Runden, Bezug ab Runde 2
    assert len(b1["teilnehmer"]) <= 6 and len(b1["teilnahme"]) == 14
    assert all(t["begruendung"].strip() for t in b1["teilnahme"])
    assert len(b1["matrix"]["runden"]) >= 3
    assert all(z["bezug_auf"] for r in b1["runden"][1:] for z in r["zuege"] if z["gueltig"])


def test_mock_zeigt_minderheit_gegen_eine_mehrheit(pg_test: psycopg.Connection[Any]) -> None:
    """Abnahme 24-1: Im Vorführfall steht jemand gegen eine Mehrheit. Das Finanzministerium hält ab der
    Verhandlungsrunde seine rote Linie gegen Mehrausgaben bei den Paket-Maßnahmen."""
    b = bericht(pg_test, _lauf(pg_test))
    mit_minderheit = {
        t: k for t, k in b["klassifikation"].items() if k["kategorie"] == "mehrheit" and k["minderheit"]
    }
    assert mit_minderheit, b["klassifikation"]
    assert any("finanzministerium" in k["minderheit"] for k in mit_minderheit.values())
    werte = b["matrix"]["werte"]["finanzministerium"]
    assert any(reihe[1] > reihe[2] for reihe in werte.values())  # bewegt sich in Runde 3 dagegen


def test_kaputter_mock_zug_ergibt_ungueltige_ausgabe_und_lauf_endet_fertig(
    pg_test: psycopg.Connection[Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("UC2_MOCK_KAPUTT", "sv:2")
    fall_id = _lauf(pg_test)
    ungueltig = [e for e in lies_ereignisse(pg_test, fall_id) if e["art"] == "ungueltige_ausgabe"]
    assert [(e["runde"], e["akteur"]) for e in ungueltig] == [(2, "sv")]
    fall = lies_fall(pg_test, fall_id)
    assert fall is not None and fall["status"] == "fertig"
    # Position bleibt „unverändert“: Runde 2 übernimmt die Werte aus Runde 1
    zeilen = pg_test.execute(
        "select runde, thema, wert, quelle from uc2.position "
        "where fall_id = %s and akteur = 'sv' and runde <= 2 order by thema, runde",
        (fall_id,),
    ).fetchall()
    paare = [(zeilen[i], zeilen[i + 1]) for i in range(0, len(zeilen), 2)]
    assert paare and all(r1[2] == r2[2] and r2[3] == "unveraendert" for r1, r2 in paare)


def test_index_quelle_mit_echtem_provider_wird_verweigert(pg_test: psycopg.Connection[Any]) -> None:
    """Ohne Namensliste ist die Index-Quelle nicht maskiert; der Lauf bricht vor der Anlage ab."""
    optionen = Laufoptionen(provider="claude", quelle=IndexQuelle(pg_test, namen=None), namen=SCHUTZLISTE)
    with pytest.raises(BelegFehler, match="nicht maskiert"):
        Verhandlung(pg_test, lade_fall("wartezeiten"), optionen).fuehre_aus()


def test_unbekannte_fall_id_und_pfad_werden_abgelehnt() -> None:
    for fall_id in ("gibtsnicht", "../faelle/wartezeiten", "/etc/passwd"):
        with pytest.raises(FallFehler):
            lade_fall(fall_id)


def test_laufender_fall_ohne_lebenszeichen_gilt_nach_60_s_als_abgebrochen() -> None:
    jetzt = datetime(2026, 11, 5, 18, 0, tzinfo=UTC)
    assert wirksamer_status("laufend", jetzt - timedelta(seconds=59), jetzt) == "laufend"
    assert wirksamer_status("laufend", jetzt - timedelta(seconds=61), jetzt) == "abgebrochen"
    assert wirksamer_status("fertig", jetzt - timedelta(hours=1), jetzt) == "fertig"


def test_echter_provider_online_ohne_budget_bricht_vor_dem_ersten_aufruf_ab(
    pg_test: psycopg.Connection[Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Review !47: Jeder UC2-Modellaufruf geht durch `plattform.llm.complete`. Dessen Budgetprüfung (!36)
    bricht mit `KIC_ONLINE=1` ohne `LLM_TAGESBUDGET_AUFRUFE` fail-closed ab, bevor ein Provider läuft."""
    from plattform.llm import kern  # type: ignore[import-untyped]

    monkeypatch.setenv("KIC_ONLINE", "1")
    monkeypatch.delenv("LLM_TAGESBUDGET_AUFRUFE", raising=False)
    aufrufe: list[str | None] = []
    echt = uc2.modelle.complete

    def gezaehlt(*args: Any, **kw: Any) -> Any:
        aufrufe.append(kw.get("provider"))
        return echt(*args, **kw)

    def kein_provider(name: str) -> Any:
        raise AssertionError(f"Provider {name} darf ohne Budget nie laufen")

    monkeypatch.setattr(uc2.modelle, "complete", gezaehlt)
    monkeypatch.setattr(kern, "provider_instanz", kein_provider)
    angelegt: list[int] = []
    optionen = Laufoptionen(
        provider="claude", quelle=FixtureQuelle(), bei_anlage=angelegt.append, namen=SCHUTZLISTE
    )
    with pytest.raises(ModellKonfigFehler, match="LLM_TAGESBUDGET_AUFRUFE"):
        Verhandlung(pg_test, lade_fall("wartezeiten"), optionen).fuehre_aus()
    assert aufrufe == ["claude"]
    fall = lies_fall(pg_test, angelegt[0])
    assert fall is not None and fall["status"] == "abgebrochen"
    abbruch = [e["daten"] for e in lies_ereignisse(pg_test, angelegt[0]) if e["art"] == "abbruch"]
    assert abbruch == [{"grund": "ModellKonfigFehler", "meldung": "Der Dienst ist gerade nicht bereit."}]
