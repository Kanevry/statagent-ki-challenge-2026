"""Vom Satz zum Vorschlag: Koordinator wählt die Rolle, die Rolle schlägt vor, das Programm prüft.

Ablauf von ``agent_ausfuehren``:

1. Koordinator (ein Modellaufruf, Zweck ``agent.koordinator``) ordnet die Anweisung einer Rolle zu oder
   stellt eine Rückfrage.
2. Die Lese-Werkzeuge stellen einen Kontext zusammen (Regeln, Schema, Klassifikation, Aggregate, nie
   Einzeldaten). Die Rolle antwortet in einem Modellaufruf mit dem Format ``VorschlagAntwort``. Bewusst
   ohne Werkzeug-Schleife: ein fester Kontext ist nachvollziehbar und läuft mit jedem Modell, auch mock.
3. Der Code prüft den Vorschlag gegen die Datenbank (Regel vorhanden, Parameter bekannt, Wert zulässig
   für die Regel-Art, keine Kennungen). Erst dann entsteht ein offener Vorschlag in meta.vorschlag.

Keine Zahl entsteht im Modell. Die Probe (``probe_rechnen``) rechnet das Programm.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any

from pydantic import BaseModel, ValidationError

from statagent.agenten import plattform_bruecke
from statagent.agenten.anwenden import CodeUngueltig, code_pruefen
from statagent.agenten.plattform_bruecke import CompleteFunktion
from statagent.agenten.regelaenderung import regelsatz_vorhanden
from statagent.agenten.rollen import (
    KOORDINATOR_ZWECK,
    ROLLEN,
    Koordination,
    Parameter,
    Rolle,
    VorschlagAntwort,
    koordinator_prompt,
)
from statagent.agenten.vorschlag import CodeDateiEntwurf, probe_rechnen, vorschlag_anlegen
from statagent.agenten.werkzeuge import (
    GESPERRTE_SPALTEN,
    AbfrageVerweigert,
    klassifikation_lesen,
    regeln_lesen,
    roh_kennzahlen,
    schema_lesen,
    sql_lesen,
)
from statagent.db import Verbindung
from statagent.sonderauswertung import PERSONENTAGE_PARAMETER


class VorschlagUngueltig(ValueError):
    """Der Vorschlag des Modells passt nicht zu den Regeln in der Datenbank."""


@dataclass
class Ergebnis:
    """Was aus einer Anweisung wurde: ein offener Vorschlag, eine Rückfrage oder eine begründete Ablehnung."""

    anweisung: str
    rolle: str | None = None
    vorschlag_id: int | None = None
    rueckfrage: str | None = None
    abgelehnt: str | None = None
    modell: str | None = None
    provider: str | None = None
    aufrufe: list[dict[str, str | None]] = field(default_factory=list)


# --- Zulässige Werte je Regel-Art (was der Zählcode versteht; Werte selbst stehen in meta.regel) -------

_TAG = re.compile(r"^(monatserster|monatsletzter|tag:\d{1,2})$")
#: ``geburtsmonat_13``, wie zaehlung.py es versteht: jahresdifferenz, unbekannt oder ``ersatz:MM-TT``. Das
#: Ersatzdatum geht dort in ``make_date(geburtsjahr, MM, TT)``; zulässig ist darum nur ein Tag, den es in
#: jedem Jahr gibt (kein 29.02., kein 31. in Monaten mit 30 Tagen).
_GEBURTSMONAT_13 = re.compile(
    r"^(jahresdifferenz|unbekannt"
    r"|ersatz:(?:(?:0[1-9]|1[0-2])-(?:0[1-9]|1\d|2[0-8])|(?:0[13-9]|1[0-2])-(?:29|30)|(?:0[13578]|1[02])-31))$"
)
_ZULAESSIG: dict[tuple[str, str], Any] = {
    ("dimension", "qualifikation"): {"code", "beschaeftigungskategorie"},
    ("bestand", "zeitraum_art"): {"Stichtag", "Monat"},
    ("bestand", "von"): _TAG,
    ("bestand", "bis"): _TAG,
    ("bestand", "lieferung"): {"eigene"},
    ("abschnittswahl", "ordnung"): {"spaetester_beginn"},
    ("alter", "bezug"): {"bis", "von"},
    ("alter", "geburtsmonat_13"): _GEBURTSMONAT_13,
    ("klassifikationsversion", "nach"): {"berichtsmonat"},
    # sonderauswertung.personentage verweigert jeden anderen Wert
    ("personentage", "datenstand"): {"juengste_lieferung_je_tag"},
    ("personentage", "angehaltene_lieferungen"): {"ueberspringen", "verwenden"},
}

#: Zählregel-Arten eines Auswertungs-Regelsatzes und die Parameter, die der Auswertungscode liest
#: (``wert(regel, …)`` in sonderauswertung.py; dort gibt es keine eigene Liste). Nur was der Code kann.
_AUSWERTUNG_PARAMETER: dict[str, frozenset[str]] = {"personentage": PERSONENTAGE_PARAMETER}
#: Was eine Rolle über die Parameter einer neuen Auswertungsregel wissen muss (Kontext ``neue_regel_arten``);
#: ohne diese Liste riet das Modell die Namen (Live-Probe Auftrag 3, 05.11.). Werte stehen hier keine.
_AUSWERTUNG_PARAMETER_TEXT: dict[str, dict[str, str]] = {
    "personentage": {
        "monate": "Zahl: Monate bis einschließlich Berichtsmonat",
        "qualifikationen": "Liste der Qualifikationscodes, z. B. ArbeiterDV",
        "oenace": "ÖNACE-Abschnitt als Buchstabe",
        "altcodes_als_abschnitt": "Liste alter ÖNACE-2003-Codes, die zu diesem Abschnitt zählen",
        "mindesttage": "Zahl: kleinste Zahl von Tagen für die Liste",
        "datenstand": "juengste_lieferung_je_tag",
        "angehaltene_lieferungen": "ueberspringen oder verwenden",
        "bereinigung_regelsatz": "Regelsatz, nach dem die Lieferungen bereinigt sind, z. B. v1",
        "geburtsjahr_unplausibel": "Text für ein unplausibles Geburtsjahr",
        "felder": "Liste der Spalten der Datei",
        "datei": "Dateiname mit dem Platzhalter {berichtsmonat}",
        "trennzeichen": "Trennzeichen der CSV",
    }
}
assert all(set(t) == _AUSWERTUNG_PARAMETER[a] for a, t in _AUSWERTUNG_PARAMETER_TEXT.items())
_V_REGELSATZ = re.compile(r"v\d+")
#: Auswertungs-Regelsatz (z. B. ``ministerium``): eigene Regeln, keine Monatsläufe. Wie der CHECK in 140_vorschlag.sql.
_AUSWERTUNG_REGELSATZ = re.compile(r"[a-z][a-z0-9_]{2,40}")


def _gleicher_typ(alt: object, neu: object) -> bool:
    if isinstance(alt, bool) or isinstance(neu, bool):
        return isinstance(alt, bool) and isinstance(neu, bool)
    if isinstance(alt, int | float):
        return isinstance(neu, int | float)
    return type(alt) is type(neu)


def _wert_pruefen(art: str, schluessel: str, alt: object, neu: object, regel: str) -> None:
    erlaubt = _ZULAESSIG.get((art, schluessel))
    if isinstance(erlaubt, set) and neu not in erlaubt:
        werte = ", ".join(sorted(erlaubt))
        raise VorschlagUngueltig(
            f"{regel}.{schluessel}: {neu!r} ist für die Art {art} nicht zulässig ({werte})"
        )
    if isinstance(erlaubt, re.Pattern) and not (isinstance(neu, str) and erlaubt.match(neu)):
        raise VorschlagUngueltig(f"{regel}.{schluessel}: {neu!r} passt nicht zu {erlaubt.pattern}")
    if alt is not None and not _gleicher_typ(alt, neu):
        raise VorschlagUngueltig(f"{regel}.{schluessel}: Wert {neu!r} hat einen anderen Typ als bisher")


_REGEL_TEXTE = frozenset({"beschreibung", "begruendung", "grundlage", "name"})


def _parameter(liste: list[Parameter]) -> dict[str, Any]:
    ergebnis: dict[str, Any] = {}
    for p in liste:
        if p.schluessel in ergebnis:
            raise VorschlagUngueltig(f"Parameter {p.schluessel} kommt doppelt vor")
        ergebnis[p.schluessel] = p.wert
    return ergebnis


def _regeln(conn: Verbindung, regelsatz: str) -> dict[str, dict[str, Any]]:
    zeilen = conn.execute(
        "SELECT name, typ, art, parameter FROM meta.regel WHERE regelsatz = %s AND aktiv", (regelsatz,)
    ).fetchall()
    return {str(z["name"]): dict(z) for z in zeilen}


def _ziel_pruefen(conn: Verbindung, ziel: str) -> bool:
    """Prüft das Ziel. True = Auswertungs-Regelsatz (eigene Regeln), False = Zählregelsatz v<Zahl>."""
    if _V_REGELSATZ.fullmatch(ziel):
        z = conn.execute(
            "SELECT count(*) AS n FROM meta.lauf WHERE regelsatz = %s AND ergebnis_status = 'endgueltig'",
            (ziel,),
        ).fetchone()
        if z is not None and int(str(z["n"])) > 0:
            raise VorschlagUngueltig(
                f"Regelsatz {ziel} hat veröffentlichte Monate; die bleiben unverändert. Bitte einen neuen Regelsatz."
            )
        return False
    if not _AUSWERTUNG_REGELSATZ.fullmatch(ziel):
        raise VorschlagUngueltig(
            f"Regelsatz {ziel!r} hat weder die Form v<Zahl> noch die eines Auswertungs-Regelsatzes "
            "(a-z, dann 2 bis 40 Zeichen aus a-z, 0-9, _)"
        )
    # Keine Monatsläufe: geschützt ist hier, was schon freigegeben ist.
    z = conn.execute(
        """SELECT count(*) AS n FROM meta.regel
           WHERE regelsatz = %s AND aktiv AND freigegeben_von IS NOT NULL""",
        (ziel,),
    ).fetchone()
    if z is not None and int(str(z["n"])) > 0:
        raise VorschlagUngueltig(
            f"Auswertungs-Regelsatz {ziel} hat freigegebene Regeln; die ändern sich nicht ohne neue Freigabe. "
            "Bitte einen neuen Auswertungs-Regelsatz."
        )
    return True


def _art_unbekannt(typ: str, art: str, arten: list[str]) -> VorschlagUngueltig:
    return VorschlagUngueltig(
        f"Eine {typ}-Regel der Art {art!r} kennt das Programm nicht (vorhanden: "
        f"{', '.join(arten)}). Eine neue Art braucht neuen Code im Programm; das ist ein "
        "Entwicklungsauftrag, kein Regelvorschlag."
    )


def _auswertung_parameter_pruefen(conn: Verbindung, name: str, art: str, parameter: dict[str, Any]) -> None:
    """Parameter einer neuen Auswertungsregel: vollständig, wie der Auswertungscode sie liest."""
    erwartet = _AUSWERTUNG_PARAMETER[art]
    fehlt, unbekannt = sorted(erwartet - set(parameter)), sorted(set(parameter) - erwartet)
    if fehlt:
        raise VorschlagUngueltig(f"{name}: der Art {art} fehlen die Parameter {', '.join(fehlt)}")
    if unbekannt:
        raise VorschlagUngueltig(f"{name}: Parameter {', '.join(unbekannt)} kennt die Art {art} nicht")
    rs = parameter["bereinigung_regelsatz"]
    if not (isinstance(rs, str) and _V_REGELSATZ.fullmatch(rs) and regelsatz_vorhanden(conn, rs)):
        raise VorschlagUngueltig(f"{name}.bereinigung_regelsatz: Regelsatz {rs!r} gibt es nicht")
    for k, kleinster in (("monate", 1), ("mindesttage", 0)):
        w = parameter[k]
        if isinstance(w, bool) or not isinstance(w, int) or w < kleinster:
            raise VorschlagUngueltig(f"{name}.{k}: ganze Zahl ab {kleinster} erwartet, nicht {w!r}")
    for k in ("qualifikationen", "felder"):
        if not (isinstance(parameter[k], list) and parameter[k]):
            raise VorschlagUngueltig(f"{name}.{k}: nicht leere Liste erwartet")
    altcodes = parameter["altcodes_als_abschnitt"]
    if not (isinstance(altcodes, list) and all(isinstance(c, str) and c for c in altcodes)):
        raise VorschlagUngueltig(f"{name}.altcodes_als_abschnitt: Liste von Codes erwartet (leer = keine)")
    listen = {"monate", "mindesttage", "qualifikationen", "felder", "altcodes_als_abschnitt"}
    for k in sorted(erwartet - listen):
        if not isinstance(parameter[k], str):
            raise VorschlagUngueltig(f"{name}.{k}: Text erwartet, nicht {parameter[k]!r}")


def _ohne_auswertungsfelder(aenderungen: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """``felder`` einer neuen Auswertungsregel nennt Spalten der Lieferung (Auftrag 3 verlangt PERSON_ID), keine
    Werte; für die Kennungsprüfung bleiben sie außen vor."""
    ergebnis: list[dict[str, Any]] = []
    for a in aenderungen:
        regel = a.get("regel")
        if isinstance(regel, dict) and regel.get("art") in _AUSWERTUNG_PARAMETER:
            parameter = {k: w for k, w in dict(regel["parameter"]).items() if k != "felder"}
            a = {**a, "regel": {**regel, "parameter": parameter}}
        ergebnis.append(a)
    return ergebnis


#: Kennungsspalten (person_id, vvh_id) als ganzes Wort, Groß/Klein egal. Ohne „beispiele“ aus
#: GESPERRTE_SPALTEN: eine Begründung „… mit Beispielen …“ nennt keine Einzeldaten.
_KENNUNGSWORT = re.compile(
    r"\b(" + "|".join(sorted(GESPERRTE_SPALTEN - {"beispiele"})) + r")\b", re.IGNORECASE
)


_TEXTFELDER = ("beschreibung", "begruendung")


def _ohne_kennungen(aenderungen: list[dict[str, Any]], begruendung: str, rumpf: str | None) -> None:
    """Code und Parameter nennen keine Kennungsspalte; Fließtext nennt keine konkrete Kennung mit Nummer.

    Der Fließtext (Begründung, Beschreibung einer neuen Regel) darf den Feldnamen nennen, den ein Auftrag verlangt
    („Felder PERSON_ID, GESCHLECHT …“ in Auftrag 3, Live-Probe 05.11.), aber keine Kennung wie „PERSON_ID 1001049“.
    """
    texte: list[object] = [begruendung]
    ohne_texte: list[dict[str, Any]] = []
    for a in aenderungen:
        regel = a.get("regel")
        if isinstance(regel, dict):
            texte += [regel.get(k) for k in _TEXTFELDER]
            a = {**a, "regel": {k: w for k, w in regel.items() if k not in _TEXTFELDER}}
        ohne_texte.append(a)
    if treffer := _KENNUNGSWORT.search(json.dumps([ohne_texte, rumpf], ensure_ascii=False, default=str)):
        raise VorschlagUngueltig(
            f"Der Vorschlag nennt „{treffer.group(1).lower()}“; Einzeldaten gehören nicht in Vorschläge."
        )
    if _KENNUNG_IN_ANWEISUNG.search(json.dumps(texte, ensure_ascii=False, default=str)):
        raise VorschlagUngueltig(
            "Der Vorschlag nennt eine konkrete Kennung; Einzeldaten gehören nicht in Vorschläge."
        )


#: Konkrete Kennung in einer Anweisung: Kennungswort, optional ``_ID``/``-ID``/``Nr.``, optional ``:``/``=``/``#``,
#: dann eine Zahl ab zwei Stellen („VVH_ID 859975“, „PERSON_ID: 1001049“, „Person 1001049“, „Verhältnis 12345“).
#: Zahlen ohne Kennungswort (Jahre, Monate wie 2025-03, Grenzen wie 110 oder 200 Tage) bleiben erlaubt.
_KENNUNG_IN_ANWEISUNG = re.compile(
    r"\b(?:vvh|person|\w*verh(?:ä|ae)ltnis(?:ses)?|id)(?:[_-]?id)?\s*(?:nr\.?|nummer)?\s*[:=#]?\s*#?\d{2,}\b",
    re.IGNORECASE,
)


def anweisung_pruefen(anweisung: str) -> str | None:
    """Grund für die Ablehnung, wenn die Anweisung eine konkrete Kennung nennt, sonst None.

    Läuft vor dem ersten Modellaufruf: eine solche Anweisung erreicht weder Modell noch Protokoll. Der Grund
    nennt die Kennung nicht.
    """
    if _KENNUNG_IN_ANWEISUNG.search(anweisung):
        return (
            "Die Anweisung enthält eine Kennung (etwa VVH_ID, PERSON_ID oder die Nummer einer Person oder "
            "eines Verhältnisses); sie geht nicht an das Modell und nicht ins Protokoll. Bitte ohne "
            "Einzeldaten formulieren."
        )
    return None


@dataclass(frozen=True)
class GeprueftVorschlag:
    typ: str
    regelsatz_ziel: str
    regelsatz_basis: str
    aenderungen: list[dict[str, Any]]
    datei: CodeDateiEntwurf | None
    begruendung: str


def vorschlag_pruefen(
    conn: Verbindung, rolle: Rolle, antwort: VorschlagAntwort, *, regelsatz_basis: str = "v1"
) -> GeprueftVorschlag:
    """Prüft den Modellvorschlag gegen die Datenbank. Werte vorher liest der Code selbst, nie das Modell."""
    if antwort.typ is None:
        raise VorschlagUngueltig("Die Antwort enthält weder Vorschlag noch Rückfrage")
    if antwort.typ not in rolle.typen:
        raise VorschlagUngueltig(f"Die Rolle {rolle.name} darf keine Vorschläge vom Typ {antwort.typ} machen")
    if not antwort.begruendung.strip():
        raise VorschlagUngueltig("Ein Vorschlag braucht eine Begründung")
    ziel = antwort.regelsatz_ziel
    auswertung = _ziel_pruefen(conn, ziel)
    if auswertung:
        # Ein Auswertungs-Regelsatz trägt nur eigene Regeln; Basis = Ziel, damit einspielen nichts kopiert.
        basis = ziel
    else:
        basis = ziel if regelsatz_vorhanden(conn, ziel) else regelsatz_basis
        if not regelsatz_vorhanden(conn, basis):
            raise VorschlagUngueltig(f"Basisregelsatz {basis} gibt es nicht")
    regeln = _regeln(conn, basis)
    aenderungen: list[dict[str, Any]] = []
    datei: CodeDateiEntwurf | None = None

    if antwort.typ == "regel_aendern":
        if not antwort.aenderungen:
            raise VorschlagUngueltig("regel_aendern ohne Änderung")
        for a in antwort.aenderungen:
            r = regeln.get(a.regel_name)
            if r is None:
                raise VorschlagUngueltig(f"Regel {a.regel_name} gibt es im Regelsatz {basis} nicht")
            if r["typ"] not in rolle.regeltypen:
                raise VorschlagUngueltig(f"Die Rolle {rolle.name} darf {r['typ']}-Regeln nicht ändern")
            alt = dict(r["parameter"])
            # Das Modell legt seinen Erklärtext manchmal als Parameter `beschreibung` ab (Live-Probe Auftrag 2,
            # 05.11.); Text der Regel ist kein Parameter und ändert keine Zahl, also verwerfen statt ablehnen.
            neu_teil = {
                k: w for k, w in _parameter(a.parameter_neu).items() if k in alt or k not in _REGEL_TEXTE
            }
            for k, w in neu_teil.items():
                if k not in alt:
                    raise VorschlagUngueltig(f"{a.regel_name}: Parameter {k!r} kennt die Regel nicht")
                _wert_pruefen(str(r["art"]), k, alt[k], w, a.regel_name)
            neu = {**alt, **neu_teil}
            if neu == alt:
                raise VorschlagUngueltig(f"{a.regel_name}: der Vorschlag ändert nichts")
            aenderungen.append({"regel_name": a.regel_name, "parameter_alt": alt, "parameter_neu": neu})
    elif antwort.typ == "regel_neu":
        if not antwort.neue_regeln:
            raise VorschlagUngueltig("regel_neu ohne Regel")
        for n in antwort.neue_regeln:
            if n.name in regeln:
                raise VorschlagUngueltig(f"Regel {n.name} gibt es schon; bitte regel_aendern")
            if n.typ not in rolle.regeltypen:
                raise VorschlagUngueltig(f"Die Rolle {rolle.name} darf keine {n.typ}-Regeln anlegen")
            gleiche_art = [r for r in regeln.values() if r["typ"] == n.typ and r["art"] == n.art]
            parameter = _parameter(n.parameter)
            if n.typ == "zaehl" and gleiche_art:
                raise VorschlagUngueltig(
                    f"Zählregeln gibt es je Art und Regelsatz genau einmal; {basis} hat schon "
                    f"{gleiche_art[0]['name']}. Bitte diese ändern"
                )
            if n.typ == "zaehl" and auswertung:
                # Im Auswertungs-Regelsatz nur Arten, die der Auswertungscode rechnet.
                if n.art not in _AUSWERTUNG_PARAMETER:
                    raise _art_unbekannt(n.typ, n.art, sorted(_AUSWERTUNG_PARAMETER))
                _auswertung_parameter_pruefen(conn, n.name, n.art, parameter)
            else:
                if not gleiche_art:
                    arten = sorted({str(r["art"]) for r in regeln.values() if r["typ"] == n.typ})
                    raise _art_unbekannt(n.typ, n.art, arten)
                bekannt = set().union(*(set(dict(r["parameter"])) for r in gleiche_art))
                unbekannt = sorted(set(parameter) - bekannt)
                if unbekannt:
                    raise VorschlagUngueltig(
                        f"{n.name}: Parameter {', '.join(unbekannt)} kennt die Art {n.art} nicht"
                    )
            for k, w in parameter.items():
                _wert_pruefen(n.art, k, None, w, n.name)
            regel = n.model_dump(exclude={"parameter"}) | {"parameter": parameter}
            aenderungen.append({"regel": regel})
    else:
        d = antwort.datei
        if d is None:
            raise VorschlagUngueltig("code_datei ohne Datei")
        if not re.fullmatch(r"[a-z0-9_]{1,60}", d.name):
            raise VorschlagUngueltig("Dateiname nur aus a-z, 0-9 und _ (höchstens 60 Zeichen)")
        endung = ".py" if d.sprache == "python" else ".sql"
        try:
            code_pruefen(endung, d.inhalt)
        except (CodeUngueltig, AbfrageVerweigert) as fehler:
            raise VorschlagUngueltig(f"Code-Datei: {fehler}") from None
        datei = CodeDateiEntwurf(name=d.name, endung=endung, rumpf=d.inhalt)

    _ohne_kennungen(
        _ohne_auswertungsfelder(aenderungen), antwort.begruendung, None if datei is None else datei.rumpf
    )
    return GeprueftVorschlag(antwort.typ, ziel, basis, aenderungen, datei, antwort.begruendung.strip())


# --- Modellaufrufe ------------------------------------------------------------------------------------


def _antwort_lesen[M: BaseModel](antwort: Any, format_: type[M]) -> M:
    roh = getattr(antwort, "json", None)
    if isinstance(roh, BaseModel):
        roh = roh.model_dump()
    if roh is None:
        roh = json.loads(str(getattr(antwort, "text", "") or "null"))
    return format_.model_validate(roh)


def _aufruf[M: BaseModel](
    complete: CompleteFunktion,
    ergebnis: Ergebnis,
    nachrichten: list[dict[str, str]],
    format_: type[M],
    zweck: str,
) -> M:
    antwort = complete(nachrichten, schema=format_, zweck=zweck)
    modell, provider = getattr(antwort, "modell", None), getattr(antwort, "provider", None)
    ergebnis.aufrufe.append(
        {
            "zweck": zweck,
            "modell": None if modell is None else str(modell),
            "provider": None if provider is None else str(provider),
        }
    )
    return _antwort_lesen(antwort, format_)


def kontext_bauen(
    conn: Verbindung, regelsatz_basis: str = "v1", lieferung: str | None = None
) -> dict[str, Any]:
    """Was eine Rolle sehen darf: Regeln, Schema, Klassifikation der Qualifikation, Lauf-Aggregate.

    Mit ``lieferung`` zusätzlich die festen Rohdaten-Kennzahlen dieser Lieferung (``roh_kennzahlen``);
    roh.* und bereinigt.* sind für freie Abfragen gesperrt.
    """
    kontext: dict[str, Any] = {
        "regelsatz_basis": regelsatz_basis,
        "regeln": regeln_lesen(conn, regelsatz_basis),
    }
    if regelsatz_basis != "v2" and regelsatz_vorhanden(conn, "v2"):
        kontext["regeln_v2"] = regeln_lesen(conn, "v2")
    kontext["klassifikation"] = klassifikation_lesen(conn, "qualifikation")
    kontext["neue_regel_arten"] = {
        art: {"typ": "zaehl", "parameter_pflicht": text} for art, text in _AUSWERTUNG_PARAMETER_TEXT.items()
    }
    kontext["schema"] = schema_lesen(conn)
    kontext["laeufe"] = sql_lesen(
        conn,
        """SELECT DISTINCT ON (regelsatz, lieferung) regelsatz, lieferung, gezaehlt, ergebnis_status
           FROM meta.lauf WHERE status IN ('fertig', 'unveraendert')
           ORDER BY regelsatz, lieferung, id DESC""",
    )["zeilen"]
    if lieferung is not None:
        kontext["roh_kennzahlen"] = roh_kennzahlen(conn, lieferung)
    return kontext


def agent_ausfuehren(
    conn: Verbindung,
    anweisung: str,
    *,
    complete: CompleteFunktion | None = None,
    regelsatz_basis: str = "v1",
    probe_lieferung: str | None = None,
) -> Ergebnis:
    """Setzt eine Anweisung in Sprache in einen offenen Vorschlag um (oder fragt zurück).

    ``complete`` ist der Modell-Schalter (Standard: ``plattform.llm.complete``); Tests geben einen Fake.
    Mit ``probe_lieferung`` rechnet das Programm gleich die Probe für diesen Monat.
    """
    ergebnis = Ergebnis(anweisung=anweisung)
    grund = anweisung_pruefen(anweisung)
    if grund is not None:
        ergebnis.abgelehnt = grund
        return ergebnis
    modell_aufruf = complete or plattform_bruecke.lade_complete()
    try:
        koordination = _aufruf(
            modell_aufruf,
            ergebnis,
            [{"role": "system", "content": koordinator_prompt()}, {"role": "user", "content": anweisung}],
            Koordination,
            KOORDINATOR_ZWECK,
        )
    except (ValidationError, ValueError) as fehler:
        ergebnis.abgelehnt = f"Antwort des Koordinators passt nicht zum Format ({type(fehler).__name__})"
        return ergebnis
    if koordination.rueckfrage or koordination.rolle is None:
        ergebnis.rueckfrage = (
            koordination.rueckfrage or "Welche Rolle ist gemeint? Bitte genauer beschreiben."
        )
        return ergebnis

    rolle = ROLLEN[koordination.rolle]
    ergebnis.rolle = rolle.name
    kontext = kontext_bauen(conn, regelsatz_basis, probe_lieferung)
    nachrichten = [
        {"role": "system", "content": rolle.system_prompt},
        {
            "role": "user",
            "content": f"Anweisung: {anweisung}\nAuftrag des Koordinators: {koordination.auftrag}\n"
            f"Kontext (JSON):\n{json.dumps(kontext, ensure_ascii=False, default=str)}",
        },
    ]
    try:
        antwort = _aufruf(modell_aufruf, ergebnis, nachrichten, VorschlagAntwort, rolle.zweck)
    except (ValidationError, ValueError) as fehler:
        ergebnis.abgelehnt = (
            f"Antwort der Rolle {rolle.name} passt nicht zum Format ({type(fehler).__name__})"
        )
        return ergebnis
    ergebnis.modell, ergebnis.provider = ergebnis.aufrufe[-1]["modell"], ergebnis.aufrufe[-1]["provider"]
    if antwort.rueckfrage:
        ergebnis.rueckfrage = antwort.rueckfrage
        return ergebnis
    try:
        g = vorschlag_pruefen(conn, rolle, antwort, regelsatz_basis=regelsatz_basis)
    except VorschlagUngueltig as fehler:
        ergebnis.abgelehnt = str(fehler)
        return ergebnis
    ergebnis.vorschlag_id = vorschlag_anlegen(
        conn,
        anweisung=anweisung,
        rolle=rolle.name,
        typ=g.typ,
        regelsatz_ziel=g.regelsatz_ziel,
        regelsatz_basis=g.regelsatz_basis,
        begruendung=g.begruendung,
        aenderungen=g.aenderungen or None,
        datei=g.datei,
        modell=ergebnis.modell,
        provider=ergebnis.provider,
    )
    if probe_lieferung is not None:
        probe_rechnen(conn, ergebnis.vorschlag_id, probe_lieferung)
    return ergebnis
