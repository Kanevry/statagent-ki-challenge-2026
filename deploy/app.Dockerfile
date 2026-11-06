# syntax=docker/dockerfile:1.7
# App-Image der Online-Demo (#68): Next.js-Web (standalone) plus Python-Workspace
# (plattform, uc1 bis uc3). Die Route-Handler starten die Python-CLIs als Subprozess (`uv run …`, Vertrag H im PRD E0),
# deshalb laufen Node und uv im selben Image. Gebaut wird auf dem Server (scripts/deploy.sh up), nicht lokal.
# Kontext: Repo-Wurzel aus git archive von HEAD, also nur committete Dateien; davon nimmt die Positivliste
# deploy/app.Dockerfile.dockerignore nur, was das Image braucht (nicht docs/, deploy/, Erzeugtes; aus abgabe/ nur drei Dateien für /uc3/ergebnisse).

# Digests gepinnt (Index für amd64/arm64), Stand 05.11.2026
ARG NODE_IMAGE=node:24-bookworm-slim@sha256:01d566e8d94d8c619591d78652babfccd3c6992a3dffa9ed5ab39e11cf6c70e9
ARG UV_IMAGE=ghcr.io/astral-sh/uv:python3.12-bookworm-slim@sha256:e5b65587bce7de595f299855d7385fe7fca39b8a74baa261ba1b7147afa78e58

# --- Web bauen ----------------------------------------------------------------------------------------------------
FROM ${NODE_IMAGE} AS web-bau
WORKDIR /bau
ENV NEXT_TELEMETRY_DISABLED=1
RUN corepack enable
COPY package.json pnpm-lock.yaml pnpm-workspace.yaml ./
COPY web/package.json web/
COPY shared/ui/package.json shared/ui/
RUN --mount=type=cache,target=/root/.local/share/pnpm/store pnpm install --frozen-lockfile
COPY web web
# ganz shared/: web importiert neben @kic/ui auch shared/schema (Fixtures, JSON-Verträge)
COPY shared shared
# Kein Schlüssel beim Build: der Vapi-Schlüssel kommt zur Laufzeit über /api/plattform/voice-config (nur bei aktivem
# Voice), nie in den Browser-Code des Builds.
RUN mkdir -p web/public && pnpm --filter web build

# --- Python-Workspace ----------------------------------------------------------------------------------------------
FROM ${UV_IMAGE} AS py-bau
WORKDIR /app
ENV UV_LINK_MODE=copy UV_COMPILE_BYTECODE=1 UV_PYTHON_DOWNLOADS=never
# ganzer Kontext, weil uc1/ uc2/ uc3/ erst nach und nach entstehen (COPY mit Muster ohne Treffer bricht ab)
COPY . .
RUN --mount=type=cache,target=/root/.cache/uv uv sync --frozen --all-packages --no-dev

# --- Laufzeit -----------------------------------------------------------------------------------------------------
# Ohne git und ohne .git (Kontext aus git archive): plattform.freigabe und der Protokoll-Export aus git log
# laufen online nicht. Die Online-Demo ist damit lesend; schreibende Wege gehören lokal vorgeführt (#68).
FROM ${UV_IMAGE} AS laufzeit
COPY --from=web-bau /usr/local/bin/node /usr/local/bin/node
RUN groupadd --system --gid 1001 app && useradd --system --uid 1001 --gid app --home-dir /app app
WORKDIR /app
# Einziger beschreibbarer Ordner (Volume app_protokoll, #100): ein neues Volume übernimmt Besitzer app von hier
RUN mkdir -p /app/var/protokoll && chown app:app /app/var/protokoll && chmod 0700 /app/var/protokoll
# Code gehört root und ist nur lesbar für den Laufzeitnutzer app: er kann ihn nicht ändern (Compose: read_only)
COPY --from=py-bau /app /app
# standalone spiegelt die Repo-Wurzel (outputFileTracingRoot): web/server.js, node_modules, shared/ui
COPY --from=web-bau /bau/web/.next/standalone /app
# Next 16.4.5 (Turbopack) lässt in standalone Server-Chunks aus, die _not-found und _global-error brauchen
# (gemessen 05.11.2026: ChunkLoadError "[root-of-the-server]__….js", jede Anfrage 500). Deshalb .next/server vollständig.
COPY --from=web-bau /bau/web/.next/server /app/web/.next/server
COPY --from=web-bau /bau/web/.next/static /app/web/.next/static
COPY --from=web-bau /bau/web/public /app/web/public
ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1 \
    HOSTNAME=0.0.0.0 \
    PORT=3000 \
    PATH=/app/.venv/bin:$PATH \
    UV_NO_SYNC=1 \
    UV_OFFLINE=1 \
    UV_CACHE_DIR=/tmp/uv-cache
USER app
EXPOSE 3000
CMD ["node", "web/server.js"]
