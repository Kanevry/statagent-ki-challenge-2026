from __future__ import annotations

import importlib.util
import shutil
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
import yaml

from uc2 import pfade
from uc2.akteure import namensscan
from uc2.akteure.laden import AkteurFehler, lade_akteure, lade_institutionen, lade_modellrollen
from uc2.akteure.pruefen import pruefe, pruefe_zug
from uc2.cli import main

PRUEFSKRIPT = Path(__file__).with_name("pruefe_namen.py")
ERFUNDEN = (
    "Laut Bericht äußerte sich Mag. Erika Musterfrau knapp.\nDas sei falsch, sagt Huber.\nDie ÖVP schweigt.\n"
)


def _skript_scanner() -> Callable[..., list[Any]]:
    spec = importlib.util.spec_from_file_location("pruefe_namen", PRUEFSKRIPT)
    assert spec is not None and spec.loader is not None
    modul = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = modul  # dataclass braucht das Modul in sys.modules
    spec.loader.exec_module(modul)
    scanner: Callable[..., list[Any]] = modul.scanne_text
    return scanner


# Laufzeit und Prüfskript sind getrennt umgesetzt; beide müssen dieselben Formen finden.
SCANNER = pytest.mark.parametrize(
    "scanne", [namensscan.scanne_text, _skript_scanner()], ids=["laufzeit", "pruefskript"]
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


def test_cli_akteure_pruefen_exit_0() -> None:
    assert main(["akteure", "pruefen"]) == 0


def test_unbekannter_zweck_und_nicht_erlaubter_provider(kopie: tuple[Path, Path]) -> None:
    akteure, config = kopie
    pfad = config / "modellrollen.yaml"
    daten = yaml.safe_load(pfad.read_text(encoding="utf-8"))
    assert {daten["rollen"][r]["zweck"] for r in ("moderator", "akteur")} == {"uc2.panel"}
    del daten["luecke"]  # optional seit E0 modell=/aufwand=
    daten["rollen"]["moderator"]["zweck"] = "uc2.moderator"
    daten["rollen"]["akteur"]["zweck"] = "qs.einstufung"  # UC3-Zweck ohne claude
    pfad.write_text(yaml.safe_dump(daten, allow_unicode=True), encoding="utf-8")
    fehler = {f for f in pruefe(akteure, config).fehler if f.startswith("modellrollen.yaml")}
    assert fehler == {
        "modellrollen.yaml: Rolle 'moderator': zweck 'uc2.moderator' fehlt in plattform/zwecke.toml",
        "modellrollen.yaml: Rolle 'akteur': Provider 'claude' ist für zweck 'qs.einstufung' nicht erlaubt",
    }


def test_themenwort_als_alias_wird_gemeldet(kopie: tuple[Path, Path]) -> None:
    akteure, config = kopie
    pfad = config / "institutionen.yaml"
    text = pfad.read_text(encoding="utf-8")
    text = text.replace("aliase: [Sozialversicherung,", "aliase: [Wartezeit, Sozialversicherung,")
    text = text.replace("aliase: [Pharmig,", "aliase: [Medikamente, Pharmig,")
    pfad.write_text(text, encoding="utf-8")
    fehler = pruefe(akteure, config).fehler
    assert "institutionen.yaml: sv: Alias 'Wartezeit' ist Themenwort in gesundheitsministerium.md" in fehler
    assert "institutionen.yaml: pharma: Alias 'Medikamente' ist ein Themenwort" in fehler


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


@SCANNER
@pytest.mark.parametrize(
    ("text", "art", "fund"),
    [
        ("Laut Mag.a Musterfrau", "titel", "Mag.a Musterfrau"),
        ("mit Dr.in Beispielhuber", "titel", "Dr.in Beispielhuber"),
        ("von Prof.in Probe", "titel", "Prof.in Probe"),
        ("durch DIin Musterfrau", "titel", "DIin Musterfrau"),
        ("durch Magª Musterfrau", "titel", "Magª Musterfrau"),
        ("bei Dr. ÖZTÜRK-PROBE", "titel", "Dr. ÖZTÜRK-PROBE"),
        ("bei Dr. Élodie", "titel", "Dr. Élodie"),
        ("laut Herr Mustermann", "funktion", "Herr Mustermann"),
        ("laut Frau Beispielhuber", "funktion", "Frau Beispielhuber"),
        ("die Gesundheitsministerin Musterfrau", "funktion", "Gesundheitsministerin Musterfrau"),
        ("der Finanzminister Probe", "funktion", "Finanzminister Probe"),
        ("Primaria Musterfrau", "funktion", "Primaria Musterfrau"),
        ("Primar Probe", "funktion", "Primar Probe"),
        ("Kammerpräsidentin Beispiel", "funktion", "Kammerpräsidentin Beispiel"),
        ("Obmann Probe und Obfrau Muster", "funktion", "Obfrau Muster"),
        ("Spitalsdirektor Probe", "funktion", "Spitalsdirektor Probe"),
        ("Pressesprecherin Musterfrau", "funktion", "Pressesprecherin Musterfrau"),
        ("Die Neos sind dagegen", "partei", "Neos"),
        ("der ÖVPs Linie", "partei", "ÖVPs"),
        ("auch övp", "partei", "övp"),
        ("Das sagt Dr.\nMusterfrau.", "titel", "Dr. Musterfrau"),
        ("Das betont\n  Probehuber.", "zuschreibung", "betont Probehuber"),
    ],
)
def test_namensscan_erkennt_jede_form(
    scanne: Callable[..., list[Any]], text: str, art: str, fund: str
) -> None:
    assert (art, fund) in {(t.art, t.text) for t in scanne(text, "x.md")}


@SCANNER
def test_namensscan_zeile_ueber_umbruch_und_keine_falschtreffer(scanne: Callable[..., list[Any]]) -> None:
    treffer = scanne("Erste Zeile.\nDas betont\nProbehuber.\n", "x.md")
    assert [(t.zeile, t.art) for t in treffer] == [(2, "zuschreibung")]
    harmlos = (
        "Die Gesundheitsministerin fordert Kassenstellen. Der Kammerpräsident Und die Frau Die.\n"
        "Herr der Lage, grüne Wiese, jetzt. Dr. Der Ordination."
    )
    assert scanne(harmlos, "x.md") == []


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


def test_kaputte_modellrollen_werden_gemeldet_statt_traceback(kopie: tuple[Path, Path]) -> None:
    akteure, config = kopie
    pfad = config / "modellrollen.yaml"
    pfad.write_text("rollen: [moderator\n  akteur: {", encoding="utf-8")
    fehler = pruefe(akteure, config).fehler
    assert any(f.startswith("modellrollen.yaml: kein gültiges YAML") for f in fehler)
    pfad.write_text(
        "luecke: x\nrollen:\n  moderator: {sprachmodell: true, provider: [azure]}\n", encoding="utf-8"
    )
    assert (
        "modellrollen.yaml: Rolle 'moderator': 'provider' ist keine Zuordnung"
        in pruefe(akteure, config).fehler
    )
    with pytest.raises(AkteurFehler, match="'provider' ist keine Zuordnung"):
        lade_modellrollen(config)


def test_zugschema_akzeptiert_gueltigen_und_lehnt_haltung_3_ab() -> None:
    zug = {
        "themen": [
            {
                "thema": "Kassenstellen",
                "haltung": 1,
                "begruendung": "Mehr Kassenstellen senken die Wartezeit laut Experte.",
                "beleg_ids": ["3f2a9c1b7d4e-012-01", "3f2a9c1b7d4e-012"],
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


def test_zugschema_lehnt_quelle_ohne_beleg_id_ab() -> None:
    zug = {"themen": [], "bezug_auf": [], "zahlen": [{"wert": 1, "einheit": "%", "quelle": "geschaetzt"}]}
    assert [f for f in pruefe_zug(zug) if "zahlen/0/quelle" in f]
    zug["zahlen"][0]["quelle"] = "3f2a9c1b7d4e-012-01"  # type: ignore[index]
    assert not [f for f in pruefe_zug(zug) if "zahlen/0/quelle" in f]
