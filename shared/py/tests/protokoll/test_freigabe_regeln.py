"""Namensregel und Vorschlagstypen der Freigabe ohne Datenbank (Review !6)."""

import unicodedata

import pytest
from plattform.freigabe import NameUngueltig, _objekt_typ, pruefe_name


@pytest.mark.parametrize("name", ["J. Huber", "Anna O’Brien", "Anna O'Brien", "Marie-Luise Gruber"])
def test_echte_namensformen_sind_erlaubt(name):
    """Fängt: Initiale mit Punkt oder typografischer Apostroph werden fälschlich abgelehnt."""
    assert pruefe_name(name) == name


def test_name_wird_nfc_normalisiert():
    """Fängt: zerlegtes ö (NFD) landet anders im Trailer als im Namensfeld."""
    zerlegt = unicodedata.normalize("NFD", "Bernhard Götzendorfer")
    assert pruefe_name(zerlegt) == "Bernhard Götzendorfer"


@pytest.mark.parametrize("name", ["J. K.", "Max Mustermann", "Vorname Nachname"])
def test_platzhalter_und_reine_initialen_abgelehnt(name):
    with pytest.raises(NameUngueltig):
        pruefe_name(name)


@pytest.mark.parametrize(
    ("vorschlag_typ", "objekt"), [("regel_neu", "regel"), ("regel_aendern", "regel"), ("code_datei", "datei")]
)
def test_vorschlagstypen_aus_uc3_werden_zugeordnet(vorschlag_typ, objekt):
    """Fängt: UC3-Vorschläge (#15) scheitern mit „objekt_typ fehlt“."""
    assert _objekt_typ(None, vorschlag_typ) == objekt
