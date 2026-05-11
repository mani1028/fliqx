from __future__ import annotations

import numpy as np

from fliq.detection.detector import BoundingBox, DetectedFace
from fliq.engine import RecognitionResult
from fliq import Fliq


def _sample_image(seed: int = 1) -> np.ndarray:
    rng = np.random.default_rng(seed)
    return rng.integers(0, 255, size=(64, 64, 3), dtype=np.uint8)


def test_register_and_recognize_same_image() -> None:
    engine = Fliq(warmup=False, detector="wholeframe", tracking=False)
    image = _sample_image()
    register_result = engine.register("user-1", image)
    assert register_result["status"] == "registered"

    results = engine.recognize(image)
    assert results
    assert results[0]["id"] == "user-1"
    assert results[0]["confidence"] >= 0.0


def test_save_and_load_index(tmp_path) -> None:
    engine = Fliq(warmup=False, detector="wholeframe", tracking=False)
    image = _sample_image()
    engine.register("user-1", image)
    saved_path = engine.save_index(tmp_path / "index")
    assert saved_path

    restored = Fliq(warmup=False, detector="wholeframe", tracking=False)
    restored.load_index(tmp_path / "index")
    results = restored.recognize(image)
    assert results[0]["id"] == "user-1"


def test_startup_preloads_saved_index(tmp_path) -> None:
    engine = Fliq(warmup=False, detector="wholeframe", tracking=False)
    image = _sample_image()
    engine.register("user-1", image)
    engine.save_index(tmp_path / "index")

    restored = Fliq(warmup=False, detector="wholeframe", tracking=False, index_path=tmp_path / "index")
    assert restored.index.size == 1


def test_track_video_applies_recognition_cooldown(monkeypatch) -> None:
    engine = Fliq(warmup=False, detector="wholeframe", tracking=True, frame_skip=1, recognition_cooldown=5.0, adaptive_scheduler=False)
    frame = _sample_image()
    detections = [DetectedFace(bbox=BoundingBox(8, 8, 32, 32), score=1.0)]
    monkeypatch.setattr(engine, "_detect_faces", lambda image: detections)

    call_count = {"value": 0}

    def fake_recognize_faces(image, track_id=None):
        call_count["value"] += 1
        return [RecognitionResult(user_id="user-1", confidence=0.99, bbox=(8, 8, 32, 32), track_id=track_id)]

    monkeypatch.setattr(engine, "_recognize_faces", fake_recognize_faces)

    results = list(engine.track_video([frame, frame, frame], include_tracking=True, class_id="class-1"))
    assert results
    assert call_count["value"] == 1
