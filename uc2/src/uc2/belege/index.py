"""Stufe 3: Extrakt (JSONL, optional Vektoren) in PG laden, in einer Transaktion und idempotent."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

import numpy as np
import psycopg

from uc2 import pfade
from uc2.belege.extraktion import lies_jsonl
from uc2.belege.vektoren import datei_hash, eingabe_texte, eingaben_hash, ids_hash


@dataclass(frozen=True)
class IndexErgebnis:
    quellen: int
    artikel: int
    abschnitte: int
    mit_vektor: int
    inhalt_hash: str
    modell: str | None
    meldung: str | None


def wende_sql_an(verbindung: psycopg.Connection[Any]) -> None:
    for datei in sorted(pfade.SQL.glob("*.sql")):
        verbindung.execute(datei.read_text(encoding="utf-8").encode("utf-8"))


class VektorenPassenNicht(RuntimeError):
    """Die Vektoren wurden aus anderen Texten gebildet als denen in `abschnitte.jsonl`; nie still laden."""


def lade_vektoren(
    extrakt: Path, abschnitt_ids: list[str], eingaben: list[str]
) -> tuple[np.ndarray[Any, Any] | None, dict[str, Any], str | None]:
    """Vektoren nur, wenn Prüfsummen und Form zu `abschnitte.jsonl` passen; sonst (None, {}, Meldung).

    `eingaben` sind die Modell-Eingaben je Abschnitt (`eingabe_texte`). Die IDs allein reichen nicht:
    `<artikel_id>-nn` bleibt gleich, wenn ein Abschnitt neu geschnitten wird. Weicht der Eingabe-Hash ab oder
    fehlt er (vektoren.json vor diesem Feld), bricht das Laden mit `VektorenPassenNicht` ab.
    """
    npy, meta_pfad = extrakt / "vektoren.npy", extrakt / "vektoren.json"
    if not npy.exists() or not meta_pfad.exists():
        return None, {}, "keine vektoren.npy/vektoren.json im Extrakt: Index ohne Vektoren"
    meta: dict[str, Any] = json.loads(meta_pfad.read_text(encoding="utf-8"))
    if meta.get("abschnitt_ids_sha256") != ids_hash(abschnitt_ids) or meta.get("anzahl") != len(
        abschnitt_ids
    ):
        return (
            None,
            {},
            (
                f"vektoren.json passt nicht zu abschnitte.jsonl ({meta.get('anzahl')} Vektoren, "
                f"{len(abschnitt_ids)} "
                "Abschnitte, z. B. Probelauf mit --grenze): Index ohne Vektoren"
            ),
        )
    if "eingaben_sha256" not in meta:
        raise VektorenPassenNicht(
            f"{meta_pfad} hat keinen Eingabe-Hash (eingaben_sha256, älteres Format): "
            "Texte und Vektoren lassen sich nicht abgleichen, bitte neu einbetten (uc2 einbetten)"
        )
    if meta["eingaben_sha256"] != eingaben_hash(eingaben):
        raise VektorenPassenNicht(
            f"{meta_pfad}: die Vektoren stammen aus anderen Abschnittstexten als abschnitte.jsonl "
            "(gleiche IDs, anderer Text, etwa nach neuer Zerlegung): bitte neu einbetten (uc2 einbetten)"
        )
    if meta.get("npy_sha256") != datei_hash(npy):
        return None, {}, "vektoren.npy weicht von der Prüfsumme in vektoren.json ab: Index ohne Vektoren"
    matrix = np.load(npy)
    if matrix.dtype != np.float32 or matrix.shape != (len(abschnitt_ids), int(meta["dim"])):
        return (
            None,
            {},
            f"vektoren.npy hat Form {matrix.shape}/{matrix.dtype}, erwartet float32: Index ohne Vektoren",
        )
    return matrix, meta, None


INHALT_SQL = """
select q.ausgabedatum, a.artikeldatum, a.medium, a.typ, a.titel, a.pdf_seite, a.zeitungsseite,
       s.nr, s.text_hash, s.institutionen, s.modell, s.dim, md5(coalesce(s.vektor, ''::bytea))
from uc2.abschnitt s
join uc2.artikel a using (artikel_id)
join uc2.quelle q on q.md5 = a.quelle_md5
where q.md5 = any(%s)
order by q.ausgabedatum, a.artikeldatum, a.medium collate "C", a.titel collate "C", a.pdf_seite, s.nr,
         s.text_hash collate "C"
"""
# collate "C": Die Sortierung darf nicht von der DB-Collation abhängen (gemessen 05.11.: M4 de_AT.UTF-8,
# m5-Container en_US.utf8 → gleicher Inhalt, verschiedener Hash).


def inhalt_hash(verbindung: psycopg.Connection[Any], md5s: list[str]) -> str:
    """sha256 über den Inhalt ohne IDs und Zeitstempel."""
    h = hashlib.sha256()
    for zeile in verbindung.execute(INHALT_SQL, (md5s,)):
        h.update(json.dumps(zeile, ensure_ascii=False, default=str).encode("utf-8") + b"\n")
    return h.hexdigest()


QUELLE_SQL = (
    "insert into uc2.quelle (md5, datei, ausgabedatum, seiten, uebersprungen, grund) "
    "values (%s, %s, %s, %s, %s, %s) on conflict (md5) "
)


def _quellzeile(q: dict[str, Any]) -> tuple[Any, ...]:
    return (
        q["md5"],
        q["datei"],
        date.fromisoformat(q["ausgabedatum"]),
        q["seiten"],
        q["uebersprungen"],
        q["grund"],
    )


def indexiere(extrakt: Path, verbindung: psycopg.Connection[Any]) -> IndexErgebnis:
    quellen = [
        q
        for q in lies_jsonl(extrakt / "quellen.jsonl")
        if not str(q.get("grund") or "").startswith("dublette")
    ]
    # Lesefehler: Die Quelle bleibt, wie sie in PG steht (Artikel, Abschnitte, Quellzeile); neu ist sie nur
    # als übersprungen eingetragen. Ein vorübergehender pdftotext-Fehler darf schon indexierte Artikel nicht
    # löschen, und eine unlesbare PDF soll den Lauf über die übrigen nicht verhindern. Sichtbar bleibt sie in
    # der Meldung, in quellen.jsonl/abweichungen.jsonl und im Prüfskript (liest die PDF selbst).
    lesefehler = [q for q in quellen if str(q.get("grund") or "").startswith("lesefehler")]
    gelesen = [q for q in quellen if q["md5"] not in {f["md5"] for f in lesefehler}]
    artikel = lies_jsonl(extrakt / "artikel.jsonl")
    abschnitte = lies_jsonl(extrakt / "abschnitte.jsonl")
    matrix, meta, meldung = lade_vektoren(
        extrakt, [a["abschnitt_id"] for a in abschnitte], eingabe_texte(artikel, abschnitte)
    )
    if lesefehler:
        hinweis = (
            f"{len(lesefehler)} Quelle(n) mit Lesefehler, bestehender Index für sie unverändert: "
            + ", ".join(sorted(q["datei"] for q in lesefehler))
        )
        meldung = f"{meldung}; {hinweis}" if meldung else hinweis
    modell = str(meta["modell_id"]) if matrix is not None else None
    md5s = sorted(q["md5"] for q in quellen)
    neu_md5s = sorted(q["md5"] for q in gelesen)

    with verbindung.transaction():
        wende_sql_an(verbindung)
        verbindung.execute(
            "delete from uc2.abschnitt where artikel_id in "
            "(select artikel_id from uc2.artikel where quelle_md5 = any(%s))",
            (neu_md5s,),
        )
        verbindung.execute("delete from uc2.artikel where quelle_md5 = any(%s)", (neu_md5s,))
        with verbindung.cursor() as cur:
            cur.executemany(
                QUELLE_SQL + "do update set datei = excluded.datei, "
                "ausgabedatum = excluded.ausgabedatum, seiten = excluded.seiten, "
                "uebersprungen = excluded.uebersprungen, grund = excluded.grund",
                [_quellzeile(q) for q in gelesen],
            )
            if lesefehler:
                cur.executemany(QUELLE_SQL + "do nothing", [_quellzeile(q) for q in lesefehler])
            cur.executemany(
                "insert into uc2.artikel (artikel_id, quelle_md5, pdf_seite, zeitungsseite, artikeldatum, "
                "medium, "
                "typ, titel) values (%s, %s, %s, %s, %s, %s, %s, %s)",
                [
                    (
                        a["artikel_id"],
                        a["quelle_md5"],
                        a["pdf_seite"],
                        a["zeitungsseite"],
                        date.fromisoformat(a["artikeldatum"]),
                        a["medium"],
                        a["typ"],
                        a["titel"],
                    )
                    for a in artikel
                ],
            )
            dim = int(meta["dim"]) if matrix is not None else None
            cur.executemany(
                "insert into uc2.abschnitt (abschnitt_id, artikel_id, nr, text, text_hash, institutionen, "
                "vektor, "
                "modell, dim) values (%s, %s, %s, %s, %s, %s, %s, %s, %s)",
                [
                    (
                        s["abschnitt_id"],
                        s["artikel_id"],
                        s["nr"],
                        s["text"],
                        s["text_hash"],
                        s["institutionen"],
                        matrix[i].astype("<f4").tobytes() if matrix is not None else None,
                        modell,
                        dim,
                    )
                    for i, s in enumerate(abschnitte)
                ],
            )
        h = inhalt_hash(verbindung, md5s)
        verbindung.execute(
            "insert into uc2.index_lauf (anzahl, inhalt_hash, modell) values (%s, %s, %s)",
            (len(abschnitte), h, modell),
        )
    return IndexErgebnis(
        quellen=len(quellen),
        artikel=len(artikel),
        abschnitte=len(abschnitte),
        mit_vektor=len(abschnitte) if matrix is not None else 0,
        inhalt_hash=h,
        modell=modell,
        meldung=meldung,
    )
