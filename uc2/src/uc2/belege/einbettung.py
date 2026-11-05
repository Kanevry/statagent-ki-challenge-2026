"""Einbettung von Texten (Schnittstelle nach E0 #67).

`einbetten` bekommt fertige Strings; die Präfixe von EmbeddingGemma setzt uc2 über `dokument_text` und
`abfrage_text`. torch und sentence-transformers werden erst in `GemmaEinbetter` importiert, damit der Kern
ohne das Extra `einbettung` läuft (Tests und CI nutzen `MockEinbetter`).
"""

from __future__ import annotations

import hashlib
import importlib
import logging
import os
import sys
import time
from collections.abc import Callable
from typing import Any, Protocol

import numpy as np

log = logging.getLogger(__name__)

GEMMA_MODELL = "google/embeddinggemma-2"
GEMMA_REVISION = "f9972ac22e696a105c482202646979e33e4b5a1e"
GEMMA_GROESSE = "ca. 1,2 GB Gewichte (float32)"
"""Erwartete Ladegröße für die Logzeile; Schätzung, nicht gemessen."""
MAX_TOKEN = 1024
"""Längere Eingaben schneidet das Modell ab; ein Abschnitt hat höchstens ca. 1.500 Zeichen."""
MOCK_DIMENSION = 768


class Einbetter(Protocol):
    modell_id: str

    def einbetten(self, texte: list[str], zweck: str) -> list[list[float]]: ...

    def dimension(self) -> int: ...


def dokument_text(titel: str | None, text: str) -> str:
    return f"title: {titel or 'none'} | text: {text}"


def abfrage_text(frage: str) -> str:
    return f"task: search result | query: {frage}"


def _protokoll(modell_id: str, zweck: str, anzahl: int, beginn: float) -> None:
    """Eine Zeile je Aufruf, ohne Inhalt."""
    log.info(
        "einbetten zweck=%s anzahl=%d dauer_s=%.3f modell=%s",
        zweck,
        anzahl,
        time.monotonic() - beginn,
        modell_id,
    )


class MockEinbetter:
    """Deterministische Vektoren aus dem sha256 des Texts, normalisiert; für Tests und CI."""

    modell_id = "mock-sha256-768"
    revision: str | None = None
    geraet = "keins"

    def dimension(self) -> int:
        return MOCK_DIMENSION

    def einbetten(self, texte: list[str], zweck: str) -> list[list[float]]:
        beginn = time.monotonic()
        vektoren: list[list[float]] = []
        for text in texte:
            saat = int.from_bytes(hashlib.sha256(text.encode("utf-8")).digest()[:8], "big")
            v = np.random.default_rng(saat).standard_normal(MOCK_DIMENSION)
            vektoren.append((v / np.linalg.norm(v)).astype(np.float32).tolist())
        _protokoll(self.modell_id, zweck, len(texte), beginn)
        return vektoren


def _geraet() -> str:
    gewaehlt = os.environ.get("UC2_GERAET")
    if gewaehlt:
        return gewaehlt
    import torch

    return "mps" if torch.backends.mps.is_available() else "cpu"


class GemmaEinbetter:
    """EmbeddingGemma 2 über sentence-transformers, immer float32 (float16 liefert falsche Vektoren)."""

    modell_id = GEMMA_MODELL
    revision: str | None = GEMMA_REVISION

    def __init__(self, batch_size: int = 32) -> None:
        import torch
        from sentence_transformers import SentenceTransformer

        self.batch_size = batch_size
        self.geraet = _geraet()
        print(
            f"Lade Einbettungsmodell {GEMMA_MODELL} @ {GEMMA_REVISION} ({GEMMA_GROESSE}) auf {self.geraet}",
            file=sys.stderr,
        )
        self._modell: Any = SentenceTransformer(
            GEMMA_MODELL,
            revision=GEMMA_REVISION,
            device=self.geraet,
            model_kwargs={"torch_dtype": torch.float32},
            config_kwargs={"vision_config": None, "audio_config": None},
        )
        self._modell.max_seq_length = MAX_TOKEN

    def dimension(self) -> int:
        # sentence-transformers ≥ 6.2 heißt es get_embedding_dimension; der alte Name warnt nur noch.
        abfrage = (
            getattr(self._modell, "get_embedding_dimension", None)
            or self._modell.get_sentence_embedding_dimension
        )
        return int(abfrage())

    def einbetten(self, texte: list[str], zweck: str) -> list[list[float]]:
        beginn = time.monotonic()
        matrix = self._modell.encode(
            texte, normalize_embeddings=True, batch_size=self.batch_size, convert_to_numpy=True
        )
        _protokoll(self.modell_id, zweck, len(texte), beginn)
        ergebnis: list[list[float]] = np.asarray(matrix, dtype=np.float32).tolist()
        return ergebnis


class PlattformEinbetter:
    """Hülle um `plattform.embeddings` (E0), sobald es das Modul gibt."""

    revision: str | None = None
    geraet = "plattform"

    def __init__(
        self,
        einbetten: Callable[[list[str], str], list[list[float]]],
        dimension: Callable[[], int],
        modell_id: str,
    ) -> None:
        self._einbetten = einbetten
        self._dimension = dimension
        self.modell_id = modell_id

    def dimension(self) -> int:
        return self._dimension()

    def einbetten(self, texte: list[str], zweck: str) -> list[list[float]]:
        beginn = time.monotonic()
        ergebnis = self._einbetten(texte, zweck)
        _protokoll(self.modell_id, zweck, len(texte), beginn)
        return ergebnis


def einbetter(batch_size: int = 32) -> Einbetter:
    """Fabrik nach `UC2_EINBETTUNG=gemma|mock` (Standard gemma); bevorzugt `plattform.embeddings`."""
    art = os.environ.get("UC2_EINBETTUNG", "gemma")
    if art == "mock":
        return MockEinbetter()
    if art != "gemma":
        raise ValueError(f"UC2_EINBETTUNG muss gemma oder mock sein, nicht {art!r}")
    try:
        plattform = importlib.import_module("plattform.embeddings")
    except ImportError:
        return GemmaEinbetter(batch_size=batch_size)
    return PlattformEinbetter(
        plattform.einbetten, plattform.dimension, str(getattr(plattform, "MODELL_ID", GEMMA_MODELL))
    )
