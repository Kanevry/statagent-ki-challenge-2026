-- Upgrade bestehender Datenbanken: Quellzuordnung je Regelsatz (Review !13). Für frische Datenbanken legt 020 die
-- Tabelle schon so an; dann tut diese Datei nichts. Kein Datenverlust: vorhandene Zeilen gehören zu Regelsatz v1.
ALTER TABLE stat.quellzuordnung ADD COLUMN IF NOT EXISTS regelsatz text NOT NULL DEFAULT 'v1';
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_index i JOIN pg_attribute a ON a.attrelid = i.indrelid AND a.attnum = ANY (i.indkey)
    WHERE i.indrelid = 'stat.quellzuordnung'::regclass AND i.indisprimary AND a.attname = 'regelsatz'
  ) THEN
    ALTER TABLE stat.quellzuordnung DROP CONSTRAINT quellzuordnung_pkey;
    ALTER TABLE stat.quellzuordnung ADD PRIMARY KEY (regelsatz, quelle, merkmal, version, geliefert);
  END IF;
END $$;
