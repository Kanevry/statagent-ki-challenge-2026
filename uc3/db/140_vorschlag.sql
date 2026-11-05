-- Vorschläge der eigenen Agenten (GitLab #15, Technische Regeln 5–8). UC3-eigen.
-- Ein Agent schlägt vor (Regeländerung, neue Regel oder Code-Datei), das Programm rechnet die Probe, ein Mensch
-- gibt mit Vor- und Nachnamen frei. Erst danach wird der Vorschlag angewendet.
-- `protokoll_id` verweist auf meta.protokoll(id) aus Vertrag P (E0, #55). Kein Fremdschlüssel, solange
-- meta.protokoll noch nicht in jeder Datenbank steht. Idempotent.
-- Ziel: uc3/db/140_vorschlag.sql (dann spielt db.schema_einrichten sie mit ein).
CREATE TABLE IF NOT EXISTS meta.vorschlag (
  id               serial PRIMARY KEY,                     -- = meta.protokoll.id, sobald meta.protokoll existiert
  protokoll_id     int,
  erstellt_am      timestamptz NOT NULL DEFAULT now(),
  anweisung        text NOT NULL,                          -- wörtlich, wie der Mensch sie gegeben hat
  rolle            text NOT NULL CHECK (rolle IN ('datenmanagement', 'klassifikation', 'qs', 'reporting')),
  typ              text NOT NULL CHECK (typ IN ('regel_neu', 'regel_aendern', 'code_datei')),
  regelsatz_ziel   text NOT NULL CHECK (regelsatz_ziel ~ '^v[0-9]+$'),
  regelsatz_basis  text NOT NULL CHECK (regelsatz_basis ~ '^v[0-9]+$'),
  -- regel_aendern: [{regel_name, parameter_alt, parameter_neu}]; regel_neu: [{regel: {...}}];
  -- code_datei: [{pfad, inhalt_sha256}] (Pfad relativ zur Repo-Wurzel)
  aenderungen      jsonb NOT NULL CHECK (jsonb_typeof(aenderungen) = 'array' AND jsonb_array_length(aenderungen) > 0),
  datei_inhalt     text,                                   -- vollständiger Inhalt der Code-Datei (nur code_datei)
  begruendung      text NOT NULL,
  probe            jsonb NOT NULL DEFAULT '{}'::jsonb,     -- Zahlen vorher/nachher je Probemonat, nur Aggregate
  modell           text,
  provider         text,
  status           text NOT NULL DEFAULT 'offen' CHECK (status IN ('offen', 'freigegeben', 'abgelehnt')),
  freigegeben_von  text,
  freigegeben_am   timestamptz,
  commit_hash      text,
  angewendet_am    timestamptz,                            -- NULL bei 'freigegeben': freigegeben, nicht angewendet
  anwenden_fehler  text,                                   -- Fehlerklasse des letzten gescheiterten Anwendens
  abgelehnt_von    text,
  abgelehnt_am     timestamptz,
  ablehnungsgrund  text,
  CHECK ((freigegeben_von IS NULL) = (freigegeben_am IS NULL)),
  CHECK ((abgelehnt_von IS NULL) = (abgelehnt_am IS NULL)),
  CHECK (status <> 'freigegeben' OR freigegeben_von IS NOT NULL),
  CHECK (status <> 'abgelehnt' OR abgelehnt_von IS NOT NULL),
  CHECK (angewendet_am IS NULL OR status = 'freigegeben'),
  CHECK ((typ = 'code_datei') = (datei_inhalt IS NOT NULL))
);
CREATE UNIQUE INDEX IF NOT EXISTS vorschlag_protokoll_idx ON meta.vorschlag (protokoll_id)
  WHERE protokoll_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS vorschlag_status_idx ON meta.vorschlag (status, id);
