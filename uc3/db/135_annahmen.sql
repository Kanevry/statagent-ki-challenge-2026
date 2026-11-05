-- Annahmen F1 bis F10: was wir bis zur Antwort der Fachabteilung annehmen, in einem Satz für den
-- Qualitätsbericht und die Weboberfläche. `rueckfrage` verweist auf meta.rueckfrage (R1 bis R10),
-- `regel_name` auf die Regel, die die Annahme umsetzt, `lieferungen` auf die Monate, für die der Satz
-- gilt (NULL = alle). `grund` ist die Begründung in einem Satz; `annahmen()` hängt sie als „Grund: …“ an den Satz,
-- `begruendung` ist die ausführliche Fassung. Annahmen ändern keine Zahl und gehören nicht zum Regelstand.
-- Idempotent: ein erneutes Einspielen übernimmt alle Texte.

CREATE TABLE IF NOT EXISTS meta.annahme (
  nr          text PRIMARY KEY CHECK (nr ~ '^F\d+$'),
  rueckfrage  text,
  regel_name  text,
  lieferungen text[],
  satz        text NOT NULL,
  begruendung text NOT NULL
);

ALTER TABLE meta.annahme ADD COLUMN IF NOT EXISTS grund text;

INSERT INTO meta.annahme (nr, rueckfrage, regel_name, lieferungen, satz, begruendung, grund) VALUES
('F1', 'R3', 'E07_fortschreibung_lieferausfall', ARRAY['2025-10'],
 'Für Oktober 2025 fehlen rund 79.000 Verhältnisse. Wir übernehmen sie einmal aus der September-Lieferung und lassen den Monat vorläufig, bis die Fachabteilung antwortet.',
 'So geht kein Verhältnis verloren, und wir nutzen nur eine frühere Lieferung. Die November-Lieferung zeigt später, wie weit die Übernahme danebenlag.',
 'So geht kein Verhältnis verloren, und wir nutzen nur eine frühere Lieferung.'),
('F2', 'R4', 'E07_fortschreibung_lieferausfall', ARRAY['2025-03'],
 'Im März 2025 fehlen alle freien Dienstverträge. Wir übernehmen sie aus der Februar-Lieferung und lassen den Monat vorläufig, bis die Fachabteilung antwortet.',
 'Eine ganze Gruppe verschwindet nicht für einen Monat. Die April-Lieferung enthält alle 1.492 freien Dienstverträge wieder.',
 'Eine ganze Gruppe verschwindet nicht für einen Monat, und die April-Lieferung enthält alle 1.492 freien Dienstverträge wieder.'),
('F3', 'R5', 'E01_spaltentausch_beginn_ende', ARRAY['2025-06'],
 'Im Juni 2025 sind Beginn und Ende vertauscht geliefert. Wir tauschen beide Felder für alle 432.086 Sätze zurück.',
 'Ohne Tausch blieben am Stichtag nur 21 Verhältnisse übrig, mit Tausch passt der Monat zu den Nachbarmonaten.',
 'Nur mit dem Tausch bleiben alle Verhältnisse erhalten, ohne ihn bestünden am Stichtag nur 21.'),
('F4', 'R8', 'P19_phantom_doppelmeldung', NULL,
 'Kurze Zweitmeldungen derselben Person zählen als eigenes Beschäftigungsverhältnis. Wir kennzeichnen sie, bis die Fachabteilung antwortet.',
 'Die Statistik zählt Beschäftigungsverhältnisse, nicht Personen. So geht nichts verloren, und die Fälle bleiben sichtbar.',
 'Gezählt werden Verhältnisse und nicht Personen, und auch der Beispielbericht zählt diese Fälle mit.'),
('F5', NULL, 'Q01_oenace_2003_unterabschnitte', NULL,
 'Alte Branchencodes aus ÖNACE 2003 (DA bis DN) zählen zur Herstellung von Waren (Abschnitt C), in den Tabellen und in der Lieferung an das Ministerium gleich.',
 'Der Beispielbericht des Veranstalters zählt sie ebenso zu C. Dieselbe Person soll nicht an einer Stelle zu C zählen und an der anderen nicht.',
 'Der Beispielbericht zählt diese Codes ebenso zu C, und dieselbe Person soll überall gleich zählen.'),
('F6', 'R2', 'P18_merkmalswelle', ARRAY['2025-05', '2026-02'],
 'Wechseln viele Verhältnisse am selben Tag die Branche, zählen wir sie wie geliefert: im Mai 2025 in der Steiermark 491 von O nach C, im Februar 2026 in Wien 347 von G nach C.',
 'Ohne Antwort der Fachabteilung wäre jede Korrektur ein Eingriff in eine Entwicklung, die echt sein kann.',
 'Ohne Antwort der Fachabteilung wäre jede Korrektur ein Eingriff in eine Entwicklung, die echt sein kann.'),
('F7', 'R1', 'R5_alter', NULL,
 'Steht im Geburtsdatum der Monat 13, gilt das Geburtsjahr, und als Geburtstag nehmen wir den 1. Juli an.',
 'So passen die Altersgruppen zum Beispielbericht. Antwortet die Fachabteilung anders, ändern wir nur einen Wert in der Regel.',
 'Die Jahresmitte ist die beste Schätzung, wenn nur das Jahr bekannt ist, und trifft den Beispielbericht für August 2024 genau.'),
('F8', 'R6', 'R5_alter', NULL,
 'Ein Alter über 110 Jahre halten wir für einen Fehler und führen es als „unbekannt“. Ein Alter von 75 bis 110 Jahren ist echt und zählt.',
 'Im Beispielbericht stehen diese Fälle unter „unbekannt“. Ab September 2024 gibt es echte Beschäftigte über 75, die sollen nicht verschwinden.',
 'Der Beispielbericht führt diese Fälle unter „unbekannt“, und echte Beschäftigte über 75 sollen nicht verschwinden.'),
('F9', 'R9', 'P24_lieferumfang_fenster', ARRAY['2024-08'],
 'Die erste Lieferung (August 2024) ist kein Vollabzug: Sie enthält nur 48 Verhältnisse, die im August vor dem Monatsletzten enden, die anderen Lieferungen je 6.614 bis 17.664. Deshalb bringt die Zählung über den ganzen Monat im August 2024 nur 48 Verhältnisse mehr als der Stichtag (September 2024: 7.746 mehr); wie viele Verhältnisse im August fehlen, ist nicht gemessen.',
 'Ergänzen könnten wir nur aus einer späteren Lieferung, und das erlaubt die Laufregel nicht. Deshalb kennzeichnen wir die Monatszählung statt sie zu ändern.',
 'Ergänzen könnten wir nur aus einer späteren Lieferung, und das erlaubt die Laufregel nicht.'),
('F10', NULL, 'R1_R3_verhaeltnis_einmal', NULL,
 'Hat ein Verhältnis mehrere Zeitabschnitte, gelten die Merkmale des Abschnitts mit dem spätesten Beginn. Lücken zwischen Abschnitten füllen wir nicht auf.',
 'Die jüngere Meldung ist die aktuellere. Eine feste Reihenfolge macht jeden Lauf wiederholbar, und gefüllte Lücken wären erfundene Beschäftigungstage.',
 'Die jüngere Meldung ist die aktuellere, und gefüllte Lücken wären erfundene Beschäftigungstage.')
ON CONFLICT (nr) DO UPDATE
  SET rueckfrage = EXCLUDED.rueckfrage, regel_name = EXCLUDED.regel_name, lieferungen = EXCLUDED.lieferungen,
      satz = EXCLUDED.satz, begruendung = EXCLUDED.begruendung, grund = EXCLUDED.grund;
