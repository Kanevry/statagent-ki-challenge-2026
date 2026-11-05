-- Revisionsbedarf, Rückfragen und Veröffentlichung (Qualitätsbericht § 3 und § 5, Technische Regel 7).

-- Veröffentlichung eines Monats: ein Mensch gibt die Lieferung mit Namen frei; erst dann ist sie endgültig.
ALTER TABLE meta.lauf ADD COLUMN IF NOT EXISTS freigegeben_von text;
ALTER TABLE meta.lauf ADD COLUMN IF NOT EXISTS freigegeben_am timestamptz;

-- Revisionsbedarf: ein Lauf rechnet die Vormonate aus seiner Lieferung nach und vergleicht mit dem
-- veröffentlichten (bzw. vorläufigen) Wert. Veröffentlichtes bleibt unverändert (Fachbeschreibung § 4 Nr. 4).
CREATE TABLE IF NOT EXISTS meta.revision (
  lauf_id         int  NOT NULL REFERENCES meta.lauf (id),
  berichtsmonat   text NOT NULL CHECK (berichtsmonat ~ '^\d{4}-\d{2}$'),
  gliederung      text NOT NULL CHECK (gliederung IN ('insgesamt', 'region', 'geschlecht', 'qualifikation', 'oenace')),
  schluessel      text NOT NULL,                             -- Code der Ausprägung, 'AT' bei insgesamt
  veroeffentlicht bigint NOT NULL,                           -- Wert aus der Lieferung des Berichtsmonats
  aktuell         bigint NOT NULL,                           -- Wert laut Lieferung dieses Laufs
  differenz       bigint GENERATED ALWAYS AS (aktuell - veroeffentlicht) STORED,
  status_vorher   text NOT NULL,                             -- vorlaeufig | endgueltig
  PRIMARY KEY (lauf_id, berichtsmonat, gliederung, schluessel)
);

-- Zerlegung der Differenz auf Ebene der Verhältnisse (Hauptursache).
CREATE TABLE IF NOT EXISTS meta.revision_ursache (
  lauf_id       int  NOT NULL REFERENCES meta.lauf (id),
  berichtsmonat text NOT NULL,
  ursache       text NOT NULL CHECK (ursache IN ('nachmeldung', 'rueckwirkende_abmeldung', 'nicht_mehr_enthalten',
                                                  'merkmal_geaendert')),
  anzahl        bigint NOT NULL,
  beispiele     jsonb NOT NULL DEFAULT '[]'::jsonb,          -- höchstens 5 VVH_IDs
  PRIMARY KEY (lauf_id, berichtsmonat, ursache)
);

-- Rückfragen an die Fachabteilung nach Veranstaltervorlage (rueckfrage_vorlage.md), mit Beleg.
-- Die gewählte Behandlung ist eine Regel (regel_name); ändert sich die Antwort, ändert sich nur die Regel.
CREATE TABLE IF NOT EXISTS meta.rueckfrage (
  nr                 text PRIMARY KEY,                       -- 'R1' …
  titel              text NOT NULL,
  lieferungen        text NOT NULL,                          -- betroffene Lieferung(en)
  aufgefallen        text NOT NULL,
  anzahl             text NOT NULL,                          -- Anzahl betroffener Sätze (mit Bezug)
  merkmale           text NOT NULL,
  beispiele          jsonb NOT NULL DEFAULT '[]'::jsonb,     -- VVH_IDs
  beleg_sql          text NOT NULL,
  vorschlag          text NOT NULL,                          -- unser Vorschlag zur Behandlung (= Annahme)
  frage              text NOT NULL,
  regel_name         text,                                   -- meta.regel.name der umgesetzten Annahme
  gestellt_am        date,
  antwort            text,
  antwort_am         date,
  ab_lieferung       text                                    -- ab welchem Berichtsmonat die Rückfrage gilt
);
