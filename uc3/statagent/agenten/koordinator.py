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
from statagent.regeln import Regel, RegelFehler
from statagent.sonderauswertung import PERSONENTAGE_PARAMETER
from statagent.zaehlung import (
    AUSSCHLUSS_MERKMALE,
    GRUPPIERUNG_MERKMALE,
    ausschluss_bedingung,
    gruppierung_zuordnung,
)


class VorschlagUngueltig(ValueError):
    """Der Vorschlag des Modells passt nicht zu den Regeln in der Datenbank."""


class RolleUnzustaendig(VorschlagUngueltig):
    """Die Rolle hat eine Regel eines Typs angefasst, den sie nicht ändern darf; ``typ`` nennt ihn."""

    def __init__(self, meldung: str, typ: str) -> None:
        super().__init__(meldung)
        self.typ = typ


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
    #: Prüfmeldungen, die an die Rolle zurückgingen (Reparaturrunde), in Reihenfolge
    korrekturen: list[str] = field(default_factory=list)
    regelsatz_basis: str | None = None
    regelsatz_ziel: str | None = None


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
    ("ausschluss", "merkmal"): set(AUSSCHLUSS_MERKMALE),
    ("gruppierung", "merkmal"): set(GRUPPIERUNG_MERKMALE),
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

#: Zählregel-Arten, die der Zählcode kennt, die aber nicht in jedem Regelsatz stehen (zaehlung.py: ohne sie zählt
#: der Code wie bisher). Eine Rolle darf sie in einem neuen Regelsatz anlegen; v1 und v2 bleiben so bitgleich.
#: Live-Probe 05.11.: „Beamte ausschließen“ und „Bundesländer zusammenlegen“ hatten keine Regel-Art.
NEUE_ZAEHL_ARTEN: dict[str, dict[str, str]] = {
    "ausschluss": {
        "merkmal": "eines von "
        + ", ".join(AUSSCHLUSS_MERKMALE)
        + " (region = Bundesland als Code 0-9 laut klassifikation.bundesland; qualifikation = Wert wie in der "
        "Statistik, also nach R6)",
        "werte": "Liste der Ausprägungen, die nicht gezählt werden, genau wie in bekannte_werte; "
        "beim Alter Spannen 'von-bis' in vollendeten Jahren, z. B. '0-14'",
    },
    "gruppierung": {
        "merkmal": "eines von "
        + ", ".join(GRUPPIERUNG_MERKMALE)
        + " (region = Bundesland als Code 0-9 laut klassifikation.bundesland, z. B. 9 = Wien)",
        "zuordnung": "Liste 'Ausprägung=Gruppe', z. B. ['3=Ostregion', '9=Ostregion']; Ausprägungen genau wie in "
        "bekannte_werte; nicht genannte Ausprägungen bleiben, wie sie sind",
    },
}
#: Auswertungs-Regelsatz (z. B. ``ministerium``): eigene Regeln, keine Monatsläufe. Wie der CHECK in 140_vorschlag.sql.
_AUSWERTUNG_REGELSATZ = re.compile(r"[a-z][a-z0-9_]{2,40}")


def _bestand_pruefen(regel: str, p: dict[str, Any]) -> None:
    """Stichtag heißt ein Tag (von = bis), ganzes Monat heißt Monatserster bis Monatsletzter (Live-Probe 05.11.:
    „am 15.“ wurde zu Stichtag mit von = monatsletzter)."""
    art, von, bis = p.get("zeitraum_art"), p.get("von"), p.get("bis")
    if art == "Stichtag" and von != bis:
        raise VorschlagUngueltig(
            f"{regel}: bei zeitraum_art Stichtag sind von und bis derselbe Tag (z. B. beide tag:15), nicht "
            f"{von!r} und {bis!r}"
        )
    if art == "Monat" and (von, bis) != ("monatserster", "monatsletzter"):
        raise VorschlagUngueltig(
            f"{regel}: bei zeitraum_art Monat ist von monatserster und bis monatsletzter, nicht {von!r} und {bis!r}"
        )


def _gleicher_typ(alt: object, neu: object) -> bool:
    if isinstance(alt, bool) or isinstance(neu, bool):
        return isinstance(alt, bool) and isinstance(neu, bool)
    if isinstance(alt, int | float):
        return isinstance(neu, int | float)
    return type(alt) is type(neu)


def _wert_pruefen(art: str, schluessel: str, alt: object, neu: object, regel: str) -> None:
    erlaubt = _ZULAESSIG.get((art, schluessel))
    # Erst der Typ: ein Listenwert wie ["Stichtag"] ist nicht hashbar und wäre sonst ein Absturz statt einer Meldung.
    if isinstance(erlaubt, set) and (not isinstance(neu, str) or neu not in erlaubt):
        werte = ", ".join(sorted(erlaubt))
        raise VorschlagUngueltig(
            f"{regel}.{schluessel}: {neu!r} ist für die Art {art} nicht zulässig ({werte})"
        )
    if isinstance(erlaubt, re.Pattern) and not (isinstance(neu, str) and erlaubt.match(neu)):
        raise VorschlagUngueltig(f"{regel}.{schluessel}: {neu!r} passt nicht zu {erlaubt.pattern}")
    if alt is not None and not _gleicher_typ(alt, neu):
        raise VorschlagUngueltig(f"{regel}.{schluessel}: Wert {neu!r} hat einen anderen Typ als bisher")


_REGEL_TEXTE = frozenset({"beschreibung", "begruendung", "grundlage", "name"})
#: Parameter einer Prüfregel, die nur Text der Meldung sind (Live-Probe 05.11.: „Monat 13 → 1. Jänner“ änderte nur
#: den Maßnahmetext von P04, keine Zahl).
_PRUEFTEXTE = frozenset({"satz", "massnahme"})


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


def _v_nummer(regelsatz: str) -> int:
    return int(regelsatz[1:]) if _V_REGELSATZ.fullmatch(regelsatz) else -1


def produktions_regelsatz(conn: Verbindung) -> str:
    """Der aktuelle Stand: jüngster Zählregelsatz v<Zahl> mit mindestens einer freigegebenen Regel (sonst v1).

    Von hier geht eine neue Änderung aus. Nach der Abgabe ist das v2; nach einer freigegebenen Live-Änderung der
    Regelsatz, in dem sie steht (eine Rücknahme geht dann von dort aus).
    """
    # Auch angewendete Vorschläge zählen: nach der Rücknahme einer neuen Regel trägt der neue Regelsatz nur die
    # abgeschaltete Regel mit Freigabe.
    zeilen = conn.execute(
        """SELECT regelsatz FROM meta.regel WHERE aktiv AND freigegeben_von IS NOT NULL
           UNION SELECT regelsatz_ziel FROM meta.vorschlag WHERE status = 'freigegeben' AND angewendet_am IS NOT NULL"""
    ).fetchall()
    kandidaten = [str(z["regelsatz"]) for z in zeilen if _V_REGELSATZ.fullmatch(str(z["regelsatz"]))]
    return max(kandidaten, key=_v_nummer) if kandidaten else "v1"


def probe_monat(conn: Verbindung, basis: str) -> str | None:
    """Monat für die Probe: der jüngste gerechnete der Basis, sonst der jüngste gerechnete überhaupt. Ein Regelsatz
    aus einer Freigabe oder Rücknahme hat keine Läufe; die Probe rechnet beide Stände ohnehin selbst (Review 9b)."""
    z = conn.execute(
        """SELECT lieferung FROM meta.lauf WHERE status IN ('fertig', 'unveraendert')
           ORDER BY (regelsatz = %s) DESC, lieferung DESC LIMIT 1""",
        (basis,),
    ).fetchone()
    return None if z is None else str(z["lieferung"])


def _hat_laeufe(conn: Verbindung, regelsatz: str) -> bool:
    z = conn.execute(
        "SELECT EXISTS (SELECT 1 FROM meta.lauf WHERE regelsatz = %s) AS da", (regelsatz,)
    ).fetchone()
    return bool(z and z["da"])


def ziel_bestimmen(conn: Verbindung, basis: str, gewuenscht: str | None = None) -> str:
    """Ziel-Regelsatz einer Zählregel-Änderung; das entscheidet der Code, nicht das Modell.

    Ein Regelsatz mit Läufen (v1, v2 der Abgabe) ändert sich nie in place: das Ziel ist dann der nächste freie
    v<Zahl>. Nur ein bestehender Entwurf (Regelsatz ohne Läufe, nicht die Basis, auch mit schon freigegebenen
    Änderungen) darf weitere Änderungen sammeln, wenn die Anweisung ihn ausdrücklich nennt (so entstand v2 aus
    Auftrag 1 und 2). Beim Freigeben prüft anwenden.ziel_gesperrt das noch einmal.
    """
    if (
        gewuenscht
        and _V_REGELSATZ.fullmatch(gewuenscht)
        and gewuenscht != basis
        and regelsatz_vorhanden(conn, gewuenscht)
        and not _hat_laeufe(conn, gewuenscht)
    ):
        return gewuenscht
    zeilen = conn.execute(
        """SELECT regelsatz FROM meta.regel UNION SELECT regelsatz FROM meta.lauf
           UNION SELECT regelsatz_ziel FROM meta.vorschlag WHERE status = 'freigegeben'"""
    ).fetchall()
    hoechste = max([_v_nummer(str(z["regelsatz"])) for z in zeilen] + [_v_nummer(basis), 1])
    return f"v{hoechste + 1}"


def bekannte_werte(conn: Verbindung, basis: str) -> dict[str, list[str]]:
    """Ausprägungen je Merkmal, wie sie in der Statistik stehen (Aggregate und Klassifikation, keine Einzeldaten).

    Grundlage für Ausschluss und Gruppierung: das Modell nennt Werte nur aus dieser Liste (Live-Probe: „Wien“
    statt Code „9“ hätte nichts ausgeschlossen). Quelle ist der jüngste Lauf der Basis mit Zellen, sonst der jüngste
    Lauf mit Zellen überhaupt: ein neuer Regelsatz nach einer Rücknahme hat noch keine Läufe (Probe 19:25 fragte
    darum zurück), und ein Lauf mit Status „unveraendert“ legt keine Zellen an (Review 9b: Geschlecht und ÖNACE
    waren für v2 leer),
    dazu die Bundesländer aus stat.klass_region. ``qualifikation`` folgt R6 der Basis: Codes oder Kategorien.
    """
    werte: dict[str, set[str]] = {m: set() for m in ("region", "geschlecht", "oenace")}
    lauf = (
        conn.execute(
            "SELECT lauf_id FROM stat.stat_beschaeftigte WHERE regelsatz = %s ORDER BY lauf_id DESC LIMIT 1",
            (basis,),
        ).fetchone()
        or conn.execute(
            "SELECT lauf_id FROM stat.stat_beschaeftigte ORDER BY lauf_id DESC LIMIT 1"
        ).fetchone()
    )
    if lauf is not None:
        for merkmal in werte:
            zeilen = conn.execute(
                f"SELECT DISTINCT {merkmal} AS w FROM stat.stat_beschaeftigte WHERE lauf_id = %s".encode(),
                (lauf["lauf_id"],),
            ).fetchall()
            werte[merkmal] |= {str(z["w"]) for z in zeilen}
    regionen = conn.execute("SELECT code AS w FROM stat.klass_region WHERE ebene = 'bundesland'").fetchall()
    werte["region"] |= {str(z["w"]) for z in regionen}
    kat = conn.execute("SELECT code, beschaeftigungskategorie AS k FROM stat.klass_qualifikation").fetchall()
    kategorien = {str(z["k"]) for z in kat}
    nach_kategorie = _zaehlt_nach_kategorie(_regeln(conn, basis))
    ergebnis = {m: sorted(w) for m, w in werte.items()}
    ergebnis["qualifikation"] = sorted(kategorien if nach_kategorie else {str(z["code"]) for z in kat})
    ergebnis["beschaeftigungskategorie"] = sorted(kategorien)
    return ergebnis


def _zaehlt_nach_kategorie(regeln: dict[str, dict[str, Any]]) -> bool:
    r6 = next((r for r in regeln.values() if r["typ"] == "zaehl" and r["art"] == "dimension"), None)
    return r6 is not None and dict(r6["parameter"]).get("qualifikation") == "beschaeftigungskategorie"


def _regel_aus(name: str, art: str, parameter: dict[str, Any]) -> Regel:
    return Regel(
        id=0,
        regelsatz="",
        name=name,
        typ="zaehl",
        art=art,
        reihenfolge=100,
        parameter=parameter,
        beschreibung="",
        grundlage="",
        gueltig_ab_lieferung="2024-08",
        gueltig_bis_lieferung=None,
        freigegeben_von=None,
        freigegeben_am=None,
    )


def _neue_zaehlart_pruefen(
    conn: Verbindung, name: str, art: str, parameter: dict[str, Any], basis: str
) -> None:
    """Parameter einer Ausschluss- oder Gruppierungsregel: vollständig, in der Form des Zählcodes, bekannte Werte."""
    erwartet = set(NEUE_ZAEHL_ARTEN[art])
    fehlt, unbekannt = sorted(erwartet - set(parameter)), sorted(set(parameter) - erwartet)
    if fehlt or unbekannt:
        raise VorschlagUngueltig(
            f"{name}: die Art {art} braucht genau die Parameter {', '.join(sorted(erwartet))}"
            + (f" (es fehlt {', '.join(fehlt)})" if fehlt else "")
            + (f" (unbekannt: {', '.join(unbekannt)})" if unbekannt else "")
        )
    regel = _regel_aus(name, art, parameter)
    merkmal = str(parameter["merkmal"])
    try:
        if art == "ausschluss":
            from psycopg import sql

            ausschluss_bedingung(regel, sql.SQL("b.qualifikation"))
            genannt = [str(w) for w in parameter["werte"]]
        else:
            _, zuordnung = gruppierung_zuordnung(regel)
            genannt = sorted(zuordnung)
    except RegelFehler as fehler:
        raise VorschlagUngueltig(str(fehler)) from None
    if merkmal == "alter":
        return
    bekannt = bekannte_werte(conn, basis).get(merkmal, [])
    fremd = [w for w in genannt if w not in bekannt]
    if fremd:
        raise VorschlagUngueltig(
            f"{name}: {', '.join(repr(w) for w in fremd)} gibt es beim Merkmal {merkmal} nicht "
            f"(bekannt: {', '.join(bekannt)})"
        )


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


def _zeichenketten(wert: object) -> list[str]:
    """Alle Zeichenketten in ``wert`` (Schlüssel und Werte, verschachtelt), roh statt als JSON.

    Ein JSON-Text schreibt einen Zeilenumbruch als ``\\n``; „PERSON_ID\\n1001049“ oder „x\\nperson_id“ hätte dann
    keine Wortgrenze und keinen Leerraum mehr, und die Prüfung liefe ins Leere (Review 05.11.).
    """
    if isinstance(wert, str):
        return [wert]
    if isinstance(wert, dict):
        return [t for k, w in wert.items() for t in (*_zeichenketten(k), *_zeichenketten(w))]
    if isinstance(wert, (list, tuple, set, frozenset)):
        return [t for w in wert for t in _zeichenketten(w)]
    return [] if wert is None else [str(wert)]


def _ohne_kennungen(aenderungen: list[dict[str, Any]], begruendung: str, rumpf: str | None) -> None:
    """Code und Parameter nennen keine Kennungsspalte; Fließtext nennt keine konkrete Kennung mit Nummer.

    Der Fließtext (Begründung, Beschreibung einer neuen Regel) darf den Feldnamen nennen, den ein Auftrag verlangt
    („Felder PERSON_ID, GESCHLECHT …“ in Auftrag 3, Live-Probe 05.11.), aber keine Kennung wie „PERSON_ID 1001049“.
    Jede Zeichenkette wird einzeln und roh geprüft, damit Leerraum echter Leerraum ist.
    """
    texte: list[object] = [begruendung]
    ohne_texte: list[dict[str, Any]] = []
    for a in aenderungen:
        regel = a.get("regel")
        if isinstance(regel, dict):
            texte += [regel.get(k) for k in _TEXTFELDER]
            a = {**a, "regel": {k: w for k, w in regel.items() if k not in _TEXTFELDER}}
        ohne_texte.append(a)
    for text in _zeichenketten([ohne_texte, rumpf]):
        if treffer := _KENNUNGSWORT.search(text):
            raise VorschlagUngueltig(
                f"Der Vorschlag nennt „{treffer.group(1).lower()}“; Einzeldaten gehören nicht in Vorschläge."
            )
    if any(_KENNUNG_IN_ANWEISUNG.search(text) for text in _zeichenketten(texte)):
        raise VorschlagUngueltig(
            "Der Vorschlag nennt eine konkrete Kennung; Einzeldaten gehören nicht in Vorschläge."
        )


#: Wort, das eine Kennung ankündigt: „VVH“, „Person(en)“, „…verhältnis“, „ID(s)“, „Kennung“, „Nummer“, „Nr.“,
#: jeweils optional mit ``_ID``/``-ID``.
_KENNUNGS_ANKUENDIGUNG = (
    r"(?:vvh|person(?:en)?|\w*verh(?:ä|ae)ltnis(?:ses|se|sen)?|ids?|kennung(?:en)?|nummern?|nr)(?:[_-]?ids?)?"
)
#: Zwischen Ankündigungen und Zahl: Leerraum (auch Zeilenumbruch) und Satzzeichen wie ``:`` ``=`` ``#`` ``/`` ``.``.
_KENNUNGS_TRENNER = r"[\s:=#/.,\-]*+"
#: Ende einer Zahl: keine weitere Ziffer, keine Einheit. Nur kurze Zahlen (bis vier Stellen) dürfen als Datum oder
#: Dezimalzahl weitergehen (``2025-10``, ``3.5``); eine lange Zahl mit ``,`` ``/`` ``-`` dahinter ist eine Liste von
#: Kennungen („1001049,1001050“, „859975/859976“; Review 5a, 05.11.).
_KENNUNGS_EINHEIT = r"(?!\s*(?:%|(?:prozent|jahre?n?|tag(?:e|en)?|monate?n?|wochen?)\b))"
_KENNUNGS_ENDE_LANG = r"(?!\d)" + _KENNUNGS_EINHEIT
_KENNUNGS_ENDE_KURZ = r"(?!\d)(?![-./,]\d)" + _KENNUNGS_EINHEIT

#: Konkrete Kennung in einer Anweisung oder im Fließtext eines Vorschlags. Eine Kennung im Datensatz hat sechs bis
#: sieben Stellen (VVH_ID um 859975, PERSON_ID um 1001049), daher zwei Formen:
#: - Ankündigung(en) („Person“, „Kennung“, „Personen/IDs/Kennung“, „Verhältnis Nr.“), dann eine Zahl ab fünf Stellen;
#: - ausdrücklicher Spaltenname ``VVH_ID``/``PERSON_ID``, dann eine Zahl beliebiger Länge außer einer Jahreszahl.
#: Alter, Grenzen, Prozente, Tage und Monate („Person 75 und älter“, „100 Jahre“, „3 Prozent“, „2025-10“) bleiben
#: erlaubt: zu kurz, mit Einheit oder als Datum.
_KENNUNG_IN_ANWEISUNG = re.compile(
    r"\b"
    + _KENNUNGS_ANKUENDIGUNG
    + r"(?:\b"
    + _KENNUNGS_TRENNER
    + _KENNUNGS_ANKUENDIGUNG
    + r"){0,3}"
    + _KENNUNGS_TRENNER
    + r"\d{5,}"
    + _KENNUNGS_ENDE_LANG
    + r"|\b(?:vvh|person)[_-]?id"
    + _KENNUNGS_TRENNER
    + r"(?:\d{5,}"
    + _KENNUNGS_ENDE_LANG
    + r"|(?!(?:19|20)\d\d(?!\d))\d{1,4}"
    + _KENNUNGS_ENDE_KURZ
    + r")",
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
    conn: Verbindung,
    rolle: Rolle,
    antwort: VorschlagAntwort,
    *,
    regelsatz_basis: str = "v1",
    regelsatz_ziel: str | None = None,
) -> GeprueftVorschlag:
    """Prüft den Modellvorschlag gegen die Datenbank. Werte vorher liest der Code selbst, nie das Modell.

    ``regelsatz_ziel``: vom Code bestimmtes Ziel (``ziel_bestimmen``); es ersetzt jedes v<Zahl>-Ziel des Modells.
    Ein Auswertungs-Regelsatz (z. B. ``ministerium``) bleibt, wie das Modell ihn nennt.
    """
    if antwort.typ is None:
        raise VorschlagUngueltig("Die Antwort enthält weder Vorschlag noch Rückfrage")
    if antwort.typ not in rolle.typen:
        raise VorschlagUngueltig(f"Die Rolle {rolle.name} darf keine Vorschläge vom Typ {antwort.typ} machen")
    if not antwort.begruendung.strip():
        raise VorschlagUngueltig("Ein Vorschlag braucht eine Begründung")
    ziel = antwort.regelsatz_ziel.strip() or "v2"
    if _V_REGELSATZ.fullmatch(ziel):
        # Nennt das Modell einen Regelsatz mit veröffentlichten Monaten (v1), bleibt es bei der Ablehnung
        # (Schutz veröffentlichter Monate); sonst bestimmt der Code das Ziel, nie in place.
        _ziel_pruefen(conn, ziel)
        ziel = regelsatz_ziel or ziel_bestimmen(conn, regelsatz_basis, ziel)
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
    ausgelassen: list[str] = []
    fremder_typ = ""
    datei: CodeDateiEntwurf | None = None

    if antwort.typ == "regel_aendern":
        if not antwort.aenderungen:
            raise VorschlagUngueltig("regel_aendern ohne Änderung")
        # Ändert der Vorschlag auch Regeln eines Typs, den die Rolle nicht anfassen darf (Live-Probe 05.11.:
        # Geburtsmonat 13 → R5_alter und zugleich der Maßnahmetext von P04), bleiben diese weg und stehen in der
        # Begründung; nur wenn nichts übrig bleibt, ist die Rolle unzuständig.
        erlaubt = []
        for a in antwort.aenderungen:
            r = regeln.get(a.regel_name)
            if r is None:
                raise VorschlagUngueltig(f"Regel {a.regel_name} gibt es im Regelsatz {basis} nicht")
            if r["typ"] in rolle.regeltypen:
                erlaubt.append(a)
            else:
                ausgelassen.append(f"{a.regel_name} ({r['typ']})")
                fremder_typ = str(r["typ"])
        if not erlaubt:
            raise RolleUnzustaendig(
                f"Die Rolle {rolle.name} darf {fremder_typ}-Regeln nicht ändern", fremder_typ
            )
        for a in erlaubt:
            r = regeln[a.regel_name]
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
            if str(r["art"]) == "bestand":
                _bestand_pruefen(a.regel_name, neu)
            if str(r["art"]) in NEUE_ZAEHL_ARTEN:
                # Auch beim Ändern gilt: bekannte Werte, sonst schlösse „auch ohne Wien“ statt Code 9 nichts aus.
                _neue_zaehlart_pruefen(conn, a.regel_name, str(r["art"]), neu, basis)
            if r["typ"] == "pruefung" and set(neu_teil) <= _PRUEFTEXTE:
                raise VorschlagUngueltig(
                    f"{a.regel_name}: nur der Meldungstext einer Prüfregel ändert sich; das ändert keine Zahl. "
                    "Gemeint ist vermutlich eine Zählregel (z. B. R5_alter für Alter und Geburtsmonat 13)"
                )
            if neu == alt:
                raise VorschlagUngueltig(
                    f"{a.regel_name}: der Vorschlag ändert nichts (die Werte stehen schon so in der Regel; zusammenlegen "
                    "oder ausschließen ist eine neue Zählregel der Art gruppierung bzw. ausschluss; sonst ist "
                    "vermutlich eine andere Regel gemeint, z. B. eine Zählregel statt einer Prüfregel)"
                )
            aenderungen.append({"regel_name": a.regel_name, "parameter_alt": alt, "parameter_neu": neu})
    elif antwort.typ == "regel_neu":
        if not antwort.neue_regeln:
            raise VorschlagUngueltig("regel_neu ohne Regel")
        namen_neu: set[str] = set()
        gruppiert_neu: set[str] = set()
        for n in antwort.neue_regeln:
            if n.name in regeln:
                raise VorschlagUngueltig(f"Regel {n.name} gibt es schon; bitte regel_aendern")
            if n.name in namen_neu:
                raise VorschlagUngueltig(
                    f"Regel {n.name} steht zweimal im Vorschlag; jede Regel braucht einen Namen"
                )
            namen_neu.add(n.name)
            if n.typ not in rolle.regeltypen:
                raise RolleUnzustaendig(f"Die Rolle {rolle.name} darf keine {n.typ}-Regeln anlegen", n.typ)
            gleiche_art = [r for r in regeln.values() if r["typ"] == n.typ and r["art"] == n.art]
            parameter = _parameter(n.parameter)
            if n.typ == "zaehl" and not auswertung and n.art in NEUE_ZAEHL_ARTEN:
                if (
                    n.art == "gruppierung"
                    and parameter.get("merkmal") == "beschaeftigungskategorie"
                    and _zaehlt_nach_kategorie(regeln)
                ):
                    # Zählt die Basis nach Kategorie, ist „beschaeftigungskategorie“ der Wert in der Spalte
                    # qualifikation (Probe 19:44: „Arbeiter und Angestellte zusammen“ scheiterte daran).
                    parameter = {**parameter, "merkmal": "qualifikation"}
                _neue_zaehlart_pruefen(conn, n.name, n.art, parameter, basis)
                if n.art == "gruppierung":
                    merkmal = str(parameter["merkmal"])
                    vorhanden = {str(dict(r["parameter"]).get("merkmal")) for r in gleiche_art}
                    if merkmal in vorhanden or merkmal in gruppiert_neu:
                        raise VorschlagUngueltig(
                            f"{n.name}: das Merkmal {merkmal} hat schon eine Gruppierungsregel; bitte alle "
                            "Zuordnungen dieses Merkmals in einer Regel nennen"
                        )
                    gruppiert_neu.add(merkmal)
                for k, w in parameter.items():
                    _wert_pruefen(n.art, k, None, w, n.name)
                regel = n.model_dump(exclude={"parameter"}) | {"parameter": parameter}
                aenderungen.append({"regel": regel})
                continue
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
    begruendung = antwort.begruendung.strip()
    if ausgelassen:
        begruendung += f" Nicht Teil dieses Vorschlags (andere Rolle zuständig): {', '.join(ausgelassen)}."
    return GeprueftVorschlag(antwort.typ, ziel, basis, aenderungen, datei, begruendung)


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


#: Was eine Rolle über die zulässigen Werte der bestehenden Zählregeln wissen muss (Live-Probe 05.11.: „monat_15“
#: statt „tag:15“). Abgeleitet aus _ZULAESSIG, damit Prüfung und Kontext dieselbe Liste haben.
def _zulaessige_werte_text() -> dict[str, str]:
    text: dict[str, str] = {}
    for (art, schluessel), erlaubt in sorted(_ZULAESSIG.items()):
        if isinstance(erlaubt, set):
            text[f"{art}.{schluessel}"] = " | ".join(sorted(erlaubt))
        elif erlaubt is _TAG:
            text[f"{art}.{schluessel}"] = (
                "monatserster | monatsletzter | tag:N (N = Tag im Monat, z. B. tag:15)"
            )
        elif erlaubt is _GEBURTSMONAT_13:
            text[f"{art}.{schluessel}"] = "jahresdifferenz | unbekannt | ersatz:MM-TT (z. B. ersatz:01-01)"
    return text


#: Wegweiser vom Begriff der Anweisung zur Regel (Live-Probe 05.11.: P06 statt R5_alter, E03 statt R5_alter).
_WEGWEISER = {
    "Stichtag, Zeitraum, ganzes Monat, Monatserster/-letzter, Tag im Monat": "zaehl-Regel der Art bestand; "
    "Stichtag am Tag N: zeitraum_art Stichtag und von = bis = tag:N; ganzes Monat: zeitraum_art Monat, von "
    "monatserster, bis monatsletzter",
    "Bundesland, Region": "Merkmal region, Codes laut klassifikation.bundesland (z. B. 9 = Wien)",
    "Alter, Plausibilitätsgrenze des Alters, Geburtsmonat 13, Ersatztag, Alter am Monatsersten/-letzten": "zaehl-"
    "Regel der Art alter (R5_alter, Ersatztag als geburtsmonat_13 = ersatz:MM-TT); E03 erkennt nur das Muster des "
    "Datums, P04/P06/P07 sind Prüfregeln und ändern keine Zahl",
    "Beschäftigungskategorie statt Qualifikation (DV/FD zusammen)": "zaehl-Regel der Art dimension",
    "welcher Abschnitt eines Verhältnisses zählt": "zaehl-Regel der Art abschnittswahl",
    "ÖNACE-Version": "zaehl-Regel der Art klassifikationsversion",
    "Ausprägungen nicht zählen (ohne Beamte, ohne ein Bundesland, Kinder unter einem Alter)": "neue zaehl-Regel "
    "der Art ausschluss (Rolle klassifikation); eine Prüfregel kann niemanden ausschließen",
    "Ausprägungen zusammenlegen (Bundesländer zu Regionen, Kategorien zusammen)": "neue zaehl-Regel der Art "
    "gruppierung auf dem bestehenden Merkmal (z. B. region mit zuordnung ['1=Ost', '3=Ost', '9=Ost'], oder "
    "qualifikation mit ['Arbeiter=Unselbständige', 'Angestellte=Unselbständige']); R6 bleibt dabei, wie es ist, und "
    "eine neue Klassifikation ist nicht nötig",
    "Schwellen, ab wann ein Monat angehalten oder gemeldet wird": "Prüfregel (typ pruefung), Rolle qs; Bestand "
    "gegen Vormonat ist P15, verschwundene Verhältnisse P16; ändere nur die eine, die die Anweisung meint",
    "Mehrere Dinge ausschließen (ohne Beamte und ohne Kinder unter 15)": "je Merkmal eine eigene neue zaehl-Regel "
    "der Art ausschluss",
}


def kontext_bauen(
    conn: Verbindung,
    regelsatz_basis: str = "v1",
    lieferung: str | None = None,
    regelsatz_ziel: str | None = None,
) -> dict[str, Any]:
    """Was eine Rolle sehen darf: Regeln, Schema, Klassifikationen, Lauf-Aggregate, zulässige und bekannte Werte.

    Mit ``lieferung`` zusätzlich die festen Rohdaten-Kennzahlen dieser Lieferung (``roh_kennzahlen``);
    roh.* und bereinigt.* sind für freie Abfragen gesperrt.
    """
    kontext: dict[str, Any] = {
        "regelsatz_basis": regelsatz_basis,
        "regelsatz_ziel": regelsatz_ziel or ziel_bestimmen(conn, regelsatz_basis),
        "wegweiser": _WEGWEISER,
        "regeln": regeln_lesen(conn, regelsatz_basis),
    }
    kontext["zulaessige_werte"] = _zulaessige_werte_text()
    kontext["bekannte_werte"] = bekannte_werte(conn, regelsatz_basis)
    kontext["klassifikation"] = klassifikation_lesen(conn, "qualifikation") | klassifikation_lesen(
        conn, "bundesland"
    )
    kontext["neue_zaehlregel_arten"] = {
        art: {"typ": "zaehl", "parameter_pflicht": text} for art, text in NEUE_ZAEHL_ARTEN.items()
    }
    kontext["neue_regel_arten"] = {
        art: {"typ": "zaehl", "parameter_pflicht": text} for art, text in _AUSWERTUNG_PARAMETER_TEXT.items()
    }
    kontext["schema"] = schema_lesen(conn)
    # Nur Läufe der Basis (alle Regelsätze sprengten den Kontext); der Name ist geprüft (v<Zahl> oder Auswertung).
    filter_rs = (
        f"AND regelsatz = '{regelsatz_basis}'"
        if _V_REGELSATZ.fullmatch(regelsatz_basis) or _AUSWERTUNG_REGELSATZ.fullmatch(regelsatz_basis)
        else ""
    )
    kontext["laeufe"] = sql_lesen(
        conn,
        f"""SELECT DISTINCT ON (regelsatz, lieferung) regelsatz, lieferung, gezaehlt, ergebnis_status
            FROM meta.lauf WHERE status IN ('fertig', 'unveraendert') {filter_rs}
            ORDER BY regelsatz, lieferung, id DESC""",
    )["zeilen"]
    if lieferung is not None:
        kontext["roh_kennzahlen"] = roh_kennzahlen(conn, lieferung)
    return kontext


def _freigegebene_vorschlaege(conn: Verbindung, n: int = 12) -> list[dict[str, Any]]:
    """Die jüngsten freigegebenen Regelvorschläge (Nummer, Anweisung, Regelsatz) für eine Rücknahme."""
    zeilen = conn.execute(
        """SELECT id, rolle, typ, regelsatz_ziel, left(anweisung, 200) AS anweisung FROM meta.vorschlag
           WHERE status = 'freigegeben' AND angewendet_am IS NOT NULL AND typ <> 'code_datei'
           ORDER BY id DESC LIMIT %s""",
        (n,),
    ).fetchall()
    return [dict(z) for z in zeilen]


def ruecknahme_pruefen(conn: Verbindung, vorschlag_id: int, basis: str) -> GeprueftVorschlag:
    """Rücknahme eines freigegebenen Regelvorschlags als neuer Vorgang: der Code rechnet die Umkehrung.

    Geänderte Parameter gehen auf den Stand vor dem Vorschlag zurück, neu angelegte Regeln werden abgeschaltet.
    Ziel ist ein neuer Regelsatz; Basis ist der aktuelle Stand, der den Vorschlag enthalten muss. Nichts wird
    gelöscht, die Historie bleibt.
    """
    z = conn.execute(
        """SELECT id, status, angewendet_am, typ, regelsatz_ziel, aenderungen FROM meta.vorschlag WHERE id = %s""",
        (vorschlag_id,),
    ).fetchone()
    if z is None or z["status"] != "freigegeben" or z["angewendet_am"] is None:
        raise VorschlagUngueltig(f"Vorschlag uc3/{vorschlag_id} ist nicht freigegeben und angewendet")
    if z["typ"] == "code_datei":
        raise VorschlagUngueltig(
            "Eine Code-Datei ändert keine Regel; zurücknehmen heißt, sie nicht mehr zu starten"
        )
    if str(z["regelsatz_ziel"]) != basis:
        raise VorschlagUngueltig(
            f"Vorschlag uc3/{vorschlag_id} steht in {z['regelsatz_ziel']}, der aktuelle Stand ist {basis}; "
            "zurückgenommen wird nur vom Stand aus, der ihn enthält"
        )
    regeln = _regeln(conn, basis)
    aenderungen: list[dict[str, Any]] = []
    roh = z["aenderungen"]
    for a in roh if isinstance(roh, list) else []:
        if z["typ"] == "regel_aendern":
            name = str(a["regel_name"])
            jetzt = regeln.get(name)
            if jetzt is None or dict(jetzt["parameter"]) != a["parameter_neu"]:
                raise VorschlagUngueltig(
                    f"{name} hat in {basis} nicht mehr den Stand des Vorschlags; bitte neu"
                )
            aenderungen.append(
                {"regel_name": name, "parameter_alt": a["parameter_neu"], "parameter_neu": a["parameter_alt"]}
            )
        else:
            name = str(a["regel"]["name"])
            jetzt = regeln.get(name)
            if jetzt is None:
                raise VorschlagUngueltig(f"{name} ist in {basis} nicht mehr aktiv")
            p = dict(jetzt["parameter"])
            aenderungen.append(
                {"regel_name": name, "parameter_alt": p, "parameter_neu": p, "aktiv_neu": False}
            )
    begruendung = (
        f"Rücknahme von Vorschlag uc3/{vorschlag_id} als neuer Vorgang: dieselben Regeln wie vor dem Vorschlag. "
        "Nichts wird gelöscht; der Vorschlag und seine Freigabe bleiben im Protokoll."
    )
    return GeprueftVorschlag(
        "regel_aendern", ziel_bestimmen(conn, basis), basis, aenderungen, None, begruendung
    )


#: Woran der Code erkennt, dass die Anweisung ausdrücklich zurücknehmen will. Ohne eines dieser Wörter ist
#: ``ruecknahme_von`` des Koordinators wirkungslos (Live-Probe 05.11.: „nicht mehr das ganze Monat, sondern am
#: 15.“ wurde als Rücknahme von Auftrag 2 gelesen und stellte den Monatsletzten wieder her).
_RUECKNAHME_WORT = re.compile(
    r"zur(?:ü|ue)ck|r(?:ü|ue)ckg(?:ä|ae)ngig|r(?:ü|ue)cknahme|widerruf|wiederherstell|wie (?:es )?vorher|"
    r"aufheb|storn",
    re.IGNORECASE,
)


def ruecknahme_gemeint(anweisung: str) -> bool:
    """True, wenn die Anweisung eine Rücknahme ausdrücklich verlangt (zurücknehmen, rückgängig, wie vorher …)."""
    return bool(_RUECKNAHME_WORT.search(anweisung))


#: Wort-Weiche für die Rollenwahl, nur als Absicherung: der Koordinator wählte in der Probe 19:2x für „Kinder unter
#: 15 nicht mehr zählen“ die Rolle qs (Vorschlag an P13) und für „Monat 13 → Jänner“ qs (Rückfrage zu P04).
#: Reihenfolge = Vorrang. Diktat-tauglich: Kleinschreibung, Zahlwörter.
_WEICHE: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("qs", re.compile(r"anhalt|schwelle|prozent|warn|melde[nt]?\b|prüfregel|pruefregel", re.IGNORECASE)),
    (
        "klassifikation",
        re.compile(
            r"zusammen|gemeinsam|ausschlie|herausf|heraus\b|weglass|nicht mehr (?:mit)?(?:gez|z(?:ä|ae)hl|vorkomm)|nicht mehr mit\b|z(?:ä|ae)hl\w* (?:\w+ ){0,4}nicht mehr\b(?! das| den| die| am| nur)|"
            r"nicht mitz|\bohne\b|region|bundesl(?:ä|ae)nd|kategorie|beamt|arbeiter|angestellt|gruppe",
            re.IGNORECASE,
        ),
    ),
    (
        "datenmanagement",
        re.compile(
            r"geburt|alter|jahre|stichtag|monatslet|monatserst|ganze[sn]? monat|tag des monats|plausib|"
            r"\bam \w+ten\b|\d{1,2}\.",
            re.IGNORECASE,
        ),
    ),
)


def rolle_nach_worten(anweisung: str) -> str | None:
    """Rolle laut Wort-Weiche oder None, wenn kein Wort passt."""
    return next((rolle for rolle, muster in _WEICHE if muster.search(anweisung)), None)


#: Wie oft eine Rolle einen vom Programm abgelehnten Vorschlag korrigieren darf (Reparaturrunde).
REPARATURRUNDEN = 2


def agent_ausfuehren(
    conn: Verbindung,
    anweisung: str,
    *,
    complete: CompleteFunktion | None = None,
    regelsatz_basis: str | None = "v1",
    probe_lieferung: str | None = None,
) -> Ergebnis:
    """Setzt eine Anweisung in Sprache in einen offenen Vorschlag um (oder fragt zurück).

    ``complete`` ist der Modell-Schalter (Standard: ``plattform.llm.complete``); Tests geben einen Fake.
    ``regelsatz_basis=None`` heißt: vom aktuellen Stand aus (``produktions_regelsatz``). Das Ziel ist immer ein
    neuer Regelsatz (``ziel_bestimmen``). Lehnt das Programm einen Vorschlag ab, bekommt die Rolle die Meldung
    und darf bis zu ``REPARATURRUNDEN`` Mal korrigieren. Mit ``probe_lieferung`` rechnet das Programm gleich die
    Probe für diesen Monat.
    """
    ergebnis = Ergebnis(anweisung=anweisung)
    grund = anweisung_pruefen(anweisung)
    if grund is not None:
        ergebnis.abgelehnt = grund
        return ergebnis
    basis = regelsatz_basis or produktions_regelsatz(conn)
    ergebnis.regelsatz_basis = basis
    modell_aufruf = complete or plattform_bruecke.lade_complete()
    freigegeben = _freigegebene_vorschlaege(conn)
    koordinator_inhalt = anweisung
    if freigegeben:
        koordinator_inhalt += "\nKontext (JSON): " + json.dumps(
            {"aktueller_regelsatz": basis, "freigegeben": freigegeben}, ensure_ascii=False, default=str
        )
    try:
        koordination = _aufruf(
            modell_aufruf,
            ergebnis,
            [
                {"role": "system", "content": koordinator_prompt()},
                {"role": "user", "content": koordinator_inhalt},
            ],
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
    if koordination.ruecknahme_von is not None and ruecknahme_gemeint(anweisung):
        ergebnis.rolle = rolle.name
        try:
            g = ruecknahme_pruefen(conn, koordination.ruecknahme_von, basis)
        except VorschlagUngueltig as fehler:
            ergebnis.abgelehnt = str(fehler)
            return ergebnis
        return _anlegen(conn, ergebnis, rolle, g, probe_lieferung)

    weiche = rolle_nach_worten(anweisung)
    if rolle.name == "qs" and weiche not in (None, "qs"):
        # qs ändert nur Prüfregeln; ohne Schwellen-Wort ist die Anweisung eine Zählfrage.
        rolle = ROLLEN[weiche]
    ziel = ziel_bestimmen(conn, basis)
    ergebnis.regelsatz_ziel = ziel
    kontext = kontext_bauen(conn, basis, probe_lieferung, ziel)
    versucht: set[str] = set()
    nachgefasst = False
    mehrere_bestaetigt = False
    while True:
        ergebnis.rolle = rolle.name
        versucht.add(rolle.name)
        nachrichten = [
            {"role": "system", "content": rolle.system_prompt},
            {
                "role": "user",
                "content": f"Anweisung: {anweisung}\nAuftrag des Koordinators: {koordination.auftrag}\n"
                f"Kontext (JSON):\n{json.dumps(kontext, ensure_ascii=False, default=str)}",
            },
        ]
        runde = 0
        umleiten = False
        while True:
            try:
                antwort = _aufruf(modell_aufruf, ergebnis, nachrichten, VorschlagAntwort, rolle.zweck)
            except (ValidationError, ValueError) as fehler:
                ergebnis.abgelehnt = (
                    f"Antwort der Rolle {rolle.name} passt nicht zum Format ({type(fehler).__name__})"
                )
                return ergebnis
            ergebnis.modell = ergebnis.aufrufe[-1]["modell"]
            ergebnis.provider = ergebnis.aufrufe[-1]["provider"]
            if antwort.rueckfrage:
                # Zweite Meinung: fragt die Rolle zurück und nennt die Wort-Weiche eine andere, noch nicht gefragte
                # Rolle, fragt der Code diese einmal (Probe 19:25: qs fragte zu P04, datenmanagement kann R5).
                if weiche is not None and weiche not in versucht:
                    rolle = ROLLEN[weiche]
                    umleiten = True
                    break
                if not nachgefasst:
                    # Einmal nachfassen (Probe 19:44: „Monat 13 → 1. Jänner“ fragte, ob P04 gemeint sei, obwohl
                    # der Wegweiser R5_alter nennt). Eine echte Mehrdeutigkeit bleibt eine Rückfrage.
                    nachgefasst = True
                    ergebnis.korrekturen.append(f"Rückfrage der Rolle: {antwort.rueckfrage}")
                    nachrichten = [
                        *nachrichten,
                        {"role": "assistant", "content": antwort.model_dump_json()},
                        {
                            "role": "user",
                            "content": "Entscheide selbst mit dem Wegweiser im Kontext: Prüfregeln ändern keine "
                            "Zahl, Zählregeln schon; Namen und Codes stehen in Klassifikation und bekannte_werte. "
                            "Schlage die passende Änderung vor. Frage nur zurück, wenn zwei fachlich verschiedene "
                            "Umsetzungen zu verschiedenen Zahlen führen, und nenne dann beide.",
                        },
                    ]
                    continue
                ergebnis.rueckfrage = antwort.rueckfrage
                return ergebnis
            try:
                g = vorschlag_pruefen(conn, rolle, antwort, regelsatz_basis=basis, regelsatz_ziel=ziel)
            except RolleUnzustaendig as fehler:
                if fehler.typ == "pruefung" and weiche not in (None, "qs") and runde < REPARATURRUNDEN:
                    # Die Anweisung ist eine Zählfrage, die Rolle griff zu einer Prüfregel. Nicht an qs umleiten: die
                    # nähme sie an, und es entstünde ein Vorschlag, der keine Zahl ändert (Stichprobe 20:5x:
                    # „Abschnitt O zählt nicht mehr“ strich ÖNACE aus der Prüfregel P13).
                    runde += 1
                    ergebnis.korrekturen.append(str(fehler))
                    nachrichten = [
                        *nachrichten,
                        {"role": "assistant", "content": antwort.model_dump_json()},
                        {
                            "role": "user",
                            "content": "Eine Prüfregel meldet nur und ändert keine Zahl; die Anweisung verlangt aber "
                            "eine andere Zählung. Schlage eine Zählregel vor (Wegweiser im Kontext) oder stelle eine "
                            "Rückfrage.",
                        },
                    ]
                    continue
                # Der Koordinator hat die falsche Rolle gewählt (Live-Probe 05.11.: Geburtsmonat 13 ging an qs, die
                # keine Zählregeln ändern darf). Einmal die Rolle fragen, die diesen Regeltyp ändern darf.
                zustaendig = next(
                    (
                        r
                        for r in ROLLEN.values()
                        if fehler.typ in r.regeltypen
                        and antwort.typ in r.typen
                        and r.name not in versucht
                        and not (r.name == "qs" and weiche not in (None, "qs"))
                    ),
                    None,
                )
                if zustaendig is None:
                    ergebnis.abgelehnt = str(fehler)
                    return ergebnis
                rolle = zustaendig
                umleiten = True
                break
            except VorschlagUngueltig as fehler:
                if runde >= REPARATURRUNDEN:
                    ergebnis.abgelehnt = str(fehler)
                    return ergebnis
                runde += 1
                ergebnis.korrekturen.append(str(fehler))
                # Reparaturrunde: die Rolle sieht ihre Antwort und die Meldung des Programms und korrigiert.
                nachrichten = [
                    *nachrichten,
                    {"role": "assistant", "content": antwort.model_dump_json()},
                    {
                        "role": "user",
                        "content": f"Das Programm hat den Vorschlag nicht angenommen: {fehler}. Korrigiere den "
                        "Vorschlag (andere Regel, zulässiger Wert, bekannte Ausprägung) oder stelle eine Rückfrage, "
                        "wenn die Anweisung so nicht umsetzbar ist.",
                    },
                ]
                continue
            if len(g.aenderungen) > 1 and not mehrere_bestaetigt:
                # Einmal nachfragen (Probe 20:36: „anhalten ab 3 Prozent“ änderte P15 und ungefragt auch P16). Sind
                # wirklich alle verlangt, kommt derselbe Vorschlag wieder und gilt.
                mehrere_bestaetigt = True
                namen = ", ".join(str(a.get("regel_name") or a["regel"]["name"]) for a in g.aenderungen)
                ergebnis.korrekturen.append(f"Mehrere Regeln, nachgefragt: {namen}")
                nachrichten = [
                    *nachrichten,
                    {"role": "assistant", "content": antwort.model_dump_json()},
                    {
                        "role": "user",
                        "content": f"Dein Vorschlag ändert mehrere Regeln: {namen}. Nimm nur die Regeln, die die "
                        "Anweisung verlangt; lass ähnliche Regeln unverändert. Verlangt sie wirklich alle, gib "
                        "denselben Vorschlag noch einmal aus.",
                    },
                ]
                continue
            break
        if not umleiten:
            break
    return _anlegen(conn, ergebnis, rolle, g, probe_lieferung)


def _anlegen(
    conn: Verbindung, ergebnis: Ergebnis, rolle: Rolle, g: GeprueftVorschlag, probe_lieferung: str | None
) -> Ergebnis:
    ergebnis.regelsatz_ziel = g.regelsatz_ziel
    ergebnis.vorschlag_id = vorschlag_anlegen(
        conn,
        anweisung=ergebnis.anweisung,
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
