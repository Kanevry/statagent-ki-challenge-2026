#!/bin/bash
# Schwerer Abnahme-Lauf auf dem Prüfrechner (docs/abnahme/PROZESS.md, Abschnitt Rhythmus).
#
#   bash schwer_pruefrechner.sh <bundle> <main-sha> <werkzeug-sha> <issues.json>
#
# 1. Holt main und den Abnahme-Branch aus dem Bundle in ABNAHME_REPO, checkt main-SHA aus und setzt tests/abnahme
#    aus dem Werkzeug-Commit ein; die Hilfsskripte neben abnahme.env werden aus diesem Stand erneuert.
# 2. README-Weg auf frischer Prüf-DB (eigenes Compose-Projekt, Port 5444, Zielprüfung; die Bau-DB wird verweigert).
# 3. pruefen.py --schwer gegen die Prüf-DB; die Laufdatei liegt danach in ABNAHME_REPO/docs/abnahme/laeufe/.
# Jeder Fehler bricht ab. Konfiguration: abnahme.env neben diesem Skript (Vorlage abnahme.env.example).
set -euo pipefail
HIER="$(cd "$(dirname "$0")" && pwd)"
# shellcheck source=/dev/null
. "$HIER/abnahme.env"
: "${ABNAHME_REPO:?ABNAHME_REPO fehlt}"
export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"
bundle="${1:?Bundle fehlt}"
sha="${2:?main-SHA fehlt}"
werkzeug="${3:?Werkzeug-SHA fehlt}"
issues="${4:?Issue-Abzug fehlt}"
PORT="${ABNAHME_DB_PORT:-5444}"
if [ "$PORT" != "5444" ]; then
  echo "Abbruch: Prüf-DB muss auf 5444 laufen, nicht $PORT." >&2
  exit 3
fi

echo "== holen $(TZ=Europe/Vienna date '+%H:%M')"
git -C "$ABNAHME_REPO" fetch -q "$bundle" \
  "+refs/remotes/origin/main:refs/heads/main-abnahme" "+refs/heads/test/abnahme-matrix:refs/heads/abnahme-werkzeug"
# ABNAHME_REPO ist laut abnahme.env der Prüf-Klon der Abnahme; die Marke erlaubt pruefen.py das harte Zurücksetzen.
touch "$ABNAHME_REPO/.kic-abnahme-pruefklon"
# Hart zurücksetzen: frühere Prüfsätze können Dateien im Klon verändert haben (Review 4d, 19:00).
git -C "$ABNAHME_REPO" checkout -q -f --detach "$sha"
git -C "$ABNAHME_REPO" clean -fdq -e .kic-abnahme-pruefklon
git -C "$ABNAHME_REPO" checkout -q "$werkzeug" -- tests/abnahme
for f in 66_jury_weg.sh 66_readme_weg.sh 66_ohne_netz.py 66_kanon_hash.sql 66_manifest_vergleich.py \
  compose-abnahme.override.yml; do
  cp "$ABNAHME_REPO/tests/abnahme/$f" "$HIER/$f"
done
(cd "$ABNAHME_REPO" && uv sync --frozen --all-packages -q)
(cd "$ABNAHME_REPO" && pnpm install --frozen-lockfile --ignore-scripts --silent) || echo "Hinweis: pnpm install gescheitert, vitest-Prüfsätze werden Lauf-Fehler"

echo "== readme-weg $(TZ=Europe/Vienna date '+%H:%M')"
bash "$HIER/66_readme_weg.sh"

echo "== pruefen $(TZ=Europe/Vienna date '+%H:%M')"
mkdir -p "$HIER/abgabe"
printf 'UC3_DATABASE_URL=postgresql://statistik:statistik@localhost:%s/statistik\nSTATAGENT_STARTPAKET=%s\nSTATAGENT_ABGABE=%s\n' \
  "$PORT" "$STARTPAKET_UC3" "$HIER/abgabe" > "$HIER/pruef-db.env"
(cd "$ABNAHME_REPO" && uv run python tests/abnahme/pruefen.py --schwer --ort . --sha "$sha" \
  --werkzeug "$werkzeug" --cache "$issues" --db-env "$HIER/pruef-db.env")
ls -t "$ABNAHME_REPO/docs/abnahme/laeufe/" | head -1
