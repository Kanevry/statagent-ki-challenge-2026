# UC2 Scope-Abgleich: sechs Themen der Aufgabenstellung gegen den Stand im Repo

Issue #87, Kind von Epic #24. Stand: 05.11.2026, Basis `main`. Jede Aussage hier hat einen Beleg im Code oder in
einem Issue. Was nicht belegt ist, steht nicht drin. Diese Datei ändert keinen Code.

## Entscheid zum Spieltheoriemodus

Die Aufgabenstellung nennt den spieltheoretischen Modus als Möglichkeit ("können"), nicht als Pflicht. Der
optionale Spieltheoriemodus ist für diese Abgabe zurückgestellt. Es gibt dazu weder Code noch Daten noch eine
Oberfläche. Eine Pflicht ist daraus nicht entstanden, und kein neues Issue ersetzt #40 bis #49. Der Entscheid
steht schon im Plan (`docs/plan/uc2/2026-11-05-healthpolicy-simulator.md`, Abschnitt Out-of-Scope und Risiko-Tabelle).
Diese Datei macht ihn prüfbar.

Die Verhandlung selbst gehört nicht zur Spieltheorie. Sie läuft seit #44 mit Moderator, Runden, Zugschema und
Ereignisprotokoll (`uc2/src/uc2/verhandlung/`).

## Scope-Matrix: sechs Themen

Erlaubte Werte in der Spalte Status: umgesetzt, teilweise oder zurückgestellt.

| Thema | Status | Begründung | Verweis |
|---|---|---|---|
| Strategische Vorteile | teilweise | Je Thema steht fest, wer dafür und wer dagegen ist, mit Begründung und Beleg. Das Rechenmodell nennt Wirkung und Mehrkosten einer Maßnahme als Spanne. Ein eigener Vergleich "Vorteil je Akteur" fehlt. | #42, #44, #45, `uc2/src/uc2/experte/modell.py`, `uc2/src/uc2/verhandlung/matrix.py` |
| Verhandlungsmacht | zurückgestellt | Das Thema gehört zum optionalen Spieltheoriemodus (BATNA, Ausweichoption). Dafür gibt es weder Code noch Daten. Der Institutionsfaktor in der Belegsuche gewichtet nur die Relevanz von Belegen und misst keine Macht. | #87, #43, `docs/plan/uc2/2026-11-05-healthpolicy-simulator.md` |
| Koalitionsmöglichkeiten (Koalition) | teilweise | Die Positionsmatrix nennt je Thema, wer zustimmt, ablehnt oder sich enthält. Jeder Zug speichert, auf wen er eingeht (`bezug_auf`). Ein Ereignis "koalition" und eine Koalitionsansicht gibt es nicht. Belegte Koalitionsereignisse folgen mit #85 nach der Abgabe. | #85, `uc2/src/uc2/verhandlung/matrix.py`, `uc2/src/uc2/akteure/zug.schema.json` |
| Abhängigkeiten | teilweise | Jeder Zug kann Bedingungen nennen. Der Lauf sammelt sie je Akteur und Thema. Abhängigkeiten zwischen Akteuren oder Maßnahmen werden nicht berechnet. Offene Bedingungen als Handlungsempfehlung folgen mit #86 nach der Abgabe. | #86, #44, `uc2/src/uc2/verhandlung/lauf.py`, `uc2/src/uc2/akteure/zug.schema.json` |
| Anreize | teilweise | Jeder Zug kann ein Zugeständnis nennen. Der Bericht zeigt es an. Anreize mit Auszahlungen oder Optimierung gibt es nicht, das wäre Spieltheorie. | #44, `uc2/src/uc2/verhandlung/ausgabe.py`, `uc2/src/uc2/akteure/zug.schema.json` |
| Kooperations- und Blockaderisiko | teilweise | Die Einordnung je Thema (Konsens, Mehrheit, abgelehnt, offener Konflikt, mit Minderheit) zeigt, wo es hakt. Einen Risikowert oder eine Vorhersage von Blockaden gibt es nicht. Das Issue dazu (#45) ist noch nicht abgeschlossen. | #45, `uc2/src/uc2/verhandlung/matrix.py` |

## Getrennt davon: Koalitionsereignisse und spieltheoretische Zahlen

Zwei Dinge werden nicht vermischt.

- **Belegte Koalitionsereignisse** (#85): Zwei oder mehr Institutionen haben dasselbe Thema, eine kompatible
  Haltung und gehen ausdrücklich aufeinander ein. Das ist eine Auswertung des vorhandenen Verhandlungsprotokolls.
  Sie braucht kein Modell und keine Auszahlungen.
- **Numerische Auszahlungen und Optimierung** (Spieltheorie): Gleichgewichte, Auszahlungsmatrizen, BATNA als Zahl.
  Das ist der optionale Modus. Er ist zurückgestellt, und #85 baut ihn nicht nach.

Wer #85 abnimmt, nimmt also keinen Spieltheoriemodus ab.

## Zusätzliche Scope-Zeilen: SozDok und historische Pressearbeit

Diese zwei Zeilen haben eigene Angaben und hängen nicht an der Spieltheorie-Rückstellung.

| Thema | Einordnung | Begründung | Verweis |
|---|---|---|---|
| SozDok (`svbox/uc2/Rechtstexte`) | bereitgestellte Quelle, bisher nicht indiziert | Der Ordner liegt in der SV-Box bereit. Der UC2-Index liest nur den Pressespiegel (`UC2_PRESSE`). Der Plan grenzt den SozDok-Index ab. Eine spätere Datenanreicherung läuft über #25. UC1 nutzt die Rechtstexte in seinem eigenen Index. | #25, `docs/plan/uc2/2026-11-05-healthpolicy-simulator.md`, `uc2/README.md` |
| Historische Pressearbeit | wird über #84 weitergeführt | Die Rückstellung der Spieltheorie streicht keine historischen Positionen. Das Pressearchiv vor 2026 kommt mit #84 nach der Abgabe, zuerst als kleines festgehaltenes Sample. Die Beispieldatei dazu (`uc2/config/historisches-sample.json`) gibt es noch nicht. | #84, #40, #43 |

## Fundstellen und Bewertung

Suche im ganzen Repo ohne diese Datei: `rg -n -i "Spieltheor|BATNA|Koalition"`. Es gibt drei Treffer, alle im Plan.
In `uc2/README.md`, `README.md`, `web/` und `uc2/src/` gibt es keinen Treffer.

| Fundstelle | Inhalt | Bewertung |
|---|---|---|
| `docs/plan/uc2/2026-11-05-healthpolicy-simulator.md:177` | Koalitionsansicht als Wunsch (Akteure mit gleicher Richtung auf mindestens 2 Themen) | Richtig. Es ist ein Wunsch und keine Funktion. Im Code gibt es keine Ansicht dazu. Folgearbeit ist #85. |
| `docs/plan/uc2/2026-11-05-healthpolicy-simulator.md:197` | Spieltheoretischer Modus (Verhandlungsmacht, BATNA, Blockaderisiken) im Abschnitt Out-of-Scope, Koalitionen nur als Wunsch | Richtig. Passt zu dieser Matrix. |
| `docs/plan/uc2/2026-11-05-healthpolicy-simulator.md:394` | Risiko-Tabelle: "Spieltheorie-Modus nachrüsten", nicht in dieser Runde, Defer | Richtig. Passt zu dieser Matrix. |

Ergebnis: Keine Fundstelle sagt, ein Spieltheoriemodus sei fertig. Die Hinweistexte von UC2 (`uc2/README.md`) behaupten
auch keinen. Eine Änderung an Code, README oder Web ist deshalb nicht nötig.

## Prüfung

Die Abnahme prüft diese Datei maschinell (Abschnitte 87-1 bis 87-3). Zählregeln, die beim Pflegen zu beachten sind:

- Genau 6 Tabellenzeilen tragen eines der drei Statuswörter. Weitere Tabellen nutzen andere Wörter.
- Mindestens 6 Tabellenzeilen haben einen Issue-Verweis oder einen Pfad.
- Ein Satz, der Spieltheorie oder BATNA als fertig beschreibt, ist nicht erlaubt.
