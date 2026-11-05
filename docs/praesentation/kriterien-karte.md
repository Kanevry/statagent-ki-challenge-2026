# Kriterien-Karte StatAgent (Use Case 3)

Sechs Bereiche, je 20 von 120 Punkten. Die Spalte „Raster“ steht wörtlich wie in der Aufgabenstellung, Abschnitt Bewertung. Die Spalte „Stand“ sagt, was im Repo auf `main` ist: **erfüllt**, **teilweise** oder **offen**. Kennungen wie F4 in Klammern verweisen auf das Belegregister, nicht auf die Annahmen F1 bis F10 in den Berichten.

**Gemessen:** 05.11.2026 auf `main` `3cb60c2`, Klassifikationen in der Abgabe-Datenbank.

| Bereich | Stufe | Raster | Stand | Was wirklich da ist | Wo zu sehen |
|---|---|---|---|---|---|
| 1 Datenmanagement | Mindest | liest alle Lieferungen korrekt ein, Datenmodell nach Vorgabe | **erfüllt** | 24 Lieferungen, 10.152.292 Zeilen (F3). Tabellen nach Anhang B. | `/uc3`, `uc3/db/020_stat_metadaten.sql`, `uc3/db/030_bereinigt_stat.sql` |
| | Optimum | versionierter Bestand über alle Lieferungen | **erfüllt** | Jede Lieferung bleibt. Fehlende Verhältnisse werden fortgeschrieben, nichts wird gelöscht (F9, F11). | Szene 3, Demo D1, `uc3/statagent/bereinigung.py` |
| | Optimum | Pensionsmeldungen aller Träger trotz unterschiedlicher Formate eingelesen | **offen** | Nicht eingelesen. | Fragenkatalog C14 |
| 2 Klassifikation | Mindest | legt die benötigten Klassifikationen an, je Begriff nur einmal | **erfüllt** | Geschlecht, Region, Qualifikation, Kategorie, ÖNACE und Alter, je einmal. | `/uc3/klassifikationen`, `uc3/db/020_stat_metadaten.sql` |
| | Optimum | ÖNACE bis zum 5-Steller und Regionen Österreichs vollständig historisiert | **teilweise** | ÖNACE 2008 und 2025 nur als Abschnitte (22 und 23), mit Gültigkeit. Regionen nur als Bundesländer. Gezählt wird kein 5-Steller, keine Bezirke, keine Gemeinden. | `/uc3/klassifikationen`, Szene 7 |
| | Optimum | Übergänge aus den amtlichen Änderungslisten | **teilweise** | 1.180 Übergänge aus den amtlichen Umsteigern: 1.115 von ÖNACE 2008 nach 2025 auf der tiefsten Ebene, 65 auf Abschnitten, darunter 2003 nach 2008. Für Regionen keine. | `uc3/statagent/klass.py`, Tabelle `stat.uebergang` |
| | Optimum | kennt und erklärt sie | **teilweise** | Erklärt auf Abschnittsebene: `uv run uc3 klass` und Frage „Was ist ÖNACE R?“ (F13). | Demo D3, Frage 7 |
| 3 Qualitätssicherung | Mindest | erkennt einen Teil der Fehler, Qualitätsbericht je Monat | **erfüllt** | 24 Berichte, 24 Prüfregeln (F15), acht Arten von Fehlern (F4 bis F11). | `/uc3/berichte/2025-03`, `abgabe/qualitaetsberichte/` |
| | Optimum | erkennt alle Fehler | **teilweise** | Der offizielle Bericht August 2024 stimmt ganz, 2.880 von 2.880 (F1). Für die anderen 23 Monate gibt es keinen Vergleich. Ob es alle Fehler sind, können wir nicht belegen. | Szene 5 und 6 |
| | Optimum | unterscheidet sie von echten Entwicklungen | **teilweise** | Jeder Befund trägt eine Einstufung. Ein Teil bleibt „nicht erklärbar“. Für die Rückfragen R1 bis R10 gilt je eine Annahme mit Beleg, die Rückfrage ist dokumentiert. Der Bericht Jänner 2025 nennt den Wechsel der Branchenliste nicht. | Demo D1, `abgabe/rueckfragen/` |
| | Optimum | jede Annahme begründet und dokumentiert | **erfüllt** | Annahmen F1 bis F10 je Monat im Bericht, Herleitung A1 bis A13 im Plan. Beispiel Geburtsmonat 13 (Beleg F4). | Szene 8, `docs/plan/uc3/annahmen.md` |
| 4 Reporting | Mindest | Aggregations-Sheet nach den Regeln der Fachbeschreibung | **erfüllt** | Sheet nach alten und neuen Regeln. Kernzahlen August 2024 exakt (F14). | `abgabe/aggregationen_v1.xlsx`, `abgabe/aggregationen_v2.xlsx` |
| | Optimum | Datenanfragen (können sich auch auf Klassifikationen und Metadaten beziehen) richtig beantwortet | **teilweise** | Acht geprüfte Fragen mit Sollzahl (F21 bis F25). Freie Fragen sind nicht alle geprüft. | Demo D3, `/uc3/fragen`, Fragenkatalog |
| | Optimum | Dashboard | **erfüllt** | Übersicht aller Monate mit Verlauf und Status. | `/uc3` |
| 5 Weiterentwicklung und Betrieb | Mindest | Produktion läuft deterministisch | **erfüllt** | 72 Wiederholungsläufe, 72-mal derselbe Hash (F16). Gemessen in der Abgabe-Datenbank. Eine frisch aufgesetzte Datenbank kennt nur Regelsatz v1. | `abgabe/uc3-abnahme.md`, Abschnitt 3 |
| | Optimum | alle Änderungsaufträge und Ministeriums-Lieferung umgesetzt | **erfüllt** | Drei Aufträge (F19). Lieferung 07/2026 mit 32.741 Personen. | `/uc3/freigaben`, `abgabe/ministerium_2026-07.beleg.md` |
| | Optimum | nachvollziehbar protokolliert | **erfüllt** | Jede Änderung mit Anweisung, Name und Zeit (F26). Die Vorschläge 24 bis 26 hat eine KI-Sitzung in Bernhards Auftrag eingegeben, er hat sie um 18:22 bestätigt. Das steht offen im Protokoll. | `abgabe/protokoll.md` |
| | Optimum | Live-Änderung per Sprache gelingt | **teilweise** | Getippter Satz, keine Stimme. Geprobt sind Änderungen an vorhandenen Regelwerten. Unbekannte Aufträge sind auf `main` nicht abgesichert. | Demo D2, Fragenkatalog Teil B |
| 6 Bedienbarkeit | Mindest | alles lässt sich über die Konsole steuern: Läufe starten, Ergebnisse und Qualitätsberichte ansehen, Änderungen freigeben | **erfüllt** | Alles über einen Befehl. | `uv run uc3 --help`, `uc3/statagent/cli.py` |
| | Optimum | übersichtliche Weboberfläche für Läufe, Qualitätsberichte und Annahmen, Klassifikationen, Freigaben und Fragen an die Daten | **erfüllt** | Alle sechs Inhalte sind im Web. Annahmen stehen im Bericht, Klassifikationen unter dem Menüpunkt „Regeln“. Aufträge gibt man nur in der Konsole ein. | `/uc3`, `/uc3/berichte/2025-03`, `/uc3/klassifikationen`, `/uc3/freigaben`, `/uc3/fragen` |

## So benutzen wir die Karte am Tisch

Die Karte liegt ausgedruckt vor der Jury. Bei einer Frage zeigt Bernhard auf die Zeile, nennt die Zahl und öffnet die Stelle. „Teilweise“ und „offen“ sagt er von sich aus.

## Vor dem Druck (nicht mit ausdrucken)

Die Karte zeigt nur, was auf `main` ist. Nach jedem dieser Merges die Zeile neu messen und die Kopfzeile mit dem Commit anpassen, dann drucken:

- !193 (5-Steller, Bezirke, Gemeinden): Bereich 2, Bereich 4 Datenanfragen
- !150 (unbekannte Live-Änderungen): Bereich 5 Live-Änderung
- !179 (frische Datenbank kennt v2): Bereich 5 Mindest
- Pensionen (#77): Bereich 1
- !196 (Menü mit Annahmen und Klassifikationen, neue Seite `/uc3/annahmen`): Bereich 6 lautet dann „Alle sechs Inhalte sind im Web. Annahmen und Klassifikationen sind eigene Menüpunkte. Aufträge gibt man nur in der Konsole ein.“, unter „Wo zu sehen“ kommt `/uc3/annahmen` dazu, auch bei Bereich 3 „jede Annahme“
