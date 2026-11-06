# Abgabe-Weg: GitHub und SV-Box

Abgabe am Fr 06.11.2026 um 09:00, an zwei Stellen: Der Code kommt in das GitHub-Repo `KIChallenge/OneShotAndy`, die Ergebnisdateien in den SV-Box-Teamordner. Beide Skripte machen ohne Schalter nur einen Trockenlauf. Erst `--ausfuehren` schreibt nach außen. Das tut nur der Lead, nach der Freigabe des Owners.

Ablauf und Zeiten stehen in `abgabe/CHECKLISTE.md`.

## 1. Ergebnisdateien in den SV-Box-Teamordner (Start 08:00)

```bash
python3 -I scripts/abgabe/svbox_upload.py \
  --csv <ordner-außerhalb-des-repos>/ministerium_2026-07.csv \
  --env-datei <pfad>/.env.local \
  --erwarteter-kopf <40-stelliger-commit-von-main>   # Trockenlauf
# danach dasselbe mit --ausfuehren
```

- Das Skript läuft nur aus einem Checkout, dessen HEAD der erwartete Kopf ist und dessen `abgabe/` sauber ist. Der Kopf steht danach im Nachweis. So kommen in die SV-Box und nach GitHub dieselben Stände.

- Welche Dateien hochgehen, steht in `abgabe/manifest.json`: alle Einträge außer `.gitignore`, dazu die Ministeriums-CSV. Die CSV liegt nicht im Repo, weil sie Einzeldaten enthält. Unterordner bleiben erhalten.
- Vor dem Upload prüft das Skript jede Datei gegen Größe und sha256 aus dem Manifest. Weicht eine Datei ab, lädt es nichts hoch.
- Im Trockenlauf liest es den Teamordner nur (PROPFIND). Es zeigt die Rechte des Ordners, was dort schon liegt und was hochgehen würde.
- Mit `--ausfuehren` lädt es per PUT hoch und liest danach jede Datei zurück, mit Größe und sha256. Das Ergebnis steht in `docs/abgabe/transfernachweis.json`. Die Datei enthält Zeit, Commit, Anzahl und Differenzen, aber keine Zugangsdaten. Exit 0 gibt es nur, wenn jede Datei beim Rücklesen stimmt.
- Der Host weist nach rund 10 schnellen Anfragen Verbindungen ab. Darum wartet das Skript 2 s zwischen zwei Anfragen (`--pause`). Ein ganzer Upload dauert so rund 7 min. Lesend gemessen: 143 Anfragen in 407 s ohne Abweisung. Der Schreibweg ist mit einer einzelnen Testdatei belegt (`--probe`, 05.11.); viele Dateien zu schreiben kann länger dauern. Bei Abweisung und Netzfehlern wiederholt es, bis zu 15 min je Anfrage. 401, 403 und 404 brechen sofort ab.
- Nach einem Abbruch ist ein zweiter Aufruf mit `--ausfuehren` gefahrlos: Er überschreibt die Dateien und löscht nichts. Dateien im Teamordner, die nicht im Manifest stehen, bleiben liegen. Sie zählen als Differenz und ergeben Exit 1, schon im Trockenlauf, weil das Kriterium volle Übereinstimmung verlangt; im Nachweis stehen sie unter `fremd_im_teamordner`. Was dann zu tun ist, steht in `abgabe/CHECKLISTE.md`.
- `--probe` prüft den Schreibweg ohne die Abgabedateien: Das Skript legt den Ordner `_probe-lead` neu an, schreibt eine Testdatei, liest sie zurück und löscht beide wieder. Gibt es den Ordner schon, ändert es nichts; liegt danach Fremdes darin, bleibt der Ordner stehen. Das schreibt in den Teamordner und braucht darum die Freigabe des Owners.
- Rückfall, wenn das Skript scheitert: Upload von Hand über das angemeldete Browser-Profil `svbox`, danach Trockenlauf mit `--erwarteter-kopf` (zeigt, was dort liegt).
- Den Zugang (`SVBOX_TEAM_URL`, `SVBOX_TEAM_TOKEN`, `SVBOX_TEAM_PW`) liest das Skript aus `--env-datei` oder aus der Umgebung, nie aus einem Argument. Link und Token müssen zum selben Share gehören. Die Ausgabe zeigt weder den Link noch das Passwort.

## 2. Code nach GitHub (kurz vor 09:00, nicht vor 08:30)

```bash
python3 -I scripts/abgabe/github_push.py \
  --sperrmuster <datei-außerhalb-des-repos> \
  --erwarteter-kopf <40-stelliger-commit-von-main>   # Trockenlauf
# danach dasselbe mit --ausfuehren
```

- Das Skript holt main (`refs/remotes/origin/main`, vorher `git fetch origin`) und GitHub-main in einen leeren Ordner unter `/tmp`.
- Fehlt GitHub-main noch in der Historie, mergt es mit `--allow-unrelated-histories -s ours`. Der Inhalt bleibt dann genau unser main, und der Push ist ein Fast-Forward.
- Danach prüft es:
  - die Pflichtdatei `KI-Challenge_UseCase.yaml`, die gleich sein muss wie auf GitHub,
  - dass alle Dateien von GitHub erhalten bleiben; nur `docs/abnahme/laeufe/` darf dort verschwinden, die Rohläufe liegen nicht mehr auf main,
  - die Dateiliste im Baum und über die ganze Historie: keine `.env`-Dateien, keine Schlüssel, keine `ministerium_*.csv`, nichts aus `svbox/` oder `lieferungen/`,
  - dass keine Datei über 50 MB ist,
  - gitleaks über die ganze Historie,
  - die Sperrmuster in Dateien, Commit-Nachrichten und Identitäten.
- Die Sperrmuster für Rechnernamen und Pfade stehen absichtlich nicht im öffentlichen Repo. Die Ausgabe nennt nur Datei und Zeile.
- Bei Commits sind bis zu 12 bekannte Treffer erlaubt. Die Historie bleibt nach dem Entscheid des Leads unverändert.
- Treffer in alten Dateiständen zählt das Skript nur (`sperrmuster historie`). Sie blocken den Push nicht.
- Der Trockenlauf fragt GitHub mit `git push --dry-run`. So stehen Zugang und Fast-Forward schon vorher fest.
- `--ausfuehren` läuft nur, wenn alle Prüfungen bestanden sind, `--erwarteter-kopf` gesetzt ist und es 08:30 Wiener Zeit oder später ist. Danach liest das Skript den GitHub-Stand mit `git ls-remote` zurück und schreibt einen Nachweis als JSON neben den Arbeitsordner, mit Commit und Pushzeit.
