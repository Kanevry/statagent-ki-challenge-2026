"""Tests für uc1.uc4 (Issue #107) ohne Netz und ohne DB: Modell injiziert oder mock-Provider
(PLATTFORM_FIXTURES=tests/fixtures/llm/uc4), Demo-Kontext „Wartezeiten“ (erfunden)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from uc1 import kern, uc4
from uc1.eval import mittlere_satzlaenge

FIXTURES = Path(__file__).resolve().parent / "fixtures"
FRAGE = "Wie lange warte ich auf eine Reha?"


def kontext() -> dict[str, Any]:
    daten: dict[str, Any] = json.loads((FIXTURES / "uc4-wartezeiten.json").read_text(encoding="utf-8"))
    return daten


def modell_mit(*saetze: str) -> Any:
    aufrufe: list[int] = []

    def fn(
        nachrichten: list[dict[str, str]], schema: dict[str, Any], provider: str | None
    ) -> kern.ModellErgebnis:
        aufrufe.append(1)
        return kern.ModellErgebnis(
            json={"saetze": list(saetze)}, provider="test", modell="skript", dauer_ms=0
        )

    fn.aufrufe = aufrufe  # type: ignore[attr-defined]
    return fn


def test_zahlen_und_belege_bleiben_unveraendert_ueber_mock(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Fängt einen Adapter, der Zahlen rundet, Beleg-Indizes verschiebt oder Belege umschreibt (#107 AC 1)."""
    from plattform.llm import mock

    monkeypatch.setenv("PLATTFORM_FIXTURES", str(FIXTURES / "llm" / "uc4"))
    monkeypatch.setenv("PLATTFORM_PROTOKOLL", str(tmp_path / "protokoll.jsonl"))
    mock.zuruecksetzen()
    ktx = kontext()
    a = uc4.antwort(FRAGE, ktx, provider="mock")
    assert set(a) == set(uc4.UcAntwort.model_fields)
    assert a["uc"] == "uc1" and a["modell"] == "mock" and a["protokoll_id"] is None
    assert a["belege"] == [uc4.Beleg.model_validate(b).model_dump() for b in ktx["belege"]]
    assert [(z["wert"], z["beleg"]) for z in a["zahlen"]] == [(19.6, 0), (23.1, 1)]
    assert "19,6" in a["text"] and "23,1" in a["text"]
    assert mittlere_satzlaenge(a["text"]) < 15
    uc4.UcAntwort.model_validate(a)


def eine_zahl() -> dict[str, Any]:
    ktx = kontext()
    ktx["zahlen"] = ktx["zahlen"][:1]
    return ktx


def test_veraenderte_zahl_wird_abgefangen() -> None:
    """Fängt „rund 20“ statt „19,6“: der Satz mit der gerundeten Zahl fällt weg, die echte steht da."""
    modell = modell_mit("Sie warten jetzt kürzer.", "Im August waren es rund 20 Tage.")
    a = uc4.antwort(FRAGE, eine_zahl(), modell=modell)
    assert "rund 20" not in a["text"] and "20 Tage" not in a["text"]
    assert a["text"].startswith("Sie warten jetzt kürzer.") and "19,6 Tage" in a["text"]
    assert [z["wert"] for z in a["zahlen"]] == [19.6]


def test_eine_zahl_im_modellsatz_bleibt() -> None:
    """Fängt eine Prüfung, die bei nur einer Kontext-Zahl auch den richtigen Modellsatz verwirft."""
    a = uc4.antwort(FRAGE, eine_zahl(), modell=modell_mit("Im August warteten Sie 19,6 Tage."))
    assert a["text"] == "Im August warteten Sie 19,6 Tage."


def test_vertauschte_zahlen_kommen_nicht_durch() -> None:
    """Fängt vertauschte Werte (Juli statt August): beide Zahlen stehen im Kontext, die alte Prüfung „kommt
    irgendwo vor“ ließ den Satz durch (Review !68). Ab zwei Zahlen fällt jeder Modellsatz mit Ziffer weg."""
    modell = modell_mit(
        "Sie warten jetzt kürzer.", "Im August waren es 23,1 Tage.", "Im Juli waren es 19,6 Tage."
    )
    a = uc4.antwort(FRAGE, kontext(), modell=modell)
    assert "Im August waren es 23,1" not in a["text"] and "Im Juli waren es 19,6" not in a["text"]
    assert a["text"] == (
        "Sie warten jetzt kürzer. Wartezeit auf eine Rehabilitation im Median, 08/2026: 19,6 Tage. "
        "Wartezeit auf eine Rehabilitation im Median, 07/2026: 23,1 Tage."
    )


def test_zwei_zahlen_server_setzt_zahlensaetze_und_prompt_verbietet_ziffern() -> None:
    """Fängt einen Prompt, der ab zwei Zahlen weiter Ziffern verlangt, und Zahlensätze, die fehlen."""
    gesehen: list[str] = []

    def fn(
        nachrichten: list[dict[str, str]], schema: dict[str, Any], provider: str | None
    ) -> kern.ModellErgebnis:
        gesehen.append(nachrichten[0]["content"])
        return kern.ModellErgebnis(
            json={"saetze": ["Sie warten jetzt kürzer."]}, provider="t", modell="t", dauer_ms=0
        )

    a = uc4.antwort(FRAGE, kontext(), modell=fn)
    assert "weder als Ziffern noch als Wörter" in gesehen[0]
    assert a["text"].count("Tage.") == 2 and "19,6" in a["text"] and "23,1" in a["text"]


def test_zahl_aus_der_frage_ist_keine_belegte_zahl() -> None:
    """Fängt die 500.000 aus „Stimmt es, dass 500.000 Frauen …?“, die mit den Belegen des Kontexts im Text
    stand, weil die Frage als Quelle erlaubter Zahlen galt (Review !68)."""
    a = uc4.antwort(
        "Stimmt es, dass 500.000 Frauen auf eine Reha warten?",
        eine_zahl(),
        modell=modell_mit("Ja, 500.000 Frauen warten.", "Sie warten im Median 19,6 Tage."),
    )
    assert "500" not in a["text"] and "19,6 Tage" in a["text"]


def test_grenzfrage_ergibt_grenzantwort_ohne_modell() -> None:
    """Fängt einen Adapter, der eine Diagnosefrage ans Modell gibt oder Statistik dazu erklärt (#107 AC 2)."""
    modell = modell_mit("Das sollte nie erscheinen.")
    a = uc4.antwort("Ich habe Fieber und Ausschlag, was habe ich?", kontext(), modell=modell)
    assert modell.aufrufe == [] and a["uc"] == "uc1" and a["zahlen"] == [] and a["belege"] == []
    assert "Diagnose" in a["text"]


def test_beleg_index_ohne_beleg_wird_abgelehnt() -> None:
    """Fängt einen Kontext, dessen Zahl auf einen fehlenden Beleg zeigt (Vertrag #96)."""
    ktx = kontext()
    ktx["zahlen"][1]["beleg"] = 5
    with pytest.raises(ValueError, match="Beleg-Index"):
        uc4.antwort(FRAGE, ktx, modell=modell_mit("egal"))


@pytest.mark.parametrize(
    ("wert", "text"),
    [
        (19.6, "19,6"),
        (1234, "1.234"),
        (12345.5, "12.345,5"),
        (-0.07, "-0,07"),
        (-1234, "-1.234"),
        (1e-07, "0,0000001"),
        (2.5e-05, "0,000025"),
        (1e20, "100.000.000.000.000.000.000"),
        (0.1 + 0.2, "0,30000000000000004"),
    ],
)
def test_anzeige_rundet_nicht(wert: Any, text: str) -> None:
    """Fängt eine Schreibweise, die rundet, das Dezimalkomma oder das Minus verliert (-0,07 wurde 0,07) oder
    bei wissenschaftlicher Schreibweise wirft (1e-07 gab ValueError bei UC2-Zahlen, Review !68)."""
    assert uc4.anzeige(uc4.Zahl(bezeichnung="x", wert=wert, beleg=0)) == text


def test_modelltext_wird_geglaettet() -> None:
    """Fängt einen UC4-Text mit Em-Dash oder Floskel des Modells, der ungeglättet rausgeht (uc1.sprache)."""
    modell = modell_mit("Gerne helfe ich Ihnen.", "Sie warten jetzt kürzer — im Median 19,6 Tage.")
    a = uc4.antwort(FRAGE, eine_zahl(), modell=modell)
    assert "—" not in a["text"] and "Gerne" not in a["text"]
    assert a["text"].startswith("Sie warten jetzt kürzer, im Median 19,6 Tage.")
    assert all(b["uc"] == "uc3" for b in a["belege"])


def test_router_adapter_haelt_jede_zahl_an_ihrem_beleg() -> None:
    """Fängt eine Kette uc3 -> uc2 -> uc1, in der die Zahl von uc2 nach dem Zusammenfügen auf einen Beleg von
    uc3 zeigt (Beleg-Index nicht um die Belege davor verschoben, #95)."""
    felder = {k: v for k, v in kontext().items() if k in uc4.UcAntwort.model_fields}
    uc3 = uc4.UcAntwort.model_validate(felder | {"uc": "uc3"})
    uc2 = uc4.UcAntwort(
        text="Im Szenario sinkt die Wartezeit auf 17,2 Tage.",
        belege=[uc4.Beleg(uc="uc2", quelle="szenario.reha")],
        zahlen=[uc4.Zahl(bezeichnung="Wartezeit im Szenario", wert=17.2, einheit="Tage", beleg=0)],
        uc="uc2",
    )
    a = uc4.router_adapter(FRAGE, [uc3, uc2])
    assert a.uc == "uc1"
    assert [b.uc for b in a.belege] == ["uc3", "uc3", "uc2"]
    assert [(z.wert, z.beleg) for z in a.zahlen] == [(19.6, 0), (23.1, 1), (17.2, 2)]


def test_router_findet_den_adapter_ueber_den_entry_point() -> None:
    """Fängt einen fehlenden oder falsch geschriebenen Entry-Point: der Router meldet uc1 sonst als
    ``kein_adapter`` und die UC4-Kette endet ohne Lotse."""
    from importlib.metadata import entry_points

    (punkt,) = entry_points(group="kic.uc_antwort", name="uc1")
    assert punkt.load() is uc4.router_adapter


def test_router_adapter_ohne_kontext_ohne_modell() -> None:
    """Fängt einen Modellaufruf ohne Kontext (die Kette davor lieferte nichts): fester Satz, keine Zahl."""
    a = uc4.router_adapter(FRAGE, [])
    assert a.text == uc4.KEIN_KONTEXT and a.zahlen == []


def test_vorzeichen_der_zahl_zaehlt() -> None:
    """Fängt „+0,5“ im Modellsatz gegen „-0,5“ im Kontext: Die Zahlenprüfung ignorierte das Vorzeichen."""
    ktx = eine_zahl()
    ktx["zahlen"][0]["wert"] = -0.5
    a = uc4.antwort(FRAGE, ktx, modell=modell_mit("Die Wartezeit stieg um +0,5 Tage."))
    assert "+0,5" not in a["text"] and "-0,5" in a["text"]
    a = uc4.antwort(FRAGE, ktx, modell=modell_mit("Die Wartezeit änderte sich um -0,5 Tage."))
    assert a["text"].startswith("Die Wartezeit änderte sich um -0,5 Tage.")


# ---------------------------------------------------------------- /uc4-Probelauf Szene 8 (E0)

WIEN = {
    "uc": "uc2",
    "text": "Im März 2025 gab es in Wien im Gesundheits- und Sozialwesen 7.498 Beschäftigungsverhältnisse.",
    "belege": [
        {"uc": "uc3", "quelle": "Demo-Statistik (erfunden)"},
        {"uc": "uc2", "quelle": "Demo (erfunden)"},
    ],
    "zahlen": [
        {
            "bezeichnung": "Beschäftigungsverhältnisse (Wien, Gesundheits- und Sozialwesen)",
            "wert": 7498,
            "einheit": "Anzahl",
            "beleg": 0,
        },
        {
            "bezeichnung": "Beschäftigungsverhältnisse (Wien, Gesundheits- und Sozialwesen)",
            "wert": 7498,
            "einheit": "Anzahl",
            "beleg": 1,
        },
    ],
}
FRAGE_WIEN = "Wie viele Menschen arbeiten im März 2025 in Wien im Gesundheits- und Sozialwesen?"


@pytest.mark.parametrize(
    "satz",
    [
        "In Wien arbeiten sieben tausend vierhundert achtundneunzig Menschen in diesem Bereich.",
        "Es sind fast siebentausendfünfhundert Stellen.",
        "Das sind zwei Zahlen aus der Statistik.",
        "About seven thousand people work there.",
    ],
)
def test_zahl_als_wort_faellt_weg(satz: str) -> None:
    """Fängt den /uc4-Probelauf: Ab zwei Zahlen durfte das Modell keine Ziffern schreiben und schrieb die Zahl
    als Wörter („sieben tausend vierhundert achtundneunzig“), ungeprüft gegen den Kontext."""
    a = uc4.antwort(FRAGE_WIEN, WIEN, modell=modell_mit("Viele Menschen arbeiten im Gesundheitswesen.", satz))
    assert satz not in a["text"] and a["text"].startswith("Viele Menschen arbeiten im Gesundheitswesen.")


@pytest.mark.parametrize("satz", ["Das ist eine große Zahl.", "Ein Teil davon arbeitet in Spitälern."])
def test_ein_und_eine_sind_kein_zahlwort(satz: str) -> None:
    """Fängt eine Zahlwortprüfung, die schon „ein“ oder „eine“ als Zahl liest und jeden Satz verwirft."""
    a = uc4.antwort(FRAGE_WIEN, WIEN, modell=modell_mit(satz))
    assert a["text"].startswith(satz)


def test_gleiche_zahl_aus_zwei_ucs_steht_einmal_ohne_einheit_anzahl() -> None:
    """Fängt den doppelten Satz „Beschäftigungsverhältnisse (…): 7.498 Anzahl.“, wenn UC3 und UC2 dieselbe
    Zahl liefern, und die Einheit „Anzahl“ als Wort im Satz. ``zahlen`` und ``belege`` bleiben (AC #107)."""
    a = uc4.antwort(FRAGE_WIEN, WIEN, modell=modell_mit("Viele Menschen arbeiten im Gesundheitswesen."))
    assert a["text"] == (
        "Viele Menschen arbeiten im Gesundheitswesen. "
        "Beschäftigungsverhältnisse (Wien, Gesundheits- und Sozialwesen): 7.498."
    )
    assert [(z["wert"], z["beleg"]) for z in a["zahlen"]] == [(7498, 0), (7498, 1)]
    assert len(a["belege"]) == 2


@pytest.mark.parametrize("satz", ["Es sind eins komma fünf Prozent.", "There were zero cases."])
def test_eins_und_zero_sind_zahlwoerter(satz: str) -> None:
    """Fängt „eins“ und „zero“, die als ausgeschriebene Zahl ungeprüft durchgingen (Review !93, #151)."""
    assert uc4.hat_zahlwort(satz)


BELEG_UC3 = uc4.Beleg(
    uc="uc3", quelle="stat.stat_beschaeftigte", monat="2025-10", lieferung="2025-10", stand="vorlaeufig"
)
ZAHL_UC3 = uc4.Zahl(bezeichnung="Beschäftigungsverhältnisse", wert=390900, einheit="Anzahl", beleg=0)
ZAHL_WIEN = ZAHL_UC3.model_copy(
    update={"bezeichnung": "Beschäftigungsverhältnisse (Wien, Gesundheits- und Sozialwesen)", "wert": 7498}
)


def _kette_kontext(*zahlen: uc4.Zahl) -> list[uc4.UcAntwort]:
    """UC3 mit Zahl und Beleg, UC2 reicht beides weiter wie uc2.antwort.adapter."""
    gezeigt = list(zahlen or (ZAHL_UC3,))
    uc3 = uc4.UcAntwort(text="Am 31.10.2025 gab es 390.900.", belege=[BELEG_UC3], zahlen=gezeigt, uc="uc3")
    presse = uc4.Beleg(uc="uc2", quelle="presse: Kurier", monat="2026-09", ref="b1")
    uc2 = uc4.UcAntwort(
        text="Mehr Personal heißt meist kürzere Wartezeiten.",
        belege=[BELEG_UC3, presse],
        zahlen=gezeigt,
        uc="uc2",
    )
    return [uc3, uc2]


def test_kette_verschiedene_fragen_ergeben_verschiedenen_text() -> None:
    """Fängt den Vorbehalt des Leads: Ein fester Satz, der für jede Frage gleich klingt, sagt nichts zum
    Arzttermin."""
    wien = uc4.router_adapter("Wien?", _kette_kontext(ZAHL_WIEN))
    alle = uc4.router_adapter("Oktober?", _kette_kontext())
    assert wien.text == (
        "Für Ihren nächsten Arzttermin in Wien heißt das: Mit mehr Personal im Gesundheits- und Sozialwesen "
        "warten "
        "Sie meist kürzer und werden oft besser betreut. Mit weniger Personal warten Sie meist länger. "
        "Grundlage ist die Zahl von StatAgent: 7.498."
    )
    assert alle.text == (
        "Für Ihren nächsten Arzttermin heißt das: Diese Zahl sagt allein wenig über Ärzte und Pflege. Mehr "
        "Beschäftigte bringen meist mehr Beiträge für die Krankenversicherung und damit mehr Geld für Ihre "
        "Versorgung. Weniger Beschäftigte bringen weniger. Grundlage ist die Zahl von StatAgent: 390.900."
    )


@pytest.mark.parametrize(
    ("bezeichnung", "erwartet"),
    [
        ("Beschäftigungsverhältnisse (Tirol)", "Arzttermin in Tirol heißt das: Diese Zahl sagt allein wenig"),
        (
            "Beschäftigungsverhältnisse (Wien, Frauen, Gesundheits- und Sozialwesen)",
            "in Wien heißt das: Mit mehr",
        ),
        (
            "Beschäftigungsverhältnisse (Frauen, Gesundheits- und Sozialwesen)",
            "Arzttermin heißt das: Mit mehr",
        ),
        ("Beschäftigungsverhältnisse (Tirol, Bau)", "in Tirol heißt das: Diese Zahl sagt allein wenig"),
        ("Fluktuation, alle Wirtschaftsbereiche", "heißt das: Wechselt das Personal oft"),
    ],
)
def test_kette_text_folgt_dem_was_die_zahl_zaehlt(bezeichnung: str, erwartet: str) -> None:
    """Fängt falsche Zuordnung: Bau bekäme den Satz übers Gesundheitswesen, Fluktuation den über mehr
    Personal."""
    zahl = ZAHL_UC3.model_copy(update={"bezeichnung": bezeichnung})
    assert erwartet in uc4.router_adapter("Frage?", _kette_kontext(zahl)).text


@pytest.mark.parametrize(("wert", "wort"), [(-22.24, "kürzer"), (3.0, "länger")])
def test_kette_paket_sagt_die_richtung_aus_dem_rechenmodell(wert: float, wort: str) -> None:
    """Fängt „warten kürzer“, wenn das Rechenmodell für das Paket längere Wartezeiten ergibt."""
    uc3, uc2 = _kette_kontext(ZAHL_WIEN)
    uc2.belege.append(uc4.Beleg(uc="uc2", quelle="uc2.experte", ref="paket"))
    uc2.zahlen.append(
        uc4.Zahl(bezeichnung="Wartezeitänderung (wahrscheinlichster Wert)", wert=wert, einheit="%", beleg=2)
    )
    text = uc4.router_adapter("Wartezeiten?", [uc3, uc2]).text
    assert f"laut Rechenmodell meist {wort}." in text and "22,24" not in text
    assert text.endswith("Grundlage ist die Zahl von StatAgent: 7.498.")


def test_kette_zahl_von_uc3_und_uc2_steht_einmal() -> None:
    """Fängt den Live-Fund vom 05.11.: Dieselbe Zahl aus UC3 und UC2 stand zweimal in der Antwort."""
    a = uc4.router_adapter("Oktober?", _kette_kontext())
    assert [(z.wert, z.beleg) for z in a.zahlen] == [(390900, 0)]
    assert [b.quelle for b in a.belege] == ["stat.stat_beschaeftigte", "presse: Kurier"]


def test_kette_ohne_modell_und_ohne_ki_kennzeichnung(monkeypatch: pytest.MonkeyPatch) -> None:
    """Fängt einen Modellaufruf in der Kette (Entscheid Lead: 4 statt 5 je Frage) und „Mit KI geschrieben“
    über Fixtext."""

    def kein_modell(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError("Modell in der Kette gerufen")

    monkeypatch.setattr(uc4, "standard_modell", kein_modell)
    assert uc4.router_adapter("Oktober?", _kette_kontext()).modell is None


def test_kette_englische_frage_bekommt_deutsche_antwort() -> None:
    """Fängt den Live-Fund: Station 3 antwortet englisch, der Rest der Seite deutsch."""
    a = uc4.router_adapter(
        "How many employees were there in Vienna in March 2025?", _kette_kontext(ZAHL_WIEN)
    )
    assert a.text.startswith("Für Ihren nächsten Arzttermin in Wien heißt das:")


def test_kette_viele_zahlen_stehen_nicht_als_liste_im_text() -> None:
    """Fängt „nach Bundesland“: neun Zahlen als Liste im Satz, die Bedeutung geht unter."""
    viele = [ZAHL_UC3.model_copy(update={"bezeichnung": f"Land {n}", "wert": n}) for n in range(1, 10)]
    a = uc4.router_adapter("Beschäftigte nach Bundesland", _kette_kontext(*viele))
    assert a.text.endswith(uc4.KETTE_VERWEIS) and len(a.zahlen) == 9


def test_kette_grenzfrage_bleibt_grenze_ohne_zahl() -> None:
    """Fängt: Die Kette umgeht die Grenzprüfung; eine Therapiefrage bekäme Zahlen statt des Grenztexts."""
    a = uc4.router_adapter("Welches Medikament soll ich gegen Fieber nehmen?", _kette_kontext())
    assert a.zahlen == [] and "Arzttermin" not in a.text


def test_kette_nachpruefung_bleibt(monkeypatch: pytest.MonkeyPatch) -> None:
    """Fängt einen Text, der an der Nachprüfung vorbeigeht, seit kein Modell ihn schreibt."""
    gesehen: list[str] = []
    echt = uc4.grenze.nachpruefung

    def spion(text: str) -> Any:
        gesehen.append(text)
        return echt(text)

    monkeypatch.setattr(uc4.grenze, "nachpruefung", spion)
    a = uc4.router_adapter("Oktober?", _kette_kontext())
    assert gesehen == [a.text]


def test_kette_belegsatz_nennt_keine_falsche_gliederung() -> None:
    """Fängt „Grundlage: 7.498 Beschäftigungsverhältnisse im März 2025“: Im März gab es rund 390.000, Wien und
    Branche fehlten im Satz (UI-Regie 05.11.)."""
    a = uc4.router_adapter("Wie viele?", _kette_kontext(ZAHL_WIEN))
    assert a.text.endswith("Grundlage ist die Zahl von StatAgent: 7.498.")
