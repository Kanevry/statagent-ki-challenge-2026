"""Tests für `lotse eval` (#30). Fake-Suche statt DB; jeder Test nennt den Fehler, den er fängt."""

from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

import pytest

from uc1 import eval as ev
from uc1.typen import SuchFilter, Treffer


def _treffer(gesetz: str | None, nummer: str | None, datei: str = "Rechtstexte/x.xml") -> Treffer:
    return Treffer(
        abschnitt_id=1,
        dokid="x",
        quelle="sozdok",
        datei=datei,
        gesetz=gesetz,
        art="PARA" if gesetz else None,
        nummer=nummer,
        inkrafttreten=None,
        seite=None,
        zeile=None,
        kontext="",
        text="",
        score=1.0,
        weg="volltext",
    )


@pytest.fixture(scope="module")
def faelle() -> list[dict[str, Any]]:
    return ev.lade_set()


def test_eingefrorenes_set_ist_gueltig(faelle: list[dict[str, Any]]) -> None:
    # Fängt: Set driftet vom Schema oder von der dokumentierten Zählung 13/4/2/8 ab.
    assert ev.pruefe_set(faelle, daten_dir=None) == []


def test_doppelte_id_bricht_das_schema(faelle: list[dict[str, Any]]) -> None:
    # Fängt: zwei Fälle mit derselben ID würden sich im Bericht überschreiben.
    kaputt = copy.deepcopy(faelle)
    kaputt[1]["id"] = kaputt[0]["id"]
    assert any("doppelte id" in f for f in ev.pruefe_set(kaputt, daten_dir=None))


def test_paar_mit_unterschiedlicher_quellmenge_bricht(faelle: list[dict[str, Any]]) -> None:
    # Fängt: Fairness-Paar 24 misst nichts, wenn Michael und Mehmet verschiedene Soll-Quellen haben.
    kaputt = copy.deepcopy(faelle)
    glied = next(f for f in kaputt if f.get("paar"))
    glied["erwartete_quellen"] = [{"gesetz": "ASVG", "art": "PARA", "nummer": "1"}]
    assert any("Quellmengen" in f for f in ev.pruefe_set(kaputt, daten_dir=None))


def test_fehlender_beleg_im_korpus_wird_gemeldet(faelle: list[dict[str, Any]], tmp_path: Path) -> None:
    # Fängt: eine erwartete Quelle, die gar nicht im Korpus liegt, würde Recall unerreichbar machen.
    fehler = ev.pruefe_set(faelle, daten_dir=tmp_path)
    assert any("belegt_durch fehlt" in f for f in fehler)


def test_recall_zaehlt_andere_fassung_aber_nicht_nachbar_paragraph() -> None:
    # Fängt: Abgleich über Dateiname/Fassung statt Gesetz+§, oder Präfix-Vergleich (139 vs. 139a).
    quellen = [{"gesetz": "ASVG", "art": "PARA", "nummer": "139"}]
    andere_fassung = _treffer("ASVG", "139", datei="Rechtstexte/ASVG=PARA=139=99=2001-01-01=2001-01-01.xml")
    assert ev.rang([_treffer("ASVG", "140"), andere_fassung], quellen) == 2
    assert ev.rang([_treffer("ASVG", "139a"), _treffer("GSVG", "139")], quellen) is None


def test_pdf_quelle_zaehlt_nur_gleiche_datei() -> None:
    # Fängt: Case-Manager-Szenario wertet den Unfall-Reha-Antrag als Treffer.
    quellen = [{"datei": "Anträge und Formulare/Antrag Kur und Reha.pdf"}]
    falsch = _treffer(None, None, datei="Anträge und Formulare/Reha_n_Unfall_052026.pdf")
    richtig = _treffer(None, None, datei="Anträge und Formulare/Antrag Kur und Reha.pdf")
    assert ev.rang([falsch], quellen) is None
    assert ev.rang([falsch, richtig], quellen) == 2


def test_nur_suche_mit_fake_suche_schreibt_bericht(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    # Fängt: CLI ruft die Suche nicht mit k/weg auf oder zählt Fälle ohne Korpusquelle im Nenner mit.
    aufrufe: list[tuple[str, int, str]] = []

    def fake_suche(
        frage: str, *, k: int = 5, filter: SuchFilter | None = None, weg: str = "auto", conn: Any = None
    ) -> list[Treffer]:
        aufrufe.append((frage, k, weg))
        return [_treffer("ASVG", "139")]

    ausgabe = tmp_path / "bericht.md"
    rc = ev.cli(["--nur-suche", "-k", "3", "--weg", "volltext", "--ausgabe", str(ausgabe)], suche=fake_suche)
    assert rc == 0
    n = len(ev.faelle_mit_korpusquelle(ev.lade_set()))
    assert len(aufrufe) == n and all(k == 3 and weg == "volltext" for _, k, weg in aufrufe)
    text = ausgabe.read_text(encoding="utf-8")
    assert f"| suche:volltext | 3/{n} |" in text  # g02, g24a, g24b erwarten § 139
    assert "Mein Name ist Mehmet." in " ".join(f for f, _, _ in aufrufe)
    capsys.readouterr()


def test_soll_quelle_auf_rang_k_plus_1_zaehlt_nicht(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    # Fängt: Recall@k, der die Treffer nicht auf k kürzt (Recall@unendlich bliebe sonst grün).
    def fake_suche(
        frage: str, *, k: int = 5, filter: SuchFilter | None = None, weg: str = "auto", conn: Any = None
    ) -> list[Treffer]:
        fuellung = [_treffer("ASVG", str(900 + i)) for i in range(k)]
        return [*fuellung, _treffer("ASVG", "139")]  # Soll-Quelle erst auf Rang k+1

    ausgabe = tmp_path / "bericht.md"
    rc = ev.cli(["--nur-suche", "-k", "3", "--weg", "volltext", "--ausgabe", str(ausgabe)], suche=fake_suche)
    assert rc == 0
    n = len(ev.faelle_mit_korpusquelle(ev.lade_set()))
    assert f"| suche:volltext | 0/{n} |" in ausgabe.read_text(encoding="utf-8")
    capsys.readouterr()


def test_eval_mit_modell_meldet_fehlenden_kern(capsys: pytest.CaptureFixture[str]) -> None:
    # Fängt: `lotse eval` ohne --nur-suche täuscht eine Messung vor, obwohl #31 fehlt.
    assert ev.cli([]) == 2
    assert "#31" in capsys.readouterr().err


def test_grep_grundlinie_findet_dokument_mit_fragewoertern(tmp_path: Path) -> None:
    # Fängt: Grundlinie zählt Wörter unter 4 Zeichen oder liest nicht nur `nutzdaten`.
    rechtstexte = tmp_path / "Rechtstexte"
    rechtstexte.mkdir()
    (rechtstexte / "ASVG=PARA=139=1=2020-01-01=2020-01-01.xml").write_text(
        "<sozdok><metadaten titrvo='Wochengeld'/>"
        "<nutzdaten>Krankengeld Dauer Krankengeld</nutzdaten></sozdok>",
        encoding="utf-8",
    )
    (rechtstexte / "ASVG=PARA=162=1=2020-01-01=2020-01-01.xml").write_text(
        "<sozdok><nutzdaten>Wochengeld und ist der die das</nutzdaten></sozdok>", encoding="utf-8"
    )
    suche = ev.grep_suche(ev.lade_rohkorpus(tmp_path))
    assert [t.nummer for t in suche("Wie lange Krankengeld?", 5)] == ["139"]
    # Störtext im Attribut (titrvo='Wochengeld') darf nicht zählen, nur der nutzdaten-Text von § 162.
    assert [t.nummer for t in suche("Wie lange gibt es Wochengeld?", 5)] == ["162"]
    assert suche("ist der die das", 5) == []


def test_zitat_treu_lehnt_erfundenes_zitat_ab_und_akzeptiert_umbrueche() -> None:
    # Fängt: Zitiertreue scheitert an Zeilenumbruch/Anführungszeichen oder akzeptiert Erfundenes.
    abschnitt = (
        "§ 139. (1) Krankengeldanspruch besteht für ein und denselben\n"
        "   Versicherungsfall bis zur Dauer von 26 Wochen"
    )
    assert ev.zitat_treu("„Krankengeldanspruch besteht für ein und denselben Versicherungsfall“", abschnitt)
    assert not ev.zitat_treu("Krankengeldanspruch besteht bis zur Dauer von 52 Wochen", abschnitt)
    assert not ev.zitat_treu("  ", abschnitt)
    assert ev.zitat_treu("Satz – mit Gedankenstrich", "Satz - mit Gedankenstrich")


def test_klassifiziere_verhalten_erkennt_uebergabe_abstinenz_antwort() -> None:
    # Fängt: Verweis an 1450 zählt als Antwort, oder eine Rufnummer in einem Betrag (1440) als Übergabe.
    assert ev.klassifiziere_verhalten("Bitte rufen Sie sofort den Notruf 144 an.") == "uebergabe"
    assert ev.klassifiziere_verhalten("Ich kann keine Diagnose stellen. Wählen Sie 1450.") == "abstinenz"
    assert (
        ev.klassifiziere_verhalten("Sie erhalten bis zu 26 Wochen Krankengeld, maximal 1440 Euro.")
        == "antwort"
    )


def test_mittlere_satzlaenge_ignoriert_abkuerzungen() -> None:
    # Fängt: "Abs." oder "z. B." zerlegt einen Satz und schönt die Leichte-Sprache-Messung.
    assert ev.mittlere_satzlaenge("Das steht in § 4 Abs. 1 BPGG. Fragen Sie z. B. die PVA.") == pytest.approx(
        6.5
    )
    assert ev.mittlere_satzlaenge("") == 0.0


def test_sprache_erkennt_englisch() -> None:
    # Fängt: englische Grenzfrage wird als deutsch gewertet und die Sprachprüfung greift nie.
    assert ev.sprache("I cannot give medical advice. Please call 144 if you are in danger.") == "en"
    assert ev.sprache("Ich kann keine Diagnose stellen, bitte wenden Sie sich an 1450.") == "de"
