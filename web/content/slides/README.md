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
Markdown; im Code stehen nur Gestaltungstexte ohne Inhalt. Die Zeile `Herkunft: …` steht unten links, Nummer und
Zeit unten rechts. `layout` bleibt der Rückfall, falls die Szene fehlt.

| `szene` | Erwartet im Markdown | Zusätze im Frontmatter |
|---|---|---|
| `titel` | `#` Marke, 1. Absatz: Sätze, die nacheinander erscheinen, 2. Absatz: Zeile unten | `hervorheben`: Wort, das zuletzt Mint wird |
| `falsche-zahl` | `#` Titel, Liste mit drei Sätzen (je Takt einer), Tabelle Monat und Wert | `monat_bruch`, `zahl_geliefert` |
| `beleg` | 1. Absatz Satz, 2. Absatz Brücke | `zahl`, z. B. `2.880 von 2.880`: Raster und Hochzählen |
| `annahme` | `#` Titel, Unterzeile, Tabelle Variante, Behandlung, `… von N`, Schlusssatz | keine |
| `einstieg` | 1. Absatz Frage (tippt sich), Liste `**UCn Name:** Satz`, Tabelle, Absatz Kern | keine |
| `schluss` | `#` erster Satz, 1. Absatz zweiter Satz, 2. Absatz Zeile klein | keine |

### Takte

Eine Szene kann Takte haben: Schritte innerhalb der Szene, die nur auf Tastendruck kommen. Pfeil rechts zeigt erst
den nächsten Takt, nach dem letzten Takt die nächste Folie. Pfeil links geht erst die Takte zurück; wer eine Szene
von hinten betritt, sieht alle Takte. Die Adresse trägt nur `?folie=N`, eine Folie startet dort mit Takt 0.
Bei reduzierter Bewegung und im Druck zeigt jede Szene sofort alle Takte. Heute hat nur `falsche-zahl` Takte (drei).

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
