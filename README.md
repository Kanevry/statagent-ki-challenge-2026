# ki-challenge-2026

Arbeitsrepo für die **KI Challenge 2026** des Dachverbands der Sozialversicherungsträger und der WK Wien
(Do 05.11. 10:00 bis Fr 06.11. ca. 13:15, Kundmanngasse 21, 1030 Wien). Team OneShotAndy, solo.

- **Abgabe:** öffentliches GitHub-Repo `KIChallenge/OneShotAndy` als zweiter Remote. Alles, was hier landet,
  muss dort veröffentlicht werden dürfen (keine Secrets, kein Code aus anderen Produkten, nur synthetische
  oder öffentliche Daten). Der Dachverband darf das Abgabe-Repo uneingeschränkt nutzen.
- **Plan:** Vault `05-business/career/hackathons-2026-27/ki-challenge/spielplan.md` (Einstieg), dort auch alle
  Rechercheberichte, das Startkit und die Click-Dummy-Spezifikationen. Vault-Issue agents/vault#427.
- **Schnittstellen:** `docs/prd/2026-11-05-e0-plattform-e1-uc3.md` (Ordner, Modell-Schalter, Protokoll und
  Freigabe, Header, Voice, Design).

## Use Cases (aus `KI-Challenge_UseCase.yaml`, Stand 03.11.)

| Kürzel | Name | Kurz |
|---|---|---|
| uc1 | SV KI-Lotse | Gesundheits- und Sozialversicherungs-Chatbot |
| uc2 | HealthPolicy Simulator | Multi-Agenten-Simulator für politische, organisatorische und finanzielle Entscheidungen |
| uc3 | StatAgent | agentengestützter Statistikprozess (**bewertet**) |

## Aufbau

Ein Monorepo: eine Next.js-App (`web/`) mit Header-Wechsel zwischen Übersicht, UC1, UC2, UC3 und Präsentation;
ein gemeinsamer Kern in `shared/` (Python-Paket `plattform`, TS-Paket `@kic/ui`); je UC ein Python-Paket
(`uc1/`, `uc2/`, `uc3/`) mit eigener Datenbank auf PostgreSQL 5433. Alle Modellaufrufe laufen über
`plattform.llm` (`LLM_PROVIDER=azure|claude|mistral|ollama|mock`), Zahlen rechnet immer die Datenbank.

## Start

Voraussetzungen: Node 24, pnpm 10 (corepack), uv 0.12, PostgreSQL 16 auf Port 5433, gitleaks.

```bash
cp .env.example .env.local            # Werte eintragen, nie committen
bash scripts/install-hooks.sh         # gitleaks als pre-commit-Hook
uv sync --all-packages                # Python-Workspace (shared/py, uc*)
pnpm install                          # TS-Workspace (web, shared/ui)
pnpm dev                              # Next.js auf http://localhost:3000, lädt ../.env.local
uv run pytest -q                      # shared/py; je UC: cd ucN && uv run pytest -q (lokal inkl. daten)
pnpm typecheck && pnpm test           # tsgo und Vitest in allen TS-Paketen
```

In einem Worktree unter `_wt/` findet `plattform.umgebung` die `.env.local` des Haupt-Checkouts selbst; für
`pnpm dev` die Datei verlinken: `ln -s <Haupt-Checkout>/.env.local .env.local`.

## Lanes (parallele Sessions)

- Je Session ein eigener Worktree, je Worktree ein Branch, Merge nur per MR.
- Jede Session schreibt nur in ihrer Lane (Tabelle in `CLAUDE.md`): E0 besitzt Wurzel-Dateien, CI, `shared/**`,
  `web/app/layout.tsx` und `web/app/praesentation/`; die Landing-Session besitzt `web/app/(landing)/`,
  `web/landing/` und `web/public/landing/`; jede UC-Session besitzt `uc<N>/**`, `web/app/uc<N>/**`,
  `web/app/api/uc<N>/**` und `web/components/uc<N>/**` sowie ihren eigenen Eintrag in `shared/ui/src/ucs.ts`.
- Abhängigkeiten: Python-Pakete trägt jede UC-Lane nur in ihre eigene `ucN/pyproject.toml` ein; `uv lock` an der
  Wurzel läuft nach dem Rebase durch die Lane, die zuletzt mergt, und das `uv.lock` ist Teil ihres MR (nie von
  Hand auflösen). `web/package.json` und `pnpm-lock.yaml` ändert nur E0; UC-Lanes stellen dafür einen Antrag in #53.

## Herkunft

- Das Voice-Konzept (Vapi Custom LLM, Webhook, Text-Fallback) folgt dem vorab entstandenen Projekt
  `everlast-voice-interviewer` des Teams; übernommen sind nur Konzept und Verträge, der Code hier entsteht neu.
  Keine `@goetzendorfer/*`-Pakete.
- Vapi ist ein US-Dienst: an Vapi gehen nur Aggregate mit Beleg, nie Einzeldaten.

## Labels

`uc1`, `uc2`, `uc3` (Raum), `kern` (gemeinsam), `ablauf` (Termine, Abgabe, Pitch), `owner` (Handgriff des Owners).
