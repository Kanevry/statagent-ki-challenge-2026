-- Regelsatz v1: Prüfkatalog P01–P24 (Qualitätssicherung, Qualitätsbericht § 2). Prüfregeln ändern keine
-- Zahl; sie melden je Lauf einen Treffer in meta.pruefung_treffer (auch anzahl 0) und können den Monat
-- anhalten (bleibt vorläufig). Der Code (statagent/pruefungen.py) kennt nur die Arten; Schwellen, Codes,
-- Einstufung, Maßnahme und Anhalten stehen hier in `parameter`. Einlese- und Zählregeln werden über ihren
-- Namen referenziert ("regel"), nie über die ID.
-- Einstufung je Ergebnisfall: "einstufung" gilt für einen Treffer, "einstufung_<fall>" für andere Fälle
-- (ohne, nicht_anwendbar, saison, klassifikationswechsel, unter_schwelle). Ohne Eintrag bleibt sie leer.
-- Idempotent: bestehende Regeln werden nie überschrieben (Änderungen nur über neue Regelzeilen).

INSERT INTO meta.regel (regelsatz, name, typ, art, reihenfolge, parameter, beschreibung, begruendung, grundlage) VALUES

('v1', 'P01_volldubletten', 'pruefung', 'volldubletten', 1,
 '{"ebene": "satz", "regel": "E02_volldubletten", "einstufung": "erklaert-datenproblem", "massnahme": "zu einem Satz verdichtet (E02), Verhältnis zählt einmal", "anhalten": false}',
 'Zeilen, die in allen neun Feldern einer anderen Zeile gleichen und zu einem Satz verdichtet wurden (Summe roh_zeilen − 1).',
 'Lieferung 2025-03 enthält 1.663 Volldubletten, alle anderen Lieferungen keine. Kommt ein Satz mehrfach vor, zählt das Verhältnis einmal (Anhang A Nr. 1).',
 'Anhang A Nr. 1; Regel E02; Rückfrage R7'),

('v1', 'P02_mehrere_abschnitte_im_zeitraum', 'pruefung', 'mehrere_abschnitte', 2,
 '{"ebene": "satz", "regel": "R1_R3_verhaeltnis_einmal", "einstufung": "erklaert-datenproblem", "massnahme": "Merkmale aus dem Abschnitt mit spätestem Beginn (R1_R3), Verhältnis zählt einmal", "anhalten": false}',
 'Verhältnisse mit mehr als einem Abschnitt am Stichtag nach der Verdichtung (vor der Abschnittswahl). Verglichen werden alle Felder; aufeinanderfolgende Zeitabschnitte sind kein Treffer.',
 'Abschnitte eines Verhältnisses schließen lückenlos an. 2025-03 hat 357 VVH_IDs mit mehreren Zeilen, das sind echte Zeitabschnitte; nach der Verdichtung bleibt am Stichtag 0. Ein Treffer hieße überlappende Abschnitte.',
 'Fachbeschreibung § 4 Nr. 3; Regel R1_R3'),

('v1', 'P03_spaltentausch', 'pruefung', 'korrektur', 3,
 '{"ebene": "lieferung", "regel": "E01_spaltentausch_beginn_ende", "bezug": "lieferung", "einstufung": "erklaert-datenproblem", "massnahme": "BEGINN und ENDE für die ganze Lieferung getauscht (E01)", "anhalten": false}',
 'Sätze, bei denen die Einleseregel E01 BEGINN und ENDE getauscht hat.',
 'Lieferung 2025-06: BEGINN mehrheitlich leer, ENDE immer gefüllt; ohne Tausch bestünden am Stichtag 21 Verhältnisse, mit Tausch 394.252. Betroffen sind alle 432.086 Sätze, sonst keine Lieferung.',
 'Anhang A Nr. 1; Regel E01; Rückfrage R5'),

('v1', 'P04_geburtsdatum_monat_13', 'pruefung', 'geburtsdatum_status', 4,
 '{"ebene": "satz", "status": "monat_13", "einstufung": "erklaert-datenproblem", "massnahme": "Geburtstag unbekannt: 1. Juli des Geburtsjahres als Ersatztag (R5 ersatz:07-01), Alter in vollendeten Jahren am Stichtag (E03, R5)", "anhalten": false, "rueckfrage": "R1"}',
 'Verhältnisse am Stichtag mit Geburtsdatum im Monat 13 (z. B. 1963-13-09).',
 '336–444 Fälle je Lieferung, in 2024-08 370 am Stichtag. Das Jahr ist plausibel, der Tag fehlt. Mit dem Ersatztag 1. Juli (R5) trifft das Alter für 08/2024 den Beispielbericht (Tab13 576 von 576 Zellen).',
 'Fachbeschreibung § 2; Regel E03; Rückfrage R1'),

('v1', 'P05_geburtsdatum_ungueltig', 'pruefung', 'geburtsdatum_status', 5,
 '{"ebene": "satz", "status": "ungueltig", "einstufung": "erklaert-datenproblem", "massnahme": "Alter unbekannt (-1), Verhältnis zählt", "anhalten": false}',
 'Verhältnisse am Stichtag mit fehlendem oder ungültigem Geburtsdatum (nicht Monat 13).',
 'Kein Verhältnis geht verloren (Anhang A Nr. 1); ohne gültiges Datum ist das Alter unbekannt.',
 'Fachbeschreibung § 2, § 4 Nr. 5; Regel E03'),

('v1', 'P06_alter_unplausibel', 'pruefung', 'alter_bereich', 6,
 '{"ebene": "satz", "regel": "R5_alter", "bereich": "unplausibel", "einstufung": "erklaert-datenproblem", "massnahme": "Alter unbekannt (-1), Verhältnis zählt", "anhalten": false, "rueckfrage": "R6"}',
 'Verhältnisse am Stichtag, deren Alter außerhalb der Plausibilitätsgrenzen der Zählregel R5_alter liegt (über max_plausibel oder unter min_plausibel).',
 '2024-08: 7 Fälle mit 117–153 Jahren, der Beispielbericht weist sie unter „unbekannt“ aus. Zwischen 78 und 116 Jahren gibt es keinen Fall.',
 'Fachbeschreibung § 4 Nr. 5; Regel R5_alter; Rückfrage R6'),

('v1', 'P07_alter_hoch_plausibel', 'pruefung', 'alter_bereich', 7,
 '{"ebene": "satz", "regel": "R5_alter", "bereich": "hoch", "ab": 75, "einstufung": "erklaert-plausibel", "massnahme": "gezählt, Zeile 75 u. mehr", "anhalten": false}',
 'Verhältnisse am Stichtag mit einem Alter von 75 Jahren bis zur Plausibilitätsgrenze von R5_alter. Echte Entwicklung, keine Korrektur.',
 '2024-08: 0, ab 2024-09 62 und bis 2026-07 310 Fälle (Jahrgänge 1948–1951 altern in die Gruppe). Eine Grenze bei 74 würde eine echte Entwicklung als Fehler korrigieren.',
 'Fachbeschreibung § 4 Nr. 5; Regel R5_alter; Beispielbericht Tab13'),

('v1', 'P08_beginn_ersetzt', 'pruefung', 'korrektur', 8,
 '{"ebene": "satz", "regel": ["E04_beginn_fehlt", "E06_ende_ungueltig"], "bezug": "lieferung", "einstufung": "erklaert-datenproblem", "massnahme": "BEGINN fehlt: erster Tag des Lieferfensters (E04); ENDE ungültig: Monatsletzter bei lesbarem Monat, sonst offen (E06); Verhältnis zählt", "anhalten": false}',
 'Sätze, bei denen eine Einleseregel BEGINN (E04) oder ENDE (E06) ersetzt hat, weil der gelieferte Wert kein gültiges Datum war.',
 'Kein Verhältnis geht verloren (Anhang A Nr. 1). E04: nach Regel E01 bisher 0 Fälle. E06: ein ENDE, das kein gültiges Datum ist, wird nicht als beendet gewertet (Monatsletzter bei lesbarem Monat, sonst offen); die Zahl je Monat steht im Qualitätsbericht (Review !13 Runde 3 Punkt 11).',
 'Fachbeschreibung § 2; Anhang A Nr. 1; Regel E04; Regel E06'),

('v1', 'P09_beginn_nach_ende', 'pruefung', 'beginn_nach_ende', 9,
 '{"ebene": "satz", "einstufung": "nicht-erklaerbar", "massnahme": "Satz zählt nach Stichtagsregel nicht; an die Fachabteilung", "anhalten": false}',
 'Abschnitte, deren BEGINN nach dem ENDE liegt (nach allen Einleseregeln).',
 'Nach dem Spaltentausch (E01) dürfte es keine solchen Abschnitte geben; ein Treffer ist ein Datenfehler ohne bekannte Ursache.',
 'Fachbeschreibung § 2; Anhang A Nr. 1'),

('v1', 'P10_merkmal_leer', 'pruefung', 'korrektur', 10,
 '{"ebene": "satz", "regel": "Q02_leer_unbekannt", "bezug": "stichtag", "einstufung": "erklaert-datenproblem", "massnahme": "unbekannt (UNB bzw. 0), Satz zählt", "anhalten": false}',
 'Verhältnisse am Stichtag, bei denen ein Merkmal (in den Lieferungen OENACE und BUNDESLAND) leer geliefert und auf „unbekannt“ geführt wurde.',
 'In jeder Lieferung fehlen OENACE und BUNDESLAND gemeinsam bei 1.587–2.192 Sätzen (2024-08: 1.996 am Stichtag). Der Beispielbericht zählt sie als unbekannt.',
 'Fachbeschreibung § 3, § 5; Regel Q02'),

('v1', 'P11_oenace_altcode_2003', 'pruefung', 'korrektur', 11,
 '{"ebene": "satz", "regel": "Q01_oenace_2003_unterabschnitte", "bezug": "stichtag", "einstufung": "erklaert-datenproblem", "massnahme": "→ C (Umsteiger ÖNACE 2003 → 2008)", "anhalten": false}',
 'Verhältnisse am Stichtag mit einem ÖNACE-2003-Unterabschnitt (DA–DN), der nach C geführt wurde.',
 'Rund 50 Sätze je Lieferung (2024-08: 50). Beispielbericht C = 62.154 + 50.',
 'Fachbeschreibung § 4 Nr. 8; Regel Q01'),

('v1', 'P12_code_unbekannt', 'pruefung', 'korrektur', 12,
 '{"ebene": "satz", "regel": "Q03_sonst_unbekannt", "bezug": "stichtag", "einstufung": "nicht-erklaerbar", "massnahme": "unbekannt, Satz zählt; Code an die Fachabteilung", "anhalten": false, "rueckfrage": "neu"}',
 'Verhältnisse am Stichtag mit einem gelieferten Code, der weder in der Klassifikation noch in einer Zuordnungsregel steht.',
 'Ein neuer Code wird nicht geraten, sondern gemeldet. Bisher 0 Fälle.',
 'Anhang A Nr. 1, 2; Regel Q03'),

('v1', 'P13_auspraegung_verschwunden', 'pruefung', 'auspraegung_verschwunden', 13,
 '{"ebene": "aggregat", "gliederungen": ["qualifikation", "region", "oenace"], "schwelle": 100, "nur_geliefert": true, "einstufung": "erklaert-datenproblem", "massnahme": "Monat angehalten; Rückfrage an die Fachabteilung", "anhalten": true, "rueckfrage": "R4"}',
 'Eine Ausprägung (Qualifikation, Bundesland, ÖNACE bei gleicher Version), die im Vormonat mehr als 100 Verhältnisse hatte, hat am Stichtag 0.',
 'Lieferung 2025-03 enthält keinen freien Dienstvertrag (ArbeiterFD, AngestellteFD), am 28.02. waren es 1.492. Ein ganzer Merkmalswert verschwindet nicht von einem Monat auf den anderen.',
 'Fachbeschreibung § 4 Nr. 6; Rückfrage R4'),

('v1', 'P14_sprung_aggregat', 'pruefung', 'sprung_aggregat', 14,
 '{"ebene": "aggregat", "gliederungen": ["qualifikation", "region", "oenace", "geschlecht"], "schwelle_prozent": 3, "n_min": 500, "saison": {"oenace": ["A", "F", "I"], "region": ["5", "7", "8"]}, "einstufung": "nicht-erklaerbar", "einstufung_saison": "erklaert-plausibel", "einstufung_klassifikationswechsel": "erklaert-plausibel", "massnahme": "an die Fachabteilung", "massnahme_saison": "keine (Saison: Land- und Forstwirtschaft, Bau, Beherbergung und Gastronomie; Salzburg, Tirol, Vorarlberg)", "massnahme_klassifikationswechsel": "ÖNACE nicht verglichen (Versionswechsel)", "anhalten": false}',
 'Ausprägungen mit mindestens 500 Verhältnissen im Vormonat, die sich um mehr als 3 % verändern. ÖNACE nur bei gleicher Version. Saisonbranchen und -länder gelten als echte Entwicklung, alles andere geht an die Fachabteilung. Anzahl = Zellen.',
 'Der Bestand ändert sich üblicherweise um weniger als 1 % je Monat. Saisonbetriebe schwanken stärker; 01/2025 wechselt ÖNACE 2008 → 2025, dann ist ein Vergleich nicht sinnvoll.',
 'Fachbeschreibung § 3, § 4 Nr. 7; Qualitätsbericht § 2'),

('v1', 'P15_bestand_vs_vormonat', 'pruefung', 'bestand_vs_vormonat', 15,
 '{"ebene": "lieferung", "schwelle": 0.05, "vergleich": "letzter_nicht_angehaltener", "einstufung": "erklaert-datenproblem", "massnahme": "Monat angehalten; Lieferung prüfen lassen", "anhalten": true, "rueckfrage": "R3"}',
 'Der Bestand am Stichtag fällt um mehr als 5 % unter den Bestand des Vormonats. War der Vormonat selbst angehalten (Teil-Lieferung), wird mit dem letzten nicht angehaltenen Monat verglichen.',
 'Monatliche Änderungen liegen unter 1,5 %. 2025-10: 313.154 gegen 394.200 (−20,6 %), weil rund 79.000 Verhältnisse in der Lieferung fehlen.',
 'Fachbeschreibung § 2; Rückfrage R3'),

('v1', 'P16_verhaeltnisse_verschwunden', 'pruefung', 'verhaeltnisse_verschwunden', 16,
 '{"ebene": "lieferung", "schwelle": 0.01, "einstufung": "erklaert-datenproblem", "einstufung_unter_schwelle": "erklaert-plausibel", "massnahme": "Monat angehalten; Nachlieferung anfordern", "massnahme_unter_schwelle": "keine (Einzelfälle, z. B. Stornos)", "anhalten": true, "rueckfrage": "R3"}',
 'Verhältnisse, die laut Vormonats-Lieferung am Vormonats-Stichtag bestanden, aber in der aktuellen Lieferung gar nicht vorkommen. Über 1 % des Vormonatsbestands hält den Monat an.',
 'Die Lieferung ist ein Vollabzug über drei Monate; ein Verhältnis, das am Vormonats-Stichtag bestand, muss wieder vorkommen (mit Ende oder ohne). Normal sind rund 200 Fälle, 2025-10 sind es 78.949.',
 'Fachbeschreibung § 2; Rückfrage R3'),

('v1', 'P17_zeilenzahl_vs_vormonat', 'pruefung', 'zeilenzahl_vs_vormonat', 17,
 '{"ebene": "lieferung", "untergrenze": 0.9, "obergrenze": 1.1, "vergleich": "letzter_nicht_angehaltener", "einstufung": "erklaert-datenproblem", "massnahme": "Monat angehalten; Lieferumfang prüfen lassen", "anhalten": true, "rueckfrage": "R3"}',
 'Die Zeilenzahl der Lieferung liegt außerhalb von 90 % bis 110 % der Zeilenzahl der Vormonats-Lieferung. War der Vormonat selbst angehalten, gilt der letzte nicht angehaltene Monat als Vergleich (sonst hielte die Erholung nach einer Teil-Lieferung, etwa 2025-11, ebenfalls an).',
 'Lieferungen haben 392.284 bis 438.181 Zeilen und ändern sich um weniger als 4 % je Monat. 2025-10: 345.078 gegen 434.104.',
 'Fachbeschreibung § 2; Rückfrage R3'),

('v1', 'P18_merkmalswelle', 'pruefung', 'merkmalswelle', 18,
 '{"ebene": "satz", "merkmale": ["oenace", "bundesland"], "schwelle": 100, "beginn_im_berichtsmonat": true, "einstufung": "nicht-erklaerbar", "massnahme": "gezählt wie geliefert; Rückfrage an die Fachabteilung", "anhalten": false, "rueckfrage": "R2"}',
 'Mehr als 100 Verhältnisse, deren neuer Abschnitt im Berichtsmonat am selben Tag denselben Codewechsel X → Y hat (ÖNACE oder Bundesland, aufeinanderfolgende Abschnitte eines Verhältnisses).',
 'Einzelne Wechsel sind normal, eine Welle gleicher Wechsel am selben Tag nicht: 2025-05 Steiermark O → C (491 am 01.05.), 2026-02 Wien G → C (347 am 01.02.). Ob Umstrukturierung oder Codierfehler, kann nur die Fachabteilung sagen.',
 'Fachbeschreibung § 4 Nr. 3; Qualitätsbericht § 2'),

('v1', 'P19_phantom_doppelmeldung', 'pruefung', 'phantom_doppelmeldung', 19,
 '{"ebene": "satz", "einstufung": "nicht-erklaerbar", "massnahme": "gekennzeichnet, gezählt (Zählregel 1: Verhältnisse, nicht Personen); Rückfrage an die Fachabteilung", "anhalten": false, "rueckfrage": "R8"}',
 'Verhältnisse mit Beginn im Berichtsmonat, deren Person am Stichtag ein zweites Verhältnis mit gleicher Qualifikation, ÖNACE und gleichem Bundesland hat.',
 'Gezählt werden Verhältnisse, nicht Personen (Fachbeschreibung § 4 Nr. 1); der Beispielbericht zählt solche Fälle mit. Die Kennzeichnung zeigt, dass mögliche Doppelmeldungen gesehen wurden.',
 'Fachbeschreibung § 4 Nr. 1; Beispielbericht 2024-08'),

('v1', 'P20_person_inkonsistent', 'pruefung', 'person_inkonsistent', 20,
 '{"ebene": "satz", "einstufung": "nicht-erklaerbar", "massnahme": "Verhältnisse zählen mit eigenen Merkmalen; an die Fachabteilung", "anhalten": false}',
 'Personen (PERSON_ID) mit mehr als einem Geburtsdatum oder Geschlecht in derselben Lieferung. Anzahl = Personen, Beispiele = VVH_IDs.',
 'Geburtsdatum und Geschlecht sind Merkmale der Person; Widersprüche deuten auf eine falsche Zuordnung von PERSON_ID. Bisher 0.',
 'Fachbeschreibung § 2'),

('v1', 'P21_blattsummen', 'pruefung', 'blattsummen', 21,
 '{"ebene": "aggregat", "gliederungen": {"region": {"tabelle": "stat.klass_region"}, "oenace": {"tabelle": "stat.klass_oenace", "version": true}, "geschlecht": {"tabelle": "stat.klass_geschlecht"}, "qualifikation": {"tabelle": "stat.klass_qualifikation"}, "alter": {"tabelle": "stat.klass_alter"}}, "einstufung": "nicht-erklaerbar", "massnahme": "harter Stopp: Monat angehalten, Zählung prüfen", "anhalten": true}',
 'Je Gliederung (Bundesland, ÖNACE, Geschlecht, Qualifikation, Alter) ist die Summe über die Codes der Klassifikation gleich dem Gesamtbestand. Eine Abweichung heißt, eine Zelle trägt einen Code außerhalb der Klassifikation.',
 'Jede Tabelle des Berichts summiert auf denselben Gesamtbestand (Beispielbericht Tab1–Tab13).',
 'Fachbeschreibung § 5; Anhang B'),

('v1', 'P22_abrechnung', 'pruefung', 'abrechnung', 22,
 '{"ebene": "lieferung", "einstufung": "nicht-erklaerbar", "massnahme": "harter Stopp: Monat angehalten, Bereinigung prüfen", "anhalten": true}',
 'Gelesene Zeilen = gezählte Verhältnisse + nicht gezählte Abschnitte + als Volldublette verdichtete Zeilen.',
 'Kein Satz geht verloren (Anhang A Nr. 1); 2024-08: 392.284 = 392.236 + 48 + 0.',
 'Anhang A Nr. 1; Qualitätsbericht § 1'),

('v1', 'P23_revision_vormonat', 'pruefung', 'revision_vormonat', 23,
 '{"ebene": "lieferung", "gliederung": "insgesamt", "schwelle": 0.0025, "einstufung": "nicht-erklaerbar", "einstufung_unter_schwelle": "erklaert-plausibel", "massnahme": "Revisionsbedarf an die Fachabteilung", "massnahme_unter_schwelle": "Revisionsbedarf im Bericht (Nachmeldungen, rückwirkende Abmeldungen); Veröffentlichtes bleibt", "anhalten": false, "rueckfrage": "neu"}',
 'Revisionsbedarf der Vormonate laut meta.revision: weicht der Bestand insgesamt um mehr als 0,25 % vom veröffentlichten Wert ab, geht es an die Fachabteilung, sonst gilt es als Nachmeldung bzw. rückwirkende Abmeldung.',
 'Veröffentlichte Monate bleiben unverändert, Abweichungen stehen als Revisionsbedarf im Bericht (Fachbeschreibung § 4 Nr. 4). Kleine Abweichungen sind durch Nachmeldungen üblich.',
 'Fachbeschreibung § 4 Nr. 4; Technische Regel 7'),

('v1', 'P24_lieferumfang_fenster', 'pruefung', 'lieferumfang_fenster', 24,
 '{"ebene": "lieferung", "fenster_vormonate": 2, "schwelle": 0.01, "einstufung": "erklaert-datenproblem", "massnahme": "keine (kein Vollabzug über drei Monate, z. B. Erstlieferung); Rückfrage an die Fachabteilung", "anhalten": false, "rueckfrage": "R9"}',
 'Die Lieferung soll ein Vollabzug über drei Monate sein und damit Abschnitte enthalten, die in den zwei Vormonaten endeten. Liegt deren Anteil unter 1 %, wird ein fehlender Vollabzug gemeldet.',
 'Gemessen 2024-09 bis 2026-07: 1,6 % (zweite Lieferung, Fenster erst einen Monat gefüllt) bis 7,5 % der Abschnitte enden im Fenster. 2024-08 enthält kein Ende vor dem 01.08.2024 (0,0 %): Erstlieferung, kein Vollabzug.',
 'Fachbeschreibung § 2')

ON CONFLICT (regelsatz, name) DO UPDATE
  SET typ = EXCLUDED.typ, art = EXCLUDED.art, reihenfolge = EXCLUDED.reihenfolge, parameter = EXCLUDED.parameter,
      beschreibung = EXCLUDED.beschreibung, begruendung = EXCLUDED.begruendung, grundlage = EXCLUDED.grundlage
  WHERE meta.regel.freigegeben_von IS NULL;  -- nur Entwürfe
