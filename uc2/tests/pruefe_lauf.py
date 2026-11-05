"""Unabhängiges Prüfskript (Oracle) für einen Verhandlungslauf (Issue #44, PRD § 3 „Verhandlung (S5)“).

Importiert keinen uc2-Laufzeitcode, nur Standardbibliothek, psycopg und jsonschema. Es liest `uc2.fall`,
`uc2.teilnahme` und `uc2.ereignis`, den Akteurs-Pool aus den Dateinamen `uc2/akteure/*.md` und das Zugschema
`uc2/src/uc2/akteure/zug.schema.json` als Datei. Das Zahlenmuster ist hier eigenständig formuliert.

Aufruf (aus `uc2/`):
    uv run python tests/pruefe_lauf.py --fall <fall_id> [--db healthpolicy] [--json]

Verbindung wie `uc2.db` (hier nachgebaut): `UC2_DATABASE_URL` gewinnt, sonst `PG*`-Variablen (Standard
localhost:5433, statistik/statistik) mit DB `UC2_DB` bzw. `healthpolicy`; `--db` ersetzt nur den DB-Namen.
Exit 0: alle Prüfungen bestanden. Exit 1: mindestens ein Verstoß. Exit 2: Betriebsfehler (DB, Fall fehlt).

Prüfungen:
1. `teilnahme`: höchstens 6 Akteure eingeladen, jeder Pool-Akteur genau einmal, jeder nicht gewählte mit
   Begründung, kein Akteur außerhalb des Pools.
2. `runden`: mindestens 3 Runden; je Runde und eingeladenem Akteur genau ein `zug` oder eine
   `ungueltige_ausgabe`; jeder Zug ab Runde 2 nennt in `bezug_auf` einen anderen Teilnehmer.
3. `schema`: jeder `zug` ist gültig gegen `zug.schema.json` (sonst hätte der Lauf `ungueltige_ausgabe`
   schreiben müssen).
4. `zahlen`: jede Zahl mit Einheit in einer Begründung steht betragsgleich (0,05) in `zahlen[]` mit gültiger
   Quelle, oder sie ist als `zahl_ohne_beleg` markiert. Steht sie in `zahlen[]` mit ungültiger Quelle, genügt
   die Markierung `beleg_ungueltig` dieser Quelle (Prüfung 6).
5. `experte`: jede Zahl mit Quelle `experte` gleicht betragsmäßig einem Wert aus dem Ereignis `experte` auf
   0,05, sonst gibt es ein Ereignis `zahl_widerspruch` mit diesem Wert.
6. `belege`: jede Beleg-ID in `themen[].beleg_ids` und `zahlen[].quelle` stammt aus dem Ereignis `belege`
   desselben Akteurs und derselben Runde, sonst gibt es `beleg_ungueltig` mit dieser ID.
7. `protokoll`: `seq` lückenlos ab 1, gespeicherter Fallstatus `fertig`.

Datenschutz: Ausgegeben werden nur IDs, Runden, Zahlen und Prüfungsnamen, kein Beleg- oder Begründungstext.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

import jsonschema
import psycopg
from psycopg.conninfo import make_conninfo

UC2 = Path(__file__).resolve().parents[1]
AKTEURE = UC2 / "akteure"
ZUG_SCHEMA = UC2 / "src" / "uc2" / "akteure" / "zug.schema.json"

MAX_AKTEURE = 6
MIN_RUNDEN = 3
TOLERANZ = 0.05
JAHR_VON, JAHR_BIS = 2000, 2040
MAX_LISTE = 40

# Eigenes Zahlenmuster: eine vollständige Zifferngruppe (nicht mitten in einer anderen Zahl beginnend),
# danach höchstens ein Leerzeichen und eine Einheit aus PRD S5. Anders als im Lauf wird die ganze Gruppe
# gelesen („1.234,5 Mio“ ist 1234,5 und nicht 234,5).
ZIFFERN = re.compile(r"(?<![\d.,])\d+(?:[.,]\d+)*")
EINHEIT = re.compile(r"\s?(?:%|Prozent|Mio|Mrd|EUR|€|Tage|Stellen)")


# --------------------------------------------------------------------------------------------- Hilfen


def zahlwert(gruppe: str) -> float | None:
    """Zifferngruppe als Zahl: ein Trenner ist das Dezimalzeichen; mehrere sind deutsche Tausenderpunkte,
    höchstens mit einem Dezimalkomma am Ende („1.234,5“). Andere Folgen gelten als unlesbar."""
    trenner = "".join(c for c in gruppe if c in ".,")
    if len(trenner) <= 1:
        return float(gruppe.replace(",", "."))
    if set(trenner[:-1]) == {"."} and trenner[-1] in ".,":
        return float(gruppe.replace(".", "").replace(",", "."))
    return None


def zahlen_mit_einheit(text: str) -> list[tuple[str, float | None]]:
    """(Fundtext, Wert) je Zahl mit Einheit; ganze Zahlen 2000–2040 gelten als Jahre und entfallen."""
    funde = []
    for m in ZIFFERN.finditer(text):
        einheit = EINHEIT.match(text, m.end())
        if einheit is None:
            continue
        gruppe = m.group(0)
        if gruppe.isdigit() and JAHR_VON <= int(gruppe) <= JAHR_BIS:
            continue
        funde.append((gruppe + einheit.group(0), zahlwert(gruppe)))
    return funde


def gleich(a: float, b: float) -> bool:
    return abs(abs(a) - abs(b)) <= TOLERANZ


def alle_zahlen(knoten: object) -> list[float]:
    """Alle Zahlen eines JSON-Baums ohne Wahrheitswerte."""
    if isinstance(knoten, bool):
        return []
    if isinstance(knoten, int | float):
        return [float(knoten)]
    if isinstance(knoten, dict):
        return [z for v in knoten.values() for z in alle_zahlen(v)]
    if isinstance(knoten, list):
        return [z for v in knoten for z in alle_zahlen(v)]
    return []


def pool() -> list[str]:
    return sorted(p.stem for p in AKTEURE.glob("*.md"))


def ergebnis(name: str, verstoesse: list[str], **zahlen: int) -> dict[str, Any]:
    return {
        "pruefung": name,
        "ok": not verstoesse,
        "verstoesse": verstoesse[:MAX_LISTE],
        **zahlen,
        "verstoesse_gesamt": len(verstoesse),
    }


# ------------------------------------------------------------------------------------------- Laden


def lade_lauf(conn: psycopg.Connection[Any], fall_id: int) -> dict[str, Any] | None:
    fall = conn.execute("select status from uc2.fall where fall_id = %s", (fall_id,)).fetchone()
    if fall is None:
        return None
    teilnahme = conn.execute(
        "select akteur, eingeladen, begruendung from uc2.teilnahme where fall_id = %s order by akteur",
        (fall_id,),
    ).fetchall()
    ereignisse = [
        {"seq": z[0], "runde": z[1], "art": z[2], "akteur": z[3], "daten": z[4]}
        for z in conn.execute(
            "select seq, runde, art, akteur, daten from uc2.ereignis where fall_id = %s order by seq",
            (fall_id,),
        )
    ]
    return {"status": fall[0], "teilnahme": teilnahme, "ereignisse": ereignisse}


class Lauf:
    """Ereignisse nach Runde und Akteur aufbereitet."""

    def __init__(self, daten: dict[str, Any]) -> None:
        self.status: str = daten["status"]
        self.teilnahme: list[tuple[str, bool, str]] = [tuple(z) for z in daten["teilnahme"]]
        self.ereignisse: list[dict[str, Any]] = daten["ereignisse"]
        self.teilnehmer = sorted(a for a, eingeladen, _ in self.teilnahme if eingeladen)
        self.runden = sorted({e["runde"] for e in self.ereignisse if e["art"] == "runde" and e["runde"]})
        self.zuege: list[dict[str, Any]] = [e for e in self.ereignisse if e["art"] == "zug"]
        self.belege: dict[tuple[int, str], set[str]] = {}
        self.marken: dict[str, list[dict[str, Any]]] = defaultdict(list)
        self.experte: dict[str, Any] | None = None
        for e in self.ereignisse:
            if e["art"] == "belege" and e["akteur"]:
                ids = {b.get("beleg_id") for b in e["daten"].get("belege", []) if isinstance(b, dict)}
                self.belege[(e["runde"], e["akteur"])] = {i for i in ids if isinstance(i, str)}
            elif e["art"] == "experte":
                self.experte = e["daten"]
            elif e["art"] in ("zahl_ohne_beleg", "beleg_ungueltig", "zahl_widerspruch", "ungueltige_ausgabe"):
                self.marken[e["art"]].append(e)

    def markiert(self, art: str, runde: int, akteur: str) -> list[dict[str, Any]]:
        return [m["daten"] for m in self.marken[art] if m["runde"] == runde and m["akteur"] == akteur]


# ---------------------------------------------------------------------------------------- Prüfungen


def pruefe_teilnahme(lauf: Lauf, pool_ids: list[str]) -> dict[str, Any]:
    verstoesse = []
    genannt = [a for a, _, _ in lauf.teilnahme]
    if len(lauf.teilnehmer) > MAX_AKTEURE:
        verstoesse.append(f"{len(lauf.teilnehmer)} Akteure eingeladen, höchstens {MAX_AKTEURE}")
    if not lauf.teilnehmer:
        verstoesse.append("kein Akteur eingeladen")
    for aid in pool_ids:
        if genannt.count(aid) != 1:
            verstoesse.append(f"Pool-Akteur {aid} steht {genannt.count(aid)}-mal in uc2.teilnahme")
    for aid in sorted(set(genannt) - set(pool_ids)):
        verstoesse.append(f"Akteur {aid} steht in uc2.teilnahme, aber nicht im Pool uc2/akteure/")
    for aid, eingeladen, begruendung in lauf.teilnahme:
        if not eingeladen and not (begruendung or "").strip():
            verstoesse.append(f"nicht gewählter Akteur {aid} ohne Begründung")
    return ergebnis("teilnahme", verstoesse, pool=len(pool_ids), eingeladen=len(lauf.teilnehmer))


def pruefe_runden(lauf: Lauf) -> dict[str, Any]:
    verstoesse = []
    if len(lauf.runden) < MIN_RUNDEN:
        verstoesse.append(f"{len(lauf.runden)} Runden, mindestens {MIN_RUNDEN}")
    for runde in lauf.runden:
        for aid in lauf.teilnehmer:
            zuege = [z for z in lauf.zuege if z["runde"] == runde and z["akteur"] == aid]
            ungueltig = lauf.markiert("ungueltige_ausgabe", runde, aid)
            if len(zuege) + len(ungueltig) != 1:
                verstoesse.append(
                    f"Runde {runde}, {aid}: {len(zuege)} Züge und {len(ungueltig)} ungueltige_ausgabe, "
                    "erwartet genau eines"
                )
    for z in lauf.zuege:
        if z["akteur"] not in lauf.teilnehmer:
            verstoesse.append(f"seq {z['seq']}: Zug von {z['akteur']}, der nicht eingeladen ist")
        if z["runde"] is None or z["runde"] < 2:
            continue
        bezug = (z["daten"].get("zug") or {}).get("bezug_auf")
        andere = set(lauf.teilnehmer) - {z["akteur"]}
        if not isinstance(bezug, list) or not set(map(str, bezug)) & andere:
            verstoesse.append(
                f"seq {z['seq']} (Runde {z['runde']}, {z['akteur']}): bezug_auf ohne anderen Teilnehmer"
            )
    return ergebnis("runden", verstoesse, runden=len(lauf.runden), zuege=len(lauf.zuege))


def gueltige_zuege(
    lauf: Lauf, validator: jsonschema.protocols.Validator
) -> tuple[dict[str, Any], list[dict]]:
    verstoesse = []
    gueltig = []
    for z in lauf.zuege:
        zug = z["daten"].get("zug")
        fehler = sorted(validator.iter_errors(zug), key=lambda f: list(f.absolute_path))
        if fehler:
            pfad = "/".join(map(str, fehler[0].absolute_path)) or "(Wurzel)"
            verstoesse.append(
                f"seq {z['seq']} (Runde {z['runde']}, {z['akteur']}): nicht schemagültig an {pfad}, "
                "aber nicht als ungueltige_ausgabe markiert"
            )
        else:
            gueltig.append(z)
    return ergebnis("schema", verstoesse, zuege=len(lauf.zuege), gueltig=len(gueltig)), gueltig


def pruefe_zahlen(lauf: Lauf, zuege: list[dict[str, Any]]) -> dict[str, Any]:
    verstoesse = []
    geprueft = 0
    for z in zuege:
        runde, aid, zug = z["runde"], z["akteur"], z["daten"]["zug"]
        erlaubt = lauf.belege.get((runde, aid), set())
        markiert_ungueltig = {m.get("beleg_id") for m in lauf.markiert("beleg_ungueltig", runde, aid)}
        ohne_beleg = lauf.markiert("zahl_ohne_beleg", runde, aid)
        for t in zug["themen"]:
            for fund, wert in zahlen_mit_einheit(t["begruendung"]):
                geprueft += 1
                ort = f"seq {z['seq']} (Runde {runde}, {aid}, Thema {t['thema']})"
                if wert is None:
                    verstoesse.append(f"{ort}: Zahl {fund!r} nicht lesbar")
                    continue
                passend = [e for e in zug["zahlen"] if gleich(float(e["wert"]), wert)]
                if any(e["quelle"] == "experte" or e["quelle"] in erlaubt for e in passend):
                    continue
                if any(e["quelle"] in markiert_ungueltig for e in passend):
                    continue
                marken = [
                    m
                    for m in ohne_beleg
                    if m.get("thema") == t["thema"]
                    and any(
                        w is not None and gleich(w, wert) for _, w in zahlen_mit_einheit(str(m.get("fund")))
                    )
                ]
                if not marken:
                    verstoesse.append(
                        f"{ort}: Zahl {fund!r} weder in zahlen[] mit Quelle noch zahl_ohne_beleg"
                    )
    return ergebnis("zahlen", verstoesse, zahlen=geprueft)


def pruefe_experte(lauf: Lauf, zuege: list[dict[str, Any]]) -> dict[str, Any]:
    verstoesse = []
    if lauf.experte is None:
        verstoesse.append("kein Ereignis experte")
    werte = alle_zahlen(lauf.experte or {})
    geprueft = 0
    for z in zuege:
        for e in z["daten"]["zug"]["zahlen"]:
            if e["quelle"] != "experte":
                continue
            geprueft += 1
            wert = float(e["wert"])
            if any(gleich(wert, w) for w in werte):
                continue
            marken = lauf.markiert("zahl_widerspruch", z["runde"], z["akteur"])
            if not any(isinstance(m.get("wert"), int | float) and gleich(m["wert"], wert) for m in marken):
                verstoesse.append(
                    f"seq {z['seq']} (Runde {z['runde']}, {z['akteur']}): Experten-Zahl {wert} weicht ab, "
                    "aber kein zahl_widerspruch"
                )
    return ergebnis("experte", verstoesse, zahlen=geprueft, experten_werte=len(werte))


def pruefe_belege(lauf: Lauf, zuege: list[dict[str, Any]]) -> dict[str, Any]:
    verstoesse = []
    geprueft = 0
    for z in zuege:
        runde, aid, zug = z["runde"], z["akteur"], z["daten"]["zug"]
        erlaubt = lauf.belege.get((runde, aid), set())
        markiert = [m.get("beleg_id") for m in lauf.markiert("beleg_ungueltig", runde, aid)]
        ids = [b for t in zug["themen"] for b in t["beleg_ids"]]
        ids += [e["quelle"] for e in zug["zahlen"] if e["quelle"] != "experte"]
        for bid in ids:
            geprueft += 1
            if bid not in erlaubt and bid not in markiert:
                verstoesse.append(
                    f"seq {z['seq']} (Runde {runde}, {aid}): Beleg {bid} nicht geholt, kein beleg_ungueltig"
                )
    return ergebnis("belege", verstoesse, beleg_ids=geprueft)


def pruefe_protokoll(lauf: Lauf) -> dict[str, Any]:
    verstoesse = []
    seqs = [e["seq"] for e in lauf.ereignisse]
    if seqs != list(range(1, len(seqs) + 1)):
        luecke = next((i + 1 for i, s in enumerate(seqs) if s != i + 1), None)
        verstoesse.append(f"seq nicht lückenlos ab 1 (erste Abweichung an Stelle {luecke})")
    if lauf.status != "fertig":
        verstoesse.append(f"Fallstatus {lauf.status}, erwartet fertig")
    return ergebnis("protokoll", verstoesse, ereignisse=len(seqs))


def pruefe(conn: psycopg.Connection[Any], fall_id: int) -> list[dict[str, Any]] | None:
    daten = lade_lauf(conn, fall_id)
    if daten is None:
        return None
    lauf = Lauf(daten)
    schema = json.loads(ZUG_SCHEMA.read_text(encoding="utf-8"))
    validator = jsonschema.Draft202012Validator(schema)
    schema_erg, gueltig = gueltige_zuege(lauf, validator)
    return [
        pruefe_teilnahme(lauf, pool()),
        pruefe_runden(lauf),
        schema_erg,
        pruefe_zahlen(lauf, gueltig),
        pruefe_experte(lauf, gueltig),
        pruefe_belege(lauf, gueltig),
        pruefe_protokoll(lauf),
    ]


# ------------------------------------------------------------------------------------------------ Main


def verbinden(db: str | None) -> psycopg.Connection[Any]:
    """Nachbau von `uc2.db.conninfo` (Import von uc2 ist hier verboten), wie in `pruefe_index.py`."""
    url = os.environ.get("UC2_DATABASE_URL")
    if url:
        return psycopg.connect(make_conninfo(url, dbname=db) if db else make_conninfo(url))
    return psycopg.connect(
        host=os.environ.get("PGHOST", "localhost"),
        port=int(os.environ.get("PGPORT", "5433")),
        user=os.environ.get("PGUSER", "statistik"),
        password=os.environ.get("PGPASSWORD", "statistik"),
        dbname=db or os.environ.get("UC2_DB", "healthpolicy"),
    )


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Unabhängige Prüfung eines Verhandlungslaufs (#44)")
    ap.add_argument("--fall", required=True, type=int, help="fall_id aus uc2.fall")
    ap.add_argument(
        "--db", default=None, help="DB-Name (Standard: aus UC2_DATABASE_URL, sonst UC2_DB oder healthpolicy)"
    )
    ap.add_argument("--json", action="store_true", help="maschinenlesbare Zusammenfassung")
    args = ap.parse_args(argv)
    try:
        with verbinden(args.db) as conn:
            ergebnisse = pruefe(conn, args.fall)
    except (psycopg.Error, OSError) as fehler:
        print(f"Betriebsfehler: {type(fehler).__name__}: {fehler}", file=sys.stderr)
        return 2
    if ergebnisse is None:
        print(f"Fall {args.fall} nicht gefunden", file=sys.stderr)
        return 2
    ok = all(e["ok"] for e in ergebnisse)
    if args.json:
        print(
            json.dumps(
                {"ok": ok, "fall_id": args.fall, "pruefungen": ergebnisse}, ensure_ascii=False, indent=2
            )
        )
    else:
        for e in ergebnisse:
            kopf = {k: v for k, v in e.items() if isinstance(v, int) and not isinstance(v, bool)}
            print(f"[{'OK' if e['ok'] else 'FEHLER'}] {e['pruefung']}  {kopf}")
            for v in e["verstoesse"]:
                print(f"    - {v}")
        print("ERGEBNIS:", "alle Prüfungen bestanden" if ok else "Verstöße")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
