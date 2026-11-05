"""Sonderauswertung „Personentage“ (Änderungsauftrag 3, Ministeriums-Lieferung).

Die Definition ist eine Regel in meta.regel (eigener Regelsatz, typ ``zaehl``, art ``personentage``), die ein
eigener Agent vorschlägt und eine Person freigibt. Dieses Modul rechnet nur, ohne Sprachmodell:

- Zeitraum: die letzten ``monate`` Monate bis einschließlich Berichtsmonat.
- Datenstand: für jeden Tag die jüngste Lieferung, die ihn enthält (eine Lieferung enthält ihren Monat und die zwei
  Vormonate). Optional werden Lieferungen übersprungen, deren Lauf eine Prüfregel angehalten hat (Teil-Lieferung).
- Tage: Kalendertage, an denen mindestens ein passender Zeitabschnitt besteht; gleichzeitige Verhältnisse zählen
  einen Tag einmal (``range_agg``), DV- und FD-Tage zusammen.
- Ausgabe: eine Zeile je Person mit mindestens ``mindesttage`` Tagen, sortiert nach PERSON_ID.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from statagent import ergebnis, konfig
from statagent.db import Verbindung, lieferungen
from statagent.regeln import Regel, RegelFehler, eine, name_pruefen, regeln_laden, wert


class NichtFreigegeben(RuntimeError):
    """Eine Auswertung startet nur mit freigegebener Definition (Technische Regel 6d)."""


@dataclass
class Auswertung:
    berichtsmonat: str
    regel: str
    von: date
    bis: date
    datenstand: dict[str, str]  # Monat -> verwendete Lieferung
    uebersprungen: dict[str, str] = field(default_factory=dict)  # Monat -> übersprungene Lieferung
    zeilen: list[tuple[int, str, str, int]] = field(default_factory=list)

    def csv(self, felder: list[str], trennzeichen: str) -> str:
        kopf = trennzeichen.join(felder)
        return "\n".join([kopf, *(trennzeichen.join(str(w) for w in z) for z in self.zeilen)]) + "\n"


def _angehalten(conn: Verbindung, lieferung: str, regelsatz: str) -> bool:
    stand = ergebnis.letzter_lauf(conn, lieferung, regelsatz)
    if stand is None:
        return False
    z = conn.execute(
        "SELECT EXISTS (SELECT 1 FROM meta.pruefung_treffer WHERE lauf_id = %s AND anhalten) AS a",
        (stand.lauf_id,),
    ).fetchone()
    return bool(z and z["a"])


def datenstand_waehlen(
    conn: Verbindung, monate: list[str], regelsatz: str, ueberspringen: bool
) -> tuple[dict[str, str], dict[str, str]]:
    """Je Monat die jüngste gerechnete Lieferung, die den Monat enthält (Lieferfenster: Monat bis Monat + 2)."""
    gerechnet = [m for m in lieferungen(conn) if ergebnis.letzter_lauf(conn, m, regelsatz) is not None]
    stand: dict[str, str] = {}
    uebersprungen: dict[str, str] = {}
    for monat in monate:
        kandidaten = sorted(
            (lf for lf in gerechnet if monat <= lf <= ergebnis.monat_verschieben(monat, 2)), reverse=True
        )
        for lieferung in kandidaten:
            if ueberspringen and _angehalten(conn, lieferung, regelsatz):
                uebersprungen.setdefault(monat, lieferung)
                continue
            stand[monat] = lieferung
            break
        if monat not in stand:
            if not kandidaten:
                raise RegelFehler(f"für {monat} gibt es keine gerechnete Lieferung im Lieferfenster")
            # Alle Lieferungen im Fenster angehalten: die jüngste trotzdem verwenden und das festhalten.
            stand[monat] = kandidaten[0]
            uebersprungen[monat] = f"{kandidaten[0]} (angehalten, mangels Alternative verwendet)"
    return stand, uebersprungen


def personentage(conn: Verbindung, regel: Regel, berichtsmonat: str) -> Auswertung:
    """Rechnet die Auswertung nach den Parametern der Regel."""
    if regel.art != "personentage":
        raise RegelFehler(f"{regel.name}: Art {regel.art!r} ist keine Personentage-Auswertung")
    anzahl = int(wert(regel, "monate"))
    monate = [ergebnis.monat_verschieben(berichtsmonat, -k) for k in range(anzahl - 1, -1, -1)]
    rs = str(wert(regel, "bereinigung_regelsatz"))
    modus = str(wert(regel, "angehaltene_lieferungen"))
    if modus not in ("ueberspringen", "verwenden"):
        raise RegelFehler(f"{regel.name}: angehaltene_lieferungen muss 'ueberspringen' oder 'verwenden' sein")
    if str(wert(regel, "datenstand")) != "juengste_lieferung_je_tag":
        raise RegelFehler(
            f"{regel.name}: nicht unterstützter Datenstand {regel.parameter.get('datenstand')!r}"
        )
    stand, uebersprungen = datenstand_waehlen(conn, monate, rs, modus == "ueberspringen")
    alter = eine(regeln_laden(conn, rs, berichtsmonat), "zaehl", "alter")
    von, bis = ergebnis.monatserster(monate[0]), ergebnis.monatsletzter(monate[-1])

    zeilen = conn.execute(
        """
        WITH quelle AS (
          SELECT * FROM unnest(%(von)s::date[], %(bis)s::date[], %(lief)s::text[]) AS q (von, bis, lieferung)
        ),
        seg AS (
          SELECT a.person_id, a.vvh_id, a.geschlecht, a.geburtsjahr, a.geburtsdatum, a.geburtsdatum_status,
                 q.lieferung, daterange(a.beginn, a.ende, '[]') * daterange(q.von, q.bis, '[]') AS r
          FROM quelle q
          JOIN bereinigt.abschnitt a ON a.lieferung = q.lieferung AND a.regelsatz = %(rs)s
          WHERE a.qualifikation = ANY(%(quals)s) AND a.oenace = %(oen)s
            AND a.beginn <= q.bis AND (a.ende IS NULL OR a.ende >= q.von)
        ),
        agg AS (SELECT person_id, range_agg(r) AS mr FROM seg WHERE NOT isempty(r) GROUP BY person_id),
        tage AS (
          SELECT person_id, sum(upper(x) - lower(x))::int AS tage FROM agg, unnest(mr) AS x GROUP BY person_id
        ),
        person AS (
          SELECT DISTINCT ON (person_id) person_id, geschlecht, geburtsjahr, geburtsdatum, geburtsdatum_status
          FROM seg ORDER BY person_id, lieferung DESC, vvh_id
        )
        SELECT p.person_id, p.geschlecht,
               CASE WHEN p.geburtsdatum_status = 'ungueltig' OR p.geburtsjahr IS NULL
                      OR coalesce(extract(year FROM age(%(stichtag)s::date, p.geburtsdatum))::int,
                                  extract(year FROM %(stichtag)s::date)::int - p.geburtsjahr) > %(amax)s
                    THEN %(unbekannt)s ELSE p.geburtsjahr::text END AS geburtsjahr,
               t.tage
        FROM tage t JOIN person p USING (person_id)
        WHERE t.tage >= %(min)s
        ORDER BY p.person_id
        """,
        {
            "von": [ergebnis.monatserster(m) for m in monate],
            "bis": [ergebnis.monatsletzter(m) for m in monate],
            "lief": [stand[m] for m in monate],
            "rs": rs,
            "quals": [str(q) for q in wert(regel, "qualifikationen")],
            "oen": str(wert(regel, "oenace")),
            "min": int(wert(regel, "mindesttage")),
            "stichtag": bis,
            "amax": int(wert(alter, "max_plausibel")),
            "unbekannt": str(wert(regel, "geburtsjahr_unplausibel")),
        },
        prepare=False,
    ).fetchall()
    return Auswertung(
        berichtsmonat=berichtsmonat,
        regel=regel.name,
        von=von,
        bis=bis,
        datenstand=stand,
        uebersprungen=uebersprungen,
        zeilen=[
            (int(str(z["person_id"])), str(z["geschlecht"]), str(z["geburtsjahr"]), int(str(z["tage"])))
            for z in zeilen
        ],
    )


def auswertung_regel(conn: Verbindung, regelsatz: str, name: str | None = None) -> Regel:
    """Die aktive Personentage-Regel eines Auswertungs-Regelsatzes; sie muss mit Namen freigegeben sein."""
    kandidaten = [
        r for r in regeln_laden(conn, regelsatz) if r.art == "personentage" and (name in (None, r.name))
    ]
    if len(kandidaten) != 1:
        raise RegelFehler(f"Regelsatz {regelsatz}: {len(kandidaten)} aktive Personentage-Regeln (erwartet 1)")
    regel = kandidaten[0]
    if not regel.freigegeben:
        raise NichtFreigegeben(f"{regel.name} ist nicht freigegeben; zuerst Vorschlag freigeben")
    return regel


def ministerium_schreiben(
    conn: Verbindung,
    berichtsmonat: str,
    name: str,
    *,
    regelsatz: str = "ministerium",
    ziel_dir: Path | None = None,
) -> tuple[Path, Auswertung]:
    """Rechnet die Lieferung, schreibt die CSV und hält die Freigabe der Lieferung mit Namen fest."""
    person = name_pruefen(name)
    regel = auswertung_regel(conn, regelsatz)
    auswertung = personentage(conn, regel, berichtsmonat)
    datei = (ziel_dir or konfig.abgabe()) / str(wert(regel, "datei")).format(berichtsmonat=berichtsmonat)
    inhalt = auswertung.csv([str(f) for f in wert(regel, "felder")], str(wert(regel, "trennzeichen")))
    datei.parent.mkdir(parents=True, exist_ok=True)
    datei.write_text(inhalt, encoding="utf-8")
    try:
        relativ = str(datei.resolve().relative_to(konfig.REPO_WURZEL))
    except ValueError:
        relativ = str(datei)
    with conn.transaction():
        conn.execute(
            """INSERT INTO meta.ausgabe (art, berichtsmonat, regel_id, datei, zeilen, sha256, datenstand,
                 freigegeben_von)
               VALUES ('ministerium', %s, %s, %s, %s, %s, %s::jsonb, %s)""",
            (
                berichtsmonat,
                regel.id,
                relativ,
                len(auswertung.zeilen),
                hashlib.sha256(inhalt.encode("utf-8")).hexdigest(),
                json.dumps(
                    {"datenstand": auswertung.datenstand, "uebersprungen": auswertung.uebersprungen},
                    sort_keys=True,
                ),
                person,
            ),
        )
    return datei, auswertung
