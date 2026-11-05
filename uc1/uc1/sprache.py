"""Sprachprüfung für jeden Text, den ein Mensch sieht (Issues #31, #32, #81, #107).

Deterministisch und ohne Modell. ``glaette`` ersetzt Gedankenstriche und streicht reine Floskeln,
``pruefe`` meldet, was bleibt: Gedankenstriche, Schablonen, Kaskaden, Emojis und zu lange Sätze.
Regeln stehen in ``daten/sprache.yaml``. Bindestriche in Wörtern („KI-Lotse“) und Bereiche („7-9“, „7–9“)
bleiben unverändert. Beträge, Paragraphen und Zitate ändert die Glättung nicht.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from functools import cache
from pathlib import Path
from typing import Any, Literal

import yaml

from uc1.eval import _ABKUERZUNGEN, _DATUM_PUNKT, _ORDNUNGSZAHL, _WORT

DATEN_DIR = Path(__file__).resolve().parent.parent / "daten"

Aktion = Literal["satz", "weg", "melden"]

# Gedankenstrich: Em-Dash immer; Halbgeviert- und Bindestrich nur mit Leerraum auf beiden Seiten und nicht
# zwischen zwei Zahlen („7 – 9“ ist ein Bereich). Ein Bindestrich am Zeilenanfang ist ein Listenpunkt.
_GEDANKENSTRICH = re.compile(r"\s*—\s*|(?<=\S)\s+[–-]\s+(?=\S)")
_ZAHL_BEREICH = re.compile(r"\d\s+[–-]\s+\d")
_EMOJI = re.compile("[\U0001f000-\U0001faff\U00002600-\U000027bf\U0001f1e6-\U0001f1ff⭐⭕✅❌️‍]")
_ZITAT = re.compile(r"„[^“”]*[“”]")
# Satzgrenze innerhalb einer Zeile; Abkürzungen maskiert vorher ``_maskiere``.
_SATZENDE = re.compile(r"(?<=[.!?])\s+(?=[A-ZÄÖÜ„\"(0-9])")


@dataclass(frozen=True)
class Befund:
    """Ein Sprachbefund: ``art`` (gedankenstrich, floskel, einleitung, ki, fuellwort, kaskade, emoji,
    satz_lang, mittel_lang), die Fundstelle und ob ``glaette`` ihn behebt."""

    art: str
    stelle: str
    behebbar: bool


@cache
def regeln() -> dict[str, Any]:
    daten: dict[str, Any] = yaml.safe_load((DATEN_DIR / "sprache.yaml").read_text(encoding="utf-8"))
    return daten


@cache
def _schablonen() -> tuple[tuple[str, Aktion, re.Pattern[str]], ...]:
    return tuple(
        (s["art"], s["aktion"], re.compile(s["muster"], re.IGNORECASE)) for s in regeln()["schablonen"]
    )


def _maskiere(text: str) -> str:
    """Punkte, die kein Satzende sind, wie in ``eval.mittlere_satzlaenge`` (gleiche Zählung)."""
    ohne = _ABKUERZUNGEN.sub(lambda m: m.group(0).replace(".", "\x00"), text)
    ohne = _DATUM_PUNKT.sub(lambda m: m.group(0).replace(".", "\x00"), ohne)
    ohne = _ORDNUNGSZAHL.sub(lambda m: m.group(0).replace(".", "\x00"), ohne)
    return re.sub(r"(?<=\d)\.(?=\d)", "\x00", ohne)


def saetze(text: str) -> list[str]:
    """Sätze je Zeile; eine Zeile ohne Satzzeichen (Überschrift, Listenpunkt) zählt als ein Satz."""
    ergebnis: list[str] = []
    for zeile in text.splitlines():
        for satz in _SATZENDE.split(_maskiere(zeile.strip())):
            satz = satz.replace("\x00", ".").strip()
            if _WORT.search(satz):
                ergebnis.append(satz)
    return ergebnis


def woerter(satz: str) -> int:
    return len(_WORT.findall(satz))


def mittlere_laenge(text: str) -> float:
    """Mittlere Wortzahl je Satz nach ``saetze`` (Zeilen getrennt gezählt)."""
    liste = saetze(text)
    return sum(woerter(s) for s in liste) / len(liste) if liste else 0.0


def _ersetze_strich(satz: str) -> str:
    """Gedankenstriche eines Satzes: ein einzelner vor einem kurzen Schluss wird Doppelpunkt, sonst Komma."""
    if _ZAHL_BEREICH.search(satz):
        satz = _ZAHL_BEREICH.sub(lambda m: m.group(0).replace(" ", ""), satz)
    funde = list(_GEDANKENSTRICH.finditer(satz))
    if not funde:
        return satz
    if len(funde) == 1:
        rest = satz[funde[0].end() :].rstrip(".!?")
        if 0 < woerter(rest) <= 6 and not re.search(r"[,;:]", rest):
            return satz[: funde[0].start()] + ": " + satz[funde[0].end() :]
    return _GEDANKENSTRICH.sub(", ", satz)


def _gross(satz: str) -> str:
    return satz[:1].upper() + satz[1:] if satz else satz


def _glaette_zeile(zeile: str) -> str:
    praefix = re.match(r"^\s*(?:[-*•]|\d+\.)\s+", zeile)
    kopf = praefix.group(0) if praefix else ""
    koerper = zeile[len(kopf) :]
    behalten: list[str] = []
    for satz in _SATZENDE.split(_maskiere(koerper)):
        satz = satz.replace("\x00", ".")
        satz = _EMOJI.sub("", satz)
        if any(aktion == "satz" and m.search(satz) for _, aktion, m in _schablonen()):
            continue
        for _, aktion, muster in _schablonen():
            if aktion == "weg":
                neu = muster.sub("", satz)
                if neu != satz:
                    satz = _gross(neu.lstrip()) if muster.search(satz[:30]) else neu
        satz = _ersetze_strich(satz)
        satz = re.sub(r"\s+([,.:;!?])", r"\1", satz)
        satz = re.sub(r"([,:;])\1+", r"\1", satz)
        satz = re.sub(r"[ \t]{2,}", " ", satz).strip()
        if _WORT.search(satz):
            behalten.append(satz)
    if not behalten:
        return ""
    return kopf + " ".join(behalten)


def glaette(text: str) -> str:
    """Gedankenstriche ersetzen, Floskeln streichen, Emojis entfernen. Zeilen und Listen bleiben erhalten;
    eine Zeile, die nur aus Floskeln bestand, fällt weg."""
    zeilen = [_glaette_zeile(z) if z.strip() else z for z in text.splitlines()]
    return "\n".join(z for z, alt in zip(zeilen, text.splitlines(), strict=True) if z or not alt.strip())


def pruefe(text: str) -> list[Befund]:
    """Alle Sprachbefunde des Textes; ``behebbar`` sagt, ob ``glaette`` sie behebt.

    Wörtliche Zitate in „…“ zählen als ein Wort: Ihren Wortlaut gibt die Quelle vor, nicht der Lotse."""
    befunde: list[Befund] = []
    text = _ZITAT.sub("„Zitat“", text)
    for zeile in text.splitlines():
        for m in _GEDANKENSTRICH.finditer(zeile):
            umfeld = zeile[max(0, m.start() - 12) : m.end() + 12]
            if not _ZAHL_BEREICH.search(umfeld) and not re.match(r"^\s*-\s", zeile[: m.end()]):
                befunde.append(Befund("gedankenstrich", umfeld.strip(), True))
    for m in _EMOJI.finditer(text):
        befunde.append(Befund("emoji", m.group(0), True))
    for art, aktion, muster in _schablonen():
        for m in muster.finditer(text):
            if aktion == "melden" and any(
                a != "melden" and x.search(text[max(0, m.start() - 2) : m.end() + 40])
                for _, a, x in _schablonen()
            ):
                continue  # dieselbe Stelle behebt schon eine „satz“- oder „weg“-Regel
            befunde.append(Befund(art, m.group(0).strip(), aktion != "melden"))
    kaskade = regeln()["kaskade"]
    anschluesse = re.findall(kaskade["muster"], text, re.IGNORECASE)
    if len(anschluesse) >= int(kaskade["ab"]):
        befunde.append(Befund("kaskade", ", ".join(anschluesse), False))
    grenzen = regeln()["satzlaenge"]
    for satz in saetze(text):
        if woerter(satz) > int(grenzen["hoechstens"]):
            befunde.append(Befund("satz_lang", f"{woerter(satz)} Wörter: {satz[:60]}", False))
    mittel = mittlere_laenge(text)
    if mittel >= float(grenzen["mittel"]):
        befunde.append(Befund("mittel_lang", f"{mittel:.1f} Wörter je Satz", False))
    return befunde


def kurzname(datei: str) -> str:
    """Anzeigename einer Datei: aus ``dateinamen`` in sprache.yaml, sonst ohne Ordner, Zahlensuffix und
    Endung („Anträge und Formulare/x.1736522017.pdf“ → „x“)."""
    stamm = re.sub(r"(?:\.\d+)?\.(?:pdf|docx?|html?|txt)$", "", datei.rsplit("/", 1)[-1], flags=re.IGNORECASE)
    namen: dict[str, str] = regeln().get("dateinamen") or {}
    return namen.get(stamm, stamm.replace("_", " "))


def kurze_quelle(schluessel: str) -> str:
    """Quelle für den Halbsatz: „BPGG § 4“ bleibt, „Ordner/Datei.pdf, S. 5“ wird „Kurzname, S. 5“."""
    datei, trenner, rest = schluessel.partition(", ")
    if "/" in datei or re.search(r"\.(?:pdf|docx?|html?)$", datei, re.IGNORECASE):
        return kurzname(datei) + (trenner + rest if trenner else "")
    return schluessel
