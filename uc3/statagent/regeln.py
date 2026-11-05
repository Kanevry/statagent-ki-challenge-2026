"""Regeln als Daten: laden, Regelstand berechnen, freigeben.

Der Code kennt nur Regel-ARTEN (z. B. ``bestand``, ``alter``, ``spaltentausch``). Was eine Regel konkret
tut, steht in ``meta.regel.parameter`` und in ``stat.quellzuordnung`` (Technische Regel 3).
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from plattform.freigabe import NameUngueltig as NameUngueltig  # Vertrag P, re-exportiert
from plattform.freigabe import pruefe_name

from statagent.db import Verbindung, lieferungen, tupelzeilen


class RegelFehler(RuntimeError):
    """Der Regelsatz ist für einen Lauf nicht vollständig oder widersprüchlich."""


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
    regelsaetze = sorted({r.regelsatz for r in regeln})
    qz = conn.execute(
        """SELECT quelle, merkmal, version, geliefert, code FROM stat.quellzuordnung WHERE regelsatz = ANY(%s)
           ORDER BY quelle, merkmal, version, geliefert COLLATE "C" """,
        (regelsaetze,),
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


def name_pruefen(name: str) -> str:
    """Prüft einen Freigabe-Namen nach Vertrag P (``plattform.freigabe.pruefe_name``): Vor- und Nachname einer
    Person, keine Platzhalter oder Rollen, keine Steuerzeichen. Liefert den normalisierten Namen (NFC)."""
    return str(pruefe_name(name))


def regeln_freigeben(
    conn: Verbindung,
    regelsatz: str,
    name: str,
    regel_ids: list[int] | None = None,
    *,
    repo_pfad: Path | None = None,
) -> int:
    """Gibt die noch offenen aktiven Regeln eines Regelsatzes (oder die genannten) mit Namen und Zeitpunkt frei
    und hält für jede Lieferung den so freigegebenen Regelstand fest (Regeln und Quellzuordnung).

    Mit ``repo_pfad`` läuft die Freigabe über Vertrag P (``plattform.freigabe.freigeben``): Eintrag in
    meta.protokoll/meta.freigabe und ein Git-Commit mit Trailer ``Freigegeben-von``. Liefert die Zahl der Regeln.

    ``freigeben`` verlangt eine Verbindung ohne offene Transaktion (DB und Git gemeinsam oder gar nicht) und liest
    Tupelzeilen. Scheitert die Freigabe, bleibt der Protokolleintrag nicht ``offen`` liegen: er wird über
    ``plattform.freigabe.ablehnen`` mit dem technischen Grund geschlossen, und keine Regel wird freigegeben.
    """
    person = name_pruefen(name)
    offen = conn.execute(
        """SELECT count(*) AS n FROM meta.regel WHERE regelsatz = %(rs)s AND aktiv AND freigegeben_von IS NULL
             AND (%(ids)s::int[] IS NULL OR id = ANY(%(ids)s::int[]))""",
        {"rs": regelsatz, "ids": regel_ids},
    ).fetchone()
    anzahl_offen = int(str(offen["n"])) if offen else 0
    protokoll_id: int | None = None
    if repo_pfad is not None:
        from plattform.freigabe import ablehnen, freigeben

        with conn.transaction():
            eintrag = conn.execute(
                """INSERT INTO meta.protokoll (uc, akteur, name, anweisung, wirkung, vorschlag_typ, ref)
                   VALUES ('uc3', 'mensch', %s, %s, %s, 'regel', %s) RETURNING id""",
                (
                    person,
                    f"Regelsatz {regelsatz} freigeben",
                    f"{anzahl_offen} Regeln mit Namen freigegeben; Regelstand je Lieferung festgehalten",
                    f"meta.regel/{regelsatz}",
                ),
            ).fetchone()
        assert eintrag is not None
        protokoll_id = int(str(eintrag["id"]))
        try:
            with tupelzeilen(conn):
                freigeben(
                    conn,
                    protokoll_id,
                    person,
                    repo_pfad,
                    objekt_typ="regel",
                    objekt_ref=f"meta.regel/{regelsatz}",
                )
        except Exception as fehler:
            with tupelzeilen(conn):
                ablehnen(
                    conn,
                    protokoll_id,
                    person,
                    f"Freigabe technisch abgebrochen ({type(fehler).__name__}: {fehler}); keine Regel freigegeben",
                    objekt_typ="regel",
                    objekt_ref=f"meta.regel/{regelsatz}",
                )
            raise
    with conn.transaction():
        cur = conn.execute(
            """
            UPDATE meta.regel SET freigegeben_von = %(n)s, freigegeben_am = now()
            WHERE regelsatz = %(rs)s AND aktiv AND freigegeben_von IS NULL
              AND (%(ids)s::int[] IS NULL OR id = ANY(%(ids)s::int[]))
            """,
            {"n": person, "rs": regelsatz, "ids": regel_ids},
        )
        geaendert = cur.rowcount
        for lieferung in lieferungen(conn):
            regeln = regeln_laden(conn, regelsatz, lieferung)
            if not regeln or not all(r.freigegeben for r in regeln):
                continue
            conn.execute(
                """INSERT INTO meta.regelstand_freigabe (regelsatz, lieferung, regelstand, freigegeben_von,
                     protokoll_id) VALUES (%s, %s, %s, %s, %s) ON CONFLICT DO NOTHING""",
                (regelsatz, lieferung, regelstand(conn, regeln), person, protokoll_id),
            )
    return geaendert


def regelstand_freigegeben(
    conn: Verbindung, regelsatz: str, lieferung: str, stand: str
) -> dict[str, object] | None:
    """Freigabe (Name, Zeitpunkt) des Regelstands für die Lieferung, sonst None."""
    return conn.execute(
        """SELECT freigegeben_von, freigegeben_am FROM meta.regelstand_freigabe
           WHERE regelsatz = %s AND lieferung = %s AND regelstand = %s""",
        (regelsatz, lieferung, stand),
    ).fetchone()
