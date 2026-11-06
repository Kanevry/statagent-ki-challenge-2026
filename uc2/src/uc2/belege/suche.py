"""Such-Prototyp: Volltext (PG), Vektor (numpy-Kosinus) oder Hybrid, gewichtet nach Alter zum Stichtag.

Kandidaten sind die Vereinigung der besten `kandidaten` nach Volltext und nach Kosinus. Relevanz:
volltext = ts_norm (`ts_rank_cd(Abschnitt || Titel, …, 32)`, liegt in [0, 1)), vektor = max(cos, 0),
hybrid (fusion rrf) = gewicht_volltext/(rrf_k + rang_volltext) + gewicht_vektor/(rrf_k + rang_vektor),
Ränge je Verfahren über Artikel (bester Abschnitt) in dessen Kandidatenliste; fehlt ein Rang, entfällt
der Summand. hybrid (fusion summe) = gewicht_vektor · max(cos, 0) + gewicht_volltext · ts_norm.
Endrang = Relevanz · 0,5^(Alter/Halbwertszeit) · f, als letzter Faktor auch bei RRF (#43): f =
`institutionsfaktor` aus `regeln.yaml`, wenn `abschnitt.institutionen` des gewählten Abschnitts die
Institution des fragenden Akteurs enthält, sonst 1,0 (ohne Institution immer 1,0).
Artikel nach dem Stichtag sind ausgeschlossen; je Artikel zählt nur der beste Abschnitt.
Nachrechnen ohne Laufzeitcode: `uc2/tests/pruefe_rang.py`.
"""

from __future__ import annotations

import hashlib
import importlib
import json
import logging
import re
import sys
from collections.abc import Callable, Sequence
from dataclasses import asdict, dataclass
from datetime import date
from typing import Any, Protocol

import numpy as np
import psycopg

from uc2.belege.einbettung import Einbetter, abfrage_text
from uc2.belege.namen import Namensliste, lade_institutionen, maskiere_artikel, zitate_anzeige
from uc2.belege.regeln import Regeln, lade_regeln

log = logging.getLogger(__name__)

AUSSCHNITT_ZEICHEN = 200
ZITAT_ZEICHEN = 300
"""Höchstlänge des Belegzitats für Anzeige und API (Entscheid Lead, Owner-Klick #8705): online gehen je
Beleg nur Zitat, Medium, Datum, Titel und PDF-Seite hinaus, nie der ganze Artikel. Die Jury braucht den
belegten Satz mit Quelle, und der APA-Kopf des Pressespiegels lautet „persönliche Information“."""
_SATZENDE = re.compile(r"(?<=[.!?…])\s+")
_SUCHWORT = re.compile(r"\w{4,}")


def kurzzitat(text: str, frage: str, zeichen: int = ZITAT_ZEICHEN) -> str:
    """Belegter Satz: ab dem Satz mit den meisten Suchwörtern der Frage (Gleichstand: der frühere) höchstens
    `zeichen` Zeichen, an einer Wortgrenze gekürzt mit „…“. Erwartet den schon maskierten Anzeigetext."""
    flach = " ".join(text.split())
    if not flach:
        return ""
    woerter = {w.lower() for w in _SUCHWORT.findall(frage)}
    saetze = _SATZENDE.split(flach)
    bester, punkte, start = 0, -1, 0
    pos = 0
    for i, satz in enumerate(saetze):
        p = sum(1 for w in _SUCHWORT.findall(satz) if w.lower() in woerter)
        if p > punkte:
            bester, punkte, start = i, p, pos
        pos += len(satz) + 1
    rest = flach[start:] if bester else flach
    if len(rest) <= zeichen:
        return rest
    schnitt = rest.rfind(" ", 0, zeichen - 1)
    return rest[: schnitt if schnitt > 0 else zeichen - 1].rstrip() + "…"


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
    institutionen: tuple[str, ...] = ()
    """Institutions-Tags des Abschnitts (`abschnitt.institutionen`)."""


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
    faktor_institution: float = 1.0
    """Letzter Faktor des Endrangs: `rang = relevanz · gewicht_alter · faktor_institution`."""
    institution: str | None = None
    """Institution des fragenden Akteurs, gegen die `faktor_institution` bestimmt wurde."""

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


def faktor_institution(institutionen: tuple[str, ...], institution: str | None, regeln: Regeln) -> float:
    """`institutionsfaktor`, wenn der Abschnitt die Institution des Akteurs trägt, sonst 1,0."""
    if institution is not None and institution in institutionen:
        return regeln.institutionsfaktor
    return 1.0


def _treffer(
    kand: Kandidat,
    rel: float,
    stichtag: date,
    regeln: Regeln,
    institution: str | None = None,
    **raenge: int | None,
) -> Treffer:
    gewicht = gewicht_alter(kand.artikeldatum, stichtag, regeln.halbwertszeit_tage)
    faktor = faktor_institution(kand.institutionen, institution, regeln)
    return Treffer(
        abschnitt_id=kand.abschnitt_id,
        artikel_id=kand.artikel_id,
        relevanz=rel,
        cos=kand.cos,
        ts=kand.ts,
        gewicht_alter=gewicht,
        rang=rel * gewicht * faktor,
        artikeldatum=kand.artikeldatum.isoformat(),
        medium=kand.medium,
        titel=kand.titel,
        ausschnitt=" ".join(kand.text.split())[:AUSSCHNITT_ZEICHEN],
        faktor_institution=faktor,
        institution=institution,
        **raenge,
    )


def _artikelraenge(kandidaten: list[Kandidat], wert: str) -> tuple[dict[str, int], dict[str, Kandidat]]:
    """Bester Abschnitt je Artikel nach `wert` (ts oder cos) und Artikelrang 1, 2, …; Gleichstand nach ID."""
    bester: dict[str, Kandidat] = {}
    for kand in sorted(kandidaten, key=lambda c: (-getattr(c, wert), c.abschnitt_id)):
        bester.setdefault(kand.artikel_id, kand)
    reihe = sorted(bester.values(), key=lambda c: (-getattr(c, wert), c.artikel_id))
    return {c.artikel_id: n for n, c in enumerate(reihe, start=1)}, bester


def bewerte_rrf(
    kandidaten: list[Kandidat], stichtag: date, regeln: Regeln, k: int, institution: str | None = None
) -> list[Treffer]:
    """Gewichtete RRF über Artikelränge, dann Alter und Institutionsfaktor; Gleichstand nach artikel_id.

    Der Faktor gilt für den gewählten Abschnitt (bester nach ts, sonst bester nach cos).
    """
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
                institution,
                rang_volltext=rang_t.get(artikel_id),
                rang_vektor=rang_v.get(artikel_id),
            )
        )
    reihe = sorted(treffer, key=lambda t: (-t.rang, t.artikel_id))
    return [t for t in reihe if t.rang > 0][:k]


def bewerte(
    kandidaten: list[Kandidat],
    modus: str,
    stichtag: date,
    regeln: Regeln,
    k: int,
    institution: str | None = None,
) -> list[Treffer]:
    """Endrang je Kandidat, bester Abschnitt je Artikel, Top k; Gleichstand nach abschnitt_id.

    Hybrid mit `fusion: rrf` geht an `bewerte_rrf`.
    """
    if modus == "hybrid" and regeln.fusion == "rrf":
        return bewerte_rrf(kandidaten, stichtag, regeln, k, institution)
    bester: dict[str, Treffer] = {}
    for kand in sorted(kandidaten, key=lambda c: c.abschnitt_id):
        if kand.artikeldatum > stichtag:
            continue
        treffer = _treffer(kand, relevanz(modus, kand.cos, kand.ts, regeln), stichtag, regeln, institution)
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
       -- float8: exakter float4-Wert; als real käme er als gerundete Dezimalzahl an (Abweichung ~3e-9)
       (case when (s.tsv || a.tsv) @@ q then ts_rank_cd(s.tsv || a.tsv, q, 32) else 0 end)::float8,
       s.institutionen
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


def _einbetter_fehler() -> tuple[type[BaseException], ...]:
    """Fehler, bei denen die Suche auf volltext zurückfällt: fehlendes Extra (ImportError, auch
    `plattform.embeddings.EmbeddingsFehlen`) und Modell nicht im Cache (`plattform.embeddings.ModellFehlt`).
    Andere Fehler laufen durch."""
    try:
        modul = importlib.import_module("plattform.embeddings")
    except ImportError:
        return (ImportError,)
    modell_fehlt = getattr(modul, "ModellFehlt", None)
    if isinstance(modell_fehlt, type) and issubclass(modell_fehlt, BaseException):
        return (ImportError, modell_fehlt)
    return (ImportError,)


def _grund_einbetter(fehler: BaseException) -> str:
    if isinstance(fehler, ImportError):
        fehlt = fehler.name or str(fehler)
        return f"Einbetter nicht ladbar, {fehlt} fehlt (Extra `einbettung` installieren)"
    return (
        f"Embedding-Modell nicht im Cache ({type(fehler).__name__}); einmal "
        "`uv run python -m plattform.embeddings laden` ausführen"
    )


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
    institution: str | None = None,
) -> tuple[str, list[Treffer]]:
    """Gibt den tatsächlich genutzten Modus und die Treffer zurück (Rückfall auf volltext wird gemeldet).

    `institution` (ID aus `institutionen.yaml`) ist die Institution des fragenden Akteurs; Abschnitte mit
    diesem Tag bekommen den Institutionsfaktor als letzten Faktor des Endrangs. Ohne sie ist f = 1,0.

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
            except _einbetter_fehler() as fehler:
                grund = _grund_einbetter(fehler)
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
                # dimension() und einbetten() laden das Modell erst hier (plattform.embeddings): fehlt das
                # Extra oder das Modell im Cache, gilt derselbe Rückfall wie beim Bau des Einbetters.
                try:
                    dimension = einbetter.dimension()
                    gelesen = _lies_vektoren(zeilen, dimension)
                    abfrage = np.empty(0)
                    if not isinstance(gelesen, str):
                        abfrage = np.asarray(
                            einbetter.einbetten([abfrage_text(frage)], "abfrage")[0], dtype=np.float64
                        )
                except _einbetter_fehler() as fehler:
                    gelesen = _grund_einbetter(fehler)
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
            institutionen=tuple(str(i) for i in (z[7] or ())),
        )
        for z in verbindung.execute(
            DETAIL_SQL.format(abfrage=ts_abfrage), {"frage": frage, "ids": kandidaten_ids}
        )
    ]
    return modus, bewerte(kandidaten, modus, stichtag, regeln, k, institution)


# --- Belege je Akteur (#43, Schnittstelle für #44) -------------------------------------------------------

THEMEN_IN_ABFRAGE = 3
"""Höchstens so viele `themen_interesse` des Akteurs gehen in die Abfrage."""


class AkteurFuerBelege(Protocol):
    """Was `belege_fuer_akteur` vom Akteur braucht; `uc2.akteure.laden.Akteur` erfüllt es."""

    @property
    def id(self) -> str: ...

    @property
    def institution(self) -> str: ...

    @property
    def themen_interesse(self) -> Sequence[str]: ...


@dataclass(frozen=True)
class Beleg:
    """Ein maskierter Beleg für einen Akteurszug (#44) oder die Anzeige.

    Felder für einen dünnen Adapter auf `belege_fuer(akteur, frage, runde, stichtag) -> list[Beleg]`:
    - `beleg_id` (= `abschnitt_id`, stabil, zitierbar), `artikel_id`, `medium`, `datum` (JJJJ-MM-TT),
      `monat` (JJJJ-MM);
    - `titel` maskiert; `text_modell` maskiert mit Zitaten (für das Modell, nur über `als_datenblock`);
      `text_anzeige` maskiert, direkte Zitate als „[Zitat]“ (nur lokal, `als_dict(mit_text=True)`);
    - `zitat` (belegter Satz, höchstens `ZITAT_ZEICHEN` Zeichen) und `pdf_seite`: online gehen nur Zitatfelder
      hinaus, nie ein ganzer Abschnitt (Entscheid Lead, Owner-Klick #8705; `als_dict()` ohne Argument);
    - Rangteile: `rang = relevanz · gewicht_alter · faktor_institution`, dazu `ts`, `cos`,
      `rang_volltext`, `rang_vektor` (RRF-Eingänge) zum Nachrechnen mit `tests/pruefe_rang.py`.
    """

    beleg_id: str
    artikel_id: str
    medium: str
    datum: str
    monat: str
    titel: str
    text_modell: str
    text_anzeige: str
    rang: float
    relevanz: float
    gewicht_alter: float
    faktor_institution: float
    ts: float
    cos: float
    rang_volltext: int | None
    rang_vektor: int | None
    pdf_seite: int | None = None
    zitat: str = ""
    """Belegter Satz aus `text_anzeige`, höchstens `ZITAT_ZEICHEN` Zeichen (siehe dort, warum)."""

    def als_dict(self, *, mit_text: bool = False, fuer_modell: bool = False) -> dict[str, Any]:
        """Standard (Online-Grenze): Kennung, Quelle, Titel, `pdf_seite`, `zitat` und Rangteile, ohne Texte.

        `mit_text=True` fügt `text_anzeige` hinzu (ganzer Abschnitt, Zitate als „[Zitat]“), zusätzlich
        `fuer_modell=True` auch `text_modell` (mit Zitaten). Beides nur lokal, nie für Oberfläche oder API.
        """
        if fuer_modell and not mit_text:
            raise ValueError("fuer_modell=True verlangt mit_text=True")
        daten = asdict(self)
        if not fuer_modell:
            del daten["text_modell"]
        if not mit_text:
            del daten["text_anzeige"]
        return daten


@dataclass(frozen=True)
class Belegsuche:
    """Ergebnis von `suche_belege`: genutzter Modus, tatsächliche Abfrage und Belege."""

    modus: str
    abfrage: str
    stichtag: date
    institution: str
    belege: list[Beleg]


def belege_abfrage(frage: str, akteur: AkteurFuerBelege, institutionsname: str) -> str:
    """Abfrage = Frage + Name der Institution + die ersten (bis zu 3) `themen_interesse` des Akteurs."""
    return " ".join([frage, institutionsname, *list(akteur.themen_interesse)[:THEMEN_IN_ABFRAGE]])


def cache_schluessel(akteur_id: str, frage: str, runde: int, stichtag: date) -> str:
    """Schlüssel für einen Belege-Cache je Akteur, Frage, Runde und Stichtag (sha256, ohne Inhalt)."""
    roh = json.dumps([akteur_id, frage, runde, stichtag.isoformat()], ensure_ascii=False)
    return hashlib.sha256(roh.encode("utf-8")).hexdigest()


ARTIKELTEXT_SQL = """
select artikel_id, abschnitt_id, text, institutionen from uc2.abschnitt
where artikel_id = any(%(ids)s) order by artikel_id, nr
"""


def maskiere_treffer(
    verbindung: psycopg.Connection[Any],
    treffer: Sequence[Treffer],
    namen: Namensliste | None,
    frage: str = "",
) -> list[Beleg]:
    """Treffer → maskierte Belege. Namen werden über Titel und alle Abschnitte des Artikels erkannt; `frage`
    wählt den Satz für `zitat`."""
    ids = sorted({t.artikel_id for t in treffer})
    teile_je_artikel: dict[str, list[tuple[str, str, list[str]]]] = {}
    for z in verbindung.execute(ARTIKELTEXT_SQL, {"ids": ids}):
        teile_je_artikel.setdefault(str(z[0]), []).append((str(z[1]), str(z[2]), list(z[3] or [])))
    seiten = {
        str(z[0]): int(z[1])
        for z in verbindung.execute(
            "select artikel_id, pdf_seite from uc2.artikel where artikel_id = any(%(ids)s)", {"ids": ids}
        )
    }
    belege: list[Beleg] = []
    for t in treffer:
        abschnitte = teile_je_artikel.get(t.artikel_id, [])
        teile = [t.titel, *(text for _, text, _ in abschnitte)]
        nr = 1 + next(i for i, (aid, _, _) in enumerate(abschnitte) if aid == t.abschnitt_id)
        tags = sorted({i for _, _, inst in abschnitte for i in inst})
        titel, text = maskiere_artikel(teile, tags, namen, nur=(0, nr))
        belege.append(
            Beleg(
                beleg_id=t.abschnitt_id,
                artikel_id=t.artikel_id,
                medium=t.medium,
                datum=t.artikeldatum,
                monat=t.artikeldatum[:7],
                titel=titel,
                text_modell=text,
                text_anzeige=zitate_anzeige(text),
                pdf_seite=seiten.get(t.artikel_id),
                zitat=kurzzitat(zitate_anzeige(text), frage),
                rang=t.rang,
                relevanz=t.relevanz,
                gewicht_alter=t.gewicht_alter,
                faktor_institution=t.faktor_institution,
                ts=t.ts,
                cos=t.cos,
                rang_volltext=t.rang_volltext,
                rang_vektor=t.rang_vektor,
            )
        )
    return belege


def suche_belege(
    verbindung: psycopg.Connection[Any],
    akteur: AkteurFuerBelege,
    frage: str,
    runde: int,
    *,
    stichtag: date | None = None,
    regeln: Regeln | None = None,
    einbetter: Einbetter | None = None,
    einbetter_fabrik: Callable[[], Einbetter] | None = None,
    namen: Namensliste | None = None,
    modus: str | None = None,
    k: int | None = None,
) -> Belegsuche:
    """Wie `belege_fuer_akteur`, dazu Modus und Abfrage (für `uc2 suche --akteur --json` und das Orakel)."""
    liste = namen if namen is not None else Namensliste.lade()  # fail-closed vor jeder Abfrage
    regeln = regeln or lade_regeln()
    stichtag = stichtag or regeln.stichtag_standard
    institutionen = lade_institutionen(regeln=regeln)
    abfrage = belege_abfrage(frage, akteur, institutionen.namen.get(akteur.institution, akteur.institution))
    genutzt, treffer = suche(
        verbindung,
        abfrage,
        regeln,
        modus=modus,
        k=k or regeln.k_je_akteur,
        stichtag=stichtag,
        einbetter=einbetter,
        einbetter_fabrik=einbetter_fabrik,
        institution=akteur.institution,
    )
    belege = maskiere_treffer(verbindung, treffer, liste, frage)
    log.info(
        "belege akteur=%s runde=%s stichtag=%s modus=%s n=%d schluessel=%s",
        akteur.id,
        runde,
        stichtag.isoformat(),
        genutzt,
        len(belege),
        cache_schluessel(akteur.id, frage, runde, stichtag)[:12],
    )
    return Belegsuche(genutzt, abfrage, stichtag, akteur.institution, belege)


def belege_fuer_akteur(
    verbindung: psycopg.Connection[Any],
    akteur: AkteurFuerBelege,
    frage: str,
    runde: int,
    *,
    stichtag: date | None = None,
    regeln: Regeln | None = None,
    einbetter: Einbetter | None = None,
    einbetter_fabrik: Callable[[], Einbetter] | None = None,
    namen: Namensliste | None = None,
) -> list[Beleg]:
    """Die k besten maskierten Belege für einen Akteur (k = `suche.k_je_akteur` aus `regeln.yaml`, 8).

    - Abfrage = `frage` + Name der Institution des Akteurs (aus `institutionen.yaml`) + die ersten bis zu
      3 `themen_interesse`, mit Leerzeichen verbunden (`belege_abfrage`).
    - Endrang wie `suche`, mit `institution = akteur.institution`: Belege, deren Abschnitt die Institution
      trägt, bekommen den `institutionsfaktor` (1,5) als letzten Faktor.
    - Personenschutz: Titel und Text laufen durch `uc2.belege.namen.maskiere_artikel` (Namen aus Titel und
      allen Abschnitten des Artikels; Muster plus `namen`, ohne `namen` die Liste aus `UC2_NAMENSLISTE`;
      fehlt sie, wirft `Namensliste.lade` `NamenslisteFehlt`, fail-closed).
    - `runde` geht nur in Protokoll und Cache-Schlüssel (`cache_schluessel`) ein, nicht in die Auswahl.
    - Fürs Modell: `uc2.belege.namen.als_datenblock(belege)`; für Anzeige und API `Beleg.als_dict()`.
    """
    return suche_belege(
        verbindung,
        akteur,
        frage,
        runde,
        stichtag=stichtag,
        regeln=regeln,
        einbetter=einbetter,
        einbetter_fabrik=einbetter_fabrik,
        namen=namen,
    ).belege
