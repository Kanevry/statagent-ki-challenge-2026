"""Ereignisse, Teilnahme und Positionen in PG (`uc2/sql/002_verhandlung.sql`).

Nur `uv run uc2 verhandlung` schreibt (`Fallschreiber`); `seq` zählt je Fall ab 1 in fester Reihenfolge.
Nach jedem Schreiben wird committet, damit Leser (Replay, später SSE) den Stand sofort sehen. Die
Lesefunktionen werten einen laufenden Fall nach `ABBRUCH_S` Sekunden ohne Lebenszeichen als abgebrochen.
"""

from __future__ import annotations

import threading
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any

import psycopg
from plattform.protokoll import NeuerEintrag, ddl_einspielen  # type: ignore[import-untyped]  # kein py.typed
from plattform.protokoll import schreibe as protokoll_schreibe
from psycopg import pq
from psycopg.types.json import Jsonb

from uc2 import pfade
from uc2.verhandlung.matrix import Position, Runde

DDL = pfade.SQL / "002_verhandlung.sql"
DDL_FREIGABE = pfade.SQL / "003_freigabe.sql"
ABBRUCH_S = 60
STATUS = ("laufend", "fertig", "abgebrochen")


def ddl_anwenden(verbindung: psycopg.Connection[Any]) -> None:
    """Schema der Verhandlung und der Freigabe idempotent anlegen."""
    verbindung.execute(DDL.read_text(encoding="utf-8"))
    verbindung.execute(DDL_FREIGABE.read_text(encoding="utf-8"))
    verbindung.commit()


def neuer_fall(
    verbindung: psycopg.Connection[Any],
    *,
    fall_name: str,
    frage: str,
    provider: str,
    belegquelle: str,
    modelle: dict[str, Any],
    stichtag: Any,
) -> int:
    zeile = verbindung.execute(
        "insert into uc2.fall (fall_name, frage, provider, belegquelle, modelle, stichtag) "
        "values (%s, %s, %s, %s, %s, %s) returning fall_id",
        (fall_name, frage, provider, belegquelle, Jsonb(modelle), stichtag),
    ).fetchone()
    verbindung.commit()
    assert zeile is not None
    return int(zeile[0])


class Fallschreiber:
    """Einziger Schreiber eines Falls; nicht thread-sicher, nur aus dem Hauptfaden benutzen."""

    def __init__(self, verbindung: psycopg.Connection[Any], fall_id: int) -> None:
        self.verbindung = verbindung
        self.fall_id = fall_id
        self.seq = 0

    def ereignis(
        self,
        art: str,
        daten: dict[str, Any] | None = None,
        *,
        runde: int | None = None,
        akteur: str | None = None,
    ) -> int:
        self.seq += 1
        self.verbindung.execute(
            "insert into uc2.ereignis (fall_id, seq, runde, art, akteur, daten) "
            "values (%s, %s, %s, %s, %s, %s)",
            (self.fall_id, self.seq, runde, art, akteur, Jsonb(daten or {})),
        )
        self.verbindung.execute(
            "update uc2.fall set lebenszeichen = now() where fall_id = %s", (self.fall_id,)
        )
        self.verbindung.commit()
        return self.seq

    def lebenszeichen(self) -> None:
        self.verbindung.execute(
            "update uc2.fall set lebenszeichen = now() where fall_id = %s", (self.fall_id,)
        )
        self.verbindung.commit()

    def auftrag(self, auftrag: dict[str, Any]) -> None:
        self.verbindung.execute(
            "update uc2.fall set auftrag = %s where fall_id = %s", (Jsonb(auftrag), self.fall_id)
        )
        self.verbindung.commit()

    def teilnahme(self, akteur: str, eingeladen: bool, begruendung: str, belegzahl: int) -> None:
        self.verbindung.execute(
            "insert into uc2.teilnahme (fall_id, akteur, eingeladen, begruendung, belegzahl) "
            "values (%s, %s, %s, %s, %s)",
            (self.fall_id, akteur, eingeladen, begruendung, belegzahl),
        )
        self.verbindung.commit()

    def positionen(self, runde: int, positionen: Runde) -> None:
        with self.verbindung.cursor() as cur:
            cur.executemany(
                "insert into uc2.position "
                "(fall_id, runde, akteur, thema, wert, begruendung, beleg_ids, quelle) "
                "values (%s, %s, %s, %s, %s, %s, %s, %s)",
                [
                    (
                        self.fall_id,
                        runde,
                        p.akteur,
                        p.thema,
                        p.wert,
                        p.begruendung,
                        list(p.beleg_ids),
                        p.quelle,
                    )
                    for akteur in sorted(positionen)
                    for _, p in sorted(positionen[akteur].items())
                ],
            )
        self.verbindung.commit()

    def beende(self, status: str) -> None:
        if status not in STATUS:
            raise ValueError(f"unbekannter Status {status!r}")
        self.verbindung.execute(
            "update uc2.fall set status = %s, ende = now(), lebenszeichen = now() where fall_id = %s",
            (status, self.fall_id),
        )
        self.verbindung.commit()


class Herzschlag:
    """Lebenszeichen alle `takt_s` Sekunden über eine eigene Verbindung, solange ein Modellaufruf läuft.

    Ein einzelner claude-Aufruf kann länger als `ABBRUCH_S` dauern; ohne Herzschlag gälte der Fall dann
    fälschlich als abgebrochen. Stirbt der Prozess, endet auch der Herzschlag.
    """

    def __init__(self, verbinde: Callable[[], psycopg.Connection[Any]], fall_id: int, takt_s: float) -> None:
        self._verbinde = verbinde
        self._fall_id = fall_id
        self._takt = takt_s
        self._stopp = threading.Event()
        self._faden = threading.Thread(target=self._lauf, name=f"herzschlag-{fall_id}", daemon=True)

    def _lauf(self) -> None:
        with self._verbinde() as verbindung:
            while not self._stopp.wait(self._takt):
                verbindung.execute(
                    "update uc2.fall set lebenszeichen = now() where fall_id = %s and status = 'laufend'",
                    (self._fall_id,),
                )
                verbindung.commit()

    def __enter__(self) -> Herzschlag:
        self._faden.start()
        return self

    def __exit__(self, *_: object) -> None:
        self._stopp.set()
        self._faden.join(timeout=5)


# --- Lesen ---------------------------------------------------------------------------------------------


def wirksamer_status(status: str, lebenszeichen: datetime, jetzt: datetime | None = None) -> str:
    """`laufend` ohne Lebenszeichen seit `ABBRUCH_S` Sekunden gilt als `abgebrochen`."""
    jetzt = jetzt or datetime.now(UTC)
    if status == "laufend" and jetzt - lebenszeichen > timedelta(seconds=ABBRUCH_S):
        return "abgebrochen"
    return status


def lies_fall(
    verbindung: psycopg.Connection[Any], fall_id: int, jetzt: datetime | None = None
) -> dict[str, Any] | None:
    zeile = verbindung.execute(
        "select fall_id, fall_name, frage, auftrag, provider, belegquelle, modelle, stichtag, status, "
        "lebenszeichen, start, ende from uc2.fall where fall_id = %s",
        (fall_id,),
    ).fetchone()
    if zeile is None:
        return None
    namen = ("fall_id", "fall_name", "frage", "auftrag", "provider", "belegquelle", "modelle", "stichtag")
    fall: dict[str, Any] = dict(zip(namen, zeile[:8], strict=True))
    fall["status_gespeichert"] = zeile[8]
    fall["status"] = wirksamer_status(zeile[8], zeile[9], jetzt)
    fall["lebenszeichen"], fall["start"], fall["ende"] = zeile[9], zeile[10], zeile[11]
    return fall


def lies_ereignisse(
    verbindung: psycopg.Connection[Any], fall_id: int, ab_seq: int = 0
) -> list[dict[str, Any]]:
    return [
        {"seq": z[0], "runde": z[1], "art": z[2], "akteur": z[3], "daten": z[4], "zeit": z[5]}
        for z in verbindung.execute(
            "select seq, runde, art, akteur, daten, zeit from uc2.ereignis where fall_id = %s and seq > %s "
            "order by seq",
            (fall_id, ab_seq),
        )
    ]


def lies_teilnahme(verbindung: psycopg.Connection[Any], fall_id: int) -> list[dict[str, Any]]:
    return [
        {"akteur": z[0], "eingeladen": z[1], "begruendung": z[2], "belegzahl": z[3]}
        for z in verbindung.execute(
            "select akteur, eingeladen, begruendung, belegzahl from uc2.teilnahme where fall_id = %s "
            "order by eingeladen desc, akteur",
            (fall_id,),
        )
    ]


def lies_positionen(verbindung: psycopg.Connection[Any], fall_id: int) -> dict[int, Runde]:
    runden: dict[int, Runde] = {}
    for z in verbindung.execute(
        "select runde, akteur, thema, wert, begruendung, beleg_ids, quelle from uc2.position "
        "where fall_id = %s order by runde, akteur, thema",
        (fall_id,),
    ):
        runden.setdefault(int(z[0]), {}).setdefault(str(z[1]), {})[str(z[2])] = Position(
            akteur=str(z[1]),
            thema=str(z[2]),
            wert=int(z[3]),
            begruendung=str(z[4]),
            beleg_ids=tuple(z[5]),
            quelle=str(z[6]),
        )
    return runden


# --- Freigabe des Berichts -----------------------------------------------------------------------------


def lies_freigabe(verbindung: psycopg.Connection[Any], fall_id: int) -> dict[str, Any] | None:
    """Entscheidung zum Bericht (`name`, `zeit`, `entscheidung`, `begruendung`) oder `None`, wenn offen.

    Fehlt die Tabelle (Datenbank ohne `003_freigabe.sql`), gilt der Bericht als offen. Der Savepoint hält
    eine bereits offene Transaktion des Aufrufers brauchbar.
    """
    try:
        with verbindung.transaction():
            zeile = verbindung.execute(
                "select name, zeitpunkt, entscheidung, begruendung from uc2.freigabe where fall_id = %s",
                (fall_id,),
            ).fetchone()
    except psycopg.errors.UndefinedTable:
        return None
    if zeile is None:
        return None
    return {"name": zeile[0], "zeit": zeile[1], "entscheidung": zeile[2], "begruendung": zeile[3]}


def schreibe_freigabe(
    verbindung: psycopg.Connection[Any],
    fall_id: int,
    name: str,
    entscheidung: str,
    begruendung: str | None,
    fall_name: str,
) -> datetime | None:
    """Speichert die Entscheidung, eine Zeile in `meta.protokoll` und eine in `meta.freigabe`, zusammen.

    Vertrag P: `meta.freigabe` bekommt `ja|nein`, `objekt_typ='antwort'` und `objekt_ref='uc2/fall/<id>'`;
    ohne diese Zeile fehlte eine Ablehnung im Abschnitt „Ablehnungen“ von `protokoll.md`. Alles läuft in einer
    Transaktion, es gibt keinen Git-Commit. Gibt den Zeitpunkt zurück, oder `None`, wenn der Fall schon
    entschieden ist. Namen und Zustand des Falls prüft der Aufrufer (`uc2.verhandlung.freigabe`). Die
    Verbindung braucht `autocommit=True` ohne offene Transaktion, sonst wäre alles nur ein Savepoint.
    """
    if entscheidung not in ("freigegeben", "abgelehnt"):
        raise ValueError(f"unbekannte Entscheidung {entscheidung!r}")
    if not verbindung.autocommit or verbindung.info.transaction_status != pq.TransactionStatus.IDLE:
        raise ValueError("Die Verbindung braucht autocommit=True ohne offene Transaktion.")
    verbindung.execute(DDL_FREIGABE.read_text(encoding="utf-8"))
    ddl_einspielen(verbindung)
    with verbindung.transaction():
        zeile = verbindung.execute(
            "insert into uc2.freigabe (fall_id, name, entscheidung, begruendung) values (%s, %s, %s, %s) "
            "on conflict (fall_id) do nothing returning zeitpunkt",
            (fall_id, name, entscheidung, begruendung),
        ).fetchone()
        if zeile is None:
            return None
        ok = entscheidung == "freigegeben"
        protokoll_id = protokoll_schreibe(
            verbindung,
            NeuerEintrag(
                uc="uc2",
                akteur="mensch",
                name=name,
                anweisung=f"Bericht der Verhandlung {fall_name} (Fall {fall_id}) "
                + ("freigeben" if ok else "ablehnen"),
                wirkung="Ergebnis als geprüft markiert" if ok else f"Abgelehnt: {begruendung}",
                vorschlag_typ="bericht",
                status="freigegeben" if ok else "abgelehnt",
                ref=f"uc2/fall/{fall_id}",
            ),
        )
        verbindung.execute(
            "update uc2.freigabe set protokoll_id = %s where fall_id = %s", (protokoll_id, fall_id)
        )
        verbindung.execute(
            "insert into meta.freigabe"
            " (protokoll_id, name, entscheidung, begruendung, objekt_typ, objekt_ref)"
            " values (%s, %s, %s, %s, 'antwort', %s)",
            (protokoll_id, name, "ja" if ok else "nein", None if ok else begruendung, f"uc2/fall/{fall_id}"),
        )
    zeitpunkt: datetime = zeile[0]
    return zeitpunkt
