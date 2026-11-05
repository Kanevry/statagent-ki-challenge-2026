"""Vollindex der dichten Vektoren (google/embeddinggemma-2) für lotse.vektor (#29).

Aufruf aus `uc1/`: `uv run python -m uc1.vektoren <unterbefehl>`.

- `export --ausgabe DATEI.jsonl`  Abschnitte als `{text_hash, eingabe}`, je Hash einmal, sortiert nach Hash.
- `berechnen --eingabe DATEI.jsonl --ausgabe PREFIX`  bettet ein (768 Dimensionen, float32) und schreibt
  `PREFIX.hashes.txt`, `PREFIX.768.npy` und `PREFIX.meta.json`. Teilstücke unter `PREFIX.teile/` machen den
  Lauf wiederaufnehmbar. Rechenintensiv: läuft auf Rechner B, nie auf Rechner A
  (Demo-Rechner) (Swap-Vorfall #29).
- `import --prefix PREFIX [--dims 768,256]`  löscht und lädt je modell/dim per COPY nach lotse.vektor.
- `status`  Vektoren je modell/dim gegen die eindeutigen Text-Hashes der Abschnitte.

256 Dimensionen entstehen aus 768 durch Kürzen auf die ersten 256 Werte und L2-Normieren; das ist genau
die Matryoshka-Kürzung, die `truncate_dim` im Modell selbst rechnet.
"""

from __future__ import annotations

import argparse
import json
import os
import resource
import sys
import time
from collections.abc import Callable, Iterable, Sequence
from pathlib import Path
from typing import Any

import numpy as np
import numpy.typing as npt
import psycopg
from psycopg import sql

from uc1.db import verbinde
from uc1.einbettung import MODELL_ID, VOLLE_DIMENSION, als_dokument

Matrix = npt.NDArray[np.float32]
Einbetter = Callable[[list[str]], list[list[float]]]

TABELLE = "lotse.vektor"
TEILGROESSE = 512  # Texte je Teilstück; ein Abbruch kostet höchstens so viele Texte
ERLAUBTE_DIMS = (768, 512, 256, 128)


# --- reine Funktionen -------------------------------------------------------------------------------


def eindeutig_sortiert(zeilen: Iterable[tuple[str, str, str]]) -> list[tuple[str, str]]:
    """Aus `(text_hash, kontext, text)` je Hash genau ein `(text_hash, eingabe)`, sortiert nach Hash.

    Sortiert wird in Python (Codepunkte), damit die Reihenfolge nicht von der Collation der DB abhängt.
    Gleicher Hash heißt laut DDL gleicher Kontext und Text; der erste Treffer gilt.
    """
    je_hash: dict[str, str] = {}
    for text_hash, kontext, text in zeilen:
        if text_hash not in je_hash:
            je_hash[text_hash] = als_dokument(kontext, text)
    return sorted(je_hash.items())


def kuerze(matrix: Matrix, dim: int) -> Matrix:
    """Matryoshka-Kürzung: die ersten `dim` Spalten, danach je Zeile L2-normiert (float32)."""
    if dim not in ERLAUBTE_DIMS or dim > matrix.shape[1]:
        raise ValueError(f"Dimension {dim} nicht ableitbar aus {matrix.shape[1]}")
    teil = matrix[:, :dim].astype(np.float64)
    normen = np.linalg.norm(teil, axis=1, keepdims=True)
    if np.any(normen == 0):
        raise ValueError("Nullvektor kann nicht normiert werden")
    return (teil / normen).astype(np.float32)


def rechenreihenfolge(eingaben: Sequence[str], hashes: Sequence[str]) -> list[int]:
    """Indizes nach (Länge, Hash): ähnlich lange Texte landen im selben Batch, das spart Padding.

    Die Reihenfolge ist deterministisch, damit die Teilstücke über einen Abbruch hinweg passen.
    """
    return sorted(range(len(eingaben)), key=lambda i: (len(eingaben[i]), hashes[i]))


# --- Dateien ----------------------------------------------------------------------------------------


def lies_jsonl(pfad: Path) -> list[tuple[str, str]]:
    paare: list[tuple[str, str]] = []
    with pfad.open(encoding="utf-8") as datei:
        for zeile in datei:
            if zeile.strip():
                obj = json.loads(zeile)
                paare.append((str(obj["text_hash"]), str(obj["eingabe"])))
    return paare


def schreibe_jsonl(pfad: Path, paare: Iterable[tuple[str, str]]) -> int:
    pfad.parent.mkdir(parents=True, exist_ok=True)
    anzahl = 0
    tmp = pfad.with_name(pfad.name + ".tmp")
    with tmp.open("w", encoding="utf-8") as datei:
        for text_hash, eingabe in paare:
            datei.write(json.dumps({"text_hash": text_hash, "eingabe": eingabe}, ensure_ascii=False) + "\n")
            anzahl += 1
    tmp.replace(pfad)
    return anzahl


def _speichere_npy(pfad: Path, matrix: Matrix) -> None:
    tmp = pfad.with_name(pfad.name + ".tmp")
    with tmp.open("wb") as datei:
        np.save(datei, matrix)
    tmp.replace(pfad)


def _speichere_text(pfad: Path, inhalt: str) -> None:
    tmp = pfad.with_name(pfad.name + ".tmp")
    tmp.write_text(inhalt, encoding="utf-8")
    tmp.replace(pfad)


def lies_vektoren(prefix: Path) -> tuple[list[str], Matrix]:
    hashes = Path(f"{prefix}.hashes.txt").read_text(encoding="utf-8").split()
    matrix = np.load(Path(f"{prefix}.{VOLLE_DIMENSION}.npy")).astype(np.float32, copy=False)
    if matrix.shape != (len(hashes), VOLLE_DIMENSION):
        raise ValueError(f"Form {matrix.shape} passt nicht zu {len(hashes)} Hashes")
    if len(set(hashes)) != len(hashes):
        raise ValueError("doppelte Hashes in der Vektordatei")
    if not np.all(np.isfinite(matrix)):
        raise ValueError("Vektordatei enthält NaN oder Inf")
    return hashes, matrix


# --- Berechnen (nur Rechner B) -----------------------------------------------------------------------------


def _speicher_mb() -> dict[str, float]:
    # macOS meldet ru_maxrss in Bytes, Linux in KB.
    roh = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    rss = roh / 1e6 if sys.platform == "darwin" else roh / 1e3
    werte = {"rss_spitze_mb": round(rss, 1)}
    torch = sys.modules.get("torch")
    if torch is not None and torch.backends.mps.is_available():
        werte["mps_treiber_mb"] = round(torch.mps.driver_allocated_memory() / 1e6, 1)
    return werte


def _leere_mps_cache() -> None:
    # Ohne Leeren wuchs der MPS-Treiberspeicher im Vollindex mit den langen Texten bis 47 GB (#29).
    torch = sys.modules.get("torch")
    if torch is not None and torch.backends.mps.is_available():
        torch.mps.empty_cache()


def _modell_einbetter(batch_size: int) -> Einbetter:
    from uc1 import einbettung

    def einbetten(texte: list[str]) -> list[list[float]]:
        return einbettung.embed(texte, batch_size=batch_size)

    return einbetten


def berechne(
    paare: Sequence[tuple[str, str]],
    prefix: Path,
    einbetten: Einbetter,
    *,
    teilgroesse: int = TEILGROESSE,
    log: Callable[[str], None] = print,
) -> dict[str, Any]:
    """Bettet alle Eingaben ein und schreibt die Vektoren in Hash-Reihenfolge nach `PREFIX.768.npy`.

    Vorhandene, passende Teilstücke unter `PREFIX.teile/` werden übernommen statt neu gerechnet.
    """
    hashes = [h for h, _ in paare]
    eingaben = [e for _, e in paare]
    if len(set(hashes)) != len(hashes):
        raise ValueError("Eingabe enthält doppelte Hashes")
    reihenfolge = rechenreihenfolge(eingaben, hashes)
    teile_dir = Path(f"{prefix}.teile")
    teile_dir.mkdir(parents=True, exist_ok=True)
    ergebnis = np.empty((len(paare), VOLLE_DIMENSION), dtype=np.float32)
    start = time.monotonic()
    gerechnet = uebernommen = 0
    for nr, anfang in enumerate(range(0, len(reihenfolge), teilgroesse)):
        idx = reihenfolge[anfang : anfang + teilgroesse]
        teil_hashes = [hashes[i] for i in idx]
        npy = teile_dir / f"teil-{nr:05d}.npy"
        txt = teile_dir / f"teil-{nr:05d}.hashes.txt"
        if npy.exists() and txt.exists() and txt.read_text(encoding="utf-8").split() == teil_hashes:
            teil = np.load(npy)
            uebernommen += len(idx)
        else:
            teil = np.asarray(einbetten([eingaben[i] for i in idx]), dtype=np.float32)
            if teil.shape != (len(idx), VOLLE_DIMENSION):
                raise ValueError(f"Teilstück {nr}: Form {teil.shape}, erwartet ({len(idx)}, 768)")
            _speichere_npy(npy, teil)
            _speichere_text(txt, "\n".join(teil_hashes) + "\n")
            gerechnet += len(idx)
            _leere_mps_cache()
        ergebnis[idx] = teil
        fertig = anfang + len(idx)
        dauer = time.monotonic() - start
        rate = gerechnet / dauer if dauer > 0 else 0.0
        log(
            f"teil {nr} fertig {fertig}/{len(paare)} gerechnet {gerechnet} uebernommen {uebernommen} "
            f"{dauer:.0f} s {rate:.1f} texte/s {json.dumps(_speicher_mb())}"
        )
    if not np.all(np.isfinite(ergebnis)):
        raise ValueError("Ergebnis enthält NaN oder Inf")
    _speichere_npy(Path(f"{prefix}.{VOLLE_DIMENSION}.npy"), ergebnis)
    _speichere_text(Path(f"{prefix}.hashes.txt"), "\n".join(hashes) + "\n")
    dauer = time.monotonic() - start
    return {
        "anzahl": len(paare),
        "gerechnet": gerechnet,
        "uebernommen": uebernommen,
        "dauer_s": round(dauer, 1),
        "texte_pro_s": round(gerechnet / dauer, 2) if dauer > 0 else None,
        "zeichen": sum(len(e) for e in eingaben),
        **_speicher_mb(),
    }


# --- Datenbank --------------------------------------------------------------------------------------


def lies_abschnitte(conn: psycopg.Connection) -> list[tuple[str, str, str]]:
    zeilen = conn.execute("SELECT text_hash, kontext, text FROM lotse.abschnitt WHERE text <> ''").fetchall()
    return [(str(h), str(k), str(t)) for h, k, t in zeilen]


def _tabelle(name: str) -> sql.Composable:
    return sql.Identifier(*name.split("."))


def schreibe(
    conn: psycopg.Connection,
    hashes: Sequence[str],
    matrix: Matrix,
    dims: Sequence[int],
    *,
    modell: str = MODELL_ID,
    tabelle: str = TABELLE,
) -> dict[int, int]:
    """Löscht je dim die Zeilen dieses Modells und lädt sie per COPY neu; eine Transaktion je Aufruf."""
    geschrieben: dict[int, int] = {}
    ziel = _tabelle(tabelle)
    for dim in dims:
        werte = matrix if dim == matrix.shape[1] else kuerze(matrix, dim)
        conn.execute(sql.SQL("DELETE FROM {} WHERE modell = %s AND dim = %s").format(ziel), (modell, dim))
        with conn.cursor().copy(
            sql.SQL("COPY {} (text_hash, modell, dim, v) FROM STDIN (FORMAT BINARY)").format(ziel)
        ) as copy:
            copy.set_types(["text", "text", "int4", "float4[]"])
            for text_hash, zeile in zip(hashes, werte, strict=True):
                copy.write_row((text_hash, modell, dim, zeile.tolist()))
        geschrieben[dim] = len(hashes)
    conn.commit()
    return geschrieben


def zaehle(conn: psycopg.Connection, *, tabelle: str = TABELLE) -> dict[str, Any]:
    """Abdeckung je modell/dim: wie viele eindeutige Abschnitts-Hashes einen Vektor haben."""
    ziel = _tabelle(tabelle)
    hashes = conn.execute("SELECT count(DISTINCT text_hash) FROM lotse.abschnitt WHERE text <> ''").fetchone()
    abschnitte = conn.execute("SELECT count(*) FROM lotse.abschnitt WHERE text <> ''").fetchone()
    zeilen = conn.execute(
        sql.SQL(
            "SELECT v.modell, v.dim, count(*),"
            " count(*) FILTER (WHERE EXISTS"
            " (SELECT 1 FROM lotse.abschnitt a WHERE a.text_hash = v.text_hash))"
            " FROM {} v GROUP BY v.modell, v.dim ORDER BY v.modell, v.dim"
        ).format(ziel)
    ).fetchall()
    return {
        "abschnitte": abschnitte[0] if abschnitte else 0,
        "eindeutige_hashes": hashes[0] if hashes else 0,
        "vektoren": [
            {"modell": m, "dim": d, "zeilen": n, "mit_abschnitt": treffer} for m, d, n, treffer in zeilen
        ],
    }


# --- CLI --------------------------------------------------------------------------------------------


def _dims(roh: str) -> list[int]:
    dims = [int(x) for x in roh.split(",") if x.strip()]
    for d in dims:
        if d not in ERLAUBTE_DIMS:
            raise argparse.ArgumentTypeError(f"Dimension {d} nicht erlaubt ({ERLAUBTE_DIMS})")
    return dims


def _log(text: str) -> None:
    print(f"{time.strftime('%Y-%m-%d %H:%M:%S')} {text}", flush=True)


def cli(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="lotse vektoren", description="Vollindex dichter Vektoren (#29)")
    parser.add_argument("--url", help="Verbindungs-URL (Standard: LOTSE_DATABASE_URL)")
    unter = parser.add_subparsers(dest="befehl", required=True)
    p_export = unter.add_parser("export", help="Abschnitte als JSONL exportieren")
    p_export.add_argument("--ausgabe", type=Path, required=True)
    p_rechnen = unter.add_parser("berechnen", help="Einbetten (nur Rechner B)")
    p_rechnen.add_argument("--eingabe", type=Path, required=True)
    p_rechnen.add_argument("--ausgabe", type=Path, required=True, help="Prefix der Ausgabedateien")
    p_rechnen.add_argument("--batch", type=int, default=8)
    p_rechnen.add_argument("--teilgroesse", type=int, default=TEILGROESSE)
    p_import = unter.add_parser("import", help="Vektoren nach lotse.vektor laden")
    p_import.add_argument("--prefix", type=Path, required=True)
    p_import.add_argument("--dims", type=_dims, default=[768, 256])
    unter.add_parser("status", help="Abdeckung je modell/dim")
    args = parser.parse_args(argv)

    if args.befehl == "export":
        with verbinde(args.url) as conn:
            paare = eindeutig_sortiert(lies_abschnitte(conn))
        anzahl = schreibe_jsonl(args.ausgabe, paare)
        _log(f"export {anzahl} eindeutige Hashes nach {args.ausgabe}")
        return 0
    if args.befehl == "berechnen":
        os.environ["EMBED_DIM"] = str(VOLLE_DIMENSION)  # gespeichert wird immer 768, 256 leitet import ab
        paare = lies_jsonl(args.eingabe)
        _log(f"berechnen {len(paare)} Texte, modell {MODELL_ID}, batch {args.batch}")
        werte = berechne(
            paare, args.ausgabe, _modell_einbetter(args.batch), teilgroesse=args.teilgroesse, log=_log
        )
        werte |= {
            "modell": MODELL_ID,
            "batch": args.batch,
            "embed_max_tokens": os.environ.get("EMBED_MAX_TOKENS", ""),
            "embed_dtype": os.environ.get("EMBED_DTYPE", ""),
            "embed_device": os.environ.get("EMBED_DEVICE", ""),
        }
        _speichere_text(Path(f"{args.ausgabe}.meta.json"), json.dumps(werte, indent=2, sort_keys=True) + "\n")
        _log(f"fertig {json.dumps(werte, sort_keys=True)}")
        return 0
    if args.befehl == "import":
        hashes, matrix = lies_vektoren(args.prefix)
        with verbinde(args.url) as conn:
            geschrieben = schreibe(conn, hashes, matrix, args.dims)
        _log(f"import {json.dumps(geschrieben)} modell {MODELL_ID}")
        return 0
    with verbinde(args.url) as conn:
        print(json.dumps(zaehle(conn), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(cli(sys.argv[1:]))
