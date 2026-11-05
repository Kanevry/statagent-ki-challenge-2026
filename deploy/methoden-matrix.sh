#!/usr/bin/env bash
# Methodenmatrix der Kante (Review !94): startet Caddy mit dem echten Caddyfile auf http://localhost:8080 (Inhalt
# platzhalter, kein TLS) und prüft, welche Anfragen Caddy selbst mit 403 „lesend“ abweist. Erlaubt sind nur GET und
# HEAD überall und POST auf genau /api/uc3/frage und /api/uc4/frage. Läuft im CI-Job deploy-check (Image caddy).
set -euo pipefail

export SITE_ADDRESS="http://localhost:8080" INHALT=platzhalter
mkdir -p /srv/platzhalter
cp -R deploy/platzhalter/. /srv/platzhalter/
caddy start --config /etc/caddy/Caddyfile --adapter caddyfile >/dev/null 2>&1
trap 'caddy stop >/dev/null 2>&1 || true' EXIT
for _ in $(seq 1 20); do curl -s -o /dev/null http://localhost:8080/ && break; sleep 0.5; done

fehler=0
# erwartet: "sperrt" (403 mit dem Satz der Kante) oder "durch" (Caddy reicht an den Inhalt weiter)
pruefe() {
  local methode=$1 pfad=$2 erwartet=$3 antwort code ergebnis
  antwort=$(curl -s -X "$methode" -d 'frage=x' -w '\n%{http_code}' "http://localhost:8080$pfad")
  code=${antwort##*$'\n'}
  if [[ $code == 403 && $antwort == *"Die Online-Demo ist lesend."* ]]; then ergebnis=sperrt; else ergebnis=durch; fi
  if [[ $ergebnis == "$erwartet" ]]; then
    echo "ok     $methode $pfad → $ergebnis ($code)"
  else
    echo "FEHLER $methode $pfad → $ergebnis ($code), erwartet $erwartet" >&2
    fehler=1
  fi
}

pruefe GET / durch
pruefe POST /api/uc4/frage durch
pruefe POST /api/uc3/frage durch
for methode in PUT PATCH DELETE OPTIONS; do
  pruefe "$methode" /api/uc4/frage sperrt
  pruefe "$methode" /api/uc3/frage sperrt
done
for pfad in /api/uc3/freigabe /api/uc2/faelle /api/uc4/frage/ /api/uc4/fragen /api/uc3/frage/x /api/probe /; do
  pruefe POST "$pfad" sperrt
done
exit "$fehler"
