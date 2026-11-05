"""Brücke zur gemeinsamen Plattform (E0): Modell-Schalter (Vertrag M) und Freigabe (Vertrag P).

UC3 baut keinen eigenen Modellaufruf und keinen eigenen Freigabe-Commit. Diese Datei holt beides erst beim
Gebrauch aus ``plattform.llm`` und ``plattform.freigabe``. Fehlt ein Modul noch, kommt eine klare Meldung
(``PlattformFehlt``) statt eines Absturzes beim Import. Der Monatslauf importiert diese Datei nie.

Einzige Ausnahme bis ``plattform.freigabe`` da ist: ``pruefe_freigegeben`` vergleicht den Inhalt einer
Code-Datei selbst mit dem freigegebenen sha256 aus ``meta.vorschlag`` (gleiche Bedeutung wie später der
Vergleich mit dem Freigabe-Commit).
"""

from __future__ import annotations

import hashlib
import importlib
from collections.abc import Callable
from pathlib import Path
from types import ModuleType
from typing import Any

from statagent.db import Verbindung

#: ``complete(nachrichten, schema=None, stream=False, provider=None, zweck=…) -> Antwort`` (Vertrag M).
CompleteFunktion = Callable[..., Any]
#: ``freigeben(conn, vorschlag_id, name, repo_pfad) -> Freigabe`` (Vertrag P); ``ablehnen`` analog.
FreigabeFunktion = Callable[..., Any]
#: ``pruefe_freigegeben(conn, datei, repo_pfad) -> bool``.
PruefFunktion = Callable[[Verbindung, Path, Path], bool]

#: Vorschlagstypen in UC3 → Objekttypen im Vertrag P (Nachtrag zu !6).
VERTRAG_TYP = {"regel_neu": "regel", "regel_aendern": "regel", "code_datei": "datei"}


class PlattformFehlt(RuntimeError):
    """Ein Modul der Plattform (E0) ist in diesem Stand noch nicht vorhanden."""


def _modul(name: str, issue: str) -> ModuleType:
    try:
        return importlib.import_module(name)
    except ModuleNotFoundError as fehler:
        if fehler.name is not None and (fehler.name == name or name.startswith(fehler.name + ".")):
            raise PlattformFehlt(f"{name} ({issue}) ist noch nicht verfügbar") from fehler
        raise


def lade_complete() -> CompleteFunktion:
    """``plattform.llm.complete`` (#54), erst beim ersten Agentenaufruf geladen."""
    funktion: CompleteFunktion = _modul("plattform.llm", "#54").complete
    return funktion


def lade_freigabe() -> FreigabeFunktion:
    """``plattform.freigabe.freigeben`` (#55): schreibt meta.freigabe und den Commit mit Trailer."""
    funktion: FreigabeFunktion = _modul("plattform.freigabe", "#55").freigeben
    return funktion


def lade_ablehnung() -> FreigabeFunktion:
    """``plattform.freigabe.ablehnen`` (#55): schreibt meta.freigabe ohne Commit."""
    funktion: FreigabeFunktion = _modul("plattform.freigabe", "#55").ablehnen
    return funktion


def sha256_datei(inhalt: bytes) -> str:
    return hashlib.sha256(inhalt).hexdigest()


def relativer_pfad(datei: Path, repo_pfad: Path) -> str:
    """Pfad einer Datei relativ zur Repo-Wurzel, mit ``/`` (so steht er in meta.vorschlag)."""
    return datei.resolve().relative_to(repo_pfad.resolve()).as_posix()


def _eigene_pruefung(conn: Verbindung, datei: Path, repo_pfad: Path) -> bool:
    """Übergang bis #55: Inhalt der Datei = freigegebener Inhalt laut meta.vorschlag (sha256)."""
    try:
        pfad = relativer_pfad(datei, repo_pfad)
        inhalt = datei.read_bytes()
    except (ValueError, OSError):
        return False
    zeile = conn.execute(
        """SELECT aenderungen -> 0 ->> 'inhalt_sha256' AS sha FROM meta.vorschlag
           WHERE typ = 'code_datei' AND status = 'freigegeben' AND aenderungen -> 0 ->> 'pfad' = %s
           ORDER BY id DESC LIMIT 1""",
        (pfad,),
    ).fetchone()
    return zeile is not None and zeile["sha"] == sha256_datei(inhalt)


def pruefe_freigegeben(conn: Verbindung, datei: Path, repo_pfad: Path) -> bool:
    """Ist genau dieser Dateiinhalt freigegeben? Nutzt ``plattform.freigabe.pruefe_freigegeben``, sobald es da ist."""
    try:
        modul = _modul("plattform.freigabe", "#55")
    except PlattformFehlt:
        return _eigene_pruefung(conn, datei, repo_pfad)
    plattform_pruefung = getattr(modul, "pruefe_freigegeben", None)
    if plattform_pruefung is None:
        return _eigene_pruefung(conn, datei, repo_pfad)
    return bool(plattform_pruefung(conn, datei, repo_pfad))
