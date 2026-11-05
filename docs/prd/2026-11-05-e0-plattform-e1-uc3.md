# Feature: E0 Plattform (Monorepo, Shell, Modell-Schalter, Protokoll/Freigabe, Design) und E1 UC3 StatAgent

**Date:** 2026-11-05
**Author:** Bernhard Götzendorfer + Claude (AI-assisted planning, Session app-c3, Lead lead-session-orchestrator-09)
**Status:** Draft
**Appetite:** E0 Kern bis Do 18:00, E0 Rest bis Fr 03:00; E1 nach Wellen #13–#20, Feature-Stopp Fr 05:00
**Parent Project:** agents/ki-challenge-2026 (Repo-Wurzel `app/`), Epics #21 (E0) und #22 (E1)

> Kompakt auf Owner-Wunsch (12:3x „straffe Planung“): Dieses Dokument ist die Schnittstellen-SSOT für E0, auf
> die UC1 (#23), UC2 (#24) und UC3 (#22) bauen. Die Arbeit selbst steht in den Kinder-Issues.
> Entscheidungen hier sind autonom getroffen (Steuerung: autonomous, Lead-Regel 12:4x) und im Epic #21 protokolliert.

## 1. Problem & Motivation

### What
Ein Monorepo, in dem ein Next.js-16-Dashboard (`web/`) über den Header zwischen Übersicht, UC1, UC2, UC3 und
Präsentation wechselt, und ein gemeinsames Fundament (`shared/`) für Modell-Schalter, Protokoll, Freigabe,
Voice und Design-Bausteine liefert, auf dem UC3 StatAgent (bewertet) sowie UC1 und UC2 (Zusatz) laufen.

### Why
Bewertet wird nur UC3 (120 Punkte, Fr 09:00). Drei Planungs-Tabs bauen parallel; ohne festgelegte Ordner,
Verträge und Bausteine entstehen drei Apps statt einer. Der Owner will „alles gesamt passend“, eigenes ruhiges
Design ohne KI-Schablonen, und Technik nur so komplex wie nötig.

### Who
Fachjury (15 Minuten am Platz, Live-Änderung per Sprache), Finaljury (12 Minuten), der Owner als Vorführender,
die Bau-Sessions der vier Tabs als erste Nutzer der Verträge.

### Evidence Baseline

| Claim | Command | Result | Measured |
|-------|---------|--------|----------|
| Repo enthält noch keinen Produktcode | `find . -maxdepth 2 -not -path './.git*'` | nur CLAUDE.md, README, CI-Vorschlag, docs/, .claude/personas | 2026-11-05 12:20 @ 51341c6 |
| Rohdaten liegen in PG 5433 | `psql -p 5433 -U statistik -d statistik -c "select count(*) from roh.lieferung"` | 10.152.292 Zeilen | 2026-11-05 12:30 |
| Golden Set 08/2024 exakt | Lead-Gegenrechnung (ki-challenge-goldenset-2024-08.md § 5) | 2.880/2.880 Zellen, 0 Abweichungen | 2026-11-05 (m5 statagent-db) |
| Azure-Endpunkt we-16 antwortet | Lead-Smoke 12:2x (`/models` und Chat gpt-5-4-mini) | HTTP 200 / 200 | 2026-11-05 12:2x |
| `claude -p --model claude-opus-5-5` liefert Antwort | `echo ok \| timeout 60 claude -p --model claude-opus-5-5 --output-format json 'Antworte nur mit ok'` (Pre-Mortem) | end_turn; API 3,5 s, Wandzeit 15–16 s, ca. 32k Cache-Tokens je Aufruf (lädt globalen Kontext) | 2026-11-05 13:0x |
| `claude -p` kann JSON-Schema-Ausgabe | `claude -p --help \| grep json-schema` | `--json-schema <schema>` vorhanden (2.1.318) | 2026-11-05 12:30 |
| Pen-Datei existiert, Frames nur UC3 | `ls -la design/ki-challenge.pen` | 919 KB, 13 StatAgent-Frames ab x=4800 (Übergabe) | 2026-11-05 10:38 |
| Baseline hat keine Python/uv-Vorlage | Baseline-Agent (templates/, grep pyproject, uv sync) | 0 Treffer; nextjs-saas einziger Next-Archetyp | 2026-11-05 |
| Schlüssel vorhanden (nur Namen) | `sed -n 's/^\([A-Z_]*\)=.*/\1/p' .env.local` | AZURE_API_KEY, VAPI_API_KEY, VAPI_PUBLIC_KEY, MISTRAL_API_KEY gesetzt | 2026-11-05 12:30 |
| `.env.example` zeigt alten Endpunkt | `grep we-01 .env.example` | 1 Treffer (we-01 statt we-16), kein LLM_PROVIDER | 2026-11-05 12:30 |
| Zweiter Postgres auf 5432 | `lsof -iTCP:5432` | postgres PID 1089 lauscht; `.env.example` hat keine DB-URL | 2026-11-05 13:0x |
| CI-Vorschlag passt nicht zum Workspace | `.gitlab-ci.yml:66-70` | `cd web`, Cache-Key `web/pnpm-lock.yaml`, `uv sync` ohne `--all-packages`, CI-Postgres leer | 2026-11-05 13:0x |
| measureSlop-Schlüssel | `grep -n kickers ~/.claude/skills/product-ux-audit/scripts/slop-measure.js` | `kickersMono`, `kickersCaps` (kein `kickers`), `root` Standard `main`, kein Export | 2026-11-05 13:0x |
| `cloudflared` vorhanden | `which cloudflared` | /opt/homebrew/bin/cloudflared | 2026-11-05 13:0x |
| Modell-Konzept Owner | Lead-Nachricht 13:0x („ok passt. so machen wirs“) | azure Pflicht UC3, mistral Zweitanbieter Live-Austausch, ollama Notnagel m5, claude Qualitätsmodus UC1/UC2; Azure-Limit 200.000 Token/s, Mistral-Budget 10 € | 2026-11-05 13:0x |

## 2. Solution & Scope

### Ordner (Vertrag O)

```
app/                         Repo-Wurzel, pnpm-workspace.yaml + pyproject.toml (uv workspace)
├── web/                     Next.js 16.4 App (eine App, ein Build). Lanes:
│   ├── app/layout.tsx, app/page.tsx (Landing), app/praesentation/   → E0
│   ├── app/uc1/**, app/api/uc1/**, components/uc1/**                 → UC1-Session
│   ├── app/uc2/**, app/api/uc2/**, components/uc2/**                 → UC2-Session
│   └── app/uc3/**, app/api/uc3/**, components/uc3/**                 → UC3-Session
├── shared/
│   ├── py/plattform/        Python-Paket `plattform`: llm, protokoll, freigabe, voice, sql/meta.sql   → E0
│   └── ui/                  TS-Paket `@kic/ui`: tokens.css, Shell, Header, ModellBadge, HerkunftChip,
│                            FreigabeKarte, ProtokollSchublade, VoiceKnopf, ucs.ts (Registry)           → E0
├── uc1/  uc2/  uc3/         je ein Python-Paket (uv-Workspace-Member) mit CLI `uv run <uc> --help`,
│                            eigener Datenbank auf PG 5433 (uc3: statistik, uc1: lotse, uc2: frei),
│                            optional FastAPI `<uc>.api:app` (Ports 8101/8102/8103) für Chat/Voice
├── abgabe/                  erzeugte UC3-Ergebnisse (nur UC3)
├── docs/                    PRD, Annahmen, models.md
└── design/ (im Elternordner ki-challenge-2026/, nicht im Repo)   Pen-Datei
```

Datenbank-Adressen je UC in `.env.local`: `UC1_DATABASE_URL`, `UC2_DATABASE_URL`, `UC3_DATABASE_URL`
(alle Port 5433; auf 5432 lauscht ein fremder Postgres). `.env.local` wird von Python per python-dotenv beim
CLI-Start geladen (Suche aufwärts bis zur Repo-Wurzel) und von `web` über `dotenv-cli` (devDependency) aus `../.env.local`;
nur `VAPI_PUBLIC_KEY` wird in `next.config.ts` als `NEXT_PUBLIC_VAPI_PUBLIC_KEY` exponiert.
CI: ein `pnpm-lock.yaml` an der Wurzel (Cache-Key), web-Job an der Wurzel mit `pnpm -r`, python-Job mit
`uv sync --frozen --all-packages`; der Playwright-Job nutzt ein Playwright-Image. Golden-Set- und DB-Tests sind
mit `pytest.mark.daten` markiert und laufen nur lokal (CI-Postgres ist leer); CI prüft die 20-Zeilen-Fixture.
Je Session ein Worktree, nur in der eigenen Lane schreiben. Root-Configs, `shared/**`, `web/app/layout.tsx`,
`web/app/page.tsx`, `web/app/praesentation/**` gehören E0. CLAUDE.md-Strukturtabelle wird darauf angepasst
(`pipeline/` → `uc3/statagent`, `db/` → `uc3/db`, `tests/` → `uc3/tests`).

### Modell-Schalter (Vertrag M, nur Python)

```python
from plattform.llm import complete, aktives_modell
antwort = complete(nachrichten, schema=None, stream=False, provider=None, zweck="qs.einstufung")
# nachrichten: list[{"role": "system"|"user"|"assistant", "content": str}]
# schema: pydantic-Modell oder JSON-Schema-dict → antwort.json validiert; sonst antwort.text
# stream=True → Iterator[str]; provider=None → LLM_PROVIDER aus Umgebung
# Antwort: text, json, provider, modell, dauer_ms, tokens_in, tokens_out
aktives_modell()  # {"provider": "azure", "modell": "gpt-5-4-mini", "quelle": "env"}
```

| LLM_PROVIDER | Umsetzung | Umgebungsvariablen |
|---|---|---|
| `azure` (Standard, Pflicht UC3-Agenten) | openai-SDK Chat Completions, Bearer, `reasoning_effort` nur hier | `AZURE_OPENAI_BASE_URL` (we-16), `AZURE_OPENAI_MODEL`, `AZURE_API_KEY` |
| `claude` (Qualitätsmodus UC1/UC2, Vergleiche) | Subprozess `claude -p --model claude-opus-5-5 --output-format json [--json-schema …]`, `cwd` = leeres Temp-Verzeichnis (lädt sonst Projekt-CLAUDE.md und Hooks, ca. 32k Cache-Tokens), Nachrichtenliste wird zu einem Prompt geflacht, Schema-Antwort aus `structured_output`, Timeout 120 s, Wandzeit ca. 15 s, Abo, kein API-Key; nie im UC3-Lauf | `CLAUDE_MODEL` optional |
| `mistral` (EU, Zweitanbieter für den Live-Austausch vor der Jury) | openai-SDK gegen `MISTRAL_BASE_URL`; Small für Klassifizieren und Extrahieren, Large nur für Texte; Budget 10 € (Limit setzt der Owner in der Konsole) | `MISTRAL_API_KEY`, `MISTRAL_MODEL_CHAT`, `MISTRAL_MODEL_FAST` |
| `ollama` (Offline-Notnagel auf m5, gemma4/qwen3) | openai-SDK gegen `OLLAMA_BASE_URL` | `OLLAMA_BASE_URL`, `OLLAMA_MODEL` |
| `mock` (Tests, CI, Jury ohne Netz) | Fixtures `shared/py/plattform/fixtures/<zweck>.json`, deterministisch | keine |

`zweck` routet: eine Tabelle `shared/py/plattform/zwecke.toml` ordnet jedem Zweck (z. B. `qs.einstufung`,
`agent.koordinator`, `frage.sql`, `uc1.lotse`) Provider-Vorzug, Modellgröße (fast|chat) und Fallback-Kette zu
(Standard: azure → mistral → ollama; UC3-Agenten ohne claude). Jeder Aufruf schreibt eine Protokollzeile
(provider, modell und Version, zweck, Prompt-Hash, Dauer, Tokens, Fallback-Stufe), nie den Inhalt.
Zahlen rechnet immer die DB: ein Providerwechsel darf keine Zahl ändern (AC E0-2e). Azure-Limit 200.000 Token/s laut Handzettel.
Keine Einzeldaten an das Modell (nur Schema, Aggregate, Prüfergebnisse). `web/` ruft nie einen Provider direkt;
der Modell-Badge liest `GET /api/plattform/modell` (E0-Route, führt `uv run python -m plattform.llm status`).

### Protokoll und Freigabe (Vertrag P)

- DDL `shared/py/plattform/sql/meta.sql`: `meta.protokoll` (id, zeit, uc, akteur agent|mensch, name, anweisung,
  wirkung, vorschlag_typ, status offen|freigegeben|abgelehnt, modell, provider, ref, commit_hash) und
  `meta.freigabe` (id, protokoll_id, name, zeitpunkt, entscheidung ja|nein, begruendung). Jeder UC spielt die DDL
  in seine eigene DB ein.
- `meta.freigabe` trägt zusätzlich `objekt_typ` (datei|regel|lieferung|antwort) und `objekt_ref`, damit „was
  freigegeben wurde“ (Regel R7 der Aufgabenstellung) direkt beantwortbar ist. DDL beginnt mit
  `CREATE SCHEMA IF NOT EXISTS meta`, kein `DROP`; UC-eigene `meta.*`-Tabellen kommen danach.
- `plattform.freigabe.freigeben(conn, vorschlag_id: int, name, repo_pfad) -> Freigabe`: Name = Vor- und Nachname
  (mindestens zwei Wörter, keine Steuerzeichen oder Zeilenumbrüche, kein `:`; Sperrliste als Held-out-Fixture:
  `Team`, `Team UC3`, `Admin Admin`, `KI Agent`, Einwort), schreibt `meta.freigabe` und den Commit in einer
  Transaktion (bei Git-Fehler Rollback): `git -C <repo_pfad> commit --allow-empty -m '<Anweisung>'
  --trailer 'Freigegeben-von: <Name>' --trailer 'Vorschlag: <id>' --trailer 'Modell: <modell>@<provider>'`
  als argv-Liste, nie als Shell-String; `--allow-empty`, weil eine Regeländerung nur Daten ändert. Ein Dateilock
  `.git/kic-freigabe.lock` serialisiert parallele Freigaben; `repo_pfad` ist der Worktree des UC.
  `ablehnen(...)` analog ohne Commit. Agenten-Skripte unter `erzeugt/` starten nur mit Status freigegeben,
  sonst `NichtFreigegeben` (Regel R6d).
- JSON-Vertrag für die UI: `GET /api/<uc>/protokoll?status=offen` liefert
  `Eintrag {id, zeit, uc, akteur, name, anweisung, wirkung, status, modell, ref}`; die Protokoll-Schublade in der
  Shell zeigt die Einträge des aktiven UC. Freigabe aus der UI ruft `POST /api/<uc>/freigabe {id, name, entscheidung}`,
  der UC-Route-Handler ruft die CLI (`uv run <uc> freigabe <id> --name …`).

### Header-Navigation und UC-Einhängen (Vertrag H)

- Routen: `/` Übersicht (Landing), `/uc1` SV KI-Lotse, `/uc2` HealthPolicy Simulator, `/uc3` StatAgent
  (Badge „bewertet“), `/praesentation`. Header rechts: ModellBadge (provider · modell), Schalter Protokoll-Schublade.
  Auf `/` und `/praesentation` zeigt die Schublade UC3 (bewertet). Der JSON-Vertrag `Eintrag` liegt als
  `shared/schema/protokoll-eintrag.json` (aus pydantic erzeugt) und wird von pytest (CLI `--json`) und Vitest/zod
  (Route-Antwort) geprüft.
- Registry `shared/ui/src/ucs.ts`: `{id, name, kurz, route, bewertet, status: "leer"|"aktiv"}`; die Shell rendert
  daraus Header und Landing-Karten. Ein UC hängt sich ein, indem er (1) seinen Eintrag in der Registry setzt,
  (2) `web/app/<uc>/layout.tsx` mit `<UcBereich uc="uc3" nav={[...]}>` anlegt (Unter-Navigation des UC),
  (3) seine Route-Handler unter `web/app/api/<uc>/**` liefert. Leere Bereiche zeigen den Leerzustand-Baustein.
- Datenweg: Route-Handler lesen die UC-Datenbank lesend (postgres.js) oder starten die UC-CLI als Subprozess mit
  `--json`. Streaming (Chat, Voice) geht an die FastAPI des UC (Port 810N), nie an das Modell direkt.

### Voice (Vertrag V, Konzept nach everlast, Code neu)

- `plattform.voice.erstelle_router(antwort)` mit `antwort(nachrichten, sitzung) -> {text, belege: list[Beleg]}`
  liefert einen FastAPI-Router mit `POST /chat/completions` (OpenAI-kompatibel, Vapi „Custom LLM“ ruft mit
  `stream: true`: Antwort als SSE `chat.completion.chunk` mit `delta.content` und `data: [DONE]`; Bearer-Schlüssel
  `VAPI_CUSTOM_LLM_KEY` Pflicht, sonst 401) und `POST /vapi/webhook` (Secret `x-vapi-secret` in konstanter Zeit
  verglichen, 503 wenn `VAPI_WEBHOOK_SECRET` fehlt, 401 vor dem Body-Lesen, andere Typen 200 `ignored`, nur
  `end-of-call-report`, Inhalte nicht loggen). Belege werden gesprochen („Beleg: roh.lieferung 2025-03“) und in
  der Sitzung für die UI abgelegt; ein Header reicht nicht, Vapi liest ihn nicht.
- Geheimnis für `/chat/completions`: Vapi sendet den im Assistant konfigurierten Custom-LLM-Schlüssel als
  `Authorization: Bearer`; der Router prüft ihn gegen `VAPI_CUSTOM_LLM_KEY` (Spike 1 in UC1 #28 misst, ob Vapi den
  Header so setzt; Fallback: Token im Pfad `/chat/completions/<token>`). `sitzung` enthält `call_id` aus dem
  Vapi-Body (`call.id`), `uc` und `gestartet`; die UC bindet daran ihre eigene Sitzung.
- Tunnel-Middleware in `plattform.voice`: Anfragen über die Tunnel-Domain (Host- oder `CF-Connecting-IP`-Header)
  dürfen nur `/chat/completions` und `/vapi/webhook` erreichen, alles andere 404; lokal bleibt die ganze API offen.
- `shared/ui` `<VoiceKnopf assistantId>`: Client-Komponente ohne SSR (`next/dynamic`, `ssr: false`), `@vapi-ai/web`
  in `web/package.json`, `NEXT_PUBLIC_VAPI_PUBLIC_KEY`, `recordingEnabled: false`; Transkript als Turns in der
  Oberfläche; Text-Fallback ist Pflicht (gleiche `antwort`-Funktion über Chat; neu gegenüber everlast).
- Vapi ist ein US-Dienst: Datenfluss im README offenlegen; kein Einzeldatum in die Antwort, nur Aggregate mit Beleg.
- Erreichbarkeit: `PUBLIC_URL` per cloudflared (named tunnel mit fester URL, sonst nach jedem Start
  `python -m plattform.voice sync`, das die Custom-LLM-URL im Assistant aktualisiert). Fehlt `PUBLIC_URL`, ist der
  VoiceKnopf deaktiviert mit Hinweis, der Text-Fallback bleibt.
- Umgebungsvariablen: `VAPI_API_KEY`, `VAPI_PUBLIC_KEY`, `VAPI_WEBHOOK_SECRET`, `VAPI_CUSTOM_LLM_KEY`, `PUBLIC_URL`.

### Design (Vertrag D)

- Tokens Klarton+ aus der Pen-Datei (per Pencil-MCP `get_style`) nach `shared/ui/src/tokens.css` als Tailwind-4
  `@theme`: ink #0B1F2A, paper #F4F7F5, klar-grün #007A50, ki-violett #5B3DF5 (nur Label und 2-px-Linie), beleg-gelb
  #F5D54F (nur Fläche), navy #001E50, slate #475256. Schriften Space Grotesk, Inter, JetBrains Mono. Typo-Skala
  56/32/20/16/14/12, Abstände 4/8/16/24/32/48/64. Hell, kein Dark Mode. Keine SV-Logos.
- Eigene, ruhige Elemente nach den Pen-Frames; keine shadcn-Defaults ohne Anpassung. Status immer Symbol plus Wort.
  Glossar-Untertitel je Fachbegriff. Je Screen eine Hauptaussage und eine Hauptaktion.
- Anti-Schablonen-Gate: `measureSlop({root:'body'})` (impeccable-Katalog, Apache-2.0; die Skript-Datei hat keinen
  Lizenzkopf und keinen Export, beides wird beim Übernehmen ergänzt, Laden per `addScriptTag`) als Playwright-Test
  gegen jede Route, Desktop 1440×900 und Mobil 390×844, Ziel 0 Treffer in den zwölf Schlüsseln kickersMono,
  kickersCaps, iconTiles, shadowCards, ghostCards, gradientText, glassBlur, lightOrbs, pulsingDecor, sparklesNonAi,
  emDashes, questionHeadings. `genericFontShare` ist ausgenommen und dokumentiert (Inter ist Vertrag). Eine
  Positiv-Fixture `slop-positive.html` muss in jedem der zwölf Schlüssel ≥ 1 liefern, sonst ist das Gate leer.
- Jede UI-Issue-AC trägt „entspricht Frame <ID> per Screenshot verglichen“ und „0 Schablonen-Treffer“.
  Frame-IDs (Pen ab x=12000, e5 12:5x): Header nas8Y, Herkunft-Chip QVMco, Warn-Chip NeqAs, Modell-Badge CKCV4,
  Freigabe-Karte FgY98, Protokoll-Schublade yK42X, Sprach-Pegel eE7uh, Landing c0eRD, Präsentation H8TJkE,
  UC3 Start bgAUw, Lauf-Detail fFDc8, Abgabe L6f3Mp, Lauf 2025-10 angehalten P6gBQD, dazu die 13 Owner-Frames ab x=4800.

### In-Scope (E0)
- [ ] Monorepo-Grundgerüst: pnpm- und uv-Workspace, CI (gitleaks, python, web) grün im ersten MR, `.env.example` auf
      we-16 mit `LLM_PROVIDER`, `OLLAMA_*`, `VAPI_*`, `PUBLIC_URL`; CLAUDE.md Struktur und Ausnahme everlast-Konzept
- [ ] `plattform.llm` mit fünf Providern, Protokollzeile, Smoke-Tests
- [ ] `plattform.protokoll` und `plattform.freigabe` samt DDL und JSON-Vertrag
- [ ] `shared/ui` Tokens und Basis-Elemente (Text, Knopf, Feld, Tabelle, Status, Leerzustand)
- [ ] `web/` Shell: Header-Navigation, ModellBadge, Protokoll-Schublade, Registry, leere Bereiche /uc1 /uc2 /uc3
- [ ] Landingpage/Übersicht (wer, Leitmotiv, drei UC-Karten mit UC3 „bewertet“, wie gebaut, gefundene Datenfehler)
- [ ] Präsentations-Tab: Slides laufen in der App (Inhalt von e5, Rahmen von E0)
- [ ] Bausteine Herkunft-Chip, Freigabe-Karte (drei Zonen, Freigabe-Waage), Protokoll-Schublade
- [ ] `plattform.voice` und `<VoiceKnopf>` mit Text-Fallback
- [ ] Anti-Schablonen-Gate als Playwright-Test

### In-Scope (E1, bestehende Kinder #13–#20, in dieser Planung geschärft)
- [ ] #13 W0 Gerüst in `uc3/` (statt `pipeline/`), DDL, CLI, LLM-Adapter aus `plattform.llm`
- [ ] #14 W1 Kern: Golden-Set-Test 2.880 Zellen als pytest gegen `beispielbericht_2024-08.xlsx`
- [ ] #15 W1 Agent-Laufzeit: Vorschlag → Freigabe mit Name → Commit mit Trailer über `plattform.freigabe`
- [ ] #16 W2 Betrieb v1: 24 Läufe, P01–P24, 24 QB, Sheet v1
- [ ] #17 W3 Änderungsaufträge 1–3, Sheet v2, ministerium_2026-07.csv, Datenanfragen (`frage` liefert SQL)
- [ ] #18 W3 Web-UI UC3 in `web/app/uc3/**` auf der E0-Shell, Frames bgAUw fFDc8 L6f3Mp P6gBQD sowie iU5QZ fJdk9 qVTQj oBcQu PPe1S F2sT1 bawCX Xw9fE DbY1q egqhg XlcSB uJbeL
- [ ] #19 W4/W5 Optimum: ÖNACE 5-Steller, Regionen, Pensionen, Live-Varianten A/B/C, Determinismus-Hash
- [ ] #20 Abgabe und Jury (gehört zu E6 #27, bleibt Kind von #22 als Terminanker)

### Out-of-Scope
- Dark Mode, Charts außer Zeitreihe und Vorher/Nachher (Streichliste uc3-panel)
- Ein TS-Modell-Schalter oder direkte Modellaufrufe aus `web/` (eine Implementierung in Python genügt)
- Eigene Vapi-Tool-Calls (Freigabe per Sprache über Vapi): Live-Änderung per Sprache läuft über den Text-/Voice-Weg
  des UC3-Agenten, nicht über Vapi-Tools
- Deploy (Vercel) und Docker-Build der Web-App: Demo läuft lokal am M4
- Inhalte von UC1, UC2, Slides (eigene Tabs #23, #24, #26) und Abgabe-Ablauf (#27)
- Code-Übernahme aus everlast: nur Konzept und Verträge, Code entsteht neu (Repo ist öffentlich)

### First Real Use / Kill
Erster echter Gebrauch: UC3-Session hängt am Do 05.11. bis 18:00 `web/app/uc3/` in die Shell und ruft
`plattform.llm.complete` aus dem Koordinator-Agenten (#15). Steht die Shell bis 18:00 nicht, baut UC3 die fünf
Seiten direkt unter `web/app/uc3/` ohne Bausteine weiter (Fallback #18), und E0 wird auf Modell-Schalter,
Protokoll und Freigabe gekürzt. Landing, Präsentations-Tab und Voice werden gestrichen, wenn abgabe-v2 um 23:00
nicht steht (gleiche Regel wie #18).

## 3. Acceptance Criteria

### E0-1 Monorepo-Grundgerüst und CI
```gherkin
Given ein frischer Clone von app/ mit pnpm 10 und uv 0.12
When die MR-Pipeline läuft
Then der web-Job führt an der Wurzel `pnpm install --frozen-lockfile` und `pnpm -r exec tsgo --noEmit` aus, der
     python-Job `uv sync --frozen --all-packages` und `uv run python -c "import plattform"`, beide grün
```
Oracle: Job-Log der MR-Pipeline, in dem genau diese Befehle stehen; der lokale Lauf zählt nicht.
```gherkin
Given .env.example im Repo
When `grep -c we-16 .env.example` und `grep -c '^LLM_PROVIDER=' .env.example` laufen
Then beide liefern 1, und `grep -c we-01 .env.example` liefert 0; gitleaks findet keinen Wert
```
Oracle: gitleaks-Job der Pipeline plus `git grep -c we-01` = 0.

### E0-2 Modell-Schalter
```gherkin
Given LLM_PROVIDER=mock
When `complete([{"role":"user","content":"ping-7f3a"}], zweck="smoke")` zweimal läuft
Then beide Antworten sind byteidentisch, je Aufruf genau eine Protokollzeile, `grep -c ping-7f3a` im Protokoll = 0,
     und alle fünf Provider-Klassen bestehen denselben Contract-Test der `Antwort`-Felder
```
Oracle: pytest; Contract-Test gilt für alle Provider, nicht nur mock.
```gherkin
Given LLM_PROVIDER in {azure, claude, mistral}
When `uv run python -m plattform.llm smoke` läuft
Then jeder Provider liefert text != "" (azure, mistral < 30 s; claude < 60 s) und `aktives_modell()` nennt provider, modell und Version
```
Oracle: Live-Antwort des jeweiligen Dienstes (Azure-Endpunkt we-16, Claude-Abo, Mistral); Ausgabe ins
`docs/models.md` mit Zeitstempel. Kann nur mit Netz und Schlüssel laufen → External Acceptance EA-1.
```gherkin
Given mock mit Fault-Fixture (erst ungültiges JSON, dann gültiges; zweite Fixture zweimal ungültig)
When `complete(..., schema=Einstufung)` läuft
Then Fall 1 validiert nach genau 2 Aufrufen, Fall 2 wirft `SchemaFehler`
```
Oracle: pytest mit Fault-Fixture; Live-Teil unter EA-1.
```gherkin
Given Lauf 2024-08 mit LLM_PROVIDER=azure und derselbe Lauf mit LLM_PROVIDER=mistral (oder mock)
When `uv run statagent lauf --lieferung 2024-08` beide Male läuft
Then `meta.lauf.ergebnis_hash` ist gleich: ein Providerwechsel ändert keine Zahl (E0-2e)
```
Oracle: Hash-Vergleich; der Lauf darf `plattform.llm` nicht einmal importieren (Regel R2 offline).

### E0-3 Protokoll und Freigabe
```gherkin
Given ein offener Vorschlag in meta.protokoll mit Anweisung „X“
When `freigeben(conn, id, name, repo)` mit jedem Namen der Held-out-Liste (`Team`, `Team UC3`, `Admin Admin`, `KI Agent`, `Bernhard`, `A\nCo-authored-by: x`) läuft
Then jeder wird mit NameUngueltig abgelehnt, kein Commit, Status bleibt offen
```
Oracle: pytest gegen Wegwerf-Repo in tmp, `git log` bleibt leer.
```gherkin
Given derselbe Vorschlag
When `freigeben(conn, id, "Bernhard Götzendorfer", repo)` läuft
Then meta.freigabe hat eine Zeile mit Name, Zeitpunkt, objekt_typ und objekt_ref, Status freigegeben,
     `git log -1 --format=%s` = „X“ und `--format=%(trailers)` zeigt `Freigegeben-von: Bernhard Götzendorfer`,
     `Vorschlag: <id>`, `Modell: …`; ein Agenten-Skript ohne Freigabe bricht mit NichtFreigegeben ab
```
Oracle: `git log --format=%(trailers)` des echten Repos (Test gegen Wegwerf-Repo in tmp) plus PG-Abfrage.

### E0-4 Design-Tokens und Basis-Elemente
```gherkin
Given shared/ui/src/tokens.css und `shared/ui/tokens.snapshot.json` (exportiert aus Pencil `get_style`, Zeitstempel im Kopf)
When ein Vitest die `--color-*`, `--font-*` und `--text-*`-Werte des `@theme` parst
Then 7 Farben, 3 Schriften und die Skala 56/32/20/16/14/12 stimmen genau mit dem Snapshot überein, keine weitere `--text-*`
```
Oracle: Vitest gegen den Pencil-Snapshot; den Snapshot erzeugt Pencil, nicht der Autor.

### E0-5 Shell mit UC-Wechsel
```gherkin
Given `pnpm dev` läuft mit LLM_PROVIDER=mock
When Playwright /, /uc1, /uc2, /uc3, /praesentation öffnet
Then jede Route antwortet 200, der Header zeigt fünf Einträge mit aktivem Zustand, UC3 trägt „bewertet“,
     der ModellBadge zeigt „mock“, leere Bereiche zeigen den Leerzustand, 0 Konsolenfehler
```
Oracle: Playwright-Lauf mit AX-Snapshot und Konsole; Screenshot gegen Frame nas8Y (Header) und CKCV4 (Modell-Badge) → EA-2.
```gherkin
Given die Registry hat einen UC-Eintrag mit status "aktiv" und web/app/uc3/layout.tsx nutzt <UcBereich>
When /uc3 geöffnet wird
Then die Unter-Navigation des UC erscheint unter dem Header und die Protokoll-Schublade listet GET /api/uc3/protokoll,
     dessen Antwort gegen `shared/schema/protokoll-eintrag.json` validiert (ebenso `uv run uc3 protokoll --json`)
```
Oracle: Playwright plus beidseitiger Schema-Test (pytest, Vitest) gegen das aus pydantic erzeugte Schema.

### E0-6 Landingpage
```gherkin
Given / geöffnet
When die Seite gerendert ist
Then sie zeigt: Team und Leitmotiv, drei UC-Karten (UC3 „bewertet“), „wie gebaut“, Tabelle gefundener Datenfehler
     aus meta.pruefung_treffer der UC3-DB (Zeilenzahl = `select count(*)`; Fixture nur bei fehlender DB, sichtbar
     als „Beispieldaten“), measureSlop({root:'body'}) = 0 auf Desktop und Mobil
```
Oracle: Playwright + measureSlop; Screenshot gegen Frame c0eRD → EA-2.

### E0-7 Präsentations-Tab
```gherkin
Given /praesentation mit einem Slide-Deck aus `web/content/slides/*.md` (Inhalt von e5)
When Pfeiltaste rechts gedrückt wird
Then die nächste Folie erscheint, die URL trägt `?folie=N`, Vollbild per Taste F, 0 Schablonen-Treffer
```
Oracle: Playwright; Screenshot gegen Frame H8TJkE, Inhalt-Abnahme durch e5 → EA-2.

### E0-8 Bausteine
```gherkin
Given <FreigabeKarte> mit Zitat, vorher 387.390, nachher 387.130 und Name leer
When gerendert
Then drei Zonen in dieser Reihenfolge, Δ −260 und −0,07 % in 56-px-Zahlen, Button „Ja, so rechnen wir ab jetzt“
     ist deaktiviert bis ein Name mit zwei Wörtern steht und nie Enter-Vorauswahl
```
Oracle: Vitest + Testing Library; Screenshot gegen Frame FgY98 (Freigabe-Karte) und qVTQj (Freigaben · einfach) → EA-2.
```gherkin
Given <HerkunftChip sql="select …" lauf="2025-03">
When geklickt
Then das SQL und der Lauf werden angezeigt und per Knopf kopierbar
```
Oracle: Vitest; Screenshot gegen Frame QVMco (Herkunft-Chip), NeqAs (Warn-Chip), yK42X (Protokoll-Schublade) → EA-2.

### E0-9 Voice
```gherkin
Given die UC3-FastAPI mit `erstelle_router(antwort)` und LLM_PROVIDER=mock
When `POST /chat/completions` mit der aufgezeichneten Vapi-Anfrage (`stream: true`, Bearer) kommt
Then die Antwort ist SSE mit `delta.content`-Chunks, deren Summe antwort.text samt gesprochenem Beleg ist, endet mit
     `[DONE]`; `sitzung.call_id` = `call.id` des Bodys; ohne oder mit falschem Bearer 401; Webhook ohne Secret 401,
     ohne gesetzte Variable 503, anderer Typ 200 `ignored`; über Tunnel-Host liefert `GET /laeufe` 404
```
Oracle: pytest gegen den Router mit der aufgezeichneten Vapi-Anfrage als Fixture.
```gherkin
Given PUBLIC_URL per Tunnel und VAPI_PUBLIC_KEY
When der Owner im Browser den VoiceKnopf drückt und „Wie viele Beschäftigte im März 2025?“ fragt
Then die gesprochene Zahl ist gleich dem vorab notierten Ergebnis der psql-Abfrage für 2025-03 (387.180), mit Beleg;
     der Text-Fallback liefert dieselbe Zahl
```
Oracle: Vapi-Call-Log (end-of-call-report) plus Transkript in der UI; Pegel nach Frame eE7uh → EA-3.

### E0-10 Anti-Schablonen-Gate
```gherkin
Given alle Routen der App, measureSlop aus dem Repo (Quelle und Lizenz im Kopf) und `slop-positive.html`
When `pnpm test:slop` läuft (Playwright, 1440×900 und 390×844, `root:'body'`)
Then jede Route meldet 0 Treffer in den zwölf Schlüsseln, und die Positiv-Fixture meldet ≥ 1 in jedem Schlüssel
```
Oracle: Playwright-Report; der Katalog stammt aus impeccable, die Positiv-Fixture belegt, dass das Gate misst.

### E1 (Schärfung der Kinder #13–#20, je Issue ein Kommentar mit AC, Oracle, Welle)
```gherkin
Given die DB mit roh.lieferung 2024-08 und Regelsatz v1
When `uv run statagent lauf --lieferung 2024-08` läuft
Then alle 2.880 Zahlenzellen von Tab1–Tab13 stimmen mit beispielbericht_2024-08.xlsx überein (0 Abweichungen)
```
Oracle: `beispielbericht_2024-08.xlsx` des Veranstalters (Kalibrierfixture mit bekannten Antworten); pytest liest beide.
```gherkin
Given zwei Läufe derselben Lieferung mit demselben Regelsatz
When `meta.lauf.ergebnis_hash` verglichen wird
Then die Hashes sind gleich
```
Oracle: Hash-Vergleich; unabhängig vom Autor.
```gherkin
Given Lieferung 2025-10
When der Lauf prüft
Then P15–P17 melden genau 78.949 fehlende Verhältnisse, der Monat steht auf „vorläufig“, `count(*)` von 2025-10-Zeilen aus
     Lieferung 2025-11 = 0, und für jeden Monat gilt gelesen = gezählt + nicht gezählt + ausgeschlossen
```
Oracle: Lead-Gegenrechnung als Soll plus SQL-Abrechnung; die QB-Vorlage hat keine Zeile „nicht gezählt“, das wird als Annahme im QB benannt.
```gherkin
Given die Abgabedateien in abgabe/
When `uv run statagent pruefe-abgabe` läuft
Then alle fünf Abgabepunkte sind da, 24 QB mit je fünf Abschnitten und Einstufung aus der Drei-Werte-Liste,
     protokoll.md = Export aus git log plus meta.protokoll, `--help` für lauf/berichte/freigabe/frage, keine Regelkonstanten in uc3/statagent
```
Oracle: Exit-Code des Validators; gehört zu #16/#20.

### External Acceptance

| ID | Criterion | Oracle | Owner | Not before | Pass condition | Fallback if it cannot run |
|----|-----------|--------|-------|------------|----------------|---------------------------|
| EA-1 | E0-2 Live-Smoke azure, claude, mistral | Antwort des Dienstes, `docs/models.md` mit Zeitstempel | Bau-Session E0 | 2026-11-05 14:00 | drei Provider liefern Text < 30 s | mock in CI; Provider als „nicht belegt“ in models.md |
| EA-2 | E0-5/6/7/8 und #18: Screens entsprechen Frames | Screenshot-Vergleich gegen die Pen-Frames (Vertrag D) | e5-praesentation-05 | 2026-11-05 18:00 | je Screen „entspricht Frame X“ als Kommentar von e5 | Vergleich gegen Frame qVTQj und Typo-Skala durch E0-Session, als „nicht abgenommen“ markiert |
| EA-3 | E0-9 Voice-Anruf Ende-zu-Ende | Vapi end-of-call-report plus UI-Transkript | Owner (Vapi-Konto) | 2026-11-05 22:00 | gesprochene Zahl = vorab notierte psql-Zahl 2025-03 (387.180), Transkript sichtbar | Text-Fallback vorführen, Voice als „nicht belegt“ |
| EA-4 | E1 Golden Set 08/2024 und Determinismus auf dem Jury-Weg (`DB_PORT=5433 docker compose down -v && up`, frischer Start, zwei Läufe) | `beispielbericht_2024-08.xlsx` plus sha256 über kanonisch sortiertes CSV aus `stat.*` | Bau-Session UC3 | nach #16 | 2.880/2.880 und Hash gleich | Homebrew-PG-Weg dokumentiert, Docker als Einschränkung im README |

## 4. Technical Notes

### Affected Files (neu)
- `pnpm-workspace.yaml`, `package.json`, `pyproject.toml` (uv workspace: shared/py, uc1, uc2, uc3), `.gitlab-ci.yml` (Workspace-Pfade)
- `shared/py/plattform/{llm.py, protokoll.py, freigabe.py, voice.py, sql/meta.sql, fixtures/}`, `shared/py/tests/`
- `shared/ui/src/{tokens.css, ucs.ts, Shell.tsx, Header.tsx, ModellBadge.tsx, HerkunftChip.tsx, FreigabeKarte.tsx, ProtokollSchublade.tsx, VoiceKnopf.tsx, Leerzustand.tsx}`
- `web/app/{layout.tsx, page.tsx, praesentation/, api/plattform/modell/route.ts, uc1/, uc2/, uc3/}`, `web/tests/slop.spec.ts`, `web/tests/lib/slop-measure.js`
- `.env.example`, `CLAUDE.md` (Struktur, Ausnahme everlast-Konzept), `docs/models.md`

### Architecture
Eine Next.js-App, ein Python-Workspace. Web ist Bedienoberfläche: lesend auf PG, CLI als Subprozess, Streaming
über die UC-FastAPI. Alle Modellaufrufe laufen durch `plattform.llm`; alle Änderungen durch `plattform.freigabe`.
Frame-Treue per Screenshot, Schablonenfreiheit per measureSlop.

### Data Model Changes
`meta.protokoll`, `meta.freigabe` (shared DDL) in jeder UC-DB; UC3 ergänzt `meta.regel`, `meta.lauf`,
`meta.pruefung_treffer`, `stat.*` nach uc3-architektur.md. UC1 legt DB `lotse` auf 5433 an (Volltext german,
kein pgvector).

### API Changes
`GET /api/plattform/modell`; je UC `GET /api/<uc>/protokoll`, `POST /api/<uc>/freigabe`; UC-FastAPI
`POST /chat/completions`, `POST /vapi/webhook`.

## 5. Risks & Dependencies

| Risk | Impact | Mitigation | Triage |
|------|--------|------------|--------|
| E0 kostet Stunden ohne Punkte (nur UC3 wird bewertet) | hoch | E0-Kern (Gerüst, Schalter, Protokoll, Shell) bis 18:00; Landing, Präsentation, Voice erst nach abgabe-v2 23:00; Owner-Frage dazu | Experiment |
| Shell nicht rechtzeitig → UC3-UI blockiert | hoch | Fallback: UC3 baut direkt unter web/app/uc3 ohne Bausteine (#18) | Implement |
| `claude -p` als Provider ist langsam (3,1 s Smoke) und nicht in CI | mittel | nur UC1/UC2-Qualitätsmodus, nie im Lauf; mock in CI | Implement |
| Vapi braucht öffentlichen Tunnel; US-Dienst | mittel | Text-Fallback Pflicht; Datenfluss im README; nur Aggregate | Implement |
| Pen-Frames ab x=12000 können sich bis zur Abnahme noch ändern | niedrig | Frame-ID in jeder AC, Vergleich erst bei EA-2 | Implement |
| pnpm/uv-Workspace bricht den CI-Vorschlag (cd web) | niedrig | CI-Pfade in E0-1 anpassen, erster MR ist der Test | Implement |
| Feature-Stopp 05:00 (uc3-bauplan) gegen 07:00 (Konzept) | niedrig | 05:00 gilt (Rangfolge Quellenkarte § 8) | Implement |
| Zwei Schlüsselwege (.env.local an Wurzel, web braucht NEXT_PUBLIC_*) | niedrig | web-Skripte starten über `dotenv -o -e ../.env.local`; nur VAPI_PUBLIC_KEY wird NEXT_PUBLIC_ | Implement |
| everlast-Code im öffentlichen Repo | mittel | nur Konzept, Code neu; README weist Herkunft aus | Reject (Code-Übernahme) |
| CI-Vorschlag bricht mit Workspace (`cd web`, Cache-Key `web/pnpm-lock.yaml`, `uv sync` ohne `--all-packages`, leerer CI-Postgres) `.gitlab-ci.yml:50,66-70` | hoch | E0-1 schreibt CI um; `pytest.mark.daten` nur lokal | Implement |
| `claude -p` kostet ca. 15 s Wandzeit und ca. 32k Cache-Tokens je Aufruf (gemessen) | mittel | `cwd` leeres Temp-Verzeichnis, nie im UC3-Lauf, AC < 60 s | Implement |
| Vapi streamt und authentifiziert per Bearer; Header `x-belege` wird nicht gelesen (inference aus Vapi-Vertrag) | hoch | SSE-Antwort, Bearer-Pflicht, Beleg gesprochen; Fixture der echten Anfrage aufzeichnen (Next check) | Implement |
| Namensregel „zwei Wörter, nicht Team“ lässt „Team UC3“ durch; Zeilenumbruch erzeugt eigene Trailer | mittel | Held-out-Namensliste, Steuerzeichen verboten, argv statt Shell | Implement |
| `git commit` ohne Dateidiff scheitert bei Regeländerungen; parallele Freigaben kollidieren am index.lock | mittel | `--allow-empty`, Transaktion mit Rollback, Dateilock, `repo_pfad` = UC-Worktree | Implement |
| measureSlop misst nur `<main>`, Schlüssel heißen `kickersMono`/`kickersCaps`, kein Export; leeres Gate besteht still | mittel | `root:'body'`, zwölf Schlüssel, Positiv-Fixture, `addScriptTag` | Implement |
| Zweiter Postgres auf 5432; Route ohne Port trifft die falsche DB | mittel | `UC*_DATABASE_URL` mit 5433 in `.env.example`, Jury-Weg `DB_PORT=5433` | Implement |
| `meta`-Schema von zwei DDL-Eigentümern (plattform, uc3) | niedrig | `CREATE SCHEMA IF NOT EXISTS`, kein DROP, Reihenfolge plattform → UC, Schema-Snapshot `pg_dump -n meta` | Implement |
| Quick-Tunnel-URL wechselt je Start; Vapi-Assistant zeigt ins Leere | mittel | named tunnel oder `voice sync` nach Start; VoiceKnopf ohne PUBLIC_URL deaktiviert | Implement |
| Regeln R2 (offline), R3 (keine Konstanten), R6d (Freigabe vor erster Ausführung), R8 (Anweisung als Commit-Nachricht) ohne AC | hoch | E0-2e, E0-3, `pruefe-abgabe` ergänzt | Implement |

### Dependencies
- #21 E0 (dieses Dokument), #22 E1 mit Kindern #13–#20; #23 UC1 und #24 UC2 bauen auf Verträgen O, M, P, H, V, D
- #26 e5: Frame-IDs für Shell, Landing, Bausteine, Präsentation (EA-2); Slide-Inhalt
- #27 E6 Abgabe: GitHub-Push erst Fr kurz vor 09:00
- Azure-Schlüssel und Endpunkt we-16: vorhanden (12:2x); Vapi-Schlüssel: vorhanden; Vapi-Konto-Freigabe: Owner
