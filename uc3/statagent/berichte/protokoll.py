"""Protokoll aller Änderungen (Abgabe `abgabe/protokoll.md`, Technische Regeln 7 und 8).

Quellen, alle ohne Sprachmodell gelesen:
- Git: jeder Commit mit Trailer ``Freigegeben-von`` (Änderung über die eigenen Agenten, Nachricht = Anweisung)
- ``meta.vorschlag``: Vorschläge der Agenten mit Status, Freigabe und Commit (falls die Tabelle existiert)
- ``meta.regel``: Regelfreigaben mit Name und Zeitpunkt
- ``meta.lauf``: Veröffentlichungen eines Monats mit Name und Zeitpunkt
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from statagent import konfig
from statagent.db import Verbindung
from statagent.zeit import zeit_text

_FELD = "\x1e"
_EINTRAG = "\x1f"


@dataclass(frozen=True)
class Commit:
    hash: str
    datum: str
    anweisung: str
    freigegeben_von: str
    vorschlag: str
    modell: str


def freigabe_commits(repo: Path) -> list[Commit]:
    """Commits mit Trailer Freigegeben-von, älteste zuerst (git als argv-Liste, keine Shell)."""
    format_ = "%x1e".join(
        [
            "%H",
            "%cI",
            "%s",
            "%(trailers:key=Freigegeben-von,valueonly,separator=%x2C )",
            "%(trailers:key=Vorschlag,valueonly,separator=%x2C )",
            "%(trailers:key=Modell,valueonly,separator=%x2C )",
        ]
    )
    erg = subprocess.run(
        ["git", "-C", str(repo), "log", "--reverse", "--grep=Freigegeben-von:", f"--format={format_}%x1f"],
        capture_output=True,
        text=True,
        check=False,
    )
    if erg.returncode != 0:
        return []
    commits = []
    for eintrag in erg.stdout.split(_EINTRAG):
        teile = eintrag.strip("\n").split(_FELD)
        if len(teile) != 6 or not teile[3].strip():
            continue
        commits.append(
            Commit(teile[0], teile[1], teile[2], teile[3].strip(), teile[4].strip(), teile[5].strip())
        )
    return commits


def _tabelle_vorhanden(conn: Verbindung, name: str) -> bool:
    z = conn.execute("SELECT to_regclass(%s) IS NOT NULL AS da", (name,)).fetchone()
    return bool(z and z["da"])


def _zahl(wert: object) -> str:
    """Ganze Zahl mit Tausenderpunkt (392.236); sonst der Text, wie er ist."""
    return f"{wert:,}".replace(",", ".") if isinstance(wert, int) else str(wert or "")


def _zelle(text: object) -> str:
    """Text für eine Tabellenzelle: eine Zeile, `|` maskiert (sonst bricht die Markdown-Tabelle um)."""
    return " ".join(str(text or "").split()).replace("|", "\\|")


def _zeit(wert: object) -> str:
    return zeit_text(wert, ersatz="")


def protokoll_erzeugen(conn: Verbindung, repo: Path | None = None) -> str:
    """Markdown-Protokoll aus Git und Datenbank."""
    zeilen = [
        "# Protokoll aller Änderungen",
        "",
        "Jede Änderung an Regeln oder Code und jede Veröffentlichung eines Monats steht hier mit Anweisung,",
        "Änderung, Name der freigebenden Person und Zeitpunkt. Erzeugt mit `uv run uc3 protokoll` aus Git",
        "(Commits mit `Freigegeben-von`) und der Datenbank (meta.vorschlag, meta.regel, meta.lauf, meta.ausgabe).",
        "",
    ]
    # Wer eine Freigabe eingegeben hat, steht nicht im Commit; die Hinweise sind Daten (docs/plan/uc3).
    hinweise = (repo or konfig.REPO_WURZEL) / "docs" / "plan" / "uc3" / "protokoll-hinweise.md"
    if hinweise.is_file():
        zeilen += ["## Hinweise zu den Freigaben", "", hinweise.read_text(encoding="utf-8").strip(), ""]
    zeilen += [
        "## 1 Änderungen über die eigenen Agenten (Git)",
        "",
    ]
    commits = freigabe_commits(repo or konfig.REPO_WURZEL)
    if commits:
        zeilen += [
            "| Zeitpunkt | Anweisung | Freigegeben von | Vorschlag | Modell | Commit |",
            "|---|---|---|---|---|---|",
        ]
        zeilen += [
            f"| {zeit_text(datetime.fromisoformat(c.datum), ersatz=c.datum)} | {_zelle(c.anweisung)} | {c.freigegeben_von} | {c.vorschlag} | {c.modell} | `{c.hash[:10]}` |"
            for c in commits
        ]
    else:
        zeilen.append("Noch keine freigegebene Änderung über die Agenten.")

    zeilen += ["", "## 2 Vorschläge der Agenten", ""]
    if _tabelle_vorhanden(conn, "meta.vorschlag"):
        vorschlaege = conn.execute(
            """SELECT id, erstellt_am, anweisung, rolle, typ, status, freigegeben_von, freigegeben_am,
                      modell, provider
               FROM meta.vorschlag ORDER BY id"""
        ).fetchall()
        if vorschlaege:
            zeilen += [
                "| Nr. | Erstellt | Anweisung | Rolle | Typ | Status | Freigegeben von | Zeitpunkt | Modell |",
                "|---|---|---|---|---|---|---|---|---|",
            ]
            zeilen += [
                f"| {v['id']} | {_zeit(v['erstellt_am'])} | {_zelle(v['anweisung'])} | {v['rolle']} | {v['typ']} |"
                f" {v['status']} | {v['freigegeben_von'] or ''} | {_zeit(v['freigegeben_am'])} |"
                f" {v['modell'] or ''}@{v['provider'] or ''} |"
                for v in vorschlaege
            ]
        else:
            zeilen.append("Noch keine Vorschläge.")
    else:
        zeilen.append("Die Agenten-Laufzeit ist in dieser Datenbank noch nicht eingerichtet.")

    zeilen += ["", "## 3 Regelfreigaben", ""]
    regeln = conn.execute(
        """SELECT regelsatz, freigegeben_von, date_trunc('minute', freigegeben_am) AS am, count(*) AS n,
                  string_agg(name, ', ' ORDER BY reihenfolge, name) AS namen
           FROM meta.regel WHERE freigegeben_von IS NOT NULL
           GROUP BY 1, 2, 3 ORDER BY 3, 1"""
    ).fetchall()
    if regeln:
        zeilen += ["| Regelsatz | Freigegeben von | Zeitpunkt | Regeln |", "|---|---|---|---|"]
        zeilen += [
            f"| {r['regelsatz']} | {r['freigegeben_von']} | {_zeit(r['am'])} | {r['n']}: {r['namen']} |"
            for r in regeln
        ]
    else:
        zeilen.append("Noch keine Regel mit Namen freigegeben; alle Ergebnisse sind vorläufig.")

    zeilen += ["", "## 4 Veröffentlichte Monate", ""]
    laeufe = conn.execute(
        """SELECT DISTINCT ON (lieferung, regelsatz) lieferung, regelsatz, freigegeben_von, freigegeben_am,
                  gezaehlt, ergebnis_hash
           FROM meta.lauf WHERE freigegeben_von IS NOT NULL
           ORDER BY lieferung, regelsatz, freigegeben_am"""
    ).fetchall()
    if laeufe:
        zeilen += [
            "| Berichtsmonat | Regelsatz | Freigegeben von | Zeitpunkt | Verhältnisse | Ergebnis-Hash |",
            "|---|---|---|---|---|---|",
        ]
        zeilen += [
            f"| {z['lieferung']} | {z['regelsatz']} | {z['freigegeben_von']} | {_zeit(z['freigegeben_am'])} |"
            f" {_zahl(z['gezaehlt'])} | `{str(z['ergebnis_hash'])[:12]}` |"
            for z in laeufe
        ]
    else:
        zeilen.append("Noch kein Monat veröffentlicht.")

    zeilen += ["", "## 5 Lieferungen nach außen (Ministerium)", ""]
    ausgaben = (
        conn.execute(
            """SELECT a.berichtsmonat, a.datei, a.zeilen, a.sha256, a.freigegeben_von, a.freigegeben_am,
                      p.status, p.commit_hash
               FROM meta.ausgabe a LEFT JOIN meta.protokoll p ON p.id = a.protokoll_id
               ORDER BY a.berichtsmonat, a.id"""
        ).fetchall()
        if _tabelle_vorhanden(conn, "meta.ausgabe")
        else []
    )
    if ausgaben:
        zeilen += [
            "| Berichtsmonat | Datei | Personen | Freigegeben von | Zeitpunkt | Protokoll | Commit | sha256 |",
            "|---|---|---|---|---|---|---|---|",
        ]
        zeilen += [
            f"| {a['berichtsmonat']} | {a['datei']} | {a['zeilen']} | {a['freigegeben_von']} |"
            f" {_zeit(a['freigegeben_am'])} | {a['status'] or 'ohne Vertrag P'} |"
            f" {'`' + str(a['commit_hash'])[:10] + '`' if a['commit_hash'] else ''} | `{str(a['sha256'])[:12]}` |"
            for a in ausgaben
        ]
    else:
        zeilen.append("Noch keine Lieferung nach außen freigegeben.")
    zeilen.append("")
    return "\n".join(zeilen)


def protokoll_schreiben(conn: Verbindung, ziel: Path | None = None) -> Path:
    ziel = ziel or konfig.abgabe() / "protokoll.md"
    ziel.parent.mkdir(parents=True, exist_ok=True)
    ziel.write_text(protokoll_erzeugen(conn), encoding="utf-8")
    return ziel
