# Sprech-Skript Fachjury: StatAgent, Use Case 3

Dieses Skript enthält den Sprechtext für die Präsentation (10 Szenen, rund 5:05), den Verweis auf die Demo, die Stichpunkte für das Gespräch am Tisch und die 5-Minuten-Fassung für das Finale. Der Sprechtext steht in der Ich-Form von Bernhard Götzendorfer und ist so geschrieben, wie er ihn laut sagt. Er gehört zur Folge „1 + 2 + 3 = 4“ (Szenen v4).

- **Stand:** 05.11.2026
- **Zeiten:** Freeze für Code, Präsentation und Demo am Fr 06.11.2026 um 07:00. Probe Fr 06:00–07:00. Fachjury ab 09:00, etwa 15 Minuten je Team: 10 Minuten Vortrag mit Demo, danach Live-Änderung der Jury und Datenanfragen.
- **Zielbild:** Die Folien zeigen das Zielbild „1 + 2 + 3 = 4“ und wie wir dahin kamen. Der Tagesstand steht nur im Fragenkatalog `docs/praesentation/fragenkatalog.md`.
- **Belege:** Zahlen mit Kennung F… (zum Beispiel F3) stehen im Belegregister `docs/praesentation/belegregister.md`. Unter jeder Szene steht, welche Kennungen darin vorkommen. Die Kennungen werden nicht mitgesprochen.
- **Takte:** Das Zeichen „→“ steht vor dem Satz, der mit dem Klick kommt. Es wird nicht mitgesprochen.
- **Demo:** Läuft live auf dem Rechner von Bernhard (Stufe 1, Modell Azure). Ablauf und Rückfallwege stehen im Demo-Drehbuch `docs/praesentation/demo-drehbuch.md`.
- **Lesehilfe:** Der gezählte Sprechtext steht in den eingerückten Absätzen (mit `>`). Alles andere sind Regieanweisungen.

---

## 1 Vortrag, rund 5 Minuten (Szenen 1 bis 10)

Sprechtempo: 130 Wörter je Minute. Die Szenenzeiten sind verbindlich, die Summe ist 5:05. Danach beginnt die Demo (siehe Abschnitt „Demo“).

### Szene 1 · Drei Aufgaben, eine Antwort · 0:00–0:15

> Guten Morgen, ich bin Bernhard Götzendorfer. Ich zeige Ihnen, wie aus drei Aufgaben eine vierte wurde. Bewertet wird die Statistik, Aufgabe 3.

Belege: keine Zahl.

### Szene 2 · Drei Menschen, drei Fragen · 0:15–0:45

> Die Challenge stellt drei Aufgaben. Versicherte wollen wissen, was ihnen zusteht. Entscheider wollen wissen, was eine Entscheidung bewirkt. Und das Statistik-Team will sicher sein, dass jede veröffentlichte Zahl stimmt. Drei Menschen, drei Fragen. Alle brauchen dasselbe: eine Antwort, der sie trauen können.

Belege: keine Zahl.

### Szene 3 · Eine falsche Zahl kostet Vertrauen · 0:45–1:45 (3 Takte)

> Ein Fall aus den Daten der Challenge. Jeden Monat kommt eine Lieferung. Daraus wird eine Zahl: wie viele Beschäftigungsverhältnisse es gibt.
> → Im Oktober 2025 fehlen in der Lieferung 78.949 Beschäftigungsverhältnisse, jedes fünfte. Wer einfach zählt, meldet für Oktober 81.046 Beschäftigungsverhältnisse weniger. Einen Einbruch, den es nie gab.
> → StatAgent veröffentlicht nicht. Er hält an und schreibt eine Rückfrage.
> → Im November 2025 sind 78.733 davon wieder da.

Belege: F11 (78.949, 78.733, vorläufig 390.900), F17 (313.154, 394.200, 81.046), F20 (24 Monatswerte). Die Zahlen 78.949 und 81.046 sind verschieden: 78.949 zählt Fälle, die in der Lieferung fehlen, 81.046 ist der Unterschied der Bestände (394.200 minus 313.154).

### Szene 4 · Aus Use Case 3 wurde ein Kern für alle drei · 1:45–2:20 (3 Takte)

> Angefangen habe ich mit der schwersten Frage: Kann man einer Zahl trauen? Daraus wurden drei Regeln.
> → Jede Zahl hat einen Beleg.
> → Jede Änderung hat einen Namen, freigeben darf nur ein Mensch.
> → Das Programm rechnet, die KI schlägt nur vor. Auf diesem Kern stehen der Lotse und der Simulator.

Belege: F3 (Fußzeile der Folie: 24 Lieferungen, 10.152.292 Zeilen).

### Szene 5 · Wir rechnen den offiziellen Bericht nach · 2:20–2:50 (ohne Takt)

> Woher wissen wir, dass StatAgent richtig rechnet? Der Veranstalter hat einen offiziellen Bericht für August 2024 mitgegeben: 13 Tabellen, 2.880 Zahlen. StatAgent rechnet ihn selbst nach. Alle 2.880 stimmen. Die Regeln stammen aus der Fachbeschreibung, nur zwei Lücken schließt der Bericht. Für die anderen 23 Monate wachen 24 Prüfregeln.

Belege: F1, F15.

### Szene 6 · Acht Arten von Fehlern gefunden · 2:50–3:25 (3 Takte)

> In den Daten stecken Fehler.
> → 370 Beschäftigungsverhältnisse mit Geburtsmonat 13.
> → Sieben Datensätze mit 117 bis 153 Jahren.
> → 1.663 doppelte Zeilen im März 2025. Dazu fünf weitere Arten, acht insgesamt. Gelöscht haben wir nichts. Das Programm korrigiert nach einer Regel oder hält an und fragt nach.

Belege: F4 (370), F5 (7; 117 bis 153), F8 (1.663), F9 (1.492 in der Nachzeile der Folie), F7 (1.996 in der Nachzeile der Folie).

### Szene 7 · Im Januar 2025 wechselt die Branchenliste · 3:25–3:50 (ohne Takt)

> Im Januar 2025 wechselt die Branchenliste. Meist passt ein alter Code auf einen neuen, manchmal wird aus einem zwei. Wir führen beide Listen mit Gültigkeit. Alte Codes von 2003 ordnen wir C zu, Herstellung von Waren.

Belege: F13 (ohne Zahl), F6 (Codes von 2003 zählen zu C). Keine Zahl auf der Folie.

### Szene 8 · Den 13. Monat haben wir nachgerechnet · 3:50–4:25 (3 Takte)

> Ein Fehler im Detail.
> → 370 Beschäftigungsverhältnisse sind laut Lieferung im 13. Monat geboren. Wie alt ist, wer so geboren ist?
> → Drei Rechenwege haben wir mit dem offiziellen Bericht verglichen. Nur einer trifft alle 576 Zahlen: Berichtsjahr minus Geburtsjahr.
> → Wir nehmen den 1. Juli als Geburtstag. Welcher Tag für Jänner bis Juni gilt, fragen wir die Fachabteilung.

Belege: F4 (370; 576; 408, 367, 0 auf der Folie).

### Szene 9 · Eine Frage, drei Antworten, jede mit Beleg · 4:25–4:55 (3 Takte)

> Das ist das Ziel: Eine Frage läuft durch alle drei.
> → StatAgent liefert die geprüfte Zahl: 7.498 Beschäftigungsverhältnisse.
> → Der Simulator wägt ab, was mehr oder weniger Personal für Wartezeiten bedeutet.
> → Der Lotse erklärt es in einfachen Worten. So wird aus drei Aufgaben eine vierte.

Belege: F18 (7.498, Sollwert laut unabhängigem Orakel).

### Szene 10 · Jede Zahl nachrechenbar · 4:55–5:05

> Jede Zahl lässt sich nachrechnen. Jetzt live. Nennen Sie mir eine Regel, die ich jetzt ändern soll.

Belege: keine Zahl. Die Schlussfolie nennt ki-challenge.gotzendorfer.at.

---

## 2 Zeittabelle

Messung: Wörter je Sprechtext mit `wc -w` gezählt, das Takt-Zeichen „→“ nicht mitgezählt. Schätzung: Wörter × 60 / 130 Sekunden, gerundet. Grenze: Summe der Schätzung höchstens 305 Sekunden (5:05).

| Szene | Soll (s) | Wörter im Sprechtext | Schätzung bei 130 Wörtern/min (s) |
|---|---|---|---|
| 1 Drei Aufgaben, eine Antwort | 15 | 22 | 10 |
| 2 Drei Menschen, drei Fragen | 30 | 42 | 19 |
| 3 Eine falsche Zahl kostet Vertrauen | 60 | 65 | 30 |
| 4 Aus Use Case 3 wurde ein Kern für alle drei | 35 | 48 | 22 |
| 5 Wir rechnen den offiziellen Bericht nach | 30 | 49 | 23 |
| 6 Acht Arten von Fehlern gefunden | 35 | 45 | 21 |
| 7 Im Januar 2025 wechselt die Branchenliste | 25 | 36 | 17 |
| 8 Den 13. Monat haben wir nachgerechnet | 35 | 56 | 26 |
| 9 Eine Frage, drei Antworten, jede mit Beleg | 30 | 43 | 20 |
| 10 Jede Zahl nachrechenbar | 10 | 17 | 8 |
| **Summe** | **305** | **423** | **196** |

Ergebnis: Schätzung 196 s (höchstens 305 s erlaubt), Soll 305 s gleich 5:05. Die Schätzung liegt unter dem Soll, weil Takte, Animationen und Blickkontakt Zeit brauchen. Wer die Folien sprechen will, braucht auch bei 20 % weniger Tempo (104 Wörter je Minute) nur 245 s.

---

## Demo

Die Demo beginnt bei 5:05, unmittelbar nach Szene 10, und dauert bis 9:30. Ablauf, Klickwege, Rückfälle und Sprechsätze stehen im Demo-Drehbuch `docs/praesentation/demo-drehbuch.md`. Hier stehen nur die Minutenmarken:

| Zeit | Schritt | Dauer |
|---|---|---|
| 5:05–6:15 | D1 Lauf und Qualitätsbericht | 1:10 |
| 6:15–7:45 | D2 Änderung per Sprache mit Freigabe | 1:30 |
| 7:45–9:00 | D3 Datenanfragen | 1:15 |
| 9:00–9:30 | D4 Gemeinsamer Einstieg (nur wenn `/uc4` bis zum Freeze grün ist) | 0:30 |

Die Live-Änderung (Dienstvertrag und freier Dienstvertrag zusammen) steht im Drehbuch, nicht auf den Folien. Läuft die öffentliche Demo im Testmodus, sagt Bernhard „Testmodus“ vorher an.

---

## 3 Fachjury-Skript am Tisch

Stichpunkte, keine ganzen Sätze zum Ablesen. Die Zeiten sind Richtwerte für die Zeit nach dem Vortrag. Monate stehen ausgeschrieben, Dateipfade und Befehle behalten ihre Schreibweise.

### Lösung (30 s)

- Zwei Sätze: Eine Lieferung rein, ein Qualitätsbericht und eine Nachrechnung des offiziellen Berichts raus. Jede Zahl hat einen Beleg.
- Die KI schreibt Code und Regeländerungen als Vorschlag. Das Programm rechnet. Der Mensch gibt frei.
- Regelsatz v1: 15 Einlese-, Zuordnungs- und Zählregeln und 24 Prüfregeln. Der Regelsatz ist die Sammlung der Regeln. Jede Regel hat Gültigkeit, Begründung, Grundlage und Freigabe (F15).
- Zwei Läufe mit denselben Daten und Regeln geben denselben Ergebnis-Hash (F16).

### Stack (30 s)

- PostgreSQL 16 mit den Schemas `roh`, `klassifikation`, `bereinigt`, `stat`, `meta`.
- Python-Paket `statagent`, Befehl `uc3`. Ein Lauf ist eine Lieferung (`lauf --lieferung JJJJ-MM`).
- Next.js-Oberfläche: im Bau (MR !51). Nur wenn `/uc3` bis zum Freeze auf main ist, wird sie gezeigt. Sonst ist die CLI der Standard.
- Modelle nur über `plattform.llm`. Standard für die UC3-Agenten ist Azure (gpt-5-4-mini). Umschaltbar über `LLM_PROVIDER`. Das Modell sieht Regeln, Schemata und Summen, keine Einzeldaten.

### Herausforderungen (45 s)

- **Wechsel der ÖNACE-Version (F13):** Die Branchenliste wechselt von ÖNACE 2008 auf ÖNACE 2025, ab der Lieferung Januar 2025, auch rückwirkend für Dezember 2024. Meist passt ein alter Code auf einen neuen, manchmal wird aus einem zwei (J: ein alter Code, zwei neue). Wir führen beide Listen mit Gültigkeit und vergleichen Sprünge nur bei gleicher Version. Keine Zahl nennen.
- **Stille Teil-Lieferung, zwei Zahlen sauber trennen (F11, F17):** Oktober 2025 hat 345.078 Zeilen statt rund 430.000. 78.949 ist die Zahl der Beschäftigungsverhältnisse, die am 30. September offen waren und in der Lieferung fehlen (20,0 %). 81.046 ist etwas anderes: der Unterschied zwischen dem Bestand der Lieferung (313.154) und dem Vormonat (394.200). Wer einfach zählt, meldet 81.046 weniger. Das Programm hält den Lauf an und schreibt 77.746 Beschäftigungsverhältnisse vorläufig fort (vorläufig 390.900). 78.733 der fehlenden sind im November 2025 wieder da.
- **Spaltentausch (F10):** Im Juni 2025 ist Beginn bei 388.115 von 432.086 Zeilen leer. Ohne Tausch bestehen am 30. Juni 2025 nur 21 Beschäftigungsverhältnisse, mit Tausch 394.252. Die Regel `E01_spaltentausch_beginn_ende` tauscht für die ganze Lieferung.
- **Revisionsbedarf, ohne Veröffentlichtes anzufassen (F12):** Dezember 2024 weicht um −260 ab (387.390 Stand aus der Lieferung Dezember 2024, 387.130 nach der Lieferung Januar 2025, −0,067 %). Die Abweichung steht im Bericht. Ist ein Monat veröffentlicht, bleibt seine Zahl. Jeder Lauf ist vorläufig, endgültig wird ein Monat nur mit `uv run uc3 veroeffentlichen --lieferung JJJJ-MM --name "…"`. Danach ist er unveränderlich. Im Bericht Januar 2025 steht Dezember 2024 noch als „387.390 (vorläufig)“.
- **Zirkelschluss? (wie Fragenkatalog C15):** Nein. Die Regeln kommen aus der Fachbeschreibung. Nur zwei Lücken schließt der Bericht selbst: Geburtsmonat 13 und die Altersgrenze (`docs/plan/uc3/annahmen.md` A4 und A5, F4, F5). Für die übrigen 23 Monate gibt es keinen Vergleichsbericht, dort wachen 24 Prüfregeln (F15). Die Gegenrechnung lief unabhängig und ohne den UC3-Code, direkt auf den Rohdaten.

### Gefundene Datenfehler (60 s)

Je ein Satz mit Zahl, Lieferung und Einstufung. Die Einstufungen stehen so in den Qualitätsberichten der UC3-Lieferungen.

1. **Geburtsmonat 13 (F4):** 370 Beschäftigungsverhältnisse am Stichtag, Lieferung August 2024. Einstufung: erklärt, Datenproblem. Wir behalten das Geburtsjahr.
2. **Unplausibles Alter (F5):** 7 Beschäftigungsverhältnisse mit 117 bis 153 Jahren, Lieferung August 2024. Einstufung: erklärt, Datenproblem. Sie zählen als Alter unbekannt, der Grenzwert `max_plausibel = 110` ist ein Regelparameter.
3. **ÖNACE-2003-Altcodes (F6):** 50 Beschäftigungsverhältnisse, Lieferung August 2024. Einstufung: erklärt, Datenproblem. Sie zählen zu Abschnitt C, 62.154 + 50 = 62.204 wie im offiziellen Bericht.
4. **Bundesland und ÖNACE leer (F7):** 1.996 Beschäftigungsverhältnisse, Lieferung August 2024, immer beide gemeinsam. Einstufung: erklärt, Datenproblem. Sie zählen als unbekannt.
5. **Volldubletten (F8):** 1.663 Zeilen doppelt, nur Lieferung März 2025. Einstufung: erklärt, Datenproblem. Ohne Bereinigung wären am 31. März 2025 1.523 Beschäftigungsverhältnisse doppelt gezählt.
6. **Freie Dienstverträge fehlen (F9):** 1.492 Beschäftigungsverhältnisse, Lieferung März 2025, alle im April 2025 wieder da. Einstufung im Bericht: erklärt, Datenproblem. Das Programm hält den Monat an und schreibt 1.470 offene Beschäftigungsverhältnisse vorläufig fort.
7. **Spaltentausch (F10):** 388.115 von 432.086 Zeilen ohne Beginn, Lieferung Juni 2025. Einstufung: erklärt, Datenproblem. Die Regel E01 tauscht Beginn und Ende.
8. **Teil-Lieferung (F11):** 78.949 Beschäftigungsverhältnisse fehlen (20,0 %), Lieferung Oktober 2025, 78.733 davon sind im November 2025 wieder da. Einstufung: erklärt, Datenproblem. Das Programm hält den Lauf an. Nicht verwechseln mit 81.046 (F17), dem Unterschied der Bestände.

Ehrlich dazu: Alle acht sind in den Berichten als erklärt, Datenproblem eingestuft. Die Stufe nicht erklärbar gibt es auch. Sie steht zum Beispiel bei einzelnen Branchensprüngen im Bericht März 2025 und beim Revisionsbedarf im Bericht Oktober 2025. Diese Fälle gehen an die Fachabteilung. Ihre Zahlen stehen nicht im Belegregister und werden deshalb nicht genannt.

### Eine Annahme im Detail: Geburtsmonat 13 (60 s)

- Problem: Geburtsdaten wie 1963-13-09. 370 Beschäftigungsverhältnisse am Stichtag August 2024, je Lieferung 305 bis 399 (F4).
- Test: drei Rechenwege gegen Tabelle 13 des offiziellen Berichts, 576 Zahlen (F4).
  - Alter bleibt leer: 408 Zahlen falsch.
  - Berichtsjahr − Geburtsjahr − 1 („ein Jahr jünger“): 367 Zahlen falsch.
  - Berichtsjahr − Geburtsjahr: 0 Zahlen falsch.
- Altersregel: Als Geburtstag gilt der 1. Juli. Für August 2024 ist das genau Berichtsjahr minus Geburtsjahr, denn der Geburtstag liegt vor dem Stichtag. Welcher Tag für Jänner bis Juni gilt, ist offen (Rückfrage R1 an die Fachabteilung).
- Regeln: `E03_datum_pruefen` und `R5_alter`, beide als Daten in `meta.regel` mit Begründung und Freigabe.
- Quelle der Annahme: `docs/plan/uc3/annahmen.md` A4 und A5. Das ist der Teil, den der Bericht schließt (siehe Zirkelschluss).

### Live-Änderung der Jury (Ablauf in 5 Schritten)

1. **Zuhören.** Den Auftrag ganz anhören, nicht unterbrechen.
2. **In einem Satz wiederholen.** „Ich verstehe: Sie wollen …“ Erst nach dem Ja der Jury weiter.
3. **Vorschlag erzeugen.** `uv run uc3 agent "<Änderungsauftrag>" --probe JJJJ-MM` mit einem Monat, der zum Auftrag passt. Der Befehl erzeugt nur einen Vorschlag und ändert nichts.
4. **Vorschlag zeigen.** `uv run uc3 vorschlag zeigen <id>`: Unterschied in den Regeln und Zahlen vorher und nachher laut vorlesen.
5. **Freigeben.** Erst nach Prüfung und Ja der Jury: `uv run uc3 freigabe <id> --name "Bernhard Götzendorfer"`. Das macht den Vorschlag wirksam, der gespeicherte Änderungsschritt im Repo trägt den Vermerk `Freigegeben-von`. Beim Üben nie `freigabe`, nur bis `vorschlag zeigen` und dann `ablehnen`. Lehnt die Jury ab: `ablehnen <id> --name "…" --begruendung "…"`.

Rückfallsatz, wenn etwas Ungeübtes kommt: „Das setzt der Agent als Vorschlag um, die Freigabe folgt nach Prüfung.“

### Datenanfragen

Beispiele, Kurzantworten und Fundstellen stehen im Fragenkatalog `docs/praesentation/fragenkatalog.md`. Stand heute: Der Befehl `frage` ist noch nicht fertig (Issues #74 und #75). Datenanfragen laufen bis dahin als SQL aus dem Fragenkatalog gegen die UC3-Datenbank. Das ehrlich so sagen.

---

## 4 Finale, 5 Minuten

Nur falls das Team unter die ersten drei kommt. Das Publikum ist ein Manager-Gremium mit weniger Technik, mehr Anwendung und Verantwortung. Szenenfolge: 1, 2, 3, 5, 6 (gekürzt auf drei Befunde), 9, dann die Verantwortung in drei Sätzen, dann 10. Keine Technikfolie am Schluss: Die Verantwortung kommt vor dem Schlussbild. Es gibt im Finale keine Demo; die Schlussszene wird ohne „Jetzt live“ gesprochen.

### Finale · Szene 1 · Drei Aufgaben, eine Antwort · 0:00–0:20

> Guten Tag, ich bin Bernhard Götzendorfer, Team OneShotAndy. Ich zeige Ihnen, wie aus drei Aufgaben eine vierte wurde. Bewertet wird die Statistik, Aufgabe 3.

### Finale · Szene 2 · Drei Menschen, drei Fragen · 0:20–0:50

> Drei Menschen brauchen eine Antwort. Versicherte wollen wissen, was ihnen zusteht. Entscheider wollen wissen, was eine Entscheidung bewirkt. Das Statistik-Team will sicher sein, dass jede veröffentlichte Zahl stimmt. Alle drei brauchen eine Antwort, der sie trauen können.

### Finale · Szene 3 · Eine falsche Zahl kostet Vertrauen · 0:50–1:40 (3 Takte)

> Ein Fall aus den Daten der Challenge. Jeden Monat kommt eine Lieferung, daraus wird eine Zahl.
> → Im Oktober 2025 fehlen in der Lieferung 78.949 Beschäftigungsverhältnisse, jedes fünfte. Wer einfach zählt, meldet 81.046 weniger, einen Einbruch, den es nie gab.
> → StatAgent veröffentlicht nicht. Er hält an und schreibt eine Rückfrage.
> → Im November 2025 sind 78.733 davon wieder da.

### Finale · Szene 5 · Wir rechnen den offiziellen Bericht nach · 1:40–2:10

> Der Veranstalter hat einen offiziellen Bericht für August 2024 mitgegeben: 13 Tabellen, 2.880 Zahlen. StatAgent rechnet ihn selbst nach. Alle 2.880 stimmen, null Abweichungen. Für die anderen 23 Monate wachen 24 Prüfregeln.

### Finale · Szene 6 (gekürzt) · Acht Arten von Fehlern gefunden · 2:10–2:50 (3 Takte)

> In den Daten stecken Fehler.
> → 370 Beschäftigungsverhältnisse mit Geburtsmonat 13.
> → Sieben Datensätze mit 117 bis 153 Jahren.
> → 1.663 doppelte Zeilen im März 2025. Acht Arten insgesamt. Gelöscht haben wir nichts. Das Programm korrigiert nach einer Regel oder hält an und fragt nach.

### Finale · Szene 9 · Eine Frage, drei Antworten, jede mit Beleg · 2:50–3:20 (3 Takte)

> Das ist das Ziel: Eine Frage läuft durch alle drei.
> → StatAgent liefert die geprüfte Zahl: 7.498 Beschäftigungsverhältnisse.
> → Der Simulator wägt ab, was mehr oder weniger Personal für Wartezeiten bedeutet.
> → Der Lotse erklärt es in einfachen Worten. So wird aus drei Aufgaben eine vierte.

### Finale · Verantwortung in drei Sätzen · 3:20–4:00

> Jede Regeländerung und jede Lieferung gibt ein Mensch mit Vor- und Nachnamen frei, und der Zeitpunkt wird festgehalten. Ist ein Monat veröffentlicht, bleibt seine Zahl, und Abweichungen stehen im Bericht, statt dass wir etwas überschreiben. Das Modell sieht keine Einzeldaten, und die Verantwortung für jede Zahl bleibt bei Menschen.

### Finale · Szene 10 · Jede Zahl nachrechenbar · 4:00–4:15

> Jede Zahl lässt sich nachrechnen, jede Änderung hat einen Namen. Danke.

**Zeittabelle Finale**

| Teil | Fenster (s) | Wörter im Sprechtext | Schätzung bei 130 Wörtern/min (s) |
|---|---|---|---|
| Szene 1 · Drei Aufgaben, eine Antwort | 20 | 24 | 11 |
| Szene 2 · Drei Menschen, drei Fragen | 30 | 37 | 17 |
| Szene 3 · Eine falsche Zahl kostet Vertrauen | 50 | 57 | 26 |
| Szene 5 · Wir rechnen den offiziellen Bericht nach | 30 | 32 | 15 |
| Szene 6 (gekürzt) · Acht Arten von Fehlern gefunden | 40 | 42 | 19 |
| Szene 9 · Eine Frage, drei Antworten | 30 | 43 | 20 |
| Verantwortung in drei Sätzen | 40 | 49 | 23 |
| Szene 10 · Jede Zahl nachrechenbar | 15 | 11 | 5 |
| **Summe** | **255** | **295** | **136** |

Ergebnis: Fenster zusammen 255 s gleich 4:15, Grenze ist 4:45. Die reine Sprechzeit liegt bei etwa 136 s. Der Rest sind Folienwechsel, Takte und Pausen.

Belege Finale: F11, F17 (Szene 3), F1, F15 (Szene 5), F4, F5, F8 (Szene 6), F18 (Szene 9).

---

## 5 Nicht sagen

- Keine Zeitersparnis ohne Messung. Kein „Minuten statt Tage“, bis ein Use-Case-Owner einen Wert nennt.
- Kein Personalabbau und keine Stelleneinsparung als Argument.
- Nie „die KI hat gerechnet“. Richtig: Die KI schreibt Code, das Programm rechnet.
- Keine Hostnamen, auch keine Rechner- oder Servernamen. Die öffentliche Demo läuft im Testmodus. Wird sie gezeigt, heißt sie „öffentliche Demo“ und der Testmodus wird angesagt.
- Keine IPs, Zugangsdaten und Beispiel-IDs einzelner Verhältnisse.
- Keine Rückfrage-Nummern außer R1 (Geburtsmonat 13). Sonst: „Rückfrage an die Fachabteilung“.
- Keine Zahl, die nicht im Belegregister steht.
