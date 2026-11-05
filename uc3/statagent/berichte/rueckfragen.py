"""Rückfragen an die Fachabteilung als Dateien (GitLab #72 AC1, Abgabe ``abgabe/rueckfragen/R1.md`` …).

Aufbau nach der Veranstaltervorlage ``rueckfrage_vorlage.md``. Die Texte stehen in ``meta.rueckfrage``
(``uc3/db/130_rueckfragen.sql``). Satzzahl und Beispiel-IDs übernimmt der Generator nicht aus dem Text: Er führt
``beleg_sql`` lesend aus und zählt nach. Weicht die gespeicherte Angabe ab, gilt die Messung, und die Datei nennt
beide. Beispiel-IDs sind VVH_IDs (bis zu fünf, kleinste zuerst); bei 0 Treffern steht keine ID in der Datei.
"""

from __future__ import annotations

import re
from datetime import date
from pathlib import Path
from typing import cast

from statagent.db import Verbindung

TEAM = "OneShotAndy"
MAX_BEISPIELE = 5


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
        return f"0 Treffer: in dieser Datenbank nicht reproduziert (Angabe aus der Analyse: {gespeichert})"
    if _erste_zahl(gespeichert) == gemessen:
        return f"{_zahl(gemessen)} (nachgezählt); {gespeichert}"
    return f"{_zahl(gemessen)} (nachgezählt, gilt); Angabe aus der Analyse weicht ab: {gespeichert}"


def _datei_text(r: dict[str, object], gemessen: int, ids: list[str], datum: date) -> str:
    gestellt = r.get("gestellt_am")
    tag = gestellt if isinstance(gestellt, date) else datum
    regel = f" Umgesetzt als Regel `{r['regel_name']}`." if r.get("regel_name") else ""
    zeitraum = f"ab lieferung_{r['ab_lieferung']}" if r.get("ab_lieferung") else str(r["lieferungen"])
    beispiele = ", ".join(ids) if ids else "keine (0 Treffer)"
    antwort = ""
    if r.get("antwort"):
        am = r.get("antwort_am")
        antwort = f"\n{r['antwort']}" + (f" ({am:%d.%m.%Y})" if isinstance(am, date) else "") + "\n"
    return (
        "# Rückfrage an die Fachabteilung\n\n"
        f"Team: {TEAM} · Nr.: {r['nr']} · Datum: {tag:%d.%m.%Y}\n\n"
        f"**Thema:** {r['titel']}\n\n"
        f"**Betroffene Lieferung(en):** {r['lieferungen']}\n\n"
        f"**Was ist aufgefallen?** {r['aufgefallen']}\n\n"
        "**Beleg**\n\n"
        "| Angabe | Wert |\n"
        "| --- | --- |\n"
        f"| Anzahl betroffener Sätze | {_zelle(_anzahl_text(gemessen, str(r['anzahl'])))} |\n"
        f"| Zeitraum / ab welcher Lieferung | {_zelle(zeitraum)}; betroffen: {_zelle(str(r['lieferungen']))} |\n"
        f"| betroffene Merkmale (Bundesland, ÖNACE, Qualifikation …) | {_zelle(str(r['merkmale']))} |\n"
        f"| Beispiel-IDs (VVH_ID, 3–5 Stück) | {beispiele} |\n\n"
        "Abfrage, mit der das nachvollzogen werden kann (eine Zeile je betroffenem Satz):\n\n"
        "```sql\n"
        f"{str(r['beleg_sql']).strip().rstrip(';')};\n"
        "```\n\n"
        f"**Unser Vorschlag zur Behandlung:** {r['vorschlag']}{regel}\n\n"
        f"**Frage an die Fachabteilung:** {r['frage']}\n\n"
        "---\n"
        "*Antwort der Fachabteilung (wird von den Mentoren ausgefüllt):*\n"
        f"{antwort}"
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
