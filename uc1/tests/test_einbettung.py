"""Einbettungs-Adapter gegen das echte Modell (AC aus #67). Ohne Modell im HF-Cache: übersprungen."""

from __future__ import annotations

import math

import pytest

from uc1.einbettung import MODELL_ID, dimension, embed

pytestmark = pytest.mark.modell


def _modell_im_cache() -> bool:
    try:
        from huggingface_hub import try_to_load_from_cache
    except ImportError:
        return False
    return isinstance(try_to_load_from_cache(MODELL_ID, "model.safetensors"), str)


@pytest.fixture(autouse=True)
def _braucht_modell() -> None:
    pytest.importorskip("sentence_transformers", reason="Extra `embed` nicht installiert")
    if not _modell_im_cache():
        pytest.skip(f"{MODELL_ID} liegt nicht im Hugging-Face-Cache")


def _cosinus(a: list[float], b: list[float]) -> float:
    return sum(x * y for x, y in zip(a, b, strict=True)) / (math.hypot(*a) * math.hypot(*b))


def test_gleiche_texte_gleiche_vektoren_in_dimension() -> None:
    erster, zweiter = embed(["a", "a"])
    assert len(erster) == dimension()
    assert erster == pytest.approx(zweiter, abs=1e-6)


def test_paraphrase_naeher_als_fremdes_thema() -> None:
    anker, paraphrase, fremd = embed(["Pflegegeld beantragen", "Antrag auf Pflegegeld", "ÖNACE Abschnitt C"])
    assert _cosinus(anker, paraphrase) > _cosinus(anker, fremd)
