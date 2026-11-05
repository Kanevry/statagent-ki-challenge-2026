"""Sonderauswertung „Personentage“ (Änderungsauftrag 3, Ministeriums-Lieferung).

Die Definition ist eine Regel in meta.regel (eigener Regelsatz, typ ``zaehl``, art ``personentage``), die ein
eigener Agent vorschlägt und eine Person freigibt. Dieses Modul rechnet nur, ohne Sprachmodell:

- Zeitraum: die letzten ``monate`` Monate bis einschließlich Berichtsmonat.
- Datenstand: für jeden Tag die jüngste Lieferung, die ihn enthält (eine Lieferung enthält ihren Monat und die zwei
  Vormonate). Optional werden Lieferungen übersprungen, deren Lauf eine Prüfregel angehalten hat (Teil-Lieferung).
- Tage: Kalendertage, an denen mindestens ein passender Zeitabschnitt besteht; gleichzeitige Verhältnisse zählen
  einen Tag einmal (``range_agg``), DV- und FD-Tage zusammen.
- Abschnitt: ``oenace`` ist der Abschnitt nach der Bereinigung. Zeitabschnitte, deren gelieferter Code ein Altcode
  ist (z. B. ÖNACE-2003-Unterabschnitte, die die Quellzuordnung in den Abschnitt übernimmt), zählen nur, wenn der
  Code in ``altcodes_als_abschnitt`` steht (leere Liste: nur direkt als Abschnitt gelieferte Codes).
- Ausgabe: eine Zeile je Person mit mindestens ``mindesttage`` Tagen, sortiert nach PERSON_ID.
- Freigabe: über Vertrag P (meta.protokoll, meta.freigabe, Commit genau der CSV mit Trailer ``Freigegeben-von``);
  je Berichtsmonat genau eine freigegebene Lieferung.

Warum das Lieferfenster „Monat bis Monat + 2“ dasselbe ist wie „je Tag die jüngste Lieferung, die ihn enthält“:
jede Lieferung ist ein Vollabzug über ihren Berichtsmonat und die zwei Vormonate (Fachbeschreibung § 2). Ein Tag
des Monats m steht also genau in den Lieferungen m, m + 1 und m + 2, und alle Tage eines Monats haben dieselbe
jüngste Lieferung. Herleitung und Varianten: docs/plan/uc3/ministerium-oracle.md.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from statagent import ergebnis, konfig
from statagent.db import Verbindung, lieferungen, tupelzeilen
from statagent.regeln import Regel, RegelFehler, eine, name_pruefen, regeln_laden, wert

#: Parameter, die die Art ``personentage`` liest (jeder ist Pflicht, siehe ``regeln.wert``). Die Agenten prüfen
#: neue Auswertungsregeln gegen diese Liste (agenten/koordinator.py).
PERSONENTAGE_PARAMETER = frozenset(
    {
        "monate",
        "qualifikationen",
        "oenace",
        "altcodes_als_abschnitt",
        "mindesttage",
        "datenstand",
        "angehaltene_lieferungen",
        "bereinigung_regelsatz",
        "geburtsjahr_unplausibel",
        "felder",
        "datei",
        "trennzeichen",
    }
)


class NichtFreigegeben(RuntimeError):
    """Eine Auswertung startet nur mit freigegebener Definition (Technische Regel 6d)."""


class LieferungBereitsFreigegeben(RuntimeError):
    """Für den Berichtsmonat ist schon eine Lieferung freigegeben; eine neue Fassung braucht einen neuen Auftrag."""


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
    altcodes = wert(regel, "altcodes_als_abschnitt")
    if not isinstance(altcodes, list) or not all(isinstance(c, str) and c.strip() for c in altcodes):
        raise RegelFehler(f"{regel.name}: altcodes_als_abschnitt muss eine Liste von Codes sein (auch leer)")
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
            AND (a.roh_oenace IS NULL OR upper(btrim(a.roh_oenace)) = %(oen)s
                 OR upper(btrim(a.roh_oenace)) = ANY(%(alt)s))
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
            "alt": [c.strip().upper() for c in altcodes],
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


def _bisherige_lieferung(conn: Verbindung, berichtsmonat: str, sha256: str) -> None:
    """Weist eine zweite Freigabe desselben Berichtsmonats ab (gleicher oder anderer Inhalt)."""
    vorher = conn.execute(
        """SELECT freigegeben_von, freigegeben_am, sha256 FROM meta.ausgabe
           WHERE art = 'ministerium' AND berichtsmonat = %s ORDER BY id LIMIT 1""",
        (berichtsmonat,),
    ).fetchone()
    if vorher is None:
        return
    am = f"{vorher['freigegeben_am']:%d.%m.%Y %H:%M}"
    if vorher["sha256"] == sha256:
        raise LieferungBereitsFreigegeben(
            f"Ministeriums-Lieferung {berichtsmonat} ist bereits freigegeben von {vorher['freigegeben_von']} am {am}"
        )
    raise LieferungBereitsFreigegeben(
        f"Ministeriums-Lieferung {berichtsmonat} ist bereits freigegeben von {vorher['freigegeben_von']} am {am};"
        " der neu gerechnete Inhalt weicht ab. Eine neue Fassung braucht einen neuen Auftrag"
    )


def _lieferung_freigeben(
    conn: Verbindung,
    person: str,
    repo_pfad: Path,
    ref: str,
    berichtsmonat: str,
    auswertung: Auswertung,
    sha: str,
) -> int:
    """Protokolleintrag (vorschlag_typ lieferung) und Freigabe über Vertrag P: Commit genau der CSV mit Trailer.

    Scheitert die Freigabe (Git, Lock, Pfad), wird der Eintrag mit dem technischen Grund abgelehnt und der Fehler
    weitergeworfen; dann entsteht keine Ausgabe.
    """
    from plattform.freigabe import ablehnen, freigeben

    with conn.transaction():
        eintrag = conn.execute(
            """INSERT INTO meta.protokoll (uc, akteur, name, anweisung, wirkung, vorschlag_typ, ref)
               VALUES ('uc3', 'mensch', %s, %s, %s, 'lieferung', %s) RETURNING id""",
            (
                person,
                f"Ministeriums-Lieferung {berichtsmonat} freigeben (Auftrag 3, Regel {auswertung.regel})",
                f"{len(auswertung.zeilen)} Personen, Zeitraum {auswertung.von} bis {auswertung.bis},"
                f" sha256 {sha[:12]}",
                ref,
            ),
        ).fetchone()
    assert eintrag is not None
    protokoll_id = int(str(eintrag["id"]))
    try:
        with tupelzeilen(conn):
            freigeben(conn, protokoll_id, person, repo_pfad, objekt_typ="datei", objekt_ref=ref)
    except Exception as fehler:
        with tupelzeilen(conn):
            ablehnen(
                conn,
                protokoll_id,
                person,
                f"Freigabe technisch abgebrochen ({type(fehler).__name__}: {fehler}); keine Lieferung freigegeben",
                objekt_typ="datei",
                objekt_ref=ref,
            )
        raise
    return protokoll_id


def ministerium_schreiben(
    conn: Verbindung,
    berichtsmonat: str,
    name: str,
    *,
    regelsatz: str = "ministerium",
    ziel_dir: Path | None = None,
    repo_pfad: Path | None = None,
) -> tuple[Path, Auswertung]:
    """Rechnet die Lieferung, schreibt die CSV und gibt sie mit Namen frei.

    Ablauf: (1) rechnen, (2) eine frühere Freigabe desselben Berichtsmonats abweisen, (3) CSV schreiben,
    (4) mit ``repo_pfad`` Protokolleintrag und Freigabe über Vertrag P (Commit genau dieser Datei mit Trailer
    ``Freigegeben-von``), (5) meta.ausgabe mit ``protokoll_id``. Scheitert (4), wird die CSV wieder entfernt.
    """
    person = name_pruefen(name)
    regel = auswertung_regel(conn, regelsatz)
    auswertung = personentage(conn, regel, berichtsmonat)
    datei = (ziel_dir or konfig.abgabe()) / str(wert(regel, "datei")).format(berichtsmonat=berichtsmonat)
    inhalt = auswertung.csv([str(f) for f in wert(regel, "felder")], str(wert(regel, "trennzeichen")))
    sha = hashlib.sha256(inhalt.encode("utf-8")).hexdigest()
    wurzel = (repo_pfad or konfig.REPO_WURZEL).resolve()
    try:
        relativ = datei.resolve().relative_to(wurzel).as_posix()
    except ValueError:
        if repo_pfad is not None:
            raise RegelFehler(
                f"{datei} liegt nicht im Repo {wurzel}; so lässt sie sich nicht freigeben"
            ) from None
        relativ = str(datei)
    _bisherige_lieferung(conn, berichtsmonat, sha)
    datei.parent.mkdir(parents=True, exist_ok=True)
    datei.write_text(inhalt, encoding="utf-8")
    protokoll_id: int | None = None
    if repo_pfad is not None:
        try:
            protokoll_id = _lieferung_freigeben(
                conn, person, repo_pfad, relativ, berichtsmonat, auswertung, sha
            )
        except Exception:
            datei.unlink(missing_ok=True)  # nicht freigegeben: keine Datei, die wie eine Lieferung aussieht
            raise
    with conn.transaction():
        conn.execute(
            """INSERT INTO meta.ausgabe (art, berichtsmonat, regel_id, datei, zeilen, sha256, datenstand,
                 freigegeben_von, protokoll_id)
               VALUES ('ministerium', %s, %s, %s, %s, %s, %s::jsonb, %s, %s)""",
            (
                berichtsmonat,
                regel.id,
                relativ,
                len(auswertung.zeilen),
                sha,
                json.dumps(
                    {"datenstand": auswertung.datenstand, "uebersprungen": auswertung.uebersprungen},
                    sort_keys=True,
                ),
                person,
                protokoll_id,
            ),
        )
    return datei, auswertung
