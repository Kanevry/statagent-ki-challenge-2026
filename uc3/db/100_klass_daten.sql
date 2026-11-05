-- Klassifikationen der Beschäftigtenstatistik, je Begriff einmal (Schritt 2, Mindestumfang).
-- Quelle: klassifikation.* aus dem Startpaket (geladen von datenbank/02_laden.sql des Veranstalters).
-- Idempotent: ON CONFLICT DO NOTHING, nichts wird überschrieben.

INSERT INTO stat.beschreibung (statistik, name, quelle, statistiktyp, dimensionen, anmerkungen) VALUES (
  'beschaeftigte',
  'Beschäftigtenstatistik (Versicherungsverhältnisse)',
  'Monatliche Lieferung der Zentralen Versicherungsdatei (roh.lieferung), synthetisch, etwa ein Zehntel Österreichs',
  'einzeldaten',
  '[{"spalte":"region","klassifikation":"klass_region","ebene":"bundesland"},
    {"spalte":"oenace","klassifikation":"klass_oenace","ebene":1},
    {"spalte":"geschlecht","klassifikation":"klass_geschlecht","ebene":1},
    {"spalte":"qualifikation","klassifikation":"klass_qualifikation","ebene":1},
    {"spalte":"alter","klassifikation":"klass_alter","ebene":1}]'::jsonb,
  'Zähleinheit ist das Versicherungsverhältnis (VVH_ID), nicht die Person. Jeder Berichtsmonat aus seiner eigenen Lieferung; Veröffentlichtes bleibt unverändert, Abweichungen späterer Lieferungen stehen als Revisionsbedarf im Qualitätsbericht.'
) ON CONFLICT (statistik) DO NOTHING;

INSERT INTO stat.variable (statistik, code, bezeichnung, beschreibung, einheit) VALUES (
  'beschaeftigte', 'Beschaeftigungsverhaeltnisse', 'Beschäftigungsverhältnisse',
  'Anzahl der Versicherungsverhältnisse (VVH_ID), die im Berichtszeitraum bestehen. Regelsatz v1: am Stichtag (Monatsletzter) besteht ein Zeitabschnitt mit Beginn ≤ Stichtag und Ende leer oder ≥ Stichtag; Merkmale aus diesem Abschnitt; jedes Verhältnis einmal. Die genaue Zählregel je Regelstand steht in meta.regel (typ zaehl).',
  'Anzahl'
) ON CONFLICT (statistik, code) DO NOTHING;

-- Geschlecht (+ 'U' unbekannt, damit kein Satz ohne Code bleibt; in den Lieferungen bisher 0 Fälle)
INSERT INTO stat.klass_geschlecht (code, bezeichnung)
SELECT code, bezeichnung FROM klassifikation.geschlecht
UNION ALL SELECT 'U', 'Geschlecht unbekannt'
ON CONFLICT (code) DO NOTHING;

-- Region: Österreich, Bundesländer 1–9, 0 = unbekannt
INSERT INTO stat.klass_region (version, code, bezeichnung, ebene, uebergeordnet, gueltig_von)
SELECT 'BL', 'AT', 'Österreich', 'staat', NULL, DATE '1900-01-01'
UNION ALL
SELECT 'BL', code, bezeichnung, 'bundesland', 'AT', DATE '1900-01-01' FROM klassifikation.bundesland
ON CONFLICT (version, code) DO NOTHING;

-- Qualifikation mit Beschäftigungskategorie und FD-Kennzeichen (+ 'UNB')
INSERT INTO stat.klass_qualifikation (code, bezeichnung, beschaeftigungskategorie, freier_dienstvertrag)
SELECT code, bezeichnung, beschaeftigungskategorie, freier_dienstvertrag = 'J' FROM klassifikation.qualifikation
UNION ALL SELECT 'UNB', 'Qualifikation unbekannt', 'Unbekannt', NULL
ON CONFLICT (code) DO NOTHING;

INSERT INTO stat.klass_beschaeftigungskategorie (code, bezeichnung)
SELECT DISTINCT beschaeftigungskategorie, beschaeftigungskategorie FROM klassifikation.qualifikation
UNION SELECT 'Unbekannt', 'Beschäftigungskategorie unbekannt'
ON CONFLICT (code) DO NOTHING;

-- ÖNACE: 2008 gilt für Berichtsmonate bis 12/2024, 2025 ab 01/2025 (Fachbeschreibung § 3, § 4 Nr. 7).
INSERT INTO stat.klass_oenace (version, code, bezeichnung, ebene, uebergeordnet, gueltig_von, gueltig_bis)
SELECT '2008', code, bezeichnung, 1, NULL, DATE '2008-01-01', DATE '2024-12-31' FROM klassifikation.oenace_2008
ON CONFLICT (version, code) DO NOTHING;
INSERT INTO stat.klass_oenace (version, code, bezeichnung, ebene, uebergeordnet, gueltig_von, gueltig_bis)
SELECT '2025', code, bezeichnung, 1, NULL, DATE '2025-01-01', NULL FROM klassifikation.oenace_2025
ON CONFLICT (version, code) DO NOTHING;

-- ÖNACE 2003, Abschnitt D und seine Unterabschnitte: kommen als Altcodes in jeder Lieferung vor
-- (je etwa 50 Sätze). Titel aus OENACE2003_DE_COT.txt des Startpakets.
INSERT INTO stat.klass_oenace (version, code, bezeichnung, ebene, uebergeordnet, gueltig_von, gueltig_bis) VALUES
  ('2003', 'D',  'Sachgütererzeugung', 1, NULL, DATE '2003-01-01', DATE '2007-12-31'),
  ('2003', 'DA', 'Herstellung von Nahrungs- und Genussmitteln und Getränken; Tabakverarbeitung', 2, 'D', DATE '2003-01-01', DATE '2007-12-31'),
  ('2003', 'DB', 'Herstellung von Textilien, Textilwaren und Bekleidung', 2, 'D', DATE '2003-01-01', DATE '2007-12-31'),
  ('2003', 'DC', 'Ledererzeugung und -verarbeitung, Herstellung von Schuhen', 2, 'D', DATE '2003-01-01', DATE '2007-12-31'),
  ('2003', 'DD', 'Be- und Verarbeitung von Holz (ohne Herstellung von Möbeln)', 2, 'D', DATE '2003-01-01', DATE '2007-12-31'),
  ('2003', 'DE', 'Herstellung und Verarbeitung von Papier und Pappe, Verlagswesen, Druckerei und Vervielfältigung', 2, 'D', DATE '2003-01-01', DATE '2007-12-31'),
  ('2003', 'DF', 'Kokerei, Mineralölverarbeitung, Herstellung und Verarbeitung von Spalt- und Brutstoffen', 2, 'D', DATE '2003-01-01', DATE '2007-12-31'),
  ('2003', 'DG', 'Herstellung von Chemikalien und chemischen Erzeugnissen', 2, 'D', DATE '2003-01-01', DATE '2007-12-31'),
  ('2003', 'DH', 'Herstellung von Gummi- und Kunststoffwaren', 2, 'D', DATE '2003-01-01', DATE '2007-12-31'),
  ('2003', 'DI', 'Herstellung und Bearbeitung von Glas, Herstellung von Waren aus Steinen und Erden', 2, 'D', DATE '2003-01-01', DATE '2007-12-31'),
  ('2003', 'DJ', 'Metallerzeugung und -bearbeitung, Herstellung von Metallerzeugnissen', 2, 'D', DATE '2003-01-01', DATE '2007-12-31'),
  ('2003', 'DK', 'Maschinenbau', 2, 'D', DATE '2003-01-01', DATE '2007-12-31'),
  ('2003', 'DL', 'Herstellung von Büromaschinen, Datenverarbeitungsgeräten und -einrichtungen; Elektrotechnik, Feinmechanik und Optik', 2, 'D', DATE '2003-01-01', DATE '2007-12-31'),
  ('2003', 'DM', 'Fahrzeugbau', 2, 'D', DATE '2003-01-01', DATE '2007-12-31'),
  ('2003', 'DN', 'Herstellung von Möbeln, Schmuck, Musikinstrumenten, Sportgeräten, Spielwaren und sonstigen Erzeugnissen; Rückgewinnung (Recycling)', 2, 'D', DATE '2003-01-01', DATE '2007-12-31')
ON CONFLICT (version, code) DO NOTHING;

-- Übergang ÖNACE 2003 (Unterabschnitt) → 2008 (Abschnitt). Abgeleitet aus OENACE2003_OENACE2008_DE_12B.txt:
-- je Unterabschnitt das Ziel der Mehrheit seiner 6-Steller (DA 49/49 C, DE 25 C, 6 J, 1 R, …).
INSERT INTO stat.uebergang (klassifikation, version_alt, code_alt, version_neu, code_neu, beziehung, gueltig_ab, quelle)
SELECT 'oenace', '2003', c, '2008', 'C', CASE WHEN c = 'DE' THEN 'm:n' ELSE 'n:1' END, DATE '2008-01-01',
       'OENACE2003_OENACE2008_DE_12B.txt, Mehrheit der 6-Steller'
FROM unnest(ARRAY['DA','DB','DC','DD','DE','DF','DG','DH','DI','DJ','DK','DL','DM','DN']) AS c
ON CONFLICT DO NOTHING;
INSERT INTO stat.uebergang (klassifikation, version_alt, code_alt, version_neu, code_neu, beziehung, gueltig_ab, quelle)
VALUES ('oenace', '2003', 'DE', '2008', 'J', 'm:n', DATE '2008-01-01', 'OENACE2003_OENACE2008_DE_12B.txt (Verlagswesen, 6 von 32 Sechsstellern)')
ON CONFLICT DO NOTHING;

-- Alter in vollendeten Jahren, Berichtsgruppen wie Tab13 des Beispielberichts
INSERT INTO stat.klass_alter (code, bezeichnung, berichtsgruppe)
SELECT a, a || ' Jahre',
       CASE WHEN a <= 14 THEN 'bis 14' WHEN a >= 75 THEN '75 u. mehr' ELSE a::text END
FROM generate_series(0, 130) AS a
UNION ALL SELECT -1, 'Alter unbekannt', 'unbekannt'
ON CONFLICT (code) DO NOTHING;
