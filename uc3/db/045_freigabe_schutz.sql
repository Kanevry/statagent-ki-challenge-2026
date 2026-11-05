-- Freigaben binden an den Regelstand, Freigegebenes ist geschützt (Technische Regel 7, Review !13).

-- Welcher Regelstand (Hash über Regeln und Quellzuordnung, statagent.regeln.regelstand) ist für welche Lieferung
-- freigegeben. `uc3 veroeffentlichen` verlangt, dass der Lauf genau diesen Stand gerechnet hat.
CREATE TABLE IF NOT EXISTS meta.regelstand_freigabe (
  regelsatz       text NOT NULL,
  lieferung       text NOT NULL CHECK (lieferung ~ '^\d{4}-\d{2}$'),
  regelstand      text NOT NULL,
  freigegeben_von text NOT NULL,
  freigegeben_am  timestamptz NOT NULL DEFAULT now(),
  protokoll_id    bigint,                                    -- meta.protokoll (Vertrag P), falls vorhanden
  PRIMARY KEY (regelsatz, lieferung, regelstand)
);

-- Frühere Fassungen freigegebener Regeln (jede Änderung bleibt nachvollziehbar).
CREATE TABLE IF NOT EXISTS meta.regel_historie (
  id          bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  regel_id    int NOT NULL,
  geaendert_am timestamptz NOT NULL DEFAULT now(),
  fassung     jsonb NOT NULL                                 -- vollständige alte Zeile
);

-- Eine freigegebene Regel ändert sich nur zusammen mit einer neuen Freigabe (neuer Zeitpunkt).
CREATE OR REPLACE FUNCTION meta.schuetze_freigegebene_regel() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
  IF OLD.freigegeben_von IS NULL THEN
    RETURN NEW;
  END IF;
  IF TG_OP = 'DELETE' THEN
    RAISE EXCEPTION 'meta.regel: freigegebene Regel % darf nicht gelöscht werden (deaktivieren statt löschen)', OLD.name;
  END IF;
  IF (NEW.parameter, NEW.typ, NEW.art, NEW.reihenfolge, NEW.gueltig_ab_lieferung, NEW.gueltig_bis_lieferung,
      NEW.aktiv, NEW.name, NEW.regelsatz)
     IS DISTINCT FROM
     (OLD.parameter, OLD.typ, OLD.art, OLD.reihenfolge, OLD.gueltig_ab_lieferung, OLD.gueltig_bis_lieferung,
      OLD.aktiv, OLD.name, OLD.regelsatz)
     AND NEW.freigegeben_am IS NOT DISTINCT FROM OLD.freigegeben_am THEN
    RAISE EXCEPTION 'meta.regel: freigegebene Regel % ändert sich nur mit neuer Freigabe (Name und Zeitpunkt)', OLD.name;
  END IF;
  INSERT INTO meta.regel_historie (regel_id, fassung) VALUES (OLD.id, to_jsonb(OLD));
  RETURN NEW;
END $$;
CREATE OR REPLACE TRIGGER regel_freigegeben_schutz BEFORE UPDATE OR DELETE ON meta.regel
  FOR EACH ROW EXECUTE FUNCTION meta.schuetze_freigegebene_regel();

-- TRUNCATE umgeht Zeilentrigger: bei veröffentlichten Zeilen verweigern.
CREATE OR REPLACE FUNCTION stat.verbiete_truncate_endgueltig() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
  IF EXISTS (SELECT 1 FROM stat.stat_beschaeftigte WHERE status = 'endgueltig') THEN
    RAISE EXCEPTION 'stat.stat_beschaeftigte enthält veröffentlichte Zeilen: TRUNCATE verweigert';
  END IF;
  RETURN NULL;
END $$;
CREATE OR REPLACE TRIGGER stat_besch_kein_truncate BEFORE TRUNCATE ON stat.stat_beschaeftigte
  FOR EACH STATEMENT EXECUTE FUNCTION stat.verbiete_truncate_endgueltig();
