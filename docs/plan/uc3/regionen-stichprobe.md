# Stichprobe Regionen: drei amtliche Übergänge (#76 AC2)

Drei Fälle unterschiedlicher Art aus der amtlichen Änderungsliste, nachgeprüft in der Datenbank und mit `uc3 klass region`. Quelle: `klassifikationen/regionen/Änderungen/aenderungenGemeinden_ab2002.ods` im Startpaket (Statistik Austria). Die Tabellenzeilen sind direkt aus der ODS-Datei gelesen, ohne den Lader.

Gemessen am 05.11.2026 auf einer Kopie der Datenbank mit geladenem Bereich 2.

| Art | Blatt und Zeile | In Kraft | Code vorher | Code nachher | Beziehung in `stat.uebergang` | Abweichung |
|---|---|---|---|---|---|---|
| Zusammenlegung | `Zusammenlegungen`, Zeilen 3 und 4 | 01.01.2025 | 62252 Söchau, 62267 Fürstenfeld | 62280 Fürstenfeld | n:1 | keine |
| Bezirkswechsel | `Bezirkszusammenlegungen`, Zeile 3 | 01.01.2017 | 32424 Zwölfaxing, Bezirk 324 Wien-Umgebung | 30741 Zwölfaxing, Bezirk 307 Bruck an der Leitha | Gemeinde 1:1, Bezirk m:n | keine |
| Umbenennung | `Namensaenderungen`, Zeile 3 | 28.11.2024 | 41713 Lenzing | 41713 Lenzing an der Ager | 1:1 | keine |

## Zusammenlegung: Söchau und Fürstenfeld werden Fürstenfeld

Zeilen in der Liste: `62280, Fürstenfeld, 62252, Söchau, Hartberg-Fürstenfeld, 01.01.2025, LGBl. STM. Nr. 106/2024` und `62280, Fürstenfeld, 62267, Fürstenfeld, Hartberg-Fürstenfeld, 01.01.2025, LGBl. STM. Nr. 106/2024`.

Die alten Codes stehen im Stand 01.01.2024 und nicht mehr im Stand 01.01.2025. Der neue Code steht im Stand 01.01.2025.

`uv run uc3 klass region 62280`:

```text
- gültig ab 01.01.2025: Fürstenfeld (62280), Bezirk Hartberg-Fürstenfeld (622), Bundesland Steiermark (6), Staat Österreich (AT)
- Stand 01.01.2024 (62252), (62267) werden ab 01.01.2025 zu Stand 01.01.2025 Fürstenfeld (62280), Beziehung n:1. Quelle: alle_GKZaenderungen (Zusammenlegung); Zusammenlegungen (LGBl. STM. Nr. 106/2024).
```

## Bezirkswechsel: Zwölfaxing kommt von Wien-Umgebung zu Bruck an der Leitha

Zeile in der Liste: `30741, Zwölfaxing, Bruck an der Leitha, 32424, Wien-Umgebung, 01.01.2017`.

Die Gemeinde wird nicht gelöscht: Sie behält den Namen und bekommt einen neuen Code, Beziehung 1:1. Der Bezirk 324 endet am 31.12.2016 und führt zu vier Bezirken, deshalb m:n.

`uv run uc3 klass region 30741` und `uv run uc3 klass region 324`:

```text
- Stand 01.01.2016 Zwölfaxing (32424) wird ab 01.01.2017 zu Stand 01.01.2017 Zwölfaxing (30741), Beziehung 1:1. Quelle: alle_GKZaenderungen (Bezirkszusammenlegung); Bezirkszusammenlegungen (Wien-Umgebung zu Bruck an der Leitha).
- Stand 01.01.2016 Wien-Umgebung (324) wird ab 01.01.2017 zu Stand 01.01.2017 Bruck an der Leitha (307), Beziehung m:n. Quelle: Bezirkszusammenlegungen (Wien-Umgebung zu Bruck an der Leitha).
```

Dazu Korneuburg (312), St. Pölten(Land) (319) und Tulln (321) mit derselben Beziehung.

## Umbenennung: Lenzing heißt Lenzing an der Ager

Zeile in der Liste: `41713, Lenzing, Lenzing an der Ager, Vöcklabruck, 28.11.2024, LGBL. OÖ. Nr. 106/2024`.

Die Gemeinde wird nicht gelöscht: Der Code bleibt und steht in beiden Ständen, nur der Name ändert sich. Die Umbenennung gilt ab 28.11.2024, der Name erscheint im nächsten Stand 01.01.2025.

`uv run uc3 klass region 41713`:

```text
- gültig 01.01.2011 bis 31.12.2024: Lenzing (41713), Bezirk Vöcklabruck (417), Bundesland Oberösterreich (4), Staat Österreich (AT)
- gültig ab 01.01.2025: Lenzing an der Ager (41713), Bezirk Vöcklabruck (417), Bundesland Oberösterreich (4), Staat Österreich (AT)
- Stand 01.01.2024 Lenzing (41713) wird ab 28.11.2024 zu Stand 01.01.2025 Lenzing an der Ager (41713), Beziehung 1:1. Quelle: Namensaenderungen (Lenzing heißt Lenzing an der Ager, LGBL. OÖ. Nr. 106/2024).
```

## Beleg

```sql
SELECT klassifikation, version_alt, code_alt, version_neu, code_neu, beziehung, gueltig_ab, quelle
FROM stat.uebergang
WHERE (klassifikation, code_alt, code_neu) IN (
  ('gemeinde', '62252', '62280'), ('gemeinde', '62267', '62280'), ('gemeinde', '32424', '30741'),
  ('bezirk', '324', '307'), ('gemeinde', '41713', '41713'));
```

Die Statistik zählt nach Bundesland, nicht nach Gemeinde oder Bezirk. Diese Übergänge ändern deshalb keine Zahl der Abgabe.
