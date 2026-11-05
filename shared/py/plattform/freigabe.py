"""Freigabe durch einen Menschen (Vertrag P, Issue #55).

``freigeben`` schreibt ``meta.freigabe``, setzt den Vorschlag in ``meta.protokoll`` auf ``freigegeben``
und legt den Git-Commit mit den Trailern ``Freigegeben-von``, ``Vorschlag`` (``<uc>/<id>``: die ID ist nur je
UC-Datenbank eindeutig, das Repo teilen alle UCs) und ``Modell`` an, alles in einer
DB-Transaktion: scheitert Git, wird die DB zurückgerollt. Ein Dateilock im Git-Verzeichnis serialisiert
parallele Freigaben auf dasselbe Repo. ``ablehnen`` arbeitet analog ohne Commit.

Die Freigabe ist an den Inhalt gebunden: bei ``objekt_typ = datei`` committet ``git commit --only`` genau
diese Datei (fremd Gestagtes bleibt draußen), und ``pruefe_freigegeben`` vergleicht den Blob im
Freigabe-Commit mit der Datei auf der Platte. Eine danach geänderte Datei gilt als nicht freigegeben.
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
#: Vorschlagstypen der Agenten (UC3 #15) und ihr Objekt der Freigabe.
VORSCHLAG_ZU_OBJEKT: dict[str, str] = {
    "regel_neu": "regel",
    "regel_aendern": "regel",
    "code_datei": "datei",
}
LOCK_NAME = "kic-freigabe.lock"

# Wortbestandteile, die auf eine Rolle oder einen Platzhalter statt auf einen Menschen deuten
# („Teamleitung“, „Administrator“, „Mustermann“).
_SPERR_TEILE = ("team", "admin", "agent", "muster")
# Ganze Wörter, die kein Personenname sind.
_SPERR_WOERTER = frozenset(
    {"ki", "ai", "bot", "system", "user", "claude", "codex", "gpt", "llm", "modell", "vorname", "nachname"}
)
_WORT = re.compile(r"^[^\W\d_]+(?:[-'’.][^\W\d_]+)*\.?$")
_INITIALE = re.compile(r"^[^\W\d_]\.$")


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
    """Gibt den Namen (NFC) zurück oder wirft ``NameUngueltig``: mindestens zwei Wörter aus Buchstaben,
    keine Steuerzeichen, kein ``:``, keine Rollen- oder Platzhalterbezeichnung. Erlaubt sind Bindestrich und
    Apostroph (' und ’) im Wort sowie eine Initiale mit Punkt („J. Huber“)."""
    if not isinstance(name, str) or any(unicodedata.category(z).startswith("C") for z in name):
        raise NameUngueltig("Name enthält Steuerzeichen oder Zeilenumbrüche")
    name = unicodedata.normalize("NFC", name)
    if ":" in name:
        raise NameUngueltig("Name darf keinen Doppelpunkt enthalten")
    woerter = name.split()
    if len(woerter) < 2:
        raise NameUngueltig("Vor- und Nachname nötig (mindestens zwei Wörter)")
    for wort in woerter:
        klein = wort.casefold()
        initiale = bool(_INITIALE.match(wort))
        if not initiale and (not _WORT.match(wort) or sum(z.isalpha() for z in wort) < 2):
            raise NameUngueltig(f"kein Namensbestandteil: {wort!r}")
        if klein.strip(".") in _SPERR_WOERTER or any(teil in klein for teil in _SPERR_TEILE):
            raise NameUngueltig(f"Rollenbezeichnung statt Name: {wort!r}")
    if len({w.casefold() for w in woerter}) < len(woerter):
        raise NameUngueltig("Wörter wiederholen sich")
    if all(_INITIALE.match(w) for w in woerter):
        raise NameUngueltig("nur Initialen, kein Name")
    return " ".join(woerter)


def _git(repo_pfad: Path | str, *argumente: str) -> str:
    # GIT_LITERAL_PATHSPECS: ein ref wie „.“ oder „*.py“ ist ein Dateiname, nie ein Muster.
    umgebung = {**os.environ, "GIT_TERMINAL_PROMPT": "0", "LC_ALL": "C", "GIT_LITERAL_PATHSPECS": "1"}
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
) -> tuple[str, str, str | None, str | None, str | None, str | None]:
    """(uc, anweisung, modell, provider, vorschlag_typ, ref) des offenen Vorschlags, mit FOR UPDATE."""
    zeile = conn.execute(
        "SELECT uc, anweisung, modell, provider, vorschlag_typ, ref, status FROM meta.protokoll"
        " WHERE id = %s FOR UPDATE",
        (vorschlag_id,),
    ).fetchone()
    if zeile is None:
        raise VorschlagUngueltig(f"Vorschlag {vorschlag_id} existiert nicht")
    if zeile[6] != "offen":
        raise VorschlagUngueltig(f"Vorschlag {vorschlag_id} ist {zeile[6]}, nicht offen")
    return zeile[0], zeile[1], zeile[2], zeile[3], zeile[4], zeile[5]


def vorschlag_kennung(uc: str, vorschlag_id: int) -> str:
    """Repo-weit eindeutige Kennung für den Trailer ``Vorschlag`` (z. B. ``uc3/7``)."""
    return f"{uc}/{vorschlag_id}"


def _objekt_typ(angegeben: str | None, vorschlag_typ: str | None) -> str | None:
    if angegeben is not None:
        if angegeben not in OBJEKT_TYPEN:
            raise ValueError(f"objekt_typ muss einer von {OBJEKT_TYPEN} sein")
        return angegeben
    if vorschlag_typ in OBJEKT_TYPEN:
        return vorschlag_typ
    return VORSCHLAG_ZU_OBJEKT.get(vorschlag_typ or "")


def _einzeilig(wert: str | None) -> str:
    return " ".join((wert or "keins").split()) or "keins"


def _vorhandener_commit(repo_pfad: Path | str, kennung: str) -> str | None:
    """Commit mit Trailer ``Vorschlag: <uc>/<id>`` (Wiederholung nach DB-Fehler), sonst None."""
    try:
        _git(repo_pfad, "rev-parse", "--verify", "-q", "HEAD")
    except GitFehler:
        return None  # noch kein Commit im Repo
    ausgabe = _git(repo_pfad, "log", "--format=%H %(trailers:key=Vorschlag,valueonly,separator=%x2C)")
    for zeile in ausgabe.splitlines():
        hash_, _, werte = zeile.partition(" ")
        if kennung in {w.strip() for w in werte.split(",")}:
            return hash_
    return None


def _pruefe_wiederverwendung(
    repo_pfad: Path | str, commit_hash: str, name: str, typ: str, ref: str | None
) -> None:
    """Ein vorhandener Commit zum Vorschlag gilt nur, wenn er denselben Freigebenden (und bei datei denselben
    Inhalt) trägt; sonst nennten DB und Git verschiedene Menschen bzw. Dateistände."""
    im_commit = _git(
        repo_pfad, "log", "-1", "--format=%(trailers:key=Freigegeben-von,valueonly)", commit_hash
    )
    if im_commit.strip() != name:
        raise VorschlagUngueltig(
            f"Commit {commit_hash[:12]} zu diesem Vorschlag nennt einen anderen Freigebenden"
        )
    if typ == "datei" and ref:
        try:
            freigegeben = _git(repo_pfad, "rev-parse", f"{commit_hash}:{ref}")
        except GitFehler as fehler:
            raise VorschlagUngueltig(f"Commit {commit_hash[:12]} enthält {ref} nicht") from fehler
        if _git(repo_pfad, "hash-object", "--", ref) != freigegeben:
            raise VorschlagUngueltig(f"{ref} weicht vom Stand im Commit {commit_hash[:12]} ab")


def _pruefe_autocommit(conn: psycopg.Connection) -> None:
    """autocommit=True und keine offene Transaktion: sonst wäre die Freigabe nur ein Savepoint."""
    from psycopg import pq

    if not conn.autocommit or conn.info.transaction_status != pq.TransactionStatus.IDLE:
        raise ValueError(
            "Verbindung braucht autocommit=True ohne offene Transaktion, sonst wäre die Freigabe nur ein"
            " Savepoint einer fremden Transaktion"
        )


def _pruefe_datei_im_repo(repo_pfad: Path | str, ref: str) -> None:
    """Der ref einer Datei-Freigabe ist genau eine reguläre Datei innerhalb des Repos."""
    wurzel = Path(_git(repo_pfad, "rev-parse", "--show-toplevel")).resolve()
    ziel = (Path(repo_pfad) / ref).resolve()
    if not ziel.is_relative_to(wurzel) or ziel == wurzel:
        raise ValueError(f"objekt_ref {ref!r} liegt nicht innerhalb des Repos")
    if not ziel.is_file():
        raise ValueError(f"objekt_ref {ref!r} ist keine reguläre Datei")


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
    _pruefe_autocommit(conn)
    with _repo_lock(repo_pfad), conn.transaction():
        uc, anweisung, modell, provider, vorschlag_typ, ref = _offener_vorschlag(conn, vorschlag_id)
        kennung = vorschlag_kennung(uc, vorschlag_id)
        typ = _objekt_typ(objekt_typ, vorschlag_typ)
        if typ is None:
            raise ValueError("objekt_typ fehlt und vorschlag_typ ist keiner von " + ", ".join(OBJEKT_TYPEN))
        ziel_ref = objekt_ref if objekt_ref is not None else ref
        if typ == "datei":
            if not ref:
                raise ValueError("objekt_typ datei braucht einen Vorschlag mit ref (Pfad relativ zum Repo)")
            if ziel_ref != ref:
                # pruefe_freigegeben sucht über ref; eine andere Datei freizugeben, hieße R6d zu umgehen.
                raise ValueError(
                    f"objekt_ref {ziel_ref!r} muss bei datei dem ref des Vorschlags {ref!r} entsprechen"
                )
            _pruefe_datei_im_repo(repo_pfad, ziel_ref)
        freigabe = _freigabe_schreiben(conn, vorschlag_id, name, "ja", None, typ, ziel_ref)
        commit_hash = _vorhandener_commit(repo_pfad, kennung)
        if commit_hash is not None:
            _pruefe_wiederverwendung(repo_pfad, commit_hash, name, typ, ziel_ref)
        if commit_hash is None:
            betreff = " ".join(anweisung.split())
            trailer = [
                "--trailer",
                f"Freigegeben-von: {name}",
                "--trailer",
                f"Vorschlag: {kennung}",
                "--trailer",
                f"Modell: {_einzeilig(modell)}@{_einzeilig(provider)}",
            ]
            if typ == "datei":
                # Genau diese Datei, nichts fremd Gestagtes; unverändert ergibt einen leeren Commit.
                _git(repo_pfad, "add", "--", str(ziel_ref))
                _git(
                    repo_pfad,
                    "commit",
                    "--only",
                    "--allow-empty",
                    "-m",
                    betreff,
                    *trailer,
                    "--",
                    str(ziel_ref),
                )
            else:
                _git(repo_pfad, "commit", "--only", "--allow-empty", "-m", betreff, *trailer)
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
    _pruefe_autocommit(conn)
    if not begruendung or not begruendung.strip():
        raise ValueError("Ablehnung braucht eine Begründung")
    with conn.transaction():
        _, _, _, _, vorschlag_typ, ref = _offener_vorschlag(conn, vorschlag_id)
        return _freigabe_schreiben(
            conn,
            vorschlag_id,
            name,
            "nein",
            begruendung.strip(),
            _objekt_typ(objekt_typ, vorschlag_typ),
            objekt_ref if objekt_ref is not None else ref,
        )


def pruefe_freigegeben(conn: psycopg.Connection, datei: Path | str, repo_pfad: Path | str = ".") -> int:
    """Gibt die Vorschlags-ID zurück, wenn der jüngste Vorschlag mit ``ref = datei`` freigegeben ist und die
    Datei noch genau den freigegebenen Inhalt hat.

    Sonst ``NichtFreigegeben``. Aufruf zu Beginn jedes Agenten-Skripts unter ``erzeugt/`` (Regel R6d);
    ``datei`` ist der Pfad relativ zu ``repo_pfad`` (POSIX), so wie er im Vorschlag als ``ref`` steht.
    """
    ref = Path(datei).as_posix()
    zeile = conn.execute(
        "SELECT p.id, p.status, p.commit_hash, (SELECT f.objekt_typ FROM meta.freigabe f"
        "   WHERE f.protokoll_id = p.id AND f.entscheidung = 'ja' ORDER BY f.id DESC LIMIT 1)"
        " FROM meta.protokoll p WHERE p.ref = %s ORDER BY p.id DESC LIMIT 1",
        (ref,),
    ).fetchone()
    if zeile is None:
        raise NichtFreigegeben(f"kein Vorschlag zu {ref}")
    vorschlag_id, status, commit_hash, objekt_typ = zeile
    if status != "freigegeben" or objekt_typ is None:
        raise NichtFreigegeben(f"Vorschlag {vorschlag_id} zu {ref} ist {status}")
    if objekt_typ != "datei":
        # Ohne Inhaltsvergleich wäre ein Skript „freigegeben“, nur weil eine Regel denselben ref trägt.
        raise NichtFreigegeben(f"Vorschlag {vorschlag_id} zu {ref} gibt keine Datei frei ({objekt_typ})")
    if objekt_typ == "datei":
        try:
            auf_platte = _git(repo_pfad, "hash-object", "--", ref)
            freigegeben = _git(repo_pfad, "rev-parse", f"{commit_hash}:{ref}")
        except GitFehler as fehler:
            raise NichtFreigegeben(f"Vorschlag {vorschlag_id}: Inhalt von {ref} nicht prüfbar") from fehler
        if auf_platte != freigegeben:
            raise NichtFreigegeben(f"{ref} wurde nach der Freigabe (Vorschlag {vorschlag_id}) geändert")
    return int(vorschlag_id)
