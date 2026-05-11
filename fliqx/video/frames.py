from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from ..utils import resize_nearest


@dataclass(slots=True)
class FrameWindow:
    frame: np.ndarray
    index: int


def resize_frame(frame: np.ndarray, max_side: int) -> np.ndarray:
    height, width = frame.shape[:2]
    longest = max(height, width)
    if longest <= max_side:
        return np.ascontiguousarray(frame)
    scale = max_side / float(longest)
    target_height = max(1, int(round(height * scale)))
    target_width = max(1, int(round(width * scale)))
    if frame.ndim == 2:
        frame = frame[:, :, None]
    return resize_nearest(frame, (target_height, target_width))


def frame_windows(frames: list[np.ndarray], stride: int) -> list[FrameWindow]:
    stride = max(1, stride)
    return [FrameWindow(frame=frame, index=index) for index, frame in enumerate(frames) if index % stride == 0]
