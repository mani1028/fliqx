from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Iterator

import numpy as np

from .frames import resize_frame


@dataclass(slots=True)
class StreamFrame:
    index: int
    frame: np.ndarray


class VideoStream:
    def __init__(self, source: str | int | Path | Iterable[np.ndarray], max_side: int = 640) -> None:
        self.source = source
        self.max_side = max_side

    def __iter__(self) -> Iterator[StreamFrame]:
        if isinstance(self.source, Iterable) and not isinstance(self.source, (str, bytes, Path, int)):
            for index, frame in enumerate(self.source):
                yield StreamFrame(index=index, frame=resize_frame(np.asarray(frame), self.max_side))
            return
        try:
            import cv2  # type: ignore
        except Exception as exc:  # pragma: no cover - optional dependency
            raise ImportError("opencv-python is required for video streaming sources") from exc
        capture = cv2.VideoCapture(self.source)
        if not capture.isOpened():
            raise RuntimeError(f"Unable to open video source: {self.source}")
        index = 0
        try:
            while True:
                success, frame = capture.read()
                if not success:
                    break
                yield StreamFrame(index=index, frame=resize_frame(frame, self.max_side))
                index += 1
        finally:
            capture.release()
