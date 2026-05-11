from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

import numpy as np

from ..detection.detector import BoundingBox, DetectedFace
from .ids import TrackIdGenerator


def _iou(left: BoundingBox, right: BoundingBox) -> float:
    left_x2 = left.x + left.width
    left_y2 = left.y + left.height
    right_x2 = right.x + right.width
    right_y2 = right.y + right.height
    intersection_x1 = max(left.x, right.x)
    intersection_y1 = max(left.y, right.y)
    intersection_x2 = min(left_x2, right_x2)
    intersection_y2 = min(left_y2, right_y2)
    intersection_width = max(0, intersection_x2 - intersection_x1)
    intersection_height = max(0, intersection_y2 - intersection_y1)
    intersection_area = intersection_width * intersection_height
    if intersection_area == 0:
        return 0.0
    union_area = left.area + right.area - intersection_area
    return float(intersection_area / max(union_area, 1))


@dataclass(slots=True)
class TrackedFace:
    track_id: str
    bbox: BoundingBox
    score: float
    age: int = 0
    hits: int = 1
    misses: int = 0
    user_id: str | None = None
    confidence: float = 0.0
    embedding: np.ndarray | None = None
    metadata: dict[str, object] = field(default_factory=dict)


class FaceTracker(Protocol):
    def update(self, detections: list[DetectedFace]) -> list[TrackedFace]:
        raise NotImplementedError


class SimpleByteTrack:
    def __init__(self, max_age: int = 30, match_threshold: float = 0.3) -> None:
        self.max_age = max_age
        self.match_threshold = match_threshold
        self._tracks: list[TrackedFace] = []
        self._ids = TrackIdGenerator()

    @property
    def tracks(self) -> list[TrackedFace]:
        return list(self._tracks)

    def update(self, detections: list[DetectedFace]) -> list[TrackedFace]:
        updated: list[TrackedFace] = []
        unmatched_detections = list(detections)
        for track in self._tracks:
            track.age += 1
            track.misses += 1
        for detection in detections:
            best_track: TrackedFace | None = None
            best_score = 0.0
            for track in self._tracks:
                score = _iou(track.bbox, detection.bbox)
                if score > best_score:
                    best_score = score
                    best_track = track
            if best_track is not None and best_score >= self.match_threshold:
                best_track.bbox = detection.bbox
                best_track.score = detection.score
                best_track.hits += 1
                best_track.misses = 0
                best_track.age = 0
                updated.append(best_track)
                unmatched_detections.remove(detection)
        for detection in unmatched_detections:
            track = TrackedFace(track_id=self._ids.next(), bbox=detection.bbox, score=detection.score)
            self._tracks.append(track)
            updated.append(track)
        self._tracks = [track for track in self._tracks if track.misses <= self.max_age]
        return updated
