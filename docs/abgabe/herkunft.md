# Herkunft und Rechte

Stand: 06.11.2026, `main` 14c86cc3. Diese Liste gehört zu Issue #91. Sie nennt jede Komponente, die nicht allein vom
Team neu geschrieben wurde, oder die das Repo nutzt. Jede Zeile hat einen Rechtebeleg.

**Ergebnis:** Für jede Zeile der Tabelle liegt ein Rechtebeleg vor, mit einer Ausnahme: Für die Formulartexte
(Zeile „Formulartexte zweier Anträge“) ist die Frage der Veröffentlichung offen. Geprüft sind Herkunft und Lizenz der Teile, die im
Repo liegen oder ausdrücklich übernommen wurden. **Nicht einzeln geprüft** sind die Lizenzen der übrigen Python- und
npm-Pakete aus den Lockfiles, und die Abgrenzung zum früheren eigenen Projekt beruht auf einer Namenssuche (Hinweise unter der
Tabelle).

Einordnung: **neu** (hier geschrieben), **vorab entstanden** (aus einem früheren Projekt übernommen), **Konzept**
(nur die Idee, kein Code), **extern** (fremdes Werk oder fremder Dienst).

| Komponente | Herkunft | Version oder Commit | Betroffene Dateien | Rechte- oder Lizenzbeleg | Einordnung |
|---|---|---|---|---|---|
| Eigener Code und eigene Texte | Team OneShotAndy | Git-Verlauf dieses Repos (`LICENSE` zuletzt geändert in 4b75b6c) | `shared/`, `uc1/`, `uc2/`, `uc3/`, `web/`, `deploy/`, `docs/` | MIT-Lizenz, `LICENSE` (Owner-Entscheid 05.11.2026, queue #8707). Die Teilnahmebedingungen geben dem Dachverband zusätzlich uneingeschränkte Nutzung (README, Abschnitt Lizenzen). | neu |
| Voice-Konzept aus einem früheren eigenen Projekt (ein Sprach-Interview mit Vapi) | früheres eigenes Projekt des Teams, nicht in diesem Repo | keine Version, **kein Code übernommen** | Konzept wirkt in `shared/py/plattform/voice/` und `docs/voice.md` (Vapi Custom LLM, Webhook, Tunnel) | Eine Suche nach dem Namen des früheren Projekts über das ganze Repo fand ihn nur in Regeln und Plänen. Im Quelltext (`shared/`, `uc*/`, `web/`, `scripts/`) kam er nicht vor. Seit dem 06.11.2026 steht der Name auch in Regeln und Plänen nicht mehr. `docs/voice.md` hält fest: Konzept vorab, Code neu. Regel in `CLAUDE.md` (Ausnahme früheres Voice-Projekt) und im PRD (`docs/prd/2026-11-05-e0-plattform-e1-uc3.md`, Zeilen 254 und 479). | Konzept |
| Schriften Inter, Space Grotesk, JetBrains Mono | npm-Pakete `@fontsource-variable/inter`, `/space-grotesk`, `/jetbrains-mono` | je 5.3.0 (`pnpm-lock.yaml`) | `shared/ui/src/tokens.css` (Zeilen 12 bis 14); Dateien kommen beim Installieren, nicht aus dem Repo | Lizenzfeld in den installierten Paketen: OFL-1.1 (SIL Open Font License). Die Schriften werden nicht im Repo mitgeliefert. | extern |
| Messregeln des Anti-Schablonen-Gates | impeccable-Katalog von Paul Bakaus, https://github.com/pbakaus/impeccable (Copyright 2025 Paul Bakaus) | Übernommen über eine Messfunktion mit Stand 25.09.2026; Upstream-Kopf an diesem Tag 9d715cc4f556 (gemessen per GitHub-API, der genaue Commit wurde damals nicht festgehalten). Im Repo seit unserem Commit 2b7081f | `web/tests/lib/slop-measure.js`, Lizenztext `web/tests/lib/LICENSE-impeccable` | Apache-2.0, SPDX-Kopf in der Datei, Lizenztext liegt daneben. Die Datei steht damit unter Apache-2.0, nicht unter MIT. | extern, angepasst |
| `three` (3D-Bibliothek) | npm-Paket `three` | 0.187.0 (`pnpm-lock.yaml`), Typen `@types/three` | steht noch in `web/package.json`, wird nicht mehr importiert; die Startseite zeichnet mit SVG und CSS | Lizenzfeld im installierten Paket: MIT | extern |
| Logo Dachverband (DVSV) | Website sozialversicherung.at | abgerufen 05.11.2026 | `web/public/landing/logos/dvsv-logo.png` | Marke des Dachverbands. Nennung der Veranstalter, keine Partnerschaftsbehauptung (`docs/landing/logos-quellen.md`). Von der MIT-Lizenz ausgenommen (README, Lizenzen). | extern |
| Logo Wirtschaftskammer Wien (WKO) | wko.at, Datei `logo.svg` | abgerufen 05.11.2026, Farben für hellen Grund angepasst | `web/public/landing/logos/wko-logo-hell.svg` | Marke der WKO. Nutzung wie oben (`docs/landing/logos-quellen.md`). Von der MIT-Lizenz ausgenommen. | extern |
| Modell `google/embeddinggemma-2` | Hugging Face | Revision `f9972ac22e696a105c482202646979e33e4b5a1e` (`shared/py/plattform/embeddings.py`, Zeile 64) | Gewichte **nicht im Repo**, Ladebefehl `python -m plattform.embeddings laden`; Code `shared/py/plattform/embeddings.py` | Gemma Terms of Use (https://ai.google.dev/gemma/terms), im Code und in `docs/models.md` genannt. Wer lädt, akzeptiert sie dort. | extern |
| Azure OpenAI (`gpt-5.4-mini`, Deployment `gpt-5-4-mini`) | Modell des Veranstalters | Version `gpt-5.4-mini-2026-03-17` (`docs/models.md`, Smoke) | Adapter `shared/py/plattform/llm/azure.py` | Vom Veranstalter bereitgestellt und genutzt, nicht verteilt. Es liegt kein Schlüssel im Repo. | extern (Dienst) |
| Mistral (EU) | Mistral AI, La Plateforme | `mistral-small-latest` und `mistral-large-latest` (`docs/models.md`) | Adapter `shared/py/plattform/llm/mistral.py` | Dienst, Zugang über Schlüssel in `.env.local`, genutzt, nicht verteilt. Kein Schlüssel im Repo. | extern (Dienst) |
| Vapi | Vapi (US-Dienst) | Assistant-Einstellung in `shared/py/plattform/voice/assistant.py` | `shared/py/plattform/voice/` | Dienst, genutzt, nicht verteilt. Datenfluss: `docs/voice.md`, README (Datenfluss Voice). | extern (Dienst) |
| `@vapi-ai/web` (Browser-SDK für den Sprechknopf) | npm-Paket `@vapi-ai/web` | 3.1.0 (`pnpm-lock.yaml`) | Abhängigkeit in `web/package.json`, geladen erst beim Klick in `web/lib/plattform/voice-lader.ts`; der Knopf `shared/ui/src/voice/` bekommt den Lader herein | Lizenzfeld im installierten Paket: MIT | extern |
| Claude Code CLI (Claude Opus 5.5) | Anthropic | Modell `claude-opus-5-5` (`docs/models.md`) | Adapter `shared/py/plattform/llm/claude.py` | Dienst im Abo des Teams, genutzt, nicht verteilt. Auch Entwicklungswerkzeug (`abgabe/modelle.md`). | extern (Dienst) |
| Zweite Prüfer in der Entwicklung: Fable 5.1 und Astra (Codex, `gpt-6-astra`) | Dienste, nur als Prüfer eingesetzt | Stand der Prüfung 05.11.2026 (`docs/abnahme/PROZESS.md`, Zeile 3) | kein Code im Repo; Ergebnis in `docs/abnahme/review-fable-2026-11-05.md` und `docs/abnahme/review-astra-2026-11-05.md` | Dienste, genutzt, nicht verteilt. Im Betrieb der Anwendung kommen sie nicht vor. | extern (Dienst) |
| Formulartexte zweier Anträge: Pflegegeld (PAL080) und Rehabilitations-, Kur- bzw. Erholungsaufenthalt | PDF-Formulare aus den Daten des Veranstalters zu UC1; Herausgeber laut Formular: PVA (PAL080) und Sozialversicherung (DVSV) | „PAL 080 (01. 2025)“ und „DVSV – KUR1 – R/8.1“ (Feld `formular.version` in den Dateien) | `uc1/formulare/pal080.felder.json`, `pal080.felder.roh.json`, `kur-reha.felder.json`, `kur-reha.felder.roh.json` | Die Dateien enthalten Feldnamen und Wortlaut der Formularfelder, mit `pdftotext` aus den PDFs gelesen. Die PDFs selbst liegen **nicht im Repo**. Die Rechte am Wortlaut liegen bei den Herausgebern; er fällt nicht unter die MIT-Lizenz. Ob der Wortlaut in einem öffentlichen Repo bleiben soll, ist offen. | extern |
| Daten des Veranstalters | KI Challenge 2026 (Startpaket, SV-Box) | Lieferungen 2024-08 bis 2026-07 | **nicht im Repo**; Pfad `../svbox/uc3` oder `STATAGENT_STARTPAKET` | Synthetische Daten des Veranstalters, bereitgestellt zur Teilnahme. Von der MIT-Lizenz ausgenommen (README, Lizenzen). Ergebnisse daraus (`abgabe/`) sind Zahlen und Berichte, keine Rohdaten. | extern |

## Hinweise

1. **Früheres eigenes Projekt:** `docs/plan/uc1/2026-11-05-prd-e2-uc1-ki-lotse.md` (Zeilen 48, 65 und 295) kennt eine spätere
   Owner-Freigabe, Browser-Code aus dem früheren Projekt zu übernehmen. Dieses Projekt hat keine Lizenzdatei („Alle Rechte
   vorbehalten“). Übernommen wurde kein solcher Code: Der Sprechknopf `VoiceKnopf` (`shared/ui/src/voice/`) ist
   hier neu geschrieben, er nutzt das Vapi-SDK `@vapi-ai/web` (MIT) direkt, und der Name des früheren Projekts kommt im Quelltext
   nicht vor. Es ist also nichts zu klären. Käme später Code aus dem früheren Projekt dazu, braucht diese Zeile vorher einen
   Eintrag mit Owner-Entscheid. Geprüft wurde per Namenssuche und
   Dateiliste, nicht mit einem Textvergleich beider Projekte.
2. **Bibliotheken:** Python- und npm-Pakete werden installiert, nicht ins Repo kopiert. Ihre Versionen stehen in
   `uv.lock` und `pnpm-lock.yaml`. Die Lizenzen der Pakete habe ich nicht einzeln geprüft. Gemessen sind nur
   `three` und die drei Schriften (Lizenzfeld im installierten Paket).
