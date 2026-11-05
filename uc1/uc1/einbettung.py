"""Embedding-Adapter für google/embeddinggemma-2 (Owner 12:5x).

Vertrag wie b-uc2 und E0 #67: `embed(texte) -> list[list[float]]` plus `MODELL_ID`. Nach dem Merge von
#67 wechselt nur der Import auf `plattform.embeddings`. Die Präfixe der Modellkarte setzt der Aufrufer als
Text (`als_anfrage`, `als_dokument`), damit `embed` ohne Zusatzparameter bleibt.

Das Modell liegt im Hugging-Face-Cache (~/.cache/huggingface), nie im Repo. Geladen wird nur der
Textteil (vision_config und audio_config None, 270 M Parameter). float16 ist laut Modellkarte verboten.
"""

from __future__ import annotations

import os
from functools import lru_cache
from typing import Any

MODELL_ID = "google/embeddinggemma-2"
VOLLE_DIMENSION = 768


def als_anfrage(frage: str) -> str:
    """Präfix für Suchanfragen laut Modellkarte (asymmetrische Suche)."""
    return f"task: search result | query: {frage}"


def als_dokument(titel: str | None, text: str) -> str:
    """Präfix für Korpus-Abschnitte laut Modellkarte; ohne Titel `title: none`."""
    return f"title: {titel.strip() if titel and titel.strip() else 'none'} | text: {text}"


def dimension() -> int:
    """Ausgabedimension. EMBED_DIM (768, 512, 256, 128) kürzt per Matryoshka; Standard 768."""
    roh = os.environ.get("EMBED_DIM", "").strip()
    dim = int(roh) if roh else VOLLE_DIMENSION
    if dim not in (768, 512, 256, 128):
        raise ValueError(f"EMBED_DIM muss 768, 512, 256 oder 128 sein, nicht {dim}")
    return dim


def _geraet() -> str:
    gewuenscht = os.environ.get("EMBED_DEVICE", "").strip()
    if gewuenscht:
        return gewuenscht
    import torch

    if torch.backends.mps.is_available():
        return "mps"
    if torch.cuda.is_available():
        return "cuda"
    return "cpu"


@lru_cache(maxsize=1)
def _modell() -> Any:
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer(
        MODELL_ID,
        device=_geraet(),
        config_kwargs={"vision_config": None, "audio_config": None},
        model_kwargs={"torch_dtype": "float32"},
    )


def embed(texte: list[str], *, batch_size: int = 32) -> list[list[float]]:
    """Bettet Texte ein, L2-normalisiert, in `dimension()` Dimensionen. Gleiche Texte, gleiche Vektoren."""
    if not texte:
        return []
    vektoren = _modell().encode(
        texte,
        batch_size=batch_size,
        normalize_embeddings=True,
        truncate_dim=dimension(),
        convert_to_numpy=True,
        show_progress_bar=False,
    )
    return [[float(x) for x in zeile] for zeile in vektoren]
