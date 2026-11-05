"""Belegquellen der Verhandlung: eigener Adapter vor `uc2.belege.suche` (Entscheid 9 in #44).

- `FixtureQuelle`: erfundene Belege aus `uc2/tests/fixtures/verhandlung/belege.json`. Für Tests und für jeden
  Lauf mit echtem Modell, solange die Maskierung aus #43 fehlt.
- `IndexQuelle`: Belegsuche im echten Index (DB `healthpolicy`, Schema `uc2`). Vor #43 nur mit mock: die
  Texte enthalten ungeschützte Personennamen. `pruefe_freigabe` verweigert sie mit echtem Provider, solange
  keine Maskierung eingehängt ist.
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import date
from pathlib import Path
from typing import Any, Protocol

import psycopg

from uc2 import pfade
from uc2.akteure.laden import Akteur
from uc2.belege.regeln import Regeln, lade_regeln
from uc2.belege.suche import ABFRAGE_SQL, suche

BELEG_ID = re.compile(r"^[0-9a-f]{12}-[0-9]{3}(-[0-9]{2})?$")
FIXTURE = pfade.UC2_WURZEL / "tests" / "fixtures" / "verhandlung" / "belege.json"


class BelegFehler(ValueError):
    """Belegquelle ungültig oder für diesen Provider nicht freigegeben."""


@dataclass(frozen=True)
class Beleg:
    beleg_id: str
    medium: str
    datum: date
    titel: str
    text: str

    def chip(self) -> dict[str, str]:
        """Anzeige ohne Text: Beleg-ID, Medium, Monat, Titel."""
        return {
            "beleg_id": self.beleg_id,
            "medium": self.medium,
            "monat": self.datum.strftime("%Y-%m"),
            "titel": self.titel,
        }


class Belegquelle(Protocol):
    name: str

    @property
    def maskiert(self) -> bool:
        """True, wenn die Texte frei von Personennamen sind (erfunden oder maskiert)."""
        ...

    def belege_fuer(self, akteur: Akteur, frage: str, runde: int, stichtag: date) -> list[Beleg]: ...

    def belegzahl(self, akteur: Akteur, frage: str, stichtag: date) -> int: ...


def pruefe_freigabe(quelle: Belegquelle, provider: str) -> None:
    """Laufzeit-Guard: ungeschützte Belege gehen nie an ein echtes Modell."""
    if provider != "mock" and not quelle.maskiert:
        raise BelegFehler(
            f"Belegquelle {quelle.name!r} ist nicht maskiert und darf nicht an Provider {provider!r} gehen "
            "(vor #43 nur mit mock; für echte Modelle --belege fixture)"
        )


class FixtureQuelle:
    """Erfundene Belege je Akteur; gleiche Belege in jeder Runde, neueste zuerst."""

    name = "fixture"

    def __init__(self, pfad: Path | None = None, k: int | None = None) -> None:
        self.pfad = pfad or FIXTURE
        self.k = k or lade_regeln().k
        roh = json.loads(self.pfad.read_text(encoding="utf-8"))
        self._belege: list[tuple[frozenset[str], Beleg]] = []
        for eintrag in roh["belege"]:
            bid = str(eintrag["beleg_id"])
            if not BELEG_ID.fullmatch(bid):
                raise BelegFehler(f"{self.pfad.name}: Beleg-ID {bid!r} passt nicht zum Muster")
            beleg = Beleg(
                beleg_id=bid,
                medium=str(eintrag["medium"]),
                datum=date.fromisoformat(str(eintrag["datum"])),
                titel=str(eintrag["titel"]),
                text=str(eintrag["text"]),
            )
            self._belege.append((frozenset(eintrag["akteure"]), beleg))

    @property
    def maskiert(self) -> bool:
        return True

    def _alle(self, akteur: Akteur, stichtag: date) -> list[Beleg]:
        passend = [b for akteure, b in self._belege if akteur.id in akteure and b.datum <= stichtag]
        return sorted(passend, key=lambda b: (b.datum, b.beleg_id), reverse=True)

    def belege_fuer(self, akteur: Akteur, frage: str, runde: int, stichtag: date) -> list[Beleg]:
        return self._alle(akteur, stichtag)[: self.k]

    def belegzahl(self, akteur: Akteur, frage: str, stichtag: date) -> int:
        return len(self._alle(akteur, stichtag))


BELEGZAHL_SQL = """
select count(distinct a.artikel_id)
from uc2.abschnitt s join uc2.artikel a using (artikel_id), {abfrage} q
where %(institution)s = any(s.institutionen) and (s.tsv @@ q or a.tsv @@ q) and a.artikeldatum <= %(stichtag)s
"""


class IndexQuelle:
    """Belege aus dem echten Index über `uc2.belege.suche.suche` (Volltext, ohne Embedding-Modell).

    VOR #43 NUR MIT MOCK: Die Abschnitte enthalten ungeschützte Personennamen. `maskierung` ist der
    Einhängepunkt für #43 (Text → maskierter Text); erst mit ihr gilt die Quelle als `maskiert`.
    Je Akteur zählen nur Abschnitte, die seine Institution nennen (`uc2.abschnitt.institutionen`).
    """

    name = "index"

    def __init__(
        self,
        verbindung: psycopg.Connection[Any],
        regeln: Regeln | None = None,
        maskierung: Callable[[str], str] | None = None,
    ) -> None:
        self.verbindung = verbindung
        self.regeln = regeln or lade_regeln()
        self.maskierung = maskierung

    @property
    def maskiert(self) -> bool:
        return self.maskierung is not None

    def belege_fuer(self, akteur: Akteur, frage: str, runde: int, stichtag: date) -> list[Beleg]:
        _, treffer = suche(
            self.verbindung,
            f"{frage} {akteur.name}",
            self.regeln,
            modus="volltext",
            k=self.regeln.kandidaten,
            stichtag=stichtag,
        )
        ids = [t.abschnitt_id for t in treffer]
        eigene = {
            str(z[0])
            for z in self.verbindung.execute(
                "select abschnitt_id from uc2.abschnitt "
                "where abschnitt_id = any(%s) and %s = any(institutionen)",
                (ids, akteur.id),
            )
        }
        belege = [
            Beleg(
                beleg_id=t.abschnitt_id,
                medium=t.medium,
                datum=date.fromisoformat(t.artikeldatum),
                titel=t.titel,
                text=t.ausschnitt,
            )
            for t in treffer
            if t.abschnitt_id in eigene
        ][: self.regeln.k]
        if self.maskierung is not None:
            m = self.maskierung
            belege = [replace(b, titel=m(b.titel), text=m(b.text)) for b in belege]
        return belege

    def belegzahl(self, akteur: Akteur, frage: str, stichtag: date) -> int:
        sql = BELEGZAHL_SQL.format(abfrage=ABFRAGE_SQL[self.regeln.volltext_verknuepfung])
        zeile = self.verbindung.execute(
            sql, {"frage": frage, "institution": akteur.id, "stichtag": stichtag}
        ).fetchone()
        return int(zeile[0]) if zeile else 0
