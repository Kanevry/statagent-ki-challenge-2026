#!/usr/bin/env bash
# Kopie der Abgabe-DB für die Live-Änderung in der Vorführung (Lead 05.11.2026): Die Vorführ-App schreibt in die Kopie,
# die Abgabe-DB bleibt unberührt und nachrechenbar. Läuft auf dem Rechner mit der Rechen-Datenbank (Docker-Container mit
# PostgreSQL 16), nie gegen die Online-Demo.
#
#   scripts/vorfuehrung-db.sh [--container NAME] [--ersetzen] QUELLE ZIEL
#
# QUELLE wird nur gelesen. ZIEL heißt statistik_vorfuehrung (Proben: statistik_vorfuehrung_<x>) und darf nicht existieren;
# mit --ersetzen wird nur ZIEL vorher gelöscht. Zuerst CREATE DATABASE … TEMPLATE (schnell, braucht eine QUELLE ohne Verbindungen), sonst pg_dump | pg_restore.
# Danach gleicher Inhalts-Hash für stat und meta in QUELLE und ZIEL, sonst Exit 1.
set -euo pipefail

container=statagent-db
ersetzen=0
while [[ ${1:-} == --* ]]; do
  case $1 in
    --container) container=${2:?--container braucht einen Namen}; shift 2 ;;
    --ersetzen) ersetzen=1; shift ;;
    *) echo "unbekannte Option: $1" >&2; exit 2 ;;
  esac
done
quelle=${1:?QUELLE fehlt (z. B. statistik)}
ziel=${2:?ZIEL fehlt (z. B. statistik_vorfuehrung)}
for n in "$quelle" "$ziel"; do
  [[ $n =~ ^[a-z][a-z0-9_]{0,62}$ ]] || { echo "ungültiger Name: $n" >&2; exit 2; }
done
[[ $quelle != "$ziel" ]] || { echo "QUELLE und ZIEL sind gleich" >&2; exit 2; }
# --ersetzen löscht ZIEL: nur die Vorführ-Kopie (und Proben davon) sind erlaubt, nie eine echte Datenbank
[[ $ziel =~ ^statistik_vorfuehrung(_[a-z0-9]+)?$ ]] ||
  { echo "ZIEL muss statistik_vorfuehrung heißen (Proben: statistik_vorfuehrung_<x>), nicht $ziel" >&2; exit 2; }
command -v docker >/dev/null || PATH=/usr/local/bin:/opt/homebrew/bin:$PATH

psql() { docker exec -i "$container" psql -X -q -At -v ON_ERROR_STOP=1 -U statistik "$@"; }
gibt_es() { [[ $(psql -d postgres -c "select count(*) from pg_database where datname = '$1'") == 1 ]]; }

start=$SECONDS
gibt_es "$quelle" || { echo "vorfuehrung-db: QUELLE $quelle gibt es nicht" >&2; exit 1; }
if gibt_es "$ziel"; then
  if [[ $ersetzen != 1 ]]; then echo "vorfuehrung-db: $ziel gibt es schon (mit --ersetzen neu anlegen)" >&2; exit 1; fi
  psql -d postgres -c "select pg_terminate_backend(pid) from pg_stat_activity where datname = '$ziel'" >/dev/null
  psql -d postgres -c "drop database $ziel"
  echo "vorfuehrung-db: alte $ziel gelöscht"
fi

if psql -d postgres -c "create database $ziel template $quelle" 2>/dev/null; then
  echo "vorfuehrung-db: $ziel als Template-Kopie von $quelle angelegt"
else
  echo "vorfuehrung-db: Template-Kopie geht nicht (Verbindungen auf $quelle), kopiere per pg_dump | pg_restore"
  psql -d postgres -c "create database $ziel"
  if ! docker exec "$container" sh -c "pg_dump -U statistik -Fc -d $quelle | pg_restore -U statistik -d $ziel --no-owner --exit-on-error"; then
    echo "vorfuehrung-db: Kopie gescheitert, $ziel bleibt unvollständig; mit --ersetzen neu anlegen" >&2
    exit 1
  fi
fi

# Gegenprobe: dieselben Zahlen in stat und meta (deploy/sql/inhaltshash.sql, über stdin in den Container)
hash_sql="$(dirname "${BASH_SOURCE[0]}")/../deploy/sql/inhaltshash.sql"
for schema in stat meta; do
  a=$(psql -d "$quelle" -v schema="$schema" -f - <"$hash_sql" | grep GESAMT)
  b=$(psql -d "$ziel" -v schema="$schema" -f - <"$hash_sql" | grep GESAMT)
  if [[ $a != "$b" ]]; then
    echo "vorfuehrung-db: $schema weicht ab ($quelle: $a, $ziel: $b)" >&2
    exit 1
  fi
  echo "vorfuehrung-db: $schema gleich ($a)"
done
echo "vorfuehrung-db: $ziel fertig, $(psql -d "$ziel" -c "select count(*) from meta.lauf") Läufe, $(psql -d postgres -c "select pg_size_pretty(pg_database_size('$ziel'))"), $((SECONDS - start)) s"
