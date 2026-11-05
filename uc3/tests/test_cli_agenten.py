"""CLI der Agenten (#15): `uc3 agent`, `vorschlag zeigen`, `freigabe`, `ablehnen`.

Geprüft wird nur, was die CLI hinzufügt: Verdrahtung, Ausgabe, Exit-Code und saubere Fehlermeldungen ohne
Traceback. Das Verhalten der Agenten selbst prüfen test_agenten.py und test_agenten_freigabe.py.
Kein echtes Modell (Fake), Git nur in einem Wegwerf-Repo unter tmp_path (nie das echte Repo).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from plattform.llm import ProviderFehler
from test_agenten import DV_FD, fake_dv_fd
from test_agenten_freigabe import NAME, git, r6_vorschlag
from typer.testing import CliRunner

from statagent import cli, konfig
from statagent.agenten import plattform_bruecke
from statagent.agenten.vorschlag import vorschlag_schema_einrichten
from statagent.db import Verbindung, verbinden

runner = CliRunner()


@pytest.fixture
def agent_db(conn: Verbindung, arbeits_db: str, monkeypatch: pytest.MonkeyPatch) -> Verbindung:
    """Die CLI verbindet sich mit der Wegwerf-DB des Tests statt mit UC3_DATABASE_URL."""
    vorschlag_schema_einrichten(conn)
    monkeypatch.setattr(cli, "verbinden", lambda: verbinden(arbeits_db))
    return conn


@pytest.fixture
def wegwerf_repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Freigabe-Commits landen hier, nie im echten Repo (konfig.REPO_WURZEL wird umgebogen)."""
    pfad = tmp_path / "repo"
    pfad.mkdir()
    git(pfad, "init", "-q", "-b", "main")
    for schluessel, wert in (
        ("user.name", "Test Lauf"),
        ("user.email", "test@example.org"),
        ("commit.gpgsign", "false"),
        ("core.hooksPath", str(pfad / ".git" / "keine-hooks")),
    ):
        git(pfad, "config", schluessel, wert)
    git(pfad, "commit", "-q", "--allow-empty", "-m", "Start")
    monkeypatch.setattr(konfig, "REPO_WURZEL", pfad)
    return pfad


def _ohne_traceback(ergebnis: Any) -> None:
    assert ergebnis.exit_code == 1
    assert isinstance(ergebnis.exception, SystemExit)  # sauber beendet, keine durchgereichte Ausnahme


# Fehler, den der Test fängt: `agent` ruft die Laufzeit nicht auf oder verschweigt ID und nächsten Schritt.
def test_agent_legt_vorschlag_an_und_nennt_naechsten_schritt(
    agent_db: Verbindung, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(plattform_bruecke, "lade_complete", fake_dv_fd)
    ergebnis = runner.invoke(cli.app, ["agent", DV_FD])
    assert ergebnis.exit_code == 0, ergebnis.output
    z = agent_db.execute("SELECT max(id) AS id FROM meta.vorschlag").fetchone()
    assert z is not None and z["id"] is not None
    assert f"Vorschlag uc3/{z['id']}" in ergebnis.output
    assert "Ziel-Regelsatz v2" in ergebnis.output
    assert f"uc3 vorschlag zeigen {z['id']}" in ergebnis.output


# Fehler: ein nicht erreichbares Modell endet mit Traceback statt mit Meldung und Exit 1.
def test_agent_ohne_modell_endet_sauber(agent_db: Verbindung, monkeypatch: pytest.MonkeyPatch) -> None:
    def kein_modell(*_: Any, **__: Any) -> Any:
        raise ProviderFehler("kein Provider hat geantwortet")

    monkeypatch.setattr(plattform_bruecke, "lade_complete", lambda: kein_modell)
    ergebnis = runner.invoke(cli.app, ["agent", DV_FD])
    _ohne_traceback(ergebnis)
    assert "Modell nicht erreichbar" in ergebnis.output


# Fehler: `vorschlag zeigen` zeigt den Regel-Diff nicht (alt → neu) oder fehlt als Befehl.
def test_vorschlag_zeigen_mit_diff(agent_db: Verbindung) -> None:
    vid = r6_vorschlag(agent_db)
    ergebnis = runner.invoke(cli.app, ["vorschlag", "zeigen", str(vid)])
    assert ergebnis.exit_code == 0, ergebnis.output
    assert '- parameter.qualifikation = "code"' in ergebnis.output
    assert '+ parameter.qualifikation = "beschaeftigungskategorie"' in ergebnis.output


# Fehler: eine unbekannte ID endet mit Traceback (VorschlagFehler) statt mit Meldung und Exit 1.
def test_vorschlag_zeigen_unbekannte_id(agent_db: Verbindung) -> None:
    ergebnis = runner.invoke(cli.app, ["vorschlag", "zeigen", "999999"])
    _ohne_traceback(ergebnis)
    assert "gibt es nicht" in ergebnis.output


# Fehler: `freigabe` übergibt Name oder Repo-Pfad falsch, oder die Ausgabe verschweigt wer und was aktiv ist.
def test_freigabe_mit_namen(agent_db: Verbindung, wegwerf_repo: Path) -> None:
    vid = r6_vorschlag(agent_db)
    ergebnis = runner.invoke(cli.app, ["freigabe", str(vid), "--name", NAME])
    assert ergebnis.exit_code == 0, ergebnis.output
    assert f"{NAME} hat Vorschlag uc3/{vid} am " in ergebnis.output
    assert "aktiv: v2/R6_beschaeftigungskategorie" in ergebnis.output
    assert f"Freigegeben-von: {NAME}" in git(wegwerf_repo, "log", "-1", "--format=%B")


# Fehler: ein Platzhalter-Name endet mit Traceback (NameUngueltig) statt mit Meldung und Exit 1.
def test_freigabe_lehnt_platzhalter_ab(agent_db: Verbindung, wegwerf_repo: Path) -> None:
    vid = r6_vorschlag(agent_db)
    ergebnis = runner.invoke(cli.app, ["freigabe", str(vid), "--name", "Team"])
    _ohne_traceback(ergebnis)
    assert "nicht freigegeben" in ergebnis.output
    assert int(git(wegwerf_repo, "rev-list", "--count", "HEAD")) == 1


# Fehler: `ablehnen` fehlt als Befehl oder gibt die Begründung nicht weiter.
def test_ablehnen_mit_begruendung(agent_db: Verbindung, wegwerf_repo: Path) -> None:
    vid = r6_vorschlag(agent_db)
    ergebnis = runner.invoke(
        cli.app, ["ablehnen", str(vid), "--name", NAME, "--begruendung", "nicht im Auftrag"]
    )
    assert ergebnis.exit_code == 0, ergebnis.output
    assert f"{NAME} hat Vorschlag uc3/" in ergebnis.output
    assert "abgelehnt. Begründung: nicht im Auftrag" in ergebnis.output


# Fehler: eine unbekannte ID beim Ablehnen endet mit Traceback statt mit Meldung und Exit 1.
def test_ablehnen_unbekannte_id(agent_db: Verbindung, wegwerf_repo: Path) -> None:
    ergebnis = runner.invoke(
        cli.app, ["ablehnen", "999999", "--name", NAME, "--begruendung", "nicht im Auftrag"]
    )
    _ohne_traceback(ergebnis)
    assert "nicht abgelehnt" in ergebnis.output
