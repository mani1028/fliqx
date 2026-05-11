from __future__ import annotations

from dataclasses import dataclass, field
from typing import List

import numpy as np

from .tracker import TrackedFace, _iou, SimpleByteTrack
from .ids import TrackIdGenerator


@dataclass(slots=True)
class KalmanState:
    x: float
    y: float
    vx: float = 0.0
    vy: float = 0.0


class ByteTrackLite(SimpleByteTrack):
    """A lightweight ByteTrack-like tracker with simple linear motion prediction.

    This is not a full ByteTrack implementation but provides smoother track
    updates and prediction to reduce recognition frequency.
    """

    def __init__(self, max_age: int = 30, match_threshold: float = 0.3) -> None:
        super().__init__(max_age=max_age, match_threshold=match_threshold)
        self._states: dict[str, KalmanState] = {}

    def predict_position(self, track: TrackedFace, dt: float = 1.0) -> TrackedFace:
        state = self._states.get(track.track_id)
        if state is None:
            cx = track.bbox.x + track.bbox.width / 2.0
            cy = track.bbox.y + track.bbox.height / 2.0
            self._states[track.track_id] = KalmanState(x=cx, y=cy)
            return track
        # predict
        nx = state.x + state.vx * dt
        ny = state.y + state.vy * dt
        w = track.bbox.width
        h = track.bbox.height
        track.bbox = track.bbox.__class__(int(nx - w / 2), int(ny - h / 2), int(w), int(h))
        return track

    def update(self, detections: List) -> List[TrackedFace]:
        updated = super().update(detections)
        # update states
        for t in updated:
            cx = t.bbox.x + t.bbox.width / 2.0
            cy = t.bbox.y + t.bbox.height / 2.0
            state = self._states.get(t.track_id)
            if state is None:
                self._states[t.track_id] = KalmanState(x=cx, y=cy)
            else:
                # simple velocity estimation
                vx = (cx - state.x)
                vy = (cy - state.y)
                state.vx = 0.6 * state.vx + 0.4 * vx
                state.vy = 0.6 * state.vy + 0.4 * vy
                state.x = cx
                state.y = cy
        # clean up old states
        alive = {t.track_id for t in self._tracks}
        for tid in list(self._states.keys()):
            if tid not in alive:
                del self._states[tid]
        return updated


__all__ = ["ByteTrackLite"]
