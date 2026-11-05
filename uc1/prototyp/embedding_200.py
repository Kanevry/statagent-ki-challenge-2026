"""Prototyp #29: Embeddings mit google/embeddinggemma-2 auf 200 Absätzen messen, bevor hochskaliert wird.

Teilbefehle (aus `uc1/`, z. B. `uv run python prototyp/embedding_200.py auswahl`):

- `auswahl`    wählt deterministisch 200 Abschnitte (Seed 42), schreibt `prototyp/auswahl-200.json` (nur IDs)
               und `laufzeit/absaetze-200.jsonl` (mit Text, nicht committen).
- `volltext`   nur PG (Schema `lotse_proto`), ohne Modell: Rangliste je Frage nach `laufzeit/volltext.json`.
- `vergleich`  dicht (768 und 256 Dimensionen) und hybrid (RRF k=60) gegen die Volltext-Rangliste,
               Rang der erwarteten Quelle je Golden-Frage, Recall@5 und MRR@10. Läuft auf m5 (#29).
- `messung`    Ladezeit, Spitzen-RAM, Durchsatz und Anfrage-Latenz je Gerät, jeweils in frischen Prozessen.
- `zaehlung`   Abschnitte im ganzen Korpus nach derselben Einheit, als Grundlage der Hochrechnung.

Einheit „Abschnitt“: Dateien bis 8 KB als Ganzes (Text aus `nutzdaten`), größere je `<absatz>`;
Listen, Tabellen und Schlussteile hängen am vorausgehenden Absatz. Die Tabellen in `lotse.*` bleiben
unberührt, der Volltext-Vergleich arbeitet nur in `lotse_proto`.
"""

from __future__ import annotations

import argparse
import json
import os
import random
import resource
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
from collections.abc import Iterator
from pathlib import Path
from typing import Any

UC1 = Path(__file__).resolve().parents[1]
LAUFZEIT = UC1 / "laufzeit"
AUSWAHL_DATEI = Path(__file__).with_name("auswahl-200.json")
JSONL_DATEI = LAUFZEIT / "absaetze-200.jsonl"
GRENZE_BYTES = 8 * 1024
SEED = 42
ZIEL = 200
ANZAHL_HART = 60  # harte Nachbarn: andere §§ aus BPGG und ASVG
RRF_K = 60
DIMENSIONEN = (768, 256)
BATCH = 8  # Koordinator-Vorgabe nach dem Swap-Vorfall auf dem M4 (#29)
NICHT_TEXT = {"inhaltsvz", "aendprot", "layoutdaten"}

FRAGEN: list[dict[str, str]] = [
    {
        "id": "F7",
        "frage": "Meine Mutter (82) braucht ungefähr 75 Stunden Pflege im Monat. Welche Pflegegeldstufe "
        "ist das und wohin schicke ich den Antrag?",
        "gesetz": "BPGG",
        "para": "4",
    },
    {
        "id": "F2",
        "frage": "Ich bin seit acht Wochen im Krankenstand. Wie lange bekomme ich Krankengeld?",
        "gesetz": "ASVG",
        "para": "139",
    },
    {"id": "F5", "frage": "Ab wann bekomme ich Wochengeld und wie lange?", "gesetz": "ASVG", "para": "162"},
    {
        "id": "F21",
        "frage": "Ich bin auf dem Heimweg von der Arbeit gestürzt. Ist das ein Arbeitsunfall und wer zahlt?",
        "gesetz": "ASVG",
        "para": "175",
    },
    {
        "id": "F6",
        "frage": "Muss ich Rezeptgebühr zahlen? Kann ich befreit werden?",
        "gesetz": "ASVG",
        "para": "136",
    },
]

# 15 weitere Anfragen, nur für die Latenzmessung (zusammen mit den 5 Golden-Fragen: 20).
WEITERE_ANFRAGEN = [
    "Wie beantrage ich Pflegegeld?",
    "Bin ich als Student mitversichert?",
    "Wann bekomme ich Rehabilitationsgeld?",
    "Wer zahlt den Krankentransport?",
    "Wie hoch ist das Krankengeld?",
    "Gilt ein Unfall im Homeoffice als Arbeitsunfall?",
    "Kann ich mich selbst versichern?",
    "Was ist die Höchstbeitragsgrundlage?",
    "Wie lange dauert das Wochengeld nach einer Frühgeburt?",
    "Muss ich für Heilbehelfe einen Selbstbehalt zahlen?",
    "Wer ist in der Unfallversicherung pflichtversichert?",
    "Bekomme ich Pflegegeld im Ausland?",
    "Wann beginnt die Pflichtversicherung?",
    "Was passiert, wenn ich die Krankmeldung zu spät abgebe?",
    "Wie viel kostet die freiwillige Versicherung?",
]


# --------------------------------------------------------------------------------------------- XML-Leser


def _text(el: ET.Element) -> str:
    """Text eines Elements ohne Inhaltsverzeichnis, Änderungsprotokoll und Layoutdaten."""
    teile: list[str] = []

    def lauf(e: ET.Element) -> None:
        if e.tag in NICHT_TEXT:
            return
        if e.text:
            teile.append(e.text)
        for kind in e:
            lauf(kind)
            if kind.tail:
                teile.append(kind.tail)

    lauf(el)
    return " ".join(" ".join(teile).split())


def _bloecke(el: ET.Element) -> Iterator[ET.Element]:
    """Flache Folge der Inhaltsblöcke; Container (alles mit einem `absatz` darunter) werden aufgelöst."""
    for kind in el:
        if kind.tag in NICHT_TEXT:
            continue
        if kind.tag != "absatz" and kind.find(".//absatz") is not None:
            yield from _bloecke(kind)
        else:
            yield kind


def lies_datei(pfad: Path) -> list[dict[str, Any]]:
    """Zerlegt eine SozDok-Datei in Abschnitte (nr 0 = ganze Datei, sonst 1..n je `<absatz>`)."""
    wurzel = ET.parse(pfad).getroot()
    dokid = wurzel.get("dokid") or pfad.stem
    meta = wurzel.find(".//metadaten")
    nutz = wurzel.find(".//nutzdaten")
    if meta is None or nutz is None:
        return []
    abkrvo, gldart, gldnr = meta.get("abkrvo", ""), meta.get("gldart", ""), meta.get("gldnr", "")
    ueberschriften = [_text(u) for u in nutz.iter("ueberschrift")]
    para_ue = [_text(u) for u in nutz.iter("ueberschrift") if u.get("typ") == "para"]
    ueberschrift = (para_ue or ueberschriften or [""])[-1]
    kopf = f"{abkrvo} § {gldnr}" if gldart == "PARA" else f"{abkrvo} {gldart} {gldnr}".strip()
    titel = f"{kopf} {ueberschrift}".strip()
    basis = {"dokid": dokid, "abkrvo": abkrvo, "gldart": gldart, "gldnr": gldnr, "titel": titel}

    if pfad.stat().st_size <= GRENZE_BYTES:
        text = " ".join(_text(b) for b in _bloecke(nutz) if b.tag != "ueberschrift").strip()
        return [{**basis, "nr": 0, "text": text}] if text else []

    stuecke: list[list[str]] = []
    vorlauf: list[str] = []
    for block in _bloecke(nutz):
        if block.tag == "ueberschrift":
            continue
        t = _text(block)
        if block.tag == "absatz":
            stuecke.append([t])
        elif stuecke:
            stuecke[-1].append(t)
        else:
            vorlauf.append(t)
    if stuecke and vorlauf:
        stuecke[0] = vorlauf + stuecke[0]
    ergebnis = []
    for i, teile in enumerate(stuecke, start=1):
        text = " ".join(x for x in teile if x).strip()
        if text:
            ergebnis.append({**basis, "nr": i, "text": text})
    return ergebnis


def _dateien(daten: Path) -> list[Path]:
    return sorted((daten / "Rechtstexte").glob("*.xml"))


def _schluessel(pfad: Path) -> tuple[str, str, str]:
    teile = pfad.name.split("=")
    return teile[0], teile[1], teile[2]


def _daten_dir() -> Path:
    from uc1.config import daten_dir

    return daten_dir()


# ----------------------------------------------------------------------------------------------- Auswahl


def auswahl() -> None:
    dateien = _dateien(_daten_dir())
    rng = random.Random(SEED)
    ziele = {(f["gesetz"], "PARA", f["para"]) for f in FRAGEN}
    gewaehlt: list[dict[str, Any]] = []

    for pfad in dateien:
        if _schluessel(pfad) in ziele:
            gewaehlt += [{**a, "rolle": "quelle"} for a in lies_datei(pfad)]

    def ziehe(kandidaten: list[Path], anzahl: int, rolle: str) -> None:
        kandidaten = list(kandidaten)
        rng.shuffle(kandidaten)
        start = len(gewaehlt)
        for pfad in kandidaten:
            if len(gewaehlt) - start >= anzahl or len(gewaehlt) >= ZIEL:
                return
            abschnitte = lies_datei(pfad)
            if abschnitte:
                gewaehlt.append({**rng.choice(abschnitte), "rolle": rolle})

    hart = [p for p in dateien if _schluessel(p)[:2] in {("BPGG", "PARA"), ("ASVG", "PARA")}]
    hart = [p for p in hart if _schluessel(p) not in ziele]
    ziehe(hart, ANZAHL_HART, "hart")
    hart_menge = set(hart)
    belegt = {a["dokid"] for a in gewaehlt}
    rest = [p for p in dateien if _schluessel(p)[1] != "INH" and p.stem not in belegt and p not in hart_menge]
    ziehe(rest, ZIEL - len(gewaehlt), "zufall")

    AUSWAHL_DATEI.write_text(
        json.dumps(
            {
                "seed": SEED,
                "grenze_bytes": GRENZE_BYTES,
                "fragen": [{k: f[k] for k in ("id", "gesetz", "para")} for f in FRAGEN],
                "abschnitte": [{"dokid": a["dokid"], "nr": a["nr"], "rolle": a["rolle"]} for a in gewaehlt],
            },
            ensure_ascii=False,
            indent=1,
        )
        + "\n",
        encoding="utf-8",
    )
    LAUFZEIT.mkdir(exist_ok=True)
    with JSONL_DATEI.open("w", encoding="utf-8") as f:
        for a in gewaehlt:
            f.write(json.dumps({"id": f"{a['dokid']}#{a['nr']}", **a}, ensure_ascii=False) + "\n")
    rollen = {r: sum(a["rolle"] == r for a in gewaehlt) for r in ("quelle", "hart", "zufall")}
    zeichen = [len(a["text"]) for a in gewaehlt]
    mittel = sum(zeichen) / len(zeichen)
    print(f"{len(gewaehlt)} Abschnitte {rollen}, Zeichen Mittel {mittel:.0f}, max {max(zeichen)}")


def lade_jsonl(pfad: Path = JSONL_DATEI) -> list[dict[str, Any]]:
    return [json.loads(z) for z in pfad.read_text(encoding="utf-8").splitlines() if z.strip()]


# --------------------------------------------------------------------------------------------- Vergleich


def _volltext(abschnitte: list[dict[str, Any]]) -> dict[str, list[str]]:
    import psycopg

    from uc1.config import datenbank_url

    ergebnis: dict[str, list[str]] = {}
    with psycopg.connect(datenbank_url()) as conn, conn.cursor() as cur:
        cur.execute("CREATE SCHEMA IF NOT EXISTS lotse_proto")
        cur.execute(
            """CREATE TABLE IF NOT EXISTS lotse_proto.abschnitt (
                 id text PRIMARY KEY, titel text NOT NULL, text text NOT NULL,
                 tsv tsvector GENERATED ALWAYS AS
                   (to_tsvector('public.lotse_german', titel || ' ' || text)) STORED)"""
        )
        cur.execute("TRUNCATE lotse_proto.abschnitt")
        cur.executemany(
            "INSERT INTO lotse_proto.abschnitt (id, titel, text) VALUES (%s, %s, %s)",
            [(a["id"], a["titel"], a["text"]) for a in abschnitte],
        )
        for f in FRAGEN:
            # ODER-Anfrage aus den Lexemen der Frage; der Cast auf tsquery stemmt nicht ein zweites Mal.
            cur.execute(
                """WITH q AS (SELECT array_to_string(ARRAY(
                       SELECT quote_literal(l) FROM unnest(tsvector_to_array(
                         to_tsvector('public.lotse_german', %s))) AS l), ' | ')::tsquery AS q)
                   SELECT a.id FROM lotse_proto.abschnitt a, q WHERE a.tsv @@ q.q
                   ORDER BY ts_rank_cd(a.tsv, q.q) DESC, a.id""",
                (f["frage"],),
            )
            ergebnis[f["id"]] = [z[0] for z in cur.fetchall()]
    return ergebnis


def _dicht(abschnitte: list[dict[str, Any]], dim: int) -> dict[str, list[str]]:
    import numpy as np

    from uc1.einbettung import als_anfrage, als_dokument, embed

    os.environ["EMBED_DIM"] = str(dim)
    dok = np.array(embed([als_dokument(a["titel"], a["text"]) for a in abschnitte], batch_size=BATCH))
    anfragen = np.array(embed([als_anfrage(f["frage"]) for f in FRAGEN], batch_size=BATCH))
    ids = [a["id"] for a in abschnitte]
    ergebnis = {}
    for f, q in zip(FRAGEN, anfragen, strict=True):
        werte = dok @ q  # beide L2-normalisiert: Skalarprodukt = Cosinus
        ergebnis[f["id"]] = [ids[i] for i in np.argsort(-werte, kind="stable")]
    return ergebnis


def _rrf(*listen: list[str]) -> list[str]:
    punkte: dict[str, float] = {}
    for liste in listen:
        for rang, i in enumerate(liste, start=1):
            punkte[i] = punkte.get(i, 0.0) + 1.0 / (RRF_K + rang)
    return sorted(punkte, key=lambda i: (-punkte[i], i))


def _rang(liste: list[str], quelle: dict[str, str], meta: dict[str, dict[str, Any]]) -> int | None:
    for rang, i in enumerate(liste, start=1):
        a = meta[i]
        if a["abkrvo"] == quelle["gesetz"] and a["gldart"] == "PARA" and a["gldnr"] == quelle["para"]:
            return rang
    return None


def volltext(ausgabe: Path) -> None:
    """Nur PG, kein Modell: läuft auf dem Rechner mit der DB, das Ergebnis geht zum Modellrechner."""
    ergebnis = _volltext(lade_jsonl())
    ausgabe.write_text(json.dumps(ergebnis, ensure_ascii=False), encoding="utf-8")
    print({k: len(v) for k, v in ergebnis.items()})


def vergleich(jsonl: Path, volltext_json: Path) -> None:
    from uc1.einbettung import max_tokens

    abschnitte = lade_jsonl(jsonl)
    meta = {a["id"]: a for a in abschnitte}
    verfahren: dict[str, dict[str, list[str]]] = {"volltext": json.loads(volltext_json.read_text("utf-8"))}
    print(f"max_tokens={max_tokens()} batch={BATCH}\n")
    for dim in DIMENSIONEN:
        verfahren[f"dicht-{dim}"] = _dicht(abschnitte, dim)
        verfahren[f"hybrid-{dim}"] = {
            f["id"]: _rrf(verfahren["volltext"][f["id"]], verfahren[f"dicht-{dim}"][f["id"]]) for f in FRAGEN
        }

    raenge = {v: {f["id"]: _rang(lst[f["id"]], f, meta) for f in FRAGEN} for v, lst in verfahren.items()}
    print("| Verfahren | Recall@5 | MRR@10 |\n|---|---:|---:|")
    kennzahlen = {}
    for v, r in raenge.items():
        recall = sum(1 for x in r.values() if x is not None and x <= 5) / len(FRAGEN)
        mrr = sum(1 / x for x in r.values() if x is not None and x <= 10) / len(FRAGEN)
        kennzahlen[v] = {"recall_at_5": recall, "mrr_at_10": mrr}
        print(f"| {v} | {recall:.2f} | {mrr:.3f} |")
    print("\n| Frage | Quelle | " + " | ".join(raenge) + " |\n|---|---|" + "---:|" * len(raenge))
    for f in FRAGEN:
        zellen = " | ".join(str(raenge[v][f["id"]] or "–") for v in raenge)
        print(f"| {f['id']} | {f['gesetz']} § {f['para']} | {zellen} |")
    print("\nTop 3 je Frage (dicht-768):")
    for f in FRAGEN:
        print(
            f"  {f['id']}: " + "; ".join(meta[i]["titel"][:50] for i in verfahren["dicht-768"][f["id"]][:3])
        )
    treffer_volltext = {k: len(v) for k, v in verfahren["volltext"].items()}
    print(f"\nVolltext-Treffermenge je Frage: {treffer_volltext}")
    LAUFZEIT.mkdir(exist_ok=True)
    (LAUFZEIT / f"vergleich-{max_tokens()}.json").write_text(
        json.dumps(
            {
                "kennzahlen": kennzahlen,
                "raenge": raenge,
                "top5": {v: {k: x[:5] for k, x in lst.items()} for v, lst in verfahren.items()},
            },
            ensure_ascii=False,
            indent=1,
        ),
        encoding="utf-8",
    )


# ----------------------------------------------------------------------------------------------- Messung


def _maxrss_bytes() -> int:
    roh = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return roh if sys.platform == "darwin" else roh * 1024  # macOS: Bytes, Linux: KiB


def einzel(jsonl: Path, nur_anfrage: bool) -> None:
    """Ein Messlauf in diesem Prozess; Gerät und dtype kommen über EMBED_DEVICE und EMBED_DTYPE."""
    t0 = time.perf_counter()
    import torch

    from uc1 import einbettung

    t_import = time.perf_counter() - t0
    t1 = time.perf_counter()
    einbettung._modell()
    t_laden = time.perf_counter() - t1
    einbettung._modell.cache_clear()
    t2 = time.perf_counter()
    modell = einbettung._modell()
    t_warm = time.perf_counter() - t2

    abschnitte = [] if nur_anfrage else lade_jsonl(jsonl)
    dokumente = [einbettung.als_dokument(a["titel"], a["text"]) for a in abschnitte]
    laeufe = []
    gekuerzt = 0
    if dokumente:
        laengen = [len(modell.tokenizer(d)["input_ids"]) for d in dokumente]
        gekuerzt = sum(n > einbettung.max_tokens() for n in laengen)
        einbettung.embed(dokumente[:16], batch_size=BATCH)  # Aufwärmen (MPS-Kernel, Speicherpools)
        for _ in range(2):
            t = time.perf_counter()
            einbettung.embed(dokumente, batch_size=BATCH)
            laeufe.append(time.perf_counter() - t)
    anfragen = [einbettung.als_anfrage(f["frage"]) for f in FRAGEN] + [
        einbettung.als_anfrage(q) for q in WEITERE_ANFRAGEN
    ]
    einbettung.embed(anfragen[:1])
    latenzen = []
    for q in anfragen:
        t = time.perf_counter()
        einbettung.embed([q])
        latenzen.append((time.perf_counter() - t) * 1000)
    latenzen.sort()

    def perzentil(p: float) -> float:
        pos = (len(latenzen) - 1) * p
        unten = int(pos)
        oben = min(unten + 1, len(latenzen) - 1)
        return latenzen[unten] + (latenzen[oben] - latenzen[unten]) * (pos - unten)

    mps_mb = None
    if str(modell.device).startswith("mps"):
        mps_mb = torch.mps.driver_allocated_memory() / 2**20
    bester = min(laeufe) if laeufe else float("nan")
    zeichen = sum(len(d) for d in dokumente)
    print(
        json.dumps(
            {
                "geraet": str(modell.device),
                "dtype": str(next(modell.parameters()).dtype),
                "import_s": round(t_import, 2),
                "laden_s": round(t_laden, 2),
                "laden_warm_s": round(t_warm, 2),
                "max_tokens": einbettung.max_tokens(),
                "batch": BATCH,
                "texte": len(dokumente),
                "gekuerzt": gekuerzt,
                "zeichen": zeichen,
                "durchsatz_laeufe_s": [round(x, 2) for x in laeufe],
                "texte_pro_s": round(len(dokumente) / bester, 1) if laeufe else None,
                "zeichen_pro_s": round(zeichen / bester) if laeufe else None,
                "anfrage_p50_ms": round(perzentil(0.5), 1),
                "anfrage_p95_ms": round(perzentil(0.95), 1),
                "maxrss_mb": round(_maxrss_bytes() / 2**20),
                "mps_treiber_mb": round(mps_mb) if mps_mb is not None else None,
                "torch": torch.__version__,
            }
        )
    )


def messung(jsonl: Path, plan: list[str], ausgabe: Path, nur_anfrage: bool) -> None:
    ergebnisse = []
    for eintrag in plan:
        geraet, _, dtype = eintrag.partition(":")
        env = {**os.environ, "EMBED_DEVICE": geraet, "EMBED_DTYPE": dtype or "float32", "HF_HUB_OFFLINE": "1"}
        t = time.perf_counter()
        lauf = subprocess.run(
            [sys.executable, __file__, "einzel", "--jsonl", str(jsonl)]
            + (["--nur-anfrage"] if nur_anfrage else []),
            env=env,
            capture_output=True,
            text=True,
            check=True,
            timeout=1800,
        )
        zeile = json.loads(lauf.stdout.strip().splitlines()[-1])
        zeile["prozess_s"] = round(time.perf_counter() - t, 1)
        zeile["lauf"] = eintrag
        ergebnisse.append(zeile)
        print(json.dumps(zeile), flush=True)
    ausgabe.parent.mkdir(parents=True, exist_ok=True)
    ausgabe.write_text(json.dumps(ergebnisse, indent=1), encoding="utf-8")


# ---------------------------------------------------------------------------------------------- Zählung


def zaehlung() -> None:
    dateien = _dateien(_daten_dir())
    abschnitte = klein = gross = roh_absaetze = zeichen = 0
    for pfad in dateien:
        teile = lies_datei(pfad)
        abschnitte += len(teile)
        zeichen += sum(len(t["titel"]) + len(t["text"]) + 18 for t in teile)  # 18 = Präfix-Länge
        if pfad.stat().st_size <= GRENZE_BYTES:
            klein += 1
        else:
            gross += 1
            roh_absaetze += sum(1 for _ in ET.parse(pfad).getroot().iter("absatz"))
    ergebnis = {
        "dateien": len(dateien),
        "dateien_bis_8kb": klein,
        "dateien_ueber_8kb": gross,
        "absatz_elemente_in_grossen": roh_absaetze,
        "schaetzung_klein_plus_absatz": klein + roh_absaetze,
        "abschnitte_nicht_leer": abschnitte,
        "zeichen_mit_praefix": zeichen,
    }
    (LAUFZEIT / "korpus-zaehlung.json").write_text(json.dumps(ergebnis, indent=1), encoding="utf-8")
    print(json.dumps(ergebnis))


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    sub = parser.add_subparsers(dest="befehl", required=True)
    sub.add_parser("auswahl")
    p_voll = sub.add_parser("volltext")
    p_voll.add_argument("--ausgabe", type=Path, default=LAUFZEIT / "volltext.json")
    p_vergl = sub.add_parser("vergleich")
    p_vergl.add_argument("--jsonl", type=Path, default=JSONL_DATEI)
    p_vergl.add_argument("--volltext", type=Path, default=LAUFZEIT / "volltext.json")
    sub.add_parser("zaehlung")
    p_einzel = sub.add_parser("einzel")
    p_einzel.add_argument("--jsonl", type=Path, default=JSONL_DATEI)
    p_einzel.add_argument("--nur-anfrage", action="store_true")
    p_mess = sub.add_parser("messung")
    p_mess.add_argument("--jsonl", type=Path, default=JSONL_DATEI)
    p_mess.add_argument("--plan", default="mps,mps,cpu", help="Läufe geraet[:dtype], kommagetrennt")
    p_mess.add_argument("--ausgabe", type=Path, default=LAUFZEIT / "messung.json")
    p_mess.add_argument("--nur-anfrage", action="store_true", help="nur Anfrage-Latenz, keine Dokumente")
    args = parser.parse_args()
    if args.befehl == "auswahl":
        auswahl()
    elif args.befehl == "volltext":
        volltext(args.ausgabe)
    elif args.befehl == "vergleich":
        vergleich(args.jsonl, args.volltext)
    elif args.befehl == "zaehlung":
        zaehlung()
    elif args.befehl == "einzel":
        einzel(args.jsonl, args.nur_anfrage)
    else:
        messung(args.jsonl, args.plan.split(","), args.ausgabe, args.nur_anfrage)


if __name__ == "__main__":
    main()
