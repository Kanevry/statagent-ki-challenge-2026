# Herkunft und Rechte

Stand: 05.11.2026, `main` d50990d plus E0-Züge 7 und 8 (Tagesbudget, Sprechknopf, Voice-Folgepunkte). Diese Liste gehört zu Issue #91. Sie nennt jede Komponente, die nicht allein vom
Team neu geschrieben wurde, oder die das Repo nutzt. Jede Zeile hat einen Rechtebeleg.

**Ergebnis: 0 ungeklärte Rechtepositionen** für Teile, die im Repo liegen. Zwei Hinweise unter der Tabelle.

Einordnung: **neu** (hier geschrieben), **vorab entstanden** (aus einem früheren Projekt übernommen), **Konzept**
(nur die Idee, kein Code), **extern** (fremdes Werk oder fremder Dienst).

| Komponente | Herkunft | Version oder Commit | Betroffene Dateien | Rechte- oder Lizenzbeleg | Einordnung |
|---|---|---|---|---|---|
| Eigener Code und eigene Texte | Team OneShotAndy | Git-Verlauf dieses Repos (`LICENSE` zuletzt geändert in 4b75b6c) | `shared/`, `uc1/`, `uc2/`, `uc3/`, `web/`, `deploy/`, `docs/` | MIT-Lizenz, `LICENSE`. Die Teilnahmebedingungen geben dem Dachverband zusätzlich uneingeschränkte Nutzung (README, Abschnitt Lizenzen). | neu |
| `everlast-voice-interviewer` | frühere Arbeit des Teams, nicht in diesem Repo | keine Version, **kein Code übernommen** | Konzept wirkt in `shared/py/plattform/voice/` und `docs/voice.md` (Vapi Custom LLM, Webhook, Tunnel) | Die Suche `git grep -n -i everlast` findet den Namen nur in `CLAUDE.md`, `docs/prd/` und `docs/plan/`, also in Regeln und Plänen. Im Quelltext (`shared/`, `uc*/`, `web/`, `scripts/`) kommt er nicht vor. `docs/voice.md` hält fest: Konzept vorab, Code neu. Regel in `CLAUDE.md` (Ausnahme everlast) und im PRD (`docs/prd/2026-11-05-e0-plattform-e1-uc3.md`, Zeilen 254 und 479). | Konzept |
| Schriften Inter, Space Grotesk, JetBrains Mono | npm-Pakete `@fontsource-variable/inter`, `/space-grotesk`, `/jetbrains-mono` | je 5.3.0 (`pnpm-lock.yaml`) | `shared/ui/src/tokens.css` (Zeilen 12 bis 14); Dateien kommen beim Installieren, nicht aus dem Repo | Lizenzfeld in den installierten Paketen: OFL-1.1 (SIL Open Font License). Die Schriften werden nicht im Repo mitgeliefert. | extern |
| `three` (3D-Bibliothek für die Startseite) | npm-Paket `three` | 0.187.0 (`pnpm-lock.yaml`), Typen `@types/three` | genutzt in `web/landing/szene/motor/motor.ts` | Lizenzfeld im installierten Paket: MIT | extern |
| Logo Dachverband (DVSV) | Website sozialversicherung.at | abgerufen 05.11.2026 | `web/public/landing/logos/dvsv-logo.png` | Marke des Dachverbands. Nennung der Veranstalter, keine Partnerschaftsbehauptung (`docs/landing/logos-quellen.md`). Von der MIT-Lizenz ausgenommen (README, Lizenzen). | extern |
| Logo Wirtschaftskammer Wien (WKO) | wko.at, Datei `logo.svg` | abgerufen 05.11.2026, Farben für hellen Grund angepasst | `web/public/landing/logos/wko-logo-hell.svg` | Marke der WKO. Nutzung wie oben (`docs/landing/logos-quellen.md`). Von der MIT-Lizenz ausgenommen. | extern |
| Umrisse der Bundesländer | Statistik Austria (data.statistik.gv.at, Gemeindegrenzen 2021), bearbeitet von Flooh Perlot | Stand der Quelle 2021 | `web/public/landing/oesterreich-punkte.bin`, `oesterreich-meta.json`; Erzeugung `web/landing/werkzeug/karte-erzeugen.mjs` | CC BY 4.0, Quelle in der Datei `oesterreich-meta.json` und auf der Seite (`web/landing/texte/inhalt.ts`, Zeile 281) genannt | extern |
| Modell `google/embeddinggemma-2` | Hugging Face | Revision `f9972ac22e696a105c482202646979e33e4b5a1e` (`shared/py/plattform/embeddings.py`, Zeile 64) | Gewichte **nicht im Repo**, Ladebefehl `python -m plattform.embeddings laden`; Code `shared/py/plattform/embeddings.py` | Gemma Terms of Use (https://ai.google.dev/gemma/terms), im Code und in `docs/models.md` genannt. Wer lädt, akzeptiert sie dort. | extern |
| Azure OpenAI (`gpt-5.4-mini`, Deployment `gpt-5-4-mini`) | Modell des Veranstalters | Version `gpt-5.4-mini-2026-03-17` (`docs/models.md`, Smoke) | Adapter `shared/py/plattform/llm/azure.py` | Vom Veranstalter bereitgestellt und genutzt, nicht verteilt. Es liegt kein Schlüssel im Repo. | extern (Dienst) |
| Mistral (EU) | Mistral AI, La Plateforme | `mistral-small-latest` und `mistral-large-latest` (`docs/models.md`) | Adapter `shared/py/plattform/llm/mistral.py` | Dienst, Zugang über Schlüssel in `.env.local`, genutzt, nicht verteilt. Kein Schlüssel im Repo. | extern (Dienst) |
| Vapi | Vapi (US-Dienst) | Assistant-Einstellung in `shared/py/plattform/voice/assistant.py` | `shared/py/plattform/voice/` | Dienst, genutzt, nicht verteilt. Datenfluss: `docs/voice.md`, README (Datenfluss Voice). | extern (Dienst) |
| `@vapi-ai/web` (Browser-SDK für den Sprechknopf) | npm-Paket `@vapi-ai/web` | 3.1.0 (`pnpm-lock.yaml`) | genutzt in `shared/ui/src/voice/`, geladen erst beim Klick | Lizenzfeld im installierten Paket: MIT | extern |
| Claude Code CLI (Claude Opus 5.5) | Anthropic | Modell `claude-opus-5-5` (`docs/models.md`) | Adapter `shared/py/plattform/llm/claude.py` | Dienst im Abo des Teams, genutzt, nicht verteilt. Auch Entwicklungswerkzeug (`abgabe/modelle.md`). | extern (Dienst) |
| Daten des Veranstalters | KI Challenge 2026 (Startpaket, SV-Box) | Lieferungen 2024-08 bis 2026-07 | **nicht im Repo**; Pfad `../svbox/uc3` oder `STATAGENT_STARTPAKET` | Synthetische Daten des Veranstalters, bereitgestellt zur Teilnahme. Von der MIT-Lizenz ausgenommen (README, Lizenzen). Ergebnisse daraus (`abgabe/`) sind Zahlen und Berichte, keine Rohdaten. | extern |

## Hinweise

1. **everlast:** `docs/plan/uc1/2026-11-05-prd-e2-uc1-ki-lotse.md` (Zeilen 48, 65 und 295) kennt eine spätere
   Owner-Freigabe, Browser-Code aus everlast zu übernehmen. Das Projekt hat keine Lizenzdatei („Alle Rechte
   vorbehalten“). Übernommen wurde kein solcher Code: Der Sprechknopf `VoiceKnopf` (`shared/ui/src/voice/`) ist
   hier neu geschrieben, er nutzt das Vapi-SDK `@vapi-ai/web` (MIT) direkt, und der Name everlast kommt im Quelltext
   nicht vor. Es ist also nichts zu klären. Käme später Code aus everlast dazu, braucht diese Zeile vorher einen
   Eintrag mit Owner-Entscheid. Geprüft wurde per Namenssuche und
   Dateiliste, nicht mit einem Textvergleich beider Projekte.
2. **Bibliotheken:** Python- und npm-Pakete werden installiert, nicht ins Repo kopiert. Ihre Versionen stehen in
   `uv.lock` und `pnpm-lock.yaml`. Die Lizenzen der Pakete habe ich nicht einzeln geprüft. Gemessen sind nur
   `three` und die drei Schriften (Lizenzfeld im installierten Paket).
