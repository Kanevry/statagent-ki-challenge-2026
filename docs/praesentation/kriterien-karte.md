# Kriterien-Karte StatAgent (Use Case 3)

Sechs Bereiche, je 20 von 120 Punkten. Die Spalte „Raster“ steht wörtlich wie in der Aufgabenstellung, Abschnitt Bewertung. Die Spalte „Stand“ sagt, was im Repo auf `main` ist: **erfüllt**, **teilweise** oder **offen**. Kennungen wie F4 in Klammern verweisen auf das Belegregister, nicht auf die Annahmen F1 bis F10 in den Berichten.

**Gemessen:** 05.11.2026 auf `main` `d3e221f`, Bereiche 1, 2 und 4 neu, online um 23:53 und auf der Datenbank `statistik_probe`. Die übrigen Zeilen werden vor dem Druck neu gemessen.

| Bereich | Stufe | Raster | Stand | Was wirklich da ist | Wo zu sehen |
|---|---|---|---|---|---|
| 1 Datenmanagement | Mindest | liest alle Lieferungen korrekt ein, Datenmodell nach Vorgabe | **erfüllt** | 24 Lieferungen, 10.152.292 Zeilen (F3). Tabellen nach Anhang B. | `/uc3`, `uc3/db/020_stat_metadaten.sql`, `uc3/db/030_bereinigt_stat.sql` |
| | Optimum | versionierter Bestand über alle Lieferungen | **erfüllt** | Jede Lieferung bleibt. Fehlende Verhältnisse werden fortgeschrieben, nichts wird gelöscht (F9, F11). | Szene 3, Demo D1, `uc3/statagent/bereinigung.py` |
| | Optimum | Pensionsmeldungen aller Träger trotz unterschiedlicher Formate eingelesen | **erfüllt** | 28 von 28 Dateien, 9 Formate, 394 Summen ohne Abweichung. 2025: 2.584.909, vorläufig bis zur Freigabe mit Namen. Öffentlich Bedienstete fehlen, die frühere BVA meldet keine. | `docs/uc3/pensionen-pruefbericht.md`, Fragenkatalog C14 |
| 2 Klassifikation | Mindest | legt die benötigten Klassifikationen an, je Begriff nur einmal | **erfüllt** | Geschlecht, Region, Qualifikation, Kategorie, ÖNACE und Alter, je einmal. | `/uc3/klassifikationen`, `uc3/db/020_stat_metadaten.sql` |
| | Optimum | ÖNACE bis zum 5-Steller und Regionen Österreichs vollständig historisiert | **teilweise** | Im Code und auf der Datenbank `statistik_probe` geladen: ÖNACE 2008 und 2025 bis zum 5-Steller (701 und 711 Codes), Bezirke und Gemeinden je Stand 2011 bis 2026. Online noch nicht sichtbar, die Seite zeigt Abschnitte (22 und 23) und Bundesländer. Gezählt wird nach Abschnitt und Bundesland, mehr haben die Lieferungen nicht. | `/uc3/klassifikationen`, `uv run uc3 klass`, Szene 7 |
| | Optimum | Übergänge aus den amtlichen Änderungslisten | **teilweise** | 1.180 Übergänge aus den amtlichen Umsteigern: 1.115 von ÖNACE 2008 nach 2025 auf der tiefsten Ebene, 65 auf Abschnitten, darunter 2003 nach 2008. Auf der Datenbank `statistik_probe` dazu 674 für Gemeinden und 16 für Bezirke, drei amtliche Fälle nachgeprüft. Online nicht sichtbar. | `uc3/statagent/klass.py`, `docs/plan/uc3/regionen-stichprobe.md`, Tabelle `stat.uebergang` |
| | Optimum | kennt und erklärt sie | **teilweise** | Online auf Abschnittsebene: Frage „Was ist ÖNACE R?“ (F13). Bei „Was ist ÖNACE C 10.11-0?“ antwortet die Frage nur zu Abschnitt C (#189). `uv run uc3 klass` kennt alle Ebenen, nur auf `statistik_probe`. | Demo D3, Frage 7 |
| 3 Qualitätssicherung | Mindest | erkennt einen Teil der Fehler, Qualitätsbericht je Monat | **erfüllt** | 24 Berichte, 24 Prüfregeln (F15), acht Arten von Fehlern (F4 bis F11). | `/uc3/berichte/2025-03`, `abgabe/qualitaetsberichte/` |
| | Optimum | erkennt alle Fehler | **teilweise** | Der offizielle Bericht August 2024 stimmt ganz, 2.880 von 2.880 (F1). Für die anderen 23 Monate gibt es keinen Vergleich. Ob es alle Fehler sind, können wir nicht belegen. | Szene 5 und 6 |
| | Optimum | unterscheidet sie von echten Entwicklungen | **teilweise** | Jeder Befund trägt eine Einstufung. Ein Teil bleibt „nicht erklärbar“. Für die Rückfragen R1 bis R10 gilt je eine Annahme mit Beleg, die Rückfrage ist dokumentiert. Der Bericht Jänner 2025 erklärt den Wechsel der Branchenliste. | Demo D1, `/uc3/berichte/2025-01`, `abgabe/rueckfragen/` |
| | Optimum | jede Annahme begründet und dokumentiert | **erfüllt** | Annahmen F1 bis F10 je Monat im Bericht und unter `/uc3/annahmen`, Herleitung A1 bis A13 im Plan. Beispiel Geburtsmonat 13 (Beleg F4). | `/uc3/annahmen`, Folie 8, `docs/plan/uc3/annahmen.md` |
| 4 Reporting | Mindest | Aggregations-Sheet nach den Regeln der Fachbeschreibung | **erfüllt** | Sheet nach alten und neuen Regeln. Kernzahlen August 2024 exakt (F14). | `abgabe/aggregationen_v1.xlsx`, `abgabe/aggregationen_v2.xlsx` |
| | Optimum | Datenanfragen (können sich auch auf Klassifikationen und Metadaten beziehen) richtig beantwortet | **teilweise** | Acht geprüfte Fragen mit Sollzahl (F21 bis F25). Zu Klassifikationen antwortet sie bis zum Abschnitt. Nach Bezirken oder Gemeinden zählt sie nicht, nach dem Alter schon (unter 25 im Juli 2026: 41.626), online gemessen. Freie Fragen sind nicht alle geprüft. | Demo D3, `/uc3/fragen`, Fragenkatalog |
| | Optimum | Dashboard | **erfüllt** | Übersicht aller Monate mit Verlauf und Status. | `/uc3` |
| 5 Weiterentwicklung und Betrieb | Mindest | Produktion läuft deterministisch | **erfüllt** | 72 Wiederholungsläufe, 72-mal derselbe Hash (F16). Gemessen in der Abgabe-Datenbank. | `abgabe/uc3-abnahme.md`, Abschnitt 3 |
| | Optimum | alle Änderungsaufträge und Ministeriums-Lieferung umgesetzt | **erfüllt** | Drei Aufträge (F19). Lieferung 07/2026 mit 32.741 Personen. | `/uc3/freigaben`, `abgabe/ministerium_2026-07.beleg.md` |
| | Optimum | nachvollziehbar protokolliert | **erfüllt** | Jede Änderung mit Anweisung, Name und Zeit (F26). Die Freigaben der Vorschläge 24 bis 26 hat eine KI-Sitzung in Bernhards Auftrag eingegeben, er hat sie um 18:22 bestätigt. Das steht offen im Protokoll. | `abgabe/protokoll.md` |
| | Optimum | Live-Änderung per Sprache gelingt | **teilweise** | Getippter Satz, keine Stimme. Geprobt sind Änderungen an vorhandenen Regelwerten. Unbekannte Aufträge sind auf `main` nicht abgesichert. | Demo D2, Fragenkatalog Teil B |
| 6 Bedienbarkeit | Mindest | alles lässt sich über die Konsole steuern: Läufe starten, Ergebnisse und Qualitätsberichte ansehen, Änderungen freigeben | **erfüllt** | Alles über einen Befehl. | `uv run uc3 --help`, `uc3/statagent/cli.py` |
| | Optimum | übersichtliche Weboberfläche für Läufe, Qualitätsberichte und Annahmen, Klassifikationen, Freigaben und Fragen an die Daten | **erfüllt** | Alle sechs Inhalte sind im Web. Annahmen und Klassifikationen sind eigene Menüpunkte. Aufträge gibt man nur in der Konsole ein. | `/uc3`, `/uc3/berichte/2025-03`, `/uc3/annahmen`, `/uc3/klassifikationen`, `/uc3/freigaben`, `/uc3/fragen` |

## So benutzen wir die Karte am Tisch

Die Karte liegt ausgedruckt vor der Jury. Bei einer Frage zeigt Bernhard auf die Zeile, nennt die Zahl und öffnet die Stelle. „Teilweise“ und „offen“ sagt er von sich aus.

## Vor dem Druck (nicht mit ausdrucken)

Die Karte zeigt nur, was auf `main` ist. Nach jedem dieser Merges die Zeile neu messen und die Kopfzeile mit dem Commit anpassen, dann drucken:

- !150 (unbekannte Live-Änderungen): Bereich 5 Live-Änderung
