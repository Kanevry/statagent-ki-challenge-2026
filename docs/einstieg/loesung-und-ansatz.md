# Lösung und Ansatz, Langfassung

Diese Seite ist die Langfassung des Abschnitts „Lösung und Ansatz“ aus dem README.
Sie zeigt, was gebaut wurde, wie UC3 rechnet, wie ein Mensch freigibt, wohin Daten bei Voice gehen und wie die Qualität geprüft wird.

Zurück zum [README](../../README.md#lösung-und-ansatz).

Das große Bild: Das Programm macht aus jeder Monatslieferung die Statistik, ohne KI. Die KI schlägt nur Änderungen
an Regeln oder Code vor, und erst die Freigabe eines Menschen mit Namen lässt sie gelten.

Eine Plattform, drei Räume und ein gemeinsamer Einstieg. Der Grundsatz überall: **Die KI schreibt Code und Texte,
das Programm rechnet.** Jede Zahl kommt aus der Datenbank und trägt ihren Beleg. Jede Änderung an Regeln oder
Code gibt ein Mensch mit Vor- und Nachnamen frei.

## Was gebaut wurde (Stand `main`, 05.11.2026)

| Raum | Was er tut | Stand | Details |
|---|---|---|---|
| **UC3 StatAgent** (bewertet) | Statistikprozess für die synthetische Beschäftigtenstatistik: 24 Monatslieferungen einlesen, nach Regeln bereinigen, zählen, prüfen, Qualitätsbericht und Aggregations-Sheet. Eigene Agenten setzen Änderungsaufträge um, ein Mensch gibt frei. | Gebaut. Die Seiten unter `/uc3` zeigen Läufe, Berichte, Klassifikationen, Freigaben und Datenanfragen, jede Zahl mit Beleg. | `uc3/README.md`, Ergebnisse in `abgabe/` |
| UC1 SV KI-Lotse | Hilft bei Fragen zu Gesundheit und Sozialversicherung, mit Quelle an jeder Antwort | Gebaut. Auf `/uc1` erzählt man seine Lage, der Lotse fragt bei Bedarf nach und antwortet mit einem Zitat als Beleg an jeder Aussage. Er nennt Antrag, zuständige Stelle und Termin. `/uc1?beispiel=pflege` spielt einen aufgezeichneten Fall ohne Netz ab. Online zeigt `/uc1` nur diese Aufzeichnung, der Live-Dialog läuft lokal. Der Lotse ist auch an `/uc4` angeschlossen. | `uc1/`, `docs/plan/uc1/` |
| UC2 HealthPolicy Simulator | Mehrere Akteure verhandeln politische, organisatorische und finanzielle Entscheidungen | Gebaut. Auf `/uc2` verhandeln Interessenvertretungen in Runden mit Moderator, mit Beleg aus dem Pressespiegel, wo es einen gibt; sonst ist die Haltung als Modellannahme markiert. Ein Mensch gibt das Ergebnis mit Namen frei, vorher heißt es „Entwurf“. Online zeigt `/uc2` eine aufgezeichnete Verhandlung; erfundene Beispielbelege sind dort als solche gekennzeichnet. | `uc2/README.md` |
| UC4 Gemeinsamer Einstieg | Eine Frage läuft nacheinander durch UC3, UC2 und UC1 (nicht bewertet) | Seite `/uc4`, lokal mit Modellwahl (Azure, Mistral, Claude oder Testbetrieb), online mit Azure oder Testbetrieb. UC3 liefert die Zahl, UC2 die Abwägung, UC1 die Erklärung; jede Antwort erscheint, sobald sie da ist. | `/uc4` in der App |

Ergänzt am 06.11.2026: Unter `/uc3` kamen nach dem Stand der Tabelle die Seiten `/uc3/annahmen` (Annahmen mit
Begründung), `/uc3/ergebnisse` (Excel-Dateien und Liste für das Ministerium), `/uc3/pensionen` (Pensionen je Träger)
und `/uc3/auftrag` (Auftrag an die Agenten, nur auf der Vorführ-Instanz) dazu, außerdem `/praesentation/management`.
Neu sind auch `/uc2/frage` (eigene Frage an den Simulator) und `/ablauf` (wie das Projekt entstanden ist).

Gemeinsamer Kern in `shared/`:

- **Modell-Schalter** `plattform.llm`: ein Aufruf für alle Modelle, umschaltbar per `LLM_PROVIDER`, mit
  Ausweichkette und einer Protokollzeile je Aufruf, ohne Inhalt. Ein anderes Modell ändert keine Zahl.
- **Protokoll und Freigabe** `plattform.protokoll` und `plattform.freigabe` (siehe unten).
- **Lokale Embeddings** `plattform.embeddings`: macht aus Text Zahlenreihen für die Suche, ohne Cloud
  (Modell `google/embeddinggemma-2`).
- **Voice** `plattform.voice` und der Sprechknopf `VoiceKnopf` in `@kic/ui`: Sprachzugang über Vapi, siehe
  „Datenfluss Voice“. Ein Anruf braucht ein eingerichtetes Vapi-Konto.
- **Oberfläche** `@kic/ui`: Design-Tokens, ruhige Bausteine, Herkunft-Chip an jeder Zahl („SQL ansehen“),
  Freigabe-Karte, Protokoll-Schublade, Header mit Modell-Anzeige. Diese Teile sehen in allen drei Bereichen gleich
  aus: Beleg an der Zahl, Freigabe mit Namen, sichtbares Modell.

## Wie UC3 rechnet

Zahlen entstehen nur durch SQL und Python. `uc3 lauf` ruft kein Sprachmodell auf, zwei Läufe mit denselben Daten
und Regeln liefern denselben Ergebnis-Hash (eine Prüfsumme über das ganze Ergebnis). Regeln stehen als Daten in der
Datenbank (`meta.regel`), mit Gültigkeit, Begründung und Freigabe. Ein Modell schlägt nur Änderungen vor. Die
fünf Schritte eines Laufs (bereinigen, zählen, Revisionsbedarf, prüfen, abrechnen) stehen in `uc3/README.md`.

## Freigabe durch einen Menschen

1. Ein Agent schlägt eine Änderung vor (Regel, Code-Datei, Lieferung). Der Vorschlag steht im Protokoll
   `meta.protokoll`, mit Modell und Anweisung.
2. Ein Mensch gibt in der Freigabe-Karte frei. Verlangt sind Vor- und Nachname. Rollen wie „Team“ oder
   „Admin“ und Platzhalter werden abgelehnt.
3. `plattform.freigabe` schreibt die Entscheidung nach `meta.freigabe` und legt in derselben Transaktion einen
   Git-Commit an. Der Betreff ist die Anweisung, dazu kommen die Trailer `Freigegeben-von`, `Vorschlag` und `Modell`.
4. Ein Agenten-Skript startet nur, wenn genau dieser Dateistand freigegeben ist. Eine danach geänderte Datei
   gilt als nicht freigegeben.

`uv run python -m plattform.protokoll export --md --db <URL der UC-Datenbank>` erzeugt daraus das Protokoll aus
Git-Verlauf und Datenbank (Datei `protokoll.md`, je Use Case mit `--uc ucN`). Das fertige UC3-Protokoll liegt in
`abgabe/protokoll.md`.

## Datenfluss Voice

Voice geht über Vapi, einen **US-Dienst**. Der Ablauf, belegt in `docs/voice.md` (Abschnitt „Datenfluss Voice“):

1. Der Browser verbindet sich mit Vapi. Vapi erhält das **Audio** der Frage, schreibt es zu Text um und schickt das
   **Transkript** an unseren Server.
2. Unser Server antwortet mit seiner eigenen `antwort`-Funktion. Die Zahlen rechnet der Code aus der Datenbank,
   kein Sprachmodell. **Aus der Datenbank gehen nur Summen mit Beleg hinaus**, keine Einzeldaten, und SQL wird nicht
   gesprochen. Was jemand ins Mikrofon sagt, geht als Ton und Text an Vapi.
3. Die Aufnahme ist aus: `recordingEnabled` steht im Assistant auf `False`
   (`shared/py/plattform/voice/assistant.py`, Zeilen 56 und 57). Vapi hält das Transkript nach eigenen Regeln.
   Dort landen die gesprochene Frage und die Antwort mit Aggregat und Beleg.
4. Für Transkription und Stimme trägt der Assistant die Dienste Deepgram (`nova-2`) und Azure (`de-AT-IngridNeural`)
   ein (`assistant.py`, Zeilen 54 und 55). Sie laufen über Vapi.
5. Bei uns bleibt je Anruf eine Protokollzeile: Hash der Anruf-Kennung, Dauer, Endgrund. Kein Transkript, keine
   Antwort.

**Der Text bleibt der Hauptweg.** Dieselbe `antwort`-Funktion beantwortet Fragen auch über ein Textfeld, ohne dass
Daten an Vapi gehen. Ohne öffentliche Adresse (`PUBLIC_URL` leer) erreicht Vapi den Server gar nicht.

## Qualitätssicherung

Jeder Merge Request durchläuft die CI: Secret-Scan, ruff, mypy, pytest, TypeScript-Prüfung, ESLint, Vitest, ein
Produktions-Build der App und Browser-Tests mit Playwright auf Desktop und Mobil. Dazu gehören:

- ein **Anti-Schablonen-Gate**: Es misst jede Seite gegen zwölf Muster generischer, maschinell zusammengesetzter
  Oberflächen und verlangt 0 Treffer (`docs/design.md`).
- eine **Prüfung der Barrierefreiheit** mit axe (WCAG 2.1 AA): Schwere Verstöße lassen die Pipeline scheitern.
- eine **gefüllte UC3-Testdatenbank** aus erfundenen Mini-Lieferungen, damit die Seiten unter `/uc3` mit Daten
  geprüft werden und nicht nur im leeren Zustand.
