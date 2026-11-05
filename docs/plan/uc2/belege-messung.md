# UC2 Belege: Messbericht Pressespiegel-Index und Suche (#40)

Stand 05.11.2026, Bau-Session b-uc2. Owner-Vorgabe 12:5x: „bzgl embeddings nutze bitte google/embeddinggemma-2 …
teste immer in nem kleinen prototypen annahmen und dann skalier alles hoch“. Lead 13:24: Extraktion, Embedding und
Indexbau nur auf dem m5, das Ergebnis kommt per `pg_dump` auf den M4 (PG 5433).

Korpus, Zwischenstände, Vektoren und Dump liegen nie im Repo. Arbeitsordner: m5 `~/Projects/_scratch/kic-uc2/`,
M4 `~/Projects/ki-challenge-2026/arbeit/uc2/`.

## 1. Prototyp 1: Modell (m5, erfundene Texte)

| Messung | Wert |
|---|---|
| Modell | `google/embeddinggemma-2`, Revision `f9972ac22e696a105c482202646979e33e4b5a1e`, Apache-2.0, nicht gated |
| Versionen | torch 2.15.0, transformers 5.22.1, sentence-transformers 6.2.0, Python 3.12 |
| Laden (MPS, float32, nur Textteil) | 1,6 s; Dimension 768 |
| Durchsatz MPS, batch 32, ca. 850 Zeichen | 97,5 Texte/s, keine NaN |
| Wiederholung MPS | max. Abweichung 0,0 |
| CPU gegen MPS, 20 Texte | Kosinus min 1,000 |
| Abfrage auf CPU | 25 ms je Frage |

Befund: Der Prozessor lädt auch im Nur-Text-Betrieb die Bild- und Video-Prozessoren und bricht ohne `Pillow` und
`torchvision` ab. Das Extra `einbettung` in `uc2/pyproject.toml` enthält beide.

## 2. Prototyp 2: ein Monat echt (09/2026, m5)

| Stufe | Ergebnis |
|---|---|
| Übertragung M4 → m5 (m5-remote) | 192 MB in 199 s, ca. 1 MB/s |
| `uc2 extrahiere` | 22 Ausgaben in 1,4 s; 352 Einträge im Inhaltsverzeichnis → 351 Artikel (1 Text-Dublette), 966 Abschnitte |
| `uc2 einbetten` | 966 Abschnitte in 21,6 s (44,7/s, Abschnitte bis 1.500 Zeichen) |
| `uc2 index` | M4 und m5: gleicher Inhalts-Hash |

## 3. Vollbestand 2026 (m5)

| Stufe | Ergebnis |
|---|---|
| Dateien | 187 PDF, 1 byte-gleiche Dublette (`Pressespiegel vom 03.08.2026.pdf` in Juli und August) übersprungen → **186 Quellen** |
| Inhaltsverzeichnis / Artikel / Abschnitte | 2.925 / 2.909 / 7.800 |
| Extraktion / Embedding | 6,2 s / 400 s (MPS) |
| Index zweimal geladen | identischer Inhalts-Hash, also idempotent |
| Dump `healthpolicy`, Schema `uc2` | `pg_dump -Fc` aus dem PG-16-Container, 32 MB; Restore auf dem M4 in 1 s; Inhalts-Hash M4 = m5 (Stand v1; ausgeliefert ist v3, § 3a) |

Abweichungen im Indexer-Protokoll: 231 Radio- und TV-Beiträge nur mit Titel, 16 Artikel- und 4 Abschnitts-Dubletten
entfernt, 1 Titel abweichend.

**Unabhängiges Prüfskript** `uc2/tests/pruefe_index.py`: eigener Inhaltsverzeichnis-Parser, eigenes md5, kein Import
von Laufzeit-Code. Lauf über alle 187 PDF auf dem m5:

- md5: 186 auf der Platte = 186 in PG.
- Keine Zeile `Autor:in` gespeichert.
- 0 doppelte Text-Hashes.
- 7.800 Vektoren mit 768 Dimensionen.

Befunde aus diesem Lauf:

1. **Hash hängt an der Collation:** Der Inhalts-Hash hing an der DB-Collation (M4 `de_AT.UTF-8`, m5 `en_US.utf8`), behoben mit `collate "C"`.
2. **Sprecherzeilen bei Radio/TV:** Umbrochene Sprecherzeilen wurden nur halb verworfen. Dadurch blieben Namensreste im Text (19 Beiträge), und verschiedene Sendungen galten als Dubletten (3 Beiträge vom 17.02.2026). Behoben in zwei Schritten (§ 3a).
3. **Autor:innen im Fließtext:** 165 der 395 Autor:in-Namen stehen im Fließtext (622 Abschnitte, Bylines und Erwähnungen). Für #40 ist das nur ein Hinweis; die Maskierung ist Aufgabe von #43 (Personenschutz).

## 3a. Nachläufe nach den Fixes (m5)

| Lauf | Änderung | Artikel / Abschnitte | Prüfskript über 187 PDF |
|---|---|---|---|
| v1 | erster Volllauf | 2.909 / 7.800 | 14 „fehlt in PG“ (davon 8 Dubletten-Regel des Skripts zu eng, 6 Schein-Dubletten bei Radio/TV) |
| v2 | Sprechereintrag über Zeilen verworfen, Dubletten-Hash für reine Titel aus Titel, Medium und Datum | 2.915 / 7.806 | **alle Prüfungen bestanden, 0 Abweichungen**; Radio/TV: 240 nur Titel, 23 mit Transkript, 2 mit Namensrest |
| v3 | Radio/TV nur noch Transkriptzeilen; Institutions-Aliase ohne Themenwörter (#41, Review-Bank) | 2.915 / 7.806 (gleiche Abschnitts-IDs wie v2) | **alle Prüfungen bestanden, 0 Abweichungen**; Radio/TV: 242 nur Titel, 23 mit Transkript, **0 Namensreste**; 4.168 Abschnitte mit Institutions-Tag |

v3 ist der ausgelieferte Stand:
- Index zweimal geladen, Inhalts-Hash beide Male `e79db68f…`.
- Dump `healthpolicy-uc2-v3.dump`: 31,7 MB, sha256 `424e70f9…`, liegt auf dem m5 und auf dem M4 unter `~/Projects/ki-challenge-2026/arbeit/uc2/dump/`.
- Auf dem M4 eingespielt, gleicher Inhalts-Hash.
- Extraktion 22 s, Embedding 14 min auf dem m5 unter Last.

**Stichprobe (Akzeptanz #40):** Ein Gutachter mit frischem Kontext hat 10 zufällige Artikel (Seed 20261105, v2) gegen ihre PDF-Seiten
geprüft: Start, Titel, Medium, Datum, Vollständigkeit über Seitenwechsel, keine Kopf- oder Fußzeilen, kein Feldblock, keine
Layout-Kopie, keine Sprecherzeilen. Ergebnis **10/10 ok**. Grenzfälle für #43: eine Dachzeile vor dem Titel bleibt im Text, und ein
Interviewer-Name steht im Fließtext.

**Betrieb:** Ohne `HF_HUB_OFFLINE=1` fragt sentence-transformers bei jedem Laden den Hub nach Dateien ab. Für den Demo-Betrieb
ohne Netz `HF_HUB_OFFLINE=1` setzen; das Modell liegt im Cache.

## 4. Suchgüte (Vollbestand, 10 Fragen, k = 8)

Methode:
- 10 Fragen zur Gesundheitspolitik, natürlich formuliert. Stichtag 2026-09-30, Halbwertszeit 120 Tage.
- Drei Modi mit demselben Einbetter.
- Die Treffer aller Modi bilden einen Pool aus 142 Paaren (Frage, Artikel).
- Ein Gutachter-Agent mit frischem Kontext bewertet den Pool **blind**, also ohne Wissen, welcher Modus ein Paar geliefert hat. Noten: 2 relevant, 1 teilweise, 0 nicht relevant.
- Ergebnis der Bewertung: 64 × 2, 43 × 1, 35 × 0.

| Verfahren | P@8 (≥ 1) | P@8 (= 2) | nDCG@8 |
|---|---|---|---|
| Volltext UND (`websearch_to_tsquery`), Prototyp 09/2026 | 6 von 10 Fragen ohne Treffer | – | – |
| Volltext ODER (gestemmte Lexeme) | 0,825 | 0,600 | 0,772 |
| Vektor (embeddinggemma-2) | 0,700 | 0,388 | 0,605 |
| Hybrid 0,7·cos + 0,3·ts | 0,738 | 0,425 | 0,618 |
| RRF (k = 60), Gewicht Volltext 0,6 / Vektor 0,4, offline auf denselben Urteilen | 0,850 | 0,600 | 0,804 |
| **RRF wie oben, eingebaut (`fusion: rrf`), Index v2** | **0,950** | **0,725** | **0,880** |
| RRF eingebaut, untere Schranke (19 neue Paare als 0 gezählt) | 0,713 | 0,575 | 0,781 |

Zur eingebauten RRF: Sie bringt 19 Paare in die Top 8, die im ersten Pool nicht vorkamen. Diese hat ein zweiter Gutachter mit
frischem Kontext blind bewertet (12 × 2, 7 × 1, 0 × 0). Er hat keine einzige 0 vergeben; mögliche Milde ist nicht auszuschließen,
deshalb steht die untere Schranke daneben. nDCG@8 ist für alle Zeilen mit eingebauter RRF über den vergrößerten Pool (161
Urteile) normiert; für Volltext ergibt sich dort 0,737 und für Vektor 0,582.

Befunde:
- **UND ist für Fragen unbrauchbar.** Der Volltext mit UND findet zu natürlich formulierten Fragen meist nichts. ODER über die gestemmten Lexeme ist der Standard (`suche.volltext_verknuepfung` in `regeln.yaml`).
- **Die Annahme „Vektor schlägt Volltext“ hält für diesen Korpus nicht.** Die Vektorsuche zieht thematisch verwandte, aber falsche Artikel an: bei „Pflege“ pflegende Angehörige und Heimkosten, bei „Finanzierung“ Landesbudgets. Ihre Stärke sind Umschreibungen, etwa bei der Augenarzt-Frage ohne das Wort „Wartezeit“.
- **Die Summe roher Werte ist praktisch reiner Vektor.** Der Kosinus liegt eng um 0,8, `ts_rank_cd` bei 0,0x; die Skalen passen nicht zusammen.
- **Eine skalenfreie Fusion der Ränge (RRF) ist auf allen drei Maßen am besten**, offline wie eingebaut. Sie hebt Artikel, die beide
  Verfahren finden, und holt aus den Kandidatenlisten beider Verfahren Treffer, die keine Einzelliste unter den ersten 8 hatte.

Grenzen der Messung:
- 10 Fragen und ein Gutachter.
- RRF ist offline auf den Top-8-Listen genähert; Ränge über 8 gelten als nicht gelistet.

Die Gewichte sind deshalb Startwerte in `regeln.yaml` und werden mit den Fällen aus #43/#44 nachgemessen.

## 5. Entscheide (autonom entschieden, Steuerung: autonomous)

| # | Entscheid | Grund | Verworfen |
|---|---|---|---|
| M1 | Volltext mit ODER-Verknüpfung als Standard | UND: 6/10 Fragen ohne Treffer | UND, `websearch_to_tsquery` |
| M2 | Hybrid als RRF (k = 60, Gewicht Volltext 0,6) statt Summe roher Werte | höchste P@8 und nDCG@8; skalenfrei | 0,7·cos + 0,3·ts (Skalen unvergleichbar), reiner Vektor |
| M3 | Index nur auf dem m5 bauen, Dump auf den M4 | Lead 13:24, M4 überlastet; Demo darf nicht vom Tunnel abhängen | Index auf dem M4, PG über den Tunnel |
| M4 | Abfrage-Embedding zur Laufzeit lokal (CPU) | Lead 13:3x: klein, erlaubt; 25 ms je Frage | Abfragen über den m5 |
| M5 | Autor:in-Namen im Fließtext als Eingabe für #43 | Akzeptanz #40 verlangt „keine Zeile Autor:in“; Namen maskiert #43 | Autor:innen schon in #40 maskieren (doppelte Maskierungslogik) |
