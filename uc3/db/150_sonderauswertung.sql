-- Ausgaben (Lieferungen nach außen, z. B. an das Ministerium): jede Datei wird mit Namen freigegeben
-- (Technische Regel 7: „jede Lieferung gibt ein Teammitglied frei“). Die Definition einer Sonderauswertung
-- ist eine Regel in meta.regel (eigener Regelsatz, typ zaehl, art personentage), vorgeschlagen von einem Agenten.
CREATE TABLE IF NOT EXISTS meta.ausgabe (
  id              serial PRIMARY KEY,
  art             text NOT NULL,                             -- 'ministerium'
  berichtsmonat   text NOT NULL CHECK (berichtsmonat ~ '^\d{4}-\d{2}$'),
  regel_id        int  NOT NULL REFERENCES meta.regel (id),
  datei           text NOT NULL,                             -- Pfad relativ zur Repo-Wurzel
  zeilen          bigint NOT NULL,
  sha256          text NOT NULL,
  datenstand      jsonb NOT NULL,                            -- je Monat die verwendete Lieferung
  erstellt_am     timestamptz NOT NULL DEFAULT now(),
  freigegeben_von text NOT NULL,
  freigegeben_am  timestamptz NOT NULL DEFAULT now()
);
