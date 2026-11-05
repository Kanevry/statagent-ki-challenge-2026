"""Deterministischer UC2-Szenario-Mock (Entscheid 1 in #44).

Eine `Provider`-Unterklasse mit Namen `mock`, die nur aus dem Kontextblock der ersten User-Nachricht
antwortet (Rolle, Akteur, Runde, Themen, Beleg-IDs, Experten-Zahlen, Vorrunde). Gleicher Prompt, gleiche
Antwort; Zufall gibt es nicht, Streuung kommt aus sha256 über Akteur und Thema.

- Haltung je Akteur und Thema: Wortbezug des Themas zu Zielen und Prioritäten (dafür) gegen rote Linien,
  Restriktionen und Budgetvorgaben (dagegen), dazu ein fester Streuwert.
- Bewegung: in Runde 2 und 3 rückt ein Teil der Akteure eine Stufe zum Mittel der anderen; ab Runde 4 bleibt
  jeder stehen, so endet der Lauf nach der Regel „Runde ohne Änderung“.
- Rote Linie gegen Mehrkosten (#24, Abnahme 24-1): Ab der Verhandlungsrunde (Runde 3) stellt sich ein Akteur
  mit einer roten Linie gegen Mehrausgaben (`MEHRKOSTEN_LINIE`) gegen jede Maßnahme des Pakets, solange der
  Experte Mehrkosten rechnet, und rückt davon nicht mehr ab. In Runde 1 und 2 bewegt er sich wie alle. So
  steht im Szenario sichtbar eine Minderheit gegen eine Mehrheit.
- Zahlen nur mit Quelle `experte` und nur aus `vom_rechenmodell_berechnet`; in Runde 2 nennt der erste
  Teilnehmer bewusst eine Zahl ohne Quelle, damit die Prüfung `zahl_ohne_beleg` im Szenario sichtbar wird.
- `UC2_MOCK_KAPUTT=<akteur_id>:<runde>` liefert für genau diesen Zug kaputtes JSON, auch bei der Wiederholung.

Eingehängt wird er nur bei Provider `mock` über `einhaengen()`; `zuruecksetzen()` stellt den vorigen
Stand her.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from typing import Any

from plattform.llm import FixtureFehlt  # type: ignore[import-untyped]
from plattform.llm import kern as _kern
from plattform.llm.basis import Provider, Rohantwort  # type: ignore[import-untyped]

from uc2.modelle.kontext import lies_kontext

MODELL = "mock-szenario"
VERSION = "szenario-1"
KAPUTT_ENV = "UC2_MOCK_KAPUTT"
KAPUTTER_TEXT = '{"themen": [{"thema": "kaputt", "haltung": '

MEHRKOSTEN_LINIE = "mehrausgaben"
VERHANDLUNGSRUNDE = 3
"""Ab dieser Runde gilt die rote Linie gegen Mehrkosten (Runde 3 ist die Verhandlung, siehe `lauf`)."""
"""Wortteil einer roten Linie gegen Mehrkosten („keine Mehrausgaben ohne Gegenfinanzierung“)."""

_WORT = re.compile(r"[A-Za-zÄÖÜäöüß]{5,}")
_FUELLWOERTER = frozenset({"gegen", "nicht", "keine", "einer", "einen", "durch", "ueber", "über", "ohne"})


def _streuung(*teile: object, modulo: int) -> int:
    """Fester Streuwert aus sha256 (gleiche Eingabe, gleicher Wert, auch über Prozesse)."""
    schluessel = "|".join(str(t) for t in teile).encode("utf-8")
    return int(hashlib.sha256(schluessel).hexdigest()[:8], 16) % modulo


def _staemme(text: str) -> set[str]:
    return {w.casefold()[:6] for w in _WORT.findall(text) if w.casefold() not in _FUELLWOERTER}


def _bezug(thema_staemme: set[str], saetze: list[str]) -> tuple[int, str | None]:
    """Zahl der Sätze mit Wortbezug zum Thema und der Satz mit dem stärksten Bezug."""
    treffer = 0
    bester: tuple[int, str] | None = None
    for satz in saetze:
        n = len(thema_staemme & _staemme(satz))
        if n:
            treffer += 1
            if bester is None or n > bester[0]:
                bester = (n, satz)
    return treffer, bester[1] if bester else None


def _klemme(wert: float) -> int:
    return max(-2, min(2, round(wert)))


def _zahl_de(wert: float) -> str:
    text = f"{abs(wert):.2f}".replace(".", ",")
    return ("−" if wert < 0 else "") + text


def _thema_staemme(thema: dict[str, Any]) -> set[str]:
    return _staemme(f"{thema.get('titel', '')} {thema.get('beschreibung', '')}")


def grundhaltung(akteur: dict[str, Any], thema: dict[str, Any]) -> int:
    """Ausgangshaltung aus den Akteursdaten (öffentlich für Tests)."""
    staemme = _thema_staemme(thema)
    dafuer, _ = _bezug(staemme, [*akteur["ziele"], *akteur["prioritaeten"], *akteur["themen_interesse"]])
    dagegen, _ = _bezug(
        staemme, [*akteur["rote_linien"], *akteur["restriktionen"], *akteur["budgetvorgaben"]]
    )
    streu = _streuung(akteur["id"], thema["id"], modulo=5) - 2
    return _klemme(1.0 * (dafuer - dagegen) + 0.5 * streu)


def mehrkosten_linie(akteur: dict[str, Any], thema_id: str, experte: dict[str, Any]) -> str | None:
    """Die rote Linie gegen Mehrkosten, wenn sie bei diesem Thema greift (öffentlich für Tests).

    Sie greift bei einer Maßnahme des Pakets (`annahme.massnahmen_umfang`), wenn das Rechenmodell für das
    Paket Mehrkosten berechnet (`kosten_aenderung_prozent.modus` > 0).
    """
    linie = next((r for r in akteur["rote_linien"] if MEHRKOSTEN_LINIE in r.casefold()), None)
    if linie is None:
        return None
    massnahmen = {str(m["id"]) for m in (experte.get("annahme") or {}).get("massnahmen_umfang") or []}
    kosten = ((experte.get("vom_rechenmodell_berechnet") or {}).get("kosten_aenderung_prozent") or {}).get(
        "modus"
    )
    if thema_id in massnahmen and isinstance(kosten, int | float) and kosten > 0:
        return str(linie)
    return None


# --- Akteur --------------------------------------------------------------------------------------------


def _akteurszug(k: dict[str, Any]) -> dict[str, Any]:
    akteur = k["akteur"]
    aid = akteur["id"]
    runde = int(k["runde"])
    themen: list[dict[str, Any]] = k["themen"]
    beleg_ids: list[str] = sorted(k.get("beleg_ids") or [])
    teilnehmer: list[str] = sorted(t for t in k.get("teilnehmer") or [] if t != aid)
    experte = k.get("experte") or {}
    vorrunde = k.get("vorrunde") or {}
    positionen: dict[str, dict[str, int]] = vorrunde.get("positionen") or {}
    eigene = positionen.get(aid, {})

    haltungen: dict[str, int] = {}
    alt: dict[str, int] = {}
    gegen: dict[str, str] = {}
    for thema in themen:
        tid = thema["id"]
        vorher = eigene.get(tid, grundhaltung(akteur, thema)) if runde > 1 else grundhaltung(akteur, thema)
        alt[tid] = vorher
        neu = vorher
        andere = [p[tid] for a, p in positionen.items() if a != aid and tid in p]
        linie_kosten = mehrkosten_linie(akteur, tid, experte) if runde >= VERHANDLUNGSRUNDE else None
        if linie_kosten is not None:
            gegen[tid] = linie_kosten
            neu = min(vorher, -1)
        elif runde in (2, 3) and andere:
            mittel = sum(andere) / len(andere)
            if abs(mittel - vorher) >= 1 and _streuung(aid, tid, runde, modulo=2) == 0:
                neu = _klemme(vorher + (1 if mittel > vorher else -1))
        haltungen[tid] = neu

    bezug: list[str] = []
    if runde > 1 and teilnehmer:

        def abstand(anderer: str) -> tuple[int, str]:
            p = positionen.get(anderer, {})
            return (-sum(abs(p.get(t, 0) - haltungen[t]) for t in haltungen), anderer)

        bezug = [min(teilnehmer, key=abstand)]

    # Nur Ergebniszahlen des Rechenmodells tragen die Quelle `experte`, nie Vorgabe oder Annahme.
    berechnet = experte.get("vom_rechenmodell_berechnet") or {}
    wz = (berechnet.get("wartezeit_aenderung_prozent") or {}).get("modus")
    kosten = (berechnet.get("kosten_aenderung_prozent") or {}).get("modus")
    zahlen: list[dict[str, Any]] = []
    zuege: list[dict[str, Any]] = []
    for i, thema in enumerate(themen):
        tid = thema["id"]
        h = haltungen[tid]
        staemme = _thema_staemme(thema)
        _, ziel = _bezug(staemme, [*akteur["ziele"], *akteur["prioritaeten"]])
        _, linie = _bezug(staemme, [*akteur["rote_linien"], *akteur["budgetvorgaben"]])
        linie = gegen.get(tid, linie)
        if h >= 1:
            grund = f"Das Thema stützt unser Ziel: {ziel or akteur['ziele'][0]}."
        elif h <= -1:
            grund = f"Das Thema berührt unsere Grenze: {linie or akteur['rote_linien'][0]}."
        else:
            grund = (
                f"Wir wägen ab zwischen {ziel or akteur['ziele'][0]} "
                f"und {linie or akteur['restriktionen'][0]}."
            )
        if runde > 1 and bezug:
            grund += f" Wir gehen auf die Position von {bezug[0]} ein."
        if i == 0 and isinstance(wz, int | float) and isinstance(kosten, int | float):
            grund += (
                f" Der Experte rechnet für das Paket mit {_zahl_de(wz)} % Wartezeit bei {_zahl_de(kosten)} % "
                "Mehrkosten."
            )
            zahlen = [
                {"wert": wz, "einheit": "%", "quelle": "experte"},
                {"wert": kosten, "einheit": "%", "quelle": "experte"},
            ]
        if runde == 2 and i == 0 and teilnehmer and aid < teilnehmer[0]:
            grund += " Nach eigener Schätzung fehlen dafür rund 300 Stellen."
        belege = [beleg_ids[_streuung(aid, tid, modulo=len(beleg_ids))]] if beleg_ids else []
        if not belege:
            grund += " Ohne Beleg im Pressespiegel, Modellannahme."
        bewegt = h != alt[tid]
        zuege.append(
            {
                "thema": tid,
                "haltung": h,
                "begruendung": grund,
                "beleg_ids": belege,
                "bedingungen": [f"Wahrung von: {linie or akteur['rote_linien'][0]}"] if runde >= 3 else [],
                "zugestaendnis": (
                    f"Bewegung von {alt[tid]:+d} auf {h:+d} mit Blick auf {bezug[0]}"
                    if bewegt and bezug
                    else None
                ),
            }
        )
    return {"themen": zuege, "bezug_auf": bezug, "zahlen": zahlen}


# --- Moderator -----------------------------------------------------------------------------------------

_ZUSATZTHEMEN = (
    {
        "id": "finanzierung",
        "titel": "Gegenfinanzierung der Mehrkosten",
        "beschreibung": "Wer trägt die Mehrkosten im Budget von Bund, Ländern und Krankenversicherung",
    },
    {
        "id": "patientenlenkung",
        "titel": "Patientenlenkung über Hotline und Primärversorgung",
        "beschreibung": (
            "Lenkung der Facharzttermine über Gesundheitshotline, Terminvergabe und Primärversorgung"
        ),
    },
)


def _auftrag(k: dict[str, Any]) -> dict[str, Any]:
    themen = [
        {
            "id": str(m["id"]),
            "titel": str(m["name"]),
            "beschreibung": f"{m['name']} im Umfang des Pakets ({m['einheit']})",
        }
        for m in ((k.get("experte") or {}).get("annahme") or {}).get("massnahmen_umfang") or []
    ]
    themen += [dict(t) for t in _ZUSATZTHEMEN]
    return {
        "themen": themen[: int(k.get("max_themen") or 6)],
        "regeln": [
            "Jede Haltung stützt sich auf einen übergebenen Beleg oder ist als Modellannahme benannt.",
            "Zahlen nur mit Quelle experte oder einer Beleg-ID.",
            "Ab Runde 2 geht jeder Zug auf mindestens einen anderen Teilnehmer ein.",
            "Rote Linien gelten; Zugeständnisse nur gegen ausdrückliche Bedingungen.",
        ],
        "ziel": str(k.get("frage") or ""),
    }


def _auswahl(k: dict[str, Any]) -> dict[str, Any]:
    themen_staemme: set[str] = set()
    for t in k.get("themen") or []:
        themen_staemme |= _thema_staemme(t)
    max_akteure = int(k.get("max_akteure") or 6)

    def punkte(eintrag: dict[str, Any]) -> tuple[int, int]:
        bezug = len(themen_staemme & _staemme(" ".join(eintrag.get("themen_interesse") or [])))
        return int(eintrag.get("belegzahl") or 0), bezug

    reihe = sorted(k.get("pool") or [], key=lambda e: (-(punkte(e)[0] + 2 * punkte(e)[1]), e["id"]))
    akteure = []
    for rang, eintrag in enumerate(reihe, start=1):
        belege, bezug = punkte(eintrag)
        gewaehlt = rang <= max_akteure
        if gewaehlt:
            text = f"Gewählt (Rang {rang}): {belege} Belege zum Fall, {bezug} Themenbezüge."
        else:
            text = (
                f"Nicht gewählt (Rang {rang}): {belege} Belege zum Fall, {bezug} Themenbezüge; "
                f"die Obergrenze von {max_akteure} Akteuren ist mit stärker belegten Akteuren erreicht."
            )
        akteure.append({"akteur": eintrag["id"], "eingeladen": gewaehlt, "begruendung": text})
    return {"akteure": sorted(akteure, key=lambda a: a["akteur"])}


def _notiz(k: dict[str, Any]) -> dict[str, Any]:
    runde = int(k["runde"])
    aenderungen = k.get("aenderungen") or []
    code = k.get("code_widersprueche") or []
    ohne = k.get("haltungen_ohne_beleg") or []
    klass = k.get("klassifikation") or {}
    offen = sorted(t for t, kat in klass.items() if kat == "offener_konflikt")
    teile = [f"Runde {runde}: {len(aenderungen)} Positionsänderungen."]
    if offen:
        teile.append(f"Offen bleiben: {', '.join(offen)}.")
    if code:
        teile.append(f"Der Code meldet {len(code)} Auffälligkeiten; ich bitte um Klärung.")
    return {
        "notiz": " ".join(teile),
        "belege_eingefordert": [
            {"akteur": e["akteur"], "thema": e["thema"], "grund": "Haltung ohne Beleg"} for e in ohne
        ],
        "widersprueche": [
            {
                "akteur": e["akteur"],
                "thema": e.get("thema") or "",
                "art": e["art"],
                "beschreibung": e["beschreibung"],
            }
            for e in code
        ],
    }


def _kaputt(k: dict[str, Any]) -> bool:
    wert = os.environ.get(KAPUTT_ENV, "").strip()
    if not wert or ":" not in wert:
        return False
    akteur, _, runde = wert.partition(":")
    return k.get("rolle") == "akteur" and k["akteur"]["id"] == akteur and str(k.get("runde")) == runde


class SzenarioMock(Provider):  # type: ignore[misc]
    """UC2-Szenario-Mock; antwortet aus dem Kontextblock der ersten User-Nachricht."""

    name = "mock"
    deterministisch = True

    def standard_modell(self, groesse: str) -> str:
        return MODELL

    def rufe(
        self,
        nachrichten: list[dict[str, str]],
        *,
        schema: dict[str, Any] | None,
        modell: str,
        aufwand: str | None,
        zweck: str,
    ) -> Any:
        erste = next((n["content"] for n in nachrichten if n.get("role") == "user"), "")
        k = lies_kontext(erste)
        if k is None:
            raise FixtureFehlt("uc2-Szenario-Mock: Nachricht ohne Kontextblock")
        rolle = k.get("rolle")
        if _kaputt(k):
            text = KAPUTTER_TEXT
        else:
            if rolle == "akteur":
                daten = _akteurszug(k)
            elif rolle == "moderator_auftrag":
                daten = _auftrag(k)
            elif rolle == "moderator_auswahl":
                daten = _auswahl(k)
            elif rolle == "moderator_notiz":
                daten = _notiz(k)
            else:
                raise FixtureFehlt(f"uc2-Szenario-Mock: unbekannte Rolle {rolle!r}")
            text = json.dumps(daten, ensure_ascii=False, sort_keys=True)
        return Rohantwort(
            text=text,
            modell=modell or MODELL,
            version=VERSION,
            tokens_in=sum(len(n["content"].split()) for n in nachrichten),
            tokens_out=len(text.split()),
        )


_VORHER: list[Any] = []


def einhaengen() -> None:
    """Szenario-Mock als `kern.INSTANZEN["mock"]` setzen (nur bei Provider mock aufrufen)."""
    instanzen: dict[str, Any] = _kern.INSTANZEN
    if not isinstance(instanzen.get("mock"), SzenarioMock):
        _VORHER.append(instanzen.get("mock"))
    instanzen["mock"] = SzenarioMock()


def zuruecksetzen() -> None:
    """Vorigen mock-Eintrag wiederherstellen (Tests, Ende eines Laufs)."""
    instanzen: dict[str, Any] = _kern.INSTANZEN
    if not isinstance(instanzen.get("mock"), SzenarioMock):
        return
    vorher = _VORHER.pop() if _VORHER else None
    if vorher is None:
        instanzen.pop("mock", None)
    else:
        instanzen["mock"] = vorher
