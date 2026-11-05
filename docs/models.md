# Modellangabe

Alle Modellaufrufe laufen über den Modell-Schalter `plattform.llm` (Vertrag M, `shared/py/plattform/llm/`).
Zahlen rechnet nie ein Modell, sondern der Code ohne Sprachmodell. An das Modell gehen keine Einzeldaten.

## Provider

| Provider | Einsatz | Modell (Standard) | Zugang |
|---|---|---|---|
| `azure` | Standard, Pflicht für die UC3-Agenten | `AZURE_OPENAI_MODEL` (gpt-5-4-mini) | OpenAI-kompatibler Endpunkt `/openai/v1` (we-16), `AZURE_API_KEY` |
| `mistral` | EU-Zweitanbieter, Live-Austausch | `fast`: `MISTRAL_MODEL_FAST` (mistral-small-latest), `chat`: `MISTRAL_MODEL_CHAT` (mistral-large-latest; gemessen 05.11. 16:2x in der Modellliste neben `mistral-large-4`, beide antworten) | `MISTRAL_BASE_URL`, `MISTRAL_API_KEY` |
| `ollama` | Offline-Notnagel (lokaler Rechner) | `OLLAMA_MODEL` (qwen3:8b) | `OLLAMA_BASE_URL` (http://localhost:11434/v1) |
| `claude` | Nur UC1/UC2-Qualitätsmodus und Vergleiche, nie UC3 | `CLAUDE_MODEL` (claude-opus-5-5) | Claude-Code-CLI im Abo, ohne `ANTHROPIC_API_KEY` |
| `mock` | Tests, CI, Jury ohne Netz | Fixtures `shared/py/plattform/fixtures/<zweck>.json` | keiner |

## Auswahl und Fallback

- Vorrang: Argument `provider` > Umgebung `LLM_PROVIDER` > Vorzug des Zwecks in `shared/py/plattform/zwecke.toml`.
  `LLM_PROVIDER=mock` stellt alles auf mock.
- Fallback-Kette je Zweck (Standard azure → mistral → ollama) bei Netz-, 5xx-, Timeout-Fehlern und HTTP 429
  (gedrosselter Endpunkt), außerdem wenn der Schlüssel einer späteren Stufe fehlt. Fehlt der Schlüssel des
  gewählten Providers (Stufe 1), ist das ein `KonfigFehler`, kein stiller Wechsel. Ein explizites `modell` gilt
  nur für Stufe 1. Die Stufe steht als `fallback_stufe` (1 = erster Provider) in Antwort und Protokoll;
  `aktives_modell()["zuletzt"]` nennt, wer laut Protokoll zuletzt tatsächlich geantwortet hat.
- UC3-Zwecke (`qs.einstufung`, `agent.koordinator`, `frage.sql`) erlauben claude nicht.
- Jeder Aufruf schreibt genau eine Protokollzeile (`var/protokoll/modellaufrufe.jsonl` oder
  `PLATTFORM_PROTOKOLL`): Provider, Modell, Version, Zweck, Prompt-Hash, Dauer, Tokens, Fallback-Stufe,
  Aufwand, Fehler. Nie den Inhalt; bei Fehlern nur Typ und (Schema) Prüfregel mit Ort.

## Prüfen

```bash
uv run python -m plattform.llm status          # provider · modell
uv run python -m plattform.llm status --json
uv run python -m plattform.llm smoke           # azure, mistral, claude; hängt das Ergebnis unten an
```

## Smoke-Läufe

Gemessen mit `uv run python -m plattform.llm smoke` (eine kurze Anfrage je Provider, ohne Fallback).

### Smoke 2026-11-05T13:22:33+01:00

| Zeit | Provider | Modell | Version | Dauer | Ergebnis |
|---|---|---|---|---|---|
| 2026-11-05T13:22:33+01:00 | azure | gpt-5-4-mini | gpt-5.4-mini-2026-03-17 | 0.9 s | ok ('bereit') |
| 2026-11-05T13:22:33+01:00 | mistral | - | - | 0.2 s | ProviderFehler: alle Stufen gescheitert (mistral): mistral: RateLimitError |
| 2026-11-05T13:22:33+01:00 | claude | claude-opus-5-5 | claude-opus-5-5 | 17.8 s | ok ('bereit') |

## Embeddings

Einziges Embedding-Modell der Plattform: `google/embeddinggemma-2` über `plattform.embeddings` (lokal,
sentence-transformers als Extra `plattform[embeddings]`, nicht in CI), Revision fest im Code. Ohne pgvector
speichern die UCs `float4[]` und rechnen Cosinus in SQL oder numpy. Prototyp mit 200 Texten; hochskalieren
(UC1, UC2) erst danach. Der Apple M4 Pro wird nicht gemessen (Regel: schwere Läufe nur auf dem Apple M5 Max
oder in CI); auf dem M5 Max misst der Bench auch `cpu` als Näherung für Rechner ohne Grafikbeschleunigung.

Nutzungsbedingungen: Für die Gewichte von embeddinggemma-2 gelten die Gemma Terms of Use
(https://ai.google.dev/gemma/terms). Die Gewichte liegen nicht im Repo und werden nicht mit ihm verteilt.
`uv run python -m plattform.embeddings laden` holt sie aus Hugging Face in den lokalen Cache; wer lädt,
akzeptiert die Bedingungen dort. Ohne diesen Schritt lädt `einbetten` nichts aus dem Netz, sondern bricht
mit `ModellFehlt` ab.

| Umgebung | Standard | Regel |
|---|---|---|
| `EMBEDDINGS_STAPEL` | 16 | Texte je Vorwärtslauf, 1 bis 256; `bench --stapel` überschreibt für den Lauf |
| `EMBEDDINGS_MAX_TOKEN` | 2048 | Token je Text, 1 bis 8192; längere Texte schneidet das Modell ab |
| `EMBEDDINGS_GERAET` | `cpu` | `cpu`, `cuda` oder `mps`; `mps` nur mit `PYTORCH_MPS_HIGH_WATERMARK_RATIO` > 0, sonst Fehler; fehlt `PYTORCH_MPS_LOW_WATERMARK_RATIO`, gilt die obere Grenze auch als untere |
| `EMBEDDINGS_DOWNLOAD` | leer | `1`: fehlende Revision beim Laden aus Hugging Face holen (wie `laden`) |

Die Texte gehen in Scheiben zu höchstens 256 ins Modell, danach wird der Speicher von `mps` bzw. `cuda`
geleert; `entladen()` gibt das Modell frei. Der Bench misst je Gerät eine Zeile mit kurzen Sätzen und eine
mit einem langen Text über `EMBEDDINGS_MAX_TOKEN` Token, jeweils mit Stapel und Speicher (cpu: RSS-Spitze; mps: Belegung des Treibers nach dem Lauf, torch misst dort keine Spitze).

#### Bench 2026-11-05T14:11:20+01:00

| Zeit | Host | Modell | Revision | Gerät | Ladezeit | Dimension | n | Dauer | Texte/s |
|---|---|---|---|---|---|---|---|---|---|
| 2026-11-05T14:11:20+01:00 | Apple M5 Max | google/embeddinggemma-2 | `f9972ac22e69` | mps | 5.3 s | 768 | 200 | 4.62 s | 43 |

#### Bench 2026-11-05T14:47:52+01:00

| Zeit | Host | Modell | Revision | Gerät | Eingabe | Stapel | Max. Token | Ladezeit | Dimension | n | Dauer | Texte/s | Speicher |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 2026-11-05T14:47:52+01:00 | Apple M5 Max | google/embeddinggemma-2 | `f9972ac22e69` | cpu | kurze Sätze | 16 | 2048 | 0.9 s | 768 | 1000 | 9.08 s | 110 | 2238 MiB (RSS-Spitze) |
| 2026-11-05T14:47:52+01:00 | Apple M5 Max | google/embeddinggemma-2 | `f9972ac22e69` | cpu | langer Text (8533 Wörter, abgeschnitten) | 16 | 2048 | 0.9 s | 768 | 1 | 2.23 s | 0.4 | 2325 MiB (RSS-Spitze) |
| 2026-11-05T14:47:52+01:00 | Apple M5 Max | google/embeddinggemma-2 | `f9972ac22e69` | mps | kurze Sätze | 16 | 2048 | 1.2 s | 768 | 1000 | 5.07 s | 197 | 2063 MiB (mps-Treiber nach dem Lauf) |
| 2026-11-05T14:47:52+01:00 | Apple M5 Max | google/embeddinggemma-2 | `f9972ac22e69` | mps | langer Text (8533 Wörter, abgeschnitten) | 16 | 2048 | 1.2 s | 768 | 1 | 0.60 s | 1.7 | 2128 MiB (mps-Treiber nach dem Lauf) |

Gemessen auf dem Apple M5 Max (Kopf 068d98e plus mps-Untergrenze), PYTORCH_MPS_HIGH_WATERMARK_RATIO=0.7. Hochgerechnet brauchen 14.244 kurze Texte auf cpu rund 2,2 Minuten.

### Smoke 2026-11-05T16:17:39+01:00

| Zeit | Provider | Modell | Version | Dauer | Ergebnis |
|---|---|---|---|---|---|
| 2026-11-05T16:17:39+01:00 | azure | gpt-5-4-mini | gpt-5.4-mini-2026-03-17 | 0.9 s | ok ('bereit') |
| 2026-11-05T16:17:39+01:00 | mistral | mistral-small-latest | mistral-small-latest | 1.4 s | ok ('bereit') |
| 2026-11-05T16:17:39+01:00 | claude | claude-opus-5-5 | claude-opus-5-5 | 12.7 s | ok ('bereit') |
