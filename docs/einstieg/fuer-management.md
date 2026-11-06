# Für Entscheiderinnen und Entscheider

Diese Seite ist für das Management eines Sozialversicherungsträgers oder einer Statistikabteilung. Sie braucht fünf Minuten und kein Technikwissen. Danach wissen Sie, was StatAgent heute nachweislich kann, was ein Mensch weiter selbst tut, was der Betrieb braucht und wo die Grenzen liegen.

## In drei Sätzen

StatAgent erstellt aus den monatlichen Lieferungen (den Daten, die die Sozialversicherungsträger jeden Monat schicken) die Beschäftigtenstatistik, prüft sie und erklärt jede Auffälligkeit. Gebaut hat ihn das Team OneShotAndy in der KI Challenge 2026 (laut Veranstalter knapp 24 Stunden Zeit), mit erfundenen Daten des Veranstalters. Bewertet wird dieser Use Case 3; die anderen Teile des Repos beschreibt das [README](../../README.md).

## Das Problem

Die Aufgabenstellung des Veranstalters beschreibt den Weg einer amtlichen Statistik in sechs Schritten: Daten kommen an, werden geprüft und bereinigt, angereichert, gezählt, noch einmal geprüft und dann bereitgestellt. Die Daten haben Fehler. Manche lassen sich bereinigen, für andere muss die liefernde Stelle nachliefern. Eine falsche Zahl, die einmal veröffentlicht ist, lässt sich nicht still zurückholen.

Die Aufgabe verlangt deshalb vier Dinge zugleich: Die Rollen eines Statistikteams (Klassifikation, Datenmanagement, Qualitätssicherung, Reporting) müssen abgedeckt sein. Gerechnet wird von Programmen, die auch ohne KI laufen. Regeln liegen lesbar in der Datenbank. Und jede Änderung gibt ein Mensch mit Namen frei. Wie lange dieser Prozess in einem Haus heute dauert, sagt die Aufgabe nicht, und das Team hat es nicht gemessen.

## Was StatAgent tut

Der Grundsatz in einem Satz (Kernsatz aus [docs/sprache.md](../sprache.md)):

> Die KI schreibt Code und Regeln, gerechnet wird ohne KI, ein Mensch gibt mit Namen frei.

| Aufgabe | Wer sie erledigt | Nachweis |
|---|---|---|
| Lieferung eines Monats einlesen, 24 Monate von August 2024 bis Juli 2026 | Programm | [uc3/README.md](../../uc3/README.md) |
| Prüfen: 24 Prüfregeln suchen Auffälligkeiten und stufen sie ein | Programm | [Qualitätsberichte](../../abgabe/qualitaetsberichte/) |
| Zählen am Stichtag (letzter Tag des Monats) nach Regeln aus der Datenbank | Programm, ohne Sprachmodell | [abgabe/modelle.md](../../abgabe/modelle.md) |
| Qualitätsbericht je Monat und Aggregations-Sheet (die Tabellen der Statistik) erzeugen | Programm | [abgabe/README.md](../../abgabe/README.md) |
| Rückfrage an die Fachabteilung schreiben, mit Beleg | Programm schreibt, die Fachabteilung müsste antworten | [abgabe/rueckfragen/](../../abgabe/rueckfragen/) |
| Fragen an die Daten beantworten | Programm, ohne Sprachmodell | [abgabe/modelle.md](../../abgabe/modelle.md) |
| Änderungsauftrag in einem Satz verstehen und als Vorschlag formulieren | KI-Agent (Azure-Modell des Veranstalters) | [abgabe/modelle.md](../../abgabe/modelle.md) |
| Vorschlag freigeben, mit Vor- und Nachnamen | Mensch | [abgabe/protokoll.md](../../abgabe/protokoll.md) |
| Ministeriums-Lieferung (die Liste an das Ministerium) freigeben | Mensch; die Liste rechnet das Programm | [Beleg der Ministeriums-Lieferung](../../abgabe/ministerium_2026-07.beleg.md) |
| Das System selbst bauen | Team mit dem Entwicklungswerkzeug Claude Code | [abgabe/modelle.md](../../abgabe/modelle.md), Abschnitt „In der Entwicklung“ |

Die Regelstände heißen in der Oberfläche „Alte Regeln“ (`v1`) und „Nach den Änderungsaufträgen“ (`v2`). Die drei Änderungsaufträge der Aufgabe sind umgesetzt, jeder als Vorschlag eines Agenten mit Freigabe.

## Belegte Kennzahlen

| Zahl | Was sie sagt | Quelle |
|---|---|---|
| 24 Lieferungen, 10.152.292 Zeilen | So viele Daten hat StatAgent verarbeitet. Die Daten sind erfunden. | [Belegregister](../praesentation/belegregister.md), F3 |
| 2.880 von 2.880 | Den Beispielbericht August 2024 aus der Aufgabe (13 Tabellen) rechnet StatAgent aus den Rohdaten nach. Alle Zahlen stimmen. | [Belegregister](../praesentation/belegregister.md), F1 |
| 78.949 | So viele Beschäftigungsverhältnisse fehlen in der Lieferung Oktober 2025, jedes fünfte. StatAgent hat den Monat angehalten statt einen Einbruch zu melden. | [Qualitätsbericht 10/2025](../../abgabe/qualitaetsberichte/2025-10.md) |
| 72 von 72 | Wiederholte Monatsläufe mit denselben Daten und Regeln ergaben jedes Mal dieselbe Prüfsumme. | [abgabe/uc3-abnahme.md](../../abgabe/uc3-abnahme.md), Abschnitt 3 |
| 0 Modellaufrufe | Monatslauf, Qualitätsbericht und Fragen an die Daten brauchen kein Sprachmodell. | [Management-FAQ](../praesentation/management-faq.md), Frage 6 |
| rund 1 Cent | Modellkosten für einen Änderungsvorschlag zum Azure-Listenpreis. Alle Anläufe rund um die drei Aufträge zusammen: 39 bis 42 Cent. | [Belegregister](../praesentation/belegregister.md), F27 |

Alle weiteren Zahlen mit Herkunft stehen in [zahlen.md](zahlen.md).

## Warum man dem Ergebnis trauen kann

| Zusage | In einem Satz | Nachweis |
|---|---|---|
| Gleiche Daten und Regeln ergeben gleiche Zahlen | Gerechnet wird mit SQL und Python, und 72 Wiederholungsläufe hatten 72-mal dieselbe Prüfsumme. | [abgabe/uc3-abnahme.md](../../abgabe/uc3-abnahme.md), Abschnitt 3 |
| Jede Zahl hat einen Beleg | Jede Auffälligkeit im Qualitätsbericht trägt die Abfrage, mit der sie gezählt wurde, und der Beispielbericht ist Zahl für Zahl nachgerechnet. | [Qualitätsberichte](../../abgabe/qualitaetsberichte/), [Belegregister](../praesentation/belegregister.md) |
| Jede Änderung hat einen Namen | Das Programm verlangt Vor- und Nachnamen und lehnt Rollen wie „Team“ oder „Admin“ ab; jede Freigabe steht mit Zeitpunkt im Protokoll. | [freigabe.py](../../shared/py/plattform/freigabe.py), [abgabe/protokoll.md](../../abgabe/protokoll.md) |
| Fehler werden von echten Entwicklungen unterschieden | Jede Auffälligkeit bekommt eine Einstufung: „Fehler in den Daten“, „Kein Fehler: echt oder üblich“ oder „Noch nicht erklärt“ (in den Berichten „erklärt, Datenproblem“, „erklärt, plausibel“, „nicht erklärbar“); das gelingt teilweise, weil nur August 2024 einen Vergleichsbericht hat. | [Kriterien-Karte](../praesentation/kriterien-karte.md), Bereich 3 |

Offen gesagt: Vier Freigaben zu den Änderungsaufträgen hat eine KI-Sitzung im Auftrag des Verantwortlichen eingegeben. Er hat sie am selben Abend selbst mit Namen bestätigt. Das steht so im Protokoll, Abschnitt „Hinweise zu den Freigaben“.

## Was der Betrieb braucht

| Thema | Stand | Nachweis |
|---|---|---|
| Lokal und offline | Die Aufgabe verlangt es (Technische Regel 2). Der Monatslauf braucht kein Netz und kein Sprachmodell, gerechnet wird in einer PostgreSQL-Datenbank (Version 16). | [README](../../README.md), Abschnitt „Beispiellauf UC3 (Jury-Weg)“ |
| Modell austauschbar | Ein Schalter wählt das Modell. Standard ist das Azure-Modell des Veranstalters (Standort West Europe). Mistral aus der EU hat am selben Code geantwortet. Ein Modell im eigenen Haus (Ollama) ist angebunden, gelaufen ist es noch nicht. | [docs/models.md](../models.md), [README](../../README.md), Abschnitt „Modelle“ |
| Wenn das Modell ausfällt | Rechnen, Berichte und Fragen an die Daten laufen weiter. Nur neue Änderungsvorschläge warten. | [Management-FAQ](../praesentation/management-faq.md), Frage 15 |
| Datenschutz | Die Demo nutzt nur erfundene Daten des Veranstalters, sie liegen nicht im Repo. Ans Modell gehen nur Schema, Regeln und Summen; das Lese-Werkzeug der Agenten sperrt die Spalten mit den Kennungen von Personen und Beschäftigungsverhältnissen. Die Ministeriums-Liste mit Einzeldaten liegt nicht im öffentlichen Repo. | [README](../../README.md), Abschnitt „Grenzen und offene Punkte“; [werkzeuge.py](../../uc3/statagent/agenten/werkzeuge.py); [abgabe/README.md](../../abgabe/README.md) |
| Modellkosten | Rund 1 Cent je Änderungsvorschlag zum Listenpreis. Welcher der zwei Azure-Preise für die Bereitstellung gilt, ist nicht bekannt. | [Management-FAQ](../praesentation/management-faq.md), Frage 6 |
| Monatliche Betriebskosten | nicht gemessen | [Management-FAQ](../praesentation/management-faq.md), Frage 6 |
| Lizenz | Eigener Code unter MIT-Lizenz; die Ergebnisse stehen dem Dachverband uneingeschränkt zur Verfügung. | [README](../../README.md), Abschnitt „Lizenzen“ |

## Zeitersparnis

Nicht gemessen. Das Team kennt die Dauer des heutigen Prozesses in einem Haus nicht und nennt deshalb keine Ersparnis ([Management-FAQ](../praesentation/management-faq.md), Frage 7). Gemessen ist nur die Dauer von StatAgent selbst:

| Was | Dauer | Quelle |
|---|---|---|
| Alle 24 Lieferungen rechnen, frische Datenbank ohne Netz | 504 s nach „Alte Regeln“, 770 s nach „Nach den Änderungsaufträgen“; unter Last 793 s und 1.169 s | [Belegregister](../praesentation/belegregister.md), F28 |
| Vom Satz bis zum Änderungsvorschlag mit Zahlen | rund 3 Minuten, davon 3 bis 9 Sekunden beim Modell | [Belegregister](../praesentation/belegregister.md), F27 |
| Antwort auf eine Frage an die Daten (Testserver) | 0,4 bis 3,8 Sekunden | [Belegregister](../praesentation/belegregister.md), F29 |

## Grenzen

StatAgent ist ein Prototyp aus der KI Challenge, für die der Veranstalter knapp 24 Stunden Zeit gab. Er ist kein geprüftes Produkt für den Echtbetrieb.

| Grenze | Was das heißt | Nachweis |
|---|---|---|
| Nur erfundene Daten | Eine echte Lieferung hat StatAgent noch nie verarbeitet. | [README](../../README.md), Abschnitt „Grenzen und offene Punkte“ |
| Ein Vergleichsbericht | Nur August 2024 lässt sich gegen einen offiziellen Bericht prüfen. Ob in den anderen 23 Monaten alle Fehler gefunden sind, lässt sich nicht belegen. | [Kriterien-Karte](../praesentation/kriterien-karte.md), Bereich 3 |
| Zehn Rückfragen offen | Die Rückfragen R1 bis R10 sind geschrieben, aber nicht beantwortet. Bis dahin gilt je eine begründete Annahme. März und Oktober 2025 bleiben vorläufig. | [abgabe/rueckfragen/](../../abgabe/rueckfragen/), [abgabe/README.md](../../abgabe/README.md), Abschnitt „Stand der Zahlen“ |
| Grobe Gliederung | Gezählt wird nach Branchenabschnitt und Bundesland, weil die Lieferungen nicht mehr enthalten. | [Kriterien-Karte](../praesentation/kriterien-karte.md), Bereich 2 |
| Pensionen vorläufig | Die Pensionsmeldungen sind eingelesen, aber nicht mit Namen freigegeben; die öffentlich Bediensteten fehlen in den Meldungen. | [Prüfbericht Pensionen](../uc3/pensionen-pruefbericht.md), [Kriterien-Karte](../praesentation/kriterien-karte.md), Bereich 1 |
| Änderung getippt, nicht gesprochen | Änderungsaufträge gibt man als Text ein. Freie Fragen an die Daten sind nicht alle geprüft. | [Kriterien-Karte](../praesentation/kriterien-karte.md), Bereiche 4 und 5 |
| Kein Modell im eigenen Haus erprobt | Angebunden, aber nicht gelaufen. | [README](../../README.md), Abschnitt „Modelle“ |
| Keine rechtliche Prüfung | Zum AI Act gibt es nur eine eigene Einschätzung des Teams: StatAgent entscheidet über keine Person und keine Leistung. | [Management-FAQ](../praesentation/management-faq.md), Frage 18 |

## Mögliche nächste Schritte

Das sind Vorschläge aus den offenen Punkten im Repo, keine Zusagen.

1. Eine echte Lieferung statt der erfundenen verarbeiten ([Management-FAQ](../praesentation/management-faq.md), Frage 5).
2. Die Rückfragen R1 bis R10 der Fachabteilung stellen, damit März und Oktober 2025 endgültig werden können ([abgabe/README.md](../../abgabe/README.md)).
3. Die Dauer des heutigen Prozesses im Haus messen. Erst dann lässt sich eine Zeitersparnis angeben ([Management-FAQ](../praesentation/management-faq.md), Frage 7).
4. Ein Modell im eigenen Haus erproben, damit auch die Änderungsvorschläge ohne Cloud laufen ([README](../../README.md), Abschnitt „Modelle“).
5. Für einen dauerhaften Betrieb: Datenbank mit Sicherung und Lese-Kopie, der Rechenkern als langlebiger Dienst, fertig gebaute Programmpakete aus der CI ([docs/betrieb/skalierung.md](../betrieb/skalierung.md), Abschnitt 4).

## Weiter lesen

- [Übersicht dieses Ordners](README.md) und [Zahlen mit Herkunft](zahlen.md)
- [Für Außenstehende](fuer-aussenstehende.md) und [Stand der Use Cases](use-cases-stand.md)
- [Fragen des Managements mit Belegen](../praesentation/management-faq.md)
- [Kriterien-Karte: was erfüllt, teilweise oder offen ist](../praesentation/kriterien-karte.md)
- [Abgabe UC3](../../abgabe/README.md) und [Protokoll aller Freigaben](../../abgabe/protokoll.md)
- Öffentliche Demo: https://ki-challenge.gotzendorfer.at
