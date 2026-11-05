#!/usr/bin/env bash
# Deploy der KI-Challenge-Demo auf den Demo-Server, Issue #68.
#
#   scripts/deploy.sh init      .env.server auf dem Server anlegen und die Datenbank-Passwörter erzeugen (idempotent)
#   scripts/deploy.sh up        HEAD per git archive packen, in ein eigenes <basis>/neu-*-Verzeichnis rsyncen, dort
#                               Compose und Caddyfile prüfen und das App-Image bauen, erst dann nach <basis>/repo
#                               übernehmen, docker compose up --wait, Caddy neu laden; ein Deploy zur Zeit (flock)
#   scripts/deploy.sh rechte    Rolle kic_app (nur lesen) anlegen und in jeder App-Datenbank berechtigen; läuft auch
#                               nach up und daten
#   scripts/deploy.sh pruefen   von außen: http leitet auf https um, 200, Sicherheits-Header, 404 für Unbekanntes,
#                               POST abgewiesen; auf dem Server: alle Container healthy
#   scripts/deploy.sh status    Container, ausgelieferte Revision, letzte Caddy-Logzeilen
#   scripts/deploy.sh bauprobe REF   App-Image eines Branches mit dem eigenen deploy/ auf dem Server bauen und
#                               in einem Wegwerf-Container ohne Netz anstarten (vor einem Merge)
#   scripts/deploy.sh daten DB DATEI     Dump aus <basis>/daten/DATEI (pg_dump -Fc .dump oder SQL .sql.gz) in die
#                               Datenbank DB, in einer Transaktion; sichert DB vorher (Rückweg: daten DB sicherung/…)
#   scripts/deploy.sh sichern [DB]       pg_dump -Fc je DB (ohne DB: alle) nach <basis>/daten/sicherung/, mit sha256,
#                               die letzten 5 je DB bleiben
#   scripts/deploy.sh inhaltshash DB SCHEMA   Inhalts-Hash wie lokal (deploy/sql/inhaltshash.sql)
#   scripts/deploy.sh           up, dann pruefen
#
# Ziel ohne Default im Repo: DEPLOY_HOST (SSH-Alias), DEPLOY_BASIS (Basisordner auf dem Server), DEPLOY_DOMAIN
# (öffentliche Adresse) aus der Umgebung, sonst aus DEPLOY_KONFIG (Standard ~/.config/ki-challenge/deploy.env).
# Geheimnisse liegen nur in <basis>/.env.server auf dem Server; das Skript gibt keine Werte aus.
# Ausgeliefert wird immer der committete Stand (HEAD), nie ungetrackte Dateien wie .env.local.
set -euo pipefail

REPO_ROOT="$(git -C "$(dirname "${BASH_SOURCE[0]}")" rev-parse --show-toplevel)"
SSH_OPTS=(-o ConnectTimeout=10 -o BatchMode=yes)
TMP_DIR=""
HOST="" BASIS="" DOMAIN="" ENV_DATEI=""

lade_ziel() {
  local konfig=${DEPLOY_KONFIG:-$HOME/.config/ki-challenge/deploy.env} k v
  if [[ -f $konfig ]]; then
    # nur fehlende Werte ergänzen: gesetzte Umgebung (etwa im CI-Job) gewinnt
    while IFS='=' read -r k v; do
      if [[ -z ${!k:-} ]]; then printf -v "$k" '%s' "$v"; fi
    done < <(grep -E '^DEPLOY_(HOST|BASIS|DOMAIN)=' "$konfig")
  fi
  HOST=${DEPLOY_HOST:?DEPLOY_HOST fehlt (Umgebung oder $konfig)}
  BASIS=${DEPLOY_BASIS:?DEPLOY_BASIS fehlt (Umgebung oder $konfig)}
  DOMAIN=${DEPLOY_DOMAIN:?DEPLOY_DOMAIN fehlt (Umgebung oder $konfig)}
  # die Werte gehen in Remote-Befehle: nur einfache Formen zulassen
  [[ $HOST =~ ^[A-Za-z0-9._-]+$ ]] || { echo "DEPLOY_HOST ungültig" >&2; exit 2; }
  [[ $BASIS =~ ^/[A-Za-z0-9._/-]+$ && $BASIS != *..* ]] || { echo "DEPLOY_BASIS ungültig" >&2; exit 2; }
  [[ $DOMAIN =~ ^[a-z0-9.-]+$ ]] || { echo "DEPLOY_DOMAIN ungültig" >&2; exit 2; }
  ENV_DATEI=$BASIS/.env.server
}

remote() { ssh "${SSH_OPTS[@]}" "$HOST" "$@"; }
aufraeumen() { if [[ -n "$TMP_DIR" ]]; then rm -rf "$TMP_DIR"; fi; }
trap aufraeumen EXIT

cmd_init() {
  remote bash -s -- "$BASIS" "$ENV_DATEI" <<'EOF'
set -euo pipefail
basis=$1 datei=$2
umask 077
mkdir -p "$basis/daten"
touch "$datei"
chmod 600 "$datei"
# Datenbank-Passwörter, nur intern: POSTGRES_PASSWORD (Superuser statistik, nur Admin) und KIC_APP_DB_PASSWORD
# (Rolle kic_app der App, nur lesend). Einmal erzeugt, nie überschrieben, weil das db-Volume den ersten Wert behält;
# eine Zeile in unerwarteter Form wird nicht still ersetzt.
for name in POSTGRES_PASSWORD KIC_APP_DB_PASSWORD; do
  if grep -q "^$name=." "$datei"; then
    if grep -q "^$name='[A-Za-z0-9]\{32\}'$" "$datei"; then
      echo "init: $name vorhanden, unverändert"
    else
      echo "init: $name in .env.server hat eine unerwartete Form, nichts geändert" >&2
      exit 1
    fi
  else
    sed -i "/^$name=/d" "$datei"
    pw=$(openssl rand 512 | LC_ALL=C tr -dc 'A-Za-z0-9')
    if [ "${#pw}" -lt 32 ]; then echo "init: Zufall zu kurz, nichts geschrieben" >&2; exit 1; fi
    printf "%s='%s'\n" "$name" "${pw:0:32}" >>"$datei"
    echo "init: $name neu angelegt"
  fi
done
grep -q '^SITE_ADDRESS=.' "$datei" || echo "init: SITE_ADDRESS fehlt noch in .env.server (öffentliche Adresse)" >&2
echo "init: .env.server Modus $(stat -c %a "$datei")"
EOF
}

cmd_up() {
  cd "$REPO_ROOT"
  local rev rc=0
  rev=$(git rev-parse HEAD)
  if [[ -n "$(git status --porcelain --untracked-files=no)" ]]; then
    echo "up: uncommittete Änderungen werden nicht ausgeliefert, nur HEAD ${rev:0:8}" >&2
  fi
  remote "test -s $ENV_DATEI" || rc=$?
  if ((rc == 255)); then
    echo "up: Server per SSH nicht erreichbar" >&2
    exit 1
  elif ((rc != 0)); then
    echo "up: .env.server fehlt auf dem Server, zuerst scripts/deploy.sh init" >&2
    exit 1
  fi

  TMP_DIR=$(mktemp -d)
  git archive --format=tar HEAD | tar -x -C "$TMP_DIR"
  printf '%s\n' "$rev" >"$TMP_DIR/REVISION"
  chmod 755 "$TMP_DIR"

  # eigenes Verzeichnis je Deploy: zwei gleichzeitige Deploys (Rechner und CI) überschreiben sich nicht
  local neu="$BASIS/neu-${rev:0:12}-$$"
  remote "mkdir -p $BASIS/repo $BASIS/daten $neu"
  rsync -az --delete --no-owner --no-group -e "ssh ${SSH_OPTS[*]}" "$TMP_DIR/" "$HOST:$neu/"
  echo "up: Revision ${rev:0:8} übertragen"

  # Das Skript kommt über stdin (bash -s). Als Funktion wird es ganz gelesen, bevor etwas läuft, und jeder
  # docker-Aufruf bekommt </dev/null: sonst liest "compose run" den Rest des Skripts als Eingabe weg.
  remote bash -s -- "$BASIS" "$ENV_DATEI" "$neu" <<'EOF'
haupt() {
  set -euo pipefail
  local basis=$1 env_datei=$2 neu=$3
  local compose=(docker compose --env-file "$env_datei" -f docker-compose.prod.yml)
  # global, weil der EXIT-Trap nach dem Ende von haupt läuft, wenn die lokalen Variablen weg sind
  NEU_VERZ=$neu
  trap 'rm -rf "$NEU_VERZ"' EXIT
  # ein Deploy zur Zeit
  exec 9>"$basis/.deploy.lock"
  flock -w 300 9 || { echo "up: ein anderer Deploy läuft seit über 5 Minuten" >&2; return 1; }
  # 0. Geld (#108b): ein Modell- oder Voice-Schlüssel wirkt online nur mit Ratenlimit und Tagesbudget als ganzer
  #    Zahl ab 1. Sonst bricht up ab, bevor sich etwas ändert. Werte werden nur geprüft, nie ausgegeben.
  #    Gelesen wie Compose: die letzte Zeile gewinnt, auch in der Form "export NAME=…".
  local name schluessel="" wert
  wert_von() { sed -nE "s/^[[:space:]]*(export[[:space:]]+)?$1=//p" "$env_datei" | tail -n 1 | tr -d "\"'[:space:]"; }
  for name in AZURE_API_KEY MISTRAL_API_KEY VAPI_API_KEY VAPI_CUSTOM_LLM_KEY; do
    wert=$(wert_von "$name")
    if [ -n "$wert" ]; then schluessel="$schluessel $name"; fi
  done
  wert=""
  if [ -n "$schluessel" ]; then
    for name in RATENLIMIT_PRO_MINUTE LLM_TAGESBUDGET_AUFRUFE; do
      if ! wert_von "$name" | grep -Eq '^[1-9][0-9]*$'; then
        echo "up: Schlüssel gesetzt ($schluessel ), aber $name fehlt oder ist keine ganze Zahl ab 1; nichts geändert" >&2
        return 1
      fi
    done
  fi
  # 1. neuen Stand prüfen und das App-Image bauen; die laufenden Ordner in repo/ bleiben bis dahin unberührt
  cd "$neu/deploy"
  "${compose[@]}" config --quiet </dev/null
  "${compose[@]}" run --rm --no-deps -T caddy caddy validate --config /etc/caddy/Caddyfile --adapter caddyfile </dev/null
  "${compose[@]}" build </dev/null
  # 2. erst nach bestandener Prüfung übernehmen; REVISION erst, wenn alles läuft
  rsync -a --delete --exclude /REVISION "$neu/" "$basis/repo/"
  cd "$basis/repo/deploy"
  local vorher nachher
  vorher=$("${compose[@]}" ps -q caddy </dev/null)
  "${compose[@]}" up -d --no-build --remove-orphans --wait --wait-timeout 180 </dev/null
  nachher=$("${compose[@]}" ps -q caddy </dev/null)
  # Container blieb derselbe (nur Dateien geändert): Caddyfile ohne Neustart übernehmen
  if [ -n "$vorher" ] && [ "$vorher" = "$nachher" ]; then
    "${compose[@]}" exec -T caddy caddy reload --config /etc/caddy/Caddyfile --adapter caddyfile </dev/null
    echo "up: Caddy neu geladen"
  fi
  cp "$neu/REVISION" "$basis/repo/REVISION"
  "${compose[@]}" ps --format 'table {{.Service}}\t{{.Status}}' </dev/null
  # Platte: jeder Build lässt Cache und ein namenloses Image zurück (05.11.: 14 GB Cache). Der Cache der letzten
  # 48 Stunden bleibt für schnelle Builds; ein Fehler hier bricht den fertigen Deploy nicht ab.
  docker builder prune -f --filter until=48h </dev/null >/dev/null 2>&1 || echo "up: Build-Cache nicht aufgeräumt" >&2
  docker image prune -f </dev/null >/dev/null 2>&1 || echo "up: namenlose Images nicht aufgeräumt" >&2
  echo "up: Platte $(df -h --output=avail "$basis" | tail -n 1 | tr -d ' ') frei"
}
haupt "$@"
EOF
  cmd_rechte
}

cmd_rechte() {
  # Rolle kic_app anlegen oder angleichen, Leserechte in jeder App-Datenbank setzen, dann als kic_app gegenprüfen
  remote bash -s -- "$BASIS" "$ENV_DATEI" <<'EOF'
haupt() {
  set -euo pipefail
  cd "$1/repo/deploy"
  local compose=(docker compose --env-file "$2" -f docker-compose.prod.yml)
  local psql=("${compose[@]}" exec -T db psql -X -q -At -U statistik)
  "${psql[@]}" -d statistik -f /deploy-sql/app-rolle.sql </dev/null
  local pw
  pw=$(sed -n "s/^KIC_APP_DB_PASSWORD='\([A-Za-z0-9]\{32\}\)'$/\1/p" "$2" | tail -n 1)
  [ -n "$pw" ] || { echo "rechte: KIC_APP_DB_PASSWORD fehlt, zuerst scripts/deploy.sh init" >&2; return 1; }
  # Passwort über stdin, nie als Argument
  printf "alter role kic_app password '%s';\n" "$pw" | "${psql[@]}" -d statistik
  local db datenbanken
  datenbanken=$("${psql[@]}" -d statistik -c "select datname from pg_database where not datistemplate and datname <> 'postgres' order by 1" </dev/null)
  for db in $datenbanken; do
    "${psql[@]}" -d "$db" -f /deploy-sql/app-rechte.sql </dev/null
  done
  # Gegenprobe als kic_app über TCP; PGPASSWORD geht als Umgebung in den Container, nicht als Argument
  export PGPASSWORD=$pw
  local als_app=("${compose[@]}" exec -T -e PGPASSWORD db psql -X -q -At -h 127.0.0.1 -U kic_app)
  "${als_app[@]}" -d statistik -c "select 'rechte: kic_app angemeldet, superuser=' || rolsuper || ', default_transaction_read_only=' || current_setting('default_transaction_read_only') from pg_roles where rolname = current_user" </dev/null
  # je Datenbank als kic_app: Anlegen muss scheitern, auch mit read write (#108a); dann echtes Lesen der ersten
  # berechtigten Tabelle
  for db in $datenbanken; do
    # bestanden nur, wenn Postgres die Rechte verweigert; jeder andere Fehler (Tabelle schon da, Schema fehlt)
    # belegt nichts und bricht ab
    local probe sql
    for sql in "create table kic_probe (x int)" "begin; set transaction read write; create table public.kic_probe (x int); rollback;"; do
      if probe=$("${als_app[@]}" -d "$db" -c "$sql" </dev/null 2>&1); then
        echo "rechte $db: kic_app konnte eine Tabelle anlegen ($sql)" >&2
        return 1
      fi
      if ! printf '%s' "$probe" | grep -Eq 'permission denied|read-only transaction'; then
        echo "rechte $db: Probe nicht aussagekräftig: $probe" >&2
        return 1
      fi
    done
    "${als_app[@]}" -d "$db" -c "select 'rechte ' || current_database() || ': Anlegen abgewiesen, kic_app liest ' || coalesce((select table_schema || '.' || table_name || ' (' || (xpath('/row/n/text()', query_to_xml(format('select count(*) as n from %I.%I', table_schema, table_name), false, true, '')))[1]::text || ' Zeilen)' from information_schema.role_table_grants where grantee = 'kic_app' and privilege_type = 'SELECT' order by 1 limit 1), 'keine Tabelle vorhanden')" </dev/null
  done
  unset PGPASSWORD
}
haupt "$@"
EOF
}

cmd_pruefen() {
  local code kopf ort fehler=0
  # von außen über das öffentliche Netz; curl prüft dabei das Zertifikat (ungültig = Abbruch)
  if ! ort=$(curl -sS -o /dev/null -w '%{http_code} %{redirect_url}' --max-time 20 "http://$DOMAIN/"); then
    echo "pruefen: http://$DOMAIN nicht erreichbar" >&2
    return 1
  fi
  if [[ $ort == "308 https://$DOMAIN/" ]]; then echo "pruefen: http leitet auf https um (308)"; else echo "pruefen: http liefert '$ort' statt 308 auf https" >&2; fehler=1; fi

  if ! kopf=$(curl -sS -D - -o /dev/null --max-time 20 "https://$DOMAIN/"); then
    echo "pruefen: https://$DOMAIN nicht erreichbar oder Zertifikat ungültig" >&2
    return 1
  fi
  code=$(printf '%s' "$kopf" | head -n 1 | tr -d '\r' | awk '{print $2}')
  if [[ $code == 200 ]]; then echo "pruefen: https 200, Zertifikat gültig"; else echo "pruefen: https liefert $code statt 200" >&2; fehler=1; fi
  local h fehlt=0
  for h in 'strict-transport-security: max-age=' 'x-content-type-options: nosniff' 'x-frame-options: deny' 'x-robots-tag: noindex'; do
    if ! printf '%s' "$kopf" | tr -d '\r' | tr '[:upper:]' '[:lower:]' | grep -q "^$h"; then
      echo "pruefen: Header fehlt: $h" >&2
      fehlt=1
    fi
  done
  if [[ $fehlt == 0 ]]; then echo "pruefen: Sicherheits-Header vollständig"; else fehler=1; fi

  code=$(curl -sS -o /dev/null -w '%{http_code}' --max-time 20 "https://$DOMAIN/gibt-es-nicht-$RANDOM") || code=000
  if [[ $code == 404 ]]; then echo "pruefen: unbekannter Pfad 404"; else echo "pruefen: unbekannter Pfad liefert $code statt 404" >&2; fehler=1; fi

  # lesend: die schreibenden Wege prüft die Sperrliste unten (am Text der Caddy-Antwort, Review !94 und !103);
  # die Methodenmatrix der Kante ohne Server prüft deploy/methoden-matrix.sh im CI-Job deploy-check
  local pfad
  # Die zwei Frage-Wege (#150): POST kommt an der Kante vorbei (Antwort nicht der Satz von Caddy; ein leerer Body
  # endet in der App mit 400 oder 403, ohne Modellaufruf), PUT, DELETE und OPTIONS weist Caddy ab.
  local methode antwort
  for pfad in /api/uc3/frage /api/uc4/frage; do
    antwort=$(curl -sS --max-time 20 -X POST -H 'content-type: application/json' -d '{}' "https://$DOMAIN$pfad") || antwort=""
    if [[ $antwort == *"Die Online-Demo ist lesend."* ]]; then echo "pruefen: POST $pfad an der Kante gesperrt" >&2; fehler=1; else echo "pruefen: POST $pfad erreicht die App"; fi
    for methode in PUT DELETE OPTIONS; do
      code=$(curl -sS -o /dev/null -w '%{http_code}' --max-time 20 -X "$methode" "https://$DOMAIN$pfad") || code=000
      if [[ $code == 403 ]]; then echo "pruefen: $methode $pfad abgewiesen (403)"; else echo "pruefen: $methode $pfad liefert $code statt 403" >&2; fehler=1; fi
    done
  done

  # Voice aus heißt: kein Vapi-Schlüssel im Body (#108 b, Lead a7 05.11.). Mit dem öffentlichen Schlüssel könnte
  # jeder abgerechnete Anrufe starten, auch wenn der Sprechknopf aus ist.
  local voice
  voice=$(curl -sS --max-time 20 "https://$DOMAIN/api/plattform/voice-config") || voice=""
  if [[ $voice == *'"aktiv":true'* ]]; then
    echo "pruefen: Voice ist aktiv (Schlüssel wird ausgeliefert, nur nach Freigabe des Leads)"
  elif [[ $voice == *'"aktiv":false'* && $voice == *'"publicKey":null'* && $voice == *'"assistantId":null'* ]]; then
    echo "pruefen: Voice aus, kein Schlüssel ausgeliefert"
  else
    echo "pruefen: voice-config liefert bei Voice aus einen Schlüssel oder ist nicht lesbar" >&2
    fehler=1
  fi

  # auf dem Server: jeder Dienst läuft und meldet healthy
  local zustand
  if ! zustand=$(remote bash -s -- "$BASIS" "$ENV_DATEI" <<'EOF'
cd "$1/repo/deploy" && docker compose --env-file "$2" -f docker-compose.prod.yml ps --all --format '{{.Service}}={{.State}}/{{.Health}}' </dev/null
EOF
  ); then
    echo "pruefen: Containerzustand auf dem Server nicht lesbar" >&2
    return 1
  fi
  local zeile
  for zeile in $zustand; do
    if [[ $zeile == *=running/healthy ]]; then echo "pruefen: ${zeile%%=*} healthy"; else echo "pruefen: $zeile" >&2; fehler=1; fi
  done
  [[ -n $zustand ]] || { echo "pruefen: keine Container gefunden" >&2; fehler=1; }
  # UC2-Namensliste: Ist UC2_NAMENSLISTE gesetzt, muss am Host-Pfad eine nicht leere Datei liegen und im Container
  # als Datei ankommen. Fehlt sie, legt Docker still ein Verzeichnis an und UC2 zeigt Beispielbelege. Gemessen wird
  # nur die Zeilenzahl, nie der Inhalt (Lead a7, 05.11.).
  local namen
  namen=$(remote bash -s -- "$BASIS" "$ENV_DATEI" <<'EOF'
pfad=$(sed -n 's/^UC2_NAMENSLISTE=//p' "$2" | tail -1 | tr -d "'\"")
if [ -z "$pfad" ]; then echo leer; exit 0; fi
if [ ! -f "$pfad" ]; then echo fehlt; exit 0; fi
host=$(wc -l < "$pfad" | tr -d ' ')
im=$(cd "$1/repo/deploy" && docker compose --env-file "$2" -f docker-compose.prod.yml exec -T app \
  sh -c 'test -f /etc/kic/uc2-namensliste && wc -l < /etc/kic/uc2-namensliste' </dev/null | tr -d ' \r')
echo "host=$host container=${im:-0}"
EOF
  ) || namen=unlesbar
  local zeilen_host zeilen_app
  case $namen in
    leer) echo "pruefen: UC2_NAMENSLISTE nicht gesetzt, UC2 zeigt gekennzeichnete Beispielbelege" ;;
    host=*)
      zeilen_host=${namen#host=}
      zeilen_host=${zeilen_host%% *}
      zeilen_app=${namen##*container=}
      if [[ $zeilen_host == 0 ]]; then
        echo "pruefen: UC2-Namensliste auf dem Server ist leer" >&2
        fehler=1
      elif [[ $zeilen_host == "$zeilen_app" ]]; then
        echo "pruefen: UC2-Namensliste geladen ($zeilen_app Zeilen im Container)"
      else
        echo "pruefen: UC2-Namensliste kommt nicht im Container an (Server $zeilen_host, Container $zeilen_app Zeilen)" >&2
        fehler=1
      fi
      ;;
    *)
      echo "pruefen: UC2-Namensliste $namen (Pfad aus UC2_NAMENSLISTE prüfen)" >&2
      fehler=1
      ;;
  esac
  # die Seiten der Demo antworten
  local pfad
  for pfad in /uc1 /uc2 /uc3 /uc4 /praesentation; do
    code=$(curl -sS -o /dev/null -w '%{http_code}' --max-time 30 "https://$DOMAIN$pfad") || code=000
    if [[ $code != 200 ]]; then echo "pruefen: GET $pfad liefert $code statt 200" >&2; fehler=1; fi
  done
  echo "pruefen: Seiten /uc1 /uc2 /uc3 /uc4 /praesentation geprüft"

  # lesend: alles außer GET und HEAD weist Caddy ab, bevor es die App erreicht. Geprüft am Text der Caddy-Antwort,
  # damit ein 403 der App nicht als Sperre an der Kante durchgeht. Die Liste nennt jeden schreibenden Weg der App.
  local antwort gesperrt=0
  for pfad in /api/probe /api/uc3/freigabe /api/uc2/faelle /api/uc2/faelle/mock-wartezeiten/freigabe \
    /api/uc2/modell /api/plattform/modell /chat/completions /vapi/webhook; do
    antwort=$(curl -sS -w ' %{http_code}' --max-time 20 -X POST -H 'content-type: application/json' -d '{}' \
      "https://$DOMAIN$pfad") || antwort="kein-netz 000"
    if [[ $antwort == "Die Online-Demo ist lesend. 403" ]]; then
      gesperrt=$((gesperrt + 1))
    else
      echo "pruefen: POST $pfad kommt an der Sperre vorbei (HTTP ${antwort##* })" >&2
      fehler=1
    fi
  done
  echo "pruefen: POST abgewiesen (403 an der Kante) auf $gesperrt schreibenden Wegen"

  # Frage-Wege (Stufe A, KIC_ONLINE_FRAGEN): offen genau dann, wenn der Schalter in .env.server auf 1 steht.
  # Ein leeres JSON ist eine ungültige Frage: die App antwortet 400, rechnet nichts und ruft kein Modell.
  local schalter erwartet
  # gelesen wie Compose: die letzte Zeile gewinnt; eine unlesbare Datei oder kein SSH ist ein Fehler, kein "zu"
  schalter=$(
    remote bash -s -- "$ENV_DATEI" <<'EOF'
test -r "$1" || exit 2
sed -nE "s/^[[:space:]]*(export[[:space:]]+)?KIC_ONLINE_FRAGEN=//p" "$1" | tail -n 1 | tr -d "\"'[:space:]"
EOF
  ) || schalter=unlesbar
  if [[ $schalter == unlesbar ]]; then
    echo "pruefen: KIC_ONLINE_FRAGEN in .env.server nicht lesbar, Frage-Wege nicht geprüft" >&2
    fehler=1
    erwartet=unbekannt
  elif [[ $schalter == 1 ]]; then erwartet=offen; else erwartet=zu; fi
  for pfad in /api/uc3/frage /api/uc4/frage; do
    code=$(curl -sS -o /dev/null -w '%{http_code}' --max-time 20 -X POST -H 'content-type: application/json' \
      -d '{}' "https://$DOMAIN$pfad") || code=000
    if [[ $erwartet == zu && $code == 403 ]] || [[ $erwartet == offen && $code == 400 ]]; then
      echo "pruefen: POST $pfad $erwartet wie erwartet ($code)"
    else
      echo "pruefen: POST $pfad liefert $code, erwartet $erwartet (KIC_ONLINE_FRAGEN)" >&2
      fehler=1
    fi
  done

  return "$fehler"
}

cmd_status() {
  remote bash -s -- "$BASIS" "$ENV_DATEI" <<'EOF'
set -euo pipefail
cd "$1/repo/deploy"
echo "Revision: $(cat "$1/repo/REVISION" 2>/dev/null || echo unbekannt)"
docker compose --env-file "$2" -f docker-compose.prod.yml ps --format 'table {{.Service}}\t{{.Image}}\t{{.Status}}' </dev/null
docker compose --env-file "$2" -f docker-compose.prod.yml logs --tail 20 --no-log-prefix caddy </dev/null
EOF
}

cmd_bauprobe() {
  local ref=${1:?bauprobe braucht einen Git-Ref, z. B. scripts/deploy.sh bauprobe feat/e0-geruest}
  cd "$REPO_ROOT"
  local rev
  rev=$(git rev-parse --verify "$ref^{commit}")
  TMP_DIR=$(mktemp -d)
  git archive --format=tar "$rev" | tar -x -C "$TMP_DIR"
  # deploy/ aus dem eigenen HEAD darüberlegen: geprüft wird der fremde Stand mit dem eigenen, committeten Dockerfile
  rm -rf "$TMP_DIR/deploy"
  git archive --format=tar HEAD deploy | tar -x -C "$TMP_DIR"
  printf '%s\n' "$rev" >"$TMP_DIR/REVISION"
  chmod 755 "$TMP_DIR"
  remote "mkdir -p $BASIS/probe"
  rsync -az --delete --no-owner --no-group -e "ssh ${SSH_OPTS[*]}" "$TMP_DIR/" "$HOST:$BASIS/probe/"
  echo "bauprobe: $ref (${rev:0:8}) übertragen, baue auf dem Server"

  # baut nur und startet einen Wegwerf-Container ohne Netz und ohne Geheimnisse; die laufende Seite bleibt unberührt
  remote bash -s -- "$BASIS" <<'EOF'
haupt() {
  set -euo pipefail
  cd "$1/probe"
  local start=$SECONDS
  docker build --progress=plain -f deploy/app.Dockerfile -t ki-challenge-app:probe . </dev/null >"$1/probe-build.log" 2>&1 || {
    tail -n 40 "$1/probe-build.log"
    echo "bauprobe: Build fehlgeschlagen, Log in $1/probe-build.log" >&2
    return 1
  }
  echo "bauprobe: Build ok in $((SECONDS - start)) s, Image $(docker image inspect ki-challenge-app:probe --format '{{.Size}}' | awk '{printf "%.0f MB", $1/1e6}')"
  docker rm -f ki-challenge-probe >/dev/null 2>&1 || true
  docker run -d --rm --name ki-challenge-probe --network none -e LLM_PROVIDER=mock ki-challenge-app:probe </dev/null >/dev/null
  sleep 4
  local fehler=0
  docker exec ki-challenge-probe node -e "fetch('http://127.0.0.1:3000/').then(async r => { console.log('bauprobe: web antwortet ' + r.status); if (r.status >= 500) { console.log((await r.text()).slice(0, 400)); process.exitCode = 1 } }).catch(e => { console.log('bauprobe: web antwortet nicht: ' + e.message); process.exitCode = 1 })" </dev/null || fehler=1
  # derselbe Weg wie die Route-Handler: uv run aus web/, ohne Sync und offline
  if docker exec -w /app/web ki-challenge-probe uv run python -c "import plattform" </dev/null; then
    echo "bauprobe: uv run python import plattform ok"
  else
    echo "bauprobe: uv run python import plattform fehlgeschlagen" >&2
    fehler=1
  fi
  if [ "$fehler" -ne 0 ]; then
    echo "bauprobe: letzte Logzeilen des Containers:"
    docker logs --tail 40 ki-challenge-probe </dev/null 2>&1 || true
  fi
  docker rm -f ki-challenge-probe >/dev/null 2>&1 || true
  return "$fehler"
}
haupt "$@"
EOF
}

# Namen und Pfade gehen in Remote-Befehle: nur einfache Bezeichner zulassen
pruefe_name() { [[ $1 =~ ^[a-z][a-z0-9_]{0,62}$ ]] || { echo "ungültiger Name: $1" >&2; exit 2; }; }

pruefe_datei() {
  if [[ ! $1 =~ ^[A-Za-z0-9._/-]+$ || $1 == *..* || $1 == /* ]]; then
    echo "Pfad relativ zu <basis>/daten angeben, ohne .." >&2
    exit 2
  fi
}

cmd_sichern() {
  # Sicherung je Datenbank (pg_dump -Fc) nach <basis>/daten/sicherung/<db>-<UTC>.dump mit .sha256 daneben.
  # Ohne DB: alle App-Datenbanken. Je DB bleiben die letzten 5; die Datei in $2 (Quelle eines laufenden `daten`)
  # wird nie weggeräumt. Zurück geht es mit `scripts/deploy.sh daten <db> sicherung/<datei>`.
  # $3 = vor-daten: eine noch fehlende DB ist dann kein Fehler (erstes Einspielen)
  local db=${1:-} schuetzen=${2:-} modus=${3:-direkt}
  if [[ -n $db ]]; then pruefe_name "$db"; fi
  if [[ -n $schuetzen ]]; then pruefe_datei "$schuetzen"; fi
  # ssh fügt die Argumente zu einem Befehlstext zusammen und verliert dabei leere: "-" steht für „keins“
  remote bash -s -- "$BASIS" "$ENV_DATEI" "${db:--}" "${schuetzen:--}" "$modus" <<'EOF'
haupt() {
  set -euo pipefail
  umask 077
  cd "$1/repo/deploy"
  local compose=(docker compose --env-file "$2" -f docker-compose.prod.yml) db=$3 schuetzen=$4 modus=$5 behalten=5
  if [ "$db" = - ]; then db=""; fi
  if [ "$schuetzen" = - ]; then schuetzen=""; fi
  local ziel="$1/daten/sicherung" liste d da stempel datei alt
  mkdir -p "$ziel"
  # eine Sicherung zur Zeit; .teil-Reste eines Abbruchs räumt der Trap weg
  exec 8>"$1/.sichern.lock"
  flock -w 600 8 || { echo "sichern: eine andere Sicherung läuft seit über 10 Minuten" >&2; return 1; }
  TEIL=""
  trap 'if [ -n "$TEIL" ]; then rm -f "$TEIL"; fi' EXIT
  "${compose[@]}" up -d --wait db </dev/null
  local psql=("${compose[@]}" exec -T db psql -X -q -At -U statistik -d statistik)
  if [ -n "$db" ]; then
    liste=$db
  else
    liste=$("${psql[@]}" -c "select datname from pg_database where not datistemplate and datname <> 'postgres' order by 1" </dev/null)
  fi
  for d in $liste; do
    da=$("${psql[@]}" -c "select 1 from pg_database where datname = '$d'" </dev/null)
    if [ "$da" != 1 ]; then
      if [ "$modus" = vor-daten ]; then
        echo "sichern: Datenbank $d gibt es noch nicht, nichts zu sichern"
        continue
      fi
      echo "sichern: Datenbank $d gibt es nicht" >&2
      return 1
    fi
    # sekundengenauer Name; liegt er schon da (zwei Läufe in derselben Sekunde), eine Sekunde warten: nie überschreiben
    stempel=$(date -u +%Y%m%dT%H%M%SZ)
    while [ -e "$ziel/$d-$stempel.dump" ]; do
      sleep 1
      stempel=$(date -u +%Y%m%dT%H%M%SZ)
    done
    datei="$ziel/$d-$stempel.dump"
    # erst als .teil schreiben und lesend gegenprüfen; eine halbe Sicherung bekommt nie den endgültigen Namen
    TEIL="$datei.teil"
    "${compose[@]}" exec -T db pg_dump -U statistik -d "$d" -Fc </dev/null >"$TEIL"
    test -s "$TEIL" || { echo "sichern: $d ergab eine leere Datei" >&2; return 1; }
    # liest jeden Datenblock, nicht nur das Inhaltsverzeichnis: eine abgeschnittene Datei scheitert hier
    "${compose[@]}" exec -T db pg_restore -f /dev/null "/daten/sicherung/$(basename "$TEIL")" </dev/null
    mv -n "$TEIL" "$datei"
    if [ -e "$TEIL" ]; then echo "sichern: $(basename "$datei") gibt es schon, nichts überschrieben" >&2; return 1; fi
    TEIL=""
    sha256sum "$datei" >"$datei.sha256"
    echo "sichern: $d nach sicherung/$(basename "$datei"), $(stat -c %s "$datei") Byte, sha256 $(cut -c1-16 "$datei.sha256")…"
    # nur die letzten $behalten je DB behalten, nie die geschützte Quelle; vor einem Einspielen wird nichts
    # weggeräumt, damit Fehlversuche keine älteren, verschiedenen Stände verdrängen
    if [ "$modus" = vor-daten ]; then continue; fi
    ls -1t "$ziel/$d"-[0-9]*Z.dump | tail -n +$((behalten + 1)) | while read -r alt; do
      if [ -n "$schuetzen" ] && [ "$alt" -ef "$1/daten/$schuetzen" ]; then continue; fi
      rm -f "$alt" "$alt.sha256"
    done
  done
}
haupt "$@"
EOF
}

cmd_daten() {
  local db=${1:?daten braucht DB und Datei, z. B. scripts/deploy.sh daten healthpolicy uc2/healthpolicy-uc2.dump}
  local datei=${2:?daten braucht eine Datei unter <basis>/daten}
  pruefe_name "$db"
  pruefe_datei "$datei"
  # 1. erst die Datei prüfen: eine fehlende, kaputte oder falsche Datei bricht ab, bevor gesichert wird
  remote bash -s -- "$BASIS" "$datei" <<'EOF'
haupt() {
  set -euo pipefail
  local basis=$1 datei=$2
  test -f "$basis/daten/$datei" || { echo "daten: <basis>/daten/$datei fehlt" >&2; return 1; }
  # psql würde einen abgeschnittenen Strom sonst bis zum Abbruch einspielen: die ganze Datei vorher prüfen
  case "$datei" in
    *.sql.gz) gzip -t "$basis/daten/$datei" || { echo "daten: $datei ist kein vollständiges gzip, nichts eingespielt" >&2; return 1; } ;;
  esac
  if [ -f "$basis/daten/$datei.sha256" ]; then
    (cd "$(dirname "$basis/daten/$datei")" && sha256sum -c --quiet "$(basename "$datei").sha256") ||
      { echo "daten: Prüfsumme von $datei stimmt nicht, nichts eingespielt" >&2; return 1; }
  fi
  echo "daten: sha256 $(sha256sum "$basis/daten/$datei" | cut -c1-16)…, $(stat -c %s "$basis/daten/$datei") Byte, geprüft"
}
haupt "$@"
EOF
  # 2. Rückweg: den heutigen Stand sichern; scheitert das, wird nichts eingespielt
  cmd_sichern "$db" "$datei" vor-daten
  # Im db-Container; der Dump liegt dort read-only unter /daten. pg_dump -Fc (.dump) über pg_restore, vorhandene
  # Objekte werden ersetzt; reines SQL (.sql.gz) über psql, der Dump muss dann selbst aufräumen (pg_dump --clean
  # --if-exists), sonst scheitert er an vorhandenen Objekten und die Datenbank bleibt, wie sie war.
  remote bash -s -- "$BASIS" "$ENV_DATEI" "$db" "$datei" <<'EOF'
haupt() {
  set -euo pipefail
  cd "$1/repo/deploy"
  local compose=(docker compose --env-file "$2" -f docker-compose.prod.yml) db=$3 datei=$4
  # 3. einspielen (die Datei ist oben geprüft)
  test -f "$1/daten/$datei" || { echo "daten: <basis>/daten/$datei fehlt" >&2; return 1; }
  "${compose[@]}" up -d --wait db </dev/null
  local da
  da=$("${compose[@]}" exec -T db psql -U statistik -d statistik -At -c "select 1 from pg_database where datname = '$db'" </dev/null)
  if [ "$da" != 1 ]; then
    "${compose[@]}" exec -T db createdb -U statistik "$db" </dev/null
    echo "daten: Datenbank $db angelegt"
  fi
  # eine Transaktion: ein Fehler lässt die Datenbank im alten Zustand statt halb geleert
  case "$datei" in
    *.sql.gz)
      # commit nur, wenn gzip bis zum Ende gelesen hat; fehlt es, rollt Postgres beim Verbindungsende zurück
      { echo 'begin;'; gzip -dc "$1/daten/$datei" && echo 'commit;'; } |
        "${compose[@]}" exec -T db psql -X -q -v ON_ERROR_STOP=1 -U statistik -d "$db" >/dev/null
      ;;
    *)
      "${compose[@]}" exec -T db pg_restore -U statistik -d "$db" --no-owner --no-privileges --clean --if-exists \
        --single-transaction --exit-on-error "/daten/$datei" </dev/null
      ;;
  esac
  echo "daten: $datei nach $db eingespielt"
}
haupt "$@"
EOF
  cmd_rechte
}

cmd_inhaltshash() {
  local db=${1:?inhaltshash braucht DB und Schema, z. B. scripts/deploy.sh inhaltshash healthpolicy uc2}
  local schema=${2:?inhaltshash braucht ein Schema}
  pruefe_name "$db"
  pruefe_name "$schema"
  # dieselbe Abfrage wie lokal: psql -X -q -At -v schema=uc2 -f deploy/sql/inhaltshash.sql
  remote bash -s -- "$BASIS" "$ENV_DATEI" "$db" "$schema" <<'EOF'
haupt() {
  set -euo pipefail
  cd "$1/repo/deploy"
  docker compose --env-file "$2" -f docker-compose.prod.yml exec -T db \
    psql -X -q -At -U statistik -d "$3" -v schema="$4" -f /deploy-sql/inhaltshash.sql </dev/null
}
haupt "$@"
EOF
}

case "${1:-alles}" in
  -h | --help | hilfe) ;;
  *) lade_ziel ;;
esac

case "${1:-alles}" in
  init) cmd_init ;;
  rechte) cmd_rechte ;;
  daten) cmd_daten "${2:-}" "${3:-}" ;;
  sichern) cmd_sichern "${2:-}" ;;
  inhaltshash) cmd_inhaltshash "${2:-}" "${3:-}" ;;
  up) cmd_up ;;
  pruefen) cmd_pruefen ;;
  status) cmd_status ;;
  bauprobe) cmd_bauprobe "${2:-}" ;;
  alles)
    # getrennte Aufrufe: in einer &&-Liste wäre set -e innerhalb von cmd_up außer Kraft
    cmd_up
    cmd_pruefen
    ;;
  -h | --help | hilfe) sed -n '2,25p' "$0" ;;
  *)
    echo "unbekannter Befehl: $1 (init|up|rechte|pruefen|status|bauprobe|daten|sichern|inhaltshash)" >&2
    exit 2
    ;;
esac
