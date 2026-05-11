"""Stream spawning utilities for multi-classroom stress testing."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator
from threading import Lock, Thread
from time import sleep, monotonic, perf_counter
from collections import deque
import numpy as np

from ..video.stream import StreamFrame, VideoStream


@dataclass(slots=True)
class StreamMetrics:
    """Per-stream metrics collection."""
    frames_processed: int = 0
    frames_dropped: int = 0
    frames_skipped: int = 0
    last_frame_time: float = 0.0
    fps_samples: deque = None
    fps_current: float = 0.0
    errors: int = 0
    last_error: str | None = None
    started_at: float = 0.0
    
    def __post_init__(self):
        if self.fps_samples is None:
            self.fps_samples = deque(maxlen=30)
        if self.started_at == 0.0:
            self.started_at = monotonic()
    
    def record_frame(self, timestamp: float | None = None) -> None:
        """Record frame processing."""
        if timestamp is None:
            timestamp = monotonic()
        self.frames_processed += 1
        
        if self.last_frame_time > 0:
            delta = timestamp - self.last_frame_time
            if delta > 0:
                fps = 1.0 / delta
                self.fps_samples.append(fps)
                self.fps_current = sum(self.fps_samples) / len(self.fps_samples)
        
        self.last_frame_time = timestamp
    
    def uptime_seconds(self) -> float:
        """Get uptime in seconds."""
        return monotonic() - self.started_at
    
    def to_dict(self) -> dict[str, Any]:
        """Export metrics as dict."""
        return {
            "frames_processed": self.frames_processed,
            "frames_dropped": self.frames_dropped,
            "frames_skipped": self.frames_skipped,
            "fps_current": round(self.fps_current, 2),
            "errors": self.errors,
            "last_error": self.last_error,
            "uptime_seconds": round(self.uptime_seconds(), 2),
        }


class StreamSpawner:
    """Spawn multiple concurrent video streams for stress testing."""
    
    def __init__(self, fps_target: int = 30, max_concurrent: int = 20):
        """Initialize stream spawner.
        
        Args:
            fps_target: Target FPS for simulated streams
            max_concurrent: Maximum concurrent streams
        """
        self.fps_target = fps_target
        self.max_concurrent = max_concurrent
        self.frame_delay = 1.0 / fps_target if fps_target > 0 else 0.0
        self.active_streams: dict[str, dict[str, Any]] = {}
        self._lock = Lock()
    
    def spawn_video_stream(
        self,
        stream_id: str,
        source: str | int | Path,
        callback: callable | None = None,
    ) -> StreamMetrics | None:
        """Spawn a video stream.
        
        Args:
            stream_id: Unique stream identifier
            source: Video source (file, webcam index, or RTSP URL)
            callback: Optional callback for each frame
        
        Returns:
            StreamMetrics or None if stream limit exceeded
        """
        with self._lock:
            if len(self.active_streams) >= self.max_concurrent:
                return None
            
            metrics = StreamMetrics()
            stream_data = {
                "metrics": metrics,
                "callback": callback,
                "active": True,
                "source": source,
            }
            self.active_streams[stream_id] = stream_data
        
        # Start stream processing in background thread
        thread = Thread(
            target=self._process_stream,
            args=(stream_id, source, callback, metrics),
            daemon=True,
            name=f"stream-{stream_id}",
        )
        thread.start()
        
        return metrics
    
    def _process_stream(
        self,
        stream_id: str,
        source: str | int | Path,
        callback: callable | None,
        metrics: StreamMetrics,
    ) -> None:
        """Process a single video stream."""
        try:
            frame_times = deque(maxlen=10)
            
            for stream_frame in VideoStream(source):
                with self._lock:
                    if stream_id not in self.active_streams:
                        return
                    if not self.active_streams[stream_id]["active"]:
                        return
                
                frame_start = perf_counter()
                
                try:
                    if callback is not None:
                        callback(stream_id, stream_frame)
                    
                    metrics.record_frame(monotonic())
                    
                    # Throttle to target FPS
                    frame_elapsed = perf_counter() - frame_start
                    sleep_time = max(0, self.frame_delay - frame_elapsed)
                    if sleep_time > 0:
                        sleep(sleep_time)
                
                except Exception as e:
                    metrics.errors += 1
                    metrics.last_error = str(e)
        
        except Exception as e:
            metrics.errors += 1
            metrics.last_error = f"Stream error: {str(e)}"
        
        finally:
            with self._lock:
                if stream_id in self.active_streams:
                    self.active_streams[stream_id]["active"] = False
    
    def stop_stream(self, stream_id: str) -> None:
        """Stop a specific stream."""
        with self._lock:
            if stream_id in self.active_streams:
                self.active_streams[stream_id]["active"] = False
    
    def stop_all(self) -> None:
        """Stop all streams."""
        with self._lock:
            for stream_data in self.active_streams.values():
                stream_data["active"] = False
    
    def get_metrics(self, stream_id: str) -> StreamMetrics | None:
        """Get metrics for a specific stream."""
        with self._lock:
            stream_data = self.active_streams.get(stream_id)
            return stream_data["metrics"] if stream_data else None
    
    def get_all_metrics(self) -> dict[str, StreamMetrics]:
        """Get metrics for all active streams."""
        with self._lock:
            return {
                stream_id: data["metrics"]
                for stream_id, data in self.active_streams.items()
            }
    
    def active_count(self) -> int:
        """Get number of active streams."""
        with self._lock:
            return sum(1 for data in self.active_streams.values() if data["active"])
    
    def total_frames(self) -> int:
        """Get total frames processed across all streams."""
        with self._lock:
            return sum(data["metrics"].frames_processed for data in self.active_streams.values())
