---
id: ki-challenge-vor-ort-05-11
type: note
title: "KI Challenge 2026: Vor-Ort-Lage am Do 05.11. (Programm, Räume, Netz, SV-Box-Inventar, offizielle Use-Case-Texte, Empfehlung)"
status: active
created: 2026-11-05
updated: 2026-11-05
tags:
  - business/career
  - area/career
  - project/hackathons-2026-27
summary: "Um 10:15 am 05.11. aus sechs Fotos der Vor-Ort-Blätter und den vier SV-Box-Shares zusammengetragen: Zeitplan mit Räumen, WLAN und Telefonnummern, die offiziellen Use-Case-Dokumente (UC1 KI-Lotse, UC2 HealthPolicy Simulator, UC3 StatAgent mit 120-Punkte-Raster und Abgabe Fr 09:00), das Veranstalter-Modell (Azure AI Foundry, gpt-5-4-mini) und das vollständige Inventar der SV-Box (UC1 80 MB mit 14.244 SozDok-XML, UC2 1,3 GB Pressespiegel, UC3 140 MB Startpaket mit 24 Lieferungen und PostgreSQL). Empfehlung: UC3, und zwar allein, ohne die Drei-Räume-Idee. Zugänge liegen in app/.env.local."
tier: active
---

# Vor-Ort-Lage Do 05.11., Stand 10:40

> Quellen: sechs Fotos der ausgeteilten Blätter (Kopie unter `~/Projects/ki-challenge-2026/svbox/vorort-fotos/`), die
> vier SV-Box-Shares (vollständig geladen nach `~/Projects/ki-challenge-2026/svbox/`, Inventar in `svbox/inventar/*.tsv`),
> die Use-Case-Dokumente im Share „Allgemeine Informationen“. Zugangsdaten (SV-Box, WLAN, Azure-Endpunkt, Telefon)
> stehen in `~/Projects/ki-challenge-2026/app/.env.local` (Schlüsselnamen `SVBOX_*`, `WLAN*`, `AZURE_*`, `KI_CHALLENGE_*`).
> Dieser Stand ersetzt § 1, 3, 6 und 8 des [Spielplans](spielplan.md), wo er abweicht.

## 1. Programm und Räume (Blatt „Programm“ und „Vorort Information“)

| Tag | Zeit | Was | Raum |
|---|---|---|---|
| Do | ab 10:00 | Eintreffen, Anmeldung | Registration/Help Desk, 1. Stock bei den Stiegen |
| Do | 11:00 | Eröffnung, Vorstellung der Use Cases | 1.69 bzw. 1.70 (Working Area, großer Raum) |
| Do | 12:00 | Offizieller Start | |
| Do | 16:00 | **Frist: Mail an ki-challenge@sozialversicherung.at für den Team-Ordner auf der SV-Box (nur UC3)** | |
| Do | 17:00 | Fragestunde | 1.68 (Final Event) |
| Do | ca. 18:00 (Blatt) bzw. ca. 20:00 (PDF) | Pizza | Vorraum 1.31 (Partnerbörse) |
| Fr | **09:00** | **Abgabe UC3** (Aggregations-Sheet, 24 Qualitätsberichte, Ministeriums-Lieferung, Protokoll, Modellangabe) | SV-Box-Teamordner |
| Fr | 09:00 bis 11:30 | Fachjury am Platz, etwa 15 Minuten je Team | beim eigenen Platz |
| Fr | 12:00 bis 12:45 | Finale der drei Erstgereihten | 1.68 |
| Fr | 12:45 bis 13:15 | Jury berät, Fachvortrag Barbara Oberrauter-Zabransky „KI im Gesundheits- und Sozialversicherungsbereich“ | 1.68 |
| Fr | 13:15 | Siegerehrung | 1.68 |

Räume für Teams: 1.32, 1.34, 1.35, 1.36, 1.37, 1.39, 1.41 (kleine Working Areas, Reihe links der Stiegen), dazu die großen
1.69/1.70 (Working Area) und 1.68 (Fragestunde, Finale). Food & Drinks als langer Streifen neben 1.69/1.70. Nur
gekennzeichnete Räume nutzen. Fluchtpläne für 1.41, 1.68, 1.69 liegen im Share. Rauchen nur im Innenhof, Alkoholverbot,
Fenster zu, Portier im Erdgeschoß durchgehend besetzt. Verpflegung: Mittag Do, Pizza Do abend, Frühstück und Mittag Fr,
Kaffee durchgehend, Getränke im Kühlschrank beim Essensbereich.

Kommunikation: Signal-Gruppe des Veranstalters (Teamkapitän gibt bei der Anmeldung die Handynummer an; Nummern werden
danach gelöscht). Helpdesk und Portier als Anlaufstellen. Telefon tagsüber und nachts: siehe `.env.local`.
Teams, die Mitglieder suchen, melden sich beim Helpdesk.

## 2. Netz

- Gäste-WLAN `99_Gast`: Registrierung als Gastnutzer mit Handynummer über den Link „Für Gast Zugang registrieren“ unten auf der Anmeldeseite.
- Zwei mobile Router `WLANZone` und `WLAN_VA` (Passwörter in `.env.local`). Hotspot als dritter Weg.

## 3. Veranstalter-Modell: Azure AI Foundry

Aus `Beispiel Verbindung API KEY.docx`: OpenAI-kompatibler Endpunkt
`https://aif-dvsv-dev-hackathon-01-we-01.services.ai.azure.com/openai/v1`, Deployment `gpt-5-4-mini`, Beispiel mit
`chat/completions` (`max_completion_tokens`, `reasoning_effort: medium`) und mit dem Python-SDK `openai` über
`client.responses.create`. Region laut Hostname West Europe („we-01“). **Den Schlüssel gibt es bei der Anmeldung**; er
gehört in `.env.local` als `AZURE_API_KEY`, nie ins Repo. UC3 schreibt vor: „Für die Agenten verwendet ihr die
bereitgestellten Modelle am Azure-Endpunkt. Das Modell muss austauschbar sein.“ Mistral bleibt der Schalter dahinter.

## 4. SV-Box: was wo liegt

Nextcloud. WebDAV `https://dvsv.svbox.at/public.php/webdav/` mit Basic-Auth `Token:Passwort` funktioniert ohne Browser;
Skripte `scripts/svbox-list.py` (Inventar) und `scripts/svbox-fetch.py` (Download mit Größenabgleich).

| Share | Inhalt | Größe |
|---|---|---|
| Allgemein | Teilnahmeinformationen, Teilnahmebedingungen (2 Fassungen), DSGVO-Info, Vorort-Info, API-Key-Beispiel, **die drei Use-Case-Dokumente**, drei Fluchtpläne | 4,4 MB |
| UC1 | `Anträge und Formulare/` (7 PDF: Kur/Reha, Fahrtkosten Wien, FSW-Anträge, Pflegegeld PAL080, Reha nach Unfall), `Befunde/` (5 anonymisierte ELGA-Befunde: Entlassungsbefund, Röntgen x2, Bildgebung, Impfpass), `Leistungskataloge/` (ÖGK-Honorarordnung, Zahnärzte-Honorarordnung, Serviceratgeber 2026), `Medikamenten Erstattungskodex/` (EKO als Festbreiten-TXT: medikament, atccode, indtext, regeltext), `Rechtstexte/` **14.244 SozDok-XML** aus 813 Rechtsquellen (ASVG 1.218, E-MVB 610, BSVG 576, GSVG 543, B-KUVG 383, DO.A/B/C, FLAG, AlVG, BPGG, KBGG, Satzungen, Krankenordnungen, EU-Koordinierung); ein XML je Paragraph und Fassung mit Metadaten (Gesetz, Art, Nummer, BGBl, Inkrafttreten) und `<nutzdaten>`-Text | 80 MB |
| UC2 | `Presse/` Pressespiegel des Dachverbands als Tages-PDF (2026 Jänner bis September je Monat ca. 20 PDF à 1 bis 10 MB, dazu Ordner 2008-2019, 2020-2023, 2024, 2025), `Rechtstexte/` dieselben SozDok-XML wie UC1 (plus 68 Dateien Differenz) | 1,3 GB |
| UC3 | Startpaket StatAgent, siehe § 6 | 140 MB |

## 5. Die offiziellen Use-Case-Texte (Kurzfassung, Volltext in `svbox/00-allgemein/text/`)

**UC1 SV KI-Lotse** (`Use Case 1 Versicherten-Chatbot V2.docx`, 15 KB). Kein Chatbot, sondern ein Lotse von der Situation
(„Meine Mutter kommt allein nicht mehr zurecht“) bis zur Inanspruchnahme: Leistung erkennen, Rückfragen nur wenn nötig,
Antrag vorbereiten und vorausfüllen, Unterlagen, zuständige Stelle, Einrichtung, Termin. Personalisierung (Sprache,
einfache Sprache, Detailtiefe, Sprachsteuerung). Dokument-Upload erlaubt (Entlassungsbrief), aber keine Diagnose, keine
Befundinterpretation, keine Therapie- oder Medikamentenempfehlung. Bewertungsszenarien: Pflege, Gesundheitsförderung,
Case Manager nach Spitalsaufenthalt, Kind. Daten: EKO, ELGA-Befunde, SozDok, Honorarordnungen, Formulare; weitere
Quellen ÖGK, Ärztekammer, FSW, SVS, BVAEB, SozDok, gesundheit.gv.at, oesterreich.gv.at. Jury: Eigenständigkeit, flexible
Aufgabenbewältigung, Nutzung und Verknüpfung der Quellen, Verständlichkeit, Qualität der Handlungsschritte, Umgang mit
Unsicherheit und Grenzen, Weg zum Produkt. Finaljury-Kriterien fehlen im Dokument (leere Überschrift).

**UC2 HealthPolicy Simulator** (`Use Case 2 Copilot für strategische Entscheidungen V2.docx`). Multi-Agenten-System mit
institutionellen Agenten (Sozialversicherung, Ministerium, Länder, Ärztekammer, Vertrags- und Wahlärzte, Spitäler,
Pflege, Patienten, Gesetzgeber, Finanzministerium, Public Health, Kammern, Pharma), die eigenständig diskutieren,
verhandeln, Koalitionen bilden und Kompromisse finden; optional Moderator-Agent; spieltheoretischer Modus; Output als
Verhandlungsprotokoll mit Konsens, Mehrheit, Minderheit, offene Konflikte, Auswirkungen. Vorgaben: keine realen Personen
zitieren, Standpunkte aus Pressearchiv nachvollziehbar belegen, Agenten lernen aus Teilergebnissen, Aktuelles wiegt
mehr als Historisches, Zahlen stichhaltig und widerspruchsfrei (eigener „Experte“-Agent). Bewertungsszenario:
„Wartezeiten auf Facharzttermine in fünf Jahren um 20 % senken, ohne mehr als 5 % Mehrausgaben.“ Jury verlangt
**visuelle Darstellung der Verhandlung und der Positionsänderungen**. Daten: Pressearchiv, SozDok.

**UC3 StatAgent** (`Use Case 3 StatAgent.docx`, gleich `StatAgent Aufgabenstellung für die Teams.md` im Paket). Ein
agentengestützter Statistikprozess für eine synthetische Beschäftigtenstatistik (etwa ein Zehntel Österreichs):

- Fünf Schritte: 1 Lieferungen einlesen und prüfen (versionierter Bestand), 2 Klassifikationen historisiert (ÖNACE 2008
  und 2025, Regionen 2011 bis 2026 mit Übergängen), 3 Monatsbetrieb (`lauf --lieferung 2025-03`, je Lauf nur eigene und
  frühere Lieferung, Qualitätsbericht je Monat, Veröffentlichtes bleibt), 4 Reporting (Aggregations-Sheet nach Bundesland,
  Geschlecht, ÖNACE, Beschäftigungskategorie; Datenanfragen mit sichtbarer Abfrage), 5 Weiterentwicklung (drei
  Änderungsaufträge per Sprache an die **eigenen** Agenten, Ministeriums-Lieferung, Pensionsstatistik aus
  trägereigenen Excel-Formaten).
- Datenmodell vorgegeben (Anhang B): `stat_<statistik>` Long-Format, eine Variablentabelle, `klass_<begriff>` mit
  Versionen, Übergänge, Quellzuordnung.
- Acht technische Regeln: KI schreibt Code, Programm rechnet (deterministisch); lokal und offline (PostgreSQL per Docker);
  Regeln als Daten in der DB; Azure-Modelle, austauschbar; eigene Agenten setzen Änderungen um, nicht Claude Code;
  Agenten-Code lesbar, startbar, ohne LLM, freigegeben, protokolliert; **Mensch gibt frei mit Namen und Zeitpunkt**;
  Protokoll je Änderung (Git-Commit mit Anweisung und „Freigegeben-von: Name“ reicht).
- **Bewertung 6 × 20 = 120 Punkte:** Datenmanagement, Klassifikation, Qualitätssicherung, Reporting, Weiterentwicklung und
  Betrieb, Bedienbarkeit (Konsole mindestens, Weboberfläche optimal). Punktabzug, wer Verhältnisse verliert oder echte
  Entwicklungen „korrigiert“.
- **Fachjury 15 Minuten:** Präsentation (Lösung, gefundene Fehler, eine Annahme im Detail), **Live-Änderung per Sprache**
  (unbekannt, mit Protokoll und Zahlen vorher/nachher), Datenanfragen (Zeitreihe, Männer/Frauen, Fluktuation je Branche).
- **Abgabe Fr 09:00** auf dem Team-Ordner der SV-Box: Aggregations-Sheet alt und neu, 24 Qualitätsberichte,
  `ministerium_2026-07.csv`, Protokoll, Modellangabe. **Team-Ordner nur nach Mail bis Do 16:00.**
- Fachabteilung vor Ort beantwortet Rückfragen mit Beleg (Lieferung, Anzahl Sätze, Beispiel-IDs), Vorlage im Paket.

## 6. UC3-Startpaket im Detail (`svbox/uc3/`)

| Teil | Befund |
|---|---|
| `lieferungen/` | 24 × `lieferung_JJJJ-MM.csv.gz`, 08/2024 bis 07/2026, je 345.000 bis 438.000 Zeilen (Vollabzug der letzten drei Monate), Felder `VVH_ID;PERSON_ID;GEBURTSDATUM;GESCHLECHT;BEGINN;ENDE;QUAL;OENACE;BUNDESLAND`, alles Text. Zusammen rund 10 Mio. Zeilen. |
| Erste Fallen (gemessen in 07/2026, erste 400.000 Zeilen) | OENACE leer in 2.015 Sätzen, Bundesland leer in 2.015; ÖNACE-2003-Unterabschnitte `DA`, `DJ`, `DK`, `DD`, `DL`, `DC`, `DF` (je 4 bis 8 Sätze) statt Abschnitt C; Lieferung 10/2025 ist mit 345.079 Zeilen deutlich kleiner als die Nachbarn (Teil-Lieferung oder Ausfall); Klassifikationswechsel 2008 → 2025 ab 01/2025 (Buchstaben verschieben sich: G Handel, J bis V neu belegt). Zu erwarten laut Text: Duplikate, Nachmeldungen, Korrekturen, unplausible Geburtsdaten, Lücken zwischen Zeitabschnitten. |
| `klassifikationen/` | Grundausstattung (Bundesland 0 bis 9, Geschlecht M/W, Qualifikation 5 Codes mit Kategorie und FD-Kennzeichen, ÖNACE 2008 A bis U plus UNB, ÖNACE 2025 A bis V plus UNB); `oenace/` Statistik-Austria-Dateien 2003/2008/2025 bis 5-Steller mit Umsteigern; `regionen/` Gemeinden und Bezirke je Stand 2011 bis 2026 plus amtliche Änderungslisten (ODS, PDF) |
| `datenbank/` + `docker-compose.yml` | PostgreSQL 16, lädt beim ersten Start alle Lieferungen in `roh.lieferung` (Spalte `lieferung` = Berichtsmonat) und Klassifikationen nach `klassifikation.*`, 2 bis 4 Minuten. Port 5432 oder `DB_PORT=5433`. User/PW/DB `statistik`. |
| `pensionen/` | 2018 bis 2025, je Jahr 3 bis 5 kleine XLSX in trägereigenem Format (PVA, VAEB/BVAEB, SVA/SVB/SVS, VAN), Trägerfusion 1.1.2020 |
| `vorlagen/` | `aggregationen_vorlage.xlsx`, `ministerium_vorlage.csv` (Kopf `PERSON_ID;GESCHLECHT;GEBURTSJAHR;TAGE`), `qualitaetsbericht_vorlage.md` (Überblick, Auffälligkeiten mit Einstufung erklärt-plausibel / erklärt-Datenproblem / nicht erklärbar, Rückfragen, Regeln, Revisionsbedarf), `rueckfrage_vorlage.md` |
| `beispielbericht_2024-08.xlsx` | 13 Tabellen im Dachverbands-Layout zum Eichen des ersten Monats |
| README-Hinweise | PostgreSQL 16, Python-Mindestversion nennen, `python3 -u` mit Logdatei, `ANALYZE`, `NOT EXISTS` statt `NOT IN` |

## 7. Was sich gegenüber dem Spielplan ändert

1. **Die Drei-Räume-Idee („Kompass“) ist tot.** Jeder Use Case hat jetzt ein eigenes, dichtes Pflichtenheft; UC3 verlangt
   konkrete Abgabedateien bis Fr 09:00 und eine Live-Änderung. Nebenräume kosten nur Zeit und bringen keine Punkte.
2. **Modell:** Azure `gpt-5-4-mini` ist für UC3-Agenten vorgeschrieben, Mistral nur noch als zweiter Anbieter hinter dem
   Schalter. Die „EU-Souveränität“-Erzählung bleibt, weil Azure West Europe ist.
3. **Stack:** PostgreSQL 16 im Docker statt DuckDB (Vorgabe). Python oder TypeScript für Produktionscode: beides erlaubt,
   Mindestversion dokumentieren. Weboberfläche bleibt Next.js (Bedienbarkeit, 20 Punkte).
4. **Abgabe doppelt:** GitHub-Repo `KIChallenge/OneShotAndy` (Code, README) **und** SV-Box-Teamordner (Ergebnisdateien).
5. **Rechtstexte:** Die 14.244 SozDok-XML sind der RIS-Ersatz für UC1 und schon lokal; für UC3 unerheblich.

## 8. Empfehlung: UC3, allein

| Kriterium | UC1 | UC2 | UC3 |
|---|---|---|---|
| Spezifikation | breit, viele „soll“-Funktionen, Finalkriterien fehlen | breit, Pressespiegel-PDFs müssen erst gelesen werden (1,3 GB), Visualisierung Pflicht | **präzise, 120 Punkte, Abgabedateien, Vorlagen, Beispielbericht zum Eichen** |
| Messbarkeit für uns | Golden Set selbst bauen | kaum objektiv | **Zahlen gegen Beispielbericht 08/2024, Fehlerliste, Determinismus** |
| Konkurrenz (Vermutung) | am vollsten | mittel | gering, weil arbeitsintensiv und „unsexy“ |
| Passt zur Flotte | mittel | mittel | **sehr gut: Datenpipeline, Regeln als Daten, Protokoll, Agenten mit Freigabe sind genau unser Betriebsmodell** |
| Risiko | Halluzination, Breite | Breite, Zahlen ohne Beleg | Menge: 10 Mio. Zeilen, 24 Läufe, eigene Agent-Laufzeit, Web-UI, alles bis Fr 09:00 |

**Entscheid (Empfehlung an den Owner, Wahl um 12:00):** UC3. Der Hauptraum wird das ganze Produkt. Was vom Vorabend
bleibt: Design-System Klarton+ für die Weboberfläche, Belegschicht (jede Zahl mit Abfrage), Audit-Trail (jetzt als
Freigabeprotokoll mit Namen), Modell-Schalter (Azure zuerst, Mistral dahinter), Golden Set (= Beispielbericht 08/2024 und
die gefundenen Fallen).

Bauplan in Prioritätsreihenfolge (Punkte zuerst, die billig sind):
1. 12:00 Docker-DB hochfahren, `roh.lieferung` laden (läuft im Hintergrund). Repo-Gerüst, YAML auf `uc3`, erster Commit.
2. Bereinigung und Zählregel als SQL/Python mit Regeln in Tabellen (`regel_*`), `lauf --lieferung` CLI, erster Monat
   08/2024 gegen `beispielbericht_2024-08.xlsx` eichen. **Prüfpunkt 15:00: August stimmt.**
3. Alle 24 Läufe, Aggregations-Sheet nach Vorlage, Qualitätsbericht je Monat aus Prüfregeln generiert (Mindestanforderung
   Bereiche 1, 3, 4 sicher).
4. Klassifikationen `klass_*` mit Versionen und Übergängen (ÖNACE 2008 → 2025 aus Umsteiger-Datei; Regionen aus ODS).
5. Eigene Agent-Laufzeit (Azure, austauschbar): Rollen Koordinator, Datenmanagement, Klassifikation, QS, Reporting; jede
   Änderung = Vorschlag (Regel-Diff oder Code-Datei) → Freigabe mit Namen → Commit „Freigegeben-von: Bernhard Götzendorfer“.
   Die drei Änderungsaufträge damit durchspielen; Live-Änderung üben.
6. Web-UI: Läufe, Qualitätsberichte, Annahmen, Klassifikationen, Freigaben, Fragen an die Daten (SQL sichtbar).
7. Pensionen (Optimum Bereich 1) nur, wenn 1 bis 6 stehen. Fr 07:00 Feature-Stopp, 08:30 Upload auf SV-Box.

**Heute noch tun (Owner):** bei der Anmeldung Azure-Schlüssel und GitHub-Einladung holen; bis 16:00 die Mail für den
SV-Box-Teamordner schicken (Entwurf: Betreff „KI Challenge: SV-Box-Ordner für Team OneShotAndy (Use Case 3)“, Text: „Team
OneShotAndy wählt Use Case 3 StatAgent und bittet um den Team-Ordner auf der SV-Box für die Abgabe. Danke.“); Handynummer
für die Signal-Gruppe angeben.

## 9. Offen

- Finaljury-Kriterien: in allen drei Dokumenten leer. Um 11:00 oder 17:00 fragen.
- Ob die Fachjury das Aggregations-Sheet selbst gegen eine Referenz prüft (vermutlich ja, synthetische Daten mit
  bekannter Wahrheit). Darum: kein Verhältnis verlieren, Annahmen begründen.
- Azure-Limits (Rate, Token) und ob weitere Deployments als `gpt-5-4-mini` existieren: nach Schlüsselerhalt `GET /models`.
- Pizza 18:00 oder 20:00 (Blatt und PDF widersprechen sich).
