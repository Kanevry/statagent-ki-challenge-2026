# Lotse-Kern (#31)

Der Kern führt von einer Lebenslage zur Leistung. Er stellt nur die nötigen Rückfragen und belegt jede Aussage mit
einem wörtlich geprüften Zitat. Dazu nennt er den zuständigen Träger. Er gibt keine Diagnose und keine Therapie- oder
Medikamentenempfehlung.
Code: `uc1/uc1/kern.py`, `uc1/uc1/grenze.py`, `uc1/uc1/erweiterung.py`. Daten: `uc1/daten/*.yaml`. DDL:
`uc1/db/002_sitzung.sql`.

## Ablauf von `frage(text, …)`

1. **Vorprüfung** (`grenze.vorpruefung`, ohne Modell). Sie erkennt Notfall, Prompt-Injection, Medikament oder Dosis,
   Befund deuten und Symptom deuten. Bei einem Treffer kommt sofort der Grenztext. Brust, Herz oder Atem mit
   Schmerz, Stechen, Druck oder Enge ist Notfall (144, 1450). Eine Beschwerde (Brust, Herz, Atem, Kopf, Bauch,
   Schmerz, Stechen, Fieber, Blutung, Schwindel, Lähmung) mit Deutungsfrage („Was habe ich“, „Ist das …“, „Was
   bedeutet …“) ist Grenze. Herzinfarkt ist nur akut ein Notfall; „Krankengeld nach einem Herzinfarkt“ bleibt
   eine Leistungsfrage (Test `test_leistungsfrage_mit_krankheitswort_ist_keine_grenze`). Eine abgewiesene
   Nachricht kommt nicht in den gespeicherten Verlauf.
2. **Sitzung laden** (`lotse.sitzung.zustand`). Lage, Leistungen und Angaben kommen aus zwei Quellen:
   - aus Regeln (Auslöser in `leistungen.yaml`, Status-Muster in `traeger.yaml`);
   - im Modus `llm` zusätzlich aus EINEM Analyse-Aufruf mit Schema: Lage, Leistungen, Angaben und Fachbegriffe.
   Werte außerhalb der Enums verwirft der Kern. Wo eine Regel etwas erkennt, hat sie Vorrang vor dem Modell.
   Vor jedem Modellaufruf maskiert `maskiere_personendaten` im Verlauf Datum, Telefon, Straße mit Hausnummer und
   PLZ („[Datum]“, „[Telefon]“, „[Adresse]“, „[PLZ]“). Namen gehen vorerst noch ans Modell (Owner-Frage #121).
3. **Rückfrage**, wenn eine Pflichtangabe fehlt. Es kommt genau eine Rückfrage, die nach Rang wichtigste zuerst; der
   Status bzw. Pensionsträger hat Rang 1. Jedes Feld wird höchstens einmal erfragt, höchstens 3-mal je Sitzung.
   Danach antwortet der Kern mit „Vorbehalt: Mir fehlen Angaben (…)“.
4. **Suche** über `uc1.suche.suche` auf dem Weg `volltext`:
   - je Leistung die `suchanfrage` mit Gesetzesfilter, fest (Pflegegeld: BPGG) oder aus dem Status;
   - die Frage plus Begriffe, gefiltert nach den Gesetzen des Status; ohne Status höchstens 2 Treffer je Gesetz
     (Review N1);
   - eine eigene Suche in Katalogen und Formularen für Unterstützungsangebote. Regionale Dateien (FSW) erscheinen nur
     im passenden Bundesland.
   Aufgehobene Paragraphen fallen weg. Es gehen höchstens 10 Abschnitte weiter.
5. **Antwort-Aufruf** mit dem Schema `{aussagen: [{text, abschnitt_id, zitat}], verhalten, uebergabe_an}`. Das Modell
   bekommt nur die gefundenen Abschnitte mit ID, Quelle, Kontext und Text, in `<daten>` markiert.
6. **Zitatprüfung** (Server, ohne Modell):
   - Die `abschnitt_id` gehört zu den gelieferten Treffern.
   - Das Zitat ist nach `normalisiere()` und `normiere()` ein Teilstring des Abschnitts.
   - Das Zitat hat mindestens 6 Wörter oder 30 Zeichen.
   - Die Aussage ist durch Zitat und Kontext gedeckt (`deckung` ≥ `schwelle` aus `daten/deckung.yaml`, siehe unten).
   - Enthält das bis zum Satzende verlängerte Zitat eine Bedingung („wenn“, „sofern“, „soweit“, „falls“, „unter
     der Voraussetzung“, „bei Vorliegen“), trägt auch die Aussage eine („wenn“, „sofern“, „soweit“, „falls“,
     „nur“, „bei“, „unter“, „wer“; englisch „if“, „only“, „when“ u. a.). Sonst fällt sie weg (Review !69:
     „Familienmitglieder können Pflegegeld ohne Bevollmächtigung beantragen“ zu BPGG § 25 Abs. 2). Die
     Prüfung ist lexikalisch: Sie erkennt, dass eine Bedingung fehlt, nicht, ob es die richtige ist.
   Andere Aussagen fallen weg (`verworfen` nennt Grund und Deckung). Bleibt keine übrig, antwortet der Kern mit
   Abstinenz und Übergabe an die Stelle bzw. an eine Beratung.
7. **Beträge**:
   - Ein Euro-Betrag im Aussagetext muss mit demselben Zahlenwert im Zitat stehen, sonst fällt die Aussage weg.
     Englische Aussagen: Jede Ziffernfolge muss im Zitat stehen.
   - Ein Betrag ohne Stand der Fassung fällt weg.
   - Der Stand steht kurz im Halbsatz: „(BPGG § 5, Stand 2020)“.
   - Bei einer Fassung vor 2026-01-01 folgt „heute vielleicht höher“ im Halbsatz und einmal „Den aktuellen
     Betrag nennt Ihnen der Träger.“
   - Platzhalterdaten (vor 1900 oder ab 9000, z. B. 1111-11-11) gelten nicht als Stand.
8. **Nachprüfung** (`grenze.nachpruefung`) auf den fertigen Text. Sie prüft auf Diagnose („Sie haben eine …“),
   Dosierangaben und Befundbewertung; bei einem Treffer kommt der Grenztext.
9. **Text** (Sprache: `docs/plan/uc1/sprache.md`): Hauptaussage zuerst, je Aussage ein Satz mit Quelle im
   Halbsatz „(BPGG § 4)“. Zitat und Stand der Fassung stehen nur in `aussagen`/`belege` („Beleg anzeigen“).
   Danach folgen die zuständige Stelle mit Fundstelle und die nächsten Schritte in Sie-Form (Formular,
   Unterlagen mit Kurzquelle, Angebot mit Seite, Stelle). Ein Formular nennt der Kern nur für die Stellen in
   `fuer_stelle` (PAL080: PVA), sonst „Fragen Sie die {Stelle} nach dem Antrag.“ `sprache.glaette` läuft vor der
   Nachprüfung. Meldet `sprache.pruefe` danach im Modelltext noch etwas (außer dem Mittelwert der Satzlänge),
   kommt eine Ersatzantwort ohne Modelltext: fester Satz, Stelle, Schritte. Die
   Sprache ist DE oder EN (`eval.sprache`); Zitate bleiben im deutschen Original.
10. **Speichern**: Zustand nach `lotse.sitzung`, jedes geprüfte Zitat nach `lotse.beleg` (`call_id` für Voice).

Erweiterung allein: `erweitere(frage, modus="aus"|"thesaurus"|"llm")`. Im Kern liefert der Analyse-Aufruf die
Begriffe; fällt er aus oder ist der Modus `thesaurus`, kommen sie aus `thesaurus.yaml`. Gedeckelt sind sie auf 6
Begriffe mit je höchstens 4 Wörtern, ohne Ziffern und §.

## Deckung: Aussage nicht über das Zitat hinaus

`deckung(aussage, zitat, kontext)` ist der Anteil der Inhaltswörter der Aussage, die im Zitat oder im `kontext` des
Abschnitts (Überschrift) vorkommen. Stoppwörter fallen weg, Wörter werden grob gestammt (eine Endung ab), auch als
Teil einer Zusammensetzung gefunden („Vertrauensperson“ ⊃ „Person“) und über `gleich` abgebildet („Prozent“ ↔
„v. H.“). Die Deckung steht in `LotseAntwort.aussagen[].deckung` und bei verworfenen Aussagen in `verworfen`.

- **Entscheid: verwerfen, nicht kürzen.** Eine Kürzung ohne Modell könnte nur das Zitat selbst wiederholen; das
  steht im Stil `standard` ohnehin daneben. Der Antwort-Prompt verlangt dafür Aussagen nahe am Wortlaut, ohne
  Fristen, Ausnahmen, Vollmachten, Personen oder Folgen, die nicht im Zitat stehen.
- **Kalibrierung** an 8 handbeschrifteten Paaren aus dem Korpus (ASVG § 132, § 141, BPGG § 25, § 25a, FSW-Antrag
  S. 1; nicht aus `eval/lotse-set.yaml`), Paare in `daten/deckung.yaml`, Test `test_kalibrierpaare_…`:
  gedeckt 1,00 / 0,86 / 0,80 / 0,62, ungedeckt 0,40 / 0,40 / 0,12 / 0,11. Schwelle **0,50**, in der Mitte der
  Lücke 0,40–0,62. Bei 8 Paaren ist die Lücke klein belegt; ein neues Paar kann sie schließen.
- **Grenzen (für A2):** lexikalisch, nicht semantisch.
  - Eine vertauschte Verneinung bleibt unerkannt: „Die Kosten werden ersetzt“ gegen „… werden nicht ersetzt“ ergibt
    0,67.
  - Eine richtige, freie Umschreibung fällt durch: „Die Krankenkasse kann statt Sachleistungen Geld zahlen …“ zu
    ASVG § 132 ergibt 0,44.
  - Englische Aussagen werden nicht gemessen (`deckung = None`), weil sie mit dem deutschen Zitat kaum Wörter teilen.
  - Ob die Aussage aus dem Zitat folgt, misst weiter A2.

## Unterstützungsangebot mit Zitat (AC B)

Katalog- und Formular-Treffer haben feste Plätze (`MAX_ANGEBOTE = 4` von 10); vorher standen sie hinten und fielen
weg. Im Prompt tragen sie `art: "angebot"`, `datei` und `seite`, und `<angebote>` nennt ihre IDs als Pflicht. Ein
Zitat daraus prüft der Server wie jedes andere. `LotseAntwort.angebot_zitiert` ist `True`, wenn eine geprüfte
Aussage aus einem Angebot stammt; sonst bleibt der nächste Schritt mit Datei und Seite. Gemessen (Azure, Pflege,
Wien, PVA): mit dem Hinweis in 2 von 3 Läufen gesetzt, ohne ihn in 0 von 4. Im dritten verwarf die Wortlautprüfung alle drei FSW-Zitate: Der PDF-Text
ist zweispaltig verwürfelt, und das Modell glättet ihn beim Zitieren.

## Modus `sprache` (Voice)

`frage(..., modus="sprache")`, CLI `lotse frage --modus sprache`: kein Analyse-Aufruf (Angaben aus Regeln, Begriffe
aus dem Thesaurus), ein Antwort-Aufruf mit `aufwand="niedrig"` (`complete` kennt kein `max_tokens`), höchstens 2
Aussagen und halb so viel Abschnittstext. Text: höchstens 2 Sätze plus eine Zeile `Quelle: …` (bei Beträgen mit Stand), ohne Zitat und ohne
Liste; Träger, Schritte und Zitate bleiben in `LotseAntwort`. Der KI-Hinweis fehlt im Sprechtext und gehört in die
Ansage zu Gesprächsbeginn.

Gemessen am 2026-11-05 (Rechner A, Azure `gpt-5-4-mini`, 3 Wechsel, 2 Läufe):

| Wechsel | Lauf 1 | Lauf 2 |
|---|---:|---:|
| 1 Rückfrage (ohne Modell) | 5 ms | 66 ms |
| 2 Antwort (Antwort-Aufruf) | 2.054 ms (1.969) | 3.732 ms (3.642) |
| 3 Antwort (Antwort-Aufruf) | 3.070 ms (2.986) | 2.115 ms (2.032) |
| **Median** | **2.054 ms** | **2.115 ms** |

Das Ziel (Median ≤ 2,0 s) ist knapp verfehlt, und es hält nur, weil die Rückfrage ohne Modell zählt. Ein Wechsel mit
Antwort braucht 2,0–3,7 s; der Modellaufruf allein macht 96 % davon aus. Der nächste Hebel ist das Streamen oder
ein kleineres Modell, nicht der Kern.

## Datenquellen

| Datei | Inhalt | Quelle |
|---|---|---|
| `traeger.yaml` | Status → Stelle je Bereich, Gesetzesfilter | BPGG § 22 Abs. 1 Z 1, 3, 5 (Fassung ab 2026-05-20), Zitate wörtlich, per Test gegen die DB geprüft |
| `leistungen.yaml` | Pflegegeld, Pflegekarenzgeld, Rehabilitation/Kur, Krankengeld, Wochengeld, Unfallversicherung: Auslöser, Pflichtangaben, Rückfragen, Suche, Formular, Unterlagen | Normen-Überschriften im Korpus; Formulare PAL080 S. 2 und „Antrag Kur und Reha“ S. 2; Unfallversicherung: ASVG § 28 Z 1 (AUVA) und Z 2 (SVS für Selbständige, `stelle_je_status`), Zitate per Test gegen die DB geprüft |
| `deckung.yaml` | Stoppwörter, Gleichwerte, Schwelle, 8 Kalibrierpaare | Abschnitte aus `lotse.abschnitt`, handbeschriftet |
| `thesaurus.yaml` | 30 Einträge Bürgersprache → Fachbegriff | Überschriften im Korpus (`kontext ILIKE`), Themen aus dem Dev-Set d01–d12, nicht aus dem Lotse-Set |
| `grenzen.yaml` | Muster vor/nach, Notfall-, Grenz- und Injection-Text DE/EN | 144 Rettung, 1450 Gesundheitsberatung |
| `texte.yaml` | Textbausteine DE/EN | abgestimmt auf `eval/verhalten.yaml` (Antworten enthalten keine Übergabe-Phrasen) |

## Latenz je Schritt (gemessen 2026-11-05, Rechner A, Azure `gpt-5-4-mini`, Modus `llm`)

| Schritt | Wechsel 1 (Rückfrage) | Wechsel 2 (Bündel) | Grenzfall 23 |
|---|---:|---:|---:|
| Vorprüfung | 5 ms | 4 ms | 5 ms |
| Analyse (Modell) | 1.622 ms | 1.257 ms | – |
| Suche (4 Aufrufe) | – | 137 ms | – |
| Antwort (Modell) | – | 2.285 ms | – |
| Prüfung + Nachprüfung | – | 2 ms | – |
| Speichern | 2 ms | 2 ms | 2 ms |
| **gesamt** | **1.651 ms** | **3.715 ms** | **30 ms** |

Ein Lauf je Zeile, keine Verteilung. Das Voice-Ziel (Median ≤ 2,0 s, Review D5c) erreicht der Textpfad mit zwei
Modell-Aufrufen nicht. Für Voice läuft `erweiterung="thesaurus"`: kein Analyse-Aufruf, nur der Antwort-Aufruf.

## Bekannte Grenzen

- **Zitat belegt nicht automatisch die Aussage.** Im Lauf vom 2026-11-05 behauptete eine Aussage zu BPGG § 25,
  Familienmitglieder könnten ohne Vollmacht beantragen; das Zitat sagte das nicht. Die Deckung verwirft solche
  Zusätze jetzt, wenn sie neue Wörter bringen (Grenzen siehe Abschnitt Deckung). Ob die Aussage aus dem Zitat folgt,
  misst weiter A2.
- Unterstützungsangebote: zitiert in 2 von 3 Azure-Läufen, sonst nur im nächsten Schritt mit Datei und Seite
  (`angebot_zitiert=False`).

## UC4-Adapter (#107)

`uc1/uc1/uc4.py`, Aufruf `python -m uc1.uc4 --kontext DATEI.json "<frage>"`. `antwort(frage, kontext) -> dict` mit
genau den Feldern von `UcAntwort` (#96, lokale Kopie, nach dem Merge wechselt nur der Import). Ablauf: Vorprüfung
der Grenze, ein Modellaufruf (`{saetze: [str]}`, Stil einfach), Zahlenprüfung, Nachprüfung, eine inhaltsfreie
Zeile in `meta.protokoll` (`vorschlag_typ = auskunft`). Zahlen und Belege gehen unverändert durch. Ein Satz mit
einer Zahl, die nicht genau so im Kontext steht („rund 20“ statt „19,6“), fällt weg. Fehlt danach eine
Kontext-Zahl, hängt der Server „Bezeichnung: Wert Einheit.“ an. Ab zwei Kontext-Zahlen schreibt das Modell keine
Zahlen, weder als Ziffern noch als Wörter: Jeder Modellsatz mit Ziffer fällt weg, der Server setzt alle
Zahlensätze selbst (sonst bestanden vertauschte Werte). Ein Satz mit ausgeschriebener Zahl („sieben tausend“)
fällt immer weg; „ein“ und „eine“ zählen nicht. Gleiche Zahlensätze (dieselbe Zahl von UC3 und UC2) stehen nur
einmal, `zahlen` und `belege` bleiben vollständig. Die Einheit „Anzahl“ steht nicht im Satz. Zahlen aus der Frage gelten nicht als belegt. `anzeige` rechnet über `Decimal`: Das Minus
bleibt, `1e-07` wird „0,0000001“. Demo-Kontext (erfunden):
`uc1/tests/fixtures/uc4-wartezeiten.json`. Azure-Lauf 2026-11-05: 778 ms, mittlere Satzlänge 8,0 Wörter, Text
„Im Monat 08/2026 warteten Versicherte im Median 19,6 Tage. Das ist kürzer als im Vormonat. Im Vormonat waren es
23,1 Tage.“; Zahlen (19.6, Beleg 0) und (23.1, Beleg 1) unverändert. Einen UC1-eigenen Beleg fügt der Adapter noch
nicht hinzu.
- Die Grenzmuster sind ein Rauchtest. Fehlalarme sind möglich, z. B. „Befund … was bedeutet das für den Antrag?“.
  Die Abnahme prüft eine frische Session ohne die Liste.
- Ohne Status sucht der Kern ohne Gesetzesfilter; paralleles Recht ist dann nur auf 2 Treffer je Gesetz gedeckelt.
- Unterlagen für Krankengeld und Wochengeld sind im Korpus nicht belegt und fehlen deshalb.
- Unfallversicherung: Beamtinnen und Beamte (Dienstunfall, B-KUVG, BVAEB) sind nicht abgebildet und bekommen
  die AUVA genannt.
- Gegen aufgehobene Paragraphen filtert der Kern selbst (Kontext enthält „aufgehoben“), bis `uc1.suche` sie
  weglässt.
- Der mock-Provider zählt Aufrufe je Prozess. Ein CLI-Lauf mit `--provider mock` über zwei Wechsel liefert deshalb
  im zweiten Wechsel wieder die erste Fixture.

## Antragsangaben (#32)

Der Kern übernimmt Angaben für einen späteren Antrag in `zustand.antrag` (Schlüssel mit Punkt) und in
`LotseAntwort.antrag`. Gemeint sind Name, Geburtsdatum, Adresse und Telefon der Person (`person.*`), dazu Name
und Beziehung des Antragstellers (`antragsteller.*`) und die Antragsart (`antrag.art`). Daten:
`daten/antragsangaben.yaml`.

- **Regeln** (`regel_antrag`, Vorrang): Geburtsdatum nach „geboren/geb.“, als TT.MM.JJJJ und nur, wenn es das
  Datum gibt; österreichische PLZ mit Ort; Straße mit Hausnummer; Telefon (+43 oder nach „Telefon“); Beziehung („ich bin ihr Sohn“, „als
  Case-Managerin“); Antragsart („erhöhen“, „noch kein Pflegegeld“).
- **Analyse-Aufruf:** Das Schema hat ein Feld `antrag` (nur Namen, Text oder null). Ein Wert gilt nur, wenn er
  im Gespräch steht (`modell_antrag`). Geburtsdatum, Adresse und Telefon sind `nur_regel` und gehen maskiert ans
  Modell. `antrag.art`
  (`nur_regel`) fragt der Kern das Modell nicht: Im Azure-Lauf riet es „zuerkennung“.
- **Keine Rückfrage:** Antragsangaben stehen nicht in `pflicht` der Leistungen. Rückfragen bleiben bei höchstens
  3, Status zuerst. Was fehlt, steht im Antrag unter „noch offen“ (`docs/plan/uc1/antrag.md`).
- **Angebot:** Leistungen mit `antrag:` in `leistungen.yaml` (Pflegegeld, Rehabilitation) bringen den Schritt
  „Antrag vorbereiten …“ in `naechste_schritte`, bei beiden zusammen nur einmal (gleiche Schritte einmal). `LotseAntwort.antraege` nennt die Art für `lotse antrag`.
- **Regel „person: selbst“:** „ich bin“ zählt nicht mehr vor einer Rolle für eine andere Person („Ich bin
  Case-Managerin“, „ich bin ihr Sohn“). Vorher setzte das Gespräch aus dem Case-Management `person=selbst`.
