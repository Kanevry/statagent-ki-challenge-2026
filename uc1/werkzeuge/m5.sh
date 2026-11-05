#!/usr/bin/env bash
# Hilfsskript für den Vollindex auf m5 (#29). Liegt auf m5 unter ~/scratch/b-uc1/m5.sh (per scp kopiert),
# kein Checkout dort. Aufruf vom M4: ssh m5-remote 'bash ~/scratch/b-uc1/m5.sh <befehl>'.
#
# Befehle:
#   entpacken       uc1-code.tgz nach uc1/, abschnitte.tgz nach vollindex/
#   korpus          svbox-uc1.tgz (gepackt mit werkzeuge/tar_nfc.py) nach svbox-uc1-nfc/
#   berechnen       Vollindex im Hintergrund (nohup), Log unter log/berechnen.log, PID in log/berechnen.pid
#   packen          Vektordateien als vektoren.tgz zum Abholen per scp
#   pg-init         eigene PG18-Instanz in pg/ (Port 5434, nur localhost, Rolle und DB per scram)
#   pg-start        Instanz starten (Log pg/server.log)
#   pg-stop         Instanz anhalten (pg_ctl stop -m fast)
#   pg-status       pg_ctl status samt PID
#   ingest          lotse db-init und lotse ingest gegen die m5-DB, Ausgabe nach log/ingest.log
#   import          Vektoren aus vollindex/ nach lotse.vektor der m5-DB, danach status
#   hashliste       dokid, nr, text_hash je Abschnitt nach log/hashliste.tsv
#   export          Export aus der m5-DB nach log/abschnitte-m5.jsonl samt Prüfsumme
#   status          python -m uc1.vektoren status gegen die m5-DB
#   repo-packen     NUR AUF DEM M4, im Checkout: git archive (HEAD) von pyproject.toml, uv.lock,
#                   .python-version, shared/py, uc1 plus geänderte und neue Dateien dieser Pfade
#                   (ohne Ignoriertes) als uc1/laufzeit/repo.tar; danach per scp nach m5
#   repo-entpacken  repo.tar nach repo/ (überschreibt), dann uv sync --package uc1 --extra embed
#   messen ARGS     Suchmessung (werkzeuge/messen.py ARGS) aus repo/uc1 gegen die m5-DB, MPS, HF offline,
#                   im Hintergrund; Log log/messen.log, PID log/messen.pid
set -euo pipefail

if [ "${1:-}" = "repo-packen" ]; then
  # Läuft auf dem M4 im Checkout, nicht auf m5.
  WURZEL="$(git rev-parse --show-toplevel)"
  cd "$WURZEL"
  mkdir -p uc1/laufzeit
  PFADE=(pyproject.toml uv.lock .python-version shared/py uc1)
  git archive --format=tar --output=uc1/laufzeit/repo.tar HEAD "${PFADE[@]}"
  git ls-files --modified --others --exclude-standard -- "${PFADE[@]}" | while IFS= read -r datei; do
    [ -f "$datei" ] && printf '%s\n' "$datei"
  done > uc1/laufzeit/repo-zusatz.txt
  [ -s uc1/laufzeit/repo-zusatz.txt ] && tar -rf uc1/laufzeit/repo.tar -T uc1/laufzeit/repo-zusatz.txt
  echo "uc1/laufzeit/repo.tar: $(git rev-parse --short HEAD) plus $(wc -l < uc1/laufzeit/repo-zusatz.txt | tr -d ' ') nicht committete Dateien"
  shasum -a 256 uc1/laufzeit/repo.tar
  rm -f uc1/laufzeit/repo-zusatz.txt
  exit 0
fi

BASIS="$HOME/scratch/b-uc1"
PGBIN=/opt/homebrew/opt/postgresql@18/bin
PGDATA="$BASIS/pg"
PORT=5434
URL="postgresql://statistik:statistik@localhost:$PORT/lotse"
PY="$BASIS/uc1/.venv/bin/python"
REPO="$BASIS/repo"
RPY="$REPO/.venv/bin/python"
# Korpus in NFC (siehe tar_nfc.py)
KORPUS="$BASIS/svbox-uc1-nfc"

cd "$BASIS"
mkdir -p log vollindex

case "${1:-}" in
  entpacken)
    tar xzf uc1-code.tgz --directory uc1
    [ -f abschnitte.tgz ] && tar xzf abschnitte.tgz --directory vollindex
    shasum -a 256 vollindex/abschnitte.jsonl
    ;;
  berechnen)
    cd uc1
    EMBED_MAX_TOKENS=2048 EMBED_DTYPE=float32 EMBED_DEVICE=mps EMBED_DIM=768 HF_HUB_OFFLINE=1 \
      nohup "$PY" -m uc1.vektoren berechnen --eingabe "$BASIS/vollindex/abschnitte.jsonl" \
      --ausgabe "$BASIS/vollindex/gemma2" --batch 8 > "$BASIS/log/berechnen.log" 2>&1 &
    echo $! > "$BASIS/log/berechnen.pid"
    echo "pid $(cat "$BASIS/log/berechnen.pid")"
    ;;
  korpus)
    # Korpus mit Python-tarfile entpacken: bsdtar legte Umlaut-Namen als NFD an (siehe tar_nfc.py)
    "$PY" -I "$BASIS/tar_nfc.py" entpacken svbox-uc1.tgz svbox-uc1-nfc
    ;;
  packen)
    tar czf vektoren.tgz --directory vollindex gemma2.hashes.txt gemma2.768.npy gemma2.meta.json
    ls -l vektoren.tgz vollindex/gemma2.768.npy vollindex/gemma2.hashes.txt
    shasum -a 256 vollindex/gemma2.768.npy vollindex/gemma2.hashes.txt
    ;;
  pg-init)
    if [ ! -f "$PGDATA/PG_VERSION" ]; then
      PWDATEI="$(mktemp)"
      echo statistik > "$PWDATEI"
      "$PGBIN/initdb" -D "$PGDATA" -U statistik --pwfile="$PWDATEI" --auth=scram-sha-256 -E UTF8 \
        --locale=C > log/initdb.log
      rm -f "$PWDATEI"
      {
        echo "listen_addresses = 'localhost'"
        echo "port = $PORT"
        echo "unix_socket_directories = '$PGDATA'"
      } >> "$PGDATA/postgresql.conf"
    fi
    bash "$0" pg-start
    PGPASSWORD=statistik "$PGBIN/psql" -h localhost -p $PORT -U statistik -d postgres -tAc \
      "SELECT 1 FROM pg_database WHERE datname = 'lotse'" | grep -q 1 \
      || PGPASSWORD=statistik "$PGBIN/createdb" -h localhost -p $PORT -U statistik lotse
    echo "db lotse bereit auf Port $PORT"
    ;;
  pg-start)
    "$PGBIN/pg_ctl" -D "$PGDATA" status > /dev/null 2>&1 || "$PGBIN/pg_ctl" -D "$PGDATA" -l "$PGDATA/server.log" -w start
    "$PGBIN/pg_ctl" -D "$PGDATA" status
    ;;
  pg-stop)
    "$PGBIN/pg_ctl" -D "$PGDATA" -m fast -w stop
    ;;
  pg-status)
    "$PGBIN/pg_ctl" -D "$PGDATA" status
    ;;
  ingest)
    # Workspace-Stand aus repo/ (repo-entpacken), sonst der alte Stand in uc1/
    if [ -x "$RPY" ]; then cd "$REPO/uc1"; IPY="$RPY"; else cd uc1; IPY="$PY"; fi
    UC1_DATABASE_URL="$URL" LOTSE_DATABASE_URL="$URL" "$IPY" -m uc1.cli db-init
    UC1_DATABASE_URL="$URL" LOTSE_DATABASE_URL="$URL" UC1_DATA_DIR="$KORPUS" \
      nice -n 10 "$IPY" -m uc1.cli ingest > "$BASIS/log/ingest.log" 2>&1
    tail -20 "$BASIS/log/ingest.log"
    ;;
  repo-entpacken)
    mkdir -p "$REPO"
    tar -xf repo.tar --directory "$REPO"
    cd "$REPO"
    uv sync --package uc1 --extra embed > "$BASIS/log/uv-sync.log" 2>&1
    tail -3 "$BASIS/log/uv-sync.log"
    "$RPY" -c "import uc1, plattform, sentence_transformers; print('uc1 und plattform importierbar')"
    ;;
  messen)
    shift
    cd "$REPO/uc1"
    UC1_DATABASE_URL="$URL" UC1_DATA_DIR="$KORPUS" EMBED_DEVICE=mps HF_HUB_OFFLINE=1 \
      nohup nice -n 5 "$RPY" werkzeuge/messen.py "$@" > "$BASIS/log/messen.log" 2>&1 &
    echo $! > "$BASIS/log/messen.pid"
    echo "pid $(cat "$BASIS/log/messen.pid")"
    ;;
  import)
    cd uc1
    LOTSE_DATABASE_URL="$URL" "$PY" -m uc1.vektoren import --prefix "$BASIS/vollindex/gemma2" --dims 768,256
    LOTSE_DATABASE_URL="$URL" "$PY" -m uc1.vektoren status
    ;;
  hashliste)
    # dokid, nr, text_hash je Abschnitt, für den Vergleich mit dem M4 (Inhalts-Hash)
    PGPASSWORD=statistik "$PGBIN/psql" -h localhost -p $PORT -U statistik -d lotse -c \
      "\\copy (SELECT d.dokid, a.nr, a.text_hash, d.datei FROM lotse.abschnitt a JOIN lotse.dokument d ON d.id = a.dokument_id ORDER BY 1, 2) TO '$BASIS/log/hashliste.tsv'"
    wc -l log/hashliste.tsv
    ;;
  export)
    # Export aus der m5-DB, zum Vergleich mit dem Export des M4 (gleiche Prüfsumme erwartet)
    cd uc1
    LOTSE_DATABASE_URL="$URL" "$PY" -m uc1.vektoren export --ausgabe "$BASIS/log/abschnitte-m5.jsonl"
    shasum -a 256 "$BASIS/log/abschnitte-m5.jsonl"
    ;;
  status)
    cd uc1
    LOTSE_DATABASE_URL="$URL" "$PY" -m uc1.vektoren status
    ;;
  *)
    sed -n '2,23p' "$0"
    exit 2
    ;;
esac
