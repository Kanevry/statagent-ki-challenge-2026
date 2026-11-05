"""Schritt 3: Bestand eines Berichtsmonats zählen (Zählregeln aus meta.regel, Typ ``zaehl``).

Erzeugt zwei temporäre Tabellen in der laufenden Transaktion:
``_bestand`` (je Verhältnis eine Zeile mit den Merkmalen des gewählten Abschnitts und dem Alter) und
``_zellen`` (Long-Format wie stat.stat_beschaeftigte, ohne Status/Stand). Prüfungen lesen beide.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date

from psycopg import sql

from statagent.db import Verbindung
from statagent.ergebnis import monatserster, monatsletzter
from statagent.regeln import Regel, RegelFehler, eine


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
    p = eine(regeln, "zaehl", "bestand").parameter
    von, bis = _tag(str(p["von"]), berichtsmonat), _tag(str(p["bis"]), berichtsmonat)
    if von > bis:
        raise RegelFehler(f"Berichtszeitraum {von} nach {bis}")
    return Zeitraum(art=str(p["zeitraum_art"]), von=von, bis=bis)


_ORDNUNG = {
    "spaetester_beginn": sql.SQL(
        'a.beginn DESC, a.ende DESC NULLS FIRST, a.qualifikation COLLATE "C", a.oenace COLLATE "C", '
        'a.bundesland COLLATE "C", a.geschlecht COLLATE "C", a.geburtsdatum_status COLLATE "C"'
    ),
}


def zaehlen(
    conn: Verbindung, *, lieferung: str, berichtsmonat: str, regelsatz: str, regeln: list[Regel]
) -> Zaehlung:
    """Zählt den Bestand des Berichtsmonats aus bereinigt.abschnitt der Lieferung (Transaktion des Aufrufers)."""
    r_bestand = eine(regeln, "zaehl", "bestand")
    r_wahl = eine(regeln, "zaehl", "abschnittswahl")
    r_alter = eine(regeln, "zaehl", "alter")
    r_dim = eine(regeln, "zaehl", "dimension")
    zr = zeitraum(regeln, berichtsmonat)
    variable = str(r_bestand.parameter.get("variable", "Beschaeftigungsverhaeltnisse"))

    ordnung = _ORDNUNG.get(str(r_wahl.parameter.get("ordnung")))
    if ordnung is None:
        raise RegelFehler(f"{r_wahl.name}: unbekannte Ordnung {r_wahl.parameter.get('ordnung')!r}")

    pa = r_alter.parameter
    bezug = {"bis": zr.bis, "von": zr.von}.get(str(pa.get("bezug", "bis")))
    if bezug is None:
        raise RegelFehler(f"{r_alter.name}: bezug muss 'bis' oder 'von' sein")
    monat13 = str(pa.get("geburtsmonat_13", "unbekannt"))
    if monat13 not in ("jahresdifferenz", "unbekannt"):
        raise RegelFehler(f"{r_alter.name}: geburtsmonat_13 muss 'jahresdifferenz' oder 'unbekannt' sein")

    dim = str(r_dim.parameter.get("qualifikation", "code"))
    if dim == "code":
        qual_ausdruck = sql.SQL("b.qualifikation")
        qual_join = sql.SQL("")
    elif dim == "beschaeftigungskategorie":
        qual_ausdruck = sql.SQL("kq.beschaeftigungskategorie")
        qual_join = sql.SQL("JOIN stat.klass_qualifikation kq ON kq.code = b.qualifikation")
    else:
        raise RegelFehler(f"{r_dim.name}: qualifikation muss 'code' oder 'beschaeftigungskategorie' sein")

    conn.execute("DROP TABLE IF EXISTS _bestand")
    conn.execute("DROP TABLE IF EXISTS _zellen")
    conn.execute(
        sql.SQL(
            """
            CREATE TEMP TABLE _bestand ON COMMIT DROP AS
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
              END AS alter_roh) x
            """
        ).format(ordnung=ordnung),
        {
            "l": lieferung,
            "rs": regelsatz,
            "von": zr.von,
            "bis": zr.bis,
            "bezug": bezug,
            "m13": monat13,
            "amax": int(pa.get("max_plausibel", 200)),
            "amin": int(pa.get("min_plausibel", 0)),
        },
    )
    conn.execute(
        sql.SQL(
            """
            CREATE TEMP TABLE _zellen ON COMMIT DROP AS
            SELECT %(art)s::text AS zeitraum_art, %(von)s::date AS zeitraum_von, %(bis)s::date AS zeitraum_bis,
                   b.bundesland AS region, b.oenace, b.oenace_version, b.geschlecht,
                   {qual} AS qualifikation, b.alter_jahre AS alter, %(var)s::text AS variable, count(*)::bigint AS wert
            FROM _bestand b {join}
            GROUP BY 1, 2, 3, 4, 5, 6, 7, 8, 9, 10
            """
        ).format(qual=qual_ausdruck, join=qual_join),
        {"art": zr.art, "von": zr.von, "bis": zr.bis, "var": variable},
    )
    kennzahlen = conn.execute(
        """
        SELECT (SELECT count(*) FROM _bestand) AS gezaehlt, count(*) AS zellen, coalesce(sum(wert), 0) AS summe,
               encode(sha256(convert_to(coalesce(string_agg(
                 concat_ws('|', zeitraum_art, zeitraum_von, zeitraum_bis, region, oenace, oenace_version, geschlecht,
                           qualifikation, alter, variable, wert),
                 E'\\n' ORDER BY zeitraum_art COLLATE "C", zeitraum_von, zeitraum_bis, region COLLATE "C",
                   oenace COLLATE "C", oenace_version COLLATE "C", geschlecht COLLATE "C",
                   qualifikation COLLATE "C", alter, variable COLLATE "C"), ''), 'UTF8')), 'hex') AS hash
        FROM _zellen
        """
    ).fetchone()
    assert kennzahlen is not None
    gezaehlt = int(str(kennzahlen["gezaehlt"]))
    if int(str(kennzahlen["summe"])) != gezaehlt:
        raise RegelFehler(f"Zellensumme {kennzahlen['summe']} ≠ gezählte Verhältnisse {gezaehlt}")
    return Zaehlung(
        zeitraum=zr,
        variable=variable,
        gezaehlt=gezaehlt,
        zellen=int(str(kennzahlen["zellen"])),
        ergebnis_hash=str(kennzahlen["hash"]),
    )
