# Freigabe des Berichts (UC2, Szene 4 „ein Kern für alle drei“)

Stand 05.11.2026. Ein Mensch gibt den Bericht einer fertigen Verhandlung mit Vor- und Nachnamen frei oder lehnt ihn ab.

## Was der Nutzer sieht

- Auf `/uc2/panel` unter „Am Ende gilt“ steht die Marke „Entwurf“, bis entschieden ist.
- Darunter die Karte „Freigabe des Berichts“ mit dem Satz „Das Ergebnis der Verhandlung wird als geprüft markiert und kommt mit deinem Namen ins Protokoll.“
- Nach der Freigabe: „Freigegeben von <Name>, <Zeit>“, die Marke ist weg. Nach der Ablehnung: „Abgelehnt von <Name>, <Zeit>“ mit Begründung.
- Im Vorführmodus (aufgezeichnete Verhandlung) wirkt die Freigabe nur in der Seite. Dort steht „Vorführung: nichts gespeichert“, und es geht keine Anfrage an den Server.

## Speicherweg

`plattform.freigabe.freigeben` legt für „ja“ immer einen Git-Commit an (auch ohne Datei, als leeren Commit). Eine reine Entscheidung zu einem Fall in PG passt dazu nicht. Darum:

- Die Entscheidung steht in `uc2.freigabe` (`uc2/sql/003_freigabe.sql`, idempotent), höchstens eine je Fall, endgültig.
- Zusätzlich schreibt dieselbe Transaktion eine Zeile in `meta.protokoll` (`akteur = mensch`, `ref = uc2/fall/<id>`, Status `freigegeben` oder `abgelehnt`) über `plattform.protokoll.schreibe`. So erscheint sie im gemeinsamen Protokoll.
- Der Name wird mit `plattform.freigabe.pruefe_name` geprüft (Python) und mit `pruefeName` aus `@kic/ui` (Web, gleiche Regel).
- `meta.freigabe` bleibt unberührt. Wenn die Plattform einmal eine Freigabe ohne Commit anbietet (`objekt_typ = antwort`), kann `schreibe_freigabe` in `uc2/src/uc2/verhandlung/speicher.py` darauf umgestellt werden.

## Schnittstellen

- `POST /faelle/{id}/freigabe` (Python-API) mit `{name, entscheidung: "freigegeben" | "abgelehnt", begruendung?}` gibt `{zeitpunkt}` zurück. Nur für Fälle mit Status `fertig` (sonst 409), unbekannter Fall 404, schon entschieden 409, ungültiger Name 422.
- `GET /faelle/{id}` enthält `freigabe: {name, zeit, entscheidung, begruendung} | null`.
- `POST /api/uc2/faelle/{id}/freigabe` (Web) reicht durch. Sperren wie beim Start: `KIC_ONLINE_LESEND=1` gibt 403 vor dem Body, Ratenlimit je IP (429), Body bis 4 KiB (413), nur feste Sätze (SEC-009). Die Python-API sperrt `KIC_ONLINE_LESEND=1` zusätzlich selbst.
- CLI: `uv run uc2 freigabe <fall_id> --name "Vorname Nachname" [--ablehnen --begruendung "…"]`.

## Grenzen

- Beispielnamen in Tests: „Maria Beispiel“. „Musterfrau“ lehnt die Namensregel ab (Teil „muster“).
- `FreigabeKarte` aus `@kic/ui` passt nicht (Vorschlag eines Agenten, Zahlen vorher und nachher). Die Karte hier nutzt dieselben Bausteine (`Feld`, `Knopf`, `Status`) und dieselbe Namensprüfung.
