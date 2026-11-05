"""Veröffentlichung ist an den freigegebenen Regelstand gebunden; Veröffentlichtes bleibt unverändert (Review !13)."""

from __future__ import annotations

import psycopg
import pytest

from statagent.db import Verbindung
from statagent.lauf import LaufFehler, lauf_ausfuehren, veroeffentlichen
from statagent.regeln import regeln_freigeben

NAME = "Lena Gruber"


def _neue_zuordnung(conn: Verbindung) -> None:
    """Ändert die Quellzuordnung (nicht freigegeben): ÖNACE 'D' wird wie die Unterabschnitte 'C'."""
    conn.execute(
        b"""UPDATE stat.quellzuordnung SET code = 'C'
            WHERE regelsatz = 'v1' AND merkmal = 'oenace' AND version = '2008' AND geliefert = 'D'"""
    )


def test_veroeffentlichen_verlangt_den_freigegebenen_regelstand(conn: Verbindung) -> None:
    # Fängt: eine Zuordnung oder Regel, die nach der Freigabe geändert wurde, macht ungeprüfte Zahlen endgültig.
    lauf_ausfuehren(conn, "2024-08", "v1")
    regeln_freigeben(conn, "v1", NAME)
    _neue_zuordnung(conn)
    with pytest.raises(LaufFehler, match="Regelstand hat sich seit dem Lauf geändert"):
        veroeffentlichen(conn, "2024-08", "v1", NAME)
    lauf_ausfuehren(conn, "2024-08", "v1")  # neu gerechnet, aber der neue Stand ist nicht freigegeben
    with pytest.raises(LaufFehler, match="nicht freigegeben"):
        veroeffentlichen(conn, "2024-08", "v1", NAME)
    regeln_freigeben(conn, "v1", NAME)  # hält den neuen Regelstand fest
    assert veroeffentlichen(conn, "2024-08", "v1", NAME) > 0


def test_zweite_veroeffentlichung_bricht_ab(conn: Verbindung) -> None:
    # Fängt: ein erneutes Veröffentlichen überschreibt Name und Zeitpunkt der ersten Freigabe.
    lauf_ausfuehren(conn, "2024-08", "v1")
    regeln_freigeben(conn, "v1", NAME)
    veroeffentlichen(conn, "2024-08", "v1", NAME)
    with pytest.raises(LaufFehler, match="bereits veröffentlicht von Lena Gruber"):
        veroeffentlichen(conn, "2024-08", "v1", "Erika Huber")


def test_lauf_nach_regelwechsel_zeigt_veroeffentlichte_kennzahlen(conn: Verbindung) -> None:
    # Fängt: meta.lauf mischt Kennzahlen des neuen Stands mit Hash und Status des veröffentlichten; die Abweichung
    # gehört nur in meta.revision.
    erster = lauf_ausfuehren(conn, "2024-08", "v1")
    regeln_freigeben(conn, "v1", NAME)
    veroeffentlichen(conn, "2024-08", "v1", NAME)
    _neue_zuordnung(conn)
    zweiter = lauf_ausfuehren(conn, "2024-08", "v1")
    assert zweiter.status == "unveraendert" and zweiter.ergebnis_status == "endgueltig"
    assert (zweiter.gezaehlt, zweiter.zellen, zweiter.ergebnis_hash, zweiter.regelstand) == (
        erster.gezaehlt,
        erster.zellen,
        erster.ergebnis_hash,
        erster.regelstand,
    )
    zeilen = conn.execute(
        b"""SELECT gliederung, schluessel, veroeffentlicht, aktuell FROM meta.revision
            WHERE lauf_id = %s AND berichtsmonat = '2024-08' AND gliederung = 'oenace' AND differenz <> 0
            ORDER BY schluessel""",
        (zweiter.lauf_id,),
    ).fetchall()
    assert [z["schluessel"] for z in zeilen] == ["C", "D"]  # D wandert nach C, insgesamt gleich
    endgueltig = conn.execute(
        b"SELECT count(DISTINCT regelstand) AS n FROM stat.stat_beschaeftigte WHERE status = 'endgueltig'"
    ).fetchone()
    assert endgueltig is not None and endgueltig["n"] == 1


def test_freigegebene_regel_aendert_sich_nur_mit_neuer_freigabe(conn: Verbindung) -> None:
    # Fängt: stille Änderung einer freigegebenen Regel (UPDATE ohne neue Freigabe).
    regeln_freigeben(conn, "v1", NAME)
    with pytest.raises(psycopg.errors.RaiseException, match="nur mit neuer Freigabe"):
        conn.execute(
            b"""UPDATE meta.regel SET parameter = parameter || '{"max_plausibel": 74}'::jsonb
                WHERE regelsatz = 'v1' AND name = 'R5_alter'"""
        )
