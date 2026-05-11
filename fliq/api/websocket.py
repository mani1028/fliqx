from __future__ import annotations

from typing import Any

from fastapi import WebSocket, WebSocketDisconnect

from ..engine import Fliq


async def websocket_handler(websocket: WebSocket, engine: Fliq) -> None:
    await websocket.accept()
    try:
        while True:
            payload = await websocket.receive_json()
            image = payload.get("image")
            class_id = payload.get("class_id")
            if image is None:
                await websocket.send_json({"error": "image is required"})
                continue
            await websocket.send_json({"results": engine.recognize(image, class_id=str(class_id) if class_id is not None else None)})
    except WebSocketDisconnect:
        return
