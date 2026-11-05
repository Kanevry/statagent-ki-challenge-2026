# Abnahmen: Übersicht

Die Abnahme-Lane prüft unabhängig von den Bau-Sessions, mit dem Blick der Jury. Sie schreibt nur Protokolle
(`docs/abnahme/`) und Skripte, die lesen und messen (`tests/abnahme/`). Befunde gehen als Kommentar an das Issue und
mit Lane-Zuordnung an die zuständige Session; Fixes macht die Lane, der der Code gehört.

Stand: 05.11.2026, 16:20 (Europe/Vienna).

| Issue | Abnahme | Urteil | Protokoll |
|---|---|---|---|
| #66 | EA-4 Jury-Weg: frische DB, Golden Set 08/2024, Determinismus | **bestanden** auf main `f1bf42bb`; alle 24 Monate bitgleich mit dem Manifest der UC3-Lane; Blocker 66-6: `lauf --alle` hängt auf frischer DB | [66.md](66.md) |
| #63 | EA-1 Modell-Schalter live | **bestanden** (16:04, nach Mistral-Freischaltung) | [63.md](63.md) |
| #64 | EA-2 Screens gegen Pen-Frames, Schablonen, Sprache | Vorprüfung **nicht bestanden** (UC3 und Präsentation live Platzhalter, Shell weicht ab); 0 Schablonen-Treffer | [64.md](64.md) |
| #95 | UC4 Gemeinsamer Einstieg | UC3-Teil **bestanden**; UC2 und UC1 ohne Adapter | [95.md](95.md) |
| #65 | EA-3 Voice Ende zu Ende | offen: nicht vor 22:00, nach #61; Soll-Zahl im Issue veraltet (388.650 statt 387.180) | Kommentar in #65 |
| #51 | UC2-Szenario mit azure | nicht prüfbar: Verhandlung erst in !47, #49 offen | - |
| #50 | UC2-Szenario vorführbar | nicht prüfbar: nicht vor 21:00, #49 offen | - |
| #36 | UC1 A1 Pflege per Stimme | nicht prüfbar: #34 Voice-Anbindung offen; Owner-Abnahme | - |
| #37 | UC1 A2 frische Prüfung | nicht prüfbar: Lotse-Kern (#31) und Antrag nicht auf main | - |
| #38 | UC1 A3 Seite gegen Frames | nicht vor 06.11., #35 offen | - |
| #39 | UC1 A4 Held-out | Vorbedingung nicht belegt (`kern.py` seit 14:31), Vorschlag in #39 | Kommentar in #39 |

## Wie man eine Messung wiederholt

- Prüf-DB und UC3-Läufe: `tests/abnahme/66_jury_weg.sh <schritt>` auf einem Rechner mit Docker, Pfade in
  `abnahme.env` neben dem Skript (Vorlage `abnahme.env.example`). Nie gegen eine Bau-Datenbank.
- Modell-Schalter: `uv run --package plattform python -m plattform.llm smoke --datei docs/abnahme/63-smoke.md`.
- UC4-Kette: `uv run python tests/abnahme/95_kette.py` mit `UC3_DATABASE_URL` auf die Prüf-DB.
- Screens: dev-browser headless, `web/tests/lib/slop-measure.js` einspielen, je Route 1440×900 und 390×844
  (Ablauf in `64.md`).
