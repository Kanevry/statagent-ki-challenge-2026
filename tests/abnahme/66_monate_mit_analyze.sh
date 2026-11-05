#!/usr/bin/env bash
# Abnahme #66: alle Monatsläufe einzeln, vor jedem Lauf ANALYZE auf bereinigt.abschnitt.
# Zweck: Gegenprobe zum Befund „lauf --alle hängt auf frischer DB“ (veraltete Planer-Statistik).
# Nur auf der eigenen Prüf-Datenbank (abnahme.env), nie auf einer Bau-Datenbank.
set -euo pipefail
HIER="$(cd "$(dirname "$0")" && pwd)"
# shellcheck source=/dev/null
. "$HIER/abnahme.env"
PORT="${ABNAHME_DB_PORT:-5444}"
CONTAINER="${ABNAHME_CONTAINER:-kic-abnahme-db}"
export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"
export UC3_DATABASE_URL="postgresql://statistik:statistik@localhost:${PORT}/statistik"
export STATAGENT_STARTPAKET="$STARTPAKET_UC3"
if [ "$CONTAINER" = "statagent-db" ]; then echo "Abbruch: Bau-Datenbank" >&2; exit 2; fi
von="${1:-2024-08}"
bis="${2:-2026-07}"
monat="$von"
while :; do
  docker exec "$CONTAINER" psql -U statistik -d statistik -q -c "ANALYZE bereinigt.abschnitt"
  start=$(date +%s)
  zeile=$(cd "$ABNAHME_REPO" && uv run uc3 lauf --lieferung "$monat" 2>&1 | tail -1)
  echo "$monat dauer_s=$(( $(date +%s) - start )) ${zeile:0:150}"
  [ "$monat" = "$bis" ] && break
  jahr=${monat%-*}; mon=$((10#${monat#*-} + 1))
  if [ "$mon" -gt 12 ]; then mon=1; jahr=$((jahr + 1)); fi
  monat=$(printf '%04d-%02d' "$jahr" "$mon")
done
