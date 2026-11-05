"""Deterministisches Wirkungsmodell für Wartezeit und Kosten (#42, PRD S4).

Kein Sprachmodell, keine Zufallszahlen. Die Wartezeit folgt der Auslastung, W(ρ) = ρ/(1 − ρ). Maßnahmen
wirken als Kapazitätszuwachs Δμ oder Nachfrageminderung Δλ, mehrere Maßnahmen multiplikativ:

    ρ₁ = ρ₀ · Π(1 − Δλᵢ) / Π(1 + Δμᵢ),   Wartezeitänderung = W(ρ₁)/W(ρ₀) − 1.

Mehrkosten sind die Summe der Maßnahmenkosten im Zieljahr in Prozent der Ausgangsausgaben. Die Spanne
läuft über alle Min/Max-Ecken der beteiligten A-Annahmen; gerechnet wird ungerundet, gerundet wird nur
in der Ausgabe (`ergebnis`).
"""

from __future__ import annotations

import itertools
import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Literal

import yaml

from uc2 import pfade

ZIEL_WARTEZEIT = -0.20
"""Zielprüfung: Wartezeitänderung höchstens −20 %."""
ZIEL_KOSTEN = 0.05
"""Zielprüfung: Mehrkosten höchstens +5 % der Ausgangsausgaben."""
TOLERANZ = 1e-9
"""Gleitkomma-Toleranz der Zielprüfung, damit exakt −20 % als erreicht zählt."""
JAHRE = 5
MAX_SPANNEN_ANNAHMEN = 16
"""Obergrenze für die vollständige Eckenrechnung (2ⁿ Ecken)."""
RHO0 = "rho0"
AUSGANGSAUSGABEN = "ausgangsausgaben"
HINWEIS = "Zahlen aus dem Experten, kein Sprachmodell"

Wirkungsart = Literal["kapazitaet", "nachfrage"]
Zielergebnis = Literal["erfüllt", "nicht erfüllt", "offen"]


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

    def beteiligte_annahmen(self) -> tuple[str, ...]:
        """ρ₀ und Ausgangsausgaben zuerst, dann die Annahmen der Maßnahmen in Paketreihenfolge."""
        ids: list[str] = [RHO0, AUSGANGSAUSGABEN]
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
    wirkungen: tuple[float, ...]
    kosten_je_massnahme: tuple[float, ...]

    @property
    def ziel_erreicht(self) -> bool:
        return self.wartezeit <= ZIEL_WARTEZEIT + TOLERANZ and self.kosten_anteil <= ZIEL_KOSTEN + TOLERANZ


# --- Laden und Prüfen ---------------------------------------------------------------------------------


def _lies_yaml(pfad: Path) -> dict[str, Any]:
    with pfad.open(encoding="utf-8") as datei:
        inhalt = yaml.safe_load(datei)
    if not isinstance(inhalt, dict):
        raise ValueError(f"{pfad.name}: erwartet eine Zuordnung auf oberster Ebene")
    return inhalt


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


def lade_annahmen(pfad: Path | None = None) -> dict[str, Annahme]:
    pfad = pfad or pfade.CONFIG / "annahmen.yaml"
    roh = _lies_yaml(pfad).get("annahmen")
    if not isinstance(roh, list):
        raise ValueError(f"{pfad.name}: Liste `annahmen` fehlt")
    annahmen: dict[str, Annahme] = {}
    for eintrag in roh:
        if not isinstance(eintrag, dict):
            raise ValueError(f"{pfad.name}: Annahme ist keine Zuordnung: {eintrag!r}")
        aid = _text(eintrag, "id", pfad.name)
        if aid in annahmen:
            raise ValueError(f"{pfad.name}: Annahme `{aid}` doppelt")
        typ = _text(eintrag, "typ", aid)
        if typ not in ("B", "D", "A"):
            raise ValueError(f"{aid}: Typ muss B, D oder A sein, gefunden {typ!r}")
        lo, mo, hi = _spanne(eintrag, aid)
        jahr = eintrag.get("jahr")
        annahmen[aid] = Annahme(
            id=aid,
            beschreibung=_text(eintrag, "beschreibung", aid),
            min=lo,
            modus=mo,
            max=hi,
            einheit=_text(eintrag, "einheit", aid),
            typ=typ,
            quelle=_text(eintrag, "quelle", aid),
            symbol=str(eintrag.get("symbol") or ""),
            jahr=int(jahr) if isinstance(jahr, int) else None,
        )
    for pflicht in (RHO0, AUSGANGSAUSGABEN):
        if pflicht not in annahmen:
            raise ValueError(f"{pfad.name}: Pflichtannahme `{pflicht}` fehlt")
    return annahmen


def _formel(roh: object, wo: str, annahmen: Mapping[str, Annahme]) -> Formel:
    if not isinstance(roh, dict):
        raise ValueError(f"{wo}: Formel fehlt")
    listen: dict[str, tuple[str, ...]] = {}
    for feld in ("faktoren", "teiler"):
        ids = roh.get(feld, [])
        if not isinstance(ids, list) or not all(isinstance(i, str) for i in ids):
            raise ValueError(f"{wo}.{feld}: Liste von Annahmen-IDs erwartet")
        for aid in ids:
            if aid not in annahmen:
                raise ValueError(f"{wo}.{feld}: unbekannte Annahme `{aid}`")
        listen[feld] = tuple(ids)
    return Formel(skala=_zahl(roh.get("skala"), f"{wo}.skala"), **listen)


def _pfad(roh: object, wo: str) -> tuple[float, ...]:
    if not isinstance(roh, list) or len(roh) != JAHRE:
        raise ValueError(f"{wo}: {JAHRE} Jahresanteile erwartet")
    werte = tuple(_zahl(w, wo) for w in roh)
    if any(not 0.0 <= w <= 1.0 for w in werte) or list(werte) != sorted(werte):
        raise ValueError(f"{wo}: kumulierte Anteile zwischen 0 und 1, nicht fallend")
    return werte


def lade_massnahmen(annahmen: Mapping[str, Annahme], pfad: Path | None = None) -> dict[str, Massnahme]:
    pfad = pfad or pfade.CONFIG / "massnahmen.yaml"
    roh = _lies_yaml(pfad).get("massnahmen")
    if not isinstance(roh, list):
        raise ValueError(f"{pfad.name}: Liste `massnahmen` fehlt")
    katalog: dict[str, Massnahme] = {}
    for eintrag in roh:
        if not isinstance(eintrag, dict):
            raise ValueError(f"{pfad.name}: Maßnahme ist keine Zuordnung: {eintrag!r}")
        mid = _text(eintrag, "id", pfad.name)
        wirkt_auf = eintrag.get("wirkt_auf")
        if wirkt_auf not in ("kapazitaet", "nachfrage"):
            raise ValueError(f"{mid}: `wirkt_auf` muss kapazitaet oder nachfrage sein")
        umsetzung = _pfad(eintrag.get("umsetzungspfad"), f"{mid}.umsetzungspfad")
        wirkungspfad = eintrag.get("wirkungspfad")
        katalog[mid] = Massnahme(
            id=mid,
            name=_text(eintrag, "name", mid),
            wirkt_auf="kapazitaet" if wirkt_auf == "kapazitaet" else "nachfrage",
            einheit=_text(eintrag, "einheit", mid),
            wirkung=_formel(eintrag.get("wirkung"), f"{mid}.wirkung", annahmen),
            kosten=_formel(eintrag.get("kosten"), f"{mid}.kosten", annahmen),
            umsetzungspfad=umsetzung,
            wirkungspfad=umsetzung if wirkungspfad is None else _pfad(wirkungspfad, f"{mid}.wirkungspfad"),
            quelle=_text(eintrag, "quelle", mid),
        )
    return katalog


def lade_paket(
    pfad: Path,
    annahmen: Mapping[str, Annahme] | None = None,
    katalog: Mapping[str, Massnahme] | None = None,
) -> Paket:
    """Paketdatei lesen: `massnahmen: [{id, umfang}]`, optional `annahmen: {id: {min, modus, max}}`."""
    annahmen = dict(annahmen if annahmen is not None else lade_annahmen())
    katalog = katalog if katalog is not None else lade_massnahmen(annahmen)
    roh = _lies_yaml(pfad)
    liste = roh.get("massnahmen")
    if not isinstance(liste, list) or not liste:
        raise ValueError(f"{pfad.name}: Liste `massnahmen` fehlt oder ist leer")
    gewaehlt: list[tuple[Massnahme, float]] = []
    for eintrag in liste:
        if not isinstance(eintrag, dict):
            raise ValueError(f"{pfad.name}: Maßnahme ist keine Zuordnung: {eintrag!r}")
        mid = _text(eintrag, "id", pfad.name)
        if mid not in katalog:
            raise ValueError(f"{pfad.name}: unbekannte Maßnahme `{mid}` (Katalog: {', '.join(katalog)})")
        if any(m.id == mid for m, _ in gewaehlt):
            raise ValueError(f"{pfad.name}: Maßnahme `{mid}` doppelt")
        umfang = _zahl(eintrag.get("umfang"), f"{mid}.umfang")
        if umfang < 0:
            raise ValueError(f"{mid}.umfang: nicht negativ")
        gewaehlt.append((katalog[mid], umfang))
    ueber = roh.get("annahmen") or {}
    if not isinstance(ueber, dict):
        raise ValueError(f"{pfad.name}: `annahmen` muss eine Zuordnung sein")
    for aid, werte in ueber.items():
        if aid not in annahmen:
            raise ValueError(f"{pfad.name}: unbekannte Annahme `{aid}`")
        if not isinstance(werte, dict):
            raise ValueError(f"{pfad.name}: `{aid}` braucht min, modus, max")
        lo, mo, hi = _spanne(werte, f"{pfad.name}:{aid}")
        annahmen[aid] = replace(annahmen[aid], min=lo, modus=mo, max=hi, ueberschrieben=True)
    beschreibung = roh.get("beschreibung")
    return Paket(
        name=pfad.stem,
        beschreibung=beschreibung.strip() if isinstance(beschreibung, str) else "",
        massnahmen=tuple(gewaehlt),
        annahmen=annahmen,
    )


# --- Rechnen ------------------------------------------------------------------------------------------


def wartezeit_faktor(rho: float) -> float:
    """W(ρ) = ρ/(1 − ρ), relative Wartezeit bei Auslastung ρ."""
    if not 0.0 < rho < 1.0:
        raise ValueError(f"Auslastung muss zwischen 0 und 1 liegen, gefunden {rho}")
    return rho / (1.0 - rho)


def rechne(paket: Paket, werte: Mapping[str, float], jahr: int = JAHRE) -> Punkt:
    """Wartezeit- und Kostenänderung im Jahr `jahr` (1 bis 5) für einen Satz Annahmenwerte."""
    if not 1 <= jahr <= JAHRE:
        raise ValueError(f"Jahr muss zwischen 1 und {JAHRE} liegen")
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


def zielpruefung(punkte: Sequence[Punkt]) -> Zielergebnis:
    erreicht = sum(p.ziel_erreicht for p in punkte)
    if erreicht == len(punkte):
        return "erfüllt"
    if erreicht == 0:
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
    liste: list[Einfluss] = []
    for aid in spannen_annahmen(paket):
        annahme = paket.annahmen[aid]
        bei_min = rechne(paket, {**basis, aid: annahme.min})
        bei_max = rechne(paket, {**basis, aid: annahme.max})
        kippt = modus.ziel_erreicht != bei_min.ziel_erreicht or modus.ziel_erreicht != bei_max.ziel_erreicht
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


def _ziel_text(punkt: Punkt) -> str:
    return "Ziel erreicht" if punkt.ziel_erreicht else "Ziel verfehlt"


def entscheidend_text(einfluss: Einfluss) -> str:
    a = einfluss.annahme
    stellen = 2 if abs(a.max) < 10 else 0

    def teil(label: str, wert: float, p: Punkt) -> str:
        return (
            f"bei {label} {zahl_de(wert, stellen)} Wartezeit {zahl_de(p.wartezeit * 100, 1)} %, "
            f"Kosten {zahl_de(p.kosten_anteil * 100, 2)} %, {_ziel_text(p)}"
        )

    return (
        f"{a.anzeige} ({a.beschreibung}, Typ {a.typ}): {teil('Min', a.min, einfluss.bei_min)}; "
        f"{teil('Max', a.max, einfluss.bei_max)}"
    )


def _punkt_json(p: Punkt) -> dict[str, float | bool]:
    return {
        "rho1": _r(p.rho1, 4),
        "wartezeit_aenderung_prozent": _prozent(p.wartezeit),
        "kosten_aenderung_prozent": _prozent(p.kosten_anteil),
        "ziel_erreicht": p.ziel_erreicht,
    }


def ergebnis(paket: Paket) -> dict[str, Any]:
    """Vollständige, gerundete Ausgabe als JSON-fähige Struktur (feste Schlüsselreihenfolge)."""
    werte = paket.modus_werte()
    modus = rechne(paket, werte)
    alle = ecken(paket)
    pruefung = zielpruefung(alle)
    liste = einfluesse(paket, modus)
    kippend = [e for e in liste if e.kippt]
    entscheidend = kippend[0] if kippend else None
    if entscheidend is not None:
        satz = f"entscheidend: {entscheidend_text(entscheidend)}"
    elif liste:
        satz = (
            "entscheidend: keine einzelne Annahme kippt die Zielprüfung; größter Ausschlag: "
            f"{entscheidend_text(liste[0])}"
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
    for jahr in range(1, JAHRE + 1):
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
    ausgang = paket.annahmen[AUSGANGSAUSGABEN]
    return {
        "hinweis": HINWEIS,
        "paket": paket.name,
        "beschreibung": paket.beschreibung,
        "zieljahr": JAHRE,
        "ziel": {
            "wartezeit_aenderung_prozent_hoechstens": _prozent(ZIEL_WARTEZEIT),
            "kosten_aenderung_prozent_hoechstens": _prozent(ZIEL_KOSTEN),
        },
        "ausgangsausgaben": {
            "wert": _r(ausgang.modus, 1),
            "einheit": ausgang.einheit,
            "jahr": ausgang.jahr,
            "quelle": ausgang.quelle,
        },
        "massnahmen": massnahmen,
        "kennzahlen": {
            "rho0": spanne("rho0", 4, prozent=False),
            "rho1": spanne("rho1", 4, prozent=False),
            "wartezeit_aenderung_prozent": spanne("wartezeit", 2, prozent=True),
            "mehrkosten_mio_eur": spanne("kosten_mio_eur", 1, prozent=False),
            "kosten_aenderung_prozent": spanne("kosten_anteil", 2, prozent=True),
        },
        "zielpruefung": {
            "ergebnis": pruefung,
            "modus_erreicht": modus.ziel_erreicht,
            "ecken": len(alle),
            "ecken_erreicht": sum(p.ziel_erreicht for p in alle),
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
                    "min": {"wert": _r(e.annahme.min, 6), **_punkt_json(e.bei_min)},
                    "max": {"wert": _r(e.annahme.max, 6), **_punkt_json(e.bei_max)},
                }
                for e in liste
            ],
        },
        "jahrespfad": jahrespfad,
        "annahmen": annahmen,
    }
