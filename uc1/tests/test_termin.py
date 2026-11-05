"""Tests für uc1.termin (Issue #81). Ohne DB: Suche injiziert, Seitentexte erfunden. Je Test steht im
Docstring, welchen Fehler er fängt. Der Lauf gegen die DB trägt den Marker daten."""

from __future__ import annotations

from typing import Any

import psycopg
import pytest

from uc1 import termin
from uc1.typen import SuchFilter, Suchweg, Treffer

# Erfundene Seite im Layout von PAL080 S. 8: zwei Spalten, die rechte Adresse steht zuerst nicht.
SEITE_ZWEISPALTIG = (
    "persönlich nach telefonischer Terminvereinbarung Landesstelle Wien Landesstelle Kärnten "
    "Musterweg 3, 9020 Klagenfurt am Wörthersee Beispielgasse 12, 1020 Wien E-Mail: test@example.org"
)
# Erfundene Seite mit Halbgeviertstrich und Zeilenumbruch in der Adresse.
SEITE_FSW = (
    "Fonds Soziales Wien Beratungszentrum Pflege- und Betreuung Probegasse 7–9,\n1030 Wien Tel.: 01 000"
)

FALL: dict[str, Any] = {
    "fall": "termin-test",
    "lage": "Meine Mutter ist 82, bekommt eine Pension von der PVA und wohnt in 1100 Wien. "
    "Ich möchte eine Beratung und einen Termin, am liebsten vormittags.",
    "leistung": "pflegegeld",
    "anliegen": "beratung",
    "angaben": {"status": "pva", "bundesland": "wien", "plz": "1100", "zeitpraeferenz": "vormittag"},
    "wunsch": {"datum": "2026-11-17", "zeitpraeferenz": "vormittag"},
    "erstellt": "2026-11-05T09:00:00Z",
}


def treffer(abschnitt_id: int, datei: str, text: str, seite: int = 1) -> Treffer:
    return Treffer(
        abschnitt_id=abschnitt_id,
        dokid=datei,
        quelle="formular",
        datei=datei,
        gesetz=None,
        art=None,
        nummer=None,
        inkrafttreten=None,
        seite=seite,
        zeile=None,
        kontext="",
        text=text,
        score=1.0,
        weg="volltext",
    )


class FalscheSuche:
    """Liefert je Suchanfrage feste Treffer; merkt sich den Suchweg."""

    def __init__(self, seiten: dict[str, list[Treffer]]) -> None:
        self.seiten = seiten
        self.wege: list[str] = []

    def __call__(
        self,
        frage: str,
        *,
        k: int = 5,
        filter: SuchFilter | None = None,
        weg: Suchweg = "auto",
        conn: psycopg.Connection | None = None,
    ) -> list[Treffer]:
        self.wege.append(weg)
        return [t for teil, ts in self.seiten.items() if teil in frage for t in ts][:k]


def stelle_fsw() -> termin.Stelle:
    fund = termin.finde_adresse(SEITE_FSW, "Beratungszentrum Pflege- und Betreuung", "Wien")
    assert fund is not None
    return termin.Stelle(
        id="fsw_beratungszentrum",
        name="Fonds Soziales Wien, Beratungszentrum Pflege und Betreuung",
        adresse=fund.adresse,
        quelle="Anträge und Formulare/Bedarfsmeldung-Senior_innen-Wohngemeinschaft_Basispaket.pdf",
        seite=1,
        abschnitt_id=7,
        beleg=fund.beleg,
        rolle="Beratung",
        zustaendig=None,
        plz=fund.plz,
        ort=fund.ort,
        anliegen=("beratung",),
    )


def test_adresse_nicht_im_quelltext_wird_nicht_belegt() -> None:
    """Fängt: eine Adresse ohne Beleg (etwa aus Modellwissen) wird ausgegeben statt „nicht belegt“."""
    assert not termin.adresse_belegt("Erfundene Straße 5, 1100 Wien", SEITE_FSW)
    assert not termin.adresse_belegt("", SEITE_FSW)
    leer = termin._stelle(
        {
            "id": "x",
            "name": "X",
            "rolle": "r",
            "anker": "Beratungszentrum Pflege- und Betreuung",
            "ort": "Wien",
        },
        [treffer(1, "Anträge und Formulare/a.pdf", "Beratungszentrum Pflege- und Betreuung Tel. 01 000")],
        None,
    )
    assert leer.adresse is None and leer.adresse_text == "nicht belegt" and leer.als_dict()["belegt"] is False


def test_zustaendiger_traeger_ohne_belegte_adresse_bleibt_nicht_belegt() -> None:
    """Fängt: der zuständige Träger fehlt ohne belegte Adresse oder bekommt eine erfundene."""
    suche = FalscheSuche({})
    stellen = termin.stellen_finden(FALL, conn=object(), suche_fn=suche)  # type: ignore[arg-type]
    traeger = [s for s in stellen if s.id == "traeger_pva"]
    assert len(traeger) == 1 and traeger[0].adresse_text == "nicht belegt"
    assert traeger[0].zustaendig == "BPGG § 22 Abs. 1 Z 1"
    assert all(not s.belegt for s in stellen)
    assert set(suche.wege) == {"volltext"}  # kein Embedding-Modell auf dem M4


def test_adresse_normiert_bindestrich_und_umbruch() -> None:
    """Fängt: Halbgeviertstrich oder Zeilenumbruch in der Quelle lassen eine echte Adresse durchfallen."""
    fund = termin.finde_adresse(SEITE_FSW, "Beratungszentrum Pflege- und Betreuung", "Wien")
    assert fund is not None and fund.adresse == "Probegasse 7-9, 1030 Wien"
    assert termin.adresse_belegt(fund.adresse, SEITE_FSW)


def test_zweispaltige_seite_nimmt_adresse_mit_passendem_ort() -> None:
    """Fängt: auf zweispaltigen Seiten bekommt die Stelle die Adresse der Nachbarspalte (Klagenfurt)."""
    fund = termin.finde_adresse(SEITE_ZWEISPALTIG, "Landesstelle Wien", "Wien")
    assert fund is not None and fund.adresse == "Beispielgasse 12, 1020 Wien"
    assert termin.finde_adresse(SEITE_ZWEISPALTIG, "Landesstelle Wien", "Graz") is None


def test_ics_genau_ein_vevent_tentative_nicht_gebucht() -> None:
    """Fängt: mehrere oder kein VEVENT, ein bestätigter Status, fehlendes „nicht gebucht“ oder ein Ort,
    der nicht aus dem Beleg stammt."""
    stelle = stelle_fsw()
    bericht = termin.parse_ics(termin.ics_inhalt(FALL, stelle, wunsch=FALL["wunsch"]))
    assert bericht["vevents"] == 1 and bericht["ausgeglichen"]
    ev = bericht["events"][0]
    assert ev["STATUS"] == "TENTATIVE" and ev["SUMMARY"] == "Terminentwurf"
    assert "nicht gebucht" in ev["DESCRIPTION"]
    assert ev["LOCATION"] == stelle.adresse and termin.adresse_belegt(ev["LOCATION"], SEITE_FSW)
    for teil in ("Unterlagen:", "Nähe:", "Zeitpräferenz:"):
        assert teil in ev["DESCRIPTION"]
    assert not termin.behauptet_termin(ev["DESCRIPTION"])
    assert bericht["zeilen_zu_lang"] == 0 and bericht["nur_crlf"]


def test_kein_entwurf_ohne_belegte_adresse() -> None:
    """Fängt: ein Terminentwurf mit leerem oder erfundenem Ort."""
    ohne = termin.Stelle("x", "X", None, None, None, None, "", "r", None)
    with pytest.raises(ValueError, match="keine belegte Adresse"):
        termin.ics_inhalt(FALL, ohne, wunsch=FALL["wunsch"])


def test_wunschdatum_deterministisch() -> None:
    """Fängt: Datum oder Zeitstempel aus now(); zwei Läufe müssen byte-gleich sein."""
    stelle = stelle_fsw()
    erster = termin.ics_inhalt(FALL, stelle, wunsch=FALL["wunsch"])
    assert erster == termin.ics_inhalt(FALL, stelle, wunsch=FALL["wunsch"])
    ev = termin.parse_ics(erster)["events"][0]
    assert ev["DTSTART"] == "20261117T080000" and ev["DTEND"] == "20261117T120000"
    assert ev["DTSTAMP"] == "20261105T090000Z"


def test_rueckfrage_zeitpraeferenz_genau_einmal() -> None:
    """Fängt: fehlende, doppelte oder wiederholte Frage nach der Zeitpräferenz."""
    frage = termin.naechste_rueckfrage({"angaben": {"plz": "1100"}})
    assert frage == "Wann passt es Ihnen besser: vormittags oder nachmittags?"
    assert termin.naechste_rueckfrage({"angaben": {"plz": "1100", "zeitpraeferenz": "vormittag"}}) is None
    assert termin.naechste_rueckfrage({"angaben": {"plz": "1100"}, "gefragt": ["zeitpraeferenz"]}) is None

    stellen = [stelle_fsw()]
    ohne_zeit = FALL["lage"].replace(", am liebsten vormittags", "")
    fehlt = termin.fuehre_dialog(FALL, [ohne_zeit, "Vormittags."], stellen)
    bekannt = termin.fuehre_dialog(FALL, [FALL["lage"]], stellen)
    assert (fehlt["rueckfragen_gesamt"], fehlt["rueckfragen_zeitpraeferenz"]) == (1, 1)
    assert (bekannt["rueckfragen_gesamt"], bekannt["rueckfragen_zeitpraeferenz"]) == (0, 0)
    for d in (fehlt, bekannt):
        assert d["ergebnis"]["gebucht"] is False and not d["freier_termin_behauptet"]
        assert d["beleg_ids"] == [7]


def test_buchungsbehauptung_wird_erkannt() -> None:
    """Fängt: eine Prüfung, die „Ihr Termin ist bestätigt“ durchlässt."""
    assert termin.behauptet_termin("Ihr Termin ist bestätigt.")
    assert not termin.behauptet_termin("Terminentwurf, nicht gebucht.")


def test_falten_nach_rfc5545() -> None:
    """Fängt: Zeilen über 75 Oktette oder zerteilte Umlaute beim Falten."""
    zeile = "DESCRIPTION:" + "Zeitpräferenz äöü " * 20
    gefaltet = termin.falte(zeile)
    teile = gefaltet.split("\r\n")
    assert all(len(t.encode("utf-8")) <= 75 for t in teile)
    assert "".join(t[1:] if i else t for i, t in enumerate(teile)) == zeile


@pytest.mark.daten
def test_fall_termin_wien_gegen_korpus() -> None:
    """Fängt: im echten Korpus keine belegte Stelle, eine unbelegte Adresse oder ein falsches ICS."""
    ergebnis = termin.pruefen("termin-wien")
    fehl = [p["name"] for p in ergebnis["pruefungen"] if not p["ok"]]
    assert ergebnis["ok"], fehl
    assert any(s["belegt"] and s["seite"] for s in ergebnis["stellen"])
