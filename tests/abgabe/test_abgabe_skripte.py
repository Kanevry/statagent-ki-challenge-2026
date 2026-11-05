"""Prüfsätze für die Abgabe-Skripte (ohne Netz). Aufruf: uv run pytest -q tests/abgabe."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import quote, unquote, urlsplit

import pytest

WURZEL = Path(__file__).resolve().parents[2]


def _lade(name: str):
    spec = importlib.util.spec_from_file_location(name, WURZEL / "scripts" / "abgabe" / f"{name}.py")
    modul = importlib.util.module_from_spec(spec)
    sys.modules[name] = modul
    spec.loader.exec_module(modul)
    return modul


gp = _lade("github_push")
sv = _lade("svbox_upload")


@pytest.mark.parametrize(
    "pfad",
    [
        ".env",
        ".env.local",
        "web/.env.production",
        "deploy/schluessel.pem",
        "x/id_ed25519",
        "abgabe/ministerium_2026-07.csv",
        "svbox/uc3/daten.csv",
        "lieferungen/a.csv",
    ],
)
def test_verbotene_pfade_werden_erkannt(pfad: str) -> None:
    assert gp.verbotene_pfade([pfad]) == [pfad]


@pytest.mark.parametrize(
    "pfad", [".env.example", "deploy/env.server.example", "abgabe/ministerium_2026-07.beleg.md"]
)
def test_erlaubte_pfade_bleiben(pfad: str) -> None:
    assert gp.verbotene_pfade([pfad]) == []


def test_sperrmuster_nennt_nur_zeilen(tmp_path: Path) -> None:
    datei = tmp_path / "muster.txt"
    datei.write_text("# Kommentar\nrechner-[0-9]+\n", encoding="utf-8")
    muster = gp.lade_sperrmuster(datei)
    assert gp.treffer_in_text("a\nlauf auf rechner-7\nb", muster) == [2]


def test_push_erst_ab_grenze() -> None:
    vorher = gp.dt.datetime(2026, 11, 6, 8, 29, tzinfo=gp.WIEN)
    danach = gp.dt.datetime(2026, 11, 6, 8, 30, tzinfo=gp.WIEN)
    assert not gp.nicht_vor_erreicht(vorher, gp.NICHT_VOR)
    assert gp.nicht_vor_erreicht(danach, gp.NICHT_VOR)


def _manifest(tmp_path: Path) -> tuple[dict, Path]:
    abgabe = tmp_path / "abgabe"
    (abgabe / "berichte").mkdir(parents=True)
    (abgabe / "berichte" / "2024-08.md").write_text("Bericht\n", encoding="utf-8")
    (abgabe / ".gitignore").write_text("*.csv\n", encoding="utf-8")
    csv = tmp_path / "extern" / "ministerium_2026-07.csv"
    csv.parent.mkdir()
    csv.write_text("PERSON_ID\n1\n", encoding="utf-8")

    def eintrag(name: str, pfad: Path, ort: str = "repo") -> dict:
        roh = pfad.read_bytes()
        return {"datei": name, "ort": ort, "groesse": len(roh), "sha256": hashlib.sha256(roh).hexdigest()}

    manifest = {
        "stand": "test",
        "dateien": [
            eintrag(".gitignore", abgabe / ".gitignore"),
            eintrag("berichte/2024-08.md", abgabe / "berichte" / "2024-08.md"),
            eintrag("ministerium_2026-07.csv", csv, "extern (Einzeldaten)"),
        ],
    }
    return manifest, csv


def test_plan_nimmt_manifest_und_csv(tmp_path: Path) -> None:
    manifest, csv = _manifest(tmp_path)
    dateien, fehler = sv.plane(manifest, tmp_path / "abgabe", csv)
    assert fehler == []
    assert [d.name for d in dateien] == ["berichte/2024-08.md", "ministerium_2026-07.csv"]
    assert sv.ordner_von(dateien) == ["berichte"]


def test_plan_meldet_abweichung_und_fehlende_csv(tmp_path: Path) -> None:
    manifest, _ = _manifest(tmp_path)
    (tmp_path / "abgabe" / "berichte" / "2024-08.md").write_text("geändert\n", encoding="utf-8")
    dateien, fehler = sv.plane(manifest, tmp_path / "abgabe", None)
    assert dateien == []
    assert any("2024-08.md" in f for f in fehler)
    assert any("--csv" in f for f in fehler)


def test_propfind_antwort_wird_gelesen() -> None:
    xml = b"""<?xml version="1.0"?>
<d:multistatus xmlns:d="DAV:">
 <d:response><d:href>/public.php/webdav/</d:href><d:propstat><d:prop><d:resourcetype><d:collection/></d:resourcetype></d:prop></d:propstat></d:response>
 <d:response><d:href>/public.php/webdav/qualitaets%20berichte/</d:href><d:propstat><d:prop><d:resourcetype><d:collection/></d:resourcetype></d:prop></d:propstat></d:response>
 <d:response><d:href>/public.php/webdav/a.xlsx</d:href><d:propstat><d:prop><d:getcontentlength>42</d:getcontentlength><d:resourcetype/></d:prop></d:propstat></d:response>
</d:multistatus>"""
    assert sv.eintraege(xml, "/public.php/webdav/") == {"qualitaets berichte": None, "a.xlsx": 42}


def test_env_datei_liest_nur_zugang_und_gibt_nichts_aus(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    env = tmp_path / ".env.local"
    env.write_text(
        "ANDERES=x\nSVBOX_TEAM_URL='https://box.example.org/s/abc'\n"
        'export SVBOX_TEAM_TOKEN="t1"\nSVBOX_TEAM_PW=p=w\n',
        encoding="utf-8",
    )
    werte = sv.lade_env_datei(env)
    assert werte == {
        "SVBOX_TEAM_URL": "https://box.example.org/s/abc",
        "SVBOX_TEAM_TOKEN": "t1",
        "SVBOX_TEAM_PW": "p=w",
    }
    zugang = sv.Zugang(werte["SVBOX_TEAM_URL"], "t1", "geheim")
    assert zugang.basis == "https://box.example.org/public.php/webdav/"
    assert "geheim" not in repr(zugang) and "t1" not in repr(zugang)


def test_trockenlauf_ohne_netz(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    manifest, csv = _manifest(tmp_path)
    (tmp_path / "abgabe" / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    rc = sv.main(["--abgabe", str(tmp_path / "abgabe"), "--csv", str(csv), "--ohne-netz"])
    assert rc == 0
    assert "2 Dateien stimmen" in capsys.readouterr().out


def test_url_zugang_wird_verborgen() -> None:
    assert (
        gp.ohne_zugang("fatal: https://nutzer:geheim@github.com/x.git")
        == "fatal: https://<verborgen>@github.com/x.git"
    )


def test_ziel_url_mit_zugang_wird_abgelehnt(tmp_path: Path) -> None:
    muster = tmp_path / "m.txt"
    muster.write_text("rechner-1\n", encoding="utf-8")
    with pytest.raises(SystemExit, match="ohne Zugangsdaten"):
        gp.main(["--sperrmuster", str(muster), "--ziel-url", "https://x:geheim@github.com/a/b.git"])


class _Webdav(BaseHTTPRequestHandler):
    """Kleiner WebDAV-Server wie der Teamordner: Dateien im Speicher, Abweisung und Fehler einstellbar."""

    def log_message(self, *args) -> None:
        pass

    def _name(self) -> str:
        return unquote(urlsplit(self.path).path).removeprefix(_BASIS).strip("/")

    def _abweisen(self) -> bool:
        s = self.server
        s.anfragen += 1
        if s.abweisen_ab and s.anfragen >= s.abweisen_ab and s.abgewiesen < s.abweisungen:
            s.abgewiesen += 1
            self.connection.close()  # wie ein Host, der die Verbindung nicht annimmt
            self.close_connection = True
            return True
        code = s.fehler.get((self.command, self._name())) or s.fehler.get(self.command)
        if code:
            self.send_response(code)
            self.send_header("Content-Length", "0")
            self.end_headers()
            return True
        return False

    def _antwort(self, code: int, koerper: bytes = b"") -> None:
        self.send_response(code)
        self.send_header("Content-Length", str(len(koerper)))
        self.end_headers()
        self.wfile.write(koerper)

    def do_PROPFIND(self) -> None:
        laenge = int(self.headers.get("Content-Length") or 0)
        koerper = self.rfile.read(laenge)
        if self._abweisen():
            return
        name = self._name()
        if b"permissions" in koerper:
            self._antwort(
                207,
                b'<d:multistatus xmlns:d="DAV:" xmlns:oc="http://owncloud.org/ns"><d:response>'
                b"<d:href>/x</d:href><d:propstat><d:prop><oc:permissions>RGDNVCK</oc:permissions>"
                b"</d:prop></d:propstat></d:response></d:multistatus>",
            )
            return
        s = self.server
        kinder = [
            f"<d:response><d:href>{_BASIS}{quote(name + '/' if name else '')}</d:href><d:propstat><d:prop>"
            "<d:resourcetype><d:collection/></d:resourcetype></d:prop></d:propstat></d:response>"
        ]
        praefix = name + "/" if name else ""
        for o in s.ordner:
            if o.startswith(praefix) and "/" not in o[len(praefix) :] and o != name:
                kinder.append(
                    f"<d:response><d:href>{_BASIS}{quote(o)}/</d:href><d:propstat><d:prop>"
                    "<d:resourcetype><d:collection/></d:resourcetype></d:prop></d:propstat></d:response>"
                )
        for d, roh in s.dateien.items():
            if d.startswith(praefix) and "/" not in d[len(praefix) :]:
                kinder.append(
                    f"<d:response><d:href>{_BASIS}{quote(d)}</d:href><d:propstat><d:prop>"
                    f"<d:getcontentlength>{len(roh)}</d:getcontentlength><d:resourcetype/></d:prop>"
                    "</d:propstat></d:response>"
                )
        self._antwort(207, ('<d:multistatus xmlns:d="DAV:">' + "".join(kinder) + "</d:multistatus>").encode())

    def do_MKCOL(self) -> None:
        if self._abweisen():
            return
        name = self._name()
        if name in self.server.ordner:
            self._antwort(405)
        else:
            self.server.ordner.add(name)
            if self.server.mkcol_antwort_verlieren:
                self.server.mkcol_antwort_verlieren = False
                self.connection.close()
                self.close_connection = True
                return
            self._antwort(201)

    def do_PUT(self) -> None:
        roh = self.rfile.read(int(self.headers.get("Content-Length") or 0))
        if self._abweisen():
            return
        name = self._name()
        self.server.puts += 1
        if self.server.puts_bis_abbruch and self.server.puts > self.server.puts_bis_abbruch:
            self.send_response(500)
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        self.server.dateien[name] = roh[:-1] if name == self.server.verstuemmeln else roh
        if self.server.fremd_bei_put:
            self.server.dateien[self.server.fremd_bei_put] = b"fremd"
        self._antwort(201)

    def do_DELETE(self) -> None:
        if self._abweisen():
            return
        s, name = self.server, self._name()
        s.geloescht.append(name)
        if name in s.ordner:
            s.ordner.discard(name)
            for d in [d for d in s.dateien if d.startswith(name + "/")]:
                del s.dateien[d]
            self._antwort(204)
        elif s.dateien.pop(name, None) is not None:
            self._antwort(204)
        else:
            self._antwort(404)

    def do_GET(self) -> None:
        if self._abweisen():
            return
        if self.server.weiterleiten:
            self.send_response(302)
            self.send_header("Location", "http://127.0.0.1:9/fremd")
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        roh = self.server.dateien.get(self._name())
        self._antwort(404) if roh is None else self._antwort(200, roh)


_BASIS = "/public.php/webdav/"


@pytest.fixture
def box(monkeypatch: pytest.MonkeyPatch):
    server = ThreadingHTTPServer(("127.0.0.1", 0), _Webdav)
    server.dateien, server.ordner, server.fehler = {}, set(), {}
    server.anfragen = server.abgewiesen = server.abweisungen = server.abweisen_ab = 0
    server.puts = server.puts_bis_abbruch = 0
    server.verstuemmeln = None
    server.mkcol_antwort_verlieren = False
    server.geloescht = []
    server.fremd_bei_put = None
    server.weiterleiten = False
    server.schlaefe = []
    threading.Thread(target=server.serve_forever, daemon=True).start()
    echt = sv.Zugang

    def fabrik(url: str, token: str, passwort: str, pause: float = 0.0):
        zugang = echt(url, token, passwort, pause=0.0, geduld=server.geduld, schlaf=server.schlaefe.append)
        zugang.basis = f"http://127.0.0.1:{server.server_port}{_BASIS}"
        return zugang

    server.geduld = 900
    monkeypatch.setattr(sv, "Zugang", fabrik)
    monkeypatch.setenv("SVBOX_TEAM_URL", "https://box.example.org/index.php/s/geheim-token/")
    monkeypatch.setenv("SVBOX_TEAM_TOKEN", "geheim-token")
    monkeypatch.setenv("SVBOX_TEAM_PW", "geheim-passwort")
    yield server
    server.shutdown()


def _git(ordner: Path, *argumente: str) -> str:
    grund = ["git", "-C", str(ordner), "-c", "user.name=Test", "-c", "user.email=test@example.org"]
    grund += ["-c", "commit.gpgsign=false", "-c", "core.hooksPath=/dev/null"]
    return subprocess.run([*grund, *argumente], check=True, capture_output=True, text=True).stdout.strip()


def _hochladen(
    tmp_path: Path, nachweis: str = "nachweis.json", ausfuehren: bool = True, kopf: str | None = None
) -> tuple[int, Path]:
    ziel = tmp_path / nachweis
    if ausfuehren and kopf is None:
        kopf = _git(tmp_path, "rev-parse", "HEAD")
    argumente = [
        "--abgabe",
        str(tmp_path / "abgabe"),
        "--csv",
        str(tmp_path / "extern" / "ministerium_2026-07.csv"),
    ]
    argumente += ["--nachweis", str(ziel)] + (["--ausfuehren"] if ausfuehren else [])
    argumente += ["--erwarteter-kopf", kopf] if kopf else []
    return sv.main(argumente), ziel


def _paket(tmp_path: Path, berichte: int = 12) -> dict:
    manifest, _ = _manifest(tmp_path)
    for i in range(berichte):
        roh = f"Bericht {i}\n".encode()
        (tmp_path / "abgabe" / "berichte" / f"b{i}.md").write_bytes(roh)
        manifest["dateien"].append(
            {
                "datei": f"berichte/b{i}.md",
                "ort": "repo",
                "groesse": len(roh),
                "sha256": hashlib.sha256(roh).hexdigest(),
            }
        )
    (tmp_path / "abgabe" / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    _git(tmp_path, "init", "-q", "-b", "main")
    _git(tmp_path, "add", "abgabe")
    _git(tmp_path, "commit", "-q", "-m", "abgabe")
    return manifest


def test_upload_wartet_abweisung_ab_der_10_anfrage_ab(tmp_path: Path, box, capsys) -> None:
    """Fängt: Der Host weist ab der 10. Anfrage ab; das Skript bricht ab oder meldet Teilupload als Erfolg."""
    _paket(tmp_path)
    box.abweisen_ab, box.abweisungen = 10, 4

    rc, nachweis = _hochladen(tmp_path)

    assert rc == 0
    daten = json.loads(nachweis.read_text(encoding="utf-8"))
    assert daten["differenzen"] == 0 and daten["anzahl"] == 14 and daten["abweisungen"] == 4
    assert box.abgewiesen == 4 and len(box.dateien) == 14
    assert "geheim" not in nachweis.read_text(encoding="utf-8") + capsys.readouterr().out


@pytest.mark.parametrize("code", [401, 403, 404])
def test_harte_antwort_wird_nie_still_wiederholt(tmp_path: Path, box, code: int) -> None:
    """Fängt: 401, 403 oder 404 laufen in die Wiederholung, statt sofort abzubrechen."""
    _paket(tmp_path)
    box.fehler["PUT"] = code

    rc, nachweis = _hochladen(tmp_path)

    assert rc == 1
    assert box.schlaefe.count(sv.ERSTE_WARTEZEIT_S) == 0
    assert not nachweis.exists() and not box.dateien


def test_rueckgabe_404_beim_ruecklesen_ist_kein_erfolg(tmp_path: Path, box) -> None:
    """Fängt: Eine Datei fehlt beim Rücklesen, der Lauf endet trotzdem mit Exit 0."""
    _paket(tmp_path)
    box.fehler[("GET", "berichte/b3.md")] = 404

    rc, nachweis = _hochladen(tmp_path)

    assert rc == 1
    daten = json.loads(nachweis.read_text(encoding="utf-8"))
    assert daten["differenzen"] == 1 and daten["abweichend"] == ["berichte/b3.md"]


def test_verstuemmelte_datei_ist_kein_erfolg(tmp_path: Path, box) -> None:
    """Fängt: Der Host speichert eine Datei falsch, nur das Rücklesen kann das sehen."""
    _paket(tmp_path)
    box.verstuemmeln = "berichte/b5.md"

    rc, nachweis = _hochladen(tmp_path)

    assert rc == 1
    assert json.loads(nachweis.read_text(encoding="utf-8"))["abweichend"] == ["berichte/b5.md"]


def test_dauerhafte_abweisung_endet_mit_fehler(tmp_path: Path, box, capsys) -> None:
    """Fängt: Ein Host, der nie wieder annimmt, gibt eine Endlosschleife oder Exit 0."""
    _paket(tmp_path)
    box.geduld = 0
    box.abweisen_ab, box.abweisungen = 5, 10_000

    rc, nachweis = _hochladen(tmp_path)

    assert rc == 1
    assert "Upload nicht vollständig" in capsys.readouterr().out
    assert not nachweis.exists()


def test_zweiter_aufruf_macht_nach_abbruch_weiter_und_loescht_nichts(tmp_path: Path, box) -> None:
    """Fängt: Nach einem Abbruch scheitert der zweite Aufruf (Ordner gibt es schon) oder löscht Fremdes."""
    _paket(tmp_path)
    box.dateien["fremd.txt"] = b"vom Veranstalter"
    box.puts_bis_abbruch = 5

    rc, _ = _hochladen(tmp_path)
    assert rc == 1
    assert 0 < len(box.dateien) - 1 <= 5

    box.puts_bis_abbruch = 0
    rc, nachweis = _hochladen(tmp_path)

    daten = json.loads(nachweis.read_text(encoding="utf-8"))
    assert rc == 1  # Das Kriterium verlangt volle Übereinstimmung, die fremde Datei zählt als Differenz.
    assert daten["abweichend"] == ["fremd.txt"] and daten["fremd_im_teamordner"] == ["fremd.txt"]
    assert box.dateien["fremd.txt"] == b"vom Veranstalter"
    assert len(box.dateien) == 15

    del box.dateien["fremd.txt"]
    rc, nachweis = _hochladen(tmp_path)
    assert rc == 0
    assert json.loads(nachweis.read_text(encoding="utf-8"))["differenzen"] == 0


def test_verlorene_mkcol_antwort_stoert_nicht(tmp_path: Path, box) -> None:
    """Fängt: Der Ordner entstand, die Antwort ging verloren; die Wiederholung bekommt 405 und bricht ab."""
    _paket(tmp_path)
    box.mkcol_antwort_verlieren = True

    rc, _ = _hochladen(tmp_path)

    assert rc == 0
    assert len(box.dateien) == 14


def test_weiterleitung_wird_nicht_verfolgt(box) -> None:
    """Fängt: urllib folgt einer Weiterleitung und gibt den Authorization-Kopf an ein fremdes Ziel."""
    box.weiterleiten = True
    zugang = sv.Zugang("https://x.example.org/s/a", "t", "p")

    with pytest.raises(sv.urllib.error.HTTPError) as fehler:
        zugang.abruf("GET", "a.txt")

    assert fehler.value.code == 302
    assert box.anfragen == 1


def test_falscher_kopf_laedt_nichts_hoch(tmp_path: Path, box) -> None:
    """Fängt: Der Upload läuft aus einem alten Checkout, GitHub und SV-Box weichen dann ab."""
    _paket(tmp_path)

    rc, nachweis = _hochladen(tmp_path, kopf="0" * 40)

    assert rc == 1
    assert box.puts == 0 and not box.ordner and not nachweis.exists()


def test_geaenderte_abgabe_laedt_nichts_hoch(tmp_path: Path, box) -> None:
    """Fängt: Der Kopf stimmt, aber abgabe/ ist lokal neu erzeugt (Manifest und Dateien passen zueinander)."""
    _paket(tmp_path)
    (tmp_path / "abgabe" / "neu.md").write_text("ungeprüft\n", encoding="utf-8")

    rc, _ = _hochladen(tmp_path)

    assert rc == 1
    assert box.puts == 0


def test_manifest_abweichung_laedt_nichts_hoch(tmp_path: Path, box) -> None:
    """Fängt: Eine Datei passt nicht zum Manifest, der Upload läuft trotzdem."""
    _paket(tmp_path)
    (tmp_path / "abgabe" / "berichte" / "b1.md").write_text("anders\n", encoding="utf-8")
    _git(tmp_path, "add", "abgabe")
    _git(tmp_path, "commit", "-q", "-m", "anders")

    rc, _ = _hochladen(tmp_path)

    assert rc == 1
    assert box.puts == 0


def test_ausfuehren_ohne_kopf_wird_abgelehnt(tmp_path: Path, box) -> None:
    """Fängt: --ausfuehren ohne Bindung an einen Commit."""
    _paket(tmp_path)
    with pytest.raises(SystemExit, match="erwarteter-kopf"):
        sv.main(["--abgabe", str(tmp_path / "abgabe"), "--ausfuehren"])
    assert box.puts == 0


def _probe() -> int:
    return sv.main(["--probe"])


def test_probe_schreibt_liest_und_raeumt_auf(box, capsys) -> None:
    """Fängt: Die Testdatei bleibt liegen oder eine fremde Datei wird angefasst."""
    box.dateien["fremd.txt"] = b"vom Veranstalter"
    box.dateien["ordner/x.txt"] = b"auch fremd"
    box.ordner.add("ordner")

    assert _probe() == 0

    assert box.geloescht == [sv.PROBE_DATEI, sv.PROBE_ORDNER]
    assert box.dateien == {"fremd.txt": b"vom Veranstalter", "ordner/x.txt": b"auch fremd"}
    assert box.ordner == {"ordner"}
    assert box.puts == 1
    assert "geheim" not in capsys.readouterr().out


@pytest.mark.parametrize("name", ["fremd.txt", "probe.txt"])
def test_probe_fasst_vorhandenen_ordner_nicht_an(box, name: str) -> None:
    """Fängt: Der Ordner gibt es schon, auch eine fremde Datei namens probe.txt ginge sonst verloren."""
    box.ordner.add(sv.PROBE_ORDNER)
    box.dateien[f"{sv.PROBE_ORDNER}/{name}"] = b"fremd"

    assert _probe() == 1

    assert box.geloescht == [] and box.puts == 0
    assert box.dateien[f"{sv.PROBE_ORDNER}/{name}"] == b"fremd"


def test_probe_loescht_ordner_nicht_wenn_waehrenddessen_fremdes_auftaucht(box) -> None:
    """Fängt: Das rekursive DELETE des Ordners nimmt eine Datei mit, die während der Probe dazukam."""
    box.fremd_bei_put = f"{sv.PROBE_ORDNER}/neu.txt"

    assert _probe() == 1

    assert box.geloescht == [sv.PROBE_DATEI]
    assert box.dateien == {f"{sv.PROBE_ORDNER}/neu.txt": b"fremd"}


def test_probe_raeumt_auch_nach_fehler_auf(box) -> None:
    """Fängt: Das Rücklesen scheitert und die Testdatei bleibt im Teamordner liegen."""
    box.fehler[("GET", sv.PROBE_DATEI)] = 403

    assert _probe() == 1

    assert box.geloescht == [sv.PROBE_DATEI, sv.PROBE_ORDNER]
    assert not box.dateien and not box.ordner


def test_probe_erkennt_falschen_inhalt(box) -> None:
    """Fängt: Schreiben meldet Erfolg, der Host speichert aber etwas anderes."""
    box.verstuemmeln = sv.PROBE_DATEI

    assert _probe() == 1
    assert not box.dateien and not box.ordner


def _bare_mit_github_stand(tmp_path: Path) -> Path:
    arbeit = tmp_path / "gh-arbeit"
    arbeit.mkdir()
    _git(arbeit, "init", "-q", "-b", "main")
    (arbeit / "KI-Challenge_UseCase.yaml").write_text("use_case:\n  - uc3\n", encoding="utf-8")
    (arbeit / "README.md").write_text("kurz\n", encoding="utf-8")
    _git(arbeit, "add", ".")
    _git(arbeit, "commit", "-q", "-m", "GitHub-Stand")
    bare = tmp_path / "gh.git"
    _git(tmp_path, "clone", "-q", "--bare", str(arbeit), str(bare))
    return bare


def _quelle(tmp_path: Path, *alte_dateien: str, zeile: str = "sauber\n") -> tuple[Path, str]:
    quelle = tmp_path / "quelle"
    quelle.mkdir()
    _git(quelle, "init", "-q", "-b", "main")
    _git(quelle, "config", "user.name", "Test")
    _git(quelle, "config", "user.email", "test@example.org")
    (quelle / "KI-Challenge_UseCase.yaml").write_text("use_case:\n  - uc3\n", encoding="utf-8")
    (quelle / "README.md").write_text("lang\n", encoding="utf-8")
    for name in alte_dateien:
        pfad = quelle / name
        pfad.parent.mkdir(parents=True, exist_ok=True)
        pfad.write_text(zeile, encoding="utf-8")
    _git(quelle, "add", ".")
    _git(quelle, "commit", "-q", "-m", "erster Stand")
    for name in alte_dateien:
        (quelle / name).unlink()
    _git(quelle, "add", "-A")
    _git(quelle, "commit", "-q", "--allow-empty", "-m", "aufgeräumt")
    return quelle, _git(quelle, "rev-parse", "HEAD")


def _push(tmp_path: Path, quelle: Path, bare: Path, *zusatz: str) -> int:
    muster = tmp_path / "muster.txt"
    muster.write_text("rechner-[0-9]+\n", encoding="utf-8")
    argumente = ["--quelle", str(quelle), "--quelle-ref", "refs/heads/main", "--ziel-url", str(bare)]
    argumente += ["--sperrmuster", str(muster), "--arbeitsordner", str(tmp_path / "arbeit")]
    return gp.main([*argumente, *zusatz])


@pytest.fixture
def ohne_gitleaks(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(gp, "gitleaks", lambda *a: (True, "gemockt"))


def test_github_trockenlauf_pusht_nicht(tmp_path: Path, ohne_gitleaks) -> None:
    """Fängt: Ein vertauschtes --dry-run schiebt den Stand schon im Trockenlauf nach GitHub."""
    bare = _bare_mit_github_stand(tmp_path)
    quelle, _ = _quelle(tmp_path)
    vorher = _git(bare, "rev-parse", "refs/heads/main")

    assert _push(tmp_path, quelle, bare) == 0

    assert _git(bare, "rev-parse", "refs/heads/main") == vorher


def test_github_push_mit_kopf_und_ruecklesen(tmp_path: Path, ohne_gitleaks, monkeypatch) -> None:
    """Fängt: --ausfuehren pusht nicht oder pusht ohne Fast-Forward über den GitHub-Stand."""
    monkeypatch.setattr(gp, "NICHT_VOR", "2020-01-01T00:00")
    bare = _bare_mit_github_stand(tmp_path)
    alt = _git(bare, "rev-parse", "refs/heads/main")
    quelle, kopf = _quelle(tmp_path)
    nachweis = tmp_path / "n.json"

    rc = _push(tmp_path, quelle, bare, "--erwarteter-kopf", kopf, "--ausfuehren", "--nachweis", str(nachweis))

    assert rc == 0
    neu = _git(bare, "rev-parse", "refs/heads/main")
    assert neu != alt
    _git(bare, "merge-base", "--is-ancestor", alt, neu)
    _git(bare, "merge-base", "--is-ancestor", kopf, neu)
    daten = json.loads(nachweis.read_text(encoding="utf-8"))
    assert daten["github_kopf_danach"] == neu == daten["abgabe_commit"] and daten["push_zeit"]


def test_github_falscher_kopf_pusht_nicht(tmp_path: Path, ohne_gitleaks, monkeypatch) -> None:
    """Fängt: main ist weitergelaufen, gepusht würde ein ungeprüfter Stand."""
    monkeypatch.setattr(gp, "NICHT_VOR", "2020-01-01T00:00")
    bare = _bare_mit_github_stand(tmp_path)
    quelle, _ = _quelle(tmp_path)
    vorher = _git(bare, "rev-parse", "refs/heads/main")

    assert _push(tmp_path, quelle, bare, "--erwarteter-kopf", "0" * 40, "--ausfuehren") == 1

    assert _git(bare, "rev-parse", "refs/heads/main") == vorher


@pytest.mark.parametrize(
    "zusatz",
    [["--ausfuehren"], ["--erwarteter-kopf", "0" * 40, "--ausfuehren"], ["--nicht-vor", "2020-01-01T00:00"]],
)
def test_github_zu_frueh_oder_ohne_kopf_bricht_ab(tmp_path: Path, zusatz: list[str], monkeypatch) -> None:
    """Fängt: Der Push läuft vor der vom Owner gesetzten Zeit, ohne Kopf oder mit umgangener Sperre."""
    monkeypatch.setattr(gp, "_jetzt", lambda: gp.dt.datetime(2026, 11, 6, 8, 29, tzinfo=gp.WIEN))
    bare = _bare_mit_github_stand(tmp_path)
    quelle, _ = _quelle(tmp_path)
    vorher = _git(bare, "rev-parse", "refs/heads/main")

    with pytest.raises(SystemExit):
        _push(tmp_path, quelle, bare, *zusatz)

    assert _git(bare, "rev-parse", "refs/heads/main") == vorher


def test_github_geloeschte_einzeldaten_in_historie_blocken(tmp_path: Path, ohne_gitleaks) -> None:
    """Fängt: Eine früher committete Lieferung wird öffentlich, obwohl der Baum sauber ist."""
    bare = _bare_mit_github_stand(tmp_path)
    quelle, _ = _quelle(tmp_path, "abgabe/ministerium_2026-07.csv")
    nachweis = tmp_path / "n.json"

    assert _push(tmp_path, quelle, bare, "--nachweis", str(nachweis)) == 1

    befunde = {b["name"]: b for b in json.loads(nachweis.read_text(encoding="utf-8"))["pruefungen"]}
    assert not befunde["dateiliste historie"]["ok"]
    assert befunde["dateiliste"]["ok"]


def test_github_alte_dateistaende_werden_gezaehlt_ohne_zu_blocken(tmp_path: Path, ohne_gitleaks) -> None:
    """Fängt: Rechnernamen in alten Dateiständen bleiben unsichtbar; ob sie blocken, entscheidet der Lead."""
    bare = _bare_mit_github_stand(tmp_path)
    quelle, _ = _quelle(tmp_path, "notiz.md", zeile="auf rechner-7 gelaufen\n")
    nachweis = tmp_path / "n.json"

    assert _push(tmp_path, quelle, bare, "--nachweis", str(nachweis)) == 0

    roh = nachweis.read_text(encoding="utf-8")
    befunde = {b["name"]: b for b in json.loads(roh)["pruefungen"]}
    text = befunde["sperrmuster historie (Zählwert)"]["text"]
    assert text.startswith("1 alte Dateistände") and "notiz.md" in text
    assert "rechner-7" not in roh


def test_trockenlauf_meldet_fremde_datei_mit_exit_1(tmp_path: Path, box, capsys) -> None:
    """Fängt: Der Trockenlauf sagt „Alles bereit“, der echte Lauf endet wegen derselben Datei mit Exit 1."""
    _paket(tmp_path)
    box.dateien["fremd.txt"] = b"vom Veranstalter"

    rc, _ = _hochladen(tmp_path, ausfuehren=False)

    ausgabe = capsys.readouterr().out
    assert rc == 1
    assert "[FEHLT] nicht im Manifest" in ausgabe and "Alles bereit" not in ausgabe
    assert box.dateien == {"fremd.txt": b"vom Veranstalter"}


def test_link_und_token_muessen_zusammenpassen(tmp_path: Path, box, monkeypatch, capsys) -> None:
    """Fängt: Der Token gehört zu einem anderen Share, der Upload ginge in den falschen Ordner."""
    _paket(tmp_path)
    monkeypatch.setenv("SVBOX_TEAM_TOKEN", "anderes-geheimnis")

    with pytest.raises(SystemExit) as fehler:
        _hochladen(tmp_path, ausfuehren=False)

    assert "anderes-geheimnis" not in str(fehler.value) and "anderes-geheimnis" not in capsys.readouterr().out
    assert box.anfragen == 0


def test_trockenlauf_schreibt_nichts(tmp_path: Path, box) -> None:
    """Fängt: Ohne --ausfuehren gelangt doch eine Datei oder ein Ordner in den Teamordner."""
    _paket(tmp_path)

    rc, nachweis = _hochladen(tmp_path, ausfuehren=False)

    assert rc == 0
    assert not box.dateien and not box.ordner and box.puts == 0
    assert not nachweis.exists()
