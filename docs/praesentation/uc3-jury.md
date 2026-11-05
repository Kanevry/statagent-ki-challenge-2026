# Fachjury Use Case 3: Ablauf der 15 Minuten

Dieses Blatt ist der Ablauf für das Gespräch mit der Fachjury. Es folgt den drei Teilen der Aufgabenstellung (Abschnitt „Abgabe und Fachjury“): Präsentation, Live-Änderung, Datenanfragen. Sprechtext, Befehle und Sollzahlen stehen in den Dateien, auf die jede Zeile zeigt. Zahlen tragen ihre Kennung aus dem Belegregister (`belegregister.md`).

Gehört zu GitLab #20 (Kriterium AC3) und Epic #26.

- **Termine:** Probe Fr 06.11.2026 06:00 bis 07:00, Freeze 07:00, Fachjury ab 09:00 (Europe/Vienna).
- **Wer spricht:** Bernhard Götzendorfer, am eigenen Rechner.
- **Datenbank:** Die ganze Vorführung läuft gegen die Kopie `statistik_vorfuehrung`, nie gegen die Abgabe-Datenbank `statistik`.
- **Auf dem Tisch:** die Kriterien-Karte (`kriterien-karte.md`) ausgedruckt, daneben der Fragenkatalog (`fragenkatalog.md`).

## Überblick

| Zeit | Teil der Aufgabe | Was die Jury sieht | Wo es steht |
|---|---|---|---|
| 0:00–5:05 | 1 Präsentation | Szenen 1 bis 10: Lösung, gefundene Fehler, eine Annahme im Detail | `skript-fachjury.md`, Abschnitt 1 |
| 5:05–6:15 | 1 Präsentation | D1: ein Lauf mit Qualitätsbericht, der Monat wird angehalten | `demo-drehbuch.md`, D1 |
| 6:15–7:45 | 2 Live-Änderung | D2: Rückblick auf die drei Aufträge, dann die Änderung der Jury | `demo-drehbuch.md`, D2 |
| 7:45–9:00 | 3 Datenanfragen | D3: Zeitreihe, Männer und Frauen, Fluktuation je Wirtschaftsbereich | `demo-drehbuch.md`, D3 |
| 9:00–9:30 | Zusatz | D4: die Wien-Frage durch alle drei Räume, nur wenn `/uc4` beim Freeze läuft | `demo-drehbuch.md`, D4 |
| 9:30–15:00 | Fragen der Jury | weitere Änderungen und Datenanfragen, Nachfragen zu den Bereichen | `fragenkatalog.md`, Teil B und C |

Wird die Zeit knapp, entfällt zuerst D4, dann der Rückblick in D2 Teil 1. Die Änderung der Jury und die drei Datenanfragen bleiben immer drin, denn sie verlangt die Aufgabe.

## 1 Präsentation: Lösung, Fehler, eine Annahme

**Die Lösung (Szenen 4 und 5).** Eine Lieferung geht hinein, ein Qualitätsbericht kommt heraus. Die KI schreibt Vorschläge, das Programm rechnet, ein Mensch gibt mit Namen frei. Der offizielle Bericht für August 2024 wird ganz nachgerechnet, 2.880 von 2.880 Zahlen stimmen (F1). Für die anderen 23 Monate wachen 24 Prüfregeln (F15). Zwei Läufe mit denselben Daten und Regeln ergeben dieselben Zahlen (F16).

**Die gefundenen Fehler (Szene 6 und D1).** Acht Arten von Fehlern, jede mit Zahl, Lieferung und Einstufung im Qualitätsbericht (F4 bis F11). Gelöscht wird nichts: Das Programm korrigiert nach einer Regel oder hält den Monat an und fragt nach. In D1 sieht die Jury das an einem echten Monat, Oktober 2025 (F11, F17) oder März 2025 (F8, F9). Die Liste zum Vorlesen steht im Skript, Abschnitt 3 „Gefundene Datenfehler“.

**Eine Annahme im Detail (Szene 8).** Geburtsmonat 13: 370 Beschäftigungsverhältnisse am Stichtag August 2024 (F4). Drei Rechenwege wurden gegen 576 Zahlen des offiziellen Berichts geprüft, nur einer trifft alle: Berichtsjahr minus Geburtsjahr. Als Geburtstag gilt der 1. Juli. Welcher Tag für Jänner bis Juni gilt, fragen wir die Fachabteilung (Rückfrage R1).

- Fundstellen: `docs/plan/uc3/annahmen.md` (A4), `abgabe/rueckfragen/R1.md`, Regeln `E03_datum_pruefen` und `R5_alter`.
- Fragt die Jury, ob das zirkulär ist: Fragenkatalog C15.

## 2 Live-Änderung: eine unbekannte Änderung der Jury

Die Aufgabe verlangt eine Änderung „per Sprache“ über die eigenen Agenten. Bei uns heißt das: Bernhard tippt den Wunsch der Jury als einen Satz in Alltagssprache (Entscheid des Owners, 05.11.2026). Fragt die Jury nach einem Mikrofon, sagt er genau das.

Ablauf (Befehle im Drehbuch D2 und im Fragenkatalog Teil B):

1. **Zuhören.** Den Wunsch ganz anhören.
2. **Wiederholen.** „Ich verstehe: Sie wollen …“, erst nach dem Ja weiter.
3. **Vorschlag erzeugen.** Den Satz an den Agenten geben. Er schreibt nur einen Vorschlag und ändert nichts.
4. **Vorher und nachher zeigen.** Regel-Unterschied und Zahlen vor und nach der Änderung vorlesen.
5. **Freigeben.** Mit Vor- und Nachnamen. Dann das Protokoll zeigen: Anweisung, Änderung, wer freigegeben hat und wann.

Damit sieht die Jury, was die Aufgabe verlangt: Protokoll und Zahlen vorher und nachher.

- **Ersatz:** Nennt die Jury nichts oder scheitert der Vorschlag zweimal, nimmt Bernhard die geübte Änderung B2 (Geburtsmonat 13).
- **Rückblick:** Die drei Änderungsaufträge der Aufgabe sind schon umgesetzt und mit Namen freigegeben (Vorschläge 24 bis 26, F19, F26). Das zeigt D2 Teil 1.
- **Grenze:** Ein Wunsch, der eine neue Regel oder neuen Code braucht, wird als Vorschlag angenommen und erst nach einer Probe freigegeben. Der Satz dazu steht im Drehbuch D2.
- **Entscheid um 06:45** in `probe.md`: Teil 1 allein oder Teil 1 und Teil 2.

## 3 Datenanfragen: drei Arten von Fragen

Die Aufgabe nennt als Beispiele eine Zeitreihe, Männer und Frauen und die Fluktuation je Wirtschaftsbereich. Für jede Art gibt es eine geprüfte Frage. Bernhard tippt sie wörtlich wie im Drehbuch D3.

| Art | Frage im Drehbuch D3 | Sollzahl | Kennung |
|---|---|---|---|
| Zeitreihe | Frage 1 | 24 Werte, August 2024 392.236, Juli 2026 399.027 | F14, F21 |
| Männer und Frauen | Frage 2 (August 2024, je Bundesland) | Männer 211.603, Frauen 180.633 | F14 |
| Fluktuation je Wirtschaftsbereich | Frage 4 (Oktober 2024) | 3,42 %, 12.215 Zugänge, 14.557 Abgänge | F23 |

- **Weg:** Seite `/uc3/fragen`, sonst `uv run uc3 frage "…"`, sonst das SQL aus dem Fragenkatalog, Teil A1 bis A3. Die Antwort zeigt Zahl oder Tabelle und die Abfrage, unter „Details“ den ganzen Satz und die Definition. Bei Männern und Frauen stehen die Summen dort, also „Details“ aufklappen. Ein Sprachmodell rechnet hier nichts.
- **Freie Fragen der Jury:** nur, wenn der Stand um 06:45 sie trägt (Eintrag in `probe.md`). Sonst bietet Bernhard die nächste geprüfte Frage an oder nimmt das SQL aus Teil A. Was heute noch eine falsche Antwort geben kann, steht im Drehbuch D3 unter „Nicht vorführen“.
- Weicht eine Zahl von der Sollzahl ab, wechselt Bernhard ohne Kommentar auf das SQL. Die Abweichung kommt ins Probe-Protokoll.

## 4 Nachfragen der Jury bis 15:00

- Bei jeder Frage zeigt Bernhard auf die Zeile der Kriterien-Karte, nennt die Zahl mit Kennung und öffnet die Fundstelle.
- Erwartete Fragen und Kurzantworten: Fragenkatalog Teil C (C1 bis C17).
- Steht eine Frage nicht im Katalog: „Das habe ich nicht vorbereitet. Ich zeige Ihnen, wo die Antwort steht.“ Dann den Weg zeigen, nicht raten.
- Was wir nicht sagen: Skript, Abschnitt 5 „Nicht sagen“.

## Ehrliche Grenzen

Bernhard nennt sie, wenn die Jury fragt, und versteckt sie nicht.

- Die Live-Änderung ist ein getippter Satz, keine gesprochene Eingabe.
- Gezählt wird nach ÖNACE-Abschnitt und Bundesland, nicht bis zum 5-Steller und nicht nach Bezirk oder Gemeinde (Kriterien-Karte, Bereich 2).
- Die Pensionsmeldungen der Träger sind nicht eingelesen (Bereich 1).
- Das Alter bei Geburtsmonat 13 vor Juli hängt an der Antwort auf R1. Die Altersgrenze 110 ist ein Parameter ohne amtlichen Standard (F5).
- Alle Grenzen gesammelt: Fragenkatalog C14.

## Probe und Backup-Video

- **Probe:** Fr 06:00 nach `probe.md`. Dort stehen die gemessene Gesamtdauer, die Abschnittszeiten und die Entscheide von 06:45 (D2 Teil 2, freie Datenfragen, D4).
- **Rückfall:** drei Stufen, Web-Oberfläche, Terminal, Video (`demo-drehbuch.md`, Abschnitt „Rückfallstufen“). Ein Wechsel dauert höchstens 30 Sekunden.
- **Backup-Video:** Aufnahme bis 05:45 auf dem Stand des Freeze, Datei, Dauer und SHA-256 in `backup-video.md`. Es wird immer angesagt: „Das ist eine Aufzeichnung von heute früh.“
