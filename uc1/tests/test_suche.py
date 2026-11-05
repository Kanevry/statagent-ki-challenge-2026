"""Tests für uc1.suche. Volltext-Tests brauchen die eingelesene DB lotse (Marker daten); dicht, hybrid
und auto laufen mit Fake-Einbettung und injiziertem Index ohne Modell und ohne Vektoren."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import date
from typing import cast

import numpy as np
import psycopg
import pytest

from uc1 import suche as s
from uc1.config import datenbank_url
from uc1.typen import SuchFilter, Treffer

FALL_7 = (
    "Meine Mutter (82) braucht ungefähr 75 Stunden Pflege im Monat. Welche Pflegegeldstufe ist das "
    "und wohin schicke ich den Antrag?"
)


@pytest.fixture
def conn() -> Iterator[psycopg.Connection]:
    try:
        verbindung = psycopg.connect(datenbank_url(), connect_timeout=3)
    except psycopg.OperationalError:
        pytest.skip("DB lotse nicht erreichbar")
    if verbindung.execute("SELECT count(*) FROM lotse.abschnitt").fetchone() == (0,):
        pytest.skip("lotse.abschnitt ist leer (lotse ingest fehlt)")
    with verbindung:
        yield verbindung


@pytest.mark.daten
def test_tsquery_operanden_ueberstehen_sonderzeichen(conn: psycopg.Connection) -> None:
    """Fängt Syntaxfehler in to_tsquery, wenn Frage oder Lexem & | ! ( ) : ' oder \\ enthält."""
    for roh in ["a&b", "x|y", "!nicht", "(klammer)", "a:b", "o'brien", "back\\slash", "'"]:
        conn.execute("SELECT %s::tsquery", (s.tsquery_literal(roh),))
    treffer = s.suche("Krankengeld & | ! ( ) : ' \\ ?", k=3, conn=conn)
    assert treffer, "Sonderzeichen dürfen die Suche nicht leeren"


@pytest.mark.daten
def test_lange_frage_scheitert_nicht_an_und(conn: psycopg.Connection) -> None:
    """Fängt eine UND-Verknüpfung: kein Abschnitt enthält alle Wörter einer langen Bürgerfrage."""
    treffer = s.suche(FALL_7, k=5, conn=conn)
    assert len(treffer) == 5 and all(t.weg == "volltext" for t in treffer)


@pytest.mark.daten
def test_fall_7_bpgg_4_steht_vor_den_uebersichten_in_top_50(conn: psycopg.Connection) -> None:
    """Fängt fehlende Abwertung großer Sammeldokumente: die BPGG-Entscheidungsübersichten (ca. 940 KB)
    dürfen BPGG § 4 nicht überholen. Prüft nur die Reihenfolge in den Top 50, NICHT die AC „BPGG § 4 in
    den Top 5“: Die ist verfehlt; laut messung.md (Blick 2, Fall g07) steht BPGG § 4 bei keiner Variante
    unter den ersten 10 Treffern („–“)."""
    treffer = s.suche(FALL_7, k=50, conn=conn)
    plaetze = {t.zitierschluessel(): i for i, t in reversed(list(enumerate(treffer)))}
    assert "BPGG § 4" in plaetze
    uebersicht = [i for i, t in enumerate(treffer) if (t.art or "") in {"Übersicht", "UEB"}]
    assert all(i > plaetze["BPGG § 4"] for i in uebersicht)


@pytest.mark.daten
def test_filter_wirkt(conn: psycopg.Connection) -> None:
    """Fängt einen Filter (gesetz, art, quelle), der im SQL nicht greift. Gesetz und Art schränken nur
    SozDok ein (PDFs haben beides NULL und bleiben erhalten, Entscheid #29)."""
    filt = SuchFilter(gesetze=("BPGG",), arten=("PARA",))
    treffer = s.suche("Pflegegeld Antrag", k=8, filter=filt, conn=conn)
    sozdok = [t for t in treffer if t.quelle == "sozdok"]
    assert sozdok and all(t.gesetz == "BPGG" and t.art == "PARA" for t in sozdok)
    nur_gesetz = s.suche(
        "Pflegegeld Antrag",
        k=5,
        filter=SuchFilter(gesetze=("BPGG",), arten=("PARA",), quellen=("sozdok",)),
        conn=conn,
    )
    assert nur_gesetz and all(t.gesetz == "BPGG" and t.art == "PARA" for t in nur_gesetz)
    eko = s.suche("Kostenübernahme", k=3, filter=SuchFilter(quellen=("eko",)), conn=conn)
    assert eko and all(t.quelle == "eko" and t.zeile for t in eko)


@pytest.mark.daten
def test_trigramm_rueckfall_findet_tippfehler(conn: psycopg.Connection) -> None:
    """Fängt einen Rückfall, der nichts liefert oder seine Treffer nicht als trgm kennzeichnet."""
    treffer = s.trigramm(conn, "Pflegegeltanspruch", 3, None, [])
    assert treffer and all(t.weg == "trgm" for t in treffer)


@pytest.mark.daten
def test_suche_deterministisch(conn: psycopg.Connection) -> None:
    """Fängt eine Rangfolge, die bei gleichem Score zwischen Läufen wechselt."""
    assert s.suche(FALL_7, k=10, conn=conn) == s.suche(FALL_7, k=10, conn=conn)


# --- dicht, hybrid, auto ohne Modell -------------------------------------------------------------------

DIM = 4


class _Info:
    dsn = "host=fake dbname=lotse"


class _FakeConn:
    """Nur was index_fuer, vektoren_vorhanden und der Cache brauchen; zählt die SQL-Aufrufe."""

    info = _Info()

    def __init__(self, vorhanden: bool = False) -> None:
        self.vorhanden = vorhanden
        self.aufrufe = 0

    def execute(self, *_: object) -> _FakeConn:
        self.aufrufe += 1
        return self

    def fetchone(self) -> tuple[bool]:
        return (self.vorhanden,)


# id -> (text_hash, quelle, gesetz, art, nummer, dokid, inkrafttreten, Vektor)
_KORPUS: dict[int, tuple[str, str, str | None, str | None, str | None, str, date | None, list[float]]] = {
    1: ("h1", "sozdok", "BPGG", "PARA", "4", "bpgg4-2020", date(2020, 1, 1), [1.0, 0.0, 0.0, 0.0]),
    2: ("h2", "sozdok", "BPGG", "PARA", "4", "bpgg4-2024", date(2024, 1, 1), [0.99, 0.1, 0.0, 0.0]),
    3: ("h3", "sozdok", "ASVG", "PARA", "1", "asvg1", date(2024, 1, 1), [0.9, 0.4, 0.0, 0.0]),
    4: ("h4", "sozdok", "ASVG", "PARA", "2", "asvg2", date(2024, 1, 1), [0.8, 0.6, 0.0, 0.0]),
    5: ("h5", "sozdok", "ASVG", "PARA", "3", "asvg3", date(2024, 1, 1), [0.7, 0.7, 0.0, 0.0]),
    6: ("h6", "eko", None, None, None, "eko.csv", None, [0.1, 0.0, 1.0, 0.0]),
    7: ("h7", "eko", None, None, None, "eko.csv", None, [0.0, 0.1, 1.0, 0.0]),
    8: ("h8", "formular", None, None, None, "antrag.pdf", None, [0.0, 0.0, 0.0, 1.0]),
}


def _index(aufgehoben: frozenset[int] = frozenset()) -> s.DichtIndex:
    vektoren = {z[0]: np.array(z[7], dtype=np.float32) for z in _KORPUS.values()}
    abschnitte = [
        (i, z[0], z[1], z[2], z[3], z[4], z[5], 1000.0, i in aufgehoben) for i, z in _KORPUS.items()
    ]
    return s.baue_index(DIM, vektoren, abschnitte)


def _zeile(i: int) -> tuple[object, ...]:
    h, quelle, gesetz, art, nummer, dokid, ikra, _ = _KORPUS[i]
    return (i, dokid, quelle, dokid, gesetz, art, nummer, ikra, None, None, f"Kontext {i}", f"Text {i}")


@pytest.fixture
def ohne_modell(monkeypatch: pytest.MonkeyPatch) -> _FakeConn:
    """Leere Caches, Fake-Einbettung (Richtung von Abschnitt 1, mit 8 Dimensionen wie ein ungekürztes
    Modell), Zeilen aus _KORPUS statt aus der DB."""
    monkeypatch.setattr(s, "_INDEX", {})
    monkeypatch.setattr(s, "_VORHANDEN", {})
    monkeypatch.setattr(
        s, "einbetten", lambda texte: [[1.0, 0.0, 0.0, 0.0, 9.0, 9.0, 9.0, 9.0] for _ in texte]
    )
    monkeypatch.setattr(s, "_zeilen", lambda _conn, ids: {i: _zeile(i) for i in ids if i in _KORPUS})
    # Der Cache-Schlüssel nimmt such_dimension(); der injizierte Testindex selbst hat DIM Dimensionen.
    monkeypatch.setenv("EMBED_DIM", "256")
    return _FakeConn()


def _mit_index(conn: _FakeConn) -> psycopg.Connection:
    s._INDEX[(conn.info.dsn, s.einbettung.MODELL_ID, s.such_dimension())] = _index()
    return cast(psycopg.Connection, conn)


def test_rrf_beide_listen_vor_einer_liste() -> None:
    """Fängt eine Fusion, die nur den besten Einzelrang zählt: Abschnitt 2 steht in beiden Listen auf
    Platz 2 und muss vor Abschnitt 1 (nur Volltext Platz 1) und 4 (nur dicht Platz 1) liegen."""
    fusion = s.rrf([[1, 2, 3], [4, 2, 5]])
    assert fusion[0][0] == 2
    assert fusion[0][1] == pytest.approx(2 / (s.RRF_K + 2))
    assert [i for i, _ in fusion][1:3] == [1, 4]  # Gleichstand: kleinere id zuerst (deterministisch)


def test_dicht_filter_greift_vor_top_n() -> None:
    """Fängt einen Filter, der erst nach der Top-N-Auswahl greift: dann blieben von den 3 besten
    (alle BPGG/ASVG) keine eko-Abschnitte übrig, statt der 2 vorhandenen."""
    index = _index()
    anfrage = np.array([1.0, 0.0, 0.0, 0.0], dtype=np.float32)
    rang = s.dicht_rang(index, anfrage, 3, SuchFilter(quellen=("eko",)))
    assert [i for i, _ in rang] == [6, 7]
    rang = s.dicht_rang(index, anfrage, 2, SuchFilter(gesetze=("ASVG",), arten=("PARA",)))
    assert [i for i, _ in rang] == [3, 4]


def test_auto_ist_volltext_ohne_vektorpruefung(
    monkeypatch: pytest.MonkeyPatch, ohne_modell: _FakeConn
) -> None:
    """Fängt auto, das hybrid wählt (Entscheid #29: auto = volltext) oder dafür die DB nach Vektoren fragt
    und das Embedding-Modell lädt."""
    gerufen: list[str] = []
    monkeypatch.setattr(s, "volltext", lambda *_a: (gerufen.append("volltext"), ([], []))[1])
    monkeypatch.setattr(s, "trigramm", lambda *_a: [])
    conn = cast(psycopg.Connection, ohne_modell)
    s.suche("Krankengeld", conn=conn)
    s.suche("Pflegegeld", conn=conn)
    assert gerufen == ["volltext", "volltext"]
    assert ohne_modell.aufrufe == 0


def test_dicht_ohne_vektoren_meldet_eigene_ausnahme(
    monkeypatch: pytest.MonkeyPatch, ohne_modell: _FakeConn
) -> None:
    """Fängt dicht/hybrid, die ohne Vektoren still auf Volltext ausweichen oder leer zurückgeben."""
    monkeypatch.setattr(s, "_vektoren_aus_db", lambda _conn, _dim: {})
    for weg in ("dicht", "hybrid"):
        with pytest.raises(s.SuchwegNichtVerfuegbar, match="keine Vektoren"):
            s.suche("Krankengeld", weg=weg, conn=cast(psycopg.Connection, ohne_modell))  # type: ignore[arg-type]


def test_keine_doppelte_fassung_desselben_paragraphen(
    monkeypatch: pytest.MonkeyPatch, ohne_modell: _FakeConn
) -> None:
    """Fängt zwei Fassungen von BPGG § 4 (Abschnitte 1 und 2) auf zwei Plätzen, in dicht und hybrid;
    stehen bleiben muss die jüngste Fassung (2024)."""
    conn = _mit_index(ohne_modell)
    voll = [s._treffer(_zeile(i), 1.0 / i, "volltext") for i in (1, 2, 5)]
    monkeypatch.setattr(s, "volltext_kandidaten", lambda *_a: (voll, []))
    for weg in ("dicht", "hybrid"):
        treffer: list[Treffer] = s.suche("Pflegegeld", k=3, weg=weg, conn=conn)  # type: ignore[arg-type]
        schluessel = [t.zitierschluessel() for t in treffer]
        assert len(treffer) == 3 and len(set(schluessel)) == 3, (weg, schluessel)
        assert schluessel[0] == "BPGG § 4" and treffer[0].dokid == "bpgg4-2024"
        assert all(t.weg == weg for t in treffer)
    hybrid = s.suche("Pflegegeld", k=3, weg="hybrid", conn=conn)
    assert hybrid[0].score == pytest.approx(1 / (s.RRF_K + 1) + 1 / (s.RRF_K + 1), abs=1e-6)


def test_256_dimensionen_durch_kuerzen_und_normieren() -> None:
    """Fängt eine Anfrage, die mit 768 Dimensionen gegen eine 256er-Matrix rechnet, nur kürzt ohne neu zu
    normieren oder das Anfrage-Präfix der Modellkarte vergisst."""
    roh = np.arange(1, 769, dtype=np.float32)
    texte: list[str] = []

    def fake(t: list[str]) -> list[list[float]]:
        texte.extend(t)
        return [list(map(float, roh))]

    v = s.anfrage_vektor("Pflegegeld", 256, fake)
    assert v.shape == (256,)
    assert float(np.linalg.norm(v)) == pytest.approx(1.0, abs=1e-6)
    assert np.allclose(v, roh[:256] / np.linalg.norm(roh[:256]))
    assert texte == ["task: search result | query: Pflegegeld"]


def test_such_dimension_standard_256(monkeypatch: pytest.MonkeyPatch) -> None:
    """Fängt eine Suche, die den Adapter-Standard 768 statt 256 nimmt, wenn EMBED_DIM fehlt."""
    monkeypatch.delenv("EMBED_DIM", raising=False)
    assert s.such_dimension() == 256
    monkeypatch.setenv("EMBED_DIM", "768")
    assert s.such_dimension() == 768


@pytest.mark.daten
def test_vektor_aus_array_send(conn: psycopg.Connection) -> None:
    """Fängt einen falschen Versatz oder falsche Byte-Reihenfolge beim binären Laden der Vektoren."""
    with conn.cursor(binary=True) as cur:
        zeile = cur.execute("SELECT array_send(ARRAY[0.5, -1.25, 3, 1e-3]::real[])").fetchone()
    assert zeile is not None
    v = s.vektor_aus_array_send(bytes(zeile[0]), 4)
    assert v is not None and np.allclose(v, [0.5, -1.25, 3, 1e-3])
    assert s.vektor_aus_array_send(bytes(zeile[0]), 3) is None


def test_gesetzesfilter_behaelt_pdfs_und_eko_dicht() -> None:
    """Fängt Bug N2 im dichten Weg: Filter gesetze=ASVG entfernt alle PDFs und EKO (gesetz ist dort NULL).
    Der Gesetzesfilter darf nur SozDok einschränken; quellen schließt weiterhin aus."""
    index = _index()
    anfrage = np.array([0.0, 0.0, 0.5, 0.5], dtype=np.float32)
    ids = {i for i, _ in s.dicht_rang(index, anfrage, 8, SuchFilter(gesetze=("ASVG",)))}
    assert ids == {3, 4, 5, 6, 7, 8}  # BPGG (1, 2) fällt weg, eko (6, 7) und formular (8) bleiben
    nur_sozdok = s.dicht_rang(index, anfrage, 8, SuchFilter(gesetze=("ASVG",), quellen=("sozdok",)))
    assert {i for i, _ in nur_sozdok} == {3, 4, 5}


def test_aufgehobene_fallen_dicht_weg_ausser_mit_aufgehobenen() -> None:
    """Fängt einen dichten Weg, der aufgehobene §§ trotz Kennzeichen rankt (Review D1b) oder sie auch mit
    mit_aufgehobenen=True nicht mehr liefert."""
    index = _index(aufgehoben=frozenset({1, 2}))
    anfrage = np.array([1.0, 0.0, 0.0, 0.0], dtype=np.float32)
    assert [i for i, _ in s.dicht_rang(index, anfrage, 2)] == [3, 4]
    assert [i for i, _ in s.dicht_rang(index, anfrage, 2, mit_aufgehobenen=True)] == [1, 2]


def test_terme_gedeckelt_auf_die_gewichtigsten() -> None:
    """Fängt eine ungedeckelte Anfrage (Review D1c: bis 2 s bei ~40 Termen) und einen Deckel, der die
    seltenen Fachwörter statt der häufigen Füllwörter verwirft."""
    terme = [(f"'t{i:02d}'", float(i), 100 - i) for i in range(30)]
    gedeckelt = s.deckle_terme(terme)
    assert len(gedeckelt) == s.MAX_TERME == 12
    assert {o for o, _, _ in gedeckelt} == {f"'t{i:02d}'" for i in range(18, 30)}
    assert s.deckle_terme(terme[:5]) == terme[:5]


@pytest.mark.daten
def test_gesetzesfilter_behaelt_pdfs_volltext(conn: psycopg.Connection) -> None:
    """Fängt Bug N2 im Volltext: mit gesetze=BPGG kamen 0 PDFs, obwohl Formular und Serviceratgeber
    zum Pflegegeld passen (AC B verlangt ein Angebot mit Seite)."""
    treffer = s.suche(
        "Antrag auf Pflegegeld Formular",
        k=30,
        filter=SuchFilter(gesetze=("BPGG",)),
        weg="volltext",
        conn=conn,
    )
    quellen = {t.quelle for t in treffer}
    assert quellen & {"formular", "katalog"}, quellen
    assert all(t.gesetz in (None, "BPGG") for t in treffer)


@pytest.mark.daten
def test_aufgehobene_fallen_volltext_weg(conn: psycopg.Connection) -> None:
    """Fängt Review D1b: „Kann ich in Gleitpension gehen?“ lieferte ASVG § 253c, GSVG § 131b und BSVG
    § 122b (alle aufgehoben) auf den Rängen 1–3. Mit mit_aufgehobenen=True bleiben sie abrufbar."""
    frage = "Kann ich in Gleitpension gehen?"
    aufgehoben = {
        r[0]
        for r in conn.execute(
            "SELECT a.id FROM lotse.abschnitt a JOIN lotse.dokument d ON d.id = a.dokument_id"
            " WHERE coalesce((d.meta->>'aufgehoben')::boolean, false)"
        ).fetchall()
    }
    ohne = s.suche(frage, k=10, weg="volltext", conn=conn)
    assert ohne and not {t.abschnitt_id for t in ohne} & aufgehoben
    mit = s.suche(frage, k=10, weg="volltext", conn=conn, mit_aufgehobenen=True)
    assert {t.abschnitt_id for t in mit} & aufgehoben
