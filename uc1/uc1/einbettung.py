"""Embedding-Adapter für google/embeddinggemma-2 (Owner 12:5x).

Vertrag wie b-uc2 und E0 #67: `embed(texte) -> list[list[float]]` plus `MODELL_ID`. Nach dem Merge von
#67 wechselt nur der Import auf `plattform.embeddings`. Die Präfixe der Modellkarte setzt der Aufrufer als
Text (`als_anfrage`, `als_dokument`), damit `embed` ohne Zusatzparameter bleibt.

Das Modell liegt im Hugging-Face-Cache (~/.cache/huggingface), nie im Repo. Geladen wird nur der
Textteil (vision_config und audio_config None, 270 M Parameter). float16 ist laut Modellkarte verboten.

Messung und Begründung der Interna: docs/plan/uc1/messung-embeddings.md.
"""

from __future__ import annotations

import os
from functools import lru_cache
from typing import Any
from unittest import mock

MODELL_ID = "google/embeddinggemma-2"
VOLLE_DIMENSION = 768
# Token-Deckel je Text. Das Modell kann 8K, aber 8192 Tokens mit batch 32 belegten auf Rechner A (MPS) über
# 14 GB Treiberspeicher und brachten den Rechner ins Swappen (#29). 512 Tokens decken laut Messung den
# Großteil der Abschnitte ab; EMBED_MAX_TOKENS überschreibt den Wert für Vergleichsläufe.
STANDARD_MAX_TOKENS = 512
_ERLAUBTE_DTYPES = ("float32", "bfloat16")


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


def _dtype_name() -> str:
    """EMBED_DTYPE (float32 oder bfloat16), Standard float32. float16 liefert laut Modellkarte NaN."""
    roh = os.environ.get("EMBED_DTYPE", "").strip() or "float32"
    if roh not in _ERLAUBTE_DTYPES:
        raise ValueError(f"EMBED_DTYPE muss float32 oder bfloat16 sein, nicht {roh}")
    return roh


def max_tokens() -> int:
    """Token-Deckel je Text (EMBED_MAX_TOKENS, Standard 512, höchstens 8192); längere Texte werden gekürzt."""
    roh = os.environ.get("EMBED_MAX_TOKENS", "").strip()
    wert = int(roh) if roh else STANDARD_MAX_TOKENS
    if not 1 <= wert <= 8192:
        raise ValueError(f"EMBED_MAX_TOKENS muss zwischen 1 und 8192 liegen, nicht {wert}")
    return wert


def _lade(local_files_only: bool) -> Any:
    import sentence_transformers.base.modules.transformer as st_transformer
    import torch
    from sentence_transformers import SentenceTransformer
    from transformers import AutoTokenizer

    # Das Repo bringt einen multimodalen EmbeddingGemma2Processor mit; dessen Bild- und Video-Teil
    # verlangt Pillow und torchvision, obwohl wir nur Text einbetten. Für den reinen Textpfad genügt
    # der Tokenizer, deshalb lädt das Transformer-Modul ihn hier statt AutoProcessor.
    with mock.patch.object(st_transformer, "AutoProcessor", AutoTokenizer):
        modell = SentenceTransformer(
            MODELL_ID,
            device=_geraet(),
            local_files_only=local_files_only,
            config_kwargs={"vision_config": None, "audio_config": None},
            model_kwargs={"dtype": getattr(torch, _dtype_name())},
        )
    modell.max_seq_length = max_tokens()
    return modell


@lru_cache(maxsize=1)
def _modell() -> Any:
    # Erst nur aus dem Cache laden (offline, ohne Hub-Anfragen); nur wenn das Modell fehlt, herunterladen.
    try:
        return _lade(local_files_only=True)
    except OSError:
        return _lade(local_files_only=False)


def embed(texte: list[str], *, batch_size: int = 8) -> list[list[float]]:
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
