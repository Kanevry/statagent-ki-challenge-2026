#!/bin/bash
# Stößt den schweren Lauf auf dem Prüfrechner an und holt die Laufdatei zurück (docs/abnahme/PROZESS.md, Rhythmus).
#
#   bash tests/abnahme/schwer_ausloesen.sh <env-datei> [<kriterium>]
#
# Die env-Datei liegt außerhalb des Repos (öffentliches Repo: keine Hostnamen, keine Pfade fremder Rechner) und setzt
#   PRUEFRECHNER       ssh-Alias des Prüfrechners
#   PRUEFRECHNER_DIR   Ordner mit abnahme.env und schwer_pruefrechner.sh auf dem Prüfrechner
#   PRUEFRECHNER_VOR   optional: Vorsatz für den Lauf, etwa „nice -n 10 taskset -c 0-5“ auf einem geteilten Rechner
# Läuft nur, wenn sich main seit dem letzten schweren Lauf in UC3-Pfaden geändert hat; nie zwei gleichzeitig.
# Mit <kriterium> läuft nur dieser Prüfsatz (`einzeln = true`), immer, und ändert den Stand des letzten Laufs nicht.
# Mit ABNAHME_ZIEL_SHA misst der Lauf einen MR-Kopf statt main (Vorprüfung, Ref refs/remotes/origin/pruef-ziel);
# die Laufdatei geht dann nach ABNAHME_ZIEL_ABLAGE, nie in docs/abnahme/laeufe: sie ist kein Beleg für main.
set -euo pipefail
cd "$(dirname "$0")/../.."
# shellcheck source=/dev/null
. "${1:?env-Datei fehlt}"
nur_id="${2:-}"
: "${PRUEFRECHNER:?}" "${PRUEFRECHNER_DIR:?}"
# Eigene Verbindungen, nie der geteilte SSH-Master.
SSH_OPT=(-o ConnectTimeout=10 -o ControlMaster=no -o ControlPath=none)
sperre="/tmp/kic-abnahme-schwer.lock"
mkdir "$sperre" 2>/dev/null || { echo "schwerer Lauf läuft schon"; exit 0; }
trap 'rmdir "$sperre"' EXIT
stand_datei="/tmp/kic-abnahme-schwer.letzter"
sha="${ABNAHME_ZIEL_SHA:-$(git rev-parse origin/main)}"
werkzeug="$(git rev-parse HEAD)"
if [ -z "$nur_id" ] && [ -s "$stand_datei" ] && git diff --quiet "$(cat "$stand_datei")" "$sha" -- uc3 abgabe docs/plan/uc3 shared \
  pyproject.toml uv.lock tests/abnahme/orakel; then
  echo "schwer: keine UC3-Änderung seit $(cut -c1-8 "$stand_datei")"
  exit 0
fi
tmp="$(mktemp -d /tmp/kic-abnahme-schwer.XXXXXX)"
git bundle create -q "$tmp/abnahme.bundle" refs/remotes/origin/main "refs/heads/$(git rev-parse --abbrev-ref HEAD)" \
  ${ABNAHME_ZIEL_SHA:+refs/remotes/origin/pruef-ziel}
uv run python -c "import json,sys; sys.path.insert(0,'tests/abnahme'); import matrix; \
json.dump(matrix.issues_holen(None), open('$tmp/issues.json','w'))"
timeout 600 scp -q "${SSH_OPT[@]}" "$tmp/abnahme.bundle" "$tmp/issues.json" tests/abnahme/schwer_pruefrechner.sh "$PRUEFRECHNER:$PRUEFRECHNER_DIR/"
echo "schwer: Lauf startet für main ${sha:0:8} $(TZ=Europe/Vienna date '+%H:%M')"
# Der Lauf arbeitet auf dem Prüfrechner losgelöst und überlebt einen Abbruch der Verbindung (20:31 und 21:11 riss
# sie ab; damals endete der Lauf mit ihr). Hier wird nur noch mit kurzen Verbindungen nachgesehen.
log="$PRUEFRECHNER_DIR/lauf.log"
timeout 60 ssh "${SSH_OPT[@]}" "$PRUEFRECHNER" "nohup bash -c '${PRUEFRECHNER_VOR:-} bash $PRUEFRECHNER_DIR/schwer_pruefrechner.sh $PRUEFRECHNER_DIR/abnahme.bundle $sha $werkzeug \
  $PRUEFRECHNER_DIR/issues.json $nur_id > $log 2>&1; echo schwer-ende-\$? >> $log' > /dev/null 2>&1 < /dev/null &"
ende=""
for _ in $(seq 1 120); do
  sleep 30
  ende="$(timeout 40 ssh "${SSH_OPT[@]}" "$PRUEFRECHNER" "tail -1 $log" 2>/dev/null || true)"
  case "$ende" in schwer-ende-*) break ;; *) ende="" ;; esac
done
timeout 120 scp -q "${SSH_OPT[@]}" "$PRUEFRECHNER:$log" "$tmp/lauf.log" || true
if [ "$ende" = "schwer-ende-0" ]; then
  datei="$(tail -2 "$tmp/lauf.log" | head -1)"
  timeout 120 scp -q "${SSH_OPT[@]}" "$PRUEFRECHNER:$PRUEFRECHNER_DIR/repo/docs/abnahme/laeufe/$datei" "${ABNAHME_ZIEL_ABLAGE:-docs/abnahme/laeufe}/${datei%.jsonl}-schwer.jsonl"
  # Der Prüfrechner kennt die Sperrnamen nicht: die Laufdatei hier mit der vollen Liste schwärzen.
  uv run python -c "import json,sys; sys.path.insert(0,'tests/abnahme'); import matrix; \
p=sys.argv[1]; z=[json.loads(l) for l in open(p) if l.strip()]; \
r=lambda x: matrix.schwaerzen(x) if isinstance(x,str) else [r(y) for y in x] if isinstance(x,list) else \
{k: r(v) for k,v in x.items()} if isinstance(x,dict) else x; \
open(p,'w').write(''.join(json.dumps(r(e),ensure_ascii=False)+'\\n' for e in z))" \
    "${ABNAHME_ZIEL_ABLAGE:-docs/abnahme/laeufe}/${datei%.jsonl}-schwer.jsonl"
  grep -E '^(Lauf|lauf_alle_exit)' "$tmp/lauf.log"
  [ -n "$nur_id" ] || echo "$sha" > "$stand_datei"
else
  echo "schwer: Lauf gescheitert (${ende:-kein Ende nach 60 min}), Log $tmp/lauf.log" >&2
  tail -5 "$tmp/lauf.log" >&2
  exit 1
fi
