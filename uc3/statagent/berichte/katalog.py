"""Nachweise für Betrieb v1 (#16): Laufmanifest (AC1) und Prüfkatalog P01–P24 (AC2) als CSV.

Beide Dateien entstehen nur aus gespeicherten Daten (``meta.lauf``, ``meta.revision``, ``meta.pruefung_treffer``,
``meta.regel``) und aus dem Code von ``statagent/pruefungen.py``. Kein Wert steht hier als Konstante; die
Spaltennamen sind Aufbau der Datei, keine Regel.

CSV: Trenner Komma, UTF-8, Zeilenende ``\\n``, sortiert nach Monat bzw. Platz. Zeitpunkte als ISO 8601 in UTC.
Gleiche Datenbank → gleiche Datei.
"""

from __future__ import annotations

import csv
import inspect
import json
import re
from collections.abc import Iterable, Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from statagent import ergebnis
from statagent.db import Verbindung, lieferungen
from statagent.pruefungen import ARTEN

MANIFEST_SPALTEN = (
    "monat",
    "lauf_id",
    "lauf_status",
    "regelsatz",
    "regelstand",
    "ergebnis_status",
    "ergebnis_hash",
    "zellen",
    "gelesen",
    "gezaehlt",
    "nicht_gezaehlt",
    "ausgeschlossen",
    "korrigiert",
    "fortgeschrieben",
    "gestartet_am",
    "beendet_am",
    "veroeffentlicht",
    "weitere_laeufe",
    "verwendete_lieferungen",
    "spaeteste_verwendete_lieferung",
    "nach_laufmonat",
)

KATALOG_SPALTEN = (
    "platz",
    "name",
    "art",
    "ebene",
    "schwelle",
    "einstufung",
    "einstufungen_faelle",
    "massnahme",
    "massnahmen_faelle",
    "anhalten",
    "beschreibung",
    "begruendung",
    "grundlage",
    "bezug_regel",
    "rueckfrage",
    "herkunft",
    "forensik",
    "befund",
    "sql",
    "status",
)

# Aufbau von meta.regel.parameter (Kommentar in db/120_pruefregeln_v1.sql): diese Schlüssel beschreiben Einstufung,
# Maßnahme und Bezug. Alles andere in `parameter` ist Kriterium oder Schwelle der Prüfung.
_KEINE_SCHWELLE = {"ebene", "regel", "bezug", "einstufung", "massnahme", "anhalten", "rueckfrage"}
_MONAT = re.compile(r"^\d{4}-\d{2}$")
_PLATZ = re.compile(r"^P(\d{2})_")
_REGEL_IM_TEXT = re.compile(r"\bRegel ([A-Z]\w*)")
_RUECKFRAGE_IM_TEXT = re.compile(r"\bRückfrage ([A-Z]\d+)")
_FORENSIK_IM_TEXT = re.compile(r"\bForensik Nr\. (\d+)")


# --- gemeinsam -----------------------------------------------------------------------------------------


def _iso(wert: object) -> str:
    if wert is None:
        return ""
    if isinstance(wert, datetime):
        return wert.astimezone(UTC).isoformat(timespec="seconds")
    return str(wert)


def _csv_schreiben(pfad: Path, spalten: Iterable[str], zeilen: list[dict[str, str]]) -> Path:
    pfad = Path(pfad)
    pfad.parent.mkdir(parents=True, exist_ok=True)
    with pfad.open("w", encoding="utf-8", newline="") as f:
        schreiber = csv.DictWriter(f, fieldnames=list(spalten), delimiter=",", lineterminator="\n")
        schreiber.writeheader()
        schreiber.writerows(zeilen)
    return pfad


# --- AC1 Laufmanifest ----------------------------------------------------------------------------------


def _monate_in(wert: object) -> set[str]:
    """Alle Werte der Form JJJJ-MM in einem JSON-Wert (rekursiv). Tagesdaten (JJJJ-MM-TT) zählen nicht."""
    if isinstance(wert, str):
        return {wert} if _MONAT.match(wert) else set()
    if isinstance(wert, Mapping):
        return set().union(*(_monate_in(v) for v in wert.values())) if wert else set()
    if isinstance(wert, list):
        return set().union(*(_monate_in(v) for v in wert)) if wert else set()
    return set()


def _verwendete_lieferungen(conn: Verbindung, lauf_id: int, monat: str, fortgeschrieben: int) -> list[str]:
    """Lieferungen, deren Daten der Lauf gelesen hat. ``meta.lauf`` speichert das nicht direkt; abgeleitet aus:

    1. der eigenen Lieferung ``monat`` (Bereinigung und Zählung lesen nur ``roh.lieferung`` dieses Monats);
    2. ``meta.revision.berichtsmonat`` des Laufs: Vormonate, die aus der eigenen Lieferung nachgerechnet und mit
       dem veröffentlichten Wert verglichen wurden, der aus der Lieferung jenes Monats stammt;
    3. bei ``fortgeschrieben > 0`` der Vorlieferung (Regel E07 übernimmt Abschnitte aus der Lieferung des
       Vormonats, ``statagent/bereinigung.py:_fortschreiben``);
    4. allen Monatsangaben (JJJJ-MM) in ``meta.pruefung_treffer.details`` des Laufs, z. B. ``vormonat``,
       ``vormonat_lieferung``, ``vergleichsmonat``: gegen diese Lieferungen haben die Prüfungen verglichen.
    """
    verwendet = {monat}
    revision = conn.execute(
        "SELECT DISTINCT berichtsmonat FROM meta.revision WHERE lauf_id = %s", (lauf_id,)
    ).fetchall()
    verwendet |= {str(z["berichtsmonat"]) for z in revision}
    if fortgeschrieben > 0:
        verwendet.add(ergebnis.monat_verschieben(monat, -1))
    treffer = conn.execute(
        "SELECT details FROM meta.pruefung_treffer WHERE lauf_id = %s", (lauf_id,)
    ).fetchall()
    for z in treffer:
        verwendet |= _monate_in(z["details"])
    return sorted(verwendet)


def laufmanifest_zeilen(conn: Verbindung, regelsatz: str = "v1") -> list[dict[str, str]]:
    """Je Berichtsmonat eine Zeile mit dem maßgeblichen Lauf des Regelsatzes, sortiert nach Monat.

    Maßgeblich ist der Lauf, den auch Sheet und Qualitätsbericht verwenden (``ergebnis.letzter_lauf``): der jüngste
    veröffentlichte, sonst der jüngste erfolgreiche (Status ``fertig`` oder ``unveraendert``; ``unveraendert`` ist
    ein Neulauf mit identischem bzw. veröffentlichtem Ergebnis). Läufe mit Status ``laeuft`` oder ``abgebrochen``
    zählen nicht. Monate ohne erfolgreichen Lauf erscheinen nicht; sie liefert ``laufmanifest_luecken``.
    ``nach_laufmonat`` ist die Anzahl verwendeter Lieferungen nach dem Berichtsmonat (Soll 0).
    """
    monate = conn.execute(
        "SELECT DISTINCT lieferung FROM meta.lauf WHERE regelsatz = %s ORDER BY lieferung", (regelsatz,)
    ).fetchall()
    zeilen: list[dict[str, str]] = []
    for m in monate:
        monat = str(m["lieferung"])
        stand = ergebnis.letzter_lauf(conn, monat, regelsatz)
        if stand is None:
            continue
        lauf = conn.execute(
            """SELECT l.*, (SELECT count(*) FROM meta.lauf w
                            WHERE w.lieferung = l.lieferung AND w.regelsatz = l.regelsatz AND w.id <> l.id) AS weitere
               FROM meta.lauf l WHERE l.id = %s""",
            (stand.lauf_id,),
        ).fetchone()
        if lauf is None:
            continue
        fortgeschrieben = int(str(lauf["fortgeschrieben"] or 0))
        verwendet = _verwendete_lieferungen(conn, stand.lauf_id, monat, fortgeschrieben)
        zeilen.append(
            {
                "monat": monat,
                "lauf_id": str(stand.lauf_id),
                "lauf_status": str(lauf["status"]),
                "regelsatz": regelsatz,
                "regelstand": _iso(lauf["regelstand"]),
                "ergebnis_status": _iso(lauf["ergebnis_status"]),
                "ergebnis_hash": _iso(lauf["ergebnis_hash"]),
                "zellen": _iso(lauf["zellen"]),
                "gelesen": _iso(lauf["gelesen"]),
                "gezaehlt": _iso(lauf["gezaehlt"]),
                "nicht_gezaehlt": _iso(lauf["nicht_gezaehlt"]),
                "ausgeschlossen": _iso(lauf["ausgeschlossen"]),
                "korrigiert": _iso(lauf["korrigiert"]),
                "fortgeschrieben": str(fortgeschrieben),
                "gestartet_am": _iso(lauf["gestartet_am"]),
                "beendet_am": _iso(lauf["beendet_am"]),
                "veroeffentlicht": "ja" if lauf["freigegeben_am"] is not None else "nein",
                "weitere_laeufe": str(lauf["weitere"]),
                "verwendete_lieferungen": ";".join(verwendet),
                "spaeteste_verwendete_lieferung": verwendet[-1],
                "nach_laufmonat": str(sum(1 for v in verwendet if v > monat)),
            }
        )
    return zeilen


def laufmanifest_luecken(conn: Verbindung, regelsatz: str = "v1") -> list[str]:
    """Geladene Lieferungen (``roh.ladeprotokoll``) ohne erfolgreichen Lauf des Regelsatzes, aufsteigend.

    Getrennt von ``laufmanifest_zeilen``, damit ein Manifest mit Lücken trotzdem geschrieben und die Lücke
    benannt werden kann, statt dass der Export abbricht.
    """
    return [m for m in lieferungen(conn) if ergebnis.letzter_lauf(conn, m, regelsatz) is None]


def laufmanifest_schreiben(conn: Verbindung, pfad: Path, regelsatz: str = "v1") -> Path:
    """Schreibt ``laufmanifest_zeilen`` als CSV nach ``pfad`` (z. B. ``docs/plan/uc3/laufmanifest-v1.csv``)."""
    return _csv_schreiben(pfad, MANIFEST_SPALTEN, laufmanifest_zeilen(conn, regelsatz))


# --- AC2 Prüfkatalog -----------------------------------------------------------------------------------


def _wert_lesbar(wert: object) -> str:
    if isinstance(wert, str):
        return wert
    return json.dumps(wert, ensure_ascii=False, sort_keys=True)


def _faelle(parameter: Mapping[str, Any], praefix: str) -> str:
    teile = [
        f"{k.removeprefix(praefix)}: {_wert_lesbar(v)}"
        for k, v in sorted(parameter.items())
        if k.startswith(praefix)
    ]
    return "; ".join(teile) if teile else "keine weiteren Fälle"


def _schwelle(parameter: Mapping[str, Any]) -> str:
    teile = [
        f"{k}={_wert_lesbar(v)}"
        for k, v in sorted(parameter.items())
        if k not in _KEINE_SCHWELLE and not k.startswith(("einstufung_", "massnahme_"))
    ]
    return "; ".join(teile) if teile else "keine Schwelle: jeder Treffer zählt"


def _code_stelle(art: str) -> str | None:
    """``statagent/pruefungen.py:<funktion>`` der Prüfart laut ``pruefungen.ARTEN``, sonst None."""
    funktion = ARTEN.get(art)
    if funktion is None:
        return None
    datei = inspect.getsourcefile(funktion)
    if datei is None:
        return None
    paket = Path(datei).resolve().parents[1]
    return f"{Path(datei).resolve().relative_to(paket).as_posix()}:{funktion.__name__}"


def _bezug(
    conn: Verbindung, regelsatz: str, parameter: Mapping[str, Any], grundlage: str
) -> list[dict[str, Any]]:
    """Regeln, auf die sich die Prüfung bezieht: ``parameter.regel`` (voller Name) und „Regel X“ in der Grundlage
    (Kurzname, z. B. E03 → E03_datum_pruefen)."""
    namen = [str(parameter["regel"])] if parameter.get("regel") else []
    namen += _REGEL_IM_TEXT.findall(grundlage)
    gefunden: dict[str, dict[str, Any]] = {}
    for n in namen:
        for z in conn.execute(
            """SELECT name, grundlage FROM meta.regel
               WHERE regelsatz = %s AND typ <> 'pruefung' AND (name = %s OR name LIKE %s) ORDER BY name""",
            (regelsatz, n, f"{n}\\_%"),
        ).fetchall():
            gefunden[str(z["name"])] = dict(z)
    return [gefunden[k] for k in sorted(gefunden)]


def _pflicht(platz: str, name: str, feld: str, wert: object) -> str:
    if wert is None or (isinstance(wert, str) and not wert.strip()):
        raise ValueError(f"Prüfkatalog {platz} ({name}): Pflichtfeld '{feld}' fehlt in meta.regel")
    return wert if isinstance(wert, str) else _wert_lesbar(wert)


def pruefkatalog_zeilen(conn: Verbindung, regelsatz: str = "v1") -> list[dict[str, str]]:
    """Je aktiver Prüfregel (``meta.regel``, Typ ``pruefung``) des Regelsatzes ein Katalogplatz, sortiert nach Platz.

    Der Platz (P01 …) kommt aus dem Regelnamen. ``status`` ist ``umgesetzt`` nur, wenn ``pruefungen.ARTEN`` für die
    Art einen Code-Pfad hat (``sql`` nennt ihn), sonst ``offen``. ``forensik`` nennt die Forensikprüfungen R01–R19,
    die den Platz laut ``meta.forensik_pruefung`` (125_forensik.sql) abdecken; ``herkunft`` ist dann ``forensik``,
    sonst ``anhang_a``, wenn die Grundlage „Anhang A“ nennt, sonst ``zusatz``. ``befund`` nennt Befunde aus dem
    Fallenkatalog („Forensik Nr. …“ in der Grundlage der Prüfung oder einer Bezugsregel).

    Wirft ``ValueError`` bei leerem Pflichtfeld (Platz und Feld im Text), bei einem Namen ohne Platz, bei doppeltem
    Platz und bei einer Lücke in der Platzfolge.
    """
    regeln = conn.execute(
        """SELECT name, art, reihenfolge, parameter, beschreibung, begruendung, grundlage FROM meta.regel
           WHERE regelsatz = %s AND typ = 'pruefung' AND aktiv ORDER BY name""",
        (regelsatz,),
    ).fetchall()
    zeilen: list[dict[str, str]] = []
    for r in regeln:
        name = str(r["name"])
        treffer = _PLATZ.match(name)
        if treffer is None:
            raise ValueError(f"Prüfregel {name}: Name beginnt nicht mit einem Platz Pnn_")
        platz = f"P{treffer.group(1)}"
        p: Mapping[str, Any] = r["parameter"] if isinstance(r["parameter"], Mapping) else {}
        art = _pflicht(platz, name, "art", r["art"])
        grundlage = _pflicht(platz, name, "grundlage", r["grundlage"])
        if not isinstance(p.get("anhalten"), bool):
            raise ValueError(f"Prüfkatalog {platz} ({name}): Pflichtfeld 'anhalten' fehlt in meta.regel")

        bezug = _bezug(conn, regelsatz, p, grundlage)
        forensik = [
            f"{z['nr']} {z['name']} ({z['schwelle']})"
            for z in conn.execute(
                "SELECT nr, name, schwelle FROM meta.forensik_pruefung WHERE %s = ANY(plaetze) ORDER BY nr",
                (platz,),
            ).fetchall()
        ]
        befunde = sorted(
            {f"Befund Nr. {n}" for n in _FORENSIK_IM_TEXT.findall(grundlage)}
            | {
                f"Befund Nr. {n} (über {b['name']})"
                for b in bezug
                for n in _FORENSIK_IM_TEXT.findall(str(b["grundlage"]))
            }
        )
        if forensik:
            herkunft = "forensik"
        elif "Anhang A" in grundlage:
            herkunft = "anhang_a"
        else:
            herkunft = "zusatz"
        rueckfragen = sorted(
            set(_RUECKFRAGE_IM_TEXT.findall(grundlage))
            | ({str(p["rueckfrage"])} if p.get("rueckfrage") else set())
        )
        code = _code_stelle(art)
        zeilen.append(
            {
                "platz": platz,
                "name": name,
                "art": art,
                "ebene": _pflicht(platz, name, "ebene", p.get("ebene")),
                "schwelle": _schwelle(p),
                "einstufung": _pflicht(platz, name, "einstufung", p.get("einstufung")),
                "einstufungen_faelle": _faelle(p, "einstufung_"),
                "massnahme": _pflicht(platz, name, "massnahme", p.get("massnahme")),
                "massnahmen_faelle": _faelle(p, "massnahme_"),
                "anhalten": "ja" if p["anhalten"] else "nein",
                "beschreibung": _pflicht(platz, name, "beschreibung", r["beschreibung"]),
                "begruendung": _pflicht(platz, name, "begruendung", r["begruendung"]),
                "grundlage": grundlage,
                "bezug_regel": "; ".join(str(b["name"]) for b in bezug) or "keine",
                "rueckfrage": "; ".join(rueckfragen) or "keine",
                "herkunft": herkunft,
                "forensik": "; ".join(forensik) or "keine Forensikprüfung (Zusatzprüfung)",
                "befund": "; ".join(befunde) or "keiner",
                "sql": code or f"kein Code-Pfad für Art '{art}' in statagent/pruefungen.py",
                "status": "umgesetzt" if code else "offen",
            }
        )

    zeilen.sort(key=lambda z: z["platz"])
    plaetze = [z["platz"] for z in zeilen]
    if len(set(plaetze)) != len(plaetze):
        doppelt = sorted({x for x in plaetze if plaetze.count(x) > 1})
        raise ValueError(f"Prüfkatalog: Platz mehrfach belegt: {', '.join(doppelt)}")
    for nr, platz in enumerate(plaetze, start=1):
        if platz != f"P{nr:02d}":
            raise ValueError(f"Prüfkatalog: Platz P{nr:02d} ist nicht belegt (nächster belegter: {platz})")
    return zeilen


def pruefkatalog_schreiben(conn: Verbindung, pfad: Path, regelsatz: str = "v1") -> Path:
    """Schreibt ``pruefkatalog_zeilen`` als CSV nach ``pfad`` (z. B. ``uc3/pruefkatalog.csv``)."""
    return _csv_schreiben(pfad, KATALOG_SPALTEN, pruefkatalog_zeilen(conn, regelsatz))
