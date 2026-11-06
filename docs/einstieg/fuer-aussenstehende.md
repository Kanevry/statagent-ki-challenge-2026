# Für alle, die das Projekt zum ersten Mal sehen

Diese Seite ist für neugierige Menschen ohne Vorwissen zu Statistik, Sozialversicherung oder Softwareentwicklung.
Nach rund zehn Minuten können Sie erklären, was StatAgent ist, und sich selbst durch die öffentliche Demo klicken
(Fachwörter: siehe Wörterbuch unten).

## Was ist das hier?

Die KI Challenge 2026 ist ein Wettbewerb des Dachverbands der österreichischen Sozialversicherungsträger und der
Wirtschaftskammer Wien am 5. und 6. November 2026: Start war am Donnerstag um 12:00 Uhr, die Teams hatten laut
Veranstalter knapp 24 Stunden, die Abgabe war am Freitag um 9 Uhr (Teilnahmeinformationen und Aufgabenstellung des
Veranstalters, nicht im Repo).
Dieses Repo ist der Beitrag von Team OneShotAndy ([README](../../README.md)).
Das Team hat Use Case 3 gewählt: „StatAgent“, ein Programm mit KI-Helfern für eine monatliche Statistik.
Bewertet wird nur dieser Use Case; drei weitere Bereiche sind daneben entstanden (Abschnitt „Die anderen Use Cases“).

## Die Aufgabe in einfachen Worten

Jeden Monat schickt die Sozialversicherung eine **Lieferung**: eine große Tabelle mit allen
Beschäftigungsverhältnissen, also sozialversicherten Jobs, der letzten drei Monate. Daraus entsteht die
Beschäftigtenstatistik: Wie viele Beschäftigungsverhältnisse gibt es am letzten Tag des Monats, nach Bundesland,
Geschlecht, Branche und Art der Anstellung?

Die Aufgabe des Veranstalters hat drei Schwierigkeiten eingebaut:

- **Lieferungen enthalten Fehler.** Zeilen sind doppelt, Angaben fehlen, ganze Gruppen verschwinden. Das Programm
  soll Fehler finden, sie von echten Entwicklungen unterscheiden und jede eigene Annahme begründen.
- **Regeln ändern sich.** Nach der ersten Fassung kommen drei Änderungsaufträge, etwa „gezählt wird jeder Job, der
  mindestens einen Tag im Monat besteht“ statt nur am letzten Tag. Die eigenen KI-Helfer des Teams sollen sie
  umsetzen, nicht das Werkzeug, mit dem das Programm gebaut wurde.
- **Gerechnet wird ohne KI.** Die Aufgabe verlangt: Zahlen entstehen nur durch Code, der auch ohne Sprachmodell
  läuft, und zwei Läufe mit denselben Daten liefern dieselben Zahlen.

Die Daten sind erfunden, in der Größe etwa ein Zehntel Österreichs: 24 Monatslieferungen von August 2024 bis Juli 2026
(Fachbeschreibung des Veranstalters; im Repo [`docs/sprache.md`](../sprache.md), Kernsätze).

Ein Vergleich aus dem Alltag: Eine Lieferung ist wie die Monatsabrechnung einer Bank. Fehlt darin plötzlich jede
fünfte Buchung, schreibt man nicht „das Geld ist weg“, sondern fragt zuerst nach, ob die Abrechnung vollständig ist.

## Was StatAgent macht

| Das Programm rechnet | Der KI-Agent schlägt vor | Ein Mensch entscheidet |
|---|---|---|
| Es liest jede Lieferung ein, prüft sie mit festen Regeln und zählt die Beschäftigungsverhältnisse am Stichtag. | Er schreibt aus einem Satz in Alltagssprache einen Vorschlag für eine neue oder geänderte Regel. | Er gibt den Vorschlag mit Vor- und Nachnamen frei oder lehnt ihn ab. „Team“ oder „Admin“ reicht nicht. |
| Es rechnet einen Monat vor und nach der vorgeschlagenen Änderung, damit man die Wirkung sieht. | Der Vorschlag steht im Protokoll, mit dem Modell und der Anweisung. | Erst mit dem Namen wird die Änderung wirksam; dazu entsteht ein Eintrag im Protokoll. |
| Es beantwortet Fragen an die Daten mit Zahl und Abfrage, ohne Sprachmodell. | | Monate mit unklaren Daten bleiben vorläufig, bis ein Mensch sie veröffentlicht. |

Belege: [README](../../README.md), Abschnitte „Wie UC3 rechnet“ und „Freigabe durch einen Menschen“;
`uc3/statagent/frage.py` („Beantwortet eine Datenanfrage ohne Sprachmodell“).

Der Grundsatz steht in der [Langfassung zu „Lösung und Ansatz“](loesung-und-ansatz.md) wörtlich so: **„Die KI schreibt Code und Texte, das Programm rechnet.“** In der
gemeinsamen Wortliste des Teams ([`docs/sprache.md`](../sprache.md), Kernsätze) heißt er: **„Die KI schreibt Code und
Regeln, gerechnet wird ohne KI, ein Mensch gibt mit Namen frei.“**

## Zwei Beispiele zum Mitdenken

**Der angehaltene Monat Oktober 2025.** Die Lieferung für Oktober 2025 hat 345.078 Zeilen, die für September
434.104. Die Prüfung findet: 78.949 von 394.200 Beschäftigungsverhältnissen, die Ende September noch liefen, fehlen in
der Lieferung ganz, das ist jedes fünfte. Das Programm hält den Monat an und markiert ihn als vorläufig; es löscht
nichts und übernimmt 77.746 Verhältnisse aus der Septemberlieferung, sodass 390.900 als vorläufiger Bestand gelten.
In der Lieferung für November sind 78.733 der fehlenden wieder da: Die Lieferung war unvollständig, einen Einbruch der
Beschäftigung gab es so nicht.
Quellen: [Qualitätsbericht Oktober 2025](../../abgabe/qualitaetsberichte/2025-10.md),
[Belegregister](../praesentation/belegregister.md) F11, [Drehbuch der Vorführung](../praesentation/demo-drehbuch.md) D1.

**Die Regeländerung „Beamte zählen nicht mehr mit“.** Diesen Satz tippt man in der Vorführung als Auftrag ein, für
den Monat Juli 2026. Der Agent schreibt daraus einen Vorschlag, und das Programm rechnet den Monat zweimal: Die
Beamten gehen von 12.289 auf 0, die Gesamtzahl sinkt um 12.289, Arbeiter und Angestellte bleiben gleich. Bis zum
Vorschlag vergingen bei einer Messung am 06.11.2026 um 02:36 Uhr 2 Minuten 55 Sekunden. Geändert ist dann noch
nichts: Wirksam wird die Regel erst mit einer Freigabe mit Namen, und auch das lässt sich mit einem neuen Auftrag
zurücknehmen.
Quellen: [Drehbuch](../praesentation/demo-drehbuch.md) D2, [Kriterien-Karte](../praesentation/kriterien-karte.md)
Bereich 5. Diese Änderung läuft nur in der Vorführung, nicht auf der öffentlichen Demo.

## Rundgang durch die öffentliche Demo

Adresse: **https://ki-challenge.gotzendorfer.at**. Die Online-Demo ist lesend: Man kann alles ansehen und Fragen
stellen, aber keine Änderung freigeben und keinen Lauf starten. Solche Anfragen lehnt der Server ab
([README](../../README.md), „Online-Demo“). Alle Seiten unten waren am 06.11.2026 um 06:48 Uhr öffentlich
erreichbar. Bis zur Abgabe ändern sich noch Kleinigkeiten an der Oberfläche.

| Seite (Pfad) | Was man dort sieht | Worauf man achten kann |
|---|---|---|
| Startseite `/` | Was StatAgent tut, erzählt als Weg der Daten in fünf Schritten: Lieferungen kommen an, werden geprüft, gezählt und belegt. | Wie aus einer Lieferung eine Zahl mit Beleg wird. |
| Dashboard `/uc3` | Kurve, Kennzahlen und alle 24 Monate mit Status, wahlweise nach „Alte Regeln“ (`v1`) oder „Nach den Änderungsaufträgen“ (`v2`). | Welche Monate vorläufig sind; an Zahlen lässt sich die Abfrage dahinter ansehen. |
| Qualitätsberichte `/uc3/berichte` | Je Monat einen Bericht mit Auffälligkeiten, Revisionsbedarf und Stand. | Oktober 2025 unter `/uc3/berichte/2025-10`: Warum der Monat angehalten ist. |
| Annahmen `/uc3/annahmen` | Die Annahmen des Teams zu fehlerhaften Daten, jede als Regel umgesetzt. | Zu jeder Annahme die Begründung. |
| Regeln und Klassifikationen `/uc3/klassifikationen` | Die Regeln und die Verzeichnisse für Branchen, Bundesländer, Bezirke und Gemeinden, mit Suche. | Wie eine Branche oder Gemeinde über die Jahre umbenannt oder zusammengelegt wurde. |
| Freigaben `/uc3/freigaben` | Die Vorschläge der Agenten, was jeder Auftrag geändert hat und wer ihn freigegeben hat. | Der Name der freigebenden Person und die Zahlen vorher und nachher. |
| Fragen an die Daten `/uc3/fragen` | Ein Feld für eigene Fragen, etwa nach Männern und Frauen je Bundesland. | Zur Antwort gehört die Abfrage; bei unklaren Fragen sagt das Programm ab, statt zu raten. |
| Ergebnisse `/uc3/ergebnisse` | Die beiden Excel-Dateien der Abgabe zum Herunterladen und die Liste für das Ministerium. | Es gibt zwei Fassungen, je eine pro Regelstand. |
| Pensionen `/uc3/pensionen` | Eine zweite Statistik aus den Meldungen der Pensionsversicherungsträger. | Jeder Träger liefert in seinem eigenen Excel-Format; die Summen bildet das Programm. |
| Gemeinsamer Einstieg `/uc4` | Eine Frage, die nacheinander drei Bereiche beantworten. | Die Zahl kommt aus StatAgent, mit Beleg. |
| Präsentation `/praesentation` | Die Folien für die Jury. | Die Kernzahlen auf einen Blick. |
| Ablauf `/ablauf` | Wie das Projekt in der Challenge entstanden ist, mit Zeitleiste. | Die Zeitpunkte und die Zahl der Aufgaben und Änderungen, mit Stand. |

Für Fragen gilt online eine Grenze: höchstens 10 Fragen in der Minute je Internetanschluss und ein festes
Tageskontingent an Modellaufrufen ([README](../../README.md), „Online-Demo“).

## Die anderen Use Cases

Neben StatAgent sind drei weitere Bereiche entstanden; sie werden nicht bewertet. Der Stand im Einzelnen steht in
[use-cases-stand.md](use-cases-stand.md). Alles hier stammt aus dem [README](../../README.md), Tabelle „Was gebaut
wurde“ und „Grenzen und offene Punkte“.

- **UC1, SV KI-Lotse:** Er hilft bei Fragen zu Gesundheit und Sozialversicherung, fragt bei Bedarf nach und belegt
  jede Aussage mit einem Zitat aus der Quelle. Er ersetzt keine Beratung, gibt keine Diagnose und keine
  Medikamentenempfehlung und lässt Aussagen ohne passendes Zitat weg.
- **UC2, HealthPolicy Simulator:** Interessenvertretungen verhandeln in Runden mit einem Moderator, mit Beleg aus dem
  Pressespiegel oder als Modellannahme markiert; ein Mensch gibt das Ergebnis mit Namen frei. Die Akteure spielt ein
  Sprachmodell, es ist eine Simulation. Online zeigt `/uc2` eine aufgezeichnete Verhandlung mit gekennzeichneten,
  erfundenen Beispielbelegen; seit dem 06.11. kann man auf `/uc2/frage` zusätzlich eine eigene Frage stellen, auf die
  ein Modell live antwortet.
- **UC4, Gemeinsamer Einstieg (eigene Idee des Teams):** Eine Frage läuft nacheinander durch StatAgent, den Simulator
  und den Lotsen: Zahl, Abwägung, Erklärung. Online dauerte eine ganze Frage mit Azure 13 Sekunden (gemessen am 06.11.
  um 05:01); fällt ein Bereich aus, steht er als „fehlt“ da.

## Kleines Wörterbuch

| Begriff | Bedeutung |
|---|---|
| Agent | Ein Programmteil, der mit einem Sprachmodell aus einer Anweisung in Alltagssprache einen Vorschlag für eine Regel oder Code schreibt. |
| Änderungsauftrag | Eine der drei Regeländerungen, die die Aufgabe nach der ersten Fassung der Statistik vorgibt und die die eigenen Agenten umsetzen. |
| Annahme | Eine begründete eigene Entscheidung, wie mit fehlerhaften Daten umzugehen ist; sie steht im Qualitätsbericht. |
| Beschäftigungsverhältnis | Ein sozialversicherter Job; wer zwei Jobs hat, zählt zweimal. |
| deterministisch | Zwei Läufe mit denselben Daten und Regeln ergeben genau dieselben Zahlen, geprüft über eine Prüfsumme über das ganze Ergebnis. |
| Freigabe | Ein Mensch bestätigt mit Vor- und Nachnamen, dass eine Änderung gilt; ohne Freigabe ändert sich nichts. |
| Klassifikation | Ein Verzeichnis mit Codes und Bezeichnungen, etwa für Geschlecht, Bundesland oder Branche, mit Versionen und Übergängen zwischen ihnen. |
| Lieferung | Die Daten, die die Sozialversicherungsträger jeden Monat schicken. |
| Ministeriums-Lieferung | Eine Sonderauswertung für das Ministerium: Personen mit mindestens 200 Tagen als Arbeiter im ÖNACE-Abschnitt C in den letzten zwölf Monaten, Berichtsmonat Juli 2026. |
| ÖNACE | Die österreichische Einteilung der Wirtschaftszweige; bis Dezember 2024 gilt die Fassung 2008, ab Jänner 2025 die Fassung 2025. |
| Protokoll | Die Aufzeichnung jeder Änderung über die Agenten: Anweisung, was geändert wurde und wer freigegeben hat ([`abgabe/protokoll.md`](../../abgabe/protokoll.md)). |
| Qualitätsbericht | Der Bericht zu jeder Lieferung: was geprüft wurde, was auffiel und was das für die Zahlen heißt. |
| Regelstand | Nach welchen Regeln gezählt wird: „Alte Regeln“ (`v1`, nach der Fachbeschreibung) oder „Nach den Änderungsaufträgen“ (`v2`). |
| Rückfrage | Eine Frage an die Fachabteilung mit Beleg; die Antwort wird zur Regel. |
| Sprachmodell | Eine KI, die Texte liest und schreibt; für die Agenten von StatAgent ist das Azure OpenAI `gpt-5.4-mini`. |
| Stichtag | Der letzte Tag des Monats; gezählt wird jedes Beschäftigungsverhältnis, das an diesem Tag besteht. |

Quellen: [`docs/sprache.md`](../sprache.md), [README](../../README.md), Unterlagen des Veranstalters (nicht im Repo).

## Häufige Fragen

**Rechnet die KI die Zahlen?** Nein: Der Monatslauf ruft kein Sprachmodell auf, und zwei Läufe mit denselben Daten
und Regeln liefern dieselbe Prüfsumme ([README](../../README.md), „Wie UC3 rechnet“). Bei StatAgent schlägt ein
Modell nur Änderungen vor, und an das Modell gehen nie Einzeldaten ([`docs/models.md`](../models.md)). In UC1 und UC2
schreibt ein Modell die Antworten; das steht dort auf der Seite dabei.

**Kann die KI allein etwas ändern?** Nein: Jede Änderung an Regeln oder Code braucht eine Freigabe mit Vor- und
Nachnamen, Rollen wie „Team“ werden abgelehnt. Ein Agenten-Skript startet nur, wenn genau dieser Dateistand
freigegeben ist ([README](../../README.md), „Freigabe durch einen Menschen“).

**Sind das echte Daten?** Nein, es sind erfundene Daten des Veranstalters, in der Größe etwa ein Zehntel Österreichs,
ohne personenbezogene Daten. Sie liegen nicht im Repo ([README](../../README.md), „Grenzen und offene Punkte“).

**Läuft das nur in der Cloud?** Nein: Das Zählen braucht kein Netz und kein Sprachmodell und läuft auf dem eigenen
Rechner, wie es die Aufgabe verlangt ([README](../../README.md), „Beispiellauf UC3“). Die Agenten brauchen ein
Sprachmodell, standardmäßig Azure; ein lokales Modell für den Betrieb ohne Netz ist vorgesehen, gelaufen ist es bisher
nicht ([README](../../README.md), „Modelle“).

**Kann ich das selbst ausprobieren?** Ja, auf https://ki-challenge.gotzendorfer.at lesend und mit Fragen an die
Daten. Wer es auf dem eigenen Rechner starten will, findet die Befehle in [schnellstart.md](schnellstart.md); für
StatAgent braucht man dazu das Datenpaket des Veranstalters.

## Weiter lesen

- [Übersicht dieses Ordners](README.md)
- [Schnellstart](schnellstart.md): das Projekt auf dem eigenen Rechner starten
- [Zahlen](zahlen.md): die wichtigsten Zahlen mit Herkunft
- [Für das Management](fuer-management.md)
- [Architektur](architektur.md): wie die Teile zusammenhängen
- [Agentisch arbeiten](arbeitsweise-agentisch.md): wie das Team mit KI-Helfern gebaut hat
- [Stand der Use Cases](use-cases-stand.md)
- [README des Repos](../../README.md) und [StatAgent im Detail](../../uc3/README.md)
