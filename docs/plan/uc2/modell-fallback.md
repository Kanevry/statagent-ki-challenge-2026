# UC2: Modellfehler und Fallback, Testbericht

Stand 05.11.2026, Issue #47 (Nachschärfung AC1), Pen-Frame `NjP7Q` (U2-1a). Lane `web/`.

## Was die Oberfläche tut

Bricht eine Verhandlung ab, schreibt die Python-Seite das Ereignis `abbruch` (`daten: {grund, meldung}`, `runde` am
Ereignis) und setzt den Fallstatus `abgebrochen`. Der SSE-Strom endet mit `event: ende` und
`{status: "abgebrochen", letzte_seq}`. Die Seite `/uc2/panel?fall=<id>` zeigt dann:

- ein rotes Band mit dem Satz in Alltagssprache, dem Hinweis auf die fertigen Runden und dem technischen Grund klein darunter,
- die fertigen Runden unverändert darunter (Personas, Stand, Moderator, Experte, Verlauf),
- "Erneut versuchen" und je ein "Modell wechseln: …" für die anderen Modelle.

"Erneut" und der Modellwechsel starten einen neuen Fall bei Runde 1 (`POST /api/uc2/faelle` mit `provider`). Die
Schnittstelle kann einen Lauf nicht fortsetzen. Der abgebrochene Fall bleibt über seine Adresse lesbar.

## Zustände

| Zustand | Anzeige | Verhalten |
|---|---|---|
| Echter Lauf, Anbieter fällt aus (z. B. azure, `TimeoutError`) | "Das Modell azure hat nicht rechtzeitig geantwortet. Zeitüberschreitung nach 30 Sekunden." plus "Technischer Grund: TimeoutError" | "Erneut" nimmt das Modell aus dem Ereignis `start`, Wechsel zu claude und ollama möglich |
| Vorführmodus (Aufzeichnung `mock-abbruch`) | "Testbetrieb, aufgezeichneter Abbruch. Hier ist kein Modell ausgefallen, die Seite zeigt nur, wie ein Abbruch aussieht." | Es wird kein Anbieter genannt, der Provider der Aufzeichnung ist `mock` und erscheint nirgends roh |
| claude | Knopf "Modell wechseln: claude", immer wählbar | Start mit `provider: "claude"` |
| azure | Knopf "Modell wechseln: azure" (wenn der Lauf nicht schon über azure lief) | Start mit `provider: "azure"` |
| ollama nicht eingerichtet (`OLLAMA_MODEL` leer) | Knopf "Modell wechseln: ollama · lokal · Ersatz" gesperrt, darunter sichtbar: "Das lokale Modell ist hier nicht eingerichtet." | Kein Start. Der Server lehnt `provider: "ollama"` zusätzlich mit 422 ab |
| ollama eingerichtet (`OLLAMA_MODEL` gesetzt) | Knopf wählbar, Beschriftung "ollama · lokal · Ersatz" | Start mit `provider: "ollama"`. Lehnt die Python-API ihn mit 422 ab, steht "Das Panel nimmt ollama gerade nicht an. Wähle ein anderes Modell." Die Runden bleiben stehen |
| Neuer Versuch scheitert (403, 409, Netz) | Meldung unter den Knöpfen: "Ein neuer Versuch ist in der Online-Demo gesperrt." bzw. "Es läuft schon eine Verhandlung." bzw. "Keine Verbindung zum Server." | Band und Runden bleiben |

## Was geprüft wurde

Alle Läufe am 05.11.2026 gegen den aufgezeichneten Fall, ohne Sprachmodell.

- **vitest** (`pnpm test`): 19 Dateien, 139 Tests grün. Davon zum Abbruch und Fallback:
  - `components/uc2/panel.test.tsx`: Band im Vorführmodus und live, fertige Runden bleiben, Erneut und Modellwahl, ollama gesperrt mit Meldung und wählbar mit `OLLAMA_MODEL`, Fehlertypen als Sätze, kein "mock-fixture" und kein erfundener Anbieter.
  - `components/uc2/panel-lauf.test.tsx`: Modellwechsel startet einen neuen Fall mit dem gewählten Modell, "Erneut" nimmt das Modell aus `start`, 422 auf ollama zeigt eine klare Meldung und lässt die Runden stehen.
  - `components/uc2/zustand.test.ts`: `abbruch` setzt den Status und behält die Runden, `fehler` gibt es nicht, `ende` mit `abgebrochen` genügt.
  - `app/api/uc2/uc2-api.test.ts`: `mock-abbruch` endet mit `abbruch` und `ende {status: "abgebrochen", letzte_seq: 37}`, der Provider der Aufzeichnung ist `mock`, ollama ohne Einrichtung gibt 422, Fehlerkörper der API gehen nie nach außen.
- **Playwright** (`web/tests/uc2.spec.ts`, Desktop 1440×900 und Mobil 390×844): Test "Modellfehler" prüft das Band, die erhaltenen Runden, den gesperrten ollama-Knopf mit Meldung, measureSlop gleich 0, keine Gedankenstriche, kein horizontales Scrollen, und dass "Erneut" einen neuen Lauf öffnet.
- **measureSlop** auf `/uc2/panel?fall=mock-abbruch`: 0 in allen zwölf Schlüsseln, Desktop und Mobil.

## Vergleich mit Pen `NjP7Q`

Verglichen wurde der Export des Frames (nur lesend, PNG) mit `u2-1a-oben-desktop.png` und `u2-1a-mobil.png`.

| Element im Frame | Umsetzung |
|---|---|
| Kopfzeile mit Titel "Runde 3 von 3" | Titel "Die Verhandlung ist in Runde 3 abgebrochen", Status "Abgebrochen" rechts |
| Schritte 1 Fall, 2 Panel verhandelt, 3 Antwort | vorhanden, Schritt 2 aktiv |
| Rotes Band mit Abbruch-Text | vorhanden, mit Satz in Alltagssprache, Hinweis auf fertige Runden und kleinem technischem Grund |
| "Erneut versuchen" | vorhanden (grüne Hauptaktion) |
| "Modell wechseln: ollama (lokal)" | je ein Knopf für die anderen Modelle, ollama als "ollama · lokal · Ersatz", gesperrt mit sichtbarer Meldung, wenn nicht eingerichtet |
| Positionen der Runden 1 und 2 bleiben | sechs Personas mit Haltung, "bewegt" oder "fest", Herkunft-Chip, Stand nach Runde 2 |
| Moderator rechts, Experte mit Annahmen und gelben Hinweisen | vorhanden |
| Gesprächsverlauf | vorhanden, nach Runden getrennt, je Beitrag mit Haltung und Herkunft |

Abweichungen vom Frame, mit Absicht: "Erneut versuchen" ist grün statt rot, weil je Screen nur eine Hauptaktion gilt. Ein Stand nach Runde 2 mit Zählung steht über den Personas. Die Zeile "Läuft · Runde 2" des Frames heißt hier
"Abgebrochen".

## Nicht geprüft

- Ein echter Azure-Abbruch gegen die Python-API: Sie lief bei den Tests nicht. Der Ablauf ist gegen den Ereignisvertrag (#44) und die Fixture geprüft, nicht gegen einen echten Ausfall.
- Ein erfolgreicher Fallback über ollama: Auf dem Rechner war kein lokaler Dienst eingerichtet. Geprüft ist nur, dass der Knopf ohne Einrichtung gesperrt bleibt und mit Einrichtung wählbar ist, und dass die Meldung bei einer Ablehnung der API (422) klar ist.
- Die Python-API nimmt `provider: "ollama"` noch nicht an (Folge-MR). Bis dahin endet ein Start damit in der 422-Meldung.
