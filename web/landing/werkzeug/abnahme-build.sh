#!/usr/bin/env bash
# Abnahme der Landingpage im Produktions-Build: Build, Server, Screenshots, measureSlop, Lighthouse.
# Gedacht für einen Rechner mit freier CPU (Build und Lighthouse sind rechenintensiv).
# Aufruf aus dem Repo-Wurzelordner:
#   bash web/landing/werkzeug/abnahme-build.sh <ausgabe-ordner> <slop-measure.js> [port]
# Ergebnis: PNGs, abnahme.json, lighthouse-{mobil,desktop}.json und lighthouse.txt im Ausgabe-Ordner.
set -euo pipefail
AUSGABE=${1:?Ausgabe-Ordner fehlt}
SLOP=${2:?Pfad zu slop-measure.js fehlt}
PORT=${3:-3987}
mkdir -p "$AUSGABE"
AUSGABE=$(cd "$AUSGABE" && pwd)

cd web
nice -n 5 pnpm exec next build > "$AUSGABE/build.log" 2>&1 || { tail -40 "$AUSGABE/build.log"; exit 3; }
pnpm exec next start -p "$PORT" > "$AUSGABE/start.log" 2>&1 &
SERVER=$!
trap 'kill $SERVER 2>/dev/null || true' EXIT
for _ in $(seq 1 40); do curl -sf -o /dev/null "http://localhost:$PORT/" && break; sleep 0.5; done

pnpm exec playwright install chromium > /dev/null 2>&1 || true
node landing/werkzeug/abnahme.mjs "http://localhost:$PORT" "$AUSGABE" "$SLOP"

CHROME_PATH=$(node -e 'import("@playwright/test").then(m => console.log(m.chromium.executablePath()))')
export CHROME_PATH
LH="pnpm dlx lighthouse@12"
$LH "http://localhost:$PORT/" --quiet --chrome-flags="--headless=new" \
  --only-categories=performance,accessibility,best-practices,seo \
  --output=json --output-path="$AUSGABE/lighthouse-mobil.json" || true
$LH "http://localhost:$PORT/" --quiet --chrome-flags="--headless=new" --preset=desktop \
  --only-categories=performance,accessibility,best-practices,seo \
  --output=json --output-path="$AUSGABE/lighthouse-desktop.json" || true
node -e '
const fs = require("fs");
for (const f of ["mobil", "desktop"]) {
  const p = process.argv[1] + "/lighthouse-" + f + ".json";
  if (!fs.existsSync(p)) { console.log(f + ": kein Bericht"); continue; }
  const r = JSON.parse(fs.readFileSync(p, "utf8"));
  const s = Object.fromEntries(Object.entries(r.categories).map(([k, v]) => [k, Math.round(v.score * 100)]));
  const a = r.audits;
  console.log(f + ": " + JSON.stringify(s) + " LCP " + a["largest-contentful-paint"].displayValue + " TBT " + a["total-blocking-time"].displayValue + " CLS " + a["cumulative-layout-shift"].displayValue);
}' "$AUSGABE" | tee "$AUSGABE/lighthouse.txt"
