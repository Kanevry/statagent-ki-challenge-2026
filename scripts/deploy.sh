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
#   scripts/deploy.sh daten DB DATEI     Dump (pg_dump -Fc) aus <basis>/daten/DATEI in die Datenbank DB
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
  local als_app=("${compose[@]}" exec -T -e PGPASSWORD db psql -X -q -At -h 127.0.0.1 -U kic_app -d statistik)
  "${als_app[@]}" -c "select 'rechte: kic_app angemeldet, superuser=' || rolsuper || ', default_transaction_read_only=' || current_setting('default_transaction_read_only') from pg_roles where rolname = current_user" </dev/null
  if "${als_app[@]}" -c "create table kic_probe (x int)" </dev/null >/dev/null 2>&1; then
    echo "rechte: kic_app konnte eine Tabelle anlegen" >&2
    return 1
  fi
  if "${als_app[@]}" -c "begin; set transaction read write; create table public.kic_probe (x int); rollback;" </dev/null >/dev/null 2>&1; then
    echo "rechte: kic_app konnte mit read write eine Tabelle anlegen" >&2
    return 1
  fi
  echo "rechte: Anlegen als kic_app abgewiesen (lesend und ohne CREATE-Recht)"
  # echtes Lesen als kic_app: je Datenbank die erste berechtigte Tabelle zählen
  for db in $datenbanken; do
    "${compose[@]}" exec -T -e PGPASSWORD db psql -X -q -At -h 127.0.0.1 -U kic_app -d "$db" -c "select 'rechte ' || current_database() || ': kic_app liest ' || coalesce((select table_schema || '.' || table_name || ' (' || (xpath('/row/n/text()', query_to_xml(format('select count(*) as n from %I.%I', table_schema, table_name), false, true, '')))[1]::text || ' Zeilen)' from information_schema.role_table_grants where grantee = 'kic_app' and privilege_type = 'SELECT' order by 1 limit 1), 'keine Tabelle vorhanden')" </dev/null
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

  # lesend: alles außer GET und HEAD weist Caddy ab, bevor es die App erreicht; Ausnahme nur POST auf die zwei
  # Frage-Wege (Stufe A). Freigaben und UC2-Fälle bleiben auch nach dem Umschalten 403 (Review !94).
  local pfad
  for pfad in /api/probe /api/uc3/freigabe /api/uc2/faelle; do
    code=$(curl -sS -o /dev/null -w '%{http_code}' --max-time 20 -X POST -d x=1 "https://$DOMAIN$pfad") || code=000
    if [[ $code == 403 ]]; then echo "pruefen: POST $pfad abgewiesen (403, lesend)"; else echo "pruefen: POST $pfad liefert $code statt 403" >&2; fehler=1; fi
  done
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

cmd_daten() {
  local db=${1:?daten braucht DB und Datei, z. B. scripts/deploy.sh daten healthpolicy uc2/healthpolicy-uc2.dump}
  local datei=${2:?daten braucht eine Datei unter <basis>/daten}
  pruefe_name "$db"
  if [[ ! $datei =~ ^[A-Za-z0-9._/-]+$ || $datei == *..* || $datei == /* ]]; then
    echo "daten: Pfad relativ zu <basis>/daten angeben, ohne .." >&2
    exit 2
  fi
  # pg_restore im db-Container; der Dump liegt dort read-only unter /daten. Vorhandene Objekte werden ersetzt.
  remote bash -s -- "$BASIS" "$ENV_DATEI" "$db" "$datei" <<'EOF'
haupt() {
  set -euo pipefail
  cd "$1/repo/deploy"
  local compose=(docker compose --env-file "$2" -f docker-compose.prod.yml) db=$3 datei=$4
  test -f "$1/daten/$datei" || { echo "daten: <basis>/daten/$datei fehlt" >&2; return 1; }
  echo "daten: sha256 $(sha256sum "$1/daten/$datei" | cut -c1-16)…, $(stat -c %s "$1/daten/$datei") Byte"
  "${compose[@]}" up -d --wait db </dev/null
  local da
  da=$("${compose[@]}" exec -T db psql -U statistik -d statistik -At -c "select 1 from pg_database where datname = '$db'" </dev/null)
  if [ "$da" != 1 ]; then
    "${compose[@]}" exec -T db createdb -U statistik "$db" </dev/null
    echo "daten: Datenbank $db angelegt"
  fi
  # eine Transaktion: ein Fehler lässt die Datenbank im alten Zustand statt halb geleert
  "${compose[@]}" exec -T db pg_restore -U statistik -d "$db" --no-owner --no-privileges --clean --if-exists \
    --single-transaction --exit-on-error "/daten/$datei" </dev/null
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
  -h | --help | hilfe) sed -n '2,22p' "$0" ;;
  *)
    echo "unbekannter Befehl: $1 (init|up|rechte|pruefen|status|bauprobe|daten|inhaltshash)" >&2
    exit 2
    ;;
esac
