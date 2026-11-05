"""claude (nur UC1/UC2-Qualitätsmodus und Vergleiche, nie UC3): Claude Code als Subprozess im Abo.

Kein ``--bare`` (das verlangt einen API-Key). Damit das Projekt-CLAUDE.md und Hooks nicht geladen werden,
läuft der Prozess in einem frischen, leeren Temp-Verzeichnis. ``ANTHROPIC_API_KEY`` in der Umgebung würde
auf API-Abrechnung umschalten: dann bricht der Aufruf vor dem Subprozess ab.
"""

from __future__ import annotations

import json
import os
import subprocess
import tempfile
from collections.abc import Callable
from typing import Any

from .basis import KonfigFehler, Nachricht, Provider, Rohantwort, VoruebergehenderFehler

ZEITLIMIT_S = 120

#: Runner-Vertrag: ``(argv, eingabe, cwd, zeitlimit_s) -> CompletedProcess`` (in Tests ersetzbar).
Runner = Callable[[list[str], str, str, int], "subprocess.CompletedProcess[str]"]


def _subprozess(
    argv: list[str], eingabe: str, cwd: str, zeitlimit_s: int
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        argv, input=eingabe, cwd=cwd, timeout=zeitlimit_s, capture_output=True, text=True, check=False
    )


def flache_nachrichten(nachrichten: list[Nachricht]) -> str:
    """Nachrichtenliste als ein Prompt mit Rollen-Markern."""
    return "\n\n".join(f"[{n['role']}]\n{n['content']}" for n in nachrichten)


class ClaudeProvider(Provider):
    name = "claude"

    def __init__(self, runner: Runner | None = None) -> None:
        self._runner = runner or _subprozess

    def standard_modell(self, groesse: str) -> str:
        return os.environ.get("CLAUDE_MODEL") or "claude-opus-5-5"

    def argv(self, modell: str, schema: dict[str, Any] | None) -> list[str]:
        befehl = ["claude", "-p", "--model", modell, "--output-format", "json", "--tools", ""]
        befehl.append("--strict-mcp-config")
        if schema is not None:
            befehl += ["--json-schema", json.dumps(schema, ensure_ascii=False)]
        return befehl

    def rufe(
        self,
        nachrichten: list[Nachricht],
        *,
        schema: dict[str, Any] | None,
        modell: str,
        aufwand: str | None,
        zweck: str,
    ) -> Rohantwort:
        if os.environ.get("ANTHROPIC_API_KEY"):
            raise KonfigFehler(
                "claude: ANTHROPIC_API_KEY ist gesetzt. Der claude-Provider läuft nur im Abo; "
                "Variable aus der Umgebung entfernen."
            )
        with tempfile.TemporaryDirectory(prefix="plattform-claude-") as leer:
            try:
                ergebnis = self._runner(
                    self.argv(modell, schema), flache_nachrichten(nachrichten), leer, ZEITLIMIT_S
                )
            except subprocess.TimeoutExpired as fehler:
                raise VoruebergehenderFehler(f"claude: Zeitlimit {ZEITLIMIT_S} s") from fehler
            except FileNotFoundError as fehler:
                raise VoruebergehenderFehler("claude: CLI nicht gefunden") from fehler
        if ergebnis.returncode != 0:
            raise VoruebergehenderFehler(f"claude: Exit {ergebnis.returncode}")
        try:
            daten = json.loads(ergebnis.stdout)
        except json.JSONDecodeError as fehler:
            raise VoruebergehenderFehler("claude: Ausgabe ist kein JSON") from fehler
        if daten.get("is_error"):
            raise VoruebergehenderFehler(f"claude: {daten.get('subtype', 'Fehler')}")
        usage = daten.get("usage") or {}
        tokens_in = None
        if usage:
            tokens_in = sum(
                int(usage.get(k) or 0)
                for k in ("input_tokens", "cache_read_input_tokens", "cache_creation_input_tokens")
            )
        modelle = list((daten.get("modelUsage") or {}).keys())
        version = next((m for m in modelle if m.startswith(modell)), modelle[0] if modelle else None)
        strukturiert = daten.get("structured_output")
        text = daten.get("result") or ""
        if strukturiert is not None and not text:
            text = json.dumps(strukturiert, ensure_ascii=False)
        return Rohantwort(
            text=text,
            modell=modell,
            version=version,
            tokens_in=tokens_in,
            tokens_out=usage.get("output_tokens") if usage else None,
            json=strukturiert,
        )
