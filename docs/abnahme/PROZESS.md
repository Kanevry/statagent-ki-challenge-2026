# Abnahme-Prozess: jedes Kriterium mit Beleg, jede Stunde wiederholbar

Entwurf v0.1, 05.11.2026 17:22 (Europe/Vienna), b-abnahme-30. Zur Prüfung durch Fable 5.1 und Astra (Codex).

## Ziel

Zu jeder Zeit kann jemand ohne Rückfrage zeigen, welches Abnahmekriterium erfüllt ist, womit das gemessen wurde
und auf welchem main-Stand. Bis Fr 06:30 haben UC3 (bewertet) und E6 (Abgabe) kein Kriterium ohne Prüfung.

## Ausgangslage (gemessen)

- 140 Issues in Projekt 259. `tests/abnahme/matrix.py` zieht 245 Kriterien heraus (17:20): uc3 68, uc1 40, uc2 14,
  plattform 123. Davon 167 als Checkbox, der Rest als Text unter Überschriften wie „Messbare Abnahmen“,
  „Akzeptanzkriterien“, „Fertig, wenn“. Abgehakt: 0.
- Bisher geprüft wurde einzeln je Issue mit einem Protokoll (#63, #64, #66, #95). Das ist gut belegt, aber nicht
  wiederholbar: nach jedem Merge kann ein Urteil falsch werden, und niemand merkt es.
- Die Bau-Lanes haken nie selbst ab. Prüfer ist allein die Abnahme-Lane.

## Grundidee

Drei getrennte Teile. Jeder Teil hat genau eine Quelle.

| Teil | Quelle | Wer schreibt |
|---|---|---|
| Kriterium (was gilt) | Issue-Beschreibung in GitLab; ID `<iid>-<n>`, dazu ein Hash des Wortlauts | Lead und Lanes im Issue |
| Prüfsatz (wie man misst) | `tests/abnahme/pruefungen/<bereich>.toml`, ein Eintrag je Kriterium | nur die Abnahme-Lane |
| Ergebnis (was gemessen wurde) | `docs/abnahme/lauf.jsonl` (automatisch) und `docs/abnahme/belege.jsonl` (von Hand) | der Lauf und der Prüfer |

Die Matrix `docs/abnahme/matrix-<bereich>.md` und der Zähler werden daraus erzeugt, nie von Hand geschrieben.

## Prüfsatz

```toml
[[pruefung]]
id = "70-2"                 # Kriterium
hash = "1a2b3c4d5e"         # Wortlaut, für den der Prüfsatz geschrieben wurde
art = "befehl"              # befehl | hand
befehl = "timeout 120 uv run python tests/abnahme/p/uc3_juli.py"
erwartet = ["^insgesamt 407604$"]   # alle Regexe müssen in der Ausgabe stehen
schwer = false              # true: braucht DB, Docker oder Lauf, läuft nur auf dem Prüfrechner
quelle = "Orakel bb, Tabelle 1"     # woher der Sollwert stammt
```

- `art = "befehl"`: der Lauf führt den Befehl aus und urteilt mechanisch.
- `art = "hand"`: für das, was kein Befehl messen kann (Screenshot gegen Pen-Frame, Sprache, Ablauf mit
  Stimme). Der Prüfer schreibt einen Beleg mit `pfade = [...]`. Der Beleg gilt, bis sich auf main unter
  diesen Pfaden etwas ändert. Danach steht das Kriterium wieder auf „nicht geprüft (veraltet)“.
- Ändert sich der Wortlaut im Issue, passt der Hash nicht mehr: „nicht geprüft (Kriterium geändert)“, bis der
  Prüfsatz angepasst ist.
- Sollwerte kommen aus einer genannten Quelle (Orakel bb, Aufgabenstellung, Issue), nie aus dem Code, der
  geprüft wird.

## Urteil (mechanisch, streng)

| Fall | Stand |
|---|---|
| Befehl lief, Exit wie erwartet, alle Regexe gefunden | bestanden |
| Befehl lief, ein Regex fehlt oder Exit falsch | nicht bestanden |
| Zeitlimit, Befehl nicht startbar (Exit 124, 126, 127), Prüfrechner nicht erreichbar | nicht geprüft (Lauf-Fehler) |
| kein Prüfsatz | nicht geprüft (kein Prüfsatz) |
| Hand-Beleg veraltet oder Hash geändert | nicht geprüft (mit Grund) |
| Label `prio::nach-abgabe` und nicht bestanden | nach Abgabe |

Ein Lauf-Fehler wird nie als „nicht bestanden“ gezählt und nie als „bestanden“. Es gibt kein Raten und kein
„sieht richtig aus“.

## Der Lauf

`uv run python tests/abnahme/pruefen.py [--schwer] [--bereich uc3] [--id 70-2]`

1. `git fetch`, main-SHA festhalten.
2. Sauberer Schnappschuss von main (`git archive` in ein eigenes tmp-Verzeichnis, `uv sync --frozen`; gemessen
   0,4 s). Kein `.env.local`, keine Modellschlüssel: Prüfungen laufen ohne Geheimnisse und ohne Sprachmodell.
3. Jeden leichten Prüfsatz ausführen, mit Zeitlimit; mit `--schwer` auch die schweren (nur auf dem
   Prürechner, gegen die Prüf-DB auf Port 5444, nie gegen eine Bau-DB).
4. `lauf.jsonl` neu schreiben: je Kriterium Stand, Befehl, Ausgabe-Auszug, Dauer, SHA, Uhrzeit.
5. Matrix und Zähler neu erzeugen.
6. Änderungsliste gegen den letzten Lauf: neu bestanden, neu nicht bestanden, Rückfall (war bestanden, jetzt
   nicht).

## Rhythmus

| Was | Wann | Wo |
|---|---|---|
| leichter Lauf | jede Stunde zur Minute :50, Dauer unter 5 min | M4, Schnappschuss |
| schwerer Lauf | alle 3 Stunden und nach jedem Merge unter `uc3/` | Prüfrechner, Prüf-DB 5444 |
| Zähler an den Lead | 19:00, 20:00, 23:00, 02:00, 05:00 aus dem letzten Lauf | SendMessage |
| Tor | Fr 06:30 | UC3 und E6 ohne „nicht geprüft“ |

## Wirkung nach außen (nur bei Wechsel, kein Rauschen)

- Neu bestanden: Checkbox im Issue abhaken und ein Kommentar mit Befehl, Ausgabe und SHA
  (`matrix.py abhaken <id> --ja`; das Skript verweigert ohne gültigen Beleg).
- Rückfall: Haken entfernen, Kommentar mit Befund, eine Zeile an die Lane, bei UC3 und E6 auch an den Lead.
- Neu nicht bestanden: Kommentar mit Datei:Zeile, erwartet, gemessen; eine Zeile an die Lane.
- Matrix und Prüfsätze gehen gesammelt als MR über die Review-Bank, nicht stündlich. Die Wahrheit für den
  Augenblick stehen in den Issues und im Zähler.

## Vier-Augen und Stichprobe

- Prüfsätze schreiben Agents (Sonnet) als Vorschlag. Ich prüfe jeden fünften und jeden mit einer Abgabezahl
  selbst nach, bevor er in die Datei kommt.
- Jeder Prüfsatz wird einmal gegen einen absichtlich falschen Stand gefahren (Sollwert verändert): Er muss dann
  „nicht bestanden“ liefern. So fällt ein Regex auf, der immer passt.

## Einführung in Stufen

1. Heute bis 19:00: Format, `pruefen.py`, UC3-Prüfsätze aus der laufenden Messung, ein Lauf von Hand,
   Ergebnis mit dem Urteil der Messer abgleichen.
2. Ab 19:50: stündlicher Lauf aus dieser Session.
3. Bis 23:00: E6 und UC4, danach UC1, UC2, E5, E0.
4. Schwere Prüfsätze für UC3 (Golden Set, 24 Läufe, Abgabezahlen gegen Orakel) als ein Skript auf dem
   Prüfrechner.
5. Nach der Abgabe: Lauf als geplante CI-Pipeline; neue Issues schreiben den Prüfsatz gleich mit (Definition of
   Done).

## Offene Fragen an die Prüfer

- Ist die Trennung Kriterium / Prüfsatz / Ergebnis die einfachste, die trägt?
- Ist das Urteil streng genug, ohne bei Lauf-Fehlern falsche Alarme zu erzeugen?
- Was fehlt für die Jury-Sicht (Bewertungsraster UC3, 120 Punkte)?
- Wo ist das zu viel für die verbleibenden 15 Stunden?
