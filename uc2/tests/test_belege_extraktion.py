from __future__ import annotations

from datetime import date
from pathlib import Path

from uc2.belege.extraktion import extrahiere, lies_jsonl

JSONL = ("quellen.jsonl", "artikel.jsonl", "abschnitte.jsonl", "abweichungen.jsonl")


def _lege_an(wurzel: Path, ausgabe_text: str) -> None:
    (wurzel / "07 Juli").mkdir(parents=True)
    (wurzel / "08 August").mkdir()
    (wurzel / "09 September").mkdir()
    (wurzel / "07 Juli" / "Pressespiegel vom 03.08.2026.pdf").write_text(ausgabe_text, encoding="utf-8")
    (wurzel / "08 August" / "Pressespiegel vom 03.08.2026.pdf").write_text(ausgabe_text, encoding="utf-8")
    zweite = ausgabe_text.replace("01.09.2026\n", "02.09.2026\n", 1)  # andere Datei, gleiche Artikel
    (wurzel / "09 September" / "Pressespiegel vom 02.09.2026.pdf").write_text(zweite, encoding="utf-8")
    (wurzel / "09 September" / "Pressespiegel vom 03.03.2019.pdf").write_text(ausgabe_text, encoding="utf-8")


def _lauf(quelle: Path, aus: Path) -> None:
    extrahiere(quelle, aus, ab=date(2026, 1, 1), prozesse=1, leser=lambda p: p.read_text(encoding="utf-8"))


def test_dubletten_und_byte_gleiche_laeufe(tmp_path: Path, ausgabe_text: str) -> None:
    quelle = tmp_path / "presse"
    _lege_an(quelle, ausgabe_text)
    _lauf(quelle, tmp_path / "a")
    _lauf(quelle, tmp_path / "b")
    for name in JSONL:
        assert (tmp_path / "a" / name).read_bytes() == (tmp_path / "b" / name).read_bytes(), name

    quellen = lies_jsonl(tmp_path / "a" / "quellen.jsonl")
    assert [(q["datei"], q["uebersprungen"]) for q in quellen] == [
        ("07 Juli/Pressespiegel vom 03.08.2026.pdf", False),
        ("08 August/Pressespiegel vom 03.08.2026.pdf", True),
        ("09 September/Pressespiegel vom 02.09.2026.pdf", False),
    ]
    artikel = lies_jsonl(tmp_path / "a" / "artikel.jsonl")
    assert len(artikel) == 3  # die Artikel der zweiten Ausgabe sind textgleich
    arten = [a["art"] for a in lies_jsonl(tmp_path / "a" / "abweichungen.jsonl")]
    assert arten.count("datei_dublette") == 1
    assert arten.count("artikel_dublette") == 3
    abschnitte = lies_jsonl(tmp_path / "a" / "abschnitte.jsonl")
    hashes = [a["text_hash"] for a in abschnitte]
    assert len(hashes) == len(set(hashes))
    assert abschnitte[0]["abschnitt_id"] == artikel[0]["artikel_id"] + "-01"
    assert abschnitte[0]["institutionen"] == ["aerztekammer", "pflege"]


def test_autorin_in_keiner_ausgabedatei(tmp_path: Path, ausgabe_text: str) -> None:
    _lege_an(tmp_path / "presse", ausgabe_text)
    _lauf(tmp_path / "presse", tmp_path / "aus")
    for datei in (tmp_path / "aus").iterdir():
        inhalt = datei.read_text(encoding="utf-8")
        assert "Autor:in" not in inhalt and "Musterfrau" not in inhalt, datei.name
