"""Freigabe durch einen Menschen (Vertrag P, Issue #55).

``freigeben`` schreibt ``meta.freigabe``, setzt den Vorschlag in ``meta.protokoll`` auf ``freigegeben``
und legt den Git-Commit mit den Trailern ``Freigegeben-von``, ``Vorschlag`` und ``Modell`` an, alles in einer
DB-Transaktion: scheitert Git, wird die DB zurückgerollt. Ein Dateilock im Git-Verzeichnis serialisiert
parallele Freigaben auf dasselbe Repo. ``ablehnen`` arbeitet analog ohne Commit.
"""

from __future__ import annotations

import fcntl
import os
import re
import subprocess
import unicodedata
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Literal

from pydantic import BaseModel

if TYPE_CHECKING:
    import psycopg

ObjektTyp = Literal["datei", "regel", "lieferung", "antwort"]
OBJEKT_TYPEN: tuple[str, ...] = ("datei", "regel", "lieferung", "antwort")
LOCK_NAME = "kic-freigabe.lock"

# Wortbestandteile, die auf eine Rolle statt auf einen Menschen deuten („Teamleitung“, „Administrator“).
_SPERR_TEILE = ("team", "admin", "agent")
# Ganze Wörter, die kein Personenname sind.
_SPERR_WOERTER = frozenset({"ki", "ai", "bot", "system", "user", "claude", "codex", "gpt", "llm", "modell"})
_WORT = re.compile(r"^[^\W\d_]+(?:[-'.][^\W\d_]+)*\.?$")


class NameUngueltig(ValueError):
    """Der Name ist kein Vor- und Nachname eines Menschen."""


class NichtFreigegeben(PermissionError):
    """Der Vorschlag zu einer Datei unter ``erzeugt/`` ist nicht freigegeben (Regel R6d)."""


class VorschlagUngueltig(LookupError):
    """Vorschlag existiert nicht oder ist nicht mehr offen."""


class GitFehler(RuntimeError):
    """Git-Aufruf gescheitert; die DB-Transaktion wurde zurückgerollt."""


class Freigabe(BaseModel):
    id: int
    protokoll_id: int
    name: str
    zeitpunkt: datetime
    entscheidung: Literal["ja", "nein"]
    begruendung: str | None
    objekt_typ: ObjektTyp | None
    objekt_ref: str | None
    commit_hash: str | None = None


def pruefe_name(name: str) -> str:
    """Gibt den Namen zurück oder wirft ``NameUngueltig``: mindestens zwei Wörter aus Buchstaben,
    keine Steuerzeichen, kein ``:``, keine Rollenbezeichnung."""
    if not isinstance(name, str) or any(unicodedata.category(z).startswith("C") for z in name):
        raise NameUngueltig("Name enthält Steuerzeichen oder Zeilenumbrüche")
    if ":" in name:
        raise NameUngueltig("Name darf keinen Doppelpunkt enthalten")
    woerter = name.split()
    if len(woerter) < 2:
        raise NameUngueltig("Vor- und Nachname nötig (mindestens zwei Wörter)")
    for wort in woerter:
        klein = wort.casefold()
        if not _WORT.match(wort) or sum(z.isalpha() for z in wort) < 2:
            raise NameUngueltig(f"kein Namensbestandteil: {wort!r}")
        if klein.strip(".") in _SPERR_WOERTER or any(teil in klein for teil in _SPERR_TEILE):
            raise NameUngueltig(f"Rollenbezeichnung statt Name: {wort!r}")
    if len({w.casefold() for w in woerter}) < len(woerter):
        raise NameUngueltig("Wörter wiederholen sich")
    return " ".join(woerter)


def _git(repo_pfad: Path | str, *argumente: str) -> str:
    umgebung = {**os.environ, "GIT_TERMINAL_PROMPT": "0"}
    try:
        lauf = subprocess.run(
            ["git", "-C", str(repo_pfad), *argumente],
            capture_output=True,
            text=True,
            timeout=60,
            env=umgebung,
        )
    except (OSError, subprocess.TimeoutExpired) as fehler:
        raise GitFehler(str(fehler)) from fehler
    if lauf.returncode != 0:
        raise GitFehler(f"git {argumente[0]}: {lauf.stderr.strip() or lauf.stdout.strip()}")
    return lauf.stdout.strip()


@contextmanager
def _repo_lock(repo_pfad: Path | str) -> Iterator[None]:
    """Exklusiver Lock ``<git-dir>/kic-freigabe.lock`` (in Worktrees ist ``.git`` eine Datei)."""
    git_dir = Path(_git(repo_pfad, "rev-parse", "--absolute-git-dir"))
    with (git_dir / LOCK_NAME).open("a+") as lockdatei:
        fcntl.flock(lockdatei, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(lockdatei, fcntl.LOCK_UN)


def _offener_vorschlag(
    conn: psycopg.Connection, vorschlag_id: int
) -> tuple[str, str | None, str | None, str | None, str | None]:
    zeile = conn.execute(
        "SELECT anweisung, modell, provider, vorschlag_typ, ref, status FROM meta.protokoll"
        " WHERE id = %s FOR UPDATE",
        (vorschlag_id,),
    ).fetchone()
    if zeile is None:
        raise VorschlagUngueltig(f"Vorschlag {vorschlag_id} existiert nicht")
    if zeile[5] != "offen":
        raise VorschlagUngueltig(f"Vorschlag {vorschlag_id} ist {zeile[5]}, nicht offen")
    return zeile[0], zeile[1], zeile[2], zeile[3], zeile[4]


def _objekt_typ(angegeben: str | None, vorschlag_typ: str | None) -> str | None:
    if angegeben is not None:
        if angegeben not in OBJEKT_TYPEN:
            raise ValueError(f"objekt_typ muss einer von {OBJEKT_TYPEN} sein")
        return angegeben
    return vorschlag_typ if vorschlag_typ in OBJEKT_TYPEN else None


def _freigabe_schreiben(
    conn: psycopg.Connection,
    vorschlag_id: int,
    name: str,
    entscheidung: str,
    begruendung: str | None,
    objekt_typ: str | None,
    objekt_ref: str | None,
) -> Freigabe:
    zeile = conn.execute(
        "INSERT INTO meta.freigabe (protokoll_id, name, entscheidung, begruendung, objekt_typ, objekt_ref)"
        " VALUES (%s, %s, %s, %s, %s, %s) RETURNING id, zeitpunkt",
        (vorschlag_id, name, entscheidung, begruendung, objekt_typ, objekt_ref),
    ).fetchone()
    assert zeile is not None
    conn.execute(
        "UPDATE meta.protokoll SET status = %s WHERE id = %s",
        ("freigegeben" if entscheidung == "ja" else "abgelehnt", vorschlag_id),
    )
    return Freigabe(
        id=zeile[0],
        protokoll_id=vorschlag_id,
        name=name,
        zeitpunkt=zeile[1],
        entscheidung=entscheidung,  # type: ignore[arg-type]
        begruendung=begruendung,
        objekt_typ=objekt_typ,  # type: ignore[arg-type]
        objekt_ref=objekt_ref,
    )


def freigeben(
    conn: psycopg.Connection,
    vorschlag_id: int,
    name: str,
    repo_pfad: Path | str,
    objekt_typ: ObjektTyp | None = None,
    objekt_ref: str | None = None,
) -> Freigabe:
    """Gibt einen offenen Vorschlag frei und committet im Repo (DB und Git gemeinsam oder gar nicht).

    ``objekt_typ``/``objekt_ref`` fehlen: aus ``vorschlag_typ`` und ``ref`` des Vorschlags übernommen.
    """
    name = pruefe_name(name)
    with _repo_lock(repo_pfad), conn.transaction():
        anweisung, modell, provider, vorschlag_typ, ref = _offener_vorschlag(conn, vorschlag_id)
        typ = _objekt_typ(objekt_typ, vorschlag_typ)
        if typ is None:
            raise ValueError("objekt_typ fehlt und vorschlag_typ ist keiner von " + ", ".join(OBJEKT_TYPEN))
        freigabe = _freigabe_schreiben(
            conn, vorschlag_id, name, "ja", None, typ, objekt_ref if objekt_ref is not None else ref
        )
        betreff = " ".join(anweisung.split())
        _git(
            repo_pfad,
            "commit",
            "--allow-empty",
            "-m",
            betreff,
            "--trailer",
            f"Freigegeben-von: {name}",
            "--trailer",
            f"Vorschlag: {vorschlag_id}",
            "--trailer",
            f"Modell: {modell or 'keins'}@{provider or 'keins'}",
        )
        commit_hash = _git(repo_pfad, "rev-parse", "HEAD")
        conn.execute("UPDATE meta.protokoll SET commit_hash = %s WHERE id = %s", (commit_hash, vorschlag_id))
    return freigabe.model_copy(update={"commit_hash": commit_hash})


def ablehnen(
    conn: psycopg.Connection,
    vorschlag_id: int,
    name: str,
    begruendung: str,
    objekt_typ: ObjektTyp | None = None,
    objekt_ref: str | None = None,
) -> Freigabe:
    """Lehnt einen offenen Vorschlag mit Begründung ab (ohne Commit)."""
    name = pruefe_name(name)
    if not begruendung or not begruendung.strip():
        raise ValueError("Ablehnung braucht eine Begründung")
    with conn.transaction():
        _, _, _, vorschlag_typ, ref = _offener_vorschlag(conn, vorschlag_id)
        return _freigabe_schreiben(
            conn,
            vorschlag_id,
            name,
            "nein",
            begruendung.strip(),
            _objekt_typ(objekt_typ, vorschlag_typ),
            objekt_ref if objekt_ref is not None else ref,
        )


def pruefe_freigegeben(conn: psycopg.Connection, datei: Path | str) -> int:
    """Gibt die Vorschlags-ID zurück, wenn der jüngste Vorschlag mit ``ref = datei`` freigegeben ist.

    Sonst ``NichtFreigegeben``. Aufruf zu Beginn jedes Agenten-Skripts unter ``erzeugt/`` (Regel R6d);
    ``datei`` wird so verglichen, wie sie im Vorschlag als ``ref`` steht (POSIX-Pfad).
    """
    ref = Path(datei).as_posix()
    zeile = conn.execute(
        "SELECT p.id, p.status, EXISTS (SELECT 1 FROM meta.freigabe f"
        "   WHERE f.protokoll_id = p.id AND f.entscheidung = 'ja')"
        " FROM meta.protokoll p WHERE p.ref = %s ORDER BY p.id DESC LIMIT 1",
        (ref,),
    ).fetchone()
    if zeile is None:
        raise NichtFreigegeben(f"kein Vorschlag zu {ref}")
    if zeile[1] != "freigegeben" or not zeile[2]:
        raise NichtFreigegeben(f"Vorschlag {zeile[0]} zu {ref} ist {zeile[1]}")
    return int(zeile[0])
