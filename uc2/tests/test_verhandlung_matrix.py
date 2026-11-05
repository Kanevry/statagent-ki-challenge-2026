"""Einordnung je Thema (PRD S6) an den Grenzfällen: genau die Hälfte reicht nie."""

from __future__ import annotations

from uc2.verhandlung.matrix import Position, aenderungen, ordne_ein

VIER = ["a", "b", "c", "d"]


def test_genau_die_haelfte_dafuer_ist_keine_mehrheit() -> None:
    e = ordne_ein({"a": 1, "b": 2, "c": 0, "d": -1}, VIER)
    assert e.kategorie == "offener_konflikt" and e.minderheit == ()


def test_genau_die_haelfte_dagegen_ist_nicht_abgelehnt() -> None:
    assert ordne_ein({"a": -1, "b": -2, "c": 0, "d": 1}, VIER).kategorie == "offener_konflikt"


def test_mehrheit_mit_ablehnender_minderheit_und_fehlender_wert_zaehlt_als_enthalten() -> None:
    e = ordne_ein({"a": 1, "b": 1, "c": 2, "d": -1}, [*VIER, "e"])
    assert (e.kategorie, e.minderheit, e.enthalten) == ("mehrheit", ("d",), ("e",))


def test_abgelehnt_mit_zustimmender_minderheit_und_konsens() -> None:
    e = ordne_ein({"a": -1, "b": -1, "c": -2, "d": 1}, VIER)
    assert (e.kategorie, e.minderheit) == ("abgelehnt", ("d",))
    assert ordne_ein({"a": 1, "b": 2, "c": 1, "d": 1}, VIER).kategorie == "konsens"


def test_aenderung_nennt_alt_neu_und_begruendung() -> None:
    vorher = {"a": {"t": Position("a", "t", -1, "alt")}}
    jetzt = {"a": {"t": Position("a", "t", 1, "neu, weil Bedingung erfüllt")}}
    (a,) = aenderungen(2, vorher, jetzt)
    assert (a.runde, a.alt, a.neu, a.begruendung) == (2, -1, 1, "neu, weil Bedingung erfüllt")
