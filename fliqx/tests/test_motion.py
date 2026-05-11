from __future__ import annotations

import numpy as np

from fliqx.video.motion import MotionDetector


def test_motion_detector_flags_changes() -> None:
    detector = MotionDetector(threshold=1.0)
    first = np.zeros((8, 8, 3), dtype=np.uint8)
    second = np.ones((8, 8, 3), dtype=np.uint8) * 255
    assert detector.detect(first).active is True
    assert detector.detect(second).active is True
