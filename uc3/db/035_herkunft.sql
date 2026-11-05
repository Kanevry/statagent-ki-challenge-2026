-- Herkunft eines bereinigten Abschnitts: geliefert (aus roh.lieferung) oder fortgeschrieben (Regel E07: bei belegtem
-- Lieferausfall einmalig aus der Vorlieferung ergänzt, getrennt ausgewiesen, Monat bleibt vorläufig).
ALTER TABLE bereinigt.abschnitt ADD COLUMN IF NOT EXISTS herkunft text NOT NULL DEFAULT 'geliefert'
  CHECK (herkunft IN ('geliefert', 'fortgeschrieben'));
ALTER TABLE meta.lauf ADD COLUMN IF NOT EXISTS fortgeschrieben bigint NOT NULL DEFAULT 0;
