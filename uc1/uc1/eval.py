"""`lotse eval`: Lotse-Set prüfen und messen, ohne Sprachmodell (Issue #30).

Befehle:
  lotse eval --pruefe-set [--set PFAD]
      Schema, eindeutige IDs, Anzahl je Art und Existenz jeder `belegt_durch`-Datei. Ohne DB.
  lotse eval --nur-suche [--weg W[,W]] [--erweiterung E[,E]] [-k 5] [--set PFAD] [--ausgabe DATEI.md]
             [--grep-grundlinie] [--trotzdem]
      Recall@k (Wilson-Intervall 95 %), MRR@10, Rang und Latenz der Suche (uc1.suche) je Fall und
      Variante (Weg x Erweiterung); gepaarte Vergleiche (gewonnen : verloren, exakter McNemar);
      optional neben einer naiven lexikalischen Grundlinie über die rohen XML-Dateien.
      Erweiterung: aus | thesaurus | llm | datei:<pfad> (JSON {frage: [begriffe]}).
      Auf dem Test-Set lotse-set.yaml zählt jeder Lauf mit --ausgabe als Blick (höchstens 3,
      testset-blicke.json); darüber nur mit --trotzdem.
  lotse eval --nur-begriffe DATEI.json --erweiterung llm [--set PFAD]
      Begriffe je Frage erzeugen und als JSON speichern (für datei:<pfad> auf einem anderen Rechner).
  lotse eval
      Messung mit Modell; braucht den Lotse-Kern (#31) und endet bis dahin mit Exit 2.

Die Prüffunktionen (`zitat_treu`, `klassifiziere_verhalten`, `mittlere_satzlaenge`, `sprache`)
sind rein und entscheiden ohne Modell.
"""

from __future__ import annotations

import argparse
import importlib
import json
import math
import re
import shlex
import sys
import time
import unicodedata
import xml.etree.ElementTree as ET
from collections import Counter
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
from datetime import datetime
from functools import cache
from pathlib import Path
from typing import Any, Literal, Protocol

import yaml

from uc1 import config
from uc1.typen import SucheFn, Treffer

Verhalten = Literal["antwort", "abstinenz", "uebergabe"]

EVAL_DIR = Path(__file__).resolve().parent.parent / "eval"
STANDARD_SET = EVAL_DIR / "lotse-set.yaml"
VERHALTEN_DATEI = EVAL_DIR / "verhalten.yaml"
DEV_SET = EVAL_DIR / "dev-set.yaml"
# Zähler der Blicke auf das Test-Set (Review D6d): höchstens MAX_BLICKE Läufe bis zur Abgabe.
BLICKE_DATEI = EVAL_DIR / "testset-blicke.json"
MAX_BLICKE = 3
# MRR wird über die ersten MRR_TIEFE Treffer gerechnet; die Suche holt deshalb mindestens so viele.
MRR_TIEFE = 10
# Ein Zitat muss mindestens so lang sein, sonst ist es kein Beleg („die“ steht in jedem Abschnitt).
ZITAT_MIN_WOERTER = 6
ZITAT_MIN_ZEICHEN = 30
WEGE = ("volltext", "dicht", "hybrid", "auto")

ARTEN = ("golden", "web", "szenario", "grenze")
VERHALTEN: tuple[Verhalten, ...] = ("antwort", "abstinenz", "uebergabe")
# Erwartete Anzahl Einträge je Art: 12 Golden-Fälle, Fall 24 als Paar mit zwei Einträgen = 13.
SOLL_ANZAHL: dict[str, int] = {"golden": 13, "web": 4, "szenario": 2, "grenze": 8}
PFLICHTFELDER = (
    "id",
    "art",
    "golden_nr",
    "persona",
    "frage",
    "sprache",
    "erwarteter_traeger",
    "erwartete_quellen",
    "verhalten_soll",
    "grenze",
    "soll_text",
    "belegt_durch",
)


# --------------------------------------------------------------------------- Set laden und prüfen


class SetFehler(ValueError):
    """Das Lotse-Set verletzt das Schema."""


def lade_set(pfad: Path = STANDARD_SET) -> list[dict[str, Any]]:
    daten = yaml.safe_load(pfad.read_text(encoding="utf-8"))
    if not isinstance(daten, dict) or not isinstance(daten.get("faelle"), list):
        raise SetFehler(f"{pfad}: Schlüssel 'faelle' mit einer Liste fehlt")
    faelle: list[dict[str, Any]] = daten["faelle"]
    return faelle


def _pruefe_quelle(fall_id: str, quelle: Any) -> list[str]:
    if not isinstance(quelle, dict):
        return [f"{fall_id}: Quelle ist kein Objekt: {quelle!r}"]
    if "datei" in quelle:
        if not isinstance(quelle["datei"], str):
            return [f"{fall_id}: 'datei' ist kein Text"]
        seite = quelle.get("seite")
        if seite is not None and (not isinstance(seite, int) or isinstance(seite, bool) or seite < 1):
            return [f"{fall_id}: 'seite' muss eine Zahl ab 1 sein: {seite!r}"]
        return []
    fehlend = [f for f in ("gesetz", "art", "nummer") if not isinstance(quelle.get(f), str)]
    return [f"{fall_id}: Quelle ohne {', '.join(fehlend)}: {quelle!r}"] if fehlend else []


def verhalten_liste(wert: Any) -> list[str]:
    return [wert] if isinstance(wert, str) else list(wert or [])


def pruefe_set(faelle: Sequence[dict[str, Any]], daten_dir: Path | None) -> list[str]:
    """Liefert alle Schemaverstöße als Text. Leere Liste heißt: Set ist gültig.

    Ist `daten_dir` None, wird die Existenz der `belegt_durch`-Dateien nicht geprüft.
    """
    fehler: list[str] = []
    ids: Counter[str] = Counter()
    anzahl: Counter[str] = Counter()
    paare: dict[str, list[dict[str, Any]]] = {}
    for nr, fall in enumerate(faelle, 1):
        fid = str(fall.get("id", f"#{nr}"))
        fehlend = [f for f in PFLICHTFELDER if f not in fall]
        if fehlend:
            fehler.append(f"{fid}: Pflichtfelder fehlen: {', '.join(fehlend)}")
            continue
        ids[fid] += 1
        art = fall["art"]
        if art not in ARTEN:
            fehler.append(f"{fid}: unbekannte art {art!r}")
        anzahl[art] += 1
        if fall["sprache"] not in ("de", "en"):
            fehler.append(f"{fid}: sprache muss de oder en sein")
        if not isinstance(fall["grenze"], bool):
            fehler.append(f"{fid}: grenze muss bool sein")
        soll = verhalten_liste(fall["verhalten_soll"])
        if not soll or any(v not in VERHALTEN for v in soll):
            fehler.append(f"{fid}: verhalten_soll ungültig: {fall['verhalten_soll']!r}")
        if not isinstance(fall["erwartete_quellen"], list):
            fehler.append(f"{fid}: erwartete_quellen ist keine Liste")
        else:
            for quelle in fall["erwartete_quellen"]:
                fehler += _pruefe_quelle(fid, quelle)
        if not str(fall["frage"]).strip():
            fehler.append(f"{fid}: frage ist leer")
        if fall.get("paar"):
            paare.setdefault(str(fall["paar"]), []).append(fall)
        fehler += _pruefe_zusatz(fid, fall)
        if daten_dir is not None:
            for datei in fall["belegt_durch"] or []:
                if not (daten_dir / datei).is_file():
                    fehler.append(f"{fid}: belegt_durch fehlt im Korpus: {datei}")
    fehler += [f"doppelte id: {fid} ({n}x)" for fid, n in ids.items() if n > 1]
    for art, soll_n in SOLL_ANZAHL.items():
        if anzahl[art] != soll_n:
            fehler.append(f"art {art}: {anzahl[art]} Einträge, erwartet {soll_n}")
    for kennung, glieder in paare.items():
        if len(glieder) != 2:
            fehler.append(f"paar {kennung}: {len(glieder)} Einträge, erwartet 2")
        elif _quellmenge(glieder[0]) != _quellmenge(glieder[1]):
            fehler.append(f"paar {kennung}: erwartete Quellmengen unterscheiden sich")
    return fehler


def _pruefe_zusatz(fid: str, fall: dict[str, Any]) -> list[str]:
    """Optionale Felder der Szenarien: nicht_erwartet (Liste von Quellen), buendel (Liste nicht leerer
    Gruppen von Quellen)."""
    fehler: list[str] = []
    if "nicht_erwartet" in fall:
        if not isinstance(fall["nicht_erwartet"], list):
            fehler.append(f"{fid}: nicht_erwartet ist keine Liste")
        else:
            for quelle in fall["nicht_erwartet"]:
                fehler += _pruefe_quelle(fid, quelle)
    if "buendel" in fall:
        gruppen = fall["buendel"]
        if not isinstance(gruppen, list) or not gruppen:
            fehler.append(f"{fid}: buendel ist keine nicht leere Liste")
        else:
            for nr, gruppe in enumerate(gruppen, 1):
                if not isinstance(gruppe, list) or not gruppe:
                    fehler.append(f"{fid}: buendel Gruppe {nr} ist keine nicht leere Liste")
                    continue
                for quelle in gruppe:
                    fehler += _pruefe_quelle(fid, quelle)
    return fehler


def _quellmenge(fall: dict[str, Any]) -> frozenset[tuple[str, ...]]:
    return frozenset(_schluessel(q) for q in fall["erwartete_quellen"])


# --------------------------------------------------------------------------- Treffer-Abgleich


def _norm(wert: str | None) -> str:
    return (wert or "").strip().casefold()


def _schluessel(quelle: dict[str, Any]) -> tuple[str, ...]:
    if "datei" in quelle:
        return ("datei", _norm(Path(str(quelle["datei"])).name))
    return ("norm", _norm(quelle["gesetz"]), _norm(quelle["art"]), _norm(quelle["nummer"]))


def trifft(treffer: Treffer, quelle: dict[str, Any]) -> bool:
    """Gleiches Gesetz, gleiche Art, gleiche Nummer (jede Fassung zählt); für PDFs gleiche Datei und, wenn
    die erwartete Quelle eine `seite` nennt, gleiche Seite."""
    if "datei" in quelle:
        if _norm(Path(treffer.datei).name) != _norm(Path(str(quelle["datei"])).name):
            return False
        return quelle.get("seite") is None or treffer.seite == quelle["seite"]
    return (
        _norm(treffer.gesetz) == _norm(quelle["gesetz"])
        and _norm(treffer.art) == _norm(quelle["art"])
        and _norm(treffer.nummer) == _norm(quelle["nummer"])
    )


def rang(
    treffer: Sequence[Treffer], quellen: Sequence[dict[str, Any]], ueberschrift_regex: str | None = None
) -> int | None:
    """1-basierter Rang des ersten Treffers, der eine erwartete Quelle ist; None ohne Treffer.

    Mit ueberschrift_regex (Dev-Set) zählt auch ein SozDok-Treffer, dessen Überschrift (kontext) die
    Regex erfüllt. So zählen parallele Normen anderer Träger (GSVG, BSVG, B-KUVG) mit."""
    muster = re.compile(ueberschrift_regex, re.IGNORECASE) if ueberschrift_regex else None
    for i, t in enumerate(treffer, 1):
        if any(trifft(t, q) for q in quellen):
            return i
        if muster and t.quelle == "sozdok" and muster.search(t.kontext):
            return i
    return None


@dataclass(frozen=True)
class FallErgebnis:
    id: str
    rang: int | None
    latenz_ms: float
    begriffe: tuple[str, ...] = ()


@dataclass(frozen=True)
class Messung:
    name: str
    k: int
    ergebnisse: tuple[FallErgebnis, ...]
    weg: str = ""
    erweiterung: str = ""

    def getroffen(self, i: int) -> bool:
        e = self.ergebnisse[i]
        return e.rang is not None and e.rang <= self.k

    @property
    def treffer_anzahl(self) -> int:
        return sum(self.getroffen(i) for i in range(len(self.ergebnisse)))

    @property
    def recall(self) -> str:
        return f"{self.treffer_anzahl}/{len(self.ergebnisse)}"

    @property
    def intervall(self) -> tuple[float, float]:
        return wilson(self.treffer_anzahl, len(self.ergebnisse))

    @property
    def mrr(self) -> float:
        """Mittlerer Kehrwert des Rangs, Ränge über MRR_TIEFE zählen 0."""
        if not self.ergebnisse:
            return 0.0
        return sum(1 / e.rang for e in self.ergebnisse if e.rang is not None and e.rang <= MRR_TIEFE) / len(
            self.ergebnisse
        )

    def latenz(self, quantil: float) -> float:
        return perzentil([e.latenz_ms for e in self.ergebnisse], quantil)


# --------------------------------------------------------------------------- Statistik


def wilson(treffer: int, n: int, z: float = 1.959964) -> tuple[float, float]:
    """Wilson-Intervall (95 %) für eine Quote treffer/n; bei kleinem n und Quoten nahe 0 oder 1 ehrlicher
    als das Normalintervall. n = 0 ergibt (0, 1)."""
    if n <= 0:
        return 0.0, 1.0
    p = treffer / n
    nenner = 1 + z * z / n
    mitte = (p + z * z / (2 * n)) / nenner
    halb = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / nenner
    return max(0.0, mitte - halb), min(1.0, mitte + halb)


def mcnemar_exakt(gewonnen: int, verloren: int) -> float:
    """Exakter zweiseitiger McNemar-Test: Binomialtest der diskordanten Paare gegen p = 0,5."""
    n = gewonnen + verloren
    if n == 0:
        return 1.0
    schwanz = sum(math.comb(n, i) for i in range(min(gewonnen, verloren) + 1))
    return min(1.0, 2 * schwanz / 2**n)


@dataclass(frozen=True)
class Paarvergleich:
    """B gegen A über dieselben Fälle: gewonnen = B trifft in Top k, A nicht; verloren umgekehrt."""

    a: str
    b: str
    gewonnen: int
    verloren: int
    gleich: int

    @property
    def p(self) -> float:
        return mcnemar_exakt(self.gewonnen, self.verloren)


def vergleiche(a: Messung, b: Messung) -> Paarvergleich:
    if [e.id for e in a.ergebnisse] != [e.id for e in b.ergebnisse]:
        raise ValueError(f"{a.name} und {b.name} haben verschiedene Fälle")
    gew = ver = 0
    for i in range(len(a.ergebnisse)):
        ta, tb = a.getroffen(i), b.getroffen(i)
        gew += tb and not ta
        ver += ta and not tb
    return Paarvergleich(a.name, b.name, gew, ver, len(a.ergebnisse) - gew - ver)


def paare(messungen: Sequence[Messung]) -> list[tuple[Messung, Messung]]:
    """Sinnvolle Paare (A, B): gleiche Erweiterung und anderer Weg, oder gleicher Weg und B erweitert
    gegen A = aus. Passt keines und sind es genau zwei (Suche gegen grep): die erste gegen die zweite."""
    ergebnis = []
    for a in messungen:
        for b in messungen:
            if a is b or not a.weg or not b.weg:
                continue
            weg_paar = a.erweiterung == b.erweiterung and (a.weg, b.weg) in (
                ("volltext", "hybrid"),
                ("volltext", "kern"),  # Suche im Kern gegen die nackte Suche bei gleicher Erweiterung
            )
            erw_paar = a.weg == b.weg and a.erweiterung == "aus" and b.erweiterung != "aus"
            if weg_paar or erw_paar:
                ergebnis.append((a, b))
    if not ergebnis and len(messungen) == 2:
        return [(messungen[1], messungen[0])]
    return ergebnis


def perzentil(werte: Sequence[float], quantil: float) -> float:
    """Nearest-rank-Perzentil; bei kleinem n ehrlicher als Interpolation."""
    if not werte:
        return 0.0
    geordnet = sorted(werte)
    index = max(0, math.ceil(quantil * len(geordnet)) - 1)
    return geordnet[index]


def faelle_mit_korpusquelle(faelle: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    return [f for f in faelle if f["erwartete_quellen"]]


_KLAMMER = re.compile(r"\s*\([^)]*\)")


def persona_text(persona: Any) -> str:
    """Persona ohne Annotationen in Klammern: „Mirela, 41, selbständige Grafikerin (GSVG), Graz“ wird
    „Mirela, 41, selbständige Grafikerin, Graz“. Die Klammern sind Notizen des Set-Autors („GSVG“); ein
    Bürger sagt „selbständig“, nicht „GSVG“, und die Suche darf das Soll nicht geschenkt bekommen."""
    return re.sub(r"\s+", " ", _KLAMMER.sub("", str(persona or ""))).strip(" ,;")


def anfrage(fall: dict[str, Any]) -> str:
    """Suchanfrage eines Falls: Persona (ohne Klammern) als eigener Satz, Vorspann, Frage. Die Persona trägt
    Angaben, die ein Bürger nennen würde (Alter, Beruf, Pension, Ort); das eingefrorene Set bleibt dafür
    unverändert (Review !25)."""
    teile = [persona_text(fall.get("persona")), str(fall.get("vorspann") or "").strip(), str(fall["frage"])]
    if teile[0] and not teile[0].endswith((".", "!", "?")):
        teile[0] += "."
    return " ".join(t for t in teile if t).strip()


Begriffe = Callable[[str], list[str]]


def messe(
    name: str,
    faelle: Sequence[dict[str, Any]],
    suche_fn: Callable[[str, int], list[Treffer]],
    k: int,
    *,
    begriffe: Begriffe | None = None,
    weg: str = "",
    erweiterung: str = "",
) -> Messung:
    """Je Fall Rang (über max(k, MRR_TIEFE) Treffer) und Latenz. Die Erweiterung (begriffe) läuft vor der
    Zeitmessung; gemessen wird nur die Suche mit der erweiterten Anfrage. Aufwärmen: `aufwaermen`."""
    ergebnisse = []
    tiefe = max(k, MRR_TIEFE)
    for fall in faelle:
        frage = anfrage(fall)
        zusatz = begriffe(frage) if begriffe else []
        if zusatz:
            from uc1.erweiterung import anfrage_aus

            frage = anfrage_aus(frage, zusatz)
        start = time.perf_counter()
        treffer = suche_fn(frage, tiefe)
        dauer = (time.perf_counter() - start) * 1000
        r = rang(treffer[:tiefe], fall["erwartete_quellen"], fall.get("ueberschrift_regex"))
        ergebnisse.append(FallErgebnis(str(fall["id"]), r, dauer, tuple(zusatz)))
    return Messung(name, k, tuple(ergebnisse), weg, erweiterung)


def aufwaermen(faelle: Sequence[dict[str, Any]], suche_fn: Callable[[str, int], Any]) -> None:
    """Eine Aufwärmrunde über alle Fälle ohne Erweiterung, nicht gezählt: Danach liegen Plan- und
    Seiten-Caches der DB für jede Anfrage warm, und die erste gemessene Variante zahlt keinen Kaltstart
    (Review !25: ein Aufwärmlauf mit Fall 1 wärmte nur Fall 1)."""
    for fall in faelle:
        suche_fn(anfrage(fall), MRR_TIEFE)


# --------------------------------------------------------------------------- Grep-Grundlinie

_WORT = re.compile(r"\w+", re.UNICODE)


def fragewoerter(text: str) -> list[str]:
    return sorted({w for w in _WORT.findall(text.casefold()) if len(w) >= 4})


@dataclass(frozen=True)
class RohDokument:
    datei: str
    gesetz: str
    art: str
    nummer: str
    woerter: Counter[str]


def lade_rohkorpus(daten_dir: Path) -> list[RohDokument]:
    """Liest den `nutzdaten`-Text aller SozDok-XML einmal; Kennung aus dem Dateinamen."""
    dokumente = []
    for pfad in sorted((daten_dir / "Rechtstexte").glob("*.xml")):
        teile = pfad.stem.split("=")
        if len(teile) < 3:
            continue
        try:
            knoten = ET.parse(pfad).getroot().find(".//nutzdaten")
        except ET.ParseError:
            continue
        text = "".join(knoten.itertext()) if knoten is not None else ""
        woerter = Counter(w for w in _WORT.findall(text.casefold()) if len(w) >= 4)
        rel = str(pfad.relative_to(daten_dir))
        dokumente.append(RohDokument(rel, teile[0], teile[1], teile[2], woerter))
    return dokumente


def grep_suche(dokumente: Sequence[RohDokument]) -> Callable[[str, int], list[Treffer]]:
    """Naive Grundlinie: Summe der Vorkommen aller Fragewörter (>= 4 Zeichen), Top-k Dateien."""

    def suche(frage: str, k: int) -> list[Treffer]:
        woerter = fragewoerter(frage)
        bewertet = [(sum(d.woerter[w] for w in woerter), d) for d in dokumente]
        bewertet = [b for b in bewertet if b[0] > 0]
        bewertet.sort(key=lambda b: (-b[0], b[1].datei))
        return [_als_treffer(d, punkte, i) for i, (punkte, d) in enumerate(bewertet[:k])]

    return suche


def _als_treffer(d: RohDokument, punkte: int, i: int) -> Treffer:
    return Treffer(
        abschnitt_id=i,
        dokid=Path(d.datei).stem,
        quelle="sozdok",
        datei=d.datei,
        gesetz=d.gesetz,
        art=d.art,
        nummer=d.nummer,
        inkrafttreten=None,
        seite=None,
        zeile=None,
        kontext=f"{d.gesetz} {d.nummer}",
        text="",
        score=float(punkte),
        weg="volltext",  # lexikalische Grundlinie; die Messung heißt „grep“
    )


# --------------------------------------------------------------------------- Bericht


def _prozent(wert: float) -> str:
    return f"{100 * wert:.0f} %"


def bericht(
    messungen: Sequence[Messung],
    faelle: Sequence[dict[str, Any]],
    befehl: str,
    kopf: Sequence[str] = (),
    titel: str = "Lotse-Set: Suche (Recall@k)",
) -> str:
    zeitpunkt = datetime.now().astimezone().isoformat(timespec="seconds")
    quellen = {str(f["id"]): f["erwartete_quellen"] for f in faelle}
    zeilen = [
        f"# {titel}",
        "",
        f"- Zeitpunkt: {zeitpunkt}",
        f"- Befehl: `{befehl}`",
        *(f"- {z}" for z in kopf),
        f"- Zählende Fälle (mit Korpusquelle, n={len(faelle)}): {', '.join(str(f['id']) for f in faelle)}",
        f"- Intervall: Wilson 95 %. MRR über die ersten {MRR_TIEFE} Treffer (Rang darüber zählt 0).",
        "",
        *messtabelle(messungen),
        *art_tabelle(messungen, faelle),
        *paartabelle(messungen),
    ]
    zeilen += rohtabelle(messungen, quellen)
    mit_begriffen = [m for m in messungen if any(e.begriffe for e in m.ergebnisse)]
    gesehen: set[str] = set()
    for m in mit_begriffen:
        if m.erweiterung in gesehen:
            continue
        gesehen.add(m.erweiterung)
        zeilen += ["", f"Begriffe der Erweiterung {m.erweiterung}:", ""]
        zeilen += [f"- {e.id}: {', '.join(e.begriffe) or '–'}" for e in m.ergebnisse]
    return "\n".join(zeilen) + "\n"


def messtabelle(messungen: Sequence[Messung]) -> list[str]:
    zeilen = [
        f"| Weg | Recall@k | Wilson 95 % | MRR@{MRR_TIEFE} | k | Latenz p50 (ms) | Latenz p95 (ms) |",
        "|---|---|---|---|---|---|---|",
    ]
    for m in messungen:
        unten, oben = m.intervall
        zeilen.append(
            f"| {m.name} | {m.recall} | {_prozent(unten)}–{_prozent(oben)} | {m.mrr:.3f} | {m.k} |"
            f" {m.latenz(0.5):.1f} | {m.latenz(0.95):.1f} |"
        )
    return zeilen


def art_tabelle(messungen: Sequence[Messung], faelle: Sequence[dict[str, Any]]) -> list[str]:
    """Recall@k je `art` (golden, web, szenario) neben der Gesamtzahl; leer, wenn das Set keine Art kennt."""
    art_von = {str(f["id"]): str(f["art"]) for f in faelle if f.get("art")}
    arten = [a for a in ARTEN if a in art_von.values()]
    if not arten or not messungen:
        return []
    zeilen = [
        "",
        "Recall@k je Art:",
        "",
        "| Weg | " + " | ".join(arten) + " | gesamt |",
        "|---|" + "---|" * (len(arten) + 1),
    ]
    for m in messungen:
        spalten = []
        for art in arten:
            idx = [i for i, e in enumerate(m.ergebnisse) if art_von.get(e.id) == art]
            spalten.append(f"{sum(m.getroffen(i) for i in idx)}/{len(idx)}")
        zeilen.append(f"| {m.name} | {' | '.join(spalten)} | {m.recall} |")
    return zeilen


def paartabelle(messungen: Sequence[Messung]) -> list[str]:
    vergleich = [vergleiche(a, b) for a, b in paare(messungen)]
    if not vergleich:
        return []
    return [
        "",
        "Gepaarte Vergleiche (B gegen A, je Fall Treffer in Top k): gewonnen = B trifft, A nicht.",
        "",
        "| B | gegen A | gewonnen : verloren | gleich | McNemar exakt p |",
        "|---|---|---|---|---|",
        *(f"| {v.b} | {v.a} | {v.gewonnen} : {v.verloren} | {v.gleich} | {v.p:.3f} |" for v in vergleich),
    ]


def rohtabelle(messungen: Sequence[Messung], quellen: dict[str, Any]) -> list[str]:
    if not messungen:
        return []
    kopf = " | ".join(f"Rang {m.name} | ms {m.name}" for m in messungen)
    zeilen = ["", f"| Fall | erwartete Quellen | {kopf} |", "|---|---|" + "---|---|" * len(messungen)]
    for i, fall_id in enumerate(e.id for e in messungen[0].ergebnisse):
        spalten = []
        for m in messungen:
            e = m.ergebnisse[i]
            spalten += [str(e.rang) if e.rang is not None else "–", f"{e.latenz_ms:.1f}"]
        zeilen.append(f"| {fall_id} | {_quelltext(quellen[fall_id])} | {' | '.join(spalten)} |")
    return zeilen


def _quelltext(quellen: Sequence[dict[str, Any]]) -> str:
    teile = []
    for q in quellen:
        if "datei" in q:
            teile.append(Path(str(q["datei"])).name)
        else:
            zeichen = "Art." if str(q["art"]).upper() == "ART" else "§"
            teile.append(f"{q['gesetz']} {zeichen} {q['nummer']}")
    return "; ".join(teile)


# --------------------------------------------------------------------------- modellfreie Prüffunktionen

_ZEICHEN = str.maketrans(
    {
        "„": '"',
        "“": '"',
        "”": '"',
        "«": '"',
        "»": '"',
        "‚": "'",
        "‘": "'",
        "’": "'",
        "‹": "'",
        "›": "'",
        "‐": "-",
        "‑": "-",
        "‒": "-",
        "–": "-",
        "—": "-",
        "−": "-",
        "­": "",  # weiches Trennzeichen
    }
)


def normiere(text: str) -> str:
    """NFKC, typografische Anführungszeichen und Bindestriche vereinheitlicht, Leerraum zusammengezogen."""
    text = unicodedata.normalize("NFKC", text).translate(_ZEICHEN)
    return re.sub(r"\s+", " ", text).strip()


def zitat_treu(zitat: str, abschnitt_text: str) -> bool:
    """Steht das Zitat wörtlich im Abschnitt? Groß-/Kleinschreibung zählt, Leerraum nicht. Kürzer als
    ZITAT_MIN_WOERTER Wörter und ZITAT_MIN_ZEICHEN Zeichen zählt nicht (Review D5a: „die“ bestand)."""
    kern = normiere(zitat).strip("\"' ")
    if len(kern.split()) < ZITAT_MIN_WOERTER and len(kern) < ZITAT_MIN_ZEICHEN:
        return False
    return kern in normiere(abschnitt_text)


PHRASEN_STUFEN = ("beleg", "grenze_uebergabe", "abstinenz", "hinweis", "uebergabe_ausdruecklich", "uebergabe")
# Eine Phrase zählt nicht, wenn direkt davor (höchstens ein Wort dazwischen, kein Satzzeichen) eine
# Verneinung steht: „kein Notruf“, „nicht an die Arbeiterkammer“.
_VERNEINT = re.compile(r"\b(?:nicht|kein|keine|keinen|keinem|keiner|not|no)\s+(?:\w+\s+)?$")


def _phrase(eintrag: Any) -> re.Pattern[str]:
    """Text (ganzes Wort bzw. ganze Wortfolge) oder {regex: ...}; beides auf normiertem, kleingeschriebenem
    Text. Wortgrenzen auch für Text-Phrasen: „rufen sie“ trifft nicht „berufen Sie“ (Review !25)."""
    if isinstance(eintrag, dict):
        return re.compile(str(eintrag["regex"]))
    return re.compile(rf"(?<!\w){re.escape(normiere(str(eintrag)).casefold())}(?!\w)")


@cache
def _phrasen(pfad: Path = VERHALTEN_DATEI) -> dict[str, tuple[re.Pattern[str], ...]]:
    daten = yaml.safe_load(pfad.read_text(encoding="utf-8"))
    return {art: tuple(_phrase(p) for p in daten.get(art) or []) for art in PHRASEN_STUFEN}


def _enthaelt(text: str, phrase: re.Pattern[str]) -> bool:
    return any(not _VERNEINT.search(text[: m.start()]) for m in phrase.finditer(text))


def klassifiziere_verhalten(antworttext: str, phrasen_datei: Path = VERHALTEN_DATEI) -> Verhalten:
    """Verhalten aus dem Antworttext über die Stufen in verhalten.yaml (erste passende entscheidet):
    Grenz-Übergabe (Notruf, Ärztin/Arzt) vor Abstinenz vor Disclaimer ohne Beleg vor ausdrücklicher
    Übergabe vor Verweis ohne Beleg vor Antwort. Belegt = mindestens ein Quellverweis (§, Art., Quelle:,
    Seite). Ein Handlungshinweis oder Disclaimer in einer belegten Antwort macht sie nicht zur Übergabe
    bzw. Abstinenz."""
    text = normiere(antworttext).casefold()
    phrasen = _phrasen(phrasen_datei)

    def trifft_stufe(stufe: str) -> bool:
        return any(_enthaelt(text, p) for p in phrasen[stufe])

    belegt = trifft_stufe("beleg")
    if trifft_stufe("grenze_uebergabe"):
        return "uebergabe"
    if trifft_stufe("abstinenz"):
        return "abstinenz"
    if not belegt and trifft_stufe("hinweis"):
        return "abstinenz"
    if trifft_stufe("uebergabe_ausdruecklich"):
        return "uebergabe"
    if not belegt and trifft_stufe("uebergabe"):
        return "uebergabe"
    return "antwort"


# Abkürzungen, deren Punkt kein Satzende ist.
_ABKUERZUNGEN = re.compile(
    r"\b(?:z\.\s?B|u\.\s?a|d\.\s?h|bzw|ca|usw|vgl|Abs|Nr|Z|lit|Art|S|idF|iVm|Dr|Mag|etc|e\.g|i\.e"
    r"|ggf|inkl|evtl|exkl|zzgl|max|mind|bzgl)\.",
    re.IGNORECASE,
)
# Datum („01.07.“, „1.7.2026“) und Ordnungszahl vor einem Wort („4. Tag“, „ab dem 3. Monat“).
_DATUM_PUNKT = re.compile(r"\b(\d{1,2})\.(\d{1,2})\.(\d{2,4})?")
_ORDNUNGSZAHL = re.compile(r"\b(\d{1,2})\.(?=\s+\w)")


def mittlere_satzlaenge(text: str) -> float:
    """Mittlere Wortzahl je Satz; Satzende an . ! ? (Abkürzungen, Datum, Ordnungszahl vor einem Wort und
    Zahlen wie 1.250 ausgenommen). Eine Zahl am Satzende vor einem neuen Satz („Stufe 4. Danach …“) zählt
    deshalb nicht als Satzende; das ist im Deutschen ohne Grammatik nicht von „4. Tag“ zu trennen."""
    ohne = _ABKUERZUNGEN.sub(lambda m: m.group(0).replace(".", ""), text)
    ohne = _DATUM_PUNKT.sub(lambda m: f"{m.group(1)}_{m.group(2)}_{m.group(3) or ''}", ohne)
    ohne = _ORDNUNGSZAHL.sub(r"\1", ohne)
    ohne = re.sub(r"(?<=\d)\.(?=\d)", "", ohne)
    saetze = [s for s in re.split(r"[.!?]+", ohne) if _WORT.search(s)]
    if not saetze:
        return 0.0
    return sum(len(_WORT.findall(s)) for s in saetze) / len(saetze)


_DE = frozenset(
    [
        "der",
        "die",
        "das",
        "und",
        "ist",
        "ich",
        "sie",
        "nicht",
        "ein",
        "eine",
        "mit",
        "von",
        "zu",
        "den",
        "auf",
        "für",
        "wie",
        "bei",
        "sich",
        "auch",
        "wird",
        "werden",
        "haben",
        "sind",
        "oder",
        "kann",
        "können",
        "bitte",
        "ihre",
        "ihr",
        "wenn",
        "dass",
        "nach",
        "aus",
        "noch",
    ]
)
# Ohne „an“, „in“, „will“: Die stehen auch in deutschen Sätzen („Ja, in Wien und in Graz.“).
_EN = frozenset(
    [
        "the",
        "and",
        "is",
        "are",
        "you",
        "your",
        "not",
        "a",
        "with",
        "of",
        "to",
        "on",
        "for",
        "how",
        "at",
        "it",
        "this",
        "that",
        "be",
        "have",
        "can",
        "please",
        "if",
        "or",
        "from",
        "would",
        "should",
        "what",
    ]
)


def sprache(text: str) -> Literal["de", "en"]:
    """Sprache über häufige Funktionswörter; Gleichstand zählt als Deutsch."""
    woerter = _WORT.findall(text.casefold())
    de = sum(w in _DE for w in woerter)
    en = sum(w in _EN for w in woerter)
    return "en" if en > de else "de"


# --------------------------------------------------------------------------- CLI


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="lotse eval", description=__doc__.splitlines()[0] if __doc__ else None)
    p.add_argument("--set", type=Path, default=STANDARD_SET, help="Pfad zum Lotse-Set (YAML)")
    p.add_argument("--pruefe-set", action="store_true", help="nur Schema und Belege prüfen")
    p.add_argument("--nur-suche", action="store_true", help="nur die Suche messen (ohne Modell)")
    p.add_argument(
        "--weg",
        default=None,
        help="Suchweg(e), Komma-getrennt: volltext, dicht, hybrid, auto (Standard auto)",
    )
    p.add_argument(
        "--erweiterung",
        default="aus",
        help="Erweiterung(en), Komma-getrennt: aus, thesaurus, llm, datei:<pfad> (JSON {frage: [begriffe]})",
    )
    p.add_argument("-k", type=int, default=5, help="Recall@k, mindestens 1")
    p.add_argument(
        "--kern",
        action="store_true",
        help="mit --nur-suche: Suche im Lotse-Kern gegen die nackte Suche messen",
    )
    p.add_argument("--ausgabe", type=Path, help="Markdown-Bericht in diese Datei schreiben")
    p.add_argument("--grep-grundlinie", action="store_true", help="naive Grundlinie über rohe XML")
    p.add_argument("--trotzdem", action="store_true", help=f"Test-Set auch nach {MAX_BLICKE} Blicken messen")
    p.add_argument("--nur-begriffe", type=Path, help="nur Begriffe je Frage erzeugen und als JSON speichern")
    return p


# --------------------------------------------------------------------------- Erweiterung und Blicke


class ErweiterungsFehler(ValueError):
    """--erweiterung ist ungültig oder die Begriff-Datei passt nicht zum Set."""


def _erweiterung(spec: str) -> tuple[str, Begriffe | None]:
    """(Name, Funktion Frage -> Begriffe) zu aus | thesaurus | llm | datei:<pfad>; aus ergibt None."""
    if spec == "aus":
        return "aus", None
    if spec in ("thesaurus", "llm"):
        from uc1.erweiterung import erweitere

        def erzeugt(frage: str) -> list[str]:
            e = erweitere(frage, modus=spec)  # type: ignore[arg-type]
            if e.quelle != spec:
                print(
                    f"lotse eval: Erweiterung {spec} fiel auf {e.quelle} zurück: {frage[:60]}",
                    file=sys.stderr,
                )
            return list(e.begriffe)

        return spec, erzeugt
    if spec.startswith("datei:"):
        pfad = Path(spec.removeprefix("datei:"))
        try:
            daten = json.loads(pfad.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as fehler:
            raise ErweiterungsFehler(f"Begriff-Datei nicht lesbar: {fehler}") from fehler
        if not isinstance(daten, dict) or not all(isinstance(v, list) for v in daten.values()):
            raise ErweiterungsFehler(f"{pfad}: erwartet ein JSON-Objekt {{frage: [begriffe]}}")
        tabelle = {normiere(str(k)): [str(b) for b in v] for k, v in daten.items()}

        def aus_datei(frage: str) -> list[str]:
            try:
                return tabelle[normiere(frage)]
            except KeyError:
                raise ErweiterungsFehler(f"{pfad}: keine Begriffe für die Frage {frage[:60]!r}") from None

        return f"datei:{pfad.stem}", aus_datei
    raise ErweiterungsFehler(f"unbekannte Erweiterung {spec!r} (aus, thesaurus, llm, datei:<pfad>)")


def ist_testset(pfad: Path) -> bool:
    return pfad.resolve() == STANDARD_SET.resolve()


def lade_blicke(pfad: Path | None = None) -> list[dict[str, Any]]:
    pfad = pfad or BLICKE_DATEI
    if not pfad.is_file():
        return []
    daten = json.loads(pfad.read_text(encoding="utf-8"))
    blicke: list[dict[str, Any]] = daten.get("blicke", [])
    return blicke


def speichere_blick(eintrag: dict[str, Any], pfad: Path | None = None) -> int:
    """Hängt einen Blick an und liefert seine Nummer n."""
    pfad = pfad or BLICKE_DATEI
    blicke = lade_blicke(pfad)
    eintrag = {"n": len(blicke) + 1, **eintrag}
    blicke.append(eintrag)
    daten = {
        "beschreibung": (
            "Blicke auf das Test-Set uc1/eval/lotse-set.yaml (Review D6d): höchstens "
            f"{MAX_BLICKE} Läufe bis zur Abgabe. Abgestimmt wird nur auf dem Dev-Set."
        ),
        "grenze": MAX_BLICKE,
        "blicke": blicke,
    }
    pfad.write_text(json.dumps(daten, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return int(eintrag["n"])


def _lade_suche() -> SucheFn | None:
    try:
        modul = importlib.import_module("uc1.suche")
    except ModuleNotFoundError as fehler:
        if fehler.name != "uc1.suche":
            raise
        return None
    suche_fn: SucheFn = modul.suche
    return suche_fn


def cli(argv: Sequence[str], *, suche: SucheFn | None = None, kern: KernFn | None = None) -> int:
    """Einstieg für `lotse eval`. `suche` ersetzt in Tests uc1.suche.suche, `kern` uc1.kern.kern_suche."""
    args = _parser().parse_args(list(argv))
    try:
        faelle = lade_set(args.set)
    except (OSError, yaml.YAMLError, SetFehler) as fehler:
        print(f"lotse eval: Set nicht lesbar: {fehler}", file=sys.stderr)
        return 2
    if args.k < 1:
        print(f"lotse eval: -k muss mindestens 1 sein: {args.k}", file=sys.stderr)
        return 2

    if args.pruefe_set:
        return _cli_pruefe_set(faelle)
    if args.nur_begriffe:
        return _cli_nur_begriffe(args, faelle)
    befehl = " ".join(["lotse eval", *map(shlex.quote, argv)])
    if args.kern and not args.nur_suche:
        print("lotse eval: --kern gilt nur mit --nur-suche", file=sys.stderr)
        return 2
    if args.nur_suche:
        return _cli_nur_suche(args, faelle, suche, befehl, kern)
    print(
        "lotse eval: die Messung mit Modell braucht den Lotse-Kern (#31), der noch nicht gebaut ist. "
        "Ohne Modell: --pruefe-set oder --nur-suche.",
        file=sys.stderr,
    )
    return 2


def _cli_pruefe_set(faelle: Sequence[dict[str, Any]]) -> int:
    try:
        daten_dir: Path | None = config.daten_dir()
    except config.KonfigFehler as konfig_fehler:
        print(f"lotse eval: {konfig_fehler}; belegt_durch wird nicht geprüft", file=sys.stderr)
        daten_dir = None
    fehler = pruefe_set(faelle, daten_dir)
    anzahl = Counter(str(f.get("art")) for f in faelle)
    belege = sum(len(f.get("belegt_durch") or []) for f in faelle)
    print(f"Lotse-Set: {len(faelle)} Einträge; " + ", ".join(f"{a} {anzahl[a]}" for a in ARTEN))
    print(f"Fälle mit Korpusquelle: {len(faelle_mit_korpusquelle(faelle))}; belegt_durch-Dateien: {belege}")
    for f in fehler:
        print(f"FEHLER {f}", file=sys.stderr)
    if fehler or daten_dir is None:
        return 1
    print("Set gültig, alle Belege im Korpus vorhanden.")
    return 0


def _cli_nur_begriffe(args: argparse.Namespace, faelle: Sequence[dict[str, Any]]) -> int:
    try:
        name, fn = _erweiterung(args.erweiterung)
    except ErweiterungsFehler as fehler:
        print(f"lotse eval: {fehler}", file=sys.stderr)
        return 2
    if fn is None:
        print("lotse eval: --nur-begriffe braucht --erweiterung thesaurus oder llm", file=sys.stderr)
        return 2
    tabelle = {anfrage(f): fn(anfrage(f)) for f in faelle_mit_korpusquelle(faelle)}
    args.nur_begriffe.write_text(json.dumps(tabelle, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"{len(tabelle)} Fragen, Erweiterung {name}: {args.nur_begriffe}")
    return 0


def _blick_kopf(args: argparse.Namespace) -> tuple[bool, list[str]] | None:
    """(zählt als Blick, Kopfzeilen); None, wenn der Blick über der Grenze läge."""
    testset = ist_testset(args.set) and args.ausgabe is not None
    if not testset:
        return False, []
    n = len(lade_blicke()) + 1
    if n > MAX_BLICKE and not args.trotzdem:
        print(
            f"lotse eval: Blick {n} von {MAX_BLICKE} auf das Test-Set wäre über der Grenze "
            f"({BLICKE_DATEI.name}). Abgestimmt wird auf dem Dev-Set (--set {DEV_SET.name}); "
            "bewusst darüber: --trotzdem.",
            file=sys.stderr,
        )
        return None
    return True, [f"Blick {n} von {MAX_BLICKE} auf das Test-Set ({BLICKE_DATEI.name})"]


def _verbindung(suche: SucheFn | None) -> Any:
    """Eine gemeinsame DB-Verbindung für alle Aufrufe der echten Suche, damit die Latenz keinen
    Verbindungsaufbau je Anfrage enthält (Review !25). Mit eingespeister Suche (Tests): None."""
    if suche is not None:
        return None
    from uc1.db import verbinde

    return verbinde()


def _abschluss(
    args: argparse.Namespace, text: str, testset: bool, befehl: str, messungen: Sequence[Messung]
) -> int:
    print(text)
    if testset:
        ergebnis = ", ".join(f"{m.name} {m.recall}" for m in messungen)
        zeit = datetime.now().astimezone().isoformat(timespec="minutes")
        speichere_blick({"zeitpunkt": zeit, "befehl": befehl, "ergebnis": ergebnis})
    if args.ausgabe:
        args.ausgabe.write_text(text, encoding="utf-8")
        print(f"Bericht geschrieben: {args.ausgabe}")
    return 0


def _cli_nur_suche(
    args: argparse.Namespace,
    faelle: Sequence[dict[str, Any]],
    suche: SucheFn | None,
    befehl: str,
    kern: KernFn | None = None,
) -> int:
    zaehlend = faelle_mit_korpusquelle(faelle)
    wege = [w.strip() for w in str(args.weg or ("volltext" if args.kern else "auto")).split(",") if w.strip()]
    if not wege or any(w not in WEGE for w in wege):
        print(f"lotse eval: --weg muss aus {', '.join(WEGE)} sein: {args.weg}", file=sys.stderr)
        return 2
    try:
        erweiterungen = [_erweiterung(e.strip()) for e in str(args.erweiterung).split(",") if e.strip()]
    except ErweiterungsFehler as fehler:
        print(f"lotse eval: {fehler}", file=sys.stderr)
        return 2
    blick = _blick_kopf(args)
    if blick is None:
        return 2
    testset, kopf = blick
    if args.kern:
        if wege != ["volltext"]:
            print("lotse eval: --kern sucht im Volltext; --weg nur volltext", file=sys.stderr)
            return 2
        if any(name not in ("aus", "thesaurus", "llm") for name, _ in erweiterungen):
            print("lotse eval: --kern kennt nur die Erweiterungen aus, thesaurus, llm", file=sys.stderr)
            return 2
        return _cli_kern(args, zaehlend, suche, kern, erweiterungen, befehl, kopf, testset)
    messungen: list[Messung] = []
    suche_fn = suche or _lade_suche()
    if suche_fn is None:
        print(
            "lotse eval: uc1.suche ist noch nicht gebaut (#29); die Suche wird nicht gemessen.",
            file=sys.stderr,
        )
        if not args.grep_grundlinie:
            return 2
    else:
        fn = suche_fn
        conn = _verbindung(suche)
        try:
            for weg in wege:
                aufwaermen(zaehlend, lambda q, k, w=weg: fn(q, k=k, weg=w, conn=conn))  # type: ignore[misc]
                for erw_name, erw_fn in erweiterungen:
                    name = (
                        f"suche:{weg}"
                        if len(erweiterungen) == 1 and erw_name == "aus"
                        else f"{weg}+{erw_name}"
                    )
                    messungen.append(
                        messe(
                            name,
                            zaehlend,
                            lambda q, k, w=weg: fn(q, k=k, weg=w, conn=conn),  # type: ignore[misc]
                            args.k,
                            begriffe=erw_fn,
                            weg=weg,
                            erweiterung=erw_name,
                        )
                    )
        except ErweiterungsFehler as fehler:
            print(f"lotse eval: {fehler}", file=sys.stderr)
            return 2
        finally:
            if conn is not None:
                conn.close()
    if args.grep_grundlinie:
        try:
            daten_dir = config.daten_dir()
        except config.KonfigFehler as fehler:
            print(f"lotse eval: {fehler}", file=sys.stderr)
            return 2
        messungen.append(messe("grep", zaehlend, grep_suche(lade_rohkorpus(daten_dir)), args.k))
    titel = "Lotse-Set: Suche (Recall@k)" if ist_testset(args.set) else f"{args.set.name}: Suche (Recall@k)"
    return _abschluss(args, bericht(messungen, zaehlend, befehl, kopf, titel), testset, befehl, messungen)


# --------------------------------------------------------------------------- Suche im Kern (--kern)


class KernErgebnis(Protocol):
    """Was uc1.kern.kern_suche liefert (hier nur als Vertrag, damit eval.py uc1.kern nicht importiert)."""

    @property
    def treffer(self) -> list[Treffer]: ...
    @property
    def angebote(self) -> list[Treffer]: ...
    @property
    def leistungen(self) -> list[str]: ...
    @property
    def angaben(self) -> dict[str, str]: ...
    @property
    def begriffe(self) -> list[str]: ...
    @property
    def grenze(self) -> str | None: ...
    @property
    def llm_aufrufe(self) -> int: ...
    @property
    def hinweise(self) -> tuple[str, ...]: ...
    @property
    def dauer_ms(self) -> dict[str, float]: ...


KernFn = Callable[..., KernErgebnis]


def _lade_kern() -> KernFn:
    # lazy über importlib: uc1.kern importiert uc1.eval, und die Messung läuft auch auf einem Stand ohne
    # Kern (Korpus-MR #29); mypy prüft den Import deshalb nicht statisch.
    kern = importlib.import_module("uc1.kern")
    fn: KernFn = kern.kern_suche
    return fn


def sozdok_quellen(fall: dict[str, Any]) -> list[dict[str, Any]]:
    return [q for q in fall["erwartete_quellen"] if "datei" not in q]


def pdf_quellen(fall: dict[str, Any], *, mit_seite: bool = True) -> list[dict[str, Any]]:
    quellen = [q for q in fall["erwartete_quellen"] if "datei" in q]
    return quellen if mit_seite else [{"datei": q["datei"]} for q in quellen]


def zaehlt_sozdok(fall: dict[str, Any]) -> bool:
    return bool(sozdok_quellen(fall) or fall.get("ueberschrift_regex"))


@dataclass(frozen=True)
class KernFall:
    """Ein Fall in beiden Varianten: nackte Suche (ohne) und Suche im Kern (mit)."""

    id: str
    ohne_sozdok: int | None
    mit_sozdok: int | None
    ohne_pdf: int | None
    mit_pdf: int | None
    ohne_pdf_datei: int | None
    mit_pdf_datei: int | None
    ms_ohne: float
    ms_erweiterung_ohne: float
    ms_analyse: float
    ms_kern: float
    llm_ohne: int
    llm_mit: int
    leistungen: tuple[str, ...] = ()
    angaben: str = ""
    begriffe_ohne: tuple[str, ...] = ()
    begriffe_mit: tuple[str, ...] = ()
    grenze: str = ""
    hinweise: str = ""
    sozdok_n: int = 0
    angebote_n: int = 0


def messe_kern_fall(
    fall: dict[str, Any],
    suche_fn: Callable[[str, int], list[Treffer]],
    kern_fn: Callable[[str], KernErgebnis],
    begriffe: Begriffe | None,
    llm_ohne: bool,
) -> KernFall:
    """Ein Fall: nackte Suche (MRR_TIEFE Treffer, Erweiterung vor der Zeitmessung) und Suche im Kern.
    SozDok-Rang im Kern über dessen SozDok-Treffer, PDF-Rang über dessen Angebote (Katalog, Formular)."""
    frage = anfrage(fall)
    start = time.perf_counter()
    zusatz = begriffe(frage) if begriffe else []
    ms_erw = (time.perf_counter() - start) * 1000
    erweitert = frage
    if zusatz:
        from uc1.erweiterung import anfrage_aus

        erweitert = anfrage_aus(frage, zusatz)
    start = time.perf_counter()
    ohne = suche_fn(erweitert, MRR_TIEFE)[:MRR_TIEFE]
    ms_ohne = (time.perf_counter() - start) * 1000
    mit = kern_fn(frage)
    regex = fall.get("ueberschrift_regex")
    mit_sozdok = [t for t in mit.treffer if t.quelle == "sozdok"]
    pdf, pdf_datei = pdf_quellen(fall), pdf_quellen(fall, mit_seite=False)
    return KernFall(
        id=str(fall["id"]),
        ohne_sozdok=rang(ohne, sozdok_quellen(fall), regex),
        mit_sozdok=rang(mit_sozdok, sozdok_quellen(fall), regex),
        ohne_pdf=rang(ohne, pdf) if pdf else None,
        mit_pdf=rang(mit.angebote, pdf) if pdf else None,
        ohne_pdf_datei=rang(ohne, pdf_datei) if pdf else None,
        mit_pdf_datei=rang(mit.angebote, pdf_datei) if pdf else None,
        ms_ohne=ms_ohne,
        ms_erweiterung_ohne=ms_erw,
        ms_analyse=float(mit.dauer_ms.get("analyse", 0.0)),
        ms_kern=float(mit.dauer_ms.get("suche", 0.0)),
        llm_ohne=int(llm_ohne and begriffe is not None),
        llm_mit=mit.llm_aufrufe,
        leistungen=tuple(mit.leistungen),
        angaben=", ".join(f"{k}={v}" for k, v in sorted(mit.angaben.items())),
        begriffe_ohne=tuple(zusatz),
        begriffe_mit=tuple(mit.begriffe),
        grenze=mit.grenze or "",
        hinweise="; ".join(mit.hinweise),
        sozdok_n=len(mit_sozdok),
        angebote_n=len(mit.angebote),
    )


def kern_messungen(
    erweiterung: str, faelle: Sequence[dict[str, Any]], ergebnisse: Sequence[KernFall], k: int
) -> dict[str, list[Messung]]:
    """Messungen je Teil: sozdok (Fälle mit Norm oder Überschrift-Regex), pdf (Fälle mit PDF-Quelle,
    seitengenau) und pdf-datei (gleiche Fälle, nur Datei)."""
    nach_id = {e.id: e for e in ergebnisse}
    teile: dict[str, list[Messung]] = {}
    for teil, auswahl, ohne_attr, mit_attr in (
        ("sozdok", [f for f in faelle if zaehlt_sozdok(f)], "ohne_sozdok", "mit_sozdok"),
        ("pdf", [f for f in faelle if pdf_quellen(f)], "ohne_pdf", "mit_pdf"),
        ("pdf-datei", [f for f in faelle if pdf_quellen(f)], "ohne_pdf_datei", "mit_pdf_datei"),
    ):
        es = [nach_id[str(f["id"])] for f in auswahl]
        zusatz = "" if teil == "sozdok" else f"-{teil}"
        ohne = tuple(FallErgebnis(e.id, getattr(e, ohne_attr), e.ms_ohne, e.begriffe_ohne) for e in es)
        mit = tuple(FallErgebnis(e.id, getattr(e, mit_attr), e.ms_kern, e.begriffe_mit) for e in es)
        teile[teil] = [
            Messung(f"volltext{zusatz}+{erweiterung}", k, ohne, "volltext", erweiterung),
            Messung(f"kern{zusatz}+{erweiterung}", k, mit, "kern", erweiterung),
        ]
    return teile


def _p50_p95(werte: Sequence[float]) -> str:
    return f"{perzentil(werte, 0.5):.0f} | {perzentil(werte, 0.95):.0f}"


def _r(wert: int | None) -> str:
    return "–" if wert is None else str(wert)


def kern_bericht(
    laeufe: dict[str, list[KernFall]],
    faelle: Sequence[dict[str, Any]],
    k: int,
    befehl: str,
    kopf: Sequence[str] = (),
    titel: str = "Suche im Kern",
) -> str:
    """Bericht für --kern: Tabellen je Teil (SozDok, PDF), gepaarte Vergleiche, Kosten, Rohdaten je Fall."""
    zeitpunkt = datetime.now().astimezone().isoformat(timespec="seconds")
    quellen = {str(f["id"]): f["erwartete_quellen"] for f in faelle}
    alle: dict[str, list[Messung]] = {"sozdok": [], "pdf": [], "pdf-datei": []}
    for erweiterung, ergebnisse in laeufe.items():
        for teil, ms in kern_messungen(erweiterung, faelle, ergebnisse, k).items():
            alle[teil] += ms
    n_sozdok = sum(zaehlt_sozdok(f) for f in faelle)
    n_pdf = sum(bool(pdf_quellen(f)) for f in faelle)
    zeilen = [
        f"# {titel}",
        "",
        f"- Zeitpunkt: {zeitpunkt}",
        f"- Befehl: `{befehl}`",
        *(f"- {z}" for z in kopf),
        f"- Fälle mit Korpusquelle: {len(faelle)}; davon SozDok-zählend {n_sozdok}, mit PDF-Quelle {n_pdf}.",
        "- volltext+E: `uc1.suche.suche(weg=volltext)` mit Erweiterung E (uc1.erweiterung), ohne Filter.",
        "- kern+E: `uc1.kern.kern_suche(erweiterung=E)`: Vorprüfung, Analyse (Regeln, bei llm ein "
        "Analyse-Aufruf), SozDok mit Gesetzesfilter aus Leistung bzw. Status, PDF-Suche in Katalog "
        "und Formular.",
        "- SozDok-Rang: im Kern über dessen SozDok-Treffer (Leistungssuchen vor allgemeiner Suche), "
        "nackt über alle Treffer. PDF-Rang: im Kern über die Angebote, nackt über alle Treffer.",
        f"- Intervall: Wilson 95 %. MRR über die ersten {MRR_TIEFE} Treffer. Latenz: nur Suche (ms); "
        "Analyse bzw. Erweiterung stehen unter Kosten.",
    ]
    for teil, ueberschrift in (
        ("sozdok", "SozDok (Recall@k über Rechtstexte)"),
        ("pdf", "PDF seitengenau (Datei und, wenn genannt, Seite)"),
        ("pdf-datei", "PDF nur Datei"),
    ):
        ms = alle[teil]
        zeilen += ["", f"## {ueberschrift}", ""]
        if not ms or not ms[0].ergebnisse:
            zeilen.append("Keine Fälle mit dieser Quellart im Set.")
            continue
        zeilen += [*messtabelle(ms), *paartabelle(ms)]
    zeilen += [
        "",
        "## Kosten je Variante",
        "",
        "| Variante | LLM-Aufrufe | Analyse bzw. Erweiterung p50 (ms) | p95 (ms) | Suche p50 (ms) |"
        " p95 (ms) |",
        "|---|---|---|---|---|---|",
    ]
    for erweiterung, es in laeufe.items():
        zeilen.append(
            f"| volltext+{erweiterung} | {sum(e.llm_ohne for e in es)} |"
            f" {_p50_p95([e.ms_erweiterung_ohne for e in es])} |"
            f" {_p50_p95([e.ms_ohne for e in es])} |"
        )
        zeilen.append(
            f"| kern+{erweiterung} | {sum(e.llm_mit for e in es)} |"
            f" {_p50_p95([e.ms_analyse for e in es])} |"
            f" {_p50_p95([e.ms_kern for e in es])} |"
        )
    for erweiterung, es in laeufe.items():
        zeilen += [
            "",
            f"## Rohdaten je Fall, Erweiterung {erweiterung}",
            "",
            "| Fall | erwartete Quellen | SozDok ohne | SozDok Kern | PDF ohne | PDF Kern | PDF-Datei ohne | "
            "PDF-Datei Kern | Leistungen | Angaben | Grenze | SozDok/Angebote im Kern | Hinweis |",
            "|---|---|---|---|---|---|---|---|---|---|---|---|---|",
        ]
        for e in es:
            zeilen.append(
                f"| {e.id} | {_quelltext(quellen[e.id])} | {_r(e.ohne_sozdok)} | {_r(e.mit_sozdok)} |"
                f" {_r(e.ohne_pdf)} | {_r(e.mit_pdf)} | {_r(e.ohne_pdf_datei)} | {_r(e.mit_pdf_datei)} |"
                f" {', '.join(e.leistungen) or '–'} | {e.angaben or '–'} | {e.grenze or '–'} |"
                f" {e.sozdok_n}/{e.angebote_n} | {e.hinweise or '–'} |"
            )
        if erweiterung != "aus":
            zeilen += ["", f"Begriffe ({erweiterung}), nackt | Kern:", ""]
            zeilen += [
                f"- {e.id}: {', '.join(e.begriffe_ohne) or '–'} | {', '.join(e.begriffe_mit) or '–'}"
                for e in es
            ]
    return "\n".join(zeilen) + "\n"


def _cli_kern(
    args: argparse.Namespace,
    zaehlend: Sequence[dict[str, Any]],
    suche: SucheFn | None,
    kern: KernFn | None,
    erweiterungen: Sequence[tuple[str, Begriffe | None]],
    befehl: str,
    kopf: list[str],
    testset: bool,
) -> int:
    suche_fn = suche or _lade_suche()
    if suche_fn is None:
        print("lotse eval: uc1.suche fehlt; --kern braucht die Suche", file=sys.stderr)
        return 2
    kern_fn = kern or _lade_kern()
    conn = _verbindung(suche)
    fn = suche_fn

    def nackt(q: str, k: int) -> list[Treffer]:
        return fn(q, k=k, weg="volltext", conn=conn)

    laeufe: dict[str, list[KernFall]] = {}
    try:
        # Aufwärmrunde ohne Erweiterung und ohne Modell, nicht gezählt
        for fall in zaehlend:
            nackt(anfrage(fall), MRR_TIEFE)
            kern_fn(anfrage(fall), erweiterung="aus", conn=conn, suche_fn=fn)
        for name, erw_fn in erweiterungen:

            def im_kern(q: str, e: str = name) -> KernErgebnis:
                return kern_fn(q, erweiterung=e, conn=conn, suche_fn=fn)

            laeufe[name] = [messe_kern_fall(f, nackt, im_kern, erw_fn, name == "llm") for f in zaehlend]
    finally:
        if conn is not None:
            conn.close()
    titel = f"{'Lotse-Set' if ist_testset(args.set) else args.set.name}: Suche im Kern (Recall@{args.k})"
    text = kern_bericht(laeufe, zaehlend, args.k, befehl, kopf, titel)
    messungen = [
        m for name, es in laeufe.items() for m in kern_messungen(name, zaehlend, es, args.k)["sozdok"]
    ]
    return _abschluss(args, text, testset, befehl, messungen)
