#!/usr/bin/env bash
# cloudflared-Quick-Tunnel auf die lokale Voice-/UC-FastAPI (Vertrag V, #61).
#
#   scripts/tunnel.sh [PORT]     # Standard 8101; Voice-Demo uc4: 8104
#
# Druckt PUBLIC_URL=<https-Adresse>, sobald cloudflared sie zugewiesen hat, und läuft weiter, bis Strg+C.
# Die Adresse wechselt bei jedem Start: danach PUBLIC_URL in .env.local eintragen und
# `uv run python -m plattform.voice sync` ausführen (Außenwirkung, nur mit Freigabe).
set -euo pipefail

port="${1:-8101}"
if ! [[ "$port" =~ ^[0-9]+$ ]]; then
  echo "Port muss eine Zahl sein: $port" >&2
  exit 2
fi
if ! command -v cloudflared >/dev/null 2>&1; then
  echo "cloudflared fehlt: brew install cloudflared (oder https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/)" >&2
  exit 1
fi

log="$(mktemp -t kic-tunnel.XXXXXX)"
cloudflared tunnel --no-autoupdate --url "http://127.0.0.1:${port}" >"$log" 2>&1 &
pid=$!
aufraeumen() {
  kill "$pid" 2>/dev/null || true
  wait "$pid" 2>/dev/null || true
  rm -f "$log"
}
trap aufraeumen EXIT INT TERM

url=""
for _ in $(seq 1 60); do
  url="$(grep -Eo 'https://[a-z0-9-]+\.trycloudflare\.com' "$log" | head -n 1 || true)"
  [[ -n "$url" ]] && break
  if ! kill -0 "$pid" 2>/dev/null; then
    echo "cloudflared ist beendet, bevor eine Adresse kam (Log: $log)" >&2
    trap - EXIT
    exit 1
  fi
  sleep 0.5
done
if [[ -z "$url" ]]; then
  echo "Keine trycloudflare-Adresse nach 30 s (Log: $log)" >&2
  trap - EXIT
  kill "$pid" 2>/dev/null || true
  exit 1
fi

echo "PUBLIC_URL=${url}"
echo "danach: PUBLIC_URL in .env.local eintragen, dann uv run python -m plattform.voice sync"
echo "Tunnel läuft auf Port ${port}, beenden mit Strg+C."
wait "$pid"
