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
from statagent.regeln import Regel, RegelFehler, eine, hoechstens_eine, wert

MERKMALE = ("geschlecht", "qualifikation", "oenace", "bundesland")


@dataclass
class Bereinigung:
    gelesen: int
    abschnitte: int
    ausgeschlossen: int  # als Volldublette verdichtete Zeilen
    korrigiert: int  # Abschnitte, die eine Einlese- oder Zuordnungsregel verändert hat
    fortgeschrieben: int  # Abschnitte, die E07 aus der Vorlieferung ergänzt hat (nicht in gelesen enthalten)
    fortschreibung: dict[str, object]  # Auslöser und Umfang der Fortschreibung (leer, wenn keine)
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


def _gueltig(spalte: str) -> str:
    """SQL-Ausdruck: Text entspricht dem Datumsmuster der Regel E03 und ist ein gültiges Datum."""
    return f"({spalte} ~ %(muster)s AND pg_input_is_valid({spalte}, 'date'))"


def _spaltentausch_noetig(conn: Verbindung, lieferung: str, regel: Regel | None, muster: str) -> bool:
    if regel is None:
        return False
    z = conn.execute(
        f"""
        SELECT avg((beginn IS NULL)::int)::float AS leer,
               avg(({_gueltig("beginn")} AND {_gueltig("ende")} AND beginn::date > ende::date)::int)::float
                 AS nach_ende
        FROM roh.lieferung WHERE lieferung = %(l)s
        """.encode(),
        {"l": lieferung, "muster": muster},
    ).fetchone()
    if z is None or z["leer"] is None:
        return False
    leer, nach_ende = float(str(z["leer"])), float(str(z["nach_ende"]))
    return leer > float(wert(regel, "anteil_beginn_leer_min")) and nach_ende > float(
        wert(regel, "anteil_beginn_nach_ende_min")
    )


def _zuordnungen_pruefen(conn: Verbindung, regeln: list[Regel]) -> list[int]:
    """IDs der Zuordnungsregeln (aller Regelsätze) mit dem Namen einer aktiven Zuordnungsregel.

    Nur deren Zeilen in stat.quellzuordnung greifen (Identitätszeilen ohne Regel greifen immer). Prüft zugleich,
    dass Regeln mit `codes`/`ziel` genau diese Zeilen in der Quellzuordnung haben.
    """
    aktive = [r for r in regeln if r.typ == "zuordnung"]
    namen = [r.name for r in aktive]
    ids = [
        int(str(z["id"]))
        for z in conn.execute("SELECT id FROM meta.regel WHERE name = ANY(%s)", (namen,)).fetchall()
    ]
    for r in aktive:
        if "codes" not in r.parameter:
            continue
        z = conn.execute(
            """SELECT coalesce(array_agg(DISTINCT q.geliefert ORDER BY q.geliefert), '{}') AS geliefert,
                      coalesce(array_agg(DISTINCT q.code), '{}') AS ziele
               FROM stat.quellzuordnung q JOIN meta.regel g ON g.id = q.regel_id
               WHERE g.name = %s AND q.merkmal = %s AND q.regelsatz = %s""",
            (r.name, wert(r, "merkmal"), r.regelsatz),
        ).fetchone()
        assert z is not None
        geliefert = sorted(str(c) for c in z["geliefert"]) if isinstance(z["geliefert"], list) else []
        ziele = [str(c) for c in z["ziele"]] if isinstance(z["ziele"], list) else []
        if geliefert != sorted(str(c) for c in wert(r, "codes")) or ziele != [str(wert(r, "ziel"))]:
            raise RegelFehler(
                f"{r.name}: stat.quellzuordnung ({z['geliefert']} → {z['ziele']}) passt nicht zu den Parametern"
            )
    return ids


def _fortschreiben(
    conn: Verbindung, *, regel: Regel, lauf_id: int, lieferung: str, regelsatz: str, version: str
) -> tuple[int, dict[str, object]]:
    """Regel E07: bei belegtem Lieferausfall fehlende Verhältnisse einmalig aus der Vorlieferung ergänzen.

    Auslöser: mehr als ``schwelle_anteil_verschwunden`` der am Vormonats-Stichtag bestehenden Verhältnisse fehlen in
    der Lieferung ganz (Teil-Lieferung), oder eine Ausprägung von ``merkmal_auspraegung`` mit mehr als
    ``mindestens_vormonat`` Verhältnissen fällt auf 0 (dann nur diese). Übernommen werden nur gelieferte Abschnitte
    der Vorlieferung, die am neuen Stichtag gelten. Nur frühere Lieferungen, keine Hochrechnung.
    """
    if wert(regel, "quelle") != "vorlieferung":
        raise RegelFehler(f"{regel.name}: nicht unterstützte Quelle {regel.parameter.get('quelle')!r}")
    merkmal = str(wert(regel, "merkmal_auspraegung"))
    if merkmal not in MERKMALE:
        raise RegelFehler(f"{regel.name}: unbekanntes Merkmal {merkmal!r}")
    vormonat = monat_verschieben(lieferung, -1)
    p = {
        "l": lieferung,
        "vm": vormonat,
        "rs": regelsatz,
        "st": monatsletzter(lieferung),
        "st_vm": monatsletzter(vormonat),
    }
    m = sql.Identifier(merkmal)
    z = conn.execute(
        sql.SQL(
            """
            WITH vm AS (
              SELECT DISTINCT ON (v.vvh_id) v.vvh_id, v.{m} AS wert
              FROM bereinigt.abschnitt v
              WHERE v.lieferung = %(vm)s AND v.regelsatz = %(rs)s AND v.herkunft = 'geliefert'
                AND v.beginn <= %(st_vm)s AND (v.ende IS NULL OR v.ende >= %(st_vm)s)
              ORDER BY v.vvh_id, v.beginn DESC
            ),
            akt AS (
              SELECT {m} AS wert, count(*) AS n FROM bereinigt.abschnitt
              WHERE lieferung = %(l)s AND regelsatz = %(rs)s AND herkunft = 'geliefert' GROUP BY 1
            )
            SELECT (SELECT count(*) FROM vm) AS basis,
                   (SELECT count(*) FROM vm WHERE NOT EXISTS (
                      SELECT 1 FROM bereinigt.abschnitt a
                      WHERE a.lieferung = %(l)s AND a.regelsatz = %(rs)s AND a.vvh_id = vm.vvh_id)) AS fehlend,
                   coalesce((SELECT jsonb_agg(w ORDER BY w) FROM (
                      SELECT vm.wert AS w FROM vm GROUP BY vm.wert
                      HAVING count(*) > %(min)s
                         AND NOT EXISTS (SELECT 1 FROM akt WHERE akt.wert = vm.wert)) x), '[]') AS ausgefallen
            """
        ).format(m=m),
        {**p, "min": int(wert(regel, "mindestens_vormonat"))},
        prepare=False,
    ).fetchone()
    if z is None or int(str(z["basis"])) < int(wert(regel, "mindestens_basis")):
        return 0, {}  # zu kleiner Vormonatsbestand: ein Anteil sagt nichts über einen Lieferausfall
    basis, fehlend = int(str(z["basis"])), int(str(z["fehlend"]))
    ausgefallen = [str(w) for w in z["ausgefallen"]] if isinstance(z["ausgefallen"], list) else []
    teil = fehlend / basis > float(wert(regel, "schwelle_anteil_verschwunden"))
    if not teil and not ausgefallen:
        return 0, {}
    vm_version = conn.execute(
        "SELECT min(oenace_version) AS v FROM bereinigt.abschnitt WHERE lieferung = %s AND regelsatz = %s",
        (vormonat, regelsatz),
    ).fetchone()
    if vm_version is None or vm_version["v"] != version:
        raise RegelFehler(
            f"{regel.name}: Fortschreibung über einen ÖNACE-Versionswechsel ist nicht vorgesehen"
        )
    auswahl = sql.SQL("TRUE") if teil else sql.SQL("v.{m} = ANY(%(werte)s)").format(m=m)
    eingefuegt = conn.execute(
        sql.SQL(
            """
            INSERT INTO bereinigt.abschnitt (lieferung, regelsatz, lauf_id, vvh_id, person_id, geburtsdatum,
                geburtsjahr, geburtsdatum_status, geschlecht, beginn, ende, qualifikation, oenace, oenace_version,
                bundesland, roh_zeilen, korrekturen, roh_oenace, roh_bundesland, herkunft)
            SELECT %(l)s, %(rs)s, %(lauf)s, v.vvh_id, v.person_id, v.geburtsdatum, v.geburtsjahr,
                   v.geburtsdatum_status, v.geschlecht, v.beginn, v.ende, v.qualifikation, v.oenace, v.oenace_version,
                   v.bundesland, 1, v.korrekturen || %(name)s::text, v.roh_oenace, v.roh_bundesland, 'fortgeschrieben'
            FROM bereinigt.abschnitt v
            WHERE v.lieferung = %(vm)s AND v.regelsatz = %(rs)s AND v.herkunft = 'geliefert'
              AND v.beginn <= %(st)s AND (v.ende IS NULL OR v.ende >= %(st)s)
              AND {auswahl}
              AND NOT EXISTS (SELECT 1 FROM bereinigt.abschnitt a
                              WHERE a.lieferung = %(l)s AND a.regelsatz = %(rs)s AND a.vvh_id = v.vvh_id)
            """
        ).format(auswahl=auswahl),
        {**p, "lauf": lauf_id, "name": regel.name, "werte": ausgefallen},
        prepare=False,
    ).rowcount
    return eingefuegt, {
        "ausloeser": "teil_lieferung" if teil else "auspraegung_ausgefallen",
        "vormonat": vormonat,
        "basis_vormonat": basis,
        "fehlend": fehlend,
        "ausgefallen": ausgefallen,
        "fortgeschrieben": eingefuegt,
    }


def bereinigen(
    conn: Verbindung, *, lauf_id: int, lieferung: str, regelsatz: str, regeln: list[Regel]
) -> Bereinigung:
    """Baut bereinigt.abschnitt für (lieferung, regelsatz) neu auf. Läuft in der Transaktion des Aufrufers."""
    r_tausch = hoechstens_eine(regeln, "einlese", "spaltentausch")
    r_dublette = hoechstens_eine(regeln, "einlese", "dublette")
    r_datum = eine(regeln, "einlese", "datum")
    r_beginn = hoechstens_eine(regeln, "einlese", "ersatz_beginn")
    r_ende = hoechstens_eine(regeln, "einlese", "ersatz_ende")
    r_qz = eine(regeln, "einlese", "quellzuordnung")
    muster = str(wert(r_datum, "muster"))
    stichtag = monatsletzter(lieferung)
    version = oenace_version(conn, regeln, stichtag)
    tausch = _spaltentausch_noetig(conn, lieferung, r_tausch, muster)
    qz_ids = _zuordnungen_pruefen(conn, regeln)

    gelesen_z = conn.execute(
        "SELECT count(*) AS n FROM roh.lieferung WHERE lieferung = %s", (lieferung,)
    ).fetchone()
    gelesen = int(str(gelesen_z["n"])) if gelesen_z else 0
    if gelesen == 0:
        raise RegelFehler(f"Lieferung {lieferung} enthält keine Sätze")

    beginn_spalte, ende_spalte = ("ende", "beginn") if tausch else ("beginn", "ende")
    if r_dublette is not None:
        if wert(r_dublette, "vergleich") != "alle_felder":
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

    monat13 = wert(r_datum, "geburtsmonat_13") == "geburtsjahr_behalten"
    muster13 = str(wert(r_datum, "muster_monat_13")) if monat13 else "^$"
    fensterbeginn = (
        monatserster(monat_verschieben(lieferung, -(int(wert(r_beginn, "fenster_monate")) - 1)))
        if r_beginn
        else None
    )
    ende_modus = str(wert(r_ende, "ersatz")) if r_ende is not None else "laeuft"
    if ende_modus not in ("laeuft", "monatsletzter_sonst_laeuft"):
        raise RegelFehler(f"{r_ende.name if r_ende else 'E06'}: nicht unterstützter Ersatz {ende_modus!r}")
    qz_quelle = str(wert(r_qz, "quelle"))

    # Fehlt eine Einleseregel, die ein vorhandener Fehler bräuchte, bricht der Lauf ab statt still zu raten.
    luecken = conn.execute(
        f"""SELECT count(*) FILTER (WHERE NOT coalesce({_gueltig(beginn_spalte)}, false)) AS beginn,
                   count(*) FILTER (WHERE {ende_spalte} IS NOT NULL AND NOT {_gueltig(ende_spalte)}) AS ende
            FROM roh.lieferung WHERE lieferung = %(l)s""".encode(),
        {"l": lieferung, "muster": muster},
    ).fetchone()
    assert luecken is not None
    if int(str(luecken["beginn"])) and r_beginn is None:
        raise RegelFehler(
            f"{luecken['beginn']} Sätze ohne gültigen BEGINN, aber keine Regel der Art ersatz_beginn"
        )
    if int(str(luecken["ende"])) and r_ende is None:
        raise RegelFehler(
            f"{luecken['ende']} Sätze mit ungültigem ENDE, aber keine Regel der Art ersatz_ende"
        )

    joins = []
    codes = {}
    regel_ids = {}
    for m in MERKMALE:
        v = version if m == "oenace" else "-"
        roh_feld = "qual" if m == "qualifikation" else m
        joins.append(
            sql.SQL(
                """LEFT JOIN stat.quellzuordnung {q} ON {q}.regelsatz = %(rs)s AND {q}.quelle = %(qz)s AND {q}.merkmal = {m}
                     AND {q}.version = {v} AND {q}.geliefert = coalesce(t.{f}, '<leer>')
                     AND ({q}.regel_id IS NULL OR {q}.regel_id = ANY(%(qz_ids)s::int[]))
                   LEFT JOIN stat.quellzuordnung {s} ON {s}.regelsatz = %(rs)s AND {s}.quelle = %(qz)s AND {s}.merkmal = {m}
                     AND {s}.version = {v} AND {s}.geliefert = '<sonst>'
                     AND ({s}.regel_id IS NULL OR {s}.regel_id = ANY(%(qz_ids)s::int[]))"""
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
    ende_name = sql.Literal(r_ende.name if r_ende else None)
    abfrage = sql.SQL(
        """
        WITH r AS ({quelle}),
        t AS (
          SELECT r.*,
            {beginn_t} AS beginn_t, {ende_t} AS ende_t,
            CASE WHEN r.geburtsdatum ~ %(muster)s AND pg_input_is_valid(r.geburtsdatum, 'date')
                 THEN r.geburtsdatum::date END AS geb,
            CASE WHEN r.geburtsdatum ~ %(muster)s AND pg_input_is_valid(r.geburtsdatum, 'date') THEN 'gueltig'
                 WHEN %(m13)s AND r.geburtsdatum ~ %(muster13)s THEN 'monat_13'
                 ELSE 'ungueltig' END AS geb_status
          FROM r
        ),
        u AS (
          SELECT t.*,
            CASE WHEN t.beginn_t ~ %(muster)s AND pg_input_is_valid(t.beginn_t, 'date') THEN t.beginn_t::date END
              AS beg,
            CASE WHEN t.ende_t ~ %(muster)s AND pg_input_is_valid(t.ende_t, 'date') THEN t.ende_t::date
                 WHEN %(ende_modus)s = 'monatsletzter_sonst_laeuft' AND t.ende_t ~ '^[0-9]{{4}}-(0[1-9]|1[0-2])-[0-9]{{2}}$'
                   THEN (make_date(substr(t.ende_t, 1, 4)::int, substr(t.ende_t, 6, 2)::int, 1)
                         + interval '1 month - 1 day')::date
            END AS end_d,
            (t.ende_t IS NOT NULL AND NOT (t.ende_t ~ %(muster)s AND pg_input_is_valid(t.ende_t, 'date'))) AS ende_korr
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
                                  CASE WHEN z.beg IS NULL THEN {beginn_name}::text END,
                                  CASE WHEN z.ende_korr THEN {ende_name}::text END]
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
        ende_name=ende_name,
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
            "qz_ids": qz_ids,
            "muster": muster,
            "muster13": muster13,
            "ende_modus": ende_modus,
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

    r_fort = hoechstens_eine(regeln, "einlese", "fortschreibung")
    fortgeschrieben: int = 0
    fortschreibung: dict[str, object] = {}
    if r_fort is not None and monat_verschieben(lieferung, -1) in [
        str(z["lieferung"])
        for z in conn.execute(
            "SELECT DISTINCT lieferung FROM bereinigt.abschnitt WHERE regelsatz = %s", (regelsatz,)
        ).fetchall()
    ]:
        fortgeschrieben, fortschreibung = _fortschreiben(
            conn, regel=r_fort, lauf_id=lauf_id, lieferung=lieferung, regelsatz=regelsatz, version=version
        )

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
    if abschnitte + ausgeschlossen != gelesen + fortgeschrieben:
        raise RegelFehler(
            f"Bereinigung verliert Sätze: {gelesen} gelesen + {fortgeschrieben} fortgeschrieben ≠ "
            f"{abschnitte} Abschnitte + {ausgeschlossen} verdichtet"
        )

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
        fortgeschrieben=fortgeschrieben,
        fortschreibung=fortschreibung,
        spaltentausch=tausch,
        oenace_version=version,
        wirkung=wirkung,
    )
