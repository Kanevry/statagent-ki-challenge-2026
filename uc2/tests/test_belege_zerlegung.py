from __future__ import annotations

from pathlib import Path

from uc2.belege.extraktion import extrahiere, lies_jsonl
from uc2.belege.zerlegung import (
    inhaltszeilen,
    ohne_sprecher,
    seiten_aus_text,
    verbinde_zeilen,
    zerlege_ausgabe,
)


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
    # der Radio-Beitrag im Fixture hat kein Transkript (`(hh:mm:ss)`) und gilt als nur_titel
    assert ausgabe.abweichungen == [{"art": "nur_titel", "artikel_nr": 3, "toc_seite": 9}]
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
    # ohne Transkriptzeile fällt der ganze Rumpf weg (Vorspann, Sprecher), der Titel ist der Beleg
    assert radio.nur_titel
    assert radio.text == "Testjournal - Kasse startet Beratung"


def test_autorin_wird_nie_uebernommen(ausgabe_text: str) -> None:
    for artikel in zerlege_ausgabe(ausgabe_text).artikel:
        assert "Autor:in" not in repr(artikel)
        assert "Musterfrau" not in repr(artikel)


def test_autorin_auch_mitten_in_der_zeile() -> None:
    zeilen = [
        "Pressespiegel",
        "Typ              Tageszeitungen        Autor:in         Max Beispiel",
        "Autor:in",
        "Die Autor:innen der Studie empfehlen mehr Kassenstellen.",
    ]
    assert inhaltszeilen(zeilen) == ["Die Autor:innen der Studie empfehlen mehr Kassenstellen."]


def test_silbentrennung() -> None:
    text = verbinde_zeilen(
        ["Abgabe von Arznei-", "mitteln und die Vier-", "Kilometer-Grenze; Gesundheits-", "und Krankenpflege"]
    )
    assert text == "Abgabe von Arzneimitteln und die Vier-Kilometer-Grenze; Gesundheits- und Krankenpflege"


def test_seiten_am_formfeed() -> None:
    assert len(seiten_aus_text("a\fb\f")) == 2


SPRECHER = [
    "Mustermann Erika (Verband der Beispielberufe in",
    "Musterstadt) (17 Sekunden)",
    "Beispiel Max (Radio Test) (9 Sekunden)",
    "Probe Anna (Kammer der",
    "",
    "Testberufe) (5 Sekunden)",
]


def _radioausgabe(titel: list[str], transkript: list[str] | None = None) -> str:
    fuss = "Seite {n} von {m}                                                  © APA-Comm GmbH"
    m = 2 + len(titel)
    toc = ["Pressespiegel", "", "Inhaltsverzeichnis"]
    for i, t in enumerate(titel):
        toc += [f"S. {3 + i}       {t}", "           17.02.2026, Radio Test - Testjournal"]
    seiten = ["Medienbeobachtung", "\n".join([*toc, fuss.format(n=2, m=m)])]
    for i, t in enumerate(titel):
        koerper = [*SPRECHER, *(transkript or [])]
        seiten.append(
            "\n".join(
                [
                    "Pressespiegel",
                    "",
                    "Radio Test - Testjournal vom 17.02.2026",
                    t,
                    *koerper,
                    "Sender           Radio Test",
                    "Quelle           Testjournal",
                    "Typ              Radio",
                    fuss.format(n=3 + i, m=m),
                ]
            )
        )
    return "\f".join(seiten) + "\f"


def test_umbrochene_sprecherzeilen_ganz_verworfen_transkript_bleibt() -> None:
    transkript = "(00:03:10) : ... die Kasse (ÖGK) startet eine Beratung"
    ausgabe = zerlege_ausgabe(_radioausgabe(["Testjournal - Beratung startet"], [transkript]))
    text = ausgabe.artikel[0].text
    for teil in (
        "Mustermann",
        "Erika",
        "Beispielberufe",
        "Musterstadt",
        "Beispiel Max",
        "Probe",
        "Testberufe",
        "Sekunden",
    ):
        assert teil not in text
    assert text == transkript
    assert not ausgabe.artikel[0].nur_titel


def test_ohne_sprecher_unausgeglichene_klammer_ohne_sekunden_bleibt() -> None:
    zeilen = ["Ein Satz (mit Klammer, die", "erst hier schließt) und weiter."]
    assert ohne_sprecher(zeilen) == zeilen


def test_nur_sprecher_beitraege_mit_anderem_titel_bleiben_beide(tmp_path: Path) -> None:
    quelle = tmp_path / "presse"
    quelle.mkdir()
    text = _radioausgabe(["Testjournal - Thema eins", "Testjournal - Thema zwei"])
    (quelle / "Pressespiegel vom 17.02.2026.pdf").write_text(text, encoding="utf-8")
    # dieselbe Sendung in einer zweiten Ausgabe ist eine echte Dublette
    (quelle / "Pressespiegel vom 18.02.2026.pdf").write_text(
        text.replace("Medienbeobachtung", "Medien"), encoding="utf-8"
    )
    extrahiere(quelle, tmp_path / "aus", prozesse=1, leser=lambda p: p.read_text(encoding="utf-8"))
    artikel = lies_jsonl(tmp_path / "aus" / "artikel.jsonl")
    assert [a["text"] for a in artikel] == ["Testjournal - Thema eins", "Testjournal - Thema zwei"]
    arten = [a["art"] for a in lies_jsonl(tmp_path / "aus" / "abweichungen.jsonl")]
    assert arten.count("artikel_dublette") == 2
    assert "nur_titel" not in artikel[0]
    for datei in (tmp_path / "aus").iterdir():
        assert "Mustermann" not in datei.read_text(encoding="utf-8")


NAMENSTEILE = ("Mustermann", "Erika", "Musterfrau", "Beispiel", "Probe", "Anna", "Verband", "Sekunden")


def _radiotext(rumpf: list[str]) -> str:
    return zerlege_ausgabe(_radioausgabe(["Testjournal - Beratung startet"], rumpf)).artikel[0].text


def test_zwei_sprecher_auf_einer_zeile_fallen_weg() -> None:
    text = _radiotext(
        [
            "Musterfrau Erika (beispiel.at - Verband zur Probe zivilgesellschaftlicher Arbeit) (8 Sekunden) "
            "Beispiel Anna (beispiel.at - Verband zur Probe",
            "(00:01:05) : ... die Kasse startet eine Beratung",
        ]
    )
    assert text == "(00:01:05) : ... die Kasse startet eine Beratung"
    assert not any(teil in text for teil in NAMENSTEILE)


def test_sprecher_mitten_in_der_zeile_faellt_weg() -> None:
    text = _radiotext(
        [
            "Vorspann Mustermann Erika (Verband Probe und Beispiel in Musterstadt) (17 Sekunden) Rest",
            "(00:02:00) : ... Wartezeiten sinken",
        ]
    )
    assert text == "(00:02:00) : ... Wartezeiten sinken"
    assert not any(teil in text for teil in (*NAMENSTEILE, "Musterstadt", "Vorspann", "Rest"))


def test_transkript_mit_fortsetzungszeile_bleibt() -> None:
    text = _radiotext(
        [
            "(00:03:10) : ... sich darauf, dass in den kommenden vier Jahren die Kassen",
            "rund drei Viertel der Kosten tragen",
            "(00:04:00) : ... der Rest fällt auf die Länder",
        ]
    )
    assert "(00:03:10) : ... sich darauf, dass in den kommenden vier Jahren die Kassen" in text
    assert "rund drei Viertel der Kosten tragen" in text
    assert "(00:04:00) : ... der Rest fällt auf die Länder" in text
    assert not any(teil in text for teil in NAMENSTEILE)
