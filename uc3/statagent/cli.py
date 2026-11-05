"""Kommandozeile `statagent`: Läufe starten, Ergebnisse ansehen, Regeln freigeben (Bedienbarkeit, Bereich 6).

Jeder Befehl läuft ohne Sprachmodell. `--json` liefert maschinenlesbare Ausgabe für die Weboberfläche.
"""

from __future__ import annotations

import csv
import dataclasses
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
            n = regeln_freigeben(conn, regelsatz, name, repo_pfad=konfig.REPO_WURZEL)
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
def berichte(
    lieferung: Annotated[str | None, typer.Option(help="Berichtsmonat JJJJ-MM")] = None,
    alle: Annotated[
        bool, typer.Option("--alle", help="Berichte für alle gerechneten Monate schreiben")
    ] = False,
    regelsatz: Annotated[str, typer.Option()] = "v1",
    zeigen: Annotated[bool, typer.Option("--zeigen", help="Bericht ausgeben statt schreiben")] = False,
) -> None:
    """Qualitätsbericht je Berichtsmonat aus der Vorlage erzeugen (abgabe/qualitaetsberichte/JJJJ-MM.md)."""
    from statagent.berichte.qualitaetsbericht import bericht_erzeugen, bericht_schreiben

    with verbinden() as conn:
        if alle:
            monate = [m for m in lieferungen(conn) if ergebnis.letzter_lauf(conn, m, regelsatz) is not None]
        elif lieferung:
            monate = [lieferung]
        else:
            typer.echo("Bitte --lieferung JJJJ-MM oder --alle angeben.", err=True)
            raise typer.Exit(2)
        for monat in monate:
            if zeigen:
                typer.echo(bericht_erzeugen(conn, monat, regelsatz))
            else:
                typer.echo(f"{monat}: {bericht_schreiben(conn, monat, regelsatz)}")


@app.command("veroeffentlichen")
def veroeffentlichen(
    name: Annotated[str, typer.Option(help="Vor- und Nachname der freigebenden Person")],
    lieferung: Annotated[str | None, typer.Option(help="Berichtsmonat JJJJ-MM")] = None,
    alle: Annotated[
        bool, typer.Option("--alle", help="alle gerechneten Monate, die nicht angehalten sind")
    ] = False,
    regelsatz: Annotated[str, typer.Option()] = "v1",
) -> None:
    """Gibt einen gerechneten Monat mit Namen frei: vorläufig → endgültig (danach unveränderlich)."""
    from statagent.lauf import LaufFehler
    from statagent.lauf import veroeffentlichen as veroeffentlichen_ausfuehren

    with verbinden() as conn:
        if alle:
            monate = [m for m in lieferungen(conn) if ergebnis.letzter_lauf(conn, m, regelsatz) is not None]
        elif lieferung:
            monate = [lieferung]
        else:
            typer.echo("Bitte --lieferung JJJJ-MM oder --alle angeben.", err=True)
            raise typer.Exit(2)
        fehler = 0
        erfolgreich = 0
        for monat in monate:
            try:
                n = veroeffentlichen_ausfuehren(conn, monat, regelsatz, name, repo_pfad=konfig.REPO_WURZEL)
                erfolgreich += 1
                typer.echo(f"{monat}: {n} Zellen endgültig, freigegeben von {' '.join(name.split())}")
            except (LaufFehler, NameUngueltig) as f:
                fehler += 1
                typer.echo(f"{monat}: nicht veröffentlicht: {f}", err=True)
    if fehler and (not alle or erfolgreich == 0):
        raise typer.Exit(1)


@app.command("sheet")
def sheet(regelsatz: Annotated[str, typer.Option()] = "v1") -> None:
    """Aggregations-Sheet aus der Vorlage füllen (alle gerechneten Monate) → abgabe/aggregationen_<regelsatz>.xlsx."""
    try:
        from statagent.berichte.sheet import sheet_schreiben
    except ModuleNotFoundError:
        _fehlt("#16", "sheet")
    with verbinden() as conn:
        erg = sheet_schreiben(conn, regelsatz)
    typer.echo(f"Sheet geschrieben: {getattr(erg, 'pfad', erg)}")


@app.command("laufmanifest")
def laufmanifest(regelsatz: Annotated[str, typer.Option()] = "v1") -> None:
    """Laufmanifest je Berichtsmonat (maßgeblicher Lauf, verwendete Lieferungen) → docs/plan/uc3/laufmanifest-<regelsatz>.csv."""
    from statagent.berichte.katalog import laufmanifest_luecken, laufmanifest_schreiben

    pfad = konfig.REPO_WURZEL / "docs" / "plan" / "uc3" / f"laufmanifest-{regelsatz}.csv"
    with verbinden() as conn:
        geschrieben = laufmanifest_schreiben(conn, pfad, regelsatz)
        luecken = laufmanifest_luecken(conn, regelsatz)
    typer.echo(f"Laufmanifest geschrieben: {geschrieben}")
    if luecken:
        typer.echo(f"ohne erfolgreichen Lauf: {', '.join(luecken)}", err=True)
        raise typer.Exit(1)


@app.command("pruefkatalog")
def pruefkatalog(regelsatz: Annotated[str, typer.Option()] = "v1") -> None:
    """Prüfkatalog P01–P24 aus meta.regel (Status, Ebene, Schwelle, Einstufung, Maßnahme) → uc3/pruefkatalog.csv."""
    from statagent.berichte.katalog import pruefkatalog_schreiben

    name = "pruefkatalog.csv" if regelsatz == "v1" else f"pruefkatalog_{regelsatz}.csv"
    with verbinden() as conn:
        geschrieben = pruefkatalog_schreiben(conn, konfig.UC3_WURZEL / name, regelsatz)
    typer.echo(f"Prüfkatalog geschrieben: {geschrieben}")


@app.command("pruefe-abgabe")
def pruefe_abgabe(als_json: JsonOption = False) -> None:
    """Prüft die Abgabedateien unter abgabe/ (Sheet alt und neu, 24 Qualitätsberichte, Ministerium, Protokoll, Modelle)."""
    from statagent.berichte.pruefe_abgabe import pruefe_abgabe as pruefen

    erg = pruefen(konfig.abgabe(), konfig.REPO_WURZEL)
    _ausgabe(erg.als_dict(), als_json, erg.als_text())
    if not erg.ok:
        raise typer.Exit(1)


@app.command("ministerium")
def ministerium(
    name: Annotated[str, typer.Option(help="Vor- und Nachname der Person, die die Lieferung freigibt")],
    monat: Annotated[str, typer.Option(help="Berichtsmonat JJJJ-MM")] = "2026-07",
    regelsatz: Annotated[str, typer.Option(help="Regelsatz mit der Definition (Auftrag 3)")] = "ministerium",
) -> None:
    """Ministeriums-Lieferung (Auftrag 3) rechnen, schreiben und über Vertrag P mit Namen freigeben (Commit)."""
    from plattform.freigabe import GitFehler, VorschlagUngueltig

    from statagent.sonderauswertung import (
        LieferungBereitsFreigegeben,
        NichtFreigegeben,
        ministerium_schreiben,
    )

    try:
        with verbinden() as conn:
            datei, auswertung = ministerium_schreiben(
                conn, monat, name, regelsatz=regelsatz, repo_pfad=konfig.REPO_WURZEL
            )
    except (
        NichtFreigegeben,
        NameUngueltig,
        RegelFehler,
        LieferungBereitsFreigegeben,
        GitFehler,
        VorschlagUngueltig,
        ValueError,
    ) as fehler:
        typer.echo(f"nicht erzeugt und nicht freigegeben: {fehler}", err=True)
        raise typer.Exit(1) from fehler
    typer.echo(f"{datei}: {len(auswertung.zeilen)} Personen, Zeitraum {auswertung.von} bis {auswertung.bis}")
    for m, lieferung in auswertung.datenstand.items():
        hinweis = f"  (übersprungen: {auswertung.uebersprungen[m]})" if m in auswertung.uebersprungen else ""
        typer.echo(f"  {m} aus Lieferung {lieferung}{hinweis}")


def _vorschlag_dict(v: Any) -> dict[str, Any]:
    """Vorschlag als dict für --json, mit Status in Alltagssprache und der Wirkung in einem Satz."""
    from statagent.agenten.vorschlag import wirkung_text

    return {
        **dataclasses.asdict(v),
        "zustand": v.zustand,
        "ref": v.ref,
        "datei_pfad": v.datei_pfad,
        "wirkung": wirkung_text(v.typ, v.aenderungen, v.regelsatz_ziel),
    }


def _entscheidung_fehler() -> tuple[type[BaseException], ...]:
    """Fehler, mit denen Freigabe und Ablehnung sauber abbrechen (Meldung, Exit 1, kein Traceback)."""
    from statagent.agenten.plattform_bruecke import PlattformFehlt
    from statagent.agenten.vorschlag import VorschlagFehler

    fehler: tuple[type[BaseException], ...] = (NameUngueltig, VorschlagFehler, PlattformFehlt)
    try:
        from plattform import freigabe as plattform_freigabe
    except ModuleNotFoundError:
        return fehler
    return (
        *fehler,
        plattform_freigabe.NichtFreigegeben,
        plattform_freigabe.VorschlagUngueltig,
        plattform_freigabe.GitFehler,
    )


@app.command("agent")
def agent(
    anweisung: Annotated[str, typer.Argument(help="Änderungsauftrag in Sprache")],
    regelsatz_basis: Annotated[str, typer.Option(help="Regelsatz, von dem der Vorschlag ausgeht")] = "v1",
    probe: Annotated[
        str | None, typer.Option(help="Probemonat JJJJ-MM: Zahlen vorher/nachher gleich mitrechnen")
    ] = None,
    als_json: JsonOption = False,
) -> None:
    """Gibt einen Änderungsauftrag an den Koordinator-Agenten (erzeugt einen Vorschlag, ändert nichts)."""
    from statagent.agenten.koordinator import agent_ausfuehren
    from statagent.agenten.plattform_bruecke import PlattformFehlt
    from statagent.agenten.vorschlag import VorschlagFehler, vorschlag_lesen, wirkung_text
    from statagent.lauf import LaufFehler

    modell_fehler: tuple[type[BaseException], ...] = (PlattformFehlt,)
    try:
        from plattform.llm import LlmFehler
    except ModuleNotFoundError:
        pass
    else:
        modell_fehler = (PlattformFehlt, LlmFehler)

    with verbinden() as conn:
        try:
            erg = agent_ausfuehren(conn, anweisung, regelsatz_basis=regelsatz_basis, probe_lieferung=probe)
        except modell_fehler as fehler:
            typer.echo(f"Modell nicht erreichbar, kein Vorschlag: {fehler}", err=True)
            raise typer.Exit(1) from fehler
        except (VorschlagFehler, LaufFehler, RegelFehler) as fehler:
            typer.echo(f"abgebrochen: {fehler}", err=True)
            raise typer.Exit(1) from fehler
        v = None if erg.vorschlag_id is None else vorschlag_lesen(conn, erg.vorschlag_id)

    daten: dict[str, Any] = dataclasses.asdict(erg)
    zeilen: list[str] = []
    if v is not None:
        wirkung = wirkung_text(v.typ, v.aenderungen, v.regelsatz_ziel)
        daten |= {"regelsatz_ziel": v.regelsatz_ziel, "wirkung": wirkung}
        zeilen += [
            f"Vorschlag uc3/{v.id} (Rolle {v.rolle}), offen, Ziel-Regelsatz {v.regelsatz_ziel}",
            f"Wirkung: {wirkung}",
        ]
    if erg.rueckfrage:
        zeilen.append(f"Rückfrage: {erg.rueckfrage}")
    if erg.abgelehnt:
        zeilen.append(f"Kein Vorschlag: {erg.abgelehnt}")
    if v is not None:
        zeilen += [
            f"Nächster Schritt: uv run uc3 vorschlag zeigen {v.id}",
            f'Wirksam erst nach Freigabe mit Namen: uv run uc3 freigabe {v.id} --name "Vorname Nachname"'
            f" (oder uv run uc3 ablehnen {v.id} --name … --begruendung …)",
        ]
    _ausgabe(daten, als_json, "\n".join(zeilen))
    if erg.abgelehnt:
        raise typer.Exit(1)


@vorschlag_app.command("zeigen")
def vorschlag_zeigen(
    vorschlag_id: Annotated[int, typer.Argument(help="ID des Vorschlags")],
    als_json: JsonOption = False,
) -> None:
    """Zeigt einen Vorschlag mit Regel-Diff, Zahlen vorher/nachher und Code-Datei."""
    from statagent.agenten.vorschlag import VorschlagFehler, diff_text, vorschlag_lesen

    try:
        with verbinden() as conn:
            v = vorschlag_lesen(conn, vorschlag_id)
    except VorschlagFehler as fehler:
        typer.echo(str(fehler), err=True)
        raise typer.Exit(1) from fehler
    text = diff_text(v)
    if v.datei_inhalt is not None:
        text += f"\n--- {v.datei_pfad} ---\n{v.datei_inhalt}"
    _ausgabe(_vorschlag_dict(v), als_json, text)


@app.command("freigabe")
def freigabe(
    vorschlag_id: Annotated[int, typer.Argument(help="ID des Vorschlags")],
    name: Annotated[str, typer.Option(help="Vor- und Nachname der freigebenden Person")],
    als_json: JsonOption = False,
) -> None:
    """Gibt einen Vorschlag mit Namen frei (Regel aktiv, Commit mit Trailer Freigegeben-von)."""
    from statagent.agenten.anwenden import freigabe_ausfuehren
    from statagent.agenten.vorschlag import vorschlag_lesen

    try:
        with verbinden() as conn:
            erg = freigabe_ausfuehren(conn, vorschlag_id, name, konfig.REPO_WURZEL)
            v = vorschlag_lesen(conn, vorschlag_id)
    except _entscheidung_fehler() as fehler:
        typer.echo(f"nicht freigegeben: {fehler}", err=True)
        raise typer.Exit(1) from fehler
    daten = dataclasses.asdict(erg) | {
        "freigegeben_am": v.freigegeben_am,
        "ref": v.ref,
        "protokoll_id": v.protokoll_id,
    }
    zeit = f"{v.freigegeben_am:%d.%m.%Y %H:%M}" if v.freigegeben_am else "?"
    zeilen = [
        f"Vorschlag uc3/{erg.vorschlag_id} freigegeben von {erg.name} am {zeit}",
        f"Commit {erg.commit_hash or '-'} · Protokoll {v.protokoll_id}",
    ]
    if erg.angewendet:
        zeilen.append(f"aktiv: {v.ref.replace(',', ', ')}")
    else:
        zeilen.append(
            f"NICHT angewendet ({erg.fehler}): {erg.meldung}. Die Freigabe bleibt bestehen; "
            "das Anwenden lässt sich wiederholen."
        )
    _ausgabe(daten, als_json, "\n".join(zeilen))
    if not erg.angewendet:
        raise typer.Exit(1)


@app.command("ablehnen")
def ablehnen(
    vorschlag_id: Annotated[int, typer.Argument(help="ID des Vorschlags")],
    name: Annotated[str, typer.Option(help="Vor- und Nachname der ablehnenden Person")],
    begruendung: Annotated[str, typer.Option(help="Warum der Vorschlag nicht kommt (Pflicht)")],
    als_json: JsonOption = False,
) -> None:
    """Lehnt einen Vorschlag mit Namen und Begründung ab (Regeln und Repo bleiben unverändert)."""
    from statagent.agenten.anwenden import ablehnen_ausfuehren

    try:
        with verbinden() as conn:
            v = ablehnen_ausfuehren(conn, vorschlag_id, name, konfig.REPO_WURZEL, begruendung=begruendung)
    except _entscheidung_fehler() as fehler:
        typer.echo(f"nicht abgelehnt: {fehler}", err=True)
        raise typer.Exit(1) from fehler
    _ausgabe(
        _vorschlag_dict(v),
        als_json,
        f"Vorschlag uc3/{v.id} abgelehnt von {v.abgelehnt_von}: {v.ablehnungsgrund}",
    )


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
def protokoll(
    zeigen: Annotated[
        bool, typer.Option("--zeigen", help="ausgeben statt nach abgabe/protokoll.md schreiben")
    ] = False,
) -> None:
    """Protokoll aller Änderungen: Anweisung, Änderung, Freigabe mit Namen (Git-Trailer und Datenbank)."""
    from statagent.berichte.protokoll import protokoll_erzeugen, protokoll_schreiben

    with verbinden() as conn:
        if zeigen:
            typer.echo(protokoll_erzeugen(conn))
        else:
            typer.echo(f"Protokoll geschrieben: {protokoll_schreiben(conn)}")


@app.command("antwort")
def antwort(
    frage_text: Annotated[
        str, typer.Argument(metavar="FRAGE", help="z. B. „Beschäftigte in Wien im März 2025“")
    ],
    regelsatz: Annotated[str, typer.Option()] = "v1",
    als_json: JsonOption = False,
) -> None:
    """UC4-Antwort von UC3: Zahl aus stat.stat_beschaeftigte mit Beleg (ohne Sprachmodell, #106)."""
    from statagent.uc4 import antwort_daten

    with verbinden() as conn:
        daten = antwort_daten(conn, frage_text, regelsatz)
    zeilen = [daten["text"]]
    for zahl in daten["zahlen"]:
        beleg = daten["belege"][zahl["beleg"]]
        zeilen.append(f"- {zahl['bezeichnung']}: {zahl['wert']} {zahl['einheit'] or ''}".rstrip())
        zeilen.append(f"  Beleg [{zahl['beleg']}] {beleg['quelle']}, {beleg['ref']}")
    for nummer, beleg in enumerate(daten["belege"]):
        zeilen.append(f"SQL [{nummer}]: {beleg['sql']}")
    _ausgabe(daten, als_json, "\n".join(zeilen))


def main() -> None:
    app()


if __name__ == "__main__":
    main()
