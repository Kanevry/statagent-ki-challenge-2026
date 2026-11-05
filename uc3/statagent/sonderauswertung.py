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
- Ablage: die CSV enthält Einzeldaten und liegt außerhalb jedes Git-Repos (``konfig.lieferungen_extern``); im Repo
  steht nur der Beleg ``abgabe/<datei>.beleg.md`` mit sha256 und Zeilenzahl.
- Freigabe: über Vertrag P (meta.protokoll, meta.freigabe, Commit genau des Belegs mit Trailer ``Freigegeben-von``);
  je Berichtsmonat genau eine freigegebene Lieferung. Scheitert die Freigabe, wird der frühere Zustand von CSV und
  Beleg wiederhergestellt (neue Dateien entfernt) und der Beleg aus dem Git-Index genommen.
- Abgabe-Definition: vor dem Schreiben prüft ``definition_pruefen``, dass ``altcodes_als_abschnitt`` genau die
  Altcodes abdeckt, die die freigegebene Zuordnungsregel des Bereinigungs-Regelsatzes in den Abschnitt legt
  (Regel Q01, wie im Sheet), und dass angehaltene Lieferungen übersprungen werden (Variante S, Annahme A13).

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
from typing import Any

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
    #: die beiden Parameter, an denen die Abgabezahl hängt (Altcodes, angehaltene Lieferungen; Annahme A13)
    parameter: dict[str, Any] = field(default_factory=dict)

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
               CASE WHEN p.geburtsdatum_status <> 'gueltig' OR p.geburtsjahr IS NULL
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
        parameter={"altcodes_als_abschnitt": list(altcodes), "angehaltene_lieferungen": modus},
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


def altcodes_soll(conn: Verbindung, regel: Regel, berichtsmonat: str) -> tuple[list[str], list[str]]:
    """Altcodes, die die Zuordnungsregeln des Bereinigungs-Regelsatzes in den Abschnitt ``oenace`` legen.

    Liefert (Codes sortiert, Namen der Regeln). Gelesen wird aus meta.regel (Regel Q01, Parameter ``codes`` und
    ``ziel``), nicht aus dem Code. Jede beteiligte Regel muss mit Namen freigegeben sein.
    """
    rs = str(wert(regel, "bereinigung_regelsatz"))
    abschnitt = str(wert(regel, "oenace")).strip().upper()
    codes: set[str] = set()
    namen: list[str] = []
    for r in regeln_laden(conn, rs, berichtsmonat):
        p = r.parameter
        if (
            r.typ != "zuordnung"
            or p.get("merkmal") != "oenace"
            or str(p.get("ziel", "")).upper() != abschnitt
        ):
            continue
        if not isinstance(p.get("codes"), list):
            continue
        if not r.freigegeben:
            raise NichtFreigegeben(
                f"{r.name} (Regelsatz {rs}) ist nicht freigegeben; ohne sie steht nicht fest, welche Altcodes"
                f" zu Abschnitt {abschnitt} zählen"
            )
        codes |= {str(c).strip().upper() for c in p["codes"]}
        namen.append(r.name)
    return sorted(codes), namen


def definition_pruefen(conn: Verbindung, regel: Regel, berichtsmonat: str) -> None:
    """Weist eine Definition ab, die nicht die Abgabe-Variante rechnet (Annahme A13, Persona-Panel F5).

    Dieselbe Person darf im Sheet nicht zu Abschnitt C zählen und in der Ministeriums-Lieferung aus C fallen:
    ``altcodes_als_abschnitt`` muss genau die Altcodes der freigegebenen Zuordnungsregel nennen. Angehaltene
    Lieferungen werden übersprungen (Variante S, Entscheid Lead 58). Bei Abweichung: RegelFehler mit Soll und Ist.
    """
    modus = str(wert(regel, "angehaltene_lieferungen"))
    if modus != "ueberspringen":
        raise RegelFehler(
            f"{regel.name}: angehaltene_lieferungen ist {modus!r}, Soll ist 'ueberspringen' (Variante S, Annahme A13)"
        )
    ist_roh = wert(regel, "altcodes_als_abschnitt")
    if not isinstance(ist_roh, list):
        raise RegelFehler(f"{regel.name}: altcodes_als_abschnitt muss eine Liste von Codes sein")
    ist = sorted({str(c).strip().upper() for c in ist_roh})
    soll, namen = altcodes_soll(conn, regel, berichtsmonat)
    if ist != soll:
        quelle = ", ".join(namen) or "keine Zuordnungsregel"
        raise RegelFehler(
            f"{regel.name}: altcodes_als_abschnitt ist [{', '.join(ist)}], Soll ist [{', '.join(soll)}] laut"
            f" {quelle} (Regelsatz {wert(regel, 'bereinigung_regelsatz')}); sonst zählt dieselbe Person im Sheet"
            " zu einem Abschnitt und fällt in der Lieferung heraus (Annahme A13)"
        )


def _bisherige_lieferung(conn: Verbindung, berichtsmonat: str, sha256: str) -> None:
    """Weist eine zweite Freigabe desselben Berichtsmonats ab (gleicher oder anderer Inhalt)."""
    vorher = conn.execute(
        """SELECT freigegeben_von, freigegeben_am, sha256 FROM meta.ausgabe
           WHERE art = 'ministerium' AND berichtsmonat = %s ORDER BY id LIMIT 1""",
        (berichtsmonat,),
    ).fetchone()
    if vorher is None:
        # Auch eine Freigabe über Vertrag P zählt, deren meta.ausgabe-Zeile fehlt (z. B. Abbruch nach dem Commit).
        protokoll = conn.execute(
            """SELECT name, zeit FROM meta.protokoll
               WHERE uc = 'uc3' AND vorschlag_typ = 'lieferung' AND status = 'freigegeben'
                 AND anweisung LIKE %s ORDER BY id LIMIT 1""",
            (f"Ministeriums-Lieferung {berichtsmonat} freigeben%",),
        ).fetchone()
        if protokoll is None:
            return
        raise LieferungBereitsFreigegeben(
            f"Ministeriums-Lieferung {berichtsmonat} ist bereits freigegeben von {protokoll['name']} am "
            f"{protokoll['zeit']:%d.%m.%Y %H:%M} (meta.protokoll); meta.ausgabe fehlt, bitte nachtragen statt neu freigeben"
        )
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
    """Protokolleintrag (vorschlag_typ lieferung) und Freigabe über Vertrag P: Commit genau des Belegs mit Trailer.

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


def beleg_text(regel: Regel, auswertung: Auswertung, dateiname: str, sha256: str, person: str) -> str:
    """Beleg zur Ministeriums-Lieferung für das Repo (die CSV selbst enthält Einzeldaten und bleibt draußen).

    Nennt Datei, sha256, Zeilenzahl, Definition mit Parametern, Datenstand je Monat, Erzeugungsbefehl, Freigabe und
    Abgabeweg (Entscheid Lead 58, #16: Abgabe über den SV-Box-Teamordner). Die Freigabe über Vertrag P committet
    diesen Beleg; über die sha256 ist sie an den Inhalt der CSV gebunden.
    """
    parameter = json.dumps(regel.parameter, ensure_ascii=False, sort_keys=True)
    stand = "; ".join(
        f"{m} aus Lieferung {lf}"
        + (f" (übersprungen: {auswertung.uebersprungen[m]})" if m in auswertung.uebersprungen else "")
        for m, lf in sorted(auswertung.datenstand.items())
    )
    zeilen = [
        f"# Ministeriums-Lieferung {auswertung.berichtsmonat} (Auftrag 3)",
        "",
        "Die Lieferung enthält Einzeldaten (PERSON_ID) und liegt deshalb nicht im Repo. Sie wird über den",
        "SV-Box-Teamordner (Ergebnisdateien) abgegeben. Dieser Beleg ordnet die Datei der Rechnung zu.",
        "",
        "| Angabe | Wert |",
        "| --- | --- |",
        f"| Datei | `{dateiname}` |",
        f"| sha256 | `{sha256}` |",
        f"| Zeilen | {len(auswertung.zeilen)} Personen und 1 Kopfzeile |",
        f"| Zeitraum | {auswertung.von:%d.%m.%Y} bis {auswertung.bis:%d.%m.%Y} |",
        f"| Definition | Regel `{regel.name}` im Regelsatz `{regel.regelsatz}` (meta.regel {regel.id}) |",
        f"| Parameter | `{parameter}` |",
        f"| Datenstand je Monat | {stand} |",
        f'| Erzeugt mit | `uv run uc3 ministerium --monat {auswertung.berichtsmonat} --name "{person}"` |',
        f"| Freigegeben von | {person} (Commit-Trailer Freigegeben-von, meta.freigabe) |",
        "| Abgabeweg | SV-Box-Teamordner, Ergebnisdateien (nicht im öffentlichen Repo) |",
        "",
    ]
    return "\n".join(zeilen)


def ministerium_schreiben(
    conn: Verbindung,
    berichtsmonat: str,
    name: str,
    *,
    regelsatz: str = "ministerium",
    ziel_dir: Path | None = None,
    beleg_dir: Path | None = None,
    repo_pfad: Path | None = None,
) -> tuple[Path, Auswertung]:
    """Rechnet die Lieferung, schreibt die CSV außerhalb des Repos und gibt den Beleg mit Namen frei.

    Ablauf: (1) Definition gegen die Abgabe-Variante prüfen (``definition_pruefen``), (2) rechnen, (3) eine
    frühere Freigabe desselben Berichtsmonats abweisen, (4) CSV in die Ablage außerhalb jedes Git-Repos schreiben
    (``konfig.lieferungen_extern``, Einzeldaten), (5) Beleg ``<datei>.beleg.md`` im Repo schreiben (sha256, Zeilen,
    Definition, Abgabeweg), (6) mit ``repo_pfad`` Protokolleintrag und Freigabe über Vertrag P (Commit genau des
    Belegs mit Trailer ``Freigegeben-von``), (7) meta.ausgabe mit ``protokoll_id``. Scheitert (6), werden CSV und
    Beleg auf den Stand davor zurückgesetzt (frühere Fassung wiederhergestellt, neue Datei entfernt) und der Beleg
    aus dem Git-Index genommen.
    """
    person = name_pruefen(name)
    regel = auswertung_regel(conn, regelsatz)
    definition_pruefen(conn, regel, berichtsmonat)
    auswertung = personentage(conn, regel, berichtsmonat)
    datei = (ziel_dir or konfig.lieferungen_extern()) / str(wert(regel, "datei")).format(
        berichtsmonat=berichtsmonat
    )
    if konfig.im_repo(datei, repo_pfad):
        raise RegelFehler(
            f"{datei.name} enthält Einzeldaten und darf nicht im Repo liegen, auch in keinem anderen Git-Repo;"
            " Ablage außerhalb, z. B. STATAGENT_LIEFERUNGEN oder lieferungen/ neben dem Repo"
        )
    beleg = (beleg_dir or konfig.abgabe()) / f"{datei.stem}.beleg.md"
    wurzel = (repo_pfad or konfig.REPO_WURZEL).resolve()
    beleg_ref: str | None = None
    if repo_pfad is not None:
        try:
            beleg_ref = beleg.resolve().relative_to(wurzel).as_posix()
        except ValueError:
            raise RegelFehler(
                f"Der Beleg {beleg.name} muss im Repo liegen, sonst lässt er sich nicht freigeben"
            ) from None
    inhalt = auswertung.csv([str(f) for f in wert(regel, "felder")], str(wert(regel, "trennzeichen")))
    sha = hashlib.sha256(inhalt.encode("utf-8")).hexdigest()
    _bisherige_lieferung(conn, berichtsmonat, sha)
    datei.parent.mkdir(parents=True, exist_ok=True)
    beleg.parent.mkdir(parents=True, exist_ok=True)
    # Frühere Fassungen merken: scheitert die Freigabe, wird der alte Zustand wiederhergestellt statt gelöscht.
    vorher = {p: (p.read_bytes() if p.is_file() else None) for p in (datei, beleg)}
    # Bytes statt Text: LF-Zeilenende auf jedem System, die Datei entspricht genau der sha256 im Beleg.
    datei.write_bytes(inhalt.encode("utf-8"))
    beleg.write_text(beleg_text(regel, auswertung, datei.name, sha, person), encoding="utf-8")
    protokoll_id: int | None = None
    if repo_pfad is not None and beleg_ref is not None:
        try:
            protokoll_id = _lieferung_freigeben(
                conn, person, repo_pfad, beleg_ref, berichtsmonat, auswertung, sha
            )
        except Exception as fehler:
            # nicht freigegeben: keine neue Datei, die wie eine Lieferung aussieht; Vorhandenes bleibt erhalten.
            # Der Beleg ist schon gestaged (git add vor dem Commit): aus dem Index nehmen, sonst landet er im
            # nächsten Commit ohne Freigabe.
            from plattform.freigabe import GitFehler, _git

            try:
                _git(repo_pfad, "reset", "-q", "--", beleg_ref)
            except GitFehler as reset_fehler:
                fehler.add_note(f"Beleg {beleg_ref} ist noch gestaged: {reset_fehler}")
            for pfad, alt in vorher.items():
                if alt is None:
                    pfad.unlink(missing_ok=True)
                else:
                    pfad.write_bytes(alt)
            raise
    with conn.transaction():
        conn.execute(
            """INSERT INTO meta.ausgabe (art, berichtsmonat, regel_id, datei, zeilen, sha256, datenstand,
                 freigegeben_von, protokoll_id)
               VALUES ('ministerium', %s, %s, %s, %s, %s, %s::jsonb, %s, %s)""",
            (
                berichtsmonat,
                regel.id,
                datei.name,  # nur der Dateiname: die CSV liegt außerhalb des Repos, kein lokaler Pfad in Protokollen
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
