"""Such-Prototyp: Volltext (PG), Vektor (numpy-Kosinus) oder Hybrid, gewichtet nach Alter zum Stichtag.

Kandidaten sind die Vereinigung der besten `kandidaten` nach Volltext und nach Kosinus. Relevanz:
volltext = ts_norm (`ts_rank_cd(Abschnitt || Titel, …, 32)`, liegt in [0, 1)), vektor = max(cos, 0),
hybrid (fusion rrf) = gewicht_volltext/(rrf_k + rang_volltext) + gewicht_vektor/(rrf_k + rang_vektor),
Ränge je Verfahren über Artikel (bester Abschnitt) in dessen Kandidatenliste; fehlt ein Rang, entfällt
der Summand. hybrid (fusion summe) = gewicht_vektor · max(cos, 0) + gewicht_volltext · ts_norm.
Endrang = Relevanz · 0,5^(Alter/Halbwertszeit).
Artikel nach dem Stichtag sind ausgeschlossen; je Artikel zählt nur der beste Abschnitt.
"""

from __future__ import annotations

import sys
from collections.abc import Callable
from dataclasses import asdict, dataclass
from datetime import date
from typing import Any

import numpy as np
import psycopg

from uc2.belege.einbettung import Einbetter, abfrage_text
from uc2.belege.regeln import Regeln

AUSSCHNITT_ZEICHEN = 200


@dataclass(frozen=True)
class Kandidat:
    abschnitt_id: str
    artikel_id: str
    artikeldatum: date
    medium: str
    titel: str
    text: str
    ts: float
    cos: float
    in_volltext: bool = False
    """Steht in der Volltext-Kandidatenliste."""
    in_vektor: bool = False
    """Steht in der Vektor-Kandidatenliste."""


@dataclass(frozen=True)
class Treffer:
    abschnitt_id: str
    artikel_id: str
    relevanz: float
    cos: float
    ts: float
    gewicht_alter: float
    rang: float
    artikeldatum: str
    medium: str
    titel: str
    ausschnitt: str
    rang_volltext: int | None = None
    rang_vektor: int | None = None

    def als_dict(self) -> dict[str, Any]:
        return asdict(self)


def gewicht_alter(artikeldatum: date, stichtag: date, halbwertszeit_tage: float) -> float:
    return float(0.5 ** ((stichtag - artikeldatum).days / halbwertszeit_tage))


def relevanz(modus: str, cos: float, ts: float, regeln: Regeln) -> float:
    if modus == "volltext":
        return ts
    if modus == "vektor":
        return max(cos, 0.0)
    return regeln.gewicht_vektor * max(cos, 0.0) + regeln.gewicht_volltext * ts


def _treffer(kand: Kandidat, rel: float, stichtag: date, regeln: Regeln, **raenge: int | None) -> Treffer:
    gewicht = gewicht_alter(kand.artikeldatum, stichtag, regeln.halbwertszeit_tage)
    return Treffer(
        abschnitt_id=kand.abschnitt_id,
        artikel_id=kand.artikel_id,
        relevanz=rel,
        cos=kand.cos,
        ts=kand.ts,
        gewicht_alter=gewicht,
        rang=rel * gewicht,
        artikeldatum=kand.artikeldatum.isoformat(),
        medium=kand.medium,
        titel=kand.titel,
        ausschnitt=" ".join(kand.text.split())[:AUSSCHNITT_ZEICHEN],
        **raenge,
    )


def _artikelraenge(kandidaten: list[Kandidat], wert: str) -> tuple[dict[str, int], dict[str, Kandidat]]:
    """Bester Abschnitt je Artikel nach `wert` (ts oder cos) und Artikelrang 1, 2, …; Gleichstand nach ID."""
    bester: dict[str, Kandidat] = {}
    for kand in sorted(kandidaten, key=lambda c: (-getattr(c, wert), c.abschnitt_id)):
        bester.setdefault(kand.artikel_id, kand)
    reihe = sorted(bester.values(), key=lambda c: (-getattr(c, wert), c.artikel_id))
    return {c.artikel_id: n for n, c in enumerate(reihe, start=1)}, bester


def bewerte_rrf(kandidaten: list[Kandidat], stichtag: date, regeln: Regeln, k: int) -> list[Treffer]:
    """Gewichtete RRF über Artikelränge, dann Altersgewicht; Gleichstand nach artikel_id."""
    gueltig = [c for c in kandidaten if c.artikeldatum <= stichtag]
    rang_t, bester_t = _artikelraenge([c for c in gueltig if c.in_volltext], "ts")
    rang_v, bester_v = _artikelraenge([c for c in gueltig if c.in_vektor], "cos")
    treffer: list[Treffer] = []
    for artikel_id in sorted(set(rang_t) | set(rang_v)):
        rel = 0.0
        if artikel_id in rang_t:
            rel += regeln.gewicht_volltext / (regeln.rrf_k + rang_t[artikel_id])
        if artikel_id in rang_v:
            rel += regeln.gewicht_vektor / (regeln.rrf_k + rang_v[artikel_id])
        kand = bester_t.get(artikel_id) or bester_v[artikel_id]
        treffer.append(
            _treffer(
                kand,
                rel,
                stichtag,
                regeln,
                rang_volltext=rang_t.get(artikel_id),
                rang_vektor=rang_v.get(artikel_id),
            )
        )
    reihe = sorted(treffer, key=lambda t: (-t.rang, t.artikel_id))
    return [t for t in reihe if t.rang > 0][:k]


def bewerte(kandidaten: list[Kandidat], modus: str, stichtag: date, regeln: Regeln, k: int) -> list[Treffer]:
    """Endrang je Kandidat, bester Abschnitt je Artikel, Top k; Gleichstand nach abschnitt_id.

    Hybrid mit `fusion: rrf` geht an `bewerte_rrf`.
    """
    if modus == "hybrid" and regeln.fusion == "rrf":
        return bewerte_rrf(kandidaten, stichtag, regeln, k)
    bester: dict[str, Treffer] = {}
    for kand in sorted(kandidaten, key=lambda c: c.abschnitt_id):
        if kand.artikeldatum > stichtag:
            continue
        treffer = _treffer(kand, relevanz(modus, kand.cos, kand.ts, regeln), stichtag, regeln)
        alt = bester.get(kand.artikel_id)
        if alt is None or treffer.rang > alt.rang:
            bester[kand.artikel_id] = treffer
    reihe = sorted(bester.values(), key=lambda t: (-t.rang, t.abschnitt_id))
    return [t for t in reihe if t.rang > 0][:k]


# Abfrage je Verknüpfung als feste SQL-Bausteine; die Frage geht nur als Parameter hinein.
# `oder`: Lexeme aus plainto_tsquery (gequotet, gestemmt) mit `|` statt `&` verknüpft.
ABFRAGE_SQL = {
    # to_tsquery('simple', …) übernimmt die schon gestemmten Lexeme unverändert (Funktion statt Cast,
    # weil der Baustein in FROM steht).
    "oder": "to_tsquery('simple', replace(plainto_tsquery('german', %(frage)s)::text, '&', '|'))",
    "und": "websearch_to_tsquery('german', %(frage)s)",
}

VOLLTEXT_SQL = """
select s.abschnitt_id
from uc2.abschnitt s join uc2.artikel a using (artikel_id),
     {abfrage} q
where (s.tsv @@ q or a.tsv @@ q) and a.artikeldatum <= %(stichtag)s
order by ts_rank_cd(s.tsv || a.tsv, q, 32) desc, s.abschnitt_id
limit %(n)s
"""

DETAIL_SQL = """
select s.abschnitt_id, s.artikel_id, a.artikeldatum, a.medium, a.titel, s.text,
       case when (s.tsv || a.tsv) @@ q then ts_rank_cd(s.tsv || a.tsv, q, 32) else 0 end
from uc2.abschnitt s join uc2.artikel a using (artikel_id),
     {abfrage} q
where s.abschnitt_id = any(%(ids)s)
"""


def vektor_stand(verbindung: psycopg.Connection[Any]) -> tuple[int, list[str]]:
    zeilen = verbindung.execute(
        "select count(*), coalesce(array_agg(distinct modell) filter (where modell is not null), '{}') "
        "from uc2.abschnitt where vektor is not null"
    ).fetchone()
    assert zeilen is not None
    return int(zeilen[0]), list(zeilen[1])


def _lies_vektoren(
    zeilen: list[tuple[Any, ...]], dimension: int
) -> tuple[list[str], np.ndarray[Any, Any]] | str:
    """IDs und Matrix aus (abschnitt_id, vektor, dim); bei Verstoß der Grund als Text, nie still weiter.

    Geprüft: Spalte `dim` = Dimension des Einbetters, Bytelänge = dim × 4 (float32), alle Werte endlich.
    """
    falsche_dim = sum(1 for z in zeilen if z[2] != dimension)
    if falsche_dim:
        return f"{falsche_dim} Vektoren mit dim ≠ {dimension} (Dimension des Einbetters)"
    falsche_laenge = sum(1 for z in zeilen if len(bytes(z[1])) != dimension * 4)
    if falsche_laenge:
        return f"{falsche_laenge} Vektoren mit Bytelänge ≠ {dimension * 4}"
    matrix = np.vstack([np.frombuffer(bytes(z[1]), dtype="<f4") for z in zeilen]).astype(np.float64)
    nicht_endlich = int((~np.isfinite(matrix).all(axis=1)).sum())
    if nicht_endlich:
        return f"{nicht_endlich} Vektoren mit NaN/Inf"
    return [str(z[0]) for z in zeilen], matrix


def suche(
    verbindung: psycopg.Connection[Any],
    frage: str,
    regeln: Regeln,
    modus: str | None = None,
    k: int | None = None,
    stichtag: date | None = None,
    einbetter: Einbetter | None = None,
    einbetter_fabrik: Callable[[], Einbetter] | None = None,
) -> tuple[str, list[Treffer]]:
    """Gibt den tatsächlich genutzten Modus und die Treffer zurück (Rückfall auf volltext wird gemeldet).

    `einbetter_fabrik` wird nur aufgerufen, wenn der Index Vektoren hat und kein `einbetter` übergeben ist;
    fehlt dafür das Extra `einbettung` (ImportError, etwa torch), fällt die Suche auf volltext zurück.
    """
    modus = modus or regeln.modus
    k = k or regeln.k
    stichtag = stichtag or regeln.stichtag_standard
    n = regeln.kandidaten
    ts_abfrage = ABFRAGE_SQL[regeln.volltext_verknuepfung]

    cos_je_id: dict[str, float] = {}
    vektor_ids: list[str] = []
    if modus in ("vektor", "hybrid"):
        anzahl, modelle = vektor_stand(verbindung)
        grund = None
        if anzahl == 0:
            grund = "Index ohne Vektoren"
        elif einbetter is None and einbetter_fabrik is not None:
            try:
                einbetter = einbetter_fabrik()
            except ImportError as fehler:
                fehlt = fehler.name or str(fehler)
                grund = f"Einbetter nicht ladbar, {fehlt} fehlt (Extra `einbettung` installieren)"
        if grund is None and einbetter is None:
            grund = "kein Einbetter"
        elif grund is None and einbetter is not None and modelle != [einbetter.modell_id]:
            grund = f"Vektoren im Index von {modelle}, Abfrage mit {einbetter.modell_id}"
        if grund is None and einbetter is not None:
            zeilen = verbindung.execute(
                "select s.abschnitt_id, s.vektor, s.dim from uc2.abschnitt s join uc2.artikel a "
                "using (artikel_id) where s.vektor is not null and a.artikeldatum <= %s "
                "order by s.abschnitt_id",
                (stichtag,),
            ).fetchall()
            if zeilen:
                dimension = einbetter.dimension()
                gelesen = _lies_vektoren(zeilen, dimension)
                abfrage = np.empty(0)
                if not isinstance(gelesen, str):
                    abfrage = np.asarray(
                        einbetter.einbetten([abfrage_text(frage)], "abfrage")[0], dtype=np.float64
                    )
                if isinstance(gelesen, str):
                    grund = gelesen
                elif abfrage.shape != (dimension,) or not np.isfinite(abfrage).all():
                    grund = f"Abfragevektor mit Form {abfrage.shape} oder NaN/Inf"
                else:
                    ids, matrix = gelesen
                    normen = np.linalg.norm(matrix, axis=1) * np.linalg.norm(abfrage)
                    cos = (matrix @ abfrage) / np.where(normen == 0, 1.0, normen)
                    beste = np.argsort(-cos, kind="stable")[:n]
                    cos_je_id = {ids[i]: float(cos[i]) for i in range(len(ids))}
                    vektor_ids = [ids[i] for i in beste]
        if grund is not None:
            print(f"Hinweis: Modus {modus} nicht möglich ({grund}), Rückfall auf volltext.", file=sys.stderr)
            modus = "volltext"

    volltext_ids: list[str] = []
    if modus in ("volltext", "hybrid"):
        volltext_ids = [
            str(z[0])
            for z in verbindung.execute(
                VOLLTEXT_SQL.format(abfrage=ts_abfrage), {"frage": frage, "stichtag": stichtag, "n": n}
            )
        ]
    volltext_menge, vektor_menge = set(volltext_ids), set(vektor_ids)
    kandidaten_ids = sorted(volltext_menge | vektor_menge)
    if not kandidaten_ids:
        return modus, []
    kandidaten = [
        Kandidat(
            abschnitt_id=str(z[0]),
            artikel_id=str(z[1]),
            artikeldatum=z[2],
            medium=str(z[3]),
            titel=str(z[4]),
            text=str(z[5]),
            ts=float(z[6]),
            cos=cos_je_id.get(str(z[0]), 0.0),
            in_volltext=str(z[0]) in volltext_menge,
            in_vektor=str(z[0]) in vektor_menge,
        )
        for z in verbindung.execute(
            DETAIL_SQL.format(abfrage=ts_abfrage), {"frage": frage, "ids": kandidaten_ids}
        )
    ]
    return modus, bewerte(kandidaten, modus, stichtag, regeln, k)
