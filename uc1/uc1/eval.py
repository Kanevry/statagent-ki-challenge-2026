"""`lotse eval`: Lotse-Set prüfen und messen, ohne Sprachmodell (Issue #30).

Befehle:
  lotse eval --pruefe-set [--set PFAD]
      Schema, eindeutige IDs, Anzahl je Art und Existenz jeder `belegt_durch`-Datei. Ohne DB.
  lotse eval --nur-suche [--weg ...] [-k 5] [--set PFAD] [--ausgabe DATEI.md] [--grep-grundlinie]
      Recall@k, Rang und Latenz der Suche (uc1.suche) je Fall; optional neben einer naiven
      lexikalischen Grundlinie über die rohen XML-Dateien.
  lotse eval
      Messung mit Modell; braucht den Lotse-Kern (#31) und endet bis dahin mit Exit 2.

Die Prüffunktionen (`zitat_treu`, `klassifiziere_verhalten`, `mittlere_satzlaenge`, `sprache`)
sind rein und entscheiden ohne Modell.
"""

from __future__ import annotations

import argparse
import importlib
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
from typing import Any, Literal

import yaml

from uc1 import config
from uc1.typen import SucheFn, Treffer

Verhalten = Literal["antwort", "abstinenz", "uebergabe"]

EVAL_DIR = Path(__file__).resolve().parent.parent / "eval"
STANDARD_SET = EVAL_DIR / "lotse-set.yaml"
VERHALTEN_DATEI = EVAL_DIR / "verhalten.yaml"

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
        return [] if isinstance(quelle["datei"], str) else [f"{fall_id}: 'datei' ist kein Text"]
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
    """Gleiches Gesetz, gleiche Art, gleiche Nummer (jede Fassung zählt); für PDFs gleiche Datei."""
    if "datei" in quelle:
        return _norm(Path(treffer.datei).name) == _norm(Path(str(quelle["datei"])).name)
    return (
        _norm(treffer.gesetz) == _norm(quelle["gesetz"])
        and _norm(treffer.art) == _norm(quelle["art"])
        and _norm(treffer.nummer) == _norm(quelle["nummer"])
    )


def rang(treffer: Sequence[Treffer], quellen: Sequence[dict[str, Any]]) -> int | None:
    """1-basierter Rang des ersten Treffers, der eine erwartete Quelle ist; None ohne Treffer."""
    for i, t in enumerate(treffer, 1):
        if any(trifft(t, q) for q in quellen):
            return i
    return None


@dataclass(frozen=True)
class FallErgebnis:
    id: str
    rang: int | None
    latenz_ms: float


@dataclass(frozen=True)
class Messung:
    name: str
    k: int
    ergebnisse: tuple[FallErgebnis, ...]

    @property
    def treffer_anzahl(self) -> int:
        return sum(1 for e in self.ergebnisse if e.rang is not None and e.rang <= self.k)

    @property
    def recall(self) -> str:
        return f"{self.treffer_anzahl}/{len(self.ergebnisse)}"

    def latenz(self, quantil: float) -> float:
        return perzentil([e.latenz_ms for e in self.ergebnisse], quantil)


def perzentil(werte: Sequence[float], quantil: float) -> float:
    """Nearest-rank-Perzentil; bei kleinem n ehrlicher als Interpolation."""
    if not werte:
        return 0.0
    geordnet = sorted(werte)
    index = max(0, math.ceil(quantil * len(geordnet)) - 1)
    return geordnet[index]


def faelle_mit_korpusquelle(faelle: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    return [f for f in faelle if f["erwartete_quellen"]]


def anfrage(fall: dict[str, Any]) -> str:
    vorspann = str(fall.get("vorspann") or "").strip()
    return f"{vorspann} {fall['frage']}".strip()


def messe(
    name: str,
    faelle: Sequence[dict[str, Any]],
    suche_fn: Callable[[str, int], list[Treffer]],
    k: int,
) -> Messung:
    ergebnisse = []
    for fall in faelle:
        start = time.perf_counter()
        treffer = suche_fn(anfrage(fall), k)
        dauer = (time.perf_counter() - start) * 1000
        ergebnisse.append(FallErgebnis(str(fall["id"]), rang(treffer[:k], fall["erwartete_quellen"]), dauer))
    return Messung(name, k, tuple(ergebnisse))


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
        weg="grep",
    )


# --------------------------------------------------------------------------- Bericht


def bericht(messungen: Sequence[Messung], faelle: Sequence[dict[str, Any]], befehl: str) -> str:
    zeitpunkt = datetime.now().astimezone().isoformat(timespec="seconds")
    quellen = {str(f["id"]): f["erwartete_quellen"] for f in faelle}
    zeilen = [
        "# Lotse-Set: Suche (Recall@k)",
        "",
        f"- Zeitpunkt: {zeitpunkt}",
        f"- Befehl: `{befehl}`",
        f"- Zählende Fälle (mit Korpusquelle, n={len(faelle)}): {', '.join(str(f['id']) for f in faelle)}",
        "",
        "| Weg | Recall@k | k | Latenz p50 (ms) | Latenz p95 (ms) |",
        "|---|---|---|---|---|",
    ]
    zeilen += [
        f"| {m.name} | {m.recall} | {m.k} | {m.latenz(0.5):.1f} | {m.latenz(0.95):.1f} |" for m in messungen
    ]
    kopf = " | ".join(f"Rang {m.name} | ms {m.name}" for m in messungen)
    zeilen += ["", f"| Fall | erwartete Quellen | {kopf} |", "|---|---|" + "---|---|" * len(messungen)]
    for i, fall_id in enumerate(e.id for e in messungen[0].ergebnisse):
        spalten = []
        for m in messungen:
            e = m.ergebnisse[i]
            spalten += [str(e.rang) if e.rang is not None else "–", f"{e.latenz_ms:.1f}"]
        zeilen.append(f"| {fall_id} | {_quelltext(quellen[fall_id])} | {' | '.join(spalten)} |")
    return "\n".join(zeilen) + "\n"


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
    """Steht das Zitat wörtlich im Abschnitt? Groß-/Kleinschreibung zählt, Leerraum nicht."""
    kern = normiere(zitat).strip("\"' ")
    return bool(kern) and kern in normiere(abschnitt_text)


@cache
def _phrasen(pfad: Path = VERHALTEN_DATEI) -> dict[str, tuple[str, ...]]:
    daten = yaml.safe_load(pfad.read_text(encoding="utf-8"))
    return {
        art: tuple(normiere(p).casefold() for p in daten.get(art, [])) for art in ("abstinenz", "uebergabe")
    }


def _enthaelt(text: str, phrase: str) -> bool:
    if phrase.isdigit():  # Rufnummern wie 144 nicht in 1440 oder Beträgen finden
        return re.search(rf"(?<!\d){phrase}(?!\d)", text) is not None
    return phrase in text


def klassifiziere_verhalten(antworttext: str, phrasen_datei: Path = VERHALTEN_DATEI) -> Verhalten:
    """Verhalten aus dem Antworttext über Phrasenlisten: abstinenz vor uebergabe vor antwort."""
    text = normiere(antworttext).casefold()
    phrasen = _phrasen(phrasen_datei)
    if any(_enthaelt(text, p) for p in phrasen["abstinenz"]):
        return "abstinenz"
    if any(_enthaelt(text, p) for p in phrasen["uebergabe"]):
        return "uebergabe"
    return "antwort"


# Abkürzungen, deren Punkt kein Satzende ist.
_ABKUERZUNGEN = re.compile(
    r"\b(?:z\.\s?B|u\.\s?a|d\.\s?h|bzw|ca|usw|vgl|Abs|Nr|Z|lit|Art|S|idF|iVm|Dr|Mag|etc|e\.g|i\.e)\.",
    re.IGNORECASE,
)


def mittlere_satzlaenge(text: str) -> float:
    """Mittlere Wortzahl je Satz; Satzende an . ! ? (Abkürzungen und Zahlen wie 1.250 ausgenommen)."""
    ohne = _ABKUERZUNGEN.sub(lambda m: m.group(0).replace(".", ""), text)
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
        "an",
        "with",
        "of",
        "to",
        "in",
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
        "will",
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
    p.add_argument("--weg", choices=("volltext", "dicht", "hybrid", "auto"), default="auto")
    p.add_argument("-k", type=int, default=5)
    p.add_argument("--ausgabe", type=Path, help="Markdown-Bericht in diese Datei schreiben")
    p.add_argument("--grep-grundlinie", action="store_true", help="naive Grundlinie über rohe XML")
    return p


def _lade_suche() -> SucheFn | None:
    try:
        modul = importlib.import_module("uc1.suche")
    except ModuleNotFoundError as fehler:
        if fehler.name != "uc1.suche":
            raise
        return None
    suche_fn: SucheFn = modul.suche
    return suche_fn


def cli(argv: Sequence[str], *, suche: SucheFn | None = None) -> int:
    """Einstieg für `lotse eval`. `suche` ersetzt in Tests uc1.suche.suche."""
    args = _parser().parse_args(list(argv))
    try:
        faelle = lade_set(args.set)
    except (OSError, yaml.YAMLError, SetFehler) as fehler:
        print(f"lotse eval: Set nicht lesbar: {fehler}", file=sys.stderr)
        return 2

    if args.pruefe_set:
        return _cli_pruefe_set(faelle)
    if args.nur_suche:
        return _cli_nur_suche(args, faelle, suche, " ".join(["lotse eval", *map(shlex.quote, argv)]))
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


def _cli_nur_suche(
    args: argparse.Namespace, faelle: Sequence[dict[str, Any]], suche: SucheFn | None, befehl: str
) -> int:
    zaehlend = faelle_mit_korpusquelle(faelle)
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
        messungen.append(messe(f"suche:{args.weg}", zaehlend, lambda q, k: fn(q, k=k, weg=args.weg), args.k))
    if args.grep_grundlinie:
        try:
            daten_dir = config.daten_dir()
        except config.KonfigFehler as fehler:
            print(f"lotse eval: {fehler}", file=sys.stderr)
            return 2
        messungen.append(messe("grep", zaehlend, grep_suche(lade_rohkorpus(daten_dir)), args.k))
    text = bericht(messungen, zaehlend, befehl)
    print(text)
    if args.ausgabe:
        args.ausgabe.write_text(text, encoding="utf-8")
        print(f"Bericht geschrieben: {args.ausgabe}")
    return 0
