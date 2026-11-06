# Live-Änderung vor der Jury: Spickzettel

Stand 05.11.2026, Code aus !150. Geprobt nur auf Kopien der Abgabe-DB, nie auf `statistik`.

## Vorher einstellen

```bash
export UC3_DATABASE_URL=<eigene Kopie, z. B. statistik_vorfuehrung>
export LLM_PROVIDER=azure
```

- Die Ziel-DB kommt nur aus `UC3_DATABASE_URL`. Ohne die Variable wäre es die Abgabe-DB `statistik`: Dann nicht weitermachen.
- Die Vorführung läuft online mit Azure auf einer eigenen, gesperrten Instanz mit eigener DB (Owner 05.11.2026, Lane b-vorfuehrung). Offline ist gestrichen. Die Zählung selbst braucht kein Modell.
- Keinen Tunnel zwischen Programm und Datenbank. In den Proben fiel der Tunnel zweimal weg, mitten im Ablauf.
- `uc3 freigabe` macht einen Git-Commit im Checkout, aus dem das Programm läuft. Die Instanz braucht einen eigenen Checkout mit schreibbarem `.git`, nie einen Arbeits-Worktree.
- Web- und Proxy-Timeouts mindestens 300 s; `uc3 agent` mit Probe dauert rund 1 bis 2 Minuten.

## Ablauf

| Schritt | Befehl | Was man sieht |
|---|---|---|
| 1. Auftrag | `uv run uc3 agent "<Auftrag der Jury>"` | Vorschlag mit Nummer N, Rolle, „v2 → v3 (v2 bleibt unverändert)“. Dauer rund 1 Minute, weil das Programm den Monat zweimal rechnet. |
| 2. Prüfen | `uv run uc3 vorschlag zeigen N` | Regel-Unterschied und Zahlen vorher und nachher, nur was sich ändert. |
| 3a. Ablehnen | `uv run uc3 ablehnen N --name "Vorname Nachname" --begruendung "…"` | Nichts ändert sich, kein Commit. |
| 3b. Freigeben | `uv run uc3 freigabe N --name "Vorname Nachname"` | Regel aktiv im neuen Regelsatz, ein Commit mit `Freigegeben-von`. |
| 4. Protokoll | `uv run uc3 protokoll --zeigen` | Anweisung, Name, Zeit. |
| 5. Zurück | `uv run uc3 agent "Nimm Vorschlag N zurück, wie es vorher war."`, dann wieder `freigabe` | Neuer Vorgang in einem neuen Regelsatz. Regelstand und Zahlen wie vorher, nichts gelöscht. |

Den Namen tippt ein Mensch aus dem Team ein. „Team“ wird abgelehnt.

## Was der Agent kann

Geprobt (Serie und Zusatzläufe, Belege in `live-proben.csv` und `live-ruecknahme.md`):
- **Zählung ändern:** Stichtag statt ganzes Monat, Alter am Monatsersten, Geburtsmonat 13, Plausibilitätsgrenze des Alters.
- **Ausschließen:** Kategorie, Bundesland, Geschlecht, ÖNACE-Abschnitt, Altersspanne, auch zwei zugleich („Beamte und Kinder unter 15“).
- **Zusammenlegen:** Bundesländer, Kategorien.
- **Prüfschwellen:** ab wann ein Monat angehalten wird.
- **Lockere Schreibweise:** Kleinschreibung, fehlende Satzzeichen, Tippfehler.

Nicht geprobt, kann klappen: ÖNACE-Abschnitte oder Geschlecht zusammenlegen.

**Nicht vorführen:** Prüfschwellen je Bundesland oder andere Regeln, die es nicht gibt. „Schon angehalten, wenn in einem Bundesland mehr als 10 % fehlen“ wurde in der Probe zu einem falschen Vorschlag (P16 von 1 % auf 10 %, also unempfindlicher, ohne Bundesland). Darum vor jeder Freigabe den Unterschied lesen: Das Programm prüft, ob ein Vorschlag gültig ist, nicht, ob er die Anweisung trifft.

## Welcher Probemonat

- **Standard ist der jüngste gerechnete Monat (Juli 2026), das passt fast immer.**
- **Geburtsmonat 13:** Einen Monat von Jänner bis Juni wählen, zum Beispiel Juni 2026. Der Ersatztag 1. Juli ist bei Alter am Monatsletzten ab Juli vorbei, darum ändert sich von Juli bis Dezember keine Zahl. Das ist richtig, wirkt aber wie „nichts passiert“.
- **Prüfschwellen:** Die Probe zeigt keine Änderung, das ist richtig: Eine Prüfregel ändert keine Zahl. Sie zeigt auch nicht, ob ein Monat angehalten würde.
- **März und Oktober 2025** enthalten Fortschreibungen. Die Probe dauert dort länger (gemessen 116 bis 180 s) und stimmt erst seit dem Fix in !150.

## Wenn etwas anders läuft

- **Rückfrage statt Vorschlag:** Ist gewollt, wenn der Auftrag mehrdeutig ist. Frage beantworten und den ganzen Auftrag genauer neu stellen; ein Gespräch über mehrere Runden gibt es nicht.
- **„Kein Vorschlag: …“:** Das Programm hat den Vorschlag auch nach zwei Korrekturen nicht angenommen. Nichts hat sich geändert. Auftrag anders formulieren.
- **„freigegeben, nicht angewendet“:** Die Freigabe gilt, das Anwenden wurde unterbrochen (kam in der Probe nur bei Verbindungsverlust vor). Das Anwenden lässt sich wiederholen.
- **Neue Regel-Art nötig:** Ein Auftrag jenseits der Liste oben wird als „Entwicklungsauftrag“ oder Rückfrage beantwortet. Das offen sagen, nicht umgehen.

## Was noch nicht geht

- `/uc3/freigaben` zeigt eine Rücknahme einer neuen Regel noch falsch („Keine Regeländerung hinterlegt.“, #168). Rücknahme darum im Terminal zeigen, bis #168 gemergt ist.
- Sheet und Qualitätsbericht für einen Regelsatz mit Ausschluss oder Gruppierung: #169. Live nur die Probe zeigen, kein Sheet erzeugen.
- Ein ÖNACE-Buchstabe kann vor und ab 01/2025 etwas anderes bedeuten (O: 2008 Öffentliche Verwaltung, 2025 sonstige wirtschaftliche Dienstleistungen). Die Probe zeigt einen einzelnen Monat; über die Zeitreihe ist das eine Falle (#169).
- Auf einer frisch aufgesetzten DB ist die Live-Änderung nicht geprobt; die Sichtprüfung misst das nach dem Merge.
