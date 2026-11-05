# Abgleich Lieferung 2025-10: Audit-Zahl 78.949 und Forensik-Zahl 78.863

Diese Datei hält fest, wie die beiden Zahlen zur Teil-Lieferung 2025-10 entstehen, jede mit eigener SQL und eigener Menge (Issue #16, AC3).
Keine Zahl gilt hier als Soll des Veranstalters, wenn wir ihre Menge nicht mit einer Abfrage nachbauen können.

Messung: 05.11.2026, Datenbank `statistik`, Tabelle `roh.lieferung`, nur SELECT. Datumsfelder sind Text im Format `JJJJ-MM-TT`, ein offenes Ende ist `NULL`.
In Lieferung 2025-09 liegt kein Ende nach dem 30.09.2025 (größtes Ende: `2025-09-30`). Ein Abschnitt gilt dort am 31.10.2025 also nur, wenn sein Ende offen ist.

## Menge A: Audit-Zahl 78.949

Verhältnisse, die am 30.09.2025 laut Lieferung 2025-09 offen sind und in Lieferung 2025-10 ganz fehlen. Dieselbe Abfrage steht in Rückfrage R3 (`uc3/db/130_rueckfragen.sql`).

```sql
SELECT count(*)
FROM (SELECT DISTINCT vvh_id FROM roh.lieferung
      WHERE lieferung = '2025-09' AND beginn <= '2025-09-30'
        AND (ende IS NULL OR ende >= '2025-09-30')) s
WHERE NOT EXISTS (SELECT 1 FROM roh.lieferung l
                  WHERE l.lieferung = '2025-10' AND l.vvh_id = s.vvh_id);
```

| Kennzahl | Anzahl |
|---|---:|
| Menge A (Verhältnisse) | **78.949** |
| davon in Lieferung 2025-11 wieder vorhanden (irgendein Abschnitt) | 78.733 |
| davon in 2025-11 nicht vorhanden | 216 |
| davon in 2025-09 am 31.10.2025 noch gültig (Ende offen, fortschreibbar nach E07) | 77.746 |
| davon in 2025-09 mit Ende 30.09.2025 (nicht fortschreibbar) | 1.203 |
| davon in 2025-11 mit einem am 31.10.2025 gültigen Abschnitt | 75.543 |
| verschiedene Personen in Menge A | 78.663 |

Die Zeilenzahl in 2025-09 zu Menge A ist ebenfalls 78.949 (ein Abschnitt je Verhältnis am 30.09.2025).

## Menge B: Forensik-Zahl 78.863

**Nicht reproduziert.** Im Repo ist die Zahl 78.863 nirgends definiert. Wir haben die naheliegenden Definitionen gemessen, keine ergibt genau 78.863:

| Kandidat | Definition | Anzahl |
|---|---|---:|
| B1 | Menge A, in 2025-09 am 31.10.2025 noch gültig (Stichtag 31.10. statt 30.09.) | 77.746 |
| B2 | Menge A, gezählt über PERSON_ID statt VVH_ID | 78.663 |
| B3 | Menge A, in 2025-11 wieder vorhanden | 78.733 |
| B4 | in 2025-11 mit einem am 31.10.2025 gültigen Abschnitt, in 2025-10 fehlend | 78.763 |
| B5 | wie B4, aber an irgendeinem Oktobertag gültig (Ende ab 01.10.2025) | 80.538 |
| B6 | wie B4, aber nur Beginn bis 31.10.2025 (Ende egal) | 83.637 |
| B7 | jedes Verhältnis aus 2025-09 (ohne Stichtag), in 2025-10 fehlend | 99.436 |
| B8 | Bestand 30.09. laut 2025-09 (394.200) minus Bestand 31.10. laut 2025-10 (313.154) | 81.046 |
| B9 | Bestand 31.10. laut 2025-11 minus Bestand 31.10. laut 2025-10 | 78.089 |
| B10 | Menge A vereinigt mit B4 | 82.169 |
| B11 | Menge A geschnitten mit B4 | 75.543 |
| B12 | Personen zu B4 (über PERSON_ID) | 78.522 |

Am nächsten liegt B4 mit 78.763, genau 100 unter 78.863. Für den Abgleich nehmen wir deshalb B4 als Arbeitsdefinition der Forensik-Menge. Sie ist **kein** Veranstalter-Soll, bis jemand die Herkunft von 78.863 belegt.

```sql
-- B4: in 2025-11 am 31.10.2025 gültig, in 2025-10 nicht geliefert
SELECT count(DISTINCT vvh_id)
FROM roh.lieferung n
WHERE n.lieferung = '2025-11' AND n.beginn <= '2025-10-31'
  AND (n.ende IS NULL OR n.ende >= '2025-10-31')
  AND NOT EXISTS (SELECT 1 FROM roh.lieferung l
                  WHERE l.lieferung = '2025-10' AND l.vvh_id = n.vvh_id);
```

Ergebnis: 78.763. Alle davon kommen per Definition in 2025-11 vor. Die Menge nutzt eine spätere Lieferung, sie taugt nur für die Revision, nicht für die Oktoberberechnung.

## Differenz

Weil 78.863 nicht reproduziert ist, gibt es keine Differenzmenge mit genau 78.949 − 78.863 = 86. Wir messen die Differenz zur Arbeitsdefinition B4 in beide Richtungen.

```sql
WITH z AS (SELECT DISTINCT vvh_id FROM roh.lieferung WHERE lieferung = '2025-10'),
a AS (SELECT DISTINCT vvh_id FROM roh.lieferung s
      WHERE lieferung = '2025-09' AND beginn <= '2025-09-30'
        AND (ende IS NULL OR ende >= '2025-09-30')
        AND NOT EXISTS (SELECT 1 FROM z WHERE z.vvh_id = s.vvh_id)),
b AS (SELECT DISTINCT vvh_id FROM roh.lieferung n
      WHERE lieferung = '2025-11' AND beginn <= '2025-10-31'
        AND (ende IS NULL OR ende >= '2025-10-31')
        AND NOT EXISTS (SELECT 1 FROM z WHERE z.vvh_id = n.vvh_id))
SELECT (SELECT count(*) FROM a WHERE vvh_id NOT IN (SELECT vvh_id FROM b)) AS a_ohne_b,
       (SELECT count(*) FROM b WHERE vvh_id NOT IN (SELECT vvh_id FROM a)) AS b_ohne_a;
```

| Menge | Anzahl | Einordnung |
|---|---:|---|
| A ohne B4 | 3.406 (78.949 − 75.543) | am 30.09. offen, aber am 31.10. laut 2025-11 nicht mehr gültig: Ende im Oktober, Ende am 30.09. (1.203 laut 2025-09) oder ganz weg (216) |
| B4 ohne A | 3.220 | am 31.10. gültig, aber am 30.09. in 2025-09 nicht offen: vor allem Neuzugänge mit Beginn im Oktober |

## Was der Lauf 2025-10 daraus macht

- Der Monat 2025-10 bleibt **vorläufig/unvollständig**. Die Prüfungen P15 bis P17 halten den Lauf an.
- Regel E07 (`E07_fortschreibung_lieferausfall`, Code `uc3/statagent/bereinigung.py:_fortschreiben`, Annahme A12) schreibt fehlende Verhältnisse einmalig aus der Vorlieferung 2025-09 fort, wenn dort ein am 31.10.2025 gültiger Abschnitt liegt. Das sind höchstens die 77.746 aus Menge A.
- Aus 2025-11 kommen **0 Ergebniszeilen**. Die Oktoberrechnung nutzt nur die eigene und frühere Lieferungen.
- Die Abweichung zu 2025-11 (Mengen A und B4) erscheint erst mit dem Lauf 2025-11 als Revisionsbedarf im Qualitätsbericht.
- Stand `meta.lauf` am 05.11.2026: der neueste Lauf 2025-10, Regelsatz v1, hat Status `fertig` und `fortgeschrieben = 0`. Das passt nicht zu den 77.746 fortschreibbaren Verhältnissen. Vermutlich stammt der Lauf aus einem Stand vor E07 oder rechnet noch neu. Das muss nach dem laufenden Datenlauf erneut geprüft werden.

Abfrage dazu:

```sql
SELECT fortgeschrieben FROM meta.lauf
WHERE lieferung = '2025-10' AND regelsatz = 'v1' AND status IN ('fertig', 'unveraendert')
ORDER BY id DESC LIMIT 1;
```
