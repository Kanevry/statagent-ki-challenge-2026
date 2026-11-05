#!/usr/bin/env python3
"""Rang-Orakel (#43): rechnet gespeicherte Suchtreffer per SQL gegen PG nach, ohne uc2-Laufzeitcode.

Aufruf: `python uc2/tests/pruefe_rang.py <treffer.json> [--regeln uc2/config/regeln.yaml] [--db healthpolicy]`

Eingabe ist die Ausgabe von `uv run uc2 suche … --json` (mit oder ohne `--akteur`):

    {"modus": "volltext|vektor|hybrid", "frage": "<tatsächliche Abfrage>", "stichtag": "JJJJ-MM-TT",
     "institution": "<ID>" | null, "k": 8,
     "treffer": [{"abschnitt_id" | "beleg_id", "relevanz", "ts", "cos", "rang_volltext", "rang_vektor",
                  "gewicht_alter", "faktor_institution", "rang"}, …]}

Geprüft, jeweils auf 1e-9:
- Altersgewicht `0,5^((stichtag − artikeldatum)/halbwertszeit_tage)` aus `uc2.artikel.artikeldatum`;
- Faktor `institutionsfaktor`, wenn `uc2.abschnitt.institutionen` die Institution enthält, sonst 1;
- Relevanz: volltext = `ts_rank_cd(abschnitt.tsv || artikel.tsv, q, 32)` (eigene SQL); hybrid/rrf =
  `gewicht_volltext/(rrf_k + rang_volltext) + gewicht_vektor/(rrf_k + rang_vektor)`; hybrid/summe und vektor
  aus dem gespeicherten `cos`;
- Endrang = Relevanz × Altersgewicht × Faktor, alles in einer SQL-Zeile gerechnet;
- Reihenfolge der Treffer absteigend nach Rang;
- Volltextrang: Kandidatenliste (beste `kandidaten` Abschnitte nach `ts_rank_cd`), bester Abschnitt je
  Artikel, Artikelrang nach (ts absteigend, artikel_id) selbst nachgerechnet; im Modus volltext
  zusätzlich die ganze Top-k-Liste.

Exit 1 bei einer Abweichung, sonst 0. Die Verbindung folgt `UC2_DATABASE_URL`, sonst `PG*` und `UC2_DB`
(Standard localhost:5433, statistik/statistik, DB healthpolicy), `--db` ersetzt den DB-Namen.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import psycopg
import yaml
from psycopg.conninfo import make_conninfo

TOLERANZ = 1e-9
REGELN = Path(__file__).resolve().parents[1] / "config" / "regeln.yaml"

ABFRAGE = {
    "oder": "to_tsquery('simple', replace(plainto_tsquery('german', %(frage)s)::text, '&', '|'))",
    "und": "websearch_to_tsquery('german', %(frage)s)",
}
"""Eigene Kopie der Abfrage je Verknüpfung (bewusst nicht aus uc2 importiert)."""

EINZEL_SQL = """
select a.artikeldatum, s.artikel_id, g.gewicht, f.faktor, t.ts, r.relevanz,
       r.relevanz * g.gewicht * f.faktor as rang
from uc2.abschnitt s join uc2.artikel a using (artikel_id),
     lateral (select {abfrage} as q) qq,
     lateral (select power(0.5, (%(stichtag)s::date - a.artikeldatum)::float8 / %(hwz)s) as gewicht) g,
     lateral (select case when %(inst)s::text = any(s.institutionen) then %(faktor)s::float8
                          else 1.0::float8 end as faktor) f,
     lateral (select case when (s.tsv || a.tsv) @@ qq.q then ts_rank_cd(s.tsv || a.tsv, qq.q, 32)
                          else 0 end::float8 as ts) t,
     lateral (select case %(art)s
        when 'volltext' then t.ts
        when 'vektor' then greatest(%(cos)s::float8, 0)
        when 'summe' then %(gv)s * greatest(%(cos)s::float8, 0) + %(gt)s * t.ts
        else coalesce(%(gt)s / (%(rrf_k)s + %(rt)s::float8), 0)
           + coalesce(%(gv)s / (%(rrf_k)s + %(rv)s::float8), 0)
     end as relevanz) r
where s.abschnitt_id = %(id)s
"""

VOLLTEXT_SQL = """
with qq as (select {abfrage} as q),
kand as (
    select s.abschnitt_id, s.artikel_id, a.artikeldatum, s.institutionen,
           (case when (s.tsv || a.tsv) @@ qq.q then ts_rank_cd(s.tsv || a.tsv, qq.q, 32) else 0 end)::float8
           as ts
    from uc2.abschnitt s join uc2.artikel a using (artikel_id), qq
    where (s.tsv @@ qq.q or a.tsv @@ qq.q) and a.artikeldatum <= %(stichtag)s
    order by ts_rank_cd(s.tsv || a.tsv, qq.q, 32) desc, s.abschnitt_id
    limit %(n)s
),
bester as (
    select distinct on (artikel_id) artikel_id, abschnitt_id, ts
    from kand order by artikel_id, ts desc, abschnitt_id collate "C"
)
select artikel_id, abschnitt_id, row_number() over (order by ts desc, artikel_id collate "C") from bester
"""

TOPK_SQL = """
with qq as (select {abfrage} as q),
kand as (
    select s.abschnitt_id, s.artikel_id,
           (case when (s.tsv || a.tsv) @@ qq.q then ts_rank_cd(s.tsv || a.tsv, qq.q, 32) else 0 end)::float8
           * power(0.5, (%(stichtag)s::date - a.artikeldatum)::float8 / %(hwz)s)
           * case when %(inst)s::text = any(s.institutionen) then %(faktor)s::float8 else 1.0::float8 end
           as rang
    from uc2.abschnitt s join uc2.artikel a using (artikel_id), qq
    where (s.tsv @@ qq.q or a.tsv @@ qq.q) and a.artikeldatum <= %(stichtag)s
    order by ts_rank_cd(s.tsv || a.tsv, qq.q, 32) desc, s.abschnitt_id
    limit %(n)s
),
bester as (
    select distinct on (artikel_id) artikel_id, abschnitt_id, rang
    from kand order by artikel_id, rang desc, abschnitt_id collate "C"
)
select abschnitt_id from bester where rang > 0 order by rang desc, abschnitt_id collate "C" limit %(k)s
"""


def conninfo(dbname: str | None) -> str:
    url = os.environ.get("UC2_DATABASE_URL")
    if url:
        return make_conninfo(url, dbname=dbname) if dbname else make_conninfo(url)
    return make_conninfo(
        "",
        host=os.environ.get("PGHOST", "localhost"),
        port=os.environ.get("PGPORT", "5433"),
        user=os.environ.get("PGUSER", "statistik"),
        password=os.environ.get("PGPASSWORD", "statistik"),
        dbname=dbname or os.environ.get("UC2_DB", "healthpolicy"),
    )


def pruefe(verbindung: psycopg.Connection[Any], lauf: dict[str, Any], regeln: dict[str, Any]) -> list[str]:
    """Liste der Abweichungen (leer = grün)."""
    suche = regeln["suche"]
    modus = str(lauf["modus"])
    art = "rrf" if modus == "hybrid" and suche.get("fusion", "rrf") == "rrf" else modus
    art = "summe" if modus == "hybrid" and art != "rrf" else art
    abfrage = ABFRAGE[str(suche.get("volltext_verknuepfung", "oder"))]
    basis = {
        "frage": lauf["frage"],
        "stichtag": lauf["stichtag"],
        "hwz": float(regeln["halbwertszeit_tage"]),
        "inst": lauf.get("institution"),
        "faktor": float(regeln["institutionsfaktor"]),
        "gt": float(suche["gewicht_volltext"]),
        "gv": float(suche["gewicht_vektor"]),
        "rrf_k": float(suche.get("rrf_k", 60)),
        "n": int(suche["kandidaten"]),
    }
    fehler: list[str] = []
    treffer = lauf["treffer"]
    artikel_je_id: dict[str, str] = {}
    for nr, t in enumerate(treffer, start=1):
        aid = str(t.get("abschnitt_id") or t["beleg_id"])
        zeile = verbindung.execute(
            EINZEL_SQL.format(abfrage=abfrage),
            {
                **basis,
                "id": aid,
                "art": art,
                "cos": float(t["cos"]),
                "rt": t.get("rang_volltext"),
                "rv": t.get("rang_vektor"),
            },
        ).fetchone()
        if zeile is None:
            fehler.append(f"{nr}. {aid}: Abschnitt fehlt im Index")
            continue
        _, artikel_id, gewicht, faktor, ts, rel, rang = zeile
        artikel_je_id[aid] = str(artikel_id)
        for feld, soll in (
            ("gewicht_alter", gewicht),
            ("faktor_institution", faktor),
            ("relevanz", rel),
            ("rang", rang),
        ):
            if abs(float(t[feld]) - float(soll)) > TOLERANZ:
                fehler.append(f"{nr}. {aid}: {feld} gespeichert {t[feld]!r}, nachgerechnet {soll!r}")
        if modus in ("volltext", "hybrid") and abs(float(t["ts"]) - float(ts)) > TOLERANZ:
            fehler.append(f"{nr}. {aid}: ts gespeichert {t['ts']!r}, nachgerechnet {ts!r}")
    raenge = [float(t["rang"]) for t in treffer]
    if raenge != sorted(raenge, reverse=True):
        fehler.append("Reihenfolge: Treffer nicht absteigend nach Rang")

    if modus in ("volltext", "hybrid"):
        liste = verbindung.execute(VOLLTEXT_SQL.format(abfrage=abfrage), basis).fetchall()
        rang_je_artikel = {str(a): (str(s), int(r)) for a, s, r in liste}
        for nr, t in enumerate(treffer, start=1):
            aid = str(t.get("abschnitt_id") or t["beleg_id"])
            soll = rang_je_artikel.get(artikel_je_id.get(aid, ""))
            gespeichert = t.get("rang_volltext")
            if modus == "hybrid":
                if (soll[1] if soll else None) != gespeichert:
                    fehler.append(
                        f"{nr}. {aid}: rang_volltext gespeichert {gespeichert}, nachgerechnet {soll}"
                    )
                elif soll and soll[0] != aid:
                    fehler.append(f"{nr}. {aid}: bester Abschnitt im Volltext ist {soll[0]}")
            elif soll is None:
                fehler.append(f"{nr}. {aid}: nicht in der Volltext-Kandidatenliste")
    if modus == "volltext":
        k = int(lauf.get("k") or len(treffer))
        soll_ids = [
            str(z[0]) for z in verbindung.execute(TOPK_SQL.format(abfrage=abfrage), {**basis, "k": k})
        ]
        ist_ids = [str(t.get("abschnitt_id") or t["beleg_id"]) for t in treffer]
        if soll_ids != ist_ids:
            fehler.append(f"Top-{k}: gespeichert {ist_ids}, nachgerechnet {soll_ids}")
    return fehler


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Rang-Orakel für uc2 suche --json (#43)")
    parser.add_argument("treffer", type=Path)
    parser.add_argument("--regeln", type=Path, default=REGELN)
    parser.add_argument("--db", default=None)
    args = parser.parse_args(argv)
    lauf = json.loads(args.treffer.read_text(encoding="utf-8"))
    regeln = yaml.safe_load(args.regeln.read_text(encoding="utf-8"))
    with psycopg.connect(conninfo(args.db)) as verbindung:
        fehler = pruefe(verbindung, lauf, regeln)
    for zeile in fehler:
        print(zeile)
    anzahl = len(lauf["treffer"])
    print(
        f"{'ABWEICHUNG' if fehler else 'GRÜN'}: {anzahl} Treffer, {len(fehler)} Abweichungen", file=sys.stderr
    )
    return 1 if fehler else 0


if __name__ == "__main__":
    sys.exit(main())
