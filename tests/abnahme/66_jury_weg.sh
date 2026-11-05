#!/usr/bin/env bash
# Abnahme #66 (EA-4) Jury-Weg: frische Datenbank, Golden Set 08/2024, Determinismus.
#
# Nur messen: das Skript startet eine EIGENE Datenbank (eigenes Compose-Projekt, eigener
# Containername, eigener Port) und rührt eine laufende Bau-Datenbank nicht an.
#
# Aufruf auf dem Prüfrechner:  bash 66_jury_weg.sh <schritt>
# Schritte: frisch | sync | init | lauf | eichen | laeufe | hash | goldenset | provider <name> | ab
#
# Konfiguration in abnahme.env neben diesem Skript (nicht im Repo, Beispiel: abnahme.env.example):
#   ABNAHME_REPO        Checkout des zu prüfenden Stands (Kopf des MR)
#   STARTPAKET_UC3      Startpaket-Ordner uc3/ (docker-compose.yml, Beispielbericht)
#   ABNAHME_PROJEKT     Compose-Projektname, Standard kic-abnahme
#   ABNAHME_DB_PORT     Port der Prüf-Datenbank, Standard 5444 (5433 Bau-DB, 5434 oft ein natives Postgres)
#   ABNAHME_CONTAINER   Containername aus compose-abnahme.override.yml, Standard kic-abnahme-db
set -euo pipefail

HIER="$(cd "$(dirname "$0")" && pwd)"
# shellcheck source=/dev/null
. "$HIER/abnahme.env"
: "${ABNAHME_REPO:?ABNAHME_REPO fehlt}" "${STARTPAKET_UC3:?STARTPAKET_UC3 fehlt}"
PROJEKT="${ABNAHME_PROJEKT:-kic-abnahme}"
PORT="${ABNAHME_DB_PORT:-5444}"
CONTAINER="${ABNAHME_CONTAINER:-kic-abnahme-db}"
export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"
export UC3_DATABASE_URL="postgresql://statistik:statistik@localhost:${PORT}/statistik"
export STATAGENT_STARTPAKET="$STARTPAKET_UC3"
export STATAGENT_ABGABE="$HIER/abgabe"

if [ "$PROJEKT" = "statagent" ] || [ "$CONTAINER" = "statagent-db" ]; then
  echo "Abbruch: Projekt oder Container der Bau-Datenbank, die Abnahme nutzt eine eigene." >&2
  exit 2
fi

compose() {
  (cd "$STARTPAKET_UC3" && DB_PORT="$PORT" docker compose -p "$PROJEKT" \
    -f docker-compose.yml -f "$HIER/compose-abnahme.override.yml" "$@")
}

zeit() { TZ=Europe/Vienna date '+%Y-%m-%dT%H:%M:%S%z'; }

# Harte Zielprüfung (Review !56): Bevor ein Schritt über UC3_DATABASE_URL arbeitet, muss diese Adresse genau den
# Abnahme-Container erreichen. Geprüft werden Compose-Projekt und veröffentlichter Port des Containers sowie der
# system_identifier des Clusters, einmal im Container und einmal über die URL gelesen. Sonst Abbruch mit Exit 3.
ziel_pruefen() {
  local projekt_ist port_ist id_container id_url
  if ! projekt_ist=$(docker inspect -f '{{index .Config.Labels "com.docker.compose.project"}}' "$CONTAINER" 2>/dev/null); then
    echo "Abbruch: Container $CONTAINER läuft nicht." >&2
    exit 3
  fi
  if [ "$projekt_ist" != "$PROJEKT" ]; then
    echo "Abbruch: $CONTAINER gehört zu Projekt '$projekt_ist', erwartet $PROJEKT." >&2
    exit 3
  fi
  port_ist=$(docker port "$CONTAINER" 5432/tcp 2>/dev/null | sed -n 's/.*:\([0-9][0-9]*\)$/\1/p' | head -1)
  if [ "$port_ist" != "$PORT" ]; then
    echo "Abbruch: $CONTAINER veröffentlicht Port '$port_ist', erwartet $PORT." >&2
    exit 3
  fi
  id_container=$(docker exec "$CONTAINER" psql -U statistik -d statistik -At \
    -c "select system_identifier from pg_control_system()")
  id_url=$(cd "$ABNAHME_REPO" && uv run python - <<'PY'
import os

import psycopg

with psycopg.connect(os.environ["UC3_DATABASE_URL"], connect_timeout=5) as verbindung:
    print(verbindung.execute("select system_identifier from pg_control_system()").fetchone()[0])
PY
  )
  if [ -z "$id_container" ] || [ "$id_container" != "$id_url" ]; then
    echo "Abbruch: $UC3_DATABASE_URL erreicht nicht $CONTAINER (Cluster '$id_url' statt '$id_container')." >&2
    exit 3
  fi
  echo "ziel ok: $CONTAINER, Projekt $PROJEKT, Port $PORT"
}

schritt="${1:?Schritt fehlt: frisch|ziel|sync|init|lauf|eichen|laeufe|hash|goldenset|provider|ab}"
echo "== $schritt $(zeit)"
case "$schritt" in
  init|lauf|eichen|laeufe|goldenset|provider) ziel_pruefen ;;
esac
case "$schritt" in
  ziel)
    ziel_pruefen
    ;;
  frisch)
    compose down -v 2>&1 | tail -3
    start=$(date +%s)
    compose up -d 2>&1 | tail -3
    # Wartet, bis die Init-Skripte fertig sind und Postgres neu gestartet hat: die Meldung
    # „ready to accept connections“ kommt einmal vom Init-Server und einmal vom echten Server.
    # grep -c liest die ganze Ausgabe (grep -q würde die Pipe abbrechen, pipefail meldet das als Fehler).
    for _ in $(seq 1 120); do
      bereit=$(docker logs "$CONTAINER" 2>&1 | grep -c 'database system is ready to accept connections' || true)
      if [ "${bereit:-0}" -ge 2 ]; then
        break
      fi
      sleep 5
    done
    if [ "${bereit:-0}" -lt 2 ]; then
      echo "Abbruch: $CONTAINER ist nach 10 Minuten nicht bereit." >&2
      exit 4
    fi
    echo "dauer_s=$(( $(date +%s) - start ))"
    docker logs -t "$CONTAINER" 2>&1 | sed -n '1p;/ready to accept connections/p' | cut -c1-30
    docker logs "$CONTAINER" 2>&1 | grep -i -E "fertig|error|fatal" | tail -5 || true
    docker exec "$CONTAINER" psql -U statistik -d statistik -At \
      -c "select 'roh.lieferung', count(*) from roh.lieferung"
    ;;
  sync)
    (cd "$ABNAHME_REPO" && uv sync --all-packages 2>&1 | tail -3)
    ;;
  init)
    (cd "$ABNAHME_REPO" && uv run uc3 db init --json)
    ;;
  lauf)
    (cd "$ABNAHME_REPO" && uv run python "$HIER/66_ohne_netz.py" lauf --lieferung 2024-08)
    ;;
  eichen)
    (cd "$ABNAHME_REPO" && uv run uc3 eichen --lieferung 2024-08)
    ;;
  laeufe)
    (cd "$ABNAHME_REPO" && uv run uc3 laeufe --json)
    ;;
  hash)
    docker exec -i "$CONTAINER" psql -U statistik -d statistik -At -v ON_ERROR_STOP=1 \
      < "$HIER/66_kanon_hash.sql"
    ;;
  goldenset)
    # Der dokumentierte Test aus uc3/README.md (rechnet in einer Transaktion und rollt zurück).
    (cd "$ABNAHME_REPO" && uv run pytest -q -m daten uc3/tests/test_goldenset.py 2>&1 | tail -5)
    ;;
  provider)
    # #63 Zusatz: derselbe Lauf mit einem anderen Modell-Provider in der Umgebung.
    anbieter="${2:?Provider fehlt: azure|mistral|mock}"
    (cd "$ABNAHME_REPO" && LLM_PROVIDER="$anbieter" uv run uc3 lauf --lieferung 2024-08 --json)
    ;;
  ab)
    compose down -v 2>&1 | tail -3
    ;;
  *)
    echo "unbekannter Schritt: $schritt" >&2
    exit 2
    ;;
esac
