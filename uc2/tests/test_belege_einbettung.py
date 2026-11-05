from __future__ import annotations

import math
from datetime import date

import numpy as np
import pytest

from uc2.belege.einbettung import MockEinbetter, abfrage_text, dokument_text, einbetter
from uc2.belege.regeln import lade_regeln
from uc2.belege.suche import Kandidat, bewerte


def test_mock_deterministisch_und_normalisiert() -> None:
    e = MockEinbetter()
    a = e.einbetten(["Wartezeit beim Facharzt", "anderer Text"], "dokument")
    b = e.einbetten(["Wartezeit beim Facharzt", "anderer Text"], "dokument")
    assert a == b
    assert a[0] != a[1]
    assert all(len(v) == e.dimension() == 768 for v in a)
    assert all(math.isclose(float(np.linalg.norm(v)), 1.0, abs_tol=1e-6) for v in a)


def test_fabrik_nach_umgebung(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("UC2_EINBETTUNG", "mock")
    assert isinstance(einbetter(), MockEinbetter)
    monkeypatch.setenv("UC2_EINBETTUNG", "falsch")
    with pytest.raises(ValueError):
        einbetter()


def test_praefixe() -> None:
    assert dokument_text(None, "x") == "title: none | text: x"
    assert abfrage_text("y") == "task: search result | query: y"


def _kandidat(nr: int, datum: date) -> Kandidat:
    return Kandidat(f"a{nr}-01", f"a{nr}", datum, "Testblatt", "Titel", "Gleicher Text", ts=0.4, cos=0.6)


def test_altersgewicht_september_vor_jaenner() -> None:
    regeln = lade_regeln()
    stichtag = date(2026, 9, 30)
    jaenner, september = date(2026, 1, 15), date(2026, 9, 10)
    nach_stichtag = date(2026, 10, 1)
    kandidaten = [_kandidat(1, jaenner), _kandidat(2, september), _kandidat(3, nach_stichtag)]
    treffer = bewerte(kandidaten, "hybrid", stichtag, regeln, 8)
    assert [t.artikel_id for t in treffer] == ["a2", "a1"]
    erwartet = 0.5 ** ((september - jaenner).days / regeln.halbwertszeit_tage)
    assert math.isclose(treffer[1].rang / treffer[0].rang, erwartet, rel_tol=0, abs_tol=1e-9)
    assert math.isclose(treffer[0].relevanz, 0.7 * 0.6 + 0.3 * 0.4, abs_tol=1e-12)


def test_je_artikel_nur_bester_abschnitt() -> None:
    regeln = lade_regeln()
    schwach = Kandidat("a1-01", "a1", date(2026, 9, 1), "T", "T", "x", ts=0.1, cos=0.0)
    stark = Kandidat("a1-02", "a1", date(2026, 9, 1), "T", "T", "y", ts=0.5, cos=0.0)
    treffer = bewerte([schwach, stark], "volltext", date(2026, 9, 30), regeln, 8)
    assert [t.abschnitt_id for t in treffer] == ["a1-02"]
