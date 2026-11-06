# Aufgaben: was erledigt ist und was offen bleibt

Diese Seite zeigt alle Aufgaben des Teams aus der KI Challenge 2026, mit Nummer, Titel, Status und Labels. Sie ist für alle, die sehen wollen, was aus Sicht des Teams noch offen ist. Die Aufgaben liegen in einem privaten GitLab-Projekt. Von außen kann man sie nicht öffnen, deshalb steht die Liste hier.

Stand: 06.11.2026, 08:39 Uhr (Wiener Zeit).

## Zählung

| Was | Zahl |
|---|---:|
| Aufgaben gesamt | 210 |
| davon erledigt | 60 |
| davon offen | 150 |
| von den offenen ausdrücklich für die Zeit nach der Abgabe vorgesehen (Label `prio::nach-abgabe`) | 21 |

Quelle: GitLab-Projekt des Teams, alle Aufgaben, gelesen über die Schnittstelle von GitLab. In der Liste unten stehen 209 von 210 Aufgaben.

## So liest man die Liste

- **Status:** „erledigt“ heißt, die Aufgabe ist im Aufgabensystem geschlossen. „offen“ heißt, sie ist dort nicht geschlossen. Was davon im Code läuft, steht im [README](../../README.md) und unter [Stand der Use Cases](use-cases-stand.md).
- **Nummern:** `#12` ist eine Aufgabe, `!12` ein Änderungsantrag (Merge Request) im privaten GitLab-Projekt.
- **Labels:** `uc1` bis `uc4` nennen den Use Case. `epic::…` nennt das große Arbeitspaket. `kern` ist der gemeinsame Kern, `ablauf` der Zeitplan. `status::in-progress` heißt in Arbeit. `prio::nach-abgabe` heißt bewusst auf nach der Abgabe gelegt. `owner` heißt, die Aufgabe braucht eine Entscheidung des Auftraggebers.
- **Was fehlt:** Beschreibungen und Kommentare stehen hier nicht, nur Titel und Labels. 3 Titel sind leicht geändert (Rechnernamen, ein Anbietername und ein interner Verweis ersetzt), 1 Titel fehlt, weil er einen persönlichen Bezug hat.

## Epics (die großen Arbeitspakete)

8 Aufgaben, davon 0 erledigt und 8 offen.

| Nr. | Titel | Status | Labels |
|---:|---|---|---|
| #21 | Epic E0 Plattform: Dashboard mit UC-Wechsel im Header, Modell-Schalter, Protokoll/Freigabe, Design Klarton+ | offen | `epic::e0-plattform`, `typ::epic` |
| #22 | Epic E1 UC3 StatAgent (wird bewertet): Pipeline bis Bericht, Anomalien klassifizieren, Agenten mit Freigabe, mit Daten sprechen | offen | `epic::e1-uc3`, `typ::epic` |
| #23 | Epic E2 UC1 SV KI-Lotse: produktiv nutzbarer Lotse mit RAG und Voice-Agent | offen | `epic::e2-uc1`, `typ::epic` |
| #24 | Epic E3 UC2 HealthPolicy Simulator: Persona-Panel mit Moderator, RAG Pressespiegel, lernend | offen | `epic::e3-uc2`, `typ::epic` |
| #25 | Epic E4 Daten-Enrichment: öffentliche Quellen gezielt ergänzen (Konzept zuerst) | offen | `epic::e4-daten`, `prio::nach-abgabe`, `typ::epic` |
| #26 | Epic E5 Präsentation & Jury: Slides in Pen, Live-Demo, Fachjury-Skript | offen | `epic::e5-praesentation`, `typ::epic` |
| #27 | Epic E6 Abgabe: SV-Box-Teamordner, README, gitleaks, GitHub-Push Fr kurz vor 09:00 | offen | `epic::e6-abgabe`, `typ::epic` |
| #95 | Epic E7 UC4 Gemeinsamer Einstieg: eine Frage läuft durch UC3 → UC2 → UC1 | offen | `kern`, `typ::epic` |

## Use Case 3 StatAgent

59 Aufgaben, davon 7 erledigt und 52 offen.

| Nr. | Titel | Status | Labels |
|---:|---|---|---|
| #7 | uc3 StatAgent: Anfrage bis Bericht, reproduzierbar | erledigt | `uc3` |
| #13 | W0 12:00 Repo-Gerüst UC3: pyproject (uv), db/ DDL, CLI lauf/freigabe, LLM-Adapter, YAML=uc3 | erledigt | `ablauf`, `epic::e1-uc3`, `uc3` |
| #14 | W1 Kern: Bereinigung, Stichtagszählung, Regeln als Daten, Eichung 08/2024 gegen Beispielbericht | offen | `epic::e1-uc3`, `status::in-progress`, `uc3` |
| #15 | W1 Agent-Laufzeit: Rollen, Vorschlag→Freigabe mit Name→Commit mit Trailer Freigegeben-von | offen | `epic::e1-uc3`, `status::in-progress`, `uc3` |
| #16 | W2 Betrieb v1: 24 Läufe, Prüfkatalog P01–P24, Qualitätsbericht je Monat, Aggregations-Sheet aus Vorlage | offen | `epic::e1-uc3`, `status::in-progress`, `uc3` |
| #17 | W3 Änderungsaufträge 1–3 über eigene Agenten, 24 Läufe neu, ministerium_2026-07.csv, Datenanfragen | offen | `epic::e1-uc3`, `uc3` |
| #18 | W3 Web-UI (Zeitbox 4 h, lesend): Monatsläufe, Qualitätsberichte, Klassifikationen, Freigaben, Fragen | offen | `epic::e1-uc3`, `status::in-progress`, `uc3` |
| #19 | W4/W5 Optimum: ÖNACE 5-Steller + Umsteiger, Regionen-Historie, Pensionen, Live-Varianten, Determinismus | offen | `epic::e1-uc3`, `prio::nach-abgabe`, `uc3` |
| #20 | Fr 05:00 Feature-Stopp, Abgabe 08:00 (SV-Box-Teamordner + GitHub), Jury 15 min, Finale 12 min | offen | `ablauf`, `epic::e1-uc3`, `uc3` |
| #66 | [Abnahme] EA-4 Jury-Weg: docker compose frisch (DB_PORT=5433), Golden Set 2.880/2.880 und Determinismus-Hash gleich | offen | `epic::e1-uc3`, `uc3` |
| #69 | UC3 W3 Auftrag 1: DV und FD rückwirkend zusammenführen (Regelsatz v2a) | offen | `epic::e1-uc3`, `status::in-progress`, `uc3` |
| #70 | UC3 W3 Auftrag 2: Monatszählung statt Stichtag, 24 Läufe und Sheet neu | offen | `epic::e1-uc3`, `status::in-progress`, `uc3` |
| #71 | UC3 W3 Auftrag 3: Ministeriumslieferung mit jüngstem Datenstand je Tag | offen | `epic::e1-uc3`, `status::in-progress`, `uc3` |
| #72 | UC3 W1 Rückfragen R1–R5 nach Veranstaltervorlage und Antworten als Regeln | offen | `epic::e1-uc3`, `uc3` |
| #73 | UC3 W1 Anhang B: Beschreibungen, Variablen und Quellzuordnungen | offen | `epic::e1-uc3`, `uc3` |
| #74 | UC3 W3 Datenanfragen: statagent frage mit sichtbarem SQL und Definition | offen | `epic::e1-uc3`, `status::in-progress`, `uc3` |
| #75 | UC3 W4 ÖNACE bis 5-Steller: Versionen und Umsteiger 2003→2008→2025 | offen | `epic::e1-uc3`, `status::in-progress`, `uc3` |
| #76 | UC3 W4 Regionen 2011–2026 mit amtlich belegten Übergängen | offen | `epic::e1-uc3`, `uc3` |
| #77 | UC3 W4 Pensionsstatistik 2018–2025 aus Trägerformaten | erledigt | `epic::e1-uc3`, `prio::nach-abgabe`, `uc3` |
| #78 | UC3 W4 Klassifikationserklärung: ÖNACE und regionale Übergänge mit Beleg | offen | `epic::e1-uc3`, `uc3` |
| #79 | UC3 W3 Voice-Verbraucher: Frage und Änderungsauftrag über plattform.voice | offen | `epic::e1-uc3`, `prio::nach-abgabe`, `uc3` |
| #80 | UC3 W4 Live-Änderung A/B/C: Proben, Ablehnen und Rücknahme | offen | `epic::e1-uc3`, `uc3` |
| #105 | UC3 Review-Restpunkte !13: regel_wirkung je Regel, Golden Set nach Veröffentlichung | offen | `epic::e1-uc3`, `uc3` |
| #106 | E7-UC3 Adapter antwort(frage, kontext) über geprüfte Monatszahlen (Epic #95) | erledigt | `epic::e1-uc3`, `uc3` |
| #122 | UC3 abgabe-v1 nach Owner-Freigabe von Regelsatz v1 als endgültig neu erzeugen | offen | `epic::e1-uc3`, `uc3` |
| #123 | UC3 Modellangabe in abgabe/modelle.md prüfen: Azure gpt-5-4-mini als Agentenmodell, kein Modell im Rechenweg | offen | `epic::e1-uc3`, `uc3` |
| #125 | UC3 UC4-Adapter: mehrere Ausprägungen eines Merkmals in einer Frage („Männer und Frauen …“) | offen | `epic::e1-uc3`, `uc3` |
| #126 | UC3 Berichte für die Web-UI: Rückfragen je Monat nach Lieferungen, berichte --json mit lauf_id, regelstand, umgeschichtet, pruefungen_gelaufen | offen | `epic::e1-uc3`, `prio::nach-abgabe`, `uc3` |
| #128 | UC3 BLOCKER Jury-Weg: lauf --alle hängt auf frischer DB in der E07-Abfrage, ANALYZE bereinigt.abschnitt im Lauf fehlt | erledigt | `epic::e1-uc3`, `priority::critical`, `status::in-progress`, `uc3` |
| #131 | Abnahme-Lane: Nachprüfungen nach Merges und Zeitsperren (66-6, #64, #95, #50, #51, #65, #37, #39) | offen | `epic::e1-uc3`, `kern` |
| #135 | UC3-Web: Folgepunkte nach !51 (Tests, v2-Bericht, Waage mit Probe, frage --json, E0-Anträge) | offen | `epic::e1-uc3`, `uc3` |
| #139 | UC3 frage (#74) Folgepunkte aus Review !61 | offen | `epic::e1-uc3`, `prio::nach-abgabe`, `uc3` |
| #147 | Zweitrechner: statagent-db aufräumen: 2 Läufe hängen auf laeuft, Klon statistik_probe 8,2 GB, Test-DBs | offen | `epic::e1-uc3` |
| #160 | UC3 pruefe-abgabe: § 1-Bestand der Berichte gegen meta.lauf.gezaehlt prüfen (v1 und v2), nicht nur ≠ 0 | offen | `epic::e1-uc3`, `uc3` |
| #166 | UC3-Web: Fluktuationsbeispiel online nicht anbieten, Oktober-Satz 78.949 fehlend / 77.746 übernommen erklären | offen | `epic::e1-uc3`, `uc3` |
| #168 | UC3 Web /uc3/freigaben: Rücknahme (aktiv_neu), Ausschluss/Gruppierung und Altersgruppe richtig anzeigen | offen | `uc3` |
| #169 | UC3: Sheet, Qualitätsbericht und Abrechnungstext für Regelsätze mit Ausschluss- oder Gruppierungsregel | offen | `uc3` |
| #171 | UC3/UC4: Vorschlag bei Monat außerhalb der Daten anklickbar machen (Folge !169) | offen | `uc3` |
| #172 | UC3: Folgepunkte aus Review !104 und !50 (Schwelle, UI-Abnahme, Frame-Matrix, Herkunftsprüfung, Live-Änderung in v2) | offen | `uc3` |
| #175 | UC3 sheet: nach einem Teillauf nicht die Abgabedatei überschreiben (Folge !179) | offen | `uc3` |
| #176 | UC3 /uc4: Fluktuation, Anteil und Einzeldaten bekommen eine Bestandszahl statt einer Absage | erledigt | `priority::high`, `uc3` |
| #177 | UC3 Zeiträume: Folgepunkte aus !169 (heuer ohne Monat, Männer/Frauen je Monat, Annahmen) | offen | `uc3` |
| #178 | UC3 Agenten: Rückfall auf Mistral beim Koordinator steht nicht im Vorschlag | offen | `uc3` |
| #179 | UC3 Monatsseite 2025-01 erklärt den ÖNACE-Wechsel nicht | erledigt | `priority::medium`, `uc3` |
| #180 | UC3 Folgepunkte aus den Reviews !150 und !169 | offen | `uc3` |
| #181 | Vorführ-Instanz: Slop-Lauf mit KIC_VORFUEHRUNG=1 und /api/uc3/auftrag in der Methodenmatrix | offen | `uc3` |
| #182 | UC3 Fragen: Alter wird abgesagt, obwohl das Sheet Altersgruppen hat | offen | `uc3` |
| #183 | UC3: Nummernkreise A und F ohne Zuordnung | offen | `uc3` |
| #184 | UC3 /uc3: Satz am Regelsatz-Schalter nennt die Zählart fest im Text | offen | `uc3` |
| #185 | UC3: Trigger überspringt das Löschen von Regelentwürfen still | offen | `uc3` |
| #186 | UC3 Datenanfragen: Zahl ohne gefragte Einschränkung (Wiener, Bergbau, Beruf, Name) | offen | `uc3` |
| #187 | UC3 Pensionen: Folgepunkte aus dem Review von !214 | offen | `prio::nach-abgabe`, `uc3` |
| #189 | UC3 Fragen und P21: tiefe Klassifikationscodes nach Bereich 2 (!193) | offen | `uc3` |
| #190 | UC3-Antwort: Hinweis auf übernommene Verhältnisse nennt bei Filtern die Gesamtzahl | offen | `uc3` |
| #197 | UC3 Rücknahme: Rückfrage des Modells sagt „im Kontext“, neue Absagesätze kommen nicht zum Zug | offen | `uc3` |
| #198 | UI-Regie: 18-AC2 und 135-3 nach dem letzten up neu belegen | offen | `uc3` |
| #199 | UI-Regie: !300 nach dem Merge live prüfen | offen | `uc3` |
| #200 | UI-Regie: SC10 nach dem letzten up neu aufnehmen und beurteilen | offen | `uc3` |
| #206 | Sichtprüfung 06.11.: Favicon 404, y-Achse ab 385.000, Zähler in Schritt 1 | offen | `prio::nach-abgabe`, `shared-ui`, `status:in-progress`, `uc3` |

## Use Case 1 SV KI-Lotse

25 Aufgaben, davon 4 erledigt und 21 offen.

| Nr. | Titel | Status | Labels |
|---:|---|---|---|
| #9 | uc1 Lotse: Träger-Routing, RIS-Belege, Abstinenz | erledigt | `uc1` |
| #28 | UC1 W0 Gerüst und Spikes: Paket lotse, DB lotse, Formularfelder, Vapi Custom LLM über Tunnel | erledigt | `epic::e2-uc1`, `kern`, `status::in-progress`, `uc1` |
| #29 | UC1 W1 Korpus und Suche: 14.244 SozDok-XML, Formulare, Leistungskataloge, EKO in DB lotse (Volltext german) | offen | `epic::e2-uc1`, `kern`, `status::in-progress`, `uc1` |
| #30 | UC1 W1 Lotse-Set und lotse eval: Soll je Fall einfrieren, Recall, Zitiertreue, Träger, Verhaltensklasse | offen | `epic::e2-uc1`, `kern`, `status::in-progress`, `uc1` |
| #31 | UC1 W1 Lotse-Kern: Situation → nötige Rückfragen → Leistungsbündel mit Quelle, Grenzen, Abstinenz, Übergabe | offen | `compliance`, `epic::e2-uc1`, `kern`, `uc1` |
| #32 | UC1 W2 Antrag vorausfüllen: Pflegegeld PAL080 und Kur/Reha als Entwurf, Unterlagen, zuständige Stelle | offen | `epic::e2-uc1`, `kern`, `status::in-progress`, `uc1` |
| #33 | UC1 W2 Upload Entlassungsbrief: nur dokumentierte Empfehlungen wörtlich → Leistung, Stelle, Antrag | offen | `compliance`, `epic::e2-uc1`, `uc1` |
| #34 | UC1 W2 Voice-Anbindung an plattform.voice (E0): UC1-Antwortfunktion, Belege je Call, Call→Sitzung, Text-Fallback | offen | `epic::e2-uc1`, `kern`, `uc1` |
| #35 | UC1 W3 UC1-Seite /uc1 nach Pen-Frames: Situation → Leistungen mit Quelle → Antrag, Replay | offen | `epic::e2-uc1`, `uc1` |
| #36 | [Abnahme] UC1 A1: Pflege-Szenario per Stimme live im Veranstaltungs-WLAN | offen | `epic::e2-uc1`, `owner`, `uc1` |
| #37 | [Abnahme] UC1 A2: frische Prüfung von Grenzen, Zitaten, Träger und Pflichtfeldlisten | offen | `compliance`, `epic::e2-uc1`, `uc1` |
| #38 | [Abnahme] UC1 A3: UC1-Seite gegen Pen-Frames und Schablonen-Messung | offen | `epic::e2-uc1`, `uc1` |
| #39 | [Abnahme] UC1 A4: Held-out-Sätze des Leads vor kern.py, Lauf danach | offen | `epic::e2-uc1`, `uc1` |
| #81 | UC1 W3 Stelle und Termin: belegte Einrichtung und Terminvorbereitung | offen | `epic::e2-uc1`, `uc1` |
| #82 | UC1 W3 Bisherige Anliegen: offene Schritte je Sitzung wiederaufnehmen | offen | `epic::e2-uc1`, `prio::nach-abgabe`, `uc1` |
| #83 | UC1 W3 Gesundheitsförderung und Kind: belegte Leistungsbündel mit fachlichen Grenzen | offen | `epic::e2-uc1`, `prio::nach-abgabe`, `uc1` |
| #107 | E7-UC1 Adapter antwort(frage, kontext) in einfacher Sprache über dem Lotse-Kern (Epic #95) | offen | `epic::e2-uc1`, `uc1` |
| #121 | UC1 Folge aus Review !46: Offline-Laden, Kern-Import, EKO-Zeilen, Doku-Abgleich, Personenangaben in der Erweiterung | offen | `epic::e2-uc1`, `uc1` |
| #130 | UC1 Nacharbeiten Kern: Bürgersprache vs. Deckungsprüfung, Pflege-Angebot, UC4 auf plattform.antwortform, Satzlänge bei Listen | offen | `epic::e2-uc1`, `uc1` |
| #151 | UC1 Kern: Folgepunkte aus Review !93 (Personendaten, Bedingungsprüfung, Träger, Zahlwörter) | offen | `prio::nach-abgabe`, `uc1` |
| #155 | UC1 Kern: Grenzen übergeben, Verweisziel je Grenzart, Träger aus der Leistung (Held-out #39) | offen | `kern`, `uc1` |
| #162 | UC1 Kern: Antwort streift die Frage statt Abstinenz (Kontrollfälle), Unfall-Auslöser für Arbeitsweg-Unterbrechung | erledigt | `kern`, `prio::nach-abgabe`, `uc1` |
| #163 | UC1 Grenze: Akutzeichen eines Schlaganfalls als eigenes Notfall-Muster (Folge !147) | erledigt | `kern`, `uc1` |
| #173 | UC1 online: KIC_ONLINE_UC1=1 zeigt das Formular, die API bleibt bei 403 | offen | `uc1` |
| #174 | UC1 Kern: Verweis „Review !155“ in Kommentaren korrigieren (gemeint: Review von !147) | offen | `prio::nach-abgabe`, `uc1` |

## Use Case 2 HealthPolicy Simulator

33 Aufgaben, davon 12 erledigt und 21 offen.

| Nr. | Titel | Status | Labels |
|---:|---|---|---|
| #8 | uc2 Simulator: Rechenmodell, Szenarien, Stakeholder-Agenten | erledigt | `uc2` |
| #40 | W1 Belege: Pressespiegel 2026 → Artikel → PG-Volltextindex | erledigt | `epic::e3-uc2`, `uc2` |
| #41 | W1 Akteure: Pool von 14 Institutionen und Modell je Rolle als Daten | erledigt | `epic::e3-uc2`, `uc2` |
| #42 | W1 Experte: deterministisches Wirkungsmodell Wartezeit und Kosten mit Annahmenregister | erledigt | `epic::e3-uc2`, `uc2` |
| #43 | W2 Belegsuche: Aktualitätsgewicht, Institutionen, Personenschutz | erledigt | `epic::e3-uc2`, `uc2` |
| #44 | W2 Verhandlung: Moderator, Runden, Zugschema, Prüfungen, Ereignisprotokoll | erledigt | `epic::e3-uc2`, `status::in-progress`, `uc2` |
| #45 | W3 Ergebnis: Positionsmatrix, Einordnung, Protokoll in 8 Teilen, Freigabe mit Name | offen | `epic::e3-uc2`, `uc2` |
| #46 | W3 Lernen: Teilergebnisse je Runde und Lektionen über Fälle | offen | `epic::e3-uc2`, `uc2` |
| #47 | W3 Oberfläche: UC2-Chat nach Pen U2-0 Fall stellen, U2-1 Panel verhandelt, U2-1a Modellfehler | offen | `epic::e3-uc2`, `uc2` |
| #48 | W4 Abgestimmte Antwort: U2-2 mit Positionsänderungen als Balkenreihe, Freigabe und Replay | offen | `epic::e3-uc2`, `uc2` |
| #49 | W4 Szenario Wartezeiten −20 % bei ≤ 5 % Mehrkosten: 3 Läufe, Aufzeichnung, Export | offen | `epic::e3-uc2`, `uc2` |
| #50 | [Abnahme] UC2-Szenario vorführbar: Protokoll, Konsens/Mehrheit/Minderheit, Belege | offen | `epic::e3-uc2`, `owner`, `uc2` |
| #51 | [Abnahme] UC2-Szenario im Standardmodus azure gpt-5-4-mini | offen | `epic::e3-uc2`, `owner`, `uc2` |
| #84 | UC2 Historische Positionen: Pressearchiv vor 2026 mit datierten institutionellen Belegen | offen | `epic::e3-uc2`, `prio::nach-abgabe`, `uc2` |
| #85 | UC2 Koalitionen: nachvollziehbare Ereignisse auf dem vorhandenen Verhandlungsprotokoll | offen | `epic::e3-uc2`, `prio::nach-abgabe`, `uc2` |
| #86 | UC2 Handlungsempfehlungen: Maßnahmen aus Konsens und Mehrheit mit offenen Bedingungen | offen | `epic::e3-uc2`, `prio::nach-abgabe`, `uc2` |
| #87 | UC2 Scope-Nachweis: optionalen Spieltheoriemodus und SozDok-Abgrenzung dokumentieren | erledigt | `ablauf`, `epic::e3-uc2`, `uc2` |
| #101 | .env.example: UC2_DATABASE_URL nennt DB uc2, lokal und im PRD heißt sie healthpolicy | erledigt | `epic::e3-uc2` |
| #103 | E7-UC2 Adapter antwort(frage, kontext) über Panel und Experte (Epic #95) | erledigt | `epic::e3-uc2`, `status::in-progress`, `uc2` |
| #104 | UC2 Embedder auf plattform.embeddings umstellen, sobald #67 gemergt ist | offen | `epic::e3-uc2`, `uc2` |
| #112 | UC2 Prüfskript pruefe_index: Dublettenbeleg über vollen Abschnitt-1-Text, Titelprüfung bei Radio/TV | offen | `epic::e3-uc2`, `uc2` |
| #117 | UC2 Personenschutz und Belegsuche: Folgepunkte aus Review !43 | offen | `epic::e3-uc2`, `uc2` |
| #127 | UC2 Herdenverhalten: claude-Panel einigt sich in allen Themen (Qualitätslauf Fall 9) | erledigt | `epic::e3-uc2`, `uc2` |
| #132 | UC2 API: Akteur-Auswahl aus U2-0 und Provider ollama an die Verhandlung durchreichen | offen | `epic::e3-uc2`, `uc2` |
| #136 | UC2 Oberfläche v2: Gesprächsverlauf ohne Wiederholungen, Mobil kürzer | offen | `epic::e3-uc2`, `uc2` |
| #137 | UC2 vor Online-Schaltung von POST/echten Modellen: Modelltexte maskieren, Zitate sperren, Freitext-Frage prüfen | offen | `epic::e3-uc2`, `priority::high`, `uc2` |
| #138 | UC2 Verhandlung: Folgepunkte aus Review !47 | offen | `epic::e3-uc2`, `uc2` |
| #142 | UC2-Antwort: Zählwert ohne „Anzahl“ als Einheit (7.498 statt 7.498 Anzahl) | erledigt | `uc2` |
| #149 | UC2 Orakel pruefe_lauf: Beleg-Zahlen gegen den vollen Abschnitt prüfen, nicht gegen das 300-Zeichen-Zitat | erledigt | `uc2` |
| #156 | UC2: Wiederholung nach ungültiger Ausgabe zeigt dem Modell den unmaskierten eigenen Text | offen | `priority::low`, `uc2` |
| #157 | UC2: Namensscan meldet Institutionswörter als Namen (Austria, Statistik Austria) | offen | `priority::low`, `uc2` |
| #158 | UC2: Namensschutz im UC4-Kurzlauf (antwort/kurzlauf.py) vor dem Online-Gang von UC4 | offen | `priority::medium`, `uc2` |
| #159 | UC2: Docstring von MEHRKOSTEN_LINIE steht unter VERHANDLUNGSRUNDE (szenario.py) | offen | `priority::low`, `uc2` |

## Use Case 4 Gemeinsamer Einstieg

6 Aufgaben, davon 4 erledigt und 2 offen.

| Nr. | Titel | Status | Labels |
|---:|---|---|---|
| #96 | E7-E0-1 Antwortform UcAntwort in shared/ (pydantic + zod, JSON-Schema, Contract-Test) | erledigt | `kern` |
| #97 | E7-E0-2 Router-Gerüst plattform.router: Kette UC3 → UC2 → UC1, Kontext weiterreichen, jeder Schritt protokolliert | erledigt | `kern` |
| #98 | E7-E0-3 UC4-Route /uc4: eine Frage, drei Karten in Kettenreihenfolge mit HerkunftChip und Modell-Badge | erledigt | `kern`, `status::in-progress` |
| #113 | UC4-Karten: Modellangabe als Modell-Pille (CKCV4) statt eigener Randlinie | erledigt | `epic::e0-plattform`, `kern` |
| #164 | UC4: Station 2 und 3 wiederholen nur die Zahl von StatAgent | offen | `uc4` |
| #202 | UC4: Folgen aus der Prüfung von !303 (Zahlwörter, Kartentext, vorläufig) | offen | keine |

## Plattform (gemeinsamer Kern, Oberfläche, Online-Demo)

50 Aufgaben, davon 24 erledigt und 26 offen.

| Nr. | Titel | Status | Labels |
|---:|---|---|---|
| #4 | 12:00 Repo-Gerüst: Next.js, gitleaks, CLAUDE.md, Remotes | erledigt | `ablauf`, `epic::e0-plattform`, `kern` |
| #5 | Kern: Belegschicht, Rechenschicht, Audit-Trail, Modell-Schalter | erledigt | `epic::e0-plattform`, `kern` |
| #52 | E0 Modell-Schalter: complete() mit modell und aufwand, claude -p gehärtet (Bedarf UC2 #44) | offen | `epic::e0-plattform`, `uc2` |
| #53 | E0-W0 Monorepo-Grundgerüst: pnpm- und uv-Workspace, CI grün im ersten MR, .env.example we-16, CLAUDE.md Struktur | erledigt | `epic::e0-plattform`, `kern` |
| #54 | E0-W0 Modell-Schalter plattform.llm: complete() mit azure\|claude\|mistral\|ollama\|mock, zweck-Routing, Protokollzeile, Smoke | erledigt | `epic::e0-plattform`, `kern` |
| #55 | E0-W1 Protokoll und Freigabe: DDL meta.protokoll/meta.freigabe, freigeben() mit Namensprüfung und Git-Trailer, JSON-Vertrag | erledigt | `epic::e0-plattform`, `kern` |
| #56 | E0-W1 shared/ui Design-Tokens Klarton+ aus Pen und eigene Basis-Elemente (keine shadcn-Defaults) | erledigt | `epic::e0-plattform`, `kern` |
| #57 | E0-W1 web/ Shell: Header mit UC-Wechsel (nas8Y), Modell-Badge (CKCV4), Protokoll-Schublade (yK42X), Registry und UcBereich | offen | `epic::e0-plattform`, `kern`, `status::in-progress` |
| #58 | E0-W2 Landingpage/Übersicht (Frame c0eRD): Leitmotiv, drei UC-Karten, wie gebaut, gefundene Datenfehler | erledigt | `epic::e0-plattform`, `kern` |
| #59 | E0-W3 Präsentations-Tab (Frame H8TJkE): Slides laufen in der App, Live-Einbettung von Routen | erledigt | `epic::e0-plattform`, `kern` |
| #60 | E0-W2 shared/ui Bausteine: Herkunft-Chip (QVMco), Warn-Chip (NeqAs), Freigabe-Karte (FgY98), Protokoll-Schublade (yK42X), Glossar | offen | `epic::e0-plattform`, `kern`, `status::in-progress` |
| #61 | E0-W3 shared/voice: Vapi-Custom-LLM-Router (SSE, Bearer, Webhook, Tunnel-Middleware), VoiceKnopf (eE7uh), Text-Fallback | offen | `epic::e0-plattform`, `kern`, `status::in-progress` |
| #62 | E0-W1 Anti-Schablonen-Gate: measureSlop (impeccable) als Playwright-Test, 12 Schlüssel = 0, Positiv-Fixture | erledigt | `epic::e0-plattform`, `kern` |
| #63 | [Abnahme] EA-1 Modell-Schalter live: azure, mistral, claude antworten; models.md mit Zeitstempel | offen | `epic::e0-plattform`, `kern` |
| #64 | [Abnahme] EA-2 Screens entsprechen Pen-Frames (Shell, Landing, Präsentation, Bausteine, UC3) per Screenshot, 0 Schablonen-Treffer | offen | `epic::e0-plattform`, `kern` |
| #65 | [Abnahme] EA-3 Voice-Anruf Ende-zu-Ende: gesprochene Zahl 2025-03 = psql-Zahl, Transkript sichtbar | offen | `epic::e0-plattform`, `kern`, `prio::nach-abgabe` |
| #67 | E0-W2 plattform.embeddings: google/embeddinggemma-2 lokal (sentence-transformers), erst Prototyp mit Messung, dann hochskalieren | erledigt | `epic::e0-plattform`, `kern` |
| #68 | E0-W3 Online-Deploy: ki-challenge.gotzendorfer.at auf einem eigenen Server (Docker, Caddy TLS, Basic Auth bis Fr 09:00) | offen | `epic::e0-plattform`, `kern` |
| #93 | E0 Kleinpunkte aus Review !4: KIC_ENV_DATEI, install-hooks, mypy in CI, vitest, .gitignore, Gerätenamen | erledigt | `epic::e0-plattform`, `kern` |
| #94 | E0 plattform.llm: Stream-Abbruch durch Verbraucher als „abgebrochen“ protokollieren, status zeigt zuletzt/Fallback-Stufe | erledigt | `epic::e0-plattform`, `kern` |
| #99 | E0 Freigabe: objekt_ref muss bei datei gleich ref sein; Commit-Wiederverwendung nur bei gleichem Freigebenden | erledigt | `epic::e0-plattform`, `kern` |
| #100 | Online-Demo: Ratenlimit und Tagesbudget für Modellaufrufe, bevor Modellschlüssel online gehen | offen | `epic::e0-plattform`, `status::in-progress` |
| #102 | E0 Gate: ab Feature-Stopp Fr 05:00 ABGABE=1 im CI-Job playwright setzen (NOCH_OFFEN leer, jede Route 200) | erledigt | `epic::e0-plattform`, `kern` |
| #108 | Deploy-Härtung: Rechteprobe je DB fail-closed, up bricht bei Modellschlüssel ohne Ratenlimit ab | offen | `epic::e0-plattform` |
| #109 | Landing-Nacharbeit: UC4-Link aktivieren (#98), Tablet 768–1100 und echtes Handy prüfen | offen | `epic::e0-plattform` |
| #110 | E0: Schriften und CSS im kritischen Pfad, LCP mobil 2,4 s auf der Landing | offen | `epic::e0-plattform`, `prio::nach-abgabe` |
| #111 | CI: workflow:rules lässt API-Pipelines (glab ci run) nicht zu, Deploy-Job nur per UI-Klick startbar | erledigt | `epic::e0-plattform` |
| #114 | E0 Voice live: Vapi-Assistent per sync anlegen, Tunnel starten, Smoke-Test | offen | `epic::e0-plattform`, `kern`, `status::in-progress` |
| #115 | E0 Header mit UC4-Tab bei 1440 px im Browser prüfen (nach !45) | erledigt | `epic::e0-plattform`, `kern` |
| #116 | E0 sichtbare Texte nach Owner-Regel 15:4x prüfen (einfach, menschlich, Glossar, keine Em-Dashes) | offen | `epic::e0-plattform`, `kern`, `status::in-progress` |
| #118 | E0 Folge Review !36: Tagesbudget Doku und Zählung schärfen, XFF bei CDN | erledigt | `epic::e0-plattform` |
| #119 | E0 Folge Review !38: Voice-Router Endgrund exakt, Webhook-Retry, Budget-Hinweis am Telefon, uc4 in metadata | erledigt | `epic::e0-plattform`, `kern` |
| #120 | E0 Folge Review !41: VoiceKnopf Vertrag ladeSdk, Transkript-Filter, reduced-motion, Bausteine-Zustände, Frame eE7uh | offen | `epic::e0-plattform`, `kern` |
| #124 | Landing: Klartext nach Owner-Feedback 15:5x und gemeinsame Wortliste docs/sprache.md | erledigt | `epic::e0-plattform` |
| #129 | E0 Folge Review !45: Spiegel-Tests, Frame-Entscheide im MR, Touch-Ziele 44 px, Pen-Variable l-gruen-dunkel | offen | `epic::e0-plattform`, `kern` |
| #133 | Landing Folge aus Review !54: Glossar-Test über alle Arrays, „keine Lieferung geprüft“ nur über meta.lauf, Personas erklären | offen | `epic::e0-plattform` |
| #140 | E0 Folge Review !66: UTC-Test schärfen, Rückwärtszählung ohne Sortier-Annahme, Schema-Eigenschaften namens default/enum | erledigt | `epic::e0-plattform` |
| #143 | Online: Datenbank lotse fehlt auf dem Server, nötig sobald /uc1 (!69) auf main ist | offen | `epic::e0-plattform` |
| #144 | Online: uc2.api läuft im App-Container nicht, /uc2 zeigt nur aufgezeichnete Fälle | offen | `epic::e0-plattform` |
| #145 | Stufe A: /api/uc3/frage hat online kein Ratenlimit je IP, nur 2 gleichzeitige Läufe | erledigt | `epic::e0-plattform` |
| #146 | Betrieb nach der Abgabe: Speicherlimit je Container, App-Image mit Revision taggen, Sicherung vom Server weg | offen | `epic::e0-plattform` |
| #148 | Live-UI aus Jury-Sicht: fünf Querschnitts-Befunde (KI-Pille, rote Sperren, Freigabe-Weg, Landing-Tabelle, leere Präsentation) | offen | `epic::e0-plattform`, `kern` |
| #150 | E0 Folge Review !94/!96: deploy-Proben, claude-Sitzung, Abbruch im Ergebnis-Weg, Kernsatz, Exit nach ende | erledigt | `epic::e0-plattform` |
| #152 | E0 Folge Review !90: Seed-Ziel prüfen, /uc3 gefüllt nachweisen, Lint-Umfang, uv-Installer pinnen | erledigt | `epic::e0-plattform` |
| #154 | Rechte und Voice-Schlüssel nachschärfen: TEMP für kic_app direkt prüfen, #108b ohne VAPI_PUBLIC_KEY/ASSISTANT_ID | offen | `epic::e0-plattform` |
| #161 | Landing: / wird beim Image-Build ohne DB mit Beispieldaten vorgerendert, nach jedem Deploy einige Minuten „nicht live“ | erledigt | `epic::e0-plattform` |
| #167 | UC2 Folge !154: lade_schutz behandelt unlesbare Namensliste wie fehlende (SchutzFehler statt PermissionError) | offen | `epic::e0-plattform` |
| #170 | README: Satz zu gleichen Zahlen und Hashes auf frischer DB auf Regelsatz v1 einschränken, falls B1-Fix nicht bis 06:30 | offen | `epic::e0-plattform` |
| #192 | Online: öffentliche db ohne init, Healthcheck-Timeout kann Postgres neu starten | offen | `epic::e0-plattform`, `prio::nach-abgabe` |
| #209 | Online: eine einzige Instanz mit Demo und Live statt zweier Adressen | offen | `epic::e0-plattform`, `prio::nach-abgabe` |

## Präsentation

5 Aufgaben, davon 0 erledigt und 5 offen.

| Nr. | Titel | Status | Labels |
|---:|---|---|---|
| #88 | E5 Screenshots SC1–SC12: nachvollziehbarer Satz für Slides und Jury | offen | `ablauf`, `epic::e5-praesentation`, `status::in-progress` |
| #89 | E5 Slides-Inhalt: 11 belegte Folien und Weg vom Prototyp zum Produkt | offen | `ablauf`, `epic::e5-praesentation`, `status::in-progress` |
| #90 | E5 Jury-Probe: 10-Minuten-Durchlauf und lokal abspielbares Backup-Video | offen | `ablauf`, `epic::e5-praesentation`, `owner`, `status::in-progress` |
| #134 | E5 Folgepunkte aus Review !52: Werkzeug-Prüfungen schärfen, PRD bereinigen | offen | `epic::e5-praesentation` |
| #141 | E5 Nacharbeit nach !80: Datenanfragen im Drehbuch, echte Screenshots, Tagesstand, Video und Probe | offen | `epic::e5-praesentation` |

## Abgabe

2 Aufgaben, davon 0 erledigt und 2 offen.

| Nr. | Titel | Status | Labels |
|---:|---|---|---|
| #91 | E6 README, Lizenz und Herkunft: ausführbare Anleitung und geklärte everlast-Anteile | offen | `ablauf`, `compliance`, `epic::e6-abgabe`, `owner`, `status::in-progress` |
| #92 | E6 Abgabe Fr 09:00: vollständige SV-Box-Artefakte und zeitlich kontrollierter GitHub-Push | offen | `ablauf`, `compliance`, `epic::e6-abgabe`, `owner` |

## Übergreifend: Ablauf, Abnahme, Betrieb

21 Aufgaben, davon 8 erledigt und 13 offen.

| Nr. | Titel | Status | Labels |
|---:|---|---|---|
| #2 | Do 10:00 Kickoff-Check: Netz, Repo-Zugang, Modellzugang | erledigt | `ablauf` |
| #3 | Do 11:00 bis 12:00: Use Case wählen und YAML setzen | erledigt | `ablauf` |
| #6 | Shell und Design-System „Klarton“ mit drei Räumen | erledigt | `kern` |
| #10 | Kette: Lotse-Signal → StatAgent → Simulator | erledigt | `kern` |
| #11 | Messung: Golden Sets und Dashboard je Raum | erledigt | `kern` |
| #12 | Fr 07:00 Abgabe und Pitch: README, Secret-Scan, Video-Backup, Probedurchlauf | erledigt | `ablauf` |
| #153 | Modell-Badge: bei Fallback das Modell nennen, das wirklich geantwortet hat | offen | `shared-ui` |
| #165 | UI-Regie Rest: Handy-Sitzreihe UC2, Markenwechsel im Kopf, Teaser „Use Case 4“ auf der Landing | offen | keine |
| #188 | E0: Trockenläufe der Abgabe-Skripte vom letzten main und Stand in der Checkliste | offen | `ablauf`, `status:in-progress` |
| #191 | [Carryover] UI-Regie Nacht bis 06:05: Bögen, Nachprüfung, Fenster, Endvideo | offen | `carryover` |
| #193 | UC3 Jury-Probe: „unter 25“ mit Sollwert prüfen statt nur Antwortart | offen | `priority::medium` |
| #194 | UC3 Datenanfrage v2: Jahreszeiten und Zeitreihe ohne Zahl | offen | `priority::low` |
| #195 | Abnahme: 13 „nicht bestanden“ aus Lauf 7de159d5 gegen main prüfen, Prüfsatz probe.md (15 oder 19 Abschnitte) | offen | `ablauf` |
| #196 | UC2: modell-fallback.md:64 nennt die Anbindung von ollama noch als offen | offen | `ablauf` |
| #201 | UC3 Ergebnisse: Image-Test um die Zeile * ergänzen, Frame-Zuordnung für /uc3/ergebnisse | offen | `prio::nach-abgabe` |
| #203 | Startseite: eigene Seite zum Ablauf des Hackathons mit Zeitleiste | erledigt | keine |
| #204 | Rückfragen und Absagen im Frage-Weg nennen noch Regelsatz v1 und v2 | erledigt | keine |
| #205 | UC2 Probierseite: Folgen aus !315 | offen | keine |
| #207 | UC3 Fragen: Bei Zeitraum fällt „nach Geschlecht und Bundesland“ auf Geschlecht zurück | offen | `prio::nach-abgabe` |
| #208 | UC3 Fragen: Folge zu !328, zwei Sätze und herausgenommene Rechenwege | offen | `prio::nach-abgabe` |
| #210 | UC3: Protokoll-Panel nennt bei freigegebenem Vorschlag weder Name noch Freigabezeit | offen | `status:in-progress` |

## Weiter lesen

- [README](../../README.md): Lösung, Ausführung und Grenzen
- [Stand der Use Cases](use-cases-stand.md): was je Use Case läuft und was nicht
- [Arbeitsweise mit KI-Agenten](arbeitsweise-agentisch.md): wie aus einer Aufgabe eine geprüfte Änderung wird
- [Übersicht dieses Ordners](README.md)
