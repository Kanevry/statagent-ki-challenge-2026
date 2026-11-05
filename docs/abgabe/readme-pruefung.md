# README-Prüfung (Issue #91)

Stand: 05.11.2026, `main` d50990d plus E0-Züge 7 und 8. Geprüft wurde das README am Repo, nicht aus dem Gedächtnis.

## 1. Pflichtabschnitte: 7 von 7

| Nr. | Pflichtabschnitt | Link im README | Wo der Beleg liegt |
|---|---|---|---|
| 1 | Lösung und Ansatz | [README.md#lösung-und-ansatz](../../README.md#lösung-und-ansatz) | Stand-Tabelle gegen `uc3/`, `abgabe/`, `shared/py/plattform/` und `web/app/uc4/` gemessen. Datenfluss Voice gegen `docs/voice.md` und `shared/py/plattform/voice/assistant.py` (Zeilen 54 bis 57). |
| 2 | Ausführung | [README.md#ausführung](../../README.md#ausführung) | Befehle aus `uc3/README.md`. Nachweis des Jury-Wegs in Issue #66 und Merge Request !56 (`docs/abnahme/66.md`), hier nicht wiederholt. |
| 3 | Abhängigkeiten und Voraussetzungen | [README.md#abhängigkeiten-und-voraussetzungen](../../README.md#abhängigkeiten-und-voraussetzungen) | Versionen aus `.python-version`, `pyproject.toml`, `package.json`, `shared/py/pyproject.toml`, `uc3/pyproject.toml`. |
| 4 | Konfiguration | [README.md#konfiguration](../../README.md#konfiguration) | Schlüsselnamen gegen `.env.example` verglichen. Das README nennt keine Werte. |
| 5 | Grenzen und offene Punkte | [README.md#grenzen-und-offene-punkte](../../README.md#grenzen-und-offene-punkte) | Je Punkt ein Beleg im Repo: `uc1/`, `uc2/src/`, `shared/py/plattform/router.py`, `docs/voice.md`, Issue #100, `abgabe/rueckfragen/`. |
| 6 | Vorab Entstandenes | [README.md#vorab-entstandenes](../../README.md#vorab-entstandenes) | `docs/abgabe/herkunft.md` und die Suche `git grep -n -i everlast`. |
| 7 | Lizenzen | [README.md#lizenzen](../../README.md#lizenzen) | `LICENSE`, `docs/landing/logos-quellen.md`, `docs/abgabe/herkunft.md`. |

Ergebnis: **7/7 vorhanden und ausgefüllt.**

### Ausführung

Der Start- und Beispiellauf ist in einer frischen Umgebung in Issue #66 und Merge Request !56 nachgewiesen. Dieses
Dokument führt ihn nicht erneut aus. Der Befund 66-6 (`lauf --alle` auf frischer Datenbank) steht im Abnahmeprotokoll
und im README unter Grenzen.

## 2. Modellangaben gegen `docs/models.md`

| Aussage im README | Fundstelle in `docs/models.md` | Ergebnis |
|---|---|---|
| Azure `gpt-5.4-mini`, Deployment `gpt-5-4-mini`, Pflicht und Standard für UC3 | Tabelle Provider, Zeile `azure`; Smoke-Tabelle (Version `gpt-5.4-mini-2026-03-17`) | gleich |
| Mistral (EU) als Zweitanbieter, seit 16:04 frei | Tabelle Provider, Zeile `mistral`; Smoke 16:17 ok | gleich |
| Mistral Projektbudget 10 € | nicht in `docs/models.md`. Quelle: Issue #54 und PRD Zeile 99. | Ergänzung, kein Widerspruch |
| Ollama lokal, Offline-Notnagel | Tabelle Provider, Zeile `ollama` | gleich |
| Claude Opus 5.5 über die CLI, nur UC1 und UC2 und Vergleiche, nie UC3 | Zeile `claude` (`claude-opus-5-5`); Abschnitt Auswahl: UC3-Zwecke erlauben claude nicht | gleich |
| Embeddings `google/embeddinggemma-2`, lokal, Gewichte nicht im Repo | Abschnitt Embeddings | gleich |
| Ohne Schlüssel `LLM_PROVIDER=mock` | Zeile `mock` | gleich |
| Tagesbudget mit Ratenlimit online (#100), ohne Budget online kein echtes Modell | Abschnitt „Tagesbudget und Ratenlimit“ (Zug 7) | gleich |

Ergebnis: **0 Widersprüche** zu `docs/models.md`. Eine Ergänzung mit Quelle (Mistral-Budget). Auch `abgabe/modelle.md` sagt
dasselbe (Azure Standard, Mistral und Ollama austauschbar, Claude nur im Entwicklungswerkzeug).

## 3. Weitere Prüfungen

- Keine Gedankenstriche im README: Suche nach den Zeichen ergab 0 Treffer.
- Keine Werte, Hostnamen oder IP-Adressen im README. Die Demo-Adresse steht schon in `deploy/README.md`.
- Der Satz „uc3/README.md folgt“ ist entfernt, das README verweist auf die vorhandene Datei.
- uv-Version: README sagt 0.12 (gemessen mit 0.12.12). `uc3/README.md` sagt „0.9 oder neuer“. Beide Angaben passen
  nicht zusammen. `pyproject.toml` legt keine Mindestversion fest. Die Datei `uc3/README.md` gehört der UC3-Lane und
  wurde hier nicht geändert.

## 4. Nicht geprüft

- Es wurde nichts ausgeführt (kein Build, kein Docker, keine Tests). Die Läufe stehen in #66 und !56.
- Ob der Befund 66-6 auf `main` behoben ist, wurde nicht gemessen.
- Lizenzen einzelner Python- und npm-Pakete (siehe `docs/abgabe/herkunft.md`, Hinweis 2).
