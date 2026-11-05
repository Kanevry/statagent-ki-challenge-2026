-- Regelsatz v1: Einlese-, Zuordnungs- und Zählregeln nach der Fachbeschreibung, geeicht an
-- beispielbericht_2024-08.xlsx (2.880 Zellen Tab1–Tab13 exakt). Jeder Wert steht in `parameter`;
-- der Code (statagent/regeln.py) kennt nur die Arten. Neue Regeln kommen ohne Freigabe an:
-- `statagent regeln freigeben --regelsatz v1 --name "Vorname Nachname"` gibt sie mit Namen frei.
-- Idempotent: noch nicht freigegebene Entwürfe werden auf diesen Stand gebracht, freigegebene Regeln nie
-- (sie ändert nur ein Vorschlag mit Freigabe).

INSERT INTO meta.regel (regelsatz, name, typ, art, reihenfolge, parameter, beschreibung, begruendung, grundlage) VALUES

('v1', 'E01_spaltentausch_beginn_ende', 'einlese', 'spaltentausch', 10,
 '{"anteil_beginn_leer_min": 0.5, "anteil_beginn_nach_ende_min": 0.05}',
 'Sind in einer Lieferung mehr als die Hälfte der BEGINN-Felder leer und liegt BEGINN bei mehr als 5 % der Sätze nach ENDE, wurden die Spalten vertauscht geliefert. BEGINN und ENDE werden dann für die ganze Lieferung getauscht.',
 'Lieferung 2025-06: 388.115 von 432.086 BEGINN leer, 43.914 Sätze mit BEGINN > ENDE, ENDE immer gefüllt. Ohne Tausch bestünden am 30.06.2025 nur 21 Verhältnisse, nach dem Tausch 394.252 (Nachbarmonate 390.001 und 397.419). Kein Verhältnis geht verloren (Anhang A Nr. 1).',
 'Fachbeschreibung § 2 (Felder BEGINN/ENDE); Anhang A Nr. 1; Forensik Nr. 1; Rückfrage F3'),

('v1', 'E02_volldubletten', 'einlese', 'dublette', 20,
 '{"vergleich": "alle_felder"}',
 'Sätze, die in allen neun Feldern gleich sind, werden zu einem Satz verdichtet. Die Anzahl der verdichteten Zeilen bleibt erhalten und steht im Qualitätsbericht.',
 'Anhang A Nr. 1: kommt ein Satz mehrfach vor, zählt das Verhältnis einmal. Lieferung 2025-03 enthält 1.663 Volldubletten (sonst keine). Vergleich über alle Felder, weil mehrfach vorkommende VVH_IDs mit verschiedenen Merkmalen regelkonforme Zeitabschnitte sind (2025-03: 357 VVH_IDs, nie gleicher BEGINN).',
 'Anhang A Nr. 1; Fachbeschreibung § 2; Lead-Gegenrechnung § 7; Rückfrage R3'),

('v1', 'E03_datum_pruefen', 'einlese', 'datum', 30,
 '{"muster": "^[0-9]{4}-[0-9]{2}-[0-9]{2}$", "muster_monat_13": "^[0-9]{4}-13-[0-9]{2}$", "geburtsmonat_13": "geburtsjahr_behalten"}',
 'BEGINN, ENDE und GEBURTSDATUM werden nur als Datum übernommen, wenn sie dem Muster JJJJ-MM-TT entsprechen und ein gültiges Datum sind (Wörter wie „today“ oder „infinity“ gelten nicht, sonst wäre ein Lauf nicht reproduzierbar). Ein Geburtsdatum mit Monat 13 bleibt als Geburtsjahr erhalten (Status monat_13), andere ungültige Geburtsdaten gelten als unbekannt.',
 'Lieferungen enthalten 336–444 Geburtsdaten je Monat mit Monat 13 (z. B. 1963-13-09), in 2024-08 370 am Stichtag. Das Jahr ist plausibel und wird für Alter und Ministeriums-Lieferung gebraucht.',
 'Fachbeschreibung § 2 (Format JJJJ-MM-TT); Forensik Nr. 7; Rückfrage R1'),

('v1', 'E04_beginn_fehlt', 'einlese', 'ersatz_beginn', 40,
 '{"ersatz": "fensterbeginn", "fenster_monate": 3}',
 'Fehlt nach den vorigen Regeln ein gültiger BEGINN, wird der erste Tag des Lieferfensters (Berichtsmonat und zwei Vormonate) eingesetzt und der Satz als korrigiert markiert, damit kein Verhältnis verloren geht.',
 'Anhang A Nr. 1 (kein Verhältnis geht verloren). Die Lieferung ist ein Vollabzug über drei Monate (Fachbeschreibung § 2); ein Verhältnis ohne BEGINN bestand also spätestens seit Fensterbeginn. Nach Regel E01 bisher 0 Fälle.',
 'Fachbeschreibung § 2; Anhang A Nr. 1, 2'),

('v1', 'E06_ende_ungueltig', 'einlese', 'ersatz_ende', 45,
 '{"ersatz": "monatsletzter_sonst_laeuft"}',
 'Ein ENDE, das geliefert, aber kein gültiges Datum ist: Sind Jahr und Monat lesbar (z. B. 2024-02-30), gilt der Monatsletzte (2024-02-29); sonst wird das Verhältnis als „läuft“ übernommen. Der Satz ist als korrigiert markiert, kein Verhältnis geht verloren.',
 'Anhang A Nr. 1 (kein Verhältnis geht verloren) und Nr. 2 (jede Zuordnung festhalten). Ein Tippfehler im Tag lässt den Monat des Endes erkennen; ein unlesbares ENDE belegt kein Ende, das Verhältnis besteht laut Lieferung (Vollabzug). Gemessen 05.11.: 0 ungültige ENDE und 0 ungültige BEGINN in allen 24 Lieferungen (Review !13).',
 'Fachbeschreibung § 2 (ENDE leer = Verhältnis läuft); Anhang A Nr. 1, 2'),

('v1', 'E05_quellzuordnung', 'einlese', 'quellzuordnung', 50,
 '{"tabelle": "stat.quellzuordnung", "quelle": "zvd"}',
 'GESCHLECHT, QUAL, OENACE und BUNDESLAND werden über stat.quellzuordnung auf Klassifikationscodes geführt. Ein leeres oder unbekanntes Feld führt auf die Ausprägung „unbekannt“ des Merkmals; der Satz zählt.',
 'Fachbeschreibung § 3 (Klassifikationen enthalten „unbekannt“) und § 4 Nr. 8 (fehlende Angaben nach begründeten Annahmen, kein Verhältnis verloren); Anhang B (Quellzuordnung statt zweiter Klassifikation).',
 'Fachbeschreibung § 3, § 4 Nr. 8; Anhang B'),

('v1', 'E07_fortschreibung_lieferausfall', 'einlese', 'fortschreibung', 60,
 '{"quelle": "vorlieferung", "schwelle_anteil_verschwunden": 0.01, "merkmal_auspraegung": "qualifikation", "mindestens_vormonat": 100, "mindestens_basis": 1000}',
 'Fehlen in einer Lieferung belegt Verhältnisse, die im Vormonat bestanden (mehr als 1 % eines Vormonatsbestands von mindestens 1.000 Verhältnissen, oder eine Qualifikation mit über 100 Verhältnissen fällt ganz aus), werden die fehlenden Verhältnisse einmalig aus der Vorlieferung ergänzt, wenn dort ein am neuen Stichtag gültiger Abschnitt vorliegt. Ergänzte Abschnitte sind als fortgeschrieben markiert, der Monat bleibt vorläufig, bereits fortgeschriebene Abschnitte werden nie weitergetragen.',
 'Anhang A Nr. 1: kein Verhältnis geht verloren. Lieferung 2025-03 enthält keine freien Dienstverträge (1.492 FD-Verhältnisse vom 28.02. fehlen, alle wieder in 2025-04), Lieferung 2025-10 rund 20 % weniger Verhältnisse (78.949 vom 30.09. fehlen, 78.733 wieder in 2025-11). Einperiodige Fortschreibung der letzten gültigen Beobachtung ist gängige Praxis bei kurzfristigem Meldeausfall (Statistische Ämter des Bundes und der Länder, Beschäftigtenpanel, Metadatenreport § 2.5.3; Statistik Austria, Konjunkturindikatoren § 2.2.3). Nur frühere Lieferungen, keine Hochrechnung; spätere Lieferungen zeigen die Abweichung als Revisionsbedarf.',
 'Anhang A Nr. 1, 2; Fachbeschreibung § 4 Nr. 4 und 8; Rückfragen R4, R5'),

('v1', 'Q01_oenace_2003_unterabschnitte', 'zuordnung', 'quellzuordnung', 51,
 '{"merkmal": "oenace", "von_version": "2003", "codes": ["DA","DB","DC","DD","DE","DF","DG","DH","DI","DJ","DK","DL","DM","DN"], "ziel": "C"}',
 'ÖNACE-2003-Unterabschnitte DA bis DN (Sachgütererzeugung) werden dem Abschnitt C „Herstellung von Waren“ zugeordnet, in ÖNACE 2008 und 2025. D allein bleibt D (Energieversorgung).',
 'Jede Lieferung enthält rund 50 Sätze mit diesen Altcodes. Laut Umsteiger OENACE2003_OENACE2008 gehen die 6-Steller dieser Unterabschnitte mehrheitlich nach C (DA 49 von 49). Der Beispielbericht weist C = 62.204 = 62.154 Sätze mit C + 50 Sätze mit D[A-M] aus. Regel: jeder Unterabschnitt geht auf den Abschnitt, auf den die Mehrheit seiner 6-Steller führt; das gilt auch für DE (25 von 32 nach C, 6 nach J Verlagswesen, 1 nach R) und DN (48 von 61 nach C). DE und DN kommen in keiner der 24 Lieferungen vor (gemessen 05.11.), die Zuordnung ändert also heute keine Zahl.',
 'Fachbeschreibung § 4 Nr. 8; beispielbericht_2024-08.xlsx Tab3; Rückfrage F5'),

('v1', 'Q02_leer_unbekannt', 'zuordnung', 'quellzuordnung', 52,
 '{"geliefert": "<leer>"}',
 'Ein leeres Feld führt auf die Ausprägung „unbekannt“: OENACE → UNB „Wirtschaftszweig unbekannt“, BUNDESLAND → 0 „Bundesland unbekannt“.',
 'In jeder Lieferung fehlen OENACE und BUNDESLAND gemeinsam bei 1.587–2.192 Sätzen (2024-08: 1.996 am Stichtag). Der Beispielbericht zählt sie als „Bundesland unbekannt“ und „Wirtschaftszweig unbekannt“.',
 'Fachbeschreibung § 3, § 5 („unbekannte Werte als eigene Zeile“); beispielbericht_2024-08.xlsx Tab2, Tab3'),

('v1', 'Q03_sonst_unbekannt', 'zuordnung', 'quellzuordnung', 53,
 '{"geliefert": "<sonst>"}',
 'Ein Wert, der weder in der Klassifikation noch in einer Zuordnungsregel vorkommt, führt auf „unbekannt“. Der Satz zählt, die Prüfregel für unbekannte Codes meldet ihn.',
 'Kein Verhältnis geht verloren (Anhang A Nr. 1); ein neuer Code wird nicht geraten, sondern gemeldet und kann per Freigabe eine eigene Zuordnung bekommen.',
 'Anhang A Nr. 1, 2'),

('v1', 'R2_R4_stichtag_eigene_lieferung', 'zaehl', 'bestand', 10,
 '{"zeitraum_art": "Stichtag", "von": "monatsletzter", "bis": "monatsletzter", "lieferung": "eigene", "variable": "Beschaeftigungsverhaeltnisse"}',
 'Ein Verhältnis zählt im Berichtsmonat, wenn ein Zeitabschnitt am Stichtag (Monatsletzter) besteht: BEGINN ≤ Stichtag und ENDE leer oder ≥ Stichtag. Gerechnet wird aus der Lieferung des Berichtsmonats.',
 'Fachbeschreibung § 4 Nr. 1, 2, 4. 2024-08: 392.284 Sätze − 48 mit Ende vor dem 31.08. = 392.236 = Beispielbericht Tab1.',
 'Fachbeschreibung § 4 Nr. 1, 2, 4'),

('v1', 'R1_R3_verhaeltnis_einmal', 'zaehl', 'abschnittswahl', 20,
 '{"ordnung": "spaetester_beginn"}',
 'Bestehen für ein Verhältnis mehrere Abschnitte im Berichtszeitraum, gelten die Merkmale des Abschnitts mit dem spätesten BEGINN (bei Gleichstand: spätestes oder offenes ENDE, dann Codes aufsteigend). Jedes Verhältnis zählt einmal.',
 'Fachbeschreibung § 4 Nr. 3 (Merkmale aus dem Abschnitt am Stichtag); Abschnitte schließen lückenlos an, Überlappungen sind selten (0–4 je Lieferung, 0 am Stichtag). Vollständige Ordnung macht den Lauf deterministisch (Technische Regel 1).',
 'Fachbeschreibung § 4 Nr. 3; Anhang A Nr. 1; Technische Regel 1'),

('v1', 'R5_alter', 'zaehl', 'alter', 30,
 '{"bezug": "bis", "geburtsmonat_13": "ersatz:07-01", "max_plausibel": 110, "min_plausibel": 0}',
 'Alter in vollendeten Jahren am Ende des Berichtszeitraums (Stichtag). Bei Geburtsmonat 13 ist der Geburtstag unbekannt: Wir setzen den 1. Juli des Geburtsjahres ein (Jahresmitte) und rechnen das vollendete Alter. Ein Alter über 110 Jahre oder unter 0 gilt als unplausibel und wird als „unbekannt“ gezählt; das Verhältnis zählt.',
 'Ersatztag 1. Juli: Ist nur das Jahr bekannt, ist die Jahresmitte die beste Schätzung (Praxis z. B. NHS England, Person Birth Date); für 08/2024 trifft sie den Beispielbericht genau wie jeder Ersatztag im Jänner bis August (Tab13 576 von 576 Zellen). Grenze 110: großzügige eigene Prüfgrenze, kein amtlicher Standard (ILO empfiehlt keine obere Altersgrenze für Erwerbstätige); ab 09/2024 erscheinen echte 75- bis 77-Jährige (62 bis 310 je Monat), zwischen 78 und 116 Jahren gibt es keinen Fall, die 7 Fälle mit 117–153 Jahren sind unplausibel. Eine Grenze von 74 würde eine echte Entwicklung als Fehler korrigieren.',
 'Fachbeschreibung § 4 Nr. 5; Erläuterungen Beispielbericht; Rückfragen R1, R2'),

('v1', 'R7_oenace_nach_berichtsmonat', 'zaehl', 'klassifikationsversion', 40,
 '{"merkmal": "oenace", "nach": "berichtsmonat"}',
 'Der Wirtschaftszweig wird nach der ÖNACE-Version ausgewiesen, die im Berichtsmonat gilt (Gültigkeit in stat.klass_oenace): bis 12/2024 ÖNACE 2008, ab 01/2025 ÖNACE 2025.',
 'Fachbeschreibung § 3 und § 4 Nr. 7.',
 'Fachbeschreibung § 3, § 4 Nr. 7'),

('v1', 'R6_beschaeftigungskategorie', 'zaehl', 'dimension', 50,
 '{"qualifikation": "code"}',
 'Die Beschäftigungskategorie wird mit den fünf Qualifikationscodes ausgewiesen (ArbeiterDV, AngestellteDV, Beamte, ArbeiterFD, AngestellteFD).',
 'Fachbeschreibung § 4 Nr. 6.',
 'Fachbeschreibung § 4 Nr. 6')

ON CONFLICT (regelsatz, name) DO UPDATE
  SET typ = EXCLUDED.typ, art = EXCLUDED.art, reihenfolge = EXCLUDED.reihenfolge, parameter = EXCLUDED.parameter,
      beschreibung = EXCLUDED.beschreibung, begruendung = EXCLUDED.begruendung, grundlage = EXCLUDED.grundlage
  WHERE meta.regel.freigegeben_von IS NULL;  -- nur Entwürfe; freigegebene Regeln ändert nur eine Freigabe

-- Quellzuordnung (Anhang B). Identität für jeden Klassifikationscode, dazu Altcodes, leer und sonst.
INSERT INTO stat.quellzuordnung (quelle, merkmal, version, geliefert, klassifikation, code, regel_id)
SELECT 'zvd', 'geschlecht', '-', code, 'klass_geschlecht', code, NULL::int FROM klassifikation.geschlecht
UNION ALL
SELECT 'zvd', 'qualifikation', '-', code, 'klass_qualifikation', code, NULL::int FROM klassifikation.qualifikation
UNION ALL
SELECT 'zvd', 'bundesland', '-', code, 'klass_region', code, NULL::int FROM klassifikation.bundesland
UNION ALL
SELECT 'zvd', 'oenace', '2008', code, 'klass_oenace', code, NULL::int FROM klassifikation.oenace_2008
UNION ALL
SELECT 'zvd', 'oenace', '2025', code, 'klass_oenace', code, NULL::int FROM klassifikation.oenace_2025
ON CONFLICT DO NOTHING;

INSERT INTO stat.quellzuordnung (quelle, merkmal, version, geliefert, klassifikation, code, regel_id)
SELECT 'zvd', 'oenace', v.version, c.code, 'klass_oenace', 'C',
       (SELECT id FROM meta.regel WHERE regelsatz = 'v1' AND name = 'Q01_oenace_2003_unterabschnitte')
FROM (VALUES ('2008'), ('2025')) AS v (version),
     unnest(ARRAY['DA','DB','DC','DD','DE','DF','DG','DH','DI','DJ','DK','DL','DM','DN']) AS c (code)
ON CONFLICT DO NOTHING;

INSERT INTO stat.quellzuordnung (quelle, merkmal, version, geliefert, klassifikation, code, regel_id)
SELECT 'zvd', m.merkmal, m.version, g.geliefert, m.klassifikation, m.code,
       (SELECT id FROM meta.regel WHERE regelsatz = 'v1'
          AND name = CASE g.geliefert WHEN '<leer>' THEN 'Q02_leer_unbekannt' ELSE 'Q03_sonst_unbekannt' END)
FROM (VALUES
        ('geschlecht', '-', 'klass_geschlecht', 'U'),
        ('qualifikation', '-', 'klass_qualifikation', 'UNB'),
        ('bundesland', '-', 'klass_region', '0'),
        ('oenace', '2008', 'klass_oenace', 'UNB'),
        ('oenace', '2025', 'klass_oenace', 'UNB')
     ) AS m (merkmal, version, klassifikation, code),
     (VALUES ('<leer>'), ('<sonst>')) AS g (geliefert)
ON CONFLICT DO NOTHING;
