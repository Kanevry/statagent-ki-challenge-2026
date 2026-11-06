# Live-Änderung: Ablehnen und Rücknahme (#80, AC2)

Ablehnen ändert nichts. Eine Rücknahme ist ein neuer freigegebener Vorgang, der wieder denselben Stand herstellt, ohne etwas zu löschen. Beides ist unten mit echten Hashes belegt.

**Rahmen der Messung:** 05.11.2026, Wiener Zeit. Kopie der Abgabe-DB, nie `statistik`, Modell Azure gpt-5-4-mini, Probemonat 2026-07, Code-Stand `d888e09`. Freigaben und Ablehnungen stammen vom Probenskript `uc3/proben/live_proben.py` unter dem Probe-Namen „Petra Probe“. Das sind keine Freigaben eines Teammitglieds, und sie liegen nur in der Kopie und einem eigenen Probe-Repo.

**Was „Produktionshash“ hier heißt:** der Regelstand (`regeln.regelstand`), ein Hash über aktive Zähl-, Einlese- und Zuordnungsregeln, Quellzuordnung und Klassifikation. Prüfregeln gehören nicht dazu, weil sie keine Zahl ändern. Das Ergebnis misst getrennt der Ergebnis-Hash des Laufs über alle Zellen.

## 1. Ablehnen ändert nichts

| Vorschlag | Auftrag | Status | Name | Änderungscommits | Regelstand danach |
|---|---|---|---|---|---|
| uc3/127 | Stichtag 15. | abgelehnt | Petra Probe | 0 | Ausgangsstand v60 unverändert `0bfa2c5bdb38c51a` |
| uc3/130 | ohne Beamte | abgelehnt | Petra Probe | 0 | Ausgangsstand v62 unverändert `0bfa2c5bdb38c51a` |

Die Zahl der Commits ist im Probe-Repo gemessen. Das Probenskript prüft das bei jedem Lauf: gleicher Regelstand, gleicher Git-Kopf, gleicher aktueller Regelsatz, kein neuer Ziel-Regelsatz (Spalte `ablehnen_hash_gleich` in `live-proben.csv`).

v60 und v62 sind Regelsätze aus früheren Proben derselben Kopie; ihr Regelstand und ihr Ergebnis sind gleich v2, das misst die Tabelle unten.

## 2. Rücknahme als neuer Vorgang

Anweisung: „Nimm die Änderung aus Vorschlag N zurück, wie es vorher war.“ Der Koordinator erkennt nur, welcher Vorschlag gemeint ist. Die Umkehrung rechnet der Code: Geänderte Parameter gehen zurück, eine neu angelegte Regel wird abgeschaltet. Ohne ausdrückliches Wort wie „zurück“ oder „rückgängig“ gibt es keine Rücknahme.

| Regelsatz | Vorgang | Vorschlag, Commit | Regelstand | Bestand 2026-07 | Ergebnis-Hash 2026-07 |
|---|---|---|---|---|---|
| v2 | Abgabe | | `0bfa2c5bdb38c51a` | 407.604 | `1b6fd3dc865de5ae` |
| v60 | Ausgangsstand | | `0bfa2c5bdb38c51a` | 407.604 | `1b6fd3dc865de5ae` |
| v61 | Stichtag 15. freigegeben | uc3/128, `e5d6099` | `acc9b44d795300f7` | 397.500 | `b4b67c57b22bef5f` |
| v62 | Rücknahme freigegeben | uc3/129, `ffc1be1` | `0bfa2c5bdb38c51a` | 407.604 | `1b6fd3dc865de5ae` |
| v63 | ohne Beamte freigegeben (neue Regel) | uc3/131, `2fe5dd9` | `078ba128f4db0c0b` | 395.315 | `bf9b21da30189745` |
| v64 | Rücknahme freigegeben (Regel abgeschaltet) | uc3/132, `9510a15` | `0bfa2c5bdb38c51a` | 407.604 | `1b6fd3dc865de5ae` |

Die Ergebnis-Hashes sind in einer zurückgerollten Transaktion neu gerechnet und mit dem gespeicherten v2-Lauf verglichen. Regelstand und Ergebnis entsprechen nach jeder Rücknahme wieder dem Stand davor. Beide Rücknahmen haben je genau einen Commit.

## 3. Die Historie bleibt

- Vorschlag und Rücknahme stehen beide als freigegeben im Protokoll, jeder mit eigenem Commit und den Trailern `Freigegeben-von` und `Vorschlag`.
- Der Regelsatz mit der Änderung bleibt bestehen. Eine neu angelegte Regel ist im Rücknahme-Regelsatz abgeschaltet (`aktiv = false`), nicht gelöscht.
- v2, die Abgabe, wird nicht angefasst. Jede Änderung und jede Rücknahme landet in einem neuen Regelsatz.

## 4. Die Abgabe bleibt unverändert

- Ein Zählregelsatz mit gerechneten Monaten ändert sich nie in place: Das Ziel bestimmt der Code (`ziel_bestimmen`). Freigabe und Anwenden prüfen das noch einmal (`ziel_gesperrt`), damit auch ein alter offener Vorschlag mit Ziel v2 scheitert, und zwar vor dem Commit.
- Nennt das Modell als Ziel einen Regelsatz mit veröffentlichten Monaten (v1), wird der Vorschlag abgelehnt.
- v1 und v2 rechnen mit dem neuen Code bitgleich: v2 2026-07 = 407.604 (`1b6fd3dc865d`), v1 2025-03 = 388.650 (`9ad1015664c0`), jeweils gleich dem gespeicherten Lauf.

## 5. Was die Serie belegt und was nicht

**Serie:** `live-proben.csv`, 10 Aufträge je dreimal, alle 30 bestanden, längster Lauf 147 s, im Mittel 79 s, gemessen von der Anweisung bis zur Probe vorher und nachher. Fünf Läufe in lockerer Schreibweise (Spalte `auftrag` endet auf `_locker`). A, B und C sind die drei Varianten aus #80 (Stichtag 15., Beamte ausschließen, Bundesländer zusammenlegen), damit sind auch die 9 Proben aus AC1 enthalten. Die Anweisung ist getippt, nicht gesprochen (Owner 05.11.2026). Die Dauer ist die längste von drei Agentenläufen je Zeile.

Vor dieser Serie liefen mehrere verworfene Serien, deren Fehler behoben wurden; sie stehen nicht in der Datei. Die Quote gilt für diesen Code-Stand. Das Modell streut: Einzelne Aufträge brauchten Korrekturrunden, in früheren Ständen fiel auch mal einer durch.

- **Erwartung bei J gelockert:** Die Schwelle von P15 muss genau stimmen. Der Meldungstext derselben Regel darf sich mit ändern und muss dann die neue Zahl nennen. Eine andere Regel nebenbei fällt weiter durch.
- **J belegt beim Hash nichts:** Der Regelstand lässt Prüfregeln aus, die Spalten `ablehnen_hash_gleich` und `ruecknahme_hash_gleich` konnten bei J in dieser Serie nicht rot werden. Seit `9c53bfd` vergleicht das Skript auch die Parameter der Prüfregeln; das misst die Nachprobe.
- **Code-Stand:** Nach der Serie kamen noch Fixes (Abschnitt 6). Für den Endkopf gilt die Nachprobe, nicht die Serie.
- **Nicht gemessen:** auf einer frisch aufgesetzten DB. Die Probe über die Vorführ-Instanz steht in Abschnitt 6.

## 6. Nachprobe auf dem Endkopf

Die Serie lief auf `d888e09`. Danach kamen Fixes aus den Reviews: falsche Probe-Zahl in Monaten mit Fortschreibung, Rücknahme nur aus dem aktuellen Stand, Texte, Wort-Weiche. Darum je Auftrag ein Lauf auf dem Endkopf `2d3b537` (`live-proben-zusatz.csv`, Spalte `serie`; fünf Aufträge in lockerer Schreibweise). Seit dieser Nachprobe vergleicht das Skript auch die Parameter der Prüfregeln. Danach kamen nur noch diese Belege dazu, kein Code.

**Wo was lief:** Serie und erste Zusatzläufe auf einer ersten Prüfkopie der Abgabe-DB (Spalte `lief_auf` in `live-proben-zusatz.csv`). Der Rechner dieser Kopie fiel am 06.11. um 00:35 aus. Die Nachprobe und alles in diesem Abschnitt außer der URL-Probe lief deshalb auf einer Ersatz-Kopie: Dump vom 05.11. 22:05 einer Vorführ-Kopie der Abgabe-DB, vor dem Pensionen-Teil (Bereich 2), den die Live-Änderung nicht braucht. Vor dem Start gemessen: Regelstand `0bfa2c5bdb38c51a`, v2 2026-07 = 407.604 (`1b6fd3dc865d`), v2 2025-03 = 396.762, v2 2025-10 = 397.514, v1 2025-03 = 388.650, also wie die Abgabe. Nichts wurde zurückgeschrieben, die Kopie ist inzwischen freigegeben. Zeitraum 06.11. 00:48 bis 01:48.

- **Summe Nachprobe: 13 von 14, längster Lauf 115 s.** Ablehnen und Rücknahme stellten bei allen 14 den Stand wieder her, auch die Parameter der Prüfregeln.
- **Zehn Aufträge A bis J:** 10 von 10.
- **Zusatz K (ohne Männer), L (ÖNACE-Abschnitt O), M (Beamte und Kinder unter 15):** Nachprobe 3 von 3; dazu auf `d888e09` 9 von 9, M hielt alle vier Male beide Regeln.
- **N „Ein Monat wird schon angehalten, wenn in einem Bundesland mehr als 10 % fehlen“: nicht bestanden.** Der Vorschlag hebt P16 von 1 % auf 10 % an, macht die Prüfung also unempfindlicher, und das Bundesland fällt weg. Eine Prüfschwelle je Bundesland gibt es nicht; richtig wäre eine Rückfrage. Vor der Freigabe zeigt der Unterschied das, das Programm erkennt es nicht. Auf `ac68b20` meldete das Skript hier noch bestanden, weil es nur „irgendeine Prüfregel“ prüfte; seit `2d3b537` urteilt es selbst richtig. Darum: Diesen Satz nicht vorführen (#180).
- **Auftrag 2 als Anweisung (Originaltext und Kurzfassung):** 10 von 10 auf `2d3b537`, Ersatz-Kopie, Basis v1. Auf frischer DB misst die UI-Regie nach dem Merge.
- **v1 und v2 auf `2d3b537` bitgleich:** v2 2026-07 = 407.604 (`1b6fd3dc865d`), v1 2025-03 = 388.650 (`9ad1015664c0`).
- **Modell:** alle 108 Agentenaufrufe dieser Nachprobe liefen über Azure (Modellprotokoll), keiner über den Zweitanbieter; bei der Endserie waren es 350 von 350.

**Probe in Monaten mit Fortschreibung:** 2025-03 und 2025-10 enthalten Fortschreibungen. Früher zeigte die Probe dort eine falsche Gesamtzahl (2025-03: −1.470 bei einer reinen Altersänderung). Gemessen allein auf der Ersatz-Kopie, Kopf `2d3b537`, je eine Altersänderung und eine Prüfregel: vorher wie Soll, 2025-03 = 396.762 und 2025-10 = 397.514, nachher dieselbe Gesamtzahl, 103 bis 115 s, im Ziel-Regelsatz 0 Läufe, 0 Abschnitte, 0 Regeln. Bei der Prüfregel bleiben alle Zahlen gleich.

**Über die echte Vorführ-URL:** am 06.11. bis 00:45 auf der Instanz mit Stand `ac68b20`, ein Auftrag zur Zeit, Name „Erika Probe“. Acht Auftragstypen (Stichtag, Alter, Monat 13, zweimal Zusammenlegen, zweimal Ausschluss, Prüfschwelle) brachten je einen passenden Vorschlag in 150 bis 203 s. Mit Probemonat 2025-03 und 2025-10 zeigt die Freigabeseite 396.762 und 397.514, die falsche Zahl 395.292 kommt nicht mehr vor. Alle zehn Ablehnungen liefen mit HTTP 200. Einmal lief der ganze Ablauf: Vorschlag (209 s), Freigabe, Rücknahme als neuer Vorgang (96 s), Freigabe. Die Dauer stieg über die Probe, die Grenze sind 240 s. Die Probe-Rechnung hat sich seit `ac68b20` nicht geändert.

## 7. Grenzen

- Die Rücknahme geht nur vom Stand aus, der den Vorschlag enthält. Liegt eine weitere Änderung darüber, wird sie abgelehnt.
- Ein Regelsatz aus einer Live-Änderung ist nur teilweise freigegeben (die geänderte Regel). Seine Monate bleiben deshalb vorläufig, bis der ganze Regelsatz mit `uc3 regeln freigeben` freigegeben ist.
- Für einen Regelsatz mit Ausschluss oder Gruppierung sind Sheet und Qualitätsbericht noch offen (#169), die Anzeige auf `/uc3/freigaben` ebenfalls (#168).
- Ein Rückfall auf den Zweitanbieter ist im Vorschlag nicht sichtbar (#178).

Wiederholen: `UC3_DATABASE_URL=<eigene Kopie> LLM_PROVIDER=azure uv run python uc3/proben/live_proben.py --repo <eigenes Git-Repo> --runden 3`
