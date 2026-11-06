"""Schritt 4: Prüfregeln eines Laufs ausführen (Regeln aus meta.regel, Typ ``pruefung``).

Läuft in der Lauf-Transaktion nach Bereinigung, Zählung (Temp-Tabellen ``_bestand`` und ``_zellen``) und
Revisionsrechnung. Je Regel entsteht genau eine Zeile in ``meta.pruefung_treffer`` (auch mit anzahl 0).
Der Code kennt nur die Arten; Schwellen, Codes, Einstufung, Maßnahme und Anhalten stehen in
``regel.parameter``. Gelesen werden nur die eigene Lieferung und der Vormonat, nie spätere Lieferungen.

Einstufung, Maßnahme und Anhalten hängen vom Ergebnisfall ab: ``treffer`` nimmt ``einstufung``,
``massnahme`` und ``anhalten``; jeder andere Fall (``ohne``, ``nicht_anwendbar``, ``saison`` …) nimmt
``einstufung_<fall>``, ``massnahme_<fall>`` und ``anhalten_<fall>``, sonst leer bzw. nicht anhalten.
"""

from __future__ import annotations

import textwrap
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Any

from psycopg import ClientCursor, sql
from psycopg.types.json import Jsonb

from statagent import ergebnis
from statagent.db import Verbindung
from statagent.ergebnis import monat_verschieben, monatserster
from statagent.regeln import Regel, RegelFehler
from statagent.zaehlung import gruppierung_zuordnung, zeitraum

#: Spalte ``meta.pruefung_treffer.beispiele`` hält höchstens fünf VVH_IDs (nie PERSON_ID).
BEISPIELE_MAX = 5
EBENEN = ("satz", "aggregat", "lieferung")
#: Gliederungen von ``_zellen`` bzw. stat.stat_beschaeftigte und ihre Spalte in bereinigt.abschnitt.
ZELLEN_SPALTEN = {
    "region": "bundesland",
    "oenace": "oenace",
    "geschlecht": "geschlecht",
    "qualifikation": "qualifikation",
    "alter": None,
}
ABSCHNITT_MERKMALE = ("oenace", "bundesland", "qualifikation", "geschlecht")

Abfrage = str | sql.SQL | sql.Composed

FALL_TREFFER = "treffer"
FALL_OHNE = "ohne"
FALL_NICHT_ANWENDBAR = "nicht_anwendbar"


@dataclass(frozen=True)
class Kontext:
    conn: Verbindung
    lauf_id: int
    lieferung: str
    regelsatz: str
    regeln: list[Regel]
    zeitraum_art: str
    von: date
    bis: date
    monatsbeginn: date
    regelstand: str
    variable: str
    oenace_version: str | None
    vormonat: str | None  # None: kein gerechneter Vormonat (erste Lieferung)
    vm_lauf_id: int | None
    vm_regelstand: str | None
    vm_von: date | None
    vm_bis: date | None
    vm_oenace_version: str | None

    @property
    def params(self) -> dict[str, Any]:
        return {
            "l": self.lieferung,
            "rs": self.regelsatz,
            "lauf": self.lauf_id,
            "art": self.zeitraum_art,
            "von": self.von,
            "bis": self.bis,
            "mb": self.monatsbeginn,
            "rst": self.regelstand,
            "var": self.variable,
            "vm": self.vormonat,
            "vm_lauf": self.vm_lauf_id,
            "rst_vm": self.vm_regelstand,
            "vm_von": self.vm_von,
            "vm_bis": self.vm_bis,
        }


@dataclass
class Befund:
    anzahl: int
    umfang: str
    fall: str
    beispiele: list[int] = field(default_factory=list)
    beleg_sql: str | None = None
    details: dict[str, Any] = field(default_factory=dict)


# --- Hilfen -----------------------------------------------------------------------------------------


def _int(wert: object) -> int:
    return int(str(wert)) if wert is not None else 0


def _n(zahl: int) -> str:
    return f"{zahl:,}".replace(",", ".")


def _prozent(anteil: float) -> str:
    return f"{anteil * 100:.1f} %".replace(".", ",")


def _param(regel: Regel, schluessel: str) -> Any:
    if schluessel not in regel.parameter:
        raise RegelFehler(f"{regel.name}: Parameter '{schluessel}' fehlt")
    return regel.parameter[schluessel]


def _regel_namentlich(k: Kontext, regel: Regel) -> Regel:
    """Die in ``parameter.regel`` namentlich referenzierte Regel des Laufs."""
    name = str(_param(regel, "regel"))
    for r in k.regeln:
        if r.name == name:
            return r
    raise RegelFehler(f"{regel.name}: referenzierte Regel '{name}' ist im Regelsatz nicht aktiv")


def _regeln_namentlich(k: Kontext, regel: Regel) -> list[Regel]:
    """Die in ``parameter.regel`` referenzierten Regeln des Laufs (ein Name oder eine Liste von Namen)."""
    angabe = _param(regel, "regel")
    namen = [str(n) for n in angabe] if isinstance(angabe, list) else [str(angabe)]
    aktiv = {r.name: r for r in k.regeln}
    fehlt = [n for n in namen if n not in aktiv]
    if fehlt or not namen:
        raise RegelFehler(
            f"{regel.name}: referenzierte Regel '{', '.join(fehlt)}' ist im Regelsatz nicht aktiv"
        )
    return [aktiv[n] for n in namen]


def _beleg(k: Kontext, abfrage: Abfrage | str, params: Mapping[str, Any], kopf: str | None = None) -> str:
    with ClientCursor(k.conn) as cur:
        text = cur.mogrify(abfrage, dict(params))
    text = textwrap.dedent(text).strip()
    return f"-- {kopf}\n{text}" if kopf else text


def _eine_zeile(k: Kontext, abfrage: Abfrage | str, params: Mapping[str, Any]) -> dict[str, object]:
    zeile = k.conn.execute(abfrage, dict(params), prepare=False).fetchone()
    assert zeile is not None
    return zeile


_BESTAND_KOPF = "_bestand: Verhältnisse {zeitraum} nach Abschnittswahl (statagent.zaehlung) im Lauf {lauf}"


def _saetze(
    k: Kontext,
    t: str | Abfrage,
    einheit: str,
    extra: Mapping[str, Any] | None = None,
    *,
    bestand: bool = False,
) -> Befund:
    """Zählt die Zeilen von ``t`` (Spalten vvh_id, gewicht) und nimmt die kleinsten VVH_IDs als Beispiele."""
    abfrage = sql.SQL(
        """
        WITH t AS ({t})
        SELECT coalesce(sum(gewicht), 0)::bigint AS n,
               coalesce((SELECT jsonb_agg(v ORDER BY v)
                         FROM (SELECT DISTINCT vvh_id AS v FROM t ORDER BY 1 LIMIT {bsp}) b), '[]'::jsonb) AS beispiele
        FROM t
        """
    ).format(t=sql.SQL(t) if isinstance(t, str) else t, bsp=sql.Literal(BEISPIELE_MAX))
    params = {**k.params, **(extra or {})}
    z = _eine_zeile(k, abfrage, params)
    n = _int(z["n"])
    beispiele = [int(v) for v in z["beispiele"]] if isinstance(z["beispiele"], list) else []
    zeitraum = "im Berichtsmonat" if k.zeitraum_art == "Monat" else "am Stichtag"
    kopf = _BESTAND_KOPF.format(zeitraum=zeitraum, lauf=k.lauf_id) if bestand else None
    return Befund(
        anzahl=n,
        umfang=f"{_n(n)} {einheit}",
        fall=FALL_TREFFER if n > 0 else FALL_OHNE,
        beispiele=beispiele,
        beleg_sql=_beleg(k, abfrage, params, kopf),
    )


def _nicht_anwendbar(grund: str) -> Befund:
    return Befund(anzahl=0, umfang="nicht anwendbar", fall=FALL_NICHT_ANWENDBAR, details={"grund": grund})


def _ohne_vormonat(k: Kontext) -> Befund | None:
    if k.vormonat is None:
        return _nicht_anwendbar(f"kein gerechneter Vormonat zu {k.lieferung} (erste Lieferung)")
    return None


_ABSCHNITTE = "bereinigt.abschnitt WHERE lieferung = %(l)s AND regelsatz = %(rs)s"
_AM_STICHTAG = "beginn <= %(bis)s AND (ende IS NULL OR ende >= %(von)s)"


# --- Satzprüfungen ----------------------------------------------------------------------------------


def _volldubletten(k: Kontext, regel: Regel) -> Befund:
    _regel_namentlich(k, regel)
    return _saetze(
        k,
        f"SELECT vvh_id, roh_zeilen - 1 AS gewicht FROM {_ABSCHNITTE} AND roh_zeilen > 1",
        "Zeilen verdichtet",
    )


def _mehrere_abschnitte(k: Kontext, regel: Regel) -> Befund:
    return _saetze(
        k,
        f"""SELECT vvh_id, 1 AS gewicht FROM {_ABSCHNITTE} AND {_AM_STICHTAG}
            GROUP BY vvh_id HAVING count(*) > 1""",
        "Verhältnisse mit mehreren Abschnitten am Stichtag",
    )


def _korrektur(k: Kontext, regel: Regel) -> Befund:
    namen = [r.name for r in _regeln_namentlich(k, regel)]
    bezug = str(_param(regel, "bezug"))
    if bezug == "lieferung":
        return _saetze(
            k,
            f"SELECT vvh_id, 1 AS gewicht FROM {_ABSCHNITTE} AND korrekturen && %(namen)s::text[]",
            "Sätze",
            {"namen": namen},
        )
    if bezug == "stichtag":
        return _saetze(
            k,
            "SELECT vvh_id, 1 AS gewicht FROM _bestand WHERE korrekturen && %(namen)s::text[]",
            "Verhältnisse am Stichtag",
            {"namen": namen},
            bestand=True,
        )
    raise RegelFehler(f"{regel.name}: bezug muss 'lieferung' oder 'stichtag' sein")


def _geburtsdatum_status(k: Kontext, regel: Regel) -> Befund:
    return _saetze(
        k,
        "SELECT vvh_id, 1 AS gewicht FROM _bestand WHERE geburtsdatum_status = %(status)s",
        "Verhältnisse am Stichtag",
        {"status": str(_param(regel, "status"))},
        bestand=True,
    )


def _alter_bereich(k: Kontext, regel: Regel) -> Befund:
    p_alter = _regel_namentlich(k, regel).parameter
    grenzen = {"amax": int(p_alter["max_plausibel"]), "amin": int(p_alter["min_plausibel"])}
    bereich = str(_param(regel, "bereich"))
    if bereich == "unplausibel":
        bedingung = "alter_roh > %(amax)s OR alter_roh < %(amin)s"
    elif bereich == "hoch":
        bedingung = "alter_roh BETWEEN %(ab)s AND %(amax)s"
        grenzen["ab"] = int(_param(regel, "ab"))
    else:
        raise RegelFehler(f"{regel.name}: bereich muss 'unplausibel' oder 'hoch' sein")
    b = _saetze(
        k,
        f"SELECT vvh_id, 1 AS gewicht FROM _bestand WHERE {bedingung}",
        "Verhältnisse am Stichtag",
        grenzen,
        bestand=True,
    )
    b.details["grenzen"] = grenzen
    return b


def _beginn_nach_ende(k: Kontext, regel: Regel) -> Befund:
    return _saetze(
        k,
        f"SELECT vvh_id, 1 AS gewicht FROM {_ABSCHNITTE} AND ende IS NOT NULL AND beginn > ende",
        "Abschnitte",
    )


def _phantom_doppelmeldung(k: Kontext, regel: Regel) -> Befund:
    return _saetze(
        k,
        """SELECT b.vvh_id, 1 AS gewicht FROM _bestand b
           WHERE b.beginn BETWEEN %(mb)s AND %(bis)s AND b.person_id IS NOT NULL
             AND EXISTS (SELECT 1 FROM _bestand z
                         WHERE z.person_id = b.person_id AND z.vvh_id <> b.vvh_id
                           AND z.qualifikation = b.qualifikation AND z.oenace = b.oenace
                           AND z.bundesland = b.bundesland)""",
        "Verhältnisse mit Beginn im Berichtsmonat",
        bestand=True,
    )


def _person_inkonsistent(k: Kontext, regel: Regel) -> Befund:
    return _saetze(
        k,
        f"""SELECT min(vvh_id) AS vvh_id, 1 AS gewicht FROM {_ABSCHNITTE} AND person_id IS NOT NULL
            GROUP BY person_id
            HAVING count(DISTINCT concat_ws('|', geburtsdatum_status, geburtsdatum, geburtsjahr)) > 1
                OR count(DISTINCT geschlecht) > 1""",
        "Personen",
    )


def _merkmalswelle(k: Kontext, regel: Regel) -> Befund:
    merkmale = [str(m) for m in _param(regel, "merkmale")]
    for m in merkmale:
        if m not in ABSCHNITT_MERKMALE:
            raise RegelFehler(f"{regel.name}: unbekanntes Merkmal '{m}'")
    schwelle = int(_param(regel, "schwelle"))
    nur_monat = bool(regel.parameter.get("beginn_im_berichtsmonat", True))
    lags = sql.SQL(", ").join(
        sql.SQL("lag({m}) OVER w AS {v}").format(m=sql.Identifier(m), v=sql.Identifier(f"{m}_vor"))
        for m in merkmale
    )
    zeitfilter = sql.SQL("beginn BETWEEN %(mb)s AND %(bis)s" if nur_monat else "beginn <= %(bis)s")
    wechsel = sql.SQL("\n          UNION ALL\n          ").join(
        sql.SQL(
            "SELECT {lit} AS merkmal, {v} AS von, {m} AS nach, beginn AS tag, vvh_id, bundesland, oenace "
            "FROM s WHERE {v} <> {m} AND {zf}"
        ).format(lit=sql.Literal(m), m=sql.Identifier(m), v=sql.Identifier(f"{m}_vor"), zf=zeitfilter)
        for m in merkmale
    )
    abfrage = sql.SQL(
        """
        WITH s AS (
          SELECT vvh_id, beginn, bundesland, oenace, {lags}
          FROM bereinigt.abschnitt WHERE lieferung = %(l)s AND regelsatz = %(rs)s
          WINDOW w AS (PARTITION BY vvh_id ORDER BY beginn, ende NULLS LAST)
        ),
        w AS (
          {wechsel}
        ),
        g AS (
          SELECT merkmal, von, nach, tag, count(*)::bigint AS n,
                 mode() WITHIN GROUP (ORDER BY bundesland) AS bundesland,
                 mode() WITHIN GROUP (ORDER BY oenace) AS oenace
          FROM w GROUP BY merkmal, von, nach, tag HAVING count(*) > %(schwelle)s
        )
        SELECT g.merkmal, g.von, g.nach, g.tag::text AS tag, g.n, g.bundesland, g.oenace,
               (SELECT jsonb_agg(v ORDER BY v) FROM (
                  SELECT w.vvh_id AS v FROM w
                  WHERE w.merkmal = g.merkmal AND w.von = g.von AND w.nach = g.nach AND w.tag = g.tag
                  ORDER BY 1 LIMIT {bsp}) b) AS beispiele
        FROM g ORDER BY g.n DESC, g.merkmal, g.von, g.nach, g.tag
        """
    ).format(
        lags=lags,
        wechsel=wechsel,
        bsp=sql.Literal(BEISPIELE_MAX),
    )
    params = {**k.params, "schwelle": schwelle}
    wellen = k.conn.execute(abfrage, params, prepare=False).fetchall()
    anzahl = sum(_int(w["n"]) for w in wellen)
    beispiele: list[int] = sorted(
        {int(v) for w in wellen if isinstance(w["beispiele"], list) for v in w["beispiele"]}
    )[:BEISPIELE_MAX]
    details: list[dict[str, Any]] = [
        {
            "merkmal": str(w["merkmal"]),
            "von": str(w["von"]),
            "nach": str(w["nach"]),
            "tag": str(w["tag"]),
            "anzahl": _int(w["n"]),
            "bundesland": str(w["bundesland"]),
            "oenace": str(w["oenace"]),
        }
        for w in wellen
    ]
    umfang = (
        "; ".join(
            f"{d['merkmal']} {d['von']} → {d['nach']} am {d['tag']}: {_n(int(d['anzahl']))} "
            f"(Bundesland {d['bundesland']}, ÖNACE {d['oenace']})"
            for d in details
        )
        if details
        else f"keine Welle über {_n(schwelle)} Verhältnisse"
    )
    return Befund(
        anzahl=anzahl,
        umfang=umfang,
        fall=FALL_TREFFER if wellen else FALL_OHNE,
        beispiele=beispiele,
        beleg_sql=_beleg(k, abfrage, params),
        details={"wellen": details, "schwelle": schwelle},
    )


# --- Aggregatprüfungen ------------------------------------------------------------------------------


def _zellen_quelle(beleg: bool, geliefert: bool = False) -> sql.SQL:
    """Zellen des Laufs: im Lauf ``_zellen`` (bzw. ``_zellen_geliefert`` ohne Fortschreibung E07), im Beleg
    dieselben Zellen aus stat.stat_beschaeftigte."""
    if not beleg:
        return sql.SQL("_zellen_geliefert" if geliefert else "_zellen")
    return sql.SQL(
        """(SELECT * FROM stat.stat_beschaeftigte
            WHERE regelsatz = %(rs)s AND regelstand = %(rst)s AND zeitraum_art = %(art)s
              AND zeitraum_bis = %(bis)s AND variable = %(var)s) AS z"""
    )


def _gliederung(regel: Regel, name: str) -> sql.Identifier:
    if name not in ZELLEN_SPALTEN:
        raise RegelFehler(f"{regel.name}: unbekannte Gliederung '{name}'")
    return sql.Identifier(name)


def _vergleich(k: Kontext, regel: Regel, gliederung: str) -> tuple[list[dict[str, object]], str]:
    """Bestand je Ausprägung: Vormonat (stat.stat_beschaeftigte) gegen aktuellen Lauf."""

    def abfrage(beleg: bool) -> Abfrage:
        return sql.SQL(
            """
            WITH vm AS (
              SELECT {g}::text AS code, sum(wert)::bigint AS n FROM stat.stat_beschaeftigte
              WHERE regelsatz = %(rs)s AND regelstand = %(rst_vm)s AND zeitraum_art = %(art)s
                AND zeitraum_bis = %(vm_bis)s AND variable = %(var)s
              GROUP BY 1
            ),
            akt AS (SELECT {g}::text AS code, sum(wert)::bigint AS n FROM {quelle} GROUP BY 1)
            SELECT coalesce(vm.code, akt.code) AS code, coalesce(vm.n, 0) AS vormonat, coalesce(akt.n, 0) AS aktuell
            FROM vm FULL JOIN akt ON akt.code = vm.code
            ORDER BY coalesce(vm.code, akt.code) COLLATE "C"
            """
        ).format(
            g=_gliederung(regel, gliederung),
            quelle=_zellen_quelle(beleg, bool(regel.parameter.get("nur_geliefert", False))),
        )

    zeilen = k.conn.execute(abfrage(False), k.params, prepare=False).fetchall()
    return zeilen, _beleg(k, abfrage(True), k.params)


def _oenace_vergleichbar(k: Kontext) -> bool:
    return k.oenace_version is not None and k.oenace_version == k.vm_oenace_version


def _auspraegung_verschwunden(k: Kontext, regel: Regel) -> Befund:
    if (leer := _ohne_vormonat(k)) is not None:
        return leer
    schwelle = int(_param(regel, "schwelle"))
    treffer: list[dict[str, Any]] = []
    belege: list[str] = []
    uebersprungen: list[str] = []
    for g in [str(x) for x in _param(regel, "gliederungen")]:
        if g == "oenace" and not _oenace_vergleichbar(k):
            uebersprungen.append(f"oenace ({k.vm_oenace_version} → {k.oenace_version})")
            continue
        zeilen, beleg = _vergleich(k, regel, g)
        belege.append(f"-- Gliederung {g}\n{beleg}")
        for z in zeilen:
            if _int(z["vormonat"]) > schwelle and _int(z["aktuell"]) == 0:
                treffer.append(
                    {"gliederung": g, "code": str(z["code"]), "vormonat": _int(z["vormonat"]), "aktuell": 0}
                )

    beispiele: list[int] = []
    if treffer:
        bedingungen = []
        params: dict[str, Any] = dict(k.params)
        for i, t in enumerate(treffer):
            spalte = ZELLEN_SPALTEN[str(t["gliederung"])]
            if spalte is None:
                continue
            params[f"c{i}"] = t["code"]
            bedingungen.append(
                sql.SQL("{s} = {p}").format(s=sql.Identifier(spalte), p=sql.Placeholder(f"c{i}"))
            )
        if bedingungen:
            bsp = k.conn.execute(
                sql.SQL(
                    """SELECT DISTINCT vvh_id FROM bereinigt.abschnitt
                       WHERE lieferung = %(vm)s AND regelsatz = %(rs)s
                         AND beginn <= %(vm_bis)s AND (ende IS NULL OR ende >= %(vm_von)s) AND ({b})
                       ORDER BY vvh_id LIMIT {n}"""
                ).format(b=sql.SQL(" OR ").join(bedingungen), n=sql.Literal(BEISPIELE_MAX)),
                params,
                prepare=False,
            ).fetchall()
            beispiele = [_int(z["vvh_id"]) for z in bsp]
    umfang = (
        f"{len(treffer)} Ausprägungen: "
        + ", ".join(f"{t['gliederung']} {t['code']} ({_n(int(t['vormonat']))} → 0)" for t in treffer)
        if treffer
        else f"keine Ausprägung über {_n(schwelle)} fällt auf 0"
    )
    return Befund(
        anzahl=len(treffer),
        umfang=umfang,
        fall=FALL_TREFFER if treffer else FALL_OHNE,
        beispiele=beispiele,
        beleg_sql=";\n\n".join(belege),
        details={"auspraegungen": treffer, "vormonat": k.vormonat, "nicht_verglichen": uebersprungen},
    )


def _sprung_aggregat(k: Kontext, regel: Regel) -> Befund:
    if (leer := _ohne_vormonat(k)) is not None:
        return leer
    schwelle = float(_param(regel, "schwelle_prozent")) / 100
    n_min = int(_param(regel, "n_min"))
    saison_param = regel.parameter.get("saison", {})
    saison = {str(g): {str(c) for c in codes} for g, codes in dict(saison_param).items()}
    zellen: list[dict[str, Any]] = []
    belege: list[str] = []
    wechsel = False
    for g in [str(x) for x in _param(regel, "gliederungen")]:
        if g == "oenace" and not _oenace_vergleichbar(k):
            wechsel = True
            continue
        zeilen, beleg = _vergleich(k, regel, g)
        belege.append(f"-- Gliederung {g}\n{beleg}")
        for z in zeilen:
            vm, akt = _int(z["vormonat"]), _int(z["aktuell"])
            if vm >= n_min and abs(akt - vm) / vm > schwelle:
                code = str(z["code"])
                zellen.append(
                    {
                        "gliederung": g,
                        "code": code,
                        "vormonat": vm,
                        "aktuell": akt,
                        "prozent": round((akt - vm) / vm * 100, 2),
                        "saison": code in saison.get(g, set()),
                    }
                )
    nicht_saison = [z for z in zellen if not z["saison"]]
    if nicht_saison:
        fall = FALL_TREFFER
    elif zellen:
        fall = "saison"
    elif wechsel:
        fall = "klassifikationswechsel"
    else:
        fall = FALL_OHNE
    teile = [f"{z['gliederung']} {z['code']} {str(z['prozent']).replace('.', ',')} %" for z in zellen]
    umfang = f"{len(zellen)} Zellen ({len(nicht_saison)} ohne Saisonerklärung)"
    if teile:
        umfang += ": " + ", ".join(teile)
    if wechsel:
        umfang += f"; ÖNACE nicht verglichen ({k.vm_oenace_version} → {k.oenace_version})"
    return Befund(
        anzahl=len(zellen),
        umfang=umfang,
        fall=fall,
        beleg_sql=";\n\n".join(belege),
        details={"zellen": zellen, "vormonat": k.vormonat, "klassifikationswechsel": wechsel},
    )


def _ausgeschlossen(k: Kontext, nur_geliefert: bool = False) -> int:
    """Verhältnisse, die eine Ausschlussregel des Laufs nicht zählt (0 ohne solche Regel). Sie stehen im Bestand
    aus bereinigt.abschnitt, aber in keiner Zelle (Live-Änderung #80, z. B. „ohne Beamte“)."""
    if not any(r.typ == "zaehl" and r.art == "ausschluss" for r in k.regeln):
        return 0
    filter_ = " AND herkunft = 'geliefert'" if nur_geliefert else ""
    z = _eine_zeile(k, f"SELECT count(*) AS n FROM _bestand WHERE ausgeschlossen{filter_}", {})
    return _int(z["n"])


def _gruppen(k: Kontext) -> dict[str, list[str]]:
    """Gruppennamen je Merkmal aus den Gruppierungsregeln des Laufs (z. B. {'region': ['Ost']})."""
    ergebnis: dict[str, list[str]] = {}
    for r in k.regeln:
        if r.typ == "zaehl" and r.art == "gruppierung":
            merkmal, zuordnung = gruppierung_zuordnung(r)
            ergebnis[merkmal] = sorted(set(zuordnung.values()))
    return ergebnis


def _blattsummen(k: Kontext, regel: Regel) -> Befund:
    gliederungen = _param(regel, "gliederungen")
    if not isinstance(gliederungen, dict):
        raise RegelFehler(f"{regel.name}: gliederungen muss ein Objekt sein")

    # Zählt die Dimensionsregel nach Beschäftigungskategorie (Auftrag 1, Regelsatz v2), stehen in den Zellen
    # Arbeiter/Angestellte/Beamte statt der fünf Qualifikationscodes; dann gilt deren Klassifikation.
    r_dim = next((r for r in k.regeln if r.typ == "zaehl" and r.art == "dimension"), None)
    kategorie = r_dim is not None and r_dim.parameter.get("qualifikation") == "beschaeftigungskategorie"
    # Eine Gruppierungsregel (z. B. Wien, NÖ, Burgenland = „Ost“) bringt Codes, die in keiner Klassifikation stehen;
    # für ihr Merkmal gelten die Gruppennamen als zulässig.
    gruppen = _gruppen(k)

    def abfrage(beleg: bool) -> Abfrage:
        summen = []
        for g, spez in gliederungen.items():
            tabelle = str(dict(spez)["tabelle"])
            if str(g) == "qualifikation" and kategorie:
                tabelle = "stat.klass_beschaeftigungskategorie"
            teile = tabelle.split(".")
            if len(teile) != 2:
                raise RegelFehler(f"{regel.name}: tabelle muss 'schema.tabelle' sein ({g})")
            version = (
                sql.SQL(" AND k.version = z.oenace_version") if dict(spez).get("version") else sql.SQL("")
            )
            zusatz = (
                sql.SQL(" OR z.{} = ANY({})").format(_gliederung(regel, str(g)), sql.Literal(gruppen[str(g)]))
                if str(g) in gruppen
                else sql.SQL("")
            )
            summen.append(
                sql.SQL(
                    "coalesce(sum(z.wert) FILTER (WHERE EXISTS (SELECT 1 FROM {t} k WHERE k.code = z.{g}{v}){z}), 0)"
                    "::bigint AS {a}"
                ).format(
                    t=sql.Identifier(*teile),
                    g=_gliederung(regel, str(g)),
                    v=version,
                    z=zusatz,
                    a=sql.Identifier(str(g)),
                )
            )
        quelle = _zellen_quelle(beleg)
        if not beleg:
            quelle = sql.SQL("_zellen z")
        return sql.SQL(
            """
            SELECT (SELECT count(DISTINCT vvh_id) FROM bereinigt.abschnitt
                    WHERE lieferung = %(l)s AND regelsatz = %(rs)s
                      AND beginn <= %(bis)s AND (ende IS NULL OR ende >= %(von)s))::bigint AS bestand,
                   coalesce(sum(z.wert), 0)::bigint AS gesamt, {summen}
            FROM {quelle}
            """
        ).format(summen=sql.SQL(", ").join(summen), quelle=quelle)

    z = _eine_zeile(k, abfrage(False), k.params)
    ausgeschlossen = _ausgeschlossen(k)
    bestand, gesamt = _int(z["bestand"]) - ausgeschlossen, _int(z["gesamt"])
    summen = {str(g): _int(z[str(g)]) for g in gliederungen}
    abweichend = {g: s for g, s in summen.items() if s != gesamt}
    if gesamt != bestand:
        abweichend["gesamt"] = gesamt
    umfang = (
        f"Summe je Gliederung = Gesamt {_n(gesamt)} (Bestand {_n(bestand)}"
        + (f", ohne {_n(ausgeschlossen)} nach Ausschlussregel)" if ausgeschlossen else ")")
        if not abweichend
        else "Abweichung: " + ", ".join(f"{g} {_n(s)}" for g, s in abweichend.items()) + f" ≠ {_n(bestand)}"
    )
    return Befund(
        anzahl=len(abweichend),
        umfang=umfang,
        fall=FALL_TREFFER if abweichend else FALL_OHNE,
        beleg_sql=_beleg(k, abfrage(True), k.params),
        details={"bestand": bestand, "gesamt": gesamt, "summen": summen, "ausgeschlossen": ausgeschlossen},
    )


# --- Lieferungsprüfungen ----------------------------------------------------------------------------

_BESTAND_ZAHL = """(SELECT count(DISTINCT vvh_id) FROM bereinigt.abschnitt
                    WHERE lieferung = %(l)s AND regelsatz = %(rs)s
                      AND beginn <= %(bis)s AND (ende IS NULL OR ende >= %(von)s))::bigint"""
#: Bestand nur aus gelieferten Abschnitten (ohne Fortschreibung E07): erkennt den Lieferausfall selbst.
_BESTAND_GELIEFERT = """(SELECT count(DISTINCT vvh_id) FROM bereinigt.abschnitt
                    WHERE lieferung = %(l)s AND regelsatz = %(rs)s AND herkunft = 'geliefert'
                      AND beginn <= %(bis)s AND (ende IS NULL OR ende >= %(von)s))::bigint"""


def _vergleichsmonat(k: Kontext, regel: Regel) -> tuple[str, int]:
    """Monat und Lauf, gegen den verglichen wird: der Vormonat, oder mit ``vergleich: letzter_nicht_angehaltener``
    der jüngste frühere Monat, dessen maßgeblicher Lauf nicht angehalten wurde (eine Teil-Lieferung soll den
    Folgemonat nicht ebenfalls anhalten). Nur eigene und frühere Lieferungen."""
    assert k.vormonat is not None and k.vm_lauf_id is not None
    modus = str(regel.parameter.get("vergleich", "vormonat"))
    if modus not in ("vormonat", "letzter_nicht_angehaltener"):
        raise RegelFehler(f"{regel.name}: unbekannter Vergleich {modus!r}")
    monat, lauf_id = k.vormonat, k.vm_lauf_id
    for _ in range(12):
        if modus == "vormonat":
            break
        angehalten = k.conn.execute(
            "SELECT EXISTS (SELECT 1 FROM meta.pruefung_treffer WHERE lauf_id = %s AND anhalten) AS a",
            (lauf_id,),
            prepare=False,
        ).fetchone()
        if angehalten is None or not angehalten["a"]:
            break
        frueher = ergebnis.monat_verschieben(monat, -1)
        stand = ergebnis.letzter_lauf(k.conn, frueher, k.regelsatz)
        if stand is None:
            break
        monat, lauf_id = frueher, stand.lauf_id
    return monat, lauf_id


def _bestand_vs_vormonat(k: Kontext, regel: Regel) -> Befund:
    if (leer := _ohne_vormonat(k)) is not None:
        return leer
    schwelle = float(_param(regel, "schwelle"))
    vergleich, vergleich_lauf = _vergleichsmonat(k, regel)
    abfrage = f"""SELECT {_BESTAND_GELIEFERT} AS aktuell,
                         (SELECT gezaehlt - fortgeschrieben FROM meta.lauf WHERE id = %(cmp_lauf)s) AS vormonat"""
    params = {**k.params, "cmp_lauf": vergleich_lauf}
    z = _eine_zeile(k, abfrage, params)
    # Der Vormonat (meta.lauf.gezaehlt) zählt ohne Ausgeschlossene; der aktuelle Bestand darum auch.
    akt, vm = _int(z["aktuell"]) - _ausgeschlossen(k, nur_geliefert=True), _int(z["vormonat"])
    verhaeltnis = akt / vm if vm else 0.0
    treffer = verhaeltnis < 1 - schwelle
    return Befund(
        anzahl=vm - akt if treffer else 0,
        umfang=f"{_n(akt)} gegen {_n(vm)} in {vergleich} ({_prozent(verhaeltnis - 1)})",
        fall=FALL_TREFFER if treffer else FALL_OHNE,
        beleg_sql=_beleg(k, abfrage, params),
        details={
            "aktuell": akt,
            "vormonat": vm,
            "verhaeltnis": round(verhaeltnis, 6),
            "vormonat_lieferung": k.vormonat,
            "vergleichsmonat": vergleich,
        },
    )


def _verhaeltnisse_verschwunden(k: Kontext, regel: Regel) -> Befund:
    if (leer := _ohne_vormonat(k)) is not None:
        return leer
    schwelle = float(_param(regel, "schwelle"))
    abfrage = sql.SQL(
        """
        WITH basis AS (
          SELECT DISTINCT v.vvh_id FROM bereinigt.abschnitt v
          WHERE v.lieferung = %(vm)s AND v.regelsatz = %(rs)s AND v.herkunft = 'geliefert'
            AND v.beginn <= %(vm_bis)s AND (v.ende IS NULL OR v.ende >= %(vm_bis)s)
        ),
        fehlt AS (
          SELECT b.vvh_id FROM basis b
          WHERE NOT EXISTS (SELECT 1 FROM bereinigt.abschnitt a
                            WHERE a.lieferung = %(l)s AND a.regelsatz = %(rs)s AND a.herkunft = 'geliefert'
                              AND a.vvh_id = b.vvh_id)
        )
        SELECT (SELECT count(*) FROM basis) AS basis, (SELECT count(*) FROM fehlt) AS n,
               coalesce((SELECT jsonb_agg(vvh_id ORDER BY vvh_id)
                         FROM (SELECT vvh_id FROM fehlt ORDER BY vvh_id LIMIT {bsp}) x), '[]'::jsonb) AS beispiele
        """
    ).format(bsp=sql.Literal(BEISPIELE_MAX))
    z = _eine_zeile(k, abfrage, k.params)
    basis, n = _int(z["basis"]), _int(z["n"])
    anteil = n / basis if basis else 0.0
    fall = FALL_TREFFER if anteil > schwelle else ("unter_schwelle" if n > 0 else FALL_OHNE)
    return Befund(
        anzahl=n,
        umfang=f"{_n(n)} von {_n(basis)} Verhältnissen des Vormonats fehlen ({_prozent(anteil)})",
        fall=fall,
        beispiele=[int(v) for v in z["beispiele"]] if isinstance(z["beispiele"], list) else [],
        beleg_sql=_beleg(k, abfrage, k.params),
        details={"basis": basis, "anteil": round(anteil, 6), "vormonat": k.vormonat},
    )


def _zeilenzahl_vs_vormonat(k: Kontext, regel: Regel) -> Befund:
    if (leer := _ohne_vormonat(k)) is not None:
        return leer
    unter, ober = float(_param(regel, "untergrenze")), float(_param(regel, "obergrenze"))
    vergleich, _ = _vergleichsmonat(k, regel)
    abfrage = """SELECT (SELECT count(*) FROM roh.lieferung WHERE lieferung = %(l)s) AS aktuell,
                        (SELECT count(*) FROM roh.lieferung WHERE lieferung = %(cmp)s) AS vormonat"""
    params = {**k.params, "cmp": vergleich}
    z = _eine_zeile(k, abfrage, params)
    akt, vm = _int(z["aktuell"]), _int(z["vormonat"])
    verhaeltnis = akt / vm if vm else 0.0
    treffer = not unter <= verhaeltnis <= ober
    return Befund(
        anzahl=abs(akt - vm) if treffer else 0,
        umfang=f"{_n(akt)} / {_n(vm)} Zeilen gegen {vergleich} ({_prozent(verhaeltnis - 1)})",
        fall=FALL_TREFFER if treffer else FALL_OHNE,
        beleg_sql=_beleg(k, abfrage, params),
        details={
            "aktuell": akt,
            "vormonat": vm,
            "verhaeltnis": round(verhaeltnis, 6),
            "vormonat_lieferung": k.vormonat,
            "vergleichsmonat": vergleich,
        },
    )


def _abrechnung(k: Kontext, regel: Regel) -> Befund:
    abfrage = f"""SELECT (SELECT count(*) FROM roh.lieferung WHERE lieferung = %(l)s) AS gelesen,
                         {_BESTAND_ZAHL} AS gezaehlt,
                         (SELECT count(*) FROM {_ABSCHNITTE}) AS abschnitte,
                         (SELECT coalesce(sum(roh_zeilen - 1), 0) FROM {_ABSCHNITTE}) AS ausgeschlossen,
                         (SELECT count(*) FROM {_ABSCHNITTE} AND herkunft = 'fortgeschrieben') AS fortgeschrieben"""
    z = _eine_zeile(k, abfrage, k.params)
    gelesen, gezaehlt, fort = _int(z["gelesen"]), _int(z["gezaehlt"]), _int(z["fortgeschrieben"])
    nicht, aus = _int(z["abschnitte"]) - gezaehlt, _int(z["ausgeschlossen"])
    bestand_temp = _int(_eine_zeile(k, "SELECT count(*) AS n FROM _bestand", {})["n"])
    differenz = gelesen + fort - (gezaehlt + nicht + aus)
    stimmt = differenz == 0 and bestand_temp == gezaehlt
    zeichen = "=" if differenz == 0 else "≠"
    return Befund(
        anzahl=0 if stimmt else max(abs(differenz), abs(bestand_temp - gezaehlt)),
        umfang=(f"{_n(gelesen)}" + (f" + {_n(fort)} fortgeschrieben" if fort else ""))
        + f" {zeichen} {_n(gezaehlt)} + {_n(nicht)} + {_n(aus)}",
        fall=FALL_OHNE if stimmt else FALL_TREFFER,
        beleg_sql=_beleg(k, abfrage, k.params),
        details={
            "gelesen": gelesen,
            "gezaehlt": gezaehlt,
            "nicht_gezaehlt": nicht,
            "ausgeschlossen": aus,
            "fortgeschrieben": fort,
            "gezaehlt_bestand": bestand_temp,
        },
    )


def _revision_vormonat(k: Kontext, regel: Regel) -> Befund:
    schwelle = float(_param(regel, "schwelle"))
    gliederung = str(_param(regel, "gliederung"))
    vorhanden = _eine_zeile(k, "SELECT to_regclass('meta.revision') IS NOT NULL AS da", {})
    if not vorhanden["da"]:
        return _nicht_anwendbar("meta.revision ist nicht eingerichtet")
    abfrage = """SELECT berichtsmonat, veroeffentlicht, aktuell, differenz FROM meta.revision
                 WHERE lauf_id = %(lauf)s AND gliederung = %(gl)s ORDER BY berichtsmonat"""
    params = {**k.params, "gl": gliederung}
    zeilen = k.conn.execute(abfrage, params, prepare=False).fetchall()
    if not zeilen:
        return _nicht_anwendbar("kein Revisionsbedarf berechnet (keine Vormonate in der Lieferung)")
    monate: list[dict[str, Any]] = [
        {
            "berichtsmonat": str(z["berichtsmonat"]),
            "veroeffentlicht": _int(z["veroeffentlicht"]),
            "differenz": _int(z["differenz"]),
            "anteil": round(abs(_int(z["differenz"])) / _int(z["veroeffentlicht"]), 6)
            if _int(z["veroeffentlicht"])
            else 0.0,
        }
        for z in zeilen
    ]
    ueber = [m for m in monate if float(m["anteil"]) > schwelle]
    summe = sum(abs(int(m["differenz"])) for m in monate)
    fall = FALL_TREFFER if ueber else ("unter_schwelle" if summe > 0 else FALL_OHNE)
    umfang = ", ".join(
        f"{m['berichtsmonat']}: {int(m['differenz']):+d} ({_prozent(float(m['anteil']))})" for m in monate
    )
    return Befund(
        anzahl=summe,
        umfang=umfang,
        fall=fall,
        beleg_sql=_beleg(k, abfrage, params),
        details={"monate": monate, "ueber_schwelle": [m["berichtsmonat"] for m in ueber]},
    )


def _lieferumfang_fenster(k: Kontext, regel: Regel) -> Befund:
    n_vm = int(_param(regel, "fenster_vormonate"))
    schwelle = float(_param(regel, "schwelle"))
    params = {
        **k.params,
        "f_von": monatserster(monat_verschieben(k.lieferung, -n_vm)),
        "f_bis": monatserster(k.lieferung) - timedelta(days=1),
    }
    abfrage = f"""SELECT count(*) AS abschnitte,
                         count(*) FILTER (WHERE ende BETWEEN %(f_von)s AND %(f_bis)s) AS im_fenster,
                         min(ende)::text AS erstes_ende
                  FROM {_ABSCHNITTE}"""
    z = _eine_zeile(k, abfrage, params)
    abschnitte, im_fenster = _int(z["abschnitte"]), _int(z["im_fenster"])
    anteil = im_fenster / abschnitte if abschnitte else 0.0
    treffer = anteil < schwelle
    umfang = (
        f"{_n(im_fenster)} von {_n(abschnitte)} Abschnitten enden {params['f_von']} bis {params['f_bis']} "
        f"({_prozent(anteil)})"
    )
    if treffer:
        umfang += f"; kein Vollabzug über {n_vm + 1} Monate (erstes Ende {z['erstes_ende']})"
    return Befund(
        anzahl=1 if treffer else 0,
        umfang=umfang,
        fall=FALL_TREFFER if treffer else FALL_OHNE,
        beleg_sql=_beleg(k, abfrage, params),
        details={"abschnitte": abschnitte, "im_fenster": im_fenster, "anteil": round(anteil, 6)},
    )


#: Kein serverseitiges Vorbereiten: ein generischer Plan macht den Anti-Join über 400.000 Verhältnisse
#: (P16) nach der 5. Ausführung minutenlang. Darum ``prepare=False`` bei allen Prüfabfragen.

#: Regel-Art → Implementierung. Neue Arten kommen nur hier hinzu; alles andere steht in meta.regel.
ARTEN: dict[str, Callable[[Kontext, Regel], Befund]] = {
    "volldubletten": _volldubletten,
    "mehrere_abschnitte": _mehrere_abschnitte,
    "korrektur": _korrektur,
    "geburtsdatum_status": _geburtsdatum_status,
    "alter_bereich": _alter_bereich,
    "beginn_nach_ende": _beginn_nach_ende,
    "auspraegung_verschwunden": _auspraegung_verschwunden,
    "sprung_aggregat": _sprung_aggregat,
    "bestand_vs_vormonat": _bestand_vs_vormonat,
    "verhaeltnisse_verschwunden": _verhaeltnisse_verschwunden,
    "zeilenzahl_vs_vormonat": _zeilenzahl_vs_vormonat,
    "merkmalswelle": _merkmalswelle,
    "phantom_doppelmeldung": _phantom_doppelmeldung,
    "person_inkonsistent": _person_inkonsistent,
    "blattsummen": _blattsummen,
    "abrechnung": _abrechnung,
    "revision_vormonat": _revision_vormonat,
    "lieferumfang_fenster": _lieferumfang_fenster,
}


# --- Ablauf -----------------------------------------------------------------------------------------


def _kontext(conn: Verbindung, lauf_id: int, lieferung: str, regelsatz: str, regeln: list[Regel]) -> Kontext:
    zr = zeitraum(regeln, lieferung)
    lauf = conn.execute("SELECT regelstand FROM meta.lauf WHERE id = %s", (lauf_id,)).fetchone()
    if lauf is None:
        raise RegelFehler(f"Lauf {lauf_id} fehlt in meta.lauf")
    z = conn.execute(
        "SELECT min(variable) AS variable, (SELECT min(oenace_version) FROM _bestand) AS version FROM _zellen"
    ).fetchone()
    assert z is not None
    vormonat = ergebnis.monat_verschieben(lieferung, -1)
    vm_stand = ergebnis.letzter_lauf(conn, vormonat, regelsatz)
    vm_version: str | None = None
    vm_zr = None
    if vm_stand is not None:
        vz = conn.execute(
            """SELECT min(oenace_version) AS version FROM bereinigt.abschnitt
               WHERE lieferung = %s AND regelsatz = %s""",
            (vormonat, regelsatz),
        ).fetchone()
        vm_version = None if vz is None or vz["version"] is None else str(vz["version"])
        if vm_version is None:
            vm_stand = None  # Vormonat gerechnet, aber bereinigt.abschnitt fehlt: wie kein Vormonat
        else:
            vm_zr = zeitraum(regeln, vormonat)
    return Kontext(
        conn=conn,
        lauf_id=lauf_id,
        lieferung=lieferung,
        regelsatz=regelsatz,
        regeln=regeln,
        zeitraum_art=zr.art,
        von=zr.von,
        bis=zr.bis,
        monatsbeginn=monatserster(lieferung),
        regelstand=str(lauf["regelstand"]),
        variable=str(z["variable"]),
        oenace_version=None if z["version"] is None else str(z["version"]),
        vormonat=vormonat if vm_stand is not None else None,
        vm_lauf_id=vm_stand.lauf_id if vm_stand is not None else None,
        vm_regelstand=vm_stand.regelstand if vm_stand is not None else None,
        vm_von=vm_zr.von if vm_zr is not None else None,
        vm_bis=vm_zr.bis if vm_zr is not None else None,
        vm_oenace_version=vm_version,
    )


def _aus_fall(regel: Regel, schluessel: str, fall: str) -> Any:
    if fall == FALL_TREFFER:
        return regel.parameter.get(schluessel)
    return regel.parameter.get(f"{schluessel}_{fall}")


def pruefungen_ausfuehren(
    conn: Verbindung, *, lauf_id: int, lieferung: str, regelsatz: str, regeln: list[Regel]
) -> list[str]:
    """Führt alle aktiven Regeln typ='pruefung' der Lieferung aus, schreibt je Treffer eine Zeile in
    meta.pruefung_treffer (auch anzahl=0 für Regeln, die geprüft und unauffällig sind) und liefert die Namen
    der Regeln, deren Treffer anhalten (Monat bleibt vorläufig)."""
    pruefregeln = sorted((r for r in regeln if r.typ == "pruefung"), key=lambda r: (r.reihenfolge, r.name))
    if not pruefregeln:
        return []
    for r in pruefregeln:
        if r.art not in ARTEN:
            raise RegelFehler(f"{r.name}: unbekannte Prüfart '{r.art}' (bekannt: {', '.join(sorted(ARTEN))})")
        if r.parameter.get("ebene") not in EBENEN:
            raise RegelFehler(f"{r.name}: ebene muss {', '.join(EBENEN)} sein")
    k = _kontext(conn, lauf_id, lieferung, regelsatz, regeln)
    anhalten: list[str] = []
    for r in pruefregeln:
        befund = ARTEN[r.art](k, r)
        halt = bool(_aus_fall(r, "anhalten", befund.fall))
        details: dict[str, Any] = {"regel": r.name, "fall": befund.fall, **befund.details}
        if befund.fall == FALL_TREFFER and "rueckfrage" in r.parameter:
            details["rueckfrage"] = r.parameter["rueckfrage"]
        einstufung = _aus_fall(r, "einstufung", befund.fall)
        massnahme = _aus_fall(r, "massnahme", befund.fall)
        conn.execute(
            """
            INSERT INTO meta.pruefung_treffer (lauf_id, regel_id, ebene, anzahl, umfang, beispiele, einstufung,
                                               massnahme, anhalten, beleg_sql, details)
            VALUES (%(lauf)s, %(regel)s, %(ebene)s, %(anzahl)s, %(umfang)s, %(bsp)s, %(einst)s, %(mass)s, %(halt)s,
                    %(beleg)s, %(details)s)
            ON CONFLICT (lauf_id, regel_id, ebene) DO UPDATE SET
              anzahl = EXCLUDED.anzahl, umfang = EXCLUDED.umfang, beispiele = EXCLUDED.beispiele,
              einstufung = EXCLUDED.einstufung, massnahme = EXCLUDED.massnahme, anhalten = EXCLUDED.anhalten,
              beleg_sql = EXCLUDED.beleg_sql, details = EXCLUDED.details
            """,
            {
                "lauf": lauf_id,
                "regel": r.id,
                "ebene": str(r.parameter["ebene"]),
                "anzahl": befund.anzahl,
                "umfang": befund.umfang,
                "bsp": Jsonb(befund.beispiele[:BEISPIELE_MAX]),
                "einst": None if einstufung is None else str(einstufung),
                "mass": None if massnahme is None else str(massnahme),
                "halt": halt,
                "beleg": befund.beleg_sql,
                "details": Jsonb(details),
            },
        )
        if halt:
            anhalten.append(r.name)
    return anhalten
