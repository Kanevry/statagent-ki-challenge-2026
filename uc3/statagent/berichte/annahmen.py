"""Annahmen F1 bis F10 (meta.annahme): was gilt, bis die Fachabteilung antwortet.

Je Annahme ein einfacher Satz, eine Begründung, die umsetzende Regel mit ihrer Wirkung im maßgeblichen Lauf
des Monats und, falls eine Rückfrage zugeordnet ist, deren Beleg-Abfrage. Kein Sprachmodell, nur Daten.
"""

from __future__ import annotations

from statagent import ergebnis
from statagent.db import Verbindung


def _hat_tabelle(conn: Verbindung, name: str) -> bool:
    zeile = conn.execute("SELECT to_regclass(%s) IS NOT NULL AS da", (name,)).fetchone()
    return bool(zeile and zeile["da"])


def annahmen(conn: Verbindung, lieferung: str, regelsatz: str = "v1") -> list[dict[str, object]]:
    """Annahmen, die für `lieferung` gelten, sortiert nach Nummer (F1, F2, …, F10).

    Felder: nr, rueckfrage, satz, grund, begruendung, regel_name, wirkung_saetze (meta.regel_wirkung des
    maßgeblichen Laufs für regel_name, sonst None), beleg_sql (meta.rueckfrage.beleg_sql, sonst None).
    `satz` endet mit „Grund: …“ (Spalte `grund`), damit Qualitätsbericht und CLI die Begründung zeigen, ohne
    ein eigenes Feld zu kennen; `grund` steht zusätzlich einzeln da.
    """
    if not _hat_tabelle(conn, "meta.annahme"):
        return []
    mit_rueckfrage = _hat_tabelle(conn, "meta.rueckfrage")
    stand = ergebnis.letzter_lauf(conn, lieferung, regelsatz)
    zeilen = conn.execute(
        f"""SELECT a.nr, a.rueckfrage, a.satz, a.grund, a.begruendung, a.regel_name,
                   (SELECT sum(w.saetze) FROM meta.regel_wirkung w JOIN meta.regel r ON r.id = w.regel_id
                    WHERE w.lauf_id = %(lauf)s AND r.name = a.regel_name) AS wirkung_saetze,
                   {
            "(SELECT q.beleg_sql FROM meta.rueckfrage q WHERE q.nr = a.rueckfrage)"
            if mit_rueckfrage
            else "NULL::text"
        } AS beleg_sql
            FROM meta.annahme a
            WHERE a.lieferungen IS NULL OR %(l)s = ANY (a.lieferungen)
            ORDER BY length(a.nr), a.nr""",
        {"lauf": stand.lauf_id if stand else None, "l": lieferung},
    ).fetchall()
    return [
        {
            "nr": z["nr"],
            "rueckfrage": z["rueckfrage"],
            "satz": f"{z['satz']} Grund: {z['grund']}" if z["grund"] else z["satz"],
            "grund": z["grund"],
            "begruendung": z["begruendung"],
            "regel_name": z["regel_name"],
            "wirkung_saetze": None if z["wirkung_saetze"] is None else int(str(z["wirkung_saetze"])),
            "beleg_sql": z["beleg_sql"],
        }
        for z in zeilen
    ]
