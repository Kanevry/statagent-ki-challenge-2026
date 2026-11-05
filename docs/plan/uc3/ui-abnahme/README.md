# UI-Abnahme UC3 (lokal, gefüllte Datenbank)

Die CI hat keine UC3-Datenbank. Der Job `playwright` misst dort nur die Leerzustände der UC3-Seiten. Diese Abnahme
misst die gefüllten Seiten gegen die maßgebliche UC3-Datenbank (lokale UC3-Datenbank, 24 Monate Regelsatz v1),
lokal mit dem Dev-Server. Nachstellen: Dev-Server mit `UC3_DATABASE_URL` auf diese Datenbank starten, dann
`node docs/plan/uc3/ui-abnahme/abnahme.mjs http://localhost:<port>`.

Gemessen am 05.11.2026 gegen 16:47 (Review !51 Runde 2), 22 von 24 Monaten veröffentlicht.
Rohdaten: `messung.json`. Screenshots: `<seite>-1440.jpg` (1440×900) und `<seite>-390.jpg` (390×844), jeweils
der sichtbare Ausschnitt oben.

## Ergebnis

| Seite | Route | HTTP | Schablonen-Treffer (12 Schlüssel) | axe critical/serious | Überlauf `main` | Zahlen ohne Beleg | Beleg-Chips | Konsolenfehler |
|---|---|---|---|---|---|---|---|---|
| Monatsläufe | `/uc3` | 200 / 200 | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 | 49 | 0 |
| Lauf März 2025 | `/uc3/laeufe/2025-03` | 200 / 200 | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 | 20 | 0 |
| Lauf Oktober 2025 (angehalten) | `/uc3/laeufe/2025-10` | 200 / 200 | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 | 20 | 0 |
| Qualitätsberichte | `/uc3/berichte` | 200 / 200 | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 | 3 | 0 |
| Qualitätsbericht Oktober 2025 | `/uc3/berichte/2025-10` | 200 / 200 | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 | 13 | 0 |
| Regeln | `/uc3/berichte/regeln` | 200 / 200 | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 | 5 | 0 |
| Klassifikationen | `/uc3/klassifikationen` | 200 / 200 | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 | 13 | 0 |
| Freigaben, wartet | `/uc3/freigaben` | 200 / 200 | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 | 0 | 0 |
| Freigaben, erledigt | `/uc3/freigaben?reiter=erledigt` | 200 / 200 | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 | 0 | 0 |
| Fragen an die Daten | `/uc3/fragen` | 200 / 200 | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 | 0 | 0 |
| Fragen, Antwort Wien März 2025 | `/uc3/fragen` + Beispiel | 200 / 200 | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 | 1 | 0 |

Werte je Zelle: 1440 / 390. „Zahlen ohne Beleg“ zählt Zahlen ab 1.000 (ohne Datumsangaben), die im selben Abschnitt
(`section`, `header`, `article`) keinen Beleg-Chip haben. Die Freigaben-Seiten zeigen keine Zahl ab 1.000, weil die
maßgebliche Datenbank noch keinen Vorschlag mit Probe hat.

## Vergleich mit den Pen-Frames

Zuordnung: `web/tests/uc3-frame-matrix.json`. Verglichen wurden Inhalt, Reihenfolge und Hauptaussage je Screen,
nicht Pixel. Die Frames zeigen eine linke Leiste; die App nutzt die Unter-Navigation der Shell oben (Vertrag H).

| Frame | Screen | Urteil |
|---|---|---|
| iU5QZ, bgAUw | Monatsläufe | entspricht im Inhalt (Hauptzahl mit Beleg, Datenstand, angehaltene Monate, Tabelle je Monat); keine Kachelreihe mit Kennzahlen, statt dessen ein Hauptsatz |
| fFDc8 | Lauf-Detail 2025-03 | entspricht im Inhalt (Kennzahlen, Auffälligkeiten mit Einstufung, Bestand je Bundesland); Beispiel-IDs bewusst entfernt (keine Einzeldaten) |
| P6gBQD | Lauf 2025-10 angehalten | entspricht (Grund des Anhaltens als Überschrift, P15–P17, 78.949, „bleibt vorläufig, bis die Rückfrage R3 beantwortet ist“) |
| fJdk9, egqhg | Qualitätsbericht, Annahmen und Regeln | entspricht (fünf Abschnitte, „Annahme: …“ je Monat, Regeln mit Freigabestand) |
| XlcSB | Klassifikationen | entspricht teilweise: Vergleich ÖNACE 2008/2025 über den Namen, weil der Umsteigeschlüssel 2008→2025 in `stat.uebergang` noch fehlt |
| qVTQj, PPe1S, oBcQu | Freigaben | Leerzustand entspricht PPe1S; Karte in drei Zonen per Test belegt, im Browser erst mit einem Vorschlag samt Probe sichtbar |
| DbY1q | Fragen an die Daten | entspricht im Ablauf (Frage, Beispiele, Antwort als Satz mit Zahl, Beleg, eingeklappt SQL und Definition) |
| L6f3Mp | Abgabe und Export | nicht umgesetzt, die Abgabe läuft über die CLI |

## Bekannt und bewusst

- Die Demo-Ansicht schaltet mit der Taste D ohne Zusatztaste (WCAG 2.1.4 verlangt abschaltbare Ein-Zeichen-Kürzel).
  Sie wirkt nicht in Eingabefeldern und ändert nur die Schriftgröße; für die Vorführung bleibt die einfache Taste.
- Der App-Header (E0) scrollt bei 390 px seitlich; gemessen ist nur `main`.
