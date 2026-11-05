"""Monatsbetrieb: ein Lauf verarbeitet genau eine Lieferung (Fachbeschreibung § 2a).

Ablauf: Vorprüfung (Lieferung vorhanden, Vormonat gelaufen) → Regeln laden und Regelstand bilden →
Bereinigung → Zählung → Prüfungen (falls vorhanden) → Ergebnis schreiben oder als unverändert erkennen.
Der Lauf braucht kein Sprachmodell und importiert keines (Technische Regeln 1 und 2).
"""

from __future__ import annotations

import importlib
from dataclasses import asdict, dataclass
from typing import Any

from statagent import ergebnis
from statagent.bereinigung import bereinigen
from statagent.db import Verbindung, lieferungen
from statagent.regeln import Regel, RegelFehler, regeln_laden, regelstand
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
    try:
        modul = importlib.import_module("statagent.pruefungen")
    except ModuleNotFoundError:
        return []
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
            nicht_gezaehlt = b.abschnitte - zl.gezaehlt
            if b.gelesen != zl.gezaehlt + nicht_gezaehlt + b.ausgeschlossen:
                raise RegelFehler(
                    "Abrechnung geht nicht auf: gelesen ≠ gezählt + nicht gezählt + ausgeschlossen"
                )

            for regel_id, saetze in sorted(b.wirkung.items()):
                conn.execute(
                    "INSERT INTO meta.regel_wirkung (lauf_id, regel_id, saetze) VALUES (%s, %s, %s)",
                    (lauf_id, regel_id, saetze),
                )
            zaehl_regeln = [r for r in regeln if r.typ == "zaehl"]
            for r in zaehl_regeln:
                conn.execute(
                    "INSERT INTO meta.regel_wirkung (lauf_id, regel_id, saetze) VALUES (%s, %s, %s)",
                    (lauf_id, r.id, zl.gezaehlt),
                )

            anhalten = _pruefungen_ausfuehren(conn, lauf_id, lieferung, regelsatz, regeln)
            ergebnis_status = "endgueltig" if alle_frei and not anhalten else "vorlaeufig"

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
            if "endgueltig" in status_vorher:
                if hash_vorher != zl.ergebnis_hash:
                    raise LaufFehler(
                        "Veröffentlichter Monat würde sich ändern (gleicher Regelstand, anderes Ergebnis). "
                        "Das darf nicht passieren; Abweichungen gehören als Revisionsbedarf in den Bericht."
                    )
                lauf_status = "unveraendert"
                ergebnis_status = "endgueltig"
                meldung_teile.append("bereits veröffentlicht, Ergebnis identisch")
            elif status_vorher and hash_vorher == zl.ergebnis_hash and ergebnis_status == "vorlaeufig":
                lauf_status = "unveraendert"
                meldung_teile.append("Ergebnis identisch mit vorigem Lauf")
            else:
                if status_vorher:
                    conn.execute(
                        """DELETE FROM stat.stat_beschaeftigte
                           WHERE regelsatz = %s AND regelstand = %s AND zeitraum_art = %s
                             AND zeitraum_von = %s AND zeitraum_bis = %s AND status <> 'endgueltig'""",
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
                     zellen = %s, meldung = %s
                   WHERE id = %s""",
                (
                    lauf_status,
                    ergebnis_status,
                    b.gelesen,
                    zl.gezaehlt,
                    nicht_gezaehlt,
                    b.ausgeschlossen,
                    b.korrigiert,
                    zl.ergebnis_hash,
                    zl.zellen,
                    meldung,
                    lauf_id,
                ),
            )
    except Exception as fehler:
        with conn.transaction():
            conn.execute(
                "UPDATE meta.lauf SET beendet_am = now(), status = 'abgebrochen', meldung = %s WHERE id = %s",
                (f"{type(fehler).__name__}: {fehler}", lauf_id),
            )
        raise

    return LaufErgebnis(
        lauf_id=lauf_id,
        lieferung=lieferung,
        regelsatz=regelsatz,
        regelstand=stand,
        status=lauf_status,
        ergebnis_status=ergebnis_status,
        gelesen=b.gelesen,
        gezaehlt=zl.gezaehlt,
        nicht_gezaehlt=nicht_gezaehlt,
        ausgeschlossen=b.ausgeschlossen,
        korrigiert=b.korrigiert,
        ergebnis_hash=zl.ergebnis_hash,
        zellen=zl.zellen,
        meldung=meldung,
    )


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
