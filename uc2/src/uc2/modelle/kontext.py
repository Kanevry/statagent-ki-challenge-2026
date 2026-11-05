"""Maschinenlesbarer Kontextblock in der User-Nachricht jedes UC2-Modellaufrufs.

Der Block nennt Rolle, Akteur, Runde, Themen, verfügbare Beleg-IDs und Experten-Zahlen als JSON. Echte
Modelle lesen ihn als Zusammenfassung, der Szenario-Mock antwortet allein daraus. Belegtexte stehen nie
darin; Marker in Belegtexten entschärft `entschaerfe`, damit ein Beleg keinen Block vortäuschen kann.
"""

from __future__ import annotations

import json
from typing import Any

START = "<<<KONTEXT"
ENDE = "KONTEXT>>>"


def kontext_block(daten: dict[str, Any]) -> str:
    """Kontext als markierter Block (kanonisches JSON, feste Schlüsselreihenfolge)."""
    text = json.dumps(daten, ensure_ascii=False, sort_keys=True, indent=1)
    return f"{START}\n{text}\n{ENDE}"


def lies_kontext(text: str) -> dict[str, Any] | None:
    """Letzten Kontextblock aus einer Nachricht lesen; `None`, wenn keiner oder kein gültiges JSON."""
    anfang = text.rfind(START + "\n")
    if anfang < 0:
        return None
    ende = text.find("\n" + ENDE, anfang)
    if ende < 0:
        return None
    try:
        daten = json.loads(text[anfang + len(START) + 1 : ende])
    except json.JSONDecodeError:
        return None
    return daten if isinstance(daten, dict) else None


def entschaerfe(text: str) -> str:
    """Block-Marker (`<<<`, `>>>`) in fremdem Text unschädlich machen."""
    return text.replace("<<<", "‹‹‹").replace(">>>", "›››")
