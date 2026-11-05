#!/usr/bin/env bash
# Installiert den gitleaks-pre-commit-Hook in das gemeinsame Hook-Verzeichnis (gilt für alle Worktrees).
set -euo pipefail
command -v gitleaks >/dev/null || { echo "gitleaks fehlt: brew install gitleaks" >&2; exit 1; }
ziel="$(git rev-parse --path-format=absolute --git-common-dir)/hooks/pre-commit"
cp "$(dirname "$0")/hooks/pre-commit" "$ziel"
chmod +x "$ziel"
echo "pre-commit-Hook installiert: $ziel"
