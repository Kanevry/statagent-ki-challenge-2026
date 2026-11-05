"""Lokale Embeddings mit genau einem Modell für die ganze Plattform (#67).

``einbetten(texte, zweck)`` liefert je Text einen L2-normierten Vektor (Cosinus = Skalarprodukt),
``dimension()`` dessen Länge. Das Modell läuft nur lokal über sentence-transformers, nie über
``plattform.llm`` oder einen Cloud-Dienst. Es wird einmal je Prozess geladen, aus dem Hugging-Face-Cache
(``~/.cache/huggingface``, nie im Repo). Liegt die Revision dort, geht keine Anfrage ins Netz; mit
``HF_HUB_OFFLINE=1`` ist das erzwungen.

Je Aufruf schreibt ``plattform.protokoll.modellaufruf`` genau eine Zeile (provider ``lokal``, Modell,
Revision, Zweck, Hash, Dauer, Anzahl der Texte), nie einen Text.

sentence-transformers ist das Extra ``plattform[embeddings]`` und fehlt in CI. Dieses Modul importiert es
deshalb erst beim ersten Einbetten; ``import plattform.embeddings`` klappt immer.

Umgebung: ``EMBEDDINGS_MODELL`` (Standard ``google/embeddinggemma-2``), ``EMBEDDINGS_REVISION``
(Standard: die gemessene Revision des Standardmodells, sonst ``main``), ``EMBEDDINGS_GERAET``
(``mps``, ``cpu`` oder ``cuda``; Standard: Wahl von sentence-transformers).

CLI: ``uv run python -m plattform.embeddings bench --n 200`` misst Ladezeit, Dimension und Durchsatz und
trägt das Ergebnis in ``docs/models.md`` ein (Abschnitt „Embeddings“).
"""

from __future__ import annotations

import argparse
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
#: Kontextfenster laut Modellkarte (Token je Text); längere Texte werden abgeschnitten.
KONTEXT = 8192
#: Stapelgröße je Vorwärtslauf. Prototyp auf m5 (mps): 16 → ~60, 64 → ~115, 200 → ~157 Texte/s.
STAPEL = 64
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


@dataclass(frozen=True, slots=True)
class _Geladen:
    schluessel: tuple[str, str, str | None]
    modell: Any
    name: str
    revision: str
    geraet: str
    ladezeit_ms: int


_GELADEN: _Geladen | None = None
_SPERRE = threading.Lock()


def modellname() -> str:
    return os.environ.get("EMBEDDINGS_MODELL", "").strip() or MODELL_STANDARD


def _revision_wunsch(name: str) -> str:
    explizit = os.environ.get("EMBEDDINGS_REVISION", "").strip()
    if explizit:
        return explizit
    return REVISION_STANDARD if name == MODELL_STANDARD else "main"


def _geraet_wunsch() -> str | None:
    return os.environ.get("EMBEDDINGS_GERAET", "").strip() or None


def _bibliothek(name: str) -> ModuleType:
    """Import erst bei Bedarf; über ``importlib``, damit mypy in CI ohne das Extra gleich prüft wie lokal."""
    try:
        return importlib.import_module(name)
    except ImportError as fehler:
        raise EmbeddingsFehlen(f"{name} fehlt für plattform.embeddings: {_INSTALLIEREN}") from fehler


def _snapshot(name: str, revision: str) -> Path:
    """Ordner der Revision im HF-Cache: zuerst lokal, nur wenn dort nichts liegt aus dem Netz."""
    hub = _bibliothek("huggingface_hub")
    fehlt = _bibliothek("huggingface_hub.errors").LocalEntryNotFoundError
    try:
        return Path(hub.snapshot_download(name, revision=revision, local_files_only=True))
    except fehlt:
        return Path(hub.snapshot_download(name, revision=revision))


def _lade_nur_text(pfad: Path, geraet: str | None) -> Any:
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
    modell.max_seq_length = KONTEXT
    return modell


def _laden() -> _Geladen:
    """Modell einmal je Prozess; ein anderes Modell, eine andere Revision oder ein anderes Gerät lädt neu."""
    global _GELADEN
    name = modellname()
    schluessel = (name, _revision_wunsch(name), _geraet_wunsch())
    with _SPERRE:
        if _GELADEN is not None and _GELADEN.schluessel == schluessel:
            return _GELADEN
        _bibliothek("sentence_transformers")  # fehlt das Extra: abbrechen, bevor der Cache berührt wird
        start = time.perf_counter()
        pfad = _snapshot(name, schluessel[1])
        modell = _lade_nur_text(pfad, schluessel[2])
        _GELADEN = _Geladen(
            schluessel=schluessel,
            modell=modell,
            name=name,
            revision=pfad.name,  # Snapshot-Ordner im HF-Cache = Commit-Hash der Revision
            geraet=str(modell.device.type),
            ladezeit_ms=round((time.perf_counter() - start) * 1000),
        )
        return _GELADEN


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
    ins Modell. Eine leere Liste ruft kein Modell auf und schreibt keine Protokollzeile.
    """
    _pruefe(texte, zweck)
    if not texte:
        return []
    start = time.perf_counter()
    geladen: _Geladen | None = None
    fehler: str | None = None
    try:
        geladen = _laden()
        vektoren = geladen.modell.encode(
            texte,
            prompt_name=aufgabe,
            batch_size=STAPEL,
            show_progress_bar=False,
            convert_to_numpy=True,
        )
        return vektoren.tolist()  # numpy float32 → Python float
    except Exception as ausnahme:
        fehler = type(ausnahme).__name__
        raise
    finally:
        modellaufruf(
            Modellaufruf(
                provider="lokal",
                modell=geladen.name if geladen else modellname(),
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
    return int(_laden().modell.get_embedding_dimension())


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


def _vergessen() -> None:
    global _GELADEN
    with _SPERRE:
        _GELADEN = None


def _messen(n: int, geraet: str | None) -> dict[str, str]:
    if geraet:
        os.environ["EMBEDDINGS_GERAET"] = geraet
    _vergessen()
    for name in ("torch", "sentence_transformers", _PROZESSOR_MODUL):  # Importzeit nicht mitmessen
        _bibliothek(name)
    geladen = _laden()
    saetze = bench_saetze(n)
    einbetten(saetze[:8], zweck="embeddings.bench")  # Aufwärmen (Kernel, Speicher)
    start = time.perf_counter()
    vektoren = einbetten(saetze, zweck="embeddings.bench")
    dauer = time.perf_counter() - start
    if len(vektoren) != n or {len(v) for v in vektoren} != {dimension()}:
        raise RuntimeError("bench: Anzahl oder Länge der Vektoren stimmt nicht")
    return {
        "modell": geladen.name,
        "revision": geladen.revision[:12],
        "geraet": geladen.geraet,
        "ladezeit": f"{geladen.ladezeit_ms / 1000:.1f} s",
        "dimension": str(len(vektoren[0])),
        "n": str(n),
        "dauer": f"{dauer:.2f} s",
        "durchsatz": f"{n / dauer:.0f}",
    }


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
    zeilen = [_messen(n, g) for g in geraete]
    kopf = (
        "| Zeit | Host | Modell | Revision | Gerät | Ladezeit | Dimension | n | Dauer | Texte/s |\n"
        "|---|---|---|---|---|---|---|---|---|---|\n"
    )
    tabelle = "".join(
        f"| {zeit} | {host} | {z['modell']} | `{z['revision']}` | {z['geraet']} | {z['ladezeit']}"
        f" | {z['dimension']} | {z['n']} | {z['dauer']} | {z['durchsatz']} |\n"
        for z in zeilen
    )
    print(kopf + tabelle, end="")
    _in_abschnitt(datei, f"#### Bench {zeit}\n\n" + kopf + tabelle)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m plattform.embeddings", description="Lokale Embeddings")
    befehle = parser.add_subparsers(dest="befehl", required=True)
    bench = befehle.add_parser("bench", help="Ladezeit, Dimension, Durchsatz messen (nach docs/models.md)")
    bench.add_argument("--n", type=int, default=200, help="Anzahl synthetischer Sätze")
    bench.add_argument("--geraet", nargs="+", default=None, help="z. B. mps cpu (Standard: automatisch)")
    bench.add_argument("--host", default=None, help="Bezeichnung des Rechners (Standard: Chip)")
    bench.add_argument("--datei", type=Path, default=None)
    args = parser.parse_args(argv)
    if args.n < 1:
        parser.error("--n muss mindestens 1 sein")
    geraete: list[str | None] = list(args.geraet) if args.geraet else [_geraet_wunsch()]
    return _bench(args.n, geraete, args.host or _chip(), args.datei or _repo_wurzel() / "docs" / "models.md")


if __name__ == "__main__":
    sys.exit(main())
