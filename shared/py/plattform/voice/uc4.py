"""Voice-Antwort für UC4: die Frage läuft durch ``plattform.router.durchreichen`` (uc3 → uc2 → uc1).

Gesprochen wird je UC ein Satz in Kettenreihenfolge („StatAgent: …“), Belege sind alle Belege der Antworten.
Modelle rufen nur die Adapter der UCs, diese Funktion selbst ruft keines.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from typing import TYPE_CHECKING

from plattform.antwortform import Beleg, UcAntwort
from plattform.router import Adapter, durchreichen, mock_adapter

from .kern import BUDGET_MELDUNG, Sitzung, VoiceAntwort

if TYPE_CHECKING:
    from plattform.llm.basis import Nachricht

#: Namen der Räume wie in der UI-Registry (``shared/ui/src/ucs.ts``).
UC_NAMEN = {"uc1": "SV KI-Lotse", "uc2": "HealthPolicy Simulator", "uc3": "StatAgent"}
OHNE_ANTWORT = "Dazu habe ich noch keine belegte Antwort."

_SATZENDE = re.compile(r"(?<=[.!?])\s")


def letzte_frage(nachrichten: list[Nachricht]) -> str:
    """Inhalt der letzten Nutzer-Nachricht, leer ohne eine."""
    for nachricht in reversed(nachrichten):
        if nachricht.get("role") == "user" and nachricht.get("content", "").strip():
            return nachricht["content"].strip()
    return ""


def _erster_satz(text: str) -> str:
    satz = _SATZENDE.split(text.strip(), maxsplit=1)[0].strip()
    return satz if satz.endswith((".", "!", "?")) else f"{satz}."


def als_voice_antwort(antworten: list[UcAntwort]) -> VoiceAntwort:
    """Je UC ein Satz mit Namen, Belege aller Antworten in Kettenreihenfolge (ohne Doppelte)."""
    saetze = [f"{UC_NAMEN.get(a.uc, a.uc)}: {_erster_satz(a.text)}" for a in antworten if a.text.strip()]
    belege: list[Beleg] = []
    for antwort in antworten:
        belege.extend(beleg for beleg in antwort.belege if beleg not in belege)
    return VoiceAntwort(text=" ".join(saetze) or OHNE_ANTWORT, belege=belege)


def uc4_antwort(*, mock: bool = False) -> Callable[[list[Nachricht], Sitzung], VoiceAntwort]:
    """``antwort``-Funktion für ``erstelle_router``; ``mock`` nimmt die Mock-Adapter des Routers."""
    adapter: dict[str, Adapter] | None = mock_adapter() if mock else None

    def antwort(nachrichten: list[Nachricht], sitzung: Sitzung) -> VoiceAntwort:
        frage = letzte_frage(nachrichten)
        if not frage:
            return VoiceAntwort(text=OHNE_ANTWORT)
        ergebnis = durchreichen(frage, adapter=adapter)
        stimme = als_voice_antwort(ergebnis.antworten)
        # Budget mitten in der Kette verbraucht (#100): sagen statt verschweigen, sonst hört man OHNE_ANTWORT.
        if any(f.grund == "BudgetErschoepft" for f in ergebnis.fehlend):
            text = BUDGET_MELDUNG if stimme.text == OHNE_ANTWORT else f"{stimme.text} {BUDGET_MELDUNG}"
            return VoiceAntwort(text=text, belege=stimme.belege)
        return stimme

    return antwort
