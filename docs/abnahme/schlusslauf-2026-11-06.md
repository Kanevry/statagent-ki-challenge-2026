# Schlusslauf der Abnahme, 06.11.2026 (Abgabe-Beleg)

Geprüfter Stand: main `b9508d6ac8b298e113ac5d93f2300c1d23a86b8f`, Merge-Stopp-Stand laut Lead f7. Prüfwerkzeug: Commit `8cb41747` des Branches `test/abnahme-matrix`.

| Lauf | Wo | Zeit (Wien) | Laufdatei |
|---|---|---|---|
| leicht | Arbeitsrechner, Abzug | 05:37 bis 05:39 | `laeufe/2026-11-06T0537-b9508d6a.jsonl` |
| schwer | Ersatzrechner, frische Prüf-DB nur auf Loopback, von außen nachgeprüft, 24 Läufe v1 | 05:38 bis 06:07 | `laeufe/2026-11-06T0600-b9508d6a-schwer.jsonl` |
| 22-1 voll | Ersatzrechner, dieselbe Prüf-DB, main `c16fa881` | 06:07 bis 06:32 | `laeufe/2026-11-06T0607-c16fa881-schwer.jsonl` |

Der Zweitrechner fiel in der Nacht aus, deshalb der Ersatz (Entscheid #92). `c16fa881` unterscheidet sich von `b9508d6a` nur in README, `docs/`, `scripts/vorfuehrung.sh` und einer Folie; Rechenpfade und UC3-Web: 0 Änderungen.

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
| 13-AC4 | nicht bestanden, angenommen | Restmangel, Entscheid Lead f7 in #77: `pensionen.py` definiert ein eigenes `freigeben()`. Die Regeln laufen darin über `plattform.freigabe` mit Commit und Trailer, die Zahlen setzt derselbe Aufruf per UPDATE |
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

## Nach diesem Beleg

Bis zum letzten Merge gegen 07:50 sind noch Web-Änderungen und der Frage-Weg (`uc3/statagent/frage*.py`, `woerter.py`, `zeitraum.py`) zugelassen. Die Matrix zeigt UC3 danach mechanisch als veraltet, weil UC3-Web zu den Belegpfaden zählt; das ist kein Rückfall. Für den Endstand kommt ein Nachtrag mit leichtem Lauf, schweren Prüfsätzen und Diff.
