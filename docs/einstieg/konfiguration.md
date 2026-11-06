# Konfiguration und Modelle, Langfassung

Diese Seite ist die Langfassung des Abschnitts „Konfiguration“ aus dem README.
Sie nennt alle Schlüssel der Einstellungen und welches Modell wofür läuft.

Zurück zum [README](../../README.md#konfiguration).

Alle Einstellungen kommen aus Umgebungsvariablen oder aus `.env.local` an der Repo-Wurzel. Vorlage mit den wichtigsten
Schlüsselnamen und Erklärungen: `.env.example`. **Werte stehen nie im Repo.** Diese Seite nennt nur Namen.

| Gruppe | Schlüssel |
|---|---|
| Modell-Schalter | `LLM_PROVIDER` (`azure`, `mistral`, `ollama`, `claude`, `mock`) |
| Azure (Standard) | `AZURE_OPENAI_BASE_URL`, `AZURE_OPENAI_MODEL`, `AZURE_API_KEY` |
| Mistral | `MISTRAL_API_KEY`, `MISTRAL_BASE_URL`, `MISTRAL_MODEL_CHAT`, `MISTRAL_MODEL_FAST` |
| Ollama | `OLLAMA_BASE_URL`, `OLLAMA_MODEL` |
| Claude | `CLAUDE_MODEL` (läuft über die Claude-Code-CLI im Abo, kein API-Schlüssel) |
| Datenbanken | `UC1_DATABASE_URL`, `UC2_DATABASE_URL`, `UC3_DATABASE_URL` |
| UC1 | `UC1_DATA_DIR` (Ordner mit dem Datenpaket des Veranstalters) |
| UC2 | `KIC_ABLAGE` (Ablage außerhalb des Repos, Standard `~/Projects/ki-challenge-2026`; `uv run uc2` liest den Wert nur aus der Shell; weitere Pfade in `uc2/README.md`) |
| UC3 | `STATAGENT_STARTPAKET`, `STATAGENT_ABGABE` (siehe `uc3/README.md`) |
| UC4 und Online | `UC4_ADAPTER`, `UC4_KETTE` (welche Bereiche auf `/uc4` antworten), `UC4_MODELLWAHL`, `KIC_ONLINE_LESEND`, `KIC_ONLINE_FRAGEN` (Fragen online erlaubt), `KIC_ONLINE` (setzt nur das Prod-Compose) |
| Grenzen für Modellaufrufe | `LLM_TAGESBUDGET_AUFRUFE` (Aufrufe je Tag, online Pflicht), `RATENLIMIT_PRO_MINUTE` (Fragen je IP und Minute), `PLATTFORM_PROTOKOLL` (Ort des Modellprotokolls, dort wird gezählt) |
| Voice | `VAPI_API_KEY`, `VAPI_PUBLIC_KEY`, `VAPI_WEBHOOK_SECRET`, `VAPI_CUSTOM_LLM_KEY`, `VAPI_ASSISTANT_ID`, `PUBLIC_URL`; optional `VOICE_RATENLIMIT_PRO_MINUTE`, `VOICE_ANTWORT_TIMEOUT_S`, `PLATTFORM_VOICE_PROTOKOLL` |
| Weitere Schalter der Web-App | `UC2_API_URL` (Adresse der UC2-Schnittstelle, ohne Angabe `http://localhost:8102`), `KIC_ONLINE_UC1` (`1` zeigt auf der lesenden Online-Demo das Fragefeld von `/uc1`, die Schnittstelle bleibt dort gesperrt; online nicht gesetzt), `KIC_VORFUEHRUNG` (`1` öffnet `/uc3/auftrag` und `/api/uc3/auftrag` für die Vorführ-Instanz, sonst 404 oder gesperrt; wirkt nicht zusammen mit `KIC_ONLINE_LESEND=1`) |

## Modelle

Die Angaben stimmen mit `docs/models.md` überein. Das ist dort die Hauptquelle, mit Messungen.

- **Azure OpenAI `gpt-5.4-mini`** (Deployment `gpt-5-4-mini`, Modell des Veranstalters, Endpunkt in der EU) ist
  **Pflicht und Standard für alle UC3-Agenten**.
- **Mistral (EU)** ist der Zweitanbieter, zum Beispiel für den Wechsel vor der Jury. Das Projektbudget beträgt
  10 €. Der Testlauf in `docs/models.md` war ok.
- **Ollama** ist als Notnagel für den Offline-Betrieb vorgesehen. Die Anbindung im Modell-Schalter ist da, gelaufen
  ist es bisher nicht.
- **Claude Opus 5.5** läuft über die CLI und ist nur ein Qualitätsmodus für UC1 und UC2 und für Vergleiche.
  **Nie in der UC3-Zählung.**
- **Embeddings:** `google/embeddinggemma-2`, lokal. Die Gewichte sind nicht im Repo (siehe [Lizenzen](grenzen-herkunft-lizenzen.md#lizenzen)).
- **Ohne Schlüssel** läuft alles mit `LLM_PROVIDER=mock`. Der UC3-Monatslauf braucht ohnehin kein Modell.
- **Online-Demo:** Dort läuft Azure `gpt-5.4-mini` mit zwei Grenzen: ein Ratenlimit je IP und ein Tagesbudget für
  Modellaufrufe, das auch bei gleichzeitigen Fragen nicht überschritten wird. Ohne Tagesbudget ruft die App online
  kein echtes Modell, sie lehnt den Aufruf vorher ab. Ist das Budget aufgebraucht, sagt die Seite das und bittet,
  am nächsten Tag wieder zu fragen.
