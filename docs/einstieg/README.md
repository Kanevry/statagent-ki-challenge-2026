# Einstieg in das Projekt

Dieser Ordner ist der Einstieg für alle, die das Projekt verstehen, starten oder nachprüfen wollen, mit oder ohne
Technikwissen. Jede Seite ist für eine Lesergruppe geschrieben und verweist für Einzelheiten auf die Dateien im Repo.

## Die Seiten

| Datei | Für wen | Was man danach weiß | Lesezeit |
|---|---|---|---|
| [fuer-aussenstehende.md](fuer-aussenstehende.md) | Neugierige ohne Vorwissen | was StatAgent ist und wie man sich selbst durch die öffentliche Demo klickt | etwa 10 Minuten |
| [fuer-management.md](fuer-management.md) | Entscheiderinnen und Entscheider | was StatAgent nachweislich kann, was der Betrieb braucht, wo die Grenzen liegen | etwa 5 Minuten |
| [architektur.md](architektur.md) | Technikerinnen und Techniker | wie App, gemeinsamer Kern, Use Cases und Datenbank zusammenhängen | etwa 15 Minuten |
| [schnellstart.md](schnellstart.md) | Entwicklerinnen, Entwickler und Coding-Agenten | wie die App lokal läuft, wie ein UC3-Lauf aussieht und wo eine erste Änderung anfängt | etwa 12 Minuten, mit Ausprobieren länger |
| [zahlen.md](zahlen.md) | alle, die Zahlen nachprüfen wollen | woher jede Zahl kommt und wie man sie nachrechnet | zum Nachschlagen |
| [arbeitsweise-agentisch.md](arbeitsweise-agentisch.md) | alle, die selbst mit KI-Agenten arbeiten wollen | wie das Team mit KI-Agenten gearbeitet hat, die Code schreiben, und was dabei schiefging | etwa 8 Minuten |
| [use-cases-stand.md](use-cases-stand.md) | alle | was der Veranstalter verlangt hat, was in UC1 bis UC4 nachweislich läuft und was fehlt | etwa 10 Minuten |
| [aufgaben-stand.md](aufgaben-stand.md) | alle, die den offenen Rest sehen wollen | welche Aufgaben erledigt und welche offen sind, mit Nummer, Titel und Labels | zum Nachschlagen |
| [loesung-und-ansatz.md](loesung-und-ansatz.md) | alle, die die Lösung genauer verstehen wollen | was gebaut wurde, wie UC3 rechnet, wie ein Mensch freigibt, Datenfluss Voice, Qualitätssicherung | zum Nachschlagen |
| [ausfuehrung.md](ausfuehrung.md) | alle, die es starten oder den Jury-Weg nachprüfen wollen | Start, Beispiellauf mit Nachweis, Online-Demo, Abhängigkeiten mit Beleg | zum Nachschlagen |
| [konfiguration.md](konfiguration.md) | Technikerinnen und Techniker | alle Schlüssel der Einstellungen und welches Modell wofür läuft | zum Nachschlagen |
| [stand-zur-abgabe.md](stand-zur-abgabe.md) | alle | was am Tag der Abgabe läuft und was offen ist, mit Beleg | etwa 5 Minuten |
| [grenzen-herkunft-lizenzen.md](grenzen-herkunft-lizenzen.md) | alle | Grenzen, vorab Entstandenes und Lizenzen in voller Länge | zum Nachschlagen |

## Empfohlene Reihenfolge

| Wer | Reihenfolge |
|---|---|
| Außenstehende | [fuer-aussenstehende.md](fuer-aussenstehende.md), dann [use-cases-stand.md](use-cases-stand.md), dann die Demo unter https://ki-challenge.gotzendorfer.at |
| Technik | [architektur.md](architektur.md), dann [schnellstart.md](schnellstart.md), dann [arbeitsweise-agentisch.md](arbeitsweise-agentisch.md) und [../../uc3/README.md](../../uc3/README.md) |
| Management | [fuer-management.md](fuer-management.md), dann [zahlen.md](zahlen.md), dann [use-cases-stand.md](use-cases-stand.md) |

## Weitere Dokumentation im Repo

| Datei | Was drinsteht |
|---|---|
| [uc3/README.md](../../uc3/README.md) | Befehle, Regeln und Schritte eines UC3-Laufs, dazu der Vergleich mit dem Beispielbericht. |
| [docs/models.md](../models.md) | Welche Modelle wofür laufen, mit Tagesbudget, Ratenlimit und Messungen. |
| [docs/voice.md](../voice.md) | Sprachzugang über Vapi: Datenfluss, Schutz, Einrichtung. |
| [docs/design.md](../design.md) | Das Anti-Schablonen-Gate, das generische KI-Muster in der Oberfläche findet. |
| [docs/sprache.md](../sprache.md) | Ein Wort für eine Sache: die Wortliste für alle Texte. |
| [docs/entwicklung.md](../entwicklung.md) | Aufbau des Repos, Einrichten und Arbeitsteilung. |
| [docs/prd/2026-11-05-e0-plattform-e1-uc3.md](../prd/2026-11-05-e0-plattform-e1-uc3.md) | Schnittstellen der Plattform. |
| [docs/abnahme/README.md](../abnahme/README.md) | Übersicht der Abnahmen mit Prüfablauf und Matrix je Bereich. |
| [docs/praesentation/](../praesentation/) | [Demo-Drehbuch](../praesentation/demo-drehbuch.md), [Kriterien-Karte](../praesentation/kriterien-karte.md) (Stand je Bewertungsbereich) und [Belegregister](../praesentation/belegregister.md) (Herkunft jeder Zahl der Präsentation). |
| [docs/betrieb/](../betrieb/) | [Vorführung](../betrieb/vorfuehrung.md) auf eigener Instanz und [Skalierung](../betrieb/skalierung.md) der Online-Demo. |
| [docs/abgabe/herkunft.md](../abgabe/herkunft.md) | Übernommene Teile mit Herkunft, Lizenz und Rechtebeleg. |

## Woran sich diese Doku hält

- Jede Zahl trägt ihre Quelle: eine Datei im Repo oder den Befehl, mit dem sie gezählt wurde.
- Stand ist der 06.11.2026 auf `main` mit dem Commit `48761dcc`. Die Messungen stammen von früheren Ständen
  desselben Morgens; abgegeben ist der Stand von `main` beim letzten Push.
- Was noch offen ist, steht im Wurzel-README unter
  [Grenzen und offene Punkte](../../README.md#grenzen-und-offene-punkte).

## Weiter lesen

- [Wurzel-README](../../README.md): Lösung, Ausführung, Abhängigkeiten, Konfiguration und Grenzen
- [abgabe/README.md](../../abgabe/README.md): die abgegebenen Dateien
- [docs/praesentation/kriterien-karte.md](../praesentation/kriterien-karte.md): Stand je Bewertungsbereich
