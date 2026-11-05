# Abnahme-Prozess: jedes Kriterium mit Beleg, bei jedem neuen main wiederholt

Stand v0.2, 05.11.2026 17:43 (Europe/Vienna), b-abnahme-30. Geprüft von Fable 5.1 und Astra (Codex, gpt-6-astra)
unabhängig voneinander; was übernommen und was verworfen wurde, steht unten.

## Ziel

Zu jeder Zeit kann jemand ohne Rückfrage zeigen, welches Abnahmekriterium erfüllt ist, womit das gemessen wurde
und auf welchem main-Stand. Vor dem Merge-Stopp Fr 06:30 ist in UC3 (bewertet) und E6 (Abgabe) jedes Kriterium
bestanden, verschoben oder als Restmangel entschieden.

## Bausteine

| Teil | Datei | Wer schreibt |
|---|---|---|
| Kriterium | Issue-Beschreibung in GitLab; ID `<iid>-ACn` (Marke im Text) oder `<iid>-<n>`; Hash über den ganzen Block | Lead und Lanes im Issue |
| Prüfsatz | `tests/abnahme/pruefungen/<bereich>.toml` | nur die Abnahme-Lane |
| Prüfskript | `tests/abnahme/p/*.py`, Sollwerte in `tests/abnahme/orakel/` | nur die Abnahme-Lane |
| Lauf | `docs/abnahme/laeufe/<zeit>-<sha>.jsonl`, eine Datei je Lauf, nie geändert | `pruefen.py` |
| Hand-Beleg | `docs/abnahme/belege.jsonl` | Prüfer (Mess-Agents nur als Vorschlag) |
| Entscheid | `docs/abnahme/entscheide.jsonl` (verschoben oder Restmangel, mit Quelle) | Lead oder Owner, eingetragen von der Abnahme |
| Matrix, Zähler, Tor | `docs/abnahme/matrix-<bereich>.md`, `matrix.py zaehler`, `matrix.py tor` | erzeugt, nie von Hand |

## Befehle

```
uv run python tests/abnahme/pruefen.py [--bereich uc3] [--id 70-AC2] [--schwer] [--gegenprobe]
uv run python tests/abnahme/matrix.py schreiben | zaehler | tor | befunde [--ja] | abhaken <id> [--ja]
bash tests/abnahme/waechter.sh          # startet den leichten Lauf bei jedem neuen origin/main
```

## Der Lauf

1. Abzug: Prüfling ist main an der vollen SHA (`git archive`, `uv sync --frozen`, `pnpm install --offline`,
   gemessen 2 s). Prüfwerkzeug ist `tests/abnahme` aus dem Abnahme-Commit. Beide SHAs stehen im Laufmanifest.
2. Im Abzug gibt es keine `.env.local`. Datenbank-Variablen zeigen auf einen gesperrten Port, `LLM_PROVIDER` ist
   gesperrt. Was eine DB, Docker, einen Browser oder ein Modell braucht, ist `schwer = true` und läuft nur auf
   dem Prüfrechner gegen die Prüf-DB (Port 5444), nie gegen eine Bau-DB.
3. Urteil je Prüfsatz, mechanisch:

| Fall | Urteil |
|---|---|
| Exit wie erwartet (Standard 0) und jeder Regex (MULTILINE, nur stdout, Farbcodes entfernt) gefunden | bestanden, bei `deckung = "teil"` nur „nicht geprüft (Teil erfüllt)“ |
| Exit falsch oder ein Regex fehlt | nicht bestanden, mit `befund_art` fehlt oder abweichend |
| Exit 124, 126, 127 oder Ausgabe zeigt fehlende DB, Modell, Paket | nicht geprüft (Lauf-Fehler), sofort nachsehen |
| Prüfsatz ungültig (Regex kaputt, verneinende Suche, Feld fehlt) | nicht geprüft (Prüfsatz ungültig) |
| `zeitlimit_ist_befund = true` und Zeitlimit | nicht bestanden (ein Hänger ist dann ein Produktfehler) |

4. Mehrere Prüfsätze je Kriterium: ein Teil nicht bestanden heißt Kriterium nicht bestanden. Bestanden nur, wenn
   ein voller Prüfsatz besteht und kein Teil scheitert.
5. Jeder wichtige Prüfsatz hat eine `gegenprobe` mit falschem Soll; `--gegenprobe` verlangt, dass sie scheitert.

## Wann ein Beleg gilt

- Hash des Kriteriums gleich, sonst „nicht geprüft (Kriterium geändert)“.
- main hat sich seit dem Messstand in den Pfaden des Bereichs nicht geändert (UC3: `uc3/`, `abgabe/`,
  `docs/plan/uc3/`, UC3-Web und alles Gemeinsame wie `shared/`, Lockfiles). Sonst „nicht geprüft (veraltet)“
  mit dem letzten Urteil im Grund.
- „Bestanden“ zählt nur aus einem Lauf oder vom Prüfer selbst. Ein Mess-Agent liefert Vorschläge.
- Bei mehreren Belegen gewinnt die jüngste Messzeit.

## Zuständigkeiten (RACI)

| Aufgabe | Verantwortlich | Entscheidet | Gefragt | Informiert |
|---|---|---|---|---|
| Kriterium formulieren und ändern (in der Beschreibung, nicht im Kommentar) | Lane | Lead | Abnahme | Review-Bank |
| Prüfsatz schreiben | Mess-Agent (Vorschlag), Abnahme | Abnahme | Lane | |
| Messen | `pruefen.py`, Wächter | Abnahme | | |
| Urteil, Haken, Kommentar | Abnahme | Abnahme | | Lane |
| Fix | Lane | Lead (Merge) | Abnahme | Review-Bank |
| Verschieben oder Restmangel annehmen | Lead | Lead oder Owner | Abnahme | Präsentation |

Eskalation: nicht bestanden bei einer Abgabezahl, bei E6 oder ein Rückfall in UC3 sofort an Lane und Lead.
Sonst an die Lane; ohne Reaktion nach 90 Minuten an den Lead.

## Definition of Done je Kriterium

Bestanden auf gültigem Stand, Haken im offenen Issue (geschlossene Issues: Matrix genügt), Kommentar mit Befehl,
Ausgabe und SHA (Marke im Kommentar, wiederholbar). Fix-MRs nennen `Abnahme: <id>` in der Beschreibung. Ein
geschlossenes Issue, ein grüner MR oder ein Haken allein sind kein Beleg.

## Rhythmus

| Was | Wann | Wo |
|---|---|---|
| leichter Lauf | bei jedem neuen origin/main (Wächter, Blick alle 5 min) | M4, Abzug |
| schwerer Lauf UC3 (Golden Set, 24 Läufe, Abgabezahlen gegen Orakel, Ministerium) | nach dem Merge von !50, dann nach gebündelten UC3-Merges, höchstens einer gleichzeitig | Prüfrechner, Prüf-DB 5444 |
| Befunde und Haken | nach jedem Lauf mit Wechsel, durch den Prüfer | GitLab |
| Zähler an den Lead | 19:00, 20:00, 23:00, 02:00, 05:00 | SendMessage |
| Vorprüfung Tor | 05:00 | |
| Schlusslauf leicht und schwer | auf dem Merge-Stopp-SHA ab 06:30 | M4 und Prüfrechner |

## Was aus den Reviews übernommen wurde

| Befund | Quelle | Umsetzung |
|---|---|---|
| Beleg veraltet nie | Fable K1, Astra 1 | Gültigkeit über Pfade des Bereichs |
| Agent-Urteil zählt als bestanden | Fable K2 | nur Vorschlag; Beispiel 13-AC4: zwei Teile waren nicht gemessen |
| Regex unterbestimmt | Fable K3, Astra 7 | Exit Pflicht, MULTILINE auf stdout, keine verneinende Suche, Farbcodes entfernt |
| Hash nur erste Zeile | Astra 2 | Hash über den ganzen Block |
| ID nach Position | Fable H1, Astra 6 | ID aus Marke ACn, sonst Rückgriff über Issue und Hash |
| Abhaken überschreibt fremde Änderungen | Fable H2, Astra 3 | frisch lesen, nie aus Cache, danach prüfen, dass alle anderen Kriterien gleich sind |
| Tor zu schwach oder unerreichbar | Fable H3, Astra 4 | Tor mit Entscheiden, Entschiedenes bleibt sichtbar, Zähler mit „fehlt auf main“ |
| Schwerer Lauf zu spät | Fable H4 | vorgezogen auf direkt nach !50 |
| DB-Fehler als Befund | Fable H5 | Lauf-Fehler |
| glab ohne Repo-Kontext | Fable M3 | `cwd` fest auf das Repo, Liste und doppelte iid geprüft |
| Läufe überschreiben sich | Astra 10 | eine Datei je Lauf mit Manifest und Schlusszeile |
| Zeitlimit kann Produktfehler sein | Astra 11 | `zeitlimit_ist_befund` je Prüfsatz |
| Auslöser Uhr statt Merge | Fable M6 | Wächter je neuem main |
| E6 im Zähler versteckt | Astra 15 | Zähler je Teil |

Nicht übernommen, mit Grund:
- Pfade je Beleg als Pflicht (Astra 9): ein Standard je Bereich reicht; nur Hand-Belege tragen eigene Pfade.
- Kommentare als Quelle des Wortlauts (Astra 2): Entscheide gehören in die Beschreibung (Fable M4); der Lead
  ändert dort, der Hash kippt, die Abnahme misst neu.
- Vollständiger Markdown-Parser, CI-Pipeline, TOML-Prüfsätze für UC1, UC2, E0, E5 heute (beide Streichlisten).

## Offen

- Raster-Zuordnung UC3 zu den sechs Bewertungsbereichen (Fable M7, Astra 18) als `raster-uc3.csv` mit
  Kurztabelle oben in der Matrix.
- 71-AC3: 32.706 gegen Orakel-Variante E (32.710) klären (Fable N4).
- Hand-Belege mit Pfaden für Pen-Frames, Stimme, Live-Proben.
