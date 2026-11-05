> Die Befund-IDs der Stufe „mittel“ heißen hier Mi1 bis Mi8 (öffentliches Repo: die kurzen IDs sind auch Rechnernamen).

# Review Abnahme-Prozess v0.1 (Fable 5.1, 05.11.2026 17:35 Wien)

Geprüft: 01 bis 10, dazu im Checkout `tests/abnahme/matrix.py`, `docs/abnahme/belege.jsonl` (58 Belege), `all.json`
(140 Issues, Parser darauf laufen lassen), `tests/abnahme/p/`, `tests/abnahme/orakel/`. Keine DB, kein Modell, nichts geändert.

## Urteil in drei Sätzen

Die Trennung Kriterium / Prüfsatz / Ergebnis trägt und ist die einfachste, die hält; `matrix.py` ist solide gebaut und parst alle 140 Issues heute ohne Verlust.
Der Prozess meldet aber auf seiner Hauptachse falsch „bestanden“: ein Beleg bleibt nach jedem Merge gültig, Agent-Belege gelten ohne Reproduktion als Urteil, und die vorgeschlagenen Regexe passen schon heute nicht zur eigenen Ausgabe.
Für die Jury zählt fast nur der schwere UC3-Lauf gegen das Orakel, der im Entwurf auf Stufe 4 steht; den vorziehen, den stündlichen Leichtlauf auf „je neuer main-SHA“ umstellen, den Rest schlank halten.

## Befunde

### Kritisch

- **K1 Beleg veraltet nie.** `stand()` (matrix.py Z. 186) prüft nur den Hash, nicht den SHA. Ein `bestanden` von `d283a78a` steht nach jedem Merge weiter als bestanden in einer Matrix, deren Kopf den aktuellen main nennt. Das ist der zentrale Falschpositiv. Änderung: Beleg gilt nur, wenn `b["sha"]` = aktueller main oder `git diff --name-only <b.sha> origin/main -- <pfade>` leer ist, sonst „nicht geprüft (veraltet seit <sha>)“. Pfade als Standard je Bereich (uc3: `uc3/ shared/py/ abgabe/ docs/plan/uc3/`), nicht je Beleg.
- **K2 Agent-Beleg = Urteil.** `einlesen` nimmt `stand: bestanden` der Messer direkt an; niemand hat den Befehl reproduziert, Vier-Augen nur per Stichprobe. Gemessen: bei 13-1 und 16-4 (beide „bestanden“) treffen die mitgelieferten `erwartet`-Regexe die eigene `ausgabe` nicht; 14-3 enthält einen ungültigen Regex (`re.PatternError`); bei 69-2, 70-1, 70-2, 71-2 ist `erwartet` ein String statt Liste. Änderung: Agent-Belege sind Prüfsatz-Vorschläge. Für UC3 und E6 zählt `bestanden` nur aus `pruefen.py` oder als Hand-Beleg mit `pruefer` = Abnahme-Session. `einlesen` setzt bei fremdem `pruefer` den Stand auf „nicht geprüft (Vorschlag)“ und validiert `erwartet` (Liste, `re.compile`).
- **K3 Regex-Urteil unterbestimmt.** Entwurf: „alle Regexe in der Ausgabe“. Offen: MULTILINE, stdout gegen stderr, Exit-Code. Gemessen in den Belegen: `^(?!.*failed)` ohne `(?m)` prüft nur die erste Zeile, `1 passed, 1 failed` auf Zeile 2 würde bestehen. Änderung in `pruefen.py`: Exit 0 ist Pflichturteil, Regexe mit `re.M` nur auf stdout, ungültiger Regex = Lauf-Fehler des Prüfsatzes, keine negativen Lookaheads, pytest-Prüfsätze nur über Exit plus `\d+ passed`. Negativtest ohne Neulauf: gespeicherte Ausgabe gegen veränderten Sollwert prüfen (`pruefen.py --negativ`), das kostet bei schweren Läufen nichts.

### Hoch

- **H1 ID nach Position.** `kriterien()` Z. 152 vergibt `<iid>-<n>` als Laufnummer. Fügt der Lead eine Checkbox ein, verschieben sich alle folgenden IDs; der Hash verhindert den Falschpositiv, alle Belege danach fallen aber auf „geändert“ (Alarm, Arbeit verloren). Änderung: Belege nach `(iid, hash)` zuordnen (`belege_lesen`, `stand`, `abhaken`), `id` nur Anzeige.
- **H2 abhaken überschreibt fremde Änderungen.** `abhaken()` Z. 325 bis 344 baut die Beschreibung aus dem beim Start geladenen `issues` (mit `--cache` beliebig alt) und PUTtet sie komplett. Alles, was Lead oder Lanes seither im Issue schrieben, ist weg; GitLab bietet kein If-Match. Änderung: Issue unmittelbar vor dem PUT frisch holen, Kriterium per Hash wiederfinden, `updated_at` vor und nach dem PUT vergleichen, bei Abweichung Exit 4 und nichts schreiben; `--cache` für `abhaken` verbieten.
- **H3 Tor „0 nicht geprüft“ ist so nicht erreichbar.** UC3 hat 23 schwere Kriterien, dazu Pen-Frames (18-1), Stimme (79-x), Live-Proben (80-1: neun Proben unter vier Minuten). 21 der 29 „nicht bestanden“ sind „Datei fehlt auf main“ (Arbeit liegt auf `feat/uc3-betrieb`), kein Fachfehler. Änderung: Tor = „0 nicht geprüft ohne Lead-Entscheid“, jeder Rest trägt im `grund` die Kommentar-ID des Entscheids oder steht im Fragenkatalog. Zähler trennt „nicht bestanden (fehlt)“ von „(abweichend)“ über ein Feld `befund: fehlt|abweichend`, sonst liest der Lead um 19:00 29 Alarme.
- **H4 Schwerer Lauf zu spät.** Alle fünf Abgabezahl-Kriterien (14-1, 14-2, 16-3, 70-2, 71-3) und 23 von 68 UC3-Kriterien brauchen die DB. Genau das ist der Jury-Beleg. Bausteine liegen fertig: `66_jury_weg.sh`, `66_readme_weg.sh` (24/24 in 419 s), `66_manifest_vergleich.py`, `p/uc3_sheet_orakel.py`, `orakel/*.csv`, Ministerium-Hash LF `d8492f46…` (Orakel Abschnitt 5). Änderung: Stufe 2 = ein Skript `tests/abnahme/uc3_schwer.sh` auf dem Prüfrechner, Ausgabe als Belege nach `lauf.jsonl`; läuft nach jedem Merge unter `uc3/` und als letzter Lauf 06:30.
- **H5 DB-Fehler wird „nicht bestanden“.** Pytest ohne DB endet mit Exit 1, genau wie ein Fachfehler. Die Exit-Regel 124/126/127 fängt das nicht. Änderung: `schwer=true` läuft nie ohne `--schwer`; Vorflug je Lauf (DB erreichbar, SHA gleich, `uv sync` ok), sonst alle schweren = Lauf-Fehler; stderr-Muster `connection refused|could not connect|OperationalError` = Lauf-Fehler.

### Mittel

- **Mi1** `beleg_pruefen` Z. 297: `bestanden` braucht Befehl oder Datei, nicht die Ausgabe. Änderung: bei `befehl` ist `ausgabe` Pflicht; bei `art=hand` sind `datei` und `pfade` Pflicht.
- **Mi2** `belege_lesen` Z. 182: „jüngster“ = letzte Dateizeile, nicht jüngste `zeit`. Zwei Messer zum selben Kriterium oder vertauschte `einlesen`-Reihenfolge lassen den falschen Beleg gelten. Änderung: nach `zeit` sortieren, bei gleicher Zeit Dateireihenfolge.
- **Mi3** `glab_json` Z. 61 ohne Host: glab nimmt den Host aus dem Git-Verzeichnis des Aufrufers. Aus dem Schnappschuss (`git archive`, kein `.git`) oder aus cron trifft `projects/259` den Standard-Host, also ein fremdes Projekt 259. Änderung: `cwd=WURZEL` setzen oder `--hostname` aus `git remote get-url origin`; zusätzlich `isinstance(teil, list)` prüfen (Fehlerobjekt wird sonst per `extend` zu Schlüsseln). Paginierung selbst ist korrekt; `order_by=created_at&sort=asc` macht sie gegen neue Issues während der Schleife stabil.
- **Mi4** Zwei Wahrheiten: Der Hash sieht nur die Beschreibungszeile, der Messer-Brief sagt „Kommentar geht dem Alttext vor“ (06, Z. 16). Eine Nachschärfung im Kommentar ändert den Hash nicht, der Prüfsatz misst dann gegen den alten Text. Änderung: Entscheide gehören in die Beschreibung (Lead), Kommentar nur als Begründung; Prüfsatz nennt in `quelle` die Kommentar-ID.
- **Mi5** Unbalancierte Code-Fence (`kriterien()` Z. 124) lässt alle folgenden Kriterien stumm verschwinden, der Zähler sinkt, `einlesen` meldet „kein solches Kriterium“. Heute 0 Fälle in 140 Issues. Änderung: Warnung auf stderr, wenn `im_code` am Ende wahr ist.
- **Mi6** Rhythmus „stündlich :50“ misst meist denselben SHA. Code ändert sich nur bei Merges (:05, :25, :45). Änderung: Lauf bei jedem neuen `origin/main`, Herzschlag stündlich nur, wenn kein Merge kam. Dann gehört jeder Rückfall automatisch zu einem Merge (Nachvollziehbarkeit Kriterium → Merge → Lane gratis).
- **Mi7** Jury-Sicht fehlt in der Matrix. Die Matrix liegt im öffentlichen Repo, hat aber keine Spalte zum 120-Punkte-Raster; `raster-120.md` (19-1) ist nach Abgabe geschoben. Änderung, 20 Minuten: `docs/abnahme/raster-uc3.csv` (Raster-Bereich, Kriterium-IDs) und oben in `matrix-uc3.md` eine Sechs-Zeilen-Tabelle „Bereich, bestanden/gesamt, stärkster Beleg“. Die fünf Abgabezahl-Kriterien mit Orakel-Zeile hervorheben.
- **Mi8** 72 der 245 Kriterien stammen aus 40 geschlossenen Issues, alle Boxen leer. Sie füllen „nicht geprüft“ auf. Änderung: im Zähler getrennt ausweisen („davon aus geschlossenen Issues“), damit das Tor nicht an Altlasten scheitert.

### Niedrig

- **N1** `abhaken()` Z. 310: `next(...)` ohne Default wirft Traceback bei unbekannter iid.
- **N2** `splitlines()` trennt auch an `\x0c`, ` `, NEL; `"\n".join` schreibt sie weg. Heute kein CRLF in 140 Issues. Für die Rückschreibung `split("\n")` nehmen.
- **N3** Repo-Fassung hat `(?<!\.env)\.local` und die 127.0.0.1-Ausnahme schon; die Review-Kopie 05 ist älter. Erledigt.
- **N4** Nicht sicher: 71-3 nennt 32706 als Vergleichswert, `ministerium-oracle.md` Z. 51 ordnet ihn „August aus Lieferung 2025-11“ zu; das Orakel kennt 32.710 für Variante E ohne Altcodes und 32.706 gar nicht. Vor der Abnahme von 71-3 klären, ob das dieselbe Variante ist.
- **N5** Stufe 1 „bis 19:00“ ist bei Start 17:30 mit `pruefen.py`, TOML, Umbau, Lauf und Abgleich nicht zu halten. Siehe Reihenfolge unten.

## Verbesserter Prozess (direkt übernehmbar)

1. Gültigkeit: Beleg zählt nur auf aktuellem main oder bei unverändertem Standard-Pfadsatz des Bereichs (K1). Stand „nicht geprüft (veraltet seit <sha>)“ ergänzen.
2. Herkunft: `pruefer` der Abnahme-Session oder `pruefen.py` entscheidet; Agent-Belege sind Vorschläge und Prüfsatz-Entwürfe (K2).
3. Urteil: Exit 0 Pflicht, Regexe `re.M` auf stdout, ungültiger Regex = Lauf-Fehler, DB-Fehlermuster = Lauf-Fehler, Negativtest per Replay (K3, H5).
4. Zuordnung über `(iid, hash)`; `abhaken` holt frisch, vergleicht `updated_at`, kein Cache (H1, H2).
5. Zähler mit vier Ständen plus `befund fehlt|abweichend` und „davon geschlossen“ (H3, Mi8).
6. Tor 06:30: UC3 und E6 ohne „nicht geprüft“ ohne Lead-Entscheid; letzter schwerer Lauf auf dem Merge-Stopp-SHA startet 06:30, Ergebnis 06:45, Zahl in die Präsentation und in `matrix-uc3.md` (H3, H4).
7. Auslöser: neuer `origin/main` statt Uhr; stündlicher Herzschlag nur ohne Merge (Mi6).
8. DoD je Kriterium: bestanden auf gültigem SHA, Haken, Kommentar mit Befehl/Ausgabe/SHA. Fix-MRs nennen `Abnahme: <id>` in der Beschreibung, Review-Bank prüft das (eine Zeile im Review-Brief). Damit steht Kriterium → Prüfung → Beleg → Commit.
9. RACI: Messer messen und schlagen vor (R), Abnahme urteilt und hakt ab (A), Lane fixt (R), Lead entscheidet Kriteriumstext, `nach-abgabe`, Fragenkatalog (A). Eskalation: nicht bestanden auf Abgabezahl oder E6 sofort Lead; sonst Lane, ohne Reaktion nach 90 Minuten Lead.
10. Kriterien, die sich nachts ändern: Lead ändert die Beschreibung, nicht nur den Kommentar (Mi4); Hash kippt auf „geändert“, Abnahme passt Prüfsatz an und misst neu; kein stilles Übernehmen.
11. Reihenfolge: bis 18:30 matrix.py-Fixes K1, H1, H2, Mi1, Mi2, Mi3 und `einlesen` der Messer als Vorschläge, Zähler 19:00 ehrlich (fast alles „nicht geprüft“, mit Messbefehl im grund). 19:00 bis 21:00 `uc3_schwer.sh` auf dem Prüfrechner, erster Lauf, Abgabezahlen gegen Orakel. 21:00 bis 23:00 `pruefen.py` leicht mit TOML für UC3 und E6, Auslöser je SHA. 23:00 bis 02:00 UC4, UC1, UC2 als Hand-Belege der Messer mit Pfaden, E5 nach Landung. 02:00 bis 06:00 Rückfälle, Fragenkatalog. 06:30 Schlusslauf.
12. Behalten: Einzelprotokolle wie `66.md` für die vier bis sechs Jury-Kriterien (Determinismus, Golden Set, Orakel, ohne Netz), sie sind der lesbare Beleg für die Präsentation; alles andere nur in Matrix und Belegen. Messer-Agents behalten, aber mit dem Ziel „Prüfsatz-Vorschlag“, nicht „Urteil“.

## Streichliste

- Stufe 5 (CI-Pipeline) heute; nach der Abgabe.
- TOML-Prüfsätze für UC1, UC2, E0, E5 heute: Hand-Belege mit Pfaden reichen, die Jury bewertet UC3.
- Negativtest mit Neulauf für schwere Prüfsätze; Replay der gespeicherten Ausgabe genügt.
- Pfade je Beleg; ein Standard-Pfadsatz je Bereich, nur bei Bedarf enger.
- Stündlicher Lauf bei unverändertem SHA inklusive `uv sync`; nur Herzschlag-Zähler.
- Zähler-Nachricht an den Lead außerhalb der fünf Zeiten; Lead liest sonst nur Rauschen.
- Änderungsliste als eigener Baustein: ein Diff zweier `lauf.jsonl` (zehn Zeilen) reicht, kein eigenes Format.
- Abhaken in geschlossenen Issues; dort genügt der Matrix-Eintrag mit Beleg.
