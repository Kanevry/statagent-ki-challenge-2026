"""Tests für uc1.antrag (#32). Unit-Tests bauen ein Mini-PDF mit AcroForm in tmp_path (pypdf); Tests mit
den echten Formularen aus UC1_DATA_DIR tragen den Marker daten. Alle Personendaten sind erfunden."""

from __future__ import annotations

import copy
import json
import re
import shutil
import subprocess
import unicodedata
from pathlib import Path
from typing import Any

import pytest
from pypdf import PdfReader, PdfWriter
from pypdf.generic import (
    ArrayObject,
    BooleanObject,
    DecodedStreamObject,
    DictionaryObject,
    FloatObject,
    NameObject,
    NumberObject,
    TextStringObject,
)

from uc1 import antrag

DEMO: dict[str, Any] = {
    "angaben": {"status": "pva"},
    "antrag": {
        "person.vorname": "Erika",
        "person.familienname": "Musterfrau",
        "person.geburtsdatum": "01.02.1943",
        "person.strasse": "Musterstraße",
        "person.hausnummer": "1",
        "person.plz": "1100",
        "person.ort": "Wien",
        "antragsteller.vorname": "Karl",
        "antragsteller.beziehung": "Sohn",
        "antrag.art": "erhoehung",
    },
}


# ---------------------------------------------------------------- Mini-PDF mit AcroForm


def _rect(*werte: float) -> ArrayObject:
    return ArrayObject([FloatObject(w) for w in werte])


def _ap(schreiber: PdfWriter) -> Any:
    strom = DecodedStreamObject()
    strom.set_data(b"")
    strom.update({NameObject("/BBox"): _rect(0, 0, 12, 12), NameObject("/Subtype"): NameObject("/Form")})
    return schreiber._add_object(strom)


def baue_mini_pdf(pfad: Path) -> Path:
    """Eine Seite, Textfelder Name (MaxLen 12), Ort, Telefon und eine Knopfgruppe Art mit /01 und /02."""
    schreiber = PdfWriter()
    schreiber.add_blank_page(595, 842)
    seite = schreiber.pages[0]
    felder = []
    for i, (name, hoechstens) in enumerate([("Fam.Name", 12), ("Ort", None), ("Telefon", None)]):
        feld = DictionaryObject(
            {
                NameObject("/Type"): NameObject("/Annot"),
                NameObject("/Subtype"): NameObject("/Widget"),
                NameObject("/FT"): NameObject("/Tx"),
                NameObject("/T"): TextStringObject(name),
                NameObject("/Rect"): _rect(100, 700 - 40 * i, 400, 720 - 40 * i),
                NameObject("/F"): NumberObject(4),
                NameObject("/DA"): TextStringObject("/Helv 10 Tf 0 g"),
            }
        )
        if hoechstens:
            feld[NameObject("/MaxLen")] = NumberObject(hoechstens)
        felder.append(schreiber._add_object(feld))
    gruppe = schreiber._add_object(
        DictionaryObject(
            {
                NameObject("/FT"): NameObject("/Btn"),
                NameObject("/T"): TextStringObject("Art"),
                NameObject("/V"): NameObject("/Off"),
            }
        )
    )
    kinder = []
    for i, export in enumerate(["/01", "/02"]):
        kind = DictionaryObject(
            {
                NameObject("/Type"): NameObject("/Annot"),
                NameObject("/Subtype"): NameObject("/Widget"),
                NameObject("/Parent"): gruppe,
                NameObject("/Rect"): _rect(100 + 50 * i, 500, 112 + 50 * i, 512),
                NameObject("/F"): NumberObject(4),
                NameObject("/AS"): NameObject("/Off"),
                NameObject("/AP"): DictionaryObject(
                    {
                        NameObject("/N"): DictionaryObject(
                            {NameObject(export): _ap(schreiber), NameObject("/Off"): _ap(schreiber)}
                        )
                    }
                ),
            }
        )
        kinder.append(schreiber._add_object(kind))
    gruppe.get_object()[NameObject("/Kids")] = ArrayObject(kinder)
    seite[NameObject("/Annots")] = ArrayObject([*felder, *kinder])
    helv = schreiber._add_object(
        DictionaryObject(
            {
                NameObject("/Type"): NameObject("/Font"),
                NameObject("/Subtype"): NameObject("/Type1"),
                NameObject("/BaseFont"): NameObject("/Helvetica"),
                NameObject("/Encoding"): NameObject("/WinAnsiEncoding"),
            }
        )
    )
    schreiber._root_object[NameObject("/AcroForm")] = DictionaryObject(
        {
            NameObject("/Fields"): ArrayObject([*felder, gruppe]),
            NameObject("/DA"): TextStringObject("/Helv 0 Tf 0 g"),
            NameObject("/DR"): DictionaryObject(
                {NameObject("/Font"): DictionaryObject({NameObject("/Helv"): helv})}
            ),
            NameObject("/NeedAppearances"): BooleanObject(False),
        }
    )
    with pfad.open("wb") as aus:
        schreiber.write(aus)
    return pfad


def mini_zuordnung(pdf: Path) -> dict[str, Any]:
    return {
        "art": "pflegegeld",
        "leistung": "pflegegeld",
        "formular": {
            "bezeichnung": "Mini-Antrag",
            "datei": "Anträge und Formulare/mini.pdf",
            "seiten": 1,
            "sha256": antrag.sha256_datei(pdf),
            "version": "Mini 1",
            "fuer_stelle": "PVA",
        },
        "formularwahl": {"begruendung": "Testformular", "quelle": {"seite": 1, "wortlaut": "Mini"}},
        "felder": [
            {
                "feld": "Fam.Name",
                "art": "text",
                "angabe": "person.familienname",
                "seite": 1,
                "beschriftung": "Name",
            },
            {"feld": "Ort", "art": "text", "angabe": "person.ort", "seite": 1, "beschriftung": "Ort"},
            {
                "feld": "Telefon",
                "art": "text",
                "angabe": "person.telefon",
                "seite": 1,
                "beschriftung": "Telefon",
            },
            {
                "feld": "Art",
                "art": "knopf",
                "angabe": "antrag.art",
                "seite": 1,
                "werte": {"zuerkennung": "/01", "erhoehung": "/02"},
                "beschriftung": "Art",
            },
        ],
        "pflicht": [
            {"id": "name", "text": "Familienname", "felder": ["Fam.Name"], "seite": 1, "wortlaut": "Name"},
            {
                "id": "telefon",
                "text": "Telefonnummer",
                "felder": ["Telefon"],
                "seite": 1,
                "wortlaut": "Telefon",
            },
        ],
        "unterlagen": [{"text": "Befunde in Kopie", "seite": 1, "wortlaut": "Befunde"}],
    }


@pytest.fixture
def mini(tmp_path: Path) -> tuple[Path, dict[str, Any]]:
    pdf = baue_mini_pdf(tmp_path / "mini.pdf")
    return pdf, mini_zuordnung(pdf)


def erzeuge(
    mini: tuple[Path, dict[str, Any]], tmp_path: Path, zustand: dict[str, Any] = DEMO
) -> antrag.AntragErgebnis:
    pdf, zuordnung = mini
    return antrag.erzeuge_antrag(
        "pflegegeld",
        "test-1",
        ausgabe_dir=tmp_path / "aus",
        zustand=zustand,
        formular=pdf,
        zuordnung=zuordnung,
    )


def _werte(pdf: str) -> dict[str, Any]:
    return {n: f.get("/V") for n, f in (PdfReader(pdf).get_fields() or {}).items()}


# ---------------------------------------------------------------- Unit-Tests ohne Daten


def test_unbekannter_feldname_ist_fehler(mini: tuple[Path, dict[str, Any]], tmp_path: Path) -> None:
    """Fängt den stillen Fall aus Spike #28: pypdf ignoriert einen falschen Feldnamen ohne Meldung."""
    pdf, zuordnung = mini
    zuordnung["felder"][1]["feld"] = "Ort_gibt_es_nicht"
    with pytest.raises(antrag.AntragFehler, match="Ort_gibt_es_nicht"):
        erzeuge((pdf, zuordnung), tmp_path)
    assert not (tmp_path / "aus").exists(), "vor der Prüfung darf nichts geschrieben werden"


def test_feld_ohne_gespraechsangabe_bleibt_leer(mini: tuple[Path, dict[str, Any]], tmp_path: Path) -> None:
    """Fängt ein Feld, das ohne Angabe aus dem Gespräch befüllt wird (Telefon ist nie genannt)."""
    e = erzeuge(mini, tmp_path)
    werte = _werte(e.pdf)
    assert werte["Ort"] == "Wien"
    assert not werte.get("Telefon")
    assert "Telefon" not in {b["feld"] for b in e.befuellt}


def test_pflichtfeld_ohne_angabe_steht_in_noch_offen(
    mini: tuple[Path, dict[str, Any]], tmp_path: Path
) -> None:
    """Fängt ein fehlendes Pflichtfeld, das still leer bleibt statt unter „noch offen“ mit Quelle."""
    e = erzeuge(mini, tmp_path)
    offen = {o["id"]: o for o in e.noch_offen}
    assert offen["telefon"]["grund"] == antrag.FEHLT
    assert offen["telefon"]["quelle"] == "Anträge und Formulare/mini.pdf, S. 1: „Telefon“"
    assert "name" not in offen
    assert e.unterlagen == [
        {"text": "Befunde in Kopie", "quelle": "Anträge und Formulare/mini.pdf, S. 1: „Befunde“"}
    ]


def test_checkbox_bekommt_richtigen_export_wert(mini: tuple[Path, dict[str, Any]], tmp_path: Path) -> None:
    """Fängt eine Checkbox mit „true“/„Ja“ oder dem falschen Export-Wert (erhoehung → /02, nicht /01)."""
    e = erzeuge(mini, tmp_path)
    assert str(_werte(e.pdf)["Art"]) == "/02"
    kinder = [a.get_object() for a in PdfReader(e.pdf).pages[0]["/Annots"] if "/Parent" in a.get_object()]
    assert [str(k["/AS"]) for k in kinder] == ["/Off", "/02"]


def test_unbekannter_export_wert_ist_fehler(mini: tuple[Path, dict[str, Any]], tmp_path: Path) -> None:
    """Fängt einen Export-Wert in der Zuordnung, den der Knopf nicht kennt (Knopf bliebe still leer)."""
    pdf, zuordnung = mini
    zuordnung["felder"][3]["werte"]["erhoehung"] = "/ja"
    with pytest.raises(antrag.AntragFehler, match="/ja"):
        erzeuge((pdf, zuordnung), tmp_path)


def test_entwurfsvermerk_in_beiden_lesern(mini: tuple[Path, dict[str, Any]], tmp_path: Path) -> None:
    """Fängt einen Entwurf ohne sichtbaren Vermerk: pypdf sieht die Annotation, pdftotext den Text."""
    e = erzeuge(mini, tmp_path)
    leser = PdfReader(e.pdf)
    assert leser.trailer["/Root"]["/AcroForm"]["/NeedAppearances"]
    vermerke = [
        a.get_object() for a in leser.pages[0]["/Annots"] if a.get_object().get("/Subtype") == "/FreeText"
    ]
    assert len(vermerke) == 1 and antrag.ENTWURF in str(vermerke[0]["/Contents"])
    if shutil.which("pdftotext") is None:
        pytest.skip("pdftotext (poppler) fehlt")
    text = subprocess.run(["pdftotext", "-layout", e.pdf, "-"], capture_output=True, text=True, check=True)
    assert antrag.ENTWURF in text.stdout
    assert "Wien" in text.stdout


def test_zu_langer_wert_wird_nicht_gekuerzt(mini: tuple[Path, dict[str, Any]], tmp_path: Path) -> None:
    """Fängt das stille Abschneiden oder Überlaufen bei MaxLen: pypdf erzwingt MaxLen nicht (Spike #28)."""
    zustand = copy.deepcopy(DEMO)
    zustand["antrag"]["person.familienname"] = "Musterfrau-Beispielhaft"  # 23 Zeichen, MaxLen 12
    e = erzeuge(mini, tmp_path, zustand)
    assert not _werte(e.pdf).get("Fam.Name")
    zu_lang = [o for o in e.noch_offen if o["id"] == "zu_lang:Fam.Name"]
    assert len(zu_lang) == 1 and zu_lang[0]["wert"] == "Musterfrau-Beispielhaft"
    assert "23 Zeichen" in zu_lang[0]["grund"] and "12" in zu_lang[0]["grund"]
    assert "name" not in {o["id"] for o in e.noch_offen}, "dasselbe Feld nicht doppelt melden"


def test_andere_sha256_ist_fehler(mini: tuple[Path, dict[str, Any]], tmp_path: Path) -> None:
    """Fängt eine andere Formularversion, die sonst still mit der alten Zuordnung befüllt würde."""
    pdf, zuordnung = mini
    zuordnung["formular"]["sha256"] = "0" * 64
    with pytest.raises(antrag.AntragFehler, match="andere Formularversion"):
        erzeuge((pdf, zuordnung), tmp_path)


def test_zuordnungen_sind_vollstaendig_und_ohne_dubletten() -> None:
    """Fängt eine Zuordnung ohne Quelle (Seite, Wortlaut) oder mit doppelt belegtem Feld."""
    for art in antrag.ZUORDNUNG:
        z = antrag.lade_zuordnung(art)
        namen = [e["feld"] for e in z["felder"]]
        assert len(namen) == len(set(namen)), art
        assert all(p["wortlaut"] and p["seite"] and "annahme" in p for p in z["pflicht"]), art
        assert all(u["wortlaut"] and u["seite"] for u in z["unterlagen"]), art
        assert re.fullmatch(r"[0-9a-f]{64}", z["formular"]["sha256"]), art


# ---------------------------------------------------------------- echte Formulare (UC1_DATA_DIR)


def _formular(z: dict[str, Any]) -> Path:
    from uc1.config import daten_dir

    return daten_dir() / z["formular"]["datei"]


def _seitentext(pfad: Path, seite: int) -> str:
    roh = subprocess.run(
        ["pdftotext", "-layout", "-f", str(seite), "-l", str(seite), str(pfad), "-"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    # Kästchen zum Ankreuzen sind Glyphen aus dem Private-Use-Bereich (z. B. vor „liegt bei“): weg damit.
    ohne = "".join(z for z in roh if z.isspace() or unicodedata.category(z) not in {"Co", "Cn", "Cc"})
    return re.sub(r"\s+", " ", ohne)


@pytest.mark.daten
@pytest.mark.parametrize("art", list(antrag.ZUORDNUNG))
def test_echte_formulare_passen_zur_zuordnung(art: str) -> None:
    """Fängt einen Feldnamen oder Export-Wert, den es im echten Formular nicht gibt, und eine neue Version."""
    z = antrag.lade_zuordnung(art)
    felder, laengen = antrag.pruefe_formular(_formular(z), z)
    assert all(e["feld"] in felder for e in z["felder"])
    # MaxLen wie im Spike #28 gemessen (formulare/*.felder.roh.json)
    roh = json.loads((antrag.FORMULARE_DIR / antrag.ZUORDNUNG[art].replace(".json", ".roh.json")).read_text())
    erwartet = {f["name"]: f["max_laenge"] for f in roh["felder"] if f.get("max_laenge")}
    assert {n: laengen.get(n) for n in erwartet} == erwartet


@pytest.mark.daten
@pytest.mark.parametrize("art", list(antrag.ZUORDNUNG))
def test_wortlaute_stehen_auf_der_genannten_seite(art: str) -> None:
    """Fängt eine Quelle (Pflicht, Unterlage, Version, Formularwahl), die so nicht auf der Seite steht."""
    z = antrag.lade_zuordnung(art)
    pfad = _formular(z)
    belege = [*z["pflicht"], *z["unterlagen"], z["formular"]["version_quelle"], z["formularwahl"]["quelle"]]
    for beleg in belege:
        text = _seitentext(pfad, int(beleg["seite"]))
        assert re.sub(r"\s+", " ", beleg["wortlaut"]) in text, (beleg["seite"], beleg["wortlaut"])
    if abgelehnt := z["formularwahl"].get("abgelehnt"):
        anderes = pfad.parent.parent / abgelehnt["datei"]
        assert abgelehnt["wortlaut"] in _seitentext(anderes, int(abgelehnt["seite"]))


@pytest.mark.daten
def test_pflegegeld_entwurf_mit_echtem_pal080(tmp_path: Path) -> None:
    """Fängt Werte, die im echten PAL080 nicht ankommen (pypdf) oder nicht sichtbar sind (pdftotext)."""
    e = antrag.erzeuge_antrag("pflegegeld", "demo", ausgabe_dir=tmp_path, zustand=DEMO)
    werte = _werte(e.pdf)
    assert werte["Fam.Name"] == "Musterfrau" and werte["PLZ"] == "1100"
    assert str(werte["Antrag Pflg"]) == "/02"
    assert e.stelle is not None and e.stelle["stelle"] == "PVA"
    text = subprocess.run(["pdftotext", "-layout", e.pdf, "-"], capture_output=True, text=True, check=True)
    assert text.stdout.count(antrag.ENTWURF) == 8  # Vermerk auf jeder der 8 Seiten
    assert "Musterstraße" in text.stdout and "01.02.1943" in text.stdout
    offen = {o["id"] for o in e.noch_offen}
    assert {"versicherungsnummer", "gesundheit", "unterschrift"} <= offen
    assert "vertretung" not in offen, "ohne Familienname des Antragstellers gilt Abschnitt 2 nicht"


@pytest.mark.daten
def test_reha_waehlt_kur_und_reha_und_nennt_aerztliche_begruendung(tmp_path: Path) -> None:
    """Fängt die Wahl von Reha_n_Unfall (füllt das Spital aus) und eine fehlende ärztliche Begründung."""
    e = antrag.erzeuge_antrag("reha", "demo", ausgabe_dir=tmp_path, zustand=DEMO)
    assert e.formularwahl["datei"].endswith("Antrag Kur und Reha.pdf")
    assert "Reha_n_Unfall" in e.formularwahl["nicht_gewaehlt"]["datei"]
    assert "aerztliche_begruendung" in {o["id"] for o in e.noch_offen}
    assert str(_werte(e.pdf)["Pensionsversicherung"]) == "/j"
