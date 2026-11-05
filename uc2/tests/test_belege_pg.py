from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any

import psycopg
import pytest

from uc2.belege.einbettung import MockEinbetter
from uc2.belege.extraktion import extrahiere
from uc2.belege.index import indexiere
from uc2.belege.regeln import lade_regeln
from uc2.belege.suche import suche
from uc2.belege.vektoren import bette_extrakt_ein


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
    assert len(treffer) > 1  # Vektor-Kandidaten ohne Volltexttreffer kommen dazu
    for t in treffer:
        assert abs(t.relevanz - (0.7 * max(t.cos, 0.0) + 0.3 * t.ts)) < 1e-12
    assert len({t.artikel_id for t in treffer}) == len(treffer)

    _, frueh = suche(pg_test, "Wartezeit Facharzt", regeln, modus="volltext", stichtag=date(2026, 8, 30))
    assert frueh == []  # Artikel vom 31.08. liegt nach dem Stichtag
