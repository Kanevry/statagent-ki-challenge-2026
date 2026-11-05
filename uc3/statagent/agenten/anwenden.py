"""Freigabe, Ablehnung und Anwenden von Vorschlägen; Start freigegebener Code-Dateien.

Reihenfolge der Freigabe (Vertrag P, Nachtrag zu !6):

1. Name prüfen (Vor- und Nachname, „Team“ reicht nicht).
2. ``freigeben`` der Plattform: schreibt meta.freigabe und den Git-Commit mit der Anweisung als Nachricht
   und den Trailern ``Freigegeben-von``, ``Vorschlag: uc3/<id>``, ``Modell``. Scheitert das, ändert sich
   nichts.
3. ``anwenden`` in einer eigenen Transaktion: Regel ändern bzw. anlegen und mit dem Namen freigeben.
   Scheitert das, bleibt die Freigabe bestehen; der Vorschlag steht dann auf „freigegeben, nicht
   angewendet“ mit der Fehlerklasse, und ``anwenden`` lässt sich erneut aufrufen.

Eine Code-Datei unter ``uc3/erzeugt/`` startet nur, wenn ihr Vorschlag freigegeben ist und ihr Inhalt
genau dem freigegebenen entspricht (Technische Regel 6d).
"""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from psycopg import pq

from statagent.agenten import plattform_bruecke
from statagent.agenten.plattform_bruecke import FreigabeFunktion, PlattformFehlt, PruefFunktion, sha256_datei
from statagent.agenten.regelaenderung import einspielen
from statagent.agenten.vorschlag import Vorschlag, VorschlagFehler, vorschlag_lesen
from statagent.agenten.werkzeuge import abfrage_pruefen
from statagent.db import Verbindung, tupelzeilen
from statagent.regeln import name_pruefen


class NichtFreigegeben(PermissionError):
    """Die Code-Datei ist nicht (oder nicht in diesem Inhalt) freigegeben (Technische Regel 6d)."""


class CodeUngueltig(ValueError):
    """Die Code-Datei hält die Form nicht ein (nur SELECT/WITH bzw. ``def run(conn, lieferung)``)."""


@dataclass(frozen=True)
class FreigabeErgebnis:
    vorschlag_id: int
    name: str
    commit_hash: str | None
    angewendet: bool
    fehler: str | None = None  # Fehlerklasse, wenn das Anwenden gescheitert ist
    meldung: str | None = None


def code_pruefen(endung: str, rumpf: str) -> None:
    """Formprüfung einer Code-Datei, bevor sie Vorschlag wird."""
    if endung == ".sql":
        abfrage_pruefen(rumpf)  # nur SELECT/WITH, eine Abfrage, keine Kennungen
        return
    if endung != ".py":
        raise CodeUngueltig("Code-Dateien sind .py oder .sql")
    try:
        baum = ast.parse(rumpf)
    except SyntaxError as fehler:
        raise CodeUngueltig(
            f"Python-Datei lässt sich nicht lesen: {fehler.msg} (Zeile {fehler.lineno})"
        ) from None
    for knoten in baum.body:
        if isinstance(knoten, ast.FunctionDef) and knoten.name == "run":
            if [a.arg for a in knoten.args.args] == ["conn", "lieferung"]:
                return
            raise CodeUngueltig("run braucht genau die Parameter (conn, lieferung)")
    raise CodeUngueltig("Python-Datei braucht auf oberster Ebene def run(conn, lieferung) -> dict")


def _repo_wurzel(start: Path) -> Path:
    for ordner in (start, *start.parents):
        if (ordner / ".git").exists():
            return ordner
    raise NichtFreigegeben(f"{start} liegt in keinem Git-Repo")


def datei_ablegen(v: Vorschlag, repo_pfad: Path) -> bool:
    """Schreibt die Code-Datei des Vorschlags nach ``uc3/erzeugt/``. True = neu geschrieben."""
    if v.datei_pfad is None or v.datei_inhalt is None:
        raise VorschlagFehler(f"Vorschlag uc3/{v.id} hat keine Code-Datei")
    ziel = repo_pfad / v.datei_pfad
    inhalt = v.datei_inhalt.encode("utf-8")
    if ziel.exists():
        if sha256_datei(ziel.read_bytes()) != v.aenderungen[0]["inhalt_sha256"]:
            raise VorschlagFehler(f"{v.datei_pfad} gibt es schon mit anderem Inhalt")
        return False
    ziel.parent.mkdir(parents=True, exist_ok=True)
    ziel.write_bytes(inhalt)
    return True


def ziel_gesperrt(conn: Verbindung, v: Vorschlag) -> str | None:
    """Grund, warum die Regeländerung nicht in ihren Ziel-Regelsatz darf, sonst None.

    Ein Zählregelsatz mit gerechneten Monaten (v1, v2 der Abgabe) ändert sich nie in place; das prüft der
    Koordinator beim Vorschlagen, und hier noch einmal beim Freigeben, weil ein alter offener Vorschlag sein
    Ziel aus einer Zeit vor den Läufen haben kann (Zweitmeinung zu #80).
    """
    if v.typ == "code_datei" or not re.fullmatch(r"v\d+", v.regelsatz_ziel):
        return None
    z = conn.execute(
        "SELECT EXISTS (SELECT 1 FROM meta.lauf WHERE regelsatz = %s) AS da", (v.regelsatz_ziel,)
    ).fetchone()
    if z is not None and z["da"]:
        return (
            f"Regelsatz {v.regelsatz_ziel} hat gerechnete Monate und ändert sich nicht mehr; der Vorschlag ist älter "
            "als diese Läufe. Bitte die Anweisung neu stellen (das Ziel wird dann ein neuer Regelsatz)."
        )
    return None


def anwenden(conn: Verbindung, vorschlag_id: int, *, repo_pfad: Path | None = None) -> Vorschlag:
    """Wendet einen freigegebenen Vorschlag an (eigene Transaktion, wiederholbar).

    Regeln: Zielregelsatz anlegen, falls er fehlt, Parameter setzen bzw. Regel anlegen, betroffene Regeln
    mit Name und Zeitpunkt der Freigabe versehen. Code-Datei: liegt mit dem freigegebenen Inhalt im Repo.
    """
    with conn.transaction():
        conn.execute("SELECT 1 FROM meta.vorschlag WHERE id = %s FOR UPDATE", (vorschlag_id,))
        v = vorschlag_lesen(conn, vorschlag_id)
        if v.status != "freigegeben":
            raise VorschlagFehler(f"Vorschlag uc3/{v.id} ist {v.status}; angewendet wird nur nach Freigabe")
        if v.angewendet_am is not None:
            return v
        if (grund := ziel_gesperrt(conn, v)) is not None:
            raise VorschlagFehler(grund)
        if v.typ == "code_datei":
            if repo_pfad is None:
                raise VorschlagFehler("Code-Dateien brauchen den Repo-Pfad")
            datei_ablegen(v, repo_pfad)
        else:
            betroffen = einspielen(
                conn,
                vorschlag_id=v.id,
                typ=v.typ,
                regelsatz_ziel=v.regelsatz_ziel,
                regelsatz_basis=v.regelsatz_basis,
                aenderungen=v.aenderungen,
                anweisung=v.anweisung,
                begruendung=v.begruendung,
            )
            conn.execute(
                "UPDATE meta.regel SET freigegeben_von = %s, freigegeben_am = %s WHERE id = ANY(%s)",
                (v.freigegeben_von, v.freigegeben_am, betroffen),
            )
        conn.execute(
            "UPDATE meta.vorschlag SET angewendet_am = now(), anwenden_fehler = NULL WHERE id = %s",
            (vorschlag_id,),
        )
    return vorschlag_lesen(conn, vorschlag_id)


def _bereit_fuer_plattform(conn: Verbindung, v: Vorschlag) -> int:
    if v.protokoll_id is None:
        raise PlattformFehlt("meta.protokoll (#55) fehlt: ohne Protokollzeile gibt es keine Freigabe")
    if not conn.autocommit or conn.info.transaction_status != pq.TransactionStatus.IDLE:
        raise VorschlagFehler("Freigabe braucht eine Verbindung mit autocommit und ohne offene Transaktion")
    return v.protokoll_id


def freigabe_ausfuehren(
    conn: Verbindung,
    vorschlag_id: int,
    name: str,
    repo_pfad: Path,
    *,
    freigeben: FreigabeFunktion | None = None,
) -> FreigabeErgebnis:
    """Gibt einen offenen Vorschlag mit Vor- und Nachnamen frei und wendet ihn danach an.

    ``freigeben`` (Standard: ``plattform.freigabe.freigeben``) schreibt meta.freigabe und den Commit.
    Wirft es, bleibt der Vorschlag offen und keine Regel ändert sich.
    """
    gepruefter_name = name_pruefen(name)
    repo_pfad = Path(repo_pfad)
    v = vorschlag_lesen(conn, vorschlag_id)
    if v.status != "offen":
        raise VorschlagFehler(f"Vorschlag uc3/{v.id} ist bereits {v.zustand}")
    if (grund := ziel_gesperrt(conn, v)) is not None:
        raise VorschlagFehler(grund)  # vor dem Commit: nichts wird freigegeben
    protokoll_id = _bereit_fuer_plattform(conn, v)
    funktion = freigeben or plattform_bruecke.lade_freigabe()

    neu_abgelegt = v.typ == "code_datei" and datei_ablegen(v, repo_pfad)  # ref muss eine Datei im Repo sein
    try:
        with tupelzeilen(conn):
            freigabe = funktion(conn, protokoll_id, gepruefter_name, repo_pfad)
    except BaseException:
        if neu_abgelegt and v.datei_pfad is not None:
            (repo_pfad / v.datei_pfad).unlink(missing_ok=True)
        raise
    commit_hash = getattr(freigabe, "commit_hash", None)
    zeitpunkt = getattr(freigabe, "zeitpunkt", None)
    with conn.transaction():
        conn.execute(
            """UPDATE meta.vorschlag SET status = 'freigegeben', freigegeben_von = %s,
                      freigegeben_am = coalesce(%s::timestamptz, now()), commit_hash = %s
               WHERE id = %s AND status = 'offen'""",
            (gepruefter_name, zeitpunkt, None if commit_hash is None else str(commit_hash), vorschlag_id),
        )
    try:
        anwenden(conn, vorschlag_id, repo_pfad=repo_pfad)
    except Exception as fehler:  # jede Fehlerklasse wird festgehalten; die Freigabe bleibt bestehen
        with conn.transaction():
            conn.execute(
                "UPDATE meta.vorschlag SET anwenden_fehler = %s WHERE id = %s",
                (type(fehler).__name__, vorschlag_id),
            )
        return FreigabeErgebnis(
            vorschlag_id,
            gepruefter_name,
            commit_hash,
            angewendet=False,
            fehler=type(fehler).__name__,
            meldung=str(fehler),
        )
    return FreigabeErgebnis(vorschlag_id, gepruefter_name, commit_hash, angewendet=True)


def ablehnen_ausfuehren(
    conn: Verbindung,
    vorschlag_id: int,
    name: str,
    repo_pfad: Path,
    *,
    begruendung: str | None = None,
    ablehnen: FreigabeFunktion | None = None,
) -> Vorschlag:
    """Lehnt einen offenen Vorschlag mit Vor- und Nachnamen ab. Regeln und Repo bleiben unverändert."""
    gepruefter_name = name_pruefen(name)
    v = vorschlag_lesen(conn, vorschlag_id)
    if v.status != "offen":
        raise VorschlagFehler(f"Vorschlag uc3/{v.id} ist bereits {v.zustand}")
    protokoll_id = _bereit_fuer_plattform(conn, v)
    funktion = ablehnen or plattform_bruecke.lade_ablehnung()
    if not begruendung or not begruendung.strip():
        raise VorschlagFehler("Eine Ablehnung braucht eine Begründung")
    # Vertrag P: ablehnen(conn, vorschlag_id, name, begruendung) – ohne Commit, daher ohne Repo-Pfad.
    with tupelzeilen(conn):
        entscheidung = funktion(conn, protokoll_id, gepruefter_name, begruendung.strip())
    zeitpunkt = getattr(entscheidung, "zeitpunkt", None)
    with conn.transaction():
        conn.execute(
            """UPDATE meta.vorschlag SET status = 'abgelehnt', abgelehnt_von = %s,
                      abgelehnt_am = coalesce(%s::timestamptz, now()), ablehnungsgrund = %s
               WHERE id = %s AND status = 'offen'""",
            (gepruefter_name, zeitpunkt, begruendung, vorschlag_id),
        )
    return vorschlag_lesen(conn, vorschlag_id)


def erzeugt_ausfuehren(
    conn: Verbindung,
    datei: Path,
    lieferung: str,
    *,
    repo_pfad: Path | None = None,
    pruefen: PruefFunktion | None = None,
) -> dict[str, Any]:
    """Startet eine erzeugte Code-Datei, aber nur mit Freigabe genau dieses Inhalts.

    ``.sql``: eine Leseabfrage mit dem Platzhalter ``%(lieferung)s``; Ergebnis ``{spalten, zeilen}``.
    ``.py``: ``run(conn, lieferung) -> dict``. Beides läuft in einer Nur-Lese-Transaktion.
    """
    datei = Path(datei).resolve()
    repo = (repo_pfad or _repo_wurzel(datei.parent)).resolve()
    try:
        inhalt = datei.read_bytes()
    except OSError as fehler:
        raise NichtFreigegeben(f"{datei.name} lässt sich nicht lesen: {type(fehler).__name__}") from None
    pruefung = pruefen or plattform_bruecke.pruefe_freigegeben
    if not pruefung(conn, datei, repo) or datei.read_bytes() != inhalt:
        raise NichtFreigegeben(
            f"{datei.name} ist nicht freigegeben oder wurde nach der Freigabe geändert; "
            "neue Freigabe nötig (uc3 freigabe)"
        )
    text = inhalt.decode("utf-8")
    with conn.transaction():
        conn.execute("SET TRANSACTION READ ONLY")
        if datei.suffix == ".sql":
            with conn.cursor() as cur:
                cur.execute(abfrage_pruefen(text).encode(), {"lieferung": lieferung})
                spalten = [s.name for s in (cur.description or [])]
                return {"spalten": spalten, "zeilen": cur.fetchall()}
        if datei.suffix != ".py":
            raise CodeUngueltig("Code-Dateien sind .py oder .sql")
        namensraum: dict[str, Any] = {"__name__": f"erzeugt_{datei.stem}", "__file__": str(datei)}
        exec(compile(text, str(datei), "exec"), namensraum)  # freigegebener Inhalt, siehe Prüfung oben
        ergebnis = namensraum["run"](conn, lieferung)
    if not isinstance(ergebnis, dict):
        raise CodeUngueltig("run(conn, lieferung) muss ein dict liefern")
    return ergebnis
