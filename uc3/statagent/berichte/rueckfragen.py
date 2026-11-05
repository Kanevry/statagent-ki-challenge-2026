"""Rückfragen an die Fachabteilung als Dateien (GitLab #72 AC1, Abgabe ``abgabe/rueckfragen/R1.md`` …).

Aufbau nach der Veranstaltervorlage ``rueckfrage_vorlage.md``. Die Texte stehen in ``meta.rueckfrage``
(``uc3/db/130_rueckfragen.sql``). Satzzahl und Beispiel-IDs übernimmt der Generator nicht aus dem Text: Er führt
``beleg_sql`` lesend aus und zählt nach. Weicht die gespeicherte Angabe ab, gilt die Messung, und die Datei nennt
beide. Beispiel-IDs sind VVH_IDs (bis zu fünf, kleinste zuerst); bei 0 Treffern steht keine ID in der Datei.

Die Dateien lesen Menschen ohne Statistikwissen: kurze Sätze, keine Prüfregel-Kürzel im Fließtext, und am Ende
jeder Datei die Fachbegriffe, die darin vorkommen, mit je einem Satz erklärt.
"""

from __future__ import annotations

import re
from datetime import date
from pathlib import Path
from typing import cast

from statagent.db import Verbindung

TEAM = "OneShotAndy"
MAX_BEISPIELE = 5

# Fachbegriff, Suchwort im Text (klein geschrieben), Erklärung in einem Satz. Reihenfolge = Reihenfolge in der Datei.
BEGRIFFE: tuple[tuple[str, str, str], ...] = (
    ("Lieferung", "lieferung", "der monatliche Datenabzug, etwa Lieferung 2025-10 für Oktober 2025."),
    ("Satz", "sätze", "eine Zeile einer Lieferung."),
    (
        "Verhältnis",
        "verhältnis",
        "ein Beschäftigungsverhältnis; wer zwei Stellen hat, zählt zweimal, gezählt werden Verhältnisse und"
        " nicht Personen.",
    ),
    ("Stichtag", "stichtag", "der letzte Tag des Monats; gezählt wird, wer an diesem Tag beschäftigt ist."),
    (
        "Fortschreiben",
        "fortschreib",
        "ein Verhältnis, das in einer Lieferung fehlt, unverändert aus der Lieferung davor übernehmen.",
    ),
    ("ÖNACE", "önace", "die österreichische Einteilung der Wirtschaftszweige, also der Branchen."),
    ("Qualifikation", "qualifikation", "die Art der Beschäftigung, etwa Arbeiter, Angestellte oder Beamte."),
    (
        "Revisionsbedarf",
        "revisionsbedarf",
        "der Hinweis, dass ein schon veröffentlichter Monat nachträglich zu berichtigen ist.",
    ),
    ("VVH_ID", "vvh_id", "die Kennung eines Verhältnisses in den Lieferungen."),
)


def _zahl(n: int) -> str:
    return f"{n:,}".replace(",", ".")


def _erste_zahl(text: str) -> int | None:
    treffer = re.search(r"\d{1,3}(?:\.\d{3})+|\d+", text)
    return int(treffer.group().replace(".", "")) if treffer else None


def _zelle(text: str) -> str:
    return text.replace("|", "\\|").replace("\n", " ")


def beleg_messen(conn: Verbindung, beleg_sql: str) -> tuple[int, list[str]]:
    """Trefferzahl von ``beleg_sql`` und bis zu fünf Beispiel-VVH_IDs (kleinste zuerst), nur lesend."""
    # Die Abfrage stammt aus der versionierten Datei 130_rueckfragen.sql, nicht aus einer Eingabe.
    beleg = beleg_sql.strip().rstrip(";")
    with conn.transaction():
        if conn.autocommit:  # eigene Transaktion: nur lesen
            conn.execute("SET TRANSACTION READ ONLY")
        zeile = conn.execute("SELECT count(*) AS n FROM (" + beleg + ") b").fetchone()
        ids = conn.execute(
            "SELECT vvh_id FROM (SELECT DISTINCT vvh_id FROM (" + beleg + ") b) d "
            "ORDER BY length(vvh_id), vvh_id LIMIT 5"  # MAX_BEISPIELE; ohne Parameter, da beleg_sql % enthält
        ).fetchall()
    anzahl = int(cast(int, zeile["n"])) if zeile else 0
    return anzahl, [str(r["vvh_id"]) for r in ids]


def _anzahl_text(gemessen: int, gespeichert: str) -> str:
    if gemessen == 0:
        return f"In dieser Datenbank findet die Abfrage keinen Satz. Unsere Analyse der Lieferungen: {gespeichert}"
    if _erste_zahl(gespeichert) == gemessen:
        return f"{gespeichert} (mit der Abfrage unten nachgezählt)"
    return (
        f"{_zahl(gemessen)} Sätze, mit der Abfrage unten in dieser Datenbank nachgezählt; diese Zahl gilt."
        f" Unsere Analyse der Lieferungen ergab: {gespeichert}"
    )


def _begriffe(text: str) -> str:
    """Erklärt die Fachbegriffe, die in ``text`` vorkommen, je in einem Satz (leer, wenn keiner vorkommt)."""
    klein = text.lower()
    zeilen = [f"- **{wort}:** {erklaerung}" for wort, such, erklaerung in BEGRIFFE if such in klein]
    return "**Begriffe kurz erklärt**\n\n" + "\n".join(zeilen) + "\n\n" if zeilen else ""


def _datei_text(r: dict[str, object], gemessen: int, ids: list[str], datum: date) -> str:
    gestellt = r.get("gestellt_am")
    tag = gestellt if isinstance(gestellt, date) else datum
    regel = f" (Hinterlegt als Regel `{r['regel_name']}`.)" if r.get("regel_name") else ""
    zeitraum = str(r["lieferungen"]).replace("lieferung_", "Lieferung ")
    beispiele = ", ".join(ids) if ids else "keine, weil die Abfrage hier keinen Satz findet"
    antwort = ""
    if r.get("antwort"):
        am = r.get("antwort_am")
        antwort = f"\n{r['antwort']}" + (f" ({am:%d.%m.%Y})" if isinstance(am, date) else "") + "\n"
    sql_block = f"```sql\n{str(r['beleg_sql']).strip().rstrip(';')};\n```\n\n"
    kopf_bis_frage = (
        "# Rückfrage an die Fachabteilung\n\n"
        f"Team: {TEAM} · Nr.: {r['nr']} · Datum: {tag:%d.%m.%Y}\n\n"
        f"**Thema:** {r['titel']}\n\n"
        f"**Betroffene Lieferung(en):** {r['lieferungen']}\n\n"
        f"**Was ist aufgefallen?** {r['aufgefallen']}\n\n"
        "**Beleg**\n\n"
        "| Angabe | Wert |\n"
        "| --- | --- |\n"
        f"| Anzahl betroffener Sätze | {_zelle(_anzahl_text(gemessen, str(r['anzahl'])))} |\n"
        f"| Zeitraum / ab welcher Lieferung | {_zelle(zeitraum)} |\n"
        f"| betroffene Merkmale (Bundesland, ÖNACE, Qualifikation …) | {_zelle(str(r['merkmale']))} |\n"
        f"| Beispiel-IDs (VVH_ID, 3–5 Stück) | {beispiele} |\n\n"
        "Abfrage, mit der das nachvollzogen werden kann (sie liefert eine Zeile je betroffenem Satz):\n\n"
        f"{sql_block}"
        # `vorschlag` ist ohne Einleitung gespeichert, damit § 3 des Qualitätsberichts sie nicht doppelt sagt.
        f"**Unser Vorschlag zur Behandlung:** So machen wir es bis zur Antwort: {r['vorschlag']}{regel}\n\n"
        f"**Frage an die Fachabteilung:** {r['frage']}\n\n"
    )
    return (
        kopf_bis_frage
        + _begriffe(kopf_bis_frage.replace(sql_block, ""))  # Begriffe nur aus dem Text, nicht aus der SQL
        + "---\n"
        + "*Antwort der Fachabteilung (wird von den Mentoren ausgefüllt):*\n"
        + antwort
    )


def rueckfragen_schreiben(conn: Verbindung, ziel_dir: Path, *, datum: date | None = None) -> list[Path]:
    """Schreibt je Zeile in ``meta.rueckfrage`` eine Datei ``<nr>.md`` nach ``ziel_dir``.

    ``datum`` steht in der Kopfzeile, solange ``gestellt_am`` leer ist (Standard: heute).
    Liefert die geschriebenen Pfade in der Reihenfolge der Nummern (R1, R2, …, R10).
    """
    zeilen = conn.execute(
        "SELECT * FROM meta.rueckfrage ORDER BY length(nr), nr",
    ).fetchall()
    ziel_dir.mkdir(parents=True, exist_ok=True)
    pfade: list[Path] = []
    for r in zeilen:
        gemessen, ids = beleg_messen(conn, str(r["beleg_sql"]))
        pfad = ziel_dir / f"{r['nr']}.md"
        pfad.write_text(_datei_text(r, gemessen, ids, datum or date.today()), encoding="utf-8")
        pfade.append(pfad)
    return pfade
