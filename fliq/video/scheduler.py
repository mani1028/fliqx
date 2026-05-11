from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

try:
    import psutil  # type: ignore
except Exception:  # pragma: no cover - optional
    psutil = None


@dataclass(slots=True)
class SchedulerStatus:
    cpu_percent: float
    gpu_percent: float | None
    frame_skip: int
    load_factor: float


class AdaptiveFrameScheduler:
    def __init__(self, base_frame_skip: int = 2, max_frame_skip: int = 10) -> None:
        self.base_frame_skip = base_frame_skip
        self.max_frame_skip = max_frame_skip

    def measure_load(self) -> float:
        if psutil is None:
            return 0.0
        try:
            cpu = psutil.cpu_percent(interval=0.1)
            # simple load factor based on CPU usage
            return min(1.0, max(0.0, cpu / 100.0))
        except Exception:
            return 0.0

    def plan(self) -> SchedulerStatus:
        load = self.measure_load()
        # scale frame_skip between base and max
        skip = int(self.base_frame_skip + (self.max_frame_skip - self.base_frame_skip) * load)
        return SchedulerStatus(cpu_percent=load * 100.0, gpu_percent=None, frame_skip=max(1, skip), load_factor=load)


__all__ = ["AdaptiveFrameScheduler", "SchedulerStatus"]
