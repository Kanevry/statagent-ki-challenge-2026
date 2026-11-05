"""Ablauf einer Verhandlung (#44, PRD S5): Auftrag, Auswahl, Runden, Prüfungen, Ereignisse.

Runden: 1 Position, 2 Debatte, 3 Verhandlung, danach bis zu 2 Kompromissrunden. Nach Runde 3 endet der Lauf,
sobald eine Runde keine Positionsänderung bringt, sonst nach Runde 5 (oder `max_runden`). Je Runde rufen die
Akteure parallel auf (echte Modelle) und sehen nur das Zwischenergebnis der Vorrunde; geschrieben wird immer
nach `akteur_id` sortiert, so ist `seq` je Fall deterministisch.
"""

from __future__ import annotations

import contextlib
import functools
import logging
from collections.abc import Callable, Iterator
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field, replace
from typing import Any

import psycopg

from uc2.akteure.laden import Akteur, lade_akteure
from uc2.experte.modell import ergebnis as experte_ergebnis
from uc2.experte.modell import lade_paket
from uc2.modelle import ModellKonfigFehler, Rollenmodell, UngueltigeAntwort, rollenmodell, rufe, szenario
from uc2.verhandlung import prompts
from uc2.verhandlung.belege import Beleg, Belegquelle, pruefe_freigabe
from uc2.verhandlung.fall import Falldefinition
from uc2.verhandlung.matrix import Einordnung, Position, Runde, aenderungen, klassifikation, werte
from uc2.verhandlung.pruefungen import (
    experten_ergebniswerte,
    haltungen_ohne_beleg,
    pruefe,
    validiere_zug,
)
from uc2.verhandlung.speicher import Fallschreiber, Herzschlag, ddl_anwenden, neuer_fall

MIN_TEILNEHMER = 2
"""Ab Runde 2 braucht jeder Zug einen anderen Teilnehmer in `bezug_auf`."""
RUNDEN_OHNE_ABBRUCH = 3
PARALLEL_ECHT = 3
"""Gleichzeitige Akteursaufrufe bei echten Modellen (claude startet je Aufruf einen Subprozess)."""
HERZSCHLAG_S = 20.0
ABBRUCH_INTERN = "Der Lauf ist an einem internen Fehler gescheitert."

_log = logging.getLogger(__name__)


class VerhandlungsFehler(RuntimeError):
    """Der Moderator liefert keinen verwertbaren Auftrag; der Fall wird abgebrochen."""


def abbruch_meldung(fehler: BaseException) -> str:
    """Fester, einfacher Satz für das öffentliche Ereignis `abbruch` (SEC-009).

    Nie der Fehlertext selbst: Er kann Env-Namen, Pfade, SQL oder Modelltext tragen. Die Einzelheiten gehen
    nur ins Server-Log (`fuehre_aus`).
    """
    if isinstance(fehler, VerhandlungsFehler):
        return "Das Modell hat nicht geantwortet."
    if isinstance(fehler, ModellKonfigFehler):
        return "Der Dienst ist gerade nicht bereit."
    if isinstance(fehler, psycopg.Error):
        return "Die Datenbank hat einen Fehler gemeldet."
    if isinstance(fehler, KeyboardInterrupt | SystemExit):
        return "Der Lauf wurde beendet."
    return ABBRUCH_INTERN


@dataclass
class Laufoptionen:
    provider: str
    quelle: Belegquelle
    max_akteure: int | None = None
    max_runden: int | None = None
    parallel: int = 1
    verbinde: Callable[[], psycopg.Connection[Any]] | None = None
    """Eigene Verbindung für den Herzschlag; ohne sie gibt es nur Lebenszeichen nach jedem Zug."""
    herzschlag_s: float = HERZSCHLAG_S
    bei_anlage: Callable[[int], None] | None = None
    """Wird mit der Fall-ID aufgerufen, sobald `uc2.fall` committet ist (CLI `--melde-fall-id`, API)."""


@dataclass
class Zugergebnis:
    akteur: str
    zug: dict[str, Any] | None
    fehler: list[str] = field(default_factory=list)
    versuche: int = 0
    provider: str | None = None
    modell: str | None = None
    fallback_stufe: int | None = None


def fuehre_zug_aus(
    rm: Rollenmodell,
    nachrichten: list[dict[str, str]],
    *,
    akteur: str,
    themen: list[str],
    runde: int,
    teilnehmer: list[str],
) -> Zugergebnis:
    """Ein Akteurszug: Schema (Wiederholung im Schalter), dann Code-Prüfung mit genau einer Wiederholung."""
    schema = prompts.zug_schema()
    verlauf = list(nachrichten)
    fehler: list[str] = []
    for versuch in (1, 2):
        try:
            antwort = rufe(rm, verlauf, schema)
        except UngueltigeAntwort as f:
            return Zugergebnis(akteur, None, [f.kennung], versuch)
        fehler = validiere_zug(antwort.json, themen, runde, akteur, teilnehmer)
        if not fehler:
            return Zugergebnis(
                akteur, antwort.json, [], versuch, antwort.provider, antwort.modell, antwort.fallback_stufe
            )
        verlauf = [
            *nachrichten,
            {"role": "assistant", "content": antwort.text},
            prompts.hinweis_nachricht(fehler),
        ]
    return Zugergebnis(akteur, None, fehler, 2)


def pruefe_auswahl(daten: dict[str, Any], ids: list[str], max_akteure: int) -> list[str]:
    """Regelverstöße einer Moderator-Auswahl (Pool vollständig, Ober- und Untergrenze); leer = gültig."""
    fehler = []
    genannt = [a["akteur"] for a in daten["akteure"]]
    if sorted(genannt) != sorted(ids):
        fehler.append("jeder Akteur des Pools muss genau einmal genannt sein")
    eingeladen = [a for a in daten["akteure"] if a["eingeladen"]]
    if len(eingeladen) > max_akteure:
        fehler.append(f"höchstens {max_akteure} Akteure einladen, nicht {len(eingeladen)}")
    if len(eingeladen) < MIN_TEILNEHMER:
        fehler.append(f"mindestens {MIN_TEILNEHMER} Akteure einladen")
    return fehler


def repariere_auswahl(
    daten: dict[str, Any], ids: list[str], max_akteure: int, belegzahl: dict[str, int]
) -> list[dict[str, Any]]:
    """Code-Korrektur nach der Wiederholung: Reihenfolge des Moderators, Obergrenze, Mindestzahl, Lücken."""
    gesehen: dict[str, dict[str, Any]] = {}
    for a in daten["akteure"]:
        gesehen.setdefault(a["akteur"], dict(a))
    zahl = 0
    for a in gesehen.values():
        if a["eingeladen"]:
            zahl += 1
            if zahl > max_akteure:
                a["eingeladen"] = False
                a["begruendung"] = (
                    f"Über der Obergrenze von {max_akteure} (Korrektur durch Code). {a['begruendung']}"
                )
    for aid in ids:
        gesehen.setdefault(
            aid,
            {
                "akteur": aid,
                "eingeladen": False,
                "begruendung": "Vom Moderator nicht bewertet (Korrektur durch Code).",
            },
        )
    for aid in sorted(ids, key=lambda i: (-belegzahl[i], i)):
        if sum(a["eingeladen"] for a in gesehen.values()) >= MIN_TEILNEHMER:
            break
        if not gesehen[aid]["eingeladen"]:
            gesehen[aid]["eingeladen"] = True
            gesehen[aid]["begruendung"] = (
                f"Ergänzt durch Code (mindestens {MIN_TEILNEHMER} Teilnehmer). {gesehen[aid]['begruendung']}"
            )
    return [gesehen[aid] for aid in ids]


def zwischenergebnis(
    jetzt: Runde, klass: dict[str, Einordnung], zuege: dict[str, dict[str, Any]], notiz: str | None
) -> dict[str, Any]:
    """Kontext der nächsten Runde: Positionen, Einigungen, gescheiterte und offene Themen, Bedingungen."""
    bedingungen = []
    zugestaendnisse = []
    for aid in sorted(zuege):
        for t in zuege[aid]["themen"]:
            bedingungen += [{"akteur": aid, "thema": t["thema"], "bedingung": b} for b in t["bedingungen"]]
            if t["zugestaendnis"]:
                zugestaendnisse.append(
                    {"akteur": aid, "thema": t["thema"], "zugestaendnis": t["zugestaendnis"]}
                )
    return {
        "positionen": werte(jetzt),
        "einigungen": [
            {"thema": t, "kategorie": e.kategorie}
            for t, e in klass.items()
            if e.kategorie in ("konsens", "mehrheit")
        ],
        "gescheitert": [t for t, e in klass.items() if e.kategorie == "abgelehnt"],
        "offen": [t for t, e in klass.items() if e.kategorie == "offener_konflikt"],
        "bedingungen": bedingungen,
        "zugestaendnisse": zugestaendnisse,
        "moderator": notiz,
    }


def einigung_ohne_gegenstimme(jetzt: Runde, teilnehmer: list[str], themen: list[str]) -> list[str]:
    """Themen, auf denen jeder Teilnehmer eine Haltung ab +1 hat (Hinweis an den Moderator, #127)."""
    return [
        t
        for t in themen
        if teilnehmer and all(t in jetzt.get(a, {}) and jetzt[a][t].wert >= 1 for a in teilnehmer)
    ]


# Alte Namen: ein anderer Branch importiert sie noch.
_pruefe_auswahl = pruefe_auswahl
_repariere_auswahl = repariere_auswahl
_zwischenergebnis = zwischenergebnis


@contextlib.contextmanager
def _herzschlag(optionen: Laufoptionen, fall_id: int) -> Iterator[None]:
    if optionen.verbinde is None:
        yield
        return
    with Herzschlag(optionen.verbinde, fall_id, optionen.herzschlag_s):
        yield


class Verhandlung:
    """Ein Lauf = ein neuer Fall-Datensatz; `fuehre_aus()` gibt die Fall-ID zurück."""

    def __init__(
        self, verbindung: psycopg.Connection[Any], fall: Falldefinition, optionen: Laufoptionen
    ) -> None:
        self.verbindung = verbindung
        self.fall = fall
        self.optionen = optionen
        self.max_akteure = min(fall.max_akteure, optionen.max_akteure or fall.max_akteure)
        self.max_runden = min(fall.max_runden, optionen.max_runden or fall.max_runden)
        self.rm_moderator = rollenmodell("moderator", optionen.provider)
        self.rm_akteur = rollenmodell("akteur", optionen.provider)
        self.akteure: dict[str, Akteur] = {a.id: a for a in lade_akteure()}
        voll = experte_ergebnis(lade_paket(fall.paket))
        self.experte_voll = voll
        self.experte = prompts.experte_kurz(voll)
        self.experte_werte = experten_ergebniswerte(voll)

    def _modelle(self) -> dict[str, Any]:
        return {
            rm.rolle: {"provider": rm.provider, "modell": rm.modell, "aufwand": rm.aufwand, "zweck": rm.zweck}
            for rm in (self.rm_moderator, self.rm_akteur)
        }

    def fuehre_aus(self) -> int:
        pruefe_freigabe(self.optionen.quelle, self.optionen.provider)
        ddl_anwenden(self.verbindung)
        mock = self.optionen.provider == "mock"
        if mock:
            szenario.einhaengen()
        try:
            fall_id = neuer_fall(
                self.verbindung,
                fall_name=self.fall.id,
                frage=self.fall.frage,
                provider=self.optionen.provider,
                belegquelle=self.optionen.quelle.name,
                modelle=self._modelle(),
                stichtag=self.fall.stichtag,
            )
            schreiber = Fallschreiber(self.verbindung, fall_id)
            try:
                if self.optionen.bei_anlage is not None:
                    self.optionen.bei_anlage(fall_id)
                with _herzschlag(self.optionen, fall_id):
                    self._ablauf(schreiber)
                schreiber.beende("fertig")
            except BaseException as fehler:
                # Abgeschlossene Runden bleiben; der Abbruch darf den ursprünglichen Fehler nie verdecken.
                # Nach außen (SSE, Bericht) nur Fehlertyp und fester Satz; die Einzelheiten ins Server-Log.
                _log.error("Fall %s abgebrochen: %s: %s", fall_id, type(fehler).__name__, fehler)
                with contextlib.suppress(psycopg.Error):
                    self.verbindung.rollback()
                    schreiber.ereignis(
                        "abbruch", {"grund": type(fehler).__name__, "meldung": abbruch_meldung(fehler)}
                    )
                    schreiber.beende("abgebrochen")
                raise
        finally:
            if mock:
                szenario.zuruecksetzen()
        return fall_id

    # --- Schritte -------------------------------------------------------------------------------------

    def _ablauf(self, s: Fallschreiber) -> None:
        f = self.fall
        s.ereignis(
            "start",
            {
                "fall": f.id,
                "frage": f.frage,
                "stichtag": f.stichtag.isoformat(),
                "belegquelle": self.optionen.quelle.name,
                "modelle": self._modelle(),
                "max_akteure": self.max_akteure,
                "max_runden": self.max_runden,
            },
        )
        k = self.experte_voll["kennzahlen"]
        s.ereignis(
            "experte",
            {
                "paket": self.experte_voll["paket"],
                "beschreibung": self.experte_voll["beschreibung"],
                "wartezeit_aenderung_prozent": k["wartezeit_aenderung_prozent"],
                "kosten_aenderung_prozent": k["kosten_aenderung_prozent"],
                "mehrkosten_mio_eur": k["mehrkosten_mio_eur"],
                "zielpruefung": self.experte_voll["zielpruefung"]["ergebnis"],
                "modus_erreicht": self.experte_voll["zielpruefung"]["modus_erreicht"],
                "entscheidend": self.experte_voll["entscheidend"]["text"],
                # Vollständiges Ergebnis: zahl_widerspruch vergleicht gegen dessen Ergebniswerte
                # (`experten_ergebniswerte`), und pruefe_lauf.py liest sie unabhängig daraus nach.
                "ergebnis": self.experte_voll,
            },
        )
        auftrag = self._auftrag(s)
        teilnehmer = self._auswahl(s, auftrag)
        self._runden(s, auftrag, teilnehmer)

    def _auftrag(self, s: Fallschreiber) -> dict[str, Any]:
        try:
            antwort = rufe(
                self.rm_moderator,
                prompts.auftrag_nachrichten(self.fall.frage, self.experte),
                prompts.AUFTRAG_SCHEMA,
            )
        except UngueltigeAntwort as fehler:
            raise VerhandlungsFehler(f"Moderator: kein gültiger Auftrag ({fehler.kennung})") from fehler
        themen: list[dict[str, Any]] = []
        for t in antwort.json["themen"]:
            if t["id"] not in {x["id"] for x in themen}:
                themen.append({"id": t["id"], "titel": t["titel"], "beschreibung": t["beschreibung"]})
        auftrag = {
            "themen": themen,
            "kriterien": list(prompts.KRITERIEN),
            "regeln": list(antwort.json["regeln"]),
            "ziel": antwort.json["ziel"],
        }
        s.auftrag(auftrag)
        s.ereignis(
            "auftrag", {**auftrag, "provider": antwort.provider, "modell": antwort.modell}, akteur="moderator"
        )
        return auftrag

    def _auswahl(self, s: Fallschreiber, auftrag: dict[str, Any]) -> list[str]:
        f = self.fall
        ids = list(self.akteure)
        belegzahl = {
            aid: self.optionen.quelle.belegzahl(a, f.frage, f.stichtag) for aid, a in self.akteure.items()
        }
        pool = [
            {
                "id": a.id,
                "name": a.name,
                "rolle": a.rolle,
                "themen_interesse": list(a.themen_interesse),
                "belegzahl": belegzahl[a.id],
            }
            for a in self.akteure.values()
        ]
        nachrichten = prompts.auswahl_nachrichten(f.frage, auftrag, pool, self.max_akteure)
        schema = prompts.auswahl_schema(ids)
        fehler: list[str] = []
        daten: dict[str, Any] = {"akteure": []}
        for _ in (1, 2):
            try:
                antwort = rufe(self.rm_moderator, nachrichten, schema)
            except UngueltigeAntwort as f_:
                raise VerhandlungsFehler(f"Moderator: keine gültige Auswahl ({f_.kennung})") from f_
            daten = antwort.json
            fehler = pruefe_auswahl(daten, ids, self.max_akteure)
            if not fehler:
                break
            nachrichten = [
                *nachrichten,
                {"role": "assistant", "content": antwort.text},
                {
                    "role": "user",
                    "content": "Deine Auswahl verletzt Regeln: " + "; ".join(fehler) + ". Antworte erneut.",
                },
            ]
        if fehler:
            s.ereignis("auswahl_korrektur", {"fehler": fehler}, akteur="moderator")
            liste = repariere_auswahl(daten, ids, self.max_akteure, belegzahl)
        else:
            liste = sorted(daten["akteure"], key=lambda a: a["akteur"])
        eintraege = []
        for a in sorted(liste, key=lambda x: x["akteur"]):
            s.teilnahme(a["akteur"], a["eingeladen"], a["begruendung"], belegzahl[a["akteur"]])
            eintraege.append({**a, "belegzahl": belegzahl[a["akteur"]]})
        s.ereignis("auswahl", {"akteure": eintraege, "max_akteure": self.max_akteure}, akteur="moderator")
        return sorted(a["akteur"] for a in liste if a["eingeladen"])

    def _alle_zuege(
        self, s: Fallschreiber, auftraege: dict[str, Callable[[], Zugergebnis]]
    ) -> dict[str, Zugergebnis]:
        ergebnisse: dict[str, Zugergebnis] = {}
        parallel = min(self.optionen.parallel, len(auftraege))
        if parallel <= 1:
            for aid in sorted(auftraege):
                ergebnisse[aid] = auftraege[aid]()
                s.lebenszeichen()
            return ergebnisse
        with ThreadPoolExecutor(max_workers=parallel, thread_name_prefix="uc2-zug") as pool:
            zukunft = {pool.submit(auftraege[aid]): aid for aid in sorted(auftraege)}
            for z in as_completed(zukunft):
                ergebnisse[zukunft[z]] = z.result()
                s.lebenszeichen()
        return ergebnisse

    def _runden(self, s: Fallschreiber, auftrag: dict[str, Any], teilnehmer: list[str]) -> None:
        f = self.fall
        themen = [t["id"] for t in auftrag["themen"]]
        runden: dict[int, Runde] = {}
        alle_aenderungen: list[dict[str, Any]] = []
        vorrunde: dict[str, Any] | None = None
        grund = f"Höchstzahl von {self.max_runden} Runden erreicht"
        letzte = 0
        for runde in range(1, self.max_runden + 1):
            letzte = runde
            s.ereignis("runde", {"phase": prompts.PHASEN[runde], "teilnehmer": teilnehmer}, runde=runde)
            belege: dict[str, list[Beleg]] = {
                aid: self.optionen.quelle.belege_fuer(self.akteure[aid], f.frage, runde, f.stichtag)
                for aid in teilnehmer
            }

            def auftrag_fuer(
                aid: str,
                runde: int = runde,
                vorrunde: dict[str, Any] | None = vorrunde,
                belege: dict[str, list[Beleg]] = belege,
            ) -> Zugergebnis:
                nachrichten = prompts.akteur_nachrichten(
                    akteur=self.akteure[aid],
                    frage=f.frage,
                    auftrag=auftrag,
                    runde=runde,
                    teilnehmer=teilnehmer,
                    belege=belege[aid],
                    experte=self.experte,
                    vorrunde=vorrunde,
                )
                return fuehre_zug_aus(
                    self.rm_akteur, nachrichten, akteur=aid, themen=themen, runde=runde, teilnehmer=teilnehmer
                )

            ergebnisse = self._alle_zuege(
                s, {aid: functools.partial(auftrag_fuer, aid) for aid in teilnehmer}
            )
            vorher = runden.get(runde - 1)
            jetzt: Runde = {}
            gueltig: dict[str, dict[str, Any]] = {}
            code_widersprueche: list[dict[str, Any]] = []
            ohne_beleg: list[dict[str, str]] = []
            for aid in teilnehmer:
                s.ereignis("belege", {"belege": [b.chip() for b in belege[aid]]}, runde=runde, akteur=aid)
                erg = ergebnisse[aid]
                alt = (vorher or {}).get(aid, {})
                if erg.zug is None:
                    s.ereignis(
                        "ungueltige_ausgabe",
                        {"fehler": erg.fehler, "versuche": erg.versuche, "position": "unverändert"},
                        runde=runde,
                        akteur=aid,
                    )
                    jetzt[aid] = {t: replace(p, quelle="unveraendert") for t, p in alt.items()}
                    continue
                zug = erg.zug
                gueltig[aid] = zug
                s.ereignis(
                    "zug",
                    {
                        "zug": zug,
                        "provider": erg.provider,
                        "modell": erg.modell,
                        "fallback_stufe": erg.fallback_stufe,
                        "versuche": erg.versuche,
                    },
                    runde=runde,
                    akteur=aid,
                )
                for befund in pruefe(zug, belege[aid], self.experte_werte):
                    s.ereignis(befund.art, befund.daten, runde=runde, akteur=aid)
                    code_widersprueche.append(
                        {
                            "art": befund.art,
                            "akteur": aid,
                            "thema": befund.daten.get("thema") or "",
                            "beschreibung": ", ".join(
                                f"{k}: {v}" for k, v in befund.daten.items() if k != "thema"
                            ),
                        }
                    )
                ohne_beleg += [{"akteur": aid, "thema": t} for t in haltungen_ohne_beleg(zug)]
                neu = {
                    t["thema"]: Position(
                        aid, t["thema"], t["haltung"], t["begruendung"], tuple(t["beleg_ids"])
                    )
                    for t in zug["themen"]
                }
                for t, p in alt.items():
                    neu.setdefault(t, replace(p, quelle="unveraendert"))
                jetzt[aid] = neu
            s.positionen(runde, jetzt)
            runden[runde] = jetzt
            aend = [a.als_dict() for a in aenderungen(runde, vorher, jetzt)]
            alle_aenderungen += aend
            klass = klassifikation(jetzt, teilnehmer, themen)
            notiz = self._notiz(
                s,
                auftrag,
                runde,
                teilnehmer,
                jetzt,
                aend,
                klass,
                code_widersprueche,
                ohne_beleg,
                einigung_ohne_gegenstimme(jetzt, teilnehmer, themen),
            )
            vorrunde = zwischenergebnis(jetzt, klass, gueltig, notiz)
            s.ereignis(
                "runde_ende",
                {
                    "aenderungen": aend,
                    "klassifikation": {t: e.kategorie for t, e in klass.items()},
                    "zwischenergebnis": vorrunde,
                },
                runde=runde,
            )
            if runde >= RUNDEN_OHNE_ABBRUCH and not aend:
                grund = f"Runde {runde} ohne Positionsänderung"
                break
        ende = runden.get(letzte, {})
        klass = klassifikation(ende, teilnehmer, themen)
        s.ereignis(
            "ergebnis",
            {
                "runden": letzte,
                "abbruch": grund,
                "klassifikation": {t: e.als_dict() for t, e in klass.items()},
                "aenderungen": alle_aenderungen,
            },
        )

    def _notiz(
        self,
        s: Fallschreiber,
        auftrag: dict[str, Any],
        runde: int,
        teilnehmer: list[str],
        jetzt: Runde,
        aend: list[dict[str, Any]],
        klass: dict[str, Einordnung],
        code_widersprueche: list[dict[str, Any]],
        ohne_beleg: list[dict[str, str]],
        einig: list[str],
    ) -> str | None:
        nachrichten = prompts.notiz_nachrichten(
            frage=self.fall.frage,
            auftrag=auftrag,
            runde=runde,
            teilnehmer=teilnehmer,
            positionen=werte(jetzt),
            aenderungen=aend,
            klassifikation={t: e.kategorie for t, e in klass.items()},
            code_widersprueche=code_widersprueche,
            haltungen_ohne_beleg=ohne_beleg,
            einigung_ohne_gegenstimme=einig,
            grenzen={
                aid: {
                    "rote_linien": list(self.akteure[aid].rote_linien),
                    "budgetvorgaben": list(self.akteure[aid].budgetvorgaben),
                }
                for aid in teilnehmer
            },
            kosten={
                k: self.experte[k]
                for k in ("mehrkosten_mio_eur", "kosten_aenderung_prozent")
                if k in self.experte
            },
        )
        try:
            antwort = rufe(self.rm_moderator, nachrichten, prompts.NOTIZ_SCHEMA)
        except UngueltigeAntwort as fehler:
            s.ereignis(
                "ungueltige_ausgabe",
                {"fehler": [fehler.kennung], "rolle": "moderator"},
                runde=runde,
                akteur="moderator",
            )
            return None
        s.ereignis(
            "moderator_notiz",
            {
                **antwort.json,
                "code_widersprueche": code_widersprueche,
                "haltungen_ohne_beleg": ohne_beleg,
                "einigung_ohne_gegenstimme": einig,
            },
            runde=runde,
            akteur="moderator",
        )
        return str(antwort.json["notiz"])
