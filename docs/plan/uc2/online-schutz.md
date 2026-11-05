# UC2: Online-Schutz vor POST und echten Modellen

Stand 05.11.2026, Issue #137 (Bedingung der Review-Bank 57 zu !47). Gilt, bevor `POST /faelle` oder echte
Modelle online gehen.

## Was geschützt ist

1. **Namen in Modelltexten.** Diese Felder gehen vor dem Schreiben in PG durch
   `uc2.belege.namen.maskiere_modelltext` (Modul `uc2.verhandlung.schutz`):
   - Zug: `begruendung`, `bedingungen`, `zugestaendnis` (auch in `uc2.position`).
   - Moderator-Notiz: `notiz`, `widersprueche[].beschreibung`, `belege_eingefordert[].grund`.
   - Auftrag: `ziel`, `regeln`, Titel und Beschreibung der Themen (auch `uc2.fall.auftrag`).
   - Auswahl: `begruendung` (auch `uc2.teilnahme`).
   - Frage: `uc2.fall.frage` und Ereignis `start`. Dazu die Fehlermeldungen von `ungueltige_ausgabe`.

   Maskiert wird beim Schreiben, nicht in der Ausgabeschicht. Deshalb gilt der Schutz für SSE, Bericht,
   Terminal und Replay gleich. PG enthält keine Namen aus Modelltext, und die nächste Runde sieht im Prompt
   nur maskierte Texte.
2. **Zitat-Sperre.** Findet die Prüfung `zitat` eine wörtliche Übernahme ab 8 Wörtern aus einem Beleg, wird
   die Stelle in Begründung, Bedingungen und Zugeständnis vor dem Speichern zu „[Zitat]“. Das Ereignis `zitat`
   bleibt als Hinweis.
3. **Freitext-Frage** (`uc2.verhandlung.cli.pruefe_frage`, API `POST /faelle`). Abgelehnt wird eine Frage
   mit einer der folgenden Angaben, mit 422 und einem festen Satz ohne die Eingabe:
   - eine Ziffernfolge ab 8 Stellen,
   - eine Sozialversicherungsnummer (4 Ziffern und 6 Ziffern Geburtsdatum, auch mit Trenner),
   - eine Ziffer direkt nach `PERSON_ID`, `VVH_ID` oder `SV-Nummer`,
   - ein Datum TT.MM.JJJJ zusammen mit „geboren“ oder „Geburtsdatum“,
   - eine E-Mail-Adresse.

   Namen werden maskiert. Gespeichert und an das Modell gegeben wird nur die maskierte Frage.

## Regel für Modelltext

Die Namensliste enthält Allgemeinwörter, etwa ein nominalisiertes Adjektiv, das als Nachname gesammelt
wurde. Deshalb zählt im Modelltext nur ein Name mit Beleg:

- Muster: Funktion, akademischer Titel, Vorname, Zuschreibung („sagt …“) und E-Mail-Adressen. Die
  Pressetext-Muster (Byline, Bildnachweis, Kürzel, Alter, Literatur) laufen hier nicht.
- Mehrteilige Einträge der Namensliste werden immer maskiert. Ein so erkannter Nachname gilt danach im
  ganzen Text.
- Ein Einzelwort der Liste wird nur maskiert, wenn alle diese Bedingungen gelten:
  - Es steht großgeschrieben mitten im Satz.
  - Es steht nicht im Fachwortschatz der eigenen Akteurs-, Fall-, Paket- und Config-Dateien.
  - Es hat keine Substantiv- oder Adjektivendung, etwa auf „-ung“, „-ene“ oder „-rte“.
  - Es steht im selben Text nie nach einem Artikel oder einem flektierten Adjektiv.

Gemessen an einem mock-Lauf (183 Modelltexte, Testliste mit Allgemeinwörtern) bleibt kein Satz verändert.

## Was nicht geschützt ist

- Ein Einzelname aus der Liste am Satzanfang oder nach einem Artikel bleibt stehen, wenn ihn kein Muster und
  kein voller Name im selben Text belegt.
- Kleingeschriebene Namen und Namen in IDs (Thema, Akteur, Beleg) prüft der Schutz nicht. IDs sind durch
  Schema und Code-Prüfung auf feste Werte begrenzt.
- **Fälle, die vor diesem Stand angelegt wurden, sind nicht maskiert.** Die Ausgabeschicht maskiert nicht
  nach. Vor dem Online-Gang die Online-DB leeren oder nur neue Läufe zeigen.
- Das Ereignis `zitat` nennt die 8 gefundenen Wörter (`woerter`). Sie stammen aus dem maskierten Beleg und
  sind kürzer als das öffentliche Zitatfeld des Belegs (≤ 300 Zeichen).
- Die Frage-Prüfung erkennt kurze Kennungen nur mit Schlüsselwort davor. „Wartet Person 4711?“ geht durch.

## Nötige Umgebung

| Variable | Wert | Wirkung |
|---|---|---|
| `UC2_NAMENSLISTE` | Pfad außerhalb jedes Git-Checkouts | Pflicht für echte Provider. Fehlt sie, bricht der Lauf vor der Anlage ab (`SchutzFehler`, fail-closed). |
| `UC2_NAMEN_OHNE_LISTE` | `1` nur in Tests | Nur Muster statt Abbruch. Bei `mock` gilt das ohnehin. |

Liste erzeugen: `uv run uc2 namen sammeln --aus-index --autoren <datei> --ausgabe <pfad außerhalb des Repos>`.
