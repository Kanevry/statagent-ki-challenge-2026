# Modellangabe

Alle Modellaufrufe laufen über den Modell-Schalter `plattform.llm` (Vertrag M, `shared/py/plattform/llm/`).
Zahlen rechnet nie ein Modell, sondern der Code ohne Sprachmodell. An das Modell gehen keine Einzeldaten.

## Provider

| Provider | Einsatz | Modell (Standard) | Zugang |
|---|---|---|---|
| `azure` | Standard, Pflicht für die UC3-Agenten | `AZURE_OPENAI_MODEL` (gpt-5-4-mini) | OpenAI-kompatibler Endpunkt `/openai/v1` (we-16), `AZURE_API_KEY` |
| `mistral` | EU-Zweitanbieter, Live-Austausch | `fast`: `MISTRAL_MODEL_FAST` (mistral-small-latest), `chat`: `MISTRAL_MODEL_CHAT` (mistral-large-latest) | `MISTRAL_BASE_URL`, `MISTRAL_API_KEY` |
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
