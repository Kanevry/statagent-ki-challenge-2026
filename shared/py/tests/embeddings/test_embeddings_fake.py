"""plattform.embeddings mit Fake-Modell: Speicher-, Download- und Modellregeln ohne sentence-transformers.

Laufen auch in CI. ``_bibliothek`` liefert gefälschte Module (sentence_transformers, huggingface_hub, torch),
``_lade_nur_text`` ein Fake-Modell; kein torch, kein Netz, kein Modell-Download.
"""

import json
import os
from pathlib import Path
from types import SimpleNamespace

import pytest
from plattform import embeddings


class _Matrix(list):
    """Steht für das numpy-Array, das ``encode`` liefert."""

    def tolist(self):
        return [list(zeile) for zeile in self]


class _FakeModell:
    def __init__(self, geraet: str):
        self.device = SimpleNamespace(type=geraet)
        self.max_seq_length = embeddings.KONTEXT
        self.aufrufe: list[dict] = []

    def encode(self, texte, **optionen):
        self.aufrufe.append({"anzahl": len(texte), **optionen})
        # unnormiert und eindeutig je Text: [Nummer, 2.0]
        return _Matrix([float(t), 2.0] for t in texte)

    def get_embedding_dimension(self):
        return 2


class _NichtImCache(Exception):
    pass


@pytest.fixture
def umgebung(tmp_path, monkeypatch):
    """Gefälschte Bibliotheken, leere Embeddings-Umgebung, frisches Protokoll; liefert die Mitschrift."""
    for name in (
        "EMBEDDINGS_MODELL",
        "EMBEDDINGS_REVISION",
        "EMBEDDINGS_GERAET",
        "EMBEDDINGS_STAPEL",
        "EMBEDDINGS_MAX_TOKEN",
        "EMBEDDINGS_DOWNLOAD",
        "PYTORCH_MPS_HIGH_WATERMARK_RATIO",
    ):
        monkeypatch.delenv(name, raising=False)
    protokoll = tmp_path / "modellaufrufe.jsonl"
    monkeypatch.setenv("PLATTFORM_PROTOKOLL", str(protokoll))
    monkeypatch.setattr(embeddings, "_GELADEN", None)

    mit = SimpleNamespace(
        protokoll=protokoll, downloads=[], geladen=[], modelle=[], geleert=[], im_cache=True
    )
    snapshot = tmp_path / "hub" / "snapshots" / embeddings.REVISION_STANDARD

    def snapshot_download(name, revision, local_files_only=False):
        mit.downloads.append({"name": name, "revision": revision, "local_files_only": local_files_only})
        if local_files_only and not mit.im_cache:
            raise _NichtImCache(name)
        return str(snapshot)

    module = {
        "sentence_transformers": SimpleNamespace(),
        "huggingface_hub": SimpleNamespace(snapshot_download=snapshot_download),
        "huggingface_hub.errors": SimpleNamespace(LocalEntryNotFoundError=_NichtImCache),
        "torch": SimpleNamespace(
            mps=SimpleNamespace(empty_cache=lambda: mit.geleert.append("mps")),
            cuda=SimpleNamespace(empty_cache=lambda: mit.geleert.append("cuda")),
        ),
    }

    def bibliothek(name):
        if name not in module:
            raise embeddings.EmbeddingsFehlen(f"{name} im Test nicht gefälscht")
        return module[name]

    def lade_nur_text(pfad: Path, geraet: str):
        mit.geladen.append({"pfad": pfad, "geraet": geraet})
        modell = _FakeModell(geraet)
        mit.modelle.append(modell)
        return modell

    monkeypatch.setattr(embeddings, "_bibliothek", bibliothek)
    monkeypatch.setattr(embeddings, "_lade_nur_text", lade_nur_text)
    return mit


def test_scheiben_behalten_reihenfolge_und_eine_protokollzeile(umgebung):
    """Fängt: Scheiben-Logik verliert oder vertauscht Texte, schreibt eine Protokollzeile je Scheibe."""
    texte = [str(i) for i in range(600)]

    vektoren = embeddings.einbetten(texte, zweck="test.scheiben")

    assert [v[0] for v in vektoren] == [float(i) for i in range(600)]
    assert [a["anzahl"] for a in umgebung.modelle[0].aufrufe] == [256, 256, 88]
    zeilen = umgebung.protokoll.read_text(encoding="utf-8").splitlines()
    assert len(zeilen) == 1
    assert json.loads(zeilen[0])["anzahl_texte"] == 600


def test_normierung_wird_erzwungen(umgebung):
    """Fängt: Normierung bleibt der Modellkonfig überlassen (unnormiert, Cosinus ≠ Skalarprodukt)."""
    embeddings.einbetten(["1", "2"], zweck="test")

    assert all(a["normalize_embeddings"] is True for a in umgebung.modelle[0].aufrufe)


def test_standard_cpu_stapel_16_max_token_2048(umgebung):
    """Fängt: ohne Umgebung still mps, Stapel 64 oder 8192 Token je Text (Speicherdruck im Prototyp)."""
    embeddings.einbetten(["1"], zweck="test")

    assert umgebung.geladen[0]["geraet"] == "cpu"
    assert umgebung.modelle[0].aufrufe[0]["batch_size"] == 16
    assert umgebung.modelle[0].max_seq_length == 2048


def test_stapel_und_max_token_aus_der_umgebung(umgebung, monkeypatch):
    """Fängt: ``EMBEDDINGS_STAPEL`` oder ``EMBEDDINGS_MAX_TOKEN`` werden gelesen, aber nicht angewandt."""
    monkeypatch.setenv("EMBEDDINGS_STAPEL", "4")
    monkeypatch.setenv("EMBEDDINGS_MAX_TOKEN", "512")

    embeddings.einbetten(["1"], zweck="test")

    assert umgebung.modelle[0].aufrufe[0]["batch_size"] == 4
    assert umgebung.modelle[0].max_seq_length == 512


@pytest.mark.parametrize(
    ("variable", "wert"),
    [
        ("EMBEDDINGS_STAPEL", "0"),
        ("EMBEDDINGS_STAPEL", "257"),
        ("EMBEDDINGS_STAPEL", "viel"),
        ("EMBEDDINGS_MAX_TOKEN", "8193"),
    ],
)
def test_stapel_und_max_token_ausserhalb_der_grenzen_abgelehnt(umgebung, monkeypatch, variable, wert):
    """Fängt: zu große oder unsinnige Werte gehen still ins Modell (Speicher) statt eines klaren Fehlers."""
    monkeypatch.setenv(variable, wert)

    with pytest.raises(ValueError, match=variable):
        embeddings.einbetten(["1"], zweck="test")
    assert umgebung.geladen == []


@pytest.mark.parametrize(
    ("geraet", "grenze", "meldung"),
    [
        ("mps", None, "PYTORCH_MPS_HIGH_WATERMARK_RATIO"),
        ("mps", "0.0", "PYTORCH_MPS_HIGH_WATERMARK_RATIO"),
        ("gpu", None, "unbekannt"),
    ],
)
def test_mps_ohne_grenze_und_unbekanntes_geraet_starten_nicht(umgebung, monkeypatch, geraet, grenze, meldung):
    """Fängt: mps startet still ohne Speichergrenze, ein Tippfehler im Gerät wird durchgereicht."""
    monkeypatch.setenv("EMBEDDINGS_GERAET", geraet)
    if grenze is not None:
        monkeypatch.setenv("PYTORCH_MPS_HIGH_WATERMARK_RATIO", grenze)

    with pytest.raises(ValueError, match=meldung):
        embeddings.einbetten(["1"], zweck="test")
    assert umgebung.geladen == []


def test_mps_untergrenze_folgt_der_oberen(umgebung, monkeypatch):
    """Fängt: torch bricht mit „invalid low watermark ratio 1.4“ ab, wenn nur die obere Grenze gesetzt ist."""
    monkeypatch.setenv("EMBEDDINGS_GERAET", "mps")
    monkeypatch.setenv("PYTORCH_MPS_HIGH_WATERMARK_RATIO", "0.7")
    monkeypatch.delenv("PYTORCH_MPS_LOW_WATERMARK_RATIO", raising=False)
    embeddings.einbetten(["1"], zweck="test")
    assert os.environ["PYTORCH_MPS_LOW_WATERMARK_RATIO"] == "0.7"

    monkeypatch.setenv("PYTORCH_MPS_LOW_WATERMARK_RATIO", "0.9")
    with pytest.raises(ValueError, match="LOW_WATERMARK"):
        embeddings.einbetten(["1"], zweck="test")


def test_nur_gemessene_revision(umgebung, monkeypatch):
    """Fängt: EMBEDDINGS_REVISION=main lädt still einen ungemessenen Stand mit anderen Vektoren."""
    monkeypatch.setenv("EMBEDDINGS_REVISION", "main")
    with pytest.raises(ValueError, match="nicht gemessen"):
        embeddings.einbetten(["1"], zweck="test")
    assert umgebung.geladen == []


def test_wechsel_gibt_das_alte_modell_vorher_frei(umgebung, monkeypatch):
    """Fängt: beim Wechsel (hier max_token) liegen kurz zwei Modelle im Speicher."""
    monkeypatch.setenv("EMBEDDINGS_GERAET", "mps")
    monkeypatch.setenv("PYTORCH_MPS_HIGH_WATERMARK_RATIO", "0.7")
    monkeypatch.delenv("PYTORCH_MPS_LOW_WATERMARK_RATIO", raising=False)
    embeddings.einbetten(["1"], zweck="test")
    monkeypatch.setenv("EMBEDDINGS_MAX_TOKEN", "512")
    embeddings.einbetten(["2"], zweck="test")
    # Scheibe 1, Freigabe des alten Modells, Scheibe 2
    assert umgebung.geleert == ["mps", "mps", "mps"]


def test_geraete_cache_wird_je_scheibe_geleert(umgebung, monkeypatch):
    """Fängt: der Zwischenspeicher von mps/cuda wächst über alle Scheiben eines großen Aufrufs."""
    monkeypatch.setenv("EMBEDDINGS_GERAET", "mps")
    monkeypatch.setenv("PYTORCH_MPS_HIGH_WATERMARK_RATIO", "0.7")

    embeddings.einbetten([str(i) for i in range(300)], zweck="test")

    assert umgebung.geleert == ["mps", "mps"]


def test_kein_download_ohne_freigabe(umgebung):
    """Fängt: fehlt die Revision im Cache, lädt der erste Aufruf still rund 1,5 GB aus dem Netz."""
    umgebung.im_cache = False

    with pytest.raises(embeddings.ModellFehlt, match="plattform.embeddings laden"):
        embeddings.einbetten(["1"], zweck="test")
    assert [d["local_files_only"] for d in umgebung.downloads] == [True]
    assert umgebung.geladen == []


def test_laden_holt_die_revision_und_nennt_nur_den_ordner(umgebung, capsys):
    """Fängt: ``laden`` fragt nur den Cache (lädt nie) oder schreibt den vollen Pfad samt Home ins Log."""
    umgebung.im_cache = False

    assert embeddings.main(["laden"]) == 0

    assert umgebung.downloads == [
        {
            "name": embeddings.MODELL_STANDARD,
            "revision": embeddings.REVISION_STANDARD,
            "local_files_only": False,
        }
    ]
    ausgabe = capsys.readouterr().out
    assert embeddings.REVISION_STANDARD in ausgabe
    assert "snapshots" not in ausgabe
    assert umgebung.geladen == []


def test_fremdes_modell_abgelehnt(umgebung, monkeypatch):
    """Fängt: ein anderes Modell über ``EMBEDDINGS_MODELL`` wird geladen (fremde Vektoren in den Tabellen)."""
    monkeypatch.setenv("EMBEDDINGS_MODELL", "sentence-transformers/all-MiniLM-L6-v2")

    with pytest.raises(ValueError, match="#67"):
        embeddings.einbetten(["1"], zweck="test")
    assert umgebung.downloads == []


def test_entladen_gibt_das_modell_frei(umgebung, monkeypatch):
    """Fängt: das Modell bleibt nach ``entladen`` im Prozess und auf dem Gerät belegt."""
    monkeypatch.setenv("EMBEDDINGS_GERAET", "cuda")
    embeddings.einbetten(["1"], zweck="test")
    umgebung.geleert.clear()

    embeddings.entladen()

    assert embeddings._GELADEN is None
    assert umgebung.geleert == ["cuda"]
    embeddings.einbetten(["1"], zweck="test")
    assert len(umgebung.geladen) == 2


@pytest.mark.parametrize(("roh", "betriebssystem"), [(512 * 2**20, "darwin"), (512 * 2**10, "linux")])
def test_spitzenspeicher_in_mib_je_betriebssystem(roh, betriebssystem):
    """Fängt: ``ru_maxrss`` auf macOS (Bytes) wie Linux (KiB) gelesen, Bench zeigt 1024-fach falsch."""
    assert embeddings._rss_mb(roh, betriebssystem) == 512


def test_langer_bench_text_deutlich_ueber_max_token():
    """Fängt: der lange Bench-Text bleibt unter der Grenze und misst das Abschneiden nicht."""
    text = embeddings.bench_langer_text(2048)

    assert len(text.split()) > 3 * 2048
    assert text == embeddings.bench_langer_text(2048)
