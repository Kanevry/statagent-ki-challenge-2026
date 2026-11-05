# Messung Dev-Set: Volltext gegen hybrid, Erweiterung aus / Thesaurus / LLM (#29, #30)

Stand 2026-11-05. Dev-Set `uc1/eval/dev-set.yaml` (d01–d12 aus `review-architektur.md` § 4). Das Test-Set
`lotse-set.yaml` wurde hier NICHT benutzt (Zähler damals `uc1/eval/testset-blicke.json`, heute `docs/plan/uc1/testset-blicke.json` unverändert bei Blick 1).

## Ergebnis und Empfehlung

| Variante (Rechner B) | Recall@5 | Wilson 95 % | MRR@10 | p50 ms | p95 ms |
|---|---|---|---|---|---|
| volltext + aus | 2/12 | 5–45 % | 0,188 | 44 | 132 |
| volltext + thesaurus | 10/12 | 55–95 % | 0,683 | 64 | 102 |
| volltext + llm | 9/12 | 47–91 % | 0,554 | 89 | 123 |
| hybrid (256 d) + aus | 3/12 | 9–53 % | 0,196 | 78 | 108 |
| hybrid (256 d) + thesaurus | 8/12 | 39–86 % | 0,543 | 96 | 131 |
| hybrid (256 d) + llm | 8/12 | 39–86 % | 0,453 | 114 | 148 |

Gepaart (B gegen A, Treffer in Top 5, exakter McNemar):
- hybrid gegen volltext: aus 1 : 0 (p = 1,0), thesaurus 0 : 2 (p = 0,50), llm 1 : 2 (p = 1,0).
- Erweiterung gegen aus: volltext llm 7 : 0 (p = 0,016), volltext thesaurus 8 : 0 (p = 0,008); hybrid llm 5 : 0
  (p = 0,063), hybrid thesaurus 6 : 1 (p = 0,125).

**Empfehlung `weg="auto"` = volltext.** Hybrid schlägt den Volltext auf diesem Set in keiner Variante; mit
Erweiterung verliert er knapp (insgesamt 2 : 4 über die drei Paare), ohne Erweiterung gewinnt er einen Fall. Kein
Unterschied ist signifikant (n=12), ein Vorteil von hybrid ist damit aber auch nicht belegt. Hybrid kostet zusätzlich
das Modell im Speicher, etwa 30 ms je Anfrage und einen Ladevorgang beim Start. Die Entscheidung trifft der
Koordinator; er hat so entschieden: `auto` ist im Code volltext (`weg_fuer` in `uc1/uc1/suche.py`).

**Empfehlung Erweiterung:** Textpfad `llm` (blind erzeugt: 9/12, 47–91 %, 7 : 0 gegen aus, p = 0,016), mit dem
Thesaurus als Rückfall, wie `erweitere()` ihn schon hat. Sprachpfad `thesaurus` (deterministisch, keine Latenz).
Vorbehalt: Das Thesaurus-Ergebnis 10/12 ist auf diesem Set eine **Obergrenze**, kein fairer Test. Laut Kopf von
`uc1/daten/thesaurus.yaml` stammen seine Themen aus genau diesem Dev-Set (z. B. Muster „kaum davon leben“ aus
d03). Für den Sprachpfad braucht es eine Prüfung auf Fragen, die der Thesaurus nicht kannte (Held-out).

## Rahmen und Grenzen
- Treffer: (Gesetz, Art, Nummer) unter den erwarteten Normen oder Überschrift eines SozDok-Treffers erfüllt
  `ueberschrift_regex`. Gesucht werden 10 Treffer (MRR@10), Recall zählt die ersten 5.
- Aufgehobene §§ sind ausgeschlossen (Standard `mit_aufgehobenen=False`), Gesetzesfilter keiner.
- Höchstens 12 Suchterme je Anfrage (`suche.MAX_TERME`).
- LLM-Begriffe: einmal auf Rechner A über `plattform.llm` (Azure, Zweck `uc1.lotse`, Prompt
  `erweiterung.ERWEITERUNG_PROMPT`), 12 Aufrufe, alle 12 mit Quelle `llm` (kein Rückfall). Gemessen wird nur die
  Suche. Die LLM-Latenz ist nicht enthalten.
- Latenz: ein ungezählter Aufwärmlauf je Variante, dann je Frage ein Lauf. p95 bei n=12 ist der Höchstwert.
- Vor der Messung lief der pg_trgm-Rückfall bei d02 ohne Erweiterung (2.522 ms auf Rechner B, 1.234 ms auf
  Rechner A). Die 80 Kandidaten-Abschnitte lagen in weniger als 10 Paragraphen. Behoben in
  `suche.volltext`, das in diesem Fall erst mehr Volltext-Kandidaten holt (`NACHLADE_FAKTOR`). Die Ränge sind
  davor und danach gleich.
- n=12, ein Prüfer hat Fragen und Normen festgelegt; kurze Fragen mit klarer Norm.

## Befehle

Rechner A, aus `uc1/`. `werkzeuge/messen.py` ruft `uc1.eval.cli` mit denselben Argumenten wie `lotse eval`:

```
uv run python werkzeuge/messen.py --set eval/dev-set.yaml --erweiterung llm --nur-begriffe laufzeit/begriffe-llm.json
uv run python werkzeuge/messen.py --nur-suche --set eval/dev-set.yaml --weg volltext \
  --erweiterung aus,thesaurus,datei:laufzeit/begriffe-llm.json --ausgabe laufzeit/dev-m4-volltext.md
bash werkzeuge/rechner-b.sh repo-packen          # Stand HEAD plus nicht committete Dateien
scp laufzeit/repo.tar werkzeuge/rechner-b.sh laufzeit/begriffe-llm.json <rechner B>:<arbeitsordner B>/
```

Rechner B (Apple Silicon), Arbeitsordner ohne Checkout, `ARBEITSORDNER_B` gesetzt, PG 18 mit voll eingelesenem Korpus und 61.309 Vektoren je Dimension:

```
bash rechner-b.sh repo-entpacken                 # repo/, uv sync --package uc1 --extra embed
bash rechner-b.sh ingest                         # setzt meta.aufgehoben
bash rechner-b.sh messen --nur-suche --set eval/dev-set.yaml --weg volltext,hybrid \
  --erweiterung aus,thesaurus,datei:<arbeitsordner B>/begriffe-llm.json --ausgabe <arbeitsordner B>/log/dev-b.md
```

`messen` setzt `EMBED_DEVICE=mps`, `HF_HUB_OFFLINE=1` und die URL der eigenen DB. Ein Prozess, Anfrage-Einbettung
batch 1.

## Ingest (beide Rechner)
- 1.141 Dokumente mit `meta.aufgehoben = true` (Überschrift beginnt mit „aufgehoben“: 1.046; dazu Stummel wie
  „§ 206. Aufgehoben.“ oder „Artikel 11 Aufgehoben. (2.ZV …)“ ohne Kennzeichen in der Überschrift).
- `inhalt_hash` unverändert `676e80d8f295e5ce3298ffca040693bda4bc2dc152ae9ef59f7473eb9c2cdfdd`: Der Hash läuft über
  (dokid, nr, text_hash) und enthält `meta` nicht, das Flag geht also nicht ein. Die Vektoren hängen an
  `text_hash` und bleiben gültig.

## Rechner A, nur Volltext

- Zeitpunkt: 2026-11-05T14:47:38+01:00

| Weg | Recall@k | Wilson 95 % | MRR@10 | k | Latenz p50 (ms) | Latenz p95 (ms) |
|---|---|---|---|---|---|---|
| volltext+aus | 2/12 | 5 %–45 % | 0.188 | 5 | 48.3 | 150.5 |
| volltext+thesaurus | 10/12 | 55 %–95 % | 0.683 | 5 | 68.1 | 100.7 |
| volltext+llm | 9/12 | 47 %–91 % | 0.554 | 5 | 97.8 | 126.1 |

Die Ränge sind gleich wie auf Rechner B, die Volltext-Suche ist rechnerübergreifend deterministisch.

## Rechner B, Rohbericht

- Zeitpunkt: 2026-11-05T14:48:02+01:00
- Befehl: `lotse eval --nur-suche --set eval/dev-set.yaml --weg volltext,hybrid --erweiterung aus,thesaurus,datei:<arbeitsordner B>/begriffe-llm.json --ausgabe <arbeitsordner B>/log/dev-b.md`
- Zählende Fälle (mit Korpusquelle, n=12): d01, d02, d03, d04, d05, d06, d07, d08, d09, d10, d11, d12
- Intervall: Wilson 95 %. MRR über die ersten 10 Treffer (Rang darüber zählt 0).

| Weg | Recall@k | Wilson 95 % | MRR@10 | k | Latenz p50 (ms) | Latenz p95 (ms) |
|---|---|---|---|---|---|---|
| volltext+aus | 2/12 | 5 %–45 % | 0.188 | 5 | 43.9 | 131.6 |
| volltext+thesaurus | 10/12 | 55 %–95 % | 0.683 | 5 | 64.3 | 102.4 |
| volltext+llm | 9/12 | 47 %–91 % | 0.554 | 5 | 89.1 | 123.0 |
| hybrid+aus | 3/12 | 9 %–53 % | 0.196 | 5 | 77.9 | 107.9 |
| hybrid+thesaurus | 8/12 | 39 %–86 % | 0.543 | 5 | 95.8 | 130.6 |
| hybrid+llm | 8/12 | 39 %–86 % | 0.453 | 5 | 113.8 | 148.2 |

Gepaarte Vergleiche (B gegen A, je Fall Treffer in Top k): gewonnen = B trifft, A nicht.

| B | gegen A | gewonnen : verloren | gleich | McNemar exakt p |
|---|---|---|---|---|
| volltext+thesaurus | volltext+aus | 8 : 0 | 4 | 0.008 |
| volltext+llm | volltext+aus | 7 : 0 | 5 | 0.016 |
| hybrid+aus | volltext+aus | 1 : 0 | 11 | 1.000 |
| hybrid+thesaurus | volltext+thesaurus | 0 : 2 | 10 | 0.500 |
| hybrid+llm | volltext+llm | 1 : 2 | 9 | 1.000 |
| hybrid+thesaurus | hybrid+aus | 6 : 1 | 5 | 0.125 |
| hybrid+llm | hybrid+aus | 5 : 0 | 7 | 0.062 |

| Fall | erwartete Quellen | Rang volltext+aus | ms volltext+aus | Rang volltext+thesaurus | ms volltext+thesaurus | Rang volltext+llm | ms volltext+llm | Rang hybrid+aus | ms hybrid+aus | Rang hybrid+thesaurus | ms hybrid+thesaurus | Rang hybrid+llm | ms hybrid+llm |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| d01 | BPGG § 21c | – | 81.8 | 2 | 89.4 | 2 | 103.8 | – | 107.9 | 6 | 117.5 | 8 | 148.2 |
| d02 | BPGG § 12 | 9 | 131.6 | – | 102.4 | 9 | 107.5 | – | 99.8 | – | 130.6 | – | 127.6 |
| d03 | ASVG § 292; ASVG § 293 | – | 46.2 | 1 | 93.5 | 1 | 111.9 | 10 | 69.3 | 1 | 120.4 | 4 | 140.0 |
| d04 | GSVG § 86 | – | 43.1 | – | 77.7 | – | 110.8 | – | 79.1 | – | 109.2 | – | 146.3 |
| d05 | ASVG § 154; ASVG § 137 | – | 30.6 | 1 | 42.6 | 1 | 58.4 | – | 63.1 | 1 | 71.2 | 1 | 84.5 |
| d06 | ASVG § 153 | – | 50.7 | 1 | 60.9 | – | 88.8 | 4 | 80.8 | 1 | 85.5 | 2 | 114.4 |
| d07 | ASVG § 258 | 1 | 21.3 | 5 | 39.5 | 5 | 39.8 | 1 | 46.9 | 10 | 61.7 | 5 | 63.2 |
| d08 | ASVG § 260; ASVG § 252 | – | 42.3 | 1 | 50.1 | 3 | 95.3 | – | 72.1 | 1 | 76.7 | 1 | 113.8 |
| d09 | ASVG § 203 | 7 | 43.9 | 1 | 51.5 | 2 | 89.1 | – | 77.9 | 2 | 92.8 | 9 | 105.7 |
| d10 | ASVG § 123 | – | 29.8 | 1 | 79.3 | 1 | 77.0 | – | 62.3 | 4 | 120.4 | 4 | 87.1 |
| d11 | ASVG § 18b; ASVG § 18a | 1 | 63.7 | 1 | 64.3 | 1 | 123.0 | 1 | 99.3 | 1 | 95.8 | 1 | 145.4 |
| d12 | BPGG § 21c; FLAG § 38j | – | 64.7 | 2 | 68.1 | 1 | 79.0 | – | 101.0 | 2 | 104.0 | 1 | 106.0 |

Begriffe der Erweiterung thesaurus:

- d01: Pflegekarenz, Pflegekarenzgeld
- d02: Krankenanstalt, Anstaltspflege
- d03: Ausgleichszulage, Richtsatz
- d04: Kostenbeteiligung, Ärztliche Hilfe
- d05: Hilfsmittel, körperlichen Gebrechen
- d06: Zahnersatz, Zahnbehandlung
- d07: Witwenpension, Hinterbliebenenpension
- d08: Waisenpension
- d09: Versehrtenrente
- d10: Anspruchsberechtigung für Angehörige
- d11: Selbstversicherung, Zeiten der Pflege
- d12: Familienhospizkarenz, Pflegekarenzgeld

Begriffe der Erweiterung llm:

- d01: Pflegekarenzgeld, Pflegekarenz, Pflegekarenzvereinbarung, nahe Angehörige, pflegebedürftige Person
- d02: Anstaltspflege, Krankenhausaufenthalt, Pflegegeld Ruhen, Unterbringung im Spital, Anspruchsfortbestand
- d03: Ausgleichszulage, Pensionshöhe, Mindestpension, Bedarfsgemeinschaft, Richtsatz
- d04: Selbstversicherung, Kostenbeteiligung, Kassenarzt, Wahlarzt, Behandlungsbeitrag
- d05: Heilbehelfe, Hilfsmittel, Körperersatzstücke, Sachleistungen, Wiederherstellung der Gesundheit
- d06: Kostenzuschuss, Sachleistung, Heilbehelf, zahnärztliche Versorgung
- d07: Witwenpension, Witwerpension, Hinterbliebenenpension, Witwenversorgung, Witwerversorgung
- d08: Waisenpension, Halbwaise, Vollwaise, Anspruchsdauer, Waisenrente
- d09: Versehrtenrente, Arbeitsunfall, Minderung der Erwerbsfähigkeit, Unfallversicherung, Heilbehandlung
- d10: Mitversicherung, Lebensgefährte, Angehörige, Anspruchsberechtigung
- d11: Pflege naher Angehöriger, Ersatzzeiten, Versicherungszeiten, Kindererziehungszeiten, Pflegekarenz
- d12: Pflegefreistellung, Begleitung eines Kindes, Sterbebegleitung, Familienhospizkarenz, Pflegekarenzgeld
