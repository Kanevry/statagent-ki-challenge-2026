#!/usr/bin/env bash
# Baut die kleine Nachlade-Datei für Klassifikationen unter dem Abschnitt und dem Bundesland (#189), für Datenbanken,
# die vor !193 geladen wurden: ÖNACE 2008 und 2025 Ebenen 2 bis 5, Bezirke und Gemeinden je Stand, Übergänge der
# Gemeinden und Bezirke. Keine Rohdaten, keine Läufe, keine Zählung, kein Regelstand; nur öffentliche Nachschlagedaten.
#
#   uc3/db/klass_online.sh [--container NAME] QUELLE ZIELORDNER      Quelle im Docker-Container
#   uc3/db/klass_online.sh --url ADRESSE QUELLE ZIELORDNER            Quelle über psql, ADRESSE ohne Datenbanknamen
#                                                                     (postgres://nutzer:passwort@rechner:port)
#
# QUELLE (eine Datenbank mit geladenen Klassifikationen) wird nur gelesen. Sie entsteht auch ohne Rechen-Datenbank aus dem
# Startpaket: leere Datenbank anlegen, dann statagent.db.schema_einrichten. Ergebnis, gleich bei gleichen Daten:
#   klass-online.sql.gz, .sha256      für `scripts/deploy.sh daten DB klass-online.sql.gz` (Transaktion kommt von dort;
#                                     von Hand: psql --single-transaction). Ersetzt nur diese Zeilen, mehrfach einspielbar.
#                                     Stimmt am Ende ein Prüfwert nicht, bricht sie ab und nichts bleibt.
#   klass-online-rueckweg.sql.gz      nimmt genau diese Zeilen wieder heraus.
set -euo pipefail

container=statagent-db
url=""
if [[ ${1:-} == --container ]]; then container=${2:?--container braucht einen Namen}; shift 2; fi
if [[ ${1:-} == --url ]]; then url=${2:?--url braucht eine Adresse}; shift 2; fi
quelle=${1:?QUELLE fehlt}
ziel=${2:?ZIELORDNER fehlt}
[[ $quelle =~ ^[a-z][a-z0-9_]{0,62}$ ]] || { echo "ungültiger Name: $quelle" >&2; exit 2; }
command -v docker >/dev/null || PATH=/usr/local/bin:/opt/homebrew/bin:$PATH
mkdir -p "$ziel"

psql_q() {
  if [[ -n $url ]]; then
    psql "$url/$quelle" -X -q -At -v ON_ERROR_STOP=1 "$@"
  else
    docker exec -i "$container" psql -X -q -At -v ON_ERROR_STOP=1 -U statistik -d "$quelle" "$@"
  fi
}
# Feste Sortierung mit COLLATE "C": gleiche Daten ergeben auf jedem Rechner dieselbe Datei.
SP_OENACE='version, code, bezeichnung, ebene, uebergeordnet, gueltig_von, gueltig_bis'
SP_REGION='version, code, bezeichnung, ebene, uebergeordnet, gueltig_von, gueltig_bis'
SP_UEB='klassifikation, version_alt, code_alt, version_neu, code_neu, beziehung, gueltig_ab, quelle'
W_OENACE="version IN ('2008', '2025') AND ebene >= 2"
W_REGION="ebene IN ('bezirk', 'gemeinde')"
W_UEB="klassifikation IN ('gemeinde', 'bezirk')"

zahl() { psql_q -c "$1"; }
o2008=$(zahl "select string_agg(n::text, '/' order by ebene) from (select ebene, count(*) n from stat.klass_oenace where version = '2008' and ebene >= 2 group by 1) x")
o2025=$(zahl "select string_agg(n::text, '/' order by ebene) from (select ebene, count(*) n from stat.klass_oenace where version = '2025' and ebene >= 2 group by 1) x")
n_oenace=$(zahl "select count(*) from stat.klass_oenace where $W_OENACE")
n_region=$(zahl "select count(*) from stat.klass_region where $W_REGION")
n_staende=$(zahl "select count(distinct version) from stat.klass_region where $W_REGION")
n_ueb=$(zahl "select count(*) from stat.uebergang where $W_UEB")
[[ $n_oenace -gt 0 && $n_region -gt 0 && $n_ueb -gt 0 ]] || { echo "klass_online: in $quelle fehlen Klassifikationen" >&2; exit 1; }

datei="$ziel/klass-online.sql"
{
  cat <<SQL
-- Klassifikationen unter Abschnitt und Bundesland (#189). Ersetzt nur diese Zeilen; Ebene 1, Bundesländer,
-- ÖNACE-Übergänge, Pensionen, Läufe, Regeln und alles andere bleiben unberührt. Transaktion: scripts/deploy.sh daten.
DO \$\$
BEGIN
  IF (SELECT count(*) FROM stat.klass_oenace WHERE ebene = 1 AND version IN ('2008', '2025')) = 0 THEN
    RAISE EXCEPTION 'klass-online: die Abschnitte fehlen, das ist nicht die erwartete Datenbank';
  END IF;
END
\$\$;
DELETE FROM stat.klass_oenace WHERE $W_OENACE;
DELETE FROM stat.klass_region WHERE $W_REGION;
DELETE FROM stat.uebergang WHERE $W_UEB;
COPY stat.klass_oenace ($SP_OENACE) FROM stdin;
SQL
  psql_q -c "COPY (SELECT $SP_OENACE FROM stat.klass_oenace WHERE $W_OENACE ORDER BY version COLLATE \"C\", code COLLATE \"C\") TO STDOUT"
  printf '\\.\nCOPY stat.klass_region (%s) FROM stdin;\n' "$SP_REGION"
  psql_q -c "COPY (SELECT $SP_REGION FROM stat.klass_region WHERE $W_REGION ORDER BY version COLLATE \"C\", code COLLATE \"C\") TO STDOUT"
  printf '\\.\nCOPY stat.uebergang (%s) FROM stdin;\n' "$SP_UEB"
  psql_q -c "COPY (SELECT $SP_UEB FROM stat.uebergang WHERE $W_UEB ORDER BY klassifikation COLLATE \"C\", version_alt COLLATE \"C\", code_alt COLLATE \"C\", version_neu COLLATE \"C\", code_neu COLLATE \"C\") TO STDOUT"
  printf '\\.\n'
  cat <<SQL
-- Prüfwerte, im selben Lauf gemessen: Weicht einer ab, bricht die Transaktion ab und nichts bleibt.
DO \$\$
DECLARE
  o2008 text; o2025 text; region int; staende int; ueb int;
BEGIN
  SELECT string_agg(n::text, '/' ORDER BY ebene) INTO o2008 FROM (SELECT ebene, count(*) n FROM stat.klass_oenace WHERE version = '2008' AND ebene >= 2 GROUP BY 1) x;
  SELECT string_agg(n::text, '/' ORDER BY ebene) INTO o2025 FROM (SELECT ebene, count(*) n FROM stat.klass_oenace WHERE version = '2025' AND ebene >= 2 GROUP BY 1) x;
  SELECT count(*), count(DISTINCT version) INTO region, staende FROM stat.klass_region WHERE $W_REGION;
  SELECT count(*) INTO ueb FROM stat.uebergang WHERE $W_UEB;
  IF o2008 IS DISTINCT FROM '$o2008' OR o2025 IS DISTINCT FROM '$o2025' OR region <> $n_region OR staende <> $n_staende OR ueb <> $n_ueb THEN
    RAISE EXCEPTION 'klass-online: Prüfwerte weichen ab: 2008 %, 2025 %, Region %, Stände %, Übergänge %', o2008, o2025, region, staende, ueb;
  END IF;
END
\$\$;
SQL
} >"$datei"
gzip -n -9 -f "$datei"
cat >"$ziel/klass-online-rueckweg.sql" <<SQL
-- Nimmt genau die Zeilen von klass-online.sql.gz wieder heraus.
DELETE FROM stat.klass_oenace WHERE $W_OENACE;
DELETE FROM stat.klass_region WHERE $W_REGION;
DELETE FROM stat.uebergang WHERE $W_UEB;
SQL
gzip -n -9 -f "$ziel/klass-online-rueckweg.sql"
( cd "$ziel" && for f in klass-online.sql.gz klass-online-rueckweg.sql.gz; do shasum -a 256 "$f" 2>/dev/null >"$f.sha256" || sha256sum "$f" >"$f.sha256"; done )
echo "klass_online: aus $quelle: ÖNACE 2008 $o2008, ÖNACE 2025 $o2025, Region $n_region Zeilen in $n_staende Ständen, Übergänge $n_ueb"
cat "$ziel/klass-online.sql.gz.sha256" "$ziel/klass-online-rueckweg.sql.gz.sha256"
ls -l "$ziel" | awk '{print $5, $9}'
