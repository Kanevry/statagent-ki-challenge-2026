# OneShotAndy, KI Challenge 2026 (bewertet: Use Case 3 StatAgent)

Ein Monorepo, drei Räume auf einem gemeinsamen Kern: UC3 StatAgent (agentengestützter Statistikprozess für eine
synthetische Beschäftigtenstatistik des Dachverbands der österreichischen Sozialversicherungsträger, **bewertet**),
UC1 SV KI-Lotse und UC2 HealthPolicy Simulator (Zusatz). Team OneShotAndy. Abgabe Fr 06.11.2026 09:00
(SV-Box-Teamordner) und im öffentlichen GitHub-Repo `KIChallenge/OneShotAndy`. Dieses Repo ist öffentlich: keine
Secrets, keine personenbezogenen Daten, kein Code aus anderen Produkten.

Schnittstellen-SSOT: `docs/prd/2026-11-05-e0-plattform-e1-uc3.md` (Verträge O, M, P, H, V, D).

## Leitlinien

- **Die KI schreibt Code, das Programm rechnet.** Zahlen entstehen nur durch Code, der ohne Sprachmodell
  läuft; zwei Läufe mit denselben Daten und Regeln liefern dieselben Zahlen. `uc3 lauf` importiert
  `plattform.llm` nicht (Regel R2 offline).
- **Lokal und offline:** PostgreSQL 16 auf Port **5433** (nativ oder `docker compose` mit `DB_PORT=5433`; auf 5432
  lauscht ein fremder Postgres). Je UC eine Datenbank (`UC1_DATABASE_URL`, `UC2_DATABASE_URL`, `UC3_DATABASE_URL`).
  UC3: DB/User/PW `statistik`, Rohdaten in `roh.lieferung`, Klassifikationen in `klassifikation.*`.
- **Regeln als Daten:** Einlese-, Prüf- und Zählregeln liegen in `meta.regel`, versioniert mit Gültigkeit,
  Begründung und Freigabe. Keine Zuordnung als Konstante im Code.
- **Mensch gibt frei:** Jede Regel- oder Codeänderung und jede Lieferung wird mit Vor- und Nachnamen und
  Zeitpunkt freigegeben (`plattform.freigabe`, CLI `freigabe --name`), Commit-Trailer `Freigegeben-von: Name`.
  „Team“ wird abgelehnt.
- **Eigene Agenten setzen Änderungsaufträge um,** nicht das Entwicklungswerkzeug. Alle Modellaufrufe laufen über
  `plattform.llm` mit `LLM_PROVIDER=azure|claude|mistral|ollama|mock`, austauschbar: `azure` (we-16) ist Standard
  und Pflicht für UC3-Agenten, `claude` (`claude -p`, Abo) nur UC1/UC2-Qualitätsmodus und Vergleiche, nie im
  UC3-Lauf. `web/` ruft nie ein Modell direkt. Keine Einzeldaten an das Modell.
- Ein Lauf = eine Lieferung (`lauf --lieferung JJJJ-MM`), nur eigene und frühere Lieferungen; veröffentlichte
  Monate bleiben unverändert, Abweichungen stehen als Revisionsbedarf im Qualitätsbericht.
- **Ausnahme everlast:** `everlast-voice-interviewer` dient nur als Konzept für Voice (Owner 05.11. 12:4x). Code
  entsteht hier neu und ist im README als vorab entstandenes Konzept ausgewiesen; keine `@goetzendorfer/*`-Pakete.

## Struktur und Lanes

| Pfad | Inhalt | Lane |
|---|---|---|
| `package.json`, `pnpm-workspace.yaml`, `pyproject.toml`, `pnpm-lock.yaml`, `.gitlab-ci.yml` | Workspace-Wurzel, CI | E0 |
| `uv.lock` | Python-Lockfile der Wurzel | die Lane, die zuletzt mergt (Regel unten) |
| `web/` | Next.js-16-App (eine App): Configs, `app/layout.tsx`, `app/praesentation/` | E0 |
| `web/app/(landing)/`, `web/landing/`, `web/public/landing/` | Landingpage `/` (rendert ohne App-Header) | Landing-Session |
| `web/app/<uc>/**`, `web/app/api/<uc>/**`, `web/components/<uc>/**` | Seiten und Route-Handler je UC | UC-Session |
| `shared/py/plattform/` | Python-Paket `plattform`: llm, protokoll, freigabe, voice, embeddings, `sql/meta.sql` | E0 |
| `shared/ui/` | TS-Paket `@kic/ui`: tokens, basis, bausteine, shell, Registry `src/ucs.ts` | E0 (Registry: je UC nur der eigene Eintrag) |
| `uc1/`, `uc2/`, `uc3/` | je ein Python-Paket (uv-Member) mit CLI `uv run <uc> --help`; UC3: `uc3/statagent`, `uc3/db`, `uc3/tests` | UC-Session |
| `abgabe/` | erzeugte UC3-Ergebnisse: Aggregations-Sheet, Qualitätsberichte, Ministeriums-Lieferung, Protokoll | UC3 |
| `docs/` | PRD, Annahmen, `models.md` | alle |

Je Session ein Worktree, nur in der eigenen Lane schreiben. Abhängigkeiten (Entscheid Lead, 05.11.):
- **Python:** Jede UC-Lane trägt Pakete nur in ihrer eigenen `ucN/pyproject.toml` ein. `uv lock` an der Wurzel
  läuft nach dem Rebase durch die Lane, die zuletzt mergt; das aktualisierte `uv.lock` ist Teil ihres MR und wird
  im Review geprüft. Lockfile-Konflikte nie von Hand lösen, sondern `uv lock` neu laufen lassen.
- **Web:** `web/package.json` und `pnpm-lock.yaml` ändert nur E0. Eine UC-Lane, die ein Web-Paket braucht, stellt
  dafür einen Antrag als Kommentar in #53.

Plan und Herleitung: Vault `05-business/career/hackathons-2026-27/ki-challenge/uc3-bauplan.md`. Daten:
`../svbox/uc3/` (nicht im Repo). Zugänge nur in `.env.local` (nie lesen oder ausgeben, SEC-008).

## Session Config

- test-command: uv run pytest -q
- typecheck-command: timeout -k 5 300 pnpm -r exec tsgo --noEmit
- lint-command: uv run ruff check .
- agents-per-wave: 6
- waves: 4
- persistence: true
- enforcement: warn
- vcs: gitlab
- mirror: none
- recent-commits: 20
- stale-branch-days: 2
