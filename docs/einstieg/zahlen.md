# Das Projekt in Zahlen

Diese Seite ist das Zahlen-Register der Doku. Sie ist für alle, die wissen wollen, mit welchen Zahlen das Team gearbeitet hat, und die jede Zahl selbst nachprüfen wollen. Jede Zeile nennt, was die Zahl bedeutet, worüber sie gemessen ist, wann, und wo man sie findet: als Link ins Repo oder als Befehl, mit dem sie gezählt wurde.

**So liest man die Tabellen.** „Stand“ ist der Zeitpunkt der Messung. Zählbefehle laufen an der Repo-Wurzel auf dem Stand `48761dcc` (`main`, 06.11.2026). Die Messungen stammen von Ständen desselben Morgens, nicht vom abgegebenen Stand; abgegeben ist der Stand von `main` beim letzten Push. Die Daten der Challenge sind synthetisch, also erfunden ([CHECKLISTE](../../abgabe/CHECKLISTE.md), letzte Zeile). Die Kennungen F1 bis F30 verweisen auf das [Belegregister](../praesentation/belegregister.md); dort stehen auch die SQL-Abfragen der Gegenrechnung. Die zwei Regelstände heißen in der Oberfläche „Alte Regeln“ (technisch `v1`) und „Nach den Änderungsaufträgen“ (technisch `v2`).

## 1 Die Daten

Eine **Lieferung** sind die Daten, die die Sozialversicherung jeden Monat schickt. Eine **Zeile** ist ein Eintrag darin.

| Zahl | Was sie bedeutet | Worüber gemessen | Stand | Quelle |
|---|---|---|---|---|
| 24 | So viele Monatslieferungen hat das Team verarbeitet. | Lieferungen August 2024 bis Juli 2026 (08/2024 bis 07/2026) | 05.11.2026 | [Belegregister F3](../praesentation/belegregister.md), [uc3/README.md](../../uc3/README.md) |
| 10.152.292 | So viele Zeilen haben alle 24 Lieferungen zusammen. | Tabelle `roh.lieferung`, `SELECT count(*) FROM roh.lieferung` | 05.11.2026 | [Belegregister F3](../praesentation/belegregister.md) |
| 392.284 | Zeilen der ersten Lieferung. | Lieferung 08/2024 | 05.11.2026 | [Belegregister F2](../praesentation/belegregister.md), [Qualitätsbericht 2024-08](../../abgabe/qualitaetsberichte/2024-08.md) |
| 432.086 | Zeilen der Lieferung Juni 2025. | Lieferung 06/2025 | 05.11.2026 | [Belegregister F10](../praesentation/belegregister.md) |
| 434.104 und 345.078 | Zeilen der Lieferungen September und Oktober 2025. Im Oktober fehlt rund ein Fünftel. | Lieferungen 09/2025 und 10/2025 | 05.11.2026 | [Belegregister F11](../praesentation/belegregister.md), [Qualitätsbericht 2025-10](../../abgabe/qualitaetsberichte/2025-10.md) |
| 13 Tabellen, 2.880 Zahlen | Umfang des Beispielberichts, also des offiziellen Monatsberichts August 2024 aus der Aufgabe. | Tab1 bis Tab13 des Beispielberichts | 05.11.2026 | [Belegregister F1](../praesentation/belegregister.md) |
| 28 Dateien, 9 Formate | Jahresmeldungen der Pensionsversicherungsträger, die eingelesen sind. Jeder Träger liefert in einem eigenen Aufbau. | Pensionsmeldungen 2018 bis 2025 | Prüfbericht im Repo | [Prüfbericht Pensionen](../uc3/pensionen-pruefbericht.md) |
| 880 | Einzelwerte der Pensionsmeldungen, je Bereich, Pensionsart und Geschlecht. | alle 28 Dateien | Prüfbericht im Repo | [Prüfbericht Pensionen](../uc3/pensionen-pruefbericht.md) |
| 394, davon 0 abweichend | Summenzeilen in den Pensionsdateien, die nachgerechnet wurden. | alle 28 Dateien | Prüfbericht im Repo | [Prüfbericht Pensionen](../uc3/pensionen-pruefbericht.md) |
| 701 und 711 | Codes von ÖNACE 2008 und ÖNACE 2025 (die Branchenliste Österreichs) bis zur tiefsten Ebene, der Unterklasse. | Klassifikationen in der Datenbank | 06.11.2026, `main` `5328291` | [Kriterien-Karte, Bereich 2](../praesentation/kriterien-karte.md) |
| 1.115 und 65 | Übergänge von ÖNACE 2008 nach 2025: 1.115 auf der tiefsten Ebene, 65 auf der Ebene der Abschnitte (darunter 2003 nach 2008). | Tabelle `stat.uebergang` | 06.11.2026, `main` `5328291` | [Kriterien-Karte, Bereich 2](../praesentation/kriterien-karte.md) |
| 674 und 16 | Übergänge bei Regionen: 674 für Gemeinden, 16 für Bezirke, aus den amtlichen Änderungslisten. | Tabelle `stat.uebergang` | 06.11.2026, `main` `5328291` | [Kriterien-Karte, Bereich 2](../praesentation/kriterien-karte.md) |

## 2 Die Ergebnisse

Gezählt werden **Beschäftigungsverhältnisse**: ein sozialversicherter Job; wer zwei Jobs hat, zählt zweimal. Der **Stichtag** ist der letzte Tag des Monats.

| Zahl | Was sie sagt | Worüber gemessen | Stand | Quelle |
|---|---|---|---|---|
| 2.880 von 2.880 | Alle Zahlen des Beispielberichts rechnet StatAgent aus den Rohdaten genau nach, keine weicht ab. | Beispielbericht 08/2024, `uv run uc3 eichen --lieferung 2024-08` | 05.11.2026 | [Belegregister F1](../praesentation/belegregister.md) |
| 392.236 | Beschäftigungsverhältnisse am 31.08.2024. Davon 211.603 Männer und 180.633 Frauen. | Lieferung 08/2024, Alte Regeln | 05.11.2026 | [Belegregister F14](../praesentation/belegregister.md), [Protokoll, Abschnitt 4](../../abgabe/protokoll.md) |
| 399.027 | Beschäftigungsverhältnisse am 31.07.2026 nach den Alten Regeln. | Lieferung 07/2026, gezählt am Stichtag | 05.11.2026 20:15 | [Abnahme UC3, Abschnitt 2](../../abgabe/uc3-abnahme.md) |
| 407.604 | Beschäftigungsverhältnisse im Juli 2026 nach den Änderungsaufträgen. Gezählt wird jetzt das ganze Monat, nicht nur der Stichtag, deshalb ist die Zahl höher. Ein unabhängiger Filter auf die Rohdatei ergibt dieselbe Zahl. | Lieferung 07/2026, Nach den Änderungsaufträgen | 05.11.2026 20:15 | [Abnahme UC3, Abschnitt 2](../../abgabe/uc3-abnahme.md) |
| 78.949 | Beschäftigungsverhältnisse, die am 30.09.2025 bestanden und in der Lieferung Oktober 2025 ganz fehlen. Das ist jedes fünfte (20,0 % von 394.200). 78.733 davon sind im November wieder da. | Lieferungen 09/2025, 10/2025 und 11/2025 | 05.11.2026 | [Belegregister F11](../praesentation/belegregister.md), [Qualitätsbericht 2025-10](../../abgabe/qualitaetsberichte/2025-10.md) |
| 313.154 gegen 394.200 | Bestand Oktober 2025 aus der Lieferung allein gegen den Vormonat. Der Unterschied von 81.046 ist eine andere Messung als 78.949: Er vergleicht Bestände, nicht fehlende Beschäftigungsverhältnisse. | Lieferungen 09/2025 und 10/2025 | 05.11.2026 | [Belegregister F17](../praesentation/belegregister.md) |
| 77.746 und 390.900 | Für Oktober 2025 einmal aus der Vorlieferung übernommene Beschäftigungsverhältnisse und der daraus folgende vorläufige Bestand. Der Monat bleibt angehalten. | Lauf 10/2025, Regel E07 | 05.11.2026 | [Qualitätsbericht 2025-10, Abschnitt 1](../../abgabe/qualitaetsberichte/2025-10.md) |
| 1.663 und 1.523 | Doppelte Zeilen in der Lieferung März 2025. Ohne Bereinigung wären 1.523 Beschäftigungsverhältnisse doppelt gezählt. | Lieferung 03/2025 | 05.11.2026 | [Belegregister F8](../praesentation/belegregister.md) |
| 1.492 | Freie Dienstverträge (Jobs ohne Anstellung, trotzdem versichert), die im Februar 2025 bestanden und im März 2025 ganz fehlen: 1.131 Angestellte und 361 Arbeiter. 1.470 davon werden fortgeschrieben. | Lieferungen 02/2025 und 03/2025 | 05.11.2026 | [Belegregister F9](../praesentation/belegregister.md) |
| 388.115 von 432.086 | Zeilen ohne Beginn im Juni 2025, weil Beginn und Ende vertauscht geliefert wurden. Ohne Tausch bestünden am 30.06.2025 nur 21 Beschäftigungsverhältnisse, mit Tausch 394.252. | Lieferung 06/2025 | 05.11.2026 | [Belegregister F10](../praesentation/belegregister.md) |
| 370 | Beschäftigungsverhältnisse am 31.08.2024 mit dem Monat 13 im Geburtsdatum, den es nicht gibt. | Lieferung 08/2024 | 05.11.2026 | [Belegregister F4](../praesentation/belegregister.md) |
| 7 | Beschäftigungsverhältnisse mit einem Alter von 117 bis 153 Jahren. Sie zählen mit Alter „unbekannt“. | Lieferung 08/2024 | 05.11.2026 | [Belegregister F5](../praesentation/belegregister.md) |
| 1.996 | Beschäftigungsverhältnisse, bei denen Bundesland und Branche fehlen, immer beide zusammen. | Lieferung 08/2024, am Stichtag | 05.11.2026 | [Belegregister F7](../praesentation/belegregister.md) |
| 50 | Beschäftigungsverhältnisse mit alten Branchencodes aus ÖNACE 2003. Sie zählen zu Abschnitt C (Herstellung von Waren). | Lieferung 08/2024, am Stichtag | 05.11.2026 | [Belegregister F6](../praesentation/belegregister.md) |
| 189.170 von 386.299 | Beschäftigungsverhältnisse, die am 31.12.2024 in der Lieferung Jänner 2025 einen anderen Branchen-Abschnitt tragen als in der Lieferung davor (48,97 %). Grund ist der Wechsel auf ÖNACE 2025, keine echte Entwicklung. Hinweis: Das Belegregister hat diese Zahl gestrichen, weil es keine eigene Abfrage dazu hat; der vom Programm erzeugte Bericht nennt sie. | Lieferungen 12/2024 und 01/2025 | 05.11.2026 | [Qualitätsbericht 2025-01](../../abgabe/qualitaetsberichte/2025-01.md), Abschnitt „Wechsel der ÖNACE“ |
| 260 weniger | Revisionsbedarf für Dezember 2024: 387.390 laut Lieferung Dezember, 387.130 laut Lieferung Jänner. Die veröffentlichte Zahl bleibt, der Unterschied steht im Qualitätsbericht. | Lieferungen 12/2024 und 01/2025 | 05.11.2026 | [Belegregister F12](../praesentation/belegregister.md) |
| 7.498 | Beschäftigungsverhältnisse in Wien im Gesundheits- und Sozialwesen (ÖNACE 2025 Abschnitt R) am 31.03.2025, vorläufig. Das ist die Beispielfrage, die durch alle Use Cases läuft. | Lieferung 03/2025, Alte Regeln, `uv run uc3 frage …` | 05.11.2026 18:31 | [Belegregister F18](../praesentation/belegregister.md) |
| 12.289 | Beamte im Juli 2026 nach den Änderungsaufträgen. Der vorgeführte Auftrag „Beamte zählen nicht mehr mit“ senkt den Gesamtwert von 407.604 auf 395.315. Die Zahl 12.289 steht auch als Wert in `aggregationen_v2.xlsx`. | Vorführ-Adresse auf einer Kopie der Abgabe-Datenbank, bis zum Vorschlag | 06.11.2026 02:36 | [Demo-Drehbuch, D2](../praesentation/demo-drehbuch.md), [Kriterien-Karte, Bereich 5](../praesentation/kriterien-karte.md) |
| 236.961 | Angestellte im August 2024 nach Auftrag 1, der Dienstvertrag und freien Dienstvertrag zusammenlegt (vorher 235.819 und 1.142). Der Gesamtwert bleibt 392.236. | Probe 08/2024 auf der Freigabe-Seite | 05.11.2026, abgeglichen 06.11.2026 06:17 | [Belegregister F19](../praesentation/belegregister.md) |
| 32.741 | Personen in der Ministeriums-Lieferung Juli 2026. Ohne die alten ÖNACE-2003-Codes wären es 32.713. | Berichtsmonat 07/2026 und elf Monate davor | 05.11.2026 19:35 | [Beleg Ministeriums-Lieferung](../../abgabe/ministerium_2026-07.beleg.md), [abgabe/README.md](../../abgabe/README.md) |
| 3,42 % | Fluktuation im Oktober 2024: 12.215 Zugänge, 14.557 Abgänge, Bestand 391.033. | Lieferung 10/2024, Alte Regeln | 05.11.2026 | [Belegregister F23](../praesentation/belegregister.md) |
| 213.129 und 185.898 | Männer und Frauen im Juli 2026. | Lieferung 07/2026, Alte Regeln | 05.11.2026 | [Belegregister F22](../praesentation/belegregister.md) |
| 28.548 | Beschäftigungsverhältnisse im Bau im Juli 2026, einer von 23 Abschnitten mit Summe 399.027. | Lieferung 07/2026 | 05.11.2026 | [Belegregister F24](../praesentation/belegregister.md) |
| 23.809 bis 24.679 | Spanne der Monatswerte im Bau im Jahr 2025. | Lieferungen 2025 | 05.11.2026 | [Belegregister F25](../praesentation/belegregister.md) |
| 41.626 | Beschäftigungsverhältnisse unter 25 Jahren im Juli 2026. Nicht gegen die unabhängige Nachrechnung geprüft. | online gefragt | 06.11.2026 | [Kriterien-Karte, Bereich 4](../praesentation/kriterien-karte.md), [Demo-Drehbuch, D3](../praesentation/demo-drehbuch.md) |
| 72 von 72 | Wiederholungsläufe mit denselben Daten und Regeln, die dieselbe Prüfsumme ergeben haben (48 Alte Regeln, 24 Nach den Änderungsaufträgen). | Abgabe-Datenbank, `meta.lauf` | 05.11.2026 20:10 | [Abnahme UC3, Abschnitt 3](../../abgabe/uc3-abnahme.md) |
| 2.584.909 | Pensionen insgesamt 2025, Summe über alle Träger. Vorläufig, noch nicht mit Namen freigegeben. | Pensionsmeldungen 2025 | Prüfbericht im Repo | [Prüfbericht Pensionen](../uc3/pensionen-pruefbericht.md) |

Die Monatswerte aller 22 veröffentlichten Monate stehen mit Prüfsumme im [Protokoll, Abschnitt 4](../../abgabe/protokoll.md).

## 3 Die Qualitätsprüfung

Ein **Qualitätsbericht** sagt zu jeder Lieferung, was geprüft wurde, was auffiel und was das für die Zahlen heißt. Jede **Auffälligkeit** bekommt eine von drei Einstufungen. In den Berichten heißen sie „erklärt, Datenproblem“, „erklärt, plausibel“ und „nicht erklärbar“, in der Weboberfläche „Fehler in den Daten“ (die Ursache ist bekannt, eine feste Regel behandelt sie), „Kein Fehler: echt oder üblich“ (ungewohnt, aber echt oder üblich, etwa Saison oder Nachmeldungen) und „Noch nicht erklärt“ (geht als Rückfrage an die Fachabteilung). Die Zuordnung steht in [`einstufung-gruppen.ts`](../../web/components/uc3/einstufung-gruppen.ts).

| Zahl | Was sie bedeutet | Worüber gemessen | Stand | Quelle |
|---|---|---|---|---|
| 24 und 24 | Qualitätsberichte je Regelstand, einer je Monat. | `ls abgabe/qualitaetsberichte \| wc -l`, ebenso `qualitaetsberichte_v2` | `48761dcc` | [abgabe/qualitaetsberichte](../../abgabe/qualitaetsberichte/) |
| 219 | Auffälligkeiten in allen 24 Berichten nach den Alten Regeln (218 nach den Änderungsaufträgen). | Zeilen der Tabelle in Abschnitt 2 jedes Berichts: `awk '/^## 2/{f=1;next} /^## /{f=0} f && /^\| [0-9]+ \|/' abgabe/qualitaetsberichte/*.md \| wc -l` | `48761dcc` | Zählbefehl links |
| 103 | davon „erklärt, Datenproblem“ | dieselben Zeilen, Spalte Einstufung: `… \| awk -F'\|' '$7 ~ /Datenproblem/' \| wc -l` | `48761dcc` | Zählbefehl links |
| 78 | davon „erklärt, plausibel“, in der Weboberfläche „Kein Fehler: echt oder üblich“ | wie oben, `/plausibel/` | `48761dcc` | Zählbefehl links |
| 38 | davon „nicht erklärbar“ | wie oben, `/nicht erkl/` | `48761dcc` | Zählbefehl links |
| 8 | Arten von Fehlern in den Daten, jede mit einer Regel oder einem Halt (Belege F4 bis F11). | alle 24 Lieferungen | 06.11.2026 | [Kriterien-Karte, Bereich 3](../praesentation/kriterien-karte.md) |
| 24 | Prüfregeln P01 bis P24, die jede Lieferung prüfen. | Regelstand Alte Regeln | 05.11.2026 | [Belegregister F15](../praesentation/belegregister.md) |
| 13 | Begründete Annahmen A1 bis A13 mit Beleg-Abfrage (zehn als eigener Abschnitt, A11 bis A13 im Nachtrag). | `grep -c -E "^## A[0-9]+ " docs/plan/uc3/annahmen.md` ergibt 10, dazu Tabelle im Nachtrag | `48761dcc` | [annahmen.md](../plan/uc3/annahmen.md) |
| 10 | Annahmen F1 bis F10, die in den Qualitätsberichten stehen. | `grep -h -o -E "Annahme F[0-9]+" abgabe/qualitaetsberichte/*.md \| sort -u \| wc -l` | `48761dcc` | Zählbefehl links |
| 10 | Rückfragen an die Fachabteilung, R1 bis R10, mit Beleg. Bis zur Antwort gilt je eine begründete Annahme. | `ls abgabe/rueckfragen \| wc -l` | `48761dcc` | [abgabe/rueckfragen](../../abgabe/rueckfragen/) |

**Welche Prüfregeln wie oft angeschlagen haben** (Berichte nach den Alten Regeln, gleiche Zählung wie oben, gruppiert nach der Regel in Klammern am Ende der Beschreibung):

| Prüfregel | Worum es geht | Monate mit Auffälligkeit | Einstufung |
|---|---|---|---|
| P04 | Monat 13 im Geburtsdatum | 24 | 24 Datenproblem |
| P06 | Alter, das nicht stimmen kann | 24 | 24 Datenproblem |
| P10 | Bundesland und Branche fehlen | 24 | 24 Datenproblem |
| P11 | alte Branchencodes aus ÖNACE 2003 | 24 | 24 Datenproblem |
| P19 | zweites, gleichartiges Beschäftigungsverhältnis derselben Person | 24 | 24 nicht erklärbar |
| P07 | Beschäftigungsverhältnisse von Menschen ab 75 Jahren | 23 | 23 plausibel |
| P16 | Beschäftigungsverhältnisse des Vormonats fehlen | 23 | 22 plausibel, 1 Datenproblem (10/2025) |
| P23 | frühere Monate sehen anders aus (Revisionsbedarf) | 23 | 22 plausibel, 1 nicht erklärbar |
| P14 | starker Sprung einer Gruppe | 22 | 11 plausibel (Saison), 11 nicht erklärbar |
| P18 | Welle bei einem Merkmal | 2 (05/2025, 02/2026) | 2 nicht erklärbar |
| P01, P13 | doppelte Zeilen; eine Ausprägung verschwindet | 1 (03/2025) | Datenproblem |
| P03 | Beginn und Ende vertauscht | 1 (06/2025) | Datenproblem |
| P15, P17 | Bestand und Zeilenzahl brechen ein | 1 (10/2025) | Datenproblem |
| P24 | Lieferumfang | 1 (08/2024) | Datenproblem |

Zusätzlich erklärt der Bericht Jänner 2025 den Wechsel von ÖNACE 2008 auf ÖNACE 2025 ausdrücklich als Umstellung der Klassifikation und nicht als echte Entwicklung ([Qualitätsbericht 2025-01](../../abgabe/qualitaetsberichte/2025-01.md)).

## 4 Regeln und Änderungen

Eine **Regel** ist eine Anweisung, wie eingelesen, geprüft oder gezählt wird. Sie steht mit Datum und Freigabe in der Datenbank. **Freigabe** heißt: Ein Mensch bestätigt mit Vor- und Nachnamen, dass eine Änderung gilt.

| Zahl | Was sie bedeutet | Worüber gemessen | Stand | Quelle |
|---|---|---|---|---|
| 39 | Regeln im Regelstand Alte Regeln: 24 Prüfregeln und 15 Regeln zum Einlesen, Zuordnen und Zählen. | Regelfreigabe `v1`; `docs/plan/uc3/regeln-v1.csv` hat 39 Datenzeilen (`wc -l` ergibt 40 mit Kopfzeile) | 05.11.2026 16:12 | [Protokoll, Abschnitt 3](../../abgabe/protokoll.md), [regeln-v1.csv](../plan/uc3/regeln-v1.csv), [Belegregister F15](../praesentation/belegregister.md) |
| 39 | Regeln im Regelstand Nach den Änderungsaufträgen, freigegeben in zwei Schritten: die geänderte Regel R6 und 38 weitere. | Regelfreigaben `v2` | 05.11.2026 16:53 und 16:54 | [Protokoll, Abschnitt 3](../../abgabe/protokoll.md) |
| 1 | Regel im Regelstand `ministerium`: `M01_personentage_ministerium`. | Regelfreigabe `ministerium` | 05.11.2026 16:54 | [Protokoll, Abschnitt 3](../../abgabe/protokoll.md) |
| 3 von 3 | Änderungsaufträge der Aufgabe, als Vorschläge 24, 25 und 26 von den eigenen Agenten formuliert und mit Namen freigegeben. | Protokoll, Abschnitt 2 | 05.11.2026 16:53 bis 16:54 | [Protokoll](../../abgabe/protokoll.md) |
| 29 | Einträge mit Name und Zeitpunkt im Protokoll der Änderungen: 1 Regelstand Alte Regeln, 22 veröffentlichte Monate, 3 Änderungsaufträge, 1 Regelstand Nach den Änderungsaufträgen, 1 Bestätigung, 1 Ministeriums-Lieferung. | `grep -c "^\| 05.11.2026" abgabe/protokoll.md` | `48761dcc` | [Protokoll, Abschnitt 1](../../abgabe/protokoll.md) |
| 4 | Freigaben, die eine KI-Sitzung im Auftrag eingegeben hat. Der Verantwortliche hat sie am selben Abend um 18:22 selbst mit Namen bestätigt. | Vorschläge 24 bis 26 und Regelstand `v2` | 05.11.2026 18:22 | [Protokoll, Hinweise zu den Freigaben](../../abgabe/protokoll.md) |
| 22 von 24 | Monate, die veröffentlicht und damit endgültig sind. März und Oktober 2025 bleiben vorläufig, bis die Fachabteilung antwortet. | Regelstand Alte Regeln | 05.11.2026 16:13 bis 16:14 | [Protokoll, Abschnitt 4](../../abgabe/protokoll.md), [abgabe/README.md](../../abgabe/README.md) |
| 32.741 Personen, 1 Kopfzeile | Ministeriums-Lieferung 07/2026: Arbeiter mit Dienst- oder freiem Dienstvertrag in Abschnitt C, mindestens 200 Tage in 12 Monaten (01.08.2025 bis 31.07.2026). Die Datei enthält Einzeldaten und liegt nicht im Repo, der Beleg mit Prüfsumme schon. | Regel M01, Parameter im Beleg | 05.11.2026 19:35 | [Beleg Ministeriums-Lieferung](../../abgabe/ministerium_2026-07.beleg.md) |
| 14 | Alte Branchencodes DA bis DN, die in der Ministeriums-Lieferung zu Abschnitt C zählen. | Parameter `altcodes_als_abschnitt` | 05.11.2026 | [Beleg Ministeriums-Lieferung](../../abgabe/ministerium_2026-07.beleg.md) |
| 13 von 14 | Unbekannte Änderungswünsche, die auf Kopien der Abgabe-Datenbank zu einem passenden Vorschlag führten. Nicht bestanden hat eine Prüfschwelle je Bundesland, die es nicht gibt. | Proben vor der Vorführung | 06.11.2026 | [Kriterien-Karte, Bereich 5](../praesentation/kriterien-karte.md) |

## 5 Die Software

Gezählt ohne Ausführen, auf dem Stand `48761dcc`. Die Zahl der Testdateien sagt nichts darüber, ob die Tests bestehen.

| Zahl | Was sie bedeutet | Zählbefehl | Stand |
|---|---|---|---|
| 106 | Python-Testdateien (`test_*.py`): UC3 48, UC2 25, gemeinsamer Kern 17, UC1 13, Abnahme- und Abgabe-Skripte 2, Präsentationswerkzeug 1. | `git ls-tree -r --name-only 48761dcc \| grep -E '(^\|/)test_[^/]*\.py$' \| wc -l` | `48761dcc` |
| 1.269 | Testfunktionen in diesen Dateien. | `git grep -h -E '^\s*(async )?def test_' 48761dcc -- '*test_*.py' \| wc -l` | `48761dcc` |
| 7 | UC3-Testdateien, die gegen die echten Daten laufen (Markierung `daten`), etwa der Vergleich mit dem Beispielbericht. | `git grep -l -E 'mark\.daten' 48761dcc -- uc3/tests \| wc -l` | `48761dcc` |
| 80 | Testdateien für Weboberfläche und Bausteine (`*.test.*`, `*.spec.*`): 63 unter `web/`, 17 unter `shared/ui/`. | `git ls-tree -r --name-only 48761dcc \| grep -E '\.(test\|spec)\.(ts\|tsx\|js\|mjs)$' \| wc -l` | `48761dcc` |
| 27 | Seiten der Weboberfläche. | `find web/app -name page.tsx \| wc -l` | `48761dcc` |
| 81 | Laufdateien der Abnahme, also gespeicherte Prüfläufe. | `ls docs/abnahme/laeufe \| wc -l` | `48761dcc` |

**Belegte Abnahmen** laut [Abnahme-Übersicht](../abnahme/README.md), Stand 05.11.2026 16:37: Der Weg der Jury auf einer frischen Datenbank mit Vergleich zum Beispielbericht und Wiederholbarkeit ist „bestanden“ (#66), ebenso der Modell-Schalter mit drei Anbietern (#63) und der UC3-Teil des gemeinsamen Einstiegs (#95). Die Vorprüfung der Oberfläche gegen die Entwürfe war zu diesem Zeitpunkt „nicht bestanden“ (#64). Das Ergebnis des [Schlusslaufs](../abnahme/SCHLUSSLAUF.md) vom 06.11.2026 steht unten in Abschnitt 8.

**Zeilen nach Sprache.** Physische Zeilen, Leerzeilen und Kommentare mitgezählt, Tests eingeschlossen. Befehl je Endung: `git ls-tree -r --name-only 48761dcc | grep -E '\.py$' | tr '\n' '\0' | xargs -0 cat | wc -l` (Arbeitsbaum sauber auf diesem Stand).

| Sprache (Endung) | Dateien | Zeilen |
|---|---|---|
| Python (`.py`) | 277 | 77.176 |
| TypeScript (`.ts`) | 162 | 18.826 |
| TypeScript mit Oberfläche (`.tsx`) | 142 | 16.595 |
| Markdown (`.md`) | 190 | 28.405 |
| CSS (`.css`) | 10 | 3.661 |
| SQL (`.sql`) | 34 | 2.508 |
| Shell (`.sh`) | 16 | 1.964 |
| JavaScript (`.mjs`, `.js`) | 10 | 1.053 |

## 6 Das Projekt

Diese Zahlen kommen aus dem GitLab-Projekt, gemessen am 06.11.2026 um 06:34, und wurden nicht neu gemessen. Nur die Commits sind im Repo gezählt.

| Zahl | Was sie bedeutet | Worüber gemessen | Stand | Quelle |
|---|---|---|---|---|
| 03.11.2026 07:47 | Erster Commit im Repo. | Commits auf `main` | `48761dcc` | `git log --reverse --format=%ad 48761dcc`, erste Zeile |
| 05.11.2026 12:10 | Wahl von Use Case 3, festgehalten im Commit `e935ede` („Select use case uc3“). | Commits auf `main` | `48761dcc` | `git log --grep="Select use case"` |
| gegen 14:35 | Die Startseite ist am 05.11.2026 öffentlich erreichbar. | erste Auslieferung der öffentlichen Seite | 06.11.2026 06:34 | GitLab-Projekt, gemessen 06.11.2026 06:34 |
| knapp 21 Stunden | Zeit zwischen der Wahl von Use Case 3 (05.11. 12:10) und der Abgabe (06.11. 09:00), gerechnet aus diesen zwei Zeitpunkten. | | 06.11.2026 | Zeitpunkte oben, Abgabezeit aus [CHECKLISTE](../../abgabe/CHECKLISTE.md) |
| 202 | Aufgaben (Issues) im GitLab-Projekt, davon 58 erledigt. | alle Issues des Projekts | 06.11.2026 06:34 | GitLab-Projekt, gemessen 06.11.2026 06:34 |
| 323 | Merge Requests (Änderungsanträge auf `main`), davon 298 gemergt. Median vom Anlegen bis zum Merge: 13,9 Minuten. | alle Merge Requests | 06.11.2026 06:34 | GitLab-Projekt, gemessen 06.11.2026 06:34 |
| 733 | Prüfläufe der CI (automatische Prüfung bei jeder Änderung), davon 568 erfolgreich. | alle Pipelines, 05.11. 12:41 bis 06.11. 06:33 | 06.11.2026 06:34 | GitLab-Projekt, gemessen 06.11.2026 06:34 |
| 1.395 | Commits, die von `main` erreichbar sind, davon 863 ohne Merge-Commits. | `git rev-list --count 48761dcc`, mit `--no-merges` | `48761dcc` | Zählbefehl links |

## 7 Modelle und Kosten

| Zahl oder Modell | Wofür | Worüber gemessen | Stand | Quelle |
|---|---|---|---|---|
| 0 Modellaufrufe | Monatslauf, Prüfung, Qualitätsbericht, Aggregations-Sheet, Ministeriums-Lieferung und Fragen an die Daten rechnen ohne Sprachmodell. | Betrieb UC3 | 05.11.2026 | [abgabe/modelle.md](../../abgabe/modelle.md), [Management-FAQ, Frage 6](../praesentation/management-faq.md) |
| Azure `gpt-5-4-mini` | Modell des Veranstalters. Die eigenen Agenten formulieren damit Änderungsaufträge als Vorschlag. | kurzer Probeaufruf, Antwort nach 0,9 Sekunden | 05.11.2026 16:17 | [abgabe/modelle.md](../../abgabe/modelle.md), [docs/models.md](../models.md) |
| Mistral | Zweitanbieter aus der EU, gleiche Schnittstelle. Projektbudget 10 €. | kurzer Probeaufruf, Antwort nach 1,4 Sekunden | 05.11.2026 16:17 | [docs/models.md](../models.md), [Konfiguration, Modelle](konfiguration.md#modelle) |
| Ollama | Notnagel ohne Netz. Angebunden, gelaufen ist es noch nicht. | | 05.11.2026 | [Konfiguration, Modelle](konfiguration.md#modelle) |
| Claude Opus 5.5 | Damit hat das Team den Code geschrieben. Im Betrieb nur für UC1 und UC2, nie für UC3. | | 05.11.2026 | [abgabe/modelle.md](../../abgabe/modelle.md), [docs/models.md](../models.md) |
| 2 Aufrufe je Auftrag | Modellaufrufe je Änderungsauftrag 1 bis 3; Kosten 1,0 bis 1,4 Cent je Auftrag zum Listenpreis. | Protokoll der Modellaufrufe (nicht im Repo) | 05.11.2026 | [Management-FAQ, Frage 6](../praesentation/management-faq.md), [Belegregister F27](../praesentation/belegregister.md) |
| 50 Aufrufe, 39 bis 42 Cent | Alle Anläufe rund um die drei Änderungsaufträge, 457.462 Tokens hinein und 19.342 heraus (Tokens sind die Wortteile, nach denen ein Modell abrechnet). | Protokoll der Modellaufrufe (nicht im Repo) | 05.11.2026 | [Belegregister F27](../praesentation/belegregister.md) |
| 2 Aufrufe, 1,2 bis 1,3 Cent | typischer Agentenlauf (Median aus 246 Läufen in den Proben). | Protokoll der Modellaufrufe (nicht im Repo) | 05.11.2026 | [Management-FAQ, Frage 6](../praesentation/management-faq.md) |
| 10 je Minute | Fragen je Internetanschluss auf der öffentlichen Demo (Standardwert). Dazu ein Tagesbudget an Modellaufrufen; sein Wert steht nicht im Repo. | Einstellungen `RATENLIMIT_PRO_MINUTE`, `LLM_TAGESBUDGET_AUFRUFE` | `48761dcc` | [docs/models.md](../models.md), [Ausführung, Online-Demo](ausfuehrung.md#online-demo) |
| 504 und 770 Sekunden | Dauer für alle 24 Lieferungen auf einer frischen Datenbank ohne Netz, Alte Regeln und Nach den Änderungsaufträgen. Unter Last 793 und 1.169 Sekunden. | eigene Nachmessung | 05.11.2026 | [Belegregister F28](../praesentation/belegregister.md) |

Die Preise stammen aus der Azure-Preisliste (Region West Europe, abgerufen 05.11.2026). Welcher von zwei Listenpreisen für die Bereitstellung gilt, weiß das Team nicht; deshalb stehen Spannen da.

## 8 Was wir nicht gemessen haben

| Was | Stand im Repo | Quelle |
|---|---|---|
| Zeitersparnis für das Statistik-Team | nicht gemessen; die Dauer des heutigen Prozesses ist dem Team nicht bekannt | [Management-FAQ, Frage 7](../praesentation/management-faq.md) |
| Dauer einer Einführung in den Echtbetrieb | nicht gemessen | [Management-FAQ, Frage 5](../praesentation/management-faq.md) |
| Monatliche Betriebskosten | nicht gemessen | [Management-FAQ, Frage 6](../praesentation/management-faq.md) |
| Ob in den 23 Monaten ohne Vergleichsbericht alle Fehler gefunden sind | nicht belegbar; nur August 2024 hat einen Vergleich | [Kriterien-Karte, Bereich 3](../praesentation/kriterien-karte.md) |
| Freie Fragen an die Daten | nicht alle geprüft; acht Fragen sind gegen eine unabhängige Nachrechnung geprüft | [Kriterien-Karte, Bereich 4](../praesentation/kriterien-karte.md) |
| Antwortzeit am Ort der Vorführung | nicht gemessen; auf dem Testserver 0,4 bis 3,8 Sekunden | [Belegregister F29](../praesentation/belegregister.md) |
| Lizenzen der Pakete einzeln | nicht gemessen | [Management-FAQ, Frage 17](../praesentation/management-faq.md) |
| Rechtliche Prüfung zum AI Act | keine; es gibt nur eine eigene Einschätzung | [Management-FAQ, Frage 18](../praesentation/management-faq.md) |
| Ob alle Abnahmekriterien bestanden sind | nein: Der Schlusslauf am 06.11. zählt für UC3 53 von 76 bestanden, 2 nicht bestanden, 4 nicht geprüft, 17 nach der Abgabe (geurteilt für `14c86cc3`, 07:50). Gezählt ist die eigene Prüfliste des Teams, nicht das Bewertungsraster der Aufgabe. UC1, UC2, UC4 und E5 sind für diesen Stand nicht neu gezählt | [Schlusslauf-Beleg](../abnahme/schlusslauf-2026-11-06.md#nachtrag-auf-dem-letzten-code-stand), Abschnitt „Nachtrag auf dem letzten Code-Stand“ |

## Weiter lesen

- [Übersicht dieses Ordners](README.md) und [Schnellstart](schnellstart.md)
- [Für das Management](fuer-management.md) und [Für Außenstehende](fuer-aussenstehende.md)
- [Architektur](architektur.md), [Arbeitsweise mit Agenten](arbeitsweise-agentisch.md), [Stand der Use Cases](use-cases-stand.md)
- [Belegregister](../praesentation/belegregister.md): jede Zahl der Präsentation mit Abfrage
- [Abgabe UC3](../../abgabe/README.md) und [Protokoll aller Änderungen](../../abgabe/protokoll.md)
- [StatAgent (UC3)](../../uc3/README.md): Befehle und Rechenweg
