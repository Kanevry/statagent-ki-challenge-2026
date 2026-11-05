"""Regel E07: Fortschreibung bei belegtem Lieferausfall (Rückfragen R4, R5)."""

from __future__ import annotations

import pytest

from statagent.db import Verbindung
from statagent.lauf import LaufFehler, lauf_ausfuehren, veroeffentlichen
from statagent.regeln import regeln_freigeben


def _ohne_mindestbasis(conn: Verbindung) -> None:
    # Die Fixture ist winzig; im Betrieb greift E07 erst ab 1.000 Verhältnissen im Vormonat.
    conn.execute(
        b"""UPDATE meta.regel SET parameter = parameter || '{"mindestens_basis": 0}'::jsonb
            WHERE regelsatz = 'v1' AND name = 'E07_fortschreibung_lieferausfall'"""
    )


def test_fortschreibung_ergaenzt_markiert_und_haelt_vorlaeufig(conn: Verbindung) -> None:
    # Fängt: Fortschreibung, die Sätze doppelt zählt oder die Abrechnung sprengt, unmarkierte ergänzte Abschnitte,
    # eine Veröffentlichung trotz Schätzung, und Prüfungen, die den Ausfall wegen der Ergänzung nicht mehr sehen.
    _ohne_mindestbasis(conn)
    lauf_ausfuehren(conn, "2024-08", "v1")
    erg = lauf_ausfuehren(conn, "2024-09", "v1")
    assert erg.fortgeschrieben > 0
    assert erg.gelesen + erg.fortgeschrieben == erg.gezaehlt + erg.nicht_gezaehlt + erg.ausgeschlossen
    assert erg.ergebnis_status == "vorlaeufig" and "fortgeschrieben" in erg.meldung
    markiert = conn.execute(
        b"""SELECT count(*) AS n FROM bereinigt.abschnitt WHERE lieferung = '2024-09' AND regelsatz = 'v1'
              AND herkunft = 'fortgeschrieben' AND 'E07_fortschreibung_lieferausfall' = ANY(korrekturen)"""
    ).fetchone()
    assert markiert is not None and markiert["n"] == erg.fortgeschrieben
    doppelt = conn.execute(
        b"""SELECT count(*) AS n FROM bereinigt.abschnitt f WHERE f.lieferung = '2024-09' AND f.regelsatz = 'v1'
              AND f.herkunft = 'fortgeschrieben' AND EXISTS (
                SELECT 1 FROM bereinigt.abschnitt g WHERE g.lieferung = '2024-09' AND g.regelsatz = 'v1'
                  AND g.herkunft = 'geliefert' AND g.vvh_id = f.vvh_id)"""
    ).fetchone()
    assert doppelt is not None and doppelt["n"] == 0
    p16 = conn.execute(
        b"""SELECT t.anzahl FROM meta.pruefung_treffer t JOIN meta.regel g ON g.id = t.regel_id
            WHERE t.lauf_id = %s AND g.name = 'P16_verhaeltnisse_verschwunden'""",
        (erg.lauf_id,),
    ).fetchone()
    assert p16 is not None and p16["anzahl"] > 0  # der Ausfall bleibt sichtbar
    regeln_freigeben(conn, "v1", "Lena Gruber")
    with pytest.raises(LaufFehler, match="fortgeschrieben|angehalten"):
        veroeffentlichen(conn, "2024-09", "v1", "Lena Gruber")


def test_fortgeschriebenes_wird_nicht_weitergetragen(conn: Verbindung) -> None:
    # Fängt: eine Schätzung, die aus einer geschätzten Vorlieferung weitergeschätzt wird (nur Beobachtetes zählt).
    _ohne_mindestbasis(conn)
    for monat in ("2024-08", "2024-09", "2024-10"):
        lauf_ausfuehren(conn, monat, "v1")
    weiter = conn.execute(
        b"""SELECT count(*) AS n FROM bereinigt.abschnitt WHERE lieferung = '2024-10' AND regelsatz = 'v1'
              AND herkunft = 'fortgeschrieben' AND vvh_id IN (
                SELECT vvh_id FROM bereinigt.abschnitt WHERE lieferung = '2024-09' AND regelsatz = 'v1'
                  AND herkunft = 'fortgeschrieben')"""
    ).fetchone()
    assert weiter is not None and weiter["n"] == 0
