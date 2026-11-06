# Schlusslauf der Abnahme: Fr 06.11.2026 ab 06:30 (Abgabe-Beleg)

Voller Abnahme-Lauf gegen den eingefrorenen main direkt nach dem Merge-Stopp 06:30, Anweisung des Leads 05.11. 21:2x.
Wer ihn fährt, braucht nur diese Datei und `PROZESS.md`.

## Zeitplan (gemessen am 05.11.)

| Schritt | Dauer | Fertig ab 06:30 |
|---|---|---|
| leichter Lauf (Arbeitsrechner) | rund 3 min | 06:35 |
| schwerer Lauf (Prüfrechner, frische Prüf-DB, 24 Läufe, alle schweren Prüfsätze, ab 06:30 parallel zum leichten) | 30 min auf dem Ersatzrechner (gemessen 06.11. 01:50 bis 02:17 und Prüfsätze 8 min); auf dem Zweitrechner 15 bis 20 min | 07:00 |
| Veröffentlichen, Tor, Tabelle an den Lead | rund 3 min | 07:03 |
| danach: 22-1 voll, eigener Lauf (24 Läufe v2, Sheet, Ministerium) | 26 min auf dem Ersatzrechner (gemessen 02:17 bis 02:43) | rund 07:30, Nachtrag an den Lead |

Die Spanne hängt an der Last auf dem Prüfrechner (`uc3 lauf --alle`: 483 und 830 s). Beide Läufe starten gemeinsam,
der schwere wartet nicht auf den leichten. Reißt die Verbindung ab, läuft der schwere Lauf auf dem Prüfrechner weiter.
Scheitert er, reicht die Zeit bis 07:30 für einen zweiten Versuch.

## Vorbereitung

1. Bis 06:00: Wächter läuft (`pgrep -fl waechter.sh`), Prüf-DB ist seit dem letzten schweren Lauf unberührt.
2. **Prüf-DB ab 06:15 reserviert.** Niemand sonst schreibt hinein. Vorher fragen alle anderen (UI-Regie) nach einem
   Fenster; ein Fenster sperrt schwere Läufe per `mkdir /tmp/kic-abnahme-schwer.lock`, Freigabe per `rmdir`.
3. 05:00: Vorprüfung `uv run python tests/abnahme/matrix.py tor`, offene Punkte an den Lead.
4. **Ab 06:05 keine schweren Läufe mehr.** Ein Merge kurz vor 06:30 löst sonst über den Wächter einen schweren Lauf auf
   dem vorletzten Stand aus, der die Prüf-DB bis nach 06:45 belegt. Deshalb um 06:05 die Sperre nehmen
   (`mkdir /tmp/kic-abnahme-schwer.lock`); läuft noch einer, sofort nach seinem Ende. Um 06:30 `rmdir`, dann der Ablauf.
5. Vor dem Lauf: Sperre frei (`ls -d /tmp/kic-abnahme-schwer.lock` meldet „No such file“), kein Merge mehr nach 06:30.
   Der Lead nennt den Merge-Stopp-SHA.

## Ablauf ab 06:30

Im Worktree der Abnahme, Branch mit dem aktuellen Stand von `tests/abnahme`:

```
git fetch origin && git log --oneline -1 origin/main     # muss der Merge-Stopp-SHA sein
: > /tmp/kic-abnahme-schwer.letzter                       # erzwingt den schweren Lauf
bash tests/abnahme/schwer_ausloesen.sh "$ABNAHME_PRUEFRECHNER_ENV" &   # startet gleich, wartet nicht auf den leichten
uv run python tests/abnahme/pruefen.py                    # leicht, schreibt docs/abnahme/laeufe/<zeit>-<sha>.jsonl
wait
uv run python tests/abnahme/matrix.py schreiben
uv run python tests/abnahme/matrix.py befunde --bereich uc3 --ja     # ebenso uc1, uc2, plattform
uv run python tests/abnahme/matrix.py abhaken alle --ja
uv run python tests/abnahme/matrix.py haken pruefen --ja
uv run python tests/abnahme/matrix.py tor                 # Tor UC3 und E6
uv run python tests/abnahme/matrix.py zaehler             # Meldung an den Lead
bash tests/abnahme/schwer_ausloesen.sh "$ABNAHME_PRUEFRECHNER_ENV" 22-1   # danach, Nachtrag an den Lead
```

`ABNAHME_PRUEFRECHNER_ENV` zeigt auf die env-Datei außerhalb des Repos (Rechte 600), Pfad in der Übergabe.

Danach: Sweep auf Rechnernamen und Pfade (`PROZESS.md`), Laufdateien und Matrix committen, MR an die Review-Bank, und
Zähler, Tor-Ergebnis und die beiden Laufdateien als Abgabe-Beleg an den Lead.

## Ersatzrechner

Fällt der Zweitrechner aus, zeigt die env-Datei auf einen Ersatz (Entscheid #92). Dort gilt: eigener Ordner, eigenes
Compose-Projekt, Port nur auf Loopback und von außen nachgeprüft, höchstens 6 Kerne und 6 GB, `nice`, mindestens 23 GiB frei
beim Start, Abbruch unter 12 GiB, danach restlos abräumen. Die Tabelle nennt den Rechner, auf dem gemessen wurde.

## Was der Beleg zeigt

- Laufdatei leicht und schwer auf demselben Merge-Stopp-SHA, jede mit Manifest und Schlusszeile.
- Tor: In UC3 und E6 ist jedes Kriterium bestanden, nach Abgabe oder per Entscheid angenommen. Offen Gebliebenes steht
  sichtbar mit Grund in der Ausgabe von `tor`.
- 92-3 (Transfernachweis) ist erst nach dem Upload messbar; danach einmal `pruefen.py --id 92-3`.

## Fallen

- Ein Befundtext kann alt sein: Bei jedem unerwarteten „nicht bestanden“ erst Befehl und Ausgabe in der Laufdatei lesen,
  dann gegen main nachsehen, dann erst an eine Lane melden. Am 05.11. waren so über ein Dutzend Befunde falsch.
- Rein leichte Prüfsätze laufen nie auf dem Prüfrechner, schwere nie auf dem Arbeitsrechner.
- Verworfene Belege (`verworfen.jsonl`) melden, sie können ein altes „bestanden“ wieder gültig machen.
