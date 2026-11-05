# Review Architektur UC1 „KI-Lotse“ vor dem Kern (#31)

Stand 2026-11-05, ca. 13:40 bis 14:10 CET. Prüfer: unabhängige Review-Session (Claude), Worktree `b-uc1`, Basis
`a930302` plus uncommittete Arbeit an `suche.py`, `typen.py` und `vektoren.py` (nicht verändert). Vorgehen: Grill
(eine Entscheidung nach der anderen, gegen Code, SQL und Quellen) im Berichtsmodus, ohne Rückfragen. Gemessen wurde
auf dem M4 nur lesend gegen die DB `lotse` (keine Modelle geladen). Der Reranker lief auf m5 in einem Prozess mit
batch 8.

## 1. Kurzfassung: Top 5 nach Wert je Aufwand

| # | Empfehlung | Beleg (Kurzform) | Konfidenz | Zeitfenster |
|---|---|---|---:|---|
| 1 | **Anfrage um Fachbegriffe in Gesetzessprache erweitern.** Das LLM liefert 3–6 Stichwörter, die an die Bürgerfrage angehängt werden; die Frage selbst bleibt. Dazu ein kleiner Thesaurus Bürgerwort → Rechtsbegriff als Daten für die Demo-Szenarien und den Voice-Pfad. Terme deckeln (Latenz). | Dev-Set n=12: Recall@5 2/12 → 9/12 mit blind erzeugten Begriffen (Haiku), Paarvergleich 7 gewonnen : 0 verloren, exakter McNemar p = 0,016 | 80 % | jetzt (≤ 1 h) |
| 2 | **Gesetzesfilter aus der Status-Rückfrage, aber den Filter-Bug zuerst beheben:** `_FILTER` wirft mit gesetzten `gesetze` alle PDFs hinaus (Serviceratgeber, FSW, Formulare). AC B verlangt aber ein Angebot „mit Seite“. | Code `suche.py` `_FILTER`; gemessen 0 PDFs in 24/24 gefilterten Läufen. Mit Filter und Begriffen: Recall@5 12/12 | 90 % (Bug), 65 % (Gewinn hält) | jetzt (≤ 1 h) |
| 3 | **Aufgehobene §§ aus dem Standard-Ranking nehmen** (Kennzeichen beim Ingest, Filter in Volltext und dicht). Für eine Antwort „wurde aufgehoben“ bleiben sie abrufbar. | 1.046 SozDok-Dokumente mit „aufgehoben“ in der Überschrift. Original-Dev-Fragen: bei 3/12 steht ein aufgehobener § auf Rang 1. „Kann ich in Gleitpension gehen?“: Top 3 alle aufgehoben | 90 % | jetzt (≤ 30 min) |
| 4 | **Beträge nie ungeprüft aus dem Gesetzestext.** Euro-Beträge nur mit Stand und nur aus einer Quelle des laufenden Jahres, sonst Betrag weglassen und auf die Stelle verweisen. Platzhalter-Daten (1111-11-11, 8888-08-08) nie als „Stand“ zeigen. | BPGG § 5 im Korpus nennt für Stufe 1 157,30 €, geltend sind 2026 206,20 € (+31 %) | 85 % | jetzt (≤ 1 h) |
| 5 | **Messung entschärfen, bevor der Kern darauf optimiert wird:** Phrasenlisten korrigieren (z. B. „in meinen quellen finde ich“ und „keine medizinische“ zählen als Abstinenz), Mindestlänge für Zitate, Dev/Test-Trennung mit Blickzähler, Wilson-Intervalle in `messung.md` | Code `eval.py`, `verhalten.yaml`; 5/15 hat das 95-%-Intervall 15–58 % | 85 % | jetzt (≤ 45 min) |

**Nicht tun:** den Cross-Encoder `BAAI/bge-reranker-v2-m3` über die Volltext-Kandidaten legen. Auf dem Dev-Set
verschlechtert er beide guten Varianten. Mit von Hand erweiterten Anfragen fällt Recall@5 von 11/12 auf 9/12
und MRR@10 von 0,82 auf 0,37, mit den LLM-Begriffen von 9/12 auf 7/12 (MRR 0,67 → 0,26). Ein CPU-Gegenlauf mit
Top 20 zeigt dasselbe Bild. Auf dem belasteten m5 kostet er p50 6,6 s je Frage (MPS, 50 Paare) bzw. 10 s (CPU,
20 Paare). Konfidenz 70 %, Details in Befund D7. Das spart 1–2 h Einbau.

## 2. Befunde

### D1 · Suche (Volltext) und „jüngste Fassung“

**D1a · Die Regel „jüngste Fassung je §“ greift in diesem Korpus nie.**
- Behauptung: Jede Kombination (Gesetz, Art, Nummer) kommt genau einmal vor. Der Korpus ist ein Schnappschuss mit
  einer Fassung je §. Die Gruppierung in `_ein_treffer_je_paragraph` legt deshalb nur die Absätze desselben §
  zusammen. Das ist nützlich für die Vielfalt der Treffer, juristisch aber ohne Wirkung.
- Beleg: M4, SQL `select n, count(*) from (select gesetz, art, nummer, count(*) n from lotse.dokument where
  quelle='sozdok' group by 1,2,3) g group by 1` → `1|14244`. Kein `inkrafttreten` liegt nach heute (0 von 14.244,
  Maximum 2026-10-01). `akra` ist nur einmal gesetzt, als Platzhalter 8888-08-08 (BSVG § 88). Das Platzhalterdatum
  1111-11-11 steht bei FLAG und den 136 `veraendW`-Dokumenten. Die gefragten Fassungen: BPGG § 4 = 1 Fassung, ikra
  2015-01-01 (dokid `BPGG=PARA=4=12=2015-01-13=2015-01-01`); ASVG § 139 = 1, ikra 2026-04-01; ASVG § 136 = 1, ikra
  2026-01-01.
- Widerspruch: Laut PRD (Pre-Mortem A) wiederholen sich bei `abkrvo+gldart+gldnr+ikra` 14 Tupel auf 51 Dateien. In
  der DB ist schon das gröbere (Gesetz, Art, Nummer) eindeutig. Die PRD-Zahl stammt vermutlich aus Dateinamen; das
  ist ungeklärt.
- Konfidenz: 95 % (direkte Zählung; offen ist nur die Herkunft der PRD-Zahl).
- Empfehlung: übernehmen, aber ehrlich benennen. Die Regel als „ein Abschnitt je §“ dokumentieren. Den Stand je
  Zitat als „Fassung ab <ikra>“ ausgeben, Platzhalterdaten unterdrücken. Aufwand 15 min.
- Nächster Check: `select count(*) from lotse.dokument where inkrafttreten < '1900-01-01'` muss in der Anzeige zu
  „Stand unbekannt“ führen (Unit-Test am Zitierschlüssel).

**D1b · Das eigentliche juristische Risiko sind aufgehobene §§ und veraltete Beträge, nicht die Fassung.**
- Behauptung: (1) 1.046 SozDok-Dokumente sind Stummel wie „§ 253c. Aufgehoben.“, und sie ranken hoch: Sie sind kurz,
  werden also kaum abgewertet, und ihre Überschrift trägt Gewicht A. (2) Gesetzestexte nennen Beträge, die seither
  valorisiert wurden.
- Beleg:
  - (1) SQL: Abschnitte mit `nr = 0` und `kontext ~* 'aufgehoben'` → 1.046 Dokumente (ASVG 194, BSVG 84, GSVG 83 bei
    den Stummeln unter 200 Zeichen). Die Dev-Läufe (Testprotokoll) zeigen den Effekt: d02 → Rang 1 „ASVG § 206
    aufgehoben - Pflegegeld“, d03 → Rang 1 „ASVG § 264a aufgehoben - Zuschlag zur Witwenpension“, d06 → Rang 1
    „ASVG § 34b aufgehoben“. Die Probe „Kann ich in Gleitpension gehen?“ liefert ASVG § 253c, GSVG § 131b und BSVG
    § 122b auf den Rängen 1–3, alle aufgehoben.
  - (2) BPGG § 5 Abs. 1 (ikra 2020-01-01) im Korpus: „in Stufe 1 … 157,30 Euro … Stufe 7 … 1688,90 Euro“, Abs. 2
    verweist auf die jährliche Anpassung ab 2020. Geltend 2026: Stufe 1 206,20 €, Stufe 7 2.214,80 € (+2,7 % zum
    1.1.2026). Quelle: PVÖ „Wichtige Zahlen 2026“,
    https://pvoe.at/fileadmin/user_upload/pvoe-bund/Dokumente_PVOE-Analysen/WichtigeZahlen2026.pdf, und
    https://www.tt.com/artikel/30926885/wieder-mehr-pflegegeldbezieher-wertanpassung-seit-1-jaenner, abgerufen am
    2026-11-05 über eine Websuche (Snippet, PDF nicht selbst geöffnet). Dasselbe Muster gilt vermutlich für ASVG § 293
    (Richtsätze); das ist nicht geprüft.
- Konfidenz: 90 % für (1), gemessen. 85 % für (2): Der Korpustext ist gemessen, der Betrag 2026 stammt aus zwei
  Sekundärquellen.
- Empfehlung:
  - (1) übernehmen. Beim Ingest `meta.aufgehoben = true`, wenn die Überschrift mit „<Gesetz> § <Nr> aufgehoben“
    beginnt. Volltext und dicht schließen solche Dokumente standardmäßig aus, außer die Frage zielt auf genau diesen
    §. Aufwand 30 min.
  - (2) übernehmen als Regel im Kern. Ein Euro-Betrag in der Antwort braucht ein Zitat aus einer Quelle mit Stand
    2026 (Serviceratgeber 2026, `veraendW` mit Jahr). Sonst nennt der Lotse keinen Betrag und verweist auf die
    Stelle. Aufwand 45 min einschließlich Nachprüfung (Regex auf `\d+,\d{2}\s?(€|Euro)` gegen die Quelle des Zitats).
- Nächster Check: Held-out-Frage „Wie viel Pflegegeld gibt es in Stufe 3?“. Die Antwort darf 451,80 € nicht nennen.
  Ob der Serviceratgeber 2026 die Beträge enthält, ist offen (`select … where a.text ~ 'Stufe 1'` über die
  Katalog-PDFs ergab 0 Zeilen, das Layout kann abweichen).

**D1c · Rangfunktion und Latenz.**
- Behauptung: Die Volltext-Konstruktion trägt: ODER-Anfrage, IDF, Themenfaktor, Präfix, Zerlegung, Längenabwertung,
  ein Abschnitt je §. Lange erweiterte Anfragen erzeugen aber Ausreißer bis 2 s und verletzen dann sowohl das AC
  „p95 < 300 ms“ als auch das Voice-Budget.
- Beleg: M4, `uv run python /tmp/b-uc1-review/kandidaten.py` und `kandidaten_llm.py` (k=50, 36 Anfragen).
  Originalfragen p50 ≈ 40 ms, Maximum 91 ms. Erweiterte Fragen p50 110 ms, Maximum 2.003 ms (d03 „… Ausgleichszulage
  Richtsatz“), dazu 1.946 ms und 1.277 ms (d03 und d04 mit LLM-Begriffen). Die Ursache ist nicht profiliert.
  Vermutlich sind es viele Präfix-Operanden (`:*`) mit dem `ts_rank` je Term im LATERAL über viele Kandidaten.
- Konfidenz: 90 % für die Messung, 60 % für die Ursache.
- Empfehlung: ausprobieren. Höchstens 8 Terme nach IDF; angehängte Begriffe ohne Präfix; `SET LOCAL
  statement_timeout = '400ms'` mit Rückfall auf die Originalfrage. Aufwand 30 min.
- Nächster Check: `lotse suche --messen` mit den 12 Dev-Fragen plus Begriffen; Ziel ist ein Maximum unter 300 ms.

### D2 · Dichte Suche (embeddinggemma-2, 256 d, Anfrage-Einbettung auf dem M4)
- Behauptung: Der Nutzen der dichten Suche ist für den Vollkorpus unbelegt. Der Prototyp (n=5, 200 Abschnitte) ist
  gesättigt: Volltext und hybrid stehen dort überall auf Rang 1. Die Wortlücke zwischen Bürger und Gesetz schließt die
  Anfrage-Erweiterung (Befund 1) bereits zu großen Teilen, und zwar ohne 3,4 GB RSS im Dienst.
- Beleg: `docs/plan/uc1/messung-embeddings.md` (n=5, „Die Aussagekraft ist gering“); M4 `select count(*) from
  lotse.vektor` → 0, hybrid also nicht messbar. Im HF-Cache von m5 liegen `onnx-community/embeddinggemma-2-ONNX` und
  `mlx-community/embeddinggemma-2-{4bit,8bit,bf16}`, also gäbe es Wege ohne torch. Ihre Gleichheit mit den
  Dokumentvektoren ist nicht geprüft.
- Konfidenz: 60 %, dass hybrid auf dem Dev-Set nicht klar über Volltext plus Erweiterung liegt (nicht gemessen; der
  Wert stützt sich auf die Sättigung und Befund 1).
- Empfehlung: Den Vollindex fertig bauen, aber `auto = hybrid` erst schalten, wenn ein gepaarter Vergleich auf dem
  Dev-Set hybrid mit Erweiterung ≥ Volltext mit Erweiterung zeigt (Verluste ≤ Gewinne, keine Latenz über 300 ms).
  Sonst bleibt dicht ein Schalter. Aufwand 30 min, sobald die Vektoren da sind.
- Nächster Check: gleicher Lauf wie im Testprotokoll mit `weg="hybrid"`, Rangliste je Fall neben `volltext`.

### D3 · Hybrid (RRF k=60, je 50)
- Behauptung: RRF mit k=60 ist ein vernünftiger, parameterarmer Standard (Cormack, Clarke, Büttcher, SIGIR 2009). Zu
  prüfen ist nur, ob beide Wege dieselben Filter tragen (Aufgehoben, Gesetz, PDFs).
- Beleg: Docstring `suche.py` („Filter … gelten wie beim Volltext“). Der dichte Code ist noch in Arbeit und nicht
  gelesen.
- Konfidenz: 70 %.
- Empfehlung: übernehmen. Den Aufgehoben- und den PDF-Fix (Befunde D1b und N2) im dichten Weg mitziehen. Aufwand im
  Fix von D1b enthalten.
- Nächster Check: ein Unit-Test mit „Gleitpension“, `weg="hybrid"`, ohne aufgehobenen § in den Top 5.

### D4 · Abschnitte (≤ 8 KB ganz, sonst nach `<absatz>`, Kontext mit Gewicht A)
- Behauptung: Die Einheit passt für Suche und Zitat. Absätze verweisen aber oft auf Nachbarn („nach Abs. 1“) oder
  auf andere §§; dann fehlt dem Modell der Zusammenhang. Abhilfe ist „klein suchen, groß lesen“: zitiert wird der
  Absatz, ins Modell gehen dazu die Überschrift und die Nachbarabsätze desselben §.
- Beleg: SQL über `lotse.abschnitt`. SozDok: 72.817 Abschnitte, Mittel 257 Zeichen, p95 1.393, 1.966 über 2.000
  Zeichen, Maximum 89.184 (Tabelle oder Anlage). BPGG § 21c zerfällt in 8 Abschnitte, ASVG § 293 in 23. Den Wert
  der Nachbarabsätze habe ich nicht gemessen.
- Konfidenz: 60 %, dass Nachbarabsätze die Belegquote in A2 spürbar heben.
- Empfehlung: ausprobieren im Kern. Dem Treffer `nr ± 1` und den Absatz 0 mitgeben und im Prompt kennzeichnen;
  explizite Verweise wie „§ 138 Abs. 1“ im selben Gesetz als Zusatzkontext auflösen. Aufwand 45 min, Verweisketten
  weitere 1–2 h.
- Nächster Check: A2-Belegquote mit und ohne Nachbarabsätze auf denselben 10 Antworten.

### D5 · Kern (#31)
**D5a · „Die KI formuliert, der Korpus belegt“ und Zitate als Teilstring.**
- Behauptung: Der Grundsatz ist richtig. Der Teilstring-Abgleich ist aber notwendig, nicht hinreichend: Ein wörtlich
  richtiges Zitat kann die Aussage trotzdem nicht tragen. Außerdem besteht `zitat_treu` schon mit einem einzigen
  Zeichen.
- Beleg:
  - `eval.py` `zitat_treu`: `return bool(kern) and kern in normiere(abschnitt_text)`, ohne Mindestlänge.
  - Magesh et al., „Hallucination-Free? Assessing the Reliability of Leading AI Legal Research Tools“, J. Empirical
    Legal Studies 2025, arXiv 2405.20362 (https://arxiv.org/abs/2405.20362, abgerufen am 2026-11-05 über eine
    Websuche): Kommerzielle juristische RAG-Werkzeuge mit Zitaten halluzinieren in 17–33 % der Antworten.
  - Anthropic, „Reduce hallucinations“
    (https://platform.claude.com/docs/en/test-and-evaluate/strengthen-guardrails/reduce-hallucinations, abgerufen am
    2026-11-05): wörtliche Zitate zuerst extrahieren, „for long documents (>20k tokens)“; dazu „find a supporting
    quote … If it can’t find a quote, it must retract the claim“.
- Konfidenz: 85 %.
- Empfehlung: übernehmen mit zwei Ergänzungen.
  - Strukturierte Ausgabe `{aussagen: [{text, abschnitt_id, zitat}]}`. Der Server prüft das Zitat gegen genau diesen
    Abschnitt und verlangt mindestens 6 Wörter oder 30 Zeichen. Den Sprech- bzw. Anzeigetext baut er erst aus den
    geprüften Aussagen.
  - Quote-first als eigener Schritt lohnt bei unseren kurzen Kontexten (5–10 Absätze, weit unter 20k Tokens) nicht
    eigens; das Schema erzwingt es schon.
  - Aufwand 30 min, im Kern ohnehin nötig.
- Nächster Check: ein Unit-Test, in dem das Zitat „die“ verworfen wird; A2 misst, ob die Aussage aus dem Zitat folgt.

**D5b · Grenzprüfung vor und nach (GOV.UK-Muster), Träger-Tabelle, Rückfragen.**
- Behauptung: Das Muster ist belegt. GOV.UK Chat nutzt einen JailbreakChecker auf der Frage und einen
  MultipleChecker auf der Antwort, und in den beiden Piloten gab es 508 Jailbreak-Versuche. Die Prüfung nach der
  Antwort kollidiert aber mit dem Streaming im Voice-Pfad (steht schon in der PRD).
- Beleg: https://docs.publishing.service.gov.uk/repos/govuk-chat/guardrails.html (laut Seite selbst „may be out of
  date“); https://insidegovuk.blog.gov.uk/2026/03/16/5-things-we-learned-testing-gov-uk-chat-an-ai-assistant-for-government
  (beide abgerufen am 2026-11-05 über eine Websuche, nur Snippets).
- Konfidenz: 75 %.
- Empfehlung: übernehmen. Die Rückfrage zum Status bzw. Pensionsträger soll zugleich den Gesetzesfilter setzen
  (Befund N2): Sie entscheidet dann den Träger und das Suchgebiet in einem Schritt. Aufwand: im Kern enthalten.
- Nächster Check: A4-Variante SVS-Pensionistin. Träger SVS, und die Treffer stammen aus GSVG/BPGG und PDFs, nicht
  aus ASVG.

**D5c · Voice-Ziel Median ≤ 2,0 s.**
- Behauptung: Mit der Anfrage-Erweiterung kommt vor der Suche ein zusätzlicher LLM-Aufruf dazu. Mit Suche (bis 2 s
  ohne Deckel), Antwort-LLM und Nachprüfung wird das Budget knapp.
- Beleg: Die Ausreißer aus D1c sind gemessen; der LLM-Aufruf ist auf diesem Weg nicht gemessen (Haiku über `claude -p`
  brauchte 24 s für alle 12 Fragen in einem Aufruf einschließlich CLI-Start; das ist kein Latenzwert).
- Konfidenz: 60 %.
- Empfehlung: Im Voice-Pfad den Thesaurus als Daten nutzen (ohne Latenz), im Textpfad das LLM. Aufwand 30 min.
  Dafür reicht ein Thesaurus mit rund 30 Einträgen für Pflege und Reha, z. B. Spital → Krankenanstalt, Rente →
  Versehrtenrente/Pension, dazuzahlen → Kostenbeteiligung, Zuschlag zur Pension → Ausgleichszulage, freistellen →
  Familienhospizkarenz.
- Nächster Check: die Antwortzeit-Uhr aus AC E über 10 Wechsel mit und ohne Erweiterung.

### D6 · Messung
- Behauptung: Die Messung ist methodisch sauber angelegt (eingefroren, Held-out, grep-Grundlinie, Verhalten aus dem
  Text). Die Stichproben sind aber zu klein für die Ziele, und zwei Bausteine erzeugen falsche Klassen.
- Beleg:
  - Intervalle (Wilson 95 %, `python3`, M4):
    - Volltext 5/15 = 15–58 %, grep 4/15 = 11–52 %; die beiden sind nicht unterscheidbar.
    - PRD-Ziele: 10/12 = 55–95 %, Held-out 8/10 = 49–94 %.
    - Grenzen 8/8 = 68–100 %: Eine Fehlerrate bis 31 % ist damit nicht ausgeschlossen.
  - Phrasenliste `uc1/eval/verhalten.yaml`, Abstinenz:
    - „in meinen quellen finde ich“ trifft auch „In meinen Quellen finde ich dazu Folgendes: …“, also eine positive
      Antwort.
    - „keine medizinische“ trifft jeden Standardhinweis „Ich gebe keine medizinische Beratung“.
    - „keinen beleg“ trifft „Sie brauchen keinen Beleg“.
    - Weil Abstinenz vor Antwort geprüft wird, wird jede solche Antwort zur Abstinenz.
  - `trifft` vergleicht „über alle Fassungen“; das ist wegen D1a ohne Wirkung.
- Konfidenz: 90 % (Rechnung und Code). Wie oft die Phrasen-Kollision eintritt, hängt vom Prompt ab; nicht gemessen.
- Empfehlung: übernehmen.
  - (a) Phrasen enger fassen: „in meinen quellen finde ich nichts“ / „keine“; „keine medizinische“ nur zusammen mit
    „diagnose|beurteil|empfehl“. Dazu 10 handbeschriftete Sätze als Test des Klassifizierers, darunter 3 mit
    Disclaimer.
  - (b) Der Kern gibt zusätzlich ein Verhaltensfeld aus; `lotse eval` meldet Abweichungen zwischen Text-Klasse und
    Feld als eigene Zahl, statt eines von beiden zu glauben.
  - (c) Gepaarte Vergleiche berichten (gewonnen : verloren je Fall, exakter McNemar), nicht nur zwei Quoten.
  - (d) Dev/Test-Vorgehen für die nächsten 15 h:
    - Abgestimmt wird nur auf dem Dev-Set (diese 12 Fragen, nach Bedarf erweitert, nie aus `lotse-set.yaml`).
    - Das Lotse-Set ist Test: höchstens 3 Läufe bis zur Abgabe, jeder Lauf mit Commit in `messung.md`
      („Blick n von 3“).
    - Held-out des Leads genau einmal am Ende.
  - Aufwand 45 min.
- Nächster Check: `pytest` mit den 10 Sätzen; `messung.md` zeigt die Intervalle neben jeder Quote.

### D7 · Reranker `BAAI/bge-reranker-v2-m3` (Kandidat aus Frage 2)
- Behauptung: Auf diesem Korpus und mit diesem Aufbau schadet der Reranker. Er zieht thematisch benachbarte, aber
  falsche Normen nach vorn: Formularseiten, Pensionsanpassung statt Ausgleichszulage, Betriebsrente statt
  Versehrtenrente, Abfindung statt Waisenpension.
- Beleg: m5, `rerank.py kandidaten.jsonl mps 512 50` (CrossEncoder, max_length 512, batch 8; Text = Kontext + Absatz;
  Anfrage = Bürgerfrage).

  | Variante | R@5 vorher → nachher | MRR@10 vorher → nachher | Recall@50 |
  |---|---|---|---:|
  | Original | 2/12 → 3/12 | 0,187 → 0,142 | 8/12 |
  | von Hand erweitert (Orakel) | 11/12 → 9/12 | 0,821 → 0,368 | 12/12 |
  | LLM-Begriffe (blind) | 9/12 → 7/12 | 0,669 → 0,257 | 12/12 |

  Beispiele: d01 (Pflegekarenzgeld) Rang 1 → 12, oben steht „PAL080 S. 7“ (Pflegegeld-Formular). d03 Rang 1 → 8/9,
  oben „ASVG § 728 Pensionsanpassung 2020“. d09 Rang 1 → 9, oben „BSVG § 149e Bemessung der Betriebsrente“.
  Gewinne: d04 (Selbstbehalt Selbständige) 45 → 3 (llm) bzw. 10 → 3 (erweitert), d05 6 → 3 (llm), d07 4 → 1
  (erweitert). Zugleich fällt d07 in der Variante llm von 5 auf 12.

  Kosten: 0,6 B Parameter, F32 (Modellkarte https://huggingface.co/BAAI/bge-reranker-v2-m3, abgerufen am
  2026-11-05). Gemessen auf m5 (MPS, belastet durch einen parallelen Indexlauf): p50 6,6 s, p95 10,0 s je 50 Paare,
  RSS 1,06 GB plus 3,27 GB MPS-Treiberspeicher.

  CPU-Gegenlauf auf m5 (`rerank.py … cpu 512 20`, 8 Threads, nur Top 20, ebenfalls belastet): p50 10,0 s, p95
  19,2 s je Frage, RSS 2,7 GB. Die Qualität bestätigt das Bild: erweitert R@5 11/12 → 10/12 (MRR 0,82 → 0,40), llm
  9/12 → 7/12 (MRR 0,67 → 0,35), original 2/12 → 3/12.

  Schätzung für die CPU des M4, nicht gemessen: 2 × 0,57 Mrd. Parameter × 512 Tokens ≈ 0,6 TFLOP je Paar, also
  ≈ 12 TFLOP für 20 Paare. Bei rund 1 TFLOP/s effektiv sind das etwa 10 s. Für Voice ist das unbrauchbar und im
  Textpfad zäh.

  Gegenposition aus der Praxis: Anthropic „Contextual Retrieval“ (2024-09-19,
  https://www.anthropic.com/news/contextual-retrieval, abgerufen am 2026-11-05) senkt die Fehlerrate bei Top-20 mit
  Reranking von 2,9 % auf 1,9 %. Dort lief der Cohere-Reranker über 150 Kandidaten, auf englischen Korpora.
- Konfidenz: 70 % für „hilft hier nicht“. Bei n=12 können einzelne Fälle kippen; die MRR-Halbierung in beiden
  Varianten ist aber deutlich. Mein Trefferkriterium zählt nur die Gesetzesnorm (bzw. Überschrift nach
  Regex), Satzungstreffer nur über die Regex; ein relevanter Serviceratgeber-Treffer zählt als Fehlschlag.
- Empfehlung: lassen. Allenfalls später prüfen: Rerank mit der erweiterten Anfrage statt der Bürgerfrage, ganzer §
  statt Absatz, oder nur als Gleichstandsbrecher unter den Top 10.
- Nächster Check: derselbe Lauf mit `anfrage` statt `frage` als Query (ein Feld in `rerank.py`).

### Nicht am Schirm

**N1 · Paralleles Recht verdrängt sich gegenseitig.** Dieselbe Leistung steht in ASVG, GSVG, BSVG, B-KUVG und den DO;
die Kopien belegen die Top 5.
- Beleg: d07 mit LLM-Begriffen liefert auf den Rängen 1–3 „ASVG § 257 / GSVG § 135 / BSVG § 126
  Hinterbliebenenpensionen“. Bei d03 stehen BSVG § 310, GSVG § 320 und ASVG § 636 (Pensionsanpassung) oben.
- Konfidenz: 85 %.
- Empfehlung: Gesetzesfilter aus der Status-Rückfrage (N2). Ohne Status je Gesetz nur den besten Treffer zulassen.
  Jetzt, 30 min.

**N2 · Der Gesetzesfilter entfernt alle PDFs (Code-Widerspruch zu AC B).**
- Beleg:
  - `suche.py` `_FILTER`: `cardinality(gesetze)=0 OR d.gesetz = ANY(gesetze)`. Für PDFs und EKO ist `gesetz` NULL,
    sie fallen also heraus.
  - Gemessen mit `/tmp/b-uc1-review/filter.py`: pdf=0 in allen 24 gefilterten Läufen.
  - Mit Filter (Status Arbeitnehmer bzw. Pension: ASVG, BPGG, FLAG, AlVG, KBGG; Selbständig: GSVG, BPGG) und
    LLM-Begriffen: Ränge 1, 1, 1, 3, 3, 1, 3, 1, 1, 1, 1, 2, also R@5 12/12 gegenüber 9/12 ohne Filter (gewonnen 3 :
    verloren 0, p = 0,25, nicht signifikant).
- Konfidenz: 90 % für den Bug, 65 % für den Gewinn.
- Empfehlung: jetzt, 20 min. Die Bedingung wird zu `… OR d.quelle <> 'sozdok'`, oder es gibt eigene Plätze für
  PDFs (z. B. 4 Gesetz + 2 Ratgeber).

**N3 · Qualitätsmodus `claude -p` kann am Demo-Tag ausfallen.**
- Beleg: M4, `claude -p --model haiku …` meldete am 2026-11-05: „Warning: this sign-in can end at any time from now
  until 2026-11-06. Renewing it does not move that date. … use claude setup-token for unattended jobs.“
- Konfidenz: 70 %, dass das Risiko real ist; ob es genau in die Demo fällt, ist nicht abzuschätzen.
- Empfehlung: In der Demo läuft Azure als Standard. Vorher `claude setup-token` durch den Owner, Konto-Aktion mit
  Freigabe. Jetzt, 10 min.

**N4 · KI-Kennzeichnung im Sprachpfad.**
- Beleg: Art. 50 Abs. 1 AI Act gilt seit 2026-08-02 und ist durch den Digital Omnibus nicht verschoben (Goodwin,
  2026-08,
  https://www.goodwinlaw.com/en/insights/publications/2026/08/alerts-technology-dpc-eu-ai-act-transparency-obligations-now-in-force,
  abgerufen am 2026-11-05 über eine Websuche, Sekundärquelle). Die PRD verlangt die Kennzeichnung nur sichtbar im UI.
- Konfidenz: 75 %.
- Empfehlung: Die erste Ansage des Vapi-Assistenten nennt „KI-Assistent“. Wer spricht, sieht das Badge nicht
  unbedingt. Jetzt, 10 min.

**N5 · Bürgersprache gegen Gesetzessprache ist der Hauptfehler, nicht das Ranking.**
- Beleg: Recall@50 im Original nur 8/12; bei 4 Fragen ist die Norm nicht einmal unter den 50 Kandidaten (d04, d06,
  d10, d12). Mit Begriffen steigt Recall@50 auf 12/12. Literatur: Statute Retrieval mit LLM-Konzeptinferenz
  (arXiv 2410.12154) übertrifft die besten COLIEE-2022/23-Systeme, ausdrücklich bei „real-life scenarios“ mit
  „vocabulary that is not specific to the legal domain“ (https://arxiv.org/html/2410.12154v1, abgerufen am
  2026-11-05 über eine Websuche, Zahlen selbstberichtet).
- Konfidenz: 85 %.
- Empfehlung: siehe Top 1.

**N6 · Offline-Betrieb.**
- Beleg: Ohne `HF_HUB_OFFLINE` fragt sentence-transformers beim Laden den Hub; im m5-Log mit gesetzter Variable steht
  „offline mode is enabled … Using cached commit hash“. Im Veranstaltungs-WLAN mit Captive Portal kann der Aufruf
  hängen (nicht gemessen).
- Konfidenz: 50 %.
- Empfehlung: `HF_HUB_OFFLINE=1` im Startskript des Dienstes setzen. Jetzt, 5 min.

**N7 · Injection aus Dokumenten.** Der Korpus besteht aus amtlichen Texten, das Risiko ist gering. Für den Upload
(Entlassungsbrief) ist es real, die PRD deckt es schon ab (Sätze als Daten markiert, Größenlimit). OWASP LLM01:2025.
Konfidenz 70 %. Empfehlung: lassen wie geplant.

## 3. Was gut ist und bleiben soll
- Suche, Zitierprüfung und Träger-Tabelle laufen ohne Modell und deterministisch. Das passt zum Grundsatz des Repos,
  und Fehler lassen sich so dem Modell oder der Suche zuordnen.
- `dokid` als Schlüssel, `text_hash` als Schlüssel der Vektoren: Ein neuer Ingest entwertet keine Vektoren.
- Die eigene Konfiguration `lotse_german` (unaccent als Wörterbuch) und die ODER-Anfrage mit IDF, Präfix und
  Zerlegung. Die Abwertung großer Sammeldokumente wirkt: Die BPGG-Entscheidungsübersichten stehen in keiner Dev-Top-3.
- Ein Abschnitt je § in den Top-k. Das gibt Vielfalt, auch wenn das Fassungsargument entfällt.
- Eingefrorenes Set vor dem Kern, Held-out beim Lead, Verhalten aus dem Text statt aus dem Selbst-Etikett,
  grep-Grundlinie neben jeder Zahl, p95 mitgemessen.
- Erst den Prototyp, dann skalieren; Deckel nach dem Vorfall (batch 8, 512 als Standard, Läufe nur auf m5).
- Rückfragen und Pflichtfelder als Daten, die Kill-Reihenfolge, Replay als Rückfall.

## 4. Testprotokoll

**Dev-Set (eigene Themen, nicht aus `lotse-set.yaml`, keine Paraphrasen davon).** Ein Treffer zählt, wenn
(Gesetz, Nummer) in den Normen liegt oder die Überschrift eines SozDok-Treffers die Regex erfüllt. So zählen
parallele Normen anderer Träger mit.

| id | Frage | erwartete Normen | Regex Überschrift |
|---|---|---|---|
| d01 | Ich möchte für ein paar Monate weniger arbeiten, um meinen Vater nach dem Schlaganfall zu pflegen. Bekomme ich in der Zeit Geld? | BPGG § 21c | Pflegekarenzgeld |
| d02 | Meine Mutter liegt seit drei Wochen im Spital. Bekommt sie das Pflegegeld weiter? | BPGG § 12 | – |
| d03 | Meine Pension ist so niedrig, dass ich kaum davon leben kann. Gibt es einen Zuschlag? | ASVG §§ 292, 293 | Ausgleichszulage\|Richtsätze |
| d04 | Ich bin selbständig. Muss ich beim Arzt etwas dazuzahlen? | GSVG § 86 | – |
| d05 | Ich brauche nach meiner Hüftoperation einen Rollstuhl. Zahlt das die Krankenkasse? | ASVG §§ 154, 137 | Heilbehelfe\|Hilfsmittel\|körperlichen Gebrechen |
| d06 | Meine Zahnprothese ist kaputt. Bekomme ich für eine neue etwas von der Kasse? | ASVG § 153 | Zahnersatz |
| d07 | Mein Mann ist gestorben. Bekomme ich jetzt eine Pension von ihm? | ASVG § 258 | Witwen |
| d08 | Mein Kind ist 17 und sein Vater ist gestorben. Bekommt es Geld und wie lange? | ASVG §§ 260, 252 | Waisen |
| d09 | Ich habe mich bei der Arbeit an der Hand verletzt und kann sie nicht mehr richtig bewegen. Bekomme ich eine Rente? | ASVG § 203 | Versehrtenrente |
| d10 | Ist meine Lebensgefährtin bei mir in der Krankenversicherung mitversichert? | ASVG § 123 | Anspruchsberechtigung für Angehörige |
| d11 | Ich pflege meinen Mann zu Hause und habe deshalb aufgehört zu arbeiten. Kann ich trotzdem Pensionszeiten sammeln? | ASVG §§ 18b, 18a | Selbstversicherung in der Pensionsversicherung für Zeiten der Pflege |
| d12 | Mein Kind ist todkrank und ich will mich von der Arbeit freistellen lassen, um bei ihm zu sein. Gibt es finanzielle Hilfe? | BPGG § 21c, FLAG § 38j | Familienhospizkarenz\|Pflegekarenzgeld |

Alle Normen sind per SQL im Korpus belegt (Überschriften wie „BPGG § 21c Pflegekarenzgeld“, „GSVG § 86
Kostenbeteiligung“).

**Varianten.**
- `original`: nur die Bürgerfrage.
- `erweitert`: Frage plus von mir geschriebene Fachbegriffe. Ich kannte die Zielnormen; die Variante ist deshalb
  eine Obergrenze (Orakel), kein fairer Test.
- `llm`: Frage plus Begriffe von Haiku (`claude -p --model haiku`, M4, 24 s für alle 12 Fragen). Der Prompt verlangt
  „3 bis 6 Fachbegriffe in der Sprache des Gesetzes … keine Paragraphennummern“ und nennt keine Zielnormen.
  Prompt: `/tmp/b-uc1-review/prompt-llm.txt`.

**Befehle.**
- M4 (aus `uc1/`, nur lesend):
  - `uv run python /tmp/b-uc1-review/kandidaten.py` und `… kandidaten_llm.py` holen je Variante Volltext Top 50
    über `uc1.suche.suche(q, k=50, weg="volltext")`.
  - `… filter.py` läuft mit `SuchFilter(gesetze=…)`.
- m5:
  - `scp` der Datei `kandidaten.jsonl` (36 Zeilen) nach `~/scratch/b-uc1-review/`.
  - `nohup sh run.sh` mit `rerank.py` (CrossEncoder, HF offline, `nice -n 5`, ein Prozess, batch 8).

**Rohzahlen Volltext (Rang der ersten erwarteten Norm in Top 50; – = nicht unter 50).**

| id | original | erweitert | llm | original + Filter | llm + Filter |
|---|---:|---:|---:|---:|---:|
| d01 | 26 | 1 | 1 | 15 | 1 |
| d02 | 10 | 1 | 1 | 6 | 1 |
| d03 | 39 | 1 | 1 | 13 | 1 |
| d04 | – | 10 | 45 | – | 3 |
| d05 | 23 | 1 | 6 | – | 3 |
| d06 | – | 1 | 1 | – | 1 |
| d07 | 1 | 4 | 5 | 1 | 3 |
| d08 | 20 | 1 | 1 | 29 | 1 |
| d09 | 7 | 1 | 1 | 5 | 1 |
| d10 | – | 2 | 6 | 26 | 1 |
| d11 | 1 | 1 | 1 | 1 | 1 |
| d12 | – | 1 | 2 | 16 | 2 |
| **R@5** | **2/12** (5–45 %) | **11/12** (65–99 %) | **9/12** (47–91 %) | **3/12** | **12/12** (76–100 %) |

Klammern: Wilson-95-%-Intervall. Gepaart `original` → `llm`: 7 gewonnen, 0 verloren, exakter McNemar p = 0,016.
`llm` → `llm + Filter`: 3 : 0, p = 0,25. Latenz Volltext k=50: original p50 ≈ 40 ms; mit Begriffen p50 110 ms,
Maximum 2.003 ms. Aufgehobene §§ in den Top 5 vor dem Rerank: d02 1, d03 1, d06 1, d11 3, d12 1 (original).

**Rohzahlen Reranker** siehe D7 (MPS, 512 Tokens, Top 50).

**Grenzen der Aussage.**
- n=12, ein Prüfer hat Fragen und Normen festgelegt; ein zweiter Prüfer der Erwartungen fehlt.
- Die Fragen sind kurz und haben eine klare Norm. Mehrteilige Lebenslagen wie im Pflege-Szenario sind nicht
  abgedeckt.
- Haiku ist nicht das Produktionsmodell (gpt-5-4-mini).
- Der Filter wurde von mir gesetzt, nicht aus einer echten Rückfrage abgeleitet.
- Die Reranker-Latenz stammt von einem belasteten m5.

## 5. Nicht geprüft
- Dichte und hybride Suche auf dem Vollkorpus (`lotse.vektor` = 0 zum Zeitpunkt der Messung).
- Reranker mit erweiterter Anfrage als Query, mit `max_length` 1024 oder mit ganzem § statt Absatz. Den Lauf mit
  1024 habe ich um 13:59 selbst beendet: Er hätte den Entscheid nicht geändert und konkurrierte auf m5 mit dem
  Indexlauf um MPS.
- Reranker-Latenz auf der CPU des M4 (auf dem M4 bewusst nicht geladen; nur geschätzt, siehe D7).
- Reranker-Latenz auf einem unbelasteten m5: Beide Läufe teilten MPS bzw. die CPU mit dem parallelen Indexlauf.
- Anfrage-Erweiterung mit gpt-5-4-mini über `plattform.llm` und deren Latenz je Anfrage.
- Ob BPGG § 4 (ikra 2015) und die übrigen Fassungen dem heutigen RIS-Stand entsprechen. Der Korpus ist ein
  Schnappschuss; ich habe nur BPGG § 5 gegen eine externe Quelle gehalten.
- Ob der Serviceratgeber 2026 die Pflegegeldbeträge 2026 enthält.
- Herkunft der PRD-Zahl „14 Tupel auf 51 Dateien“.
- Quote-first gegen die einfache Schema-Ausgabe, Grenzprüfung, Voice-Latenz, Verweisketten: nicht gemessen.
- Phrasen-Kollisionen an echten Kern-Antworten (es gibt noch keinen Kern).
- Das eingefrorene `lotse-set.yaml` und die Held-out-Fragen habe ich nicht für Messungen benutzt; gelesen habe ich nur
  die Fragezeilen, um Themen-Überschneidungen zu vermeiden.
