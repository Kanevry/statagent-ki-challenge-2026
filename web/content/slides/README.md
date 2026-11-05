# Folien für /praesentation

Jede Folie ist eine Markdown-Datei in diesem Ordner. Die Reihenfolge ergibt sich aus dem Dateinamen
(`01-titel.md`, `02-falsche-zahl.md`, ..., `10-...` kommt nach `09-...`). Diese README ist keine Folie.

## Aufbau einer Datei

```
---
titel: Kurzer Titel
layout: text
---

# Überschrift der Folie

Text, Listen, Tabellen.

<!-- notizen -->

Sprechtext. Steht nie auf der Folie.
```

- Oben steht ein Block zwischen zwei Zeilen `---` mit Zeilen der Form `schluessel: wert`.
- Danach folgt der Inhalt der Folie. Alles nach der Zeile `<!-- notizen -->` ist nur Sprechtext. Die Zeile
  `## Sprechernotizen` gilt genauso als Trenner.
- Die Notizen erscheinen nur, wenn man bei der Präsentation die Taste N drückt.

## Angaben oben in der Datei

| Schlüssel | Pflicht | Bedeutung |
|---|---|---|
| `titel` | ja | Name der Folie in der Folienleiste. Fehlt er, gilt die erste Überschrift. |
| `layout` | ja | Eines der Layouts unten. Unbekannt oder leer ergibt `text`. |
| `route` | bei `live` | Seite, die in der Folie läuft, z. B. `/uc3`. |
| `zeit` | nein | Zeit in der Folienleiste, z. B. `3:15` oder `3:15–4:15`. Es zählt der Anfang. |
| `zahl` | nein | Nur bei `zahl`: die große Zahl. |
| `beleg` | nein | Nur bei `zahl`: die Zeile unter der Zahl. |

| `szene` | nein | Animierte Szene, siehe unten. Unbekannt oder leer: es gilt `layout`. |

Weitere Schlüssel (`nummer`, `bereiche`, `belege` und so weiter) sind erlaubt. Die Szenen lesen manche davon
als Zusatz (Tabelle unten), alle anderen werden ignoriert.

## Szenen

Steht `szene` im Frontmatter, läuft die Folie als animierte Szene auf der dunklen Bühne (1920 × 1080). Die Registry
ist `web/components/praesentation/szenen/index.ts`. Jede Szene nimmt ihren Text, ihre Zahlen und Tabellen aus dem
Markdown; im Code stehen nur Gestaltungstexte ohne Inhalt. Die Zeile `Herkunft: …` steht unten links. Zeitmarken
(`zeit`) stehen nur in den Notizen (Taste N), nie auf der Bühne. `layout` bleibt der Rückfall, falls die Szene fehlt.
Die Szenen 3 bis 9 tragen einen einheitlichen Kopf: kleiner Kreis 3, daneben die `#`-Überschrift in einer Zeile.

| `szene` | Takte | Erwartet im Markdown | Zusätze im Frontmatter |
|---|---|---|---|
| `gleichung` | 0 | `#` Satz unter 1 + 2 + 3 = 4, 1. Absatz: Zeile klein | keine |
| `drei-fragen` | 0 | Tabelle Aufgabe, Person, Frage (tippt sich), Lösung; Absatz: Satz über der Linie | keine |
| `falsche-zahl` | 3 | `#` Titel, Liste mit drei Sätzen (je Takt einer), Tabelle Monat (JJJJ-MM) und Wert, Spaltenkopf über dem Diagramm | `monat_bruch`, `zahl_geliefert`, `vergleich`, `vorlaeufig`, `stempel` |
| `kern` | 3 | `#` Titel, Liste mit drei Regeln (je Takt eine, von oben), Absatz unten klein | `name`: tippt sich unter der zweiten Regel; `screenshot`, `bild_alt` |
| `beleg` | 0 | `#` Titel, Tabelle mit drei Spalten-Köpfen (Bericht, eigene Rechnung, übrige Monate), Absätze: Zählzeile, Ergebnis, Satz | `zahl`, z. B. `2.880`: Zahl der Quadrate je Raster |
| `fehler` | 3 | `#` Titel, Tabelle Muster, Fehler, Anzahl, Lieferung (je Takt eine Zeile), Absatz im dritten Takt | keine |
| `woerterbuecher` | 0 | `#` Titel, zwei Tabellen (alte und neue Liste, Kopf: Name und Gültigkeit), Absätze: Teilung, Satz | `uebergang`, z. B. `C-C J-J Q-R J-K`; ein Code mit zwei Zielen teilt sich gelb |
| `annahme` | 3 | `#` Titel, 1. Absatz (Takt 1), Tabelle Rechenweg und Spaltenkopf mit Gesamtzahl (Takt 2), Schlusssatz (Takt 3) | `treffer`: Satz neben dem Haken |
| `einstieg` | 3 | `#` Titel, 1. Absatz Frage (tippt sich), Liste mit drei Antworten (je Takt eine), 2. Absatz unter Kreis 4 | keine |
| `schluss` | 0 | `#` erster Satz, Absätze: zweiter Satz, Live-Zeile, Nebenzeile, Adresse unten | keine |

Jeder sichtbare Satz steht im Markdown, auch kurze wie der Stempel oder der Treffer-Satz. Monate im sichtbaren Text
ausgeschrieben („Oktober 2025“); nur Tabellen tragen sie als Daten (`2025-10`), die Säulenachse macht daraus
„Okt 2025“. Die Kreise 1 bis 4, die Zeichen + und = und die Achsenwerte sind Gestaltung. Kreise mit gleicher Nummer
gleiten beim Wechsel von ihrer alten an ihre neue Stelle. Gelb steht nur für Probleme, Erfolge sind Mint oder Weiß.

### Blick in die App

`screenshot: freigabe-echt` nennt die Aufnahme, die eine Szene als ruhiges Fenster zeigt (heute nur `kern`, im
zweiten Takt). Sie erscheint nur, wenn die Datei hier unter `bilder/` liegt und in
`web/components/praesentation/bilder.ts` unter derselben Kennung statisch importiert ist; den Alt-Text trägt
`bild_alt`. Sonst bleibt der Platz leer. Nur echte Aufnahmen aus der App, ohne Beschriftung.

### Takte

Eine Szene kann Takte haben: Schritte innerhalb der Szene, die nur auf Tastendruck kommen. Pfeil rechts zeigt erst
den nächsten Takt, nach dem letzten Takt die nächste Folie. Pfeil links geht erst die Takte zurück; wer eine Szene
von hinten betritt, sieht alle Takte. Die Adresse trägt nur `?folie=N`, eine Folie startet dort mit Takt 0.
Bei reduzierter Bewegung und im Druck zeigt jede Szene sofort alle Takte. Die Taktzahl je Szene steht in der
Registry; im Sprechtext markiert `[→]` den Klick.

## Layouts

- `titel` (auch `cover`): große Überschrift, der erste Absatz als Untertitel, weitere Absätze klein darunter.
- `text`: Überschrift, darunter Absätze, Listen, Tabellen und Zwischenüberschriften (`##`).
- `schritte`: wie `text`, aber nummerierte Listen (`1.`) erscheinen als große Schritte.
- `zahl`: eine große Zahl mit Beleg-Zeile. Die Zahl ist `zahl`, sonst die erste Überschrift. Die Beleg-Zeile ist
  `beleg`, sonst der Absatz, der mit `Herkunft:` oder `Beleg:` beginnt.
- `live`: die Überschrift oben, darunter läuft die Seite aus `route` mitten in der Folie. Erlaubt sind nur Routen
  aus `web/lib/praesentation/live.tsx`. Eine andere Route zeigt einen ruhigen Hinweis mit Link.

## Schreibweise

- `# ` und `## ` für Überschriften, `- ` und `1. ` für Listen, `**fett**` und `` `code` `` im Text.
- Tabellen mit `| a | b |` und einer Trennzeile `|---|---|`.
- Kein HTML. Ein Absatz endet mit einer Leerzeile.
- Kurze Sätze, keine Gedankenstriche, keine erfundenen Zahlen.

## Bedienung

Pfeil rechts, Leertaste und Bild ab: weiter (erst Takt, dann Folie). Pfeil links und Bild auf: zurück. Pos1 und Ende: erste und letzte
Folie. F: Vollbild. N: Notizen. Die Adresse trägt die Folie (`/praesentation?folie=3`, ab 1 gezählt). Eine
ungültige Zahl öffnet Folie 1.
