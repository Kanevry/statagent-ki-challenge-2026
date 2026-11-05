"""Experte (#42): Literalwerte aus der geschlossenen Formel, nicht aus dem Code nachgerechnet."""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

import pytest
import yaml

from uc2 import pfade
from uc2.cli import main
from uc2.experte import modell

PAKETE = pfade.UC2_WURZEL / "pakete"
PDF = Path("statistik_at_gesundheitsausgaben") / "20260611Gesundheitsausgaben2025.pdf"


def test_pflichtwert_kassenstellen_fuenf_prozent() -> None:
    # ρ₁ = 0,80/1,05 = 0,761904…; W(ρ₁)/W(ρ₀) = (0,7619/0,2381)/(0,8/0,2) = 3,2/4 = 0,8 → −20 %.
    paket = modell.lade_paket(PAKETE / "test-kassenstellen-5.yaml")
    punkt = modell.rechne(paket, paket.modus_werte())
    assert punkt.rho1 == pytest.approx(0.7619, abs=5e-5)
    assert punkt.wartezeit * 100 == pytest.approx(-20.0, abs=0.1)
    assert modell.ergebnis(paket)["zielpruefung"]["ergebnis"] == "erfüllt"


def test_zwei_laeufe_byte_gleich(capsys: pytest.CaptureFixture[str]) -> None:
    paket = str(PAKETE / "beispiel-wartezeiten.yaml")
    assert main(["experte", "--paket", paket, "--json"]) == 0
    erster = capsys.readouterr().out
    assert main(["experte", "--paket", paket, "--json"]) == 0
    assert capsys.readouterr().out == erster
    assert "kein Sprachmodell" in erster


@pytest.mark.daten
def test_ausgangsausgaben_gleich_pdf() -> None:
    pdf = pfade.daten() / PDF
    if not pdf.exists() or shutil.which("pdftotext") is None:
        pytest.skip("Statistik-Austria-PDF oder pdftotext fehlt")
    text = subprocess.run(
        ["pdftotext", "-layout", "-f", "2", "-l", "2", str(pdf), "-"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    zeilen = text.splitlines()
    kopf = next(z for z in zeilen if re.search(r"2018\s+2019.*2025", z))
    jahre = [int(j) for j in re.findall(r"\b20\d\d\b", kopf)]
    # Tabellenzeile, nicht die Überschrift „Laufende Gesundheitsausgaben in Österreich …“.
    reihe = next(z for z in zeilen if re.match(r"\s*Laufende Gesundheitsausgaben\s{2,}\d", z))
    werte = [int(w.replace(" ", "")) for w in re.findall(r"\d{1,3}(?: \d{3})+|\d+", reihe)]
    pdf_wert = dict(zip(jahre, werte, strict=True))[2025]

    eintrag = next(
        a
        for a in yaml.safe_load((pfade.CONFIG / "annahmen.yaml").read_text(encoding="utf-8"))["annahmen"]
        if a["id"] == "ausgangsausgaben"
    )
    assert pdf_wert == 61338
    assert eintrag["modus"] == eintrag["min"] == eintrag["max"] == pdf_wert
    assert (eintrag["typ"], eintrag["jahr"], eintrag["einheit"]) == ("B", 2025, "Mio. EUR")
    assert "Seite 2" in eintrag["quelle"]


def test_beispielpaket_offen_und_rho0_entscheidend() -> None:
    # Modus ρ₀ = 0,80 erreicht −22 %; bei ρ₀ = 0,70 bleiben nur rund −16 %: die Spanne schneidet −20 %.
    daten = modell.ergebnis(modell.lade_paket(PAKETE / "beispiel-wartezeiten.yaml"))
    spanne = daten["kennzahlen"]["wartezeit_aenderung_prozent"]
    assert spanne["min"] < -20.0 < spanne["max"]
    assert daten["zielpruefung"]["ergebnis"] == "offen"
    assert daten["entscheidend"]["annahme"] == "rho0"
    assert daten["entscheidend"]["text"].startswith("entscheidend: ρ₀")
    rho0 = daten["entscheidend"]["einfluesse"][0]
    assert (rho0["min"]["wert"], rho0["max"]["wert"]) == (0.7, 0.95)
    assert rho0["min"]["ziel_erreicht"] is False and rho0["max"]["ziel_erreicht"] is True


def test_kapazitaet_und_nachfrage_multiplikativ(tmp_path: Path) -> None:
    # Kassenstellen +5 % (Δμ = 0,05) und Triage 50 % × 0,2 (Δλ = 0,10) bei ρ₀ = 0,80:
    # ρ₁ = 0,8 · 0,9 / 1,05 = 24/35; W(ρ₁) = 24/11; W(ρ₀) = 4 → Änderung 6/11 − 1 = −5/11.
    fest = {"min": None, "modus": None, "max": None}
    paket_datei = tmp_path / "kombination.yaml"
    paket_datei.write_text(
        yaml.safe_dump(
            {
                "massnahmen": [{"id": "kassenstellen", "umfang": 5}, {"id": "triage", "umfang": 50}],
                "annahmen": {
                    aid: dict.fromkeys(fest, wert)
                    for aid, wert in {
                        "rho0": 0.8,
                        "kassenstellen_besetzung": 1.0,
                        "triage_vermeidung": 0.2,
                    }.items()
                },
            }
        ),
        encoding="utf-8",
    )
    paket = modell.lade_paket(paket_datei)
    punkt = modell.rechne(paket, paket.modus_werte())
    assert punkt.rho1 == pytest.approx(0.6857142857, abs=1e-9)
    assert punkt.wartezeit == pytest.approx(-0.4545454545, abs=1e-9)


def _paket(tmp_path: Path, inhalt: dict[str, object]) -> Path:
    datei = tmp_path / "paket.yaml"
    datei.write_text(yaml.safe_dump(inhalt, allow_unicode=True), encoding="utf-8")
    return datei


def test_text_zeigt_wartezeit_mit_zwei_stellen(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    # Umfang 4,99: W(0,8/1,0499)/W(0,8) = 0,8/0,2499/4 = 0,80032 → −19,97 %, Ziel verfehlt.
    # Mit einer Nachkommastelle stand „−20,0 %“ neben „nicht erfüllt“.
    fest = {"min": 0.8, "modus": 0.8, "max": 0.8}
    datei = _paket(
        tmp_path,
        {
            "massnahmen": [{"id": "kassenstellen", "umfang": 4.99}],
            "annahmen": {"rho0": fest, "kassenstellen_besetzung": {"min": 1.0, "modus": 1.0, "max": 1.0}},
        },
    )
    assert main(["experte", "--paket", str(datei)]) == 0
    text = capsys.readouterr().out
    assert "Wartezeitänderung: −19,97 %" in text
    assert ": nicht erfüllt" in text


def test_tippfehler_im_paket_wird_abgelehnt(tmp_path: Path) -> None:
    datei = _paket(tmp_path, {"massnahmen": [{"id": "kassenstellen", "umfnag": 5}]})
    with pytest.raises(ValueError, match="umfnag"):
        modell.lade_paket(datei)


def test_teiler_null_wird_beim_laden_abgelehnt(tmp_path: Path) -> None:
    register = yaml.safe_load((pfade.CONFIG / "annahmen.yaml").read_text(encoding="utf-8"))
    for eintrag in register["annahmen"]:
        if eintrag["id"] == "bevoelkerung":
            eintrag.update(min=0, modus=0, max=0)
    datei = tmp_path / "annahmen.yaml"
    datei.write_text(yaml.safe_dump(register, allow_unicode=True), encoding="utf-8")
    with pytest.raises(ValueError, match="bevoelkerung"):
        modell.lade_massnahmen(modell.lade_annahmen(datei), modell.lade_ziel())


def test_umfang_ueber_100_prozent_wird_abgelehnt(tmp_path: Path) -> None:
    datei = _paket(tmp_path, {"massnahmen": [{"id": "triage", "umfang": 150}]})
    with pytest.raises(ValueError, match="zwischen 0 und 100"):
        modell.lade_paket(datei)


def test_belegte_annahme_im_paket_gesperrt(tmp_path: Path) -> None:
    datei = _paket(
        tmp_path,
        {
            "massnahmen": [{"id": "kassenstellen", "umfang": 5}],
            "annahmen": {"ausgangsausgaben": {"min": 1000, "modus": 1000, "max": 1000}},
        },
    )
    with pytest.raises(ValueError, match="Typ B"):
        modell.lade_paket(datei)


def test_ziel_kommt_aus_daten() -> None:
    # −20 % erfüllt das Ziel −20 %, aber nicht ein strengeres Ziel −25 %.
    ziel = modell.Ziel(wartezeit=-0.25, kosten=0.05, zieljahr=5, quelle="Test")
    paket = modell.lade_paket(PAKETE / "test-kassenstellen-5.yaml", ziel=ziel)
    daten = modell.ergebnis(paket)
    assert daten["zielpruefung"]["ergebnis"] == "nicht erfüllt"
    assert daten["ziel"]["wartezeit_aenderung_prozent_hoechstens"] == -25.0


def test_gegenlaeufige_annahme_ergibt_offen_statt_nicht_erfuellt(tmp_path: Path) -> None:
    # Kassenstellen +6 % bei ρ₀ 0,8, Bestand 4.200, 13 Mio. EUR je Stelle, Besetzung 0,60/0,85/1,00:
    # Modus Δμ = 0,051 → −20,32 %, Kosten 252 · 0,85 · 13 / 61.338 = +4,54 %, beide Ziele erreicht.
    # Ecke 0,60 verfehlt die Wartezeit (−15,25 %), Ecke 1,00 die Kosten (+5,34 %): keine Ecke erreicht beide.
    def fest(wert: float) -> dict[str, float]:
        return {"min": wert, "modus": wert, "max": wert}

    datei = _paket(
        tmp_path,
        {
            "massnahmen": [{"id": "kassenstellen", "umfang": 6}],
            "annahmen": {
                "rho0": fest(0.8),
                "kassenstellen_bestand": fest(4200),
                "kosten_je_kassenstelle": fest(13),
                "kassenstellen_besetzung": {"min": 0.6, "modus": 0.85, "max": 1.0},
            },
        },
    )
    pruefung = modell.ergebnis(modell.lade_paket(datei))["zielpruefung"]
    assert (pruefung["ecken_erreicht"], pruefung["modus_erreicht"]) == (0, True)
    assert pruefung["ergebnis"] == "offen"


def test_nicht_monotone_struktur_wird_abgelehnt(tmp_path: Path) -> None:
    # Gegenbeispiel aus dem Review: x als Faktor in kompetenzen.wirkung und als Teiler in triage.wirkung.
    # Ecken ergaben −36,0 % und −33,6 % („erfüllt“), der innere Punkt x = 1 nur −9,2 %.
    register = yaml.safe_load((pfade.CONFIG / "annahmen.yaml").read_text(encoding="utf-8"))
    register["annahmen"].append(
        {
            "id": "x",
            "beschreibung": "Test",
            "min": 0.1,
            "modus": 1,
            "max": 10,
            "einheit": "Faktor",
            "typ": "A",
            "quelle": "Test",
        }
    )
    katalog = yaml.safe_load((pfade.CONFIG / "massnahmen.yaml").read_text(encoding="utf-8"))
    for eintrag in katalog["massnahmen"]:
        if eintrag["id"] == "kompetenzen":
            eintrag["wirkung"]["faktoren"].append("x")
        if eintrag["id"] == "triage":
            eintrag["wirkung"]["teiler"] = ["x"]
    (tmp_path / "annahmen.yaml").write_text(yaml.safe_dump(register, allow_unicode=True), encoding="utf-8")
    (tmp_path / "massnahmen.yaml").write_text(yaml.safe_dump(katalog, allow_unicode=True), encoding="utf-8")
    annahmen = modell.lade_annahmen(tmp_path / "annahmen.yaml")
    ziel = modell.lade_ziel()
    massnahmen = modell.lade_massnahmen(annahmen, ziel, tmp_path / "massnahmen.yaml")
    datei = _paket(
        tmp_path, {"massnahmen": [{"id": "kompetenzen", "umfang": 30}, {"id": "triage", "umfang": 30}]}
    )
    with pytest.raises(ValueError, match="`x`"):
        modell.lade_paket(datei, annahmen, massnahmen, ziel)
