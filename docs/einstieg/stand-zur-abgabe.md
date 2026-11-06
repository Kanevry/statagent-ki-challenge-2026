# Stand zur Abgabe, 06.11.2026, Langfassung

Diese Seite ist die Langfassung des Abschnitts „Stand zur Abgabe“ aus dem README. Sie nennt je Use Case, was am
Tag der Abgabe wirklich läuft und was offen ist, mit Beleg. Bewertet wird Use Case 3, die anderen Use Cases sind
Zusatz.

Gemessen wurde am 06.11.2026 auf zwei Ständen von `main`. Die Bereiche in der Tabelle stammen aus der
Kriterien-Karte, gemessen auf `ceef8b1` (online 07:27 bis 07:35, Bereich 5 auf der Vorführ-Adresse 06:15 bis 06:28, auf einem früheren Stand von `main`).
Die Zahlen der Abnahme unten sind für `14c86cc3` geurteilt (07:50, Prüfläufe 07:39 bis 07:50). Abgegeben ist der
Stand von `main` beim letzten Push.

Zurück zum [README](../../README.md#stand-zur-abgabe-06112026).

## Use Case 3 StatAgent

Die öffentliche Demo ist lesend: Man sieht alle Seiten und kann Fragen an die Daten stellen, die das Programm ohne
Sprachmodell beantwortet. Aufträge an die Agenten und Freigaben mit Namen laufen auf einer eigenen Vorführ-Adresse
mit Passwort ([`docs/betrieb/vorfuehrung.md`](../betrieb/vorfuehrung.md)) und lokal.

Stand je Bewertungsbereich der Aufgabenstellung. Die Einzelheiten mit Beleg je Zeile stehen in der
[Kriterien-Karte](../praesentation/kriterien-karte.md), hier nur die Zusammenfassung:

| Bereich | Mindestanforderung | Optimum | Was zum Optimum fehlt |
|---|---|---|---|
| 1 Datenmanagement | erfüllt | erfüllt | |
| 2 Klassifikation | erfüllt | teilweise | ÖNACE und Regionen sind bis zur tiefsten Ebene da, Zahlen gibt es aber nur je Branchenabschnitt und Bundesland |
| 3 Qualitätssicherung | erfüllt | teilweise | nur August 2024 hat einen Vergleichsbericht; ob in den anderen 23 Monaten alle Fehler gefunden sind, lässt sich nicht belegen |
| 4 Reporting | erfüllt | teilweise | Dashboard ist da; freie Fragen an die Daten sind nicht alle geprüft, siehe unten |
| 5 Weiterentwicklung und Betrieb | erfüllt | teilweise | die Live-Änderung wird getippt, nicht gesprochen |
| 6 Bedienbarkeit | erfüllt | erfüllt | |

Was man dazu wissen muss:

- **Zahlen nach den alten Regeln:** 22 der 24 Monate sind mit Namen veröffentlicht. März und Oktober 2025 sind
  angehalten und bleiben vorläufig, bis die Fachabteilung die Rückfragen R3 und R4 beantwortet
  ([`abgabe/README.md`](../../abgabe/README.md), „Stand der Zahlen“).
- **Zahlen nach den Änderungsaufträgen:** Hier zählt ein Beschäftigungsverhältnis, wenn es irgendwann im Monat
  bestand, nicht nur am Stichtag. Die Regeln sind freigegeben, die Monate selbst sind noch nicht mit Namen
  veröffentlicht: Alle 24 Monate sind dort vorläufig (so steht es im Kopf jedes Berichts in
  [`abgabe/qualitaetsberichte_v2/`](../../abgabe/qualitaetsberichte_v2/)).
- **Pensionen:** Die Pensionsmeldungen aller Träger sind eingelesen (28 von 28 Dateien, 394 Summen ohne
  Abweichung), der Stand ist vorläufig und noch nicht mit Namen freigegeben
  ([`docs/uc3/pensionen-pruefbericht.md`](../uc3/pensionen-pruefbericht.md)). Sie kamen dazu, nachdem die
  Abgabedateien eingefroren waren. Deshalb sagt [`abgabe/uc3-abnahme.md`](../../abgabe/uc3-abnahme.md) in Zeile 68 noch
  „Pensionen sind nicht importiert“.
- **Live-Änderung:** Den Auftrag gibt man als getippten Satz ein, eine Sprachsteuerung dafür gibt es nicht. Ein
  Agent macht daraus einen Vorschlag mit Zahlen vorher und nachher, ein Mensch gibt mit Namen frei oder lehnt ab.
- **Fragen an die Daten, bekannte Grenzen:**
  - Eine Frage über einen Zeitraum mit zwei Aufteilungen („nach Geschlecht und Bundesland“) liefert nur die
    Aufteilung nach Geschlecht (Issue #207).
  - Die Frage nach der Fluktuation je Wirtschaftsbereich kann unter Last in die Zeitgrenze laufen und antwortet
    dann „später noch einmal fragen“. Allein gestellt liefert sie die Zahl. Eine falsche Zahl kommt nicht
    (Abnahme 74-AC1, Restmangel).
  - „Vorher und nachher“ in einer einzigen Frage sagt das Programm ab und nennt ein Beispiel für zwei einzelne
    Fragen (`uc3/statagent/frage.py`).
- **Protokoll in der Oberfläche:** Das Protokoll-Panel nennt bei einem freigegebenen Vorschlag weder den Namen noch
  die Zeit der Freigabe (Issue #210). Beides steht auf der Seite `/uc3/freigaben` und in
  [`abgabe/protokoll.md`](../../abgabe/protokoll.md).
- **Abnahme:** Im Schlusslauf sind für UC3 53 von 76 Kriterien bestanden, 2 nicht bestanden, 4 nicht geprüft und
  17 für die Zeit nach der Abgabe vorgesehen. Gezählt ist die eigene Prüfliste des Teams, nicht das Bewertungsraster.
  Das ist kein „alles bestanden“
  ([`docs/abnahme/schlusslauf-2026-11-06.md`](../abnahme/schlusslauf-2026-11-06.md), Nachtrag auf dem letzten
  Code-Stand).

## Die anderen Use Cases

| Use Case | Stand zur Abgabe |
|---|---|
| UC1 SV KI-Lotse | Online zeigt `/uc1` einen aufgezeichneten Fall. Eigene Fragen beantwortet der Lotse nur lokal; online fehlt seine Datenbank (Issue #143). |
| UC2 HealthPolicy Simulator | Die Verhandlung auf `/uc2` ist online eine Aufzeichnung (Issue #144). Live antwortet ein Modell unter „Eigene Frage ausprobieren“ (`/uc2/frage`). Die Rollen spielt eine KI, es ist keine echte Verhandlung. |
| UC4 Gemeinsamer Einstieg | Eigene Idee des Teams, ein Ausblick und nicht Teil der Bewertung. Die Zahl kommt aus StatAgent, die beiden anderen Antworten schreibt ein Modell oder eine Vorlage. Online ist das Modell fest Azure, eine Auswahl gibt es dort nicht. |

Mehr dazu, mit Fundstellen im Code: [`docs/einstieg/use-cases-stand.md`](use-cases-stand.md).
