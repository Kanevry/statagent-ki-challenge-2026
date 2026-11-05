# Abnahme UC3 StatAgent: Prüfausgaben und Belege

Stand 05.11.2026 20:15 (Wiener Zeit), gemessen auf der Abgabe-Datenbank (nur lesend) und im Repo. Bezug: Issue #20
(AC2), Teilissues #15, #16, #17, #69, #70, #71, #73, #74; Abnahmen #63 (Modelle), #65 (Voice), #66 (Golden Set und
Determinismus).

## 1 Abgabedateien vollständig

`cd uc3 && uv run uc3 pruefe-abgabe --mit-db` am 05.11.2026 19:3x, nach der Ministeriums-Lieferung:

```
[ok] Aggregations-Sheet v1: aggregationen_v1.xlsx: 6 Blätter, Monatsspalten gefüllt, Insgesamt-Formeln und Blattsummen stimmen, Summen = stat.stat_beschaeftigte
[ok] Qualitätsberichte 2024-08 bis 2026-07: 24 Berichte mit 5 Abschnitten, Monat im Titel, aufgehender Abrechnung und gültigen Einstufungen
[ok] Qualitätsberichte v2 (Aufträge 1+2): 24 Berichte mit 5 Abschnitten, Monat im Titel, aufgehender Abrechnung und gültigen Einstufungen
[ok] Vorlage Qualitätsbericht: qualitaetsbericht_vorlage.md: 5 Abschnitte, 3 Einstufungen
[ok] Ministeriums-Lieferung 2026-07: 32.741 Personen wie Annahme A13, sortiert, TAGE ≥ 200
[ok] Protokoll: protokoll.md vorhanden
[ok] Modellangabe: models.md vorhanden
[ok] Aggregations-Sheet v2 (nach Änderungsaufträgen): aggregationen_v2.xlsx: 6 Blätter, Monatsspalten gefüllt, Insgesamt-Formeln und Blattsummen stimmen, Summen = stat.stat_beschaeftigte
[ok] keine Regelkonstanten im Code (Technische Regel 3): kein Treffer außerhalb von regeln.py
Abgabe vollständig.
```

Seit diesem MR kommt der Punkt „Manifest“ dazu: `abgabe/manifest.json` nennt jede Abgabedatei mit Größe, sha256,
Regelsatz und Stand, dazu `ministerium_2026-07.csv` mit Ort „extern“. Fehlt eine Datei oder weicht sie ab, endet
die Prüfung mit Exit 1. Die Ausgabe nach dem Neuschreiben steht in der Beschreibung des MR.

## 2 Zahlen

| Zahl | Wert | Beleg |
|---|---|---|
| Beschäftigungsverhältnisse 07/2026, Regelsatz v1 (Stichtag) | 399.027 | `aggregationen_v1.xlsx`, Qualitätsbericht 2026-07, Lauf 121 |
| Beschäftigungsverhältnisse 07/2026, Regelsatz v2 (ganzes Monat, Aufträge 1+2) | 407.604 | `aggregationen_v2.xlsx`; unabhängiger CSV-Filter (BEGINN ≤ 31.07.2026, ENDE leer oder ≥ 01.07.2026, eindeutige VVH_ID) ergibt dieselbe Zahl |
| Ministeriums-Lieferung 07/2026 | 32.741 Personen | `ministerium_2026-07.beleg.md`, sha256 `d8492f46dd5f…86379`, unabhängiges Orakel 0 Abweichungen |

## 3 Determinismus und Golden Set (#66)

- Zwei Läufe mit denselben Daten und Regeln liefern denselben Ergebnis-Hash: In der Abgabe-Datenbank gibt es 72
  Wiederholungsläufe (`meta.lauf.status = 'unveraendert'`, 48 in v1 und 24 in v2, je Lieferung), und alle 72 haben
  den Ergebnis-Hash des Laufs davor mit demselben Regelstand (72 von 72 gleich, gemessen 05.11.2026 20:10).
- Golden Set: `uv run pytest -m daten tests/test_goldenset.py` vergleicht 2.880 Zahlenzellen des Beispielberichts
  08/2024 mit dem Monatslauf. Gegen die Kopie der Abgabe-Datenbank (`statistik_probe`, Lauf in einer
  zurückgerollten Transaktion): `3 passed`, gemessen 05.11.2026 20:12. Der vollständige Jury-Weg (docker compose
  frisch) ist Teil von #66 und wird dort abgenommen.

## 4 Modelle (#63)

`abgabe/modelle.md`: Monatslauf, Prüfungen, Berichte, Sheet, Ministeriums-Lieferung, Datenanfragen und
Klassifikationen laufen ohne Modell. Die eigenen Agenten nutzen Azure AI Foundry, Deployment `gpt-5-4-mini`, über
`plattform.llm`. Die drei Pflicht-Agentenläufe (Aufträge 1 bis 3) liefen mit `provider = azure`,
`modell = gpt-5-4-mini` (meta.protokoll, IDs 24, 25, 26; `docs/plan/uc3/agenten-routing.json`). Der Modell-Schalter
für alle Anbieter wird in #63 abgenommen.

## 5 Änderungsaufträge, Freigaben, Protokoll

- Weg je Auftrag mit Rolle, Vorschlag, Freigabe und Ergebnis: `docs/plan/uc3/aenderungsauftraege-matrix.md`.
- Rollenrouting: `docs/plan/uc3/agenten-routing.json` (vier Anweisungen, je eine Rolle, mit Protokoll-ID).
- Jede Regeländerung und jede Lieferung steht mit Vor- und Nachnamen und Zeitpunkt in `abgabe/protokoll.md`
  (Abschnitt 1 Freigaben, Abschnitt 5 Lieferung nach außen) und als Commit-Trailer `Freigegeben-von`.
- Die Freigaben im Auftrag hat Bernhard Götzendorfer selbst bestätigt (Commit `2ba95e5`), die Ministeriums-Lieferung
  hat er selbst ausgelöst (Commit `1b0f799`).

## 6 Anhang B (#73)

`docs/plan/uc3/anhang-b-schema.sql` enthält elf Prüfabfragen (Long-Format, Beschreibung, Dimensionen, Variable,
Klassifikationen, Übergänge, Quellzuordnung, Zellcodes), jede mit Soll 0. `uc3/tests/test_anhang_b.py` führt sie
auf der Fixture-Datenbank nach drei Läufen aus: alle 0. Bewusste Ausnahme: `klass_alter` hat keine Gültigkeit
(Alter in Jahren ist zeitlos). Pensionen sind nicht importiert (Optimum Bereich 1, offen).

## 7 Was nicht Teil dieser Abgabe ist

- Voice für UC3 (#65, #79): Das Gespräch über die Plattform-Stimme ist für UC1 gebaut; einen UC3-Voice-Verbraucher
  (`uc3/statagent/voice.py`) gibt es nicht. Datenfragen an UC3 gehen über `uv run uc3 frage` und die Weboberfläche.
- Live-Änderung vor der Jury (#80): Proben, Ablehnen und Rücknahme belegt die Live-Lane in eigenen Dateien.
- Ein eigenes Sheet nur für Auftrag 1 (`aggregationen_v2a.xlsx`): entfällt, weil Auftrag 2 laut Aufgabenstellung
  zusammen mit Auftrag 1 gilt (Begründung in der Matrix).
