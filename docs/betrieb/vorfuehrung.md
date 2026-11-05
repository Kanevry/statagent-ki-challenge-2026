# Vorführung am Freitag (06.11.2026) ohne Netz

Die Vorführung läuft auf dem Vorführrechner, weil das Veranstaltungs-WLAN unsicher ist. Alles Lesende (`/`, `/uc3`,
`/uc4`) liest aus der lokalen Datenbank `statistik_demo`, die genau den Inhalt der Online-Demo hat.
Stand und Messdatum: 05.11.2026. Was nicht gemessen ist, steht als „nicht gemessen“.

Platzhalter: `<hauptablage>` ist der Checkout mit der `.env.local`, `<vorfuehrung>` der Worktree für die Vorführung,
`<lokal>` die Verbindung zur lokalen Postgres-Instanz auf Port 5433 (`postgresql://<nutzer>:<passwort>@localhost:5433`),
`<bau-db>` die Verbindungs-URL der Rechen-Datenbank auf dem Bau-Rechner, `<bau-host>` dessen SSH-Name. Zugänge stehen
nie im Repo.

## Vorbereitung (Donnerstag spät oder Freitag nach dem Merge-Stopp, mit Netz)

Die Hauptablage stand am 05.11. auf einem alten Planungs-Branch, nicht auf `main`. Vorgeführt wird deshalb aus einem
eigenen Worktree auf dem gemergten Stand. `web` liest `../.env.local`, also die Datei an der Wurzel des Worktrees; sie ist
ein Link auf die `.env.local` der Hauptablage und kommt nie ins Repo.

```bash
cd <hauptablage> && git fetch origin
git worktree add --detach <vorfuehrung> origin/main
cd <vorfuehrung> && ln -s <hauptablage>/.env.local .env.local
pnpm install --frozen-lockfile && uv sync --all-packages   # braucht Netz, danach nicht mehr
```

Ist der Worktree schon da: `git -C <vorfuehrung> checkout --detach origin/main` nach einem `git fetch`, dann dieselbe
Installationszeile.

## Start in fünf Befehlen (Freitag früh, ohne Netz)

```bash
cd <vorfuehrung> && grep -cE '^(LLM_PROVIDER|UC[123]_DATABASE_URL)=' .env.local   # muss 0 sein, sonst siehe unten
psql "<lokal>/statistik_demo" -Atc 'select count(*) from meta.lauf'                  # erwartet 166
export UC3_DATABASE_URL=<lokal>/statistik_demo UC1_DATABASE_URL=<lokal>/lotse UC2_DATABASE_URL=<lokal>/healthpolicy LLM_PROVIDER=mock NEXT_TELEMETRY_DISABLED=1
pnpm dev   # Terminal 1, App auf http://127.0.0.1:3000 (Skript in web/package.json)
curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1:3000/uc3   # Terminal 2, erwartet 200
```

- `web` startet mit `dotenv -o` (`web/package.json`): Ein Schlüssel aus `.env.local` **überschreibt** das `export`.
  Deshalb muss die erste Zeile 0 ergeben. Steht dort `LLM_PROVIDER` oder eine `UC*_DATABASE_URL`, liefe die Vorführung
  still gegen ein echtes Modell (Geld) oder eine andere Datenbank. Dann die Zeile in `.env.local` auskommentieren.
  Am 05.11. ergab die Prüfung 0 (gemessen nur über Schlüsselnamen).
- `LLM_PROVIDER=mock` gibt feste Platzhalter statt Modellantworten. Zahlen kommen aus der Datenbank und bleiben gleich.
- `pnpm dev` statt Produktions-Build: Der Build ist für den Vorführrechner zu schwer. Dauer des ersten Aufrufs: nicht
  gemessen.
- `.env.local` enthält weitere Schlüssel (Modell, Voice, Abgabe). Ihre Werte werden nie gezeigt.

## Probe ohne Netz (nicht ausgeführt)

1. WLAN aus: `networksetup -setairportpower en0 off` (wieder an: `... on`). Ethernet und Hotspot ebenfalls trennen.
   Das trennt auch den Tunnel zum Bau-Rechner.
2. Die fünf Befehle oben ausführen, dann `/`, `/uc3`, `/uc3/klassifikationen`, `/uc4` und `/praesentation` öffnen.
3. Erwartet: Status 200, keine Meldung „nicht erreichbar“, dieselben Zahlen wie online (24 Lieferungen, 166 Läufe).
4. Im Browser unter „Netzwerk“ prüfen, dass keine Anfrage nach außen geht. Im Web-Code stehen keine Schrift- oder
   CDN-Adressen, die Schriften kommen lokal aus `@fontsource-variable/*` (gemessen mit `grep`).

## Datenbank statistik_demo

Der Dump `uc3-online-2026-11-05.sql.gz` liegt auf dem Server in `<basis>/daten/uc3/` und als Kopie lokal außerhalb des
Repos. Er ist 17.057.030 Bytes groß, die ersten 16 Zeichen seines SHA-256 sind `891a651c9a09c2d7`.

- Inhalt: pg_dump im Klartext, 2.781.882 Zeilen, nur die Schemas `meta` und `stat` (ohne `roh`, bereinigt).
  Die Klassifikationen stecken in `stat.klass_*`, ein eigenes Schema `klassifikation` gibt es im Dump nicht.
- Er enthält kein `DROP`, kein `CREATE DATABASE`, kein `\connect` und kein eigenes `BEGIN`/`COMMIT`. Gegen `statistik`
  würde er an `CREATE SCHEMA` scheitern. Er gehört deshalb nur in eine neue, leere Datenbank.

```bash
psql "<lokal>/statistik" -c 'create database statistik_demo'   # nur wenn sie fehlt
gzip -t <dump> && { echo 'begin;'; gzip -dc <dump> && echo 'commit;'; } | nice -n 10 psql "<lokal>/statistik_demo" -X -q -v ON_ERROR_STOP=1
for s in stat meta; do psql "<lokal>/statistik_demo" -X -q -At -v schema=$s -f deploy/sql/inhaltshash.sql | grep GESAMT; done
scripts/deploy.sh inhaltshash statistik stat; scripts/deploy.sh inhaltshash statistik meta   # online, nur lesend
```

`gzip -t` prüft die ganze Datei vorher, und das `commit` folgt nur, wenn gzip bis zum Ende gelesen hat (wie
`scripts/deploy.sh daten`).

Gemessen am 05.11.: Einspielen 12,9 s, Größe 839 MB, freie Platte 21 GiB vorher, 19 GiB nachher.
Die GESAMT-Zeilen sind lokal und online gleich: `stat 2764050 95f11e1b4c81107e70f45300c37b18c3`, `meta 16350 6b3fe1a923300314ac641e0e9edb1e04`.
Neuaufbau: `dropdb` für `statistik_demo`, dann die Befehle oben (rund 13 s).

Kernabfragen der Seiten, lokal gelaufen: `select count(*) from meta.lauf` gibt 166, `count(distinct lieferung)` gibt 24,
der letzte Lauf ist Lieferung 2026-07 mit Status `unveraendert`. `select sum(wert), count(*) from stat.stat_beschaeftigte
where zeitraum_von='2024-08-31'` gibt 1568944 und 115220. Die App liest nur `UC3_DATABASE_URL` (`web/components/uc3/db.ts`,
`web/landing/daten/befunde.ts`) und nur aus `meta` und `stat`. Die App selbst ist nicht gestartet worden.

## Live-Änderung (ein Lauf)

Entscheid (Lead und Infra-Lane, 05.11.): Die Live-Änderung schreibt in eine eigene Kopie `statistik_vorfuehrung` der
Abgabe-DB `statistik` auf dem Bau-Rechner. `statistik` bleibt unberührt, damit die Abgabe nachrechenbar ist. Die
Vorführ-App liest bei der Live-Änderung genau diese Kopie, sonst erscheint der neue Lauf nicht. `statistik_demo` (lokal,
lesend) ist der Rückfall ohne Netz.

**Kopie anlegen, Freitag 06:00 bis 06:30 (nach den letzten Läufen, vor der Vorführung).** Auf dem Bau-Rechner, aus
einem Checkout mit `scripts/` und `deploy/sql/`:

```bash
scripts/vorfuehrung-db.sh --ersetzen statistik statistik_vorfuehrung
```

- `statistik` wird nur gelesen. Das Ziel darf nie `statistik` sein; ohne `--ersetzen` bricht das Skript ab, wenn es die
  Kopie schon gibt.
- Erst `CREATE DATABASE … TEMPLATE` (schnell, geht nur ohne offene Verbindungen auf `statistik`), sonst
  `pg_dump | pg_restore`. Danach muss der Inhalts-Hash von `stat` und `meta` in Quelle und Kopie gleich sein, sonst Exit 1.
- Probe am 05.11. mit einem Wegwerf-Namen: Rückweg `pg_dump | pg_restore` (zwei Verbindungen offen), 132 s, 5,7 GB,
  166 Läufe, beide Hashes gleich, `stat` auch gleich wie online. Die Probe-DB ist wieder gelöscht.
- Nicht verwechseln: `statistik_probe` und `statistik_live80*` sind Übungskopien anderer Lanes, keine Quelle.

**Vorführen:**

1. **Mit Netz:** SSH-Tunnel `ssh -o ExitOnForwardFailure=yes -N -L <tunnel-port>:localhost:5433 <bau-host>`
   (Terminal 3), dann die App mit `UC3_DATABASE_URL=<bau-db-vorfuehrung>` neu starten, also der Verbindung zur Kopie
   `statistik_vorfuehrung` über den Tunnel. Sie zeigt dieselben Zahlen wie online plus den neuen Lauf. Ein Lauf über den
   Tunnel ist nicht erprobt.
2. **Ohne Netz:** keine Live-Änderung, die App bleibt auf `statistik_demo` (lesend, gleiche Zahlen wie online). Ein
   Einzellauf gegen die lokale `statistik` ist möglich (dort liegt `roh.lieferung` mit allen 24 Lieferungen, aber nur
   2 Läufe, die Anzeige weicht dann von online ab); Dauer lokal nicht gemessen.
3. **Letzter Rückfall:** Backup-Video.

Wechsel zwischen den Datenbanken: `pnpm dev` mit Strg-C beenden, `export UC3_DATABASE_URL=…`, neu starten. Vorher die
Prüfzeile aus „Start in fünf Befehlen“ wiederholen (`.env.local` darf `UC3_DATABASE_URL` nicht setzen).

## Voice (nur auf ausdrückliche Anordnung)

Befehle aus `docs/voice.md`, `--help` geprüft (`serve`, `sync`, `smoke`; `serve` kennt `--uc uc4`, `--mock`, `--port`, `--host`):

```bash
uv run python -m plattform.voice serve --uc uc4 --port 8104   # Terminal 3
scripts/tunnel.sh 8104                                        # druckt PUBLIC_URL (braucht cloudflared)
# PUBLIC_URL in <vorfuehrung>/.env.local eintragen (Wert nie ausgeben), dann:
uv run python -m plattform.voice sync                         # wirkt nach außen
```

Dann ein Web-Anruf auf `http://127.0.0.1:3000/uc4` als Smoke. Die Chat-API (`smoke`) braucht eine Karte (402).
Die Tunnel-Adresse wechselt bei jedem Start, `sync` ist danach jedes Mal nötig. Kosten: etwa 5 Cent je 40 s, Guthaben nie
unter 5 €. `sync` und `smoke` laufen nur mit Freigabe. Voice braucht Netz (Vapi, cloudflared). Gestartet ist nichts davon.

## Was Netz braucht

- `pnpm install`, `uv sync`, Git und `scripts/deploy.sh`.
- Modellaufrufe mit `azure`, `mistral`, `claude`. Mit `mock` und `ollama` lokal entfällt das.
- Voice: Vapi, cloudflared-Tunnel, Webhook.
- Der Tunnel zum Bau-Rechner für die Live-Änderung.
- Die Abgabe (`SVBOX_*`). Ein PDF-Dienst steht in `.env.local`, wird im Repo aber nicht gelesen.
- Kein Netz brauchen: Lesen aus `statistik_demo`, Schriften, `uc3 lauf` (laut `CLAUDE.md` ohne Sprachmodell).

## Offene Punkte

- App-Start gegen `statistik_demo` und die Probe ohne Netz sind nicht gelaufen (Build zu schwer für den Vorführrechner).
- `/uc4` nutzt auch `UC1_DATABASE_URL` und `UC2_DATABASE_URL`. Die lokalen DBs `lotse` und `healthpolicy` haben je 9
  Tabellen, ihr Inhalt ist nicht mit online verglichen.
- Der Tunnel zum Bau-Rechner ist nicht mit einem Lauf erprobt, die Laufdauer lokal ist nicht gemessen.
- `statistik_vorfuehrung` wird erst Freitag 06:00 bis 06:30 angelegt (Infra-Lane).
- Der Worktree `<vorfuehrung>` ist noch nicht angelegt; er gehört nach dem Merge-Stopp auf den letzten `main`.
