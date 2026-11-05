#!/usr/bin/env bash
# Vorführ-Instanz der Live-Demo auf dem Demo-Server: eigene Adresse mit Basic-Auth, eigene App, eigene Datenbank, eigener
# Git-Checkout. Die öffentliche Demo bleibt lesend und wird von diesem Skript nur beim Neuladen von Caddy berührt.
#
#   scripts/vorfuehrung.sh zugang         lokal: VORFUEHRUNG_ZUGANG in .env.local anlegen, falls er fehlt (Wert nie ausgeben)
#   scripts/vorfuehrung.sh init           auf dem Server: Passwort, Budget, Azure-Zugang, Caddy-Fragment (nur der Hash)
#   scripts/vorfuehrung.sh up [REF]       Stand REF (Standard HEAD) bauen und starten, Git-Checkout neu aus REF, Caddy neu laden
#   scripts/vorfuehrung.sh daten DATEI    pg_dump -Fc (lokale Datei) hochladen, als Vorlage einspielen, Arbeitskopie anlegen
#   scripts/vorfuehrung.sh reset          Ausgangsstand: Arbeitskopie neu aus der Vorlage, Freigabe-Commits weg, App neu
#   scripts/vorfuehrung.sh pensionen-freigeben "Vor- und Nachname"   Freigabe der Pensionen in der Instanz, Commit im eigenen Checkout
#   scripts/vorfuehrung.sh festschreiben  heutiger Stand wird Ausgangsstand (etwa nach der Freigabe der Pensionen), reset behält ihn
#   scripts/vorfuehrung.sh pruefen        von außen: ohne Zugang 401, mit Zugang Seiten, öffentliche Demo weiter gesperrt
#   scripts/vorfuehrung.sh status         Container, Revision, Regelsatz, Läufe, Commits
#
# Ziel wie scripts/deploy.sh (DEPLOY_HOST, DEPLOY_BASIS, DEPLOY_DOMAIN). Adresse: VORFUEHRUNG_DOMAIN, sonst
# vorfuehrung.<DEPLOY_DOMAIN>. Werte gehen nur über stdin an den Server, nie als Argument und nie in die Ausgabe.
set -euo pipefail

REPO_ROOT="$(git -C "$(dirname "${BASH_SOURCE[0]}")" rev-parse --show-toplevel)"
SSH_OPTS=(-o ConnectTimeout=10 -o BatchMode=yes)
NUTZER=vorfuehrung
TMP_DIR=""
HOST="" BASIS="" DOMAIN="" V_DOMAIN="" V_BASIS="" ENV_LOKAL=""

lade_ziel() {
  local konfig=${DEPLOY_KONFIG:-$HOME/.config/ki-challenge/deploy.env} k v
  if [[ -f $konfig ]]; then
    while IFS='=' read -r k v; do
      if [[ -z ${!k:-} ]]; then printf -v "$k" '%s' "$v"; fi
    done < <(grep -E '^(DEPLOY_(HOST|BASIS|DOMAIN)|VORFUEHRUNG_DOMAIN)=' "$konfig")
  fi
  HOST=${DEPLOY_HOST:?DEPLOY_HOST fehlt (Umgebung oder $konfig)}
  BASIS=${DEPLOY_BASIS:?DEPLOY_BASIS fehlt (Umgebung oder $konfig)}
  DOMAIN=${DEPLOY_DOMAIN:?DEPLOY_DOMAIN fehlt (Umgebung oder $konfig)}
  V_DOMAIN=${VORFUEHRUNG_DOMAIN:-vorfuehrung.$DOMAIN}
  [[ $HOST =~ ^[A-Za-z0-9._-]+$ ]] || { echo "DEPLOY_HOST ungültig" >&2; exit 2; }
  [[ $BASIS =~ ^/[A-Za-z0-9._/-]+$ && $BASIS != *..* ]] || { echo "DEPLOY_BASIS ungültig" >&2; exit 2; }
  [[ $DOMAIN =~ ^[a-z0-9.-]+$ && $V_DOMAIN =~ ^[a-z0-9.-]+$ ]] || { echo "Domain ungültig" >&2; exit 2; }
  # dieselbe Adresse hieße: Basic-Auth und Schreibwege auf der öffentlichen Demo
  [[ $V_DOMAIN != "$DOMAIN" ]] || { echo "VORFUEHRUNG_DOMAIN darf nicht die öffentliche Adresse sein" >&2; exit 2; }
  V_BASIS=$BASIS/vorfuehrung
}

# .env.local liegt im Haupt-Checkout; ein Worktree hat oft keine eigene
lade_env_lokal() {
  local haupt
  haupt=$(git -C "$REPO_ROOT" worktree list --porcelain | sed -n '1s/^worktree //p')
  ENV_LOKAL=${VORFUEHRUNG_ENV:-$haupt/.env.local}
  [[ -f $ENV_LOKAL ]] || { echo ".env.local fehlt im Haupt-Checkout" >&2; exit 1; }
}

# Wert eines Schlüssels; die letzte Zeile gewinnt, umschließende Anführungszeichen fallen weg. Nie ausgeben.
lokal_wert() {
  sed -n "s/^$1=//p" "$ENV_LOKAL" | tail -n 1 | sed -e "s/^'\(.*\)'$/\1/" -e 's/^"\(.*\)"$/\1/'
}

remote() { ssh "${SSH_OPTS[@]}" "$HOST" "$@"; }
aufraeumen() { if [[ -n "$TMP_DIR" ]]; then rm -rf "$TMP_DIR"; fi; }
trap aufraeumen EXIT

cmd_zugang() {
  lade_env_lokal
  if grep -q '^VORFUEHRUNG_ZUGANG=.' "$ENV_LOKAL"; then
    echo "zugang: VORFUEHRUNG_ZUGANG vorhanden, unverändert"
    return
  fi
  local wert
  wert=$(openssl rand 256 | LC_ALL=C tr -dc 'A-Za-z0-9' | cut -c1-24)
  [[ ${#wert} == 24 ]] || { echo "zugang: Zufall zu kurz, nichts geschrieben" >&2; exit 1; }
  # führender Zeilenumbruch, falls die Datei ohne endet
  printf "\nVORFUEHRUNG_ZUGANG='%s'\n" "$wert" >>"$ENV_LOKAL"
  echo "zugang: VORFUEHRUNG_ZUGANG angelegt (Nutzername: $NUTZER), Wert nur in .env.local"
}

cmd_init() {
  lade_env_lokal
  local zugang name hash
  zugang=$(lokal_wert VORFUEHRUNG_ZUGANG)
  [[ -n $zugang ]] || { echo "init: VORFUEHRUNG_ZUGANG fehlt, zuerst scripts/vorfuehrung.sh zugang" >&2; exit 1; }
  for name in AZURE_OPENAI_BASE_URL AZURE_OPENAI_MODEL AZURE_API_KEY; do
    [[ -n $(lokal_wert "$name") ]] || { echo "init: $name fehlt in .env.local" >&2; exit 1; }
  done
  # bcrypt lokal, über stdin: nur der Hash geht auf den Server
  hash=$(printf '%s' "$zugang" | htpasswd -niBC 12 "$NUTZER" | sed -n "s/^$NUTZER://p")
  [[ $hash == \$2* ]] || { echo "init: Hash nicht erzeugt (htpasswd fehlt?)" >&2; exit 1; }

  remote bash -s -- "$V_BASIS" "$V_DOMAIN" <<'EOF'
set -euo pipefail
v=$1 domain=$2
umask 077
mkdir -p "$v/daten" "$v/caddy" "$v/repo"
datei=$v/.env
touch "$datei"
chmod 600 "$datei"
if ! grep -q '^VORFUEHRUNG_DB_PASSWORD=.' "$datei"; then
  pw=$(openssl rand 512 | LC_ALL=C tr -dc 'A-Za-z0-9')
  if [ "${#pw}" -lt 32 ]; then echo "init: Zufall zu kurz, nichts geschrieben" >&2; exit 1; fi
  printf "VORFUEHRUNG_DB_PASSWORD='%s'\n" "${pw:0:32}" >>"$datei"
  echo "init: Datenbank-Passwort neu angelegt"
fi
# Jeder Modellaufruf zählt, Grenze je UTC-Tag. Ein Auftrag mit Freigabe und Rücknahme kostet 6 bis 15 Aufrufe, eine
# Probenserie der Live-Lane brauchte 673: Proben dürfen die Vorführung nicht aussperren.
grep -q '^VORFUEHRUNG_TAGESBUDGET=.' "$datei" || echo "VORFUEHRUNG_TAGESBUDGET=2000" >>"$datei"
sed -i '/^VORFUEHRUNG_DOMAIN=/d;/^VORFUEHRUNG_GIT=/d' "$datei"
printf "VORFUEHRUNG_DOMAIN=%s\nVORFUEHRUNG_GIT=%s/checkout/.git\n" "$domain" "$v" >>"$datei"
echo "init: $datei Modus $(stat -c %a "$datei")"
EOF

  # Azure-Zugang über stdin; eigene Datei, die öffentliche .env.server bleibt ohne Modellschlüssel
  {
    for name in AZURE_OPENAI_BASE_URL AZURE_OPENAI_MODEL AZURE_API_KEY; do
      printf "%s='%s'\n" "$name" "$(lokal_wert "$name")"
    done
  } | remote "umask 077 && cat > $V_BASIS/.env.azure"
  echo "init: Azure-Zugang übertragen"

  sed -e "s/@@DOMAIN@@/$V_DOMAIN/" "$REPO_ROOT/deploy/vorfuehrung.caddy.vorlage" |
    awk -v h="$hash" '{ i = index($0, "@@HASH@@"); if (i) print substr($0, 1, i - 1) h substr($0, i + 8); else print }' |
    remote "umask 022 && cat > $V_BASIS/caddy/vorfuehrung.caddy.neu"
  remote "chmod 755 $V_BASIS $V_BASIS/caddy"
  # Das Muster im Caddyfile trifft nur *.caddy. Scharf wird das Fragment erst nach bestandener Prüfung im Caddy-Container:
  # Ein kaputtes Fragment ließe Caddy beim nächsten Neustart nicht starten, dann wäre auch die öffentliche Demo weg.
  remote bash -s -- "$BASIS" "$V_BASIS" <<'EOF'
haupt() {
  set -euo pipefail
  local basis=$1 v=$2
  cd "$basis/repo/deploy"
  if ! docker compose --env-file "$basis/.env.server" -f docker-compose.prod.yml exec -T caddy sh -c \
    'cat /etc/caddy/Caddyfile >/tmp/pruefung.caddyfile && echo "import /etc/caddy-vorfuehrung/vorfuehrung.caddy.neu" >>/tmp/pruefung.caddyfile && caddy validate --config /tmp/pruefung.caddyfile --adapter caddyfile' \
    </dev/null >"$v/caddy-pruefung.log" 2>&1; then
    tail -n 5 "$v/caddy-pruefung.log" >&2
    rm -f "$v/caddy/vorfuehrung.caddy.neu"
    echo "init: Fragment besteht die Prüfung nicht (oder Caddy kennt das Volume noch nicht: zuerst scripts/deploy.sh up von main), nichts scharf" >&2
    return 1
  fi
  mv "$v/caddy/vorfuehrung.caddy.neu" "$v/caddy/vorfuehrung.caddy"
}
haupt "$@"
EOF
  echo "init: Caddy-Fragment geprüft und scharf (nur der Hash)"
}

cmd_up() {
  cd "$REPO_ROOT"
  local ref=${1:-HEAD} rev
  rev=$(git rev-parse --verify "$ref^{commit}")
  TMP_DIR=$(mktemp -d)
  git archive --format=tar "$rev" | tar -x -C "$TMP_DIR"
  printf '%s\n' "$rev" >"$TMP_DIR/REVISION"
  chmod 755 "$TMP_DIR"
  local neu="$V_BASIS/neu-${rev:0:12}-$$"
  remote "test -s $V_BASIS/.env" || { echo "up: zuerst scripts/vorfuehrung.sh init" >&2; exit 1; }
  remote "mkdir -p $neu"
  rsync -az --delete --no-owner --no-group -e "ssh ${SSH_OPTS[*]}" "$TMP_DIR/" "$HOST:$neu/"
  echo "up: Revision ${rev:0:8} übertragen"

  remote bash -s -- "$BASIS" "$V_BASIS" "$neu" <<'EOF'
haupt() {
  set -euo pipefail
  local basis=$1 v=$2 neu=$3
  NEU_VERZ=$neu
  trap 'rm -rf "$NEU_VERZ"' EXIT
  exec 9>"$v/.lock"
  flock -w 300 9 || { echo "up: ein anderer Vorgang läuft seit über 5 Minuten" >&2; return 1; }
  local compose=(docker compose --env-file "$basis/.env.server" --env-file "$v/.env" --env-file "$v/.env.azure" -f docker-compose.vorfuehrung.yml)
  # 1. prüfen und bauen; die laufende Instanz bleibt bis dahin unberührt
  cd "$neu/deploy"
  "${compose[@]}" config --quiet </dev/null
  cd "$neu"
  local start=$SECONDS
  docker build --progress=plain -f deploy/app.Dockerfile -t ki-challenge-vorfuehrung:basis . </dev/null >"$v/bau.log" 2>&1 ||
    { tail -n 40 "$v/bau.log"; echo "up: Build fehlgeschlagen, nichts geändert" >&2; return 1; }
  docker build --progress=plain -t ki-challenge-vorfuehrung:aktuell - <deploy/vorfuehrung.Dockerfile >>"$v/bau.log" 2>&1 ||
    { tail -n 40 "$v/bau.log"; echo "up: Build fehlgeschlagen, nichts geändert" >&2; return 1; }
  echo "up: Image gebaut in $((SECONDS - start)) s"
  rsync -a --delete --exclude /REVISION "$neu/" "$v/repo/"

  # 2. eigener Checkout aus genau diesem Stand: ein Commit, Marke ausgangsstand, kein Remote, also kein Push
  local rev git=(git -c safe.directory=* -c user.name=StatAgent -c user.email=vorfuehrung@example.invalid)
  rev=$(cat "$neu/REVISION")
  rm -rf "$v/checkout"
  mkdir -p "$v/checkout"
  rsync -a --exclude /REVISION "$neu/" "$v/checkout/"
  "${git[@]}" -C "$v/checkout" init -q -b vorfuehrung
  "${git[@]}" -C "$v/checkout" add -A
  "${git[@]}" -C "$v/checkout" commit -q -m "Ausgangsstand der Vorführung (${rev:0:12})"
  "${git[@]}" -C "$v/checkout" tag ausgangsstand
  chown -R 1001:1001 "$v/checkout/.git"

  # 3. starten; das Git-Verzeichnis ist neu, also die App neu erzeugen
  cd "$v/repo/deploy"
  "${compose[@]}" up -d --no-build --force-recreate --wait --wait-timeout 180 vorfuehrung-db vorfuehrung-app </dev/null
  cp "$neu/REVISION" "$v/repo/REVISION"
  "${compose[@]}" ps --format 'table {{.Service}}\t{{.Status}}' </dev/null

  # 4. Caddy nimmt das Fragment auf; ein kaputtes Fragment scheitert hier, die alte Konfiguration bleibt aktiv
  cd "$basis/repo/deploy"
  docker compose --env-file "$basis/.env.server" -f docker-compose.prod.yml exec -T caddy \
    caddy reload --config /etc/caddy/Caddyfile --adapter caddyfile </dev/null
  echo "up: Caddy neu geladen"
  docker image prune -f </dev/null >/dev/null 2>&1 || echo "up: namenlose Images nicht aufgeräumt" >&2
  echo "up: Platte $(df -h --output=avail "$basis" | tail -n 1 | tr -d ' ') frei"
}
haupt "$@"
EOF
}

cmd_daten() {
  local datei=${1:?daten braucht eine lokale pg_dump-Datei (-Fc)}
  [[ -f $datei ]] || { echo "daten: $datei fehlt" >&2; exit 1; }
  rsync -a --partial --no-owner --no-group -e "ssh ${SSH_OPTS[*]}" "$datei" "$HOST:$V_BASIS/daten/quelle.dump"
  echo "daten: Dump übertragen"
  remote bash -s -- "$BASIS" "$V_BASIS" <<'EOF'
haupt() {
  set -euo pipefail
  local basis=$1 v=$2 start=$SECONDS
  exec 9>"$v/.lock"
  flock -w 300 9 || { echo "daten: ein anderer Vorgang läuft seit über 5 Minuten" >&2; return 1; }
  cd "$v/repo/deploy"
  local compose=(docker compose --env-file "$basis/.env.server" --env-file "$v/.env" --env-file "$v/.env.azure" -f docker-compose.vorfuehrung.yml)
  local psql=("${compose[@]}" exec -T vorfuehrung-db psql -X -q -At -v ON_ERROR_STOP=1 -U statistik -d postgres)
  "${compose[@]}" stop vorfuehrung-app </dev/null
  "${compose[@]}" up -d --wait vorfuehrung-db </dev/null
  "${psql[@]}" -c 'drop database if exists statistik_vorfuehrung_vorlage with (force)' </dev/null
  "${psql[@]}" -c 'create database statistik_vorfuehrung_vorlage' </dev/null
  "${compose[@]}" exec -T vorfuehrung-db pg_restore -U statistik -d statistik_vorfuehrung_vorlage --no-owner --no-privileges \
    --exit-on-error -j 3 /daten/quelle.dump </dev/null
  # Nach dem Einspielen fehlen die Statistiken; ohne sie rechnet jede Abfrage eines Laufs mit falschen Plänen
  "${compose[@]}" exec -T vorfuehrung-db psql -X -q -U statistik -d statistik_vorfuehrung_vorlage -c 'analyze' </dev/null
  "${psql[@]}" -c 'drop database if exists statistik_vorfuehrung with (force)' </dev/null
  "${psql[@]}" -c 'create database statistik_vorfuehrung template statistik_vorfuehrung_vorlage' </dev/null
  local s
  for s in stat meta; do
    "${compose[@]}" exec -T vorfuehrung-db psql -X -q -At -U statistik -d statistik_vorfuehrung_vorlage \
      -v schema="$s" -f /deploy-sql/inhaltshash.sql </dev/null | grep GESAMT | sed "s/^/daten: $s /"
  done
  "${compose[@]}" up -d --wait --wait-timeout 180 vorfuehrung-app </dev/null
  echo "daten: Vorlage und Arbeitskopie stehen in $((SECONDS - start)) s"
}
haupt "$@"
EOF
}

cmd_reset() {
  remote bash -s -- "$BASIS" "$V_BASIS" <<'EOF'
haupt() {
  set -euo pipefail
  local basis=$1 v=$2 start=$SECONDS
  exec 9>"$v/.lock"
  flock -w 300 9 || { echo "reset: ein anderer Vorgang läuft seit über 5 Minuten" >&2; return 1; }
  cd "$v/repo/deploy"
  local compose=(docker compose --env-file "$basis/.env.server" --env-file "$v/.env" --env-file "$v/.env.azure" -f docker-compose.vorfuehrung.yml)
  local psql=("${compose[@]}" exec -T vorfuehrung-db psql -X -q -At -v ON_ERROR_STOP=1 -U statistik -d postgres)
  "${psql[@]}" -c "select 1 from pg_database where datname = 'statistik_vorfuehrung_vorlage'" </dev/null | grep -q 1 ||
    { echo "reset: keine Vorlage, zuerst scripts/vorfuehrung.sh daten" >&2; return 1; }
  # App weg: beendet einen laufenden Auftrag, leert tmpfs (Code-Vorschläge) und den Stand im Prozess
  "${compose[@]}" stop vorfuehrung-app </dev/null
  "${psql[@]}" -c 'drop database if exists statistik_vorfuehrung with (force)' </dev/null
  "${psql[@]}" -c 'create database statistik_vorfuehrung template statistik_vorfuehrung_vorlage' </dev/null
  # Das .git beschreibt der Container-Nutzer: Git liest dort auch Einstellungen, die Programme starten. Darum nie als root.
  als_app() { HOME=/nonexistent setpriv --reuid=1001 --regid=1001 --clear-groups git -c 'safe.directory=*' -C "$v/checkout" "$@"; }
  als_app reset -q --mixed ausgangsstand
  "${compose[@]}" up -d --wait --wait-timeout 180 --force-recreate vorfuehrung-app </dev/null
  echo "reset: Commits seit Ausgangsstand: $(als_app rev-list --count ausgangsstand..HEAD)"
  "${compose[@]}" exec -T vorfuehrung-db psql -X -q -At -U statistik -d statistik_vorfuehrung \
    -c "select 'reset: Läufe ' || (select count(*) from meta.lauf) || ', offene Vorschläge ' || (select count(*) from meta.vorschlag where status = 'offen')" </dev/null
  echo "reset: fertig in $((SECONDS - start)) s"
}
haupt "$@"
EOF
}

cmd_pensionen_freigeben() {
  local name=${1:?pensionen-freigeben braucht Vor- und Nachnamen}
  # Prüft die CLI noch einmal; base64, weil ssh die Argumente zu einem Befehlstext zusammenfügt und Leerzeichen verlöre
  remote bash -s -- "$BASIS" "$V_BASIS" "$(printf '%s' "$name" | base64 | tr -d '\n')" <<'EOF'
haupt() {
  set -euo pipefail
  local basis=$1 v=$2 name
  name=$(printf '%s' "$3" | base64 -d)
  exec 9>"$v/.lock"
  flock -w 300 9 || { echo "pensionen-freigeben: ein anderer Vorgang läuft seit über 5 Minuten" >&2; return 1; }
  cd "$v/repo/deploy"
  # In der App: nur dort stimmen Datenbank, Git-Identität und Checkout
  docker compose --env-file "$basis/.env.server" --env-file "$v/.env" --env-file "$v/.env.azure" -f docker-compose.vorfuehrung.yml \
    exec -T vorfuehrung-app uv run --frozen --package statagent uc3 pensionen freigeben --name "$name" </dev/null
  HOME=/nonexistent setpriv --reuid=1001 --regid=1001 --clear-groups git -c 'safe.directory=*' -C "$v/checkout" \
    log -1 --format='pensionen-freigeben: Commit %h | %(trailers:key=Freigegeben-von,valueonly,separator=%x2C)'
}
haupt "$@"
EOF
}

cmd_festschreiben() {
  remote bash -s -- "$BASIS" "$V_BASIS" <<'EOF'
haupt() {
  set -euo pipefail
  local basis=$1 v=$2 start=$SECONDS
  exec 9>"$v/.lock"
  flock -w 300 9 || { echo "festschreiben: ein anderer Vorgang läuft seit über 5 Minuten" >&2; return 1; }
  cd "$v/repo/deploy"
  local compose=(docker compose --env-file "$basis/.env.server" --env-file "$v/.env" --env-file "$v/.env.azure" -f docker-compose.vorfuehrung.yml)
  local psql=("${compose[@]}" exec -T vorfuehrung-db psql -X -q -At -v ON_ERROR_STOP=1 -U statistik -d postgres)
  als_app() { HOME=/nonexistent setpriv --reuid=1001 --regid=1001 --clear-groups git -c 'safe.directory=*' -C "$v/checkout" "$@"; }
  # App weg, sonst scheitert die Kopie an offenen Verbindungen. Erst die neue Vorlage bauen, dann die alte ersetzen:
  # Scheitert die Kopie, bleibt der bisherige Ausgangsstand.
  "${compose[@]}" stop vorfuehrung-app </dev/null
  "${psql[@]}" -c 'drop database if exists statistik_vorfuehrung_vorlage_neu' </dev/null
  "${psql[@]}" -c 'create database statistik_vorfuehrung_vorlage_neu template statistik_vorfuehrung' </dev/null
  "${psql[@]}" -c 'drop database if exists statistik_vorfuehrung_vorlage with (force)' </dev/null
  "${psql[@]}" -c 'alter database statistik_vorfuehrung_vorlage_neu rename to statistik_vorfuehrung_vorlage' </dev/null
  echo "festschreiben: Commits seit dem alten Ausgangsstand: $(als_app rev-list --count ausgangsstand..HEAD)"
  als_app tag -f ausgangsstand HEAD >/dev/null
  "${compose[@]}" up -d --wait --wait-timeout 180 vorfuehrung-app </dev/null
  "${compose[@]}" exec -T vorfuehrung-db psql -X -q -At -U statistik -d statistik_vorfuehrung_vorlage \
    -c "select 'festschreiben: Vorlage mit ' || (select count(*) from meta.lauf) || ' Läufen, ' || (select count(*) from meta.vorschlag where status = 'offen') || ' offenen Vorschlägen'" </dev/null
  echo "festschreiben: fertig in $((SECONDS - start)) s"
}
haupt "$@"
EOF
}

cmd_status() {
  remote bash -s -- "$BASIS" "$V_BASIS" <<'EOF'
haupt() {
  set -uo pipefail
  local basis=$1 v=$2
  cd "$v/repo/deploy" || return 1
  local compose=(docker compose --env-file "$basis/.env.server" --env-file "$v/.env" --env-file "$v/.env.azure" -f docker-compose.vorfuehrung.yml)
  echo "Revision: $(cat "$v/repo/REVISION" 2>/dev/null || echo unbekannt)"
  "${compose[@]}" ps --format 'table {{.Service}}\t{{.Status}}' </dev/null
  # als Container-Nutzer, nie als root (wie in reset)
  HOME=/nonexistent setpriv --reuid=1001 --regid=1001 --clear-groups git -c 'safe.directory=*' -C "$v/checkout" \
    log --format='%h %s | %(trailers:key=Freigegeben-von,valueonly,separator=%x2C)' ausgangsstand~0..HEAD
  "${compose[@]}" exec -T vorfuehrung-db psql -X -q -At -U statistik -d statistik_vorfuehrung \
    -c "select 'Läufe ' || (select count(*) from meta.lauf) || ', Vorschläge ' || (select count(*) from meta.vorschlag) || ', offen ' || (select count(*) from meta.vorschlag where status = 'offen')" </dev/null
  df -h --output=avail "$basis" | tail -n 1 | sed 's/^/Platte frei: /'
  free -h | sed -n 2p
}
haupt "$@"
EOF
}

# Basic-Auth über eine Konfiguration auf stdin (curl -K -): der Wert steht nie in der Prozessliste
mit_zugang() {
  printf 'user = "%s:%s"\n' "$NUTZER" "$(lokal_wert VORFUEHRUNG_ZUGANG)" | curl -K - "$@"
}

cmd_pruefen() {
  lade_env_lokal
  local code fehler=0 pfad antwort ziel="https://$V_DOMAIN"
  [[ -n $(lokal_wert VORFUEHRUNG_ZUGANG) ]] || { echo "pruefen: VORFUEHRUNG_ZUGANG fehlt" >&2; return 1; }

  code=$(curl -sS -o /dev/null -w '%{http_code}' --max-time 30 "$ziel/uc3") || code=000
  if [[ $code == 401 ]]; then echo "pruefen: ohne Zugang 401"; else echo "pruefen: ohne Zugang $code statt 401" >&2; fehler=1; fi
  code=$(curl -sS -o /dev/null -w '%{http_code}' --max-time 30 -X POST -H 'content-type: application/json' -d '{}' "$ziel/api/uc3/auftrag") || code=000
  if [[ $code == 401 ]]; then echo "pruefen: POST ohne Zugang 401"; else echo "pruefen: POST ohne Zugang $code statt 401" >&2; fehler=1; fi

  for pfad in / /uc3 /uc3/auftrag /uc3/freigaben /uc3/fragen /uc4; do
    code=$(mit_zugang -sS -o /dev/null -w '%{http_code}' --max-time 60 "$ziel$pfad") || code=000
    if [[ $code == 200 ]]; then echo "pruefen: GET $pfad 200"; else echo "pruefen: GET $pfad $code statt 200" >&2; fehler=1; fi
  done
  # leerer Auftrag: 400 aus der App, ohne Lauf und ohne Modell; belegt, dass Schreibwege offen sind
  code=$(mit_zugang -sS -o /dev/null -w '%{http_code}' --max-time 30 -X POST -H 'content-type: application/json' -d '{}' "$ziel/api/uc3/auftrag") || code=000
  if [[ $code == 400 ]]; then echo "pruefen: POST Auftrag erreicht die App (400)"; else echo "pruefen: POST Auftrag $code statt 400" >&2; fehler=1; fi

  # Die öffentliche Demo bleibt zu: Auftrag und Freigabe weist die Kante ab, die Seite gibt es dort nicht
  for pfad in /api/uc3/auftrag /api/uc3/freigabe; do
    antwort=$(curl -sS -w ' %{http_code}' --max-time 20 -X POST -H 'content-type: application/json' -d '{}' "https://$DOMAIN$pfad") || antwort="kein-netz 000"
    if [[ $antwort == "Die Online-Demo ist lesend. 403" ]]; then echo "pruefen: öffentlich POST $pfad gesperrt"; else echo "pruefen: öffentlich POST $pfad kommt durch (HTTP ${antwort##* })" >&2; fehler=1; fi
  done
  code=$(curl -sS -o /dev/null -w '%{http_code}' --max-time 20 "https://$DOMAIN/uc3/auftrag") || code=000
  if [[ $code == 404 ]]; then echo "pruefen: öffentlich /uc3/auftrag 404"; else echo "pruefen: öffentlich /uc3/auftrag $code statt 404" >&2; fehler=1; fi
  code=$(curl -sS -o /dev/null -w '%{http_code}' --max-time 20 "https://$DOMAIN/api/uc3/auftrag") || code=000
  if [[ $code == 403 ]]; then echo "pruefen: öffentlich GET Auftrag 403"; else echo "pruefen: öffentlich GET Auftrag $code statt 403" >&2; fehler=1; fi
  return "$fehler"
}

case "${1:-}" in
  zugang) cmd_zugang ;;
  init) lade_ziel; cmd_init ;;
  up) lade_ziel; cmd_up "${2:-}" ;;
  daten) lade_ziel; cmd_daten "${2:-}" ;;
  reset) lade_ziel; cmd_reset ;;
  pensionen-freigeben) lade_ziel; cmd_pensionen_freigeben "${2:-}" ;;
  festschreiben) lade_ziel; cmd_festschreiben ;;
  pruefen) lade_ziel; cmd_pruefen ;;
  status) lade_ziel; cmd_status ;;
  *)
    sed -n '2,16p' "$0"
    exit 2
    ;;
esac
