# Abgabe UC3 StatAgent

Alle Dateien hier erzeugt das Programm aus der Datenbank `statistik`. Kein Sprachmodell rechnet eine Zahl. Zwei
Läufe mit denselben Daten und Regeln liefern dieselben Dateien. Prüfen: `cd uc3 && uv run uc3 pruefe-abgabe --mit-db`.

| Datei | Inhalt | Erzeugt mit |
|---|---|---|
| `aggregationen_v1.xlsx` | Aggregations-Sheet nach Vorlage, 24 Berichtsmonate 2024-08 bis 2026-07, Regelsatz v1 | `uv run uc3 lauf --alle`, dann `uv run uc3 sheet` |
| `aggregationen_v2.xlsx` | Aggregations-Sheet nach den Änderungsaufträgen 1 und 2 (Regelsatz v2): gezählt über das ganze Monat, Kategorien Arbeiter, Angestellte, Beamte | `uv run uc3 lauf --alle --regelsatz v2`, dann `uv run uc3 sheet --regelsatz v2` |
| `qualitaetsberichte/JJJJ-MM.md` | 24 Qualitätsberichte nach Vorlage (Überblick, Auffälligkeiten mit SQL, Rückfragen, Regeln, Revisionsbedarf) | `uv run uc3 berichte --alle` |
| `qualitaetsberichte_v2/JJJJ-MM.md` | 24 Qualitätsberichte zu Regelsatz v2 | `uv run uc3 berichte --alle --regelsatz v2` |
| `rueckfragen/R1.md` … `R10.md` | Rückfragen an die Fachabteilung nach Vorlage, Satzzahl und Beispiel-IDs aus der Datenbank gemessen | `uv run uc3 rueckfragen` |
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
Person ohne Doppelzählung; mindestens 200 Tage; unplausible Geburtsdaten, auch Monat 13, als `Unbekannt`;
ÖNACE-2003-Altcodes DA bis DN zählen zu Abschnitt C wie im Sheet. Ergebnis im Prototyp: 32.741 Personen.

Anweisung an den Agenten für Auftrag 3 (Wortlaut und Begründung in `docs/plan/uc3/ministerium-oracle.md`):
`altcodes_als_abschnitt` = DA bis DN (genau die Codes der Regel `Q01_oenace_2003_unterabschnitte` im Regelsatz
v1), `angehaltene_lieferungen` = `ueberspringen`, also die angehaltene Lieferung 2025-10 überspringen. Soll:
32.741 Personen; ohne Altcodes kämen 32.713 heraus. `uv run uc3 ministerium` weist eine abweichende Definition
ohne Datei ab (Exit 1, Meldung mit Soll und Ist) und gibt beide Parameter und die Zeilenzahl aus. `pruefe-abgabe`
vergleicht die Zeilenzahl im Beleg mit der Sollzahl aus Annahme A13 (`docs/plan/uc3/annahmen.md`) und die sha256
im Beleg mit der Soll-sha256 aus `docs/plan/uc3/ministerium-oracle.md` (unabhängiges Orakel, CSV mit LF).

Die Definition (Regelsatz `ministerium`, Vorschlag uc3/26) ist mit Namen freigegeben. Die Lieferung 2026-07 hat
Bernhard Götzendorfer am 05.11.2026 um 19:35 selbst ausgelöst (Commit `1b0f799`, Vorschlag uc3/28).

## Stand der Zahlen

Regelsatz v1 ist mit Namen freigegeben, 22 der 24 Monate sind veröffentlicht und damit endgültig.
2025-03 und 2025-10 bleiben vorläufig: In diesen Lieferungen fehlt ein Teil der Verhältnisse, wir haben ihn einmal
aus der Vorlieferung übernommen (Regel E07) und warten auf die Antwort der Fachabteilung (Rückfragen R3 und R4).
Das Sheet nennt diese Monate im Blatt Hinweise und im Kommentar der Monatsspalte, der Qualitätsbericht in § 1.

## Auf einer frischen Datenbank nachrechnen

`uv run uc3 db init` legt die Regelsätze so an, wie die Abgabe sie gerechnet hat: v1 (`uc3/db/110`, `120`),
v2 mit den Änderungsaufträgen 1 und 2 (`uc3/db/111_regelsatz_v2.sql`) und `ministerium` mit Auftrag 3
(`uc3/db/112_regelsatz_ministerium.sql`). v2 und `ministerium` tragen die festgehaltene Freigabe aus der Abgabe
(Name, Zeitpunkt). v1 kommt ohne Freigabe an; wer nachrechnet, gibt ihn mit seinem eigenen Namen frei
(`uv run uc3 regeln freigeben --regelsatz v1 --name "Vor- und Nachname"`). Danach:

```
uv run uc3 lauf --alle
uv run uc3 lauf --alle --regelsatz v2
uv run uc3 sheet && uv run uc3 sheet --regelsatz v2
uv run uc3 berichte --alle && uv run uc3 berichte --alle --regelsatz v2
uv run uc3 ministerium --monat 2026-07 --name "Vor- und Nachname"
```

Gleich wie in der Abgabe sind die Zahlen, der Ergebnis-Hash je Monat und Lauf, die Sheets und die Ministeriums-CSV
(32.741 Personen, sha256 wie im Beleg). Anders ist nur, was Menschen in der Abgabe-Datenbank entschieden haben: Auf
der frischen Datenbank ist noch kein Monat veröffentlicht (alle Zahlen „vorläufig“), und ein neu erzeugtes
`protokoll.md` zeigt nur die Freigaben dieser Datenbank. Das Protokoll der Abgabe mit allen Namen und Zeitpunkten ist
die Datei `protokoll.md` hier. `uc3 sheet` und `uc3 berichte` schreiben nichts und enden mit Exit 1, solange für den
Regelsatz kein fertiger Lauf da ist.
