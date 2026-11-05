# StatAgent, KI Challenge 2026 (Use Case 3)

Agentengestützter Statistikprozess für eine synthetische Beschäftigtenstatistik des Dachverbands der
österreichischen Sozialversicherungsträger. Team OneShotAndy. Abgabe Fr 06.11.2026 09:00 (SV-Box-Teamordner)
und im öffentlichen GitHub-Repo `KIChallenge/OneShotAndy`. Dieses Repo ist öffentlich: keine Secrets, keine
personenbezogenen Daten, kein Code aus anderen Produkten.

## Leitlinien

- **Die KI schreibt Code, das Programm rechnet.** Zahlen entstehen nur durch Code, der ohne Sprachmodell
  läuft; zwei Läufe mit denselben Daten und Regeln liefern dieselben Zahlen.
- **Lokal und offline:** PostgreSQL 16 (nativ Port 5433 oder `docker compose` mit `DB_PORT=5433`), DB/User/PW
  `statistik`. Rohdaten in `roh.lieferung`, Klassifikationen in `klassifikation.*`.
- **Regeln als Daten:** Einlese-, Prüf- und Zählregeln liegen in `meta.regel`, versioniert mit Gültigkeit,
  Begründung und Freigabe. Keine Zuordnung als Konstante im Code.
- **Mensch gibt frei:** Jede Regel- oder Codeänderung und jede Lieferung wird mit Vor- und Nachnamen und
  Zeitpunkt freigegeben (`freigabe --name`), Commit-Trailer `Freigegeben-von: Name`. „Team“ wird abgelehnt.
- **Eigene Agenten setzen Änderungsaufträge um,** nicht das Entwicklungswerkzeug. Modell über
  `LLM_PROVIDER=azure|mistral|ollama|mock`, austauschbar. Keine Einzeldaten an das Modell.
- Ein Lauf = eine Lieferung (`lauf --lieferung JJJJ-MM`), nur eigene und frühere Lieferungen; veröffentlichte
  Monate bleiben unverändert, Abweichungen stehen als Revisionsbedarf im Qualitätsbericht.

## Struktur

| Pfad | Inhalt |
|---|---|
| `pipeline/` | Python-Paket `statagent`: lauf, regeln, pruefungen, reporting, agenten, CLI |
| `db/` | SQL-Migrationen (stat_, variable, klass_, uebergang, quellzuordnung, meta.*) |
| `web/` | Next.js-Bedienoberfläche (lesend; startet die CLI) |
| `abgabe/` | erzeugte Ergebnisse: Aggregations-Sheet, Qualitätsberichte, Ministeriums-Lieferung, Protokoll |
| `docs/` | Plan, Annahmen, Modellangabe |
| `tests/` | Golden Set 08/2024 (2.880 Zellen), Fixture-Lieferung, Determinismus |

Plan und Herleitung: Vault `05-business/career/hackathons-2026-27/ki-challenge/uc3-bauplan.md`. Daten:
`../svbox/uc3/` (nicht im Repo). Zugänge nur in `.env.local` (nie lesen oder ausgeben, SEC-008).

## Session Config

- test-command: uv run pytest -q
- typecheck-command: timeout -k 5 300 uv run mypy pipeline
- lint-command: uv run ruff check .
- agents-per-wave: 6
- waves: 4
- persistence: true
- enforcement: warn
- vcs: gitlab
- mirror: none
- recent-commits: 20
- stale-branch-days: 2
