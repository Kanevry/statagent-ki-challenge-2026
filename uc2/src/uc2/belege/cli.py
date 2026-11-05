"""Befehle `extrahiere`, `einbetten`, `index`, `suche` (eingehängt von `uc2.cli`)."""

from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import date
from pathlib import Path
from typing import Any

from uc2 import db, pfade
from uc2.belege.regeln import MODI, lade_regeln


def _extrahiere(args: argparse.Namespace) -> int:
    from uc2.belege.extraktion import extrahiere

    zusammenfassung = extrahiere(args.quelle, args.aus, ab=args.ab, bis=args.bis, prozesse=args.prozesse)
    summe = zusammenfassung["summe"]
    print(
        f"{summe['dateien']} Dateien ({summe['uebersprungen']} übersprungen), Inhaltsverzeichnis "
        f"{summe['inhaltsverzeichnis']}, Artikel {summe['artikel']}, Abschnitte {summe['abschnitte']}, "
        f"Abweichungen {summe['abweichungen']}, {zusammenfassung['dauer_s']} s → {args.aus}"
    )
    return 0


def _einbetten(args: argparse.Namespace) -> int:
    from uc2.belege.einbettung import einbetter
    from uc2.belege.vektoren import bette_extrakt_ein

    logging.basicConfig(level=logging.INFO, format="%(message)s")
    meta = bette_extrakt_ein(
        args.extrakt, einbetter(batch_size=args.batch), batch=args.batch, grenze=args.grenze
    )
    print(json.dumps(meta, ensure_ascii=False))
    return 0


def _index(args: argparse.Namespace) -> int:
    from uc2.belege.index import indexiere

    with db.verbinde(args.db) as verbindung:
        ergebnis = indexiere(args.extrakt, verbindung)
    if ergebnis.meldung:
        print(f"Hinweis: {ergebnis.meldung}", file=sys.stderr)
    print(
        f"quellen={ergebnis.quellen} artikel={ergebnis.artikel} abschnitte={ergebnis.abschnitte} "
        f"mit_vektor={ergebnis.mit_vektor} modell={ergebnis.modell} inhalt_hash={ergebnis.inhalt_hash}"
    )
    return 0


def _suche(args: argparse.Namespace) -> int:
    from uc2.belege.einbettung import Einbetter, einbetter
    from uc2.belege.suche import suche

    regeln = lade_regeln()
    modus = args.modus or regeln.modus
    e: Einbetter | None = einbetter() if modus != "volltext" else None
    with db.verbinde(args.db) as verbindung:
        genutzt, treffer = suche(
            verbindung, args.frage, regeln, modus=modus, k=args.k, stichtag=args.stichtag, einbetter=e
        )
    if args.json:
        ausgabe: dict[str, Any] = {"modus": genutzt, "treffer": [t.als_dict() for t in treffer]}
        print(json.dumps(ausgabe, ensure_ascii=False, indent=2))
        return 0
    print(f"Modus {genutzt}, {len(treffer)} Treffer")
    for n, t in enumerate(treffer, start=1):
        print(
            f"{n:2d}. rang={t.rang:.4f} relevanz={t.relevanz:.4f} cos={t.cos:.4f} ts={t.ts:.4f} "
            f"rang_volltext={t.rang_volltext} rang_vektor={t.rang_vektor} "
            f"gewicht_alter={t.gewicht_alter:.4f} | {t.artikeldatum} {t.medium} | {t.titel}"
            f"\n    {t.ausschnitt}"
        )
    return 0


def register(sub: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    p = sub.add_parser("extrahiere", help="Pressespiegel-PDFs → JSONL (Stufe 1)")
    p.add_argument("--quelle", type=Path, default=pfade.presse())
    p.add_argument("--ab", type=date.fromisoformat, default=date(2026, 1, 1))
    p.add_argument("--bis", type=date.fromisoformat, default=None)
    p.add_argument("--aus", type=Path, default=pfade.arbeit() / "extrakt")
    p.add_argument("--prozesse", type=int, default=None, help="Prozesse für pdftotext (Standard: alle Kerne)")
    p.set_defaults(func=_extrahiere)

    p = sub.add_parser("einbetten", help="Abschnitte → vektoren.npy/vektoren.json (Stufe 2)")
    p.add_argument("--extrakt", type=Path, default=pfade.arbeit() / "extrakt")
    p.add_argument("--batch", type=int, default=32)
    p.add_argument("--grenze", type=int, default=None, help="nur die ersten N Abschnitte (Probelauf)")
    p.set_defaults(func=_einbetten)

    p = sub.add_parser("index", help="Extrakt in PG laden (Stufe 3)")
    p.add_argument("--extrakt", type=Path, default=pfade.arbeit() / "extrakt")
    p.add_argument("--db", default=None, help="Datenbank (Standard UC2_DB oder healthpolicy)")
    p.set_defaults(func=_index)

    p = sub.add_parser("suche", help="Belege suchen (Volltext, Vektor, Hybrid)")
    p.add_argument("frage")
    p.add_argument("--modus", choices=MODI, default=None)
    p.add_argument("--k", type=int, default=None)
    p.add_argument("--stichtag", type=date.fromisoformat, default=None)
    p.add_argument("--db", default=None)
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=_suche)
