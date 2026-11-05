"""CLI: ``uv run python -m plattform.llm status [--json]`` und ``smoke [--provider ...]``.

``smoke`` schickt je Provider eine kurze Anfrage ohne Fallback, misst die Dauer, druckt eine Tabelle und
hängt das Ergebnis mit Zeitstempel an ``docs/models.md`` an. Fehlt ein Schlüssel: „nicht belegt“.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import time
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from plattform.umgebung import lade_env_local

from .kern import aktives_modell, ausfuehren

STANDARD_PROVIDER = ("azure", "mistral", "claude")
SMOKE_NACHRICHTEN = [{"role": "user", "content": "Antworte nur mit dem Wort: bereit"}]


def _belegt(provider: str) -> str | None:
    """``None`` wenn bereit, sonst Grund für „nicht belegt“ (nur Variablennamen, nie Werte)."""
    if provider == "azure":
        fehlend = [v for v in ("AZURE_API_KEY", "AZURE_OPENAI_BASE_URL") if not os.environ.get(v)]
        return ", ".join(fehlend) + " fehlt" if fehlend else None
    if provider == "mistral":
        return None if os.environ.get("MISTRAL_API_KEY") else "MISTRAL_API_KEY fehlt"
    if provider == "claude":
        if shutil.which("claude") is None:
            return "claude-CLI fehlt"
        return "ANTHROPIC_API_KEY gesetzt (Abo-Pflicht)" if os.environ.get("ANTHROPIC_API_KEY") else None
    return None


#: Zeitgrenzen laut Akzeptanz #54: azure und mistral unter 30 s, claude unter 60 s.
ZEITGRENZE_MS = {"azure": 30_000, "mistral": 30_000, "claude": 60_000}


def _repo_wurzel() -> Path:
    wurzel = Path.cwd().resolve()
    for ordner in (wurzel, *wurzel.parents):
        if (ordner / ".git").exists():
            return ordner
    return wurzel


def _smoke(provider: list[str], datei: Path) -> int:
    zeilen: list[dict[str, str]] = []
    for name in provider:
        grund = _belegt(name)
        if grund:
            zeilen.append({"provider": name, "modell": "-", "version": "-", "dauer": "-", "ergebnis": grund})
            continue
        start = time.perf_counter()
        try:
            antwort = ausfuehren(SMOKE_NACHRICHTEN, kette=[name], zweck="smoke")
        except Exception as fehler:  # Smoke darf nie abstürzen, jeder Fehler kommt in die Tabelle
            dauer = f"{(time.perf_counter() - start):.1f} s"
            meldung = f"{type(fehler).__name__}: {fehler}".replace("|", "/")[:120]
            zeilen.append(
                {"provider": name, "modell": "-", "version": "-", "dauer": dauer, "ergebnis": meldung}
            )
            continue
        grenze_ms = ZEITGRENZE_MS.get(name, 30_000)
        if not antwort.text.strip():
            ergebnis = "fehler: leere Antwort"
        elif antwort.dauer_ms > grenze_ms:
            ergebnis = f"zu langsam: {antwort.dauer_ms / 1000:.1f} s über {grenze_ms // 1000} s"
        else:
            ergebnis = f"ok ({antwort.text.strip()[:20]!r})"
        zeilen.append(
            {
                "provider": name,
                "modell": antwort.modell,
                "version": antwort.version or "-",
                "dauer": f"{antwort.dauer_ms / 1000:.1f} s",
                "ergebnis": ergebnis,
            }
        )
    zeit = datetime.now(ZoneInfo("Europe/Vienna")).isoformat(timespec="seconds")
    kopf = "| Zeit | Provider | Modell | Version | Dauer | Ergebnis |\n|---|---|---|---|---|---|\n"
    tabelle = "".join(
        f"| {zeit} | {z['provider']} | {z['modell']} | {z['version']} | {z['dauer']} | {z['ergebnis']} |\n"
        for z in zeilen
    )
    print(kopf + tabelle, end="")
    datei.parent.mkdir(parents=True, exist_ok=True)
    with datei.open("a", encoding="utf-8") as ziel:
        ziel.write(f"\n### Smoke {zeit}\n\n" + kopf + tabelle)
    return 0 if all(z["ergebnis"].startswith("ok") for z in zeilen) else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m plattform.llm", description="Modell-Schalter")
    befehle = parser.add_subparsers(dest="befehl", required=True)
    status = befehle.add_parser("status", help="aktives Modell anzeigen")
    status.add_argument("--json", action="store_true")
    status.add_argument("--zweck", default="")
    smoke = befehle.add_parser("smoke", help="je Provider eine kurze Anfrage, Ergebnis nach docs/models.md")
    smoke.add_argument("--provider", nargs="+", default=list(STANDARD_PROVIDER))
    smoke.add_argument("--datei", type=Path, default=None)
    args = parser.parse_args(argv)

    lade_env_local()
    if args.befehl == "status":
        info = aktives_modell(args.zweck)
        if args.json:
            print(json.dumps(info, ensure_ascii=False))
            return 0
        zeile = f"{info['provider']} · {info['modell']}"
        zuletzt = info.get("zuletzt") or {}
        if zuletzt and (
            zuletzt.get("provider") != info["provider"] or (zuletzt.get("fallback_stufe") or 1) > 1
        ):
            zeile += f" (zuletzt {zuletzt.get('provider')}, Stufe {zuletzt.get('fallback_stufe')})"
        print(zeile)
        return 0
    return _smoke(args.provider, args.datei or _repo_wurzel() / "docs" / "models.md")


if __name__ == "__main__":
    sys.exit(main())
