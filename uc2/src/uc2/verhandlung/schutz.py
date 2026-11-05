"""Namensschutz für Modelltexte der Verhandlung (#137, Entscheid D6: nicht nur der Prompt schützt).

Jeder Text, den ein Modell schreibt, geht durch `uc2.belege.namen.maskiere_modelltext`, **bevor** er in ein
Ereignis, `uc2.fall`, `uc2.teilnahme` oder `uc2.position` geschrieben wird. Gewählt statt einer Schicht im
Ausgabefilter (`uc2.api.belegfilter`): So gilt der Schutz für SSE, Bericht, Terminal und Replay gleich, PG
enthält keine Namen aus Modelltext, und die nächste Runde sieht im Prompt nur maskierte Texte.

Betroffen sind: im Zug `begruendung`, `bedingungen`, `zugestaendnis` und `zahlen[].einheit` (gekürzt auf
`MAX_EINHEIT`); in der Moderator-Notiz `notiz` und alle Textfelder von `widersprueche[]` und
`belege_eingefordert[]` (auch `akteur` und `thema`, die das Schema nicht auf IDs begrenzt); im Auftrag
`ziel`, `regeln`, Titel und Beschreibung der Themen; in der Auswahl die `begruendung`; dazu die Frage und
Fehlermeldungen ungültiger Ausgaben (sie zitieren Modellwerte). IDs im Zug (Thema, Akteur, Beleg) prüfen
Schema und Code, Zahlen bleiben unverändert.

Die Namensliste lädt der Lauf einmal (`lade_schutz`). Fail-closed: Fehlt sie bei einem echten Provider,
bricht der Lauf vor der Anlage des Falls ab (`SchutzFehler`); das Test-Env `UC2_NAMEN_OHNE_LISTE` gilt dann
nicht, und eine übergebene leere Liste auch nicht (`pruefe_liste`). Bei mock reichen die Muster.
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

MAX_EINHEIT = 60
"""Höchstlänge der Einheit einer Zahl nach dem Maskieren. Kein Schema-Limit: Die Modelle beschreiben die
Einheit oft in einem halben Satz („Prozent Wartezeitänderung, wahrscheinlichster Wert“); ein Limit im
Schema würde gültige Züge verwerfen."""


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
        zahlen = [{**z, "einheit": self.text(z["einheit"])[:MAX_EINHEIT]} for z in zug.get("zahlen", [])]
        return {**zug, "themen": themen, "zahlen": zahlen}

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
        """Moderator-Notiz mit maskierter Notiz und allen Textfeldern der Widersprüche und Belegforderungen.

        `akteur` und `thema` sind dort freie Strings (Schema `NOTIZ_SCHEMA`); IDs wie `sv` oder `stellen` sind
        kleingeschrieben und bleiben durch die Maske unverändert.
        """

        def je(eintraege: list[dict[str, Any]]) -> list[dict[str, Any]]:
            return [{k: self.text(v) if isinstance(v, str) else v for k, v in e.items()} for e in eintraege]

        return {
            **daten,
            "notiz": self.text(daten["notiz"]),
            "widersprueche": je(daten["widersprueche"]),
            "belege_eingefordert": je(daten["belege_eingefordert"]),
        }


def lade_schutz(provider: str) -> Namensschutz:
    """Namensliste aus `UC2_NAMENSLISTE` laden, fail-closed bei echtem Provider.

    Bei `mock` reicht ohne Liste der Schutz mit Mustern (Hinweis auf stderr aus `Namensliste.lade`). Eine
    Liste im Git-Checkout ist immer ein Fehler.
    """
    mock = provider == "mock"
    try:
        liste = Namensliste.lade(erlaube_ohne_liste=mock, env_ohne_liste=mock)
    except (NamenslisteFehlt, NamenslisteImRepo) as fehler:
        raise SchutzFehler(
            f"Modelltexte nur mit Namensliste: Provider {provider!r} braucht UC2_NAMENSLISTE. {fehler}"
        ) from fehler
    return Namensschutz(pruefe_liste(liste, provider))


def pruefe_liste(namen: Namensliste, provider: str) -> Namensliste:
    """Eine leere Liste reicht nur bei mock; bei einem echten Provider `SchutzFehler` (fail-closed)."""
    if provider != "mock" and len(namen) == 0:
        raise SchutzFehler(f"Modelltexte nur mit Namensliste: Provider {provider!r} bekam eine leere Liste.")
    return namen
