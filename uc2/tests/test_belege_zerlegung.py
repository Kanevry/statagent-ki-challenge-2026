from __future__ import annotations

from uc2.belege.zerlegung import seiten_aus_text, verbinde_zeilen, zerlege_ausgabe


def test_inhaltsverzeichnis_mit_umbruch_ueber_zwei_seiten(ausgabe_text: str) -> None:
    eintraege = zerlege_ausgabe(ausgabe_text).eintraege
    assert [(e.pdf_seite, e.medium, e.artikeldatum, e.zeitungsseite) for e in eintraege] == [
        (4, "Testblatt", "2026-09-01", "12-13"),
        (8, "Wochenblatt Test", "2026-08-31", "3"),
        (9, "Radio Test - Testjournal", "2026-09-01", None),
    ]
    assert eintraege[0].titel == "Neue Regeln für die Abgabe von Medikamenten in ländlichen Gemeinden"


def test_artikel_ueber_zwei_seiten_ohne_kopf_fuss_und_titel(ausgabe_text: str) -> None:
    ausgabe = zerlege_ausgabe(ausgabe_text)
    assert ausgabe.abweichungen == []
    erster = ausgabe.artikel[0]
    assert erster.text.endswith("Bild: Eine Apotheke in Musterdorf.")
    assert "Apothekerkammer warnt" in erster.text  # Text der zweiten Seite
    for verboten in ("Pressespiegel", "APA-Comm", "Seite 4 von", "Neue Regeln für", "Quelle", "Mutation"):
        assert verboten not in erster.text
    assert (erster.medium, erster.typ) == ("Testblatt", "Tageszeitungen")


def test_layout_kopien_mit_startzeile_werden_verworfen(ausgabe_text: str) -> None:
    ausgabe = zerlege_ausgabe(ausgabe_text)
    assert len(ausgabe.artikel) == 3
    assert all("LAYOUTKOPIE" not in a.text for a in ausgabe.artikel)
    assert all(a.medium != "Musterblatt" for a in ausgabe.artikel)


def test_radio_ohne_sprache_und_ohne_sprecherzeilen(ausgabe_text: str) -> None:
    radio = zerlege_ausgabe(ausgabe_text).artikel[2]
    assert (radio.medium, radio.typ) == ("Radio Test - Testjournal", "Radio")
    assert radio.text.startswith("Die Krankenkasse startet eine kostenlose Beratung")
    assert radio.text.endswith("in allen Bezirken.")


def test_autorin_wird_nie_uebernommen(ausgabe_text: str) -> None:
    for artikel in zerlege_ausgabe(ausgabe_text).artikel:
        assert "Autor:in" not in repr(artikel)
        assert "Musterfrau" not in repr(artikel)


def test_silbentrennung() -> None:
    text = verbinde_zeilen(
        ["Abgabe von Arznei-", "mitteln und die Vier-", "Kilometer-Grenze; Gesundheits-", "und Krankenpflege"]
    )
    assert text == "Abgabe von Arzneimitteln und die Vier-Kilometer-Grenze; Gesundheits- und Krankenpflege"


def test_seiten_am_formfeed() -> None:
    assert len(seiten_aus_text("a\fb\f")) == 2
