# Vorführung am Freitag (06.11.2026): online auf einer eigenen Instanz

Die Live-Demo läuft auf dem Demo-Server unter einer eigenen Adresse mit Passwort, über den Hotspot des Vortragenden.
Die öffentliche Demo bleibt lesend und daneben unverändert. Gerechnet wird ohne Modell, nur die Agenten rufen das
Azure-Modell (`gpt-5-4-mini`).
Stand 05.11.2026. Was nicht gemessen ist, steht als „nicht gemessen“.

Platzhalter: `<vorführ-adresse>` ist die Adresse der Instanz, `<dump>` eine `pg_dump -Fc`-Datei der Abgabe-DB. Zugang: Nutzer
`vorfuehrung`, Passwort `VORFUEHRUNG_ZUGANG` in der `.env.local` des Haupt-Checkouts. Beides steht nie im Repo.

## Aufbau

| Teil | Inhalt |
|---|---|
| Caddy | der öffentliche Container mit einem zweiten Site-Block aus `<basis>/vorfuehrung/caddy/`, Basic-Auth, alle Methoden |
| App | eigenes Compose-Projekt `ki-challenge-vorfuehrung`, eigenes Image mit git, ohne `KIC_ONLINE_LESEND`, mit `KIC_VORFUEHRUNG=1` |
| DB | eigener Container in eigenem Netz, `statistik_vorfuehrung` plus Vorlage. Enthält `roh` und `bereinigt`, die öffentliche App erreicht ihn nicht |
| UC1, UC2 | lesend aus der öffentlichen DB (Rolle `kic_app`) |
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
`docker exec statagent-db pg_dump -U statistik -d statistik -Fc -Z 4 > <dump>`. Vor der Vorführung (Fr 06:00 bis 06:30, nach den
letzten Läufen) einmal neu ziehen und `daten` wiederholen. Ein neuer Stand: `up <ref>`, danach `reset`.

## Vorführen

1. Hotspot an, `<vorführ-adresse>` öffnen, Nutzer und Passwort eingeben.
2. **D1 Lauf und Bericht:** `/uc3/auftrag`, unten einen Monat rechnen, dann „Monat und Qualitätsbericht ansehen“.
3. **D2 Live-Änderung:** `/uc3/auftrag`, Satz tippen, „Vorschlag schreiben lassen“. Danach „Vorher und nachher ansehen“, Name
   eintragen, freigeben. Die Seite nennt den Commit. Rücknahme: neuer Auftrag „Nimm Vorschlag <n> zurück“, wieder freigeben.
4. **D3 Datenanfragen:** `/uc3/fragen`.
5. **D4 Gemeinsamer Einstieg:** `/uc4`.

## Zurück auf den Ausgangsstand

```bash
scripts/vorfuehrung.sh reset
```

Neue Arbeitskopie aus der Vorlage, Freigabe-Commits weg, App neu gestartet, auch ein laufender Auftrag endet damit. Die Vorlage
und das Tagesbudget bleiben. Danach kann die Vorführung noch einmal laufen, etwa 09:00 und später fürs Management.

Eine Freigabe, die bleiben soll (die Pensionen, Fr 07:00), würde `reset` mit zurücknehmen. Deshalb direkt danach:

```bash
scripts/vorfuehrung.sh festschreiben   # heutiger Stand wird Vorlage, der Commit gehört zum neuen Ausgangsstand
```

Das ersetzt die Vorlage. Zurück geht es nur mit `daten <dump>`. Also nur auf einem geprüften Stand, nie nach einer Probe.

## Messungen

Nicht gemessen: Die Instanz ist noch nicht aufgesetzt.

| Messung | Ergebnis |
|---|---|
| Durchlauf 1, D1 bis D4 | nicht gemessen |
| Reset | nicht gemessen |
| Durchlauf 2, D1 bis D4 | nicht gemessen |
| Seitenlast über Hotspot | nicht gemessen |
| Live-Änderung über Hotspot | nicht gemessen (`uc3 agent` mit Probe auf einer Abgabe-Kopie: 42 bis 110 s, Lane Live-Änderung) |
| Basisregelsatz von `uc3 agent` auf dem vorgeführten Stand | nicht gemessen |
| App-Neustart nach einer Freigabe, dann ein Lauf (Code-Vorschläge liegen im tmpfs, DB und Git bleiben) | nicht gemessen |

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
Einmal gemessen: nicht gemessen, folgt, sobald die Server-Instanz steht.
