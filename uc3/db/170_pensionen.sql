-- Pensionsstatistik 2018–2025 (#77, Anhang B): eigene stat_-Tabelle, Klassifikationen der Träger und Pensionsarten,
-- Übergänge zum 1.1.2020, Quellzuordnung und Regeln als Daten. `klass_geschlecht` ist dieselbe wie bei den Beschäftigten.
-- Alles gehört zum eigenen Regelsatz `pensionen-v1`: der Regelstand von v1 und v2 filtert nach Regelsatz und bleibt gleich.
-- Idempotent, lädt keine Zahlen. Die Zahlen schreibt `uc3 pensionen laden`.

ALTER TABLE stat.quellzuordnung DROP CONSTRAINT IF EXISTS quellzuordnung_merkmal_check;
ALTER TABLE stat.quellzuordnung ADD CONSTRAINT quellzuordnung_merkmal_check
  CHECK (merkmal IN ('geschlecht', 'qualifikation', 'oenace', 'bundesland', 'versicherungstraeger', 'pensionsart'));

-- Blätter sind die Gliederung der Träger, Knoten darüber die Summen. Versicherungsbereiche sind frühere Träger,
-- keine Merkmale der Beschäftigten: PVA-ARB und PVA-ANG gehören nicht in klass_qualifikation.
CREATE TABLE IF NOT EXISTS stat.klass_versicherungstraeger (
  code text PRIMARY KEY, bezeichnung text NOT NULL,
  ebene int NOT NULL, uebergeordnet text REFERENCES stat.klass_versicherungstraeger (code),
  gueltig_von date NOT NULL, gueltig_bis date, anmerkung text
);

INSERT INTO stat.klass_versicherungstraeger (code, bezeichnung, ebene, uebergeordnet, gueltig_von, gueltig_bis, anmerkung) VALUES
('INSG',     'Insgesamt',                                                    1, NULL,     '1900-01-01', NULL, 'Summe, wird nicht gemeldet'),
('PV-UNS',   'Pensionsversicherung der Unselbständigen',                     2, 'INSG',   '1900-01-01', NULL, 'Summe, wird nicht gemeldet'),
('PV-SEL',   'Pensionsversicherung der Selbständigen',                       2, 'INSG',   '1900-01-01', NULL, 'Summe, wird nicht gemeldet'),
('PVA',      'Pensionsversicherungsanstalt',                                 3, 'PV-UNS', '2003-01-01', NULL, NULL),
('PVA-ARB',  'Arbeiter (frühere PVA der Arbeiter)',                          4, 'PVA',    '2003-01-01', NULL, 'Versicherungsbereich, nicht die Qualifikation Arbeiter der Beschäftigtenstatistik'),
('PVA-ANG',  'Angestellte (frühere PVA der Angestellten)',                   4, 'PVA',    '2003-01-01', NULL, 'Versicherungsbereich, nicht die Qualifikation Angestellte der Beschäftigtenstatistik'),
('VAEB',     'Versicherungsanstalt für Eisenbahnen und Bergbau',             3, 'PV-UNS', '2005-01-01', '2019-12-31', NULL),
('VAEB-EB',  'Eisenbahn',                                                    4, 'VAEB',   '2005-01-01', '2019-12-31', NULL),
('VAEB-BB',  'Bergbau',                                                      4, 'VAEB',   '2005-01-01', '2019-12-31', NULL),
('BVA',      'Versicherungsanstalt öffentlich Bediensteter',                 3, 'PV-UNS', '1900-01-01', '2019-12-31', 'Liefert in diesem Paket keine Pensionsmeldung'),
('BVAEB',    'Versicherungsanstalt öffentlich Bediensteter, Eisenbahnen und Bergbau', 3, 'PV-UNS', '2020-01-01', NULL, NULL),
('BVAEB-EB', 'Eisenbahn',                                                    4, 'BVAEB',  '2020-01-01', NULL, NULL),
('BVAEB-BB', 'Bergbau',                                                      4, 'BVAEB',  '2020-01-01', NULL, NULL),
('SVA',      'Sozialversicherungsanstalt der gewerblichen Wirtschaft',       3, 'PV-SEL', '1900-01-01', '2019-12-31', NULL),
('SVB',      'Sozialversicherungsanstalt der Bauern',                        3, 'PV-SEL', '1900-01-01', '2019-12-31', NULL),
('VAN',      'Versicherungsanstalt des österreichischen Notariates',         3, 'PV-SEL', '1900-01-01', '2019-12-31', 'Meldet nur den Pensionsstand'),
('SVS',      'Sozialversicherungsanstalt der Selbständigen',                 3, 'PV-SEL', '2020-01-01', NULL, NULL),
('SVS-GW',   'Gewerbliche Wirtschaft',                                       4, 'SVS',    '2020-01-01', NULL, NULL),
('SVS-LW',   'Landwirtschaft',                                               4, 'SVS',    '2020-01-01', NULL, NULL)
ON CONFLICT (code) DO NOTHING;

CREATE TABLE IF NOT EXISTS stat.klass_pensionsart (
  code text PRIMARY KEY, bezeichnung text NOT NULL,
  ebene int NOT NULL, uebergeordnet text REFERENCES stat.klass_pensionsart (code),
  gueltig_von date NOT NULL DEFAULT '1900-01-01', gueltig_bis date
);

INSERT INTO stat.klass_pensionsart (code, bezeichnung, ebene, uebergeordnet) VALUES
('T12',         'Stand der Pensionen (Tabelle 12)',                 1, NULL),
('T13',         'Vorzeitige Alterspensionen (Tabelle 13)',          1, NULL),
('GEM',         'Geminderte Arbeitsfähigkeit/Erwerbsunfähigkeit',   2, 'T12'),
('ALTER',       'Alter',                                            2, 'T12'),
('WITWE',       'Witwen/Witwer',                                    2, 'T12'),
('WAISE',       'Waisen',                                           2, 'T12'),
('LVD',         'Lange Versicherungsdauer',                         2, 'T13'),
('KORRIDOR',    'Korridorpension',                                  2, 'T13'),
('LZV',         'Langzeitversicherte',                              2, 'T13'),
('SCHWER_ASVG', 'Schwerarbeit § 607/14 ASVG',                       2, 'T13'),
('SCHWER_APG',  'Schwerarbeit § 4 Abs. 3 APG',                      2, 'T13')
ON CONFLICT (code) DO NOTHING;

-- Long-Format wie im Anhang B, dazu die Herkunft jeder Zahl (Datei, Blatt, Zelle).
CREATE TABLE IF NOT EXISTS stat.stat_pensionen (
  zeitraum_art text NOT NULL CHECK (zeitraum_art = 'Jahresdurchschnitt'),
  zeitraum_von date NOT NULL, zeitraum_bis date NOT NULL,
  versicherungstraeger text NOT NULL REFERENCES stat.klass_versicherungstraeger (code),
  pensionsart text NOT NULL REFERENCES stat.klass_pensionsart (code),
  geschlecht text NOT NULL REFERENCES stat.klass_geschlecht (code),
  variable text NOT NULL,
  wert bigint NOT NULL CHECK (wert >= 0),
  status text NOT NULL CHECK (status IN ('vorlaeufig', 'endgueltig')),
  stand text NOT NULL,
  regelstand text NOT NULL,
  quelle_datei text NOT NULL, quelle_blatt text NOT NULL, quelle_zelle text NOT NULL,
  PRIMARY KEY (zeitraum_von, versicherungstraeger, pensionsart, geschlecht, variable)
);

-- Ladeprotokoll: je Datei eine Zeile mit Format, Hash und Anzahl.
CREATE TABLE IF NOT EXISTS meta.pension_ladung (
  datei text PRIMARY KEY,                -- JJJJ/Dateiname
  jahr int NOT NULL,
  quelle text NOT NULL,                  -- stat.quellzuordnung.quelle
  regel_name text NOT NULL,              -- Formatregel in meta.regel
  sha256 text NOT NULL,
  werte int NOT NULL,
  summen int NOT NULL,
  ergebnis_hash text NOT NULL,           -- Hash über alle Dateien dieses Ladens
  regelstand text NOT NULL,
  geladen_am timestamptz NOT NULL DEFAULT now(),
  freigegeben_von text,
  freigegeben_am timestamptz
);

-- Summen aus den Dateien: nicht als Zahl der Statistik geladen, sondern als Prüfwert gegen die eigene Summe gehalten.
CREATE TABLE IF NOT EXISTS meta.pension_summe (
  datei text NOT NULL REFERENCES meta.pension_ladung (datei) ON DELETE CASCADE,
  blatt text NOT NULL, zelle text NOT NULL,
  jahr int NOT NULL,
  versicherungstraeger text NOT NULL,
  pensionsart text NOT NULL,
  geschlecht text,                       -- NULL: über beide Geschlechter
  gemeldet bigint NOT NULL,
  gerechnet bigint NOT NULL,
  PRIMARY KEY (datei, blatt, zelle)
);

INSERT INTO stat.beschreibung (statistik, name, quelle, statistiktyp, dimensionen, anmerkungen) VALUES (
  'pensionen',
  'Pensionsstatistik (Tabellen 12 und 13 der Jahresergebnisse)',
  'Jahresmeldungen der Pensionsversicherungsträger 2018 bis 2025, Ordner pensionen/ des Startpakets',
  'aggregiert',
  '[{"spalte":"versicherungstraeger","klassifikation":"klass_versicherungstraeger","ebene":4},
    {"spalte":"pensionsart","klassifikation":"klass_pensionsart","ebene":2},
    {"spalte":"geschlecht","klassifikation":"klass_geschlecht","ebene":1}]'::jsonb,
  'Jahresdurchschnitte. Vorzeitige Alterspensionen (Tabelle 13) sind ein Teil der Alterspensionen und werden nicht zu Tabelle 12 addiert. Summen über Träger bildet die Statistik selbst, Summen aus den Dateien sind nur Prüfwerte. Der Bruch 2019/2020 durch die Zusammenlegungen wird nicht geglättet.'
) ON CONFLICT (statistik) DO NOTHING;

INSERT INTO stat.variable (statistik, code, bezeichnung, beschreibung, einheit) VALUES (
  'pensionen', 'Pensionen', 'Pensionen',
  'Anzahl der Pensionen im Jahresdurchschnitt, wie vom Träger gemeldet. Bei Witwen/Witwer zählen Witwer als Männer und Witwen als Frauen.',
  'Anzahl'
) ON CONFLICT (statistik, code) DO NOTHING;

-- Übergänge zum 1.1.2020 auf Träger- und Bereichsebene (Zeitreihenbruch im Prüfbericht).
INSERT INTO stat.uebergang (klassifikation, version_alt, code_alt, version_neu, code_neu, beziehung, gueltig_ab, quelle) VALUES
('versicherungstraeger', '2019', 'SVA',     '2020', 'SVS',      'n:1', '2020-01-01', 'LIESMICH Pensionen, Zeile 25'),
('versicherungstraeger', '2019', 'SVB',     '2020', 'SVS',      'n:1', '2020-01-01', 'LIESMICH Pensionen, Zeile 25'),
('versicherungstraeger', '2019', 'VAN',     '2020', 'SVS',      'n:1', '2020-01-01', 'LIESMICH Pensionen, Zeile 26'),
('versicherungstraeger', '2019', 'VAEB',    '2020', 'BVAEB',    'n:1', '2020-01-01', 'LIESMICH Pensionen, Zeile 25'),
('versicherungstraeger', '2019', 'BVA',     '2020', 'BVAEB',    'n:1', '2020-01-01', 'LIESMICH Pensionen, Zeile 25'),
('versicherungstraeger', '2019', 'SVA',     '2020', 'SVS-GW',   'n:1', '2020-01-01', 'LIESMICH Pensionen, Zeile 21'),
('versicherungstraeger', '2019', 'VAN',     '2020', 'SVS-GW',   'n:1', '2020-01-01', 'Annahme: die Quelle nennt nur die SVS, ohne Sparte'),
('versicherungstraeger', '2019', 'SVB',     '2020', 'SVS-LW',   '1:1', '2020-01-01', 'LIESMICH Pensionen, Zeile 21'),
('versicherungstraeger', '2019', 'VAEB-EB', '2020', 'BVAEB-EB', '1:1', '2020-01-01', 'LIESMICH Pensionen, Zeile 20'),
('versicherungstraeger', '2019', 'VAEB-BB', '2020', 'BVAEB-BB', '1:1', '2020-01-01', 'LIESMICH Pensionen, Zeile 20')
ON CONFLICT DO NOTHING;

-- Quellzuordnung: wie ein Träger einen Wert schreibt und auf welchen Code das führt. Ein Code mit untergeordneten
-- Codes (PVA, VAEB, BVAEB) macht aus der Zeile eine Summenzeile. Ein Wert, der hier fehlt, bricht das Laden ab.
INSERT INTO stat.quellzuordnung (regelsatz, quelle, merkmal, version, geliefert, klassifikation, code)
SELECT 'pensionen-v1', q.quelle, 'versicherungstraeger', '-', q.geliefert, 'klass_versicherungstraeger', q.code
FROM (VALUES
  ('PVA-BIS-2021', 'Pensionsversicherungsanstalt gesamt', 'PVA'),
  ('PVA-BIS-2021', 'davon Arbeiter', 'PVA-ARB'),
  ('PVA-BIS-2021', 'davon Angestellte', 'PVA-ANG'),
  ('PVA-AB-2022',  'Pensionsversicherungsanstalt gesamt', 'PVA'),
  ('PVA-AB-2022',  'davon Arbeiter', 'PVA-ARB'),
  ('PVA-AB-2022',  'davon Angestellte', 'PVA-ANG'),
  ('SVA', 'SVA', 'SVA'),
  ('SVB', 'SVB', 'SVB'),
  ('VAEB', 'Eisenbahn', 'VAEB-EB'),
  ('VAEB', 'Bergbau', 'VAEB-BB'),
  ('VAEB', 'Gesamt', 'VAEB'),
  ('BVAEB', 'Eisenbahn', 'BVAEB-EB'),
  ('BVAEB', 'Bergbau', 'BVAEB-BB'),
  ('BVAEB', 'Gesamt', 'BVAEB'),
  ('VAN', 'Versicherungsanstalt des österreichischen Notariates', 'VAN'),
  ('SVS-BIS-2022', 'GW', 'SVS-GW'),
  ('SVS-BIS-2022', 'LW', 'SVS-LW'),
  ('SVS-AB-2023', 'Gewerbliche Wirtschaft', 'SVS-GW'),
  ('SVS-AB-2023', 'Landwirtschaft', 'SVS-LW')
) AS q(quelle, geliefert, code)
ON CONFLICT DO NOTHING;

-- Pensionsarten im Klartext: bei allen Quellen außer SVA und SVB gleich geschrieben.
INSERT INTO stat.quellzuordnung (regelsatz, quelle, merkmal, version, geliefert, klassifikation, code)
SELECT 'pensionen-v1', q.quelle, 'pensionsart', '-', a.geliefert, 'klass_pensionsart', a.code
FROM (VALUES ('PVA-BIS-2021'), ('PVA-AB-2022'), ('VAEB'), ('BVAEB'), ('VAN'), ('SVS-BIS-2022'), ('SVS-AB-2023')) AS q(quelle)
CROSS JOIN (VALUES
  ('geminderte Arbeitsfähigkeit/Erwerbsunfähigkeit', 'GEM'),
  ('Alter', 'ALTER'),
  ('Witwen/Witwer', 'WITWE'),
  ('Waisen', 'WAISE')
) AS a(geliefert, code)
ON CONFLICT DO NOTHING;

INSERT INTO stat.quellzuordnung (regelsatz, quelle, merkmal, version, geliefert, klassifikation, code)
SELECT 'pensionen-v1', q.quelle, 'pensionsart', '-', a.geliefert, 'klass_pensionsart', a.code
FROM (VALUES ('PVA-BIS-2021'), ('PVA-AB-2022'), ('VAEB'), ('BVAEB'), ('SVS-BIS-2022'), ('SVS-AB-2023')) AS q(quelle)
CROSS JOIN (VALUES
  ('lange Versicherungsdauer', 'LVD'),
  ('Korridorpension', 'KORRIDOR'),
  ('Langzeitversicherte', 'LZV'),
  ('Schwerarbeit § 607/14 ASVG', 'SCHWER_ASVG'),
  ('Schwerarbeit § 4 Abs. 3 APG', 'SCHWER_APG')
) AS a(geliefert, code)
ON CONFLICT DO NOTHING;

-- Kürzel der Legende von SVA und SVB.
INSERT INTO stat.quellzuordnung (regelsatz, quelle, merkmal, version, geliefert, klassifikation, code)
SELECT 'pensionen-v1', q.quelle, 'pensionsart', '-', a.geliefert, 'klass_pensionsart', a.code
FROM (VALUES ('SVA'), ('SVB')) AS q(quelle)
CROSS JOIN (VALUES
  ('GEM', 'GEM'), ('ALT', 'ALTER'), ('WIT', 'WITWE'), ('WAI', 'WAISE'),
  ('LVD', 'LVD'), ('KOR', 'KORRIDOR'), ('LZV', 'LZV'), ('SA1', 'SCHWER_ASVG'), ('SA2', 'SCHWER_APG')
) AS a(geliefert, code)
ON CONFLICT DO NOTHING;

-- Spalte `Tabelle` der SVS und Summenzeile der VAN führen auf die Tabelle selbst.
INSERT INTO stat.quellzuordnung (regelsatz, quelle, merkmal, version, geliefert, klassifikation, code)
SELECT 'pensionen-v1', q.quelle, 'pensionsart', '-', q.geliefert, 'klass_pensionsart', q.code
FROM (VALUES
  ('SVS-BIS-2022', 'Pensionsstand', 'T12'),
  ('SVS-BIS-2022', 'Vorzeitige Alterspensionen', 'T13'),
  ('SVS-AB-2023', 'Pensionsstand', 'T12'),
  ('SVS-AB-2023', 'Vorzeitige Alterspensionen', 'T13'),
  ('VAN', 'Pensionen insgesamt', 'T12')
) AS q(quelle, geliefert, code)
ON CONFLICT DO NOTHING;

-- Geschlecht: gemeinsame klass_geschlecht, je Quelle eigene Schreibweise. Witwer zählen als Männer, Witwen als Frauen.
INSERT INTO stat.quellzuordnung (regelsatz, quelle, merkmal, version, geliefert, klassifikation, code)
SELECT 'pensionen-v1', q.quelle, 'geschlecht', '-', q.geliefert, 'klass_geschlecht', q.code
FROM (VALUES
  ('PVA-BIS-2021', 'Männer', 'M'), ('PVA-BIS-2021', 'Witwer', 'M'),
  ('PVA-BIS-2021', 'Frauen', 'W'), ('PVA-BIS-2021', 'Witwen', 'W'),
  ('PVA-AB-2022', 'Männer', 'M'), ('PVA-AB-2022', 'Witwer', 'M'),
  ('PVA-AB-2022', 'Frauen', 'W'), ('PVA-AB-2022', 'Witwen', 'W'),
  ('SVA', 'M', 'M'), ('SVA', 'F', 'W'),
  ('SVB', 'm', 'M'), ('SVB', 'w', 'W'),
  ('VAEB', 'm', 'M'), ('VAEB', 'w', 'W'),
  ('BVAEB', 'm', 'M'), ('BVAEB', 'w', 'W'),
  ('VAN', 'männlich', 'M'), ('VAN', 'weiblich', 'W'),
  ('SVS-BIS-2022', 'M', 'M'), ('SVS-BIS-2022', 'W', 'W'),
  ('SVS-AB-2023', 'm', 'M'), ('SVS-AB-2023', 'w', 'W')
) AS q(quelle, geliefert, code)
ON CONFLICT DO NOTHING;

-- Regelsatz pensionen-v1: je Format eine Einleseregel mit Fingerabdruck, dazu die Prüfregeln. Ohne Freigabe, bis eine
-- Person sie mit Vor- und Nachnamen freigibt (`uc3 pensionen freigeben --name`). Die Kopfzeilen stammen aus den Dateien,
-- das Jahr ist als JJJJ maskiert.
INSERT INTO meta.regel (regelsatz, name, typ, art, reihenfolge, parameter, beschreibung, begruendung, grundlage,
                        gueltig_ab_lieferung, gueltig_bis_lieferung) VALUES

('pensionen-v1', 'P01_format_pva_bis_2021', 'einlese', 'pension_format', 10,
 '{"quelle": "PVA-BIS-2021", "parser": "kreuztabelle", "jahre": [2018, 2021], "blaetter": ["Tabelle 12", "Tabelle 13"], "kopf": [{"blatt": "Tabelle 12", "zeile": 1, "zellen": ["Pensionsversicherungsanstalt – Stand der Pensionen"]}, {"blatt": "Tabelle 12", "zeile": 2, "zellen": ["Jahresdurchschnitt JJJJ"]}, {"blatt": "Tabelle 12", "zeile": 4, "zellen": ["Bereich", "Alle", "geminderte Arbeitsfähigkeit/Erwerbsunfähigkeit", null, "Alter", null, "Witwen/Witwer", null, "Waisen"]}, {"blatt": "Tabelle 12", "zeile": 5, "zellen": [null, null, "Männer", "Frauen", "Männer", "Frauen", "Witwer", "Witwen", "Männer", "Frauen"]}, {"blatt": "Tabelle 13", "zeile": 1, "zellen": ["Pensionsversicherungsanstalt – Vorzeitige Alterspensionen"]}, {"blatt": "Tabelle 13", "zeile": 2, "zellen": ["Jahresdurchschnitt JJJJ"]}, {"blatt": "Tabelle 13", "zeile": 4, "zellen": ["Bereich", "Alle", "lange Versicherungsdauer", null, "Korridorpension", null, "Langzeitversicherte", null, "Schwerarbeit § 607/14 ASVG", null, "Schwerarbeit § 4 Abs. 3 APG"]}, {"blatt": "Tabelle 13", "zeile": 5, "zellen": [null, null, "Männer", "Frauen", "Männer", "Frauen", "Männer", "Frauen", "Männer", "Frauen", "Männer", "Frauen"]}], "tabellen": {"T12": {"blatt": "Tabelle 12", "kopfzeile": 4, "geschlechtzeile": 5, "summenspalte": "Alle"}, "T13": {"blatt": "Tabelle 13", "kopfzeile": 4, "geschlechtzeile": 5, "summenspalte": "Alle"}}, "jahr_zelle": {"blatt": "Tabelle 12", "zelle": "A2"}}',
 'PVA 2018 bis 2021: Kreuztabelle mit zweizeiligem Kopf, Männer vor Frauen.',
 'Die Formate unterscheiden sich je Träger und können sich von Jahr zu Jahr ändern. Der Fingerabdruck aus Blättern und Kopfzeilen erkennt das Format; alles andere bricht ab.',
 'LIESMICH Pensionen, Zeile 7 bis 8; Fingerabdruck der 28 Dateien', '2018-01', '2021-12'),

('pensionen-v1', 'P02_format_pva_ab_2022', 'einlese', 'pension_format', 20,
 '{"quelle": "PVA-AB-2022", "parser": "flach", "jahre": [2022, 2025], "blaetter": ["Info", "Pensionsstand", "Vorzeitige Alterspensionen"], "kopf": [{"blatt": "Info", "zeile": 1, "zellen": ["Pensionsversicherungsanstalt – Datenmeldung an den Dachverband"]}, {"blatt": "Info", "zeile": 2, "zellen": ["Berichtsjahr JJJJ, Jahresdurchschnitt"]}, {"blatt": "Info", "zeile": 3, "zellen": ["Blatt Pensionsstand: Stand der Pensionen nach Pensionsart und Geschlecht"]}, {"blatt": "Info", "zeile": 4, "zellen": ["Blatt Vorzeitige Alterspensionen: vorzeitige Alterspensionen nach Art und Geschlecht"]}, {"blatt": "Info", "zeile": 5, "zellen": ["Hinweis: Frauen stehen ab dem Berichtsjahr JJJJ vor den Männern."], "jahr_frei": true}, {"blatt": "Pensionsstand", "zeile": 1, "zellen": ["Bereich", "insgesamt", "geminderte Arbeitsfähigkeit/Erwerbsunfähigkeit – Frauen", "geminderte Arbeitsfähigkeit/Erwerbsunfähigkeit – Männer", "Alter – Frauen", "Alter – Männer", "Witwen/Witwer – Witwen", "Witwen/Witwer – Witwer", "Waisen – Frauen", "Waisen – Männer"]}, {"blatt": "Vorzeitige Alterspensionen", "zeile": 1, "zellen": ["Bereich", "insgesamt", "lange Versicherungsdauer – Frauen", "lange Versicherungsdauer – Männer", "Korridorpension – Frauen", "Korridorpension – Männer", "Langzeitversicherte – Frauen", "Langzeitversicherte – Männer", "Schwerarbeit § 607/14 ASVG – Frauen", "Schwerarbeit § 607/14 ASVG – Männer", "Schwerarbeit § 4 Abs. 3 APG – Frauen", "Schwerarbeit § 4 Abs. 3 APG – Männer"]}], "tabellen": {"T12": {"blatt": "Pensionsstand", "kopfzeile": 1, "summenspalte": "insgesamt", "trenner": " – "}, "T13": {"blatt": "Vorzeitige Alterspensionen", "kopfzeile": 1, "summenspalte": "insgesamt", "trenner": " – "}}, "jahr_zelle": {"blatt": "Info", "zelle": "A2"}}',
 'PVA ab 2022: neue Blätter, flacher Kopf in Zeile 1, Frauen vor Männern.',
 'Die Formate unterscheiden sich je Träger und können sich von Jahr zu Jahr ändern. Der Fingerabdruck aus Blättern und Kopfzeilen erkennt das Format; alles andere bricht ab.',
 'LIESMICH Pensionen, Zeile 7 bis 8; Fingerabdruck der 28 Dateien', '2022-01', '2025-12'),

('pensionen-v1', 'P03_format_sva', 'einlese', 'pension_format', 30,
 '{"quelle": "SVA", "parser": "kuerzel", "jahre": [2018, 2019], "blaetter": ["Pensionsstand", "vorzeitige AP", "Legende"], "kopf": [{"blatt": "Pensionsstand", "zeile": 1, "zellen": ["JAHR", "TRAEGER", "GES", "GEM_M", "GEM_F", "ALT_M", "ALT_F", "WIT_M", "WIT_F", "WAI_M", "WAI_F"]}, {"blatt": "vorzeitige AP", "zeile": 1, "zellen": ["JAHR", "TRAEGER", "GES", "LVD_M", "LVD_F", "KOR_M", "KOR_F", "LZV_M", "LZV_F", "SA1_M", "SA1_F", "SA2_M", "SA2_F"]}, {"blatt": "Legende", "zeile": 1, "zellen": ["GES", "alle Pensionen"]}, {"blatt": "Legende", "zeile": 2, "zellen": ["GEM", "geminderte Arbeitsfähigkeit/Erwerbsunfähigkeit"]}, {"blatt": "Legende", "zeile": 3, "zellen": ["ALT", "Alter"]}, {"blatt": "Legende", "zeile": 4, "zellen": ["WIT", "Witwen/Witwer"]}, {"blatt": "Legende", "zeile": 5, "zellen": ["WAI", "Waisen"]}, {"blatt": "Legende", "zeile": 6, "zellen": ["LVD", "lange Versicherungsdauer"]}, {"blatt": "Legende", "zeile": 7, "zellen": ["KOR", "Korridorpension"]}, {"blatt": "Legende", "zeile": 8, "zellen": ["LZV", "Langzeitversicherte"]}, {"blatt": "Legende", "zeile": 9, "zellen": ["SA1", "Schwerarbeit § 607/14 ASVG"]}, {"blatt": "Legende", "zeile": 10, "zellen": ["SA2", "Schwerarbeit § 4 Abs. 3 APG"]}, {"blatt": "Legende", "zeile": 11, "zellen": ["M", "männlich (bei WIT: Witwer)"]}, {"blatt": "Legende", "zeile": 12, "zellen": ["F", "weiblich (bei WIT: Witwen)"]}], "tabellen": {"T12": {"blatt": "Pensionsstand", "kopfzeile": 1, "summenspalte": "GES"}, "T13": {"blatt": "vorzeitige AP", "kopfzeile": 1, "summenspalte": "GES"}}}',
 'SVA 2018 und 2019: eine Datenzeile, Kürzel mit Suffix _M und _F.',
 'Die Formate unterscheiden sich je Träger und können sich von Jahr zu Jahr ändern. Der Fingerabdruck aus Blättern und Kopfzeilen erkennt das Format; alles andere bricht ab.',
 'LIESMICH Pensionen, Zeile 7 bis 8; Fingerabdruck der 28 Dateien', '2018-01', '2019-12'),

('pensionen-v1', 'P04_format_svb', 'einlese', 'pension_format', 40,
 '{"quelle": "SVB", "parser": "kuerzel", "jahre": [2018, 2019], "blaetter": ["Stand", "vorzeitig", "Legende"], "kopf": [{"blatt": "Stand", "zeile": 1, "zellen": ["JAHR", "TRAEGER", "GES", "GEM_m", "GEM_w", "ALT_m", "ALT_w", "WIT_m", "WIT_w", "WAI_m", "WAI_w"]}, {"blatt": "vorzeitig", "zeile": 1, "zellen": ["JAHR", "TRAEGER", "GES", "LVD_m", "LVD_w", "KOR_m", "KOR_w", "LZV_m", "LZV_w", "SA1_m", "SA1_w", "SA2_m", "SA2_w"]}, {"blatt": "Legende", "zeile": 1, "zellen": ["GES", "alle Pensionen"]}, {"blatt": "Legende", "zeile": 2, "zellen": ["GEM", "geminderte Arbeitsfähigkeit/Erwerbsunfähigkeit"]}, {"blatt": "Legende", "zeile": 3, "zellen": ["ALT", "Alter"]}, {"blatt": "Legende", "zeile": 4, "zellen": ["WIT", "Witwen/Witwer"]}, {"blatt": "Legende", "zeile": 5, "zellen": ["WAI", "Waisen"]}, {"blatt": "Legende", "zeile": 6, "zellen": ["LVD", "lange Versicherungsdauer"]}, {"blatt": "Legende", "zeile": 7, "zellen": ["KOR", "Korridorpension"]}, {"blatt": "Legende", "zeile": 8, "zellen": ["LZV", "Langzeitversicherte"]}, {"blatt": "Legende", "zeile": 9, "zellen": ["SA1", "Schwerarbeit § 607/14 ASVG"]}, {"blatt": "Legende", "zeile": 10, "zellen": ["SA2", "Schwerarbeit § 4 Abs. 3 APG"]}, {"blatt": "Legende", "zeile": 11, "zellen": ["m", "männlich (bei WIT: Witwer)"]}, {"blatt": "Legende", "zeile": 12, "zellen": ["w", "weiblich (bei WIT: Witwen)"]}], "tabellen": {"T12": {"blatt": "Stand", "kopfzeile": 1, "summenspalte": "GES"}, "T13": {"blatt": "vorzeitig", "kopfzeile": 1, "summenspalte": "GES"}}}',
 'SVB 2018 und 2019: wie SVA, aber Suffix _m und _w.',
 'Die Formate unterscheiden sich je Träger und können sich von Jahr zu Jahr ändern. Der Fingerabdruck aus Blättern und Kopfzeilen erkennt das Format; alles andere bricht ab.',
 'LIESMICH Pensionen, Zeile 7 bis 8; Fingerabdruck der 28 Dateien', '2018-01', '2019-12'),

('pensionen-v1', 'P05_format_vaeb', 'einlese', 'pension_format', 50,
 '{"quelle": "VAEB", "parser": "bloecke", "jahre": [2018, 2019], "blaetter": ["Pensionen"], "kopf": [{"blatt": "Pensionen", "zeile": 1, "zellen": ["Versicherungsanstalt für Eisenbahnen und Bergbau – Meldung Pensionen JJJJ (Jahresdurchschnitt)"]}, {"blatt": "Pensionen", "zeile": 3, "zellen": ["A. Pensionsstand"]}, {"blatt": "Pensionen", "zeile": 4, "zellen": ["Sparte", "Summe", "geminderte Arbeitsfähigkeit/Erwerbsunfähigkeit m", "geminderte Arbeitsfähigkeit/Erwerbsunfähigkeit w", "Alter m", "Alter w", "Witwen/Witwer m", "Witwen/Witwer w", "Waisen m", "Waisen w"]}, {"blatt": "Pensionen", "zeile": 9, "zellen": ["B. Vorzeitige Alterspensionen"]}, {"blatt": "Pensionen", "zeile": 10, "zellen": ["Sparte", "Summe", "lange Versicherungsdauer m", "lange Versicherungsdauer w", "Korridorpension m", "Korridorpension w", "Langzeitversicherte m", "Langzeitversicherte w", "Schwerarbeit § 607/14 ASVG m", "Schwerarbeit § 607/14 ASVG w", "Schwerarbeit § 4 Abs. 3 APG m", "Schwerarbeit § 4 Abs. 3 APG w"]}, {"blatt": "Pensionen", "zeile": 15, "zellen": ["m = männlich, w = weiblich; bei Witwen/Witwer: m = Witwer, w = Witwen"]}], "tabellen": {"T12": {"blatt": "Pensionen", "titel": "A. Pensionsstand", "summenspalte": "Summe"}, "T13": {"blatt": "Pensionen", "titel": "B. Vorzeitige Alterspensionen", "summenspalte": "Summe"}}, "jahr_zelle": {"blatt": "Pensionen", "zelle": "A1"}}',
 'VAEB 2018 und 2019: zwei Blöcke in einem Blatt, Zahlen als Text mit Tausenderpunkt.',
 'Die Formate unterscheiden sich je Träger und können sich von Jahr zu Jahr ändern. Der Fingerabdruck aus Blättern und Kopfzeilen erkennt das Format; alles andere bricht ab.',
 'LIESMICH Pensionen, Zeile 7 bis 8; Fingerabdruck der 28 Dateien', '2018-01', '2019-12'),

('pensionen-v1', 'P06_format_bvaeb', 'einlese', 'pension_format', 60,
 '{"quelle": "BVAEB", "parser": "bloecke", "jahre": [2020, 2025], "blaetter": ["Pensionen"], "kopf": [{"blatt": "Pensionen", "zeile": 1, "zellen": ["Versicherungsanstalt öffentlich Bediensteter, Eisenbahnen und Bergbau – Meldung Pensionen JJJJ (Jahresdurchschnitt)"]}, {"blatt": "Pensionen", "zeile": 3, "zellen": ["A. Pensionsstand"]}, {"blatt": "Pensionen", "zeile": 4, "zellen": ["Sparte", "Summe", "geminderte Arbeitsfähigkeit/Erwerbsunfähigkeit m", "geminderte Arbeitsfähigkeit/Erwerbsunfähigkeit w", "Alter m", "Alter w", "Witwen/Witwer m", "Witwen/Witwer w", "Waisen m", "Waisen w"]}, {"blatt": "Pensionen", "zeile": 9, "zellen": ["B. Vorzeitige Alterspensionen"]}, {"blatt": "Pensionen", "zeile": 10, "zellen": ["Sparte", "Summe", "lange Versicherungsdauer m", "lange Versicherungsdauer w", "Korridorpension m", "Korridorpension w", "Langzeitversicherte m", "Langzeitversicherte w", "Schwerarbeit § 607/14 ASVG m", "Schwerarbeit § 607/14 ASVG w", "Schwerarbeit § 4 Abs. 3 APG m", "Schwerarbeit § 4 Abs. 3 APG w"]}, {"blatt": "Pensionen", "zeile": 15, "zellen": ["m = männlich, w = weiblich; bei Witwen/Witwer: m = Witwer, w = Witwen"]}], "tabellen": {"T12": {"blatt": "Pensionen", "titel": "A. Pensionsstand", "summenspalte": "Summe"}, "T13": {"blatt": "Pensionen", "titel": "B. Vorzeitige Alterspensionen", "summenspalte": "Summe"}}, "jahr_zelle": {"blatt": "Pensionen", "zelle": "A1"}}',
 'BVAEB 2020 bis 2025: Aufbau der VAEB, nur der Titel ist neu.',
 'Die Formate unterscheiden sich je Träger und können sich von Jahr zu Jahr ändern. Der Fingerabdruck aus Blättern und Kopfzeilen erkennt das Format; alles andere bricht ab.',
 'LIESMICH Pensionen, Zeile 7 bis 8; Fingerabdruck der 28 Dateien', '2020-01', '2025-12'),

('pensionen-v1', 'P07_format_van', 'einlese', 'pension_format', 70,
 '{"quelle": "VAN", "parser": "lang_anzahl", "jahre": [2018, 2019], "blaetter": ["Pensionen JJJJ"], "kopf": [{"blatt": "Pensionen JJJJ", "zeile": 1, "zellen": ["Versicherungsanstalt des österreichischen Notariates"]}, {"blatt": "Pensionen JJJJ", "zeile": 2, "zellen": ["Pensionsstand Jahresdurchschnitt JJJJ"]}, {"blatt": "Pensionen JJJJ", "zeile": 4, "zellen": ["Pensionsart", "Geschlecht", "Anzahl"]}, {"blatt": "Pensionen JJJJ", "zeile": 15, "zellen": ["Vorzeitige Alterspensionen werden nicht gesondert gemeldet."]}], "tabellen": {"T12": {"blatt": "Pensionen JJJJ", "kopfzeile": 4}}, "jahr_zelle": {"blatt": "Pensionen JJJJ", "zelle": "A2"}, "traeger_zelle": "A1"}',
 'VAN 2018 und 2019: lange Liste, Jahr im Blattnamen, nur Pensionsstand.',
 'Die Formate unterscheiden sich je Träger und können sich von Jahr zu Jahr ändern. Der Fingerabdruck aus Blättern und Kopfzeilen erkennt das Format; alles andere bricht ab.',
 'LIESMICH Pensionen, Zeile 7 bis 8; Fingerabdruck der 28 Dateien', '2018-01', '2019-12'),

('pensionen-v1', 'P08_format_svs_bis_2022', 'einlese', 'pension_format', 80,
 '{"quelle": "SVS-BIS-2022", "parser": "lang", "jahre": [2020, 2022], "blaetter": ["Daten"], "kopf": [{"blatt": "Daten", "zeile": 1, "zellen": ["Jahr", "Sparte", "Tabelle", "Pensionsart", "Geschlecht", "Anzahl"]}], "tabellen": {"T12": {"blatt": "Daten", "kopfzeile": 1}, "T13": {"blatt": "Daten", "kopfzeile": 1}}}',
 'SVS 2020 bis 2022: lange Liste, Sparte GW und LW, Geschlecht M und W, keine Summenzeilen.',
 'Die Formate unterscheiden sich je Träger und können sich von Jahr zu Jahr ändern. Der Fingerabdruck aus Blättern und Kopfzeilen erkennt das Format; alles andere bricht ab.',
 'LIESMICH Pensionen, Zeile 7 bis 8; Fingerabdruck der 28 Dateien', '2020-01', '2022-12'),

('pensionen-v1', 'P09_format_svs_ab_2023', 'einlese', 'pension_format', 90,
 '{"quelle": "SVS-AB-2023", "parser": "lang", "jahre": [2023, 2025], "blaetter": ["Daten"], "kopf": [{"blatt": "Daten", "zeile": 1, "zellen": ["Jahr", "Sparte", "Tabelle", "Pensionsart", "Geschlecht", "Anzahl", "Zeitraum"]}], "tabellen": {"T12": {"blatt": "Daten", "kopfzeile": 1}, "T13": {"blatt": "Daten", "kopfzeile": 1}}, "zeitraum_spalte": "Zeitraum"}',
 'SVS ab 2023: Sparte im Klartext, Geschlecht m und w, neue Spalte Zeitraum.',
 'Die Formate unterscheiden sich je Träger und können sich von Jahr zu Jahr ändern. Der Fingerabdruck aus Blättern und Kopfzeilen erkennt das Format; alles andere bricht ab.',
 'LIESMICH Pensionen, Zeile 7 bis 8; Fingerabdruck der 28 Dateien', '2023-01', '2025-12'),

('pensionen-v1', 'P20_summen_der_dateien', 'pruefung', 'pension_summen', 200,
 '{}',
 'Jede Summenzeile und Summenspalte einer Datei wird aus den Einzelwerten derselben Datei nachgerechnet.',
 'Die Träger melden Summen mit; sie sind der einzige Prüfwert innerhalb einer Datei. SVS meldet keine Summen.',
 'Aufgabenstellung Anhang B; LIESMICH Pensionen, Zeile 9 bis 10', '2018-01', NULL),

('pensionen-v1', 'P21_luecken', 'pruefung', 'pension_luecke', 210,
 '{"luecken": [
   {"titel": "VAN meldet keine vorzeitigen Alterspensionen", "beleg": "Datei VAN_Pensionsstand_JJJJ.xlsx, Zeile 15, und LIESMICH Zeile 14", "annahme": "Für VAN 2018 und 2019 gibt es keine Zahl in Tabelle 13. Es wird keine 0 und keine Schätzung eingesetzt. Tabelle 13 der Selbständigen enthält die VAN deshalb nicht."},
   {"titel": "BVA liefert keine Pensionsmeldung", "beleg": "LIESMICH Zeile 15 und 25; BVAEB-Dateien nennen nur Eisenbahn und Bergbau", "annahme": "Die Beamten der früheren BVA fehlen in allen Jahren. BVAEB enthält hier nur Eisenbahn und Bergbau und ist nicht der ganze Träger."},
   {"titel": "SVS meldet keine Summenzeilen", "beleg": "Dateien svs_pensionen_JJJJ.xlsx haben nur Einzelzeilen", "annahme": "Für die SVS 2020 bis 2025 gibt es keinen Prüfwert aus der Datei. Geprüft wird nur, dass jede Kombination genau einmal vorkommt."}
 ]}',
 'Lücken in den Lieferungen, die der Prüfbericht mit Annahme nennt.',
 'Nichts wird still ergänzt: Was nicht gemeldet ist, bleibt leer und steht im Bericht.',
 'LIESMICH Pensionen, Zeile 13 bis 15', '2018-01', NULL),

('pensionen-v1', 'P22_uebergang_2020', 'pruefung', 'pension_uebergang', 220,
 '{"jahr_alt": 2019, "jahr_neu": 2020, "ziele": ["SVS-GW", "SVS-LW", "BVAEB-EB", "BVAEB-BB"],
   "annahme": "Die Zeitreihe wird nicht geglättet. 2019 und 2020 stehen unverändert nebeneinander. SVA und VAN werden der Sparte Gewerbliche Wirtschaft gegenübergestellt, SVB der Landwirtschaft. Dass die VAN zur Gewerblichen Wirtschaft kommt, ist eine Annahme: Die Quelle nennt nur die SVS, ohne Sparte."}',
 'Stellt 2019 und 2020 je Nachfolger gegenüber und nennt den Unterschied.',
 'Zum 1.1.2020 wurden Träger zusammengelegt; die Zahlen müssen über den Bruch hinweg lesbar bleiben.',
 'LIESMICH Pensionen, Zeile 25 bis 26; Aufgabenstellung Schritt 6', '2018-01', NULL),

('pensionen-v1', 'P23_spruenge', 'pruefung', 'pension_sprung', 230,
 '{"schwelle_prozent": 15, "mindestwert": 1000}',
 'Meldet Werte je Bereich, Art und Geschlecht, die sich von einem Jahr aufs nächste stark ändern.',
 'Ein Sprung kann ein Lesefehler oder ein echter Wechsel sein. Er wird gemeldet und nicht geändert.',
 'Projektregel: Auffälliges benennen, nichts still glätten', '2018-01', NULL),

('pensionen-v1', 'P24_geschlecht', 'pruefung', 'pension_geschlecht', 240,
 '{"schwelle_punkte": 5, "mindestwert": 1000}',
 'Meldet, wenn sich der Männeranteil einer Pensionsart bei einem Bereich von einem Jahr aufs nächste stark ändert.',
 'Die PVA stellt ab 2022 Frauen vor Männer. Ein Tausch der Spalten ließe alle Summen stimmen und fiele nur hier auf.',
 'Info-Blatt der PVA-Dateien ab 2022, Zelle A5', '2018-01', NULL),

('pensionen-v1', 'P25_vorzeitig_in_alter', 'pruefung', 'pension_vorzeitig', 250,
 '{}',
 'Vorzeitige Alterspensionen (Tabelle 13) dürfen je Bereich und Geschlecht nicht mehr sein als Alterspensionen (Tabelle 12).',
 'Tabelle 13 ist ein Teil der Alterspensionen.',
 'Aufgabenstellung Anhang C; LIESMICH Pensionen, Zeile 3 bis 5', '2018-01', NULL),

('pensionen-v1', 'P30_frage_begriffe', 'zuordnung', 'pension_frage', 300,
 '{"arten": {
     "T12": ["pensionsstand", "stand"],
     "T13": ["vorzeitig", "vorzeitige", "vorzeitigen", "frühpension", "frühpensionen"],
     "GEM": ["invaliditätspension", "invaliditätspensionen", "erwerbsunfähigkeit", "arbeitsfähigkeit", "invalidität", "geminderte", "geminderter"],
     "ALTER": ["alterspension", "alterspensionen", "alter"],
     "WITWE": ["witwenpension", "witwenpensionen", "witwerpension", "witwerpensionen", "witwen", "witwer", "witwen/witwer"],
     "WAISE": ["waisenpension", "waisenpensionen", "waisen"],
     "LVD": ["versicherungsdauer"],
     "KORRIDOR": ["korridorpension", "korridorpensionen", "korridor"],
     "LZV": ["langzeitversicherte", "langzeitversicherten"],
     "SCHWER_ASVG": ["asvg"],
     "SCHWER_APG": ["apg"]},
   "traeger": {
     "PV-UNS": ["unselbständige", "unselbständigen"],
     "PV-SEL": ["selbständige", "selbständigen"],
     "PVA": ["pva", "pensionsversicherungsanstalt"],
     "PVA-ARB": ["arbeiter"],
     "PVA-ANG": ["angestellte", "angestellten"],
     "VAEB": ["vaeb"],
     "BVAEB": ["bvaeb"],
     "SVA": ["sva"],
     "SVB": ["svb"],
     "VAN": ["van", "notariat", "notare"],
     "SVS": ["svs"],
     "SVS-GW": ["gewerbliche", "gewerblichen", "gewerbe"],
     "SVS-LW": ["landwirtschaft", "bauern"]},
   "geschlecht": {
     "M": ["männer", "männlich", "männliche", "witwer", "witwerpension", "witwerpensionen"],
     "W": ["frauen", "weiblich", "weibliche", "witwen", "witwenpension", "witwenpensionen"]},
   "mehrdeutig": {
     "schwerarbeit": {"codes": ["SCHWER_ASVG", "SCHWER_APG"], "satz": "Schwerarbeit gibt es nach ASVG und nach APG. Welche meinen Sie?"},
     "lange": {"codes": ["LVD"], "satz": "Meinen Sie die Pensionsart lange Versicherungsdauer? Dann nennen Sie sie bitte ganz. Wie lange jemand eine Pension bezieht, steht nicht in den Meldungen."}},
   "abgelehnt": {
     "pensionist": "Die Meldungen zählen Pensionen, nicht Personen. Eine Person kann mehrere Pensionen beziehen. Fragen Sie bitte nach der Zahl der Pensionen.",
     "pensionisten": "Die Meldungen zählen Pensionen, nicht Personen. Eine Person kann mehrere Pensionen beziehen. Fragen Sie bitte nach der Zahl der Pensionen.",
     "pensionistinnen": "Die Meldungen zählen Pensionen, nicht Personen. Eine Person kann mehrere Pensionen beziehen. Fragen Sie bitte nach der Zahl der Pensionen.",
     "viel": "Die Meldungen nennen die Zahl der Pensionen, keine Beträge. Fragen Sie bitte nach der Anzahl.",
     "wieviel": "Die Meldungen nennen die Zahl der Pensionen, keine Beträge. Fragen Sie bitte nach der Anzahl.",
     "bekommen": "Die Meldungen nennen die Zahl der Pensionen, keine Beträge. Fragen Sie bitte nach der Anzahl.",
     "hinterbliebene": "Hinterbliebene sind Witwen, Witwer und Waisen, das sind zwei Pensionsarten. Fragen Sie bitte nach einer davon."},
   "hinweis_vorzeitig": {
     "knoten": ["INSG", "PV-SEL"], "bis_jahr": 2019,
     "satz": "Bei den vorzeitigen Alterspensionen fehlt 2018 und 2019 das Notariat (VAN), es meldet diese Art nicht."},
   "hinweis_traeger": {
     "INSG": "Nicht enthalten sind die öffentlich Bediensteten, die frühere BVA meldet keine Pensionen.",
     "PV-UNS": "Nicht enthalten sind die öffentlich Bediensteten, die frühere BVA meldet keine Pensionen.",
     "PVA-ARB": "Arbeiter ist hier ein Versicherungsbereich der PVA, die frühere PVA der Arbeiter. Das ist nicht die Qualifikation Arbeiter der Beschäftigtenstatistik.",
     "PVA-ANG": "Angestellte ist hier ein Versicherungsbereich der PVA, die frühere PVA der Angestellten. Das ist nicht die Qualifikation Angestellte der Beschäftigtenstatistik.",
     "BVAEB": "Die BVAEB meldet hier nur Eisenbahn und Bergbau, die Beamten der früheren BVA fehlen."},
   "fuellwoerter": ["wie", "viele", "gab", "gibt", "es", "im", "in", "den", "dem", "der", "die", "das", "des", "und", "nach", "je", "pro", "von", "bis", "seit", "für", "an", "bei", "mit", "zu", "zur", "waren", "war", "sind", "ist", "hat", "hatte", "hatten", "bezogen", "beziehen", "jahr", "jahre", "jahren", "jahres", "jahresdurchschnitt", "durchschnitt", "durchschnittlich", "anzahl", "zahl", "zahlen", "summe", "insgesamt", "gesamt", "alle", "aller", "allen", "österreich", "pension", "pensionen", "entwicklung", "zeitreihe", "verlauf", "zeig", "zeige", "zeigen", "mir", "bitte", "was", "welche", "welcher", "wieviele", "ein", "eine", "einer", "aus", "wurden", "werden", "sv", "pv"]}',
 'Wörter einer Datenfrage nach Pensionen und die Codes, die sie meinen. Ein anderes Wort führt zur Rückfrage statt zu einer Zahl.',
 'Die Frage wird ohne Sprachmodell gelesen. Sprachverständnis, kein Rechenregelwerk: Die Zahl kommt immer aus der Abfrage.',
 'Aufgabenstellung Schritt 6; Projektregel: keine Zahl zu einer Frage, die nicht verstanden ist', '2018-01', NULL)

ON CONFLICT (regelsatz, name) DO UPDATE
  SET typ = EXCLUDED.typ, art = EXCLUDED.art, reihenfolge = EXCLUDED.reihenfolge, parameter = EXCLUDED.parameter,
      beschreibung = EXCLUDED.beschreibung, begruendung = EXCLUDED.begruendung, grundlage = EXCLUDED.grundlage
  WHERE meta.regel.freigegeben_von IS NULL;  -- nur Entwürfe; freigegebene Regeln ändert nur eine Freigabe
