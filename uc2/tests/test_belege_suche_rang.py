"""Rang mit Altersgewicht und Institutionsfaktor, nachgerechnet vom Orakel `pruefe_rang.py` (#43).

Kalibrier-Fixture (erfunden): zwei textgleiche Artikel vom Jänner und September 2026, Stichtag 2026-09-30.
"""

from __future__ import annotations

import json
import math
import sys
from datetime import date
from pathlib import Path
from typing import Any, cast

import numpy as np
import psycopg
import pytest

from uc2 import pfade
from uc2.akteure.laden import lade_akteure
from uc2.belege.einbettung import MockEinbetter, dokument_text
from uc2.belege.namen import BLOCK_BEGINN, Namensliste, NamenslisteFehlt, als_datenblock
from uc2.belege.regeln import lade_regeln
from uc2.belege.suche import ZITAT_ZEICHEN, belege_fuer_akteur
from uc2.cli import main

sys.path.insert(0, str(Path(__file__).parent))
import pruefe_rang  # noqa: E402  (Prüfskript ist kein Paket und importiert uc2 nicht)

STICHTAG = date(2026, 9, 30)
JAENNER, SEPTEMBER = date(2026, 1, 15), date(2026, 9, 10)
TITEL = "Kassenstellen bleiben unbesetzt"
TEXT = (
    "Die Kassenstellen in der Allgemeinmedizin bleiben unbesetzt. Die Präsidentin der Ärztekammer, "
    "Maria Musterfrau, fordert höhere Honorare. „Wir brauchen mehr Geld“, sagt Musterfrau."
)


def _kalibrierung(verbindung: psycopg.Connection[Any], tags_jaenner: list[str], vektoren: bool) -> None:
    verbindung.execute((pfade.SQL / "001_belege.sql").read_text(encoding="utf-8"))
    verbindung.execute(
        "insert into uc2.quelle (md5, datei, ausgabedatum) values ('q1', 'test.pdf', '2026-09-10')"
    )
    vektor = np.asarray(MockEinbetter().einbetten([dokument_text(TITEL, TEXT)], "dokument")[0], dtype="<f4")
    for artikel_id, datum, tags in (("jan", JAENNER, tags_jaenner), ("sep", SEPTEMBER, [])):
        verbindung.execute(
            "insert into uc2.artikel (artikel_id, quelle_md5, pdf_seite, artikeldatum, medium, titel) "
            "values (%s, 'q1', 1, %s, 'Testblatt', %s)",
            (artikel_id, datum, TITEL),
        )
        verbindung.execute(
            "insert into uc2.abschnitt (abschnitt_id, artikel_id, nr, text, text_hash, institutionen, "
            "vektor, modell, dim) values (%s, %s, 1, %s, %s, %s, %s, %s, %s)",
            (
                f"{artikel_id}-01",
                artikel_id,
                TEXT,
                f"hash-{artikel_id}",  # textgleich, der Hash ist nur eindeutig gesetzt
                tags,
                vektor.tobytes() if vektoren else None,
                MockEinbetter.modell_id if vektoren else None,
                vektor.shape[0] if vektoren else None,
            ),
        )
    verbindung.commit()


def _suche_json(tmp_path: Path, capsys: pytest.CaptureFixture[str], *argumente: str) -> tuple[Path, Any]:
    capsys.readouterr()
    code = main(
        ["suche", *argumente, "--stichtag", STICHTAG.isoformat(), "--db", "healthpolicy_test", "--json"]
    )
    assert code == 0
    pfad = tmp_path / "treffer.json"
    pfad.write_text(capsys.readouterr().out, encoding="utf-8")
    return pfad, json.loads(pfad.read_text(encoding="utf-8"))


def test_september_vor_jaenner_und_orakel_gruen(
    pg_test: psycopg.Connection[Any],
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("UC2_NAMENSLISTE", raising=False)
    _kalibrierung(pg_test, [], vektoren=False)
    pfad, lauf = _suche_json(tmp_path, capsys, "Kassenstellen Honorare", "--modus", "volltext")
    treffer = lauf["treffer"]
    assert [t["artikel_id"] for t in treffer] == ["sep", "jan"]
    assert treffer[0]["ts"] == treffer[1]["ts"] > 0
    erwartet = 0.5 ** ((SEPTEMBER - JAENNER).days / lade_regeln().halbwertszeit_tage)
    assert math.isclose(treffer[1]["rang"] / treffer[0]["rang"], erwartet, rel_tol=0, abs_tol=1e-9)
    assert "Musterfrau" not in pfad.read_text(encoding="utf-8")  # Anzeige ist maskiert
    assert pruefe_rang.main([str(pfad), "--db", "healthpolicy_test"]) == 0

    lauf["treffer"][1]["rang"] *= 1 + 1e-6  # Orakel erkennt eine Abweichung
    pfad.write_text(json.dumps(lauf), encoding="utf-8")
    assert pruefe_rang.main([str(pfad), "--db", "healthpolicy_test"]) == 1


def test_institutionsfaktor_letzter_faktor_und_belege_maskiert(
    pg_test: psycopg.Connection[Any],
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _kalibrierung(pg_test, ["aerztekammer"], vektoren=True)
    regeln = lade_regeln()
    akteur = next(a for a in lade_akteure() if a.id == "aerztekammer")
    belege = belege_fuer_akteur(
        pg_test,
        akteur,
        "Kassenstellen",
        1,
        stichtag=STICHTAG,
        regeln=regeln,
        einbetter=MockEinbetter(),
        namen=Namensliste(),
    )
    assert [(b.artikel_id, b.faktor_institution) for b in belege] == [("sep", 1.0), ("jan", 1.5)]
    alter = 0.5 ** ((SEPTEMBER - JAENNER).days / regeln.halbwertszeit_tage)
    jan, sep = belege[1], belege[0]
    assert math.isclose(jan.rang, jan.relevanz * jan.gewicht_alter * 1.5, abs_tol=1e-12)
    assert math.isclose(jan.gewicht_alter / sep.gewicht_alter, alter, abs_tol=1e-9)
    assert (jan.beleg_id, jan.monat, jan.datum) == ("jan-01", "2026-01", "2026-01-15")
    assert all(b.rang_vektor is not None for b in belege)  # hybrid mit Mock-Vektoren
    for b in belege:
        assert "Musterfrau" not in b.titel + b.text_modell + b.text_anzeige
        assert "eine Vertreterin der Ärztekammer" in b.text_modell.replace("Eine", "eine")
        assert "„Wir brauchen mehr Geld“" in b.text_modell and "[Zitat]" in b.text_anzeige
    assert als_datenblock(belege).startswith(BLOCK_BEGINN)

    pfad, lauf = _suche_json(tmp_path, capsys, "Kassenstellen", "--akteur", "aerztekammer")
    assert (lauf["modus"], lauf["institution"]) == ("hybrid", "aerztekammer")
    assert pruefe_rang.main([str(pfad), "--db", "healthpolicy_test"]) == 0

    # Online-Grenze (Entscheid Lead 58): nur Zitatfelder, kein ganzer Abschnitt, in API und CLI
    for daten in [*(b.als_dict() for b in belege), *lauf["treffer"]]:
        assert not {"text_modell", "text_anzeige"} & set(daten)
        assert all(len(w) <= ZITAT_ZEICHEN for w in daten.values() if isinstance(w, str)), daten
        assert daten["zitat"] and daten["pdf_seite"] == 1
    assert "Wir brauchen mehr Geld" not in pfad.read_text(encoding="utf-8")
    assert set(belege[0].als_dict(mit_text=True)) - set(belege[0].als_dict()) == {"text_anzeige"}
    assert "„Wir brauchen" in belege[0].als_dict(mit_text=True, fuer_modell=True)["text_modell"]
    with pytest.raises(ValueError):
        belege[0].als_dict(fuer_modell=True)


def test_suche_ohne_namensliste_fail_closed(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("UC2_NAMEN_OHNE_LISTE")  # Testschalter aus conftest aus: echte Regel
    monkeypatch.delenv("UC2_NAMENSLISTE", raising=False)
    capsys.readouterr()
    argumente = ["suche", "Kassenstellen", "--akteur", "aerztekammer", "--db", "healthpolicy_test", "--json"]
    assert main(argumente) == 2
    fehler = capsys.readouterr()
    assert fehler.out == "" and "Traceback" not in fehler.err
    assert "uv run uc2 namen sammeln --aus-index" in fehler.err
    with pytest.raises(NamenslisteFehlt):
        belege_fuer_akteur(
            cast(psycopg.Connection[Any], None),
            next(a for a in lade_akteure() if a.id == "aerztekammer"),
            "Kassenstellen",
            1,
            einbetter=MockEinbetter(),
        )
