from __future__ import annotations

import json
from dataclasses import replace
from datetime import date
from pathlib import Path
from typing import Any

import psycopg
import pytest

from uc2.belege.einbettung import Einbetter, MockEinbetter
from uc2.belege.extraktion import extrahiere, lies_jsonl
from uc2.belege.index import VektorenPassenNicht, indexiere, lade_vektoren
from uc2.belege.regeln import lade_regeln
from uc2.belege.suche import suche
from uc2.belege.vektoren import bette_extrakt_ein, eingabe_texte


@pytest.fixture
def extrakt(tmp_path: Path, ausgabe_text: str) -> Path:
    quelle = tmp_path / "presse"
    quelle.mkdir()
    (quelle / "Pressespiegel vom 01.09.2026.pdf").write_text(ausgabe_text, encoding="utf-8")
    aus = tmp_path / "extrakt"
    extrahiere(quelle, aus, ab=date(2026, 1, 1), prozesse=1, leser=lambda p: p.read_text(encoding="utf-8"))
    return aus


def _zahlen(verbindung: psycopg.Connection[Any]) -> tuple[Any, ...]:
    zeile = verbindung.execute(
        "select (select count(*) from uc2.quelle), (select count(*) from uc2.artikel), "
        "(select count(*) from uc2.abschnitt), (select count(*) from uc2.abschnitt where vektor is not null)"
    ).fetchone()
    assert zeile is not None
    return tuple(zeile)


def test_zweimal_laden_gleiche_zeilen_und_hash(pg_test: psycopg.Connection[Any], extrakt: Path) -> None:
    erst = indexiere(extrakt, pg_test)
    zahlen = _zahlen(pg_test)
    zweit = indexiere(extrakt, pg_test)
    assert erst.inhalt_hash == zweit.inhalt_hash
    assert _zahlen(pg_test) == zahlen == (1, 3, 3, 0)
    assert erst.meldung is not None and "ohne Vektoren" in erst.meldung


def test_suche_volltext_und_hybrid_mit_mock(pg_test: psycopg.Connection[Any], extrakt: Path) -> None:
    regeln = lade_regeln()
    indexiere(extrakt, pg_test)
    modus, treffer = suche(pg_test, "Wartezeit Facharzt", regeln, modus="hybrid", einbetter=MockEinbetter())
    assert modus == "volltext"  # ohne Vektoren: Rückfall

    bette_extrakt_ein(extrakt, MockEinbetter(), batch=2)
    ergebnis = indexiere(extrakt, pg_test)
    assert ergebnis.mit_vektor == 3 and ergebnis.modell == MockEinbetter.modell_id

    modus, treffer = suche(pg_test, "Wartezeit Facharzt", regeln, modus="volltext")
    assert modus == "volltext"
    assert [t.titel for t in treffer] == ["Wartezeit beim Facharzt wird kürzer"]
    assert treffer[0].ts > 0 and treffer[0].rang > 0

    modus, treffer = suche(pg_test, "Wartezeit Facharzt", regeln, modus="hybrid", einbetter=MockEinbetter())
    assert modus == "hybrid"
    # Mock-Kosinus ist Zufall: geprüft werden Vereinigung der Kandidaten und Zusammensetzung der Relevanz.
    nach_titel = {t.titel: t for t in treffer}
    assert nach_titel["Wartezeit beim Facharzt wird kürzer"].ts > 0
    assert nach_titel["Wartezeit beim Facharzt wird kürzer"].rang_volltext == 1
    assert len(treffer) > 1  # Vektor-Kandidaten ohne Volltexttreffer kommen dazu
    for t in treffer:
        erwartet = 0.0
        if t.rang_volltext is not None:
            erwartet += regeln.gewicht_volltext / (regeln.rrf_k + t.rang_volltext)
        if t.rang_vektor is not None:
            erwartet += regeln.gewicht_vektor / (regeln.rrf_k + t.rang_vektor)
        assert abs(t.relevanz - erwartet) < 1e-12
    assert len({t.artikel_id for t in treffer}) == len(treffer)

    _, frueh = suche(pg_test, "Wartezeit Facharzt", regeln, modus="volltext", stichtag=date(2026, 8, 30))
    assert frueh == []  # Artikel vom 31.08. liegt nach dem Stichtag


def test_volltext_oder_findet_teiltreffer_und_nicht(pg_test: psycopg.Connection[Any], extrakt: Path) -> None:
    regeln = lade_regeln()
    indexiere(extrakt, pg_test)
    frage = "Augenarzt Facharzt"  # „Augenarzt“ steht nicht im Fixture, „Facharzt“ im Titel
    _, oder = suche(pg_test, frage, replace(regeln, volltext_verknuepfung="oder"), modus="volltext")
    _, und = suche(pg_test, frage, replace(regeln, volltext_verknuepfung="und"), modus="volltext")
    assert [t.titel for t in oder] == ["Wartezeit beim Facharzt wird kürzer"]
    assert und == []


def test_volltext_oder_mehr_passende_woerter_hoeher(pg_test: psycopg.Connection[Any], extrakt: Path) -> None:
    regeln = replace(lade_regeln(), volltext_verknuepfung="oder")
    indexiere(extrakt, pg_test)
    _, eins = suche(pg_test, "Augenarzt Facharzt", regeln, modus="volltext")
    _, zwei = suche(pg_test, "Facharzt Termin Kassenstellen", regeln, modus="volltext")
    assert 0 < eins[0].ts < zwei[0].ts < 1
    _, sonderzeichen = suche(pg_test, "Facharzt' & | ! :* (", regeln, modus="volltext")
    assert [t.titel for t in sonderzeichen] == ["Wartezeit beim Facharzt wird kürzer"]


def test_lesefehler_loescht_keine_indexierten_artikel(
    pg_test: psycopg.Connection[Any], extrakt: Path, tmp_path: Path
) -> None:
    indexiere(extrakt, pg_test)

    def kaputt(_: Path) -> str:
        raise OSError("vorübergehend nicht lesbar")

    zweiter = tmp_path / "extrakt_lesefehler"
    extrahiere(tmp_path / "presse", zweiter, ab=date(2026, 1, 1), prozesse=1, leser=kaputt)
    assert lies_jsonl(zweiter / "artikel.jsonl") == []
    ergebnis = indexiere(zweiter, pg_test)
    assert _zahlen(pg_test) == (1, 3, 3, 0)
    assert ergebnis.meldung is not None and "Lesefehler" in ergebnis.meldung
    grund = pg_test.execute("select grund from uc2.quelle").fetchone()
    assert grund == (None,)  # Quellzeile des guten Laufs bleibt


def test_vektoren_gleiche_id_anderer_text_bricht_ab(extrakt: Path) -> None:
    bette_extrakt_ein(extrakt, MockEinbetter(), batch=2)
    artikel = lies_jsonl(extrakt / "artikel.jsonl")
    abschnitte = lies_jsonl(extrakt / "abschnitte.jsonl")
    ids = [a["abschnitt_id"] for a in abschnitte]
    matrix, _, meldung = lade_vektoren(extrakt, ids, eingabe_texte(artikel, abschnitte))
    assert matrix is not None and meldung is None

    abschnitte[0] = {**abschnitte[0], "text": abschnitte[0]["text"] + " Neu geschnitten."}
    with pytest.raises(VektorenPassenNicht, match="neu einbetten"):
        lade_vektoren(extrakt, ids, eingabe_texte(artikel, abschnitte))

    meta_pfad = extrakt / "vektoren.json"
    meta = json.loads(meta_pfad.read_text(encoding="utf-8"))
    del meta["eingaben_sha256"]  # Format vor dem Eingabe-Hash
    meta_pfad.write_text(json.dumps(meta), encoding="utf-8")
    with pytest.raises(VektorenPassenNicht, match="neu einbetten"):
        lade_vektoren(extrakt, ids, eingabe_texte(lies_jsonl(extrakt / "artikel.jsonl"), abschnitte))


def test_hybrid_ohne_torch_faellt_auf_volltext_zurueck(
    pg_test: psycopg.Connection[Any], extrakt: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    regeln = lade_regeln()
    aufrufe: list[int] = []

    def ohne_torch() -> Einbetter:
        aufrufe.append(1)
        raise ModuleNotFoundError("No module named 'torch'", name="torch")

    indexiere(extrakt, pg_test)
    modus, _ = suche(pg_test, "Wartezeit Facharzt", regeln, modus="hybrid", einbetter_fabrik=ohne_torch)
    assert (modus, aufrufe) == ("volltext", [])  # ohne Vektoren wird der Einbetter gar nicht gebaut

    bette_extrakt_ein(extrakt, MockEinbetter(), batch=2)
    indexiere(extrakt, pg_test)
    modus, treffer = suche(pg_test, "Wartezeit Facharzt", regeln, modus="hybrid", einbetter_fabrik=ohne_torch)
    assert (modus, aufrufe) == ("volltext", [1])
    assert [t.titel for t in treffer] == ["Wartezeit beim Facharzt wird kürzer"]
    assert "torch fehlt" in capsys.readouterr().err


def test_modell_nicht_im_cache_faellt_auf_volltext_zurueck(
    pg_test: psycopg.Connection[Any], extrakt: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Review !32 Pflicht 7: dimension() lädt das Modell erst bei der Suche; ModellFehlt → volltext."""
    from plattform.embeddings import ModellFehlt

    class OhneCache(MockEinbetter):
        def dimension(self) -> int:
            raise ModellFehlt("Revision nicht im HF-Cache")

    bette_extrakt_ein(extrakt, MockEinbetter(), batch=2)
    indexiere(extrakt, pg_test)
    modus, treffer = suche(
        pg_test, "Wartezeit Facharzt", lade_regeln(), modus="hybrid", einbetter=OhneCache()
    )
    assert modus == "volltext" and treffer
    assert "plattform.embeddings laden" in capsys.readouterr().err


def test_kaputter_vektor_faellt_auf_volltext_zurueck(
    pg_test: psycopg.Connection[Any], extrakt: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    bette_extrakt_ein(extrakt, MockEinbetter(), batch=2)
    indexiere(extrakt, pg_test)
    pg_test.execute(
        "update uc2.abschnitt set vektor = substring(vektor from 1 for 400) "
        "where abschnitt_id = (select min(abschnitt_id) from uc2.abschnitt)"
    )
    modus, _ = suche(pg_test, "Wartezeit Facharzt", lade_regeln(), modus="hybrid", einbetter=MockEinbetter())
    assert modus == "volltext"
    assert "Bytelänge" in capsys.readouterr().err
