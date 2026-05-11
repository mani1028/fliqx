from __future__ import annotations

from typing import Any

import numpy as np

from .detector import AutoDetector, DetectedFace, FaceDetector


class ScrfdDetector(FaceDetector):
    def __init__(self, model_path: str | None = None, **_: Any) -> None:
        self.model_path = model_path
        self._fallback = AutoDetector()

    def detect(self, image: np.ndarray) -> list[DetectedFace]:
        return self._fallback.detect(image)
