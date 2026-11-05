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
from typing import Any

from statagent import ergebnis
from statagent.bereinigung import bereinigen
from statagent.db import Verbindung, lieferungen
from statagent.regeln import Regel, RegelFehler, name_pruefen, regeln_laden, regelstand
from statagent.revision import revision_berechnen
from statagent.zaehlung import zaehlen


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
            mehrfach_abschnitte = zl.aktive_abschnitte - zl.gezaehlt
            nicht_gezaehlt = zl.nicht_aktiv + mehrfach_abschnitte
            if b.abschnitte != zl.aktive_abschnitte + zl.nicht_aktiv:
                raise RegelFehler("Abschnitte aus der Bereinigung ≠ aktive + nicht aktive Abschnitte")
            if b.gelesen != zl.gezaehlt + nicht_gezaehlt + b.ausgeschlossen:
                raise RegelFehler(
                    "Abrechnung geht nicht auf: gelesen ≠ gezählt + nicht gezählt + ausgeschlossen"
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
                    conn.execute(
                        """INSERT INTO meta.revision (lauf_id, berichtsmonat, gliederung, schluessel,
                             veroeffentlicht, aktuell, status_vorher) VALUES (%s, %s, 'insgesamt', 'AT', %s, %s,
                             'endgueltig')""",
                        (lauf_id, lieferung, v_wert, zl.gezaehlt),
                    )
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
            meldung = "; ".join(meldung_teile)
            conn.execute(
                """UPDATE meta.lauf SET beendet_am = now(), status = %s, ergebnis_status = %s, gelesen = %s,
                     gezaehlt = %s, nicht_gezaehlt = %s, ausgeschlossen = %s, korrigiert = %s, ergebnis_hash = %s,
                     zellen = %s, meldung = %s, regelstand = %s
                   WHERE id = %s""",
                (
                    lauf_status,
                    ergebnis_status,
                    b.gelesen,
                    zl.gezaehlt,
                    nicht_gezaehlt,
                    b.ausgeschlossen,
                    b.korrigiert,
                    hash_ergebnis,
                    zl.zellen,
                    meldung,
                    stand_ergebnis,
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
        gelesen=b.gelesen,
        gezaehlt=zl.gezaehlt,
        nicht_gezaehlt=nicht_gezaehlt,
        ausgeschlossen=b.ausgeschlossen,
        korrigiert=b.korrigiert,
        ergebnis_hash=hash_ergebnis,
        zellen=zl.zellen,
        meldung=meldung,
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
) -> int:
    """Gibt das Ergebnis des letzten Laufs eines Monats mit Namen frei: vorläufig → endgültig.

    Voraussetzungen: alle für die Lieferung geltenden Regeln sind freigegeben, und keine Prüfregel hat den
    Monat angehalten (außer ausdrücklich `trotz_anhalten`). Liefert die Zahl der veröffentlichten Zellen.
    """
    person = name_pruefen(name)
    stand = ergebnis.letzter_lauf(conn, lieferung, regelsatz)
    if stand is None:
        raise LaufFehler(f"Kein Lauf für {lieferung} ({regelsatz}): zuerst `lauf --lieferung {lieferung}`")
    offen = [r.name for r in regeln_laden(conn, regelsatz, lieferung) if not r.freigegeben]
    if offen:
        raise LaufFehler(
            f"{len(offen)} Regeln ohne Freigabe ({', '.join(offen[:4])} …): zuerst `regeln freigeben`"
        )
    angehalten = conn.execute(
        """SELECT g.name FROM meta.pruefung_treffer t JOIN meta.regel g ON g.id = t.regel_id
           WHERE t.lauf_id = %s AND t.anhalten ORDER BY g.reihenfolge""",
        (stand.lauf_id,),
    ).fetchall()
    if angehalten and not trotz_anhalten:
        namen = ", ".join(str(z["name"]) for z in angehalten)
        raise LaufFehler(f"{lieferung} ist angehalten durch {namen}; bleibt vorläufig (Rückfrage offen)")
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
