# uc2 – HealthPolicy Simulator

Python-Paket für UC2 der KI Challenge 2026: Pressespiegel-Belege, Akteurs-Pool, Experte (Wirkungsmodell) und
Verhandlung. Plan: `docs/plan/uc2/2026-11-05-healthpolicy-simulator.md`, Epic #24.

```bash
cd uc2
uv sync                      # Kern ohne torch
uv sync --extra einbettung   # mit embeddinggemma-2 (sentence-transformers, torch)
uv run uc2 --help
uv run pytest
```

Daten liegen nie im Repo. Pfade über Umgebungsvariablen (Standard in Klammern):

| Variable | Inhalt |
|---|---|
| `UC2_PRESSE` | Pressespiegel-PDFs (`~/Projects/ki-challenge-2026/svbox/uc2/Presse`) |
| `UC2_DATEN` | Kalibrierdaten (`~/Projects/ki-challenge-2026/data/uc2`) |
| `UC2_ARBEIT` | Zwischenstände, Vektoren, Messberichte (`~/Projects/ki-challenge-2026/arbeit/uc2`) |
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
- Belege: Standard ist `--belege fixture` mit erfundenen Belegen aus
  `tests/fixtures/verhandlung/belege.json`. `--belege index` liest den echten Index und ist vor der
  Maskierung (#43) nur mit `mock` erlaubt; mit echtem Provider bricht der Lauf vorher ab.
- Szenario-Mock (`uc2.modelle.szenario`): Er antwortet aus dem Kontextblock des Prompts.
  `UC2_MOCK_KAPUTT=<akteur>:<runde>` liefert für genau diesen Zug kaputtes JSON.

## UC4-Adapter (#103)

`uc2.antwort.antwort(frage, kontext) -> UcAntwort` (Entry-Point `kic.uc_antwort: uc2`) beantwortet eine
Frage aus der Kette uc3 → uc2 → uc1, ohne PG:

- Fall per Stichwort aus `faelle/*.yaml` (sonst `wartezeiten`), der Experte rechnet dessen Paket.
- Zahlen aus `kontext` (etwa UC3) gehen samt Beleg in die Antwort und als `kontext_zahlen` ans Panel.
- Kurzverhandlung: Moderator, höchstens 4 Akteure, Runde 1 Position und Runde 2 Debatte, über
  `plattform.llm` (Zweck `uc2.panel`). Mit `LLM_PROVIDER=mock` deterministisch.
- Belege: `quelle=presse` je Akteur mit Medium im Text, sonst „Modellannahme“; Experte als
  `quelle=uc2.experte`, `ref=<paket>`. Belegquelle `FixtureQuelle`, unmaskiert nur mit mock.
- Den Text schreibt der Code. Zahlen ohne Eintrag in `zahlen` werden ersetzt, bleibt eine übrig, wirft der
  Adapter `FreieZahl`. Modellfehler werfen; der Router meldet UC2 dann als fehlend.
- `protokoll_id` ist `None`, weil der Kurzlauf nicht in PG schreibt.

```bash
LLM_PROVIDER=mock uv run python -c "from uc2.antwort import antwort; print(antwort('Wie entwickeln sich die Wartezeiten?', []).text)"
```
