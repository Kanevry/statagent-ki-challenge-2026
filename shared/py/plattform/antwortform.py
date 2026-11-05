"""Antwortform ``UcAntwort`` (UC4, #96): gemeinsame Form der Antwort jedes Use Case.

Jede Zahl zeigt per Index auf einen Beleg; ein Beleg nennt die Herkunft (Tabelle, Lieferung, SQL) und wird
nie erfunden. ``UcAntwort`` heißt so, weil ``plattform.llm.Antwort`` schon belegt ist.
Schema-Datei: ``uv run python -m plattform.antwortform schema`` schreibt ``shared/schema/uc-antwort.json``.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Literal, Self

from pydantic import BaseModel, ConfigDict, model_validator

SCHEMA_DATEI = Path(__file__).resolve().parents[2] / "schema" / "uc-antwort.json"

Uc = Literal["uc1", "uc2", "uc3"]


class Beleg(BaseModel):
    """Herkunft einer Aussage, z. B. ``quelle="roh.lieferung"``, ``lieferung="2025-03"``."""

    model_config = ConfigDict(extra="forbid")

    quelle: str
    lieferung: str | None
    monat: str | None
    sql: str | None
    ref: str | None


class Zahl(BaseModel):
    """Eine Zahl der Antwort; ``beleg`` ist der Index in ``UcAntwort.belege``."""

    model_config = ConfigDict(extra="forbid")

    bezeichnung: str
    wert: int | float
    einheit: str | None
    beleg: int


class UcAntwort(BaseModel):
    """Antwort eines Use Case in der UC4-Kette (Schema: ``shared/schema/uc-antwort.json``)."""

    model_config = ConfigDict(extra="forbid", title="UcAntwort")

    text: str
    belege: list[Beleg]
    zahlen: list[Zahl]
    uc: Uc
    modell: str | None
    protokoll_id: int | None

    @model_validator(mode="after")
    def _beleg_index_gueltig(self) -> Self:
        for nummer, zahl in enumerate(self.zahlen):
            if not 0 <= zahl.beleg < len(self.belege):
                vorhanden = len(self.belege)
                raise ValueError(
                    f"zahlen[{nummer}].beleg={zahl.beleg} zeigt auf keinen Beleg ({vorhanden} vorhanden)"
                )
        return self


def antwort_schema() -> dict[str, Any]:
    """JSON-Schema der ``UcAntwort`` (Draft 2020-12), Quelle der eingecheckten Schema-Datei."""
    schema = UcAntwort.model_json_schema()
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", **schema}


def schema_text() -> str:
    return json.dumps(antwort_schema(), ensure_ascii=False, indent=2) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m plattform.antwortform")
    befehle = parser.add_subparsers(dest="befehl", required=True)
    schema = befehle.add_parser("schema", help="JSON-Schema der UcAntwort nach shared/schema schreiben")
    schema.add_argument("--out", type=Path, default=SCHEMA_DATEI)
    args = parser.parse_args(argv)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(schema_text(), encoding="utf-8")
    print(args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
