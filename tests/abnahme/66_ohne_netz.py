"""Abnahme #66 (EA-4): führt eine statagent-CLI ohne Netz aus und belegt das.

Aufruf: ``uv run python tests/abnahme/66_ohne_netz.py lauf --lieferung 2024-08``

Was gemessen wird:
- Jeder Verbindungsversuch über Python-Sockets wird abgewiesen und gezählt. Die Datenbank
  spricht libpq (C) und ist davon nicht betroffen; erlaubt bleibt außerdem localhost.
- Nach dem Befehl steht, ob ``plattform.llm``, ``openai`` oder ``httpx`` geladen wurden.

Die letzte Zeile ist JSON: ``{"exit": ..., "netzversuche": [...], "geladen": [...]}``.
Der Prüfer liest das Ergebnis, das Skript entscheidet nichts.
"""

from __future__ import annotations

import json
import os
import socket
import sys

os.environ.pop("LLM_PROVIDER", None)
os.environ["AZURE_OPENAI_BASE_URL"] = "http://localhost:9"

ERLAUBT = {"localhost", "::1", "127.0.0.1"}
versuche: list[str] = []
_connect = socket.socket.connect
_create = socket.create_connection


def _ziel(adresse: object) -> str:
    if isinstance(adresse, tuple) and adresse:
        return str(adresse[0])
    return str(adresse)


def _sperre_connect(self: socket.socket, adresse: object) -> None:
    ziel = _ziel(adresse)
    if self.family == socket.AF_UNIX or ziel in ERLAUBT:
        _connect(self, adresse)  # type: ignore[arg-type]
        return
    versuche.append(ziel)
    raise OSError(f"Abnahme: Netz gesperrt ({ziel})")


def _sperre_create(adresse: tuple[str, int], *args: object, **kwargs: object) -> socket.socket:
    if adresse[0] not in ERLAUBT:
        versuche.append(str(adresse[0]))
        raise OSError(f"Abnahme: Netz gesperrt ({adresse[0]})")
    return _create(adresse, *args, **kwargs)  # type: ignore[arg-type]


socket.socket.connect = _sperre_connect  # type: ignore[method-assign]
socket.create_connection = _sperre_create  # type: ignore[assignment]


def main() -> int:
    from statagent.cli import app

    code: object = 0
    try:
        app(args=sys.argv[1:], prog_name="uc3")
    except SystemExit as ende:
        code = ende.code
    geladen = sorted(
        name
        for name in sys.modules
        if name == "plattform.llm" or name.startswith(("plattform.llm.", "openai", "httpx"))
    )
    print(json.dumps({"exit": code, "netzversuche": versuche, "geladen": geladen}, ensure_ascii=False))
    return 0 if code in (0, None) else 1


if __name__ == "__main__":
    raise SystemExit(main())
