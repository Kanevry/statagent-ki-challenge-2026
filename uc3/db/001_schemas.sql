-- StatAgent UC3: Schemas. Idempotent, kein DROP (Rohdaten in roh.* bleiben unangetastet).
-- roh.*            Startpaket des Veranstalters (so wie geliefert, nur lesen)
-- klassifikation.* Startpaket des Veranstalters (Quelle für stat.klass_*)
-- bereinigt.*      typisierte Zeitabschnitte je Lieferung und Regelsatz (abgeleitet, je Lauf neu)
-- meta.*           Regeln als Daten, Läufe, Prüftreffer (UC3); meta.protokoll/meta.freigabe kommen aus shared (E0)
-- stat.*           Datenmodell nach Anhang B: stat_<statistik>, variable, beschreibung, klass_*, uebergang, quellzuordnung
CREATE SCHEMA IF NOT EXISTS bereinigt;
CREATE SCHEMA IF NOT EXISTS meta;
CREATE SCHEMA IF NOT EXISTS stat;
