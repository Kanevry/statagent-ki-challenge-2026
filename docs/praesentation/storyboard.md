# Storyboard: Fachjury-Präsentation StatAgent

Stand 05.11.2026. Gehört zu Epic #26 und #89. Diese Datei ordnet jede Folie einer Datei, einem Pen-Frame und einem Screenshot zu.
Sie beschreibt auch das Folienformat für die Präsentations-Runtime (#59) und den Rückfall ohne Runtime.

Ablauf: 10 Minuten Vortrag mit Demo, Ziel 9:40, damit 20 Sekunden Puffer bleiben. Danach Live-Änderung und Datenanfragen der Jury.
Sprechtext: `skript-fachjury.md`. Demo: `demo-drehbuch.md`. Fragen: `fragenkatalog.md`. Zahlen: `belegregister.md`.

## Folien

| Nr | Datei in `web/content/slides/` | Zeit | Titel | Layout | Pen-Frame (P01–P11) | Bild | Bewertungsbereiche |
|---|---|---|---|---|---|---|---|
| 1 | `01-cover.md` | 0:00–0:30 | StatAgent | cover | `wsmDT` | kein Bild | alle |
| 2 | `02-problem.md` | 0:30–1:15 | Eine falsche Zahl kostet Vertrauen | aussage | `hVSIB` | SC1 | Datenmanagement, Qualitätssicherung |
| 3 | `03-drei-schritte.md` | 1:15–2:00 | Einlesen, rechnen, freigeben | schritte | `uw3eY` | SC2 | Datenmanagement, Weiterentwicklung und Betrieb |
| 4 | `04-stack.md` | 2:00–2:45 | Was wo läuft | diagramm | `QpM2f` | SC3 | Weiterentwicklung und Betrieb, Bedienbarkeit |
| 5 | `05-beleg.md` | 2:45–3:15 | 2.880 von 2.880 | zahl | `uzmdd` | SC4, SC5 | Qualitätssicherung, Reporting |
| 6 | `06-datenfehler.md` | 3:15–4:15 | Acht Datenfehler, nichts gelöscht | tafel | `Zzdmf` | SC6, SC7 | Datenmanagement, Qualitätssicherung |
| 7 | `07-annahme.md` | 4:15–5:00 | Geburtsmonat 13 | annahme | `Z1sWFu` | SC8, SC9 | Qualitätssicherung, Klassifikation |
| 8 | `08-live.md` | 5:00–8:30 | Jetzt live | live (`/uc3`) | `Q1wWT` | SC12 | Reporting, Weiterentwicklung und Betrieb, Bedienbarkeit |
| 9 | `09-grenzen.md` | 8:30–9:00 | Was wir nicht anfassen | grenzen | `TUmCv` | SC10 | Datenmanagement, Qualitätssicherung |
| 10 | `10-einstieg.md` | 9:00–9:25 | Ein Kern, ein Einstieg | einstieg | `vJ2qx` | SC11 | Weiterentwicklung und Betrieb, Bedienbarkeit |
| 11 | `11-schluss.md` | 9:25–9:40 | Jede Zahl nachrechenbar | schluss | `qwTm6` | kein Bild | alle |

Folie 8 enthält die Demo von 5:15 bis 8:30. Die Überleitung dauert 15 Sekunden.

Die Pen-Frames liegen in `design/ki-challenge.pen` im Bereich x 0–7920, y 4400–7880 (Reihen zu vier Folien, je 1920 × 1080). Die Bildflächen tragen bis zur Aufnahme den Hinweis „folgt“.

Pflichtinhalte der Aufgabenstellung und wo sie stehen: Lösung (Folien 1, 3, 4), gefundene Fehler (Folie 6), eine Annahme im Detail (Folie 7), Live-Änderung und Datenanfrage (Folie 8, Demo).

## Folienformat für die Runtime (#59)

Eine Markdown-Datei je Folie. Der Dateiname beginnt mit der zweistelligen Nummer, die Reihenfolge ergibt sich daraus.

Frontmatter (YAML):

| Feld | Pflicht | Inhalt |
|---|---|---|
| `nummer` | ja | Position im Deck, 1 bis 11 |
| `titel` | ja | Titel der Folie, auch für die Folienleiste |
| `layout` | ja | eines von `cover`, `aussage`, `schritte`, `diagramm`, `zahl`, `tafel`, `annahme`, `live`, `grenzen`, `einstieg`, `schluss` |
| `route` | bei `live` | App-Route, die in der Folie eingebettet wird, z. B. `/uc3` |
| `zeit` | ja | Zeitmarke im Vortrag, z. B. `"2:45–3:15"` |
| `dauer_s` | ja | Soll-Dauer in Sekunden, Summe 580 |
| `bereiche` | ja | Bewertungsbereiche, die die Folie belegt |
| `screenshot` | nein | Kennung des Bildes (`SC1` bis `SC12`) oder `null`; Datei `docs/praesentation/screens/SC01.png` usw. |
| `pen_frame` | nein | ID des Pen-Frames in `design/ki-challenge.pen` |
| `belege` | ja | Kennungen der Zahlen im Belegregister, z. B. `[F1, F2]` |

Körper: Die erste Überschrift `#` ist der sichtbare Titel. Alles bis zur Überschrift `## Sprechernotizen` ist Folieninhalt. Was danach steht, sind die Notizen; die Runtime zeigt sie mit der Taste N.

Die Zeile, die mit `Herkunft:` beginnt, ist die sichtbare Quellenangabe der Folie. Die Runtime setzt sie klein an den unteren Rand.

## Rückfall ohne Runtime

Läuft die Runtime #59 am Freitag nicht, gilt diese Reihenfolge:

1. Die Pen-Frames P01 bis P11 als PDF (Export 1920 × 1080) im Vollbild zeigen. Die Notizen stehen im Skript.
2. Die Markdown-Dateien sind ohne Runtime lesbar. Sie dienen als Sprechzettel.
3. Die Demo läuft unabhängig davon in einem eigenen Fenster (`demo-drehbuch.md`).

Der PDF-Export liegt nicht im Repo, sondern lokal unter `docs/praesentation/export/` (über `.gitignore` ausgeschlossen).

## Screenshots SC1 bis SC12

Abnahme der Bilder über #88. Ablage `docs/praesentation/screens/SC01.png` bis `SC12.png`, mindestens 1920 Pixel breit. Das Manifest `screens-manifest.md` nennt je Bild Route, Commit, Lauf und ob es live, aus Testdaten oder eine Aufzeichnung ist.

| Bild | Motiv | Quelle | Folie |
|---|---|---|---|
| SC1 | Läufe-Übersicht, 24 Monate mit Status | UC3-Oberfläche (#18) | 2 |
| SC2 | Eine Regel mit Gültigkeit, Begründung, Freigabe | UC3-Oberfläche (#18) oder `uc3 regeln zeigen` | 3 |
| SC3 | Terminal `uc3 lauf --lieferung 2024-08` | Terminal-Aufnahme eines echten Laufs | 4 |
| SC4 | Zellvergleich 2.880 von 2.880 | Terminal `uc3 eichen --lieferung 2024-08` | 5 |
| SC5 | Aggregations-Sheet Tab1 | `abgabe/aggregationen_v1.xlsx` | 5 |
| SC6 | Qualitätsbericht 2025-03 mit Einstufungen | UC3-Oberfläche oder `abgabe/qualitaetsberichte/2025-03.md` | 6 |
| SC7 | Qualitätsbericht 2025-10, Lauf angehalten | UC3-Oberfläche oder `abgabe/qualitaetsberichte/2025-10.md` | 6 |
| SC8 | Regel `R5_alter` als Daten | UC3-Oberfläche oder `uc3 regeln zeigen` | 7 |
| SC9 | Rückfrage R1 an die Fachabteilung | `abgabe/rueckfragen/R1.md` | 7 |
| SC10 | Protokoll mit Freigabe, Name, Zeit, Wirkung | UC3-Oberfläche oder `uc3 protokoll --zeigen` | 9 |
| SC11 | Gemeinsamer Einstieg (UC4) mit dem Wechsel der Use Cases im App-Kopf | öffentliche Demo, Route `/uc4` | 10 |
| SC12 | Agent-Vorschlag mit Diff vor der Freigabe | `uc3 vorschlag zeigen <id>` oder Oberfläche | 8 |

Ein Bild aus Testdaten oder eine Aufzeichnung wird im Manifest so gekennzeichnet. Es wird nie als Live-Lauf ausgegeben.

## Gemeinsamer Einstieg (UC4, #95)

Folie 10 zeigt den gemeinsamen Einstieg als nächsten Schritt: Eine Frage läuft durch UC3, UC2 und UC1. Jeder Use Case antwortet in derselben Form `antwort(frage, kontext)` mit Text, Belegen, Zahlen, Use Case, Modell und Protokoll-Eintrag.
In der Demo kommt der Einstieg nur vor, wenn `/uc4` bis zum Freeze Fr 07:00 grün ist (optional D4 im Drehbuch). Sonst bleibt es bei Folie 10.
