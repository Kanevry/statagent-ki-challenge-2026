# UC3 StatAgent: Annahmen der Zählung

Stand 05.11.2026. Regelsatz `v1` (`meta.regel`; Regeln immer über `name` ansprechen, die Ids hängen von der Datenbank ab). GitLab #14 (AC4). Rückfragen an den Veranstalter stehen in GitLab #72; hier nur mit Nummer.

## Lesehinweise

- Datenbasis: `roh.lieferung` (10.152.292 Zeilen, 24 Lieferungen 2024-08 bis 2026-07, alle Felder Text). Alle Zahlen mit Vermerk „gemessen" wurden am 05.11.2026 per SELECT nachgerechnet. Zahlen mit Vermerk „Quelle: Lead-Gegenrechnung bzw. Forensik 05.11." sind übernommen.
- Beispiel-IDs sind VVH_IDs. Personenschlüssel werden nicht genannt.
- Stichtag einer Lieferung ist der Monatsletzte des Berichtsmonats. Ein Satz ist am Stichtag aktiv, wenn `beginn <= Stichtag` und `ende` leer oder `ende >= Stichtag`. Abkürzung in den Abfragen: `AKTIV(st)`.
- Alle Regeln gelten ab Lieferung 2024-08 und sind angelegt (`aktiv = true`). Regelsatz v1 umfasst 15 Einlese-, Zuordnungs- und Zählregeln sowie 24 Prüfregeln (P01–P24). Eine Namensfreigabe (`freigegeben_von`) ist noch nicht eingetragen; sie erfolgt mit `uv run uc3 regeln freigeben --name "Vor- und Nachname"` über Vertrag P.

## Übersicht

| Nr. | Kurzname | Betroffene Sätze | Regel in `meta.regel` | Rückfrage |
|---|---|---|---|---|
| A1 | Volldubletten einmal zählen | 1.663 Zeilen verdichtet (nur 2025-03); 1.523 Sätze am 31.03.2025 | `E02_volldubletten` | R7 |
| A2 | Leere Merkmale sind „unbekannt" | 1.996 am Stichtag 2024-08; 1.587 bis 2.031 je Lieferung am Stichtag | `Q02_leer_unbekannt` (mit `E05_quellzuordnung`) | keine |
| A3 | ÖNACE-2003-Unterabschnitte nach C | 50 am Stichtag 2024-08; 40 bis 51 je Lieferung | `Q01_oenace_2003_unterabschnitte` | keine |
| A4 | Geburtsmonat 13 | 370 am Stichtag 2024-08; 305 bis 399 je Lieferung | `E03_datum_pruefen`, `R5_alter` | R1 |
| A5 | Unplausibles Alter | 7 am Stichtag 2024-08 | `R5_alter` (`max_plausibel = 110`) | R6 |
| A6 | Spaltentausch BEGINN/ENDE | 388.115 von 432.086 (nur 2025-06) | `E01_spaltentausch_beginn_ende` | R5 |
| A7 | Abschnittswahl am Stichtag | 0 am Stichtag; Lücken 0 bis 7 und Überlappungen 0 bis 4 je Lieferung | `R1_R3_verhaeltnis_einmal` | keine |
| A8 | Abrechnung „nicht gezählt" | 48 in 2024-08 | `R2_R4_stichtag_eigene_lieferung` | keine |
| A9 | Erstlieferung kein Vollabzug | ganze Lieferung 2024-08 (392.284) | `R2_R4_stichtag_eigene_lieferung` | keine |
| A10 | Phantom-Doppelmeldungen | 196 in 2024-08 | `R1_R3_verhaeltnis_einmal` (Zählregel 1) | keine |

---

## A1 Volldubletten einmal zählen

**Befund.** Nur Lieferung 2025-03 enthält Volldubletten: 1.663 Gruppen mit genau zwei Zeilen, alle neun Felder gleich (gemessen). Ohne Verdichtung zählt der Stichtag 31.03.2025 388.703 Sätze, mit Verdichtung 387.180 (gemessen), also 1.523 doppelt. 357 VVH_IDs haben in 2025-03 mehrere verschiedene Zeilen (gemessen). Das sind echte Zeitabschnitte: 219 mit QUAL-Wechsel und 137 mit BL-Wechsel, nie mit gleichem BEGINN (Quelle: Lead-Gegenrechnung bzw. Forensik 05.11.; 219 + 137 = 356, ein Fall ist dort nicht eingeordnet). Beispiele: 100071, 100136, 10047.

**Annahme.** Ein Satz, der in allen neun Feldern gleich ist, zählt einmal. Verglichen werden alle Felder, nicht nur die VVH_ID.

**Begründung.** Anhang A Nr. 1 (kommt ein Satz mehrfach vor, zählt das Verhältnis einmal); Fachbeschreibung § 2.

**Umgesetzt als.** `E02_volldubletten`, Parameter `{"vergleich": "alle_felder"}`. Die Zahl der verdichteten Zeilen steht im Qualitätsbericht.

**Gültigkeit.** Ab Lieferung 2024-08, wirksam in 2025-03.

**Beleg-SQL.**

```sql
-- Dublettengruppen je Lieferung (Ergebnis: nur 2025-03, 1663 Gruppen, max. 2 Zeilen)
SELECT lieferung, count(*) FROM (
  SELECT lieferung FROM roh.lieferung
  GROUP BY lieferung, vvh_id, person_id, geburtsdatum, geschlecht, beginn, ende, qual, oenace, bundesland
  HAVING count(*) > 1) g GROUP BY 1;
-- Stichtag 31.03.2025 roh (388703) gegen verdichtet (387180)
SELECT count(*) FROM roh.lieferung WHERE lieferung='2025-03' AND AKTIV('2025-03-31');
SELECT count(*) FROM (SELECT DISTINCT vvh_id, person_id, geburtsdatum, geschlecht, beginn, ende, qual, oenace, bundesland
  FROM roh.lieferung WHERE lieferung='2025-03' AND AKTIV('2025-03-31')) x;
-- VVH_IDs mit mehreren verschiedenen Zeilen (357)
SELECT count(*) FROM (SELECT vvh_id FROM (SELECT DISTINCT * FROM roh.lieferung WHERE lieferung='2025-03') d
  GROUP BY vvh_id HAVING count(*) > 1) x;
```

**Verworfene Alternativen.** Vergleich nur über VVH_ID: würde 357 echte Zeitabschnitte zusammenlegen. Dubletten doppelt zählen: widerspricht Anhang A Nr. 1 und dem Beispielbericht.

**Offene Rückfrage.** R7.

---

## A2 Leere Merkmale sind „unbekannt"

**Befund.** OENACE und BUNDESLAND fehlen in jeder Lieferung immer gemeinsam; es gibt keinen Satz, bei dem nur eines fehlt (gemessen für alle 24 Lieferungen). Je Lieferung sind es 1.742 bis 2.192 Zeilen, am Stichtag 1.587 bis 2.031 (gemessen, ohne 2025-06). Lieferung 2024-08: 1.996 am Stichtag (gemessen). Beispiele: 100355, 100627, 101181. Die Vorgabe nannte 1.587 bis 2.192 als einen Bereich; das mischt Stichtag und ganze Lieferung.

**Annahme.** Ein leeres Feld führt auf die Ausprägung „unbekannt": BUNDESLAND `0` „Bundesland unbekannt", OENACE `UNB` „Wirtschaftszweig unbekannt". Der Satz zählt.

**Begründung.** Fachbeschreibung § 3 und § 5 (unbekannte Werte als eigene Zeile), § 4 Nr. 8; Beispielbericht 2024-08 Tab2 und Tab3 weisen beide Zeilen aus.

**Umgesetzt als.** `Q02_leer_unbekannt` (5 Zeilen in `stat.quellzuordnung`, `geliefert = '<leer>'`), geführt über `E05_quellzuordnung`. Neue, nie gesehene Codes fängt `Q03_sonst_unbekannt` ab.

**Gültigkeit.** Ab Lieferung 2024-08.

**Beleg-SQL.**

```sql
-- gemeinsames Fehlen (Ergebnis: 0 Abweichungen)
SELECT count(*) FROM roh.lieferung WHERE lieferung='2024-08'
  AND (coalesce(oenace,'')='') <> (coalesce(bundesland,'')='');
-- Stichtag 2024-08 (Ergebnis 1996)
SELECT count(*) FROM roh.lieferung WHERE lieferung='2024-08'
  AND coalesce(oenace,'')='' AND coalesce(bundesland,'')='' AND AKTIV('2024-08-31');
-- Bereich je Lieferung am Stichtag (Ergebnis 1587 bis 2031): wie oben, gruppiert nach lieferung
```

**Verworfene Alternativen.** Sätze ohne Merkmale ausschließen: verliert Verhältnisse, die der Beispielbericht zählt. Ersatzwert raten oder aus anderen Quellen ergänzen: Zahlen entstehen nur aus den Daten und den Regeln, ein geratener Wert wäre nicht belegbar.

**Offene Rückfrage.** Keine.

---

## A3 ÖNACE-2003-Unterabschnitte gehören zu C

**Befund.** Die Lieferungen enthalten Altcodes der ÖNACE 2003: DA, DB, DC, DD, DF, DG, DH, DI, DJ, DK, DL, DM. In 2024-08 sind es 50 Sätze am Stichtag (gemessen: DA 8, DB 2, DC 4, DD 5, DF 4, DG 1, DH 4, DI 3, DJ 7, DK 6, DL 5, DM 1). Über alle Lieferungen am Stichtag 40 bis 51 (gemessen, ohne 2025-06). Die Vorgabe nannte 50 je Lieferung. Abschnitt C hat in 2024-08 62.154 Sätze mit Code C (gemessen); mit den 50 Altcodes sind es 62.204 wie im Beispielbericht (Quelle: Beispielbericht Tab3). Umsteiger 2003 nach 2008: die 6-Steller gehen mehrheitlich nach C, DA 49 von 49 (Quelle: Lead-Gegenrechnung bzw. Forensik 05.11.). DE und DN kommen in keiner Lieferung vor (gemessen) und sind nach derselben Mehrheitsregel C zugeordnet (siehe unten). Beispiele: 100216, 1005, 101214.

**Annahme.** DA bis DN (Sachgütererzeugung) zählen zum Abschnitt C „Herstellung von Waren", in ÖNACE 2008 und ab 2025 auch in ÖNACE 2025. D allein bleibt D (Energieversorgung).

**Begründung.** Fachbeschreibung § 4 Nr. 8 (fehlende oder abweichende Angaben nach begründeten Annahmen); Beispielbericht Tab3 (C = 62.154 + 50).

**Umgesetzt als.** `Q01_oenace_2003_unterabschnitte`, 28 Zeilen in `stat.quellzuordnung` (14 Codes DA–DN mal 2 Versionen).

**Gültigkeit.** Ab Lieferung 2024-08, auch für die Version ÖNACE 2025.

**Beleg-SQL.**

```sql
SELECT oenace, count(*) FROM roh.lieferung WHERE lieferung='2024-08' AND oenace ~ '^D[A-Z]$' GROUP BY 1 ORDER BY 1;
SELECT count(*) FROM roh.lieferung WHERE lieferung='2024-08' AND oenace='C' AND AKTIV('2024-08-31');  -- 62154
SELECT count(*) FROM stat.quellzuordnung q JOIN meta.regel g ON g.id = q.regel_id
 WHERE g.regelsatz = 'v1' AND g.name = 'Q01_oenace_2003_unterabschnitte';  -- 28 (14 Codes × 2 Versionen)
```

**Verworfene Alternativen.** Altcodes als „unbekannt": Tab3 des Beispielberichts würde nicht stimmen. DE und DN gehen nach derselben Mehrheitsregel nach C (DE: 25 von 32 Sechsstellern nach C, 6 nach J; DN: 48 von 61); beide kommen in keiner der 24 Lieferungen vor, die Zuordnung ändert also keine Zahl (Review !13).

**Offene Rückfrage.** Keine (Zuordnung belegt durch Beispielbericht Tab3, Regel `Q01_oenace_2003_unterabschnitte`).

---

## A4 Geburtsmonat 13

**Befund.** Geburtsdaten der Form JJJJ-13-TT. In 2024-08 sind es 370, alle am Stichtag, der Tag liegt zwischen 01 und 28 (gemessen). Je Lieferung ganz 336 bis 444, am Stichtag 305 bis 399 (gemessen). Andere ungültige Geburtsdaten gibt es in 2024-08 nicht (gemessen, 0). Beispiele: 101551, 102661, 102767.

**Annahme.** Der Geburtstag ist unbekannt: Ersatztag ist der 1. Juli des Geburtsjahres, gezählt wird das vollendete Alter am Stichtag (siehe Nachtrag unten). Für 08/2024 ergibt das dieselben Zahlen wie Berichtsjahr minus Geburtsjahr. Das Geburtsjahr bleibt erhalten, der Satz zählt.

**Begründung.** Beispielbericht 2024-08 Tab13 führt die 370 Fälle in den Altersjahren nach Berichtsjahr minus Geburtsjahr; Variante D der Lead-Gegenrechnung trifft 576 von 576 Zellen (Quelle: Lead-Gegenrechnung bzw. Forensik 05.11.).

**Umgesetzt als.** `E03_datum_pruefen` (Parameter `geburtsmonat_13: geburtsjahr_behalten`, Status `monat_13`) und `R5_alter` (Parameter `geburtsmonat_13: ersatz:07-01`).

**Gültigkeit.** Ab Lieferung 2024-08.

**Beleg-SQL.**

```sql
SELECT count(*) FROM roh.lieferung WHERE lieferung='2024-08' AND substr(geburtsdatum,6,2)='13' AND AKTIV('2024-08-31');  -- 370
SELECT min(substr(geburtsdatum,9,2)), max(substr(geburtsdatum,9,2)) FROM roh.lieferung
  WHERE lieferung='2024-08' AND substr(geburtsdatum,6,2)='13';  -- 01, 28
SELECT count(*) FROM roh.lieferung WHERE lieferung='2024-08'
  AND geburtsdatum !~ '^\d{4}-(0[1-9]|1[0-3])-\d{2}$';  -- 0
```

**Verworfene Alternativen.** Alter „unbekannt": 408 Zellen in Tab13 falsch. Geburtstag noch nicht erreicht, also minus 1: 367 Zellen falsch (beide Quelle: Lead-Gegenrechnung bzw. Forensik 05.11.).

**Offene Rückfrage.** R1 (Ersatztag).

---

## A5 Unplausibles Alter

**Befund.** In 2024-08 haben 7 Sätze am Stichtag ein Alter von 117 bis 153 Jahren (Geburtsjahre ab 1871, gemessen). Beispiele: 149431, 207859, 327231. Echte Hochbetagte kommen ab 2024-09 dazu: vollendete 75 bis 100 Jahre am Stichtag in 2024-09 62, in 2025-03 211, in 2026-07 310 (gemessen, Geburtsjahre 1948 bis 1951). Zwischen 78 und 116 vollendeten Jahren gibt es in keiner Lieferung einen Fall (gemessen über alle Lieferungen außer 2025-06 am Stichtag, 0). Zum Vergleich: Die Jahresdifferenz allein liefert für 2026-01 bis 2026-07 je 2 bis 5 Sätze mit 78; das ist ein Messeffekt (Geburtstag noch nicht erreicht) und kein Altersbereich ohne Lücke.

**Annahme.** Ein Alter über 110 oder unter 0 Jahren gilt als unplausibel und wird als „unbekannt" gezählt. Das Verhältnis zählt. Die Grenze ist ein Regelparameter (`max_plausibel = 110`): eine großzügige eigene Prüfgrenze, kein amtlicher Standard (die ILO empfiehlt keine obere Altersgrenze für Erwerbstätige). Für alle 24 Lieferungen liefern 100 und 110 dieselben Zahlen.

**Begründung.** Beispielbericht 2024-08 Tab13: nur die 7 Fälle mit 117 bis 153 Jahren stehen unter „unbekannt"; für 2024-08 liefern die Grenzen 74 und 100 dieselben Zahlen (Zeile „75 u. mehr" = 0). Fachbeschreibung § 4 Nr. 5.

**Umgesetzt als.** `R5_alter`, Parameter `{"bezug": "bis", "geburtsmonat_13": "ersatz:07-01", "max_plausibel": 110, "min_plausibel": 0}`.

**Gültigkeit.** Ab Lieferung 2024-08. Ab 2024-09 kommt es darauf an, dass die Grenze über 77 Jahren liegt; 100 und 110 liefern dieselben Zahlen.

**Beleg-SQL.**

```sql
-- 7 Fälle in 2024-08 (Ergebnis 7, Alter 117 bis 153, ältestes Geburtsjahr 1871)
SELECT count(*), min(2024-left(geburtsdatum,4)::int), max(2024-left(geburtsdatum,4)::int), min(left(geburtsdatum,4))
FROM roh.lieferung WHERE lieferung='2024-08' AND AKTIV('2024-08-31') AND 2024-left(geburtsdatum,4)::int > 100;
-- vollendetes Alter 75..100 am Stichtag (62 / 211 / 310): al = Jahresdifferenz bei Monat 13, sonst extract(year from age(st, geburtsdatum::date))
-- Lücke 78..116 vollendet, alle Lieferungen ohne 2025-06: Ergebnis 0
```

**Verworfene Alternativen.** Grenze „Alter über 74": würde ab 2024-09 echte 75- bis 77-Jährige als Fehler zählen. Keine Grenze: 7 Fälle mit 117 bis 153 Jahren stünden in den Altersjahren und Tab13 stimmte nicht.

**Offene Rückfrage.** R6.

---

## A6 Spaltentausch BEGINN und ENDE in 2025-06

**Befund.** Lieferung 2025-06: BEGINN ist bei 388.115 von 432.086 Zeilen leer, BEGINN liegt bei 43.914 Zeilen nach ENDE, ENDE ist immer gefüllt (alle gemessen). Die Nachbarlieferungen 2025-05 und 2025-07 haben 0 leere BEGINN (gemessen). Ohne Tausch bestehen am 30.06.2025 nur 21 Verhältnisse, nach dem Tausch 394.252 (beide gemessen). Die Nachbarmonate haben 390.001 und 397.419 (Quelle: Lead-Gegenrechnung bzw. Forensik 05.11.).

**Annahme.** Die Spalten wurden vertauscht geliefert. BEGINN und ENDE werden für die ganze Lieferung getauscht. Die Schwellen sind Parameter: mehr als 50 % BEGINN leer und mehr als 5 % BEGINN nach ENDE.

**Begründung.** Anhang A Nr. 1 (kein Verhältnis geht verloren); Fachbeschreibung § 2 (Felder BEGINN/ENDE).

**Umgesetzt als.** `E01_spaltentausch_beginn_ende`, Parameter `{"anteil_beginn_leer_min": 0.5, "anteil_beginn_nach_ende_min": 0.05}`. Danach greift `E04_beginn_fehlt` für einzelne fehlende BEGINN; nach dem Tausch gibt es dafür laut Regeltext 0 Fälle.

**Gültigkeit.** Ab Lieferung 2024-08, ausgelöst nur in 2025-06.

**Beleg-SQL.**

```sql
SELECT count(*), count(*) FILTER (WHERE coalesce(beginn,'')=''), count(*) FILTER (WHERE beginn>ende),
       count(*) FILTER (WHERE coalesce(ende,'')='') FROM roh.lieferung WHERE lieferung='2025-06';  -- 432086, 388115, 43914, 0
SELECT count(*) FROM roh.lieferung WHERE lieferung='2025-06' AND beginn<>'' AND beginn<='2025-06-30'
  AND (coalesce(ende,'')='' OR ende>='2025-06-30');  -- ohne Tausch: 21
SELECT count(*) FROM roh.lieferung WHERE lieferung='2025-06' AND ende<>'' AND ende<='2025-06-30'
  AND (coalesce(beginn,'')='' OR beginn>='2025-06-30');  -- nach Tausch: 394252
```

**Verworfene Alternativen.** Nur die Zeilen mit leerem BEGINN tauschen: ließe 43.914 Zeilen mit BEGINN nach ENDE zurück. BEGINN durch Fensterbeginn ersetzen (`E04`): würde alle 388.115 Verhältnisse mit falschem Beginn zählen und die Enddaten verwerfen.

**Offene Rückfrage.** R5.

---

## A7 Abschnittswahl am Stichtag

**Befund.** Hat ein Verhältnis mehrere Abschnitte, schließen sie in der Regel lückenlos an. Je Lieferung gibt es 0 bis 7 Lücken und 0 bis 4 Überlappungen (Quelle: Lead-Gegenrechnung bzw. Forensik 05.11.). Am Stichtag hat in 2024-08 keine VVH_ID mehr als einen aktiven Abschnitt (gemessen, 0).

**Annahme.** Bestehen mehrere Abschnitte, gelten die Merkmale des Abschnitts mit dem spätesten BEGINN. Bei Gleichstand entscheidet das späteste oder offene ENDE, dann die Codes aufsteigend. Jedes Verhältnis zählt einmal.

**Begründung.** Fachbeschreibung § 4 Nr. 3; Anhang A Nr. 1; Technische Regel 1 (zwei Läufe mit gleichen Daten liefern gleiche Zahlen, daher vollständige Ordnung).

**Umgesetzt als.** `R1_R3_verhaeltnis_einmal`, Parameter `{"ordnung": "spaetester_beginn"}`.

**Gültigkeit.** Ab Lieferung 2024-08. Die Tie-Breaker sind heute wirkungslos (0 am Stichtag), sichern aber den Determinismus für künftige Lieferungen.

**Beleg-SQL.**

```sql
SELECT count(*) FROM (SELECT vvh_id FROM roh.lieferung WHERE lieferung='2024-08' AND AKTIV('2024-08-31')
  GROUP BY 1 HAVING count(*)>1) x;  -- 0
```

**Verworfene Alternativen.** Frühester Beginn: widerspricht „Abschnitt am Stichtag". Zufällige Wahl: nicht deterministisch.

**Offene Rückfrage.** Keine.

---

## A8 Abrechnung mit Zeile „nicht gezählt"

**Befund.** Lieferung 2024-08: 392.284 Zeilen gelesen, 392.236 am Stichtag gezählt, 48 nicht am Stichtag aktiv (ENDE zwischen 01.08. und 30.08.2024), 0 ausgeschlossen (alle gemessen; 392.284 = 392.236 + 48).

**Annahme.** Der Qualitätsbericht weist die Abrechnung vollständig aus: gelesen, gezählt, nicht am Stichtag aktiv, ausgeschlossen. Die Vorlage des Veranstalters hat keine Zeile „nicht gezählt"; wir ergänzen sie, damit die Bilanz aufgeht.

**Begründung.** Fachbeschreibung § 4 Nr. 1, 2, 4; Beispielbericht Tab1 (392.236).

**Umgesetzt als.** `R2_R4_stichtag_eigene_lieferung`, Parameter `{"zeitraum_art": "Stichtag", "lieferung": "eigene"}`. Die Zusatzzeile ist Berichtsformat und keine eigene Regel.

**Gültigkeit.** Ab Lieferung 2024-08.

**Beleg-SQL.**

```sql
SELECT count(*), count(*) FILTER (WHERE AKTIV('2024-08-31')),
       count(*) FILTER (WHERE ende<>'' AND ende<'2024-08-31')
FROM roh.lieferung WHERE lieferung='2024-08';  -- 392284, 392236, 48
```

**Verworfene Alternativen.** Die 48 stillschweigend weglassen: Bilanz im Bericht ginge nicht auf.

**Offene Rückfrage.** Keine.

---

## A9 Lieferung 2024-08 ist kein Drei-Monats-Vollabzug

**Befund.** Das kleinste ENDE in 2024-08 ist der 01.08.2024. Enden im Juni oder Juli 2024 gibt es nicht (beide gemessen, 0). Die Lieferung enthält also nur Verhältnisse, die im August noch bestanden. Vor dem Monatsletzten enden in 2024-08 nur 48 Verhältnisse, in den anderen 23 Lieferungen je 6.614 bis 17.664 im eigenen Monat (gemessen; 17.664 ist 2025-06 mit Spaltentausch, sonst höchstens 9.180).

**Annahme.** 2024-08 ist eine Erstlieferung, kein Vollabzug über drei Monate. Das hat auf die Zählung am Stichtag keine Wirkung. Bei der Zählung über den ganzen Monat (Auftrag 2, Regelsatz v2) bringt 2024-08 nur 48 Verhältnisse mehr als der Stichtag (392.284 statt 392.236), 2024-09 dagegen 7.746 (gemessen in `stat.stat_beschaeftigte`). Die Monatszahl August 2024 kann deshalb zu niedrig sein; wie viele Verhältnisse fehlen, ist nicht gemessen. Ergänzt wird nicht, weil ein Monat keine spätere Lieferung nutzen darf. Annahme F9 und Rückfrage R9 (`meta.annahme`, `meta.rueckfrage`). Eine früher genannte Größe von „rund 8.000 zu niedrig“ ist nicht belegt: Lieferung 2024-09 kennt nur 36 im August endende Verhältnisse, und ihre Revision für August beträgt +684 (unabhängiges Orakel).

**Begründung.** Messung an den Daten (Beleg-SQL); Fachbeschreibung § 2 beschreibt die Lieferung als Abzug über drei Monate, die Daten bestätigen das für 2024-08 nicht.

**Umgesetzt als.** `R2_R4_stichtag_eigene_lieferung` rechnet aus der Lieferung des Berichtsmonats (`"lieferung": "eigene"`). Die Beschränkung auf eigene und frühere Lieferungen steht in den Leitlinien. Eine eigene Regel für Auftrag 2 gibt es noch nicht.

**Gültigkeit.** Lieferung 2024-08.

**Beleg-SQL.**

```sql
SELECT min(ende), count(*) FILTER (WHERE ende BETWEEN '2024-06-01' AND '2024-07-31')
FROM roh.lieferung WHERE lieferung='2024-08' AND ende<>'';  -- 2024-08-01, 0
SELECT lieferung, count(DISTINCT vvh_id) FROM roh.lieferung
WHERE ende ~ '^\d{4}-\d{2}-\d{2}$' AND left(ende, 7) = lieferung
  AND ende < to_char(to_date(lieferung, 'YYYY-MM') + interval '1 month - 1 day', 'YYYY-MM-DD')
GROUP BY lieferung ORDER BY lieferung;  -- 2024-08: 48; übrige 6.614 bis 17.664
```

**Verworfene Alternativen.** Annahme eines Vollabzugs: würde Zeiträume mit fehlenden Beendigungen als durchgehend beschäftigt zählen.

**Offene Rückfrage.** Keine.

---

## A10 Phantom-Doppelmeldungen

**Befund.** Im VVH_ID-Bereich 859780 bis 864885 haben Sätze ein zweites Verhältnis derselben Person. In 2024-08 sind es 196 Sätze im Bereich (gemessen), alle 196 haben ein zweites Verhältnis mit gleichem Personenschlüssel, Geburtsdatum und Geschlecht (gemessen). Über alle Felder außer VVH_ID hinweg ist keines davon identisch (gemessen, 0); worin sich die Paare unterscheiden, ist nicht aufgeschlüsselt. Der Bereich kommt in allen 24 Lieferungen vor, mit 131 bis 218 Sätzen je Lieferung (gemessen). Die Vorgabe nannte etwa 213 je Lieferung und „nur eine Lieferung sichtbar"; beides hält die Messung nicht ohne Weiteres. Die Deutung stammt aus der Forensik und ist hier nicht bestätigt.

**Annahme.** Die Verhältnisse zählen. Gezählt werden Verhältnisse, nicht Personen. Der Beispielbericht zählt sie ebenfalls mit. Im Qualitätsbericht stehen sie als Auffälligkeit.

**Begründung.** Zählregel 1 (Verhältnisse, nicht Personen); Beispielbericht 2024-08.

**Zählweise im Qualitätsbericht.** Die Prüfregel `P19_phantom_doppelmeldung` zählt nicht den Kennungsbereich, sondern alle Verhältnisse mit Beginn im Berichtsmonat, deren Person am Stichtag ein zweites Verhältnis mit gleicher Qualifikation, Branche und gleichem Bundesland hat: 216 bis 322 je Monat, 216 in 2024-08, davon 196 im Kennungsbereich (gemessen in `meta.pruefung_treffer` und `bereinigt.abschnitt`). Rückfrage R8 nennt seit 05.11.2026 dieselbe Zählung.

**Umgesetzt als.** `R1_R3_verhaeltnis_einmal` zählt jede VVH_ID einmal; die Ausweisung als Auffälligkeit liegt im Berichtsformat und hat keine eigene Regel.

**Gültigkeit.** Ab Lieferung 2024-08.

**Beleg-SQL.**

```sql
SELECT count(*) FROM roh.lieferung WHERE lieferung='2024-08' AND vvh_id ~ '^\d+$'
  AND vvh_id::int BETWEEN 859780 AND 864885;  -- 196
SELECT count(*) FROM roh.lieferung a WHERE a.lieferung='2024-08' AND a.vvh_id ~ '^\d+$'
  AND a.vvh_id::int BETWEEN 859780 AND 864885
  AND EXISTS (SELECT 1 FROM roh.lieferung b WHERE b.lieferung='2024-08' AND b.vvh_id<>a.vvh_id
              AND b.person_id=a.person_id AND b.geburtsdatum=a.geburtsdatum AND b.geschlecht=a.geschlecht);  -- 196
SELECT min(c), max(c) FROM (SELECT count(*) c FROM roh.lieferung WHERE vvh_id ~ '^\d+$'
  AND vvh_id::int BETWEEN 859780 AND 864885 GROUP BY lieferung) x;  -- 131, 218
```

**Verworfene Alternativen.** Zweites Verhältnis streichen: Beispielbericht und Zählregel 1 widersprechen. Stillschweigend mitzählen: die Auffälligkeit bliebe unsichtbar.

**Offene Rückfrage.** Keine.

---

## Datenanfragen: Sprachverständnis

Die Synonym- und Signalwortlisten in `uc3/statagent/frage.py` (Branchennamen, Geschlecht, nicht ausgewertete Merkmale, Füllwörter) sind Sprachverständnis, kein Rechenregelwerk: Sie entscheiden nur, welche Frage verstanden wurde, nie, wie gezählt wird.

## Anhang: Stand der Regelfreigabe

```sql
SELECT id, name, gueltig_ab_lieferung, aktiv, freigegeben_von IS NOT NULL AS freigegeben FROM meta.regel ORDER BY id;
-- Ergebnis 05.11.2026, Regelsatz v1: 15 Einlese-, Zuordnungs- und Zählregeln (7 + 3 + 5) und 24 Prüfregeln, alle aktiv, gueltig_ab 2024-08, freigegeben: f
```

## Abweichungen der Messung von den übernommenen Zahlen

| Nr. | Vorgabe | Messung 05.11.2026 | Bemerkung |
|---|---|---|---|
| A2 | 1.587 bis 2.192 je Lieferung | Zeilen gesamt 1.742 bis 2.192; am Stichtag 1.587 bis 2.031 | Bereich mischt zwei Bezugsgrößen |
| A3 | 50 je Lieferung | 40 bis 51 am Stichtag, 50 in 2024-08 | |
| A4 | 336 bis 444 je Lieferung | gesamt 336 bis 444; am Stichtag 305 bis 399 | 2024-08: 370 stimmt |
| A5 | keine Fälle 78 bis 116 Jahre | stimmt für vollendetes Alter; nach Jahresdifferenz 2 bis 5 Fälle mit 78 in 2026-01 bis 2026-07 | Zahlen 62 / 211 / 310 bestätigt |
| A10 | etwa 213 je Lieferung, nur eine Lieferung sichtbar | 131 bis 218 je Lieferung, Bereich in allen 24 Lieferungen | Deutung nicht bestätigt; der Qualitätsbericht (P19) zählt 216 bis 322 je Monat, siehe A10 |

## Nachtrag 05.11.2026 nachmittags (Review !13, Recherche zu den Rückfragen)

| Nr. | Änderung | Regel | Wirkung |
|---|---|---|---|
| A4 | Geburtsmonat 13: Ersatztag **1. Juli** des Geburtsjahres, vollendetes Alter (Jahresmitte, beste Schätzung bei nur bekanntem Jahr; Praxis z. B. NHS England, Person Birth Date). Vorher Jahresdifferenz (= Ersatztag Jänner). | `R5_alter` (`geburtsmonat_13 = ersatz:07-01`) | 08/2024 unverändert (Tab13 576/576, Golden Set grün); in Berichtsmonaten Jänner bis Juni sind die betroffenen Personen ein Jahr jünger als nach Jahresdifferenz. Rückfrage R1 bleibt offen. |
| A5 | Plausibilitätsgrenze **110** statt 100 Jahre | `R5_alter` (`max_plausibel = 110`) | keine Zahl ändert sich (zwischen 78 und 116 Jahren gibt es keinen Fall) |
| A11 | Ungültiges ENDE (z. B. `2024-02-30`): Monatsletzter von JJJJ-MM (`2024-02-29`); nur ein unlesbares ENDE gilt als „läuft“. Datumsprüfung per Muster `JJJJ-MM-TT` plus gültiges Datum (`today`, `infinity` gelten nicht). | `E06_ende_ungueltig`, `E03_datum_pruefen` | 0 Fälle in 24 Lieferungen (gemessen), Beleg: `SELECT count(*) FROM roh.lieferung WHERE ende IS NOT NULL AND NOT (ende ~ '^[0-9]{4}-[0-9]{2}-[0-9]{2}$' AND pg_input_is_valid(ende, 'date'));` = 0, ebenso für BEGINN außer 2025-06 vor dem Spaltentausch |
| A12 | Fortschreibung bei belegtem Lieferausfall: fehlen mehr als 1 % der Vormonats-Verhältnisse (Basis mindestens 1.000) oder fällt eine Qualifikation mit über 100 Verhältnissen ganz aus, werden die fehlenden Verhältnisse **einmalig aus der Vorlieferung** ergänzt, wenn dort ein am neuen Stichtag gültiger Abschnitt vorliegt. Markiert als `herkunft = fortgeschrieben`, getrennt ausgewiesen, Monat bleibt vorläufig, Fortgeschriebenes wird nie weitergetragen. | `E07_fortschreibung_lieferausfall` | betrifft 2025-03 (FD, 1.492 Verhältnisse vom 28.02.) und 2025-10 (Teil-Lieferung, 78.949 fehlende vom 30.09.); P13/P15/P16 messen weiter nur Geliefertes und zeigen den Ausfall. Praxis: einperiodige Fortschreibung (Beschäftigtenpanel der Statistischen Ämter, Metadatenreport § 2.5.3). Rückfragen R3, R4. |
| A13 | Ministeriums-Lieferung (Auftrag 3): Abschnitt C umfasst auch die ÖNACE-2003-Altcodes DA bis DN (Regel Q01), und die angehaltene Teil-Lieferung 2025-10 wird für die Tage übersprungen (Variante S, Entscheid Lead 58, #72). | `Q01_oenace_2003_unterabschnitte`, Parameter `altcodes_als_abschnitt` | **32.741 Personen** (Abgabezahl); ohne Altcodes 32.713; mit der Teil-Lieferung 2025-10 wären es 32.667 bzw. 32.639 (siehe docs/plan/uc3/ministerium-oracle.md). `uc3 ministerium` weist eine Definition ab, deren Altcodes nicht genau Q01 entsprechen oder die angehaltene Lieferungen verwendet; `pruefe-abgabe` liest die fett gesetzte Personenzahl dieser Zeile als Sollzahl für den Beleg. |

## Nachtrag 05.11.2026 abends (Begründungen, F9, Rückfragen)

- Jede Annahme F1 bis F10 trägt in `meta.annahme.grund` einen Grund in einem Satz; Qualitätsbericht und `uc3 annahmen` zeigen ihn als „Grund: …“.
- F9 / R9: Satz neu mit Messung (48 gegen 6.614 bis 17.664, +48 gegen +7.746), ohne ungemessene Größe; siehe A9.
- R8 zählt wie der Qualitätsbericht (216 bis 322 je Monat); R5, R6 und R9 stellen nur noch eine Frage; R7 begründet den Vorschlag.
- Neue Rückfrage R10 zu `P14_sprung_aggregat`: 19 Gruppen in 11 Monaten (2024-09 bis 2026-07) ändern sich ohne Saisongrund um 3,1 bis 7,5 %; bis zur Antwort zählen wie geliefert und als „nicht erklärbar“ kennzeichnen.

## Nachtrag 05.11.2026 nachts (Datenanfragen zum Alter, Review !227)

| Nr. | Änderung | Regel | Wirkung |
|---|---|---|---|
| A14 | Datenanfrage „über 50“ heißt in vollendeten Jahren **51 Jahre und älter**, „ab 50“ heißt 50 Jahre und älter (Entscheid Review-Bank). Die Antwort nennt die Grenze im Verstanden-Satz. Grenzen unter 14 Jahren gelten nicht als Altersgrenze und werden abgesagt. | keine Zählregel: Sprachverständnis der Datenanfrage (`uc3/statagent/frage.py`) | keine Zahl der Abgabe ändert sich; wer „über 50“ fragt, sieht das Altersjahr 50 nicht mitgezählt |
| A15 | Datenanfrage im Regelsatz v2: Alter und Altersgruppen werden abgesagt, weil der Weg über die Regeln nur Monat, Bundesland, Geschlecht, Branche und Beschäftigungskategorie liest (Review !230). | keine Zählregel: Sprachverständnis der Datenanfrage (`uc3/statagent/frage.py`) | keine Zahl der Abgabe ändert sich |
