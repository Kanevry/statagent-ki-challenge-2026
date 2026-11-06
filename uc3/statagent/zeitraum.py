"""Zeiträume der Alltagssprache lesen, ohne Sprachmodell (#74, UC4 #106).

Die KI schreibt Code, das Programm rechnet: Dieses Modul übersetzt Wörter wie „Sommer 2025“, „Q1 2025“,
„erstes Halbjahr“, „Jänner bis März“, „Ende 2025“ oder „letzten Monat“ in einen Zeitraum aus Monaten
(JJJJ-MM bis JJJJ-MM). Es fragt keine Datenbank und kein Modell; zwei Aufrufe mit derselben Frage und demselben
jüngsten Monat liefern denselben Zeitraum. Jeder erkannte Zeitraum kommt mit einem Satz, der sagt, welche Monate
gemeint sind („„Sommer 2025“ heißt hier Juni bis August 2025.“).

Festlegungen (Sprachverständnis, kein Rechenregelwerk):

- Jahreszeiten meteorologisch: Frühling März bis Mai, Sommer Juni bis August, Herbst September bis November,
  Winter Dezember bis Februar. „Winter 2025“ ist der Winter, der 2025 endet (Dezember 2024 bis Februar 2025);
  „Winter 2025/26“ ist Dezember 2025 bis Februar 2026.
- Ohne Jahr gilt der jüngste passende Zeitraum, der ganz vor oder im jüngsten Monat mit Daten liegt. Steht ein Jahr
  direkt daneben („2025 im März“, „im März letzten Jahres“, „heuer im März“), gilt dieses Jahr. Nennt die Frage ein
  Jahr, das sich nicht zuordnen lässt, fragt ``unklar`` zurück: nie still der jüngste Zeitraum.
- „Anfang 2025“ ist Jänner, „Mitte 2025“ Juni, „Ende 2025“ Dezember.
- „letzten Monat“, „aktuell“ und Ähnliches meinen den jüngsten Monat mit Daten, nicht den Kalendermonat.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, replace

#: Monatsnamen der Alltagssprache (österreichisch und bundesdeutsch, mit Abkürzungen) → Monatsnummer.
MONATSNAMEN: dict[str, int] = {
    "jänner": 1, "jaenner": 1, "januar": 1, "jänn": 1, "jän": 1, "jan": 1,
    "feber": 2, "februar": 2, "febr": 2, "feb": 2,
    "märz": 3, "maerz": 3, "mär": 3, "mrz": 3,
    "april": 4, "apr": 4,
    "mai": 5,
    "juni": 6, "jun": 6,
    "juli": 7, "jul": 7,
    "august": 8, "aug": 8,
    "september": 9, "sept": 9, "sep": 9,
    "oktober": 10, "okt": 10,
    "november": 11, "nov": 11,
    "dezember": 12, "dez": 12,
}  # fmt: skip
#: Ausgeschriebene Namen: nur sie gelten auch ohne Jahr als Monat („im März“), Abkürzungen nicht („Jan“).
_VOLLE_NAMEN = (
    "jänner", "jaenner", "januar", "feber", "februar", "märz", "maerz", "april", "mai", "juni", "juli",
    "august", "september", "oktober", "november", "dezember",
)  # fmt: skip
ANZEIGE_MONAT = (
    "Jänner", "Februar", "März", "April", "Mai", "Juni",
    "Juli", "August", "September", "Oktober", "November", "Dezember",
)  # fmt: skip

_MW = "|".join(sorted(map(re.escape, MONATSNAMEN), key=len, reverse=True))
_VOLL = "|".join(sorted(map(re.escape, _VOLLE_NAMEN), key=len, reverse=True))
_J = r"((?:19|20)\d{2})(?!\d)"

ISO = re.compile(r"(?<!\d)(\d{4})-(\d{1,2})(?!\d)")
ZAHL_MONAT = re.compile(r"(?<!\d)(\d{1,2})[./](\d{4})(?!\d)")
NAME_MONAT = re.compile(r"(?<!\w)(" + _MW + r")\.?\s+(\d{4})(?!\d)")
JAHR = re.compile(r"(?<![\d./-])((?:19|20)\d{2})(?![\d./-]?\d)")

_JAHRESZEITEN = {"früh": (3, 5), "frueh": (3, 5), "sommer": (6, 8), "herbst": (9, 11), "winter": (12, 2)}
_ZEITWORT = {"frühling": "Frühling", "frühjahr": "Frühjahr", "fruehling": "Frühling", "fruehjahr": "Frühjahr"}
_ORDNUNG = {"erst": 1, "zweit": 2, "dritt": 3, "viert": 4, "letzt": 0}
_ZAHLWORT = {
    "zwei": 2, "drei": 3, "vier": 4, "fünf": 5, "fuenf": 5, "sechs": 6, "sieben": 7, "acht": 8, "neun": 9,
    "zehn": 10, "elf": 11, "zwölf": 12, "zwoelf": 12,
}  # fmt: skip

_JAHRESZEIT = re.compile(
    r"(?<!\w)(frühlings?|frühjahrs?|fruehlings?|fruehjahrs?|sommers?|herbst(?:es|s)?|winters?)"
    r"(?:monate[n]?)?(?!\w)"
    rf"(?:\s+(?:des\s+jahres\s+|im\s+jahr\s+|von\s+)?{_J}(?:\s*/\s*(\d{{4}}|\d{{2}})(?!\d))?)?",
    re.IGNORECASE,
)
_QUARTAL = re.compile(
    r"(?<!\w)(?:q([1-4])|([1-4])\.\s*quartal|(erst|zweit|dritt|viert|letzt)e[nmrs]?\s+quartal|quartal\s+([1-4]))"
    rf"(?!\w)(?:\s*(?:des\s+jahres\s+|im\s+jahr\s+|von\s+|/\s*|-\s*)?{_J})?",
    re.IGNORECASE,
)
_JAHR_QUARTAL = re.compile(rf"(?<!\d){_J}\s*[-/ ]\s*q([1-4])(?!\w)", re.IGNORECASE)
_HALBJAHR = re.compile(
    r"(?<!\w)(?:([12])\.\s*(?:halbjahr|hj|jahreshälfte|jahreshaelfte)|(erst|zweit)e[nmrs]?\s+"
    r"(?:halbjahr|jahreshälfte|jahreshaelfte|hälfte|haelfte)(?:\s+des\s+jahres)?)"
    rf"(?!\w)(?:\s*(?:des\s+jahres\s+|im\s+jahr\s+|von\s+)?{_J})?",
    re.IGNORECASE,
)
_H_JAHR = re.compile(rf"(?<!\w)h([12])\s*(?:/\s*)?{_J}", re.IGNORECASE)
_JAHRESTEIL = re.compile(
    r"(?<!\w)(?:jahres(anfang|beginn|mitte|ende)|(anfang|beginn|mitte|ende)(?:\s+des\s+jahres)?)"
    rf"\s+(?:von\s+)?{_J}",
    re.IGNORECASE,
)
_JAHRESTEIL_MONAT = {"anfang": 1, "beginn": 1, "mitte": 6, "ende": 12}
_BEREICH = re.compile(
    rf"(?<!\w)({_MW})\.?(?:\s+{_J})?\s*(?:bis(?:\s+einschließlich|\s+inklusive|\s+ende)?|–|—|-)\s*"
    rf"({_MW})\.?(?!\w)(?:\s+{_J})?",
    re.IGNORECASE,
)
_ZWISCHEN = re.compile(
    rf"(?<!\w)zwischen\s+({_MW})\.?(?:\s+{_J})?\s+und\s+({_MW})\.?(?!\w)(?:\s+{_J})?", re.IGNORECASE
)
_LETZTE_MONATE = re.compile(
    r"(?<!\w)(?:(?:in\s+den|die|den)\s+)?(?:letzte[nr]?|vergangene[nr]?)\s+(\d{1,2}|zwei|drei|vier|fünf|fuenf|sechs|"
    r"sieben|acht|neun|zehn|elf|zwölf|zwoelf)\s+monate?n?(?!\w)",
    re.IGNORECASE,
)
_LETZTER_MONAT = re.compile(
    r"(?<!\w)(?:letzte[nmr]?|vergangene[nmr]?|jüngste[nmr]?|neueste[nmr]?|aktuellste[nmr]?)"
    r"\s+monats?(?!\w)",
    re.IGNORECASE,
)
_AKTUELL = re.compile(
    r"(?<!\w)(aktuell|derzeit|zurzeit|momentan|jetzt|gegenwärtig|zuletzt)(?!\w)", re.IGNORECASE
)
_MONAT_OHNE_JAHR = re.compile(rf"(?<!\w)({_VOLL})(?!\w)(?!\.?\s*(?:\d|/))", re.IGNORECASE)
_HEUER = re.compile(
    r"(?<!\w)(heuer|dieses\s+jahr(?:es)?|in\s+diesem\s+jahr|im\s+laufenden\s+jahr)(?!\w)", re.I
)
_LETZTES_JAHR = re.compile(
    r"(?<!\w)(?:(?:im|des)\s)?(?:(?:letzte[nms]?|vergangene[nms]?|vorige[nms]?)\s+jahr(?:es)?|vorjahr(?:es)?)(?!\w)",
    re.IGNORECASE,
)
#: „2025/26“ außerhalb einer Jahreszeit: zwei Jahre, für einen Monat ohne Jahr nicht zuzuordnen.
_JAHRESPAAR = re.compile(r"(?<!\d)(?:19|20)\d{2}\s*/\s*\d{2,4}(?!\d)")
#: Ein Vergleich meint oft zwei Zeitpunkte: Ein Jahr daneben gehört dann nicht sicher zum Monat ohne Jahr.
_VERGLEICH = re.compile(
    r"vergleich|gegenüber|gegenueber|verglichen|(?<!\w)vs\.?(?!\w)|(?<!\w)zu\s+\d{4}", re.IGNORECASE
)
#: Davor ein Wort, das das Jahr zum zweiten Zeitpunkt macht („zum Vorjahr“, „und 2025“).
_VERGLEICH_DAVOR = re.compile(
    r"(?<!\w)(?:zum?|gegen|gegenüber|gegenueber|vs\.?|und|oder|mit)\s*$", re.IGNORECASE
)
#: Zwischen Jahr und Zeitangabe steht höchstens ein kurzes Füllwort („2025 im März“, „März in 2025“).
_JAHR_NEBEN = re.compile(
    r"\s*(?:[,:–—-]\s*)?(?:(?:im|in|von|vom|aus|des|dem|den|der|jahre?s?)\s+)*", re.IGNORECASE
)
#: Relative Jahre, die wir nicht auflösen: lieber nachfragen als den jüngsten Monat nehmen.
_ANDERES_JAHR = re.compile(
    r"(?<!\w)(?:vor\s+\w+\s+jahr(?:en)?|vorletzte[nms]?\s+jahr|vorvorjahr|nächste[nms]?\s+jahr|naechste[nms]?\s+jahr"
    r"|ein\s+jahr\s+(?:zuvor|davor|früher|frueher))",
    re.IGNORECASE,
)
_VIER_ZIFFERN = re.compile(r"\d{4}")
_JAHR_OFFEN = (
    "Das Jahr ist nicht eindeutig. Bitte Monat und Jahr nennen, zum Beispiel „Beschäftigte im März 2025“."
)
#: Zwischen zwei Teilen einer Aufzählung steht nur ein Bindewort („im Mai 2025 und im Juni“).
_NUR_BINDEWORT = re.compile(
    r"\s*(?:,|und|oder|sowie|bzw\.?)\s*(?:auch\s+)?(?:(?:im|in|den|dem|der|von)\s+)?", re.IGNORECASE
)
#: Wörter, mit denen eine bloße Jahreszahl den Durchschnitt aller Monate meint („Jahresdurchschnitt 2025“).
DURCHSCHNITT_WORT = re.compile(
    r"durchschnitt|jahresmittel|im\s+mittel|(?:ganze|gesamte)[ns]?\s+jahr|übers?\s+(?:das\s+)?jahr|ueber\s+das\s+jahr",
    re.IGNORECASE,
)


#: Wörter, mit denen eine Frage die Monate einzeln sehen will (Text in Kleinbuchstaben).
ZEITREIHE_WORT = re.compile(
    r"zeitreihe|entwicklung|entwickelt|verlauf|monatsweise|je monat|pro monat|\bseit\b"
)

#: Ein gemeinsames Jahr am Ende einer Aufzählung („März und April 2025“, „Q1 und Q3 2025“).
_FOLGEJAHR = re.compile(
    r"\s*(?:,|und|oder|sowie|bzw\.?)\s+[^,]{0,30}?(?<!\d)((?:19|20)\d{2})(?!\d)", re.IGNORECASE
)
_MONAT_DES_JAHRES = re.compile(rf"(?<!\w)({_MW})\.?\s+(?:des\s+jahres|im\s+jahre?|von)\s+{_J}", re.IGNORECASE)
_RANDMONAT_DES_JAHRES = re.compile(
    rf"(?<!\w)(letzte|erste)[nmr]?\s+monats?\s+(?:des\s+jahres\s+|im\s+jahre?\s+|von\s+|in\s+)?{_J}",
    re.IGNORECASE,
)
_DATUM = re.compile(
    r"(?<![\d.])(\d{1,2})\.\s?(\d{1,2})\.\s?((?:19|20)\d{2})(?!\d)|(?<!\d)((?:19|20)\d{2})-(\d{1,2})-(\d{1,2})(?!\d)"
)
_HALBJAHR_SAISON = re.compile(r"(?<!\w)(sommer|winter)(halbjahr|saison)\w*", re.IGNORECASE)
_BEREICHSWORT = re.compile(r"(?<!\w)(?:bis|zwischen)(?!\w)|[–—-]", re.IGNORECASE)
#: Jahreszahlen, die kein Zeitraum sind („ÖNACE 2008“, „Version 2025“).
KEIN_JAHR = re.compile(
    r"(?:önace|oenace|nace|version|fassung|klassifikation|plz|postleitzahl|jahrgang|geburtsjahr)[\s-]*(?:19|20)\d{2}"
    r"|(?<!\w)(?:über|ueber|mehr als|weniger als|unter)\s+(?:19|20)\d{2}(?!\d)"
    # „mit“ nur mit Mengenwort: „März 2026 mit 2025 vergleichen“ meint ein Jahr.
    r"|(?<!\w)mit\s+(?:19|20)\d{2}\s+(?:mitarbeiter|beschäftigte|personen|leute|euro)",
    re.IGNORECASE,
)


#: „Winter 24/25“, „Q1/25“, „März/25“, „03/25“: Ein zweistelliges Jahr wäre sonst still ein anderer Zeitraum.
_KURZES_JAHR = re.compile(
    rf"(?<![\w/.-])(?:(?:{_MW}|frühlings?|frühjahrs?|sommers?|herbst(?:es|s)?|winters?|q[1-4])\.?\s*[/ -]\s*\d{{2}}"
    rf"(?:\s*/\s*\d{{2}})?|\d{{1,2}}/\d{{2}}|\d{{1,2}}\.\d{{2}}|\d{{1,2}}\.\d{{1,2}}\.\d{{2}})"
    rf"(?![\w/]|\.\s?\d|\s*(?:jahre|jahren)\b)",
    re.IGNORECASE,
)
_MONAT_SCHRAEG = re.compile(rf"(?<!\w)({_MW})\.?\s*/\s*(?=(?:{_MW})(?!\w))", re.IGNORECASE)


def schraegstrich_lesen(frage: str) -> str:
    """„Mai/Juni 2026“ nennt zwei Monate; sonst zählte nur der zweite."""
    return _MONAT_SCHRAEG.sub(r"\1 und ", frage)


def _folgejahr(t: re.Match[str]) -> int | None:
    folge = _FOLGEJAHR.match(t.string, t.end())
    if folge is None or any(k.start() <= folge.start(1) < k.end() for k in KEIN_JAHR.finditer(t.string)):
        return None
    return int(folge.group(1))


def monat_anzeige(monat: str) -> str:
    """„2025-03“ → „März 2025“."""
    jahr, nummer = monat.split("-")
    return f"{ANZEIGE_MONAT[int(nummer) - 1]} {jahr}"


def _monat(jahr: int, nummer: int) -> str:
    return f"{jahr:04d}-{nummer:02d}"


def verschieben(monat: str, anzahl: int) -> str:
    jahr, nummer = int(monat[:4]), int(monat[5:7])
    index = jahr * 12 + nummer - 1 + anzahl
    return _monat(index // 12, index % 12 + 1)


def monate(von: str, bis: str) -> list[str]:
    """Alle Monate von bis bis, beide eingeschlossen (höchstens 600)."""
    ergebnis: list[str] = []
    monat = von
    while monat <= bis and len(ergebnis) < 600:
        ergebnis.append(monat)
        monat = verschieben(monat, 1)
    return ergebnis


def zeitraum_anzeige(von: str, bis: str) -> str:
    """„Juni bis August 2025“, „Dezember 2024 bis Februar 2025“ oder „März 2025“."""
    if von == bis:
        return monat_anzeige(von)
    if von[:4] == bis[:4]:
        return f"{ANZEIGE_MONAT[int(von[5:7]) - 1]} bis {monat_anzeige(bis)}"
    return f"{monat_anzeige(von)} bis {monat_anzeige(bis)}"


@dataclass(frozen=True)
class Zeitraum:
    """Ein erkannter Zeitraum: Monate von bis bis, die Art und die Textstelle der Frage."""

    von: str
    bis: str
    #: monat, bereich, jahreszeit, quartal, halbjahr, jahresteil, jahr, letzte_monate, aktuell
    art: str
    wort: str  # die Textstelle, wie sie in der Frage steht („Sommer 2025“)
    start: int = -1
    ende: int = -1
    ohne_jahr: bool = False  # das Jahr fehlte und wurde aus dem jüngsten Monat ergänzt
    #: Art „liste“: nur diese Monate („Jänner 2025 und Juli 2025“), nicht die Monate dazwischen.
    nur: tuple[str, ...] = ()

    @property
    def monatsliste(self) -> list[str]:
        return list(self.nur) if self.nur else monate(self.von, self.bis)

    @property
    def mehrere(self) -> bool:
        return self.von != self.bis

    def erklaerung(self) -> str | None:
        """Ein Satz, welche Monate gemeint sind; None, wenn die Frage die Monate schon wörtlich nennt.

        Ohne Anführungszeichen: In /uc3/fragen wird Text in „…“ als anklickbarer Vorschlag gezeigt.
        """
        zeit = zeitraum_anzeige(self.von, self.bis)
        wort = self.wort.strip()
        gross = wort[:1].upper() + wort[1:]
        if self.art == "liste":
            return None
        if self.art in ("monat", "bereich"):
            if self.ohne_jahr:
                was = (
                    f"der jüngste {wort} mit Daten"
                    if self.art == "monat"
                    else "der jüngste solche Zeitraum mit Daten"
                )
                return f"{gross} ohne Jahr heißt hier {zeit}, {was}."
            if self.art == "bereich" and self.von[:4] != self.bis[:4] and self.von[:4] not in wort:
                return f"{gross} heißt hier {zeit}."
            return None
        if self.art == "aktuell":
            return f"Mit {wort} ist hier der jüngste Monat mit Daten gemeint: {zeit}."
        if self.art == "letzte_monate":
            return f"Mit den {wort} sind hier die jüngsten Monate mit Daten gemeint: {zeit}."
        if self.art == "jahr":
            return f"Gemeint ist der Durchschnitt der Monate {zeit}."
        if self.art in ("quartal", "halbjahr"):
            laenge = 3 if self.art == "quartal" else 6
            name = "Quartal" if self.art == "quartal" else "Halbjahr"
            teil = f"{(int(self.von[5:7]) - 1) // laenge + 1}. {name} {self.von[:4]}"
            zusatz = ", das jüngste mit Daten" if self.ohne_jahr else ""
            return f"Das {teil} sind die Monate {zeit}{zusatz}."
        if self.ohne_jahr:
            return f"{gross} ohne Jahr heißt hier {zeit}, der jüngste {gross} mit Daten."
        return f"{gross} heißt hier {zeit}."


def _jahr_fuer(letzter: str | None, von_nummer: int, bis_nummer: int) -> int | None:
    """Jahr, in dem der Zeitraum (Monat von_nummer bis bis_nummer, über den Jahreswechsel, wenn von > bis) zuletzt
    ganz bis zum jüngsten Monat mit Daten liegt; ohne jüngsten Monat None."""
    if letzter is None:
        return None
    jahr = int(letzter[:4])
    while _monat(jahr, bis_nummer) > letzter:
        jahr -= 1
    return jahr


def _treffer_jahreszeit(t: re.Match[str], letzter: str | None) -> tuple[str, str, bool] | None:
    stamm = t.group(1).lower()
    von_n, bis_n = next(v for k, v in _JAHRESZEITEN.items() if stamm.startswith(k))
    if t.group(2):
        jahr = int(t.group(2))
        if t.group(3):
            zweites = int(t.group(3)) if len(t.group(3)) == 4 else (jahr // 100) * 100 + int(t.group(3))
            if von_n > bis_n and zweites == jahr + 1:
                return _monat(jahr, von_n), _monat(jahr + 1, bis_n), False
            return None  # widersprüchliches Jahrespaar („Winter 2025/27“), siehe unklar()
        if von_n > bis_n:
            return _monat(jahr - 1, von_n), _monat(jahr, bis_n), False
        return _monat(jahr, von_n), _monat(jahr, bis_n), False
    folge = _folgejahr(t)
    if folge is not None:
        return (_monat(folge - 1 if von_n > bis_n else folge, von_n), _monat(folge, bis_n), False)
    jahr_bis = _jahr_fuer(letzter, von_n, bis_n)
    if jahr_bis is None:
        return None
    jahr_von = jahr_bis - 1 if von_n > bis_n else jahr_bis
    return _monat(jahr_von, von_n), _monat(jahr_bis, bis_n), True


def _drei(nummer: int, jahr: int | None, letzter: str | None, laenge: int) -> tuple[str, str, bool] | None:
    """Quartal (laenge 3) oder Halbjahr (laenge 6) Nummer nummer; nummer 0 heißt das letzte."""
    anzahl = 12 // laenge
    if jahr is not None:
        n = anzahl if nummer == 0 else nummer
        return _monat(jahr, (n - 1) * laenge + 1), _monat(jahr, n * laenge), False
    if letzter is None:
        return None
    if nummer == 0:  # das letzte ganze Quartal bis zum jüngsten Monat
        ende = int(letzter[5:7]) // laenge * laenge
        jahr_l = int(letzter[:4])
        if ende == 0:
            jahr_l, ende = jahr_l - 1, 12
        return _monat(jahr_l, ende - laenge + 1), _monat(jahr_l, ende), True
    gefunden = _jahr_fuer(letzter, (nummer - 1) * laenge + 1, nummer * laenge)
    if gefunden is None:
        return None
    return _monat(gefunden, (nummer - 1) * laenge + 1), _monat(gefunden, nummer * laenge), True


def _treffer_quartal(t: re.Match[str], letzter: str | None) -> tuple[str, str, bool] | None:
    roh = t.group(1) or t.group(2) or t.group(4)
    nummer = int(roh) if roh else _ORDNUNG[t.group(3).lower()]
    return _drei(nummer, int(t.group(5)) if t.group(5) else _folgejahr(t), letzter, 3)


def _treffer_jahr_quartal(t: re.Match[str], _letzter: str | None) -> tuple[str, str, bool] | None:
    return _drei(int(t.group(2)), int(t.group(1)), None, 3)


def _treffer_halbjahr(t: re.Match[str], letzter: str | None) -> tuple[str, str, bool] | None:
    nummer = int(t.group(1)) if t.group(1) else _ORDNUNG[t.group(2).lower()]
    return _drei(nummer, int(t.group(3)) if t.group(3) else _folgejahr(t), letzter, 6)


def _treffer_h_jahr(t: re.Match[str], _letzter: str | None) -> tuple[str, str, bool] | None:
    return _drei(int(t.group(1)), int(t.group(2)), None, 6)


def _treffer_jahresteil(t: re.Match[str], _letzter: str | None) -> tuple[str, str, bool] | None:
    teil = (t.group(1) or t.group(2)).lower()
    monat = _monat(int(t.group(3)), _JAHRESTEIL_MONAT[teil])
    return monat, monat, False


def _bereich(
    erster: str, jahr1: str | None, zweiter: str, jahr2: str | None, letzter: str | None
) -> tuple[str, str, bool] | None:
    von_n, bis_n = MONATSNAMEN[erster.lower()], MONATSNAMEN[zweiter.lower()]
    if jahr2 is not None:
        bis_j = int(jahr2)
        von_j = int(jahr1) if jahr1 else (bis_j - 1 if von_n > bis_n else bis_j)
        ohne = False
    elif jahr1 is not None:
        von_j = int(jahr1)
        bis_j = von_j + 1 if von_n > bis_n else von_j
        ohne = False
    else:
        gefunden = _jahr_fuer(letzter, von_n, bis_n)
        if gefunden is None:
            return None
        bis_j, von_j, ohne = gefunden, gefunden - 1 if von_n > bis_n else gefunden, True
    von, bis = _monat(von_j, von_n), _monat(bis_j, bis_n)
    return (von, bis, ohne) if von <= bis else None


def _treffer_bereich(t: re.Match[str], letzter: str | None) -> tuple[str, str, bool] | None:
    return _bereich(t.group(1), t.group(2), t.group(3), t.group(4), letzter)


def _treffer_letzte_monate(t: re.Match[str], letzter: str | None) -> tuple[str, str, bool] | None:
    if letzter is None:
        return None
    roh = t.group(1).lower()
    anzahl = int(roh) if roh.isdigit() else _ZAHLWORT[roh]
    if not 1 <= anzahl <= 120:
        return None
    return verschieben(letzter, 1 - anzahl), letzter, False


def _treffer_letzter_monat(_t: re.Match[str], letzter: str | None) -> tuple[str, str, bool] | None:
    return None if letzter is None else (letzter, letzter, False)


def _treffer_monat_des_jahres(t: re.Match[str], _letzter: str | None) -> tuple[str, str, bool] | None:
    monat = _monat(int(t.group(2)), MONATSNAMEN[t.group(1).lower()])
    return monat, monat, False


def _treffer_monat_ohne_jahr(t: re.Match[str], letzter: str | None) -> tuple[str, str, bool] | None:
    nummer = MONATSNAMEN[t.group(1).lower()]
    folge = _folgejahr(t)
    if folge is not None:
        return _monat(folge, nummer), _monat(folge, nummer), False
    jahr = _jahr_fuer(letzter, nummer, nummer)
    return None if jahr is None else (_monat(jahr, nummer), _monat(jahr, nummer), True)


def _treffer_randmonat(t: re.Match[str], _letzter: str | None) -> tuple[str, str, bool] | None:
    monat = _monat(int(t.group(2)), 12 if t.group(1).lower() == "letzte" else 1)
    return monat, monat, False


#: Muster in der Reihenfolge, in der sie gelten: zusammengesetzte Zeiträume vor einzelnen Monaten.
_MUSTER: tuple[tuple[re.Pattern[str], str, object], ...] = (
    (_RANDMONAT_DES_JAHRES, "monat", _treffer_randmonat),
    (_MONAT_DES_JAHRES, "monat", _treffer_monat_des_jahres),
    (_ZWISCHEN, "bereich", _treffer_bereich),
    (_BEREICH, "bereich", _treffer_bereich),
    (_JAHRESZEIT, "jahreszeit", _treffer_jahreszeit),
    (_JAHR_QUARTAL, "quartal", _treffer_jahr_quartal),
    (_QUARTAL, "quartal", _treffer_quartal),
    (_H_JAHR, "halbjahr", _treffer_h_jahr),
    (_HALBJAHR, "halbjahr", _treffer_halbjahr),
    (_JAHRESTEIL, "jahresteil", _treffer_jahresteil),
    (_LETZTE_MONATE, "letzte_monate", _treffer_letzte_monate),
    (_LETZTER_MONAT, "aktuell", _treffer_letzter_monat),
)


def _wort(frage: str, t: re.Match[str]) -> str:
    """Die Textstelle ohne einleitendes „im/den/in den/von“, mit großem Anfangsbuchstaben wie in der Frage."""
    wort = frage[t.start() : t.end()].strip()
    return re.sub(r"^(?:im|den|der|in den|die|von|ab)\s+", "", wort, flags=re.IGNORECASE)


def _explizit(frage: str) -> list[tuple[int, int, str]]:
    """Wörtlich genannte Monate (``2025-03``, ``03/2025``, „März 2025“) als (Anfang, Ende, JJJJ-MM)."""
    gefunden: list[tuple[int, int, str]] = []
    for muster, jahr_gruppe, monat_gruppe in ((NAME_MONAT, 2, 1), (ZAHL_MONAT, 2, 1), (ISO, 1, 2)):
        for t in muster.finditer(frage.lower()):
            if any(t.start() < b and t.end() > a for a, b, _ in gefunden):
                continue
            roh = t.group(monat_gruppe)
            nummer = MONATSNAMEN[roh] if muster is NAME_MONAT else int(roh)
            if 1 <= nummer <= 12:
                gefunden.append((t.start(), t.end(), _monat(int(t.group(jahr_gruppe)), nummer)))
    return sorted(gefunden)


def _teile_roh(frage: str, letzter: str | None) -> list[Zeitraum]:
    """Alle zusammengesetzten Zeitangaben der Frage, ein fehlendes Jahr aus dem jüngsten Monat ergänzt."""
    teile: list[Zeitraum] = []

    def frei(a: int, b: int) -> bool:
        return not any(a < z.ende and b > z.start for z in teile)

    for muster, art, behandle in _MUSTER:
        for t in muster.finditer(frage):
            if not frei(t.start(), t.end()):
                continue
            ergebnis = behandle(t, letzter)  # type: ignore[operator]
            if ergebnis is None:
                continue
            von, bis, ohne = ergebnis
            teile.append(Zeitraum(von, bis, art, _wort(frage, t), t.start(), t.end(), ohne))
    belegt = [(a, b) for a, b, _ in _explizit(frage)]
    for t in _MONAT_OHNE_JAHR.finditer(frage):
        if not frei(t.start(), t.end()) or any(t.start() < b and t.end() > a for a, b in belegt):
            continue
        ergebnis = _treffer_monat_ohne_jahr(t, letzter)
        if ergebnis is not None:
            von, bis, ohne = ergebnis
            teile.append(Zeitraum(von, bis, "monat", _wort(frage, t), t.start(), t.end(), ohne))
    return sorted(teile, key=lambda z: z.start)


def _freie_jahre(
    frage: str, teile: list[Zeitraum], explizit: list[tuple[int, int, str]], letzter: str | None
) -> list[tuple[int, int, int]]:
    """Jahre außerhalb aller Zeitangaben als (Jahr, Anfang, Ende): „2025“, „heuer“, „letzten Jahres“."""
    zeichen = list(frage)

    def weg(a: int, b: int) -> None:
        zeichen[a:b] = " " * (b - a)

    for z in teile:
        weg(z.start, z.ende)
    for a, b, _ in explizit:
        weg(a, b)
    for muster in (KEIN_JAHR, _DATUM):
        for t in muster.finditer(frage):
            weg(t.start(), t.end())
    rest = "".join(zeichen)
    jahre: list[tuple[int, int, int]] = []
    if letzter is not None:
        for t in _HEUER.finditer(rest):
            jahre.append((int(letzter[:4]), t.start(), t.end()))
        for t in _LETZTES_JAHR.finditer(rest):
            jahre.append((int(letzter[:4]) - 1, t.start(), t.end()))
    for t in JAHR.finditer(rest):
        jahre.append((int(t.group(1)), t.start(), t.end()))
    return sorted(jahre, key=lambda j: j[1])


def _ins_jahr(z: Zeitraum, jahr: int) -> Zeitraum:
    """Der Teil ohne Jahr im genannten Jahr; ein Zeitraum über den Jahreswechsel endet darin („Winter 2025“)."""
    if z.art in ("quartal", "halbjahr") and re.search(r"letzt", z.wort, re.IGNORECASE):
        # „das letzte Quartal von 2025“ ist das vierte, nicht das Quartal, das zuletzt Daten hat.
        laenge = 3 if z.art == "quartal" else 6
        von, bis = _monat(jahr, 13 - laenge), _monat(jahr, 12)
    else:
        schritte = (jahr - int(z.bis[:4])) * 12
        von, bis = verschieben(z.von, schritte), verschieben(z.bis, schritte)
    return replace(z, von=von, bis=bis, ohne_jahr=False, wort=f"{z.wort} {jahr}")


def _grenzt_an(frage: str, z: Zeitraum, start: int, ende: int) -> bool:
    """Steht das Jahr (Textstelle start bis ende) direkt neben dem Teil, nur durch „im“, „in“ oder „von“ getrennt?"""
    if _VERGLEICH_DAVOR.search(frage[:start]):
        return False
    zwischen = frage[ende : z.start] if ende <= z.start else frage[z.ende : start]
    return _JAHR_NEBEN.fullmatch(zwischen) is not None


def _beide_monate(monat: str, jahr: int) -> str:
    """Rückfrage mit dem genannten Monat und demselben Monat im anderen Jahr (sonst ein Jahr davor)."""
    anderer = _monat(jahr, int(monat[5:7])) if jahr != int(monat[:4]) else verschieben(monat, -12)
    return (
        "Bitte beide Monate mit Jahr nennen, "
        f"zum Beispiel „Beschäftigte im {monat_anzeige(monat)} und im {monat_anzeige(anderer)}“."
    )


def _aufloesen(frage: str, letzter: str | None) -> tuple[list[Zeitraum], list[tuple[int, int]], str | None]:
    """Weist Teilen ohne Jahr das Jahr zu, das die Frage nennt.

    Ein Jahr gilt, wenn es direkt neben dem Teil steht („2025 im März“, „März in 2025“, „im März letzten Jahres“). In
    einer Aufzählung gilt das Jahr des Nachbarn, wenn der Teil damit in der genannten Reihenfolge bleibt („im Mai 2025
    und im Juni“; „Dezember 2025 und Jänner“ bleibt offen). Rückgabe: die Teile, die Textstellen der freien Jahre und
    ein Satz, wenn das Jahr nicht eindeutig ist. Dann bleiben die Teile, wie sie sind; ``unklar`` fragt zurück, bevor
    eine Zahl entsteht. Steht nirgends ein Jahr, gilt der jüngste passende Zeitraum, und der Text sagt es.
    """
    roh = _teile_roh(frage, letzter)
    explizit = [(a, e, m) for a, e, m in _explizit(frage) if not any(a < z.ende and e > z.start for z in roh)]
    freie = _freie_jahre(frage, roh, explizit, letzter)
    if not roh and not explizit:
        jahre = sorted({j for j, _, _ in freie})
        if len(jahre) < 2:
            return roh, [], None
        return (
            roh,
            [],
            (
                "Die Frage nennt mehrere Jahre. Meinen Sie alle Monate als Zeitreihe, "
                f"zum Beispiel „Zeitreihe 01/{jahre[0]} bis 12/{jahre[-1]}“?"
            ),
        )
    relativ = [z for z in roh if z.art in ("aktuell", "letzte_monate")]
    if relativ and freie:
        was = "Der letzte Monat" if relativ[0].art == "aktuell" else "Die letzten Monate"
        return (
            roh,
            [],
            (
                f"{was} und ein Jahr passen nicht zusammen. "
                "Bitte Monat und Jahr nennen, zum Beispiel „Beschäftigte im Dezember 2025“."
            ),
        )
    if any(z.ohne_jahr for z in roh) and (
        _JAHRESPAAR.search(frage) or _ANDERES_JAHR.search(frage) or (freie and _VERGLEICH.search(frage))
    ):
        return roh, [], _JAHR_OFFEN
    # Reihenfolge der Frage; wörtliche Monate zählen als Nachbarn, „letzten Monat“ nennt kein Jahr.
    alle = sorted([*roh, *(Zeitraum(m, m, "monat", "", a, e) for a, e, m in explizit)], key=lambda z: z.start)
    benutzt: set[int] = set()
    for i, z in enumerate(alle):
        if not z.ohne_jahr:
            continue
        nah = {n for n, (_, a, e) in enumerate(freie) if _grenzt_an(frage, z, a, e)}
        if len({freie[n][0] for n in nah}) > 1:
            return roh, [], _JAHR_OFFEN
        if nah:
            alle[i] = _ins_jahr(z, freie[min(nah)][0])
            benutzt |= nah

    def kennt_jahr(z: Zeitraum) -> bool:
        return not z.ohne_jahr and z.art not in ("aktuell", "letzte_monate")

    def verbunden(links: Zeitraum, rechts: Zeitraum) -> bool:
        return _NUR_BINDEWORT.fullmatch(frage[links.ende : rechts.start]) is not None

    for i in range(1, len(alle)):
        if alle[i].ohne_jahr and kennt_jahr(alle[i - 1]) and verbunden(alle[i - 1], alle[i]):
            kandidat = _ins_jahr(alle[i], int(alle[i - 1].bis[:4]))
            if kandidat.von <= alle[i - 1].bis:
                return roh, [], _JAHR_OFFEN
            alle[i] = kandidat
    for i in range(len(alle) - 2, -1, -1):
        if alle[i].ohne_jahr and kennt_jahr(alle[i + 1]) and verbunden(alle[i], alle[i + 1]):
            kandidat = _ins_jahr(alle[i], int(alle[i + 1].von[:4]))
            if kandidat.bis >= alle[i + 1].von:
                return roh, [], _JAHR_OFFEN
            alle[i] = kandidat

    # Ohne eigenes Jahr dürfen die Teile nicht gegen die Lesereihenfolge laufen („im Juli und August“).
    def ohne_eigenes(z: Zeitraum) -> bool:
        return bool(z.wort) and not _VIER_ZIFFERN.search(z.wort)

    reihe = [z for z in alle if z.art not in ("aktuell", "letzte_monate")]
    for links, rechts in zip(reihe, reihe[1:], strict=False):
        if (ohne_eigenes(links) or ohne_eigenes(rechts)) and links.von >= rechts.von:
            return roh, [], _JAHR_OFFEN
    genannt = {int(m[:4]) for z in alle if kennt_jahr(z) for m in (z.von, z.bis)}
    if any(z.ohne_jahr for z in alle):
        return roh, [], (_JAHR_OFFEN if genannt or freie else None)
    # Eine Jahresangabe, die zu keinem Teil gehört: „März 2025 und 2026“, „März 2025 im Vergleich zum Vorjahr“.
    # Auch eine gleiche Zahl zählt nur, wenn sie direkt daneben steht („2025 im März 2025“).
    for n, (j, a, e) in enumerate(freie):
        if n not in benutzt and not any(
            kennt_jahr(z) and j in (int(z.von[:4]), int(z.bis[:4])) and _grenzt_an(frage, z, a, e)
            for z in alle
        ):
            return roh, [], _beide_monate(next(z.von for z in alle if kennt_jahr(z)), j)
    teile = [z for z in alle if z.wort]
    return teile, [(a, e) for _, a, e in freie], None


def teile_lesen(frage: str, letzter: str | None) -> list[Zeitraum]:
    """Alle zusammengesetzten Zeitangaben der Frage (ohne wörtliche Einzelmonate und bloße Jahre).

    Eine Textstelle zählt nur einmal; zuerst Bereiche, dann Jahreszeiten, Quartale, Halbjahre, Jahresteile,
    „letzte N Monate“, „letzter Monat“, zuletzt ausgeschriebene Monatsnamen ohne Jahr. Ein Jahr an anderer Stelle
    der Frage gilt für Teile ohne Jahr (siehe ``_aufloesen``).
    """
    return _aufloesen(frage, letzter)[0]


def jahr_lesen(frage: str, letzter: str | None) -> tuple[int, str] | None:
    """Ein bloßes Jahr („2025“, „heuer“, „letztes Jahr“) mit der Textstelle; sonst None."""
    t = _HEUER.search(frage)
    if t and letzter is not None:
        return int(letzter[:4]), t.group(0)
    t = _LETZTES_JAHR.search(frage)
    if t and letzter is not None:
        return int(letzter[:4]) - 1, _wort(frage, t)
    rest = KEIN_JAHR.sub(lambda m: " " * len(m.group(0)), frage)
    for muster in (NAME_MONAT, ZAHL_MONAT, ISO):
        rest = muster.sub(lambda m: " " * len(m.group(0)), rest.lower())
    t = JAHR.search(rest)
    return (int(t.group(1)), frage[t.start() : t.end()]) if t else None


def zeitraum_lesen(frage: str, letzter: str | None) -> Zeitraum | None:
    """Der Zeitraum der Frage, oder None, wenn sie keinen nennt.

    Vorrang: eine zusammengesetzte Angabe (Jahreszeit, Quartal, Bereich …), sonst wörtliche Monate (zwei oder
    mehr ergeben den Bereich vom ersten bis zum letzten), sonst „aktuell“, sonst ein bloßes Jahr (alle zwölf
    Monate, gedacht für einen Durchschnitt). ``letzter`` ist der jüngste Monat mit Daten (JJJJ-MM) für Angaben
    ohne Jahr und für „letzten Monat“; ohne ihn bleiben solche Angaben unerkannt.
    """
    teile = teile_lesen(frage, letzter)
    # Wörtliche Monate innerhalb eines Teils („März 2025 bis Juni 2025“) zählen nicht extra.
    explizit = [
        (a, e, m) for a, e, m in _explizit(frage) if not any(a < z.ende and e > z.start for z in teile)
    ]
    teil_liste = sorted(
        [(z.start, z.ende, z.von, z.bis, z) for z in teile] + [(a, e, m, m, None) for a, e, m in explizit],
        key=lambda x: x[0],
    )
    if len(teil_liste) == 1:
        start, ende, von, bis, z = teil_liste[0]
        if z is not None:
            return z
        return Zeitraum(von, bis, "monat", frage[start:ende], start, ende)
    if teil_liste:
        von, bis = min(x[2] for x in teil_liste), max(x[3] for x in teil_liste)
        start, ende = teil_liste[0][0], teil_liste[-1][1]
        zwischen = [frage[teil_liste[i][1] : teil_liste[i + 1][0]] for i in range(len(teil_liste) - 1)]
        if all(_BEREICHSWORT.search(z) for z in zwischen):
            return Zeitraum(von, bis, "bereich", frage[start:ende], start, ende)
        nur = sorted({m for x in teil_liste for m in monate(x[2], x[3])})
        return Zeitraum(von, bis, "liste", frage[start:ende], start, ende, nur=tuple(nur))
    t = _AKTUELL.search(frage)
    if t and letzter is not None and jahr_lesen(frage, letzter) is None:
        return Zeitraum(letzter, letzter, "aktuell", t.group(0), t.start(), t.end())
    jahr = jahr_lesen(frage, letzter)
    if jahr is not None:
        return Zeitraum(_monat(jahr[0], 1), _monat(jahr[0], 12), "jahr", jahr[1])
    return None


def umschreiben(frage: str, letzter: str | None) -> tuple[str, list[str], bool]:
    """Ersetzt zusammengesetzte Zeitangaben durch wörtliche Monate („Sommer 2025“ → „Juni 2025 bis August 2025“).

    Rückgabe: neue Frage, Sätze, welche Monate gemeint sind, und ob ein Durchschnitt über mehrere Monate gemeint
    ist (Jahreszeit, Quartal, Halbjahr oder ein Durchschnittswort). Wörtliche Monate bleiben stehen.
    """
    teile, jahresstellen, _ = _aufloesen(frage, letzter)
    notizen: list[str] = []
    mittel = False
    # Von hinten ersetzen, damit die Stellen davor gültig bleiben; das verwendete Jahr steht danach im Monat.
    aenderungen: list[tuple[int, int, str, Zeitraum | None]] = [(a, b, "", None) for a, b in jahresstellen]
    for z in teile:
        ersatz = (
            monat_anzeige(z.von) if z.von == z.bis else f"{monat_anzeige(z.von)} bis {monat_anzeige(z.bis)}"
        )
        aenderungen.append((z.start, z.ende, ersatz, z))
    for start, ende, ersatz, teil in sorted(aenderungen, key=lambda x: x[0], reverse=True):
        frage = frage[:start] + ersatz + frage[ende:]
        if teil is None:
            continue
        satz = teil.erklaerung()
        if satz:
            notizen.insert(0, satz)
        if teil.mehrere and teil.art in ("jahreszeit", "quartal", "halbjahr"):
            mittel = True
    if DURCHSCHNITT_WORT.search(frage):
        mittel = True
    gesamt = zeitraum_lesen(frage, letzter)
    if gesamt is not None and gesamt.art == "liste":
        mittel = False  # aufgezählte Monate sind kein durchgehender Zeitraum
    return frage, notizen, mittel


def unklar(frage: str, letzter: str | None = None) -> str | None:
    """Ein Satz, wenn die Frage einen Zeitraum nennt, der nicht eindeutig ist; sonst None.

    „Sommerhalbjahr“ und „Wintersaison“ meinen je nach Fach andere Monate, „Winter 2025/27“ widerspricht sich. Mit
    ``letzter`` (jüngster Monat mit Daten) auch: Monat ohne Jahr neben Jahren, die nicht eindeutig zu ihm gehören.
    """
    kurz = _KURZES_JAHR.search(frage)
    if kurz:
        return (
            # Ohne Anführungszeichen: In /uc3/fragen würde das Zitat ein Knopf, der dieselbe Frage noch einmal stellt.
            f"Bei {kurz.group(0).strip()} ist das Jahr nicht eindeutig. Bitte das Jahr vierstellig nennen, "
            "zum Beispiel „Winter 2024/25“ oder „März 2025“."
        )
    for muster, gruppe in ((ZAHL_MONAT, 1), (ISO, 2)):
        for fund in muster.finditer(frage):
            if not 1 <= int(fund.group(gruppe)) <= 12:
                return (
                    f"„{fund.group(0)}“ ist kein Monat, ein Jahr hat zwölf. "
                    "Welchen Monat meinen Sie, zum Beispiel „Beschäftigte im März 2025“?"
                )
    t = _HALBJAHR_SAISON.search(frage)
    if t:
        return (
            f"{t.group(0)[:1].upper()}{t.group(0)[1:]} ist nicht eindeutig. Bitte die Monate nennen, "
            "zum Beispiel „Beschäftigte von Mai bis Oktober 2025“."
        )
    for t in _JAHRESZEIT.finditer(frage):
        if t.group(2) and t.group(3):
            jahr = int(t.group(2))
            zweites = int(t.group(3)) if len(t.group(3)) == 4 else (jahr // 100) * 100 + int(t.group(3))
            if not t.group(1).lower().startswith("winter") or zweites != jahr + 1:
                return (
                    f"{t.group(0).strip()} passt nicht zusammen. "
                    f"Meinen Sie „Beschäftigte im Winter {jahr}/{str(jahr + 1)[2:]}“?"
                )
    return _aufloesen(frage, letzter)[2]


def tag_hinweis(frage: str) -> str | None:
    """Ein Satz, wenn die Frage einen Tag nennt, der nicht der Monatsletzte ist (gezählt wird am Monatsletzten)."""
    from calendar import monthrange

    for t in _DATUM.finditer(frage):
        if t.group(1):
            tag, nummer, jahr = int(t.group(1)), int(t.group(2)), int(t.group(3))
        else:
            jahr, nummer, tag = int(t.group(4)), int(t.group(5)), int(t.group(6))
        if not 1 <= nummer <= 12:
            continue
        letzter_tag = monthrange(jahr, nummer)[1]
        if tag != letzter_tag:
            name = ANZEIGE_MONAT[nummer - 1]
            return (
                "Die Statistik zählt nur am letzten Tag jedes Monats. "
                f"Für den {tag}. {name} {jahr} zeigen wir darum den Stand vom {letzter_tag}. {name} {jahr}."
            )
    return None
