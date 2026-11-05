"""Schritt 1: eine Lieferung einlesen und bereinigen (Einlese- und Zuordnungsregeln aus meta.regel).

Ergebnis ist ``bereinigt.abschnitt`` für (Lieferung, Regelsatz). Kein Satz geht verloren: Volldubletten
werden verdichtet und gezählt, unklare Werte zugeordnet und in ``korrekturen`` markiert.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from psycopg import sql

from statagent.db import Verbindung
from statagent.ergebnis import monat_verschieben, monatserster, monatsletzter
from statagent.regeln import Regel, RegelFehler, eine, hoechstens_eine

MERKMALE = ("geschlecht", "qualifikation", "oenace", "bundesland")


@dataclass
class Bereinigung:
    gelesen: int
    abschnitte: int
    ausgeschlossen: int  # als Volldublette verdichtete Zeilen
    korrigiert: int  # Abschnitte, die eine Einlese- oder Zuordnungsregel verändert hat
    spaltentausch: bool
    oenace_version: str
    wirkung: dict[int, int] = field(default_factory=dict)  # regel_id -> betroffene Sätze


def oenace_version(conn: Verbindung, regeln: list[Regel], stichtag: date) -> str:
    """ÖNACE-Version, die laut stat.klass_oenace am Stichtag gilt (Regel R7, Art klassifikationsversion)."""
    regel = eine(regeln, "zaehl", "klassifikationsversion")
    if regel.parameter.get("merkmal") != "oenace" or regel.parameter.get("nach") != "berichtsmonat":
        raise RegelFehler(f"{regel.name}: nicht unterstützte Parameter {regel.parameter}")
    zeilen = conn.execute(
        """SELECT DISTINCT version FROM stat.klass_oenace
           WHERE ebene = 1 AND gueltig_von <= %(s)s AND (gueltig_bis IS NULL OR gueltig_bis >= %(s)s)""",
        {"s": stichtag},
    ).fetchall()
    if len(zeilen) != 1:
        raise RegelFehler(
            f"am {stichtag} gilt nicht genau eine ÖNACE-Version: {[z['version'] for z in zeilen]}"
        )
    return str(zeilen[0]["version"])


def _spaltentausch_noetig(conn: Verbindung, lieferung: str, regel: Regel | None) -> bool:
    if regel is None:
        return False
    p = regel.parameter
    z = conn.execute(
        """
        SELECT avg((beginn IS NULL)::int)::float AS leer,
               avg((pg_input_is_valid(beginn, 'date') AND pg_input_is_valid(ende, 'date')
                    AND beginn::date > ende::date)::int)::float AS nach_ende
        FROM roh.lieferung WHERE lieferung = %s
        """,
        (lieferung,),
    ).fetchone()
    if z is None or z["leer"] is None:
        return False
    leer, nach_ende = float(str(z["leer"])), float(str(z["nach_ende"]))
    return leer > float(p["anteil_beginn_leer_min"]) and nach_ende > float(p["anteil_beginn_nach_ende_min"])


def bereinigen(
    conn: Verbindung, *, lauf_id: int, lieferung: str, regelsatz: str, regeln: list[Regel]
) -> Bereinigung:
    """Baut bereinigt.abschnitt für (lieferung, regelsatz) neu auf. Läuft in der Transaktion des Aufrufers."""
    r_tausch = hoechstens_eine(regeln, "einlese", "spaltentausch")
    r_dublette = hoechstens_eine(regeln, "einlese", "dublette")
    r_datum = hoechstens_eine(regeln, "einlese", "datum")
    r_beginn = hoechstens_eine(regeln, "einlese", "ersatz_beginn")
    r_qz = eine(regeln, "einlese", "quellzuordnung")
    stichtag = monatsletzter(lieferung)
    version = oenace_version(conn, regeln, stichtag)
    tausch = _spaltentausch_noetig(conn, lieferung, r_tausch)

    gelesen_z = conn.execute(
        "SELECT count(*) AS n FROM roh.lieferung WHERE lieferung = %s", (lieferung,)
    ).fetchone()
    gelesen = int(str(gelesen_z["n"])) if gelesen_z else 0
    if gelesen == 0:
        raise RegelFehler(f"Lieferung {lieferung} enthält keine Sätze")

    beginn_spalte, ende_spalte = ("ende", "beginn") if tausch else ("beginn", "ende")
    if r_dublette is not None:
        if r_dublette.parameter.get("vergleich") != "alle_felder":
            raise RegelFehler(f"{r_dublette.name}: nicht unterstützter Vergleich {r_dublette.parameter}")
        quelle = sql.SQL(
            """SELECT vvh_id, person_id, geburtsdatum, geschlecht, beginn, ende, qual, oenace, bundesland,
                      count(*)::int AS roh_zeilen
               FROM roh.lieferung WHERE lieferung = %(l)s
               GROUP BY vvh_id, person_id, geburtsdatum, geschlecht, beginn, ende, qual, oenace, bundesland"""
        )
    else:
        quelle = sql.SQL(
            """SELECT vvh_id, person_id, geburtsdatum, geschlecht, beginn, ende, qual, oenace, bundesland,
                      1 AS roh_zeilen
               FROM roh.lieferung WHERE lieferung = %(l)s"""
        )

    monat13 = r_datum is not None and r_datum.parameter.get("geburtsmonat_13") == "geburtsjahr_behalten"
    fenster_monate = int(r_beginn.parameter.get("fenster_monate", 3)) if r_beginn else 0
    fensterbeginn = monatserster(monat_verschieben(lieferung, -(fenster_monate - 1))) if r_beginn else None
    qz_quelle = str(r_qz.parameter.get("quelle", "zvd"))

    joins = []
    codes = {}
    regel_ids = {}
    for m in MERKMALE:
        v = version if m == "oenace" else "-"
        roh_feld = "qual" if m == "qualifikation" else m
        joins.append(
            sql.SQL(
                """LEFT JOIN stat.quellzuordnung {q} ON {q}.quelle = %(qz)s AND {q}.merkmal = {m}
                     AND {q}.version = {v} AND {q}.geliefert = coalesce(t.{f}, '<leer>')
                   LEFT JOIN stat.quellzuordnung {s} ON {s}.quelle = %(qz)s AND {s}.merkmal = {m}
                     AND {s}.version = {v} AND {s}.geliefert = '<sonst>'"""
            ).format(
                q=sql.Identifier(f"q_{m}"),
                s=sql.Identifier(f"s_{m}"),
                m=sql.Literal(m),
                v=sql.Literal(v),
                f=sql.Identifier(roh_feld),
            )
        )
        codes[m] = sql.SQL("coalesce({q}.code, {s}.code)").format(
            q=sql.Identifier(f"q_{m}"), s=sql.Identifier(f"s_{m}")
        )
        regel_ids[m] = sql.SQL(
            "CASE WHEN {q}.code IS NOT NULL THEN {q}.regel_id ELSE {s}.regel_id END"
        ).format(q=sql.Identifier(f"q_{m}"), s=sql.Identifier(f"s_{m}"))

    tausch_name = sql.Literal(r_tausch.name if (r_tausch and tausch) else None)
    beginn_name = sql.Literal(r_beginn.name if r_beginn else None)
    abfrage = sql.SQL(
        """
        WITH r AS ({quelle}),
        t AS (
          SELECT r.*,
            {beginn_t} AS beginn_t, {ende_t} AS ende_t,
            CASE WHEN pg_input_is_valid(r.geburtsdatum, 'date') THEN r.geburtsdatum::date END AS geb,
            CASE WHEN pg_input_is_valid(r.geburtsdatum, 'date') THEN 'gueltig'
                 WHEN %(m13)s AND r.geburtsdatum ~ '^\\d{{4}}-13-\\d{{2}}$' THEN 'monat_13'
                 ELSE 'ungueltig' END AS geb_status
          FROM r
        ),
        u AS (
          SELECT t.*,
            CASE WHEN pg_input_is_valid(t.beginn_t, 'date') THEN t.beginn_t::date END AS beg,
            CASE WHEN pg_input_is_valid(t.ende_t, 'date') THEN t.ende_t::date END AS end_d
          FROM t
        ),
        z AS (
          SELECT t.*,
            {code_g} AS c_geschlecht, {code_q} AS c_qualifikation, {code_o} AS c_oenace, {code_b} AS c_bundesland,
            ARRAY[{rid_g}, {rid_q}, {rid_o}, {rid_b}] AS qz_regeln
          FROM u t
          {joins}
        )
        INSERT INTO bereinigt.abschnitt (lieferung, regelsatz, lauf_id, vvh_id, person_id, geburtsdatum, geburtsjahr,
            geburtsdatum_status, geschlecht, beginn, ende, qualifikation, oenace, oenace_version, bundesland,
            roh_zeilen, korrekturen, roh_oenace, roh_bundesland)
        SELECT %(l)s, %(rs)s, %(lauf)s, z.vvh_id::bigint, z.person_id::bigint, z.geb,
               CASE WHEN z.geb_status = 'gueltig' THEN extract(year FROM z.geb)::int
                    WHEN z.geb_status = 'monat_13' THEN substr(z.geburtsdatum, 1, 4)::int END,
               z.geb_status, z.c_geschlecht,
               coalesce(z.beg, %(fb)s::date),
               z.end_d,
               z.c_qualifikation, z.c_oenace, %(ver)s, z.c_bundesland, z.roh_zeilen,
               array_remove(ARRAY[{tausch_name}::text,
                                  CASE WHEN z.beg IS NULL THEN {beginn_name}::text END]
                            || coalesce((SELECT array_agg(g.name ORDER BY g.name) FROM meta.regel g
                                         WHERE g.id = ANY(z.qz_regeln)), '{{}}'), NULL),
               z.oenace, z.bundesland
        FROM z
        """
    ).format(
        quelle=quelle,
        beginn_t=sql.Identifier("r", beginn_spalte),
        ende_t=sql.Identifier("r", ende_spalte),
        code_g=codes["geschlecht"],
        code_q=codes["qualifikation"],
        code_o=codes["oenace"],
        code_b=codes["bundesland"],
        rid_g=regel_ids["geschlecht"],
        rid_q=regel_ids["qualifikation"],
        rid_o=regel_ids["oenace"],
        rid_b=regel_ids["bundesland"],
        joins=sql.SQL("\n").join(joins),
        tausch_name=tausch_name,
        beginn_name=beginn_name,
    )

    conn.execute(
        "DELETE FROM bereinigt.abschnitt WHERE lieferung = %s AND regelsatz = %s", (lieferung, regelsatz)
    )
    conn.execute(
        abfrage,
        {
            "l": lieferung,
            "rs": regelsatz,
            "lauf": lauf_id,
            "m13": monat13,
            "fb": fensterbeginn,
            "ver": version,
            "qz": qz_quelle,
        },
    )

    fehlt = conn.execute(
        """SELECT count(*) AS n FROM bereinigt.abschnitt
           WHERE lieferung = %s AND regelsatz = %s AND (geschlecht IS NULL OR qualifikation IS NULL
             OR oenace IS NULL OR bundesland IS NULL)""",
        (lieferung, regelsatz),
    ).fetchone()
    if fehlt and int(str(fehlt["n"])) > 0:
        raise RegelFehler("Quellzuordnung unvollständig: Abschnitte ohne Code (fehlt eine '<sonst>'-Zeile?)")

    summe = conn.execute(
        """SELECT count(*) AS abschnitte, coalesce(sum(roh_zeilen - 1), 0) AS dubletten,
                  count(*) FILTER (WHERE cardinality(korrekturen) > 0) AS korrigiert,
                  count(*) FILTER (WHERE geburtsdatum_status = 'monat_13') AS monat13
           FROM bereinigt.abschnitt WHERE lieferung = %s AND regelsatz = %s""",
        (lieferung, regelsatz),
    ).fetchone()
    assert summe is not None
    abschnitte = int(str(summe["abschnitte"]))
    ausgeschlossen = int(str(summe["dubletten"]))
    if abschnitte + ausgeschlossen != gelesen:
        raise RegelFehler(f"Bereinigung verliert Sätze: {gelesen} gelesen, {abschnitte} + {ausgeschlossen}")

    wirkung: dict[int, int] = {}
    if r_tausch is not None and tausch:
        wirkung[r_tausch.id] = gelesen
    if r_dublette is not None:
        wirkung[r_dublette.id] = ausgeschlossen
    if r_datum is not None:
        wirkung[r_datum.id] = int(str(summe["monat13"]))
    namen = conn.execute(
        """SELECT k.name, count(*) AS n FROM bereinigt.abschnitt a, unnest(a.korrekturen) AS k(name)
           WHERE a.lieferung = %s AND a.regelsatz = %s GROUP BY k.name""",
        (lieferung, regelsatz),
    ).fetchall()
    nach_name = {r.name: r.id for r in regeln}
    for z in namen:
        rid = nach_name.get(str(z["name"]))
        if rid is not None and rid not in wirkung:
            wirkung[rid] = int(str(z["n"]))
    wirkung.setdefault(r_qz.id, abschnitte)

    return Bereinigung(
        gelesen=gelesen,
        abschnitte=abschnitte,
        ausgeschlossen=ausgeschlossen,
        korrigiert=int(str(summe["korrigiert"])),
        spaltentausch=tausch,
        oenace_version=version,
        wirkung=wirkung,
    )
