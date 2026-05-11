from __future__ import annotations

from dataclasses import dataclass, field
from contextlib import contextmanager
from collections.abc import Iterable as IterableABC
from pathlib import Path
from threading import BoundedSemaphore
from time import monotonic
from typing import Any, Iterable, Iterator

import numpy as np

from .cache.embeddings import EmbeddingCache
from .cache.memory import ThreadSafeTTLCache
from .cache.sessions import SessionStore
from .config import FliqConfig
from .detection.detector import AutoDetector, BoundingBox, DetectedFace, FaceDetector, WholeFrameDetector
from .detection.retinaface import RetinaFaceDetector
from .detection.scrfd import ScrfdDetector
try:
    from .detection.scrfd_onnx import ScrfdOnnxDetector  # type: ignore
except Exception:
    ScrfdOnnxDetector = None
from .embeddings.arcface import ArcFaceEmbedder
from .embeddings.buffalo import BuffaloEmbedder
from .embeddings.embedder import FaceEmbedder, LightweightEmbedder
try:
    from .embeddings.buffalo_onnx import BuffaloOnnxEmbedder  # type: ignore
except Exception:
    BuffaloOnnxEmbedder = None
from .tracking.bytetrack import ByteTrack
from .tracking.tracker import SimpleByteTrack, TrackedFace
try:
    from .tracking.bytetrack_full import ByteTrackLite  # type: ignore
except Exception:
    ByteTrackLite = None
from .vector.faiss_index import FaissVectorIndex, RecognitionMatch, VectorIndex
try:
    from .vector.faiss_optimized import FaissOptimizedIndex  # type: ignore
except Exception:
    FaissOptimizedIndex = None
from .video.motion import MotionDetector
from .video.stream import StreamFrame, VideoStream
try:
    from .video.scheduler import AdaptiveFrameScheduler  # type: ignore
except Exception:
    AdaptiveFrameScheduler = None
from .workers.async_pool import AsyncWorkerPool
from .workers.queue import BoundedQueue
from .workers.threads import ThreadPoolManager


@dataclass(slots=True)
class RecognitionResult:
    user_id: str
    confidence: float
    bbox: tuple[int, int, int, int]
    track_id: str | None = None
    unknown: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.user_id,
            "confidence": round(float(self.confidence), 4),
            "bbox": self.bbox,
            "track_id": self.track_id,
            "unknown": self.unknown,
            "metadata": self.metadata,
        }


@dataclass(slots=True)
class ClassroomTrackCache:
    result: dict[str, Any]
    recognized_at: float
    last_seen_at: float
    bbox: tuple[int, int, int, int]


@dataclass(slots=True)
class ClassroomCache:
    tracks: dict[str, ClassroomTrackCache] = field(default_factory=dict)
    seat_positions: dict[str, tuple[int, int, int, int]] = field(default_factory=dict)
    last_motion_score: float = 0.0
    last_update_at: float = 0.0


@dataclass(slots=True)
class EngineMetrics:
    recognition_calls: int = 0
    recognition_results: int = 0
    tracking_only_frames: int = 0  # Frames using cached tracking results
    cooldown_skipped_recognitions: int = 0  # Recognitions skipped due to cooldown
    stream_recoveries: int = 0
    stream_failures: int = 0
    frames_dropped: int = 0
    queue_peak_depth: int = 0
    started_at: float = field(default_factory=monotonic)
    last_error: str | None = None
    uptime_seconds: float = 0.0


class Fliq:
    def __init__(
        self,
        device: str = "auto",
        frame_skip: int = 5,
        tracking: bool = True,
        recognition_cooldown: float = 5.0,
        max_faces: int = 100,
        mode: str = "speed",
        recognition_interval: int = 10,
        confidence_threshold: float = 0.55,
        classroom_cache_size: int = 256,
        max_concurrent_streams: int = 20,
        adaptive_scheduler: bool = True,
        detector: str = "auto",
        embedder: str = "auto",
        tracker: str = "bytetrack",
        vector_backend: str = "faiss",
        warmup: bool = True,
        index_path: str | Path | None = None,
        **config_overrides: Any,
    ) -> None:
        self.config = FliqConfig(
            device=device,
            frame_skip=frame_skip,
            tracking=tracking,
            recognition_cooldown=recognition_cooldown,
            max_faces=max_faces,
            mode=mode,
            recognition_interval=recognition_interval,
            confidence_threshold=confidence_threshold,
            classroom_cache_size=classroom_cache_size,
            max_concurrent_streams=max_concurrent_streams,
            adaptive_scheduler=adaptive_scheduler,
            detector=detector,
            embedder=embedder,
            tracker=tracker,
            vector_backend=vector_backend,
            warmup=warmup,
            additional_options=dict(config_overrides),
        )
        self.index_path = Path(index_path) if index_path is not None else Path(".fliq_index")
        self.detector = self._build_detector()
        self.embedder = self._build_embedder()
        self.tracker = self._build_tracker()
        self.index = self._build_index()
        self.embedding_cache = EmbeddingCache(max_size=self.config.embedding_cache_size)
        self.match_cache = ThreadSafeTTLCache[str, list[dict[str, Any]]](max_size=self.config.cache_size, ttl_seconds=120.0)
        self.session_store = SessionStore()
        self.worker_pool = ThreadPoolManager()
        self.async_pool = AsyncWorkerPool()
        self.motion_detector = MotionDetector(threshold=self.config.motion_threshold)
        self.scheduler = AdaptiveFrameScheduler() if (self.config.adaptive_scheduler and AdaptiveFrameScheduler is not None) else None
        self._stream_guard = BoundedSemaphore(self.config.max_concurrent_streams)
        self.classroom_cache: dict[str, ClassroomCache] = {}
        self.metrics = EngineMetrics()
        self._track_memory: dict[str, dict[str, Any]] = {}
        self._track_last_recognized: dict[str, int] = {}
        self._warm = False
        self._load_saved_index_if_present()
        if self.config.warmup:
            self._warmup()

    def _load_saved_index_if_present(self) -> None:
        path = self.index_path
        if not path.exists():
            return
        if not any((path / name).exists() for name in ("meta.json", "embeddings.npy", "external_ids.npy", "index.faiss")):
            return
        try:
            self.load_index(path)
        except Exception:
            return

    def _build_detector(self) -> FaceDetector:
        detector_name = self.config.detector.lower()
        if detector_name == "scrfd":
            if ScrfdOnnxDetector is not None:
                try:
                    return ScrfdOnnxDetector(device=self.config.device)
                except Exception:
                    pass
            return ScrfdDetector()
        if detector_name == "retinaface":
            return RetinaFaceDetector()
        if detector_name == "wholeframe":
            return WholeFrameDetector()
        return AutoDetector(min_face_size=self.config.min_face_size)

    def _build_embedder(self) -> FaceEmbedder:
        embedder_name = self.config.embedder.lower()
        if embedder_name == "buffalo":
            if BuffaloOnnxEmbedder is not None:
                try:
                    return BuffaloOnnxEmbedder(device=self.config.device)
                except Exception:
                    pass
            return BuffaloEmbedder()
        if embedder_name == "arcface":
            return ArcFaceEmbedder()
        return LightweightEmbedder()

    def _build_tracker(self) -> SimpleByteTrack:
        if self.config.tracker and ByteTrackLite is not None:
            try:
                return ByteTrackLite()
            except Exception:
                pass
        return ByteTrack() if self.config.tracking else SimpleByteTrack(max_age=1)

    def _build_index(self) -> FaissVectorIndex:
        dimension = getattr(self.embedder, "dimension", 256)
        if FaissOptimizedIndex is not None:
            try:
                return FaissOptimizedIndex(dimension=dimension)
            except Exception:
                pass
        return FaissVectorIndex(dimension=dimension, use_ann=self.config.vector_backend == "faiss")

    def _warmup(self) -> None:
        if self._warm:
            return
        dummy = np.zeros((32, 32, 3), dtype=np.uint8)
        self.embedder.embed(dummy)
        self.detector.detect(dummy)
        self.motion_detector.detect(dummy)
        dummy_embedding = np.zeros((1, getattr(self.embedder, "dimension", 256)), dtype=np.float32)
        self.index.search(dummy_embedding, top_k=1)
        self._warm = True

    def _ensure_array(self, image: Any) -> np.ndarray:
        array = np.asarray(image)
        if array.ndim not in (2, 3):
            raise ValueError("Expected a 2D or 3D image array")
        return np.ascontiguousarray(array)

    def _crop(self, image: np.ndarray, bbox: BoundingBox) -> np.ndarray:
        y_slice, x_slice = bbox.to_slice()
        cropped = image[y_slice, x_slice]
        return np.ascontiguousarray(cropped)

    def _detect_faces(self, image: np.ndarray) -> list[DetectedFace]:
        detections = self.detector.detect(image)
        return detections[: self.config.max_faces]

    def _embed_faces(self, faces: list[np.ndarray]) -> np.ndarray:
        if not faces:
            return np.empty((0, getattr(self.embedder, "dimension", 256)), dtype=np.float32)
        cached_embeddings: list[np.ndarray | None] = []
        pending_images: list[np.ndarray] = []
        pending_indices: list[int] = []
        for index, face in enumerate(faces):
            cached = self.embedding_cache.get(face)
            if cached is None:
                cached_embeddings.append(None)
                pending_images.append(face)
                pending_indices.append(index)
            else:
                cached_embeddings.append(cached)
        if pending_images:
            computed = self.embedder.embed_batch(pending_images)
            for index, embedding, image in zip(pending_indices, computed, pending_images, strict=True):
                cached_embeddings[index] = embedding
                self.embedding_cache.set(image, embedding)
        return np.vstack([embedding for embedding in cached_embeddings if embedding is not None]).astype(np.float32, copy=False)

    def _classroom_key(self, class_id: str | None) -> str:
        return class_id or "default"

    def _get_classroom_cache(self, class_id: str | None) -> ClassroomCache:
        cache_key = self._classroom_key(class_id)
        cache = self.classroom_cache.get(cache_key)
        if cache is None:
            if len(self.classroom_cache) >= self.config.classroom_cache_size:
                oldest_key = next(iter(self.classroom_cache))
                self.classroom_cache.pop(oldest_key, None)
            cache = ClassroomCache()
            self.classroom_cache[cache_key] = cache
        return cache

    def _track_key(self, class_id: str | None, track_id: str) -> str:
        return f"{self._classroom_key(class_id)}:{track_id}"

    @contextmanager
    def _stream_slot(self):
        if not self._stream_guard.acquire(blocking=False):
            raise RuntimeError("Too many concurrent recognition streams")
        try:
            yield
        finally:
            self._stream_guard.release()

    def _cache_track_result(
        self,
        classroom_cache: ClassroomCache | None,
        class_id: str | None,
        track_id: str,
        result: dict[str, Any],
        bbox: tuple[int, int, int, int],
        recognized_at: float,
        frame_index: int,
    ) -> None:
        if classroom_cache is None:
            return
        classroom_cache.tracks[track_id] = ClassroomTrackCache(
            result=result,
            recognized_at=recognized_at,
            last_seen_at=recognized_at,
            bbox=bbox,
        )
        classroom_cache.seat_positions[track_id] = bbox
        classroom_cache.last_update_at = recognized_at
        track_key = self._track_key(class_id, track_id)
        self._track_last_recognized[track_key] = frame_index
        self._track_memory[track_key] = result

    def _cached_track_result(
        self,
        classroom_cache: ClassroomCache | None,
        class_id: str | None,
        track_id: str,
        bbox: tuple[int, int, int, int],
        now: float,
        frame_index: int,
        tracking_confidence: float = 0.0,
        motion_score: float = 0.0,
    ) -> dict[str, Any] | None:
        if classroom_cache is None:
            return None
        cached = classroom_cache.tracks.get(track_id)
        if cached is None:
            return None
        track_key = self._track_key(class_id, track_id)
        frame_delta = frame_index - self._track_last_recognized.get(track_key, frame_index)
        effective_cooldown = self.config.recognition_cooldown
        if tracking_confidence >= 0.95 and motion_score < self.config.motion_threshold * 0.5:
            effective_cooldown = max(effective_cooldown, 10.0)
        elif tracking_confidence >= 0.85 and motion_score < self.config.motion_threshold:
            effective_cooldown = max(effective_cooldown, 5.0)
        if now - cached.recognized_at >= effective_cooldown and frame_delta >= self.config.recognition_interval:
            return None
        cached.last_seen_at = now
        cached.bbox = bbox
        classroom_cache.seat_positions[track_id] = bbox
        result = dict(cached.result)
        result["bbox"] = bbox
        result["track_id"] = track_id
        self._track_memory[track_key] = result
        self._track_last_recognized[track_key] = frame_index
        return result

    def _recognize_embeddings(self, embeddings: np.ndarray) -> list[RecognitionMatch]:
        matches: list[RecognitionMatch] = []
        if embeddings.size == 0:
            return matches
        search_results = self.index.search(embeddings, top_k=self.config.similarity_top_k)
        for row in search_results:
            match = row[0] if row else RecognitionMatch(user_id=self.config.unknown_label, confidence=0.0, unknown=True)
            if match.confidence < self.config.confidence_threshold:
                match = RecognitionMatch(
                    user_id=self.config.unknown_label,
                    confidence=match.confidence,
                    distance=match.distance,
                    metadata=match.metadata,
                    unknown=True,
                )
            matches.append(match)
        return matches

    def _recognize_faces(self, image: np.ndarray, track_id: str | None = None) -> list[RecognitionResult]:
        self.metrics.recognition_calls += 1
        detections = self._detect_faces(image)
        crops = [self._crop(image, detection.bbox) for detection in detections]
        embeddings = self._embed_faces(crops)
        matches = self._recognize_embeddings(embeddings)
        results: list[RecognitionResult] = []
        for detection, match in zip(detections, matches, strict=True):
            result = RecognitionResult(
                user_id=match.user_id,
                confidence=match.confidence,
                bbox=(detection.bbox.x, detection.bbox.y, detection.bbox.width, detection.bbox.height),
                track_id=track_id,
                unknown=match.unknown,
                metadata=match.metadata,
            )
            results.append(result)
        self.metrics.recognition_results += len(results)
        return results

    def _stream_frames(self, source: str | int | Path | Iterable[np.ndarray]) -> Iterator[StreamFrame]:
        retryable_source = not isinstance(source, IterableABC) or isinstance(source, (str, bytes, Path, int))
        retries = 1 if retryable_source else 0
        while True:
            try:
                yield from VideoStream(source, max_side=self.config.detection_size)
                return
            except (RuntimeError, OSError) as exc:
                self.metrics.stream_failures += 1
                self.metrics.last_error = str(exc)
                if retries <= 0:
                    raise
                retries -= 1
                self.metrics.stream_recoveries += 1

    def register(self, user_id: str, image: Any) -> dict[str, Any]:
        array = self._ensure_array(image)
        detections = self._detect_faces(array)
        if not detections:
            detections = [DetectedFace(bbox=BoundingBox(0, 0, array.shape[1], array.shape[0]), score=1.0)]
        detection = max(detections, key=lambda item: item.bbox.area)
        crop = self._crop(array, detection.bbox)
        embedding = self.embedder.embed(crop)
        self.index.add(user_id, embedding, metadata={"source": "register"})
        self.embedding_cache.set(crop, embedding, {"user_id": user_id})
        return {"user_id": user_id, "status": "registered", "faces": len(detections)}

    def recognize(self, image: Any, class_id: str | None = None) -> list[dict[str, Any]]:
        with self._stream_slot():
            array = self._ensure_array(image)
            fingerprint = f"recognize:{self._classroom_key(class_id)}:{array.shape}:{int(array.sum())}"
            cached = self.match_cache.get(fingerprint)
            if cached is not None:
                return cached
            results = [result.to_dict() for result in self._recognize_faces(array)]
            self.match_cache.set(fingerprint, results)
            return results

    def recognize_video(self, video: str | int | Path | Iterable[np.ndarray]) -> list[dict[str, Any]]:
        return list(self.track_video(video, include_tracking=False))

    def track_video(self, source: str | int | Path | Iterable[np.ndarray], include_tracking: bool = True, class_id: str | None = None) -> Iterator[dict[str, Any]]:
        with self._stream_slot():
            classroom_cache = self._get_classroom_cache(class_id) if include_tracking else None
            for stream_frame in self._stream_frames(source):
                # compute adaptive frame skip
                frame_skip = self.config.frame_skip
                if self.scheduler is not None:
                    try:
                        status = self.scheduler.plan()
                        frame_skip = max(1, status.frame_skip)
                    except Exception:
                        frame_skip = self.config.frame_skip

                motion = self.motion_detector.detect(stream_frame.frame)
                if classroom_cache is not None:
                    classroom_cache.last_motion_score = motion.score

                # skip frames when advised by scheduler
                if stream_frame.index % frame_skip != 0:
                    cached_tracks = list(classroom_cache.tracks.values()) if classroom_cache is not None else []
                    yield {
                        "frame_index": stream_frame.index,
                        "motion": motion.score,
                        "tracks": [dict(track.result, bbox=track.bbox, track_id=track.result.get("track_id")) for track in cached_tracks],
                    }
                    continue

                if not motion.active and classroom_cache is not None and classroom_cache.tracks:
                    classroom_cache.last_update_at = monotonic()
                    yield {
                        "frame_index": stream_frame.index,
                        "motion": motion.score,
                        "tracks": [dict(track.result, bbox=track.bbox, track_id=track.result.get("track_id")) for track in classroom_cache.tracks.values()],
                    }
                    continue

                detections = self._detect_faces(stream_frame.frame)
                tracked_faces = self.tracker.update(detections) if include_tracking else [TrackedFace(track_id=f"frame-{stream_frame.index}-{idx}", bbox=detection.bbox, score=detection.score) for idx, detection in enumerate(detections)]
                frame_results: list[dict[str, Any]] = []
                for tracked_face in tracked_faces:
                    if include_tracking:
                        bbox = (tracked_face.bbox.x, tracked_face.bbox.y, tracked_face.bbox.width, tracked_face.bbox.height)
                        now = monotonic()
                        tracking_confidence = tracked_face.hits / max(1, tracked_face.hits + tracked_face.misses)
                        cached_result = self._cached_track_result(
                            classroom_cache,
                            class_id,
                            tracked_face.track_id,
                            bbox,
                            now,
                            stream_frame.index,
                            tracking_confidence=tracking_confidence,
                            motion_score=motion.score,
                        )
                        if cached_result is not None:
                            frame_results.append(cached_result)
                            continue
                        crop = self._crop(stream_frame.frame, tracked_face.bbox)
                        recognition = self._recognize_faces(crop, track_id=tracked_face.track_id)
                        result = recognition[0].to_dict() if recognition else {
                            "id": self.config.unknown_label,
                            "confidence": 0.0,
                            "bbox": bbox,
                            "track_id": tracked_face.track_id,
                            "unknown": True,
                            "metadata": {},
                        }
                        self._cache_track_result(classroom_cache, class_id, tracked_face.track_id, result, bbox, now, stream_frame.index)
                        frame_results.append(result)
                    else:
                        crop = self._crop(stream_frame.frame, tracked_face.bbox)
                        recognition = self._recognize_faces(crop)
                        frame_results.extend([item.to_dict() for item in recognition])
                yield {"frame_index": stream_frame.index, "motion": motion.score, "tracks": frame_results}

    def save_index(self, directory: str | Path | None = None) -> str:
        path = Path(directory) if directory is not None else self.index_path
        self.index.save(path)
        return str(path)

    def load_index(self, directory: str | Path | None = None) -> str:
        path = Path(directory) if directory is not None else self.index_path
        self.index = FaissVectorIndex.load(path)
        self.match_cache.clear()
        self.embedding_cache.clear()
        self.classroom_cache.clear()
        return str(path)

    def remove_user(self, user_id: str) -> None:
        self.index.remove_user(user_id)
        self.match_cache.clear()
        self.embedding_cache.clear()
        self.classroom_cache.clear()

    def snapshot_metrics(self) -> dict[str, Any]:
        """Get comprehensive engine metrics snapshot.
        
        Returns:
            Dictionary with detailed performance metrics
        """
        uptime = max(0.0, monotonic() - self.metrics.started_at)
        
        # Calculate recognition reduction percentage
        total_potential = self.metrics.recognition_calls * self.config.frame_skip
        if total_potential > 0:
            recognition_reduction_pct = 100.0 * (1.0 - self.metrics.recognition_results / total_potential)
        else:
            recognition_reduction_pct = 0.0
        
        # Count total frames in all classroom caches
        total_tracked_faces = sum(
            len(cache.tracks) for cache in self.classroom_cache.values()
        )
        
        return {
            # Performance metrics
            "fps_estimate": self.metrics.recognition_calls / max(1.0, uptime),
            "recognition_calls": self.metrics.recognition_calls,
            "recognition_results": self.metrics.recognition_results,
            "recognition_reduction_pct": round(recognition_reduction_pct, 2),
            
            # Optimization metrics
            "tracking_only_frames": self.metrics.tracking_only_frames,
            "cooldown_skipped_recognitions": self.metrics.cooldown_skipped_recognitions,
            
            # Stream health
            "stream_failures": self.metrics.stream_failures,
            "stream_recoveries": self.metrics.stream_recoveries,
            "frames_dropped": self.metrics.frames_dropped,
            
            # System state
            "uptime_seconds": round(uptime, 2),
            "classroom_cache_size": len(self.classroom_cache),
            "total_tracked_faces": total_tracked_faces,
            "queue_peak_depth": self.metrics.queue_peak_depth,
            
            # Error tracking
            "last_error": self.metrics.last_error,
            
            # Index info
            "index_size": len(self.index),
        }

    def optimize_existing(self, embeddings: np.ndarray, ids: Iterable[str]) -> dict[str, Any]:
        id_list = list(ids)
        if len(id_list) == 0:
            return {"status": "noop", "count": 0}
        self.index.add_batch(id_list, np.asarray(embeddings, dtype=np.float32))
        return {"status": "optimized", "count": len(id_list)}

    def close(self) -> None:
        self.worker_pool.shutdown()
        self.async_pool.close()

    def __enter__(self) -> "Fliq":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()
