-- Anhang B: gemeinsame Metadaten für alle Statistiken. Je Begriff genau eine klass_-Tabelle.

CREATE TABLE IF NOT EXISTS stat.beschreibung (
  statistik     text PRIMARY KEY,                            -- 'beschaeftigte'
  name          text NOT NULL,
  quelle        text NOT NULL,
  statistiktyp  text NOT NULL CHECK (statistiktyp IN ('einzeldaten', 'aggregiert')),
  dimensionen   jsonb NOT NULL,                              -- [{spalte, klassifikation, ebene}]
  anmerkungen   text
);

CREATE TABLE IF NOT EXISTS stat.variable (
  statistik     text NOT NULL REFERENCES stat.beschreibung (statistik),
  code          text NOT NULL,                               -- steht in stat_<statistik>.variable
  bezeichnung   text NOT NULL,
  beschreibung  text NOT NULL,                               -- Definition, Berechnungslogik
  einheit       text NOT NULL,
  PRIMARY KEY (statistik, code)
);

CREATE TABLE IF NOT EXISTS stat.klass_geschlecht (
  code text PRIMARY KEY, bezeichnung text NOT NULL,
  gueltig_von date NOT NULL DEFAULT '1900-01-01', gueltig_bis date
);

-- Region: Bundesländer jetzt, Bezirke und Gemeinden je Stand später (Ebene, übergeordneter Code).
CREATE TABLE IF NOT EXISTS stat.klass_region (
  version text NOT NULL, code text NOT NULL, bezeichnung text NOT NULL,
  ebene text NOT NULL CHECK (ebene IN ('staat', 'bundesland', 'bezirk', 'gemeinde')),
  uebergeordnet text, gueltig_von date NOT NULL, gueltig_bis date,
  PRIMARY KEY (version, code)
);

CREATE TABLE IF NOT EXISTS stat.klass_qualifikation (
  code text PRIMARY KEY, bezeichnung text NOT NULL,
  beschaeftigungskategorie text NOT NULL,                     -- Arbeiter | Angestellte | Beamte | Unbekannt
  freier_dienstvertrag boolean,
  gueltig_von date NOT NULL DEFAULT '1900-01-01', gueltig_bis date
);

CREATE TABLE IF NOT EXISTS stat.klass_beschaeftigungskategorie (
  code text PRIMARY KEY, bezeichnung text NOT NULL,
  gueltig_von date NOT NULL DEFAULT '1900-01-01', gueltig_bis date
);

CREATE TABLE IF NOT EXISTS stat.klass_oenace (
  version text NOT NULL,                                     -- '2003' | '2008' | '2025'
  code text NOT NULL, bezeichnung text NOT NULL,
  ebene int NOT NULL,                                        -- 1 = Abschnitt (Buchstabe), 2.. tiefere Ebenen
  uebergeordnet text,
  gueltig_von date NOT NULL, gueltig_bis date,               -- Berichtsmonate, für die die Version gilt
  PRIMARY KEY (version, code)
);

-- Alter in vollendeten Jahren; -1 = unbekannt. berichtsgruppe = Zeile in Tab13 des Beispielberichts.
CREATE TABLE IF NOT EXISTS stat.klass_alter (
  code int PRIMARY KEY, bezeichnung text NOT NULL, berichtsgruppe text NOT NULL
);

CREATE TABLE IF NOT EXISTS stat.uebergang (
  klassifikation text NOT NULL,                              -- 'oenace', 'region', …
  version_alt text NOT NULL, code_alt text NOT NULL,
  version_neu text NOT NULL, code_neu text NOT NULL,
  beziehung text NOT NULL CHECK (beziehung IN ('1:1', '1:n', 'n:1', 'm:n')),
  gueltig_ab date NOT NULL, quelle text,
  PRIMARY KEY (klassifikation, version_alt, code_alt, version_neu, code_neu)
);

-- Quellzuordnung (Anhang B): wie eine Lieferung ein Merkmal schreibt und auf welchen Code das führt.
-- geliefert '<leer>' = Feld leer, '<sonst>' = jeder andere nicht zugeordnete Wert.
-- version '-' für Merkmale ohne Versionen.
CREATE TABLE IF NOT EXISTS stat.quellzuordnung (
  quelle text NOT NULL,                                      -- 'zvd' (Lieferung der Zentralen Versicherungsdatei)
  merkmal text NOT NULL CHECK (merkmal IN ('geschlecht', 'qualifikation', 'oenace', 'bundesland')),
  version text NOT NULL DEFAULT '-',
  geliefert text NOT NULL,
  klassifikation text NOT NULL,                              -- Zieltabelle, z. B. 'klass_oenace'
  code text NOT NULL,
  regel_id int REFERENCES meta.regel (id),                   -- Regel, die diese Zuordnung begründet (NULL = Identität)
  PRIMARY KEY (quelle, merkmal, version, geliefert)
);
