"""Qualitätsbericht je Berichtsmonat nach der Vorlage des Veranstalters (`qualitaetsbericht_vorlage.md`).

Alle Inhalte kommen aus der Datenbank (meta.lauf, meta.pruefung_treffer, meta.rueckfrage, meta.regel_wirkung,
meta.revision). Der Bericht ist deterministisch: gleiche Datenbank, gleicher Bericht, Byte für Byte. Es gibt
keinen Zeitstempel „jetzt“; „erstellt am“ ist das Ende des Laufs (meta.lauf.beendet_am).
"""

from __future__ import annotations

from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from statagent import ergebnis, konfig
from statagent.db import Verbindung

ZEITZONE = ZoneInfo("Europe/Vienna")
#: Variable der Stichtagszählung in stat.stat_beschaeftigte (Name der Kennzahl, keine Zuordnungsregel).
STICHTAG_VARIABLE = "Beschaeftigungsverhaeltnisse"

#: Die fünf Abschnittsüberschriften der Vorlage, in dieser Reihenfolge.
ABSCHNITTE = (
    "## 1 Überblick",
    "## 2 Auffälligkeiten",
    "## 3 Rückfragen an die Fachabteilung",
    "## 4 Angewendete Regeln",
    "## 5 Revisionsbedarf früherer Monate",
)

#: Einstufungen der Vorlage (wörtlich) zu den Codes in meta.pruefung_treffer.einstufung.
EINSTUFUNGEN = {
    "erklaert-plausibel": "erklärt – plausibel",
    "erklaert-datenproblem": "erklärt – Datenproblem",
    "nicht-erklaerbar": "nicht erklärbar",
}
GUELTIGE_EINSTUFUNGEN = frozenset(EINSTUFUNGEN.values())

EBENEN = {"satz": "Satz", "aggregat": "Aggregat", "lieferung": "Lieferung"}
URSACHEN = {
    "nachmeldung": "Nachmeldung",
    "rueckwirkende_abmeldung": "rückwirkende Abmeldung",
    "nicht_mehr_enthalten": "nicht mehr enthalten",
    "merkmal_geaendert": "Merkmal geändert",
}
TYP_REIHENFOLGE = {"einlese": 1, "zuordnung": 2, "zaehl": 3}
BELEG_KURZ = 60
#: Gliederungen in meta.revision (ohne „insgesamt“), mit Namen für den Bericht.
GLIEDERUNGEN = {
    "region": "Bundesland",
    "geschlecht": "Geschlecht",
    "qualifikation": "Qualifikation",
    "oenace": "ÖNACE-Abschnitt",
}
#: Höchstens so viele Abweichungen je Gliederung zeigt § 5 (die größten nach Betrag).
REVISION_ZEILEN = 5


class BerichtFehler(RuntimeError):
    """Für die Lieferung gibt es keinen erfolgreichen Lauf."""


# --- Formatierung ------------------------------------------------------------------------------------


def zahl(wert: int) -> str:
    """Ganzzahl im österreichischen Format (Tausenderpunkt)."""
    return f"{wert:,}".replace(",", ".")


def zahl_vorzeichen(wert: int) -> str:
    return ("+" if wert > 0 else "") + zahl(wert)


def prozent(wert: float) -> str:
    """Prozent mit zwei Nachkommastellen, Dezimalkomma und Vorzeichen."""
    text = f"{abs(wert):,.2f}".replace(",", "_").replace(".", ",").replace("_", ".")
    vorzeichen = "+" if wert > 0 else ("-" if wert < 0 else "")
    return f"{vorzeichen}{text} %"


def datum(wert: object) -> str:
    """TT.MM.JJJJ; Zeitpunkte in Wiener Ortszeit."""
    if isinstance(wert, datetime):
        wert = wert.astimezone(ZEITZONE).date()
    if isinstance(wert, date):
        return wert.strftime("%d.%m.%Y")
    return "–"


def _zelle(text: object) -> str:
    """Tabellenzelle: einzeilig, Pipe maskiert."""
    if text is None or text == "":
        return "–"
    return " ".join(str(text).split()).replace("|", "\\|")


def _kurz(text: str, laenge: int) -> str:
    text = " ".join(text.split())
    return text if len(text) <= laenge else text[: laenge - 1].rstrip() + "…"


def _int(wert: object) -> int:
    return 0 if wert is None else int(str(wert))


def _tabelle(kopf: list[str], zeilen: list[list[str]]) -> list[str]:
    aus = ["| " + " | ".join(kopf) + " |", "| " + " | ".join("---" for _ in kopf) + " |"]
    aus += ["| " + " | ".join(z) + " |" for z in zeilen]
    return aus


# --- Datenbank ---------------------------------------------------------------------------------------


def _hat_tabelle(conn: Verbindung, name: str) -> bool:
    zeile = conn.execute("SELECT to_regclass(%s) IS NOT NULL AS da", (name,)).fetchone()
    return bool(zeile and zeile["da"])


def _bestand(conn: Verbindung, regelsatz: str, regelstand: str, lieferung: str) -> int:
    zeile = conn.execute(
        """SELECT coalesce(sum(wert), 0) AS n FROM stat.stat_beschaeftigte
           WHERE regelsatz = %s AND regelstand = %s AND zeitraum_art = 'Stichtag' AND variable = %s
             AND zeitraum_bis BETWEEN %s AND %s""",
        (
            regelsatz,
            regelstand,
            STICHTAG_VARIABLE,
            ergebnis.monatserster(lieferung),
            ergebnis.monatsletzter(lieferung),
        ),
    ).fetchone()
    return _int(zeile["n"]) if zeile else 0


def _veroeffentlichender_lauf(conn: Verbindung, stand: ergebnis.LaufStand) -> int:
    """Lauf, dessen Zahlen veröffentlicht sind: seine lauf_id hängt an den endgültigen Zeilen.

    Rechnet ein späterer Lauf einen veröffentlichten Monat unter neuem Regelstand nach, übernimmt er nur die
    Kennzahlen; Prüftreffer und Regelwirkung in meta.* gehören zu seinem neuen Regelstand. Für einen nicht
    veröffentlichten Monat ist es der Lauf selbst."""
    if stand.ergebnis_status != "endgueltig":
        return stand.lauf_id
    zeile = conn.execute(
        """SELECT min(lauf_id) AS id FROM stat.stat_beschaeftigte
           WHERE regelsatz = %s AND regelstand = %s AND status = 'endgueltig'
             AND zeitraum_bis BETWEEN %s AND %s""",
        (
            stand.regelsatz,
            stand.regelstand,
            ergebnis.monatserster(stand.lieferung),
            ergebnis.monatsletzter(stand.lieferung),
        ),
    ).fetchone()
    return stand.lauf_id if zeile is None or zeile["id"] is None else _int(zeile["id"])


def _dateiname(conn: Verbindung, lieferung: str) -> str:
    zeile = conn.execute(
        "SELECT datei FROM roh.ladeprotokoll WHERE lieferung = %s AND datei IS NOT NULL "
        "ORDER BY geladen_am DESC, datei LIMIT 1",
        (lieferung,),
    ).fetchone()
    return str(zeile["datei"]) if zeile else f"lieferung_{lieferung}.csv"


# --- Abschnitte --------------------------------------------------------------------------------------


def _ueberblick(conn: Verbindung, lauf: dict[str, object], lieferung: str, regelsatz: str) -> list[str]:
    gelesen, gezaehlt = _int(lauf["gelesen"]), _int(lauf["gezaehlt"])
    nicht, ausgeschlossen, korrigiert = (
        _int(lauf["nicht_gezaehlt"]),
        _int(lauf["ausgeschlossen"]),
        _int(lauf["korrigiert"]),
    )
    fortgeschrieben = _int(lauf.get("fortgeschrieben") or 0)
    bestand = _bestand(conn, regelsatz, str(lauf["regelstand"]), lieferung)

    vormonat = ergebnis.monat_verschieben(lieferung, -1)
    vorher = ergebnis.letzter_lauf(conn, vormonat, regelsatz)
    if vorher is None:
        veraenderung = f"– (kein Lauf für {vormonat})"
    else:
        alt = _bestand(conn, regelsatz, vorher.regelstand, vormonat)
        diff = bestand - alt
        anteil = prozent(diff / alt * 100) if alt else "–"
        veraenderung = f"{zahl_vorzeichen(diff)} ({anteil}) gegenüber {vormonat} ({zahl(alt)})"

    zeilen = [
        ["gelesene Sätze", zahl(gelesen)],
        ["davon gezählt am Stichtag", zahl(gezaehlt)],
        [
            "ausgeschlossene oder korrigierte Sätze",
            f"{zahl(ausgeschlossen)} ausgeschlossen · {zahl(korrigiert)} korrigiert",
        ],
        ["Beschäftigungsverhältnisse am Stichtag", zahl(bestand)],
        ["Veränderung zum Vormonat", veraenderung],
    ]
    abrechnung = "Abrechnung: gelesene Sätze = gezählte + nicht gezählte + ausgeschlossene Sätze."
    if fortgeschrieben:
        # E07 schreibt nur Verhältnisse fort, die am Stichtag laufen; sie stecken in „gezählt“.
        zeilen[2:2] = [
            ["davon geliefert gezählt", zahl(gezaehlt - fortgeschrieben)],
            ["davon fortgeschrieben aus der Vorlieferung (Regel E07, vorläufig)", zahl(fortgeschrieben)],
        ]
        abrechnung = (
            "Abrechnung: gelesene Sätze + fortgeschriebene Verhältnisse = gezählte + nicht gezählte"
            " + ausgeschlossene Sätze."
        )
    aufgeht = (
        "geht auf" if gelesen + fortgeschrieben == gezaehlt + nicht + ausgeschlossen else "geht NICHT auf"
    )
    return [
        ABSCHNITTE[0],
        "",
        *_tabelle(["Kennzahl", "Wert"], zeilen),
        "",
        abrechnung,
        "",
        f"Abrechnung in Zahlen: {zahl(gelesen)} gelesen"
        + (f" + {zahl(fortgeschrieben)} fortgeschrieben" if fortgeschrieben else "")
        + f" = {zahl(gezaehlt)} gezählt + {zahl(nicht)} nicht gezählt"
        f" + {zahl(ausgeschlossen)} ausgeschlossen ({aufgeht}). Korrigierte Sätze ({zahl(korrigiert)}) bleiben"
        " in der Abrechnung, eine Einleseregel hat sie nur verändert.",
        "",
        "Die Vorlage hat keine Zeile ‚nicht gezählt‘; wir weisen Abschnitte ohne Bestand am Stichtag dort aus"
        " (Annahme A8).",
    ]


def _pruefungen_gelaufen(conn: Verbindung, lauf_id: int) -> int:
    """Anzahl der Prüfergebnisse des Laufs (auch ohne Treffer); 0 heißt: keine Prüfung gelaufen."""
    if not _hat_tabelle(conn, "meta.pruefung_treffer"):
        return 0
    zeile = conn.execute(
        "SELECT count(*) AS n FROM meta.pruefung_treffer WHERE lauf_id = %s", (lauf_id,)
    ).fetchone()
    return _int(zeile["n"]) if zeile else 0


def _treffer(conn: Verbindung, lauf_id: int) -> list[dict[str, object]]:
    if not _hat_tabelle(conn, "meta.pruefung_treffer"):
        return []
    return conn.execute(
        """SELECT t.ebene, t.anzahl, t.umfang, t.einstufung, t.massnahme, t.anhalten, t.beleg_sql,
                  t.details ->> 'rueckfrage' AS rueckfrage, r.name, r.beschreibung
           FROM meta.pruefung_treffer t JOIN meta.regel r ON r.id = t.regel_id
           WHERE t.lauf_id = %s AND t.anzahl > 0
           ORDER BY r.reihenfolge, r.name, array_position(ARRAY['satz', 'aggregat', 'lieferung'], t.ebene)""",
        (lauf_id,),
    ).fetchall()


def _rueckfragen(conn: Verbindung) -> list[dict[str, object]]:
    if not _hat_tabelle(conn, "meta.rueckfrage"):
        return []
    return conn.execute(
        """SELECT nr, titel, frage, vorschlag, regel_name, gestellt_am, antwort, antwort_am, ab_lieferung
           FROM meta.rueckfrage ORDER BY length(nr), nr"""
    ).fetchall()


def _verweise(treffer: dict[str, object], rueckfragen: list[dict[str, object]]) -> list[str]:
    nrn = [
        str(r["nr"])
        for r in rueckfragen
        if r["regel_name"] is not None and r["regel_name"] == treffer["name"]
    ]
    if treffer["rueckfrage"] and str(treffer["rueckfrage"]) not in nrn:
        nrn.append(str(treffer["rueckfrage"]))
    return nrn


def _auffaelligkeiten(
    treffer: list[dict[str, object]], rueckfragen: list[dict[str, object]], gelaufen: int
) -> list[str]:
    kopf = [
        "Nr.",
        "Ebene (Satz / Aggregat / Lieferung)",
        "Beschreibung",
        "Umfang (Sätze, Zellen)",
        "Beleg (Abfrage)",
        "Einstufung",
        "Maßnahme",
        "Rückfrage",
    ]
    zeilen: list[list[str]] = []
    belege: list[str] = []
    for nr, t in enumerate(treffer, start=1):
        sql = str(t["beleg_sql"] or "").strip()
        beleg = "–"
        if sql:
            beleg = "`" + _kurz(sql.replace("`", "'"), BELEG_KURZ).replace("|", "\\|") + "`"
            belege += [
                f"<details><summary>Beleg {nr}: {t['name']}</summary>",
                "",
                "```sql",
                sql,
                "```",
                "",
                "</details>",
                "",
            ]
        # Ohne Einstufung gilt der Treffer als nicht erklärt und geht an die Fachabteilung.
        einstufung = EINSTUFUNGEN.get(str(t["einstufung"]), EINSTUFUNGEN["nicht-erklaerbar"])
        umfang = str(t["umfang"]) if t["umfang"] else f"{zahl(_int(t['anzahl']))} Sätze"
        zeilen.append(
            [
                str(nr),
                EBENEN.get(str(t["ebene"]), str(t["ebene"])),
                _zelle(f"{t['name']}: {t['beschreibung']}"),
                _zelle(umfang),
                beleg,
                einstufung,
                _zelle(t["massnahme"]),
                _zelle(", ".join(_verweise(t, rueckfragen))),
            ]
        )
    aus = [ABSCHNITTE[1], "", *_tabelle(kopf, zeilen), ""]
    if not gelaufen:
        aus += ["Für diesen Lauf liegen keine Prüfergebnisse vor (meta.pruefung_treffer leer).", ""]
    elif not zeilen:
        aus += [
            f"Keine Prüfregel hat in diesem Monat angeschlagen ({gelaufen} Prüfergebnisse ohne Treffer).",
            "",
        ]
    aus += belege
    aus.append(
        "Einstufung: **erklärt – plausibel** (reale Entwicklung, mit Daten belegt) · **erklärt – Datenproblem**"
        " (Ursache in den Daten, Maßnahme umgesetzt) · **nicht erklärbar** (an die Fachabteilung eskaliert)."
    )
    return aus


def _rueckfragen_abschnitt(
    lieferung: str, treffer: list[dict[str, object]], rueckfragen: list[dict[str, object]]
) -> list[str]:
    verwiesen = {nr for t in treffer for nr in _verweise(t, rueckfragen)}
    gewaehlt = [
        r
        for r in rueckfragen
        if str(r["nr"]) in verwiesen
        or (r["ab_lieferung"] is not None and str(r["ab_lieferung"]) <= lieferung)
    ]
    zeilen = []
    for r in gewaehlt:
        gestellt = datum(r["gestellt_am"]) if r["gestellt_am"] else "noch nicht gestellt"
        if r["antwort"]:
            antwort = f"{r['antwort']} ({datum(r['antwort_am'])})" if r["antwort_am"] else str(r["antwort"])
        else:
            antwort = f"offen; bis dahin gilt unser Vorschlag: {r['vorschlag']}"
        zeilen.append(
            [
                _zelle(r["nr"]),
                gestellt,
                _zelle(_kurz(f"{r['titel']}: {r['frage']}", 160)),
                _zelle(antwort),
                _zelle(r["regel_name"]),
            ]
        )
    aus = [
        ABSCHNITTE[2],
        "",
        *_tabelle(
            ["Nr.", "Gestellt am", "Frage (kurz)", "Antwort der Fachabteilung", "Umgesetzt als Regel"], zeilen
        ),
    ]
    if not zeilen:
        aus += ["", "Für diesen Berichtsmonat gibt es keine Rückfrage an die Fachabteilung."]
    return aus


def _regeln(conn: Verbindung, lauf_id: int, lieferung: str, regelsatz: str) -> list[str]:
    zeilen = conn.execute(
        """SELECT r.name, r.typ, r.reihenfolge, r.gueltig_ab_lieferung, r.grundlage, w.saetze
           FROM meta.regel r
           LEFT JOIN meta.regel_wirkung w ON w.regel_id = r.id AND w.lauf_id = %(lauf)s
           WHERE r.typ IN ('einlese', 'zuordnung', 'zaehl')
             AND (w.lauf_id IS NOT NULL
                  OR (r.regelsatz = %(rs)s AND r.aktiv AND r.gueltig_ab_lieferung <= %(l)s
                      AND (r.gueltig_bis_lieferung IS NULL OR r.gueltig_bis_lieferung >= %(l)s)))""",
        {"lauf": lauf_id, "rs": regelsatz, "l": lieferung},
    ).fetchall()
    zeilen.sort(key=lambda z: (TYP_REIHENFOLGE[str(z["typ"])], _int(z["reihenfolge"]), str(z["name"])))
    tabelle = [
        [f"`{z['name']}`", str(z["gueltig_ab_lieferung"]), _zelle(z["grundlage"]), zahl(_int(z["saetze"]))]
        for z in zeilen
    ]
    return [
        ABSCHNITTE[3],
        "",
        *_tabelle(
            [
                "Regel",
                "Seit Berichtsmonat",
                "Grundlage (Rückfrage, Änderungsauftrag)",
                "betroffene Sätze in diesem Monat",
            ],
            tabelle,
        ),
    ]


def _nachrechnung(
    conn: Verbindung, lauf: dict[str, object], quelle_id: int, treffer_quelle: list[dict[str, object]]
) -> list[str]:
    """Hinweis in § 5, wenn ein späterer Lauf einen veröffentlichten Monat unter neuem Regelstand nachrechnet."""
    lauf_id = _int(lauf["id"])
    if lauf_id == quelle_id:
        return []
    aus = [
        f"Lauf {lauf_id} hat den veröffentlichten Monat nachgerechnet. § 1 bis § 4 zeigen den veröffentlichenden"
        f" Lauf {quelle_id}; was der neue Regelstand anders sieht, steht nur hier.",
    ]
    if lauf["meldung"]:
        aus += ["", f"Meldung des Laufs {lauf_id}: {_zelle(lauf['meldung'])}."]
    alt = {(t["name"], t["ebene"], _int(t["anzahl"]), bool(t["anhalten"])) for t in treffer_quelle}
    neu = [
        t
        for t in _treffer(conn, lauf_id)
        if (t["name"], t["ebene"], _int(t["anzahl"]), bool(t["anhalten"])) not in alt
    ]
    if neu:
        teile = [
            f"{t['name']} ({EBENEN.get(str(t['ebene']), str(t['ebene']))}, {zahl(_int(t['anzahl']))} Sätze"
            + (", hätte angehalten)" if t["anhalten"] else ")")
            for t in neu
        ]
        aus += ["", "Prüfungen, die unter dem neuen Regelstand anders treffen: " + "; ".join(teile) + "."]
    return [*aus, ""]


def _revision(conn: Verbindung, lauf_id: int, hinweis: list[str] | None = None) -> list[str]:
    aus = [
        ABSCHNITTE[4],
        "",
        "Weicht die aktuelle Lieferung für bereits veröffentlichte Monate ab, hier ausweisen"
        " (Veröffentlichtes bleibt unverändert).",
        "",
        *(hinweis or []),
    ]
    kopf = ["Berichtsmonat", "veröffentlicht", "laut aktueller Lieferung", "Differenz", "Hauptursache"]
    if not _hat_tabelle(conn, "meta.revision"):
        return [*aus, *_tabelle(kopf, []), "", "Für diesen Lauf liegt kein Revisionsabgleich vor."]
    zeilen = conn.execute(
        """SELECT berichtsmonat, veroeffentlicht, aktuell, differenz, status_vorher
           FROM meta.revision WHERE lauf_id = %s AND gliederung = 'insgesamt' ORDER BY berichtsmonat""",
        (lauf_id,),
    ).fetchall()
    # Abweichungen je Gliederung: eine Umschichtung (z. B. C +10, D −10) lässt „insgesamt“ unverändert.
    gliederung: dict[str, list[dict[str, object]]] = {}
    for g in conn.execute(
        """SELECT berichtsmonat, gliederung, schluessel, veroeffentlicht, aktuell, differenz
           FROM meta.revision WHERE lauf_id = %s AND gliederung <> 'insgesamt' AND differenz <> 0
           ORDER BY berichtsmonat, gliederung, abs(differenz) DESC, schluessel""",
        (lauf_id,),
    ).fetchall():
        gliederung.setdefault(str(g["berichtsmonat"]), []).append(g)
    ursachen: dict[str, tuple[str, int]] = {}
    if _hat_tabelle(conn, "meta.revision_ursache"):
        for u in conn.execute(
            """SELECT DISTINCT ON (berichtsmonat) berichtsmonat, ursache, anzahl FROM meta.revision_ursache
               WHERE lauf_id = %s ORDER BY berichtsmonat, abs(anzahl) DESC, ursache""",
            (lauf_id,),
        ).fetchall():
            ursachen[str(u["berichtsmonat"])] = (str(u["ursache"]), _int(u["anzahl"]))
    tabelle = []
    details: list[list[str]] = []
    for z in zeilen:
        monat = str(z["berichtsmonat"])
        if _int(z["differenz"]) == 0 and monat not in gliederung:
            continue
        status = " (vorläufig)" if z["status_vorher"] == "vorlaeufig" else ""
        haupt = "–"
        if _int(z["differenz"]) == 0:
            haupt = "Umschichtung zwischen Ausprägungen, insgesamt unverändert"
        elif monat in ursachen:
            ursache, anzahl = ursachen[monat]
            haupt = f"{URSACHEN.get(ursache, ursache)} ({zahl(anzahl)} Verhältnisse)"
        tabelle.append(
            [
                monat,
                zahl(_int(z["veroeffentlicht"])) + status,
                zahl(_int(z["aktuell"])),
                zahl_vorzeichen(_int(z["differenz"])),
                haupt,
            ]
        )
        gezeigt: dict[str, int] = {}
        for g in gliederung.get(monat, []):
            name = str(g["gliederung"])
            gezeigt[name] = gezeigt.get(name, 0) + 1
            if gezeigt[name] > REVISION_ZEILEN:
                continue
            details.append(
                [
                    monat,
                    GLIEDERUNGEN.get(name, name),
                    _zelle(g["schluessel"]),
                    zahl(_int(g["veroeffentlicht"])),
                    zahl(_int(g["aktuell"])),
                    zahl_vorzeichen(_int(g["differenz"])),
                ]
            )
    aus += _tabelle(kopf, tabelle)
    if details:
        aus += [
            "",
            f"Abweichungen nach Gliederung (die {REVISION_ZEILEN} größten je Gliederung, nach Betrag):",
            "",
            *_tabelle(
                [
                    "Berichtsmonat",
                    "Gliederung",
                    "Ausprägung",
                    "veröffentlicht",
                    "laut aktueller Lieferung",
                    "Differenz",
                ],
                details,
            ),
        ]
    if not zeilen:
        aus += ["", "Für diesen Lauf liegt kein Revisionsabgleich vor."]
    elif not tabelle:
        aus += [
            "",
            f"Kein Revisionsbedarf: {len(zeilen)} geprüfte Vormonate stimmen in allen Gliederungen mit der"
            " aktuellen Lieferung überein.",
        ]
    return aus


# --- Bericht -----------------------------------------------------------------------------------------


def bericht_erzeugen(conn: Verbindung, lieferung: str, regelsatz: str = "v1") -> str:
    """Qualitätsbericht (Markdown) des Berichtsmonats aus dem letzten erfolgreichen Lauf."""
    stand = ergebnis.letzter_lauf(conn, lieferung, regelsatz)
    if stand is None:
        raise BerichtFehler(f"kein erfolgreicher Lauf für {lieferung} (Regelsatz {regelsatz})")
    lauf = conn.execute("SELECT * FROM meta.lauf WHERE id = %s", (stand.lauf_id,)).fetchone()
    assert lauf is not None
    # Veröffentlichter Monat: § 1 bis § 4 aus dem Lauf, der veröffentlicht hat; Neues nur in § 5.
    quelle_id = _veroeffentlichender_lauf(conn, stand)
    quelle = (
        lauf
        if quelle_id == stand.lauf_id
        else conn.execute("SELECT * FROM meta.lauf WHERE id = %s", (quelle_id,)).fetchone()
    )
    assert quelle is not None
    treffer = _treffer(conn, quelle_id)
    rueckfragen = _rueckfragen(conn)

    name, am = quelle.get("freigegeben_von"), quelle.get("freigegeben_am")
    freigabe = f"{name} am {datum(am)}" if name else "noch nicht freigegeben"
    kopf = [
        f"# Qualitätsbericht – Berichtsmonat {lieferung}",
        "",
        f"Lieferung: `{_dateiname(conn, lieferung)}` · erstellt am {datum(lauf['beendet_am'])}"
        f" · freigegeben von: {freigabe}",
        "",
    ]
    angehalten = [t for t in treffer if t["anhalten"]]
    if stand.ergebnis_status == "endgueltig":
        # Veröffentlicht ist veröffentlicht: ein Anhalten unter neuem Regelstand steht nur in § 5.
        kopf.append(f"> **Status: endgültig**, freigegeben von {freigabe}.")
    else:
        gruende = [
            f"Prüfung {t['name']} hat angehalten ({_zelle(t['umfang'] or zahl(_int(t['anzahl'])))})"
            for t in angehalten
        ]
        if lauf["meldung"]:
            gruende.append(str(lauf["meldung"]))
        status = "gesperrt" if stand.ergebnis_status == "gesperrt" else "vorläufig"
        kopf.append(
            f"> **Status: {status.upper()}.** Grund: {'; '.join(gruende) or 'Lauf nicht freigegeben'}."
        )

    teile = [
        kopf,
        _ueberblick(conn, quelle, lieferung, regelsatz),
        _auffaelligkeiten(treffer, rueckfragen, _pruefungen_gelaufen(conn, quelle_id)),
        _rueckfragen_abschnitt(lieferung, treffer, rueckfragen),
        _regeln(conn, quelle_id, lieferung, regelsatz),
        _revision(conn, stand.lauf_id, _nachrechnung(conn, lauf, quelle_id, treffer)),
        [
            "---",
            "",
            f"Regelsatz {regelsatz} · Lauf {stand.lauf_id} · Regelstand `{stand.regelstand}`"
            f" · Ergebnis-Hash `{stand.ergebnis_hash}`",
        ],
    ]
    zeilen: list[str] = []
    for teil in teile:
        if zeilen:
            zeilen.append("")
        zeilen += teil
    while zeilen and zeilen[-1] == "":
        zeilen.pop()
    return "\n".join(zeilen) + "\n"


def bericht_pfad(lieferung: str, regelsatz: str = "v1") -> Path:
    ordner = "qualitaetsberichte" if regelsatz == "v1" else f"qualitaetsberichte_{regelsatz}"
    return konfig.abgabe() / ordner / f"{lieferung}.md"


def bericht_schreiben(
    conn: Verbindung, lieferung: str, regelsatz: str = "v1", ziel: Path | None = None
) -> Path:
    """Schreibt den Bericht nach `ziel` bzw. `abgabe/qualitaetsberichte[_<regelsatz>]/<lieferung>.md`."""
    pfad = ziel or bericht_pfad(lieferung, regelsatz)
    pfad.parent.mkdir(parents=True, exist_ok=True)
    pfad.write_text(bericht_erzeugen(conn, lieferung, regelsatz), encoding="utf-8")
    return pfad
