# Sprech-Skript Fachjury: StatAgent, Use Case 3

Dieses Skript enthält den Sprechtext für den 10-Minuten-Vortrag, die Stichpunkte für das Gespräch am Tisch und die 5-Minuten-Fassung für das Finale. Der Sprechtext steht in der Ich-Form von Bernhard Götzendorfer und ist so geschrieben, wie er ihn laut sagt.

- **Stand:** 05.11.2026
- **Zeiten:** Freeze für Code, Präsentation und Demo am Fr 06.11.2026 um 07:00. Probe Fr 06:00–07:00. Fachjury ab 09:00, etwa 15 Minuten je Team: 10 Minuten Vortrag mit Demo, danach Live-Änderung der Jury und Datenanfragen.
- **Belege:** Zahlen mit Kennung F… (zum Beispiel F3) stehen im Belegregister `docs/praesentation/belegregister.md`. Unter jedem Abschnitt steht, welche Kennungen darin vorkommen. Die Kennungen werden nicht mitgesprochen.
- **Demo:** Ablauf und Rückfallwege stehen im Demo-Drehbuch `docs/praesentation/demo-drehbuch.md`.
- **Lesehilfe:** Der gezählte Sprechtext steht in den eingerückten Absätzen (mit `>`). Alles andere sind Regieanweisungen.

---

## 1 Vortrag, 10 Minuten

Sprechtempo: 130 Wörter je Minute. Die Folienzeiten sind verbindlich, die Summe ist 9:40. Es bleiben 20 Sekunden Puffer.

### Folie 1 · StatAgent · 0:00–0:30

> Guten Morgen. Ich bin Bernhard Götzendorfer, Team OneShotAndy. Das ist StatAgent. Die KI schreibt Code. Das Programm rechnet. Der Mensch gibt frei.

Belege: keine Zahl.

### Folie 2 · Eine falsche Zahl kostet Vertrauen · 0:30–1:15

> Das Statistik-Team des Dachverbands arbeitet mit Hochrisikodaten. Es geht um Beschäftigte und ihre Geburtsdaten. Wir haben 24 Lieferungen bekommen, das sind die Monatsdateien. Zusammen sind es 10.152.292 Zeilen. Wenn eine veröffentlichte Zahl falsch ist, geht Vertrauen verloren. Darum haben wir eine Frage gestellt: Woher kommt jede Zahl, und wer hat sie freigegeben?

Belege: F3.

### Folie 3 · Einlesen, rechnen, freigeben · 1:15–2:00

> Der Ablauf hat drei Schritte. Erstens lesen wir eine Lieferung ein und prüfen sie. Nichts wird gelöscht. Zweitens stehen die Regeln als Daten in der Tabelle meta.regel. Das Programm rechnet mit diesen Regeln, ganz ohne Sprachmodell. Zwei Läufe mit gleichen Daten ergeben gleiche Zahlen. Drittens gibt ein Mensch frei, mit Vor- und Nachnamen. Der Name Team wird abgelehnt.

Belege: F15, F16.

### Folie 4 · Was wo läuft · 2:00–2:45

> So ist es gebaut. Unten liegt PostgreSQL 16, die Datenbank. Darüber liegt das Python-Paket statagent mit dem Befehl uc3. Es liest, prüft und rechnet. Die Oberfläche in Next.js liest nur und startet diesen Befehl. Die Agenten sprechen über eine einzige Schnittstelle mit dem Modell. Das Modell ist austauschbar. Es sieht Regeln, Schemata und Summen. Einzeldaten sieht es nie.

Belege: Stack laut `uc3/README.md`, keine Zahl.

### Folie 5 · 2.880 von 2.880 · 2:45–3:15

> Zuerst der Beleg. Der Beispielbericht für August 2024 ist unser Golden Set, also die Vorlage zum Prüfen. Er hat 2.880 Zahlenzellen. Wir haben alle nachgerechnet, null Abweichungen. Auch die Brücke geht auf: 392.284 Zeilen, minus 48 Abschnitte, die vor dem Stichtag enden, gleich 392.236. Der Stichtag ist der Monatsletzte.

Belege: F1, F2.

### Folie 6 · Acht Datenfehler, nichts gelöscht · 3:15–4:15

> Wir haben acht Datenfehler gefunden. Gelöscht haben wir keinen. Erstens: 370 Beschäftigungsverhältnisse haben Geburtsmonat 13. Zweitens: Sieben Verhältnisse haben ein Alter von 117 bis 153 Jahren. Drittens: 50 Verhältnisse tragen Branchencodes von 2003. Viertens: Bei 1.996 fehlen Bundesland und Branche. Das sind Zahlen für August 2024. Fünftens: Im März 2025 sind 1.663 Zeilen doppelt. Sechstens: Im selben Monat fehlen 1.492 freie Dienstverträge. Siebtens: Im Juni 2025 sind Beginn und Ende vertauscht, bei 388.115 Zeilen. Achtens: Im Oktober 2025 fehlen 78.949 Verhältnisse. Bei Fehler sechs und acht hält das Programm den Monat an. Alles steht im Qualitätsbericht.

Belege: F4, F5, F6, F7, F8, F9, F10, F11.

### Folie 7 · Geburtsmonat 13 · 4:15–5:00

> Eine Annahme im Detail: Geburtsmonat 13, zum Beispiel 1963-13-09. Wir haben vier Varianten gegen die Tabelle 13 des Beispielberichts getestet. Sie hat 576 Zellen. Variante A liegt bei 416 Zellen falsch, B bei 408, C bei 367. Nur D trifft, null falsch. D heißt: Alter gleich Berichtsjahr minus Geburtsjahr. Als Ersatztag nehmen wir den 1. Juli. Ob das fachlich passt, fragen wir die Fachabteilung in Rückfrage R1.

Belege: F4.

### Folie 8 · Jetzt live · 5:00–8:30

Überleitung, 15 Sekunden (5:00–5:15):

> Jetzt zeige ich es live, in der öffentlichen Demo. Drei Schritte: Lauf und Bericht, eine Änderung per Sprache, eine Datenanfrage.

Demo-Gerüst, 3:15 (195 Sekunden). Ablauf, Klickwege und Rückfälle stehen im Demo-Drehbuch `docs/praesentation/demo-drehbuch.md`. Hier steht nur, was Bernhard sagt.

- **5:15 D1, Lauf und Qualitätsbericht 2025-03 (65 s).** Sage: „Ich starte den Lauf für März 2025. Der Bericht zeigt die doppelten Zeilen und die fehlenden freien Dienstverträge, jeweils mit Einstufung.“
- **6:20 D2, Änderung per Sprache mit Freigabe (80 s).** Sage: „Ich gebe einen Änderungsauftrag. Der Agent macht nur einen Vorschlag. Sie sehen den Unterschied in den Regeln und die Zahlen vorher und nachher. Dann gebe ich mit meinem Namen frei.“
- **7:40 D3, Datenanfrage Männer und Frauen je Bundesland (40 s).** Sage: „Jetzt eine Datenanfrage. Die Zahlen kommen aus einer Abfrage, die Sie sehen können.“
- **8:20 UC-Wechsel kurz zeigen (10 s).** Sage: „Derselbe Kern trägt auch die anderen Anwendungsfälle.“

Belege: keine neue Zahl im Sprechtext.

### Folie 9 · Was wir nicht anfassen · 8:30–9:00

> Was wir nicht anfassen: Veröffentlichtes bleibt, wie es ist. Ändert eine spätere Lieferung einen alten Monat, steht das als Revisionsbedarf im Bericht. Beispiel Dezember 2024: minus 260 Verhältnisse. Die Zahl bleibt veröffentlicht, die Abweichung ist dokumentiert. Und das Modell sieht keine Einzeldaten.

Belege: F12.

### Folie 10 · Ein Kern, ein Einstieg · 9:00–9:25

> Bewertet wird Use Case 3. Der Kern trägt mehr: Belege, Freigabe mit Namen, Modell-Schalter. Darauf laufen der KI-Lotse und der HealthPolicy Simulator. Nächster Schritt: ein gemeinsamer Einstieg. Eine Frage bekommt die geprüfte Zahl, die Abwägung und eine einfache Erklärung.

Belege: keine Zahl.

### Folie 11 · Jede Zahl nachrechenbar · 9:25–9:40

> Jede Zahl ist nachrechenbar. Jede Änderung ist freigegeben. Alles liegt offen im Repo KIChallenge/OneShotAndy. Danke.

Belege: keine Zahl.

---

## 2 Zeittabelle

Messung: Wörter je Sprechtext mit `wc -w` gezählt. Schätzung: Wörter × 60 / 130 Sekunden. Die Demo ist mit festen 195 Sekunden angesetzt. Grenze: Summe der Schätzung höchstens 580 Sekunden.

| Folie | Soll (s) | Wörter im Sprechtext | Schätzung bei 130 Wörtern/min (s) |
|---|---|---|---|
| 1 StatAgent | 30 | 22 | 10 |
| 2 Eine falsche Zahl kostet Vertrauen | 45 | 52 | 24 |
| 3 Einlesen, rechnen, freigeben | 45 | 58 | 27 |
| 4 Was wo läuft | 45 | 58 | 27 |
| 5 2.880 von 2.880 | 30 | 49 | 23 |
| 6 Acht Datenfehler, nichts gelöscht | 60 | 96 | 44 |
| 7 Geburtsmonat 13 | 45 | 67 | 31 |
| 8 Überleitung | 15 | 20 | 9 |
| 8 Demo D1 bis UC-Wechsel | 195 | (Demo, nicht gezählt) | 195 |
| 9 Was wir nicht anfassen | 30 | 42 | 19 |
| 10 Ein Kern, ein Einstieg | 25 | 39 | 18 |
| 11 Jede Zahl nachrechenbar | 15 | 15 | 7 |
| **Summe** | **580** | **518** | **434** |

Ergebnis: Schätzung 434 s (höchstens 580 s erlaubt), Soll 580 s gleich 9:40, Puffer zu 10:00 sind 20 s. Die Schätzung liegt unter dem Soll, weil Pausen, Klicks und Blickkontakt dazukommen.

---

## 3 Fachjury-Skript am Tisch

Stichpunkte, keine ganzen Sätze zum Ablesen. Die Zeiten sind Richtwerte für die Zeit nach dem Vortrag.

### Lösung (30 s)

- Zwei Sätze: Eine Lieferung rein, ein Qualitätsbericht und ein Beispielbericht raus. Jede Zahl hat einen Beleg.
- Die KI schreibt Code und Regeländerungen als Vorschlag. Das Programm rechnet. Der Mensch gibt frei.
- Regelsatz v1: 15 Einlese-, Zuordnungs- und Zählregeln und 24 Prüfregeln. Der Regelsatz ist die Sammlung der Regeln. Jede Regel hat Gültigkeit, Begründung, Grundlage und Freigabe (F15).
- Zwei Läufe mit denselben Daten und Regeln geben denselben Ergebnis-Hash (F16).

### Stack (30 s)

- PostgreSQL 16 mit den Schemas `roh`, `klassifikation`, `bereinigt`, `stat`, `meta`.
- Python-Paket `statagent`, Befehl `uc3`. Ein Lauf ist eine Lieferung (`lauf --lieferung JJJJ-MM`).
- Next.js liest nur und startet die CLI.
- Modelle nur über `plattform.llm`. Standard für die UC3-Agenten ist Azure (gpt-5-4-mini). Umschaltbar über `LLM_PROVIDER`. Das Modell sieht Regeln, Schemata und Summen, keine Einzeldaten.

### Herausforderungen (45 s)

- **Klassifikationswechsel (F13):** Ab Lieferung 2025-01 gilt ÖNACE 2025 statt 2008, auch rückwirkend für den 31.12.2024. 189.170 von 386.299 Verhältnissen tragen dort einen anderen Abschnittscode. Wir führen beide Versionen getrennt und vergleichen Sprünge nur bei gleicher Version.
- **Stille Teil-Lieferung (F11):** Oktober 2025 hat 345.078 Zeilen statt rund 430.000. Das Programm hält den Lauf an und schreibt 77.746 Verhältnisse vorläufig fort.
- **Spaltentausch (F10):** Im Juni 2025 ist Beginn bei 388.115 von 432.086 Zeilen leer. Ohne Tausch bestehen am 30.06.2025 nur 21 Verhältnisse, mit Tausch 394.252. Die Regel `E01_spaltentausch_beginn_ende` tauscht für die ganze Lieferung.
- **Revisionsbedarf, ohne Veröffentlichtes anzufassen (F12):** Dezember 2024 weicht um −260 ab (387.390 veröffentlicht, 387.130 nach Lieferung 2025-01, −0,067 %). Die Abweichung steht im Bericht. Die veröffentlichte Zahl bleibt.

### Gefundene Datenfehler (60 s)

Je ein Satz mit Zahl, Lieferung und Einstufung. Die Einstufungen stehen so in den Qualitätsberichten der UC3-Lieferungen.

1. **Geburtsmonat 13 (F4):** 370 Verhältnisse am Stichtag, Lieferung 2024-08. Einstufung: erklärt, Datenproblem. Wir behalten das Geburtsjahr.
2. **Unplausibles Alter (F5):** 7 Verhältnisse mit 117 bis 153 Jahren, Lieferung 2024-08. Einstufung: erklärt, Datenproblem. Sie zählen als Alter unbekannt, der Grenzwert `max_plausibel = 110` ist ein Regelparameter.
3. **ÖNACE-2003-Altcodes (F6):** 50 Verhältnisse, Lieferung 2024-08. Einstufung: erklärt, Datenproblem. Sie zählen zu Abschnitt C, 62.154 + 50 = 62.204 wie im Beispielbericht.
4. **Bundesland und ÖNACE leer (F7):** 1.996 Verhältnisse, Lieferung 2024-08, immer beide gemeinsam. Einstufung: erklärt, Datenproblem. Sie zählen als unbekannt.
5. **Volldubletten (F8):** 1.663 Zeilen doppelt, nur Lieferung 2025-03. Einstufung: erklärt, Datenproblem. Ohne Bereinigung wären am 31.03.2025 1.523 Verhältnisse doppelt gezählt.
6. **Freie Dienstverträge fehlen (F9):** 1.492 Verhältnisse, Lieferung 2025-03, alle in 2025-04 wieder da. Einstufung im Bericht: erklärt, Datenproblem. Das Programm hält den Monat an und schreibt 1.470 offene Verhältnisse vorläufig fort.
7. **Spaltentausch (F10):** 388.115 von 432.086 Zeilen ohne Beginn, Lieferung 2025-06. Einstufung: erklärt, Datenproblem. Die Regel E01 tauscht Beginn und Ende.
8. **Teil-Lieferung (F11):** 78.949 Verhältnisse fehlen (20,0 %), Lieferung 2025-10, 78.733 davon sind in 2025-11 wieder da. Einstufung: erklärt, Datenproblem. Das Programm hält den Lauf an.

Ehrlich dazu: Alle acht sind in den Berichten als erklärt, Datenproblem eingestuft. Die Stufe nicht erklärbar gibt es auch. Sie steht zum Beispiel bei einzelnen Branchensprüngen im Bericht 2025-03 und beim Revisionsbedarf im Bericht 2025-10. Diese Fälle gehen an die Fachabteilung. Ihre Zahlen stehen nicht im Belegregister und werden deshalb nicht genannt.


### Eine Annahme im Detail: Geburtsmonat 13 (60 s)

- Problem: Geburtsdaten wie 1963-13-09. 370 Verhältnisse am Stichtag 08/2024, je Lieferung 305 bis 399 (F4).
- Test: vier Varianten gegen Tabelle 13 des Beispielberichts, 576 Zellen (F4).
  - A: unbekannt, Alter über 74 bleibt in „75 u. mehr“: 416 Zellen falsch.
  - B: unbekannt: 408 Zellen falsch.
  - C: Berichtsjahr − Geburtsjahr − 1: 367 Zellen falsch.
  - D: Berichtsjahr − Geburtsjahr: 0 Zellen falsch.
- Entscheid: Ersatztag 1. Juli des Geburtsjahres. Für 08/2024 gleich wie D.
- Regeln: `E03_datum_pruefen` und `R5_alter`, beide als Daten in `meta.regel` mit Begründung und Freigabe.
- Offen: Welcher Ersatztag fachlich gilt. Das ist Rückfrage R1 an die Fachabteilung.

### Live-Änderung der Jury (Ablauf in 5 Schritten)

1. **Zuhören.** Den Auftrag ganz anhören, nicht unterbrechen.
2. **In einem Satz wiederholen.** „Ich verstehe: Sie wollen …“ Erst nach dem Ja der Jury weiter.
3. **Vorschlag erzeugen.** `uv run uc3 agent "<Änderungsauftrag>" --probe JJJJ-MM` mit einem Monat, der zum Auftrag passt. Der Befehl erzeugt nur einen Vorschlag und ändert nichts.
4. **Vorschlag zeigen.** `uv run uc3 vorschlag zeigen <id>`: Unterschied in den Regeln und Zahlen vorher und nachher laut vorlesen.
5. **Freigeben.** Erst nach Prüfung und Ja der Jury: `uv run uc3 freigabe <id> --name "Bernhard Götzendorfer"`. Das macht den Vorschlag wirksam, der Commit trägt den Trailer `Freigegeben-von`. Lehnt die Jury ab: `ablehnen <id> --name "…" --begruendung "…"`.

Rückfallsatz, wenn etwas Ungeübtes kommt: „Das setzt der Agent als Vorschlag um, die Freigabe folgt nach Prüfung.“

### Datenanfragen

Beispiele, Kurzantworten und Fundstellen stehen im Fragenkatalog `docs/praesentation/fragenkatalog.md`. Stand heute: Der Befehl `frage` ist noch nicht fertig (Issues #74 und #75). Datenanfragen laufen bis dahin als SQL aus dem Fragenkatalog gegen die UC3-Datenbank. Das ehrlich so sagen.

---

## 4 Finale, 5 Minuten

Nur falls das Team unter die ersten drei kommt. Das Publikum ist ein Manager-Gremium mit weniger Technik, mehr Anwendung und Verantwortung. Folienfolge: 1, 2, 3, 5, 6 (gekürzt auf vier Befunde), 11 plus Verantwortung in drei Sätzen. Keine Technikfolie am Schluss: Die Verantwortung kommt vor dem Schlussbild.

### Finale · Folie 1 · StatAgent · 0:00–0:20

> Guten Tag. Ich bin Bernhard Götzendorfer, Team OneShotAndy. Das ist StatAgent. Die KI schreibt Code. Das Programm rechnet. Der Mensch gibt frei. Heute zeige ich, wie jede Zahl nachrechenbar entsteht.

### Finale · Folie 2 · Eine falsche Zahl kostet Vertrauen · 0:20–1:00

> Stellen Sie sich vor: Eine Statistik über Beschäftigte wird veröffentlicht, und eine Zahl stimmt nicht. Das kostet Vertrauen. Das sind Hochrisikodaten: Es geht um Menschen und ihre Arbeit. Wer darauf Entscheidungen aufbaut, muss sich verlassen können. Wir haben 24 Monatsdateien bekommen, zusammen 10.152.292 Zeilen. Jede Zahl daraus braucht einen Beleg.

### Finale · Folie 3 · Einlesen, rechnen, freigeben · 1:00–1:45

> Wir arbeiten in drei Schritten. Wir lesen eine Monatsdatei ein und prüfen sie. Nichts wird gelöscht. Dann rechnet ein Programm nach Regeln, die als Daten gespeichert sind. Dabei kommt kein Sprachmodell zum Einsatz. Das Ergebnis ist jedes Mal gleich. Zuletzt gibt ein Mensch frei, mit Vor- und Nachnamen. Wer freigibt, steht mit seinem Namen dafür ein.

### Finale · Folie 5 · 2.880 von 2.880 · 1:45–2:15

> Der Beleg: Unser Beispielbericht für August 2024 ist die Vorlage, gegen die wir prüfen. Er hat 2.880 Zahlenzellen. Wir haben alle nachgerechnet. Alle 2.880 stimmen. Null Abweichungen.

### Finale · Folie 6 (gekürzt) · Vier Datenfehler, nichts gelöscht · 2:15–3:05

> In den Daten stecken Fehler. Vier Beispiele. 370 Beschäftigungsverhältnisse haben als Geburtsmonat die Zahl 13. In einem Monat fehlen 1.492 freie Dienstverträge ganz. In einem anderen sind Beginn und Ende vertauscht, bei 388.115 Zeilen. In einer Lieferung fehlen 78.949 Verhältnisse. Wir löschen nichts. Fehlen Daten, hält das Programm den Monat an. Alles steht im Bericht. Jeder Fall hat eine Zahl, eine Lieferung und eine Einstufung.

### Finale · Verantwortung in drei Sätzen · 3:05–3:50

> Jede Regeländerung und jede Lieferung gibt ein Mensch mit Vor- und Nachnamen frei, und der Zeitpunkt wird festgehalten. Veröffentlichte Zahlen bleiben unverändert, und Abweichungen stehen im Bericht, statt dass wir etwas überschreiben. Das Modell sieht keine Einzeldaten, und die Verantwortung für jede Zahl bleibt bei Menschen.

### Finale · Folie 11 · Jede Zahl nachrechenbar · 3:50–4:05

> Jede Zahl ist nachrechenbar. Jede Änderung ist freigegeben. Das Repo heißt KIChallenge/OneShotAndy. Danke.

**Zeittabelle Finale**

| Teil | Fenster (s) | Wörter im Sprechtext | Schätzung bei 130 Wörtern/min (s) |
|---|---|---|---|
| Folie 1 · StatAgent | 20 | 30 | 14 |
| Folie 2 · Eine falsche Zahl kostet Vertrauen | 40 | 50 | 23 |
| Folie 3 · Einlesen, rechnen, freigeben | 45 | 56 | 26 |
| Folie 5 · 2.880 von 2.880 | 30 | 27 | 12 |
| Folie 6 (gekürzt) · Vier Datenfehler, nichts gelöscht | 50 | 65 | 30 |
| Verantwortung in drei Sätzen | 45 | 46 | 21 |
| Folie 11 · Jede Zahl nachrechenbar | 15 | 13 | 6 |
| **Summe** | **245** | **287** | **132** |

Ergebnis: Fenster zusammen 245 s gleich 4:05, Grenze ist 4:45. Die reine Sprechzeit liegt bei etwa 132 s. Der Rest sind Folienwechsel und Pausen.

Belege Finale: F3 (Folie 2), F1 (Folie 5), F4, F9, F10, F11 (Folie 6).

---

## 5 Nicht sagen

- Keine Zeitersparnis ohne Messung. Kein „Minuten statt Tage“, bis ein Use-Case-Owner einen Wert nennt.
- Kein Personalabbau und keine Stelleneinsparung als Argument.
- Nie „die KI hat gerechnet“. Richtig: Die KI schreibt Code, das Programm rechnet.
- Keine Hostnamen, auch keine Rechner- oder Servernamen. Die Live-App heißt „öffentliche Demo“.
- Keine IPs, Zugangsdaten und Beispiel-IDs einzelner Verhältnisse.
- Keine Rückfrage-Nummern außer R1 (Geburtsmonat 13). Sonst: „Rückfrage an die Fachabteilung“.
- Keine Zahl, die nicht im Belegregister steht.
