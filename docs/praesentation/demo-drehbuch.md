# Demo-Drehbuch (Folie 8, 5:00–8:30)

Gehört zu GitLab #90, Epic #26. Zahlen tragen ihre Kennung aus dem Belegregister (F1 bis F16).

Feature-Stopp und Freeze für Code, Präsentation und Demo: **Fr 06.11.2026 07:00 (Europe/Vienna)**. Nach dem Freeze ändert niemand mehr etwas. Die Demo läuft auf dem Stand vom Freeze.

## Überblick

| Zeit | Schritt | Dauer |
|---|---|---|
| 5:00–5:15 | Überleitung von Folie 7 | 0:15 |
| 5:15–6:20 | D1 Lauf 2025-03 und Qualitätsbericht | 1:05 |
| 6:20–7:40 | D2 Änderung per Sprache mit Freigabe | 1:20 |
| 7:40–8:20 | D3 Datenanfrage Männer und Frauen je Bundesland | 0:40 |
| 8:20–8:30 | UC-Wechsel im App-Header | 0:10 |
| 8:30 | Weiter mit Folie 9 | |

Die Demo selbst dauert 3:15 (5:15–8:30). Optional D4 steht am Ende dieses Blatts und hat keine eigene Zeit.

## Wo die Demo läuft

- **Live heißt: auf dem Rechner von Bernhard.** Stufe 1 ist der lokale Stand mit dem Modell Azure.
- **Die öffentliche Demo läuft im Testmodus.** Dort zeigt der Kopf „Modell mock · mock“, und `/uc3` zeigt den Leerzustand. Sie ist keine Live-Demo des Agenten. Wird sie gezeigt, sagt Bernhard vorher „Testmodus“ an.
- **Bedingung für die Web-Oberfläche:** Die Seite `/uc3` liegt noch in MR !51. Nur wenn sie bis zum Freeze auf main ist, wird die Web-Oberfläche gezeigt. Sonst ist der CLI-Weg (Stufe 2) der Standard. Der Stand wird um 06:45 geprüft und in `probe.md` eingetragen.

## Schritte

### Überleitung (5:00–5:15)

- Sagt Bernhard: „Bisher waren das Folien. Jetzt zeige ich denselben Ablauf am echten Stand, auf meinem Rechner.“
- Jury sieht: Folie 8 „Jetzt live“, danach der Wechsel zum Browser.

### D1 Lauf 2025-03 und Qualitätsbericht (5:15–6:20)

- CLI-Weg (Standard): `uv run uc3 lauf --lieferung 2025-03`, danach `uv run uc3 laeufe`. Bericht: `abgabe/qualitaetsberichte/2025-03.md`.
- Klickweg, nur wenn `/uc3` (MR !51) bis zum Freeze auf main ist: Web-UI, Seite `/uc3`, dann „Lauf-Detail 2025-03“. Dort steht der Qualitätsbericht des Monats.
- Sagt Bernhard: „März 2025 hat zwei Fehler auf einmal. 1.663 Zeilen sind doppelt (F8), und die freien Dienstverträge fehlen ganz, 1.492 Verhältnisse (F9). Das Programm hält den Monat an und markiert ihn als vorläufig.“
- Jury muss sehen:
  - Auffälligkeit Volldubletten mit 1.663 Zeilen (F8), Einstufung sichtbar.
  - Auffälligkeit fehlende freie Dienstverträge mit 1.492 Verhältnissen (F9), Einstufung sichtbar.
  - Status des Monats: angehalten und vorläufig.
  - Nichts wurde gelöscht. Die Rohdaten bleiben.

### D2 Änderung per Sprache (6:20–7:40)

Geübter Auftrag: Plausibilitätsgrenze für das Alter von 110 auf 100 senken. Das ändert keine Zahlen (F5). So zeigt die Demo Diff und Freigabe ohne Risiko.

Ablauf mit den Befehlen (im Terminal, in der Web-UI nur bei `/uc3` auf main, gleiche Schritte):

1. 6:20 Auftrag stellen. Der Agent erzeugt nur einen Vorschlag und ändert nichts:
   `uv run uc3 agent "Setze die Plausibilitätsgrenze für das Alter von 110 auf 100" --probe 2024-08`
2. 6:50 Vorschlag ansehen:
   `uv run uc3 vorschlag zeigen <id>`
3. 7:10 Freigeben mit Vor- und Nachnamen:
   `uv run uc3 freigabe <id> --name "Bernhard Götzendorfer"`
4. 7:25 Protokoll zeigen:
   `uv run uc3 protokoll --zeigen`

- Sagt Bernhard (bei 1): „Ich sage der Maschine in einem Satz, was sich ändern soll. Sie schreibt nur einen Vorschlag.“
- Sagt Bernhard (bei 2): „Hier ist der Unterschied in der Regel. Und hier die Zahlen vorher und nachher. Sie sind gleich, weil zwischen 78 und 116 Jahren kein Fall liegt (F5).“
- Sagt Bernhard (bei 3 und 4): „Erst mit meinem Namen wird es wirksam. Der gespeicherte Änderungsschritt im Repo trägt den Vermerk Freigegeben-von. Das Protokoll hält es fest.“
- Jury muss sehen:
  - Regel-Diff: `max_plausibel` von 110 auf 100 (F5).
  - Zahlen vorher und nachher, gleich.
  - Freigabe mit Vor- und Nachname, „Team“ wird abgelehnt (`shared/py/plattform/freigabe.py`, `pruefe_name`).
  - Gespeicherter Änderungsschritt (Commit) mit dem Vermerk `Freigegeben-von`.
  - Eintrag im Protokoll.
- Vorher prüft Bernhard: Er nimmt die Kennung `<id>` aus der Ausgabe von Schritt 1. Nie eine Kennung von gestern übernehmen.
- Üben nur bis zur Ablehnung: `uv run uc3 vorschlag zeigen <id>`, dann `uv run uc3 ablehnen <id> --name "Bernhard Götzendorfer" --begruendung "Übung vor der Jury"`. Vor der Jury nie `freigabe` üben. Es aktiviert den Regelsatz v2 und committet. Einen Reset-Befehl gibt es nicht (`uc3/statagent/cli.py`). Wäre v2 schon auf 100 gesetzt, träfe die Live-Änderung auf einen Stand, der nicht mehr von 110 ausgeht.
- Modell: D2 braucht das echte Modell (Azure). Mit `mock` gibt es keinen Vorschlag.

### D3 Datenanfrage Männer und Frauen je Bundesland (7:40–8:20)

- Klickweg oder Befehl: Der Befehl `frage` ist noch nicht fertig (Issue #74). Bis dahin läuft die Anfrage als SQL mit `psql` gegen die UC3-Datenbank. Die fertige Abfrage steht in `docs/praesentation/fragenkatalog.md`, Teil A2.
- Sagt Bernhard: „Die Frage lautet: Männer und Frauen je Bundesland. Die SQL sehen Sie hier vollständig. Die Summe stimmt mit dem Beispielbericht überein.“
- Jury muss sehen:
  - Die SQL im Klartext.
  - Die Tabelle je Bundesland mit Männern und Frauen.
  - Zur Kontrolle für Bernhard (Stand 08/2024): gesamt 392.236, Männer 211.603, Frauen 180.633 (F14). Wien 90.799, Niederösterreich 64.505 (F14).
- Die Zahlen oben gelten für den Stichtag 31.08.2024. Läuft die Anfrage auf einem anderen Monat, steht der Monat sichtbar in der SQL.

### UC-Wechsel (8:20–8:30)

- Klickweg (nur in der Web-Oberfläche): App-Header, UC-Wechsel einmal öffnen und zurück zu UC3. Im CLI-Weg zeigt Bernhard nur den Satz und nennt, dass die anderen Anwendungsfälle auf demselben Kern entstehen.
- Sagt Bernhard: „Derselbe Kern trägt auch die anderen Räume. Dazu gleich mehr.“
- Jury muss sehen: den Umschalter mit UC1, UC2, UC3. Mehr nicht.

### Optional D4 Gemeinsamer Einstieg (UC4)

- Eine Frage läuft durch UC3, UC2 und UC1: „Wie viele Menschen arbeiten in Wien im Gesundheits- und Sozialwesen (März 2025), und was heißt das für Wartezeiten beim Arzt?“ UC3 liefert die Zahl für ÖNACE-2025-Abschnitt R (Gesundheits- und Sozialwesen), Wien, 2025-03 mit Beleg, UC2 die Abwägung, UC1 die Erklärung in einfacher Sprache.
- Die Frage stammt aus dem Abgleich der Review-Bank. Die Wartezeiten selbst kann UC3 nicht beantworten, es kennt nur Beschäftigte. Online antworten die Modelle bis #100 im Testmodus (mock); das wird angesagt.
- Nur wenn `/uc4` bis zum Freeze grün ist. Sonst entfällt D4 ohne Ersatz.
- **Entscheid am Fr 06:45.** Wer entscheidet: Lead mit Bernhard. Ergebnis in `probe.md` eintragen.
- D4 hat keine eigene Zeit. Wird D4 gezeigt, kürzt Bernhard den UC-Wechsel auf einen Satz und geht von dort in `/uc4`. Die Gesamtdauer von 10:00 darf dadurch nicht steigen. Sonst entfällt D4.

## Rückfallstufen

Die Stufen brauchen keinen Umbau. Die Befehle bleiben gleich.

| Stufe | Auslöser | Wechsel (höchstens 30 s) | Was Bernhard sagt |
|---|---|---|---|
| 1 Web-UI | Nur wenn `/uc3` (MR !51) bis zum Freeze auf main ist: lokaler Stand auf dem Rechner von Bernhard, Modell Azure. Ist die öffentliche Demo im Bild, läuft sie im Testmodus. | keiner | nichts Besonderes. Bei der öffentlichen Demo vorher: „Das ist der Testmodus.“ |
| 2 CLI im Terminal | Standard, solange `/uc3` nicht auf main ist. Auch: Web-UI lädt nicht, Netz fällt aus oder Seite zeigt Fehler. Auch: Live-Modell antwortet nicht (dann nur für D1 und D3). | Terminal-Fenster nach vorn holen. Dieselben Befehle wie in D1 bis D3. Bei fehlendem Modell vorher `LLM_PROVIDER=mock` setzen: Damit laufen D1 und D3, denn sie brauchen kein Modell. D2 geht ohne Modell auf die Aufzeichnung (Stufe 3). | „Die Oberfläche macht gerade Pause. Ich zeige dasselbe im Terminal.“ Bei fehlendem Modell zusätzlich: „Das Modell ist nicht erreichbar. Lauf und Datenanfrage brauchen keins (F16). Die Änderung zeige ich als Aufzeichnung.“ |
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
- [ ] Ist `/uc3` (MR !51) auf main: Browser-Tabs vorbereitet (`/uc3` mit Lauf-Detail 2025-03, Protokoll, bei D4 zusätzlich `/uc4`). Sonst: Terminal ist der Standard.
- [ ] Terminal mit großer Schrift, aus 3 Metern lesbar.
- [ ] Modell-Schalter geprüft: `LLM_PROVIDER` auf den Standard. Mit `mock` laufen nur D1 und D3.
- [ ] Video lokal geöffnet und startklar (Stufe 3).
- [ ] Netz aus getestet: Stufe 2 (D1 und D3) und Stufe 3 laufen ohne Netz. D2 braucht das Modell.
- [ ] Keine Secrets sichtbar. Umgebungsvariablen nicht im Terminal anzeigen, keine `.env.local` öffnen.
- [ ] Zahlen auf den Folien gegen `abgabe/` abgeglichen.
- [ ] Übungsauftrag aus D2 nur bis `vorschlag zeigen <id>` gelaufen, dann `ablehnen <id>` mit der Begründung „Übung vor der Jury“. Nie `freigabe` geübt.
- [ ] Entscheid D4 um 06:45 getroffen und in `probe.md` eingetragen.
- [ ] Freeze um 07:00 (Europe/Vienna) bestätigt. Danach keine Änderung mehr.
