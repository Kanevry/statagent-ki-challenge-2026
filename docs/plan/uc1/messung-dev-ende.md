# UC1: Messreihe im eigenen End-zu-End-Dev-Set (#155, #162, #151)

Set: `uc1/eval/dev-ende.yaml`. Es hat 20 erfundene Fälle:
- 12 zu Träger und Nachbarleistung,
- 6 Abstinenz-Fallen mit klarer Antwort im Gesetz, aber in Bürgersprache gefragt,
- 2 Kontrollfälle, deren Antwort nicht im Korpus steht.

Das Set ist ohne Blick auf `lotse-set.yaml` und das Held-out-Set geschrieben. Ein Lauf hier zählt nicht als Blick auf das Test-Set.

Aufruf aus `uc1/`: `uv run --frozen python werkzeuge/messen.py --ende --set eval/dev-ende.yaml --provider azure --ausgabe <datei>`. Provider azure, Modell gpt-5-4-mini, eigene Lotse-DB mit dem Korpus (Volltext), Läufe am 05.11.2026 zwischen 19:20 und 20:15.

Gezählt wird ohne Modell:
- **Verhalten:** Der Klassifizierer muss das Soll treffen.
- **Träger:** Die erwartete Stelle muss unter den genannten Stellen sein.
- **Zitiertreue:** Jedes Zitat steht wörtlich im Abschnitt.

„Ausfall“ heißt, das Antwort-Modell war in diesem Fall nicht erreichbar. Das zählt als Fehler des Falls. Gezählt ist der deutsche Ersatztext, englische Fälle sind nur bei nach-2 von Hand nachgezählt.

| Lauf | Stand | Was neu ist | Verhalten | Träger | Zitiertreue | Ausfälle (mindestens) |
|---|---|---|---|---|---|---|
| grund-1 | main-Kern | Grundlinie | 16/20 | 14/18 | 35/35 | 0 |
| grund-2 | main-Kern | Grundlinie, Wiederholung | 16/20 | 14/18 | 45/45 | 0 |
| nach-1 | 9c18f83 | Stelle aus der zitierten Norm, zweiter Versuch, Sprachprüfung je Aussage | 20/20 | 16/18 | 41/41 | 0 |
| nach-2 | a54ee2b | wie nach-1, Wiederholung | 17/20 | 18/18 | 48/48 | 2 |
| nach-3 | 241d824 | Regeln vor Modell (verworfen) | 19/20 | 17/18 | 56/56 | 0 |
| nach-4 | 6fb1d1b | enge Auslöser vor Modell | 18/20 | 17/18 | 44/44 | 1 |
| nach-5 | 6fb1d1b | Wiederholung | 17/20 | 17/18 | 45/45 | 1 |
| nach-6 | 79640f8 | Review-Fixes (!147, gemergt) | 19/20 | 17/18 | 40/40 | 0 |
| nach-7 | 1278dd6 | Schwellen aus dem Zitat, Akutzeichen (!152) | 20/20 | 17/18 | 46/46 | 0 |
| rel-1 | e6c1a2f | `beantwortet` für alle Fragen (verworfen) | 16/20 | 17/18 | 41/41 | 1 |
| rel-2 | 3aa52bd | wie rel-1, Wiederholung | 14/20 | 17/18 | 29/29 | 1 |
| rel-3 | cb00434 | `beantwortet` nur ohne erkannte Leistung (!164) | 18/20 | 17/18 | 36/36 | 1 |
| rel-4 | cb00434 | Wiederholung | 19/20 | 17/18 | 32/32 | 0 |
| klein-1 | e744b7a | Unfall-Auslöser für Dienstzeit (auf main mit !152) | 20/20 | 17/18 | 44/44 | 0 |

## Was die Reihe zeigt

- **Grundlinie:** Sie ist stabil, beide Läufe ergeben Verhalten 16/20 und Träger 14/18. Die Fehler waren:
  - x02: Status aus einer Frage statt aus der Aussage.
  - x03: falscher Notfall bei einem vergangenen Schlaganfall.
  - x07, x08: Abstinenz trotz Treffer, weil eine Aussage die Sprachprüfung nicht bestand oder kein Zitat wörtlich war.
  - x12, x16: Unfall ohne Stelle.
  - x19, x20: streifende Antwort auf die Kontrollfälle.
- **Nach den Änderungen:** Verhalten liegt bei 17 bis 20 von 20, Träger bei 16 bis 18 von 18. Fast jeder verbliebene Verhaltensfehler ist ein Modellausfall oder eine Schwankung des Modells von Lauf zu Lauf, etwa x04 (Pflegekarenz auf Englisch, mal SMS, mal PVA).
- **Verworfen:** Zwei Varianten haben die Messung verschlechtert und sind nicht übernommen:
  - „Regeln vor Modell“ (nach-3): x04 fällt.
  - `beantwortet` für alle Fragen (rel-1, rel-2): passende Antworten werden zur Abstinenz.
- **Recall@5 über den Kern** (dev-set, dev-set-2, LLM-Erweiterung): Der Abstand zur nackten Suche ist vor und nach #155 gleich. Die Schwankung zwischen den Läufen kommt aus der LLM-Erweiterung.

## Grenzen

- n = 20, ein Autor, Fragen formuliert und nicht gesammelt. Die Reihe eignet sich für Fehlersuche und Vorher-Nachher-Vergleiche, nicht für Prozentwerte.
- Je Stand ein bis zwei Läufe. Das Modell schwankt von Lauf zu Lauf um etwa ±2 Fälle.
- Das Test-Set `lotse-set.yaml` ist nicht gemessen (3 von 3 Blicken verbraucht). Den Held-out-Lauf macht der Lead nach dem Merge.
