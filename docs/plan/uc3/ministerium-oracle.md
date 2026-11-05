# Ministeriums-Lieferung (Auftrag 3): Definition, Datenstand und bekannte Zahlen

Stand 05.11.2026. Bezug: Issue #71, Review !13 Punkte 3 und 9. Code: `uc3/statagent/sonderauswertung.py`.
Die Definition ist eine Regel in `meta.regel` (Regelsatz `ministerium`, Zählregel `A3_ministerium_personentage`,
art `personentage`). Ein eigener Agent schlägt sie vor, ein Mensch gibt sie mit Namen frei. Das Programm rechnet
ohne Sprachmodell.

## Definition in Alltagssprache

- **Wer:** Personen mit Arbeiter-Verhältnissen (Qualifikationen laut Parameter `qualifikationen`, DV und FD
  zusammen) in einem ÖNACE-Abschnitt (Parameter `oenace`, hier C „Herstellung von Waren“).
- **Zeitraum:** die letzten `monate` Kalendermonate bis einschließlich Berichtsmonat.
- **Tage:** Kalendertage, an denen die Person mindestens ein passendes Verhältnis hat. Laufen zwei Verhältnisse
  derselben Person gleichzeitig, zählt der Tag einmal (Vereinigung der Zeiträume, nicht ihre Summe).
- **Schwelle:** geliefert werden Personen mit mindestens `mindesttage` Tagen (Vergleich „mindestens“, also
  200 Tage zählen, 199 nicht).
- **Altcodes:** Die Bereinigung ordnet ÖNACE-2003-Unterabschnitte (DA bis DN) über die Quellzuordnung des
  Bereinigungs-Regelsatzes einem Abschnitt der ÖNACE 2008 zu, die meisten C. Ob solche Verhältnisse in der
  Lieferung mitzählen, legt der Parameter `altcodes_als_abschnitt` fest: eine Liste gelieferter Codes, die als
  Abschnitt `oenace` gelten. Die leere Liste `[]` zählt nur Verhältnisse, die direkt mit dem Abschnitt geliefert
  wurden. Der Parameter ist Pflicht (kein stiller Standardwert, wie jeder Regelparameter); der Code trägt keine
  Codeliste.

## Datenstand: je Tag die jüngste Lieferung, die ihn enthält

Auftrag 3 verlangt für jeden Tag die jüngste Lieferung, die diesen Tag enthält. Jede Lieferung ist ein
Vollabzug über ihren Berichtsmonat und die zwei Vormonate (Fachbeschreibung § 2). Ein Tag im Monat m steht
damit genau in den Lieferungen m, m+1 und m+2. Alle Tage eines Monats liegen in denselben drei Lieferungen und
haben deshalb dieselbe jüngste Lieferung. Der Code wählt die Lieferung darum je Monat aus dem Fenster
„Monat bis Monat+2“. Das ist dieselbe Regel, nur je Monat statt je Tag ausgewertet. Berücksichtigt werden nur
Lieferungen, die mit dem Bereinigungs-Regelsatz gerechnet sind. Gibt es zum Zeitpunkt der Auswertung eine
spätere Lieferung noch nicht, gilt die jüngste vorhandene.

**Angehaltene Lieferungen** (Parameter `angehaltene_lieferungen`): Hat eine Prüfregel den Lauf einer Lieferung
angehalten (etwa weil sie unvollständig ist), ist sie keine verlässliche Fassung ihrer drei Monate. Mit
`ueberspringen` nimmt die Auswertung für diese Monate die nächstjüngere Lieferung im Fenster und hält das im
Datenstand fest (`uebersprungen`). Sind alle Lieferungen im Fenster angehalten, nimmt sie trotzdem die jüngste
und vermerkt „mangels Alternative verwendet“, damit die Lieferung nicht still ausfällt. Mit `verwenden` gilt die
jüngste Lieferung ohne diese Prüfung. Datenstand und übersprungene Lieferungen stehen in `meta.ausgabe.datenstand`.

## Varianten und bekannte Zahlen

Berichtsmonat 2026-07, zwölf Monate, Abschnitt C, Schwelle 200 Tage.

| Variante | Parameter | Personen | Quelle |
|---|---|---|---|
| ohne Altcodes | `altcodes_als_abschnitt: []` | 32.639 | Forensik, Lead note 269248 |
| DA bis DM als C | `altcodes_als_abschnitt: ["DA", "DB", "DC", "DD", "DE", "DF", "DG", "DH", "DI", "DJ", "DK", "DL", "DM"]` | 32.667 | Prototyp-Lauf auf m5 |
| wie oben, August 2025 aus Lieferung 2025-11 | Datenstand weicht vom Fenster ab (kein Parameterwert) | 32.706 | Orakel-Angabe |

Die dritte Zeile entsteht nicht durch einen Parameterwert. Eine Lieferung 2025-11 enthält nach § 2 die Monate
September bis November 2025, also keinen August. Wer August 2025 aus ihr nimmt, verlässt die Regel „jüngste
Lieferung, die den Tag enthält“. Die Zahl steht hier nur, damit sich die Abweichung zum Orakel erklären lässt.

**Vorbehalt:** Die Zahlen stammen aus einem Prototyp-Lauf beziehungsweise aus der Forensik und nicht aus dem
finalen Code. Der Koordinator bestätigt sie mit `uv run uc3 ministerium` nach der Freigabe der Definition und
trägt das Ergebnis hier nach. Bis dahin sind sie Erwartungswerte.

## Freigabe der Lieferung (Regel 7)

`uv run uc3 ministerium --name "<Vor- und Nachname>" [--monat JJJJ-MM]` rechnet, schreibt die CSV unter `abgabe/` und
gibt sie über Vertrag P frei: ein Eintrag in `meta.protokoll` (`vorschlag_typ lieferung`), die Freigabe in
`meta.freigabe` (`objekt_typ datei`, `objekt_ref` = Pfad der CSV) und ein Commit genau dieser Datei mit dem Trailer
`Freigegeben-von`. Erst danach entsteht die Zeile in `meta.ausgabe` mit `protokoll_id`. Scheitert Git, wird der
Eintrag mit dem technischen Grund abgelehnt, die CSV wieder entfernt und es entsteht keine Ausgabe. Jeder
Berichtsmonat wird nur einmal freigegeben. Eine zweite Freigabe wird abgewiesen; weicht der neue Inhalt ab, braucht
die neue Fassung einen neuen Auftrag. `uv run uc3 protokoll` zeigt die Lieferung in Abschnitt 5.

## Prüfung durch Tests

`uc3/tests/test_sonderauswertung.py` enthält erfundene Grenzfälle: eine Person knapp unter der Schwelle, eine
genau auf der Schwelle (im Test `mindesttage = 30` auf einen Monat, entspricht 199/200 auf zwölf Monate), zwei
überlappende Verhältnisse derselben Person (Tage einmal gezählt) und ein Verhältnis mit Altcode DA, das nur mit
passendem Parameter mitzählt.
