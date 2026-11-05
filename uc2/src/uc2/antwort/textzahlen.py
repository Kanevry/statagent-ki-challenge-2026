"""Zahlen im Text der UC2-Antwort prüfen und unbelegte entfernen (#103, Review zu !73).

Jede Zifferngruppe im Text muss zu einem Eintrag in `zahlen` passen:

- gleicher Wert auf `TOLERANZ` (aus `uc2.verhandlung.pruefungen`),
- gleiches Vorzeichen („−22,24 %“ passt zu −22,24, „22,24 %“ nicht),
- gleiche Einheit direkt dahinter („135.790 Personen“ passt zu `einheit="Personen"`, „135.790 fehlende
  Stellen“ nicht); hat der Eintrag keine Einheit, muss ein Wort seiner Bezeichnung im selben Satzteil
  stehen („40 von 64 durchgerechneten Annahmen“).

Ausgenommen sind nur echte Jahresangaben ohne Mengeneinheit dahinter: „2025“ allein, „im Jahr 2025“,
„bis 2030“, „März 2025“, „2025-03“. „2025 Stellen“ ist eine Menge, ebenso eine Jahreszahl, auf die ohne
Zeitwort davor ein Hauptwort folgt („2025 Pflegekräfte“).

`bereinige` ersetzt jede freie Zahl über ihre Trefferposition (Vorzeichen, Ziffern, Einheit) durch `ERSATZ`;
`freie_zahlen` nennt sie. Ziffern direkt nach einem Buchstaben („Ö1“, „H5N1“) gelten als Teil eines Namens.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Sequence

# plattform hat keinen py.typed-Marker (E0); wie in uc2.modelle.
from plattform.antwortform import Zahl  # type: ignore[import-untyped]

from uc2.verhandlung.pruefungen import EINHEIT, JAHRE, TOLERANZ, zahlwert

ERSATZ = "(Zahl ohne Beleg entfernt)"
GEDANKENSTRICH = re.compile(r"\s*[–—]\s*")

_ZAHL = re.compile(r"(?<![\w.,])\d+(?:[.,]\d+)*")
"""Vollständige Zifferngruppe wie `pruefungen.ZIFFERN`, aber nie direkt nach einem Buchstaben."""
_VORZEICHEN = re.compile(r"(?:(?<!\w)([−+-])|(?<!\w)(minus|plus)\s+)$", re.IGNORECASE)
"""Vorzeichen direkt vor der Zahl; ein Bindestrich nach einem Wort („Covid-19“) ist keines."""
_MONAT_NACH_JAHR = re.compile(r"-(?:0[1-9]|1[0-2])(?!\w|[.,]\d)")
_MONATE = "Jänner|Januar|Februar|März|April|Mai|Juni|Juli|August|September|Oktober|November|Dezember"
_JAHR_DAVOR = re.compile(
    rf"(?<!\w)(?:im|Jahr|Jahre|Jahres|bis|ab|seit|von|vor|nach|zum|um|Ende|Anfang|Mitte|{_MONATE})\s+$",
    re.IGNORECASE,
)
_HAUPTWORT_DANACH = re.compile(r"\s+[A-ZÄÖÜ]")
_GLEICHE_EINHEIT: dict[str, tuple[str, ...]] = {
    "%": ("%", "Prozent"),
    "EUR": ("EUR", "€", "Euro"),
    "Mio EUR": ("Mio EUR", "Mio. EUR", "Mio €", "Mio. €", "Mio Euro", "Mio. Euro", "Millionen Euro"),
}
"""Schreibweisen, die als dieselbe Einheit gelten; sonst muss die Einheit wörtlich dastehen."""
_WORT = re.compile(r"[^\W\d_]{5,}")
_SATZGRENZE = re.compile(r"[;!?\n()]|\.(?!\d)")
_WOERTER_DAVOR = 6
_WOERTER_DANACH = 4
_FENSTER = 80


def _schreibweisen(einheit: str) -> tuple[str, ...]:
    return _GLEICHE_EINHEIT.get(einheit, (einheit,))


def _als_muster(schreibweisen: Sequence[str]) -> str:
    """Alternativen, längste zuerst; eine Einheit aus Buchstaben endet an einer Wortgrenze."""
    teile = [
        re.escape(s) + (r"(?!\w)" if s[-1].isalnum() else "")
        for s in sorted(set(schreibweisen), key=len, reverse=True)
    ]
    return "|".join(teile)


def _einheit_muster(einheit: str) -> re.Pattern[str]:
    return re.compile(rf"\s?(?:{_als_muster(_schreibweisen(einheit))})")


def _mengen_muster(zahlen: Sequence[Zahl]) -> re.Pattern[str]:
    """Jede bekannte Mengeneinheit: `EINHEIT` und die Einheiten der Antwort mit ihren Schreibweisen."""
    eigene = [s for z in zahlen if z.einheit for s in _schreibweisen(z.einheit)]
    if not eigene:
        return EINHEIT
    return re.compile(rf"\s?(?:{_als_muster(eigene)})|{EINHEIT.pattern}")


def _staemme(text: str) -> set[str]:
    return {w.casefold()[:6] for w in _WORT.findall(text)}


def _umfeld(text: str, start: int, ende: int) -> str:
    """Wörter im selben Satzteil vor und nach der Zahl (für Einträge ohne Einheit)."""
    davor = _SATZGRENZE.split(text[max(0, start - _FENSTER) : start])[-1]
    danach = _SATZGRENZE.split(text[ende : ende + _FENSTER])[0]
    return " ".join(_WORT.findall(davor)[-_WOERTER_DAVOR:] + _WORT.findall(danach)[:_WOERTER_DANACH])


def _vorzeichen(text: str, start: int) -> tuple[float, int]:
    """Faktor (−1 oder 1) und Beginn der Zahl samt Vorzeichen."""
    stueck = text[max(0, start - 8) : start]
    treffer = _VORZEICHEN.search(stueck)
    if treffer is None:
        return 1.0, start
    zeichen = (treffer.group(1) or treffer.group(2)).casefold()
    faktor = -1.0 if zeichen in ("−", "-", "minus") else 1.0
    return faktor, start - (len(stueck) - treffer.start())


def _ist_jahr(text: str, start: int, ende: int) -> bool:
    """Jahreszahl ohne Mengeneinheit: Zeitwort davor („bis“, „im Jahr“, Monat) oder kein Hauptwort danach."""
    if _JAHR_DAVOR.search(text[max(0, start - 20) : start]):
        return True
    return _HAUPTWORT_DANACH.match(text, ende) is None


def _passt(zahl: Zahl, wert: float, text: str, start: int, ende: int, menge: re.Pattern[str]) -> bool:
    if abs(wert - float(zahl.wert)) > TOLERANZ:
        return False
    if zahl.einheit:
        if _einheit_muster(zahl.einheit).match(text, ende) is not None:
            return True
        # „135.790 Beschäftigte“ zur Zahl „Beschäftigte (…)“ mit Einheit „Personen“: ein Wort der Bezeichnung
        # direkt nach der Zahl zählt wie die Einheit; eine andere Mengeneinheit nie.
        if menge.match(text, ende) is not None:
            return False
        danach = _WORT.match(text, ende + 1) if text[ende : ende + 1] == " " else None
        return danach is not None and bool(_staemme(danach.group(0)) & _staemme(zahl.bezeichnung))
    if menge.match(text, ende) is not None:
        return False
    return bool(_staemme(zahl.bezeichnung) & _staemme(_umfeld(text, start, ende)))


def profilzahlen(texte: Iterable[str]) -> frozenset[str]:
    """Zifferngruppen aus Akteursprofilen (z. B. die Gesundheitshotline „1450“): Namen, keine Messwerte."""
    return frozenset(m.group(0) for t in texte for m in _ZAHL.finditer(t))


def _freie_stellen(
    text: str, zahlen: Sequence[Zahl], profil: frozenset[str] = frozenset()
) -> list[tuple[int, int]]:
    """Spannen (Beginn, Ende) der Zahlen ohne passenden Eintrag, je mit Vorzeichen und Einheit.

    Eine Zifferngruppe ohne Einheit, die wörtlich im Profil eines Teilnehmers steht (`profil`), ist ein Name
    wie eine Telefonnummer und bleibt stehen; mit Mengeneinheit gilt sie als Zahl und wird geprüft."""
    menge = _mengen_muster(zahlen)
    frei: list[tuple[int, int]] = []
    weiter_ab = 0
    for m in _ZAHL.finditer(text):
        if m.start() < weiter_ab:
            continue
        gruppe = m.group(0)
        einheit = menge.match(text, m.end())
        if einheit is None and gruppe in profil:
            continue
        if einheit is None and gruppe.isdigit() and int(gruppe) in JAHRE:
            monat = _MONAT_NACH_JAHR.match(text, m.end())
            if monat is not None:
                weiter_ab = monat.end()
                continue
            if _ist_jahr(text, m.start(), m.end()):
                continue
        faktor, beginn = _vorzeichen(text, m.start())
        wert = zahlwert(gruppe)
        if wert is not None and any(_passt(z, faktor * wert, text, beginn, m.end(), menge) for z in zahlen):
            continue
        ende = einheit.end() if einheit is not None else m.end()
        frei.append((beginn, ende))
        weiter_ab = ende
    return frei


def freie_zahlen(text: str, zahlen: Sequence[Zahl], profil: frozenset[str] = frozenset()) -> list[str]:
    """Zahlen im Text, die mit Wert, Vorzeichen und Einheit zu keinem Eintrag in `zahlen` passen."""
    return [text[a:e] for a, e in _freie_stellen(text, zahlen, profil)]


def bereinige(text: str, zahlen: Sequence[Zahl], profil: frozenset[str] = frozenset()) -> str:
    """Gedankenstriche durch Kommas, dann jede freie Zahl an ihrer Position durch `ERSATZ` ersetzen.

    Erst die Striche: Ein „–20 %“ wird so zu „, 20 %“ und als positive Zahl geprüft, nie als belegtes −20.
    """
    text = GEDANKENSTRICH.sub(", ", text)
    teile: list[str] = []
    pos = 0
    for anfang, ende in _freie_stellen(text, zahlen, profil):
        teile += [text[pos:anfang], ERSATZ]
        pos = ende
    teile.append(text[pos:])
    return "".join(teile)
