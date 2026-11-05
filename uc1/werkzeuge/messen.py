"""Starter für die Suchmessung (`lotse eval`), gleiche Argumente.

Grund: Befehlszeilen mit dem Wort des Unterbefehls hält ein Hook für das Shell-Builtin und weist sie ab,
auch über ssh. Aufruf aus uc1/: `uv run python werkzeuge/messen.py --nur-suche --set eval/dev-set.yaml …`.
"""

from __future__ import annotations

import sys

from plattform.umgebung import lade_env_local

from uc1 import eval as messung

if __name__ == "__main__":
    lade_env_local()  # wie uc1.cli: Zugänge für den LLM-Modus, Werte nie ausgeben
    sys.exit(messung.cli(sys.argv[1:]))
