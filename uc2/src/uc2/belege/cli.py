"""Befehle `extrahiere`, `einbetten`, `index`, `suche`, `namen sammeln` (eingehängt von `uc2.cli`)."""

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
from uc2.belege.suche import AUSSCHNITT_ZEICHEN


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
    from uc2.belege.index import VektorenPassenNicht, indexiere

    try:
        with db.verbinde(args.db) as verbindung:
            ergebnis = indexiere(args.extrakt, verbindung)
    except VektorenPassenNicht as fehler:
        print(f"Abbruch: {fehler}", file=sys.stderr)
        return 1
    if ergebnis.meldung:
        print(f"Hinweis: {ergebnis.meldung}", file=sys.stderr)
    print(
        f"quellen={ergebnis.quellen} artikel={ergebnis.artikel} abschnitte={ergebnis.abschnitte} "
        f"mit_vektor={ergebnis.mit_vektor} modell={ergebnis.modell} inhalt_hash={ergebnis.inhalt_hash}"
    )
    return 0


def _akteur(akteur_id: str) -> Any:
    from uc2.akteure.laden import lade_akteure

    for akteur in lade_akteure():
        if akteur.id == akteur_id:
            return akteur
    raise SystemExit(f"Akteur {akteur_id!r} unbekannt")


def _suche(args: argparse.Namespace) -> int:
    """Ausgabe immer maskiert in Anzeigeform (Namen als Rolle, Zitate als [Zitat]); keine Rohform.

    Fail-closed: ohne Namensliste (`UC2_NAMENSLISTE`) Meldung auf stderr und Exit 2 (`NamenslisteFehlt`).

    JSON (`--json`, Eingabe für `tests/pruefe_rang.py`): `{"modus", "frage" (tatsächliche Abfrage),
    "stichtag", "institution" (oder null), "k", "treffer": [...]}`; je Treffer `abschnitt_id`, `artikel_id`,
    `artikeldatum`, `medium`, `titel`, `ausschnitt`, `relevanz`, `ts`, `cos`, `rang_volltext`,
    `rang_vektor`, `gewicht_alter`, `faktor_institution`, `rang`. Mit `--akteur` zusätzlich `akteur`,
    `runde` und je Treffer die Felder von `Beleg.als_dict()` (Online-Grenze: `zitat` statt Abschnittstext,
    weder `text_anzeige` noch `text_modell`).
    """
    from uc2.belege.einbettung import einbetter
    from uc2.belege.namen import Namensliste, NamenslisteFehlt, NamenslisteImRepo
    from uc2.belege.suche import maskiere_treffer, suche, suche_belege

    regeln = lade_regeln()
    modus = args.modus or regeln.modus
    stichtag = args.stichtag or regeln.stichtag_standard
    try:
        namen = Namensliste.lade()
    except (NamenslisteFehlt, NamenslisteImRepo) as fehler:
        print(f"Abbruch: {fehler}", file=sys.stderr)
        return 2
    ausgabe: dict[str, Any]
    with db.verbinde(args.db) as verbindung:
        # Der Einbetter (torch, Modell) lädt erst, wenn der Index Vektoren hat; ohne das Extra `einbettung`
        # fällt `suche` mit Hinweis auf volltext zurück.
        if args.akteur:
            ergebnis = suche_belege(
                verbindung,
                _akteur(args.akteur),
                args.frage,
                args.runde,
                stichtag=stichtag,
                regeln=regeln,
                einbetter_fabrik=einbetter,
                namen=namen,
                modus=modus,
                k=args.k,
            )
            ausgabe = {
                "modus": ergebnis.modus,
                "frage": ergebnis.abfrage,
                "stichtag": stichtag.isoformat(),
                "institution": ergebnis.institution,
                "k": args.k or regeln.k_je_akteur,
                "akteur": args.akteur,
                "runde": args.runde,
                "treffer": [
                    {"abschnitt_id": b.beleg_id, "artikeldatum": b.datum, **b.als_dict()}
                    for b in ergebnis.belege
                ],
            }
        else:
            genutzt, treffer = suche(
                verbindung,
                args.frage,
                regeln,
                modus=modus,
                k=args.k,
                stichtag=stichtag,
                einbetter_fabrik=einbetter,
            )
            belege = maskiere_treffer(verbindung, treffer, namen)
            ausgabe = {
                "modus": genutzt,
                "frage": args.frage,
                "stichtag": stichtag.isoformat(),
                "institution": None,
                "k": args.k or regeln.k,
                "treffer": [
                    {
                        **t.als_dict(),
                        "titel": b.titel,
                        "ausschnitt": " ".join(b.text_anzeige.split())[:AUSSCHNITT_ZEICHEN],
                    }
                    for t, b in zip(treffer, belege, strict=True)
                ],
            }
    if args.json:
        print(json.dumps(ausgabe, ensure_ascii=False, indent=2))
        return 0
    anzahl = len(ausgabe["treffer"])
    print(f"Modus {ausgabe['modus']}, {anzahl} Treffer (maskiert), Abfrage: {ausgabe['frage']}")
    for n, t in enumerate(ausgabe["treffer"], start=1):
        text = t.get("zitat", t.get("ausschnitt", ""))
        print(
            f"{n:2d}. rang={t['rang']:.4f} relevanz={t['relevanz']:.4f} cos={t['cos']:.4f} ts={t['ts']:.4f} "
            f"rang_volltext={t['rang_volltext']} rang_vektor={t['rang_vektor']} "
            f"gewicht_alter={t['gewicht_alter']:.4f} faktor_institution={t['faktor_institution']:.2f} "
            f"| {t['artikeldatum']} {t['medium']} | {t['titel']}"
            f"\n    {' '.join(text.split())[:AUSSCHNITT_ZEICHEN]}"
        )
    return 0


def _namen_sammeln(args: argparse.Namespace) -> int:
    """Namensliste schreiben: Muster über alle Titel und Abschnitte des Index plus externe Autor:in-Liste."""
    import time

    from uc2.belege.namen import (
        Namenseintrag,
        NamenslisteImRepo,
        lies_namenszeilen,
        pruefe_ausserhalb_repo,
        sammle_namen,
        schreibe_namensliste,
    )

    beginn = time.monotonic()
    try:
        pruefe_ausserhalb_repo(args.ausgabe)
    except NamenslisteImRepo as fehler:
        print(f"Abbruch: {fehler}", file=sys.stderr)
        return 1
    if not args.aus_index and args.autoren is None:
        print("Abbruch: --aus-index oder --autoren angeben", file=sys.stderr)
        return 2
    eintraege: list[Namenseintrag] = []
    aus_index = 0
    if args.aus_index:
        artikel: dict[str, list[str]] = {}
        with db.verbinde(args.db) as verbindung:
            for artikel_id, titel, text in verbindung.execute(
                "select a.artikel_id, a.titel, s.text from uc2.artikel a "
                "join uc2.abschnitt s using (artikel_id) order by a.artikel_id, s.nr"
            ):
                artikel.setdefault(str(artikel_id), [str(titel)]).append(str(text))
        gesammelt = sammle_namen(artikel.values())
        aus_index = len(gesammelt)
        eintraege.extend(gesammelt)
    autoren = 0
    if args.autoren is not None:
        liste = lies_namenszeilen(args.autoren.read_text(encoding="utf-8"))
        autoren = len(liste)
        eintraege.extend(Namenseintrag(e.name) for e in liste)
    anzahl = schreibe_namensliste(args.ausgabe, eintraege)
    # Nur Zahlen, nie Namen ausgeben
    print(
        f"namen={anzahl} aus_index={aus_index} autoren={autoren} dauer_s={time.monotonic() - beginn:.1f} "
        f"→ {args.ausgabe}"
    )
    return 0


MAX_BATCH = 64


def _batch(wert: str) -> int:
    """1 bis 64 (Review-Bank 4f): begrenzt den Speicher je Modellaufruf bei Abschnitten bis 1.024 Token."""
    zahl = int(wert)
    if not 1 <= zahl <= MAX_BATCH:
        raise argparse.ArgumentTypeError(f"--batch muss zwischen 1 und {MAX_BATCH} liegen, nicht {zahl}")
    return zahl


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
    p.add_argument("--batch", type=_batch, default=32, help=f"Texte je Modellaufruf, höchstens {MAX_BATCH}")
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
    p.add_argument("--akteur", default=None, help="Akteurs-ID: Abfrage, k und Institutionsfaktor je Akteur")
    p.add_argument("--runde", type=int, default=1, help="nur mit --akteur, geht ins Protokoll")
    p.set_defaults(func=_suche)

    p = sub.add_parser("namen", help="Personenschutz: Namensliste außerhalb des Repos")
    namen_sub = p.add_subparsers(dest="namen_befehl", metavar="BEFEHL", required=True)
    q = namen_sub.add_parser("sammeln", help="Namen per Muster aus dem Index und aus einer Autor:in-Liste")
    q.add_argument("--ausgabe", type=Path, required=True, help="Zieldatei außerhalb des Repos")
    q.add_argument("--aus-index", action="store_true", help="Titel und Abschnitte des Index durchsuchen")
    q.add_argument("--autoren", type=Path, default=None, help="Datei mit einer Autor:in je Zeile")
    q.add_argument("--db", default=None)
    q.set_defaults(func=_namen_sammeln)
