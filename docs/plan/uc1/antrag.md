# Antrag als Entwurf (#32)

Der Lotse füllt aus einem Gespräch zwei Anträge als Entwurf vor: Pflegegeld (PAL080 der PVA) und Kur/Reha. Dazu
liefert er, was noch offen ist, welche Unterlagen beiliegen müssen, welche Stelle zuständig ist und warum er
dieses Formular gewählt hat. Jede Angabe trägt eine Quelle. **Eingereicht wird nichts.** Gesundheitsangaben und
die ärztlichen Teile füllt der Lotse nicht aus.

Code: `uc1/uc1/antrag.py`. Daten: `uc1/formulare/pal080.felder.json`, `uc1/formulare/kur-reha.felder.json` und
`uc1/daten/antragsangaben.yaml`. Den Kern erweitert der Abschnitt „Antragsangaben“ in `kern.md`.

```
lotse antrag pflegegeld|reha --sitzung ID [--ausgabe DIR] [--json]
```

Der Entwurf landet in `uc1/laufzeit/antraege/<art>-<sitzung>-entwurf.pdf` (gitignored) oder in `--ausgabe`.
Ins Repo kommen keine PDFs: Die Formulare liegen in `UC1_DATA_DIR`, nicht im Repo.

## Ablauf von `erzeuge_antrag(art, sitzung_id, *, ausgabe_dir, conn=None)`

1. **Sitzung laden** (`lotse.sitzung.zustand`). Der Zustand liefert `antrag` (Angaben aus dem Gespräch) und
   `angaben.status`. Aus dem Status folgen der Pensionsträger (`antragsangaben.yaml: pensionstraeger`) und die
   zuständige Stelle (`kern.zustaendige_stelle`, `traeger.yaml`).
2. **Formular prüfen, bevor geschrieben wird:**
   - sha256 und Seitenzahl der Datei müssen der Version in der Zuordnung entsprechen;
   - jeder Feldname aus `felder` und `pflicht` muss in `reader.get_fields()` stehen;
   - jeder Export-Wert eines Knopfs muss zu den Zuständen des Knopfs gehören, bei Gruppen zu den `/AP /N` der
     Kinder.

   Weicht etwas ab, bricht der Lauf mit `AntragFehler` ab und schreibt nichts. Der Grund: pypdf ignoriert
   unbekannte Namen still (Spike #28).
3. **Belegen:** Befüllt werden nur Felder, deren Angaben alle im Gespräch vorkommen. Ein Feld ohne Angabe
   bleibt leer. Knöpfe bekommen den Export-Wert aus der Zuordnung, z. B. `zuerkennung → /01`, `PVA → /j`.
   MaxLen liest der Lotse selbst aus dem AcroForm-Baum, auch geerbt; `get_fields()` liefert sie nicht mit. Ein zu
   langer Wert wird **nicht gekürzt**. Er steht unter „noch offen“ mit Länge und Grenze.
4. **Schreiben:** `PdfWriter(clone_from=…)`, Feldwerte, `NeedAppearances=true`. Auf jeder Seite steht oben eine
   FreeText-Annotation „Entwurf, nicht eingereicht (SV KI-Lotse)“ in Rot, dazu `/Subject` in den Metadaten. Danach
   liest der Lotse die Datei zurück: Steht ein gesetzter Wert nicht im Feld, ist das ein Fehler.
5. **Ergebnis** (`AntragErgebnis`, JSON über `--json`): `pdf`, `formular` (Datei, Version, Seiten, sha256),
   `formularwahl` (Begründung mit Quelle, bei Reha auch das nicht gewählte Formular), `befuellt`, `noch_offen`,
   `unterlagen`, `stelle` und `eingereicht: false`.

## Feldzuordnung als Daten

| | PAL080 | Kur/Reha |
|---|---:|---:|
| Felder im PDF (Text / Knopf) | 63 / 34 | 46 / 45 |
| zugeordnet (Text / Knopf) | 10 / 1 | 8 / 1 |
| kuratierte Pflichtangaben | 15 | 10 |
| davon vom Formular einzeln belegt (`annahme: false`) | 1 | 8 |
| Unterlagen mit Seite | 5 | 1 |

- **Schlüssel der Angaben:** `person.*` meint die Person, die die Leistung braucht (pflegebedürftige Person bzw.
  Patientin oder Patient), `antragsteller.*` die Person im Gespräch. Dazu kommen `antrag.art` (Pflegegeld:
  `zuerkennung`, `erhoehung`, `weitergewaehrung`) und `stelle.name`. Mehrere Angaben in einem Feld fasst
  `format` zusammen, z. B. „Patient(in)“ = `{person.familienname} {person.vorname}`. `umformung: jahr` macht
  aus dem Geburtsdatum das Geburtsjahr.
- **Pflicht mit Quelle:** Jede Pflichtangabe nennt Seite und Wortlaut aus `pdftotext -layout`. Ein Test mit dem
  Marker `daten` prüft das gegen das PDF.
  - **PAL080** hat 0 Required-Flags und keine Sternchen. Belegt ist nur die Erklärung auf S. 4: „Ich habe alle
    Fragen richtig und vollständig beantwortet.“ Darum tragen die Pflichtangaben `annahme: true` mit Grund.
    Abschnitt 2 (Vertretung, Nachweis) gilt nur, wenn ein Antragsteller mit Familiennamen bekannt ist.
  - **Kur/Reha** belegt S. 1 wörtlich: „Von dem/der Versicherten (Antragsteller/in) in allen Teilen
    auszufüllen“. Die ärztliche Stellungnahme und die Begründung auf S. 2 sind `annahme: true`. Sie stehen
    immer unter „noch offen“ mit „füllt der Lotse nicht aus“.
- **Formularwahl Reha:** gewählt ist „Antrag Kur und Reha.pdf“ (S. 1: „Von dem/der Versicherten
  (Antragsteller/in) in allen Teilen auszufüllen“). Nicht gewählt ist `Reha_n_Unfall_052026.pdf`, denn S. 1
  sagt: „Vom antragstellenden Krankenhaus auszufüllen!“.
- **Formular und Stelle:** PAL080 trägt `fuer_stelle: PVA`. Ist laut BPGG § 22 eine andere Stelle zuständig
  (SVS, BVAEB), steht das als erster Punkt unter „noch offen“. Fehlt der Status, steht dort, dass die Stelle
  offen ist.

## Prüfungen und Tests

`uc1/tests/test_antrag.py`. Die Unit-Tests bauen ein Mini-PDF mit AcroForm per pypdf in `tmp_path`, darin
Textfelder, eines mit MaxLen, und eine Knopfgruppe mit Kindern. Jeder Test benennt den Fehler, den er fängt:

| Test | fängt |
|---|---|
| `test_unbekannter_feldname_ist_fehler` | einen still ignorierten Feldnamen; vorher wird nichts geschrieben |
| `test_feld_ohne_gespraechsangabe_bleibt_leer` | ein Feld, das ohne Angabe befüllt wird |
| `test_pflichtfeld_ohne_angabe_steht_in_noch_offen` | ein leeres Pflichtfeld ohne Eintrag mit Quelle |
| `test_checkbox_bekommt_richtigen_export_wert` | `true`/`Ja` oder den falschen Export-Wert, `/AS` am richtigen Kind |
| `test_unbekannter_export_wert_ist_fehler` | einen Export-Wert, den der Knopf nicht kennt |
| `test_entwurfsvermerk_in_beiden_lesern` | einen Entwurf ohne Vermerk (pypdf-Annotation und `pdftotext`) |
| `test_zu_langer_wert_wird_nicht_gekuerzt` | Abschneiden oder Überlauf bei MaxLen |
| `test_andere_sha256_ist_fehler` | eine andere Formularversion |
| `daten`: `test_echte_formulare_passen_zur_zuordnung` | Namen, Export-Werte, Version und MaxLen wie im Spike gegen die echten PDFs |
| `daten`: `test_wortlaute_stehen_auf_der_genannten_seite` | eine Quelle, die so nicht auf der Seite steht |
| `daten`: `test_pflegegeld_entwurf_mit_echtem_pal080` | Werte, die nicht ankommen; den Vermerk auf allen 8 Seiten |
| `daten`: `test_reha_waehlt_kur_und_reha_…` | die Wahl von Reha_n_Unfall, eine fehlende ärztliche Begründung |

## Demo-Lauf (2026-11-05, M4, Azure `gpt-5-4-mini`, erfundene Daten)

**Pflegegeld:** drei Wechsel. (1) „Meine Mutter Erika Musterfrau, geboren am 01.02.1943, kommt allein nicht mehr
zurecht. Ich bin ihr Sohn Karl Musterfrau.“ ergibt die Rückfrage nach dem Status. (2) „PVA, Musterstraße 1,
1100 Wien“ ergibt die Antwort mit dem Schritt „Antrag vorbereiten“. (3) „noch kein Pflegegeld“ setzt
`antrag.art = zuerkennung`. `lotse antrag pflegegeld` befüllt 10 Felder: `Antrag Pflg=/01`, `Fam.Name`,
`Vorname`, `Geburtsdatum`, `Adresse Straße`, `Hausnummer…`, `PLZ`, `Ort`, `Familienname andere`,
`Vorname andere Person`. `Telefon` bleibt leer, weil es im Gespräch nicht vorkam. Offen bleiben 11 Punkte:
Versicherungsnummer, Staatsbürgerschaft, Personenstand, Vertretung/Nachweis, Gesundheit, Gründe, Medikamente,
Betreuung, Fragen 5–8, Anweisung, Unterschrift. Zuständig ist die PVA (BPGG § 22 Abs. 1 Z 1). Beide Leser zeigen
die Werte; `pdftotext` zeigt den Vermerk 8-mal.

**Reha:** Gespräch aus dem Case-Management („Ich bin Case-Managerin im Spital. Frau Erika Musterfrau … braucht
nach ihrer Operation eine Reha.“, dann PVA und Adresse). Befüllt werden 8 Felder, darunter
`zuständiger SV-träger = Pensionsversicherungsanstalt (PVA)`, `Patient(in) = Musterfrau Erika`,
`Pensionsversicherung=/j` und `Geburtsjahr = 1943`. Offen bleiben 7 Punkte, darunter die ärztliche
Stellungnahme und die ärztliche Begründung sowie die Unterschrift der versicherten Person. Zuständig ist die PVA
(ASVG § 300).

## Bekannte Grenzen

- **Anzeige in Vorschau.app und Acrobat nicht geprüft.** Geprüft sind pypdf und poppler (`pdftotext`). Der
  Vermerk ist eine FreeText-Annotation ohne eigenen Appearance-Stream (pypdf erzeugt keinen). poppler und
  Acrobat erzeugen ihn aus `/DA`, Vorschau.app vermutlich auch. Das ist nicht gemessen. Felder zeigen ihre Werte
  über NeedAppearances. poppler meldet beim Lesen „Font dictionary is not a dictionary“, der Text erscheint
  trotzdem.
- **Export-Werte von PAL080 „Antrag Pflg“** (/01 Zuerkennung, /02 Erhöhung, /03 Weitergewährung) sind aus der
  Lage der Widgets abgeleitet, das Formular hat dafür keinen Tooltip (`annahme` in der Zuordnung).
- **Kur/Reha hat keine Tooltips.** Die Felder rechts oben (`Anschrift`, `Personenstand`, `Telefonnummer` unter
  „Angaben des (der) Versicherten“) sind nicht eindeutig der Patientin zuzuordnen. Befüllt wird nur
  `Anschrift Patient(in)`. Der Block „Versicherte(r)“ gilt nur, wenn die Patientin über eine angehörige Person
  versichert ist; der Lotse füllt ihn nicht.
- Die **Versicherungsnummer** fragt der Lotse bewusst nicht ab. Sie steht immer unter „noch offen“.
- **Angaben aus dem Modell** gelten nur, wenn sie wörtlich im Gespräch stehen; ein Datum muss als Datum im
  Gespräch vorkommen. `antrag.art` kommt nur aus Regeln: Im Azure-Lauf setzte das Modell „zuerkennung“, ohne
  dass das Gespräch etwas über bisheriges Pflegegeld sagte.
- Ein neues Formular (andere sha256) braucht eine neue, geprüfte Zuordnung. Der Lotse befüllt es nicht.
