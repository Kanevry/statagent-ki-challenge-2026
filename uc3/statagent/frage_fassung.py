"""Zwei ÖNACE-Fassungen vergleichen (78-AC2): „ÖNACE C 2008 vs 2025“ meint Fassungen, keinen Zeitraum.

Die Antwort nennt beide Fassungen mit Name und Gültigkeit, wie viele Unterklassen auf einen oder mehrere Codes führen,
einen Code ohne eindeutige Umcodierung und welche Abschnitte Teile abgeben oder aufnehmen. Sie nennt keine
Beschäftigtenzahl und wählt kein Ziel aus. Alle Namen, Codes und Beziehungen kommen aus ``stat.klass_oenace`` und
``stat.uebergang``; Dateiname und 1:n stehen im Beleg, nicht im Text.

Antwortet nur, wenn beide Jahre echte Fassungen sind und die Frage weder Zahl noch Monat noch Merkmal nennt; alles
andere bleibt beim bisherigen Weg. Nur lesend. Importiert ``plattform.llm`` nicht (R2).
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import Any

import psycopg
from psycopg import sql

from statagent import klass
from statagent.agenten.werkzeuge import AbfrageVerweigert
from statagent.db import Verbindung
from statagent.frage import (
    _BUNDESLAND,
    _FLUKTUATION,
    _GESCHLECHT,
    _ZEITREIHE,
    NICHT_LESBAR,
    _Abgeschnitten,
    _antwort,
    _lesen,
    _treffer,
    fragetyp,
    monate_lesen,
    nicht_auswertbar,
)
from statagent.frage_klass import (
    _JAHR,
    _ZAHLEN_FRAGE,
    _ÖNACE_WORT,
    HOECHSTENS,
    OENACE,
    _beleg,
    _erklaerung,
    _monat,
    _nachsehen,
    codes_erkennen,
)

ABSCHNITTE = "oenace"
UNTERKLASSEN = klass.UNTERKLASSE
_ABSCHNITT_BEISPIEL = "ÖNACE C 2008 vs 2025"

#: Woran man erkennt, dass die zwei Jahre gegenübergestellt werden. „von 2008 bis 2025“ bleibt ein Zeitraum.
_SIGNAL = re.compile(
    r"(?<![a-zäöü])(?:vs\.?|versus)(?![a-zäöü])|gegen|unterschied|unterscheid|vergleich|änder|aender|anders"
    r"|umsteig|umcodier|umstell|wechsel|übergang|uebergang|fassung|version"
    # „2008 und 2025“, auch „2008 und ÖNACE C 2025“.
    r"|(?:19|20)\d{2}\s*(?:und|/|&)\s*(?:\S+\s+){0,3}(?:19|20)\d{2}"
    r"|(?:19|20)\d{2}\s+(?:auf|nach|zu)\s+(?:19|20)\d{2}"
)
#: Zeitangaben, die monate_lesen nicht als Monat liest; dann ist ein Zeitraum gemeint, keine Fassung.
_ZEIT_WORT = re.compile(r"quartal|halbjahr|winter|sommer|frühling|fruehling|herbst|saison|monat")
#: Fragt nach Daten, ohne dass _ZAHLEN_FRAGE es merkt; eine Erklärung der Listen wäre daran vorbei geantwortet.
_DATEN_WORT = re.compile(
    r"angestellt|lehrling|beamt|anteil|prozent|%|wachstum|gewachsen|wächst|waechst|zunahme|abnahme|rückgang"
    r"|rueckgang|gestiegen|gesunken|jährig|jaehrig|\balter\b|bezirk|gemeinde"
)
#: „Wie viele Unterklassen wechseln …“ zählt Codes, keine Menschen.
_ZAEHLT_CODES = re.compile(r"(?:wie\s*viele?|anzahl\s+der)\s+(?:unterklassen|codes|abschnitte|buchstaben)")
_ABSCHNITT = re.compile(
    r"(?<!\w)(?:(?i:önace|oenace|nace)(?:[\s-]+(?:19|20)\d{2})?[\s:-]*(?:(?i:abschnitt)[\s:-]+)?|(?i:abschnitt)[\s:-]+)"
    # Einzelne Buchstaben in jeder Schreibweise, längere Codes (UNB, DA) nur groß; „VS“ ist das Vergleichswort.
    r"(?P<code>(?!VS(?!\w))[A-Z]{2,3}|[A-Za-z])(?!\w)"
)
#: Ohne das Wort davor nur groß: „Vergleiche ÖNACE 2008 und 2025 für Q“, „ÖNACE 2008 und 2025 C“.
_ABSCHNITT_LOSE = re.compile(
    r"(?<!\w)(?:(?i:für|fuer|bei|von|zu|in)\s+(?:(?i:den|dem)\s+)?(?:(?i:abschnitt)\s+)?|(?:19|20)\d{2}\s+)"
    r"(?P<code>[A-Z])(?!\w)"
)


@dataclass(frozen=True)
class Vergleich:
    """Zwei Jahre, ältere Fassung zuerst, und der Abschnitt, falls die Frage einen nennt."""

    alt: str
    neu: str
    code: str | None


def vergleich_erkennen(frage: str) -> Vergleich | None:
    """Reine Funktion ohne Datenbank: Ob die Jahre echte Fassungen sind, prüft erst die Antwort."""
    vergleich = _gegenueberstellung(frage)
    if vergleich is None or nicht_auswertbar(frage.lower(), mittel=True) is not None:
        return None
    return vergleich


def _gegenueberstellung(frage: str) -> Vergleich | None:
    """Die Form „zwei Jahre gegenübergestellt“, noch ohne die Frage, ob sie überhaupt auswertbar ist."""
    text = unicodedata.normalize("NFC", frage)
    klein = text.lower()
    if not _ÖNACE_WORT.search(text) or not _SIGNAL.search(klein):
        return None
    jahre = sorted(set(_JAHR.findall(text)))
    if len(jahre) != 2 or monate_lesen(text) or _ZEIT_WORT.search(klein):
        return None
    ohne_codes = _ZAEHLT_CODES.sub(" ", klein)
    merkmale = (_ZAHLEN_FRAGE, _FLUKTUATION, _GESCHLECHT, _BUNDESLAND, _ZEITREIHE, _DATEN_WORT)
    if any(m.search(ohne_codes) for m in merkmale):
        return None
    treffer = _ABSCHNITT.search(text) or _ABSCHNITT_LOSE.search(text)
    return Vergleich(jahre[0], jahre[1], treffer.group("code").upper() if treffer else None)


def fassungsvergleich_antwort(conn: Verbindung, frage: str) -> dict[str, Any] | None:
    """Fertige Antwort, wenn die Frage zwei ÖNACE-Fassungen vergleicht; sonst None (bisheriger Weg). Wirft nie."""
    if _gegenueberstellung(frage) is None:
        return None
    # Einzeldaten und Merkmale, die es nicht gibt: ihre Absage, weder Erklärung der Listen noch Rückfrage zur Zeitreihe.
    absage = nicht_auswertbar(frage.lower(), mittel=True)
    if absage is not None:
        return _antwort(fragetyp(frage), absage, hinweise=[absage])
    vergleich = vergleich_erkennen(frage)
    assert vergleich is not None
    try:
        return _beantworten(conn, frage, vergleich)
    except (psycopg.Error, AbfrageVerweigert, _Abgeschnitten):
        return _antwort("definition", NICHT_LESBAR, hinweise=[NICHT_LESBAR])


def _beantworten(conn: Verbindung, frage: str, v: Vergleich) -> dict[str, Any] | None:
    fassungen = _fassungen_lesen(conn, v)
    if len(fassungen) != 2:
        return None  # „ÖNACE C 2024 vs 2025“: keine Fassungen, also doch ein Zeitraum.
    laender = _lesen(conn, "SELECT bezeichnung FROM stat.klass_region WHERE ebene = 'bundesland'")
    if any(_treffer(frage.lower(), str(z["bezeichnung"])) for z in laender):
        return None  # „… in Wien“ fragt nach Daten, nicht nach den Listen.
    codes = codes_erkennen(frage)
    if codes:
        if any(c.art != OENACE for c in codes):
            return None  # „… im Bezirk 701“ fragt nach Daten.
        return _erklaerung([_nachsehen(conn, c) for c in codes])
    code = v.code
    if code and len(code) > 1 and code not in _laengere_codes(conn):
        code = None  # „ÖNACE UND …“ oder „ÖNACE ROH …“ in Großbuchstaben: ein Wort, kein Code.
    if code:
        return _abschnitt_antwort(conn, v, code, fassungen)
    return _ueberblick_antwort(conn, v, fassungen)


# --- Datenbank ------------------------------------------------------------------------------------------------


def _wert(conn: Verbindung, wert: str) -> str:
    return sql.Literal(wert).as_string(conn)


def _fassungen_lesen(conn: Verbindung, v: Vergleich) -> dict[str, dict[str, Any]]:
    zeilen = _lesen(
        conn,
        "SELECT version, min(gueltig_von) AS gueltig_von, "
        "CASE WHEN bool_or(gueltig_bis IS NULL) THEN NULL ELSE max(gueltig_bis) END AS gueltig_bis "
        f"FROM stat.klass_oenace WHERE version IN ({_wert(conn, v.alt)}, {_wert(conn, v.neu)}) GROUP BY version",
    )
    return {str(z["version"]): z for z in zeilen}


def _laengere_codes(conn: Verbindung) -> set[str]:
    """Codes aus mehreren Buchstaben (UNB, DA). Fremde Wörter kommen so nie als Literal in eine Abfrage."""
    zeilen = _lesen(
        conn,
        "SELECT DISTINCT code FROM stat.klass_oenace WHERE length(code) > 1 AND code = upper(code) AND code !~ ' '",
    )
    return {str(z["code"]) for z in zeilen}


def _paar(conn: Verbindung, v: Vergleich, klassifikation: str) -> str:
    return (
        f"u.klassifikation = {_wert(conn, klassifikation)} AND u.version_alt = {_wert(conn, v.alt)} "
        f"AND u.version_neu = {_wert(conn, v.neu)}"
    )


def _aus_abschnitt(conn: Verbindung, code: str | None) -> str:
    return f" AND split_part(u.code_alt, ' ', 1) = {_wert(conn, code)}" if code else ""


def _wege_sql(conn: Verbindung, v: Vergleich, code: str) -> str:
    """Von welchem Abschnitt zu welchem führen wie viele Unterklassen, in beide Richtungen um ``code``."""
    return (
        "SELECT split_part(u.code_alt, ' ', 1) AS von, split_part(u.code_neu, ' ', 1) AS nach, "
        "count(DISTINCT u.code_alt) AS codes, count(DISTINCT u.code_neu) AS ziele, "
        f"(SELECT count(DISTINCT g.code_neu) FROM stat.uebergang g WHERE g.klassifikation = {_wert(conn, UNTERKLASSEN)} "
        f"AND g.version_alt = {_wert(conn, v.alt)} AND g.version_neu = {_wert(conn, v.neu)} "
        f"AND split_part(g.code_neu, ' ', 1) = {_wert(conn, code)}) AS ziele_gesamt, "
        "min(u.quelle) AS quelle FROM stat.uebergang u "
        f"WHERE {_paar(conn, v, UNTERKLASSEN)} AND (split_part(u.code_alt, ' ', 1) = {_wert(conn, code)} "
        f"OR split_part(u.code_neu, ' ', 1) = {_wert(conn, code)}) "
        "GROUP BY 1, 2 ORDER BY 3 DESC, 1, 2"
    )


def _abschnitts_wege_sql(conn: Verbindung, v: Vergleich, code: str) -> str:
    """Dieselbe Frage ohne Unterklassen: die Abschnittszeilen des Umsteigeschlüssels."""
    return (
        "SELECT u.code_alt AS von, u.code_neu AS nach, u.beziehung, u.quelle FROM stat.uebergang u "
        f"WHERE {_paar(conn, v, ABSCHNITTE)} AND (u.code_alt = {_wert(conn, code)} OR u.code_neu = {_wert(conn, code)}) "
        'ORDER BY u.code_alt COLLATE "C", u.code_neu COLLATE "C"'
    )


def _kinder_wege_sql(conn: Verbindung, v: Vergleich, code: str) -> str:
    """Die Abschnittszeilen der Ebene unter ``code``: ÖNACE 2003 D steht nur über DA bis DN im Schlüssel."""
    return (
        "SELECT u.code_alt AS von, u.code_neu AS nach, u.beziehung, u.quelle FROM stat.uebergang u "
        "JOIN stat.klass_oenace k ON k.version = u.version_alt AND k.code = u.code_alt "
        f"WHERE {_paar(conn, v, ABSCHNITTE)} AND k.uebergeordnet = {_wert(conn, code)} "
        'ORDER BY u.code_alt COLLATE "C", u.code_neu COLLATE "C"'
    )


def _zaehlung_sql(conn: Verbindung, v: Vergleich, code: str | None) -> str:
    """Wie viele Unterklassen führen auf genau einen Code und wie viele auf mehrere."""
    return (
        "SELECT count(*) AS codes, count(*) FILTER (WHERE z.ziele > 1) AS mehrdeutig FROM ("
        f"SELECT u.code_alt, count(*) AS ziele FROM stat.uebergang u WHERE {_paar(conn, v, UNTERKLASSEN)}"
        f"{_aus_abschnitt(conn, code)} GROUP BY u.code_alt) z"
    )


def _fall_sql(conn: Verbindung, v: Vergleich, code: str | None, nur_rein: bool) -> str:
    """Der erste Code mit mehreren Zielen und alle seine Ziele. ``nur_rein``: nur ein echter 1:n-Fall."""
    rein = " AND bool_and(u.beziehung = '1:n')" if nur_rein else ""
    return (
        "SELECT z.code_alt, z.code_neu, z.beziehung, z.quelle FROM stat.uebergang z "
        f"WHERE z.klassifikation = {_wert(conn, UNTERKLASSEN)} AND z.version_alt = {_wert(conn, v.alt)} "
        f"AND z.version_neu = {_wert(conn, v.neu)} AND z.code_alt = ("
        f"SELECT u.code_alt FROM stat.uebergang u WHERE {_paar(conn, v, UNTERKLASSEN)}{_aus_abschnitt(conn, code)} "
        f'GROUP BY u.code_alt HAVING count(*) > 1{rein} ORDER BY u.code_alt COLLATE "C" LIMIT 1) '
        'ORDER BY z.code_neu COLLATE "C"'
    )


def _fall_lesen(
    conn: Verbindung, v: Vergleich, code: str | None, zaehlung: dict[str, Any]
) -> tuple[list[dict[str, Any]], str | None]:
    """Ein Beispiel: zuerst ein echter 1:n-Fall, sonst irgendein Code mit mehreren Zielen."""
    if int(zaehlung["mehrdeutig"]) == 0:
        return [], None
    abfrage = _fall_sql(conn, v, code, nur_rein=True)
    fall = _lesen(conn, abfrage)
    if not fall:
        abfrage = _fall_sql(conn, v, code, nur_rein=False)
        fall = _lesen(conn, abfrage)
    return fall, abfrage


def _hat_umsteiger_sql(conn: Verbindung, v: Vergleich) -> str:
    return f"SELECT count(*) AS n FROM stat.uebergang u WHERE {_paar(conn, v, ABSCHNITTE)}"


def _hat_umsteiger(conn: Verbindung, v: Vergleich) -> bool:
    return int(_lesen(conn, _hat_umsteiger_sql(conn, v))[0]["n"]) > 0


def _umsteiger_beleg(sql_text: str, zeilen: list[dict[str, Any]], ref: str) -> dict[str, Any]:
    """Der Dateiname gehört in den Beleg, nicht in den Text."""
    dateien = sorted({_datei(z.get("quelle")) for z in zeilen} - {""})
    return _beleg(", ".join(["stat.uebergang", *dateien]), sql_text, ref)


def _datei(quelle: object) -> str:
    """Die Quelldatei aus ``stat.uebergang.quelle``, vor dem Doppelpunkt oder Komma."""
    treffer = re.match(r"[^\s:,]+", str(quelle or ""))
    return treffer.group(0) if treffer else ""


# --- Texte ----------------------------------------------------------------------------------------------------

QUELLE_SATZ = "Quelle: Umsteigeschlüssel von Statistik Austria."
_ABGELEITET = re.compile(r"Mehrheit|Sechssteller|6-Steller")
#: Die Abschnittszeilen 2003 → 2008 nennen nur das Ziel der Mehrheit, nicht jeden Weg.
QUELLE_ABGELEITET = "Quelle: abgeleitet aus dem Umsteigeschlüssel von Statistik Austria."


def _zeit(zeile: dict[str, Any]) -> str:
    von, bis = zeile["gueltig_von"], zeile["gueltig_bis"]
    return f"von {_monat(von)} bis {_monat(bis)}" if bis else f"ab {_monat(von)}"


def _gueltigkeit_satz(fassungen: dict[str, dict[str, Any]], kurz: bool = False) -> str:
    alt, neu = sorted(fassungen)
    bis = fassungen[alt]["gueltig_bis"]
    zeit_alt = f"bis {_monat(bis)}" if kurz and bis else _zeit(fassungen[alt])
    return f"Die Fassung {alt} gilt {zeit_alt}, die Fassung {neu} {_zeit(fassungen[neu])}."


def _aufzaehlung(teile: list[str], wort: str = "und") -> str:
    if len(teile) < 2:
        return "".join(teile)
    return f"{', '.join(teile[:-1])} {wort} {teile[-1]}"


def _anzahl(zahl: object, einzahl: str, mehrzahl: str) -> str:
    return f"{klass._deutsch(int(str(zahl)))} {einzahl if int(str(zahl)) == 1 else mehrzahl}"


def _mehrdeutig_saetze(
    zaehlung: dict[str, Any], fall: list[dict[str, Any]], neu: str, herkunft: str
) -> list[str]:
    """Wie viele Unterklassen auf einen oder mehrere Codes führen, und ein Beispiel ohne gewähltes Ziel."""
    codes, mehrdeutig = int(zaehlung["codes"]), int(zaehlung["mehrdeutig"])
    gesamt = _anzahl(codes, "Unterklasse", "Unterklassen")
    if mehrdeutig == 0:
        if codes == 1:
            return [f"Die einzige Unterklasse {herkunft} führt auf genau einen Code der Fassung {neu}."]
        return [f"Von den {gesamt} {herkunft} führt jede auf genau einen Code der Fassung {neu}."]
    eindeutig = codes - mehrdeutig
    verb = "führt" if eindeutig == 1 else "führen"
    if codes == 1:
        saetze = [f"Die einzige Unterklasse {herkunft} führt auf mehrere Codes der Fassung {neu}."]
    elif eindeutig == 0:
        saetze = [f"Alle {gesamt} {herkunft} führen auf mehrere Codes der Fassung {neu}."]
    else:
        saetze = [
            f"Von den {gesamt} {herkunft} {verb} {klass._deutsch(eindeutig)} auf genau einen "
            f"Code der Fassung {neu} und {klass._deutsch(mehrdeutig)} auf mehrere."
        ]
    if not fall:
        return saetze
    gezeigt = [str(z["code_neu"]) for z in fall[:HOECHSTENS]]
    weitere = len(fall) - len(gezeigt)
    if weitere:
        gezeigt.append(_anzahl(weitere, "weiterer Code", "weitere Codes"))
    diese = "diese eine" if mehrdeutig == 1 else f"diese {klass._deutsch(mehrdeutig)}"
    saetze.append(
        f"Für {diese} gibt es keine eindeutige Umcodierung: {fall[0]['code_alt']} kann "
        f"{_aufzaehlung(gezeigt, 'oder')} sein, das Programm wählt keinen aus."
    )
    return saetze


def _name_satz(code: str, zeilen: dict[str, dict[str, Any]], v: Vergleich) -> str:
    alt, neu = zeilen.get(v.alt), zeilen.get(v.neu)
    if alt and neu:
        if alt["bezeichnung"] == neu["bezeichnung"]:
            return f"ÖNACE {code} heißt in beiden Fassungen „{alt['bezeichnung']}“."
        return (
            f"ÖNACE {code} heißt je Fassung anders. Fassung {v.alt}: „{alt['bezeichnung']}“. "
            f"Fassung {v.neu}: „{neu['bezeichnung']}“."
        )
    version, zeile, fehlt = (v.alt, alt, v.neu) if alt else (v.neu, neu, v.alt)
    assert zeile is not None
    return (
        f"ÖNACE {code} gibt es nur in der Fassung {version}: „{zeile['bezeichnung']}“. "
        f"In den Listen der Fassung {fehlt} steht {'dieser Abschnitt' if len(code) == 1 else 'dieser Code'} nicht."
    )


def _hinaus(wege: list[dict[str, Any]], code: str) -> list[dict[str, Any]]:
    """Wege aus dem Abschnitt, der größte zuerst; bei Gleichstand bleibt der Abschnitt bei sich."""
    return sorted(
        (w for w in wege if w["von"] == code),
        key=lambda w: (-int(w["codes"]), w["nach"] != code, str(w["nach"])),
    )


def _hauptweg_saetze(wege: list[dict[str, Any]], code: str, v: Vergleich, gesamt: int) -> list[str]:
    """Führt das meiste aus dem Abschnitt woanders hin oder kommt von woanders, trägt der Buchstabe nicht."""
    hinaus = _hinaus(wege, code)
    if hinaus and hinaus[0]["nach"] == code:
        return []
    saetze = []
    if hinaus and int(hinaus[0]["codes"]) * 2 > gesamt:
        saetze.append(
            f"Der Buchstabe allein reicht hier nicht: Das meiste aus {code} steht in der Fassung {v.neu} "
            f"unter {hinaus[0]['nach']}."
        )
    elif hinaus:
        saetze.append(
            f"Der Buchstabe allein reicht hier nicht: {code} verteilt sich in der Fassung {v.neu} auf mehrere Abschnitte."
        )
    # Mehrere alte Codes können auf einen neuen führen: Das Gewicht zählt die neuen Codes, nicht die alten.
    herein = sorted(
        (w for w in wege if w["nach"] == code and w["von"] != code),
        key=lambda w: (-int(w["ziele"]), str(w["von"])),
    )
    if herein and int(herein[0]["ziele"]) * 2 > int(herein[0]["ziele_gesamt"]):
        saetze.append(f"Das meiste in {code} (Fassung {v.neu}) kommt aus {herein[0]['von']}.")
    elif herein:
        namen = _aufzaehlung([str(w["von"]) for w in herein])
        saetze.append(f"Nach {code} (Fassung {v.neu}) kommen Teile aus {namen}.")
    return saetze


def _wechsel_saetze(wege: list[dict[str, Any]], code: str, gesamt: int) -> list[str]:
    """Nur wenn der Abschnitt im Wesentlichen bleibt: wer Teile abgibt und aufnimmt."""
    hinaus = _hinaus(wege, code)
    if not hinaus or hinaus[0]["nach"] != code:
        return []
    weg = [w for w in hinaus if w["nach"] != code]
    her = [w for w in wege if w["nach"] == code and w["von"] != code]
    if not weg and not her:
        return []
    bewegt = sum(int(w["codes"]) for w in [*weg, *her])
    if bewegt == 1:
        anfang = "Eine Unterklasse wechselt den Abschnitt"
    else:
        anfang = f"{'Einzelne' if bewegt * 10 <= gesamt else 'Manche'} Unterklassen wechseln den Abschnitt"
    teile = []
    if weg:
        teile.append(f"Teile gehen nach {_aufzaehlung([str(w['nach']) for w in weg])}")
    if her:
        teile.append(f"Teile kommen aus {_aufzaehlung([str(w['von']) for w in her])}")
    return [f"{anfang}: {', '.join(teile)}."]


def _abschnitts_wege_saetze(wege: list[dict[str, Any]], code: str, v: Vergleich) -> list[str]:
    """Ohne Unterklassen: nur was die Abschnittszeilen hergeben, ohne Anzahl und ohne Einzelfall."""
    hinaus = [str(w["nach"]) for w in wege if w["von"] == code]
    herein = [str(w["von"]) for w in wege if w["nach"] == code]
    vor_allem = "vor allem " if _nur_mehrheit(wege) else ""
    saetze = []
    if hinaus:
        saetze.append(f"{code} (Fassung {v.alt}) führt {vor_allem}nach {_kurzliste(hinaus)}.")
    if herein:
        verb = "führt" if len(herein) == 1 else "führen"
        saetze.append(f"Nach {code} (Fassung {v.neu}) {verb} {vor_allem}{_kurzliste(herein)}.")
    if len(hinaus) > 1:
        saetze.append(f"Für {code} gibt es also keine eindeutige Umcodierung.")
    saetze.append(
        "Die Liste je Unterklasse ist für diese Fassungen nicht dabei, darum folgt hier kein Einzelfall."
    )
    return saetze


def _nur_mehrheit(wege: list[dict[str, Any]]) -> bool:
    """Die Zeilen sind aus den 6-Stellern abgeleitet (Mehrheit oder „6 von 32 Sechsstellern“), nicht der ganze Weg.

    Das steht nur in ``quelle``, nicht in einer eigenen Spalte (uc3/db/100_klass_daten.sql)."""
    return any(_ABGELEITET.search(str(w.get("quelle") or "")) for w in wege)


def _quelle_abschnitte(wege: list[dict[str, Any]]) -> str:
    return QUELLE_ABGELEITET if _nur_mehrheit(wege) else QUELLE_SATZ


def _kinder_satz(kinder: list[dict[str, Any]], code: str) -> str:
    """Der Schlüssel nennt nur die Ebene darunter: „D steht im Schlüssel über seine Unterabschnitte DA bis DN …“."""
    codes = sorted({str(w["von"]) for w in kinder})
    je_ziel: dict[str, list[str]] = {}
    for w in kinder:
        je_ziel.setdefault(str(w["nach"]), []).append(str(w["von"]))
    haupt = sorted(je_ziel, key=lambda ziel: (-len(je_ziel[ziel]), ziel))[0]
    teile = [f"{'vor allem ' if _nur_mehrheit(kinder) else ''}nach {haupt}"]
    for ziel in sorted(je_ziel):
        if ziel != haupt:
            teile += [f"{k} {'auch ' if k in je_ziel[haupt] else ''}nach {ziel}" for k in je_ziel[ziel]]
    spanne = f"{codes[0]} bis {codes[-1]}" if len(codes) > 2 else _aufzaehlung(codes)
    ebene = klass.ebene_name(2, codes[0], mehrzahl=True) if len(codes) > 1 else klass.ebene_name(2, codes[0])
    verb = "führen" if len(codes) > 1 else "führt"
    pronomen = "sie" if len(codes) > 1 else "er"
    return f"{code} steht im Schlüssel über {'seine' if len(codes) > 1 else 'seinen'} {ebene} {spanne}, {pronomen} {verb} {', '.join(teile)}."


def _kurzliste(teile: list[str]) -> str:
    gezeigt = teile[:HOECHSTENS]
    weitere = len(teile) - len(gezeigt)
    if weitere:
        gezeigt = [*gezeigt, _anzahl(weitere, "weiterer", "weitere")]
    return _aufzaehlung(gezeigt)


def _kein_umsteiger(v: Vergleich) -> str:
    return f"Ein direkter Umsteigeschlüssel zwischen den Fassungen {v.alt} und {v.neu} liegt hier nicht vor."


def _abschnitt_antwort(
    conn: Verbindung, v: Vergleich, code: str, fassungen: dict[str, dict[str, Any]]
) -> dict[str, Any]:
    namen_sql = (
        "SELECT version, code, bezeichnung, gueltig_von, gueltig_bis FROM stat.klass_oenace "
        f"WHERE code = {_wert(conn, code)} AND version IN ({_wert(conn, v.alt)}, {_wert(conn, v.neu)}) ORDER BY version"
    )
    namen = {str(z["version"]): z for z in _lesen(conn, namen_sql)}
    ref = f"stat.klass_oenace/{code}"
    belege = [_beleg("stat.klass_oenace", namen_sql, ref)]
    if not namen:
        satz = f"Einen Abschnitt {code} gibt es in den Fassungen {v.alt} und {v.neu} nicht."
        return _antwort("definition", satz, hinweise=[satz], belege=belege)
    saetze = [_name_satz(code, namen, v), _gueltigkeit_satz(fassungen, kurz=True)]
    wege_sql = _wege_sql(conn, v, code)
    wege = _lesen(conn, wege_sql)
    if wege:
        zaehlung_sql = _zaehlung_sql(conn, v, code)
        zaehlung = _lesen(conn, zaehlung_sql)[0]
        fall, fall_sql = _fall_lesen(conn, v, code, zaehlung)
        saetze += _hauptweg_saetze(wege, code, v, int(zaehlung["codes"]))
        if int(zaehlung["codes"]) > 0:
            saetze += _mehrdeutig_saetze(zaehlung, fall, v.neu, f"aus {code}")
        saetze += _wechsel_saetze(wege, code, int(zaehlung["codes"]))
        saetze.append(QUELLE_SATZ)
        umsteiger = f"stat.uebergang/{UNTERKLASSEN}/{code}"
        belege += [
            _umsteiger_beleg(wege_sql, wege, umsteiger),
            _umsteiger_beleg(zaehlung_sql, wege, umsteiger),
        ]
        if fall_sql and fall:
            belege.append(_umsteiger_beleg(fall_sql, fall, f"{umsteiger}/{fall[0]['code_alt']}"))
    else:
        abschnitts_sql = _abschnitts_wege_sql(conn, v, code)
        abschnitts_wege = _lesen(conn, abschnitts_sql)
        if abschnitts_wege:
            saetze += _abschnitts_wege_saetze(abschnitts_wege, code, v)
            saetze.append(_quelle_abschnitte(abschnitts_wege))
            belege.append(
                _umsteiger_beleg(abschnitts_sql, abschnitts_wege, f"stat.uebergang/{ABSCHNITTE}/{code}")
            )
        else:
            # Die leere Abfrage ist der Beleg der Aussage, dazu die Zählung, ob es den Schlüssel überhaupt gibt.
            belege.append(_beleg("stat.uebergang", abschnitts_sql, f"stat.uebergang/{ABSCHNITTE}/{code}"))
            kinder_sql = _kinder_wege_sql(conn, v, code)
            kinder = _lesen(conn, kinder_sql)
            if kinder:
                saetze += [_kinder_satz(kinder, code), _quelle_abschnitte(kinder)]
                belege.append(_umsteiger_beleg(kinder_sql, kinder, f"stat.uebergang/{ABSCHNITTE}/{code}"))
            else:
                belege.append(
                    _beleg("stat.uebergang", _hat_umsteiger_sql(conn, v), f"stat.uebergang/{ABSCHNITTE}")
                )
                saetze.append(
                    f"Der Umsteigeschlüssel zwischen den Fassungen {v.alt} und {v.neu} nennt {code} nicht."
                    if _hat_umsteiger(conn, v)
                    else _kein_umsteiger(v)
                )
    return _antwort(
        "definition",
        " ".join(saetze),
        definition="; ".join(f"ÖNACE {version} {code}: {z['bezeichnung']}" for version, z in namen.items()),
        stand=[{"klassifikation": "stat.klass_oenace", "version": version} for version in namen],
        belege=belege,
    )


def _ueberblick_antwort(
    conn: Verbindung, v: Vergleich, fassungen: dict[str, dict[str, Any]]
) -> dict[str, Any]:
    """Ohne Abschnitt: Zahl der Abschnitte, gleich gebliebene Namen und der Umsteigeschlüssel im Ganzen."""
    abschnitte_sql = (
        "SELECT version, count(*) AS abschnitte FROM stat.klass_oenace "
        f"WHERE ebene = 1 AND length(code) = 1 AND version IN ({_wert(conn, v.alt)}, {_wert(conn, v.neu)}) "
        "GROUP BY version ORDER BY version"
    )
    abschnitte = {str(z["version"]): int(z["abschnitte"]) for z in _lesen(conn, abschnitte_sql)}
    namen_sql = (
        "SELECT count(*) FILTER (WHERE a.bezeichnung = n.bezeichnung) AS gleich, "
        "count(*) FILTER (WHERE a.bezeichnung <> n.bezeichnung) AS anders FROM stat.klass_oenace a "
        "JOIN stat.klass_oenace n ON n.code = a.code "
        f"WHERE a.ebene = 1 AND length(a.code) = 1 AND a.version = {_wert(conn, v.alt)} "
        f"AND n.version = {_wert(conn, v.neu)}"
    )
    namen = _lesen(conn, namen_sql)[0]
    saetze = [_gueltigkeit_satz(fassungen)]
    # Von der Fassung 2003 liegt nur ein Teil vor (D und seine Unterabschnitte): Dann sagt die Zahl nichts.
    vollstaendig = len(abschnitte) == 2 and min(abschnitte.values()) > 1
    if vollstaendig:
        saetze.append(
            f"Die Fassung {v.alt} hat {_anzahl(abschnitte.get(v.alt, 0), 'Abschnitt', 'Abschnitte')}, "
            f"die Fassung {v.neu} {_anzahl(abschnitte.get(v.neu, 0), 'Abschnitt', 'Abschnitte')}."
        )
    if vollstaendig and int(namen["anders"]) > 0:
        saetze.append(
            f"Bei {klass._deutsch(int(namen['gleich']))} Buchstaben bleibt der Name gleich, bei "
            f"{klass._deutsch(int(namen['anders']))} Buchstaben ändert er sich. "
            "Derselbe Buchstabe meint also nicht immer dasselbe."
        )
    belege = [
        _beleg("stat.klass_oenace", abschnitte_sql, "stat.klass_oenace"),
        _beleg("stat.klass_oenace", namen_sql, "stat.klass_oenace"),
    ]
    zaehlung_sql = _zaehlung_sql(conn, v, None)
    zaehlung = _lesen(conn, zaehlung_sql)[0]
    if int(zaehlung["codes"]) > 0:
        fall, fall_sql = _fall_lesen(conn, v, None, zaehlung)
        saetze += _mehrdeutig_saetze(zaehlung, fall, v.neu, f"der Fassung {v.alt}")
        saetze.append(QUELLE_SATZ)
        umsteiger = f"stat.uebergang/{UNTERKLASSEN}"
        belege.append(_umsteiger_beleg(zaehlung_sql, fall, umsteiger))
        if fall_sql and fall:
            belege.append(_umsteiger_beleg(fall_sql, fall, f"{umsteiger}/{fall[0]['code_alt']}"))
    else:
        belege.append(_beleg("stat.uebergang", _hat_umsteiger_sql(conn, v), f"stat.uebergang/{ABSCHNITTE}"))
        saetze.append(
            "Die Liste je Unterklasse ist für diese Fassungen nicht dabei."
            if _hat_umsteiger(conn, v)
            else _kein_umsteiger(v)
        )
    saetze.append(f"Zu einem einzelnen Abschnitt fragen Sie zum Beispiel: „{_ABSCHNITT_BEISPIEL}“.")
    return _antwort(
        "definition",
        " ".join(saetze),
        definition=f"ÖNACE {v.alt} und ÖNACE {v.neu}",
        stand=[{"klassifikation": "stat.klass_oenace", "version": version} for version in sorted(fassungen)],
        belege=belege,
    )
