"""Tests der Abnahme-Werkzeuge (ohne GitLab, ohne Datenbank, ohne Modell).

    uv run pytest -q tests/abnahme/test_abnahme.py

Kern (Review-Bank 4d, 05.11. 19:0x): Zwei Läufe auf neuem main mit unverändertem Stand erzeugen genau einen
Kommentar je Kriterium; die Marke enthält weder SHA noch Zeit.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import matrix  # noqa: E402
import pruefen  # noqa: E402

KOPF = matrix.git("rev-parse", "HEAD").stdout.strip()


class GitLabAttrappe:
    """Ein Issue im Speicher; zählt geschriebene Kommentare."""

    def __init__(self, beschreibung: str) -> None:
        self.issue = {
            "iid": 900,
            "title": "Testissue",
            "state": "opened",
            "labels": ["uc3"],
            "description": beschreibung,
        }
        self.notizen: list[dict] = []

    def lesen(self, pfad: str, versuche: int = 3) -> object:
        return self.notizen if "/notes" in pfad else dict(self.issue)

    def schreiben(self, methode: str, pfad: str, feld: str, wert: str, versuche: int = 3) -> None:
        if feld == "description":
            self.issue["description"] = wert
        else:
            self.notizen.append({"body": wert})


@pytest.fixture
def gitlab(monkeypatch: pytest.MonkeyPatch) -> GitLabAttrappe:
    g = GitLabAttrappe(
        "### Messbare Abnahmen\n\n- [ ] **AC1:** Die Zahl stimmt.\n- [ ] **AC2:** Die Datei fehlt nicht.\n"
    )
    monkeypatch.setattr(matrix, "glab_json", g.lesen)
    monkeypatch.setattr(matrix, "glab_schreiben", g.schreiben)
    monkeypatch.setattr(matrix, "_ZIEL", KOPF)
    monkeypatch.setattr(matrix, "_ENTSCHEIDE", {})
    return g


def beleg(k: dict, stand: str, zeit: str, **mehr: str) -> dict:
    return {
        "id": k["id"],
        "hash": k["hash"],
        "stand": stand,
        "befehl": "echo 1",
        "ausgabe": "1",
        "grund": mehr.get("grund", "gemessen"),
        "sha": KOPF[:12],
        "zeit": zeit,
        "pruefer": f"lauf {zeit}",
        "pfade": ["tests/abnahme/orakel"],
    }


def test_zwei_laeufe_gleicher_stand_ein_haken_kommentar(gitlab: GitLabAttrappe) -> None:
    k = matrix.alle_kriterien([gitlab.issue])[0]
    assert k["id"] == "900-AC1"
    for zeit in ("2026-11-05 19:00", "2026-11-05 20:00"):  # zwei Läufe, neue Zeit, gleicher Stand
        belege = {k["id"]: [beleg(k, "bestanden", zeit)]}
        assert matrix.abhaken(k["id"], belege, ja=True) == 0
    haken = [n for n in gitlab.notizen if "abnahme-haken:" in n["body"]]
    assert len(haken) == 1
    assert KOPF[:12] not in haken[0]["body"].split("<!--")[-1]
    assert "19:00" not in haken[0]["body"].split("<!--")[-1]
    assert "- [x] **AC1:**" in gitlab.issue["description"]


def test_zwei_laeufe_gleicher_befund_ein_befund_kommentar(gitlab: GitLabAttrappe) -> None:
    zeilen = matrix.alle_kriterien([gitlab.issue])
    k = zeilen[1]
    for zeit, grund in (
        ("2026-11-05 19:00", "Exit 1 statt 0, 1.52s"),
        ("2026-11-05 20:00", "Exit 1 statt 0, 1.71s"),
    ):
        belege = {k["id"]: [beleg(k, "nicht bestanden", zeit, grund=grund)]}
        matrix.befunde(zeilen, belege, None, ja=True)
    assert len([n for n in gitlab.notizen if "abnahme-befund:" in n["body"]]) == 1


def test_beleg_zum_alten_wortlaut_verdraengt_den_aktuellen_nicht(gitlab: GitLabAttrappe) -> None:
    k = matrix.alle_kriterien([gitlab.issue])[0]
    aktuell = beleg(k, "bestanden", "2026-11-05 19:00")
    alt = beleg(k, "nicht geprüft", "2026-11-05 19:30") | {"hash": "0000000000"}
    assert matrix.beleg_fuer(k, {k["id"]: [aktuell, alt]}) is aktuell


def test_teil_pruefsatz_ergibt_nie_bestanden() -> None:
    p = {"deckung": "teil", "erwartet": ["^ok$"]}
    assert pruefen.urteil(p, 0, "ok\n")[0] == "nicht geprüft"
    assert pruefen.urteil(p, 0, "nein\n")[0] == "nicht bestanden"


def test_lauf_fehler_ist_kein_befund() -> None:
    p = {"erwartet": ["^ok$"]}
    assert pruefen.urteil(p, 124, "")[0] == "nicht geprüft"
    assert pruefen.urteil(p, 1, "", "psycopg.OperationalError: connection refused")[0] == "nicht geprüft"


def test_durchfaller_passt_nie_auf_verankerte_testzahl() -> None:
    p = {"erwartet": ["(^|= )\\d+ passed"]}
    assert pruefen.urteil(p, 0, "1 failed, 23 passed in 2s\n")[0] == "nicht bestanden"
    assert pruefen.urteil(p, 0, "24 passed in 2s\n")[0] == "bestanden"


@pytest.mark.parametrize(
    "befehl",
    [
        "STATAGENT_STARTPAKET=<Pfad zu svbox/uc3> pytest",
        "psql x -c 'select 1' (erwartet 392284)",
        "DB_PORT=5433 docker compose up -d",
    ],
)
def test_ungueltige_pruefsaetze(befehl: str) -> None:
    assert pruefen.pruefsatz_fehler({"id": "1-1", "hash": "x", "befehl": befehl})


def test_html_kommentar_ist_kein_platzhalter() -> None:
    assert not pruefen.pruefsatz_fehler(
        {"id": "1-1", "hash": "x", "befehl": "grep -c '<!-- notizen -->' a.md"}
    )


def test_schwaerzen_entfernt_pfade_und_rechnernamen() -> None:
    text = matrix.schwaerzen("liegt in ~/Projects/x und /Users/a/b auf m5-remote bzw. M4, nicht 127.0.0.1")
    assert not matrix.VERBOTEN.search(text)
    assert "127.0.0.1" in text


def test_bau_db_wird_verweigert(tmp_path: Path) -> None:
    datei = tmp_path / "bau.env"
    datei.write_text("UC3_DATABASE_URL=postgresql://s:s@localhost:5433/statistik\n")
    assert pruefen.db_umgebung(datei)


def test_eigener_arbeitsbaum_wird_nie_zurueckgesetzt() -> None:
    with pytest.raises(SystemExit, match="eigene Arbeitsbaum"):
        pruefen.zuruecksetzen(pruefen.WURZEL, KOPF, KOPF)


def test_ordner_ohne_marke_wird_nicht_zurueckgesetzt(tmp_path: Path) -> None:
    with pytest.raises(SystemExit, match="keine Marke"):
        pruefen.zuruecksetzen(tmp_path, KOPF, KOPF)
