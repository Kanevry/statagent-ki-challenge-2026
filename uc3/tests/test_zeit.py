"""Zeitangaben in Wiener Zeit (Lead-Befund 05.11.: Freigabe zeigte 15:53 UTC statt 16:53)."""

from datetime import UTC, datetime

from statagent.zeit import zeit_text


def test_utc_wird_wiener_zeit_auch_ohne_zone() -> None:
    # Fängt: Formatieren ohne Umrechnung zeigt eine (im Sommer zwei) Stunden zu früh.
    assert zeit_text(datetime(2026, 11, 5, 15, 53, tzinfo=UTC)) == "05.11.2026 16:53"
    assert zeit_text(datetime(2026, 7, 31, 22, 30)) == "01.08.2026 00:30"
    assert zeit_text(None) == "?"
