-- Annahmen F1 bis F10: was wir bis zur Antwort der Fachabteilung annehmen, in einem Satz für den
-- Qualitätsbericht und die Weboberfläche. `rueckfrage` verweist auf meta.rueckfrage (R1 bis R9),
-- `regel_name` auf die Regel, die die Annahme umsetzt, `lieferungen` auf die Monate, für die der Satz
-- gilt (NULL = alle). Annahmen ändern keine Zahl und gehören nicht zum Regelstand. Idempotent.

CREATE TABLE IF NOT EXISTS meta.annahme (
  nr          text PRIMARY KEY CHECK (nr ~ '^F\d+$'),
  rueckfrage  text,
  regel_name  text,
  lieferungen text[],
  satz        text NOT NULL,
  begruendung text NOT NULL
);

INSERT INTO meta.annahme (nr, rueckfrage, regel_name, lieferungen, satz, begruendung) VALUES
('F1', 'R3', 'E07_fortschreibung_lieferausfall', ARRAY['2025-10'],
 'Für Oktober 2025 fehlen rund 79.000 Verhältnisse. Wir übernehmen sie einmal aus der September-Lieferung und lassen den Monat vorläufig, bis die Fachabteilung antwortet.',
 'So geht kein Verhältnis verloren, und wir nutzen nur eine frühere Lieferung. Die November-Lieferung zeigt später, wie weit die Übernahme danebenlag.'),
('F2', 'R4', 'E07_fortschreibung_lieferausfall', ARRAY['2025-03'],
 'Im März 2025 fehlen alle freien Dienstverträge. Wir übernehmen sie aus der Februar-Lieferung und lassen den Monat vorläufig, bis die Fachabteilung antwortet.',
 'Eine ganze Gruppe verschwindet nicht für einen Monat. Die April-Lieferung enthält alle 1.492 freien Dienstverträge wieder.'),
('F3', 'R5', 'E01_spaltentausch_beginn_ende', ARRAY['2025-06'],
 'Im Juni 2025 sind Beginn und Ende vertauscht geliefert. Wir tauschen beide Felder für alle 432.086 Sätze zurück.',
 'Ohne Tausch blieben am Stichtag nur 21 Verhältnisse übrig, mit Tausch passt der Monat zu den Nachbarmonaten.'),
('F4', 'R8', 'P19_phantom_doppelmeldung', NULL,
 'Kurze Zweitmeldungen derselben Person zählen als eigenes Beschäftigungsverhältnis. Wir kennzeichnen sie, bis die Fachabteilung antwortet.',
 'Die Statistik zählt Beschäftigungsverhältnisse, nicht Personen. So geht nichts verloren, und die Fälle bleiben sichtbar.'),
('F5', NULL, 'Q01_oenace_2003_unterabschnitte', NULL,
 'Alte Branchencodes aus ÖNACE 2003 (DA bis DN) zählen zur Herstellung von Waren (Abschnitt C), in den Tabellen und in der Lieferung an das Ministerium gleich.',
 'Der Beispielbericht des Veranstalters zählt sie ebenso zu C. Dieselbe Person soll nicht an einer Stelle zu C zählen und an der anderen nicht.'),
('F6', 'R2', 'P18_merkmalswelle', ARRAY['2025-05', '2026-02'],
 'Wechseln viele Verhältnisse am selben Tag die Branche, zählen wir sie wie geliefert: im Mai 2025 in der Steiermark 491 von O nach C, im Februar 2026 in Wien 347 von G nach C.',
 'Ohne Antwort der Fachabteilung wäre jede Korrektur ein Eingriff in eine Entwicklung, die echt sein kann.'),
('F7', 'R1', 'R5_alter', NULL,
 'Steht im Geburtsdatum der Monat 13, gilt das Geburtsjahr, und als Geburtstag nehmen wir den 1. Juli an.',
 'So passen die Altersgruppen zum Beispielbericht. Antwortet die Fachabteilung anders, ändern wir nur einen Wert in der Regel.'),
('F8', 'R6', 'R5_alter', NULL,
 'Ein Alter über 110 Jahre halten wir für einen Fehler und führen es als „unbekannt“. Ein Alter von 75 bis 110 Jahren ist echt und zählt.',
 'Im Beispielbericht stehen diese Fälle unter „unbekannt“. Ab September 2024 gibt es echte Beschäftigte über 75, die sollen nicht verschwinden.'),
('F9', 'R9', 'P24_lieferumfang_fenster', ARRAY['2024-08'],
 'Die erste Lieferung (August 2024) enthält nicht alle Verhältnisse, die im August geendet haben. Der Stand am Stichtag stimmt, eine Zählung über den ganzen Monat liegt um rund 8.000 Verhältnisse zu niedrig.',
 'Ergänzen könnten wir nur aus einer späteren Lieferung, und das erlaubt die Laufregel nicht. Deshalb kennzeichnen wir die Monatszählung statt sie zu ändern.'),
('F10', NULL, 'R1_R3_verhaeltnis_einmal', NULL,
 'Hat ein Verhältnis mehrere Zeitabschnitte, gelten die Merkmale des Abschnitts mit dem spätesten Beginn. Lücken zwischen Abschnitten füllen wir nicht auf.',
 'Die jüngere Meldung ist die aktuellere. Eine feste Reihenfolge macht jeden Lauf wiederholbar, und gefüllte Lücken wären erfundene Beschäftigungstage.')
ON CONFLICT (nr) DO UPDATE
  SET rueckfrage = EXCLUDED.rueckfrage, regel_name = EXCLUDED.regel_name, lieferungen = EXCLUDED.lieferungen,
      satz = EXCLUDED.satz, begruendung = EXCLUDED.begruendung;
