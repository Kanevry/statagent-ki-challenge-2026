"""Lokale Embeddings mit genau einem Modell für die ganze Plattform (#67).

``einbetten(texte, zweck)`` liefert je Text einen L2-normierten Vektor (Cosinus = Skalarprodukt),
``dimension()`` dessen Länge. Das Modell läuft nur lokal über sentence-transformers, nie über
``plattform.llm`` oder einen Cloud-Dienst. Es wird einmal je Prozess geladen, aus dem Hugging-Face-Cache
(``~/.cache/huggingface``, nie im Repo), und zwar nur von dort: Fehlt die Revision, bricht das Laden mit
``ModellFehlt`` ab, statt still rund 1,5 GB zu laden. Geladen wird ausdrücklich mit
``uv run python -m plattform.embeddings laden`` (oder ``EMBEDDINGS_DOWNLOAD=1``); wer lädt, akzeptiert die
Gemma Terms of Use (https://ai.google.dev/gemma/terms).

Je Aufruf schreibt ``plattform.protokoll.modellaufruf`` genau eine Zeile (provider ``lokal``, Modell,
Revision, Zweck, Hash, Dauer, Anzahl der Texte), nie einen Text.

sentence-transformers ist das Extra ``plattform[embeddings]`` und fehlt in CI. Dieses Modul importiert es
deshalb erst beim ersten Einbetten; ``import plattform.embeddings`` klappt immer.

Umgebung (falsche Werte sind ein ``ValueError`` vor dem Laden):

- ``EMBEDDINGS_MODELL``: nur ``google/embeddinggemma-2`` (``ERLAUBTE_MODELLE``, #67).
- ``EMBEDDINGS_REVISION``: Standard ``REVISION_STANDARD``.
- ``EMBEDDINGS_GERAET``: ``cpu`` (Standard), ``cuda`` oder ``mps``. ``mps`` nur zusammen mit
  ``PYTORCH_MPS_HIGH_WATERMARK_RATIO`` (> 0, vor dem Prozessstart gesetzt), damit der Grafikspeicher
  begrenzt ist. Fehlt ``PYTORCH_MPS_LOW_WATERMARK_RATIO``, setzt das Modul es auf die obere Grenze.
- ``EMBEDDINGS_STAPEL``: Texte je Vorwärtslauf, Standard 16, erlaubt 1 bis 256.
- ``EMBEDDINGS_MAX_TOKEN``: Token je Text, Standard 2048, erlaubt 1 bis 8192 (``KONTEXT``). Längere Texte
  schneidet das Modell ab; was danach steht, geht nicht in den Vektor ein.
- ``EMBEDDINGS_DOWNLOAD=1``: fehlende Revision beim Laden aus dem Netz holen.

CLI: ``uv run python -m plattform.embeddings laden`` holt die Revision in den HF-Cache;
``uv run python -m plattform.embeddings bench --n 200`` misst Ladezeit, Dimension, Durchsatz und
Speicher (auch für einen langen Text) und trägt das Ergebnis in ``docs/models.md`` ein (Abschnitt
„Embeddings“).
"""

from __future__ import annotations

import argparse
import gc
import hashlib
import importlib
import json
import os
import platform
import subprocess
import sys
import threading
import time
from dataclasses import dataclass
from datetime import datetime
from itertools import product
from pathlib import Path
from types import ModuleType, SimpleNamespace
from typing import TYPE_CHECKING, Any
from zoneinfo import ZoneInfo

from plattform.protokoll import Modellaufruf, modellaufruf

if TYPE_CHECKING:
    import psycopg

MODELL_STANDARD = "google/embeddinggemma-2"
#: Revision, mit der Bench und Tests gelaufen sind (Hugging Face, Stand 2026-10-28). Fest, damit alle Rechner
#: dieselben Vektoren liefern; ein neuer Stand ist eine bewusste Änderung mit neuer Messung.
REVISION_STANDARD = "f9972ac22e696a105c482202646979e33e4b5a1e"
#: Nur dieses Modell ist vereinbart (#67); ein zweites hieße andere Vektoren in denselben Tabellen.
ERLAUBTE_MODELLE = (MODELL_STANDARD,)
#: Nur gemessene, feste Revisionen (40 Hex-Zeichen); ``main`` zeigte still auf den neuesten Stand.
ERLAUBTE_REVISIONEN = (REVISION_STANDARD,)
#: Kontextfenster laut Modellkarte (Token je Text), Obergrenze für ``EMBEDDINGS_MAX_TOKEN``.
KONTEXT = 8192
#: Standard für ``EMBEDDINGS_MAX_TOKEN``. Der Speicher je Vorwärtslauf wächst mit Stapel × Token;
#: 64 × 8192 im Prototyp brachte den Rechner unter Speicherdruck.
MAX_TOKEN_STANDARD = 2048
#: Standard für ``EMBEDDINGS_STAPEL`` (Texte je Vorwärtslauf) und dessen Obergrenze.
STAPEL_STANDARD = 16
STAPEL_MAX = 256
#: Höchstens so viele Texte gehen je ``encode``-Aufruf ins Modell; danach wird der Geräte-Cache geleert.
SCHEIBE = 256
#: Erlaubte Werte für ``EMBEDDINGS_GERAET``.
GERAETE = ("cpu", "cuda", "mps")
_MPS_GRENZE = "PYTORCH_MPS_HIGH_WATERMARK_RATIO"
#: torch verlangt untere Grenze ≤ obere; ihr Standard (1,4 auf Apple Silicon) liegt über üblichen oberen
#: Grenzen wie 0,7, dann bricht torch beim ersten mps-Tensor ab („invalid low watermark ratio“, m5, 05.11.).
_MPS_UNTERGRENZE = "PYTORCH_MPS_LOW_WATERMARK_RATIO"
_MPS_UNTERGRENZE_STANDARD = 1.4
_LADEN_BEFEHL = "uv run python -m plattform.embeddings laden"
_BEDINGUNGEN = "Gemma Terms of Use: https://ai.google.dev/gemma/terms"
#: Nur Text: Bild- und Audio-Encoder werden nicht geladen (740M → 271M Parameter, laut Modellkarte).
_NUR_TEXT_KONFIG: dict[str, Any] = {"vision_config": None, "audio_config": None}
#: Platzhalter für Bild, Video und Audio. Ohne die zugehörigen Medien würde das Modell sie still
#: falsch einbetten, daher lehnt ``einbetten`` solche Texte ab.
_PLATZHALTER = ("<|image|>", "<|video|>", "<|audio|>")
#: Ort, an dem sentence-transformers den Prozessor lädt (siehe ``_lade_nur_text``).
_PROZESSOR_MODUL = "sentence_transformers.base.modules.transformer"
_INSTALLIEREN = "uv sync --all-packages --all-extras (Extra plattform[embeddings])"


class EmbeddingsFehlen(ImportError):
    """sentence-transformers ist nicht installiert (CI, Jury-Rechner ohne Extra)."""


class ModellFehlt(RuntimeError):
    """Die Revision liegt nicht im HF-Cache; geladen wird nur ausdrücklich (``laden``)."""


@dataclass(frozen=True, slots=True)
class _Einstellung:
    """Gelesene und geprüfte Umgebung; die ersten vier Felder bestimmen, ob neu geladen wird."""

    modell: str
    revision: str
    geraet: str
    max_token: int
    stapel: int

    @property
    def schluessel(self) -> tuple[str, str, str, int]:
        return (self.modell, self.revision, self.geraet, self.max_token)


@dataclass(frozen=True, slots=True)
class _Geladen:
    schluessel: tuple[str, str, str, int]
    modell: Any
    name: str
    revision: str
    geraet: str
    ladezeit_ms: int


_GELADEN: _Geladen | None = None
_SPERRE = threading.Lock()


def modellname() -> str:
    """Name des Modells; ein anderes als das vereinbarte ist ein ``ValueError`` (#67)."""
    name = os.environ.get("EMBEDDINGS_MODELL", "").strip() or MODELL_STANDARD
    if name not in ERLAUBTE_MODELLE:
        raise ValueError(
            f"EMBEDDINGS_MODELL={name!r} ist nicht vereinbart; erlaubt: {', '.join(ERLAUBTE_MODELLE)} "
            "(ein Embedding-Modell für die ganze Plattform, #67)"
        )
    return name


def _revision_wunsch() -> str:
    revision = os.environ.get("EMBEDDINGS_REVISION", "").strip() or REVISION_STANDARD
    if revision not in ERLAUBTE_REVISIONEN:
        raise ValueError(
            f"EMBEDDINGS_REVISION={revision!r} ist nicht gemessen; erlaubt: {', '.join(ERLAUBTE_REVISIONEN)} "
            "(neue Revision nur mit neuer Messung, #67)"
        )
    return revision


def _geraet_wunsch() -> str:
    """``cpu``, wenn nichts gesetzt ist. ``mps`` nur mit begrenztem Grafikspeicher, sonst ``ValueError``."""
    geraet = os.environ.get("EMBEDDINGS_GERAET", "").strip().lower() or "cpu"
    if geraet not in GERAETE:
        raise ValueError(f"EMBEDDINGS_GERAET={geraet!r} unbekannt; erlaubt: {', '.join(GERAETE)}")
    if geraet == "mps":
        grenze = os.environ.get(_MPS_GRENZE, "").strip()
        try:
            gueltig = float(grenze) > 0
        except ValueError:
            gueltig = False
        if not gueltig:
            # 0.0 hieße bei torch: keine Grenze, also gerade der Speicherdruck, den die Regel verhindern soll
            raise ValueError(
                f"EMBEDDINGS_GERAET=mps braucht {_MPS_GRENZE} > 0 (z. B. 0.7), gesetzt vor dem Start des "
                "Prozesses; ohne Grenze belegt mps womöglich den ganzen Speicher. Sonst cpu nehmen."
            )
        _mps_untergrenze(float(grenze))
    return geraet


def _mps_untergrenze(obere: float) -> None:
    """Setzt die untere mps-Grenze auf die obere, wenn sie fehlt und ihr torch-Standard darüber läge.

    Läuft vor dem ersten mps-Tensor (torch liest beide Werte, wenn der mps-Speicher angelegt wird). Eine
    gesetzte untere Grenze über der oberen ist ein Fehler, kein stilles Anpassen.
    """
    roh = os.environ.get(_MPS_UNTERGRENZE, "").strip()
    if not roh:
        if obere < _MPS_UNTERGRENZE_STANDARD:
            os.environ[_MPS_UNTERGRENZE] = repr(obere)
        return
    try:
        untere = float(roh)
    except ValueError:
        untere = -1.0
    if not 0 < untere <= obere:
        raise ValueError(f"{_MPS_UNTERGRENZE}={roh!r} ungültig; erlaubt: > 0 und ≤ {_MPS_GRENZE} ({obere})")


def _ganzzahl(variable: str, standard: int, hoechstens: int) -> int:
    roh = os.environ.get(variable, "").strip()
    if not roh:
        return standard
    try:
        wert = int(roh)
    except ValueError:
        wert = 0
    if not 1 <= wert <= hoechstens:
        raise ValueError(f"{variable}={roh!r} ungültig; erlaubt: ganze Zahl von 1 bis {hoechstens}")
    return wert


def _einstellung() -> _Einstellung:
    return _Einstellung(
        modell=modellname(),
        revision=_revision_wunsch(),
        geraet=_geraet_wunsch(),
        max_token=_ganzzahl("EMBEDDINGS_MAX_TOKEN", MAX_TOKEN_STANDARD, KONTEXT),
        stapel=_ganzzahl("EMBEDDINGS_STAPEL", STAPEL_STANDARD, STAPEL_MAX),
    )


def _bibliothek(name: str) -> ModuleType:
    """Import erst bei Bedarf; über ``importlib``, damit mypy in CI ohne das Extra gleich prüft wie lokal."""
    try:
        return importlib.import_module(name)
    except ImportError as fehler:
        raise EmbeddingsFehlen(f"{name} fehlt für plattform.embeddings: {_INSTALLIEREN}") from fehler


def _snapshot(name: str, revision: str, *, download: bool | None = None) -> Path:
    """Revision im HF-Cache; aus dem Netz nur mit ``download`` (Standard: ``EMBEDDINGS_DOWNLOAD=1``)."""
    if download is None:
        download = os.environ.get("EMBEDDINGS_DOWNLOAD", "").strip() == "1"
    hub = _bibliothek("huggingface_hub")
    if download:
        return Path(hub.snapshot_download(name, revision=revision))
    fehlt = _bibliothek("huggingface_hub.errors").LocalEntryNotFoundError
    try:
        return Path(hub.snapshot_download(name, revision=revision, local_files_only=True))
    except fehlt as fehler:
        raise ModellFehlt(
            f"{name} (Revision {revision[:12]}) liegt nicht im Hugging-Face-Cache. Einmalig laden mit "
            f"`{_LADEN_BEFEHL}` (rund 1,5 GB; {_BEDINGUNGEN}) oder EMBEDDINGS_DOWNLOAD=1 setzen."
        ) from fehler


def laden() -> str:
    """Lädt die eingestellte Revision (Standard ``REVISION_STANDARD``) ausdrücklich in den HF-Cache.

    Gibt den Namen des Snapshot-Ordners zurück (Commit-Hash), nicht den Pfad. Lädt nur die Dateien, nicht
    das Modell in den Speicher.
    """
    return _snapshot(modellname(), _revision_wunsch(), download=True).name


def _lade_nur_text(pfad: Path, geraet: str) -> Any:
    """Lädt das Modell nur mit dem Text-Teil.

    sentence-transformers lädt den Prozessor über ``AutoProcessor``. Für embeddinggemma-2 enthält er auch
    Bild-, Video- und Audio-Prozessoren, die torchvision und Pillow brauchen (keine Abhängigkeiten der
    Plattform). Für reinen Text ruft dieser Prozessor nur den Tokenizer auf (``ProcessorMixin.__call__``
    ohne Medien). Deshalb setzen wir für die Dauer des Ladens den Tokenizer an seine Stelle. Verschiebt
    eine neue Version von sentence-transformers die Stelle, bricht das hier laut ab (AttributeError),
    nicht still.
    """
    st = _bibliothek("sentence_transformers")
    torch = _bibliothek("torch")
    auto_tokenizer = _bibliothek("transformers").AutoTokenizer
    modul: Any = _bibliothek(_PROZESSOR_MODUL)  # Any: das Attribut wird zur Laufzeit ersetzt
    original = modul.AutoProcessor
    modul.AutoProcessor = SimpleNamespace(from_pretrained=auto_tokenizer.from_pretrained)
    try:
        modell = st.SentenceTransformer(
            str(pfad),
            device=geraet,
            # float32: bfloat16 brachte im Prototyp keinen Gewinn (mps) bzw. war 6x langsamer (cpu) und weicht
            # bis 0,03 je Komponente ab; float16 liefert laut Modellkarte NaN.
            model_kwargs={"dtype": torch.float32},
            config_kwargs=dict(_NUR_TEXT_KONFIG),
        )
    finally:
        modul.AutoProcessor = original
    return modell


def _laden(einstellung: _Einstellung) -> _Geladen:
    """Modell einmal je Prozess; andere Revision, anderes Gerät oder ``max_token`` lädt neu."""
    global _GELADEN
    with _SPERRE:
        if _GELADEN is not None and _GELADEN.schluessel == einstellung.schluessel:
            return _GELADEN
        _bibliothek("sentence_transformers")  # fehlt das Extra: abbrechen, bevor der Cache berührt wird
        if _GELADEN is not None:
            # das alte Modell zuerst freigeben, sonst liegen beim Wechsel kurz zwei Modelle im Speicher
            altes_geraet = _GELADEN.geraet
            _GELADEN = None
            gc.collect()
            _cache_leeren(altes_geraet)
        start = time.perf_counter()
        pfad = _snapshot(einstellung.modell, einstellung.revision)
        modell = _lade_nur_text(pfad, einstellung.geraet)
        # sentence-transformers schneidet jeden Text nach so vielen Token ab
        modell.max_seq_length = einstellung.max_token
        _GELADEN = _Geladen(
            schluessel=einstellung.schluessel,
            modell=modell,
            name=einstellung.modell,
            revision=pfad.name,  # Snapshot-Ordner im HF-Cache = Commit-Hash der Revision
            geraet=str(modell.device.type),
            ladezeit_ms=round((time.perf_counter() - start) * 1000),
        )
        return _GELADEN


def _cache_leeren(geraet: str) -> None:
    """Gibt den Zwischenspeicher von mps oder cuda an den Treiber zurück; cpu hat keinen."""
    if geraet in ("mps", "cuda"):
        getattr(_bibliothek("torch"), geraet).empty_cache()


def entladen() -> None:
    """Gibt das Modell frei (Speicher von Prozess und Gerät); das nächste Einbetten lädt neu."""
    global _GELADEN
    with _SPERRE:
        geraet = _GELADEN.geraet if _GELADEN is not None else None
        _GELADEN = None
    if geraet is not None:
        gc.collect()
        _cache_leeren(geraet)


def texte_hash(texte: list[str], aufgabe: str | None = None) -> str:
    """sha256 über kanonisches JSON der Texte (und der Aufgabe); der Inhalt bleibt im Prozess."""
    kanonisch = json.dumps(
        {"aufgabe": aufgabe, "texte": texte}, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    return hashlib.sha256(kanonisch.encode("utf-8")).hexdigest()


def _pruefe(texte: list[str], zweck: str) -> None:
    if not isinstance(texte, list) or not all(isinstance(t, str) for t in texte):
        raise TypeError("texte muss eine Liste von str sein")
    if not isinstance(zweck, str) or not zweck.strip():
        raise ValueError("zweck darf nicht leer sein (steht im Protokoll)")
    for text in texte:
        for marke in _PLATZHALTER:
            if marke in text:
                raise ValueError(f"Text enthält den Medien-Platzhalter {marke}; nur reiner Text ist erlaubt")


def einbetten(texte: list[str], zweck: str, *, aufgabe: str | None = None) -> list[list[float]]:
    """Je Text ein L2-normierter Vektor der Länge ``dimension()``; gleiche Texte ergeben gleiche Vektoren.

    ``aufgabe`` wählt einen Prompt des Modells (embeddinggemma-2: ``query`` und ``document`` für Suche,
    ``STS`` für Ähnlichkeit, ``Classification``, ``Clustering``). Ohne Aufgabe geht der Text unverändert
    ins Modell. Texte über ``EMBEDDINGS_MAX_TOKEN`` Token schneidet das Modell ab. Die Texte gehen in
    Scheiben zu höchstens ``SCHEIBE`` ins Modell; das Ergebnis steht in Eingabereihenfolge, und es gibt
    genau eine Protokollzeile je Aufruf. Eine leere Liste ruft kein Modell auf und schreibt keine
    Protokollzeile; eine ungültige Umgebung ist ein ``ValueError`` ohne Protokollzeile.
    """
    _pruefe(texte, zweck)
    if not texte:
        return []
    einstellung = _einstellung()
    start = time.perf_counter()
    geladen: _Geladen | None = None
    fehler: str | None = None
    try:
        geladen = _laden(einstellung)
        vektoren: list[list[float]] = []
        for anfang in range(0, len(texte), SCHEIBE):
            scheibe = geladen.modell.encode(
                texte[anfang : anfang + SCHEIBE],
                prompt_name=aufgabe,
                batch_size=einstellung.stapel,
                normalize_embeddings=True,  # Cosinus = Skalarprodukt, nicht der Modellkonfig überlassen
                show_progress_bar=False,
                convert_to_numpy=True,
            )
            vektoren.extend(scheibe.tolist())  # numpy float32 → Python float
            _cache_leeren(geladen.geraet)
        return vektoren
    except Exception as ausnahme:
        fehler = type(ausnahme).__name__
        raise
    finally:
        modellaufruf(
            Modellaufruf(
                provider="lokal",
                modell=geladen.name if geladen else einstellung.modell,
                version=geladen.revision if geladen else None,
                zweck=zweck,
                prompt_hash=texte_hash(texte, aufgabe),
                dauer_ms=round((time.perf_counter() - start) * 1000),
                tokens_in=None,
                tokens_out=None,
                fallback_stufe=1,
                fehler=fehler,
                anzahl_texte=len(texte),
            )
        )


def dimension() -> int:
    """Länge der Vektoren (embeddinggemma-2: 768). Lädt das Modell, falls nötig."""
    return int(_laden(_einstellung()).modell.get_embedding_dimension())


def pgvector_verfuegbar(conn: psycopg.Connection) -> bool:
    """Ob der Server die Erweiterung ``vector`` anbietet (verfügbar, nicht unbedingt installiert).

    Ohne pgvector speichern UCs ``float4[]`` und rechnen Cosinus in SQL oder numpy; die Vektoren sind
    normiert, Cosinus ist also das Skalarprodukt.
    """
    return conn.execute("select 1 from pg_available_extensions where name = 'vector'").fetchone() is not None


# --- CLI: bench ---------------------------------------------------------------------------------------

ABSCHNITT = "## Embeddings"

_SUBJEKTE = (
    "Die Beschäftigtenstatistik",
    "Der Dachverband",
    "Die Gesundheitskasse",
    "Die Pensionsversicherung",
    "Die Unfallversicherung",
    "Das Statistikteam",
    "Die Meldestelle",
    "Der Prüfbericht",
)
_VERBEN = ("zählt", "meldet", "prüft", "veröffentlicht", "korrigiert")
_OBJEKTE = (
    "die geringfügig Beschäftigten",
    "die Pflegegeldanträge",
    "die Beitragsgrundlagen",
    "die Revisionen des Vormonats",
    "die Dienstverhältnisse nach ÖNACE",
)
_ORTE = ("in Wien", "im Burgenland", "in Tirol", "in der Steiermark", "in Kärnten", "für ganz Österreich")


def bench_saetze(n: int) -> list[str]:
    """``n`` kurze, synthetische deutsche Sätze (deterministisch, keine echten Daten)."""
    vorlagen = [f"{s} {v} {o} {ort}." for s, v, o, ort in product(_SUBJEKTE, _VERBEN, _OBJEKTE, _ORTE)]
    runde = len(vorlagen)  # 1200 verschiedene Sätze, danach mit Rundennummer
    return [vorlagen[i % runde] + (f" Runde {i // runde}" if i >= runde else "") for i in range(n)]


def bench_langer_text(max_token: int) -> str:
    """Ein synthetischer Text deutlich über ``max_token`` Token (deterministisch, keine echten Daten).

    ``max_token // 2`` Sätze zu je mindestens 7 Wörtern, also über 3,5 Wörter je erlaubtem Token; der
    Tokenizer macht aus einem deutschen Wort mindestens ein Token.
    """
    return " ".join(bench_saetze(max(1, max_token // 2)))


def _chip() -> str:
    if sys.platform == "darwin":
        try:
            return subprocess.run(
                ["sysctl", "-n", "machdep.cpu.brand_string"],
                capture_output=True,
                text=True,
                timeout=5,
                check=True,
            ).stdout.strip()
        except (OSError, subprocess.SubprocessError):
            pass
    return platform.processor() or platform.machine()


def _repo_wurzel() -> Path:
    wurzel = Path.cwd().resolve()
    for ordner in (wurzel, *wurzel.parents):
        if (ordner / ".git").exists():
            return ordner
    return wurzel


def _rss_mb(ru_maxrss: int, betriebssystem: str) -> float:
    """``ru_maxrss`` in MiB: macOS zählt in Bytes, Linux in KiB."""
    return ru_maxrss / 2**20 if betriebssystem == "darwin" else ru_maxrss / 2**10


def _spitzenspeicher(geraet: str) -> str:
    if geraet == "mps":
        # torch bietet für mps keine Spitze an: das ist die Belegung des Treibers nach dem Lauf
        belegt = _bibliothek("torch").mps.driver_allocated_memory() / 2**20
        return f"{belegt:.0f} MiB (mps-Treiber nach dem Lauf)"
    if geraet == "cuda":
        return f"{_bibliothek('torch').cuda.max_memory_allocated() / 2**20:.0f} MiB (cuda-Spitze)"
    resource = importlib.import_module("resource")  # nur Unix; der Bench läuft auf macOS und Linux
    return f"{_rss_mb(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss, sys.platform):.0f} MiB (RSS-Spitze)"


def _messen(n: int, geraet: str | None) -> list[dict[str, str]]:
    """Zwei Zeilen je Gerät: ``n`` kurze Sätze und ein langer Text über ``EMBEDDINGS_MAX_TOKEN`` Token."""
    vorher = os.environ.get("EMBEDDINGS_GERAET")
    if geraet:
        os.environ["EMBEDDINGS_GERAET"] = geraet
    try:
        return _messen_mit_geraet(n)
    finally:
        # der Bench ändert die Umgebung des Prozesses nicht dauerhaft
        if vorher is None:
            os.environ.pop("EMBEDDINGS_GERAET", None)
        else:
            os.environ["EMBEDDINGS_GERAET"] = vorher


def _messen_mit_geraet(n: int) -> list[dict[str, str]]:
    entladen()
    for name in ("torch", "sentence_transformers", _PROZESSOR_MODUL):  # Importzeit nicht mitmessen
        _bibliothek(name)
    einstellung = _einstellung()
    if einstellung.geraet == "cuda":
        _bibliothek("torch").cuda.reset_peak_memory_stats()
    geladen = _laden(einstellung)
    gemeinsam = {
        "modell": geladen.name,
        "revision": geladen.revision[:12],
        "geraet": geladen.geraet,
        "stapel": str(einstellung.stapel),
        "max_token": str(einstellung.max_token),
        "ladezeit": f"{geladen.ladezeit_ms / 1000:.1f} s",
    }
    saetze = bench_saetze(n)
    einbetten(saetze[:8], zweck="embeddings.bench")  # Aufwärmen (Kernel, Speicher)
    start = time.perf_counter()
    vektoren = einbetten(saetze, zweck="embeddings.bench")
    dauer = time.perf_counter() - start
    if len(vektoren) != n or {len(v) for v in vektoren} != {dimension()}:
        raise RuntimeError("bench: Anzahl oder Länge der Vektoren stimmt nicht")
    kurz = {
        **gemeinsam,
        "eingabe": "kurze Sätze",
        "dimension": str(len(vektoren[0])),
        "n": str(n),
        "dauer": f"{dauer:.2f} s",
        "durchsatz": f"{n / dauer:.0f}",
        "speicher": _spitzenspeicher(geladen.geraet),
    }
    lang = bench_langer_text(einstellung.max_token)
    start = time.perf_counter()
    (vektor,) = einbetten([lang], zweck="embeddings.bench")
    dauer = time.perf_counter() - start
    lang_zeile = {
        **gemeinsam,
        "eingabe": f"langer Text ({len(lang.split())} Wörter, abgeschnitten)",
        "dimension": str(len(vektor)),
        "n": "1",
        "dauer": f"{dauer:.2f} s",
        "durchsatz": f"{1 / dauer:.1f}",
        "speicher": _spitzenspeicher(geladen.geraet),
    }
    return [kurz, lang_zeile]


def _in_abschnitt(datei: Path, block: str) -> None:
    """Hängt ``block`` ans Ende des Abschnitts „Embeddings“ (legt ihn an, falls er fehlt)."""
    text = datei.read_text(encoding="utf-8") if datei.is_file() else ""
    if ABSCHNITT + "\n" not in text:
        text = text.rstrip("\n") + f"\n\n{ABSCHNITT}\n"
    anfang = text.index(ABSCHNITT + "\n") + len(ABSCHNITT)
    naechster = text.find("\n## ", anfang)
    ende = len(text) if naechster == -1 else naechster + 1
    rest = text[ende:]
    neu = text[:ende].rstrip("\n") + "\n\n" + block.strip("\n") + "\n" + ("\n" + rest if rest else "")
    datei.parent.mkdir(parents=True, exist_ok=True)
    datei.write_text(neu, encoding="utf-8")


def _bench(n: int, geraete: list[str | None], host: str, datei: Path) -> int:
    zeit = datetime.now(ZoneInfo("Europe/Vienna")).isoformat(timespec="seconds")
    zeilen = [z for g in geraete for z in _messen(n, g)]
    kopf = (
        "| Zeit | Host | Modell | Revision | Gerät | Eingabe | Stapel | Max. Token | Ladezeit | Dimension"
        " | n | Dauer | Texte/s | Speicher |\n"
        "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|\n"
    )
    tabelle = "".join(
        f"| {zeit} | {host} | {z['modell']} | `{z['revision']}` | {z['geraet']} | {z['eingabe']}"
        f" | {z['stapel']} | {z['max_token']} | {z['ladezeit']} | {z['dimension']} | {z['n']}"
        f" | {z['dauer']} | {z['durchsatz']} | {z['speicher']} |\n"
        for z in zeilen
    )
    print(kopf + tabelle, end="")
    _in_abschnitt(datei, f"#### Bench {zeit}\n\n" + kopf + tabelle)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m plattform.embeddings", description="Lokale Embeddings")
    befehle = parser.add_subparsers(dest="befehl", required=True)
    befehle.add_parser(
        "laden", help=f"Revision aus Hugging Face in den lokalen Cache holen (rund 1,5 GB; {_BEDINGUNGEN})"
    )
    bench = befehle.add_parser("bench", help="Ladezeit, Durchsatz, Speicher messen (nach docs/models.md)")
    bench.add_argument("--n", type=int, default=200, help="Anzahl synthetischer Sätze")
    bench.add_argument(
        "--geraet", nargs="+", default=None, help="z. B. cpu mps (Standard: EMBEDDINGS_GERAET)"
    )
    bench.add_argument("--stapel", type=int, default=None, help="überschreibt EMBEDDINGS_STAPEL für den Lauf")
    bench.add_argument("--host", default=None, help="Bezeichnung des Rechners (Standard: Chip)")
    bench.add_argument("--datei", type=Path, default=None)
    args = parser.parse_args(argv)
    if args.befehl == "laden":
        print(f"{modellname()}: Snapshot {laden()} im Hugging-Face-Cache ({_BEDINGUNGEN})")
        return 0
    if args.n < 1:
        parser.error("--n muss mindestens 1 sein")
    if args.stapel is not None:
        if not 1 <= args.stapel <= STAPEL_MAX:
            parser.error(f"--stapel muss zwischen 1 und {STAPEL_MAX} liegen")
        os.environ["EMBEDDINGS_STAPEL"] = str(args.stapel)
    geraete: list[str | None] = list(args.geraet) if args.geraet else [None]
    return _bench(args.n, geraete, args.host or _chip(), args.datei or _repo_wurzel() / "docs" / "models.md")


if __name__ == "__main__":
    sys.exit(main())
