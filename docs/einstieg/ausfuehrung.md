# Ausführung, Langfassung

Diese Seite ist die Langfassung der Abschnitte „Ausführung“ und „Abhängigkeiten und Voraussetzungen“ aus dem README.
Die Testbefehle stehen im README unter „Ausführung“, dort auch der Hinweis, dass der Beispiellauf in den Ordner `abgabe/` schreibt.

Zurück zum [README](../../README.md#ausführung).

## Start

```bash
cp .env.example .env.local && sed -i.bak 's/^LLM_PROVIDER=.*/LLM_PROVIDER=mock/' .env.local  # ohne Schlüssel
uv sync --all-packages && pnpm install  # Python- und TypeScript-Workspace
pnpm dev                                # App auf http://localhost:3000
```

Die Seiten `/`, `/uc1`, `/uc2`, `/uc4` und `/praesentation` laufen damit lokal. Mit `LLM_PROVIDER=mock` antworten Modelle
mit festen Platzhaltern. Zahlen aus der Datenbank bleiben gleich. Die Seiten unter `/uc3` und die Zahl auf `/uc4`
brauchen die UC3-Datenbank mit gerechneten Läufen (nächster Abschnitt).

## Beispiellauf UC3 (Jury-Weg)

Voraussetzung ist die Datenbank des Veranstalters auf Port 5433. Im Ordner des Startpakets:
`DB_PORT=5433 docker compose up -d`, dann warten, bis `docker logs statagent-db` „fertig“ meldet. Danach im Repo:

```bash
uv run uc3 db init                          # Schemas, Klassifikationen, Regelsätze (wiederholbar, löscht nichts)
uv run uc3 lauf --alle                      # 24 Einzelläufe 2024-08 bis 2026-07, in zeitlicher Reihenfolge
uv run uc3 eichen --lieferung 2024-08       # Vergleich mit dem Beispielbericht, Tab1 bis Tab13
uv run uc3 berichte --alle && uv run uc3 sheet   # 24 Qualitätsberichte und Aggregations-Sheet nach abgabe/
```

Das Ergebnis des Eichens ist die Zeile „Zellen 2880, abweichend 0“ (`uc3/README.md`). Alle Befehle und die Regeln
dazu stehen in `uc3/README.md`. Der Lauf braucht kein Netz und kein Sprachmodell. Die Änderungsaufträge (Regelsatz v2)
und die Ministeriums-Lieferung auf einer frischen Datenbank nachrechnen: `abgabe/README.md`, Abschnitt „Auf einer frischen
Datenbank nachrechnen“.

**Nachweis des Jury-Wegs:** Die Abnahme in einer frischen Umgebung steht in `docs/abnahme/66.md`, mit Befehlen,
Zahlen und Ausgaben. Gemessen wurden alle 24 Läufe nacheinander auf einer frisch geladenen Datenbank: 24 von 24
fertig in rund 7 Minuten, das Ergebnis gleich dem früheren Lauf. Auf einer frischen Datenbank entstehen dieselben
Zahlen und Ergebnis-Hashes wie bei uns; der Status bleibt dort „vorläufig“, weil Freigaben und Veröffentlichung mit
Namen in unserer Team-Datenbank stehen. Den Nachweis dafür enthält `abgabe/protokoll.md`.

## Online-Demo

Eine öffentliche Demo läuft unter https://ki-challenge.gotzendorfer.at (Adresse und Aufbau: `deploy/README.md`).
Man kann dort Fragen stellen: auf `/uc3/fragen` an die Daten (ohne Sprachmodell) und auf `/uc4`, wo UC3, UC2 und UC1
nacheinander antworten, mit dem Modell Azure `gpt-5.4-mini`. Die Zahl kommt immer aus der Datenbank, mit Beleg.
Alles andere ist dort nur zum Ansehen: Freigaben, Läufe und neue Verhandlungen nimmt der Server nicht an (403).
Standardmäßig gehen je Internetanschluss höchstens 10 Fragen in der Minute, und für den ganzen Tag gibt es ein
festes Kontingent an Modellaufrufen.

## Abhängigkeiten und Voraussetzungen

| Was | Version | Beleg |
|---|---|---|
| Python | 3.12 oder neuer | `.python-version`, `requires-python` in `pyproject.toml` |
| uv (Python-Werkzeug) | 0.12, gemessen mit 0.12.12 | PRD `docs/prd/2026-11-05-e0-plattform-e1-uc3.md` Zeile 271; `uv --version` auf dem Entwicklungsrechner. `pyproject.toml` legt keine Mindestversion fest. |
| Node | 24 oder neuer | `engines` in `package.json` |
| pnpm | 10 (festgelegt auf 10.34.5) | `packageManager` in `package.json` |
| PostgreSQL | 16, Port **5433** (auf 5432 lauscht oft ein fremder Postgres) | `CLAUDE.md`, `uc3/README.md` |
| Docker | nur für die Datenbank des Veranstalters (`docker compose`) | `uc3/README.md` |
| Daten | Startpaket des Veranstalters, synthetisch, nicht im Repo; Ordner `../svbox/uc3` oder `STATAGENT_STARTPAKET` | `uc3/README.md` |

Wichtige Bibliotheken: `openai`, `fastapi`, `psycopg`, `pydantic` (Kern, `shared/py/pyproject.toml`), `typer` und
`openpyxl` (UC3, `uc3/pyproject.toml`), Next.js 16, React 19 und `@vapi-ai/web` für den
Sprechknopf (App, `web/package.json`; geladen in `web/lib/plattform/voice-lader.ts`). Die genauen
Versionen stehen in `uv.lock` und `pnpm-lock.yaml`. Für die lokalen Embeddings kommt das Extra
`plattform[embeddings]` (sentence-transformers) dazu. Es ist nicht in der CI.

## Für Entwickler

Aufbau, Arbeitsteilung und Regeln für Änderungen: `docs/entwicklung.md`. Schnittstellen der Plattform:
`docs/prd/2026-11-05-e0-plattform-e1-uc3.md`.
