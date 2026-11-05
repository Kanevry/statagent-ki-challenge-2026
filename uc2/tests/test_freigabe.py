"""Freigabe des Berichts (PRD S8, U2-2): Kern, API und CLI gegen `healthpolicy_test` (erfundene Namen)."""

from __future__ import annotations

import contextlib
import subprocess
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import psycopg
import pytest
from fastapi.testclient import TestClient
from plattform.protokoll import export_md

from uc2 import db
from uc2.api import erstelle_app
from uc2.api.app import (
    BODY_ZU_GROSS,
    FREIGABE_GESPERRT,
    FREIGABE_PRO_MINUTE,
    FREIGABE_ZU_OFT,
)
from uc2.api.belegfilter import bericht_fuer_ausgabe
from uc2.cli import main
from uc2.verhandlung.belege import FixtureQuelle
from uc2.verhandlung.bericht import bericht
from uc2.verhandlung.fall import lade_fall
from uc2.verhandlung.freigabe import NAME_UNGUELTIG, FreigabeFehler, entscheide
from uc2.verhandlung.lauf import Laufoptionen, Verhandlung
from uc2.verhandlung.speicher import ddl_anwenden, neuer_fall, schreibe_freigabe

TEST_DB = "healthpolicy_test"
NAME = "Maria Beispiel"
"""Erfundener Name; „Musterfrau“ ginge nicht, `pruefe_name` lehnt „muster“ als Platzhalter ab."""


@pytest.fixture(autouse=True)
def umgebung(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("PLATTFORM_PROTOKOLL", str(tmp_path / "modellaufrufe.jsonl"))
    monkeypatch.delenv("KIC_ONLINE_LESEND", raising=False)
    monkeypatch.delenv("KIC_ONLINE", raising=False)
    monkeypatch.delenv("UC2_MOCK_KAPUTT", raising=False)
    monkeypatch.setenv("UC2_DATABASE_URL", "")
    monkeypatch.setenv("UC2_DB", TEST_DB)


def _verbinde() -> psycopg.Connection[Any]:
    return db.verbinde(TEST_DB, autocommit=True)


@pytest.fixture
def sauberes_protokoll(pg_test: psycopg.Connection[Any]) -> None:
    """`pg_test` leert nur das Schema `uc2`; Protokollzeilen früherer Läufe tragen dieselben Fall-Nummern."""
    with _verbinde() as v, contextlib.suppress(psycopg.errors.UndefinedTable):
        v.execute(
            "delete from meta.freigabe where protokoll_id in (select id from meta.protokoll where uc = 'uc2')"
        )
        v.execute("delete from meta.protokoll where uc = 'uc2' and ref like 'uc2/fall/%'")


@pytest.fixture
def fertig(pg_test: psycopg.Connection[Any], sauberes_protokoll: None) -> int:
    optionen = Laufoptionen(provider="mock", quelle=FixtureQuelle())
    return Verhandlung(pg_test, lade_fall("wartezeiten"), optionen).fuehre_aus()


@pytest.fixture
def laufend(pg_test: psycopg.Connection[Any], sauberes_protokoll: None) -> int:
    ddl_anwenden(pg_test)
    return neuer_fall(
        pg_test,
        fall_name="wartezeiten",
        frage="Erfundene Frage",
        provider="mock",
        belegquelle="fixture",
        modelle={},
        stichtag="2026-09-01",
    )


@pytest.fixture
def client() -> Iterator[TestClient]:
    with TestClient(erstelle_app(verbinde=_verbinde)) as c:
        yield c


def _protokoll(fall_id: int) -> list[tuple[Any, ...]]:
    with _verbinde() as v:
        return v.execute(
            "select akteur, name, status, uc from meta.protokoll where ref = %s order by id",
            (f"uc2/fall/{fall_id}",),
        ).fetchall()


def _meta_freigaben(fall_id: int) -> list[tuple[Any, ...]]:
    """Zeilen in `meta.freigabe` (Vertrag P) zu einem Fall, mit der Protokollzeile verbunden."""
    with _verbinde() as v:
        return v.execute(
            "select f.name, f.entscheidung, f.begruendung, f.objekt_typ, f.objekt_ref,"
            " f.zeitpunkt is not null, p.status, p.id = f.protokoll_id"
            " from meta.freigabe f join meta.protokoll p on p.id = f.protokoll_id"
            " where f.objekt_ref = %s order by f.id",
            (f"uc2/fall/{fall_id}",),
        ).fetchall()


def test_freigabe_eines_fertigen_falls_erscheint_im_bericht_und_im_protokoll(
    fertig: int, client: TestClient
) -> None:
    assert client.get(f"/faelle/{fertig}").json()["freigabe"] is None
    antwort = client.post(
        f"/faelle/{fertig}/freigabe", json={"name": f"  {NAME} ", "entscheidung": "freigegeben"}
    )
    assert antwort.status_code == 200
    zeitpunkt = antwort.json()["zeitpunkt"]
    frei = client.get(f"/faelle/{fertig}").json()["freigabe"]
    assert frei == {"name": NAME, "zeit": zeitpunkt, "entscheidung": "freigegeben", "begruendung": None}
    assert _protokoll(fertig) == [("mensch", NAME, "freigegeben", "uc2")]
    # Vertrag P: genau eine Zeile in meta.freigabe, ja, objekt_typ antwort, Bezug auf den Fall
    assert _meta_freigaben(fertig) == [
        (NAME, "ja", None, "antwort", f"uc2/fall/{fertig}", True, "freigegeben", True)
    ]
    # endgültig: eine zweite Entscheidung wird abgelehnt
    zweit = client.post(
        f"/faelle/{fertig}/freigabe",
        json={"name": "Hans Beispiel", "entscheidung": "abgelehnt", "begruendung": "x"},
    )
    assert zweit.status_code == 409
    assert client.get(f"/faelle/{fertig}").json()["freigabe"]["name"] == NAME
    assert len(_meta_freigaben(fertig)) == 1  # die abgelehnte zweite Entscheidung schreibt nichts


def test_ablehnung_braucht_begruendung_und_steht_im_bericht(fertig: int, client: TestClient) -> None:
    ohne = client.post(f"/faelle/{fertig}/freigabe", json={"name": NAME, "entscheidung": "abgelehnt"})
    assert ohne.status_code == 422
    assert client.get(f"/faelle/{fertig}").json()["freigabe"] is None
    mit = client.post(
        f"/faelle/{fertig}/freigabe",
        json={"name": NAME, "entscheidung": "abgelehnt", "begruendung": "Zahlen\nzu dünn"},
    )
    assert mit.status_code == 200
    frei = client.get(f"/faelle/{fertig}").json()["freigabe"]
    assert (frei["entscheidung"], frei["begruendung"]) == ("abgelehnt", "Zahlen zu dünn")
    assert _protokoll(fertig) == [("mensch", NAME, "abgelehnt", "uc2")]
    assert _meta_freigaben(fertig) == [
        (NAME, "nein", "Zahlen zu dünn", "antwort", f"uc2/fall/{fertig}", True, "abgelehnt", True)
    ]


@pytest.mark.parametrize("name", ["Team", "Das Team", "Maria", "Admin Beispiel", "", "Maria\x00 Beispiel"])
def test_ungueltige_namen_ergeben_422_mit_festem_satz(fertig: int, client: TestClient, name: str) -> None:
    antwort = client.post(f"/faelle/{fertig}/freigabe", json={"name": name, "entscheidung": "freigegeben"})
    assert antwort.status_code == 422
    assert antwort.json() == {"detail": NAME_UNGUELTIG}
    assert client.get(f"/faelle/{fertig}").json()["freigabe"] is None
    assert _protokoll(fertig) == []
    assert _meta_freigaben(fertig) == []


def test_laufender_fall_wird_abgelehnt(laufend: int, client: TestClient) -> None:
    antwort = client.post(f"/faelle/{laufend}/freigabe", json={"name": NAME, "entscheidung": "freigegeben"})
    assert antwort.status_code == 409
    assert client.get(f"/faelle/{laufend}").json()["freigabe"] is None
    assert _protokoll(laufend) == []
    assert _meta_freigaben(laufend) == []


def test_unbekannter_fall_und_falsche_anfrage(fertig: int, client: TestClient) -> None:
    assert (
        client.post("/faelle/424242/freigabe", json={"name": NAME, "entscheidung": "freigegeben"}).status_code
        == 404
    )
    pfad = f"/faelle/{fertig}/freigabe"
    for kaputt in (
        {"name": NAME, "entscheidung": "vielleicht"},
        {"name": NAME, "entscheidung": "freigegeben", "fremd": 1},
        {"entscheidung": "freigegeben"},
    ):
        antwort = client.post(pfad, json=kaputt)
        # feste Sätze, die Eingabe wird nicht zurückgegeben
        assert antwort.status_code == 422 and "vielleicht" not in antwort.text
    assert client.post(pfad, content=b"kein json").status_code == 422


def test_online_demo_sperrt_vor_dem_body(
    fertig: int, client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("KIC_ONLINE_LESEND", "1")
    # Der Body ist kein JSON und riesig: die Sperre greift vorher.
    antwort = client.post(f"/faelle/{fertig}/freigabe", content=b"x" * 100_000)
    assert (antwort.status_code, antwort.json()) == (403, {"detail": FREIGABE_GESPERRT})
    assert client.get(f"/faelle/{fertig}").json()["freigabe"] is None


def test_body_grenze_413(fertig: int, client: TestClient) -> None:
    antwort = client.post(f"/faelle/{fertig}/freigabe", content=b"x" * 5000)
    assert (antwort.status_code, antwort.json()) == (413, {"detail": BODY_ZU_GROSS})


def test_ratenlimit_je_ip_und_minute(fertig: int) -> None:
    jetzt = [1000.0]
    with TestClient(erstelle_app(verbinde=_verbinde, uhr=lambda: jetzt[0])) as c:
        pfad = f"/faelle/{fertig}/freigabe"
        falsch = {"name": "Team", "entscheidung": "freigegeben"}
        assert [c.post(pfad, json=falsch).status_code for _ in range(FREIGABE_PRO_MINUTE)] == [
            422
        ] * FREIGABE_PRO_MINUTE
        zu_oft = c.post(pfad, json=falsch)
        assert (zu_oft.status_code, zu_oft.json()) == (429, {"detail": FREIGABE_ZU_OFT})
        jetzt[0] += 60.0
        assert c.post(pfad, json=falsch).status_code == 422


def test_kern_wirft_feste_saetze(fertig: int) -> None:
    with _verbinde() as v:
        with pytest.raises(FreigabeFehler) as fehler:
            entscheide(v, fertig, "Team", "freigegeben")
        assert fehler.value.art == "name" and str(fehler.value) == NAME_UNGUELTIG
        with pytest.raises(FreigabeFehler) as fehler:
            entscheide(v, fertig, NAME, "abgelehnt", "   ")
        assert fehler.value.art == "begruendung"


def test_cli_gibt_frei_und_lehnt_team_ab(fertig: int, capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["freigabe", str(fertig), "--name", "Team"]) == 2
    assert "Fehler:" in capsys.readouterr().err
    assert main(["freigabe", str(fertig), "--name", NAME]) == 0
    assert capsys.readouterr().out.startswith(f"Freigegeben von {NAME}, ")
    with _verbinde() as v:
        assert bericht(v, fertig)["freigabe"]["name"] == NAME
    assert main(["freigabe", str(fertig), "--name", NAME]) == 1  # schon entschieden


def test_cli_ablehnen_mit_begruendung(fertig: int, capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["freigabe", str(fertig), "--name", NAME, "--ablehnen"]) == 2
    capsys.readouterr()
    assert (
        main(["freigabe", str(fertig), "--name", NAME, "--ablehnen", "--begruendung", "Zu wenig Belege"]) == 0
    )
    assert capsys.readouterr().out.startswith(f"Abgelehnt von {NAME}, ")


def test_ablehnung_steht_in_protokoll_md_unter_ablehnungen(fertig: int, tmp_path: Path) -> None:
    """Ohne die Zeile in `meta.freigabe` fehlten UC2-Ablehnungen im Abschnitt „Ablehnungen“ (Vertrag P)."""
    repo = tmp_path / "leeres-repo"
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    with _verbinde() as v:
        entscheide(v, fertig, NAME, "abgelehnt", "Zahlen zu dünn")
        text = export_md(v, repo, "uc2")
    ablehnungen = text.split("## Ablehnungen", 1)[1]
    assert NAME in ablehnungen and "Zahlen zu dünn" in ablehnungen and f"Fall {fertig}" in ablehnungen


def test_schreiben_braucht_autocommit_ohne_offene_transaktion(fertig: int) -> None:
    with db.verbinde(TEST_DB, autocommit=False) as v, pytest.raises(ValueError, match="autocommit"):
        schreibe_freigabe(v, fertig, NAME, "freigegeben", None, "wartezeiten")
    with _verbinde() as v:
        v.execute("begin")
        with pytest.raises(ValueError, match="autocommit"):
            schreibe_freigabe(v, fertig, NAME, "freigegeben", None, "wartezeiten")
        v.execute("rollback")
    assert _meta_freigaben(fertig) == []


def _entscheide_beide(client: TestClient, fall_id: int) -> None:
    antwort = client.post(
        f"/faelle/{fall_id}/freigabe",
        json={"name": NAME, "entscheidung": "abgelehnt", "begruendung": "Zahlen zu dünn"},
    )
    assert antwort.status_code == 200


@pytest.mark.parametrize("schalter", ["KIC_ONLINE", "KIC_ONLINE_LESEND"])
def test_oeffentlich_steht_nur_entscheidung_und_zeit(
    fertig: int, client: TestClient, monkeypatch: pytest.MonkeyPatch, schalter: str
) -> None:
    """Personenschutz: online weder Name noch Begründung, lokal beides."""
    _entscheide_beide(client, fertig)
    lokal = client.get(f"/faelle/{fertig}").json()["freigabe"]
    assert lokal["name"] == NAME and lokal["begruendung"] == "Zahlen zu dünn"
    monkeypatch.setenv(schalter, "1")
    online = client.get(f"/faelle/{fertig}").json()["freigabe"]
    assert online == {"entscheidung": "abgelehnt", "zeit": lokal["zeit"]}
    assert NAME not in client.get(f"/faelle/{fertig}").text
    assert "dünn" not in client.get(f"/faelle/{fertig}").text
    monkeypatch.setenv(schalter, "0")
    assert client.get(f"/faelle/{fertig}").json()["freigabe"] == lokal


def test_ausgabefilter_laesst_offene_und_fehlende_freigabe_in_ruhe() -> None:
    offen = {"fall": {"fall_id": 1}, "freigabe": None}
    assert bericht_fuer_ausgabe(offen, anonym=True) == offen
    assert bericht_fuer_ausgabe({"fall": {}}, anonym=True) == {"fall": {}}
    frei = {"freigabe": {"name": NAME, "zeit": "z", "entscheidung": "freigegeben", "begruendung": None}}
    oeffentlich = {"freigabe": {"zeit": "z", "entscheidung": "freigegeben"}}
    assert bericht_fuer_ausgabe(frei, anonym=True) == oeffentlich
    assert bericht_fuer_ausgabe(frei, anonym=False) == frei
