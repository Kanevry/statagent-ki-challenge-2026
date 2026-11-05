# Storyboard: Fachjury-Präsentation StatAgent

Stand 05.11.2026, Szenen v4 („1 + 2 + 3 = 4“). Gehört zu Epic #26, #89 und #59. Diese Datei ordnet jede Szene einer Datei, einem Bild und den Bewertungsbereichen zu.
Sie beschreibt auch das Format der Präsentations-Runtime (#59) und den Rückfall ohne Runtime.

Ablauf: 10 Szenen in rund 5:05, danach die Live-Demo bis 9:30 (D1 5:05–6:15, D2 6:15–7:45, D3 7:45–9:00, D4 9:00–9:30). Danach Live-Änderung und Datenanfragen der Jury.
Sprechtext: `skript-fachjury.md`. Demo: `demo-drehbuch.md`. Fragen: `fragenkatalog.md`. Zahlen: `belegregister.md`.

Eine „Szene“ ist eine Seite der Präsentation. Die Dateien liegen unter `web/content/slides/`, die Reihenfolge ergibt sich aus dem Dateinamen.

## Roter Faden

Drei Menschen brauchen eine Antwort, der sie trauen können. Vertrauen entsteht, wenn jede Zahl einen Beleg hat und jede Änderung einen Namen. Aus diesem Kern für die Statistik (3) wurden Lotse (1) und Simulator (2), und zusammen der gemeinsame Einstieg (4).

Owner-Entscheide: Die Folien zeigen das Zielbild „1 + 2 + 3 = 4“ und wie wir dahin kamen. Der Tagesstand steht nur im Fragenkatalog. Monate stehen im Text ausgeschrieben („Oktober 2025“), auf Achsen in Kurzform („Okt 2025“), nie als Ziffernfolge aus Jahr und Monat. Sichtbar steht nie „Beispiel“, „Platzhalter“ oder „generiert“. Zeitmarken stehen nur in den Notizen. Die Schlussfolie nennt ki-challenge.gotzendorfer.at.

## Szenen

| Nr | Datei in `web/content/slides/` | Zeit | Titel | Szene | Takte | Bild | Bewertungsbereiche |
|---|---|---|---|---|---|---|---|
| 1 | `01-gleichung.md` | 0:00–0:15 | Drei Aufgaben, eine Antwort | `gleichung` | 0 | kein Bild | alle |
| 2 | `02-drei-fragen.md` | 0:15–0:45 | Drei Menschen, drei Fragen | `drei-fragen` | 0 | kein Bild | Bedienbarkeit, Weiterentwicklung und Betrieb |
| 3 | `03-falsche-zahl.md` | 0:45–1:45 | Eine falsche Zahl kostet Vertrauen | `falsche-zahl` | 3 | kein Bild (24 Säulen) | Datenmanagement, Qualitätssicherung |
| 4 | `04-kern.md` | 1:45–2:20 | Aus Use Case 3 wurde ein Kern für alle drei | `kern` | 3 | `freigabe-echt` | Weiterentwicklung und Betrieb, Qualitätssicherung |
| 5 | `05-beleg.md` | 2:20–2:50 | Wir rechnen den offiziellen Bericht nach | `beleg` | 0 (Zählung ist die Bewegung) | kein Bild | Qualitätssicherung, Reporting |
| 6 | `06-fehler.md` | 2:50–3:25 | Acht Arten von Fehlern gefunden | `fehler` | 3 | kein Bild | Datenmanagement, Qualitätssicherung |
| 7 | `07-woerterbuecher.md` | 3:25–3:50 | Im Januar 2025 wechselt die Branchenliste | `woerterbuecher` | 0 | kein Bild | Klassifikation, Datenmanagement |
| 8 | `08-annahme.md` | 3:50–4:25 | Den 13. Monat haben wir nachgerechnet | `annahme` | 3 | kein Bild | Qualitätssicherung, Klassifikation |
| 9 | `09-einstieg.md` | 4:25–4:55 | Eine Frage, drei Antworten, jede mit Beleg | `einstieg` | 3 | kein Bild | Weiterentwicklung und Betrieb, Bedienbarkeit |
| 10 | `10-schluss.md` | 4:55–5:05 | Jede Zahl nachrechenbar | `schluss` | 0 | kein Bild | alle |

Die Summe von `dauer_s` ist 305 Sekunden (5:05). Danach folgt die Demo nach dem Drehbuch, sie steht nicht in den Folien.

Die Pen-Frames P01 bis P11 in `design/ki-challenge.pen` (x 0–7920, y 4400–7880) gelten als Entwurf der ersten Fassung. Sie gehören nicht zu den Szenen v4.

Pflichtinhalte der Aufgabenstellung und wo sie stehen: Lösung (Szenen 3, 4, 5), gefundene Fehler (Szenen 6, 7), eine Annahme im Detail (Szene 8), Zielbild und Einstieg (Szene 9), Live-Änderung und Datenanfrage (Demo nach Szene 10).

## Bildsprache

- **Drei Kreise** sind die drei Aufgaben. Linie `#F4F7F5` 3 px, Ziffer in Space Grotesk. Kreis 3 trägt einen Mint-Ring. Der vierte Kreis ist gefüllt Mint (`#3DDC97`), Ziffer 4 in `#060F15`.
- **Mint-Haken** (gezeichneter SVG-Pfad) heißt belegt, geprüft. **Gelb** (`#F5D54F`) heißt Problem, Fehler, angehalten, und steht nur dort. Erfolge sind Mint oder Weiß. **Unterschrift** (ein Name tippt sich) heißt: Ein Mensch gibt frei.
- Hintergrund `#060F15`, Text `#F4F7F5`, Nebentext `#8FA3AD`, Linien `#1E3542`. Schriften: Space Grotesk (Überschriften, Zahlen), Inter (Text), JetBrains Mono (Daten, Codes).
- Kopf in den Szenen 3 bis 9: Kreis 3 klein (72 px) bei x=120, y=92, Titel bei x=220, höchstens eine Zeile (60 px, Szene 5 46 px). Die Szenen 1, 2 und 10 sind zentrierte Erzählfolien.
- Herkunft 26 px (Mint, unten links), Fließtext und Takttexte mindestens 36 px, kleinste Beschriftung 28 px.
- Überschriften sind Aussagen, nie Fragen. Keine Kartenrahmen, keine Schatten, keine Verläufe.
- Beschäftigungsverhältnisse, nicht „Beschäftigte“ oder „Menschen“, wenn gezählte Fälle gemeint sind. „Datensätze“ ist neutral.

## Motion

- Ein Blickpunkt nach dem anderen. Bewegungen 400 bis 900 ms, `cubic-bezier(.2,.7,.2,1)`. Linien und Haken zeichnen sich, Zahlen zählen hoch, Elemente gleiten 24 px herein.
- Szenenwechsel: Überblendung 300 ms. Kreise gleicher Nummer gleiten von ihrer alten an ihre neue Stelle.
- **Takte:** Ein Klick ergibt einen gesprochenen Satz und eine Bewegung. Takte haben die Szenen 3, 4, 6, 8 und 9 (je 3). Szene 5 läuft ohne Takt. Im Sprechtext der Notizen markiert „[→]“ den Klick.
- Keine Endlosschleifen. Einzige Ausnahme: Kreis 4 atmet in Szene 10 genau zweimal.
- `prefers-reduced-motion: reduce` und Druck: sofort Endzustand, alle Takte sichtbar.
- Sprechtexte passen in die Szenendauer bei 130 Wörtern pro Minute minus 20 %.
- Tasten: Pfeil rechts, Leertaste und Bild ab gehen zum nächsten Takt oder zur nächsten Szene. Pfeil links und Bild auf gehen zurück. F ist Vollbild, N schaltet die Notizen, Pos1 und Ende springen an den Rand.

## Format der Runtime (#59)

Eine Markdown-Datei je Szene. Der Dateiname beginnt mit der zweistelligen Nummer, die Reihenfolge ergibt sich daraus. Die Layouts und Schlüssel der Runtime stehen auch in `web/content/slides/README.md`. Die Datei `README.md` ist keine Szene.

Frontmatter (flache `schluessel: wert`-Zeilen):

| Feld | Pflicht | Inhalt |
|---|---|---|
| `titel` | ja | Titel der Szene, auch für die Leiste. Ist er gesetzt, braucht der Körper keine `#`-Überschrift (Szene 2 hat keine). |
| `layout` | ja | Rückfall-Layout der Runtime: `titel`, `text`, `schritte`, `zahl` oder `live`. Der alte Name `cover` gilt weiter als `titel`. |
| `szene` | ja | wählt die animierte Szene, Muster `[a-z0-9-]+`. Kennt die Runtime die Szene nicht, zeichnet sie das `layout`. |
| `zeit` | ja | Zeitmarke im Vortrag, z. B. `"2:20–2:50"` |
| `dauer_s` | ja | Soll-Dauer in Sekunden, Summe höchstens 600, Soll 305 |
| `belege` | ja | Kennungen der Zahlen im Belegregister, z. B. `[F1, F15]`, oder `[]` |
| `nummer` | nein | Position im Deck 1 bis 10, passend zum Dateinamen |
| `bereiche` | nein | Bewertungsbereiche, die die Szene belegt |
| `screenshot` | nein | Schlüssel des Bildes in der Bildregistry, oder `null` |
| `route` | bei `live` | App-Route, die in der Szene läuft |
| `pen_frame` | nein | ID des Pen-Frames, heute `null` |

Weitere Schlüssel (zum Beispiel `zahl_geliefert` in Szene 3) sind erlaubt. Die Runtime liest nur, was die Szene braucht.

Körper: Alles bis zur Überschrift `## Sprechernotizen` (oder zur Zeile `<!-- notizen -->`) ist Szeneninhalt. Was danach steht, sind die Notizen; die Runtime zeigt sie mit der Taste N. Der Sprechtext im Skript ist wörtlich dieser Text, die Takte stehen dort als „[→]“.

Die Zeile, die mit `Herkunft:` beginnt, ist die sichtbare Quellenangabe der Szene. Die Runtime setzt sie klein an den unteren Rand.

**Bilder:** `screenshot` nennt einen Schlüssel der Bildregistry `web/components/praesentation/bilder.ts`. Die Datei liegt in `web/content/slides/bilder/`. Es gibt nur echte Aufnahmen, zugeschnitten auf ein lesbares Element, ohne Beschriftung als „Beispiel“ oder „Platzhalter“. Heute gibt es ein Bild: Szene 4, `freigabe-echt.png`, zugeschnitten aus der Freigabe-Seite (MR !51) mit „Diese Änderung wartet auf Ihre Freigabe.“, Vorher 392.236, Nachher 392.236, Unterschied 0 und dem Feld „Vor- und Nachname“ (F19). Alle anderen Szenen haben kein Bild.

Geprüft wird das Format mit `python3 docs/praesentation/werkzeug/slides_check.py`.

## Rückfall ohne Runtime

Läuft die Runtime #59 am Freitag nicht, gilt diese Reihenfolge:

1. Das PDF aus der Seite zeigen: die Druckansicht der Präsentationsseite als PDF, alle Szenen im Endzustand, im Vollbild. Die Notizen stehen im Skript.
2. Die Markdown-Dateien sind ohne Runtime lesbar. Sie dienen als Sprechzettel.
3. Die Demo läuft unabhängig davon in einem eigenen Fenster (`demo-drehbuch.md`).

Das PDF liegt nicht im Repo, sondern lokal unter `docs/praesentation/export/` (über `.gitignore` ausgeschlossen).

## Screenshots SC1 bis SC12 (Liste für #88)

Die Liste bleibt für die Abnahme über #88. Die Folien selbst zeigen nur noch `freigabe-echt` aus MR !51 (Szene 4). Ablage der übrigen Bilder `docs/praesentation/screens/SC01.png` bis `SC12.png`, mindestens 1920 Pixel breit. Das Manifest `screens-manifest.md` nennt je Bild Route, Commit, Lauf und ob es live, aus Testdaten oder eine Aufzeichnung ist.

| Bild | Motiv | Quelle |
|---|---|---|
| SC1 | Läufe-Übersicht, 24 Monate mit Status | UC3-Oberfläche (#18) |
| SC2 | Eine Regel mit Gültigkeit, Begründung, Freigabe | UC3-Oberfläche (#18) oder `uc3 regeln zeigen` |
| SC3 | Terminal `uc3 lauf --lieferung 2024-08` | Terminal-Aufnahme eines echten Laufs |
| SC4 | Zellvergleich 2.880 von 2.880 | Terminal `uc3 eichen --lieferung 2024-08` |
| SC5 | Aggregations-Sheet Tab1 | `abgabe/aggregationen_v1.xlsx` |
| SC6 | Qualitätsbericht März 2025 mit Einstufungen | UC3-Oberfläche oder `abgabe/qualitaetsberichte/2025-03.md` |
| SC7 | Qualitätsbericht Oktober 2025, Lauf angehalten | UC3-Oberfläche oder `abgabe/qualitaetsberichte/2025-10.md` |
| SC8 | Regel `R5_alter` als Daten | UC3-Oberfläche oder `uc3 regeln zeigen` |
| SC9 | Rückfrage R1 an die Fachabteilung | `abgabe/rueckfragen/R1.md` |
| SC10 | Protokoll mit Freigabe, Name, Zeit, Wirkung | UC3-Oberfläche oder `uc3 protokoll --zeigen` |
| SC11 | Gemeinsamer Einstieg (UC4) mit dem Wechsel der Use Cases im App-Kopf | öffentliche Demo, Route `/uc4` |
| SC12 | Agent-Vorschlag mit Diff vor der Freigabe | `uc3 vorschlag zeigen <id>` oder Oberfläche |

Ein Bild aus Testdaten oder eine Aufzeichnung wird im Manifest so gekennzeichnet. Es wird nie als Live-Lauf ausgegeben.

## Gemeinsamer Einstieg (UC4, #95)

Szene 9 zeigt den gemeinsamen Einstieg als Zielbild: Eine Frage läuft durch UC3, UC2 und UC1. Jeder Use Case antwortet in derselben Form `antwort(frage, kontext)` mit Text, Belegen, Zahlen, Use Case, Modell und Protokoll-Eintrag.
In der Demo kommt der Einstieg nur vor, wenn `/uc4` bis zum Freeze Fr 07:00 grün ist (optional D4 im Drehbuch). Der Tagesstand steht im Fragenkatalog (C16).
