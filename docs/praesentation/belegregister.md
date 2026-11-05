# Belegregister: jede Zahl der Präsentation mit Herkunft

Stand 05.11.2026. Gehört zu #89. Jede Ergebniszahl auf den 11 Szenen (Szenen v2) in `web/content/slides/` steht hier mit Kennung, Quelle, Abfrage und Datenstand.
Die Kennung (F1 bis F17) steht im Feld `belege` der Szene. Die Spalte „Szene“ nennt die Nummer der Szene (Datei `NN-*.md`). Skript, Fragenkatalog und Drehbuch verwenden dieselben Kennungen.

Zwei Quellen rechnen unabhängig voneinander:

- **Lauf**: der UC3-Kern (`uc3/`, Befehl `uv run uc3 …`), Ergebnisse in `abgabe/`. Datenstand: Läufe vom 05.11.2026 aus MR !13 (Kopf `fbaeac2f981e`), seit dem 05.11.2026 auf `main`.
- **Gegenrechnung**: eine unabhängige Nachrechnung vom 05.11.2026 direkt auf `roh.lieferung`, nur lesend, ohne den UC3-Code. Die Abfragen dazu stehen unten.

Eine Zahl gilt als belegt, wenn beide Quellen sie liefern oder wenn eine Quelle sie mit Abfrage liefert und die andere ihr nicht widerspricht.

## Register

| Kennung | Zahl in der Szene | Szene | Bedeutung | Quelle und Abfrage | Datenstand |
|---|---|---|---|---|---|
| F1 | 2.880 von 2.880, 0 Abweichungen | 5 | Zahlenzellen Tab1 bis Tab13 des Beispielberichts 08/2024, exakt nachgerechnet | Lauf: `uv run uc3 eichen --lieferung 2024-08` meldet „Zellen 2880, abweichend 0“; Test `uc3/tests/test_goldenset.py`. Gegenrechnung: Zellvergleich Tab1 12, Tab2 132, Tab3 bis Tab12 2.160, Tab13 576 Zellen | 05.11.2026 |
| F2 | 392.284, 48, 392.236 | 5 | Zeilen der Lieferung 2024-08, davon vor dem Stichtag beendet, Bestand am 31.08.2024 | Lauf: `abgabe/qualitaetsberichte/2024-08.md` Abschnitt 1. Gegenrechnung: Abfrage A1 | 05.11.2026 |
| F3 | 24 Lieferungen, 10.152.292 Zeilen | keine | Datenbasis 2024-08 bis 2026-07 | `docs/plan/uc3/annahmen.md`, Lesehinweise; `SELECT count(*) FROM roh.lieferung` | 05.11.2026 |
| F4 | 370; 576 Zellen; 416, 408, 367, 0 | 6, 7 | Geburtsmonat 13 am Stichtag 08/2024; Varianten A bis D gegen Tab13 | Lauf: `abgabe/qualitaetsberichte/2024-08.md` Auffälligkeit 1 (P04), Regel `R5_alter`. Gegenrechnung: Abfrage A2 und Variantenvergleich | 05.11.2026 |
| F5 | 7; 117 bis 153 Jahre | 6 | Alter über der Plausibilitätsgrenze, zählt als unbekannt | Lauf: Qualitätsbericht 2024-08 Auffälligkeit 2 (P06), `docs/plan/uc3/annahmen.md` A5. Gegenrechnung: Abfrage A3 | 05.11.2026 |
| F6 | 50 | 6 | ÖNACE-2003-Codes am Stichtag 08/2024, zählen zu C. In den Daten kommen DA bis DM vor, ohne DE; die Regel deckt DA bis DN ab | Lauf: Qualitätsbericht 2024-08 Auffälligkeit 4 (P11). Gegenrechnung: C = 62.154 + 50 = 62.204 wie Tab3 | 05.11.2026 |
| F7 | 1.996 | 6 | Bundesland und ÖNACE leer, immer gemeinsam | Lauf: Qualitätsbericht 2024-08 Auffälligkeit 3 (P10). Gegenrechnung: Abfrage A4 | 05.11.2026 |
| F8 | 1.663 | 6 | doppelte Zeilen in Lieferung 2025-03, in allen Feldern gleich | Lauf: Qualitätsbericht 2025-03 Auffälligkeit 1 (P01). Gegenrechnung: Abfrage A5 | 05.11.2026 |
| F9 | 1.492 | 6 | freie Dienstverträge, die am 28.02.2025 bestehen und in 2025-03 fehlen | Lauf: Qualitätsbericht 2025-03 Auffälligkeit 7 (P13, AngestellteFD 1.131 und ArbeiterFD 361). Gegenrechnung: Abfrage A6 | 05.11.2026 |
| F10 | 388.115 | 6 | Zeilen ohne Beginn in Lieferung 2025-06 (von 432.086) | Lauf: `docs/plan/uc3/annahmen.md` A6, Qualitätsbericht 2025-06 (P03). Abfrage A7 | 05.11.2026 |
| F11 | 78.949; „jede fünfte“; „fast alle wieder“; 313.154; 390.900 | 2, 6 | am 30.09.2025 offene Verhältnisse, die in 2025-10 fehlen (20,0 % von 394.200); 78.733 davon wieder in 2025-11; 313.154 so geliefert am 31.10.2025 (P15) und 390.900 vorläufig nach Fortschreibung | Lauf: Qualitätsbericht 2025-10 (P15, P16, P17), Status und Abschnitt 1 Überblick (313.154 „davon geliefert gezählt“, 390.900 „davon gezählt am Stichtag“). Gegenrechnung: Abfrage A8 | 05.11.2026 |
| F12 | −260; 0,067 % | 9 | Revisionsbedarf Dezember 2024: 387.390 veröffentlicht, 387.130 laut Lieferung 2025-01. Der Bericht rundet auf 0,1 %, die 0,067 % stammen aus der Gegenrechnung | Lauf: Qualitätsbericht 2025-01 Auffälligkeit 8 (P23). Gegenrechnung: Abfrage A9 | 05.11.2026 |
| F15 | 15 Regeln, 24 Prüfregeln | 3 | Regelsatz v1 in `meta.regel` | `uv run uc3 regeln zeigen`; `docs/plan/uc3/annahmen.md`, Lesehinweise | 05.11.2026 |
| F16 | (keine Zahl) zwei Läufe, derselbe Hash | 3, 4 | Determinismus | `uv run uc3 laeufe` zeigt den Ergebnis-Hash je Lauf; `uc3/README.md` | 05.11.2026 |
| F17 | 24 Monatswerte | 2 | Beschäftigungsverhältnisse am Stichtag, 2024-08 bis 2026-07, jeweils der Wert der Zeile „Beschäftigungsverhältnisse am Stichtag“ | Lauf: `abgabe/qualitaetsberichte/<Monat>.md` Abschnitt 1, Zeile „Beschäftigungsverhältnisse am Stichtag“. Status vorläufig bis zur Freigabe des Regelsatzes; 2025-03 und 2025-10 sind angehalten | Läufe vom 05.11.2026 |

F13 (Klassifikationswechsel, 189.170 Verhältnisse) und F14 (Kernzahlen 08/2024) kommen in keiner Szene vor, nur im Skript und im Fragenkatalog. Sie stehen der Vollständigkeit halber unten.

| Kennung | Zahl | Bedeutung | Quelle | Datenstand |
|---|---|---|---|---|
| F13 | 189.170 von 386.299 | Verhältnisse mit anderem ÖNACE-Abschnitt in Lieferung 2025-01 als in 2024-12 (Umstellung ÖNACE 2008 auf 2025) | Gegenrechnung, Abfrage A10 | 05.11.2026 |
| F14 | 392.236 gesamt, 211.603 Männer, 180.633 Frauen, 90.799 Wien, 64.505 Niederösterreich | Kernzahlen 08/2024 | Beispielbericht Tab1 und Tab2, im Lauf exakt nachgerechnet (F1) | 05.11.2026 |

## Abfragen der Gegenrechnung

Stichtag ist der Monatsletzte. Ein Abschnitt besteht am Stichtag, wenn `beginn <= Stichtag` und `ende` leer ist oder `ende >= Stichtag`.

```sql
-- A1  Brücke 08/2024 (Ergebnis 392.284 Zeilen, 392.236 am Stichtag)
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

-- A6  Freie Dienstverträge je Lieferung (Ergebnis 2025-03: 0; sonst 1.316 bis 1.697)
SELECT lieferung, count(*) FILTER (WHERE qual LIKE '%FD') FROM roh.lieferung GROUP BY 1 ORDER BY 1;

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

-- A10 ÖNACE-Abschnitt geändert zwischen 2024-12 und 2025-01 (Ergebnis 189.170 von 386.299)
--     Vergleich je VVH_ID über die Abschnittscodes beider Lieferungen (Umsteiger 2008 auf 2025 beachten).
```

## Prüfung

- Vor der Probe am Fr 06.11.2026 werden F1 bis F12 und F17 gegen die Dateien in `abgabe/` des gemergten Stands abgeglichen. Weicht eine Zahl ab, gilt die Zahl aus dem Lauf, und Szene, Skript und dieses Register werden in einem Zug geändert.
- Zahlen ohne Kennung stehen in keiner Szene. Uhrzeiten, Datumsangaben und Szenenzeiten sind keine Ergebniszahlen.
