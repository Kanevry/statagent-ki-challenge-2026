# Protokoll aller Änderungen

Jede Änderung an Regeln oder Code und jede Veröffentlichung eines Monats steht hier mit Anweisung,
Änderung, Name der freigebenden Person und Zeitpunkt. Erzeugt mit `uv run uc3 protokoll` aus Git
(Commits mit `Freigegeben-von`) und der Datenbank (meta.vorschlag, meta.regel, meta.lauf, meta.ausgabe).

## 1 Änderungen über die eigenen Agenten (Git)

| Zeitpunkt | Anweisung | Freigegeben von | Vorschlag | Modell | Commit |
|---|---|---|---|---|---|
| 2026-11-05T16:12:58+01:00 | Regelsatz v1 freigeben | Bernhard Götzendorfer | uc3/1 | keins@keins | `4d4973dec6` |
| 2026-11-05T16:13:28+01:00 | Berichtsmonat 2024-08 (v1) veröffentlichen | Bernhard Götzendorfer | uc3/2 | keins@keins | `5963abeb7d` |
| 2026-11-05T16:13:30+01:00 | Berichtsmonat 2024-09 (v1) veröffentlichen | Bernhard Götzendorfer | uc3/3 | keins@keins | `955b429466` |
| 2026-11-05T16:13:32+01:00 | Berichtsmonat 2024-10 (v1) veröffentlichen | Bernhard Götzendorfer | uc3/4 | keins@keins | `532dfa4f00` |
| 2026-11-05T16:13:34+01:00 | Berichtsmonat 2024-11 (v1) veröffentlichen | Bernhard Götzendorfer | uc3/5 | keins@keins | `906aae9fe0` |
| 2026-11-05T16:13:36+01:00 | Berichtsmonat 2024-12 (v1) veröffentlichen | Bernhard Götzendorfer | uc3/6 | keins@keins | `380a3ccebf` |
| 2026-11-05T16:13:39+01:00 | Berichtsmonat 2025-01 (v1) veröffentlichen | Bernhard Götzendorfer | uc3/7 | keins@keins | `b78b99397a` |
| 2026-11-05T16:13:41+01:00 | Berichtsmonat 2025-02 (v1) veröffentlichen | Bernhard Götzendorfer | uc3/8 | keins@keins | `b1d5d25380` |
| 2026-11-05T16:13:44+01:00 | Berichtsmonat 2025-04 (v1) veröffentlichen | Bernhard Götzendorfer | uc3/9 | keins@keins | `ea34737301` |
| 2026-11-05T16:13:46+01:00 | Berichtsmonat 2025-05 (v1) veröffentlichen | Bernhard Götzendorfer | uc3/10 | keins@keins | `07dd19f08b` |
| 2026-11-05T16:13:48+01:00 | Berichtsmonat 2025-06 (v1) veröffentlichen | Bernhard Götzendorfer | uc3/11 | keins@keins | `278ba6c306` |
| 2026-11-05T16:13:50+01:00 | Berichtsmonat 2025-07 (v1) veröffentlichen | Bernhard Götzendorfer | uc3/12 | keins@keins | `6de5e2dc08` |
| 2026-11-05T16:13:52+01:00 | Berichtsmonat 2025-08 (v1) veröffentlichen | Bernhard Götzendorfer | uc3/13 | keins@keins | `1872434ae2` |
| 2026-11-05T16:13:54+01:00 | Berichtsmonat 2025-09 (v1) veröffentlichen | Bernhard Götzendorfer | uc3/14 | keins@keins | `01313be959` |
| 2026-11-05T16:13:56+01:00 | Berichtsmonat 2025-11 (v1) veröffentlichen | Bernhard Götzendorfer | uc3/15 | keins@keins | `61f3dad023` |
| 2026-11-05T16:13:58+01:00 | Berichtsmonat 2025-12 (v1) veröffentlichen | Bernhard Götzendorfer | uc3/16 | keins@keins | `53c27c4f67` |
| 2026-11-05T16:14:00+01:00 | Berichtsmonat 2026-01 (v1) veröffentlichen | Bernhard Götzendorfer | uc3/17 | keins@keins | `70b976bfc3` |
| 2026-11-05T16:14:02+01:00 | Berichtsmonat 2026-02 (v1) veröffentlichen | Bernhard Götzendorfer | uc3/18 | keins@keins | `6f929adfd0` |
| 2026-11-05T16:14:04+01:00 | Berichtsmonat 2026-03 (v1) veröffentlichen | Bernhard Götzendorfer | uc3/19 | keins@keins | `f28fd57923` |
| 2026-11-05T16:14:06+01:00 | Berichtsmonat 2026-04 (v1) veröffentlichen | Bernhard Götzendorfer | uc3/20 | keins@keins | `879e5656b4` |
| 2026-11-05T16:14:08+01:00 | Berichtsmonat 2026-05 (v1) veröffentlichen | Bernhard Götzendorfer | uc3/21 | keins@keins | `3f1c68f95f` |
| 2026-11-05T16:14:10+01:00 | Berichtsmonat 2026-06 (v1) veröffentlichen | Bernhard Götzendorfer | uc3/22 | keins@keins | `7b32aabb3f` |
| 2026-11-05T16:14:12+01:00 | Berichtsmonat 2026-07 (v1) veröffentlichen | Bernhard Götzendorfer | uc3/23 | keins@keins | `54bdf87976` |

## 2 Vorschläge der Agenten

| Nr. | Erstellt | Anweisung | Rolle | Typ | Status | Freigegeben von | Zeitpunkt | Modell |
|---|---|---|---|---|---|---|---|---|
| 24 | 05.11.2026 15:37 | Auftrag 1, Dienstvertrag und freier Dienstvertrag zusammen: In der Statistik und im Aggregations-Sheet wird nicht mehr zwischen Dienstvertrag (DV) und freiem Dienstvertrag (FD) unterschieden. Die Beschäftigungskategorie hat nur noch die Ausprägungen Arbeiter, Angestellte und Beamte (siehe Spalte BESCHAEFTIGUNGSKATEGORIE in qualifikation.csv). Die Änderung gilt rückwirkend für die ganze Zeitreihe. Ändere dafür nur die Zählregel der Beschäftigungskategorie so, dass sie die Spalte beschaeftigungskategorie der bestehenden Qualifikations-Klassifikation verwendet; die Klassifikationstabelle selbst bleibt unverändert. Ziel ist der neue Regelsatz v2, Regelsatz v1 bleibt, wie er ist. | klassifikation | regel_aendern | offen |  |  | gpt-5-4-mini@azure |
| 25 | 05.11.2026 15:40 | Auftrag 2, ganzes Monat statt Stichtag: Gezählt wird nicht mehr der Monatsletzte, sondern das ganze Monat. Beschäftigt ist, wer im Berichtsmonat jemals beschäftigt war; auch ein einziger Tag mitten im Monat genügt. Ein Verhältnis zählt, wenn mindestens ein Zeitabschnitt mindestens einen Tag im Berichtsmonat besteht: Beginn höchstens Monatsletzter und Ende leer oder mindestens Monatserster. Zähleinheit bleiben die Versicherungsverhältnisse, jedes zählt im Monat genau einmal. Die Merkmale kommen aus dem letzten Zeitabschnitt des Verhältnisses im Berichtsmonat, das Alter in vollendeten Jahren am Monatsletzten, gezählt wird weiterhin aus der Lieferung des Berichtsmonats. Die Änderung gilt rückwirkend für die ganze Zeitreihe zusammen mit Auftrag 1, also im Regelsatz v2; Regelsatz v1 bleibt, wie er ist.
 Der Zeitraum der Zählregel ist also der ganze Monat (Art Monat statt Stichtag), vom Monatsersten bis zum Monatsletzten. | datenmanagement | regel_aendern | offen |  |  | gpt-5-4-mini@azure |
| 26 | 05.11.2026 15:45 | Auftrag 3, Datenlieferung an das Ministerium: Das Ministerium erhält eine Liste aller Personen, die in den letzten zwölf Monaten bis einschließlich Berichtsmonat mindestens 200 Tage als Arbeiter beschäftigt waren, mit Dienstvertrag oder freiem Dienstvertrag (ArbeiterDV, ArbeiterFD), im ÖNACE-Abschnitt C. Der Berichtsmonat ist ein Parameter, für die Abgabe 07/2026, also der Zeitraum 01.08.2025 bis 31.07.2026. Tage sind Kalendertage, an denen mindestens ein passender Zeitabschnitt besteht; gleichzeitige Verhältnisse zählen einen Tag nur einmal, DV- und FD-Tage werden zusammengezählt. Datenstand: Für jeden Tag gilt die jüngste Lieferung, die diesen Tag enthält, verarbeitet nach unseren Regeln (Regelsatz v1); eine Lieferung, deren Monatslauf angehalten wurde (Teil-Lieferung), wird dabei übersprungen. Wirtschaftszweig ist die ÖNACE des jeweiligen Zeitabschnitts, wie ihn die verwendete Lieferung ausweist: bis 12/2024 nach ÖNACE 2008, ab 01/2025 nach ÖNACE 2025, gezählt wird Abschnitt C; die alten ÖNACE-2003-Codes DA bis DN zählen wie in unserer Zuordnungsregel Q01 zu C. Felder: PERSON_ID, GESCHLECHT, GEBURTSJAHR (bei unplausiblem Geburtsdatum Unbekannt), TAGE. Format: CSV mit Semikolon, Datei ministerium_JJJJ-MM.csv, sortiert nach PERSON_ID. Setze das als Regel um, nicht als Code: eine neue Regel (regel_neu) vom Typ zaehl der Art personentage im Regelsatz ministerium, mit den Parametern, die diese Art kennt. | datenmanagement | regel_neu | offen |  |  | gpt-5-4-mini@azure |

## 3 Regelfreigaben

| Regelsatz | Freigegeben von | Zeitpunkt | Regeln |
|---|---|---|---|
| v1 | Bernhard Götzendorfer | 05.11.2026 15:12 | 39: P01_volldubletten, P02_mehrere_abschnitte_im_zeitraum, P03_spaltentausch, P04_geburtsdatum_monat_13, P05_geburtsdatum_ungueltig, P06_alter_unplausibel, P07_alter_hoch_plausibel, P08_beginn_ersetzt, P09_beginn_nach_ende, E01_spaltentausch_beginn_ende, P10_merkmal_leer, R2_R4_stichtag_eigene_lieferung, P11_oenace_altcode_2003, P12_code_unbekannt, P13_auspraegung_verschwunden, P14_sprung_aggregat, P15_bestand_vs_vormonat, P16_verhaeltnisse_verschwunden, P17_zeilenzahl_vs_vormonat, P18_merkmalswelle, P19_phantom_doppelmeldung, E02_volldubletten, P20_person_inkonsistent, R1_R3_verhaeltnis_einmal, P21_blattsummen, P22_abrechnung, P23_revision_vormonat, P24_lieferumfang_fenster, E03_datum_pruefen, R5_alter, E04_beginn_fehlt, R7_oenace_nach_berichtsmonat, E06_ende_ungueltig, E05_quellzuordnung, R6_beschaeftigungskategorie, Q01_oenace_2003_unterabschnitte, Q02_leer_unbekannt, Q03_sonst_unbekannt, E07_fortschreibung_lieferausfall |

## 4 Veröffentlichte Monate

| Berichtsmonat | Regelsatz | Freigegeben von | Zeitpunkt | Verhältnisse | Ergebnis-Hash |
|---|---|---|---|---|---|
| 2024-08 | v1 | Bernhard Götzendorfer | 05.11.2026 15:13 | 392236 | `de35e5b8837c` |
| 2024-09 | v1 | Bernhard Götzendorfer | 05.11.2026 15:13 | 393454 | `d7b32d2bed1c` |
| 2024-10 | v1 | Bernhard Götzendorfer | 05.11.2026 15:13 | 391033 | `676240a20cd5` |
| 2024-11 | v1 | Bernhard Götzendorfer | 05.11.2026 15:13 | 389141 | `0a5e7bef37c3` |
| 2024-12 | v1 | Bernhard Götzendorfer | 05.11.2026 15:13 | 387390 | `22c406871f2a` |
| 2025-01 | v1 | Bernhard Götzendorfer | 05.11.2026 15:13 | 385033 | `68ba0b5a3704` |
| 2025-02 | v1 | Bernhard Götzendorfer | 05.11.2026 15:13 | 386996 | `5a9aa6c9babb` |
| 2025-04 | v1 | Bernhard Götzendorfer | 05.11.2026 15:13 | 387601 | `3a917452e284` |
| 2025-05 | v1 | Bernhard Götzendorfer | 05.11.2026 15:13 | 390001 | `47f863da9087` |
| 2025-06 | v1 | Bernhard Götzendorfer | 05.11.2026 15:13 | 394252 | `5dec1780ffa2` |
| 2025-07 | v1 | Bernhard Götzendorfer | 05.11.2026 15:13 | 397419 | `5a0128470ba8` |
| 2025-08 | v1 | Bernhard Götzendorfer | 05.11.2026 15:13 | 393712 | `cf4b69d616c4` |
| 2025-09 | v1 | Bernhard Götzendorfer | 05.11.2026 15:13 | 394200 | `155252e0e863` |
| 2025-11 | v1 | Bernhard Götzendorfer | 05.11.2026 15:13 | 389823 | `66a453d93287` |
| 2025-12 | v1 | Bernhard Götzendorfer | 05.11.2026 15:13 | 388231 | `5b125df6c742` |
| 2026-01 | v1 | Bernhard Götzendorfer | 05.11.2026 15:14 | 385573 | `6e40a4577df6` |
| 2026-02 | v1 | Bernhard Götzendorfer | 05.11.2026 15:14 | 387947 | `224e7722de8d` |
| 2026-03 | v1 | Bernhard Götzendorfer | 05.11.2026 15:14 | 391475 | `901b5e763328` |
| 2026-04 | v1 | Bernhard Götzendorfer | 05.11.2026 15:14 | 389361 | `74db783ba6c0` |
| 2026-05 | v1 | Bernhard Götzendorfer | 05.11.2026 15:14 | 391871 | `be2cf1392f6e` |
| 2026-06 | v1 | Bernhard Götzendorfer | 05.11.2026 15:14 | 395320 | `472dd18a5d1e` |
| 2026-07 | v1 | Bernhard Götzendorfer | 05.11.2026 15:14 | 399027 | `0f1f7def0db7` |

## 5 Lieferungen nach außen (Ministerium)

Noch keine Lieferung nach außen freigegeben.
