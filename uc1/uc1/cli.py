"""Einstieg `lotse <befehl> [argumente]`. Jeder Befehl gehört einem Modul mit `cli(argv) -> int`."""

from __future__ import annotations

import importlib
import sys

# Befehl -> (Modul, Kurzbeschreibung). Module ohne Umsetzung melden das selbst.
BEFEHLE: dict[str, tuple[str, str]] = {
    "db-init": ("uc1.db", "DDL der Datenbank lotse einspielen"),
    "ingest": ("uc1.ingest", "Korpus svbox/uc1 in die Datenbank lotse einlesen (#29)"),
    "suche": ("uc1.suche", "Abschnitte zu einer Frage suchen (#29)"),
    "vektoren": ("uc1.vektoren", "Vollindex dichter Vektoren: export, berechnen, import, status (#29)"),
    "eval": ("uc1.eval", "Lotse-Set messen: Recall@5, Zitiertreue, Träger, Verhalten (#30)"),
    "frage": ("uc1.kern", "Eine Frage an den Lotsen stellen (#31)"),
    "uc4": ("uc1.uc4", "UC4-Antwort in einfacher Sprache über Zahlen und Belege aus UC3/UC2 (#107)"),
    "antrag": ("uc1.antrag", "Antrag als Entwurf vorausfüllen (#32)"),
    "termin": ("uc1.termin", "Belegte Stelle und Terminentwurf (ICS), nichts wird gebucht (#81)"),
    "serve": ("uc1.api", "Dienst uc1.api:app auf 127.0.0.1:8101 starten (#34)"),
}


def hilfe() -> str:
    breite = max(len(b) for b in BEFEHLE)
    zeilen = ["Aufruf: lotse <befehl> [argumente]", "", "Befehle:"]
    zeilen += [f"  {name.ljust(breite)}  {text}" for name, (_, text) in BEFEHLE.items()]
    return "\n".join(zeilen)


def main(argv: list[str] | None = None) -> int:
    # E0-Vertrag: jede Python-CLI lädt .env.local über plattform.umgebung (Datei gewinnt gegen Geerbtes).
    from plattform.umgebung import lade_env_local

    lade_env_local()
    args = list(sys.argv[1:] if argv is None else argv)
    if not args or args[0] in {"-h", "--help", "hilfe"}:
        print(hilfe())
        return 0
    befehl, rest = args[0], args[1:]
    if befehl not in BEFEHLE:
        print(f"unbekannter Befehl: {befehl}\n\n{hilfe()}", file=sys.stderr)
        return 2
    modulname = BEFEHLE[befehl][0]
    try:
        modul = importlib.import_module(modulname)
    except ModuleNotFoundError as fehler:
        if fehler.name != modulname:
            raise
        print(f"lotse {befehl}: noch nicht gebaut ({BEFEHLE[befehl][1]})", file=sys.stderr)
        return 2
    rueckgabe = modul.cli(rest)
    return int(rueckgabe)


if __name__ == "__main__":
    raise SystemExit(main())
