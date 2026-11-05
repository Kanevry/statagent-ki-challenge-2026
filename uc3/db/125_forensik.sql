-- Die 19 Prüfungen der Datenforensik (R01–R19, Stand 05.11.2026) und ihre Plätze im Prüfkatalog P01–P24.
-- Als Daten, damit der Prüfkatalog (`uc3 pruefkatalog`, uc3/pruefkatalog.csv) die Zuordnung ausweist und
-- Plätze ohne Forensikprüfung als Zusatzprüfung erkennbar sind. Die Forensikprüfungen ändern keine Zahl und
-- gehören nicht zum Regelstand; geprüft wird im Programm über die P-Regeln in meta.regel (120_pruefregeln_v1.sql).
-- Zuordnung: ein Platz kann mehrere Forensikprüfungen abdecken und umgekehrt. Idempotent.

CREATE TABLE IF NOT EXISTS meta.forensik_pruefung (
  nr        text PRIMARY KEY CHECK (nr ~ '^R[0-9]{2}$'),
  name      text NOT NULL,
  ebene     text NOT NULL CHECK (ebene IN ('satz', 'lieferung', 'aggregat')),
  schwelle  text NOT NULL,
  plaetze   text[] NOT NULL,                 -- Katalogplätze P01–P24, die diese Prüfung abdecken
  begruendung text NOT NULL,                 -- warum genau diese Plätze
  quelle    text NOT NULL
);

INSERT INTO meta.forensik_pruefung (nr, name, ebene, schwelle, plaetze, begruendung, quelle) VALUES
('R01', 'zeilenzahl_vs_vormonat', 'lieferung', 'Zeilen / Vormonat < 0,90 oder > 1,10 → Stopp',
 '{P17}', 'P17 vergleicht die Zeilenzahl der Lieferung mit dem Vormonat.', 'Datenforensik 05.11.2026 § 7'),
('R02', 'spaltentausch_beginn_ende', 'lieferung', 'Anteil BEGINN leer > 0,5 bzw. BEGINN > ENDE > 0,05 → tauschen',
 '{P03}', 'P03 meldet die Sätze, bei denen E01 BEGINN und ENDE getauscht hat.', 'Datenforensik 05.11.2026 § 7'),
('R03', 'exakte_duplikate', 'satz', 'gleiche Zeile in allen Spalten > 0 → verdichten, melden',
 '{P01}', 'P01 zählt die zu einem Satz verdichteten Volldubletten (E02).', 'Datenforensik 05.11.2026 § 7'),
('R04', 'vvh_mehrfach_offen', 'satz', 'je VVH_ID mehr als ein offener Abschnitt > 0',
 '{P02}', 'P02 meldet Verhältnisse mit mehr als einem Abschnitt am Stichtag.', 'Datenforensik 05.11.2026 § 7'),
('R05', 'datum_unparsebar', 'satz', 'Datum nicht lesbar > 0 → Muster melden (Monat 13)',
 '{P04,P05,P08}', 'P04 (Monat 13) und P05 (sonst ungültig) für das Geburtsdatum, P08 für einen ersetzten BEGINN.',
 'Datenforensik 05.11.2026 § 7'),
('R06', 'beginn_gt_ende', 'satz', 'BEGINN > ENDE > 0',
 '{P09}', 'P09 meldet Abschnitte mit BEGINN nach ENDE.', 'Datenforensik 05.11.2026 § 7'),
('R07', 'ende_vor_fenster / beginn_in_zukunft', 'satz', 'ENDE < Monatserster − 2 Monate oder BEGINN > Monatsletzter > 0',
 '{P24}', 'P24 prüft den Lieferumfang gegen das Lieferfenster (Berichtsmonat und zwei Vormonate).',
 'Datenforensik 05.11.2026 § 7'),
('R08', 'geburtsdatum_unplausibel', 'satz', 'Geburtsdatum vor 1930, nach BEGINN oder Alter < 14 > 0 → Alter unbekannt',
 '{P06,P07}', 'P06 meldet unplausible Alter (Grenze aus R5_alter), P07 hohe, aber plausible Alter.',
 'Datenforensik 05.11.2026 § 7'),
('R09', 'code_ungueltig', 'satz', 'Code ohne gültige Klassifikation im Berichtsmonat > 0 → Quellzuordnung (DA–DM → C) oder unbekannt',
 '{P11,P12}', 'P11 meldet ÖNACE-2003-Altcodes, P12 Codes ohne Klassifikation und ohne Zuordnung.',
 'Datenforensik 05.11.2026 § 7'),
('R10', 'code_null_anteil', 'lieferung', 'Anteil leerer Codes je Spalte > 1 % oder Veränderung zum Vormonat > 0,2 Prozentpunkte',
 '{P10}', 'P10 meldet leere Merkmale.', 'Datenforensik 05.11.2026 § 7'),
('R11', 'auspraegung_verschwunden', 'aggregat', 'Wert im Vormonat > 100 und jetzt 0 → Stopp (FD 03/2025)',
 '{P13}', 'P13 meldet Ausprägungen, die gegenüber dem Vormonat verschwinden.', 'Datenforensik 05.11.2026 § 7'),
('R12', 'sprung_aggregat', 'aggregat', 'Veränderung je Zelle zum Vormonat > 3 % bei n ≥ 500; Saison und Klassifikationswechsel ausgenommen',
 '{P14}', 'P14 meldet Sprünge in den Aggregatzellen mit denselben Ausnahmen.', 'Datenforensik 05.11.2026 § 7'),
('R13', 'abschnitt_luecke / ueberlappung', 'satz', 'Lücke oder Überlappung zwischen Abschnitten eines Verhältnisses > 0 → melden, Stichtagsabschnitt wählen',
 '{P02}', 'P02 vergleicht die Abschnitte eines Verhältnisses; aufeinanderfolgende Abschnitte sind kein Treffer, Überlappungen schon.',
 'Datenforensik 05.11.2026 § 7'),
('R14', 'merkmalswelle', 'satz', 'gleicher BEGINN und gleicher Codewechsel > 100 → Rückfrage',
 '{P18}', 'P18 meldet Wellen gleicher Merkmalswechsel (Rückfrage R6).', 'Datenforensik 05.11.2026 § 7'),
('R15', 'phantom_doppelmeldung', 'satz', 'neues Verhältnis mit Beginn im Berichtsmonat, Person hat zweites Verhältnis mit gleichen Merkmalen > 0',
 '{P19}', 'P19 kennzeichnet kurzlebige Zweitmeldungen (Rückfrage R7).', 'Datenforensik 05.11.2026 § 7'),
('R16', 'revision_vormonat', 'lieferung', 'Stichtag des Vormonats aus der aktuellen Lieferung gegen veröffentlicht > 0,5 % → Rückfrage',
 '{P23}', 'P23 rechnet den Vormonat aus der aktuellen Lieferung nach und weist den Revisionsbedarf aus.',
 'Datenforensik 05.11.2026 § 7'),
('R17', 'person_konsistenz', 'satz', 'mehr als ein Geburtsdatum oder Geschlecht je PERSON_ID > 0',
 '{P20}', 'P20 meldet Personen mit widersprüchlichen Merkmalen.', 'Datenforensik 05.11.2026 § 7'),
('R18', 'fenster_abdeckung', 'lieferung', 'Enden im Vormonat < 50 % des Üblichen → kein Vollabzug (08/2024)',
 '{P24}', 'P24 prüft, ob die Lieferung das ganze Fenster abdeckt.', 'Datenforensik 05.11.2026 § 7'),
('R19', 'bilanz', 'lieferung', 'gelesen = gezählt + nicht am Stichtag + verdichtet + ausgeschlossen; ≠ 0 → Fehler',
 '{P22}', 'P22 prüft die Abrechnung der Sätze (mit fortgeschriebenen Verhältnissen nach E07).',
 'Datenforensik 05.11.2026 § 7')
ON CONFLICT (nr) DO UPDATE
  SET name = EXCLUDED.name, ebene = EXCLUDED.ebene, schwelle = EXCLUDED.schwelle, plaetze = EXCLUDED.plaetze,
      begruendung = EXCLUDED.begruendung, quelle = EXCLUDED.quelle;
