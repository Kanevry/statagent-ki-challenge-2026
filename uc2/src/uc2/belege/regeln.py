"""Regeln für Belege und Suche aus `config/regeln.yaml`."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

import yaml

from uc2 import pfade

MODI = ("volltext", "vektor", "hybrid")
VERKNUEPFUNGEN = ("oder", "und")
FUSIONEN = ("rrf", "summe")


@dataclass(frozen=True)
class Regeln:
    stichtag_standard: date
    halbwertszeit_tage: float
    max_zeichen: int
    ueberlappung: int
    modus: str
    gewicht_vektor: float
    gewicht_volltext: float
    kandidaten: int
    volltext_verknuepfung: str
    fusion: str
    rrf_k: float
    k: int
    institutionsfaktor: float
    k_je_akteur: int = 8
    """Belege je Akteur und Runde (`belege_fuer_akteur`)."""
    rolle_genitiv: tuple[tuple[str, str], ...] = ()
    """Institutions-ID → Genitivform für die Rolle beim Personenschutz („der Ärztekammer“)."""


def _datum(wert: Any) -> date:
    if isinstance(wert, date):
        return wert
    return date.fromisoformat(str(wert))


def lade_regeln(pfad: Path | None = None) -> Regeln:
    """Liest die Regeldatei; fehlende Pflichtwerte führen zu einem KeyError mit dem Feldnamen."""
    with (pfad or pfade.CONFIG / "regeln.yaml").open(encoding="utf-8") as datei:
        roh: dict[str, Any] = yaml.safe_load(datei)
    abschnitt = roh["abschnitt"]
    suche = roh["suche"]
    modus = str(suche["modus"])
    if modus not in MODI:
        raise ValueError(f"regeln.yaml: suche.modus muss einer von {MODI} sein, nicht {modus!r}")
    verknuepfung = str(suche.get("volltext_verknuepfung", "oder"))
    if verknuepfung not in VERKNUEPFUNGEN:
        raise ValueError(
            f"regeln.yaml: suche.volltext_verknuepfung muss einer von {VERKNUEPFUNGEN} sein, "
            f"nicht {verknuepfung!r}"
        )
    fusion = str(suche.get("fusion", "rrf"))
    if fusion not in FUSIONEN:
        raise ValueError(f"regeln.yaml: suche.fusion muss einer von {FUSIONEN} sein, nicht {fusion!r}")
    genitiv: dict[str, Any] = (roh.get("personenschutz") or {}).get("rolle_genitiv") or {}
    return Regeln(
        stichtag_standard=_datum(roh["stichtag_standard"]),
        halbwertszeit_tage=float(roh["halbwertszeit_tage"]),
        max_zeichen=int(abschnitt["max_zeichen"]),
        ueberlappung=int(abschnitt["ueberlappung"]),
        modus=modus,
        gewicht_vektor=float(suche["gewicht_vektor"]),
        gewicht_volltext=float(suche["gewicht_volltext"]),
        kandidaten=int(suche["kandidaten"]),
        volltext_verknuepfung=verknuepfung,
        fusion=fusion,
        rrf_k=float(suche.get("rrf_k", 60)),
        k=int(suche["k"]),
        institutionsfaktor=float(roh["institutionsfaktor"]),
        k_je_akteur=int(suche.get("k_je_akteur", suche["k"])),
        rolle_genitiv=tuple(sorted((str(i), str(g)) for i, g in genitiv.items())),
    )
