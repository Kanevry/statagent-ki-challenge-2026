# Demo-Drehbuch, Fachjury (Pfad A)

Gehört zu GitLab #90, Epic #26. Zahlen tragen ihre Kennung aus dem Belegregister (F1 bis F29). Der Ablauf der ganzen 15 bis 20 Minuten steht in `uc3-jury.md`.

Feature-Stopp und Freeze für Code, Präsentation und Demo: **Fr 06.11.2026 07:00 (Europe/Vienna)**. Nach dem Freeze ändert niemand mehr etwas. Die Demo läuft auf dem Stand vom Freeze.

Folge: Am Anfang keine Folien, Laptop offen auf `/uc3`. Das Management (Pfad B) sieht Folien, dort ist die Demo nur ein Zusatz.

## Überblick

| Zeit | Schritt | Dauer |
|---|---|---|
| 0:00–3:00 | D1 Lösung, Lauf und Qualitätsbericht Oktober 2025 | 3:00 |
| 3:00–4:00 | D1 Beleg: Bericht August 2024, 2.880 von 2.880 | 1:00 |
| 4:00–5:00 | Annahme im Detail: Folie 8, Geburtsmonat 13 | 1:00 |
| 5:00–6:00 | D2 Teil 1: Rückblick auf die drei Aufträge | 1:00 |
| 6:00–9:30 | D2 Teil 2: die Änderung der Jury, live | 3:30 |
| 9:30–12:00 | D3 Datenanfragen der Jury-Aufgabe | 2:30 |
| 12:00–13:00 | D3 Zusatz: ehrliche Absage | 1:00 |
| 13:00–14:00 | D4 Gemeinsamer Einstieg: die Wien-Frage in `/uc4`, nur wenn sie um 06:45 echt läuft | 1:00 |
| bis 20:00 | Fragen der Jury | |

Die Zeiten sind Richtwerte, gemessen wird in der Probe. Wichtig ist die Reihenfolge.

## Wo die Demo läuft

- **Online über Hotspot** (Owner 05.11.2026). Vorführ-Adresse mit Passwort, Modell Azure. Einen Lauf ohne Netz gibt es nicht. Die Adresse meldet die Lane Vorführung, sie steht nicht im Repo.
- **Datenbank der Vorführung:** eine eigene Kopie der Abgabe-Datenbank, nie `statistik` selbst, auch nach 09:00 nicht. Die Abgabezahlen sind auf der eigenen Datenbank gerechnet, online läuft nur die Vorführung. So bleibt die Abgabe jederzeit nachrechenbar.
- **Klickwege für D1 und D2:** Beide laufen im Browser auf der Vorführ-Adresse, Seite `/uc3/auftrag` (`docs/betrieb/vorfuehrung.md`). Die Knöpfe stehen hier wie im Code auf main, der Durchlauf auf dem aktuellen Stand kommt in der Probe. Der Weg im Terminal bleibt die Reserve.
- **Was die Zahlen im D2 zeigen:** D1 läuft vor D2. Die Zahlen nachher kommen aus der Probe auf dem Vorschlag, ein Monat auf dem neuen Regelsatz wird live nicht gerechnet. Offene Vorschläge nacheinander ablehnen, zwei können auf denselben neuen Regelsatz zielen (#169).
- **Zwischen zwei Durchläufen:** Zurücksetzen nach `docs/betrieb/vorfuehrung.md`, damit die Proben nicht in der Vorführung stehen.

## Schritte

### D1 Lösung, Lauf und Qualitätsbericht (0:00–4:00)

Standard ist Oktober 2025. Alternative ist März 2025. Bernhard wählt vorab einen der beiden und trägt die Wahl in `probe.md` ein.

- Sagt Bernhard (Einstieg auf `/uc3`): „24 Monatslieferungen, eine Zahl pro Monat. Zwei Monate hat das Programm angehalten, statt sie zu veröffentlichen. Das zeige ich Ihnen zuerst.“

- Reserve im Terminal: `uv run uc3 lauf --lieferung 2025-10`, danach `uv run uc3 laeufe`. Bericht: `abgabe/qualitaetsberichte/2025-10.md`. Alternative: `--lieferung 2025-03` und `abgabe/qualitaetsberichte/2025-03.md`.
- Klickweg: `/uc3/auftrag`, unten „Einen Monat rechnen“, Monat wählen, dann „Monat und Qualitätsbericht ansehen“. Gemessen für Oktober 2025: 92,9 s und 102,0 s (Lane Vorführung).
- Sagt Bernhard (Oktober 2025): „Es kommen 313.154 gegen 394.200 im Vormonat (F17). 78.949 Verhältnisse fehlen in der Lieferung (F11). Das Programm hält den Monat an und markiert ihn als vorläufig.“
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
- Beleg danach (3:00–4:00): Bericht August 2024 öffnen. Sagt Bernhard: „Ihr Beispielbericht August 2024, 2.880 Zahlen. Wir rechnen ihn komplett nach: 2.880 stimmen (F1). Für die 23 anderen Monate wachen 24 Prüfregeln (F15).“
- Hinweis zu 81.046 und 78.949: Die Differenz der Bestände ist 394.200 minus 313.154, also 81.046 (F17). Die Zahl 78.949 zählt Verhältnisse, die in der Lieferung gar nicht vorkommen (F11). Das sind zwei verschiedene Messungen. Bernhard nennt in der Demo beide nur mit ihrer Bedeutung.

### Annahme im Detail (4:00–5:00)

Folie 8 öffnen (`/praesentation?folie=8`, Tab liegt bereit), Stichpunkte: Skript-Abschnitt „Eine Annahme im Detail“. Die Aufgabe verlangt diesen Teil ausdrücklich, er bleibt auch bei Zeitnot.

### D2 Änderung per Sprache (5:00–9:30)

Bewertet in Bereich 5 („Live-Änderung per Sprache gelingt“, 20 Punkte). „Per Sprache“ heißt: Die Anweisung ist ein Satz in Alltagssprache, den Bernhard tippt (Owner-Wort 05.11.2026 19:3x).

**Datenbank:** Die ganze Demo läuft gegen die Kopie `statistik_vorfuehrung` (`UC3_DATABASE_URL` auf die Kopie), nie gegen `statistik`. Die Freigabe schreibt einen Commit; deshalb läuft D2 auf einem eigenen Demo-Branch im Checkout des Vortragsrechners, der Commit wird nie gepusht. Geprobt wird vorher nur auf `statistik_probe`.

**Demo-Branch je Lauf frisch ab main:** Für jeden Lauf, Probe wie Vorführung, legt Bernhard einen neuen Demo-Branch ab main an (`git switch -c demo/<uhrzeit> origin/main`) und nimmt nie einen Branch aus einer früheren Probe. Grund: Bei gleicher Vorschlags-ID kann die Freigabe sonst auf einen Commit aus der Probe zeigen.

**Teil 1, Rückblick (5:00–6:00):** Die drei Änderungsaufträge der Aufgabe sind umgesetzt und mit Namen freigegeben (Vorschläge 24, 25, 26).

1. `uv run uc3 vorschlag zeigen 24`: Regel-Unterschied und Zahlen vorher und nachher von Auftrag 1.
2. `uv run uc3 protokoll --zeigen`, Abschnitt 2: alle drei Aufträge mit Status „freigegeben“ und Name.

- Sagt Bernhard (FAQ Frage 11): „Die drei Aufträge der Aufgabe habe ich in Sätzen gestellt, die Agenten schrieben Vorschläge. Die Freigaben hat in meinem Auftrag eine KI-Sitzung eingegeben, ich habe sie um 18:22 mit meinem Namen bestätigt. Das steht offen im Protokoll.“
- Sagt Bernhard (bei 1): „Der Gesamtbestand bleibt bei 392.236. Die Kategorien verschieben sich, zum Beispiel Angestellte von 0 auf 236.961.“

**Teil 2, live per Sprache (6:00–9:30):** Laut Aufgabenstellung gibt die Jury eine kleine, unbekannte Änderung vor. Bernhard fragt: „Nennen Sie mir eine Regel, die ich jetzt ändern soll.“ Er wiederholt den Wunsch der Jury in einem Satz und tippt diesen Satz. Die vier geübten Änderungen im Fragenkatalog Teil B decken die naheliegenden Wünsche ab (Altersgrenze, Geburtsmonat 13, Schwelle Bestandsrückgang, Spaltentausch). Nennt die Jury nichts, nimmt Bernhard den Standard-Satz unten.

**Standard-Satz:** „Beamte zählen nicht mehr mit“, Monat Juli 2026. Die Seite zeigt: Gesamt 407.604 → 395.315, „Gesamt ändert sich um −12.289“, Beamte 12.289 → 0, Angestellte und Arbeiter gleich. Der Vorschlag dauert rund 3 Minuten: gemessen 06.11.2026 02:36 auf dem Instanz-Stand 1a4e0b8, 2 min 55 s, nur bis zum Vorschlag. Die Lane Vorführung maß 2 min 45 s, die UI-Regie 2 min 34 s. Rücknahme: neuer Auftrag „Nimm Vorschlag <n> zurück“, +12.289, rund 1,5 Minuten; bis #168 nennt die Seite dabei „Keine Regeländerung hinterlegt“. Ausschluss und Rücknahme sind seit !150 auf main (06.11.2026 02:06). Entscheid um 06:45.

**Knapp:** Von den 3:30 für Teil 2 gehen rund 3 Minuten ans Warten. In der Wartezeit sagt Bernhard: „Das Programm rechnet den Monat jetzt zweimal, nach der alten und nach der neuen Regel. Geändert ist noch nichts.“

1. `/uc3/auftrag`: Satz tippen, Monat für die Zahlen wählen, „Vorschlag schreiben lassen“. Im Satz den Zielwert nennen. Bei einer Änderung an Geburtsmonat 13 Juni 2026 wählen. Reserve im Terminal: `uv run uc3 agent "<Satz>" --probe JJJJ-MM`, zum Beispiel B2: `uv run uc3 agent "Rechne bei Geburtsmonat 13 nur mit der Differenz der Jahre (Jahresdifferenz) statt mit dem 1. Juli." --probe 2026-06`. Der Agent schreibt einen Vorschlag. Seit !150 stimmt die Probe auch in 2025-03 und 2025-10 (396.762 und 397.514, gemessen von der UC3-Lane). Die Seite bietet alle 24 Monate an, auch diese zwei (gesehen 06.11.2026 02:36).
2. „Vorher und nachher ansehen, dann entscheiden“: Regel-Unterschied und Zahlen vorher und nachher. Reserve: `uv run uc3 vorschlag zeigen <id>`. Bei B2: `R5_alter`, `geburtsmonat_13` von `ersatz:07-01` auf `jahresdifferenz`.
3. Vor- und Nachnamen eintragen, „Ja, so rechnen wir ab jetzt“. Die Seite nennt den Commit. Reserve: `uv run uc3 freigabe <id> --name "Bernhard Götzendorfer"`, dann `uv run uc3 protokoll --zeigen`.

- Sagt Bernhard (bei 1): „Ich sage dem Agenten in einem Satz, was er ändern soll.“
- Sagt Bernhard (bei 2): „Hier ist, was sich ändern würde, vorher und nachher. Wirksam wird es erst mit meinem Namen.“ Bei B2 zusätzlich: „Der Gesamtbestand bleibt gleich. Die Regel ändert nur das Alter, deshalb steht die Wirkung unter der Tabelle, bei den Altersgruppen.“
- Rückfall Agent: Kommt „Kein Vorschlag“, sendet Bernhard den Satz einmal neu und nennt den Zielwert ausdrücklich. Kommt er wieder, sagt er „Das zeige ich Ihnen mit einer geübten Änderung“ und nimmt den Standard-Satz. Eine Rückfrage statt eines Vorschlags ist möglich, das ist nicht gemessen. Scheitert auch das, bleibt es beim Rückblick aus Teil 1.
- Prüfschwellen je Bundesland nicht vorführen: „Schon angehalten, wenn in einem Bundesland mehr als 10 % fehlen“ wurde in der Probe zu einem falschen Vorschlag (`docs/plan/uc3/live-vorfuehrung.md`). Der Regel-Unterschied zeigt das vor der Freigabe, dann ablehnen.
- Will die Jury etwas, das eine neue Regel oder Code braucht (keine Änderung eines Parameters), sagt Bernhard: „Das wäre eine neue Regel. Der Agent schlägt sie vor, freigeben würde ich sie erst nach einer Probe.“ und nimmt den Standard-Satz.
- Azure antwortet nicht: Hotspot wechseln (10 s), Satz noch einmal. Geht es dann nicht, reicht Teil 1 als Beleg, und Bernhard sagt das offen.

**Jury muss sehen:**
- Die Anweisung als Satz in Alltagssprache.
- Regel-Diff und Zahlen vorher und nachher (F19 für Auftrag 1, live für den Standard-Satz).
- Freigabe mit Vor- und Nachname, „Team“ wird abgelehnt (`shared/py/plattform/freigabe.py`, `pruefe_name`).
- Eintrag im Protokoll (F26).

**Stand der Proben:** 05.11.2026 17:56 bis 17:58 auf main 321a7176: B1, B2, B3 ohne Vorschlag oder abgebrochen. 18:20 bis 18:25 mit dem Code von !50: B2 dreimal von drei gültig. Das war mit 2025-03. Am selben Abend maß die UC3-Lane dort 396.762 → 395.292 (−1.470) bei einer reinen Altersänderung: In der Probe fehlten die Fortschreibungen von 2025-03 und 2025-10, seit !150 ist das behoben, die Abgabe war nicht betroffen. Mit 2026-06 bleibt die Gesamtzahl bei 403.301 (einmal gemessen von der UC3-Lane, 22:40, Commit d888e09, bis zum Vorschlag). Im Browser bleibt die Tabelle dort gleich, darunter nennt die Seite die Altersgruppen (seit !239). Juli bis Dezember zeigen bei B2 keinen Unterschied, das ist fachlich richtig.

- Nie `freigabe` üben: Es committet ins Repo, einen Reset gibt es nicht. Proben nur gegen `statistik_probe`.
- Entscheid in `probe.md` (Fr 06:45): Teil 1 allein oder Teil 1 und Teil 2.

### D3 Datenanfragen (9:30–12:00)

Drei Anfragen der Aufgabenstellung, je etwa 25 Sekunden: Zeitreihe, Männer und Frauen je Bundesland, Fluktuation je Branche. Jede Antwort abwarten, bevor die nächste Frage kommt. Alle drei stammen aus der Liste der acht geprüften Fragen unten. Reihenfolge: zuerst Männer und Frauen, dann Fluktuation, die Zeitreihe zuletzt. Sie dauerte auf der Vorführ-Adresse 16 bis 35 s (gemessen 06.11.2026 im Video und von der UI-Regie), in der Zeit erklärt Bernhard, was die Frage zeigt.

**Nur geprüfte Fragen.** Vorgeführt werden ausschließlich die acht Fragen aus der Tabelle, wörtlich so getippt. Jede ist gegen eigenes SQL und das unabhängige Orakel nachgerechnet (Prüfung im Team, 05.11.2026 17:15 bis 17:19, #74). Ob Bernhard freie Fragen der Jury eintippt, wird um 06:45 entschieden und in `probe.md` eingetragen. Sonst bietet er eine Frage aus der Liste an.

- Klickweg: Seite `/uc3/fragen`, Frage ins Feld tippen. Die Antwort zeigt die Zahl oder Tabelle und „Abfrage ansehen“. Den ganzen Antwortsatz und die Definition zeigt „Details“.
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

Zusatz (12:00–13:00), eine ehrliche Absage, nur wenn Zeit bleibt: „Wie viele Beschäftigte gab es im Juli 2026 in Wien und Tirol?“ Das Programm gibt keine Zahl und bittet, getrennt zu fragen (online gemessen 06.11.2026 00:46). Sagt Bernhard: „Hier sagt das Programm ehrlich nein, statt eine missverständliche Summe zu nennen.“ „Entwicklung im Bau seit August 2024“ sagt nicht mehr ab: Sie liefert 28.858 bis 28.548 und den Hinweis, dass der Vergleich über den Wechsel im Jänner 2025 nur ungefähr ist (05:39).

**Nicht vorführen:**

- Zahlen je Bezirk oder Gemeinde: Die Frage sagt ab, die Lieferungen haben nur das Bundesland.
- Was eine Zahl liefert, aber nicht gegen das Orakel geprüft ist: Branchen in Umgangssprache („Gastronomie“, „Gesundheitswesen“, „Handel“), „freie Dienstverträge“, Zeiträume („von März bis Juni 2025“).

**Stand der freien Fragen** (online gemessen 06.11.2026 00:46, Stand `main` `2005e01`, um 06:45 neu messen):

- Neu seit #189, Klassifikationen (06.11.2026 01:34, main `275ffb2`): „Was ist ÖNACE C 10.11-0?“, „Was ist die Gemeinde 62280?“, „Welche Bezirke hat Tirol?“ werden erklärt, die Suche steht auf `/uc3/klassifikationen`. Nicht gegen das Orakel, Texte aus den Klassifikationen.
- Neu seit !230, Regelsatz v2: „Beschäftigte im Juli 2026 nach Regelsatz v2“ 407.604, ohne „v2“ bleibt es 399.027. Fluktuation gibt es unter v2 nicht.
- Neu seit !227, Alter: „Wie viele Beschäftigte unter 25 Jahren gab es im Juli 2026?“ 41.626, in Wien 8.352. „Wie viele 30-Jährige gab es im August 2024?“ 9.017. „Beschäftigte ab 50 Jahren im Juli 2026“ 124.728. Nicht gegen das Orakel belegt, Entscheid um 06:45. Falle: „über 50“ heißt 51 Jahre und älter (115.451).
- Sagt ehrlich ab: zwei Werte eines Merkmals („Wien und Tirol“, „Arbeiter und Angestellte“), „Durchschnittsalter“, „ab 50“ ohne „Jahren“, Fluktuation mit Filter („in Wien“) oder für August 2024, Fragen nach einer einzelnen Person. Neu gemessen sind davon „Wien und Tirol“, „Durchschnittsalter“ und „ab 50“, der Rest stammt vom Stand `fd936b3`.
- Holpert: „Welche Branche hat die höchste Fluktuation“ sagt ab, aber mit „Das Wort ‚hat‘ kenne ich nicht“.

Fragt die Jury so etwas, sagt Bernhard: „Das zeige ich Ihnen mit einer Abfrage aus dem Katalog“ und nimmt die passende SQL aus Teil A oder eine Frage aus der Tabelle.

- Jury muss sehen:
  - Die Zahl, die Abfrage und die Definition auf dem Bildschirm.
  - Frage 1: erste Zeile 392.236 (F14). Der Oktober 2025 steht als vorläufig (F11).
  - Frage 2: die Tabelle je Bundesland mit Summenzeile: Männer 211.603, Frauen 180.633 (F14).
  - Frage 4: Fluktuation 3,42 % mit Zugängen und Abgängen (F23). Nie zwei Monate mit verschiedener ÖNACE-Version Abschnitt gegen Abschnitt vergleichen (F13).
- Weicht eine Zahl von der Sollzahl ab, sagt Bernhard nichts dazu und wechselt auf die SQL aus dem Fragenkatalog. Die Abweichung kommt danach ins Probe-Protokoll.

### D4 Gemeinsamer Einstieg (13:00–14:00)

- Die Wien-Frage in `/uc4` mit einem Klick auf das erste Beispiel: „Wie viele Beschäftigte gab es im März 2025 in Wien im Gesundheits- und Sozialwesen?“ Sie steht wörtlich auf Folie 9.
- Sollwert für UC3: **7.498** Beschäftigungsverhältnisse (F18), Wien, ÖNACE 2025 Abschnitt R (Gesundheits- und Sozialwesen), Stichtag 31.03.2025, mit Beleg. Der Simulator sagt, was mehr oder weniger Personal für Wartezeit und Betreuung heißt, der Lotse sagt es für den nächsten Arzttermin (fester Text, an der Karte steht „Fester Text“). Dauer online 9 bis 12 s.
- **Nur die Frage vom Knopf, ohne Zusatz.** Mit „und was heißt das für Wartezeiten beim Arzt?“ stoppt die Kette bei StatAgent, ohne Zahl (online gemessen 06.11.2026 05:02). Am Vorabend lief dieselbe Frage noch über das Rechenmodell, das ist überholt.
- Was von UC1 und UC2 läuft, steht im Tagesstand des Fragenkatalogs (Teil C, „Läuft der gemeinsame Einstieg schon?“). Bernhard sagt nur, was dort steht.
- Nur wenn die Wien-Frage um 06:45 echt läuft (nicht im Testmodus). Sonst entfällt D4 ohne Ersatz.
- **Entscheid am Fr 06:45.** Wer entscheidet: Lead mit Bernhard. Ergebnis in `probe.md` eintragen.
- Sagt Bernhard: „Eine Frage, drei Antworten. Die Zahl kommt aus UC3 und trägt ihren Beleg: 7.498.“

## Rückfall

| Stufe | Auslöser | Wechsel | Was Bernhard sagt |
|---|---|---|---|
| 1 Hotspot wechseln | Seite lädt nicht, Netz hakt, Azure antwortet nicht | Zweiter Hotspot, höchstens 10 s, vorher einmal geübt | nichts Besonderes |
| 2 Terminal | Oberfläche zeigt einen Fehler | Terminal nach vorn, dieselben Schritte als Befehl. D1 und D3 brauchen kein Modell | „Die Oberfläche macht gerade Pause. Ich zeige dasselbe im Terminal.“ |
| 3 Backup-Video | Auch das Terminal geht nicht | Videoplayer mit der Datei vom USB-Stick nach vorn (`backup-video.md`) | „Das ist eine Aufzeichnung von heute früh.“ |

Regeln für alle Stufen:

- Eine Aufzeichnung wird immer als Aufzeichnung gekennzeichnet. Bernhard sagt es vor dem ersten Bild.
- Der Wechsel zählt ab dem Auslöser bis zum ersten sichtbaren Bild. Mehr als 30 Sekunden gelten in der Probe als Fehlschlag.
- D2 hat ohne Modell keinen Ersatz außer dem Rückblick in Teil 1 und der Aufzeichnung.
- Beim Wechsel nicht diskutieren, nicht entschuldigen. Ein Satz, dann weiter.

## Vorbereitungs-Checkliste Fr 06:00–07:00

Jeder Punkt wird abgehakt, sobald er geprüft ist. Uhrzeit nur aus der Uhr (`TZ=Europe/Vienna date`), nie schätzen.

- [ ] Vorführ-Adresse lädt über beide Hotspots, Passwort zur Hand. Datenbank antwortet.
- [ ] Regelsatz freigegeben: Bernhard gibt die Regeln mit seinem Namen frei (`uv run uc3 regeln freigeben --name "Bernhard Götzendorfer"`), danach `uv run uc3 lauf --alle` und `uv run uc3 berichte --alle`. Ohne diese Freigabe nennt der Bericht „Regeln ohne Freigabe“. Jeder Lauf bleibt danach vorläufig (`uc3/statagent/lauf.py`, Zeile 151 bis 152). Das ist eine Handlung des Owners, spätestens 05:30.
- [ ] Entscheid des Leads: ob und welche Monate veröffentlicht werden. Ohne diesen Entscheid zeigt die Jury vorläufige Monate. Das ist gewollt und wird nicht als Fehler erklärt.
- [ ] Läufe 2024-08 bis 2026-07 sind vorhanden (24 Lieferungen, F3). Prüfung mit `uv run uc3 laeufe`.
- [ ] Browser-Tabs vorbereitet: `/uc3`, der Monat aus D1, Bericht August 2024, Folie 8, `/uc3/freigaben`, `/uc3/fragen`, bei D4 zusätzlich `/uc4`.
- [ ] Terminal mit großer Schrift, aus 3 Metern lesbar.
- [ ] Modell-Schalter geprüft: Azure. Eine kurze Frage an den Agenten vorab, dann erst vorführen.
- [ ] Video lokal geöffnet und startklar (Stufe 3).
- [ ] Hotspot-Wechsel einmal geübt, Dauer in `probe.md`.
- [ ] Keine Secrets sichtbar. Umgebungsvariablen nicht im Terminal anzeigen, keine `.env.local` öffnen.
- [ ] Zahlen in den Szenen gegen `abgabe/` abgeglichen.
- [ ] D1: Monat gewählt (2025-10 oder 2025-03) und in `probe.md` eingetragen.
- [ ] D3: Die acht geprüften Fragen auf `/uc3/fragen` und mit `uv run uc3 frage "…"` geprobt, jede Zahl gegen die Sollzahl der Tabelle. SQL A1 bis A3 als Rückfall bereit, `<regelstand>` eingesetzt.
- [ ] D4: Sollwert 7.498 (F18) gegen die Abfrage im Belegregister geprüft. Testmodus-Ansage bereit.
- [ ] D2: `uv run uc3 vorschlag zeigen 24` und `uv run uc3 protokoll --zeigen` laufen auf dem Vortragsrechner. B2 zeigt die Wirkung nur unter der Tabelle, bei den Altersgruppen (im Browser gesehen, UI-Regie). Nie `freigabe` geübt.
- [ ] Datenbank: `UC3_DATABASE_URL` zeigt auf `statistik_vorfuehrung`, nicht auf `statistik`. Prüfung ohne Wert: Datenbankname im Kopf der App oder `uv run uc3 laeufe` liefert die 24 Läufe der Kopie. Checkout steht auf einem Demo-Branch, der für diesen Lauf frisch ab main angelegt ist.
- [ ] Protokolleintrag der Freigabe von Auftrag 1 (05.11.2026 16:54) gefunden, Fenster für den Rückblick bereit.
- [ ] Entscheid D4 um 06:45 getroffen und in `probe.md` eingetragen.
- [ ] Freeze um 07:00 (Europe/Vienna) bestätigt. Danach keine Änderung mehr.
