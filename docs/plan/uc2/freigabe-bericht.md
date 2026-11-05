# Freigabe des Berichts (UC2, Szene 4 „ein Kern für alle drei“)

Stand 05.11.2026. Ein Mensch gibt den Bericht einer fertigen Verhandlung mit Vor- und Nachnamen frei oder lehnt ihn ab.

## Was der Nutzer sieht

- Auf `/uc2/panel` unter „Am Ende gilt“ steht die Marke „Entwurf“, bis entschieden ist; nach einer Ablehnung steht dort die Marke „Abgelehnt“, nach einer Freigabe keine.
- Darunter die Karte „Freigabe des Berichts“ mit dem Satz „Das Ergebnis der Verhandlung wird als geprüft markiert und kommt mit deinem Namen ins Protokoll.“
- Nach der Freigabe: „Freigegeben von <Name>, <Zeit>“. Nach der Ablehnung: „Abgelehnt von <Name>, <Zeit>“ mit Begründung (höchstens 500 Zeichen, das Feld begrenzt sie).
- Öffentlich (Online-Demo) steht nur „Freigegeben am <Zeit>“ bzw. „Abgelehnt am <Zeit>“, ohne Name und ohne Grund (Personenschutz, siehe Schnittstellen).
- Im Vorführmodus (aufgezeichnete Verhandlung) wirkt die Freigabe nur in der Seite. Statt des Satzes mit dem Protokoll steht dort „In der Vorführung wird nichts gespeichert. Im echten Betrieb kommt dein Name ins Protokoll.“ und unten „Vorführung: nichts gespeichert“; es geht keine Anfrage an den Server.
- Alle Knöpfe, auch die Textknöpfe „Ablehnen“ und „Zurück“, sind mindestens 44 px hoch (`min-h-11`, wie in UC3).

## Speicherweg

`plattform.freigabe.freigeben` legt für „ja“ immer einen Git-Commit an (auch ohne Datei, als leeren Commit). Eine reine Entscheidung zu einem Fall in PG passt dazu nicht. Darum:

- Die Entscheidung steht in `uc2.freigabe` (`uc2/sql/003_freigabe.sql`, idempotent), höchstens eine je Fall, endgültig.
- Zusätzlich schreibt dieselbe Transaktion eine Zeile in `meta.protokoll` (`akteur = mensch`, `ref = uc2/fall/<id>`, Status `freigegeben` oder `abgelehnt`) über `plattform.protokoll.schreibe`.
- Vertrag P: dieselbe Transaktion schreibt auch `meta.freigabe` (`entscheidung` `ja|nein`, `objekt_typ = antwort`, `objekt_ref = uc2/fall/<id>`, Name, Zeitpunkt, bei „nein“ die Begründung), ohne Git-Commit. So erscheinen Ablehnungen in `protokoll.md` unter „Ablehnungen“. Die Verbindung muss `autocommit=True` ohne offene Transaktion haben, `schreibe_freigabe` prüft das.
- Der Name wird mit `plattform.freigabe.pruefe_name` geprüft (Python) und mit `pruefeName` aus `@kic/ui` (Web, gleiche Regel).

## Schnittstellen

- `POST /faelle/{id}/freigabe` (Python-API) mit `{name, entscheidung: "freigegeben" | "abgelehnt", begruendung?}` gibt `{zeitpunkt}` zurück. Nur für Fälle mit Status `fertig` (sonst 409), unbekannter Fall 404, schon entschieden 409, ungültiger Name 422.
- `GET /faelle/{id}` enthält `freigabe: {name, zeit, entscheidung, begruendung} | null`. Der Ausgabefilter (`uc2.api.belegfilter.bericht_fuer_ausgabe`) entfernt `name` und `begruendung`, sobald `KIC_ONLINE=1` oder `KIC_ONLINE_LESEND=1` gesetzt ist; übrig bleiben `entscheidung` und `zeit`. Lokal bleibt alles vollständig. Keine eigene Variable, daher kein neuer README-Eintrag.
- `POST /api/uc2/faelle/{id}/freigabe` (Web) reicht durch. Sperren wie beim Start: `KIC_ONLINE_LESEND=1` gibt 403 vor dem Body, Ratenlimit je IP (429, eigener Satz „Zu viele Freigaben in kurzer Zeit. Bitte in einer Minute noch einmal.“ mit `Retry-After`), Body bis 4 KiB (413), nur feste Sätze in Alltagssprache ohne Feldnamen (SEC-009). Die Python-API sperrt `KIC_ONLINE_LESEND=1` zusätzlich selbst.
- CLI: `uv run uc2 freigabe <fall_id> --name "Vorname Nachname" [--ablehnen --begruendung "…"]`.

## Grenzen

- Beispielnamen in Tests: „Maria Beispiel“. „Musterfrau“ lehnt die Namensregel ab (Teil „muster“).
- `FreigabeKarte` aus `@kic/ui` passt nicht (Vorschlag eines Agenten, Zahlen vorher und nachher). Die Karte hier nutzt dieselben Bausteine (`Feld`, `Knopf`, `Status`) und dieselbe Namensprüfung.
