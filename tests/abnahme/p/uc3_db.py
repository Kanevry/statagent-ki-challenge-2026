"""Liest die UC3-Prüf-DB (nur lesen) und gibt eindeutige Zeilen für schwere Prüfsätze aus.

    P="uv run --package statagent python tests/abnahme/p/uc3_db.py"
    $P abrechnung 2024-08 [--regelsatz v1]
    $P zeitreihe --orakel tests/abnahme/orakel/zeitreihe.csv --spalte v1_sheet_mit_e07
    $P laeufe --manifest docs/plan/uc3/laufmanifest-v1.csv
    $P regelsaetze v1 v2 ministerium
    $P schema       # Tabellen, PostgreSQL-Version, Pflichtspalten (#13 AC2, #73 AC2)
    $P ladung       # Ladeprotokoll gegen Rohtabelle und Lieferungsdateien (#13 AC3)
    $P anhangb      # Prüfabfragen aus docs/plan/uc3/anhang-b-schema.sql auf der vollen DB (#69 AC1)
    $P qualifikation  # Ausgangscodes je Beschäftigungskategorie (#69 AC1)

Die Adresse kommt aus UC3_DATABASE_URL; der Prüflauf setzt sie nur auf die Prüf-DB (Port 5444).
Je Monat zählt der jüngste Lauf mit Status fertig oder unveraendert. Monatssumme = gezaehlt; die
E07-Fortschreibung ist darin enthalten (Laufmanifest 2025-03: gezaehlt 388650 = 387180 + 1470).
"""

from __future__ import annotations

import argparse
import csv
import gzip
import os
import re
import sys
from pathlib import Path

import psycopg

LETZTER_LAUF = """
select distinct on (lieferung) lieferung, gelesen, gezaehlt, nicht_gezaehlt, ausgeschlossen,
       coalesce(fortgeschrieben, 0), ergebnis_hash, ergebnis_status
from meta.lauf
where status in ('fertig', 'unveraendert') and regelsatz = %s
order by lieferung, id desc
"""


def laeufe_lesen(regelsatz: str) -> dict[str, tuple]:
    with psycopg.connect(os.environ["UC3_DATABASE_URL"], connect_timeout=5) as verbindung:
        verbindung.read_only = True
        zeilen = verbindung.execute(LETZTER_LAUF, (regelsatz,)).fetchall()
    return {z[0]: z for z in zeilen}


def abrechnung(lieferung: str, regelsatz: str) -> int:
    z = laeufe_lesen(regelsatz).get(lieferung)
    if not z:
        print(f"kein fertiger Lauf {regelsatz} für {lieferung}")
        return 1
    _, gelesen, gezaehlt, nicht, aus, fort, _, status = z
    print(f"gelesen {gelesen}")
    print(f"gezaehlt {gezaehlt}")
    print(f"nicht_gezaehlt {nicht}")
    print(f"ausgeschlossen {aus}")
    print(f"fortgeschrieben {fort}")
    print(f"ergebnis_status {status}")
    # gezaehlt enthält die E07-Fortschreibung; sie stammt nicht aus der eigenen Lieferung
    print(f"aufgehend {'ja' if gelesen == gezaehlt - fort + nicht + aus else 'nein'}")
    return 0


def zeitreihe(orakel: str, spalte: str, regelsatz: str) -> int:
    ist = laeufe_lesen(regelsatz)
    with open(orakel, newline="") as f:
        soll = {r["monat"]: int(r[spalte]) for r in csv.DictReader(f, delimiter=";")}
    abweichend = []
    for monat, wert in sorted(soll.items()):
        z = ist.get(monat)
        summe = z[2] if z else None
        if summe != wert:
            abweichend.append((monat, wert, summe))
    print(f"monate {len(soll)}")
    print(f"mit_lauf {sum(1 for m in soll if m in ist)}")
    print(f"abweichend {len(abweichend)}")
    for monat, wert, summe in abweichend[:10]:
        print(f"  {monat}: soll {wert}, ist {summe}")
    return 0 if not abweichend else 1


def laeufe(manifest: str, regelsatz: str) -> int:
    ist = laeufe_lesen(regelsatz)
    with open(manifest, newline="", encoding="utf-8") as f:
        soll = {r["monat"]: r for r in csv.DictReader(f)}
    gleich = sum(1 for m, r in soll.items() if m in ist and ist[m][6] == r["ergebnis_hash"])
    nach = sum(int(r.get("nach_laufmonat") or 0) for r in soll.values())
    print(f"manifest_monate {len(soll)}")
    print(f"db_monate {len(ist)}")
    print(f"hash_gleich {gleich}")
    print(f"nach_laufmonat {nach}")
    return 0 if gleich == len(soll) == len(ist) and nach == 0 else 1


REGELN_AKTIV = """
select count(*) filter (where aktiv), count(*) filter (where aktiv and freigegeben_von is not null)
from meta.regel where regelsatz = %s
"""


def regelsaetze(namen: list[str]) -> int:
    """Aktive und freigegebene Regeln je Regelsatz; auf frischer Prüf-DB zeigt das, ob `db init` sie lädt."""
    leer = 0
    with psycopg.connect(os.environ["UC3_DATABASE_URL"], connect_timeout=5) as verbindung:
        verbindung.read_only = True
        for name in namen:
            aktiv, frei = verbindung.execute(REGELN_AKTIV, (name,)).fetchone()
            print(f"regelsatz {name} aktiv {aktiv} freigegeben {frei}")
            leer += aktiv == 0
    print(f"regelsaetze_ohne_aktive_regel {leer}")
    return 0 if leer == 0 else 1


PFLICHT_TABELLEN = (
    "meta.regel",
    "meta.lauf",
    "meta.pruefung_treffer",
    "stat.stat_beschaeftigte",
    "stat.beschreibung",
    "stat.variable",
    "stat.klass_geschlecht",
    "stat.klass_region",
    "stat.klass_qualifikation",
    "stat.klass_beschaeftigungskategorie",
    "stat.klass_oenace",
    "stat.klass_alter",
    "stat.uebergang",
    "stat.quellzuordnung",
)
# Definition und Berechnung stehen laut Schema zusammen in stat.variable.beschreibung.
PFLICHT_SPALTEN = {
    "variable": (
        "stat.variable",
        ("statistik", "code", "bezeichnung", "beschreibung", "einheit"),
    ),
    "oenace": ("stat.klass_oenace", ("version", "code", "ebene", "uebergeordnet", "gueltig_von")),
    "uebergang": ("stat.uebergang", ("klassifikation", "beziehung", "gueltig_ab")),
}


def schema() -> int:
    with psycopg.connect(os.environ["UC3_DATABASE_URL"], connect_timeout=5) as v:
        v.read_only = True
        print(f"pg {v.execute('show server_version').fetchone()[0].split('.')[0]}")
        fehlt = [
            t for t in PFLICHT_TABELLEN if v.execute("select to_regclass(%s)", (t,)).fetchone()[0] is None
        ]
        print(f"fehlende_tabellen {len(fehlt)}")
        for t in fehlt:
            print(f"  {t}")
        for name, (tabelle, spalten) in PFLICHT_SPALTEN.items():
            sch, tab = tabelle.split(".")
            da = {
                z[0]
                for z in v.execute(
                    "select column_name from information_schema.columns"
                    " where table_schema=%s and table_name=%s",
                    (sch, tab),
                )
            }
            print(f"{name}_fehlend {' '.join(sorted(set(spalten) - da)) or 'keine'}")
    return 0 if not fehlt else 1


def ladung() -> int:
    with psycopg.connect(os.environ["UC3_DATABASE_URL"], connect_timeout=5) as v:
        v.read_only = True
        protokoll = dict(v.execute("select lieferung, zeilen from roh.ladeprotokoll").fetchall())
        roh = dict(v.execute("select lieferung, count(*) from roh.lieferung group by 1").fetchall())
        nicht_text = v.execute(
            "select count(*) from information_schema.columns where table_schema='roh'"
            " and table_name='lieferung' and data_type <> 'text'"
        ).fetchone()[0]
    start = Path(os.environ.get("STATAGENT_STARTPAKET", "../svbox/uc3")) / "lieferungen"
    datei_abweichend = 0
    for monat, zeilen in protokoll.items():
        with gzip.open(start / f"lieferung_{monat}.csv.gz", "rt", encoding="utf-8") as f:
            datei_abweichend += sum(1 for _ in f) - 1 != zeilen
    print(f"lieferungen {len(protokoll)}")
    print(f"db_abweichend {sum(roh.get(m) != z for m, z in protokoll.items())}")
    print(f"datei_abweichend {datei_abweichend}")
    print(f"roh_nicht_text {nicht_text}")
    return 0


def anhangb() -> int:
    """Anhang-B-Abfragen auf der vollen Prüf-DB (der Test der Lane misst drei Fixture-Monate)."""
    text = Path("docs/plan/uc3/anhang-b-schema.sql").read_text(encoding="utf-8")
    ohne_kommentare = "\n".join(z for z in text.splitlines() if not z.lstrip().startswith("--"))
    abfragen = [a.strip() for a in re.split(r";\s*\n", ohne_kommentare) if a.strip()]
    gesamt = 0
    with psycopg.connect(os.environ["UC3_DATABASE_URL"], connect_timeout=5) as verbindung:
        verbindung.read_only = True
        for abfrage in abfragen:
            pruefung, fehlend = verbindung.execute(abfrage.encode()).fetchone()
            gesamt += int(fehlend)
            print(f"{pruefung.split()[0]} {fehlend}")
    print(f"abfragen {len(abfragen)}")
    print(f"fehlend_gesamt {gesamt}")
    return 0


def qualifikation() -> int:
    """Fünf Ausgangscodes auf drei Fachkategorien, Unbekannt gesondert (#69 AC1)."""
    with psycopg.connect(os.environ["UC3_DATABASE_URL"], connect_timeout=5) as verbindung:
        verbindung.read_only = True
        zeilen = verbindung.execute(
            "select beschaeftigungskategorie, count(*) from stat.klass_qualifikation group by 1 order by 1"
        ).fetchall()
    for kategorie, codes in zeilen:
        print(f"kategorie {kategorie} codes {codes}")
    fach = [z for z in zeilen if z[0] != "Unbekannt"]
    print(f"fachkategorien {len(fach)}")
    print(f"ausgangscodes {sum(z[1] for z in fach)}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    unter = ap.add_subparsers(dest="befehl", required=True)
    a1 = unter.add_parser("abrechnung")
    a1.add_argument("lieferung")
    a2 = unter.add_parser("zeitreihe")
    a2.add_argument("--orakel", required=True)
    a2.add_argument("--spalte", required=True)
    a3 = unter.add_parser("laeufe")
    a3.add_argument("--manifest", required=True)
    for p in (a1, a2, a3):
        p.add_argument("--regelsatz", default="v1")
    a4 = unter.add_parser("regelsaetze")
    a4.add_argument("namen", nargs="+")
    unter.add_parser("schema")
    unter.add_parser("ladung")
    unter.add_parser("anhangb")
    unter.add_parser("qualifikation")
    a = ap.parse_args()
    if a.befehl == "regelsaetze":
        return regelsaetze(a.namen)
    if a.befehl == "schema":
        return schema()
    if a.befehl == "ladung":
        return ladung()
    if a.befehl == "anhangb":
        return anhangb()
    if a.befehl == "qualifikation":
        return qualifikation()
    if a.befehl == "abrechnung":
        return abrechnung(a.lieferung, a.regelsatz)
    if a.befehl == "zeitreihe":
        return zeitreihe(a.orakel, a.spalte, a.regelsatz)
    return laeufe(a.manifest, a.regelsatz)


if __name__ == "__main__":
    sys.exit(main())
