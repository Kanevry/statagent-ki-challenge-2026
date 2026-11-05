"""Terminal-Ausgabe eines Berichts: Kopf, Auswahl, Runden mit Beleg-Chips, Matrix, Änderungen, Einordnung,
Prüfereignisse und Experte."""

from __future__ import annotations

from typing import Any

KATEGORIE_TEXT = {
    "konsens": "Konsens",
    "mehrheit": "Mehrheit",
    "abgelehnt": "abgelehnt",
    "offener_konflikt": "offener Konflikt",
}
KURZ = 160


def _kurz(text: str, n: int = KURZ) -> str:
    text = " ".join(text.split())
    return text if len(text) <= n else text[: n - 1] + "…"


def _h(wert: int | None) -> str:
    return "–" if wert is None else f"{wert:+d}"


def _p(wert: float) -> str:
    text = f"{abs(wert):.2f}".replace(".", ",")
    return ("−" if wert < 0 else "+" if wert > 0 else "") + text


def _chip(c: dict[str, str]) -> str:
    return f"[{c['beleg_id']} · {c['medium']} · {c['monat']} · {_kurz(c['titel'], 60)}]"


def _tabelle(kopf: list[str], zeilen: list[list[str]]) -> list[str]:
    breiten = [max(len(z[i]) for z in [kopf, *zeilen]) for i in range(len(kopf))]

    def zeile(z: list[str]) -> str:
        return "  " + " | ".join(w.ljust(b) for w, b in zip(z, breiten, strict=True))

    return [zeile(kopf), "  " + "-+-".join("-" * b for b in breiten), *(zeile(z) for z in zeilen)]


def als_text(b: dict[str, Any]) -> str:
    fall = b["fall"]
    aus: list[str] = []
    modelle = fall["modelle"]
    aus += [
        f"Verhandlung {fall['fall_name']} (Fall {fall['fall_id']}), Status: {fall['status']}",
        f"Frage: {fall['frage']}",
        f"Provider: {fall['provider']} · Belegquelle: {fall['belegquelle']} · Stichtag: {fall['stichtag']}",
        "Modelle: "
        + "; ".join(
            f"{rolle} {m['modell']}" + (f" (Aufwand {m['aufwand']})" if m.get("aufwand") else "")
            for rolle, m in modelle.items()
        ),
        "",
        "Auftrag (Moderator):",
        *(f"  - {t['id']}: {t['titel']}" for t in b["auftrag"]["themen"]),
        f"  Kriterien: {', '.join(b['auftrag']['kriterien'])}",
        "",
        f"Auswahl ({len(b['teilnehmer'])} von {len(b['teilnahme'])}):",
    ]
    for t in b["teilnahme"]:
        marke = "x" if t["eingeladen"] else " "
        aus.append(f"  [{marke}] {t['akteur']} ({t['belegzahl']} Belege): {_kurz(t['begruendung'])}")

    for r in b["runden"]:
        aus += ["", f"Runde {r['runde']} ({r['phase']}):"]
        for z in r["zuege"]:
            if not z["gueltig"]:
                aus.append(
                    f"  {z['akteur']}: ungültige Ausgabe, Position unverändert ({'; '.join(z['fehler'])})"
                )
                continue
            bezug = f" → bezug auf {', '.join(z['bezug_auf'])}" if z["bezug_auf"] else ""
            aus.append(f"  {z['akteur']}{bezug}")
            for t in z["themen"]:
                aus.append(f"    {t['thema']} {_h(t['haltung'])}: {_kurz(t['begruendung'])}")
                for c in t["belege"]:
                    aus.append(f"      {_chip(c)}")
                if t["bedingungen"]:
                    aus.append(f"      Bedingungen: {_kurz('; '.join(t['bedingungen']))}")
                if t["zugestaendnis"]:
                    aus.append(f"      Zugeständnis: {_kurz(t['zugestaendnis'])}")
            if z["zahlen"]:
                aus.append(
                    "    Zahlen: "
                    + "; ".join(
                        f"{str(n['wert']).replace('.', ',')} {n['einheit']} ({n['quelle']})"
                        for n in z["zahlen"]
                    )
                )
        if r["notiz"]:
            aus.append(f"  Moderator: {_kurz(r['notiz']['notiz'], 300)}")
            for e in r["notiz"].get("belege_eingefordert", []):
                aus.append(f"    Beleg eingefordert: {e['akteur']} / {e['thema']}: {e['grund']}")
            for w in r["notiz"].get("widersprueche", []):
                aus.append(
                    f"    Widerspruch ({w['art']}): {w['akteur']} / {w['thema']}: {_kurz(w['beschreibung'])}"
                )

    m = b["matrix"]
    aus += ["", "Positionsmatrix (Haltung je Runde, −2 … +2):"]
    kopf = ["Akteur", *m["themen"]]
    zeilen = [
        [a, *(" ".join(_h(w) for w in m["werte"][a][t]) for t in m["themen"])] for a in sorted(m["werte"])
    ]
    aus += _tabelle(kopf, zeilen) if zeilen else ["  (keine Positionen)"]

    aus += ["", "Positionsänderungen:"]
    if not b["aenderungen"]:
        aus.append("  keine")
    for a in b["aenderungen"]:
        aus.append(
            f"  Runde {a['runde']}: {a['akteur']} / {a['thema']}: {_h(a['alt'])} → {_h(a['neu'])}: "
            f"{_kurz(a['begruendung'])}"
        )

    aus += ["", "Einordnung je Thema (Endmatrix):"]
    for t, e in b["klassifikation"].items():
        zeile = (
            f"  {t}: {KATEGORIE_TEXT[e['kategorie']]} (dafür {len(e['zustimmend'])}, "
            f"dagegen {len(e['ablehnend'])}, enthalten {len(e['enthalten'])})"
        )
        if e["minderheit"]:
            zeile += f"; Minderheit: {', '.join(e['minderheit'])}"
        aus.append(zeile)

    aus += ["", f"Prüfereignisse ({len(b['pruefereignisse'])}):"]
    if not b["pruefereignisse"]:
        aus.append("  keine")
    for p in b["pruefereignisse"]:
        details = ", ".join(f"{k}: {v}" for k, v in p["daten"].items())
        aus.append(f"  Runde {p['runde']} {p['akteur']}: {p['art']} ({_kurz(details, 200)})")

    ex = b["experte"]
    if ex:
        w, k = ex["wartezeit_aenderung_prozent"], ex["kosten_aenderung_prozent"]
        aus += [
            "",
            f"Experte (Paket {ex['paket']}, Code ohne Sprachmodell):",
            f"  Wartezeit {_p(w['modus'])} % (Spanne {_p(w['min'])} % bis {_p(w['max'])} %)",
            f"  Kosten {_p(k['modus'])} % (Spanne {_p(k['min'])} % bis {_p(k['max'])} %)",
            f"  Zielprüfung: {ex['zielpruefung']}",
            f"  {ex['entscheidend']}",
        ]
    erg = b["ergebnis"]
    aus += [
        "",
        f"Ende: {erg['runden']} Runden, {erg['abbruch']}; {b['ereignisse']} Ereignisse." if erg else "",
    ]
    return "\n".join(aus).rstrip() + "\n"
