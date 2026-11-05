# UC1 KI-Lotse: Spikes (#28)

Stand 2026-11-05, Rechner A (M4, Demo-Rechner), pypdf 6.21.4, cloudflared (Homebrew).
Skripte unter `uc1/spikes/`, Befehle aus `uc1/`. Temporäre Dateien lagen unter `/tmp/b-uc1-spikes/`, PDFs
kommen nicht ins Repo.

## Spike 2: Formularfelder (pypdf)

**Ziel:** Feldmetadaten beider Antragsformulare lesen und klären, ob das Vorausfüllen mit pypdf trägt.

**Befehle** (2026-11-05 13:08 CET, M4):

```sh
UC1_DATA_DIR=…/svbox/uc1 uv run python spikes/formularfelder.py   # -> uc1/formulare/*.felder.roh.json
UC1_DATA_DIR=…/svbox/uc1 uv run python spikes/schreibprobe.py     # Kopien unter /tmp/b-uc1-spikes/
```

**Messwerte, Feldzählung** (Endfelder; ein Feld kann mehrere Widgets haben):

| Formular | Seiten | Text `/Tx` | Knopf `/Btn` | Auswahl `/Ch` | Required | ReadOnly | Widgets | Tooltip `/TU` | MaxLen |
|---|---|---|---|---|---|---|---|---|---|
| PAL080 (`PAL080_0125_Mpfl_052026.pdf`) | 8 | 63 | 34 | 0 | 0 | 0 | 136 | 51 | 61 |
| Kur/Reha (`Antrag Kur und Reha.pdf`) | 2 | 46 | 45 | 0 | 0 | 0 | 116 | 0 | 42 |

Die Plan-Erwartung (63/34, 46/45, 0 Required) trifft genau. `get_fields()` liefert je Formular 5 Einträge
mehr (102 bzw. 96): das sind Eltern-Knoten ohne `/FT`, keine Felder. Felder liegen bei PAL080 nur auf
den Seiten 1 bis 4, die Seiten 5 bis 8 haben keine. Kein XFA, `NeedAppearances` im Original nicht gesetzt,
kein `/Encrypt`.

**Messwerte, Schreibprobe:** je Formular 2 Textfelder, 1 Checkbox und zusätzlich 1 Knopfgruppe mit
erfundenen Werten („Erika Musterfrau“, „01.01.1950“).

| Prüfung | PAL080 | Kur/Reha |
|---|---|---|
| Textwerte in `get_fields()` | ja (2/2) | ja (2/2) |
| Textwerte in `pdftotext -layout` sichtbar | ja (2/2) | ja (2/2) |
| Checkbox `/V` und `/AS` gesetzt | `/ja`, `/ja` | `/n`, `/n` |
| Knopfgruppe (mehrere Widgets) | `Antrag Pflg=/02`, `/AS` = Off, `/02`, Off | `Geschlecht=/w`, `/AS` = Off, `/w` |
| `NeedAppearances` nach dem Schreiben | true | true |
| unbekannter Feldname | still ignoriert: keine Ausnahme, keine Warnung, kein Log, kein neues Feld | ebenso |

**Machbar: ja.** pypdf `update_page_form_field_values(None, werte, auto_regenerate=True)` füllt beide
Formulare. pypdf erzeugt die Appearance-Streams der Textfelder selbst, darum sieht auch poppler
(`pdftotext`) die Werte.

**Stolpersteine und Folgerungen für #32 (Antrag):**

- **Feldnamen-Schema:** Die Namen sind von Hand vergeben und uneinheitlich, etwa `Fam.Name`, `VSNR_1`,
  `Versicherte(r) beschäftigt` oder `zuständiger SV-träger`. Ein Punkt im Namen ist echte Hierarchie:
  Eltern-Knoten `Fam`, Kind `Name`. Bei `körperl. Einschränkung` beginnt der Kindname mit einem
  Leerzeichen. #32 braucht eine versionierte Zuordnung „fachlicher Schlüssel → voller Feldname“ je
  Formularversion. Die Roh-JSONs sind die Grundlage dafür. Der Dateiname trägt die Version (`_0125_…_052026`).
- **Unbekannte Namen:** pypdf ignoriert sie still. #32 prüft vor dem Füllen jeden Schlüssel gegen
  `get_fields()` und bricht bei einem Treffer außerhalb mit einem Fehler ab.
- **MaxLen wird nicht erzwungen:** `VSNR_2` (MaxLen 10) nahm 16 Zeichen an, ohne Meldung. 61 bzw. 42
  Textfelder haben eine MaxLen. Die Prüfung gehört in #32.
- **Knöpfe:** Alle Knöpfe sind Checkboxen. Radio-Flags gibt es keine, Gruppen entstehen nur über mehrere
  Widgets mit verschiedenen Export-Werten (`/01`,`/02`, …, `/j`,`/n`, `/m`,`/w`). Zu setzen ist der
  Export-Wert, nicht `true` oder `"Ja"`. Die erlaubten Werte stehen je Feld in `export_werte`.
- **Mehrfach-Widgets:** `VSNR_1` hat in PAL080 4 Widgets auf den Seiten 1 bis 4. Einmal füllen reicht,
  der Wert erscheint auf jeder Seite.
- **Komprimierte Objekt-Streams:** Die Originale haben `/ObjStm` (PAL080 17, Kur/Reha 8). Für pypdf ist
  das kein Problem. Die Kopie schreibt pypdf ohne Objekt-Streams.
- **Tooltips:** Nur PAL080 hat welche (51 von 97). Für Kur/Reha muss die fachliche Bedeutung von Hand
  zugeordnet werden.
- **Offen:** Ob Acrobat oder Vorschau.app die von pypdf erzeugten Appearances gleich darstellen, ist nicht
  geprüft. Geprüft wurden nur pypdf und poppler.

## Spike 1: Tunnel und Custom-LLM-Endpunkt (ohne Vapi)

**Ziel:** Trägt ein cloudflared-Quick-Tunnel einen OpenAI-kompatiblen SSE-Endpunkt mit Bearer-Token, und
wie schnell ist er?

**Befehle** (Tunnel offen von 2026-11-05 13:10:33 bis 13:13:15 CET, M4; das Token wurde mit
`secrets.token_urlsafe` zur Laufzeit erzeugt und nach der Messung gelöscht):

```sh
TUNNEL_ECHO_TOKEN=… .venv/bin/python spikes/tunnel_echo.py --port 8199 &
cloudflared tunnel --url http://127.0.0.1:8199 --no-autoupdate > /tmp/b-uc1-spikes/cloudflared.log 2>&1 &
# 10x: curl -s -N -o /dev/null -w '%{time_connect} %{time_starttransfer} %{time_total}\n' \
#      -K <cfg mit Bearer> -H 'Content-Type: application/json' -d @body.json <url>/chat/completions
```

**Messwerte** (je n=10, Perzentil nach Nearest Rank):

| Weg | connect p50 | TTFB p50 | TTFB p95 | gesamt p50 | gesamt p95 |
|---|---|---|---|---|---|
| lokal `http://127.0.0.1:8199` (M4, 13:10:51) | 0,2 ms | 0,4 ms | 0,6 ms | 0,5 ms | 0,6 ms |
| Tunnel `https://…trycloudflare.com` vom M4 (13:12:38, Edge `vie05`) | 24,6 ms | 149,0 ms | 242,3 ms | 151,7 ms | 244,6 ms |

Funktion über den Tunnel: Der Stream kommt vollständig an (4 `data:`-Chunks und `data: [DONE]`). Ohne
Token kommt 401, mit GET 404. Für `POST /upload` kam beim ersten Lauf **400 von Cloudflare** statt 404.
Ursache: Der Echo-Server ließ den Request-Body bei der 404 ungelesen, cloudflared verwendet die
Keep-alive-Verbindung weiter, und der Body-Rest verdarb die nächste Anfrage. Nach der Korrektur (die
Verbindung wird nach Fehlerantworten geschlossen) kam zweimal 404, danach wieder 200 und 401.

**Nicht gemessen: von m5.** Jede ssh-Form, die das Wegwerf-Token nach m5 bringt, ohne es in der
Befehlszeile zu zeigen, wurde vom Grenz-Hook abgewiesen: stdin-Umleitung, lokale Skriptdatei, Heredoc und
`-K` mit Pfad auf m5. Ein einfacher ssh-Inline-Befehl ging durch. Die Messung vom M4 über die öffentliche
URL läuft trotzdem über die Cloudflare-Edge (Weg Client → vie05 → cloudflared auf dem M4 → 127.0.0.1). Sie
enthält aber nicht die Netzstrecke eines zweiten Rechners.

**Machbar: ja**, mit Vorbehalt. Rund 150 ms TTFB-Aufschlag (p95 rund 245 ms) liegt weit unter der Latenz
eines LLM-Aufrufs. Für Vapi ist das tragbar. Der Wert von m5 und von Vapi selbst steht noch aus.

**Folgerungen für #34/#61 (Voice):**

- Die Quick-Tunnel-URL wechselt bei jedem Start. #61 braucht ein Startskript: Tunnel starten, URL aus dem
  Log lesen (`https://[a-z0-9-]+\.trycloudflare\.com`), die Assistent-URL bei Vapi setzen und zurücklesen,
  erst dann melden, dass alles bereit ist.
- Der Router in #61 muss den Request-Body auch bei 401/404 verwerfen oder die Verbindung schließen.
  Hinter cloudflared führt sonst Keep-alive zu fremden 400ern. FastAPI/uvicorn tut das in der Regel
  selbst, ein Test mit zwei Anfragen hintereinander über den Tunnel deckt es auf.
- Den Token-Vergleich mit `hmac.compare_digest` machen und das Token nie loggen. Der Standard-Log von
  `http.server` schrieb beim 400 den Body-Rest ins Log. Ein Log ohne Inhalte ist also aktiv herzustellen.
- Vom M4 aus war die URL beim ersten Abruf direkt nach dem Start noch leer, vermutlich wegen DNS (13:10:51).
  Knapp 2 Minuten später (13:12:38) ging sie, dazwischen gab es keinen weiteren Versuch. Das Startskript wartet, bis ein Gesundheitsabruf über die öffentliche URL gelingt.

## Spike 3: E0-Schnittstellen (festgehalten, nicht gemessen)

Laut E0-Entscheid #21 (note_269372):

- `from plattform.llm import complete, aktives_modell`. `complete(nachrichten, schema=None, stream=False,
  provider=None, zweck="")` liefert `antwort.text | antwort.json, provider, modell, dauer_ms, tokens`.
- `LLM_PROVIDER` = `azure` (Standard, gpt-5-4-mini) | `claude` (Opus 5.5 per `claude -p`) | `mistral` |
  `ollama` | `mock`.
- Route `/uc1`, Dienst `uc1.api:app` auf 127.0.0.1:8101, DB `lotse` auf PG 5433 ohne pgvector.
- Voice über `plattform.voice.erstelle_router(antwort)` mit `antwort(nachrichten, sitzung) -> {text, belege[]}`.

**Machbar: ja.** Bis E0 #54 liefert, nutzt UC1 einen Adapter mit demselben Vertrag, damit der Tausch
später nur den Import ändert.
