# StatAgent (Use Case 3): Beschäftigtenstatistik im Monatsbetrieb

Python-Paket `statagent`. Es liest die 24 Monatslieferungen ein, bereinigt sie nach Regeln aus der Datenbank,
zählt den Bestand am Stichtag, prüft jede Lieferung und schreibt je Monat einen Qualitätsbericht und eine Spalte im
Aggregations-Sheet. **Die KI schreibt Code, das Programm rechnet:** Kein Befehl hier ruft ein Sprachmodell auf.
Zwei Läufe mit denselben Daten und Regeln liefern denselben Ergebnis-Hash.

## Voraussetzungen

- Python **3.12** oder neuer, [uv](https://docs.astral.sh/uv/) 0.12 oder neuer
- PostgreSQL **16** mit den Daten des Startpakets (`roh.lieferung`, `klassifikation.*`), Port **5433**:
  im Startpaket `DB_PORT=5433 docker compose up -d`, warten bis `docker logs statagent-db` „fertig“ meldet
- Startpaket-Ordner (Beispielbericht, Vorlagen) unter `../svbox/uc3` neben dem Repo oder über `STATAGENT_STARTPAKET`

Konfiguration über Umgebung oder `.env.local` an der Repo-Wurzel (Beispiel: `.env.example`):

| Variable | Standard | Bedeutung |
|---|---|---|
| `UC3_DATABASE_URL` | `postgresql://statistik:statistik@localhost:5433/statistik` | Datenbank |
| `STATAGENT_STARTPAKET` | `../svbox/uc3` | Ordner des Startpakets (wird nicht ins Repo kopiert) |
| `STATAGENT_ABGABE` | `abgabe/` | Ablage der Ergebnisse |

## In fünf Befehlen zum Ergebnis

```bash
uv sync --all-packages                      # an der Repo-Wurzel
uv run uc3 db init                          # Schemas, Klassifikationen, Regelsatz v1 (idempotent, löscht nichts)
uv run uc3 lauf --alle                      # 24 Einzelläufe 2024-08 … 2026-07, in zeitlicher Reihenfolge
uv run uc3 eichen --lieferung 2024-08       # Beispielbericht Tab1–Tab13: „Zellen 2880, abweichend 0“
uv run uc3 berichte --alle && uv run uc3 sheet   # 24 Qualitätsberichte und Aggregations-Sheet nach abgabe/
```

`uv run statagent …` ist gleichwertig zu `uv run uc3 …`. Jeder Befehl hat `--help`, viele `--json`.

## Befehle

| Befehl | Was er tut |
|---|---|
| `db init` / `db pruefen` | Schema anlegen; Ladeprotokoll gegen `roh.lieferung` (und mit `--startpaket` gegen die CSV) prüfen |
| `regeln zeigen` / `regeln export` | Regeln als Daten mit Parametern, Begründung, Grundlage und Freigabe |
| `regeln freigeben --name "Vorname Nachname"` | gibt offene Regeln mit Namen und Zeitpunkt frei („Team“ wird abgelehnt) |
| `lauf --lieferung JJJJ-MM` | ein Produktionslauf: genau eine Lieferung, nur eigene und frühere Lieferungen |
| `laeufe` | Läufe mit Status, Abrechnung und Ergebnis-Hash; für den Hash-Vergleich `laeufe --json` (voller Hash, die Textausgabe kürzt auf 12 Zeichen) |
| `eichen` | Zellvergleich gegen `beispielbericht_2024-08.xlsx` |
| `veroeffentlichen --lieferung JJJJ-MM --name "…"` | gibt einen Monat frei: vorläufig → endgültig, danach unveränderlich |
| `berichte`, `sheet`, `pruefe-abgabe` | Qualitätsberichte, Aggregations-Sheet, Prüfung der Abgabedateien |
| `ministerium --monat JJJJ-MM --name "…"` | Ministeriums-Lieferung (Auftrag 3): prüft die Definition gegen Annahme A13 (Altcodes wie Regel Q01, angehaltene Lieferungen überspringen), schreibt die CSV außerhalb jedes Git-Repos und gibt den Beleg (sha256, Zeilenzahl) unter `abgabe/` mit Namen frei; Ausgabe mit beiden Parametern und Zeilenzahl |
| `protokoll` | Protokoll aller Änderungen: Git-Commits mit `Freigegeben-von`, Regelfreigaben, veröffentlichte Monate |
| `klass [begriff] [code] [--version V] [--unterklassen N]` | erklärt eine Klassifikation (oenace, region, qualifikation, beschaeftigungskategorie, geschlecht, alter): Versionen mit Codes; mit Code Bezeichnung je Version, Übergänge aus `stat.uebergang` (ÖNACE 2008 zu 2025 lädt `db init` aus dem Umsteiger des Startpakets), Quellzuordnungen und Verhältnisse im letzten veröffentlichten Monat mit SQL |
| `export-online --ziel datei.sql [--pg-dump "…"] [--rolle kic_app]` | Plain-SQL-Dump nur von `stat` und `meta` (nie `roh`, `bereinigt`; sonst wird die Datei gelöscht) mit Leserechten für die Rolle, einspielbar in PostgreSQL 16; Ausgabe Pfad, Größe, Tabellen je Schema, sha256 |

Der Ergebnis-Hash eines Laufs ist SHA-256 über alle Zellen des Monats: je Zelle eine Zeile
`zeitraum_art|zeitraum_von|zeitraum_bis|region|oenace|oenace_version|geschlecht|qualifikation|alter|variable|wert`,
sortiert (Sortierfolge `C`) und mit Zeilenumbruch verbunden. Zwei Läufe mit denselben Daten und Regeln ergeben
denselben Hash.

## Wie ein Lauf rechnet

1. **Bereinigen** (`bereinigt.abschnitt`): Spaltentausch BEGINN/ENDE erkennen, Volldubletten verdichten, Daten
   prüfen (Geburtsmonat 13 behält das Jahr, Ersatztag 1. Juli), Merkmale über `stat.quellzuordnung` auf Klassifikationscodes führen
   (leer → unbekannt, ÖNACE-2003-Unterabschnitte DA–DN → C). Kein Satz geht verloren.
2. **Zählen** (`stat.stat_beschaeftigte`, Long-Format nach Anhang B): Verhältnis zählt, wenn ein Abschnitt am
   Stichtag besteht; Merkmale aus diesem Abschnitt; Alter in vollendeten Jahren am Stichtag; bei Geburtsmonat 13 gilt der 1. Juli als Geburtstag, über 110 Jahre als unbekannt.
3. **Revisionsbedarf**: die zwei Vormonate aus der eigenen Lieferung nachrechnen und mit dem Veröffentlichten
   vergleichen (Nachmeldungen, rückwirkende Abmeldungen, nicht mehr enthalten).
4. **Prüfen** (Prüfkatalog P01–P24 in `meta.regel`): Auffälligkeiten mit Einstufung erklärt-plausibel,
   erklärt-Datenproblem oder nicht erklärbar; Teil-Lieferungen halten den Monat an.
5. **Abrechnen**: gelesene Sätze = gezählt + nicht gezählt + ausgeschlossen, sonst Abbruch.

Ein Lauf schreibt **vorläufig**. Endgültig wird ein Monat erst, wenn alle Regeln mit Namen freigegeben sind und
eine Person ihn mit `veroeffentlichen` freigibt. Veröffentlichte Zeilen schützt ein Trigger gegen jede Änderung.

## Regeln als Daten

Alle Werte, die eine Zahl beeinflussen, stehen in der Datenbank: `meta.regel` (Einlese-, Zuordnungs-, Zähl- und
Prüfregeln mit Parametern, Gültigkeit, Begründung, Freigabe), `stat.quellzuordnung`, `stat.klass_*`,
`stat.uebergang`. Der Code kennt nur die Regel-Arten. Snapshot: `docs/plan/uc3/regeln-v1.csv`. Begründete Annahmen
mit Beleg-SQL: `docs/plan/uc3/annahmen.md`; offene Rückfragen an die Fachabteilung: `meta.rueckfrage`.

## Tests

```bash
uv run pytest -q -m "not daten" uc3/tests   # Fixture-Lieferungen mit allen Fallen, Wegwerf-Datenbank je Testlauf
uv run pytest -q -m daten uc3/tests         # gegen die echten Daten: Golden Set 2.880 Zellen, Prüfkatalog-Sollwerte
```

## Grenzen

- Daten sind synthetisch (Startpaket des Veranstalters) und liegen nicht im Repo.
- Für Berichtsmonate vor Juli hängt das Alter bei Geburtsmonat 13 von der Antwort auf Rückfrage R1 ab.
