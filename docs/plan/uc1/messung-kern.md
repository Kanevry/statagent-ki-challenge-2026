# Messung: Suche im Lotse-Kern (`--kern`), Issue #30

Stand 2026-11-05, Rechner A (M4), DB `lotse` lokal (Port 5433), Weg `volltext`, Modell über `plattform.llm`
(Azure). Gemessen nur auf den Dev-Sets: `uc1/eval/dev-set.yaml` (d01–d12) und `uc1/eval/dev-set-2.yaml`
(e01–e24, 21 SozDok-zählend, 5 mit PDF-Quelle). Das Test-Set `lotse-set.yaml` wurde nicht gemessen
(Blickzähler unverändert 2 von 3).

## Was gemessen wird

- **volltext+E:** `uc1.suche.suche(weg=volltext)` mit der Erweiterung E aus `uc1.erweiterung`, ohne Filter.
- **kern+E:** `uc1.kern.kern_suche(erweiterung=E)`. Das ist derselbe Weg wie in `frage`: Vorprüfung,
  Analyse (Regeln, bei `llm` ein Analyse-Aufruf), SozDok mit Gesetzesfilter aus Leistung bzw. Status,
  PDF-Suche in Katalog und Formular. Ohne Rückfrage und ohne Antwort-Aufruf. Fehlt eine Pflichtangabe,
  sucht die Messung trotzdem, so wie der Kern nach der letzten Rückfrage.
- **SozDok-Rang:** im Kern über seine SozDok-Treffer (bis zu 10, so wie das Antwort-Modell sie sieht),
  ohne Kern über alle Treffer. **PDF-Rang:** im Kern über die Angebote, ohne Kern über alle Treffer.
  Gezählt wird seitengenau (neu: `trifft` vergleicht `seite`, wenn die erwartete Quelle eine nennt) und
  nur nach Datei.
- Eine Aufwärmrunde über alle Fälle (ohne Erweiterung, ohne Modell) wird nicht gezählt. Alle Aufrufe
  laufen über eine gemeinsame DB-Verbindung. Latenz bedeutet nur die Suche; Analyse und Erweiterung
  stehen unter Kosten.
- Die Anfrage enthält jetzt die Persona ohne Klammern (`eval.anfrage`). Die Dev-Sets haben keine Persona,
  ihre Anfragen ändern sich dadurch nicht.

Befehl, je Set und Stand gleich (aus `uc1/`):

```
UC1_DATA_DIR=… nice -n 10 uv run python werkzeuge/messen.py --nur-suche --kern \
  --set eval/dev-set.yaml --erweiterung aus,thesaurus,llm --ausgabe …
UC1_DATA_DIR=… nice -n 10 uv run python werkzeuge/messen.py --nur-suche --kern \
  --set eval/dev-set-2.yaml --erweiterung aus,thesaurus,llm --ausgabe …
```

Zeitpunkte: Vorher-Stand ca. 15:05–15:12, nach Änderung 1 ca. 15:18, nach Änderung 2 ca. 15:29
(2026-11-05, +01:00).

**Grenze der llm-Varianten:** Bei gleichem Code streuen sie von Lauf zu Lauf stark. volltext+llm auf
Dev-Set 1 hatte im Vorher-Lauf MRR 0,611 und im Lauf nach Änderung 1 MRR 0,487; an der nackten Suche hatte
sich nichts geändert. Über die Kern-Regeln entscheiden deshalb nur `aus` und `thesaurus`, die
deterministisch sind. Die llm-Zeilen zeigen die Größenordnung.

## Neu gezählt: symmetrische Ränge (Review !46)

Bis hierher zählte `--kern` die Ränge ungleich: die nackte Suche über ihre gemischte Liste (SozDok und PDF
in den ersten 10 Treffern), den Kern über seine SozDok-gefilterte Liste. Dieselbe Norm stand so einmal auf
Rang 6 und einmal auf Rang 1. Jetzt gilt auf beiden Seiten dieselbe Definition (`messe_kern_fall`): Rang in
der nach Quelle gefilterten Liste, je höchstens 10 Einträge. SozDok: SozDok-Treffer der nackten Suche gegen
SozDok-Treffer des Kerns. PDF: Formular- und Katalog-Treffer der nackten Suche gegen die Angebote des Kerns.
Die nackte Suche holt dafür 30 Treffer (`KERN_OHNE_TIEFE`), damit ihre gefilterten Listen so lang sein können
wie die des Kerns. Ihre Latenz ist deshalb nicht mit den alten Zeilen vergleichbar.

Lauf 2026-11-05 16:12 (Dev-Set 1) und 16:14 (Dev-Set 2), Stand `88bc419+dirty` auf Rechner A, gleicher Befehl
wie oben. Der Kern-Code war dabei der Arbeitsstand der parallelen Kern-Session. llm je Set ein Lauf, mit der
Streuung von oben. Alt = Tabellen „Endstand, nach Änderung 2“ unten (SozDok) bzw. Anhang #31 (Kern-PDF).

| Set, Maß | Variante | volltext alt (asymmetrisch) | volltext neu | kern neu | kern gegen volltext neu |
|---|---|---|---|---|---|
| D1 SozDok | aus | 2/12, MRR 0.188 | 2/12, MRR 0.189 | 2/12, MRR 0.181 | 0 : 0, p 1.000 |
| D1 SozDok | thesaurus | 10/12, MRR 0.683 | 10/12, MRR 0.683 | 9/12, MRR 0.639 | 0 : 1, p 1.000 |
| D1 SozDok | llm | 8/12, MRR 0.438 | 8/12, MRR 0.576 | 8/12, MRR 0.507 | 2 : 2, p 1.000 |
| D2 SozDok | aus | 1/21, MRR 0.021 | 1/21, MRR 0.052 | 4/21, MRR 0.093 | 3 : 0, p 0.250 |
| D2 SozDok | thesaurus | 1/21, MRR 0.052 | 1/21, MRR 0.052 | 4/21, MRR 0.093 | 3 : 0, p 0.250 |
| D2 SozDok | llm | 4/21, MRR 0.101 | 4/21, MRR 0.098 | 6/21, MRR 0.111 | 4 : 2, p 0.688 |
| D2 PDF seitengenau | aus | 2/5, MRR 0.179 | 4/5, MRR 0.700 | 4/5, MRR 0.700 | 0 : 0, p 1.000 |
| D2 PDF seitengenau | thesaurus | 1/5, MRR 0.100 | 3/5, MRR 0.400 | 3/5, MRR 0.500 | 0 : 0, p 1.000 |
| D2 PDF seitengenau | llm | 2/5, MRR 0.300 | 4/5, MRR 0.700 | 3/5, MRR 0.467 | 0 : 1, p 1.000 |
| D2 PDF nur Datei | aus | 2/5, MRR 0.279 | 5/5, MRR 0.867 | 5/5, MRR 0.900 | 0 : 0, p 1.000 |
| D2 PDF nur Datei | thesaurus | 1/5, MRR 0.200 | 5/5, MRR 0.767 | 5/5, MRR 0.900 | 0 : 0, p 1.000 |
| D2 PDF nur Datei | llm | 2/5, MRR 0.429 | 4/5, MRR 0.800 | 5/5, MRR 0.767 | 1 : 0, p 1.000 |

Folgerung: Bei SozDok ändert die symmetrische Zählung den Recall nicht, nur die MRR der nackten Suche
(D2 aus 0.021 → 0.052). Der Vorsprung des Kerns auf Dev-Set 2 (3 : 0) bleibt. Bei PDF verschwindet der
Vorsprung des Kerns: Gefiltert findet schon die nackte Suche 4/5 seitengenau und 5/5 die Datei. Der alte
Abstand kam aus der Zählung, nicht aus dem Kern. Alle Unterschiede bleiben bei n = 12, 21 bzw. 5 ohne
Signifikanz.

## Ergebnis (Endstand, nach Änderung 2) — asymmetrisch gezählt, ersetzt

Die volltext-Zeilen dieses Abschnitts sind gemischt gezählt, die kern-Zeilen gefiltert; ersetzt durch den
Abschnitt „Neu gezählt: symmetrische Ränge“ oben. Stehen gelassen als Beleg der damaligen Entscheidungen.

### Dev-Set 1, SozDok

| Weg | Recall@k | Wilson 95 % | MRR@10 | k | Latenz p50 (ms) | Latenz p95 (ms) |
|---|---|---|---|---|---|---|
| volltext+aus | 2/12 | 5 %–45 % | 0.188 | 5 | 32.7 | 133.8 |
| kern+aus | 2/12 | 5 %–45 % | 0.181 | 5 | 28.6 | 170.1 |
| volltext+thesaurus | 10/12 | 55 %–95 % | 0.683 | 5 | 57.7 | 86.2 |
| kern+thesaurus | 9/12 | 47 %–91 % | 0.639 | 5 | 47.3 | 134.8 |
| volltext+llm | 8/12 | 39 %–86 % | 0.438 | 5 | 91.0 | 121.5 |
| kern+llm | 8/12 | 39 %–86 % | 0.326 | 5 | 95.1 | 209.9 |
| B | gegen A | gewonnen : verloren | gleich | McNemar exakt p |
|---|---|---|---|---|
| kern+aus | volltext+aus | 0 : 0 | 12 | 1.000 |
| volltext+thesaurus | volltext+aus | 8 : 0 | 4 | 0.008 |
| volltext+llm | volltext+aus | 6 : 0 | 6 | 0.031 |
| kern+thesaurus | kern+aus | 8 : 1 | 3 | 0.039 |
| kern+llm | kern+aus | 6 : 0 | 6 | 0.031 |
| kern+thesaurus | volltext+thesaurus | 0 : 1 | 11 | 1.000 |
| kern+llm | volltext+llm | 2 : 2 | 8 | 1.000 |

### Dev-Set 2, SozDok

| Weg | Recall@k | Wilson 95 % | MRR@10 | k | Latenz p50 (ms) | Latenz p95 (ms) |
|---|---|---|---|---|---|---|
| volltext+aus | 1/21 | 1 %–23 % | 0.021 | 5 | 47.3 | 65.0 |
| kern+aus | 4/21 | 8 %–40 % | 0.105 | 5 | 37.3 | 107.3 |
| volltext+thesaurus | 1/21 | 1 %–23 % | 0.052 | 5 | 52.4 | 76.6 |
| kern+thesaurus | 4/21 | 8 %–40 % | 0.105 | 5 | 40.8 | 108.8 |
| volltext+llm | 4/21 | 8 %–40 % | 0.101 | 5 | 93.3 | 177.8 |
| kern+llm | 8/21 | 21 %–59 % | 0.233 | 5 | 75.2 | 135.1 |
| B | gegen A | gewonnen : verloren | gleich | McNemar exakt p |
|---|---|---|---|---|
| kern+aus | volltext+aus | 3 : 0 | 18 | 0.250 |
| volltext+thesaurus | volltext+aus | 0 : 0 | 21 | 1.000 |
| volltext+llm | volltext+aus | 3 : 0 | 18 | 0.250 |
| kern+thesaurus | kern+aus | 0 : 0 | 21 | 1.000 |
| kern+llm | kern+aus | 6 : 2 | 13 | 0.289 |
| kern+thesaurus | volltext+thesaurus | 3 : 0 | 18 | 0.250 |
| kern+llm | volltext+llm | 5 : 1 | 15 | 0.219 |

### Dev-Set 2, PDF seitengenau

| Weg | Recall@k | Wilson 95 % | MRR@10 | k | Latenz p50 (ms) | Latenz p95 (ms) |
|---|---|---|---|---|---|---|
| volltext-pdf+aus | 2/5 | 12 %–77 % | 0.179 | 5 | 50.0 | 67.4 |
| kern-pdf+aus | 1/5 | 4 %–62 % | 0.200 | 5 | 47.8 | 112.8 |
| volltext-pdf+thesaurus | 1/5 | 4 %–62 % | 0.100 | 5 | 70.0 | 90.5 |
| kern-pdf+thesaurus | 1/5 | 4 %–62 % | 0.200 | 5 | 73.2 | 143.5 |
| volltext-pdf+llm | 2/5 | 12 %–77 % | 0.300 | 5 | 85.7 | 109.5 |
| kern-pdf+llm | 1/5 | 4 %–62 % | 0.200 | 5 | 87.4 | 156.0 |
| B | gegen A | gewonnen : verloren | gleich | McNemar exakt p |
|---|---|---|---|---|
| kern-pdf+aus | volltext-pdf+aus | 0 : 1 | 4 | 1.000 |
| volltext-pdf+thesaurus | volltext-pdf+aus | 0 : 1 | 4 | 1.000 |
| volltext-pdf+llm | volltext-pdf+aus | 0 : 0 | 5 | 1.000 |
| kern-pdf+thesaurus | kern-pdf+aus | 0 : 0 | 5 | 1.000 |
| kern-pdf+llm | kern-pdf+aus | 0 : 0 | 5 | 1.000 |
| kern-pdf+thesaurus | volltext-pdf+thesaurus | 1 : 1 | 3 | 1.000 |
| kern-pdf+llm | volltext-pdf+llm | 0 : 1 | 4 | 1.000 |

### Dev-Set 2, PDF nur Datei

| Weg | Recall@k | Wilson 95 % | MRR@10 | k | Latenz p50 (ms) | Latenz p95 (ms) |
|---|---|---|---|---|---|---|
| volltext-pdf-datei+aus | 2/5 | 12 %–77 % | 0.279 | 5 | 50.0 | 67.4 |
| kern-pdf-datei+aus | 1/5 | 4 %–62 % | 0.200 | 5 | 47.8 | 112.8 |
| volltext-pdf-datei+thesaurus | 1/5 | 4 %–62 % | 0.200 | 5 | 70.0 | 90.5 |
| kern-pdf-datei+thesaurus | 1/5 | 4 %–62 % | 0.200 | 5 | 73.2 | 143.5 |
| volltext-pdf-datei+llm | 2/5 | 12 %–77 % | 0.429 | 5 | 85.7 | 109.5 |
| kern-pdf-datei+llm | 1/5 | 4 %–62 % | 0.200 | 5 | 87.4 | 156.0 |
| B | gegen A | gewonnen : verloren | gleich | McNemar exakt p |
|---|---|---|---|---|
| kern-pdf-datei+aus | volltext-pdf-datei+aus | 0 : 1 | 4 | 1.000 |
| volltext-pdf-datei+thesaurus | volltext-pdf-datei+aus | 0 : 1 | 4 | 1.000 |
| volltext-pdf-datei+llm | volltext-pdf-datei+aus | 0 : 0 | 5 | 1.000 |
| kern-pdf-datei+thesaurus | kern-pdf-datei+aus | 0 : 0 | 5 | 1.000 |
| kern-pdf-datei+llm | kern-pdf-datei+aus | 0 : 0 | 5 | 1.000 |
| kern-pdf-datei+thesaurus | volltext-pdf-datei+thesaurus | 1 : 1 | 3 | 1.000 |
| kern-pdf-datei+llm | volltext-pdf-datei+llm | 0 : 1 | 4 | 1.000 |

Dev-Set 1 hat keine PDF-Quelle.

## Befund

1. **Der Kern hilft dort, wo eine Leistung oder ein Status erkannt wird.** Auf Dev-Set 2 schlägt kern+aus
   die nackte Suche mit 4/21 gegen 1/21 (3 : 0) und kern+llm mit 8/21 gegen 4/21. Auf Dev-Set 1 liegt der Kern
   gleichauf oder einen Fall darunter. Keiner dieser Unterschiede ist bei n = 12 bzw. 21 signifikant
   (McNemar p ≥ 0,22).
2. **Ohne Erweiterung findet die Suche wenig:** Dev-Set 1 2/12, Dev-Set 2 1/21. Thesaurus und llm tragen auf
   Dev-Set 1 den Recall (10/12 bzw. 8–9/12), auf Dev-Set 2 kaum (thesaurus 1/21).
3. **PDF-Ziele fehlen im Kern, wenn keine Leistung mit `angebote` erkannt wird:** Bei e04, e14 und e16 findet
   die nackte Suche die Datei auf Rang 1–7, der Kern sucht dort gar nicht in PDFs (0 Angebote). Das ist ein
   generischer Mangel. Er ist nur auf Dev-Set 2 belegt, Dev-Set 1 hat keine PDF-Fälle. Nach der Regel
   (Beleg auf Dev-Set 1) bleibt er deshalb unverändert, siehe OPEN-QUESTIONS.
4. **Der Status-Filter schließt Verfahrensrecht aus:** e23 und e24 erwarten ASGG. Kein Status in
   `traeger.yaml` lässt ASGG zu, mit erkanntem Status ist es deshalb unerreichbar. Auch das ist nur auf
   Dev-Set 2 belegt und bleibt unverändert.
5. **Kosten:** kern+llm braucht einen Analyse-Aufruf je Frage (p50 ≈ 1,4 s), so viel wie die nackte
   llm-Erweiterung (p50 ≈ 1,0 s). Die Suche im Kern hat p50 30–95 ms und ist damit nicht langsamer als die
   nackte Suche, obwohl sie 2 bis 4 Suchaufrufe macht. Die Filter verkleinern die Kandidatenmenge.

## Änderungen am Kern (generisch, mit Vorher/Nachher)

### Änderung 1: `_je_gesetz` ordnet nach Vorrang, statt zu kappen

Mangel (Beleg Dev-Set 1, llm): Ohne Status holte die allgemeine Suche 10 Treffer und behielt höchstens 2 je
Gesetz. Stammten die Top 10 aus einem Gesetz, blieben 2 übrig: d09 hatte 2, d10 4 SozDok-Abschnitte.
Neu: zuerst höchstens 2 je Gesetz in Rangfolge, danach die übrigen. Paralleles Recht rückt weiter nach vorn
(Review N1), die Liste schrumpft aber nicht mehr. Test: `test_je_gesetz_ohne_status_schrumpft_nicht`.

| Set | Variante | vorher Recall / MRR | nach 1 Recall / MRR |
|---|---|---|---|
| Dev-Set 1 | kern+aus | 3/12 / 0.132 | 3/12 / 0.132 |
| Dev-Set 1 | kern+thesaurus | 9/12 / 0.565 | 9/12 / 0.565 |
| Dev-Set 1 | kern+llm | 8/12 / 0.269 | 6/12 / 0.253 |
| Dev-Set 2 | kern+aus | 4/21 / 0.093 | 4/21 / 0.093 |
| Dev-Set 2 | kern+thesaurus | 4/21 / 0.093 | 4/21 / 0.093 |
| Dev-Set 2 | kern+llm | 5/21 / 0.159 | 8/21 / 0.248 |

Wirkung: Mechanisch belegt (d10: 4 → 5 SozDok-Abschnitte im Kontext), im Recall@5 der deterministischen
Varianten auf beiden Sets 0. Die zusätzlichen Treffer stehen hinten. Die llm-Zeilen schwanken mit dem Modell
(siehe oben). Der Koordinator entscheidet, ob die Änderung ohne Recall-Gewinn bleibt; sie lässt sich
einzeln zurücknehmen.

### Änderung 2: Reißverschluss aus Frage-Treffern und Leistungssuche

Mangel (Beleg Dev-Set 1, thesaurus, deterministisch): `sammle_treffer` stellte alle Treffer der festen
Leistungssuchen (`suchanfrage` je Leistung) vor die Treffer zur Frage. Die fragespezifischen rutschten nach
hinten und fielen bei 10 Abschnitten weg: d01 Rang 2 → 5, d11 Rang 1 → 4, d07 Rang 5 → nicht im Kontext.
Neu: abwechselnd, die Frage zuerst. Test: `test_sammle_treffer_frage_vor_leistungssuche_im_wechsel`.

| Set | Variante | nach 1 Recall / MRR | nach 2 Recall / MRR |
|---|---|---|---|
| Dev-Set 1 | kern+aus | 3/12 / 0.132 | 2/12 / 0.181 |
| Dev-Set 1 | kern+thesaurus | 9/12 / 0.565 | 9/12 / 0.639 |
| Dev-Set 1 | kern+llm | 6/12 / 0.253 | 8/12 / 0.326 |
| Dev-Set 2 | kern+aus | 4/21 / 0.093 | 4/21 / 0.105 |
| Dev-Set 2 | kern+thesaurus | 4/21 / 0.093 | 4/21 / 0.105 |
| Dev-Set 2 | kern+llm | 8/21 / 0.248 | 8/21 / 0.233 |

Wirkung: Der MRR steigt in beiden deterministischen Varianten auf beiden Sets: Dev-Set 1 thesaurus
0,565 → 0,639, aus 0,132 → 0,181; Dev-Set 2 aus und thesaurus je 0,093 → 0,105. Je Fall auf Dev-Set 1,
thesaurus: d01 5 → 3, d11 4 → 1, die übrigen gleich. Kosten: Dev-Set 1 kern+aus verliert einen Fall im
Recall@5 (3/12 → 2/12). d12 wird nur über die Leistungssuche Pflegekarenzgeld getroffen und rutscht von
Rang 3 auf 6; im Kontext des Modells bleibt er. Auf Dev-Set 2 ist der Recall@5 unverändert.

## Rohdaten je Frage und Kosten (Endstand)

### Dev-Set 1

## Kosten je Variante

| Variante | LLM-Aufrufe | Analyse bzw. Erweiterung p50 (ms) | p95 (ms) | Suche p50 (ms) | p95 (ms) |
|---|---|---|---|---|---|
| volltext+aus | 0 | 0 | 0 | 33 | 134 |
| kern+aus | 0 | 0 | 0 | 29 | 170 |
| volltext+thesaurus | 0 | 0 | 4 | 58 | 86 |
| kern+thesaurus | 0 | 0 | 0 | 47 | 135 |
| volltext+llm | 12 | 1174 | 2700 | 91 | 122 |
| kern+llm | 12 | 1413 | 1978 | 95 | 210 |

### Rohdaten je Fall, Erweiterung aus

| Fall | erwartete Quellen | SozDok ohne | SozDok Kern | PDF ohne | PDF Kern | PDF-Datei ohne | PDF-Datei Kern | Leistungen | Angaben | Grenze | SozDok/Angebote im Kern | Hinweis |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| d01 | BPGG § 21c | – | – | – | – | – | – | pflegegeld | person=angehoerige | – | 8/1 | – |
| d02 | BPGG § 12 | 9 | – | – | – | – | – | pflegegeld | person=angehoerige | – | 8/1 | – |
| d03 | ASVG § 292; ASVG § 293 | – | – | – | – | – | – | – | – | – | 5/0 | – |
| d04 | GSVG § 86 | – | – | – | – | – | – | – | person=selbst, status=svs | – | 5/0 | – |
| d05 | ASVG § 154; ASVG § 137 | – | – | – | – | – | – | – | person=selbst | – | 5/0 | – |
| d06 | ASVG § 153 | – | – | – | – | – | – | – | – | – | 5/0 | – |
| d07 | ASVG § 258 | 1 | 1 | – | – | – | – | – | person=angehoerige | – | 5/0 | – |
| d08 | ASVG § 260; ASVG § 252 | – | – | – | – | – | – | – | person=angehoerige | – | 5/0 | – |
| d09 | ASVG § 203 | 7 | – | – | – | – | – | – | – | – | 5/0 | – |
| d10 | ASVG § 123 | – | – | – | – | – | – | – | person=angehoerige | – | 5/0 | – |
| d11 | ASVG § 18b; ASVG § 18a | 1 | 1 | – | – | – | – | pflegegeld | person=angehoerige | – | 8/1 | – |
| d12 | BPGG § 21c; FLAG § 38j | – | 6 | – | – | – | – | pflegekarenzgeld | person=angehoerige | – | 8/0 | – |

### Rohdaten je Fall, Erweiterung thesaurus

| Fall | erwartete Quellen | SozDok ohne | SozDok Kern | PDF ohne | PDF Kern | PDF-Datei ohne | PDF-Datei Kern | Leistungen | Angaben | Grenze | SozDok/Angebote im Kern | Hinweis |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| d01 | BPGG § 21c | 2 | 3 | – | – | – | – | pflegegeld | person=angehoerige | – | 8/1 | – |
| d02 | BPGG § 12 | – | – | – | – | – | – | pflegegeld | person=angehoerige | – | 8/1 | – |
| d03 | ASVG § 292; ASVG § 293 | 1 | 1 | – | – | – | – | – | – | – | 5/0 | – |
| d04 | GSVG § 86 | – | – | – | – | – | – | – | person=selbst, status=svs | – | 5/0 | – |
| d05 | ASVG § 154; ASVG § 137 | 1 | 1 | – | – | – | – | – | person=selbst | – | 5/0 | – |
| d06 | ASVG § 153 | 1 | 1 | – | – | – | – | – | – | – | 5/0 | – |
| d07 | ASVG § 258 | 5 | – | – | – | – | – | – | person=angehoerige | – | 5/0 | – |
| d08 | ASVG § 260; ASVG § 252 | 1 | 1 | – | – | – | – | – | person=angehoerige | – | 5/0 | – |
| d09 | ASVG § 203 | 1 | 1 | – | – | – | – | – | – | – | 5/0 | – |
| d10 | ASVG § 123 | 1 | 1 | – | – | – | – | – | person=angehoerige | – | 5/0 | – |
| d11 | ASVG § 18b; ASVG § 18a | 1 | 1 | – | – | – | – | pflegegeld | person=angehoerige | – | 8/1 | – |
| d12 | BPGG § 21c; FLAG § 38j | 2 | 3 | – | – | – | – | pflegekarenzgeld | person=angehoerige | – | 6/0 | – |

Begriffe (thesaurus), nackt | Kern:

- d01: Pflegekarenz, Pflegekarenzgeld | Pflegekarenz, Pflegekarenzgeld
- d02: Krankenanstalt, Anstaltspflege | Krankenanstalt, Anstaltspflege
- d03: Ausgleichszulage, Richtsatz | Ausgleichszulage, Richtsatz
- d04: Kostenbeteiligung, Ärztliche Hilfe | Kostenbeteiligung, Ärztliche Hilfe
- d05: Hilfsmittel, körperlichen Gebrechen | Hilfsmittel, körperlichen Gebrechen
- d06: Zahnersatz, Zahnbehandlung | Zahnersatz, Zahnbehandlung
- d07: Witwenpension, Hinterbliebenenpension | Witwenpension, Hinterbliebenenpension
- d08: Waisenpension | Waisenpension
- d09: Versehrtenrente | Versehrtenrente
- d10: Anspruchsberechtigung für Angehörige | Anspruchsberechtigung für Angehörige
- d11: Selbstversicherung, Zeiten der Pflege | Selbstversicherung, Zeiten der Pflege
- d12: Familienhospizkarenz, Pflegekarenzgeld | Familienhospizkarenz, Pflegekarenzgeld

### Rohdaten je Fall, Erweiterung llm

| Fall | erwartete Quellen | SozDok ohne | SozDok Kern | PDF ohne | PDF Kern | PDF-Datei ohne | PDF-Datei Kern | Leistungen | Angaben | Grenze | SozDok/Angebote im Kern | Hinweis |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| d01 | BPGG § 21c | 2 | 3 | – | – | – | – | pflegekarenzgeld, pflegegeld | person=angehoerige | – | 9/1 | – |
| d02 | BPGG § 12 | – | – | – | – | – | – | pflegegeld | person=angehoerige | – | 8/1 | – |
| d03 | ASVG § 292; ASVG § 293 | 8 | 1 | – | – | – | – | – | person=selbst, status=pva | – | 5/0 | – |
| d04 | GSVG § 86 | – | – | – | – | – | – | – | person=selbst, status=svs | – | 5/0 | – |
| d05 | ASVG § 154; ASVG § 137 | 1 | – | – | – | – | – | rehabilitation | person=selbst | – | 7/3 | – |
| d06 | ASVG § 153 | 2 | – | – | – | – | – | – | person=selbst | – | 5/0 | – |
| d07 | ASVG § 258 | 5 | 4 | – | – | – | – | – | person=angehoerige | – | 5/0 | – |
| d08 | ASVG § 260; ASVG § 252 | 1 | 2 | – | – | – | – | – | person=angehoerige | – | 5/0 | – |
| d09 | ASVG § 203 | 1 | 4 | – | – | – | – | krankengeld, rehabilitation | person=selbst | – | 7/3 | – |
| d10 | ASVG § 123 | 10 | 3 | – | – | – | – | – | person=angehoerige | – | 5/0 | – |
| d11 | ASVG § 18b; ASVG § 18a | 3 | 4 | – | – | – | – | pflegekarenzgeld, pflegegeld | person=angehoerige, status=keine_pension | – | 9/1 | – |
| d12 | BPGG § 21c; FLAG § 38j | 2 | 1 | – | – | – | – | pflegekarenzgeld | person=angehoerige | – | 8/0 | – |

Begriffe (llm), nackt | Kern:

- d01: Pflegekarenz, Pflegekarenzgeld, Angehörigenpflege, Pflege naher Angehöriger, Arbeitszeitreduktion | Pflegekarenz, Pflegekarenzgeld, Angehörigenpflege, Arbeitsreduktion, Pflegebedürftigkeit
- d02: Krankenhausaufenthalt, Anstaltspflege, Pflegegeld-Ruhen, Unterbringung, Weitergewährung | Spitalsaufenthalt, Auszahlung, Anspruch, Fortzahlung
- d03: Ausgleichszulage, Mindestsicherung, Pensionshöhe, Einkommensgrenze, Anrechenbare Einkünfte | Ausgleichszulage, Mindestpension, Pensionshöhe
- d04: Selbstversicherte, Behandlungsbeitrag, Kassenarzt, Wahlarzt, Kostenersatz | Selbstbehalt, Ärztliche Hilfe, Kostenbeteiligung, Kassenarzt
- d05: Hilfsmittel, Heilbehelfe, Sachleistungen, Kostenzuschuss | Rehabilitation, Heilbehelfe, Sachleistung, Krankenversicherung, Operation
- d06: Zahnersatz, Kassenleistung, Sachleistung, Heilbehelfe, Kostenzuschuss | Zahnersatz, Heilbehelfe, Sachleistung, Kostenersatz
- d07: Witwenpension, Hinterbliebenenpension, Witwerpension, Versorgungsanspruch, Pensionsanspruch | Witwenpension, Hinterbliebenenpension, Waisenpension, Pensionsversicherung, Versicherungsfall des Todes
- d08: Waisenpension, Halbwaise, Vollwaise, Anspruchsdauer, Kindesalter | Waisenpension, Halbwaisenrente, Vollwaisenrente, Hinterbliebenenleistung, Anspruchsdauer
- d09: Arbeitsunfall, Erwerbsfähigkeit, Minderung der Erwerbsfähigkeit, Versehrtenrente, Invalidität | Arbeitsunfall, Sachleistung, vorübergehende Arbeitsunfähigkeit, Wiederherstellung der Arbeitsfähigkeit
- d10: Lebensgefährte, Mitversicherung, Angehörige, Familienangehörige | Mitversicherung, Angehörige
- d11: Pflege eines nahen Angehörigen, Ersatzzeiten, Pflegezeit, freiwillige Weiterversicherung | Pflegekarenz, Pflegekarenzgeld, Angehörigenpflege, Haushaltsangehöriger
- d12: Sterbebegleitung, Pflegekarenz, Freistellung, Familienhospizkarenz | Pflegekarenz, Freistellung von der Arbeitsleistung, Pflegekarenzgeld, schwer kranke Kinder


### Dev-Set 2

## Kosten je Variante

| Variante | LLM-Aufrufe | Analyse bzw. Erweiterung p50 (ms) | p95 (ms) | Suche p50 (ms) | p95 (ms) |
|---|---|---|---|---|---|
| volltext+aus | 0 | 0 | 0 | 47 | 65 |
| kern+aus | 0 | 0 | 0 | 37 | 113 |
| volltext+thesaurus | 0 | 0 | 0 | 52 | 90 |
| kern+thesaurus | 0 | 0 | 0 | 47 | 143 |
| volltext+llm | 24 | 1018 | 1630 | 92 | 178 |
| kern+llm | 24 | 1520 | 2010 | 75 | 156 |

### Rohdaten je Fall, Erweiterung aus

| Fall | erwartete Quellen | SozDok ohne | SozDok Kern | PDF ohne | PDF Kern | PDF-Datei ohne | PDF-Datei Kern | Leistungen | Angaben | Grenze | SozDok/Angebote im Kern | Hinweis |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| e01 | BPGG § 4; BPGG § 5 | – | – | – | – | – | – | – | person=angehoerige | – | 5/0 | – |
| e02 | PAL080_0125_Mpfl_052026.pdf; PAL080_0125_Mpfl_052026.pdf | – | – | – | – | – | – | pflegegeld | bundesland=steiermark, person=angehoerige | – | 8/1 | – |
| e03 | ASVG § 139; ASVG § 138 | – | 2 | – | – | – | – | krankengeld | person=selbst | – | 8/0 | – |
| e04 | Serviceratgeber-2026_Broschuere_A5_OEAM_99-19_klein_korr.pdf | – | – | 7 | – | 7 | – | – | – | – | 5/0 | – |
| e05 | Antrag Kur und Reha.pdf; Antrag Kur und Reha.pdf | – | – | 4 | 1 | 4 | 1 | rehabilitation | – | – | 7/3 | – |
| e06 | ASVG § 143a; ASVG § 255b | – | – | – | – | – | – | – | person=selbst | – | 5/0 | – |
| e07 | ASVG § 162 | 3 | 1 | – | – | – | – | wochengeld | person=selbst | – | 8/0 | – |
| e08 | KBGG § 5; KBGG § 3 | – | – | – | – | – | – | – | person=angehoerige | – | 5/0 | – |
| e09 | ASVG § 255 | – | – | – | – | – | – | – | person=selbst | – | 5/0 | – |
| e10 | ASVG § 265 | – | – | – | – | – | – | – | – | – | 5/0 | – |
| e11 | ASVG § 175 | – | – | – | – | – | – | – | person=selbst | – | 5/0 | – |
| e12 | ASVG § 177; ASVG § 1 | 10 | – | – | – | – | – | – | person=selbst | – | 5/0 | – |
| e13 | ASVG § 131 | – | – | – | – | – | – | – | – | – | 5/0 | – |
| e14 | Antrag-auf-Zuschuss-zu-Fahrtkosten_Wien.pdf; ASVG § 135 | – | 5 | 2 | – | 1 | – | – | bundesland=wien, person=angehoerige, status=angestellt | – | 5/0 | – |
| e15 | ASVG § 51d | – | – | – | – | – | – | – | person=angehoerige | – | 5/0 | – |
| e16 | Serviceratgeber-2026_Broschuere_A5_OEAM_99-19_klein_korr.pdf; ASVG § 123 | – | – | – | – | – | – | – | person=angehoerige | – | 5/0 | – |
| e17 | GSVG § 2; GSVG § 4 | – | – | – | – | – | – | – | person=selbst, status=svs | – | 5/0 | – |
| e18 | GSVG § 104a | – | – | – | – | – | – | krankengeld | status=angestellt | – | 7/0 | – |
| e19 | BSVG § 2 | – | – | – | – | – | – | – | – | – | 5/0 | – |
| e20 | BSVG § 3; BSVG § 148c | – | – | – | – | – | – | – | person=angehoerige | – | 5/0 | – |
| e21 | B-KUVG § 63 | – | – | – | – | – | – | – | person=selbst, status=bvaeb | – | 5/0 | – |
| e22 | B-KUVG § 90 | – | 2 | – | – | – | – | – | person=selbst, status=bvaeb | – | 5/0 | – |
| e23 | ASGG § 67; ASGG § 65 | – | – | – | – | – | – | – | – | – | 5/0 | – |
| e24 | ASVG § 368; ASGG § 67 | – | – | – | – | – | – | – | – | – | 5/0 | – |

### Rohdaten je Fall, Erweiterung thesaurus

| Fall | erwartete Quellen | SozDok ohne | SozDok Kern | PDF ohne | PDF Kern | PDF-Datei ohne | PDF-Datei Kern | Leistungen | Angaben | Grenze | SozDok/Angebote im Kern | Hinweis |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| e01 | BPGG § 4; BPGG § 5 | – | – | – | – | – | – | – | person=angehoerige | – | 5/0 | – |
| e02 | PAL080_0125_Mpfl_052026.pdf; PAL080_0125_Mpfl_052026.pdf | – | – | – | – | – | – | pflegegeld | bundesland=steiermark, person=angehoerige | – | 8/1 | – |
| e03 | ASVG § 139; ASVG § 138 | – | 2 | – | – | – | – | krankengeld | person=selbst | – | 6/0 | – |
| e04 | Serviceratgeber-2026_Broschuere_A5_OEAM_99-19_klein_korr.pdf | – | – | – | – | – | – | – | – | – | 5/0 | – |
| e05 | Antrag Kur und Reha.pdf; Antrag Kur und Reha.pdf | – | – | – | 1 | – | 1 | rehabilitation | – | – | 7/3 | – |
| e06 | ASVG § 143a; ASVG § 255b | – | – | – | – | – | – | – | person=selbst | – | 5/0 | – |
| e07 | ASVG § 162 | 1 | 1 | – | – | – | – | wochengeld | person=selbst | – | 7/0 | – |
| e08 | KBGG § 5; KBGG § 3 | – | – | – | – | – | – | – | person=angehoerige | – | 5/0 | – |
| e09 | ASVG § 255 | – | – | – | – | – | – | – | person=selbst | – | 5/0 | – |
| e10 | ASVG § 265 | – | – | – | – | – | – | – | – | – | 5/0 | – |
| e11 | ASVG § 175 | – | – | – | – | – | – | – | person=selbst | – | 5/0 | – |
| e12 | ASVG § 177; ASVG § 1 | 10 | – | – | – | – | – | – | person=selbst | – | 5/0 | – |
| e13 | ASVG § 131 | – | – | – | – | – | – | – | – | – | 5/0 | – |
| e14 | Antrag-auf-Zuschuss-zu-Fahrtkosten_Wien.pdf; ASVG § 135 | – | 5 | 2 | – | 1 | – | – | bundesland=wien, person=angehoerige, status=angestellt | – | 5/0 | – |
| e15 | ASVG § 51d | – | – | – | – | – | – | – | person=angehoerige | – | 5/0 | – |
| e16 | Serviceratgeber-2026_Broschuere_A5_OEAM_99-19_klein_korr.pdf; ASVG § 123 | – | – | – | – | – | – | – | person=angehoerige | – | 5/0 | – |
| e17 | GSVG § 2; GSVG § 4 | – | – | – | – | – | – | – | person=selbst, status=svs | – | 5/0 | – |
| e18 | GSVG § 104a | – | – | – | – | – | – | krankengeld | status=angestellt | – | 7/0 | – |
| e19 | BSVG § 2 | – | – | – | – | – | – | – | – | – | 5/0 | – |
| e20 | BSVG § 3; BSVG § 148c | – | – | – | – | – | – | – | person=angehoerige | – | 5/0 | – |
| e21 | B-KUVG § 63 | – | – | – | – | – | – | – | person=selbst, status=bvaeb | – | 5/0 | – |
| e22 | B-KUVG § 90 | – | 2 | – | – | – | – | – | person=selbst, status=bvaeb | – | 5/0 | – |
| e23 | ASGG § 67; ASGG § 65 | – | – | – | – | – | – | – | – | – | 5/0 | – |
| e24 | ASVG § 368; ASGG § 67 | – | – | – | – | – | – | – | – | – | 5/0 | – |

Begriffe (thesaurus), nackt | Kern:

- e01: – | –
- e02: – | –
- e03: Arbeitsunfähigkeit, Krankengeld | Arbeitsunfähigkeit, Krankengeld
- e04: Krankenanstalt, Anstaltspflege, Ärztliche Hilfe, Kostenbeteiligung | Krankenanstalt, Anstaltspflege, Ärztliche Hilfe, Kostenbeteiligung
- e05: Festigung der Gesundheit, Rehabilitation, Ärztliche Hilfe, Kostenbeteiligung | Festigung der Gesundheit, Rehabilitation, Ärztliche Hilfe, Kostenbeteiligung
- e06: – | –
- e07: Wochengeld, Mutterschaft | Wochengeld, Mutterschaft
- e08: – | –
- e09: Alterspension | Alterspension
- e10: Hinterbliebenenpension | Hinterbliebenenpension
- e11: – | –
- e12: – | –
- e13: – | –
- e14: – | –
- e15: Anspruchsberechtigung für Angehörige | Anspruchsberechtigung für Angehörige
- e16: – | –
- e17: – | –
- e18: – | –
- e19: – | –
- e20: – | –
- e21: – | –
- e22: – | –
- e23: – | –
- e24: – | –

### Rohdaten je Fall, Erweiterung llm

| Fall | erwartete Quellen | SozDok ohne | SozDok Kern | PDF ohne | PDF Kern | PDF-Datei ohne | PDF-Datei Kern | Leistungen | Angaben | Grenze | SozDok/Angebote im Kern | Hinweis |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| e01 | BPGG § 4; BPGG § 5 | – | 2 | – | – | – | – | pflegegeld | person=angehoerige | – | 8/1 | – |
| e02 | PAL080_0125_Mpfl_052026.pdf; PAL080_0125_Mpfl_052026.pdf | – | – | – | – | – | – | pflegegeld | bundesland=steiermark, person=angehoerige, status=pva | – | 8/1 | – |
| e03 | ASVG § 139; ASVG § 138 | – | 2 | – | – | – | – | krankengeld | person=selbst, status=angestellt | – | 6/0 | – |
| e04 | Serviceratgeber-2026_Broschuere_A5_OEAM_99-19_klein_korr.pdf | – | – | – | – | 7 | – | krankengeld | person=selbst, status=angestellt | – | 6/0 | – |
| e05 | Antrag Kur und Reha.pdf; Antrag Kur und Reha.pdf | – | – | 1 | 1 | 1 | 1 | rehabilitation | person=selbst | – | 7/3 | – |
| e06 | ASVG § 143a; ASVG § 255b | 2 | 4 | – | – | – | – | krankengeld, rehabilitation | person=selbst, status=angestellt | – | 7/3 | – |
| e07 | ASVG § 162 | 4 | 1 | – | – | – | – | wochengeld | person=selbst, status=angestellt | – | 8/0 | – |
| e08 | KBGG § 5; KBGG § 3 | 2 | 1 | – | – | – | – | – | person=angehoerige | – | 5/0 | – |
| e09 | ASVG § 255 | – | – | – | – | – | – | – | person=selbst, status=angestellt | – | 5/0 | – |
| e10 | ASVG § 265 | 8 | – | – | – | – | – | – | person=selbst, status=pva | – | 5/0 | – |
| e11 | ASVG § 175 | – | 7 | – | – | – | – | krankengeld, rehabilitation | person=selbst, status=angestellt | – | 7/3 | – |
| e12 | ASVG § 177; ASVG § 1 | – | – | – | – | – | – | krankengeld | person=selbst, status=angestellt | – | 7/0 | – |
| e13 | ASVG § 131 | 6 | 4 | – | – | – | – | – | person=selbst | – | 5/0 | – |
| e14 | Antrag-auf-Zuschuss-zu-Fahrtkosten_Wien.pdf; ASVG § 135 | – | – | 2 | – | 1 | – | rehabilitation | bundesland=wien, person=angehoerige, status=angestellt | – | 7/3 | – |
| e15 | ASVG § 51d | – | – | – | – | – | – | – | person=angehoerige | – | 5/0 | – |
| e16 | Serviceratgeber-2026_Broschuere_A5_OEAM_99-19_klein_korr.pdf; ASVG § 123 | – | – | – | – | – | – | – | person=angehoerige | – | 5/0 | – |
| e17 | GSVG § 2; GSVG § 4 | – | – | – | – | – | – | – | person=selbst, status=svs | – | 5/0 | – |
| e18 | GSVG § 104a | – | – | – | – | – | – | krankengeld | person=selbst, status=angestellt | – | 6/0 | – |
| e19 | BSVG § 2 | 7 | – | – | – | – | – | – | person=selbst, status=svs | – | 5/0 | – |
| e20 | BSVG § 3; BSVG § 148c | – | – | – | – | – | – | krankengeld | person=angehoerige, status=svs | – | 8/0 | – |
| e21 | B-KUVG § 63 | – | 4 | – | – | – | – | – | person=selbst, status=bvaeb | – | 5/0 | – |
| e22 | B-KUVG § 90 | 3 | – | – | – | – | – | – | person=selbst, status=bvaeb | – | 5/0 | – |
| e23 | ASGG § 67; ASGG § 65 | – | – | – | – | – | – | – | person=selbst | – | 5/0 | – |
| e24 | ASVG § 368; ASGG § 67 | 9 | 1 | – | – | – | – | – | person=selbst | – | 5/0 | – |

Begriffe (llm), nackt | Kern:

- e01: Pflegegeld, Hilflosigkeit, Betreuungsbedarf, Grundpflege, Dauerzustand | Pflegegeld, erhebliche Pflegebedürftigkeit, Betreuungsbedarf, Hilflosigkeit, Sachleistung
- e02: zuständiger Versicherungsträger, Einbringung des Antrages, persönliche Abgabe, Wohnort Graz | persönliche Abgabe, Zuständigkeit
- e03: Arbeitsunfähigkeit, Krankengeld, Entgeltfortzahlung, Höchstbezugsdauer | Entgeltfortzahlung, Krankengeld, Arbeitsunfähigkeit, Versicherungsanstalt
- e04: Arbeitsunfähigkeit, Krankenstand, ärztliche Bestätigung | Arbeitsunfähigkeit, ärztliche Bestätigung, Krankengeld
- e05: Antrag auf Kur, ärztlicher Befund, Eigenangaben, ärztliche Stellungnahme, medizinische Begründung | Rehabilitation, ärztliche Bestätigung, Antragsformular
- e06: Invaliditätspension, Berufsunfähigkeitspension, Rehabilitationsgeld, Krankengeld, Wiedereingliederungsteilzeit | vorübergehende Arbeitsunfähigkeit, Krankengeld, Rehabilitation, Berufsunfähigkeit
- e07: Wochengeld, Karenzgeld, Mutterschutz, Beschäftigungsverbot, Schutzfrist | Wochengeld, Beschäftigungsverbot, Mutterschutz, Entbindung
- e08: Kinderbetreuungsgeld, Bezugsdauer, Wechsel der Betreuung, Partnerschaftsvariante, Anspruchsdauer | Kinderbetreuungsgeld, Wechsel der Elternteile, Anspruchsdauer, Bezugsvariante, Partnerschaftsregelung
- e09: Berufsunfähigkeit, Invaliditätspension, Leistungskalkül, gesundheitliche Voraussetzungen, Arbeitsfähigkeit, schwere körperliche Arbeit | Invaliditätspension, Berufsunfähigkeitspension, Erwerbsunfähigkeit, Schwerarbeit, Arbeitsunfähigkeit
- e10: Wiederverehelichung, Witwe, Abfindung, Waisenpension | Wiederverehelichung, Wegfall der Pension, Hinterbliebenenpension, Pensionsanspruch
- e11: Wegunfall, Arbeitsweg, Weg zur Arbeit, Unfallversicherung, Betriebsweg | Arbeitsunfall, Wegeunfall, Dienstverhinderung, Arbeitsunfähigkeit, Heilverfahren
- e12: Berufskrankheit, Hautekzem, Berufsunfähigkeit, Leistungspflicht | Berufskrankheit, Arbeitsunfähigkeit, Krankengeld
- e13: Wahlarzt, Kostenerstattung, Befund, Rechnung, Krankenbehandlung | Wahlarzt, Kostenerstattung, Behandlungskosten, Arztkosten
- e14: Krankenbehandlung, Fahrtkosten, Transporte, Heilbehandlung, Dialysebehandlung | Krankenbeförderung, Fahrtkosten, Sachleistung, Krankenbehandlung
- e15: Mitversicherung, Angehörigenversicherung, Beitragsfreiheit, Ehegattenmitversicherung, Familienversicherung | Mitversicherung, Ehegattin, Sachleistung, Beitragsfreiheit, Anspruch
- e16: Mitversicherung, Studienbestätigung, Schüler-Studentennachweis, Anstaltspflege, Familienangehörige, Selbsterhaltungsfähigkeit | Mitversicherung, Familienversicherung, Studiennachweis, Anspruch auf Mitversicherung, Krankenversicherung
- e17: nebenberufliche selbständige Tätigkeit, neue Selbständigkeit, Pflichtversicherung, Geringfügigkeitsgrenze, Mehrfachversicherung | Pflichtversicherung, Nebenerwerb, selbständige Tätigkeit, Meldung bei der SVS
- e18: Selbstversicherung Krankengeld, Krankengeldbezug, Ruhegeld, Versicherungsfall Krankheit, Versicherungsberechtigung | Arbeitsunfähigkeit, Selbständige, Leistungsanspruch, Versicherung
- e19: land- und forstwirtschaftliche Tätigkeit, Betrieb auf eigene Rechnung, geringfügige landwirtschaftliche Nutzung, Pflichtversicherung, Mitteilungspflicht | Pflichtversicherung, land- und forstwirtschaftlicher Betrieb, Mitteilungspflicht, Nebenerwerb
- e20: Unfallversicherung, landwirtschaftliche Mitarbeit, Angehörigenhilfe, Mithelfende Angehörige, Betriebsarbeit | Arbeitsunfall, Unfallversicherung, landwirtschaftliche Mitarbeit, Hilfe am Hof
- e21: Wahlarzt, Kostenersatz, Selbstbehalt, Vertragsarzt, Kassengebühr | Selbstbehalt, Wahlarzt, Kostenersatz, Vertragsarzt
- e22: Dienstverrichtung, Arbeitsunfall, Unfall im Dienst, häuslicher Arbeitsplatz | Arbeitsunfall, Unfall im Dienst
- e23: Bescheidbeschwerde, Rechtsmittelfrist, Pensionsantrag, Zurückweisungsbescheid, Berufung | Beschwerde, Rechtsmittel, Frist
- e24: Bescheidpflicht, Säumnisentscheidung, Frist zur Bescheiderlassung, Antrag auf Entscheidung, Untätigkeit der Kasse | Bescheid, Antrag, säumige Entscheidung, Frist, Ablehnung


---

## Anhang (#31): PDF-Suche immer, Verfahrensrecht für jeden Status, Etikett der Grenzantwort, hybrid

Stand 2026-11-05, Code 0d038dd plus die Änderungen unten. Zwischendurch kam 27d2e48 dazu, das nur ändert,
wie `--kern` den Kern lädt (importlib). Gemessen nur auf Dev-Set 1 (d01–d12) und Dev-Set 2 (e01–e24).
Das Test-Set wurde nicht gemessen. Rohberichte liegen in `uc1/laufzeit/kern31/` (nicht versioniert), der
gepaarte Vergleich kommt aus `uc1/werkzeuge/kern_paar.py`.

### Befehle und Zeitpunkte

Rechner A, aus `uc1/`, `UC1_DATA_DIR=…`, je Stand (S = vorher | n1 | n2):

```
nice -n 10 uv run python werkzeuge/messen.py --nur-suche --kern --set eval/dev-set.yaml \
  --erweiterung aus,thesaurus,llm --ausgabe laufzeit/kern31/S-s1-a.md      # llm Lauf 1
nice -n 10 uv run python werkzeuge/messen.py --nur-suche --kern --set eval/dev-set.yaml \
  --erweiterung llm --ausgabe laufzeit/kern31/S-s1-b.md                     # llm Lauf 2
# dasselbe mit --set eval/dev-set-2.yaml (…-s2-a.md, …-s2-b.md)
uv run python werkzeuge/kern_paar.py laufzeit/kern31/vorher-s2-a.md laufzeit/kern31/n1-s2-a.md \
  --erweiterung aus --spalte "SozDok Kern" --spalte "PDF Kern" --spalte "PDF-Datei Kern"
```

Zeitpunkte (+01:00): vorher 15:35–15:39, nach Änderung 1 15:39–15:41, nach Änderung 2 15:41–15:43.
Begriffe für Rechner B (`--nur-begriffe … --erweiterung llm`, je Set eine Datei) um 15:44, Messung auf
Rechner B 15:45–15:47.

Gezählt wird SozDok im Kern über seine SozDok-Treffer und PDF über die Angebote, k = 5. Dev-Set 2 hat
n = 21 für SozDok und n = 5 für PDF. Der llm-Modus streut: Bei unverändertem Code lag kern+llm auf Dev-Set 1
einmal bei 5/12 und einmal bei 8/12, auf Dev-Set 2 bei 10/21 und bei 7/21. Entscheidend sind deshalb `aus`
und `thesaurus`, die deterministisch sind. Die zwei llm-Läufe stehen als Lauf 1 und Lauf 2 daneben.

### Änderung 1: PDF-Suche mit der Frage, auch ohne erkannte Leistung (`sammle_treffer`)

Der Kern sucht jetzt immer auch mit der (erweiterten) Frage in Katalog und Formular, k = 3 nach Regionalfilter.
Die Treffer zur Leistung bleiben vorn, die Frage-Treffer kommen im Reißverschluss dazu, `MAX_ANGEBOTE` = 4
deckelt die Plätze. Regionale Dateien anderer Bundesländer fallen auch bei Frage-Treffern weg (Vereinigung
der `regional`-Marken aller Leistungen). Gepaart nach Änderung 1 gegen vorher:

| Set, Maß | Erweiterung | vorher | nach Ä1 | Wilson 95 % nach | gewonnen : verloren | McNemar p | Fälle |
|---|---|---|---|---|---|---|---|
| D1 SozDok | aus | 2/12 | 2/12 | 5 %–45 % | 0 : 0 | 1.000 | – |
| D1 SozDok | thesaurus | 9/12 | 9/12 | 47 %–91 % | 0 : 0 | 1.000 | – |
| D1 SozDok | llm Lauf 1 / 2 | 5/12 / 8/12 | 9/12 / 10/12 | 47 %–91 % / 55 %–95 % | 5 : 1 / 2 : 0 | 0.219 / 0.500 | Streuung |
| D2 SozDok | aus | 4/21 | 4/21 | 8 %–40 % | 0 : 0 | 1.000 | – |
| D2 SozDok | thesaurus | 4/21 | 4/21 | 8 %–40 % | 0 : 0 | 1.000 | – |
| D2 SozDok | llm Lauf 1 / 2 | 10/21 / 7/21 | 5/21 / 10/21 | 11 %–45 % / 28 %–68 % | 0 : 5 / 4 : 1 | 0.062 / 0.375 | Streuung |
| D2 PDF seitengenau | aus | 1/5 | 4/5 | 38 %–96 % | 3 : 0 | 0.250 | +e04, e14, e16 |
| D2 PDF seitengenau | thesaurus | 1/5 | 3/5 | 23 %–88 % | 2 : 0 | 0.500 | +e14, e16 |
| D2 PDF seitengenau | llm Lauf 1 / 2 | 1/5 / 1/5 | 4/5 / 5/5 | 38 %–96 % / 57 %–100 % | 3 : 0 / 4 : 0 | 0.250 / 0.125 | +e04, e14, e16 (, e02) |
| D2 PDF nur Datei | aus, thesaurus, llm 1, llm 2 | 1/5 | 5/5 | 57 %–100 % | 4 : 0 | 0.125 | +e02, e04, e14, e16 |

Dev-Set 1 hat keine PDF-Quelle. SozDok@5 kann sich durch Änderung 1 nicht ändern: Die SozDok-Reihenfolge
bleibt gleich, nur die Plätze 7–10 können an Angebote gehen. Die llm-Ausschläge in beiden Richtungen sind
Streuung, `aus` und `thesaurus` bleiben gleich. Die Änderung bleibt: Sie schadet auf keinem Set und hebt
PDF auf Dev-Set 2 in jeder Erweiterung (nur Datei 1/5 → 5/5). Einzeln ist das nicht signifikant (n = 5).

### Änderung 2: Verfahrensrecht unabhängig vom Status (`traeger.yaml` `verfahren`, `_mit_verfahrensrecht`)

Der Gesetzesfilter entstand bisher allein aus `status.<s>.gesetze`, damit fehlte das ASGG bei jedem Status,
und SVS und BVAEB hatten auch kein ASVG-Verfahrensrecht. Neu gilt der Block `verfahren` für jeden Status:
`gesetze: [ASGG]` immer, `paragraphen: {ASVG: [354, 368]}` nur mit diesem Bereich, wenn der Status das ASVG
nicht ohnehin enthält. GSVG § 194, BSVG § 182 und B-KUVG § 129 verweisen wörtlich auf den Siebenten Teil
des ASVG (im Korpus geprüft). Bei einem Bereich holt die Frage-Suche 3 × 5 Treffer und verwirft
ASVG-Treffer außerhalb von §§ 354–368. Ohne Status bleibt die Suche wie bisher ungefiltert. Die festen
Leistungssuchen bleiben ohne Verfahrensrecht. Gepaart nach Änderung 2 gegen nach Änderung 1:

| Set, Maß | Erweiterung | nach Ä1 | nach Ä2 | gewonnen : verloren | McNemar p |
|---|---|---|---|---|---|
| D1 SozDok | aus / thesaurus | 2/12 / 9/12 | 2/12 / 9/12 | 0 : 0 / 0 : 0 | 1.000 |
| D1 SozDok | llm Lauf 1 / 2 | 9/12 / 10/12 | 6/12 / 7/12 | 1 : 4 / 0 : 3 | 0.375 / 0.250 |
| D2 SozDok | aus / thesaurus | 4/21 / 4/21 | 4/21 / 4/21 | 0 : 0 / 0 : 0 | 1.000 |
| D2 SozDok | llm Lauf 1 / 2 | 5/21 / 10/21 | 8/21 / 8/21 | 3 : 0 / 3 : 5 | 0.250 / 0.727 |
| D2 PDF seitengenau | aus / thesaurus | 4/5 / 3/5 | 4/5 / 3/5 | 0 : 0 / 0 : 0 | 1.000 |
| D2 PDF seitengenau | llm Lauf 1 / 2 | 4/5 / 5/5 | 3/5 / 5/5 | 0 : 1 / 0 : 0 | 1.000 |

Die verlorenen llm-Fälle auf Dev-Set 1 (d02, d05, d07, d12) haben in beiden Läufen keinen Status in der
Analyse. Für sie ist Änderung 2 ein No-op, der Unterschied ist also Streuung. Dasselbe gilt für PDF (e14), das
Änderung 2 nicht berührt. Auf beiden Dev-Sets ist die Änderung neutral: e23 und e24 (ASGG) haben keinen
Status und waren schon ungefiltert. Sie bleibt, weil sie eine Lücke für jede Verfahrensfrage mit Status
schließt. Ein Unit-Test belegt das mit SVS: ASGG § 67 und ASVG § 361 kommen durch, ASVG § 255 nicht.
Am Ranking von e23 und e24 ändert die Änderung nichts.

### Änderung 3: Etikett der Grenzantwort

`_grenzantwort` setzt `verhalten="uebergabe"` und `uebergabe_an` (Notfall: „Rettung 144; Gesundheitsberatung
1450“, sonst „Ärztin oder Arzt; Gesundheitsberatung 1450; Rettung 144“). `LotseAntwort` hat dafür das neue
Feld `uebergabe_an`. Das Etikett stimmt jetzt mit `klassifiziere_verhalten` überein: Die Tests
`test_grenzfall_antwortet_ohne_modell` und `test_nachpruefung_ersetzt_diagnose_im_modelltext` prüfen
`verhalten == "uebergabe" == klassifiziere_verhalten(text)`. Die Suche ändert sich dadurch nicht.

### Endstand auf Rechner A, gegen vorher

| Set, Maß | aus | thesaurus | llm Lauf 1 | llm Lauf 2 |
|---|---|---|---|---|
| D1 SozDok | 2/12 → 2/12 (0 : 0) | 9/12 → 9/12 (0 : 0) | 5/12 → 6/12 (2 : 1, p 1.000) | 8/12 → 7/12 (1 : 2, p 1.000) |
| D2 SozDok | 4/21 → 4/21 (0 : 0) | 4/21 → 4/21 (0 : 0) | 10/21 → 8/21 (3 : 5, p 0.727) | 7/21 → 8/21 (3 : 2, p 1.000) |
| D2 PDF seitengenau | 1/5 → 4/5 (3 : 0, p 0.250) | 1/5 → 3/5 (2 : 0, p 0.500) | 1/5 → 3/5 (2 : 0, p 0.500) | 1/5 → 5/5 (4 : 0, p 0.125) |
| D2 PDF nur Datei | 1/5 → 5/5 (4 : 0, p 0.125) | 1/5 → 5/5 (4 : 0) | 1/5 → 5/5 (4 : 0) | 1/5 → 5/5 (4 : 0) |

### Hybrid gegen volltext auf Rechner B (`--nur-suche`, ohne Kern)

Der Stand mit allen Änderungen kam gepackt (`repo-packen`, sha256 9e331fe7…4dc8) nach Rechner B und wurde
dort entpackt. Die DB auf B hatte das Flag schon (1141 von 14.256 Dokumenten `meta.aufgehoben`, wie auf A),
ein neuer Ingest war nicht nötig. Es gibt 122.618 Vektoren (61.309 je 768 und 256). Hybrid läuft mit 256 d,
MPS, HF offline und einem Prozess. Die llm-Begriffe kamen als Datei von A, weil B keine Modellzugänge hat.

```
<hilfsskript> messen --nur-suche --set eval/dev-set.yaml --weg volltext,hybrid \
  --erweiterung aus,thesaurus,datei:<B>/begriffe-llm-s1.json --ausgabe <B>/log/kern31-s1.md
<hilfsskript> messen --nur-suche --set eval/dev-set-2.yaml --weg volltext,hybrid \
  --erweiterung aus,thesaurus,datei:<B>/begriffe-llm-s2.json --ausgabe <B>/log/kern31-s2.md
```

Ohne Kern zählt der Bericht je Fall den ersten Treffer irgendeiner erwarteten Quelle. Getrennt ist unten
„nur §“ (Fälle nur mit Rechtsquelle) und „mit PDF“ (e02, e04, e05, e14, e16; bei e14 und e16 zählt auch
die §-Quelle). Gepaart hybrid gegen volltext bei gleicher Erweiterung, k = 5:

| Set | Fälle | Erweiterung | volltext | hybrid | gewonnen : verloren | McNemar p | gewonnen / verloren |
|---|---|---|---|---|---|---|---|
| D1 | nur § (12) | aus | 2/12 (5 %–45 %) | 3/12 (9 %–53 %) | 1 : 0 | 1.000 | d06 / – |
| D1 | nur § (12) | thesaurus | 10/12 (55 %–95 %) | 8/12 (39 %–86 %) | 0 : 2 | 0.500 | – / d01, d07 |
| D1 | nur § (12) | llm-Datei | 10/12 (55 %–95 %) | 6/12 (25 %–75 %) | 0 : 4 | 0.125 | – / d01, d07, d09, d10 |
| D2 | nur § (19) | aus | 1/19 (1 %–25 %) | 1/19 (1 %–25 %) | 1 : 1 | 1.000 | e22 / e07 |
| D2 | nur § (19) | thesaurus | 1/19 (1 %–25 %) | 1/19 (1 %–25 %) | 1 : 1 | 1.000 | e22 / e07 |
| D2 | nur § (19) | llm-Datei | 3/19 (6 %–38 %) | 4/19 (9 %–43 %) | 2 : 1 | 1.000 | e03, e10 / e06 |
| D2 | mit PDF (5) | aus | 2/5 (12 %–77 %) | 2/5 (12 %–77 %) | 0 : 0 | 1.000 | – |
| D2 | mit PDF (5) | thesaurus | 1/5 (4 %–62 %) | 2/5 (12 %–77 %) | 1 : 0 | 1.000 | e05 / – |
| D2 | mit PDF (5) | llm-Datei | 3/5 (23 %–88 %) | 4/5 (38 %–96 %) | 1 : 0 | 1.000 | e04 / – |
| D2 | alle (24) | llm-Datei | 6/24 (12 %–45 %) | 8/24 (18 %–53 %) | 3 : 1 | 0.625 | laut Bericht |

**Ergebnis:** Hybrid zeigt auf Dev-Set 2 keinen klaren Gewinn. Es sind höchstens 1 bis 2 Fälle netto, und
kein Vergleich ist signifikant. Auf Dev-Set 1 verliert hybrid mit thesaurus (0 : 2) und mit llm-Begriffen
(0 : 4, p 0,125). Damit ist die Bedingung „Gewinn auf Dev-Set 2 ohne Verlust auf Dev-Set 1“ nicht erfüllt.
`kern_suche`, `kern_belege` und `frage` bekommen deshalb keinen Parameter `weg`, der Kern bleibt bei
`volltext`. Empfehlung: hybrid nicht in den Kern übernehmen. Ein neuer Anlauf lohnt erst mit einer anderen
Fusion (Gewichtung oder RRF-Konstante) und erneut gepaart auf beiden Dev-Sets.
