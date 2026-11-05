"""HTTP-Schnittstelle von UC2: `uv run uvicorn uc2.api:app --port 8102` (#44)."""

from uc2.api.app import erstelle_app

app = erstelle_app()

__all__ = ["app", "erstelle_app"]
