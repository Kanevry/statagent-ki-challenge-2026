---
nummer: 4
titel: Was wo läuft
layout: diagramm
zeit: "2:00–2:45"
dauer_s: 45
bereiche: [Weiterentwicklung und Betrieb, Bedienbarkeit]
screenshot: SC3
pen_frame: QpM2f
belege: [F16]
---

# Was wo läuft

**PostgreSQL 16:** Rohdaten, Klassifikationen, Regeln in `meta.regel`

**Python-Programm `statagent`, Befehl `uc3`:** liest ein, rechnet, prüft, schreibt Berichte

**Oberfläche:** zeigt Läufe und Berichte und startet Befehle

**Agenten:** schreiben Vorschläge für Regeln und Code. Das Modell ist austauschbar. Es sieht Regeln und Summen, keine Einzeldaten.

Herkunft: `uc3/README.md`

## Sprechernotizen

So ist es gebaut. Unten liegt PostgreSQL 16, die Datenbank. Darüber liegt das Python-Paket statagent mit dem Befehl uc3. Es liest, prüft und rechnet. Die Oberfläche in Next.js liest nur und startet diesen Befehl. Die Agenten sprechen über eine einzige Schnittstelle mit dem Modell. Das Modell ist austauschbar. Es sieht Regeln, Schemata und Summen. Einzeldaten sieht es nie.
