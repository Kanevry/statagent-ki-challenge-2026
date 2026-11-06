# StatAgent: Monatsstatistik mit KI-Agenten, freigegeben von Menschen

StatAgent macht aus den monatlichen Lieferungen der Sozialversicherung die Beschäftigtenstatistik und einen
Qualitätsbericht. Es ist für Statistikteams, die jeden Monat Zahlen liefern und jede Regeländerung belegen müssen.
Ein KI-Agent schlägt Änderungen an den Regeln vor, ein Mensch gibt sie mit seinem Namen frei, gerechnet wird ohne KI.

**Ausprobieren ohne Installation:** https://ki-challenge.gotzendorfer.at/

**Direkt zu Use Case 3 StatAgent:** https://ki-challenge.gotzendorfer.at/uc3

**Keine Zeit?** Aufzeichnung der Vorführung, 2:45 min, ohne Ton:
[docs/praesentation/backup-demo.mp4](docs/praesentation/backup-demo.mp4).
So sieht eine Freigabe aus, auch online ohne Passwort:
https://ki-challenge.gotzendorfer.at/uc3/freigaben/24

![Freigabe-Seite in StatAgent zum Änderungsauftrag 1 „Dienstvertrag und freier Dienstvertrag zusammen“. Die Testrechnung für August 2024 zeigt die Zahlen vorher und nachher. Aus 235.819 und 1.142 Angestellten werden 236.961. Gesamt bleibt 392.236. Darunter steht, wer freigegeben hat und wann.](docs/praesentation/screens/SC12.png)

Oben steht der Auftrag im Wortlaut. In der Mitte rechnet das Programm die Zahlen vorher und nachher. Unten steht
die Freigabe mit Vor- und Nachnamen und Uhrzeit. Diese Freigabe ist eine der vier, die eine KI-Sitzung im Auftrag von
Bernhard Götzendorfer eingegeben hat; er hat sie am selben Abend bestätigt (Commit `2ba95e5`, [Stand zur Abgabe](#stand-zur-abgabe-06112026)).

Die öffentliche Demo ist lesend: Man kann alles ansehen und Fragen an die Daten stellen. Aufträge an die Agenten und
Freigaben mit Namen laufen auf einer eigenen Vorführ-Adresse mit Passwort und lokal.

Beitrag von Team OneShotAndy zur **KI Challenge 2026** des Dachverbands der österreichischen
Sozialversicherungsträger und der WK Wien (05. bis 06.11.2026). Bewertet wird **Use Case 3, StatAgent**.

## Wo fange ich an?

| Ich bin … oder ich will … | Dann lies zuerst |
|---|---|
| Fachjury | [abgabe/README.md](abgabe/README.md) und [docs/praesentation/kriterien-karte.md](docs/praesentation/kriterien-karte.md) |
| neu hier und neugierig | [docs/einstieg/fuer-aussenstehende.md](docs/einstieg/fuer-aussenstehende.md) |
| Entscheiderin oder Entscheider | [docs/einstieg/fuer-management.md](docs/einstieg/fuer-management.md) |
| Technikerin oder Techniker | [docs/einstieg/architektur.md](docs/einstieg/architektur.md) |
| es lokal starten | [docs/einstieg/schnellstart.md](docs/einstieg/schnellstart.md) |
| selbst agentisch arbeiten, also mit KI-Agenten, die Code schreiben | [docs/einstieg/arbeitsweise-agentisch.md](docs/einstieg/arbeitsweise-agentisch.md) |
| die Zahlen nachprüfen | [docs/einstieg/zahlen.md](docs/einstieg/zahlen.md) |
| sehen, welche Aufgaben erledigt und welche offen sind | [docs/einstieg/aufgaben-stand.md](docs/einstieg/aufgaben-stand.md) (interne Aufgabenliste; offen heißt nur: nicht abgehakt) |
| wissen, was am Tag der Abgabe läuft und was offen ist | [Stand zur Abgabe](#stand-zur-abgabe-06112026) |

Alle Einstiegsseiten im Überblick: [docs/einstieg/README.md](docs/einstieg/README.md).

## Was liegt wo

| Ordner | Inhalt |
|---|---|
| `uc3/` | StatAgent selbst: Python-Paket mit dem Befehl `uc3` zum Einlesen, Prüfen, Zählen und für die Berichte, dazu die Agenten |
| `abgabe/` | die abgegebenen Ergebnisse von UC3, vom Programm erzeugt: Aggregations-Sheets, Qualitätsberichte, Rückfragen, Protokoll |
| `docs/abgabe/` | wie abgegeben wurde: Abgabe-Weg, Herkunft übernommener Teile, Prüfung dieses README, Nachweis der Übertragung |
| `web/` | die Weboberfläche für alle Use Cases und die Präsentation |
| `shared/` | gemeinsamer Kern: Python-Paket `plattform` (Modellaufrufe, Protokoll, Freigabe, Voice) und die Bausteine der Oberfläche |
| `uc1/`, `uc2/` | Zusatz: SV KI-Lotse und HealthPolicy Simulator |
| `docs/` | Dokumentation: Einstieg, Präsentation, Betrieb, Modelle, Abnahme, Plan |
| `tests/`, `scripts/`, `deploy/` | Prüfungen für Abnahme und Abgabe, Hilfsskripte, Betrieb der Online-Demo |

`CLAUDE.md`, `.claude/`, `.orchestrator/`, `docs/plan/` und `docs/abnahme/` sind Arbeitsdateien der Coding-Agenten und bleiben als
Nachweis drin ([docs/einstieg/arbeitsweise-agentisch.md](docs/einstieg/arbeitsweise-agentisch.md)).
`abgabe/CHECKLISTE.md` ist die interne Ablaufliste der Abgabenacht.
`KI-Challenge_UseCase.yaml` ist die Pflichtdatei des Veranstalters mit den Angaben zum Beitrag.

## Lösung und Ansatz

**Jeden Monat**

```mermaid
flowchart LR
  L["Monatslieferung"] --> P["Programm prüft und rechnet, ohne KI"]
  P --> S["Statistik und Qualitätsbericht"]
  S --> W["Weboberfläche, Fragen an die Daten"]
```

**Wenn sich eine Regel ändert**

```mermaid
flowchart LR
  T["Auftrag in einem Satz"] --> K["KI-Agent macht Vorschlag"]
  K --> F["Mensch gibt mit Namen frei"]
  F --> G["Gilt ab dann im Programm"]
```

Der Vorschlag zeigt die Zahlen vorher und nachher, Vorschlag und Freigabe stehen im Protokoll. Die KI schreibt Code
und Regeln, gerechnet wird ohne KI.

Eine Plattform mit drei Anwendungen (UC1, UC2, UC3) und einem gemeinsamen Einstieg (UC4). Jede Zahl kommt aus der Datenbank und trägt ihren Beleg.
Jede Änderung an Regeln oder Code gibt ein Mensch mit Vor- und Nachnamen frei.

UC1 (SV KI-Lotse), UC2 (HealthPolicy Simulator) und UC4 (gemeinsamer Einstieg) sind Zusatz. Was gebaut wurde, wie
UC3 rechnet, Freigabe, Voice und Qualitätssicherung: [docs/einstieg/loesung-und-ansatz.md](docs/einstieg/loesung-und-ansatz.md).

## Ausführung

Mit `git clone` holen, nicht als ZIP: Ohne den Ordner `.git` fallen einige Tests.

```bash
git clone https://github.com/KIChallenge/OneShotAndy.git && cd OneShotAndy
cp .env.example .env.local && sed -i.bak 's/^LLM_PROVIDER=.*/LLM_PROVIDER=mock/' .env.local  # ohne Schlüssel
uv sync --all-packages && pnpm install  # Python- und TypeScript-Workspace
pnpm dev                                # App auf http://localhost:3000
```

Das Startpaket sind die Unterlagen des Veranstalters für die Teams der Challenge: Lieferungen, Klassifikationen,
Beispielbericht und eine Datenbank, alles synthetisch. Es liegt nicht im Repo. Ohne Startpaket zeigt `/uc3` lokal
keine Zahlen, und die Befehle unten enden schon bei `uv run uc3 db init`.

Für `/uc3` braucht es die Datenbank des Veranstalters auf Port 5433. Im Ordner des Startpakets:
`DB_PORT=5433 docker compose up -d`, dann warten, bis `docker logs statagent-db` „fertig“ meldet.

**Achtung:** `uv run uc3 berichte --alle` und `uv run uc3 sheet` schreiben ohne weitere Einstellung in den Ordner
`abgabe/` und überschreiben dort die abgegebenen Dateien. Wer das nicht will, setzt vorher `STATAGENT_ABGABE` auf
einen eigenen Ordner.

```bash
uv run uc3 db init                          # Schemas, Klassifikationen, Regelsätze (wiederholbar, löscht nichts)
uv run uc3 lauf --alle                      # 24 Einzelläufe 2024-08 bis 2026-07, in zeitlicher Reihenfolge
uv run uc3 eichen --lieferung 2024-08       # Vergleich mit dem Beispielbericht, Tab1 bis Tab13
uv run uc3 berichte --alle && uv run uc3 sheet   # 24 Qualitätsberichte und Aggregations-Sheet nach abgabe/
```

Tests (ohne die Daten des Veranstalters, so ruft es auch die CI in `.gitlab-ci.yml` auf):

- `uv run pytest -q -m "not daten" shared/py/tests` für den gemeinsamen Kern, je Use Case `cd ucN && uv run pytest -q -m "not daten"`
- `pnpm typecheck && pnpm test` für den TypeScript-Teil
- UC3 gegen die echten Daten (Datenbank mit gerechneten Läufen, Golden Set mit 2.880 Zellen):
  `UC3_DATEN_URL=postgresql://statistik:statistik@localhost:5433/statistik uv run pytest -q -m daten uc3/tests`.

Start der Datenbank, Ergebnis des Eichens, Nachweis des Jury-Wegs und die Online-Demo:
[docs/einstieg/ausfuehrung.md](docs/einstieg/ausfuehrung.md).

## Abhängigkeiten und Voraussetzungen

- Python 3.12 oder neuer mit uv 0.12, Node 24 oder neuer mit pnpm 10.
- PostgreSQL 16 auf Port **5433**. Docker braucht es nur für die Datenbank des Veranstalters.
- Daten: Startpaket des Veranstalters, synthetisch, nicht im Repo. Es liegt im Ordner `svbox/uc3` neben dem
  Repo-Ordner (also `../svbox/uc3`), oder `STATAGENT_STARTPAKET` nennt einen anderen Pfad.

Belege je Version und die wichtigen Bibliotheken:
[docs/einstieg/ausfuehrung.md](docs/einstieg/ausfuehrung.md#abhängigkeiten-und-voraussetzungen).

## Konfiguration

Alle Einstellungen kommen aus Umgebungsvariablen oder aus `.env.local` an der Repo-Wurzel. Vorlage mit den
wichtigsten Schlüsselnamen und Erklärungen: `.env.example`. Alle Schlüssel stehen in
[docs/einstieg/konfiguration.md](docs/einstieg/konfiguration.md). **Werte stehen nie im Repo.** Dieses README nennt nur Namen.

- **Azure OpenAI `gpt-5.4-mini`** (Deployment `gpt-5-4-mini`, Modell des Veranstalters, Endpunkt in der EU) ist
  **Pflicht und Standard für alle UC3-Agenten**.
- **Mistral (EU)** ist der Zweitanbieter, etwa für den Wechsel vor der Jury. Das Projektbudget bei Mistral ist 10 €
  ([PRD](docs/prd/2026-11-05-e0-plattform-e1-uc3.md)), ein kurzer Probeaufruf am 05.11.2026 hat geantwortet
  ([docs/models.md](docs/models.md)).
- **Ollama** ist als Notnagel für den Offline-Betrieb angebunden, gelaufen ist es bisher nicht.
- **Claude Opus 5.5** läuft über die CLI, nur als Qualitätsmodus für UC1, UC2 und Vergleiche. **Nie in der UC3-Zählung.**
- **Embeddings:** `google/embeddinggemma-2`, lokal. Die Gewichte sind nicht im Repo (siehe Lizenzen).
- **Ohne Schlüssel** läuft alles mit `LLM_PROVIDER=mock`. Der UC3-Monatslauf braucht ohnehin kein Modell.

Alle Schlüssel und die Grenzen der Online-Demo: [docs/einstieg/konfiguration.md](docs/einstieg/konfiguration.md).

## Stand zur Abgabe, 06.11.2026

Stand je Bewertungsbereich der Aufgabenstellung. Abgegeben ist der Stand von main zum Zeitpunkt des letzten Pushs.
Die Messungen stammen von früheren Ständen desselben Morgens.

| Bereich | Mindestanforderung | Optimum | Was zum Optimum fehlt |
|---|---|---|---|
| 1 Datenmanagement | erfüllt | erfüllt | |
| 2 Klassifikation | erfüllt | teilweise | ÖNACE und Regionen sind bis zur tiefsten Ebene da, Zahlen gibt es aber nur je Branchenabschnitt und Bundesland |
| 3 Qualitätssicherung | erfüllt | teilweise | nur August 2024 hat einen Vergleichsbericht; ob in den anderen 23 Monaten alle Fehler gefunden sind, lässt sich nicht belegen |
| 4 Reporting | erfüllt | teilweise | Dashboard ist da; freie Fragen an die Daten sind nicht alle geprüft |
| 5 Weiterentwicklung und Betrieb | erfüllt | teilweise | die Live-Änderung wird getippt, nicht gesprochen |
| 6 Bedienbarkeit | erfüllt | erfüllt | |

22 der 24 Monate sind nach den alten Regeln mit Namen veröffentlicht, die Zahlen nach den Änderungsaufträgen sind
noch vorläufig. Die Pensionsmeldungen sind eingelesen, ihr Stand ist ebenfalls vorläufig. Die alten Regeln (technisch `v1`) und die
Veröffentlichung der 22 Monate hat Bernhard Götzendorfer selbst freigegeben. Vier Freigaben vom 05.11.2026 hat eine
KI-Sitzung in seinem Auftrag eingegeben; er hat sie am selben Abend selbst bestätigt (Commit `2ba95e5`,
[abgabe/protokoll.md](abgabe/protokoll.md), „Hinweise zu den Freigaben“). Im Schlusslauf der Abnahme
(Stand `14c86cc3`, 07:50) sind für UC3 53 von 76 Kriterien bestanden. 2 sind nicht bestanden, 4 nicht geprüft, 17 für
die Zeit nach der Abgabe vorgesehen. Das ist kein „alles bestanden“. Die Kriterien sind die eigene Prüfliste des Teams,
nicht das Bewertungsraster. Beleg: [docs/abnahme/schlusslauf-2026-11-06.md](docs/abnahme/schlusslauf-2026-11-06.md),
jedes Kriterium mit Befehl: [docs/abnahme/matrix-uc3.md](docs/abnahme/matrix-uc3.md). Die Matrix zählt inzwischen mehr
Kriterien, weil nach dem Schlusslauf neue dazukamen; bestanden sind dort ebenfalls 53 (Stand `7dff9bdb`, 08:49: 53 von 78). Beleg je Zeile: [Kriterien-Karte](docs/praesentation/kriterien-karte.md). Grenzen bei Fragen an die
Daten, Stand von UC1, UC2 und UC4, Abnahme: [docs/einstieg/stand-zur-abgabe.md](docs/einstieg/stand-zur-abgabe.md).

## Grenzen und offene Punkte

- **Daten:** nur die synthetischen Daten des Veranstalters und öffentliche Quellen, nicht im Repo. Einzige Ausnahme:
  Die Rückfragen in `abgabe/rueckfragen/` nennen als Beispiel einige synthetische Kennungen. An ein Modell gehen nie
  Einzeldaten, nur Schema, Aggregate und Prüfergebnisse.
- **UC1** ersetzt keine Beratung. **UC2** ist eine Simulation, keine echte Verhandlung.
- **Voice** läuft über den US-Dienst Vapi und braucht ein eingerichtetes Konto. Der Text-Weg ersetzt Voice vollständig.
- **UC3:** Offene Rückfragen an die Fachabteilung stehen in `abgabe/rueckfragen/`.

Alle Grenzen im Einzelnen: [docs/einstieg/grenzen-herkunft-lizenzen.md](docs/einstieg/grenzen-herkunft-lizenzen.md).

## Vorab Entstandenes

Das Voice-Konzept (Vapi Custom LLM, Webhook, Text-Fallback) folgt einem früheren eigenen Projekt des Teams,
einem Sprach-Interview mit Vapi. **Übernommen sind nur Konzept und Schnittstellen. Der Code ist hier neu
geschrieben.** Die Liste aller übernommenen Teile mit Herkunft, Version und Rechtebeleg: `docs/abgabe/herkunft.md`.

## Lizenzen

Der eigene Code dieses Repos steht unter der MIT-Lizenz (`LICENSE`). Nach den Teilnahmebedingungen der
KI Challenge 2026 stehen die Ergebnisse (dieses Repository) neben dem Team auch dem Dachverband der
österreichischen Sozialversicherungsträger uneingeschränkt zur Verfügung. Ausgenommen sind die Daten des
Veranstalters, die Gewichte fremder Modelle (etwa `google/embeddinggemma-2` unter den Gemma Terms of Use) sowie Logos
und Marken Dritter. Fremde Bibliotheken behalten ihre Lizenzen. Die Messfunktion des Anti-Schablonen-Gates
(`web/tests/lib/slop-measure.js`; das Gate ist ein Test, der typische Muster von KI-Vorlagen in der Oberfläche zählt,
siehe [docs/design.md](docs/design.md)) steht unter Apache-2.0.
Einzelheiten: [docs/einstieg/grenzen-herkunft-lizenzen.md](docs/einstieg/grenzen-herkunft-lizenzen.md#lizenzen).

## Entstehung

Das Repo ist während der KI Challenge mit vielen KI-Agenten entstanden. Gearbeitet wurde in einem privaten
GitLab: Dort lagen Aufgaben und Änderungsanträge, und dort lief auch die CI (`.gitlab-ci.yml`). Auf GitHub
läuft keine CI. Darum stehen in Doku, Kommentaren und Commits diese Wörter:

| Wort | Bedeutung |
|---|---|
| `#123` | eine Aufgabe (Issue) im privaten GitLab |
| `!123` | ein Änderungsantrag (Merge Request) im privaten GitLab |
| Owner | der Mensch, der entscheidet und Fachliches mit seinem Namen freigibt |
| Lead | die führende KI-Sitzung, die Arbeit verteilt und fertige Änderungen bündelt |
| Lane | der Arbeitsbereich einer KI-Sitzung |
| Zug | mehrere geprüfte Änderungen, die zusammen durch die CI und auf `main` gehen |

Wie das im Einzelnen lief: [docs/einstieg/arbeitsweise-agentisch.md](docs/einstieg/arbeitsweise-agentisch.md).

## Dokumentation im Überblick

Alle Seiten der Dokumentation mit einem Satz dazu: [docs/einstieg/README.md](docs/einstieg/README.md). Dort stehen die
Einstiegsseiten, die Langfassungen der Abschnitte oben und die übrige Doku im Repo (Modelle, Voice, Betrieb, Abnahme,
Präsentation, Herkunft).

Die Pflichtabschnitte stehen in dieser Reihenfolge: [Lösung und Ansatz](#lösung-und-ansatz),
[Ausführung](#ausführung), [Abhängigkeiten und Voraussetzungen](#abhängigkeiten-und-voraussetzungen),
[Konfiguration](#konfiguration), [Grenzen und offene Punkte](#grenzen-und-offene-punkte),
[Vorab Entstandenes](#vorab-entstandenes), [Lizenzen](#lizenzen). Prüfliste dazu: `docs/abgabe/readme-pruefung.md`.
