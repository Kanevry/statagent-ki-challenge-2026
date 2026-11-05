"""UC4-Adapter `antwort(frage, kontext) -> UcAntwort` für UC2 (#103, Epic #95).

Ablauf: Fall zur Frage wählen (Stichwort aus der Fall-ID, sonst `STANDARD_FALL`), Experte rechnet das
Paket des Falls, Zahlen aus dem Kontext (z. B. UC3) gehen mit ihren Belegen als Eingabe ans Panel, die
Kurzverhandlung (`uc2.antwort.kurzlauf`) bildet Positionen, der Code schreibt daraus den Text.

Zahlen kommen nur vom Experten oder aus dem Kontext. Text aus Modellen (Begründungen, Moderator-Notiz)
läuft durch `bereinige`; danach prüft `freie_zahlen` den ganzen Text mit dem Zahlenmuster aus
`uc2.verhandlung.pruefungen` und wirft `FreieZahl`, statt eine unbelegte Zahl auszuliefern.

`protokoll_id` bleibt `None`: Der Kurzlauf schreibt nicht in PG (Begründung in `uc2.antwort.kurzlauf`).
Fehler werfen (`AntwortFehler` und Unterklassen, `ModellKonfigFehler`, `BelegFehler`); der Router zählt
den UC dann als fehlend. Es gibt keinen Ersatztext.
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import Any

# plattform hat keinen py.typed-Marker (E0); wie in uc2.modelle.
from plattform.antwortform import Beleg, UcAntwort, Zahl  # type: ignore[import-untyped]

from uc2.akteure.laden import Akteur, lade_akteure
from uc2.experte.modell import ergebnis as experte_ergebnis
from uc2.experte.modell import lade_paket, zahl_de
from uc2.modelle import waehle_provider
from uc2.verhandlung import prompts
from uc2.verhandlung.belege import Beleg as PresseBeleg
from uc2.verhandlung.belege import Belegquelle, FixtureQuelle
from uc2.verhandlung.fall import Falldefinition, bekannte_faelle, lade_fall
from uc2.verhandlung.pruefungen import TOLERANZ, ZAHL_MUSTER, experten_werte, zahlen_im_text

from .kurzlauf import KURZ_MAX_AKTEURE, KURZ_RUNDEN, Kurzergebnis, KurzlaufFehler, kurzverhandlung

STANDARD_FALL = "wartezeiten"
"""Fall ohne Stichworttreffer; sein Paket ist `pakete/beispiel-wartezeiten.yaml`."""
QUELLE_EXPERTE = "uc2.experte"
QUELLE_PRESSE = "presse"
MODELLANNAHME = "Modellannahme"
ERSATZ = "(Zahl ohne Beleg entfernt)"
_KATEGORIE = {
    "konsens": "alle dafür",
    "mehrheit": "Mehrheit dafür",
    "abgelehnt": "Mehrheit dagegen",
    "offener_konflikt": "offen",
}
_ZIELPRUEFUNG = {
    "erfüllt": "erfüllt, das Ziel hält unter allen Annahmen",
    "nicht erfüllt": "nicht erfüllt, das Ziel wird unter keiner Annahme erreicht",
    "offen": "offen, das Ziel hält nur unter einem Teil der Annahmen",
}
_WORT = {1: "einer", 2: "zwei", 3: "drei", 4: "vier", 5: "fünf", 6: "sechs"}


class AntwortFehler(RuntimeError):
    """UC2 kann die Frage nicht beantworten (Panel ohne Position, leere Frage)."""


class FreieZahl(AntwortFehler):
    """Im fertigen Text steht eine Zahl, die nicht in `zahlen` steht."""


# --- Fall und Zahlen ----------------------------------------------------------------------------------


def _stichwort(fall_id: str) -> str:
    # Einfache Regel: Fall-ID ohne Endung (`wartezeiten` → `wartezeit`), damit auch der Singular trifft.
    return fall_id[: max(4, len(fall_id) - 2)].replace("-", " ").replace("_", " ")


def waehle_fall(frage: str, ordner: Path | None = None) -> Falldefinition:
    """Erster Fall (alphabetisch), dessen Stichwort in der Frage steht, sonst `STANDARD_FALL`."""
    text = frage.casefold()
    for fall_id in bekannte_faelle(ordner):
        if _stichwort(fall_id) in text:
            return lade_fall(fall_id, ordner)
    return lade_fall(STANDARD_FALL, ordner)


class _Sammlung:
    """Belege und Zahlen der Antwort; gleiche Belege stehen nur einmal in `belege`."""

    def __init__(self) -> None:
        self.belege: list[Beleg] = []
        self.zahlen: list[Zahl] = []

    def beleg(self, beleg: Beleg) -> int:
        for i, vorhanden in enumerate(self.belege):
            if vorhanden == beleg:
                return i
        self.belege.append(beleg)
        return len(self.belege) - 1

    def zahl(self, bezeichnung: str, wert: int | float, einheit: str | None, beleg: int) -> Zahl:
        zahl = Zahl(bezeichnung=bezeichnung, wert=wert, einheit=einheit, beleg=beleg)
        self.zahlen.append(zahl)
        return zahl


def _kontextzahlen(kontext: Sequence[UcAntwort], s: _Sammlung) -> list[tuple[Zahl, Beleg]]:
    """Zahlen der Kontext-Antworten mit ihrem Beleg übernehmen; der Beleg bleibt unverändert (Herkunft)."""
    uebernommen = []
    for vorher in kontext:
        for zahl in vorher.zahlen:
            beleg = vorher.belege[zahl.beleg].model_copy(deep=True)
            neu = s.zahl(zahl.bezeichnung, zahl.wert, zahl.einheit, s.beleg(beleg))
            uebernommen.append((neu, beleg))
    return uebernommen


def _experte_zahlen(voll: dict[str, Any], s: _Sammlung) -> dict[str, Zahl]:
    """Kennzahlen des Experten als `Zahl` mit einem Beleg `uc2.experte`, `ref` = Paket-ID."""
    idx = s.beleg(Beleg(uc="uc2", quelle=QUELLE_EXPERTE, ref=str(voll["paket"]), sql=None))
    k = voll["kennzahlen"]
    z = voll["zielpruefung"]
    ziel = voll["ziel"]
    zahlen = {
        "wartezeit": s.zahl("Wartezeitänderung (Modus)", k["wartezeit_aenderung_prozent"]["modus"], "%", idx),
        "wartezeit_min": s.zahl(
            "Wartezeitänderung (Minimum)", k["wartezeit_aenderung_prozent"]["min"], "%", idx
        ),
        "wartezeit_max": s.zahl(
            "Wartezeitänderung (Maximum)", k["wartezeit_aenderung_prozent"]["max"], "%", idx
        ),
        "kosten": s.zahl(
            "Mehrkosten in % der Gesundheitsausgaben (Modus)",
            k["kosten_aenderung_prozent"]["modus"],
            "%",
            idx,
        ),
        "kosten_mio": s.zahl("Mehrkosten (Modus)", k["mehrkosten_mio_eur"]["modus"], "Mio EUR", idx),
        "ziel_wartezeit": s.zahl(
            "Ziel Wartezeitänderung", ziel["wartezeit_aenderung_prozent_hoechstens"], "%", idx
        ),
        "ziel_kosten": s.zahl(
            "Ziel Mehrkosten höchstens", ziel["kosten_aenderung_prozent_hoechstens"], "%", idx
        ),
        "ecken_erreicht": s.zahl(
            "Zielprüfung: Annahme-Kombinationen mit erreichtem Ziel", z["ecken_erreicht"], None, idx
        ),
        "ecken": s.zahl("Zielprüfung: Annahme-Kombinationen gesamt", z["ecken"], None, idx),
    }
    for m in voll["massnahmen"]:
        # Katalog-Einheiten sind Sätze („% zusätzliche … Kassenstellen“); in der Zahl steht nur das Kürzel.
        einheit = str(m["einheit"])
        kurz = "%" if einheit.startswith("%") else einheit
        zahlen[f"massnahme_{m['id']}"] = s.zahl(f"Umfang: {m['name']}", m["umfang"], kurz, idx)
    return zahlen


# --- Zahlen im Text -----------------------------------------------------------------------------------


def _belegt(wert: float, zahlen: Sequence[Zahl]) -> bool:
    return any(abs(wert - abs(float(z.wert))) <= TOLERANZ for z in zahlen)


def freie_zahlen(text: str, zahlen: Sequence[Zahl]) -> list[str]:
    """Fundstellen des Zahlenmusters, deren Betrag (auf 0,05) in keiner `Zahl` steht."""
    return [fund for fund, wert in zahlen_im_text(text) if not _belegt(wert, zahlen)]


def bereinige(text: str, zahlen: Sequence[Zahl]) -> str:
    """Freie Zahlen in Modell- oder Datentext durch `ERSATZ` ersetzen."""
    for fund in freie_zahlen(text, zahlen):
        text = text.replace(fund, ERSATZ)
    return text


def _zahl_text(zahl: Zahl) -> str:
    """Deutsch formatiert. Tausenderpunkt nur, wenn das Zahlenmuster die Einheit nicht erfasst.

    Sonst läse das Muster „1.250 Mio“ als 1,25 und hielte die belegte Zahl für frei.
    """
    wert = zahl.wert
    ganz = isinstance(wert, int) or float(wert).is_integer()
    stellen = 0 if ganz else (1 if round(float(wert), 1) == wert else 2)
    text = zahl_de(float(wert), stellen)
    if zahl.einheit and ZAHL_MUSTER.match(f"1 {zahl.einheit}"):
        text = text.replace(".", "")
    return f"{text} {zahl.einheit}" if zahl.einheit else text


def _herkunft(beleg: Beleg) -> str:
    teile = [beleg.uc.upper()]
    if beleg.monat:
        teile.append(f"Monat {beleg.monat}")
    if beleg.lieferung:
        teile.append(f"Lieferung {beleg.lieferung}")
    if beleg.stand:
        teile.append(beleg.stand)
    return ", ".join(teile)


# --- Text ---------------------------------------------------------------------------------------------


def _akteur_zeile(
    akteur: Akteur,
    ergebnis: Kurzergebnis,
    titel: dict[str, str],
    s: _Sammlung,
) -> str:
    positionen = ergebnis.positionen.get(akteur.id, {})
    if akteur.id in ergebnis.ohne_zug:
        return f"- {akteur.name}: ohne gültige Antwort des Modells, keine Position."
    themen = [t["id"] for t in ergebnis.auftrag["themen"] if t["id"] in positionen]
    dafuer = [titel[t] for t in themen if positionen[t].wert >= 1]
    dagegen = [titel[t] for t in themen if positionen[t].wert <= -1]
    teile = []
    if dafuer:
        teile.append(f"dafür bei {', '.join(dafuer)}")
    if dagegen:
        teile.append(f"dagegen bei {', '.join(dagegen)}")
    if not teile:
        teile.append("unentschieden")
    zeile = f"- {akteur.name}: {'; '.join(teile)}."
    if themen:
        zeile += f" Begründung: {positionen[themen[0]].begruendung}"
    # Belege: nur IDs, die der Akteur zitiert hat und die ihm die Belegquelle gegeben hat.
    erlaubt = ergebnis.belege.get(akteur.id, {})
    zitiert: list[PresseBeleg] = []
    for t in themen:
        for bid in positionen[t].beleg_ids:
            if bid in erlaubt and erlaubt[bid] not in zitiert:
                zitiert.append(erlaubt[bid])
    if zitiert:
        for b in zitiert:
            s.beleg(Beleg(uc="uc2", quelle=QUELLE_PRESSE, monat=b.datum.strftime("%Y-%m"), ref=b.beleg_id))
        chips = ", ".join(f"{b.medium} ({b.datum.strftime('%Y-%m')})" for b in zitiert)
        zeile += f" Belege: {chips}."
    else:
        zeile += f" {MODELLANNAHME}: kein Beleg im Pressespiegel."
    return zeile


def _text(
    voll: dict[str, Any],
    ez: dict[str, Zahl],
    kontext: list[tuple[Zahl, Beleg]],
    ergebnis: Kurzergebnis,
    akteure: dict[str, Akteur],
    s: _Sammlung,
) -> str:
    n = len(ergebnis.teilnehmer)
    zeilen = [
        f"Kurzverhandlung im Panel (Simulation mit {_WORT.get(n, 'mehreren')} Akteuren, "
        f"{_WORT.get(ergebnis.runden, 'mehreren')} Runde{'n' if ergebnis.runden > 1 else ''})."
    ]
    if kontext:
        teile = [f"{z.bezeichnung} {_zahl_text(z)} ({_herkunft(b)})" for z, b in kontext]
        zeilen.append(f"Ausgangslage aus dem Kontext: {'; '.join(teile)}.")
    massnahmen = [f"{m['name']} {_zahl_text(ez[f'massnahme_{m["id"]}'])}" for m in voll["massnahmen"]]
    zeilen.append(f"Das Paket: {', '.join(massnahmen)}.")
    pruefung = voll["zielpruefung"]["ergebnis"]
    entscheidend = voll["entscheidend"]["annahme"]
    beschreibung = {a["id"]: a["beschreibung"] for a in voll["annahmen"]}
    erreicht, ecken = _zahl_text(ez["ecken_erreicht"]), _zahl_text(ez["ecken"])
    experte = (
        f"Der Experte (Rechenmodell, kein Sprachmodell) rechnet mit {_zahl_text(ez['wartezeit'])} Wartezeit "
        f"(Spanne {_zahl_text(ez['wartezeit_min'])} bis {_zahl_text(ez['wartezeit_max'])}) bei "
        f"{_zahl_text(ez['kosten'])} Mehrkosten, das sind {_zahl_text(ez['kosten_mio'])}. "
        f"Ziel: {_zahl_text(ez['ziel_wartezeit'])} Wartezeit bei höchstens {_zahl_text(ez['ziel_kosten'])} "
        f"Mehrkosten. Zielprüfung: {_ZIELPRUEFUNG.get(pruefung, pruefung)} ({erreicht} "
        f"von {ecken} Annahme-Kombinationen)."
    )
    if entscheidend in beschreibung:
        experte += f" Am meisten hängt das Ergebnis an der Annahme: {beschreibung[entscheidend]}."
    zeilen.append(experte)
    titel = {t["id"]: t["titel"] for t in ergebnis.auftrag["themen"]}
    einordnung = [
        f"{titel[t]}: {_KATEGORIE.get(e.kategorie, e.kategorie)}" for t, e in ergebnis.klassifikation.items()
    ]
    zeilen.append(f"Ergebnis je Thema: {'; '.join(einordnung)}.")
    zeilen.append("Wer ist dafür, wer dagegen:")
    zeilen += [_akteur_zeile(akteure[aid], ergebnis, titel, s) for aid in ergebnis.teilnehmer]
    bedingungen = [
        f"{akteure[aid].name}: {b}"
        for aid in ergebnis.teilnehmer
        for t in ergebnis.zuege.get(aid, {}).get("themen", [])
        for b in t["bedingungen"]
    ]
    if bedingungen:
        zeilen.append(f"Bedingungen: {'; '.join(bedingungen)}.")
    if ergebnis.notiz:
        zeilen.append(f"Moderator: {ergebnis.notiz}")
    return "\n".join(bereinige(z, s.zahlen) for z in zeilen)


# --- Adapter ------------------------------------------------------------------------------------------


def antwort(
    frage: str,
    kontext: list[UcAntwort],
    *,
    provider: str | None = None,
    quelle: Belegquelle | None = None,
    max_akteure: int = KURZ_MAX_AKTEURE,
    runden: int = KURZ_RUNDEN,
) -> UcAntwort:
    """UC2-Antwort zur Frage: verhandelte Position des Panels, Zahlen vom Experten und aus dem Kontext.

    `kontext` sind die bisherigen Antworten der Kette (z. B. UC3). Provider: Argument > `LLM_PROVIDER` >
    `modellrollen.yaml`. Belegquelle: `FixtureQuelle`, sofern nicht übergeben; eine unmaskierte Quelle
    (`IndexQuelle` vor #43) ist nur mit `mock` erlaubt (`pruefe_freigabe`).
    """
    if not frage.strip():
        raise AntwortFehler("leere Frage")
    gewaehlt = waehle_provider(provider)
    quelle = quelle or FixtureQuelle()
    fall = waehle_fall(frage)
    voll = experte_ergebnis(lade_paket(fall.paket))

    s = _Sammlung()
    kontextzahlen = _kontextzahlen(kontext, s)
    ez = _experte_zahlen(voll, s)

    experte = prompts.experte_kurz(voll)
    if kontextzahlen:
        experte["kontext_zahlen"] = [
            {
                "bezeichnung": z.bezeichnung,
                "wert": z.wert,
                "einheit": z.einheit,
                "uc": b.uc,
                "quelle": b.quelle,
                "lieferung": b.lieferung,
                "monat": b.monat,
            }
            for z, b in kontextzahlen
        ]
    werte = sorted({*experten_werte(voll), *(float(z.wert) for z, _ in kontextzahlen)})
    akteure = {a.id: a for a in lade_akteure()}
    try:
        ergebnis = kurzverhandlung(
            frage=frage,
            experte=experte,
            experte_werte=werte,
            akteure=list(akteure.values()),
            quelle=quelle,
            provider=gewaehlt,
            stichtag=fall.stichtag,
            max_akteure=max_akteure,
            runden=runden,
        )
    except KurzlaufFehler as fehler:
        raise AntwortFehler(f"Panel: {fehler}") from fehler

    text = _text(voll, ez, kontextzahlen, ergebnis, akteure, s)
    frei = freie_zahlen(text, s.zahlen)
    if frei:
        raise FreieZahl(f"Zahl ohne Eintrag in zahlen: {', '.join(frei)}")
    return UcAntwort(
        text=text,
        belege=s.belege,
        zahlen=s.zahlen,
        uc="uc2",
        modell=" + ".join(ergebnis.modelle) or None,
        protokoll_id=None,
    )
