"""plattform.embeddings ohne das Extra (CI-Fall) und Prüfungen vor dem Laden; laufen auch in CI."""

import os
import subprocess
import sys

import psycopg
import pytest
from plattform import embeddings


def test_import_ohne_sentence_transformers_und_klarer_fehler(tmp_path):
    """Fängt: sentence-transformers oder torch auf Modulebene importiert (CI bricht), unklarer Fehler."""
    code = (
        "import sys\n"
        "sys.modules['sentence_transformers'] = None  # wie in CI: Paket fehlt\n"
        "import plattform.embeddings as e\n"
        "assert 'torch' not in sys.modules, 'torch beim Import geladen'\n"
        "try:\n"
        "    e.einbetten(['x'], zweck='test')\n"
        "except e.EmbeddingsFehlen as fehler:\n"
        "    print(fehler)\n"
    )
    umgebung = {**os.environ, "PLATTFORM_PROTOKOLL": str(tmp_path / "p.jsonl")}

    lauf = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, timeout=120, env=umgebung
    )

    assert lauf.returncode == 0, lauf.stderr[-2000:]
    assert "uv sync --all-packages --all-extras" in lauf.stdout


def test_medien_platzhalter_abgelehnt(tmp_path, monkeypatch):
    """Fängt: ``<|image|>`` ohne Bild ginge still falsch eingebettet ins Modell (im Prototyp kein Fehler)."""
    monkeypatch.setenv("PLATTFORM_PROTOKOLL", str(tmp_path / "p.jsonl"))

    with pytest.raises(ValueError, match="Platzhalter"):
        embeddings.einbetten(["Formular <|image|> Seite 2"], zweck="test")


def test_pgvector_verfuegbar_liefert_bool():
    """Fängt: falsche Katalogabfrage (Fehler statt Antwort) oder Zeile statt bool."""
    url = os.environ.get("PLATTFORM_TEST_DATABASE_URL")
    if not url:
        pytest.skip("PLATTFORM_TEST_DATABASE_URL nicht gesetzt: DB-Test braucht eine Wegwerf-DB")
    with psycopg.connect(url, autocommit=True) as conn:
        assert isinstance(embeddings.pgvector_verfuegbar(conn), bool)
