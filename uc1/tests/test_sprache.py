"""Tests für uc1.sprache (Owner-Vorgabe Sprache, #31, #32, #81, #107): Gedankenstriche, Schablonen, Satzlänge,
feste Texte und Quelle im Halbsatz. Ohne DB und ohne Modell."""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
import yaml

from uc1 import kern, sprache

PAKET = Path(__file__).resolve().parent.parent
# Schlüssel, deren Wert ein Mensch liest (Antwort, Rückfrage, Antrag, Termin). Muster und Modell-Hinweise
# (z. B. antragsangaben.yaml „beschreibung“) sind nicht dabei.
SICHTBAR = {
    "de", "en", "text", "bedingung", "begruendung", "beschriftung", "annahme_grund", "frage", "summary",
    "nicht_gebucht", "wunschhinweis", "ohne_adresse", "rolle", "bezeichnung",
}  # fmt: skip
DATEIEN = [
    *sorted((PAKET / "daten").glob("*.yaml")),
    *sorted((PAKET / "stellen").glob("*.yaml")),
    *sorted((PAKET / "formulare").glob("*.felder.json")),
]


def _texte(knoten: Any, pfad: str = "") -> Iterator[tuple[str, str]]:
    if isinstance(knoten, dict):
        for schluessel, wert in knoten.items():
            if isinstance(wert, str) and schluessel in SICHTBAR:
                yield f"{pfad}.{schluessel}", wert
            else:
                yield from _texte(wert, f"{pfad}.{schluessel}")
    elif isinstance(knoten, list):
        for i, wert in enumerate(knoten):
            yield from _texte(wert, f"{pfad}[{i}]")


def _lade(datei: Path) -> Any:
    roh = datei.read_text(encoding="utf-8")
    return json.loads(roh) if datei.suffix == ".json" else yaml.safe_load(roh)


def test_em_dash_wird_geglaettet_bereich_und_bindestrich_bleiben() -> None:
    """Fängt einen Em-Dash im Modelltext, der rausgeht, und eine Glättung, die „7-9“ trennt."""
    text = "Der FSW berät in der Guglgasse 7-9 — gleich bei der U3 — in 1030 Wien. Der KI-Lotse hilft."
    geglaettet = sprache.glaette(text)
    assert "—" not in geglaettet
    assert "Guglgasse 7-9, gleich bei der U3, in 1030 Wien." in geglaettet and "KI-Lotse" in geglaettet
    assert sprache.glaette("Welche Zeit passt – vormittags oder nachmittags?") == (
        "Welche Zeit passt: vormittags oder nachmittags?"
    )
    assert sprache.glaette("Seiten 7 – 9 und Stufe 1-3.") == "Seiten 7–9 und Stufe 1-3."
    assert [b.art for b in sprache.pruefe(text)].count("gedankenstrich") == 2
    assert not [b for b in sprache.pruefe(geglaettet) if b.art == "gedankenstrich"]


def test_schablone_wird_gefunden_und_floskelsatz_gestrichen() -> None:
    """Fängt KI-Schablonen („Gerne helfe ich“, „Bitte beachten Sie:“, Emoji), die unbemerkt rausgehen."""
    text = "Gerne helfe ich Ihnen. Bitte beachten Sie: Der Antrag kostet nichts. Ich hoffe, das hilft! 😊"
    arten = {b.art for b in sprache.pruefe(text)}
    assert {"floskel", "einleitung", "emoji"} <= arten
    assert sprache.glaette(text) == "Der Antrag kostet nichts."
    assert sprache.pruefe(sprache.glaette(text)) == []


def test_nicht_loesbares_wird_gemeldet_nicht_umgeschrieben() -> None:
    """Fängt eine Glättung, die „, dass …“-Sätze oder Kaskaden kaputt umstellt, statt sie zu melden."""
    text = (
        "Es ist wichtig zu beachten, dass Sie den Antrag stellen. Zudem gibt es Geld. Darüber hinaus Kurse."
    )
    assert sprache.glaette(text) == text
    befunde = {(b.art, b.behebbar) for b in sprache.pruefe(text)}
    assert ("einleitung", False) in befunde and ("kaskade", False) in befunde


def test_satzlaenge_wird_gemessen() -> None:
    """Fängt einen Satz über 25 Wörtern und ein Mittel ab 15 Wörtern, die ohne Befund durchgehen."""
    lang = " ".join(["Wort"] * 26) + "."
    arten = [b.art for b in sprache.pruefe(lang)]
    assert "satz_lang" in arten and "mittel_lang" in arten
    assert sprache.pruefe("Pflegegeld gibt es ab mehr als 65 Stunden Pflege im Monat (BPGG § 4).") == []


@pytest.mark.parametrize("datei", DATEIEN, ids=lambda d: f"{d.parent.name}/{d.name}")
def test_feste_texte_bestehen_sprachpruefung(datei: Path) -> None:
    """Fängt einen festen Text in daten/, stellen/ oder formulare/ mit Gedankenstrich, Schablone oder zu
    langen Sätzen (Owner-Vorgabe: Bürgersprache, kurze Sätze)."""
    funde = [(pfad, b.art, b.stelle) for pfad, text in _texte(_lade(datei)) for b in sprache.pruefe(text)]
    assert funde == []


def test_quelle_steht_im_halbsatz_zitat_und_stand_nur_im_beleg() -> None:
    """Fängt die lange Zeile „Quelle: …, Stand: Fassung ab …“ samt Zitat im Fließtext statt „(BPGG § 4)“."""
    a = kern.Aussage(
        text="Pflegegeld gibt es ab mehr als 65 Stunden Pflege im Monat.",
        zitat="Pflegebedarf im Monat durchschnittlich mehr als 65 Stunden beträgt",
        abschnitt_id=1,
        schluessel="BPGG § 4",
        stand="2015-01-01",
        betrag=False,
        hinweis_hoehe=False,
        treffer={},
    )
    text = kern.setze_text([a], [], [], sprache="de", stil="standard")
    assert text.startswith("Pflegegeld gibt es ab mehr als 65 Stunden Pflege im Monat (BPGG § 4).")
    assert "Quelle:" not in text and "Fassung ab" not in text and "„" not in text
    angebot = sprache.kurze_quelle(
        "Anträge und Formulare/fsw-antrag-auf-foerderung-von-leistungen.1779095804.pdf, S. 5"
    )
    assert angebot == "FSW-Antrag auf Förderung, S. 5"
