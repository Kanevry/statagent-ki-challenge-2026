"""Namensliste vorhanden, aber nicht lesbar: UC2 bleibt bei Beispielbelegen statt auszufallen (online 05.11.).

Fängt: `lade_namensliste` warf PermissionError durch; im UC4-Router fehlte UC2 dann ganz (`fehlend: uc2`).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from uc2.belege.namen import Namensliste
from uc2.verhandlung import belege


def test_unlesbare_namensliste_gilt_als_nicht_geladen(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    datei = tmp_path / "namensliste.txt"
    datei.write_text("Erika Muster\n", encoding="utf-8")
    monkeypatch.setenv("UC2_NAMENSLISTE", str(datei))

    def verweigert(pfad: Path) -> Namensliste:
        raise PermissionError(13, "Permission denied")

    # Rechte statt chmod: die CI läuft als root und könnte die Datei trotzdem lesen.
    monkeypatch.setattr(Namensliste, "lade", staticmethod(verweigert))

    assert belege.lade_namensliste() is None
    fehler = capsys.readouterr().err
    assert "PermissionError" in fehler
    assert str(datei) not in fehler
