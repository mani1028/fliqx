from __future__ import annotations

from dataclasses import dataclass, field


_MODE_DEFAULTS = {
    "speed": {"frame_skip": 5, "recognition_interval": 10, "confidence_threshold": 0.55},
    "balanced": {"frame_skip": 3, "recognition_interval": 6, "confidence_threshold": 0.6},
    "accuracy": {"frame_skip": 1, "recognition_interval": 3, "confidence_threshold": 0.65},
}


@dataclass(slots=True)
class FliqConfig:
    device: str = "auto"
    frame_skip: int = 5
    tracking: bool = True
    recognition_cooldown: float = 5.0
    max_faces: int = 100
    mode: str = "speed"
    recognition_interval: int = 10
    confidence_threshold: float = 0.55
    cache_size: int = 2048
    embedding_cache_size: int = 1024
    classroom_cache_size: int = 256
    max_concurrent_streams: int = 20
    adaptive_scheduler: bool = True
    queue_size: int = 256
    batch_size: int = 32
    detection_size: int = 640
    motion_threshold: float = 12.0
    warmup: bool = True
    detector: str = "auto"
    embedder: str = "auto"
    tracker: str = "bytetrack"
    vector_backend: str = "faiss"
    video_backend: str = "auto"
    min_face_size: int = 24
    similarity_top_k: int = 1
    unknown_label: str = "unknown"
    additional_options: dict[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        mode = self.mode.lower().strip()
        if mode not in _MODE_DEFAULTS:
            raise ValueError(f"Unsupported mode: {self.mode}")
        defaults = _MODE_DEFAULTS[mode]
        if self.frame_skip < 1:
            raise ValueError("frame_skip must be >= 1")
        if self.recognition_cooldown < 0:
            raise ValueError("recognition_cooldown must be >= 0")
        if self.recognition_interval < 1:
            raise ValueError("recognition_interval must be >= 1")
        if self.max_faces < 1:
            raise ValueError("max_faces must be >= 1")
        if self.batch_size < 1:
            raise ValueError("batch_size must be >= 1")
        if self.classroom_cache_size < 1:
            raise ValueError("classroom_cache_size must be >= 1")
        if self.max_concurrent_streams < 1:
            raise ValueError("max_concurrent_streams must be >= 1")
        if not 0.0 <= self.confidence_threshold <= 1.0:
            raise ValueError("confidence_threshold must be between 0 and 1")
        self.mode = mode
        self.frame_skip = max(self.frame_skip, defaults["frame_skip"])
        self.recognition_interval = max(self.recognition_interval, defaults["recognition_interval"])
        self.confidence_threshold = max(self.confidence_threshold, defaults["confidence_threshold"])
