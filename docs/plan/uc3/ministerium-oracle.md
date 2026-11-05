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
| ohne Altcodes, Teil-Lieferung 2025-10 übersprungen | `altcodes_als_abschnitt: []`, `angehaltene_lieferungen: ueberspringen` | **32.713** | finaler Code, gemessen 05.11.2026 15:0x |
| DA bis DN als C, Teil-Lieferung 2025-10 übersprungen (Abgabezahl) | `altcodes_als_abschnitt: ["DA", …, "DN"]`, `angehaltene_lieferungen: ueberspringen` | **32.741** | finaler Code, gemessen 05.11.2026 15:0x |
| ohne Altcodes, August 2025 aus der Teil-Lieferung 2025-10 | – | 32.639 | Forensik, Lead note 269248 |
| DA bis DN als C, August 2025 aus der Teil-Lieferung 2025-10 | – | 32.667 | früherer Prototyp |
| DA bis DM als C, August 2025 aus Lieferung 2025-11 | Datenstand weicht vom Fenster ab (kein Parameterwert) | 32.706 | Orakel-Angabe |

Gemessen mit dem Code dieses Branches auf der Datenbank `statistik` (24 Läufe v1, nicht freigegeben), ohne
Eintrag in der Datenbank: die Definition lag nur im Speicher, freigegeben ist nichts. Datenstand je Monat: 2025-08
aus Lieferung 2025-09, weil die jüngere Lieferung 2025-10 angehalten ist (Teil-Lieferung, Rückfrage zur
Teil-Lieferung, P15/P16); 2025-09 aus 2025-11, 2025-10 aus 2025-12 und so weiter bis 2026-05 bis 2026-07 aus
2026-07. Die 74 Personen Unterschied zu 32.639/32.667 kommen genau aus dieser Wahl: Die Teil-Lieferung 2025-10
fehlen rund 20 % der Verhältnisse, mit ihr verlieren diese Personen Tage im August und fallen unter 200 Tage.

Die fünfte Zeile entsteht nicht durch einen Parameterwert. Eine Lieferung 2025-11 enthält nach § 2 die Monate
September bis November 2025, also keinen August. Wer August 2025 aus ihr nimmt, verlässt die Regel „jüngste
Lieferung, die den Tag enthält“. Die Zahl steht hier nur, damit sich die Abweichung zum Orakel erklären lässt.

**Entscheid (Lead 58, autonom, 05.11.2026, Kommentare in #72):** Abgabezahl ist **32.741**: Variante S mit den
ÖNACE-2003-Altcodes DA bis DN in Abschnitt C, also dieselbe Zuordnung wie Regel Q01 im Sheet (Persona-Panel F5).
32.713 (Variante S ohne Altcodes) steht nur noch als Variante im Beleg. Sie passt zum Entscheid E07, die Teil-Lieferung 2025-10 als Lieferausfall zu behandeln. Die
wörtliche Lesart H („jüngste Lieferung, die den Tag enthält“, August 2025 aus der Teil-Lieferung 2025-10) ergibt
32.639 bzw. 32.667 und ist das bisherige Soll des Leads (note 269248). Drei unabhängige Rechnungen und die
Forensik stimmen dort überein. Die Wahl S statt H ist eine Annahme und steht als Rückfrage R3 (Lead: F1) an die
Fachabteilung. Das unabhängige Orakel von 4f bestätigt S: 0 Abweichungen bei Personen und Tagen, Kopf bytegleich
zur Vorlage. Eine Schwelle „mehr als 200 Tage“ statt „mindestens 200“ ergäbe 14 Personen weniger.

**GEBURTSJAHR:** Ein Geburtsdatum mit Monat 13 ist kein gültiges Datum und gilt nach Auftrag 3 als unplausibel:
die Lieferung trägt dort `Unbekannt` (39 Personen in 2026-07). Der Ersatztag 1. Juli (R5_alter) gilt nur für das
Alter in der Statistik, nicht für das Feld der Lieferung.

**Offen:** Die amtliche Lieferung entsteht erst mit `uv run uc3 ministerium --name …`, nachdem der Owner die
Definition (Regelsatz `ministerium`) mit seinem Namen freigegeben hat. Die Definition setzt
`altcodes_als_abschnitt` auf DA bis DN und `angehaltene_lieferungen` auf `ueberspringen`; damit ergibt sie die
Abgabezahl 32.741 (Annahme A13). Die CSV liegt außerhalb des Repos (`lieferungen/` neben dem Repo), im Repo steht
nur `abgabe/ministerium_2026-07.beleg.md`.

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
