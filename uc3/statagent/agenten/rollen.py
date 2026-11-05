"""Die Rollen der Agenten: Aufgabe, erlaubte Vorschläge, System-Prompt und Antwortformat.

Jede Rolle schlägt nur vor. Ein Mensch gibt frei, das Programm rechnet. Kein Modell sieht Einzeldaten:
es bekommt Schema, Regeln, Klassifikationen und Aggregate aus den Lese-Werkzeugen.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel, Field

RollenName = Literal["datenmanagement", "klassifikation", "qs", "reporting"]

_GRUNDSAETZE = (
    "Grundsätze: Du schlägst vor, ein Mensch gibt mit Vor- und Nachnamen frei, das Programm rechnet. "
    "Du nennst nie Zahlen, die nicht im Kontext stehen, und du siehst und verlangst keine Einzeldaten "
    "(keine PERSON_ID, keine VVH_ID, keine einzelnen Sätze), nur Schema, Regeln, Klassifikationen und "
    "Aggregate. Antworte auf Deutsch und nur im verlangten JSON-Format. Ist die Anweisung mehrdeutig oder "
    "passt keine Möglichkeit, stelle eine Rückfrage statt zu raten."
)


@dataclass(frozen=True)
class Rolle:
    name: RollenName
    aufgabe: str
    #: erlaubte Vorschlagstypen
    typen: tuple[str, ...]
    #: Regeltypen (meta.regel.typ), die diese Rolle ändern oder anlegen darf
    regeltypen: tuple[str, ...]

    @property
    def zweck(self) -> str:
        """Zweck für den Modell-Schalter (Vertrag M), z. B. ``agent.klassifikation``."""
        return f"agent.{self.name}"

    @property
    def system_prompt(self) -> str:
        typen = ", ".join(self.typen)
        regeltypen = ", ".join(self.regeltypen) or "keine"
        return (
            f"Du bist die Rolle „{self.name}“ von StatAgent, der Beschäftigtenstatistik des Dachverbands. "
            f"Aufgabe: {self.aufgabe} "
            f"Erlaubte Vorschläge: {typen}; Regeltypen, die du ändern darfst: {regeltypen}. "
            "Werkzeuge: Der Kontext unten stammt aus den Lese-Werkzeugen regeln_lesen, schema_lesen, "
            "klassifikation_lesen und sql_lesen (nur stat, meta und klassifikation; Kennzahlen der Rohdaten "
            "kommen nur über roh_kennzahlen, Zellen unter 5 als „<5“). "
            "Bei regel_aendern nennt parameter_neu nur Schlüssel, die im Feld parameter der Regel schon stehen, "
            "in derselben Schreibweise und mit einem der dort erlaubten Werte; Beschreibung, Begründung und "
            "der Regelname sind keine Parameter. "
            "Regeln sind Daten: ändere bevorzugt Parameter einer bestehenden Regel (regel_aendern), lege nur "
            "dann eine neue Regel an (regel_neu), wenn es ihre Art schon gibt, und schreibe Code (code_datei) "
            "nur für Sonderauswertungen: Python mit def run(conn, lieferung) -> dict oder ein einzelnes "
            "SELECT/WITH mit dem Platzhalter %(lieferung)s. "
            "Änderungsaufträge gelten rückwirkend und landen im Regelsatz v2; v1 bleibt unverändert. "
            "Ausgabe: das JSON-Objekt Vorschlag (typ, regelsatz_ziel, aenderungen, neue_regeln, datei, "
            "begruendung, rueckfrage). " + _GRUNDSAETZE
        )


ROLLEN: dict[str, Rolle] = {
    r.name: r
    for r in (
        Rolle(
            "datenmanagement",
            "Einlesen und Zählen: Berichtszeitraum, Stichtag, Bestand, Abschnittswahl, Einleseregeln; dazu "
            "Sonderauswertungen mit Personenliste (z. B. Ministeriumslieferung) als neue Zählregel der Art "
            "personentage in einem eigenen Regelsatz, nie als Code.",
            ("regel_aendern", "regel_neu"),
            ("einlese", "zaehl"),
        ),
        Rolle(
            "klassifikation",
            "Merkmale und Zuordnungen: Beschäftigungskategorie, ÖNACE-Versionen, Quellzuordnung, Gruppierung.",
            ("regel_aendern", "regel_neu"),
            ("zuordnung", "zaehl"),
        ),
        Rolle(
            "qs",
            "Qualitätssicherung: Prüfregeln, Schwellen, Einstufung und Anhalten von Monaten.",
            ("regel_aendern", "regel_neu"),
            ("pruefung",),
        ),
        Rolle(
            "reporting",
            "Auswertungen über Aggregate als Code-Datei, ohne Regeln zu ändern; keine Personenlisten "
            "(die gehören zu datenmanagement).",
            ("code_datei",),
            (),
        ),
    )
}

KOORDINATOR_ZWECK = "agent.koordinator"


def koordinator_prompt() -> str:
    rollen = "; ".join(f"{r.name}: {r.aufgabe}" for r in ROLLEN.values())
    return (
        "Du bist der Koordinator von StatAgent. Aufgabe: Ordne die Anweisung eines Menschen genau einer Rolle "
        f"zu und formuliere den Auftrag knapp. Rollen: {rollen}. Werkzeuge: keine. "
        "Ausgabe: JSON {rolle, auftrag, rueckfrage}. Ist unklar, was gemeint ist oder welche Rolle zuständig "
        "ist, setze rolle auf null und stelle in rueckfrage eine konkrete Frage. " + _GRUNDSAETZE
    )


# --- Antwortformate (Structured Output) -----------------------------------------------------------

Wert = str | int | float | bool | list[str]


class Koordination(BaseModel):
    """Antwort des Koordinators."""

    rolle: RollenName | None = None
    auftrag: str = ""
    rueckfrage: str | None = None


class Parameter(BaseModel):
    schluessel: str
    wert: Wert


class RegelAenderung(BaseModel):
    regel_name: str
    parameter_neu: list[Parameter] = Field(description="nur die Parameter, die sich ändern")


class NeueRegel(BaseModel):
    name: str
    typ: Literal["einlese", "zaehl", "pruefung", "zuordnung"]
    art: str
    reihenfolge: int = 100
    parameter: list[Parameter]
    beschreibung: str
    begruendung: str
    grundlage: str = "Änderungsauftrag"


class CodeDatei(BaseModel):
    name: str = Field(description="Dateiname ohne Endung, nur a-z, 0-9 und _")
    sprache: Literal["python", "sql"]
    inhalt: str


class VorschlagAntwort(BaseModel):
    """Antwort einer Rolle: ein Vorschlag oder eine Rückfrage."""

    typ: Literal["regel_aendern", "regel_neu", "code_datei"] | None = None
    regelsatz_ziel: str = "v2"
    aenderungen: list[RegelAenderung] = []
    neue_regeln: list[NeueRegel] = []
    datei: CodeDatei | None = None
    begruendung: str = ""
    rueckfrage: str | None = None
