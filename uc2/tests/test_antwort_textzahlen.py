"""Zahlen im Antworttext (`uc2.antwort.textzahlen`, Review zu !73).

Geprüft werden Wert, Vorzeichen, Einheit, Jahresausnahme und der Ersatz an der Trefferposition.
"""

from __future__ import annotations

import pytest
from plattform.antwortform import Zahl

from uc2.antwort.textzahlen import ERSATZ, bereinige, freie_zahlen

ZAHLEN = [
    Zahl(
        bezeichnung="Beschäftigte (Wien, Gesundheits- und Sozialwesen)",
        wert=135790,
        einheit="Personen",
        beleg=0,
    ),
    Zahl(bezeichnung="Wartezeitänderung (wahrscheinlichster Wert)", wert=-22.24, einheit="%", beleg=0),
    Zahl(bezeichnung="Mehrkosten pro Jahr", wert=128.2, einheit="Mio EUR", beleg=0),
    Zahl(bezeichnung="Durchgerechnete Annahmen insgesamt", wert=64, einheit=None, beleg=0),
]


@pytest.mark.parametrize(
    ("text", "frei"),
    [
        # Zahl ohne Eintrag, auch mit unbekannter Einheit
        ("In Wien fehlen 2.000 Pflegekräfte.", ["2.000"]),
        # Wert passt, Einheit nicht
        ("Es gibt 135.790 fehlende Stellen.", ["135.790"]),
        ("Es sind 135.790 Personen.", []),
        # Vorzeichen
        ("Die Wartezeit ändert sich um 22,24 %.", ["22,24 %"]),
        ("Die Wartezeit steigt um +22,24 %.", ["+22,24 %"]),
        ("Die Wartezeit ändert sich um −22,24 %.", []),
        ("Die Wartezeit ändert sich um -22,24 Prozent.", []),
        ("Die Wartezeit ändert sich um minus 22,24 %.", []),
        # Jahreszahl mit Mengeneinheit ist eine Menge
        ("Es fehlen 2025 Stellen.", ["2025 Stellen"]),
        ("Dafür braucht es 2025 Pflegekräfte.", ["2025"]),
        # echte Jahresangaben
        ("Im Jahr 2025 gab es Streit.", []),
        ("Bis 2030 Kosten senken.", []),
        ("2025 war ein schwieriges Jahr.", []),
        ("Stand März 2025, Lieferung 2025-03.", []),
        # Eintrag ohne Einheit: Bezeichnung muss in der Nähe stehen
        ("Es sind 64 durchgerechnete Annahmen.", []),
        ("Durchgerechnete Annahmen insgesamt: 64.", []),
        ("Es fehlen 64 Pflegekräfte.", ["64"]),
        ("Es sind 64 % mehr.", ["64 %"]),
        # Einheit in anderer Schreibweise
        ("Das kostet 128,2 Millionen Euro im Jahr.", []),
        # jede Zifferngruppe, auch ohne Einheit
        ("Das zeigt Runde 2.", ["2"]),
        # Ziffern in Namen sind keine Zahlen
        ("Das sagt Ö1 im Bericht.", []),
    ],
)
def test_jede_zifferngruppe_wird_geprueft(text: str, frei: list[str]) -> None:
    assert freie_zahlen(text, ZAHLEN) == frei


def test_ersatz_ueber_trefferposition_nicht_teilstring() -> None:
    assert bereinige("135.790 Personen, davon 790 Personen in der Pflege", ZAHLEN) == (
        f"135.790 Personen, davon {ERSATZ} in der Pflege"
    )
    vierzehn = [Zahl(bezeichnung="Wartezeit", wert=-14, einheit="%", beleg=0)]
    assert bereinige("Wartezeit −14 %, Kosten 4 %", vierzehn) == f"Wartezeit −14 %, Kosten {ERSATZ}"


def test_bereinigter_text_hat_keine_freie_zahl_mehr() -> None:
    text = (
        "In Wien fehlen 2.000 Pflegekräfte, also 135.790 fehlende Stellen und 2025 Stellen, "
        "Wartezeit 22,24 %."
    )
    sauber = bereinige(text, ZAHLEN)
    assert freie_zahlen(sauber, ZAHLEN) == []
    assert sauber == (
        f"In Wien fehlen {ERSATZ} Pflegekräfte, also {ERSATZ} fehlende Stellen und {ERSATZ}, "
        f"Wartezeit {ERSATZ}."
    )


def test_gedankenstrich_ist_kein_minus() -> None:
    ziel = [Zahl(bezeichnung="Ziel Wartezeitänderung", wert=-20, einheit="%", beleg=0)]
    assert bereinige("Ziel –20 %", ziel) == f"Ziel, {ERSATZ}"
    assert bereinige("Ziel −20 %", ziel) == "Ziel −20 %"


def test_profilzahl_ohne_einheit_bleibt_mit_einheit_nicht() -> None:
    """Die Hotline „1450“ aus einem Akteursprofil ist ein Name; „1450 Stellen“ bleibt zu prüfen."""
    from uc2.antwort.textzahlen import ERSATZ, bereinige, profilzahlen

    profil = profilzahlen(["Patientenlenkung über Hausärztinnen, Hausärzte und 1450"])
    assert (
        bereinige("Lenkung über die Hotline 1450 hilft.", [], profil)
        == "Lenkung über die Hotline 1450 hilft."
    )
    assert ERSATZ in bereinige("Es fehlen 1450 Stellen.", [], profil)
    assert ERSATZ in bereinige("Lenkung über die Hotline 1450 hilft.", [])


def test_wort_der_bezeichnung_gilt_als_einheit() -> None:
    """Azure-Lauf 05.11.: „135.790 Beschäftigte“ passt zur Zahl „Beschäftigte (…)“ mit Einheit Personen."""
    from plattform.antwortform import Zahl

    from uc2.antwort.textzahlen import ERSATZ, bereinige

    z = [
        Zahl(
            bezeichnung="Beschäftigte (Wien, Gesundheits- und Sozialwesen)",
            wert=135790,
            einheit="Personen",
            beleg=0,
        )
    ]
    assert (
        bereinige("Rund 135.790 Beschäftigte arbeiten dort.", z) == "Rund 135.790 Beschäftigte arbeiten dort."
    )
    assert ERSATZ in bereinige("Es gibt 135.790 fehlende Stellen.", z)


# --- Review zu !73 --------------------------------------------------------------------------------------


PROFIL = [
    "Patientenlenkung über Hausärztinnen, Hausärzte und 1450",
    "Gesundheitshotline 1450 stärken",
    "digitale Versorgung über ELGA, 1450 und Telemedizin ausbauen",
]


@pytest.mark.parametrize(
    ("text", "bleibt"),
    [
        ("Es fehlen 1450 Pflegekräfte.", False),
        ("Dafür fehlen 1450 im Land.", False),
        ("Über 1450 Pflegekräfte fehlen.", False),
        ("Die Hotline 1450 hilft.", True),
        ("Die Gesundheitshotline 1450 hilft.", True),
        ("Ruf das Telefon 1450 an.", True),
        ("Die Rufnummer 1450 hilft.", True),
        ("Lenkung über 1450 entlastet.", True),
        # Wortlaut aus dem Profil, Komma und „und“ dazwischen zählen nicht
        ("Lenkung über Hausärzte und 1450 entlastet.", True),
        ("Versorgung über ELGA, 1450 und Telemedizin.", True),
        ("Es fehlen Ärzte und 1450 im Land.", False),
    ],
)
def test_profilzahl_nur_mit_bezeichnung_aus_dem_profil(text: str, bleibt: bool) -> None:
    from uc2.antwort.textzahlen import profilzahlen

    assert (freie_zahlen(text, [], profilzahlen(PROFIL)) == []) is bleibt


@pytest.mark.parametrize(
    ("text", "frei"),
    [
        ("Es fehlen 2025 zusätzliche Pflegekräfte.", ["2025"]),
        ("Es fehlen 2025.", ["2025"]),
        ("Das gilt bis 2030.", []),
        ("Das war im Jahr 2025 so.", []),
        ("Stand März 2025.", []),
        ("2025 wurde gestritten.", []),
        ("Danach: 2025 gab es Streit.", []),
        ("Zwischen 2025 und 2030 steigt es.", []),
        ("2025 zusätzliche Pflegekräfte fehlen.", ["2025"]),
    ],
)
def test_jahr_nur_mit_zeitkontext(text: str, frei: list[str]) -> None:
    assert freie_zahlen(text, ZAHLEN) == frei


@pytest.mark.parametrize(
    ("text", "frei"),
    [
        ("Es gibt 135.790 Gesundheitszentren.", ["135.790"]),
        ("Es gibt 135.790 Sozialwesen.", ["135.790"]),
        ("Es gibt 135.790 Beschäftigte.", []),
        ("Es gibt 135.790 Personen.", []),
        ("Dort arbeiten 135.790 Menschen.", []),
    ],
)
def test_einheit_nur_ueber_feste_aliasse(text: str, frei: list[str]) -> None:
    assert freie_zahlen(text, ZAHLEN) == frei


def test_gleiche_einheit_anderer_begriff_passt_nicht() -> None:
    ziel = [
        Zahl(bezeichnung="Ziel Wartezeitänderung", wert=-20, einheit="%", beleg=0),
        Zahl(bezeichnung="Ziel Mehrkosten höchstens", wert=5, einheit="%", beleg=0),
    ]
    assert freie_zahlen("Das bringt −20 % Mehrkosten.", ziel) == ["−20 %"]
    assert freie_zahlen("Die Mehrkosten sinken um −20 %.", ziel) == ["−20 %"]
    assert freie_zahlen("Das bringt −20 % Wartezeit.", ziel) == []
    assert freie_zahlen("Das Ziel ist −20 % Wartezeit bei höchstens 5 % Mehrkosten.", ziel) == []
    assert freie_zahlen("Das Ziel ist −20 % Mehrkosten bei höchstens 5 % Wartezeit.", ziel) == [
        "−20 %",
        "5 %",
    ]
    # ohne Kennwort im Satzteil entscheidet nur Wert, Vorzeichen und Einheit
    assert freie_zahlen("Das Ziel liegt bei −20 %.", ziel) == []


def test_anzahl_als_einheit_steht_nicht_im_text() -> None:
    """E0 Szene 8: UC3 liefert Einheit „Anzahl“; im Text steht „7.498“, und die Zahl bleibt belegt."""
    from plattform.antwortform import Zahl

    from uc2.antwort.textzahlen import ERSATZ, bereinige, sichtbare_einheit

    z = [
        Zahl(
            bezeichnung="Beschäftigte (Wien, Gesundheits- und Sozialwesen)",
            wert=7498,
            einheit="Anzahl",
            beleg=0,
        )
    ]
    assert sichtbare_einheit("Anzahl") is None and sichtbare_einheit("Personen") == "Personen"
    satz = (
        "Beschäftigte (Wien, Gesundheits- und Sozialwesen): 7.498 (laut Beschäftigtenstatistik, März 2025)."
    )
    assert bereinige(satz, z) == satz
    assert ERSATZ in bereinige("Es fehlen 7.498 Gesundheitszentren.", z)
