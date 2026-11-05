# Demo-Drehbuch (nach Szene 10, 5:05–9:30)

Gehört zu GitLab #90, Epic #26. Zahlen tragen ihre Kennung aus dem Belegregister (F1 bis F25).

Feature-Stopp und Freeze für Code, Präsentation und Demo: **Fr 06.11.2026 07:00 (Europe/Vienna)**. Nach dem Freeze ändert niemand mehr etwas. Die Demo läuft auf dem Stand vom Freeze.

Folge: Erst die Präsentation (Szene 1 bis 10, 0:00–5:05), dann die Demo (5:05–9:30). Danach folgen Live-Änderung und Datenanfragen der Jury bis etwa 15:00 (Fragenkatalog Teil A und B). Die Szenen zeigen das Zielbild. Der Tagesstand steht nur im Fragenkatalog.

## Überblick

| Zeit | Schritt | Dauer |
|---|---|---|
| 5:05–6:15 | D1 Lauf und Qualitätsbericht (2025-10 angehalten, alternativ 2025-03) | 1:10 |
| 6:15–7:45 | D2 Änderung per Sprache: Rückblick auf die echte Freigabe von Auftrag 1 | 1:30 |
| 7:45–9:00 | D3 Datenanfragen der Jury-Aufgabe | 1:15 |
| 9:00–9:30 | D4 Gemeinsamer Einstieg: die Wien-Frage in `/uc4` | 0:30 |
| 9:30 | Ende der Demo, danach Fragen der Jury | |

Die Demo dauert 4:25 (5:05–9:30). Eine eigene Überleitung gibt es nicht. Szene 10 endet mit der Einladung „Nennen Sie mir eine Regel, die ich jetzt ändern soll.“ Bernhard wechselt danach sofort zum Terminal oder Browser.

## Wo die Demo läuft

- **Live heißt: auf dem Rechner von Bernhard.** Stufe 1 ist der lokale Stand mit dem Modell Azure.
- **Die öffentliche Demo läuft im Testmodus.** Dort zeigt der Kopf „Modell mock · mock“, und `/uc3` zeigt den Leerzustand. Sie ist keine Live-Demo des Agenten. Wird sie gezeigt, sagt Bernhard vorher „Testmodus“ an.
- **Web-Oberfläche:** `/uc3` (MR !51) und `uc3 frage` mit `/uc3/fragen` (MR !61) sind seit dem 05.11.2026 auf main. Die Web-Oberfläche ist damit Stufe 1, sofern sie auf dem Rechner von Bernhard Daten zeigt. Der Stand wird um 06:45 geprüft und in `probe.md` eingetragen.

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

### D2 Änderung per Sprache: Rückblick auf eine echte Freigabe (6:15–7:45)

**Stand der Probe (05.11.2026 17:56 bis 17:58, Azure, Kopie der Abgabe-DB):** Keine Live-Änderung ging durch. B2 (Geburtsmonat 13, drei Versuche), B3 und B1 endeten mit „Kein Vorschlag“ (falsche Rolle oder falscher Parameter) oder mit dem Abbruch der Probe bei Prüfregel P08. Der Fehler liegt bei b-uc3-84. Deshalb zeigt D2 nur, was geprobt ist: die echte Freigabe von Auftrag 1.

**Auftrag 1 ist abgegeben.** „Dienstvertrag und freien Dienstvertrag zusammen ausweisen“ hat Bernhard am 5. November 2026 freigegeben (Vorschlag 24, Regelsatz v2, F19, F26). Er steckt in der Abgabe. Ihn live noch einmal auszuführen hieße, eine schon gültige Änderung zu wiederholen; einen Reset gibt es nicht.

Ablauf (im Browser auf `/uc3/freigaben`, Reiter „Erledigt“, gleich im Terminal):

1. 6:15 Auftrag zeigen: die Anweisung von Vorschlag 24 im Wortlaut.
2. 6:40 Vorschlag zeigen: `uv run uc3 vorschlag zeigen 24`. Regel-Unterschied und Zahlen vorher und nachher.
3. 7:10 Freigabe und Protokoll: `uv run uc3 protokoll --zeigen`, Abschnitt 2 und 3.

- Sagt Bernhard (bei 1): „Das war ein Auftrag der Aufgabe. Ich habe ihn in einem Satz an die Maschine gegeben. Sie schrieb nur einen Vorschlag.“
- Sagt Bernhard (bei 2): „Hier ist der Unterschied in der Regel. Und hier die Zahlen vorher und nachher. Der Gesamtbestand bleibt bei 392.236. Die Kategorien verschieben sich, zum Beispiel Angestellte von 0 auf 236.961.“
- Sagt Bernhard (bei 3): „Erst mit meinem Namen wurde es wirksam. Das Protokoll hält fest, wer, wann und was.“
- Jury muss sehen:
  - Regel-Diff von Vorschlag 24 (Regel `R6_beschaeftigungskategorie`).
  - Zahlen vorher und nachher: Gesamt gleich, Kategorien verschoben (F19).
  - Freigabe mit Vor- und Nachname im Protokoll (F26). „Team“ wird abgelehnt (`shared/py/plattform/freigabe.py`, `pruefe_name`).
- Die Uhrzeit liest Bernhard nicht vor: Das Protokoll zeigt sie ohne Zeitzone (15:53 statt 16:53 Wien), Hinweis an b-uc3-84.

**Live-Änderung B2, sobald !50 auf main ist.** Mit dem Stand von !50 (feat/uc3-betrieb, 4cbcf47, behebt Rolle und Abbruch bei P08) hat E5 B2 am 05.11.2026 18:20 bis 18:25 dreimal hintereinander gegen `statistik_probe` geprobt: drei gültige Vorschläge (34, 35, 36), Rolle datenmanagement, `R5_alter.geburtsmonat_13` von `ersatz:07-01` auf `jahresdifferenz`. `vorschlag zeigen 34` zeigt Regel-Diff und Probe 2025-03 mit gleichem Gesamtbestand. Ist !50 beim Freeze auf main, kommt nach dem Rückblick (ab 6:50) live dazu:

`uv run uc3 agent "Rechne bei Geburtsmonat 13 nur mit der Differenz der Jahre (Jahresdifferenz) statt mit dem 1. Juli." --probe 2025-03`, dann `uv run uc3 vorschlag zeigen <id>` und `uv run uc3 freigabe <id> --name "Bernhard Götzendorfer"`.

Kommt „Kein Vorschlag“, sendet Bernhard denselben Satz einmal neu. Kommt er wieder, bleibt es beim Rückblick.

Bis dahin gilt: Nennt die Jury nach Szene 10 eine Regel, sagt Bernhard: „Das zeige ich Ihnen an einer Änderung, die ich heute schon freigegeben habe“ und bleibt bei Vorschlag 24.

- Nie `freigabe` üben: Es committet ins Repo, einen Reset gibt es nicht. Proben nur gegen `statistik_probe`, nie gegen die Abgabe-DB `statistik`, denn auch ein abgelehnter Vorschlag steht danach im Protokoll der Abgabe.
- Entscheid in `probe.md` (Fr 06:45): Rückblick allein oder Rückblick plus B2 live.

### D3 Datenanfragen (7:45–9:00)

Drei Anfragen der Aufgabenstellung, je etwa 25 Sekunden: Zeitreihe, Männer und Frauen je Bundesland, Fluktuation je Branche. Alle drei stammen aus der Liste der acht geprüften Fragen unten.

**Nur geprüfte Fragen.** Vorgeführt werden ausschließlich die acht Fragen aus der Tabelle, wörtlich so getippt. Jede ist gegen eigenes SQL und das unabhängige Orakel nachgerechnet (Prüfung lead-session-orchestrator-bb, 05.11.2026 17:15 bis 17:19, #74). Freie Fragen der Jury tippt Bernhard nicht ein, solange der Folge-MR von bb („nie still falsch“) nicht auf main ist. Dann bietet er eine Frage aus der Liste an. Der Stand wird um 06:45 geprüft und in `probe.md` eingetragen.

- Klickweg: Seite `/uc3/fragen`, Frage ins Feld tippen. Die Antwort zeigt die Zahl, die Abfrage und die Definition.
- Terminal (Stufe 2): `uv run uc3 frage "…"` mit demselben Text.
- Letzter Rückfall: SQL mit `psql` aus dem Fragenkatalog, Teil A1 bis A3.
- Sagt Bernhard: „Drei Fragen an die Daten. Das Programm rechnet die Antwort ohne KI und zeigt Ihnen die Abfrage dazu.“
- Bernhard sagt „Beschäftigungsverhältnisse“, auch wenn die getippte Frage „Beschäftigte“ sagt. Gezählt werden Verhältnisse, nicht Personen.

| Nr. | Frage, wörtlich so tippen | Sollzahl für Bernhard | Kennung | In D3 |
|---|---|---|---|---|
| 1 | „Zeigen Sie mir die Zeitreihe der Beschäftigten, jeweils zum Monatsletzten.“ | 24 Werte, erster Wert August 2024 392.236, letzter Wert Juli 2026 399.027 | F14, F21 | ja |
| 2 | „Wie viele Männer und Frauen sind im August 2024 je Bundesland beschäftigt?“ | Männer 211.603, Frauen 180.633 | F14 | ja |
| 3 | „Männer und Frauen im Juli 2026“ | Männer 213.129, Frauen 185.898 | F22 | Reserve |
| 4 | „Wie hoch ist die Fluktuation je Wirtschaftsbereich im Oktober 2024?“ | 3,42 % (12.215 Zugänge, 14.557 Abgänge, Bestand 391.033) | F23 | ja |
| 5 | „Wie viele Beschäftigte gab es im März 2025 in Wien im Gesundheits- und Sozialwesen?“ | 7.498, vorläufig | F18 | Reserve, sonst D4 |
| 6 | „Beschäftigte nach Branche im Juli 2026“ | 23 Werte, Summe 399.027, Bau 28.548 | F24 | Reserve |
| 7 | „Was ist ÖNACE R?“ | ÖNACE 2025: Gesundheits- und Sozialwesen; ÖNACE 2008: Kunst, Unterhaltung und Erholung | F13 | Reserve |
| 8 | „Zeitreihe Bau 2025“ | Werte 23.809 bis 24.679 | F25 | Reserve |

Gegenprobe für eine ehrliche Absage, nur wenn Zeit bleibt: „Entwicklung im Bau seit August 2024“. Das Programm sagt ab, weil die Branchen ab 2025 nach ÖNACE 2025 gezählt werden (F13). Sagt Bernhard: „Hier sagt das Programm ehrlich nein, statt zwei verschiedene Einteilungen zu vergleichen.“

**Nicht vorführen**, solange der Folge-MR von bb fehlt. Diese Fragen liefern heute eine Antwort auf eine andere Frage ohne Hinweis:

- Branchen in Umgangssprache, etwa „Gastronomie“, „Gesundheitswesen“ oder „Handel“.
- Zwei Werte eines Merkmals, etwa „Wien und Tirol“ oder „Arbeiter und Angestellte“.
- Alter, etwa „unter 25“ oder „Durchschnittsalter“, und „freie Dienstverträge“.
- Zeiträume wie „von März bis Juni 2025“.
- Fluktuation mit Filter („in Wien“), für August 2024 oder mit „am höchsten“.
- Fragen nach einer einzelnen Person.

Fragt die Jury so etwas, sagt Bernhard: „Das zeige ich Ihnen mit einer Abfrage aus dem Katalog“ und nimmt die passende SQL aus Teil A oder eine Frage aus der Tabelle.

- Jury muss sehen:
  - Die Zahl, die Abfrage und die Definition auf dem Bildschirm.
  - Frage 1: erste Zeile 392.236 (F14). Der Oktober 2025 steht als vorläufig (F11).
  - Frage 2: Männer 211.603, Frauen 180.633, je Bundesland gegliedert (F14).
  - Frage 4: Fluktuation 3,42 % mit Zugängen und Abgängen (F23). Nie zwei Monate mit verschiedener ÖNACE-Version Abschnitt gegen Abschnitt vergleichen (F13).
- Weicht eine Zahl von der Sollzahl ab, sagt Bernhard nichts dazu und wechselt auf die SQL aus dem Fragenkatalog. Die Abweichung kommt danach ins Probe-Protokoll.

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
- [ ] D3: Die acht geprüften Fragen auf `/uc3/fragen` und mit `uv run uc3 frage "…"` geprobt, jede Zahl gegen die Sollzahl der Tabelle. Folge-MR von bb auf main? Wenn nein, keine freien Fragen. SQL A1 bis A3 als Rückfall bereit, `<regelstand>` eingesetzt.
- [ ] D4: Sollwert 7.498 (F18) gegen die Abfrage im Belegregister geprüft. Testmodus-Ansage bereit.
- [ ] D2: `uv run uc3 vorschlag zeigen 24` und `uv run uc3 protokoll --zeigen` laufen auf dem Vortragsrechner. B2 nur, wenn es nach dem Fix von b-uc3-84 dreimal gegen `statistik_probe` geklappt hat. Nie `freigabe` geübt.
- [ ] Protokolleintrag der Freigabe von Auftrag 1 (05.11.2026 16:54) gefunden, Fenster für den Rückblick bereit.
- [ ] Entscheid D4 um 06:45 getroffen und in `probe.md` eingetragen.
- [ ] Freeze um 07:00 (Europe/Vienna) bestätigt. Danach keine Änderung mehr.
