"""Rückfragen als Dateien (GitLab #72 AC1): Dateien R1 bis R10 nach Vorlage, nachgezählt aus der Datenbank."""

from __future__ import annotations

import re
from datetime import date
from pathlib import Path

from statagent.berichte.rueckfragen import rueckfragen_schreiben
from statagent.db import Verbindung

ABSCHNITTE = (
    "# Rückfrage an die Fachabteilung",
    "Team: OneShotAndy · Nr.: ",
    "**Betroffene Lieferung(en):**",
    "**Was ist aufgefallen?**",
    "**Beleg**",
    "| Anzahl betroffener Sätze |",
    "| Zeitraum / ab welcher Lieferung |",
    "| betroffene Merkmale (Bundesland, ÖNACE, Qualifikation …) |",
    "| Beispiel-IDs (VVH_ID, 3–5 Stück) |",
    "```sql\nSELECT ",
    "**Unser Vorschlag zur Behandlung:**",
    "**Frage an die Fachabteilung:**",
    "*Antwort der Fachabteilung (wird von den Mentoren ausgefüllt):*",
)
THEMEN = {
    "R1": "Geburtsmonat 13",
    "R2": "ÖNACE",
    "R3": "Teil-Lieferung 2025-10",
    "R4": "Freie Dienstverträge fehlen in Lieferung 2025-03",
    "R5": "BEGINN und ENDE vertauscht in Lieferung 2025-06",
}


def _satz(conn: Verbindung, lieferung: str, vvh_id: str, beginn: str | None, ende: str | None) -> None:
    # Erfundene Testsätze, keine Daten aus den Lieferungen.
    conn.execute(
        "INSERT INTO roh.lieferung (lieferung, vvh_id, person_id, geburtsdatum, geschlecht, beginn, ende, qual,"
        " oenace, bundesland) VALUES (%s, %s, %s, '1980-05-05', 'M', %s, %s, 'Arbeiter', 'C', '9')",
        (lieferung, vvh_id, f"T{vvh_id}", beginn, ende),
    )


def _beispiele(text: str) -> list[str]:
    zeile = re.search(r"\| Beispiel-IDs \(VVH_ID, 3–5 Stück\) \| (.*) \|", text)
    assert zeile
    return [] if zeile.group(1).startswith("keine") else zeile.group(1).split(", ")


def test_fuenf_rueckfragen_nach_vorlage_mit_nachgezaehlten_beispielen(
    conn: Verbindung, tmp_path: Path
) -> None:
    # R5 bekommt 2 Treffer (alle IDs), R3 bekommt 4 Treffer (3–5 IDs), R4 bleibt ohne 2025-02 bei 0.
    _satz(conn, "2025-06", "990001", None, "2025-01-01")
    _satz(conn, "2025-06", "990002", None, "2025-02-01")
    for vvh in ("990011", "990012", "990013", "990014"):
        _satz(conn, "2025-09", vvh, "2025-01-01", None)

    pfade = rueckfragen_schreiben(conn, tmp_path, datum=date(2026, 11, 5))

    namen = [p.name for p in pfade]
    assert namen[:5] == ["R1.md", "R2.md", "R3.md", "R4.md", "R5.md"]
    texte = {p.stem: p.read_text(encoding="utf-8") for p in pfade}
    for nr, thema in THEMEN.items():
        text = texte[nr]
        for abschnitt in ABSCHNITTE:
            assert abschnitt in text, (nr, abschnitt)
        assert f"Nr.: {nr} · Datum: 05.11.2026" in text
        assert thema in text.split("**Betroffene")[0], nr

    assert _beispiele(texte["R5"]) == ["990001", "990002"]
    assert (
        "| Anzahl betroffener Sätze | 2 Sätze, mit der Abfrage unten in dieser Datenbank nachgezählt; diese Zahl"
        " gilt. Unsere Analyse der Lieferungen ergab: 388.115" in texte["R5"]
    )
    assert _beispiele(texte["R3"]) == ["990011", "990012", "990013", "990014"]
    assert _beispiele(texte["R4"]) == []
    assert "| Anzahl betroffener Sätze | In dieser Datenbank findet die Abfrage keinen Satz" in texte["R4"]

    # Für Laien lesbar (Owner 05.11.): kein Em-Dash in keiner Datei, „·“ nur in der Kopfzeile der Vorlage,
    # jede Datei sagt, wie wir bis zur Antwort verfahren, und erklärt die Fachbegriffe.
    for nr, text in texte.items():
        assert "—" not in text, nr
        assert all("·" not in z for z in text.splitlines() if not z.startswith("Team: ")), nr
        assert "**Unser Vorschlag zur Behandlung:** So machen wir es bis zur Antwort: " in text, nr
        assert "**Begriffe kurz erklärt**" in text, nr
    assert "- **Verhältnis:** ein Beschäftigungsverhältnis" in texte["R3"]
    assert "- **Fortschreiben:**" in texte["R3"]
    assert "- **Fortschreiben:**" not in texte["R1"]  # nur Begriffe, die im Text vorkommen


def test_r10_entsteht_und_jede_rueckfrage_stellt_eine_frage(conn: Verbindung, tmp_path: Path) -> None:
    # Fängt: R10 (P14) fehlt oder ihre Beleg-Abfrage bricht den Generator (keine Spalte vvh_id), eine Rückfrage
    # stellt zwei Fragen auf einmal, R8 und R9 nennen wieder Zahlen, die nicht zum Qualitätsbericht passen.
    pfade = rueckfragen_schreiben(conn, tmp_path, datum=date(2026, 11, 5))
    texte = {p.stem: p.read_text(encoding="utf-8") for p in pfade}
    assert list(texte)[-2:] == ["R9", "R10"]
    assert "Nr.: R10 · Datum: 05.11.2026" in texte["R10"]
    assert "(Hinterlegt als Regel `P14_sprung_aggregat`.)" in texte["R10"]
    for nr, text in texte.items():
        frage = re.search(r"\*\*Frage an die Fachabteilung:\*\* (.*)", text)
        assert frage and frage.group(1).count("?") == 1, nr
    assert "216 bis 322" in texte["R8"] and "8.000" not in texte["R9"]
