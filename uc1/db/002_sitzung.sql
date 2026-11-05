-- UC1 KI-Lotse: Gesprächszustand und Belege (Issue #31). Idempotent: `lotse db-init` darf beliebig oft laufen.

-- Eine Sitzung = ein Gespräch mit dem Lotsen. zustand: Lage, erkannte Leistungen, Angaben, gestellte
-- Rückfragen (Daten, kein Freitext-Protokoll). rueckfragen zählt die gestellten Rückfragen (höchstens 3).
CREATE TABLE IF NOT EXISTS lotse.sitzung (
  id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  erstellt    timestamptz NOT NULL DEFAULT now(),
  geaendert   timestamptz NOT NULL DEFAULT now(),
  zustand     jsonb NOT NULL DEFAULT '{}'::jsonb,
  sprache     text NOT NULL DEFAULT 'de' CHECK (sprache IN ('de', 'en')),
  stil        text NOT NULL DEFAULT 'standard' CHECK (stil IN ('standard', 'einfach')),
  rueckfragen integer NOT NULL DEFAULT 0 CHECK (rueckfragen >= 0)
);

-- Ein Beleg = ein geprüftes Zitat einer angezeigten Aussage. call_id: Vapi-Call (Voice-Pfad), sonst NULL.
-- abschnitt_id ohne Fremdschlüssel: `lotse ingest` leert lotse.abschnitt per TRUNCATE, ein FK würde das
-- blockieren. Die Belege behalten das Zitat im Wortlaut.
CREATE TABLE IF NOT EXISTS lotse.beleg (
  id           bigserial PRIMARY KEY,
  sitzung_id   uuid NOT NULL REFERENCES lotse.sitzung (id) ON DELETE CASCADE,
  call_id      text,
  abschnitt_id bigint NOT NULL,
  zitat        text NOT NULL,
  erstellt     timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS beleg_sitzung_idx ON lotse.beleg (sitzung_id);
CREATE INDEX IF NOT EXISTS beleg_call_idx ON lotse.beleg (call_id) WHERE call_id IS NOT NULL;
