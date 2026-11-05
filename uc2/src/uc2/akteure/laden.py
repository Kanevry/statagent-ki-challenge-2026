"""Lader für Akteursdateien, Institutionen und Modellrollen.

Akteursdatei = YAML-Frontmatter zwischen zwei `---`-Zeilen, danach Markdown mit `## Auftrag` und
`## Ausgabeschema`. Die Lader prüfen streng und werfen `AkteurFehler`; die gesammelte Fehlerliste
für `uc2 akteure pruefen` baut `uc2.akteure.pruefen`.
"""

from __future__ import annotations

import json
import os
from collections.abc import Mapping
from dataclasses import dataclass
from importlib import resources
from pathlib import Path
from typing import Any

import jsonschema
import yaml

from uc2 import pfade

SPRACHMODELL_PROVIDER: tuple[str, ...] = ("azure", "claude", "mock")
"""Provider, für die jede Sprachmodell-Rolle ein Modell nennen muss (ollama ist optionaler Notnagel)."""


class AkteurFehler(ValueError):
    """Akteursdatei, Institutionen oder Modellrollen sind ungültig."""


@dataclass(frozen=True)
class Akteur:
    """Ein institutioneller Akteur des Pools (Frontmatter plus Auftragstext)."""

    id: str
    version: int
    name: str
    institution: str
    rolle: str
    ziele: tuple[str, ...]
    interessen: tuple[str, ...]
    restriktionen: tuple[str, ...]
    budgetvorgaben: tuple[str, ...]
    prioritaeten: tuple[str, ...]
    rote_linien: tuple[str, ...]
    annahme: str
    themen_interesse: tuple[str, ...]
    auftrag: str
    """Markdown ab `## Auftrag` bis zum Dateiende (Auftrag und Ausgabeschema)."""
    pfad: Path


@dataclass(frozen=True)
class ProviderModell:
    """Modellangabe einer Rolle für einen Provider."""

    modell: str
    aufwand: str | None = None
    modell_env: str | None = None
    """Umgebungsvariable, die `modell` überschreibt (ollama: `OLLAMA_MODEL`)."""

    def aufgeloest(self, env: Mapping[str, str] | None = None) -> str:
        """Modellname nach Auflösung von `modell_env`; sonst der Standardwert."""
        quelle = os.environ if env is None else env
        if self.modell_env and quelle.get(self.modell_env):
            return quelle[self.modell_env]
        return self.modell


@dataclass(frozen=True)
class Modellrolle:
    """Eine Rolle aus `modellrollen.yaml`; Rollen ohne Sprachmodell haben keine Provider."""

    name: str
    sprachmodell: bool
    zweck: str | None
    provider: dict[str, ProviderModell]


def lade_schema(name: str) -> dict[str, Any]:
    """JSON-Schema aus dem Paket laden (`akteur` oder `zug`)."""
    text = resources.files("uc2.akteure").joinpath(f"{name}.schema.json").read_text(encoding="utf-8")
    schema: dict[str, Any] = json.loads(text)
    return schema


def _lies_text(pfad: Path) -> str:
    """Datei als UTF-8; Lese- und Kodierungsfehler werden zu `AkteurFehler`."""
    try:
        return pfad.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as fehler:
        raise AkteurFehler(f"{pfad.name}: nicht lesbar ({fehler})") from None


def _lies_yaml(pfad: Path) -> Any:
    """YAML-Datei laden; Lese- und Syntaxfehler werden zu `AkteurFehler`."""
    try:
        return yaml.safe_load(_lies_text(pfad))
    except yaml.YAMLError as fehler:
        raise AkteurFehler(f"{pfad.name}: kein gültiges YAML ({fehler})") from None


def lies_akteursdatei(pfad: Path) -> tuple[dict[str, Any], str]:
    """Frontmatter (als dict) und Body einer Akteursdatei; `AkteurFehler` bei kaputtem Format."""
    text = _lies_text(pfad)
    zeilen = text.splitlines(keepends=True)
    if not zeilen or zeilen[0].strip() != "---":
        raise AkteurFehler(f"{pfad.name}: Frontmatter fehlt (erste Zeile muss '---' sein)")
    try:
        ende = next(i for i in range(1, len(zeilen)) if zeilen[i].strip() == "---")
    except StopIteration:
        raise AkteurFehler(f"{pfad.name}: Frontmatter nicht mit '---' abgeschlossen") from None
    try:
        daten = yaml.safe_load("".join(zeilen[1:ende]))
    except yaml.YAMLError as fehler:
        raise AkteurFehler(f"{pfad.name}: Frontmatter ist kein gültiges YAML ({fehler})") from None
    if not isinstance(daten, dict):
        raise AkteurFehler(f"{pfad.name}: Frontmatter ist keine Zuordnung")
    return daten, "".join(zeilen[ende + 1 :])


def lade_institutionen(config: Path | None = None) -> list[str]:
    """IDs aus `institutionen.yaml` in fester Reihenfolge."""
    pfad = (config or pfade.CONFIG) / "institutionen.yaml"
    daten = _lies_yaml(pfad)
    eintraege = daten.get("institutionen") if isinstance(daten, dict) else None
    if not isinstance(eintraege, list):
        raise AkteurFehler(f"{pfad.name}: Liste 'institutionen' fehlt")
    ids: list[str] = []
    for eintrag in eintraege:
        if not isinstance(eintrag, dict) or not isinstance(eintrag.get("id"), str):
            raise AkteurFehler(f"{pfad.name}: Eintrag ohne 'id': {eintrag!r}")
        ids.append(eintrag["id"])
    return ids


def akteur_aus_daten(daten: dict[str, Any], body: str, pfad: Path) -> Akteur:
    """Frontmatter gegen `akteur.schema.json` prüfen und in einen `Akteur` überführen."""
    validator = jsonschema.Draft202012Validator(lade_schema("akteur"))
    fehler = sorted(validator.iter_errors(daten), key=lambda f: list(f.absolute_path))
    if fehler:
        erster = fehler[0]
        stelle = "/".join(str(t) for t in erster.absolute_path) or "(Wurzel)"
        raise AkteurFehler(f"{pfad.name}: {stelle}: {erster.message}")
    start = body.find("## Auftrag")

    def liste(feld: str) -> tuple[str, ...]:
        return tuple(str(x) for x in daten[feld])

    return Akteur(
        id=daten["id"],
        version=daten["version"],
        name=daten["name"],
        institution=daten["institution"],
        rolle=daten["rolle"],
        ziele=liste("ziele"),
        interessen=liste("interessen"),
        restriktionen=liste("restriktionen"),
        budgetvorgaben=liste("budgetvorgaben"),
        prioritaeten=liste("prioritaeten"),
        rote_linien=liste("rote_linien"),
        annahme=daten["annahme"],
        themen_interesse=liste("themen_interesse"),
        auftrag=body[start:].strip() if start >= 0 else body.strip(),
        pfad=pfad,
    )


def lade_akteure(verzeichnis: Path | None = None, config: Path | None = None) -> list[Akteur]:
    """Alle Akteure in der Reihenfolge von `institutionen.yaml`; `AkteurFehler` beim ersten Fehler."""
    ordner = verzeichnis or pfade.AKTEURE
    akteure: list[Akteur] = []
    for iid in lade_institutionen(config):
        pfad = ordner / f"{iid}.md"
        if not pfad.is_file():
            raise AkteurFehler(f"Akteursdatei fehlt: {pfad.name}")
        daten, body = lies_akteursdatei(pfad)
        akteur = akteur_aus_daten(daten, body, pfad)
        if akteur.id != iid or akteur.institution != iid:
            raise AkteurFehler(f"{pfad.name}: id und institution müssen '{iid}' sein")
        akteure.append(akteur)
    return akteure


def lies_modellrollen(config: Path | None = None) -> dict[str, Any]:
    """Rohdaten aus `modellrollen.yaml`."""
    pfad = (config or pfade.CONFIG) / "modellrollen.yaml"
    daten = _lies_yaml(pfad)
    if not isinstance(daten, dict) or not isinstance(daten.get("rollen"), dict):
        raise AkteurFehler(f"{pfad.name}: Zuordnung 'rollen' fehlt")
    return daten


def lade_modellrollen(config: Path | None = None) -> dict[str, Modellrolle]:
    """Rollen aus `modellrollen.yaml` als `Modellrolle`, Schlüssel = Rollenname."""
    rollen: dict[str, Modellrolle] = {}
    for name, eintrag in lies_modellrollen(config)["rollen"].items():
        if not isinstance(eintrag, dict) or not isinstance(eintrag.get("sprachmodell"), bool):
            raise AkteurFehler(f"Rolle {name}: Feld 'sprachmodell' (true/false) fehlt")
        roh = eintrag.get("provider") or {}
        if not isinstance(roh, dict):
            raise AkteurFehler(f"Rolle {name}: 'provider' ist keine Zuordnung")
        provider: dict[str, ProviderModell] = {}
        for pname, angabe in roh.items():
            if not isinstance(angabe, dict) or not isinstance(angabe.get("modell"), str):
                raise AkteurFehler(f"Rolle {name}: Provider {pname} ohne 'modell'")
            if any(not isinstance(angabe.get(f), str | None) for f in ("aufwand", "modell_env")):
                raise AkteurFehler(f"Rolle {name}: Provider {pname}: 'aufwand'/'modell_env' müssen Text sein")
            provider[str(pname)] = ProviderModell(
                modell=angabe["modell"],
                aufwand=angabe.get("aufwand"),
                modell_env=angabe.get("modell_env"),
            )
        zweck = eintrag.get("zweck")
        rollen[str(name)] = Modellrolle(
            name=str(name),
            sprachmodell=eintrag["sprachmodell"],
            zweck=zweck if isinstance(zweck, str) else None,
            provider=provider,
        )
    return rollen
