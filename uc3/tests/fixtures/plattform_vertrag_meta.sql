-- Kopie des Vertrags P bis #55 gemergt ist (PRD 2026-11-05 § „Protokoll und Freigabe (Vertrag P)“).
-- Nur Test-DDL für tests/test_agenten*.py. Die echte DDL kommt aus shared/py/plattform/sql/meta.sql,
-- nie aus uc3/db/.
CREATE SCHEMA IF NOT EXISTS meta;

CREATE TABLE IF NOT EXISTS meta.protokoll (
  id            serial PRIMARY KEY,
  zeit          timestamptz NOT NULL DEFAULT now(),
  uc            text NOT NULL,
  akteur        text NOT NULL CHECK (akteur IN ('agent', 'mensch')),
  name          text NOT NULL,
  anweisung     text NOT NULL,
  wirkung       text,
  vorschlag_typ text CHECK (vorschlag_typ IN ('datei', 'regel', 'lieferung', 'antwort')),
  status        text NOT NULL DEFAULT 'offen' CHECK (status IN ('offen', 'freigegeben', 'abgelehnt')),
  modell        text,
  provider      text,
  ref           text,
  commit_hash   text
);

CREATE TABLE IF NOT EXISTS meta.freigabe (
  id            serial PRIMARY KEY,
  protokoll_id  int NOT NULL REFERENCES meta.protokoll (id),
  name          text NOT NULL,
  zeitpunkt     timestamptz NOT NULL DEFAULT now(),
  entscheidung  text NOT NULL CHECK (entscheidung IN ('ja', 'nein')),
  begruendung   text,
  objekt_typ    text CHECK (objekt_typ IN ('datei', 'regel', 'lieferung', 'antwort')),
  objekt_ref    text
);
