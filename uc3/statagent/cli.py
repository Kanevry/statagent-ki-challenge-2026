"""Kommandozeile `statagent`: Läufe starten, Ergebnisse ansehen, Regeln freigeben (Bedienbarkeit, Bereich 6).

Jeder Befehl läuft ohne Sprachmodell. `--json` liefert maschinenlesbare Ausgabe für die Weboberfläche.
"""

from __future__ import annotations

import csv
import gzip
import json
import sys
from pathlib import Path
from typing import Annotated, Any, NoReturn

import typer

from statagent import ergebnis, konfig
from statagent.db import lieferungen, schema_einrichten, verbinden
from statagent.regeln import NameUngueltig, RegelFehler, regeln_freigeben, regeln_laden

app = typer.Typer(
    help="StatAgent: Monatsbetrieb der Beschäftigtenstatistik. Die KI schreibt Code, das Programm rechnet.",
    no_args_is_help=True,
    add_completion=False,
)
db_app = typer.Typer(help="Datenbank: Schema einrichten und Rohdaten prüfen.", no_args_is_help=True)
regeln_app = typer.Typer(help="Regeln als Daten: anzeigen, exportieren, freigeben.", no_args_is_help=True)
vorschlag_app = typer.Typer(help="Vorschläge der Agenten ansehen.", no_args_is_help=True)
app.add_typer(db_app, name="db")
app.add_typer(regeln_app, name="regeln")
app.add_typer(vorschlag_app, name="vorschlag")

JsonOption = Annotated[bool, typer.Option("--json", help="Ausgabe als JSON")]


def _ausgabe(daten: Any, als_json: bool, text: str) -> None:
    if als_json:
        typer.echo(json.dumps(daten, ensure_ascii=False, default=str, indent=2))
    else:
        typer.echo(text)


def _fehlt(issue: str, was: str) -> NoReturn:
    typer.echo(f"{was}: noch nicht umgesetzt ({issue}).", err=True)
    raise typer.Exit(2)


# --- db -----------------------------------------------------------------------------------------------------


@db_app.command("init")
def db_init(als_json: JsonOption = False) -> None:
    """Legt Schemas bereinigt/meta/stat, Klassifikationen und Regelsatz v1 an (idempotent, nichts wird gelöscht)."""
    with verbinden() as conn:
        dateien = schema_einrichten(conn)
    _ausgabe({"angewendet": dateien}, als_json, "angewendet: " + ", ".join(dateien))


@db_app.command("pruefen")
def db_pruefen(
    startpaket: Annotated[bool, typer.Option(help="auch die CSV-Dateien des Startpakets nachzählen")] = False,
    als_json: JsonOption = False,
) -> None:
    """Prüft das Ladeprotokoll: je Lieferung Zeilen in roh.lieferung = roh.ladeprotokoll.zeilen (= CSV-Sätze)."""
    with verbinden() as conn:
        zeilen = conn.execute(
            """SELECT p.lieferung, p.zeilen AS protokoll, count(r.*) AS geladen
               FROM roh.ladeprotokoll p LEFT JOIN roh.lieferung r USING (lieferung)
               GROUP BY p.lieferung, p.zeilen ORDER BY p.lieferung"""
        ).fetchall()
    ergebnisse = []
    ok = True
    for z in zeilen:
        eintrag: dict[str, Any] = {
            "lieferung": z["lieferung"],
            "protokoll": z["protokoll"],
            "geladen": z["geladen"],
        }
        if startpaket:
            datei = konfig.startpaket() / "lieferungen" / f"lieferung_{z['lieferung']}.csv.gz"
            if datei.is_file():
                with gzip.open(datei, "rt", encoding="utf-8", newline="") as f:
                    eintrag["csv"] = sum(1 for _ in csv.reader(f, delimiter=";")) - 1
        eintrag["stimmt"] = (
            eintrag["protokoll"] == eintrag["geladen"]
            and eintrag.get("csv", eintrag["geladen"]) == (eintrag["geladen"])
        )
        ok = ok and bool(eintrag["stimmt"])
        ergebnisse.append(eintrag)
    text = "\n".join(
        f"{e['lieferung']}  protokoll {e['protokoll']:>8}  geladen {e['geladen']:>8}"
        + (f"  csv {e['csv']:>8}" if "csv" in e else "")
        + ("  ✓" if e["stimmt"] else "  ✗ ABWEICHUNG")
        for e in ergebnisse
    )
    text += f"\n{len(ergebnisse)} Lieferungen, {'alle stimmen' if ok else 'Abweichungen'}"
    _ausgabe({"lieferungen": ergebnisse, "anzahl": len(ergebnisse), "stimmt": ok}, als_json, text)
    if not ok:
        raise typer.Exit(1)


# --- regeln -------------------------------------------------------------------------------------------------


@regeln_app.command("zeigen")
def regeln_zeigen(
    regelsatz: Annotated[str, typer.Option(help="Regelsatz, z. B. v1")] = "v1",
    lieferung: Annotated[str | None, typer.Option(help="nur Regeln, die für diese Lieferung gelten")] = None,
    als_json: JsonOption = False,
) -> None:
    """Zeigt die aktiven Regeln mit Parametern, Grundlage und Freigabe."""
    with verbinden() as conn:
        regeln = regeln_laden(conn, regelsatz, lieferung)
    daten = [
        {
            "id": r.id,
            "name": r.name,
            "typ": r.typ,
            "art": r.art,
            "parameter": r.parameter,
            "beschreibung": r.beschreibung,
            "grundlage": r.grundlage,
            "gueltig_ab": r.gueltig_ab_lieferung,
            "gueltig_bis": r.gueltig_bis_lieferung,
            "freigegeben_von": r.freigegeben_von,
            "freigegeben_am": r.freigegeben_am,
        }
        for r in regeln
    ]
    text = "\n".join(
        f"{r.id:>4} {r.typ:<9} {r.name:<34} {json.dumps(r.parameter, ensure_ascii=False)}\n"
        f"     {r.beschreibung}\n     Grundlage: {r.grundlage} · "
        + (
            f"freigegeben von {r.freigegeben_von} am {r.freigegeben_am:%d.%m.%Y %H:%M}"
            if r.freigegeben_am
            else "NICHT freigegeben"
        )
        for r in regeln
    )
    _ausgabe(daten, als_json, text)


@regeln_app.command("export")
def regeln_export(
    datei: Annotated[Path, typer.Option(help="Zieldatei (CSV, Semikolon)")],
    regelsatz: Annotated[str, typer.Option()] = "v1",
) -> None:
    """Schreibt den Regelsatz als CSV-Snapshot (für Dokumentation und Review)."""
    with verbinden() as conn:
        zeilen = conn.execute(
            """SELECT id, regelsatz, name, typ, art, reihenfolge, parameter::text AS parameter, beschreibung,
                      begruendung, grundlage, gueltig_ab_lieferung, gueltig_bis_lieferung, aktiv,
                      freigegeben_von, freigegeben_am
               FROM meta.regel WHERE regelsatz = %s ORDER BY typ, reihenfolge, id""",
            (regelsatz,),
        ).fetchall()
    datei.parent.mkdir(parents=True, exist_ok=True)
    with datei.open("w", encoding="utf-8", newline="") as f:
        if zeilen:
            w = csv.DictWriter(f, fieldnames=list(zeilen[0].keys()), delimiter=";")
            w.writeheader()
            w.writerows(zeilen)
    typer.echo(f"{len(zeilen)} Regeln → {datei}")


@regeln_app.command("freigeben")
def regeln_freigeben_befehl(
    name: Annotated[str, typer.Option(help="Vor- und Nachname der freigebenden Person")],
    regelsatz: Annotated[str, typer.Option()] = "v1",
) -> None:
    """Gibt alle noch offenen Regeln eines Regelsatzes mit Namen und Zeitpunkt frei („Team“ wird abgelehnt)."""
    try:
        with verbinden() as conn:
            n = regeln_freigeben(conn, regelsatz, name)
    except NameUngueltig as fehler:
        typer.echo(f"abgelehnt: {fehler}", err=True)
        raise typer.Exit(1) from fehler
    typer.echo(f"{n} Regeln im Regelsatz {regelsatz} freigegeben von {' '.join(name.split())}.")


# --- lauf ---------------------------------------------------------------------------------------------------


@app.command("lauf")
def lauf(
    lieferung: Annotated[str | None, typer.Option(help="Berichtsmonat JJJJ-MM, z. B. 2025-03")] = None,
    regelsatz: Annotated[str, typer.Option(help="v1 (Fachbeschreibung) oder v2 (Änderungsaufträge)")] = "v1",
    alle: Annotated[bool, typer.Option("--alle", help="alle Lieferungen als Folge von Einzelläufen")] = False,
    gestartet_von: Annotated[str | None, typer.Option(help="Name der Person, die den Lauf startet")] = None,
    als_json: JsonOption = False,
) -> None:
    """Rechnet einen Berichtsmonat aus seiner eigenen Lieferung (ein Lauf = eine Lieferung)."""
    from statagent.lauf import LaufFehler, lauf_ausfuehren

    with verbinden() as conn:
        if alle:
            monate = lieferungen(conn)
        elif lieferung:
            monate = [lieferung]
        else:
            typer.echo("Bitte --lieferung JJJJ-MM oder --alle angeben.", err=True)
            raise typer.Exit(2)
        ergebnisse = []
        for monat in monate:
            try:
                e = lauf_ausfuehren(conn, monat, regelsatz, gestartet_von=gestartet_von)
            except (LaufFehler, RegelFehler) as fehler:
                typer.echo(f"{monat}: abgebrochen: {fehler}", err=True)
                raise typer.Exit(1) from fehler
            ergebnisse.append(e.als_dict())
            if not als_json:
                typer.echo(
                    f"{e.lieferung} [{e.regelsatz}] {e.status:<12} {e.ergebnis_status:<10} "
                    f"gezählt {e.gezaehlt:>7,}  gelesen {e.gelesen:>7,} = {e.gezaehlt:,} + {e.nicht_gezaehlt:,} "
                    f"nicht gezählt + {e.ausgeschlossen:,} ausgeschlossen  hash {e.ergebnis_hash[:12]}"
                    + (f"  ({e.meldung})" if e.meldung else "")
                )
                sys.stdout.flush()
    if als_json:
        typer.echo(
            json.dumps(ergebnisse if alle else ergebnisse[0], ensure_ascii=False, default=str, indent=2)
        )


@app.command("laeufe")
def laeufe(regelsatz: Annotated[str, typer.Option()] = "v1", als_json: JsonOption = False) -> None:
    """Listet die Läufe mit Status, Abrechnung und Ergebnis-Hash."""
    with verbinden() as conn:
        zeilen = conn.execute(
            """SELECT id, lieferung, regelsatz, regelstand, status, ergebnis_status, gelesen, gezaehlt,
                      nicht_gezaehlt, ausgeschlossen, ergebnis_hash, gestartet_am, meldung
               FROM meta.lauf WHERE regelsatz = %s ORDER BY id""",
            (regelsatz,),
        ).fetchall()
    text = "\n".join(
        f"{z['id']:>4} {z['lieferung']} {z['status']:<12} {z['ergebnis_status'] or '-':<10} "
        f"gezählt {z['gezaehlt'] or 0:>8,} hash {str(z['ergebnis_hash'] or '')[:12]}"
        for z in zeilen
    )
    _ausgabe(zeilen, als_json, text or "noch keine Läufe")


@app.command("eichen")
def eichen(
    lieferung: Annotated[str, typer.Option(help="Berichtsmonat mit Beispielbericht")] = "2024-08",
    regelsatz: Annotated[str, typer.Option()] = "v1",
    xlsx: Annotated[Path | None, typer.Option(help="Beispielbericht (Standard: Startpaket)")] = None,
) -> None:
    """Vergleicht Tab1–Tab13 des Beispielberichts Zelle für Zelle mit stat.stat_beschaeftigte."""
    from statagent.eichung import bericht_text
    from statagent.eichung import eichen as eichen_ausfuehren

    with verbinden() as conn:
        if ergebnis.letzter_lauf(conn, lieferung, regelsatz) is None:
            typer.echo(
                f"Kein Lauf für {lieferung} ({regelsatz}). Zuerst: statagent lauf --lieferung {lieferung}"
            )
            raise typer.Exit(1)
        erg = eichen_ausfuehren(conn, lieferung, xlsx, regelsatz)
    typer.echo(bericht_text(erg))
    if not erg.stimmt:
        raise typer.Exit(1)


# --- noch nicht umgesetzte Befehle (eigene Issues) ---------------------------------------------------------


@app.command("berichte")
def berichte(lieferung: Annotated[str | None, typer.Option(help="Berichtsmonat JJJJ-MM")] = None) -> None:
    """Qualitätsbericht je Berichtsmonat aus der Vorlage erzeugen bzw. anzeigen."""
    _fehlt("#16", "berichte")


@app.command("sheet")
def sheet(regelsatz: Annotated[str, typer.Option()] = "v1") -> None:
    """Aggregations-Sheet aus der Vorlage füllen (alle gerechneten Monate)."""
    _fehlt("#16", "sheet")


@app.command("pruefe-abgabe")
def pruefe_abgabe() -> None:
    """Prüft die Abgabedateien unter abgabe/ (Sheet, 24 Qualitätsberichte, Ministerium, Protokoll, Modelle)."""
    _fehlt("#16/#20", "pruefe-abgabe")


@app.command("ministerium")
def ministerium(monat: Annotated[str, typer.Option(help="Berichtsmonat JJJJ-MM")] = "2026-07") -> None:
    """Ministeriums-Lieferung (Auftrag 3) erzeugen."""
    _fehlt("#71", "ministerium")


@app.command("agent")
def agent(anweisung: Annotated[str, typer.Argument(help="Änderungsauftrag in Sprache")]) -> None:
    """Gibt einen Änderungsauftrag an den Koordinator-Agenten (erzeugt einen Vorschlag, ändert nichts)."""
    _fehlt("#15", "agent")


@vorschlag_app.command("zeigen")
def vorschlag_zeigen(vorschlag_id: Annotated[int, typer.Argument()]) -> None:
    """Zeigt einen Vorschlag mit Regel-Diff und Zahlen vorher/nachher."""
    _fehlt("#15", "vorschlag zeigen")


@app.command("freigabe")
def freigabe(
    vorschlag_id: Annotated[int, typer.Argument(help="ID des Vorschlags")],
    name: Annotated[str, typer.Option(help="Vor- und Nachname der freigebenden Person")],
) -> None:
    """Gibt einen Vorschlag mit Namen frei (Regel aktiv, Commit mit Trailer Freigegeben-von)."""
    _fehlt("#15", "freigabe")


@app.command("frage")
def frage(text: Annotated[str, typer.Argument(help="Frage an die Daten")]) -> None:
    """Beantwortet eine Datenanfrage aus der Datenbank, mit sichtbarer Abfrage und Definition."""
    _fehlt("#74", "frage")


@app.command("klass")
def klass(
    begriff: Annotated[str, typer.Argument(help="z. B. oenace, region, qualifikation")] = "oenace",
) -> None:
    """Zeigt eine Klassifikation mit Versionen und Übergängen."""
    _fehlt("#75", "klass")


@app.command("protokoll")
def protokoll(als_json: JsonOption = False) -> None:
    """Protokoll aller Änderungen über die Agenten (Anweisung, Änderung, Freigabe)."""
    _fehlt("#15", "protokoll")


def main() -> None:
    app()


if __name__ == "__main__":
    main()
