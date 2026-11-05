"""Annahmen F1 bis F10 als Daten (meta.annahme) und ihre Auswahl je Monat."""

from __future__ import annotations

from statagent.berichte.annahmen import annahmen
from statagent.db import Verbindung
from statagent.lauf import lauf_ausfuehren


def test_alle_zehn_annahmen_mit_satz_und_begruendung(conn: Verbindung) -> None:
    # Fängt: eine Annahme fehlt im Seed, leerer Satz, Gedankenstrich im Satz, Rückfrage-Nummer ohne Rückfrage,
    # Grund fehlt oder ist mehr als ein Satz, F9 behauptet wieder eine ungemessene Größe („rund 8.000“).
    zeilen = conn.execute("SELECT nr, rueckfrage, satz, begruendung, grund FROM meta.annahme").fetchall()
    assert sorted(str(z["nr"]) for z in zeilen) == sorted(f"F{i}" for i in range(1, 11))
    rueckfragen = {str(r["nr"]) for r in conn.execute("SELECT nr FROM meta.rueckfrage").fetchall()}
    for z in zeilen:
        assert str(z["satz"]).strip() and str(z["begruendung"]).strip()
        assert "—" not in str(z["satz"]) and " – " not in str(z["satz"])
        assert z["rueckfrage"] is None or z["rueckfrage"] in rueckfragen
        grund = str(z["grund"] or "")
        assert grund.endswith(".") and grund.count(". ") == 0 and "—" not in grund, z["nr"]
    f9 = next(str(z["satz"]) for z in zeilen if z["nr"] == "F9")
    assert "8.000" not in f9 and "nicht gemessen" in f9


def test_auswahl_je_monat_wirkung_und_beleg(conn: Verbindung) -> None:
    # Fängt: monatsgebundene Annahmen (F2 nur März 2025) in jedem Monat, falsche Reihenfolge (F10 vor F2),
    # Beleg der Rückfrage oder Regelwirkung des maßgeblichen Laufs nicht übernommen.
    maerz = [a["nr"] for a in annahmen(conn, "2025-03")]
    assert maerz == ["F2", "F4", "F5", "F7", "F8", "F10"]
    assert "F2" not in [a["nr"] for a in annahmen(conn, "2025-04")]

    lauf = lauf_ausfuehren(conn, "2024-08", "v1")
    liste = {a["nr"]: a for a in annahmen(conn, "2024-08")}
    assert "F9" in liste and "F1" not in liste
    f7 = liste["F7"]
    beleg = conn.execute("SELECT beleg_sql FROM meta.rueckfrage WHERE nr = 'R1'").fetchone()
    assert beleg is not None and f7["beleg_sql"] == beleg["beleg_sql"]
    wirkung = conn.execute(
        """SELECT sum(w.saetze) AS n FROM meta.regel_wirkung w JOIN meta.regel r ON r.id = w.regel_id
           WHERE w.lauf_id = %s AND r.name = 'R5_alter'""",
        (lauf.lauf_id,),
    ).fetchone()
    erwartet = None if wirkung is None or wirkung["n"] is None else int(str(wirkung["n"]))
    assert f7["wirkung_saetze"] == erwartet
    assert liste["F5"]["beleg_sql"] is None


def test_satz_endet_mit_grund(conn: Verbindung) -> None:
    # Fängt: der Qualitätsbericht und `uc3 annahmen` zeigen nur `satz`; ohne angehängten Grund stünde dort
    # keine Begründung (0 Treffer „Grund:“ in den 24 Berichten).
    for a in annahmen(conn, "2024-08"):
        assert a["grund"] and str(a["satz"]).endswith(f" Grund: {a['grund']}"), a["nr"]
