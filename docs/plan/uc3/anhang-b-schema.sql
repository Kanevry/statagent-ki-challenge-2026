-- Anhang B (Fachbeschreibung): Schema-Readback und Integrität der Beschäftigtenstatistik (Issue #73).
-- Jede Abfrage liefert genau eine Zeile mit `pruefung` und `fehlend`; Soll ist überall fehlend = 0.
-- Nur lesend. Ausführen: psql -f docs/plan/uc3/anhang-b-schema.sql gegen eine UC3-Datenbank nach `uc3 db init`
-- und mindestens einem Lauf; automatisch geprüft in uc3/tests/test_anhang_b.py (Fixture-Lieferungen).
-- B1 bis B11 gelten für die Beschäftigung, B12 bis B15 für die Pensionen (#77); sie halten auch vor dem ersten Laden.

-- B1 Long-Format: Pflichtspalten von stat.stat_beschaeftigte (Zeitraum, Dimensionen, Variable, Wert, Status, Stand)
SELECT 'B1 Pflichtspalten stat_beschaeftigte' AS pruefung, count(*) AS fehlend
FROM unnest(ARRAY['zeitraum_art', 'zeitraum_von', 'zeitraum_bis', 'region', 'oenace', 'oenace_version',
                  'geschlecht', 'qualifikation', 'alter', 'variable', 'wert', 'status', 'stand', 'regelsatz',
                  'regelstand', 'lauf_id']) AS soll(spalte)
WHERE NOT EXISTS (SELECT 1 FROM information_schema.columns c
                  WHERE c.table_schema = 'stat' AND c.table_name = 'stat_beschaeftigte'
                    AND c.column_name = soll.spalte);

-- B2 Beschreibung: Name, Quelle, Typ, Dimensionen und Anmerkungen gefüllt
SELECT 'B2 Pflichtfelder stat.beschreibung' AS pruefung, count(*) AS fehlend
FROM stat.beschreibung b
WHERE coalesce(b.name, '') = '' OR coalesce(b.quelle, '') = '' OR coalesce(b.statistiktyp, '') = ''
   OR jsonb_typeof(b.dimensionen) <> 'array' OR jsonb_array_length(b.dimensionen) = 0
   OR coalesce(b.anmerkungen, '') = '';

-- B3 Jede Dimension nennt Spalte, Klassifikation und Ebene
SELECT 'B3 Dimension mit Spalte, Klassifikation, Ebene' AS pruefung, count(*) AS fehlend
FROM stat.beschreibung b, jsonb_array_elements(b.dimensionen) d
WHERE coalesce(d ->> 'spalte', '') = '' OR coalesce(d ->> 'klassifikation', '') = '' OR d -> 'ebene' IS NULL;

-- B4 Die Spalte jeder Dimension gibt es in der Datentabelle, die Klassifikation als Tabelle stat.<klassifikation>
SELECT 'B4 Dimension zeigt auf Spalte und Klassifikationstabelle' AS pruefung, count(*) AS fehlend
FROM stat.beschreibung b, jsonb_array_elements(b.dimensionen) d
WHERE NOT EXISTS (SELECT 1 FROM information_schema.columns c
                  WHERE c.table_schema = 'stat' AND c.table_name = 'stat_' || b.statistik
                    AND c.column_name = d ->> 'spalte')
   OR NOT EXISTS (SELECT 1 FROM information_schema.tables t
                  WHERE t.table_schema = 'stat' AND t.table_name = d ->> 'klassifikation');

-- B5 Gemeinsame Variable: Bezeichnung, Definition/Berechnung und Einheit gefüllt
SELECT 'B5 Pflichtfelder stat.variable' AS pruefung, count(*) AS fehlend
FROM stat.variable v
WHERE coalesce(v.bezeichnung, '') = '' OR coalesce(v.beschreibung, '') = '' OR coalesce(v.einheit, '') = '';

-- B6 Anti-Join: jede Variable der Datentabelle steht in stat.variable (Statistik, Code)
SELECT 'B6 Variable der Daten ohne Eintrag in stat.variable' AS pruefung, count(*) AS fehlend
FROM (SELECT DISTINCT variable FROM stat.stat_beschaeftigte) s
WHERE NOT EXISTS (SELECT 1 FROM stat.variable v WHERE v.statistik = 'beschaeftigte' AND v.code = s.variable);

-- B7 Klassifikationen: jede klass_-Tabelle hat Gültigkeit; versionierte zusätzlich Version, Ebene und Elterncode.
-- Bewusste Ausnahme: klass_alter (Alter in vollendeten Jahren und seine Berichtsgruppe aus Tab13 ändern sich nicht
-- mit der Zeit; eine neue Altersgliederung wäre eine Zählregel im Regelsatz, keine neue Klassifikationsversion).
SELECT 'B7 klass_-Tabellen mit Gültigkeit (versioniert: Version, Ebene, Elterncode)' AS pruefung, count(*) AS fehlend
FROM information_schema.tables t
WHERE t.table_schema = 'stat' AND t.table_name LIKE 'klass\_%' AND t.table_name <> 'klass_alter'
  AND (NOT EXISTS (SELECT 1 FROM information_schema.columns c WHERE c.table_schema = 'stat'
                   AND c.table_name = t.table_name AND c.column_name = 'gueltig_von')
       OR (t.table_name IN ('klass_oenace', 'klass_region')
           AND (SELECT count(*) FROM information_schema.columns c WHERE c.table_schema = 'stat'
                AND c.table_name = t.table_name AND c.column_name IN ('version', 'ebene', 'uebergeordnet')) <> 3));

-- B8 Je Begriff genau eine Klassifikation (keine zweite Geschlechtsklassifikation, auch nicht für Pensionen)
SELECT 'B8 Begriff mit mehr als einer klass_-Tabelle' AS pruefung, count(*) AS fehlend
FROM (SELECT split_part(table_name, '_', 2) AS begriff FROM information_schema.tables
      WHERE table_schema = 'stat' AND table_name LIKE 'klass\_%'
      GROUP BY 1 HAVING count(*) > 1) mehrfach;

-- B9 Übergänge tragen Beziehungstyp und Datum
SELECT 'B9 Übergang ohne Typ oder Datum' AS pruefung, count(*) AS fehlend
FROM stat.uebergang u
WHERE u.beziehung IS NULL OR u.gueltig_ab IS NULL;

-- B10 Anti-Join Quellzuordnung: jede gelieferte Ausprägung (auch leer) hat eine Zuordnung im Regelsatz v1;
-- ÖNACE nach der Version, die im Lieferungsmonat gilt (stat.klass_oenace, Ebene 1).
WITH geliefert AS (
  SELECT DISTINCT r.lieferung, m.merkmal, nullif(btrim(m.wert), '') AS wert
  FROM roh.lieferung r
  CROSS JOIN LATERAL (VALUES ('geschlecht', r.geschlecht), ('qualifikation', r.qual),
                             ('oenace', r.oenace), ('bundesland', r.bundesland)) AS m(merkmal, wert)
), mit_version AS (
  SELECT g.*, CASE WHEN g.merkmal = 'oenace' THEN (
           SELECT min(k.version) FROM stat.klass_oenace k
           WHERE k.ebene = 1 AND k.gueltig_von <= (to_date(g.lieferung, 'YYYY-MM') + interval '1 month - 1 day')
             AND (k.gueltig_bis IS NULL OR k.gueltig_bis >= to_date(g.lieferung, 'YYYY-MM')))
         ELSE '-' END AS version
  FROM geliefert g
)
SELECT 'B10 gelieferte Ausprägung ohne Quellzuordnung' AS pruefung, count(*) AS fehlend
FROM mit_version g
WHERE NOT EXISTS (
  SELECT 1 FROM stat.quellzuordnung q
  WHERE q.regelsatz = 'v1' AND q.quelle = 'zvd' AND q.merkmal = g.merkmal AND q.version = g.version
    AND (q.geliefert = coalesce(g.wert, '<leer>') OR q.geliefert = '<sonst>'));

-- B11 Zellen der Datentabelle ohne Klassifikationszeile (Region, ÖNACE je Version, Geschlecht, Alter)
SELECT 'B11 Zellcode ohne Klassifikationszeile' AS pruefung, count(*) AS fehlend
FROM stat.stat_beschaeftigte s
WHERE NOT EXISTS (SELECT 1 FROM stat.klass_region k WHERE k.code = s.region)
   OR NOT EXISTS (SELECT 1 FROM stat.klass_oenace k WHERE k.code = s.oenace AND k.version = s.oenace_version)
   OR NOT EXISTS (SELECT 1 FROM stat.klass_geschlecht k WHERE k.code = s.geschlecht)
   OR NOT EXISTS (SELECT 1 FROM stat.klass_alter k WHERE k.code = s."alter");

-- B12 Versicherungsbereiche sind keine Qualifikation: kein Code der Trägergliederung steht in klass_qualifikation
SELECT 'B12 Trägerbereich in klass_qualifikation' AS pruefung, count(*) AS fehlend
FROM stat.klass_qualifikation q
WHERE q.code IN (SELECT code FROM stat.klass_versicherungstraeger);

-- B13 Anti-Join: jede Variable der Pensionsdaten steht in stat.variable
SELECT 'B13 Variable der Pensionen ohne Eintrag in stat.variable' AS pruefung, count(*) AS fehlend
FROM (SELECT DISTINCT variable FROM stat.stat_pensionen) s
WHERE NOT EXISTS (SELECT 1 FROM stat.variable v WHERE v.statistik = 'pensionen' AND v.code = s.variable);

-- B14 Quellzuordnung der Pensionen führt nur auf vorhandene Codes
SELECT 'B14 Quellzuordnung Pensionen ohne Klassifikationszeile' AS pruefung, count(*) AS fehlend
FROM stat.quellzuordnung q
WHERE q.regelsatz = 'pensionen-v1'
  AND NOT EXISTS (SELECT 1 FROM stat.klass_versicherungstraeger k
                  WHERE q.merkmal = 'versicherungstraeger' AND k.code = q.code)
  AND NOT EXISTS (SELECT 1 FROM stat.klass_pensionsart k WHERE q.merkmal = 'pensionsart' AND k.code = q.code)
  AND NOT EXISTS (SELECT 1 FROM stat.klass_geschlecht k WHERE q.merkmal = 'geschlecht' AND k.code = q.code);

-- B15 Pensionszellen nur auf Blättern: Summen gehören nicht in die Statistik
SELECT 'B15 Pensionszelle auf einem Summencode' AS pruefung, count(*) AS fehlend
FROM stat.stat_pensionen s
WHERE EXISTS (SELECT 1 FROM stat.klass_versicherungstraeger k WHERE k.uebergeordnet = s.versicherungstraeger)
   OR EXISTS (SELECT 1 FROM stat.klass_pensionsart k WHERE k.uebergeordnet = s.pensionsart);
