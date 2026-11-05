# Skalierung: Stand und nächste Schritte

## 1. Zweck

Diese Seite zeigt, wo die Online-Demo heute an Grenzen stößt und welche Strukturentscheide schon tragen.
Sie beschreibt den Weg nach der Abgabe, vor Freitag 09:00 wird nichts umgebaut.

## 2. Was heute ein Engpass wäre

Gemessen am 05.11.2026: ein Server mit 4 vCPU, 7,7 GB RAM, ohne Swap, 54 GB Platte frei.
Die Spalte „ab wann“ ist eine Schätzung, nicht gemessen.

| Engpass | Beleg | Ab wann es weh tut (Schätzung) |
|---|---|---|
| Ein Server für Caddy, App und Datenbank | `deploy/docker-compose.prod.yml:8-116` | beim ersten Ausfall des Servers ist alles weg |
| Eine Postgres-Instanz, Sicherung auf derselben Platte | `deploy/docker-compose.prod.yml:39-59`; `scripts/deploy.sh sichern` legt Dumps unter `<basis>/daten/sicherung/` ab | beim Verlust des Servers; dann Wiederaufbau aus den Quell-Dumps auf dem Rechenrechner |
| Python als Subprozess je Frage (`uv run`) | `web/components/uc3/cli.ts:15,31-39`, `web/lib/plattform/uc4.ts:13` | je Route höchstens 2 Läufe gleichzeitig (`web/components/uc3/antwort.ts:14`, `web/lib/plattform/uc4.ts:54`), ab dem dritten Nutzer kommt 429 |
| Lange Zeitlimits je Frage | 60 s (`web/components/uc3/antwort.ts:15`), 120 s (`web/components/uc3/cli.ts:16`), 180 s (`web/lib/plattform/uc4.ts:16`) | ein langsamer Lauf belegt einen der 2 Plätze bis zu 3 Minuten |
| Ratenlimit im Speicher des Next-Prozesses | `web/lib/plattform/ratenlimit.ts:1-3,26` | ab dem zweiten App-Container zählt jeder für sich |
| UC3-Fragen ohne Ratenlimit je IP | nur `MAX_LAEUFE` in `web/components/uc3/antwort.ts:224` | sobald Fragen online offen sind |
| Tagesbudget zählt in einer JSONL-Datei | `shared/py/plattform/llm/kern.py:500-523`; Prüfen und Schreiben nicht atomar (`kern.py:571-572`) | ab dem zweiten Container mit eigenem Volume; die Datei wird je Aufruf ganz gelesen und wächst ohne Ende |
| Ein Budget je Tag für alle | `shared/py/plattform/llm/kern.py:484-498`, `web/lib/plattform/uc4.ts:176` | ein einzelner Vielnutzer sperrt alle bis Mitternacht UTC |
| Embeddings je Prozess neu geladen | Abfrage lädt das Modell (`uc1/uc1/suche.py:364-366`, `uc2/src/uc2/belege/suche.py:356-364`), RSS rund 2,2 GB (`docs/models.md:107`) | online heute nicht: das Image hat kein torch und kein sentence-transformers (gemessen 05.11., `site-packages`), UC2 sucht dort im Volltext-Rückfall; mit Modell geschätzt ab 3 gleichzeitigen Fragen RAM voll |
| Vektoren ganz in numpy statt Index | UC1 lädt alle Vektoren (`uc1/uc1/suche.py:486-500`), UC2 ebenso (`uc2/src/uc2/belege/suche.py:300`) | geschätzt ab rund 100.000 Abschnitten je Index |
| Kein Speicherlimit je Container | kein `mem_limit` in `deploy/docker-compose.prod.yml` | ohne Swap kann der OOM-Killer Postgres statt der App treffen |
| Image wird auf dem Server gebaut | `deploy/docker-compose.prod.yml:3,61-67`, `scripts/deploy.sh` (`cmd_up`, compose build) | jeder Build kostet CPU und RAM der laufenden Demo; den Cache räumt `up` seit 05.11. auf (vorher 14 GB) |
| UC2-Schnittstelle online nicht gestartet | Standard `localhost:8102` (`web/app/api/uc2/_lib/proxy.ts:6-9`), kein Dienst und kein `UC2_API_URL` im Compose | UC2 läuft online nur als Vorführung |

## 3. Was schon skalierbar ist

- Die App hält keinen eigenen Zustand, bis auf das Modellprotokoll im Volume `app_protokoll` (`deploy/docker-compose.prod.yml:72-78`, `deploy/app.Dockerfile:44`).
- Verbindungen kommen aus der Umgebung, der Standardwert `localhost:5433` gilt nur lokal (`uc3/statagent/konfig.py:34`, `uc1/uc1/config.py:30-32`, `uc2/src/uc2/db.py:30`, `web/components/uc3/db.ts:29`).
- Die App liest als Rolle `kic_app` nur mit SELECT, lesend als Voreinstellung und mit höchstens 20 Verbindungen (`deploy/sql/app-rolle.sql:14-19`).
- Rollen und Rechte sind wiederholbar (`deploy/sql/app-rolle.sql:6-12`, `deploy/sql/app-rechte.sql`).
- Das UC3-Schema läuft wiederholbar in einer Transaktion (`uc3/statagent/db.py:62-69`, `README.md:105`).
- Dumps werden in einer Transaktion eingespielt (`scripts/deploy.sh`, `cmd_daten`, pg_restore oder psql mit `--single-transaction`) und per Inhalts-Hash gegen lokal geprüft (`deploy/sql/inhaltshash.sql`, `deploy/README.md:80-83`).
- Alle Basis-Images sind per Digest gepinnt (`deploy/docker-compose.prod.yml:11,41`, `deploy/app.Dockerfile:9-10`).
- Der Web-Pool ist klein und hat Zeitlimits: 3 Verbindungen, 3 s Aufbau, 4 s je Abfrage (`web/components/uc3/db.ts:18,33-45`).
- Die Kante ist schmal: Caddy lässt nur GET und HEAD durch (`deploy/caddy/Caddyfile:27-28`), Stufe A (MR !94) öffnet nur POST auf die zwei Frage-Wege. `scripts/deploy.sh pruefen` misst von außen, dass alle anderen schreibenden Wege zu sind.
- Vor jedem Einspielen sichert `scripts/deploy.sh daten` die Datenbank (`cmd_sichern`), der Rückweg ist ein Befehl.

## 4. Die drei nächsten Schritte

**(a) Datenbank mit Sicherung und Lese-Replik.**
Was: eine eigene oder verwaltete Postgres-16-Instanz mit täglicher Sicherung und einer Lese-Replik.
Warum: der Verlust von `db_daten` ist heute das größte Risiko, und die App braucht nur eine neue `*_DATABASE_URL`.
Aufwand: rund 4 Stunden (Schätzung).
Voraussetzung: ein Rückspielen aus `deploy.sh sichern` ist einmal geprobt; Sicherungen gehen zusätzlich vom Server weg.

**(b) Python-Kern als langlebiger Dienst, Zähler in der Datenbank.**
Was: Fragen laufen über einen Python-Dienst nach dem Muster von `uc2.api` statt über `uv run` je Anfrage.
Was dazu: Ratenlimit und Tagesbudget zählen in einer Tabelle statt im Prozess und in der Datei.
Warum: das Embedding-Modell lädt dann einmal statt je Frage, und mehrere App-Container zählen gemeinsam.
Aufwand: rund 12 Stunden (Schätzung).
Voraussetzung: die App-Rolle bekommt gezielt INSERT auf genau eine Zählertabelle (`deploy/sql/app-rolle.sql:15-17`).

**(c) Images in der CI bauen und in eine Registry schieben.**
Was: die CI baut das App-Image, taggt es mit der Revision und der Server zieht es nur noch.
Warum: der Server rechnet dann nur die Demo, und ein Rückweg ist ein Tag statt ein neuer Build.
Aufwand: rund 4 Stunden (Schätzung).
Voraussetzung: ein Registry-Zugang als geschützte CI-Variable.

Warum diese drei: (a) schützt die Daten, (b) löst die zwei größten Laufzeit-Engpässe zugleich, (c) entlastet den Server billig.
pgvector kommt erst, wenn ein Index über rund 100.000 Abschnitte wächst.

## 5. Was wir bewusst nicht tun

- Kein Kubernetes und keine zweite Server-Region, ein Server mit Sicherung reicht für eine Demo.
- Keine Queue und kein neuer Dienst vor der Abgabe.
- Kein pgvector und keine Partitionierung, solange numpy und die bestehenden Indizes reichen.
