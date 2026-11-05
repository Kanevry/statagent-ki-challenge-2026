"""Das eingecheckte abgabe/manifest.json passt zu den eingecheckten Abgabedateien (läuft in der CI, ohne Datenbank).

Ändert jemand eine Datei unter abgabe/ (etwa `uc3 protokoll` oder ein neues Sheet) und vergisst
`uv run uc3 pruefe-abgabe --manifest`, schlägt dieser Test fehl, und die MR-Pipeline wird rot. Die
Ministeriums-CSV liegt außerhalb des Repos; ihr Eintrag wird hier nur auf Vorhandensein geprüft.
"""

from __future__ import annotations

from pathlib import Path

from statagent.berichte.pruefe_abgabe import _punkt_manifest

ABGABE = Path(__file__).resolve().parents[2] / "abgabe"


def test_manifest_passt_zu_den_abgabedateien() -> None:
    punkt = _punkt_manifest(ABGABE, lieferungen_dir=None)
    assert punkt.ok, (
        f"{punkt.hinweis}. Nach jeder Änderung unter abgabe/: "
        "cd uc3 && uv run uc3 pruefe-abgabe --manifest, dann abgabe/manifest.json committen."
    )
