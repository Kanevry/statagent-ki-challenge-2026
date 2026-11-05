# Probe-Protokoll (Vorlage)

Gehört zu GitLab #90, Epic #26. Wird am Fr 06.11.2026 ab 06:00 ausgefüllt.

- Probe: Fr 06.11.2026 06:00–07:00 (Europe/Vienna).
- **Feature-Stopp und Freeze: Fr 06.11.2026 07:00 (Europe/Vienna).** Nach dem Freeze ändert niemand Code, Folien oder Demo.
- Ältere Dokumente nennen teils 05:00. Es gilt 07:00 laut Owner.
- Uhrzeiten nur aus der Uhr eintragen: `TZ=Europe/Vienna date`. Nie schätzen, nie runden.
- **Bedingung für die Web-Oberfläche:** Die Seite `/uc3` liegt in MR !51. Nur wenn sie bis zum Freeze auf main ist, wird die Web-Oberfläche gezeigt (Stufe 1). Sonst ist der CLI-Weg (Stufe 2) der Standard. Der Stand wird um 06:45 geprüft und in der Tabelle unten eingetragen.
- **Live heißt auf dem Rechner von Bernhard** (Modell Azure). Die öffentliche Demo läuft im Testmodus und wird so angesagt.
- **Üben ohne Folgen:** Den Änderungsauftrag aus D2 nur bis `vorschlag zeigen <id>` üben, dann `ablehnen <id>`. Nie `freigabe` üben (siehe Demo-Drehbuch, D2).
- Das Soll kommt aus der Szenenfolge (10 Szenen, Präsentation 0:00–5:05) und aus `docs/praesentation/demo-drehbuch.md` (Demo 5:05–9:30). Danach folgen Live-Änderung und Datenanfragen der Jury bis etwa 15:00. Sie gehören nicht zu diesem Durchlauf.

## 1. Durchlauf

| Feld | Wert |
|---|---|
| Datum | |
| Start (Uhr) | |
| Ende (Uhr) | |
| Gesamtdauer Ist | |
| Soll | Präsentation 5:05, mit Demo 9:30 |
| Präsentation ≤ 5:05 | ja / nein |
| Gesamtdauer mit Demo ≤ 9:30 | ja / nein |
| D1 Monat | 2025-10 / 2025-03 |
| `/uc3` (MR !51) beim Freeze auf main | ja / nein (bei nein ist Stufe 2 der Standard) |
| Stufe der Demo | 1 Web-UI (nur bei `/uc3` auf main) / 2 CLI / 3 Video |
| Stand (Commit) | |
| D4 gezeigt (Entscheid 06:45) | ja / nein (bei nein endet die Demo um 9:00) |
| D2 Live-Änderung (Entscheid 06:45) | B2 Ersatztag Geburtsmonat 13 / Ersatz B1, B3 oder B4. Auftrag 1 ist abgegeben und wird nur als Rückblick gezeigt |
| D3 freie Fragen | nein, nur die acht geprüften (ja erst, wenn der Folge-MR von bb auf main ist) |
| Zahlen in den Szenen gegen `abgabe/` abgeglichen | ja / nein |

### Abschnittszeiten

Ist-Dauer ist das Ende minus der Start des Abschnitts. Beide Uhrzeiten eintragen.

| Nr | Abschnitt | Soll-Fenster | Soll-Dauer | Start Ist | Ende Ist | Dauer Ist |
|---|---|---|---|---|---|---|
| 1 | Szene 1 Gleichung „1 + 2 + 3 = 4“ | 0:00–0:15 | 0:15 | | | |
| 2 | Szene 2 Drei Menschen, drei Fragen | 0:15–0:45 | 0:30 | | | |
| 3 | Szene 3 Eine falsche Zahl kostet Vertrauen | 0:45–1:45 | 1:00 | | | |
| 4 | Szene 4 Aus Aufgabe 3 wurde der Kern für alle drei | 1:45–2:20 | 0:35 | | | |
| 5 | Szene 5 Wir rechnen den offiziellen Bericht nach | 2:20–2:50 | 0:30 | | | |
| 6 | Szene 6 Acht Arten von Fehlern gefunden. Nichts gelöscht | 2:50–3:25 | 0:35 | | | |
| 7 | Szene 7 Im Januar 2025 wechselt die Branchenliste | 3:25–3:50 | 0:25 | | | |
| 8 | Szene 8 Das Alter bei Geburtsmonat 13 nachgerechnet | 3:50–4:25 | 0:35 | | | |
| 9 | Szene 9 Eine Frage, drei Antworten, jede mit Beleg | 4:25–4:55 | 0:30 | | | |
| 10 | Szene 10 Jede Zahl nachrechenbar. Jede Änderung mit Namen | 4:55–5:05 | 0:10 | | | |
| D1 | Demo D1 Lauf und Qualitätsbericht | 5:05–6:15 | 1:10 | | | |
| D2 | Demo D2 Rückblick Auftrag 1, neue Änderung B2 mit Freigabe | 6:15–7:45 | 1:30 | | | |
| D3 | Demo D3 Datenanfragen | 7:45–9:00 | 1:15 | | | |
| D4 | Demo D4 Gemeinsamer Einstieg, Wien-Frage in `/uc4` (Entscheid 06:45) | 9:00–9:30 | 0:30 | | | |

### Pflichtschritte

Alle fünf müssen im Durchlauf vorkommen. Die Spalte „vom Lead bestätigt“ füllt der Lead aus, nicht Bernhard.

| Nr | Pflichtschritt | Wo im Ablauf | Uhr (Ist) | Vom Lead bestätigt (Name, Uhr) |
|---|---|---|---|---|
| 1 | Lösung | Szenen 4 und 5 | | |
| 2 | Fehlerbeispiel | Szenen 3 und 6 und D1 | | |
| 3 | Eine begründete Annahme | Szene 8 | | |
| 4 | Live-Änderung mit Vorher/Nachher | D2 | | |
| 5 | Eine Datenfrage | D3 | | |

Ergebnis: ___ von 5 bestätigt (Ziel 5 von 5).

### Auffälligkeiten

| Nr | Was fiel auf | Abschnitt | Maßnahme | Erledigt vor 07:00 |
|---|---|---|---|---|
| | | | | |

## 2. Backup-Video

Der Metadatenbericht steht in `docs/praesentation/backup-video.md`, Abschnitt „Metadatenbericht“. Er enthält Datei, Dauer, Größe, SHA-256, Auflösung, Abspieltest offline und Sichtprüfung.

| Feld | Wert |
|---|---|
| Metadatenbericht ausgefüllt | ja / nein |
| Abspieltest offline bestanden | ja / nein |
| Sichtprüfung bestanden (0 sichtbare Secrets) | ja / nein |
| Geprüft von, Uhr | |

## 3. Ausfallprobe

Das Live-Modell wird absichtlich nicht verfügbar gemacht. Gemessen werden zwei Wege getrennt:

- Weg (a): Wechsel auf die Aufzeichnung. Das ist der Nachweis für #90. Ziel: höchstens 30 Sekunden.
- Weg (b): Stufe 2 im Terminal mit `LLM_PROVIDER=mock`. Damit laufen nur D1 und D3 (D3 über SQL), denn sie brauchen kein Modell. Für D2 gibt es keinen Mock-Weg, weil die Fixture `agent.koordinator.json` fehlt (`shared/py/plattform/llm/mock.py`, Zeile 56). D2 geht ohne Modell auf die Aufzeichnung, das ist Weg (a). Weg (b) wird zusätzlich protokolliert und ersetzt Weg (a) nicht.

| Feld | Wert |
|---|---|
| Datum | |
| Auslöser (so wurde das Modell unverfügbar gemacht) | |
| Uhr beim Auslöser | |
| Uhr beim ersten sichtbaren Bild der Aufzeichnung | |
| Dauer des Wechsels in Sekunden | |
| Dauer ≤ 30 s | ja / nein |
| Weg (b) Stufe 2 mit `LLM_PROVIDER=mock` für D1 und D3: Dauer in Sekunden und Ergebnis | |
| Aufzeichnung gekennzeichnet („Das ist eine Aufzeichnung von heute früh“ gesagt) | ja / nein |
| Kennzeichnung im Bild sichtbar | ja / nein |
| Wiederholt nach Fehlschlag | ja / nein, Dauer |
| Vom Lead bestätigt (Name, Uhr) | |

## 4. Freeze

| Feld | Wert |
|---|---|
| Freeze-Zeit (Soll) | Fr 06.11.2026 07:00 Europe/Vienna |
| Freeze bestätigt (Uhr aus `TZ=Europe/Vienna date`) | |
| Stand (Commit) beim Freeze | |
| Offene Punkte | |
