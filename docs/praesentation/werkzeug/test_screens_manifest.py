"""Gegenproben für screens_manifest.py --check in einem tmpdir-Abbild (#134).

Aufruf: uv run pytest -q docs/praesentation/werkzeug/test_screens_manifest.py
(testpaths der Wurzel sammelt diesen Ordner nicht automatisch ein).
"""

from __future__ import annotations

import json
import struct
from pathlib import Path

import pytest
import screens_manifest as sm


def png(breite: int = 1920, hoehe: int = 1080) -> bytes:
    return (
        sm.PNG_SIGNATUR
        + b"\x00\x00\x00\x0dIHDR"
        + struct.pack(">II", breite, hoehe)
        + b"\x08\x02\x00\x00\x00"
    )


def eintrag(n: int, **ueber: object) -> dict[str, object]:
    basis: dict[str, object] = {
        "bild": f"SC{n:02d}",
        "motiv": "m",
        "folie": 1,
        "quelle": "oberflaeche",
        "route": "/uc3",
        "commit": "abc123",
        "lauf": "2024-08",
        "pen_frame": None,
        "art": "live",
        "aufgenommen_am": "2026-11-05T10:00:00+01:00",
        "hinweis": "",
    }
    basis.update(ueber)
    return basis


def abbild(tmp_path: Path, eintraege: list[dict[str, object]]) -> Path:
    screens = tmp_path / "docs" / "praesentation" / "screens"
    screens.mkdir(parents=True)
    (screens / "quellen.json").write_text(json.dumps(eintraege), encoding="utf-8")
    for e in eintraege:
        if not sm.ist_entfallen(e) and "/" not in str(e["bild"]):
            (screens / f"{e['bild']}.png").write_bytes(png())
    return tmp_path


def lauf_check(tmp_path: Path, eintraege: list[dict[str, object]], capsys: pytest.CaptureFixture[str]):
    code = sm.main(["--wurzel", str(abbild(tmp_path, eintraege)), "--check"])
    aus = capsys.readouterr()
    assert aus.err == ""
    return code, aus.out


def test_alles_gueltig_mit_entfallenen(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    eintraege = [eintrag(n) for n in range(1, 13)]
    for n in (3, 4, 5):
        eintraege[n - 1] = eintrag(n, art="offen", lauf=None, commit=None, hinweis="entfällt in v4: x")
    code, out = lauf_check(tmp_path, eintraege, capsys)
    assert code == 0, out
    assert "Stand: 9/9 vorhanden, 9/9 gültig, 3 entfallen, 0 Befunde" in out
    assert not (tmp_path / "docs" / "praesentation" / "screens-manifest.md").exists()


@pytest.mark.parametrize(
    ("ueber", "befund"),
    [
        ({"lauf": None}, "SC01: lauf fehlt"),
        ({"hinweis": "Daten aus MOCK-Provider"}, "SC01: art live, aber hinweis nennt Mock"),
    ],
)
def test_einzelbefund(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], ueber: dict[str, object], befund: str
) -> None:
    eintraege = [eintrag(1, **ueber)] + [eintrag(n) for n in range(2, 13)]
    code, out = lauf_check(tmp_path, eintraege, capsys)
    assert code == 1
    assert befund in out
    assert "11/12 gültig, 1 Befunde" in out


def test_pfadgrenze(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    # Eine echte PNG außerhalb von screens/ darf nicht gelesen werden.
    (tmp_path / "docs" / "praesentation").mkdir(parents=True)
    (tmp_path / "docs" / "praesentation" / "x.png").write_bytes(png())
    eintraege = [eintrag(1, bild="../x")] + [eintrag(n) for n in range(2, 13)]
    screens = tmp_path / "docs" / "praesentation" / "screens"
    screens.mkdir()
    (screens / "quellen.json").write_text(json.dumps(eintraege), encoding="utf-8")
    for n in range(2, 13):
        (screens / f"SC{n:02d}.png").write_bytes(png())
    code = sm.main(["--wurzel", str(tmp_path), "--check"])
    out = capsys.readouterr().out
    assert code == 1
    assert "../x: Bildname unzulässig, nicht gelesen" in out
    assert "11/12 vorhanden" in out


@pytest.mark.parametrize("name", ["../x", "a/b", "/etc/passwd", "..", "", "a\\b"])
def test_bild_pfad_lehnt_ab(tmp_path: Path, name: str) -> None:
    assert sm.bild_pfad(tmp_path, name) is None


def test_pen_frame_optional(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    eintraege = [eintrag(n) for n in range(1, 13)]
    for e in eintraege:
        del e["pen_frame"]
    code, out = lauf_check(tmp_path, eintraege, capsys)
    assert code == 0, out
