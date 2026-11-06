# Schnellstart: in 30 Minuten arbeitsfähig

Diese Seite ist für Entwicklerinnen, Entwickler und Coding-Agenten, die das Repo zum ersten Mal öffnen. Danach läuft
die App bei dir, du hast einen Lauf von UC3 (StatAgent, der bewertete Use Case) gesehen und weißt, wo du für eine
erste Änderung anfängst. Die 30 Minuten im Titel sind ein Ziel, keine Messung; gemessene Zeiten stehen bei den
Schritten mit ihrer Quelle.

## Was du brauchst

| Werkzeug | Version | Woher die Angabe kommt |
|---|---|---|
| Python | 3.12 oder neuer | `.python-version` (3.12), `requires-python = ">=3.12"` in `pyproject.toml` und `uc3/pyproject.toml` |
| uv (Python-Werkzeug für Pakete und Umgebungen) | 0.12 oder neuer; die CI installiert 0.12.12 | [`uc3/README.md`](../../uc3/README.md), Job `playwright` in [`.gitlab-ci.yml`](../../.gitlab-ci.yml). Die `pyproject.toml` legt keine Mindestversion fest. |
| Node | 24 oder neuer | `engines` in `package.json`; die CI nutzt das Image `node:24-bookworm-slim` |
| pnpm | 10.34.5 | `packageManager` in `package.json` |
| PostgreSQL | 16, auf Port **5433** | [`CLAUDE.md`](../../CLAUDE.md), [`uc3/README.md`](../../uc3/README.md); die CI nutzt den Dienst `postgres:16` |
| Docker mit `docker compose` | keine Version im Repo festgelegt | nur für die Datenbank aus dem Startpaket des Veranstalters ([`uc3/README.md`](../../uc3/README.md)) |
| Startpaket des Veranstalters | synthetische Daten, nicht im Repo | Ordner `../svbox/uc3` neben dem Repo oder Pfad in `STATAGENT_STARTPAKET` |
| gitleaks (Suche nach Schlüsseln im Code) | nur für den lokalen pre-commit-Hook; die CI nutzt v8.28.0 | `scripts/install-hooks.sh`, Job `gitleaks` in `.gitlab-ci.yml` |

Die beiden Compose-Dateien im Repo (`deploy/docker-compose.prod.yml`, `deploy/docker-compose.vorfuehrung.yml`) sind
für die Online-Demo und die Vorführung. Für den lokalen Start brauchst du sie nicht; die Compose-Datei für die
Datenbank liegt im Startpaket.

## In fünf Schritten zum laufenden System

### 1. Klonen

```bash
git clone https://github.com/KIChallenge/OneShotAndy.git
```

Die Adresse steht in `scripts/abgabe/github_push.py`. Lege den Klon so ab, dass das Startpaket als `../svbox/uc3`
daneben liegt, oder setze später `STATAGENT_STARTPAKET`.

### 2. Abhängigkeiten

```bash
cp .env.example .env.local && sed -i.bak 's/^LLM_PROVIDER=.*/LLM_PROVIDER=mock/' .env.local  # ohne Schlüssel
uv sync --all-packages && pnpm install  # Python- und TypeScript-Workspace
bash scripts/install-hooks.sh           # optional: gitleaks als pre-commit-Hook
```

Die ersten beiden Zeilen stehen so im [`README.md`](../../README.md) (Abschnitt „Start“), die dritte in
[`docs/entwicklung.md`](../entwicklung.md). `uv sync --all-packages` installiert den gemeinsamen Kern
(`shared/py`) und die drei Use-Case-Pakete. Laut [Abnahme 66](../abnahme/66.md) kommt dabei kein `torch` mit; die
Pakete für lokale Embeddings stehen nur im Extra `plattform[embeddings]`.

### 3. Datenbank

Im Ordner des Startpakets, nicht im Repo:

```bash
DB_PORT=5433 docker compose up -d
docker logs statagent-db   # warten, bis „fertig“ erscheint
```

In der Abnahme war die Datenbank in 16 bis 18 Sekunden geladen, mit 10.152.292 Zeilen in 24 Lieferungen
([`docs/abnahme/66.md`](../abnahme/66.md), Schritt „frisch“). Den Standard-Zugang
`postgresql://statistik:statistik@localhost:5433/statistik` nimmt UC3 von selbst; eine andere Adresse setzt du in
`UC3_DATABASE_URL` ([`uc3/README.md`](../../uc3/README.md)).

### 4. Beispiellauf UC3

```bash
uv run uc3 db init                          # Schemas, Klassifikationen, Regelsätze (wiederholbar, löscht nichts)
uv run uc3 lauf --alle                      # 24 Einzelläufe 2024-08 bis 2026-07, in zeitlicher Reihenfolge
uv run uc3 eichen --lieferung 2024-08       # Vergleich mit dem Beispielbericht, Tab1 bis Tab13
uv run uc3 berichte --alle && uv run uc3 sheet   # 24 Qualitätsberichte und Aggregations-Sheet nach abgabe/
```

Die Befehle stehen so im [`README.md`](../../README.md) (Abschnitt „Beispiellauf UC3 (Jury-Weg)“) und in
[`uc3/README.md`](../../uc3/README.md). Alle vier Befehle und der Schalter `--alle` sind in
`uc3/statagent/cli.py` vorhanden; `uv run statagent …` ist gleichwertig.

- **Dauer:** `lauf --alle` brauchte in der Nachmessung 419 Sekunden für alle 24 Monate, rund 7 Minuten
  ([`docs/abnahme/66.md`](../abnahme/66.md), „Nachmessung mit dem Fix aus !58“). In der Messung davor, mit `ANALYZE` von Hand,
  dauerte ein einzelner Monat 18 bis 22 Sekunden.
- **Erwartetes Ergebnis von `eichen`:** die Zeile `Zellen 2880, abweichend 0`. Das heißt: Alle 2.880 Zahlen des
  Beispielberichts (der Monatsbericht August 2024 aus der Aufgabe) rechnet UC3 aus den Rohdaten gleich nach.
- **Ohne Netz und ohne Sprachmodell:** `uc3 lauf` und `uc3 eichen` laden kein Modell-Modul. Die Abnahme hat das im
  Prozess gemessen: `netzversuche: []` ([`docs/abnahme/66.md`](../abnahme/66.md), Abschnitt „Ohne Netz“).
- **Zweiter Regelstand:** Die Regeln heißen in der Oberfläche „Alte Regeln“ (Kennung `v1`) und „Nach den
  Änderungsaufträgen“ (Kennung `v2`). Wie du die Regeln nach den Änderungsaufträgen und die Ministeriums-Lieferung
  nachrechnest, steht in [`abgabe/README.md`](../../abgabe/README.md), Abschnitt „Auf einer frischen Datenbank
  nachrechnen“.

Achtung: `berichte` und `sheet` schreiben in den Ordner `abgabe/`, also in die abgegebenen Dateien. Wer das nicht
will, setzt vorher `STATAGENT_ABGABE` auf einen anderen Ordner (`uc3/statagent/konfig.py`, Funktion `abgabe`).

### 5. Weboberfläche

```bash
pnpm dev   # App auf http://localhost:3000
```

`pnpm dev` startet `next dev` im Paket `web` und lädt dabei `../.env.local` (`web/package.json`, Skript `dev`). Der
Server hört nur auf `127.0.0.1`. Mit gerechneten Läufen zeigen die Seiten unter `/uc3` Läufe, Berichte,
Klassifikationen, Freigaben und Datenanfragen, jede Zahl mit Beleg ([`README.md`](../../README.md)).

## Ohne Schlüssel starten

Mit `LLM_PROVIDER=mock` (Schritt 2) braucht nichts einen Modellschlüssel. Was dann geht und was nicht:

| Teil | Mit `mock` | Quelle |
|---|---|---|
| UC3-Lauf, Eichen, Berichte, Sheet | geht ganz; der Lauf ruft ohnehin kein Modell | [`README.md`](../../README.md), [`docs/abnahme/66.md`](../abnahme/66.md) |
| Fragen an die Daten (`uv run uc3 frage "…"`, Seite `/uc3/fragen`) | geht; die Frage wird ohne Sprachmodell gelesen | `uc3/statagent/frage.py`, [`README.md`](../../README.md) |
| Seiten `/`, `/uc1`, `/uc2`, `/uc4`, `/praesentation` | laufen lokal; Modelle antworten mit festen Platzhaltern, Zahlen aus der Datenbank bleiben gleich | [`README.md`](../../README.md), Abschnitt „Start“ |
| Tests und CI | laufen mit `mock`; die CI hat keinen Modellschlüssel | [`.gitlab-ci.yml`](../../.gitlab-ci.yml) |
| Andere Modellaufrufe über `plattform.llm` | geht teilweise: `mock` antwortet aus Dateien `shared/py/plattform/fixtures/<zweck>.json`. Dort liegt im Repo nur `smoke.json`. Für einen Zweck ohne Datei bricht der Aufruf mit `FixtureFehlt` ab, statt zu raten. Tests bringen ihre eigenen Dateien über `PLATTFORM_FIXTURES` mit. | `shared/py/plattform/llm/mock.py`, [`docs/models.md`](../models.md) |
| Änderungsaufträge an die UC3-Agenten (`uv run uc3 agent "…"`) | für echte Vorschläge ein Modell nötig; Pflicht für die UC3-Agenten ist Azure | [`docs/models.md`](../models.md) |
| Voice | geht nicht ohne eingerichtetes Vapi-Konto und öffentliche Adresse | [`README.md`](../../README.md), Abschnitt „Grenzen“ |
| Lokale Embeddings | brauchen einmal `uv run python -m plattform.embeddings laden`; ohne diesen Schritt bricht `einbetten` mit `ModellFehlt` ab | [`docs/models.md`](../models.md) |

Für echte Modelle trägst du in `.env.local` die Schlüssel ein. Die Namen stehen mit Erklärung in
[`.env.example`](../../.env.example), zum Beispiel `LLM_PROVIDER`, `AZURE_OPENAI_BASE_URL`, `AZURE_OPENAI_MODEL`,
`AZURE_API_KEY`, `MISTRAL_API_KEY`, `MISTRAL_BASE_URL`, `OLLAMA_BASE_URL` und `CLAUDE_MODEL`. Werte stehen nie im
Repo. Welches Modell wofür gedacht ist, steht in [`docs/models.md`](../models.md).

## Landkarte des Repos

| Ordner | Was drin ist | Wann du ihn anfasst |
|---|---|---|
| `uc3/` | Python-Paket `statagent` (CLI `uv run uc3`), SQL-Dateien für Schema und Regeln in `uc3/db/`, Tests in `uc3/tests/` | bei allem, was die Beschäftigtenstatistik rechnet, prüft oder berichtet |
| `uc1/` | Python-Paket für den SV KI-Lotsen (UC1) | bei Antworten des Lotsen; Plan in `docs/plan/uc1/` |
| `uc2/` | Python-Paket für den HealthPolicy Simulator (UC2): Akteure, Fälle, Verhandlung | bei der Verhandlungs-Simulation; Einstieg [`uc2/README.md`](../../uc2/README.md) |
| `shared/` | gemeinsamer Kern: Python-Paket `plattform` in `shared/py/` (Modell-Schalter, Protokoll, Freigabe, Voice, Embeddings), Oberflächen-Paket `@kic/ui` in `shared/ui/`, JSON-Schemas in `shared/schema/` | wenn eine Änderung alle Use Cases betrifft |
| `web/` | die eine Next.js-App mit allen Seiten und Route-Handlern, Browser-Tests in `web/tests/` | bei allem, was man im Browser sieht |
| `abgabe/` | vom Programm erzeugte UC3-Ergebnisse: Aggregations-Sheets, Qualitätsberichte, Rückfragen, Protokoll | nicht von Hand; siehe „Für Coding-Agenten“ |
| `docs/` | Pläne, Annahmen, Abnahmen, Präsentation, Modelle, Sprach- und Designregeln | vor einer Änderung zum Nachlesen, danach zum Nachtragen |
| `tests/` | Prüfungen über das ganze Repo: `tests/abnahme/` (Abnahme-Skripte) und `tests/abgabe/` (Abgabe-Skripte) | wenn du eine Abnahme nachvollziehen willst |
| `scripts/` | Hilfsskripte: Hook-Installation, Deploy, Vorführung, Füllen der CI-Datenbank, Abgabe-Upload | selten; nur mit Blick in das jeweilige Skript |
| `deploy/` | Dockerfiles, Compose-Dateien und Caddy-Konfiguration der Online-Demo | nur für die Online-Demo; Einstieg `deploy/README.md` |

## Wo ändere ich was?

| Aufgabe | Hier fängst du an |
|---|---|
| Neue Prüfregel oder andere Schwelle | `uc3/db/120_pruefregeln_v1.sql`: Prüfregeln sind Zeilen in `meta.regel`, Schwellen stehen im Feld `parameter`. Eine neue Art von Prüfung braucht Code in `uc3/statagent/pruefungen.py`, denn der Code kennt nur die Arten. Eine bestehende Regel wird nie überschrieben, nur durch eine neue Regelzeile ersetzt (Kopf der SQL-Datei). |
| Änderung an einer Regel über die eigenen Agenten | `uv run uc3 agent "<Änderungsauftrag>"` erzeugt einen Vorschlag und ändert nichts; `uv run uc3 freigabe <ID> --name "Vor- und Nachname"` gibt ihn frei (`uc3/statagent/cli.py`, Code in `uc3/statagent/agenten/`) |
| Einlese-, Zuordnungs- oder Zählregel | `uc3/db/110_regelsatz_v1.sql` (Regeln der Typen `einlese`, `zuordnung`, `zaehl`), Code in `uc3/statagent/bereinigung.py` und `uc3/statagent/zaehlung.py` |
| Neue Frage an die Daten | `uc3/statagent/frage.py`; Soll-Antworten im Katalog `uc3/tests/fragen_katalog.md`, gerechnet von `uc3/tests/fragen_orakel.py` |
| Qualitätsbericht oder Aggregations-Sheet | `uc3/statagent/berichte/qualitaetsbericht.py` und `uc3/statagent/berichte/sheet.py` |
| Neuer Befehl in der UC3-CLI | `uc3/statagent/cli.py` (Typer-Befehle) |
| Text in der Oberfläche | Seiten je Use Case in `web/app/<uc>/` und `web/components/<uc>/`; Startseite in `web/landing/texte/inhalt.ts`, ihre Zahlen in `web/landing/daten/fakten.ts`; Fachwörter zuerst in [`docs/sprache.md`](../sprache.md), dann im Glossar `shared/ui/src/bausteine/glossar.ts` |
| Gemeinsame Bausteine und Farben | `shared/ui/src/bausteine/` (etwa Herkunft-Chip und Freigabe-Karte), Farben und Schriften in `shared/ui/src/tokens.css` |
| Neues Modell oder neuer Anbieter | `shared/py/plattform/llm/`: je Anbieter eine Datei, eingetragen in `FABRIKEN` in `kern.py`; welcher Zweck welches Modell nimmt, steht in `shared/py/plattform/zwecke.toml`; Schlüsselnamen in `.env.example`, Beschreibung in [`docs/models.md`](../models.md) |
| Neuer Bereich in der App | `web/app/<uc>/layout.tsx` mit `<UcBereich>`, dazu `page.tsx` und `web/app/api/<uc>/protokoll/route.ts`; die Liste der Bereiche `shared/ui/src/ucs.ts` gehört der Plattform ([`docs/entwicklung.md`](../entwicklung.md)) |
| Neues Python-Paket | nur in die `pyproject.toml` des eigenen Use Case, danach `uv lock` an der Wurzel; `web/package.json` und `pnpm-lock.yaml` ändert nur die Plattform ([`docs/entwicklung.md`](../entwicklung.md)) |

## Prüfen, bevor du etwas abgibst

Die CI läuft nur für Merge Requests und für von Hand gestartete Pipelines ([`.gitlab-ci.yml`](../../.gitlab-ci.yml),
Block `workflow`). Diese Befehle fährt sie, du kannst sie lokal genauso ausführen.

Python (Job `python`):

```bash
uv sync --frozen --all-packages
uv run ruff check .
uv run ruff format --check .
uv run mypy shared/py/plattform
(cd uc1 && uv run mypy uc1) && (cd uc2 && uv run mypy src) && (cd uc3 && uv run mypy statagent)
uv run pytest -q -m "not daten" shared/py/tests
for d in uc1 uc2 uc3; do (cd "$d" && uv run pytest -q -m "not daten") || exit 1; done
uv run pytest -q -p no:cacheprovider tests/abnahme/test_abnahme.py
uv run pytest -q -p no:cacheprovider tests/abgabe
```

Die mypy-Zeile für die Use Cases ist in der CI eine Schleife, die nur Pakete mit eigenem Abschnitt `[tool.mypy]`
prüft; alle drei haben ihn. Die UC3-Tests legen sich eine Wegwerf-Datenbank `statagent_test_<…>` auf dem
PostgreSQL an Port 5433 an und schreiben nie in eine bestehende (`uc3/tests/conftest.py`).

TypeScript (Jobs `web` und `web-build`):

```bash
pnpm install --frozen-lockfile
pnpm -r exec tsgo --noEmit          # Typprüfung
pnpm -r --if-present run lint       # ESLint, Regeln in web/eslint.config.mjs
pnpm -r --if-present run test       # Vitest
pnpm --filter web run build         # Produktions-Build
```

Was die CI zusätzlich macht:

| Job | Was er prüft |
|---|---|
| `gitleaks` | sucht in der ganzen Git-Geschichte nach Schlüsseln, weil das Repo öffentlich ist |
| `playwright` | füllt eine leere Datenbank mit erfundenen Mini-Lieferungen (`scripts/ci/uc3_seed.py`) und fährt `pnpm --filter web run test:slop`: Browser-Tests auf Desktop und Mobil, das Anti-Schablonen-Gate ([`docs/design.md`](../design.md)) und die Prüfung der Barrierefreiheit mit axe |
| `deploy-check` | nur bei Änderungen an `deploy/` und den Deploy-Skripten: shellcheck, Caddy-Konfiguration, Compose-Dateien und ihre Regeln |
| `deploy` | nur manuell auf `main`; bringt die Online-Demo auf den Server |

Die Tests mit dem Marker `daten` laufen nicht in der CI, weil sie die echten Lieferungen brauchen. Lokal mit
gerechneten Läufen: `UC3_DATEN_URL=postgresql://statistik:statistik@localhost:5433/statistik uv run pytest -q -m daten uc3/tests`
([`README.md`](../../README.md), Abschnitt „Tests“).

## Für Coding-Agenten

Lies zuerst diese Dateien, in dieser Reihenfolge:

| Datei | Warum |
|---|---|
| [`CLAUDE.md`](../../CLAUDE.md) | Leitlinien, Aufbau des Repos, welcher Bereich welche Dateien besitzt |
| [`docs/sprache.md`](../sprache.md) | ein Wort für eine Sache; gilt für jeden Text, den Jury oder Publikum sehen |
| [`docs/design.md`](../design.md) | das Anti-Schablonen-Gate: zwölf Muster, die auf jeder Seite 0 sein müssen |
| [`docs/entwicklung.md`](../entwicklung.md) | Einrichten, Arbeitsteilung, Regeln für Abhängigkeiten |
| [`web/AGENTS.md`](../../web/AGENTS.md) | die Next.js-Version hier weicht vom Trainingswissen ab; vor Code in `web/` die Doku in `node_modules/next/dist/docs/` lesen |

Nicht verhandelbar (sinngemäß nach [`CLAUDE.md`](../../CLAUDE.md), Abschnitt „Leitlinien“, ergänzt um das, was der Code
erzwingt, etwa die Namensprüfung in [`freigabe.py`](../../shared/py/plattform/freigabe.py)):

- **Die KI schreibt Code, das Programm rechnet.** Zahlen entstehen nur durch Code, der ohne
  Sprachmodell läuft. `uc3 lauf` importiert `plattform.llm` nicht. Zwei Läufe mit denselben Daten und Regeln liefern
  dieselben Zahlen.
- **Zahlen nie vom Modell.** Ein Modell schlägt nur Änderungen vor. An ein Modell gehen keine Einzeldaten, nur
  Schema, Summen und Prüfergebnisse. `web/` ruft nie direkt ein Modell, alles läuft über `plattform.llm`.
- **Freigabe durch einen Menschen mit Namen.** Jede Regel- oder Codeänderung und jede Lieferung gibt eine Person mit
  Vor- und Nachnamen frei. Rollen wie „Team“ oder „Admin“ werden abgelehnt.
- **Regeln als Daten.** Regeln stehen in `meta.regel`, mit Gültigkeit, Begründung und Freigabe, nie als Konstante
  im Code.
- **Öffentliches Repo.** Keine Schlüssel, keine personenbezogenen Daten. Werte aus `.env.local` gehören nie in
  Ausgaben, Commits oder Issues.

Gesperrt:

- **`abgabe/`** ist die eingereichte Abgabe (Abgabe 06.11.2026 09:00, [`CLAUDE.md`](../../CLAUDE.md)). Alle Dateien
  dort erzeugt das Programm; nie von Hand ändern ([`abgabe/README.md`](../../abgabe/README.md)).
- **Lockfiles:** Konflikte in `uv.lock` nie von Hand lösen, sondern `uv lock` neu laufen lassen
  ([`docs/entwicklung.md`](../entwicklung.md)).
- **Veröffentlichte Monate:** Ein Trigger in der Datenbank schützt veröffentlichte Zeilen gegen jede Änderung
  ([`uc3/README.md`](../../uc3/README.md)).

## Häufige Stolpersteine

| Stolperstein | Was hilft | Quelle |
|---|---|---|
| Auf Port 5432 lauscht oft ein anderes PostgreSQL | immer Port 5433 nutzen, oder die Adresse in `UC3_DATABASE_URL` setzen | [`README.md`](../../README.md), [`CLAUDE.md`](../../CLAUDE.md) |
| `uv run statagent regeln laden` bricht ab: den Befehl gibt es nicht | `db init` spielt die Regeln schon ein | [`docs/abnahme/66.md`](../abnahme/66.md), Punkt 66-1 |
| `uv run uc3 laeufe` zeigt den Ergebnis-Hash nur mit 12 Zeichen | für einen Vergleich `uv run uc3 laeufe --json` | [`uc3/README.md`](../../uc3/README.md), Punkt 66-3 |
| Der Ergebnis-Hash passt nicht zu einem selbst gebauten CSV-Hash | der Hash hat eine eigene Formel über die Zahlen des Monats; sie steht in [`uc3/README.md`](../../uc3/README.md) | [`docs/abnahme/66.md`](../abnahme/66.md), Punkt 66-4 |
| `lauf --alle` hing auf einer frisch geladenen Datenbank im dritten Monat | behoben: der Lauf führt jetzt selbst `ANALYZE bereinigt.abschnitt` aus (`uc3/statagent/bereinigung.py`, Zeile 406) | [`docs/abnahme/66.md`](../abnahme/66.md), Punkt 66-6 |
| Auf einer frischen Datenbank bleiben alle Monate „vorläufig“, die Ministeriums-Lieferung startet nicht | die alten Regeln (`v1`) zuerst mit eigenem Namen freigeben: `uv run uc3 regeln freigeben --regelsatz v1 --name "Vor- und Nachname"` | [`abgabe/README.md`](../../abgabe/README.md) |
| `uc3 sheet` oder `uc3 berichte` enden mit Exit 1 | für diesen Regelstand gibt es noch keinen fertigen Lauf; erst `uc3 lauf` | [`abgabe/README.md`](../../abgabe/README.md) |
| Nach dem Neuerzeugen meldet `uc3 pruefe-abgabe` Abweichungen vom Manifest | erwartet; `git checkout abgabe/` holt den Abgabestand zurück | [`abgabe/README.md`](../../abgabe/README.md) |
| `pytest -m daten` scheitert sofort | diese Tests brauchen die Datenbank mit allen 24 Lieferungen; ohne sie `-m "not daten"` wie die CI | `uc3/tests/test_goldenset.py`, `pyproject.toml` |
| In einem zusätzlichen Git-Worktree findet `pnpm dev` keine Schlüssel | `.env.local` in den Worktree verlinken; die Python-Seite findet die Datei des Haupt-Checkouts selbst | [`docs/entwicklung.md`](../entwicklung.md) |
| Die Online-Demo lehnt Freigaben und Läufe ab (403) | so gewollt: online sind nur Fragen erlaubt | [`README.md`](../../README.md), Abschnitt „Online-Demo“ |

## Weiter lesen

- [`README.md`](../../README.md): Übersicht über das ganze Repo mit Lösung, Ausführung, Grenzen und Lizenzen
- [`uc3/README.md`](../../uc3/README.md): alle Befehle von StatAgent und wie ein Lauf rechnet
- [`abgabe/README.md`](../../abgabe/README.md): was in der Abgabe liegt und wie man sie nachrechnet
- [`docs/abnahme/66.md`](../abnahme/66.md): der Jury-Weg in einer frischen Umgebung, mit Messungen
- [`docs/models.md`](../models.md): Modelle, Ausweichkette, Tagesbudget
- [`docs/prd/2026-11-05-e0-plattform-e1-uc3.md`](../prd/2026-11-05-e0-plattform-e1-uc3.md): Schnittstellen der Plattform
- In diesem Ordner: [Übersicht](README.md), [Architektur](architektur.md), [Zahlen](zahlen.md),
  [Agentische Arbeitsweise](arbeitsweise-agentisch.md), [Stand der Use Cases](use-cases-stand.md)
