# Änderungsaufträge: Weg und Beleg je Auftrag (UC3)

Stand 05.11.2026 19:50. Bezug: Issue #17 (koordiniert), Teilissues #69, #70, #71, #74. Quelle der Aufträge:
`svbox/uc3/aenderungsauftraege.md`. Jeder Auftrag ging als Satz in Alltagssprache an die eigenen Agenten
(`uv run uc3 agent "…"`), nicht an das Entwicklungswerkzeug. Der Koordinator ordnet ihn genau einer Rolle zu
(`docs/plan/uc3/agenten-routing.json`), die Rolle schreibt einen Vorschlag, ein Mensch gibt ihn mit Vor- und
Nachnamen frei, das Programm rechnet danach ohne Modell.

| Auftrag | Teilissue | Rolle (Protokoll-ID) | Vorschlag und Wirkung | Freigabe (Commit) | Ergebnis und Beleg |
|---|---|---|---|---|---|
| 1 Dienstvertrag und freier Dienstvertrag zusammen | #69 | klassifikation (24) | uc3/24: Regelsatz v2, R6 zählt nach Beschäftigungskategorie statt Qualifikation | Bernhard Götzendorfer, 05.11.2026 16:53 (`d92cd47`), Regelsatz v2 (`599e601`) | `abgabe/aggregationen_v2.xlsx` Blatt Beschäftigungskategorie mit Arbeiter = ArbeiterDV + ArbeiterFD und Angestellte = AngestellteDV + AngestellteFD; `uc3 pruefe-abgabe --mit-db` Punkt „Aggregations-Sheet v2“ ok |
| 2 Ganzes Monat statt Stichtag | #70 | datenmanagement (25) | uc3/25: Regelsatz v2, R2_R4 zählt vom Monatsersten bis zum Monatsletzten | Bernhard Götzendorfer, 05.11.2026 16:54 (`952eeb8`), Regelsatz v2 (`599e601`) | 24 Läufe v2, `abgabe/aggregationen_v2.xlsx` und `abgabe/qualitaetsberichte_v2/`; 07/2026 = 407.604 (v1: 399.027), gegen ein unabhängiges CSV-Orakel gleich; Tests `uc3/tests/test_monatszaehlung.py` |
| 3 Datenlieferung an das Ministerium | #71 | datenmanagement (26) | uc3/26: Regelsatz ministerium, neue Regel M01_personentage_ministerium | Definition: Bernhard Götzendorfer, 05.11.2026 16:54 (`08e63c0`); Lieferung 2026-07: Bernhard Götzendorfer, 05.11.2026 19:35 (`1b0f799`, uc3/28) | `abgabe/ministerium_2026-07.beleg.md`: 32.741 Personen, sha256 `d8492f46dd5f`; CSV außerhalb des Repos, Abgabe über den SV-Box-Teamordner; `docs/plan/uc3/ministerium-oracle.md` |
| Datenanfragen der Jury | #74 | ohne Agent (Programm) | keine Regeländerung: `uv run uc3 frage "…"` antwortet mit sichtbarem SQL, Definition und Stand | entfällt (ändert nichts) | `uc3/tests/test_frage.py`; Antworten ohne Modell (`abgabe/modelle.md`) |

## Warum v1 und v2 und kein eigenes Sheet nur für Auftrag 1

Die Aufgabenstellung nennt bei Auftrag 2 als Geltung „rückwirkend für die ganze Zeitreihe, zusammen mit
Auftrag 1“ (`svbox/uc3/aenderungsauftraege.md`, Zeile 24). Deshalb gibt es genau zwei Stände: v1 (Regeln vor den Aufträgen,
`aggregationen_v1.xlsx`) und v2 (Aufträge 1 und 2 zusammen, `aggregationen_v2.xlsx`). Ein drittes Sheet nur mit
Auftrag 1 (in #69 als `aggregationen_v2a.xlsx` geplant) entsteht nicht. v1 bleibt unverändert: veröffentlichte
Monate sind geschützt (`stat.schuetze_endgueltig`), Abweichungen stehen als Revisionsbedarf in den Berichten.

## Bestätigung durch die Person selbst

Die Freigaben uc3/24 bis uc3/27 gab der Lead im Auftrag von Bernhard Götzendorfer ein. Bernhard Götzendorfer hat
sie danach selbst bestätigt (`uv run uc3 bestaetigen`, Commit `2ba95e5`, Technische Regel 7). Die
Ministeriums-Lieferung hat er selbst ausgelöst (Commit `1b0f799`). Alles steht in `abgabe/protokoll.md`.
