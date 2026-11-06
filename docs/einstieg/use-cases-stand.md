# Die Use Cases und ihr Stand

Diese Seite ist für die Jury, für Technikerinnen und Techniker und für alle, die wissen wollen, was der Veranstalter
verlangt hat und was davon im Repo nachweislich läuft. Jede Aussage nennt ihren Beleg, eine Datei oder eine
Codestelle. Was nur teilweise geht oder fehlt, steht ausdrücklich da.

Stand: `main` vom 06.11.2026, geprüft am Commit `48761dc`; die Abnahme-Zähler und der Online-Stand von UC2 und UC4
sind auf `bcabeab` nachgezogen. Die Aufgabenstellungen des Veranstalters liegen nicht im Repo; sie
stehen hier sinngemäß, bei den Bewertungsbereichen wörtlich gekürzt. Kurzfassung je Raum: Wurzel-[README](../../README.md).

## Überblick

| Use Case | Gestellt von | Rolle in der Abgabe | Stand in einem Satz |
|---|---|---|---|
| UC3 StatAgent | Veranstalter | gewählt und bewertet (Commit „Select use case uc3“, 05.11.2026 12:10; [`KI-Challenge_UseCase.yaml`](../../KI-Challenge_UseCase.yaml)) | Alle fünf Abgabeteile liegen vor, die Mindestanforderung ist in allen sechs Bewertungsbereichen erfüllt, das Optimum in zwei ganz und in vier teilweise. |
| UC1 SV KI-Lotse | Veranstalter | Zusatz, nicht bewertet | Der Lotse antwortet mit einem Zitat an jeder Aussage; online läuft nur ein aufgezeichneter Fall, eigene Fragen gehen nur lokal. |
| UC2 HealthPolicy Simulator | Veranstalter | Zusatz, nicht bewertet | Institutionen verhandeln mit Moderator über die Wartezeiten auf Facharzttermine; online als Aufzeichnung mit gekennzeichneten erfundenen Beispielbelegen und seit dem 06.11. mit der Seite `/uc2/frage`, auf der ein Modell live auf eine eigene Frage antwortet. Auf der Vorführ-Instanz hinter Passwort lässt sich eine Verhandlung live starten (gebaut und auf einem zweiten Rechner gemessen, auf der Instanz selbst noch nicht); öffentlich bleibt die Aufzeichnung. |
| UC4 Gemeinsamer Einstieg | eigene Idee des Teams | Zusatz, nicht bewertet | Eine Frage läuft durch drei Stationen. Die erste holt die Zahl aus der Datenbank. Die zweite rechnet nur, wenn die Frage das Wort „Wartezeit“ enthält, sonst ist sie Modelltext oder feste Sätze. Die dritte ist eine Vorlage. |

## Use Case 3 StatAgent

Die Aufgabe: Aus 24 Monatslieferungen, das sind die Daten, die die Sozialversicherung jeden Monat schickt, entsteht
eine Beschäftigtenstatistik mit Qualitätsbericht je Monat. Eigene KI-Agenten setzen danach drei Änderungsaufträge
um, ein Mensch gibt jede Änderung mit Namen frei. Die Datenbasis sind 24 Lieferungen mit 10.152.292 Zeilen
([Belegregister](../praesentation/belegregister.md), F3).

### Die fünf Abgabeteile

| Teil laut Aufgabenstellung | Fundort im Repo |
|---|---|
| Aggregations-Sheet nach den Regeln der Fachbeschreibung und nach den Änderungsaufträgen | [`abgabe/aggregationen_v1.xlsx`](../../abgabe/aggregationen_v1.xlsx) („Alte Regeln“, `v1`) und [`abgabe/aggregationen_v2.xlsx`](../../abgabe/aggregationen_v2.xlsx) („Nach den Änderungsaufträgen“, `v2`) |
| 24 Qualitätsberichte | [`abgabe/qualitaetsberichte/`](../../abgabe/qualitaetsberichte/) nach alten Regeln, dazu [`abgabe/qualitaetsberichte_v2/`](../../abgabe/qualitaetsberichte_v2/), je 24 Dateien (`ls`) |
| Ministeriums-Lieferung 07/2026 | Beleg [`abgabe/ministerium_2026-07.beleg.md`](../../abgabe/ministerium_2026-07.beleg.md), 32.741 Personen; die CSV selbst enthält Einzeldaten und liegt bewusst nicht im Repo ([`abgabe/CHECKLISTE.md`](../../abgabe/CHECKLISTE.md), Zeile 49) |
| Protokoll aller Änderungen über die Agenten | [`abgabe/protokoll.md`](../../abgabe/protokoll.md) |
| Angabe zu den Modellen | [`abgabe/modelle.md`](../../abgabe/modelle.md) |

Die Abgabeprüfung `uv run uc3 pruefe-abgabe --mit-db` meldete am 05.11.2026 „Abgabe vollständig.“
([`abgabe/uc3-abnahme.md`](../../abgabe/uc3-abnahme.md), Abschnitt 1). [`abgabe/manifest.json`](../../abgabe/manifest.json)
führt jede Abgabedatei mit Größe und sha256.

### Die sechs Bewertungsbereiche

Jeder Bereich zählt 20 von 120 Punkten. Der Stand folgt der [Kriterien-Karte](../praesentation/kriterien-karte.md),
gemessen am 06.11.2026 auf `main` `5328291`; die Spalte „Nachweis“ zeigt, wo man es selbst prüft.

| Bereich | Mindestanforderung | Optimum | Stand | Nachweis | Was fehlt |
|---|---|---|---|---|---|
| 1 Datenmanagement | „liest alle Lieferungen korrekt ein, Datenmodell nach Vorgabe“ | „versionierter Bestand über alle Lieferungen, Pensionsmeldungen aller Träger … eingelesen“ | Mindest erfüllt, Optimum erfüllt | 24 Lieferungen (F3); Pensionen: 28 von 28 Dateien, 9 Formate, 394 nachgerechnete Summen ohne Abweichung ([Prüfbericht](../uc3/pensionen-pruefbericht.md)) | Pensionszahlen sind noch vorläufig, nicht mit Namen freigegeben (Prüfbericht); Pensionen öffentlich Bediensteter fehlen, die frühere BVA meldet keine (Kriterien-Karte, Zeile 11) |
| 2 Klassifikation | „legt die benötigten Klassifikationen an, je Begriff nur einmal“ | „ÖNACE bis zum 5-Steller und Regionen Österreichs vollständig historisiert, Übergänge aus den amtlichen Änderungslisten, kennt und erklärt sie“ | Mindest erfüllt, Optimum teilweise | `uv run uc3 klass`, Seite `/uc3/klassifikationen`, Tabelle `stat.uebergang` ([`uc3/README.md`](../../uc3/README.md), Befehl `klass`) | ÖNACE 2003 nur bis Ebene 2; Zahlen je Bezirk oder Gemeinde gibt es nicht, weil die Lieferungen nur Bundesland und Abschnitt tragen (Kriterien-Karte, Zeile 13) |
| 3 Qualitätssicherung | „erkennt einen Teil der Fehler, Qualitätsbericht je Monat“ | „erkennt alle Fehler, unterscheidet sie von echten Entwicklungen, jede Annahme begründet und dokumentiert“ | Mindest erfüllt, Optimum teilweise | 24 Berichte, 24 Prüfregeln P01 bis P24 (F15); Beispielbericht August 2024: 2.880 von 2.880 Zahlen gleich (F1); Rückfragen in [`abgabe/rueckfragen/`](../../abgabe/rueckfragen/) | „Alle Fehler“ ist nur für August 2024 belegbar, für die übrigen 23 Monate gibt es keinen Vergleichsbericht (F15); ein Teil der Auffälligkeiten bleibt „nicht erklärbar“ |
| 4 Reporting | „Aggregations-Sheet nach den Regeln der Fachbeschreibung“ | „Datenanfragen … richtig beantwortet, Dashboard“ | Mindest erfüllt, Optimum teilweise | beide Sheets (siehe oben); `uv run uc3 frage`, Seite `/uc3/fragen`; Übersicht `/uc3` | Freie Fragen sind nicht alle geprüft; keine Zahlen je Bezirk oder Gemeinde (Kriterien-Karte, Zeile 21) |
| 5 Weiterentwicklung und Betrieb | „Produktion läuft deterministisch“ | „alle Änderungsaufträge und Ministeriums-Lieferung umgesetzt, nachvollziehbar protokolliert, Live-Änderung per Sprache gelingt“ | Mindest erfüllt, Optimum teilweise | 72 von 72 Wiederholungsläufen mit gleichem Ergebnis-Hash ([`uc3-abnahme.md`](../../abgabe/uc3-abnahme.md), Zeile 38 bis 40); Wege der drei Aufträge in [`aenderungsauftraege-matrix.md`](../plan/uc3/aenderungsauftraege-matrix.md) | Die Live-Änderung ist ein getippter Satz, keine Stimme; von 14 unbekannten Probeaufträgen gelangen 13 ([`live-ruecknahme.md`](../plan/uc3/live-ruecknahme.md), Zeile 64) |
| 6 Bedienbarkeit | „alles lässt sich über die Konsole steuern“ | „übersichtliche Weboberfläche für Läufe, Qualitätsberichte und Annahmen, Klassifikationen, Freigaben und Fragen an die Daten“ | Mindest erfüllt, Optimum erfüllt | `uv run uc3 --help` ([`uc3/statagent/cli.py`](../../uc3/statagent/cli.py)); Seiten unter `/uc3` | Aufträge an die Agenten nimmt nur die Vorführ-Instanz an; die öffentliche Demo ist nur lesend ([README](../../README.md), Abschnitt „Online-Demo“) |

**Ein scheinbarer Widerspruch bei den Pensionen.** [`abgabe/uc3-abnahme.md`](../../abgabe/uc3-abnahme.md) sagt in
Zeile 68 noch „Pensionen sind nicht importiert“. Die Datei gehört zur eingefrorenen Abgabe: `abgabe/manifest.json`
hält ihren sha256 vom 05.11.2026 fest, und eine Änderung unter `abgabe/` würde Prüfung und Upload brechen
([`abgabe/CHECKLISTE.md`](../../abgabe/CHECKLISTE.md), Zeile 32). Auf `main` sind die Pensionsmeldungen inzwischen
eingelesen: [`uc3/README.md`](../../uc3/README.md) (Abschnitt „Pensionen“), [`uc3/statagent/pensionen.py`](../../uc3/statagent/pensionen.py)
und [`docs/uc3/pensionen-pruefbericht.md`](../uc3/pensionen-pruefbericht.md).

**Die formale Abnahmeliste.** Neben dem Jury-Raster prüft das Team die Kriterien seiner eigenen Aufgaben
(Issues) in [`docs/abnahme/matrix-uc3.md`](../abnahme/matrix-uc3.md). Der Schlusslauf am 06.11.2026, geurteilt für
`main` `c16fa881` um 06:07, zählt für UC3: 53 von 76 Kriterien bestanden, 1 nicht bestanden, 5 nicht geprüft, 17 nach
der Abgabe; der Nachtrag auf dem letzten Code-Stand `14c86cc3` um 07:50 zählt 53, 2, 4 und 17
([`schlusslauf-2026-11-06.md`](../abnahme/schlusslauf-2026-11-06.md)). Der Beleg sagt selbst: kein „alles
bestanden“, das Tor ist offen. Das eine „nicht bestanden“ (13-AC4) ist als Restmangel angenommen:
`uc3/statagent/pensionen.py` enthält eine eigene Funktion `freigeben`; die Regeln laufen darin über
`plattform.freigabe` mit Commit und der Zeile `Freigegeben-von`. Offen sind unter anderem zwei Punkte zur Oberfläche
(18-AC2, 18-AC3) und zwei zu den Klassifikationen (75-AC1, 76-AC1). Der volle Lauf 22-1 (24 Läufe und Sheet nach den
Änderungsaufträgen, Liste für das Ministerium) ist danach bestanden. Nach dem Schlusslauf landeten noch Änderungen an
der Weboberfläche; die Matrix zeigt UC3-Belege danach als veraltet, bis ein Nachtrag sie neu misst.

### Die acht technischen Regeln

| Regel (gekürzt) | Wie erfüllt | Nachweis |
|---|---|---|
| 1 Die KI schreibt Code, das Programm rechnet | Kein UC3-Befehl für Lauf, Bericht oder Sheet ruft ein Sprachmodell auf; gleiche Daten und Regeln ergeben denselben Hash | [`uc3/README.md`](../../uc3/README.md), Einleitung; `uc3-abnahme.md`, Zeile 38 bis 40 |
| 2 Lokal und offline | PostgreSQL 16 auf dem eigenen Gerät; der Lauf braucht kein Netz | [README](../../README.md), „Beispiellauf UC3“ |
| 3 Regeln als Daten | Regeln und Prüfungen stehen in `meta.regel` mit Gültigkeit, Begründung und Freigabe | `uc3/README.md`, „Wie ein Lauf rechnet“; Abgabeprüfung „keine Regelkonstanten im Code“ (`uc3-abnahme.md`, Zeile 20) |
| 4 Modelle | Agenten nutzen Azure `gpt-5-4-mini`; austauschbar über `LLM_PROVIDER` | [`abgabe/modelle.md`](../../abgabe/modelle.md) |
| 5 Eure Agenten setzen um | Die drei Aufträge liefen über die eigenen Agenten mit Rollen; die Anweisung ist ein Satz in natürlicher Sprache, getippt | [`agenten-routing.json`](../plan/uc3/agenten-routing.json); gesprochen geht es für UC3 nicht (`uc3-abnahme.md`, Abschnitt 7) |
| 6 Agenten-Code nur unter fünf Bedingungen | Code der Agenten liegt lesbar in `uc3/erzeugt/` und startet nur, wenn genau dieser Inhalt freigegeben ist | [`uc3/erzeugt/README.md`](../../uc3/erzeugt/README.md); Test [`test_agenten_freigabe.py`](../../uc3/tests/test_agenten_freigabe.py) |
| 7 Mensch gibt frei | Vor- und Nachname Pflicht, „Team“ wird abgelehnt; vier Freigaben gab eine KI-Sitzung im Auftrag von Bernhard Götzendorfer ein, er hat sie am selben Abend selbst bestätigt | [`abgabe/protokoll.md`](../../abgabe/protokoll.md), „Hinweise zu den Freigaben“ |
| 8 Protokoll | Jede Änderung als Git-Commit mit Anweisung und Zeile `Freigegeben-von` | `abgabe/protokoll.md`, Abschnitt 1 |

## Use Case 1 SV KI-Lotse

**Was der Veranstalter verlangt.** Gesucht ist kein klassischer Chatbot, sondern ein Lotse, der die Lage einer
Person versteht, nur nötige Rückfragen stellt und passende Leistungen vorschlägt. Er soll Anträge vorbereiten,
Unterlagen und zuständige Stellen nennen und Termine organisieren, in der Sprache und Tiefe, die die Person will.
Er stellt keine Diagnosen und gibt keine Therapie- oder Medikamentenempfehlungen.

**Was im Repo liegt.** Das Paket [`uc1/`](../../uc1/) mit dem Kern, der jede Aussage mit einem Zitat aus der Quelle
belegt und eine Aussage ohne passendes Zitat weglässt ([README](../../README.md), „Grenzen und offene Punkte“).
Dazu Felddateien für Formulare ([`uc1/formulare/`](../../uc1/formulare/)), Stellen in Wien
([`uc1/stellen/`](../../uc1/stellen/)) und ein Terminentwurf als Kalenderdatei, ausdrücklich „nicht gebucht“
([`uc1/erzeugt/termin-wien.ics`](../../uc1/erzeugt/termin-wien.ics); [`matrix-uc1.md`](../abnahme/matrix-uc1.md), Kriterium 81-2).

**Was online läuft.** Die öffentliche Demo zeigt auf `/uc1` nur den aufgezeichneten Pflegefall; eigene Fragen nimmt
der Server dort nicht an (403). Belege: [`web/app/uc1/page.tsx`](../../web/app/uc1/page.tsx), Zeile 15 bis 17, und
[`web/app/api/uc1/frage/route.ts`](../../web/app/api/uc1/frage/route.ts), Zeile 4. Mit eigenen Fragen läuft der
Lotse lokal ([`schnellstart.md`](schnellstart.md)).

**Was offen ist** (laut [`matrix-uc1.md`](../abnahme/matrix-uc1.md), Stand 06.11.2026 05:03):

| Punkt | Stand | Kriterium |
|---|---|---|
| Szenario per Stimme | nicht geprüft | 23-1 |
| Anliegen über mehrere Besuche fortsetzen | nach der Abgabe | 82-1 bis 82-3 |
| Bündel für Gesundheitsförderung und Kind | nach der Abgabe | 83-1 bis 83-3 |
| Namen aus der Frage gehen bei der Erweiterung der Suchbegriffe unverändert an das Modell | nicht bestanden | 121-5 |
| Bürgersprache scheitert an der Prüfung, ob das Zitat die Aussage deckt (2 von 4 Pflege-Aussagen fielen durch) | nicht bestanden | 130-1 (in der Abnahmeliste dem Teil UC4 zugeordnet) |

## Use Case 2 HealthPolicy Simulator

**Was der Veranstalter verlangt.** KI-Agenten vertreten Institutionen des Gesundheitswesens, verhandeln miteinander
und erzeugen nachvollziehbare Kompromisse. Ihre Standpunkte sollen aus Presseberichten belegt sein, echte Personen
dürfen nicht vorkommen, und aktuelle Informationen zählen mehr als alte. Der Mensch soll Argumente, Positionswechsel
und Konflikte sehen; als Szenario nennt die Aufgabe die Wartezeiten auf Facharzttermine, ein spieltheoretischer
Modus ist optional.

**Was im Repo liegt.** Das Paket [`uc2/`](../../uc2/README.md): ein Pool von 14 Akteuren
([`uc2/akteure/`](../../uc2/akteure/), `ls`), aus dem ein Moderator höchstens sechs wählt; Runden für Position,
Debatte, Verhandlung und bis zu zwei Kompromissrunden; jede Zahl wird gegen ihren Beleg oder das Rechenmodell des
Experten geprüft ([`uc2/README.md`](../../uc2/README.md), „Verhandlung“). Es gibt genau einen Fall,
[`uc2/faelle/wartezeiten.yaml`](../../uc2/faelle/wartezeiten.yaml). Das Ergebnis heißt „Entwurf“, bis ein Mensch es
mit Namen freigibt ([README](../../README.md), Tabelle „Was gebaut wurde“).

**Was online läuft.** Zwei Dinge. Erstens eine aufgezeichnete Verhandlung; Starten und Freigeben lehnt der Server ab
([`web/app/api/uc2/faelle/route.ts`](../../web/app/api/uc2/faelle/route.ts), Zeile 52). Die Belege der Aufzeichnung
sind erfunden und am Beleg selbst als „erfundene Beispielquelle“ gekennzeichnet
([`web/components/uc2/buehne/buehne.tsx`](../../web/components/uc2/buehne/buehne.tsx), Zeile 146 bis 150). Zweitens
seit dem 06.11. die Seite `/uc2/frage`: Auf eine eigene Frage zur Gesundheitspolitik wägen drei Interessenvertretungen
ab, ihre Rollen und Sätze schreibt ein Modell (Azure `gpt-5-4-mini`). Online gemessen am 06.11.2026 um 06:52 vom
zuständigen Bereich: Die Seite antwortet live, höchstens 5 Fragen je Minute, und nennt je Organisation echte Medien
als „Quelle: Medium, Monat“, ohne Link auf den Artikel; eine Haltung ohne passenden Artikel steht ohne Quelle da.
Persönliche Angaben und Fragen außerhalb der Gesundheitspolitik bekommen ohne Modellaufruf einen festen Satz. Es ist
keine echte Verhandlung und keine Aussage dieser Organisationen.

Auf der Vorführ-Instanz hinter Passwort lässt sich auf `/uc2` zusätzlich eine Verhandlung live starten, mit Azure
`gpt-5-4-mini` und nur mit erfundenen Beispielbelegen. Gemessen ist das am 06.11.2026 auf einem zweiten Rechner (Lauf
im Container der Instanz, 236 s), auf der Vorführ-Instanz selbst noch nicht. Die Seite sagt das auch im Satz unter der Verhandlung
([`buehne.tsx`](../../web/components/uc2/buehne/buehne.tsx), Zeile 127). Das Ergebnis gibt am Ende ein Mensch mit
Namen frei. Öffentlich bleibt es bei der Aufzeichnung. Aufbau und Schutz:
[`docs/betrieb/vorfuehrung.md`](../betrieb/vorfuehrung.md), Abschnitt „UC2 live“.

**Was offen ist.** Den optionalen spieltheoretischen Modus gibt es nicht: Er ist zurückgestellt, dafür gibt es
weder Code noch Daten noch eine Oberfläche ([`docs/plan/uc2/scope-abgleich.md`](../plan/uc2/scope-abgleich.md),
„Entscheid zum Spieltheoriemodus“). Derselbe Abgleich stuft fünf von sechs Themen der Aufgabe als „teilweise“ ein,
die Verhandlungsmacht als „zurückgestellt“. Die
Rechtstexte (SozDok) sind bereitgestellt, aber nicht indiziert. In [`matrix-uc2.md`](../abnahme/matrix-uc2.md)
(Stand 06.11.2026 05:03) ist von 14 Kriterien keines bestanden, 5 stehen auf „nicht geprüft“ und 9 auf „nach der
Abgabe“, darunter historische Presse (84),
Koalitionen (85) und Handlungsempfehlungen (86).

## Use Case 4, eine Idee des Teams

**Die Idee.** Eine Frage läuft durch drei Stationen: zuerst die Zahl aus der Statistik (UC3), dann die Abwägung
(UC2), zuletzt, was das für die fragende Person heißt (UC1). Reihenfolge und Ablauf:
[`shared/py/plattform/router.py`](../../shared/py/plattform/router.py), Zeile 1 bis 5 und 53. UC4 ist nicht Teil der
Bewertung ([README](../../README.md), Tabelle „Was gebaut wurde“).

| Station | Was dort entsteht | Echt gerechnet? | Beleg |
|---|---|---|---|
| 1 Zahl | erkennt Monat, Region und Branche ohne Sprachmodell und holt die Zahl per SQL aus `stat.stat_beschaeftigte`, mit Abfrage als Beleg | ja | [`uc3/statagent/uc4.py`](../../uc3/statagent/uc4.py), Zeile 1 bis 11 |
| 2 Abwägung | kurze Verhandlung über ein Sprachmodell, eine Runde mit höchstens drei Akteuren; liefert das Modell keinen brauchbaren Text, kommen feste Sätze. Enthält die Frage „Wartezeit“, rechnet der Code vorher das Maßnahmenpaket des Falls durch, und die Verhandlung nutzt diese Zahlen. Sonst gilt: Zählt die Zahl von Station 1 nicht die Versorgung, wägt die Station nicht ab | nur beim Fall Wartezeiten, und dort nur das Paket; sonst nein, Modelltext oder feste Sätze | [`uc2/src/uc2/antwort/adapter.py`](../../uc2/src/uc2/antwort/adapter.py), Zeile 1 bis 20, 110 bis 119, 553 bis 554 und 567 bis 568; [`allgemein.py`](../../uc2/src/uc2/antwort/allgemein.py), Zeile 99 bis 102 und 268 bis 288 |
| 3 Was es heißt | in der Kette eine Vorlage ohne Modell, gebaut aus der Zahl und dem Ergebnis von Station 2 | nein, Vorlage | [`uc1/uc1/uc4.py`](../../uc1/uc1/uc4.py), Zeile 20 bis 25 |

Findet Station 1 keine Zahl, hält die Kette an ([`router.py`](../../shared/py/plattform/router.py), Zeile 15 bis 18).
Station 2 prüft jede Zahl in ihrem Text gegen Beleg oder Kontext und bricht ab, statt eine unbelegte Zahl
auszugeben ([`adapter.py`](../../uc2/src/uc2/antwort/adapter.py), Zeile 17 bis 19).

**Online eingeschränkt.** Lokal ist jede Modellwahl offen. Online gibt es seit dem 06.11. keine Modellwahl und keinen
Testbetrieb mehr: Ist nur ein Anbieter freigegeben, nennt der Kopf der Seite das Modell (Commits `f1911da` und
`a7297f2`). Der Server lässt weiterhin nur die Anbieter zu, die in `UC4_MODELLWAHL` freigegeben sind
([`web/lib/plattform/uc4.ts`](../../web/lib/plattform/uc4.ts), Funktion `modellErlaubt`). Laut
[README](../../README.md) ist das online Azure. Je Internetanschluss gehen standardmäßig höchstens 10 Fragen in der
Minute, dazu kommt ein Tagesbudget für Modellaufrufe (README, „Online-Demo“).

## Für alle, die weiterbauen wollen

Vorschläge des Teams, abgeleitet nur aus den oben belegten offenen Punkten:

| Bereich | Sinnvoller nächster Schritt (Vorschlag) |
|---|---|
| UC3 | Die Stimme der Plattform an UC3 anschließen, damit die Live-Änderung gesprochen gelingt (`uc3-abnahme.md`, Abschnitt 7), und die Pensionszahlen mit Namen freigeben. |
| UC1 | Namen vor der Erweiterung der Suchbegriffe entfernen (Kriterium 121-5), danach Anliegen über mehrere Besuche (82). |
| UC2 | Historische Presse und SozDok indizieren (84, `scope-abgleich.md`) und online echte Belege mit Namensliste zeigen. |
| UC4 | Weitere Fälle in `uc2/faelle/` anlegen, damit Station 2 auch außerhalb der Versorgung abwägt. |
| Abnahme | Die offenen Punkte des Schlusslaufs schließen und die UC3-Belege nach den letzten Änderungen an der Weboberfläche neu messen ([`schlusslauf-2026-11-06.md`](../abnahme/schlusslauf-2026-11-06.md)). |

## Weiter lesen

- [Übersicht der Einstiegsseiten](README.md)
- [Kriterien-Karte UC3](../praesentation/kriterien-karte.md) und [Belegregister](../praesentation/belegregister.md)
- [Abgabe UC3](../../abgabe/README.md) und [Abnahme UC3](../../abgabe/uc3-abnahme.md)
- [Zahlen nachprüfen](zahlen.md), [Architektur](architektur.md), [Schnellstart](schnellstart.md)
- [StatAgent im Detail](../../uc3/README.md)
