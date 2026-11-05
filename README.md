# OneShotAndy · KI Challenge 2026

Beitrag von Team OneShotAndy zur **KI Challenge 2026** des Dachverbands der österreichischen
Sozialversicherungsträger und der WK Wien (05. bis 06.11.2026). Bewertet wird **Use Case 3, StatAgent**.

Eine Plattform, drei Räume und ein gemeinsamer Einstieg. Grundsatz überall: **Die KI schreibt Code und Texte,
das Programm rechnet.** Jede Zahl kommt aus der Datenbank und trägt ihren Beleg; jede Änderung an Regeln oder
Code gibt ein Mensch mit Vor- und Nachnamen frei.

## Was gebaut wurde

| Raum | Was er tut | Details |
|---|---|---|
| **UC3 StatAgent** (bewertet) | Agentengestützter Statistikprozess für die synthetische Beschäftigtenstatistik: Lieferung einlesen, prüfen, zählen, Qualitätsbericht; Änderungsaufträge setzen eigene Agenten um, ein Mensch gibt frei | in Arbeit, `uc3/README.md` folgt |
| UC1 SV KI-Lotse | Chatbot zu Gesundheit und Sozialversicherung, jede Antwort mit Quelle | in Arbeit, `uc1/README.md` folgt |
| UC2 HealthPolicy Simulator | Mehrere Agenten sollen politische, organisatorische und finanzielle Entscheidungen verhandeln; Akteure und Konfiguration stehen, die Verhandlung ist in Arbeit | `uc2/README.md` |
| UC4 Gemeinsamer Einstieg | Eine Frage läuft durch UC3 (geprüfte Zahlen), UC2 (Position) und UC1 (einfache Sprache) | in Arbeit, `/uc4` in der App |

Gemeinsamer Kern in `shared/`:

- **Modell-Schalter** `plattform.llm`: ein Aufruf für alle Modelle, umschaltbar per `LLM_PROVIDER`
  (`azure`, `mistral`, `ollama`, `claude`, `mock`), mit Fallback-Kette und einer Protokollzeile je Aufruf
  ohne Inhalt. Ein Wechsel des Modells ändert keine Zahl.
- **Protokoll und Freigabe** `plattform.protokoll`, `plattform.freigabe` (siehe unten).
- **Oberfläche** `@kic/ui`: Design-Tokens, ruhige Bausteine, Herkunft-Chip an jeder Zahl („SQL ansehen“),
  Freigabe-Karte, Protokoll-Schublade, Header mit Modell-Anzeige.
- **Lokale Embeddings** `plattform.embeddings` für die Suche in UC1 und UC2, ohne Cloud (in Arbeit).

## Start in drei Befehlen

Voraussetzungen: Node 24 mit pnpm 10, uv 0.12, für die Daten von UC3 PostgreSQL 16 auf Port 5433.

```bash
cp .env.example .env.local && sed -i.bak 's/^LLM_PROVIDER=.*/LLM_PROVIDER=mock/' .env.local  # ohne Schlüssel
uv sync --all-packages && pnpm install  # Python- und TypeScript-Workspace
pnpm dev                                # App auf http://localhost:3000
```

Tests: `uv run pytest -q` (gemeinsamer Kern; je Use Case `cd ucN && uv run pytest -q`) und
`pnpm typecheck && pnpm test`. Das Einspielen der Daten für UC3 beschreibt `uc3/README.md` (folgt mit dem UC3-Kern).

## Daten und Modelle

- **Daten:** ausschließlich die synthetischen Daten des Veranstalters und öffentliche Quellen. Sie liegen nicht
  im Repo. Personenbezogene Daten gibt es keine.
- **An ein Modell gehen nie Einzeldaten,** nur Schema, Aggregate und Prüfergebnisse. Gerechnet wird in SQL.
- **Modelle:** Standard ist das Modell des Veranstalters (Azure OpenAI `gpt-5.4-mini`, EU). Mistral (EU) ist der Zweitanbieter für
  den Live-Wechsel, Ollama läuft lokal ohne Netz. Claude nutzen nur UC1 und UC2 im Qualitätsmodus, nie die
  Zählung von UC3. Embeddings rechnet ein lokales Modell (`google/embeddinggemma-2`). Stand und Messungen:
  `docs/models.md`.
- **Voice** ist geplant über Vapi, einen US-Dienst: Er erhielte Audio und Transkript, nie Einzeldaten, nur
  Aggregate mit Beleg. Ohne Voice gibt es immer denselben Weg als Text.

## Freigabe durch einen Menschen

1. Ein Agent schlägt eine Änderung vor (Regel, Code-Datei, Lieferung). Der Vorschlag steht im Protokoll
   `meta.protokoll`, mit Modell und Anweisung.
2. Ein Mensch gibt in der Freigabe-Karte frei. Verlangt sind Vor- und Nachname; Rollen wie „Team“ oder
   „Admin“ und Platzhalter werden abgelehnt.
3. `plattform.freigabe` schreibt die Entscheidung nach `meta.freigabe` und legt in derselben Transaktion einen
   Git-Commit an: Betreff ist die Anweisung, Trailer `Freigegeben-von`, `Vorschlag` und `Modell`.
4. Ein Agenten-Skript startet nur, wenn genau dieser Dateistand freigegeben ist. Eine danach geänderte Datei
   gilt als nicht freigegeben.

`uv run python -m plattform.protokoll export --md --db <URL der UC-Datenbank>` erzeugt daraus das Protokoll
aus Git-Verlauf und Datenbank (Datei `protokoll.md`, je Use Case mit `--uc ucN`).

## Qualität

Jeder Merge Request durchläuft die CI: Secret-Scan, ruff, mypy, pytest, TypeScript-Prüfung, Vitest, ein
Produktions-Build der App und ein **Anti-Schablonen-Gate**. Das Gate misst jede Seite auf Desktop und Mobil
gegen zwölf Muster generischer, maschinell zusammengesetzter Oberflächen und verlangt 0 Treffer
(`docs/design.md`).

## Stand und Grenzen

Stand: 05.11.2026, Nachmittag. Der Endabgleich mit dem gemergten Stand folgt vor der Abgabe.

- Gebaut und in `main`: Monorepo, CI, Modell-Schalter, Protokoll und Freigabe, Design-Tokens, Bausteine, Shell
  mit UC-Wechsel, Landingpage, UC1-Gerüst, Konfiguration und Akteure von UC2.
- In Arbeit: UC3-Kern und Qualitätsbericht, lokale Embeddings, UC4-Einstieg `/uc4`, UC1-Lotse, UC2-Verhandlung.
- Nicht gebaut: Voice.
- Ohne Modellschlüssel läuft alles mit `LLM_PROVIDER=mock`; Antworten sind dann Platzhalter, Zahlen aus der
  Datenbank bleiben gleich.

## Herkunft

Das Voice-Konzept (Vapi Custom LLM, Webhook, Text-Fallback) folgt einem vorab entstandenen Projekt des Teams;
übernommen sind nur Konzept und Schnittstellen, der Code ist hier neu entstanden.

## Für Entwickler

Aufbau, Arbeitsteilung und Regeln für Änderungen: `docs/entwicklung.md`. Schnittstellen der Plattform:
`docs/prd/2026-11-05-e0-plattform-e1-uc3.md`.
