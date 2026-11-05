"""Stufe 2: `abschnitte.jsonl` → `vektoren.npy` (float32, n×dim) und `vektoren.json` (Herkunft)."""

from __future__ import annotations

import hashlib
import json
import socket
import time
from pathlib import Path
from typing import Any

import numpy as np

from uc2.belege.einbettung import Einbetter, dokument_text
from uc2.belege.extraktion import lies_jsonl


def ids_hash(abschnitt_ids: list[str]) -> str:
    return hashlib.sha256("\n".join(abschnitt_ids).encode("utf-8")).hexdigest()


def datei_hash(pfad: Path) -> str:
    return hashlib.sha256(pfad.read_bytes()).hexdigest()


def bette_extrakt_ein(
    extrakt: Path, einbetter: Einbetter, batch: int = 32, grenze: int | None = None
) -> dict[str, Any]:
    """Bettet alle (oder die ersten `grenze`) Abschnitte ein; Reihenfolge = `abschnitte.jsonl`."""
    titel = {a["artikel_id"]: a["titel"] for a in lies_jsonl(extrakt / "artikel.jsonl")}
    abschnitte = lies_jsonl(extrakt / "abschnitte.jsonl")
    if grenze is not None:
        abschnitte = abschnitte[:grenze]
    texte = [dokument_text(titel.get(a["artikel_id"]), a["text"]) for a in abschnitte]
    beginn = time.monotonic()
    zeilen: list[list[float]] = []
    for i in range(0, len(texte), batch):
        zeilen.extend(einbetter.einbetten(texte[i : i + batch], "dokument"))
    dauer = time.monotonic() - beginn
    dim = einbetter.dimension()
    matrix = np.asarray(zeilen, dtype=np.float32).reshape(len(texte), dim)
    npy = extrakt / "vektoren.npy"
    np.save(npy, matrix)
    meta: dict[str, Any] = {
        "modell_id": einbetter.modell_id,
        "revision": getattr(einbetter, "revision", None),
        "dim": dim,
        "anzahl": len(texte),
        "abschnitt_ids_sha256": ids_hash([a["abschnitt_id"] for a in abschnitte]),
        "npy_sha256": datei_hash(npy),
        "dauer_s": round(dauer, 3),
        "texte_pro_s": round(len(texte) / dauer, 2) if dauer > 0 else None,
        "host": socket.gethostname(),
        "geraet": getattr(einbetter, "geraet", None),
    }
    (extrakt / "vektoren.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return meta
