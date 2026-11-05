#!/bin/bash
# Abnahme #66 (66-6): README-Weg „In fünf Befehlen“ auf frisch geladener Prüf-DB, ohne manuelles ANALYZE.
# Misst je Monat die Dauer von `uc3 lauf --alle` und schreibt danach die Läufe als TSV für 66_manifest_vergleich.py.
# Nur die eigene Prüf-DB (abnahme.env); 66_jury_weg.sh verweigert die Bau-DB.
# Jeder Fehler bricht ab (Review !56); vor dem Lauf prüft `ziel`, dass die URL den Abnahme-Container erreicht.
set -euo pipefail
HIER="$(cd "$(dirname "$0")" && pwd)"
# shellcheck source=/dev/null
. "$HIER/abnahme.env"
PORT="${ABNAHME_DB_PORT:-5444}"
CONTAINER="${ABNAHME_CONTAINER:-kic-abnahme-db}"
export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"
export UC3_DATABASE_URL="postgresql://statistik:statistik@localhost:${PORT}/statistik"
export STATAGENT_STARTPAKET="$STARTPAKET_UC3"
echo "== kopf $(git -C "$ABNAHME_REPO" rev-parse HEAD)"
bash "$HIER/66_jury_weg.sh" frisch || exit 1
bash "$HIER/66_jury_weg.sh" sync
bash "$HIER/66_jury_weg.sh" init > /dev/null && echo "init ok"
bash "$HIER/66_jury_weg.sh" ziel
start=$(date +%s)
if (cd "$ABNAHME_REPO" && timeout 1500 uv run uc3 lauf --alle > "$HIER/lauf_alle.log" 2>&1); then
  rc=0
else
  rc=$?
fi
grep -E '^20[0-9]{2}-[0-9]{2} ' "$HIER/lauf_alle.log" | cut -c1-120
echo "lauf_alle_exit=$rc dauer_s=$(( $(date +%s) - start ))"
docker exec -i "$CONTAINER" psql -U statistik -d statistik -At -F "$(printf '\t')" \
  -c "select distinct on (lieferung) lieferung, ergebnis_hash, gezaehlt, fortgeschrieben from meta.lauf where status in ('fertig','unveraendert') order by lieferung, id desc" \
  > "$HIER/laeufe.tsv"
echo "laeufe=$(wc -l < "$HIER/laeufe.tsv")"
echo "== ende"
