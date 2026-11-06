"""Belegzitat für Anzeige und API: höchstens 300 Zeichen, ab dem passenden Satz (Entscheid des Owners)."""

from __future__ import annotations

from uc2.belege.suche import ZITAT_ZEICHEN, kurzzitat

LANG = (
    "Die Landesregierung stellt ein neues Programm vor. "
    + "Es geht um Kassenstellen in ländlichen Regionen und um bessere Erreichbarkeit. " * 6
    + "Die Wartezeiten auf einen Termin beim Facharzt sollen bis 2030 deutlich sinken, "
    "sagt eine Vertreterin der Sozialversicherung. " + "Weitere Schritte folgen im Herbst. " * 10
)


def test_kurzzitat_hoechstens_300_zeichen_ab_passendem_satz() -> None:
    zitat = kurzzitat(LANG, "Wartezeiten Facharzt")
    assert len(LANG) > 3 * ZITAT_ZEICHEN
    assert len(zitat) <= ZITAT_ZEICHEN
    assert zitat.startswith("Die Wartezeiten auf einen Termin beim Facharzt")
    assert zitat.endswith("…") and " ".join(LANG.split()).find(zitat[:-1].rstrip()) >= 0


def test_kurzzitat_kurzer_text_bleibt_ganz() -> None:
    text = "Kurze Meldung zur Primärversorgung."
    assert kurzzitat(text, "Wartezeiten") == text
