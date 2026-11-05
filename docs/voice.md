# Voice

Sprachzugang zu den Use Cases über Vapi (Vertrag V im PRD, Issue #61). Das Konzept stammt aus einem vorab
entstandenen Projekt des Teams, der Code in `shared/py/plattform/voice/` ist hier neu geschrieben.

## Datenfluss Voice

1. Der Browser verbindet sich mit Vapi. Vapi ist ein US-Dienst. Es erhält das Audio der Frage, transkribiert es
   und schickt das Transkript an die UC-FastAPI (`POST /chat/completions`, OpenAI-kompatibel, „Custom LLM“).
2. Die UC beantwortet die Frage mit ihrer eigenen `antwort`-Funktion. Die Zahlen rechnet der Code aus der
   Datenbank, kein Sprachmodell. Vapi bekommt nur Aggregate, jeweils mit gesprochenem Beleg
   („Beleg: Quelle Lieferung“). Einzeldaten verlassen den Rechner nicht, SQL wird nicht gesprochen.
3. Vapi spricht die Antwort. Die Belege legt der Router je Anruf (`call_id`) im Speicher ab, die Oberfläche holt
   sie über `sitzungs_belege(call_id)`.
4. Am Ende des Anrufs schickt Vapi einen `end-of-call-report` an `POST /vapi/webhook`. Ins Protokoll
   (`voice.jsonl` neben `modellaufrufe.jsonl`) geht genau eine Zeile: Hash der `call_id`, Dauer, Endgrund. Kein
   Transkript, keine Antwort, keine Zusammenfassung.

Die Aufnahme ist aus (`recordingEnabled: false` im Assistant). Vapi hält das Transkript des Anrufs nach eigenen
Regeln; was dort landet, ist die gesprochene Frage und die Antwort mit Aggregat und Beleg.

Ohne Tunnel (`PUBLIC_URL` leer) erreicht Vapi die FastAPI nicht. Dann gibt es nur den Text-Fallback: dieselbe
`antwort`-Funktion über das Chatfeld der UC (`text_antwort(antwort, frage, uc)`), ohne Daten an Vapi.

## Schutz

- `/chat/completions` (und Fallback `/chat/completions/<token>`) verlangt `Authorization: Bearer` mit
  `VAPI_CUSTOM_LLM_KEY`. `/vapi/webhook` verlangt `x-vapi-secret` mit `VAPI_WEBHOOK_SECRET`. Beide Vergleiche
  laufen in konstanter Zeit. Fehlt die Variable, antwortet der Endpunkt 503; ein falscher oder fehlender
  Schlüssel gibt 401, beim Webhook bevor der Body gelesen wird. Nach zehn Fehlversuchen je IP in 60 Sekunden
  folgt 429.
- Die Tunnel-Middleware (`TunnelFilter`) lässt über die Tunnel-Domain nur `/chat/completions*` und
  `/vapi/webhook` durch, alles andere gibt dort 404. Lokal bleibt die ganze API offen.

## Einbinden

```python
from plattform.voice import TunnelFilter, erstelle_router

app.include_router(erstelle_router(antwort, uc="uc3"))
app.add_middleware(TunnelFilter)
```

Der Assistant liegt als Code in `plattform/voice/assistant.py`. `uv run python -m plattform.voice sync --trocken`
druckt ihn ohne Schlüssel. Ohne `--trocken` schreibt `sync` ihn über die Vapi-API (Außenwirkung, nur mit Freigabe).

## Umgebungsvariablen

| Variable | Zweck | Wer liest sie |
|---|---|---|
| `VAPI_API_KEY` | privater Schlüssel der Vapi-API | nur `python -m plattform.voice sync` |
| `VAPI_PUBLIC_KEY` | öffentlicher Schlüssel für den VoiceKnopf | Browser (`NEXT_PUBLIC_VAPI_PUBLIC_KEY`) |
| `VAPI_CUSTOM_LLM_KEY` | Bearer-Schlüssel, den Vapi an `/chat/completions` schickt | UC-FastAPI |
| `VAPI_WEBHOOK_SECRET` | `x-vapi-secret` des Webhooks, `sync` trägt ihn im Assistant ein | UC-FastAPI, `sync` |
| `PUBLIC_URL` | öffentliche Adresse der UC-FastAPI über den Tunnel | `sync`, Tunnel-Middleware |
| `VAPI_ASSISTANT_ID` | optional: Assistant, den `sync` aktualisiert; leer legt einen neuen an | `sync` |
| `PLATTFORM_VOICE_PROTOKOLL` | optional: Ziel der Anrufende-Zeilen | UC-FastAPI |

Werte stehen nur in `.env.local`, nie im Repo.
