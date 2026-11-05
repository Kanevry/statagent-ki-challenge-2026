# Feature: E5 Präsentation & Jury (Epic #26)

**Date:** 2026-11-05
**Author:** Bernhard Götzendorfer + Claude (AI-assisted planning, Steuerung: autonomous)
**Status:** umgesetzt als 11 Folien, gültig ist `storyboard.md` (Zeiten, Folien, Bilder) und `belegregister.md` (Zahlen). Abweichungen zum Storyboard unten: Folie 6 zeigt den Spaltentausch 2025-06 statt der Revision, die Revision steht auf Folie 9; Feature-Stopp ist Fr 07:00.
**Appetite:** 1 Tag (Do 05.11. nachmittags bis Fr 06.11. 08:30, Feature-Stopp Fr 07:00)
**Parent Project:** StatAgent, KI Challenge 2026, Use Case 3

## 1. Problem & Motivation

### What
Eine 10-Minuten-Präsentation (Slides in Pen plus Live-Demo), ein Fachjury-Skript für den Tisch, ein Fragenkatalog,
eine 5-Minuten-Fassung für das Finale und ein Backup-Video. Alles in `docs/praesentation/` (Text) und in der Pen-Datei
`design/ki-challenge.pen` (Slide-Frames, eigener Bereich ab y = 4400, bestehende StatAgent-Frames ab x = 4800 unberührt).

### Why
Die Fachjury sitzt Fr 09:00 bis 11:30 je 15 Minuten am Tisch und erwartet laut Aufgabenstellung: Präsentation (Lösung,
gefundene Fehler, eine Annahme im Detail), eine unbekannte Live-Änderung per Sprache mit Protokoll und Zahlen
vorher/nachher sowie Datenanfragen (Zeitreihe, Männer/Frauen, Fluktuation je Branche). Bewertet werden 6 × 20 = 120
Punkte (Datenmanagement, Klassifikation, Qualitätssicherung, Reporting, Weiterentwicklung und Betrieb, Bedienbarkeit).
Owner: „Die Präsentation in 10 min muss wirklich knackig sein und alles abdecken, was in den Dokumenten definiert ist.
Am besten sobald wie möglich in Pen die Slides umsetzen.“

### Who
Vortragender: Bernhard Götzendorfer (Team OneShotAndy, eine Person). Publikum 1: Fachjury aus Statistik/BI der
Sozialversicherung am Tisch. Publikum 2 (Finale, falls Top 3): Manager-Gremium plus Publikum, weniger Technik, mehr
Anwendung und Verantwortung.

### Evidence Baseline
| Claim | Quelle / Befehl | Ergebnis | Gemessen |
|-------|-----------------|----------|----------|
| Fachjury 15 min: Präsentation, Live-Änderung, Datenanfragen; Abgabe Fr 09:00 | Vault `vor-ort-05-11.md` § 1 und § 5 (Blätter und `Use Case 3 StatAgent.docx`) | bestätigt | 2026-11-05 10:40 |
| Golden Set 08/2024 wird exakt reproduziert | Lead-Gegenrechnung `ki-challenge-goldenset-2024-08.md` § 3 (`compare.py` gegen `beispielbericht_2024-08.xlsx`) | 2.880 / 2.880 Zellen, 0 Abweichungen | 2026-11-05 auf einer separaten Datenbankinstanz |
| Gefundene Datenfehler (Monat 13, Alter > 74, ÖNACE 2003, BL/ÖNACE leer, Dubletten 2025-03, FD fehlen 2025-03, Teil-Lieferung 2025-10, Revision 12/2024) | dieselbe Datei § 2, § 4, § 7 bis § 9, SQL je Befund | Zahlen siehe Storyboard S6 | 2026-11-05 |
| Pen-Datei hat freien Bereich unter y = 3900 | Pencil-MCP `Get(document, depth 0)` | tiefster Frame endet bei y = 3900 (S7 · Protokoll); Story-Frame endet bei y = 3854 | 2026-11-05 |
| Design-Entscheide: Richtung B „Kontrollraum“, B1 Lichtkarte, Gelb = Warnfarbe, Mint = Beleg, Name „StatAgent by Bernhard Götzendorfer“ | Vault `show-und-design.md` § 8 (Owner-Entscheide 05.11. 09:45) und Pen-Variablen (`night`, `ink`, `mint`, `ki-violett`, `warn`, `beleg`, `font-head` Space Grotesk, `font-body` Inter, `font-mono` JetBrains Mono) | bestätigt | 2026-11-05 |
| Web-UI, Agent-Laufzeit, 24 Läufe stehen am Fr für die Demo | Issues #14 bis #18 (status::in-progress) | **Hypothese**, hängt an E1 | 2026-11-05 11:15 |

## 2. Solution & Scope

### Dramaturgie (Leitmotiv Hochrisikodaten → Vertrauen → Glaubwürdigkeit)
Spannungsbogen in drei Akten: **Akt 1 Vertrauen behaupten** (Problem, drei Schritte, Stack), **Akt 2 Vertrauen beweisen**
(Golden Set, gefundene Fehler, eine Annahme im Detail, Live-Demo), **Akt 3 Vertrauen begrenzen** (Grenzen, Rückfragen,
ein Kern für drei Use Cases, Schluss). Jede Zahl auf einer Folie stammt aus der Gegenrechnung des Leads oder aus einem
Lauf der Pipeline; keine Zahl ohne Messung, keine Zeitersparnis-Behauptung („Minuten statt Tagen“ bleibt draußen, bis
der Use-Case-Owner einen Wert nennt). Nie mit Personalabbau argumentieren. Keine SV-Logos, Träger nur als Text.

### Storyboard 10 Minuten (12 Folien, 16:9, 1920 × 1080, dunkle Bühne)

| # | Zeit | Folie (Layout) | Kernaussage / Inhalt | Bewertungsbereich |
|---|------|----------------|----------------------|-------------------|
| S1 | 0:00–0:30 | Cover (L02, Lichtpunkte-Hintergrund) | **StatAgent by Bernhard Götzendorfer.** „Die KI schreibt Code. Das Programm rechnet. Der Mensch gibt frei.“ Team OneShotAndy, Use Case 3 | alle |
| S2 | 0:30–1:15 | Problem (L05) | Für wen: das Statistik-Team des Dachverbands. Was: 24 Monatslieferungen, rund 10 Mio. Zeilen, Hochrisikodaten (Beschäftigte, Geburtsdaten). Risiko: eine falsche Zahl in einer Veröffentlichung. Leitmotiv Hochrisikodaten → Vertrauen → Glaubwürdigkeit | 1, 3 |
| S3 | 1:15–2:00 | Drei Schritte (L13) | 1 Lieferung einlesen und prüfen (versioniert, nichts gelöscht). 2 Regeln als Daten in `meta.regel`, das Programm rechnet, deterministisch. 3 Mensch gibt frei: Name, Zeitpunkt, Commit-Trailer | 1, 5 |
| S4 | 2:00–2:45 | Stack nachvollziehbar (L05, Diagramm) | PostgreSQL 16 (`roh.lieferung`, `klassifikation.*`, `meta.regel`) → Python `statagent` CLI (`lauf --lieferung`, `freigabe --name`) → Next.js (lesend). Agenten: Azure gpt-5-4-mini, `LLM_PROVIDER` austauschbar (azure, mistral, ollama, mock), keine Einzeldaten ans Modell | 5, 6 |
| S5 | 2:45–3:15 | Beleg (L09, eine Zahl) | **2.880 von 2.880** Zellen des Beispielberichts 08/2024 exakt reproduziert, 0 Abweichungen. Brücke: 392.284 Zeilen − 48 (Ende vor Stichtag) = 392.236 | 3, 4 |
| S6 | 3:15–4:15 | Gefundene Fehler (Fallen-Tafel, Gelb) | 8 Befunde mit Zahl, Lieferung, Einstufung: Monat 13 (370, erklärt-plausibel), Alter 117–153 J. (7, erklärt-Datenproblem), ÖNACE 2003 DA–DM (50, erklärt-plausibel), BL + ÖNACE leer (1.996, immer gemeinsam), Volldubletten 2025-03 (1.663 Zeilen, 1.523 doppelt am Stichtag), freie Dienstverträge fehlen 2025-03 (1.492, nicht erklärbar → Rückfrage), Teil-Lieferung 2025-10 (−20 %, 78.949 fehlen, 78.733 in 11/2025 wieder da), Revisionsbedarf 12/2024 (−260, −0,067 %) | 1, 3 |
| S7 | 4:15–5:00 | Eine Annahme im Detail (L08/L17) | Geburtsmonat 13: vier Varianten A–D gegen Tab13 getestet, nur D (Alter = Berichtsjahr − Geburtsjahr, Alter ≥ 75 = unbekannt) trifft 0 Abweichungen. Offen: 1.1. oder 1.7. als Ersatztag, ab 09/2024 verschieden. Rückfrage R1 an die Fachabteilung gestellt. Regel R6/R7 liegt als Daten in der DB, mit Begründung und Freigabe | 3, 5 |
| S8 | 5:00–5:15 | Demo-Überleitung (L04) | „Live: ein Lauf, ein Qualitätsbericht, eine Änderung per Sprache, eine Datenanfrage.“ Danach Wechsel zur Web-UI | 5, 6 |
| Demo | 5:15–8:45 | Live (Web-UI, Fallback CLI, Fallback Video) | D1 Lauf 2025-03 starten, Qualitätsbericht öffnen: Dubletten und fehlende FD als Auffälligkeit mit Einstufung. D2 Änderungsauftrag per Sprache (vorbereitet, klein): Vorschlag → Diff → Freigabe mit Name → Commit mit `Freigegeben-von`, Zahlen vorher/nachher. D3 Datenanfrage Männer/Frauen je Bundesland mit sichtbarer SQL. UC-Wechsel im Header einmal zeigen (UC1/UC2 als Ausblick) | 4, 5, 6 |
| S9 | 8:45–9:15 | Grenzen & Verantwortung (L19) | Nichts wird gelöscht, Veröffentlichtes bleibt, Abweichungen stehen als Revisionsbedarf. Modell sieht Regeln und Schemata, keine Einzeldaten. Offene Rückfragen R1–R5 an die Fachabteilung. Was nicht gelöst ist (Stand Fr früh eintragen) | 1, 3 |
| S10 | 9:15–9:40 | Ein Kern, drei Use Cases (L07) | Belegschicht, Freigabeprotokoll, Modell-Schalter tragen UC1 (Lotse) und UC2 (Simulator) im selben Dashboard. Bewertet wird UC3; der Rest ist Ausblick, ein Satz | 5, 6 |
| S11 | 9:40–10:00 | Schluss (L20) | „Jede Zahl nachrechenbar. Jede Änderung freigegeben.“ GitHub `KIChallenge/OneShotAndy`, Abgabe im SV-Box-Teamordner | alle |
| A1 | Anhang | Kriterien-Karte (Tabelle) | 6 Bereiche × Beleg × Fundstelle im Repo; liegt ausgedruckt am Tisch | alle |
| A2 | Anhang | Prüfkatalog und Regeln | Prüfregeln P01–P24 (Stand Fr), Regelversionen mit Gültigkeit | 3 |
| A3 | Anhang | Finale 5 min | Reihenfolge S1, S2, S3, S5, S6 (gekürzt), S11 plus Verantwortung in drei Sätzen; keine Technikfolie als Schluss | Finale |

### In-Scope
- [ ] Storyboard und Sprechtext je Folie als Markdown (`docs/praesentation/skript-fachjury.md`), mit Stoppuhr-Marken
- [ ] 12 Slide-Frames plus 3 Anhangs-Frames in Pen (Bereich y ≥ 4400, Design Kontrollraum, Tokens aus der Datei), PDF-Export nach `docs/praesentation/export/` (nicht ins öffentliche Repo, `.gitignore`)
- [ ] Demo-Drehbuch D1–D3 mit drei Fallback-Stufen (Web-UI → CLI → Video) und Vorbereitungs-Checkliste (`docs/praesentation/demo-drehbuch.md`)
- [ ] Fragenkatalog der Fachjury mit Kurzantworten und Fundstelle: Datenanfragen (Zeitreihe, M/F, Fluktuation je Branche), Live-Änderung, Methode, Datenschutz/Hochrisiko, Determinismus, Modellwahl (`docs/praesentation/fragenkatalog.md`)
- [ ] Finale-Fassung 5 min (Reihenfolge, Sprechtext) in derselben Skript-Datei
- [ ] Backup-Video der Demo per `browser-kit record` (Fr früh, nach Feature-Stopp 07:00), Ablage lokal, Pfad im Drehbuch
- [ ] Probelauf mit Stoppuhr ≤ 10 min, Jury-Simulation durch den Lead (Abnahme)

### Out-of-Scope
- Bauen der Web-UI, der Agent-Laufzeit oder der Läufe (E0 #21, E1 #22): die Präsentation zeigt, was steht
- Abgabe-Dateien, README, GitHub-Push (E6 #27)
- SV-Logos, nachgebaute CD-Formen, Zeitersparnis-Zahlen ohne Quelle, Personalabbau-Argumente
- Animierte 3D-Lichtkarte im Deck: Lichtpunkte nur als statischer Hintergrund (Zeit)

### First Real Use / Kill
Erster Probelauf mit Stoppuhr Do 05.11. ab 20:00 mit dem Stand der Slides; zweiter Probelauf Fr 06.11. 07:30 mit
Demo und Video. Fehlt Fr 07:30 die Web-UI, läuft die Demo per CLI (Fallback 2) und das Skript wird angepasst, kein
stilles Hoffen.

## 3. Acceptance Criteria

### Slides in Pen
```gherkin
Given die Pen-Datei design/ki-challenge.pen mit den StatAgent-Frames ab x = 4800
When die 15 Slide-Frames im Bereich y ≥ 4400 angelegt sind
Then überlappt kein neuer Frame einen bestehenden, jede Folie ist 1920 × 1080, Fließtext ≥ 24 px, Titel ≥ 40 px,
  und jede Zahl auf einer Folie steht mit Quelle in der Evidence Baseline oder im Skript
```
Oracle: Pencil-MCP `Get(document, depth 0)` zeigt keine Überlappung mit den Frames vor y = 3900; `TakeScreenshot` je Folie; Lead liest die Zahlen gegen `ki-challenge-goldenset-2024-08.md`.

### Skript und Zeit
```gherkin
Given das Skript skript-fachjury.md mit Stoppuhr-Marken je Folie
When Bernhard Götzendorfer den Vortrag laut mit Stoppuhr hält
Then dauert er höchstens 10:00 min inklusive Demo, und alle Pflichtinhalte der Aufgabenstellung sind abgedeckt
  (Lösung, Stack, Herausforderungen, gefundene Fehler, eine Annahme im Detail)
```
Oracle: Stoppuhr-Zeit im Probelauf, vom Lead als Jury-Simulation protokolliert (Kommentar im Epic #26).

### Demo mit Fallback
```gherkin
Given das Demo-Drehbuch mit Stufen Web-UI, CLI, Video
When Netz, Azure oder Web-UI ausfallen
Then zeigt die nächste Stufe denselben Inhalt (Lauf, Qualitätsbericht, Änderung mit Freigabe, Datenanfrage) ohne Umbau
```
Oracle: Backup-Video liegt lokal, Abspieltest ohne Netz; CLI-Befehle aus dem Drehbuch laufen mit `LLM_PROVIDER=mock`.

### Fragenkatalog
```gherkin
Given die drei Datenanfragen der Aufgabenstellung (Zeitreihe, Männer/Frauen, Fluktuation je Branche)
When die Jury eine davon stellt
Then liefert der Katalog Antwortweg, SQL-Skizze und Fundstelle im Repo in unter 30 s Lesezeit
```
Oracle: Lead stellt in der Jury-Simulation drei Fragen aus dem Katalog und eine außerhalb.

### External Acceptance
| Criterion | Oracle | Owner | Not before | Pass condition | Fallback if it cannot run |
|-----------|--------|-------|------------|----------------|---------------------------|
| Probelauf ≤ 10 min und Jury-Simulation | Stoppuhr, Lead-Protokoll | lead-session-orchestrator-09 | 2026-11-05 20:00 | ≤ 10:00, keine Pflichtlücke | Owner hält den Probelauf allein und notiert Zeit |
| Backup-Video der Demo | Abspieltest offline | Owner | 2026-11-06 07:00 | Video zeigt D1–D3 | Screenshots der Web-UI als Bildfolge im Deck |

## 4. Technical Notes

### Affected Files
- `docs/praesentation/2026-11-05-prd-e5-praesentation.md` — dieses Dokument (Storyboard)
- `docs/praesentation/skript-fachjury.md` — Sprechtext mit Zeitmarken, Finale-Fassung
- `docs/praesentation/demo-drehbuch.md` — D1–D3, Fallbacks, Checkliste
- `docs/praesentation/fragenkatalog.md` — Fragen, Kurzantworten, Fundstellen
- `docs/praesentation/kriterien-karte.md` — 120-Punkte-Raster mit Belegen
- `design/ki-challenge.pen` (außerhalb des Abgabe-Repos) — Slide-Frames ab y = 4400

### Architecture
Slides als Top-Level-Frames „P01 · …“ bis „P15 · …“ in Pen, Reihen à 4 Folien (x = 0, 2000, 4000, 6000; y = 4400,
5600, 6800, 8000). Ein wiederverwendbarer Folienkopf (Nummer, Abschnitt, Zeitmarke) als Komponente. Farben nur über
die bestehenden Variablen (`night`, `ink`, `text`, `text-dim`, `mint`/`beleg`, `warn`, `ki-lila`, `ki-violett`).

### Data Model Changes
Keine.

### API Changes
Keine.

## 5. Risks & Dependencies

| Risk | Impact | Mitigation | Triage |
|------|--------|------------|--------|
| Web-UI oder Agent-Laufzeit stehen Fr 07:00 nicht | Demo zeigt weniger, Bereiche 5 und 6 verlieren Punkte | Drei Fallback-Stufen, Skript mit zwei Varianten; Stand am Do 22:00 und Fr 07:00 prüfen | Implement |
| Zahl auf einer Folie stimmt nach neuem Lauf nicht mehr | Glaubwürdigkeit kippt am Tisch | Alle Zahlen tragen Lieferung und Quelle; Fr 07:30 Abgleich gegen `abgabe/` | Implement |
| Live-Änderung der Jury trifft etwas Ungeübtes | Stocken vor der Jury | Fünf geübte Änderungsaufträge im Katalog, ehrlicher Satz „das setzt der Agent so um, Freigabe folgt“ | Implement |
| Netz und Azure fallen aus | Agent läuft nicht | `LLM_PROVIDER=ollama` oder `mock` als Schalter, Video | Implement |
| Zu viel Inhalt für 10 min | Jury schaltet ab | Eine Aussage je Folie, Details in Anhang und Katalog, Probelauf mit Stoppuhr | Implement |
| Pen-Export oder Beamer-Format | Folien unscharf | PDF-Export 1920 × 1080, Test am Do abend | Defer bis Probelauf |

### Dependencies
- Epic E1 #22 (Pipeline, Agenten, Läufe): Demo-Inhalt, Zahlen Fr früh
- Epic E0 #21 (Dashboard, UC-Wechsel): Demo-Bühne, Folie S10
- Epic E6 #27 (Abgabe): Repo-Link auf S11, README-Fundstellen in der Kriterien-Karte
- Lead-Gegenrechnung `ki-challenge-goldenset-2024-08.md`: Quelle aller Fehler-Zahlen
