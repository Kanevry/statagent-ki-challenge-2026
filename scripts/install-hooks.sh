#!/usr/bin/env bash
# Installiert den gitleaks-pre-commit-Hook in das gemeinsame Hook-Verzeichnis (gilt für alle Worktrees).
# Bricht ab, statt einen fremden Hook zu überschreiben oder an core.hooksPath vorbei zu installieren.
set -euo pipefail
command -v gitleaks >/dev/null || { echo "gitleaks fehlt: brew install gitleaks" >&2; exit 1; }
quelle="$(cd "$(dirname "$0")" && pwd)/hooks/pre-commit"
if hookpfad="$(git config --get core.hooksPath)"; then
  echo "core.hooksPath ist gesetzt ($hookpfad): Hook dort selbst einbinden, $quelle wird nicht installiert." >&2
  exit 1
fi
ziel="$(git rev-parse --path-format=absolute --git-common-dir)/hooks/pre-commit"
if [ -e "$ziel" ] && ! cmp -s "$quelle" "$ziel"; then
  echo "Ein anderer pre-commit-Hook existiert schon: $ziel. Bitte zusammenführen, nichts geändert." >&2
  exit 1
fi
mkdir -p "$(dirname "$ziel")"
cp "$quelle" "$ziel"
chmod +x "$ziel"
cmp -s "$quelle" "$ziel" && echo "pre-commit-Hook installiert: $ziel"
