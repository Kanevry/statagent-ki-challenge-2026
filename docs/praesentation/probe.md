# Probe-Protokoll (Vorlage)

Gehört zu GitLab #90, Epic #26. Wird am Fr 06.11.2026 ab 06:00 ausgefüllt.

- Probe: Fr 06.11.2026 06:00–07:00 (Europe/Vienna).
- **Feature-Stopp und Freeze: Fr 06.11.2026 07:00 (Europe/Vienna).** Nach dem Freeze ändert niemand Code, Szenen oder Demo.
- Ältere Dokumente nennen teils 05:00. Es gilt 07:00 laut Owner.
- Uhrzeiten nur aus der Uhr eintragen: `TZ=Europe/Vienna date`. Nie schätzen, nie runden.
- Das Soll kommt aus der Szenenliste (Summe 9:30, 30 s Puffer bis 10:00) und aus `docs/praesentation/demo-drehbuch.md`.

## 1. Durchlauf

| Feld | Wert |
|---|---|
| Datum | |
| Start (Uhr) | |
| Ende (Uhr) | |
| Gesamtdauer Ist | |
| Soll | 9:30, Obergrenze 10:00 |
| Gesamtdauer ≤ 10:00 | ja / nein |
| Stufe der Demo | 1 Web-UI / 2 CLI / 3 Video |
| Stand (Commit) | |
| Zahlen in den Szenen gegen `abgabe/` abgeglichen | ja / nein |

### Abschnittszeiten

Ist-Dauer ist das Ende minus der Start des Abschnitts. Beide Uhrzeiten eintragen.

| Nr | Abschnitt | Soll-Fenster | Soll-Dauer | Start Ist | Ende Ist | Dauer Ist |
|---|---|---|---|---|---|---|
| 1 | Szene 1 StatAgent | 0:00–0:20 | 0:20 | | | |
| 2 | Szene 2 Eine falsche Zahl | 0:20–1:20 | 1:00 | | | |
| 3 | Szene 3 Einlesen, rechnen, freigeben | 1:20–2:10 | 0:50 | | | |
| 4 | Szene 4 Was wo läuft | 2:10–2:40 | 0:30 | | | |
| 5 | Szene 5 2.880 von 2.880 | 2:40–3:15 | 0:35 | | | |
| 6 | Szene 6 Acht Fallen in den Daten | 3:15–4:15 | 1:00 | | | |
| 7 | Szene 7 Geburtsmonat 13 | 4:15–5:00 | 0:45 | | | |
| 8a | Szene 8 Überleitung | 5:00–5:10 | 0:10 | | | |
| 8b | D1 Lauf 2025-03 und Qualitätsbericht | 5:10–6:15 | 1:05 | | | |
| 8c | D2 Änderung per Sprache mit Freigabe | 6:15–7:35 | 1:20 | | | |
| 8d | D3 Datenanfrage Männer und Frauen je Bundesland | 7:35–8:10 | 0:35 | | | |
| 8e | UC-Wechsel im App-Header | 8:10–8:20 | 0:10 | | | |
| 9 | Szene 9 Veröffentlicht bleibt veröffentlicht | 8:20–8:50 | 0:30 | | | |
| 10 | Szene 10 Ein Kern, ein Einstieg | 8:50–9:15 | 0:25 | | | |
| 11 | Szene 11 Jede Zahl nachrechenbar | 9:15–9:30 | 0:15 | | | |
| D4 | Optional UC4 „Wartezeiten“ (Entscheid 06:45) | keine eigene Zeit | | gezeigt: ja / nein | | |

### Pflichtschritte

Alle fünf müssen im Durchlauf vorkommen. Die Spalte „vom Lead bestätigt“ füllt der Lead aus, nicht Bernhard.

| Nr | Pflichtschritt | Wo im Ablauf | Uhr (Ist) | Vom Lead bestätigt (Name, Uhr) |
|---|---|---|---|---|
| 1 | Lösung | Szenen 3 bis 5 | | |
| 2 | Fehlerbeispiel | Szene 6 und D1 | | |
| 3 | Eine begründete Annahme | Szene 7 | | |
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
- Weg (b): Stufe 2 im Terminal mit `LLM_PROVIDER=mock`. Er wird zusätzlich protokolliert und ersetzt Weg (a) nicht.

| Feld | Wert |
|---|---|
| Datum | |
| Auslöser (so wurde das Modell unverfügbar gemacht) | |
| Uhr beim Auslöser | |
| Uhr beim ersten sichtbaren Bild der Aufzeichnung | |
| Dauer des Wechsels in Sekunden | |
| Dauer ≤ 30 s | ja / nein |
| Weg (b) Stufe 2 mit `LLM_PROVIDER=mock`: Dauer in Sekunden und Ergebnis | |
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
