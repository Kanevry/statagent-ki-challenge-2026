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


@pytest.fixture(autouse=True)
def blicke_im_tmp(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Kein Test zählt einen Blick auf das echte Test-Set."""
    pfad = tmp_path / "testset-blicke.json"
    monkeypatch.setattr(ev, "BLICKE_DATEI", pfad)
    return pfad


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
    # Die Suche holt MRR_TIEFE Treffer; Recall zählt nur die ersten k = 3.
    # n Fälle plus eine ungezählte Aufwärmrunde über alle n Fälle
    assert len(aufrufe) == 2 * n and all(k == ev.MRR_TIEFE and weg == "volltext" for _, k, weg in aufrufe)
    text = ausgabe.read_text(encoding="utf-8")
    assert f"| suche:volltext | 3/{n} |" in text  # g02, g24a, g24b erwarten § 139
    assert "Mein Name ist Mehmet." in " ".join(f for f, _, _ in aufrufe)
    capsys.readouterr()


def test_soll_quelle_auf_rang_k_plus_1_zaehlt_nicht(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    # Fängt: Recall@k, der die Treffer nicht auf k kürzt (Recall@unendlich bliebe sonst grün). Review !25.
    def fake_suche(
        frage: str, *, k: int = 5, filter: SuchFilter | None = None, weg: str = "auto", conn: Any = None
    ) -> list[Treffer]:
        fuellung = [_treffer("ASVG", str(900 + i)) for i in range(3)]
        return [*fuellung, _treffer("ASVG", "139")]  # Soll-Quelle erst auf Rang k+1 = 4

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
    # Störtext im Attribut (titrvo) zählt nicht, nur der nutzdaten-Text von § 162 (Review !25).
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
    assert ev.zitat_treu(
        "Ein ganzer Satz – mit Gedankenstrich im Text", "Ein ganzer Satz - mit Gedankenstrich im Text"
    )


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


# Handbeschriftet (Review D6a): erfundene, typische Lotse-Sätze. Die drei mit Disclaimer sind positive
# Antworten und dürfen nicht als Abstinenz zählen.
VERHALTEN_SAETZE = [
    ("In meinen Quellen finde ich dazu Folgendes: Pflegegeld gebührt ab 65 Stunden im Monat.", "antwort"),
    (
        "Ich gebe keine medizinische Beratung. Das Pflegegeld beantragen Sie bei der PVA.",
        "antwort",
    ),  # Disclaimer
    (
        "Diese Auskunft ersetzt keine medizinische Beurteilung; laut BPGG § 4 gebührt Pflegegeld ab Stufe 1.",
        "antwort",
    ),  # Disclaimer
    ("Den Arztbesuch müssen Sie nicht belegen, und Sie brauchen keinen Beleg für die e-card.", "antwort"),
    (
        "Das ist keine Rechtsberatung. Krankengeld gibt es laut ASVG § 139 bis zu 26 Wochen.",
        "antwort",
    ),  # Disclaimer
    (
        "Die Rezeptgebühr regelt ASVG § 136; nach § 144 ASVG gilt Weiteres. Die Grenze liegt bei 1450 Euro.",
        "antwort",
    ),
    ("In meinen Quellen finde ich dazu nichts. Ich will Ihnen nichts Falsches sagen.", "abstinenz"),
    ("Dazu habe ich keinen Beleg in meinen Quellen.", "abstinenz"),
    # Grenzantwort mit Verweis an die Ärztin: Übergabe (Review !25), wie die Grenztexte des Kerns.
    ("Ich kann keine medizinische Empfehlung geben. Bitte fragen Sie Ihre Ärztin.", "uebergabe"),
    ("Bitte wenden Sie sich an die Pensionsversicherungsanstalt, sie prüft Ihren Antrag.", "uebergabe"),
]


@pytest.mark.parametrize(("satz", "soll"), VERHALTEN_SAETZE)
def test_verhalten_handbeschriftet_disclaimer_ist_keine_abstinenz(satz: str, soll: str) -> None:
    """Fängt zu weite Phrasen (Review D6a): „in meinen quellen finde ich“, „keine medizinische“, „keinen
    beleg“ und „144“ machten positive Antworten mit Disclaimer oder Zitat zu Abstinenz bzw. Übergabe."""
    assert ev.klassifiziere_verhalten(satz) == soll


def test_zitat_treu_verwirft_zu_kurzes_zitat() -> None:
    """Fängt Review D5a: „die“ steht in jedem Abschnitt und bestand als Zitat."""
    abschnitt = "§ 4. (1) Das Pflegegeld gebührt bei Zutreffen der übrigen Voraussetzungen die Person"
    assert not ev.zitat_treu("die", abschnitt)
    assert not ev.zitat_treu("Das Pflegegeld gebührt", abschnitt)  # 3 Wörter, 21 Zeichen
    assert ev.zitat_treu("Das Pflegegeld gebührt bei Zutreffen der übrigen", abschnitt)  # 7 Wörter


def test_wilson_und_mcnemar_wie_im_review() -> None:
    """Fängt falsche Intervalle oder p-Werte: Review D6 rechnet 5/15 = 15–58 % und 7 : 0 → p = 0,016."""
    unten, oben = ev.wilson(5, 15)
    assert (round(unten, 2), round(oben, 2)) == (0.15, 0.58)
    assert ev.wilson(12, 12)[1] == 1.0 and ev.wilson(0, 0) == (0.0, 1.0)
    assert ev.mcnemar_exakt(7, 0) == pytest.approx(0.015625)
    assert ev.mcnemar_exakt(3, 0) == pytest.approx(0.25)
    assert ev.mcnemar_exakt(0, 0) == 1.0


def test_ueberschrift_regex_zaehlt_parallele_norm() -> None:
    """Fängt einen Dev-Set-Abgleich, der GSVG § 135 „Witwenpension“ nicht zählt, wenn ASVG § 258 erwartet ist,
    oder der ein PDF über die Regex zählt."""
    gsvg = Treffer(**{**_treffer("GSVG", "135").__dict__, "kontext": "GSVG § 135 Witwen(Witwer)pension"})
    pdf = Treffer(**{**_treffer(None, None).__dict__, "quelle": "katalog", "kontext": "Witwenpension"})
    quellen = [{"gesetz": "ASVG", "art": "PARA", "nummer": "258"}]
    assert ev.rang([pdf, gsvg], quellen, "Witwen") == 2
    assert ev.rang([pdf, gsvg], quellen) is None


def test_dev_set_ist_vollstaendig() -> None:
    """Fängt ein unvollständiges Dev-Set oder eine Regex, die nicht kompiliert."""
    import re

    faelle = ev.lade_set(ev.DEV_SET)
    assert [f["id"] for f in faelle] == [f"d{i:02d}" for i in range(1, 13)]
    for f in faelle:
        assert f["erwartete_quellen"] and f["frage"].strip()
        if f["ueberschrift_regex"]:
            re.compile(f["ueberschrift_regex"])


def _fake_suche(aufrufe: list[str]) -> Any:
    def suche(
        frage: str, *, k: int = 5, filter: SuchFilter | None = None, weg: str = "auto", conn: Any = None
    ) -> list[Treffer]:
        aufrufe.append(frage)
        return [_treffer("BPGG", "21c")]

    return suche


def test_testset_blicke_zaehlen_und_brechen_nach_drei_ab(
    tmp_path: Path, blicke_im_tmp: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Fängt Review D6d: beliebig viele Blicke auf das Test-Set. Blick 4 bricht ohne --trotzdem ab."""
    ausgabe = tmp_path / "b.md"
    argv = ["--nur-suche", "--weg", "volltext", "--ausgabe", str(ausgabe)]
    for n in (1, 2, 3):
        assert ev.cli(argv, suche=_fake_suche([])) == 0
        assert f"Blick {n} von 3" in ausgabe.read_text(encoding="utf-8")
    aufrufe: list[str] = []
    assert ev.cli(argv, suche=_fake_suche(aufrufe)) == 2 and aufrufe == []
    assert "Blick 4 von 3" in capsys.readouterr().err
    assert ev.cli([*argv, "--trotzdem"], suche=_fake_suche([])) == 0
    assert [b["n"] for b in ev.lade_blicke()] == [1, 2, 3, 4]
    # Dev-Set zählt nicht
    assert ev.cli([*argv, "--set", str(ev.DEV_SET)], suche=_fake_suche([])) == 0
    assert len(ev.lade_blicke()) == 4


def test_erweiterung_aus_datei_und_gepaarter_vergleich(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Fängt eine Erweiterung datei:, die die Begriffe nicht an die Anfrage hängt oder eine fehlende Frage
    still als „aus“ misst; und einen Bericht ohne gepaarten Vergleich."""
    faelle = ev.lade_set(ev.DEV_SET)
    datei = tmp_path / "begriffe.json"
    datei.write_text(
        ev.json.dumps({f["frage"]: ["Pflegekarenzgeld"] for f in faelle}, ensure_ascii=False),
        encoding="utf-8",
    )
    aufrufe: list[str] = []
    ausgabe = tmp_path / "dev.md"
    argv = [
        "--nur-suche",
        "--set",
        str(ev.DEV_SET),
        "--weg",
        "volltext",
        "--erweiterung",
        f"aus,datei:{datei}",
    ]
    assert ev.cli([*argv, "--ausgabe", str(ausgabe)], suche=_fake_suche(aufrufe)) == 0
    # je Variante 12 Fälle plus eine Aufwärmrunde über 12 Fälle (ohne Begriffe)
    assert len(aufrufe) == 36 and sum(q.endswith(" Pflegekarenzgeld") for q in aufrufe) == 12
    text = ausgabe.read_text(encoding="utf-8")
    assert "| volltext+datei:begriffe | volltext+aus | 0 : 0 | 12 | 1.000 |" in text
    datei.write_text("{}", encoding="utf-8")
    assert ev.cli(argv, suche=_fake_suche([])) == 2
    assert "keine Begriffe" in capsys.readouterr().err


# Review !25: Probesätze. Die ersten vier waren falsch klassifiziert (Negativtests), die übrigen richtig
# (Positivtests, damit die Korrektur sie nicht kippt).
PROBE_FEHLTREFFER = [
    # vorher abstinenz: Disclaimer in einer belegten Antwort
    "Krankengeld gibt es bis 26 Wochen (ASVG § 139). Ich stelle keine Diagnose.",
    # vorher uebergabe: 144 als Paragraph, Seite und Betrag
    "Laut § 144 ASVG und S. 144 beträgt der Betrag 1.144 €.",
    # vorher uebergabe: verneinter Notruf
    "Rufen Sie nicht 144 an, das ist kein Notfall. Pflegegeld gibt es ab 65 Stunden.",
    # vorher uebergabe: Handlungshinweis in einer belegten Antwort
    "Pflegegeld Stufe 1 ab 65 Stunden (BPGG § 4). Wenden Sie sich an die PVA für den Antrag.",
]
PROBE_RICHTIG = [
    ("In meinen Quellen finde ich § 139 ASVG: Krankengeld gibt es bis zu 26 Wochen.", "antwort"),
    ("Berufen Sie sich gegenüber der ÖGK auf ASVG § 139.", "antwort"),
    ("Den Arztbesuch müssen Sie nicht belegen.", "antwort"),
    ("In meinen Quellen finde ich dazu nichts. Ich will Ihnen nichts Falsches sagen.", "abstinenz"),
    ("Rufen Sie sofort die Rettung unter 144.", "uebergabe"),
]


@pytest.mark.parametrize("satz", PROBE_FEHLTREFFER)
def test_probe_fehltreffer_ist_antwort(satz: str) -> None:
    """Fängt die vier Fehltreffer aus Review !25: belegte Antwort mit Disclaimer, 144 als §/Seite/Betrag,
    verneinter Notruf, Handlungshinweis in belegter Antwort."""
    assert ev.klassifiziere_verhalten(satz) == "antwort"


@pytest.mark.parametrize(("satz", "soll"), PROBE_RICHTIG)
def test_probe_richtige_faelle_bleiben(satz: str, soll: str) -> None:
    """Fängt eine Korrektur, die die schon richtigen Probesätze kippt."""
    assert ev.klassifiziere_verhalten(satz) == soll


@pytest.mark.parametrize(
    ("satz", "soll"),
    [
        ("Das ist kein Notruf, sondern eine Frage zum Pflegegeld.", "antwort"),  # Verneinung
        ("Rufen Sie die Rettung, der Notruf ist 144.", "uebergabe"),  # Notruf auch mit Beleg-freiem Text
        ("Laut ASVG § 139 gibt es Krankengeld. Im Notfall rufen Sie 144.", "uebergabe"),  # Grenze vor Beleg
        ("Dazu kann ich Ihnen nicht helfen.", "uebergabe"),  # ausdrücklich nicht helfen
        ("Wenden Sie sich an die PVA, die prüft Ihren Antrag.", "uebergabe"),  # Verweis ohne Beleg
    ],
)
def test_verhalten_wortgrenzen_verneinung_und_beleg(satz: str, soll: str) -> None:
    """Fängt Phrasen ohne Verneinung („kein Notruf“), eine Grenzantwort, die ein Beleg zur Antwort macht, und
    einen Verweis ohne Beleg, der als Antwort durchgeht."""
    assert ev.klassifiziere_verhalten(satz) == soll


def test_satzende_nicht_nach_ordnungszahl_datum_abkuerzung() -> None:
    """Fängt Review !25: „4. Tag“, „01.07.“, „ggf.“, „inkl.“, „evtl.“ beendeten den Satz."""
    assert (
        ev.mittlere_satzlaenge("Am 4. Tag kommt Geld. Ab 01.07. gilt ggf. inkl. Zuschlag evtl. mehr.") == 6.5
    )
    assert ev.mittlere_satzlaenge("Das gilt u. a. bzw. z. B. nach Nr. 3 und Abs. 2.") == 13


def test_sprache_in_und_an_sind_deutsch() -> None:
    """Fängt Review !25: „in“, „an“, „will“ zählten englisch, „Ja, in Wien und in Graz.“ wurde en."""
    assert ev.sprache("Ja, in Wien und in Graz.") == "de"
    assert ev.sprache("Ich will an die PVA schreiben.") == "de"


def test_anfrage_nimmt_persona_ohne_klammern() -> None:
    """Fängt eine Suchanfrage ohne Persona-Angaben oder mit der Set-Notiz „(GSVG)“, die kein Bürger sagt."""
    fall = {
        "persona": "Mirela, 41, selbständige Grafikerin (GSVG), Graz",
        "frage": "Was zahle ich beim Arzt?",
    }
    assert ev.anfrage(fall) == "Mirela, 41, selbständige Grafikerin, Graz. Was zahle ich beim Arzt?"
    assert ev.anfrage({"frage": "Wie lange?", "vorspann": "Ich bin Mehmet."}) == "Ich bin Mehmet. Wie lange?"


def test_pdf_seite_zaehlt_wenn_erwartet() -> None:
    """Fängt einen PDF-Abgleich, der die erwartete Seite übergeht (Antrag S. 1 statt S. 2)."""
    datei = "Anträge und Formulare/Antrag Kur und Reha.pdf"
    s1 = Treffer(**{**_treffer(None, None, datei=datei).__dict__, "seite": 1})
    s2 = Treffer(**{**_treffer(None, None, datei=datei).__dict__, "seite": 2})
    assert ev.rang([s1, s2], [{"datei": datei, "seite": 2}]) == 2
    assert ev.rang([s1, s2], [{"datei": datei}]) == 1


def test_pruefe_set_validiert_nicht_erwartet_und_buendel(faelle: list[dict[str, Any]]) -> None:
    """Fängt kaputte Szenario-Felder (buendel mit leerer Gruppe, nicht_erwartet ohne Datei), die bisher
    ungeprüft durchgingen."""
    kaputt = copy.deepcopy(faelle)
    mit_buendel = next(f for f in kaputt if "buendel" in f)
    mit_buendel["buendel"].append([])
    mit_nicht = next(f for f in kaputt if "nicht_erwartet" in f)
    mit_nicht["nicht_erwartet"] = [{"datei": 3}]
    fehler = ev.pruefe_set(kaputt, daten_dir=None)
    assert any("buendel Gruppe" in f for f in fehler) and any("'datei' ist kein Text" in f for f in fehler)


def test_k_unter_eins_wird_abgewiesen(capsys: pytest.CaptureFixture[str]) -> None:
    """Fängt -k 0, das Recall@0 = 0 meldet, statt abzubrechen."""
    assert ev.cli(["--nur-suche", "-k", "0", "--set", str(ev.DEV_SET)], suche=_fake_suche([])) == 2
    assert "-k muss" in capsys.readouterr().err


def test_recall_je_art_im_bericht(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """Fängt einen Bericht, der nur die Gesamtzahl nennt und Golden gegen Web nicht trennt."""
    ausgabe = tmp_path / "b.md"
    argv = ["--nur-suche", "--weg", "volltext", "--ausgabe", str(ausgabe)]

    def fake(
        frage: str, *, k: int = 5, filter: Any = None, weg: str = "auto", conn: Any = None
    ) -> list[Treffer]:
        return [_treffer("ASVG", "139")]

    assert ev.cli(argv, suche=fake) == 0
    text = ausgabe.read_text(encoding="utf-8")
    assert "Recall@k je Art:" in text and "| suche:volltext | 3/" in text
    capsys.readouterr()


class _FakeKern:
    """Kern-Ersatz ohne uc1.kern: SozDok-Treffer BPGG § 4, Angebot Antrag Kur und Reha S. 2."""

    def __init__(self) -> None:
        self.aufrufe: list[tuple[str, str]] = []

    def __call__(self, text: str, *, erweiterung: str = "llm", conn: Any = None, suche_fn: Any = None) -> Any:
        from types import SimpleNamespace

        self.aufrufe.append((text, erweiterung))
        pdf = Treffer(
            **{
                **_treffer(None, None, datei="Anträge und Formulare/Antrag Kur und Reha.pdf").__dict__,
                "quelle": "formular",
                "seite": 2,
            }
        )
        return SimpleNamespace(
            treffer=[_treffer("BPGG", "4"), pdf],
            angebote=[pdf],
            leistungen=["pflegegeld"],
            angaben={"status": "pva"},
            begriffe=["Pflegegeld"] if erweiterung != "aus" else [],
            grenze=None,
            llm_aufrufe=int(erweiterung == "llm"),
            hinweise=(),
            dauer_ms={"analyse": 1.0, "suche": 2.0},
        )


def test_kern_modus_misst_sozdok_und_pdf_gepaart(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """Fängt einen --kern-Modus, der den Kern nicht je Fall aufruft, SozDok und PDF vermengt oder ohne
    gepaarten Vergleich gegen die nackte Suche berichtet."""
    set_datei = tmp_path / "set.yaml"
    set_datei.write_text(
        ev.yaml.safe_dump(
            {
                "faelle": [
                    {
                        "id": "t1",
                        "frage": "Pflege?",
                        "erwartete_quellen": [{"gesetz": "BPGG", "art": "PARA", "nummer": "4"}],
                    },
                    {
                        "id": "t2",
                        "frage": "Reha-Antrag?",
                        "erwartete_quellen": [
                            {"datei": "Anträge und Formulare/Antrag Kur und Reha.pdf", "seite": 2}
                        ],
                    },
                ]
            },
            allow_unicode=True,
        ),
        encoding="utf-8",
    )
    kern = _FakeKern()
    nackt: list[str] = []
    ausgabe = tmp_path / "k.md"
    argv = [
        "--nur-suche",
        "--kern",
        "--set",
        str(set_datei),
        "--erweiterung",
        "aus,thesaurus",
        "--ausgabe",
        str(ausgabe),
    ]
    assert ev.cli(argv, suche=_fake_suche(nackt), kern=kern) == 0
    # Aufwärmrunde (2 Fälle, aus) plus 2 Varianten x 2 Fälle
    assert [e for _, e in kern.aufrufe] == ["aus", "aus", "aus", "aus", "thesaurus", "thesaurus"]
    text = ausgabe.read_text(encoding="utf-8")
    assert "| kern+aus | 1/1 |" in text and "| volltext+aus | 0/1 |" in text
    assert "| kern-pdf+aus | 1/1 |" in text
    assert "| kern+aus | volltext+aus | 1 : 0 | 0 |" in text
    assert "| kern+thesaurus | 0 |" in text  # Kosten: keine LLM-Aufrufe
    assert ev.cli(["--kern", "--set", str(set_datei)], kern=kern) == 2
    capsys.readouterr()
