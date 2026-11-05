"""``complete`` und ``aktives_modell``: Routing, Fallback, Schema-Prüfung und genau eine Protokollzeile."""

from __future__ import annotations

import hashlib
import json
import time
from collections.abc import Iterator
from typing import Any, Literal, overload

import jsonschema
from pydantic import BaseModel, ValidationError

from plattform.protokoll import Modellaufruf, modellaufruf, protokoll_datei

from . import zwecke
from .azure import AUFWAND, AzureProvider
from .basis import (
    ROLLEN,
    Antwort,
    KonfigFehler,
    LlmFehler,
    Nachricht,
    Provider,
    ProviderFehler,
    Rohantwort,
    SchemaFehler,
    SchluesselFehlt,
    VoruebergehenderFehler,
)
from .claude import ClaudeProvider
from .mistral import MistralProvider
from .mock import MockProvider
from .ollama import OllamaProvider

FABRIKEN: dict[str, type[Provider]] = {
    "azure": AzureProvider,
    "mistral": MistralProvider,
    "ollama": OllamaProvider,
    "claude": ClaudeProvider,
    "mock": MockProvider,
}

#: Feste Instanzen je Provider-Name (Tests injizieren hier Provider mit MockTransport oder Fake-Runner).
INSTANZEN: dict[str, Provider] = {}

#: Zuletzt beobachtete Version je Provider (für ``aktives_modell``).
_LETZTE_VERSION: dict[str, str] = {}

Schema = type[BaseModel] | dict[str, Any] | None


def provider_instanz(name: str) -> Provider:
    return INSTANZEN.get(name) or FABRIKEN[name]()


def prompt_hash(nachrichten: list[Nachricht]) -> str:
    """sha256 über kanonisches JSON der Nachrichten (Inhalt verlässt den Prozess nie)."""
    kanonisch = json.dumps(nachrichten, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(kanonisch.encode("utf-8")).hexdigest()


def _pruefe_eingaben(nachrichten: list[Nachricht], aufwand: str | None) -> None:
    if not nachrichten:
        raise ValueError("nachrichten darf nicht leer sein")
    for n in nachrichten:
        if n.get("role") not in ROLLEN or not isinstance(n.get("content"), str):
            raise ValueError("jede Nachricht braucht role (system|user|assistant) und content (str)")
    if aufwand is not None and aufwand not in AUFWAND:
        raise ValueError(f"aufwand muss {' oder '.join(AUFWAND)} sein")


def _json_schema(schema: Schema) -> dict[str, Any] | None:
    if schema is None:
        return None
    if isinstance(schema, dict):
        return schema
    return schema.model_json_schema()


class _Verstoss(ValueError):
    """Schema-Verstoß: ``str()`` ist der Hinweis ans Modell (darf Werte nennen), ``kennung`` nur Regel/Ort."""

    def __init__(self, meldung: str, kennung: str) -> None:
        super().__init__(meldung)
        self.kennung = kennung


def _validiere(roh: Rohantwort, schema: Schema) -> dict[str, Any]:
    """Validiertes dict oder ``_Verstoss`` mit kurzer Begründung (geht als Hinweis zurück ans Modell)."""
    daten = roh.json
    if daten is None:
        try:
            daten = json.loads(roh.text)
        except json.JSONDecodeError as fehler:
            raise _Verstoss(f"Antwort ist kein gültiges JSON ({fehler.msg})", "json $") from fehler
    if isinstance(schema, dict):
        try:
            jsonschema.validate(daten, schema)
        except jsonschema.ValidationError as fehler:
            raise _Verstoss(
                f"Schema verletzt: {fehler.message}", f"{fehler.validator} {fehler.json_path}"
            ) from fehler
        if not isinstance(daten, dict):
            raise _Verstoss("Antwort muss ein JSON-Objekt sein", "type $")
        return daten
    assert schema is not None
    try:
        return schema.model_validate(daten).model_dump(mode="json")
    except ValidationError as fehler:
        erster = fehler.errors()[0]
        ort = "$" + "".join(f".{teil}" for teil in erster["loc"])
        raise _Verstoss(f"Schema verletzt: {erster['msg']}", f"{erster['type']} {ort}") from fehler


def _kennung(fehler: BaseException) -> str:
    """Fehler fürs Protokoll: nur Typ und, bei Schemafehlern, Regel und Ort. Nie der Meldungstext,
    denn der kann Teile der Modellantwort enthalten."""
    kennung = getattr(fehler, "kennung", "")
    return f"{type(fehler).__name__}: {kennung}" if kennung else type(fehler).__name__


def _summe(a: int | None, b: int | None) -> int | None:
    return b if a is None else a + (b or 0)


def _protokolliere(
    *,
    provider: str,
    modell: str,
    version: str | None,
    zweck: str,
    hash_: str,
    dauer_ms: int,
    tokens_in: int | None,
    tokens_out: int | None,
    stufe: int,
    aufwand: str | None,
    fehler: str | None,
) -> None:
    modellaufruf(
        Modellaufruf(
            provider=provider,
            modell=modell,
            version=version,
            zweck=zweck,
            prompt_hash=hash_,
            dauer_ms=dauer_ms,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            fallback_stufe=stufe,
            aufwand=aufwand,
            fehler=fehler,
        )
    )


def _ein_provider(
    instanz: Provider,
    nachrichten: list[Nachricht],
    schema: Schema,
    modell: str,
    aufwand: str | None,
    zweck: str,
) -> tuple[Rohantwort, dict[str, Any] | None]:
    """Ein Provider, bei Schema-Verstoß genau eine Wiederholung mit Fehlerhinweis."""
    json_schema = _json_schema(schema)
    roh = instanz.rufe(nachrichten, schema=json_schema, modell=modell, aufwand=aufwand, zweck=zweck)
    if schema is None:
        return roh, None
    try:
        return roh, _validiere(roh, schema)
    except _Verstoss as erster_fehler:
        hinweis = {
            "role": "user",
            "content": (
                f"Deine letzte Antwort war ungültig: {erster_fehler}. Antworte nur mit JSON nach dem Schema: "
                + json.dumps(json_schema, ensure_ascii=False)
            ),
        }
        zweiter = instanz.rufe(
            [*nachrichten, hinweis], schema=json_schema, modell=modell, aufwand=aufwand, zweck=zweck
        )
        zweiter.tokens_in = _summe(roh.tokens_in, zweiter.tokens_in)
        zweiter.tokens_out = _summe(roh.tokens_out, zweiter.tokens_out)
        try:
            return zweiter, _validiere(zweiter, schema)
        except _Verstoss as fehler:
            raise SchemaFehler(
                f"{instanz.name}: {fehler} (nach einer Wiederholung)", fehler.kennung
            ) from fehler


def _modell_fuer(instanz: Provider, stufe: int, modell: str | None, groesse: str) -> str:
    """Ein explizites ``modell`` gilt nur für Stufe 1; Fallback-Stufen nehmen ihr Standardmodell."""
    return modell if (modell and stufe == 1) else instanz.standard_modell(groesse)


def ausfuehren(
    nachrichten: list[Nachricht],
    *,
    kette: list[str],
    schema: Schema = None,
    zweck: str = "",
    modell: str | None = None,
    aufwand: str | None = None,
) -> Antwort:
    """Läuft eine gegebene Kette ab (``complete`` und der Smoke-Test ohne Fallback nutzen das)."""
    _pruefe_eingaben(nachrichten, aufwand)
    hash_ = prompt_hash(nachrichten)
    groesse = zwecke.zweck(zweck).groesse
    letzter: Exception | None = None
    start = time.perf_counter()
    name = kette[0]
    gewaehlt = modell or ""
    for stufe, name in enumerate(kette, start=1):
        instanz = provider_instanz(name)
        gewaehlt = _modell_fuer(instanz, stufe, modell, groesse)
        try:
            try:
                roh, daten = _ein_provider(instanz, nachrichten, schema, gewaehlt, aufwand, zweck)
            except SchluesselFehlt as fehler:
                if stufe == 1:
                    raise KonfigFehler(
                        f"{fehler}: der gewählte Provider braucht seinen Schlüssel"
                    ) from fehler
                raise
        except VoruebergehenderFehler as fehler:
            letzter = fehler
            continue
        except Exception as fehler:
            _protokolliere(
                provider=name,
                modell=gewaehlt,
                version=None,
                zweck=zweck,
                hash_=hash_,
                dauer_ms=round((time.perf_counter() - start) * 1000),
                tokens_in=None,
                tokens_out=None,
                stufe=stufe,
                aufwand=aufwand,
                fehler=_kennung(fehler),
            )
            raise
        dauer_ms = 0 if instanz.deterministisch else round((time.perf_counter() - start) * 1000)
        if roh.version:
            _LETZTE_VERSION[name] = roh.version
        _protokolliere(
            provider=name,
            modell=roh.modell,
            version=roh.version,
            zweck=zweck,
            hash_=hash_,
            dauer_ms=dauer_ms,
            tokens_in=roh.tokens_in,
            tokens_out=roh.tokens_out,
            stufe=stufe,
            aufwand=aufwand,
            fehler=None,
        )
        return Antwort(
            text=roh.text,
            json=daten,
            provider=name,
            modell=roh.modell,
            version=roh.version,
            dauer_ms=dauer_ms,
            tokens_in=roh.tokens_in,
            tokens_out=roh.tokens_out,
            fallback_stufe=stufe,
        )
    meldung = f"alle Stufen gescheitert ({' → '.join(kette)}): {letzter}"
    _protokolliere(
        provider=name,
        modell=gewaehlt,
        version=None,
        zweck=zweck,
        hash_=hash_,
        dauer_ms=round((time.perf_counter() - start) * 1000),
        tokens_in=None,
        tokens_out=None,
        stufe=len(kette),
        aufwand=aufwand,
        fehler=f"ProviderFehler: {' → '.join(kette)}",
    )
    raise ProviderFehler(meldung) from letzter


def _strom(
    nachrichten: list[Nachricht], kette: list[str], zweck: str, modell: str | None, aufwand: str | None
) -> Iterator[str]:
    """Streaming: Fallback bis zum ersten Teil; Protokollzeile erst nach Ende des Streams."""
    _pruefe_eingaben(nachrichten, aufwand)
    hash_ = prompt_hash(nachrichten)
    groesse = zwecke.zweck(zweck).groesse
    start = time.perf_counter()
    letzter: Exception | None = None
    for stufe, name in enumerate(kette, start=1):
        instanz = provider_instanz(name)
        gewaehlt = _modell_fuer(instanz, stufe, modell, groesse)
        fehler_text: str | None = None
        try:
            try:
                strom = instanz.strom(nachrichten, modell=gewaehlt, aufwand=aufwand, zweck=zweck)
                erster = next(strom.teile, None)
            except SchluesselFehlt as fehler:
                if stufe == 1:
                    raise KonfigFehler(
                        f"{fehler}: der gewählte Provider braucht seinen Schlüssel"
                    ) from fehler
                raise
        except VoruebergehenderFehler as fehler:
            letzter = fehler
            continue
        except Exception as fehler:
            _protokolliere(
                provider=name,
                modell=gewaehlt,
                version=None,
                zweck=zweck,
                hash_=hash_,
                dauer_ms=round((time.perf_counter() - start) * 1000),
                tokens_in=None,
                tokens_out=None,
                stufe=stufe,
                aufwand=aufwand,
                fehler=_kennung(fehler),
            )
            raise
        try:
            if erster is not None:
                yield erster
            yield from strom.teile
        except Exception as fehler:
            fehler_text = _kennung(fehler)
            raise
        finally:
            dauer_ms = 0 if instanz.deterministisch else round((time.perf_counter() - start) * 1000)
            _protokolliere(
                provider=name,
                modell=strom.modell,
                version=strom.version,
                zweck=zweck,
                hash_=hash_,
                dauer_ms=dauer_ms,
                tokens_in=strom.tokens_in,
                tokens_out=strom.tokens_out,
                stufe=stufe,
                aufwand=aufwand,
                fehler=fehler_text,
            )
        return
    meldung = f"alle Stufen gescheitert ({' → '.join(kette)}): {letzter}"
    _protokolliere(
        provider=kette[-1],
        modell=modell or "",
        version=None,
        zweck=zweck,
        hash_=hash_,
        dauer_ms=round((time.perf_counter() - start) * 1000),
        tokens_in=None,
        tokens_out=None,
        stufe=len(kette),
        aufwand=aufwand,
        fehler=f"ProviderFehler: {' → '.join(kette)}",
    )
    raise ProviderFehler(meldung) from letzter


@overload
def complete(
    nachrichten: list[Nachricht],
    schema: Schema = ...,
    stream: Literal[False] = ...,
    provider: str | None = ...,
    zweck: str = ...,
    modell: str | None = ...,
    aufwand: str | None = ...,
) -> Antwort: ...


@overload
def complete(
    nachrichten: list[Nachricht],
    schema: Schema = ...,
    *,
    stream: Literal[True],
    provider: str | None = ...,
    zweck: str = ...,
    modell: str | None = ...,
    aufwand: str | None = ...,
) -> Iterator[str]: ...


def complete(
    nachrichten: list[Nachricht],
    schema: Schema = None,
    stream: bool = False,
    provider: str | None = None,
    zweck: str = "",
    modell: str | None = None,
    aufwand: str | None = None,
) -> Antwort | Iterator[str]:
    """Ein Modellaufruf nach Vertrag M.

    ``schema`` (pydantic-Klasse oder JSON-Schema-dict) validiert die Antwort nach ``antwort.json``;
    ``stream=True`` liefert einen Iterator über Textteile (ohne Schema). Vorrang des Providers:
    Argument > ``LLM_PROVIDER`` > Vorzug des Zwecks. Jeder Aufruf schreibt genau eine Protokollzeile.
    """
    kette, _ = zwecke.kette(zweck, provider)
    if stream:
        if schema is not None:
            raise ValueError("stream=True und schema schließen sich aus")
        return _strom(nachrichten, kette, zweck, modell, aufwand)
    return ausfuehren(nachrichten, kette=kette, schema=schema, zweck=zweck, modell=modell, aufwand=aufwand)


def letzter_erfolg(max_zeilen: int = 500) -> dict[str, Any] | None:
    """Letzte Protokollzeile ohne Fehler (wer zuletzt tatsächlich geantwortet hat), sonst ``None``."""
    datei = protokoll_datei()
    if not datei.is_file():
        return None
    zeilen = datei.read_text(encoding="utf-8").splitlines()[-max_zeilen:]
    for zeile in reversed(zeilen):
        try:
            eintrag = json.loads(zeile)
        except json.JSONDecodeError:
            continue
        if not eintrag.get("fehler"):
            return {
                k: eintrag.get(k)
                for k in ("provider", "modell", "version", "fallback_stufe", "zweck", "zeit")
            }
    return None


def aktives_modell(zweck: str = "") -> dict[str, Any]:
    """Gewählter Provider (erste Stufe der Kette), Modell, Version, Quelle der Wahl und ``zuletzt``:
    wer laut Protokoll zuletzt tatsächlich geantwortet hat, mit Fallback-Stufe."""
    kette_, quelle = zwecke.kette(zweck, None)
    name = kette_[0]
    if name not in FABRIKEN:
        raise LlmFehler(f"unbekannter Provider {name!r}")
    instanz = provider_instanz(name)
    zuletzt = letzter_erfolg()
    version = _LETZTE_VERSION.get(name)
    if version is None and zuletzt and zuletzt.get("provider") == name:
        version = zuletzt.get("version")
    return {
        "provider": name,
        "modell": instanz.standard_modell(zwecke.zweck(zweck).groesse),
        "version": version,
        "quelle": quelle,
        "zuletzt": zuletzt,
    }
