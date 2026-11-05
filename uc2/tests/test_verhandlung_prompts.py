"""Prompts gegen Herdenverhalten (#127, PRD § 5): Grenzen im Akteurs-Prompt, Gegenfragen beim Moderator."""

from __future__ import annotations

from typing import Any

from uc2.akteure.laden import lade_akteure
from uc2.verhandlung import prompts
from uc2.verhandlung.lauf import einigung_ohne_gegenstimme
from uc2.verhandlung.matrix import Position

AUFTRAG: dict[str, Any] = {
    "themen": [
        {"id": "fachaerzte", "titel": "Mehr Facharztstellen", "beschreibung": "Ausbau der Kassenstellen"},
        {"id": "finanzierung", "titel": "Gegenfinanzierung", "beschreibung": "Wer trägt die Mehrkosten"},
    ],
    "regeln": ["Rote Linien gelten."],
    "ziel": "Kürzere Wartezeiten",
}


def _user(nachrichten: list[dict[str, str]]) -> str:
    return next(n["content"] for n in nachrichten if n["role"] == "user")


def test_akteurs_prompt_nennt_rote_linien_und_budgetvorgaben_als_verbindliche_grenzen() -> None:
    akteur = next(a for a in lade_akteure() if a.id == "finanzministerium")
    assert akteur.rote_linien and akteur.budgetvorgaben
    text = _user(
        prompts.akteur_nachrichten(
            akteur=akteur,
            frage="Wie sinken die Wartezeiten?",
            auftrag=AUFTRAG,
            runde=1,
            teilnehmer=["finanzministerium", "sv"],
            belege=[],
            experte={},
            vorrunde=None,
        )
    )
    grenzen = text.split("# Deine verbindlichen Grenzen", 1)[1].split("# Experte", 1)[0]
    for eintrag in (*akteur.rote_linien, *akteur.budgetvorgaben):
        assert f"- {eintrag}" in grenzen
    assert "höchstens 0" in grenzen
    assert "Dass die anderen schon zustimmen, ist kein Grund." in grenzen


def test_moderator_prompt_ab_runde_zwei_fordert_gegenargument_und_nennt_hinweis_aus_dem_code() -> None:
    jetzt = {
        a: {
            "fachaerzte": Position(a, "fachaerzte", 1, "dafür"),
            "finanzierung": Position(a, "finanzierung", w, "x"),
        }
        for a, w in (("aerztekammer", 2), ("sv", -1))
    }
    einig = einigung_ohne_gegenstimme(jetzt, ["aerztekammer", "sv"], ["fachaerzte", "finanzierung"])
    assert einig == ["fachaerzte"]
    text = _user(
        prompts.notiz_nachrichten(
            frage="Wie sinken die Wartezeiten?",
            auftrag=AUFTRAG,
            runde=2,
            teilnehmer=["aerztekammer", "sv"],
            positionen={"aerztekammer": {"fachaerzte": 1}, "sv": {"fachaerzte": 1}},
            aenderungen=[],
            klassifikation={"fachaerzte": "konsens", "finanzierung": "offener_konflikt"},
            code_widersprueche=[],
            haltungen_ohne_beleg=[],
            einigung_ohne_gegenstimme=einig,
            grenzen={"sv": {"rote_linien": ["keine Beitragserhöhung"], "budgetvorgaben": []}},
            kosten={"mehrkosten_mio_eur": {"modus": 120.0, "min": 90.0, "max": 150.0}},
        )
    )
    assert prompts.KONSENSREGELN[0] in text
    assert "mindestens ein Gegenargument oder eine offene Kostenfrage" in text
    assert "Einigung ohne Gegenstimme in Runde 2 bei Themen: fachaerzte." in text
    assert "keine Beitragserhöhung" in text and "gegenfinanziert" in text
