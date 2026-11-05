"""Protokoll der Plattform (Vertrag P).

Teil 1 (dieses Gerüst, #53): ``modellaufruf`` schreibt je Modellaufruf genau eine JSON-Zeile mit
Provider, Modell, Version, Zweck, Prompt-Hash, Dauer, Tokens und Fallback-Stufe, nie den Inhalt.
``plattform.llm`` (#54) ruft es auf; die Signatur ist Vertrag.

Teil 2 (#55): ``schreibe``/``lies`` gegen ``meta.protokoll`` und der JSON-Vertrag ``Eintrag``.
"""

from __future__ import annotations

import json
import os
import threading
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path

_SCHREIBSPERRE = threading.Lock()


@dataclass(frozen=True, slots=True)
class Modellaufruf:
    """Eine Protokollzeile je Modellaufruf. Absichtlich ohne Feld für Prompt oder Antwort."""

    provider: str
    modell: str
    version: str | None
    zweck: str
    prompt_hash: str
    dauer_ms: int
    tokens_in: int | None
    tokens_out: int | None
    fallback_stufe: int
    aufwand: str | None = None
    fehler: str | None = None
    zeit: str = ""


def protokoll_datei() -> Path:
    """Ziel der Modell-Protokollzeilen: ``PLATTFORM_PROTOKOLL`` oder ``var/protokoll/modellaufrufe.jsonl``."""
    explizit = os.environ.get("PLATTFORM_PROTOKOLL")
    if explizit:
        return Path(explizit)
    wurzel = Path.cwd().resolve()
    for ordner in (wurzel, *wurzel.parents):
        if (ordner / ".git").exists():
            wurzel = ordner
            break
    return wurzel / "var" / "protokoll" / "modellaufrufe.jsonl"


def modellaufruf(eintrag: Modellaufruf) -> Path:
    """Hängt genau eine Zeile an und gibt die Datei zurück."""
    zeile = asdict(eintrag)
    if not zeile["zeit"]:
        zeile["zeit"] = datetime.now(UTC).isoformat(timespec="milliseconds")
    ziel = protokoll_datei()
    ziel.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(zeile, ensure_ascii=False, sort_keys=True) + "\n"
    with _SCHREIBSPERRE, ziel.open("a", encoding="utf-8") as datei:
        datei.write(text)
    return ziel
