"""mock (Tests, CI, Jury ohne Netz): Antworten aus ``fixtures/<zweck>.json``, deterministisch.

Fixture-Format::

    {"modell": "mock", "antworten": [{"text": "..."}, {"json": {...}}]}

Aufruf n eines Zwecks liefert ``antworten[n-1]``; nach der letzten bleibt es bei der letzten. So lassen
sich Folgen für Fault-Tests bauen (erst ungültig, dann gültig). ``PLATTFORM_FIXTURES`` zeigt auf einen
anderen Ordner. ``zuruecksetzen()`` setzt die Aufrufzähler auf null.
"""

from __future__ import annotations

import json
import os
import threading
from pathlib import Path
from typing import Any

from .basis import FixtureFehlt, Nachricht, Provider, Rohantwort

STANDARD_ORDNER = Path(__file__).resolve().parent.parent / "fixtures"

_ZAEHLER: dict[Path, int] = {}
_SPERRE = threading.Lock()


def zuruecksetzen() -> None:
    with _SPERRE:
        _ZAEHLER.clear()


def fixture_pfad(zweck: str) -> Path:
    ordner = Path(os.environ.get("PLATTFORM_FIXTURES") or STANDARD_ORDNER)
    return ordner / f"{zweck or 'standard'}.json"


class MockProvider(Provider):
    name = "mock"
    deterministisch = True

    def standard_modell(self, groesse: str) -> str:
        return "mock"

    def rufe(
        self,
        nachrichten: list[Nachricht],
        *,
        schema: dict[str, Any] | None,
        modell: str,
        aufwand: str | None,
        zweck: str,
    ) -> Rohantwort:
        pfad = fixture_pfad(zweck)
        if not pfad.is_file():
            raise FixtureFehlt(f"mock: keine Fixture für Zweck {zweck or 'standard'!r} ({pfad.name})")
        daten = json.loads(pfad.read_text(encoding="utf-8"))
        antworten = daten["antworten"]
        with _SPERRE:
            nummer = _ZAEHLER.get(pfad, 0)
            _ZAEHLER[pfad] = nummer + 1
        eintrag = antworten[min(nummer, len(antworten) - 1)]
        if "json" in eintrag:
            text = json.dumps(eintrag["json"], ensure_ascii=False, sort_keys=True)
        else:
            text = eintrag["text"]
        return Rohantwort(
            text=text,
            modell=daten.get("modell", "mock"),
            version=daten.get("version", "fixture"),
            tokens_in=sum(len(n["content"].split()) for n in nachrichten),
            tokens_out=len(text.split()),
        )
