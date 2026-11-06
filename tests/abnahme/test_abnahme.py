"""Tests der Abnahme-Werkzeuge (ohne GitLab, ohne Datenbank, ohne Modell).

    uv run pytest -q tests/abnahme/test_abnahme.py

Kern (Review, 05.11. 19:0x): Zwei Läufe auf neuem main mit unverändertem Stand erzeugen genau einen
Kommentar je Kriterium; die Marke enthält weder SHA noch Zeit.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
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


def test_schwaerzen_entfernt_pfade_und_rechnernamen(monkeypatch: pytest.MonkeyPatch) -> None:
    rechner = matrix.re.compile(
        r"\brechner-erfunden\b|nutzer\S*"
    )  # erfundene Namen, echte nur außerhalb des Repos
    monkeypatch.setattr(matrix, "_RECHNER", rechner)
    monkeypatch.setattr(
        matrix, "VERBOTEN", matrix.re.compile(matrix.VERBOTEN.pattern[:-1] + "|" + rechner.pattern + ")")
    )
    text = matrix.schwaerzen(
        "liegt in ~/Projects/x und /Users/nutzer1/b auf rechner-erfunden, nicht 127.0.0.1"
    )
    assert not matrix.VERBOTEN.search(text)
    assert "rechner-erfunden" not in text
    assert "127.0.0.1" in text


def test_bau_db_wird_verweigert(tmp_path: Path) -> None:
    datei = tmp_path / "bau.env"
    datei.write_text("UC3_DATABASE_URL=postgresql://s:s@localhost:5433/statistik\n")
    assert pruefen.db_umgebung(datei)


def test_eigener_arbeitsbaum_wird_nie_zurueckgesetzt() -> None:
    assert not (pruefen.WURZEL / pruefen.MARKE_KLON).exists()
    with pytest.raises(SystemExit, match="eigene Arbeitsbaum ohne Marke"):
        pruefen.zuruecksetzen(pruefen.WURZEL, KOPF, KOPF)


def test_eigener_arbeitsbaum_ohne_marke_ist_kein_ort() -> None:
    with pytest.raises(SystemExit, match="eigene Arbeitsbaum"):
        pruefen.ort_vorbereiten(pruefen.WURZEL, KOPF, KOPF)


def test_pruefklon_als_eigener_ort_wird_nur_geprueft(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Prüfrechner: pruefen.py läuft im Prüf-Klon; mit Marke und passendem Kopf kein Abbruch."""
    git = ["git", "-C", str(tmp_path), "-c", "user.name=t", "-c", "user.email=t@example.org"]
    subprocess.run([*git, "init", "-q"], check=True)
    (tmp_path / "a.txt").write_text("a\n")
    subprocess.run([*git, "add", "a.txt"], check=True)
    subprocess.run([*git, "commit", "-q", "-m", "a"], check=True)
    kopf = subprocess.run([*git, "rev-parse", "HEAD"], capture_output=True, text=True, check=True)
    kopf = kopf.stdout.strip()
    (tmp_path / pruefen.MARKE_KLON).write_text("x\n")
    monkeypatch.setattr(pruefen, "WURZEL", tmp_path)
    pruefen.ort_vorbereiten(tmp_path, kopf, kopf)
    assert (tmp_path / "a.txt").exists()
    with pytest.raises(SystemExit, match="nicht auf main"):
        pruefen.ort_vorbereiten(tmp_path, "0" * 40, kopf)


def test_ordner_ohne_marke_wird_nicht_zurueckgesetzt(tmp_path: Path) -> None:
    with pytest.raises(SystemExit, match="ohne Marke"):
        pruefen.zuruecksetzen(tmp_path, KOPF, KOPF)


def test_verworfener_beleg_zaehlt_nicht(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Ein Beleg aus verworfen.jsonl fällt aus der Matrix, die Laufdatei bleibt unverändert."""
    laeufe = tmp_path / "laeufe"
    laeufe.mkdir()
    lauf = laeufe / "2026-11-05T2011-abc.jsonl"
    beleg = {"pruefer": "lauf 2026-11-05T2011-abc", "zeit": "2026-11-05 20:11"}
    zeilen = [
        {"lauf": "2026-11-05T2011-abc"},
        {"id": "1-1", "stand": "nicht bestanden", **beleg},
        {"id": "1-2", "stand": "bestanden", **beleg},
        {"abgeschlossen": True},
    ]
    lauf.write_text("".join(json.dumps(z) + "\n" for z in zeilen))
    verworfen = tmp_path / "verworfen.jsonl"
    eintrag = {"lauf": "2026-11-05T2011-abc", "ids": ["1-1"], "grund": "x", "wer": "y"}
    verworfen.write_text(json.dumps(eintrag) + "\n")
    monkeypatch.setattr(matrix, "LAEUFE", laeufe)
    monkeypatch.setattr(matrix, "BELEGE", tmp_path / "belege.jsonl")
    monkeypatch.setattr(matrix, "VERWORFEN", verworfen)
    belege = matrix.belege_lesen()
    assert "1-1" not in belege
    assert belege["1-2"][0]["stand"] == "bestanden"


def test_fehlende_sperrliste_warnt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(matrix, "_SPERRDATEI", tmp_path / "gibt-es-nicht")
    assert matrix._sperrnamen() == r"(?!)"
    assert "Sperrliste fehlt" in capsys.readouterr().err


def test_env_datei_ist_eine_echte_leere_datei() -> None:
    """plattform.umgebung verlangt is_file(); /dev/null ließ UC1-Tests im Abzug scheitern (28-1)."""
    pfad = Path(pruefen.UMGEBUNG["KIC_ENV_DATEI"])
    assert pfad.is_file()
    assert pfad.read_text() == ""


def test_alte_abzuege_entfernen_laesst_die_neuesten_und_die_links(tmp_path: Path) -> None:
    # Fängt: Der Aufräumer löscht den laufenden Abzug oder folgt einem Link zu den Daten.
    daten = tmp_path / "daten"
    daten.mkdir()
    (daten / "lieferung.csv").write_text("x")
    ordner = tmp_path / "abzug"
    ordner.mkdir()
    (ordner / "svbox").symlink_to(daten)
    (ordner / "notizen").mkdir()
    for i, name in enumerate(("aaaaaaaaaaaa-git", "bbbbbbbbbbbb-git", "cccccccccccc-git", "dddddddddddd")):
        (ordner / name).mkdir()
        os.utime(ordner / name, (1000 + i, 1000 + i))

    weg = pruefen.alte_abzuege_entfernen(2, ordner)

    assert weg == ["aaaaaaaaaaaa-git", "bbbbbbbbbbbb-git"]
    assert sorted(p.name for p in ordner.iterdir()) == [
        "cccccccccccc-git",
        "dddddddddddd",
        "notizen",
        "svbox",
    ]
    assert (daten / "lieferung.csv").exists()


def test_alte_abzuege_entfernen_schont_den_laufenden_abzug(tmp_path: Path) -> None:
    # Fängt: Ein Lauf auf einem älteren Stand löscht seinen eigenen Abzug.
    for i, name in enumerate(("aaaaaaaaaaaa-git", "bbbbbbbbbbbb-git", "cccccccccccc-git")):
        (tmp_path / name).mkdir()
        os.utime(tmp_path / name, (1000 + i, 1000 + i))

    weg = pruefen.alte_abzuege_entfernen(1, tmp_path, aktuell=tmp_path / "aaaaaaaaaaaa-git")

    assert weg == ["bbbbbbbbbbbb-git"]
    assert (tmp_path / "aaaaaaaaaaaa-git").is_dir()


def test_hand_beleg_wird_nicht_von_der_laufzeile_ueberdeckt(monkeypatch: pytest.MonkeyPatch) -> None:
    # Fängt: Nach dem ersten Lauf steht dessen Zeile vorn, der Hand-Beleg zählt nie wieder.
    monkeypatch.setattr(pruefen.matrix, "veraltet", lambda *a: "")
    k = {"id": "1-1", "hash": "h", "bereich": "uc3"}
    p = {"beschreibung": "Ein Mensch prüft."}
    belege = {
        "1-1": [
            {
                "hash": "h",
                "art": "hand",
                "stand": "bestanden",
                "zeit": "2026-11-06 06:00",
                "pruefer": "Abnahme-Prüfer",
            },
            {"hash": "h", "stand": "nicht geprüft", "zeit": "2026-11-06 07:00", "pruefer": "lauf x"},
        ]
    }
    assert pruefen.hand_teil(p, k, belege, "abc")["stand"] == "bestanden"
    assert pruefen.hand_teil(p, k, {"1-1": belege["1-1"][1:]}, "abc")["stand"] == "nicht geprüft"


def test_schwaerzen_ersetzt_woerter_aus_der_ersatzliste(monkeypatch: pytest.MonkeyPatch) -> None:
    # Fängt: Ein Wort aus einem Issue landet über die Matrix wieder im Repo.
    monkeypatch.setattr(matrix, "_ERSATZ", [(re.compile("altname", re.I), "neuer Name")])
    assert matrix.schwaerzen("Für AltName steht") == "Für neuer Name steht"


def test_schwaerzen_macht_sitzungsnamen_zu_rollen_und_laesst_woerter_stehen() -> None:
    # Fängt: Der Pfad des Lead-Repos aus Issue-Texten landet über die Matrix im Repo.
    assert (
        matrix.schwaerzen("siehe lead-session-orchestrator/.orchestrator/x.md:399; weiter")
        == "siehe <pfad>; weiter"
    )
    # Fängt: Ein Sitzungsname landet über die Matrix im Repo; Wörter oder Dateinamen werden ersetzt.
    rollen = {
        "Abnahme-Prüfer": ["b-abnahme", "b-abnahme-7q"],
        "UI-Prüfung": ["ui-regie-4z"],
        "Lead": [
            "Lead 4z",
            "Lead z9",
            "Lead 7k",
            "Lead q4",
            "Lead 0x",
            "Lead 9w",
            "lead-session-orchestrator-q7",
        ],
        "Lead-Assistenz": ["Assistenz 8y"],
        "Review": ["Bank 6z", "Review-Bank k3"],
        "Lane": [
            "b-e0-folge-9q",
            "b-e0-7z",
            "b-uc3-0z",
            "b-uc3-ui-9k",
            "b-uc3-z1",
            "b-deploy-0q",
            "b-vorfuehrung",
            "b-landing",
            "b-landing-x9",
            "b-uc2-antwort",
            "b-uc1-0x",
            "e5-praesentation-0q",
            "e5-szenen",
            "e5-szenen-9z",
        ],
    }
    for rolle, namen in rollen.items():
        for name in namen:
            assert matrix.schwaerzen(f"Laut {name}, 05.11.") == f"Laut {rolle}, 05.11.", name
    assert matrix.schwaerzen("b-abnahme-7q/messer-x") == "Abnahme-Prüfer/messer-x"
    # Fängt: Steht der Name hinter dem Wort UI-Regie, wird daraus nicht „UI-Regie UI-Prüfung“.
    assert matrix.schwaerzen("gibt die UI-Regie ui-regie-4z frei") == "gibt die UI-Regie frei"

    for bleibt in (
        "Lead an",
        "Lead zu",
        "Assistenz um",
        "Lead im",
        "Lead 05.11. 17:30",
        "docs/plan/uc3/anhang-b-schema.sql",
        "anhang-b-schema",
        "docs/b-uc3-0z/notiz",
        "docs/plan/2026-11-05-prd-e5-praesentation.md",
        "b-tree",
        "b-uc3-notiz.md",
    ):
        assert matrix.schwaerzen(bleibt) == bleibt

    # Der Hash kommt aus dem Rohwortlaut: Das Schwärzen darf keinen Beleg ungültig machen.
    k = matrix.kriterien(
        {
            "iid": 900,
            "title": "Testissue",
            "state": "opened",
            "labels": ["uc3"],
            "description": "- [ ] Regel Lead q4 steht",
        }
    )[0]
    assert k["wortlaut"] == "Regel Lead q4 steht"
    assert k["hash"] == matrix.kriterium_hash("Regel Lead q4 steht")


@pytest.mark.parametrize(
    ("pruefer", "vorschlag"),
    [
        ("Abnahme-Prüfer", False),
        ("lauf x", False),
        ("Abnahme-Prüfer/Mess-Agent", True),
        ("UI-Prüfung", True),
    ],
)
def test_nur_abnahme_pruefer_und_lauf_zaehlen(pruefer: str, vorschlag: bool) -> None:
    # Fängt: Der Beleg eines Mess-Agents oder einer anderen Rolle gilt als bestanden.
    assert matrix.ist_vorschlag({"pruefer": pruefer}) is vorschlag
