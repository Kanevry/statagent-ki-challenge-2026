"""Router UC4 (#97): reicht eine Frage durch die Kette uc3 → uc2 → uc1.

Jeder Schritt ruft den Adapter des UC mit der Frage und den bisherigen Antworten als Kontext. Adapter kommen
aus der Registry (``registriere``) oder der Entry-Point-Gruppe ``kic.uc_antwort``, nie aus einem harten Import
der UC-Pakete. Fehlt ein Adapter oder wirft er, läuft die Kette weiter und ``fehlend`` nennt den UC.

Je Schritt genau eine Zeile über ``plattform.protokoll.modellaufruf``: Hash der Frage, nie Frage- oder
Antworttext; bei einem Fehler nur dessen Typ. Nicht aus ``plattform/__init__.py`` importiert (R2).
"""

from __future__ import annotations

import argparse
import hashlib
import sys
import time
from collections.abc import Callable, Mapping, Sequence
from importlib.metadata import entry_points

from pydantic import BaseModel, ConfigDict

from .antwortform import Beleg, UcAntwort, Zahl
from .protokoll import Modellaufruf, modellaufruf

Adapter = Callable[[str, list[UcAntwort]], UcAntwort]

ENTRY_POINT_GRUPPE = "kic.uc_antwort"
STANDARD_KETTE: tuple[str, ...] = ("uc3", "uc2", "uc1")

_REGISTRY: dict[str, Adapter] = {}


class Ergebnis(BaseModel):
    """Ergebnis der Kette: Antworten in Kettenreihenfolge, ``fehlend`` die UCs ohne Antwort."""

    model_config = ConfigDict(extra="forbid")

    antworten: list[UcAntwort]
    fehlend: list[str]


class AdapterFehlt(LookupError):
    """Für den UC ist weder in der Registry noch per Entry-Point ein Adapter bekannt."""


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


def durchreichen(
    frage: str,
    kette: Sequence[str] = STANDARD_KETTE,
    adapter: Mapping[str, Adapter] | None = None,
) -> Ergebnis:
    """Ruft die Adapter der Kette nacheinander; ``adapter`` ersetzt Registry und Entry-Points ganz."""
    antworten: list[UcAntwort] = []
    fehlend: list[str] = []
    frage_hash = _frage_hash(frage)
    for stufe, uc in enumerate(kette):
        start = time.monotonic()
        antwort: UcAntwort | None = None
        fehler: str | None = None
        try:
            funktion = _adapter_finden(uc, adapter)
            antwort = funktion(frage, list(antworten))
            if not isinstance(antwort, UcAntwort) or antwort.uc != uc:
                raise TypeError(f"Adapter {uc} lieferte keine UcAntwort für {uc}")
        except Exception as fehlerobjekt:  # die Kette läuft mit den übrigen UCs weiter
            antwort = None
            fehler = type(fehlerobjekt).__name__
        modellaufruf(
            Modellaufruf(
                provider="router",
                modell=(antwort.modell if antwort is not None else None) or "keins",
                version=None,
                zweck=f"uc4.{uc}",
                prompt_hash=frage_hash,
                dauer_ms=round((time.monotonic() - start) * 1000),
                tokens_in=None,
                tokens_out=None,
                fallback_stufe=stufe,
                fehler=fehler,
            )
        )
        if antwort is None:
            fehlend.append(uc)
        else:
            antworten.append(antwort)
    return Ergebnis(antworten=antworten, fehlend=fehlend)


# --- Mock-Adapter für Tests und Demo ohne Netz -------------------------------------------------------


def _mock_uc3(frage: str, kontext: list[UcAntwort]) -> UcAntwort:
    # Erfundener Wert; der echte UC3-Adapter liest die Zahl aus der Datenbank.
    return UcAntwort(
        text="Im März 2025 waren 412.345 Personen unselbständig beschäftigt (Mock).",
        belege=[Beleg(quelle="roh.lieferung", lieferung="2025-03", monat="2025-03", sql=None, ref=None)],
        zahlen=[Zahl(bezeichnung="Beschäftigte", wert=412345, einheit="Personen", beleg=0)],
        uc="uc3",
        modell=None,
        protokoll_id=None,
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
                protokoll_id=None,
            )
    return UcAntwort(
        text="Keine Zahl im Kontext (Mock).", belege=[], zahlen=[], uc="uc2", modell="mock", protokoll_id=None
    )


def _mock_uc1(frage: str, kontext: list[UcAntwort]) -> UcAntwort:
    zahlen = [z for vorher in kontext for z in vorher.zahlen]
    text = (
        f"Kurz gesagt: Es gab {zahlen[0].wert} {zahlen[0].einheit or ''}. Die Zahl kommt aus der Statistik."
        if zahlen
        else "Dazu gibt es noch keine Zahl."
    )
    return UcAntwort(text=text, belege=[], zahlen=[], uc="uc1", modell="mock", protokoll_id=None)


def mock_adapter() -> dict[str, Adapter]:
    """Deterministische Adapter für uc3, uc2 und uc1, ohne Netz und ohne Datenbank."""
    return {"uc3": _mock_uc3, "uc2": _mock_uc2, "uc1": _mock_uc1}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m plattform.router")
    befehle = parser.add_subparsers(dest="befehl", required=True)
    frage = befehle.add_parser("frage", help="eine Frage durch die Kette uc3 → uc2 → uc1 reichen")
    frage.add_argument("frage")
    frage.add_argument("--json", action="store_true", help="Ergebnis als JSON drucken")
    frage.add_argument("--mock", action="store_true", help="Mock-Adapter statt Registry und Entry-Points")
    args = parser.parse_args(argv)

    ergebnis = durchreichen(args.frage, adapter=mock_adapter() if args.mock else None)
    if args.json:
        print(ergebnis.model_dump_json(indent=2))
    else:
        for antwort in ergebnis.antworten:
            print(f"[{antwort.uc}] {antwort.text}")
        if ergebnis.fehlend:
            print("fehlend: " + ", ".join(ergebnis.fehlend), file=sys.stderr)
    return 0 if ergebnis.antworten else 1


if __name__ == "__main__":
    raise SystemExit(main())
