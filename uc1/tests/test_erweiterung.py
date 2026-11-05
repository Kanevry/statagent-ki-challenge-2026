"""Tests für uc1.erweiterung: Thesaurus deterministisch, LLM-Modus mit injiziertem Modell, Deckel."""

from __future__ import annotations

from typing import Any

from plattform.llm import ProviderFehler

from uc1 import erweiterung as erw


def test_thesaurus_bildet_buergersprache_auf_rechtsbegriff_ab() -> None:
    """Fängt einen Thesaurus, der Spital nicht als Krankenanstalt erkennt (Dev-Set d02)."""
    e = erw.erweitere("Meine Mutter liegt seit drei Wochen im Spital.", modus="thesaurus")
    assert "Krankenanstalt" in e.begriffe
    assert e.anfrage.startswith("Meine Mutter liegt") and "Krankenanstalt" in e.anfrage


def test_modus_aus_haengt_nichts_an() -> None:
    """Fängt einen Modus aus, der doch Begriffe anhängt."""
    e = erw.erweitere("Muss ich beim Arzt etwas dazuzahlen?", modus="aus")
    assert e.begriffe == [] and e.anfrage == "Muss ich beim Arzt etwas dazuzahlen?"


def test_llm_begriffe_werden_gedeckelt() -> None:
    """Fängt zu viele, zu lange oder nummerierte Begriffe, die die Suche auf 2 s treiben."""

    def modell(
        nachrichten: list[dict[str, str]], schema: dict[str, Any], provider: str | None
    ) -> dict[str, Any]:
        return {
            "begriffe": [
                "Kostenbeteiligung",
                "§ 86 GSVG",
                "ein sehr langer Begriff aus vielen einzelnen Wörtern",
                "Behandlungsbeitrag",
                "Kostenbeteiligung",
                "ärztliche Hilfe",
                "Selbstbehalt",
                "Krankenversicherung",
                "Sachleistung",
                "Vertragspartner",
            ]
        }

    e = erw.erweitere("Ich bin selbständig. Muss ich beim Arzt etwas dazuzahlen?", modus="llm", modell=modell)
    assert e.quelle == "llm"
    assert len(e.begriffe) == erw.MAX_BEGRIFFE
    assert all("§" not in b and len(b.split()) <= erw.MAX_WOERTER for b in e.begriffe)
    assert e.begriffe.count("Kostenbeteiligung") == 1


def test_llm_ausfall_faellt_auf_thesaurus_zurueck() -> None:
    """Fängt eine Erweiterung, die bei Modellausfall ohne Begriffe weiterläuft oder abstürzt."""

    def modell(
        nachrichten: list[dict[str, str]], schema: dict[str, Any], provider: str | None
    ) -> dict[str, Any]:
        raise ProviderFehler("alle Stufen gescheitert")

    e = erw.erweitere(
        "Meine Pension ist so niedrig. Gibt es einen Zuschlag zur Pension?", modus="llm", modell=modell
    )
    assert e.quelle == "thesaurus-ersatz"
    assert "Ausgleichszulage" in e.begriffe
