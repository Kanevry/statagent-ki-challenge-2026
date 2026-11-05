"""Schritt 3: Bestand eines Berichtsmonats zählen (Zählregeln aus meta.regel, Typ ``zaehl``).

Erzeugt zwei temporäre Tabellen in der laufenden Transaktion:
``<praefix>bestand`` (Standard ``_bestand``; je Verhältnis eine Zeile mit den Merkmalen des gewählten Abschnitts und dem Alter) und
``<praefix>zellen`` (Long-Format wie stat.stat_beschaeftigte, ohne Status/Stand). Prüfungen lesen beide.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date

from psycopg import sql

from statagent.db import Verbindung
from statagent.ergebnis import monatserster, monatsletzter
from statagent.regeln import Regel, RegelFehler, eine, wert


@dataclass(frozen=True)
class Zeitraum:
    art: str
    von: date
    bis: date


@dataclass(frozen=True)
class Zaehlung:
    zeitraum: Zeitraum
    variable: str
    gezaehlt: int  # Verhältnisse (je VVH_ID einmal)
    aktive_abschnitte: int  # Abschnitte, die im Berichtszeitraum bestehen (vor der Abschnittswahl)
    nicht_aktiv: int  # Abschnitte ohne Bestand im Berichtszeitraum
    mehrfach: int  # Verhältnisse mit mehr als einem aktiven Abschnitt
    alter_unbekannt: int  # Verhältnisse mit Alter unbekannt (-1)
    zellen: int
    ergebnis_hash: str


def _tag(token: str, berichtsmonat: str) -> date:
    if token == "monatserster":
        return monatserster(berichtsmonat)
    if token == "monatsletzter":
        return monatsletzter(berichtsmonat)
    treffer = re.fullmatch(r"tag:(\d{1,2})", token)
    if treffer:
        letzter = monatsletzter(berichtsmonat)
        return letzter.replace(day=min(int(treffer.group(1)), letzter.day))
    raise RegelFehler(f"unbekannte Tagesangabe '{token}' (erlaubt: monatserster, monatsletzter, tag:N)")


def zeitraum(regeln: list[Regel], berichtsmonat: str) -> Zeitraum:
    r = eine(regeln, "zaehl", "bestand")
    von, bis = _tag(str(wert(r, "von")), berichtsmonat), _tag(str(wert(r, "bis")), berichtsmonat)
    if von > bis:
        raise RegelFehler(f"Berichtszeitraum {von} nach {bis}")
    return Zeitraum(art=str(wert(r, "zeitraum_art")), von=von, bis=bis)


_ORDNUNG = {
    "spaetester_beginn": sql.SQL(
        'a.beginn DESC, a.ende DESC NULLS FIRST, a.qualifikation COLLATE "C", a.oenace COLLATE "C", '
        'a.bundesland COLLATE "C", a.geschlecht COLLATE "C", a.geburtsdatum_status COLLATE "C", '
        "a.geburtsdatum NULLS LAST, a.geburtsjahr NULLS LAST, a.person_id NULLS LAST, a.roh_zeilen"
    ),
}


def zaehlen(
    conn: Verbindung,
    *,
    lieferung: str,
    berichtsmonat: str,
    regelsatz: str,
    regeln: list[Regel],
    praefix: str = "_",
) -> Zaehlung:
    """Zählt den Bestand des Berichtsmonats aus bereinigt.abschnitt der Lieferung (Transaktion des Aufrufers)."""
    r_bestand = eine(regeln, "zaehl", "bestand")
    r_wahl = eine(regeln, "zaehl", "abschnittswahl")
    r_alter = eine(regeln, "zaehl", "alter")
    r_dim = eine(regeln, "zaehl", "dimension")
    zr = zeitraum(regeln, berichtsmonat)
    variable = str(wert(r_bestand, "variable"))

    ordnung = _ORDNUNG.get(str(wert(r_wahl, "ordnung")))
    if ordnung is None:
        raise RegelFehler(f"{r_wahl.name}: unbekannte Ordnung {r_wahl.parameter.get('ordnung')!r}")

    bezug = {"bis": zr.bis, "von": zr.von}.get(str(wert(r_alter, "bezug")))
    if bezug is None:
        raise RegelFehler(f"{r_alter.name}: bezug muss 'bis' oder 'von' sein")
    monat13 = str(wert(r_alter, "geburtsmonat_13"))
    ersatz = re.fullmatch(r"ersatz:(\d{2})-(\d{2})", monat13)
    if monat13 not in ("jahresdifferenz", "unbekannt") and ersatz is None:
        raise RegelFehler(
            f"{r_alter.name}: geburtsmonat_13 muss 'jahresdifferenz', 'unbekannt' oder 'ersatz:MM-TT' sein"
        )
    ersatz_monat, ersatz_tag = (int(ersatz.group(1)), int(ersatz.group(2))) if ersatz else (0, 0)

    dim = str(wert(r_dim, "qualifikation"))
    if dim == "code":
        qual_ausdruck = sql.SQL("b.qualifikation")
        qual_join = sql.SQL("")
    elif dim == "beschaeftigungskategorie":
        qual_ausdruck = sql.SQL("kq.beschaeftigungskategorie")
        qual_join = sql.SQL("JOIN stat.klass_qualifikation kq ON kq.code = b.qualifikation")
    else:
        raise RegelFehler(f"{r_dim.name}: qualifikation muss 'code' oder 'beschaeftigungskategorie' sein")

    if praefix not in ("_", "_rev_", "_alt_"):
        raise ValueError(f"unzulässiges Tabellen-Präfix {praefix!r}")
    t_bestand, t_zellen = sql.Identifier(f"{praefix}bestand"), sql.Identifier(f"{praefix}zellen")
    conn.execute(sql.SQL("DROP TABLE IF EXISTS {}").format(t_bestand))
    conn.execute(sql.SQL("DROP TABLE IF EXISTS {}").format(t_zellen))
    conn.execute(
        sql.SQL(
            """
            CREATE TEMP TABLE {t_bestand} ON COMMIT DROP AS
            WITH w AS (
              SELECT DISTINCT ON (a.vvh_id) a.*
              FROM bereinigt.abschnitt a
              WHERE a.lieferung = %(l)s AND a.regelsatz = %(rs)s
                AND a.beginn <= %(bis)s AND (a.ende IS NULL OR a.ende >= %(von)s)
              ORDER BY a.vvh_id, {ordnung}
            )
            SELECT w.*,
              CASE WHEN x.alter_roh IS NULL OR x.alter_roh > %(amax)s OR x.alter_roh < %(amin)s THEN -1
                   ELSE x.alter_roh END AS alter_jahre,
              x.alter_roh
            FROM w
            CROSS JOIN LATERAL (SELECT
              CASE WHEN w.geburtsdatum IS NOT NULL THEN extract(year FROM age(%(bezug)s::date, w.geburtsdatum))::int
                   WHEN w.geburtsdatum_status = 'monat_13' AND %(m13)s = 'jahresdifferenz'
                     THEN extract(year FROM %(bezug)s::date)::int - w.geburtsjahr
                   WHEN w.geburtsdatum_status = 'monat_13' AND %(em)s > 0
                     THEN extract(year FROM age(%(bezug)s::date, make_date(w.geburtsjahr, %(em)s, %(et)s)))::int
              END AS alter_roh) x
            """
        ).format(ordnung=ordnung, t_bestand=t_bestand),
        {
            "l": lieferung,
            "rs": regelsatz,
            "von": zr.von,
            "bis": zr.bis,
            "bezug": bezug,
            "m13": monat13,
            "em": ersatz_monat,
            "et": ersatz_tag,
            "amax": int(wert(r_alter, "max_plausibel")),
            "amin": int(wert(r_alter, "min_plausibel")),
        },
    )
    conn.execute(
        sql.SQL(
            """
            CREATE TEMP TABLE {t_zellen} ON COMMIT DROP AS
            SELECT %(art)s::text AS zeitraum_art, %(von)s::date AS zeitraum_von, %(bis)s::date AS zeitraum_bis,
                   b.bundesland AS region, b.oenace, b.oenace_version, b.geschlecht,
                   {qual} AS qualifikation, b.alter_jahre AS alter, %(var)s::text AS variable, count(*)::bigint AS wert
            FROM {t_bestand} b {join}
            GROUP BY 1, 2, 3, 4, 5, 6, 7, 8, 9, 10
            """
        ).format(qual=qual_ausdruck, join=qual_join, t_bestand=t_bestand, t_zellen=t_zellen),
        {"art": zr.art, "von": zr.von, "bis": zr.bis, "var": variable},
    )
    # Nur gelieferte Abschnitte (ohne Fortschreibung E07): Prüfungen erkennen daran einen Lieferausfall.
    t_geliefert = sql.Identifier(f"{praefix}zellen_geliefert")
    conn.execute(sql.SQL("DROP TABLE IF EXISTS {}").format(t_geliefert))
    conn.execute(
        sql.SQL(
            """
            CREATE TEMP TABLE {t_geliefert} ON COMMIT DROP AS
            SELECT b.bundesland AS region, b.oenace, b.oenace_version, b.geschlecht, {qual} AS qualifikation,
                   b.alter_jahre AS alter, count(*)::bigint AS wert
            FROM {t_bestand} b {join} WHERE b.herkunft = 'geliefert'
            GROUP BY 1, 2, 3, 4, 5, 6
            """
        ).format(qual=qual_ausdruck, join=qual_join, t_bestand=t_bestand, t_geliefert=t_geliefert)
    )
    # Temporäre Tabellen haben keine Statistik; ohne ANALYZE plant PostgreSQL Anti-Joins als verschachtelte Schleifen.
    conn.execute(sql.SQL("CREATE INDEX ON {} (vvh_id)").format(t_bestand))
    conn.execute(sql.SQL("ANALYZE {}").format(t_bestand))
    conn.execute(sql.SQL("ANALYZE {}").format(t_zellen))
    kennzahlen = conn.execute(
        sql.SQL(
            """
        SELECT (SELECT count(*) FROM {t_bestand}) AS gezaehlt, count(*) AS zellen, coalesce(sum(wert), 0) AS summe,
               encode(sha256(convert_to(coalesce(string_agg(
                 concat_ws('|', zeitraum_art, zeitraum_von, zeitraum_bis, region, oenace, oenace_version, geschlecht,
                           qualifikation, alter, variable, wert),
                 E'\\n' ORDER BY zeitraum_art COLLATE "C", zeitraum_von, zeitraum_bis, region COLLATE "C",
                   oenace COLLATE "C", oenace_version COLLATE "C", geschlecht COLLATE "C",
                   qualifikation COLLATE "C", alter, variable COLLATE "C"), ''), 'UTF8')), 'hex') AS hash
        FROM {t_zellen}
        """
        ).format(t_bestand=t_bestand, t_zellen=t_zellen)
    ).fetchone()
    assert kennzahlen is not None
    gezaehlt = int(str(kennzahlen["gezaehlt"]))
    if int(str(kennzahlen["summe"])) != gezaehlt:
        raise RegelFehler(f"Zellensumme {kennzahlen['summe']} ≠ gezählte Verhältnisse {gezaehlt}")
    # Unabhängig von der Abschnittswahl gezählt (Abrechnung, Qualitätsbericht § 1).
    abschnitte = conn.execute(
        sql.SQL(
            """
            SELECT count(*) FILTER (WHERE a.beginn <= %(bis)s AND (a.ende IS NULL OR a.ende >= %(von)s)) AS aktiv,
                   count(*) FILTER (WHERE NOT (a.beginn <= %(bis)s AND (a.ende IS NULL OR a.ende >= %(von)s)))
                     AS nicht_aktiv,
                   (SELECT count(*) FROM (
                      SELECT a2.vvh_id FROM bereinigt.abschnitt a2
                      WHERE a2.lieferung = %(l)s AND a2.regelsatz = %(rs)s
                        AND a2.beginn <= %(bis)s AND (a2.ende IS NULL OR a2.ende >= %(von)s)
                      GROUP BY a2.vvh_id HAVING count(*) > 1) m) AS mehrfach,
                   (SELECT count(*) FROM {t_bestand} WHERE alter_jahre = -1) AS alter_unbekannt
            FROM bereinigt.abschnitt a WHERE a.lieferung = %(l)s AND a.regelsatz = %(rs)s
            """
        ).format(t_bestand=t_bestand),
        {"l": lieferung, "rs": regelsatz, "von": zr.von, "bis": zr.bis},
    ).fetchone()
    assert abschnitte is not None
    return Zaehlung(
        zeitraum=zr,
        variable=variable,
        gezaehlt=gezaehlt,
        aktive_abschnitte=int(str(abschnitte["aktiv"])),
        nicht_aktiv=int(str(abschnitte["nicht_aktiv"])),
        mehrfach=int(str(abschnitte["mehrfach"])),
        alter_unbekannt=int(str(abschnitte["alter_unbekannt"])),
        zellen=int(str(kennzahlen["zellen"])),
        ergebnis_hash=str(kennzahlen["hash"]),
    )
