# OneShotAndy · KI Challenge 2026

Beitrag von Team OneShotAndy zur **KI Challenge 2026** des Dachverbands der österreichischen
Sozialversicherungsträger und der WK Wien (05. bis 06.11.2026). Bewertet wird **Use Case 3, StatAgent**.

Die Pflichtabschnitte stehen in dieser Reihenfolge: [Lösung und Ansatz](#lösung-und-ansatz),
[Ausführung](#ausführung), [Abhängigkeiten und Voraussetzungen](#abhängigkeiten-und-voraussetzungen),
[Konfiguration](#konfiguration), [Grenzen und offene Punkte](#grenzen-und-offene-punkte),
[Vorab Entstandenes](#vorab-entstandenes), [Lizenzen](#lizenzen). Prüfliste dazu: `docs/abgabe/readme-pruefung.md`.

## Lösung und Ansatz

Eine Plattform, drei Räume und ein gemeinsamer Einstieg. Der Grundsatz überall: **Die KI schreibt Code und Texte,
das Programm rechnet.** Jede Zahl kommt aus der Datenbank und trägt ihren Beleg. Jede Änderung an Regeln oder
Code gibt ein Mensch mit Vor- und Nachnamen frei.

### Was gebaut wurde (Stand `main`, 05.11.2026)

| Raum | Was er tut | Stand | Details |
|---|---|---|---|
| **UC3 StatAgent** (bewertet) | Statistikprozess für die synthetische Beschäftigtenstatistik: 24 Monatslieferungen einlesen, nach Regeln bereinigen, zählen, prüfen, Qualitätsbericht und Aggregations-Sheet. Eigene Agenten setzen Änderungsaufträge um, ein Mensch gibt frei. | Gebaut. Die Seiten unter `/uc3` zeigen Läufe, Berichte, Klassifikationen, Freigaben und Datenanfragen, jede Zahl mit Beleg. | `uc3/README.md`, Ergebnisse in `abgabe/` |
| UC1 SV KI-Lotse | Hilft bei Fragen zu Gesundheit und Sozialversicherung, mit Quelle an jeder Antwort | Gebaut. Auf `/uc1` erzählt man seine Lage, der Lotse fragt bei Bedarf nach und antwortet mit einem Zitat als Beleg an jeder Aussage. Er nennt Antrag, zuständige Stelle und Termin. `/uc1?beispiel=pflege` spielt einen aufgezeichneten Fall ohne Netz ab. Der Lotse ist auch an `/uc4` angeschlossen. | `uc1/`, `docs/plan/uc1/` |
| UC2 HealthPolicy Simulator | Mehrere Akteure verhandeln politische, organisatorische und finanzielle Entscheidungen | Gebaut. Auf `/uc2` verhandeln Interessenvertretungen in Runden mit Moderator, mit Beleg aus dem Pressespiegel, wo es einen gibt; sonst ist die Haltung als Modellannahme markiert. Ein Mensch gibt das Ergebnis mit Namen frei, vorher heißt es „Entwurf“. Online zeigt `/uc2` eine aufgezeichnete Verhandlung; erfundene Beispielbelege sind dort als solche gekennzeichnet. | `uc2/README.md` |
| UC4 Gemeinsamer Einstieg | Eine Frage läuft nacheinander durch UC3, UC2 und UC1 (nicht bewertet) | Seite `/uc4`, lokal mit Modellwahl (Azure, Mistral, Claude oder Testbetrieb), online mit Azure oder Testbetrieb. UC3 liefert die Zahl, UC2 die Abwägung, UC1 die Erklärung; jede Antwort erscheint, sobald sie da ist. | `/uc4` in der App |

Gemeinsamer Kern in `shared/`:

- **Modell-Schalter** `plattform.llm`: ein Aufruf für alle Modelle, umschaltbar per `LLM_PROVIDER`, mit
  Ausweichkette und einer Protokollzeile je Aufruf, ohne Inhalt. Ein anderes Modell ändert keine Zahl.
- **Protokoll und Freigabe** `plattform.protokoll` und `plattform.freigabe` (siehe unten).
- **Lokale Embeddings** `plattform.embeddings`: macht aus Text Zahlenreihen für die Suche, ohne Cloud
  (Modell `google/embeddinggemma-2`).
- **Voice** `plattform.voice` und der Sprechknopf `VoiceKnopf` in `@kic/ui`: Sprachzugang über Vapi, siehe
  „Datenfluss Voice“. Ein Anruf braucht ein eingerichtetes Vapi-Konto.
- **Oberfläche** `@kic/ui`: Design-Tokens, ruhige Bausteine, Herkunft-Chip an jeder Zahl („SQL ansehen“),
  Freigabe-Karte, Protokoll-Schublade, Header mit Modell-Anzeige. Diese Teile sehen in allen drei Bereichen gleich
  aus: Beleg an der Zahl, Freigabe mit Namen, sichtbares Modell.

### Wie UC3 rechnet

Zahlen entstehen nur durch SQL und Python. `uc3 lauf` ruft kein Sprachmodell auf, zwei Läufe mit denselben Daten
und Regeln liefern denselben Ergebnis-Hash (eine Prüfsumme über das ganze Ergebnis). Regeln stehen als Daten in der
Datenbank (`meta.regel`), mit Gültigkeit, Begründung und Freigabe. Ein Modell schlägt nur Änderungen vor. Die
fünf Schritte eines Laufs (bereinigen, zählen, Revisionsbedarf, prüfen, abrechnen) stehen in `uc3/README.md`.

### Freigabe durch einen Menschen

1. Ein Agent schlägt eine Änderung vor (Regel, Code-Datei, Lieferung). Der Vorschlag steht im Protokoll
   `meta.protokoll`, mit Modell und Anweisung.
2. Ein Mensch gibt in der Freigabe-Karte frei. Verlangt sind Vor- und Nachname. Rollen wie „Team“ oder
   „Admin“ und Platzhalter werden abgelehnt.
3. `plattform.freigabe` schreibt die Entscheidung nach `meta.freigabe` und legt in derselben Transaktion einen
   Git-Commit an. Der Betreff ist die Anweisung, dazu kommen die Trailer `Freigegeben-von`, `Vorschlag` und `Modell`.
4. Ein Agenten-Skript startet nur, wenn genau dieser Dateistand freigegeben ist. Eine danach geänderte Datei
   gilt als nicht freigegeben.

`uv run python -m plattform.protokoll export --md --db <URL der UC-Datenbank>` erzeugt daraus das Protokoll aus
Git-Verlauf und Datenbank (Datei `protokoll.md`, je Use Case mit `--uc ucN`). Das fertige UC3-Protokoll liegt in
`abgabe/protokoll.md`.

### Datenfluss Voice

Voice geht über Vapi, einen **US-Dienst**. Der Ablauf, belegt in `docs/voice.md` (Abschnitt „Datenfluss Voice“):

1. Der Browser verbindet sich mit Vapi. Vapi erhält das **Audio** der Frage, schreibt es zu Text um und schickt das
   **Transkript** an unseren Server.
2. Unser Server antwortet mit seiner eigenen `antwort`-Funktion. Die Zahlen rechnet der Code aus der Datenbank,
   kein Sprachmodell. **Aus der Datenbank gehen nur Summen mit Beleg hinaus**, keine Einzeldaten, und SQL wird nicht
   gesprochen. Was jemand ins Mikrofon sagt, geht als Ton und Text an Vapi.
3. Die Aufnahme ist aus: `recordingEnabled` steht im Assistant auf `False`
   (`shared/py/plattform/voice/assistant.py`, Zeilen 56 und 57). Vapi hält das Transkript nach eigenen Regeln.
   Dort landen die gesprochene Frage und die Antwort mit Aggregat und Beleg.
4. Für Transkription und Stimme trägt der Assistant die Dienste Deepgram (`nova-2`) und Azure (`de-AT-IngridNeural`)
   ein (`assistant.py`, Zeilen 54 und 55). Sie laufen über Vapi.
5. Bei uns bleibt je Anruf eine Protokollzeile: Hash der Anruf-Kennung, Dauer, Endgrund. Kein Transkript, keine
   Antwort.

**Der Text bleibt der Hauptweg.** Dieselbe `antwort`-Funktion beantwortet Fragen auch über ein Textfeld, ohne dass
Daten an Vapi gehen. Ohne öffentliche Adresse (`PUBLIC_URL` leer) erreicht Vapi den Server gar nicht.

### Qualitätssicherung

Jeder Merge Request durchläuft die CI: Secret-Scan, ruff, mypy, pytest, TypeScript-Prüfung, ESLint, Vitest, ein
Produktions-Build der App und Browser-Tests mit Playwright auf Desktop und Mobil. Dazu gehören:

- ein **Anti-Schablonen-Gate**: Es misst jede Seite gegen zwölf Muster generischer, maschinell zusammengesetzter
  Oberflächen und verlangt 0 Treffer (`docs/design.md`).
- eine **Prüfung der Barrierefreiheit** mit axe (WCAG 2.1 AA): Schwere Verstöße lassen die Pipeline scheitern.
- eine **gefüllte UC3-Testdatenbank** aus erfundenen Mini-Lieferungen, damit die Seiten unter `/uc3` mit Daten
  geprüft werden und nicht nur im leeren Zustand.

## Ausführung

### Start

```bash
cp .env.example .env.local && sed -i.bak 's/^LLM_PROVIDER=.*/LLM_PROVIDER=mock/' .env.local  # ohne Schlüssel
uv sync --all-packages && pnpm install  # Python- und TypeScript-Workspace
pnpm dev                                # App auf http://localhost:3000
```

Die Seiten `/`, `/uc1`, `/uc2`, `/uc4` und `/praesentation` laufen damit lokal. Mit `LLM_PROVIDER=mock` antworten Modelle
mit festen Platzhaltern. Zahlen aus der Datenbank bleiben gleich. Die Seiten unter `/uc3` und die Zahl auf `/uc4`
brauchen die UC3-Datenbank mit gerechneten Läufen (nächster Abschnitt).

### Beispiellauf UC3 (Jury-Weg)

Voraussetzung ist die Datenbank des Veranstalters auf Port 5433. Im Ordner des Startpakets:
`DB_PORT=5433 docker compose up -d`, dann warten, bis `docker logs statagent-db` „fertig“ meldet. Danach im Repo:

```bash
uv run uc3 db init                          # Schemas, Klassifikationen, Regelsatz v1 (wiederholbar, löscht nichts)
uv run uc3 lauf --alle                      # 24 Einzelläufe 2024-08 bis 2026-07, in zeitlicher Reihenfolge
uv run uc3 eichen --lieferung 2024-08       # Vergleich mit dem Beispielbericht, Tab1 bis Tab13
uv run uc3 berichte --alle && uv run uc3 sheet   # 24 Qualitätsberichte und Aggregations-Sheet nach abgabe/
```

Das Ergebnis des Eichens ist die Zeile „Zellen 2880, abweichend 0“ (`uc3/README.md`). Alle Befehle und die Regeln
dazu stehen in `uc3/README.md`. Der Lauf braucht kein Netz und kein Sprachmodell.

**Nachweis des Jury-Wegs:** Die Abnahme in einer frischen Umgebung steht in `docs/abnahme/66.md`, mit Befehlen,
Zahlen und Ausgaben. Gemessen wurden alle 24 Läufe nacheinander auf einer frisch geladenen Datenbank: 24 von 24
fertig in rund 7 Minuten, das Ergebnis gleich dem früheren Lauf. Auf einer frischen Datenbank entstehen dieselben
Zahlen und Ergebnis-Hashes wie bei uns; der Status bleibt dort „vorläufig“, weil Freigaben und Veröffentlichung mit
Namen in unserer Team-Datenbank stehen. Den Nachweis dafür enthält `abgabe/protokoll.md`.

### Tests

- `uv run pytest -q` für den gemeinsamen Kern, je Use Case `cd ucN && uv run pytest -q`
- `pnpm typecheck && pnpm test` für den TypeScript-Teil
- UC3 gegen die echten Daten (Datenbank mit gerechneten Läufen, Golden Set mit 2.880 Zellen):
  `UC3_DATEN_URL=postgresql://statistik:statistik@localhost:5433/statistik uv run pytest -q -m daten uc3/tests`.

### Online-Demo

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
| uv (Python-Werkzeug) | 0.12, gemessen mit 0.12.12 | PRD `docs/prd/2026-11-05-e0-plattform-e1-uc3.md` Zeile 267; `uv --version` auf dem Entwicklungsrechner. `pyproject.toml` legt keine Mindestversion fest. |
| Node | 24 oder neuer | `engines` in `package.json` |
| pnpm | 10 (festgelegt auf 10.34.5) | `packageManager` in `package.json` |
| PostgreSQL | 16, Port **5433** (auf 5432 lauscht oft ein fremder Postgres) | `CLAUDE.md`, `uc3/README.md` |
| Docker | nur für die Datenbank des Veranstalters (`docker compose`) | `uc3/README.md` |
| Daten | Startpaket des Veranstalters, synthetisch, nicht im Repo; Ordner `../svbox/uc3` oder `STATAGENT_STARTPAKET` | `uc3/README.md` |

Wichtige Bibliotheken: `openai`, `fastapi`, `psycopg`, `pydantic` (Kern, `shared/py/pyproject.toml`), `typer` und
`openpyxl` (UC3, `uc3/pyproject.toml`), Next.js 16, React 19, `three` und `@vapi-ai/web` für den
Sprechknopf (App, `web/package.json`; geladen in `web/lib/plattform/voice-lader.ts`). Die genauen
Versionen stehen in `uv.lock` und `pnpm-lock.yaml`. Für die lokalen Embeddings kommt das Extra
`plattform[embeddings]` (sentence-transformers) dazu. Es ist nicht in der CI.

## Konfiguration

Alle Einstellungen kommen aus Umgebungsvariablen oder aus `.env.local` an der Repo-Wurzel. Vorlage mit allen
Schlüsselnamen und Erklärungen: `.env.example`. **Werte stehen nie im Repo.** Dieses README nennt nur Namen.

| Gruppe | Schlüssel |
|---|---|
| Modell-Schalter | `LLM_PROVIDER` (`azure`, `mistral`, `ollama`, `claude`, `mock`) |
| Azure (Standard) | `AZURE_OPENAI_BASE_URL`, `AZURE_OPENAI_MODEL`, `AZURE_API_KEY` |
| Mistral | `MISTRAL_API_KEY`, `MISTRAL_BASE_URL`, `MISTRAL_MODEL_CHAT`, `MISTRAL_MODEL_FAST` |
| Ollama | `OLLAMA_BASE_URL`, `OLLAMA_MODEL` |
| Claude | `CLAUDE_MODEL` (läuft über die Claude-Code-CLI im Abo, kein API-Schlüssel) |
| Datenbanken | `UC1_DATABASE_URL`, `UC2_DATABASE_URL`, `UC3_DATABASE_URL` |
| UC3 | `STATAGENT_STARTPAKET`, `STATAGENT_ABGABE` (siehe `uc3/README.md`) |
| UC4 und Online | `UC4_ADAPTER`, `UC4_KETTE` (welche Bereiche auf `/uc4` antworten), `UC4_MODELLWAHL`, `KIC_ONLINE_LESEND`, `KIC_ONLINE_FRAGEN` (Fragen online erlaubt), `KIC_ONLINE` (setzt nur das Prod-Compose) |
| Grenzen für Modellaufrufe | `LLM_TAGESBUDGET_AUFRUFE` (Aufrufe je Tag, online Pflicht), `RATENLIMIT_PRO_MINUTE` (Fragen je IP und Minute), `PLATTFORM_PROTOKOLL` (Ort des Modellprotokolls, dort wird gezählt) |
| Voice | `VAPI_API_KEY`, `VAPI_PUBLIC_KEY`, `VAPI_WEBHOOK_SECRET`, `VAPI_CUSTOM_LLM_KEY`, `VAPI_ASSISTANT_ID`, `PUBLIC_URL`; optional `VOICE_RATENLIMIT_PRO_MINUTE`, `VOICE_ANTWORT_TIMEOUT_S`, `PLATTFORM_VOICE_PROTOKOLL` |

### Modelle

Die Angaben stimmen mit `docs/models.md` überein. Das ist dort die Hauptquelle, mit Messungen.

- **Azure OpenAI `gpt-5.4-mini`** (Deployment `gpt-5-4-mini`, Modell des Veranstalters, Endpunkt in der EU) ist
  **Pflicht und Standard für alle UC3-Agenten**.
- **Mistral (EU)** ist der Zweitanbieter, zum Beispiel für den Wechsel vor der Jury. Das Projektbudget beträgt
  10 €. Der Testlauf in `docs/models.md` war ok.
- **Ollama** läuft lokal ohne Netz und ist ein Notnagel für den Offline-Betrieb.
- **Claude Opus 5.5** läuft über die CLI und ist nur ein Qualitätsmodus für UC1 und UC2 und für Vergleiche.
  **Nie in der UC3-Zählung.**
- **Embeddings:** `google/embeddinggemma-2`, lokal. Die Gewichte sind nicht im Repo (siehe Lizenzen).
- **Ohne Schlüssel** läuft alles mit `LLM_PROVIDER=mock`. Der UC3-Monatslauf braucht ohnehin kein Modell.
- **Online-Demo:** Dort läuft Azure `gpt-5.4-mini` mit zwei Grenzen: ein Ratenlimit je IP und ein Tagesbudget für
  Modellaufrufe, das auch bei gleichzeitigen Fragen nicht überschritten wird. Ohne Tagesbudget ruft die App online
  kein echtes Modell, sie lehnt den Aufruf vorher ab. Ist das Budget aufgebraucht, sagt die Seite das und bittet,
  am nächsten Tag wieder zu fragen.

## Grenzen und offene Punkte

- **Daten:** Es sind nur die synthetischen Daten des Veranstalters und öffentliche Quellen. Sie liegen nicht im
  Repo. Einzige Ausnahme: Die Rückfragen in `abgabe/rueckfragen/` nennen als Beispiel einige synthetische
  Kennungen (`VVH_ID`), damit die Fachabteilung den Fall findet. Personenbezogene Daten gibt es keine. An ein Modell
  gehen nie Einzeldaten, nur Schema, Aggregate und Prüfergebnisse.
- **UC1:** Der Lotse ersetzt keine Beratung. Er gibt keine Diagnose und keine Therapie- oder Medikamentenempfehlung;
  bei solchen Fragen verweist er an Ärztin, Arzt oder die Gesundheitsberatung 1450, im Notfall an 144. Eine
  Aussage ohne passendes Zitat aus der Quelle lässt er weg.
- **UC2:** Die Akteure spielt ein Sprachmodell. Das ist eine Simulation, keine echte Verhandlung. Die Antwort auf
  `/uc4` sagt das in einem eigenen Satz.
- **UC4:** Die drei Antworten kommen nacheinander. Mit Azure dauerte die ganze Frage am 05.11. gemessen 5 bis 7
  Sekunden; die Seite wartet höchstens drei Minuten und zeigt jede Antwort, sobald sie da ist. Fällt ein Bereich
  aus, nennt die Seite ihn als „fehlt“ und zeigt die anderen. Online kann UC2 statt echter Presse-Belege
  gekennzeichnete Beispielbelege zeigen, solange dort die Namensliste zur Maskierung von Personennamen fehlt.
- **Voice:** Server und Sprechknopf sind gebaut. Ein Anruf geht erst nach der Einrichtung (Tunnel, Vapi-Konto mit
  Zahlungsmittel, Schlüssel). Die Tunnel-Adresse wechselt bei jedem Start, danach muss der Assistent neu
  eingetragen werden (`docs/voice.md`). Vapi ist ein US-Dienst. Der Text-Weg ersetzt Voice vollständig.
- **UC3 Rückfragen:** Offene Fragen an die Fachabteilung stehen in `abgabe/rueckfragen/`. Für Berichtsmonate vor
  Juli hängt das Alter bei Geburtsmonat 13 von der Antwort auf Rückfrage R1 ab.

## Vorab Entstandenes

Das Voice-Konzept (Vapi Custom LLM, Webhook, Text-Fallback) folgt dem vorab entstandenen Projekt
`everlast-voice-interviewer` des Teams. **Übernommen sind nur Konzept und Schnittstellen. Der Code ist hier neu
geschrieben.** Das belegt eine Suche im Repo: Der Name steht nur in Plänen und Regeln, nicht im Code.
Die Liste aller übernommenen Teile mit Herkunft, Version und Rechtebeleg: `docs/abgabe/herkunft.md`.

## Lizenzen

Der eigene Code dieses Repos steht unter der MIT-Lizenz (`LICENSE`). Nach den Teilnahmebedingungen der
KI Challenge 2026 stehen die Ergebnisse (dieses Repository) neben dem Team auch dem Dachverband der
österreichischen Sozialversicherungsträger uneingeschränkt zur Verfügung. Ausgenommen von der MIT-Lizenz sind:

- die Daten des Veranstalters. Sie liegen nicht im Repo.
- die Gewichte fremder Modelle, etwa `google/embeddinggemma-2` unter den Gemma Terms of Use. Sie werden getrennt
  geladen und hier nicht verteilt.
- Logos und Marken Dritter: das Logo des Dachverbands und das Logo der Wirtschaftskammer Wien in
  `web/public/landing/logos/`. Sie gehören den beiden Organisationen und nennen auf der Startseite nur die
  Veranstalter. Quellen stehen in `docs/landing/logos-quellen.md`.

Die Umrisse der Bundesländer auf der Startseite (`web/public/landing/oesterreich-*`) stammen von Statistik Austria
(data.statistik.gv.at), bearbeitet von Flooh Perlot, Lizenz CC BY 4.0. Die Quelle steht auf der Seite.

Fremde Bibliotheken behalten ihre eigenen Lizenzen. Die Schriften Inter, Space Grotesk und JetBrains Mono kommen
über `@fontsource-variable/*` unter der OFL-1.1, `three` steht unter MIT. Die Messfunktion des Anti-Schablonen-Gates
(`web/tests/lib/slop-measure.js`) folgt dem impeccable-Katalog von Paul Bakaus und steht unter Apache-2.0
(Lizenztext `web/tests/lib/LICENSE-impeccable`). Einzelheiten: `docs/abgabe/herkunft.md`.

## Für Entwickler

Aufbau, Arbeitsteilung und Regeln für Änderungen: `docs/entwicklung.md`. Schnittstellen der Plattform:
`docs/prd/2026-11-05-e0-plattform-e1-uc3.md`.
