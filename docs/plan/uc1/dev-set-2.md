# UC1 Dev-Set 2: zweites Abstimm-Set für die Suche (#30)

Stand 2026-11-05. Datei: `uc1/eval/dev-set-2.yaml` (e01–e24). Es ergänzt `uc1/eval/dev-set.yaml`
(d01–d12). Auf beiden Sets wird die Suche abgestimmt. Das eingefrorene Test-Set `lotse-set.yaml` bleibt
dabei unberührt.

Messen ohne Modell: `lotse eval --nur-suche --set uc1/eval/dev-set-2.yaml` (beim Schreiben nicht
ausgeführt, siehe Unabhängigkeit).

## Vorgehen

1. **Unabhängigkeit.** Nicht geöffnet wurden `uc1/eval/lotse-set.yaml`, `docs/plan/uc1/messung.md`,
   `docs/plan/uc1/messung-dev.md` und `uc1/laufzeit/`, auch nicht als Commit-Diff. Gelesen wurde
   `dev-set.yaml`, nur wegen der Dubletten und des Formats. `lotse suche` lief nicht. Kein Suchergebnis
   hat eine Frage oder Norm beeinflusst.
2. **Themen zuerst.** Für jedes der zwölf Themen gibt es zwei Lebenslagen, die d01–d12 nicht abdecken.
   Die Fragen sind in Alltagssprache formuliert, meist mit einer kurzen Lebenslage, und unterschiedlich
   lang. e08 und e24 sind auf Englisch.
3. **Norm aus dem Text.** Die Kandidatennorm wurde per SQL nach Gesetz und Nummer oder Überschrift
   (`lotse.abschnitt.kontext`) in `lotse.dokument` gesucht. Dann wurde der Abschnitt gelesen und geprüft,
   ob er die Antwort trägt. Für PDFs wurden alle Seiten der Formulare und des Serviceratgebers 2026
   angelesen, die tragende Seite steht als `seite` im Set.
4. **Beleg.** Je Quelle wurde per SQL geprüft: Das Dokument existiert, es ist nicht aufgehoben, und ein
   Abschnitt (bei PDFs die genannte Seite) enthält die tragende Wendung (Abfragen unten).
5. **Regex nur für parallele Normen.** `ueberschrift_regex` ist dort gesetzt, wo andere Träger eine
   gleichartige Norm haben. Jede Regex wurde gegen die Überschriften aller geltenden SozDok-Dokumente
   von ASVG, GSVG, BSVG, B-KUVG, ASGG, KBGG und BPGG geprüft, mit Python `re` und mit PostgreSQL `~*`;
   beide liefern dieselben Treffer.

## Verteilung

| Thema | Fälle | Ziel |
|---|---|---|
| Pflege und Angehörige | e01, e02 | BPGG § 4/5; PAL080 S. 8 |
| Krankheit und Krankenstand | e03, e04 | ASVG § 139/138; Serviceratgeber S. 26 |
| Rehabilitation und Kur | e05, e06 | Antrag Kur und Reha S. 1/2; ASVG § 143a/255b |
| Schwangerschaft und Kind | e07, e08 (en) | ASVG § 162; KBGG § 5/3 |
| Pension und Hinterbliebene | e09, e10 | ASVG § 255; ASVG § 265 |
| Arbeitsunfall | e11, e12 | ASVG § 175; ASVG § 177 + Anlage 1 |
| Kosten und Selbstbehalte | e13, e14 | ASVG § 131; Fahrtkosten-Antrag Wien S. 2 + ASVG § 135 |
| Mitversicherung | e15, e16 | ASVG § 51d; Serviceratgeber S. 6 + ASVG § 123 |
| Selbständige (GSVG) | e17, e18 | GSVG § 2/4; GSVG § 104a |
| Bauern (BSVG) | e19, e20 | BSVG § 2; BSVG § 3/148c |
| Öffentlich Bedienstete (B-KUVG) | e21, e22 | B-KUVG § 63; B-KUVG § 90 |
| Verfahren und Bescheid | e23, e24 (en) | ASGG § 67/65; ASVG § 368 + ASGG § 67 |

**Nach Quellen.** 24 Fälle mit 37 erwarteten Quellen. Davon sind 30 SozDok-Normen: ASVG 15, GSVG 3,
BSVG 3, ASGG 3 (§ 67 zweimal), BPGG 2, KBGG 2, B-KUVG 2. Dazu kommen 7 PDF-Seiten aus 4 Dateien.
5 Fälle zielen auf eine PDF-Seite. Bei 3 davon (e02, e04, e05) ist die PDF das einzige Ziel, bei 2
(e14, e16) steht daneben eine Norm.

| PDF (Pfad wie `lotse.dokument.datei`) | Seite | Fall |
|---|---|---|
| `Anträge und Formulare/PAL080_0125_Mpfl_052026.pdf` | 8, 1 | e02 |
| `Leistungskataloge/Serviceratgeber-2026_Broschuere_A5_OEAM_99-19_klein_korr.pdf` | 26 | e04 |
| `Anträge und Formulare/Antrag Kur und Reha.pdf` | 1, 2 | e05 |
| `Anträge und Formulare/Antrag-auf-Zuschuss-zu-Fahrtkosten_Wien.pdf` | 2 | e14 |
| `Leistungskataloge/Serviceratgeber-2026_Broschuere_A5_OEAM_99-19_klein_korr.pdf` | 6 | e16 |

11 Fälle tragen eine `ueberschrift_regex`. Sie trifft folgende parallele Normen:

| Fall | Regex trifft (geltende Fassungen) |
|---|---|
| e03 | ASVG § 139, § 140 |
| e06 | ASVG § 255b, § 273b, § 280b |
| e07 | ASVG § 162, GSVG § 102a, BSVG § 98 |
| e09 | ASVG § 255, § 280 |
| e10 | ASVG § 265, GSVG § 146, BSVG § 137 |
| e11, e22 | ASVG § 175, BSVG § 148c, B-KUVG § 90 |
| e12 | ASVG § 177, ASVG Anlage 1, BSVG § 148e, B-KUVG § 92 |
| e13 | ASVG § 131 |
| e15 | ASVG § 51d, GSVG § 27c, BSVG § 24b, B-KUVG § 20b (dazu E-MVB 051d-Einträge) |
| e16 | ASVG § 123, GSVG § 83, BSVG § 78 |

Bewusst ohne Regex sind e18 und e21. Bei e18 würde „Unterstützungsleistung bei lang andauernder
Krankheit“ auch ASVG § 90a treffen, eine Zusammentreffens-Regel. Bei e21 wäre eine Regex für
Behandlungsbeiträge zu breit.

## Belegabfragen

DB `lotse` (Port 5433), nur gelesen. Kernabfrage für eine Norm (Platzhalter in psql-Syntax):

```sql
select d.id, d.inkrafttreten, coalesce(d.meta->>'aufgehoben', 'false') as aufgehoben, a.kontext,
       substr(regexp_replace(a.text, '\s+', ' ', 'g'),
              strpos(regexp_replace(a.text, '\s+', ' ', 'g'), :'wendung') - 80, 400) as stelle
from lotse.dokument d join lotse.abschnitt a on a.dokument_id = d.id
where d.quelle = 'sozdok' and d.gesetz = :'gesetz' and d.art = :'art' and d.nummer = :'nummer'
  and strpos(regexp_replace(a.text, '\s+', ' ', 'g'), :'wendung') > 0;
```

Für eine PDF-Seite gilt `where d.datei = :'datei' and a.seite = :'seite'` statt Gesetz, Art und Nummer.

Sammelprüfung über alle 37 Quellen: Je Quelle stehen Fall, Gesetz/Art/Nummer bzw. Datei/Seite und die
tragende Wendung in einer `values`-Liste. Gezählt werden die Dokumente, die geltenden Dokumente und die
Abschnitte mit der Wendung:

```sql
with z(fid, g, art, nr, datei, seite, w) as (values
  ('e01','BPGG','PARA','4',null,null,'mindestens sechs Monate andauern'),
  ('e02',null,null,null,'Anträge und Formulare/PAL080_0125_Mpfl_052026.pdf',8,'Graz'),
  -- … eine Zeile je erwarteter Quelle, Wendungen siehe Tabelle unten
  ('e24','ASGG','PARA','67',null,null,'nicht innerhalb von drei Monaten'))
select z.fid, count(distinct d.id) as dok,
       count(distinct d.id) filter (where coalesce(d.meta->>'aufgehoben','false') <> 'true') as geltend,
       count(a.*) filter (where strpos(regexp_replace(a.text,'\s+',' ','g'), z.w) > 0) as abschnitte_mit_wendung
from z left join lotse.dokument d
  on (z.datei is null and d.quelle = 'sozdok' and d.gesetz = z.g and d.art = z.art and d.nummer = z.nr)
  or d.datei = z.datei
left join lotse.abschnitt a on a.dokument_id = d.id and (z.seite is null or a.seite = z.seite)
group by z.fid, z.g, z.art, z.nr, z.datei, z.seite, z.w order by 1;
```

Ergebnis am 2026-11-05: Für alle 37 Quellen gilt `dok = 1`, `geltend = 1` und `abschnitte_mit_wendung = 1`.

| Fall | Quelle | geprüfte Wendung |
|---|---|---|
| e01 | BPGG § 4 / § 5 | „mindestens sechs Monate andauern“ / „in Stufe 1“ |
| e02 | PAL080 S. 8 / S. 1 | „Graz“ / „Hauptstelle Friedrich-Hillegeist-Straße 1, 1020 Wien“ |
| e03 | ASVG § 139 / § 138 | „52 Wochen“ / „vom vierten Tag“ |
| e04 | Serviceratgeber S. 26 | „Ambulanzkarte nicht als Krankmel“ |
| e05 | Kur und Reha S. 1 / S. 2 | „Von dem/der Versicherten“ / „Ärztliche Stellungnahme“ |
| e06 | ASVG § 143a / § 255b | „Anspruch auf Rehabilitationsgeld“ / Text gelesen: vorübergehende Invalidität mindestens sechs Monate |
| e07 | ASVG § 162 | „letzten acht Wochen“ |
| e08 | KBGG § 5 / § 3 | „1063 Tage“ / „365 Tagen“ |
| e09 | ASVG § 255 | „60. Lebensjahr vollendet“ |
| e10 | ASVG § 265 | „35fachen“ |
| e11 | ASVG § 175 | „Weg zur oder von der Arbeits“ |
| e12 | ASVG § 177 / Anlage 1 | „Anlage 1“ / „Hauterkrankungen“ |
| e13 | ASVG § 131 | „80 vH“ |
| e14 | Fahrtkosten Wien S. 2 / ASVG § 135 | „Dialyse“ / „Reise(Fahrt)kosten“ |
| e15 | ASVG § 51d | „3,4%“ |
| e16 | Serviceratgeber S. 6 / ASVG § 123 | „Ordentliches Studium“ / „Vollendung des 27. Lebensjahres“ |
| e17 | GSVG § 2 / § 4 | „4. selbständig erwerbstätige Personen“ / „Zwölffache des Betrages nach § 25 Abs. 4“ |
| e18 | GSVG § 104a | „ab dem 43. Tag“ |
| e19 | BSVG § 2 | „Einheitswert des land“ (Schwelle 1 500 € im Text gelesen) |
| e20 | BSVG § 3 / § 148c | „die Geschwister“ / Text gelesen: Arbeitsunfall im Zusammenhang mit der Tätigkeit |
| e21 | B-KUVG § 63 | „Behandlungsbeitrag“ |
| e22 | B-KUVG § 90 | „Telearbeit“ |
| e23 | ASGG § 67 / § 65 | „von drei Monaten“ / Text gelesen: Abs. 1 Z 1 Leistungsansprüche |
| e24 | ASVG § 368 / ASGG § 67 | „binnen zwei Wochen“ / „nicht innerhalb von drei Monaten“ |

Regex-Prüfung (PostgreSQL, gleiches Ergebnis wie Python `re.search(..., re.I)`):

```sql
select string_agg(distinct d.gesetz || ' ' || d.art || ' ' || d.nummer, ', ')
from lotse.abschnitt a join lotse.dokument d on d.id = a.dokument_id
where d.quelle = 'sozdok' and coalesce(d.meta->>'aufgehoben','false') <> 'true'
  and a.kontext ~* :'regex';
```

Schema-Prüfung: `lade_set` lädt die Datei, die IDs sind e01–e24, `_pruefe_quelle` meldet keinen Fehler,
jede Regex kompiliert, keine Frage stimmt wörtlich mit d01–d12 überein.

## Grenzen

- **Ein Autor, n=24.** Fragen und Normen stammen von einem einzigen Autor ohne Zweitprüfung. Eine
  menschliche Freigabe steht aus. Bei 24 Fällen verschiebt ein Fall den Recall um gut 4 Prozentpunkte.
- **Formulierte Fragen.** Die Fragen sind keine echten Bürgeranfragen. Sie sind eher vollständig und
  grammatisch sauber. Tippfehler, Dialekt und sehr kurze Anfragen fehlen fast ganz.
- **Erwartete Quellen sind nicht vollständig.** Gelistet ist die Norm, die die Antwort trägt, plus
  höchstens eine Ergänzung. Andere passende Stellen (Satzungen, Krankenordnungen, E-MVB) zählen nur über
  die Regex oder gar nicht. Ein Recall unter 1 kann also auch einen richtigen Treffer übersehen.
- **PDF-Seite wird nicht gezählt.** `eval.trifft` vergleicht bei PDFs nur den Dateinamen. Ein Treffer
  auf irgendeiner Seite des Serviceratgebers zählt also für e04 wie für e16. Die Angabe `seite` dient
  der Nachprüfung.
- **ASVG-lastig.** 15 der 30 Normquellen sind ASVG. Die Träger-Themen (GSVG, BSVG, B-KUVG) haben je
  nur zwei Fälle.
- **Korpusstand.** Belegt am 2026-11-05. Ändert ein neuer Ingest Fassungen oder Dateinamen, müssen die
  Belegabfragen neu laufen.
