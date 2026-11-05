from __future__ import annotations

from uc2.belege.abschnitte import Tagger, lade_tagger, text_hash, zerlege_abschnitte


def _langer_text() -> str:
    return "\n".join(
        " ".join(f"Satz {a}.{s} über die Versorgung in der Gemeinde Musterdorf." for s in range(1, 9))
        for a in range(1, 8)
    )


def test_kurzer_artikel_ist_ein_abschnitt() -> None:
    assert zerlege_abschnitte("Ein kurzer Text.", 1500, 200) == ["Ein kurzer Text."]


def test_abschnitte_begrenzt_ueberlappend_und_deterministisch() -> None:
    text = _langer_text()
    abschnitte = zerlege_abschnitte(text, 1500, 200)
    assert abschnitte == zerlege_abschnitte(text, 1500, 200)
    assert len(abschnitte) >= 3
    assert all(len(a) <= 1500 for a in abschnitte)
    for vorher, nachher in zip(abschnitte, abschnitte[1:], strict=False):
        erster_satz = nachher.split(". ")[0] + "."
        assert erster_satz in vorher  # Überlappung: der Folgeabschnitt beginnt mit dem Ende des vorigen
    # nichts geht verloren
    assert all(f"Satz {a}.{s} " in " ".join(abschnitte) for a in range(1, 8) for s in range(1, 9))


def test_text_hash_ignoriert_leerraum() -> None:
    assert text_hash("Ein  Text\nzwei") == text_hash("Ein Text zwei")
    assert text_hash("Ein Text") != text_hash("Ein Test")


def test_tags_ganze_woerter_ohne_gross_klein() -> None:
    tagger = Tagger(
        [
            {"id": "sv", "name": "SV", "aliase": ["ÖGK", "Krankenkasse"]},
            {"id": "pharma", "name": "Pharma", "aliase": ["Arzneimittel"]},
        ]
    )
    assert tagger.tags("Die ögk und die KRANKENKASSE") == ["sv"]
    assert tagger.tags("Krankenkassenbeitrag und Arzneimittelpreise") == []
    assert tagger.tags("Arzneimittel, ÖGK.") == ["pharma", "sv"]


def test_tags_aus_institutionen_yaml() -> None:
    assert lade_tagger().tags("Die Ärztekammer und die Gesundheitskasse") == ["aerztekammer", "sv"]
