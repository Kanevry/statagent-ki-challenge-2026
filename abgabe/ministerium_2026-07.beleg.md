# Ministeriums-Lieferung 2026-07 (Auftrag 3)

Die Lieferung enthält Einzeldaten (PERSON_ID) und liegt deshalb nicht im Repo. Sie wird über den
SV-Box-Teamordner (Ergebnisdateien) abgegeben. Dieser Beleg ordnet die Datei der Rechnung zu.

| Angabe | Wert |
| --- | --- |
| Datei | `ministerium_2026-07.csv` |
| sha256 | `d8492f46dd5f21fcd391e82d3eb671d437e46de2bda96f4237fd1d5972e86379` |
| Zeilen | 32741 Personen und 1 Kopfzeile |
| Zeitraum | 01.08.2025 bis 31.07.2026 |
| Definition | Regel `M01_personentage_ministerium` im Regelsatz `ministerium` (meta.regel 663) |
| Parameter | `{"altcodes_als_abschnitt": ["DA", "DB", "DC", "DD", "DE", "DF", "DG", "DH", "DI", "DJ", "DK", "DL", "DM", "DN"], "angehaltene_lieferungen": "ueberspringen", "bereinigung_regelsatz": "v1", "datei": "ministerium_{berichtsmonat}.csv", "datenstand": "juengste_lieferung_je_tag", "felder": ["PERSON_ID", "GESCHLECHT", "GEBURTSJAHR", "TAGE"], "geburtsjahr_unplausibel": "Unbekannt", "mindesttage": 200, "monate": 12, "oenace": "C", "qualifikationen": ["ArbeiterDV", "ArbeiterFD"], "trennzeichen": ";"}` |
| Datenstand je Monat | 2025-08 aus Lieferung 2025-09 (übersprungen: 2025-10); 2025-09 aus Lieferung 2025-11; 2025-10 aus Lieferung 2025-12; 2025-11 aus Lieferung 2026-01; 2025-12 aus Lieferung 2026-02; 2026-01 aus Lieferung 2026-03; 2026-02 aus Lieferung 2026-04; 2026-03 aus Lieferung 2026-05; 2026-04 aus Lieferung 2026-06; 2026-05 aus Lieferung 2026-07; 2026-06 aus Lieferung 2026-07; 2026-07 aus Lieferung 2026-07 |
| Erzeugt mit | `uv run uc3 ministerium --monat 2026-07 --name "Bernhard Götzendorfer"` |
| Freigegeben von | Bernhard Götzendorfer (Commit-Trailer Freigegeben-von, meta.freigabe) |
| Abgabeweg | SV-Box-Teamordner, Ergebnisdateien (nicht im öffentlichen Repo) |
