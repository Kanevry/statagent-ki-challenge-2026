"""Eichung nur auf dem geltenden Regelstand (Review !13 Runde 2 Punkt 14 / Runde 3 NIEDRIG)."""

from __future__ import annotations

import pytest

from statagent.db import Verbindung
from statagent.eichung import eichen
from statagent.regeln import RegelFehler


def test_eichen_verweigert_lauf_mit_altem_regelstand(conn: Verbindung) -> None:
    # Fängt: eichen vergleicht Zahlen eines Laufs, dessen Regelstand seit dem Lauf geändert wurde, und meldet
    # „stimmt“ für Regeln, die so nicht mehr gelten.
    lauf = pytest.importorskip("statagent.lauf")
    lauf.lauf_ausfuehren(conn, "2024-08", regelsatz="v1", gestartet_von=None)
    with conn.transaction():
        conn.execute(
            """UPDATE meta.regel SET parameter = jsonb_set(parameter, '{max_plausibel}', '111')
               WHERE regelsatz = 'v1' AND name = 'R5_alter'"""
        )
    with pytest.raises(RegelFehler, match="neu rechnen"):
        eichen(conn, "2024-08")
