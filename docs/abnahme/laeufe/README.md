# Rohläufe

Die 101 Laufdateien liegen unverändert im GitLab-Branch `abnahme/laeufe` (Commit `9255594d`), nicht im Hauptstand, weil sie alte Befehlstexte im Wortlaut tragen. Maßgeblich im Hauptstand sind `docs/abnahme/matrix-*.md`, `belege.jsonl`, `entscheide.jsonl` und `schlusslauf-2026-11-06.md`. Die Matrix neu erzeugen: `ABNAHME_LAEUFE=<Ordner mit den Laufdateien> uv run python tests/abnahme/matrix.py schreiben`.
