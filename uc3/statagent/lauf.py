"""Monatsbetrieb: ein Lauf verarbeitet genau eine Lieferung (Fachbeschreibung § 2a).

Ablauf: Vorprüfung (Lieferung vorhanden, Vormonat gelaufen) → Regeln laden und Regelstand bilden →
Bereinigung → Zählung → Revisionsbedarf der Vormonate → Prüfungen → Ergebnis vorläufig schreiben oder als
unverändert erkennen. Endgültig wird ein Monat erst durch `veroeffentlichen` mit Namen (Technische Regel 7).
Der Lauf braucht kein Sprachmodell und importiert keines (Technische Regeln 1 und 2).
"""

from __future__ import annotations

import importlib
import importlib.util
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from statagent import ergebnis
from statagent.bereinigung import bereinigen
from statagent.db import Verbindung, lieferungen, tupelzeilen
from statagent.regeln import (
    Regel,
    RegelFehler,
    name_pruefen,
    regeln_laden,
    regelstand,
    regelstand_freigegeben,
)
from statagent.revision import revision_berechnen
from statagent.zaehlung import zaehlen
from statagent.zeit import zeit_text


class LaufFehler(RuntimeError):
    """Der Lauf darf so nicht starten oder wurde abgebrochen."""


@dataclass
class LaufErgebnis:
    lauf_id: int
    lieferung: str
    regelsatz: str
    regelstand: str
    status: str  # fertig | unveraendert | abgebrochen
    ergebnis_status: str  # vorlaeufig | endgueltig
    gelesen: int
    gezaehlt: int
    nicht_gezaehlt: int
    ausgeschlossen: int
    korrigiert: int
    fortgeschrieben: int
    ergebnis_hash: str
    zellen: int
    meldung: str

    def als_dict(self) -> dict[str, Any]:
        return asdict(self)


def _pruefungen_ausfuehren(
    conn: Verbindung, lauf_id: int, lieferung: str, regelsatz: str, regeln: list[Regel]
) -> list[str]:
    """Führt die Prüfregeln aus, wenn das Modul vorhanden ist. Liefert Namen der Regeln, die anhalten."""
    if importlib.util.find_spec("statagent.pruefungen") is None:
        return []
    modul = importlib.import_module("statagent.pruefungen")  # Fehler im Modul selbst schlagen durch
    anhalten: list[str] = modul.pruefungen_ausfuehren(
        conn, lauf_id=lauf_id, lieferung=lieferung, regelsatz=regelsatz, regeln=regeln
    )
    return anhalten


def lauf_ausfuehren(
    conn: Verbindung,
    lieferung: str,
    regelsatz: str = "v1",
    *,
    gestartet_von: str | None = None,
    reihenfolge_pruefen: bool = True,
) -> LaufErgebnis:
    """Rechnet den Berichtsmonat `lieferung` aus seiner eigenen Lieferung."""
    vorhanden = lieferungen(conn)
    if lieferung not in vorhanden:
        raise LaufFehler(
            f"Lieferung {lieferung} ist nicht geladen (roh.ladeprotokoll kennt {len(vorhanden)})"
        )
    vormonat = ergebnis.monat_verschieben(lieferung, -1)
    if (
        reihenfolge_pruefen
        and vormonat in vorhanden
        and ergebnis.letzter_lauf(conn, vormonat, regelsatz) is None
    ):
        raise LaufFehler(
            f"Lieferungen werden in zeitlicher Reihenfolge verarbeitet: zuerst `lauf --lieferung {vormonat}`"
        )

    regeln = regeln_laden(conn, regelsatz, lieferung)
    if not regeln:
        raise LaufFehler(f"Regelsatz {regelsatz} hat keine aktiven Regeln für {lieferung}")
    stand = regelstand(conn, regeln)
    alle_frei = all(r.freigegeben for r in regeln)

    if not conn.autocommit:
        conn.commit()  # eigene Transaktionsblöcke statt Savepoints in einer offenen Transaktion
    with conn.transaction():
        z = conn.execute(
            """INSERT INTO meta.lauf (lieferung, regelsatz, regelstand, gestartet_von)
               VALUES (%s, %s, %s, %s) RETURNING id""",
            (lieferung, regelsatz, stand, gestartet_von),
        ).fetchone()
    assert z is not None
    lauf_id = int(str(z["id"]))

    try:
        with conn.transaction():
            b = bereinigen(conn, lauf_id=lauf_id, lieferung=lieferung, regelsatz=regelsatz, regeln=regeln)
            zl = zaehlen(
                conn, lieferung=lieferung, berichtsmonat=lieferung, regelsatz=regelsatz, regeln=regeln
            )
            # Abrechnung aus unabhängig gezählten Größen: roh.lieferung, Verdichtung, Bestand, Abschnittszählung.
            # Eine Ausschlussregel (z. B. „ohne Beamte“) zählt Verhältnisse nicht; verloren geht keines, sie stehen
            # unter „nicht gezählt“. Ohne Ausschlussregel ist zl.ausgeschlossen_merkmal 0.
            mehrfach_abschnitte = zl.aktive_abschnitte - zl.gezaehlt - zl.ausgeschlossen_merkmal
            nicht_gezaehlt = zl.nicht_aktiv + mehrfach_abschnitte + zl.ausgeschlossen_merkmal
            if b.abschnitte != zl.aktive_abschnitte + zl.nicht_aktiv:
                raise RegelFehler("Abschnitte aus der Bereinigung ≠ aktive + nicht aktive Abschnitte")
            unabhaengig = _bestand_aus_roh(conn, lieferung, regelsatz, regeln, zl.zeitraum, b.spaltentausch)
            if unabhaengig is not None and unabhaengig != zl.gezaehlt + zl.ausgeschlossen_merkmal:
                raise RegelFehler(
                    f"Gegenrechnung aus roh.lieferung ergibt {unabhaengig} Verhältnisse, gezählt sind {zl.gezaehlt}"
                    + (
                        f" und ausgeschlossen {zl.ausgeschlossen_merkmal}"
                        if zl.ausgeschlossen_merkmal
                        else ""
                    )
                )
            if b.gelesen + b.fortgeschrieben != zl.gezaehlt + nicht_gezaehlt + b.ausgeschlossen:
                raise RegelFehler(
                    "Abrechnung geht nicht auf: gelesen + fortgeschrieben ≠ gezählt + nicht gezählt + ausgeschlossen"
                )

            for regel_id, saetze in sorted(b.wirkung.items()):
                conn.execute(
                    "INSERT INTO meta.regel_wirkung (lauf_id, regel_id, saetze) VALUES (%s, %s, %s)",
                    (lauf_id, regel_id, saetze),
                )
            wirkung_zaehl = {
                "bestand": zl.gezaehlt,
                "abschnittswahl": zl.mehrfach,
                "alter": zl.alter_unbekannt,
                "ausschluss": zl.ausgeschlossen_merkmal,
            }
            for r in (r for r in regeln if r.typ == "zaehl"):
                conn.execute(
                    "INSERT INTO meta.regel_wirkung (lauf_id, regel_id, saetze) VALUES (%s, %s, %s)",
                    (lauf_id, r.id, wirkung_zaehl.get(r.art, zl.gezaehlt)),
                )

            revision_berechnen(conn, lauf_id=lauf_id, lieferung=lieferung, regelsatz=regelsatz, regeln=regeln)
            anhalten = _pruefungen_ausfuehren(conn, lauf_id, lieferung, regelsatz, regeln)
            # Ein Lauf schreibt vorläufig; endgültig wird ein Monat erst durch `veroeffentlichen` mit Namen.
            ergebnis_status = "vorlaeufig"

            vorher = conn.execute(
                """SELECT status, count(*) AS n, max(lauf_id) AS lauf_id FROM stat.stat_beschaeftigte
                   WHERE regelsatz = %s AND regelstand = %s AND zeitraum_art = %s
                     AND zeitraum_von = %s AND zeitraum_bis = %s GROUP BY status""",
                (regelsatz, stand, zl.zeitraum.art, zl.zeitraum.von, zl.zeitraum.bis),
            ).fetchall()
            status_vorher = {str(v["status"]): int(str(v["n"])) for v in vorher}
            lauf_status = "fertig"
            meldung_teile: list[str] = []
            if not alle_frei:
                offen = sorted(r.name for r in regeln if not r.freigegeben)
                meldung_teile.append(f"{len(offen)} Regeln ohne Freigabe: Ergebnis vorläufig")
            if anhalten:
                meldung_teile.append("angehalten durch " + ", ".join(anhalten))
            if b.fortgeschrieben:
                meldung_teile.append(
                    f"{b.fortgeschrieben} Verhältnisse aus {b.fortschreibung.get('vormonat')} fortgeschrieben "
                    f"({b.fortschreibung.get('ausloeser')}): Ergebnis vorläufig"
                )

            hash_vorher = _hash_bestehend(
                conn, regelsatz, stand, zl.zeitraum.art, zl.zeitraum.von, zl.zeitraum.bis
            )
            veroeffentlicht = _veroeffentlichter_stand(conn, regelsatz, zl.zeitraum)
            stand_ergebnis, hash_ergebnis = stand, zl.ergebnis_hash
            if veroeffentlicht is not None:
                # Veröffentlichtes bleibt unverändert, gleich unter welchem Regelstand (Fachbeschreibung § 4 Nr. 4).
                v_stand, v_wert = veroeffentlicht
                stand_ergebnis = v_stand
                hash_ergebnis = (
                    _hash_bestehend(
                        conn, regelsatz, v_stand, zl.zeitraum.art, zl.zeitraum.von, zl.zeitraum.bis
                    )
                    or ""
                )
                lauf_status = "unveraendert"
                ergebnis_status = "endgueltig"
                if v_stand == stand and hash_vorher != zl.ergebnis_hash:
                    raise LaufFehler(
                        "Gleicher Regelstand, anderes Ergebnis als veröffentlicht: der Lauf ist nicht deterministisch."
                    )
                if v_stand == stand:
                    meldung_teile.append("bereits veröffentlicht, Ergebnis identisch")
                else:
                    meldung_teile.append(
                        f"veröffentlicht unter Regelstand {v_stand} bleibt; Regelstand {stand} ergäbe "
                        f"{zl.gezaehlt} statt {v_wert} ({zl.gezaehlt - v_wert:+d}), siehe Revisionsbedarf"
                    )
                    _revision_regelwechsel(conn, lauf_id, lieferung, regelsatz, v_stand, zl.zeitraum)
                conn.execute(
                    """UPDATE meta.lauf SET (freigegeben_von, freigegeben_am) = (
                         SELECT freigegeben_von, freigegeben_am FROM meta.lauf
                         WHERE lieferung = %s AND regelsatz = %s AND regelstand = %s AND freigegeben_von IS NOT NULL
                         ORDER BY id DESC LIMIT 1)
                       WHERE id = %s""",
                    (lieferung, regelsatz, v_stand, lauf_id),
                )
            elif status_vorher and hash_vorher == zl.ergebnis_hash:
                lauf_status = "unveraendert"
                meldung_teile.append("Ergebnis identisch mit vorigem Lauf")
            else:
                if status_vorher:
                    conn.execute(
                        """DELETE FROM stat.stat_beschaeftigte
                           WHERE regelsatz = %s AND regelstand = %s AND zeitraum_art = %s
                             AND zeitraum_von = %s AND zeitraum_bis = %s AND status = 'vorlaeufig'""",
                        (regelsatz, stand, zl.zeitraum.art, zl.zeitraum.von, zl.zeitraum.bis),
                    )
                conn.execute(
                    """INSERT INTO stat.stat_beschaeftigte (zeitraum_art, zeitraum_von, zeitraum_bis, region, oenace,
                         oenace_version, geschlecht, qualifikation, alter, variable, wert, status, stand, regelsatz,
                         regelstand, lauf_id)
                       SELECT zeitraum_art, zeitraum_von, zeitraum_bis, region, oenace, oenace_version, geschlecht,
                              qualifikation, alter, variable, wert, %s, %s, %s, %s, %s
                       FROM _zellen""",
                    (ergebnis_status, f"Lieferung {lieferung}", regelsatz, stand, lauf_id),
                )
            kennzahlen = {
                "gelesen": b.gelesen,
                "gezaehlt": zl.gezaehlt,
                "nicht_gezaehlt": nicht_gezaehlt,
                "ausgeschlossen": b.ausgeschlossen,
                "korrigiert": b.korrigiert,
                "fortgeschrieben": b.fortgeschrieben,
                "zellen": zl.zellen,
            }
            if veroeffentlicht is not None:
                # Kennzahlen des veröffentlichten Laufs: meta.lauf zeigt nie eine unveröffentlichte Zahl neben dem
                # veröffentlichten Hash; die Abweichung steht nur in meta.revision.
                quelle = conn.execute(
                    """SELECT gelesen, gezaehlt, nicht_gezaehlt, ausgeschlossen, korrigiert, fortgeschrieben, zellen
                       FROM meta.lauf WHERE id = (
                         SELECT min(lauf_id) FROM stat.stat_beschaeftigte
                         WHERE regelsatz = %s AND regelstand = %s AND zeitraum_art = %s AND zeitraum_von = %s
                           AND zeitraum_bis = %s AND status = 'endgueltig')""",
                    (regelsatz, stand_ergebnis, zl.zeitraum.art, zl.zeitraum.von, zl.zeitraum.bis),
                ).fetchone()
                if quelle is not None:
                    kennzahlen = {k: int(str(v)) for k, v in quelle.items()}
            meldung = "; ".join(meldung_teile)
            conn.execute(
                """UPDATE meta.lauf SET beendet_am = now(), status = %s, ergebnis_status = %s, gelesen = %s,
                     gezaehlt = %s, nicht_gezaehlt = %s, ausgeschlossen = %s, korrigiert = %s, ergebnis_hash = %s,
                     zellen = %s, meldung = %s, regelstand = %s, fortgeschrieben = %s
                   WHERE id = %s""",
                (
                    lauf_status,
                    ergebnis_status,
                    kennzahlen["gelesen"],
                    kennzahlen["gezaehlt"],
                    kennzahlen["nicht_gezaehlt"],
                    kennzahlen["ausgeschlossen"],
                    kennzahlen["korrigiert"],
                    hash_ergebnis,
                    kennzahlen["zellen"],
                    meldung,
                    stand_ergebnis,
                    kennzahlen["fortgeschrieben"],
                    lauf_id,
                ),
            )
    except Exception as fehler:
        with conn.transaction():
            conn.execute(
                "UPDATE meta.lauf SET beendet_am = now(), status = 'abgebrochen', meldung = %s WHERE id = %s",
                (_meldung_ohne_daten(fehler), lauf_id),
            )
        raise

    return LaufErgebnis(
        lauf_id=lauf_id,
        lieferung=lieferung,
        regelsatz=regelsatz,
        regelstand=stand_ergebnis,
        status=lauf_status,
        ergebnis_status=ergebnis_status,
        gelesen=kennzahlen["gelesen"],
        gezaehlt=kennzahlen["gezaehlt"],
        nicht_gezaehlt=kennzahlen["nicht_gezaehlt"],
        ausgeschlossen=kennzahlen["ausgeschlossen"],
        korrigiert=kennzahlen["korrigiert"],
        fortgeschrieben=kennzahlen["fortgeschrieben"],
        ergebnis_hash=hash_ergebnis,
        zellen=kennzahlen["zellen"],
        meldung=meldung,
    )


def _bestand_aus_roh(
    conn: Verbindung, lieferung: str, regelsatz: str, regeln: list[Regel], zeitraum: Any, tausch: bool
) -> int | None:
    """Unabhängige Gegenrechnung des Bestands direkt aus roh.lieferung (ohne bereinigt.abschnitt und ohne
    Abschnittswahl): je VVH_ID einmal, Abschnitt besteht im Berichtszeitraum, BEGINN/ENDE nach Spaltentausch und
    Datumsmuster; dazu die fortgeschriebenen Verhältnisse (E07), die nicht in der Lieferung stehen.

    Enthält die Lieferung Daten, die eine Einleseregel ersetzt (ungültiges BEGINN/ENDE), gibt es keine einfache
    Gegenrechnung: dann None (in den 24 Lieferungen gemessen 0 solche Sätze)."""
    muster = str(next(r for r in regeln if r.typ == "einlese" and r.art == "datum").parameter["muster"])
    beginn, ende = ("ende", "beginn") if tausch else ("beginn", "ende")
    z = conn.execute(
        f"""
        WITH r AS (SELECT vvh_id, {beginn} AS b, {ende} AS e FROM roh.lieferung WHERE lieferung = %(l)s)
        SELECT count(*) FILTER (WHERE b IS NULL OR NOT (b ~ %(m)s AND pg_input_is_valid(b, 'date'))
                                   OR (e IS NOT NULL AND NOT (e ~ %(m)s AND pg_input_is_valid(e, 'date')))) AS ersetzt,
               (SELECT count(DISTINCT vvh_id) FROM r
                WHERE b ~ %(m)s AND pg_input_is_valid(b, 'date') AND b::date <= %(bis)s
                  AND (e IS NULL OR (e ~ %(m)s AND pg_input_is_valid(e, 'date') AND e::date >= %(von)s))) AS bestand,
               (SELECT count(DISTINCT a.vvh_id) FROM bereinigt.abschnitt a
                WHERE a.lieferung = %(l)s AND a.regelsatz = %(rs)s AND a.herkunft = 'fortgeschrieben'
                  AND a.beginn <= %(bis)s AND (a.ende IS NULL OR a.ende >= %(von)s)) AS fortgeschrieben
        FROM r
        """.encode(),
        {"l": lieferung, "rs": regelsatz, "m": muster, "von": zeitraum.von, "bis": zeitraum.bis},
        prepare=False,
    ).fetchone()
    if z is None or int(str(z["ersetzt"])) > 0:
        return None
    return int(str(z["bestand"])) + int(str(z["fortgeschrieben"]))


def _revision_regelwechsel(
    conn: Verbindung, lauf_id: int, lieferung: str, regelsatz: str, v_stand: str, zeitraum: Any
) -> None:
    """Revisionsbedarf eines veröffentlichten Monats unter neuem Regelstand: jede Gliederung, veröffentlicht
    (stat.stat_beschaeftigte) gegen neu gerechnet (_zellen). Veröffentlichtes bleibt unverändert."""
    for gliederung, spalte in (
        ("insgesamt", "'AT'"),
        ("region", "region"),
        ("geschlecht", "geschlecht"),
        ("qualifikation", "qualifikation"),
        ("oenace", "oenace"),
    ):
        conn.execute(
            f"""
            INSERT INTO meta.revision (lauf_id, berichtsmonat, gliederung, schluessel, veroeffentlicht, aktuell,
                                       status_vorher)
            SELECT %(lauf)s, %(l)s, %(g)s, coalesce(alt.k, neu.k), coalesce(alt.n, 0), coalesce(neu.n, 0), 'endgueltig'
            FROM (SELECT {spalte}::text AS k, sum(wert) AS n FROM stat.stat_beschaeftigte
                  WHERE regelsatz = %(rs)s AND regelstand = %(st)s AND zeitraum_art = %(art)s
                    AND zeitraum_von = %(von)s AND zeitraum_bis = %(bis)s AND status = 'endgueltig' GROUP BY 1) alt
            FULL JOIN (SELECT {spalte}::text AS k, sum(wert) AS n FROM _zellen GROUP BY 1) neu ON neu.k = alt.k
            """.encode(),
            {
                "lauf": lauf_id,
                "l": lieferung,
                "g": gliederung,
                "rs": regelsatz,
                "st": v_stand,
                "art": zeitraum.art,
                "von": zeitraum.von,
                "bis": zeitraum.bis,
            },
        )


def _meldung_ohne_daten(fehler: BaseException) -> str:
    """Fehlertext für meta.lauf: eigene Fehler im Wortlaut, Datenbankfehler nur Klasse und SQLSTATE.

    PostgreSQL-Meldungen können Werte aus Sätzen enthalten (DETAIL „Failing row contains …“); die gehören nicht
    ins Protokoll.
    """
    if isinstance(fehler, (LaufFehler, RegelFehler)):
        return f"{type(fehler).__name__}: {fehler}"
    sqlstate = getattr(fehler, "sqlstate", None)
    return f"{type(fehler).__name__}" + (f" (SQLSTATE {sqlstate})" if sqlstate else "")


def _veroeffentlichter_stand(conn: Verbindung, regelsatz: str, zeitraum: Any) -> tuple[str, int] | None:
    """Regelstand und Gesamtwert des veröffentlichten Ergebnisses für (Regelsatz, Berichtszeitraum), falls vorhanden."""
    z = conn.execute(
        """SELECT regelstand, sum(wert) AS wert FROM stat.stat_beschaeftigte
           WHERE regelsatz = %s AND zeitraum_art = %s AND zeitraum_von = %s AND zeitraum_bis = %s
             AND status = 'endgueltig'
           GROUP BY regelstand ORDER BY min(lauf_id) LIMIT 1""",
        (regelsatz, zeitraum.art, zeitraum.von, zeitraum.bis),
    ).fetchone()
    if z is None:
        return None
    return str(z["regelstand"]), int(str(z["wert"]))


def _hash_bestehend(
    conn: Verbindung, regelsatz: str, stand: str, art: str, von: object, bis: object
) -> str | None:
    """Hash der schon gespeicherten Zellen (gleiche Formel wie zaehlung.zaehlen)."""
    z = conn.execute(
        """
        SELECT count(*) AS n, encode(sha256(convert_to(coalesce(string_agg(
                 concat_ws('|', zeitraum_art, zeitraum_von, zeitraum_bis, region, oenace, oenace_version, geschlecht,
                           qualifikation, alter, variable, wert),
                 E'\\n' ORDER BY zeitraum_art COLLATE "C", zeitraum_von, zeitraum_bis, region COLLATE "C",
                   oenace COLLATE "C", oenace_version COLLATE "C", geschlecht COLLATE "C",
                   qualifikation COLLATE "C", alter, variable COLLATE "C"), ''), 'UTF8')), 'hex') AS hash
        FROM stat.stat_beschaeftigte
        WHERE regelsatz = %s AND regelstand = %s AND zeitraum_art = %s AND zeitraum_von = %s AND zeitraum_bis = %s
        """,
        (regelsatz, stand, art, von, bis),
    ).fetchone()
    if z is None or int(str(z["n"])) == 0:
        return None
    return str(z["hash"])


def veroeffentlichen(
    conn: Verbindung,
    lieferung: str,
    regelsatz: str,
    name: str,
    *,
    trotz_anhalten: bool = False,
    repo_pfad: Path | None = None,
) -> int:
    """Gibt das Ergebnis des letzten Laufs eines Monats mit Namen frei: vorläufig → endgültig.

    Voraussetzungen (Technische Regel 7, Fachbeschreibung § 4 Nr. 4):
    - der Monat ist noch nicht veröffentlicht,
    - der Lauf hat genau den Regelstand gerechnet, der heute gilt (Regeln und Quellzuordnung), und dieser
      Regelstand ist für die Lieferung mit Namen freigegeben,
    - keine Prüfregel hat angehalten und nichts wurde fortgeschrieben (außer ausdrücklich ``trotz_anhalten``).
    Mit ``repo_pfad`` wird die Freigabe der Lieferung über Vertrag P protokolliert (Git-Commit mit Trailer).
    Liefert die Zahl der veröffentlichten Zellen.
    """
    person = name_pruefen(name)
    stand = ergebnis.letzter_lauf(conn, lieferung, regelsatz)
    if stand is None:
        raise LaufFehler(f"Kein Lauf für {lieferung} ({regelsatz}): zuerst `lauf --lieferung {lieferung}`")
    if stand.ergebnis_status == "endgueltig":
        frueher = conn.execute(
            "SELECT freigegeben_von, freigegeben_am FROM meta.lauf WHERE id = %s", (stand.lauf_id,)
        ).fetchone()
        von = frueher["freigegeben_von"] if frueher else "?"
        am = zeit_text(frueher["freigegeben_am"]) if frueher else "?"
        raise LaufFehler(f"{lieferung} ({regelsatz}) ist bereits veröffentlicht von {von} am {am}")
    regeln = regeln_laden(conn, regelsatz, lieferung)
    offen = [r.name for r in regeln if not r.freigegeben]
    if offen:
        raise LaufFehler(
            f"{len(offen)} Regeln ohne Freigabe ({', '.join(offen[:4])} …): zuerst `regeln freigeben`"
        )
    aktuell = regelstand(conn, regeln)
    if aktuell != stand.regelstand:
        raise LaufFehler(
            f"Regelstand hat sich seit dem Lauf geändert ({stand.regelstand} → {aktuell}): "
            f"zuerst `lauf --lieferung {lieferung}` neu rechnen"
        )
    if regelstand_freigegeben(conn, regelsatz, lieferung, aktuell) is None:
        raise LaufFehler(
            f"Regelstand {aktuell} ist für {lieferung} nicht freigegeben (z. B. geänderte Quellzuordnung): "
            "zuerst `regeln freigeben`"
        )
    angehalten = conn.execute(
        """SELECT g.name FROM meta.pruefung_treffer t JOIN meta.regel g ON g.id = t.regel_id
           WHERE t.lauf_id = %s AND t.anhalten ORDER BY g.reihenfolge""",
        (stand.lauf_id,),
    ).fetchall()
    fort = conn.execute("SELECT fortgeschrieben FROM meta.lauf WHERE id = %s", (stand.lauf_id,)).fetchone()
    if fort is not None and int(str(fort["fortgeschrieben"])) > 0 and not trotz_anhalten:
        raise LaufFehler(
            f"{lieferung} enthält {fort['fortgeschrieben']} fortgeschriebene Verhältnisse (E07); bleibt vorläufig"
        )
    if angehalten and not trotz_anhalten:
        namen = ", ".join(str(z["name"]) for z in angehalten)
        raise LaufFehler(f"{lieferung} ist angehalten durch {namen}; bleibt vorläufig (Rückfrage offen)")
    if repo_pfad is not None:
        from plattform.freigabe import freigeben

        ref = f"stat.stat_beschaeftigte/{regelsatz}/{lieferung}"
        with conn.transaction():
            eintrag = conn.execute(
                """INSERT INTO meta.protokoll (uc, akteur, name, anweisung, wirkung, vorschlag_typ, ref)
                   VALUES ('uc3', 'mensch', %s, %s, %s, 'lieferung', %s) RETURNING id""",
                (
                    person,
                    f"Berichtsmonat {lieferung} ({regelsatz}) veröffentlichen",
                    f"Regelstand {aktuell}, Ergebnis-Hash {stand.ergebnis_hash[:12]}",
                    ref,
                ),
            ).fetchone()
        assert eintrag is not None
        with tupelzeilen(conn):
            freigeben(
                conn, int(str(eintrag["id"])), person, repo_pfad, objekt_typ="lieferung", objekt_ref=ref
            )
    with conn.transaction():
        cur = conn.execute(
            """UPDATE stat.stat_beschaeftigte SET status = 'endgueltig'
               WHERE regelsatz = %s AND regelstand = %s AND status = 'vorlaeufig'
                 AND zeitraum_bis BETWEEN %s AND %s""",
            (
                regelsatz,
                stand.regelstand,
                ergebnis.monatserster(lieferung),
                ergebnis.monatsletzter(lieferung),
            ),
        )
        conn.execute(
            """UPDATE meta.lauf SET ergebnis_status = 'endgueltig', freigegeben_von = %s, freigegeben_am = now()
               WHERE id = %s""",
            (person, stand.lauf_id),
        )
        return cur.rowcount
