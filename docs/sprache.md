# Sprache: ein Wort für eine Sache

Gilt für alles, was Jury oder Publikum liest oder hört: Landingpage, App (UC1 bis UC4), Präsentation, README,
Texte im Qualitätsbericht, Voice. Ergänzt die Owner-Regel 15:4x (#116): einfach, menschlich, ohne Fachwissen
verständlich, keine Gedankenstriche, kein Marketing.

**Ausnahme Vorlagen:** Der Wortlaut der Vorlagen der Aufgabe (Qualitätsbericht, Rückfrage, Beispielbericht,
Ministeriums-Lieferung) bleibt unverändert, auch wo er Wörter enthält, die hier sonst nicht vorkommen sollen
(„erklärt – plausibel“, „Ebene (Satz / …)“, „Umfang (Sätze, Zellen)“). Die Regeln unten gelten für unsere eigenen
Sätze: Seiten, Folien, Sprechtext, Erklärungen und Freitext in den Berichten. Auf Seiten ohne Gedankenstrich
stehen die Einstufungen mit Komma („erklärt, plausibel“).

Im Code liegt das Glossar in `shared/ui/src/bausteine/glossar.ts` (Baustein `Begriff`). Diese Datei ist die Liste
dazu: welches Wort wir sagen, was es heißt und welches Wort wir dafür nicht nehmen. Neue Begriffe kommen zuerst
hierher, dann ins Glossar.

## Drei Regeln

1. **Wörter der Aufgabenstellung bleiben.** Die Jury kennt sie und sucht sie: Lieferung, Beschäftigungsverhältnis,
   Stichtag, Beispielbericht, Rückfrage, Revisionsbedarf, Qualitätsbericht und die drei Einstufungen der Vorlage.
   Beim ersten Auftreten auf einer Seite oder Folie steht eine Erklärung in einem Halbsatz daneben.
2. **Keine eigenen Kurzformen, keine Synonyme.** In eigenen Sätzen nie „Verhältnisse“, „Zellen“, „Sätze“, „Befunde“, „Datenabzug“,
   „Golden Set“. Eine Sache heißt überall gleich, auf der Landingpage wie in der App und auf den Folien.
3. **Jede große Zahl bekommt ein „das heißt“.** Wofür steht sie (je Monat oder zusammen)? Womit lässt sie sich
   vergleichen („jedes fünfte“)? Was wäre ohne StatAgent passiert? Vorlesetest: Den Satz kann man laut sagen, ohne
   dass jemand nachfragt.

## Ablauf

Überall dieselben sechs Verben, in dieser Reihenfolge. Die Szene der Landingpage zeigt die ersten vier.

| Wort | Was passiert | Schritt der Aufgabenstellung |
|---|---|---|
| Einlesen | die Lieferung eines Monats kommt unverändert in die Datenbank | 1 Anlieferung |
| Prüfen | Regeln suchen Auffälligkeiten und stufen sie ein | 2 Prüfen und bereinigen |
| Zählen | gezählt wird nach festen Regeln, am Stichtag | 3 Anreichern, 4 Aggregieren |
| Belegen | jede Zahl hat die Abfrage, die sie erzeugt; Gegenrechnung am Beispielbericht | 5 Ergebnisse prüfen |
| Freigeben | ein Mensch bestätigt mit Vor- und Nachnamen | Grundsatz 7 |
| Bereitstellen | Bericht, Qualitätsbericht und Ministeriums-Lieferung entstehen | 6 Bereitstellen |

„Lieferung“ allein meint immer die Daten, die hereinkommen. Die Lieferung ans Ministerium heißt immer
„Ministeriums-Lieferung“; Bericht und Qualitätsbericht heißen nie „Lieferung“.

## Wortliste

| Wort (immer so) | Erklärung als Glossar-Untertitel | Nicht verwenden (als Ersatz für das Wort links) |
|---|---|---|
| Beschäftigtenstatistik | die Statistik, die StatAgent jeden Monat erzeugt | Beschäftigungsstatistik (die Aufgabe nutzt beide, wir eines) |
| Lieferung, Monatslieferung | Die Daten, die die Sozialversicherungsträger jeden Monat schicken. | Datenabzug, Abzug, Datei, Batch |
| Zeile | ein Eintrag in einer Lieferung | Satz, Datensatz, Record |
| Beschäftigungsverhältnis | ein sozialversicherter Job; wer zwei Jobs hat, zählt zweimal | Verhältnis, VVH, Anstellung, Beschäftigte (das sind Personen) |
| Freier Dienstvertrag | ein Job ohne Anstellung, trotzdem sozialversichert | FD |
| Stichtag | der letzte Tag des Monats; gezählt wird jedes Beschäftigungsverhältnis, das an diesem Tag besteht | Monatsletzter |
| Auffälligkeit | etwas, das die Prüfung in einer Lieferung findet: ein Fehler oder etwas Ungewohntes | Befund, Anomalie, Treffer |
| erklärt, plausibel | ungewohnt, aber echt: zählt mit und wird vermerkt | |
| erklärt, Datenproblem | ein Fehler in den Daten mit bekannter Ursache; eine feste Regel behebt ihn | |
| nicht erklärbar | geht als Rückfrage an die Fachabteilung; der Monat bleibt vorläufig | offen, unklar |
| Rückfrage | eine Frage an die Fachabteilung mit Beleg; die Antwort wird zur Regel | Eskalation, Ticket |
| Beispielbericht | der Monatsbericht August 2024 aus der Aufgabe, 13 Tabellen im Layout des Dachverbands | Golden Set, Referenz, Musterbericht |
| Zahl (in einem Bericht) | eine einzelne Zahl in einer Tabelle | Zelle, Wert, Datenpunkt |
| Beleg | Zeigt, woher eine Zahl kommt: aus welcher Lieferung und mit welcher Abfrage sie gerechnet wurde. | Nachweis, Provenienz |
| Freigabe | Ein Mensch bestätigt mit Vor- und Nachname, dass eine Änderung gilt. Ohne Freigabe ändert sich nichts. | Approval |
| Revisionsbedarf | Eine schon veröffentlichte Zahl wäre mit den neuen Daten anders. Sie bleibt stehen, der Unterschied kommt in den Qualitätsbericht. | Revision, Korrektur |
| Qualitätsbericht | Bericht zu jeder Lieferung: was geprüft wurde, was auffiel und was das für die Zahlen heißt. | QA-Report |
| Lauf | eine Lieferung einmal ganz verarbeiten, vom Einlesen bis zur Zahl | Run, Pipeline, Job |
| Regel | eine Anweisung, wie eingelesen, geprüft oder gezählt wird; steht mit Datum und Freigabe in der Datenbank | Logik, Mapping |

Daten und Zahlen:
- Monate im Fließtext ausgeschrieben („Oktober 2025“), in engen Tabellen „10/2025“. Die Form „2025-10“ nur in Code
  und Abfragen.
- Zahlen mit Tausenderpunkt. Gerundet wird mit „rund“, nie mit „~“.

## Kernsätze

Diese Sätze tragen die Geschichte (Muster: Landingpage, `web/landing/texte/inhalt.ts`). Landingpage, Folien und Sprechtext verwenden sie wörtlich oder sinngemäß; die
Zahlen kommen aus `web/landing/daten/fakten.ts`.

- Jeden Monat schickt die Sozialversicherung eine Lieferung. Sie soll alle Beschäftigungsverhältnisse der letzten
  drei Monate enthalten, rund 420.000 Zeilen. Wir haben 24 davon, August 2024 bis Juli 2026, zusammen 10.152.292 Zeilen. Die Daten
  sind erfunden, in der Größe etwa ein Zehntel Österreichs.
- Im Oktober 2025 fehlt jedes fünfte Beschäftigungsverhältnis, 78.949 Stück. Im November sind fast alle wieder da:
  Die Lieferung war unvollständig. Ohne Prüfung hätte die Statistik einen Einbruch gezeigt, den es so nicht gab.
- Den Beispielbericht der Aufgabe, 13 Tabellen mit 2.880 Zahlen, rechnet StatAgent aus den Rohdaten nach. Alle
  2.880 stimmen.
- Die KI schreibt Code und Regeln, gerechnet wird ohne KI, ein Mensch gibt mit Namen frei.
