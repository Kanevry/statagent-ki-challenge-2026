"""Proben der Live-Änderung (Jury-Teil 2): unbekannte Änderungsaufträge in Sprache an die eigenen Agenten.

Je Lauf und Auftrag:

1. Anweisung an den Koordinator, Vorschlag mit Probe vorher/nachher (Dauer gemessen, Ziel unter 4 Minuten).
2. Prüfung, ob die Regeländerung die richtige ist (Erwartung je Auftrag, unten).
3. Ablehnen mit Namen: Regelstand des aktuellen Stands (Produktionshash) und Git-Kopf bleiben gleich, kein
   neuer Regelsatz entsteht.
4. Dieselbe Anweisung noch einmal, diesmal Freigabe mit Namen: Regel aktiv, ein Commit mit Trailer.
5. Rücknahme in Sprache als neuer Vorgang („Nimm Vorschlag N zurück“), Freigabe: Regelstand und Zahlen der Probe
   entsprechen wieder dem Stand vor Schritt 4. Nichts wird gelöscht.

Läuft nur gegen eine eigene Kopie der Abgabe-DB (``UC3_DATABASE_URL``, Name nie ``statistik``) und committet
die Freigaben in ein eigenes Probe-Repo (``--repo``), nie in dieses. Schreibt je Lauf eine Zeile nach
``docs/plan/uc3/live-proben.csv``.

    UC3_DATABASE_URL=postgresql://…/statistik_live80 LLM_PROVIDER=azure \\
      uv run python uc3/proben/live_proben.py --repo ~/Projects/_scratch/uc3-live-proben-git --runden 3
"""

from __future__ import annotations

import argparse
import csv
import os
import subprocess
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo

from statagent import konfig
from statagent.agenten.anwenden import ablehnen_ausfuehren, freigabe_ausfuehren
from statagent.agenten.koordinator import agent_ausfuehren, produktions_regelsatz, ruecknahme_pruefen
from statagent.agenten.regelaenderung import regelsatz_vorhanden
from statagent.agenten.vorschlag import (
    Vorschlag,
    vorschlag_anlegen,
    vorschlag_lesen,
    vorschlag_schema_einrichten,
    wirkung_text,
)
from statagent.db import Verbindung, verbinden
from statagent.regeln import regeln_laden, regelstand

NAME = "Petra Probe"  # erkennbar eine Probe, keine echte Freigabe
WIEN = ZoneInfo("Europe/Vienna")
SPALTEN = (
    "auftrag",
    "lauf",
    "anweisung",
    "zeit",
    "dauer_s",
    "regelsatz",
    "probe_monat",
    "vorschlag_abgelehnt",
    "vorschlag_freigegeben",
    "vorschlag_ruecknahme",
    "protokoll_ids",
    "name",
    "diff",
    "zahlen",
    "regel_richtig",
    "ablehnen_hash_gleich",
    "freigabe_angewendet",
    "ruecknahme_hash_gleich",
    "ruecknahme_zahlen_gleich",
    "dauer_unter_4min",
    "bestanden",
    "hinweis",
)


def _regel_neu(v: Vorschlag, art: str) -> dict[str, Any] | None:
    if v.typ != "regel_neu":
        return None
    treffer = [a["regel"] for a in v.aenderungen if a["regel"]["art"] == art]
    return treffer[0] if len(treffer) == 1 and len(v.aenderungen) == 1 else None


def _geaendert(v: Vorschlag, regel_praefix: str) -> dict[str, tuple[Any, Any]]:
    """Geänderte Parameter einer Regel (Name beginnt mit regel_praefix); leer, wenn andere Regeln mit dabei sind."""
    if v.typ != "regel_aendern" or len(v.aenderungen) != 1:
        return {}
    a = v.aenderungen[0]
    if not str(a["regel_name"]).startswith(regel_praefix):
        return {}
    alt, neu = a["parameter_alt"], a["parameter_neu"]
    return {k: (alt.get(k), neu.get(k)) for k in set(alt) | set(neu) if alt.get(k) != neu.get(k)}


def _gruppen(regel: dict[str, Any] | None, merkmal: str) -> dict[str, str]:
    if regel is None or regel["parameter"].get("merkmal") != merkmal:
        return {}
    return dict(str(e).split("=", 1) for e in regel["parameter"].get("zuordnung", []))


def _eine_gruppe(regel: dict[str, Any] | None, merkmal: str, codes: set[str]) -> bool:
    g = _gruppen(regel, merkmal)
    return set(g) == codes and len(set(g.values())) == 1


@dataclass(frozen=True)
class Auftrag:
    kurz: str
    anweisung: str
    erwartung: Callable[[Vorschlag], bool]
    #: lockere Schreibweise (klein, ohne Satzzeichen, Tippfehler, Zahlwörter); gilt im letzten Lauf
    locker: str | None = None


def _ausschluss(v: Vorschlag, merkmale: set[str], werte: set[str]) -> bool:
    r = _regel_neu(v, "ausschluss")
    return r is not None and r["parameter"]["merkmal"] in merkmale and set(r["parameter"]["werte"]) == werte


#: Zehn Aufträge, bewusst anders formuliert als die Abnahme-Muster (A, B, C aus #80 darunter).
AUFTRAEGE: tuple[Auftrag, ...] = (
    Auftrag(
        "A_stichtag_15",
        "Ab sofort zählen wir nicht mehr das ganze Monat, sondern nur, wer am 15. des Monats beschäftigt ist.",
        lambda v: (
            _geaendert(v, "R2_R4")
            == {
                "zeitraum_art": ("Monat", "Stichtag"),
                "von": ("monatserster", "tag:15"),
                "bis": ("monatsletzter", "tag:15"),
            }
        ),
    ),
    Auftrag(
        "B_ohne_beamte",
        "Beamtinnen und Beamte sollen in der Beschäftigtenstatistik künftig nicht mehr vorkommen.",
        lambda v: _ausschluss(v, {"qualifikation", "beschaeftigungskategorie"}, {"Beamte"}),
    ),
    Auftrag(
        "C_ostregion",
        "Wien, Niederösterreich und das Burgenland bitte gemeinsam als eine Region Ost ausweisen.",
        lambda v: _eine_gruppe(_regel_neu(v, "gruppierung"), "region", {"1", "3", "9"}),
    ),
    Auftrag(
        "D_monat13_jaenner",
        "Wenn im Geburtsdatum der Monat 13 steht, nehmt als Ersatz den ersten Jänner.",
        lambda v: _geaendert(v, "R5_alter") == {"geburtsmonat_13": ("ersatz:07-01", "ersatz:01-01")},
    ),
    Auftrag(
        "E_alter_monatserster",
        "Das Alter soll künftig am Ersten des Berichtsmonats gerechnet werden, nicht am Letzten.",
        lambda v: _geaendert(v, "R5_alter") == {"bezug": ("bis", "von")},
    ),
    Auftrag(
        "F_alter_max_100",
        "Wer laut Geburtsdatum älter als 100 Jahre wäre, gilt ab jetzt als unplausibles Alter.",
        lambda v: _geaendert(v, "R5_alter") == {"max_plausibel": (110, 100)},
    ),
    Auftrag(
        "G_ohne_unter_15",
        "Beschäftigungsverhältnisse von Kindern unter 15 Jahren zählen wir nicht mehr mit.",
        lambda v: _ausschluss(v, {"alter"}, {"0-14"}),
    ),
    Auftrag(
        "H_ohne_vorarlberg",
        "Vorarlberg fällt aus der Statistik heraus, alle anderen Bundesländer bleiben.",
        lambda v: _ausschluss(v, {"region"}, {"8"}),
    ),
    Auftrag(
        "I_unselbstaendige",
        "Arbeiter und Angestellte sollen zusammen als eine Gruppe Unselbständige erscheinen, Beamte bleiben extra.",
        lambda v: _eine_gruppe(_regel_neu(v, "gruppierung"), "qualifikation", {"Arbeiter", "Angestellte"}),
    ),
    Auftrag(
        "J_anhalten_3_prozent",
        "Haltet einen Monat schon an, wenn der Bestand mehr als 3 Prozent unter dem Vormonat liegt.",
        lambda v: _geaendert(v, "P15") == {"schwelle": (0.05, 0.03)},
    ),
)
#: Fünf Fassungen in lockerer Schreibweise, wie sie live getippt werden (Owner 05.11. 19:3x: getippter Text reicht,
#: robust gegen Kleinschreibung, fehlende Satzzeichen und Tippfehler).
LOCKER = {
    "A_stichtag_15": "ab jetzt zählt nur mehr wer am fünfzehnten des monats beschäftigt ist",
    "B_ohne_beamte": "beamtinen und beamte bitte nciht mehr mitzählen",
    "C_ostregion": "wien niederösterreich und burgenland zusamen als ostregion ausweisen",
    "D_monat13_jaenner": "bei geburtsmonat 13 nehmt bitte den ersten jänner als ersatztag",
    "G_ohne_unter_15": "kinder unter 15 jahren zählen wir ab jetzt nicht mehr",
}
AUFTRAEGE = tuple(replace(a, locker=LOCKER.get(a.kurz)) for a in AUFTRAEGE)


def _jetzt() -> str:
    return datetime.now(WIEN).strftime("%Y-%m-%d %H:%M:%S")


def _git_kopf(repo: Path) -> str:
    return subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "HEAD"], capture_output=True, text=True, check=True
    ).stdout.strip()


def _stand(conn: Verbindung, regelsatz: str, monat: str) -> str:
    return regelstand(conn, regeln_laden(conn, regelsatz, monat))


def _zahlen(v: Vorschlag, monat: str) -> str:
    p = v.probe.get(monat, {})
    if "vorher" not in p:
        return str(p.get("hinweis", ""))
    teile = [f"gesamt {p['vorher']['gesamt']} → {p['nachher']['gesamt']}"]
    for merkmal, vm in p["vorher"]["je_merkmal"].items():
        nm = p["nachher"]["je_merkmal"].get(merkmal, {})
        for code in sorted(set(vm) | set(nm)):
            if vm.get(code, 0) != nm.get(code, 0):
                teile.append(f"{merkmal} {code}: {vm.get(code, 0)} → {nm.get(code, 0)}")
    return "; ".join(teile[:6])


def _vorschlag(conn: Verbindung, anweisung: str, monat: str) -> tuple[Vorschlag | None, float, str]:
    start = time.monotonic()
    erg = agent_ausfuehren(conn, anweisung, regelsatz_basis=None, probe_lieferung=monat)
    dauer = time.monotonic() - start
    if erg.vorschlag_id is None:
        return None, dauer, erg.rueckfrage or erg.abgelehnt or "kein Vorschlag"
    korrektur = f" (Korrekturen: {len(erg.korrekturen)})" if erg.korrekturen else ""
    return vorschlag_lesen(conn, erg.vorschlag_id), dauer, korrektur.strip()


#: Freigegebener Probe-Vorschlag, dessen Rücknahme noch aussteht (für das Aufräumen nach einem Fehler)
_OFFEN: dict[str, int] = {}


def _aufraeumen(conn: Verbindung, vorschlag_id: int, repo: Path) -> None:
    """Stellt den Stand vor einem freigegebenen Vorschlag ohne Modell wieder her (Umkehrung aus dem Code), damit
    ein gescheiterter Lauf die folgenden nicht verfälscht. Zählt nie als bestanden."""
    basis = produktions_regelsatz(conn)
    g = ruecknahme_pruefen(conn, vorschlag_id, basis)
    vid = vorschlag_anlegen(
        conn,
        anweisung=f"Aufräumen der Probe: Vorschlag {vorschlag_id} zurücknehmen",
        rolle="datenmanagement",
        typ=g.typ,
        regelsatz_ziel=g.regelsatz_ziel,
        regelsatz_basis=g.regelsatz_basis,
        begruendung=g.begruendung,
        aenderungen=g.aenderungen,
    )
    freigabe_ausfuehren(conn, vid, NAME, repo)


def ein_lauf(
    conn: Verbindung,
    auftrag: Auftrag,
    nummer: int,
    monat: str,
    repo: Path,
    locker: bool = False,
    referenz: str | None = None,
) -> dict[str, Any]:
    anweisung = auftrag.locker if locker and auftrag.locker else auftrag.anweisung
    zeile: dict[str, Any] = {
        "auftrag": auftrag.kurz + ("_locker" if anweisung == auftrag.locker else ""),
        "lauf": nummer,
        "anweisung": anweisung,
        "name": NAME,
    }
    zeile["zeit"] = _jetzt()
    hinweise: list[str] = []
    basis = produktions_regelsatz(conn)
    stand_vorher = _stand(conn, basis, monat)
    if referenz is not None and stand_vorher != referenz:
        zeile |= {
            "bestanden": False,
            "hinweis": f"Ausgangsstand {basis} weicht vom Stand der Abgabe ab; Lauf nicht gewertet",
        }
        return zeile

    # 1–3: Vorschlag, Erwartung, Ablehnen
    v1, dauer1, h = _vorschlag(conn, anweisung, monat)
    hinweise.append(h)
    zeile["dauer_s"] = round(dauer1, 1)
    if v1 is None:
        zeile |= {"regel_richtig": False, "bestanden": False, "hinweis": "; ".join(x for x in hinweise if x)}
        return zeile
    zeile["regelsatz"] = f"{v1.regelsatz_basis} → {v1.regelsatz_ziel}"
    zeile["probe_monat"] = monat
    zeile["diff"] = wirkung_text(v1.typ, v1.aenderungen, v1.regelsatz_ziel)
    zeile["zahlen"] = _zahlen(v1, monat)
    richtig = auftrag.erwartung(v1)
    kopf = _git_kopf(repo)
    ablehnen_ausfuehren(conn, v1.id, NAME, repo, begruendung="Probe der Live-Änderung: Ablehnen")
    zeile["vorschlag_abgelehnt"] = v1.id
    zeile["ablehnen_hash_gleich"] = (
        _stand(conn, basis, monat) == stand_vorher
        and _git_kopf(repo) == kopf
        and produktions_regelsatz(conn) == basis
        and not regelsatz_vorhanden(conn, v1.regelsatz_ziel)
    )

    # 4: noch einmal, Freigabe
    v2, dauer2, h = _vorschlag(conn, anweisung, monat)
    hinweise.append(h)
    zeile["dauer_s"] = round(max(dauer1, dauer2), 1)
    if v2 is None:
        zeile |= {"regel_richtig": False, "bestanden": False, "hinweis": "; ".join(x for x in hinweise if x)}
        return zeile
    richtig = richtig and auftrag.erwartung(v2)
    zeile["regel_richtig"] = richtig
    f2 = freigabe_ausfuehren(conn, v2.id, NAME, repo)
    zeile["vorschlag_freigegeben"] = v2.id
    if f2.angewendet:
        _OFFEN["id"] = v2.id
    zeile["freigabe_angewendet"] = f2.angewendet and _git_kopf(repo) != kopf
    if not f2.angewendet:
        hinweise.append(f"Freigabe nicht angewendet: {f2.meldung}")

    # 5: Rücknahme als neuer Vorgang
    v3, dauer3, h = _vorschlag(
        conn, f"Nimm die Änderung aus Vorschlag {v2.id} zurück, wie es vorher war.", monat
    )
    hinweise.append(h)
    zeile["dauer_s"] = round(max(dauer1, dauer2, dauer3), 1)
    if v3 is None:
        _aufraeumen(conn, v2.id, repo)
        _OFFEN.pop("id", None)
        hinweise.append("Rücknahme per Sprache gescheitert, ohne Modell aufgeräumt")
        zeile |= {
            "ruecknahme_hash_gleich": False,
            "bestanden": False,
            "hinweis": "; ".join(x for x in hinweise if x),
        }
        return zeile
    f3 = freigabe_ausfuehren(conn, v3.id, NAME, repo)
    zeile["vorschlag_ruecknahme"] = v3.id
    if not f3.angewendet:
        _aufraeumen(conn, v2.id, repo)
    _OFFEN.pop("id", None)
    nach = produktions_regelsatz(conn)
    zeile["ruecknahme_hash_gleich"] = f3.angewendet and _stand(conn, nach, monat) == stand_vorher
    p1, p3 = v2.probe.get(monat, {}), v3.probe.get(monat, {})
    zeile["ruecknahme_zahlen_gleich"] = (
        "vorher" in p1
        and "nachher" in p3
        and p3["nachher"]["gesamt"] == p1["vorher"]["gesamt"]
        and p3["nachher"]["je_merkmal"] == p1["vorher"]["je_merkmal"]
    )
    zeile["regelsatz"] += f"; Rücknahme {v3.regelsatz_basis} → {v3.regelsatz_ziel}"
    zeile["protokoll_ids"] = " ".join(str(x.protokoll_id) for x in (v1, v2, v3))
    zeile["dauer_unter_4min"] = max(dauer1, dauer2, dauer3) < 240
    zeile["bestanden"] = all(
        zeile.get(k) is True
        for k in (
            "regel_richtig",
            "ablehnen_hash_gleich",
            "freigabe_angewendet",
            "ruecknahme_hash_gleich",
            "ruecknahme_zahlen_gleich",
            "dauer_unter_4min",
        )
    )
    zeile["hinweis"] = "; ".join(x for x in hinweise if x)
    return zeile


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--repo", type=Path, required=True, help="eigenes Git-Repo für die Freigabe-Commits")
    parser.add_argument("--runden", type=int, default=3)
    parser.add_argument("--monat", default="2026-07")
    parser.add_argument("--auftraege", nargs="*", help="Kurznamen, Standard: alle zehn")
    parser.add_argument("--csv", type=Path, default=Path("docs/plan/uc3/live-proben.csv"))
    args = parser.parse_args()

    konfig.umgebung_laden()  # .env.local wie die CLI (Modell-Schlüssel); gesetzte Variablen bleiben
    url = os.environ.get("UC3_DATABASE_URL", "")
    if urlsplit(url).path.strip("/") in ("", "statistik"):
        print(
            "Abbruch: Proben nur gegen eine eigene Kopie (UC3_DATABASE_URL mit anderem DB-Namen)",
            file=sys.stderr,
        )
        return 2
    repo = args.repo.expanduser().resolve()
    if (repo / "uc3" / "statagent").exists():
        print("Abbruch: --repo ist ein Checkout dieses Repos; Proben committen nur in ein eigenes Probe-Repo")
        return 2
    auswahl = [a for a in AUFTRAEGE if not args.auftraege or a.kurz in args.auftraege]
    neu = not args.csv.exists()
    with verbinden(url) as conn, args.csv.open("a", encoding="utf-8", newline="") as f:
        vorschlag_schema_einrichten(conn)
        # Stand der Abgabe (Zählregeln von v2) als Ausgangsstand jedes Laufs
        referenz = _stand(conn, produktions_regelsatz(conn), args.monat)
        schreiber = csv.DictWriter(f, fieldnames=SPALTEN, delimiter=";")
        if neu:
            schreiber.writeheader()
        for nummer in range(1, args.runden + 1):
            for auftrag in auswahl:
                try:
                    zeile = ein_lauf(
                        conn,
                        auftrag,
                        nummer,
                        args.monat,
                        repo,
                        locker=nummer == args.runden,
                        referenz=referenz,
                    )
                except Exception as fehler:  # nicht bestanden, kein Abbruch der Serie
                    if "id" in _OFFEN:
                        _aufraeumen(conn, _OFFEN.pop("id"), repo)
                    zeile = {
                        "auftrag": auftrag.kurz,
                        "lauf": nummer,
                        "anweisung": auftrag.anweisung,
                        "zeit": _jetzt(),
                        "bestanden": False,
                        "hinweis": f"{type(fehler).__name__}: {fehler}",
                    }
                schreiber.writerow(zeile)
                f.flush()
                print(
                    f"{zeile['zeit']} {auftrag.kurz} Lauf {nummer}: "
                    f"{'bestanden' if zeile.get('bestanden') else 'NICHT bestanden'} "
                    f"({zeile.get('dauer_s', '-')} s) {zeile.get('hinweis', '')}",
                    flush=True,
                )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
