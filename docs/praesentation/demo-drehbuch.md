# Demo-Drehbuch (nach Szene 10, 5:05–9:30)

Gehört zu GitLab #90, Epic #26. Zahlen tragen ihre Kennung aus dem Belegregister (F1 bis F19).

Feature-Stopp und Freeze für Code, Präsentation und Demo: **Fr 06.11.2026 07:00 (Europe/Vienna)**. Nach dem Freeze ändert niemand mehr etwas. Die Demo läuft auf dem Stand vom Freeze.

Folge: Erst die Präsentation (Szene 1 bis 10, 0:00–5:05), dann die Demo (5:05–9:30). Danach folgen Live-Änderung und Datenanfragen der Jury bis etwa 15:00 (Fragenkatalog Teil A und B). Die Szenen zeigen das Zielbild. Der Tagesstand steht nur im Fragenkatalog.

## Überblick

| Zeit | Schritt | Dauer |
|---|---|---|
| 5:05–6:15 | D1 Lauf und Qualitätsbericht (2025-10 angehalten, alternativ 2025-03) | 1:10 |
| 6:15–7:45 | D2 Änderung per Sprache mit sichtbarer Wirkung und Freigabe | 1:30 |
| 7:45–9:00 | D3 Datenanfragen der Jury-Aufgabe | 1:15 |
| 9:00–9:30 | D4 Gemeinsamer Einstieg: die Wien-Frage in `/uc4` | 0:30 |
| 9:30 | Ende der Demo, danach Fragen der Jury | |

Die Demo dauert 4:25 (5:05–9:30). Eine eigene Überleitung gibt es nicht. Szene 10 endet mit der Einladung „Nennen Sie mir eine Regel, die ich jetzt ändern soll.“ Bernhard wechselt danach sofort zum Terminal oder Browser.

## Wo die Demo läuft

- **Live heißt: auf dem Rechner von Bernhard.** Stufe 1 ist der lokale Stand mit dem Modell Azure.
- **Die öffentliche Demo läuft im Testmodus.** Dort zeigt der Kopf „Modell mock · mock“, und `/uc3` zeigt den Leerzustand. Sie ist keine Live-Demo des Agenten. Wird sie gezeigt, sagt Bernhard vorher „Testmodus“ an.
- **Bedingung für die Web-Oberfläche:** Die Seite `/uc3` liegt noch in MR !51. Nur wenn sie bis zum Freeze auf main ist, wird die Web-Oberfläche gezeigt. Sonst ist der CLI-Weg (Stufe 2) der Standard. Der Stand wird um 06:45 geprüft und in `probe.md` eingetragen.

## Schritte

### D1 Lauf und Qualitätsbericht (5:05–6:15)

Standard ist Oktober 2025, weil Szene 3 diesen Monat zeigt. Alternative ist März 2025 (Szene 6). Bernhard wählt vorab einen der beiden und trägt die Wahl in `probe.md` ein.

- CLI-Weg (Standard): `uv run uc3 lauf --lieferung 2025-10`, danach `uv run uc3 laeufe`. Bericht: `abgabe/qualitaetsberichte/2025-10.md`. Alternative: `--lieferung 2025-03` und `abgabe/qualitaetsberichte/2025-03.md`.
- Klickweg, nur wenn `/uc3` (MR !51) bis zum Freeze auf main ist: Web-UI, Seite `/uc3`, dann „Lauf-Detail“ des gewählten Monats. Dort steht der Qualitätsbericht.
- Sagt Bernhard (Oktober 2025): „Das ist der Monat aus der Präsentation. Es kommen 313.154 gegen 394.200 im Vormonat (F17). 78.949 Verhältnisse fehlen in der Lieferung (F11). Das Programm hält den Monat an und markiert ihn als vorläufig.“
- Sagt Bernhard (März 2025): „März 2025 hat zwei Fehler auf einmal. 1.663 Zeilen sind doppelt (F8), und die freien Dienstverträge fehlen ganz, 1.492 Verhältnisse (F9). Das Programm hält den Monat an und markiert ihn als vorläufig.“
- Jury muss sehen (Oktober 2025):
  - Prüfregel P15: 313.154 gegen 394.200 (F17), Einstufung sichtbar.
  - Prüfregel P16: 78.949 von 394.200 Verhältnissen fehlen (F11).
  - Prüfregel P17: 345.078 Zeilen gegen 434.104 im Vormonat (F11).
  - Status des Monats: angehalten und vorläufig. 77.746 Verhältnisse sind fortgeschrieben, 390.900 sind als vorläufiger Bestand ausgewiesen (F11).
  - Nichts wurde gelöscht. Die Rohdaten bleiben.
- Jury muss sehen (März 2025):
  - Auffälligkeit Volldubletten mit 1.663 Zeilen (F8), Einstufung sichtbar.
  - Auffälligkeit fehlende freie Dienstverträge mit 1.492 Verhältnissen (F9), Einstufung sichtbar.
  - Status des Monats: angehalten und vorläufig.
- Hinweis zu 81.046 und 78.949: Die Differenz der Bestände ist 394.200 minus 313.154, also 81.046 (F17). Die Zahl 78.949 zählt Verhältnisse, die in der Lieferung gar nicht vorkommen (F11). Das sind zwei verschiedene Messungen. Bernhard nennt in der Demo beide nur mit ihrer Bedeutung.

### D2 Änderung per Sprache mit sichtbarer Wirkung (6:15–7:45)

Auftrag: „Dienstvertrag und freien Dienstvertrag in der Statistik zusammen ausweisen.“ Er ändert Zahlen, die Jury sieht also eine echte Wirkung. Der Gesamtbestand bleibt gleich.

Aufnahme als Vorbild: Die Freigabe-Seite aus MR !51 zeigte den Vorschlag uc3/24. Gesamt 392.236 bleibt (F14). Die Kategorien verschieben sich, zum Beispiel Angestellte (Qualifikation) von 0 auf 236.961 und Angestellte (freier Dienstvertrag) von 1.142 auf 0 (F19). Die Kennung des Live-Vorschlags ist eine andere. Bernhard liest die Zahlen live vom Bildschirm.

Ablauf mit den Befehlen (im Terminal, in der Web-UI nur bei `/uc3` auf main, gleiche Schritte):

1. 6:15 Auftrag stellen. Der Agent erzeugt nur einen Vorschlag und ändert nichts:
   `uv run uc3 agent "Weise Dienstvertrag und freien Dienstvertrag in der Statistik zusammen aus" --probe 2024-08`
2. 6:45 Vorschlag ansehen:
   `uv run uc3 vorschlag zeigen <id>`
3. 7:15 Freigeben mit Vor- und Nachnamen:
   `uv run uc3 freigabe <id> --name "Bernhard Götzendorfer"`
4. 7:30 Protokoll zeigen:
   `uv run uc3 protokoll --zeigen`

- Sagt Bernhard (bei 1): „Ich sage der Maschine in einem Satz, was sich ändern soll. Sie schreibt nur einen Vorschlag.“
- Sagt Bernhard (bei 2): „Hier ist der Unterschied in der Regel. Und hier die Zahlen vorher und nachher. Der Gesamtbestand bleibt bei 392.236. Die Kategorien verschieben sich.“
- Sagt Bernhard (bei 3 und 4): „Erst mit meinem Namen wird es wirksam. Der gespeicherte Änderungsschritt im Repo trägt den Vermerk Freigegeben-von. Das Protokoll hält es fest.“
- Jury muss sehen:
  - Regel-Diff des Vorschlags. Den Regelnamen liest Bernhard vom Bildschirm vor.
  - Zahlen vorher und nachher: Gesamt gleich, Kategorien verschoben.
  - Freigabe mit Vor- und Nachname, „Team“ wird abgelehnt (`shared/py/plattform/freigabe.py`, `pruefe_name`).
  - Gespeicherter Änderungsschritt (Commit) mit dem Vermerk `Freigegeben-von`.
  - Eintrag im Protokoll.
- Vorher prüft Bernhard: Er nimmt die Kennung `<id>` aus der Ausgabe von Schritt 1. Nie eine Kennung von gestern übernehmen.
- Üben nur bis zur Ablehnung: `uv run uc3 vorschlag zeigen <id>`, dann `uv run uc3 ablehnen <id> --name "Bernhard Götzendorfer" --begruendung "Übung vor der Jury"`. Vor der Jury nie `freigabe` üben. Es aktiviert den Regelsatz v2 und committet. Einen Reset-Befehl gibt es nicht (`uc3/statagent/cli.py`). Wäre v2 schon geändert, träfe die Live-Änderung auf einen anderen Stand als geprobt.
- Modell: D2 braucht das echte Modell (Azure). Mit `mock` gibt es keinen Vorschlag.
- Die Wirkung auf Zahlen ist größer als bei der früheren Übung mit der Altersgrenze. Die Altersgrenze bleibt als Beispiel für „Zahlen bleiben gleich“ im Fragenkatalog, Teil B1 (F5).

### D3 Datenanfragen (7:45–9:00)

Drei Anfragen, je etwa 25 Sekunden: Zeitreihe, Männer und Frauen je Bundesland, Fluktuation je Branche.

- Befehl (nur wenn MR !61 bis zum Freeze auf main ist): `uv run uc3 frage "…"`. Heute ist `frage` noch nicht fertig (`uc3/statagent/cli.py`, Hinweis #74).
- Sonst: SQL mit `psql` gegen die UC3-Datenbank. Die fertigen Abfragen stehen in `docs/praesentation/fragenkatalog.md`, Teil A1, A2 und A3.
- Sagt Bernhard: „Drei Fragen an die Daten. Die SQL sehen Sie hier vollständig. Die Summen stimmen mit dem Beispielbericht überein.“
- Jury muss sehen:
  - Die SQL im Klartext, bei `frage` zusätzlich den Antwortweg.
  - A1 Zeitreihe: erste Zeile 392.236 (F2). Der Oktober 2025 steht als vorläufig mit 390.900 (F11).
  - A2 Männer und Frauen je Bundesland. Zur Kontrolle für Bernhard (Stand 08/2024): gesamt 392.236, Männer 211.603, Frauen 180.633 (F14). Wien 90.799, Niederösterreich 64.505 (F14).
  - A3 Fluktuation je Branche: Zugänge, Abgänge, Saldo. Ergebnis live. Nie zwei Monate mit verschiedener ÖNACE-Version Abschnitt gegen Abschnitt vergleichen (F13).
- Die Zahlen oben gelten für den Stichtag 31.08.2024. Läuft die Anfrage auf einem anderen Monat, steht der Monat sichtbar in der SQL.

### D4 Gemeinsamer Einstieg (9:00–9:30)

- Die Wien-Frage in `/uc4`: „Wie viele Menschen arbeiten in Wien im Gesundheits- und Sozialwesen (März 2025), und was heißt das für Wartezeiten beim Arzt?“
- Sollwert für UC3: **7.498** Beschäftigungsverhältnisse (F18), Wien, ÖNACE 2025 Abschnitt R (Gesundheits- und Sozialwesen), Stichtag 31.03.2025, mit Beleg. UC2 liefert die Abwägung, UC1 die Erklärung in einfacher Sprache.
- Die Frage stammt aus dem Abgleich der Review-Bank. Die Wartezeiten selbst kann UC3 nicht beantworten, es kennt nur Beschäftigte.
- **Testmodus ansagen:** Laufen die Modelle online im Testmodus (mock), sagt Bernhard vorher „Testmodus“. Dann ist die Antwort fest vorgegeben und keine Live-Antwort eines Modells.
- Was von UC1 und UC2 läuft, steht im Tagesstand des Fragenkatalogs (Teil C, „Läuft der gemeinsame Einstieg schon?“). Bernhard sagt nur, was dort steht.
- Nur wenn `/uc4` bis zum Freeze grün ist. Sonst entfällt D4 ohne Ersatz, die Demo endet um 9:00.
- **Entscheid am Fr 06:45.** Wer entscheidet: Lead mit Bernhard. Ergebnis in `probe.md` eintragen.
- Sagt Bernhard: „Eine Frage, drei Antworten. Die Zahl kommt aus UC3 und trägt ihren Beleg: 7.498.“

## Rückfallstufen

Die Stufen brauchen keinen Umbau. Die Befehle bleiben gleich.

| Stufe | Auslöser | Wechsel (höchstens 30 s) | Was Bernhard sagt |
|---|---|---|---|
| 1 Web-UI | Nur wenn `/uc3` (MR !51) bis zum Freeze auf main ist: lokaler Stand auf dem Rechner von Bernhard, Modell Azure. Ist die öffentliche Demo im Bild, läuft sie im Testmodus. | keiner | nichts Besonderes. Bei der öffentlichen Demo vorher: „Das ist der Testmodus.“ |
| 2 CLI im Terminal | Standard, solange `/uc3` nicht auf main ist. Auch: Web-UI lädt nicht, Netz fällt aus oder Seite zeigt Fehler. Auch: Live-Modell antwortet nicht (dann nur für D1 und D3, D4 entfällt). | Terminal-Fenster nach vorn holen. Dieselben Befehle wie in D1 bis D3. Bei fehlendem Modell vorher `LLM_PROVIDER=mock` setzen: Damit laufen D1 und D3, denn sie brauchen kein Modell. D2 geht ohne Modell auf die Aufzeichnung (Stufe 3). | „Die Oberfläche macht gerade Pause. Ich zeige dasselbe im Terminal.“ Bei fehlendem Modell zusätzlich: „Das Modell ist nicht erreichbar. Lauf und Datenanfrage brauchen keins (F16). Die Änderung zeige ich als Aufzeichnung.“ Bei D3 zählt hier der SQL-Weg, denn ob `frage` ein Modell braucht, steht erst mit MR !61 fest. |
| 3 Backup-Video | Auch das Terminal geht nicht (Datenbank, Rechner). | Vorbereiteten Videoplayer mit der lokalen Datei in den Vordergrund holen und starten. Plan: `docs/praesentation/backup-video.md`. | „Das ist eine Aufzeichnung von heute früh.“ |

Regeln für alle Stufen:

- Eine Aufzeichnung wird immer als Aufzeichnung gekennzeichnet. Bernhard sagt es vor dem ersten Bild.
- Der Wechsel zählt ab dem Auslöser bis zum ersten sichtbaren Bild der neuen Stufe. Mehr als 30 Sekunden gelten als Fehlschlag der Probe.
- Im Modus `mock` entsteht kein Modellaufruf. Es gibt dort nur die Smoke-Fixture `shared/py/plattform/fixtures/smoke.json`. Der Agent braucht `agent.koordinator.json`. Fehlt sie, bricht er ab (`shared/py/plattform/llm/mock.py`, Zeile 56). Einen Mock-Rückfall für D2 gibt es deshalb nicht.
- Beim Wechsel nicht diskutieren, nicht entschuldigen. Ein Satz, dann weiter.

## Vorbereitungs-Checkliste Fr 06:00–07:00

Jeder Punkt wird abgehakt, sobald er geprüft ist. Uhrzeit nur aus der Uhr (`TZ=Europe/Vienna date`), nie schätzen.

- [ ] Datenbank läuft und antwortet.
- [ ] Regelsatz freigegeben: Bernhard gibt die Regeln mit seinem Namen frei (`uv run uc3 regeln freigeben --name "Bernhard Götzendorfer"`), danach `uv run uc3 lauf --alle` und `uv run uc3 berichte --alle`. Ohne diese Freigabe nennt der Bericht „Regeln ohne Freigabe“. Jeder Lauf bleibt danach vorläufig (`uc3/statagent/lauf.py`, Zeile 151 bis 152). Das ist eine Handlung des Owners, spätestens 05:30.
- [ ] Entscheid des Leads: ob und welche Monate veröffentlicht werden. Ohne diesen Entscheid zeigt die Jury vorläufige Monate. Das ist gewollt und wird nicht als Fehler erklärt.
- [ ] Läufe 2024-08 bis 2026-07 sind vorhanden (24 Lieferungen, F3). Prüfung mit `uv run uc3 laeufe`.
- [ ] Ist `/uc3` (MR !51) auf main: Browser-Tabs vorbereitet (`/uc3` mit Lauf-Detail des gewählten Monats aus D1, Protokoll, bei D4 zusätzlich `/uc4`). Sonst: Terminal ist der Standard.
- [ ] Terminal mit großer Schrift, aus 3 Metern lesbar.
- [ ] Modell-Schalter geprüft: `LLM_PROVIDER` auf den Standard. Mit `mock` laufen nur D1 und D3.
- [ ] Video lokal geöffnet und startklar (Stufe 3).
- [ ] Netz aus getestet: Stufe 2 (D1 und D3) und Stufe 3 laufen ohne Netz. D2 braucht das Modell.
- [ ] Keine Secrets sichtbar. Umgebungsvariablen nicht im Terminal anzeigen, keine `.env.local` öffnen.
- [ ] Zahlen in den Szenen gegen `abgabe/` abgeglichen.
- [ ] D1: Monat gewählt (2025-10 oder 2025-03) und in `probe.md` eingetragen.
- [ ] D3: MR !61 auf main? Dann `uv run uc3 frage "…"` je Anfrage geprobt. Sonst SQL A1 bis A3 aus dem Fragenkatalog bereit, `<regelstand>` eingesetzt.
- [ ] D4: Sollwert 7.498 (F18) gegen die Abfrage im Belegregister geprüft. Testmodus-Ansage bereit.
- [ ] Übungsauftrag aus D2 (Dienstvertrag und freier Dienstvertrag) nur bis `vorschlag zeigen <id>` gelaufen, dann `ablehnen <id>` mit der Begründung „Übung vor der Jury“. Nie `freigabe` geübt.
- [ ] Entscheid D4 um 06:45 getroffen und in `probe.md` eingetragen.
- [ ] Freeze um 07:00 (Europe/Vienna) bestätigt. Danach keine Änderung mehr.
