from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException

from ..engine import Fliq


def create_router(engine: Fliq) -> APIRouter:
    router = APIRouter()

    @router.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @router.post("/register")
    def register(payload: dict[str, Any]) -> dict[str, Any]:
        user_id = payload.get("user_id")
        image = payload.get("image")
        if user_id is None or image is None:
            raise HTTPException(status_code=400, detail="user_id and image are required")
        return engine.register(str(user_id), image)

    @router.post("/recognize")
    def recognize(payload: dict[str, Any]) -> dict[str, Any]:
        image = payload.get("image")
        class_id = payload.get("class_id")
        if image is None:
            raise HTTPException(status_code=400, detail="image is required")
        return {"results": engine.recognize(image, class_id=str(class_id) if class_id is not None else None)}

    return router
