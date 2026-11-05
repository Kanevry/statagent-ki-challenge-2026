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


def test_erweiterung_schickt_keine_personendaten_ans_modell() -> None:
    """Fängt die Abnahme 121-5: Name, Geburtsdatum und Adresse gingen ungefiltert an das Modell der
    Anfrage-Erweiterung (gemessen 4 von 4 erfundenen Angaben)."""
    gesehen: list[str] = []

    def modell(
        nachrichten: list[dict[str, str]], schema: dict[str, Any], provider: str | None
    ) -> dict[str, Any]:
        gesehen.append(nachrichten[-1]["content"])
        return {"begriffe": ["Pflegegeld"]}

    frage = (
        "Meine Mutter heißt Maria Beispiel, ist am 12.03.1942 geboren, wohnt in der Favoritenstraße 1, "
        "1100 Wien, Telefon 0664 1234567. Bekommt sie Pflegegeld?"
    )
    erw.llm_begriffe(frage, modell=modell)
    for angabe in ("Maria", "Beispiel", "12.03.1942", "Favoritenstraße 1", "1100", "1234567"):
        assert angabe not in gesehen[0]
    assert "Pflegegeld" in gesehen[0] and "Wien" in gesehen[0]
