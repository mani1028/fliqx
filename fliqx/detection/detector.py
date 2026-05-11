from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

import numpy as np

from ..utils import normalize_image, to_grayscale


@dataclass(slots=True)
class BoundingBox:
    x: int
    y: int
    width: int
    height: int

    @property
    def area(self) -> int:
        return max(self.width, 0) * max(self.height, 0)

    def clamp(self, width: int, height: int) -> "BoundingBox":
        x = max(0, min(self.x, width - 1))
        y = max(0, min(self.y, height - 1))
        x2 = max(x + 1, min(self.x + self.width, width))
        y2 = max(y + 1, min(self.y + self.height, height))
        return BoundingBox(x=x, y=y, width=x2 - x, height=y2 - y)

    def to_slice(self) -> tuple[slice, slice]:
        return slice(self.y, self.y + self.height), slice(self.x, self.x + self.width)


@dataclass(slots=True)
class DetectedFace:
    bbox: BoundingBox
    score: float
    landmarks: np.ndarray | None = None


class FaceDetector(Protocol):
    def detect(self, image: np.ndarray) -> list[DetectedFace]:
        raise NotImplementedError


class WholeFrameDetector:
    def detect(self, image: np.ndarray) -> list[DetectedFace]:
        view = normalize_image(image)
        bbox = BoundingBox(0, 0, view.width, view.height)
        return [DetectedFace(bbox=bbox, score=1.0)]


class OpenCVCascadeDetector:
    def __init__(self, min_face_size: int = 24) -> None:
        self.min_face_size = min_face_size
        try:
            import cv2  # type: ignore
        except Exception as exc:  # pragma: no cover - optional dependency
            raise ImportError("opencv-python is required for OpenCVCascadeDetector") from exc
        self._cv2 = cv2
        cascade_path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
        self._cascade = cv2.CascadeClassifier(cascade_path)

    def detect(self, image: np.ndarray) -> list[DetectedFace]:
        view = normalize_image(image)
        gray = to_grayscale(view.data)
        faces = self._cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=4, minSize=(self.min_face_size, self.min_face_size))
        results: list[DetectedFace] = []
        for (x, y, width, height) in faces:
            bbox = BoundingBox(int(x), int(y), int(width), int(height)).clamp(view.width, view.height)
            results.append(DetectedFace(bbox=bbox, score=0.9))
        if not results:
            results.append(DetectedFace(bbox=BoundingBox(0, 0, view.width, view.height), score=0.1))
        return results


class AutoDetector:
    def __init__(self, min_face_size: int = 24) -> None:
        try:
            self._delegate: FaceDetector = OpenCVCascadeDetector(min_face_size=min_face_size)
        except Exception:
            self._delegate = WholeFrameDetector()

    def detect(self, image: np.ndarray) -> list[DetectedFace]:
        return self._delegate.detect(image)
