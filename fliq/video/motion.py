from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from ..utils import to_grayscale


@dataclass(slots=True)
class MotionResult:
    active: bool
    score: float


class MotionDetector:
    def __init__(self, threshold: float = 12.0) -> None:
        self.threshold = threshold
        self._previous_gray: np.ndarray | None = None

    def reset(self) -> None:
        self._previous_gray = None

    def detect(self, frame: np.ndarray) -> MotionResult:
        gray = to_grayscale(frame).astype(np.float32)
        if self._previous_gray is None:
            self._previous_gray = gray
            return MotionResult(active=True, score=1.0)
        difference = np.abs(gray - self._previous_gray)
        score = float(np.mean(difference))
        self._previous_gray = gray
        return MotionResult(active=score >= self.threshold, score=score)
