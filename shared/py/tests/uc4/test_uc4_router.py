"""Router UC4 (#97): Reihenfolge, Kontext, eigenes Schrittprotokoll, fehlende Adapter, R2."""

import ast
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


def _importiert_llm_oder_router(datei: Path) -> bool:
    """Echte Import-Anweisungen (auch in Funktionen), nicht Erwähnungen in Docstrings oder Kommentaren."""
    for knoten in ast.walk(ast.parse(datei.read_text("utf-8"))):
        if isinstance(knoten, ast.Import):
            namen = [alias.name for alias in knoten.names]
        elif isinstance(knoten, ast.ImportFrom):
            modul = knoten.module or ""
            namen = [modul, *(f"{modul}.{alias.name}" for alias in knoten.names)]
        else:
            continue
        if any(re.fullmatch(r"plattform\.(llm|router)(\..*)?", name) for name in namen):
            return True
    return False


def test_r2_uc3_lauf_importiert_weder_router_noch_llm():
    """R2: ``uc3 lauf`` und der UC3-Adapter ``uc3/statagent/uc4.py`` laufen ohne Sprachmodell, auch nicht über
    den Router. ``OHNE_MODELL`` im Router baut darauf (Online-Stufe A ohne Budget, Review !94)."""
    uc3 = WURZEL / "uc3"
    dateien = sorted([*uc3.rglob("lauf*.py"), *uc3.rglob("statagent/uc4.py")]) if uc3.is_dir() else []
    if not dateien:
        pytest.skip("uc3/**/lauf*.py liegt in diesem Stand nicht vor")
    assert any(d.name == "uc4.py" for d in dateien), "UC3-Adapter fehlt in der Prüfung"
    treffer = [str(d.relative_to(WURZEL)) for d in dateien if _importiert_llm_oder_router(d)]
    assert treffer == []


def test_r2_pruefung_erkennt_import_aber_nicht_docstring(tmp_path):
    datei = tmp_path / "x.py"
    datei.write_text('"""Importiert ``plattform.llm`` nicht."""\n', encoding="utf-8")
    assert not _importiert_llm_oder_router(datei)
    datei.write_text("def f():\n    from plattform import llm\n", encoding="utf-8")
    assert _importiert_llm_oder_router(datei)
    datei.write_text("import plattform.router as r\n", encoding="utf-8")
    assert _importiert_llm_oder_router(datei)


# --- --kette (Online-Demo Stufe A: nur UC3, ohne Modell) ----------------------------------------------------


def test_cli_kette_uc3_fragt_nur_uc3(protokoll, capsys):
    """Fängt: `--kette uc3` lässt UC2 und UC1 trotzdem laufen (online kämen Mock-Texte)."""
    assert main(["frage", "--json", "--mock", "--kette", "uc3", "--", "Wie viele?"]) == 0
    ausgabe = json.loads(capsys.readouterr().out)
    assert [a["uc"] for a in ausgabe["antworten"]] == ["uc3"]
    assert ausgabe["fehlend"] == []


def test_cli_kette_haelt_die_standardreihenfolge(protokoll, capsys):
    assert main(["frage", "--json", "--mock", "--kette", "uc1,uc3", "--", "Wie viele?"]) == 0
    assert [a["uc"] for a in json.loads(capsys.readouterr().out)["antworten"]] == ["uc3", "uc1"]


@pytest.mark.parametrize("kette", ["", "uc4", "uc3,uc3", "uc3,x"])
def test_cli_ungueltige_kette_bricht_ab(protokoll, kette):
    with pytest.raises(SystemExit) as abbruch:
        main(["frage", "--json", "--mock", "--kette", kette, "--", "Wie viele?"])
    assert abbruch.value.code == 2


def test_cli_kette_nur_uc3_braucht_kein_budget(protokoll, monkeypatch, capsys):
    """Fängt: Stufe A online (kein Modell) sperrt, sobald das Tagesbudget aus Stufe B verbraucht ist."""
    monkeypatch.setenv("LLM_PROVIDER", "mock")
    monkeypatch.setenv("LLM_TAGESBUDGET_AUFRUFE", "1")
    complete([{"role": "user", "content": "x"}], zweck="smoke")
    uc3 = {"text": "7.498", "belege": [], "zahlen": [], "uc": "uc3"}
    monkeypatch.setattr(router, "_REGISTRY", {"uc3": lambda f, k: uc3})

    assert main(["frage", "--json", "--kette", "uc3", "--", "Wie viele?"]) == 0
    assert [a["uc"] for a in json.loads(capsys.readouterr().out)["antworten"]] == ["uc3"]
    assert main(["frage", "--json", "--", "Wie viele?"]) == 3


# --- --strom (Seite /uc4 zeigt die Stationen nacheinander, ui-regie-32) -------------------------------------


def _ereignisse(capsys) -> list[dict]:
    return [json.loads(z) for z in capsys.readouterr().out.splitlines()]


def test_strom_meldet_start_stationen_antworten_und_ende_in_reihenfolge(protokoll, capsys, monkeypatch):
    """Fängt: Strom erst am Ende, fehlende Station vor der Antwort, Ereignisse ohne Stufe oder Kern."""
    monkeypatch.setattr(router, "MOCK_PAUSE_S", 0.0)
    assert main(["frage", "--strom", "--mock", "--", "Wie viele?"]) == 0
    ereignisse = _ereignisse(capsys)
    assert [(e["art"], e.get("uc")) for e in ereignisse] == [
        ("start", None),
        ("station", "uc3"),
        ("antwort", "uc3"),
        ("station", "uc2"),
        ("antwort", "uc2"),
        ("station", "uc1"),
        ("antwort", "uc1"),
        ("ende", None),
    ]
    assert ereignisse[0]["kette"] == ["uc3", "uc2", "uc1"]
    uc3 = ereignisse[2]
    assert uc3["stufe"] == 1 and uc3["antwort"]["zahlen"][0]["wert"] == 412345
    assert uc3["kern"] == "Im März 2025 waren 412.345 Personen unselbständig beschäftigt (Mock)."
    assert ereignisse[-1]["fehlend"] == []


def test_strom_meldet_fehlende_station_mit_grund(protokoll):
    ereignisse: list[dict] = []
    uc3 = {"text": "7.498 Beschäftigte.", "belege": [], "zahlen": [], "uc": "uc3"}
    durchreichen(
        "Wie viele?", kette=("uc3", "uc2"), adapter={"uc3": lambda f, k: uc3}, melden=ereignisse.append
    )
    assert ereignisse[-2] == {"art": "fehlt", "uc": "uc2", "stufe": 2, "grund": "kein_adapter"}
    assert ereignisse[-1]["fehlend"] == [{"uc": "uc2", "grund": "kein_adapter"}]


def test_strom_mit_mock_wartet_je_station(protokoll, capsys, monkeypatch):
    pausen: list[float] = []
    monkeypatch.setattr(router.time, "sleep", pausen.append)
    assert main(["frage", "--strom", "--mock", "--", "x"]) == 0
    assert pausen == [router.MOCK_PAUSE_S] * 3


def test_strom_mit_erschoepftem_budget_meldet_fehler_als_eine_zeile(protokoll, monkeypatch, capsys):
    monkeypatch.setenv("LLM_PROVIDER", "mock")
    monkeypatch.setenv("LLM_TAGESBUDGET_AUFRUFE", "1")
    complete([{"role": "user", "content": "x"}], zweck="smoke")
    assert main(["frage", "--strom", "--", "Wie viele?"]) == 3
    assert _ereignisse(capsys) == [
        {
            "art": "fehler",
            "fehler": "budget_erschoepft",
            "meldung": "Das Tageskontingent für Modellaufrufe ist aufgebraucht.",
        }
    ]


@pytest.mark.parametrize(
    ("text", "kern"),
    [
        (
            "Am 31.03.2025 gab es 7.498 Verhältnisse; vorläufig. Zweiter Satz.",
            "Am 31.03.2025 gab es 7.498 Verhältnisse; vorläufig.",
        ),
        ("Erste Zeile ohne Punkt\nZweite Zeile.", "Erste Zeile ohne Punkt"),
        ("wort " * 40, ("wort " * 27).strip() + "…"),
    ],
)
def test_kern_ist_der_erste_satz_hoechstens_140_zeichen(text, kern):
    assert router.kern_satz(text) == kern
    assert len(router.kern_satz(text)) <= router.KERN_ZEICHEN
