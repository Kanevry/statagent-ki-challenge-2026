#!/usr/bin/env bash
# Wächter der Abnahme: startet den leichten Prüflauf bei jedem neuen Stand von origin/main.
#
#   bash tests/abnahme/waechter.sh [Sekunden zwischen zwei Blicken, Standard 300]
#
# Misst, schreibt docs/abnahme/laeufe/*.jsonl und die Matrix, kommentiert geänderte Befunde und hakt gültig
# bestandene Kriterien ab (beides wiederholbar, Marke je Befund und Beleg). Er committet nicht und schreibt den
# Lanes nicht: das macht der Prüfer. Prüfsätze wirken erst nach Commit und Sichtung. Läuft nie doppelt.
set -euo pipefail
cd "$(dirname "$0")/../.."
pause="${1:-300}"
sperre="/tmp/kic-abnahme-waechter.lock"
if ! mkdir "$sperre" 2>/dev/null; then
  echo "Wächter läuft schon (Sperre $sperre)" >&2
  exit 3
fi
trap 'rmdir "$sperre"' EXIT
letzter=""
while true; do
  git fetch -q origin main || { echo "$(date '+%H:%M') fetch gescheitert, nächster Versuch" >&2; sleep "$pause"; continue; }
  sha="$(git rev-parse origin/main)"
  if [[ "$sha" != "$letzter" ]]; then
    echo "$(TZ=Europe/Vienna date '+%H:%M') neuer main ${sha:0:8}: Lauf startet"
    if timeout 1200 uv run python tests/abnahme/pruefen.py 2>&1 | grep -E '^(Lauf|abgelegt|Hinweis)'; then
      uv run python tests/abnahme/matrix.py schreiben | sed -n '1,6p'
      for b in uc3 uc1 uc2 plattform; do
        uv run python tests/abnahme/matrix.py befunde --bereich "$b" --ja | tail -1
      done
      uv run python tests/abnahme/matrix.py abhaken alle --ja | grep -c abgehakt=True | sed 's/^/abgehakt (Bestand): /'
      letzter="$sha"
    else
      echo "$(TZ=Europe/Vienna date '+%H:%M') Lauf gescheitert, nächster Versuch" >&2
    fi
  fi
  sleep "$pause"
done
