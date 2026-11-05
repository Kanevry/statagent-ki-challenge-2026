# Folien für /praesentation

Jede Folie ist eine Markdown-Datei in diesem Ordner. Die Reihenfolge ergibt sich aus dem Dateinamen
(`01-cover.md`, `02-problem.md`, ..., `10-...` kommt nach `09-...`). Diese README ist keine Folie.
Die drei Dateien `*-beispiel-*` sind Platzhalter und werden gelöscht, sobald die echten Folien da sind.

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

Weitere Schlüssel (`nummer`, `bereiche`, `belege` und so weiter) sind erlaubt und werden ignoriert.

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

Pfeil rechts, Leertaste und Bild ab: weiter. Pfeil links und Bild auf: zurück. Pos1 und Ende: erste und letzte
Folie. F: Vollbild. N: Notizen. Die Adresse trägt die Folie (`/praesentation?folie=3`, ab 1 gezählt). Eine
ungültige Zahl öffnet Folie 1.
