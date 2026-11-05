# Storyboard: Fachjury-Präsentation StatAgent

Stand 05.11.2026, Szenen v2. Gehört zu Epic #26, #89 und #59. Diese Datei ordnet jede Szene einer Datei, einem Bild und den Bewertungsbereichen zu.
Sie beschreibt auch das Format der Präsentations-Runtime (#59) und den Rückfall ohne Runtime.

Ablauf: 10 Minuten Vortrag mit Demo, Ziel 9:30, damit 30 Sekunden Puffer bleiben. Danach Live-Änderung und Datenanfragen der Jury.
Sprechtext: `skript-fachjury.md`. Demo: `demo-drehbuch.md`. Fragen: `fragenkatalog.md`. Zahlen: `belegregister.md`.

Eine „Szene“ ist eine Seite der Präsentation. Die Dateien liegen unter `web/content/slides/`, die Reihenfolge ergibt sich aus dem Dateinamen.

## Dramaturgie

Der Einstieg zeigt die falsche Zahl: Im Oktober 2025 kamen 313.154 statt 390.900 Beschäftigungsverhältnisse (F11), und StatAgent hat angehalten. Der Beweis folgt in Szene 3 bis 8: die Lösung in drei Schritten, 2.880 von 2.880 Zellen (F1), die Fallen in den Daten, eine Annahme im Detail und die Demo. Zum Schluss stehen die Grenzen: Veröffentlichtes bleibt, ein Kern trägt mehrere Use Cases, jede Zahl ist nachrechenbar.

## Szenen

| Nr | Datei in `web/content/slides/` | Zeit | Titel | Layout | Szene | Pen-Frame | Bild | Bewertungsbereiche |
|---|---|---|---|---|---|---|---|---|
| 1 | `01-titel.md` | 0:00–0:20 | StatAgent | titel | `titel` | folgt | kein Bild | alle |
| 2 | `02-falsche-zahl.md` | 0:20–1:20 | Eine falsche Zahl | text | `falsche-zahl` | folgt | SC1 | Datenmanagement, Qualitätssicherung |
| 3 | `03-drei-schritte.md` | 1:20–2:10 | Einlesen, rechnen, freigeben | schritte | `drei-schritte` | folgt | SC2 | Datenmanagement, Weiterentwicklung und Betrieb |
| 4 | `04-stack.md` | 2:10–2:40 | Was wo läuft | text | `stack` | folgt | SC3 | Weiterentwicklung und Betrieb, Bedienbarkeit |
| 5 | `05-beleg.md` | 2:40–3:15 | 2.880 von 2.880 | zahl | `beleg` | folgt | SC4 | Qualitätssicherung, Reporting |
| 6 | `06-fallen.md` | 3:15–4:15 | Acht Fallen in den Daten | text | `fallen` | folgt | SC6 | Datenmanagement, Qualitätssicherung |
| 7 | `07-annahme.md` | 4:15–5:00 | Geburtsmonat 13 | text | `annahme` | folgt | SC8 | Qualitätssicherung, Klassifikation |
| 8 | `08-live.md` | 5:00–8:20 | Jetzt live | live (`/uc3`) | `live` | folgt | SC12 | Reporting, Weiterentwicklung und Betrieb, Bedienbarkeit |
| 9 | `09-veroeffentlicht.md` | 8:20–8:50 | Veröffentlicht bleibt veröffentlicht | zahl | `veroeffentlicht` | folgt | SC10 | Datenmanagement, Qualitätssicherung |
| 10 | `10-einstieg.md` | 8:50–9:15 | Ein Kern, ein Einstieg | text | `einstieg` | folgt | SC11 | Weiterentwicklung und Betrieb, Bedienbarkeit |
| 11 | `11-schluss.md` | 9:15–9:30 | Jede Zahl nachrechenbar | titel | `schluss` | folgt | kein Bild | alle |

Die Summe von `dauer_s` ist 570 Sekunden (9:30). Bis 10:00 bleiben 30 Sekunden Puffer.

Szene 8 enthält die Überleitung (5:00–5:10, 10 Sekunden) und die Demo von 5:10 bis 8:20 (3:10). Die Demo hat vier Teile: D1 5:10–6:15, D2 6:15–7:35, D3 7:35–8:10, UC-Wechsel 8:10–8:20.

Pen-Frame: Die Spalte bleibt `folgt`. Die Pen-Frames P01 bis P11 in `design/ki-challenge.pen` (x 0–7920, y 4400–7880) gelten als Entwurf der alten Folienfolge. Sie gehören nicht zu den Szenen v2.

Pflichtinhalte der Aufgabenstellung und wo sie stehen: Lösung (Szenen 1, 3, 4), gefundene Fehler (Szene 6), eine Annahme im Detail (Szene 7), Live-Änderung und Datenanfrage (Szene 8, Demo).

## Format der Runtime (#59)

Eine Markdown-Datei je Szene. Der Dateiname beginnt mit der zweistelligen Nummer, die Reihenfolge ergibt sich daraus. Die Layouts und Schlüssel der Runtime stehen auch in `web/content/slides/README.md`. Die Datei `README.md` ist keine Szene.

Frontmatter (flache `schluessel: wert`-Zeilen):

| Feld | Pflicht | Inhalt |
|---|---|---|
| `nummer` | ja | Position im Deck, 1 bis 11, passend zum Dateinamen |
| `titel` | ja | Titel der Szene, auch für die Leiste |
| `layout` | ja | Rückfall-Layout der Runtime: `titel`, `text`, `schritte`, `zahl` oder `live`. Der alte Name `cover` gilt weiter als `titel`. |
| `szene` | ja | wählt die animierte Szene, Muster `[a-z0-9-]+`, nicht leer. Kennt die Runtime die Szene nicht, zeichnet sie das `layout`. |
| `route` | bei `live` | App-Route, die in der Szene läuft, z. B. `/uc3` |
| `zeit` | ja | Zeitmarke im Vortrag, z. B. `"2:40–3:15"` |
| `dauer_s` | ja | Soll-Dauer in Sekunden, Summe höchstens 600, Soll 570 |
| `bereiche` | ja | Bewertungsbereiche, die die Szene belegt |
| `screenshot` | nein | Kennung des Bildes (`SC1` bis `SC12`) oder `null`; Datei `docs/praesentation/screens/SC01.png` usw. |
| `pen_frame` | nein | ID des Pen-Frames, heute `null` |
| `belege` | ja | Kennungen der Zahlen im Belegregister, z. B. `[F1, F2]` |
| `zahl`, `beleg` | nein | nur bei Layout `zahl`: die große Zahl und die Zeile darunter |

Weitere Schlüssel (zum Beispiel `zahl_geliefert` und `monat_bruch` in Szene 2) sind erlaubt. Die Runtime liest nur, was die Szene braucht.

Körper: Die erste Überschrift `#` ist der sichtbare Titel. Alles bis zur Überschrift `## Sprechernotizen` ist Szeneninhalt. Was danach steht, sind die Notizen; die Runtime zeigt sie mit der Taste N. Der Sprechtext im Skript ist wörtlich dieser Text.

Die Zeile, die mit `Herkunft:` beginnt, ist die sichtbare Quellenangabe der Szene. Die Runtime setzt sie klein an den unteren Rand.

Geprüft wird das Format mit `python3 docs/praesentation/werkzeug/slides_check.py`.

## Animation

Die Regeln gelten für den Prototyp und die App gleich.

- Tasten: Pfeil rechts, Leertaste und Bild ab gehen zum nächsten Takt oder zur nächsten Szene. Pfeil links und Bild auf gehen zurück. F ist Vollbild, N schaltet die Notizen, Pos1 und Ende springen an den Rand.
- Die Szene steht in der Adresse (`#3` im Prototyp, `?folie=3` in der App).
- Animiert wird nur mit CSS-Keyframes an der aktiven Szene (`.aktiv`). Die Staffel läuft über `--i` (`animation-delay: calc(var(--i) * 90ms + 100ms)`). Eine Animation dauert 0,5 bis 0,8 Sekunden, Easing `cubic-bezier(.2,.7,.2,1)`.
- Große Zahlen zählen mit `requestAnimationFrame` in 1,2 Sekunden hoch.
- Keine Endlosschleifen, keine schwebenden Elemente.
- Bei `prefers-reduced-motion: reduce` gibt es keine Bewegung. Der Endzustand ist sofort sichtbar: alle Takte gezeigt, Zahlen am Endwert.
- Beleg-Fenster: Bild mit dünnem Rand in #1E3542, 560 Pixel breit, unten rechts. Es gleitet nach 1,2 Sekunden herein. Platzhalterbilder tragen oben links einen gelben Chip „Platzhalter, generiert“.
- Druck und PDF: alle Szenen untereinander im Endzustand.

## Rückfall ohne Runtime

Läuft die Runtime #59 am Freitag nicht, gilt diese Reihenfolge:

1. Das PDF aus der Seite zeigen: die Druckansicht der Präsentationsseite, alle Szenen im Endzustand, im Vollbild. Das PDF ersetzt das frühere Pen-PDF. Die Notizen stehen im Skript.
2. Die Markdown-Dateien sind ohne Runtime lesbar. Sie dienen als Sprechzettel.
3. Die Demo läuft unabhängig davon in einem eigenen Fenster (`demo-drehbuch.md`).

Das PDF liegt nicht im Repo, sondern lokal unter `docs/praesentation/export/` (über `.gitignore` ausgeschlossen).

## Screenshots SC1 bis SC12

Abnahme der Bilder über #88. Ablage `docs/praesentation/screens/SC01.png` bis `SC12.png`, mindestens 1920 Pixel breit. Das Manifest `screens-manifest.md` nennt je Bild Route, Commit, Lauf und ob es live, aus Testdaten oder eine Aufzeichnung ist.

| Bild | Motiv | Quelle | Szene |
|---|---|---|---|
| SC1 | Läufe-Übersicht, 24 Monate mit Status | UC3-Oberfläche (#18) | 2 |
| SC2 | Eine Regel mit Gültigkeit, Begründung, Freigabe | UC3-Oberfläche (#18) oder `uc3 regeln zeigen` | 3 |
| SC3 | Terminal `uc3 lauf --lieferung 2024-08` | Terminal-Aufnahme eines echten Laufs | 4 |
| SC4 | Zellvergleich 2.880 von 2.880 | Terminal `uc3 eichen --lieferung 2024-08` | 5 |
| SC5 | Aggregations-Sheet Tab1 | `abgabe/aggregationen_v1.xlsx` | Reserve |
| SC6 | Qualitätsbericht 2025-03 mit Einstufungen | UC3-Oberfläche oder `abgabe/qualitaetsberichte/2025-03.md` | 6 |
| SC7 | Qualitätsbericht 2025-10, Lauf angehalten | UC3-Oberfläche oder `abgabe/qualitaetsberichte/2025-10.md` | Reserve |
| SC8 | Regel `R5_alter` als Daten | UC3-Oberfläche oder `uc3 regeln zeigen` | 7 |
| SC9 | Rückfrage R1 an die Fachabteilung | `abgabe/rueckfragen/R1.md` | Reserve |
| SC10 | Protokoll mit Freigabe, Name, Zeit, Wirkung | UC3-Oberfläche oder `uc3 protokoll --zeigen` | 9 |
| SC11 | Gemeinsamer Einstieg (UC4) mit dem Wechsel der Use Cases im App-Kopf | öffentliche Demo, Route `/uc4` | 10 |
| SC12 | Agent-Vorschlag mit Diff vor der Freigabe | `uc3 vorschlag zeigen <id>` oder Oberfläche | 8 |

Die Bilder SC5, SC7 und SC9 tragen keine Szene mehr und sind Reserve. Ein Bild aus Testdaten oder eine Aufzeichnung wird im Manifest so gekennzeichnet. Es wird nie als Live-Lauf ausgegeben.

## Gemeinsamer Einstieg (UC4, #95)

Szene 10 zeigt den gemeinsamen Einstieg als nächsten Schritt: Eine Frage läuft durch UC3, UC2 und UC1. Jeder Use Case antwortet in derselben Form `antwort(frage, kontext)` mit Text, Belegen, Zahlen, Use Case, Modell und Protokoll-Eintrag.
In der Demo kommt der Einstieg nur vor, wenn `/uc4` bis zum Freeze Fr 07:00 grün ist (optional D4 im Drehbuch). Sonst bleibt es bei Szene 10.
