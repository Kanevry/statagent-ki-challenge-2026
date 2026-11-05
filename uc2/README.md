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
| `POST /faelle` | `{fall, frage?, provider?, belege?}` → 202 `{fall_id, status}`. Fall-ID nur aus `faelle/` (unbekannt 404, Pfad 422), Frage ≤ 500 Zeichen ohne Steuerzeichen (sonst 422). |
| `GET /faelle` | Liste der letzten Fälle mit Status (60-s-Regel) und Zeiten |
| `GET /faelle/{fall_id}/ereignisse?seq=n` | SSE ab `seq > n`: je Ereignis `id: <seq>`, `event: <art>`, `data: <json>`; `Last-Event-ID` gewinnt über `?seq`. Nachladen alle 0,5 s, Schluss mit `event: ende`, sobald der Fall `fertig` oder `abgebrochen` ist. |
| `GET /faelle/{fall_id}` | Bericht als JSON (Matrix, Einordnung, Auswahl, Runden) |

- `POST /faelle` startet `uv run uc2 verhandlung … --melde-fall-id [--frage-stdin]` als Unterprozess mit
  fester argv und ohne Shell. Die Frage geht über stdin. Die Fall-ID liest die API aus der ersten
  stdout-Zeile `fall_id=<n>`. Der Unterprozess ist der einzige Schreiber, die API liest nur.
- Höchstens ein laufender Fall je API-Prozess: Ein zweiter Start ergibt 409. Das ersetzt ein Rate-Limit.
- Standard-Provider ist `mock`. `claude` und `azure` laufen nur mit `UC2_API_ECHTE_MODELLE=1`, sonst gibt es 403.
  `belege: index` geht vor #43 nur mit `mock`.
- Belege gehen online nur als Zitatfelder hinaus: `beleg_id`, `medium`, `datum`/`monat`, `titel`, `pdf_seite`
  und `zitat`, Titel und Zitat höchstens 300 Zeichen (`uc2.api.belegfilter`). Den Volltext `text` liefert die
  API nur mit `KIC_VOLLTEXT_ONLINE=1` (Standard aus, lokal in der Demo an).
- Unabhängige Prüfung eines Laufs: `uv run python tests/pruefe_lauf.py --fall <fall_id> [--db …] [--json]`
  (Exit 0 grün, 1 Verstoß, 2 Betriebsfehler).
