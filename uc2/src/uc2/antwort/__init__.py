"""UC4-Adapter von UC2 (#103): `antwort(frage, kontext) -> UcAntwort`, Abwägung der Akteure mit Beleg.

Entry-Point `kic.uc_antwort: uc2 = "uc2.antwort:antwort"`; der Router (`plattform.router`) findet ihn ohne
harten Import.
"""

from uc2.antwort.adapter import (
    AntwortFehler,
    FreieZahl,
    antwort,
    belegquelle,
    bereinige,
    freie_zahlen,
    waehle_fall,
)

__all__ = ["AntwortFehler", "FreieZahl", "antwort", "belegquelle", "bereinige", "freie_zahlen", "waehle_fall"]
