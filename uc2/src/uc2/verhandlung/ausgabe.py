"""Terminal-Ausgabe eines Berichts: Kopf, Auswahl, Runden mit Beleg-Chips, Matrix, Änderungen, Einordnung,
Prüfhinweise und Rechenmodell.

Die Texte richten sich an Menschen ohne Fachwissen (Owner-Vorgabe 05.11.): Alltagssprache, Akteursnamen statt
IDs, Fachbegriffe mit kurzer Erklärung, keine Gedankenstriche."""

from __future__ import annotations

from functools import cache
from typing import Any

KATEGORIE_TEXT = {
    "konsens": "Einigung, alle dafür",
    "mehrheit": "Mehrheit dafür",
    "abgelehnt": "Mehrheit dagegen",
    "offener_konflikt": "noch strittig",
}
PRUEF_TEXT = {
    "zahl_ohne_beleg": "Zahl ohne Beleg",
    "beleg_ungueltig": "Beleg stammt nicht aus der Suche",
    "zitat": "wörtlich aus einem Artikel übernommen",
    "ungueltige_ausgabe": "Antwort nicht verwertbar",
    "zahl_widerspruch": "Zahl passt nicht zum Rechenmodell",
}
PHASE_TEXT = {
    "position": "erste Positionen",
    "debatte": "Debatte",
    "verhandlung": "Verhandlung",
    "kompromiss": "Kompromiss",
}
KURZ = 160


@cache
def _namen() -> dict[str, str]:
    """Akteur-ID → Name aus den Akteursdateien; fehlt etwas, bleibt die ID."""
    try:
        from uc2.akteure.laden import lade_akteure

        return {a.id: a.name for a in lade_akteure()}
    except Exception:  # Anzeige darf nie an einer Akteursdatei scheitern
        return {}


def _n(akteur_id: str) -> str:
    return _namen().get(akteur_id, akteur_id)


def _kurz(text: str, n: int = KURZ) -> str:
    text = " ".join(text.split())
    return text if len(text) <= n else text[: n - 1] + "…"


def _h(wert: int | None) -> str:
    if wert is None:
        return "·"
    return "0" if wert == 0 else f"{wert:+d}"


def _p(wert: float) -> str:
    text = f"{abs(wert):.2f}".replace(".", ",")
    return ("−" if wert < 0 else "+" if wert > 0 else "") + text


def _chip(c: dict[str, Any]) -> str:
    seite = f" · S. {c['pdf_seite']}" if c.get("pdf_seite") else ""
    return f"[{c['medium']} · {c['monat']} · {_kurz(c['titel'], 60)}{seite} · {c['beleg_id']}]"


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
        f"KI-Anbieter: {fall['provider']} · Belege aus: {fall['belegquelle']} · Stand der Presse: "
        f"{fall['stichtag']}",
        "Modelle: "
        + "; ".join(
            f"{rolle} {m['modell']}" + (f" (Aufwand {m['aufwand']})" if m.get("aufwand") else "")
            for rolle, m in modelle.items()
        ),
        "",
        "Worum es geht (vom Moderator festgelegt):",
        *(f"  - {t['id']}: {t['titel']}" for t in b["auftrag"]["themen"]),
        f"  Bewertet nach: {', '.join(b['auftrag']['kriterien'])}",
        "",
        f"Wer verhandelt ({len(b['teilnehmer'])} von {len(b['teilnahme'])} Interessenvertretungen, "
        "x = eingeladen):",
    ]
    for t in b["teilnahme"]:
        marke = "x" if t["eingeladen"] else " "
        aus.append(
            f"  [{marke}] {_n(t['akteur'])} ({t['belegzahl']} Presseartikel): {_kurz(t['begruendung'])}"
        )

    for r in b["runden"]:
        aus += ["", f"Runde {r['runde']} ({PHASE_TEXT.get(r['phase'], r['phase'])}):"]
        for z in r["zuege"]:
            if not z["gueltig"]:
                aus.append(
                    f"  {_n(z['akteur'])}: Antwort nicht verwertbar, Haltung bleibt wie zuvor "
                    f"({'; '.join(z['fehler'])})"
                )
                continue
            bezug = f" (geht ein auf {', '.join(_n(x) for x in z['bezug_auf'])})" if z["bezug_auf"] else ""
            aus.append(f"  {_n(z['akteur'])}{bezug}")
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
                        f"{str(n['wert']).replace('.', ',')} {n['einheit']} "
                        f"({'Rechenmodell' if n['quelle'] == 'experte' else 'Beleg ' + n['quelle']})"
                        for n in z["zahlen"]
                    )
                )
        if r["notiz"]:
            aus.append(f"  Moderator: {_kurz(r['notiz']['notiz'], 300)}")
            for e in r["notiz"].get("belege_eingefordert", []):
                aus.append(f"    Beleg eingefordert: {_n(e['akteur'])} / {e['thema']}: {e['grund']}")
            for w in r["notiz"].get("widersprueche", []):
                aus.append(
                    f"    Widerspruch ({w['art']}): {_n(w['akteur'])} / {w['thema']}: "
                    f"{_kurz(w['beschreibung'])}"
                )

    m = b["matrix"]
    aus += ["", "Haltungen je Runde (−2 stark dagegen, 0 neutral, +2 stark dafür; · = keine Angabe):"]
    kopf = ["Interessenvertretung", *m["themen"]]
    zeilen = [
        [_n(a), *(" ".join(_h(w) for w in m["werte"][a][t]) for t in m["themen"])] for a in sorted(m["werte"])
    ]
    aus += _tabelle(kopf, zeilen) if zeilen else ["  (keine Positionen)"]

    aus += ["", "Wer hat seine Haltung geändert:"]
    if not b["aenderungen"]:
        aus.append("  niemand")
    for a in b["aenderungen"]:
        aus.append(
            f"  Runde {a['runde']}: {_n(a['akteur'])} / {a['thema']}: {_h(a['alt'])} → {_h(a['neu'])}: "
            f"{_kurz(a['begruendung'])}"
        )

    aus += ["", "Ergebnis je Thema (nach der letzten Runde):"]
    for t, e in b["klassifikation"].items():
        zeile = (
            f"  {t}: {KATEGORIE_TEXT[e['kategorie']]} (dafür {len(e['zustimmend'])}, "
            f"dagegen {len(e['ablehnend'])}, neutral {len(e['enthalten'])})"
        )
        if e["minderheit"]:
            zeile += f"; überstimmt: {', '.join(_n(x) for x in e['minderheit'])}"
        aus.append(zeile)

    aus += ["", f"Prüfhinweise, vom Programm gefunden ({len(b['pruefereignisse'])}):"]
    if not b["pruefereignisse"]:
        aus.append("  keine")
    for p in b["pruefereignisse"]:
        details = ", ".join(f"{k}: {v}" for k, v in p["daten"].items())
        art = PRUEF_TEXT.get(p["art"], p["art"])
        aus.append(f"  Runde {p['runde']} {_n(p['akteur'])}: {art} ({_kurz(details, 200)})")

    ex = b["experte"]
    if ex:
        w, k = ex["wartezeit_aenderung_prozent"], ex["kosten_aenderung_prozent"]
        aus += [
            "",
            f"Rechenmodell ohne KI (Maßnahmenpaket {ex['paket']}):",
            f"  Wartezeit {_p(w['modus'])} % (je nach Annahmen {_p(w['min'])} % bis {_p(w['max'])} %)",
            f"  Kosten {_p(k['modus'])} % (je nach Annahmen {_p(k['min'])} % bis {_p(k['max'])} %)",
            f"  Ziel erreicht? {ex['zielpruefung']}",
            f"  {ex['entscheidend']}",
        ]
    erg = b["ergebnis"]
    aus += [
        "",
        f"Ende: {erg['runden']} Runden, {erg['abbruch']}; {b['ereignisse']} Ereignisse." if erg else "",
    ]
    return "\n".join(aus).rstrip() + "\n"
