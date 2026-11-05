#!/usr/bin/env bash
# Wächter der Abnahme: startet den leichten Prüflauf bei jedem neuen Stand von origin/main.
#
#   bash tests/abnahme/waechter.sh [Sekunden zwischen zwei Blicken, Standard 300]
#
# Misst, schreibt docs/abnahme/laeufe/*.jsonl und die Matrix, kommentiert geänderte Befunde, hakt gültig bestandene
# Kriterien ab und entfernt unbelegte Haken (alles wiederholbar, Marke je Befund und Beleg). Ist
# ABNAHME_PRUEFRECHNER_ENV gesetzt (Datei außerhalb des Repos), stößt er bei UC3-Änderungen den schweren Lauf an
# (im Hintergrund, nie zwei gleichzeitig). Er committet nicht und schreibt den Lanes nicht: das macht der Prüfer.
# Prüfsätze wirken erst nach Commit und Sichtung. Läuft nie doppelt.
set -euo pipefail
cd "$(dirname "$0")/../.."
pause="${1:-300}"
sperre="/tmp/kic-abnahme-waechter.lock"
if ! mkdir "$sperre" 2>/dev/null; then
  echo "Wächter läuft schon (Sperre $sperre)" >&2
  exit 3
fi
trap 'rmdir "$sperre"' EXIT
veroeffentlichen() {
  uv run python tests/abnahme/matrix.py schreiben | sed -n '1,6p'
  for b in uc3 uc1 uc2 plattform; do
    uv run python tests/abnahme/matrix.py befunde --bereich "$b" --ja | tail -1
  done
  uv run python tests/abnahme/matrix.py abhaken alle --ja | grep -c abgehakt=True | sed 's/^/abgehakt (Bestand): /' || true
  uv run python tests/abnahme/matrix.py haken pruefen --ja | tail -1
}
letzter=""
laeufe_vorher="$(ls docs/abnahme/laeufe | wc -l)"
while true; do
  git fetch -q origin main || { echo "$(date '+%H:%M') fetch gescheitert, nächster Versuch" >&2; sleep "$pause"; continue; }
  sha="$(git rev-parse origin/main)"
  if [[ "$sha" != "$letzter" ]]; then
    echo "$(TZ=Europe/Vienna date '+%H:%M') neuer main ${sha:0:8}: Lauf startet"
    if timeout 1200 uv run python tests/abnahme/pruefen.py 2>&1 | grep -E '^(Lauf|abgelegt|Hinweis)'; then
      letzter="$sha"
      if [[ -n "${ABNAHME_PRUEFRECHNER_ENV:-}" && -f "$ABNAHME_PRUEFRECHNER_ENV" ]]; then
        (bash tests/abnahme/schwer_ausloesen.sh "$ABNAHME_PRUEFRECHNER_ENV" >> /tmp/kic-abnahme-schwer.log 2>&1 &)
      fi
    else
      echo "$(TZ=Europe/Vienna date '+%H:%M') Lauf gescheitert, nächster Versuch" >&2
    fi
  fi
  laeufe_jetzt="$(ls docs/abnahme/laeufe | wc -l)"
  if [[ "$laeufe_jetzt" != "$laeufe_vorher" ]]; then
    veroeffentlichen
    laeufe_vorher="$laeufe_jetzt"
  fi
  sleep "$pause"
done
