# Messung Embeddings `google/embeddinggemma-2` (Issue #29, Prototyp vor dem Hochskalieren)

Owner-Vorgabe: „teste immer in nem kleinen prototypen annahmen und dann skalier alles hoch“. Der Prototyp prüft
an 200 Abschnitten Qualität und Kosten, bevor der ganze Korpus eingebettet wird.

## Aufbau

| Punkt | Wert |
|---|---|
| Modell | `google/embeddinggemma-2`, HF-Snapshot `f9972ac22e696a105c482202646979e33e4b5a1e`, nur der Textteil (271,0 M Parameter) |
| Bibliotheken | torch 2.15.0, transformers 5.22.1, sentence-transformers 6.2.0, Python 3.12 (uv-venv) |
| M4 | Apple M4 Pro, 12 Kerne, 24 GB, macOS 27.0.1. Hier läuft die Demo offline. |
| m5 | Apple M5 Max, 18 Kerne, 128 GB, Arbeitsordner `~/scratch/b-uc1/` (kein Checkout) |
| Code | `uc1/prototyp/embedding_200.py`, Adapter `uc1/uc1/einbettung.py`, Basis-Commit `cd28a5a` |
| Auswahl | `uc1/prototyp/auswahl-200.json`, Seed 42 |
| Zeitstempel | M4 Auswahl und Vorlauf 2026-11-05 13:08 bis 13:20 CET, m5 Vergleich 13:30:45, m5 Messung 13:31:41 bis 13:33:16, M4 Anfrage-Latenz 13:33:42 |

Befehle (aus `uc1/`, `UC1_DATA_DIR` zeigt auf `svbox/uc1`, `HF_HUB_OFFLINE=1`):

```bash
uv run python prototyp/embedding_200.py auswahl          # M4: 200 Abschnitte, nur XML
uv run python prototyp/embedding_200.py zaehlung         # M4: Abschnitte im ganzen Korpus
uv run python prototyp/embedding_200.py volltext         # M4: nur PG (Schema lotse_proto), kein Modell
# m5:
EMBED_DEVICE=mps uv run python prototyp/embedding_200.py vergleich \
  --jsonl ~/scratch/b-uc1/absaetze-200.jsonl --volltext ~/scratch/b-uc1/volltext.json
EMBED_MAX_TOKENS=2048 …vergleich…                         # gleicher Lauf mit 2048 Tokens
EMBED_DTYPE=bfloat16 EMBED_MAX_TOKENS=2048 …vergleich…    # Qualitätsprobe bfloat16
uv run python prototyp/embedding_200.py messung --jsonl ~/scratch/b-uc1/absaetze-200.jsonl \
  --plan mps,mps,cpu,mps:bfloat16                        # je Lauf ein frischer Prozess
# M4, nur Anfrage-Latenz:
EMBED_DEVICE=cpu nice -n 10 uv run python prototyp/embedding_200.py einzel --nur-anfrage
```

**Auswahl.** Die 200 Abschnitte setzen sich so zusammen: 25 Abschnitte aus den 5 erwarteten Quellen (BPGG § 4 und
ASVG § 162 bzw. § 175 sind größer als 8 KB und zerfallen in 7, 8 und 8 Absätze; ASVG § 136 und § 139 sind
ganze Dateien), 60 harte Nachbarn (andere §§ aus BPGG und ASVG, je ein Abschnitt) und 115 Zufallsabschnitte aus
dem übrigen Korpus ohne Inhaltsverzeichnisse. Ein Abschnitt hat im Mittel 839 Zeichen, der längste 3.982.

**Verfahren.** Volltext: ODER-Anfrage aus den Lexemen von `to_tsvector('public.lotse_german', frage)`,
sortiert nach `ts_rank_cd`, über `titel || text`. Dicht: Cosinus mit den Präfixen der Modellkarte. Hybrid:
RRF mit k=60 aus Volltext und dicht. Ein Treffer zählt, wenn der Abschnitt aus dem erwarteten Gesetz und
der erwarteten §-Nummer stammt.

**Fix am Adapter.** Das Repo bringt einen multimodalen `EmbeddingGemma2Processor` mit, und der verlangt Pillow
und torchvision. `einbettung.py` lädt deshalb für den Textpfad nur den Tokenizer. Es lädt zuerst aus dem Cache
(`local_files_only`) und nur bei Fehlen aus dem Netz. Der Parameter `torch_dtype` ist veraltet und heißt jetzt
`dtype`.

## Vorfall und Deckel (wichtig)

Der erste Vorlauf auf dem M4 lief mit 8192 Tokens Deckel und batch 32 auf MPS. Er belegte 14 GB
MPS-Treiberspeicher, auf CPU 11 GB RSS. Ein Diagnoselauf mit batch 64 kam dann auf 28 GB Footprint und brachte
den M4 ins Swappen. Der Koordinator hat ihn beendet. Daraus folgt:

- Der Adapter deckelt jetzt auf **512 Tokens** (`EMBED_MAX_TOKENS` überschreibt das, höchstens 8192). Der
  Standard von `embed` ist jetzt **batch 8**; die Signatur ist gleich geblieben, das hat der Koordinator so
  entschieden.
- Auf dem M4 laufen keine Dokument-Einbettungen mehr, dort wird nur die Latenz einzelner Anfragen auf der CPU
  gemessen. Die Vorlauf-Zahlen des M4 für MPS und CPU stehen unten nur zum Vergleich; sie gelten für die alte
  Konfiguration.

## Ergebnis Qualität (m5, n = 5 Fragen auf 200 Abschnitten)

| Verfahren | Recall@5 (512 Tok.) | MRR@10 (512 Tok.) | Recall@5 (2048 Tok.) | MRR@10 (2048 Tok.) |
|---|---:|---:|---:|---:|
| Volltext | 1,00 | 1,000 | 1,00 | 1,000 |
| dicht 768 | 0,80 | 0,700 | 1,00 | 0,767 |
| hybrid 768 | 1,00 | 0,840 | 1,00 | 1,000 |
| dicht 256 | 0,80 | 0,700 | 1,00 | 0,800 |
| hybrid 256 | 1,00 | 0,850 | 1,00 | 1,000 |

bfloat16 bei 2048 Tokens liefert dieselben Ränge wie float32. Der Vorlauf mit 8192 Tokens auf dem M4 ergab
dieselben Ränge wie 2048 (kein Abschnitt hat mehr als 2048 Tokens).

Rang der erwarteten Quelle je Frage:

| Frage | Quelle | Volltext | dicht 768 (512 / 2048) | hybrid 768 (512 / 2048) | dicht 256 (512 / 2048) | hybrid 256 (512 / 2048) |
|---|---|---:|---:|---:|---:|---:|
| F7 Pflegestufe 75 h | BPGG § 4 | 1 | 1 / 1 | 1 / 1 | 1 / 1 | 1 / 1 |
| F2 Krankengeld Dauer | ASVG § 139 | 1 | 2 / 2 | 1 / 1 | 2 / 2 | 1 / 1 |
| F5 Wochengeld | ASVG § 162 | 1 | 1 / 1 | 1 / 1 | 1 / 1 | 1 / 1 |
| F21 Wegunfall | ASVG § 175 | 1 | 1 / 1 | 1 / 1 | 1 / 1 | 1 / 1 |
| F6 Rezeptgebühr | ASVG § 136 | 1 | **31** / 3 | 5 / 1 | **24** / 2 | 4 / 1 |

Wie die Zahlen zu lesen sind:

- **Der 512-Deckel kostet Qualität.** 28 der 200 Abschnitte (14 %) sind länger als 512 Tokens. ASVG § 136 ist
  eine ganze Datei mit 3.347 Zeichen, und die Rezeptgebühr steht erst im hinteren Teil, den der Deckel
  abschneidet. Deshalb fällt F6 dicht auf Rang 31. Der Deckel ist eine Speicherbremse für den M4, für den Index
  taugt er nicht.
- Dicht allein verliert gegen Volltext. F2 landet hinter ASVG § 162 (Wochengeld), F6 hinter
  Schlussbestimmungen. Hybrid holt bei 2048 Tokens beide Fälle zurück.
- 256 Dimensionen sind hier so gut wie 768 (MRR 0,800 gegen 0,767; das ist Rauschen bei n = 5).
- **Die Aussagekraft ist gering.** Es sind nur 5 Fragen, alle mit eindeutigen Fachwörtern (Krankengeld,
  Wochengeld, Rezeptgebühr), in denen Volltext stark ist. Die Quellen stellen 25 von 200 Abschnitten. Der Test
  ist gesättigt: Volltext und hybrid erreichen überall Rang 1 und unterscheiden sich nicht. Ob dicht bei
  Alltagssprache ohne Fachwort hilft („Heimweg gestürzt“ statt „Wegunfall“), zeigt erst der volle Korpus mit
  mehr Golden-Fragen. F7 fragt auch „wohin schicke ich den Antrag“; das steht in BPGG § 25, gewertet wurde nur
  § 4.

## Ressourcen

m5, 200 Abschnitte (182.986 Zeichen mit Präfix), batch 8, je Lauf ein frischer Prozess:

| Lauf | Deckel | Laden kalt / warm | Durchsatz | Zeichen/s | Anfrage p50 / p95 | RSS max | MPS-Treiber |
|---|---:|---:|---:|---:|---:|---:|---:|
| mps float32, 1. Prozess | 512 | 2,32 s / 0,79 s | 42,0 Texte/s | 38.467 | 20,5 / 23,7 ms | 2.379 MB | 2.581 MB |
| mps float32, 2. Prozess | 512 | 2,28 s / 0,75 s | 46,4 Texte/s | 42.485 | 21,0 / 24,2 ms | 2.368 MB | 2.581 MB |
| cpu float32 | 512 | 2,12 s / 0,68 s | 12,3 Texte/s | 11.257 | 24,9 / 28,3 ms | 3.589 MB | – |
| mps bfloat16 | 512 | 2,29 s / 0,74 s | 90,0 Texte/s | 82.352 | 19,9 / 22,1 ms | 1.363 MB | 2.677 MB |
| mps float32 | 2048 | 2,30 s / 0,72 s | 31,6 Texte/s | 28.907 | 20,2 / 23,4 ms | 2.364 MB | 6.055 MB |

M4, nur Anfrage-Einbettung (cpu, float32, batch 1, 20 Anfragen, `nice -n 10`, 13:33:42):

| Laden kalt / warm | Anfrage p50 / p95 | RSS max |
|---:|---:|---:|
| 3,82 s / 0,78 s | 27,2 / 30,3 ms | 3.375 MB |

Begriffe: „kalt“ ist das erste Laden in einem frischen Prozess, einschließlich Import von sentence-transformers.
Die Gewichte lagen dabei wahrscheinlich schon im Seiten-Cache des Systems; ein echter Kaltstart nach dem
Booten wurde nicht gemessen (dafür bräuchte es `sudo purge`). Der einmalige Download (1,49 GB) dauerte rund
60 s. „Warm“ heißt neu laden im selben Prozess. RSS kommt aus `ru_maxrss`; MPS-Speicher zählt dort nicht mit
und steht deshalb in einer eigenen Spalte (`torch.mps.driver_allocated_memory`). p95 aus 20 Werten ist
interpoliert und deshalb nur grob.

Vorlauf auf dem M4, **alte Konfiguration** (8192 Tokens, batch 32), nur zum Vergleich: mps 8,9 bzw. 6,6
Texte/s mit 14 GB MPS-Treiber, cpu 5,4 Texte/s mit 11,2 GB RSS, mps bfloat16 7,7 Texte/s. Die
Anfrage-Latenz auf mps lag bei p50 24–49 ms und p95 71–408 ms mit Ausreißern, auf cpu bei 37 / 77 ms. Diese
Konfiguration ist verworfen.

## Hochrechnung Vollindex (m5)

Basis: 72.817 SozDok-Abschnitte und 2.883 Abschnitte aus PDF und EKO, gezählt in der DB `lotse` des M4
(Koordinator), zusammen **75.700**. Die eigene XML-Zählung mit der Einheit dieses Prototyps kommt auf 72.782
nicht leere Abschnitte (14.244 Dateien: 13.359 bis 8 KB, 885 größer mit 68.866 `<absatz>`-Elementen; die
grobe Schätzung „1 + Anzahl absatz“ ergibt 82.225). Im Korpus hat ein Abschnitt im Mittel nur rund 350
Zeichen, in der Stichprobe 915. Die Hochrechnung über Texte/s ist deshalb pessimistisch, die über Zeichen/s
näher an der Wirklichkeit. Für PDF und EKO ist dieselbe mittlere Länge angenommen (rund 26,2 Mio. Zeichen
gesamt).

| Konfiguration auf m5 | über Texte/s | über Zeichen/s |
|---|---:|---:|
| mps float32, 2048 Tokens | 75.700 / 31,6 ≈ 40 min | 26,2 M / 28.907 ≈ 15 min |
| mps float32, 512 Tokens | ≈ 27 min | ≈ 10 min |
| mps bfloat16, 512 Tokens | ≈ 14 min | ≈ 5 min |

bfloat16 mit 2048 Tokens wurde nur auf Qualität geprüft (gleiche Ränge), nicht auf Durchsatz. Zu erwarten
ist ein Wert zwischen den Zeilen 1 und 3. Speicher in `lotse.vektor`: 75.700 × 768 × 4 B ≈ 233 MB Nutzdaten
(256 Dimensionen: ≈ 78 MB), beides passt für den numpy-Cosinus in den RAM des M4.

## Empfehlung

1. **Hochskalieren: ja.** Den Index auf m5 bauen, nicht auf dem M4. Er dauert dort zwischen einer
   Viertelstunde und 40 Minuten und braucht rund 8,5 GB (6 GB MPS plus 2,4 GB RSS bei 2048 Tokens). Auf dem M4 wird zur Laufzeit nur die Anfrage
   eingebettet: 27 / 30 ms p50 / p95 auf der CPU bei 3,4 GB RSS. Dafür genügt die CPU; MPS bringt bei einer
   einzelnen Anfrage nichts und hatte im Vorlauf Ausreißer.
2. **Deckel für Dokumente auf 2048 Tokens** (`EMBED_MAX_TOKENS=2048` für den Indexlauf auf m5), nicht 512.
   Der 512-Deckel hat F6 messbar verschlechtert. Für Anfragen reicht 512. Besser als Kürzen ist, lange
   Abschnitte über 512 Tokens beim Ingest weiter zu teilen. Das wäre eine Änderung der Einheit und gehört zu
   #29/Ingest, nicht zum Adapter.
3. **Dimension 256.** In dieser Stichprobe kein Verlust gegenüber 768, dazu ein Drittel des Speichers und
   der Rechenzeit für den Cosinus. Die Modellkarte nennt 256 „nahezu verlustfrei“. Beim Vollindex 768
   mitspeichern (`dim` ist Teil des Schlüssels) und mit mehr Golden-Fragen nachmessen.
4. **Hybrid statt nur dicht.** Dicht allein verliert hier gegen Volltext (MRR 0,77–0,80 gegen 1,00), hybrid
   ist nie schlechter als Volltext. Die Frage ist, ob hybrid besser ist als Volltext allein. Bei n = 5 und
   fachwortlastigen Fragen ist das nicht messbar und muss auf dem Vollindex mit Fragen in Alltagssprache
   geprüft werden.
5. **dtype:** float32 bleibt Standard. bfloat16 lieferte auf m5 doppelt so viel Durchsatz bei gleichen
   Rängen und ist für den Indexlauf eine Option (`EMBED_DTYPE=bfloat16`). Anfragen und Dokumente sollten
   dabei mit demselben dtype eingebettet werden; das ist nicht gemessen und eine offene Frage.

## Vollindex

Gebaut am 2026-11-05 auf m5, importiert in die DB des M4 und in eine eigene DB-Kopie auf m5. Code
`uc1/uc1/vektoren.py` (Aufruf `uv run python -m uc1.vektoren …`), Hilfsskripte `uc1/werkzeuge/m5.sh` und
`uc1/werkzeuge/tar_nfc.py`. Einstellungen laut Koordinator: `EMBED_MAX_TOKENS=2048`, float32, mps, batch 8,
Eingabe `als_dokument(kontext, text)`. Gespeichert werden 768 Dimensionen, 256 entstehen beim Import aus den
ersten 256 Werten mit anschließender L2-Normierung.

| Punkt | Wert |
|---|---|
| Abschnitte mit Text | 75.700 |
| eindeutige `text_hash` (eingebettet) | 61.309 (14.391 Abschnitte sind Duplikate, meist gleiche Fassungen) |
| Zeichen der Eingaben | 26.073.554 |
| Laufzeit m5 | 39 min Wandzeit (13:41:47 bis 14:20:51), davon 1.602 s für 59.904 Texte und 718 s für die letzten 1.405 |
| Texte/s | 26,4 über den ganzen Lauf; die längsten Texte (2048-Token-Deckel) zuletzt mit rund 2 Texten/s |
| Spitzen-Speicher m5 | RSS 2,6 GB. MPS-Treiber bis 60 GB im ersten Lauf, mit `torch.mps.empty_cache()` je Teilstück 2,5 GB |
| Dateien | `gemma2.768.npy` 188,3 MB, `gemma2.hashes.txt` 4,0 MB, `abschnitte.jsonl` 32,5 MB, Archiv `vektoren.tgz` 177 MB |
| Prüfsummen (sha256) | `gemma2.768.npy` `468eaad7…f802`, `gemma2.hashes.txt` `4602c797…b56e`, `abschnitte.jsonl` `312c6e14…dbe1` |
| Import M4 | 6,3 s, 615 MB RSS, mit `nice -n 10` (beide Dimensionen) |
| Normen | alle 61.309 Vektoren mit L2-Norm 1,0, keine NaN |

**Abbruch und Wiederaufnahme.** Gerechnet wird in Teilstücken zu 512 Texten, sortiert nach (Länge, Hash),
damit ein Batch ähnlich lange Texte enthält. Ohne Leeren des MPS-Caches wuchs der Treiberspeicher mit den
langen Texten auf 60 GB. Der Lauf wurde nach Teilstück 116 (59.904 Texte) über seine PID beendet, und
`vektoren.py` leert den Cache seitdem nach jedem Teilstück. Der neue Lauf übernahm die 117 fertigen
Teilstücke und rechnete nur die letzten 1.405 Texte. Die langsamen letzten Teilstücke (300 s je 512 Texte)
fielen in eine Zeit, in der m5 eine Last von 14 hatte. Ob das Leeren des Caches selbst Zeit kostet, ist
nicht gemessen.

**Status M4** (`postgresql://…@localhost:5433/lotse`, 14:27:08) und **m5** (Port 5434, 14:27:35), gleiche
Ausgabe; auf m5 nach zwei Importen hintereinander, also ohne Verdopplung:

```json
{"abschnitte": 75700, "eindeutige_hashes": 61309, "vektoren": [
  {"modell": "google/embeddinggemma-2", "dim": 256, "zeilen": 61309, "mit_abschnitt": 61309},
  {"modell": "google/embeddinggemma-2", "dim": 768, "zeilen": 61309, "mit_abschnitt": 61309}]}
```

**Hash-Vergleich M4/m5 (Determinismus über zwei Rechner).** `lotse ingest` auf m5 (PG 18.6, Python 3.12.13,
pdftotext 26.10.0 wie auf dem M4) ergab `inhalt_hash 676e80d8f295e5ce3298ffca040693bda4bc2dc152ae9ef59f7473eb9c2cdfdd`,
gleich dem M4, mit denselben Zählungen (14.244 SozDok-Dokumente, 72.817 + 31 + 253 + 2.599 Abschnitte,
0 Ingest-Fehler). Der Export aus der m5-DB hat dieselbe Prüfsumme `312c6e14…` wie der Export des M4.

Der erste Versuch ergab `6dfd230c…`. Ursache: Der Korpus war mit bsdtar gepackt, und auf m5 lagen die drei
Dateinamen mit Umlaut („ÖGK …“, „Zahnärzte …“) danach in NFD statt NFC vor. Weil `dokid` bei PDFs der
Dateipfad ist, wichen 194 Zeilen ab, alle Text-Hashes waren gleich. `werkzeuge/tar_nfc.py` packt und entpackt
deshalb mit Pythons tarfile, das die Namen als Bytes übernimmt, und lässt AppleDouble-Dateien (`._*`) weg.
Folgerung für die Abgabe: Der Inhalts-Hash hängt an der Unicode-Form der Dateinamen. Wer den Korpus kopiert,
muss die Namen in NFC erhalten.

**DB-Kopie auf m5.** Eigene Instanz PG 18.6 in `~/scratch/b-uc1/pg`, Port 5434, nur localhost, Rolle und
Passwort `statistik` (scram), DB `lotse`. Start, Stopp und Status: `bash ~/scratch/b-uc1/m5.sh pg-start`,
`pg-stop` und `pg-status`. Für die Messung auf m5: `LOTSE_DATABASE_URL=postgresql://statistik:statistik@localhost:5434/lotse`.

Befehle:

```bash
# M4 (aus uc1/)
nice -n 10 uv run python -m uc1.vektoren export --ausgabe laufzeit/vollindex/abschnitte.jsonl
nice -n 10 python3 -I werkzeuge/tar_nfc.py packen "$UC1_DATA_DIR" laufzeit/transfer/svbox-uc1.tgz
scp werkzeuge/m5.sh werkzeuge/tar_nfc.py laufzeit/transfer/*.tgz m5-remote:scratch/b-uc1/
# m5
bash ~/scratch/b-uc1/m5.sh entpacken      # Code und Export
bash ~/scratch/b-uc1/m5.sh berechnen      # nohup, Log log/berechnen.log
bash ~/scratch/b-uc1/m5.sh korpus         # Korpus als NFC
bash ~/scratch/b-uc1/m5.sh pg-init        # initdb, Start, createdb lotse
bash ~/scratch/b-uc1/m5.sh ingest         # db-init und ingest gegen Port 5434
bash ~/scratch/b-uc1/m5.sh packen         # vektoren.tgz
bash ~/scratch/b-uc1/m5.sh import         # Import und status auf m5
# M4
scp m5-remote:scratch/b-uc1/vektoren.tgz laufzeit/transfer/
nice -n 10 uv run python -m uc1.vektoren import --prefix laufzeit/vollindex/gemma2 --dims 768,256
nice -n 10 uv run python -m uc1.vektoren status
```

Offen: Der Volltext-Vergleich dicht/hybrid auf dem Vollindex (`lotse eval`) ist noch nicht gelaufen. Ein
Lauf mit bfloat16 würde den Index etwa halb so lange rechnen lassen; dafür müssten Anfragen mit demselben
dtype eingebettet werden (siehe Empfehlung 5).
