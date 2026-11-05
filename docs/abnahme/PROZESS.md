# Abnahme-Prozess: jedes Kriterium mit Beleg, bei jedem neuen main wiederholt

Stand v0.3, 05.11.2026 18:10 (Europe/Vienna), b-abnahme-30 (v0.2 17:43 nach Review). Geprüft von Fable 5.1 und Astra (Codex, gpt-6-astra)
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
| Verworfener Beleg | `docs/abnahme/verworfen.jsonl` (Lauf, IDs, Grund, wer): ein Werkzeugfehler hat ihn verfälscht; die Laufdatei bleibt unverändert | Abnahme |
| Matrix, Zähler, Tor | `docs/abnahme/matrix-<bereich>.md`, `matrix.py zaehler`, `matrix.py tor` | erzeugt, nie von Hand |
| Jury-Raster UC3 | `docs/abnahme/raster-uc3.csv` (Bewertungsbereich je Issue), Tabelle oben in `matrix-uc3.md` | Abnahme |

## Befehle

```
uv run python tests/abnahme/pruefen.py [--bereich uc3] [--id 70-AC2] [--schwer] [--gegenprobe]
uv run python tests/abnahme/matrix.py schreiben | zaehler | tor | befunde [--ja] | abhaken <id> [--ja]
bash tests/abnahme/waechter.sh          # startet den leichten Lauf bei jedem neuen origin/main
bash tests/abnahme/schwer_pruefrechner.sh <bundle> <main-sha> <werkzeug-sha> <issues.json>   # Prüfrechner
```

## Der Lauf

1. Abzug: Prüfling ist main an der vollen SHA, als geteilter Klon mit Git-Historie (für git- und
   gitleaks-Prüfsätze), mit `uv sync --frozen` und `pnpm install` (erst offline, dann mit Netz; scheitert beides,
   werden die vitest-Prüfsätze Lauf-Fehler). Prüfwerkzeug ist `tests/abnahme` aus dem Abnahme-Commit. Beide SHAs
   stehen im Laufmanifest.
   Neben den Abzügen liegen wie beim Jury-Weg `../svbox` (Startpaket) und `../lieferungen` (Einzeldaten, nie im
   Repo) als Links auf die Ordner neben dem Haupt-Checkout (`pruefen.nachbarn_verlinken`).
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

4. `art = "hand"`: ein Mensch prüft (Screens, Stimme, Upload, Jury-Probe). Er zählt nur mit einem Hand-Beleg
   des Prüfers in `belege.jsonl` (`art = "hand"`, Hash passend, Pfade unverändert); sonst „Hand-Prüfung offen“.
5. Schwerer Lauf: Kriterien mit schwerem Teil urteilt nur der schwere Lauf (alle Teile). Ein leichter Lauf darf
   sie abwerten (nicht bestanden), sonst schweigt er. Der schwere Lauf bricht vor jedem Schritt ab, wenn eine
   Datenbank-Adresse nicht auf die lokale Prüf-DB (Port 5444) zeigt (gemessen: mit 5433 Exit 3).
6. Mehrere Prüfsätze je Kriterium: ein Teil nicht bestanden heißt Kriterium nicht bestanden. Bestanden nur, wenn
   ein voller Prüfsatz besteht und kein Teil scheitert.
7. Testzählungen sind so verankert, dass ein Durchfaller nie passt (pytest `(^|= )\d+ passed`, vitest
   `^\s*Tests\s+\d+ passed \(\d+\)`); keine feste Testzahl, außer `-k` wählt genau einen Test.
8. Jeder wichtige Prüfsatz hat eine `gegenprobe` mit falschem Soll; `--gegenprobe` verlangt, dass sie scheitert.

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
| leichter Lauf | bei jedem neuen origin/main (Wächter, Blick alle 5 min) | Arbeitsrechner, Abzug |
| schwerer Lauf UC3 (Golden Set, 24 Läufe, Abgabezahlen gegen Orakel) | automatisch nach jedem leichten Lauf, wenn sich main in UC3-Pfaden (`uc3/`, `abgabe/`, `docs/plan/uc3/`, `shared/`, Lockfiles) geändert hat; höchstens einer gleichzeitig (`schwer_ausloesen.sh`, Ziel aus einer env-Datei außerhalb des Repos) | Prüfrechner, Prüf-DB 5444, rund 10 min |
| Befunde und Haken | nach jedem Lauf mit Wechsel, durch den Prüfer | GitLab |
| Zähler an den Lead | 19:00, 20:00, 23:00, 02:00, 05:00 | SendMessage |
| Vorprüfung Tor | 05:00 | |
| Schlusslauf leicht und schwer | auf dem Merge-Stopp-SHA ab 06:30 | Arbeitsrechner und Prüfrechner |

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
| glab ohne Repo-Kontext | Fable Mi3 | `cwd` fest auf das Repo, Liste und doppelte iid geprüft |
| Läufe überschreiben sich | Astra 10 | eine Datei je Lauf mit Manifest und Schlusszeile |
| Zeitlimit kann Produktfehler sein | Astra 11 | `zeitlimit_ist_befund` je Prüfsatz |
| Auslöser Uhr statt Merge | Fable Mi6 | Wächter je neuem main |
| E6 im Zähler versteckt | Astra 15 | Zähler je Teil |

Nicht übernommen, mit Grund:
- Pfade je Beleg als Pflicht (Astra 9): ein Standard je Bereich reicht; nur Hand-Belege tragen eigene Pfade.
- Kommentare als Quelle des Wortlauts (Astra 2): Entscheide gehören in die Beschreibung (Fable Mi4); der Lead
  ändert dort, der Hash kippt, die Abnahme misst neu.
- Vollständiger Markdown-Parser, CI-Pipeline, TOML-Prüfsätze für UC1, UC2, E0, E5 heute (beide Streichlisten).

## Was der Prozess schon gefunden hat (eigene Fehler eingeschlossen)

- Fixes auf main selbst erkannt: 135-10, 135-11 (Commit 043885a).
- Zu großzügige Agent-Urteile: 13-AC4 (zwei Teile ungemessen), 16-AC4 (Prüfsatz verlangte Exit 0 des ganzen
  Validators), 92-1 (Ministeriums-CSV im Repo verlangt, laut Owner-Entscheid nur im Manifest).
- Schwerer Lauf 18:26 auf frischer Prüf-DB (main 27e54816): Golden Set grün; Abrechnung 2024-08 392284 = 392236 + 48
  + 0; 24 Läufe hash-gleich mit dem Manifest der UC3-Lane; DB-Zeitreihe = Orakel in 24/24 Monaten; Sheet v1 = Orakel
  in 1051 Zellen.
- Entscheid #16 (Einzeldaten nur SV-Box): 22-1 und 20-AC1 messen Validator und Beleg (sha256, Zeilen) gegen das
  Orakel Variante S, nicht die CSV im Checkout; die CSV selbst prüft 71-AC2 am externen Ort, nur Kennzahlen in der
  Ausgabe. 22-1 hat einen schweren Teil: aktive Regelsätze v2 und ministerium auf frischer DB (Jury-Probe 4d, B1).
- Schwerer Lauf 20:01 (main 71ba5c82) brach nach den 24 Läufen am eigenen Prüf-Klon-Schutz ab: auf dem
  Prüfrechner läuft `pruefen.py` im Klon selbst. Seitdem entscheidet die Marke, und `--ort` im eigenen Baum wird
  nur geprüft (Kopf = main), nicht erneut zurückgesetzt.
- Agent-Vorschläge mit Platzhaltern (`<Pfad zu …>`) ergaben über Syntaxfehler falsch „nicht bestanden“; ein Vorschlag
  startete `docker compose` auf dem Bau-Port 5433. Seitdem: Platzhalter, Syntaxfehler, Bau-Ports und Docker machen
  einen Prüfsatz ungültig.
- Eigene Werkzeugfehler, behoben: Prüfskripte fehlten im Abzug, Farbcodes, fehlende Node-Module, Abzug ohne Git,
  Befund-Kommentare wurden bei geänderter Laufzeit erneut gepostet (in UC3 und UC1 je ein doppelter Kommentar
  aus dem Lauf 18:05).

## Offen

- 71-AC3: 32.706 gegen Orakel-Variante E (32.710) klären (Fable N4).
- Hand-Belege mit Pfaden für Pen-Frames, Stimme, Live-Proben.
