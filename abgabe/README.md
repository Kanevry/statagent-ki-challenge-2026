# Abgabe UC3 StatAgent

Alle Dateien hier erzeugt das Programm aus der Datenbank `statistik`. Kein Sprachmodell rechnet eine Zahl. Zwei
Läufe mit denselben Daten und Regeln liefern dieselben Dateien. Prüfen: `cd uc3 && uv run uc3 pruefe-abgabe --mit-db`.

| Datei | Inhalt | Erzeugt mit |
|---|---|---|
| `aggregationen_v1.xlsx` | Aggregations-Sheet nach Vorlage, 24 Berichtsmonate 2024-08 bis 2026-07, Regelsatz v1 | `uv run uc3 lauf --alle`, dann `uv run uc3 sheet` |
| `qualitaetsberichte/JJJJ-MM.md` | 24 Qualitätsberichte nach Vorlage (Überblick, Auffälligkeiten mit SQL, Rückfragen, Regeln, Revisionsbedarf) | `uv run uc3 berichte --alle` |
| `rueckfragen/R1.md` … `R9.md` | Rückfragen an die Fachabteilung nach Vorlage, Satzzahl und Beispiel-IDs aus der Datenbank gemessen | `uv run uc3 rueckfragen` |
| `protokoll.md` | Protokoll aller Änderungen und Freigaben (Anweisung, Änderung, Name, Zeitpunkt, Commit) | `uv run uc3 protokoll` |
| `modelle.md` | verwendete Modelle | von Hand |
| `ministerium_2026-07.beleg.md` | Beleg zur Ministeriums-Lieferung (Auftrag 3): Datei, sha256, Zeilen, Definition, Datenstand, Befehl, Freigabe | `uv run uc3 ministerium --monat 2026-07 --name "Vor- und Nachname"` |

## Ministeriums-Lieferung

`ministerium_2026-07.csv` enthält je Person PERSON_ID, Geschlecht, Geburtsjahr und Tage, also Einzeldaten. Die
Datei liegt deshalb nicht in diesem öffentlichen Repo (`abgabe/.gitignore`). Sie wird über den SV-Box-Teamordner
(Ergebnisdateien) abgegeben. Im Repo steht der Beleg `ministerium_2026-07.beleg.md`; seine sha256 ordnet die Datei
der Rechnung zu, und die Freigabe mit Namen (Commit-Trailer `Freigegeben-von`) gilt genau für diesen Inhalt.

Rechenweg (Auftrag 3, Entscheid zur Variante in `docs/plan/uc3/ministerium-oracle.md`): Berichtsmonat 2026-07 und
die elf Monate davor; Arbeiter mit Dienst- oder freiem Dienstvertrag; ÖNACE-Abschnitt C; je Tag die jüngste
Lieferung, die ihn enthält, wobei die angehaltene Teil-Lieferung 2025-10 übersprungen wird (Variante S); Tage je
Person ohne Doppelzählung; mindestens 200 Tage; unplausible Geburtsdaten, auch Monat 13, als `Unbekannt`.

Die Lieferung entsteht erst, wenn die Definition (Regelsatz `ministerium`) mit Namen freigegeben ist. Bis dahin
fehlt der Beleg, und `pruefe-abgabe` meldet die Lieferung als offen.

## Stand der Zahlen

Alle 24 Monate sind vorläufig, solange Regelsatz v1 nicht mit Namen freigegeben ist
(`uv run uc3 regeln freigeben --regelsatz v1 --name "Vor- und Nachname"`, danach `uv run uc3 veroeffentlichen --alle --name …`).
2025-03 und 2025-10 enthalten zusätzlich fortgeschriebene Verhältnisse (Regel E07). Das Sheet nennt sie im Blatt
Hinweise und im Kommentar der Monatsspalte, der Qualitätsbericht in § 1.
