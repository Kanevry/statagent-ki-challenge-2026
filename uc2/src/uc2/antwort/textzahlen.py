"""Zahlen im Text der UC2-Antwort prüfen und unbelegte entfernen (#103, Review zu !73).

Jede Zifferngruppe im Text muss zu einem Eintrag in `zahlen` passen:

- gleicher Wert auf `TOLERANZ` (aus `uc2.verhandlung.pruefungen`),
- gleiches Vorzeichen („−22,24 %“ passt zu −22,24, „22,24 %“ nicht),
- gleiche Einheit direkt dahinter, in einer festen Schreibweise oder einem festen Alias der Einheit
  (`_GLEICHE_EINHEIT`: „135.790 Beschäftigte“ passt zu `einheit="Personen"`, „135.790 fehlende Stellen“ und
  „135.790 Gesundheitszentren“ nicht); hat der Eintrag keine Einheit, muss ein Wort seiner Bezeichnung im
  selben Satzteil stehen („40 von 64 durchgerechneten Annahmen“),
- derselbe Begriff: Steht im Satzteil ein Kennwort (`_KENNWORTE`: Wartezeit, Kosten, Stellen, Beschäftigte),
  gilt das nächstgelegene als Begriff der Zahl; es muss auch in der Bezeichnung stehen („−20 % Mehrkosten“
  passt nicht zum Ziel „Wartezeitänderung“).

Ausgenommen sind nur echte Jahresangaben ohne Mengeneinheit dahinter, und nur mit Zeitkontext: ein Zeitwort
davor („im Jahr 2025“, „bis 2030“, „März 2025“), „2025-03“ oder ein Satzanfang mit Verb danach („2025 wurde
…“). Ohne Zeitkontext ist eine Jahreszahl eine Menge („Es fehlen 2025 zusätzliche Pflegekräfte“).

Zifferngruppen aus Akteursprofilen (`profilzahlen`, z. B. die Gesundheitshotline „1450“) bleiben nur stehen,
wenn sie wie im Profil benannt sind: dasselbe Wort direkt davor, oder „Hotline“, „Telefon“, „Nummer“,
„über“, „unter“; danach weder Mengeneinheit noch Hauptwort („Es fehlen 1450 Pflegekräfte“ wird geprüft).

`bereinige` ersetzt jede freie Zahl über ihre Trefferposition (Vorzeichen, Ziffern, Einheit) durch `ERSATZ`;
`freie_zahlen` nennt sie. Ziffern direkt nach einem Buchstaben („Ö1“, „H5N1“) gelten als Teil eines Namens.
"""

from __future__ import annotations

import re
from collections.abc import Collection, Iterable, Mapping, Sequence

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
    rf"(?<!\w)(?:im|seit|bis|ab|Jahr|Jahres|von|zwischen|vor|nach|Ende|Anfang|Mitte|{_MONATE}"
    r"|zwischen\s+\d{4}\s+und)\s+$",
    re.IGNORECASE,
)
"""Zeitkontext direkt vor einer Jahreszahl; „zwischen 2025 und 2030“ auch für die zweite."""
_VERB_DANACH = re.compile(
    r"\s+(?:wurde|wurden|war|waren|gab|gibt|ist|sind|hat|hatte|hatten|haben|wird|werden|kam|kamen|lag|lagen"
    r"|stieg|stiegen|sank|sanken|begann|endete|brachte|zeigte|soll|sollen|bleibt|blieb)(?!\w)"
)
"""Verb nach einer Jahreszahl am Satzanfang („2025 wurde …“, „2025 gab es …“)."""
_HAUPTWORT_DANACH = re.compile(r"\s+[A-ZÄÖÜ]")
_GLEICHE_EINHEIT: dict[str, tuple[str, ...]] = {
    "%": ("%", "Prozent"),
    "EUR": ("EUR", "€", "Euro"),
    "Mio EUR": ("Mio EUR", "Mio. EUR", "Mio €", "Mio. €", "Mio Euro", "Mio. Euro", "Millionen Euro"),
    "Personen": (
        "Personen",
        "Beschäftigte",
        "Beschäftigten",
        "Beschäftigungsverhältnisse",
        "Menschen",
        "Arbeitskräfte",
        "Erwerbstätige",
    ),
}
"""Feste Schreibweisen und Aliasse je Einheit; sonst muss die Einheit wörtlich dastehen."""
_KENNWORTE: dict[str, tuple[str, ...]] = {
    "wartezeit": ("wartezeit",),
    "kosten": ("kosten", "ausgaben"),
    "stellen": ("stellen",),
    "beschaeftigte": ("beschäftig",),
}
"""Begriffe, denen eine Zahl im Text zugeordnet sein kann; Teilwort eines großgeschriebenen Worts."""
_HAUPTWORT = re.compile(r"(?<!\w)[A-ZÄÖÜ][^\W\d_]+")
_WORT = re.compile(r"[^\W\d_]{5,}")
_VORWORT = re.compile(
    r"(?<![^\W\d_])(?!(?:und|oder)(?!\w))([^\W\d_]+)(?:\s*,\s*|\s+(?:und|oder)\s+)*\s*$", re.IGNORECASE
)
"""Wort direkt vor einer Zahl; Komma, „und“ und „oder“ dazwischen zählen nicht („ELGA, 1450“)."""
_SATZGRENZE = re.compile(r"[;!?\n()]|\.(?!\d)")
_SATZTEILGRENZE = re.compile(r"[;!?\n()]|[.,](?!\d)")
_PROFIL_VORWORT = frozenset({"über", "unter"})
_PROFIL_ENDUNG = ("hotline", "telefon", "nummer")
"""Wörter vor einer Profilzahl, die sie immer als Name ausweisen („Hotline 1450“, „Rufnummer 1450“)."""
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


def _gruppen(woerter: Iterable[str]) -> set[str]:
    """Kennwort-Gruppen großgeschriebener Wörter („Mehrkosten“ → kosten, „Wartezeitänderung“ → wartezeit)."""
    return {
        gruppe
        for wort in woerter
        for gruppe, teile in _KENNWORTE.items()
        if any(teil in wort.casefold() for teil in teile)
    }


def _begriff(text: str, start: int, ende: int) -> str | None:
    """Kennwort-Gruppe des nächstgelegenen Kennworts im Satzteil um die Zahl; bei gleichem Abstand das danach.

    `ende` liegt hinter der Einheit, die Einheit selbst zählt nicht als Begriff."""
    davor = _SATZTEILGRENZE.split(text[max(0, start - _FENSTER) : start])[-1]
    danach = _SATZTEILGRENZE.split(text[ende : ende + _FENSTER])[0]
    kandidaten: list[tuple[int, int, str]] = []
    for m in _HAUPTWORT.finditer(danach):
        kandidaten += [(m.start(), 0, g) for g in sorted(_gruppen([m.group(0)]))]
    for m in _HAUPTWORT.finditer(davor):
        kandidaten += [(len(davor) - m.end(), 1, g) for g in sorted(_gruppen([m.group(0)]))]
    return min(kandidaten)[2] if kandidaten else None


def _gleicher_begriff(zahl: Zahl, text: str, start: int, ende: int) -> bool:
    begriff = _begriff(text, start, ende)
    return begriff is None or begriff in _gruppen(_HAUPTWORT.findall(zahl.bezeichnung))


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
    """Jahreszahl nur mit Zeitkontext: Zeitwort davor („bis“, „im Jahr“, Monat) oder Satzanfang mit Verb."""
    if _JAHR_DAVOR.search(text[max(0, start - 30) : start]):
        return True
    davor = text[:start].rstrip(" \t")
    satzanfang = not davor or davor[-1] in ".!?:\n"
    return satzanfang and _VERB_DANACH.match(text, ende) is not None


#: Einheiten, die nur „Stück“ meinen (UC3 liefert „Anzahl“): im Text steht die Zahl ohne Einheit.
OHNE_EINHEIT = frozenset({"anzahl"})


def sichtbare_einheit(einheit: str | None) -> str | None:
    """Einheit für den Text; „Anzahl“ und ähnliche Zählwörter entfallen („7.498“, nicht „7.498 Anzahl“)."""
    return None if not einheit or einheit.strip().casefold() in OHNE_EINHEIT else einheit


def _passt(zahl: Zahl, wert: float, text: str, start: int, ende: int, menge: re.Pattern[str]) -> bool:
    if abs(wert - float(zahl.wert)) > TOLERANZ:
        return False
    if zahl.einheit:
        if (
            not sichtbare_einheit(zahl.einheit)
            and zahl.bezeichnung in text[text.rfind("\n", 0, start) + 1 : start]
        ):
            # Zählwert („Anzahl“) ohne sichtbare Einheit: belegt, wenn seine volle Bezeichnung in derselben
            # Zeile davor steht, wie in der Ausgangslage des Adapters („Beschäftigte (Wien, …): 7.498“).
            return True
        if not sichtbare_einheit(zahl.einheit) and text.startswith(
            f" {zahl.bezeichnung.split(' (', 1)[0]}", ende
        ):
            # Oder ihr Wort direkt dahinter, wie im Bezugssatz („7.498 Beschäftigungsverhältnisse“).
            return True
        # Nur die Einheit in einer ihrer festen Schreibweisen („135.790 Beschäftigte“ für „Personen“), nie ein
        # beliebiges Wort der Bezeichnung („135.790 Gesundheitszentren“ über „Gesundheits- und Sozialwesen“).
        einheit = _einheit_muster(zahl.einheit).match(text, ende)
        return einheit is not None and _gleicher_begriff(zahl, text, start, einheit.end())
    if menge.match(text, ende) is not None:
        return False
    if not _staemme(zahl.bezeichnung) & _staemme(_umfeld(text, start, ende)):
        return False
    return _gleicher_begriff(zahl, text, start, ende)


Profil = Mapping[str, Collection[str]]
"""Zifferngruppe aus einem Akteursprofil → Wörter (casefold), die im Profil direkt davor stehen."""


def _vorwort(text: str, start: int) -> str | None:
    """Wort direkt vor der Zahl (casefold), über Komma, „und“, „oder“ hinweg; im Profil wie im Text."""
    treffer = _VORWORT.search(text[max(0, start - _FENSTER) : start])
    return treffer.group(1).casefold() if treffer is not None else None


def profilzahlen(texte: Iterable[str]) -> dict[str, frozenset[str]]:
    """Zifferngruppen aus Akteursprofilen (z. B. die Gesundheitshotline „1450“) mit dem Wort direkt davor.

    Aus „Hausärzte und 1450“ wird „hausärzte“, aus „über ELGA, 1450“ wird „elga“ (`_vorwort`)."""
    davor: dict[str, set[str]] = {}
    for t in texte:
        for m in _ZAHL.finditer(t):
            eintrag = davor.setdefault(m.group(0), set())
            if (wort := _vorwort(t, m.start())) is not None:
                eintrag.add(wort)
    return {gruppe: frozenset(woerter) for gruppe, woerter in davor.items()}


def _ist_profilname(text: str, start: int, ende: int, profil: Profil) -> bool:
    """Profilzahl wie im Profil benannt („Hotline 1450“, „über 1450“), danach kein Hauptwort."""
    vorwoerter = profil.get(text[start:ende])
    if vorwoerter is None or _HAUPTWORT_DANACH.match(text, ende) is not None:
        return False
    wort = _vorwort(text, start)
    if wort is None:
        return False
    return wort in vorwoerter or wort in _PROFIL_VORWORT or wort.endswith(_PROFIL_ENDUNG)


_ALTERSETIKETT = re.compile(r"(?:unter |ab )?\d+(?: bis \d+)? Jahre(?: und älter)?")


def _in_altersetikett(text: str, start: int, ende: int, zahlen: Sequence[Zahl]) -> bool:
    """Grenze einer Altersgruppe, wie sie in der Bezeichnung einer Zahl steht („unter 25 Jahre“)."""
    for zahl in zahlen:
        for etikett in _ALTERSETIKETT.findall(zahl.bezeichnung):
            stelle = text.find(etikett, max(0, start - len(etikett)))
            if 0 <= stelle <= start and ende <= stelle + len(etikett):
                return True
    return False


def _freie_stellen(text: str, zahlen: Sequence[Zahl], profil: Profil | None = None) -> list[tuple[int, int]]:
    """Spannen (Beginn, Ende) der Zahlen ohne passenden Eintrag, je mit Vorzeichen und Einheit.

    Eine Zifferngruppe aus dem Profil eines Teilnehmers (`profil`) ist ein Name wie eine Telefonnummer und
    bleibt stehen, wenn sie wie im Profil benannt ist (`_ist_profilname`); sonst wird sie geprüft."""
    profil = profil or {}
    menge = _mengen_muster(zahlen)
    frei: list[tuple[int, int]] = []
    weiter_ab = 0
    for m in _ZAHL.finditer(text):
        if m.start() < weiter_ab:
            continue
        gruppe = m.group(0)
        if _in_altersetikett(text, m.start(), m.end(), zahlen):
            continue
        einheit = menge.match(text, m.end())
        if einheit is None and _ist_profilname(text, m.start(), m.end(), profil):
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


def freie_zahlen(text: str, zahlen: Sequence[Zahl], profil: Profil | None = None) -> list[str]:
    """Zahlen im Text, die mit Wert, Vorzeichen und Einheit zu keinem Eintrag in `zahlen` passen."""
    return [text[a:e] for a, e in _freie_stellen(text, zahlen, profil)]


def bereinige(text: str, zahlen: Sequence[Zahl], profil: Profil | None = None) -> str:
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
