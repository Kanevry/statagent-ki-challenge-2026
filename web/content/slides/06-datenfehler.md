---
nummer: 6
titel: Acht Datenfehler, nichts gelöscht
layout: tafel
zeit: "3:15–4:15"
dauer_s: 60
bereiche: [Datenmanagement, Qualitätssicherung]
screenshot: SC6
pen_frame: Zzdmf
belege: [F4, F5, F6, F7, F8, F9, F10, F11]
---

# Acht Datenfehler, nichts gelöscht

| Befund | Lieferung | Umfang | Was das Programm tut |
|---|---|---|---|
| Geburtsmonat 13 | 2024-08 | 370 Verhältnisse | Alter aus dem Geburtsjahr |
| Alter 117 bis 153 Jahre | 2024-08 | 7 Verhältnisse | zählt als Alter unbekannt |
| Alte Branchencodes (ÖNACE 2003) | 2024-08 | 50 Verhältnisse | zählt zu C, Herstellung von Waren |
| Bundesland und Branche leer | 2024-08 | 1.996 Verhältnisse | zählt als unbekannt |
| Doppelte Zeilen | 2025-03 | 1.663 Zeilen | zählt einmal |
| Freie Dienstverträge fehlen | 2025-03 | 1.492 Verhältnisse | hält den Monat an, fragt nach |
| Beginn und Ende vertauscht | 2025-06 | 388.115 Zeilen ohne Beginn | tauscht die Spalten zurück |
| Teil-Lieferung | 2025-10 | 78.949 Verhältnisse fehlen | hält den Lauf an, fragt nach |

Jeder Befund steht mit Abfrage und Einstufung im Qualitätsbericht des Monats.

Herkunft: Qualitätsberichte 2024-08, 2025-03, 2025-06 und 2025-10. Die 388.115 stehen in `docs/plan/uc3/annahmen.md` A6 (Regel E01). Der Bericht 2025-06 nennt 432.086 getauschte Sätze.

## Sprechernotizen

Wir haben acht Datenfehler gefunden. Gelöscht haben wir keinen. Erstens: 370 Beschäftigungsverhältnisse haben Geburtsmonat 13. Zweitens: Sieben Verhältnisse haben ein Alter von 117 bis 153 Jahren. Drittens: 50 Verhältnisse tragen Branchencodes von 2003. Viertens: Bei 1.996 fehlen Bundesland und Branche. Das sind Zahlen für August 2024. Fünftens: Im März 2025 sind 1.663 Zeilen doppelt. Sechstens: Im selben Monat fehlen 1.492 freie Dienstverträge. Siebtens: Im Juni 2025 sind Beginn und Ende vertauscht, bei 388.115 Zeilen. Achtens: Im Oktober 2025 fehlen 78.949 Verhältnisse. Bei Fehler sechs und acht hält das Programm den Monat an. Alles steht im Qualitätsbericht.
