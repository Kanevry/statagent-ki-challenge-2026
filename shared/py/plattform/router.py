"""Router UC4 (#97): reicht eine Frage durch die Kette uc3 → uc2 → uc1.

Jeder Schritt ruft den Adapter des UC mit der Frage und den bisherigen Antworten als Kontext. Adapter kommen
aus der Registry (``registriere``) oder der Entry-Point-Gruppe ``kic.uc_antwort``, nie aus einem harten Import
der UC-Pakete. Fehlt ein Adapter oder wirft er, läuft die Kette weiter und ``fehlend`` nennt den UC.

Je Schritt genau eine ``Routerschritt``-Zeile in ``router.jsonl`` (neben ``modellaufrufe.jsonl``, das nur
Modellaufrufe trägt): UC, Stufe ab 1, Hash der Frage, Dauer, Modell, Anzahl Belege und Zahlen, protokoll_id;
nie Frage- oder Antworttext, bei einem Fehler nur dessen Grund. Nicht aus ``plattform/__init__.py`` importiert
(R2).

``frage --strom`` druckt statt eines Ergebnisses je Ereignis eine JSON-Zeile, sofort beim Eintreten (die
Seite /uc4 zeigt die Stationen nacheinander): ``start`` (kette), ``station`` (läuft), ``antwort`` (mit
``kern``, dem ersten Satz, höchstens 140 Zeichen) oder ``fehlt`` (Grund), am Ende ``ende`` (fehlend, Dauer).

Die CLI ``frage`` prüft ohne ``--mock`` vorab das Tagesbudget von ``plattform.llm`` (#100): ist nichts frei,
endet sie mit Exit 3 (``BUDGET_ERSCHOEPFT``) und ruft keinen Adapter.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import threading
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from importlib.metadata import entry_points
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, ValidationError

from .antwortform import Beleg, UcAntwort, Zahl
from .protokoll import protokoll_datei

#: Ein Adapter liefert eine ``UcAntwort`` oder ein Mapping derselben Form (wird streng geprüft).
Adapter = Callable[[str, list[UcAntwort]], UcAntwort | Mapping[str, Any]]

_SCHREIBSPERRE = threading.Lock()

ENTRY_POINT_GRUPPE = "kic.uc_antwort"
STANDARD_KETTE: tuple[str, ...] = ("uc3", "uc2", "uc1")
#: UCs, deren Adapter kein Sprachmodell aufrufen (UC3 rechnet nur mit SQL, R2). Eine Kette nur aus ihnen
#: braucht kein Tagesbudget, etwa die Online-Demo ohne Modell (``UC4_KETTE=uc3``).
OHNE_MODELL: frozenset[str] = frozenset({"uc3"})
#: Exit-Code von ``frage``, wenn das Tagesbudget von ``plattform.llm`` verbraucht ist (Web-App: 429).
BUDGET_ERSCHOEPFT = 3

_REGISTRY: dict[str, Adapter] = {}

#: Ereignis des Stroms (``frage --strom``), eine JSON-Zeile je Ereignis.
Melden = Callable[[dict[str, Any]], None]
#: Pause je Station im Mock-Strom, damit die Seite das Nacheinander auch ohne Modell zeigt (ui-regie-32).
MOCK_PAUSE_S = 1.2
#: Höchstlänge von ``kern`` im Ereignis ``antwort``.
KERN_ZEICHEN = 140


class Fehlend(BaseModel):
    """Ein UC ohne Antwort; ``grund``: ``kein_adapter``, ``ungueltige_antwort`` oder der Fehlertyp."""

    model_config = ConfigDict(extra="forbid")

    uc: str
    grund: str


class Ergebnis(BaseModel):
    """Ergebnis der Kette: Antworten in Kettenreihenfolge, ``fehlend`` die UCs ohne Antwort mit Grund."""

    model_config = ConfigDict(extra="forbid")

    antworten: list[UcAntwort]
    fehlend: list[Fehlend]


@dataclass(frozen=True, slots=True)
class Routerschritt:
    """Eine Zeile je Schritt der Kette, ohne Frage- und Antworttext. ``fehler``: Grund wie in ``Fehlend``."""

    uc: str
    stufe: int
    frage_hash: str
    dauer_ms: int
    modell: str | None
    anzahl_belege: int
    anzahl_zahlen: int
    protokoll_id: int | None
    fehler: str | None


class AdapterFehlt(LookupError):
    """Für den UC ist weder in der Registry noch per Entry-Point ein Adapter bekannt."""


class UngueltigeAntwort(TypeError):
    """Der Adapter lieferte keine ``UcAntwort`` (oder kein passendes Mapping) für seinen UC."""


def registriere(uc: str, funktion: Adapter) -> None:
    """Meldet den Adapter eines UC an; ein späterer Aufruf für denselben UC ersetzt ihn."""
    _REGISTRY[uc] = funktion


def _adapter_finden(uc: str, adapter: Mapping[str, Adapter] | None) -> Adapter:
    if adapter is not None:
        if uc in adapter:
            return adapter[uc]
        raise AdapterFehlt(uc)
    if uc in _REGISTRY:
        return _REGISTRY[uc]
    for punkt in entry_points(group=ENTRY_POINT_GRUPPE, name=uc):
        geladen: Adapter = punkt.load()
        return geladen
    raise AdapterFehlt(uc)


def _frage_hash(frage: str) -> str:
    return hashlib.sha256(frage.encode("utf-8")).hexdigest()


def router_protokoll_datei() -> Path:
    """Ziel der Schrittzeilen: ``PLATTFORM_ROUTER_PROTOKOLL`` oder ``router.jsonl`` neben dem Modellprotokoll.

    Eigene Datei, weil ``modellaufrufe.jsonl`` laut docs/models.md genau eine Zeile je Modellaufruf trägt;
    ein Router-Schritt ist keiner.
    """
    explizit = os.environ.get("PLATTFORM_ROUTER_PROTOKOLL")
    return Path(explizit) if explizit else protokoll_datei().with_name("router.jsonl")


def _schritt_schreiben(schritt: Routerschritt) -> None:
    zeile = asdict(schritt)
    zeile["zeit"] = datetime.now(UTC).isoformat(timespec="milliseconds")
    ziel = router_protokoll_datei()
    ziel.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(zeile, ensure_ascii=False, sort_keys=True) + "\n"
    with _SCHREIBSPERRE, ziel.open("a", encoding="utf-8") as datei:
        datei.write(text)


def _als_antwort(roh: object, uc: str) -> UcAntwort:
    """Nimmt eine ``UcAntwort`` oder ein Mapping (dict, TypedDict) an; prüft streng und dass ``uc`` passt."""
    antwort = UcAntwort.model_validate(roh) if isinstance(roh, Mapping) else roh
    if not isinstance(antwort, UcAntwort) or antwort.uc != uc:
        raise UngueltigeAntwort(uc)
    return antwort


#: Abkürzungen, nach deren Punkt kein Satz endet (kleingeschrieben, ohne Punkt).
_ABKUERZUNGEN = frozenset(
    {
        "z",
        "b",
        "ca",
        "bzw",
        "vgl",
        "inkl",
        "exkl",
        "nr",
        "abs",
        "art",
        "lt",
        "gem",
        "u",
        "a",
        "n",
        "g",
        "d",
        "h",
        "s",
        "o",
        "ä",
        "usw",
        "etc",
        "evtl",
        "ggf",
        "max",
        "min",
        "mio",
        "mrd",
        "rd",
    }
)
#: Monatsnamen nach einer Tageszahl („31. März“): dort endet kein Satz (#150).
_MONATE = frozenset(
    {
        "Januar",
        "Jänner",
        "Februar",
        "Feber",
        "März",
        "April",
        "Mai",
        "Juni",
        "Juli",
        "August",
        "September",
        "Oktober",
        "November",
        "Dezember",
    }
)
_SATZENDE = re.compile(r"[.!?]\s+(?=[A-ZÄÖÜ])")


def kern_satz(text: str, grenze: int = KERN_ZEICHEN) -> str:
    """Erster Satz der ersten Zeile, gekürzt auf ``grenze`` Zeichen.

    Ein Satz endet bei ``.``, ``!`` oder ``?`` vor Leerraum und Großbuchstaben, nicht nach einer Tageszahl
    vor einem Monatsnamen („31. März“) und nicht nach einer Abkürzung („z. B.“, „ca.“, „a. n. g.“).
    """
    erste_zeile = text.strip().split("\n", 1)[0].strip()
    satz = erste_zeile
    for treffer in _SATZENDE.finditer(erste_zeile):
        davor = re.search(r"(\w+)$", erste_zeile[: treffer.start()])
        wort = davor.group(1) if davor else ""
        danach = erste_zeile[treffer.end() :].split(" ", 1)[0].rstrip(",.;:")
        tageszahl = wort.isdigit() and len(wort) <= 2 and danach in _MONATE
        if erste_zeile[treffer.start()] == "." and (tageszahl or wort.lower() in _ABKUERZUNGEN):
            continue
        satz = erste_zeile[: treffer.start() + 1]
        break
    if len(satz) <= grenze:
        return satz
    gekuerzt = satz[: grenze - 1].rsplit(" ", 1)[0].rstrip(" ,;:")
    return f"{gekuerzt}…"


def durchreichen(
    frage: str,
    kette: Sequence[str] = STANDARD_KETTE,
    adapter: Mapping[str, Adapter] | None = None,
    melden: Melden | None = None,
    pause_s: float = 0.0,
) -> Ergebnis:
    """Ruft die Adapter der Kette nacheinander; ``adapter`` ersetzt Registry und Entry-Points ganz.

    Jeder Adapter bekommt tiefe Kopien der bisherigen Antworten: was er am Kontext ändert, ändert keine
    frühere Antwort im Ergebnis. ``melden`` bekommt die Ereignisse des Stroms (siehe Moduldoku), ``pause_s``
    wartet vor jeder Station (nur Mock-Strom).
    """
    antworten: list[UcAntwort] = []
    fehlend: list[Fehlend] = []
    frage_hash = _frage_hash(frage)
    beginn = time.monotonic()
    if melden:
        melden({"art": "start", "kette": list(kette)})
    # Stufe zählt ab 1 wie Vertrag M (plattform.llm: Stufe 1 = gewählter Provider), hier: Stufe 1 = erster UC.
    for stufe, uc in enumerate(kette, start=1):
        if melden:
            melden({"art": "station", "uc": uc, "stufe": stufe, "zustand": "laeuft"})
        if pause_s:
            time.sleep(pause_s)
        start = time.monotonic()
        antwort: UcAntwort | None = None
        grund: str | None = None
        try:
            funktion = _adapter_finden(uc, adapter)
            kontext = [vorher.model_copy(deep=True) for vorher in antworten]
            antwort = _als_antwort(funktion(frage, kontext), uc)
        except AdapterFehlt:
            grund = "kein_adapter"
        except (UngueltigeAntwort, ValidationError):
            grund = "ungueltige_antwort"
        except Exception as fehlerobjekt:  # die Kette läuft mit den übrigen UCs weiter
            grund = type(fehlerobjekt).__name__
        dauer_ms = round((time.monotonic() - start) * 1000)
        _schritt_schreiben(
            Routerschritt(
                uc=uc,
                stufe=stufe,
                frage_hash=frage_hash,
                dauer_ms=dauer_ms,
                modell=antwort.modell if antwort is not None else None,
                anzahl_belege=len(antwort.belege) if antwort is not None else 0,
                anzahl_zahlen=len(antwort.zahlen) if antwort is not None else 0,
                protokoll_id=antwort.protokoll_id if antwort is not None else None,
                fehler=grund,
            )
        )
        if antwort is None:
            fehlend.append(Fehlend(uc=uc, grund=grund or "unbekannt"))
            if melden:
                melden({"art": "fehlt", "uc": uc, "stufe": stufe, "grund": grund or "unbekannt"})
        else:
            antworten.append(antwort)
            if melden:
                melden(
                    {
                        "art": "antwort",
                        "uc": uc,
                        "stufe": stufe,
                        "dauer_ms": dauer_ms,
                        "kern": kern_satz(antwort.text),
                        "antwort": antwort.model_dump(mode="json"),
                    }
                )
    ergebnis = Ergebnis(antworten=antworten, fehlend=fehlend)
    if melden:
        melden(
            {
                "art": "ende",
                "fehlend": [f.model_dump(mode="json") for f in fehlend],
                "dauer_ms": round((time.monotonic() - beginn) * 1000),
            }
        )
    return ergebnis


# --- Mock-Adapter für Tests und Demo ohne Netz -------------------------------------------------------


def _mock_uc3(frage: str, kontext: list[UcAntwort]) -> UcAntwort:
    # Erfundener Wert; der echte UC3-Adapter liest die Zahl aus der Datenbank.
    return UcAntwort(
        text="Im März 2025 waren 412.345 Personen unselbständig beschäftigt (Mock).",
        belege=[
            Beleg(
                uc="uc3",
                quelle="stat.beschaeftigte_monat",
                lieferung="2025-03",
                monat="2025-03",
                regelstand="v1",
                stand="endgueltig",
            )
        ],
        zahlen=[Zahl(bezeichnung="Beschäftigte", wert=412345, einheit="Personen", beleg=0)],
        uc="uc3",
    )


def _mock_uc2(frage: str, kontext: list[UcAntwort]) -> UcAntwort:
    for vorher in kontext:
        if vorher.zahlen:
            zahl = vorher.zahlen[0]
            beleg = vorher.belege[zahl.beleg]
            return UcAntwort(
                text=f"Laut {vorher.uc.upper()}: {zahl.bezeichnung} {zahl.wert} {zahl.einheit or ''}".strip()
                + " (Mock).",
                belege=[beleg],
                zahlen=[zahl.model_copy(update={"beleg": 0})],
                uc="uc2",
                modell="mock",
            )
    return UcAntwort(text="Keine Zahl im Kontext (Mock).", belege=[], zahlen=[], uc="uc2", modell="mock")


def _mock_uc1(frage: str, kontext: list[UcAntwort]) -> UcAntwort:
    # Reicht die erste Zahl des Kontexts mit ihrem Beleg durch (der Beleg behält den liefernden UC).
    for vorher in kontext:
        if vorher.zahlen:
            zahl = vorher.zahlen[0]
            return UcAntwort(
                text=f"Kurz gesagt: Es gab {zahl.wert} {zahl.einheit or ''}, laut Statistik.",
                belege=[vorher.belege[zahl.beleg]],
                zahlen=[zahl.model_copy(update={"beleg": 0})],
                uc="uc1",
                modell="mock",
            )
    return UcAntwort(text="Dazu gibt es noch keine Zahl.", belege=[], zahlen=[], uc="uc1", modell="mock")


def mock_adapter() -> dict[str, Adapter]:
    """Deterministische Adapter für uc3, uc2 und uc1, ohne Netz und ohne Datenbank."""
    return {"uc3": _mock_uc3, "uc2": _mock_uc2, "uc1": _mock_uc1}


def _zeile(ereignis: dict[str, Any]) -> None:
    """Ein Ereignis als eine JSON-Zeile auf stdout, sofort geflusht (die Web-Route liest Zeile für Zeile)."""
    sys.stdout.write(json.dumps(ereignis, ensure_ascii=False) + "\n")
    sys.stdout.flush()


def kette_lesen(text: str) -> tuple[str, ...]:
    """``uc3,uc1`` → ``("uc3", "uc1")``: nur bekannte UCs, keine Doppelten, Reihenfolge der Standardkette."""
    teile = [teil.strip() for teil in text.split(",") if teil.strip()]
    unbekannt = sorted(set(teile) - set(STANDARD_KETTE))
    if not teile or unbekannt or len(set(teile)) != len(teile):
        raise argparse.ArgumentTypeError(f"ungültige Kette: {text!r} (erlaubt: {','.join(STANDARD_KETTE)})")
    return tuple(uc for uc in STANDARD_KETTE if uc in teile)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m plattform.router")
    befehle = parser.add_subparsers(dest="befehl", required=True)
    frage = befehle.add_parser("frage", help="eine Frage durch die Kette uc3 → uc2 → uc1 reichen")
    frage.add_argument("frage")
    frage.add_argument("--json", action="store_true", help="Ergebnis als JSON drucken")
    frage.add_argument("--mock", action="store_true", help="Mock-Adapter statt Registry und Entry-Points")
    frage.add_argument(
        "--kette",
        type=kette_lesen,
        default=STANDARD_KETTE,
        help="Komma-Liste in Kettenreihenfolge, Teilmenge von uc3,uc2,uc1 (Standard: alle drei)",
    )
    frage.add_argument(
        "--strom",
        action="store_true",
        help="je Ereignis eine JSON-Zeile (start, station, antwort oder fehlt, ende), sofort geflusht",
    )
    args = parser.parse_args(argv)
    kette: tuple[str, ...] = args.kette

    # Erst hier laden: wer nur antwortform oder router importiert, zieht plattform.llm nicht nach (R2).
    if not args.mock and not set(kette) <= OHNE_MODELL:
        from .llm import budget_status

        if budget_status()["frei"] == 0:
            meldung = "Das Tageskontingent für Modellaufrufe ist aufgebraucht."
            if args.strom:
                _zeile({"art": "fehler", "fehler": "budget_erschoepft", "meldung": meldung})
            elif args.json:
                print(json.dumps({"fehler": "budget_erschoepft", "meldung": meldung}, ensure_ascii=False))
            else:
                print(meldung, file=sys.stderr)
            return BUDGET_ERSCHOEPFT

    ergebnis = durchreichen(
        args.frage,
        kette=kette,
        adapter=mock_adapter() if args.mock else None,
        melden=_zeile if args.strom else None,
        pause_s=MOCK_PAUSE_S if args.strom and args.mock else 0.0,
    )
    if args.strom:
        pass  # die Ereignisse sind schon gedruckt
    elif args.json:
        print(ergebnis.model_dump_json(indent=2))
    else:
        for antwort in ergebnis.antworten:
            print(f"[{antwort.uc}] {antwort.text}")
        if ergebnis.fehlend:
            fehlend = ", ".join(f"{f.uc} ({f.grund})" for f in ergebnis.fehlend)
            print(f"fehlend: {fehlend}", file=sys.stderr)
    return 0 if ergebnis.antworten else 1


if __name__ == "__main__":
    raise SystemExit(main())
