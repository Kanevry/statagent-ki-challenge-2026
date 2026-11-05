"""Kurzverhandlung für den UC4-Adapter: Auftrag, Auswahl, Positionsrunde, optional Debatte, ohne PG.

Nachbau des Ablaufs aus `uc2.verhandlung.lauf.Verhandlung` mit denselben Bausteinen (Prompts, Zugprüfung,
Matrix, Szenario-Mock), aber ohne `Fallschreiber`: `Verhandlung` schreibt jeden Schritt in PG und
verhandelt immer die Fall-Frage. Der Adapter muss ohne Datenbank laufen (Router, Web, Tests) und die Frage
des Nutzers verhandeln. Alle Modellaufrufe laufen über `uc2.modelle.rufe`, also
`plattform.llm.complete(zweck="uc2.panel")` mit Modell und Aufwand aus `modellrollen.yaml`.

Den Auftrag baut `auftrag_nachrichten`: für einen Fall `prompts.auftrag_nachrichten` (Experte mit Paket), für
eine allgemeine Frage `uc2.antwort.allgemein.auftrag_nachrichten` (nur Ausgangslage aus dem Kontext). Mit
Provider `mock` antwortet `uc2.antwort.allgemein.KurzMock`.

Laufzeit (die Web-Route `uc4.ts` bricht nach 60 s ab, Review zu !73): Standard eine Runde mit höchstens 3
Akteuren. Die Teilnehmer wählt der Code (Belegzahl und Themenbezug, kein Modellaufruf), die Züge einer Runde
laufen bei echten Providern parallel. Mit einer Frist (`frist_bis`) folgt nach dem laufenden Schritt keine
weitere Runde und keine Notiz mehr. So sind es höchstens 1 + Akteure + 1 Aufrufe (Auftrag, Züge, Notiz),
zuzüglich der Wiederholungen bei ungültigen Antworten.

`BudgetErschoepft` aus `plattform.llm` geht unverändert an den Aufrufer, damit der Router den Grund
`BudgetErschoepft` meldet (Hinweis aus #100 in Web und Voice).
"""

from __future__ import annotations

import functools
import re
import threading
import time
from collections.abc import Callable, Mapping, Sequence
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field, replace
from datetime import date
from typing import Any

# plattform hat keinen py.typed-Marker (E0); wie in uc2.modelle.
from plattform.llm import BudgetErschoepft  # type: ignore[import-untyped]

from uc2.akteure.laden import Akteur
from uc2.modelle import Rollenmodell, UngueltigeAntwort, rollenmodell, rufe
from uc2.verhandlung import prompts
from uc2.verhandlung.belege import Beleg, Belegquelle, pruefe_freigabe
from uc2.verhandlung.lauf import MIN_TEILNEHMER, Zugergebnis, fuehre_zug_aus, zwischenergebnis
from uc2.verhandlung.matrix import Einordnung, Position, Runde, aenderungen, klassifikation, werte
from uc2.verhandlung.pruefungen import haltungen_ohne_beleg, pruefe

from .allgemein import mock_einhaengen, mock_zuruecksetzen

KURZ_MAX_AKTEURE = 3
"""Standard-Höchstzahl der Akteure für UC4 (Laufzeit); erlaubt sind bis `KURZ_GRENZE_AKTEURE`."""
KURZ_GRENZE_AKTEURE = 4
"""Obergrenze für `max_akteure` im Kurzlauf (die volle Verhandlung erlaubt bis zu 6)."""
KURZ_RUNDEN = 1
"""Standard für UC4: nur die Positionsrunde; mit `runden=2` folgt eine Debatte."""
FRIST_S = 25.0
"""Frist ab Start des Adapters; danach keine weitere Runde und keine Notiz (Web-Route: 60 s)."""
ALLTAGSREGEL = (
    "Zusatzregel für diese Kurzfassung, sie geht allen anderen Sprachregeln vor: Themen, Begründungen, "
    "Bedingungen, Zugeständnisse und die Notiz lesen und hören Bürgerinnen und Bürger ohne Fachwissen. "
    "Schreibe in Alltagssprache, in kurzen Sätzen, ohne Abkürzungen und ohne Gedankenstriche. Einen "
    "Fachbegriff verwendest du nur mit einer kurzen Erklärung in Klammern, etwa „Primärversorgung (die "
    "erste Anlaufstelle, zum Beispiel die Hausarztpraxis)“. Eine Zahl schreibst du nur genau so, wie sie in "
    "der Ausgangslage oder beim Rechenmodell steht: gleicher Wert, gleiches Vorzeichen, gleiche Einheit. "
    "Jede andere Zahl lässt du weg, auch Rundennummern, Telefonnummern und eigene Schätzungen; "
    "Jahreszahlen wie „bis 2030“ sind erlaubt. Sage nicht voraus, was sich ändern wird."
)
"""Eigene Sprachregel des Kurzlaufs (Review zu !73), an die Systemnachricht jedes Aufrufs angehängt."""

_MOCK_SPERRE = threading.Lock()
"""`KurzMock` hängt sich global in `plattform.llm` ein; gleichzeitige mock-Läufe warten aufeinander."""
_WORT = re.compile(r"[^\W\d_]{5,}")


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
    """Modelle, die tatsächlich geantwortet haben, sortiert, eindeutig; Provider `mock` heißt `mock`."""
    zuege: dict[str, dict[str, Any]] = field(default_factory=dict)
    """Letzter gültiger Zug je Akteur (mit Bedingungen und Zugeständnissen)."""
    ohne_zug: list[str] = field(default_factory=list)
    """Teilnehmer, die in keiner Runde einen gültigen Zug geliefert haben."""


AuftragNachrichten = Callable[[str, dict[str, Any]], list[dict[str, str]]]


def modellname(provider: str, modell: str) -> str:
    """Name des antwortenden Modells für `UcAntwort.modell`: beim Mock `mock`, sonst das Modell."""
    return "mock" if provider == "mock" else modell


def mit_alltagsregel(nachrichten: list[dict[str, str]]) -> list[dict[str, str]]:
    """Kopie der Nachrichten, `ALLTAGSREGEL` an die Systemnachricht angehängt (oder vorangestellt)."""
    if nachrichten and nachrichten[0].get("role") == "system":
        erste = {**nachrichten[0], "content": f"{nachrichten[0]['content']}\n\n{ALLTAGSREGEL}"}
        return [erste, *nachrichten[1:]]
    return [{"role": "system", "content": ALLTAGSREGEL}, *nachrichten]


def _staemme(text: str) -> set[str]:
    return {w.casefold()[:6] for w in _WORT.findall(text)}


def _budget_weiter(fehler: UngueltigeAntwort) -> None:
    """`BudgetErschoepft` hinter einer `UngueltigeAntwort` unverändert weiterwerfen."""
    if isinstance(fehler.__cause__, BudgetErschoepft):
        raise fehler.__cause__


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
        auftrag_nachrichten: AuftragNachrichten,
        frist_bis: float | None,
        mit_notiz: bool,
        fester_auftrag: dict[str, Any] | None = None,
    ) -> None:
        self.frist_bis = frist_bis
        self.mit_notiz = mit_notiz
        self.fester_auftrag = fester_auftrag
        self.auftrag_nachrichten = auftrag_nachrichten
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

    def frist_um(self) -> bool:
        return self.frist_bis is not None and time.monotonic() >= self.frist_bis

    def _moderator(self, nachrichten: list[dict[str, str]], schema: dict[str, Any], was: str) -> Any:
        try:
            antwort = rufe(self.rm_moderator, mit_alltagsregel(nachrichten), schema)
        except UngueltigeAntwort as fehler:
            _budget_weiter(fehler)
            raise KurzlaufFehler(f"Moderator: kein gültiger {was} ({fehler.kennung})") from fehler
        self.modelle.add(modellname(antwort.provider, antwort.modell))
        return antwort

    def auftrag(self) -> dict[str, Any]:
        antwort = self._moderator(
            self.auftrag_nachrichten(self.frage, self.experte), prompts.AUFTRAG_SCHEMA, "Auftrag"
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
        """Teilnehmer per Code, ohne Modellaufruf: Belegzahl plus doppelt der Themenbezug, dann ID.

        Gleiche Gewichtung wie die Auswahl des Szenario-Mocks; spart den Auswahl-Aufruf (Laufzeit UC4).
        """
        themen = _staemme(" ".join(f"{t['titel']} {t['beschreibung']}" for t in auftrag["themen"]))

        def rang(a: Akteur) -> tuple[int, str]:
            bezug = len(themen & _staemme(" ".join(a.themen_interesse)))
            return -(self.quelle.belegzahl(a, self.frage, self.stichtag) + 2 * bezug), a.id

        reihe = sorted(self.akteure.values(), key=rang)
        return sorted(a.id for a in reihe[: self.max_akteure])

    def verhandle(self) -> Kurzergebnis:
        # Allgemeine Fragen (UC4) bringen einen festen Auftrag mit: spart den Auftragsaufruf (Laufzeit).
        auftrag = self.fester_auftrag if self.fester_auftrag is not None else self.auftrag()
        teilnehmer = self.auswahl(auftrag)
        themen = [t["id"] for t in auftrag["themen"]]
        parallel = 1 if self.provider == "mock" else len(teilnehmer)
        gelaufen = 0
        budget_aus = False
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
                    self.rm_akteur,
                    mit_alltagsregel(nachrichten),
                    akteur=aid,
                    themen=themen,
                    runde=runde,
                    teilnehmer=teilnehmer,
                )

            ergebnisse = _zuege({aid: functools.partial(zug, aid) for aid in teilnehmer}, parallel)
            budget_aus = any(erg.fehler == ["BudgetErschoepft"] for erg in ergebnisse.values())
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
                    self.modelle.add(modellname(erg.provider or self.provider, erg.modell))
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
            vorrunde = zwischenergebnis(jetzt, klass, gueltig, None)
            vorher = jetzt
            gelaufen = runde
            if budget_aus or self.frist_um():
                break
        mit_position = [aid for aid in teilnehmer if aid in letzter_zug]
        if len(mit_position) < MIN_TEILNEHMER:
            if budget_aus:
                # Die Ursache verschluckt `fuehre_zug_aus`; Typ und Meldung wie in plattform.llm.
                raise BudgetErschoepft("Das Tageskontingent für Modellaufrufe ist aufgebraucht.")
            raise KurzlaufFehler(
                f"nur {len(mit_position)} von {len(teilnehmer)} Akteuren mit gültigem Zug "
                f"(mindestens {MIN_TEILNEHMER} nötig)"
            )
        klass = klassifikation(jetzt, teilnehmer, themen)
        notiz = None
        if self.mit_notiz and not budget_aus and not self.frist_um():
            notiz = self._notiz(auftrag, teilnehmer, gelaufen, jetzt, aend, klass, letzte_befunde, ohne_beleg)
        return Kurzergebnis(
            auftrag=auftrag,
            teilnehmer=teilnehmer,
            runden=gelaufen,
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
        runde: int,
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
            runde=runde,
            teilnehmer=teilnehmer,
            positionen=werte(jetzt),
            aenderungen=aend,
            klassifikation={t: e.kategorie for t, e in klass.items()},
            code_widersprueche=befunde,
            haltungen_ohne_beleg=ohne_beleg,
        )
        try:
            antwort = rufe(self.rm_moderator, mit_alltagsregel(nachrichten), prompts.NOTIZ_SCHEMA)
        except UngueltigeAntwort:
            # Auch bei erschöpftem Budget: Die Abwägung steht, nur die Notiz entfällt.
            return None
        self.modelle.add(modellname(antwort.provider, antwort.modell))
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
    auftrag_nachrichten: AuftragNachrichten = prompts.auftrag_nachrichten,
    frist_bis: float | None = None,
    notiz: bool = True,
    fester_auftrag: dict[str, Any] | None = None,
) -> Kurzergebnis:
    """Kurzverhandlung ohne PG; mit Provider `mock` über den Szenario-Mock deterministisch.

    `experte` ist die Kurzform für die Prompts (`prompts.experte_kurz`, ggf. ergänzt um Kontextzahlen),
    `experte_werte` die Zahlen, gegen die `pruefe` Züge mit Quelle `experte` abgleicht.
    `auftrag_nachrichten` baut den Auftrag des Moderators (Fall oder allgemeine Frage, siehe Moduldoku).
    `frist_bis` ist ein Zeitpunkt auf `time.monotonic()`; `None` heißt ohne Frist. `notiz=False` spart den
    Aufruf für die Notiz der Moderation, wenn der Aufrufer sie nicht zeigt.
    """
    if not 1 <= runden <= 2:
        raise ValueError("Kurzlauf: runden muss 1 oder 2 sein")
    if not MIN_TEILNEHMER <= max_akteure <= KURZ_GRENZE_AKTEURE:
        raise ValueError(
            f"Kurzlauf: max_akteure muss zwischen {MIN_TEILNEHMER} und {KURZ_GRENZE_AKTEURE} liegen"
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
        auftrag_nachrichten=auftrag_nachrichten,
        frist_bis=frist_bis,
        mit_notiz=notiz,
        fester_auftrag=fester_auftrag,
    )
    if provider != "mock":
        return lauf.verhandle()
    with _MOCK_SPERRE:
        vorher = mock_einhaengen()
        try:
            return lauf.verhandle()
        finally:
            mock_zuruecksetzen(vorher)
