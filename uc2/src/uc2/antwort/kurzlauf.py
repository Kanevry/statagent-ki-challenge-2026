"""Kurzverhandlung für den UC4-Adapter: Auftrag, Auswahl, Positionsrunde, optional Debatte, ohne PG.

Nachbau des Ablaufs aus `uc2.verhandlung.lauf.Verhandlung` mit denselben Bausteinen (Prompts, Zugprüfung,
Matrix, Szenario-Mock), aber ohne `Fallschreiber`: `Verhandlung` schreibt jeden Schritt in PG und
verhandelt immer die Fall-Frage. Der Adapter muss ohne Datenbank laufen (Router, Web, Tests) und die Frage
des Nutzers verhandeln. Alle Modellaufrufe laufen über `uc2.modelle.rufe`, also
`plattform.llm.complete(zweck="uc2.panel")` mit Modell und Aufwand aus `modellrollen.yaml`.
"""

from __future__ import annotations

import functools
from collections.abc import Callable, Mapping, Sequence
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field, replace
from datetime import date
from typing import Any

from uc2.akteure.laden import Akteur
from uc2.modelle import Rollenmodell, UngueltigeAntwort, rollenmodell, rufe, szenario
from uc2.verhandlung import prompts
from uc2.verhandlung.belege import Beleg, Belegquelle, pruefe_freigabe
from uc2.verhandlung.lauf import (
    MIN_TEILNEHMER,
    PARALLEL_ECHT,
    Zugergebnis,
    _pruefe_auswahl,
    _repariere_auswahl,
    _zwischenergebnis,
    fuehre_zug_aus,
)
from uc2.verhandlung.matrix import Einordnung, Position, Runde, aenderungen, klassifikation, werte
from uc2.verhandlung.pruefungen import haltungen_ohne_beleg, pruefe

KURZ_MAX_AKTEURE = 4
"""Höchstzahl der Akteure im Kurzlauf (die volle Verhandlung erlaubt bis zu 6)."""
KURZ_RUNDEN = 2
"""Runde 1 Position, Runde 2 Debatte; mit `runden=1` nur die Positionsrunde."""


class KurzlaufFehler(RuntimeError):
    """Der Kurzlauf liefert keine verwertbare Position (Moderator ungültig, zu wenige gültige Züge)."""


@dataclass(frozen=True)
class Kurzergebnis:
    """Ergebnis der Kurzverhandlung; Positionen der letzten Runde, Belege je Akteur über alle Runden."""

    auftrag: dict[str, Any]
    teilnehmer: list[str]
    runden: int
    positionen: Runde
    klassifikation: dict[str, Einordnung]
    belege: dict[str, dict[str, Beleg]]
    notiz: str | None
    modelle: list[str]
    """Modelle, die tatsächlich geantwortet haben (aus der `Antwort` von `complete`), sortiert, eindeutig."""
    zuege: dict[str, dict[str, Any]] = field(default_factory=dict)
    """Letzter gültiger Zug je Akteur (mit Bedingungen und Zugeständnissen)."""
    ohne_zug: list[str] = field(default_factory=list)
    """Teilnehmer, die in keiner Runde einen gültigen Zug geliefert haben."""


def _zuege(auftraege: Mapping[str, Callable[[], Zugergebnis]], parallel: int) -> dict[str, Zugergebnis]:
    if parallel <= 1:
        return {aid: auftraege[aid]() for aid in sorted(auftraege)}
    with ThreadPoolExecutor(max_workers=parallel, thread_name_prefix="uc2-kurz") as pool:
        zukunft = {aid: pool.submit(auftraege[aid]) for aid in sorted(auftraege)}
        return {aid: zukunft[aid].result() for aid in sorted(zukunft)}


class _Kurzlauf:
    def __init__(
        self,
        *,
        frage: str,
        experte: dict[str, Any],
        experte_werte: Sequence[float],
        akteure: Mapping[str, Akteur],
        quelle: Belegquelle,
        provider: str,
        stichtag: date,
        max_akteure: int,
        runden: int,
    ) -> None:
        self.frage = frage
        self.experte = experte
        self.experte_werte = list(experte_werte)
        self.akteure = dict(akteure)
        self.quelle = quelle
        self.provider = provider
        self.stichtag = stichtag
        self.max_akteure = max_akteure
        self.runden = runden
        self.rm_moderator: Rollenmodell = rollenmodell("moderator", provider)
        self.rm_akteur: Rollenmodell = rollenmodell("akteur", provider)
        self.modelle: set[str] = set()

    def _moderator(self, nachrichten: list[dict[str, str]], schema: dict[str, Any], was: str) -> Any:
        try:
            antwort = rufe(self.rm_moderator, nachrichten, schema)
        except UngueltigeAntwort as fehler:
            raise KurzlaufFehler(f"Moderator: kein gültiger {was} ({fehler.kennung})") from fehler
        self.modelle.add(antwort.modell)
        return antwort

    def auftrag(self) -> dict[str, Any]:
        antwort = self._moderator(
            prompts.auftrag_nachrichten(self.frage, self.experte), prompts.AUFTRAG_SCHEMA, "Auftrag"
        )
        themen: list[dict[str, Any]] = []
        for t in antwort.json["themen"]:
            if t["id"] not in {x["id"] for x in themen}:
                themen.append({"id": t["id"], "titel": t["titel"], "beschreibung": t["beschreibung"]})
        return {
            "themen": themen,
            "kriterien": list(prompts.KRITERIEN),
            "regeln": list(antwort.json["regeln"]),
            "ziel": antwort.json["ziel"],
        }

    def auswahl(self, auftrag: dict[str, Any]) -> list[str]:
        ids = list(self.akteure)
        belegzahl = {
            aid: self.quelle.belegzahl(a, self.frage, self.stichtag) for aid, a in self.akteure.items()
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
        nachrichten = prompts.auswahl_nachrichten(self.frage, auftrag, pool, self.max_akteure)
        schema = prompts.auswahl_schema(ids)
        daten: dict[str, Any] = {"akteure": []}
        fehler: list[str] = []
        for _ in (1, 2):
            antwort = self._moderator(nachrichten, schema, "Auswahl")
            daten = antwort.json
            fehler = _pruefe_auswahl(daten, ids, self.max_akteure)
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
        liste = _repariere_auswahl(daten, ids, self.max_akteure, belegzahl) if fehler else daten["akteure"]
        return sorted(a["akteur"] for a in liste if a["eingeladen"])

    def verhandle(self) -> Kurzergebnis:
        auftrag = self.auftrag()
        teilnehmer = self.auswahl(auftrag)
        themen = [t["id"] for t in auftrag["themen"]]
        parallel = 1 if self.provider == "mock" else PARALLEL_ECHT
        vorher: Runde | None = None
        jetzt: Runde = {}
        vorrunde: dict[str, Any] | None = None
        letzter_zug: dict[str, dict[str, Any]] = {}
        alle_belege: dict[str, dict[str, Beleg]] = {aid: {} for aid in teilnehmer}
        letzte_befunde: list[dict[str, Any]] = []
        ohne_beleg: list[dict[str, str]] = []
        aend: list[dict[str, Any]] = []
        for runde in range(1, self.runden + 1):
            belege = {
                aid: self.quelle.belege_fuer(self.akteure[aid], self.frage, runde, self.stichtag)
                for aid in teilnehmer
            }
            for aid in teilnehmer:
                alle_belege[aid].update({b.beleg_id: b for b in belege[aid]})

            def zug(
                aid: str,
                runde: int = runde,
                vorrunde: dict[str, Any] | None = vorrunde,
                belege: dict[str, list[Beleg]] = belege,
            ) -> Zugergebnis:
                nachrichten = prompts.akteur_nachrichten(
                    akteur=self.akteure[aid],
                    frage=self.frage,
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

            ergebnisse = _zuege({aid: functools.partial(zug, aid) for aid in teilnehmer}, parallel)
            jetzt = {}
            gueltig: dict[str, dict[str, Any]] = {}
            letzte_befunde, ohne_beleg = [], []
            for aid in teilnehmer:
                erg = ergebnisse[aid]
                alt = (vorher or {}).get(aid, {})
                if erg.zug is None:
                    jetzt[aid] = {t: replace(p, quelle="unveraendert") for t, p in alt.items()}
                    continue
                if erg.modell:
                    self.modelle.add(erg.modell)
                letzter_zug[aid] = erg.zug
                gueltig[aid] = erg.zug
                for befund in pruefe(erg.zug, belege[aid], self.experte_werte):
                    letzte_befunde.append(
                        {
                            "art": befund.art,
                            "akteur": aid,
                            "thema": befund.daten.get("thema") or "",
                            "beschreibung": ", ".join(
                                f"{k}: {v}" for k, v in befund.daten.items() if k != "thema"
                            ),
                        }
                    )
                ohne_beleg += [{"akteur": aid, "thema": t} for t in haltungen_ohne_beleg(erg.zug)]
                neu = {
                    t["thema"]: Position(
                        aid, t["thema"], t["haltung"], t["begruendung"], tuple(t["beleg_ids"])
                    )
                    for t in erg.zug["themen"]
                }
                for t, p in alt.items():
                    neu.setdefault(t, replace(p, quelle="unveraendert"))
                jetzt[aid] = neu
            aend = [a.als_dict() for a in aenderungen(runde, vorher, jetzt)]
            klass = klassifikation(jetzt, teilnehmer, themen)
            vorrunde = _zwischenergebnis(jetzt, klass, gueltig, None)
            vorher = jetzt
        mit_position = [aid for aid in teilnehmer if aid in letzter_zug]
        if len(mit_position) < MIN_TEILNEHMER:
            raise KurzlaufFehler(
                f"nur {len(mit_position)} von {len(teilnehmer)} Akteuren mit gültigem Zug "
                f"(mindestens {MIN_TEILNEHMER} nötig)"
            )
        klass = klassifikation(jetzt, teilnehmer, themen)
        notiz = self._notiz(auftrag, teilnehmer, jetzt, aend, klass, letzte_befunde, ohne_beleg)
        return Kurzergebnis(
            auftrag=auftrag,
            teilnehmer=teilnehmer,
            runden=self.runden,
            positionen=jetzt,
            klassifikation=klass,
            belege=alle_belege,
            notiz=notiz,
            modelle=sorted(self.modelle),
            zuege=letzter_zug,
            ohne_zug=[aid for aid in teilnehmer if aid not in letzter_zug],
        )

    def _notiz(
        self,
        auftrag: dict[str, Any],
        teilnehmer: list[str],
        jetzt: Runde,
        aend: list[dict[str, Any]],
        klass: dict[str, Einordnung],
        befunde: list[dict[str, Any]],
        ohne_beleg: list[dict[str, str]],
    ) -> str | None:
        """Notiz des Moderators zur letzten Runde; fehlt sie (ungültig), entfällt sie, ohne Ersatztext."""
        nachrichten = prompts.notiz_nachrichten(
            frage=self.frage,
            auftrag=auftrag,
            runde=self.runden,
            teilnehmer=teilnehmer,
            positionen=werte(jetzt),
            aenderungen=aend,
            klassifikation={t: e.kategorie for t, e in klass.items()},
            code_widersprueche=befunde,
            haltungen_ohne_beleg=ohne_beleg,
        )
        try:
            antwort = rufe(self.rm_moderator, nachrichten, prompts.NOTIZ_SCHEMA)
        except UngueltigeAntwort:
            return None
        self.modelle.add(antwort.modell)
        return str(antwort.json["notiz"])


def kurzverhandlung(
    *,
    frage: str,
    experte: dict[str, Any],
    experte_werte: Sequence[float],
    akteure: Sequence[Akteur],
    quelle: Belegquelle,
    provider: str,
    stichtag: date,
    max_akteure: int = KURZ_MAX_AKTEURE,
    runden: int = KURZ_RUNDEN,
) -> Kurzergebnis:
    """Kurzverhandlung ohne PG; mit Provider `mock` über den Szenario-Mock deterministisch.

    `experte` ist die Kurzform für die Prompts (`prompts.experte_kurz`, ggf. ergänzt um Kontextzahlen),
    `experte_werte` die Zahlen, gegen die `pruefe` Züge mit Quelle `experte` abgleicht.
    """
    if not 1 <= runden <= 2:
        raise ValueError("Kurzlauf: runden muss 1 oder 2 sein")
    if not MIN_TEILNEHMER <= max_akteure <= KURZ_MAX_AKTEURE:
        raise ValueError(
            f"Kurzlauf: max_akteure muss zwischen {MIN_TEILNEHMER} und {KURZ_MAX_AKTEURE} liegen"
        )
    pruefe_freigabe(quelle, provider)
    lauf = _Kurzlauf(
        frage=frage,
        experte=experte,
        experte_werte=experte_werte,
        akteure={a.id: a for a in akteure},
        quelle=quelle,
        provider=provider,
        stichtag=stichtag,
        max_akteure=max_akteure,
        runden=runden,
    )
    mock = provider == "mock"
    if mock:
        szenario.einhaengen()
    try:
        return lauf.verhandle()
    finally:
        if mock:
            szenario.zuruecksetzen()
