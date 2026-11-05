from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

from uc2.belege.extraktion import extrahiere, lies_jsonl

sys.path.insert(0, str(Path(__file__).parent))
import pruefe_index  # noqa: E402  (Prüfskript ist kein Paket und importiert uc2 nicht)


def test_seitentext_passt_zu_druck_und_radio_und_erkennt_verschiebung(
    tmp_path: Path, ausgabe_text: str
) -> None:
    quelle = tmp_path / "presse"
    quelle.mkdir()
    (quelle / "Pressespiegel vom 01.09.2026.pdf").write_text(ausgabe_text, encoding="utf-8")
    extrahiere(
        quelle, tmp_path, ab=date(2026, 1, 1), prozesse=1, leser=lambda p: p.read_text(encoding="utf-8")
    )
    titel = {a["artikel_id"]: (a["pdf_seite"], a["titel"]) for a in lies_jsonl(tmp_path / "artikel.jsonl")}
    seiten = pruefe_index.seiten_von(ausgabe_text)
    v = pruefe_index.vergleichsform
    gesehen = set()
    for s in lies_jsonl(tmp_path / "abschnitte.jsonl"):
        seite, t = titel[s["artikel_id"]]
        rest = pruefe_index.seitenrest(seiten[seite - 1 : seite + 1])
        assert rest is not None
        gesehen.add(rest.rundfunk)
        assert pruefe_index.passt(rest, v(s["text"]), v(t)), seite
        assert not pruefe_index.passt(rest, v(s["text"])[12:], v(t)), seite  # Anfang verschoben
    assert gesehen == {True, False}  # Druck (über Seitenwechsel) und Radio nur mit Titel
    assert pruefe_index.seitenrest(seiten[1:3]) is None  # Verzeichnisseite: keine Startzeile

    transkript = [
        "Pressespiegel",
        "Radio Test - Testjournal vom 02.09.2026",
        "Testjournal - Kasse erweitert Beratung",
        "Sendungsdatum: 02.09.2026",
        "Max Beispiel (Radio Test) (9 Sekunden)",
        "(00:00:05) : Die Kasse erweitert ab heute die Beratung zur Rauchentwöhnung auf alle Bezirke.",
        "Sender           Radio Test",
        "Quelle           Testjournal",
    ]
    rest = pruefe_index.seitenrest([transkript])
    assert rest is not None and rest.rundfunk
    text = v(transkript[5])
    assert pruefe_index.passt(rest, text, v(transkript[2]))
    assert not pruefe_index.passt(rest, text[12:], v(transkript[2]))
