from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class FrameOptimizationPlan:
    frame_skip: int
    max_side: int
    recognition_interval: int


class AdaptiveOptimizer:
    def __init__(self, base_frame_skip: int = 5, base_max_side: int = 640, base_recognition_interval: int = 10) -> None:
        self.base_frame_skip = base_frame_skip
        self.base_max_side = base_max_side
        self.base_recognition_interval = base_recognition_interval

    def plan(self, load_factor: float, motion_score: float) -> FrameOptimizationPlan:
        if load_factor > 0.85:
            frame_skip = self.base_frame_skip + 4
            max_side = max(320, self.base_max_side // 2)
            recognition_interval = self.base_recognition_interval + 6
        elif load_factor > 0.6:
            frame_skip = self.base_frame_skip + 2
            max_side = max(480, int(self.base_max_side * 0.75))
            recognition_interval = self.base_recognition_interval + 3
        else:
            frame_skip = self.base_frame_skip
            max_side = self.base_max_side
            recognition_interval = self.base_recognition_interval
        if motion_score < 8.0:
            frame_skip += 2
        return FrameOptimizationPlan(frame_skip=frame_skip, max_side=max_side, recognition_interval=recognition_interval)
