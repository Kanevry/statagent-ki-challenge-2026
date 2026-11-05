"""Such-Prototyp: Volltext (PG), Vektor (numpy-Kosinus) oder Hybrid, gewichtet nach Alter zum Stichtag.

Kandidaten sind die Vereinigung der besten `kandidaten` nach Volltext und nach Kosinus. Relevanz:
volltext = ts_norm (`ts_rank_cd(Abschnitt || Titel, …, 32)`, liegt in [0, 1)), vektor = max(cos, 0),
hybrid = gewicht_vektor · max(cos, 0) + gewicht_volltext · ts_norm.
Endrang = Relevanz · 0,5^(Alter/Halbwertszeit).
Artikel nach dem Stichtag sind ausgeschlossen; je Artikel zählt nur der beste Abschnitt.
"""

from __future__ import annotations

import sys
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


def bewerte(kandidaten: list[Kandidat], modus: str, stichtag: date, regeln: Regeln, k: int) -> list[Treffer]:
    """Endrang je Kandidat, bester Abschnitt je Artikel, Top k; Gleichstand nach abschnitt_id."""
    bester: dict[str, Treffer] = {}
    for kand in sorted(kandidaten, key=lambda c: c.abschnitt_id):
        if kand.artikeldatum > stichtag:
            continue
        rel = relevanz(modus, kand.cos, kand.ts, regeln)
        gewicht = gewicht_alter(kand.artikeldatum, stichtag, regeln.halbwertszeit_tage)
        treffer = Treffer(
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
        )
        alt = bester.get(kand.artikel_id)
        if alt is None or treffer.rang > alt.rang:
            bester[kand.artikel_id] = treffer
    reihe = sorted(bester.values(), key=lambda t: (-t.rang, t.abschnitt_id))
    return [t for t in reihe if t.rang > 0][:k]


VOLLTEXT_SQL = """
select s.abschnitt_id
from uc2.abschnitt s join uc2.artikel a using (artikel_id),
     websearch_to_tsquery('german', %(frage)s) q
where (s.tsv @@ q or a.tsv @@ q) and a.artikeldatum <= %(stichtag)s
order by ts_rank_cd(s.tsv || a.tsv, q, 32) desc, s.abschnitt_id
limit %(n)s
"""

DETAIL_SQL = """
select s.abschnitt_id, s.artikel_id, a.artikeldatum, a.medium, a.titel, s.text,
       case when (s.tsv || a.tsv) @@ q then ts_rank_cd(s.tsv || a.tsv, q, 32) else 0 end
from uc2.abschnitt s join uc2.artikel a using (artikel_id),
     websearch_to_tsquery('german', %(frage)s) q
where s.abschnitt_id = any(%(ids)s)
"""


def vektor_stand(verbindung: psycopg.Connection[Any]) -> tuple[int, list[str]]:
    zeilen = verbindung.execute(
        "select count(*), coalesce(array_agg(distinct modell) filter (where modell is not null), '{}') "
        "from uc2.abschnitt where vektor is not null"
    ).fetchone()
    assert zeilen is not None
    return int(zeilen[0]), list(zeilen[1])


def suche(
    verbindung: psycopg.Connection[Any],
    frage: str,
    regeln: Regeln,
    modus: str | None = None,
    k: int | None = None,
    stichtag: date | None = None,
    einbetter: Einbetter | None = None,
) -> tuple[str, list[Treffer]]:
    """Gibt den tatsächlich genutzten Modus und die Treffer zurück (Rückfall auf volltext wird gemeldet)."""
    modus = modus or regeln.modus
    k = k or regeln.k
    stichtag = stichtag or regeln.stichtag_standard
    n = regeln.kandidaten

    cos_je_id: dict[str, float] = {}
    vektor_ids: list[str] = []
    if modus in ("vektor", "hybrid"):
        anzahl, modelle = vektor_stand(verbindung)
        grund = None
        if anzahl == 0:
            grund = "Index ohne Vektoren"
        elif einbetter is None:
            grund = "kein Einbetter"
        elif modelle != [einbetter.modell_id]:
            grund = f"Vektoren im Index von {modelle}, Abfrage mit {einbetter.modell_id}"
        if grund is not None or einbetter is None:
            print(f"Hinweis: Modus {modus} nicht möglich ({grund}), Rückfall auf volltext.", file=sys.stderr)
            modus = "volltext"
        else:
            zeilen = verbindung.execute(
                "select s.abschnitt_id, s.vektor from uc2.abschnitt s join uc2.artikel a using (artikel_id) "
                "where s.vektor is not null and a.artikeldatum <= %s order by s.abschnitt_id",
                (stichtag,),
            ).fetchall()
            if zeilen:
                ids = [str(z[0]) for z in zeilen]
                matrix = np.vstack([np.frombuffer(bytes(z[1]), dtype="<f4") for z in zeilen]).astype(
                    np.float64
                )
                abfrage = np.asarray(
                    einbetter.einbetten([abfrage_text(frage)], "abfrage")[0], dtype=np.float64
                )
                normen = np.linalg.norm(matrix, axis=1) * np.linalg.norm(abfrage)
                cos = (matrix @ abfrage) / np.where(normen == 0, 1.0, normen)
                beste = np.argsort(-cos, kind="stable")[:n]
                cos_je_id = {ids[i]: float(cos[i]) for i in range(len(ids))}
                vektor_ids = [ids[i] for i in beste]

    volltext_ids: list[str] = []
    if modus in ("volltext", "hybrid"):
        volltext_ids = [
            str(z[0])
            for z in verbindung.execute(VOLLTEXT_SQL, {"frage": frage, "stichtag": stichtag, "n": n})
        ]
    kandidaten_ids = sorted(set(volltext_ids) | set(vektor_ids))
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
        )
        for z in verbindung.execute(DETAIL_SQL, {"frage": frage, "ids": kandidaten_ids})
    ]
    return modus, bewerte(kandidaten, modus, stichtag, regeln, k)
