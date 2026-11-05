-- Bereinigte Zeitabschnitte je Lieferung und Regelsatz (Schritt 1). Abgeleitet: ein Lauf baut seine
-- Lieferung neu auf. Kein Satz geht verloren: Volldubletten werden verdichtet (roh_zeilen zählt sie),
-- unklare Werte werden zugeordnet und markiert, nicht entfernt.
CREATE TABLE IF NOT EXISTS bereinigt.abschnitt (
  lieferung            text NOT NULL,
  regelsatz            text NOT NULL,
  lauf_id              int  NOT NULL,
  vvh_id               bigint NOT NULL,
  person_id            bigint,
  geburtsdatum         date,                                 -- NULL, wenn nicht gültig
  geburtsjahr          int,                                  -- auch bei Monat 13 bekannt
  geburtsdatum_status  text NOT NULL CHECK (geburtsdatum_status IN ('gueltig', 'monat_13', 'ungueltig')),
  geschlecht           text NOT NULL,
  beginn               date NOT NULL,
  ende                 date,                                 -- NULL = läuft
  qualifikation        text NOT NULL,
  oenace               text NOT NULL,
  oenace_version       text NOT NULL,
  bundesland           text NOT NULL,
  roh_zeilen           int  NOT NULL,                        -- > 1: Volldublette
  korrekturen          text[] NOT NULL DEFAULT '{}',         -- Namen der Einleseregeln, die den Satz verändert haben
  roh_oenace           text,
  roh_bundesland       text
);
CREATE INDEX IF NOT EXISTS abschnitt_lief_idx ON bereinigt.abschnitt (lieferung, regelsatz, vvh_id);

-- Datentabelle der Beschäftigtenstatistik (Anhang B, Long-Format). Mehrere Regelstände stehen
-- nebeneinander (Sheet alt und neu); Veröffentlichtes (status endgueltig) ist unveränderlich.
CREATE TABLE IF NOT EXISTS stat.stat_beschaeftigte (
  zeitraum_art   text NOT NULL CHECK (zeitraum_art IN ('Stichtag', 'Monat', 'Jahr')),
  zeitraum_von   date NOT NULL,
  zeitraum_bis   date NOT NULL,
  region         text NOT NULL,                              -- klass_region (Bundesland), '0' = unbekannt
  oenace         text NOT NULL,                              -- klass_oenace (Abschnitt), 'UNB' = unbekannt
  oenace_version text NOT NULL,
  geschlecht     text NOT NULL,                              -- klass_geschlecht
  qualifikation  text NOT NULL,                              -- klass_qualifikation (v1) bzw. Kategorie (v2)
  alter          int  NOT NULL,                              -- klass_alter, -1 = unbekannt
  variable       text NOT NULL,                              -- stat.variable
  wert           bigint NOT NULL CHECK (wert >= 0),
  status         text NOT NULL CHECK (status IN ('vorlaeufig', 'endgueltig', 'gesperrt')),
  stand          text NOT NULL,                              -- 'Lieferung 2025-03'
  regelsatz      text NOT NULL,
  regelstand     text NOT NULL,
  lauf_id        int  NOT NULL REFERENCES meta.lauf (id),
  PRIMARY KEY (regelsatz, regelstand, zeitraum_art, zeitraum_von, zeitraum_bis,
               region, oenace, oenace_version, geschlecht, qualifikation, alter, variable)
);
CREATE INDEX IF NOT EXISTS stat_besch_lauf_idx ON stat.stat_beschaeftigte (lauf_id);

-- Veröffentlichtes bleibt unverändert (Fachbeschreibung § 4 Nr. 4).
CREATE OR REPLACE FUNCTION stat.schuetze_endgueltig() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
  IF OLD.status = 'endgueltig' THEN
    RAISE EXCEPTION 'stat.stat_beschaeftigte: veröffentlichte Zeile (% %, Lieferung %) ist unveränderlich',
      OLD.zeitraum_art, OLD.zeitraum_bis, OLD.stand
      USING HINT = 'Abweichungen späterer Lieferungen gehören als Revisionsbedarf in den Qualitätsbericht.';
  END IF;
  IF TG_OP = 'DELETE' THEN RETURN OLD; END IF;
  RETURN NEW;
END $$;

CREATE OR REPLACE TRIGGER stat_besch_endgueltig BEFORE UPDATE OR DELETE ON stat.stat_beschaeftigte
  FOR EACH ROW EXECUTE FUNCTION stat.schuetze_endgueltig();
