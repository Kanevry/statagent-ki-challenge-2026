# Verwendete Modelle (UC3 StatAgent, Team OneShotAndy)

## Im Betrieb

| Teil | Modell | Wofür | Wo |
|---|---|---|---|
| Monatslauf, Prüfungen, Qualitätsberichte, Aggregations-Sheet, Ministeriums-Lieferung, Datenanfragen (`uc3 frage`, `uc3 antwort`), Klassifikationen (`uc3 klass`) | **keines** | Zahlen entstehen nur durch SQL und Python (`uv run uc3 lauf`, `berichte`, `sheet`); zwei Läufe liefern denselben Ergebnis-Hash | lokal, PostgreSQL 16 |
| Eigene Agenten (Koordinator, Datenmanagement, Klassifikation, Qualitätssicherung, Reporting) | **Azure AI Foundry `gpt-5-4-mini`** (Deployment des Veranstalters, Endpunkt West Europe) | Änderungsaufträge in Sprache verstehen und als Vorschlag formulieren (Regeländerung oder Code-Datei) | über `plattform.llm` (Schalter `LLM_PROVIDER`) |
| Austauschbar (Technische Regel 4) | Mistral (EU, Zweitanbieter), Ollama (offline, Notnagel) | gleiche Aufgaben, gleiche Schnittstelle | `LLM_PROVIDER=mistral` bzw. `ollama` |
| Tests, CI | `mock` (feste Antworten) | Agenten-Tests ohne Netz | `LLM_PROVIDER=mock` |

Ein Modell schlägt nur vor. Jede Änderung gilt erst, wenn eine Person sie mit Vor- und Nachnamen freigibt; das
Programm rechnet danach ohne Modell neu. An das Modell gehen nur Schema, Regeln, Aggregate und Prüfergebnisse,
keine Einzeldaten (das Lese-Werkzeug der Agenten verweigert Ergebnisse mit `PERSON_ID` oder `VVH_ID`).
Jeder Modellaufruf wird mit Anbieter, Modell, Zweck, Dauer und Tokens protokolliert, nie mit Inhalt.

## In der Entwicklung

Den Code hat das Team mit Claude Code (Anthropic, Claude Opus 5.5) geschrieben. Das Entwicklungswerkzeug setzt im
Betrieb keine Änderung um: Die drei Änderungsaufträge und die Live-Änderung laufen über die eigenen Agenten oben.
