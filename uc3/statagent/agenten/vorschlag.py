"""Vorschläge der Agenten: anlegen, lesen, als Änderung lesbar machen und mit echten Zahlen proben.

Ein Vorschlag ist noch nichts Wirksames. Er steht in ``meta.vorschlag`` (und als offene Zeile in
``meta.protokoll``, sobald es die Tabelle gibt), bis ein Mensch ihn mit Vor- und Nachnamen freigibt.
Die Probe rechnet den Monat einmal nach dem alten und einmal nach dem neuen Regelstand und rollt danach
alles zurück; gespeichert werden nur die Zahlen (Aggregate).
"""

from __future__ import annotations

import contextlib
import json
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from statagent import konfig
from statagent.agenten.plattform_bruecke import VERTRAG_TYP, sha256_datei
from statagent.agenten.regelaenderung import einspielen
from statagent.db import Verbindung
from statagent.ergebnis import monatswerte
from statagent.lauf import lauf_ausfuehren
from statagent.regeln import eine, regeln_laden

#: Ablage freigegebener Code-Dateien, relativ zur Repo-Wurzel.
ERZEUGT_RELATIV = "uc3/erzeugt"
DDL = konfig.DB_VERZEICHNIS / "140_vorschlag.sql"
#: Merkmale, deren Summen die Probe zeigt (Zellen mit vielen Ausprägungen wie Alter bleiben außen vor).
PROBE_MERKMALE = ("qualifikation", "geschlecht", "region")
#: Altersgruppen der Probe: macht Änderungen an R5_alter sichtbar (Geburtsmonat 13, Plausibilitätsgrenzen).
ALTERSGRUPPEN = ((0, 14), (15, 24), (25, 34), (35, 44), (45, 54), (55, 64), (65, 74), (75, 999))


def altersgruppe(alter: int) -> str:
    """Altersgruppe einer Zelle; -1 (unbekannt oder unplausibel) heißt „unbekannt“."""
    for von, bis in ALTERSGRUPPEN:
        if von <= alter <= bis:
            return f"{von}+" if bis == 999 else f"{von}-{bis}"
    return "unbekannt"


class VorschlagFehler(RuntimeError):
    """Der Vorschlag fehlt oder passt nicht zum verlangten Schritt."""


@dataclass(frozen=True)
class CodeDateiEntwurf:
    """Eine vom Agenten geschriebene Code-Datei, bevor sie eine ID und einen Kopf hat."""

    name: str  # nur [a-z0-9_]
    endung: str  # ".py" oder ".sql"
    rumpf: str


@dataclass(frozen=True)
class Vorschlag:
    id: int
    protokoll_id: int | None
    erstellt_am: datetime
    anweisung: str
    rolle: str
    typ: str
    regelsatz_ziel: str
    regelsatz_basis: str
    aenderungen: list[dict[str, Any]]
    datei_inhalt: str | None
    begruendung: str
    probe: dict[str, Any]
    modell: str | None
    provider: str | None
    status: str
    freigegeben_von: str | None
    freigegeben_am: datetime | None
    commit_hash: str | None
    angewendet_am: datetime | None
    anwenden_fehler: str | None
    abgelehnt_von: str | None
    ablehnungsgrund: str | None

    @property
    def zustand(self) -> str:
        """Status in Alltagssprache, z. B. „freigegeben, nicht angewendet (RegelKonflikt)“."""
        if self.status != "freigegeben":
            return self.status
        if self.angewendet_am is not None:
            return "freigegeben, angewendet"
        fehler = f" ({self.anwenden_fehler})" if self.anwenden_fehler else ""
        return f"freigegeben, nicht angewendet{fehler}"

    @property
    def datei_pfad(self) -> str | None:
        return str(self.aenderungen[0]["pfad"]) if self.typ == "code_datei" else None

    @property
    def ref(self) -> str:
        """Was freigegeben wird: genau eine Datei im Repo oder die Regeln als ``<regelsatz>/<name>``."""
        if self.typ == "code_datei":
            return str(self.aenderungen[0]["pfad"])
        namen = [str(a.get("regel_name") or a["regel"]["name"]) for a in self.aenderungen]
        return ",".join(f"{self.regelsatz_ziel}/{n}" for n in namen)


def vorschlag_schema_einrichten(conn: Verbindung) -> None:
    """Legt meta.vorschlag an (idempotent), bis die DDL unter uc3/db/ liegt."""
    with conn.transaction():
        conn.execute(DDL.read_text(encoding="utf-8").encode())


def protokoll_vorhanden(conn: Verbindung) -> bool:
    z = conn.execute("SELECT to_regclass('meta.protokoll') IS NOT NULL AS da").fetchone()
    return bool(z and z["da"])


def _einzeilig(text: str) -> str:
    return " ".join(text.split())


def datei_kopf(anweisung: str, vorschlag_id: int, rolle: str, endung: str) -> str:
    """Kopfkommentar jeder erzeugten Datei (Teil des freigegebenen Inhalts)."""
    zeichen = "#" if endung == ".py" else "--"
    zeilen = [
        f"Erzeugt von StatAgent (Rolle {rolle}), Vorschlag uc3/{vorschlag_id}.",
        f"Anweisung: {_einzeilig(anweisung)}",
        "Freigabe: läuft nur, wenn genau dieser Inhalt mit Vor- und Nachnamen freigegeben ist",
        "(Commit-Trailer „Freigegeben-von“, uc3 protokoll). Jede Änderung braucht eine neue Freigabe.",
    ]
    return "".join(f"{zeichen} {z}\n" for z in zeilen) + "\n"


def wirkung_text(typ: str, aenderungen: list[dict[str, Any]], ziel: str) -> str:
    """Eine Zeile „was würde sich ändern“ für das Protokoll."""
    if typ == "regel_aendern":
        teile = []
        for a in aenderungen:
            if a.get("aktiv_neu") is False:
                teile.append(f"{a['regel_name']} wird abgeschaltet")
                continue
            for k in sorted(set(a["parameter_alt"]) | set(a["parameter_neu"])):
                alt, neu = a["parameter_alt"].get(k), a["parameter_neu"].get(k)
                if alt != neu:
                    teile.append(f"{a['regel_name']}.{k}: {json.dumps(alt)} → {json.dumps(neu)}")
        return f"Regelsatz {ziel}: " + "; ".join(teile)
    if typ == "regel_neu":
        return f"Regelsatz {ziel}: neue Regel " + ", ".join(str(a["regel"]["name"]) for a in aenderungen)
    return "neue Code-Datei " + ", ".join(str(a["pfad"]) for a in aenderungen)


def vorschlag_anlegen(
    conn: Verbindung,
    *,
    anweisung: str,
    rolle: str,
    typ: str,
    regelsatz_ziel: str,
    regelsatz_basis: str,
    begruendung: str,
    aenderungen: list[dict[str, Any]] | None = None,
    datei: CodeDateiEntwurf | None = None,
    modell: str | None = None,
    provider: str | None = None,
) -> int:
    """Legt einen offenen Vorschlag an und liefert seine ID.

    Gibt es ``meta.protokoll`` (Vertrag P), entsteht dort zugleich eine Zeile mit Status offen, und der
    Vorschlag bekommt dieselbe ID (so passt der Commit-Trailer ``Vorschlag: uc3/<id>`` zu beiden).
    Bei Code-Dateien setzt diese Funktion Pfad, Kopfkommentar und sha256 selbst.
    """
    if (typ == "code_datei") != (datei is not None):
        raise VorschlagFehler("Code-Datei-Vorschläge brauchen genau eine Datei, Regelvorschläge keine")
    with conn.transaction():
        mit_protokoll = protokoll_vorhanden(conn)
        if mit_protokoll:
            z = conn.execute(
                """INSERT INTO meta.protokoll (uc, akteur, name, anweisung, vorschlag_typ, status, modell, provider)
                   VALUES ('uc3', 'agent', %s, %s, %s, 'offen', %s, %s) RETURNING id""",
                (f"agent.{rolle}", anweisung, VERTRAG_TYP[typ], modell, provider),
            ).fetchone()
        else:
            z = conn.execute(
                "SELECT nextval(pg_get_serial_sequence('meta.vorschlag', 'id')) AS id"
            ).fetchone()
        assert z is not None
        vid = int(str(z["id"]))

        inhalt: str | None = None
        if datei is not None:
            inhalt = datei_kopf(anweisung, vid, rolle, datei.endung) + datei.rumpf.rstrip("\n") + "\n"
            pfad = f"{ERZEUGT_RELATIV}/{vid}_{datei.name}{datei.endung}"
            aenderungen = [{"pfad": pfad, "inhalt_sha256": sha256_datei(inhalt.encode("utf-8"))}]
        if not aenderungen:
            raise VorschlagFehler("Ein Vorschlag braucht mindestens eine Änderung")

        conn.execute(
            """INSERT INTO meta.vorschlag (id, protokoll_id, anweisung, rolle, typ, regelsatz_ziel, regelsatz_basis,
                                           aenderungen, datei_inhalt, begruendung, modell, provider)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s, %s, %s, %s)""",
            (
                vid,
                vid if mit_protokoll else None,
                anweisung,
                rolle,
                typ,
                regelsatz_ziel,
                regelsatz_basis,
                json.dumps(aenderungen, ensure_ascii=False),
                inhalt,
                begruendung,
                modell,
                provider,
            ),
        )
        if mit_protokoll:
            v = vorschlag_lesen(conn, vid)
            conn.execute(
                "UPDATE meta.protokoll SET wirkung = %s, ref = %s WHERE id = %s",
                (wirkung_text(typ, aenderungen, regelsatz_ziel), v.ref, vid),
            )
            conn.execute(
                """SELECT setval(pg_get_serial_sequence('meta.vorschlag', 'id'),
                                 greatest((SELECT max(id) FROM meta.vorschlag), 1))"""
            )
    return vid


def vorschlag_lesen(conn: Verbindung, vorschlag_id: int) -> Vorschlag:
    z = conn.execute(
        """SELECT id, protokoll_id, erstellt_am, anweisung, rolle, typ, regelsatz_ziel, regelsatz_basis,
                  aenderungen, datei_inhalt, begruendung, probe, modell, provider, status, freigegeben_von,
                  freigegeben_am, commit_hash, angewendet_am, anwenden_fehler, abgelehnt_von, ablehnungsgrund
           FROM meta.vorschlag WHERE id = %s""",
        (vorschlag_id,),
    ).fetchone()
    if z is None:
        raise VorschlagFehler(f"Vorschlag uc3/{vorschlag_id} gibt es nicht")

    def text(k: str) -> str | None:
        return None if z[k] is None else str(z[k])

    def zeit(k: str) -> datetime | None:
        wert = z[k]
        return wert if isinstance(wert, datetime) else None

    erstellt = zeit("erstellt_am")
    assert erstellt is not None
    aenderungen = z["aenderungen"]
    probe = z["probe"]
    return Vorschlag(
        id=int(str(z["id"])),
        protokoll_id=None if z["protokoll_id"] is None else int(str(z["protokoll_id"])),
        erstellt_am=erstellt,
        anweisung=str(z["anweisung"]),
        rolle=str(z["rolle"]),
        typ=str(z["typ"]),
        regelsatz_ziel=str(z["regelsatz_ziel"]),
        regelsatz_basis=str(z["regelsatz_basis"]),
        aenderungen=list(aenderungen) if isinstance(aenderungen, list) else [],
        datei_inhalt=text("datei_inhalt"),
        begruendung=str(z["begruendung"]),
        probe=dict(probe) if isinstance(probe, dict) else {},
        modell=text("modell"),
        provider=text("provider"),
        status=str(z["status"]),
        freigegeben_von=text("freigegeben_von"),
        freigegeben_am=zeit("freigegeben_am"),
        commit_hash=text("commit_hash"),
        angewendet_am=zeit("angewendet_am"),
        anwenden_fehler=text("anwenden_fehler"),
        abgelehnt_von=text("abgelehnt_von"),
        ablehnungsgrund=text("ablehnungsgrund"),
    )


def _wert(w: object) -> str:
    return json.dumps(w, ensure_ascii=False)


def diff_text(vorschlag: Vorschlag) -> str:
    """Die Änderung in zwei Sprachen: Alltagssprache und technisch. Nur geänderte Zeilen."""
    v = vorschlag
    zeilen = [
        f"Vorschlag uc3/{v.id} · Rolle {v.rolle} · {v.typ} · Regelsatz {v.regelsatz_basis} → {v.regelsatz_ziel}"
        f" · Status {v.zustand}",
        f"Anweisung: „{v.anweisung}“",
    ]
    if v.typ == "regel_aendern":
        for a in v.aenderungen:
            alt, neu = dict(a["parameter_alt"]), dict(a["parameter_neu"])
            zeilen.append(f"Regel {a['regel_name']}:")
            if a.get("aktiv_neu") is False:
                zeilen.append("  In Worten: die Regel wird abgeschaltet (nicht gelöscht).")
                zeilen.append(f"  - {a['regel_name']} aktiv = true")
                zeilen.append(f"  + {a['regel_name']} aktiv = false")
                continue
            for k in sorted(set(alt) | set(neu)):
                if alt.get(k) == neu.get(k):
                    continue
                if k not in neu:
                    zeilen.append(f"  In Worten: „{k}“ fällt weg (bisher {_wert(alt[k])}).")
                elif k not in alt:
                    zeilen.append(f"  In Worten: „{k}“ kommt neu dazu mit {_wert(neu[k])}.")
                else:
                    zeilen.append(
                        f"  In Worten: „{k}“ wird von {_wert(alt[k])} auf {_wert(neu[k])} geändert."
                    )
                zeilen.append(f"  - parameter.{k} = {_wert(alt.get(k))}")
                zeilen.append(f"  + parameter.{k} = {_wert(neu.get(k))}")
    elif v.typ == "regel_neu":
        for a in v.aenderungen:
            r = a["regel"]
            zeilen.append(f"Neue Regel {r['name']} ({r['typ']}, Art {r['art']}):")
            zeilen.append(f"  In Worten: {r['beschreibung']}")
            zeilen.append(f"  + {r['name']} parameter = {_wert(r['parameter'])}")
    else:
        inhalt = v.datei_inhalt or ""
        zeilen.append(f"Neue Code-Datei {v.datei_pfad} ({len(inhalt.splitlines())} Zeilen):")
        zeilen.append(
            "  In Worten: eine Sonderauswertung; sie ändert keine Regel und läuft erst nach Freigabe."
        )
        zeilen.append(f"  + sha256 {v.aenderungen[0]['inhalt_sha256']}")
    zeilen.append(f"Begründung: {v.begruendung}")
    for monat, p in sorted(v.probe.items()):
        if "vorher" not in p:
            zeilen.append(f"Probe {monat}: {p.get('hinweis', '')}")
            continue
        vg, ng = int(p["vorher"]["gesamt"]), int(p["nachher"]["gesamt"])
        zeilen.append(
            f"Probe {monat}: gesamt {vg} → {ng} ({ng - vg:+d}), Zellen ≠ 0: "
            f"{p['vorher']['zellen']} → {p['nachher']['zellen']}"
        )
        for merkmal in (*PROBE_MERKMALE, "altersgruppe"):
            vm, nm = p["vorher"]["je_merkmal"].get(merkmal, {}), p["nachher"]["je_merkmal"].get(merkmal, {})
            if vm != nm:
                zeilen.append(f"  {merkmal}: {_wert(vm)} → {_wert(nm)}")
    return "\n".join(zeilen)


class _Zurueckrollen(Exception):
    """Beendet die Probe-Transaktion ohne Wirkung."""


def _zahlen(conn: Verbindung, lieferung: str, regelsatz: str) -> dict[str, Any]:
    lauf = lauf_ausfuehren(conn, lieferung, regelsatz, reihenfolge_pruefen=False, gestartet_von="probe")
    variable = str(eine(regeln_laden(conn, regelsatz, lieferung), "zaehl", "bestand").parameter["variable"])
    je_merkmal: dict[str, dict[str, int]] = {m: defaultdict(int) for m in (*PROBE_MERKMALE, "altersgruppe")}
    zellen = 0
    zeitraum_art = ""
    for z in monatswerte(conn, lieferung, regelsatz):
        wert = int(str(z["wert"]))
        if z["variable"] != variable or wert == 0:
            continue
        zellen += 1
        zeitraum_art = str(z["zeitraum_art"])
        for m in PROBE_MERKMALE:
            je_merkmal[m][str(z[m])] += wert
        je_merkmal["altersgruppe"][altersgruppe(int(str(z["alter"])))] += wert
    return {
        "regelsatz": regelsatz,
        "zeitraum_art": zeitraum_art,
        "gesamt": lauf.gezaehlt,
        "zellen": zellen,
        "je_merkmal": {m: dict(sorted(w.items())) for m, w in je_merkmal.items()},
    }


def probe_rechnen(conn: Verbindung, vorschlag_id: int, lieferung: str) -> dict[str, Any]:
    """Rechnet den Probemonat vorher (Basisregelsatz) und nachher (mit Vorschlag) und speichert die Zahlen.

    Alles, was die Probe in der Datenbank anlegt (Läufe, Zellen, Zielregelsatz), wird zurückgerollt.
    """
    v = vorschlag_lesen(conn, vorschlag_id)
    if v.typ == "code_datei":
        ergebnis: dict[str, Any] = {
            "lieferung": lieferung,
            "hinweis": "Code-Datei ändert keine Zahl der Statistik; sie läuft erst nach Freigabe.",
        }
    else:
        if not conn.autocommit:
            raise VorschlagFehler(
                "Die Probe braucht eine Verbindung mit autocommit (der Lauf committet sonst)"
            )
        gerechnet: dict[str, Any] = {}
        with contextlib.suppress(_Zurueckrollen), conn.transaction():
            gerechnet["vorher"] = _zahlen(conn, lieferung, v.regelsatz_basis)
            einspielen(
                conn,
                vorschlag_id=v.id,
                typ=v.typ,
                regelsatz_ziel=v.regelsatz_ziel,
                regelsatz_basis=v.regelsatz_basis,
                aenderungen=v.aenderungen,
                anweisung=v.anweisung,
                begruendung=v.begruendung,
            )
            gerechnet["nachher"] = _zahlen(conn, lieferung, v.regelsatz_ziel)
            raise _Zurueckrollen
        ergebnis = {
            "lieferung": lieferung,
            **gerechnet,
            "differenz_gesamt": int(gerechnet["nachher"]["gesamt"]) - int(gerechnet["vorher"]["gesamt"]),
        }
    with conn.transaction():
        conn.execute(
            "UPDATE meta.vorschlag SET probe = probe || jsonb_build_object(%s::text, %s::jsonb) WHERE id = %s",
            (lieferung, json.dumps(ergebnis, ensure_ascii=False), vorschlag_id),
        )
    return ergebnis
