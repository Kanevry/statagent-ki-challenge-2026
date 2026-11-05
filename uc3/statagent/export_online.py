"""Export für den Online-Server: Schemata ``stat`` und ``meta`` als Plain-SQL, ohne ``roh`` und ``bereinigt``.

``pg_dump --schema=stat --schema=meta --no-owner --no-privileges`` aus ``UC3_DATABASE_URL``, danach Leserechte
für die Rolle der Web-App. Die Datei enthält kein Passwort und keinen Hostnamen; die Verbindung geht über
die Umgebung (``PGHOST``, ``PGPASSWORD`` …) an ``pg_dump``, nicht über die Kommandozeile.

Angepasst wird der Dump an zwei Stellen, damit er in PostgreSQL 16 mit ``psql`` einspielt:
``SET transaction_timeout`` (neu in PG 17, ``pg_dump`` 17/18 schreibt es) und die Meta-Befehle
``\\restrict``/``\\unrestrict`` (``pg_dump`` ab 17.6/18, ältere ``psql`` kennen sie nicht) werden
als Kommentar stehen gelassen. Danach prüft der Export, dass keine Tabelle aus ``roh`` oder ``bereinigt`` in
der Datei steht; sonst löscht er sie.
"""

from __future__ import annotations

import hashlib
import os
import re
import shlex
import subprocess
from collections import Counter
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import BinaryIO

from psycopg.conninfo import conninfo_to_dict

SCHEMATA = ("stat", "meta")
VERBOTEN = ("roh", "bereinigt")
STANDARD_ROLLE = "kic_app"

_ROLLE = re.compile(r"^[a-z_][a-z0-9_]{0,62}$")
_VERBOTEN = re.compile(
    r"^(?:CREATE (?:UNLOGGED )?TABLE|CREATE (?:MATERIALIZED )?VIEW|COPY|INSERT INTO)\s+"
    r"(?:ONLY\s+)?\"?(" + "|".join(VERBOTEN) + r")\"?\."
)
_TABELLE = re.compile(r"^CREATE (?:UNLOGGED )?TABLE\s+\"?([a-z_]+)\"?\.")
_ENTFERNEN = re.compile(r"^(?:SET transaction_timeout\b|\\restrict\b|\\unrestrict\b)")
_PG_ENV = {
    "host": "PGHOST",
    "port": "PGPORT",
    "user": "PGUSER",
    "password": "PGPASSWORD",
    "dbname": "PGDATABASE",
}


class ExportFehler(RuntimeError):
    """Der Export ist gescheitert; die Zieldatei wurde gelöscht."""


@dataclass
class ExportErgebnis:
    pfad: Path
    groesse: int
    sha256: str
    tabellen: dict[str, int] = field(default_factory=dict)
    entfernt: list[str] = field(default_factory=list)


def _kurz(zeile: str) -> str:
    """Was entfernt wurde, ohne Wert (der Schlüssel von \\restrict ist zufällig)."""
    teile = zeile.split()
    return " ".join(teile[:2]) if teile[0] == "SET" else teile[0]


def grants(rolle: str) -> str:
    """Leserechte für die Web-App. Die Rolle entsteht nur, wenn sie fehlt, ohne Passwort und ohne Login."""
    if not _ROLLE.fullmatch(rolle):
        raise ExportFehler(f"Rollenname „{rolle}“ ist nicht erlaubt (nur a-z, 0-9, _).")
    schemata = ", ".join(SCHEMATA)
    return f"""
--
-- Leserechte für die Rolle {rolle} (angehängt von `uc3 export-online`).
-- Die Rolle entsteht ohne Passwort und ohne Login; Anmeldung und Passwort setzt der Betrieb des Servers.
--
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '{rolle}') THEN
    CREATE ROLE {rolle};
  END IF;
END
$$;
GRANT USAGE ON SCHEMA {schemata} TO {rolle};
GRANT SELECT ON ALL TABLES IN SCHEMA {schemata} TO {rolle};
-- Tabellen, die der einspielende Benutzer später in stat/meta anlegt, sind ebenfalls lesbar.
ALTER DEFAULT PRIVILEGES IN SCHEMA {schemata} GRANT SELECT ON TABLES TO {rolle};
"""


def _umgebung(url: str) -> dict[str, str]:
    """Verbindung als PG*-Variablen, damit das Passwort nicht in der Prozessliste steht."""
    umgebung = dict(os.environ)
    for schluessel, wert in conninfo_to_dict(url).items():
        if schluessel in _PG_ENV and wert is not None:
            umgebung[_PG_ENV[schluessel]] = str(wert)
    return umgebung


def befehl(pg_dump: str | list[str]) -> list[str]:
    """Kommando als Liste (``shlex.split``), keine Shell; dazu die festen Schalter."""
    basis = shlex.split(pg_dump) if isinstance(pg_dump, str) else list(pg_dump)
    if not basis:
        raise ExportFehler("--pg-dump ist leer.")
    schemata = [f"--schema={s}" for s in SCHEMATA]
    return [*basis, *schemata, "--no-owner", "--no-privileges", "--format=plain", "--encoding=UTF8"]


def exportieren(
    ziel: Path, url: str, pg_dump: str | list[str] = "pg_dump", rolle: str = STANDARD_ROLLE
) -> ExportErgebnis:
    """Schreibt den Dump nach ``ziel``. Bei Fehler oder verbotenem Schema ist ``ziel`` danach gelöscht."""
    anhang = grants(rolle)
    kommando = befehl(pg_dump)
    ziel.parent.mkdir(parents=True, exist_ok=True)
    pruefsumme = hashlib.sha256()
    tabellen: Counter[str] = Counter()
    entfernt: list[str] = []
    verboten: list[str] = []

    def schreiben(f: BinaryIO, text: str) -> None:
        daten = text.encode("utf-8")
        pruefsumme.update(daten)
        f.write(daten)

    try:
        with ziel.open("wb") as f:
            schreiben(
                f,
                f"-- UC3 StatAgent, Export für den Online-Server: Schemata {', '.join(SCHEMATA)}, ohne "
                f"{' und '.join(VERBOTEN)}.\n-- Erzeugt {datetime.now(UTC):%Y-%m-%dT%H:%M:%SZ}. Einspielen in eine "
                "leere Datenbank: psql -v ON_ERROR_STOP=1 -f <datei>\n",
            )
            with subprocess.Popen(
                kommando, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=_umgebung(url)
            ) as prozess:
                assert prozess.stdout is not None and prozess.stderr is not None
                for roh in prozess.stdout:
                    zeile = roh.decode("utf-8")
                    if _ENTFERNEN.match(zeile):
                        entfernt.append(_kurz(zeile))
                        zeile = f"-- entfernt für PostgreSQL 16: {_kurz(zeile)}\n"
                    elif _VERBOTEN.match(zeile):
                        verboten.append(zeile.strip()[:80])
                    elif treffer := _TABELLE.match(zeile):
                        tabellen[treffer.group(1)] += 1
                    schreiben(f, zeile)
                fehlertext = prozess.stderr.read().decode("utf-8", errors="replace").strip()
                code = prozess.wait()
            if code != 0:
                raise ExportFehler(f"pg_dump endete mit Code {code}: {fehlertext[:500]}")
            if verboten:
                raise ExportFehler(
                    "Der Dump enthält Daten aus " + " oder ".join(VERBOTEN) + ": " + "; ".join(verboten[:5])
                )
            fremd = set(tabellen) - set(SCHEMATA)
            if fremd:
                raise ExportFehler(
                    f"Der Dump enthält Tabellen aus anderen Schemata: {', '.join(sorted(fremd))}"
                )
            if not tabellen:
                raise ExportFehler("Der Dump enthält keine Tabelle aus stat oder meta.")
            schreiben(f, anhang)
    except BaseException:
        ziel.unlink(missing_ok=True)
        raise
    return ExportErgebnis(
        pfad=ziel,
        groesse=ziel.stat().st_size,
        sha256=pruefsumme.hexdigest(),
        tabellen={s: tabellen.get(s, 0) for s in SCHEMATA},
        entfernt=entfernt,
    )
