"""Namensschutz für Modelltexte der Verhandlung (#137, Entscheid D6: nicht nur der Prompt schützt).

Jeder Text, den ein Modell schreibt, geht durch `uc2.belege.namen.maskiere_modelltext`, **bevor** er in ein
Ereignis, `uc2.fall`, `uc2.teilnahme` oder `uc2.position` geschrieben wird. Gewählt statt einer Schicht im
Ausgabefilter (`uc2.api.belegfilter`): So gilt der Schutz für SSE, Bericht, Terminal und Replay gleich, PG
enthält keine Namen aus Modelltext, und die nächste Runde sieht im Prompt nur maskierte Texte.

Betroffen sind: im Zug `begruendung`, `bedingungen`, `zugestaendnis`; in der Moderator-Notiz `notiz`,
`widersprueche[].beschreibung`, `belege_eingefordert[].grund`; im Auftrag `ziel`, `regeln`, Titel und
Beschreibung der Themen; in der Auswahl die `begruendung`; dazu die Frage und Fehlermeldungen ungültiger
Ausgaben (sie zitieren Modellwerte). IDs (Thema, Akteur, Beleg) und Zahlen bleiben unverändert.

Die Namensliste lädt der Lauf einmal (`lade_schutz`). Fail-closed: Fehlt sie bei einem echten Provider,
bricht der Lauf vor der Anlage des Falls ab (`SchutzFehler`). Bei mock reichen die Muster.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from uc2.belege.namen import (
    Institutionen,
    Namensliste,
    NamenslisteFehlt,
    NamenslisteImRepo,
    lade_institutionen,
    maskiere_modelltext,
)


class SchutzFehler(RuntimeError):
    """Ohne Namensliste darf kein echtes Modell laufen: Modelltexte wären nur mit Mustern geschützt."""


@dataclass
class Namensschutz:
    """Maskiert Modelltexte mit einer einmal geladenen Namensliste."""

    namen: Namensliste
    institutionen: Institutionen = field(default_factory=lade_institutionen)

    def text(self, wert: str) -> str:
        return maskiere_modelltext(wert, self.namen, self.institutionen)

    def _liste(self, werte: list[str]) -> list[str]:
        return [self.text(w) for w in werte]

    def zug(self, zug: dict[str, Any]) -> dict[str, Any]:
        """Zug mit maskierter Begründung, Bedingungen und Zugeständnis je Thema."""
        themen = []
        for t in zug["themen"]:
            zugestaendnis = t["zugestaendnis"]
            themen.append(
                {
                    **t,
                    "begruendung": self.text(t["begruendung"]),
                    "bedingungen": self._liste(t["bedingungen"]),
                    "zugestaendnis": self.text(zugestaendnis) if zugestaendnis else zugestaendnis,
                }
            )
        return {**zug, "themen": themen}

    def auftrag(self, auftrag: dict[str, Any]) -> dict[str, Any]:
        """Auftrag mit maskiertem Ziel, Regeln, Thementitel und -beschreibung."""
        return {
            **auftrag,
            "themen": [
                {**t, "titel": self.text(t["titel"]), "beschreibung": self.text(t["beschreibung"])}
                for t in auftrag["themen"]
            ],
            "regeln": self._liste(auftrag["regeln"]),
            "ziel": self.text(auftrag["ziel"]),
        }

    def auswahl(self, eintraege: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Auswahl je Akteur mit maskierter Begründung."""
        return [{**a, "begruendung": self.text(a["begruendung"])} for a in eintraege]

    def notiz(self, daten: dict[str, Any]) -> dict[str, Any]:
        """Moderator-Notiz mit maskierter Notiz, Widerspruchsbeschreibung und Grund eingeforderter Belege."""

        def je(eintraege: list[dict[str, Any]], feld: str) -> list[dict[str, Any]]:
            return [{**e, feld: self.text(e[feld])} for e in eintraege]

        return {
            **daten,
            "notiz": self.text(daten["notiz"]),
            "widersprueche": je(daten["widersprueche"], "beschreibung"),
            "belege_eingefordert": je(daten["belege_eingefordert"], "grund"),
        }


def lade_schutz(provider: str) -> Namensschutz:
    """Namensliste aus `UC2_NAMENSLISTE` laden, fail-closed bei echtem Provider.

    Bei `mock` reicht ohne Liste der Schutz mit Mustern (Hinweis auf stderr aus `Namensliste.lade`). Eine
    Liste im Git-Checkout ist immer ein Fehler.
    """
    try:
        return Namensschutz(Namensliste.lade(erlaube_ohne_liste=provider == "mock"))
    except (NamenslisteFehlt, NamenslisteImRepo) as fehler:
        raise SchutzFehler(
            f"Modelltexte nur mit Namensliste: Provider {provider!r} braucht UC2_NAMENSLISTE. {fehler}"
        ) from fehler
