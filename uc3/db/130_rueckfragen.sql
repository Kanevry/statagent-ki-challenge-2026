-- Rückfragen an die Fachabteilung nach Veranstaltervorlage (rueckfrage_vorlage.md), mit Beleg.
-- `vorschlag` ist unsere Annahme, bis die Fachabteilung antwortet; umgesetzt ist sie als Regel `regel_name`
-- (Parameter in meta.regel). Kommt eine Antwort, ändert sich nur die Regel, per Freigabe mit Namen.
-- Nummern R1 bis R5 nach GitLab #72 AC1 (Geburtsmonat 13, ÖNACE-Wellen, Teil-Lieferung 2025-10, fehlende FD 2025-03,
-- Spaltentausch 2025-06), danach R6 bis R10. Umnummeriert am 05.11.2026, als noch keine Antwort eingetragen war.
-- `beleg_sql` liefert je betroffenem Satz eine Zeile mit `vvh_id` (ohne Semikolon); der Generator
-- (statagent/berichte/rueckfragen.py) zählt damit nach und zieht die Beispiel-IDs. Die erste Zahl in `anzahl`
-- ist die Trefferzahl dieser Abfrage, gemessen am 05.11.2026 in der Datenbank statistik. Beispiel-IDs sind VVH_IDs.
-- R8 und R10 lesen die Ergebnisse eines Laufs (bereinigt.abschnitt, meta.pruefung_treffer), damit ihre Zahl
-- dieselbe ist wie im Qualitätsbericht; in einer Datenbank ohne Lauf finden sie keinen Satz.

INSERT INTO meta.rueckfrage (nr, titel, lieferungen, aufgefallen, anzahl, merkmale, beispiele, beleg_sql, vorschlag, frage,
                             regel_name, ab_lieferung) VALUES

('R1', 'Geburtsmonat 13 im Geburtsdatum', 'lieferung_2024-08 und alle weiteren',
 'In jeder Lieferung haben 336 bis 444 Sätze ein Geburtsdatum mit dem Monat 13, zum Beispiel 1963-13-09. Der Beispielbericht für August 2024 rechnet das Alter dieser Personen trotzdem aus dem Geburtsjahr.',
 '370 Sätze am Stichtag 31.08.2024 in Lieferung 2024-08, in den anderen Lieferungen 336 bis 444 Sätze', 'Geburtsdatum, daraus das Alter in der Alterstabelle',
 '[1050, 1824, 2257, 5493, 7739]',
 'SELECT vvh_id FROM roh.lieferung WHERE lieferung = ''2024-08'' AND substr(geburtsdatum, 6, 2) = ''13'' AND beginn <= ''2024-08-31'' AND (ende IS NULL OR ende >= ''2024-08-31'')',
 'Wir lesen Monat 13 als „Monat unbekannt“ und rechnen mit dem 1. Juli des Geburtsjahres, also der Jahresmitte. Das ist die beste Schätzung, wenn nur das Jahr bekannt ist, und für August 2024 ergibt es genau die Zahlen des Beispielberichts. Einen Unterschied macht die Wahl nur in Berichtsmonaten von Jänner bis Juni. Wollt ihr anders rechnen, etwa nur mit der Differenz der Jahre, stellen wir einen Wert der Regel um. Die Fälle stehen jeden Monat im Qualitätsbericht.',
 'Mit welchem Tag sollen wir bei Geburtsmonat 13 rechnen: mit dem 1. Juli, mit dem 1. Jänner oder nur mit der Differenz der Jahre?',
 'R5_alter', '2024-08'),

('R2', 'Ganze Gruppen wechseln die ÖNACE-Branche (Mai 2025, Februar 2026)', 'lieferung_2025-05, lieferung_2026-02',
 'Am 1. Mai 2025 wechseln in der Steiermark 491 Verhältnisse auf einen Schlag von der Branche O (öffentliche Verwaltung) zu C (Herstellung von Waren), darunter 11 Beamte. Am 1. Februar 2026 wechseln in Wien 347 Verhältnisse von G (Handel) zu C.',
 '838 Verhältnisse: 491 in Lieferung 2025-05 und 347 in Lieferung 2026-02', 'Branche (ÖNACE), jeweils als neuer Zeitabschnitt am selben Tag',
 '[125007, 229275, 229304, 229324, 229333]',
 'SELECT n.vvh_id FROM roh.lieferung n WHERE ((n.lieferung = ''2025-05'' AND n.beginn = ''2025-05-01'' AND n.oenace = ''C'' AND n.bundesland = ''6'') OR (n.lieferung = ''2026-02'' AND n.beginn = ''2026-02-01'' AND n.oenace = ''C'' AND n.bundesland = ''9'')) AND EXISTS (SELECT 1 FROM roh.lieferung a WHERE a.lieferung = n.lieferung AND a.vvh_id = n.vvh_id AND a.oenace = CASE n.lieferung WHEN ''2025-05'' THEN ''O'' ELSE ''G'' END AND a.ende < n.beginn)',
 'Wir zählen die Verhältnisse so, wie sie geliefert sind, also ab dem Wechsel in C. Ohne eure Auskunft wäre jede Korrektur ein Eingriff in eine Entwicklung, die echt sein kann. Im Qualitätsbericht steht die Welle mit Zahl und Tag als „nicht erklärbar“ und verweist auf diese Rückfrage.',
 'Haben diese Dienstgeber wirklich die Branche gewechselt, oder ist die Branche falsch codiert?',
 'P18_merkmalswelle', '2025-05'),

('R3', 'Teil-Lieferung 2025-10: rund ein Fünftel fehlt', 'lieferung_2025-10',
 'In Lieferung 2025-10 fehlen rund 20 % der Verhältnisse: 345.078 Zeilen statt rund 430.000 wie in den Nachbarmonaten. Die Lücke ist in allen Bundesländern, Branchen und Qualifikationen gleich groß, und fast alle fehlenden Verhältnisse sind in Lieferung 2025-11 wieder da.',
 '78.949 Verhältnisse, die am 30.09.2025 bestanden, fehlen in Lieferung 2025-10; 78.733 davon sind in 2025-11 wieder da, 216 nicht', 'alle Merkmale gleichmäßig, jeweils etwa 20 %',
 '[34, 79, 95, 122, 133]',
 'SELECT s.vvh_id FROM (SELECT DISTINCT vvh_id FROM roh.lieferung WHERE lieferung = ''2025-09'' AND beginn <= ''2025-09-30'' AND (ende IS NULL OR ende >= ''2025-09-30'')) s WHERE NOT EXISTS (SELECT 1 FROM roh.lieferung l WHERE l.lieferung = ''2025-10'' AND l.vvh_id = s.vvh_id)',
 'Wir übernehmen die fehlenden Verhältnisse einmalig aus Lieferung 2025-09, wenn sie dort am 31.10.2025 noch gültig sind (wir schreiben sie fort). Spätere Lieferungen nutzen wir nicht, weil jeder Monat nur aus seiner eigenen und früheren Lieferungen gerechnet wird. So geht kein Verhältnis verloren, und der Fehler bleibt klein: Mit Fortschreibung zählen wir 390.900 Verhältnisse, Lieferung 2025-11 nennt für denselben Tag 391.243. Der Qualitätsbericht zeigt gelieferte und fortgeschriebene Verhältnisse getrennt, der Lauf hält an, bis ein Mensch freigibt, und der Monat bleibt vorläufig. Auch die Ministeriums-Lieferung rechnet August 2025 aus Lieferung 2025-09 und nicht aus der Teil-Lieferung: Das ergibt 32.741 Personen, aus der Teil-Lieferung wären es 32.667.',
 'Kommt für Oktober 2025 eine vollständige Nachlieferung, oder dürfen wir die fehlenden Verhältnisse wie beschrieben aus Lieferung 2025-09 fortschreiben?',
 'E07_fortschreibung_lieferausfall', '2025-10'),

('R4', 'Freie Dienstverträge fehlen in Lieferung 2025-03', 'lieferung_2025-03',
 'In Lieferung 2025-03 fehlt die ganze Gruppe der freien Dienstverträge, bei Arbeitern wie bei Angestellten. Die anderen Lieferungen haben je 1.316 bis 1.697 solche Sätze, und in 2025-02 und 2025-04 stehen die betroffenen Verhältnisse unverändert.',
 '1.492 freie Dienstverträge, die am 28.02.2025 bestanden, fehlen; alle sind in 2025-04 wieder da. Lieferung 2025-03 hat keinen einzigen solchen Satz.', 'Qualifikation (ArbeiterFD, AngestellteFD)',
 '[448, 1054, 1264, 1289, 2247]',
 'SELECT DISTINCT p.vvh_id FROM roh.lieferung p WHERE p.lieferung = ''2025-02'' AND p.qual LIKE ''%FD'' AND p.beginn <= ''2025-02-28'' AND (p.ende IS NULL OR p.ende >= ''2025-02-28'') AND NOT EXISTS (SELECT 1 FROM roh.lieferung l WHERE l.lieferung = ''2025-03'' AND l.vvh_id = p.vvh_id)',
 'Wir übernehmen die fehlenden freien Dienstverträge einmalig aus Lieferung 2025-02, wenn sie dort am 31.03.2025 noch gültig sind (wir schreiben sie fort). Eine ganze Gruppe verschwindet nicht für einen Monat und kommt dann zurück; ohne Fortschreibung zeigte die Zeitreihe einen Bruch, den es nicht gibt. Der Qualitätsbericht zeigt gelieferte und fortgeschriebene Verhältnisse getrennt, der Lauf hält an, und der Monat bleibt vorläufig. Mit Lieferung 2025-04 steht die Abweichung als Revisionsbedarf im Bericht.',
 'Dürfen wir die freien Dienstverträge für März 2025 aus Lieferung 2025-02 fortschreiben, oder soll März 2025 ohne sie erscheinen und erst später berichtigt werden?',
 'E07_fortschreibung_lieferausfall', '2025-03'),

('R5', 'BEGINN und ENDE vertauscht in Lieferung 2025-06', 'lieferung_2025-06',
 'In Lieferung 2025-06 ist das Beginndatum bei 388.115 von 432.086 Sätzen leer, und bei 43.914 Sätzen liegt der Beginn nach dem Ende. Es sieht aus, als wären die Spalten BEGINN und ENDE vertauscht; ohne Tausch bestünden am 30.06.2025 nur 21 Verhältnisse.',
 '388.115 von 432.086 Sätzen haben keinen Beginn; getauscht werden alle 432.086 Sätze der Lieferung', 'Beginn und Ende (ganze Lieferung)',
 '[7, 12, 14, 33, 34]',
 'SELECT vvh_id FROM roh.lieferung WHERE lieferung = ''2025-06'' AND beginn IS NULL',
 'Wir tauschen Beginn und Ende für die ganze Lieferung, nicht Zeile für Zeile. Danach bestehen am 30.06.2025 394.252 Verhältnisse, ähnlich wie in den Nachbarmonaten (390.001 und 397.419), und keines geht verloren. Der Tausch greift nur, wenn mehr als die Hälfte der Beginndaten leer ist und mehr als 5 % nach dem Ende liegen; das trifft nur diese Lieferung. Der Tausch steht im Qualitätsbericht für Juni 2025.',
 'Sind Beginn und Ende in Lieferung 2025-06 vertauscht?',
 'E01_spaltentausch_beginn_ende', '2025-06'),

('R6', 'Obergrenze für ein glaubwürdiges Alter', 'lieferung_2024-08 und alle weiteren',
 'Einige Geburtsdaten sind formal gültig, ergeben aber ein Alter von 117 bis 153 Jahren (Geburtsjahre ab 1871). Der Beispielbericht zählt diese Personen unter „Alter unbekannt“; echte Beschäftigte mit 75 bis 77 Jahren gibt es ab September 2024.',
 '7 Verhältnisse am 31.08.2024; 7 bis 14 Sätze je Lieferung', 'Geburtsdatum, daraus das Alter in der Alterstabelle',
 '[149431, 207859, 327231]',
 'SELECT vvh_id FROM roh.lieferung WHERE lieferung = ''2024-08'' AND geburtsdatum < ''1913-09-01'' AND beginn <= ''2024-08-31'' AND (ende IS NULL OR ende >= ''2024-08-31'')',
 'Ein Alter über 110 Jahre halten wir für einen Fehler im Geburtsdatum; es steht unter „Alter unbekannt“, das Verhältnis zählt trotzdem mit. Zwischen 78 und 116 Jahren gibt es in keiner Lieferung einen Fall, deshalb ergibt jede Grenze in diesem Bereich dieselben Zahlen. Eine Grenze bei 74 würde dagegen echte 75-Jährige wegrechnen, 62 bis 310 je Monat. Dieselbe Grenze gilt für das Geburtsjahr in der Ministeriums-Lieferung.',
 'Ab welchem Alter sollen wir ein Geburtsdatum als Fehler werten?',
 'R5_alter', '2024-08'),

('R7', 'Doppelte Zeilen in Lieferung 2025-03', 'lieferung_2025-03',
 'In Lieferung 2025-03 stehen 1.663 Zeilen zweimal, in allen neun Feldern gleich. Keine der anderen 23 Lieferungen hat solche doppelten Zeilen.',
 '1.663 überzählige Zeilen; ohne Bereinigung wären am 31.03.2025 1.523 Verhältnisse doppelt gezählt (388.703 statt 387.180)', 'ganze Zeile',
 '[100071, 100136, 10047]',
 'SELECT vvh_id FROM roh.lieferung WHERE lieferung = ''2025-03'' GROUP BY vvh_id, person_id, geburtsdatum, geschlecht, beginn, ende, qual, oenace, bundesland HAVING count(*) > 1',
 'Zwei völlig gleiche Zeilen fassen wir zu einer zusammen. Sie beschreiben dasselbe Verhältnis, und ohne Zusammenfassen zählten wir am 31.03.2025 1.523 Verhältnisse doppelt. Wie viele es waren, steht im Qualitätsbericht für März 2025.',
 'Sind die doppelten Zeilen ein technischer Fehler beim Abzug der Daten, oder können sie zwei echte Verhältnisse sein?',
 'E02_volldubletten', '2025-03'),

('R8', 'Kurze Zweitmeldungen derselben Person', 'alle ab lieferung_2024-08',
 'Jeden Monat beginnen 216 bis 322 Verhältnisse, deren Person am Stichtag schon ein zweites Verhältnis mit gleicher Qualifikation, Branche und gleichem Bundesland hat. Im August 2024 sind es 216, und 196 davon haben eine Kennung zwischen 859780 und 864885.',
 '216 Verhältnisse am Stichtag 31.08.2024 in Lieferung 2024-08; 216 bis 322 je Monat, so zählt sie auch der Qualitätsbericht', 'ganze Zeile (das zweite Verhältnis)',
 '[859975, 860000, 860337, 861206, 861975]',
 'WITH a AS (SELECT DISTINCT ON (vvh_id) vvh_id, person_id, qualifikation, oenace, bundesland, beginn FROM bereinigt.abschnitt WHERE lieferung = ''2024-08'' AND regelsatz = ''v1'' AND beginn <= ''2024-08-31'' AND (ende IS NULL OR ende >= ''2024-08-31'') ORDER BY vvh_id, beginn DESC) SELECT n.vvh_id::text AS vvh_id FROM a n WHERE n.beginn >= ''2024-08-01'' AND n.person_id IS NOT NULL AND EXISTS (SELECT 1 FROM a z WHERE z.person_id = n.person_id AND z.vvh_id <> n.vvh_id AND z.qualifikation = n.qualifikation AND z.oenace = n.oenace AND z.bundesland = n.bundesland)',
 'Wir zählen sie mit, denn gezählt werden Verhältnisse und nicht Personen, und auch der Beispielbericht zählt sie. Im Qualitätsbericht sind sie gekennzeichnet und als „nicht erklärbar“ eingestuft, bis ihr antwortet. Ausschließen könnten wir sie nur mit Wissen aus der nächsten Lieferung, und die darf ein Monat nicht nutzen.',
 'Sind das echte zweite Verhältnisse oder doppelte Meldungen, die wir nicht zählen sollen?',
 'P19_phantom_doppelmeldung', '2024-08'),

('R9', 'Lieferung 2024-08 ohne die im August beendeten Verhältnisse', 'lieferung_2024-08',
 'Lieferung 2024-08 enthält nur 48 Verhältnisse, die im August vor dem Monatsletzten enden, die anderen Lieferungen je 6.614 bis 17.664 im eigenen Monat. Außerdem enthält sie kein Verhältnis, das im Juni oder Juli 2024 endete, sie ist also kein Vollabzug über drei Monate.',
 '5.736 Verhältnisse enden in Lieferung 2024-08 im August, nur 48 davon vor dem 31.08.2024; in den anderen Lieferungen enden 6.614 bis 17.664 vor dem Monatsletzten', 'Ende im Berichtsmonat',
 '[]',
 'SELECT DISTINCT vvh_id FROM roh.lieferung WHERE lieferung = ''2024-08'' AND ende ~ ''^\d{4}-\d{2}-\d{2}$'' AND left(ende, 7) = ''2024-08''',
 'Die Zählung am Stichtag bleibt, wie sie ist; sie stimmt mit dem Beispielbericht in allen 2.880 Zellen überein. Zählen wir über den ganzen Monat, rechnen wir August 2024 nur aus der eigenen Lieferung und kennzeichnen den Monat als eingeschränkt: Die Monatszählung liegt dort nur 48 Verhältnisse über dem Stichtag, im September 2024 um 7.746. Wie viele Verhältnisse im August fehlen, ist nicht gemessen. Aus Lieferung 2024-09 ergänzen wir nichts, weil ein Monat keine späteren Lieferungen nutzen darf.',
 'Kommt für August 2024 noch eine vollständige Lieferung mit den Verhältnissen, die im August geendet haben?',
 'P24_lieferumfang_fenster', '2024-08'),

('R10', 'Große Gruppen springen ohne Saisongrund um mehr als 3 %',
 'lieferung_2024-09, lieferung_2024-10, lieferung_2024-12, lieferung_2025-03, lieferung_2025-07, lieferung_2025-08, lieferung_2025-09, lieferung_2025-12, lieferung_2026-01, lieferung_2026-03, lieferung_2026-07',
 'In 11 Monaten ändern sich 19 Gruppen mit mindestens 500 Verhältnissen um 3,1 bis 7,5 % gegenüber dem Vormonat, ohne dass die Saison das erklärt, zum Beispiel Erziehung und Unterricht (ÖNACE P) im Dezember 2024 um 5,4 % mehr und das Burgenland im Dezember 2025 um 3,1 % weniger.',
 '199.194 Sätze am jeweiligen Stichtag in den 19 Gruppen; die Gruppen haben 469 bis 21.387 Verhältnisse', 'Branche (ÖNACE) und Bundesland, Zahl der Verhältnisse je Gruppe',
 '[]',
 'SELECT l.vvh_id FROM meta.lauf f JOIN meta.pruefung_treffer t ON t.lauf_id = f.id JOIN meta.regel r ON r.id = t.regel_id CROSS JOIN LATERAL jsonb_array_elements(t.details -> ''zellen'') z JOIN roh.lieferung l ON l.lieferung = f.lieferung AND l.beginn <= to_char(to_date(f.lieferung, ''YYYY-MM'') + interval ''1 month - 1 day'', ''YYYY-MM-DD'') AND (l.ende IS NULL OR l.ende >= to_char(to_date(f.lieferung, ''YYYY-MM'') + interval ''1 month - 1 day'', ''YYYY-MM-DD'')) AND CASE z ->> ''gliederung'' WHEN ''oenace'' THEN l.oenace WHEN ''region'' THEN l.bundesland END = z ->> ''code'' WHERE r.name = ''P14_sprung_aggregat'' AND f.regelsatz = ''v1'' AND t.einstufung = ''nicht-erklaerbar'' AND NOT (z ->> ''saison'')::boolean AND f.id = (SELECT m.id FROM meta.lauf m WHERE m.lieferung = f.lieferung AND m.regelsatz = ''v1'' AND m.status IN (''fertig'', ''unveraendert'') ORDER BY (m.ergebnis_status = ''endgueltig'') DESC, m.id DESC LIMIT 1)',
 'Wir zählen die Verhältnisse so, wie sie geliefert sind, und kennzeichnen jeden Sprung im Qualitätsbericht mit Gruppe, Monat und Prozent als „nicht erklärbar“. Ohne eure Auskunft wäre jede Korrektur ein Eingriff in eine Entwicklung, die echt sein kann.',
 'Kennt ihr für diese Sprünge eine Ursache in den Meldungen der Dienstgeber?',
 'P14_sprung_aggregat', '2024-09')

ON CONFLICT (nr) DO UPDATE
  SET titel = EXCLUDED.titel, lieferungen = EXCLUDED.lieferungen, aufgefallen = EXCLUDED.aufgefallen,
      anzahl = EXCLUDED.anzahl, merkmale = EXCLUDED.merkmale, beispiele = EXCLUDED.beispiele,
      beleg_sql = EXCLUDED.beleg_sql, vorschlag = EXCLUDED.vorschlag, frage = EXCLUDED.frage,
      regel_name = EXCLUDED.regel_name, ab_lieferung = EXCLUDED.ab_lieferung;
-- gestellt_am, antwort und antwort_am trägt die Fachabteilung ein; das erneute Einspielen ändert sie nie.
