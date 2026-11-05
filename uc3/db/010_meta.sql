-- Regeln als Daten (Technische Regel 3). Der Code kennt nur Regel-ARTEN (siehe statagent/regeln.py);
-- jeder Wert (Codes, Stichtag, Altersgrenze, Schwellen) steht hier in `parameter`.
CREATE TABLE IF NOT EXISTS meta.regel (
  id                    serial PRIMARY KEY,
  regelsatz             text NOT NULL,                       -- 'v1' Fachbeschreibung, 'v2' Änderungsaufträge
  name                  text NOT NULL,                       -- z. B. 'E01_spaltentausch_beginn_ende'
  typ                   text NOT NULL CHECK (typ IN ('einlese', 'zaehl', 'pruefung', 'zuordnung')),
  art                   text NOT NULL,                       -- Implementierungsart, z. B. 'spaltentausch', 'bestand'
  reihenfolge           int  NOT NULL DEFAULT 100,
  parameter             jsonb NOT NULL DEFAULT '{}'::jsonb,
  beschreibung          text NOT NULL,                       -- für Menschen lesbar
  begruendung           text NOT NULL,                       -- Beleg: Fachbeschreibung, Rückfrage, Messung
  grundlage             text NOT NULL,                       -- Fachbeschreibung § …, Rückfrage R…, Änderungsauftrag …
  gueltig_ab_lieferung  text NOT NULL DEFAULT '2024-08' CHECK (gueltig_ab_lieferung ~ '^\d{4}-\d{2}$'),
  gueltig_bis_lieferung text CHECK (gueltig_bis_lieferung IS NULL OR gueltig_bis_lieferung ~ '^\d{4}-\d{2}$'),
  aktiv                 boolean NOT NULL DEFAULT true,
  freigegeben_von       text,
  freigegeben_am        timestamptz,
  ersetzt_regel_id      int REFERENCES meta.regel (id),
  erstellt_am           timestamptz NOT NULL DEFAULT now(),
  UNIQUE (regelsatz, name),
  CHECK ((freigegeben_von IS NULL) = (freigegeben_am IS NULL))
);

-- Ein Lauf = eine Lieferung (Fachbeschreibung § 2a).
CREATE TABLE IF NOT EXISTS meta.lauf (
  id                   serial PRIMARY KEY,
  lieferung            text NOT NULL CHECK (lieferung ~ '^\d{4}-\d{2}$'),
  regelsatz            text NOT NULL,
  regelstand           text,                                 -- Hash über aktive Regeln + Quellzuordnung
  gestartet_am         timestamptz NOT NULL DEFAULT now(),
  beendet_am           timestamptz,
  status               text NOT NULL DEFAULT 'laeuft'
                       CHECK (status IN ('laeuft', 'fertig', 'unveraendert', 'abgebrochen')),
  ergebnis_status      text CHECK (ergebnis_status IN ('vorlaeufig', 'endgueltig', 'gesperrt')),
  gelesen              bigint,                               -- Zeilen der Lieferung
  gezaehlt             bigint,                               -- Verhältnisse am Stichtag (je VVH_ID einmal)
  nicht_gezaehlt       bigint,                               -- Abschnitte ohne Bestand im Berichtszeitraum + Mehrfachabschnitte
  ausgeschlossen       bigint,                               -- Volldubletten (zu einem Satz verdichtet)
  korrigiert           bigint,                               -- Sätze, die eine Einleseregel verändert hat (Info, nicht Teil der Abrechnung)
  ergebnis_hash        text,                                 -- sha256 über alle Zellen, kanonisch sortiert
  zellen               bigint,
  gestartet_von        text,
  meldung              text
);
CREATE INDEX IF NOT EXISTS lauf_lieferung_idx ON meta.lauf (regelsatz, lieferung, id);

-- Welche Regel hat in welchem Lauf wie viele Sätze betroffen (Qualitätsbericht § 4).
CREATE TABLE IF NOT EXISTS meta.regel_wirkung (
  lauf_id  int NOT NULL REFERENCES meta.lauf (id),
  regel_id int NOT NULL REFERENCES meta.regel (id),
  saetze   bigint NOT NULL,
  hinweis  text,
  PRIMARY KEY (lauf_id, regel_id)
);

-- Treffer der Prüfregeln je Lauf (Grundlage Qualitätsbericht § 2).
CREATE TABLE IF NOT EXISTS meta.pruefung_treffer (
  lauf_id    int NOT NULL REFERENCES meta.lauf (id),
  regel_id   int NOT NULL REFERENCES meta.regel (id),
  ebene      text NOT NULL CHECK (ebene IN ('satz', 'aggregat', 'lieferung')),
  anzahl     bigint NOT NULL,
  umfang     text,                                           -- z. B. '1.663 Sätze', '3 Zellen'
  beispiele  jsonb NOT NULL DEFAULT '[]'::jsonb,             -- höchstens 5 VVH_IDs, nie PERSON_ID
  einstufung text CHECK (einstufung IN ('erklaert-plausibel', 'erklaert-datenproblem', 'nicht-erklaerbar')),
  massnahme  text,
  anhalten   boolean NOT NULL DEFAULT false,                 -- true: Monat bleibt vorläufig
  beleg_sql  text,
  details    jsonb NOT NULL DEFAULT '{}'::jsonb,
  PRIMARY KEY (lauf_id, regel_id, ebene)
);
