"""Klassifikationen auf der Prüf-DB gegen die Quelldateien des Startpakets (#75, #76), nur lesen, nur Zahlen.

    uv run --package statagent python tests/abnahme/p/uc3_klass.py oenace
    uv run --package statagent python tests/abnahme/p/uc3_klass.py regionen

Die Sollwerte kommen aus den Dateien unter `klassifikationen/`, gelesen ohne Produktcode. Adresse aus
UC3_DATABASE_URL, Startpaket aus STATAGENT_STARTPAKET.
"""

from __future__ import annotations

import argparse
import csv
import io
import os
import re
import sys
from collections import Counter
from pathlib import Path

import psycopg


def ordner() -> Path:
    return Path(os.environ.get("STATAGENT_STARTPAKET", "../svbox/uc3")) / "klassifikationen"


def cti(datei: Path) -> dict[str, int]:
    text = datei.read_bytes().decode("cp1252")
    return {z["Code"]: int(z["Ebene"]) for z in csv.DictReader(io.StringIO(text), delimiter=";")}


def oenace(conn: psycopg.Connection) -> int:
    quelle = ordner() / "oenace"
    for version in ("2003", "2008", "2025"):
        zeilen = conn.execute(
            "select ebene, count(*) from stat.klass_oenace where version = %s group by 1 order by 1",
            (version,),
        ).fetchall()
        print(f"db_{version} " + " ".join(f"e{e}={n}" for e, n in zeilen))
    cot = (quelle / "OENACE2003_DE_COT.txt").read_bytes().decode("cp1252")
    codes_2003 = {z["Code"]: z["Ebene"] for z in csv.DictReader(io.StringIO(cot), delimiter=";") if z["Code"]}
    je_ebene = sorted(Counter(codes_2003.values()).items())
    print("quelle_2003 " + " ".join(f"e{e}={n}" for e, n in je_ebene))
    for version in ("2008", "2025"):
        soll = cti(quelle / f"OENACE{version}_DE_CTI.txt")
        ist = {
            c: e
            for c, e in conn.execute(
                "select code, ebene from stat.klass_oenace where version = %s", (version,)
            ).fetchall()
        }
        print(f"antijoin_quelle_nicht_db_{version} {sum(1 for c in soll if c not in ist)}")
        nur_db = sorted(c for c in ist if c not in soll)
        print(f"antijoin_db_nicht_quelle_{version} {len(nur_db)} {','.join(nur_db[:5])}".rstrip())
        print(f"ebene_abweichend_{version} {sum(1 for c, e in soll.items() if c in ist and ist[c] != e)}")
        waisen = conn.execute(
            """with recursive kette as (
                 select code, uebergeordnet, ebene, code as start from stat.klass_oenace
                  where version = %(v)s and ebene = 5
                 union all
                 select o.code, o.uebergeordnet, o.ebene, k.start from stat.klass_oenace o
                   join kette k on o.code = k.uebergeordnet and o.version = %(v)s)
               select count(*) filter (where n = 0), count(*) from
                 (select start, count(*) filter (where ebene = 1) as n from kette group by start) s""",
            {"v": version},
        ).fetchone()
        print(f"fuenfsteller_{version} {waisen[1]}")
        print(f"fuenfsteller_ohne_abschnitt_{version} {waisen[0]}")
    for alt, neu, klasse in (("2003", "2008", "oenace"), ("2008", "2025", "oenace_unterklasse")):
        zeilen = conn.execute(
            """select beziehung, count(*) from stat.uebergang
               where version_alt = %s and version_neu = %s and klassifikation = %s
               group by 1 order by 1""",
            (alt, neu, klasse),
        ).fetchall()
        print(f"uebergang_{alt}_{neu} {sum(n for _, n in zeilen)} " + " ".join(f"{b}={n}" for b, n in zeilen))
    datei = quelle / "OENACE2008_OENACE2025_DE_12B.txt"
    print(f"quelle_umsteiger_2008_2025 {len(datei.read_bytes().decode('cp1252').splitlines()) - 1}")
    return 0


def regionen(conn: psycopg.Connection) -> int:
    quelle = ordner() / "regionen"
    staende = sorted(re.search(r"\d{4}-\d{2}-\d{2}", p.name).group(0) for p in quelle.glob("gemeinden_*.csv"))
    print(f"quelle_staende {len(staende)}")
    fehlen = zuviel = 0
    for art in ("bezirk", "gemeinde"):
        for stand in staende:
            with open(
                quelle / f"{art}e_{stand}.csv" if art == "bezirk" else quelle / f"gemeinden_{stand}.csv",
                encoding="utf-8",
                newline="",
            ) as f:
                lesen = csv.DictReader(f, delimiter=_trenner(f))
                spalte = next(s for s in lesen.fieldnames if re.search("kennziffer|code|gkz|nummer", s, re.I))
                soll = {z[spalte].strip() for z in lesen}
            ist = {
                r[0]
                for r in conn.execute(
                    "select code from stat.klass_region where version = %s and ebene = %s", (stand, art)
                ).fetchall()
            }
            fehlen += len(soll - ist)
            zuviel += len(ist - soll)
    print(f"antijoin_quelle_nicht_db {fehlen}")
    print(f"antijoin_db_nicht_quelle {zuviel}")
    z = conn.execute(
        "select ebene, count(distinct version), count(*) from stat.klass_region group by 1 order by 1"
    ).fetchall()
    for ebene, versionen, n in z:
        print(f"region_{ebene} staende {versionen} zeilen {n}")
    z = conn.execute(
        """select klassifikation, count(*), count(*) filter (where quelle is null or quelle = ''),
                  count(*) filter (where gueltig_ab is null)
           from stat.uebergang where klassifikation in ('gemeinde', 'bezirk') group by 1 order by 1"""
    ).fetchall()
    for name, n, ohne_quelle, ohne_datum in z:
        print(f"uebergang_{name} {n} ohne_quelle {ohne_quelle} ohne_datum {ohne_datum}")
    weg = conn.execute(
        """with paar as (
             select version, lead(version) over (order by version) as naechster
             from (select distinct version from stat.klass_region where ebene = 'gemeinde') s)
           select count(*) from paar p
             join stat.klass_region a on a.version = p.version and a.ebene = 'gemeinde'
             left join stat.klass_region b
               on b.version = p.naechster and b.ebene = 'gemeinde' and b.code = a.code
           where p.naechster is not null and b.code is null and not exists (
             select 1 from stat.uebergang u where u.klassifikation = 'gemeinde' and u.code_alt = a.code)"""
    ).fetchone()[0]
    print(f"verschwunden_ohne_uebergang {weg}")
    return 0


def _trenner(f: io.TextIOBase) -> str:
    kopf = f.readline()
    f.seek(0)
    return ";" if ";" in kopf else ","


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("was", choices=["oenace", "regionen"])
    a = ap.parse_args()
    with psycopg.connect(os.environ["UC3_DATABASE_URL"], connect_timeout=5) as conn:
        conn.read_only = True
        return oenace(conn) if a.was == "oenace" else regionen(conn)


if __name__ == "__main__":
    sys.exit(main())
