-- Vertrag P (PRD E0, Issue #55): gemeinsames Protokoll und Freigaben aller Use Cases.
-- Jeder UC spielt diese Datei zuerst in seine DB ein (plattform.protokoll.ddl_einspielen),
-- UC-eigene meta.*-Tabellen kommen danach. Idempotent, kein DROP: mehrfach einspielbar.
-- Rückweg (nur nach ausdrücklicher Freigabe, löscht das Protokoll):
--   DROP TABLE meta.freigabe; DROP TABLE meta.protokoll;

CREATE SCHEMA IF NOT EXISTS meta;

CREATE TABLE IF NOT EXISTS meta.protokoll (
    id            bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    zeit          timestamptz NOT NULL DEFAULT now(),
    uc            text NOT NULL CHECK (uc <> ''),
    akteur        text NOT NULL CHECK (akteur IN ('agent', 'mensch')),
    name          text NOT NULL CHECK (name <> ''),
    anweisung     text NOT NULL CHECK (anweisung <> ''),
    wirkung       text,                 -- NULL: Wirkung noch nicht bekannt (offener Vorschlag)
    vorschlag_typ text,                 -- NULL: reiner Protokolleintrag ohne Vorschlag
    status        text NOT NULL DEFAULT 'offen'
                  CHECK (status IN ('offen', 'freigegeben', 'abgelehnt')),
    modell        text,                 -- NULL: kein Modell beteiligt (akteur mensch)
    provider      text,
    ref           text,                 -- Bezug, z. B. Pfad unter erzeugt/ oder Regel-ID
    commit_hash   text                  -- gesetzt nach erfolgreicher Freigabe
);

-- lies(): Filter uc/status, neueste zuerst
CREATE INDEX IF NOT EXISTS protokoll_uc_status_id_idx ON meta.protokoll (uc, status, id DESC);
-- pruefe_freigegeben(): Suche nach ref
CREATE INDEX IF NOT EXISTS protokoll_ref_idx ON meta.protokoll (ref) WHERE ref IS NOT NULL;

CREATE TABLE IF NOT EXISTS meta.freigabe (
    id            bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    protokoll_id  bigint NOT NULL REFERENCES meta.protokoll (id) ON DELETE RESTRICT,
    name          text NOT NULL CHECK (name <> ''),
    zeitpunkt     timestamptz NOT NULL DEFAULT now(),
    entscheidung  text NOT NULL CHECK (entscheidung IN ('ja', 'nein')),
    begruendung   text,                 -- Pflicht bei nein (siehe CHECK unten)
    objekt_typ    text CHECK (objekt_typ IN ('datei', 'regel', 'lieferung', 'antwort')),
    objekt_ref    text,
    CONSTRAINT freigabe_ja_mit_objekt CHECK (entscheidung = 'nein' OR objekt_typ IS NOT NULL),
    CONSTRAINT freigabe_nein_mit_begruendung CHECK (entscheidung = 'ja' OR coalesce(begruendung, '') <> '')
);

-- FK-Index
CREATE INDEX IF NOT EXISTS freigabe_protokoll_id_idx ON meta.freigabe (protokoll_id);
