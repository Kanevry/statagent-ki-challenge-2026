# Probe-Protokoll (Vorlage)

Gehört zu GitLab #90, Epic #26. Wird am Fr 06.11.2026 ab 06:00 ausgefüllt.

- Probe: Fr 06.11.2026 06:00–07:00 (Europe/Vienna).
- **Feature-Stopp und Freeze: Fr 06.11.2026 07:00 (Europe/Vienna).** Nach dem Freeze ändert niemand Code, Folien oder Demo.
- Ältere Dokumente nennen teils 05:00. Es gilt 07:00 laut Owner.
- Uhrzeiten nur aus der Uhr eintragen: `TZ=Europe/Vienna date`. Nie schätzen, nie runden.
- **Live heißt online** über Hotspot auf der Vorführ-Adresse, Modell Azure (Owner 05.11.2026). Einen Lauf ohne Netz gibt es nicht.
- **Üben ohne Folgen:** Den Änderungsauftrag aus D2 nur bis zum Vorschlag üben, dann ablehnen. Nie `freigabe` üben (siehe Demo-Drehbuch, D2).
- Das Soll kommt aus `uc3-jury.md`: Pfad A Fachjury 15 bis 20 Minuten, Pfad B Management 10 Minuten plus 5 Minuten Fragen. Beide werden gemessen, nach der Uhr.

## 1. Durchlauf

**Probe 1 war eine automatische Probe ohne Sprecher,** Auftrag des Leads: Ein Skript fuhr Pfad A im Browser auf der Vorführ-Adresse, Stand `d2621a2`, gleich main `b9508d6`. Die Sprechzeit kommt von einer Systemstimme mit 150 Wörtern je Minute, ohne Pausen und Fragen. Dauer je Abschnitt: der größere Wert aus Klickzeit und Sprechzeit. Beide Gesamtdauern sind deshalb untere Grenzen. Die echten Dauern stehen unter Probe 2.

| Feld | Wert |
|---|---|
| Datum | 06.11.2026 |
| Start (Uhr) | 06:15 |
| Ende (Uhr) | 06:21 |
| Gesamtdauer Ist | 6:19, untere Grenze, automatische Probe ohne Sprecher |
| Gesamtdauer Ist Pfad A | 7:13, untere Grenze, automatische Probe ohne Sprecher |
| Soll | Die Dauer wird je Pfad getrennt gemessen. „Gesamtdauer Ist“ ist Pfad B, höchstens 10:00. „Gesamtdauer Ist Pfad A“ mit allen fünf Pflichtschritten, höchstens 14:00, ohne Fragen |
| Pfad A ≤ 14:00 | ja, untere Grenze |
| Pfad B ≤ 10:00 | ja, untere Grenze |
| D1 Monat | 2025-10 |
| Hotspot-Wechsel geübt, Dauer in Sekunden | nicht geübt, nicht gemessen, Owner geht davon aus, dass es funktioniert |
| Stand (Commit) | `b9508d6`, Instanz `d2621a2` |
| D4 und Folie 9 (Entscheid 06:45) | ja, die Knopf-Frage, Lead 3d 06:34. In `/uc4` keine Fluktuationsfrage zeigen, bis der Lead den Fix zu !303 live meldet |
| D2 Teil 2 (Entscheid 06:45) | ja, „Beamte zählen nicht mehr mit“, Soll −12.289, Lead 3d 06:34 |
| Datenbank der Vorführung | Kopie des Abgabe-Stands, zurückgesetzt um 06:15 von der Lane Vorführung. Nie `statistik` |
| D3 freie Fragen (Entscheid 06:45) | nur die acht geprüften Fragen und die Wien-Frage. Freie Fragen der Jury nur auf Nachfrage und mit dem Hinweis, dass sie nicht gegen das Orakel geprüft sind, Lead 3d 06:34 |
| Zahlen in den Szenen gegen `abgabe/` abgeglichen | teilweise: die 17 Monatswerte von Folie 3 direkt, die übrigen über das Belegregister |

### Abschnittszeiten

Ist-Dauer ist das Ende minus der Start des Abschnitts. Beide Uhrzeiten eintragen.

| Nr | Abschnitt | Soll-Fenster | Soll-Dauer | Start Ist | Ende Ist | Dauer Ist |
|---|---|---|---|---|---|---|
| 1 | Pfad A: Lösung und Fehler, Oktober 2025 | 0:00–3:00 | 3:00 | 06:15:35 | 06:17:27 | 1:52 |
| 2 | Pfad A: Bericht August 2024 | 3:00–4:00 | 1:00 | 06:17:27 | 06:17:30 | 0:17 |
| 3 | Pfad A: Annahme, Folie 8 | 4:00–5:00 | 1:00 | 06:17:30 | 06:17:35 | 0:36 |
| 4 | Pfad A: D2 Teil 1 Rückblick | 5:00–6:00 | 1:00 | 06:17:35 | 06:17:40 | 0:34 |
| 5 | Pfad A: D2 Teil 2 Änderung der Jury | 6:00–9:30 | 3:30 | 06:17:40 | 06:20:28 | 2:48 |
| 6 | Pfad A: D3 Datenanfragen | 9:30–12:00 | 2:30 | 06:20:28 | 06:20:57 | 0:29 |
| 7 | Pfad A: Absage | 12:00–13:00 | 1:00 | 06:20:57 | 06:21:06 | 0:09 |
| 8 | Pfad A: D4 Wien-Frage (Entscheid 06:45) | 13:00–14:00 | 1:00 | 06:21:06 | 06:21:33 | 0:27 |
| 9 | Pfad B: Folie 1 Drei Menschen | 0:00–1:00 | 1:00 | automatisch, ohne Uhr | automatisch, ohne Uhr | 0:36 |
| 10 | Pfad B: Folie 2 Oktober 2025 | 1:00–2:30 | 1:30 | automatisch, ohne Uhr | automatisch, ohne Uhr | 0:34 |
| 11 | Pfad B: Folie 3 StatAgent hält an | 2:30–3:15 | 0:45 | automatisch, ohne Uhr | automatisch, ohne Uhr | 0:38 |
| 12 | Pfad B: Folie 4 Nachgerechnet | 3:15–4:15 | 1:00 | automatisch, ohne Uhr | automatisch, ohne Uhr | 0:43 |
| 13 | Pfad B: Folie 5 Acht Arten von Fehlern | 4:15–5:15 | 1:00 | automatisch, ohne Uhr | automatisch, ohne Uhr | 0:37 |
| 14 | Pfad B: Folie 6 Wer was macht | 5:15–6:15 | 1:00 | automatisch, ohne Uhr | automatisch, ohne Uhr | 0:33 |
| 15 | Pfad B: Folie 7 Drei Aufträge | 6:15–7:15 | 1:00 | automatisch, ohne Uhr | automatisch, ohne Uhr | 0:54 |
| 16 | Pfad B: Folie 8 Gerechnet ohne KI | 7:15–8:15 | 1:00 | automatisch, ohne Uhr | automatisch, ohne Uhr | 0:45 |
| 17 | Pfad B: Folie 9 Eine Frage, drei Antworten | 8:15–9:00 | 0:45 | automatisch, ohne Uhr | automatisch, ohne Uhr | 0:27 |
| 18 | Pfad B: Folie 10 Verantwortung | 9:00–9:45 | 0:45 | automatisch, ohne Uhr | automatisch, ohne Uhr | 0:24 |
| 19 | Pfad B: Folie 11 Schluss | 9:45–10:00 | 0:15 | automatisch, ohne Uhr | automatisch, ohne Uhr | 0:07 |

### Pflichtschritte

Alle fünf müssen im Durchlauf vorkommen. Die Spalte „vom Lead bestätigt“ füllt der Lead aus, nicht Bernhard.

| Nr | Pflichtschritt | Wo im Ablauf | Uhr (Ist) | Vom Lead bestätigt (Name, Uhr) |
|---|---|---|---|---|
| 1 | Lösung | Pfad A: `/uc3`, Bericht August 2024 | 06:15:35 bis 06:17:27 | Lead 3d, gelesen 06:28, Bild 01 |
| 2 | Fehlerbeispiel | Pfad A: D1 | 06:27 bis 06:28, Nachmessung | Lead 3d, 06:29, Bild vom Bericht Oktober 2025 |
| 3 | Eine begründete Annahme | Pfad A: Folie 8 | 06:17:30 bis 06:17:35 | Lead 3d, gelesen 06:28, Bild 03 |
| 4 | Live-Änderung mit Vorher/Nachher | D2 | 06:17:40 bis 06:20:28 | Lead 3d, gelesen 06:28, Bild 05 |
| 5 | Eine Datenfrage | D3 | 06:20:28 bis 06:20:57 | Lead 3d, gelesen 06:28, Bild 06 |

Ergebnis: 5 von 5 bestätigt (Ziel 5 von 5).

### Auffälligkeiten

| Nr | Was fiel auf | Abschnitt | Maßnahme | Erledigt vor 07:00 |
|---|---|---|---|---|
| 1 | D1: „Rechnen“ läuft nach Regelsatz v2, die Seite zeigt 319.768 + 77.746 = 397.514, im Drehbuch stand 313.154 (alte Regeln). 78.949 stimmt auf beiden | 1 | Drehbuch und Klickliste am Endstand ändern, Satz dazu: Das Video zeigt die alten Regeln, „Rechnen“ rechnet nach den Änderungsaufträgen | offen |
| 2 | D1: Das Skript fand nach dem Klick den Bericht nicht. Nachmessung 06:27: Der Link geht, 78.949 und „angehalten“ stehen im ersten Bildschirm. Fehler im Skript | 1 | keine | ja |
| 3 | „2.880 von 2.880“ steht auf dem Bericht August 2024 nur zugeklappt, sichtbar ist 392.236 | 2 | Sprechsatz bleibt, Klickliste geändert | offen |
| 4 | Vorschlag blieb offen, Ablehnen scheiterte am Skript, Instanz zurückgesetzt | 5 | keine | ja |

## 2. Backup-Video

Der Metadatenbericht steht in `docs/praesentation/backup-video.md`, Abschnitt „Metadatenbericht“. Er enthält Datei, Dauer, Größe, SHA-256, Auflösung, Abspieltest offline und Sichtprüfung.

| Feld | Wert |
|---|---|
| Metadatenbericht ausgefüllt | ja |
| Abspieltest offline bestanden | ja, nur der Browser war ohne Netz, der Rechner nicht, 165 s bis zum Ende, 06:24 |
| Sichtprüfung bestanden (0 sichtbare Secrets) | ja |
| Geprüft von, Uhr | Agent UI-Regie, nicht Mensch, 03:2x |

## 3. Ausfallprobe

Automatisch auf dem Rechner der Session, nicht am Vortragsrechner. Gemessen wird der Wechsel auf die Aufzeichnung, Nachweis für #90. Ziel: höchstens 30 Sekunden. Der Wechsel des Hotspots steht oben im Durchlauf.

| Feld | Wert |
|---|---|
| Datum | 06.11.2026 |
| Auslöser (so wurde das Modell unverfügbar gemacht) | Browser ohne Netz gesetzt, das Modell selbst wurde nicht abgeschaltet |
| Uhr beim Auslöser | 06:21:38 |
| Uhr beim ersten sichtbaren Bild der Aufzeichnung | 06:21:39 |
| Dauer des Wechsels in Sekunden | 1 |
| Dauer ≤ 30 s | ja |
| Aufzeichnung gekennzeichnet („Das ist eine Aufzeichnung von heute früh“ gesagt) | nein, kein Sprecher in Probe 1, Probe 2 prüft das |
| Kennzeichnung im Bild sichtbar | ja |
| Wiederholt nach Fehlschlag | nein |
| Vom Lead bestätigt (Name, Uhr) | Lead 3d, 06:34, nach Bild; die Zeiten stammen von E5, nur Browser ohne Netz, Rechner online |

## 4. Freeze

| Feld | Wert |
|---|---|
| Freeze-Zeit (Soll) | Fr 06.11.2026 07:00 Europe/Vienna |
| Freeze bestätigt (Uhr aus `TZ=Europe/Vienna date`) | |
| Stand (Commit) beim Freeze | |
| Offene Punkte | |

## 5. Probe 2

Geplant war ein voller Vortrag des Owners samt Demo. Sie fand nicht statt. Die Abschnitte oben gehören zu Probe 1.

| Feld | Wert |
|---|---|
| Probe 2 Start (Uhr) | nicht gehalten |
| Probe 2 Ende (Uhr) | nicht gehalten |
| Probe 2 Dauer Pfad A | nicht gemessen, kein Sprecher, keine Stoppuhr |
| Probe 2 Dauer Pfad B | nicht gemessen, kein Sprecher, keine Stoppuhr |
| Probe 2 Befunde | Keine Sprechprobe, Owner-Wort 06.11.2026 08:35 („machs pragmatisch“). Stattdessen die Klickwege D1 bis D4 auf dem Endstand der Vorführ-Adresse nachgemessen, 07:44 bis 07:50, ohne Abweichung von der Klickliste: D1 106 s, D2 Vorschlag 2:42, D3 8 bis 16 s, D4 14 s. 26-1 bleibt damit offen, 90-3 bleibt rot |
