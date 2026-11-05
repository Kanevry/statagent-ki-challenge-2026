"""Zeiträume der Alltagssprache (#74, UC4 #106): Tabelle aus Formulierungen mit erwartetem Zeitraum und Art.

Läuft ohne Datenbank und ohne Modell. Der jüngste Monat mit Daten ist hier Juli 2026, wie in der Aufgabe
(Lieferungen August 2024 bis Juli 2026). Die Zahlen zu diesen Zeiträumen prüfen test_uc4.py und test_frage.py
gegen eigenes SQL.
"""

from __future__ import annotations

import pytest

from statagent.zeitraum import umschreiben, zeitraum_lesen

LETZTER = "2026-07"

# (Formulierung, von, bis, Art); None = kein Zeitraum in der Frage.
TABELLE: list[tuple[str, str | None, str | None, str | None]] = [
    # Jahreszeiten (Befund Owner 05.11.: „Sommer“ ergab „kein Monat erkannt“)
    ("Wie viele Beschäftigte gab es im Sommer 2025 in Wien im Gesundheits- und Sozialwesen?", "2025-06", "2025-08", "jahreszeit"),
    ("Beschäftigte im Frühling 2025", "2025-03", "2025-05", "jahreszeit"),
    ("Beschäftigte im Frühjahr 2026", "2026-03", "2026-05", "jahreszeit"),
    ("Wie war es im Herbst 2024?", "2024-09", "2024-11", "jahreszeit"),
    ("Beschäftigte im Winter 2025", "2024-12", "2025-02", "jahreszeit"),
    ("Beschäftigte im Winter 2025/26", "2025-12", "2026-02", "jahreszeit"),
    ("Beschäftigte im Winter 2025/2026", "2025-12", "2026-02", "jahreszeit"),
    ("im Herbst des Jahres 2025", "2025-09", "2025-11", "jahreszeit"),
    ("Wie viele arbeiten im Sommer?", "2025-06", "2025-08", "jahreszeit"),
    ("Beschäftigte im Winter", "2025-12", "2026-02", "jahreszeit"),
    # Quartale
    ("Beschäftigte Q1 2025", "2025-01", "2025-03", "quartal"),
    ("Beschäftigte im 2. Quartal 2025", "2025-04", "2025-06", "quartal"),
    ("im ersten Quartal 2026", "2026-01", "2026-03", "quartal"),
    ("im vierten Quartal 2024", "2024-10", "2024-12", "quartal"),
    ("Beschäftigte 2025-Q3", "2025-07", "2025-09", "quartal"),
    ("im letzten Quartal", "2026-04", "2026-06", "quartal"),
    # Halbjahre
    ("im ersten Halbjahr 2025", "2025-01", "2025-06", "halbjahr"),
    ("im 2. Halbjahr 2025", "2025-07", "2025-12", "halbjahr"),
    ("H1 2026", "2026-01", "2026-06", "halbjahr"),
    ("in der zweiten Jahreshälfte 2024", "2024-07", "2024-12", "halbjahr"),
    # Jahresanfang, Mitte, Ende
    ("Beschäftigte Anfang 2025", "2025-01", "2025-01", "jahresteil"),
    ("zum Jahresende 2025", "2025-12", "2025-12", "jahresteil"),
    ("Mitte 2025", "2025-06", "2025-06", "jahresteil"),
    ("Ende des Jahres 2024", "2024-12", "2024-12", "jahresteil"),
    # Bereiche
    ("von Jänner bis März 2025", "2025-01", "2025-03", "bereich"),
    ("Feber bis April 2025", "2025-02", "2025-04", "bereich"),
    ("November bis Februar 2025", "2024-11", "2025-02", "bereich"),
    ("zwischen März und Mai 2025", "2025-03", "2025-05", "bereich"),
    ("Mai-Juli 2025", "2025-05", "2025-07", "bereich"),
    ("von März 2025 bis Juni 2025", "2025-03", "2025-06", "bereich"),
    ("Zeitreihe 08/2024 bis 07/2026", "2024-08", "2026-07", "bereich"),
    ("Juli bis August", "2025-07", "2025-08", "bereich"),
    # Monate, österreichische Namen und Abkürzungen
    ("Beschäftigte Jänner 2025", "2025-01", "2025-01", "monat"),
    ("Beschäftigte Feber 2025", "2025-02", "2025-02", "monat"),
    ("im Jän. 2025", "2025-01", "2025-01", "monat"),
    ("Stand 3/2025", "2025-03", "2025-03", "monat"),
    ("Beschäftigte 2025-03", "2025-03", "2025-03", "monat"),
    ("im Sept. 2025", "2025-09", "2025-09", "monat"),
    ("im März", "2026-03", "2026-03", "monat"),
    ("im August", "2025-08", "2025-08", "monat"),
    # jüngste Monate
    ("Wie viele waren es letzten Monat?", "2026-07", "2026-07", "aktuell"),
    ("im vergangenen Monat in Tirol", "2026-07", "2026-07", "aktuell"),
    ("Wie viele Beschäftigte gibt es aktuell?", "2026-07", "2026-07", "aktuell"),
    ("in den letzten 3 Monaten", "2026-05", "2026-07", "letzte_monate"),
    ("die letzten zwölf Monate", "2025-08", "2026-07", "letzte_monate"),
    # ganze Jahre
    ("Beschäftigte 2025", "2025-01", "2025-12", "jahr"),
    ("Jahresdurchschnitt 2025", "2025-01", "2025-12", "jahr"),
    ("Beschäftigte letztes Jahr", "2025-01", "2025-12", "jahr"),
    ("Beschäftigte heuer", "2026-01", "2026-12", "jahr"),
    # keine Zeitangabe, und Jahreszahlen, die keine sind
    ("Wie viele Beschäftigte gibt es in Tirol?", None, None, None),
    ("Beschäftigte im Winterdienst", None, None, None),
    ("Was ist ÖNACE 2008 Abschnitt F?", None, None, None),
]  # fmt: skip


# Fängt: eine Alltagsformulierung wird nicht oder als falscher Zeitraum erkannt (Befund: „Sommer“ ohne Monat).
@pytest.mark.parametrize(("frage", "von", "bis", "art"), TABELLE)
def test_zeitraum_tabelle(frage: str, von: str | None, bis: str | None, art: str | None) -> None:
    zeitraum = zeitraum_lesen(frage, LETZTER)
    if von is None:
        assert zeitraum is None
        return
    assert zeitraum is not None
    assert (zeitraum.von, zeitraum.bis, zeitraum.art) == (von, bis, art)


def test_tabelle_hat_mindestens_dreissig_formulierungen() -> None:
    assert len(TABELLE) >= 30


# Fängt: die Antwort verschweigt, welche Monate gemeint sind (Jahreszeit, Quartal, ohne Jahr, jüngster Monat).
@pytest.mark.parametrize(
    ("frage", "satz"),
    [
        ("Sommer 2025", "Sommer 2025 heißt hier Juni bis August 2025."),
        ("Winter 2025", "Winter 2025 heißt hier Dezember 2024 bis Februar 2025."),
        ("Q1 2025", "Das 1. Quartal 2025 sind die Monate Jänner bis März 2025."),
        ("im ersten Halbjahr 2025", "Das 1. Halbjahr 2025 sind die Monate Jänner bis Juni 2025."),
        ("im März", "März ohne Jahr heißt hier März 2026, der jüngste März mit Daten."),
        ("letzten Monat", "Mit letzten Monat ist hier der jüngste Monat mit Daten gemeint: Juli 2026."),
        ("2025", "Mit 2025 ist hier der Durchschnitt der Monate Jänner bis Dezember 2025 gemeint."),
        (
            "November bis Februar 2025",
            "November bis Februar 2025 heißt hier November 2024 bis Februar 2025.",
        ),
    ],
)
def test_erklaerung_nennt_die_monate(frage: str, satz: str) -> None:
    zeitraum = zeitraum_lesen(frage, LETZTER)
    assert zeitraum is not None and zeitraum.erklaerung() == satz
    assert "„" not in satz  # /uc3/fragen macht Text in „…“ zu einem Knopf


# Fängt: wörtlich genannte Monate bekommen einen überflüssigen Erklärsatz.
def test_woertliche_monate_ohne_erklaerung() -> None:
    for frage in ("März 2025", "von Jänner bis März 2025", "08/2024 bis 07/2026"):
        zeitraum = zeitraum_lesen(frage, LETZTER)
        assert zeitraum is not None and zeitraum.erklaerung() is None


# Fängt: Umschreiben verliert die übrigen Wörter der Frage oder markiert eine Jahreszeit nicht als Durchschnitt.
def test_umschreiben() -> None:
    frage, notizen, mittel = umschreiben("Beschäftigte im Sommer 2025 in Wien", LETZTER)
    assert frage == "Beschäftigte im Juni 2025 bis August 2025 in Wien"
    assert notizen == ["Sommer 2025 heißt hier Juni bis August 2025."] and mittel
    frage, notizen, mittel = umschreiben("Beschäftigte von März bis Juni 2025", LETZTER)
    assert frage == "Beschäftigte von März 2025 bis Juni 2025" and notizen == [] and not mittel
    assert umschreiben("Jahresdurchschnitt 2025", LETZTER)[2]


# Fängt: ohne jüngsten Monat (noch nichts gerechnet) werden Angaben ohne Jahr geraten.
def test_ohne_daten_keine_raterei() -> None:
    assert zeitraum_lesen("im Sommer", None) is None
    assert zeitraum_lesen("letzten Monat", None) is None
    zeitraum = zeitraum_lesen("Sommer 2025", None)
    assert zeitraum is not None and (zeitraum.von, zeitraum.bis) == ("2025-06", "2025-08")


# Fängt (Prüfung astra 05.11.): Randfälle, die still eine falsche Zahl lieferten.
@pytest.mark.parametrize(
    ("frage", "von", "bis", "art", "nur"),
    [
        # gemeinsames Jahr am Ende einer Aufzählung, nicht der jüngste März
        ("im März und April 2025", "2025-03", "2025-04", "liste", ("2025-03", "2025-04")),
        ("Q1 und Q3 2025", "2025-01", "2025-09", "liste", ("2025-01", "2025-02", "2025-03", "2025-07", "2025-08", "2025-09")),
        # „des Jahres“ hinter einem Monat
        ("im März des Jahres 2025", "2025-03", "2025-03", "monat", ()),
        # aufgezählte Monate ohne die Monate dazwischen
        ("im Jänner 2025 und Juli 2025", "2025-01", "2025-07", "liste", ("2025-01", "2025-07")),
        ("Wien im Juli 2026 im Vergleich zum Juli 2025", "2025-07", "2026-07", "liste", ("2025-07", "2026-07")),
    ],
)  # fmt: skip
def test_randfaelle_astra(frage: str, von: str, bis: str, art: str, nur: tuple[str, ...]) -> None:
    zeitraum = zeitraum_lesen(frage, LETZTER)
    assert zeitraum is not None
    assert (zeitraum.von, zeitraum.bis, zeitraum.art, zeitraum.nur) == (von, bis, art, nur)


# Fängt: aufgezählte Monate werden als Durchschnitt über alle Monate dazwischen gerechnet.
def test_aufzaehlung_kein_durchschnitt_ueber_zwischenmonate() -> None:
    assert not umschreiben("Durchschnitt im Jänner 2025 und Juli 2025", LETZTER)[2]
    assert umschreiben("Durchschnitt von Jänner bis Juli 2025", LETZTER)[2]


# Fängt: mehrdeutige oder widersprüchliche Zeiträume werden still als ganzes Jahr oder anderer Winter gelesen;
# ein genannter Tag wird ohne Hinweis zum Monatsletzten.
def test_unklar_und_tag() -> None:
    from statagent.zeitraum import tag_hinweis, unklar

    assert unklar("Beschäftigte im Sommerhalbjahr 2025") == (
        "Sommerhalbjahr ist nicht eindeutig. Bitte die Monate nennen, zum Beispiel „Beschäftigte von Mai bis "
        "Oktober 2025“."
    )
    assert (
        unklar("Winter 2025/27")
        == "Winter 2025/27 passt nicht zusammen. Meinen Sie „Beschäftigte im Winter 2025/26“?"
    )
    assert unklar("Winter 2025/26") is None and unklar("Sommer 2025") is None
    assert tag_hinweis("am 1.3.2025") == (
        "Die Statistik zählt nur am Monatsletzten, darum zeigen wir für den 1. März 2025 den Stand vom "
        "31. März 2025."
    )
    assert tag_hinweis("am 2025-03-01") is not None
    assert tag_hinweis("am 31.03.2025") is None and tag_hinweis("im März 2025") is None


# Fängt: „ÖNACE 2025“ wird in uc3 frage als Berichtsjahr gelesen; ein Median wird als Durchschnitt gerechnet.
def test_klassifikationsjahr_und_median() -> None:
    from statagent.frage import jahr_ohne_monat, nicht_auswertbar

    assert jahr_ohne_monat("Beschäftigte gemäß ÖNACE 2025") is None
    assert jahr_ohne_monat("Beschäftigte 2025 nach ÖNACE 2008") == "2025"
    median = nicht_auswertbar("Median der Beschäftigten Juni 2025 bis August 2025", mittel=True)
    assert median is not None and median.startswith("Durchschnitte")
    assert nicht_auswertbar("Durchschnitt der Beschäftigten Juni 2025 bis August 2025", mittel=True) is None
