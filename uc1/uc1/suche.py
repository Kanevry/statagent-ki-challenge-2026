"""Suche `lotse suche` (#29): Volltext über lotse.abschnitt.tsv mit Rückfall auf pg_trgm.

Volltext: Die Lexeme der Frage (Stoppwörter fallen weg) werden ODER-verknüpft, damit eine lange
Bürgerfrage nicht an einer UND-Verknüpfung scheitert. Jeder Term zählt mit
  IDF (ln(1 + N/df), df über den GIN-Index) x Themenfaktor (kommt der Term in Überschriften vor?)
  x r/(r+K) mit r = ts_rank des Terms (Häufigkeit, Gewicht A Überschrift / B Text), BM25-artig gesättigt.
Lexeme ab 5 Zeichen werden als Präfix gesucht (krankengeld:* findet Krankengeldanspruch), lange Lexeme
zusätzlich über bekannte Teile (pflegegeldstuf -> pflegegeld, stuf). Abgewertet werden lange Abschnitte
und Abschnitte sehr großer Sammeldokumente (dokument.meta.zeichen, z. B. Entscheidungsübersichten);
leicht bevorzugt werden Gesetze, auf die andere Gesetze oft verweisen (dokument.meta.autoritaet).
Mehrere Fassungen eines Paragraphen belegen einen Platz (jüngste Fassung). Bleiben weniger als k
Treffer, ergänzt pg_trgm (Wortähnlichkeit) mit weg="trgm". Höchstens MAX_TERME Terme gehen in die Anfrage.

Filter: Der Gesetzesfilter schränkt nur SozDok ein; PDFs und EKO haben kein Gesetz und bleiben, solange
`quellen` sie nicht ausschließt (Review N2). Aufgehobene Paragraphen (dokument.meta.aufgehoben, gesetzt
beim Ingest) fallen in allen Wegen weg, außer mit mit_aufgehobenen=True (Review D1b).

Dicht: Cosinus in numpy gegen lotse.vektor (google/embeddinggemma-2, SUCH_DIMENSION). Die Matrix lädt je
Prozess und Verbindung einmal; Filter, Abwertung großer Sammeldokumente und eine Fassung je Paragraph gelten
wie beim Volltext. Hybrid: Reciprocal Rank Fusion (k=60) aus Volltext und dicht auf Ebene der Abschnitte.
Auto: hybrid, wenn Vektoren da sind (einmal je Prozess geprüft), sonst Volltext.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import re
import sys
import threading
import time
from collections.abc import Callable, Sequence
from dataclasses import asdict, dataclass, replace

import numpy as np
import numpy.typing as npt
import psycopg

from uc1 import einbettung
from uc1.db import verbinde
from uc1.typen import Quelle, SuchFilter, Suchweg, Treffer, TrefferWeg

# Rangparameter (generisch, nicht auf einzelne Fragen abgestimmt).
PRAEFIX_AB = 5  # Lexeme ab dieser Länge als Präfix suchen (Komposita mit dem Wort als Anfang)
ZERLEGEN_AB = 9  # Lexeme ab dieser Länge zusätzlich über ihr längstes bekanntes Präfix suchen
TEIL_FAKTOR = 0.7  # Gewicht eines solchen Teils relativ zu seiner IDF
AUTORITAET_GEWICHT = 0.4  # Faktor 0,6 (nie zitiert) bis 1,0 (meistzitiertes Gesetz); PDF/EKO 0,8
KANDIDAT_DF_ANTEIL = 0.02  # Kandidaten nur über Terme, die in höchstens 2 % der Abschnitte stehen
THEMA_MIN = 0.3  # Gewicht eines Terms, der in keiner Überschrift vorkommt
THEMA_VOLL = 50  # ab so vielen Überschriften mit dem Term volles Gewicht
SAETTIGUNG = 0.5  # K in r/(r+K) für ts_rank je Term
KANDIDATEN_FAKTOR = 8  # k mal so viele Kandidaten, bevor Fassungen zusammengelegt werden
NACHLADE_FAKTOR = 8  # ergeben die Kandidaten weniger als k Paragraphen: einmal so viel mal mehr holen
ABSCHNITT_REFERENZ = 1500  # Zeichen; längere Abschnitte werden logarithmisch abgewertet
DOKUMENT_REFERENZ = 50_000  # Zeichen; größere Dokumente (Sammelwerke) werden logarithmisch abgewertet
TRGM_SCHWELLE = 0.6  # word_similarity für den Rückfall
TRGM_WOERTER = 3  # so viele (längste, im Volltext seltene) Wörter prüft der Rückfall
# Deckel für die Terme einer Anfrage (Lexeme samt Teilen aus der Zerlegung). Frage plus Erweiterung ergab
# bis zu ~40 Terme, und ts_rank je Term über viele Kandidaten trieb die Volltext-Zeit auf bis 2 s (Review
# D1c). Behalten werden die MAX_TERME mit dem höchsten Gewicht (IDF x Themenfaktor x Teilfaktor), also
# die seltenen Fachwörter; häufige Füllwörter und Wortteile fallen zuerst weg. Ziel: p95 unter 300 ms.
MAX_TERME = 12
# Dimension der Suche. Der Dienst sucht mit 256 (Messbericht: so gut wie 768 bei einem Drittel Speicher);
# EMBED_DIM überschreibt. Der Adapter selbst bleibt beim Standard 768 (einbettung.dimension()).
SUCH_DIMENSION = 256
# Reciprocal Rank Fusion: score = Summe 1/(RRF_K + Rang). 60 ist der Wert aus Cormack et al. (2009) und
# dem Prototyp (messung-embeddings.md); er dämpft den Abstand zwischen Platz 1 und Platz 10, sodass ein
# Abschnitt, den beide Wege finden, vor einem steht, den nur einer weit oben hat.
RRF_K = 60
HYBRID_N = 50  # so viele Abschnitte je Weg gehen in die Fusion

# Feste Messfragen für p50/p95 (allgemeine Bürgerfragen, nicht das Lotse-Set).
MESSFRAGEN = (
    "Meine Mutter (82) braucht ungefähr 75 Stunden Pflege im Monat. Welche Pflegegeldstufe ist das "
    "und wohin schicke ich den Antrag?",
    "Ich bin seit acht Wochen im Krankenstand. Wie lange bekomme ich Krankengeld?",
    "Ich bin auf dem Heimweg von der Arbeit gestürzt. Ist das ein Arbeitsunfall und wer zahlt?",
    "Wann kann ich in Pension gehen, wenn ich 1965 geboren bin?",
    "Bekomme ich Wochengeld, wenn ich selbständig bin?",
    "Wer übernimmt die Kosten für eine Kur oder Rehabilitation?",
    "Muss ich für Medikamente eine Rezeptgebühr zahlen und kann ich davon befreit werden?",
    "Wie hoch ist der Zuschuss für eine Zahnspange bei Kindern?",
    "Ist mein Ehepartner bei mir mitversichert?",
    "Was passiert mit meiner Versicherung, wenn ich arbeitslos werde?",
    "Bekomme ich Fahrtkosten ersetzt, wenn ich zur Dialyse fahre?",
    "Wie beantrage ich eine Invaliditätspension wegen Krankheit?",
)


class SuchwegNichtVerfuegbar(RuntimeError):
    """Der Suchweg (dicht, hybrid) ist nicht nutzbar, z. B. weil lotse.vektor für Modell und Dimension
    keine Vektoren enthält."""


_WORT = re.compile(r"\w{4,}")

_SPALTEN = (
    "a.id, d.dokid, d.quelle, d.datei, d.gesetz, d.art, d.nummer, d.inkrafttreten,"
    " a.seite, a.zeile, a.kontext, a.text"
)
# Gesetzesfilter nur für SozDok: PDFs und EKO haben gesetz NULL und fielen sonst immer heraus (N2).
_FILTER = (
    " AND (cardinality(%(gesetze)s::text[]) = 0 OR d.quelle <> 'sozdok' OR d.gesetz = ANY(%(gesetze)s))"
    " AND (cardinality(%(arten)s::text[]) = 0 OR d.quelle <> 'sozdok' OR d.art = ANY(%(arten)s))"
    " AND (cardinality(%(quellen)s::text[]) = 0 OR d.quelle = ANY(%(quellen)s))"
    " AND (%(mit_aufgehobenen)s OR NOT coalesce((d.meta->>'aufgehoben')::boolean, false))"
)
# Längenabwertung: Abschnitt und Dokument, beide 1 bis ca. 0,3 bei sehr großen Werten.
_ABWERTUNG = (
    " / (1 + 0.5 * ln(1 + length(a.text)::float8 / %(abschnitt_ref)s))"
    " / (1 + ln(1 + coalesce((d.meta->>'zeichen')::float8, length(a.text)) / %(dokument_ref)s))"
    " * (1 - %(autoritaet)s + %(autoritaet)s * coalesce((d.meta->>'autoritaet')::float8, 0.5))"
)


def tsquery_literal(lexem: str) -> str:
    """Ein Lexem als gequoteter tsquery-Operand; & | ! ( ) : und Apostrophe sind darin wirkungslos."""
    return "'" + lexem.replace("\\", "\\\\").replace("'", "''") + "'"


def lexeme(conn: psycopg.Connection, frage: str) -> list[str]:
    """Lexeme der Frage über dieselbe Konfiguration wie tsv; Stoppwörter fallen dabei weg."""
    zeile = conn.execute(
        "SELECT tsvector_to_array(to_tsvector('public.lotse_german', %s))", (frage,)
    ).fetchone()
    return sorted(zeile[0]) if zeile and zeile[0] else []


def _filter_param(f: SuchFilter | None, mit_aufgehobenen: bool = False) -> dict[str, object]:
    f = f or SuchFilter()
    return {
        "gesetze": list(f.gesetze),
        "arten": list(f.arten),
        "quellen": list(f.quellen),
        "mit_aufgehobenen": mit_aufgehobenen,
    }


def _treffer(zeile: tuple[object, ...], score: float, weg: TrefferWeg) -> Treffer:
    (abschnitt_id, dokid, quelle, datei, gesetz, art, nummer, ikra, seite, zeile_nr, kontext, text) = zeile
    return Treffer(
        abschnitt_id=int(abschnitt_id),  # type: ignore[call-overload]
        dokid=str(dokid),
        quelle=quelle,  # type: ignore[arg-type]
        datei=str(datei),
        gesetz=gesetz,  # type: ignore[arg-type]
        art=art,  # type: ignore[arg-type]
        nummer=nummer,  # type: ignore[arg-type]
        inkrafttreten=ikra,  # type: ignore[arg-type]
        seite=seite,  # type: ignore[arg-type]
        zeile=zeile_nr,  # type: ignore[arg-type]
        kontext=str(kontext),
        text=str(text),
        score=round(score, 6),
        weg=weg,
    )


def _kopf(op: str) -> str:
    """Operand eingeschränkt auf Gewicht A (Überschrift/Kontext): 'x':A bzw. 'x':*A."""
    return op + "A" if op.endswith(":*") else op + ":A"


def _df(conn: psycopg.Connection, operanden: Sequence[str]) -> tuple[int, list[int], list[int]]:
    """Zahl aller Abschnitte, df je tsquery-Operand und df_A (Treffer in der Überschrift)."""
    zeile = conn.execute(
        "SELECT (SELECT count(*) FROM lotse.abschnitt),"
        " array_agg(z.df ORDER BY t.i), array_agg(z.dfa ORDER BY t.i)"
        " FROM unnest(%s::text[], %s::text[]) WITH ORDINALITY AS t(q, h, i),"
        " LATERAL (SELECT count(*) AS df, count(*) FILTER (WHERE tsv @@ t.h::tsquery) AS dfa"
        "          FROM lotse.abschnitt WHERE tsv @@ t.q::tsquery) AS z",
        (list(operanden), [_kopf(o) for o in operanden]),
    ).fetchone()
    if not zeile or zeile[1] is None:
        return int(zeile[0]) if zeile else 0, [0] * len(operanden), [0] * len(operanden)
    return int(zeile[0]), [int(x) for x in zeile[1]], [int(x) for x in zeile[2]]


def themenfaktor(df_kopf: int) -> float:
    """Fachbegriffe stehen in Überschriften, Füllwörter einer Frage (seit, ungefähr, wohin) kaum.
    0 Überschriften: THEMA_MIN, ab THEMA_VOLL Überschriften: 1 (logarithmisch dazwischen)."""
    anteil = min(1.0, math.log1p(df_kopf) / math.log1p(THEMA_VOLL))
    return THEMA_MIN + (1 - THEMA_MIN) * anteil


def operand(lexem: str) -> str:
    """Ab PRAEFIX_AB Zeichen als Präfix (krankengeld:* findet krankengeldanspruch)."""
    return tsquery_literal(lexem) + (":*" if len(lexem) >= PRAEFIX_AB else "")


def zerlege(conn: psycopg.Connection, lexeme_: Sequence[str]) -> dict[str, list[str]]:
    """Lange Lexeme in Teile, die selbst Lexeme im Korpus sind: das längste echte Präfix (mind. 5
    Zeichen, mind. 3 Zeichen Rest) und, falls bekannt, der Rest (sonst ohne Fugen-s). pflegegeldstuf ->
    pflegegeld, stuf."""
    kandidaten = {lx: [lx[:i] for i in range(len(lx) - 3, 4, -1)] for lx in lexeme_ if len(lx) >= ZERLEGEN_AB}
    reste = {
        r for lx in kandidaten for i in range(5, len(lx) - 2) for r in (lx[i:], lx[i:].removeprefix("s"))
    }
    alle = sorted({p for ps in kandidaten.values() for p in ps} | {r for r in reste if len(r) >= 3})
    if not alle:
        return {}
    _, dfs, _ = _df(conn, [tsquery_literal(p) for p in alle])
    bekannt = {p for p, df in zip(alle, dfs, strict=True) if df > 0}
    teile: dict[str, list[str]] = {}
    for lx, ps in kandidaten.items():
        praefix = next((p for p in ps if p in bekannt), None)
        if praefix:
            roh = lx[len(praefix) :]
            rest = next((r for r in (roh, roh.removeprefix("s")) if len(r) >= 3 and r in bekannt), None)
            teile[lx] = [praefix] + ([rest] if rest else [])
    return teile


def deckle_terme(
    terme: Sequence[tuple[str, float, int]], max_terme: int = MAX_TERME
) -> list[tuple[str, float, int]]:
    """Die max_terme Terme mit dem höchsten Gewicht, in der Reihenfolge der Eingabe (deterministisch:
    bei gleichem Gewicht entscheidet der Operand)."""
    if len(terme) <= max_terme:
        return list(terme)
    behalten = {o for o, _, _ in sorted(terme, key=lambda t: (-t[1], t[0]))[:max_terme]}
    return [t for t in terme if t[0] in behalten]


def anfrage_terme(
    conn: psycopg.Connection, frage: str
) -> tuple[list[str], int, list[tuple[str, float, int]]]:
    """Lexeme der Frage, Zahl der Abschnitte und Terme (Operand, Gewicht, df); df 0 fällt weg.
    Gewicht = IDF mal Teil-Faktor (Zerlegung) mal Themenfaktor (Vorkommen in Überschriften); höchstens
    MAX_TERME Terme (deckle_terme)."""
    lx = lexeme(conn, frage)
    terme: dict[str, float] = {operand(x): 1.0 for x in lx}
    for teile in zerlege(conn, lx).values():
        for teil in teile:
            terme.setdefault(operand(teil), TEIL_FAKTOR)
    ops = sorted(terme)
    n, dfs, dfas = _df(conn, ops)
    gewichtet = [
        (o, terme[o] * math.log(1 + n / df) * themenfaktor(dfa), df)
        for o, df, dfa in zip(ops, dfs, dfas, strict=True)
        if df
    ]
    return lx, n, deckle_terme(gewichtet)


def _ein_treffer_je_paragraph(treffer: list[Treffer], k: int) -> list[Treffer]:
    """Mehrere Fassungen desselben Paragraphen (gesetz, art, nummer) belegen nur einen Platz: der
    beste Abschnitt der jüngsten Fassung unter den Kandidaten, Platz nach dem besten Score der Gruppe."""
    gruppen: dict[tuple[str, ...], list[Treffer]] = {}
    for t in treffer:
        schluessel = (t.gesetz, t.art, t.nummer) if t.gesetz and t.nummer else (t.dokid, str(t.abschnitt_id))
        gruppen.setdefault(tuple(x or "" for x in schluessel), []).append(t)
    ergebnis = []
    for liste in gruppen.values():
        juengste = max((t.inkrafttreten for t in liste if t.inkrafttreten), default=None)
        fassung = [t for t in liste if t.inkrafttreten == juengste] or liste
        ergebnis.append(replace(fassung[0], score=liste[0].score))
    return ergebnis[:k]


def volltext(
    conn: psycopg.Connection, frage: str, k: int, filter: SuchFilter | None, mit_aufgehobenen: bool = False
) -> tuple[list[Treffer], list[str]]:
    n_max = k * KANDIDATEN_FAKTOR
    kandidaten, lx = volltext_kandidaten(conn, frage, n_max, filter, mit_aufgehobenen)
    treffer = _ein_treffer_je_paragraph(kandidaten, k)
    if len(treffer) < k and len(kandidaten) == n_max:
        # Die Kandidaten lagen in weniger als k Paragraphen (viele Absätze eines großen §). Mehr Volltext ist
        # billig; der pg_trgm-Rückfall kostete hier über 1 s (Dev-Set d02).
        n_max *= NACHLADE_FAKTOR
        kandidaten, lx = volltext_kandidaten(conn, frage, n_max, filter, mit_aufgehobenen)
        treffer = _ein_treffer_je_paragraph(kandidaten, k)
    return treffer, lx


def volltext_kandidaten(
    conn: psycopg.Connection,
    frage: str,
    n_max: int,
    filter: SuchFilter | None,
    mit_aufgehobenen: bool = False,
) -> tuple[list[Treffer], list[str]]:
    """Bis zu n_max Abschnitte nach Volltext-Score, beste zuerst, Fassungen noch nicht zusammengelegt."""
    lx, n, terme = anfrage_terme(conn, frage)
    if not terme:
        return [], lx
    selten = [o for o, _, df in terme if df <= KANDIDAT_DF_ANTEIL * n] or [o for o, _, _ in terme]
    params: dict[str, object] = {
        "q": " | ".join(selten),
        "ops": [o for o, _, _ in terme],
        "idf": [w for _, w, _ in terme],
        "abschnitt_ref": ABSCHNITT_REFERENZ,
        "dokument_ref": DOKUMENT_REFERENZ,
        "n": n_max,
        "autoritaet": AUTORITAET_GEWICHT,
        "k_satt": SAETTIGUNG,
        **_filter_param(filter, mit_aufgehobenen),
    }
    # ts_rank je Term misst Häufigkeit und Gewicht (A Überschrift 1.0, B Text 0.4); r/(r+K) sättigt das
    # wie BM25, damit viele verschiedene Terme mehr zählen als ein oft wiederholter.
    sql = (
        f"SELECT {_SPALTEN}, (SELECT sum(t.w * r.r / (r.r + %(k_satt)s))"
        "   FROM unnest(%(ops)s::text[], %(idf)s::float8[]) AS t(o, w),"
        "   LATERAL (SELECT ts_rank(a.tsv, t.o::tsquery)::float8 AS r) AS r)"
        f"   {_ABWERTUNG} AS score"
        " FROM lotse.abschnitt a JOIN lotse.dokument d ON d.id = a.dokument_id"
        f" WHERE a.tsv @@ %(q)s::tsquery {_FILTER}"
        " ORDER BY score DESC, a.id LIMIT %(n)s"
    )
    zeilen = conn.execute(sql, params).fetchall()
    return [_treffer(z[:-1], float(z[-1]), "volltext") for z in zeilen], lx


def trigramm(
    conn: psycopg.Connection,
    frage: str,
    k: int,
    filter: SuchFilter | None,
    ausschluss: Sequence[int],
    lexeme_: Sequence[str] = (),
    mit_aufgehobenen: bool = False,
) -> list[Treffer]:
    """Rückfall über pg_trgm: die längsten Wörter der Frage, die keine Stoppwörter sind, als
    Wortähnlichkeit gegen abschnitt.text."""
    staemme = {x[:4] for x in lexeme_}
    woerter = sorted(set(_WORT.findall(frage.lower())), key=lambda w: (-len(w), w))
    auswahl = [w for w in woerter if not staemme or w[:4] in staemme][:TRGM_WOERTER]
    if not auswahl or k <= 0:
        return []
    params: dict[str, object] = {
        "woerter": auswahl,
        "aus": list(ausschluss),
        "k": k,
        **_filter_param(filter, mit_aufgehobenen),
    }
    sql = (
        f"SELECT {_SPALTEN}, s.score FROM ("
        "  SELECT a.id, max(word_similarity(w, a.text)) AS score"
        "  FROM unnest(%(woerter)s::text[]) AS w"
        "  JOIN lotse.abschnitt a ON a.text %%> w"
        "  GROUP BY a.id) s"
        " JOIN lotse.abschnitt a ON a.id = s.id JOIN lotse.dokument d ON d.id = a.dokument_id"
        f" WHERE NOT (a.id = ANY(%(aus)s::bigint[])) {_FILTER}"
        " ORDER BY s.score DESC, a.id LIMIT %(k)s"
    )
    with conn.transaction():
        conn.execute(
            "SELECT set_config('pg_trgm.word_similarity_threshold', %s, true)", (str(TRGM_SCHWELLE),)
        )
        zeilen = conn.execute(sql, params).fetchall()
    return [_treffer(z[:-1], float(z[-1]), "trgm") for z in zeilen]


# ---------------------------------------------------------------------------------------------------------
# Dichte Suche
# ---------------------------------------------------------------------------------------------------------

Einbetten = Callable[[list[str]], list[list[float]]]


def _standard_einbetten(texte: list[str]) -> list[list[float]]:
    # batch 1: die Anfrage ist ein einzelner kurzer Text; größere Batches kosten nur Speicher.
    return einbettung.embed(texte, batch_size=1)


# Injizierbar: Tests setzen hier eine Fake-Einbettung ein und laden so nie das Modell.
einbetten: Einbetten = _standard_einbetten


def such_dimension() -> int:
    """Dimension der dichten Suche: EMBED_DIM, sonst SUCH_DIMENSION (256)."""
    roh = os.environ.get("EMBED_DIM", "").strip()
    dim = int(roh) if roh else SUCH_DIMENSION
    if dim not in (768, 512, 256, 128):
        raise ValueError(f"EMBED_DIM muss 768, 512, 256 oder 128 sein, nicht {dim}")
    return dim


def anfrage_vektor(frage: str, dim: int, fn: Einbetten | None = None) -> npt.NDArray[np.float32]:
    """Anfrage einbetten (Präfix laut Modellkarte) und auf dim Dimensionen bringen.

    einbettung.embed liest die Dimension nur aus der Umgebung (EMBED_DIM über dimension()), einen
    Parameter gibt es nicht. os.environ während der Anfrage umzusetzen wäre ein prozessweiter
    Seiteneffekt (Dienst mit Threads). Deshalb: Ist EMBED_DIM gesetzt, liefert embed schon dim
    Dimensionen. Sonst liefert es 768, und hier wird auf dim gekürzt und neu normiert. Das ist dieselbe
    Matryoshka-Kürzung, die sentence-transformers mit truncate_dim und normalize_embeddings rechnet."""
    roh = (fn or einbetten)([einbettung.als_anfrage(frage)])
    v = np.asarray(roh[0], dtype=np.float32)
    if v.shape[0] < dim:
        raise SuchwegNichtVerfuegbar(f"Einbettung hat {v.shape[0]} Dimensionen, die Suche braucht {dim}")
    v = v[:dim]
    norm = float(np.linalg.norm(v))
    if norm == 0.0:
        raise SuchwegNichtVerfuegbar("Einbettung der Anfrage ist der Nullvektor")
    return v / norm


@dataclass(frozen=True)
class DichtIndex:
    """Vektoren und Metadaten für die dichte Suche. Zeile i gehört zu Abschnitt ids[i].

    Gleiche Texte (text_hash) teilen sich eine Matrixzeile: matrix hat eine Zeile je Hash, vektor_zeile
    zeigt je Abschnitt darauf. Filter und Fassungsregel arbeiten über Codes (np.unique) statt Strings."""

    dim: int
    matrix: npt.NDArray[np.float32]  # (Hashes, dim), zeilennormiert
    vektor_zeile: npt.NDArray[np.int64]  # je Abschnitt: Zeile in matrix
    ids: npt.NDArray[np.int64]  # abschnitt.id
    faktor: npt.NDArray[np.float32]  # Abwertung großer Sammeldokumente, wie beim Volltext
    gruppe: npt.NDArray[np.int64]  # Code des Schlüssels (gesetz, art, nummer) bzw. (dokid, id)
    werte: dict[str, tuple[str, ...]]  # Spalte -> Werte zu den Codes (gesetz, art, quelle)
    codes: dict[str, npt.NDArray[np.int64]]  # Spalte -> Code je Abschnitt
    aufgehoben: npt.NDArray[np.bool_]  # je Abschnitt: Dokument ist ein aufgehobener Paragraph

    def _erlaubt(self, spalte: str, erlaubt: Sequence[str]) -> npt.NDArray[np.bool_]:
        codes = [i for i, w in enumerate(self.werte[spalte]) if w in set(erlaubt)]
        return np.isin(self.codes[spalte], codes)

    def maske(self, filter: SuchFilter | None, mit_aufgehobenen: bool = False) -> npt.NDArray[np.bool_]:
        """Zulässige Abschnitte für den Filter; leere Tupel schränken nicht ein. Wie _FILTER: Gesetze
        schränken nur SozDok ein, aufgehobene Paragraphen fallen ohne mit_aufgehobenen weg."""
        maske = np.ones(self.ids.shape[0], dtype=bool) if mit_aufgehobenen else ~self.aufgehoben
        if filter is None:
            return maske
        if filter.gesetze:
            maske &= ~self._erlaubt("quelle", ["sozdok"]) | self._erlaubt("gesetz", filter.gesetze)
        if filter.arten:
            maske &= ~self._erlaubt("quelle", ["sozdok"]) | self._erlaubt("art", filter.arten)
        if filter.quellen:
            maske &= self._erlaubt("quelle", filter.quellen)
        return maske


def baue_index(
    dim: int,
    vektoren: dict[str, npt.NDArray[np.float32]],
    abschnitte: Sequence[tuple[int, str, str, str | None, str | None, str | None, str, float, bool]],
) -> DichtIndex:
    """Index aus Vektoren je text_hash und Abschnitten (id, text_hash, quelle, gesetz, art, nummer, dokid,
    Dokumentzeichen, aufgehoben). Abschnitte ohne Vektor fehlen im Index. Auch für Tests ohne DB."""
    hashes = sorted(vektoren)
    zeile_von = {h: i for i, h in enumerate(hashes)}
    matrix = np.stack([vektoren[h] for h in hashes]).astype(np.float32) if hashes else np.zeros((0, dim))
    normen = np.linalg.norm(matrix, axis=1, keepdims=True)
    matrix = (matrix / np.where(normen == 0, 1, normen)).astype(np.float32)
    mit = sorted((a for a in abschnitte if a[1] in zeile_von), key=lambda a: a[0])
    codes: dict[str, npt.NDArray[np.int64]] = {}
    werte: dict[str, tuple[str, ...]] = {}
    for spalte, pos in (("quelle", 2), ("gesetz", 3), ("art", 4)):
        uniq, inv = np.unique(np.array([a[pos] or "" for a in mit], dtype=object), return_inverse=True)
        werte[spalte], codes[spalte] = tuple(str(x) for x in uniq), inv.astype(np.int64)
    # Gleicher Schlüssel wie _ein_treffer_je_paragraph.
    schluessel = [f"{a[3]}\x1f{a[4] or ''}\x1f{a[5]}" if a[3] and a[5] else f"{a[6]}\x1f{a[0]}" for a in mit]
    _, gruppe = np.unique(np.array(schluessel, dtype=object), return_inverse=True)
    zeichen = np.array([a[7] for a in mit], dtype=np.float64)
    return DichtIndex(
        dim=dim,
        matrix=matrix,
        vektor_zeile=np.array([zeile_von[a[1]] for a in mit], dtype=np.int64),
        ids=np.array([a[0] for a in mit], dtype=np.int64),
        # Wie der Dokumentteil von _ABWERTUNG: 1 / (1 + ln(1 + zeichen / DOKUMENT_REFERENZ)).
        faktor=(1 / (1 + np.log1p(zeichen / DOKUMENT_REFERENZ))).astype(np.float32),
        gruppe=gruppe.astype(np.int64),
        werte=werte,
        codes=codes,
        aufgehoben=np.array([bool(a[8]) for a in mit], dtype=bool),
    )


_ARRAY_ELEMENT = np.dtype([("laenge", ">i4"), ("wert", ">f4")])


def vektor_aus_array_send(daten: bytes, dim: int) -> npt.NDArray[np.float32] | None:
    """real[] im binären Array-Format (array_send) als float32-Vektor; None bei NULL oder falscher Länge.

    Aufbau: ndim, has_null, Element-OID (je int32), je Dimension Größe und Untergrenze (int32), dann je
    Element Länge (int32) und Wert (float4), big-endian. Bei ndim 1 beginnen die Elemente bei Byte 20."""
    if len(daten) < 20 or int.from_bytes(daten[0:4], "big") != 1 or int.from_bytes(daten[4:8], "big"):
        return None
    werte = np.frombuffer(daten, dtype=_ARRAY_ELEMENT, offset=20)["wert"]
    return werte.astype(np.float32) if werte.shape[0] == dim else None


def _vektoren_aus_db(conn: psycopg.Connection, dim: int) -> dict[str, npt.NDArray[np.float32]]:
    # Binär über array_send statt real[] als Python-Listen: spart Millionen Python-floats beim Laden
    # (61.000 Hashes x 256 Werte).
    vektoren: dict[str, npt.NDArray[np.float32]] = {}
    with conn.cursor(binary=True) as cur:
        cur.execute(
            "SELECT text_hash, array_send(v) FROM lotse.vektor WHERE modell = %s AND dim = %s",
            (einbettung.MODELL_ID, dim),
        )
        for text_hash, roh in cur:
            v = vektor_aus_array_send(bytes(roh), dim)
            if v is not None:
                vektoren[str(text_hash)] = v
    return vektoren


def _lade_index(conn: psycopg.Connection, dim: int) -> DichtIndex:
    vektoren = _vektoren_aus_db(conn, dim)
    if not vektoren:
        raise SuchwegNichtVerfuegbar(
            f"lotse.vektor hat keine Vektoren für {einbettung.MODELL_ID} mit {dim} Dimensionen"
            " (Einbettungslauf fehlt oder EMBED_DIM passt nicht)"
        )
    zeilen = conn.execute(
        "SELECT a.id, a.text_hash, d.quelle, d.gesetz, d.art, d.nummer, d.dokid,"
        " coalesce((d.meta->>'zeichen')::float8, length(a.text)),"
        " coalesce((d.meta->>'aufgehoben')::boolean, false)"
        " FROM lotse.abschnitt a JOIN lotse.dokument d ON d.id = a.dokument_id"
    ).fetchall()
    return baue_index(dim, vektoren, zeilen)


_SPERRE = threading.Lock()
_INDEX: dict[tuple[str, str, int], DichtIndex] = {}
_VORHANDEN: dict[tuple[str, str, int], bool] = {}


def _schluessel(conn: psycopg.Connection, dim: int) -> tuple[str, str, int]:
    # conn.info.dsn ohne Passwort: Host, Port, DB und Rolle unterscheiden die Verbindungen.
    return conn.info.dsn, einbettung.MODELL_ID, dim


def index_fuer(conn: psycopg.Connection, dim: int | None = None) -> DichtIndex:
    """Index je Prozess und Verbindung einmal laden (danach aus dem Speicher)."""
    schluessel = _schluessel(conn, dim or such_dimension())
    with _SPERRE:
        if schluessel not in _INDEX:
            _INDEX[schluessel] = _lade_index(conn, schluessel[2])
            _VORHANDEN[schluessel] = True
        return _INDEX[schluessel]


def vektoren_vorhanden(conn: psycopg.Connection, dim: int | None = None) -> bool:
    """Gibt es Vektoren für MODELL_ID und Dimension? Einmal je Prozess und Verbindung geprüft."""
    schluessel = _schluessel(conn, dim or such_dimension())
    with _SPERRE:
        if schluessel not in _VORHANDEN:
            zeile = conn.execute(
                "SELECT EXISTS (SELECT 1 FROM lotse.vektor WHERE modell = %s AND dim = %s)", schluessel[1:]
            ).fetchone()
            _VORHANDEN[schluessel] = bool(zeile and zeile[0])
        return _VORHANDEN[schluessel]


def dicht_rang(
    index: DichtIndex,
    anfrage: npt.NDArray[np.float32],
    n: int,
    filter: SuchFilter | None = None,
    min_gruppen: int = 0,
    mit_aufgehobenen: bool = False,
) -> list[tuple[int, float]]:
    """Abschnitte (id, Score) nach Cosinus mal Dokumentabwertung, beste zuerst, bei Gleichstand kleinere id.

    Der Filter wirkt als Maske VOR der Auswahl. Es sind mindestens n Abschnitte, und so viele mehr, bis
    min_gruppen verschiedene Paragraphen dabei sind (Fassungen belegen später nur einen Platz)."""
    maske = index.maske(filter, mit_aufgehobenen)
    zulaessig = int(maske.sum())
    if zulaessig == 0 or n <= 0:
        return []
    cos = (index.matrix @ anfrage)[index.vektor_zeile]
    # Abwertung wie beim Volltext; negative Cosinus-Werte werden geteilt, damit auch sie sinken.
    score = np.where(cos > 0, cos * index.faktor, cos / index.faktor)
    score = np.where(maske, score, -np.inf)
    anzahl = min(zulaessig, n)
    while True:
        top = np.argpartition(-score, anzahl - 1)[:anzahl] if anzahl < score.shape[0] else np.arange(anzahl)
        top = top[np.lexsort((index.ids[top], -score[top]))]
        top = top[np.isfinite(score[top])]
        if anzahl >= zulaessig or np.unique(index.gruppe[top]).shape[0] >= min_gruppen:
            break
        anzahl = min(zulaessig, anzahl * 2)
    return [(int(index.ids[i]), float(score[i])) for i in top]


def _zeilen(conn: psycopg.Connection, ids: Sequence[int]) -> dict[int, tuple[object, ...]]:
    """Volle Zeilen (_SPALTEN) zu Abschnitts-ids; Texte bleiben so in der DB statt im Speicher."""
    if not ids:
        return {}
    zeilen = conn.execute(
        f"SELECT {_SPALTEN} FROM lotse.abschnitt a JOIN lotse.dokument d ON d.id = a.dokument_id"
        " WHERE a.id = ANY(%s::bigint[])",
        (list(ids),),
    ).fetchall()
    return {int(z[0]): tuple(z) for z in zeilen}


def _als_treffer(
    conn: psycopg.Connection, rang: Sequence[tuple[int, float]], weg: TrefferWeg
) -> list[Treffer]:
    zeilen = _zeilen(conn, [i for i, _ in rang])
    return [_treffer(zeilen[i], score, weg) for i, score in rang if i in zeilen]


def dicht(
    conn: psycopg.Connection, frage: str, k: int, filter: SuchFilter | None, mit_aufgehobenen: bool = False
) -> list[Treffer]:
    index = index_fuer(conn)
    rang = dicht_rang(
        index, anfrage_vektor(frage, index.dim), k * KANDIDATEN_FAKTOR, filter, k, mit_aufgehobenen
    )
    return _ein_treffer_je_paragraph(_als_treffer(conn, rang, "dicht"), k)


def rrf(listen: Sequence[Sequence[int]], k: int = RRF_K) -> list[tuple[int, float]]:
    """Reciprocal Rank Fusion: je Liste 1/(k + Rang), Rang ab 1; beste zuerst, bei Gleichstand kleinere id."""
    summe: dict[int, float] = {}
    for liste in listen:
        for rang, abschnitt_id in enumerate(liste, start=1):
            summe[abschnitt_id] = summe.get(abschnitt_id, 0.0) + 1.0 / (k + rang)
    return sorted(summe.items(), key=lambda p: (-p[1], p[0]))


def hybrid(
    conn: psycopg.Connection, frage: str, k: int, filter: SuchFilter | None, mit_aufgehobenen: bool = False
) -> list[Treffer]:
    """Volltext und dicht je HYBRID_N Abschnitte, RRF auf Abschnittsebene, danach eine Fassung je
    Paragraph. Reicht das nicht für k, ergänzt pg_trgm wie beim Volltext."""
    index = index_fuer(conn)
    voll, lx = volltext_kandidaten(
        conn, frage, max(HYBRID_N, k * KANDIDATEN_FAKTOR), filter, mit_aufgehobenen
    )
    rang_dicht = dicht_rang(index, anfrage_vektor(frage, index.dim), HYBRID_N, filter, k, mit_aufgehobenen)
    fusion = rrf([[t.abschnitt_id for t in voll], [i for i, _ in rang_dicht]])
    bekannt = {t.abschnitt_id: t for t in voll}
    fehlend = _zeilen(conn, [i for i, _ in fusion if i not in bekannt])
    treffer = [
        replace(bekannt[i], score=round(score, 6), weg="hybrid")
        if i in bekannt
        else _treffer(fehlend[i], score, "hybrid")
        for i, score in fusion
        if i in bekannt or i in fehlend
    ]
    ergebnis = _ein_treffer_je_paragraph(treffer, k)
    if len(ergebnis) < k:
        ausschluss = [t.abschnitt_id for t in treffer]
        ergebnis += trigramm(conn, frage, k - len(ergebnis), filter, ausschluss, lx, mit_aufgehobenen)
    return ergebnis


def weg_fuer(conn: psycopg.Connection, weg: Suchweg) -> Suchweg:
    """auto heißt volltext (Entscheid #29 nach gepaartem Dev-Vergleich, docs/plan/uc1/messung-dev.md).

    Mit Anfrage-Erweiterung war hybrid nicht besser als volltext (n=12: 8/12 gegen 9/12 bzw. 10/12,
    gepaart 2 : 4) und braucht das Embedding-Modell im Speicher. hybrid und dicht bleiben ausdrücklich
    wählbar (`weg="hybrid"`), z. B. für Paraphrasen ohne Erweiterung.
    """
    if weg != "auto":
        return weg
    return "volltext"


def _suche(
    conn: psycopg.Connection,
    frage: str,
    k: int,
    filter: SuchFilter | None,
    weg: Suchweg = "volltext",
    mit_aufgehobenen: bool = False,
) -> list[Treffer]:
    weg = weg_fuer(conn, weg)
    if weg == "dicht":
        return dicht(conn, frage, k, filter, mit_aufgehobenen)
    if weg == "hybrid":
        return hybrid(conn, frage, k, filter, mit_aufgehobenen)
    treffer, lx = volltext(conn, frage, k, filter, mit_aufgehobenen)
    if len(treffer) < k:
        ausschluss = [t.abschnitt_id for t in treffer]
        treffer += trigramm(conn, frage, k - len(treffer), filter, ausschluss, lx, mit_aufgehobenen)
    return treffer


def suche(
    frage: str,
    *,
    k: int = 5,
    filter: SuchFilter | None = None,
    weg: Suchweg = "auto",
    conn: psycopg.Connection | None = None,
    mit_aufgehobenen: bool = False,
) -> list[Treffer]:
    """Abschnitte zu einer Frage, beste zuerst. Vertrag: uc1.typen.SucheFn.

    mit_aufgehobenen=True lässt aufgehobene Paragraphen zu (für eine Antwort „wurde aufgehoben“).
    Wirft SuchwegNichtVerfuegbar, wenn weg dicht oder hybrid ist und lotse.vektor keine passenden
    Vektoren hat."""
    if not frage.strip() or k <= 0:
        return []
    if conn is not None:
        return _suche(conn, frage, k, filter, weg, mit_aufgehobenen)
    with verbinde() as eigene:
        return _suche(eigene, frage, k, filter, weg, mit_aufgehobenen)


def _perzentil(werte: Sequence[float], p: float) -> float:
    s = sorted(werte)
    return s[min(len(s) - 1, max(0, math.ceil(p * len(s)) - 1))]


def messe(
    conn: psycopg.Connection, fragen: Sequence[str] = MESSFRAGEN, k: int = 5, weg: Suchweg = "auto"
) -> dict[str, float]:
    """Laufzeit je Anfrage in ms (ein Aufwärmlauf, der auch Matrix und Modell lädt, dann je Frage einmal)."""
    suche(fragen[0], k=k, weg=weg, conn=conn)
    dauer = []
    for frage in fragen:
        start = time.perf_counter()
        suche(frage, k=k, weg=weg, conn=conn)
        dauer.append((time.perf_counter() - start) * 1000)
    return {
        "n": len(dauer),
        "p50_ms": round(_perzentil(dauer, 0.5), 1),
        "p95_ms": round(_perzentil(dauer, 0.95), 1),
    }


def _kurz(text: str, laenge: int = 160) -> str:
    return text if len(text) <= laenge else text[: laenge - 1] + "…"


def cli(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="lotse suche", description="Abschnitte zu einer Frage suchen (#29)")
    parser.add_argument("frage", nargs="?", help="Frage in natürlicher Sprache")
    parser.add_argument("-k", type=int, default=5, help="Zahl der Treffer (Standard 5)")
    parser.add_argument("--gesetz", action="append", default=[], help="nur dieses Gesetz (abkrvo), mehrfach")
    parser.add_argument("--art", action="append", default=[], help="nur diese Gliederungsart (gldart)")
    parser.add_argument(
        "--quelle", action="append", default=[], choices=["sozdok", "formular", "katalog", "eko", "befund"]
    )
    parser.add_argument("--weg", default="auto", choices=["auto", "volltext", "dicht", "hybrid"])
    parser.add_argument("--mit-aufgehobenen", action="store_true", help="aufgehobene §§ zulassen")
    parser.add_argument("--json", action="store_true", help="Treffer als JSON")
    parser.add_argument("--messen", action="store_true", help="p50/p95 über die 12 Messfragen ausgeben")
    args = parser.parse_args(argv)
    if not args.frage and not args.messen:
        parser.error("Frage fehlt")
    quellen: tuple[Quelle, ...] = tuple(args.quelle)
    filt = SuchFilter(gesetze=tuple(args.gesetz), arten=tuple(args.art), quellen=quellen)
    with verbinde() as conn:
        ausgabe: dict[str, object] = {}
        if args.frage:
            try:
                start = time.perf_counter()
                treffer = suche(
                    args.frage,
                    k=args.k,
                    filter=filt,
                    weg=args.weg,
                    conn=conn,
                    mit_aufgehobenen=args.mit_aufgehobenen,
                )
                ms = (time.perf_counter() - start) * 1000
            except SuchwegNichtVerfuegbar as fehler:
                print(f"lotse suche: {fehler}", file=sys.stderr)
                return 2
            ausgabe["treffer"] = [asdict(t) | {"zitat": t.zitierschluessel()} for t in treffer]
            ausgabe["dauer_ms"] = round(ms, 1)
            if not args.json:
                for i, t in enumerate(treffer, start=1):
                    print(f"{i}. [{t.weg} {t.score:.3f}] {t.zitierschluessel()} | {t.kontext}")
                    print(f"   {_kurz(t.text)}")
                print(f"({len(treffer)} Treffer, {ms:.0f} ms)")
        if args.messen:
            try:
                ausgabe["messung"] = m = messe(conn, k=args.k, weg=args.weg)
            except SuchwegNichtVerfuegbar as fehler:
                print(f"lotse suche: {fehler}", file=sys.stderr)
                return 2
            if not args.json:
                print(f"Messung über {m['n']:.0f} Fragen: p50 {m['p50_ms']} ms, p95 {m['p95_ms']} ms")
        if args.json:
            print(json.dumps(ausgabe, ensure_ascii=False, indent=2, default=str))
    return 0
