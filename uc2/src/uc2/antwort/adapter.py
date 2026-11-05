"""UC4-Adapter `antwort(frage, kontext) -> UcAntwort` für UC2 (#103, Epic #95).

UC2 liefert in der Kette uc3 → uc2 → uc1 die Abwägung der Akteure mit Beleg. Zwei Wege:

- **Frage mit Fall** (Stichwortregel `waehle_fall`, z. B. „Wartezeiten“): Der Experte rechnet das Paket des
  Falls, das Panel verhandelt mit dessen Zahlen, der Text nennt das Rechenmodell.
- **Allgemeine Frage** (kein Fall passt, z. B. Beschäftigte in Wien): Kein Rechenmodell. Der Moderator
  bekommt nur die Ausgangslage aus dem Kontext (UC3-Zahlen mit Beleg, `uc2.antwort.allgemein`).

In beiden Wegen: Kurzverhandlung (`uc2.antwort.kurzlauf`, Standard eine Runde mit höchstens 3 Akteuren und
einer Frist von 25 s); der Code schreibt den Text. Die erste Zeile ist die Kernaussage, die oben auf der
Station
steht: Was mehr oder weniger Personal bedeutet (allgemeine Frage, Moderator, sonst feste Sätze), oder was das
durchgerechnete Paket bringt und kostet (Fall). Die Zahl von UC3 steht dort nicht, sie steht schon bei UC3
(#164).
Zahlen kommen nur vom Experten oder aus dem Kontext. Jede
Zeile läuft durch `bereinige` (`uc2.antwort.textzahlen`: jede Zifferngruppe muss mit Wert, Vorzeichen und
Einheit zu `zahlen` passen); danach prüft `freie_zahlen` den ganzen Text und wirft `FreieZahl`, statt eine
unbelegte Zahl auszuliefern.

`protokoll_id` bleibt `None`: Der Kurzlauf schreibt nicht in PG (Begründung in `uc2.antwort.kurzlauf`).
Fehler werfen (`AntwortFehler` und Unterklassen, `ModellKonfigFehler`, `BelegFehler`,
`plattform.llm.BudgetErschoepft` unverändert); der Router zählt den UC dann als fehlend und nennt den
Fehlertyp als Grund. Es gibt keinen Ersatztext.
"""

from __future__ import annotations

import contextlib
import re
import time
from collections.abc import Iterator, Sequence
from datetime import date
from pathlib import Path
from typing import Any

import psycopg

# plattform hat keinen py.typed-Marker (E0); wie in uc2.modelle.
from plattform.antwortform import Beleg, UcAntwort, Zahl  # type: ignore[import-untyped]

from uc2.akteure.laden import Akteur, lade_akteure
from uc2.db import conninfo
from uc2.experte.modell import ergebnis as experte_ergebnis
from uc2.experte.modell import lade_paket, zahl_de
from uc2.modelle import waehle_provider
from uc2.verhandlung import prompts
from uc2.verhandlung.belege import Beleg as PresseBeleg
from uc2.verhandlung.belege import Belegquelle, FixtureQuelle, IndexQuelle, hat_index, lade_namensliste
from uc2.verhandlung.fall import Falldefinition, bekannte_faelle, lade_fall
from uc2.verhandlung.pruefungen import experten_ergebniswerte

from . import allgemein
from .kurzlauf import FRIST_S, KURZ_MAX_AKTEURE, KURZ_RUNDEN, Kurzergebnis, KurzlaufFehler, kurzverhandlung
from .textzahlen import ERSATZ as ERSATZ  # Wiederexport: Tests und Aufrufer lesen ihn hier
from .textzahlen import ERSATZ as _ERSATZ
from .textzahlen import bereinige, freie_zahlen, profilzahlen, sichtbare_einheit

QUELLE_EXPERTE = "uc2.experte"
QUELLE_PRESSE = "presse"
QUELLE_BEISPIEL = "beispielbeleg (erfunden)"
"""Quelle eines Fixture-Belegs: Medium und Text sind erfunden, nur zur Vorführung ohne Index."""
MODELLANNAHME = "Modellannahme"
VERBINDUNG_TIMEOUT_S = 3
_KATEGORIE = {
    "konsens": "alle dafür",
    "mehrheit": "Mehrheit dafür",
    "abgelehnt": "Mehrheit dagegen",
    "offener_konflikt": "noch strittig",
}
_ALLTAG = {
    "konsens": "Bei diesem Thema sind sich alle einig.",
    "mehrheit": "Die meisten sind dafür, einige haben noch Bedenken.",
    "abgelehnt": "Die meisten sind dagegen.",
    "offener_konflikt": "Hier gehen die Meinungen auseinander.",
}
"""Was die Einordnung für Bürger heißt, ohne Prognose: Verhandelt wurde keine Maßnahme."""
_ZIELPRUEFUNG = {
    "erfüllt": "Ja, unter allen durchgerechneten Annahmen",
    "nicht erfüllt": "Nein, unter keiner der durchgerechneten Annahmen",
    "offen": "Das ist offen, es hängt von den Annahmen ab",
}
_STAND = {"endgueltig": "endgültig", "vorlaeufig": "vorläufig, die Zahl kann sich noch ändern"}
_STATISTIK = {"uc3": "Beschäftigtenstatistik"}
"""Name der Statistik im Text; Tabelle, Lieferung und SQL stehen nur im Beleg."""
_MONAT = (
    "Jänner", "Februar", "März", "April", "Mai", "Juni",
    "Juli", "August", "September", "Oktober", "November", "Dezember",
)  # fmt: skip
_WORT = {1: "eine", 2: "zwei", 3: "drei", 4: "vier", 5: "fünf", 6: "sechs"}
_HOECHSTENS_KONTEXT_IM_TEXT = 3


class AntwortFehler(RuntimeError):
    """UC2 kann die Frage nicht beantworten (Panel ohne Position, leere Frage)."""


class FreieZahl(AntwortFehler):
    """Im fertigen Text steht eine Zahl, die nicht in `zahlen` steht."""


# --- Fall und Zahlen ----------------------------------------------------------------------------------


def stichwort(fall_id: str) -> str:
    """Stichwort eines Falls: Fall-ID ohne die letzten zwei Buchstaben (`wartezeiten` → `wartezeit`).

    So trifft auch der Singular. Bindestrich und Unterstrich gelten als Leerzeichen.
    """
    return fall_id[: max(4, len(fall_id) - 2)].replace("-", " ").replace("_", " ")


def waehle_fall(frage: str, ordner: Path | None = None) -> Falldefinition | None:
    """Stichwortregel: erster Fall (alphabetisch), dessen `stichwort` in der Frage steht, sonst None.

    None heißt allgemeine Frage: Der Adapter rechnet dann kein Paket.
    """
    text = frage.casefold()
    for fall_id in bekannte_faelle(ordner):
        if stichwort(fall_id) in text:
            return lade_fall(fall_id, ordner)
    return None


class _Sammlung:
    """Belege und Zahlen der Antwort; gleiche Belege stehen nur einmal in `belege`."""

    def __init__(self) -> None:
        self.belege: list[Beleg] = []
        self.zahlen: list[Zahl] = []

    def beleg(self, beleg: Beleg) -> int:
        for i, vorhanden in enumerate(self.belege):
            if vorhanden == beleg:
                return i
        self.belege.append(beleg)
        return len(self.belege) - 1

    def zahl(self, bezeichnung: str, wert: int | float, einheit: str | None, beleg: int) -> Zahl:
        zahl = Zahl(bezeichnung=bezeichnung, wert=wert, einheit=einheit, beleg=beleg)
        self.zahlen.append(zahl)
        return zahl


def _kontextzahlen(kontext: Sequence[UcAntwort], s: _Sammlung) -> list[tuple[Zahl, Beleg]]:
    """Zahlen der Kontext-Antworten mit ihrem Beleg übernehmen; der Beleg bleibt unverändert (Herkunft)."""
    uebernommen = []
    for vorher in kontext:
        for zahl in vorher.zahlen:
            beleg = vorher.belege[zahl.beleg].model_copy(deep=True)
            neu = s.zahl(zahl.bezeichnung, zahl.wert, zahl.einheit, s.beleg(beleg))
            uebernommen.append((neu, beleg))
    return uebernommen


def _kontext_fuer_prompt(kontextzahlen: list[tuple[Zahl, Beleg]]) -> list[dict[str, Any]]:
    return [
        {
            "bezeichnung": z.bezeichnung,
            "wert": z.wert,
            "einheit": z.einheit,
            "uc": b.uc,
            "quelle": b.quelle,
            "lieferung": b.lieferung,
            "monat": b.monat,
            "stand": b.stand,
        }
        for z, b in kontextzahlen
    ]


def _experte_zahlen(voll: dict[str, Any], s: _Sammlung) -> dict[str, Zahl]:
    """Kennzahlen des Experten als `Zahl` mit einem Beleg `uc2.experte`, `ref` = Paket-ID."""
    idx = s.beleg(Beleg(uc="uc2", quelle=QUELLE_EXPERTE, ref=str(voll["paket"]), sql=None))
    k = voll["kennzahlen"]
    z = voll["zielpruefung"]
    ziel = voll["ziel"]
    zahlen = {
        "wartezeit": s.zahl(
            "Wartezeitänderung (wahrscheinlichster Wert)", k["wartezeit_aenderung_prozent"]["modus"], "%", idx
        ),
        "wartezeit_min": s.zahl(
            "Wartezeitänderung (günstigster Fall)", k["wartezeit_aenderung_prozent"]["min"], "%", idx
        ),
        "wartezeit_max": s.zahl(
            "Wartezeitänderung (ungünstigster Fall)", k["wartezeit_aenderung_prozent"]["max"], "%", idx
        ),
        "kosten": s.zahl(
            "Mehrkosten in % der Gesundheitsausgaben (wahrscheinlichster Wert)",
            k["kosten_aenderung_prozent"]["modus"],
            "%",
            idx,
        ),
        "kosten_mio": s.zahl(
            "Mehrkosten pro Jahr (wahrscheinlichster Wert)", k["mehrkosten_mio_eur"]["modus"], "Mio EUR", idx
        ),
        "ziel_wartezeit": s.zahl(
            "Ziel Wartezeitänderung", ziel["wartezeit_aenderung_prozent_hoechstens"], "%", idx
        ),
        "ziel_kosten": s.zahl(
            "Ziel Mehrkosten höchstens", ziel["kosten_aenderung_prozent_hoechstens"], "%", idx
        ),
        "ecken_erreicht": s.zahl(
            "Durchgerechnete Annahmen, bei denen das Ziel erreicht wird", z["ecken_erreicht"], None, idx
        ),
        "ecken": s.zahl("Durchgerechnete Annahmen insgesamt", z["ecken"], None, idx),
    }
    for m in voll["massnahmen"]:
        # Katalog-Einheiten sind Sätze („% zusätzliche … Kassenstellen“); in der Zahl steht nur das Kürzel.
        einheit = str(m["einheit"])
        kurz = "%" if einheit.startswith("%") else einheit
        zahlen[f"massnahme_{m['id']}"] = s.zahl(f"Umfang: {m['name']}", m["umfang"], kurz, idx)
    return zahlen


# --- Zahlen im Text -----------------------------------------------------------------------------------


def _zahl_text(zahl: Zahl) -> str:
    """Deutsch formatiert, mit Tausenderpunkt („135.790 Personen“, „1.250 Mio EUR“)."""
    wert = zahl.wert
    ganz = isinstance(wert, int) or float(wert).is_integer()
    stellen = 0 if ganz else (1 if round(float(wert), 1) == wert else 2)
    text = zahl_de(float(wert), stellen)
    einheit = sichtbare_einheit(zahl.einheit)
    return f"{text} {einheit}" if einheit else text


def _monat_text(monat: str) -> str:
    """`2025-03` → „März 2025“; anderes bleibt, wie es ist."""
    treffer = re.fullmatch(r"(\d{4})-(\d{2})", monat)
    if treffer is None or not 1 <= int(treffer.group(2)) <= 12:
        return monat
    return f"{_MONAT[int(treffer.group(2)) - 1]} {treffer.group(1)}"


def _herkunft(beleg: Beleg) -> str:
    """Herkunft zum Vorlesen: „laut Beschäftigtenstatistik, März 2025, endgültig“, ohne Tabelle und Lieferung.

    Die Sprachausgabe liest diesen Satz vor; Tabelle, Lieferung und SQL stehen nur im Beleg.
    """
    teile = [f"laut {_STATISTIK.get(beleg.uc, 'Statistik')}"]
    if beleg.monat:
        teile.append(_monat_text(beleg.monat))
    if beleg.stand:
        teile.append(_STAND.get(beleg.stand, beleg.stand))
    return ", ".join(teile)


# --- Belegquelle --------------------------------------------------------------------------------------


@contextlib.contextmanager
def belegquelle() -> Iterator[Belegquelle]:
    """`IndexQuelle` mit Maskierung, wenn `UC2_NAMENSLISTE` geladen ist und der Index Abschnitte hat.

    Sonst `FixtureQuelle` (erfundene Belege). Die Verbindung zu `healthpolicy` lebt nur für diese Antwort;
    ist die Datenbank nicht erreichbar, gilt das als „kein Index“.
    """
    namen = lade_namensliste()
    if namen is None:
        yield FixtureQuelle()
        return
    try:
        verbindung = psycopg.connect(conninfo(), autocommit=True, connect_timeout=VERBINDUNG_TIMEOUT_S)
    except psycopg.OperationalError:
        yield FixtureQuelle()
        return
    with verbindung:
        if hat_index(verbindung):
            yield IndexQuelle(verbindung, namen=namen)
        else:
            yield FixtureQuelle()


def _presse_beleg(b: PresseBeleg, beispiel: bool) -> Beleg:
    """Beleg mit Herkunft: Quelle nennt Medium (bei Fixture als erfundenes Beispiel), `ref` die Beleg-ID."""
    quelle = f"{QUELLE_BEISPIEL if beispiel else QUELLE_PRESSE}: {b.medium}"
    return Beleg(uc="uc2", quelle=quelle, monat=b.datum.strftime("%Y-%m"), ref=b.beleg_id)


# --- Text ---------------------------------------------------------------------------------------------


def _namen_statt_ids(text: str, akteure: dict[str, Akteur]) -> str:
    """Akteurs-IDs in Modelltext („Position von sv“) durch den Namen ersetzen."""
    muster = re.compile(
        r"(?<![\w-])(" + "|".join(map(re.escape, sorted(akteure, key=len, reverse=True))) + r")(?![\w-])"
    )
    return muster.sub(lambda m: akteure[m.group(1)].name, text)


def _akteur_zeile(
    akteur: Akteur,
    ergebnis: Kurzergebnis,
    titel: dict[str, str],
    s: _Sammlung,
    beispiel: bool,
    akteure: dict[str, Akteur],
) -> str:
    positionen = ergebnis.positionen.get(akteur.id, {})
    if akteur.id in ergebnis.ohne_zug:
        return f"- {akteur.name}: hat keine gültige Antwort geliefert und bleibt ohne Position."
    themen = [t["id"] for t in ergebnis.auftrag["themen"] if t["id"] in positionen]
    dafuer = [titel[t] for t in themen if positionen[t].wert >= 1]
    dagegen = [titel[t] for t in themen if positionen[t].wert <= -1]
    teile = []
    if dafuer:
        teile.append(f"Dafür bei {', '.join(dafuer)}.")
    if dagegen:
        teile.append(f"Dagegen bei {', '.join(dagegen)}.")
    if not teile:
        teile.append("Unentschieden.")
    zeile = f"- {akteur.name}: {' '.join(teile)}"
    if themen:
        grund = _namen_statt_ids(positionen[themen[0]].begruendung, akteure)
        zeile += f" Grund: {grund}"
    # Belege: nur IDs, die der Akteur zitiert hat und die ihm die Belegquelle gegeben hat.
    erlaubt = ergebnis.belege.get(akteur.id, {})
    zitiert: list[PresseBeleg] = []
    for t in themen:
        for bid in positionen[t].beleg_ids:
            if bid in erlaubt and erlaubt[bid] not in zitiert:
                zitiert.append(erlaubt[bid])
    if zitiert:
        for b in zitiert:
            s.beleg(_presse_beleg(b, beispiel))
        art = "Beispielbeleg, erfunden" if beispiel else "Beleg"
        # Alle zitierten Belege stehen in `belege`; im Text steht jedes Medium mit Monat nur einmal.
        chips = "; ".join(
            dict.fromkeys(f"{b.medium}, {_monat_text(b.datum.strftime('%Y-%m'))}" for b in zitiert)
        )
        zeile += f" {art}: {chips}."
    else:
        zeile += (
            f" {MODELLANNAHME}: Dazu gibt es keinen Zeitungsartikel. Die Haltung folgt nur aus der "
            "Beschreibung der Rolle."
        )
    return zeile


def _ausgangslage(kontext: list[tuple[Zahl, Beleg]]) -> str:
    if not kontext:
        return "Zu dieser Frage liegt keine Zahl aus der Statistik vor."
    gezeigt = kontext[:_HOECHSTENS_KONTEXT_IM_TEXT]
    teile = [f"{z.bezeichnung}: {_zahl_text(z)} ({_herkunft(b)})" for z, b in gezeigt]
    text = f"Die Zahl aus der Statistik: {'; '.join(teile)}."
    if len(kontext) > len(gezeigt):
        text += " Weitere Zahlen stehen in der Liste der Zahlen."
    return text


def _abwaegung(ergebnis: Kurzergebnis, akteure: dict[str, Akteur], s: _Sammlung, beispiel: bool) -> list[str]:
    """Wer dafür, wer dagegen, mit Gründen und Belegen, und was das im Alltag heißt."""
    titel = {t["id"]: t["titel"] for t in ergebnis.auftrag["themen"]}
    zeilen = ["Wer ist dafür, wer dagegen:"]
    zeilen += [
        _akteur_zeile(akteure[aid], ergebnis, titel, s, beispiel, akteure) for aid in ergebnis.teilnehmer
    ]
    einordnung = [
        f"{titel[t]}: {_KATEGORIE.get(e.kategorie, e.kategorie)}" for t, e in ergebnis.klassifikation.items()
    ]
    zeilen.append(f"So stehen die Beteiligten zu den Themen: {'; '.join(einordnung)}.")
    alltag = [
        f"{titel[t]}: {_ALLTAG.get(e.kategorie, e.kategorie)}" for t, e in ergebnis.klassifikation.items()
    ]
    zeilen.append(f"Kurz gesagt: {' '.join(alltag)}")
    bedingungen = [
        f"{akteure[aid].name}: {b}"
        for aid in ergebnis.teilnehmer
        for t in ergebnis.zuege.get(aid, {}).get("themen", [])
        for b in t["bedingungen"]
    ]
    if bedingungen:
        zeilen.append(f"Bedingungen: {'; '.join(bedingungen)}.")
    return zeilen


def _kernzeile(ergebnis: Kurzergebnis, ez: dict[str, Zahl]) -> str:
    """Erste Zeile der Antwort, was die Station oben zeigt; ohne Zahlenecho von UC3 (#164)."""
    if ez:
        return (
            "Das durchgerechnete Paket mit mehr Personal bringt laut Rechenmodell: "
            f"Wartezeit {_zahl_text(ez['wartezeit'])}, Mehrkosten {_zahl_text(ez['kosten_mio'])} pro Jahr."
        )
    return ergebnis.kern or " ".join(allgemein.FESTER_KERN)


def _einleitung(ergebnis: Kurzergebnis) -> str:
    n = len(ergebnis.teilnehmer)
    runden = "einer Runde" if ergebnis.runden == 1 else f"{_WORT.get(ergebnis.runden, 'mehreren')} Runden"
    if ergebnis.modelle == ["mock"]:
        art = (
            "Testbetrieb ohne KI: Die Rollen kommen aus einer festen Vorlage. Es ist keine echte Verhandlung."
        )
    else:
        art = "Das ist eine Simulation: Die Rollen spielt eine KI, es ist keine echte Verhandlung."
    return (
        f"{_WORT.get(n, 'Mehrere').capitalize()} Interessenvertretungen haben die Frage in {runden} "
        f"abgewogen. {art}"
    )


def _experte_text(voll: dict[str, Any], ez: dict[str, Zahl]) -> list[str]:
    massnahmen = [f"{m['name']} {_zahl_text(ez[f'massnahme_{m["id"]}'])}" for m in voll["massnahmen"]]
    pruefung = voll["zielpruefung"]["ergebnis"]
    entscheidend = voll["entscheidend"]["annahme"]
    beschreibung = {a["id"]: a["beschreibung"] for a in voll["annahmen"]}
    erreicht, ecken = _zahl_text(ez["ecken_erreicht"]), _zahl_text(ez["ecken"])
    experte = (
        "Ein Rechenmodell ohne KI schätzt die Wirkung im fünften Jahr: Wartezeit "
        f"{_zahl_text(ez['wartezeit'])}, je nach Annahmen zwischen {_zahl_text(ez['wartezeit_min'])} und "
        f"{_zahl_text(ez['wartezeit_max'])}. Mehrkosten {_zahl_text(ez['kosten'])} der Gesundheitsausgaben, "
        f"das sind {_zahl_text(ez['kosten_mio'])} pro Jahr. Das Ziel ist {_zahl_text(ez['ziel_wartezeit'])} "
        f"Wartezeit bei höchstens {_zahl_text(ez['ziel_kosten'])} Mehrkosten. Wird es erreicht? "
        f"{_ZIELPRUEFUNG.get(pruefung, pruefung)} ({erreicht} von {ecken} durchgerechneten Annahmen "
        "erreichen es)."
    )
    if entscheidend in beschreibung:
        experte += f" Am meisten hängt das Ergebnis davon ab: {beschreibung[entscheidend]}."
    return [f"Durchgerechnete Maßnahmen: {', '.join(massnahmen)}.", experte]


def _ohne_entfernte_zahl(zeile: str) -> str:
    """Ein Satz, aus dem die Prüfung eine Zahl genommen hat, fällt ganz weg: „lag bei (Zahl ohne Beleg
    entfernt).“
    sagt niemandem etwas. Die Zeile selbst (etwa mit dem Akteursnamen) bleibt, solange ein Satz übrig ist."""
    if _ERSATZ not in zeile:
        return zeile
    saetze = re.split(r"(?<=[.!?])\s+", zeile)
    return " ".join(satz for satz in saetze if _ERSATZ not in satz)


# --- Adapter ------------------------------------------------------------------------------------------


def antwort(
    frage: str,
    kontext: list[UcAntwort],
    *,
    provider: str | None = None,
    quelle: Belegquelle | None = None,
    max_akteure: int = KURZ_MAX_AKTEURE,
    runden: int = KURZ_RUNDEN,
    stichtag: date | None = None,
    frist_s: float = FRIST_S,
) -> UcAntwort:
    """UC2-Antwort zur Frage: Abwägung der Akteure mit Beleg, Zahlen nur aus Kontext und Rechenmodell.

    `kontext` sind die bisherigen Antworten der Kette (z. B. UC3). Provider: Argument > `LLM_PROVIDER` >
    `modellrollen.yaml`. Belegquelle: `belegquelle()`, sofern nicht übergeben; eine unmaskierte Quelle geht
    nur an `mock` (`pruefe_freigabe` in `kurzverhandlung`). `stichtag` begrenzt das Datum der Belege
    (Standard: Stichtag des Falls, bei allgemeinen Fragen heute).

    Laufzeit (die Web-Route bricht nach 60 s ab): Standard eine Runde mit höchstens 3 Akteuren, deren Züge
    bei echten Providern parallel laufen. `frist_s` zählt ab diesem Aufruf; ist sie um, folgt nach dem
    laufenden Schritt keine weitere Runde und keine Notiz der Moderation.
    """
    if not frage.strip():
        raise AntwortFehler("leere Frage")
    frist_bis = time.monotonic() + frist_s
    gewaehlt = waehle_provider(provider)
    if quelle is not None:
        return _antwort(frage, kontext, gewaehlt, quelle, max_akteure, runden, stichtag, frist_bis)
    with belegquelle() as gefunden:
        return _antwort(frage, kontext, gewaehlt, gefunden, max_akteure, runden, stichtag, frist_bis)


def _antwort(
    frage: str,
    kontext: list[UcAntwort],
    provider: str,
    quelle: Belegquelle,
    max_akteure: int,
    runden: int,
    stichtag: date | None,
    frist_bis: float,
) -> UcAntwort:
    fall = waehle_fall(frage)
    s = _Sammlung()
    kontextzahlen = _kontextzahlen(kontext, s)
    kontext_prompt = _kontext_fuer_prompt(kontextzahlen)
    # Kontextzahlen gelten im Kurzlauf als vorgegeben: Mit Quelle `experte` sind sie kein Widerspruch.
    werte = {float(z.wert) for z, _ in kontextzahlen}

    voll: dict[str, Any] | None = None
    ez: dict[str, Zahl] = {}
    if fall is not None:
        voll = experte_ergebnis(lade_paket(fall.paket))
        ez = _experte_zahlen(voll, s)
        experte = prompts.experte_kurz(voll)
        if kontext_prompt:
            experte["kontext_zahlen"] = kontext_prompt
        werte |= set(experten_ergebniswerte(voll))
        auftrag_nachrichten = prompts.auftrag_nachrichten
    else:
        experte = allgemein.ausgangslage(kontext_prompt)
        auftrag_nachrichten = allgemein.auftrag_nachrichten

    akteure = {a.id: a for a in lade_akteure()}
    try:
        ergebnis = kurzverhandlung(
            frage=frage,
            experte=experte,
            experte_werte=sorted(werte),
            akteure=list(akteure.values()),
            quelle=quelle,
            provider=provider,
            stichtag=stichtag or (fall.stichtag if fall is not None else date.today()),
            max_akteure=max_akteure,
            runden=runden,
            auftrag_nachrichten=auftrag_nachrichten,
            frist_bis=frist_bis,
            # Die Notiz steht nur im Fall-Weg im Text; im allgemeinen Weg spart das einen Aufruf.
            notiz=fall is not None,
            # Allgemeine Fragen: feste Themen statt Auftragsaufruf (gemessen 38,5 s mit Aufruf bei azure).
            fester_auftrag=allgemein.fester_auftrag(frage) if fall is None else None,
            kern=fall is None,
        )
    except KurzlaufFehler as fehler:
        raise AntwortFehler(f"Panel: {fehler}") from fehler

    beispiel = isinstance(quelle, FixtureQuelle)
    zeilen = [_kernzeile(ergebnis, ez), _ausgangslage(kontextzahlen), _einleitung(ergebnis)]
    if voll is not None:
        zeilen += _experte_text(voll, ez)
    zeilen += _abwaegung(ergebnis, akteure, s, beispiel)
    if voll is not None and ergebnis.notiz:
        zeilen.append(f"Einschätzung der Moderation: {_namen_statt_ids(ergebnis.notiz, akteure)}")
    # Zifferngruppen aus den Profilen der Teilnehmer (z. B. die Hotline „1450“) sind Namen, keine Messwerte.
    profil = profilzahlen(
        t
        for aid in ergebnis.teilnehmer
        if aid in akteure
        for feld in ("ziele", "interessen", "restriktionen", "budgetvorgaben", "prioritaeten", "rote_linien")
        for t in getattr(akteure[aid], feld)
    )
    text = "\n".join(_ohne_entfernte_zahl(bereinige(z, s.zahlen, profil)) for z in zeilen)
    frei = freie_zahlen(text, s.zahlen, profil)
    if frei:
        raise FreieZahl(f"Zahl ohne Eintrag in zahlen: {', '.join(frei)}")
    return UcAntwort(
        text=text,
        belege=s.belege,
        zahlen=s.zahlen,
        uc="uc2",
        modell=" + ".join(ergebnis.modelle) or None,
        protokoll_id=None,
    )
