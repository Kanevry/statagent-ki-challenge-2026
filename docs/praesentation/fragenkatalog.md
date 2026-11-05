# Fragenkatalog der Fachjury

Der Katalog hilft am Tisch, wenn die Fachjury nachfragt. Er enthält die drei Datenanfragen der Aufgabenstellung, fünf geübte Live-Änderungen und die Fragen, die wir erwarten.

Regel: Jede Antwort ist in unter 30 Sekunden lesbar. Aufbau je Frage: Frage, Kurzantwort, Antwortweg, Fundstelle im Repo, Zahlen mit Kennung F….

Der Vermerk „(mit !13)“ heißt: Die Datei kommt erst mit dem Merge Request !13 (UC3-Kern) auf `main`. Die Kennungen F1 bis F16 stehen im Faktenblatt der Präsentation.

Stand der Befehle: `uv run uc3 frage` ist noch nicht fertig (#74). Bis dahin läuft jede Datenanfrage als SQL mit `psql` gegen die UC3-Datenbank. Der Befehl `uv run uc3 antwort "…"` beantwortet einfache Fragen zu einem Monat, zum Beispiel „Beschäftigte in Wien im März 2025“, ohne Sprachmodell.

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

**Antwortweg:** psql mit diesem SQL.

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

**Fundstelle im Repo:** `uc3/db/030_bereinigt_stat.sql` (Tabelle), `uc3/statagent/zaehlung.py` (Zählregel), `abgabe/aggregationen_v1.xlsx` (alle Monate als Sheet), alle mit !13.

**Zahlen:** Erste Zeile muss 392.236 ergeben (F2). Datenbasis 24 Monatslieferungen (F3). Alle anderen Monate: Ergebnis live aus der Abfrage.

**Hinweis:** Solange der Regelsatz nicht mit Namen freigegeben ist, steht bei allen Monaten „vorläufig“. Nach der Freigabe bleibt „vorläufig“ nur bei 2025-03 und 2025-10, weil dort Teile der Lieferung fehlten (F9, F11).

### A2 Männer und Frauen je Bundesland, ein Monat

**Frage:** „Wie viele Männer und Frauen sind im August 2024 je Bundesland beschäftigt?“

**Kurzantwort:** Die Zahlen kommen aus derselben Tabelle, gegliedert nach `region` und `geschlecht`. Die Summe stimmt mit dem Gesamtbestand überein. Die Zeile „Bundesland unbekannt“ bleibt sichtbar.

**Antwortweg:** psql mit diesem SQL. Für einen anderen Monat das Datum und `stand` tauschen.

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

**Fundstelle im Repo:** `uc3/db/020_stat_metadaten.sql` (Klassifikationen), `uc3/db/100_klass_daten.sql` (Codes), `uc3/statagent/uc4.py` (gleiche Abfrage ohne Sprachmodell), alle mit !13.

**Zahlen (08/2024, F14):** gesamt 392.236 · Männer 211.603 · Frauen 180.633 · Wien 90.799 · Niederösterreich 64.505. Alle übrigen Bundesländer: Ergebnis live aus der Abfrage.

### A3 Fluktuation je Branche zwischen zwei Stichtagen

**Frage:** „Wie viele Zugänge und Abgänge gab es je Branche zwischen Ende September und Ende Oktober 2024?“

**Kurzantwort:** Ein Zugang ist ein Verhältnis, das am zweiten Stichtag besteht und am ersten nicht. Ein Abgang ist das Gegenteil. Gerechnet wird aus den bereinigten Zeitabschnitten einer Lieferung, die beide Stichtage enthält. Beide Stichtage haben dann dieselbe ÖNACE-Version. Ein Branchenwechsel bei bleibendem Verhältnis zählt weder als Zugang noch als Abgang.

**Antwortweg:** psql mit diesem SQL. Es nimmt die Lieferung 2024-10 mit den Stichtagen 30.09. und 31.10.2024.

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

**Klassifikationswechsel (F13):** Ab Lieferung 2025-01 gilt ÖNACE 2025, auch rückwirkend für den 31.12.2024. 189.170 von 386.299 Verhältnissen tragen dort einen anderen Abschnittscode. Deshalb gilt für Fluktuation über den Jahreswechsel: beide Stichtage aus derselben Lieferung nehmen (zum Beispiel 31.12.2024 und 31.01.2025 aus Lieferung 2025-01) oder die Umsteiger ausdrücklich nennen. Zwei Monate aus Lieferungen mit verschiedener ÖNACE-Version nie Abschnitt gegen Abschnitt vergleichen.

**Grenze der Skizze:** Abschnitte, die bei einem Lieferausfall aus der Vorlieferung fortgeschrieben wurden (Spalte `herkunft`), zählen mit. Für 2025-03 und 2025-10 deshalb den Hinweis „vorläufig“ mitsagen (F9, F11). Vor der Freigabe des Regelsatzes gilt „vorläufig“ für alle Monate.

**Fundstelle im Repo:** `uc3/db/030_bereinigt_stat.sql` (Tabelle `bereinigt.abschnitt`), `uc3/db/035_herkunft.sql`, `docs/plan/uc3/annahmen.md`, alle mit !13.

**Zahlen:** Ergebnis live aus der Abfrage.

## Teil B: Fünf geübte Live-Änderungen

Ablauf immer gleich: Satz sprechen, `agent` erzeugt nur einen Vorschlag, `vorschlag zeigen` zeigt Regel-Unterschied und Zahlen vorher und nachher, `freigabe` macht ihn wirksam. Änderungen landen im Regelsatz `v2`, `v1` bleibt unverändert. Die Freigabe schreibt einen Commit mit dem Trailer `Freigegeben-von`.

Befehle (Fundstelle jeweils `uc3/statagent/cli.py` und `uc3/statagent/agenten/` mit !13):

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

### B2 Ersatztag bei Geburtsmonat 13 ändern

**Satz der Jury:** „Rechnen Sie bei Geburtsmonat 13 mit dem 1. Jänner statt mit dem 1. Juli.“

**Befehl:** `uv run uc3 agent "Setze bei Geburtsmonat 13 den Ersatztag auf den 1. Jänner des Geburtsjahres." --probe 2024-08`

**Was der Vorschlag ändert:** Regel `R5_alter`, Parameter `geburtsmonat_13` von `ersatz:07-01` auf `ersatz:01-01`.

**Erwartete Wirkung:** Für 08/2024 bleibt der Beispielbericht exakt, weil jeder Ersatztag von Jänner bis August Tab13 trifft (F4). Der Gesamtbestand ändert sich nie, nur das Alter einzelner Verhältnisse mit Monat 13. In Monaten, deren Stichtag vor dem 1. Juli liegt, verschiebt sich das Alter dieser Verhältnisse um ein Jahr. Zweite Probe: `--probe 2025-03`. Der Vorschlag zeigt dann die verschobenen Altersgruppen.

**Wozu die Übung dient:** Sie zeigt, dass die offene Frage R1 an die Fachabteilung ein Regelparameter ist und keine Programmänderung.

**Freigabe:** `uv run uc3 freigabe <id> --name "Bernhard Götzendorfer"`

### B3 Schwelle des Bestandsrückgangs senken

**Satz der Jury:** „Halten Sie einen Monat schon bei 3 Prozent Bestandsrückgang an, nicht erst bei 5.“

**Befehl:** `uv run uc3 agent "Halte einen Monat schon an, wenn der Bestand um mehr als 3 Prozent unter dem Vormonat liegt." --probe 2025-10`

**Was der Vorschlag ändert:** Prüfregel `P15_bestand_vs_vormonat` (Typ `pruefung`), Parameter `schwelle` von 0.05 auf 0.03.

**Erwartete Wirkung:** Der Bestand ändert sich nicht, eine Prüfregel ändert keine Zahl. Es ändert sich nur, welche Monate anhalten. Teil-Lieferung 2025-10 hält ohnehin an (P15, P16, P17, F11). Welche weiteren Monate die neue Schwelle träfe, zeigt die Probe live.

**Freigabe:** `uv run uc3 freigabe <id> --name "Bernhard Götzendorfer"`

### B4 Schwelle des Spaltentauschs anheben

**Satz der Jury:** „Erkennen Sie den Spaltentausch erst, wenn mehr als 80 Prozent der Beginn-Felder leer sind.“

**Befehl:** `uv run uc3 agent "Erkenne den Spaltentausch von Beginn und Ende erst, wenn mehr als 80 Prozent der Beginn-Felder leer sind." --probe 2025-06`

**Was der Vorschlag ändert:** Einleseregel `E01_spaltentausch_beginn_ende`, Parameter `anteil_beginn_leer_min` von 0.5 auf 0.8.

**Erwartete Wirkung:** Die Zahlen bleiben gleich. In 2025-06 sind 388.115 von 432.086 Zeilen ohne Beginn (F10). Das liegt über 80 Prozent, der Tausch greift weiter. Bestand am 30.06.2025 bleibt 394.252 (F10).

**Freigabe:** `uv run uc3 freigabe <id> --name "Bernhard Götzendorfer"`

### B5 Gegenprobe: Schwelle für verschwundene Ausprägungen anheben, ablehnen

**Satz der Jury:** „Melden Sie eine verschwundene Ausprägung erst, wenn sie vorher mehr als 2.000 Verhältnisse hatte.“

**Befehl:** `uv run uc3 agent "Melde eine verschwundene Ausprägung erst, wenn sie im Vormonat mehr als 2000 Verhältnisse hatte." --probe 2025-03`

**Was der Vorschlag ändert:** Prüfregel `P13_auspraegung_verschwunden`, Parameter `schwelle` von 100 auf 2000.

**Erwartete Wirkung:** Die freien Dienstverträge in 2025-03 (AngestellteFD 1.131, ArbeiterFD 361, zusammen 1.492, F9) liegen jeweils unter 2.000. Die Prüfregel würde den Monat nicht mehr anhalten. Das ist eine Änderung, die wir nicht wollen.

**Was wir sagen:** Die Probe zeigt die Folge, bevor etwas gilt. Wir lehnen ab:

`uv run uc3 ablehnen <id> --name "Bernhard Götzendorfer" --begruendung "Schwelle würde den Ausfall der freien Dienstverträge nicht mehr melden"`

**Wozu die Übung dient:** Sie zeigt, dass der Mensch nein sagen kann und die Ablehnung im Protokoll steht (`uv run uc3 protokoll --zeigen`).

## Teil C: Weitere Fragen der Fachjury

### C1 Was zählen Sie genau?

**Kurzantwort:** Ein Versicherungsverhältnis zählt einmal, wenn am Stichtag ein Zeitabschnitt besteht. Stichtag ist der Monatsletzte. Der Abschnitt besteht, wenn der Beginn am oder vor dem Stichtag liegt und das Ende leer ist oder am oder nach dem Stichtag liegt. Beispiel 08/2024: 392.284 Zeilen minus 48, die vor dem Stichtag enden, gleich 392.236 (F2).

**Antwortweg:** `uv run uc3 regeln zeigen`, Regeln `R2_R4_stichtag_eigene_lieferung` und `R1_R3_verhaeltnis_einmal`.

**Fundstelle:** `uc3/db/110_regelsatz_v1.sql`, `abgabe/qualitaetsberichte/2024-08.md` (beide mit !13).

### C2 Warum nur eigene und frühere Lieferungen?

**Kurzantwort:** Ein Monat darf sich nicht durch spätere Daten ändern. Spätere Lieferungen werden nie verwendet. Zeigen spätere Lieferungen eine Abweichung, steht sie als Revisionsbedarf im Qualitätsbericht (F12).

**Antwortweg:** Regel `R2_R4_stichtag_eigene_lieferung`, Qualitätsbericht 2025-01, Abschnitt 2.

**Fundstelle:** `uc3/db/110_regelsatz_v1.sql`, `abgabe/qualitaetsberichte/2025-01.md` (beide mit !13).

### C3 Sieht das Sprachmodell Einzeldaten?

**Kurzantwort:** Nein. Beschäftigte und Geburtsdaten sind Hochrisikodaten, deshalb sieht das Modell nur Regeln, Schemata, Klassifikationen und Aggregate. Das Lese-Werkzeug der Agenten verweigert Ergebnisse mit Personen- oder Verhältnis-ID. Kleine Zellen unter 5 erscheinen als „<5“. Jeder Modellaufruf wird protokolliert, nie mit Inhalt.

**Antwortweg:** Datei `abgabe/modelle.md` zeigen.

**Fundstelle:** `abgabe/modelle.md`, `uc3/statagent/agenten/rollen.py`, `uc3/statagent/agenten/werkzeuge.py` (alle mit !13).

### C4 Läuft das auch lokal und offline?

**Kurzantwort:** Ja. Die Rechnung läuft in PostgreSQL 16 und Python auf dem eigenen Rechner. Kein Befehl von `uc3 lauf` ruft ein Sprachmodell auf (F16). Nur die Agenten brauchen ein Modell. Dafür gibt es den Schalter `LLM_PROVIDER=ollama` für den Betrieb ohne Netz.

**Antwortweg:** `uv run uc3 lauf --lieferung 2024-08` ohne Netz zeigen.

**Fundstelle:** `uc3/README.md`, `abgabe/modelle.md` (beide mit !13).

### C5 Ist das Ergebnis reproduzierbar?

**Kurzantwort:** Ja. Zwei Läufe mit denselben Daten und Regeln liefern denselben Ergebnis-Hash (F16). Den Hash zeigt `uv run uc3 laeufe`. Gegenprobe zum Beispielbericht: 2.880 von 2.880 Zellen, 0 Abweichungen (F1).

**Antwortweg:** `uv run uc3 laeufe`, `uv run uc3 eichen --lieferung 2024-08`.

**Fundstelle:** `uc3/tests/test_goldenset.py`, `uc3/statagent/ergebnis.py` (beide mit !13).

### C6 Welches Modell nutzen Sie, und lässt es sich tauschen?

**Kurzantwort:** Die Agenten laufen standardmäßig auf Azure (gpt-5-4-mini). Über den Schalter `LLM_PROVIDER` geht auch `claude`, `mistral`, `ollama` oder `mock`. Schnittstelle und Protokoll bleiben gleich. Das Modell schlägt nur vor, die Rechnung macht das Programm.

**Antwortweg:** `abgabe/modelle.md` zeigen. Der Schalter steht in `.env.example`.

**Fundstelle:** `abgabe/modelle.md` (mit !13), `shared/py/plattform/llm/`.

### C7 Was passiert, wenn das Modell ausfällt?

**Kurzantwort:** Der Lauf rechnet trotzdem, denn er braucht kein Modell (F16). Es fehlen nur die Vorschläge der Agenten. Der Befehl `agent` meldet den Modellfehler als Meldung, ohne die Daten anzufassen. Dann hilft der Wechsel des Anbieters oder `LLM_PROVIDER=mock`.

**Antwortweg:** Live zeigen: `uv run uc3 lauf --lieferung 2024-08` läuft, `agent` meldet den Fehler.

**Fundstelle:** `uc3/statagent/cli.py` (Befehl `agent`), `uc3/tests/test_cli_agenten.py` (beide mit !13).

### C8 Was ist mit bereits Veröffentlichtem?

**Kurzantwort:** Veröffentlichtes bleibt, die Datenbank schützt es durch einen Trigger. Sehen spätere Lieferungen andere Werte, steht die Abweichung als Revisionsbedarf im Qualitätsbericht. Beispiel Dezember 2024: minus 260 Verhältnisse, also 387.390 veröffentlicht gegen 387.130 nach Lieferung 2025-01 (F12).

**Antwortweg:** `uv run uc3 berichte --lieferung 2025-01 --zeigen`.

**Fundstelle:** `uc3/db/030_bereinigt_stat.sql` (Trigger `stat_besch_endgueltig`), `abgabe/qualitaetsberichte/2025-01.md` (beide mit !13).

### C9 Wie gehen Sie mit dem Wechsel der ÖNACE-Version um?

**Kurzantwort:** Der Wirtschaftszweig wird nach der Version ausgewiesen, die im Berichtsmonat gilt: bis 12/2024 ÖNACE 2008, ab 01/2025 ÖNACE 2025. Ab Lieferung 2025-01 tragen 189.170 von 386.299 Verhältnissen einen anderen Abschnittscode, auch rückwirkend für den 31.12.2024 (F13). Branchen vergleichen wir nur innerhalb derselben Version. Die Sprungprüfung P14 vergleicht ÖNACE nicht über den Wechsel.

**Antwortweg:** `uv run uc3 regeln zeigen`, Regel `R7_oenace_nach_berichtsmonat`.

**Fundstelle:** `uc3/db/110_regelsatz_v1.sql`, `uc3/db/120_pruefregeln_v1.sql`, `uc3/db/020_stat_metadaten.sql` (Tabelle `stat.uebergang`), alle mit !13.

### C10 Warum löschen Sie nichts?

**Kurzantwort:** Die Aufgabenstellung verlangt, dass kein Verhältnis verloren geht. Volldubletten werden zu einem Satz verdichtet, die Zahl der verdichteten Zeilen bleibt erhalten (2025-03: 1.663 Zeilen, F8). Unklare Werte werden zugeordnet und markiert. Die Abrechnung geht auf: gelesene Sätze gleich gezählte plus nicht gezählte plus ausgeschlossene.

**Antwortweg:** Qualitätsbericht 2025-03, Abschnitt 1 (Abrechnung) und 2 (Auffälligkeiten).

**Fundstelle:** `abgabe/qualitaetsberichte/2025-03.md`, `uc3/db/030_bereinigt_stat.sql` (beide mit !13).

### C11 Wie kommt eine neue Regel in Kraft?

**Kurzantwort:** Eine Regel ist eine Zeile in `meta.regel` mit Gültigkeit, Begründung, Grundlage und Freigabe. Regelsatz v1 hat 15 Einlese-, Zuordnungs- und Zählregeln und 24 Prüfregeln P01 bis P24 (F15). Freigeben kann nur eine Person mit Vor- und Nachnamen. „Team“ wird abgelehnt. Bei Vorschlägen der Agenten entsteht dazu ein Commit mit dem Trailer `Freigegeben-von`.

**Antwortweg:** `uv run uc3 regeln zeigen`, `uv run uc3 regeln freigeben --name "Vor- und Nachname"`, `uv run uc3 protokoll --zeigen`.

**Fundstelle:** `uc3/db/010_meta.sql`, `uc3/db/045_freigabe_schutz.sql`, `uc3/statagent/regeln.py`, `docs/plan/uc3/regeln-v1.csv` (alle mit !13).

### C12 Wie hängt der gemeinsame Einstieg (UC4) mit UC3 zusammen?

**Kurzantwort:** Eine Frage läuft nacheinander durch UC3, UC2 und UC1. Jeder Use Case hat einen Adapter `antwort(frage, kontext)`, der eine Antwort in gleicher Form liefert: Text, Belege, Zahlen, Use Case, Modell und Protokoll-ID. Belegschicht, Freigabe und Modell-Schalter sind für alle drei gleich. Der UC3-Adapter nutzt kein Sprachmodell.

**Antwortweg:** `uv run uc3 antwort "Beschäftigte in Wien im März 2025"`. In der Oberfläche die Seite für den gemeinsamen Einstieg zeigen.

**Fundstelle:** `uc3/statagent/uc4.py` (mit !13), `shared/py/plattform/router.py`, `shared/py/plattform/antwortform.py`, `web/app/uc4/page.tsx`.

### C13 Was habt ihr bei der Teil-Lieferung 2025-10 gemacht?

**Kurzantwort:** Die Lieferung hatte 345.078 Zeilen statt rund 430.000. Von 394.200 am 30.09.2025 offenen Verhältnissen fehlten 78.949 (20,0 Prozent), 78.733 davon sind in 2025-11 wieder da (F11). Der Lauf hält an, schreibt 77.746 Verhältnisse fort und weist 390.900 als vorläufig aus (F11).

**Antwortweg:** Qualitätsbericht 2025-10, Prüfregeln P15, P16, P17.

**Fundstelle:** `abgabe/qualitaetsberichte/2025-10.md`, `docs/plan/uc3/annahmen.md` (beide mit !13).

### C14 Was löst die Lösung nicht?

**Kurzantwort:** Wir nennen vier Grenzen offen.
Erstens sind die Daten synthetisch.
Zweitens hängt das Alter bei Geburtsmonat 13 vor Juli von der Antwort der Fachabteilung auf Rückfrage R1 ab (F4).
Drittens sind `uv run uc3 frage` und `klass` noch nicht fertig (#74, #75). Datenanfragen laufen bis dahin als SQL aus diesem Katalog.
Viertens steht die Altersgrenze 110 ohne amtlichen Standard. Sie ist ein Parameter und lässt sich ändern (F5).

**Antwortweg:** `uc3/README.md`, Abschnitt Grenzen, und Rückfrage R1 zeigen.

**Fundstelle:** `uc3/README.md`, `abgabe/rueckfragen/R1.md`, `docs/plan/uc3/annahmen.md` (alle mit !13).

## Wenn eine Frage nicht im Katalog steht

Ehrlicher Satz: „Das habe ich nicht vorbereitet. Ich zeige Ihnen, wo die Antwort steht, und wir lesen sie gemeinsam.“ Dann den Weg zeigen, nicht raten: Regel mit `uv run uc3 regeln zeigen`, Zahl mit dem SQL aus Teil A, Begründung im Qualitätsbericht oder in `docs/plan/uc3/annahmen.md`.
