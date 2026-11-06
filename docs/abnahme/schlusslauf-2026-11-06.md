# Schlusslauf der Abnahme, 06.11.2026 (Abgabe-Beleg)

Geprüfter Stand: main `b9508d6ac8b298e113ac5d93f2300c1d23a86b8f`, Merge-Stopp-Stand laut Lead. Prüfwerkzeug: Commit `8cb41747` des Branches `test/abnahme-matrix`.

| Lauf | Wo | Zeit (Wien) | Laufdatei |
|---|---|---|---|
| leicht | Arbeitsrechner, Abzug | 05:37 bis 05:39 | `laeufe/2026-11-06T0537-b9508d6a.jsonl` |
| schwer | Ersatzrechner, frische Prüf-DB nur auf Loopback, von außen nachgeprüft, 24 Läufe v1 | 05:38 bis 06:07 | `laeufe/2026-11-06T0600-b9508d6a-schwer.jsonl` |
| 22-1 voll | Ersatzrechner, dieselbe Prüf-DB, main `c16fa881` | 06:07 bis 06:32 | `laeufe/2026-11-06T0607-c16fa881-schwer.jsonl` |

Der Zweitrechner fiel in der Nacht aus, deshalb der Ersatz (Entscheid #92). `c16fa881` unterscheidet sich von `b9508d6a` nur in README, `docs/`, `scripts/vorfuehrung.sh` und einer Folie; Rechenpfade und UC3-Web: 0 Änderungen.

Die genannten Laufdateien liegen unverändert im GitLab-Branch `abnahme/laeufe`, siehe `laeufe/README.md`.

## Zähler

Geurteilt für main `c16fa881`, 06:07. Kein „alles bestanden“: Das Tor ist offen.

| Teil | bestanden | nicht bestanden | nicht geprüft | nach Abgabe | gesamt |
|---|---:|---:|---:|---:|---:|
| UC3 | 53 | 1 | 5 | 17 | 76 |
| E6 | 2 | 1 | 6 | 0 | 9 |
| UC4 | 10 | 4 | 8 | 0 | 22 |
| UC1 | 3 | 2 | 19 | 7 | 31 |
| UC2 | 0 | 0 | 5 | 9 | 14 |
| E5 | 6 | 8 | 13 | 0 | 27 |
| E0 | 0 | 0 | 88 | 0 | 88 |

E0 hat keine Prüfsätze, das ist kein Urteil. UC1, UC2, UC4 und E5 sind für diesen Stand nicht einzeln nachgesehen. Seit dem Zähler liegen 22-1 voll (bestanden) und die Hand-Belege 27-1 und 91-2 vor.

## Tor UC3 und E6

| Kriterium | Stand | Grund |
|---|---|---|
| 13-AC4 | nicht bestanden, angenommen | Restmangel, Entscheid des Leads in #77: `pensionen.py` definiert ein eigenes `freigeben()`. Die Regeln laufen darin über `plattform.freigabe` mit Commit und Trailer, die Zahlen setzt derselbe Aufruf per UPDATE |
| 22-1 | bestanden | 24 Läufe v2 und Sheet v2 (1003 Zellen) gleich Orakel, Ministeriums-CSV 32.741 Personen mit sha256 wie Beleg |
| 18-AC2 | offen | Hand-Beleg galt für den Stand vor den letzten Web-Änderungen, neue Prüfung nach dem letzten Deploy. Geprüft von einem Agenten, kein Mensch; Qualitätsberichte haben keinen eigenen Reiter |
| 18-AC3 | offen, Teil-Restmangel | Auf dem Ersatzrechner nicht messbar (Port 3210 belegt, Node 22). Schablonen aus dem Job `playwright` des letzten Zugs, axe auf den Unterseiten offen |
| 75-AC1 | offen, Teil-Restmangel | ÖNACE 2008 und 2025 gemessen und gleich den Quellen; 2003 bis zum 5-Steller und Importprotokoll fehlen |
| 76-AC1 | offen, Teil-Restmangel | 16 Stände, Codes und Übergänge gemessen; Importmanifest fehlt |
| 91-1, 91-3 | veraltet, offen | README nach dem Lauf geändert, misst der leichte Lauf auf dem Endstand |
| 92-2 | offen | Maschinenteil leicht; Dateiliste geht die Lead-Session vor dem Upload durch |
| 92-3, 92-4 | offen | erst nach Upload und Push messbar |

27-1 und 91-2 bestanden mit Hand-Beleg: 27-1 gegengelesen von der Lead-Session, kein Mensch; 91-2 laut Lead-Entscheid mit dem Owner-Wort „Logos haben wir das okay“, Lockfile-Pakete nur installiert.

## Anmerkungen, die sichtbar bleiben

- 75-AC2 bestanden: keine eigene Fußnote an Abschnitt C, Wortlaut „nicht eindeutig“ fehlt.
- 76-AC2 bestanden: SQL genannt, Ergebniszeilen nicht in der Datei, Beziehungen nicht neu gemessen.
- 135-3 bestanden: geprüft von einem Agenten im Browser, kein Mensch.
- 80-AC1 und 80-AC2 bestanden laut Belegdatei, kein neuer Lauf.
- 26-1 offen bis zur Probe des Owners, zählt nicht zum Tor.
- 89-3 und 98-1: auf dem Ersatzrechner nicht messbar (Port 3210, Node 22).

## Korrektur früherer Läufe

Bis 06.11. 02:20 hatten die pytest-Sätze 14-AC3, 15-AC2, 16-AC1, 70-AC1, 73-AC1, 74-AC2 und 78-AC1 keine Adresse für ihre Test-Fixtures und fielen auf den Bau-Port zurück. Frühere Läufe dieser Sätze liefen damit vermutlich gegen den Bau-Server, nicht gegen die Prüf-DB. In diesem Lauf liefen sie auf der Prüf-DB und bestanden.

## Nachtrag auf dem letzten Code-Stand

Letzter Stand für App und Code: main `14c86cc3593167e322392cc08a00f02c687532d7` (Lead). Leichter Lauf 07:46 bis 07:48 auf dem Arbeitsrechner, schwere Prüfsätze 07:39 bis 07:50 auf dem Ersatzrechner, ohne neue Rechnung auf der Prüf-DB vom Stand `b9508d6a`.

**Diff `b9508d6a` bis `14c86cc3`:** Rechenpfade 0 Änderungen. Genannte Ausnahme Frage-Weg: `uc3/statagent/frage.py`, `uc3/statagent/frage_app.py`, dazu Tests und Fragenkatalog. `abgabe/` und Lockfiles 0 Änderungen. Web und `shared/ui`: 128 Dateien, darunter die Downloads der Abgabe-Excel.

| Teil | bestanden | nicht bestanden | nicht geprüft | nach Abgabe | gesamt |
|---|---:|---:|---:|---:|---:|
| UC3 | 53 | 2 | 4 | 17 | 76 |
| E6 | 4 | 1 | 4 | 0 | 9 |

Geurteilt für `14c86cc3`, 07:50. Das Tor bleibt offen: 10 offen, 1 per Entscheid; mit dem Entscheid zu 74-AC1 und dem Beleg zu 92-2 sind es 8 offen, 2 per Entscheid: 18-AC3, 22-1, 75-AC1, 76-AC1, 91-2, 91-3, 92-3, 92-4.

**74-AC1, Restmangel (Entscheid des Leads):** Die Frage nach der Fluktuation je Wirtschaftsbereich läuft unter Last oder mit kaltem Cache, nicht getrennt gemessen, in die Zeitgrenze und antwortet dann mit ‚später noch einmal fragen‘; allein gestellt lieferte sie die Zahl (88 von 88, zweimal gemessen, beide Male kurz nach dem roten Lauf). Keine falsche Zahl. Gemessen: im vollen Lauf hinter den anderen Sätzen zweimal 86 von 88 (ceef8b15, 14c86cc3), allein zweimal 88 von 88. Benannt ist die Frage „Wie hoch ist die Fluktuation je Wirtschaftsbereich im Oktober 2024?“; der zweite rote Test ist vermutlich die Sammelprüfung derselben Frage, das ist nicht belegt. Dass es die Zeitgrenze ist, folgt aus dem Antworttext und dem Muster, gemessen ist die Grenze selbst nicht. Die zwei grünen Einzelläufe starteten Minuten nach dem roten Lauf auf derselben Prüf-DB, also mit warmem Cache und ohne die Wegwerf-DBs davor; Last und kalter Cache sind nicht getrennt.

**22-1 voll:** letzte Messung auf `c16fa881` bestanden, auf `14c86cc3` nicht wiederholt (26 min). Rechenpfade seither unverändert.

**18-AC2 und 135-3:** bestanden, neu belegt von der UI-Prüfung auf dem Stand gleich `ceef8b15`, Agent und kein Mensch. Trailer gelesen von der Vorführ-Lane. „Kein Modellaufruf aus web/“ per Suche des Prüfers auf main.

**92-2:** Dateiliste gelesen vom Lead um 07:53, Einträge geprüft von der Lead-Assistenz um 07:44, Agent und kein Mensch.

**91-2:** bestanden nach neuer Lesung durch die Assistenz des Leads (Agent, kein Mensch) mit der ergänzten Zeile zu den Formulartexten; die Veröffentlichung dieses Wortlauts entscheidet der Owner und ist nicht Teil des Belegs; Paketlizenzen nicht einzeln geprüft. **91-3:** beim Owner.

**92-3:** bestanden: 67 von 67 Dateien, einschließlich Ministeriums-CSV, sha256 gleich Manifest und Rücklesen, 07:55:36 bis 08:02:09 (Agent, kein Mensch). Danach kam auf Owner-Freigabe `zusatz/stand-uc1-uc2-uc4.md` außerhalb des Manifests dazu.

**92-4:** bestanden: Der Abgabestand `7dff9bdb` lag um 08:30:37 auf GitHub-`main`, also vor 09:00. Um 08:56:08 folgte `d130a9ef`, das um 09:00 auf GitHub-`main` stand (nur eine README-Zeile und `docs/einstieg/aufgaben-stand.md` mehr, `abgabe/` gleich), um 09:25:58 `93929f9a`; um 09:35 stand GitHub-`main` auf `93929f9a`, mit README, ohne Rohläufe und mit unverändertem `abgabe/`. Per API nachgesehen vom Prüfer. Das Repo ist privat; ob die Jury Zugriff hat, liegt beim Lead. Ein späterer Push ist damit nicht belegt.

**Online gemessen 07:53:** `/api/uc3/ergebnisse/v1` und `v2` antworten 200 mit sha256 wie im Manifest, `ministerium` und `ministerium_2026-07.csv` antworten 404. Welcher Commit online läuft, ist von außen nicht abgelesen.

**Nachgetragen nach dem Schlusslauf in den Prüfsätzen:** Hand-Belege wurden bis 07:39 von der Zeile des letzten Laufs überdeckt und erschienen als offen; behoben, kein Rückfall.

Der Prüfrechner ist abgeräumt.

**Welche UC3-Zahl zu welchem Stand gehört:** Die Messung ist dieselbe, gewachsen ist nur die Liste der Kriterien.

| Zeit | Geurteilt für | bestanden | nicht bestanden | nicht geprüft | nach Abgabe | gesamt |
|---|---|---:|---:|---:|---:|---:|
| 07:50 | `14c86cc3` | 53 | 2 | 4 | 17 | 76 |
| 08:49 | `7dff9bdb` | 53 | 2 | 4 | 19 | 78 |
| 09:26 | `7dff9bdb` | 53 | 2 | 4 | 21 | 80 |

Dazugekommen sind 211-1 und 211-2 (bis 08:49) sowie 212-1 und 212-2 (bis 09:26). Beide Issues tragen das Label `prio::nach-abgabe` und wurden nie gemessen. Für die Abgabe gilt die Zeile von 07:50.

## Nach diesem Beleg

Danach waren nur noch Doku und der Nachweis-Commit vorgesehen. Die Matrix zeigt bei Änderungen an UC3-Web mechanisch „veraltet“, das ist kein Rückfall.
