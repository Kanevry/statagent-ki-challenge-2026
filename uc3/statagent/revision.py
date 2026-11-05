"""Revisionsbedarf: ein Lauf rechnet die Vormonate aus seiner Lieferung nach (Fachbeschreibung § 4 Nr. 4).

Jede Lieferung ist ein Vollabzug über drei Monate. Für die zwei Vormonate im Fenster rechnet der Lauf den
Stichtagsbestand mit den aktuellen Regeln aus der eigenen Lieferung und vergleicht ihn mit dem Wert aus der
Lieferung des Berichtsmonats. Veröffentlichtes bleibt unverändert; die Differenz und ihre Ursachen stehen in
meta.revision / meta.revision_ursache und im Qualitätsbericht § 5. Nur eigene und frühere Lieferungen.
"""

from __future__ import annotations

import json

from psycopg import sql

from statagent import ergebnis
from statagent.db import Verbindung, lieferungen
from statagent.regeln import Regel
from statagent.zaehlung import zaehlen

#: Gliederungen des Vergleichs; ÖNACE nur, wenn beide Seiten dieselbe Version haben (Klassifikationswechsel).
GLIEDERUNGEN = {
    "region": "region",
    "geschlecht": "geschlecht",
    "qualifikation": "qualifikation",
    "oenace": "oenace",
}


def _vormonate(lieferung: str, vorhanden: list[str], fenster: int = 3) -> list[str]:
    return [m for k in range(1, fenster) if (m := ergebnis.monat_verschieben(lieferung, -k)) in vorhanden]


def revision_berechnen(
    conn: Verbindung, *, lauf_id: int, lieferung: str, regelsatz: str, regeln: list[Regel]
) -> list[str]:
    """Schreibt meta.revision und meta.revision_ursache für die Vormonate im Lieferfenster.

    Läuft in der Transaktion des Laufs, nach der Bereinigung der Lieferung. Liefert die verglichenen Monate.
    """
    verglichen: list[str] = []
    for monat in _vormonate(lieferung, lieferungen(conn)):
        stand = ergebnis.letzter_lauf(conn, monat, regelsatz)
        if stand is None:
            continue
        alt_zeilen = ergebnis.monatswerte(conn, monat, regelsatz)
        if not alt_zeilen:
            continue
        status_vorher = "endgueltig" if all(z["status"] == "endgueltig" for z in alt_zeilen) else "vorlaeufig"
        zaehlen(
            conn,
            lieferung=lieferung,
            berichtsmonat=monat,
            regelsatz=regelsatz,
            regeln=regeln,
            praefix="_rev_",
        )
        version_alt = {str(z["oenace_version"]) for z in alt_zeilen}
        version_neu = {
            str(z["oenace_version"])
            for z in conn.execute("SELECT DISTINCT oenace_version FROM _rev_zellen").fetchall()
        }
        gliederungen = dict(GLIEDERUNGEN)
        if version_alt != version_neu:
            gliederungen.pop("oenace")

        alt: dict[tuple[str, str], int] = {("insgesamt", "AT"): 0}
        for z in alt_zeilen:
            wert = int(str(z["wert"]))
            alt[("insgesamt", "AT")] += wert
            for g, spalte in gliederungen.items():
                schluessel = (g, str(z[spalte]))
                alt[schluessel] = alt.get(schluessel, 0) + wert
        neu: dict[tuple[str, str], int] = {("insgesamt", "AT"): 0}
        for z in conn.execute(
            "SELECT region, oenace, geschlecht, qualifikation, wert FROM _rev_zellen"
        ).fetchall():
            wert = int(str(z["wert"]))
            neu[("insgesamt", "AT")] += wert
            for g, spalte in gliederungen.items():
                schluessel = (g, str(z[spalte]))
                neu[schluessel] = neu.get(schluessel, 0) + wert
        with conn.cursor() as cur:
            cur.executemany(
                """INSERT INTO meta.revision (lauf_id, berichtsmonat, gliederung, schluessel, veroeffentlicht,
                     aktuell, status_vorher) VALUES (%s, %s, %s, %s, %s, %s, %s)""",
                [
                    (lauf_id, monat, g, k, alt.get((g, k), 0), neu.get((g, k), 0), status_vorher)
                    for (g, k) in sorted(set(alt) | set(neu))
                ],
            )

        # Ursachen auf Ebene der Verhältnisse: Bestand laut Lieferung des Monats gegen Bestand laut dieser Lieferung.
        zaehlen(
            conn, lieferung=monat, berichtsmonat=monat, regelsatz=regelsatz, regeln=regeln, praefix="_alt_"
        )
        merkmale = ["a.bundesland", "a.geschlecht", "a.qualifikation"] + (
            ["a.oenace"] if "oenace" in gliederungen else []
        )
        vergleich = sql.SQL(" OR ").join(
            sql.SQL("{} IS DISTINCT FROM {}").format(sql.SQL(m), sql.SQL(m.replace("a.", "n.")))
            for m in merkmale
        )
        ursachen = {
            "nachmeldung": sql.SQL(
                "SELECT n.vvh_id FROM _rev_bestand n WHERE NOT EXISTS (SELECT 1 FROM _alt_bestand a WHERE a.vvh_id = n.vvh_id)"
            ),
            "rueckwirkende_abmeldung": sql.SQL(
                """SELECT a.vvh_id FROM _alt_bestand a
                   WHERE NOT EXISTS (SELECT 1 FROM _rev_bestand n WHERE n.vvh_id = a.vvh_id)
                     AND EXISTS (SELECT 1 FROM bereinigt.abschnitt b
                                 WHERE b.lieferung = %(l)s AND b.regelsatz = %(rs)s AND b.vvh_id = a.vvh_id)"""
            ),
            "nicht_mehr_enthalten": sql.SQL(
                """SELECT a.vvh_id FROM _alt_bestand a
                   WHERE NOT EXISTS (SELECT 1 FROM bereinigt.abschnitt b
                                     WHERE b.lieferung = %(l)s AND b.regelsatz = %(rs)s AND b.vvh_id = a.vvh_id)"""
            ),
            "merkmal_geaendert": sql.SQL(
                "SELECT a.vvh_id FROM _alt_bestand a JOIN _rev_bestand n USING (vvh_id) WHERE {}"
            ).format(vergleich),
        }
        for ursache, abfrage in ursachen.items():
            treffer = conn.execute(
                sql.SQL(
                    """WITH t AS ({abfrage})
                       SELECT count(*) AS n,
                              coalesce((SELECT jsonb_agg(vvh_id ORDER BY vvh_id)
                                        FROM (SELECT vvh_id FROM t ORDER BY vvh_id LIMIT 5) b), '[]') AS beispiele
                       FROM t"""
                ).format(abfrage=abfrage),
                {"l": lieferung, "rs": regelsatz},
            ).fetchone()
            if treffer is None:
                continue
            beispiele = treffer["beispiele"] if isinstance(treffer["beispiele"], list) else []
            conn.execute(
                """INSERT INTO meta.revision_ursache (lauf_id, berichtsmonat, ursache, anzahl, beispiele)
                   VALUES (%s, %s, %s, %s, %s::jsonb)""",
                (lauf_id, monat, ursache, int(str(treffer["n"])), json.dumps(beispiele)),
            )
        conn.execute("DROP TABLE IF EXISTS _rev_bestand; DROP TABLE IF EXISTS _rev_zellen")
        conn.execute("DROP TABLE IF EXISTS _alt_bestand; DROP TABLE IF EXISTS _alt_zellen")
        verglichen.append(monat)
    return verglichen
