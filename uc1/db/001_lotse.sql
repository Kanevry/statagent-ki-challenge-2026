-- UC1 KI-Lotse: Datenbank lotse auf PG16 (Port 5433), getrennt von der UC3-Datenbank statistik.
-- Idempotent: `lotse db-init` darf beliebig oft laufen.

CREATE EXTENSION IF NOT EXISTS unaccent;
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- Eigene Suchkonfiguration: german plus unaccent. unaccent() selbst ist nicht IMMUTABLE und taugt
-- deshalb nicht für eine generierte Spalte; als Wörterbuch in einer Konfiguration schon.
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_ts_config WHERE cfgname = 'lotse_german') THEN
    CREATE TEXT SEARCH CONFIGURATION public.lotse_german (COPY = pg_catalog.german);
    ALTER TEXT SEARCH CONFIGURATION public.lotse_german
      ALTER MAPPING FOR hword, hword_part, word WITH unaccent, german_stem;
  END IF;
END
$$;

CREATE SCHEMA IF NOT EXISTS lotse;

-- Ein Dokument = eine Datei des Korpus (SozDok-XML: eine Fassung eines §/Art; PDF; EKO-Datei).
CREATE TABLE IF NOT EXISTS lotse.dokument (
  id            bigserial PRIMARY KEY,
  quelle        text NOT NULL CHECK (quelle IN ('sozdok', 'formular', 'katalog', 'eko', 'befund')),
  dokid         text NOT NULL UNIQUE,  -- SozDok: Attribut dokid; sonst Dateipfad relativ zu UC1_DATA_DIR
  datei         text NOT NULL,         -- Pfad relativ zu UC1_DATA_DIR
  titel         text,                  -- SozDok: titrvo; PDF: Dateiname
  gesetz        text,                  -- SozDok: abkrvo
  art           text,                  -- SozDok: gldart (PARA, ART, ...)
  nummer        text,                  -- SozDok: gldnr
  inkrafttreten date,                  -- SozDok: ikra
  berkz         text,                  -- SozDok: berkz (Bereichskennzeichen)
  meta          jsonb NOT NULL DEFAULT '{}'::jsonb,
  inhalt_hash   text NOT NULL          -- sha256 über die sortierten Abschnittstexte
);

CREATE INDEX IF NOT EXISTS dokument_gesetz_idx ON lotse.dokument (gesetz, art, nummer);

-- Ein Abschnitt = zitierfähige Einheit: SozDok-Absatz bzw. ganzes kleines Dokument, PDF-Seite, EKO-Zeile.
CREATE TABLE IF NOT EXISTS lotse.abschnitt (
  id          bigserial PRIMARY KEY,
  dokument_id bigint NOT NULL REFERENCES lotse.dokument (id) ON DELETE CASCADE,
  nr          integer NOT NULL,        -- laufende Nummer im Dokument, ab 0
  seite       integer,                 -- PDF, ab 1
  zeile       integer,                 -- EKO, ab 1
  kontext     text NOT NULL DEFAULT '',-- Überschrift für Suche und Anzeige, z. B. "BPGG § 4 Pflegebedarf"
  text        text NOT NULL,
  text_hash   text NOT NULL,           -- sha256(kontext || E'\n' || text); Schlüssel für lotse.vektor
  tsv         tsvector GENERATED ALWAYS AS (
                setweight(to_tsvector('public.lotse_german'::regconfig, kontext), 'A')
                || setweight(to_tsvector('public.lotse_german'::regconfig, text), 'B')
              ) STORED,
  UNIQUE (dokument_id, nr)
);

CREATE INDEX IF NOT EXISTS abschnitt_tsv_idx ON lotse.abschnitt USING gin (tsv);
CREATE INDEX IF NOT EXISTS abschnitt_trgm_idx ON lotse.abschnitt USING gin (text gin_trgm_ops);
CREATE INDEX IF NOT EXISTS abschnitt_hash_idx ON lotse.abschnitt (text_hash);

-- Dateien, die nicht eingelesen werden konnten, je mit Grund. Summe mit dokument(sozdok) = 14.244.
CREATE TABLE IF NOT EXISTS lotse.ingest_fehler (
  id    bigserial PRIMARY KEY,
  datei text NOT NULL UNIQUE,
  grund text NOT NULL
);

-- Dichte Vektoren ohne pgvector (nicht installiert). Schlüssel ist der Text-Hash, damit ein neuer
-- Ingest die Vektoren nicht entwertet. Cosinus rechnet der Dienst in numpy.
CREATE TABLE IF NOT EXISTS lotse.vektor (
  text_hash text NOT NULL,
  modell    text NOT NULL,
  dim       integer NOT NULL,
  v         real[] NOT NULL,
  PRIMARY KEY (text_hash, modell, dim)
);
