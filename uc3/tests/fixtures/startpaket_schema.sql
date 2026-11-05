-- Startpaket-Tabellen des Veranstalters (Nachbau für Tests; in der echten DB vom Startpaket angelegt).
CREATE SCHEMA roh;
CREATE SCHEMA klassifikation;

CREATE TABLE roh.lieferung (
  lieferung text NOT NULL, vvh_id text, person_id text, geburtsdatum text, geschlecht text,
  beginn text, ende text, qual text, oenace text, bundesland text
);
CREATE TABLE roh.ladeprotokoll (
  lieferung text PRIMARY KEY, datei text, zeilen bigint, geladen_am timestamptz DEFAULT now()
);
CREATE TABLE klassifikation.oenace_2008 (code text PRIMARY KEY, bezeichnung text);
CREATE TABLE klassifikation.oenace_2025 (code text PRIMARY KEY, bezeichnung text);
CREATE TABLE klassifikation.bundesland (code text PRIMARY KEY, bezeichnung text);
CREATE TABLE klassifikation.geschlecht (code text PRIMARY KEY, bezeichnung text);
CREATE TABLE klassifikation.qualifikation (
  code text PRIMARY KEY, bezeichnung text, beschaeftigungskategorie text, freier_dienstvertrag text
);
