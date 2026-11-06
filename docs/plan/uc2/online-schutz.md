# UC2: Online-Schutz vor POST und echten Modellen

Stand 05.11.2026, Issue #137 (Bedingung der Review zu !47). Gilt, bevor `POST /faelle` oder echte
Modelle online gehen.

## Was geschützt ist

1. **Namen in Modelltexten.** Diese Felder gehen vor dem Schreiben in PG durch
   `uc2.belege.namen.maskiere_modelltext` (Modul `uc2.verhandlung.schutz`):
   - Zug: `begruendung`, `bedingungen`, `zugestaendnis` (auch in `uc2.position`) und `zahlen[].einheit`
     (danach auf 60 Zeichen gekürzt).
   - Moderator-Notiz: `notiz` und alle Textfelder von `widersprueche[]` und `belege_eingefordert[]`, auch
     `akteur` und `thema` (das Schema begrenzt sie dort nicht auf IDs).
   - Auftrag: `ziel`, `regeln`, Titel und Beschreibung der Themen (auch `uc2.fall.auftrag`).
   - Auswahl: `begruendung` (auch `uc2.teilnahme`).
   - Frage: `uc2.fall.frage` und Ereignis `start`. Dazu die Fehlermeldungen von `ungueltige_ausgabe`.

   Maskiert wird beim Schreiben, nicht in der Ausgabeschicht. Deshalb gilt der Schutz für SSE, Bericht,
   Terminal und Replay gleich. PG enthält keine Namen aus Modelltext, und die nächste Runde sieht im Prompt
   nur maskierte Texte.
2. **Zitat-Sperre.** Findet die Prüfung `zitat` eine wörtliche Übernahme ab 8 Wörtern aus einem Beleg, wird
   die Stelle in Begründung, Bedingungen und Zugeständnis vor dem Speichern zu „[Zitat]“. Das Ereignis `zitat`
   bleibt als Hinweis und nennt nur Thema, Beleg-ID und Wortzahl, nicht die Wörter.
3. **Freitext-Frage** (`uc2.verhandlung.cli.pruefe_frage`, API `POST /faelle`). Abgelehnt wird eine Frage
   mit einer der folgenden Angaben, mit 422 und einem festen Satz ohne die Eingabe:
   - eine Ziffernfolge ab 8 Stellen,
   - eine Sozialversicherungsnummer (4 Ziffern und Geburtsdatum als TTMMJJ oder TT.MM.JJ, auch mit Trenner),
   - eine Ziffer direkt nach `PERSON_ID`, `VVH_ID` oder `SV-Nummer`, auch in Anführungszeichen,
   - ein Datum (TT.MM.JJJJ, TT.MM.JJ oder JJJJ-MM-TT) zusammen mit „geb.“, „geboren“ oder „Geburtsdatum“,
   - eine E-Mail-Adresse.

   Namen werden maskiert. Gespeichert und an das Modell gegeben wird nur die maskierte Frage.

## Regel für Modelltext

Die Namensliste enthält Allgemeinwörter, etwa ein nominalisiertes Adjektiv, das als Nachname gesammelt
wurde. Deshalb zählt im Modelltext nur ein Name mit Beleg:

- Muster: Funktion, akademischer Titel, Vorname, Zuschreibung („sagt …“) und E-Mail-Adressen. Die
  Pressetext-Muster (Byline, Bildnachweis, Kürzel, Alter, Literatur) laufen hier nicht.
- Mehrteilige Einträge der Namensliste werden immer maskiert. Ein so erkannter Nachname gilt danach im
  ganzen Text.
- Ein Einzelwort der Liste wird maskiert, wenn alle diese Bedingungen gelten:
  - Es ist großgeschrieben.
  - Es steht nicht im Fachwortschatz der eigenen Akteurs-, Fall-, Paket- und Config-Dateien.
  - Es hat keine Substantiv- oder Adjektivendung, etwa auf „-ung“, „-ene“ oder „-rte“, und ist kein Stoppwort.
- Die Stellung im Satz zählt nicht: Satzanfang, nach „aber“ oder „für“, nach einem Artikel („die X“, auch im
  Relativsatz „…, die X vorschlägt“) und vor einem Bindestrich („X-Pläne“) wird gleich maskiert.
- Ein so erkannter Name gilt danach im ganzen Text.
- Die Zahlbefunde (`zahl_ohne_beleg`, `zahl_widerspruch`) tragen die maskierte Einheit.

Messung (Review zu !97, 05.11.): Die Maske ändert keinen von 2.000 Modelltexten des Qualitätslaufs 4
(claude) und keinen von 234 Modelltexten der Vorführ-Aufzeichnung, mit der Index-Liste und mit der
Server-Liste. Namensscan (`uc2/tests/pruefe_namen.py --lauf`) über alle Ereignisse des Laufs: 0 Treffer mit
der Server-Liste. Die Index-Liste trifft nur „Austria“ in Institutionsnamen.

## Was nicht geschützt ist

- Ein Name, der zugleich ein gängiges Hauptwort ist (im Fachwortschatz, mit Substantivendung wie „-ung“
  oder als Stoppwort), bleibt als Einzelwort stehen, wenn ihn kein Muster (Funktion, Titel, Vorname,
  Zuschreibung) und kein voller Name im selben Text belegt.
- Kleingeschriebene Namen und Namen in IDs (Thema, Akteur, Beleg) prüft der Schutz nicht. IDs sind durch
  Schema und Code-Prüfung auf feste Werte begrenzt.
- **Fälle, die vor diesem Stand angelegt wurden, sind nicht maskiert.** Die Ausgabeschicht maskiert nicht
  nach. Vor dem Online-Gang die Online-DB leeren oder nur neue Läufe zeigen.
- Die Wiederholung nach einer ungültigen Ausgabe zeigt dem Modell seinen eigenen, noch nicht maskierten
  Text. Er geht nur an das Modell, nicht in PG oder nach außen.
- Die Frage-Prüfung erkennt kurze Kennungen nur mit Schlüsselwort davor. „Wartet Person 4711?“ geht durch.

## Nötige Umgebung

| Variable | Wert | Wirkung |
|---|---|---|
| `UC2_NAMENSLISTE` | Pfad außerhalb jedes Git-Checkouts | Pflicht für echte Provider. Fehlt sie, bricht der Lauf vor der Anlage ab (`SchutzFehler`, fail-closed). |
| `UC2_NAMEN_OHNE_LISTE` | `1` nur in Tests | Nur Muster statt Abbruch, nur bei `mock`. Echte Provider brechen trotzdem ab, auch mit einer übergebenen leeren Liste. |

Liste erzeugen: `uv run uc2 namen sammeln --aus-index --autoren <datei> --ausgabe <pfad außerhalb des Repos>`.
