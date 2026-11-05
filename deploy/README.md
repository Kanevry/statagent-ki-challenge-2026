# Online-Deploy: https://ki-challenge.gotzendorfer.at

Die Domain ist bewusst öffentlich genannt (Lead 05.11.2026); im Code steht sie nicht, dort kommt sie aus `DEPLOY_DOMAIN`
und `SITE_ADDRESS`.

Die Demo läuft zusätzlich zur lokalen Vorführung online, damit jede und jeder sie selbst ausprobieren kann (#68).
Server, Zugänge und Pfade stehen bewusst nicht im Repo; hier heißen sie `<server>` (SSH-Alias) und `<basis>`
(Basisordner auf dem Server).

## Stand

| Teil | Inhalt | Stand |
|---|---|---|
| Caddy | TLS (Let's Encrypt), Sicherheits-Header, Inhalt umschaltbar, öffentlich ohne Passwort | online seit 05.11.2026 |
| db | PostgreSQL 16, je UC eine Datenbank, ohne Port nach außen; App liest als `kic_app` (nur SELECT) | läuft, UC2-Index eingespielt |
| app | Next.js-Web (standalone) plus Python-Workspace in einem Image | läuft intern, geht mit `INHALT=app` online |

## Ziel einstellen

`scripts/deploy.sh` liest `DEPLOY_HOST`, `DEPLOY_BASIS` und `DEPLOY_DOMAIN` aus der Umgebung, sonst aus
`~/.config/ki-challenge/deploy.env` (eine Zeile je Wert, `NAME=wert`). Der CI-Job `deploy` bekommt sie als
Projektvariablen. Im Repo gibt es keinen Default.

## Aufbau auf dem Server

```
<basis>/
  .env.server          Geheimnisse und Schalter, nur für den Deploy-Nutzer lesbar (Vorlage: deploy/env.server.example)
  neu-<rev>-<pid>/     neuer Stand je Deploy: compose config, caddy validate und Image-Build, danach gelöscht
  repo/                laufender Stand (git archive von HEAD); REVISION nennt den Commit, der wirklich läuft
  .deploy.lock         flock: ein Deploy zur Zeit (Rechner und CI teilen sich den Server)
  daten/               Dumps zum Einspielen, außerhalb von repo/ (rsync --delete erreicht sie nicht)
```

Docker-Volumes halten Zertifikate (`caddy_data`, `caddy_config`) und die Datenbanken (`db_daten`) über Deploys hinweg.

## Befehle

Alle im Repo-Wurzelverzeichnis. Ausgeliefert wird immer `HEAD`; uncommittete Änderungen gehen nicht mit.

```bash
scripts/deploy.sh init                   # einmalig: .env.server und beide DB-Passwörter anlegen (idempotent)
scripts/deploy.sh                        # deployen und prüfen (= up + pruefen)
scripts/deploy.sh up                     # nur deployen: prüfen und bauen im neuen Stand, übernehmen, up --wait, rechte
scripts/deploy.sh rechte                 # Rolle kic_app anlegen, Leserechte in allen App-DBs, Gegenprobe als kic_app
scripts/deploy.sh pruefen                # von außen: 308, 200, Header, 404, Seiten, Sperrliste, Frage-Wege; Container healthy
scripts/deploy.sh status                 # Container, ausgelieferte Revision, letzte Caddy-Logzeilen
scripts/deploy.sh bauprobe <ref>         # App-Image eines Branches auf dem Server bauen und kurz anstarten
scripts/deploy.sh daten <db> <datei>     # Dump (.dump oder .sql.gz) aus <basis>/daten/<datei> einspielen, vorher sichern
scripts/deploy.sh sichern [<db>]         # pg_dump -Fc nach <basis>/daten/sicherung/, mit sha256, je DB die letzten 5
scripts/deploy.sh inhaltshash <db> <s>   # Inhalts-Hash eines Schemas, vergleichbar mit lokal (deploy/sql/inhaltshash.sql)
```

`up` prüft Compose-Datei und Caddyfile und baut das App-Image im neuen Stand, bevor sich an den laufenden Ordnern etwas
ändert. Eine kaputte Konfiguration oder ein fehlgeschlagener Build bricht ab und lässt die Seite stehen. Images baut der
Server, nicht der Entwicklerrechner. Nach dem Deploy räumt `up` Build-Cache älter als 48 Stunden und namenlose Images
weg und nennt den freien Platz. `daten` spielt in einer Transaktion ein: ein Fehler lässt die Datenbank, wie sie war.

`pruefen` misst von außen, dass genau das offen ist, was offen sein soll: Die Seiten liefern 200. Jeder schreibende Weg der
App (Freigaben, UC2-Fälle, Modellwahl, Voice) bekommt die 403-Antwort von Caddy. Die zwei Frage-Wege sind offen (400 auf
eine leere Frage, ohne Rechnen und ohne Modell), genau wenn `KIC_ONLINE_FRAGEN=1` in `.env.server` steht, sonst 403.

## Zugang

Die Seite ist öffentlich, ohne Passwort (Owner 05.11.2026: Basic Auth entfernt), und lesend: Caddy lässt nur GET und
HEAD durch, dazu POST auf genau zwei Pfade (`/api/uc3/frage`, `/api/uc4/frage`), und antwortet auf alles andere mit
403, bevor die Anfrage die App erreicht. Das sperrt Freigabe-POSTs, Läufe, UC2-Fälle und Next Server Actions. Die App
bekommt zusätzlich `KIC_ONLINE_LESEND=1` und nimmt die zwei Frage-Wege erst mit `KIC_ONLINE_FRAGEN=1` an. Suchmaschinen sollen die
Seite nicht aufnehmen (`X-Robots-Tag: noindex, nofollow`).

Datenbank: Die App verbindet sich als `kic_app` (nur SELECT, `default_transaction_read_only`, kein CREATE, kein
Superuser). Der Superuser `statistik` bleibt für `daten`, `sichern`, `inhaltshash` und `rechte`. `rechte` läuft nach
jedem `up` und `daten`: Es entzieht PUBLIC das Anlegen und Schreiben, bricht ab, sobald `kic_app` in einer Datenbank ein
Schreibrecht (auch auf Spalten, Sequenzen oder über eine Rolle) oder CREATE hat, und prüft in jeder Datenbank als
`kic_app`, dass Anlegen mit „permission denied“ scheitert (#108a). Gemessen 05.11.: online 0 Schreibrechte.

## Schalter in `.env.server`

| Schlüssel | Werte | Wirkung |
|---|---|---|
| `SITE_ADDRESS` | Domain | öffentliche Adresse, für die Caddy das Zertifikat holt |
| `INHALT` | `platzhalter` \| `app` | statische Seite oder Next.js-Web. `app`, sobald die Landingpage (#58) auf main ist |
| `KIC_ONLINE_FRAGEN` | leer \| `1` | `1` öffnet nur die Fragen (`/api/uc4/frage`; `/api/uc3/frage` ab dem UC3-Teil in !92). Freigaben, Läufe, UC2-Fälle und Voice bleiben zu |
| `UC4_KETTE` | `uc3` (Standard, auch wenn leer) \| Komma-Liste | Stationen auf `/uc4`. `uc3` fragt nur die Zahl, ohne Modell. Stufe B setzt `uc3,uc2,uc1` ausdrücklich; ein ungültiger Wert heißt wieder nur `uc3` |
| `UC4_MODELLWAHL` | leer \| z. B. `azure` | Anbieter, die man auf `/uc4` wählen darf. Leer: nur Testbetrieb |
| `RATENLIMIT_PRO_MINUTE` | Zahl ab 1 | Fragen je IP und Minute, Standard 10 |
| `UC2_NAMENSLISTE` | leer \| absoluter Pfad auf dem Server | Namensliste für den echten UC2-Presse-Index, schreibgeschützt nach `/etc/kic/uc2-namensliste` gemountet. Leer: UC2 zeigt gekennzeichnete Beispielbelege |

**Stufe A, Fragen ohne Modell:** `KIC_ONLINE_FRAGEN=1`, `UC4_KETTE=uc3`, kein Modellschlüssel. Die Zahl kommt aus
der Datenbank `statistik` (gerechnete Läufe mit Regelsatz v1 nötig), kein Modellaufruf, das Tagesbudget wird nicht
verbraucht. **Stufe B, mit Modell:** zusätzlich `UC4_KETTE=uc3,uc2,uc1`, `LLM_PROVIDER=azure` mit den
`AZURE_*`-Schlüsseln, `UC4_MODELLWAHL=azure` und ein bewusst gesetztes `LLM_TAGESBUDGET_AUFRUFE`. Bedingung der
Review-Bank: Stufe B erst, wenn das Tagesbudget atomar reserviert (heute kann es bei gleichzeitigen Aufrufen um
einige Aufrufe überschritten werden).

Umschalten: Zeile in `.env.server` ändern, dann `scripts/deploy.sh up && scripts/deploy.sh pruefen`. Ein anderer Wert
für `INHALT` lässt Caddy nicht starten (fail-closed). Ein ungültiges `UC4_KETTE` fällt auf `uc3` zurück, ein
ungültiges `RATENLIMIT_PRO_MINUTE` auf 10.

## Daten

UC-Datenbanken kommen als `pg_dump -Fc` (`.dump`) oder als SQL mit `pg_dump --clean --if-exists --no-owner
--no-privileges` (`.sql.gz`) nach `<basis>/daten/`, dann `scripts/deploy.sh daten <db> <datei>`. Vor dem Einspielen
sichert `daten` die Datenbank (`sichern`); scheitert die Sicherung, wird nichts eingespielt. Eine `.sql.gz` muss
`gzip -t` bestehen, und das `commit` folgt nur, wenn gzip bis zum Ende gelesen hat. Liegt neben der Datei eine
`.sha256` (so bei jeder Sicherung), muss sie stimmen.
Gegenprobe: `scripts/deploy.sh inhaltshash <db> <schema>` auf dem Server und lokal
`psql -X -q -At -v schema=<schema> -f deploy/sql/inhaltshash.sql` müssen dieselbe GESAMT-Zeile liefern.
Gemessen 05.11.2026: UC2 (`healthpolicy`, Schema `uc2`) lokal und online `GESAMT 10897 3806efa2…`.

## CI

- `deploy-check` (MR-Pipelines, wenn `deploy/`, `scripts/deploy.sh` oder `.gitlab-ci.yml` sich ändern): shellcheck,
  `docker compose config` und `caddy validate` für beide Werte von `INHALT`, mit Dummy-Werten.
- `deploy` (manuell, nur in einer Web-Pipeline auf main): `scripts/deploy.sh up` und `pruefen`. SSH-Schlüssel und
  Hostschlüssel liegen als geschützte Projektvariablen, der Schlüssel steht auf dem Server mit `restrict`.

## Sicherung

`scripts/deploy.sh sichern` schreibt je App-Datenbank einen `pg_dump -Fc` nach `<basis>/daten/sicherung/<db>-<UTC>.dump`
und eine `.sha256` daneben. Die Datei wird erst als `.teil` geschrieben, mit `pg_restore -f /dev/null` ganz gelesen
(jeder Datenblock) und dann ohne Überschreiben umbenannt. Eine Sicherung läuft zur Zeit (Sperre `<basis>/.sichern.lock`).
`sichern` behält je Datenbank die letzten fünf. `daten` prüft erst die Datei (vorhanden, `gzip -t`, `.sha256`), sichert
dann von selbst und räumt dabei nichts weg, damit Fehlversuche keine älteren Stände verdrängen. Die Online-Daten
sind Kopien (die Quellen liegen lokal und auf dem Rechen-Rechner), die Sicherung ist der schnelle Rückweg, kein Archiv.

## Rückweg

Älteren Stand ausliefern: `git checkout <commit>`, dann `scripts/deploy.sh up`, danach zurück auf den Branch.
Datenbank zurück: `scripts/deploy.sh daten <db> sicherung/<db>-<UTC>.dump` (sichert vorher den aktuellen Stand).
Seite vom Netz nehmen: auf dem Server in `<basis>/repo/deploy`
`docker compose --env-file ../../.env.server -f docker-compose.prod.yml down` (Volumes bleiben).

## Sicherheit

- Nur Caddy veröffentlicht Ports (TCP 80/443). Docker umgeht Host-Firewalls, deshalb haben db und app kein `ports:`.
- Caddy läuft mit `cap_drop: ALL` plus `NET_BIND_SERVICE`, `no-new-privileges`, schreibgeschütztem Dateisystem und
  Healthcheck; app ohne Capabilities als Nutzer `app`, schreibgeschützt (tmpfs nur `/tmp` und `.next/cache`), Code
  gehört root. Basis-Images der Deploy-Teile per Digest gepinnt (Compose, `app.Dockerfile`, CI-Jobs `deploy` und
  `deploy-check`); die übrigen CI-Jobs gehören E0.
- Build-Kontext per Positivliste (`deploy/app.Dockerfile.dockerignore`): nur Workspace-Dateien, `web/`, `shared/`, `uc*/`.
- `deploy-check` prüft Invarianten der Compose-Datei (`deploy/compose-invarianten.jq`): nur caddy mit Ports, Härtung
  vorhanden, App-URLs nur mit `kic_app`.
- Header auf jeder Antwort, auch auf Fehlerantworten: HSTS (30 Tage), `nosniff`, `X-Frame-Options DENY`, Referrer- und
  Permissions-Policy, `noindex`; strikte CSP für die Platzhalter-Seite. Kein HTTP/3.
- Lesend auf drei Ebenen: Caddy (nur GET/HEAD, dazu POST auf die zwei Frage-Wege, die die App nur mit `KIC_ONLINE_FRAGEN=1` annimmt), Datenbankrolle `kic_app` (nur SELECT, read-only), App-Image ohne git
  und ohne Repo (`plattform.freigabe` und der Protokoll-Export aus `git log` gehen online ohnehin nicht).
- Keine Modellschlüssel in `.env.server`, solange kein Ratenlimit und kein Tagesbudget steht: die Seite ist ohne
  Passwort erreichbar, Modellaufrufe kosten Geld (Lead 05.11.2026). `up` bricht vor jeder Änderung ab, wenn
  `AZURE_API_KEY`, `MISTRAL_API_KEY`, `VAPI_API_KEY` oder `VAPI_CUSTOM_LLM_KEY` gesetzt ist und
  `RATENLIMIT_PRO_MINUTE` oder `LLM_TAGESBUDGET_AUFRUFE` keine ganze Zahl ab 1 ist (#108b).
- Tagesbudget ist Pflicht (#100): ohne `LLM_TAGESBUDGET_AUFRUFE` (ganze Zahl ab 1) in `.env.server` bricht
  `docker compose` ab. Die App setzt `KIC_ONLINE=1`; damit ruft `plattform.llm` ohne Budget kein echtes Modell.
  Gezählt wird im Modellprotokoll. Es liegt im Volume `app_protokoll` unter `/app/var/protokoll/` (Variable
  `PLATTFORM_PROTOKOLL`, Standard `/app/var/protokoll/modellaufrufe.jsonl`), dem einzigen beschreibbaren Ort im
  `read_only`-Container. Ist es nicht beschreibbar, lehnt `plattform.llm` jeden Aufruf ab.
- Voice (Vapi) braucht POST auf `/chat/completions` und `/vapi/webhook`. Soll Voice online gehen, bekommen genau diese
  Pfade eine Ausnahme vom GET/HEAD-Matcher; geschützt bleiben sie über Bearer-Schlüssel und Webhook-Secret im Router
  (Vertrag V im PRD E0).
