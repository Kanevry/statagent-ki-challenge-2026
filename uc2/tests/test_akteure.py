from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

from uc2 import pfade
from uc2.akteure import namensscan
from uc2.akteure.laden import lade_akteure, lade_institutionen, lade_modellrollen
from uc2.akteure.pruefen import pruefe, pruefe_zug

PRUEFSKRIPT = Path(__file__).with_name("pruefe_namen.py")
ERFUNDEN = (
    "Laut Bericht äußerte sich Mag. Erika Musterfrau knapp.\nDas sei falsch, sagt Huber.\nDie ÖVP schweigt.\n"
)


@pytest.fixture(autouse=True)
def _ohne_namensliste(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(namensscan.NAMENSLISTE_ENV, raising=False)


@pytest.fixture
def kopie(tmp_path: Path) -> tuple[Path, Path]:
    akteure = shutil.copytree(pfade.AKTEURE, tmp_path / "akteure")
    config = tmp_path / "config"
    config.mkdir()
    for name in ("institutionen.yaml", "modellrollen.yaml"):
        shutil.copy(pfade.CONFIG / name, config / name)
    return akteure, config


def test_alle_14_akteure_und_rollen_gueltig() -> None:
    ergebnis = pruefe()
    assert ergebnis.fehler == []
    assert sorted(ergebnis.akteure) == sorted(lade_institutionen())
    assert [a.id for a in lade_akteure()] == lade_institutionen()
    rollen = lade_modellrollen()
    assert rollen["akteur"].provider["azure"].aufwand == "niedrig"
    assert rollen["moderator"].provider["ollama"].aufgeloest({"OLLAMA_MODEL": "lokal-x"}) == "lokal-x"


def test_fehlendes_provider_modell_und_fehlende_rolle(kopie: tuple[Path, Path]) -> None:
    akteure, config = kopie
    pfad = config / "modellrollen.yaml"
    daten = yaml.safe_load(pfad.read_text(encoding="utf-8"))
    del daten["rollen"]["akteur"]["provider"]["claude"]
    del daten["rollen"]["experte"]
    pfad.write_text(yaml.safe_dump(daten, allow_unicode=True), encoding="utf-8")
    fehler = pruefe(akteure, config).fehler
    assert "modellrollen.yaml: Rolle 'akteur': kein Modell für Provider 'claude'" in fehler
    assert "modellrollen.yaml: Rolle 'experte' fehlt" in fehler


def test_unbekannte_institution_und_fehlende_datei(kopie: tuple[Path, Path]) -> None:
    akteure, config = kopie
    pfad = akteure / "pharma.md"
    pfad.write_text(
        pfad.read_text(encoding="utf-8").replace("institution: pharma", "institution: apotheke"),
        encoding="utf-8",
    )
    (akteure / "pflege.md").unlink()
    fehler = pruefe(akteure, config).fehler
    assert "pharma.md: unbekannte institution 'apotheke'" in fehler
    assert "Akteursdatei fehlt: pflege.md" in fehler


def test_namensscan_laufzeit_erkennt_erfundene_namen_und_parteien() -> None:
    arten = {(t.zeile, t.art) for t in namensscan.scanne_text(ERFUNDEN, "x.md")}
    assert {(1, "titel"), (1, "vorname"), (2, "zuschreibung"), (3, "partei")} <= arten
    liste = namensscan.scanne_text("von musterfrau, nicht Musterfrauen", "x.md", ["Musterfrau"])
    assert [t.text for t in liste] == ["musterfrau"]  # ganzes Wort, Groß-/Kleinschreibung egal


def test_pruefskript_meldet_treffer_und_ist_auf_akteuren_sauber(tmp_path: Path) -> None:
    datei = tmp_path / "erfunden.md"
    datei.write_text(ERFUNDEN, encoding="utf-8")
    liste = tmp_path / "namen.txt"
    liste.write_text("# Testliste\nHuber\n", encoding="utf-8")
    lauf = subprocess.run(
        [sys.executable, "-I", str(PRUEFSKRIPT), str(datei), "--namensliste", str(liste)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert lauf.returncode == 1
    assert f"{datei}:1: titel: Mag. Erika" in lauf.stdout
    assert f"{datei}:2: zuschreibung: sagt Huber" in lauf.stdout
    assert f"{datei}:2: namensliste: Huber" in lauf.stdout
    assert f"{datei}:3: partei: ÖVP" in lauf.stdout

    echte = [*sorted(pfade.AKTEURE.glob("*.md")), pfade.CONFIG / "modellrollen.yaml"]
    sauber = subprocess.run(
        [sys.executable, "-I", str(PRUEFSKRIPT), *map(str, echte)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert (sauber.returncode, sauber.stdout) == (0, "")


def test_zugschema_akzeptiert_gueltigen_und_lehnt_haltung_3_ab() -> None:
    zug = {
        "themen": [
            {
                "thema": "Kassenstellen",
                "haltung": 1,
                "begruendung": "Mehr Kassenstellen senken die Wartezeit laut Experte.",
                "beleg_ids": ["presse-2026-09:12"],
                "bedingungen": ["Gegenfinanzierung durch den Bund"],
                "zugestaendnis": None,
            }
        ],
        "bezug_auf": ["aerztekammer"],
        "zahlen": [{"wert": 4.3, "einheit": "%", "quelle": "experte"}],
    }
    assert pruefe_zug(zug) == []
    zug["themen"][0]["haltung"] = 3  # type: ignore[index]
    assert pruefe_zug(zug) == ["zug: themen/0/haltung: 3 is greater than the maximum of 2"]
