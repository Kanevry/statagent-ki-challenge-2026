"""Ausgabefilter für Belege: online nur Zitatfelder, nie der ganze Artikeltext.

Zitat statt Volltext, weil die Jury den belegten Satz mit Quelle braucht und der APA-Kopf des Pressespiegels
„persönliche Information“ lautet (Entscheid Lead 58, Owner-Klick #8705). Jede Route von `uc2.api` schickt ihre
Daten durch `daten_fuer_ausgabe`; die CLI-Terminalausgabe ist lokal und bleibt unberührt.

Je Beleg gehen nur `BELEG_FELDER` hinaus, Texte gekürzt auf `MAX_ZEICHEN` an einer Wortgrenze mit „…“. Fehlt
ein `zitat`, entsteht es aus `ausschnitt`, `text_anzeige` oder `text`. Nur mit `KIC_VOLLTEXT_ONLINE=1`
(Standard aus, lokal in der Demo an) kommt zusätzlich `text` ungekürzt.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from typing import Any

MAX_ZEICHEN = 300
BELEG_FELDER = ("beleg_id", "medium", "datum", "monat", "titel", "pdf_seite", "zitat")
"""Felder, die je Beleg online erlaubt sind."""
VOLLTEXT_FELDER = frozenset({"text", "text_modell", "text_anzeige", "ausschnitt"})
ZITAT_QUELLEN = ("zitat", "ausschnitt", "text_anzeige", "text")
"""Woraus `zitat` entsteht, in dieser Reihenfolge."""
_MERKMALE = frozenset(BELEG_FELDER) - {"beleg_id"} | VOLLTEXT_FELDER
SCHALTER = "KIC_VOLLTEXT_ONLINE"
ONLINE_SCHALTER = ("KIC_ONLINE", "KIC_ONLINE_LESEND")
"""Mit einem dieser Schalter auf `1` gilt die Ausgabe als öffentlich (Online-Demo)."""
FREIGABE_OEFFENTLICH = ("entscheidung", "zeit")
"""Von der Freigabe eines Berichts gehen öffentlich nur Entscheidung und Zeit hinaus, nie Name oder Grund."""


def volltext_online() -> bool:
    """`KIC_VOLLTEXT_ONLINE=1` schaltet den Volltext frei; gelesen bei jeder Anfrage."""
    return os.environ.get(SCHALTER) == "1"


def oeffentlich() -> bool:
    """`True`, wenn `KIC_ONLINE=1` oder `KIC_ONLINE_LESEND=1` gesetzt ist; gelesen bei jeder Anfrage."""
    return any(os.environ.get(name, "").strip() == "1" for name in ONLINE_SCHALTER)


def kuerze(text: str, n: int = MAX_ZEICHEN) -> str:
    """Höchstens `n` Zeichen; länger wird an der letzten Wortgrenze geschnitten und mit „…“ beendet."""
    if len(text) <= n:
        return text
    kopf = text[: n - 1]
    grenze = kopf.rfind(" ")
    if grenze > 0:
        kopf = kopf[:grenze]
    return kopf.rstrip() + "…"


def ist_beleg(knoten: Mapping[str, Any]) -> bool:
    """Ein Objekt mit `beleg_id` und mindestens einem Beleg-Merkmal (Medium, Titel, Text …).

    Prüfereignisse wie `zitat` oder `beleg_ungueltig` tragen nur `beleg_id` neben eigenen Feldern und bleiben
    so unverändert.
    """
    return isinstance(knoten.get("beleg_id"), str) and any(k in knoten for k in _MERKMALE)


def beleg_fuer_ausgabe(beleg: Mapping[str, Any], volltext: bool | None = None) -> dict[str, Any]:
    """Ein Beleg mit nur den erlaubten Feldern; Texte auf `MAX_ZEICHEN` gekürzt."""
    volltext = volltext_online() if volltext is None else volltext
    aus: dict[str, Any] = {}
    for feld in BELEG_FELDER:
        if feld == "zitat":
            quelle = next(
                (beleg[q] for q in ZITAT_QUELLEN if isinstance(beleg.get(q), str) and beleg[q]), None
            )
            if quelle is not None:
                aus["zitat"] = kuerze(quelle)
        elif feld in beleg:
            wert = beleg[feld]
            aus[feld] = kuerze(wert) if isinstance(wert, str) else wert
    if volltext and isinstance(beleg.get("text"), str):
        aus["text"] = beleg["text"]
    return aus


def daten_fuer_ausgabe(knoten: Any, volltext: bool | None = None) -> Any:
    """Rekursiv über JSON-Daten: Belege auf Zitatfelder, Volltextfelder außerhalb von Belegen entfernt.

    Erfasst Belege an jeder Stelle (Ereignis `belege`, Züge im Bericht, Auswahl, Moderator-Notizen).
    `text_modell` und `text_anzeige` fallen überall weg, `ausschnitt` wird gekürzt.
    """
    volltext = volltext_online() if volltext is None else volltext
    if isinstance(knoten, Mapping):
        if ist_beleg(knoten):
            return beleg_fuer_ausgabe(knoten, volltext)
        aus: dict[str, Any] = {}
        for k, v in knoten.items():
            if k in ("text_modell", "text_anzeige"):
                continue
            if k == "ausschnitt" and isinstance(v, str):
                aus[k] = kuerze(v)
            else:
                aus[k] = daten_fuer_ausgabe(v, volltext)
        return aus
    if isinstance(knoten, list | tuple):
        return [daten_fuer_ausgabe(v, volltext) for v in knoten]
    return knoten


def ereignis_fuer_ausgabe(ereignis: Mapping[str, Any], volltext: bool | None = None) -> dict[str, Any]:
    """Ein Ereignis aus `uc2.ereignis` für SSE: Kopf unverändert, `daten` gefiltert."""
    return {**ereignis, "daten": daten_fuer_ausgabe(ereignis.get("daten") or {}, volltext)}


def bericht_fuer_ausgabe(
    bericht: Mapping[str, Any], volltext: bool | None = None, anonym: bool | None = None
) -> Any:
    """Der Bericht eines Falls für die Ausgabe: Belegfilter, dazu der Personenschutz der Freigabe.

    Öffentlich (`oeffentlich()`) bleibt von `freigabe` nur „freigegeben am <Zeit>“ bzw. „abgelehnt am <Zeit>“:
    `name` und `begruendung` fallen weg. Lokal bleibt die Freigabe vollständig.
    """
    aus = daten_fuer_ausgabe(bericht, volltext)
    versteckt = oeffentlich() if anonym is None else anonym
    freigabe = aus.get("freigabe") if isinstance(aus, dict) else None
    if versteckt and isinstance(freigabe, dict):
        aus["freigabe"] = {k: v for k, v in freigabe.items() if k in FREIGABE_OEFFENTLICH}
    return aus
