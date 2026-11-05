"""Router UC4 (#97): Reihenfolge, Kontext, eigenes Schrittprotokoll, fehlende Adapter, R2."""

import json
import re
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from plattform import router
from plattform.llm import complete, kern
from plattform.router import durchreichen, main, mock_adapter, registriere

WURZEL = Path(__file__).resolve().parents[4]
_LEER_UC2 = {"text": "x", "belege": [], "zahlen": [], "uc": "uc2"}


@pytest.fixture
def protokoll(tmp_path, monkeypatch):
    datei = tmp_path / "modellaufrufe.jsonl"
    monkeypatch.setenv("PLATTFORM_PROTOKOLL", str(datei))
    monkeypatch.delenv("PLATTFORM_ROUTER_PROTOKOLL", raising=False)
    monkeypatch.setattr(router, "_REGISTRY", {})
    return datei


def _schritte(protokoll: Path) -> list[dict]:
    zeilen = (protokoll.parent / "router.jsonl").read_text(encoding="utf-8").splitlines()
    return [json.loads(z) for z in zeilen]


def test_reihenfolge_und_uc2_sieht_uc3_zahl(protokoll):
    gesehen = {}
    adapter = mock_adapter()
    mock_uc2 = adapter["uc2"]

    def uc2(frage, kontext):
        gesehen["kontext"] = kontext
        return mock_uc2(frage, kontext)

    ergebnis = durchreichen("Wie viele Beschäftigte?", adapter={**adapter, "uc2": uc2})
    assert [a.uc for a in ergebnis.antworten] == ["uc3", "uc2", "uc1"]
    assert ergebnis.fehlend == []
    assert [a.uc for a in gesehen["kontext"]] == ["uc3"]
    assert ergebnis.antworten[1].zahlen[0].wert == ergebnis.antworten[0].zahlen[0].wert
    # UC1 reicht die Zahl samt Beleg durch; der Beleg nennt weiter den liefernden UC
    assert ergebnis.antworten[2].belege[0].uc == "uc3"


def test_schrittzeilen_in_eigener_datei_ohne_fragetext(protokoll):
    durchreichen("ping-7f3a", adapter=mock_adapter())
    schritte = _schritte(protokoll)
    assert [(s["uc"], s["stufe"]) for s in schritte] == [("uc3", 1), ("uc2", 2), ("uc1", 3)]
    assert [(s["anzahl_belege"], s["anzahl_zahlen"]) for s in schritte] == [(1, 1)] * 3
    assert all("protokoll_id" in s and s["fehler"] is None for s in schritte)
    assert (protokoll.parent / "router.jsonl").read_text(encoding="utf-8").count("ping-7f3a") == 0
    assert not protokoll.exists()  # modellaufrufe.jsonl trägt nur Modellaufrufe


def test_frage_aendert_den_modell_badge_nicht(protokoll):
    """Fängt: nach einer UC4-Frage zeigt der Badge „router · keins“ statt des zuletzt antwortenden Modells."""
    complete([{"role": "user", "content": "x"}], provider="mock", zweck="smoke")
    vorher = kern.letzter_erfolg()
    durchreichen("Wie viele Beschäftigte?", adapter=mock_adapter())
    assert kern.letzter_erfolg() == vorher

    zeile_embeddings = {"provider": "lokal", "modell": "google/embeddinggemma-2", "fehler": None}
    with protokoll.open("a", encoding="utf-8") as datei:  # Zeile wie aus plattform.embeddings
        datei.write(json.dumps(zeile_embeddings) + "\n")
    assert kern.letzter_erfolg() == vorher


@pytest.mark.parametrize(
    ("ersatz", "grund"),
    [
        (None, "kein_adapter"),
        (lambda frage, kontext: (_ for _ in ()).throw(RuntimeError("kaputt")), "RuntimeError"),
        (lambda frage, kontext: mock_adapter()["uc3"](frage, kontext), "ungueltige_antwort"),  # uc3 statt uc2
        (lambda frage, kontext: {**_LEER_UC2, "neu": 1}, "ungueltige_antwort"),
    ],
    ids=["fehlt", "wirft", "falsches-uc", "dict-ungueltig"],
)
def test_fehlender_oder_kaputter_adapter_steht_mit_grund_in_fehlend(protokoll, ersatz, grund):
    adapter = mock_adapter()
    if ersatz is None:
        del adapter["uc2"]
    else:
        adapter["uc2"] = ersatz
    ergebnis = durchreichen("Wie viele Beschäftigte?", adapter=adapter)
    assert [(f.uc, f.grund) for f in ergebnis.fehlend] == [("uc2", grund)]
    assert [a.uc for a in ergebnis.antworten] == ["uc3", "uc1"]
    assert _schritte(protokoll)[1]["fehler"] == grund


def test_adapter_darf_ein_dict_liefern(protokoll):
    adapter = mock_adapter()
    adapter["uc2"] = lambda frage, kontext: {**_LEER_UC2, "text": "ok"}
    ergebnis = durchreichen("Wie viele Beschäftigte?", adapter=adapter)
    assert ergebnis.fehlend == [] and ergebnis.antworten[1].text == "ok"


def test_kontext_ist_eine_tiefe_kopie(protokoll):
    """Fängt: ein Adapter ändert eine frühere Zahl im Kontext, das Ergebnis zeigt die geänderte Zahl."""
    adapter = mock_adapter()
    mock_uc2 = adapter["uc2"]

    def uc2(frage, kontext):
        kontext[0].zahlen[0].wert = -1
        kontext[0].belege.clear()
        return mock_uc2(frage, kontext)

    ergebnis = durchreichen("Wie viele Beschäftigte?", adapter={**adapter, "uc2": uc2})
    assert ergebnis.antworten[0].zahlen[0].wert == 412345
    assert len(ergebnis.antworten[0].belege) == 1


def test_registry_ohne_explizite_adapter(protokoll):
    registriere("uc3", mock_adapter()["uc3"])
    ergebnis = durchreichen("Wie viele Beschäftigte?", kette=("uc3",))
    assert [a.uc for a in ergebnis.antworten] == ["uc3"]


def test_entry_point_wird_ohne_registry_geladen(protokoll, monkeypatch):
    """Fängt: Gruppe oder Name falsch abgefragt, Adapter aus installierten UC-Paketen werden nie gefunden."""
    gefragt = []

    def entry_points(group, name):
        gefragt.append((group, name))
        return [SimpleNamespace(load=lambda: mock_adapter()["uc3"])] if name == "uc3" else []

    monkeypatch.setattr(router, "entry_points", entry_points)
    ergebnis = durchreichen("Wie viele Beschäftigte?", kette=("uc3", "uc2"))
    assert gefragt == [("kic.uc_antwort", "uc3"), ("kic.uc_antwort", "uc2")]
    assert [a.uc for a in ergebnis.antworten] == ["uc3"]
    assert [(f.uc, f.grund) for f in ergebnis.fehlend] == [("uc2", "kein_adapter")]


def test_cli_mock_liefert_json_mit_drei_antworten(protokoll, capsys):
    assert main(["frage", "--json", "--mock", "Wie viele Beschäftigte?"]) == 0
    ausgabe = json.loads(capsys.readouterr().out)
    assert [a["uc"] for a in ausgabe["antworten"]] == ["uc3", "uc2", "uc1"]
    assert ausgabe["fehlend"] == []


def test_cli_frage_nach_doppelstrich_ist_kein_schalter(protokoll, capsys):
    """Die Web-Route setzt `--` vor die Frage (#98): eine Frage wie „-h“ bleibt eine Frage."""
    assert main(["frage", "--json", "--mock", "--", "-h"]) == 0
    ausgabe = json.loads(capsys.readouterr().out)
    assert [a["uc"] for a in ausgabe["antworten"]] == ["uc3", "uc2", "uc1"]


def test_r2_antwortform_und_plattform_laden_weder_router_noch_llm():
    """R2: UC3-Adapter importieren plattform.antwortform; das darf plattform.llm nicht nachladen."""
    code = (
        "import sys, plattform, plattform.antwortform; "
        "print(sorted(m for m in ('plattform.router', 'plattform.llm') if m in sys.modules))"
    )
    lauf = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, timeout=60, check=True
    )
    assert lauf.stdout.strip() == "[]"


def test_r2_uc3_lauf_importiert_weder_router_noch_llm():
    """R2: der UC3-Lauf (``uc3 lauf``) läuft ohne Sprachmodell, auch nicht über den Router."""
    dateien = sorted((WURZEL / "uc3").rglob("lauf*.py")) if (WURZEL / "uc3").is_dir() else []
    if not dateien:
        pytest.skip("uc3/**/lauf*.py liegt in diesem Stand nicht vor")
    verboten = re.compile(r"plattform\.(llm|router)\b|from plattform import [^\n]*\b(llm|router)\b")
    treffer = [str(d.relative_to(WURZEL)) for d in dateien if verboten.search(d.read_text("utf-8"))]
    assert treffer == []
