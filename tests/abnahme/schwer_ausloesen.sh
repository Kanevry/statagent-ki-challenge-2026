#!/bin/bash
# Stößt den schweren Lauf auf dem Prüfrechner an und holt die Laufdatei zurück (docs/abnahme/PROZESS.md, Rhythmus).
#
#   bash tests/abnahme/schwer_ausloesen.sh <env-datei>
#
# Die env-Datei liegt außerhalb des Repos (öffentliches Repo: keine Hostnamen, keine Pfade fremder Rechner) und setzt
#   PRUEFRECHNER       ssh-Alias des Prüfrechners
#   PRUEFRECHNER_DIR   Ordner mit abnahme.env und schwer_pruefrechner.sh auf dem Prüfrechner
# Läuft nur, wenn sich main seit dem letzten schweren Lauf in UC3-Pfaden geändert hat; nie zwei gleichzeitig.
set -euo pipefail
cd "$(dirname "$0")/../.."
# shellcheck source=/dev/null
. "${1:?env-Datei fehlt}"
: "${PRUEFRECHNER:?}" "${PRUEFRECHNER_DIR:?}"
sperre="/tmp/kic-abnahme-schwer.lock"
mkdir "$sperre" 2>/dev/null || { echo "schwerer Lauf läuft schon"; exit 0; }
trap 'rmdir "$sperre"' EXIT
stand_datei="/tmp/kic-abnahme-schwer.letzter"
sha="$(git rev-parse origin/main)"
werkzeug="$(git rev-parse HEAD)"
if [ -s "$stand_datei" ] && git diff --quiet "$(cat "$stand_datei")" "$sha" -- uc3 abgabe docs/plan/uc3 shared \
  pyproject.toml uv.lock tests/abnahme/orakel; then
  echo "schwer: keine UC3-Änderung seit $(cut -c1-8 "$stand_datei")"
  exit 0
fi
tmp="$(mktemp -d /tmp/kic-abnahme-schwer.XXXXXX)"
git bundle create -q "$tmp/abnahme.bundle" refs/remotes/origin/main "refs/heads/$(git rev-parse --abbrev-ref HEAD)"
uv run python -c "import json,sys; sys.path.insert(0,'tests/abnahme'); import matrix; \
json.dump(matrix.issues_holen(None), open('$tmp/issues.json','w'))"
scp -q "$tmp/abnahme.bundle" "$tmp/issues.json" tests/abnahme/schwer_pruefrechner.sh "$PRUEFRECHNER:$PRUEFRECHNER_DIR/"
echo "schwer: Lauf startet für main ${sha:0:8} $(TZ=Europe/Vienna date '+%H:%M')"
if ssh "$PRUEFRECHNER" "bash $PRUEFRECHNER_DIR/schwer_pruefrechner.sh $PRUEFRECHNER_DIR/abnahme.bundle $sha $werkzeug \
  $PRUEFRECHNER_DIR/issues.json" > "$tmp/lauf.log" 2>&1; then
  datei="$(tail -1 "$tmp/lauf.log")"
  scp -q "$PRUEFRECHNER:$PRUEFRECHNER_DIR/repo/docs/abnahme/laeufe/$datei" "docs/abnahme/laeufe/${datei%.jsonl}-schwer.jsonl"
  grep -E '^(Lauf|lauf_alle_exit)' "$tmp/lauf.log"
  echo "$sha" > "$stand_datei"
else
  echo "schwer: Lauf gescheitert, Log $tmp/lauf.log" >&2
  tail -5 "$tmp/lauf.log" >&2
  exit 1
fi
