"""Abnahme UC4 (Epic #95): Eine Frage durch die Kette, jede UC3-Zahl gegen die Datenbank nachgerechnet.

Aufruf (Repo-Wurzel, UC3_DATABASE_URL zeigt auf eine Datenbank mit Läufen):
    uv run python tests/abnahme/95_kette.py

Je Frage:
1. ``plattform.router.durchreichen`` mit den echten Adaptern (Entry-Points ``kic.uc_antwort``).
2. Für jede Zahl mit UC3-Beleg: das SQL aus dem Beleg selbst erneut ausführen (Wert muss gleich sein) und eine
   eigene, unabhängig geschriebene Abfrage auf ``stat.stat_beschaeftigte`` (Wert muss gleich sein).
3. Beleg ``lauf`` muss gleich ``meta.lauf.ergebnis_hash`` des Monats sein.
4. ``router.jsonl`` darf keinen Fragetext enthalten.

Nur lesen. Die letzte Zeile ist JSON mit dem Ergebnis je Frage; der Prüfer urteilt.
"""

from __future__ import annotations

import json
import os
import re
import tempfile
from pathlib import Path
from typing import Any

import psycopg

FRAGEN = [
    "Wie viele Beschäftigte gab es im März 2025?",
    "Wie viele Beschäftigte gab es im August 2024 in Wien?",
    "Beschäftigte im März 2025 nach Bundesland",
    "Wie geht es den Wartezeiten?",
    "Wie viele Beschäftigte gab es im Juli 2027?",
    "Wie viele Beschäftigte gab es im Oktober 2025?",
]
#: Kette uc3 → uc2 → uc1: je Frage genau ein Routerschritt je UC, auch für fehlende Adapter.
SCHRITTE_JE_FRAGE = 3

#: Eigene Abfrage: Die Tabelle hat keine Summenzeilen, nur die volle Kreuzgliederung.
#: Österreich ist die Summe aller Zellen des Monats (Stichtag, Regelsatz v1),
#: je Bundesland die Summe je Code aus ``stat.klass_region``.
EIGENE = """
select r.bezeichnung, sum(s.wert)
from stat.stat_beschaeftigte s
left join stat.klass_region r on r.code = s.region
where s.regelsatz = 'v1'
  and s.zeitraum_art = 'Stichtag'
  and s.zeitraum_bis = (date_trunc('month', %(monat)s::date) + interval '1 month - 1 day')::date
group by rollup (r.bezeichnung)
order by 1 nulls first
"""


def _db() -> psycopg.Connection[Any]:
    url = os.environ.get("UC3_DATABASE_URL", "postgresql://statistik:statistik@localhost:5433/statistik")
    return psycopg.connect(url, autocommit=True)


def _laeufe(conn: psycopg.Connection[Any]) -> dict[str, tuple[str, str]]:
    """Je Lieferung der letzte gültige Lauf: (ergebnis_hash, ergebnis_status)."""
    rows = conn.execute(
        "select distinct on (lieferung) lieferung, ergebnis_hash, ergebnis_status from meta.lauf "
        "where status in ('fertig', 'unveraendert') order by lieferung, id desc"
    ).fetchall()
    return {r[0]: (r[1], r[2]) for r in rows}


def _sql_wert(conn: psycopg.Connection[Any], sql_text: str) -> list[Any]:
    """Führt das SQL aus dem Beleg aus, nur wenn es ein reines SELECT/WITH ist."""
    if not re.match(r"^\s*(select|with)\b", sql_text, re.I) or ";" in sql_text.strip().rstrip(";"):
        return ["nicht ausgeführt: kein einzelnes SELECT"]
    with conn.transaction():
        conn.execute("set transaction read only")
        return [list(r) for r in conn.execute(sql_text).fetchall()]


def main() -> int:
    ordner = Path(tempfile.mkdtemp(prefix="abnahme95-"))
    # Beide Ziele ausdrücklich setzen, ein geerbtes PLATTFORM_ROUTER_PROTOKOLL schriebe sonst woanders hin.
    os.environ["PLATTFORM_PROTOKOLL"] = str(ordner / "modellaufrufe.jsonl")
    router_datei = ordner / "router.jsonl"
    os.environ["PLATTFORM_ROUTER_PROTOKOLL"] = str(router_datei)
    from plattform.router import durchreichen

    conn = _db()
    laeufe = _laeufe(conn)
    ergebnisse: list[dict[str, Any]] = []
    for frage in FRAGEN:
        erg = durchreichen(frage)
        eintrag: dict[str, Any] = {
            "frage": frage,
            "antworten": [a.uc for a in erg.antworten],
            "fehlend": [f"{f.uc}: {f.grund}" for f in erg.fehlend],
            "zahlen": [],
        }
        for antwort in erg.antworten:
            eintrag.setdefault("texte", {})[antwort.uc] = antwort.text[:300]
            eintrag.setdefault("modell", {})[antwort.uc] = antwort.modell
            for zahl in antwort.zahlen:
                beleg = antwort.belege[zahl.beleg]
                pruef: dict[str, Any] = {
                    "uc": antwort.uc,
                    "bezeichnung": zahl.bezeichnung,
                    "wert": zahl.wert,
                    "beleg_uc": beleg.uc,
                    "monat": beleg.monat,
                    "lauf_gleich_meta": (beleg.lauf == laeufe.get(beleg.monat or "", ("", ""))[0])
                    if beleg.lauf
                    else None,
                    "beleg_stand": beleg.stand,
                    "stand_gleich_meta": (beleg.stand == laeufe.get(beleg.monat or "", ("", ""))[1])
                    if beleg.stand
                    else None,
                }
                if beleg.uc == "uc3" and beleg.sql:
                    pruef["beleg_sql_ergebnis"] = _sql_wert(conn, beleg.sql)
                ergebnisse_monat = beleg.monat
                if beleg.uc == "uc3" and ergebnisse_monat:
                    rows = conn.execute(EIGENE, {"monat": f"{ergebnisse_monat}-01"}).fetchall()
                    pruef["eigene_summen"] = {(r[0] or "Österreich"): r[1] for r in rows}
                eintrag["zahlen"].append(pruef)
        ergebnisse.append(eintrag)
    # Fehlt die Datei, ist das ein Befund, kein „ohne Fragetext“.
    router_da = router_datei.is_file()
    router_text = router_datei.read_text(encoding="utf-8") if router_da else ""
    router_zeilen = len([z for z in router_text.splitlines() if z.strip()])
    erwartet = len(FRAGEN) * SCHRITTE_JE_FRAGE
    frei_von_text = (not any(f in router_text for f in FRAGEN)) if router_da else None
    print(
        json.dumps(
            {
                "ergebnisse": ergebnisse,
                "router_datei_da": router_da,
                "router_zeilen": router_zeilen,
                "router_zeilen_erwartet": erwartet,
                "router_ohne_fragetext": frei_von_text,
            },
            ensure_ascii=False,
            default=str,
        )
    )
    return 0 if router_da and router_zeilen == erwartet and frei_von_text else 1


if __name__ == "__main__":
    raise SystemExit(main())
