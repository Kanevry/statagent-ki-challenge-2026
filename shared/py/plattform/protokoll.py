"""Protokoll der Plattform (Vertrag P).

Teil 1 (dieses Gerüst, #53): ``modellaufruf`` schreibt je Modellaufruf genau eine JSON-Zeile mit
Provider, Modell, Version, Zweck, Prompt-Hash, Dauer, Tokens und Fallback-Stufe, nie den Inhalt.
``plattform.llm`` (#54) ruft es auf; die Signatur ist Vertrag.

Teil 2 (#55): ``schreibe``/``lies`` gegen ``meta.protokoll`` und der JSON-Vertrag ``Eintrag``.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import threading
from collections.abc import Mapping
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal

from pydantic import BaseModel, ConfigDict

if TYPE_CHECKING:
    import psycopg

_SCHREIBSPERRE = threading.Lock()


@dataclass(frozen=True, slots=True)
class Modellaufruf:
    """Eine Protokollzeile je Modellaufruf. Absichtlich ohne Feld für Prompt oder Antwort."""

    provider: str
    modell: str
    version: str | None
    zweck: str
    prompt_hash: str
    dauer_ms: int
    tokens_in: int | None
    tokens_out: int | None
    fallback_stufe: int
    aufwand: str | None = None
    fehler: str | None = None
    zeit: str = ""


def protokoll_datei() -> Path:
    """Ziel der Modell-Protokollzeilen: ``PLATTFORM_PROTOKOLL`` oder ``var/protokoll/modellaufrufe.jsonl``."""
    explizit = os.environ.get("PLATTFORM_PROTOKOLL")
    if explizit:
        return Path(explizit)
    wurzel = Path.cwd().resolve()
    for ordner in (wurzel, *wurzel.parents):
        if (ordner / ".git").exists():
            wurzel = ordner
            break
    return wurzel / "var" / "protokoll" / "modellaufrufe.jsonl"


def modellaufruf(eintrag: Modellaufruf) -> Path:
    """Hängt genau eine Zeile an und gibt die Datei zurück."""
    zeile = asdict(eintrag)
    if not zeile["zeit"]:
        zeile["zeit"] = datetime.now(UTC).isoformat(timespec="milliseconds")
    ziel = protokoll_datei()
    ziel.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(zeile, ensure_ascii=False, sort_keys=True) + "\n"
    with _SCHREIBSPERRE, ziel.open("a", encoding="utf-8") as datei:
        datei.write(text)
    return ziel


# --- Teil 2 (#55): meta.protokoll -------------------------------------------------------------------

DDL_DATEI = Path(__file__).with_name("sql") / "meta.sql"
SCHEMA_DATEI = Path(__file__).resolve().parents[2] / "schema" / "protokoll-eintrag.json"

Akteur = Literal["agent", "mensch"]
Status = Literal["offen", "freigegeben", "abgelehnt"]


class Eintrag(BaseModel):
    """JSON-Vertrag für ``GET /api/<uc>/protokoll`` (Schema: ``shared/schema/protokoll-eintrag.json``)."""

    model_config = ConfigDict(extra="forbid", title="ProtokollEintrag")

    id: int
    zeit: datetime
    uc: str
    akteur: Akteur
    name: str
    anweisung: str
    wirkung: str | None
    status: Status
    modell: str | None
    ref: str | None


class NeuerEintrag(BaseModel):
    """Eingabe für ``schreibe``: ``id`` und ``zeit`` vergibt die Datenbank."""

    model_config = ConfigDict(extra="forbid")

    uc: str
    akteur: Akteur
    name: str
    anweisung: str
    wirkung: str | None = None
    vorschlag_typ: str | None = None
    status: Status = "offen"
    modell: str | None = None
    provider: str | None = None
    ref: str | None = None


def ddl_einspielen(conn: psycopg.Connection) -> None:
    """Spielt ``sql/meta.sql`` ein (idempotent). Muss vor UC-eigenen ``meta.*``-Tabellen laufen."""
    with conn.transaction():
        conn.execute(DDL_DATEI.read_text(encoding="utf-8"))


def schreibe(conn: psycopg.Connection, eintrag: NeuerEintrag | Mapping[str, Any]) -> int:
    """Legt einen Eintrag in ``meta.protokoll`` an und gibt dessen ``id`` zurück."""
    neu = eintrag if isinstance(eintrag, NeuerEintrag) else NeuerEintrag.model_validate(eintrag)
    werte = neu.model_dump()
    spalten = ", ".join(werte)
    platzhalter = ", ".join(f"%({k})s" for k in werte)
    with conn.transaction():
        zeile = conn.execute(
            f"INSERT INTO meta.protokoll ({spalten}) VALUES ({platzhalter}) RETURNING id", werte
        ).fetchone()
    assert zeile is not None
    return int(zeile[0])


_EINTRAG_SPALTEN = ", ".join(Eintrag.model_fields)


def lies(
    conn: psycopg.Connection, status: Status | None = None, limit: int = 200, *, uc: str | None = None
) -> list[Eintrag]:
    """Einträge, neueste zuerst, optional gefiltert nach ``status`` und ``uc``."""
    zeilen = conn.execute(
        f"SELECT {_EINTRAG_SPALTEN} FROM meta.protokoll"
        " WHERE (%(status)s::text IS NULL OR status = %(status)s)"
        " AND (%(uc)s::text IS NULL OR uc = %(uc)s)"
        " ORDER BY id DESC LIMIT %(limit)s",
        {"status": status, "uc": uc, "limit": limit},
    ).fetchall()
    felder = list(Eintrag.model_fields)
    return [Eintrag.model_validate(dict(zip(felder, zeile, strict=True))) for zeile in zeilen]


def eintrag_schema() -> dict[str, Any]:
    """JSON-Schema des ``Eintrag`` (Draft 2020-12), Quelle der eingecheckten Schema-Datei."""
    schema = Eintrag.model_json_schema()
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", **schema}


def schema_text() -> str:
    return json.dumps(eintrag_schema(), ensure_ascii=False, indent=2) + "\n"


# --- Export protokoll.md (Pflichtabgabe UC3) ---------------------------------------------------------

_FELD = "\x1f"
_SATZ = "\x1e"


def _zelle(wert: object) -> str:
    text = "" if wert is None else str(wert)
    return " ".join(text.split()).replace("|", "\\|")


def freigabe_commits(repo: Path | str) -> list[dict[str, str]]:
    """Commits mit Trailer ``Freigegeben-von`` (neueste zuerst); leeres Repo liefert eine leere Liste."""
    format_ = _FELD.join(
        [
            "%H",
            "%aI",
            "%s",
            "%(trailers:key=Freigegeben-von,valueonly,separator=%x2C )",
            "%(trailers:key=Vorschlag,valueonly,separator=%x2C )",
            "%(trailers:key=Modell,valueonly,separator=%x2C )",
        ]
    )
    lauf = subprocess.run(
        ["git", "-C", str(repo), "log", f"--format={format_}{_SATZ}"],
        capture_output=True,
        text=True,
        timeout=60,
        env={**os.environ, "LC_ALL": "C"},
    )
    if lauf.returncode != 0:
        if "does not have any commits" in lauf.stderr:
            return []
        raise RuntimeError(f"git log fehlgeschlagen: {lauf.stderr.strip()}")
    commits = []
    for satz in lauf.stdout.split(_SATZ):
        teile = satz.strip("\n").split(_FELD)
        if len(teile) != 6:
            continue
        hash_, zeit, betreff, name, vorschlag, modell = (t.strip() for t in teile)
        if name:
            commits.append(
                {
                    "hash": hash_,
                    "zeit": zeit,
                    "betreff": betreff,
                    "name": name,
                    "vorschlag": vorschlag,
                    "modell": modell,
                }
            )
    return commits


def export_md(conn: psycopg.Connection, repo: Path | str, uc: str | None = None) -> str:
    """``protokoll.md``: je Freigabe-Commit, je Ablehnung und je ``meta.protokoll``-Eintrag eine Zeile.

    Mit ``uc`` zählen nur Commits, deren Trailer ``Vorschlag`` auf einen Eintrag dieses UC zeigt.
    """
    eintraege = conn.execute(
        "SELECT id, zeit, uc, akteur, name, anweisung, wirkung, status, modell, provider, ref, commit_hash"
        " FROM meta.protokoll WHERE (%(uc)s::text IS NULL OR uc = %(uc)s) ORDER BY id",
        {"uc": uc},
    ).fetchall()
    commits = freigabe_commits(repo)
    if uc is not None:
        eigene = {str(e[0]) for e in eintraege}
        commits = [c for c in commits if {v.strip() for v in c["vorschlag"].split(",")} & eigene]
    ablehnungen = conn.execute(
        "SELECT f.protokoll_id, f.zeitpunkt, p.anweisung, f.name, f.begruendung FROM meta.freigabe f"
        " JOIN meta.protokoll p ON p.id = f.protokoll_id"
        " WHERE f.entscheidung = 'nein' AND (%(uc)s::text IS NULL OR p.uc = %(uc)s) ORDER BY f.id",
        {"uc": uc},
    ).fetchall()
    zeilen = [
        "# Protokoll",
        "",
        "Erzeugt aus `git log` (Trailer) und `meta.protokoll`" + (f", Use Case {uc}." if uc else "."),
        "",
        f"## Freigaben im Git-Verlauf ({len(commits)})",
        "",
        "| Commit | Zeit | Anweisung | Freigegeben von | Vorschlag | Modell |",
        "|---|---|---|---|---|---|",
    ]
    for c in commits:
        zeilen.append(
            f"| `{c['hash'][:12]}` | {_zelle(c['zeit'])} | {_zelle(c['betreff'])} | {_zelle(c['name'])}"
            f" | {_zelle(c['vorschlag'])} | {_zelle(c['modell'])} |"
        )
    zeilen += [
        "",
        f"## Ablehnungen ({len(ablehnungen)})",
        "",
        "| Vorschlag | Zeit | Anweisung | Abgelehnt von | Begründung |",
        "|---|---|---|---|---|",
    ]
    for protokoll_id, zeitpunkt, anweisung, name, begruendung in ablehnungen:
        zeilen.append(
            f"| {protokoll_id} | {zeitpunkt.isoformat(timespec='seconds')} | {_zelle(anweisung)}"
            f" | {_zelle(name)} | {_zelle(begruendung)} |"
        )
    zeilen += [
        "",
        f"## Einträge in meta.protokoll ({len(eintraege)})",
        "",
        "| ID | Zeit | UC | Akteur | Name | Anweisung | Wirkung | Status | Modell | Bezug | Commit |",
        "|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for id_, zeit, uc_, akteur, name, anweisung, wirkung, status, modell, provider, ref, commit in eintraege:
        modell_text = f"{modell}@{provider}" if modell else ""
        zeilen.append(
            f"| {id_} | {zeit.isoformat(timespec='seconds')} | {_zelle(uc_)} | {akteur} | {_zelle(name)}"
            f" | {_zelle(anweisung)} | {_zelle(wirkung)} | {status} | {_zelle(modell_text)}"
            f" | {_zelle(ref)} | {_zelle(commit and commit[:12])} |"
        )
    return "\n".join(zeilen) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m plattform.protokoll")
    befehle = parser.add_subparsers(dest="befehl", required=True)
    schema = befehle.add_parser("schema", help="JSON-Schema des Eintrag nach shared/schema schreiben")
    schema.add_argument("--out", type=Path, default=SCHEMA_DATEI)
    export = befehle.add_parser("export", help="protokoll.md aus git log und meta.protokoll erzeugen")
    export.add_argument("--md", action="store_true", required=True)
    export.add_argument("--repo", type=Path, default=Path("."))
    export.add_argument("--db", required=True, help="PostgreSQL-URL der UC-Datenbank")
    export.add_argument("--uc", default=None)
    export.add_argument("--out", type=Path, default=Path("protokoll.md"))
    args = parser.parse_args(argv)

    if args.befehl == "schema":
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(schema_text(), encoding="utf-8")
        print(args.out)
        return 0

    import psycopg

    with psycopg.connect(args.db) as conn:
        text = export_md(conn, args.repo, uc=args.uc)
    args.out.write_text(text, encoding="utf-8")
    print(args.out, file=sys.stdout)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
