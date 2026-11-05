"""Gemeinsame Typen (Vertrag zwischen ingest, suche, eval und kern). Änderungen nur koordiniert."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Literal, Protocol

import psycopg

Quelle = Literal["sozdok", "formular", "katalog", "eko", "befund"]
Suchweg = Literal["volltext", "dicht", "hybrid", "auto"]
# Weg, über den ein Treffer kam; trgm ist der Rückfall über pg_trgm.
TrefferWeg = Literal["volltext", "trgm", "dicht", "hybrid"]


@dataclass(frozen=True)
class SuchFilter:
    """Einschränkung der Suche. Leere Tupel heißen: keine Einschränkung."""

    gesetze: tuple[str, ...] = ()  # abkrvo, z. B. ("BPGG", "ASVG")
    arten: tuple[str, ...] = ()  # gldart, z. B. ("PARA",)
    quellen: tuple[Quelle, ...] = ()


@dataclass(frozen=True)
class Treffer:
    """Ein gefundener Abschnitt mit allem, was ein Zitat braucht."""

    abschnitt_id: int
    dokid: str
    quelle: Quelle
    datei: str  # relativ zu UC1_DATA_DIR
    gesetz: str | None
    art: str | None
    nummer: str | None
    inkrafttreten: date | None
    seite: int | None  # PDF
    zeile: int | None  # EKO
    kontext: str  # z. B. "BPGG § 4 Pflegebedarf"
    text: str
    score: float
    weg: TrefferWeg

    def zitierschluessel(self) -> str:
        """Anzeigeform für Herkunft-Chips: Gesetz und Paragraph, sonst Datei und Seite oder Zeile."""
        if self.gesetz and self.nummer:
            # "§" nur bei Paragraphen; andere Gliederungsarten (ZIFF, ZAHL, ANL ...) bleiben als Text.
            zeichen = {"PARA": "§", "ART": "Art."}.get((self.art or "").upper(), self.art or "")
            return " ".join(teil for teil in (self.gesetz, zeichen, self.nummer) if teil)
        if self.seite is not None:
            return f"{self.datei}, S. {self.seite}"
        if self.zeile is not None:
            return f"{self.datei}, Zeile {self.zeile}"
        return self.datei


class SucheFn(Protocol):
    """Signatur von uc1.suche.suche. eval und kern hängen nur an diesem Vertrag."""

    def __call__(
        self,
        frage: str,
        *,
        k: int = 5,
        filter: SuchFilter | None = None,
        weg: Suchweg = "auto",
        conn: psycopg.Connection | None = None,
    ) -> list[Treffer]: ...
