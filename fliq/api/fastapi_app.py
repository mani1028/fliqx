from __future__ import annotations

from typing import Any

from ..engine import Fliq
from .routes import create_router


def create_app(engine: Fliq | None = None) -> Any:
    try:
        from fastapi import FastAPI  # type: ignore
    except Exception as exc:  # pragma: no cover - optional dependency
        raise ImportError("fastapi is required to use the API layer") from exc

    engine = engine or Fliq()
    app = FastAPI(title="FLIQ", version="0.1.0")
    app.include_router(create_router(engine))

    @app.get("/")
    def root() -> dict[str, str]:
        return {"name": "fliq", "status": "ready"}

    return app
