"""Start einer Verhandlung als Unterprozess `uv run uc2 verhandlung …` (#44, PRD S8).

Der Unterprozess ist der einzige Schreiber des Falls; die API liest nur. Feste argv ohne Shell, die Frage
kommt über stdin (`--frage-stdin`). Die Fall-ID liest die API aus der ersten stdout-Zeile `fall_id=<n>`
(`--melde-fall-id`, Begründung in `uc2.verhandlung.cli`). Den Rest von stdout liest ein Faden weg, damit der
Kindprozess nie an einer vollen Pipe hängt; stderr geht ins Server-Log, nie an den Client.
"""

from __future__ import annotations

import re
import subprocess
import threading
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import IO, Protocol

from uc2 import pfade

BASIS_ARGV: tuple[str, ...] = ("uv", "run", "--frozen", "uc2")
START_TIMEOUT_S = 90.0
"""So lange wartet POST höchstens auf `fall_id=<n>` (uv-Start, Importe, DDL)."""
_ZEILE = re.compile(r"^fall_id=(\d+)$")


class StartFehler(RuntimeError):
    """Der Lauf hat keinen Fall angelegt (Exit vor der Anlage, falsche erste Zeile, Zeitüberschreitung)."""


@dataclass(frozen=True)
class Startauftrag:
    fall: str
    provider: str
    belege: str
    frage: str | None = None


class Lauf(Protocol):
    """Gestarteter Lauf: die Fall-ID und ob der Schreiber noch arbeitet."""

    @property
    def fall_id(self) -> int: ...

    def laeuft(self) -> bool: ...


Starter = Callable[[Startauftrag], Lauf]


def argv_fuer(auftrag: Startauftrag, basis: Sequence[str] = BASIS_ARGV) -> list[str]:
    """Feste argv; Fall, Provider und Belegquelle sind vorher gegen Listen geprüft."""
    argv = [
        *basis,
        "verhandlung",
        "--fall",
        auftrag.fall,
        "--provider",
        auftrag.provider,
        "--belege",
        auftrag.belege,
        "--melde-fall-id",
    ]
    if auftrag.frage is not None:
        argv.append("--frage-stdin")
    return argv


@dataclass
class Unterprozess:
    fall_id: int
    prozess: subprocess.Popen[str]

    def laeuft(self) -> bool:
        return self.prozess.poll() is None


def _wegschreiben(strom: IO[str], prozess: subprocess.Popen[str]) -> None:
    for _ in strom:
        pass
    strom.close()
    prozess.wait()


class UnterprozessStarter:
    """Standard-Starter der API; `basis` und `cwd` sind für Tests ersetzbar."""

    def __init__(
        self,
        basis: Sequence[str] = BASIS_ARGV,
        cwd: Path | None = None,
        timeout_s: float = START_TIMEOUT_S,
    ) -> None:
        self.basis = tuple(basis)
        self.cwd = cwd or pfade.UC2_WURZEL
        self.timeout_s = timeout_s

    def __call__(self, auftrag: Startauftrag) -> Unterprozess:
        prozess = subprocess.Popen(
            argv_fuer(auftrag, self.basis),
            cwd=self.cwd,
            stdin=subprocess.PIPE if auftrag.frage is not None else subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=None,
            text=True,
            encoding="utf-8",
            shell=False,
        )
        assert prozess.stdout is not None
        stdout = prozess.stdout
        if auftrag.frage is not None:
            assert prozess.stdin is not None
            try:
                prozess.stdin.write(auftrag.frage)
                prozess.stdin.close()
            except BrokenPipeError:
                pass  # Der Prozess ist schon beendet; die fehlende erste Zeile meldet es unten.
        zeile: list[str] = []
        leser = threading.Thread(target=lambda: zeile.append(stdout.readline()), daemon=True)
        leser.start()
        leser.join(self.timeout_s)
        if leser.is_alive():
            prozess.kill()
            prozess.wait()
            raise StartFehler("Lauf hat innerhalb der Frist keinen Fall angelegt")
        treffer = _ZEILE.match(zeile[0].strip()) if zeile else None
        if treffer is None:
            if prozess.poll() is None:
                prozess.kill()
            prozess.wait()
            raise StartFehler(f"Lauf hat keinen Fall angelegt (Exit {prozess.returncode})")
        threading.Thread(
            target=_wegschreiben, args=(stdout, prozess), name="uc2-lauf-stdout", daemon=True
        ).start()
        return Unterprozess(int(treffer.group(1)), prozess)
