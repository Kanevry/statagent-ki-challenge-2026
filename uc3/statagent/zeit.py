"""Zeitangaben für Menschen: immer Wiener Zeit, egal in welcher Zone die Datenbank liefert.

Die Datenbank speichert ``timestamptz`` und gibt sie in der Zone der Sitzung zurück (im Container UTC). Wer
„am 05.11.2026 15:53 freigegeben“ liest, versteht Ortszeit; ohne Umrechnung steht dort eine Stunde zu früh.
"""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

ZEITZONE = ZoneInfo("Europe/Vienna")


def zeit_text(wert: object, ersatz: str = "?") -> str:
    """``TT.MM.JJJJ HH:MM`` in Wiener Zeit; eine Zeit ohne Zone gilt als UTC (so liefert sie der Container)."""
    if not isinstance(wert, datetime):
        return ersatz
    if wert.tzinfo is None:
        wert = wert.replace(tzinfo=ZoneInfo("UTC"))
    return f"{wert.astimezone(ZEITZONE):%d.%m.%Y %H:%M}"
