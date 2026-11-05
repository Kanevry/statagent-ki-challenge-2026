"""Allgemeine Fragen im UC4-Adapter: Auftrag des Moderators ohne Rechenmodell und Mock dafür.

Eine allgemeine Frage passt zu keinem Fall in `uc2/faelle/` (etwa „Wie viele Menschen arbeiten im März 2025 in
Wien im Gesundheits- und Sozialwesen?“). Dann rechnet der Experte nichts: Zahlen des Wartezeiten-Pakets unter
einer Beschäftigungsfrage wären irreführend. Der Moderator bekommt statt des Experten die Ausgangslage, also
die Zahlen aus dem Kontext (UC3) mit ihrer Herkunft, und bildet daraus Themen für die Abwägung.

Der Szenario-Mock aus `uc2.modelle.szenario` leitet Themen nur aus dem Maßnahmenpaket ab. Für diesen Auftrag
antwortet deshalb `KurzMock` (Unterklasse des Szenario-Mocks) mit festen, allgemeinen Themen; alle anderen
Rollen beantwortet weiter der Szenario-Mock.
"""

from __future__ import annotations

import json
from typing import Any

from plattform.llm import kern as _kern  # type: ignore[import-untyped]
from plattform.llm.basis import Rohantwort  # type: ignore[import-untyped]

from uc2.modelle.kontext import kontext_block, lies_kontext
from uc2.modelle.szenario import SzenarioMock
from uc2.verhandlung import prompts

ROLLE_AUFTRAG = "moderator_auftrag_allgemein"
MAX_THEMEN = 3
HINWEIS = (
    "Zu dieser Frage gibt es kein Rechenmodell. Zahlen gibt es nur unter `kontext_zahlen`: Sie kommen "
    "aus der amtlichen Statistik (UC3) und tragen ihre Herkunft. Andere Zahlen nennst du nicht."
)

MOCK_THEMEN: tuple[dict[str, str], ...] = (
    {
        "id": "versorgung",
        "titel": "Versorgung im Alltag",
        "beschreibung": "Ob Menschen rasch Hilfe in Praxis, Spital und Pflege bekommen",
    },
    {
        "id": "personal",
        "titel": "Personal und Arbeitsbedingungen",
        "beschreibung": "Genug Fachkräfte in Gesundheit und Pflege, Bezahlung, Ausbildung und Belastung",
    },
    {
        "id": "finanzierung",
        "titel": "Kosten und Finanzierung",
        "beschreibung": "Wer die Kosten trägt: Krankenversicherung, Bund und Länder",
    },
)
"""Feste Themen des Mocks für allgemeine Fragen; ein echtes Modell bildet sie aus der Frage."""


def ausgangslage(kontext_zahlen: list[dict[str, Any]]) -> dict[str, Any]:
    """Block für Prompts statt `prompts.experte_kurz`: Hinweis und Kontextzahlen, kein Rechenmodell."""
    return {"hinweis": HINWEIS, "rechenmodell": None, "kontext_zahlen": kontext_zahlen}


def auftrag_nachrichten(frage: str, experte: dict[str, Any]) -> list[dict[str, str]]:
    """Auftrag des Moderators für eine allgemeine Frage (gleiches Schema wie `prompts.AUFTRAG_SCHEMA`).

    `experte` ist hier die `ausgangslage` (Name wie in `prompts.auftrag_nachrichten`, gleiche Signatur).
    """
    lage = experte
    kontext = {"rolle": ROLLE_AUFTRAG, "frage": frage, "max_themen": MAX_THEMEN, "ausgangslage": lage}
    text = (
        f"# Frage\n{frage}\n\n# Ausgangslage (Zahlen aus der Statistik, Code)\n"
        f"{json.dumps(lage, ensure_ascii=False, indent=1, sort_keys=True)}\n\n"
        "# Aufgabe\nÜbersetze die Frage in einen kurzen Auftrag für eine Abwägung unter "
        f"Interessenvertretungen des Gesundheitswesens: höchstens {MAX_THEMEN} Themen (id in Kleinbuchstaben "
        "mit Unterstrich, Titel, kurze Beschreibung), Regeln für die Runden und das Ziel. Die Themen sollen "
        "zeigen, was die Zahl für Versorgung, Personal und Kosten bedeutet. Erfinde keine Zahlen.\n\n"
        f"{kontext_block(kontext)}"
    )
    return [{"role": "system", "content": prompts.MODERATOR_SYSTEM}, {"role": "user", "content": text}]


def _mock_auftrag(k: dict[str, Any]) -> dict[str, Any]:
    return {
        "themen": [dict(t) for t in MOCK_THEMEN],
        "regeln": [
            "Jede Haltung stützt sich auf einen übergebenen Beleg oder ist als Modellannahme benannt.",
            "Zahlen nur aus der Ausgangslage, keine eigenen Schätzungen.",
            "Ab Runde 2 geht jeder Zug auf mindestens einen anderen Teilnehmer ein.",
        ],
        "ziel": str(k.get("frage") or ""),
    }


class KurzMock(SzenarioMock):
    """Szenario-Mock plus Antwort auf den allgemeinen Auftrag (`ROLLE_AUFTRAG`), deterministisch."""

    def rufe(
        self,
        nachrichten: list[dict[str, str]],
        *,
        schema: dict[str, Any] | None,
        modell: str,
        aufwand: str | None,
        zweck: str,
    ) -> Any:
        erste = next((n["content"] for n in nachrichten if n.get("role") == "user"), "")
        k = lies_kontext(erste)
        if k is None or k.get("rolle") != ROLLE_AUFTRAG:
            return super().rufe(nachrichten, schema=schema, modell=modell, aufwand=aufwand, zweck=zweck)
        text = json.dumps(_mock_auftrag(k), ensure_ascii=False, sort_keys=True)
        return Rohantwort(
            text=text,
            modell=modell,
            version="kurz-1",
            tokens_in=sum(len(n["content"].split()) for n in nachrichten),
            tokens_out=len(text.split()),
        )


def mock_einhaengen() -> object:
    """`KurzMock` als Provider `mock` setzen; gibt den vorigen Eintrag zurück (für `mock_zuruecksetzen`)."""
    instanzen: dict[str, Any] = _kern.INSTANZEN
    vorher = instanzen.get("mock")
    instanzen["mock"] = KurzMock()
    return vorher


def mock_zuruecksetzen(vorher: object) -> None:
    instanzen: dict[str, Any] = _kern.INSTANZEN
    if vorher is None:
        instanzen.pop("mock", None)
    else:
        instanzen["mock"] = vorher
