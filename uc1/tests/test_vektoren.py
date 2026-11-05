"""Tests für uc1.vektoren, ohne Modell. Der Import-Test braucht die lokale DB und nutzt ein eigenes Schema."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import numpy as np
import psycopg
import pytest

from uc1 import vektoren as v
from uc1.config import datenbank_url


def _einheitsmatrix(zeilen: int, seed: int = 7) -> v.Matrix:
    roh = np.random.default_rng(seed).normal(size=(zeilen, 768))
    return (roh / np.linalg.norm(roh, axis=1, keepdims=True)).astype(np.float32)


def test_256_entsteht_aus_768_durch_kuerzen_und_normieren() -> None:
    """Fängt eine Ableitung, die nicht die ersten 256 Werte nimmt oder das Normieren vergisst."""
    m = _einheitsmatrix(5)
    k = v.kuerze(m, 256)
    assert k.shape == (5, 256) and k.dtype == np.float32
    np.testing.assert_allclose(np.linalg.norm(k, axis=1), 1.0, rtol=1e-6)
    erwartet = m[:, :256] / np.linalg.norm(m[:, :256], axis=1, keepdims=True)
    np.testing.assert_allclose(k, erwartet, rtol=1e-6)


def test_export_entfernt_duplikate_und_sortiert_nach_hash() -> None:
    """Fängt einen Export, der doppelte Hashes zweimal einbettet oder in DB-Reihenfolge schreibt."""
    zeilen = [("c", "BPGG § 4", "Text C"), ("a", "", "Text A"), ("c", "BPGG § 4", "Text C"), ("b", "K", "B")]
    assert v.eindeutig_sortiert(zeilen) == [
        ("a", "title: none | text: Text A"),
        ("b", "title: K | text: B"),
        ("c", "title: BPGG § 4 | text: Text C"),
    ]


def test_berechnen_nimmt_teilstuecke_wieder_auf(tmp_path: Path) -> None:
    """Fängt einen Lauf, der nach Abbruch alles neu rechnet oder die Zeilen nicht in Hash-Reihenfolge
    zurücksortiert (gerechnet wird nach Länge)."""
    paare = [(f"h{i:02d}", "x" * (20 - i)) for i in range(10)]
    aufrufe: list[int] = []

    def einbetten(texte: list[str]) -> list[list[float]]:
        aufrufe.append(len(texte))
        if len(aufrufe) == 3:
            raise RuntimeError("Abbruch")
        # Vektor kodiert die Textlänge, damit die Zuordnung zum Hash prüfbar ist.
        return [[float(len(t))] + [0.0] * 767 for t in texte]

    prefix = tmp_path / "idx"
    with pytest.raises(RuntimeError):
        v.berechne(paare, prefix, einbetten, teilgroesse=3, log=lambda _: None)
    aufrufe.clear()
    werte = v.berechne(paare, prefix, einbetten, teilgroesse=3, log=lambda _: None)
    assert werte["uebernommen"] == 6 and werte["gerechnet"] == 4
    assert aufrufe == [3, 1]
    hashes, matrix = v.lies_vektoren(prefix)
    assert hashes == [h for h, _ in paare]
    assert matrix[:, 0].tolist() == [float(len(e)) for _, e in paare]


@pytest.fixture
def test_conn() -> Iterator[psycopg.Connection]:
    try:
        conn = psycopg.connect(datenbank_url(), connect_timeout=3)
    except psycopg.OperationalError:
        pytest.skip("DB lotse nicht erreichbar")
    conn.execute("DROP SCHEMA IF EXISTS lotse_test_vektoren CASCADE")
    conn.execute("CREATE SCHEMA lotse_test_vektoren")
    conn.execute("CREATE TABLE lotse_test_vektoren.vektor (LIKE lotse.vektor INCLUDING ALL)")
    conn.commit()
    try:
        yield conn
    finally:
        conn.rollback()
        conn.execute("DROP SCHEMA lotse_test_vektoren CASCADE")
        conn.commit()
        conn.close()


def test_zweiter_import_verdoppelt_nicht(test_conn: psycopg.Connection) -> None:
    """Fängt einen Import, der beim zweiten Lauf Zeilen anhängt statt je modell/dim neu zu laden."""
    hashes = ["a", "b", "c"]
    m = _einheitsmatrix(3)
    for _ in range(2):
        v.schreibe(test_conn, hashes, m, [768, 256], modell="test", tabelle="lotse_test_vektoren.vektor")
    zeilen = test_conn.execute(
        "SELECT dim, count(*) FROM lotse_test_vektoren.vektor GROUP BY dim ORDER BY dim"
    ).fetchall()
    assert zeilen == [(256, 3), (768, 3)]
    gelesen = test_conn.execute(
        "SELECT v FROM lotse_test_vektoren.vektor WHERE text_hash = 'b' AND dim = 256"
    ).fetchone()
    assert gelesen is not None
    np.testing.assert_allclose(np.asarray(gelesen[0], dtype=np.float32), v.kuerze(m, 256)[1], rtol=1e-6)
