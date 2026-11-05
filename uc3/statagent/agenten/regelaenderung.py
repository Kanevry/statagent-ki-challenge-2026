"""Regeländerungen eines Vorschlags in meta.regel einspielen (für Probe und Anwenden derselbe Code).

Der Zielregelsatz (z. B. v2) entsteht beim ersten Mal als Kopie aller aktiven Regeln des Basisregelsatzes
(gleiche Namen, ohne Freigabe). Die Quellzuordnung in stat.quellzuordnung bleibt gemeinsam. Das Einspielen
ist wiederholbar: steht eine Änderung schon so in der Datenbank, passiert nichts.
"""

from __future__ import annotations

import json
from typing import Any

from statagent.db import Verbindung


class RegelKonflikt(RuntimeError):
    """Die Regel steht nicht mehr so in der Datenbank, wie der Vorschlag sie vorgefunden hat."""


def regelsatz_vorhanden(conn: Verbindung, regelsatz: str) -> bool:
    zeile = conn.execute("SELECT EXISTS (SELECT 1 FROM meta.regel WHERE regelsatz = %s) AS da", (regelsatz,))
    z = zeile.fetchone()
    return bool(z and z["da"])


def regelsatz_sicherstellen(conn: Verbindung, ziel: str, basis: str) -> bool:
    """Legt den Zielregelsatz als Kopie der aktiven Basisregeln an, wenn er fehlt. True = neu angelegt."""
    if ziel == basis or regelsatz_vorhanden(conn, ziel):
        return False
    cur = conn.execute(
        """INSERT INTO meta.regel (regelsatz, name, typ, art, reihenfolge, parameter, beschreibung, begruendung,
                                   grundlage, gueltig_ab_lieferung, gueltig_bis_lieferung, aktiv)
           SELECT %s, name, typ, art, reihenfolge, parameter, beschreibung, begruendung, grundlage,
                  gueltig_ab_lieferung, gueltig_bis_lieferung, true
           FROM meta.regel WHERE regelsatz = %s AND aktiv""",
        (ziel, basis),
    )
    if cur.rowcount == 0:
        raise RegelKonflikt(f"Basisregelsatz {basis} hat keine aktiven Regeln")
    # Quellzuordnungen gehören zum Regelsatz (Sheet alt und neu bleiben getrennt änderbar).
    conn.execute(
        """INSERT INTO stat.quellzuordnung (regelsatz, quelle, merkmal, version, geliefert, klassifikation, code,
                                            regel_id)
           SELECT %s, quelle, merkmal, version, geliefert, klassifikation, code, regel_id
           FROM stat.quellzuordnung WHERE regelsatz = %s
           ON CONFLICT DO NOTHING""",
        (ziel, basis),
    )
    return True


def _herkunft(vorschlag_id: int, anweisung: str) -> str:
    return f"Vorschlag uc3/{vorschlag_id}: {' '.join(anweisung.split())}"


def einspielen(
    conn: Verbindung,
    *,
    vorschlag_id: int,
    typ: str,
    regelsatz_ziel: str,
    regelsatz_basis: str,
    aenderungen: list[dict[str, Any]],
    anweisung: str,
    begruendung: str,
) -> list[int]:
    """Spielt die Regeländerungen ein (ohne Freigabe-Felder). Liefert die IDs der betroffenen Regeln.

    Muss in einer Transaktion laufen; der Aufrufer entscheidet, ob sie bestehen bleibt (Anwenden) oder
    zurückgerollt wird (Probe).
    """
    if typ not in ("regel_aendern", "regel_neu"):
        return []
    regelsatz_sicherstellen(conn, regelsatz_ziel, regelsatz_basis)
    herkunft = _herkunft(vorschlag_id, anweisung)
    betroffen: list[int] = []
    for a in aenderungen:
        if typ == "regel_aendern":
            betroffen.append(_aendern(conn, regelsatz_ziel, regelsatz_basis, a, herkunft, begruendung))
        else:
            betroffen.append(_neu(conn, regelsatz_ziel, dict(a["regel"]), herkunft))
    return betroffen


def _aendern(
    conn: Verbindung, ziel: str, basis: str, a: dict[str, Any], herkunft: str, begruendung: str
) -> int:
    name = str(a["regel_name"])
    z = conn.execute(
        "SELECT id, parameter FROM meta.regel WHERE regelsatz = %s AND name = %s AND aktiv FOR UPDATE",
        (ziel, name),
    ).fetchone()
    if z is None:
        raise RegelKonflikt(f"Regel {name} fehlt im Regelsatz {ziel}")
    regel_id = int(str(z["id"]))
    if z["parameter"] == a["parameter_neu"]:
        return regel_id  # schon eingespielt
    if z["parameter"] != a["parameter_alt"]:
        raise RegelKonflikt(
            f"Regel {name} in {ziel} hat inzwischen andere Parameter als beim Vorschlag; bitte neu vorschlagen"
        )
    conn.execute(
        """UPDATE meta.regel r SET parameter = %(neu)s::jsonb, begruendung = %(b)s,
                  grundlage = r.grundlage || '; ' || %(h)s,
                  -- die alte Freigabe gilt nicht für die neue Fassung (meta.regel_historie hält sie fest);
                  -- `anwenden` setzt in derselben Transaktion die neue Freigabe mit Namen
                  freigegeben_von = NULL, freigegeben_am = NULL,
                  ersetzt_regel_id = coalesce(r.ersetzt_regel_id,
                      (SELECT b.id FROM meta.regel b WHERE b.regelsatz = %(basis)s AND b.name = r.name
                         AND b.regelsatz <> r.regelsatz))
           WHERE r.id = %(id)s""",
        {
            "neu": json.dumps(a["parameter_neu"]),
            "b": begruendung,
            "h": herkunft,
            "basis": basis,
            "id": regel_id,
        },
    )
    return regel_id


def _neu(conn: Verbindung, ziel: str, regel: dict[str, Any], herkunft: str) -> int:
    z = conn.execute(
        "SELECT id, typ, art, parameter FROM meta.regel WHERE regelsatz = %s AND name = %s FOR UPDATE",
        (ziel, regel["name"]),
    ).fetchone()
    if z is not None:
        if (z["typ"], z["art"], z["parameter"]) == (regel["typ"], regel["art"], regel["parameter"]):
            return int(str(z["id"]))  # schon eingespielt
        raise RegelKonflikt(f"Regel {regel['name']} gibt es in {ziel} schon mit anderem Inhalt")
    neu = conn.execute(
        """INSERT INTO meta.regel (regelsatz, name, typ, art, reihenfolge, parameter, beschreibung, begruendung,
                                   grundlage, gueltig_ab_lieferung)
           VALUES (%(rs)s, %(name)s, %(typ)s, %(art)s, %(rf)s, %(p)s::jsonb, %(be)s, %(bg)s, %(g)s, %(ab)s)
           RETURNING id""",
        {
            "rs": ziel,
            "name": regel["name"],
            "typ": regel["typ"],
            "art": regel["art"],
            "rf": int(regel.get("reihenfolge", 100)),
            "p": json.dumps(regel["parameter"]),
            "be": regel["beschreibung"],
            "bg": regel["begruendung"],
            "g": f"{regel.get('grundlage') or 'Änderungsauftrag'}; {herkunft}",
            "ab": regel.get("gueltig_ab_lieferung") or "2024-08",
        },
    ).fetchone()
    assert neu is not None
    return int(str(neu["id"]))
