from __future__ import annotations

import numpy as np

from fliqx.benchmarks import benchmark_classroom_load, benchmark_recognition
from fliqx.detection.detector import BoundingBox, DetectedFace
from fliqx.engine import Fliq, RecognitionResult


def _sample_image(seed: int = 1) -> np.ndarray:
    rng = np.random.default_rng(seed)
    return rng.integers(0, 255, size=(64, 64, 3), dtype=np.uint8)


def test_benchmark_recognition_reports_recognition_work(monkeypatch) -> None:
    engine = Fliq(warmup=False, detector="wholeframe", tracking=False, adaptive_scheduler=False)
    monkeypatch.setattr(engine, "_detect_faces", lambda image: [DetectedFace(bbox=BoundingBox(0, 0, 32, 32), score=1.0)])
    monkeypatch.setattr(
        engine,
        "_recognize_faces",
        lambda image, track_id=None: [RecognitionResult(user_id="student-1", confidence=0.99, bbox=(0, 0, 32, 32), track_id=track_id)],
    )

    result = benchmark_recognition(engine, _sample_image(), iterations=5)

    assert result.iterations == 5
    assert result.recognition_calls == 5
    assert result.recognition_results == 5
    assert result.fps > 0.0


def test_benchmark_classroom_load_tracks_concurrent_streams(monkeypatch) -> None:
    engine = Fliq(warmup=False, detector="wholeframe", tracking=True, frame_skip=1, adaptive_scheduler=False)
    monkeypatch.setattr(engine, "_detect_faces", lambda image: [DetectedFace(bbox=BoundingBox(0, 0, 32, 32), score=1.0)])
    monkeypatch.setattr(
        engine,
        "_recognize_faces",
        lambda image, track_id=None: [RecognitionResult(user_id="student-1", confidence=0.99, bbox=(0, 0, 32, 32), track_id=track_id)],
    )

    classrooms = {
        "class-a": [_sample_image(1), _sample_image(2), _sample_image(3)],
        "class-b": [_sample_image(4), _sample_image(5), _sample_image(6)],
    }
    result = benchmark_classroom_load(engine, classrooms, max_workers=2)

    assert result.iterations == 6
    assert result.recognition_calls > 0
    assert result.concurrent_streams <= 2
    assert result.queue_peak_size >= 1