# uc2: HealthPolicy Simulator

Python-Paket für UC2 der KI Challenge 2026: Pressespiegel-Belege, Akteurs-Pool, Experte (Wirkungsmodell) und
Verhandlung. Plan: `docs/plan/uc2/2026-11-05-healthpolicy-simulator.md`, Epic #24.

```bash
cd uc2
uv sync                      # Kern ohne torch
uv sync --extra einbettung   # mit embeddinggemma-2 (sentence-transformers, torch)
uv run uc2 --help
uv run pytest
```

Daten liegen nie im Repo. Pfade über Umgebungsvariablen; ohne sie gilt die Ablage `KIC_ABLAGE` (Standard in Klammern, relativ dazu):

| Variable | Inhalt |
|---|---|
| `UC2_PRESSE` | Pressespiegel-PDFs (`$KIC_ABLAGE/svbox/uc2/Presse`) |
| `UC2_DATEN` | Kalibrierdaten (`$KIC_ABLAGE/data/uc2`) |
| `UC2_ARBEIT` | Zwischenstände, Vektoren, Messberichte (`$KIC_ABLAGE/arbeit/uc2`) |
| `PGHOST`, `PGPORT`, `PGUSER`, `PGPASSWORD`, `UC2_DB` | PG (localhost, 5433, statistik, statistik, `healthpolicy`) |

Teilmodule hängen ihre Befehle in `uc2.cli` über `register(subparsers)` ein.

## Verhandlung (#44)

```bash
uv run uc2 verhandlung --fall wartezeiten                     # Provider aus LLM_PROVIDER, sonst modellrollen.yaml
LLM_PROVIDER=mock uv run uc2 verhandlung --fall wartezeiten   # deterministisch, ohne Netz
uv run uc2 verhandlung --fall wartezeiten --provider claude --belege fixture --max-akteure 2 --max-runden 2
```

- Fälle kommen nur aus `uc2/faelle/<id>.yaml`; die CLI nimmt die ID, nie einen Pfad.
- Ablauf: Der Moderator setzt den Auftrag (≤ 6 Themen, 5 feste Kriterien, Regeln) und wählt ≤ 6 von 14
  Akteuren mit Begründung für jeden. Danach folgen die Runden 1 Position, 2 Debatte, 3 Verhandlung und
  bis zu 2 Kompromissrunden. Nach Runde 3 endet der Lauf, sobald eine Runde keine Positionsänderung bringt.
- Jeder Zug wird gegen `zug.schema.json` und im Code geprüft. Es gibt die Ereignisse `zahl_ohne_beleg`,
  `beleg_ungueltig`, `zitat`, `zahl_widerspruch` und `ungueltige_ausgabe`.
- Zahlen: Deutsche Schreibweise wird ganz gelesen („12.000 Stellen“ ist zwölftausend, „1.234,5 Mio“ ist
  1234,5); Jahreszahlen 2000 bis 2040 entfallen. Lauf und `tests/pruefe_lauf.py` lesen gleich, je mit eigenem
  Code. Eine Zahl mit Quelle `experte` muss einem Ergebnis des Rechenmodells gleichen (Kennzahlen mit Spanne,
  Wirkung und Mehrkosten je Maßnahme, Jahrespfad), sonst `zahl_widerspruch`. Ziel, Zieljahr, Annahmen und
  Maßnahmenumfang sind Eingaben und zählen nicht. Eine Zahl mit einer Beleg-ID als Quelle muss im Text dieses
  Belegs stehen, sonst `zahl_ohne_beleg` mit Grund „Zahl steht nicht im Beleg“.
- Bricht ein Lauf ab, trägt das Ereignis `abbruch` nur den Fehlertyp (`grund`) und einen festen Satz
  (`meldung`). Den Fehlertext schreibt der Lauf ins Server-Log.
- Geschrieben werden `uc2.fall`, `uc2.teilnahme`, `uc2.ereignis` (mit `seq` je Fall) und `uc2.position`
  (DDL `sql/002_verhandlung.sql`, wendet die CLI idempotent an). Matrix und Einordnung rechnet der Code.
- Belege: `--belege index` holt je Akteur die 8 besten maskierten Belege aus dem Index
  (`uc2.belege.suche.belege_fuer_akteur`, mit Institutionsfaktor; ohne Vektoren oder Modell Volltext).
  `--belege fixture` nimmt erfundene Belege aus `tests/fixtures/verhandlung/belege.json`.
- Ohne Angabe gilt `index`, wenn `uc2.abschnitt` Zeilen hat und die Namensliste geladen ist, sonst `fixture`
  mit Hinweis auf stderr. Geladen heißt: `UC2_NAMENSLISTE` zeigt auf eine vorhandene, nicht leere Datei
  außerhalb des Repos. Ein ausdrückliches `--belege` gewinnt immer.
- Echte Provider (`claude`, `azure`) bekommen Index-Belege nur mit geladener Namensliste; ohne sie maskieren
  nur Muster, und der Lauf bricht vorher ab. Liste erzeugen:
  `uv run uc2 namen sammeln --aus-index --autoren <datei> --ausgabe <pfad außerhalb des Repos>`.
- Das Modell sieht `text_modell` (maskiert, Zitate bleiben) in einem markierten Block; die Prüfung `zitat`
  vergleicht dagegen. Das Ereignis `belege` speichert je Beleg ID, Medium, Datum, Monat, Titel, `zitat`
  (höchstens 300 Zeichen), `pdf_seite` und die Rangteile, aber keinen Text.
- Online-Schutz (#137, `docs/plan/uc2/online-schutz.md`): Jeder Modelltext (Zug, Moderator-Notiz, Auftrag,
  Auswahl) und die Frage gehen vor dem Schreiben durch `uc2.belege.namen.maskiere_modelltext`; Namen werden
  zur Rolle. Ohne Namensliste bricht ein Lauf mit echtem Provider vor der Anlage ab, mock schützt mit Mustern.
  Eine wörtliche Übernahme ab 8 Wörtern aus einem Beleg wird vor dem Speichern zu „[Zitat]“, das Ereignis
  `zitat` bleibt als Hinweis. Eine Frage mit Kennung, Geburtsdatum oder E-Mail-Adresse wird abgelehnt.
- Szenario-Mock (`uc2.modelle.szenario`): Er antwortet aus dem Kontextblock des Prompts.
  `UC2_MOCK_KAPUTT=<akteur>:<runde>` liefert für genau diesen Zug kaputtes JSON.

## API (#44)

```bash
uv run uvicorn uc2.api:app --port 8102     # aus uc2/, kein --reload im Betrieb
curl -s -X POST localhost:8102/faelle -H 'content-type: application/json' -d '{"fall":"wartezeiten"}'
curl -sN 'localhost:8102/faelle/<fall_id>/ereignisse?seq=0'
```

| Route | Antwort |
|---|---|
| `POST /faelle` | `{fall, frage?, provider?, belege?}` → 202 `{fall_id, status}`. Fall-ID nur aus `faelle/` (unbekannt 404, Pfad 422), Frage ≤ 500 Zeichen ohne Steuerzeichen, Kennungen, Geburtsdatum oder E-Mail-Adresse (sonst 422 mit festem Satz); Namen darin werden maskiert. |
| `GET /faelle` | Liste der letzten Fälle mit Status (60-s-Regel) und Zeiten |
| `GET /faelle/{fall_id}/ereignisse?seq=n` | SSE ab `seq > n`: je Ereignis `id: <seq>`, `event: <art>`, `data: <json>`; `Last-Event-ID` gewinnt über `?seq`. Nachladen alle 0,5 s, Schluss mit `event: ende`, sobald der Fall `fertig` oder `abgebrochen` ist. |
| `GET /faelle/{fall_id}` | Bericht als JSON (Matrix, Einordnung, Auswahl, Runden) |

- `POST /faelle` startet `uv run uc2 verhandlung … --melde-fall-id [--frage-stdin]` als Unterprozess mit
  fester argv und ohne Shell. Die Frage geht über stdin. Die Fall-ID liest die API aus der ersten
  stdout-Zeile `fall_id=<n>`. Der Unterprozess ist der einzige Schreiber, die API liest nur.
- Höchstens ein laufender Fall je API-Prozess: Ein zweiter Start ergibt 409. Dazu höchstens ein Start je
  Client-IP und Minute, sonst 429. Hinter einem Proxy gilt das Limit für alle zusammen.
- Standard-Provider ist `mock`. `claude` und `azure` laufen nur mit `UC2_API_ECHTE_MODELLE=1`, sonst gibt es 403.
  Mit `KIC_ONLINE=1` braucht ein echter Provider zusätzlich ein gültiges `LLM_TAGESBUDGET_AUFRUFE`, sonst
  gibt es 503. Auch der Lauf selbst bricht dann in `plattform.llm.complete` ab, bevor ein Modell gerufen wird.
- Fehler gehen nur als feste, einfache Sätze hinaus, ohne Env-Namen, Pfade oder Fehlertexte.
  `belege: index` geht vor #43 nur mit `mock`.
- Belege gehen online nur als Zitatfelder hinaus: `beleg_id`, `medium`, `datum`/`monat`, `titel`, `pdf_seite`
  und `zitat`, Titel und Zitat höchstens 300 Zeichen (`uc2.api.belegfilter`). Den Volltext `text` liefert die
  API nur mit `KIC_VOLLTEXT_ONLINE=1` (Standard aus, lokal in der Demo an).
- Unabhängige Prüfung eines Laufs: `uv run python tests/pruefe_lauf.py --fall <fall_id> [--db …] [--json]`
  (Exit 0 grün, 1 Verstoß, 2 Betriebsfehler).

## UC4-Adapter (#103)

`uc2.antwort.antwort(frage, kontext) -> UcAntwort` (Entry-Point `kic.uc_antwort: uc2`) liefert in der Kette
uc3 → uc2 → uc1 die Abwägung der Akteure mit Beleg, ohne in PG zu schreiben:

- **Stichwortregel** (`waehle_fall`): Ein Fall aus `faelle/*.yaml` passt, wenn sein Stichwort in der Frage
  steht. Stichwort ist die Fall-ID ohne die letzten zwei Buchstaben (`wartezeiten` → `wartezeit`).
- **Frage mit Fall** (Wartezeiten): Der Experte rechnet das Paket des Falls; Text und `zahlen` nennen das
  Rechenmodell (Beleg `quelle=uc2.experte`, `ref=<paket>`).
- **Allgemeine Frage** (kein Fall, etwa Beschäftigte in Wien): kein Rechenmodell, keine Paketzahlen. Der
  Moderator bekommt nur die Ausgangslage aus dem Kontext (`uc2.antwort.allgemein`).
- Kurzverhandlung in beiden Fällen über `plattform.llm` (Zweck `uc2.panel`). Standard für UC4 (die Web-Route
  bricht nach 60 s ab): Moderator mit Auftrag, höchstens 3 Akteure (Auswahl per Code nach Belegzahl und
  Themenbezug), eine Positionsrunde mit parallelen Zügen, Notiz der Moderation nur bei einem Fall. Das sind
  höchstens 5 Modellaufrufe (ohne Wiederholungen). Allgemeine Fragen kommen ohne Auftragsaufruf aus (feste Themen Versorgung, Personal, Finanzierung): gemessen mit azure 4,1 s statt 38,5 s. `frist_s` (Standard 25 s ab Aufruf): Ist sie um, folgt
  keine weitere Runde und keine Notiz. `runden=2`, `max_akteure=4` geben die Debatte. Jeder Aufruf bekommt
  eine Sprachregel (Alltagssprache, Fachbegriffe nur mit Erklärung, `kurzlauf.ALLTAGSREGEL`). Mit
  `LLM_PROVIDER=mock` deterministisch (`KurzMock`); der Text sagt dann „Testbetrieb ohne KI“.
- Zahlen aus `kontext` (UC3) gehen mit ihrem Beleg unverändert in `zahlen` und `belege`.
- Belege: `IndexQuelle` mit Maskierung, wenn `UC2_NAMENSLISTE` geladen ist und `uc2.abschnitt` Zeilen hat,
  sonst `FixtureQuelle`. Je zitiertem Artikel ein Beleg `quelle="presse: <Medium>"` (Fixture:
  `"beispielbeleg (erfunden): <Medium>"`), `monat`, `ref=<Beleg-ID>`. Ohne Beleg steht im Text
  „Modellannahme“. Echte Provider nur mit maskierter Quelle (`pruefe_freigabe`).
- Den Text schreibt der Code: Ausgangszahl mit Herkunft zum Vorlesen („laut Beschäftigtenstatistik, März
  2025, endgültig“; Tabelle, Lieferung und SQL nur im Beleg), wer dafür und wer dagegen ist, wo man sich einig
  ist (ohne Prognose). Den Schluss für den Einzelnen schreibt UC1.
- Zahlen im Text (`uc2.antwort.textzahlen`): Jede Zifferngruppe muss mit Wert, Vorzeichen und Einheit zu
  einem Eintrag in `zahlen` passen (ohne Einheit: ein Wort der Bezeichnung in der Nähe). Ausgenommen sind nur
  Jahresangaben ohne Mengeneinheit („bis 2030“, „März 2025“). Alles andere wird an seiner Position durch
  „(Zahl ohne Beleg entfernt)“ ersetzt; bleibt eine übrig, wirft der Adapter `FreieZahl`.
- Modellfehler werfen; der Router meldet UC2 dann als fehlend. `BudgetErschoepft` geht unverändert durch,
  der Router meldet den Grund `BudgetErschoepft` (Hinweis aus #100).
- `modell` nennt das antwortende Modell, bei mock `mock`. `protokoll_id` ist `None`.

```bash
LLM_PROVIDER=mock uv run python -c "from uc2.antwort import antwort; print(antwort('Wie entwickeln sich die Wartezeiten?', []).text)"
# Router über Entry-Points (an der Wurzel; uc3 braucht `uv sync --all-packages` und UC3_DATABASE_URL):
LLM_PROVIDER=mock uv run python -m plattform.router frage --json -- "Wie viele Menschen arbeiten im März 2025 in Wien?"
```

`--mock` am Router nimmt dessen eigene Mock-Adapter (`plattform.router.mock_adapter`), nicht diesen Adapter.
