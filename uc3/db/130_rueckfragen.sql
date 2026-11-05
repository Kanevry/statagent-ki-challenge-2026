-- Rückfragen an die Fachabteilung nach Veranstaltervorlage (rueckfrage_vorlage.md), mit Beleg.
-- `vorschlag` ist unsere Annahme, bis die Fachabteilung antwortet; umgesetzt ist sie als Regel `regel_name`
-- (Parameter in meta.regel). Kommt eine Antwort, ändert sich nur die Regel, per Freigabe mit Namen.
-- Nummern R1–R5 nach GitLab #72 AC1 (Geburtsmonat 13, ÖNACE-Wellen, Teil-Lieferung 2025-10, fehlende FD 2025-03,
-- Spaltentausch 2025-06), danach R6–R8. Umnummeriert am 05.11.2026, als noch keine Antwort eingetragen war.
-- `beleg_sql` liefert je betroffenem Satz eine Zeile mit `vvh_id` (ohne Semikolon); der Generator
-- (statagent/berichte/rueckfragen.py) zählt damit nach und zieht die Beispiel-IDs. Die erste Zahl in `anzahl`
-- ist die Trefferzahl dieser Abfrage, gemessen am 05.11.2026 in der Datenbank statistik. Beispiel-IDs sind VVH_IDs.

INSERT INTO meta.rueckfrage (nr, titel, lieferungen, aufgefallen, anzahl, merkmale, beispiele, beleg_sql, vorschlag, frage,
                             regel_name, ab_lieferung) VALUES

('R1', 'Geburtsmonat 13', 'lieferung_2024-08 und alle weiteren',
 'Geburtsdaten mit Monat 13 (z. B. 1963-13-09). Der Beispielbericht 08/2024 zählt diese Verhältnisse nicht als „Alter unbekannt“, sondern mit Alter = Berichtsjahr − Geburtsjahr.',
 '370 Sätze am 31.08.2024 (Lieferung 2024-08); 336–444 Sätze je Lieferung', 'GEBURTSDATUM → Alter (Tab13)',
 '[1050, 1824, 2257, 5493, 7739]',
 'SELECT vvh_id FROM roh.lieferung WHERE lieferung = ''2024-08'' AND substr(geburtsdatum, 6, 2) = ''13'' AND beginn <= ''2024-08-31'' AND (ende IS NULL OR ende >= ''2024-08-31'')',
 'Monat 13 heißt „Monat unbekannt“. Wir setzen den 1. Juli des Geburtsjahres ein (Jahresmitte, die beste Schätzung bei nur bekanntem Jahr; Praxis z. B. NHS England) und rechnen das vollendete Alter. Für 08/2024 ergibt das genau den Beispielbericht. Die Fälle stehen im Qualitätsbericht (P04); der Ersatztag ist ein Parameter der Regel R5_alter.',
 'Welcher Ersatztag gilt bei Geburtsmonat 13? Für 08/2024 führen 1.1. und 1.7. zu denselben Zahlen, für Berichtsmonate vor Juli nicht.',
 'R5_alter', '2024-08'),

('R2', 'Wellen von ÖNACE-Wechseln (05/2025, 02/2026)', 'lieferung_2025-05, lieferung_2026-02',
 '491 Verhältnisse in der Steiermark wechseln am 01.05.2025 von O nach C (darunter 11 Beamte), 347 in Wien am 01.02.2026 von G nach C, jeweils als neuer Zeitabschnitt am selben Tag.',
 '838 Verhältnisse: 491 (2025-05) und 347 (2026-02)', 'OENACE (neuer Zeitabschnitt)',
 '[125007, 229275, 229304, 229324, 229333]',
 'SELECT n.vvh_id FROM roh.lieferung n WHERE ((n.lieferung = ''2025-05'' AND n.beginn = ''2025-05-01'' AND n.oenace = ''C'' AND n.bundesland = ''6'') OR (n.lieferung = ''2026-02'' AND n.beginn = ''2026-02-01'' AND n.oenace = ''C'' AND n.bundesland = ''9'')) AND EXISTS (SELECT 1 FROM roh.lieferung a WHERE a.lieferung = n.lieferung AND a.vvh_id = n.vvh_id AND a.oenace = CASE n.lieferung WHEN ''2025-05'' THEN ''O'' ELSE ''G'' END AND a.ende < n.beginn)',
 'Wir zählen die Verhältnisse im neuen Abschnitt C, wie geliefert, und weisen die Welle im Qualitätsbericht als nicht erklärbar aus (P18).',
 'Handelt es sich um echte Umklassifizierungen von Dienstgebern oder um Codierfehler?',
 'P18_merkmalswelle', '2025-05'),

('R3', 'Teil-Lieferung 2025-10', 'lieferung_2025-10',
 'In Lieferung 2025-10 fehlen rund 20 % der Verhältnisse (345.078 Zeilen statt rund 430.000). Die Lücke verteilt sich gleichmäßig über Bundesland, ÖNACE und Qualifikation; fast alle fehlenden Verhältnisse stehen in 2025-11 wieder.',
 '78.949 am 30.09.2025 offene Verhältnisse fehlen, 78.733 davon wieder in 2025-11, 216 nicht', 'alle, gleichmäßig etwa 20 %',
 '[34, 79, 95, 122, 133]',
 'SELECT s.vvh_id FROM (SELECT DISTINCT vvh_id FROM roh.lieferung WHERE lieferung = ''2025-09'' AND beginn <= ''2025-09-30'' AND (ende IS NULL OR ende >= ''2025-09-30'')) s WHERE NOT EXISTS (SELECT 1 FROM roh.lieferung l WHERE l.lieferung = ''2025-10'' AND l.vvh_id = s.vvh_id)',
 'Die fehlenden Verhältnisse werden einmalig aus Lieferung 2025-09 fortgeschrieben, wenn dort ein am 31.10.2025 gültiger Abschnitt vorliegt (Regel E07); keine Hochrechnung, keine späteren Lieferungen. Gelieferter und fortgeschriebener Bestand stehen getrennt im Qualitätsbericht, der Lauf hält an (P15–P17) und der Monat bleibt vorläufig. Mit Lieferung 2025-11 steht die Abweichung als Revisionsbedarf im Bericht.',
 'Kommt eine vollständige Nachlieferung für 2025-10? Wenn nicht: Ist das Fortschreiben aus 2025-09 zulässig, und wie sind die 216 Verhältnisse zu behandeln, die auch in 2025-11 fehlen? Für die Ministeriums-Lieferung (Auftrag 3) nehmen wir August 2025 aus Lieferung 2025-09 statt aus der Teil-Lieferung 2025-10 (32.713 Personen; wörtlich „jüngste Lieferung je Tag“ mit 2025-10 wären es 32.639): Ist das so gewünscht?',
 'E07_fortschreibung_lieferausfall', '2025-10'),

('R4', 'Freie Dienstverträge fehlen in Lieferung 2025-03', 'lieferung_2025-03',
 'In Lieferung 2025-03 fehlen alle freien Dienstverträge (ArbeiterFD, AngestellteFD). Die anderen Lieferungen enthalten 1.316 bis 1.697 solche Sätze; die betroffenen Verhältnisse stehen in 2025-02 und 2025-04 unverändert.',
 '1.492 am 28.02.2025 bestehende FD-Verhältnisse fehlen, alle wieder in 2025-04; Lieferung 2025-03 hat 0 FD-Sätze', 'QUAL (ArbeiterFD, AngestellteFD)',
 '[448, 1054, 1264, 1289, 2247]',
 'SELECT DISTINCT p.vvh_id FROM roh.lieferung p WHERE p.lieferung = ''2025-02'' AND p.qual LIKE ''%FD'' AND p.beginn <= ''2025-02-28'' AND (p.ende IS NULL OR p.ende >= ''2025-02-28'') AND NOT EXISTS (SELECT 1 FROM roh.lieferung l WHERE l.lieferung = ''2025-03'' AND l.vvh_id = p.vvh_id)',
 'Die fehlenden FD-Verhältnisse werden einmalig aus Lieferung 2025-02 fortgeschrieben, wenn dort ein am 31.03.2025 gültiger Abschnitt vorliegt (Regel E07, Praxis einperiodiger Fortschreibung bei Meldeausfall). Gelieferter und fortgeschriebener Bestand stehen getrennt im Qualitätsbericht, der Monat bleibt vorläufig (P13 hält an). Mit Lieferung 2025-04 erscheint die Abweichung als Revisionsbedarf.',
 'Ist das ein Lieferfehler (Teilabzug ohne FD)? Dürfen wir aus 2025-02 fortschreiben, oder wird 03/2025 ohne FD veröffentlicht und erst in der Revision korrigiert?',
 'E07_fortschreibung_lieferausfall', '2025-03'),

('R5', 'BEGINN und ENDE vertauscht in Lieferung 2025-06', 'lieferung_2025-06',
 'In Lieferung 2025-06 ist BEGINN bei 388.115 von 432.086 Sätzen leer, bei 43.914 Sätzen liegt BEGINN nach ENDE, ENDE ist immer gefüllt. Keine andere Lieferung hat leere BEGINN. Ohne Tausch bestünden am 30.06.2025 nur 21 Verhältnisse.',
 '388.115 von 432.086 Sätzen mit leerem BEGINN; getauscht werden alle 432.086 Sätze der Lieferung', 'BEGINN, ENDE (ganze Lieferung)',
 '[7, 12, 14, 33, 34]',
 'SELECT vvh_id FROM roh.lieferung WHERE lieferung = ''2025-06'' AND beginn IS NULL',
 'BEGINN und ENDE werden für die ganze Lieferung getauscht (Regel E01: mehr als 50 % BEGINN leer und mehr als 5 % BEGINN nach ENDE). Nach dem Tausch bestehen am 30.06.2025 394.252 Verhältnisse (Nachbarmonate 390.001 und 397.419); kein Verhältnis geht verloren. Der Tausch steht im Qualitätsbericht 06/2025 (P03).',
 'Wurden BEGINN und ENDE in Lieferung 2025-06 vertauscht geliefert? Dürfen wir sie für die ganze Lieferung tauschen, oder kommt eine korrigierte Nachlieferung?',
 'E01_spaltentausch_beginn_ende', '2025-06'),

('R6', 'Plausibilitätsgrenze Alter', 'lieferung_2024-08 und alle weiteren',
 'Formal gültige Geburtsdaten mit einem Alter von 117 bis 153 Jahren (Geburtsjahre ab 1871). Der Beispielbericht zählt sie unter „unbekannt“, die Zeile „75 u. mehr“ ist 0. Ab 09/2024 gibt es echte 75- bis 77-Jährige (Geburtsjahre 1948–1951).',
 '7 Verhältnisse am 31.08.2024; 7–14 Sätze je Lieferung', 'GEBURTSDATUM → Alter (Tab13)',
 '[149431, 207859, 327231]',
 'SELECT vvh_id FROM roh.lieferung WHERE lieferung = ''2024-08'' AND geburtsdatum < ''1913-09-01'' AND beginn <= ''2024-08-31'' AND (ende IS NULL OR ende >= ''2024-08-31'')',
 'Ein Alter über 110 Jahre gilt als unplausibel und wird als „unbekannt“ ausgewiesen; das Verhältnis zählt. 110 ist eine großzügige eigene Prüfgrenze (die ILO empfiehlt keine obere Altersgrenze für Erwerbstätige). Eine Grenze von 74 würde ab 09/2024 echte 75-Jährige wegkorrigieren (62 bis 310 Fälle je Monat).',
 'Wo liegt die Plausibilitätsgrenze (75, 100 oder eine andere)? Gilt dieselbe Grenze für das Geburtsjahr in der Ministeriums-Lieferung?',
 'R5_alter', '2024-08'),

('R7', 'Volldubletten in Lieferung 2025-03', 'lieferung_2025-03',
 'In Lieferung 2025-03 kommen 1.663 Zeilen genau doppelt vor, in allen neun Feldern gleich. Alle anderen 23 Lieferungen haben keine.',
 '1.663 überzählige Zeilen; ohne Verdichtung 1.523 Verhältnisse am 31.03.2025 doppelt (388.703 statt 387.180)', 'ganzer Satz',
 '[100071, 100136, 10047]',
 'SELECT vvh_id FROM roh.lieferung WHERE lieferung = ''2025-03'' GROUP BY vvh_id, person_id, geburtsdatum, geschlecht, beginn, ende, qual, oenace, bundesland HAVING count(*) > 1',
 'Exakte Dubletten werden zu einem Satz verdichtet (Anhang A Nr. 1), ihre Anzahl steht im Qualitätsbericht 03/2025 (P01).',
 'Bestätigt ihr, dass es sich um einen technischen Doppelabzug handelt und nicht um zwei Verhältnisse?',
 'E02_volldubletten', '2025-03'),

('R8', 'Kurzlebige Zweitmeldungen derselben Person', 'alle ab lieferung_2024-08',
 'VVH_IDs im Bereich 859780 bis 864885 beginnen im Berichtsmonat, und dieselbe Person hat am Stichtag ein zweites Verhältnis mit gleicher Qualifikation, ÖNACE und Bundesland. Der Bereich kommt in allen 24 Lieferungen vor (131–218 Sätze je Lieferung, Annahme A10); dass jedes dieser Verhältnisse nur in einer Lieferung sichtbar ist, ist nicht bestätigt.',
 '196 Sätze in Lieferung 2024-08; 131–218 Sätze je Lieferung', 'ganzer Satz (zweites Verhältnis)',
 '[859975, 860000, 860337, 861206, 861975]',
 'SELECT vvh_id FROM roh.lieferung WHERE lieferung = ''2024-08'' AND CASE WHEN vvh_id ~ ''^[0-9]+$'' THEN vvh_id::bigint END BETWEEN 859780 AND 864885',
 'Wir zählen sie (Zählregel 1: Verhältnisse, nicht Personen; der Beispielbericht zählt sie mit) und kennzeichnen sie im Qualitätsbericht (P19).',
 'Sind das echte zweite Verhältnisse oder Doppelmeldungen, die nicht gezählt werden sollen?',
 'P19_phantom_doppelmeldung', '2024-08'),

('R9', 'Lieferung 2024-08 ohne Vollabzug der Monatsenden', 'lieferung_2024-08',
 'In Lieferung 2024-08 enden nur 5.736 Verhältnisse im Berichtsmonat, in den anderen Lieferungen 13.133 bis 15.000 (gemessen 2024-09, 2024-10, 2025-01, 2026-07). Für den Stichtag 31.08. spielt das keine Rolle (Beispielbericht 2.880/2.880 Zellen). Für eine Zählung über den ganzen Monat (Auftrag 2) fehlen damit rund 8.000 Verhältnisse, die im August 2024 beendet wurden; Lieferung 2024-09 kann sie nicht ergänzen, weil jede Lieferung nur ihren eigenen Monat zählt.',
 '5.736 Verhältnisse enden in Lieferung 2024-08 im August; in anderen Lieferungen 13.133 bis 15.000 im eigenen Monat', 'ENDE im Berichtsmonat',
 '[]',
 'SELECT DISTINCT vvh_id FROM roh.lieferung WHERE lieferung = ''2024-08'' AND ende ~ ''^\d{4}-\d{2}-\d{2}$'' AND left(ende, 7) = ''2024-08''',
 'Stichtagszählung (v1) unverändert. Bei einer Monatszählung (Auftrag 2) wird 2024-08 aus der eigenen Lieferung gerechnet und als vorläufig mit diesem Hinweis ausgewiesen; keine Ergänzung aus späteren Lieferungen (Anhang A, eigene oder frühere Lieferungen).',
 'Ist Lieferung 2024-08 ein Teilabzug ohne die im August beendeten Verhältnisse? Kommt eine vollständige Lieferung, oder soll 2024-08 in der Monatszählung mit diesem Vorbehalt stehen bleiben?',
 'P24_lieferumfang_fenster', '2024-08')

ON CONFLICT (nr) DO UPDATE
  SET titel = EXCLUDED.titel, lieferungen = EXCLUDED.lieferungen, aufgefallen = EXCLUDED.aufgefallen,
      anzahl = EXCLUDED.anzahl, merkmale = EXCLUDED.merkmale, beispiele = EXCLUDED.beispiele,
      beleg_sql = EXCLUDED.beleg_sql, vorschlag = EXCLUDED.vorschlag, frage = EXCLUDED.frage,
      regel_name = EXCLUDED.regel_name, ab_lieferung = EXCLUDED.ab_lieferung;
-- gestellt_am, antwort und antwort_am trägt die Fachabteilung ein; das erneute Einspielen ändert sie nie.
