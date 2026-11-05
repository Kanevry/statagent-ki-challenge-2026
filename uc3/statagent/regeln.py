"""Regeln als Daten: laden, Regelstand berechnen, freigeben.

Der Code kennt nur Regel-ARTEN (z. B. ``bestand``, ``alter``, ``spaltentausch``). Was eine Regel konkret
tut, steht in ``meta.regel.parameter`` und in ``stat.quellzuordnung`` (Technische Regel 3).
"""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from statagent.db import Verbindung


class RegelFehler(RuntimeError):
    """Der Regelsatz ist für einen Lauf nicht vollständig oder widersprüchlich."""


class NameUngueltig(ValueError):
    """Freigabe braucht Vor- und Nachnamen einer Person (Technische Regel 7)."""


@dataclass(frozen=True)
class Regel:
    id: int
    regelsatz: str
    name: str
    typ: str
    art: str
    reihenfolge: int
    parameter: dict[str, Any] = field(hash=False)
    beschreibung: str
    grundlage: str
    gueltig_ab_lieferung: str
    gueltig_bis_lieferung: str | None
    freigegeben_von: str | None
    freigegeben_am: datetime | None

    @property
    def freigegeben(self) -> bool:
        return self.freigegeben_von is not None


def regeln_laden(conn: Verbindung, regelsatz: str, lieferung: str | None = None) -> list[Regel]:
    """Aktive Regeln eines Regelsatzes, die für die Lieferung gelten (alle aktiven ohne Lieferung)."""
    zeilen = conn.execute(
        """
        SELECT id, regelsatz, name, typ, art, reihenfolge, parameter, beschreibung, grundlage,
               gueltig_ab_lieferung, gueltig_bis_lieferung, freigegeben_von, freigegeben_am
        FROM meta.regel
        WHERE regelsatz = %(rs)s AND aktiv
          AND (%(l)s::text IS NULL OR (gueltig_ab_lieferung <= %(l)s
               AND (gueltig_bis_lieferung IS NULL OR gueltig_bis_lieferung >= %(l)s)))
        ORDER BY typ, reihenfolge, id
        """,
        {"rs": regelsatz, "l": lieferung},
    ).fetchall()
    return [
        Regel(
            id=int(str(z["id"])),
            regelsatz=str(z["regelsatz"]),
            name=str(z["name"]),
            typ=str(z["typ"]),
            art=str(z["art"]),
            reihenfolge=int(str(z["reihenfolge"])),
            parameter=dict(z["parameter"]) if isinstance(z["parameter"], dict) else {},
            beschreibung=str(z["beschreibung"]),
            grundlage=str(z["grundlage"]),
            gueltig_ab_lieferung=str(z["gueltig_ab_lieferung"]),
            gueltig_bis_lieferung=None
            if z["gueltig_bis_lieferung"] is None
            else str(z["gueltig_bis_lieferung"]),
            freigegeben_von=None if z["freigegeben_von"] is None else str(z["freigegeben_von"]),
            freigegeben_am=z["freigegeben_am"] if isinstance(z["freigegeben_am"], datetime) else None,
        )
        for z in zeilen
    ]


def eine(regeln: list[Regel], typ: str, art: str) -> Regel:
    """Genau eine aktive Regel dieser Art (für Zählregeln Pflicht)."""
    treffer = [r for r in regeln if r.typ == typ and r.art == art]
    if len(treffer) != 1:
        namen = ", ".join(r.name for r in treffer) or "keine"
        raise RegelFehler(
            f"Regelsatz braucht genau eine aktive {typ}-Regel der Art '{art}' (gefunden: {namen})"
        )
    return treffer[0]


def wert(regel: Regel, schluessel: str) -> Any:
    """Pflichtparameter einer Regel; fehlt er, ist der Regelsatz unvollständig (kein stiller Standardwert)."""
    if schluessel not in regel.parameter:
        raise RegelFehler(f"{regel.name}: Parameter '{schluessel}' fehlt")
    return regel.parameter[schluessel]


def hoechstens_eine(regeln: list[Regel], typ: str, art: str) -> Regel | None:
    """Höchstens eine aktive Regel dieser Art (Einleseregeln sind abschaltbar)."""
    treffer = [r for r in regeln if r.typ == typ and r.art == art]
    if len(treffer) > 1:
        raise RegelFehler(
            f"mehrere aktive {typ}-Regeln der Art '{art}': {', '.join(r.name for r in treffer)}"
        )
    return treffer[0] if treffer else None


def regelstand(conn: Verbindung, regeln: list[Regel]) -> str:
    """Kurzer Hash über alles, was das Ergebnis bestimmt: aktive Regeln, Quellzuordnung, ÖNACE-Gültigkeit.

    Freigabe-Felder und Prüfregeln gehören nicht dazu: beide ändern keine Zahl.
    """
    teile: list[Any] = [
        [r.typ, r.name, r.art, r.reihenfolge, r.parameter, r.gueltig_ab_lieferung, r.gueltig_bis_lieferung]
        for r in sorted(regeln, key=lambda r: (r.typ, r.reihenfolge, r.name))
        if r.typ != "pruefung"  # Prüfregeln melden, sie ändern keine Zahl
    ]
    qz = conn.execute(
        """SELECT quelle, merkmal, version, geliefert, code FROM stat.quellzuordnung
           ORDER BY quelle, merkmal, version, geliefert COLLATE "C" """
    ).fetchall()
    ko = conn.execute(
        """SELECT DISTINCT version, gueltig_von::text AS von, coalesce(gueltig_bis::text, '') AS bis
           FROM stat.klass_oenace ORDER BY 1, 2, 3"""
    ).fetchall()
    kq = conn.execute(
        """SELECT code, beschaeftigungskategorie FROM stat.klass_qualifikation ORDER BY code COLLATE "C" """
    ).fetchall()
    teile.append([[str(v) for v in z.values()] for z in qz])
    teile.append([[str(v) for v in z.values()] for z in ko])
    teile.append([[str(v) for v in z.values()] for z in kq])
    roh = json.dumps(teile, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(roh.encode("utf-8")).hexdigest()[:16]


#: Wörter, die keine Person bezeichnen (Technische Regel 7: „Ein Platzhalter wie ‚Team‘ reicht nicht“).
_PLATZHALTER = {"team", "admin", "administrator", "agent", "ki", "ai", "bot", "system", "user", "test", "uc3"}


def name_pruefen(name: str) -> str:
    """Prüft einen Freigabe-Namen: Vor- und Nachname, keine Platzhalter, keine Steuerzeichen.

    Liefert den normalisierten Namen. Der Commit-Weg der Freigabe (Trailer) läuft über
    ``plattform.freigabe`` (E0, #55); diese Prüfung sichert die Regelfreigabe in ``meta.regel``.
    """
    if any(unicodedata.category(z).startswith("C") for z in name):
        raise NameUngueltig("Der Name enthält Steuerzeichen oder Zeilenumbrüche.")
    if ":" in name:
        raise NameUngueltig("Der Name darf keinen Doppelpunkt enthalten.")
    normal = " ".join(name.split())
    woerter = normal.split(" ")
    if len(woerter) < 2:
        raise NameUngueltig("Bitte Vor- und Nachnamen angeben, z. B. „Erika Musterfrau“.")
    for wort in woerter:
        if (
            not re.fullmatch(r"[^\W\d_][^\W\d_'’.\-]*(?:[-'’][^\W\d_]+)*\.?", wort)
            or len(wort.rstrip(".")) < 2
        ):
            raise NameUngueltig(f"„{wort}“ ist kein Namensbestandteil.")
        if wort.lower().strip(".") in _PLATZHALTER:
            raise NameUngueltig(f"„{normal}“ ist ein Platzhalter, kein Name einer Person.")
    if len({w.lower() for w in woerter}) == 1:
        raise NameUngueltig(f"„{normal}“ ist ein Platzhalter, kein Name einer Person.")
    return normal


def regeln_freigeben(conn: Verbindung, regelsatz: str, name: str, regel_ids: list[int] | None = None) -> int:
    """Gibt alle noch nicht freigegebenen aktiven Regeln (oder die genannten) mit Namen und Zeitpunkt frei."""
    gepruefter_name = name_pruefen(name)
    with conn.transaction():
        cur = conn.execute(
            """
            UPDATE meta.regel SET freigegeben_von = %(n)s, freigegeben_am = now()
            WHERE regelsatz = %(rs)s AND aktiv AND freigegeben_von IS NULL
              AND (%(ids)s::int[] IS NULL OR id = ANY(%(ids)s::int[]))
            """,
            {"n": gepruefter_name, "rs": regelsatz, "ids": regel_ids},
        )
        return cur.rowcount
