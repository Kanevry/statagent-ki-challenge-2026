-- Zu- und Abgänge je ÖNACE-Abschnitt für Datenanfragen (#74, Fluktuation). Liefert nur Summen, nie Einzelsätze:
-- Antworten und freie Abfragen (sql_lesen) lesen bereinigt.* nie selbst, nur über diese feste Aggregatfunktion.
--
-- Zugang: Beschäftigungsverhältnis (VVH_ID) besteht am Stichtag, aber nicht am Stichtag davor.
-- Abgang: besteht am Stichtag davor, aber nicht am Stichtag. Beide Stichtage aus derselben Lieferung, damit eine
-- verspätete Meldung nicht als Zu- oder Abgang zählt. Bestehen wie Zählregel 2 (Beginn ≤ Stichtag, Ende leer
-- oder ≥ Stichtag); der Abschnitt je Verhältnis wie die Abschnittswahl „spaetester_beginn“ in
-- statagent/zaehlung.py (_ORDNUNG; eine neue Ordnung dort braucht dieselbe Änderung hier).
-- Zugänge zählen beim ÖNACE-Abschnitt am Stichtag, Abgänge beim Abschnitt am Stichtag davor.
--
-- bereinigt.abschnitt hält nur den jüngsten Lauf einer Lieferung. Stammt er aus einem anderen Regelstand als
-- der gefragte, bricht die Funktion ab statt Zahlen aus zwei Regelständen zu mischen.
CREATE OR REPLACE FUNCTION stat.bewegung_oenace(
  p_lieferung text, p_regelsatz text, p_regelstand text, p_stichtag_vorher date, p_stichtag date
) RETURNS TABLE (oenace text, zugaenge bigint, abgaenge bigint)
LANGUAGE plpgsql STABLE SECURITY DEFINER SET search_path = pg_catalog, pg_temp AS $$
#variable_conflict use_column
DECLARE
  v_regelstand text;
BEGIN
  SELECT l.regelstand INTO v_regelstand
  FROM bereinigt.abschnitt a JOIN meta.lauf l ON l.id = a.lauf_id
  WHERE a.lieferung = p_lieferung AND a.regelsatz = p_regelsatz
  ORDER BY a.lauf_id DESC LIMIT 1;
  IF v_regelstand IS NULL THEN
    RAISE EXCEPTION 'Für Lieferung % (Regelsatz %) liegen keine bereinigten Daten vor', p_lieferung, p_regelsatz;
  END IF;
  IF v_regelstand <> p_regelstand THEN
    RAISE EXCEPTION 'Die bereinigten Daten der Lieferung % stammen aus Regelstand %, gefragt ist %',
      p_lieferung, v_regelstand, p_regelstand;
  END IF;
  RETURN QUERY
  WITH am AS (
    SELECT DISTINCT ON (a.vvh_id) a.vvh_id, a.oenace
    FROM bereinigt.abschnitt a
    WHERE a.lieferung = p_lieferung AND a.regelsatz = p_regelsatz
      AND a.beginn <= p_stichtag AND (a.ende IS NULL OR a.ende >= p_stichtag)
    ORDER BY a.vvh_id, a.beginn DESC, a.ende DESC NULLS FIRST, a.qualifikation COLLATE "C",
      a.oenace COLLATE "C", a.bundesland COLLATE "C", a.geschlecht COLLATE "C",
      a.geburtsdatum_status COLLATE "C", a.geburtsdatum NULLS LAST, a.geburtsjahr NULLS LAST,
      a.person_id NULLS LAST, a.roh_zeilen
  ), vorher AS (
    SELECT DISTINCT ON (a.vvh_id) a.vvh_id, a.oenace
    FROM bereinigt.abschnitt a
    WHERE a.lieferung = p_lieferung AND a.regelsatz = p_regelsatz
      AND a.beginn <= p_stichtag_vorher AND (a.ende IS NULL OR a.ende >= p_stichtag_vorher)
    ORDER BY a.vvh_id, a.beginn DESC, a.ende DESC NULLS FIRST, a.qualifikation COLLATE "C",
      a.oenace COLLATE "C", a.bundesland COLLATE "C", a.geschlecht COLLATE "C",
      a.geburtsdatum_status COLLATE "C", a.geburtsdatum NULLS LAST, a.geburtsjahr NULLS LAST,
      a.person_id NULLS LAST, a.roh_zeilen
  ), bewegung AS (
    SELECT n.oenace, true AS zugang FROM am n
    WHERE NOT EXISTS (SELECT 1 FROM vorher v WHERE v.vvh_id = n.vvh_id)
    UNION ALL
    SELECT v.oenace, false FROM vorher v
    WHERE NOT EXISTS (SELECT 1 FROM am n WHERE n.vvh_id = v.vvh_id)
  )
  SELECT b.oenace, count(*) FILTER (WHERE b.zugang), count(*) FILTER (WHERE NOT b.zugang)
  FROM bewegung b GROUP BY b.oenace;
END $$;
