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
   (`voice.jsonl` neben `modellaufrufe.jsonl`) geht je Anruf genau eine Zeile: Hash der `call_id`, Dauer,
   Endgrund aus einer Liste bekannter Vapi-Endgründe (alles andere wird `sonstiges`). Kein Transkript, keine
   Antwort, keine Zusammenfassung. Ein zweiter Bericht zum selben Anruf schreibt keine weitere Zeile.

Die Aufnahme ist aus (`recordingEnabled: false` im Assistant). Vapi hält das Transkript des Anrufs nach eigenen
Regeln; was dort landet, ist die gesprochene Frage und die Antwort mit Aggregat und Beleg.

Ohne Tunnel (`PUBLIC_URL` leer) erreicht Vapi die FastAPI nicht. Dann gibt es nur den Text-Fallback: dieselbe
`antwort`-Funktion über das Chatfeld der UC (`text_antwort(antwort, frage, uc)`), ohne Daten an Vapi.

## Schutz und Grenzen

- `/chat/completions` verlangt `Authorization: Bearer` mit `VAPI_CUSTOM_LLM_KEY`, `/vapi/webhook` verlangt
  `x-vapi-secret` mit `VAPI_WEBHOOK_SECRET`. Beide Vergleiche laufen in konstanter Zeit. Fehlt die Variable,
  antwortet der Endpunkt 503 („Voice ist nicht eingerichtet.“, der Variablenname steht nur im Server-Log). Ein
  falscher oder fehlender Schlüssel gibt 401, beim Webhook bevor der Body gelesen wird. Nach zehn
  Fehlversuchen je IP in 60 Sekunden folgt 429.
- Gültige Aufrufe von `/chat/completions` sind je IP auf `VOICE_RATENLIMIT_PRO_MINUTE` (Standard 30) je Minute
  begrenzt, danach 429.
- Bodies über 256 KiB gibt es nicht: 413, geprüft an `Content-Length` und beim Lesen.
- `antwort` hat `VOICE_ANTWORT_TIMEOUT_S` Sekunden (Standard 20), sonst 504.
- Das Tagesbudget für Modellaufrufe (`LLM_TAGESBUDGET_AUFRUFE`) setzt `plattform.llm` in jedem Adapter durch,
  der es nutzt. Wirft `antwort` dabei `BudgetErschoepft`, antwortet der Router 429 mit lesbarer Meldung.
- Die Tunnel-Middleware (`TunnelFilter`) lässt über die Tunnel-Domain nur `/chat/completions` und
  `/vapi/webhook` durch, alles andere gibt dort 404. Lokal bleibt die ganze API offen.

## Einbinden

```python
from plattform.voice import TunnelFilter, erstelle_router

app.include_router(erstelle_router(antwort, uc="uc3"))  # uc optional, sonst metadata.uc oder „unbekannt“
app.add_middleware(TunnelFilter)
```

Der Assistant liegt als Code in `plattform/voice/assistant.py`. `uv run python -m plattform.voice sync --trocken`
druckt ihn ohne Schlüssel. Als Custom-LLM-URL trägt er die Basis `PUBLIC_URL` ein; Vapi hängt `/chat/completions`
selbst an.

`sync` überträgt `VAPI_CUSTOM_LLM_KEY` nicht. Diesen Schlüssel einmal von Hand in Vapi als Zugang für den
Custom LLM hinterlegen (gleicher Wert wie in `.env.local`), sonst bekommt jede Anfrage von Vapi 401.

## Demo (UC4 über den Router)

`sync` und `smoke` wirken nach außen und laufen nur mit Freigabe. Reihenfolge:

1. `uv run python -m plattform.voice serve --mock` startet die Voice-App für UC4 auf `127.0.0.1:8104`. Die Frage
   läuft durch die Kette uc3 → uc2 → uc1, gesprochen wird je UC ein Satz mit allen Belegen. Ohne `--mock`
   nimmt sie die echten Adapter.
2. `scripts/tunnel.sh 8104` öffnet einen cloudflared-Quick-Tunnel und druckt `PUBLIC_URL=…`.
3. `PUBLIC_URL` in `.env.local` eintragen.
4. `uv run python -m plattform.voice sync` schreibt den Assistant und druckt seine ID.
5. `VAPI_ASSISTANT_ID` in `.env.local` eintragen.
6. `uv run python -m plattform.voice smoke` stellt eine Textfrage über die Vapi-Chat-API. Gedruckt werden die
   Chat-ID und die ersten 200 Zeichen der Antwort. Gibt es keine Antwort des Assistants, endet der Befehl mit
   Exit 1.

## Umgebungsvariablen

| Variable | Zweck | Wer liest sie |
|---|---|---|
| `VAPI_API_KEY` | privater Schlüssel der Vapi-API | `sync`, `smoke` |
| `VAPI_PUBLIC_KEY` | öffentlicher Schlüssel für den VoiceKnopf | Browser (`NEXT_PUBLIC_VAPI_PUBLIC_KEY`) |
| `VAPI_CUSTOM_LLM_KEY` | Bearer-Schlüssel, den Vapi an `/chat/completions` schickt | UC-FastAPI |
| `VAPI_WEBHOOK_SECRET` | `x-vapi-secret` des Webhooks, `sync` trägt ihn im Assistant ein | UC-FastAPI, `sync` |
| `PUBLIC_URL` | öffentliche Adresse der UC-FastAPI über den Tunnel | `sync`, Tunnel-Middleware |
| `VAPI_ASSISTANT_ID` | Assistant für `sync` und `smoke`; leer legt `sync` einen neuen an | `sync`, `smoke` |
| `VOICE_RATENLIMIT_PRO_MINUTE` | optional: gültige Anfragen je IP und Minute (Standard 30) | UC-FastAPI |
| `VOICE_ANTWORT_TIMEOUT_S` | optional: Frist der `antwort`-Funktion in Sekunden (Standard 20) | UC-FastAPI |
| `PLATTFORM_VOICE_PROTOKOLL` | optional: Ziel der Anrufende-Zeilen | UC-FastAPI |

Werte stehen nur in `.env.local`, nie im Repo.
