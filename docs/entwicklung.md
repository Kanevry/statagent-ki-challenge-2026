# Entwicklung

## Aufbau

Ein Monorepo: eine Next.js-App (`web/`) mit Header-Wechsel zwischen Übersicht, UC1, UC2, UC3 und Präsentation;
ein gemeinsamer Kern in `shared/` (Python-Paket `plattform`, TS-Paket `@kic/ui`); je UC ein Python-Paket
(`uc1/`, `uc2/`, `uc3/`) mit eigener Datenbank auf PostgreSQL 5433. Alle Modellaufrufe laufen über
`plattform.llm`, Zahlen rechnet immer die Datenbank.

## Einrichten

```bash
cp .env.example .env.local            # Werte eintragen, nie committen
bash scripts/install-hooks.sh         # gitleaks als pre-commit-Hook
uv sync --all-packages                # Python-Workspace (shared/py, uc*)
pnpm install                          # TS-Workspace (web, shared/ui)
pnpm dev                              # Next.js auf http://localhost:3000, lädt ../.env.local
uv run pytest -q                      # shared/py; je UC: cd ucN && uv run pytest -q (lokal inkl. daten)
pnpm typecheck && pnpm test           # tsgo und Vitest in allen TS-Paketen
```

In einem zusätzlichen Git-Worktree findet `plattform.umgebung` die `.env.local` des Haupt-Checkouts selbst; für
`pnpm dev` die Datei in den Worktree verlinken.

## Arbeitsteilung (parallele Sessions)

- Je Session ein eigener Worktree, je Worktree ein Branch, Merge nur per Merge Request.
- Jede Session schreibt nur in ihrem Bereich (Tabelle in `CLAUDE.md`): Die Plattform besitzt Wurzel-Dateien, CI,
  `shared/**`, `web/app/layout.tsx` und `web/app/praesentation/`. Die Landingpage besitzt `web/app/(landing)/`,
  `web/landing/` und `web/public/landing/`. Jeder Use Case besitzt `uc<N>/**`, `web/app/uc<N>/**`,
  `web/app/api/uc<N>/**` und `web/components/uc<N>/**`. Die Registry `shared/ui/src/ucs.ts` gehört der Plattform.
- Einhängen eines Use Case in die Shell: `web/app/<uc>/layout.tsx` mit `<UcBereich>` plus `page.tsx`, dazu
  `web/app/api/<uc>/protokoll/route.ts`. Liefert der Handler nichts, zeigt die Shell den Leerzustand.
- Abhängigkeiten: Python-Pakete trägt jeder Use Case nur in seine eigene `ucN/pyproject.toml` ein; `uv lock` an der
  Wurzel läuft nach dem Rebase durch den Bereich, der zuletzt mergt, und das `uv.lock` ist Teil seines Merge
  Requests (nie von Hand auflösen). `web/package.json` und `pnpm-lock.yaml` ändert nur die Plattform.
