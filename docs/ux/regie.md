# UI-Regie: Bestandsaufnahme und Ziel je Seite

Stand 05.11.2026 18:00. Grundlage: alle Seiten live und lokal mit Daten, Desktop 1440 und Handy 390.
Maßstab: Fünf-Sekunden-Test, eine Hauptaussage und eine Hauptaktion je Bildschirm, höchstens drei Schritte je
Journey, kein totes Bedienelement, gestaltete Zustände, keine Schablonen, Bewegung nur wenn sie erklärt.
Pen ist Ausgangsbasis, Vereinfachen geht vor.

## Befund in einem Satz

Jede Seite erklärt sich selbst, bevor sie etwas zeigt: Begriffsleisten, Hinweise, Beleg-Pillen an jeder Zahl und
gesperrte Knöpfe stapeln sich, und die eine Sache, die man tun soll, geht darin unter.

## Systemweit (gilt für alle Seiten, Bausteine in `shared/ui`)

| Baustein | heute | Ziel |
|---|---|---|
| Kopfzeile | Logo, Untertitel, lila Pille „Testbetrieb: keine KI angeschlossen“, Protokoll-Knopf, sechs Reiter, grünes Abzeichen „bewertet“ | Name, Reiter in Jury-Reihenfolge (StatAgent zuerst), Protokoll als Textlink. Keine Pille, kein Abzeichen, kein Lila. |
| Beleg | mintgrüne Pille an jeder Zahl mit Tabelle, Regelstand, Lauf, „vorläufig“, „SQL ansehen“ | ein ruhiger Textlink „Beleg“ je Aussage; Klick öffnet eine Seitenleiste mit Tabelle, Regelstand, Lauf und SQL. |
| Begriffsleisten | fünf Worterklärungen über dem Inhalt | weg. Erklärung nur am Wort, an dem man stolpert (unterstrichen, Klick zeigt einen Satz). |
| Seitenbalken | farbiger Strich links an Zitat, Moderator, Agenten-Vorschlag, Hinweis | weg. Abstand und eine kleine Zeile darüber reichen. |
| Status | Abzeichen „fest / bewegt / wartet“, Warn-Kästen, Häkchen-Icons | ein Statuswort mit Punkt in Grau oder Gelb. Grün nur für „freigegeben“. |
| Modell | Pille im Kopf | eine Zeile an der Stelle, an der ein Modell geschrieben hat: „Text: Azure gpt-5-4-mini“. |
| Zustände | „Die Zahlen ließen sich gerade nicht lesen“, „noch leer“, rote Sperr-Meldungen | je Zustand ein ruhiger Block mitten in der Fläche: ein Satz, eine Aktion. Was online nicht geht, wird nicht angeboten. |
| Text | vier bis fünf Größen, lange Sätze | Überschrift, Text, Kleintext. Sätze unter 20 Wörtern, Sie-Form. |

Navigation: Reiter, deren Seite leer ist, fallen weg, bis sie Inhalt haben (heute live: UC1, Präsentation).

## UC3 StatAgent (bewertet)

**Die eine Journey:** Monate → angehaltener Monat (Oktober 2025) → Freigabe einer Änderung mit Namen.
„Fragen an die Daten“ ist der zweite Einstieg zum Selbst-Ausprobieren.
**Unternavigation neu:** Monate · Freigaben · Fragen an die Daten. Qualitätsbericht ist die Monatsseite selbst,
Klassifikationen und Regeln sind ein ruhiger Link „Regeln und Klassifikationen“ rechts.

### /uc3 Monate
- bleibt: Hauptsatz mit 399.027, Tabelle der 24 Monate, Knopf „Oktober 2025 prüfen“, Regelsatz v1/v2.
- fällt weg: Begriffsleiste (Stichtag, Zeile, Abrechnung …), 24 Beleg-Pillen in der Tabelle, Spalten „gelesen / nicht gezählt / ausgeschlossen“ (hinter „Details“), zweiter Zwischentitel.
- neu: Zeitreihe als 24 Balken über der Tabelle (die zwei angehaltenen Monate gelb, Klick führt in den Monat), Hauptsatz „24 Monate gerechnet. 2 warten auf die Fachabteilung.“, ein Beleg-Link je Zeile.

### /uc3/laeufe/[monat] (wird zugleich der Qualitätsbericht)
- bleibt: Hauptsatz „Im Oktober 2025 fehlt jedes fünfte …“, Rechnung 313.154 + 77.746 = 390.900 groß, Liste der Auffälligkeiten.
- fällt weg: Begriffsleiste, Beleg-Pille unter jedem Absatz, Codes wie `P17_zeilenzahl_vs_vormonat` im Fließtext, Bundesländer-Tabelle offen.
- neu: Auffälligkeiten als Zeilen (Punkt, ein Satz, Anzahl), Klick klappt „Was wir tun“ und Beleg auf; die drei, die den Monat anhalten, oben. Danach die fünf Abschnitte der Berichtsvorlage als Sprungmarken. Rechnung baut sich beim Laden einmal auf (reduced-motion: statisch).

### /uc3/berichte, /uc3/berichte/[monat]
- bleibt: Inhalt der fünf Abschnitte, Route bleibt erreichbar (Links aus Präsentation und Abgabe).
- fällt weg: eigene Liste neben der Monatstabelle, doppelter Inhalt zur Monatsseite.
- neu: Monatstabelle hat die Spalte „Bericht“; /uc3/berichte/[monat] zeigt dieselbe Seite wie der Monat.

### /uc3/klassifikationen
- bleibt: ÖNACE 2008 → 2025 nach Branchennamen, Stand von Auftrag 1 mit Name und Zeit.
- fällt weg: als eigener Reiter.
- neu: Gegenüberstellung wie Präsentation Szene 7 (alt links, neu rechts, Linien), erreichbar über „Regeln und Klassifikationen“.

### /uc3/freigaben, /uc3/freigaben/[id]
- bleibt: Auftrag im Wortlaut, Probe vorher/nachher, „Freigegeben von Vorname Nachname, Zeit“.
- fällt weg: Begriffsleiste, leerer Reiter „Wartet auf Sie (0)“ als Startansicht, Seitenbalken am Agenten-Vorschlag, Regelsatz-Vergleich offen.
- neu: Liste zeigt die drei Aufträge als Zeilen mit Name und Zeit; Detail: oben Auftrag, Mitte vorher → nachher groß, unten Freigabe-Block. Online ohne Formular.

### /uc3/fragen
- bleibt: Eingabe, Beispiele, Antwort mit Zahl und Abfrage.
- fällt weg: zweiter Erklärsatz, Pillen-Optik der Beispiele.
- neu: Eingabe mittig groß, Beispiele als schlichte Liste; Antwort: große Zahl, ein Satz „Verstanden: …“, „Abfrage ansehen“; Rückfrage als freundliche Frage mit Knöpfen.

## UC2 HealthPolicy

**Die eine Journey:** Fall lesen → Verhandlung ansehen (Bühne, ein Sprecher zur Zeit) → Ergebnis.

### /uc2 Fall
- bleibt: die Frage groß, Ziel und Rahmen in einer Zeile.
- fällt weg: 14 Gruppen als Checkboxen (wirkungslos), Schrittleiste, Vorführmodus-Strich, Worterklärungen, Fußnote, Moderator- und Experten-Absatz, „Verhandlung starten“ online (endet in Sperre).
- neu: die sechs Gruppen am Tisch als ruhige Reihe, darunter eine Hauptaktion „Verhandlung ansehen“.

### /uc2/panel
- bleibt: Runden, Positionen je Thema, Experte mit Zahlen, Moderator-Zusammenfassung, Belege.
- fällt weg: sechs Positionskarten gleichzeitig, Pillen „Stützt sich auf“, Abzeichen „fest/bewegt“, gelbe Warnkästen, Gesprächsverlauf offen.
- neu: Bühne. Oben vier Themen als Linie von „dagegen“ bis „dafür“, darauf sechs Punkte. In der Mitte genau ein Sprecher: Name, ein Satz, ein Beleg. Bewegt er sich, wandert sein Punkt sichtbar. Moderator spricht zwischen den Runden, Experte bei Zahlen. Steuerung: Pause, Weiter, Tempo. Am Ende Ergebnis je Thema in einem Satz.

## UC4 Einstieg

**Die eine Journey:** Frage stellen → drei Stationen antworten nacheinander → Antwort mit Belegen.
- bleibt: Eingabe, die drei Stationen.
- fällt weg: lange Überschrift, ausgegrauter Sprechknopf mit Erklärsatz, Modellwahl solange online wirkungslos (Stufe A), Platzhaltertext in den Karten, rote Sperr-Meldungen.
- neu: Stationen als Kette, die nacheinander aufleuchten und ihre Antwort aufklappen (NDJSON-Strom von E0); online in Stufe A nur Station StatAgent, ohne leere Karten.

## UC1 KI-Lotse
- live leer („kommt mit dem nächsten Stand“). Reiter weg, bis !69 drauf ist; dann Abnahme nach demselben Maßstab.

## Landing /
- zuletzt. Erster Eindruck oben ruhig; die lange Scroll-Strecke wird nach UC3 geprüft.

## Präsentation /praesentation (!80)
- passt nach vier Änderungen (an e5-szenen-45): Szene 3 Oktober gelb statt grünes Häkchen, Szene 4 Screenshot durch großen Freigabe-Baustein ersetzen, Szene 5 in zwei Takte teilen, Szene 8 Satz zu 576 umschreiben.
