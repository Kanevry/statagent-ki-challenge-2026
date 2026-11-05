"""plattform.embeddings mit dem echten Modell (#67). Ohne das Extra (CI) werden diese Tests übersprungen."""

import json
import math
import os
import re
import subprocess
import sys

import pytest

pytest.importorskip(
    "sentence_transformers",
    reason="Extra plattform[embeddings] fehlt (CI); lokal: uv sync --all-packages --all-extras",
)

from plattform import embeddings  # noqa: E402


@pytest.fixture
def protokoll(tmp_path, monkeypatch):
    datei = tmp_path / "modellaufrufe.jsonl"
    monkeypatch.setenv("PLATTFORM_PROTOKOLL", str(datei))
    return datei


def _cosinus(a: list[float], b: list[float]) -> float:
    skalar = math.fsum(x * y for x, y in zip(a, b, strict=True))
    return skalar / math.sqrt(math.fsum(x * x for x in a) * math.fsum(y * y for y in b))


def test_gleiche_texte_gleiche_vektoren_der_laenge_dimension(protokoll):
    """Fängt: Vektor hängt von der Position im Stapel ab, Länge passt nicht zu ``dimension()``."""
    erster, zweiter = embeddings.einbetten(["a", "a"], zweck="test")

    assert erster == zweiter
    assert len(erster) == embeddings.dimension()


def test_ranking_naher_text_vor_fremdem(protokoll):
    """Fängt: falsches Modell oder kaputtes Pooling (deutsche Paraphrase nicht näher als Fremdes)."""
    anfrage, nah, fern = embeddings.einbetten(
        ["Pflegegeld beantragen", "Antrag auf Pflegegeld", "ÖNACE Abschnitt C"], zweck="test"
    )

    assert _cosinus(anfrage, nah) > _cosinus(anfrage, fern)


def test_protokoll_genau_eine_zeile_ohne_text(protokoll):
    """Fängt: fehlende oder doppelte Zeile je Aufruf, Text im Protokoll, Revision fehlt oder „main“."""
    texte = ["Protokollprobe-7c2e", "Zweitprobe-41ab"]
    embeddings.einbetten(texte, zweck="test.protokoll")

    zeilen = protokoll.read_text(encoding="utf-8").splitlines()
    assert len(zeilen) == 1
    assert not any(text in zeilen[0] for text in texte)
    eintrag = json.loads(zeilen[0])
    assert (eintrag["provider"], eintrag["zweck"], eintrag["anzahl_texte"]) == ("lokal", "test.protokoll", 2)
    assert eintrag["modell"] == embeddings.modellname()
    assert re.fullmatch(r"[0-9a-f]{40}", eintrag["version"])
    assert eintrag["prompt_hash"] == embeddings.texte_hash(texte)


def test_offline_aus_dem_cache(protokoll, tmp_path):
    """Fängt: Laden fragt trotz gefülltem Cache den Hub und scheitert ohne Netz."""
    embeddings.einbetten(["einmal laden"], zweck="test")  # füllt den Cache, falls er leer war
    code = (
        "from plattform.embeddings import dimension, einbetten\n"
        "print(len(einbetten(['ohne Netz'], zweck='test')[0]) == dimension())\n"
    )
    umgebung = {**os.environ, "HF_HUB_OFFLINE": "1", "PLATTFORM_PROTOKOLL": str(tmp_path / "offline.jsonl")}

    lauf = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, timeout=300, env=umgebung
    )

    assert lauf.returncode == 0, lauf.stderr[-2000:]
    assert lauf.stdout.strip().splitlines()[-1] == "True"
