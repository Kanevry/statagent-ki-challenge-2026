"""Lader für ÖNACE bis zum 5-Steller, die Regionen Österreichs je Stand und die amtlichen Gemeindeänderungen.

Alle Inhalte kommen aus den Dateien des Startpakets (``klassifikationen/``), der Code kennt nur deren Aufbau:

- ``oenace/OENACE<JJJJ>_DE_CTI.txt`` (Statistik Austria, Windows-1252, Semikolon): Ebenen 1 bis 5. Geladen
  werden die Ebenen 2 bis 5 nach ``stat.klass_oenace``, nur für Versionen, deren Abschnitte (Ebene 1) schon in
  der Tabelle stehen. Sie bekommen genau deren Gültigkeit. So entsteht keine neue Version, und der Regelstand
  (``regeln.regelstand``) bleibt gleich. ``code`` ist die Spalte „Code“ (``A 01.11-0``), wie im Umsteiger.
  ``uebergeordnet`` ist der Code der letzten Zeile mit der nächsthöheren Ebene davor.
- ``regionen/bezirke_JJJJ-01-01.csv`` und ``regionen/gemeinden_JJJJ-01-01.csv`` (UTF-8): je Stand eine Version
  ``'JJJJ-01-01'`` in ``stat.klass_region`` mit den Ebenen ``bezirk`` (übergeordnet: Bundesland) und
  ``gemeinde`` (übergeordnet: Bezirk). Ein Stand gilt ab seinem Datum bis zum Tag vor dem nächsten Stand, der
  letzte ohne Ende.
- ``regionen/Änderungen/aenderungenGemeinden_ab2002.ods``: Übergänge nach ``stat.uebergang`` mit den
  Klassifikationen ``gemeinde`` und ``bezirk`` (Regeln bei :func:`uebergaenge_bilden`). Die ODS-Datei wird
  ohne Zusatzpaket gelesen (``zipfile`` und ``xml.etree``).

Importiert ``plattform.llm`` nicht (R2).
"""

from __future__ import annotations

import csv
import io
import re
import unicodedata
import zipfile
from collections import Counter, defaultdict
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path
from xml.etree import ElementTree

from statagent import konfig
from statagent.db import Verbindung
from statagent.klass import KlassFehler, _beziehung

KLASS_ORDNER = Path("klassifikationen")
_CTI_NAME = re.compile(r"OENACE(\d{4})_DE_CTI\.txt$")
_STAND_NAME = re.compile(r"(bezirke|gemeinden)_(\d{4}-\d{2}-\d{2})\.csv$")
_ODS_MUSTER = "*/aenderungenGemeinden_ab*.ods"

#: Blätter der Änderungsliste, die Übergänge liefern; Statusänderungen (Stadt, Markt) ändern weder Code noch
#: Namen und stehen nicht in stat.klass_region.
BLATT_ALLE = "alle_GKZaenderungen"
BLATT_ZUSAMMEN = "Zusammenlegungen"
BLATT_TEILUNG = "Teilungen"
BLATT_BEZIRK = "Bezirkszusammenlegungen"
BLATT_NAME = "Namensaenderungen"
BLATT_STATUS = "Statusaenderungen"

GEMEINDE = "gemeinde"
BEZIRK = "bezirk"

_T = "urn:oasis:names:tc:opendocument:xmlns:table:1.0"
_TX = "urn:oasis:names:tc:opendocument:xmlns:text:1.0"
_OFFICE = "urn:oasis:names:tc:opendocument:xmlns:office:1.0"


# --- ÖNACE ----------------------------------------------------------------------------------------------------


@dataclass(frozen=True)
class OenaceZeile:
    version: str
    code: str  # Spalte „Code“, z. B. "A 01.11-0"
    bezeichnung: str
    ebene: int
    uebergeordnet: str | None


def oenace_lesen(datei: Path) -> list[OenaceZeile]:
    """Liest eine CTI-Datei (alle Ebenen). Version aus dem Dateinamen, übergeordnet aus der Reihenfolge."""
    treffer = _CTI_NAME.search(datei.name)
    if not treffer:
        raise KlassFehler(f"{datei.name}: Dateiname nicht im Format OENACE<JJJJ>_DE_CTI.txt.")
    version = treffer.group(1)
    leser = csv.reader(io.StringIO(datei.read_bytes().decode("cp1252")), delimiter=";", quotechar='"')
    kopf = [k.strip() for k in next(leser)]
    try:
        i_ebene, i_code, i_titel = kopf.index("Ebene"), kopf.index("Code"), kopf.index("Titel")
    except ValueError as fehler:
        raise KlassFehler(f"{datei.name}: Spalte fehlt ({fehler}).") from fehler
    letzte: dict[int, str] = {}  # je Ebene der zuletzt gelesene Code
    zeilen: list[OenaceZeile] = []
    for z in leser:
        if len(z) <= max(i_ebene, i_code, i_titel) or not z[i_code].strip():
            continue
        ebene, code = int(z[i_ebene]), z[i_code].strip()
        if ebene > 1 and ebene - 1 not in letzte:
            raise KlassFehler(
                f"{datei.name}: {code} (Ebene {ebene}) steht vor jeder Zeile der Ebene {ebene - 1}."
            )
        letzte[ebene] = code
        for tiefer in [e for e in letzte if e > ebene]:
            del letzte[tiefer]
        zeilen.append(OenaceZeile(version, code, z[i_titel].strip(), ebene, letzte.get(ebene - 1)))
    if not zeilen:
        raise KlassFehler(f"{datei.name}: keine Zeilen gefunden.")
    return zeilen


def oenace_laden(conn: Verbindung, ordner: Path) -> list[str]:
    """Schreibt die Ebenen 2 bis 5 je CTI-Datei. Liefert einen Text je Datei (Zeilen je Ebene oder Hinweis)."""
    texte: list[str] = []
    for datei in sorted(ordner.glob("OENACE*_DE_CTI.txt")):
        zeilen = [z for z in oenace_lesen(datei) if z.ebene >= 2]
        version = zeilen[0].version if zeilen else ""
        gueltig = conn.execute(
            "SELECT DISTINCT gueltig_von, gueltig_bis FROM stat.klass_oenace WHERE version = %s AND ebene = 1",
            (version,),
        ).fetchall()
        if len(gueltig) != 1:
            texte.append(
                f"Hinweis: ÖNACE {version} hat keine eindeutige Gültigkeit der Ebene 1, nicht geladen"
            )
            continue
        von, bis = gueltig[0]["gueltig_von"], gueltig[0]["gueltig_bis"]
        with conn.cursor() as cur:
            cur.executemany(
                """INSERT INTO stat.klass_oenace
                     (version, code, bezeichnung, ebene, uebergeordnet, gueltig_von, gueltig_bis)
                   VALUES (%s, %s, %s, %s, %s, %s, %s)
                   ON CONFLICT (version, code) DO UPDATE
                     SET bezeichnung = EXCLUDED.bezeichnung, ebene = EXCLUDED.ebene,
                         uebergeordnet = EXCLUDED.uebergeordnet, gueltig_von = EXCLUDED.gueltig_von,
                         gueltig_bis = EXCLUDED.gueltig_bis
                   WHERE stat.klass_oenace.ebene >= 2""",
                [(z.version, z.code, z.bezeichnung, z.ebene, z.uebergeordnet, von, bis) for z in zeilen],
            )
        je_ebene = Counter(z.ebene for z in zeilen)
        texte.append(f"ÖNACE {version} " + ", ".join(f"Ebene {e}: {n}" for e, n in sorted(je_ebene.items())))
    if not texte:
        texte.append("Hinweis: keine OENACE*_DE_CTI.txt im Startpaket, ÖNACE-Ebenen 2 bis 5 nicht geladen")
    return texte


# --- Regionen je Stand ----------------------------------------------------------------------------------------


@dataclass(frozen=True)
class RegionZeile:
    version: str  # Stand, z. B. "2011-01-01"
    code: str
    bezeichnung: str
    ebene: str  # bezirk | gemeinde
    uebergeordnet: str
    gueltig_von: date
    gueltig_bis: date | None


def staende(ordner: Path) -> list[date]:
    """Alle Stände, für die es eine Bezirks- oder Gemeindedatei gibt, aufsteigend."""
    gefunden = {_STAND_NAME.search(d.name) for d in ordner.glob("*.csv")}
    return sorted({date.fromisoformat(t.group(2)) for t in gefunden if t})


def _csv_lesen(datei: Path) -> list[dict[str, str]]:
    with datei.open(encoding="utf-8-sig", newline="") as f:
        return [
            {k.strip(): (v or "").strip() for k, v in z.items() if k}
            for z in csv.DictReader(f, delimiter=";")
        ]


def regionen_lesen(ordner: Path) -> list[RegionZeile]:
    """Bezirke und Gemeinden aller Stände. Gültig bis = Tag vor dem nächsten Stand, der letzte ohne Ende."""
    liste = staende(ordner)
    zeilen: list[RegionZeile] = []
    for i, stand in enumerate(liste):
        bis = liste[i + 1] - timedelta(days=1) if i + 1 < len(liste) else None
        version = stand.isoformat()
        for ebene, datei_art, code, name, ueber in (
            (BEZIRK, "bezirke", "BEZIRK_CODE", "BEZIRK", "BUNDESLAND_CODE"),
            (GEMEINDE, "gemeinden", "GEMEINDE_CODE", "GEMEINDE", "BEZIRK_CODE"),
        ):
            datei = ordner / f"{datei_art}_{version}.csv"
            if not datei.is_file():
                continue
            for z in _csv_lesen(datei):
                if z.get(code):
                    zeilen.append(RegionZeile(version, z[code], z[name], ebene, z[ueber], stand, bis))
    return zeilen


def regionen_laden(conn: Verbindung, ordner: Path) -> tuple[str, list[RegionZeile]]:
    """Ersetzt die Stand-Versionen (Ebenen bezirk und gemeinde) in stat.klass_region. Version 'BL' bleibt."""
    zeilen = regionen_lesen(ordner)
    if not zeilen:
        return "Hinweis: keine bezirke_/gemeinden_JJJJ-01-01.csv im Startpaket, Regionen nicht geladen", []
    conn.execute(
        """DELETE FROM stat.klass_region
           WHERE ebene IN ('bezirk', 'gemeinde') AND version ~ '^[0-9]{4}-[0-9]{2}-[0-9]{2}$'"""
    )
    with (
        conn.cursor() as cur,
        cur.copy(
            "COPY stat.klass_region (version, code, bezeichnung, ebene, uebergeordnet, gueltig_von, gueltig_bis) "
            "FROM STDIN"
        ) as kopie,
    ):
        for z in zeilen:
            kopie.write_row(
                (z.version, z.code, z.bezeichnung, z.ebene, z.uebergeordnet, z.gueltig_von, z.gueltig_bis)
            )
    je = Counter(z.ebene for z in zeilen)
    versionen = sorted({z.version for z in zeilen})
    return (
        f"Regionen {len(versionen)} Stände {versionen[0]} bis {versionen[-1]}: {je[BEZIRK]} Bezirke, "
        f"{je[GEMEINDE]} Gemeinden",
        zeilen,
    )


# --- Änderungsliste (ODS) -------------------------------------------------------------------------------------


def _zelltext(zelle: ElementTree.Element) -> str:
    """Angezeigter Text einer Zelle (Absätze mit Leerzeichen verbunden); sonst der Datumswert."""

    def text(e: ElementTree.Element) -> str:
        teile = [e.text or ""]
        for kind in e:
            if kind.tag == f"{{{_TX}}}s":
                teile.append(" " * int(kind.get(f"{{{_TX}}}c", "1")))
            elif kind.tag in (f"{{{_TX}}}tab", f"{{{_TX}}}line-break"):
                teile.append(" ")
            else:
                teile.append(text(kind))
            teile.append(kind.tail or "")
        return "".join(teile)

    absaetze = [text(p).strip() for p in zelle.findall(f"{{{_TX}}}p")]
    wert = " ".join(a for a in absaetze if a)
    return wert or zelle.get(f"{{{_OFFICE}}}date-value", "")


def ods_lesen(datei: Path) -> dict[str, list[list[str]]]:
    """Alle Blätter einer ODS-Datei als Zeilen mit Zelltexten. Leere Zeilen fallen weg, leere Zellen am Ende
    auch; wiederholte Zeilen und Spalten (``number-rows-repeated``, ``number-columns-repeated``) werden
    ausgeschrieben, solange sie Inhalt haben."""
    with zipfile.ZipFile(datei) as z:
        wurzel = ElementTree.fromstring(z.read("content.xml"))
    blaetter: dict[str, list[list[str]]] = {}
    for tabelle in wurzel.iter(f"{{{_T}}}table"):
        zeilen: list[list[str]] = []
        for zeile in tabelle.iter(f"{{{_T}}}table-row"):
            werte: list[str] = []
            leer = 0  # leere Zellen, die erst bei folgendem Inhalt ausgeschrieben werden
            for zelle in zeile:
                if zelle.tag not in (f"{{{_T}}}table-cell", f"{{{_T}}}covered-table-cell"):
                    continue
                anzahl = int(zelle.get(f"{{{_T}}}number-columns-repeated", "1"))
                wert = _zelltext(zelle)
                if not wert:
                    leer += anzahl
                    continue
                werte.extend([""] * leer + [wert] * anzahl)
                leer = 0
            if werte:
                zeilen.extend([werte] * int(zeile.get(f"{{{_T}}}number-rows-repeated", "1")))
        blaetter[tabelle.get(f"{{{_T}}}name", "")] = zeilen
    return blaetter


def _norm(text: str) -> str:
    return unicodedata.normalize("NFC", text).strip().lower()


def _datum(text: str) -> date | None:
    text = text.strip()
    if m := re.fullmatch(r"(\d{1,2})\.(\d{1,2})\.(\d{4})", text):
        return date(int(m.group(3)), int(m.group(2)), int(m.group(1)))
    if m := re.match(r"(\d{4})-(\d{2})-(\d{2})", text):
        return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    return None


def _tabelle(zeilen: list[list[str]], blatt: str, spalten: dict[str, str]) -> list[dict[str, str]]:
    """Datenzeilen eines Blatts als dict. Die Kopfzeile ist die erste Zeile mit „in Kraft seit“; Spalten werden
    über den Anfang ihres Kopftexts gefunden. Datenzeilen sind die mit einem Datum in „in Kraft seit“."""
    for i, kopf in enumerate(zeilen):
        normiert = [_norm(k) for k in kopf]
        if "in kraft seit" not in normiert:
            continue
        index: dict[str, int] = {}
        for name, anfang in spalten.items():
            treffer = [j for j, k in enumerate(normiert) if k.startswith(_norm(anfang))]
            if not treffer:
                raise KlassFehler(f"Blatt {blatt}: Spalte „{anfang}“ fehlt.")
            index[name] = treffer[0]
        index["in_kraft"] = normiert.index("in kraft seit")
        daten: list[dict[str, str]] = []
        for z in zeilen[i + 1 :]:
            werte = {n: (z[j].strip() if j < len(z) else "") for n, j in index.items()}
            if _datum(werte["in_kraft"]) is not None:
                daten.append(werte)
        return daten
    raise KlassFehler(f"Blatt {blatt}: keine Kopfzeile mit „in Kraft seit“.")


@dataclass(frozen=True)
class Aenderung:
    """Eine Zeile der Änderungsliste: Gemeinde- bzw. Bezirkscode alt und neu, in Kraft ab, Begründung."""

    klassifikation: str  # gemeinde | bezirk
    blatt: str
    code_alt: str
    code_neu: str
    in_kraft: date
    text: str  # Grund oder Rechtsgrundlage, kurz


@dataclass
class Aenderungsliste:
    aenderungen: list[Aenderung] = field(default_factory=list)
    nicht_verwendet: Counter[str] = field(default_factory=Counter)  # Blatt -> Zeilen ohne Übergang


def aenderungen_lesen(datei: Path) -> Aenderungsliste:
    """Liest die Blätter der Änderungsliste.

    - ``alle_GKZaenderungen``, ``Zusammenlegungen``, ``Teilungen``: Gemeindecode alt zu neu. Die drei Blätter
      überschneiden sich; beim Bilden der Übergänge wird jedes Paar einmal geführt, mit allen Blättern in
      ``quelle``.
    - ``Bezirkszusammenlegungen``: Gemeindecode alt zu neu und zusätzlich der Bezirk alt zu neu. Der
      Bezirkscode ist laut LIESMICH des Startpakets die ersten drei Stellen des Gemeindecodes.
    - ``Namensaenderungen``: Code bleibt, Übergang 1:1 auf denselben Code. Der Name steht in beiden Ständen
      verschieden; der Übergang belegt, dass es dieselbe Gemeinde ist, mit Rechtsgrundlage.
    - ``Statusaenderungen`` (Stadt, Markt): kein Übergang, nur gezählt.
    """
    blaetter = {_norm(n): z for n, z in ods_lesen(datei).items()}

    def blatt(name: str) -> list[list[str]]:
        if _norm(name) not in blaetter:
            raise KlassFehler(f"{datei.name}: Blatt {name} fehlt.")
        return blaetter[_norm(name)]

    liste = Aenderungsliste()
    neu = liste.aenderungen.append
    for z in _tabelle(blatt(BLATT_ALLE), BLATT_ALLE, {"alt": "Gemeindekennziffer alt",
                                                      "neu": "Gemeindekennziffer neu", "grund": "Änderungsgrund"}):  # fmt: skip
        neu(Aenderung(GEMEINDE, BLATT_ALLE, z["alt"], z["neu"], _tag(z), z["grund"]))
    for name in (BLATT_ZUSAMMEN, BLATT_TEILUNG):
        for z in _tabelle(blatt(name), name, {"alt": "Gemeindekennziffer alt", "neu": "Gemeindekennziffer neu",
                                              "grund": "Gesetzliche"}):  # fmt: skip
            neu(Aenderung(GEMEINDE, name, z["alt"], z["neu"], _tag(z), z["grund"]))
    for z in _tabelle(blatt(BLATT_BEZIRK), BLATT_BEZIRK, {"alt": "Gemeindekennziffer alt",
                      "neu": "Gemeindekennziffer neu", "b_alt": "Politischer Bezirk alt",
                      "b_neu": "Politischer Bezirk neu"}):  # fmt: skip
        text = f"{z['b_alt']} zu {z['b_neu']}"
        neu(Aenderung(GEMEINDE, BLATT_BEZIRK, z["alt"], z["neu"], _tag(z), text))
        neu(Aenderung(BEZIRK, BLATT_BEZIRK, z["alt"][:3], z["neu"][:3], _tag(z), text))
    for z in _tabelle(blatt(BLATT_NAME), BLATT_NAME, {"code": "Gemeindekennziffer", "alt": "Gemeindename alt",
                      "neu": "Gemeindename neu", "grund": "Gesetzliche"}):  # fmt: skip
        text = f"{z['alt']} heißt {z['neu']}, {z['grund']}".rstrip(", ")
        neu(Aenderung(GEMEINDE, BLATT_NAME, z["code"], z["code"], _tag(z), text))
    if _norm(BLATT_STATUS) in blaetter:
        status = _tabelle(blatt(BLATT_STATUS), BLATT_STATUS, {"code": "Gemeindekennziffer"})
        liste.nicht_verwendet[BLATT_STATUS] = len(status)
    return liste


def _tag(z: dict[str, str]) -> date:
    tag = _datum(z["in_kraft"])
    assert tag is not None  # _tabelle liefert nur Zeilen mit Datum
    return tag


@dataclass
class Uebergaenge:
    zeilen: list[dict[str, object]] = field(default_factory=list)
    je_blatt: Counter[str] = field(default_factory=Counter)  # verwendete Änderungszeilen je Blatt
    ausserhalb: Counter[str] = field(default_factory=Counter)  # Blatt -> Zeilen außerhalb der Stände
    nicht_im_stand: int = 0  # Übergänge, deren Code alt oder neu im jeweiligen Stand fehlt


def _versionen(tag: date, liste: Sequence[date]) -> tuple[date, date] | None:
    vorher = [s for s in liste if s < tag]
    nachher = [s for s in liste if s >= tag]
    if not vorher or not nachher:
        return None
    return vorher[-1], nachher[0]


def uebergaenge_bilden(
    aenderungen: Iterable[Aenderung],
    staende_liste: Sequence[date],
    bestand: dict[tuple[str, str], set[str]] | None = None,
) -> Uebergaenge:
    """Übergänge für stat.uebergang aus der Änderungsliste.

    Versionen: Eine Änderung, die am Tag T in Kraft tritt, führt von ``version_alt`` = letzter Stand vor T
    (echt kleiner) zu ``version_neu`` = erster Stand am oder nach T. Ein Stand am 1.1. zeigt also schon die
    Änderungen, die am 1.1. in Kraft treten. Fehlt einer der beiden Stände (T am oder vor dem ersten Stand,
    oder nach dem letzten), wird die Zeile nicht geladen und in ``ausserhalb`` gezählt. ``gueltig_ab`` = T
    (bei mehreren Zeilen desselben Paars das früheste T). Ausnahme mit ``bestand``: Fehlt der alte Code schon
    im Stand vor T, steht aber im Stand davor, und der neue Code ist im Stand vor T da, dann zeigt dieser
    Stand die Änderung schon. Der Übergang führt dann vom Stand davor zu diesem Stand (die Liste nennt
    zwei Zusammenlegungen mit 2.1. und 3.1.2015, der Stand vom 1.1.2015 zeigt sie bereits).

    Beziehung je Paar wie beim ÖNACE-Umsteiger aus der Zahl der Ziele des alten und der Quellen des neuen Codes,
    gezählt innerhalb desselben Versionspaars.

    Mit ``bestand`` ((Version, Ebene) -> Codes des Stands) kommt für jeden beteiligten Code, der in beiden
    Ständen vorkommt, ein Übergang auf sich selbst dazu: Er besteht weiter und gibt Gebiet ab oder nimmt
    Gebiet auf (z. B. Bezirk Bruck an der Leitha nimmt 2017 Gemeinden aus Wien-Umgebung auf). Codes, die im
    jeweiligen Stand fehlen, zählt ``nicht_im_stand``.
    """
    ergebnis = Uebergaenge()
    paare: dict[tuple[str, date, date, str, str], list[Aenderung]] = defaultdict(list)

    def im_stand(code: str, stand: date, k: str) -> bool:
        return bestand is not None and code in bestand.get((stand.isoformat(), k), set())

    for a in aenderungen:
        versionen = _versionen(a.in_kraft, staende_liste)
        if versionen is None:
            ergebnis.ausserhalb[a.blatt] += 1
            continue
        # Die Liste nennt einzelne Zusammenlegungen mit 2.1. oder 3.1., der Stand vom 1.1. zeigt sie aber schon
        # (alter Code fehlt dort, steht im Stand davor). Dann gilt der Übergang zwischen diesen beiden Ständen.
        i = staende_liste.index(versionen[0])
        if (
            bestand is not None
            and i > 0
            and a.code_alt != a.code_neu
            and not im_stand(a.code_alt, versionen[0], a.klassifikation)
            and im_stand(a.code_alt, staende_liste[i - 1], a.klassifikation)
            and im_stand(a.code_neu, versionen[0], a.klassifikation)
        ):
            versionen = (staende_liste[i - 1], versionen[0])
        ergebnis.je_blatt[a.blatt] += 1
        paare[(a.klassifikation, *versionen, a.code_alt, a.code_neu)].append(a)

    if bestand is not None:
        beteiligt: dict[tuple[str, date, date, str], list[Aenderung]] = defaultdict(list)
        for (k, alt, neu, c_alt, c_neu), liste in paare.items():
            beteiligt[(k, alt, neu, c_alt)].extend(liste)
            beteiligt[(k, alt, neu, c_neu)].extend(liste)
        for (k, alt, neu, c), liste in beteiligt.items():
            bleibt = im_stand(c, alt, k) and im_stand(c, neu, k)
            if bleibt and (k, alt, neu, c, c) not in paare:
                blaetter = ", ".join(sorted({a.blatt for a in liste}))
                tag = min(a.in_kraft for a in liste)
                paare[(k, alt, neu, c, c)].append(
                    Aenderung(k, "Stände", c, c, tag, f"Code bleibt, Gebiet ändert sich ({blaetter})")
                )

    ziele: dict[tuple[str, date, date, str], set[str]] = defaultdict(set)
    quellen: dict[tuple[str, date, date, str], set[str]] = defaultdict(set)
    for k, alt, neu, c_alt, c_neu in paare:
        ziele[(k, alt, neu, c_alt)].add(c_neu)
        quellen[(k, alt, neu, c_neu)].add(c_alt)
    for (k, alt, neu, c_alt, c_neu), liste in sorted(paare.items()):
        texte: dict[str, None] = {}
        for a in liste:
            texte.setdefault(f"{a.blatt} ({a.text})" if a.text else a.blatt)
        if bestand is not None and not (im_stand(c_alt, alt, k) and im_stand(c_neu, neu, k)):
            ergebnis.nicht_im_stand += 1
        ergebnis.zeilen.append({
            "klassifikation": k, "version_alt": alt.isoformat(), "code_alt": c_alt,
            "version_neu": neu.isoformat(), "code_neu": c_neu,
            "beziehung": _beziehung(len(ziele[(k, alt, neu, c_alt)]), len(quellen[(k, alt, neu, c_neu)])),
            "gueltig_ab": min(a.in_kraft for a in liste), "quelle": "; ".join(texte),
        })  # fmt: skip
    return ergebnis


def uebergaenge_laden(conn: Verbindung, datei: Path, staende_liste: Sequence[date],
                      regionen: Sequence[RegionZeile]) -> str:  # fmt: skip
    """Ersetzt die Übergänge der Klassifikationen gemeinde und bezirk in stat.uebergang."""
    bestand: dict[tuple[str, str], set[str]] = defaultdict(set)
    for r in regionen:
        bestand[(r.version, r.ebene)].add(r.code)
    liste = aenderungen_lesen(datei)
    ue = uebergaenge_bilden(liste.aenderungen, staende_liste, bestand)
    conn.execute("DELETE FROM stat.uebergang WHERE klassifikation IN (%s, %s)", (GEMEINDE, BEZIRK))
    with conn.cursor() as cur:
        cur.executemany(
            """INSERT INTO stat.uebergang
                 (klassifikation, version_alt, code_alt, version_neu, code_neu, beziehung, gueltig_ab, quelle)
               VALUES (%(klassifikation)s, %(version_alt)s, %(code_alt)s, %(version_neu)s, %(code_neu)s,
                       %(beziehung)s, %(gueltig_ab)s, %(quelle)s)""",
            ue.zeilen,
        )
    je = Counter(str(z["klassifikation"]) for z in ue.zeilen)
    teile = [f"Übergänge {datei.name}: {je[GEMEINDE]} Gemeinden, {je[BEZIRK]} Bezirke"]
    ausgelassen = ue.ausserhalb + liste.nicht_verwendet
    if ausgelassen:
        teile.append(
            "nicht geladen: "
            + ", ".join(f"{b} {n}" for b, n in sorted(ausgelassen.items()))
            + " (vor dem ersten oder nach dem letzten Stand; Statusänderungen ohne Codewechsel)"
        )
    if ue.nicht_im_stand:
        teile.append(f"{ue.nicht_im_stand} Übergänge mit einem Code, der im Stand fehlt")
    return ", ".join(teile)


# --- Einstieg -------------------------------------------------------------------------------------------------


def klassifikationen_einrichten(conn: Verbindung, startpaket: Path | None = None) -> str:
    """Lädt ÖNACE-Ebenen 2 bis 5, Regionen je Stand und Gemeindeänderungen aus dem Startpaket (idempotent).

    Fehlt ein Teil im Startpaket, steht ein Hinweis im Text, die anderen Teile laden trotzdem.
    """
    basis = (startpaket or konfig.startpaket()) / KLASS_ORDNER
    with conn.transaction():
        teile = oenace_laden(conn, basis / "oenace")
        regionen_ordner = basis / "regionen"
        text, regionen = regionen_laden(conn, regionen_ordner)
        teile.append(text)
        ods = sorted(regionen_ordner.glob(_ODS_MUSTER))
        if not ods:
            teile.append(
                "Hinweis: aenderungenGemeinden_ab*.ods nicht im Startpaket, Gemeindeänderungen nicht geladen"
            )
        elif not regionen:
            teile.append("Hinweis: ohne Stände keine Gemeindeänderungen geladen")
        else:
            teile.append(uebergaenge_laden(conn, ods[-1], staende(regionen_ordner), regionen))
    return "Klassifikationen: " + "; ".join(teile)
