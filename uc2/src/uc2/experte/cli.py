"""Befehl `uv run uc2 experte --paket <datei.yaml> [--json]`."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from uc2 import pfade
from uc2.experte import modell


def register(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    parser = subparsers.add_parser(
        "experte",
        help="Wirkung eines Maßnahmenpakets auf Wartezeit und Kosten rechnen (ohne Sprachmodell)",
    )
    parser.add_argument("--paket", required=True, type=Path, help="Paketdatei, etwa uc2/pakete/….yaml")
    parser.add_argument("--json", action="store_true", help="Ausgabe als JSON (byte-gleich je Paket)")
    parser.set_defaults(func=ausfuehren)


def finde_paket(pfad: Path) -> Path:
    """Pfad relativ zum Arbeitsordner, sonst relativ zur Repo-Wurzel (`uc2/pakete/…` aus `uc2/`)."""
    if pfad.exists():
        return pfad
    kandidat = pfade.UC2_WURZEL.parent / pfad
    return kandidat if kandidat.exists() else pfad


def als_json(daten: dict[str, Any]) -> str:
    return json.dumps(daten, ensure_ascii=False, indent=2) + "\n"


def _p(wert: float, stellen: int = 1) -> str:
    text = f"{abs(wert):.{stellen}f}".replace(".", ",")
    return ("−" if round(wert, stellen) < 0 else "+" if round(wert, stellen) > 0 else "") + text


def _mio(wert: float) -> str:
    return modell.zahl_de(wert, 1)


def als_text(daten: dict[str, Any]) -> str:
    k = daten["kennzahlen"]
    w, c, r1 = k["wartezeit_aenderung_prozent"], k["kosten_aenderung_prozent"], k["rho1"]
    mk, cn = k["mehrkosten_mio_eur"], k["kosten_aenderung_niedergelassen_prozent"]
    ausgang, nieder, ziel = daten["ausgangsausgaben"], daten["basis_niedergelassen"], daten["ziel"]
    zeilen = [
        f"Experte: Paket {daten['paket']}" + (f" ({daten['beschreibung']})" if daten["beschreibung"] else ""),
        f"Hinweis: {daten['hinweis']}.",
        "",
        "Maßnahmen:",
    ]
    for m in daten["massnahmen"]:
        kapazitaet = m["wirkt_auf"] == "kapazitaet"
        art = "Kapazität" if kapazitaet else "Nachfrage"
        wirkung = m["wirkung_prozent"] if kapazitaet else -m["wirkung_prozent"]
        zeilen.append(
            f"  - {m['name']}: {m['umfang']:g} ({m['einheit']}) → {art} {_p(wirkung, 2)} %, "
            f"Mehrkosten {_mio(m['mehrkosten_mio_eur'])} Mio. EUR/Jahr"
        )
    zeilen += [
        "",
        f"Zieljahr {daten['zieljahr']} (Modus; Spanne über {daten['zielpruefung']['ecken']} Ecken):",
        f"  Auslastung ρ₁: {r1['modus']:.4f} (Spanne {r1['min']:.4f} bis {r1['max']:.4f})".replace(".", ","),
        f"  Wartezeitänderung: {_p(w['modus'], 2)} % (Spanne {_p(w['min'], 2)} % bis {_p(w['max'], 2)} %)",
        f"  Kostenänderung: {_p(c['modus'], 2)} % der Ausgangsausgaben "
        f"(Spanne {_p(c['min'], 2)} % bis {_p(c['max'], 2)} %), "
        f"Mehrkosten {_mio(mk['modus'])} Mio. EUR/Jahr",
        f"  Ausgangsausgaben: {_mio(ausgang['wert'])} {ausgang['einheit']} ({ausgang['jahr']})",
        f"  Zusatzkennzahl: {_p(cn['modus'], 2)} % der niedergelassenen Versorgung "
        f"({_mio(nieder['wert'])} {nieder['einheit']}, {nieder['jahr']}; nicht Teil der Zielprüfung)",
        "",
        f"Zielprüfung „{_p(ziel['wartezeit_aenderung_prozent_hoechstens'], 2)} % Wartezeit, "
        f"≤ {_p(ziel['kosten_aenderung_prozent_hoechstens'], 2)} % Kosten in {ziel['zieljahr']} Jahren“: "
        f"{daten['zielpruefung']['ergebnis']} "
        f"({daten['zielpruefung']['ecken_erreicht']} von {daten['zielpruefung']['ecken']} Ecken "
        "erreichen beide Ziele)",
        daten["entscheidend"]["text"],
        f"Ziel laut {ziel['quelle']}",
        "",
        "Jahrespfad (Modus):",
    ]
    for j in daten["jahrespfad"]:
        zeilen.append(
            f"  Jahr {j['jahr']}: Wartezeit {_p(j['wartezeit_aenderung_prozent'], 2)} %, "
            f"Kosten {_p(j['kosten_aenderung_prozent'], 2)} % ({_mio(j['mehrkosten_mio_eur'])} Mio. EUR)"
        )
    zeilen += ["", "Verwendete Annahmen (Typ B belegt, D abgeleitet, A Annahme):"]
    for a in daten["annahmen"]:
        marke = ", im Paket überschrieben" if a["ueberschrieben"] else ""
        spanne = f"{a['min']:g} / {a['modus']:g} / {a['max']:g}".replace(".", ",")
        zeilen.append(
            f"  - [{a['typ']}] {a['symbol']}: {spanne} {a['einheit']}{marke}. Quelle: {a['quelle']}"
        )
    return "\n".join(zeilen) + "\n"


def ausfuehren(args: argparse.Namespace) -> int:
    pfad = finde_paket(args.paket)
    try:
        daten = modell.ergebnis(modell.lade_paket(pfad))
    except (OSError, ValueError) as fehler:
        print(f"Fehler: {fehler}", file=sys.stderr)
        return 1
    except ArithmeticError as fehler:
        print(f"Fehler: Rechnung nicht möglich ({type(fehler).__name__}: {fehler})", file=sys.stderr)
        return 1
    sys.stdout.write(als_json(daten) if args.json else als_text(daten))
    return 0
