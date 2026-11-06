# Feature: E3 UC2 HealthPolicy Simulator (Verhandlungsraum mit Moderator)

**Date:** 2026-11-05
**Author:** Bernhard Götzendorfer + Claude (AI-assisted planning, Steuerung: autonomous)
**Status:** Draft
**Epic:** #24 · Kinder: W1 #40 Belege, #41 Akteure, #42 Experte · W2 #43 Belegsuche, #44 Verhandlung · W3 #45 Ergebnis,
#46 Lernen, #47 Oberfläche U2-0/U2-1 · W4 #48 Abgestimmte Antwort U2-2, #49 Szenario · Abnahme #50 Owner, #51 azure
**Appetite:** Zusatz-Epic, 4 Wellen à 2–3 h mit bis zu 6 Agenten, Do 05.11. 13:30 bis Fr 06.11. 04:00 (UC2-Arbeitsende).
Projektweiter Feature-Stopp Fr 05:00 gilt auch hier. UC3 hat Vorrang, nur UC3 wird bewertet.

> **Nachtrag 05.11.2026, 13:10 (Bau-Session b-uc2, autonom entschieden, Steuerung: autonomous; Details #40 note_269666):**
> Der Owner hat um 12:5x Embeddings mit `google/embeddinggemma-2` vorgegeben. Damit sind D2 und der Ausschluss
> „Embeddings“ in § 2 Out-of-Scope ersetzt. Die Belegsuche ist hybrid: PG-Volltext `german` und Kosinus auf
> embeddinggemma-2 (768d, nur Textteil, float32). Die Relevanz wird mit `0,5^(Δ/h)` und dem Institutionsfaktor gewichtet.
> Die Vektoren liegen als `bytea` in `uc2.abschnitt`, die Ähnlichkeit rechnet numpy; pgvector wird nicht gebraucht.
> Extraktion und Korpus-Embedding laufen auf Rechner B, der Index und die Abfrage-Einbettung auf Rechner A. Der Embedder
> folgt der E0-Schnittstelle aus #67 (`einbetten(texte, zweck)`, `dimension()`). Gewichte stehen nach der
> Prototyp-Messung (09/2026) in `uc2/config/regeln.yaml`. Prüf- und Testskripte liegen unter `uc2/tests/` statt
> `tests/uc2/` (Lane `uc2/`). ollama ist seit der Owner-Vorgabe 13:0x wieder als Offline-Notnagel erlaubt (ersetzt den
> Ausschluss vom 04.11.); Standard bleibt `azure`, der Qualitätsmodus `claude`.
**Parent Project:** Monorepo `agents/ki-challenge-2026` (StatAgent; UC2 als Zusatz in `uc2/` und im UC2-Bereich von `web/`)

## 1. Problem & Motivation

### What
Ein Chat-Verhandlungsraum für gesundheitspolitische Fragen. Ein Moderator übersetzt die Frage in einen
Verhandlungsauftrag (Themen, Kriterien, Ziel), wählt bis zu 6 Akteure aus einem Pool von 14 Institutionen, führt sie
durch Runden (Position, Debatte, Verhandlung, Kompromiss), beobachtet und denkt sichtbar mit. Am Ende steht ein
abgestimmtes Verhandlungsprotokoll mit Konsens, Mehrheit, Minderheit, offenen Konflikten und Auswirkungen. Jede Haltung
ist mit Pressespiegel-Artikeln belegt, neue wiegen mehr als alte. Zahlen liefert nur der Experte, und der ist Code.
Teilergebnisse fließen in die nächste Runde, abgeschlossene Fälle als Lektionen in spätere Fälle. Positionsänderungen je
Akteur und Thema sind über die Runden sichtbar.

Vier Schichten: **Belege** (PDF → Artikel → PG-Volltext), **Akteure** (Pool und Modell je Rolle als Daten),
**Verhandlung** (Moderator, Züge, Experte, Matrix, Klassifikation, Lernen; Python-Paket `uc2` als uv-Member nach E0-Vertrag,
CLI `uv run uc2`, eigene DB `healthpolicy` auf PG 5433), **Oberfläche** (Chat nach Pen-Frames, Technik ai-elements, im UC2-Bereich von `web/`).

### Why
Owner-Auftrag Epic #24, „Fertig, wenn: Das Szenario läuft vorführbar mit Protokoll, Konsens/Mehrheit/Minderheit und
Belegen“. Der offizielle UC2-Text (`svbox/00-allgemein/text/Use Case 2 Copilot für strategische Entscheidungen V2.md`)
verlangt institutionelle Agenten, einen optionalen Moderator und ein Verhandlungsprotokoll in 8 Teilen. Die Standpunkte
sollen aus dem Pressearchiv nachvollziehbar belegt sein, ohne echte Personen zu zitieren oder darzustellen. Weiter
verlangt er Lernen aus Teilergebnissen, eine stärkere Gewichtung des Aktuellen und stichhaltige, widerspruchsfreie
Zahlen über einen eigenen Experten. Die Verhandlung und die Positionsänderungen sollen visuell dargestellt werden. UC2
zeigt, dass derselbe Kern (Modell-Schalter, Belegschicht, Protokoll, „Mensch gibt frei“) einen zweiten Use Case trägt
(Pitch „ein Kern für drei Use Cases“, #26).

### Who
- **Bediener:in:** Bernhard Götzendorfer in der Demo; im Zielbild eine Person aus der strategischen Planung des
  Dachverbands, die eine Frage stellt, die Akteurauswahl bestätigt, das Protokoll liest und mit Namen freigibt.
- **Publikum:** Fach- und Finaljury (#26), die sehen will, wer was warum vertreten hat und wie sich Positionen bewegten.

### Evidence Baseline
| Claim | Command | Result | Measured (date / SHA) |
|-------|---------|--------|-----------------------|
| Kein Code für UC2, `web/`, `shared/`, `pipeline/` in keinem Checkout | `git ls-files` in `app/` und `_wt/ki-challenge-2026/*` | nur README, CLAUDE.md, CI, `.env.example`, `.claude/personas/*`, Plan-Dokumente | 2026-11-05 12:20 @ 51341c6 |
| Kinder-Issues zu #24 fehlen | `glab issue list --label epic::e3-uc2` | nur #24 | 2026-11-05 12:20 |
| Pressespiegel: 190 PDF, 1,2 GB, 7.983 Seiten; 187 aus Jan.–Sep. 2026, **186 eindeutig** | `find svbox/uc2/Presse -iname '*.pdf' \| wc -l`; `md5 -q` | `Pressespiegel vom 03.08.2026.pdf` liegt byte-gleich in `07 Juli` und `08 August`; Ordner „2008-2019“ hat 3 Dateien (2016 Memo, 2018 Clips mit ca. 390 Zeichen/Seite, OCR nötig) | 2026-11-05 12:30 |
| 2026 sind Text-PDFs (APA-Comm, Apache FOP) | `pdfinfo`, `pdftotext -q -layout f - \| wc -c` | sauberer Text, 39 s Extraktion für alle 190 | 2026-11-05 12:30 |
| Artikelstruktur (Zählung über die 187 Dateien, Dublette 03.08. also doppelt) | `.orchestrator/runtime/uc2-plan/toc_check.py` plus Korpus-Durchlauf der Pre-Mortem-Agenten über alle 187 | Inhaltsverzeichnis 2.942 · Startzeilen `<Medium> vom TT.MM.JJJJ` 2.947 (5 in Layout-Kopien) · Feld `Quelle` 2.943 (passt in 186/187) · Feld `Sprache` 2.927 (15 Artikel ohne, v. a. Radio) · `Autor:in` 1.382; Feldblock ohne Doppelpunkt, zweispaltig; je Artikel folgt eine Layout-Kopie mit Nachbarartikeln | 2026-11-05 12:35 |
| Datum und Medium je Artikel weichen von der Ausgabe ab | Inhaltsverzeichnis 05.01.2026 | Einträge mit 04.01. und 03.01.; Medium in Startzeile und `Quelle` verschieden geschrieben | 2026-11-05 12:35 |
| Offizieller Text: 8 Protokollteile und Beispielergebnis | `grep -n '^\*\*[1-8]\. \|Wartezeitreduktion\|Budgetsteigerung' 'svbox/00-allgemein/text/Use Case 2 … V2.md'` | Zeilen 211–239: 1 Zusammenfassung der Ausgangsfrage, 2 Beteiligte Agenten, 3 Verhandlungsverlauf, 4 Konfliktanalyse, 5 Kompromissvorschläge, 6 Konsensanalyse, 7 Offene Streitpunkte, 8 Auswirkungen; Zeilen 463/465: Wartezeitreduktion 22 %, Budgetsteigerung 4,3 % | 2026-11-05 13:05 |
| Kalibrierungsdatei Gesundheitsausgaben vorhanden | `ls data/uc2/statistik_at_gesundheitsausgaben/` | `20260611Gesundheitsausgaben2025.pdf` (3 Seiten) | 2026-11-05 13:05 |
| Belege zum Thema Wartezeit je Akteur ungleich | Artikel-Zählung Alias × „Wartezeit“ (Deepen-Agent) | 280 von 2.942 Artikeln nennen Wartezeit; SV 104, Spitäler 108, Kassenärzt:innen 73, Ärztekammer 51, Wahlärzt:innen 52, Länder 55, Gesundheitsministerium 39, Public Health 10, Kammern 9, Pflege 7, Gesetzgeber 5, Finanzministerium 1, Pharma 0 | 2026-11-05 12:35 |
| Namen realer Personen stecken in Titeln, Zuschreibungen ohne Funktion („sagt <Nachname>“), Genitiven und Zitaten | `pdftotext` 02.09.2026, Muster-Zählung (Refute-Agent), **Stichprobe einer Ausgabe** | Funktion + Name 3 Treffer, Nachname-Zuschreibungen ≥ 26 | 2026-11-05 12:35 |
| Lokale PG 16.15: `german`-Volltext da; `unaccent`, `pg_trgm` nur verfügbar, nicht installiert; kein `pgvector` | `psql -p 5433 -Atc "select cfgname from pg_ts_config …; select name from pg_available_extensions …"` | bestätigt; der deutsche Stemmer faltet Umlaute (`arztekamm`) | 2026-11-05 12:24 |
| CI: `postgres:16` auf Port 5432, `LLM_PROVIDER: mock`, Job `web` prüft ganz `web/` | `.gitlab-ci.yml` | bestätigt (Datei ist Lead-Vorschlag) | 2026-11-05 @ 51341c6 |
| Chat-Bausteine lokal, Apache-2.0: `references/ai-elements` (conversation, message, sources, inline-citation, reasoning) zielt auf `ai ^6`; `references/chatbot` pinnt `ai 7.0.15` | `package.json` beider Referenzen | Versionen verschieden | 2026-11-05 12:35 |
| E0-Verträge stehen: `plattform.llm.complete(nachrichten, schema, stream, provider, zweck)`, `meta.protokoll`/`meta.freigabe` + `plattform.freigabe.freigeben()`, Lanes `web/app/uc2/**`, `web/app/api/uc2/**`, `web/components/uc2/**`, `@kic/ui`-Bausteine, je UC eigene DB auf 5433, optional FastAPI `uc2.api:app` auf 8102 | `glab api projects/:id/issues/21/notes/269372` | bestätigt; `complete()` hat keinen Parameter für Modell oder Denkaufwand | 2026-11-05 12:55 |
| UC2-Frames in Pen: `bhI7X` U2-0 Fall stellen, `f1ct2` U2-1 Panel verhandelt, `NjP7Q` U2-1a Modellfehler inline, `k3wbtm` U2-2 Abgestimmte Antwort; Bausteine `nas8Y`, `QVMco`, `NeqAs`, `CKCV4`, `FgY98`, `yK42X` | Kommentar in #24 (Präsentation) | Positionsänderungen als Balkenreihe je Persona und Runde | 2026-11-05 12:40 |
| `claude -p --bare` liest kein OAuth/Abo, nur `ANTHROPIC_API_KEY` | `claude --help` (2.1.318) | bestätigt; `ANTHROPIC_API_KEY` ist nicht gesetzt | 2026-11-05 12:35 |
| Azure-Schlüssel in `app/.env.local` leer | Quellenkarte Lead | **Hypothese** bis E0-Smoke-Test (#21) | 2026-11-05 12:30 |
| Wartezeit-Ziel hängt an der Auslastung ρ₀ | Handrechnung W ∝ ρ/(1−ρ) | für −20 % braucht es +1,25 % Kapazität bei ρ₀ = 0,95, +5 % bei 0,80, +7,5 % bei 0,70; ρ₀ ist unbelegt (Typ A) | 2026-11-05 12:35 |

## 2. Solution & Scope

### In-Scope (Must, zählt für „Fertig, wenn“)
- [ ] **S1 Pressespiegel-Index** (Modul `uc2.belege`, `uv run uc2 index`): je PDF Prüfsumme; Dubletten werden
      übersprungen und protokolliert. `pdftotext -layout`. Das Inhaltsverzeichnis ist die Liste der Artikel (Titel,
      Artikeldatum, Medium, PDF-Seite `S. N`, Zeitungsseite optional). Ein Artikel reicht von der Startzeile
      `<Medium> vom TT.MM.JJJJ` bis zum Feldblock (`Quelle` … zweispaltig, ohne Doppelpunkt) oder zur Fußzeile
      `Seite N von M`; die Layout-Kopie danach wird verworfen. Felder Medium (aus `Quelle`), Typ, Datum (aus dem
      Inhaltsverzeichnis). Die Zeile `Autor:in` wird aus dem Text entfernt und nirgends gespeichert. Artikel über ca.
      1.500 Zeichen werden in Abschnitte mit Überlappung geteilt. Institutions-Tags über `uc2/config/institutionen.yaml`.
      Erst 09/2026 als Durchstich, dann alle 186 Ausgaben. 2016/2018 bleiben draußen. Korpus und Index nie im Repo.
- [ ] **S2 Belegsuche und Personenschutz:** Spalte `tsv = to_tsvector('german'::regconfig, text)` (immutable, kein
      `unaccent`). Rang = Relevanz (hybrid: `w_v`·Kosinus embeddinggemma-2 + `w_t`·`ts_rank_cd` normiert, siehe
      Nachtrag) × `0,5^((Stichtag − Artikeldatum) / Halbwertszeit)` × Institutionsfaktor
      (1,5, wenn der Artikel die Institution des Akteurs trägt, sonst 1,0); je Akteur und Runde die besten k = 8.
      Stichtag ist Fall-Parameter (Standard 2026-09-30), Halbwertszeit 120 Tage, Faktor und k in `uc2/config/regeln.yaml`; Jänner
      wiegt dann ca. 0,2 des Septembers. **Personenschutz** auf Titel und Text, bevor etwas an ein Modell oder in die
      Anzeige geht. Funktionsmuster, Zuschreibungen („sagt/so/betont/meint/kritisiert <Name>“), Genitiv und
      Titelmuster („<Name>: …“) werden zu einer Namensliste; jeder Treffer wird zur Rolle maskiert („eine Vertreterin
      der Ärztekammer“). Die Liste liegt außerhalb des Repos. Direkte Zitate („…“) erscheinen in der Anzeige als
      „[Zitat]“. Pressetext geht als markierter, nicht vertrauenswürdiger Datenblock an das Modell.
- [ ] **S3 Akteurs-Pool und Modellrollen** (`uc2/akteure/*.md`, `uc2/config/modellrollen.yaml`): 14 Institutionen aus
      dem offiziellen Text. Format nach dem persona-panel-Konzept, neu geschrieben: Frontmatter mit id, Version, Rolle,
      Zielen, Interessen, Restriktionen, Budgetvorgaben, Prioritäten, roten Linien und Aliasen; dazu Auftrag und
      Ausgabeschema. Keine echten Personen, keine Parteien. Fehlen Belege zu einem Thema, gilt die Akteursdatei als
      „Modellannahme“ und wird so markiert.
- [ ] **S4 Experte** (Modul `uc2.experte`, `uv run uc2 experte`): deterministisches Wirkungsmodell auf 5 Jahre für
      den Maßnahmenkatalog `uc2/config/massnahmen.yaml`: zusätzliche Kassenstellen, Telemedizin-Anteil, digitale
      Facharzt-Triage, Kompetenzen Gesundheitsberufe, Öffnungszeiten, PVE. Wartezeit über Auslastung W ∝ ρ/(1−ρ),
      Mehrkosten in % der Ausgangsausgaben (aus dem Statistik-Austria-PDF in `data/uc2/`). Jede A-Annahme hat Min,
      Modus und Max (`uc2/config/annahmen.yaml`, Typ B/D/A, Quelle). Ausgabe: Wert beim Modus, Spanne aus Min/Max, die
      Annahme, die die Zielprüfung kippt („entscheidend: ρ₀“), Zielprüfung „−20 % Wartezeit, ≤ +5 % Kosten“ als
      erfüllt, nicht erfüllt oder offen.
- [ ] **S5 Verhandlungs-Laufzeit** (`uv run uc2 verhandlung --fall <id>`, Fall-IDs nur aus `uc2/faelle/`):
      - **Auftrag:** Der Moderator legt Themen (≤ 6 Vorschläge), Kriterien (Wirkung Wartezeit, Kosten, Akzeptanz,
        Umsetzbarkeit, Versorgungsqualität) und Regeln fest.
      - **Auswahl:** Er wählt ≤ 6 Akteure, zeigt je Akteur die Zahl der Belege zum Fall und begründet Auswahl und
        Nicht-Auswahl aller übrigen.
      - **Runden:** 1 Position (parallel, unabhängig), 2 Debatte, 3 Verhandlung, danach bis zu 2 Kompromissrunden.
        Abbruch nach Runde 3, wenn eine Runde keine Positionsänderung bringt, sonst nach Runde 5.
      - **Moderator denkt mit:** Je Runde schreibt er Notizen dazu. Er fordert Belege ein und meldet Widersprüche
        (Zahl ≠ Experte, Haltung ≠ Begründung).
      - **Zugschema** je Akteur und Runde (JSON):
        - `themen[]` mit Haltung −2…+2, Begründung, `beleg_ids`, Bedingungen und Zugeständnis;
        - `bezug_auf[]` mit ≥ 1 anderem Teilnehmer ab Runde 2;
        - `zahlen[]` mit Wert, Einheit und Quelle `experte` oder Beleg-ID.

      Zahlenprüfung im Feld Begründung: Das Muster `\d+([.,]\d+)?\s?(%|Prozent|Mio|Mrd|EUR|€|Tage|Stellen)` muss in
      `zahlen[]` stehen, Jahreszahlen 2000–2040 ausgenommen; sonst entsteht das Ereignis `zahl_ohne_beleg`. Eine Beleg-ID
      außerhalb der geholten Belege ergibt `beleg_ungueltig`. Wörtliche Übernahme von ≥ 8 Wörtern aus dem Beleg ergibt
      `zitat`. Ungültige Ausgabe: ein Wiederholungsversuch, dann „unverändert“ mit `ungueltige_ausgabe`.

      Genau ein Schreibprozess je Fall: `uv run uc2 verhandlung`, auch wenn die API ihn startet. Er schreibt Ereignisse
      mit fortlaufender Nummer je Fall (`seq`) in `uc2.ereignis`. Fallstatus
      `laufend|fertig|abgebrochen` mit Lebenszeichen; bei Abbruch bleiben abgeschlossene Runden erhalten.
- [ ] **S6 Positionsmatrix und Ergebnis:** Matrix Akteur × Thema × Runde; Änderung = Differenz mit Begründung des Akteurs.
      Zustimmung ≥ +1, Ablehnung ≤ −1, 0 = enthalten. Je Thema: **Konsens** alle ≥ +1; **Mehrheit** mehr als die
      Hälfte ≥ +1 (sonst kein Konsens); **abgelehnt** mehr als die Hälfte ≤ −1; sonst **offener Konflikt**.
      **Minderheit** sind bei Mehrheit die Ablehnenden, bei Ablehnung die Zustimmenden. Die Einordnung ist Code und
      erzwingt keinen Konsens. Das Protokoll hat die 8 Teile des offiziellen Texts: 1 Zusammenfassung der Ausgangsfrage, 2 Beteiligte
      Agenten, 3 Verhandlungsverlauf, 4 Konfliktanalyse, 5 Kompromissvorschläge, 6 Konsensanalyse, 7 Offene
      Streitpunkte, 8 Auswirkungen (Experte). Den Text schreibt der Moderator über diese Zahlen. Export mit
      `uc2 protokoll --format md|json`.
- [ ] **S7 Lernen:**
      - **Im Fall:** Das Zwischenergebnis jeder Runde (Einigung, gescheiterte Vorschläge, Bedingungen) steht im Kontext
        der nächsten.
      - **Über Fälle:** Nach Abschluss schreibt der Moderator je Akteur bis zu 3 Lektionen in `uc2.lektion`, mit
        Quell-Fall: welches Argument bewegt hat und woran ein Vorschlag scheiterte. Ein neuer Fall holt die 3 besten
        Lektionen je Akteur, gerankt nach Volltext × Aktualität, nur Lektionen, deren Volltext die Fallfrage trifft
        (`tsv @@ plainto_tsquery('german', frage)`). Zweiter Fall für die Prüfung: `uc2/faelle/wartezeiten-land.yaml`
        („Wie kann die fachärztliche Versorgung in ländlichen Regionen in fünf Jahren verbessert werden, ohne die
        Ausgaben um mehr als 5 % zu erhöhen?“).
      - **Verwaltung:** `uc2 lektion an|aus <id>`; Lektionen werden nie gelöscht.
- [ ] **S8 Chat-Oberfläche** (UC2-Bereich in `web/`), nach den Pen-Frames:
      - **U2-0 `bhI7X`:** Fall mit Parametern, Akteure als Haken (≤ 6), Moderator und Experte, Start.
      - **U2-1 `f1ct2`:** Je Persona die Runden mit „bewegt“/„fest“ und Herkunft-Chip `QVMco` (Medium, Monat), rechts
        die Moderator-Zusammenfassung und der Experte (Annahmen und Widersprüche gelb `NeqAs`), dazu der Verlauf.
      - **U2-1a `NjP7Q`:** Modellfehler inline, abgeschlossene Runden bleiben, „Erneut“ und Modellwechsel nur zwischen
        `azure` und `claude`.
      - **U2-2 `k3wbtm`:** Konsens/Mehrheit/Minderheit/Konflikte mit n/N, Auswirkungen als Spanne mit Annahme,
        Belegzahl, Widersprüche, „Freigeben mit Name“ (Freigabe-Karte `FgY98`, E0-Freigabe-Protokoll).
      - **Rahmen:** Header `nas8Y`, Modell-Badge `CKCV4`, Protokoll-Schublade `yK42X`.

      Einhängen nach E0: Eintrag in `shared/ui/src/ucs.ts` (Datei gehört E0, Eintrag über E0), `web/app/uc2/layout.tsx`
      mit `<UcBereich uc="uc2" nav={…}>`; Bausteine aus `@kic/ui` (HerkunftChip, WarnChip, ModellBadge, FreigabeKarte,
      ProtokollSchublade). Chat-Technik aus ai-elements (conversation, message, sources, inline-citation, reasoning) im
      Lane `web/components/uc2/`, sofern E0 ihn nicht in `@kic/ui` aufnimmt. Start und Strom über FastAPI
      `uc2.api:app` (Port 8102): `POST /faelle` (Fall-ID aus Liste, Frage im JSON-Body) startet
      `uv run uc2 verhandlung` als Unterprozess (feste argv, kein Shell, Frage per stdin) und bleibt Leser;
      `GET /faelle/{id}/ereignisse?seq=n` liefert SSE aus `uc2.ereignis`. SSE ist Must, weil der Owner ein Chat-Interface
      will, in dem die Verhandlung live mitläuft; das Replay liest dieselben Ereignisse. `web/app/api/uc2/**` reicht durch,
      Replay liest PG lesend. Freigabe nach E0-Vertrag: `GET /api/uc2/protokoll`, `POST /api/uc2/freigabe`, CLI
      `uv run uc2 freigabe <id> --name "Vorname Nachname"` über `plattform.freigabe.freigeben()`.
- [ ] **S9 Positionsänderungen sichtbar und Replay:** Balkenreihe je Persona und Runde mit Pfeil und Wort bei Änderung
      (k3wbtm, f1ct2); Replay eines aufgezeichneten Falls aus PG, ohne Netz und ohne Modellaufruf.
- [ ] **S10 Szenario-Lauf** „Wie können die Wartezeiten auf Facharzttermine innerhalb von fünf Jahren um 20 % reduziert
      werden, ohne die Gesundheitsausgaben um mehr als 5 % zu erhöhen?“ (`uc2/faelle/wartezeiten.yaml`, Stichtag
      2026-09-30): 3 Läufe im Qualitätsmodus aufgezeichnet, die Übereinstimmung der Klassifikation je Thema wird
      berichtet. Ein Lauf im Standardmodus folgt, sobald der Azure-Schlüssel da ist. Protokoll als md und json, Replay
      als Demo-Rückfall.

### Should (nur wenn Must steht)
- Koalitionsansicht (Akteure mit gleicher Richtung auf ≥ 2 Themen), Navigationspunkte „Quellen (Pressespiegel)“ und
  „Frühere Fälle“, Lektionen in der Oberfläche schalten, mehr als 3 Läufe je Fall.

### Modell je Rolle (`uc2/config/modellrollen.yaml`, Aufruf über `plattform.llm.complete(…, provider=, zweck="uc2.moderator|uc2.akteur")`)
| Rolle | Standard (`azure`) | Qualitätsmodus (`claude`, Abo über `claude -p`) | Tests/CI (`mock`) |
|---|---|---|---|
| Moderator (Auftrag, Auswahl, Steuerung, Protokolltext, Lektionen) | `gpt-5-4-mini`, Denkaufwand hoch | `claude-opus-5-5` | Fixture |
| Akteur (Züge) | `gpt-5-4-mini`, Denkaufwand niedrig | `claude-sonnet-5-5` | Fixture |
| Experte, Suche, Matrix, Klassifikation, Prüfungen, Personenschutz | kein Sprachmodell (Code) | kein Sprachmodell (Code) | Code |

`complete()` kennt laut E0-Vertrag nur `provider` und `zweck`; die Rollen brauchen zusätzlich `modell` und `aufwand`
(Bitte an E0). Bis dahin laufen Akteure im Qualitätsmodus auf demselben Modell wie der Moderator, und das Protokoll
nennt die Lücke. Für den `claude`-Provider gelten diese Anforderungen an E0:
- Das Arbeitsverzeichnis ist ein leerer Temp-Ordner, damit keine Repo-`CLAUDE.md` geladen wird.
- Aufruf mit `--tools ""` und `--strict-mcp-config` ohne Server; der Prompt kommt per stdin.
- Kein `--bare`, das bricht das Abo.
- Ist `ANTHROPIC_API_KEY` gesetzt, bricht der Aufruf ab, damit nichts über die bezahlte API läuft.

### Out-of-Scope
- **Öffentliche Quellen und Anreicherung** (ORF, Parlament, Träger-Websites, Scrapling): Abhängigkeit zu #25.
- **Spieltheoretischer Modus** (Verhandlungsmacht, BATNA, Blockaderisiken); Koalitionen nur als Should.
- **Monte-Carlo-Band, Backtest, Slider-Cockpit, Karte, Sankey** aus Recherche und Click-Dummy-Spezifikation.
- **SozDok-Index** (`svbox/uc2/Rechtstexte`, 14.312 XML) und **OCR** für 2016/2018.
- **pgvector, unaccent**: fehlen bzw. nicht installiert; der deutsche Stemmer faltet Umlaute. (Embeddings sind seit dem
  Nachtrag vom 05.11. 13:10 in Scope, ohne pgvector.)
- **Framework einbetten** (TinyTroupe MIT, Concordia Apache-2.0, MiroFish/AgentTorch AGPL): nur Muster.
- **Code aus eigenen Produkten** (persona-panel-Code, früheres Voice-Projekt, Pflegegeld-Prüfer): verboten im öffentlichen Repo.
- **Abgabe von UC2:** bewertet wird nur UC3; nichts nach GitHub vor Fr kurz vor 09:00.

### First Real Use / Kill
- **Do 19:00, Prüfpunkt:** Bernhard sieht `uc2 verhandlung --fall wartezeiten` mit `mock` und im Qualitätsmodus.
  Daraus entsteht ein Protokoll mit Belegen und Matrix im Terminal.
- **Do 21:00, Kill:** Steht das bis dahin nicht, wird die Oberfläche auf Replay plus U2-2 gekürzt, und Lernen über
  Fälle fällt weg.
- **Streichreihenfolge danach:** Should → S7 über Fälle → S8 U2-0 als Formular statt Auswahl → Vollbestand S1 (09/2026
  bleibt; die S1-Kriterien gelten dann für die 22 Ausgaben von 09/2026).

## 3. Acceptance Criteria

Prüfskripte unter `tests/uc2/pruefe_*.py` lesen nur PG und Rohdaten und importieren keinen Laufzeit-Code. Tests laufen
in einer eigenen DB `healthpolicy_test`; die PG-Verbindung kommt aus `PG*`-Variablen (lokal 5433, CI 5432).

### Belege (S1, S2)
```gherkin
Given die 187 Dateien `Pressespiegel vom *2026.pdf`
When `uc2 index --ab 2026-01-01` zweimal läuft
Then ist count(distinct pruefsumme) in uc2.quelle 186 (bei Kill: 22 für 09/2026), und die Dublette 03.08.2026 ist als übersprungen protokolliert
And je Ausgabe stimmen Artikelzahl, Titel und PDF-Seite mit dem Inhaltsverzeichnis überein; erlaubt sind höchstens 2 Abweichungen je Ausgabe und 15 in Summe, jede gelistet
And kein Artikeltext enthält eine Zeile `Autor:in` und kein Abschnitt hat denselben Text-Hash wie ein anderer
And Lauf 2 gleicht Lauf 1 in Zeilenzahl und Inhalts-Hash (ohne IDs und Zeitstempel)
```
Oracle: `tests/uc2/pruefe_index.py` liest die PDFs selbst (eigener Inhaltsverzeichnis-Parser, `md5`) und vergleicht mit PG; dazu 10 Zufallsartikel gegen die PDF-Seite, gelesen von einem Reviewer-Agenten mit frischem Kontext.

```gherkin
Given ein Kalibrier-Fixture mit zwei erfundenen, textgleichen Artikeln (Jänner und September 2026), Stichtag 2026-09-30
When die Belegsuche läuft
Then steht der September-Artikel vorne, im Verhältnis 0,5^(Δ/Halbwertszeit)
And auf dem echten Index stimmt für 20 Zufallstreffer der gespeicherte Rang mit der nachgerechneten vollen Formel auf 1e-9 überein
```
Oracle: `tests/uc2/pruefe_rang.py` liest Halbwertszeit, Institutionsfaktor und k aus `regeln.yaml` und rechnet `ts_rank_cd × 0,5^(Δ/h) × Faktor` per SQL selbst nach.

```gherkin
Given der aufgezeichnete Lauf aus S10
When alle Texte (Züge, Moderator, Protokoll, Beleg-Chips samt Titel) gescannt werden
Then markiert ein Reviewer-Agent mit frischem Kontext vor Sicht der Maskierung Personennamen in Artikeln mit Funktions- oder Zuschreibungsmustern, bis ≥ 50 Namen beisammen sind, und davon sind ≥ 95 % maskiert
And der Scan aller Texte des Laufs gegen die Reviewer-Namen ergibt 0 Treffer
And zusätzlich ergibt der Scan gegen die getrennt aus den PDFs gelesenen Autor:in-Werte 0 Treffer
And kein Zug enthält ≥ 8 aufeinanderfolgende Wörter aus einem Beleg
```
Oracle: Recall-Stichprobe des frischen Reviewers (Namensliste außerhalb des Repos) ist der Beweis; `tests/uc2/pruefe_namen.py` scannt gegen diese Liste und gegen die Autor:in-Werte.

### Akteure und Modellrollen (S3)
```gherkin
Given uc2/akteure und uc2/config/modellrollen.yaml
When `uc2 akteure pruefen` läuft
Then sind 14 Dateien gegen das JSON-Schema gültig, jede Rolle hat ein Modell für azure, claude und mock
And der Namensscan über die Akteursdateien ergibt 0 Treffer
```
Oracle: JSON-Schema-Prüfung (`jsonschema`) plus `pruefe_namen.py`; die Modellangabe je Rolle steht im Protokoll jedes Laufs.

### Experte (S4)
```gherkin
Given eine Maßnahme „Kassenstellen“ mit +5 % Kapazität und ρ₀ = 0,80 ohne Spanne
When `uc2 experte` rechnet
Then ist die Wartezeitänderung −20,0 % ± 0,1 Prozentpunkte
And dasselbe Paket zweimal gerechnet ergibt identische Werte
And die Ausgangsausgaben im Kostenmodell gleichen dem Wert im Statistik-Austria-PDF in data/uc2
And die Ausgabe nennt die Annahme, die die Zielprüfung kippt
```
Oracle: Literalwert aus der geschlossenen Formel (ρ₁ = 0,7619), Wert aus `pdftotext` des Statistik-Austria-PDF; ein Reviewer-Agent rechnet das Paket der offiziellen Beispiellösung (Wartezeit −22 %, Budget +4,3 %, Text Zeilen 463/465) nach. Bestanden, wenn die Differenz berichtet und die tragende Annahme benannt ist.

### Verhandlung (S5)
```gherkin
Given der aufgezeichnete Lauf aus S10
When `tests/uc2/pruefe_lauf.py` auf uc2.ereignis läuft
Then sind ≤ 6 Akteure beteiligt und jeder nicht gewählte Pool-Akteur hat eine Begründung
And es gibt ≥ 3 Runden, jeder Zug ab Runde 2 nennt in `bezug_auf` ≥ 1 anderen Teilnehmer
And jeder Zug ist schemagültig oder als `ungueltige_ausgabe` markiert
And das Prüfskript findet mit eigenem Muster jede Zahl in den Begründungen; jede ist in `zahlen[]` mit gültiger Quelle oder im Protokoll sichtbar als „Zahl ohne Beleg“ markiert
And jede Zahl mit Quelle `experte` gleicht dem Experten-Ergebnis des Falls auf 0,05
```
Oracle: `tests/uc2/pruefe_lauf.py` (eigenes Zahlenmuster, liest Experten-Ergebnis aus `uc2.ereignis`) auf dem echten Lauf mit `claude-opus-5-5` / `claude-sonnet-5-5`; dazu prüft ein Reviewer-Agent 20 Zufallszahlen auf Herkunft.

```gherkin
Given derselbe Fall mit LLM_PROVIDER=mock
When er zweimal läuft
Then sind Ereignisse (ohne Zeit), Matrix und Klassifikation identisch
And ein mock-Zug mit kaputtem JSON führt zu `ungueltige_ausgabe`, der Lauf endet mit Status fertig
```
Oracle: CI-Job `python` (Determinismus des Codes; Modellverhalten deckt der S10-Lauf ab).

### Positionen und Ergebnis (S6)
```gherkin
Given der aufgezeichnete Lauf aus S10
When das Protokoll erzeugt wird
Then stimmt die Einordnung je Thema mit der Regel auf der Endmatrix überein
And jede Positionsänderung nennt Runde, alten und neuen Wert und die Begründung
And das Markdown-Protokoll hat die 8 Überschriften in der Reihenfolge aus § 2 S6
```
Oracle: `tests/uc2/pruefe_ergebnis.py` rechnet die Einordnung per SQL auf `uc2.position` nach und prüft die Überschriften per grep.

### Lernen (S7)
```gherkin
Given Fall A `wartezeiten` ist abgeschlossen und hat Lektionen
When Fall B `wartezeiten-land` startet
Then enthält das Kontextprotokoll von B die IDs der geholten Lektionen aus A, höchstens 3 je Akteur
And eine mit `uc2 lektion aus` abgeschaltete Lektion fehlt dort und steht weiter in uc2.lektion
```
Oracle: SQL auf `uc2.lektion` und `uc2.ereignis` (Art `kontext`) eines echten Folgelaufs.

### Oberfläche (S8, S9)
```gherkin
Given der aufgezeichnete Lauf aus S10 und gesperrtes Netz
When die UC2-Seiten U2-0, U2-1, U2-1a und U2-2 geöffnet werden
Then zeigt U2-1 je Beitrag Akteur, Haltung, Herkunft-Chip mit Medium und Monat und eine getrennte Moderator-Spur
And U2-2 zeigt Konsens/Mehrheit/Minderheit/Konflikte mit n/N und die Balkenreihe mit Pfeil und Wort je Änderung
And das Replay läuft ohne Modellaufruf, und U2-1a zeigt einen Abbruch mit erhaltenen Runden
And der CI-Job `web` bleibt grün
```
Oracle: `@playwright/test` im Repo gegen den aufgezeichneten Fall, Screenshots in 1440×900 und 390×844 (E0-Design-Regel, #21 note_269372 § D). Je Seite gilt „entspricht Frame `bhI7X` / `f1ct2` / `NjP7Q` / `k3wbtm` per Screenshot“; bestanden, wenn ein Reviewer-Agent mit frischem Kontext je Frame alle genannten Elemente findet. Dazu 0 Schablonen-Treffer laut measureSlop (E0-Design-Regel).

### Szenario (S10)
```gherkin
Given Index, Pool, Experte und Fall wartezeiten.yaml
When das Szenario dreimal im Qualitätsmodus läuft
Then hat jeder Lauf ein Protokoll mit Einordnung je Thema, Experten-Spanne mit Zielprüfung und ≥ 1 Beleg je Akteur und Runde oder die Markierung „Modellannahme“
And die Übereinstimmung der Einordnung je Thema über die 3 Läufe ist im Protokoll berichtet
And die Zahl der Positionsänderungen wird berichtet, ohne Mindestzahl
And ein Reviewer-Agent prüft 20 Zufallspaare (Haltung, Beleg), davon stützen ≥ 18 die Haltung
```
Oracle: `pruefe_lauf.py`, `pruefe_ergebnis.py`, `pruefe_namen.py` auf allen 3 Läufen plus die Paar-Stichprobe durch einen frischen Reviewer.

### External Acceptance
| Criterion | Oracle | Owner | Not before | Pass condition | Fallback if it cannot run |
|-----------|--------|-------|------------|----------------|---------------------------|
| S10 Szenario vorführbar | Owner sieht Replay und U2-2, liest das Protokoll; Checkliste: 8 Teile da, Namensscan 0, jede Zahl mit Experte oder Beleg, Einordnung nachgerechnet | Bernhard Götzendorfer | 2026-11-05 21:00 | Owner bestätigt im Issue mit Name und Zeitpunkt („accepted by the operator“) | Prüfskript-Ergebnisse im Issue, Status „nicht abgenommen“ |
| S10 Lauf im Standardmodus | `LLM_PROVIDER=azure uc2 verhandlung --fall wartezeiten`, Modellangabe im Protokoll | Bernhard Götzendorfer (Schlüssel in `app/.env.local`), Lauf durch die Bau-Session | 2026-11-05 18:00 | Lauf `fertig`, Modell `gpt-5-4-mini` je Rolle im Protokoll | Demo im Qualitätsmodus, Lücke im Protokoll benannt |

## 4. Technical Notes

### Affected Files
- `uc2/` (neu, uv-Member, Layout nach E0-PRD): Module `belege` (extrahieren, zerlegen, index, suche, namen), `akteure`, `experte`, `verhandlung` (moderator, zug, runden, pruefungen), `ergebnis`, `lernen`, `modelle` (Rolle → `plattform.llm.complete`), `api` (FastAPI 8102), `cli`
- `uc2/akteure/*.md` (14), `uc2/config/{modellrollen,institutionen,massnahmen,annahmen,regeln}.yaml`, `uc2/faelle/wartezeiten.yaml`, `uc2/faelle/wartezeiten-land.yaml`
- `uc2/sql/*.sql` (neu): DB `healthpolicy`, Schema `uc2`, dazu `meta.protokoll`/`meta.freigabe` aus `shared/py/plattform/sql/meta.sql`
- `web/app/uc2/**`, `web/app/api/uc2/**`, `web/components/uc2/**` (neu): Seiten U2-0 bis U2-2, Durchreichen an `uc2.api`, Protokoll/Freigabe; Bausteine aus `@kic/ui`
- `tests/uc2/` (neu): erfundene Fixture-Texte (keine echten Namen), mock-Antworten, `pruefe_*.py`
- `uc2/pyproject.toml` (uv-Member, Skript `uc2`); Wurzel-Workspace gehört E0

### Architecture
Wie UC3: Python rechnet, Next.js zeigt an und ruft nie ein Modell. Genau ein Schreibprozess je Fall (`uv run uc2 verhandlung`,
auch wenn `uc2.api` auf 8102 ihn startet); sie schreibt Ereignisse nach jedem Zug in fester Reihenfolge mit `seq` je Fall. `web/app/api/uc2/**`
reicht Start und SSE an `uc2.api` durch und liest für Replay und Protokoll lesend aus PG. Modellaufrufe gehen über
`plattform.llm.complete`, je Rolle mit `zweck` und dem Modell aus `modellrollen.yaml`; jeder Aufruf schreibt die
E0-Protokollzeile ohne Inhalt.
Ein Akteurszug bekommt: Auftrag, eigene Akteursdatei, die k = 8 besten maskierten Belege als nicht vertrauenswürdigen Block,
Experten-Ausgabe zum aktuellen Paket, Zwischenergebnis der Vorrunde und die geholten Lektionen. Nur der Moderator
bestimmt Runden, Themen und Abbruch (Game-Master-Muster aus Concordia, nur als Idee). Alle Prüfungen sind Code und
laufen nach jedem Zug.

### Data Model Changes
Eigene DB `healthpolicy` (PG 5433) mit `meta.protokoll`/`meta.freigabe` (E0-DDL) und Schema `uc2`:
- `quelle`: Datei, Prüfsumme, Ausgabedatum, Seiten, übersprungen
- `artikel`: Quelle, PDF-Seite, Zeitungsseite, Artikeldatum, Medium, Typ, Titel maskiert
- `abschnitt`: Artikel, Text maskiert, Institutionen[], `tsv`
- `fall`: Frage, Auftrag JSON, Modus, Modelle je Rolle, Stichtag, Status, Lebenszeichen, Start/Ende
- `teilnahme`: Fall, Akteur, eingeladen, Begründung, Belegzahl
- `ereignis`: Fall, `seq`, Runde, Art, Akteur, JSON, Zeit
- `position`: Fall, Runde, Akteur, Thema, Wert, Begründung, Beleg-IDs
- `lektion`: Quell-Fall, Akteur, Text, `tsv`, aktiv, Zeit

Regeln (Halbwertszeit, Grenzen) stehen in YAML im Repo, Änderungen per Commit mit `Freigegeben-von`.

### API Changes
- CLI (`uv run uc2 …`): `index`, `akteure pruefen`, `experte --paket`, `verhandlung --fall`, `protokoll --fall --format md|json`, `lektion an|aus`, `freigabe <id> --name`
- FastAPI `uc2.api:app` (8102): `POST /faelle`, `GET /faelle`, `GET /faelle/{id}/ereignisse?seq=n` (SSE)
- Web (E0-Vertrag): `web/app/api/uc2/faelle/**` (Durchreichen), `GET /api/uc2/protokoll?status=`, `POST /api/uc2/freigabe {id, name, entscheidung}`

## 5. Risks & Dependencies

| Risk | Impact | Mitigation | Triage |
|------|--------|------------|--------|
| UC2 frisst Zeit von UC3 | hoch | Prüfpunkt 19:00, Kill 21:00, Must/Should, eigener Worktree | Implement |
| Personenschutz lückenhaft (Nachname-Zuschreibungen ≥ 26 in einer Ausgabe, Titel, Zitate) | hoch | Muster für Zuschreibung, Genitiv und Titel; Scan gegen zweite Liste (Autor:in); Recall-Stichprobe; Zitate in der Anzeige als „[Zitat]“ | Experiment |
| Artikelzerlegung: Radio ohne `Sprache`, 5 Startzeilen in Layout-Kopien, Nachbarartikel in der Kopie | mittel | Inhaltsverzeichnis als Liste, Ende an `Quelle` oder Fußzeile, Abweichungen je Ausgabe gelistet | Implement |
| Wenig Belege zur Wartezeit für Finanzministerium (1), Pharma (0), Gesetzgeber (5) | mittel | Belegzahl in der Auswahl zeigen, „Modellannahme“ markieren, Moderator begründet | Implement |
| Zielprüfung hängt an unbelegtem ρ₀ (+1,25 % bis +7,5 % Kapazität für −20 %) | hoch für Glaubwürdigkeit | Spanne und „entscheidende Annahme“ zeigen, Ziel „offen“, wenn die Spanne −20 % schneidet | Implement |
| Herdenverhalten: schneller Konsens | mittel | rote Linien je Akteur, Moderator fordert Gegenargumente, 3 Läufe mit berichteter Übereinstimmung | Implement |
| `claude -p` lädt Repo-Regeln, Hooks und Werkzeuge; `--bare` bricht das Abo | hoch | neutraler Temp-Ordner, `--tools ""`, `--strict-mcp-config`, Abbruch bei gesetztem `ANTHROPIC_API_KEY` | Implement |
| `complete()` ohne Parameter für Modell und Denkaufwand; „Personas niedriger“ nicht abbildbar | mittel | Bitte an E0 (`modell`, `aufwand`); bis dahin gleiches Modell, Lücke im Protokoll | Implement |
| `CLAUDE.md` nennt `LLM_PROVIDER` noch ohne `claude` | niedrig | E0-1 ändert CLAUDE.md (#21 note_269372, Entscheid 7) | Implement |
| Pen-Frame `NjP7Q` bietet „ollama lokal“; der Ausschluss lokaler Modelle vom 04.11. ist seit 05.11. 13:0x aufgehoben (ollama als Offline-Notnagel) | niedrig | Modellwechsel `azure`/`claude`, `ollama` nur als Notnagel; Frame passt wieder | Implement |
| UC2-Seiten brechen den CI-Job `web` von UC3; ai-elements zielt auf `ai ^6`, chatbot auf `ai 7` | hoch | E0 pinnt `ai`; UC2-Seiten nur in eigenem Bereich; CI `web` grün als Akzeptanz | Implement |
| Abruf nach `id` verliert Ereignisse bei parallelen Schreibern | mittel | genau ein Schreibprozess je Fall, SSE und Replay lesen nach `seq` | Implement |
| Abgebrochene CLI lässt Fall „laufend“ | mittel | Lebenszeichen, Status `abgebrochen` nach 60 s, Anzeige U2-1a | Implement |
| Fixture-Lektionen aus Tests landen in echten Fällen | mittel | Tests nur in Schema `uc2_test` | Implement |
| Presse-Urheberrecht | mittel | Korpus und Index nie im Repo; nur kurze maskierte Ausschnitte mit Quelle | Implement |
| Prompt-Injection aus Pressetext | mittel | markierter Datenblock, keine Werkzeuge im Modellaufruf, Ausgabe nur per Schema | Implement |
| Spieltheorie-Modus nachrüsten | niedrig | nicht in dieser Runde | Defer |

### Dependencies
- #21 E0 Plattform (Vertrag note_269372): `plattform.llm.complete` mit `claude`/`azure`/`mock` (Bitte: `modell`, `aufwand`, Härtung `claude -p`), `meta.protokoll`/`meta.freigabe` + `freigeben()`, Shell mit `/uc2`, Eintrag in `ucs.ts`, `<UcBereich>`, `@kic/ui`, Pin der `ai`-Version, uv-/pnpm-Workspace.
- #26 E5: Pen-Frames `bhI7X`, `f1ct2`, `NjP7Q`, `k3wbtm` und Bausteine (Kommentar in #24).
- #25 E4 Daten-Enrichment: öffentliche Quellen, nur als Abhängigkeit.
- Daten: `../svbox/uc2/Presse` (vollständig), `data/uc2/` (Kalibrierung), Annahmen aus Vault `uc2-healthpolicy-simulator-recherche.md` § 6.
- Lizenzen: ai-elements und vercel/chatbot Apache-2.0, im README nennen; TinyTroupe MIT nur gelesen.
