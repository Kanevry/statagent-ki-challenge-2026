"""Belegquellen der Verhandlung: eigener Adapter vor `uc2.belege.suche` (Entscheid 9 in #44).

- `FixtureQuelle`: erfundene Belege aus `uc2/tests/fixtures/verhandlung/belege.json`. Für Tests und für
  Läufe ohne Index oder ohne Namensliste.
- `IndexQuelle`: maskierte Belege aus dem echten Index (DB `healthpolicy`, Schema `uc2`) über
  `uc2.belege.suche.belege_fuer_akteur` (#43): Institutionsfaktor, k = `suche.k_je_akteur` (8), Maskierung
  mit Mustern und Namensliste. Ohne Vektoren oder ohne Embedding-Modell fällt die Suche selbst auf Volltext
  zurück.

Maskiert gilt eine Index-Quelle nur mit geladener Namensliste (`lade_namensliste`): Muster allein erkennen
nicht jeden Personennamen. `pruefe_freigabe` lässt echte Provider nur mit einer maskierten Quelle zu.
"""

from __future__ import annotations

import functools
import json
import os
import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field, replace
from datetime import date
from pathlib import Path
from typing import Any, Protocol

import psycopg

from uc2 import pfade
from uc2.akteure.laden import Akteur
from uc2.belege.einbettung import Einbetter, einbetter
from uc2.belege.namen import (
    NAMENSLISTE_ENV,
    Namensliste,
    NamenslisteImRepo,
    pruefe_ausserhalb_repo,
    zitate_anzeige,
)
from uc2.belege.regeln import Regeln, lade_regeln
from uc2.belege.suche import ABFRAGE_SQL, belege_fuer_akteur, kurzzitat
from uc2.belege.suche import Beleg as SuchBeleg

BELEG_ID = re.compile(r"^[0-9a-f]{12}-[0-9]{3}(-[0-9]{2})?$")
FIXTURE = pfade.UC2_WURZEL / "tests" / "fixtures" / "verhandlung" / "belege.json"
RANGTEILE = (
    "rang",
    "relevanz",
    "gewicht_alter",
    "faktor_institution",
    "ts",
    "cos",
    "rang_volltext",
    "rang_vektor",
)
"""Rangteile eines Index-Belegs (`uc2.belege.suche.Beleg`), nachrechenbar mit `tests/pruefe_rang.py`."""
NAMENSLISTE_ANLEITUNG = (
    "Namensliste erzeugen: uv run uc2 namen sammeln --aus-index --autoren <datei> "
    f"--ausgabe <pfad außerhalb des Repos>, dann {NAMENSLISTE_ENV}=<pfad> setzen"
)


class BelegFehler(ValueError):
    """Belegquelle ungültig oder für diesen Provider nicht freigegeben."""


@dataclass(frozen=True)
class Beleg:
    """Ein Beleg für einen Akteurszug, gleich für Fixture und Index.

    `text_modell` ist der Text, den das Modell sieht (maskiert, Zitate bleiben); gegen ihn prüft `zitat`
    in `uc2.verhandlung.pruefungen`. `text_anzeige` hat direkte Zitate als „[Zitat]“, `zitat` ist der
    belegte Satz (höchstens 300 Zeichen), `pdf_seite` die Seite im Pressespiegel (Fixture: None).
    """

    beleg_id: str
    medium: str
    datum: date
    titel: str
    text_modell: str
    text_anzeige: str = ""
    zitat: str = ""
    pdf_seite: int | None = None
    rangteile: Mapping[str, float | int | None] = field(default_factory=dict, hash=False)
    """Leer bei Fixture-Belegen; bei Index-Belegen die Felder aus `RANGTEILE`."""

    @property
    def text(self) -> str:
        """Was das Modell gesehen hat (= `text_modell`); Bezug der Prüfung `zitat`."""
        return self.text_modell

    def chip(self) -> dict[str, Any]:
        """Inhalt des Ereignisses `belege` je Beleg: Kopf, `zitat`, `pdf_seite`, Rangteile, ohne Text.

        `text_modell` liegt bewusst nicht in PG: Beleg-ID und Index bestimmen ihn eindeutig. Die Prüfung
        `zitat` läuft vorher im Speicher und schreibt die gefundenen Wörter ins eigene Ereignis. Jede Kopie
        des Artikeltexts in `uc2.ereignis` wäre ein weiterer Ort, den der Filter (`uc2.api.belegfilter`) und
        jede Löschung abdecken müssten. Das Zitat (≤ 300 Zeichen) genügt für Chips und Anzeige.
        """
        daten: dict[str, Any] = {
            "beleg_id": self.beleg_id,
            "medium": self.medium,
            "datum": self.datum.isoformat(),
            "monat": self.datum.strftime("%Y-%m"),
            "titel": self.titel,
            "zitat": self.zitat,
            "pdf_seite": self.pdf_seite,
        }
        if self.rangteile:
            daten["rangteile"] = dict(self.rangteile)
        return daten


def aus_suchbeleg(beleg: SuchBeleg) -> Beleg:
    """Maskierten Beleg aus #43 (`uc2.belege.suche.Beleg`) in den Beleg der Verhandlung überführen."""
    return Beleg(
        beleg_id=beleg.beleg_id,
        medium=beleg.medium,
        datum=date.fromisoformat(beleg.datum),
        titel=beleg.titel,
        text_modell=beleg.text_modell,
        text_anzeige=beleg.text_anzeige,
        zitat=beleg.zitat,
        pdf_seite=beleg.pdf_seite,
        rangteile={teil: getattr(beleg, teil) for teil in RANGTEILE},
    )


class Belegquelle(Protocol):
    name: str

    @property
    def maskiert(self) -> bool:
        """True, wenn die Texte frei von Personennamen sind (erfunden oder mit Namensliste maskiert)."""
        ...

    def belege_fuer(self, akteur: Akteur, frage: str, runde: int, stichtag: date) -> list[Beleg]: ...

    def belegzahl(self, akteur: Akteur, frage: str, stichtag: date) -> int: ...


def lade_namensliste() -> Namensliste | None:
    """Die Namensliste aus `UC2_NAMENSLISTE`, wenn sie geladen werden kann, sonst None.

    Geladen heißt: Die Variable zeigt auf eine vorhandene, nicht leere Datei außerhalb jedes Git-Checkouts.
    Eine Liste im Repo ist ein Fehler (`BelegFehler`), kein stiller Rückfall: Namen gehören nie ins Repo.
    """
    wert = os.environ.get(NAMENSLISTE_ENV)
    if not wert:
        return None
    pfad = Path(wert)
    try:
        pruefe_ausserhalb_repo(pfad)
    except NamenslisteImRepo as fehler:
        raise BelegFehler(str(fehler)) from fehler
    if not pfad.is_file():
        return None
    liste = Namensliste.lade(pfad)
    return liste if len(liste) else None


def pruefe_freigabe(quelle: Belegquelle, provider: str) -> None:
    """Laufzeit-Guard: Belege ohne Namensliste-Maskierung gehen nie an ein echtes Modell."""
    if provider != "mock" and not quelle.maskiert:
        raise BelegFehler(
            f"Belegquelle {quelle.name!r} ist nicht maskiert (keine Namensliste geladen, Schutz nur mit "
            f"Mustern) und darf nicht an Provider {provider!r} gehen. {NAMENSLISTE_ANLEITUNG}; "
            "sonst --belege fixture"
        )


class FixtureQuelle:
    """Erfundene Belege je Akteur; gleiche Belege in jeder Runde, neueste zuerst.

    Die Texte sind erfunden und gelten als maskiert. `zitat` ist der belegte Satz zur Frage (wie im Index über
    `kurzzitat`), `pdf_seite` fehlt (None): Es gibt kein PDF.
    """

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
            text = str(eintrag["text"])
            beleg = Beleg(
                beleg_id=bid,
                medium=str(eintrag["medium"]),
                datum=date.fromisoformat(str(eintrag["datum"])),
                titel=str(eintrag["titel"]),
                text_modell=text,
                text_anzeige=zitate_anzeige(text),
            )
            self._belege.append((frozenset(eintrag["akteure"]), beleg))

    @property
    def maskiert(self) -> bool:
        return True

    def _alle(self, akteur: Akteur, stichtag: date) -> list[Beleg]:
        passend = [b for akteure, b in self._belege if akteur.id in akteure and b.datum <= stichtag]
        return sorted(passend, key=lambda b: (b.datum, b.beleg_id), reverse=True)

    def belege_fuer(self, akteur: Akteur, frage: str, runde: int, stichtag: date) -> list[Beleg]:
        return [
            replace(b, zitat=kurzzitat(b.text_anzeige, frage)) for b in self._alle(akteur, stichtag)[: self.k]
        ]

    def belegzahl(self, akteur: Akteur, frage: str, stichtag: date) -> int:
        return len(self._alle(akteur, stichtag))


BELEGZAHL_SQL = """
select count(distinct a.artikel_id)
from uc2.abschnitt s join uc2.artikel a using (artikel_id), {abfrage} q
where %(institution)s = any(s.institutionen) and (s.tsv @@ q or a.tsv @@ q) and a.artikeldatum <= %(stichtag)s
"""


def hat_index(verbindung: psycopg.Connection[Any]) -> bool:
    """True, wenn `uc2.abschnitt` existiert und mindestens eine Zeile hat (nur lesend)."""
    zeile = verbindung.execute("select to_regclass('uc2.abschnitt') is not null").fetchone()
    if not zeile or not zeile[0]:
        return False
    return verbindung.execute("select exists (select 1 from uc2.abschnitt)").fetchone() == (True,)


class IndexQuelle:
    """Maskierte Belege aus dem echten Index über `uc2.belege.suche.belege_fuer_akteur` (#43).

    `namen` ist die geladene Namensliste (`lade_namensliste`); nur mit ihr gilt die Quelle als `maskiert`.
    Ohne sie maskiert die Suche nur mit Mustern, das reicht nur für mock. Die Einbetter-Fabrik wird höchstens
    einmal je Quelle gebaut (das Modell lädt sonst je Akteur und Runde neu). Die Auswahl hängt nicht von der
    Runde ab (`belege_fuer_akteur`), daher holt die Quelle je Akteur, Frage und Stichtag nur einmal.
    """

    name = "index"

    def __init__(
        self,
        verbindung: psycopg.Connection[Any],
        regeln: Regeln | None = None,
        namen: Namensliste | None = None,
        einbetter_fabrik: Callable[[], Einbetter] = einbetter,
    ) -> None:
        self.verbindung = verbindung
        self.regeln = regeln or lade_regeln()
        self.namen = namen
        self.einbetter_fabrik = functools.cache(einbetter_fabrik)
        self._cache: dict[tuple[str, str, date], list[Beleg]] = {}

    @property
    def maskiert(self) -> bool:
        return self.namen is not None

    def belege_fuer(self, akteur: Akteur, frage: str, runde: int, stichtag: date) -> list[Beleg]:
        schluessel = (akteur.id, frage, stichtag)
        if schluessel not in self._cache:
            treffer = belege_fuer_akteur(
                self.verbindung,
                akteur,
                frage,
                runde,
                stichtag=stichtag,
                regeln=self.regeln,
                einbetter_fabrik=self.einbetter_fabrik,
                # Leere Liste statt None: sonst lädt die Suche `UC2_NAMENSLISTE` selbst, und `maskiert`
                # spräche nicht mehr für das, was tatsächlich maskiert wurde.
                namen=self.namen if self.namen is not None else Namensliste(),
            )
            self._cache[schluessel] = [aus_suchbeleg(b) for b in treffer]
        return list(self._cache[schluessel])

    def belegzahl(self, akteur: Akteur, frage: str, stichtag: date) -> int:
        sql = BELEGZAHL_SQL.format(abfrage=ABFRAGE_SQL[self.regeln.volltext_verknuepfung])
        zeile = self.verbindung.execute(
            sql, {"frage": frage, "institution": akteur.institution, "stichtag": stichtag}
        ).fetchone()
        return int(zeile[0]) if zeile else 0
