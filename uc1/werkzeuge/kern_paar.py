"""Gepaarter Vergleich zweier Kern-Messberichte (`messen.py --nur-suche --kern --ausgabe …`), Issue #31.

Liest je Bericht die Tabelle „Rohdaten je Fall, Erweiterung E“ und vergleicht eine Rang-Spalte zwischen
A (vorher) und B (nachher): Recall@k mit Wilson-Intervall, gewonnen : verloren, McNemar exakt.
Gezählt werden bei SozDok-Spalten nur Fälle mit einer §-Quelle, bei PDF-Spalten nur Fälle mit
einer PDF-Quelle.

Aufruf aus uc1/: `uv run python werkzeuge/kern_paar.py A.md B.md --erweiterung aus --spalte "SozDok Kern"`
"""

from __future__ import annotations

import argparse
import sys
from math import comb, sqrt
from pathlib import Path


def rohdaten(pfad: Path, erweiterung: str) -> dict[str, dict[str, str]]:
    """Fall -> {Spaltenname: Wert} aus der Rohdaten-Tabelle der Erweiterung."""
    zeilen = pfad.read_text(encoding="utf-8").splitlines()
    kopf = f"Rohdaten je Fall, Erweiterung {erweiterung}"
    start = next(i for i, z in enumerate(zeilen) if z.lstrip("#").strip() == kopf)
    spalten: list[str] = []
    faelle: dict[str, dict[str, str]] = {}
    for z in zeilen[start + 1 :]:
        if z.startswith("#"):
            break
        if not z.startswith("|"):
            if faelle:
                break
            continue
        zellen = [c.strip() for c in z.strip("|").split("|")]
        if not spalten:
            spalten = zellen
        elif not set(zellen[0]) <= {"-"}:
            faelle[zellen[0]] = dict(zip(spalten, zellen, strict=False))
    return faelle


def treffer(wert: str, k: int) -> bool:
    return wert.isdigit() and int(wert) <= k


def wilson(x: int, n: int, z: float = 1.959964) -> tuple[float, float]:
    if n == 0:
        return 0.0, 0.0
    p = x / n
    mitte = (p + z * z / (2 * n)) / (1 + z * z / n)
    breite = z * sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return max(0.0, mitte - breite), min(1.0, mitte + breite)


def mcnemar(b: int, c: int) -> float:
    n = b + c
    if n == 0:
        return 1.0
    return min(1.0, 2 * sum(comb(n, i) for i in range(min(b, c) + 1)) / 2**n)


def main(argv: list[str]) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("a", type=Path)
    p.add_argument("b", type=Path)
    p.add_argument("--erweiterung", required=True)
    p.add_argument("--spalte", action="append", required=True)
    p.add_argument("-k", type=int, default=5)
    p.add_argument("--name-a", default="vorher")
    p.add_argument("--name-b", default="nachher")
    args = p.parse_args(argv)
    ra, rb = rohdaten(args.a, args.erweiterung), rohdaten(args.b, args.erweiterung)
    for spalte in args.spalte:
        pdf = "PDF" in spalte
        quelle = "erwartete Quellen"
        faelle = [f for f, z in ra.items() if (".pdf" in z[quelle].casefold() if pdf else "§" in z[quelle])]
        xa = [f for f in faelle if treffer(ra[f][spalte], args.k)]
        xb = [f for f in faelle if treffer(rb[f][spalte], args.k)]
        gew, ver = sorted(set(xb) - set(xa)), sorted(set(xa) - set(xb))
        n = len(faelle)
        for name, x in ((args.name_a, xa), (args.name_b, xb)):
            lo, hi = wilson(len(x), n)
            print(f"| {spalte} {args.erweiterung} {name} | {len(x)}/{n} | {lo:.0%}–{hi:.0%} |")
        print(
            f"| {spalte} {args.erweiterung} {args.name_b} gegen {args.name_a} | {len(gew)} : {len(ver)} | "
            f"{n - len(gew) - len(ver)} | {mcnemar(len(gew), len(ver)):.3f} | "
            f"gewonnen {', '.join(gew) or '–'}; verloren {', '.join(ver) or '–'} |"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
