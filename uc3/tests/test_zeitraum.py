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
    # Ein Jahr an anderer Stelle gilt, nicht der jüngste passende Zeitraum (Prüfung !169, vorher still falsch)
    ("Wie viele Beschäftigte gab es 2025 im März?", "2025-03", "2025-03", "monat"),
    ("2024 im Herbst", "2024-09", "2024-11", "jahreszeit"),
    ("im Jahr 2024 im Dezember", "2024-12", "2024-12", "monat"),
    ("März in 2025", "2025-03", "2025-03", "monat"),
    ("im März letzten Jahres", "2025-03", "2025-03", "monat"),
    ("im letzten Monat des Jahres 2025", "2025-12", "2025-12", "monat"),
    ("im Mai 2025 und im Juni", "2025-05", "2025-06", "liste"),
    ("heuer im März", "2026-03", "2026-03", "monat"),
    ("heuer im Dezember", "2026-12", "2026-12", "monat"),
    ("im Dezember letztes Jahr", "2025-12", "2025-12", "monat"),
    ("im Sommer letzten Jahres", "2025-06", "2025-08", "jahreszeit"),
    ("im September letzten Jahres", "2025-09", "2025-09", "monat"),
    ("im März des Vorjahres", "2025-03", "2025-03", "monat"),
    ("2025 im Winter", "2024-12", "2025-02", "jahreszeit"),
    ("2025 im letzten Quartal", "2025-10", "2025-12", "quartal"),
    ("2025 im ersten Halbjahr", "2025-01", "2025-06", "halbjahr"),
    # Der jüngste Zeitraum bleibt, wenn gar kein Jahr dasteht; „ÖNACE 2008“ ist keines
    ("im März nach ÖNACE 2008", "2026-03", "2026-03", "monat"),
    # Klassifikationsjahre hinter Komma oder „und“ sind kein gemeinsames Jahr (Prüfung !169)
    ("Beschäftigte im März, nach ÖNACE 2025", "2026-03", "2026-03", "monat"),
    ("im März, ÖNACE 2008", "2026-03", "2026-03", "monat"),
    ("im März, Jahrgang 1975", "2026-03", "2026-03", "monat"),
    ("im März und ÖNACE 2025", "2026-03", "2026-03", "monat"),
    # Eine Menge ist kein Jahr
    ("Gab es im August 2024 über 2000 Beschäftigte in Wien?", "2024-08", "2024-08", "monat"),
    # In Lesereihenfolge bleiben Monate ohne Jahr
    ("Dezember und Jänner", "2025-12", "2026-01", "liste"),
    ("November und Dezember", "2025-11", "2025-12", "liste"),
    ("2025 im März 2025", "2025-03", "2025-03", "monat"),
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
        ("2025", "Gemeint ist der Durchschnitt der Monate Jänner bis Dezember 2025."),
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
        # das Jahr des Nachbarn in einer Aufzählung, in der genannten Reihenfolge
        ("im Mai 2025 und Juni 2026 und im Juli", "2025-05", "2026-07", "liste", ("2025-05", "2026-06", "2026-07")),
        ("März, April, Mai 2025", "2025-03", "2025-05", "liste", ("2025-03", "2025-04", "2025-05")),
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
        "Die Statistik zählt nur am letzten Tag jedes Monats. "
        "Für den 1. März 2025 zeigen wir darum den Stand vom 31. März 2025."
    )
    assert tag_hinweis("am 2025-03-01") is not None
    assert tag_hinweis("am 31.03.2025") is None and tag_hinweis("im März 2025") is None


# Fängt: ein Monat ohne Jahr neben mehreren oder fremden Jahren wird still zum jüngsten Monat.
@pytest.mark.parametrize(
    "frage",
    [
        "2024 und 2025 im März",
        "März im Vergleich zu 2025",
        "Juli 2026 im Vergleich zum Juli",
        "2025/26 im Winter",
        "letzten Monat im Vergleich zu 2025",
        "die letzten 3 Monate 2025",
        # Nachbar-Jahr würde die Reihenfolge umdrehen: nicht raten
        "Dezember 2025 und Jänner",
        "Herbst 2025 und Winter",
        "Q4 2025 und Jänner",
        # Vorjahr als zweiter Zeitpunkt
        "Wie hat sich der März zum Vorjahr entwickelt?",
        "Veränderung zum Vorjahr im März",
        "Beschäftigte im März und im Vorjahr",
        # Jahr und Monat als zwei Dinge
        "Jahresdurchschnitt 2025 und März",
        "2025 und im März",
        "2024 im März und im April 2025",
        "2024 im Herbst 2025",
        # gegen die Lesereihenfolge
        "im Juli und August",
        "Mai und Oktober",
        "im Juni, Juli und August",
        "Dezember und Jänner 2025",
        # relative Jahre, die wir nicht auflösen
        "vor zwei Jahren im März",
        "vorletztes Jahr im März",
    ],
)
def test_jahr_nicht_zuzuordnen_fragt_zurueck(frage: str) -> None:
    from statagent.zeitraum import unklar

    grund = unklar(frage, LETZTER)
    assert grund is not None and "„Beschäftigte im" in grund


# Fängt: Rückfrage, obwohl die Frage gar kein Jahr nennt; Klassifikationsjahre gelten als Berichtsjahr.
@pytest.mark.parametrize(
    ("frage", "nur"),
    [
        ("Beschäftigte im März und letzten Monat", ("2026-03", "2026-07")),
        ("Juni und letzten Monat vergleichen", ("2026-06", "2026-07")),
        ("Klassifikation 2025 im März", ()),
        ("Jahrgang 2025 im März", ()),
        ("Beschäftigte im März PLZ 2025", ()),
        ("Betriebe mit 2025 Mitarbeitern im März", ()),
        ("Beschäftigte im März mit 2025 Euro", ()),
    ],
)
def test_ohne_jahr_keine_rueckfrage(frage: str, nur: tuple[str, ...]) -> None:
    from statagent.zeitraum import unklar

    zeitraum = zeitraum_lesen(frage, LETZTER)
    assert unklar(frage, LETZTER) is None and zeitraum is not None
    assert zeitraum.nur == nur if nur else zeitraum.von == "2026-03"


# Fängt: Eine Jahresangabe neben einem Zeitraum fällt still weg, auch wenn die Zahl schon vorkommt (Prüfung !169).
@pytest.mark.parametrize(
    ("frage", "beispiel"),
    [
        ("März 2025 im Vergleich zum Vorjahr", "„Beschäftigte im März 2025 und im März 2024“"),
        ("März 2025 zum Vorjahr", "„Beschäftigte im März 2025 und im März 2024“"),
        ("März 2025 und Vorjahr", "„Beschäftigte im März 2025 und im März 2024“"),
        ("Sommer 2025 im Vergleich zum Vorjahr", "„Beschäftigte im Juni 2025 und im Juni 2024“"),
        ("Juli 2026 im Vergleich zum Vorjahr", "„Beschäftigte im Juli 2026 und im Juli 2025“"),
        ("März 2025 und 2026", "„Beschäftigte im März 2025 und im März 2026“"),
        ("Sommer 2024 und 2025", "„Beschäftigte im Juni 2024 und im Juni 2025“"),
    ],
)
def test_freies_jahr_neben_einem_zeitraum_fragt_nach_beiden(frage: str, beispiel: str) -> None:
    from statagent.zeitraum import unklar

    grund = unklar(frage, LETZTER)
    assert grund is not None and grund.startswith("Bitte beide Monate") and beispiel in grund


# Fängt: Der Text der Rückfrage passt nicht zur Frage: „Bitte Monat und Jahr nennen“ bei zwei bloßen Jahren, oder ein
# abgeschnittener Satzanfang bei relativen Angaben.
def test_rueckfragetext_passt_zur_frage() -> None:
    from statagent.zeitraum import unklar

    for frage, von_bis in (
        ("Zeitreihe 2024 bis 2026", "01/2024 bis 12/2026"),
        ("Jahresdurchschnitt 2024 und 2025", "01/2024 bis 12/2025"),
    ):
        grund = unklar(frage, LETZTER)
        assert grund is not None and f"„Zeitreihe {von_bis}“" in grund
    assert (unklar("die letzten 3 Monate 2025", LETZTER) or "").startswith("Die letzten Monate und ein Jahr")
    assert (unklar("letzten Monat im Vergleich zu 2025", LETZTER) or "").startswith(
        "Der letzte Monat und ein Jahr"
    )


# Fängt: „für 2026 gibt es zwölf Werte“ und ein Vorschlag, der zu „keine Daten“ führt (2026 nur bis Juli, 2024 ab August).
def test_jahr_rueckfrage_aus_vorhandenen_monaten() -> None:
    from statagent.uc4 import jahr_rueckfrage

    def text(jahr: str) -> str:
        return jahr_rueckfrage("die Zahl der Beschäftigten", "Beschäftigte", jahr, "2024-08", "2026-07")

    assert "zwölf Werte" in text("2025") and "„Beschäftigte Dezember 2025“" in text("2025")
    assert "„Zeitreihe 01/2025 bis 12/2025“" in text("2025")
    assert "7 Werte, Jänner bis Juli 2026" in text("2026") and "„Beschäftigte Juli 2026“" in text("2026")
    assert "„Zeitreihe 01/2026 bis 07/2026“" in text("2026") and "Dezember 2026" not in text("2026")
    assert "5 Werte, August bis Dezember 2024" in text("2024") and "„Zeitreihe 08/2024 bis 12/2024“" in text(
        "2024"
    )
    assert text("2023").startswith("Für 2023 gibt es keine Daten, nur für August 2024 bis Juli 2026.")


# Fängt: Das zugewiesene Jahr bleibt doppelt im Text stehen, uc3 frage liest dann ein zweites Jahr.
def test_umschreiben_nimmt_das_freie_jahr_heraus() -> None:
    from statagent.frage import jahr_ohne_monat

    for frage, monate_text in (
        ("Wie viele Beschäftigte gab es 2025 im März?", "März 2025"),
        ("im März letzten Jahres in Wien", "März 2025"),
        ("2024 im Herbst", "September 2024 bis November 2024"),
    ):
        neu = umschreiben(frage, LETZTER)[0]
        assert monate_text in neu and jahr_ohne_monat(neu) is None and "letzten" not in neu


# Fängt: „ÖNACE 2025“ wird in uc3 frage als Berichtsjahr gelesen; ein Median wird als Durchschnitt gerechnet.
def test_klassifikationsjahr_und_median() -> None:
    from statagent.frage import jahr_ohne_monat, nicht_auswertbar

    assert jahr_ohne_monat("Beschäftigte gemäß ÖNACE 2025") is None
    assert jahr_ohne_monat("Beschäftigte 2025 nach ÖNACE 2008") == "2025"
    median = nicht_auswertbar("Median der Beschäftigten Juni 2025 bis August 2025", mittel=True)
    assert median is not None and median.startswith("Durchschnitte")
    assert nicht_auswertbar("Durchschnitt der Beschäftigten Juni 2025 bis August 2025", mittel=True) is None
