"""Orakel und Urteil zum Fragen-Katalog (``fragen_katalog.md``).

Das Orakel rechnet das Soll je Frage mit eigenem SQL direkt auf ``stat.stat_beschaeftigte``. Es importiert nichts aus
``statagent`` (ein Test prüft das): Sonst bestätigte der Code sich selbst. Das Urteil vergleicht eine Antwort mit dem
Soll und kennt vier Ausgänge: richtig, rueckfrage, absage, falsch. Falsch heißt: eine Zahl, die nicht zur Frage gehört.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path
from typing import Any

KATALOG = Path(__file__).with_name("fragen_katalog.md")
SPALTEN = ("id", "achsen", "soll", "monate", "filter", "optionen", "frage")
SOLLE = frozenset({"zahl", "rueckfrage", "absage", "definition"})
URTEILE = ("richtig", "rueckfrage", "absage", "falsch")

#: Die Zahl, die alle Antworten als Mindestbestand nennen dürfen, ist keine Aussage über die Frage.
_FESTE_ZAHLEN = frozenset({1000})
_GROSSE_ZAHL = re.compile(r"(?<![\d.,])\d{1,3}(?:\.\d{3})+(?![\d])")
_RUECKFRAGE = re.compile(r"\?")
#: Sätze, die vom Kern nichts aussagen; in der Kette darf keiner davon als Einziges stehen bleiben.
_NUR_DEFINITION = re.compile(
    r"heißt hier|^Gemeint ist|^Ohne Zeitangabe|^Mit (?:den )?\w+ (?:ist|sind) hier|^Verstanden:"
)


# --- Katalog ----------------------------------------------------------------------------------------------------


@dataclass(frozen=True)
class Zeile:
    """Eine Frage des Katalogs mit ihrem Soll."""

    id: str
    achsen: tuple[str, ...]
    soll: str
    monate: tuple[str, ...]
    filter: dict[str, str]
    optionen: dict[str, str]
    frage: str

    @property
    def auch(self) -> frozenset[str]:
        """Weitere erlaubte Ausgänge. Eine Zahl muss auch dann stimmen."""
        return frozenset(w for w in self.optionen.get("auch", "").split(",") if w)

    @property
    def regelsatz(self) -> str:
        return self.optionen.get("regelsatz", "v1")

    @property
    def muss(self) -> bool:
        """Die Frage muss eine richtige Zahl bekommen, Rückfrage oder Absage reichen nicht."""
        return "muss" in self.optionen


def _monate_lesen(roh: str) -> tuple[str, ...]:
    monate: list[str] = []
    for teil in filter(None, (t.strip() for t in roh.split(","))):
        if teil == "-":
            continue
        if ".." not in teil:
            monate.append(teil)
            continue
        von, bis = teil.split("..")
        jahr, nummer = int(von[:4]), int(von[5:7])
        while f"{jahr:04d}-{nummer:02d}" <= bis:
            monate.append(f"{jahr:04d}-{nummer:02d}")
            jahr, nummer = (jahr + 1, 1) if nummer == 12 else (jahr, nummer + 1)
    return tuple(monate)


def _paare(roh: str) -> dict[str, str]:
    paare: dict[str, str] = {}
    for teil in filter(None, (t.strip() for t in roh.split(";"))):
        if teil == "-":
            continue
        schluessel, _, wert = teil.partition("=")
        paare[schluessel] = wert
    return paare


def katalog_lesen(pfad: Path = KATALOG) -> list[Zeile]:
    """Die Tabellenzeilen der Markdown-Datei; alles andere in der Datei ist Erklärung."""
    zeilen: list[Zeile] = []
    for roh in pfad.read_text(encoding="utf-8").splitlines():
        if not roh.startswith("| ") or roh.startswith(("| id ", "| ---")):
            continue
        felder = [f.strip() for f in roh.strip().strip("|").split(" | ")]
        if len(felder) != len(SPALTEN):
            raise ValueError(f"Zeile hat {len(felder)} statt {len(SPALTEN)} Spalten: {roh}")
        werte = dict(zip(SPALTEN, felder, strict=True))
        zeilen.append(
            Zeile(
                id=werte["id"],
                achsen=tuple(a for a in werte["achsen"].split(",") if a),
                soll=werte["soll"],
                monate=_monate_lesen(werte["monate"]),
                filter=_paare(werte["filter"]),
                optionen=_paare(werte["optionen"]),
                frage=werte["frage"],
            )
        )
    return zeilen


# --- Orakel -----------------------------------------------------------------------------------------------------


@dataclass
class Soll:
    """Was eine Antwort mit Zahl enthalten muss und was sie sonst noch nennen darf."""

    pflicht: dict[str, float] = field(default_factory=dict)
    erlaubt: set[float] = field(default_factory=set)
    nur_enthaelt: bool = False  # weitere Zahlen sind in Ordnung (Tabellen der Fluktuation, Anteile)


_MASSGEBLICH = """
WITH lauf AS (
  SELECT DISTINCT ON (lieferung) lieferung, regelstand FROM meta.lauf
  WHERE regelsatz = %(rs)s AND status IN ('fertig', 'unveraendert')
  ORDER BY lieferung, (ergebnis_status = 'endgueltig') DESC, id DESC
)"""
_SPALTE_GRUPPE = {"region": "s.region", "geschlecht": "s.geschlecht", "oenace": "s.oenace", "kategorie": None}


def _kategorie_spalte(regelsatz: str) -> str:
    # In v1 steht die Qualifikation mit Dienstvertrag in den Daten, in v2 schon die Kategorie selbst.
    return "s.qualifikation" if regelsatz == "v2" else "q.beschaeftigungskategorie"


def _bedingungen(conn: Any, zeile: Zeile, parameter: dict[str, Any]) -> list[str]:
    bedingungen: list[str] = []
    f = zeile.filter
    if "region" in f:
        bedingungen.append("s.region = ANY(%(region)s)")
        parameter["region"] = f["region"].split(",")
    if "geschlecht" in f:
        bedingungen.append("s.geschlecht = %(geschlecht)s")
        parameter["geschlecht"] = f["geschlecht"]
    if "oenace" in f:
        bedingungen.append("s.oenace = %(oenace)s")
        parameter["oenace"] = f["oenace"]
    if "branche" in f:
        # Der Name gilt je ÖNACE-Version der Zeile: dasselbe Wort hat 2008 und 2025 oft einen anderen Buchstaben.
        paare = conn.execute(
            "SELECT version || ':' || code AS paar FROM stat.klass_oenace WHERE ebene = 1 AND bezeichnung LIKE %s",
            (f["branche"],),
        ).fetchall()
        bedingungen.append("(s.oenace_version || ':' || s.oenace) = ANY(%(branche)s)")
        parameter["branche"] = [str(z["paar"]) for z in paare]
    if "kategorie" in f:
        bedingungen.append(f"{_kategorie_spalte(zeile.regelsatz)} = %(kategorie)s")
        parameter["kategorie"] = f["kategorie"]
    if "freier_dv" in f:
        bedingungen.append("q.freier_dienstvertrag IS TRUE")
    if "alter" in f:
        von, _, bis = f["alter"].partition("-")
        bedingungen.append("s.alter BETWEEN %(alter_von)s AND %(alter_bis)s")
        parameter["alter_von"], parameter["alter_bis"] = int(von), int(bis)
    return bedingungen


def _bestand(conn: Any, zeile: Zeile, gruppe: str | None) -> list[dict[str, Any]]:
    """Bestand je Monat (und je Gruppe) im maßgeblichen Lauf des Monats, unabhängig von statagent."""
    parameter: dict[str, Any] = {
        "rs": zeile.regelsatz,
        "monate": list(zeile.monate),
        "art": "Monat" if zeile.regelsatz == "v2" else "Stichtag",
        "erster": min(zeile.monate),
        "letzter": max(zeile.monate),
    }
    bedingungen = _bedingungen(conn, zeile, parameter)
    spalte = None
    if gruppe:
        spalte = _SPALTE_GRUPPE[gruppe] or _kategorie_spalte(zeile.regelsatz)
    join_q = (zeile.regelsatz == "v1" and ("kategorie" in zeile.filter or gruppe == "kategorie")) or (
        "freier_dv" in zeile.filter
    )
    abfrage = (
        _MASSGEBLICH
        + " SELECT l.lieferung AS monat, "
        + (f"{spalte} AS gruppe, " if spalte else "")
        + "sum(s.wert)::bigint AS wert"
        + " FROM stat.stat_beschaeftigte s JOIN lauf l ON s.regelstand = l.regelstand"
        + " AND to_char(s.zeitraum_bis, 'YYYY-MM') = l.lieferung"
        + (" LEFT JOIN stat.klass_qualifikation q ON q.code = s.qualifikation" if join_q else "")
        + " WHERE s.regelsatz = %(rs)s AND s.zeitraum_art = %(art)s"
        + " AND s.variable = 'Beschaeftigungsverhaeltnisse' AND l.lieferung = ANY(%(monate)s)"
        # Grenzen auf der Spalte selbst, sonst liest der Join über to_char zwei Millionen Zeilen je Frage.
        + " AND s.zeitraum_bis >= to_date(%(erster)s, 'YYYY-MM')"
        + " AND s.zeitraum_bis < to_date(%(letzter)s, 'YYYY-MM') + interval '1 month'"
        + "".join(f" AND {b}" for b in bedingungen)
        + " GROUP BY 1"
        + (", 2" if spalte else "")
        + " ORDER BY 1"
    )
    return [dict(z) for z in conn.execute(abfrage.encode(), parameter).fetchall()]


def _halb_auf(wert: Decimal) -> float:
    return float(wert.quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def _prozent(teil: int, ganz: int) -> float:
    return float((Decimal(100 * teil) / Decimal(ganz)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def _soll_bestand(conn: Any, zeile: Zeile) -> Soll:
    gruppe = zeile.optionen.get("gruppe")
    werte_je = zeile.optionen.get("werte_je")
    soll = Soll()
    if werte_je:
        # „Wien und Tirol“: je Wert eine Zahl, die Summe darf dabei stehen.
        merkmal, _, codes = werte_je.partition(":")
        zeilen = [z for z in _bestand(conn, zeile, merkmal) if str(z["gruppe"]) in codes.split(",")]
        for z in zeilen:
            soll.pflicht[f"{z['monat']} {z['gruppe']}"] = float(z["wert"])
        soll.erlaubt.add(float(sum(int(z["wert"]) for z in zeilen)))
        return soll
    zeilen = _bestand(conn, zeile, gruppe)
    if not zeilen and not gruppe:
        # Keine Zeile heißt: In diesem Monat gibt es 0 davon, nicht „keine Antwort“.
        return Soll(pflicht={m: 0.0 for m in zeile.monate})
    for z in zeilen:
        schluessel = f"{z['monat']} {z['gruppe']}" if gruppe else str(z["monat"])
        soll.pflicht[schluessel] = float(z["wert"])
    je_monat: dict[str, int] = {}
    for z in zeilen:
        je_monat[str(z["monat"])] = je_monat.get(str(z["monat"]), 0) + int(z["wert"])
    soll.erlaubt.update(float(w) for w in je_monat.values())
    if len(je_monat) > 1:
        mittel = _halb_auf(Decimal(sum(je_monat.values())) / Decimal(len(je_monat)))
        soll.erlaubt.add(mittel)
        if "mittel" in zeile.optionen:
            soll.pflicht["Durchschnitt"] = mittel
    if gruppe:
        soll.nur_enthaelt = "summen" in zeile.optionen
    return soll


def _soll_anteil(conn: Any, zeile: Zeile) -> Soll:
    """Anteil einer Ausprägung am Bestand mit denselben übrigen Filtern (Option ``anteil=merkmal:code``)."""
    merkmal, _, code = zeile.optionen["anteil"].partition(":")
    zeilen = _bestand(conn, zeile, merkmal)
    ganz = sum(int(z["wert"]) for z in zeilen)
    teil = sum(int(z["wert"]) for z in zeilen if str(z["gruppe"]) == code)
    return Soll(pflicht={"Anteil": _prozent(teil, ganz)}, nur_enthaelt=True)


def _soll_fluktuation(conn: Any, zeile: Zeile) -> Soll:
    """(Zugänge + Abgänge) / 2 / Bestand: Bewegung aus der Aggregatfunktion der Datenbank, Formel hier."""
    monat = zeile.monate[0]
    stand = conn.execute(
        (_MASSGEBLICH + " SELECT regelstand FROM lauf WHERE lieferung = %(monat)s").encode(),
        {"rs": zeile.regelsatz, "monat": monat},
    ).fetchone()
    grenzen = conn.execute(
        "SELECT (to_date(%(m)s, 'YYYY-MM') + interval '1 month - 1 day')::date AS stichtag,"
        " (to_date(%(m)s, 'YYYY-MM') - interval '1 day')::date AS vorher",
        {"m": monat},
    ).fetchone()
    bewegung = {
        str(z["oenace"]): (int(z["zugaenge"]), int(z["abgaenge"]))
        for z in conn.execute(
            "SELECT oenace, zugaenge, abgaenge FROM stat.bewegung_oenace(%s, %s, %s, %s, %s)",
            (monat, zeile.regelsatz, stand["regelstand"], grenzen["vorher"], grenzen["stichtag"]),
        ).fetchall()
    }
    bestand = {
        str(z["gruppe"]): int(z["wert"])
        for z in _bestand(conn, Zeile(**{**zeile.__dict__, "filter": {}}), "oenace")
    }
    codes = None
    if "branche" in zeile.filter:
        codes = {
            str(z["code"])
            for z in conn.execute(
                "SELECT code FROM stat.klass_oenace WHERE ebene = 1 AND bezeichnung LIKE %s"
                " AND gueltig_von <= %s AND (gueltig_bis IS NULL OR gueltig_bis >= %s)",
                (zeile.filter["branche"], grenzen["stichtag"], grenzen["stichtag"]),
            ).fetchall()
        }
    elif "oenace" in zeile.filter:
        codes = {zeile.filter["oenace"]}
    zu = sum(w[0] for c, w in bewegung.items() if codes is None or c in codes)
    ab = sum(w[1] for c, w in bewegung.items() if codes is None or c in codes)
    best = sum(w for c, w in bestand.items() if codes is None or c in codes)
    wert = float(
        (Decimal(zu + ab) * 100 / 2 / Decimal(best)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    )
    return Soll(pflicht={"Fluktuation": wert}, nur_enthaelt=True)


def soll_rechnen(conn: Any, zeile: Zeile) -> Soll:
    """Das Soll der Zeile; ohne Monate gibt es keine Zahl, die stimmen könnte."""
    if not zeile.monate:
        return Soll()
    art = zeile.optionen.get("art", "bestand")
    if art == "anteil":
        return _soll_anteil(conn, zeile)
    if art == "fluktuation":
        return _soll_fluktuation(conn, zeile)
    return _soll_bestand(conn, zeile)


# --- Urteil -----------------------------------------------------------------------------------------------------


@dataclass(frozen=True)
class Urteil:
    urteil: str  # richtig | rueckfrage | absage | falsch
    grund: str = ""
    mangel: str = ""  # Anzeige in der Kette: Der Kern-Satz sagt nicht, was er sagen sollte.
    ziel: bool = True  # Hat die Antwort den Ausgang, den der Katalog erlaubt?


def _gleich(a: float, b: float) -> bool:
    return abs(a - b) < 0.006


def _deutsch(wert: float) -> str:
    return f"{int(wert):,}".replace(",", ".")


def _grosse_zahlen(text: str) -> list[int]:
    return [int(t.group(0).replace(".", "")) for t in _GROSSE_ZAHL.finditer(text)]


def _ohne_fortschreibung(text: str) -> str:
    """Der Satz zur Fortschreibung nennt eine eigene Menge (Regel E07), keine Antwort auf die Frage."""
    return " ".join(s for s in re.split(r"(?<=\.)\s+", text) if "übernommen" not in s)


def _ohne_zahl_ausgang(antwort: dict[str, Any]) -> str:
    return "rueckfrage" if _RUECKFRAGE.search(str(antwort.get("text", ""))) else "absage"


def urteilen(zeile: Zeile, soll: Soll, antwort: dict[str, Any], kern: str | None = None) -> Urteil:
    """Vergleicht eine Antwort (``text``, ``zahlen``) mit dem Soll der Zeile.

    ``kern`` ist der erste Satz, den die Kette auf /uc4 als Antwort der Station zeigt, nur dort gesetzt.
    """
    text = str(antwort.get("text", ""))
    zahlen = antwort.get("zahlen") or []
    mangel = ""
    if not zahlen:
        unbelegt = [z for z in _grosse_zahlen(_ohne_fortschreibung(text)) if z not in _FESTE_ZAHLEN]
        if unbelegt:
            return Urteil("falsch", f"Zahl im Text ohne Beleg: {_deutsch(unbelegt[0])}", ziel=False)
        ausgang = _ohne_zahl_ausgang(antwort)
        if kern is not None and _NUR_DEFINITION.search(kern):
            mangel = f"Kern nennt nur die Definition: {kern}"
        if zeile.soll == "definition":
            if "text" in zeile.optionen and zeile.optionen["text"] not in text:
                return Urteil(ausgang, f"Text fehlt: {zeile.optionen['text']}", mangel, False)
            return (
                Urteil("richtig", "", mangel) if ausgang == "absage" else Urteil(ausgang, "", mangel, False)
            )
        if zeile.soll == ausgang:
            return Urteil("richtig", "", mangel)
        erlaubt = zeile.soll in ("rueckfrage", "absage") or ausgang in zeile.auch
        return Urteil(ausgang, "" if erlaubt else "Zahl erwartet", mangel, erlaubt)
    if "frei" in zeile.optionen and zeile.soll == "zahl":
        return Urteil(
            "richtig", "", mangel
        )  # Tabelle, die der Katalog nicht nachrechnet (Summe prüft test_frage).
    if zeile.soll != "zahl" and "zahl" not in zeile.auch:
        wert = zahlen[0].get("wert")
        return Urteil(
            "falsch", f"Zahl statt {zeile.soll}: {wert} ({zahlen[0].get('bezeichnung')})", ziel=False
        )
    if not soll.pflicht:
        return Urteil("falsch", f"Zahl, obwohl es im Soll keine gibt: {zahlen[0].get('wert')}", ziel=False)
    werte = [float(z["wert"]) for z in zahlen if z.get("wert") is not None]
    fehlend = [s for s, w in soll.pflicht.items() if not any(_gleich(w, x) for x in werte)]
    if fehlend:
        schluessel = fehlend[0]
        return Urteil(
            "falsch",
            f"Soll {schluessel} = {soll.pflicht[schluessel]:g}, Antwort nennt {[f'{x:g}' for x in werte[:4]]}",
            ziel=False,
        )
    if not soll.nur_enthaelt:
        bekannt = [*soll.pflicht.values(), *soll.erlaubt]
        fremd = [x for x in werte if not any(_gleich(x, w) for w in bekannt)]
        if fremd:
            return Urteil("falsch", f"Zahl, die nicht zur Frage gehört: {fremd[0]:g}", ziel=False)
        im_text = [
            z
            for z in _grosse_zahlen(_ohne_fortschreibung(text))
            if z not in _FESTE_ZAHLEN and not any(_gleich(float(z), w) for w in bekannt)
        ]
        if im_text:
            return Urteil(
                "falsch", f"Zahl im Text, die nicht zur Frage gehört: {_deutsch(im_text[0])}", ziel=False
            )
    if "text" in zeile.optionen and zeile.optionen["text"] not in text:
        return Urteil("falsch", f"Hinweis fehlt im Text: {zeile.optionen['text']}", ziel=False)
    if kern is not None and not re.search(r"\d[\d.,]*", _ohne_monatsangabe(kern)):
        mangel = f"Kern ohne Zahl: {kern}"
    return Urteil("richtig", "", mangel)


def _ohne_monatsangabe(kern: str) -> str:
    """Datum und Jahr im Kern zählen nicht als Zahl: „Winter 2025 heißt hier …“ nennt keine Antwort."""
    return re.sub(r"\b\d{1,2}\.\d{1,2}\.\d{4}\b|\b(?:19|20)\d{2}\b", " ", kern)


# --- Matrix -----------------------------------------------------------------------------------------------------


def matrix(ergebnisse: list[tuple[Zeile, str, Urteil]]) -> str:
    """Text für Menschen: zuerst alles Falsche, dann je Achse die Zählung je Weg."""
    wege = sorted({weg for _, weg, _ in ergebnisse})
    zeilen: list[str] = []
    falsch = [(z, w, u) for z, w, u in ergebnisse if u.urteil == "falsch"]
    zeilen.append(f"## Falsch: {len(falsch)} von {len(ergebnisse)} Antworten")
    zeilen.append("")
    for z, w, u in falsch:
        zeilen.append(f"- {z.id} [{w}] {z.frage}: {u.grund}")
    verfehlt = [(z, w, u) for z, w, u in ergebnisse if u.urteil != "falsch" and not u.ziel]
    if verfehlt:
        zeilen += ["", f"## Zahl erwartet, keine bekommen: {len(verfehlt)}", ""]
        zeilen += [f"- {z.id} [{w}] {z.frage}: {u.urteil}" for z, w, u in verfehlt]
    muss = [(z, w, u) for z, w, u in ergebnisse if z.muss and u.urteil != "richtig"]
    if muss:
        zeilen += ["", f"## Muss eine Zahl haben: {len(muss)} ohne", ""]
        zeilen += [f"- {z.id} [{w}] {z.frage}: {u.urteil}" for z, w, u in muss]
    maengel = [(z, w, u) for z, w, u in ergebnisse if u.mangel]
    if maengel:
        zeilen += ["", f"## Anzeige in der Kette: {len(maengel)}", ""]
        zeilen += [f"- {z.id} {z.frage}: {u.mangel}" for z, _, u in maengel]
    achsen = sorted({a for z, _, _ in ergebnisse for a in z.achsen})
    zeilen += [
        "",
        "## Matrix je Achse",
        "",
        "| Achse | Weg | Fragen | richtig | Rückfrage | Absage | falsch | richtig in % |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for achse in [*achsen, "alle"]:
        for weg in wege:
            teil = [u for z, w, u in ergebnisse if w == weg and (achse == "alle" or achse in z.achsen)]
            if not teil:
                continue
            zaehlung = {name: sum(u.urteil == name for u in teil) for name in URTEILE}
            anteil = round(100 * zaehlung["richtig"] / len(teil))
            zeilen.append(
                f"| {achse} | {weg} | {len(teil)} | {zaehlung['richtig']} | {zaehlung['rueckfrage']} "
                f"| {zaehlung['absage']} | {zaehlung['falsch']} | {anteil} |"
            )
    return "\n".join(zeilen) + "\n"
