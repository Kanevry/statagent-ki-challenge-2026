"""Deterministisches Wirkungsmodell für Wartezeit und Kosten (#42, PRD S4).

Kein Sprachmodell, keine Zufallszahlen. Maßnahmen wirken als Kapazitätszuwachs Δμ oder Nachfrageminderung
Δλ, mehrere Maßnahmen multiplikativ:

    ρ₁ = ρ₀ · Π(1 − Δλᵢ) / Π(1 + Δμᵢ),   Wartezeitänderung = W(ρ₁)/W(ρ₀) − 1,   W(ρ) = ρ/(1 − ρ).

Modellannahmen (bewusst, Vorgabe aus Issue #42, Entscheid X2):
- W ∝ ρ/(1 − ρ) ohne den Faktor 1/μ. Mehr Kapazität senkt die Wartezeit hier nur über die Auslastung, nicht
  zusätzlich über die schnellere Bedienung. Ein M/M/1-Modell mit W = ρ/(μ − λ) ergäbe für den Pflicht-Testwert
  (+5 % Kapazität, ρ₀ = 0,80) −23,8 % statt −20 %; das Modell ist also eher vorsichtig.
- Ein Versorgungspool: ρ₀, Kassenstellen-Bestand und alle Maßnahmen beziehen sich auf die kassenärztliche
  Versorgung (Allgemein- und Fachmedizin gemeinsam), siehe Kopf von `annahmen.yaml`.
- Mehrkosten sind die jährlichen Mehrkosten im Zieljahr (nicht über die Jahre kumuliert) in Prozent der
  nominalen Ausgangsausgaben 2025 ohne Fortschreibung. Zweite Kennzahl: dieselben Mehrkosten in Prozent der
  Ausgaben für die niedergelassene Versorgung (Budgetdienst, Jahr 2024); sie geht nicht in die
  Zielprüfung ein.

Ziel und Zieljahr stehen in `uc2/config/ziel.yaml`. Die Spanne läuft über alle Min/Max-Ecken der beteiligten
A-Annahmen; gerechnet wird ungerundet, gerundet wird nur in der Ausgabe (`ergebnis`).
"""

from __future__ import annotations

import itertools
import math
from collections.abc import Collection, Mapping, Sequence
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Literal

import yaml

from uc2 import pfade

TOLERANZ = 1e-9
"""Gleitkomma-Toleranz der Zielprüfung, damit exakt −20 % als erreicht zählt."""
MAX_SPANNEN_ANNAHMEN = 16
"""Obergrenze für die vollständige Eckenrechnung (2ⁿ Ecken)."""
RHO0 = "rho0"
AUSGANGSAUSGABEN = "ausgangsausgaben"
BASIS_NIEDERGELASSEN = "basis_niedergelassen"
POSITIVE_ANNAHMEN = (AUSGANGSAUSGABEN, BASIS_NIEDERGELASSEN)
HINWEIS = "Zahlen aus dem Experten, kein Sprachmodell"

Wirkungsart = Literal["kapazitaet", "nachfrage"]
Zielergebnis = Literal["erfüllt", "nicht erfüllt", "offen"]

SCHLUESSEL_REGISTER = frozenset({"version", "annahmen"})
SCHLUESSEL_ANNAHME = frozenset(
    {"id", "symbol", "beschreibung", "min", "modus", "max", "einheit", "jahr", "typ", "quelle"}
)
SCHLUESSEL_KATALOG = frozenset({"version", "massnahmen"})
SCHLUESSEL_MASSNAHME = frozenset(
    {
        "id",
        "name",
        "wirkt_auf",
        "einheit",
        "max_umfang",
        "wirkung",
        "kosten",
        "umsetzungspfad",
        "wirkungspfad",
        "quelle",
    }
)
SCHLUESSEL_FORMEL = frozenset({"skala", "faktoren", "teiler"})
SCHLUESSEL_ZIEL = frozenset(
    {"version", "wartezeit_aenderung_hoechstens", "kosten_aenderung_hoechstens", "zieljahr", "quelle"}
)
SCHLUESSEL_PAKET = frozenset({"beschreibung", "massnahmen", "annahmen"})
SCHLUESSEL_PAKET_MASSNAHME = frozenset({"id", "umfang"})
SCHLUESSEL_SPANNE = frozenset({"min", "modus", "max"})


@dataclass(frozen=True)
class Annahme:
    id: str
    beschreibung: str
    min: float
    modus: float
    max: float
    einheit: str
    typ: str
    quelle: str
    symbol: str = ""
    jahr: int | None = None
    ueberschrieben: bool = False

    @property
    def hat_spanne(self) -> bool:
        return self.typ == "A" and self.min < self.max

    @property
    def anzeige(self) -> str:
        return self.symbol or self.id


@dataclass(frozen=True)
class Ziel:
    wartezeit: float
    """Wartezeitänderung höchstens (Anteil, z. B. −0,20)."""
    kosten: float
    """Mehrkosten höchstens (Anteil der Ausgangsausgaben, z. B. 0,05)."""
    zieljahr: int
    quelle: str


@dataclass(frozen=True)
class Formel:
    skala: float
    faktoren: tuple[str, ...]
    teiler: tuple[str, ...]

    def wert(self, umfang: float, werte: Mapping[str, float]) -> float:
        zaehler = umfang * self.skala * math.prod(werte[f] for f in self.faktoren)
        return zaehler / math.prod(werte[t] for t in self.teiler)

    @property
    def annahmen(self) -> tuple[str, ...]:
        return self.faktoren + self.teiler


@dataclass(frozen=True)
class Massnahme:
    id: str
    name: str
    wirkt_auf: Wirkungsart
    einheit: str
    max_umfang: float
    wirkung: Formel
    kosten: Formel
    umsetzungspfad: tuple[float, ...]
    wirkungspfad: tuple[float, ...]
    quelle: str


@dataclass(frozen=True)
class Paket:
    name: str
    beschreibung: str
    massnahmen: tuple[tuple[Massnahme, float], ...]
    annahmen: Mapping[str, Annahme]
    ziel: Ziel

    def beteiligte_annahmen(self) -> tuple[str, ...]:
        """ρ₀ und Kostenbasen zuerst, dann die Annahmen der Maßnahmen in Paketreihenfolge."""
        ids: list[str] = [RHO0, AUSGANGSAUSGABEN, BASIS_NIEDERGELASSEN]
        for massnahme, _ in self.massnahmen:
            for aid in massnahme.wirkung.annahmen + massnahme.kosten.annahmen:
                if aid not in ids:
                    ids.append(aid)
        return tuple(ids)

    def modus_werte(self) -> dict[str, float]:
        return {aid: self.annahmen[aid].modus for aid in self.beteiligte_annahmen()}


@dataclass(frozen=True)
class Punkt:
    """Ergebnis einer Rechnung für einen Satz Annahmenwerte in einem Jahr (ungerundet)."""

    rho0: float
    rho1: float
    wartezeit: float
    kosten_mio_eur: float
    kosten_anteil: float
    kosten_anteil_niedergelassen: float
    wirkungen: tuple[float, ...]
    kosten_je_massnahme: tuple[float, ...]


def erreicht(punkt: Punkt, ziel: Ziel) -> bool:
    return punkt.wartezeit <= ziel.wartezeit + TOLERANZ and punkt.kosten_anteil <= ziel.kosten + TOLERANZ


# --- Laden und Prüfen ---------------------------------------------------------------------------------


def _lies_yaml(pfad: Path) -> dict[str, Any]:
    with pfad.open(encoding="utf-8") as datei:
        inhalt = yaml.safe_load(datei)
    if not isinstance(inhalt, dict):
        raise ValueError(f"{pfad.name}: erwartet eine Zuordnung auf oberster Ebene")
    return inhalt


def _pruefe_schluessel(eintrag: Mapping[str, Any], erlaubt: Collection[str], wo: str) -> None:
    fremd = sorted(str(k) for k in eintrag if k not in erlaubt)
    if fremd:
        raise ValueError(
            f"{wo}: unbekannte(s) Feld(er) {', '.join(fremd)} (erlaubt: {', '.join(sorted(erlaubt))})"
        )


def _zahl(wert: object, wo: str) -> float:
    if isinstance(wert, bool) or not isinstance(wert, int | float):
        raise ValueError(f"{wo}: Zahl erwartet, gefunden {wert!r}")
    if not math.isfinite(wert):
        raise ValueError(f"{wo}: endliche Zahl erwartet")
    return float(wert)


def _text(eintrag: Mapping[str, Any], feld: str, wo: str) -> str:
    wert = eintrag.get(feld)
    if not isinstance(wert, str) or not wert.strip():
        raise ValueError(f"{wo}: Feld `{feld}` fehlt oder ist leer")
    return wert.strip()


def _spanne(roh: Mapping[str, Any], wo: str) -> tuple[float, float, float]:
    lo, mo, hi = (_zahl(roh.get(feld), f"{wo}.{feld}") for feld in ("min", "modus", "max"))
    if not lo <= mo <= hi:
        raise ValueError(f"{wo}: erwartet min ≤ modus ≤ max, gefunden {(lo, mo, hi)}")
    return lo, mo, hi


def _pruefe_werte(a: Annahme) -> None:
    """Wertebereiche, die eine Division durch null oder unsinnige Wirkungen ausschließen."""
    if a.min < 0:
        raise ValueError(f"{a.id}: Werte müssen ≥ 0 sein, gefunden min {a.min}")
    if a.einheit == "Anteil" and a.max > 1:
        raise ValueError(f"{a.id}: Anteil muss ≤ 1 sein, gefunden max {a.max}")
    if a.id == RHO0 and not (a.min > 0 and a.max < 1):
        raise ValueError(f"{a.id}: Auslastung muss zwischen 0 und 1 liegen (ausschließlich)")
    if a.id in POSITIVE_ANNAHMEN and a.min <= 0:
        raise ValueError(f"{a.id}: Kostenbasis muss > 0 sein")


def lade_annahmen(pfad: Path | None = None) -> dict[str, Annahme]:
    pfad = pfad or pfade.CONFIG / "annahmen.yaml"
    datei = _lies_yaml(pfad)
    _pruefe_schluessel(datei, SCHLUESSEL_REGISTER, pfad.name)
    roh = datei.get("annahmen")
    if not isinstance(roh, list):
        raise ValueError(f"{pfad.name}: Liste `annahmen` fehlt")
    annahmen: dict[str, Annahme] = {}
    for eintrag in roh:
        if not isinstance(eintrag, dict):
            raise ValueError(f"{pfad.name}: Annahme ist keine Zuordnung: {eintrag!r}")
        aid = _text(eintrag, "id", pfad.name)
        _pruefe_schluessel(eintrag, SCHLUESSEL_ANNAHME, f"{pfad.name}:{aid}")
        if aid in annahmen:
            raise ValueError(f"{pfad.name}: Annahme `{aid}` doppelt")
        typ = _text(eintrag, "typ", aid)
        if typ not in ("B", "D", "A"):
            raise ValueError(f"{aid}: Typ muss B, D oder A sein, gefunden {typ!r}")
        jahr = eintrag.get("jahr")
        if jahr is not None and (isinstance(jahr, bool) or not isinstance(jahr, int)):
            raise ValueError(f"{aid}.jahr: ganze Zahl erwartet, gefunden {jahr!r}")
        lo, mo, hi = _spanne(eintrag, aid)
        annahme = Annahme(
            id=aid,
            beschreibung=_text(eintrag, "beschreibung", aid),
            min=lo,
            modus=mo,
            max=hi,
            einheit=_text(eintrag, "einheit", aid),
            typ=typ,
            quelle=_text(eintrag, "quelle", aid),
            symbol=str(eintrag.get("symbol") or ""),
            jahr=jahr,
        )
        _pruefe_werte(annahme)
        annahmen[aid] = annahme
    for pflicht in (RHO0, *POSITIVE_ANNAHMEN):
        if pflicht not in annahmen:
            raise ValueError(f"{pfad.name}: Pflichtannahme `{pflicht}` fehlt")
    return annahmen


def lade_ziel(pfad: Path | None = None) -> Ziel:
    pfad = pfad or pfade.CONFIG / "ziel.yaml"
    roh = _lies_yaml(pfad)
    _pruefe_schluessel(roh, SCHLUESSEL_ZIEL, pfad.name)
    wartezeit = _zahl(
        roh.get("wartezeit_aenderung_hoechstens"), f"{pfad.name}.wartezeit_aenderung_hoechstens"
    )
    kosten = _zahl(roh.get("kosten_aenderung_hoechstens"), f"{pfad.name}.kosten_aenderung_hoechstens")
    zieljahr = roh.get("zieljahr")
    if not -1 < wartezeit <= 0:
        raise ValueError(f"{pfad.name}: Wartezeitziel muss zwischen −1 und 0 liegen")
    if kosten < 0:
        raise ValueError(f"{pfad.name}: Kostenziel muss ≥ 0 sein")
    if isinstance(zieljahr, bool) or not isinstance(zieljahr, int) or not 1 <= zieljahr <= 20:
        raise ValueError(f"{pfad.name}.zieljahr: ganze Zahl von 1 bis 20 erwartet")
    return Ziel(wartezeit, kosten, zieljahr, _text(roh, "quelle", pfad.name))


def _formel(roh: object, wo: str, annahmen: Mapping[str, Annahme]) -> Formel:
    if not isinstance(roh, dict):
        raise ValueError(f"{wo}: Formel fehlt")
    _pruefe_schluessel(roh, SCHLUESSEL_FORMEL, wo)
    listen: dict[str, tuple[str, ...]] = {}
    for feld in ("faktoren", "teiler"):
        ids = roh.get(feld, [])
        if not isinstance(ids, list) or not all(isinstance(i, str) for i in ids):
            raise ValueError(f"{wo}.{feld}: Liste von Annahmen-IDs erwartet")
        for aid in ids:
            if aid not in annahmen:
                raise ValueError(f"{wo}.{feld}: unbekannte Annahme `{aid}`")
        listen[feld] = tuple(ids)
    skala = _zahl(roh.get("skala"), f"{wo}.skala")
    if skala < 0:
        raise ValueError(f"{wo}.skala: muss ≥ 0 sein")
    formel = Formel(skala=skala, **listen)
    _pruefe_teiler(formel, annahmen, wo)
    return formel


def _pruefe_teiler(formel: Formel, annahmen: Mapping[str, Annahme], wo: str) -> None:
    for aid in formel.teiler:
        if annahmen[aid].min <= 0:
            raise ValueError(f"{wo}.teiler: Annahme `{aid}` muss > 0 sein, gefunden min {annahmen[aid].min}")


def _pfad(roh: object, wo: str, jahre: int) -> tuple[float, ...]:
    if not isinstance(roh, list) or len(roh) != jahre:
        raise ValueError(f"{wo}: {jahre} Jahresanteile erwartet (Zieljahr laut ziel.yaml)")
    werte = tuple(_zahl(w, wo) for w in roh)
    if any(not 0.0 <= w <= 1.0 for w in werte) or list(werte) != sorted(werte):
        raise ValueError(f"{wo}: kumulierte Anteile zwischen 0 und 1, nicht fallend")
    return werte


def lade_massnahmen(
    annahmen: Mapping[str, Annahme], ziel: Ziel, pfad: Path | None = None
) -> dict[str, Massnahme]:
    pfad = pfad or pfade.CONFIG / "massnahmen.yaml"
    datei = _lies_yaml(pfad)
    _pruefe_schluessel(datei, SCHLUESSEL_KATALOG, pfad.name)
    roh = datei.get("massnahmen")
    if not isinstance(roh, list):
        raise ValueError(f"{pfad.name}: Liste `massnahmen` fehlt")
    katalog: dict[str, Massnahme] = {}
    for eintrag in roh:
        if not isinstance(eintrag, dict):
            raise ValueError(f"{pfad.name}: Maßnahme ist keine Zuordnung: {eintrag!r}")
        mid = _text(eintrag, "id", pfad.name)
        _pruefe_schluessel(eintrag, SCHLUESSEL_MASSNAHME, f"{pfad.name}:{mid}")
        wirkt_auf = eintrag.get("wirkt_auf")
        if wirkt_auf not in ("kapazitaet", "nachfrage"):
            raise ValueError(f"{mid}: `wirkt_auf` muss kapazitaet oder nachfrage sein")
        max_umfang = _zahl(eintrag.get("max_umfang"), f"{mid}.max_umfang")
        if max_umfang <= 0:
            raise ValueError(f"{mid}.max_umfang: muss > 0 sein")
        umsetzung = _pfad(eintrag.get("umsetzungspfad"), f"{mid}.umsetzungspfad", ziel.zieljahr)
        wirkungspfad = eintrag.get("wirkungspfad")
        katalog[mid] = Massnahme(
            id=mid,
            name=_text(eintrag, "name", mid),
            wirkt_auf="kapazitaet" if wirkt_auf == "kapazitaet" else "nachfrage",
            einheit=_text(eintrag, "einheit", mid),
            max_umfang=max_umfang,
            wirkung=_formel(eintrag.get("wirkung"), f"{mid}.wirkung", annahmen),
            kosten=_formel(eintrag.get("kosten"), f"{mid}.kosten", annahmen),
            umsetzungspfad=umsetzung,
            wirkungspfad=umsetzung
            if wirkungspfad is None
            else _pfad(wirkungspfad, f"{mid}.wirkungspfad", ziel.zieljahr),
            quelle=_text(eintrag, "quelle", mid),
        )
    return katalog


def _zahl_kurz(wert: float) -> str:
    return f"{wert:g}".replace(".", ",")


def lade_paket(
    pfad: Path,
    annahmen: Mapping[str, Annahme] | None = None,
    katalog: Mapping[str, Massnahme] | None = None,
    ziel: Ziel | None = None,
) -> Paket:
    """Paketdatei lesen: `massnahmen: [{id, umfang}]`, optional `annahmen: {id: {min, modus, max}}`.

    Überschreiben darf ein Paket nur A-Annahmen. B (belegt) und D (abgeleitet) sind Daten; ein Paket, das
    sie ändert, würde Ergebnisse unter einer Quelle zeigen, die den Wert nicht trägt.
    """
    ziel = ziel or lade_ziel()
    annahmen = dict(annahmen if annahmen is not None else lade_annahmen())
    katalog = katalog if katalog is not None else lade_massnahmen(annahmen, ziel)
    roh = _lies_yaml(pfad)
    _pruefe_schluessel(roh, SCHLUESSEL_PAKET, pfad.name)
    liste = roh.get("massnahmen")
    if not isinstance(liste, list) or not liste:
        raise ValueError(f"{pfad.name}: Liste `massnahmen` fehlt oder ist leer")
    gewaehlt: list[tuple[Massnahme, float]] = []
    for eintrag in liste:
        if not isinstance(eintrag, dict):
            raise ValueError(f"{pfad.name}: Maßnahme ist keine Zuordnung: {eintrag!r}")
        mid = _text(eintrag, "id", pfad.name)
        _pruefe_schluessel(eintrag, SCHLUESSEL_PAKET_MASSNAHME, f"{pfad.name}:{mid}")
        if mid not in katalog:
            raise ValueError(f"{pfad.name}: unbekannte Maßnahme `{mid}` (Katalog: {', '.join(katalog)})")
        if any(m.id == mid for m, _ in gewaehlt):
            raise ValueError(f"{pfad.name}: Maßnahme `{mid}` doppelt")
        umfang = _zahl(eintrag.get("umfang"), f"{mid}.umfang")
        if not 0 <= umfang <= katalog[mid].max_umfang:
            raise ValueError(
                f"{mid}.umfang: muss zwischen 0 und {_zahl_kurz(katalog[mid].max_umfang)} liegen "
                f"({katalog[mid].einheit}), gefunden {_zahl_kurz(umfang)}"
            )
        gewaehlt.append((katalog[mid], umfang))
    ueber = roh.get("annahmen") or {}
    if not isinstance(ueber, dict):
        raise ValueError(f"{pfad.name}: `annahmen` muss eine Zuordnung sein")
    for aid, werte in ueber.items():
        if aid not in annahmen:
            raise ValueError(f"{pfad.name}: unbekannte Annahme `{aid}`")
        alt = annahmen[aid]
        if alt.typ != "A":
            raise ValueError(
                f"{pfad.name}: `{aid}` ist Typ {alt.typ} (Daten) und darf nicht überschrieben werden"
            )
        if not isinstance(werte, dict):
            raise ValueError(f"{pfad.name}: `{aid}` braucht min, modus, max")
        _pruefe_schluessel(werte, SCHLUESSEL_SPANNE, f"{pfad.name}:{aid}")
        lo, mo, hi = _spanne(werte, f"{pfad.name}:{aid}")
        register = f"{_zahl_kurz(alt.min)} / {_zahl_kurz(alt.modus)} / {_zahl_kurz(alt.max)}"
        neu = replace(
            alt,
            min=lo,
            modus=mo,
            max=hi,
            quelle=f"Paket {pfad.stem} (Registerwert {register}: {alt.quelle})",
            ueberschrieben=True,
        )
        _pruefe_werte(neu)
        annahmen[aid] = neu
    for m, _ in gewaehlt:
        _pruefe_teiler(m.wirkung, annahmen, f"{m.id}.wirkung")
        _pruefe_teiler(m.kosten, annahmen, f"{m.id}.kosten")
    beschreibung = roh.get("beschreibung")
    return Paket(
        name=pfad.stem,
        beschreibung=beschreibung.strip() if isinstance(beschreibung, str) else "",
        massnahmen=tuple(gewaehlt),
        annahmen=annahmen,
        ziel=ziel,
    )


# --- Rechnen ------------------------------------------------------------------------------------------


def wartezeit_faktor(rho: float) -> float:
    """W(ρ) = ρ/(1 − ρ), relative Wartezeit bei Auslastung ρ (ohne Faktor 1/μ, siehe Modulkopf)."""
    if not 0.0 < rho < 1.0:
        raise ValueError(f"Auslastung muss zwischen 0 und 1 liegen, gefunden {rho}")
    return rho / (1.0 - rho)


def rechne(paket: Paket, werte: Mapping[str, float], jahr: int | None = None) -> Punkt:
    """Wartezeit- und Kostenänderung im Jahr `jahr` (Standard: Zieljahr) für einen Satz Annahmenwerte."""
    jahr = paket.ziel.zieljahr if jahr is None else jahr
    if not 1 <= jahr <= paket.ziel.zieljahr:
        raise ValueError(f"Jahr muss zwischen 1 und {paket.ziel.zieljahr} liegen")
    kapazitaet = 1.0
    nachfrage = 1.0
    wirkungen: list[float] = []
    kosten: list[float] = []
    for massnahme, umfang in paket.massnahmen:
        delta = massnahme.wirkung.wert(umfang * massnahme.wirkungspfad[jahr - 1], werte)
        if massnahme.wirkt_auf == "kapazitaet":
            kapazitaet *= 1.0 + delta
        else:
            nachfrage *= 1.0 - delta
        wirkungen.append(delta)
        kosten.append(massnahme.kosten.wert(umfang * massnahme.umsetzungspfad[jahr - 1], werte))
    if nachfrage <= 0.0:
        raise ValueError("Nachfrageminderung von 100 % oder mehr: Paket ist nicht plausibel")
    rho0 = werte[RHO0]
    rho1 = rho0 * nachfrage / kapazitaet
    summe = math.fsum(kosten)
    return Punkt(
        rho0=rho0,
        rho1=rho1,
        wartezeit=wartezeit_faktor(rho1) / wartezeit_faktor(rho0) - 1.0,
        kosten_mio_eur=summe,
        kosten_anteil=summe / werte[AUSGANGSAUSGABEN],
        kosten_anteil_niedergelassen=summe / werte[BASIS_NIEDERGELASSEN],
        wirkungen=tuple(wirkungen),
        kosten_je_massnahme=tuple(kosten),
    )


def spannen_annahmen(paket: Paket) -> tuple[str, ...]:
    return tuple(aid for aid in paket.beteiligte_annahmen() if paket.annahmen[aid].hat_spanne)


def ecken(paket: Paket) -> list[Punkt]:
    """Alle 2ⁿ Min/Max-Ecken der beteiligten A-Annahmen im Zieljahr (übrige Annahmen beim Modus)."""
    ids = spannen_annahmen(paket)
    if len(ids) > MAX_SPANNEN_ANNAHMEN:
        raise ValueError(
            f"{len(ids)} A-Annahmen mit Spanne; vollständige Eckenrechnung nur bis {MAX_SPANNEN_ANNAHMEN}"
        )
    basis = paket.modus_werte()
    punkte: list[Punkt] = []
    for wahl in itertools.product((False, True), repeat=len(ids)):
        werte = dict(basis)
        for aid, oben in zip(ids, wahl, strict=True):
            annahme = paket.annahmen[aid]
            werte[aid] = annahme.max if oben else annahme.min
        punkte.append(rechne(paket, werte))
    return punkte


def zielpruefung(punkte: Sequence[Punkt], ziel: Ziel) -> Zielergebnis:
    anzahl = sum(erreicht(p, ziel) for p in punkte)
    if anzahl == len(punkte):
        return "erfüllt"
    if anzahl == 0:
        return "nicht erfüllt"
    return "offen"


@dataclass(frozen=True)
class Einfluss:
    """Eine A-Annahme auf Min bzw. Max, alle übrigen beim Modus."""

    annahme: Annahme
    bei_min: Punkt
    bei_max: Punkt
    kippt: bool

    @property
    def ausschlag(self) -> float:
        return max(
            abs(self.bei_max.wartezeit - self.bei_min.wartezeit),
            abs(self.bei_max.kosten_anteil - self.bei_min.kosten_anteil),
        )


def einfluesse(paket: Paket, modus: Punkt) -> list[Einfluss]:
    """Je A-Annahme Min und Max bei Modus der übrigen; sortiert: kippend zuerst, dann nach Ausschlag."""
    basis = paket.modus_werte()
    ziel = paket.ziel
    im_modus = erreicht(modus, ziel)
    liste: list[Einfluss] = []
    for aid in spannen_annahmen(paket):
        annahme = paket.annahmen[aid]
        bei_min = rechne(paket, {**basis, aid: annahme.min})
        bei_max = rechne(paket, {**basis, aid: annahme.max})
        kippt = im_modus != erreicht(bei_min, ziel) or im_modus != erreicht(bei_max, ziel)
        liste.append(Einfluss(annahme, bei_min, bei_max, kippt))
    liste.sort(key=lambda e: (not e.kippt, -e.ausschlag, e.annahme.id))
    return liste


# --- Ausgabe ------------------------------------------------------------------------------------------


def _r(wert: float, stellen: int) -> float:
    gerundet = round(wert, stellen)
    return 0.0 if gerundet == 0 else gerundet  # kein „-0.0“ in der Ausgabe


def _prozent(wert: float) -> float:
    return _r(wert * 100.0, 2)


def zahl_de(wert: float, stellen: int) -> str:
    """Zahl deutsch formatiert (Tausenderpunkt, Dezimalkomma, echtes Minuszeichen)."""
    text = f"{abs(wert):,.{stellen}f}".replace(",", " ").replace(".", ",").replace(" ", ".")
    return ("−" if round(wert, stellen) < 0 else "") + text


def entscheidend_text(einfluss: Einfluss, ziel: Ziel) -> str:
    a = einfluss.annahme
    stellen = 2 if abs(a.max) < 10 else 0

    def teil(label: str, wert: float, p: Punkt) -> str:
        return (
            f"bei {label} {zahl_de(wert, stellen)} Wartezeit {zahl_de(p.wartezeit * 100, 2)} %, "
            f"Kosten {zahl_de(p.kosten_anteil * 100, 2)} %, "
            f"{'Ziel erreicht' if erreicht(p, ziel) else 'Ziel verfehlt'}"
        )

    return (
        f"{a.anzeige} ({a.beschreibung}, Typ {a.typ}): {teil('Min', a.min, einfluss.bei_min)}; "
        f"{teil('Max', a.max, einfluss.bei_max)}"
    )


def _punkt_json(p: Punkt, ziel: Ziel) -> dict[str, float | bool]:
    return {
        "rho1": _r(p.rho1, 4),
        "wartezeit_aenderung_prozent": _prozent(p.wartezeit),
        "kosten_aenderung_prozent": _prozent(p.kosten_anteil),
        "ziel_erreicht": erreicht(p, ziel),
    }


def _basis_json(a: Annahme) -> dict[str, Any]:
    return {"wert": _r(a.modus, 1), "einheit": a.einheit, "jahr": a.jahr, "quelle": a.quelle}


def ergebnis(paket: Paket) -> dict[str, Any]:
    """Vollständige, gerundete Ausgabe als JSON-fähige Struktur (feste Schlüsselreihenfolge)."""
    ziel = paket.ziel
    werte = paket.modus_werte()
    modus = rechne(paket, werte)
    alle = ecken(paket)
    pruefung = zielpruefung(alle, ziel)
    liste = einfluesse(paket, modus)
    kippend = [e for e in liste if e.kippt]
    entscheidend = kippend[0] if kippend else None
    if entscheidend is not None:
        satz = f"entscheidend: {entscheidend_text(entscheidend, ziel)}"
    elif liste:
        satz = (
            "entscheidend: keine einzelne Annahme kippt die Zielprüfung; größter Ausschlag: "
            f"{entscheidend_text(liste[0], ziel)}"
        )
    else:
        satz = "entscheidend: keine A-Annahme mit Spanne beteiligt"

    def spanne(attr: str, stellen: int, prozent: bool) -> dict[str, float]:
        def fmt(x: float) -> float:
            return _prozent(x) if prozent else _r(x, stellen)

        reihe = [getattr(p, attr) for p in alle]
        return {"modus": fmt(getattr(modus, attr)), "min": fmt(min(reihe)), "max": fmt(max(reihe))}

    massnahmen = []
    for i, (m, umfang) in enumerate(paket.massnahmen):
        massnahmen.append(
            {
                "id": m.id,
                "name": m.name,
                "umfang": _r(umfang, 4),
                "einheit": m.einheit,
                "wirkt_auf": m.wirkt_auf,
                "wirkung_prozent": _prozent(modus.wirkungen[i]),
                "mehrkosten_mio_eur": _r(modus.kosten_je_massnahme[i], 1),
            }
        )
    jahrespfad = []
    for jahr in range(1, ziel.zieljahr + 1):
        p = rechne(paket, werte, jahr)
        jahrespfad.append(
            {
                "jahr": jahr,
                "rho1": _r(p.rho1, 4),
                "wartezeit_aenderung_prozent": _prozent(p.wartezeit),
                "mehrkosten_mio_eur": _r(p.kosten_mio_eur, 1),
                "kosten_aenderung_prozent": _prozent(p.kosten_anteil),
            }
        )
    annahmen = []
    for aid in paket.beteiligte_annahmen():
        a = paket.annahmen[aid]
        annahmen.append(
            {
                "id": a.id,
                "symbol": a.symbol or a.id,
                "beschreibung": a.beschreibung,
                "min": _r(a.min, 6),
                "modus": _r(a.modus, 6),
                "max": _r(a.max, 6),
                "einheit": a.einheit,
                "typ": a.typ,
                "jahr": a.jahr,
                "quelle": a.quelle,
                "in_spanne": a.hat_spanne,
                "ueberschrieben": a.ueberschrieben,
            }
        )
    return {
        "hinweis": HINWEIS,
        "paket": paket.name,
        "beschreibung": paket.beschreibung,
        "zieljahr": ziel.zieljahr,
        "ziel": {
            "wartezeit_aenderung_prozent_hoechstens": _prozent(ziel.wartezeit),
            "kosten_aenderung_prozent_hoechstens": _prozent(ziel.kosten),
            "zieljahr": ziel.zieljahr,
            "quelle": ziel.quelle,
        },
        "ausgangsausgaben": _basis_json(paket.annahmen[AUSGANGSAUSGABEN]),
        "basis_niedergelassen": _basis_json(paket.annahmen[BASIS_NIEDERGELASSEN]),
        "massnahmen": massnahmen,
        "kennzahlen": {
            "rho0": spanne("rho0", 4, prozent=False),
            "rho1": spanne("rho1", 4, prozent=False),
            "wartezeit_aenderung_prozent": spanne("wartezeit", 2, prozent=True),
            "mehrkosten_mio_eur": spanne("kosten_mio_eur", 1, prozent=False),
            "kosten_aenderung_prozent": spanne("kosten_anteil", 2, prozent=True),
            "kosten_aenderung_niedergelassen_prozent": spanne(
                "kosten_anteil_niedergelassen", 2, prozent=True
            ),
        },
        "zielpruefung": {
            "ergebnis": pruefung,
            "modus_erreicht": erreicht(modus, ziel),
            "ecken": len(alle),
            "ecken_erreicht": sum(erreicht(p, ziel) for p in alle),
            "annahmen_in_spanne": list(spannen_annahmen(paket)),
        },
        "entscheidend": {
            "text": satz,
            "annahme": entscheidend.annahme.id if entscheidend else None,
            "einfluesse": [
                {
                    "annahme": e.annahme.id,
                    "kippt": e.kippt,
                    "ausschlag_prozentpunkte": _prozent(e.ausschlag),
                    "min": {"wert": _r(e.annahme.min, 6), **_punkt_json(e.bei_min, ziel)},
                    "max": {"wert": _r(e.annahme.max, 6), **_punkt_json(e.bei_max, ziel)},
                }
                for e in liste
            ],
        },
        "jahrespfad": jahrespfad,
        "annahmen": annahmen,
    }
