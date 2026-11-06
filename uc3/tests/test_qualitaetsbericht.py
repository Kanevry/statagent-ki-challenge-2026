"""Qualitätsbericht aus der Fixture-Datenbank (Läufe 2024-08 und 2024-09)."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from statagent.berichte.pruefe_abgabe import bericht_maengel, einstufungen_aus_bericht
from statagent.berichte.qualitaetsbericht import (
    ABSCHNITTE,
    GUELTIGE_EINSTUFUNGEN,
    HINWEIS_NUR_GELIEFERT,
    BerichtFehler,
    _auffaelligkeiten_daten,
    _lesbar,
    _md_revision,
    _rueckfragen,
    _rueckfragen_daten,
    _ueberblick,
    _verweise,
    bericht_daten,
    bericht_erzeugen,
    bericht_schreiben,
    grundlage_kurz,
    im_zeitraum,
    text_glaetten,
    zahl,
)
from statagent.db import Verbindung
from statagent.lauf import lauf_ausfuehren, veroeffentlichen
from statagent.regeln import regeln_freigeben

NAME = "Lena Gruber"


def _abschnitt(text: str, nr: int) -> str:
    """Text des Abschnitts `nr` (1–5) ohne die folgenden Abschnitte."""
    anfang = text.index(ABSCHNITTE[nr - 1])
    ende = text.index(ABSCHNITTE[nr]) if nr < len(ABSCHNITTE) else len(text)
    return text[anfang:ende]


def _laeufe(conn: Verbindung) -> int:
    lauf_ausfuehren(conn, "2024-08", regelsatz="v1", gestartet_von=None)
    return lauf_ausfuehren(conn, "2024-09", regelsatz="v1", gestartet_von=None).lauf_id


def _lauf(conn: Verbindung, lauf_id: int) -> dict[str, object]:
    zeile = conn.execute("SELECT * FROM meta.lauf WHERE id = %s", (lauf_id,)).fetchone()
    assert zeile is not None
    return zeile


def test_bericht_folgt_vorlage_und_meta_lauf(conn: Verbindung) -> None:
    # Fängt: Abschnitte fehlen/vertauscht, Kennzahlen nicht aus meta.lauf, Abrechnung fehlt oder falsch.
    lauf = _lauf(conn, _laeufe(conn))
    text = bericht_erzeugen(conn, "2024-09")
    ueberschriften = [z for z in text.splitlines() if z.startswith("## ")]
    assert ueberschriften == list(ABSCHNITTE)
    assert text.startswith("# Qualitätsbericht – Berichtsmonat 2024-09\n")
    assert "freigegeben von: noch nicht freigegeben" in text
    assert "> **Status: vorläufig.** Die Zahlen für September 2024 sind vorläufig." in text
    assert "Die Regeln sind noch nicht mit Namen freigegeben." in text

    g, z, n, a = (int(str(lauf[k])) for k in ("gelesen", "gezaehlt", "nicht_gezaehlt", "ausgeschlossen"))
    assert f"| gelesene Sätze | {zahl(g)} |" in text
    assert f"| davon gezählt am Stichtag | {zahl(z)} |" in text
    assert f"| Beschäftigungsverhältnisse am Stichtag | {zahl(z)} |" in text
    assert (
        f"Abrechnung in Zahlen: {zahl(g)} gelesen = {zahl(z)} gezählt + {zahl(n)} nicht gezählt"
        f" + {zahl(a)} ausgeschlossen (geht auf)."
    ) in text
    assert "Annahme A8" not in text and "Die Vorlage hat keine Zeile „nicht gezählt“" in text
    assert "gegenüber 2024-08" in text
    assert f"Ergebnis-Hash `{lauf['ergebnis_hash']}`" in text
    assert bericht_maengel(text) == []


def test_bericht_ist_bytegleich_und_wird_geschrieben(conn: Verbindung, tmp_path: Path) -> None:
    # Fängt: Zeitstempel „jetzt“, unsortierte Abfragen oder Mengen-Iteration im Bericht.
    _laeufe(conn)
    pfad = bericht_schreiben(conn, "2024-09", ziel=tmp_path / "a" / "2024-09.md")
    assert pfad.read_bytes() == bericht_erzeugen(conn, "2024-09").encode("utf-8")
    assert bericht_erzeugen(conn, "2024-09") == bericht_erzeugen(conn, "2024-09")


def test_auffaelligkeit_mit_einstufung_beleg_und_anhalten(conn: Verbindung) -> None:
    # Fängt: Einstufungs-Code statt Vorlagentext, Beleg-SQL fehlt, angehaltene Prüfung nicht als Grund genannt.
    lauf_id = _laeufe(conn)
    regel = conn.execute(
        """INSERT INTO meta.regel (regelsatz, name, typ, art, reihenfolge, beschreibung, begruendung, grundlage)
           VALUES ('v1', 'P90_testpruefung', 'pruefung', 'test', 90, 'Testprüfung', 'Test', 'Test')
           RETURNING id"""
    ).fetchone()
    assert regel is not None
    for ebene, einstufung, anhalten in (("satz", "erklaert-datenproblem", False), ("aggregat", None, True)):
        conn.execute(
            """INSERT INTO meta.pruefung_treffer (lauf_id, regel_id, ebene, anzahl, einstufung, anhalten, beleg_sql)
               VALUES (%s, %s, %s, 3, %s, %s, 'SELECT vvh_id FROM roh.lieferung WHERE lieferung = ''2024-09''')""",
            (lauf_id, regel["id"], ebene, einstufung, anhalten),
        )
    text = bericht_erzeugen(conn, "2024-09")
    zeilen_p90 = [z for z in text.splitlines() if z.startswith("|") and "Testprüfung" in z]
    assert len(zeilen_p90) == 2
    assert "erklärt – Datenproblem" in zeilen_p90[0] and "nicht erklärbar" in zeilen_p90[1]
    assert set(einstufungen_aus_bericht(text)) <= GUELTIGE_EINSTUFUNGEN
    assert "</summary>" in text and "P90_testpruefung</summary>" in text
    (grund,) = re.findall(r"Deshalb ist der Monat angehalten \(([^)]*)\)\.", text)
    assert "P90_testpruefung" in grund.split(", ")
    assert bericht_maengel(text) == []


def test_ohne_lauf_gibt_es_keinen_bericht(conn: Verbindung) -> None:
    # Fängt: ein Bericht aus leeren Kennzahlen, wenn der Monat nie gerechnet wurde.
    with pytest.raises(BerichtFehler):
        bericht_erzeugen(conn, "2024-09")


def test_veroeffentlichter_monat_zeigt_den_veroeffentlichenden_lauf(conn: Verbindung) -> None:
    # Fängt: nach einem Regelwechsel zeigt der Bericht eines veröffentlichten Monats in § 2 und § 4 Treffer und
    # Wirkung des neuen Regelstands und im Kopf „VORLÄUFIG“, obwohl § 1 die veröffentlichten Zahlen zeigt.
    erster = lauf_ausfuehren(conn, "2024-08", "v1")
    regeln_freigeben(conn, "v1", NAME)
    veroeffentlichen(conn, "2024-08", "v1", NAME)
    conn.execute(  # neuer Regelstand: ÖNACE 'D' wird wie 'C' zugeordnet (nicht freigegeben)
        b"""UPDATE stat.quellzuordnung SET code = 'C'
            WHERE regelsatz = 'v1' AND merkmal = 'oenace' AND version = '2008' AND geliefert = 'D'"""
    )
    zweiter = lauf_ausfuehren(conn, "2024-08", "v1")
    assert zweiter.ergebnis_status == "endgueltig" and zweiter.lauf_id != erster.lauf_id
    # Der neue Lauf sieht etwas anderes: eine Prüfung, die anhält, und eine andere Regelwirkung.
    regel = conn.execute(
        """INSERT INTO meta.regel (regelsatz, name, typ, art, reihenfolge, beschreibung, begruendung, grundlage)
           VALUES ('v1', 'P90_testpruefung', 'pruefung', 'test', 90, 'Testprüfung', 'Test', 'Test')
           RETURNING id"""
    ).fetchone()
    assert regel is not None
    conn.execute(
        """INSERT INTO meta.pruefung_treffer (lauf_id, regel_id, ebene, anzahl, einstufung, anhalten, beleg_sql)
           VALUES (%s, %s, 'aggregat', 7, NULL, TRUE, 'SELECT 1')""",
        (zweiter.lauf_id, regel["id"]),
    )
    wirkung = conn.execute(
        """UPDATE meta.regel_wirkung SET saetze = 987654
           WHERE lauf_id = %s AND regel_id = (SELECT min(regel_id) FROM meta.regel_wirkung WHERE lauf_id = %s)
           RETURNING regel_id""",
        (zweiter.lauf_id, zweiter.lauf_id),
    ).fetchall()
    assert len(wirkung) == 1

    text = bericht_erzeugen(conn, "2024-08")
    assert "VORLÄUFIG" not in text
    assert (
        "> **Status: endgültig.** Die Zahlen für August 2024 sind endgültig. Lena Gruber hat sie am " in text
    )
    assert f"| davon gezählt am Stichtag | {zahl(erster.gezaehlt)} |" in _abschnitt(text, 1)
    alte_treffer = conn.execute(
        "SELECT r.name FROM meta.pruefung_treffer t JOIN meta.regel r ON r.id = t.regel_id "
        "WHERE t.lauf_id = %s AND t.anzahl > 0",
        (erster.lauf_id,),
    ).fetchall()
    for t in alte_treffer:
        assert str(t["name"]) in _abschnitt(text, 2)
    assert "Testprüfung" not in _abschnitt(text, 2)
    assert zahl(987654) not in _abschnitt(text, 4)
    revision = _abschnitt(text, 5)
    assert f"veröffentlichenden Lauf {erster.lauf_id}" in revision
    assert "P90_testpruefung (Aggregat, 7 Sätze, hätte angehalten)" in revision
    assert "Umschichtung" in revision and re.search(
        r"\| 2024-08 \| ÖNACE-Abschnitt \| [^|]*\(C\) \|", revision
    )
    assert bericht_maengel(text) == []


def test_umschichtung_ist_revisionsbedarf(conn: Verbindung) -> None:
    # Fängt: § 5 liest nur „insgesamt“; C +10 / D −10 erscheint dann als „kein Revisionsbedarf“.
    lauf_id = _laeufe(conn)
    conn.execute(
        "UPDATE meta.revision SET aktuell = veroeffentlicht WHERE lauf_id = %s AND berichtsmonat = '2024-08'",
        (lauf_id,),
    )
    geaendert = conn.execute(
        """UPDATE meta.revision SET aktuell = veroeffentlicht + CASE schluessel WHEN 'C' THEN 10 ELSE -10 END
           WHERE lauf_id = %s AND berichtsmonat = '2024-08' AND gliederung = 'oenace' AND schluessel IN ('C', 'D')
           RETURNING schluessel""",
        (lauf_id,),
    ).fetchall()
    assert len(geaendert) == 2
    revision = _abschnitt(bericht_erzeugen(conn, "2024-09"), 5)
    assert "Kein Revisionsbedarf" not in revision
    assert "Umschichtung zwischen Ausprägungen, insgesamt unverändert" in revision
    zeilen = [z for z in revision.splitlines() if z.startswith("| 2024-08 | ÖNACE-Abschnitt |")]
    # Klarnamen statt Codes in § 5 (Review-Bank 69, Runde 3), der Abschnittsbuchstabe bleibt in Klammern.
    assert [z.split(" | ")[2][-3:] for z in zeilen] == ["(C)", "(D)"]
    assert zeilen[0].endswith("| +10 |") and zeilen[1].endswith("| -10 |")


def test_abrechnung_nennt_fortgeschriebene_verhaeltnisse(conn: Verbindung) -> None:
    # Fängt: mit Fortschreibung (E07) sagt die Prosa „gelesen = gezählt + …“ und die Tabelle trennt geliefert
    # gezählte und fortgeschriebene Verhältnisse nicht.
    lauf = dict(_lauf(conn, _laeufe(conn)))
    lauf["fortgeschrieben"], lauf["gezaehlt"] = 5, int(str(lauf["gezaehlt"])) + 5
    text = "\n".join(_ueberblick(conn, lauf, "2024-09", "v1"))
    z = int(str(lauf["gezaehlt"]))
    assert f"| davon geliefert gezählt (ohne fortgeschriebene) | {zahl(z - 5)} |" in text
    assert "| Beschäftigungsverhältnisse am Stichtag (mit fortgeschriebenen, Regel E07) |" in text
    assert "| davon fortgeschrieben aus der Vorlieferung (Regel E07, vorläufig) | 5 |" in text
    assert (
        "Abrechnung: gelesene Sätze + fortgeschriebene Verhältnisse = gezählte + nicht gezählte"
        " + ausgeschlossene Sätze."
    ) in text
    assert " + 5 fortgeschrieben = " in text and "(geht auf)" in text


def test_freigabe_kommt_vom_freigegebenen_lauf(conn: Verbindung) -> None:
    # Fängt: zweimal gerechnet mit gleichem Ergebnis, dann veröffentlicht. Die Zellen hängen am ersten Lauf, die
    # Freigabe am zweiten; der Bericht las Name und Zeitpunkt vom ersten und sagte „noch nicht freigegeben“.
    erster = lauf_ausfuehren(conn, "2024-08", "v1")
    zweiter = lauf_ausfuehren(conn, "2024-08", "v1")
    regeln_freigeben(conn, "v1", NAME)
    veroeffentlichen(conn, "2024-08", "v1", NAME)
    zellen = conn.execute(
        "SELECT min(lauf_id) AS id FROM stat.stat_beschaeftigte WHERE status = 'endgueltig'"
    ).fetchone()
    freigegeben = conn.execute(
        "SELECT id FROM meta.lauf WHERE lieferung = '2024-08' AND freigegeben_von IS NOT NULL"
    ).fetchall()
    assert zellen is not None and zellen["id"] == erster.lauf_id
    assert [z["id"] for z in freigegeben] == [zweiter.lauf_id]
    text = bericht_erzeugen(conn, "2024-08")
    assert "noch nicht freigegeben" not in text
    assert f"freigegeben von: {NAME} am " in text and f"{NAME} hat sie am " in text

    # Fängt (Review-Bank 69): § 2 kam vom Lauf mit den Zellen (erster), nicht vom freigegebenen (zweiter);
    # Prüfregeln stehen nicht im Regelstand, die beiden Läufe können also verschieden treffen. Und ein weiterer
    # Lauf mit gleichem Regelstand galt als „mit geänderten Regeln nachgerechnet“.
    dritter = lauf_ausfuehren(conn, "2024-08", "v1")
    regel = conn.execute(
        """INSERT INTO meta.regel (regelsatz, name, typ, art, reihenfolge, beschreibung, begruendung, grundlage)
           VALUES ('v1', 'P90_testpruefung', 'pruefung', 'test', 90, 'Testprüfung', 'Test', 'Test')
           RETURNING id"""
    ).fetchone()
    assert regel is not None
    for lauf_id, anzahl in ((erster.lauf_id, 11), (zweiter.lauf_id, 22)):
        conn.execute(
            """INSERT INTO meta.pruefung_treffer (lauf_id, regel_id, ebene, anzahl, einstufung, anhalten)
               VALUES (%s, %s, 'satz', %s, 'erklaert-datenproblem', FALSE)""",
            (lauf_id, regel["id"], anzahl),
        )
    text = bericht_erzeugen(conn, "2024-08")
    assert dritter.lauf_id > zweiter.lauf_id and f"Lauf {dritter.lauf_id}," in text
    paragraf2 = _abschnitt(text, 2)
    assert "Testprüfung (22 Sätze)" in paragraf2 and "Testprüfung (11 Sätze)" not in paragraf2
    assert "nachgerechnet" not in _abschnitt(text, 5)


def test_saetze_sind_einfach_und_struktur_passt_zum_markdown(conn: Verbindung) -> None:
    # Fängt: Regelcode statt Satz als Hauptaussage in § 2, Platzhalter ungefüllt, Gedankenstriche oder „·“ in
    # Sätzen, Annahmen fehlen im Bericht, JSON-Struktur und Markdown rechnen auseinander.
    _laeufe(conn)
    daten = bericht_daten(conn, "2024-09")
    text = bericht_erzeugen(conn, "2024-09")
    assert daten["auffaelligkeiten"], "Fixture ohne Prüftreffer"
    for a in daten["auffaelligkeiten"]:
        assert "{" not in a["satz"] and not a["satz"].startswith(a["regel"])
        assert f"| {a['satz']} ({a['regel']}) |" in text.replace("\\|", "|")
    for satz in [*daten["status_saetze"], *(a["satz"] for a in daten["auffaelligkeiten"])]:
        assert "—" not in satz and " – " not in satz and "·" not in satz
    assert "—" not in text and "·" not in text
    assert daten["kennzahlen"]["abrechnung_in_zahlen"] in text
    nrn = [a["nr"] for a in daten["annahmen"]]
    assert "F4" in nrn and "F9" not in nrn
    assert "- Annahme F4: " in _abschnitt(text, 4)
    assert "Begriffe: Ein Verhältnis ist ein Beschäftigungsverhältnis, nicht eine Person." in text


def _pruef_treffer(
    name: str, pruef_regel: str | None, rueckfrage: str | None, einstufung: str
) -> dict[str, object]:
    # Prüftreffer wie aus _treffer, Werte erfunden; die Rückfragen kommen aus 130_rueckfragen.sql.
    return {
        "ebene": "satz",
        "anzahl": 3,
        "umfang": None,
        "einstufung": einstufung,
        "massnahme": "x",
        "anhalten": False,
        "beleg_sql": None,
        "rueckfrage": rueckfrage,
        "name": name,
        "pruef_regel": pruef_regel,
        "beschreibung": "x",
        "satz_vorlage": None,
    }


def test_rueckfragen_je_monat_vollstaendig_und_ohne_doppelung(conn: Verbindung) -> None:
    # Fängt: § 2 zeigt „–“ bei P01/P03, obwohl R7/R5 ihre geprüfte Einleseregel umsetzen; „neu“ statt
    # Klartext; R5 (nur Lieferung 2025-06) erscheint in jedem späteren Monat (#126); die Frage wird
    # mitten im Wort gekürzt; § 3 sagt „Bis zur Antwort gilt: So machen wir es bis zur Antwort: …“.
    rueckfragen = _rueckfragen(conn)
    treffer = [
        _pruef_treffer("P01_volldubletten", "E02_volldubletten", None, "erklaert-datenproblem"),
        _pruef_treffer("P03_spaltentausch", "E01_spaltentausch_beginn_ende", None, "erklaert-datenproblem"),
        _pruef_treffer("P06_alter_unplausibel", "R5_alter", "R6", "erklaert-datenproblem"),
        _pruef_treffer("P12_code_unbekannt", "Q03_sonst_unbekannt", "neu", "nicht-erklaerbar"),
        _pruef_treffer("P23_revision_vormonat", None, "neu", "erklaert-plausibel"),
    ]
    # Über regel_name nur im Monat der Rückfrage: R7 gilt für 2025-03, R5 für 2025-06.
    spalte = [a["rueckfragen"] for a in _auffaelligkeiten_daten(treffer, rueckfragen, "2025-03")]
    assert spalte == [["R7"], [], ["R6"], ["noch keine Rückfrage gestellt"], ["keine Rückfrage nötig"]]
    assert _auffaelligkeiten_daten(treffer[1:2], rueckfragen, "2025-06")[0]["rueckfragen"] == ["R5"]
    # Fängt: P07 (erklärt – plausibel) erbte über seine Regel R5_alter die Rückfrage R1; P14 (nicht erklärbar,
    # ohne Rückfrage) zeigte „–“.
    spaeter = [
        _pruef_treffer("P07_alter_hoch_plausibel", "R5_alter", None, "erklaert-plausibel"),
        _pruef_treffer("P90_ohne_rueckfrage", None, None, "nicht-erklaerbar"),
    ]
    spalte = [a["rueckfragen"] for a in _auffaelligkeiten_daten(spaeter, rueckfragen, "2025-10")]
    assert spalte == [["keine Rückfrage nötig"], ["noch keine Rückfrage gestellt"]]

    oktober = {r["nr"] for r in _rueckfragen_daten("2025-10", [], rueckfragen)}
    # Einzelmonate nur im eigenen Monat, „alle“ ab ab_lieferung; R8 gehört zur Prüfregel P19 und steht nur mit
    # einem Treffer, der auf sie verweist, in § 3 (Runde 4).
    assert oktober == {"R1", "R3", "R6"}
    p19 = _pruef_treffer("P19_phantom_doppelmeldung", None, "R8", "nicht-erklaerbar")
    assert "R8" in {r["nr"] for r in _rueckfragen_daten("2025-10", [p19], rueckfragen)}
    assert "R5" not in {r["nr"] for r in _rueckfragen_daten("2025-10", treffer[1:2], rueckfragen)}

    for r in _rueckfragen_daten("2024-08", [], rueckfragen):
        assert not r["frage"].endswith("…"), r["nr"]
        assert r["antwort"].count("bis zur Antwort") + r["antwort"].count("Bis zur Antwort") == 1, r["nr"]
    r1 = next(r for r in _rueckfragen_daten("2024-08", [], rueckfragen) if r["nr"] == "R1")
    assert r1["antwort"].startswith("Noch offen. Bis zur Antwort gilt: Wir lesen Monat 13")
    assert r1["frage"].endswith("nur mit der Differenz der Jahre?")


def test_befundtexte_im_format_des_berichts() -> None:
    # Fängt: „-4410“ ohne Tausenderpunkt aus `:+d` (2025-10), „1 Gruppen … haben“ und „1 Zellen“ (2024-11,
    # 2025-11); Monate wie „2025-08“ dürfen dabei nicht zu Zahlen werden.
    assert text_glaetten("2025-08: -4410 (1,1 %), 2025-09: +1151 (0,3 %), 2025-10: -12") == (
        "2025-08: -4.410 (1,1 %), 2025-09: +1.151 (0,3 %), 2025-10: -12"
    )
    assert (
        text_glaetten(
            "1 Gruppen mit mindestens 500 Verhältnissen haben sich verändert (1 Zellen (0 ohne Saisonerklärung))."
        )
        == "1 Gruppe mit mindestens 500 Verhältnissen hat sich verändert (1 Zelle (0 ohne Saisonerklärung))."
    )
    assert (
        text_glaetten("21 Zellen, 11 Gruppen, Bei 1 Verhältnissen")
        == "21 Zellen, 11 Gruppen, Bei 1 Verhältnis"
    )


def test_nur_gelieferte_pruefung_erklaert_abweichung_vom_ueberblick(conn: Verbindung) -> None:
    # Fängt: 2025-10 nennt „Bestand am Stichtag“ einmal 313.154 (P15, nur geliefert) und einmal 390.900 (mit E07),
    # ohne zu sagen, welche Zahl welche ist.
    t = _pruef_treffer("P15_bestand_vs_vormonat", None, "R3", "erklaert-datenproblem")
    t["beleg_sql"] = "SELECT count(*) FROM bereinigt.abschnitt WHERE herkunft = 'geliefert'"
    rueckfragen = _rueckfragen(conn)
    mit = _auffaelligkeiten_daten([t], rueckfragen, "2025-10", mit_fortschreibung=True)[0]["satz"]
    ohne = _auffaelligkeiten_daten([t], rueckfragen, "2025-10")[0]["satz"]
    assert mit.endswith(HINWEIS_NUR_GELIEFERT) and HINWEIS_NUR_GELIEFERT not in ohne


def test_json_fuer_weboberflaeche_und_erster_monat(conn: Verbindung) -> None:
    # Fängt: #126-Felder fehlen auf oberster Ebene; pruefungen_gelaufen zählt Zeilen statt Prüfregeln;
    # 2024-08 sagt nur „kein Revisionsabgleich“ ohne Grund.
    lauf = _lauf(conn, lauf_ausfuehren(conn, "2024-08", "v1").lauf_id)
    daten = bericht_daten(conn, "2024-08")
    regeln = conn.execute(
        "SELECT count(DISTINCT regel_id) AS n FROM meta.pruefung_treffer WHERE lauf_id = %s", (lauf["id"],)
    ).fetchone()
    assert regeln is not None and regeln["n"] > 0
    assert (daten["lauf_id"], daten["regelstand"]) == (lauf["id"], lauf["regelstand"])
    assert daten["umgeschichtet"] == lauf["fortgeschrieben"]
    assert daten["pruefungen_gelaufen"] == regeln["n"]
    assert "August 2024 der erste gerechnete Monat ist" in str(daten["revision"]["satz"])


def test_klarnamen_statt_codes_und_zeilenvergleich_mit_richtung() -> None:
    # Fängt: „oenace A“, „region 5“, „Alter unbekannt (-1)“, „(UNB bzw. 0)“ im Bericht und „mehr oder weniger
    # Zeilen (345.078 / 434.104 …)“ ohne Richtung (2024-08, 2024-09, 2025-10).
    namen = {("oenace", "A"): "Land- und Forstwirtschaft, Fischerei (A)", ("region", "5"): "Salzburg"}
    t = _pruef_treffer("P14_sprung_aggregat", None, None, "nicht-erklaerbar")
    t["umfang"], t["massnahme"] = (
        "2 Zellen: oenace A -3,1 %, region 5 4,9 %, oenace ZZ 1 %",
        "Alter unbekannt (-1), zählt",
    )
    (lesbar,) = _lesbar([t], namen)
    assert (
        lesbar["umfang"]
        == "2 Zellen: Land- und Forstwirtschaft, Fischerei (A) -3,1 %, Salzburg 4,9 %, oenace ZZ 1 %"
    )
    assert lesbar["massnahme"] == "Alter unbekannt, zählt"
    assert _lesbar([t | {"massnahme": "unbekannt (UNB bzw. 0), Satz zählt"}], namen)[0]["massnahme"] == (
        "unbekannt, Satz zählt"
    )
    assert (
        text_glaetten(
            "Die Lieferung hat deutlich mehr oder weniger Zeilen als die vorige (345.078 / 434.104 Zeilen gegen 2025-09"
            " (-20,5 %))."
        )
        == "Die Lieferung hat deutlich weniger Zeilen als die vorige (345.078 Zeilen statt 434.104 in 2025-09 (-20,5 %))."
    )


def test_status_nennt_anhalten_einmal_und_revision_sagt_damals_vorlaeufig(conn: Verbindung) -> None:
    # Fängt: „Deshalb ist der Monat angehalten“ je Befund (2025-10 dreimal); § 5 markiert einen inzwischen
    # endgültigen Vormonat als „(vorläufig)“; 2024-08 zeigt einen leeren Tabellenkopf in § 5.
    lauf_id = _laeufe(conn)
    assert "| Berichtsmonat |" not in _abschnitt(bericht_erzeugen(conn, "2024-08"), 5)
    regeln_freigeben(conn, "v1", NAME)
    veroeffentlichen(conn, "2024-08", "v1", NAME)
    conn.execute(
        "UPDATE meta.revision SET aktuell = veroeffentlicht + 7, status_vorher = 'vorlaeufig'"
        " WHERE lauf_id = %s AND berichtsmonat = '2024-08' AND gliederung = 'insgesamt'",
        (lauf_id,),
    )
    for nr in (91, 92):
        regel = conn.execute(
            f"""INSERT INTO meta.regel (regelsatz, name, typ, art, reihenfolge, beschreibung, begruendung, grundlage)
               VALUES ('v1', 'P{nr}_test', 'pruefung', 'test', {nr}, 'Testprüfung {nr}', 'Test', 'Test')
               RETURNING id""".encode()
        ).fetchone()
        assert regel is not None
        conn.execute(
            """INSERT INTO meta.pruefung_treffer (lauf_id, regel_id, ebene, anzahl, einstufung, anhalten)
               VALUES (%s, %s, 'lieferung', 1, 'erklaert-datenproblem', TRUE)""",
            (lauf_id, regel["id"]),
        )
    text = bericht_erzeugen(conn, "2024-09")
    (grund,) = re.findall(r"Deshalb ist der Monat angehalten \(([^)]*)\)\.", text)
    assert {"P91_test", "P92_test"} <= set(grund.split(", "))
    zeile = next(z for z in _abschnitt(text, 5).splitlines() if z.startswith("| 2024-08 |"))
    assert "(damals vorläufig)" in zeile


def test_saisonmonat_und_revision_aus_lieferausfall_verweisen_richtig() -> None:
    # Fängt (Runde 3): P14 im Saisonmonat (erklärt – plausibel) zeigte R10 über regel_name, auch in Monaten,
    # die R10 nicht nennt; P23 in 2025-10/2025-11 zeigte „noch keine Rückfrage gestellt“ statt R3 (Teil-Lieferung).
    rueckfragen: list[dict[str, object]] = [
        {
            "nr": "R10",
            "regel_name": "P14_sprung_aggregat",
            "lieferungen": "lieferung_2024-09",
            "ab_lieferung": None,
        },
    ]
    p14 = _pruef_treffer("P14_sprung_aggregat", None, None, "erklaert-plausibel")
    assert _verweise(p14, rueckfragen, "2024-09") == []
    p14_offen = p14 | {"einstufung": "nicht-erklaerbar"}
    assert _verweise(p14_offen, rueckfragen, "2024-09") == ["R10"]
    # Runde 4: Zur eigenen Prüfregel gilt die Rückfrage in jedem Monat (v2 springt in anderen Monaten als v1).
    assert _verweise(p14_offen, rueckfragen, "2024-11") == ["R10"]
    p23 = _pruef_treffer("P23_revision_vormonat", None, "neu", "nicht-erklaerbar") | {
        "art": "revision_vormonat",
        "umfang": "2025-10: +343 (0,1 %)",
    }
    ausfall = {"2025-10": ["R3"]}
    assert _verweise(p23, rueckfragen, "2025-10", ausfall) == ["R3"]
    assert _verweise(p23, rueckfragen, "2025-11", ausfall) == ["R3"]  # Revision des Ausfallmonats
    assert _verweise(p23 | {"umfang": "2025-12: +5 (0,0 %)"}, rueckfragen, "2026-01", ausfall) == []


def test_grundlage_nennt_den_kern_statt_der_ganzen_anweisung() -> None:
    # Fängt (Runde 3): § 4 zeigte in v2 die ganze Agenten-Anweisung (980 Zeichen) als Grundlage.
    lang = (
        "Fachbeschreibung § 4 Nr. 1, 2, 4; Vorschlag uc3/25: Auftrag 2, ganzes Monat statt Stichtag: "
        + "Text " * 200
    )
    assert (
        grundlage_kurz(lang)
        == "Fachbeschreibung § 4 Nr. 1, 2, 4; Vorschlag uc3/25: Auftrag 2, ganzes Monat statt Stichtag"
    )
    ohne = grundlage_kurz("Wort " * 100)
    assert len(ohne) <= 160 and ohne.endswith("Wort…")
    assert grundlage_kurz("Fachbeschreibung § 4 Nr. 6") == "Fachbeschreibung § 4 Nr. 6"


def test_v2_ueberblick_zaehlt_im_berichtsmonat(conn: Verbindung) -> None:
    # Fängt (Runde 3, Blocker): v2 zählt die Zeitraumart „Monat“, § 1 filterte fest auf „Stichtag“ und zeigte
    # „Beschäftigungsverhältnisse am Stichtag | 0“ und „Veränderung zum Vormonat | 0“.
    import json

    from statagent.agenten.regelaenderung import regelsatz_sicherstellen

    regelsatz_sicherstellen(conn, "v2", "v1")
    conn.execute(
        """UPDATE meta.regel SET parameter = parameter || %s::jsonb
           WHERE regelsatz = 'v2' AND name = 'R2_R4_stichtag_eigene_lieferung'""",
        (json.dumps({"zeitraum_art": "Monat"}),),
    )
    conn.execute(
        """UPDATE meta.regel SET grundlage = grundlage || '; Vorschlag uc3/25: Auftrag 2, ganzes Monat: lang'
           WHERE regelsatz = 'v2' AND name = 'R2_R4_stichtag_eigene_lieferung'"""
    )
    lauf = lauf_ausfuehren(conn, "2024-08", regelsatz="v2")
    gezaehlt = int(str(_lauf(conn, lauf.lauf_id)["gezaehlt"]))
    text = bericht_erzeugen(conn, "2024-08", "v2")
    assert gezaehlt > 0
    assert f"| Beschäftigungsverhältnisse im Berichtsmonat (mindestens ein Tag) | {zahl(gezaehlt)} |" in text
    assert f"| davon gezählt im Berichtsmonat (mindestens ein Tag) | {zahl(gezaehlt)} |" in text
    assert "am Stichtag |" not in _abschnitt(text, 1)
    assert text.startswith("# Qualitätsbericht – Berichtsmonat 2024-08 (Regelsatz v2: Auftrag 2)\n")


def test_v2_texte_folgen_der_monatszaehlung_und_r10_nur_mit_verweis() -> None:
    # Fängt (Runde 4): v2 zeigte „Bestand am Stichtag“ und „Verhältnisse am Stichtag“ aus den Satzvorlagen, obwohl
    # über den Monat gezählt wird; R10 stand in § 3 eines Monats, in dem § 2 „keine Rückfrage nötig“ sagt;
    # § 5 nannte „veröffentlicht“, obwohl im Regelsatz nichts veröffentlicht ist.
    satz = "Der Bestand am Stichtag weicht ab (10 Verhältnisse am Stichtag)."
    assert im_zeitraum(satz, "Stichtag") == satz
    assert (
        im_zeitraum(satz, "Monat")
        == "Der Bestand im Berichtsmonat weicht ab (10 Verhältnisse im Berichtsmonat)."
    )

    r10: dict[str, object] = {
        "nr": "R10",
        "titel": "Sprünge",
        "frage": "Ursache?",
        "vorschlag": "wie geliefert",
        "regel_name": "P14_sprung_aggregat",
        "lieferungen": "lieferung_2025-03",
        "ab_lieferung": None,
        "gestellt_am": None,
        "antwort": None,
        "antwort_am": None,
        "zu_pruefung": True,
    }
    plausibel = _pruef_treffer("P14_sprung_aggregat", None, None, "erklaert-plausibel")
    assert _rueckfragen_daten("2025-03", [plausibel], [r10]) == []
    offen = plausibel | {"einstufung": "nicht-erklaerbar"}
    assert [x["nr"] for x in _rueckfragen_daten("2025-04", [offen], [r10])] == ["R10"]
    ohne_pruefung = r10 | {"nr": "R3", "regel_name": "E07_fortschreibung_lieferausfall", "zu_pruefung": False}
    assert [x["nr"] for x in _rueckfragen_daten("2025-03", [], [ohne_pruefung])] == ["R3"]

    zeile = {
        "berichtsmonat": "2025-08",
        "veroeffentlicht": 10,
        "vorlaeufig": True,
        "damals_vorlaeufig": True,
        "aktuell": 9,
        "differenz": -1,
        "hauptursache": None,
    }
    revision = {"zeilen": [zeile], "details": [], "satz": None, "nachrechnung": []}
    v2 = "\n".join(_md_revision(revision | {"veroeffentlicht_gibt_es": False}))
    assert (
        "| Berichtsmonat | bisher gerechnet |" in v2
        and "| 2025-08 | 10 |" in v2
        and "veröffentlichte Monate" not in v2
    )
    v1 = "\n".join(_md_revision(revision | {"veroeffentlicht_gibt_es": True}))
    assert "| Berichtsmonat | veröffentlicht |" in v1 and "| 2025-08 | 10 (vorläufig) |" in v1


def test_im_zeitraum_laesst_den_bezugstag_des_alters_stehen() -> None:
    # Fängt: In v2 stand „Alter in vollendeten Jahren im Berichtsmonat“, das Alter gilt aber am Stichtag
    # (Review, 05.11.); der Kopf des Bestands-Belegs folgt dagegen dem Zählzeitraum.
    from statagent.berichte.qualitaetsbericht import im_zeitraum

    alter = "Alter in vollendeten Jahren am Stichtag (E03, R5)"
    kopf = "-- _bestand: Verhältnisse am Stichtag nach Abschnittswahl"
    assert im_zeitraum(alter, "Monat") == alter
    assert im_zeitraum(kopf, "Monat") == "-- _bestand: Verhältnisse im Berichtsmonat nach Abschnittswahl"
    assert im_zeitraum(kopf, "Stichtag") == kopf


def test_bericht_nennt_den_oenace_wechsel_nur_im_ersten_monat(conn: Verbindung) -> None:
    # Fängt: Der Monat mit neuer ÖNACE-Version sagt nicht, dass Abschnitte nur wegen der Umstellung anders heißen
    # (Forensik: 189.171 Merkmalsänderungen zu 12/2024). Die Fixture hat den Wechsel erst 2025; hier auf 10/2024 gelegt.
    from statagent.berichte import qualitaetsbericht

    lauf = pytest.importorskip("statagent.lauf")
    for lieferung in ("2024-08", "2024-09", "2024-10"):
        lauf.lauf_ausfuehren(conn, lieferung, regelsatz="v1", gestartet_von=None)
    with conn.transaction():
        conn.execute("UPDATE stat.klass_oenace SET gueltig_bis = DATE '2024-09-30' WHERE version = '2008'")
        conn.execute(
            """INSERT INTO stat.klass_oenace (version, code, bezeichnung, ebene, gueltig_von)
               SELECT 'T', 'Y', bezeichnung, 1, DATE '2024-10-01' FROM stat.klass_oenace
               WHERE version = '2008' AND code = 'C'"""
        )
        # Die Fixture-Lieferungen haben kaum gemeinsame Verhältnisse: dieselben Zeilen auch in die Lieferung davor.
        conn.execute(
            """CREATE TEMP TABLE beide AS SELECT * FROM bereinigt.abschnitt
               WHERE lieferung = '2024-10' AND regelsatz = 'v1' AND oenace = 'C' AND beginn <= DATE '2024-09-30'
                 AND (ende IS NULL OR ende >= DATE '2024-09-30')"""
        )
        conn.execute("UPDATE beide SET lieferung = '2024-09'")
        conn.execute(
            """DELETE FROM bereinigt.abschnitt a USING beide b
               WHERE a.lieferung = '2024-09' AND a.regelsatz = 'v1' AND a.vvh_id = b.vvh_id"""
        )
        conn.execute("INSERT INTO bereinigt.abschnitt SELECT * FROM beide")
        geaendert = conn.execute(
            """UPDATE bereinigt.abschnitt a SET oenace = 'Y' FROM beide b
               WHERE a.lieferung = '2024-10' AND a.regelsatz = 'v1' AND a.vvh_id = b.vvh_id"""
        ).rowcount
    assert geaendert > 0
    w = qualitaetsbericht.bericht_daten(conn, "2024-10")["oenace_wechsel"]
    assert (w["version_alt"], w["version_neu"], w["vormonat"]) == ("2008", "T", "2024-09")
    assert 0 < w["anders"] <= w["gesamt"]
    assert w["nur_buchstabe"] == w["beispiel"]["anzahl"]
    assert (w["beispiel"]["alt"], w["beispiel"]["neu"]) == ("C", "Y")
    text = qualitaetsbericht.bericht_erzeugen(conn, "2024-10")
    assert "**Wechsel der ÖNACE:**" in text
    assert "keine echte Entwicklung" in text
    assert "```sql\nWITH vorher AS" in text
    assert qualitaetsbericht.bericht_daten(conn, "2024-09")["oenace_wechsel"] is None
    assert "Wechsel der ÖNACE" not in qualitaetsbericht.bericht_erzeugen(conn, "2024-09")
