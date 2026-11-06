# Vorführung am Freitag (06.11.2026): online auf einer eigenen Instanz

Die Live-Demo läuft auf dem Demo-Server unter einer eigenen Adresse mit Passwort, über den Hotspot des Vortragenden.
Die öffentliche Demo bleibt lesend und daneben unverändert. Gerechnet wird ohne Modell. Das Azure-Modell (`gpt-5-4-mini`)
rufen nur die Agenten von UC3 und die Verhandlung von UC2.
Stand 05.11.2026. Was nicht gemessen ist, steht als „nicht gemessen“.

Platzhalter: `<vorführ-adresse>` ist die Adresse der Instanz, `<dump>` eine `pg_dump -Fc`-Datei der Abgabe-DB. Zugang: Nutzer
`vorfuehrung`, Passwort `VORFUEHRUNG_ZUGANG` in der `.env.local` des Haupt-Checkouts. Beides steht nie im Repo.

## Aufbau

| Teil | Inhalt |
|---|---|
| Caddy | der öffentliche Container mit einem zweiten Site-Block aus `<basis>/vorfuehrung/caddy/`, Basic-Auth, alle Methoden |
| App | eigenes Compose-Projekt `ki-challenge-vorfuehrung`, eigenes Image mit git, ohne `KIC_ONLINE_LESEND`, mit `KIC_VORFUEHRUNG=1` |
| DB | eigener Container in eigenem Netz, `statistik_vorfuehrung` plus Vorlage. Enthält `roh` und `bereinigt`, die öffentliche App erreicht ihn nicht |
| UC1, UC2 | UC1 lesend aus der öffentlichen DB (Rolle `kic_app`). Auch UC2 liest die App dort lesend, eine Live-Verhandlung läuft über den Dienst `vorfuehrung-uc2` |
| UC2 live | Dienst `vorfuehrung-uc2`: dasselbe Image wie die App, `uvicorn uc2.api:app` auf Port 8102, kein Port nach außen, nur im eigenen Netz, schreibgeschütztes Dateisystem, 1 Kern, 768 MB. Eigene Datenbank `healthpolicy_vorfuehrung` im Container `vorfuehrung-db`. Die App erreicht ihn über `UC2_API_URL` |
| Git | eigener Checkout mit einem Commit „Ausgangsstand“, kein Remote, also kein Push. Die Freigabe committet dorthin |
| Modell | nur Azure, kein Rückfall auf Mistral: Scheitert Azure, steht das als Fehler auf der Seite. Eigenes Tagesbudget (`VORFUEHRUNG_TAGESBUDGET`, Standard 2000, Grenze je UTC-Tag), eigenes Protokoll-Volume |

Der Auftrag im Browser hält keine Anfrage offen: POST startet `uc3 agent` im Server, die Seite fragt alle 3 s den Stand ab.
Reißt das Netz kurz ab, rechnet der Auftrag weiter, und auch ein Neuladen findet ihn wieder.

## Aufsetzen (einmal, nur der Lead)

```bash
scripts/vorfuehrung.sh zugang              # legt VORFUEHRUNG_ZUGANG an, falls er fehlt; Wert wird nie ausgegeben
scripts/deploy.sh up && scripts/deploy.sh pruefen   # einmalig von main: Caddy bekommt die Import-Zeile und das Volume
scripts/vorfuehrung.sh init                # Passwort, Budget, Azure-Zugang, Caddy-Fragment (nur der Hash)
scripts/vorfuehrung.sh up <ref>            # baut den Stand, legt den Checkout an, lädt Caddy neu
scripts/vorfuehrung.sh daten <dump>        # lädt hoch, spielt die Vorlage ein, legt die Arbeitskopie an
scripts/vorfuehrung.sh pruefen             # ohne Zugang 401, mit Zugang Seiten, öffentliche Demo weiter gesperrt
```

Den Dump zieht man auf dem Rechner mit der Rechen-Datenbank aus der Abgabe-DB, die dabei nur gelesen wird:
`docker exec statagent-db pg_dump -U statistik -d statistik -Fc -Z 4 > <dump>`. Ein neuer Stand: `up <ref>`, danach `reset`.

## Ablauf Freitag früh (05:57 bis 07:00)

Die Reihenfolge zählt, weil `daten` Vorlage und Arbeitskopie ersetzt und `reset` jede spätere Freigabe zurücknimmt.
`statistik` wird dabei nur gelesen und bekommt die Pensionen bis nach 09:00 nicht. Server-Schritte startet nur der Lead.

1. **Ab 05:57, neuer Dump mit Pensionen, nach den letzten Läufen.** Auf dem Rechner mit der Rechen-Datenbank, mit einem
   Code-Stand ab MR 214:
   ```bash
   scripts/vorfuehrung-db.sh --ersetzen statistik statistik_vorfuehrung_pensionen
   # mit UC3_DATABASE_URL auf diese Kopie und gesetztem STATAGENT_STARTPAKET:
   uv run uc3 db init && uv run uc3 pensionen laden && uv run uc3 pensionen pruefen
   # tiefe Klassifikationen (ÖNACE bis 5-Steller, Bezirk, Gemeinde); eine Transaktion, ein Fehler lässt alles, wie es war
   { echo 'begin;'; gunzip -c <klass-datei>; echo 'commit;'; } | psql "<kopie>" -X -q -v ON_ERROR_STOP=1
   docker exec statagent-db pg_dump -U statistik -Fc -d statistik_vorfuehrung_pensionen > <dump>
   psql "<kopie>" -X -q -At -v schema=stat -f deploy/sql/inhaltshash.sql | grep GESAMT   # dasselbe für meta, beide notieren
   ```
   Probe am 05.11. mit einem Zwischenstand von MR 214: 2 min 33 s bis zum fertigen Dump, 457 MB.
   Die Klassifikations-Datei lief auf einer Wegwerf-Kopie in 1 s, ein zweites Mal ohne Änderung; `meta` bleibt gleich, `stat` bekommt
   einen neuen Hash. Darum gelten nur die GESAMT-Zeilen dieses Schritts als Vergleich für `daten`, keine älteren.
2. **Stand und Daten auf den Server.** `scripts/vorfuehrung.sh up <ref>` mit dem Stand, der vorgeführt wird, dann
   `scripts/vorfuehrung.sh daten <dump>`. `daten` gibt die GESAMT-Zeilen aus, sie müssen denen aus Schritt 1 gleichen.
3. **Probe.** `scripts/vorfuehrung.sh pruefen`, danach einmal D1 bis D4 im Browser, dann `scripts/vorfuehrung.sh reset`.
4. **07:00, Freigabe.** Der Owner gibt die Pensionen mit seinem Namen frei, bis dahin steht dort „vorläufig“:
   `scripts/vorfuehrung.sh pensionen-freigeben "<Vor- und Nachname>"`. Der Befehl läuft in der App, der Commit landet im Checkout.
5. **Direkt danach:** `scripts/vorfuehrung.sh festschreiben`. Keine Probe dazwischen, sonst wird sie mit festgeschrieben.
6. **Gegenprobe.** `scripts/vorfuehrung.sh reset`. Der Beleg ist die Freigabe, die danach noch auf der Seite steht; die Meldung
   „0 Commits“ gilt immer. Das ist der Stand für die Vorführung um 09:00.

### Dieselbe Folge ohne Rechen-Datenbank

Plan für Fr 05:57, solange der Rechner mit der Rechen-Datenbank nicht erreichbar ist (seit 06.11. 00:35). Schritt 1 entfällt. Die
Vorlage auf dem Server bleibt, sie enthält den letzten eingespielten Dump samt Pensionen, und der liegt auch noch auf dem Server.

**Einschränkung:** Der Stand von `statistik` ist damit nur bis etwa 23:00 am 05.11. belegt. Was sich seither dort geändert hat, fehlt
in der Vorführung und ist nicht messbar, das gehört am Tisch nicht behauptet. Die Abgabe selbst berührt das nicht.

1. `scripts/vorfuehrung.sh up <ref>`: Volume und Vorlage bleiben, der Checkout entsteht neu.
2. `scripts/vorfuehrung.sh reset`, dann `scripts/vorfuehrung.sh klassifikationen <klass-datei>` und `scripts/vorfuehrung.sh
   festschreiben`, damit die Vorlage sie behält. Ohne die Datei entfällt das, und die tiefen Klassifikationen fehlen.
3. Probe wie oben, dann `reset`, Freigabe 07:00, `festschreiben`, Gegenprobe.

## Vorführen

1. Hotspot an, `<vorführ-adresse>` öffnen, Nutzer und Passwort eingeben.
2. **D1 Lauf und Bericht, vor D2:** `/uc3/auftrag`, unten einen Monat rechnen, dann „Monat und Qualitätsbericht ansehen“.
3. **D2 Live-Änderung:** `/uc3/auftrag`, Satz tippen, Monat für die Zahlen wählen, „Vorschlag schreiben lassen“. Danach „Vorher
   und nachher ansehen“, Name eintragen, freigeben. Die Seite nennt den Commit. Rücknahme: neuer Auftrag „Nimm Vorschlag <n>
   zurück“, wieder freigeben.
4. **D3 Datenanfragen:** `/uc3/fragen`. Eine Frage braucht rund 3 s. Höchstens zwei rechnen gleichzeitig, also die Antwort abwarten:
   Die dritte Frage innerhalb dieser 3 s bekommt „Gerade rechnet das Programm schon zwei Fragen“.
5. **D4 Gemeinsamer Einstieg:** `/uc4`.
6. **UC2 live:** `/uc2`, „Neu verhandeln lassen, mit Modell“. Eine Verhandlung dauert rund fünf Minuten, die Runden erscheinen
   laufend. Am Ende Vor- und Nachname eintragen und freigeben. Während des Laufs geht kein zweiter Start: Er bekommt „Es läuft
   schon eine Verhandlung.“

Die Zahlen nachher kommen in der Vorführung aus der Probe auf dem Vorschlag. Ein neuer Regelsatz rechnet Monate nur in
zeitlicher Reihenfolge ab dem ersten Monat, alle 24 sind live nicht machbar; die Seite bietet deshalb nur rechenbare Monate an.
Nicht jeder Auftrag ändert in jedem Monat eine Zahl: Der Auftrag zum Geburtsmonat 13 wirkt nur in Jänner bis Juni, im Juli 2026
ändert er keine. Für ihn Juni 2026 wählen (Gesamtzahl gleich, die Altersgruppen verschieben sich um wenige Personen, gemessen in
der Lane Live-Änderung).

## UC2 live

Stand 06.11.2026. Auf `/uc2` lässt sich hier eine echte Verhandlung starten, statt nur die Aufzeichnung zu lesen. Die
öffentliche Demo bleibt lesend und zeigt weiter nur die Aufzeichnung. Starten ist dort gesperrt.

- **Modell:** Der Knopf schickt den Anbieter `azure` mit (`UC2_START_PROVIDER`). Es antwortet `gpt-5-4-mini`, ohne Rückfall
  auf ein anderes Modell.
- **Schutz:** Höchstens eine Verhandlung gleichzeitig und höchstens ein Start je Minute. Dazu kommt ein eigenes Tageslimit von
  300 Modellaufrufen (`VORFUEHRUNG_UC2_TAGESBUDGET`), getrennt vom Budget der UC3-Agenten, Grenze je UTC-Tag. Das reicht für rund
  acht Verhandlungen am Tag. Ist es erreicht, steht auf der Seite „Heute sind keine neuen Live-Verhandlungen mehr möglich. Die
  aufgezeichnete Verhandlung bleibt.“
- **Belege:** Live nutzt die Verhandlung nur erfundene Beispielbelege, keine Pressetexte. Die Seite kennzeichnet sie am Beleg
  („Beleg (erfundene Beispielquelle): …“) und im Satz unter der Verhandlung („Die Belege sind erfundene Beispiele.“).
- **Namensschutz:** Texte, die das Modell schreibt, laufen vor dem Speichern durch die Namensliste. Ohne Namensliste startet
  kein echtes Modell.
- **Freigabe:** Am Ende gibt ein Mensch das Ergebnis mit Vor- und Nachnamen frei. Gespeichert wird der Name. Nach dem Neuladen
  zeigt die Seite nur „Freigegeben am <Zeit>“. Die Instanz gilt als online und liefert dann keine Namen aus.
- **Daten:** Die Verhandlungen liegen in der eigenen Datenbank `healthpolicy_vorfuehrung`. `up` legt sie an, falls sie fehlt,
  und startet danach den Dienst in einem eigenen Schritt. `reset`, `daten` und `festschreiben` berühren Dienst und Datenbank
  nicht. Gespeicherte Verhandlungen bleiben also über ein `reset` hinweg.
- **Rückfall:** Scheitert dieser Schritt bei `up`, läuft die Instanz weiter, und `/uc2` zeigt die Aufzeichnung.

Prüfen nach `up`: `scripts/vorfuehrung.sh status` zeigt den Dienst `vorfuehrung-uc2`. `scripts/vorfuehrung.sh pruefen` meldet
„pruefen: UC2 live (Dienst erreichbar)“ oder „pruefen: UC2 zeigt die Aufzeichnung (Dienst nicht erreichbar)“. Die zweite
Meldung ist kein Fehler des Befehls. Sie heißt nur, dass `/uc2` die Aufzeichnung zeigt.

## Zurück auf den Ausgangsstand

```bash
scripts/vorfuehrung.sh reset
```

Neue Arbeitskopie aus der Vorlage, Freigabe-Commits weg, App neu gestartet, auch ein laufender Auftrag endet damit. Jede Probe
eines Auftrags hinterlässt tote Zeilen (auf einer Kopie nach rund 100 Proben 23 statt 8 GB, Lane Live-Änderung), deshalb direkt vor
der Vorführung immer `reset`. Die Vorlage bleibt dabei sauber, die Platte zeigt `status`. Die Vorlage
und das Tagesbudget bleiben. Danach kann die Vorführung noch einmal laufen, etwa 09:00 und später fürs Management.

Eine Freigabe, die bleiben soll (die Pensionen, Fr 07:00), würde `reset` mit zurücknehmen. Deshalb direkt danach:

```bash
scripts/vorfuehrung.sh festschreiben   # heutiger Stand wird Vorlage, der Commit gehört zum neuen Ausgangsstand
```

Das ersetzt die Vorlage. Zurück geht es nur mit `daten <dump>`. Also nur auf einem geprüften Stand, nie nach einer Probe.
Ein späteres `up` behält den Checkout samt Freigabe-Commit; `uc3 pensionen freigeben` ließe sich auch gar nicht wiederholen. Neu legt
ihn nur `up <ref> --checkout-neu` an, dann ist der Commit weg, die Freigabe in der Datenbank bleibt.
Bricht `daten`, `reset` oder `festschreiben` mitten ab, startet das Skript die App wieder; danach den Befehl wiederholen.

## Messungen

Gemessen am 05.11.2026 auf der echten Adresse im Browser, mit dem Stand aus MR 229. Freigaben mit einem Probe-Namen, vor jedem
Durchlauf `reset`.

| Messung | Durchlauf 1 (23:00) | Durchlauf 2 (23:06, gedrosselt) |
|---|---|---|
| Ganzer Durchlauf D1 bis D4 | 349,7 s | 358,3 s |
| Seite `/uc3` | 1,8 s | 1,8 s |
| D1 Lauf Oktober 2025 | 101,2 s | 96,2 s |
| D1 Monatsseite | 0,7 s | 0,6 s |
| D2 Vorschlag (Geburtsmonat 13, Juni 2026) | 144,6 s | 147,6 s |
| D2 Freigabe mit Name | 3,1 s | 5,8 s |
| D2 Rücknahme, Vorschlag | 85,7 s | 90,8 s |
| D2 Rücknahme, Freigabe | 2,3 s | 3,7 s |
| D3 Datenanfrage (7.498) | 5,0 s | 5,8 s |
| D4 `/uc4` | 4,3 s | 4,6 s |

Gedrosselt heißt: 4 Mbit/s herunter, 1 Mbit/s hinauf, 150 ms im Browser. Beide Durchläufe liefen ohne Fehler und ohne Abriss.
Das ersetzt keine Messung über einen echten Hotspot, die steht aus und liegt bei der Probe um 07:00.

| Weitere Messung | Ergebnis |
|---|---|
| Durchlauf auf dem Endstand der Nacht (06.11. 03:08 bis 03:15, Auftrag „Beamte zählen nicht mehr mit“) | 387,7 s ohne Fehler; Vorschlag 164,9 s, Freigabe 3,7 s, Rücknahme 97,8 s und 2,5 s; Beamte 12.289 zu 0, Gesamt 407.604 zu 395.315 |
| 25 Fragen hintereinander (Limit der Instanz) | ohne Fehler |
| Lauf Oktober 2025 gegen die Rechen-Datenbank | gleich: 397.514, Hash `63f106818887` |
| Reset | 51 bis 53 s, fünfmal |
| Erster Monat auf einem neuen Regelsatz (2024-08) | 41 s |
| Basisregelsatz von `uc3 agent` | v2, Ziel v3, nach Rücknahme Ziel v4 |
| App-Neustart nach einer Freigabe, dann ein Lauf | läuft; ein Code-Vorschlag ist dabei nicht geprüft |
| Generalprobe `up`, `daten`, `pensionen-freigeben`, `festschreiben`, `reset`, zurück mit `daten` (23:34 bis 23:46) | bestanden: Hashes gleich, `festschreiben` 53 s, `reset` 51 s, Freigabe danach noch auf der Seite, nach `daten` wieder „vorläufig“ |
| Folge ohne Rechen-Datenbank (06.11. 00:49 bis 00:54) | bestanden: `up`, `reset`, `klassifikationen`, `festschreiben` 53 s, `reset`, `pruefen`; danach Inhalts-Hash `stat` wie auf der Probe-Kopie, Regelstände v1, v2 und `ministerium` gleich dem Soll |
| Lauf Oktober 2025 mit den tiefen Klassifikationen | `unveraendert`, 397.514, Hash `63f106818887` |
| Ratenlimit vor der Änderung | sechs Fragen hintereinander 200, je rund 3 s; die elfte in einer Minute 429 |
| UC2-Verhandlung per CLI auf einem zweiten Rechner, nicht auf der Instanz (06.11., sechs Gruppen, fünf Runden, Azure `gpt-5-4-mini`) | 321 s, 37 Modellaufrufe, Status `fertig` |

## Reserve: lokal

Fällt der Server aus, läuft dieselbe App auf dem Vortragsrechner, Azure weiter über den Hotspot. Das ist auch der Weg, den
die Aufgabenstellung vorgibt (Regel 2, eigenes Gerät) und den andere nachbauen können: `uc3/README.md`.

Vorbereiten, solange das Netz gut ist: ein Worktree auf dem vorgeführten Stand mit Link auf die `.env.local`,
`pnpm install --frozen-lockfile && uv sync --all-packages`, dazu `statistik_vorfuehrung` lokal aus `<dump>`
(`createdb`, dann `pg_restore --no-owner --no-privileges`).

```bash
export UC3_DATABASE_URL=<lokale Verbindung>/statistik_vorfuehrung KIC_VORFUEHRUNG=1 LLM_PROVIDER=azure
pnpm dev   # App auf http://127.0.0.1:3000
```

`web` startet mit `dotenv -o`: Ein Schlüssel aus `.env.local` überschreibt das `export`, also dort prüfen, dass
`UC3_DATABASE_URL` nicht gesetzt ist. Die Freigabe committet hier in den Worktree, deshalb ein eigener Demo-Branch ohne Push.

Befehle auf dem Zweitrechner gemessen, auf dem Vortragsrechner nicht gemessen. Ob der Vortragsrechner das trägt, ist damit offen; für einen
Server-Ausfall am Tisch gilt das Backup-Video.

Gemessen am 05.11.2026, Dump mit Pensionen, `vorfuehrung/stand`:

| Schritt | Ergebnis |
|---|---|
| Einspielen und `analyze` | 77 s und 5 s, Inhalts-Hashes von `stat` und `meta` gleich wie auf dem Server |
| App antwortet | 5 s, alle Seiten 200 |
| Auftrag „Beamte zählen nicht mehr mit“, Azure | Vorschlag nach 92 s, neue Regel `R8_beamte_ausschluss` |
| Freigabe mit Probe-Namen | Commit mit Trailer im Worktree, kein Push |
| Datenanfrage | 2 s, 7.498, gleich wie auf dem Server |

