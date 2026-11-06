# Fragenkatalog der Fachjury

Der Katalog hilft am Tisch, wenn die Fachjury nachfragt. Er enthält die drei Datenanfragen der Aufgabenstellung, vier geübte Live-Änderungen und die Fragen, die wir erwarten.

Regel: Jede Antwort ist in unter 30 Sekunden lesbar. Aufbau je Frage: Frage, Kurzantwort, Antwortweg, Fundstelle im Repo, Zahlen mit Kennung F….

Die Kennungen F1 bis F25 stehen im Belegregister `belegregister.md`.

Stand der Befehle: `uv run uc3 frage "…"` und die Seite `/uc3/fragen` sind mit MR !61 auf main (#74). Sie rechnen die Antwort ohne Sprachmodell und zeigen Abfrage und Definition. Das SQL unten ist der Rückfall mit `psql`.

## Die acht geprüften Fragen

Nur diese Fragen werden vorgeführt, wörtlich so getippt. Jede Zahl ist gegen eigenes SQL und das unabhängige Orakel nachgerechnet (Prüfung im Team, 05.11.2026 17:15 bis 17:19, #74). Freie Fragen der Jury werden nicht eingetippt, solange der Folge-MR von bb („nie still falsch“) nicht auf main ist. Dann bietet Bernhard eine Frage aus dieser Liste an oder nimmt das SQL aus Teil A.

| Nr. | Frage | Sollzahl | Kennung |
|---|---|---|---|
| 1 | „Zeigen Sie mir die Zeitreihe der Beschäftigten, jeweils zum Monatsletzten.“ | 24 Werte, erster Wert August 2024 392.236, letzter Wert Juli 2026 399.027 | F14, F21 |
| 2 | „Wie viele Männer und Frauen sind im August 2024 je Bundesland beschäftigt?“ | Männer 211.603, Frauen 180.633 | F14 |
| 3 | „Männer und Frauen im Juli 2026“ | Männer 213.129, Frauen 185.898 | F22 |
| 4 | „Wie hoch ist die Fluktuation je Wirtschaftsbereich im Oktober 2024?“ | 3,42 % (12.215 Zugänge, 14.557 Abgänge, Bestand 391.033) | F23 |
| 5 | „Wie viele Beschäftigte gab es im März 2025 in Wien im Gesundheits- und Sozialwesen?“ | 7.498, vorläufig | F18 |
| 6 | „Beschäftigte nach Branche im Juli 2026“ | 23 Werte, Summe 399.027, Bau 28.548 | F24 |
| 7 | „Was ist ÖNACE R?“ | ÖNACE 2025: Gesundheits- und Sozialwesen; ÖNACE 2008: Kunst, Unterhaltung und Erholung | F13 |
| 8 | „Zeitreihe Bau 2025“ | Werte 23.809 bis 24.679 | F25 |

Gegenprobe mit ehrlicher Absage: „Entwicklung im Bau seit August 2024“. Das Programm sagt ab, weil die Branchen ab 2025 nach ÖNACE 2025 gezählt werden (F13).

Freie Fragen, Stand 05.11.2026 (Testserver, `main` `fd936b3`): Zwei Werte eines Merkmals („Wien und Tirol“), „Durchschnittsalter“, Fluktuation mit Filter und Fragen nach einer Person sagt das Programm ehrlich ab.

Alter geht seit !227, online gemessen 06.11.2026 00:45 auf main `2005e01`: „Wie viele Beschäftigte unter 25 Jahren gab es im Juli 2026?“ 41.626, „Wie viele 30-Jährige gab es im August 2024?“ 9.017, „Beschäftigte ab 50 Jahren im Juli 2026“ 124.728. Falle: „über 50“ heißt 51 Jahre und älter (115.451), „ab 50“ ohne „Jahren“ sagt ab. Gegen das Orakel ist das nicht belegt, Entscheid um 06:45.

Nicht vorführen, weil eine Zahl kommt, aber nicht gegen das Orakel geprüft ist: Branchen in Umgangssprache („Gastronomie“), „freie Dienstverträge“ und Zeiträume („von März bis Juni 2025“). Um 06:45 neu messen.

## Gemeinsame Bausteine für das SQL

Die Ergebnis-Tabelle heißt `stat.stat_beschaeftigte` (Long-Format: eine Zeile je Zelle). Wichtige Spalten: `zeitraum_art`, `zeitraum_bis` (der Stichtag), `region` (Bundesland, `0` = unbekannt), `oenace` (Abschnitt, `UNB` = unbekannt), `oenace_version`, `geschlecht` (`M`, `W`, `U`), `variable`, `wert`, `status`, `stand`, `regelstand`.

Der Bestand heißt in der Spalte `variable` `Beschaeftigungsverhaeltnisse`. Zähleinheit ist das Versicherungsverhältnis, Stichtag der Monatsletzte.

Den Regelstand des jüngsten Laufs holen alle Abfragen so:

```sql
SELECT regelstand FROM meta.lauf
WHERE regelsatz = 'v1' AND status IN ('fertig', 'unveraendert')
ORDER BY id DESC LIMIT 1
```

In den Abfragen unten steht dafür `<regelstand>`. Beim Üben zuerst diese Abfrage laufen lassen und den Wert einsetzen.

## Teil A: Die drei Datenanfragen

### A1 Zeitreihe: Bestand je Monatsletzter, 08/2024 bis 07/2026

**Frage:** „Zeigen Sie mir die Zeitreihe der Beschäftigten, jeweils zum Monatsletzten.“

**Kurzantwort:** Das ist eine Summe über alle Zellen des jeweiligen Stichtags. Jeder Monat kommt aus seiner eigenen Lieferung. Monate mit auffälliger Lieferung stehen als vorläufig im Ergebnis, nicht als Lücke.

**Antwortweg:** `/uc3/fragen` oder `uv run uc3 frage` mit Frage 1 der Liste oben. Rückfall: psql mit diesem SQL.

```sql
SELECT zeitraum_bis           AS stichtag,
       sum(wert)              AS bestand,
       string_agg(DISTINCT status, ', ') AS status
FROM stat.stat_beschaeftigte
WHERE regelsatz = 'v1'
  AND regelstand = '<regelstand>'
  AND zeitraum_art = 'Stichtag'
  AND variable = 'Beschaeftigungsverhaeltnisse'
  AND stand = 'Lieferung ' || to_char(zeitraum_bis, 'YYYY-MM')
  AND zeitraum_bis BETWEEN DATE '2024-08-31' AND DATE '2026-07-31'
GROUP BY zeitraum_bis
ORDER BY zeitraum_bis;
```

**Fundstelle im Repo:** `uc3/db/030_bereinigt_stat.sql` (Tabelle), `uc3/statagent/zaehlung.py` (Zählregel), `abgabe/aggregationen_v1.xlsx` (alle Monate als Sheet).

**Zahlen:** Erste Zeile muss 392.236 ergeben (F2). Datenbasis 24 Monatslieferungen (F3). Alle anderen Monate: Ergebnis live aus der Abfrage.

**Hinweis:** Die Regel-Freigabe macht keinen Monat endgültig. Jeder Lauf ist vorläufig (`uc3/statagent/lauf.py`, Zeile 151 bis 152). Endgültig wird ein Monat nur mit `uv run uc3 veroeffentlichen --lieferung JJJJ-MM --name "…"` (`uc3/statagent/cli.py`, Zeile 300). Danach ist er unveränderlich. Bei 2025-03 und 2025-10 wurde fortgeschrieben, weil Teile der Lieferung fehlten (F9, F11). Solche Monate veröffentlicht der Befehl nicht ohne Weiteres. Ob veröffentlicht wird, entscheidet der Lead.

### A2 Männer und Frauen je Bundesland, ein Monat

**Frage:** „Wie viele Männer und Frauen sind im August 2024 je Bundesland beschäftigt?“

**Kurzantwort:** Die Zahlen kommen aus derselben Tabelle, gegliedert nach `region` und `geschlecht`. Die Summe stimmt mit dem Gesamtbestand überein. Die Zeile „Bundesland unbekannt“ bleibt sichtbar.

**Antwortweg:** `/uc3/fragen` oder `uv run uc3 frage` mit Frage 2 (August 2024) oder Frage 3 (Juli 2026). Rückfall: psql mit diesem SQL. Für einen anderen Monat das Datum und `stand` tauschen.

```sql
SELECT r.bezeichnung AS bundesland,
       sum(s.wert) FILTER (WHERE s.geschlecht = 'M') AS maenner,
       sum(s.wert) FILTER (WHERE s.geschlecht = 'W') AS frauen,
       sum(s.wert)                                   AS gesamt
FROM stat.stat_beschaeftigte s
JOIN stat.klass_region r ON r.version = 'BL' AND r.code = s.region
WHERE s.regelsatz = 'v1'
  AND s.regelstand = '<regelstand>'
  AND s.zeitraum_art = 'Stichtag'
  AND s.variable = 'Beschaeftigungsverhaeltnisse'
  AND s.zeitraum_bis = DATE '2024-08-31'
  AND s.stand = 'Lieferung 2024-08'
GROUP BY r.code, r.bezeichnung
ORDER BY r.code;
```

**Fundstelle im Repo:** `uc3/db/020_stat_metadaten.sql` (Klassifikationen), `uc3/db/100_klass_daten.sql` (Codes), `uc3/statagent/uc4.py` (gleiche Abfrage ohne Sprachmodell).

**Zahlen (08/2024, F14):** gesamt 392.236 · Männer 211.603 · Frauen 180.633 · Wien 90.799 · Niederösterreich 64.505. Alle übrigen Bundesländer: Ergebnis live aus der Abfrage. Juli 2026: Männer 213.129, Frauen 185.898 (F22).

### A3 Fluktuation je Branche zwischen zwei Stichtagen

**Frage:** „Wie viele Zugänge und Abgänge gab es je Branche zwischen Ende September und Ende Oktober 2024?“

**Kurzantwort:** Ein Zugang ist ein Verhältnis, das am zweiten Stichtag besteht und am ersten nicht. Ein Abgang ist das Gegenteil. Gerechnet wird aus den bereinigten Zeitabschnitten einer Lieferung, die beide Stichtage enthält. Beide Stichtage haben dann dieselbe ÖNACE-Version. Ein Branchenwechsel bei bleibendem Verhältnis zählt weder als Zugang noch als Abgang.

**Antwortweg:** `/uc3/fragen` oder `uv run uc3 frage` mit Frage 4 der Liste oben, Sollzahl 3,42 % (F23). Rückfall: psql mit diesem SQL. Es nimmt die Lieferung 2024-10 mit den Stichtagen 30.09. und 31.10.2024.

```sql
WITH st(tag) AS (VALUES (DATE '2024-09-30'), (DATE '2024-10-31')),
bestand AS (
  SELECT DISTINCT ON (a.vvh_id, st.tag)
         a.vvh_id, st.tag, a.oenace, a.oenace_version
  FROM bereinigt.abschnitt a
  JOIN st ON a.beginn <= st.tag AND (a.ende IS NULL OR a.ende >= st.tag)
  WHERE a.lieferung = '2024-10' AND a.regelsatz = 'v1'
  ORDER BY a.vvh_id, st.tag, a.beginn DESC
),
zugang AS (
  SELECT b2.oenace_version, b2.oenace, count(*) AS n
  FROM bestand b2
  WHERE b2.tag = DATE '2024-10-31'
    AND NOT EXISTS (SELECT 1 FROM bestand b1
                    WHERE b1.vvh_id = b2.vvh_id AND b1.tag = DATE '2024-09-30')
  GROUP BY 1, 2
),
abgang AS (
  SELECT b1.oenace_version, b1.oenace, count(*) AS n
  FROM bestand b1
  WHERE b1.tag = DATE '2024-09-30'
    AND NOT EXISTS (SELECT 1 FROM bestand b2
                    WHERE b2.vvh_id = b1.vvh_id AND b2.tag = DATE '2024-10-31')
  GROUP BY 1, 2
)
SELECT coalesce(z.oenace, a.oenace)                AS abschnitt,
       k.bezeichnung                               AS branche,
       coalesce(z.n, 0)                            AS zugaenge,
       coalesce(a.n, 0)                            AS abgaenge,
       coalesce(z.n, 0) - coalesce(a.n, 0)         AS saldo
FROM zugang z
FULL JOIN abgang a ON a.oenace_version = z.oenace_version AND a.oenace = z.oenace
LEFT JOIN stat.klass_oenace k
       ON k.version = coalesce(z.oenace_version, a.oenace_version)
      AND k.code = coalesce(z.oenace, a.oenace)
ORDER BY 1;
```

**Wechsel der ÖNACE-Version (F13):** Klassifikationswechsel ÖNACE 2008 → 2025 ab Lieferung 2025-01, auch rückwirkend für Dezember 2024. Deshalb gilt für Fluktuation über den Jahreswechsel: beide Stichtage aus derselben Lieferung nehmen (zum Beispiel 31.12.2024 und 31.01.2025 aus Lieferung 2025-01) oder die Umsteiger ausdrücklich nennen. Zwei Monate aus Lieferungen mit verschiedener ÖNACE-Version nie Abschnitt gegen Abschnitt vergleichen.

**Grenze der Skizze:** Abschnitte, die bei einem Lieferausfall aus der Vorlieferung fortgeschrieben wurden (Spalte `herkunft`), zählen mit. Jeder Lauf ist vorläufig, bis ein Monat veröffentlicht ist. Für 2025-03 und 2025-10 den Hinweis „vorläufig“ besonders mitsagen (F9, F11).

**Fundstelle im Repo:** `uc3/db/030_bereinigt_stat.sql` (Tabelle `bereinigt.abschnitt`), `uc3/db/035_herkunft.sql`, `docs/plan/uc3/annahmen.md`.

**Zahlen:** Ergebnis live aus der Abfrage.

## Teil B: Fünf geübte Live-Änderungen

Beim Üben nur bis `vorschlag zeigen`, dann `ablehnen`. Vor der Jury nie `freigabe` üben: Es aktiviert den Regelsatz v2 und committet, einen Reset-Befehl gibt es nicht.

Ablauf immer gleich: Satz sprechen, `agent` erzeugt nur einen Vorschlag, `vorschlag zeigen` zeigt Regel-Unterschied und Zahlen vorher und nachher, `freigabe` macht ihn wirksam. Änderungen landen im Regelsatz `v2`, `v1` bleibt unverändert. Die Freigabe schreibt einen gespeicherten Änderungsschritt im Repo (Commit) mit dem Vermerk `Freigegeben-von`.

Befehle (Fundstelle jeweils `uc3/statagent/cli.py` und `uc3/statagent/agenten/`):

```bash
uv run uc3 agent "<Auftrag>" --probe JJJJ-MM
uv run uc3 vorschlag zeigen <id>
uv run uc3 freigabe <id> --name "Bernhard Götzendorfer"
uv run uc3 ablehnen <id> --name "Bernhard Götzendorfer" --begruendung "…"
```

Der Vorschlag kommt vom Modell. Welche Regel und welchen Wert es wählt, zeigt `vorschlag zeigen`. Die Angaben unten sind die Erwartung. Weicht der Vorschlag ab, lesen wir den Unterschied vor und lehnen ab, wenn er nicht passt.

### B1 Altersgrenze für unplausible Alter senken

**Satz der Jury:** „Setzen Sie die Altersgrenze für unplausible Alter auf 100 Jahre.“

**Befehl:** `uv run uc3 agent "Setze die Altersgrenze für unplausible Alter auf 100 Jahre." --probe 2024-08`

**Was der Vorschlag ändert:** Regel `R5_alter` (Typ `zaehl`), Parameter `max_plausibel` von 110 auf 100.

**Erwartete Wirkung:** Die Zahlen bleiben gleich. Zwischen 78 und 116 Jahren gibt es in keiner Lieferung einen Fall, 100 und 110 liefern dieselben Zahlen (F5). Die 7 Verhältnisse mit 117 bis 153 Jahren zählen weiter als „Alter unbekannt“ (F5). Gut für den Beleg, dass die Probe „vorher gleich nachher“ zeigt.

**Freigabe:** `uv run uc3 freigabe <id> --name "Bernhard Götzendorfer"`

### B2 Geburtsmonat 13: nur mit der Differenz der Jahre rechnen

**Satz der Jury:** „Rechnen Sie bei Geburtsmonat 13 nur mit der Differenz der Jahre, nicht mit dem 1. Juli.“

**Befehl:** `uv run uc3 agent "Rechne bei Geburtsmonat 13 nur mit der Differenz der Jahre (Jahresdifferenz) statt mit dem 1. Juli." --probe 2026-06`. Der Vorschlag selbst ist am 05.11.2026 18:20 bis 18:25 mit dem Stand von !50 geprobt, 3 von 3 gültig, damals mit 2025-03. Diesen Monat nicht mehr nehmen, siehe unten.

**Was der Vorschlag ändert:** Regel `R5_alter`, Parameter `geburtsmonat_13` von `ersatz:07-01` auf `jahresdifferenz`. Der Agent darf für diesen Parameter nur `jahresdifferenz` oder `unbekannt` vorschlagen (`uc3/statagent/agenten/koordinator.py`, Zeile 81). Einen anderen Ersatztag wie den 1. Jänner weist er ab.

**Erwartete Wirkung:** Der Gesamtbestand ändert sich nie, nur das Alter einzelner Verhältnisse mit Monat 13. Für August 2024 gilt Jahresdifferenz gleich Ersatztag 1. Juli, der Beispielbericht bleibt exakt (F4). Im Juni 2026 liegt der Stichtag vor dem 1. Juli: Mit Jahresdifferenz sind diese Verhältnisse ein Jahr älter, der Vorschlag zeigt wenige verschobene Altersgruppen, der Gesamtbestand bleibt 403.301 (einmal gemessen von der UC3-Lane, 05.11.2026 22:40, Commit d888e09, bis zum Vorschlag). Juli bis Dezember zeigen keinen Unterschied, das ist fachlich richtig.

**Auf der Seite:** Die Tabelle von „Vorher und nachher ansehen“ zählt Beschäftigungskategorien und bleibt in Juni 2026 gleich. Seit !239 steht darunter: „Die Änderung zeigt sich an anderer Stelle. Altersgruppe 15-24: 42.422 statt 42.428; Altersgruppe 35-44: 98.940 statt 98.946; Altersgruppe 55-64: 74.472 statt 74.466; dazu 3 weitere Zeilen.“ Im Browser gesehen von der UI-Regie, Instanz-Stand 04060ad, 2 min 51 s bis zum Vorschlag. Die Wirkung ist klein: B2 nur nehmen, wenn die Jury genau das wünscht.

**Falle:** Mit `--probe 2025-03` zeigt die Probe 396.762 → 395.292 (−1.470), obwohl sich nur das Alter ändert. In der Probe fehlen die Fortschreibungen von 2025-03 und 2025-10. Der Fix kommt mit !150, die Abgabe ist nicht betroffen.

**Wozu die Übung dient:** Sie zeigt, dass die offene Frage R1 an die Fachabteilung ein Regelparameter ist und keine Programmänderung.

**Freigabe:** `uv run uc3 freigabe <id> --name "Bernhard Götzendorfer"`

### B3 Schwelle des Bestandsrückgangs senken

**Satz der Jury:** „Halten Sie einen Monat schon bei 3 Prozent Bestandsrückgang an, nicht erst bei 5.“

**Befehl:** `uv run uc3 agent "Halte einen Monat schon an, wenn der Bestand um mehr als 3 Prozent unter dem Vormonat liegt." --probe 2026-07`

**Was der Vorschlag ändert:** Prüfregel `P15_bestand_vs_vormonat` (Typ `pruefung`), Parameter `schwelle` von 0.05 auf 0.03.

**Erwartete Wirkung:** Der Bestand ändert sich nicht, eine Prüfregel ändert keine Zahl. Im Juli 2026 bleibt die Gesamtzahl 407.604 (einmal gemessen von der UC3-Lane, 05.11.2026, Commit d888e09, mit fast gleichem Satz). Die Probe zeigt also keinen Unterschied. Das sagen wir dazu: Es ändert sich nur, welche Monate anhalten, und das sieht man in dieser Probe nicht. Nicht mit `--probe 2025-10` proben, dort fehlen in der Probe die Fortschreibungen (siehe B2).

**Freigabe:** `uv run uc3 freigabe <id> --name "Bernhard Götzendorfer"`

### B4 Schwelle des Spaltentauschs anheben

**Satz der Jury:** „Erkennen Sie den Spaltentausch erst, wenn mehr als 80 Prozent der Beginn-Felder leer sind.“

**Befehl:** `uv run uc3 agent "Erkenne den Spaltentausch von Beginn und Ende erst, wenn mehr als 80 Prozent der Beginn-Felder leer sind." --probe 2025-06`

**Was der Vorschlag ändert:** Einleseregel `E01_spaltentausch_beginn_ende`, Parameter `anteil_beginn_leer_min` von 0.5 auf 0.8.

**Erwartete Wirkung:** Die Zahlen bleiben gleich. In 2025-06 sind 388.115 von 432.086 Zeilen ohne Beginn (F10). Das liegt über 80 Prozent, der Tausch greift weiter. Bestand am 30.06.2025 bleibt 394.252 (F10).

**Freigabe:** `uv run uc3 freigabe <id> --name "Bernhard Götzendorfer"`

### B5 Nicht vorführen: Schwelle für verschwundene Ausprägungen anheben

**Satz der Jury, falls er kommt:** „Melden Sie eine verschwundene Ausprägung erst, wenn sie vorher mehr als 2.000 Verhältnisse hatte.“

**Warum nicht als Übung:** Die Probe zeigt nur Zahlen, keine Treffer der Prüfregeln. Dass etwas nicht mehr gemeldet würde, sieht man dort in keinem Monat. Aus dem Code gelesen von der UC3-Lane, nicht gemessen.

**Was wir sagen:** „Eine Prüfregel ändert keine Zahl, die Probe zeigt also keinen Unterschied. Diese Änderung würde ich ablehnen: Die 1.492 freien Dienstverträge vom März 2025 (F9) würden nicht mehr gemeldet.“

**Wenn die Jury das Nein sehen will:** Satz mit `--probe 2026-07` tippen, dann `uv run uc3 ablehnen <id> --name "Bernhard Götzendorfer" --begruendung "Schwelle würde den Ausfall der freien Dienstverträge nicht mehr melden"`. Die Ablehnung steht im Protokoll (`uv run uc3 protokoll --zeigen`).

## Teil C: Weitere Fragen der Fachjury

### C1 Was zählen Sie genau?

**Kurzantwort:** Ein Versicherungsverhältnis zählt einmal, wenn am Stichtag ein Zeitabschnitt besteht. Stichtag ist der Monatsletzte. Der Abschnitt besteht, wenn der Beginn am oder vor dem Stichtag liegt und das Ende leer ist oder am oder nach dem Stichtag liegt. Beispiel 08/2024: 392.284 Zeilen minus 48, die vor dem Stichtag enden, gleich 392.236 (F2).

**Antwortweg:** `uv run uc3 regeln zeigen`, Regeln `R2_R4_stichtag_eigene_lieferung` und `R1_R3_verhaeltnis_einmal`.

**Fundstelle:** `uc3/db/110_regelsatz_v1.sql`, `abgabe/qualitaetsberichte/2024-08.md`.

### C2 Warum nur eigene und frühere Lieferungen?

**Kurzantwort:** Ein Monat darf sich nicht durch spätere Daten ändern. Spätere Lieferungen werden nie verwendet. Zeigen spätere Lieferungen eine Abweichung, steht sie als Revisionsbedarf im Qualitätsbericht (F12).

**Antwortweg:** Regel `R2_R4_stichtag_eigene_lieferung`, Qualitätsbericht 2025-01, Abschnitt 2.

**Fundstelle:** `uc3/db/110_regelsatz_v1.sql`, `abgabe/qualitaetsberichte/2025-01.md`.

### C3 Sieht das Sprachmodell Einzeldaten?

**Kurzantwort:** Nein. Beschäftigte und Geburtsdaten sind Hochrisikodaten, deshalb sieht das Modell nur Regeln, Tabellenaufbau, Klassifikationen und Aggregate. Das Lese-Werkzeug der Agenten verweigert Ergebnisse mit Personen- oder Verhältnis-ID. Kleine Zellen unter 5 erscheinen als „<5“. Jeder Modellaufruf wird protokolliert, nie mit Inhalt.

**Antwortweg:** Datei `abgabe/modelle.md` zeigen.

**Fundstelle:** `abgabe/modelle.md`, `uc3/statagent/agenten/rollen.py`, `uc3/statagent/agenten/werkzeuge.py`.

### C4 Läuft das auch lokal und offline?

**Kurzantwort:** Es läuft lokal wie gefordert, und zusätzlich auf einem Server, den wir selbst betreiben. Die Abgabezahlen sind auf der eigenen Datenbank gerechnet, online läuft nur die Vorführung. Kein Befehl von `uc3 lauf` ruft ein Sprachmodell auf (F16). Nur die Agenten brauchen ein Modell. Sie können es selbst nachbauen: ab einem frischen Klon 36 Minuten, auf einer frischen Datenbank im vorhandenen Klon 24 Minuten, jeweils mit den Datentests (F30).

**Antwortweg:** `uv run uc3 lauf --lieferung 2024-08` ohne Netz zeigen.

**Fundstelle:** `uc3/README.md`, `abgabe/modelle.md`.

### C5 Ist das Ergebnis reproduzierbar?

**Kurzantwort:** Ja. Zwei Läufe mit denselben Daten und Regeln liefern denselben Ergebnis-Hash (F16). Den Hash zeigt `uv run uc3 laeufe`. Gegenprobe zum Beispielbericht: 2.880 von 2.880 Zellen, 0 Abweichungen (F1).

**Antwortweg:** `uv run uc3 laeufe`, `uv run uc3 eichen --lieferung 2024-08`.

**Fundstelle:** `uc3/tests/test_goldenset.py`, `uc3/statagent/ergebnis.py`.

### C6 Welches Modell nutzen Sie, und lässt es sich tauschen?

**Kurzantwort:** Die Agenten laufen standardmäßig auf Azure (gpt-5-4-mini). Über den Schalter `LLM_PROVIDER` geht auch `mistral` oder `ollama`. `mock` liefert feste Antworten für Tests. Schnittstelle und Protokoll bleiben gleich. Das Modell schlägt nur vor, die Rechnung macht das Programm.

**Antwortweg:** `abgabe/modelle.md` zeigen. Der Schalter steht in `.env.example`.

**Fundstelle:** `abgabe/modelle.md`, `shared/py/plattform/llm/`.

### C7 Was passiert, wenn das Modell ausfällt?

**Kurzantwort:** Der Lauf rechnet trotzdem, denn er braucht kein Modell (F16). Es fehlen nur die Vorschläge der Agenten. Der Befehl `agent` meldet den Modellfehler als Meldung, ohne die Daten anzufassen. Dann hilft der Wechsel des Anbieters (`mistral`, `ollama`). `mock` hilft dem Agenten nicht, denn die Fixture `agent.koordinator.json` fehlt (`shared/py/plattform/llm/mock.py`, Zeile 56). In der Demo geht D2 dann auf die Aufzeichnung.

**Antwortweg:** Live zeigen: `uv run uc3 lauf --lieferung 2024-08` läuft, `agent` meldet den Fehler.

**Fundstelle:** `uc3/statagent/cli.py` (Befehl `agent`), `uc3/tests/test_cli_agenten.py`.

### C8 Was ist mit bereits Veröffentlichtem?

**Kurzantwort:** Ist ein Monat veröffentlicht, bleibt seine Zahl, die Datenbank schützt ihn durch einen Trigger. Veröffentlicht wird nur mit `veroeffentlichen`, vorher ist jeder Lauf vorläufig. Sehen spätere Lieferungen andere Werte, steht die Abweichung als Revisionsbedarf im Qualitätsbericht. Beispiel Dezember 2024: minus 260 Verhältnisse, also 387.390 laut Lieferung 2024-12 gegen 387.130 nach Lieferung 2025-01 (F12). Im Bericht 2025-01 steht Dezember 2024 noch als „387.390 (vorläufig)“.

**Antwortweg:** `uv run uc3 berichte --lieferung 2025-01 --zeigen`.

**Fundstelle:** `uc3/db/030_bereinigt_stat.sql` (Trigger `stat_besch_endgueltig`), `abgabe/qualitaetsberichte/2025-01.md`.

### C9 Wie behandelt ihr den ÖNACE-Wechsel?

**Kurzantwort:** Klassifikationen tragen eine Gültigkeit (`stat.klass_oenace`, Spalten `version`, `gueltig_von`, `gueltig_bis`). Der Wirtschaftszweig wird nach der Version ausgewiesen, die im Berichtsmonat gilt: bis 12/2024 ÖNACE 2008, ab 01/2025 ÖNACE 2025. Das regelt Regel `R7_oenace_nach_berichtsmonat`. Der Wechsel gilt ab Lieferung 2025-01, auch rückwirkend für Dezember 2024 (F13). Alte ÖNACE-2003-Codes (DA bis DN) gehen über Regel `Q01_oenace_2003_unterabschnitte` auf Abschnitt C, in 08/2024 sind das 50 Verhältnisse (F6). Branchen vergleichen wir nur innerhalb derselben Version. Die Sprungprüfung P14 vergleicht ÖNACE nicht über den Wechsel.

**Antwortweg:** `uv run uc3 regeln zeigen`, Regeln `R7_oenace_nach_berichtsmonat` und `Q01_oenace_2003_unterabschnitte`.

**Fundstelle:** `uc3/db/110_regelsatz_v1.sql` (Q01 ab Zeile 52, R7 ab Zeile 88), `uc3/db/120_pruefregeln_v1.sql`, `uc3/db/020_stat_metadaten.sql` (Tabellen `stat.klass_oenace` und `stat.uebergang`), `docs/plan/uc3/annahmen.md` (A3).

### C10 Warum löschen Sie nichts?

**Kurzantwort:** Die Aufgabenstellung verlangt, dass kein Verhältnis verloren geht. Volldubletten werden zu einem Satz verdichtet, die Zahl der verdichteten Zeilen bleibt erhalten (2025-03: 1.663 Zeilen, F8). Unklare Werte werden zugeordnet und markiert. Die Abrechnung geht auf: gelesene plus fortgeschriebene Sätze gleich gezählte plus nicht gezählte plus ausgeschlossene (März 2025: 1.470 fortgeschrieben, F9).

**Antwortweg:** Qualitätsbericht 2025-03, Abschnitt 1 (Abrechnung) und 2 (Auffälligkeiten).

**Fundstelle:** `abgabe/qualitaetsberichte/2025-03.md`, `uc3/db/030_bereinigt_stat.sql`.

### C11 Wie kommt eine neue Regel in Kraft?

**Kurzantwort:** Eine Regel ist eine Zeile in `meta.regel` mit Gültigkeit, Begründung, Grundlage und Freigabe. Regelsatz v1 hat 15 Einlese-, Zuordnungs- und Zählregeln und 24 Prüfregeln P01 bis P24 (F15). Freigeben kann nur eine Person mit Vor- und Nachnamen. „Team“ wird abgelehnt. Bei Vorschlägen der Agenten entsteht dazu ein gespeicherter Änderungsschritt im Repo (Commit) mit dem Vermerk `Freigegeben-von`.

**Antwortweg:** `uv run uc3 regeln zeigen`, `uv run uc3 regeln freigeben --name "Vor- und Nachname"`, `uv run uc3 protokoll --zeigen`.

**Fundstelle:** `uc3/db/010_meta.sql`, `uc3/db/045_freigabe_schutz.sql`, `uc3/statagent/regeln.py`, `docs/plan/uc3/regeln-v1.csv`.

### C12 Wie hängt der gemeinsame Einstieg (UC4) mit UC3 zusammen?

**Kurzantwort:** Eine Frage läuft nacheinander durch UC3, UC2 und UC1. Jeder Use Case hat einen Adapter `antwort(frage, kontext)`, der eine Antwort in gleicher Form liefert: Text, Belege, Zahlen, Use Case, Modell und Protokoll-ID. Belegschicht, Freigabe und Modell-Schalter sind für alle drei gleich. Der UC3-Adapter nutzt kein Sprachmodell.

**Antwortweg:** `uv run uc3 antwort "Beschäftigte in Wien im März 2025"`. In der Oberfläche die Seite für den gemeinsamen Einstieg zeigen.

**Fundstelle:** `uc3/statagent/uc4.py`, `shared/py/plattform/router.py`, `shared/py/plattform/antwortform.py`, `web/app/uc4/page.tsx`.

### C13 Was habt ihr bei der Teil-Lieferung 2025-10 gemacht?

**Kurzantwort:** Die Lieferung hatte 345.078 Zeilen statt rund 430.000. Der bereinigte Bestand lag bei 313.154 gegen 394.200 im Vormonat, die Differenz ist 81.046 (F17). Von 394.200 am 30.09.2025 offenen Verhältnissen fehlten 78.949 in der Lieferung (20,0 Prozent), 78.733 davon sind in 2025-11 wieder da (F11). Beide Zahlen messen Verschiedenes: Die erste vergleicht Bestände, die zweite zählt Verhältnisse, die gar nicht vorkommen. Der Lauf hält an, schreibt 77.746 Verhältnisse fort und weist 390.900 als vorläufig aus (F11).

**Antwortweg:** Qualitätsbericht 2025-10, Prüfregeln P15, P16, P17.

**Fundstelle:** `abgabe/qualitaetsberichte/2025-10.md`, `docs/plan/uc3/annahmen.md`.

### C14 Was löst die Lösung nicht?

**Kurzantwort:** Wir nennen fünf Grenzen offen.
Erstens sind die Daten synthetisch.
Zweitens hängt das Alter bei Geburtsmonat 13 vor Juli von der Antwort der Fachabteilung auf Rückfrage R1 ab (F4).
Drittens fehlen bei den Pensionen die öffentlich Bediensteten, die frühere BVA meldet keine. Die Zahlen sind vorläufig, bis sie mit Namen freigegeben sind.
Viertens zählen wir nach ÖNACE-Abschnitt und Bundesland, nicht bis zum 5-Steller und nicht nach Bezirk oder Gemeinde, denn die Lieferungen haben nur das. Die tiefen Klassifikationen kann man online nachschlagen, gezählt wird nicht tiefer.
Fünftens steht die Altersgrenze 110 ohne amtlichen Standard. Sie ist ein Parameter und lässt sich ändern (F5).

**Antwortweg:** `uc3/README.md`, Abschnitt Grenzen, und Rückfrage R1 zeigen.

**Fundstelle:** `uc3/README.md`, `abgabe/rueckfragen/R1.md`, `docs/plan/uc3/annahmen.md`.

### C15 Ihr habt die Regeln am Bericht abgestimmt, ist das nicht zirkulär?

**Kurzantwort:** Nein. Die Regeln kommen aus der Fachbeschreibung. Nur zwei Lücken schließt der Bericht selbst: Geburtsmonat 13 und die Altersgrenze (`docs/plan/uc3/annahmen.md` A4 und A5, F4, F5). Für die übrigen 23 Monate gibt es keinen Vergleichsbericht. Dort laufen 24 Prüfregeln (F15). Die Gegenrechnung lief unabhängig und ohne den UC3-Code, direkt auf den Rohdaten (Belegregister, Abfragen A1 bis A9).

**Antwortweg:** `uv run uc3 eichen --lieferung 2024-08` (F1), danach `docs/plan/uc3/annahmen.md` A4 und A5 zeigen und `uv run uc3 regeln zeigen`.

**Fundstelle:** `docs/plan/uc3/annahmen.md`, `uc3/pruefkatalog.csv`, `docs/praesentation/belegregister.md`.

**Zahlen:** 2.880 von 2.880 Zellen (F1), 23 Monate ohne Vergleichsbericht und 24 Prüfregeln (F15).

### C16 Läuft der gemeinsame Einstieg schon?

**Kurzantwort:** Die Szenen zeigen das Zielbild: eine Frage, drei Antworten. Was davon heute wirklich läuft, steht im Abschnitt „Stand“ darunter. Bernhard sagt nur, was dort steht. Sicher ist: Die Zahl kommt aus UC3, ohne Sprachmodell und mit Beleg, Sollwert 7.498 (F18).

**Antwortweg:** In der Oberfläche die Seite `/uc4`, im Terminal `uv run uc3 antwort "Beschäftigte in Wien im März 2025"`. Laufen die Modelle im Testbetrieb, sagt Bernhard „Testbetrieb“ an.

**Fundstelle:** `shared/py/plattform/router.py` (Router), Entry-Points `kic.uc_antwort` in `uc1/pyproject.toml`, `uc2/pyproject.toml`, `uc3/pyproject.toml`; `web/app/uc4/page.tsx`, `web/app/api/uc4/frage/route.ts`; siehe C12.

#### Stand (was vom Zielbild auf main ist)

Code gemessen am 05.11.2026 18:54 auf main `1a8c645`. Betrieb gemessen am 05.11.2026 23:04 bis 23:08 auf der Online-Demo, main `11b5ff5` (POST `/api/uc4/frage`), dazu der Prüfpunkt des Leads um 20:00. Fr 05:00 noch einmal messen. Nicht gemessen heißt: nicht behaupten.

| Teil des Zielbilds | Stand auf main | Beleg |
|---|---|---|
| Gemeinsamer Router | im Code | `shared/py/plattform/router.py` |
| Seite `/uc4` und Schnittstelle | im Code | `web/app/uc4/page.tsx`, `web/app/api/uc4/frage/route.ts` |
| UC3-Adapter (StatAgent) | registriert | `uc3/pyproject.toml`, `statagent.uc4:antwort` |
| UC2-Adapter (Simulator) | registriert | `uc2/pyproject.toml`, `uc2.antwort:antwort` |
| UC1-Adapter (Lotse) | registriert | `uc1/pyproject.toml`, `uc1.uc4:router_adapter` |
| Freigabe mit Namen in UC2 | im Code | `uc2/src/uc2/verhandlung/freigabe.py`, `web/app/api/uc2/faelle/[id]/freigabe/route.ts` |
| Freigabe mit Namen in UC1 | nicht gefunden | keine Fundstelle auf main |
| Wien-Frage liefert drei Antworten | online ja: StatAgent 7.498 mit Beleg (Lauf 105, vorläufig), Simulator mit Modell gpt-5-4-mini, Lotse fester Text, beide mit dem Beleg aus UC3; nichts fehlt; 9 bis 12 s | gemessen 23:04, zweimal |
| Frage ohne Zahl | „Wie heißt der Hund von Pippi Langstrumpf?“: Die Kette stoppt bei StatAgent, ohne Zahl, 3 s | gemessen 23:06 |
| Frage mit „Wartezeiten“ | Mit Wien und März 2025: Der Simulator rechnet über das Rechenmodell, Wartezeit −22,2 %, 128,2 Mio. Euro pro Jahr, 22 s. Nicht vorführen. Ohne Monat und Ort: StatAgent fragt zurück, welchen Begriff es erklären soll, die Kette stoppt | gemessen 23:06 und 23:08 |
| „Zugänge Oktober 2024“ | Öffentliche Adresse: keine Zahl, Hinweis auf die lokale Auswertung. Vorführ-Instanz nicht gemessen | gemessen 23:07 und 23:08 |
| Live-Änderung per Agent (D2 Teil 2) | Endserie läuft, MR !150 Stand 20:00 noch rot; Teil 2 nur, wenn beim Freeze auf main | Prüfpunkt Lead 20:00 |
| Klassifikation bis 5-Steller und Gemeinden | online nachzuschlagen auf `/uc3/klassifikationen` mit Suche, und die Frage erklärt tiefe Codes, Gemeinden und Bezirke. Gezählt wird weiter nach Abschnitt und Bundesland, „Bezirk“ als Filter sagt ab | online gemessen 06.11.2026 01:34, main `275ffb2` |
| Pensionsmeldungen der Träger | eingelesen: 28 von 28 Dateien, 9 Formate, 394 Summen ohne Abweichung. Online 2025 im Jahresdurchschnitt 2.584.909, vorläufig | `docs/uc3/pensionen-pruefbericht.md`, online gemessen 23:16 |
| Lotse, verdeckter Test | Trefferquote 8 von 10, Träger richtig 6 von 10, Grenzen erkannt 3 von 8; Verbesserung eingespielt, Nachmessung offen | Prüfpunkt Lead 20:00 |
| Simulator ohne passenden Zeitungsartikel | sagt offen „Modellannahme“, erfindet keinen Beleg | Prüfpunkt Lead 20:00, Messung E0 19:50 |
| Online-Demo, Budget | 1.000 Modellaufrufe je Tag | Prüfpunkt Lead 20:00 |
| Alle Seiten online | /, /uc1, /uc2, /uc3, /uc3/fragen, /uc4, /praesentation je HTTP 200 | Prüfpunkt Lead, gemessen 19:58 |
| Online-Demo | mit KI: Azure gpt-5-4-mini (seit 19:17 laut Betrieb); `/uc4` wählt das Modell je Frage | Antwort der Wien-Frage, gemessen 19:40 |

**Pflege:** Vor Fr 07:00 mit dem Stand auf main abgleichen, Uhrzeit und Commit neu setzen.

### C17 Wo seht ihr, dass die KI nichts erfindet?

**Kurzantwort:** Der Agent schreibt nur Vorschläge. Die Wirkung wird vorab gerechnet und gezeigt. Wirksam wird eine Änderung erst mit der Freigabe durch eine Person mit Namen. Im Lauf kommt `plattform.llm` nie vor: `uv run uc3 lauf` importiert es nicht, die Zahlen entstehen allein durch Code und Regeln (F16).

**Antwortweg:** `uv run uc3 vorschlag zeigen <id>` (Regel-Unterschied, Zahlen vorher und nachher), `uv run uc3 protokoll --zeigen`. Danach `uc3/statagent/lauf.py` auf Importe prüfen: kein `plattform.llm`.

**Fundstelle:** `uc3/statagent/agenten/koordinator.py`, `uc3/statagent/cli.py` (Befehl `agent`, Import von `plattform.llm` nur dort), `abgabe/modelle.md`.

### C18 Warum stimmt die Summe von v2 nicht mit v1 überein?

**Kurzantwort:** v2 trägt beide Aufträge zusammen. Deshalb stimmt die Summe gegen v1 nicht je Kategorie allein. August 2024: Arbeiter +28, Angestellte +19, Beamte +1, zusammen +48 (392.284 statt 392.236). Das kommt ganz aus Auftrag 2 (ganzes Monat statt Stichtag). Auftrag 1 allein lässt die Monatssumme in allen 24 Monaten gleich. Ein eigenes Sheet nur mit Auftrag 1 gibt es bewusst nicht.

**Antwortweg:** `abgabe/aggregationen_v1.xlsx` und `abgabe/aggregationen_v2.xlsx` nebeneinander.

**Fundstelle:** Blatt `Beschaeftigungskategorie` beider Sheets, Spalte 2024-08 (nachgerechnet 05.11.2026); `docs/plan/uc3/aenderungsauftraege-matrix.md`.

## Wenn eine Frage nicht im Katalog steht

Ehrlicher Satz: „Das habe ich nicht vorbereitet. Ich zeige Ihnen, wo die Antwort steht, und wir lesen sie gemeinsam.“ Dann den Weg zeigen, nicht raten: Regel mit `uv run uc3 regeln zeigen`, Zahl mit dem SQL aus Teil A, Begründung im Qualitätsbericht oder in `docs/plan/uc3/annahmen.md`.
