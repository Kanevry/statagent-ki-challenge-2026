"""Aggregations-Sheet nach der Vorlage des Veranstalters (`vorlagen/aggregationen_vorlage.xlsx`).

Je Blatt eine Dimension (Bundesland, Geschlecht, ÖNACE 2008/2025, Beschäftigungskategorie), Zeilen = Codes,
Spalten = Berichtsmonate (JJJJ-MM). Werte = Beschäftigungsverhältnisse am Stichtag aus
stat.stat_beschaeftigte, Regelstand des letzten Laufs je Lieferung (`ergebnis.monatswerte`).

Festlegungen:

- Spalten werden über die Kopfzeile (JJJJ-MM) gefunden, Zeilen über die Spalte ``CODE`` der Vorlage.
  Blattnamen, Kopfzeilen und Beschriftungen bleiben unverändert.
- Für jeden gerechneten Monat wird jede Zelle geschrieben, auch 0. Eine leere Zelle heißt damit „Monat
  nicht gerechnet“; die Vorlage („Leere Zelle = 0“) liest beides richtig.
- Die Insgesamt-Formeln bleiben stehen. Nur wenn ein Blatt Zeilen bekommt, wird der ``=SUM``-Bereich
  nachgezogen: (a) für „unbekannt“, wenn Werte darauf fallen und die Vorlage keine Zeile hat (Code laut
  stat.quellzuordnung, geliefert '<leer>'; Fachbeschreibung § 5 „unbekannte Werte als eigene Zeile“),
  (b) beim Umbau des Blatts Beschäftigungskategorie, wenn ``qualifikation`` Kategorien statt
  Qualifikationen trägt (Änderungsauftrag 1, Hinweis der Vorlage „Zeilen entsprechend anpassen“).
- Vorläufige Monate tragen an der Kopfzelle einen Kommentar „vorläufig: <meta.lauf.meldung>“.
- Deterministisch: Dokument-Zeitstempel und Zeitstempel im Zip-Archiv sind das Ende des jüngsten
  verwendeten Laufs. Gleiche Datenbank, gleiche Vorlage → bytegleiche Datei.
"""

from __future__ import annotations

import io
import re
import zipfile
from collections import defaultdict
from copy import copy
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from openpyxl import load_workbook
from openpyxl.comments import Comment
from openpyxl.xml.functions import tostring

from statagent import ergebnis, konfig
from statagent.db import Verbindung
from statagent.regeln import eine, regeln_laden
from statagent.regeln import wert as regel_wert

#: Variable und Zeitraumart der Stichtagszählung (Kennzahl, keine Zuordnungsregel).
STICHTAG_VARIABLE = "Beschaeftigungsverhaeltnisse"
STICHTAG = "Stichtag"
VORLAGE_DATEI = "aggregationen_vorlage.xlsx"
KOMMENTAR_AUTOR = "StatAgent"

#: Blätter der Vorlage (Namen dürfen laut Vorlage nicht geändert werden) und ihre Spalte in stat.
BLATT_BUNDESLAND = "Bundesland"
BLATT_GESCHLECHT = "Geschlecht"
BLATT_KATEGORIE = "Beschaeftigungskategorie"
BLATT_HINWEISE = "Hinweise"
OENACE_PRAEFIX = "OENACE_"

_MONAT = re.compile(r"^\d{4}-\d{2}$")
_SUMME = re.compile(r"^=SUM\(([A-Z]+)(\d+):([A-Z]+)(\d+)\)$")


@dataclass(frozen=True)
class SheetErgebnis:
    pfad: Path
    regelsatz: str
    monate: list[str]
    #: je Blatt die Summe je Monat (nur Monate, die in diesem Blatt stehen)
    summen: dict[str, dict[str, int]]
    #: Monate, in denen eine Blattsumme von Insgesamt des Bundesland-Blatts abweicht (Soll: leer)
    abweichungen: list[str]
    #: vorläufige Monate mit Grund (meta.lauf.meldung)
    vorlaeufig: dict[str, str]
    #: Monate mit fortgeschriebenen Verhältnissen (Regel E07): Anzahl, in den Werten enthalten
    fortgeschrieben: dict[str, int]
    #: True, wenn das Blatt Beschäftigungskategorie auf Kategorien umgebaut wurde
    kategorien: bool
    #: je Blatt die ergänzten Zeilen-Codes (unbekannt bzw. Umbau)
    ergaenzt: dict[str, list[str]] = field(default_factory=dict)


@dataclass
class _Blatt:
    ws: Any
    kopfzeile: int
    code_spalte: int
    text_spalte: int
    spalten: dict[str, int]
    zeilen: dict[str, int]
    insgesamt: int


def _blatt_lesen(ws: Any) -> _Blatt:
    """Findet Kopfzeile (Spalte ``CODE`` + Monatsspalten), Datenzeilen und die Zeile „Insgesamt“."""
    kopfzeile = 1
    code_spalte = 0
    spalten: dict[str, int] = {}
    for zelle in ws[kopfzeile]:
        wert = zelle.value
        if isinstance(wert, str) and wert.strip().upper() == "CODE":
            code_spalte = zelle.column
        elif isinstance(wert, str) and _MONAT.match(wert.strip()):
            spalten[wert.strip()] = zelle.column
    if not code_spalte or not spalten:
        raise ValueError(f"Blatt {ws.title}: Kopfzeile ohne CODE- oder Monatsspalten")
    insgesamt = 0
    text_spalte = 0
    for zeile in ws.iter_rows(min_row=kopfzeile + 1):
        for zelle in zeile:
            if isinstance(zelle.value, str) and zelle.value.strip() == "Insgesamt":
                insgesamt, text_spalte = zelle.row, zelle.column
                break
        if insgesamt:
            break
    if not insgesamt:
        raise ValueError(f"Blatt {ws.title}: keine Zeile „Insgesamt“")
    zeilen: dict[str, int] = {}
    for r in range(kopfzeile + 1, insgesamt):
        code = ws.cell(r, code_spalte).value
        if code is not None and str(code).strip():
            zeilen[str(code).strip()] = r
    return _Blatt(ws, kopfzeile, code_spalte, text_spalte, spalten, zeilen, insgesamt)


def _zeilen_neu(blatt: _Blatt, zeilen: list[tuple[str, str]]) -> None:
    """Ersetzt die Datenzeilen durch `zeilen` (Code, Bezeichnung) und zieht die ``=SUM``-Bereiche nach.

    Formate kommen aus der ersten Datenzeile bzw. der alten Insgesamt-Zeile. Kopfzeile und
    Beschriftungen bestehender Codes bleiben wörtlich.
    """
    ws = blatt.ws
    erste = blatt.kopfzeile + 1
    max_spalte = ws.max_column
    alt_text = {code: ws.cell(r, blatt.text_spalte).value for code, r in blatt.zeilen.items()}
    daten_stil = [copy(ws.cell(erste, s)._style) for s in range(1, max_spalte + 1)]
    summe_zellen = [
        (ws.cell(blatt.insgesamt, s).value, copy(ws.cell(blatt.insgesamt, s)._style))
        for s in range(1, max_spalte + 1)
    ]
    ws.delete_rows(erste, blatt.insgesamt - blatt.kopfzeile)
    for i, (code, text) in enumerate(zeilen):
        r = erste + i
        for s in range(1, max_spalte + 1):
            ws.cell(r, s)._style = copy(daten_stil[s - 1])
        ws.cell(r, blatt.code_spalte).value = code
        ws.cell(r, blatt.text_spalte).value = alt_text.get(code, text)
    letzte = erste + len(zeilen) - 1
    neu_insgesamt = letzte + 1
    for s, (wert, stil) in enumerate(summe_zellen, start=1):
        zelle = ws.cell(neu_insgesamt, s)
        zelle._style = stil
        if isinstance(wert, str) and wert.startswith("="):
            treffer = _SUMME.match(wert)
            if treffer is None:
                raise ValueError(f"Blatt {ws.title}: Insgesamt-Formel {wert!r} ist keine einfache SUM")
            sp_von, z_von, sp_bis, _ = treffer.groups()
            wert = f"=SUM({sp_von}{z_von}:{sp_bis}{letzte})"
        zelle.value = wert
    blatt.zeilen = {code: erste + i for i, (code, _) in enumerate(zeilen)}
    blatt.insgesamt = neu_insgesamt


def _dict(conn: Verbindung, abfrage: str, parameter: tuple[object, ...] = ()) -> dict[str, str]:
    return {
        str(z["code"]): str(z["bezeichnung"]) for z in conn.execute(abfrage.encode(), parameter).fetchall()
    }


def _unbekannt_codes(conn: Verbindung, regelsatz: str) -> dict[tuple[str, str], str]:
    """Code für „unbekannt“ je (Merkmal, Version) laut stat.quellzuordnung des Regelsatzes (geliefert '<leer>')."""
    zeilen = conn.execute(
        """SELECT merkmal, version, code FROM stat.quellzuordnung
           WHERE regelsatz = %s AND geliefert = '<leer>' ORDER BY 1, 2""",
        (regelsatz,),
    ).fetchall()
    return {(str(z["merkmal"]), str(z["version"])): str(z["code"]) for z in zeilen}


def zaehl_zeitraum(conn: Verbindung, regelsatz: str, monat: str) -> str:
    """Zeitraumart der Bestandsregel des Regelsatzes: v1 „Stichtag“, nach Auftrag 2 „Monat“ (Regeln als Daten)."""
    return str(regel_wert(eine(regeln_laden(conn, regelsatz, monat), "zaehl", "bestand"), "zeitraum_art"))


def _gerechnete_monate(conn: Verbindung, regelsatz: str) -> list[str]:
    zeilen = conn.execute(
        """
        SELECT DISTINCT lieferung FROM meta.lauf
        WHERE regelsatz = %s AND status IN ('fertig', 'unveraendert') ORDER BY lieferung
        """,
        (regelsatz,),
    ).fetchall()
    return [str(z["lieferung"]) for z in zeilen]


def _oenace_versionen(conn: Verbindung, monat: str) -> set[str]:
    zeilen = conn.execute(
        """
        SELECT DISTINCT version FROM stat.klass_oenace
        WHERE ebene = 1 AND gueltig_von <= %s AND (gueltig_bis IS NULL OR gueltig_bis >= %s)
        """,
        (ergebnis.monatserster(monat), ergebnis.monatsletzter(monat)),
    ).fetchall()
    return {str(z["version"]) for z in zeilen}


def merkmal_von(conn: Verbindung, blatt: str) -> tuple[str, str, dict[str, str]]:
    """Merkmal, Version und Bezeichnungen je Blatt (für ergänzte Zeilen).

    Nur die Ebene, nach der die Statistik zählt: Bundesländer (Region) und Abschnitte (ÖNACE). Bezirke,
    Gemeinden und die ÖNACE-Ebenen 2 bis 5 stehen in denselben Tabellen und gehören nicht ins Sheet.
    """
    if blatt == BLATT_BUNDESLAND:
        return (
            "bundesland",
            "-",
            _dict(
                conn,
                "SELECT code, bezeichnung FROM stat.klass_region WHERE ebene IN ('staat', 'bundesland')"
                " ORDER BY version",
            ),
        )
    if blatt == BLATT_GESCHLECHT:
        return "geschlecht", "-", _dict(conn, "SELECT code, bezeichnung FROM stat.klass_geschlecht")
    if blatt == BLATT_KATEGORIE:
        return "qualifikation", "-", _dict(conn, "SELECT code, bezeichnung FROM stat.klass_qualifikation")
    version = blatt.removeprefix(OENACE_PRAEFIX)
    return (
        "oenace",
        version,
        _dict(
            conn,
            "SELECT code, bezeichnung FROM stat.klass_oenace WHERE version = %s AND ebene = 1",
            (version,),
        ),
    )


def _zip_fest(daten: bytes, zeit: datetime, ersetzen: dict[str, bytes]) -> bytes:
    """Schreibt das Archiv neu mit festem Zeitstempel je Eintrag (openpyxl setzt „jetzt“).

    `ersetzen` tauscht einzelne Einträge aus (docProps/core.xml: `save` überschreibt `modified`).
    """
    stempel = (zeit.year, zeit.month, zeit.day, zeit.hour, zeit.minute, zeit.second)
    aus = io.BytesIO()
    with zipfile.ZipFile(io.BytesIO(daten)) as quelle, zipfile.ZipFile(aus, "w") as ziel:
        for info in quelle.infolist():
            neu = zipfile.ZipInfo(info.filename, date_time=stempel)
            neu.compress_type = info.compress_type
            neu.external_attr = info.external_attr
            ziel.writestr(neu, ersetzen.get(info.filename) or quelle.read(info.filename))
    return aus.getvalue()


def sheet_schreiben(
    conn: Verbindung,
    regelsatz: str = "v1",
    ziel: Path | None = None,
    vorlage: Path | None = None,
) -> SheetErgebnis:
    """Füllt die Vorlage mit allen in `regelsatz` gerechneten Monaten und speichert sie.

    Ziel ist standardmäßig ``konfig.abgabe()/aggregationen_<regelsatz>.xlsx``. Wirft ``ValueError``,
    wenn ein Monat keine Spalte oder ein Code (außer „unbekannt“) keine Zeile in der Vorlage hat.
    """
    vorlage = vorlage or konfig.vorlagen() / VORLAGE_DATEI
    ziel = ziel or konfig.abgabe() / f"aggregationen_{regelsatz}.xlsx"
    wb = load_workbook(vorlage)

    monate = _gerechnete_monate(conn, regelsatz)
    unbekannt = _unbekannt_codes(conn, regelsatz)
    qual_kategorie = {
        str(z["code"]): str(z["beschaeftigungskategorie"])
        for z in conn.execute(
            "SELECT code, beschaeftigungskategorie FROM stat.klass_qualifikation"
        ).fetchall()
    }
    kategorien = _dict(conn, "SELECT code, bezeichnung FROM stat.klass_beschaeftigungskategorie")

    # Summen je Blatt, Monat und Code; Monate je Blatt.
    werte: dict[str, dict[str, dict[str, int]]] = defaultdict(lambda: defaultdict(lambda: defaultdict(int)))
    blatt_monate: dict[str, list[str]] = defaultdict(list)
    vorlaeufig: dict[str, str] = {}
    fortgeschrieben: dict[str, int] = {}
    letztes_ende: datetime | None = None
    zeitraum_arten: set[str] = set()
    for monat in monate:
        stand = ergebnis.letzter_lauf(conn, monat, regelsatz)
        assert stand is not None
        lauf = conn.execute(
            "SELECT beendet_am, meldung, fortgeschrieben FROM meta.lauf WHERE id = %s", (stand.lauf_id,)
        ).fetchone()
        assert lauf is not None
        ende = lauf["beendet_am"]
        if isinstance(ende, datetime) and (letztes_ende is None or ende > letztes_ende):
            letztes_ende = ende
        # Zeitraumart aus der Bestandsregel des Regelsatzes: v1 zählt am Stichtag, v2 über das ganze Monat
        # (Auftrag 2). Fest „Stichtag“ ergab für v2 lauter Nullen.
        art = zaehl_zeitraum(conn, regelsatz, monat)
        zeitraum_arten.add(art)
        zellen = [
            z
            for z in ergebnis.monatswerte(conn, monat, regelsatz)
            if z["zeitraum_art"] == art and z["variable"] == STICHTAG_VARIABLE
        ]
        if int(str(lauf["fortgeschrieben"] or 0)) > 0:
            fortgeschrieben[monat] = int(str(lauf["fortgeschrieben"]))
        if stand.ergebnis_status == "vorlaeufig" or any(z["status"] == "vorlaeufig" for z in zellen):
            vorlaeufig[monat] = str(lauf["meldung"] or "Ergebnis vorläufig")
        versionen = _oenace_versionen(conn, monat) | {str(z["oenace_version"]) for z in zellen}
        for festes_blatt in (BLATT_BUNDESLAND, BLATT_GESCHLECHT, BLATT_KATEGORIE):
            blatt_monate[festes_blatt].append(monat)
        for version in sorted(versionen):
            blatt_monate[OENACE_PRAEFIX + version].append(monat)
        for z in zellen:
            wert = int(str(z["wert"]))
            werte[BLATT_BUNDESLAND][monat][str(z["region"])] += wert
            werte[BLATT_GESCHLECHT][monat][str(z["geschlecht"])] += wert
            werte[BLATT_KATEGORIE][monat][str(z["qualifikation"])] += wert
            werte[OENACE_PRAEFIX + str(z["oenace_version"])][monat][str(z["oenace"])] += wert

    # Kategorien statt Qualifikationen (Regelsatz mit Änderungsauftrag 1)?
    kat_codes = {c for m in werte[BLATT_KATEGORIE].values() for c, w in m.items() if w}
    ist_kategorie = bool(kat_codes) and kat_codes <= set(kategorien) and not kat_codes <= set(qual_kategorie)

    ergaenzt: dict[str, list[str]] = {}
    summen: dict[str, dict[str, int]] = {}
    for name in wb.sheetnames:
        if name not in blatt_monate:
            continue
        blatt = _blatt_lesen(wb[name])
        merkmal, version, texte = merkmal_von(conn, name)
        unb = unbekannt.get((merkmal, version))
        belegt = {c for m in werte[name].values() for c, w in m.items() if w}

        if name == BLATT_KATEGORIE and ist_kategorie:
            unb_kat = qual_kategorie.get(unb) if unb else None
            reihe: list[str] = []
            for code in blatt.zeilen:
                kat = qual_kategorie.get(code, code if code in kategorien else None)
                if kat is not None and kat not in reihe and kat != unb_kat:
                    reihe.append(kat)
            fremd = sorted(belegt - set(reihe) - ({unb_kat} if unb_kat else set()))
            if fremd:
                raise ValueError(f"Blatt {name}: Kategorien ohne Zeile in der Vorlage: {fremd}")
            if unb_kat and unb_kat in belegt:
                reihe.append(unb_kat)
            _zeilen_neu(blatt, [(k, kategorien.get(k, k)) for k in reihe])
            ergaenzt[name] = reihe
        else:
            fehlend = sorted(belegt - set(blatt.zeilen))
            if fehlend and fehlend != [unb]:
                raise ValueError(f"Blatt {name}: Codes ohne Zeile in der Vorlage: {fehlend}")
            if fehlend and unb is not None:
                zeilen = [
                    (c, str(blatt.ws.cell(r, blatt.text_spalte).value or "")) for c, r in blatt.zeilen.items()
                ]
                _zeilen_neu(blatt, [*zeilen, (unb, texte.get(unb, "Unbekannt"))])
                ergaenzt[name] = [unb]

        ws = blatt.ws
        summen[name] = {}
        for monat in blatt_monate[name]:
            spalte = blatt.spalten.get(monat)
            if spalte is None:
                raise ValueError(f"Blatt {name}: keine Spalte für {monat}")
            for code, r in blatt.zeilen.items():
                ws.cell(r, spalte).value = werte[name][monat].get(code, 0)
            summen[name][monat] = sum(werte[name][monat].get(code, 0) for code in blatt.zeilen)
            if monat in vorlaeufig:
                text = f"vorläufig: {vorlaeufig[monat]}"
                if monat in fortgeschrieben:
                    anzahl = f"{fortgeschrieben[monat]:,}".replace(",", ".")
                    text += (
                        f" · enthält {anzahl} fortgeschriebene Verhältnisse aus der Vorlieferung"
                        " (Regel E07), getrennt ausgewiesen im Qualitätsbericht"
                    )
                ws.cell(blatt.kopfzeile, spalte).comment = Comment(text, KOMMENTAR_AUTOR)

    gesamt = summen.get(BLATT_BUNDESLAND, {})
    abweichungen = sorted(
        {m for s in summen.values() for m, w in s.items() if w != gesamt.get(m)}
        | {m for m in monate if sum(werte[BLATT_BUNDESLAND][m].values()) != gesamt.get(m)}
    )

    if BLATT_HINWEISE in wb.sheetnames:
        hinweise = wb[BLATT_HINWEISE]
        zeile = hinweise.max_row + 2
        spanne = f"{monate[0]} bis {monate[-1]}" if monate else "keine"
        vorl = ", ".join(vorlaeufig) if vorlaeufig else "keine"
        hinweise.cell(zeile, 1).value = (
            f"Erzeugt aus stat.stat_beschaeftigte, Regelsatz {regelsatz}, Monate {spanne}; "
            f"vorläufig: {vorl}. 0 = gerechnet, keine Fälle; leer = Monat nicht gerechnet."
        )
        if zeitraum_arten - {STICHTAG}:
            # Die Vorlage sagt „am Stichtag“; für einen anderen Zählzeitraum steht hier, was die Werte bedeuten.
            hinweise.cell(zeile, 1).value = str(hinweise.cell(zeile, 1).value) + (
                " Gezählt sind Verhältnisse, die im Berichtsmonat mindestens einen Tag bestehen (ganzes Monat statt"
                " Stichtag, Regel R2_R4)."
            )
        if fortgeschrieben:
            liste = "; ".join(
                f"{m}: {n:,} Verhältnisse".replace(",", ".") for m, n in sorted(fortgeschrieben.items())
            )
            hinweise.cell(zeile + 1, 1).value = (
                "Fortgeschrieben, vorläufig (Regel E07, belegter Lieferausfall): fehlende Verhältnisse einmalig aus der "
                f"Vorlieferung ergänzt und in den Werten enthalten – {liste}. Getrennt ausgewiesen im Qualitätsbericht "
                "des Monats, § 1."
            )

    if letztes_ende is not None:
        fest = letztes_ende.astimezone(UTC).replace(tzinfo=None, microsecond=0)
    else:
        fest = (wb.properties.created or datetime(2026, 1, 1)).replace(microsecond=0)
    wb.properties.created = fest
    wb.properties.modified = fest

    puffer = io.BytesIO()
    wb.save(puffer)
    wb.properties.modified = fest  # save() setzt „jetzt“; Kern-Eigenschaften mit festem Wert neu schreiben
    kern = tostring(wb.properties.to_tree())
    ziel.parent.mkdir(parents=True, exist_ok=True)
    ziel.write_bytes(_zip_fest(puffer.getvalue(), fest, {"docProps/core.xml": kern}))

    return SheetErgebnis(
        pfad=ziel,
        regelsatz=regelsatz,
        monate=monate,
        summen=summen,
        abweichungen=abweichungen,
        vorlaeufig=vorlaeufig,
        fortgeschrieben=fortgeschrieben,
        kategorien=ist_kategorie,
        ergaenzt=ergaenzt,
    )
