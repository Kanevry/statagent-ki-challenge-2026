"""Revisionsbedarf: Vormonate aus der eigenen Lieferung nachrechnen, Differenz in Ursachen zerlegen."""

from __future__ import annotations

from statagent.db import Verbindung
from statagent.lauf import lauf_ausfuehren


def _zahl(conn: Verbindung, sql: bytes, *parameter: object) -> int:
    z = conn.execute(sql, parameter).fetchone()
    assert z is not None
    return int(str(z["n"]))


def test_revision_zerlegt_die_differenz_vollstaendig(conn: Verbindung) -> None:
    # Fängt: Revisionsbedarf, der veröffentlichte Werte falsch übernimmt, oder Ursachen, die sich nicht zur
    # Differenz aufaddieren (Nachmeldungen − rückwirkende Abmeldungen − nicht mehr enthaltene = Differenz).
    for monat in ("2024-08", "2024-09", "2024-10"):
        erg = lauf_ausfuehren(conn, monat, "v1")
    lauf_id = erg.lauf_id
    monate = conn.execute(
        b"SELECT DISTINCT berichtsmonat FROM meta.revision WHERE lauf_id = %s ORDER BY 1", (lauf_id,)
    ).fetchall()
    assert [m["berichtsmonat"] for m in monate] == ["2024-08", "2024-09"]
    for m in monate:
        monat = m["berichtsmonat"]
        zeile = conn.execute(
            b"""SELECT veroeffentlicht, aktuell, differenz FROM meta.revision
                WHERE lauf_id = %s AND berichtsmonat = %s AND gliederung = 'insgesamt'""",
            (lauf_id, monat),
        ).fetchone()
        assert zeile is not None
        veroeffentlicht = _zahl(
            conn,
            b"""SELECT gezaehlt AS n FROM meta.lauf WHERE lieferung = %s AND status IN ('fertig', 'unveraendert')
                ORDER BY id DESC LIMIT 1""",
            monat,
        )
        assert zeile["veroeffentlicht"] == veroeffentlicht
        ursache = {
            str(u["ursache"]): int(str(u["anzahl"]))
            for u in conn.execute(
                b"SELECT ursache, anzahl FROM meta.revision_ursache WHERE lauf_id = %s AND berichtsmonat = %s",
                (lauf_id, monat),
            ).fetchall()
        }
        assert set(ursache) == {
            "nachmeldung",
            "rueckwirkende_abmeldung",
            "nicht_mehr_enthalten",
            "merkmal_geaendert",
        }
        assert zeile["differenz"] == (
            ursache["nachmeldung"] - ursache["rueckwirkende_abmeldung"] - ursache["nicht_mehr_enthalten"]
        )
        # Je Gliederung summiert sich der Revisionsbedarf auf Insgesamt.
        for gliederung in ("region", "geschlecht", "qualifikation"):
            summe = _zahl(
                conn,
                b"""SELECT coalesce(sum(aktuell), 0) AS n FROM meta.revision
                    WHERE lauf_id = %s AND berichtsmonat = %s AND gliederung = %s""",
                lauf_id,
                monat,
                gliederung,
            )
            assert summe == zeile["aktuell"]
