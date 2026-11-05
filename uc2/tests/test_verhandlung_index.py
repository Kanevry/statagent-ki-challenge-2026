"""Index-Belege in der Verhandlung (#44 mit #43): Guard, Maskierung, Standard von `--belege`.

Alle Texte und Namen sind erfunden; die Namensliste liegt in `tmp_path`, also außerhalb des Repos.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any

import psycopg
import pytest

from uc2 import pfade
from uc2.akteure.laden import lade_akteure
from uc2.belege.suche import ZITAT_ZEICHEN
from uc2.verhandlung.belege import (
    BelegFehler,
    FixtureQuelle,
    IndexQuelle,
    lade_namensliste,
    pruefe_freigabe,
)
from uc2.verhandlung.cli import waehle_belege

STICHTAG = date(2026, 9, 30)
NAME = "Erika Beispielfrau"
TITEL = "Mehr Kassenstellen gefordert"
TEXT = (
    "Die Ärztekammer widerspricht der Kasse bei den Kassenstellen in ländlichen Bezirken. "
    "Die Kassenstellen in der Allgemeinmedizin bleiben seit Monaten unbesetzt, weil die Honorare zu niedrig "
    "sind und die Wege in den Bezirken zu lang werden, und die Ärztekammer verlangt deshalb neue Verträge "
    "mit höheren Tarifen, mehr Gruppenpraxen und einer Förderung für junge Ärztinnen und Ärzte, die in "
    "entlegene Gemeinden ziehen wollen. "
    "Das Team um Beispielfrau prüft die Tarife."  # nur die Namensliste erkennt diesen Namen
)


@pytest.fixture
def namensliste(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    pfad = tmp_path / "namen.txt"
    pfad.write_text(f"{NAME}\taerztekammer\nBeispielfrau\taerztekammer\n", encoding="utf-8")
    monkeypatch.setenv("UC2_NAMENSLISTE", str(pfad))
    return pfad


def _index(verbindung: psycopg.Connection[Any]) -> None:
    """Ein erfundener Artikel mit einem Abschnitt, getaggt für die Ärztekammer, ohne Vektoren."""
    verbindung.execute((pfade.SQL / "001_belege.sql").read_text(encoding="utf-8"))
    verbindung.execute(
        "insert into uc2.quelle (md5, datei, ausgabedatum) values ('q1', 'test.pdf', '2026-09-10')"
    )
    verbindung.execute(
        "insert into uc2.artikel (artikel_id, quelle_md5, pdf_seite, artikeldatum, medium, titel) "
        "values ('0123456789ab-001', 'q1', 7, '2026-09-10', 'Testblatt', %s)",
        (TITEL,),
    )
    verbindung.execute(
        "insert into uc2.abschnitt (abschnitt_id, artikel_id, nr, text, text_hash, institutionen) "
        "values ('0123456789ab-001-01', '0123456789ab-001', 1, %s, 'hash-1', %s)",
        (TEXT, ["aerztekammer"]),
    )
    verbindung.commit()


def test_guard_lehnt_index_mit_echtem_provider_ohne_namensliste_ab_und_laesst_ihn_mit_liste_zu(
    pg_test: psycopg.Connection[Any], monkeypatch: pytest.MonkeyPatch, namensliste: Path
) -> None:
    monkeypatch.delenv("UC2_NAMENSLISTE")
    ohne = IndexQuelle(pg_test, namen=lade_namensliste())
    with pytest.raises(BelegFehler, match="nicht maskiert") as fehler:
        pruefe_freigabe(ohne, "claude")
    assert "uc2 namen sammeln --aus-index" in str(fehler.value)
    pruefe_freigabe(ohne, "mock")  # mock darf auch ohne Liste

    monkeypatch.setenv("UC2_NAMENSLISTE", str(namensliste.parent / "fehlt.txt"))
    with pytest.raises(BelegFehler, match="nicht maskiert"):
        pruefe_freigabe(IndexQuelle(pg_test, namen=lade_namensliste()), "azure")

    monkeypatch.setenv("UC2_NAMENSLISTE", str(namensliste))
    mit = IndexQuelle(pg_test, namen=lade_namensliste())
    assert mit.maskiert
    pruefe_freigabe(mit, "claude")


def test_index_quelle_liefert_maskierte_belege_mit_kurzem_zitat(
    pg_test: psycopg.Connection[Any], namensliste: Path
) -> None:
    _index(pg_test)
    akteur = next(a for a in lade_akteure() if a.id == "aerztekammer")
    quelle = IndexQuelle(pg_test, namen=lade_namensliste())
    belege = quelle.belege_fuer(akteur, "Kassenstellen Honorare", 1, STICHTAG)
    assert [b.beleg_id for b in belege] == ["0123456789ab-001-01"]
    b = belege[0]
    for text in (b.titel, b.text_modell, b.text_anzeige, b.zitat):
        assert "Beispielfrau" not in text and "Erika" not in text
    assert 0 < len(b.zitat) <= ZITAT_ZEICHEN
    assert b.pdf_seite == 7 and b.rangteile["faktor_institution"] == 1.5
    assert b.text == b.text_modell  # Prüfung `zitat` vergleicht gegen das, was das Modell sieht
    nur_muster = IndexQuelle(pg_test, namen=None).belege_fuer(akteur, "Kassenstellen Honorare", 1, STICHTAG)
    assert "Beispielfrau" in nur_muster[0].text_modell  # ohne Liste nur Muster: darum der Guard
    chip = b.chip()
    assert "text_modell" not in chip and (chip["monat"], chip["pdf_seite"]) == ("2026-09", 7)


def test_standard_der_belege_index_nur_mit_index_und_namensliste(
    pg_test: psycopg.Connection[Any], monkeypatch: pytest.MonkeyPatch, namensliste: Path
) -> None:
    assert isinstance(waehle_belege(pg_test, None), FixtureQuelle)  # Schema leer: kein Index
    _index(pg_test)
    assert isinstance(waehle_belege(pg_test, None), IndexQuelle)
    monkeypatch.delenv("UC2_NAMENSLISTE")
    assert isinstance(waehle_belege(pg_test, None), FixtureQuelle)
    assert isinstance(waehle_belege(pg_test, "index"), IndexQuelle)  # ausdrücklich gewinnt
