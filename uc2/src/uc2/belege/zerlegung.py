"""Zerlegung einer Pressespiegel-Ausgabe (Text aus `pdftotext -layout`) in Artikel.

Der Parser arbeitet nur auf Text; `pdftotext` ruft allein die Datei-Stufe (`extraktion`) auf. Seiten sind
durch Formfeed getrennt. Leitfaden ist das Inhaltsverzeichnis: je Eintrag wird ab der genannten PDF-Seite
die Startzeile `<Medium> vom TT.MM.JJJJ` gesucht, der Text läuft bis zum Feldblock (`Quelle …`). Seiten
ohne Kopfzeile „Pressespiegel“ sind Layout-Kopien des Zeitungsscans und werden verworfen.

Datenschutz: Die Zeile `Autor:in` wird nie gelesen, gespeichert oder ausgegeben, ebenso Sprecherzeilen
von Radio-Beiträgen (`Name (Sender) (17 Sekunden)`).
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from datetime import date

KOPFZEILE = "Pressespiegel"
FUSSZEILE_RE = re.compile(r"Seite \d+ von \d+\s+©\s*APA-Comm")
TOC_START_RE = re.compile(r"^S\.\s*(\d+)\s{2,}(\S.*)$")
TOC_META_RE = re.compile(r"^(\d{2}\.\d{2}\.\d{4}),\s+(.+?)(?:,\s+Seite\s+(\S.*))?$")
STARTZEILE_RE = re.compile(r"^(\S.*?) vom (\d{2}\.\d{2}\.\d{4})$")
FELDBLOCK_RE = re.compile(r"^(?:Sender|Quelle)\s{2,}\S")
FELD_RE = re.compile(r"^(Sender|Quelle|Typ)\s{2,}(\S.*)$")
FOLGEFELD_RE = re.compile(r"^(?:Mutation|Typ|Land|Sprache|Adresse)\s{2,}\S|^\S+$")
GESCHUETZT = "Autor:in"
SPRECHERZEILE_RE = re.compile(r"\(\d+ Sekunden\)$")
RADIO_BEIWERK = (
    "Sendungsdatum:",
    "Sendungsbeginn:",
    "Sendungsdauer:",
    "Link zur Sendung",
    "Der angezeigte Beitrag beruht auf automatisierter Spracherkennung",
    "Für abrufbare Audio-/Video-Beiträge",
    "sind, kann keine Rechtegarantie übernommen werden.",
)
BINDEWOERTER = frozenset({"und", "oder", "bzw.", "sowie", "bis", "als", "noch", "wie"})
SATZENDE = tuple('.!?:;“”"«»)')


@dataclass(frozen=True)
class Eintrag:
    """Eintrag des Inhaltsverzeichnisses."""

    nr: int
    pdf_seite: int
    titel: str
    artikeldatum: str
    medium: str
    zeitungsseite: str | None


@dataclass(frozen=True)
class Artikel:
    nr: int
    pdf_seite: int
    zeitungsseite: str | None
    artikeldatum: str
    medium: str
    typ: str | None
    titel: str
    text: str
    nur_titel: bool = False
    """Radio/TV ohne Transkript: der Text ist der Titel (nicht in `artikel.jsonl`)."""


@dataclass
class Ausgabe:
    seiten: int
    eintraege: list[Eintrag] = field(default_factory=list)
    artikel: list[Artikel] = field(default_factory=list)
    abweichungen: list[dict[str, object]] = field(default_factory=list)


def iso_datum(tt_mm_jjjj: str) -> str:
    tag, monat, jahr = tt_mm_jjjj.split(".")
    return date(int(jahr), int(monat), int(tag)).isoformat()


def seiten_aus_text(text: str) -> list[list[str]]:
    """Teilt am Formfeed; leere Restseite nach dem letzten Formfeed fällt weg."""
    seiten = text.split("\f")
    if seiten and not seiten[-1].strip():
        seiten.pop()
    return [[zeile.rstrip() for zeile in seite.split("\n")] for seite in seiten]


def ist_artikelseite(zeilen: list[str]) -> bool:
    """Seiten des Pressespiegels tragen oben „Pressespiegel“; Layout-Kopien nicht."""
    for zeile in zeilen:
        if zeile.strip():
            return zeile.strip() == KOPFZEILE
    return False


def inhaltszeilen(zeilen: list[str]) -> list[str]:
    """Zeilen ohne Kopf- und Fußzeile, ohne geschützte Zeilen, getrimmt; Leerzeilen bleiben.

    Abstände innerhalb der Zeile bleiben, weil Verzeichnis und Feldblock sie als Trenner brauchen.
    """
    ergebnis: list[str] = []
    kopf_gesehen = False
    for zeile in zeilen:
        s = zeile.strip()
        if not kopf_gesehen and s:
            kopf_gesehen = True
            if s == KOPFZEILE:
                continue
        if FUSSZEILE_RE.search(s) or s.startswith(GESCHUETZT):
            continue
        ergebnis.append(s)
    return ergebnis


def lies_inhaltsverzeichnis(seiten: list[list[str]]) -> list[Eintrag]:
    """Einträge ab der Seite mit „Inhaltsverzeichnis“, auch über mehrere Seiten und mit Titelumbruch."""
    start = next(
        (i for i, s in enumerate(seiten) if any(z.strip() == "Inhaltsverzeichnis" for z in s)),
        None,
    )
    if start is None:
        return []
    eintraege: list[Eintrag] = []
    offen: tuple[int, list[str]] | None = None
    for i in range(start, len(seiten)):
        if eintraege and i + 1 >= min(e.pdf_seite for e in eintraege):
            break
        gefunden = False
        for zeile in inhaltszeilen(seiten[i]):
            if not zeile or zeile == "Inhaltsverzeichnis":
                continue
            treffer = TOC_START_RE.match(zeile)
            if treffer:
                offen = (int(treffer.group(1)), [treffer.group(2)])
                gefunden = True
                continue
            if offen is None:
                continue
            meta = TOC_META_RE.match(zeile)
            if meta:
                eintraege.append(
                    Eintrag(
                        nr=len(eintraege) + 1,
                        pdf_seite=offen[0],
                        titel=verbinde_zeilen(offen[1]).replace("\n", " "),
                        artikeldatum=iso_datum(meta.group(1)),
                        medium=meta.group(2).strip(),
                        zeitungsseite=meta.group(3).strip() if meta.group(3) else None,
                    )
                )
                offen = None
            else:
                offen[1].append(zeile)
        if not gefunden and offen is None and i > start:
            break
    return eintraege


def _zeile_anhaengen(vorher: str, naechste: str) -> str:
    """Verbindet zwei Zeilen eines Absatzes und löst Silbentrennung am Zeilenende auf.

    „Arznei-“ + „mittel“ → „Arzneimittel“ (nächstes Zeichen klein); „Vier-“ + „Kilometer“ bleibt mit
    Bindestrich; „Gesundheits-“ + „und …“ bleibt eine Ergänzung mit Bindestrich und Leerzeichen.
    """
    if re.search(r"[^\W\d_]-$", vorher):
        erstes_wort = naechste.split(" ", 1)[0]
        if naechste[:1].islower() and erstes_wort not in BINDEWOERTER:
            return vorher[:-1] + naechste
        if naechste[:1].islower():
            return vorher + " " + naechste
        return vorher + naechste
    return vorher + " " + naechste


def verbinde_zeilen(zeilen: list[str]) -> str:
    """Fügt Layoutzeilen zu Absätzen zusammen (Absätze durch `\\n` getrennt).

    Absatzende: Leerzeile, „Bild:“-Zeile, oder eine deutlich kurze Zeile (Satzende oder Zwischentitel).
    """
    zeilen = [re.sub(r"\s+", " ", z.strip()) for z in zeilen]
    laengste = max((len(z) for z in zeilen), default=0)
    absaetze: list[str] = []
    aktuell = ""
    for zeile in zeilen:
        if not zeile:
            if aktuell:
                absaetze.append(aktuell)
                aktuell = ""
            continue
        if zeile.startswith("Bild:") and aktuell:
            absaetze.append(aktuell)
            aktuell = ""
        aktuell = _zeile_anhaengen(aktuell, zeile) if aktuell else zeile
        endet_satz = zeile.endswith(SATZENDE) and len(zeile) < 0.85 * laengste
        zwischentitel = not zeile.endswith("-") and len(zeile) < 0.5 * laengste
        if endet_satz or zwischentitel or zeile.startswith("Bild:"):
            absaetze.append(aktuell)
            aktuell = ""
    if aktuell:
        absaetze.append(aktuell)
    return "\n".join(absaetze)


def _vergleichsform(text: str) -> str:
    text = unicodedata.normalize("NFC", text).casefold()
    return re.sub(r"[\W_]+", "", text)


def _titel_abtrennen(zeilen: list[str], titel: str) -> tuple[list[str], bool]:
    """Entfernt die (ggf. umgebrochenen) Titelzeilen am Textanfang, wenn sie dem Verzeichnis entsprechen.

    Eine Dachzeile vor dem Titel („Interview mit …“) darf bis zu zwei Zeilen lang sein und bleibt im Text.
    """
    ziel = _vergleichsform(titel)
    nicht_leer = [i for i, z in enumerate(zeilen) if z][:3]
    for erste in nicht_leer:
        for ende in range(erste + 1, min(erste + 7, len(zeilen)) + 1):
            kandidat = _vergleichsform(verbinde_zeilen(zeilen[erste:ende]))
            if kandidat == ziel:
                return zeilen[:erste] + zeilen[ende:], True
            if not ziel.startswith(kandidat):
                break
    return zeilen, False


def _ist_beiwerk(zeile: str) -> bool:
    return zeile.startswith(RADIO_BEIWERK)


def _klammertiefe(zeile: str) -> int:
    return zeile.count("(") - zeile.count(")")


def ohne_sprecher(zeilen: list[str], max_folgezeilen: int = 4) -> list[str]:
    """Verwirft Sprechereinträge von Radio/TV (`Name (Organisation) (17 Sekunden)`), auch umbrochene.

    Ein Eintrag reicht von seiner ersten Zeile bis zur Zeile, die auf `(N Sekunden)` endet und die dort
    offene Klammer schließt. Transkript-Zeilen wie `(00:03:10) : … Text` sind ausgeglichen und bleiben.
    """
    ergebnis: list[str] = []
    i = 0
    while i < len(zeilen):
        if SPRECHERZEILE_RE.search(zeilen[i]):
            i += 1
            continue
        ende = _sprecher_ende(zeilen, i, max_folgezeilen)
        if ende is not None:
            i = ende + 1
            continue
        ergebnis.append(zeilen[i])
        i += 1
    return ergebnis


def _sprecher_ende(zeilen: list[str], start: int, max_folgezeilen: int) -> int | None:
    """Letzte Zeile eines umbrochenen Sprechereintrags ab `start`, sonst None.

    Leerzeilen innerhalb des Eintrags werden mit verworfen.
    """
    tiefe = _klammertiefe(zeilen[start])
    if tiefe <= 0:
        return None
    folgezeilen = 0
    for j in range(start + 1, len(zeilen)):
        if not zeilen[j]:
            continue  # Leerzeilen, etwa vom Seitenwechsel, gehören nicht zum Eintrag
        folgezeilen += 1
        if folgezeilen > max_folgezeilen:
            return None
        tiefe += _klammertiefe(zeilen[j])
        if tiefe <= 0:
            return j if SPRECHERZEILE_RE.search(zeilen[j]) else None
    return None


def _startzeile(zeilen: list[str]) -> int | None:
    """Index der Startzeile, wenn sie die erste Inhaltszeile der Seite ist."""
    for i, zeile in enumerate(zeilen):
        if zeile:
            return i if STARTZEILE_RE.match(zeile) else None
    return None


def zerlege_ausgabe(text: str) -> Ausgabe:
    """Zerlegt eine Ausgabe in Artikel und listet Abweichungen gegen das Inhaltsverzeichnis."""
    seiten = seiten_aus_text(text)
    ausgabe = Ausgabe(seiten=len(seiten))
    ausgabe.eintraege = lies_inhaltsverzeichnis(seiten)
    if not ausgabe.eintraege:
        ausgabe.abweichungen.append({"art": "inhaltsverzeichnis_fehlt"})
        return ausgabe

    def abweichung(eintrag: Eintrag, art: str, **mehr: object) -> None:
        ausgabe.abweichungen.append(
            {"art": art, "artikel_nr": eintrag.nr, "toc_seite": eintrag.pdf_seite, **mehr}
        )

    for k, eintrag in enumerate(ausgabe.eintraege):
        bis = ausgabe.eintraege[k + 1].pdf_seite if k + 1 < len(ausgabe.eintraege) else len(seiten) + 1
        bis = max(bis, eintrag.pdf_seite + 1)
        start: tuple[int, int] | None = None
        for seite in range(eintrag.pdf_seite, min(bis, len(seiten) + 1)):
            zeilen = seiten[seite - 1]
            if not ist_artikelseite(zeilen):
                continue
            idx = _startzeile(inhaltszeilen(zeilen))
            if idx is not None:
                start = (seite, idx)
                break
        if start is None:
            abweichung(eintrag, "startzeile_fehlt")
            continue
        if start[0] != eintrag.pdf_seite:
            abweichung(eintrag, "pdf_seite_abweichend", gefunden_seite=start[0])

        koerper: list[str] = []
        felder: dict[str, str] = {}
        feldblock = False
        seite = start[0]
        while seite < min(bis, len(seiten) + 1) and not feldblock:
            zeilen = inhaltszeilen(seiten[seite - 1])
            if seite == start[0]:
                zeilen = zeilen[start[1] + 1 :]
            elif not ist_artikelseite(seiten[seite - 1]):
                break  # Layout-Kopie: Artikel endet vor dieser Seite
            elif _startzeile(zeilen) is not None:
                abweichung(eintrag, "startzeile_ohne_eintrag", gefunden_seite=seite)
                break
            for zeile in zeilen:
                if feldblock:
                    treffer = FELD_RE.match(zeile)
                    if treffer:
                        felder.setdefault(treffer.group(1), treffer.group(2).strip())
                    continue
                if FELDBLOCK_RE.match(zeile):
                    feldblock = True
                    treffer = FELD_RE.match(zeile)
                    if treffer:
                        felder[treffer.group(1)] = treffer.group(2).strip()
                    continue
                if not _ist_beiwerk(zeile):
                    koerper.append(zeile)
            seite += 1
        if feldblock and seite < min(bis, len(seiten) + 1) and ist_artikelseite(seiten[seite - 1]):
            # Feldblock über den Seitenwechsel: nur Feldzeilen der Folgeseite lesen.
            for zeile in inhaltszeilen(seiten[seite - 1]):
                treffer = FELD_RE.match(zeile)
                if treffer:
                    felder.setdefault(treffer.group(1), treffer.group(2).strip())
                elif zeile and not FOLGEFELD_RE.match(zeile):
                    break
        if not feldblock:
            abweichung(eintrag, "feldblock_fehlt")

        koerper, titel_ok = _titel_abtrennen(ohne_sprecher(koerper), eintrag.titel)
        if not titel_ok:
            abweichung(eintrag, "titel_abweichend")
        inhalt = verbinde_zeilen(koerper).strip()
        nur_titel = False
        if not inhalt and titel_ok:
            # Radio-Beitrag nur mit Sprecherliste: der Titel ist der ganze Beleg.
            abweichung(eintrag, "nur_titel")
            inhalt = eintrag.titel
            nur_titel = True
        if not inhalt:
            abweichung(eintrag, "text_leer")
            continue
        medium = felder.get("Quelle") or eintrag.medium
        if "Sender" in felder and "Quelle" in felder:
            medium = f"{felder['Sender']} - {felder['Quelle']}"
        if medium != eintrag.medium:
            abweichung(eintrag, "medium_abweichend", medium=medium, toc_medium=eintrag.medium)
        ausgabe.artikel.append(
            Artikel(
                nr=eintrag.nr,
                pdf_seite=eintrag.pdf_seite,
                zeitungsseite=eintrag.zeitungsseite,
                artikeldatum=eintrag.artikeldatum,
                medium=medium,
                typ=felder.get("Typ"),
                titel=eintrag.titel,
                text=inhalt,
                nur_titel=nur_titel,
            )
        )
    if len(ausgabe.artikel) != len(ausgabe.eintraege):
        ausgabe.abweichungen.append(
            {
                "art": "artikelzahl",
                "gefunden": len(ausgabe.artikel),
                "inhaltsverzeichnis": len(ausgabe.eintraege),
            }
        )
    return ausgabe
