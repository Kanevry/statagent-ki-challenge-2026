---
nummer: 4
titel: Was wo läuft
layout: text
szene: stack
zeit: "2:10–2:40"
dauer_s: 30
bereiche: [Weiterentwicklung und Betrieb, Bedienbarkeit]
screenshot: SC3
pen_frame: null
belege: [F16]
---

# Was wo läuft

- **Oberfläche:** zeigt und startet
- **Programm `statagent`, Befehl `uc3`:** liest ein, rechnet, prüft, berichtet
- **PostgreSQL 16:** Rohdaten, Klassifikationen, Regeln

**Agenten:** schreiben Vorschläge für Regeln und Code. Modell austauschbar. Sehen Regeln und Summen, keine Einzeldaten.

Herkunft: uc3/README.md

## Sprechernotizen

So ist es gebaut. Unten die Datenbank, darüber das Programm, oben die Oberfläche.
Die Agenten machen nur Vorschläge. Welches Modell dahinter steht, ist ein Schalter. Einzelne Datensätze sieht es nie.
