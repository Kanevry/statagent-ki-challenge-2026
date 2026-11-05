# Belegregister: jede Zahl der Präsentation mit Herkunft

Stand 05.11.2026. Gehört zu #89. Jede Ergebniszahl auf den 11 Folien in `web/content/slides/` steht hier mit Kennung, Quelle, Abfrage und Datenstand.
Die Kennung (F1 bis F16) steht im Feld `belege` der Folie. Skript, Fragenkatalog und Drehbuch verwenden dieselben Kennungen.

Zwei Quellen rechnen unabhängig voneinander:

- **Lauf**: der UC3-Kern (`uc3/`, Befehl `uv run uc3 …`), Ergebnisse in `abgabe/`. Datenstand: Läufe vom 05.11.2026 aus MR !13 (Kopf `fbaeac2f981e`), seit dem 05.11.2026 auf `main`.
- **Gegenrechnung**: eine unabhängige Nachrechnung vom 05.11.2026 direkt auf `roh.lieferung`, nur lesend, ohne den UC3-Code. Die Abfragen dazu stehen unten.

Eine Zahl gilt als belegt, wenn beide Quellen sie liefern oder wenn eine Quelle sie mit Abfrage liefert und die andere ihr nicht widerspricht.

## Register

| Kennung | Zahl auf der Folie | Folie | Bedeutung | Quelle und Abfrage | Datenstand |
|---|---|---|---|---|---|
| F1 | 2.880 von 2.880, 0 Abweichungen | 5 | Zahlenzellen Tab1 bis Tab13 des Beispielberichts 08/2024, exakt nachgerechnet | Lauf: `uv run uc3 eichen --lieferung 2024-08` meldet „Zellen 2880, abweichend 0“; Test `uc3/tests/test_goldenset.py`. Gegenrechnung: Zellvergleich Tab1 12, Tab2 132, Tab3 bis Tab12 2.160, Tab13 576 Zellen | 05.11.2026 |
| F2 | 392.284, 48, 392.236 | 5 | Zeilen der Lieferung 2024-08, davon vor dem Stichtag beendet, Bestand am 31.08.2024 | Lauf: `abgabe/qualitaetsberichte/2024-08.md` Abschnitt 1. Gegenrechnung: Abfrage A1 | 05.11.2026 |
| F3 | 24 Lieferungen, 10.152.292 Zeilen | 2 | Datenbasis 2024-08 bis 2026-07 | `docs/plan/uc3/annahmen.md`, Lesehinweise; `SELECT count(*) FROM roh.lieferung` | 05.11.2026 |
| F4 | 370; 305 bis 399; 576 Zellen; 408, 367, 0 | 6, 7 | Geburtsmonat 13 am Stichtag 08/2024 (370); je Lieferung am Stichtag 305 bis 399; Varianten B, C und D gegen Tab13 (576 Zellen). Variante A (416) ist gestrichen: keine Quelle im Repo | Lauf: `abgabe/qualitaetsberichte/2024-08.md` Auffälligkeit 1 (P04), Regel `R5_alter`. `docs/plan/uc3/annahmen.md` A4: „408 Zellen“ (Alter unbekannt), „367 Zellen“ (minus 1), „576 von 576“ (Variante D), „305 bis 399“ am Stichtag. Gegenrechnung: Abfrage A2 | 05.11.2026 |
| F5 | 7; 117 bis 153 Jahre; 78 bis 116 Jahre (kein Fall) | 6, 8 | Alter über der Plausibilitätsgrenze, zählt als unbekannt. Zwischen 78 und 116 vollendeten Jahren gibt es in keiner Lieferung einen Fall, deshalb ändern 100 und 110 keine Zahl | Lauf: Qualitätsbericht 2024-08 Auffälligkeit 2 (P06), `docs/plan/uc3/annahmen.md` A5 („Zwischen 78 und 116 vollendeten Jahren gibt es in keiner Lieferung einen Fall“). Gegenrechnung: Abfrage A3 | 05.11.2026 |
| F6 | 50 | 6 | ÖNACE-2003-Codes am Stichtag 08/2024, zählen zu C. In den Daten kommen DA bis DM vor, ohne DE; die Regel deckt DA bis DN ab | Lauf: Qualitätsbericht 2024-08 Auffälligkeit 4 (P11). Gegenrechnung: C = 62.154 + 50 = 62.204 wie Tab3 | 05.11.2026 |
| F7 | 1.996 | 6 | Bundesland und ÖNACE leer, immer gemeinsam | Lauf: Qualitätsbericht 2024-08 Auffälligkeit 3 (P10). Gegenrechnung: Abfrage A4 | 05.11.2026 |
| F8 | 1.663; 1.523 | 6, 8 | doppelte Zeilen in Lieferung 2025-03, in allen Feldern gleich (1.663). Ohne Verdichtung wären am 31.03.2025 1.523 Verhältnisse doppelt gezählt | Lauf: Qualitätsbericht 2025-03 Auffälligkeit 1 (P01); `docs/plan/uc3/annahmen.md` A1 („1.523 Sätze am 31.03.2025“). Gegenrechnung: Abfrage A5 | 05.11.2026 |
| F9 | 1.492; 1.131; 361; 1.470 | 6, 8 | freie Dienstverträge, die laut Lieferung 2025-02 am 28.02.2025 bestehen und in 2025-03 fehlen (1.131 AngestellteFD und 361 ArbeiterFD, zusammen 1.492). Davon schreibt der Lauf 1.470 Verhältnisse aus 2025-02 fort | Lauf: Qualitätsbericht 2025-03 Auffälligkeit 7 (P13) und Abschnitt 1 („1.470“ fortgeschrieben, Regel E07). Gegenrechnung: Abfrage A6b (A6 liefert nur die FD-Sätze je Lieferung) | 05.11.2026 |
| F10 | 388.115; 432.086; 21; 394.252 | 6 | Zeilen ohne Beginn in Lieferung 2025-06 (388.115 von 432.086). Ohne Tausch bestehen am 30.06.2025 nur 21 Verhältnisse, mit Tausch 394.252 | `docs/plan/uc3/annahmen.md` A6 (Regel E01; „21“ und „394.252“ dort „gemessen“). Der Qualitätsbericht 2025-06 (P03, Abschnitt 1) nennt dagegen 432.086 getauschte Sätze und 394.252 gezählt. Abfrage A7 | 05.11.2026 |
| F11 | 78.949; „jede fünfte“; „fast alle wieder“; 345.078; 77.746; 390.900; rund 430.000 | 6 | am 30.09.2025 offene Verhältnisse, die in 2025-10 fehlen (20,0 % von 394.200); 78.733 davon wieder in 2025-11. Lieferung 2025-10 hat 345.078 Zeilen (Vormonat 434.104, daher „rund 430.000“). Der Lauf schreibt 77.746 Verhältnisse fort und weist 390.900 als vorläufigen Bestand aus | Lauf: Qualitätsbericht 2025-10 Abschnitt 1 (345.078 gelesen, 77.746 fortgeschrieben, 390.900 gezählt) und Auffälligkeiten 7 bis 9 (P15, P16, P17). Gegenrechnung: Abfrage A8 | 05.11.2026 |
| F12 | −260; 0,067 % | 9 | Revisionsbedarf Dezember 2024: 387.390 laut Lieferung 2024-12 (im Bericht 2025-01 „vorläufig“, nicht veröffentlicht), 387.130 laut Lieferung 2025-01. Der Bericht rundet auf 0,1 %, die 0,067 % stammen aus der Gegenrechnung | Lauf: Qualitätsbericht 2025-01 Auffälligkeit 8 (P23). Gegenrechnung: Abfrage A9 | 05.11.2026 |
| F15 | 15 Regeln, 24 Prüfregeln | 3 | Regelsatz v1 in `meta.regel` | `uv run uc3 regeln zeigen`; `docs/plan/uc3/annahmen.md`, Lesehinweise | 05.11.2026 |
| F16 | (keine Zahl) zwei Läufe, derselbe Hash | 3, 4 | Determinismus | `uv run uc3 laeufe` zeigt den Ergebnis-Hash je Lauf; `uc3/README.md` | 05.11.2026 |

F13 (Klassifikationswechsel) und F14 (Kernzahlen 08/2024) kommen nicht auf den Folien vor, nur im Skript, im Fragenkatalog und in der Kriterien-Karte. Sie stehen der Vollständigkeit halber unten. F13 führt keine Zahl: Die Zahlen 189.170 und 386.299 sind gestrichen, weil es dazu keine ausführbare Abfrage gibt.

| Kennung | Zahl | Bedeutung | Quelle | Datenstand |
|---|---|---|---|---|
| F13 | (ohne Zahl) | Klassifikationswechsel ÖNACE 2008 → 2025 ab Lieferung 2025-01, auch rückwirkend für Dezember 2024 | `docs/plan/uc3/annahmen.md`, Regel `R7_oenace_nach_berichtsmonat` | 05.11.2026 |
| F14 | 392.236 gesamt, 211.603 Männer, 180.633 Frauen, 90.799 Wien, 64.505 Niederösterreich | Kernzahlen 08/2024 | Beispielbericht Tab1 und Tab2, im Lauf exakt nachgerechnet (F1) | 05.11.2026 |

Parameterwerte der geübten Änderungen (Fragenkatalog Teil B) sind Eingaben und keine Ergebniszahlen: `max_plausibel` 110 mit Übungswert 100 (`docs/plan/uc3/annahmen.md` A5, F5), Schwelle der Prüfregel P13 100 mit Übungswert 2.000 (Qualitätsbericht 2025-03 Auffälligkeit 7, F9).

## Abfragen der Gegenrechnung

Stichtag ist der Monatsletzte. Ein Abschnitt besteht am Stichtag, wenn `beginn <= Stichtag` und `ende` leer ist oder `ende >= Stichtag`.

```sql
-- A1  Rechnung 08/2024 (Ergebnis 392.284 Zeilen, 392.236 am Stichtag)
SELECT count(*) FROM roh.lieferung WHERE lieferung = '2024-08';
SELECT count(DISTINCT vvh_id) FROM roh.lieferung
 WHERE lieferung = '2024-08' AND beginn <= '2024-08-31' AND (coalesce(ende, '') = '' OR ende >= '2024-08-31');

-- A2  Geburtsmonat 13 am Stichtag 08/2024 (Ergebnis 370)
SELECT count(*) FROM roh.lieferung
 WHERE lieferung = '2024-08' AND substr(geburtsdatum, 6, 2) = '13'
   AND beginn <= '2024-08-31' AND (coalesce(ende, '') = '' OR ende >= '2024-08-31');

-- A3  Alter über 100 am Stichtag 08/2024 (Ergebnis 7, Alter 117 bis 153)
SELECT count(*), min(2024 - left(geburtsdatum, 4)::int), max(2024 - left(geburtsdatum, 4)::int)
  FROM roh.lieferung
 WHERE lieferung = '2024-08' AND 2024 - left(geburtsdatum, 4)::int > 100
   AND beginn <= '2024-08-31' AND (coalesce(ende, '') = '' OR ende >= '2024-08-31');

-- A4  Bundesland und ÖNACE leer, nur gemeinsam (Ergebnis 1.996 am Stichtag; 0 Sätze mit nur einer Lücke)
SELECT count(*) FROM roh.lieferung
 WHERE lieferung = '2024-08' AND coalesce(oenace, '') = '' AND coalesce(bundesland, '') = ''
   AND beginn <= '2024-08-31' AND (coalesce(ende, '') = '' OR ende >= '2024-08-31');
SELECT count(*) FROM roh.lieferung
 WHERE lieferung = '2024-08' AND (coalesce(oenace, '') = '') <> (coalesce(bundesland, '') = '');

-- A5  Volldubletten (Ergebnis: nur 2025-03, 1.663 Gruppen mit je zwei Zeilen)
SELECT lieferung, count(*) FROM (
  SELECT lieferung FROM roh.lieferung
   GROUP BY lieferung, vvh_id, person_id, geburtsdatum, geschlecht, beginn, ende, qual, oenace, bundesland
  HAVING count(*) > 1) g
 GROUP BY 1;

-- A6  FD-Sätze je Lieferung (Ergebnis: 2025-03 hat 0, alle anderen Lieferungen 1.316 bis 1.697). Das ist nicht die Zahl 1.492.
SELECT lieferung, count(*) FILTER (WHERE qual LIKE '%FD') FROM roh.lieferung GROUP BY 1 ORDER BY 1;

-- A6b FD-Verhältnisse, die laut Lieferung 2025-02 am 28.02.2025 bestehen und in 2025-03 fehlen
--     (Ergebnis 1.492, davon AngestellteFD 1.131 und ArbeiterFD 361; ausgeführt am 05.11.2026, nur lesend;
--      passt zu Qualitätsbericht 2025-03, P13: 1.131 + 361)
SELECT count(DISTINCT a.vvh_id),
       count(DISTINCT a.vvh_id) FILTER (WHERE a.qual = 'AngestellteFD'),
       count(DISTINCT a.vvh_id) FILTER (WHERE a.qual = 'ArbeiterFD')
  FROM roh.lieferung a
 WHERE a.lieferung = '2025-02' AND a.qual LIKE '%FD'
   AND a.beginn <= '2025-02-28' AND (coalesce(a.ende, '') = '' OR a.ende >= '2025-02-28')
   AND NOT EXISTS (SELECT 1 FROM roh.lieferung b
                    WHERE b.lieferung = '2025-03' AND b.vvh_id = a.vvh_id AND b.qual LIKE '%FD');

-- A7  Spaltentausch 2025-06 (Ergebnis 432.086 Zeilen, 388.115 ohne Beginn, 0 ohne Ende)
SELECT count(*), count(*) FILTER (WHERE coalesce(beginn, '') = ''), count(*) FILTER (WHERE coalesce(ende, '') = '')
  FROM roh.lieferung WHERE lieferung = '2025-06';

-- A8  Teil-Lieferung 2025-10 (Ergebnis 78.949 fehlen)
SELECT count(*) FROM (
  SELECT DISTINCT vvh_id FROM roh.lieferung
   WHERE lieferung = '2025-09' AND beginn <= '2025-09-30' AND (coalesce(ende, '') = '' OR ende >= '2025-09-30')) s
 WHERE NOT EXISTS (SELECT 1 FROM roh.lieferung l WHERE l.lieferung = '2025-10' AND l.vvh_id = s.vvh_id);

-- A9  Revisionsbedarf 12/2024 (Ergebnis 387.390 alt, 387.130 neu)
SELECT lieferung, count(DISTINCT vvh_id) FROM roh.lieferung
 WHERE lieferung IN ('2024-12', '2025-01') AND beginn <= '2024-12-31' AND (coalesce(ende, '') = '' OR ende >= '2024-12-31')
 GROUP BY 1;
```

## Prüfung

- Vor der Probe am Fr 06.11.2026 werden F1 bis F12 gegen die Dateien in `abgabe/` des gemergten Stands abgeglichen. Weicht eine Zahl ab, gilt die Zahl aus dem Lauf, und Folie, Skript und dieses Register werden in einem Zug geändert.
- Zahlen ohne Kennung stehen auf keiner Folie. Uhrzeiten, Datumsangaben und Folienzeiten sind keine Ergebniszahlen.
