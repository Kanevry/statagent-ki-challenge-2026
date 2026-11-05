# Stelle und Termin: Prüfbericht (Issue #81)

Stand: 2026-11-05T14:01:37Z, Branch `feat/uc1-korpus`, DB `lotse` (lokal, Port 5433), Suchweg `volltext`.
Fall: `uc1/eval/termin-wien.json` (erfunden: Mutter 82, Pension von der PVA, 1100 Wien, braucht Unterstützung
zu Hause; der Angehörige möchte eine Beratung und einen Termin, Wunsch vormittags am 2026-11-17).

Nichts wird gebucht. Es gibt keinen Zugriff auf Buchungs- oder Kalenderdienste und kein Sprachmodell im Ablauf.

## Befehle

Aus `uc1/`:

```bash
uv run python -m uc1.termin --fall termin-wien          # Stellen finden, erzeugt/termin-wien.ics schreiben
uv run python -m uc1.termin --fall termin-wien --json   # dasselbe als JSON
uv run python -m uc1.termin --aufzeichnen termin-wien    # eval/termin-dialoge.json neu schreiben
uv run python -m uc1.termin --pruefen termin-wien       # AC prüfen, Exit 0 nur wenn alle bestehen
UC1_DATA_DIR=…/svbox/uc1 uv run pytest -q -m daten tests/test_termin.py
```

## Wie die Adresse belegt wird

1. Je Stelle aus `uc1/stellen/wien.yaml` läuft eine Volltextsuche über Kataloge und Formulare
   (`SuchFilter(quellen=("katalog", "formular"))`, `weg="volltext"`, k = 5).
2. Im Seitentext des Treffers steht ein wörtlicher Namensanker. Gesucht wird die erste Adresse höchstens
   80 Zeichen dahinter, mit den Mustern aus `uc1/stellen/adressmuster.yaml` (Straße, Hausnummer, PLZ, Ort, in
   beiden Reihenfolgen). Der Ort muss passen. Das schützt auf zweispaltigen Seiten vor der Nachbarspalte.
3. Ausgegeben wird die Adresse nur, wenn sie nach `normiere` (NFKC, Bindestriche und Anführungszeichen
   vereinheitlicht, Leerraum zusammengezogen) Teilstring der Quelle ist. Sonst steht dort „nicht belegt“.
   `--pruefen` liest den Abschnittstext dafür neu aus `lotse.abschnitt`.
4. Die zuständige Stelle kommt aus dem Kern (`kern.zustaendige_stelle`, `daten/traeger.yaml`, BPGG § 22).
   Hat der zuständige Träger keine belegte Adresse, wird er mit „nicht belegt“ angezeigt.

## Gefundene Stellen

| Stelle | Adresse (normiert) | Quelle | Seite | Abschnitt | zuständig |
|---|---|---|---|---|---|
| Fonds Soziales Wien, Beratungszentrum Pflege und Betreuung | Guglgasse 7-9, 1030 Wien | `Anträge und Formulare/Bedarfsmeldung-Senior_innen-Wohngemeinschaft_Basispaket.1736522017.pdf` | 1 | 72822 | – |
| Pensionsversicherungsanstalt, Landesstelle Wien | Friedrich-Hillegeist-Straße 1, 1020 Wien | `Anträge und Formulare/PAL080_0125_Mpfl_052026.pdf` | 8 | 72833 | BPGG § 22 Abs. 1 Z 1 |
| Pensionsversicherungsanstalt, Hauptstelle | Friedrich-Hillegeist-Straße 1, 1020 Wien | `Anträge und Formulare/PAL080_0125_Mpfl_052026.pdf` | 1 | 72826 | BPGG § 22 Abs. 1 Z 1 |

Ausgegebene Adressen: 3, davon belegt 3. **Unbelegte Adressen: 0.** In der Quelle steht „Guglgasse 7–9“ mit
Halbgeviertstrich; normiert ist das „7-9“.

## Prüfung (`--pruefen termin-wien`, Exit 0)

```
OK   mindestens 1 Stelle mit Name, Adresse, Quelle, Seite (3)
OK   jede ausgegebene Adresse ist Teilstring der Quelle (3/3)
OK   0 unbelegte Adressen (0)
OK   genau 1 VEVENT (1)
OK   STATUS:TENTATIVE (TENTATIVE)
OK   SUMMARY Terminentwurf (Terminentwurf)
OK   DESCRIPTION enthält „nicht gebucht“
OK   LOCATION ist belegte Adresse (Guglgasse 7-9, 1030 Wien)
OK   Wunschdatum aus dem Fixture (20261117T080000)
OK   Checkliste: Unterlagen, Nähe, Zeitpräferenz
OK   kein freier Termin behauptet (ICS)
OK   Zeilen RFC 5545 (≤ 75 Oktette, CRLF)
OK   deterministisch (zwei Läufe byte-gleich)
OK   Dialog zeit-fehlt: 1 Rückfrage(n) zur Zeit (1)
OK   Dialog zeit-bekannt: 0 Rückfrage(n) zur Zeit (0)
ERGEBNIS: bestanden
```

## ICS-Auszug (`uc1/erzeugt/termin-wien.ics`)

Die Datei ist mit der Standardbibliothek gebaut (RFC 5545: CRLF, Faltung auf 75 Oktette, TEXT maskiert,
VTIMEZONE Europe/Vienna). DTSTAMP und Wunschdatum stammen aus dem Fixture. Der Parser-Bericht zählt
1 VEVENT. SHA-256 dieses Laufs: `ee4709ceab012e95988df51da70b9865db0ba4d2506bbb8a1127e386461aaa22`.

```
BEGIN:VEVENT
UID:termin-wien-3f0532636d892f99@lotse.invalid
DTSTAMP:20261105T090000Z
DTSTART;TZID=Europe/Vienna:20261117T080000
DTEND;TZID=Europe/Vienna:20261117T120000
SUMMARY:Terminentwurf
STATUS:TENTATIVE
TRANSP:TRANSPARENT
CLASS:PRIVATE
LOCATION:Guglgasse 7-9\, 1030 Wien
DESCRIPTION:Terminentwurf\, nicht gebucht. Kein freier Termin bestätigt: D
 en Termin vereinbaren Sie selbst mit der Stelle.\nDatum und Zeitfenster si
 …
END:VEVENT
```

Entfaltet enthält DESCRIPTION:

- Unterlagen: „vorhandene Befunde von Ärztin, Arzt oder Krankenhaus in Kopie“ (PAL080 S. 2) und den Antrag auf
  Pflegegeld (PAL080), beide aus `daten/leistungen.yaml` mit Quelle
- Nähe: Wohnort 1100 Wien, Stelle 1030 Wien (Guglgasse 7-9, 1030 Wien)
- Zeitpräferenz: vormittags (08:00 bis 12:00)
- Quelle: Bedarfsmeldung-Senior_innen-Wohngemeinschaft_Basispaket…pdf, S. 1 (Abschnitt 72822)

## Dialogfälle (`uc1/eval/termin-dialoge.json`)

Die Dialoge laufen ohne Modell. Je Runde werden Angaben regelbasiert erkannt (`stellen/termin.yaml`), dann
kommt höchstens eine Frage aus `naechste_rueckfrage`.

| Fall | Eingaben | Rückfragen gesamt | davon Zeitpräferenz | Ergebnis | Beleg-IDs |
|---|---|---|---|---|---|
| `zeit-fehlt` | Lage ohne Zeitwunsch, dann „Vormittags.“ | 1 | 1 („Welche Zeiten passen Ihnen – vormittags oder nachmittags?“) | Entwurf FSW Beratungszentrum, TENTATIVE, `gebucht: false` | 72822, 72833, 72826 |
| `zeit-bekannt` | Lage mit „am liebsten vormittags“ | 0 | 0 | wie oben | 72822, 72833, 72826 |

In beiden Fällen wird kein freier Termin behauptet (`freier_termin_behauptet: false`, Muster in
`stellen/termin.yaml` `verboten`).

## Grenzen

- **Nur Wien, nur drei Stellen.** `stellen/wien.yaml` nennt Anker für FSW und PVA. Für andere Bundesländer
  erscheint nur der zuständige Träger, mit „nicht belegt“ statt einer Adresse.
- **Zweispaltige Seiten.** Auf PAL080 S. 8 stehen Wien und Kärnten nebeneinander. Die Zuordnung hängt an
  „erste Adresse hinter dem Anker mit passendem Ort“. Die Seiten 48 und 49 des Serviceratgebers (ÖGK-Kundenservice
  je Bezirk, darunter Favoriten) sind so verschränkt, dass Name und Adresse nicht sicher zusammengehören. Sie
  sind deshalb bewusst nicht aufgenommen, auch wenn ihre Adressen dort belegt wären.
- **Kein Termin, keine Verfügbarkeit.** DTSTART und DTEND bilden das Wunschfenster ab und keinen freien Slot.
  Die PVA-Quelle nennt „persönlich nach telefonischer Terminvereinbarung“. Vereinbaren muss die Person selbst.
- **Telefonnummern** werden nicht ausgegeben, weil ihre Spaltenzuordnung nicht geprüft ist.
- **Unterlagen hängen an `daten/leistungen.yaml`.** Ändert #32 dort die Liste, ändern sich DESCRIPTION und der
  Hash der ICS-Datei. Datum, Stelle und Status bleiben gleich.
- **Postleitzahl-Erkennung** gilt nur für Wien (`1xx0 Wien`).
